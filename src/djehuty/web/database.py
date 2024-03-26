"""
This module provides the communication with the SPARQL endpoint to provide
data for the API server.
"""

import uuid
import secrets
import os.path
import logging
from datetime import datetime
from urllib.error import URLError, HTTPError
from rdflib import Dataset, Graph, Literal, RDF, XSD, URIRef
from rdflib.plugins.stores import sparqlstore, memory
from rdflib.store import CORRUPTED_STORE, NO_STORE
from jinja2 import Environment, FileSystemLoader
from djehuty.web import cache
from djehuty.utils import rdf
from djehuty.utils import convenience as conv

class SparqlInterface:
    """This class reads and writes data from a SPARQL endpoint."""

    def __init__ (self):

        self.storage     = None
        self.secondary_storage = None
        self.secondary_storage_quirks = False
        self.endpoint    = "http://127.0.0.1:8890/sparql"
        self.update_endpoint = None
        self.state_graph = "https://data.4tu.nl/portal/self-test"
        self.privileges  = {}
        self.thumbnail_storage = None
        self.profile_images_storage = None
        self.log         = logging.getLogger(__name__)
        self.cache       = cache.CacheLayer(None)
        self.jinja       = Environment(loader = FileSystemLoader(
                            os.path.join(os.path.dirname(__file__),
                                         "resources/sparql_templates")),
                                         autoescape=True)
        self.sparql       = None
        self.sparql_is_up = False
        self.enable_query_audit_log = False
        self.account_quotas = {}
        self.group_quotas   = {}
        self.default_quota  = 5000000000
        self.store          = None
        self.disable_collaboration = True

    def setup_sparql_endpoint (self):
        """Procedure to be called after setting the 'endpoint' members."""

        # BerkeleyDB as local RDF store.
        if (isinstance (self.endpoint, str) and self.endpoint.startswith("bdb://")):
            directory = self.endpoint[6:]
            self.sparql = Dataset("BerkeleyDB")
            self.sparql.open (directory, create=True)
            if not isinstance (self.sparql, Dataset):
                if self.sparql == CORRUPTED_STORE:
                    self.log.error ("'%s' is corrupt.", directory)
                elif self.sparql == NO_STORE:
                    self.log.error ("'%s' is not a BerkeleyDB store.", directory)
                else:
                    self.log.error ("Loading '%s' returned %s.", directory, self.sparql)
                return None
            self.log.info ("Using BerkeleyDB RDF store.")

        # In-memory SPARQL endpoint. This does not work when live-reload
        # is enabled.
        elif (isinstance (self.endpoint, str) and
              self.endpoint.startswith ("memory://")):
            self.store = memory.Memory(identifier = URIRef(self.state_graph))
            self.sparql = Dataset(store = self.store)
            self.log.info ("Using in-memory RDF store.")

        # External SPARQL endpoints, like Virtuoso.
        else:
            if self.update_endpoint is None:
                self.update_endpoint = self.endpoint

            self.store = sparqlstore.SPARQLUpdateStore(
                # Avoid rdflib from wrapping in a blank-node graph by setting
                # context_aware to False.
                context_aware   = False,
                autocommit      = False,
                query_endpoint  = self.endpoint,
                update_endpoint = self.update_endpoint,
                returnFormat    = "json",
                method          = "POST")
            # Set bind_namespaces so rdflib does not inject PREFIXes.
            self.sparql  = Graph(store = self.store, bind_namespaces = "none")
            self.log.info ("Using external RDF store.")

        self.sparql_is_up = True
        return None

    ## ------------------------------------------------------------------------
    ## Private methods
    ## ------------------------------------------------------------------------

    def __log_query (self, query, prefix="Query"):
        self.log.info ("%s:\n---\n%s\n---", prefix, query)

    def __normalize_binding (self, row):
        output = {}
        for name in row.keys():
            if isinstance(row[name], Literal):
                xsd_type = row[name].datatype
                if xsd_type == XSD.integer:
                    output[str(name)] = int(float(row[name]))
                elif xsd_type == XSD.decimal:
                    output[str(name)] = int(float(row[name]))
                elif xsd_type == XSD.boolean:
                    try:
                        output[str(name)] = bool(int(row[name]))
                    except ValueError:
                        output[str(name)] = str(row[name]).lower() == "true"
                elif xsd_type == XSD.dateTime:
                    time_value = row[name].partition(".")[0]
                    if time_value[-1] == 'Z':
                        time_value = time_value[:-1]
                    if time_value.endswith("+00:00"):
                        time_value = time_value[:-6]
                    output[str(name)] = time_value
                elif xsd_type == XSD.date:
                    output[str(name)] = row[name]
                elif xsd_type == XSD.string:
                    if row[name] == "NULL":
                        output[str(name)] = None
                    else:
                        output[str(name)] = str(row[name])
                # bindings that were produced with BIND() on Virtuoso
                # have no XSD type.
                elif xsd_type is None:
                    output[str(name)] = str(row[name])
            elif row[name] is None:
                output[str(name)] = None
            else:
                output[str(name)] = str(row[name])

        return output

    def __normalize_orcid (self, orcid):
        """Procedure to make storing ORCID identifiers consistent."""
        # Don't process invalid entries
        if not isinstance(orcid, str):
            return None
        # Don't store empty ORCID identifiers.
        orcid = orcid.strip()
        if orcid == "":
            return None
        # Strip the URI prefix from ORCID identifiers.
        if orcid.startswith ("https://orcid.org/"):
            return orcid[18:]

        return orcid

    def __query_from_template (self, name, args=None):
        template   = self.jinja.get_template (f"{name}.sparql")
        parameters = {
            "state_graph":           self.state_graph,
            "disable_collaboration": self.disable_collaboration
        }
        if args is None:
            args = {}

        return template.render ({ **args, **parameters })

    def __run_logged_query (self, query):
        """Passthrough for '__run_query' that handles the audit log feature."""

        if self.enable_query_audit_log:
            self.__log_query (query, "Query Audit Log")

        return self.__run_query (query)

    def __run_query (self, query, cache_key_string=None, prefix=None, retries=5):

        cache_key = None
        if cache_key_string is not None:
            cache_key = self.cache.make_key (cache_key_string)
            cached    = self.cache.cached_value(prefix, cache_key)
            if cached is not None:
                return cached

        results = []
        try:
            execution_type, query_type = rdf.query_type (query)
            if execution_type == "update":
                self.sparql.update (query)
                self.sparql.commit()
                ## Upon failure, an exception is thrown.
                results = True
            elif execution_type == "gather":
                query_results = self.sparql.query(query)
                ## ASK queries only return a boolean.
                if query_type == "ASK":
                    results = query_results.askAnswer
                elif isinstance(query_results, tuple):
                    self.log.error ("Error executing query (%s): %s",
                                    query_results[0], query_results[1])
                    self.__log_query (query)
                    return []
                else:
                    results = list(map(self.__normalize_binding,
                                       query_results.bindings))
            else:
                self.log.error ("Invalid query (%s, %s)", execution_type, query_type)
                self.__log_query (query)
                return []

            if cache_key_string is not None:
                self.cache.cache_value (prefix, cache_key, results, query)

            if not self.sparql_is_up:
                self.log.info ("Connection to the SPARQL endpoint seems up again.")
                self.sparql_is_up = True

        except HTTPError as error:
            self.sparql.rollback()
            if error.code == 503:
                if retries > 0:
                    self.log.warning ("Retrying SPARQL request due to service unavailability (%s)",
                                      retries)
                    return self.__run_query (query, cache_key_string=cache_key_string,
                                             prefix=prefix, retries=retries-1)

                self.log.warning ("Giving up on retrying SPARQL request.")

            self.log.error ("SPARQL endpoint returned %d:\n---\n%s\n---",
                            error.code, error.reason)

            return []
        except URLError:
            if self.sparql_is_up:
                self.log.error ("Connection to the SPARQL endpoint seems down.")
                self.sparql_is_up = False
                return []
        except AttributeError as error:
            self.log.error ("SPARQL query failed.")
            self.log.error ("Exception: %s", error)
            self.__log_query (query)
        except Exception as error:  # pylint: disable=broad-exception-caught
            self.log.error ("SPARQL query failed.")
            self.log.error ("Exception: %s: %s", type(error), error)
            self.__log_query (query)
            return []

        return results

    def __insert_query_for_graph (self, graph):
        if self.enable_query_audit_log:
            query = rdf.insert_query (self.state_graph, graph)
            self.__log_query (query, "Query Audit Log")
            return query
        return rdf.insert_query (self.state_graph, graph)

    ## ------------------------------------------------------------------------
    ## GET METHODS
    ## ------------------------------------------------------------------------

    def dataset_storage_used (self, dataset_uuid):
        """Returns the number of bytes used by a dataset."""

        query = self.__query_from_template ("dataset_storage_used", {
            "dataset_uuid": dataset_uuid
        })

        results = self.__run_query (query, query, f"{dataset_uuid}_dataset_storage")
        try:
            return results[0]["bytes"]
        except (IndexError, KeyError):
            pass

        return 0

    def dataset_versions (self, limit=1000, offset=0, order="version",
                          order_direction="desc", container_uri=None):
        """Procedure to retrieve the versions of a dataset."""

        query = self.__query_from_template ("dataset_versions", {
            "container_uri": container_uri
        })
        query += rdf.sparql_suffix (order, order_direction, limit, offset)

        return self.__run_query (query)

    def container_items (self, account_uuid=None, container_uuid=None,
                         item_uuid=None, is_published=True, is_latest=False):
        """Returns datasets or collections filtered by its parameters."""

        query = self.__query_from_template ("container_items", {
            "account_uuid":   account_uuid,
            "container_uri":  rdf.uuid_to_uri (container_uuid, "container"),
            "item_uuid":      item_uuid,
            "is_latest":      is_latest,
            "is_published":   is_published
        })

        return self.__run_query (query)

    def __search_query_to_sparql_filters (self, search_for, search_format):
        """
        Procedure to parse search queries and return SPARQL FILTER statements.
        """

        filters = ""
        if search_for is None:
            return filters

        if isinstance (search_for, str):
            # turn into list for loop purposes
            search_for = [search_for]
        if dict in list(map(type, search_for)):
            filters += "FILTER ("
            last_used_field = None
            for element in search_for:
                if (isinstance (element, dict)
                    and len(element.items()) == 1
                    and next(iter(element)) == "operator"):
                    if element['operator'] == "(":
                        filters += " ( "
                        continue
                    if element['operator'] == ")":
                        filters += " ) "
                    filters += f" {element['operator']} "
                # This is a case that a search term comes after field search
                # :tag: maize processing -> tag:maize || tag:processing
                # :tag: maize AND processing -> tag:maize && tag:processing
                elif isinstance (element, str):
                    if last_used_field is None:
                        continue
                    escaped_value = rdf.escape_string_value (element.lower())
                    filters += f"CONTAINS(LCASE(?{last_used_field}), {escaped_value})\n"
                    continue
                else:
                    filter_list = []
                    for key, value in element.items():
                        if value == "":
                            continue
                        escaped_value = rdf.escape_string_value (value.lower())
                        filter_list.append(f"CONTAINS(LCASE(?{key}), {escaped_value})\n")
                        last_used_field = key
                    if filter_list:
                        filters += (f"({' || '.join(filter_list)})")
            filters += ")"

            # Post-construction heuristical query fixing
            # It's undocumented because it needs to be replaced.
            filters = filters.replace("FILTER ( || ", "FILTER (")
            filters = filters.replace(")CONTAINS", ") || CONTAINS")
            filters = filters.replace(")\nCONTAINS", ") || CONTAINS")
            filters = filters.replace(")(", ") || (")
            filters = filters.replace(")  )", ")")
        else:
            filter_list = []
            for search_term in search_for:
                search_term_safe = rdf.escape_string_value (search_term.lower())

                # should be the same as ApiServer.ui_search()'s fields.
                fields = ["title", "resource_title", "description", "tag", "organizations"]
                for field in fields:
                    filter_list.append(f"       CONTAINS(LCASE(?{field}),          {search_term_safe})")

                if search_format:
                    filter_list.append(f"       CONTAINS(LCASE(?format),         {search_term_safe})")
            if len(filter_list) > 0:
                filters += f"FILTER({' || '.join(filter_list)})"

        return filters

    def datasets (self, account_uuid=None, categories=None, collection_uri=None,
                  container_uuid=None, dataset_id=None, dataset_uuid=None, doi=None,
                  exclude_ids=None, groups=None, handle=None, institution=None,
                  is_latest=False, item_type=None, limit=None, modified_since=None,
                  offset=None, order=None, order_direction=None, published_since=None,
                  resource_doi=None, return_count=False, search_for=None, search_format=False,
                  version=None, is_published=True, is_under_review=None, git_uuid=None,
                  private_link_id_string=None, use_cache=True, is_restricted=None,
                  is_embargoed=None, is_software=None):
        """Procedure to retrieve version(s) of datasets."""

        filters  = rdf.sparql_filter ("container_uri",  rdf.uuid_to_uri (container_uuid, "container"), is_uri=True)
        filters += rdf.sparql_filter ("dataset",        rdf.uuid_to_uri (dataset_uuid, "dataset"), is_uri=True)
        filters += rdf.sparql_filter ("institution_id", institution)
        filters += rdf.sparql_filter ("defined_type",   item_type)
        filters += rdf.sparql_filter ("dataset_id",     dataset_id)
        filters += rdf.sparql_filter ("git_uuid",       git_uuid,     escape=True)
        filters += rdf.sparql_filter ("version",        version)
        filters += rdf.sparql_filter ("resource_doi",   resource_doi, escape=True)
        filters += rdf.sparql_filter ("doi",            doi,          escape=True)
        filters += rdf.sparql_filter ("handle",         handle,       escape=True)
        filters += rdf.sparql_filter ("is_restricted",          is_restricted)
        filters += rdf.sparql_filter ("is_embargoed",           is_embargoed)
        filters += rdf.sparql_filter ("private_link_id_string", private_link_id_string, escape=True)
        filters += rdf.sparql_in_filter ("group_id",    groups)
        filters += rdf.sparql_in_filter ("dataset_id", exclude_ids, negate=True)
        filters += self.__search_query_to_sparql_filters (search_for, search_format)

        if is_software is not None:
            if is_software:
                filters += rdf.sparql_filter ("defined_type_name", "software", escape=True)
            else:
                filters += rdf.sparql_filter ("defined_type_name", "dataset", escape=True)

        if categories is not None:
            filters += f"FILTER ((?category_id IN ({','.join(map(str, categories))})) || "
            filters += f"(?parent_category_id IN ({','.join(map(str, categories))})))\n"

        if published_since is not None:
            published_since_safe = rdf.escape_datetime_value (published_since)
            filters += rdf.sparql_bound_filter ("published_date")
            filters += f"FILTER (?published_date > {published_since_safe})\n"

        if modified_since is not None:
            modified_since_safe = rdf.escape_datetime_value (modified_since)
            filters += rdf.sparql_bound_filter ("modified_date")
            filters += f"FILTER (STR(?modified_date) > STR({modified_since_safe}))\n"

        query = self.__query_from_template ("datasets", {
            "categories":     categories,
            "collection_uri": collection_uri,
            "account_uuid":   account_uuid,
            "is_latest":      is_latest,
            "is_published":   is_published,
            "is_under_review": is_under_review,
            "private_link_id_string": private_link_id_string,
            "filters":        filters,
            "return_count":   return_count
        })

        # Setting the default value for 'limit' to 10 makes passing
        # parameters from HTTP requests cumbersome. Therefore, we
        # set the default again here.
        if limit is None:
            limit = 10

        if not return_count:
            query += rdf.sparql_suffix (order, order_direction, limit, offset)

        if use_cache:
            cache_prefix = f"datasets_{account_uuid}" if account_uuid is not None else "datasets"
            return self.__run_query (query, query, cache_prefix)

        return self.__run_query (query)

    def datasets_missing_dois (self):
        """Procedure to retrieve datasets where a DOI registration went wrong."""
        query = self.__query_from_template ("datasets_missing_dois")
        return self.__run_query (query)

    def repository_statistics (self):
        """Procedure to retrieve repository-wide statistics."""

        datasets_query    = self.__query_from_template ("statistics_datasets")
        collections_query = self.__query_from_template ("statistics_collections")
        authors_query     = self.__query_from_template ("statistics_authors")
        files_query       = self.__query_from_template ("statistics_files")

        row = { "datasets": 0, "authors": 0, "collections": 0, "files": 0, "bytes": 0 }
        try:
            datasets    = self.__run_query (datasets_query, datasets_query, "repository_statistics")
            authors     = self.__run_query (authors_query, authors_query, "repository_statistics")
            collections = self.__run_query (collections_query, collections_query, "repository_statistics")
            files       = self.__run_query (files_query, files_query, "repository_statistics")
            number_of_files = 0
            number_of_bytes = 0
            for entry in files:
                number_of_files += 1
                number_of_bytes += int(float(entry["bytes"]))

            files_results = {
                "files": number_of_files,
                "bytes": number_of_bytes
            }
            row = { **datasets[0], **authors[0], **collections[0], **files_results }
        except (IndexError, KeyError):
            pass

        return row

    def dataset_statistics (self, item_type="downloads",
                                  order="downloads",
                                  order_direction="desc",
                                  group_ids=None,
                                  category_ids=None,
                                  limit=10,
                                  offset=0):
        """Procedure to retrieve dataset statistics."""

        prefix  = item_type.capitalize()
        filters = ""

        filters += rdf.sparql_in_filter ("category_id", category_ids)
        filters += rdf.sparql_in_filter ("group_id", group_ids)

        query   = self.__query_from_template ("dataset_statistics", {
            "category_ids":  category_ids,
            "item_type":     item_type,
            "prefix":        prefix,
            "filters":       filters
        })

        query += rdf.sparql_suffix (order, order_direction, limit, offset)
        return self.__run_query (query, query, "statistics")

    def dataset_statistics_timeline (self,
                                     dataset_id=None,
                                     item_type="downloads",
                                     order="downloads",
                                     order_direction="desc",
                                     category_ids=None,
                                     limit=10,
                                     offset=0):
        """Procedure to retrieve dataset statistics per date."""

        item_class  = item_type.capitalize()
        filters = ""

        filters += rdf.sparql_filter ("dataset_id", dataset_id)
        filters += rdf.sparql_in_filter ("category_id", category_ids)

        query   = self.__query_from_template ("dataset_statistics_timeline", {
            "category_ids":  category_ids,
            "item_type":     item_type,
            "item_class":    item_class,
            "filters":       filters
        })

        order = "dataset_id" if order is None else order
        query += rdf.sparql_suffix (order, order_direction, limit, offset)
        return self.__run_query (query, query, "statistics")

    def container_uuid_by_id (self, identifier, item_type="dataset"):
        """Procedure to retrieve container_uuid from Figshare id if necessary"""

        if conv.parses_to_int (identifier):
            try:
                query = self.__query_from_template ("container_uuid_by_id", {
                    "container_id": identifier,
                    "item_type"   : item_type
                })
                result = self.__run_query (query)
                return result[0]["container_uuid"]
            except (IndexError, KeyError):
                self.log.error ("Retrieving uuid for %s failed.", identifier)
                return None

        return identifier

    def container (self, container_uuid, item_type="dataset", use_cache=True):
        """Procedure to get container properties (incl shallow statistics)."""

        query   = self.__query_from_template ("container", {
            "item_type"     : item_type,
            "container_uuid": container_uuid
        })

        try:
            if use_cache:
                return self.__run_query (query, query, "container")[0]
            return self.__run_query (query)[0]
        except (TypeError, IndexError):
            self.log.error ("Retrieving container for %s failed.", container_uuid)
            return None

    def authors (self, first_name=None, full_name=None, group_id=None,
                 author_id=None, institution_id=None, is_active=None,
                 is_public=None, job_title=None, last_name=None,
                 orcid_id=None, url_name=None, limit=10, order="order_index",
                 order_direction="asc", item_uri=None, search_for=None,
                 account_uuid=None, item_type="dataset", is_published=True):
        """Procedure to retrieve authors of a dataset."""

        prefix = item_type.capitalize()

        filters  = rdf.sparql_filter ("group_id",       group_id)
        filters += rdf.sparql_filter ("id",             author_id)
        filters += rdf.sparql_filter ("institution_id", institution_id)
        filters += rdf.sparql_filter ("is_active",      is_active)
        filters += rdf.sparql_filter ("is_public",      is_public)
        filters += rdf.sparql_filter ("job_title",      job_title,  escape=True)
        filters += rdf.sparql_filter ("first_name",     first_name, escape=True)
        filters += rdf.sparql_filter ("last_name",      last_name,  escape=True)
        filters += rdf.sparql_filter ("full_name",      full_name,  escape=True)
        filters += rdf.sparql_filter ("orcid_id",       orcid_id,   escape=True)
        filters += rdf.sparql_filter ("url_name",       url_name,   escape=True)

        if search_for is not None:
            escaped = rdf.escape_string_value (search_for.lower())
            filters += (f"FILTER (CONTAINS(LCASE(?first_name), {escaped}) ||\n"
                        f"        CONTAINS(LCASE(?last_name),  {escaped}) ||\n"
                        f"        CONTAINS(LCASE(?full_name),  {escaped}) ||\n"
                        f"        CONTAINS(LCASE(?orcid_id),   {escaped}))")

        query = self.__query_from_template ("authors", {
            "item_type":   item_type,
            "prefix":      prefix,
            "is_published": is_published,
            "item_uri":    item_uri,
            "account_uuid": account_uuid,
            "filters":     filters
        })
        query += rdf.sparql_suffix (order, order_direction, limit, None)

        return self.__run_query(query)

    def author_profile (self, author_uri):
        """Returns author and account information for an AUTHOR_URI."""
        query = self.__query_from_template ("author_profile", {
            "author_uri": author_uri
        })
        return self.__run_query(query)

    def author_public_items (self, author_uri):
        """Returns the public datasets and collections of a given AUTHOR_URI."""
        query = self.__query_from_template ("author_public_items", {
            "author_uri": author_uri
        })
        return self.__run_query(query)

    def associated_authors (self, author_uri):
        """Returns collaborating authors for a given AUTHOR_URI."""
        query = self.__query_from_template ("associated_authors", {
            "author_uri": author_uri
        })
        return self.__run_query(query)

    def dataset_files (self, name=None, size=None, is_link_only=None,
                       file_uuid=None, download_url=None, supplied_md5=None,
                       computed_md5=None, viewer_type=None, preview_state=None,
                       status=None, upload_url=None, upload_token=None,
                       order="order_index", order_direction="asc", limit=None,
                       dataset_uri=None, account_uuid=None, file_id=None,
                       private_view=None, is_incomplete=None, is_image=None):
        """Procedure to retrieve files of a dataset."""

        filters  = rdf.sparql_filter ("size",          size)
        filters += rdf.sparql_filter ("is_link_only",  is_link_only)
        filters += rdf.sparql_filter ("id",            file_id)
        filters += rdf.sparql_filter ("name",          name,          escape=True)
        filters += rdf.sparql_filter ("download_url",  download_url,  escape=True)
        filters += rdf.sparql_filter ("supplied_md5",  supplied_md5,  escape=True)
        filters += rdf.sparql_filter ("computed_md5",  computed_md5,  escape=True)
        filters += rdf.sparql_filter ("viewer_type",   viewer_type,   escape=True)
        filters += rdf.sparql_filter ("preview_state", preview_state, escape=True)
        filters += rdf.sparql_filter ("status",        status,        escape=True)
        filters += rdf.sparql_filter ("upload_url",    upload_url,    escape=True)
        filters += rdf.sparql_filter ("upload_token",  upload_token,  escape=True)
        filters += rdf.sparql_filter ("is_incomplete", is_incomplete)
        filters += rdf.sparql_filter ("is_image",      is_image)

        query = self.__query_from_template ("dataset_files", {
            "dataset_uri":         dataset_uri,
            "account_uuid":        account_uuid,
            "private_view":        private_view,
            "file_uuid":           file_uuid,
            "filters":             filters
        })

        query += rdf.sparql_suffix (order, order_direction, limit, None)

        return self.__run_query(query)

    def derived_from (self, item_uri, item_type='dataset',
                      order=None, order_direction=None, limit=10):
        """Procedure to retrieve derived_from links"""

        query = self.__query_from_template ("derived_from", {
            "prefix":      item_type.capitalize(),
            "item_uri":    item_uri
        })

        query += rdf.sparql_suffix (order, order_direction, limit, None)

        return [d['derived_from'] for d in self.__run_query(query)]

    def custom_fields (self, name=None, value=None, default_value=None,
                       field_id=None, placeholder=None, max_length=None,
                       min_length=None, field_type=None, is_multiple=None,
                       is_mandatory=None, order="name", order_direction=None,
                       limit=10, item_uri=None, item_type="dataset"):
        """Procedure to get custom metadata of a dataset or a collection."""

        prefix = item_type.capitalize()

        filters = rdf.sparql_filter ("id",            field_id)
        filters += rdf.sparql_filter ("max_length",    max_length)
        filters += rdf.sparql_filter ("min_length",    min_length)
        filters += rdf.sparql_filter ("is_multiple",   is_multiple)
        filters += rdf.sparql_filter ("is_mandatory",  is_mandatory)
        filters += rdf.sparql_filter ("name",          name,          escape=True)
        filters += rdf.sparql_filter ("value",         value,         escape=True)
        filters += rdf.sparql_filter ("default_value", default_value, escape=True)
        filters += rdf.sparql_filter ("placeholder",   placeholder,   escape=True)
        filters += rdf.sparql_filter ("field_type",    field_type,    escape=True)

        query = self.__query_from_template ("custom_fields", {
            "item_uri":    item_uri,
            "item_type":   item_type,
            "prefix":      prefix,
            "filters":     filters
        })
        query += rdf.sparql_suffix (order, order_direction, limit, None)

        return self.__run_query(query)

    def previously_used_tags (self, search_for, order=None, order_direction=None, limit=10):
        """Procedure to get tags unrelated to their datasets."""
        filters = ""
        if search_for is not None:
            escaped = rdf.escape_string_value (search_for.upper())
            filters += f"FILTER (CONTAINS(UCASE(STR(?tag)), {escaped}))"

        query = self.__query_from_template ("search_tags", { "filters": filters })
        query += rdf.sparql_suffix (order, order_direction, limit, None)
        return self.__run_query (query)

    def tags (self, order=None, order_direction=None, limit=10,
              item_uri=None, account_uuid=None):
        """Procedure to get tags for a dataset or a collection."""

        query   = self.__query_from_template ("tags", {
            "account_uuid": account_uuid,
            "item_uri":    item_uri
        })

        # Order by insertion-order by default.
        if order is None and order_direction is None:
            order = "index"
            order_direction = "asc"

        query += rdf.sparql_suffix (order, order_direction, limit, None)
        return self.__run_query(query)

    def categories (self, title=None, order=None, order_direction=None,
                    limit=10, item_uri=None, account_uuid=None,
                    is_published=True):
        """Procedure to retrieve categories of a dataset or collection."""

        filters = rdf.sparql_filter ("title", title, escape=True)
        query   = self.__query_from_template ("categories", {
            "item_uri":     item_uri,
            "account_uuid": account_uuid,
            "is_published": is_published,
            "filters":      filters
        })
        query += rdf.sparql_suffix (order, order_direction, limit, None)

        return self.__run_query(query)

    def account_categories (self, account_uuid, title=None, order=None,
                            order_direction=None, limit=10):
        """Procedure to retrieve categories of a dataset."""

        filters = rdf.sparql_filter ("title", title, escape=True)
        query   = self.__query_from_template ("account_categories", {
            "account_uuid": account_uuid,
            "filters":      filters
        })
        query += rdf.sparql_suffix (order, order_direction, limit, None)

        return self.__run_query (query)

    def private_links (self, item_uri=None, account_uuid=None, id_string=None):
        """Procedure to get private links to a dataset or a collection."""

        query   = self.__query_from_template ("private_links", {
            "id_string":   id_string,
            "item_uri":    item_uri,
            "account_uuid": account_uuid,
        })

        return self.__run_query(query)

    def license_url_by_id (self, license_id):
        """Procedure to get a license URL by its ID."""

        if license_id is None:
            return None

        query = self.__query_from_template ("licenses", {
            "license_id": license_id
        })

        try:
            return self.__run_query (query, query, "licenses")[0]["url"]
        except (IndexError, KeyError):
            pass

        return None

    def licenses (self):
        """Procedure to get a list of allowed licenses."""

        query = self.__query_from_template ("licenses")
        return self.__run_query (query, query, "licenses")

    def latest_datasets_portal (self, page_size=30):
        """Procedure to get the latest datasets."""

        query = self.__query_from_template ("latest_datasets_portal", {
            "page_size":   page_size
        })

        return self.__run_query(query)

    def collections_from_dataset (self, dataset_container_uuid):
        """Procedure to get the collections a dataset is part of."""

        query = self.__query_from_template ("collections_from_dataset", {
            "dataset_container_uuid":  dataset_container_uuid
        })

        return self.__run_query(query)

    def collection_datasets (self, collection_uri, limit=None, offset=0):
        """Procedure to get the published datasets of a collection."""

        query = self.__query_from_template ("collection_datasets", {
            "collection":  collection_uri
        })
        #ordering is done in the query template as it depends on 2 parameters
        #which is not supported by rdf.sparql_suffix
        query += rdf.sparql_suffix (None, None, limit, offset)

        return self.__run_query(query)

    def contact_info_from_container (self, container_uuid):
        """Procedure to retrieve contact info from container ."""
        query   = self.__query_from_template ("contact_info_from_container", {
            "container_uuid": container_uuid
        })
        try:
            return self.__run_query(query)[0]
        except (TypeError, IndexError):
            self.log.error ("Retrieving contact info for container %s failed.",
                            container_uuid)
            return None

    ## ------------------------------------------------------------------------
    ## COLLECTIONS
    ## ------------------------------------------------------------------------

    def collection_versions (self, limit=1000, offset=0, order="version",
                             order_direction=None, collection_id=None,
                             container_uri=None):
        """Procedure to retrieve the versions of an collection."""

        filters  = rdf.sparql_filter ("collection_id", collection_id)
        filters += rdf.sparql_filter ("container_uri", container_uri, is_uri=True)

        query = self.__query_from_template ("collection_versions", {
            "filters":     filters
        })
        query += rdf.sparql_suffix (order, order_direction, limit, offset)
        return self.__run_query (query)

    ## This procedure exists because the 'datasets' procedure will only
    ## count datasets that are either public, or were published using the
    ## same account_uuid as the collection.
    ##
    ## So to get the actual count, this separate procedure exists.
    def collections_dataset_count (self, collection_uri):
        """Procedure to count the datasets in a collection."""

        if collection_uri is None:
            return 0

        query = self.__query_from_template ("collection_datasets_count", {
            "collection_uri":  collection_uri
        })
        results = self.__run_query (query)

        try:
            return results[0]["datasets"]
        except KeyError:
            return 0

    def collections (self, limit=10, offset=None, order=None, collection_uuid=None,
                     order_direction=None, institution=None, categories=None,
                     published_since=None, modified_since=None, group=None,
                     resource_doi=None, resource_id=None, doi=None, handle=None,
                     account_uuid=None, search_for=None, collection_id=None,
                     version=None, container_uuid=None, is_latest=False,
                     is_published=True, private_link_id_string=None, use_cache=True):
        """Procedure to retrieve collections."""

        filters  = rdf.sparql_filter ("container_uri",  rdf.uuid_to_uri (container_uuid, "container"), is_uri=True)
        filters += rdf.sparql_filter ("collection",     rdf.uuid_to_uri (collection_uuid, "collection"), is_uri=True)
        filters += rdf.sparql_filter ("institution_id", institution)
        filters += rdf.sparql_filter ("group_id",       group)
        filters += rdf.sparql_filter ("collection_id",  collection_id)
        filters += rdf.sparql_filter ("version",        version)
        filters += rdf.sparql_filter ("resource_doi",   resource_doi, escape=True)
        filters += rdf.sparql_filter ("resource_id",    resource_id,  escape=True)
        filters += rdf.sparql_filter ("doi",            doi,          escape=True)
        filters += rdf.sparql_filter ("handle",         handle,       escape=True)
        filters += rdf.sparql_filter ("private_link_id_string", private_link_id_string, escape=True)

        if categories is not None:
            filters += f"FILTER ((?category_id IN ({','.join(map(str, categories))})) || "
            filters += f"(?parent_category_id IN ({','.join(map(str, categories))})))\n"

        if search_for is not None:
            escaped = rdf.escape_string_value (search_for)
            filters += (f"FILTER (CONTAINS(STR(?title),          {escaped}) ||\n"
                        f"        CONTAINS(STR(?resource_title), {escaped}) ||\n"
                        f"        CONTAINS(STR(?description),    {escaped}) ||\n"
                        f"        CONTAINS(STR(?citation),       {escaped}))")

        if published_since is not None:
            published_since_safe = rdf.escape_datetime_value (published_since)
            filters += rdf.sparql_bound_filter ("published_date")
            filters += f"FILTER (?published_date > {published_since_safe})\n"

        if modified_since is not None:
            modified_since_safe = rdf.escape_datetime_value (modified_since)
            filters += rdf.sparql_bound_filter ("modified_date")
            filters += f"FILTER (?modified_date > {modified_since_safe})\n"

        query   = self.__query_from_template ("collections", {
            "account_uuid": account_uuid,
            "categories":   categories,
            "filters":      filters,
            "is_latest":    is_latest,
            "is_published": is_published,
            "private_link_id_string": private_link_id_string,

        })
        query += rdf.sparql_suffix (order, order_direction, limit, offset)

        if use_cache:
            cache_prefix = f"collections_{account_uuid}" if account_uuid is not None else "collections"
            return self.__run_query (query, query, cache_prefix)

        return self.__run_query (query)

    def collections_by_account (self, account_uuid=None, limit=100, offset=None,
                                order=None, order_direction=None):
        """Procedure to retrieve essential metadata of collections of an account."""

        query   = self.__query_from_template ("collections_by_account", {
            "account_uuid": account_uuid
        })
        query += rdf.sparql_suffix (order, order_direction, limit, offset)

        return self.__run_query(query)

    def fundings (self, title=None, order=None, order_direction=None,
                  limit=10, item_uri=None, account_uuid=None, search_for=None,
                  item_type="dataset", is_published=True):
        """Procedure to retrieve funding information."""

        filters = rdf.sparql_filter ("title", title, escape=True)
        if search_for is not None:
            escaped  = rdf.escape_string_value (search_for.lower())
            filters += (f"FILTER (CONTAINS(LCASE(?title),       {escaped}) ||\n"
                        f"        CONTAINS(LCASE(?grant_code),  {escaped}) ||\n"
                        f"        CONTAINS(LCASE(?funder_name), {escaped}) ||\n"
                        f"        CONTAINS(LCASE(?url),         {escaped}))")

        query   = self.__query_from_template ("funding", {
            "prefix":      item_type.capitalize(),
            "item_uri":    item_uri,
            "account_uuid": account_uuid,
            "is_published": is_published,
            "filters":     filters
        })

        if order_direction is None and order is None:
            order_direction = "asc"
            order = "order_index"

        query += rdf.sparql_suffix (order, order_direction, limit, None)
        return self.__run_query(query)

    def references (self, order=None, order_direction=None, limit=10,
                    item_uri=None, account_uuid=None):
        """Procedure to retrieve references."""

        query   = self.__query_from_template ("references", {
            "item_uri":       item_uri,
            "account_uuid":   account_uuid,
        })
        query += rdf.sparql_suffix (order, order_direction, limit, None)

        return self.__run_query(query)

    def collection_dataset_containers (self, collection_uri, limit=10):
        """Procedure to retrieve dataset containers in a collection."""

        query   = self.__query_from_template ("collection_dataset_containers", {
            "collection_uri":  collection_uri
        })
        query += rdf.sparql_suffix (None, None, limit)

        return self.__run_query(query)

    ## ------------------------------------------------------------------------
    ## INSERT METHODS
    ## ------------------------------------------------------------------------

    def record_uri (self, record_type, identifier_name, identifier):
        """
        Returns the URI for a record identified with IDENTIFIER_NAME and by
        IDENTIFIER or None if no such URI can be found.
        """
        if identifier is None:
            return None

        if isinstance(identifier, str):
            identifier = rdf.escape_string_value (identifier)

        try:
            query    = self.__query_from_template ("record_uri.sparql", {
                "record_type": record_type,
                "identifier_name": identifier_name,
                "identifier": identifier
            })
            results = self.__run_query (query)
            return results[0]["uri"]
        except (KeyError, IndexError):
            pass

        return None

    def container_uri (self, graph, item_id, item_type, account_uuid):
        """Returns the URI of the container belonging to item with item_id."""

        prefix     = item_type.capitalize()
        item_class = f"{prefix}Container"
        uri        = None
        if conv.parses_to_int (item_id):
            uri = self.record_uri (item_class, f"{item_type}_id", item_id)
        else:
            uri = item_id

        if uri is None:
            uri = rdf.unique_node ("container")
            account_uri = URIRef(rdf.uuid_to_uri (account_uuid, "account"))
            graph.add ((uri, RDF.type,                   rdf.DJHT[item_class]))
            graph.add ((uri, rdf.DJHT["account"],        account_uri))

            ## The item_id is a left-over from the Figshare days.
            rdf.add (graph, uri, rdf.DJHT[f"{item_type}_id"], item_id, datatype=XSD.integer)

        return uri

    def insert_record_list (self, graph, uri, records, name, insert_procedure):
        """
        Adds an RDF list with indexes for RECORDS to the graph using
        INSERT_PROCEDURE.  The INSERT_PROCEDURE must take  a single item
        from RECORDS, and it must return the URI used as subject to describe
        the record.
        """
        if records:
            blank_node = rdf.blank_node ()
            graph.add ((uri, rdf.DJHT[name], blank_node))

            previous_blank_node = None
            for index, item in enumerate(records):
                if insert_procedure:
                    item = insert_procedure (**item)

                graph.add ((blank_node, rdf.DJHT["index"], Literal (index, datatype=XSD.integer)))
                if isinstance (item, URIRef):
                    graph.add ((blank_node, RDF.first,    item))
                else:
                    graph.add ((blank_node, RDF.first,    Literal (item, datatype=XSD.string)))

                if previous_blank_node is not None:
                    graph.add ((previous_blank_node, RDF.rest, blank_node))
                    graph.add ((previous_blank_node, RDF.type, RDF.List))

                previous_blank_node = blank_node
                blank_node = rdf.blank_node ()

            del blank_node
            graph.add ((previous_blank_node, RDF.rest, RDF.nil))
            graph.add ((previous_blank_node, RDF.type, RDF.List))

        return True

    def insert_item_list (self, graph, uri, items, items_name):
        """Adds an RDF list with indexes for ITEMS to GRAPH."""
        return self.insert_record_list (graph, uri, items, items_name, None)

    def wrap_in_blank_node (self, item, item_type="dataset", index=None):
        """Returns the blank node URI for the rdf:List node for a dataset."""

        rdf_store  = Graph ()
        blank_node = rdf.blank_node ()

        item_uri = item if isinstance (item, URIRef) else rdf.uuid_to_uri (item, item_type)

        rdf.add (rdf_store, blank_node, RDF.type, RDF.List, "url")
        rdf.add (rdf_store, blank_node, RDF.first, URIRef(item_uri), "url")
        rdf.add (rdf_store, blank_node, RDF.rest, RDF.nil, "url")
        if index is not None:
            rdf.add (rdf_store, blank_node, rdf.DJHT["index"], index, XSD.integer)

        if self.add_triples_from_graph (rdf_store):
            return blank_node

        return None

    def update_dataset_git_uuid (self, dataset_uuid, account_uuid):
        """Procedure to update the Git UUID of a draft dataset."""

        new_git_uuid = str(uuid.uuid4())
        query = self.__query_from_template ("update_git_uuid", {
            "dataset_uuid": dataset_uuid,
            "git_uuid":     rdf.escape_string_value (new_git_uuid)
        })

        self.cache.invalidate_by_prefix (f"datasets_{account_uuid}")
        self.cache.invalidate_by_prefix ("datasets")

        if self.__run_logged_query (query):
            return True, new_git_uuid

        return False, None

    def insert_dataset (self,
                        title,
                        account_uuid,
                        container_uuid=None,
                        description=None,
                        defined_type=None,
                        defined_type_name=None,
                        derived_from=None,
                        funding=None,
                        license_url=None,
                        language=None,
                        doi=None,
                        handle=None,
                        resource_doi=None,
                        resource_title=None,
                        publisher=None,
                        publisher_publication=None,
                        submission=None,
                        posted=None,
                        revision=None,
                        group_id=None,
                        funding_list=None,
                        tags=None,
                        references=None,
                        categories=None,
                        authors=None,
                        custom_fields=None,
                        private_links=None,
                        files=None,
                        embargo_type=None,
                        embargo_until_date=None,
                        embargo_title=None,
                        embargo_reason=None,
                        eula=None,
                        data_link=None,
                        thumb=None,
                        thumb_origin=None,
                        is_public=0,
                        is_active=1,
                        is_latest=0,
                        is_editable=1,
                        git_uuid=None,
                        version=None):
        """Procedure to insert a dataset to the state graph."""

        funding_list    = [] if funding_list    is None else funding_list
        tags            = [] if tags            is None else tags
        references      = [] if references      is None else references
        categories      = [] if categories      is None else categories
        authors         = [] if authors         is None else authors
        custom_fields   = [] if custom_fields   is None else custom_fields
        private_links   = [] if private_links   is None else private_links
        files           = [] if files           is None else files

        graph           = Graph()
        uri             = rdf.unique_node ("dataset")
        container_uri   = None
        if container_uuid is not None:
            container_uri   = URIRef(rdf.uuid_to_uri (container_uuid, "container"))

        container       = self.container_uri (graph, container_uri, "dataset", account_uuid)
        account_uri     = URIRef(rdf.uuid_to_uri (account_uuid, "account"))

        ## TIMELINE
        ## --------------------------------------------------------------------
        self.insert_timeline (
            graph                 = graph,
            item_uri              = uri,
            revision              = revision,
            publisher_publication = publisher_publication,
            posted                = posted,
            submission            = submission
        )

        authors       = rdf.uris_from_records (authors, "author", "uuid")
        categories    = rdf.uris_from_records (categories, "category", "uuid")
        tags          = list(map(lambda tag: tag["tag"], tags))
        references    = list(map(lambda reference: reference["url"], references))
        files         = rdf.uris_from_records (files, "file", "uuid")
        funding_list  = rdf.uris_from_records (funding_list, "funding", "uuid")
        private_links = rdf.uris_from_records (private_links, "private_link", "uuid")

        self.insert_item_list (graph, uri, authors, "authors")
        self.insert_item_list (graph, uri, categories, "categories")
        self.insert_item_list (graph, uri, references, "references")
        self.insert_item_list (graph, uri, tags, "tags")
        self.insert_item_list (graph, uri, files, "files")
        self.insert_item_list (graph, uri, funding_list, "funding_list")
        self.insert_item_list (graph, uri, private_links, "private_links")

        ## CUSTOM FIELDS
        ## --------------------------------------------------------------------
        for field in custom_fields:
            self.insert_custom_field_value (
                name     = conv.value_or_none (field, "name"),
                value    = conv.value_or_none (field, "value"),
                item_uri = uri,
                graph    = graph)

        ## TOPLEVEL FIELDS
        ## --------------------------------------------------------------------

        graph.add ((uri, RDF.type,                      rdf.DJHT["Dataset"]))
        graph.add ((uri, rdf.DJHT["title"],              Literal(title, datatype=XSD.string)))
        graph.add ((uri, rdf.DJHT["container"],          container))

        rdf.add (graph, uri, rdf.DJHT["description"],    description,    XSD.string)
        rdf.add (graph, uri, rdf.DJHT["defined_type"],   defined_type)
        rdf.add (graph, uri, rdf.DJHT["defined_type_name"], defined_type_name, XSD.string)
        rdf.add (graph, uri, rdf.DJHT["funding"],        funding,        XSD.string)
        rdf.add (graph, uri, rdf.DJHT["license"],        license_url,    "url")
        rdf.add (graph, uri, rdf.DJHT["language"],       language,       XSD.string)
        rdf.add (graph, uri, rdf.DJHT["doi"],            doi,            XSD.string)
        rdf.add (graph, uri, rdf.DJHT["handle"],         handle,         XSD.string)
        rdf.add (graph, uri, rdf.DJHT["resource_doi"],   resource_doi,   XSD.string)
        rdf.add (graph, uri, rdf.DJHT["resource_title"], resource_title, XSD.string)
        rdf.add (graph, uri, rdf.DJHT["group_id"],       group_id)
        rdf.add (graph, uri, rdf.DJHT["publisher"],      publisher,      XSD.string)
        rdf.add (graph, uri, rdf.DJHT["derived_from"],   derived_from,   XSD.string)
        rdf.add (graph, uri, rdf.DJHT["data_link"],      data_link,      XSD.string)
        rdf.add (graph, uri, rdf.DJHT["thumb"],          thumb,          XSD.string)
        rdf.add (graph, uri, rdf.DJHT["thumb_origin"],   thumb_origin,   XSD.string)

        current_time = datetime.strftime (datetime.now(), "%Y-%m-%dT%H:%M:%SZ")
        rdf.add (graph, uri, rdf.DJHT["created_date"],   current_time, XSD.dateTime)
        rdf.add (graph, uri, rdf.DJHT["modified_date"],  current_time, XSD.dateTime)
        rdf.add (graph, uri, rdf.DJHT["is_public"],      is_public)
        rdf.add (graph, uri, rdf.DJHT["is_active"],      is_active)
        rdf.add (graph, uri, rdf.DJHT["is_latest"],      is_latest)
        rdf.add (graph, uri, rdf.DJHT["is_editable"],    is_editable)
        rdf.add (graph, uri, rdf.DJHT["version"],        version)

        rdf.add (graph, uri, rdf.DJHT["embargo_type"], embargo_type, XSD.string)
        rdf.add (graph, uri, rdf.DJHT["embargo_until_date"], embargo_until_date, XSD.date)
        rdf.add (graph, uri, rdf.DJHT["embargo_title"], embargo_title, XSD.string)
        rdf.add (graph, uri, rdf.DJHT["embargo_reason"], embargo_reason, XSD.string)
        rdf.add (graph, uri, rdf.DJHT["eula"],           eula, XSD.string)

        # Reserve a UUID for a Git repository.
        if git_uuid is None:
            git_uuid = str(uuid.uuid4())

        rdf.add (graph, uri, rdf.DJHT["git_uuid"], git_uuid, XSD.string)

        # Add the dataset to its container.
        graph.add ((container, rdf.DJHT["draft"],       uri))
        graph.add ((container, rdf.DJHT["account"],     account_uri))

        self.cache.invalidate_by_prefix ("datasets")

        if self.add_triples_from_graph (graph):
            container_uuid = rdf.uri_to_uuid (container)
            self.log.info ("Inserted dataset %s", container_uuid)
            self.cache.invalidate_by_prefix (f"datasets_{account_uuid}")
            return container_uuid, rdf.uri_to_uuid (uri)

        return None, None

    def insert_quota_request (self, account_uuid, requested_size, reason):
        """Procedure to create a quota request."""

        if account_uuid is None or requested_size is None:
            return None

        graph        = Graph()
        uri          = rdf.unique_node ("quota-request")
        account_uri  = rdf.uuid_to_uri (account_uuid, "account")
        current_time = datetime.strftime (datetime.now(), "%Y-%m-%dT%H:%M:%S")

        graph.add ((uri, RDF.type,      rdf.DJHT["QuotaRequest"]))
        rdf.add (graph, uri, rdf.DJHT["account"], account_uri, "uri")
        rdf.add (graph, uri, rdf.DJHT["requested_size"], requested_size, XSD.integer)
        rdf.add (graph, uri, rdf.DJHT["reason"], reason, XSD.string)
        rdf.add (graph, uri, rdf.DJHT["created_date"], current_time, XSD.dateTime)
        rdf.add (graph, uri, rdf.DJHT["status"], rdf.DJHT["QuotaRequestUnresolved"], "uri")

        if self.add_triples_from_graph (graph):
            return rdf.uri_to_uuid (uri)

        return None

    def update_quota_request (self, quota_request_uuid, requested_size=None,
                              reason=None, status=None):
        """Procedure to update a quota request."""

        status_uri = None
        if status is not None:
            status_uri = rdf.DJHT[f"QuotaRequest{status.capitalize()}"]

        query = self.__query_from_template ("update_quota_request", {
            "quota_request_uuid": quota_request_uuid,
            "requested_size": requested_size,
            "reason": reason,
            "status": None if status_uri is None else rdf.urify_value (status_uri),
            "assign_to_account": status == "approved"
        })

        self.cache.invalidate_by_prefix ("accounts")
        return self.__run_logged_query (query)

    def quota_requests (self, status=None):
        """Procedure to return a list of quota requests."""

        status_uri = None
        if status is not None:
            status_uri = rdf.urify_value (rdf.DJHT[f"QuotaRequest{status.capitalize()}"])

        query = self.__query_from_template ("quota_requests", { "status": status_uri })
        return self.__run_query (query)

    def update_account (self, account_uuid, active=None, email=None, job_title=None,
                        first_name=None, last_name=None, institution_user_id=None,
                        institution_id=None,
                        maximum_file_size=None, modified_date=None, created_date=None,
                        location=None, biography=None, categories=None, twitter=None,
                        linkedin=None, website=None, profile_image=None):
        """Procedure to update account settings."""

        if modified_date is None:
            modified_date = datetime.strftime (datetime.now(), "%Y-%m-%dT%H:%M:%S")

        full_name = None
        if first_name is not None and last_name is not None:
            full_name = f"{first_name} {last_name}"

        query        = self.__query_from_template ("update_account", {
            "account_uuid":          account_uuid,
            "is_active":             active,
            "job_title":             rdf.escape_string_value (job_title),
            "email":                 rdf.escape_string_value (email),
            "first_name":            rdf.escape_string_value (first_name),
            "last_name":             rdf.escape_string_value (last_name),
            "full_name":             rdf.escape_string_value (full_name),
            "location":              rdf.escape_string_value (location),
            "twitter":               rdf.escape_string_value (twitter),
            "linkedin":              rdf.escape_string_value (linkedin),
            "website":               rdf.escape_string_value (website),
            "biography":             rdf.escape_string_value (biography),
            "institution_user_id":   institution_user_id,
            "institution_id":        institution_id,
            "maximum_file_size":     maximum_file_size,
            "profile_image":         profile_image,
            "modified_date":         modified_date,
            "created_date":          created_date
        })

        self.cache.invalidate_by_prefix ("accounts")

        results = self.__run_logged_query (query)
        if results and categories:

            if categories:
                graph = Graph()
                items = rdf.uris_from_records (categories, "category")
                self.delete_account_property (account_uuid, "categories")
                self.insert_item_list (graph,
                                       URIRef(rdf.uuid_to_uri (account_uuid, "account")),
                                       items,
                                       "categories")

                if not self.add_triples_from_graph (graph):
                    self.log.error ("Updating categories for account %s failed.",
                                    account_uuid)
                    return None

        return results

    def update_orcid_for_account (self, account_uuid, orcid):
        """Procedure to change the ORCID in the author record associated with an account."""

        query = self.__query_from_template ("update_orcid_for_account", {
            "account_uuid":  account_uuid,
            "orcid":         self.__normalize_orcid (orcid),
        })

        return self.__run_logged_query (query)

    def update_item_list (self, item_uuid, account_uuid, items, predicate):
        """Procedure to modify a list property of a container item."""
        try:
            graph   = Graph()
            item = self.container_items (item_uuid      = item_uuid,
                                         is_published   = None,
                                         is_latest      = None,
                                         account_uuid   = account_uuid)[0]

            self.delete_associations (item_uuid, account_uuid, predicate)
            if items:
                self.insert_item_list (graph,
                                       URIRef(item["uri"]),
                                       items,
                                       predicate)

                if not self.add_triples_from_graph (graph):
                    self.log.error ("%s insert query failed for %s",
                                    predicate, item_uuid)
                    return False

            return True

        except IndexError:
            self.log.error ("Could not insert %s items for %s",
                            predicate, item_uuid)

        return False

    def insert_author (self, author_id=None, is_active=None, first_name=None,
                       last_name=None, full_name=None, institution_id=None,
                       job_title=None, is_public=None, url_name=None,
                       orcid_id=None, email=None, group_id=None,
                       author_uuid=None, created_by=None, account_uuid=None):
        """Procedure to add an author to the state graph."""

        if author_uuid is not None:
            return author_uuid

        graph      = Graph()
        author_uri = rdf.unique_node ("author")

        graph.add ((author_uri, RDF.type,      rdf.DJHT["Author"]))

        orcid_id = self.__normalize_orcid (orcid_id)
        rdf.add (graph, author_uri, rdf.DJHT["id"],             author_id)
        rdf.add (graph, author_uri, rdf.DJHT["institution_id"], institution_id)
        rdf.add (graph, author_uri, rdf.DJHT["group_id"],       group_id)
        rdf.add (graph, author_uri, rdf.DJHT["is_active"],      is_active)
        rdf.add (graph, author_uri, rdf.DJHT["is_public"],      is_public)
        rdf.add (graph, author_uri, rdf.DJHT["first_name"],     first_name,     XSD.string)
        rdf.add (graph, author_uri, rdf.DJHT["last_name"],      last_name,      XSD.string)
        rdf.add (graph, author_uri, rdf.DJHT["full_name"],      full_name,      XSD.string)
        rdf.add (graph, author_uri, rdf.DJHT["job_title"],      job_title,      XSD.string)
        rdf.add (graph, author_uri, rdf.DJHT["url_name"],       url_name,       XSD.string)
        rdf.add (graph, author_uri, rdf.DJHT["orcid_id"],       orcid_id,       XSD.string)
        rdf.add (graph, author_uri, rdf.DJHT["email"],          email,          XSD.string)
        rdf.add (graph, author_uri, rdf.DJHT["created_by"],     rdf.uuid_to_uri (created_by, "account"), "uri")
        if account_uuid is not None:
            account_uri = URIRef(rdf.uuid_to_uri(account_uuid, "account"))
            rdf.add (graph, author_uri, rdf.DJHT["account"], account_uri, "uri")

        if self.add_triples_from_graph (graph):
            return rdf.uri_to_uuid (author_uri)

        return None

    def insert_account (self, email=None, first_name=None, last_name=None,
                        common_name=None, location=None, biography=None):
        """Procedure to create an account."""

        graph       = Graph()
        account_uri = rdf.unique_node ("account")

        graph.add ((account_uri, RDF.type,      rdf.DJHT["Account"]))

        domain = None
        if email is not None:
            domain = email.partition("@")[2]

        rdf.add (graph, account_uri, rdf.DJHT["active"],     1)
        rdf.add (graph, account_uri, rdf.DJHT["first_name"], first_name, XSD.string)
        rdf.add (graph, account_uri, rdf.DJHT["last_name"],  last_name,  XSD.string)
        rdf.add (graph, account_uri, rdf.DJHT["full_name"],  common_name, XSD.string)
        rdf.add (graph, account_uri, rdf.DJHT["email"],      email,      XSD.string)
        rdf.add (graph, account_uri, rdf.DJHT["domain"],     domain,     XSD.string)
        rdf.add (graph, account_uri, rdf.DJHT["location"],   location,   XSD.string)
        rdf.add (graph, account_uri, rdf.DJHT["biography"],  biography,  XSD.string)

        # Legacy properties.
        rdf.add (graph, account_uri, rdf.DJHT["institution_id"], 898)
        rdf.add (graph, account_uri, rdf.DJHT["url_name"],       "_", XSD.string)

        if self.add_triples_from_graph (graph):
            self.cache.invalidate_by_prefix ("accounts")
            return rdf.uri_to_uuid (account_uri)

        return None

    def insert_timeline (self, graph, item_uri=None, revision=None, posted=None,
                         submission=None, publisher_publication=None):
        """Procedure to add a timeline to the state graph."""

        rdf.add (graph, item_uri, rdf.DJHT["revision_date"],          revision,     XSD.dateTime)
        rdf.add (graph, item_uri, rdf.DJHT["posted_date"],            posted,       XSD.dateTime)
        rdf.add (graph, item_uri, rdf.DJHT["publisher_publication_date"], publisher_publication, XSD.dateTime)
        rdf.add (graph, item_uri, rdf.DJHT["submission_date"],        submission,   XSD.dateTime)

    def delete_associations (self, item_uuid, account_uuid, predicate):
        """Procedure to delete the list of PREDICATE of a dataset or collection."""

        query = self.__query_from_template ("delete_associations", {
            "item_uuid":     item_uuid,
            "predicate":     predicate,
            "account_uuid":  account_uuid,
        })

        return self.__run_logged_query (query)

    def delete_account_property (self, account_uuid, predicate):
        """Procedure to delete the PREDICATE of an account."""

        query = self.__query_from_template ("delete_account_property", {
            "predicate":     predicate,
            "account_uuid":  account_uuid,
        })

        self.cache.invalidate_by_prefix ("accounts")
        return self.__run_logged_query (query)

    def delete_item_categories (self, item_id, account_uuid, category_id=None,
                                item_type="dataset"):
        """Procedure to delete the categories of a dataset or collection."""

        prefix = item_type.capitalize()
        query = self.__query_from_template ("delete_item_categories", {
            "item_id":     item_id,
            "item_type":   item_type,
            "prefix":      prefix,
            "account_uuid": account_uuid,
            "category_id": category_id
        })

        return self.__run_logged_query (query)

    def delete_dataset_categories (self, dataset_id, account_uuid, category_id=None):
        """Procedure to delete the categories related to a dataset."""
        return self.delete_item_categories (dataset_id, account_uuid, category_id, "dataset")

    def insert_funding (self, title=None, grant_code=None, funder_name=None,
                        account_uuid=None, url=None, funding_id=None):
        """Procedure to add an funding to the state graph."""

        graph       = Graph()
        funding_uri = rdf.unique_node ("funding")

        graph.add ((funding_uri, RDF.type,                   rdf.DJHT["Funding"]))

        account_uri = None
        is_user_defined = False
        if account_uuid:
            account_uri = URIRef(rdf.uuid_to_uri (account_uuid, "account"))
            is_user_defined = True

        rdf.add (graph, funding_uri, rdf.DJHT["id"],              funding_id)
        rdf.add (graph, funding_uri, rdf.DJHT["title"],           title,           XSD.string)
        rdf.add (graph, funding_uri, rdf.DJHT["grant_code"],      grant_code,      XSD.string)
        rdf.add (graph, funding_uri, rdf.DJHT["funder_name"],     funder_name,     XSD.string)
        rdf.add (graph, funding_uri, rdf.DJHT["is_user_defined"], is_user_defined)
        rdf.add (graph, funding_uri, rdf.DJHT["url"],             url,             XSD.string)
        rdf.add (graph, funding_uri, rdf.DJHT["created_by"],      account_uri,     "uri")

        if self.add_triples_from_graph (graph):
            return rdf.uri_to_uuid (funding_uri)

        return None

    def append_to_list (self, node_to_be_appended_to, node_to_append):
        """Procedure to append a blank node to an existing list."""

        query = self.__query_from_template ("append_to_list", {
            "last_blank_node":   node_to_be_appended_to,
            "append_blank_node": node_to_append
        })

        return self.__run_logged_query (query)

    def delete_item_from_list (self, subject, predicate, rdf_first_value, value_type="uri"):
        """
        Removes node from list where RDF_FIRST_VALUE is the rdf:first property
        in the list pointed to by SUBJECT and PREDICATE.
        """

        first = None
        if value_type != "uri":
            first = rdf.escape_value (rdf_first_value, value_type)
        else:
            first = URIRef(rdf_first_value).n3()

        query = self.__query_from_template ("delete_item_from_list", {
            "subject":   subject,
            "predicate": rdf.DJHT[predicate].n3(),
            "first":     first
        })

        return self.__run_logged_query (query)

    def delete_items_all_from_list (self, subject, predicate):
        """
        Removes all nodes from list where RDF_FIRST_VALUE is the rdf:first property
        in the list pointed to by SUBJECT and PREDICATE.
        """

        query = self.__query_from_template ("delete_items_all_from_list", {
            "subject":   subject,
            "predicate": rdf.DJHT[predicate].n3(),
        })

        return self.__run_logged_query (query)

    def insert_file (self, file_id=None, name=None, size=None,
                     is_link_only=None, download_url=None, supplied_md5=None,
                     computed_md5=None, viewer_type=None, preview_state=None,
                     status=None, upload_url=None, upload_token=None,
                     dataset_uri=None, account_uuid=None, file_uuid=None):
        """Procedure to add an file to the state graph."""

        if file_uuid is not None:
            return file_uuid

        graph    = Graph()
        file_uri = rdf.unique_node ("file")

        graph.add ((file_uri, RDF.type,               rdf.DJHT["File"]))

        rdf.add (graph, file_uri, rdf.DJHT["id"],            file_id)
        rdf.add (graph, file_uri, rdf.DJHT["name"],          name,          XSD.string)
        rdf.add (graph, file_uri, rdf.DJHT["size"],          size)
        rdf.add (graph, file_uri, rdf.DJHT["is_link_only"],  is_link_only)
        rdf.add (graph, file_uri, rdf.DJHT["download_url"],  download_url,  XSD.string)
        rdf.add (graph, file_uri, rdf.DJHT["supplied_md5"],  supplied_md5,  XSD.string)
        rdf.add (graph, file_uri, rdf.DJHT["computed_md5"],  computed_md5,  XSD.string)
        rdf.add (graph, file_uri, rdf.DJHT["viewer_type"],   viewer_type,   XSD.string)
        rdf.add (graph, file_uri, rdf.DJHT["preview_state"], preview_state, XSD.string)
        rdf.add (graph, file_uri, rdf.DJHT["status"],        status,        XSD.string)
        rdf.add (graph, file_uri, rdf.DJHT["upload_url"],    upload_url,    XSD.string)
        rdf.add (graph, file_uri, rdf.DJHT["upload_token"],  upload_token,  XSD.string)

        current_time = datetime.strftime (datetime.now(), "%Y-%m-%dT%H:%M:%S")
        rdf.add (graph, file_uri, rdf.DJHT["created_date"],  current_time,  XSD.dateTime)
        rdf.add (graph, file_uri, rdf.DJHT["modified_date"], current_time,  XSD.dateTime)

        self.cache.invalidate_by_prefix ("datasets")
        if account_uuid:
            self.cache.invalidate_by_prefix (f"datasets_{account_uuid}")

        if self.add_triples_from_graph (graph):
            dataset_uuid   = rdf.uri_to_uuid (dataset_uri)
            existing_files = self.dataset_files (dataset_uri  = dataset_uri,
                                                 limit        = None,
                                                 account_uuid = account_uuid)

            # In the case where there are already files in the dataset,
            # we can append to the last blank node.
            if existing_files:
                last_file = existing_files[-1]
                new_index = conv.value_or (last_file, "order_index", 0) + 1
                if new_index < 1:
                    self.log.error ("Expected larger index for to-be-appended file.")

                last_node = conv.value_or_none (last_file, "originating_blank_node")
                new_node  = self.wrap_in_blank_node (file_uri, index=new_index)
                if new_node is None:
                    self.log.error ("Failed preparation to append %s.", file_uri)
                    return None

                self.cache.invalidate_by_prefix (f"{account_uuid}_storage")
                self.cache.invalidate_by_prefix (f"{dataset_uuid}_dataset_storage")

                if self.append_to_list (last_node, new_node):
                    return rdf.uri_to_uuid (file_uri)

                self.log.error ("Failed to append %s to the file list.", file_uri)
                return None

            files = [URIRef(file_uri)]
            if self.update_item_list (dataset_uuid, account_uuid, files, "files"):
                self.cache.invalidate_by_prefix (f"{account_uuid}_storage")
                self.cache.invalidate_by_prefix (f"{dataset_uuid}_dataset_storage")
                return rdf.uri_to_uuid (file_uri)

        return None

    def update_file (self, account_uuid, file_uuid, dataset_uuid, download_url=None,
                     computed_md5=None, viewer_type=None, preview_state=None,
                     file_size=None, status=None, filesystem_location=None,
                     is_incomplete=None, is_image=None):
        """Procedure to update file metadata."""

        modified_date = datetime.strftime (datetime.now(), "%Y-%m-%dT%H:%M:%SZ")
        query   = self.__query_from_template ("update_file", {
            "account_uuid":  account_uuid,
            "file_uuid":     file_uuid,
            "filesystem_location": filesystem_location,
            "download_url":  download_url,
            "computed_md5":  computed_md5,
            "viewer_type":   viewer_type,
            "preview_state": preview_state,
            "file_size":     file_size,
            "is_incomplete": is_incomplete,
            "is_image":      rdf.escape_boolean_value (is_image),
            "modified_date": modified_date,
            "status":        status
        })

        self.cache.invalidate_by_prefix (f"{account_uuid}_storage")
        self.cache.invalidate_by_prefix (f"{dataset_uuid}_dataset_storage")

        return self.__run_logged_query (query)

    def insert_log_entry (self, created_date, ip_address, item_uuid,
                          item_type="dataset", event_type="view"):
        """Procedure to register a djht:LogEntry."""
        if not isinstance (event_type, str):
            self.log.error ("Invalid event_type passed to 'insert_log_entry'.")
            return False

        graph       = Graph()
        entry_uri   = rdf.unique_node ("log-entry")
        type_suffix = f"LogEntry{event_type[0].upper()}{event_type[1:]}"
        item_uri    = rdf.uuid_to_uri (item_uuid, "container")

        graph.add ((entry_uri, RDF.type, rdf.DJHT["LogEntry"]))
        rdf.add (graph, entry_uri, rdf.DJHT["ip_address"], ip_address, XSD.string)
        rdf.add (graph, entry_uri, rdf.DJHT["created"], created_date, XSD.dateTime)
        rdf.add (graph, entry_uri, rdf.DJHT[f"{item_type}"], item_uri, "url")
        rdf.add (graph, entry_uri, rdf.DJHT["event_type"], rdf.DJHT[f"{type_suffix}"], "url")
        if self.add_triples_from_graph (graph):
            return True

        return False

    def item_collaborative_permissions (self, item_type, item_uuid,
                                        collaborator_account_uuid):
        """
        Returns the permissions of a collaborator with ACCOUNT_UUID for dataset
        or collection identified by ITEM_UUID.
        """

        query = self.__query_from_template ("item_collaborative_permissions", {
            "item_type": item_type,
            "item_uuid": item_uuid,
            "account_uuid": collaborator_account_uuid
        })

        rows = self.__run_query (query)
        if rows:
            return rows[0]

        return None

    def collaborators (self, dataset_uuid, account_uuid=None):
        "Get list of collaborators of a dataset"
        query = self.__query_from_template("collaborators", {
            "dataset_uuid": dataset_uuid,
            "account_uuid": account_uuid,
        })

        return self.__run_query(query)

    def insert_collaborator (self, dataset_uuid, collaborator_uuid,
                             account_uuid, metadata_read, metadata_edit,
                             data_read, data_edit, data_remove):
        """Procedure to add a collaborator to the state graph."""

        graph = Graph()
        collaborator_uri = rdf.unique_node("collaborator")

        graph.add ((collaborator_uri, RDF.type,      rdf.DJHT["Collaborator"]))
        rdf.add (graph, collaborator_uri, rdf.DJHT["metadata_read"], metadata_read, XSD.boolean)
        rdf.add (graph, collaborator_uri, rdf.DJHT["metadata_edit"], metadata_edit, XSD.boolean)
        rdf.add (graph, collaborator_uri, rdf.DJHT["data_read"],     data_read,     XSD.boolean)
        rdf.add (graph, collaborator_uri, rdf.DJHT["data_edit"],     data_edit,     XSD.boolean)
        rdf.add (graph, collaborator_uri, rdf.DJHT["data_remove"],   data_remove,   XSD.boolean)
        rdf.add (graph, collaborator_uri, rdf.DJHT["item"],          rdf.uuid_to_uri(dataset_uuid, "dataset"), "uri")
        rdf.add (graph, collaborator_uri, rdf.DJHT["account"],       rdf.uuid_to_uri(collaborator_uuid, "account"),  "uri")

        if self.add_triples_from_graph (graph):
            existing_collaborators = self.collaborators (dataset_uuid)
            if existing_collaborators:
                last_collaborator = existing_collaborators [-1]
                last_node = conv.value_or_none(last_collaborator, "originating_blank_node")
                new_index = conv.value_or (last_collaborator, "order_index", 0) +1
                new_node = self.wrap_in_blank_node(collaborator_uri, index=new_index)

                if self.append_to_list(last_node, new_node):
                    return rdf.uri_to_uuid (collaborator_uri)

                self.log.error ("failed to append %s to list of collaborators ", collaborator_uri)
                return None

            collaborators = [URIRef(collaborator_uri)]
            if self.update_item_list (dataset_uuid, account_uuid, collaborators, "collaborators"):
                collaborators = self.collaborators(dataset_uuid)
                for collaborator in collaborators:
                    self.cache.invalidate_by_prefix(f"datasets_{collaborator['account_uuid']}")

                return rdf.uri_to_uuid (collaborator_uri)

            self.log.error("failed to create collaborator list for %s ", collaborator_uri)
        return None

    def remove_collaborator (self, dataset_uuid, collaborator_uuid):
        "Procedure to remove a collaborator from the state graph."

        query = self.__query_from_template("delete_collaborator", {
            "dataset_uuid": dataset_uuid,
            "collaborator_uuid": collaborator_uuid
        })

        self.cache.invalidate_by_prefix(f"datasets_{dataset_uuid}")
        self.cache.invalidate_by_prefix("datasets")
        return self.__run_logged_query (query)

    def insert_private_link (self, item_uuid, account_uuid, whom=None,
                             purpose=None, item_type=None, anonymize=False,
                             read_only=True, id_string=None,
                             is_active=True, expires_date=None):
        """Procedure to add a private link to the state graph."""

        if item_uuid is None:
            return None

        if id_string is None:
            id_string = secrets.token_urlsafe()

        graph    = Graph()
        link_uri = rdf.unique_node ("private_link")

        graph.add ((link_uri, RDF.type,      rdf.DJHT["PrivateLink"]))

        rdf.add (graph, link_uri, rdf.DJHT["id"],           id_string,    XSD.string)
        rdf.add (graph, link_uri, rdf.DJHT["read_only"],    read_only)
        rdf.add (graph, link_uri, rdf.DJHT["is_active"],    is_active)
        rdf.add (graph, link_uri, rdf.DJHT["expires_date"], expires_date, XSD.dateTime)
        rdf.add (graph, link_uri, rdf.DJHT["whom"], whom,  XSD.string)
        rdf.add (graph, link_uri, rdf.DJHT["anonymize"], anonymize,  XSD.boolean)
        rdf.add (graph, link_uri, rdf.DJHT["purpose"], purpose,  XSD.string)

        if self.add_triples_from_graph (graph):
            item_uri    = rdf.uuid_to_uri (item_uuid, item_type)
            existing_links = self.private_links (item_uri=item_uri, account_uuid=account_uuid)
            existing_links = list(map (lambda item: URIRef(rdf.uuid_to_uri(item["uuid"], "private_link")),
                                               existing_links))

            new_links    = existing_links + [URIRef(link_uri)]

            item = None
            if item_type == "dataset":
                item      = self.datasets (dataset_uuid = item_uuid,
                                           account_uuid = account_uuid,
                                           # Ignoring is_published and is_latest
                                           # enabled both published and draft
                                           # datasets to be found via the
                                           # dataset -> container relationship.
                                           is_published = None,
                                           is_latest    = None,
                                           limit        = 1)[0]
            elif item_type == "collection":
                item      = self.collections (collection_uuid = item_uuid,
                                              account_uuid = account_uuid,
                                              # See above.
                                              is_published = None,
                                              is_latest    = None,
                                              limit        = 1)[0]

            if item is None:
                self.log.error ("Could not find item to insert a private link for.")
                return None

            if self.update_item_list (item["uuid"],
                                      account_uuid,
                                      new_links,
                                      "private_links"):
                return link_uri

        return None

    def insert_custom_field_value (self, name=None, value=None,
                                   item_uri=None, graph=None):
        """Procedure to add a custom field value to the state graph."""

        if name is None or value is None or item_uri is None or graph is None:
            self.log.error ("insert_custom_field_value was passed None parameters.")
            return False

        name = conv.custom_field_name (name)
        rdf.add (graph, item_uri, rdf.DJHT[name], value)
        return True

    def dataset_is_under_review (self, dataset_uuid):
        """
        Returns True when the dataset identified by DATASET_UUID is under
        review, False otherwise.
        """
        query = self.__query_from_template ("dataset_is_under_review", {
            "dataset_uuid": dataset_uuid
        })

        return self.__run_query (query)

    def delete_dataset_draft (self, container_uuid, dataset_uuid, account_uuid):
        """Remove the draft dataset from a container in the state graph."""

        collaborators = self.collaborators(dataset_uuid)
        query   = self.__query_from_template ("delete_dataset_draft", {
            "account_uuid":        account_uuid,
            "container_uri":       rdf.uuid_to_uri (container_uuid, "container")
        })

        result = self.__run_logged_query (query)
        self.cache.invalidate_by_prefix (f"{account_uuid}_storage")
        self.cache.invalidate_by_prefix (f"{dataset_uuid}_dataset_storage")
        self.cache.invalidate_by_prefix (f"datasets_{account_uuid}")

        for collaborator in collaborators:
            self.cache.invalidate_by_prefix(f"datasets_{collaborator['account_uuid']}")

        is_under_review = self.dataset_is_under_review (dataset_uuid)
        if is_under_review:
            self.cache.invalidate_by_prefix ("reviews")

        return result

    def publish_collection (self, container_uuid, account_uuid):
        """Procedure to publish a collection."""

        # Prevent caches from playing a role.
        self.cache.invalidate_by_prefix (f"collections_{account_uuid}")
        self.cache.invalidate_by_prefix ("collections")
        self.cache.invalidate_by_prefix ("repository_statistics")

        draft = None
        try:
            draft = self.collections (container_uuid = container_uuid,
                                      is_published = False,
                                      use_cache = False)[0]
        except IndexError:
            self.log.error ("Attempted to publish without a draft <container:%s>.",
                           container_uuid)
            return False

        new_version_number = 1
        latest             = None
        try:
            latest = self.collections (container_uuid = container_uuid,
                                       is_published   = True,
                                       is_latest      = True,
                                       use_cache      = False)[0]
            new_version_number = latest["version"] + 1
        except IndexError:
            self.log.error ("No latest version for <container:%s>.", container_uuid)

        collection_uuid = draft["uuid"]
        blank_node   = self.wrap_in_blank_node (collection_uuid, "collection")
        query        = self.__query_from_template ("publish_draft_collection", {
            "account_uuid":      account_uuid,
            "blank_node":        blank_node,
            "version":           new_version_number,
            "container_uuid":    container_uuid,
            "collection_uuid":   collection_uuid,
            "first_publication": not latest
        })

        return bool(self.__run_logged_query (query))

    def create_draft_from_published_collection (self, container_uuid):
        """Procedure to copy a published collection as draft in its container."""

        latest_uri = None
        try:
            latest = self.collections (container_uuid = container_uuid,
                                       is_published   = True,
                                       is_latest      = True,
                                       use_cache      = False,
                                       limit          = 1)[0]

            latest_uri      = latest["uri"]
        except (IndexError, TypeError):
            return None

        ## Derive the new draft from the published version.
        draft_authors       = self.authors(item_uri=latest_uri, item_type="collection", limit=None)
        draft_tags          = self.tags(item_uri=latest_uri, limit=None)
        draft_categories    = self.categories(item_uri=latest_uri, limit=None)
        draft_references    = self.references(item_uri=latest_uri, limit=None)
        draft_derived_from  = self.derived_from(item_uri=latest_uri, item_type="collection", limit=None)
        draft_fundings      = self.fundings(item_uri=latest_uri, item_type="collection", limit=None)
        draft_custom_fields = self.custom_fields (item_uri=latest_uri, item_type="collection")
        draft_datasets      = self.collection_dataset_containers(collection_uri=latest_uri, limit=None)
        draft_dataset_uris  = list({URIRef(container['container_uri']) for container in draft_datasets})

        if isinstance (draft_derived_from, list):
            try:
                draft_derived_from = draft_derived_from[0]
            except IndexError:
                draft_derived_from = None

        draft_funding_title = None
        if draft_fundings:
            draft_funding_title = draft_fundings[0]["title"]

        ## Insert collection
        # We don't insert the DOI because the draft will get a new DOI.
        # We also don't copy posted, published, and submission dates because
        # these are yet-to-be-determined.
        container_uuid, draft_uuid = self.insert_collection (
                title                 = conv.value_or_none (latest, "title"),
                account_uuid          = conv.value_or_none (latest, "account_uuid"),
                container_uuid        = container_uuid,
                description           = conv.value_or_none (latest, "description"),
                derived_from          = draft_derived_from,
                funding               = draft_funding_title,
                language              = conv.value_or_none (latest, "language"),
                resource_doi          = conv.value_or_none (latest, "resource_doi"),
                resource_title        = conv.value_or_none (latest, "resource_title"),
                revision              = conv.value_or_none (latest, "timeline_revision"),
                group_id              = conv.value_or_none (latest, "group_id"),
                publisher             = conv.value_or_none (latest, "publisher"),
                funding_list          = draft_fundings,
                tags                  = draft_tags,
                references            = draft_references,
                categories            = draft_categories,
                authors               = draft_authors,
                custom_fields         = draft_custom_fields,
                datasets              = draft_dataset_uris,
                private_links         = None,
                is_public             = 0,
                is_active             = 1,
                is_latest             = 0,
                is_editable           = 1,
                version               = None)

        graph         = Graph()
        container_uri = URIRef(rdf.uuid_to_uri (container_uuid, "container"))
        draft_uri     = URIRef(rdf.uuid_to_uri (draft_uuid, "collection"))
        rdf.add (graph, container_uri, rdf.DJHT["draft"], draft_uri, "uri")

        if self.add_triples_from_graph (graph):
            return draft_uuid

        return None

    def publish_dataset (self, container_uuid, account_uuid):
        """Procedure to publish a draft dataset."""

        # Prevent caches from playing a role.
        self.cache.invalidate_by_prefix (f"datasets_{account_uuid}")
        self.cache.invalidate_by_prefix ("datasets")

        draft = None
        try:
            draft = self.datasets (container_uuid = container_uuid,
                                   is_published   = False,
                                   use_cache      = False)[0]
        except IndexError:
            self.log.error ("Attempted to publish without a draft <container:%s>.",
                           container_uuid)
            return False

        new_version_number = 1
        latest             = None
        try:
            latest = self.datasets (container_uuid = container_uuid,
                                    is_published   = True,
                                    is_latest      = True,
                                    use_cache      = False)[0]
            new_version_number = latest["version"] + 1
        except IndexError:
            self.log.error ("No latest version for <container:%s>.", container_uuid)

        dataset_uuid = draft["uuid"]
        blank_node   = self.wrap_in_blank_node (dataset_uuid, "dataset")
        query        = self.__query_from_template ("publish_draft_dataset", {
            "blank_node":        blank_node,
            "version":           new_version_number,
            "container_uuid":    container_uuid,
            "dataset_uuid":      dataset_uuid,
            "first_publication": not latest
        })

        if self.__run_logged_query (query):
            self.cache.invalidate_by_prefix ("repository_statistics")
            self.cache.invalidate_by_prefix ("reviews")
            self.cache.invalidate_by_prefix (f"datasets_{account_uuid}")
            return True

        return False

    def decline_dataset (self, container_uuid, account_uuid):
        """Procedure to decline a draft dataset."""

        # Prevent caches from playing a role.
        self.cache.invalidate_by_prefix (f"datasets_{account_uuid}")
        self.cache.invalidate_by_prefix ("datasets")

        try:
            self.datasets (container_uuid = container_uuid,
                           is_published   = False)[0]
        except IndexError:
            self.log.error ("Attempted to decline without a draft <container:%s>.",
                            container_uuid)
            return False

        query = self.__query_from_template ("decline_draft_dataset", {
            "container_uuid": container_uuid,
        })

        if self.__run_logged_query (query):
            self.cache.invalidate_by_prefix ("reviews")
            self.cache.invalidate_by_prefix (f"datasets_{account_uuid}")
            return True

        self.log.error ("Failed to decline dataset %s", container_uuid)
        return False

    def create_draft_from_published_dataset (self, container_uuid, account_uuid=None):
        """Procedure to copy a published dataset as draft in its container."""

        latest_uri = None
        try:
            latest = self.datasets (container_uuid = container_uuid,
                                    is_published   = True,
                                    is_latest      = True,
                                    use_cache      = False,
                                    limit          = 1)[0]

            latest_uri      = latest["uri"]
        except (IndexError, TypeError):
            return None

        ## Derive the new draft from the published version.
        draft_authors       = self.authors(item_uri=latest_uri, limit=None)
        draft_files         = self.dataset_files(dataset_uri=latest_uri, account_uuid=account_uuid, limit=None)
        draft_tags          = self.tags(item_uri=latest_uri, limit=None)
        draft_categories    = self.categories(item_uri=latest_uri, limit=None)
        draft_references    = self.references(item_uri=latest_uri, limit=None)
        draft_derived_from  = self.derived_from(item_uri=latest_uri, limit=None)
        draft_fundings      = self.fundings(item_uri=latest_uri, limit=None)
        draft_custom_fields = self.custom_fields (item_uri=latest_uri, item_type="dataset")

        if isinstance (draft_derived_from, list):
            try:
                draft_derived_from = draft_derived_from[0]
            except IndexError:
                draft_derived_from = None

        draft_funding_title = None
        if draft_fundings:
            draft_funding_title = draft_fundings[0]["title"]

        ## Insert dataset
        # We don't insert the DOI because the draft will get a new DOI.
        # We also don't copy posted, published, and submission dates because
        # these are yet-to-be-determined.
        container_uuid, draft_uuid = self.insert_dataset (
                title                 = conv.value_or_none (latest, "title"),
                account_uuid          = conv.value_or_none (latest, "account_uuid"),
                container_uuid        = container_uuid,
                description           = conv.value_or_none (latest, "description"),
                defined_type          = conv.value_or_none (latest, "defined_type"),
                defined_type_name     = conv.value_or_none (latest, "defined_type_name"),
                derived_from          = draft_derived_from,
                funding               = draft_funding_title,
                license_url           = conv.value_or_none (latest, "license_url"),
                language              = conv.value_or_none (latest, "language"),
                resource_doi          = conv.value_or_none (latest, "resource_doi"),
                resource_title        = conv.value_or_none (latest, "resource_title"),
                revision              = conv.value_or_none (latest, "timeline_revision"),
                group_id              = conv.value_or_none (latest, "group_id"),
                publisher             = conv.value_or_none (latest, "publisher"),
                data_link             = conv.value_or_none (latest, "data_link"),
                thumb                 = conv.value_or_none (latest, "thumb"),
                thumb_origin          = conv.value_or_none (latest, "thumb_origin"),
                funding_list          = draft_fundings,
                tags                  = draft_tags,
                references            = draft_references,
                categories            = draft_categories,
                authors               = draft_authors,
                custom_fields         = draft_custom_fields,
                private_links         = None,
                files                 = draft_files,
                embargo_type          = conv.value_or_none (latest, "embargo_type"),
                embargo_until_date    = conv.value_or_none (latest, "embargo_until_date"),
                embargo_title         = conv.value_or_none (latest, "embargo_title"),
                embargo_reason        = conv.value_or_none (latest, "embargo_reason"),
                eula                  = conv.value_or_none (latest, "eula"),
                is_public             = 0,
                is_active             = 1,
                is_latest             = 0,
                is_editable           = 1,
                version               = None)

        graph         = Graph()
        container_uri = URIRef(rdf.uuid_to_uri (container_uuid, "container"))
        draft_uri     = URIRef(rdf.uuid_to_uri (draft_uuid, "dataset"))
        rdf.add (graph, container_uri, rdf.DJHT["draft"], draft_uri, "uri")

        if self.add_triples_from_graph (graph):
            return draft_uuid

        return None

    def update_dataset (self, dataset_uuid, account_uuid, title=None,
                        description=None, resource_doi=None, doi=None,
                        resource_title=None, license_url=None, group_id=None,
                        time_coverage=None, publisher=None, language=None,
                        mimetype=None, contributors=None, license_remarks=None,
                        geolocation=None, longitude=None, latitude=None,
                        data_link=None, has_linked_file=None, derived_from=None,
                        same_as=None, organizations=None, categories=None,
                        defined_type=None, defined_type_name=None,
                        embargo_until_date=None, embargo_type=None,
                        embargo_title=None, embargo_reason=None, eula=None,
                        is_embargoed=False, is_restricted=False,
                        agreed_to_deposit_agreement=False, agreed_to_publish=False,
                        is_metadata_record=False, metadata_reason=None,
                        container_doi=None, is_first_online=False):
        """Procedure to overwrite parts of a dataset."""

        modified_date_str = datetime.strftime (datetime.now(), "%Y-%m-%dT%H:%M:%SZ")
        first_online_date_str = modified_date_str if is_first_online else None

        query   = self.__query_from_template ("update_dataset", {
            "account_uuid":    account_uuid,
            "dataset_uri":     rdf.uuid_to_uri (dataset_uuid, "dataset"),
            "contributors":    rdf.escape_string_value (contributors),
            "data_link":       rdf.escape_string_value (data_link),
            "defined_type":    defined_type,
            "defined_type_name": rdf.escape_string_value (defined_type_name),
            "derived_from":    rdf.escape_string_value (derived_from),
            "description":     rdf.escape_string_value (description),
            "doi":             rdf.escape_string_value (doi),
            "format":          rdf.escape_string_value (mimetype),
            "geolocation":     rdf.escape_string_value (geolocation),
            "has_linked_file": has_linked_file,
            "language":        rdf.escape_string_value (language),
            "latitude":        rdf.escape_string_value (latitude),
            "license_url":     license_url,
            "group_id":        group_id,
            "license_remarks": rdf.escape_string_value (license_remarks),
            "longitude":       rdf.escape_string_value (longitude),
            "modified_date":   modified_date_str,
            "organizations":   rdf.escape_string_value (organizations),
            "publisher":       rdf.escape_string_value (publisher),
            "resource_doi":    rdf.escape_string_value (resource_doi),
            "resource_title":  rdf.escape_string_value (resource_title),
            "same_as":         rdf.escape_string_value (same_as),
            "time_coverage":   rdf.escape_string_value (time_coverage),
            "title":           rdf.escape_string_value (title),
            "is_embargoed":    int(is_embargoed),
            "is_restricted":   int(is_restricted),
            "is_metadata_record": rdf.escape_boolean_value (is_metadata_record),
            "metadata_reason": rdf.escape_string_value (metadata_reason),
            "embargo_until_date": rdf.escape_date_value (embargo_until_date),
            "embargo_type":    rdf.escape_string_value (embargo_type),
            "embargo_title":   rdf.escape_string_value (embargo_title),
            "embargo_reason":  rdf.escape_string_value (embargo_reason),
            "eula":            rdf.escape_string_value (eula),
            "agreed_to_deposit_agreement":
                               rdf.escape_boolean_value (agreed_to_deposit_agreement),
            "agreed_to_publish": rdf.escape_boolean_value (agreed_to_publish),
            "container_doi":   rdf.escape_string_value (container_doi),
            "first_online_date": first_online_date_str
        })

        collaborators = self.collaborators(dataset_uuid)
        for collaborator in collaborators:
            self.cache.invalidate_by_prefix(f"datasets_{collaborator['account_uuid']}")

        self.cache.invalidate_by_prefix (f"datasets_{account_uuid}")
        self.cache.invalidate_by_prefix ("datasets")

        results = self.__run_logged_query (query)
        if results:
            items = []
            if isinstance (categories, list):
                items = rdf.uris_from_records (categories, "category")
                self.update_item_list (dataset_uuid, account_uuid, items, "categories")
        else:
            return False

        return True

    def delete_dataset_embargo (self, dataset_uri, account_uuid):
        """Procedure to lift the embargo on a dataset."""

        query   = self.__query_from_template ("delete_dataset_embargo", {
            "account_uuid": account_uuid,
            "dataset_uri":  dataset_uri
        })

        self.cache.invalidate_by_prefix (f"datasets_{account_uuid}")
        self.cache.invalidate_by_prefix ("datasets")

        return self.__run_logged_query (query)

    def delete_private_links (self, container_uuid, account_uuid, link_id):
        """Procedure to remove private links to a dataset."""

        query   = self.__query_from_template ("delete_private_links", {
            "account_uuid":   account_uuid,
            "container_uuid": container_uuid,
            "id_string":      link_id
        })

        self.cache.invalidate_by_prefix (f"datasets_{account_uuid}")
        self.cache.invalidate_by_prefix ("datasets")

        return self.__run_logged_query (query)

    def update_private_link (self, item_uri, account_uuid, link_id,
                             is_active=None, expires_date=None,
                             read_only=None):
        """Procedure to update a private link to a dataset."""

        query   = self.__query_from_template ("update_private_link", {
            "account_uuid": account_uuid,
            "item_uri":     item_uri,
            "id_string":    link_id,
            "is_active":    is_active,
            "expires_date": expires_date,
            "read_only":    read_only
        })

        self.cache.invalidate_by_prefix (f"datasets_{account_uuid}")
        self.cache.invalidate_by_prefix ("datasets")

        return self.__run_logged_query (query)

    def dataset_update_thumb (self, dataset_uuid, account_uuid, file_uuid,
                              extension, version=None):
        """Procedure to update the thumbnail of a dataset."""

        if file_uuid == "":
            file_uuid = None

        query = self.__query_from_template ("update_dataset_thumb", {
            "account_uuid": account_uuid,
            "dataset_uuid": dataset_uuid,
            "extension":    extension,
            "file_uuid":    file_uuid,
            "version":      version
        })

        self.cache.invalidate_by_prefix (f"datasets_{account_uuid}")
        self.cache.invalidate_by_prefix ("datasets")
        return self.__run_query(query)

    def dataset_update_doi_after_publishing (self, dataset_uuid, doi):
        """Procedure to update a DOI after it has been published."""

        query = self.__query_from_template ("update_doi_after_publishing", {
            "dataset_uuid": dataset_uuid,
            "doi": rdf.escape_string_value (doi)
        })
        return self.__run_logged_query (query)

    def insert_collection (self, title,
                           account_uuid,
                           collection_id=None,
                           container_uuid=None,
                           funding=None,
                           funding_list=None,
                           description=None,
                           derived_from=None,
                           datasets=None,
                           authors=None,
                           categories=None,
                           categories_by_source_id=None,
                           tags=None,
                           references=None,
                           custom_fields=None,
                           custom_fields_list=None,
                           doi=None,
                           handle=None,
                           url=None,
                           language=None,
                           resource_id=None,
                           resource_doi=None,
                           resource_link=None,
                           resource_title=None,
                           resource_version=None,
                           group_id=None,
                           publisher=None,
                           publisher_publication=None,
                           submission=None,
                           posted=None,
                           revision=None,
                           private_links=None,
                           is_public=0,
                           is_active=1,
                           is_latest=0,
                           is_editable=1,
                           version=None):
        """Procedure to insert a collection to the state graph."""

        funding_list            = [] if funding_list            is None else funding_list
        tags                    = [] if tags                    is None else tags
        references              = [] if references              is None else references
        categories              = [] if categories              is None else categories
        categories_by_source_id = [] if categories_by_source_id is None else categories_by_source_id
        authors                 = [] if authors                 is None else authors
        custom_fields           = [] if custom_fields           is None else custom_fields
        custom_fields_list      = [] if custom_fields_list      is None else custom_fields_list
        private_links           = [] if private_links           is None else private_links
        datasets                = [] if datasets                is None else datasets

        graph                   = Graph()
        uri                     = rdf.unique_node ("collection")
        container_uri           = None
        if container_uuid is not None:
            container_uri = URIRef(rdf.uuid_to_uri (container_uuid, "container"))

        container               = self.container_uri (graph, container_uri, "collection", account_uuid)
        account_uri             = URIRef(rdf.uuid_to_uri (account_uuid, "account"))

        ## TIMELINE
        ## --------------------------------------------------------------------
        self.insert_timeline (
            graph                 = graph,
            item_uri              = uri,
            revision              = revision,
            publisher_publication = publisher_publication,
            posted                = posted,
            submission            = submission
        )

        authors       = rdf.uris_from_records (authors, "author", "uuid")
        categories    = rdf.uris_from_records (categories, "category", "uuid")
        references    = list(map(lambda reference: reference["url"], references))
        tags          = list(map(lambda tag: tag["tag"], tags))
        funding_list  = rdf.uris_from_records (funding_list, "funding", "uuid")
        private_links = rdf.uris_from_records (private_links, "private_link", "uuid")

        self.insert_item_list (graph, uri, authors, "authors")
        self.insert_item_list (graph, uri, categories, "categories")
        self.insert_item_list (graph, uri, references, "references")
        self.insert_item_list (graph, uri, tags, "tags")
        self.insert_item_list (graph, uri, funding_list, "funding_list")
        self.insert_item_list (graph, uri, private_links, "private_links")
        self.insert_item_list (graph, uri, datasets, "datasets")

        ## DATASETS
        ## --------------------------------------------------------------------
        self.insert_item_list (graph, uri, datasets, "datasets")

        ## CUSTOM FIELDS
        ## --------------------------------------------------------------------
        for field in custom_fields:
            self.insert_custom_field_value (
                name     = conv.value_or_none (field, "name"),
                value    = conv.value_or_none (field, "value"),
                item_uri = uri,
                graph    = graph)

        ## TOPLEVEL FIELDS
        ## --------------------------------------------------------------------

        graph.add ((uri, RDF.type,         rdf.DJHT["Collection"]))
        graph.add ((uri, rdf.DJHT["title"], Literal(title, datatype=XSD.string)))
        graph.add ((uri, rdf.DJHT["container"], container))

        rdf.add (graph, uri, rdf.DJHT["collection_id"],  collection_id)
        rdf.add (graph, uri, rdf.DJHT["account"],        account_uri)
        rdf.add (graph, uri, rdf.DJHT["description"],    description,    XSD.string)
        rdf.add (graph, uri, rdf.DJHT["derived_from"],   derived_from,   XSD.string)
        rdf.add (graph, uri, rdf.DJHT["funding"],        funding,        XSD.string)
        rdf.add (graph, uri, rdf.DJHT["doi"],            doi,            XSD.string)
        rdf.add (graph, uri, rdf.DJHT["handle"],         handle,         XSD.string)
        rdf.add (graph, uri, rdf.DJHT["url"],            url,            XSD.string)
        rdf.add (graph, uri, rdf.DJHT["language"],       language,       XSD.string)
        rdf.add (graph, uri, rdf.DJHT["resource_id"],    resource_id,    XSD.string)
        rdf.add (graph, uri, rdf.DJHT["resource_doi"],   resource_doi,   XSD.string)
        rdf.add (graph, uri, rdf.DJHT["resource_link"],  resource_link,  XSD.string)
        rdf.add (graph, uri, rdf.DJHT["resource_title"], resource_title, XSD.string)
        rdf.add (graph, uri, rdf.DJHT["resource_version"], resource_version)
        rdf.add (graph, uri, rdf.DJHT["group_id"],       group_id)
        rdf.add (graph, uri, rdf.DJHT["publisher"],      publisher,      XSD.string)

        current_time = datetime.strftime (datetime.now(), "%Y-%m-%dT%H:%M:%S")
        rdf.add (graph, uri, rdf.DJHT["created_date"],   current_time, XSD.dateTime)
        rdf.add (graph, uri, rdf.DJHT["modified_date"],  current_time, XSD.dateTime)
        rdf.add (graph, uri, rdf.DJHT["is_public"],      is_public)
        rdf.add (graph, uri, rdf.DJHT["is_active"],      is_active)
        rdf.add (graph, uri, rdf.DJHT["is_latest"],      is_latest)
        rdf.add (graph, uri, rdf.DJHT["is_editable"],    is_editable)
        rdf.add (graph, uri, rdf.DJHT["version"],        version)

        # Add the collection to its container.
        graph.add ((container, rdf.DJHT["draft"],       uri))
        graph.add ((container, rdf.DJHT["account"],     account_uri))

        if self.add_triples_from_graph (graph):
            container_uuid = rdf.uri_to_uuid (container)
            self.log.info ("Inserted collection %s", container_uuid)
            self.cache.invalidate_by_prefix (f"collections_{account_uuid}")
            return container_uuid, rdf.uri_to_uuid (uri)

        return None, None

    def delete_collection_draft (self, container_uuid, account_uuid):
        """Procedure to remove a collection from the state graph."""

        query   = self.__query_from_template ("delete_collection_draft", {
            "account_uuid":   account_uuid,
            "container_uri":  rdf.uuid_to_uri (container_uuid, "container")
        })

        self.cache.invalidate_by_prefix (f"collections_{account_uuid}")
        self.cache.invalidate_by_prefix ("collections")

        return self.__run_logged_query (query)

    def update_collection (self, collection_uuid, account_uuid, title=None,
                           description=None, resource_doi=None, doi=None,
                           resource_title=None, group_id=None, datasets=None,
                           time_coverage=None, publisher=None, language=None,
                           contributors=None, geolocation=None, longitude=None,
                           latitude=None, organizations=None, categories=None,
                           container_doi=None, is_first_online=False):
        """Procedure to overwrite parts of a collection."""

        modified_date_str = datetime.strftime (datetime.now(), "%Y-%m-%dT%H:%M:%SZ")
        first_online_date_str = modified_date_str if is_first_online else None

        query   = self.__query_from_template ("update_collection", {
            "account_uuid":      account_uuid,
            "collection_uri":    rdf.uuid_to_uri (collection_uuid, "collection"),
            "contributors":      rdf.escape_string_value (contributors),
            "description":       rdf.escape_string_value (description),
            "doi":               rdf.escape_string_value (doi),
            "geolocation":       rdf.escape_string_value (geolocation),
            "language":          rdf.escape_string_value (language),
            "latitude":          rdf.escape_string_value (latitude),
            "group_id":          group_id,
            "longitude":         rdf.escape_string_value (longitude),
            "modified_date":     modified_date_str,
            "organizations":     rdf.escape_string_value (organizations),
            "publisher":         rdf.escape_string_value (publisher),
            "resource_doi":      rdf.escape_string_value (resource_doi),
            "resource_title":    rdf.escape_string_value (resource_title),
            "time_coverage":     rdf.escape_string_value (time_coverage),
            "title":             rdf.escape_string_value (title),
            "container_doi":     rdf.escape_string_value (container_doi),
            "first_online_date": first_online_date_str
        })

        self.cache.invalidate_by_prefix (f"{collection_uuid}_collection")
        self.cache.invalidate_by_prefix (f"collections_{account_uuid}")
        self.cache.invalidate_by_prefix ("collections")

        results = self.__run_logged_query (query)
        if results and categories:
            items = rdf.uris_from_records (categories, "category")
            self.update_item_list (collection_uuid, account_uuid, items, "categories")

        if results and datasets:
            items = rdf.uris_from_records (datasets, "dataset")
            self.update_item_list (collection_uuid, account_uuid, items, "datasets")

        return results

    def category_by_id (self, category_id):
        """Procedure to return category information by its identifier."""

        query = self.__query_from_template ("category_by_id", {
            "category_id": category_id
        })

        try:
            results = self.__run_query (query, query, "category")
            return results[0]
        except IndexError:
            return None

    def subcategories_for_category (self, category_uuid):
        """Procedure to return the subcategories for a category."""

        query = self.__query_from_template ("subcategories_by_category", {
            "category_uri": rdf.uuid_to_uri (category_uuid, "category")
        })

        return self.__run_query (query, query, "category")

    def root_categories (self):
        """Procedure to return the categories without a parent category."""

        query = self.__query_from_template ("root_categories", {
            "state_graph": self.state_graph
        })

        query += rdf.sparql_suffix ("title", "asc")
        return self.__run_query (query, query, "category")

    def categories_tree (self):
        """Procedure to return a tree of categories."""

        query   = self.__query_from_template ("categories_tree")
        results = self.__run_query (query, query, "categories_tree")
        roots   = list (filter (lambda category: conv.value_or (category, "parent_id", 0) == 0, results))
        for root in roots:
            # The iterable 'subcategories' is materialized by the call to 'sorted'.
            subcategories = filter (lambda category: conv.value_or_none (category, "parent_id") == root["id"], results)  # pylint: disable=cell-var-from-loop
            root["subcategories"] = sorted (subcategories, key = lambda field: field["title"])

        roots = sorted (roots, key = lambda field: field["title"])
        return roots

    def group (self, group_id=None, parent_id=None, name=None,
               association=None, limit=None, offset=None,
               order=None, order_direction=None, starts_with=False):
        """Procedure to return group information."""

        filters = ""
        filters += rdf.sparql_filter ("id", group_id)
        filters += rdf.sparql_filter ("parent_id", parent_id)

        if name is not None:
            if starts_with:
                escaped_name = rdf.escape_string_value (name)
                filters += f"FILTER (STRSTARTS(STR(?name), {escaped_name}))"
            else:
                filters += rdf.sparql_filter ("name", name, escape=True)

        filters += rdf.sparql_filter ("association", association, escape=True)

        query = self.__query_from_template ("group", {
            "filters":     filters
        })

        query += rdf.sparql_suffix (order, order_direction, limit, offset)

        return self.__run_query (query, query, "group")

    def group_by_name (self, group_name, startswith=False):
        """Procedure to return group information by its name."""

        query = self.__query_from_template ("group_by_name", {
            "startswith": startswith,
            "group_name": group_name
        })

        results = self.__run_query (query, query, "group")
        if startswith:
            return results
        try:
            return results[0]
        except IndexError:
            return None

    def account_storage_used (self, account_uuid):
        """Returns the number of bytes used by an account."""

        query = self.__query_from_template ("account_storage_used", {
            "account_uuid": account_uuid
        })

        files = self.__run_query (query, query, f"{account_uuid}_storage")
        try:
            number_of_bytes = 0
            for entry in files:
                number_of_bytes += int(float(entry["bytes"]))
            return number_of_bytes
        except (IndexError, KeyError):
            pass

        return 0

    def opendap_to_doi(self, startswith=None, endswith=None):
        """Procedure to return DOI corresponding to opendap catalog url"""

        filters = ""

        if startswith is not None:
            if isinstance(startswith, list):
                escaped_startswith = rdf.escape_string_value (startswith[0])
                filters += f"FILTER ((STRSTARTS(STR(?data_url), {escaped_startswith}))"
                for filter_item in startswith[1:]:
                    escaped_item = rdf.escape_string_value (filter_item)
                    filters += f" || (STRSTARTS(STR(?data_url), {escaped_item}))"
                filters += ")\n"
            elif isinstance(startswith, str):
                escaped_startswith = rdf.escape_string_value (startswith)
                filters += f"FILTER (STRSTARTS(STR(?data_url), {escaped_startswith}))\n"
            else:
                self.log.error ("startswith of type %s is not supported", type(startswith))

        if endswith is not None:
            escaped_endswith = rdf.escape_string_value (endswith)
            filters += f"FILTER (STRENDS(STR(?data_url), {escaped_endswith}))\n"

        query = self.__query_from_template ("opendap_to_doi", {
            "filters": filters
        })

        results = self.__run_query (query)
        return results

    ## ------------------------------------------------------------------------
    ## REVIEWS
    ## ------------------------------------------------------------------------

    def reviews (self, assigned_to=None, dataset_uri=None, status=None,
                 account_uuid=None, limit=10, order=None, order_direction=None,
                 offset=None, review_uuid=None):
        """Returns reviews within the scope of the procedure's parameters."""

        filters = rdf.sparql_filter ("dataset", dataset_uri, is_uri=True)

        query = self.__query_from_template ("reviews", {
            "account_uuid":   account_uuid,
            "assigned_to":    assigned_to,
            "review_uuid":    review_uuid,
            "status":         status.capitalize() if status is not None else status,
            "filters":        filters,
        })

        query += rdf.sparql_suffix (order, order_direction, limit, offset)
        return self.__run_query (query, query, "reviews")

    def insert_review (self, dataset_uri, request_date=None, assigned_to=None,
                       status=None, reminder_date=None):
        """Procedure to insert a review for a dataset."""

        graph           = Graph()
        uri             = rdf.unique_node ("review")

        if request_date is None:
            request_date = datetime.strftime (datetime.now(), "%Y-%m-%dT%H:%M:%SZ")

        if not isinstance (dataset_uri, URIRef):
            dataset_uri = URIRef(dataset_uri)

        graph.add ((uri, RDF.type,                      rdf.DJHT["Review"]))
        graph.add ((uri, rdf.DJHT["dataset"],            dataset_uri))

        status_uri = None
        if status is not None:
            status_uri = rdf.DJHT["Review" + status.capitalize()]

        if assigned_to is not None:
            assigned_to = rdf.uuid_to_uri (assigned_to, "account")

        rdf.add (graph, uri, rdf.DJHT["request_date"],   request_date,  XSD.dateTime)
        rdf.add (graph, uri, rdf.DJHT["reminder_date"],  reminder_date, XSD.dateTime)
        rdf.add (graph, uri, rdf.DJHT["assigned_to"],    assigned_to,   "uri")
        rdf.add (graph, uri, rdf.DJHT["status"],         status_uri,    "uri")
        rdf.add (graph, dataset_uri, rdf.DJHT["is_under_review"], True, XSD.boolean)

        if self.add_triples_from_graph (graph):
            self.cache.invalidate_by_prefix ("reviews")
            self.log.info ("Inserted review for dataset %s", dataset_uri)
            return uri

        return None

    def update_review (self, review_uri, dataset_uri=None, assigned_to=None,
                       status=None, reminder_date=None,
                       author_account_uuid=None):
        """Procedure to update a review."""

        query        = self.__query_from_template ("update_review", {
            "review_uri":            review_uri,
            "dataset_uri":           dataset_uri,
            "assigned_to":           assigned_to,
            "status":                status.capitalize() if status is not None else status,
            "reminder_date":         reminder_date
        })

        self.cache.invalidate_by_prefix (f"datasets_{author_account_uuid}")
        self.cache.invalidate_by_prefix ("reviews")

        return self.__run_logged_query (query)

    def account_uuid_by_orcid (self, orcid):
        """Returns the account ID belonging to an ORCID."""

        query = self.__query_from_template ("account_uuid_by_orcid", {
            "orcid": rdf.escape_string_value (orcid)
        })

        try:
            results = self.__run_query (query)
            return results[0]["uuid"]
        except (IndexError, KeyError):
            pass

        return None

    def account_quota (self, email, domain, account):
        """Return the account's quota in bytes."""

        account_quota = self.account_quotas.get (email)
        group_quota   = self.group_quotas.get (domain)

        if "quota" in account:
            return account["quota"]

        if account_quota:
            return account_quota

        if group_quota:
            return group_quota

        return self.default_quota

    def __account_with_privileges_and_quotas (self, account):
        """Returns an account record with privileges and quotas."""

        try:
            privileges = {}
            email = account["email"].lower()
            if email in self.privileges:
                privileges = self.privileges[email]

            domain     = conv.value_or (account, "domain", "")
            quota      = self.account_quota (email, domain, account)
            account    = { **account, **privileges, "quota": quota }
        except (TypeError, KeyError):
            pass

        return account

    def account_by_session_token (self, session_token, mfa_token=None):
        """Returns an account record or None."""

        if session_token is None:
            return None

        query = self.__query_from_template ("account_by_session_token", {
            "token":       rdf.escape_string_value (session_token),
            "mfa_token":   mfa_token
        })

        results = self.__run_query (query)
        if results:
            return self.__account_with_privileges_and_quotas (results[0])

        return None

    def __privileged_role_email_addresses (self, privilege):
        """Returns e-mail addresses of accounts with PRIVILEGE."""
        addresses = []
        ## The privileges are stored by e-mail address, so we can use
        ## this to look up the email addresses without accessing the
        ## SPARQL endpoint.
        for email_address in self.privileges:  # pylint: disable=consider-using-dict-items
            email = email_address.lower()
            if self.privileges[email][privilege]:
                addresses.append(email_address)

        return addresses

    def reviewer_email_addresses (self):
        """Returns the e-mail addresses of accounts with 'may_review' privileges."""
        return self.__privileged_role_email_addresses ("may_review")

    def reviewer_accounts (self):
        """Returns the accounts with 'may_review' privileges."""

        email_addresses = self.reviewer_email_addresses ()
        accounts = []
        for email_address in email_addresses:
            account = self.account_by_email (email_address)
            accounts.append (account)

        return accounts

    def quota_reviewer_email_addresses (self):
        """Returns the e-mail addresses of accounts with 'may_review_quotas' privileges."""
        return self.__privileged_role_email_addresses ("may_review_quotas")

    def feedback_reviewer_email_addresses (self):
        """Returns the e-mail addresses of accounts with 'may_process_feedback' privileges."""
        return self.__privileged_role_email_addresses ("may_process_feedback")

    def accounts (self, account_uuid=None, order=None, order_direction=None,
                  limit=None, offset=None, is_active=None, email=None,
                  id_lte=None, id_gte=None, institution_user_id=None,
                  search_for=None):
        """Returns accounts."""

        query = self.__query_from_template ("accounts", {
            "account_uuid": account_uuid,
            "is_active": is_active,
            "email": rdf.escape_string_value(email),
            "institution_user_id": rdf.escape_string_value (institution_user_id),
            "search_for": rdf.escape_string_value (search_for),
            "minimum_account_id": id_gte,
            "maximum_account_id": id_lte,
        })
        query += rdf.sparql_suffix (order, order_direction, limit, offset)
        return self.__run_query (query, query, "accounts")

    def account_by_uuid (self, account_uuid):
        """Returns an account record or None."""

        results    = self.accounts(account_uuid)
        if results:
            return self.__account_with_privileges_and_quotas (results[0])

        return None

    def account_by_email (self, email):
        """Returns the account matching EMAIL."""

        query = self.__query_from_template ("account_by_email", {
            "email":  rdf.escape_string_value (email)
        })

        results = self.__run_query (query)
        if results:
            return self.__account_with_privileges_and_quotas (results[0])

        return None

    def missing_checksummed_files_for_container (self, container_uuid):
        """
        Returns a list of file UUIDs and paths of files without checksums
        for CONTAINER_UUID.
        """

        query = self.__query_from_template ("missing_checksummed_files_for_container", {
            "container_uuid": container_uuid
        })
        return self.__run_query (query)

    def initialize_privileged_accounts (self):
        """Ensures privileged accounts are present in the database."""

        privileged_accounts = list(self.privileges.keys())
        for email in privileged_accounts:
            account = self.account_by_email (email)
            if account is not None:
                self.log.info ("Account for %s already exists.", email)
                continue

            account_uuid = self.insert_account (email=email)
            if not account_uuid:
                self.log.error ("Creating account for %s failed.", email)
                continue

            self.log.info ("Created account for %s.", email)

            orcid = self.privileges[email]["orcid"]
            if orcid is None:
                continue

            author_uuid = self.insert_author (
                email        = email,
                account_uuid = account_uuid,
                orcid_id     = orcid,
                is_active    = True,
                is_public    = True)
            if not author_uuid:
                self.log.warning ("Failed to link author to account for %s.", email)
                continue

            self.log.info ("Linked account of %s to ORCID: %s.", email, orcid)
            continue

    def update_view_and_download_counts (self):
        """Procedure that recalculate views and downloads statistics."""
        query = self.__query_from_template ("update_view_and_download_counts")
        return self.__run_query (query)

    def insert_session (self, account_uuid, name=None, token=None, editable=False,
                        override_mfa=False):
        """Procedure to add a session token for an account_uuid."""

        if account_uuid is None:
            return None, None, None

        account = self.account_by_uuid (account_uuid)
        if account is None:
            return None, None, None

        if token is None:
            token = secrets.token_hex (64)

        current_time = datetime.strftime (datetime.now(), "%Y-%m-%dT%H:%M:%SZ")

        graph       = Graph()
        link_uri    = rdf.unique_node ("session")
        account_uri = URIRef(rdf.uuid_to_uri (account_uuid, "account"))

        graph.add ((link_uri, RDF.type,               rdf.DJHT["Session"]))
        graph.add ((link_uri, rdf.DJHT["account"],    account_uri))
        graph.add ((link_uri, rdf.DJHT["created_date"], Literal(current_time, datatype=XSD.dateTime)))
        graph.add ((link_uri, rdf.DJHT["name"],       Literal(name, datatype=XSD.string)))
        graph.add ((link_uri, rdf.DJHT["token"],      Literal(token, datatype=XSD.string)))
        graph.add ((link_uri, rdf.DJHT["editable"],   Literal(editable, datatype=XSD.boolean)))

        mfa_token = None
        try:
            if self.privileges[account["email"].lower()]["needs_2fa"] and not override_mfa:
                mfa_token = secrets.randbelow (1000000)
                graph.add ((link_uri, rdf.DJHT["mfa_token"], Literal(mfa_token, datatype=XSD.integer)))
                graph.add ((link_uri, rdf.DJHT["mfa_tries"], Literal(0, datatype=XSD.integer)))
        except KeyError:
            pass

        graph.add ((link_uri, rdf.DJHT["active"], Literal((mfa_token is None), datatype=XSD.boolean)))

        if self.add_triples_from_graph (graph):
            return token, mfa_token, rdf.uri_to_uuid (link_uri)

        return None, None, None

    def update_session (self, account_uuid, session_uuid, name=None, active=None):
        """Procedure to edit a session."""

        query = self.__query_from_template ("update_session", {
            "account_uuid":  account_uuid,
            "session_uuid":  session_uuid,
            "name":          name,
            "active":        rdf.escape_boolean_value (active)
        })

        return self.__run_logged_query (query)

    def delete_all_sessions (self):
        """Procedure to delete all sessions."""

        query = self.__query_from_template ("delete_sessions")
        return self.__run_logged_query (query)

    def delete_inactive_session_by_uuid (self, session_uuid):
        """Procedure to remove an inactive session by its UUID alone."""

        query = self.__query_from_template ("delete_inactive_session_by_uuid", {
            "session_uuid": session_uuid
        })

        return self.__run_logged_query (query)

    def delete_session_by_uuid (self, account_uuid, session_uuid):
        """Procedure to remove a session from the state graph."""

        query   = self.__query_from_template ("delete_session_by_uuid", {
            "session_uuid":  session_uuid,
            "account_uuid":  account_uuid
        })

        return self.__run_logged_query (query)

    def delete_session (self, token):
        """Procedure to remove a session from the state graph."""

        if token is None:
            return True

        query = self.__query_from_template ("delete_session", {"token": token})
        return self.__run_logged_query (query)

    def sessions (self, account_uuid, session_uuid=None, mfa_token=None):
        """Returns the sessions for an account."""

        query = self.__query_from_template ("account_sessions", {
            "account_uuid":  account_uuid,
            "session_uuid":  session_uuid,
            "mfa_token":     mfa_token
        })

        return self.__run_query (query)

    def __may_execute_role (self, session_token, task, account=None):
        """Returns True when the sessions' account may perform 'task'."""

        if session_token is None:
            return False

        if account is None:
            account = self.account_by_session_token (session_token)
        try:
            return account[f"may_{task}"]
        except (KeyError, TypeError):
            pass

        return False

    def may_receive_email_notifications (self, email):
        """
        Returns True when the account identified by EMAIL may receive an
        e-mail notification.  This procedure assumes True unless False is
        explicitely specified, so that it can be used in logic where
        e-mails are sent to accounts that have no preference set.
        """
        if email is None:
            return False

        # When an account was created from an ORCID login, there is no
        # valid e-mail address known for the user. These addresses end
        # with just '@orcid'.  This is a safety measure to prevent attempting
        # to send e-mail to invalid e-mail addresses.
        if email.endswith("orcid"):
            return False

        account = self.account_by_email (email)
        try:
            return account["may_receive_email_notifications"]
        except (KeyError, TypeError):
            pass

        # Assume it's OK to send e-mails unless explicitly specified
        # not to do so.
        return True

    def may_review (self, session_token, account=None):
        """Returns True when the session's account is a reviewer."""
        return self.__may_execute_role (session_token, "review", account)

    def may_administer (self, session_token, account=None):
        """Returns True when the session's account is an administrator."""
        return self.__may_execute_role (session_token, "administer", account)

    def may_query (self, session_token, account=None):
        """Returns True when the session's account is an administrator and may query."""
        return (self.__may_execute_role (session_token, "administer", account) and
                self.__may_execute_role (session_token, "query", account))

    def may_impersonate (self, session_token, account=None):
        """Returns True when the session's account may impersonate other accounts."""
        return self.__may_execute_role (session_token, "impersonate", account)

    def may_review_quotas (self, session_token, account=None):
        """Returns True when the session's account may handle storage requests."""
        return self.__may_execute_role (session_token, "review_quotas", account)

    def is_depositor (self, session_token):
        """Returns True when the account linked to the session is a depositor, False otherwise"""
        return self.is_logged_in (session_token)

    def is_logged_in (self, session_token):
        """Returns True when the session_token is valid, False otherwise."""

        if session_token is None:
            return False

        account = self.account_by_session_token (session_token)
        return account is not None

    def properties_for_type (self, rdf_type):
        """Returns properties for the current state graph for RDF_TYPE."""

        query = self.__query_from_template ("explorer_properties", {
            "type": rdf_type
        })

        return self.__run_query (query, query, "explorer_properties")

    def types (self):
        """Returns a list of 'rdf:type's used in the state-graph."""

        query = self.__query_from_template ("explorer_types")
        return self.__run_query (query, query, "explorer_types")

    def types_for_property (self, rdf_type, rdf_property):
        """Returns types for the current state graph for RDF_PROPERTY in RDF_TYPE."""

        query = self.__query_from_template ("explorer_property_types", {
            "type":     rdf_type,
            "property": rdf_property
        })

        return self.__run_query (query, query, "explorer_property_types")

    def add_triples_from_graph (self, graph):
        """Inserts triples from GRAPH into the state graph."""

        ## There's an upper limit to how many triples one can add in a single
        ## INSERT query.  To stay on the safe side, we create batches of 250
        ## triplets per INSERT query.

        counter             = 0
        processing_complete = True
        insertable_graph    = Graph()

        for subject, predicate, noun in graph:
            counter += 1
            insertable_graph.add ((subject, predicate, noun))
            if counter >= 250:
                query = self.__insert_query_for_graph (insertable_graph)
                if not self.__run_query (query):
                    processing_complete = False
                    break

                # Reset the graph by creating a new one.
                insertable_graph = Graph()
                counter = 0

        query = self.__insert_query_for_graph (insertable_graph)
        if not self.__run_query (query):
            processing_complete = False

        if processing_complete:
            return True

        self.log.error ("Inserting triples from a graph failed.")
        self.__log_query (query)

        return False

    def run_query (self, query, session_token):
        """Procedure to run a SPARQL query."""

        if not self.may_query (session_token):
            return False

        if self.enable_query_audit_log:
            execution_type, _ = rdf.query_type (query)
            if execution_type == "update":
                self.__log_query (query, "Query Audit Log (manual execution)")

        return self.__run_query (query)
