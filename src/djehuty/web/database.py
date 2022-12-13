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
from SPARQLWrapper import SPARQLWrapper, JSON, SPARQLExceptions
from rdflib import Graph, Literal, RDF, XSD, URIRef
from jinja2 import Environment, FileSystemLoader
from djehuty.web import cache
from djehuty.utils import rdf
from djehuty.utils import convenience as conv

class SparqlInterface:
    """This class reads and writes data from a SPARQL endpoint."""

    def __init__ (self):

        self.storage     = None
        self.endpoint    = "http://127.0.0.1:8890/sparql"
        self.state_graph = "https://data.4tu.nl/portal/self-test"
        self.privileges  = {}
        self.cache       = cache.CacheLayer(None)
        self.jinja       = Environment(loader = FileSystemLoader(
                            os.path.join(os.path.dirname(__file__),
                                         "resources/sparql_templates")),
                                         autoescape=True)

        self.account_quotas = {}
        self.group_quotas   = {}
        self.default_quota  = 5000000000

        self.sparql      = SPARQLWrapper(self.endpoint)
        self.sparql.setReturnFormat(JSON)
        self.sparql_is_up = True

    ## ------------------------------------------------------------------------
    ## Private methods
    ## ------------------------------------------------------------------------

    def __log_query (self, query):
        logging.info ("Query:\n---\n%s\n---", query)

    def __normalize_binding (self, record):
        for item in record:
            if record[item]["type"] == "typed-literal":
                datatype = record[item]["datatype"]
                if datatype == "http://www.w3.org/2001/XMLSchema#integer":
                    record[item] = int(float(record[item]["value"]))
                elif datatype == "http://www.w3.org/2001/XMLSchema#decimal":
                    record[item] = int(float(record[item]["value"]))
                elif datatype == "http://www.w3.org/2001/XMLSchema#boolean":
                    record[item] = bool(int(record[item]["value"]))
                elif datatype == "http://www.w3.org/2001/XMLSchema#dateTime":
                    time_value = record[item]["value"].partition(".")[0]
                    if time_value[-1] == 'Z':
                        time_value = time_value[:-1]
                    record[item] = time_value
                elif datatype == "http://www.w3.org/2001/XMLSchema#date":
                    record[item] = record[item]["value"]
                elif datatype == "http://www.w3.org/2001/XMLSchema#string":
                    if record[item]["value"] == "NULL":
                        record[item] = None
                    else:
                        record[item] = record[item]["value"]
            elif record[item]["type"] == "literal":
                if (record[item]['value'].startswith("Modify ") or
                    record[item]['value'].startswith("Insert into ") or
                    record[item]['value'].startswith("Delete from ")):
                    # The 'store' member has been dynamically added in the 'ui' module.
                    logging.store ("%s", record[item]['value']) #  pylint: disable=no-member
                    return record[item]["value"]

                record[item] = record[item]["value"]

            elif record[item]["type"] == "uri":
                record[item] = str(record[item]["value"])
            else:
                logging.info("Not a typed-literal: %s", record[item]['type'])
        return record

    def __query_from_template (self, name, args=None):
        template   = self.jinja.get_template (f"{name}.sparql")
        parameters = { "state_graph": self.state_graph }
        if args is None:
            args = {}

        return template.render ({ **args, **parameters })

    def __run_query (self, query, cache_key_string=None, prefix=None):

        cache_key = None
        if cache_key_string is not None:
            cache_key = self.cache.make_key (cache_key_string)
            cached    = self.cache.cached_value(prefix, cache_key)
            if cached is not None:
                return cached

        self.sparql.method = 'POST'
        self.sparql.setQuery(query)
        results = []
        try:
            query_results = self.sparql.query().convert()
            results = list(map(self.__normalize_binding,
                               query_results["results"]["bindings"]))

            if cache_key_string is not None:
                self.cache.cache_value (prefix, cache_key, results, query)

            if not self.sparql_is_up:
                logging.info("Connection to the SPARQL endpoint seems up again.")
                self.sparql_is_up = True

        except HTTPError as error:
            logging.error("SPARQL endpoint returned %d:\n---\n%s\n---",
                          error.code, error.message)
            return []
        except (URLError, SPARQLExceptions.EndPointNotFound):
            if self.sparql_is_up:
                logging.error("Connection to the SPARQL endpoint seems down.")
                self.sparql_is_up = False
                return []
        except SPARQLExceptions.QueryBadFormed:
            logging.error("Badly formed SPARQL query:")
            self.__log_query (query)
        except SPARQLExceptions.EndPointInternalError as error:
            logging.error("SPARQL internal error: %s", error)
            return []
        except Exception as error:
            logging.error("SPARQL query failed.")
            logging.error("Exception: %s", type(error))
            self.__log_query (query)
            return []

        return results

    def __insert_query_for_graph (self, graph):
        return rdf.insert_query (self.state_graph, graph)

    ## ------------------------------------------------------------------------
    ## GET METHODS
    ## ------------------------------------------------------------------------

    def dataset_storage_used (self, container_uri):
        """Returns the number of bytes used by a dataset."""

        query = self.__query_from_template ("dataset_storage_used", {
            "container_uri": container_uri
        })

        results = self.__run_query (query, query, f"{container_uri}_dataset_storage")
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
                         item_uuid=None, item_type="dataset", is_published=True,
                         is_latest=False):
        """Returns datasets or collections filtered by its parameters."""

        query = self.__query_from_template ("container_items", {
            "account_uuid":   account_uuid,
            "container_uri":  rdf.uuid_to_uri (container_uuid, "container"),
            "item_uri":       rdf.uuid_to_uri (item_uuid, item_type),
            "item_type":      item_type,
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
            for element in search_for:
                if (isinstance (element, dict)
                    and len(element.items()) == 1
                    and next(iter(element)) == "operator"):
                    filters += f" {element['operator'].upper()} "
                else:
                    filter_list = []
                    for key, value in element.items():
                        if '"' in value:
                            value = value.replace('"', '\\\"')
                        filter_list.append(f" CONTAINS(LCASE(?{key}), \"{value.lower()}\") \n")
                    filters += "(" + " OR\n".join(filter_list) + ") \n"
            filters += ")"
        else:
            filter_list = []
            for search_term in search_for:
                search_term_lower = search_term.lower()
                filter_list.append(f"       CONTAINS(LCASE(?title),          \"{search_term_lower}\")")
                filter_list.append(f"       CONTAINS(LCASE(?resource_title), \"{search_term_lower}\")")
                filter_list.append(f"       CONTAINS(LCASE(?description),    \"{search_term_lower}\")")
                filter_list.append(f"       CONTAINS(LCASE(?citation),       \"{search_term_lower}\")")
                if search_format:
                    filter_list.append(f"       CONTAINS(LCASE(?format),         \"{search_term_lower}\")")
            if len(filter_list) > 0:
                filters += "FILTER(\n" + " OR\n".join(filter_list) + ')'

        return filters

    def datasets (self, account_uuid=None, categories=None, collection_uri=None,
                  container_uuid=None, dataset_id=None, dataset_uuid=None, doi=None,
                  exclude_ids=None, groups=None, handle=None, institution=None,
                  is_latest=False, item_type=None, limit=None, modified_since=None,
                  offset=None, order=None, order_direction=None, published_since=None,
                  resource_doi=None, return_count=False, search_for=None, search_format=False,
                  version=None, is_published=True, is_under_review=None, git_uuid=None,
                  private_link_id_string=None):
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
        filters += rdf.sparql_filter ("private_link_id_string", private_link_id_string, escape=True)
        filters += rdf.sparql_in_filter ("group_id",    groups)
        filters += rdf.sparql_in_filter ("dataset_id", exclude_ids, negate=True)
        filters += self.__search_query_to_sparql_filters (search_for, search_format)

        if categories is not None:
            filters += f"FILTER ((?category_id IN ({','.join(map(str, categories))})) OR "
            filters += f"(?parent_category_id IN ({','.join(map(str, categories))})))\n"


        if published_since is not None:
            filters += rdf.sparql_bound_filter ("published_date")
            filters += f"FILTER (?published_date > \"{published_since}\"^^xsd:dateTime)\n"

        if modified_since is not None:
            filters += rdf.sparql_bound_filter ("modified_date")
            filters += f"FILTER (?modified_date > \"{modified_since}\"^^xsd:dateTime)\n"

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

        cache_key = f"datasets_{account_uuid}" if account_uuid is not None else "datasets"
        return self.__run_query (query, query, cache_key)

    def repository_statistics (self):
        """Procedure to retrieve repository-wide statistics."""

        datasets_query    = self.__query_from_template ("statistics_datasets")
        collections_query = self.__query_from_template ("statistics_collections")
        authors_query     = self.__query_from_template ("statistics_authors")
        files_query       = self.__query_from_template ("statistics_files")

        row = { "datasets": 0, "authors": 0, "collections": 0, "files": 0, "bytes": 0 }
        try:
            datasets    = self.__run_query (datasets_query, datasets_query, "statistics")
            authors     = self.__run_query (authors_query, authors_query, "statistics")
            collections = self.__run_query (collections_query, collections_query, "statistics")
            files       = self.__run_query (files_query, files_query, "statistics")
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
                logging.error ("Retrieving uuid for %s failed.", identifier)
                return None

        return identifier

    def container (self, container_uuid, item_type="dataset"):
        """Procedure to get container properties (incl shallow statistics)."""

        query   = self.__query_from_template ("container", {
            "item_type"     : item_type,
            "container_uuid": container_uuid
        })

        return self.__run_query (query, query, "container")

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
            filters += (f"FILTER (CONTAINS(LCASE(?first_name), {escaped}) OR\n"
                        f"        CONTAINS(LCASE(?last_name),  {escaped}) OR\n"
                        f"        CONTAINS(LCASE(?full_name),  {escaped}) OR\n"
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

    def author_collaborators (self, author_uri):
        """Returns collaborating authors for a given AUTHOR_URI."""
        query = self.__query_from_template ("author_collaborators", {
            "author_uri": author_uri
        })
        return self.__run_query(query)

    def dataset_files (self, name=None, size=None, is_link_only=None,
                       file_uuid=None, download_url=None, supplied_md5=None,
                       computed_md5=None, viewer_type=None, preview_state=None,
                       status=None, upload_url=None, upload_token=None,
                       order="order_index", order_direction="asc", limit=10,
                       dataset_uri=None, account_uuid=None, file_id=None):
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

        query = self.__query_from_template ("dataset_files", {
            "dataset_uri":         dataset_uri,
            "account_uuid":        account_uuid,
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
        """Procedure to retrieve categories of a dataset."""

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

    def collections (self, limit=10, offset=None, order=None,
                     order_direction=None, institution=None, categories=None,
                     published_since=None, modified_since=None, group=None,
                     resource_doi=None, resource_id=None, doi=None, handle=None,
                     account_uuid=None, search_for=None, collection_id=None,
                     version=None, container_uuid=None, is_latest=False,
                     is_published=True):
        """Procedure to retrieve collections."""

        filters  = rdf.sparql_filter ("container_uri",  rdf.uuid_to_uri (container_uuid, "container"), is_uri=True)
        filters += rdf.sparql_filter ("institution_id", institution)
        filters += rdf.sparql_filter ("group_id",       group)
        filters += rdf.sparql_filter ("collection_id",  collection_id)
        filters += rdf.sparql_filter ("version",        version)
        filters += rdf.sparql_filter ("resource_doi",   resource_doi, escape=True)
        filters += rdf.sparql_filter ("resource_id",    resource_id,  escape=True)
        filters += rdf.sparql_filter ("doi",            doi,          escape=True)
        filters += rdf.sparql_filter ("handle",         handle,       escape=True)

        if categories is not None:
            filters += f"FILTER ((?category_id IN ({','.join(map(str, categories))})) OR "
            filters += f"(?parent_category_id IN ({','.join(map(str, categories))})))\n"

        if search_for is not None:
            escaped = rdf.escape_string_value (search_for)
            filters += (f"FILTER (CONTAINS(STR(?title),          {escaped}) OR\n"
                        f"        CONTAINS(STR(?resource_title), {escaped}) OR\n"
                        f"        CONTAINS(STR(?description),    {escaped}) OR\n"
                        f"        CONTAINS(STR(?citation),       {escaped}))")

        if published_since is not None:
            filters += rdf.sparql_bound_filter ("published_date")
            filters += f"FILTER (?published_date > \"{published_since}\"^^xsd:dateTime)\n"

        if modified_since is not None:
            filters += rdf.sparql_bound_filter ("modified_date")
            filters += f"FILTER (?modified_date > \"{modified_since}\"^^xsd:dateTime)\n"

        query   = self.__query_from_template ("collections", {
            "account_uuid": account_uuid,
            "categories":   categories,
            "filters":      filters,
            "is_latest":    is_latest,
            "is_published": is_published
        })
        query += rdf.sparql_suffix (order, order_direction, limit, offset)

        return self.__run_query(query)

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
            filters += (f"FILTER (CONTAINS(LCASE(?title),       {escaped}) OR\n"
                        f"        CONTAINS(LCASE(?grant_code),  {escaped}) OR\n"
                        f"        CONTAINS(LCASE(?funder_name), {escaped}) OR\n"
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

    def wrap_dataset_in_blank_node (self, dataset_uuid):
        """Returns the blank node URI for the rdf:List node for a dataset."""

        rdf_store  = Graph ()
        blank_node = rdf.blank_node ()
        dataset_uri = rdf.uuid_to_uri (dataset_uuid, "dataset")
        rdf.add (rdf_store, blank_node, RDF.first, URIRef(dataset_uri), "url")
        rdf.add (rdf_store, blank_node, RDF.rest, RDF.nil)

        if self.add_triples_from_graph (rdf_store):
            return blank_node

        return None

    def update_dataset_git_uuid (self, dataset_uuid):
        """Procedure to update the Git UUID of a draft dataset."""

        query = self.__query_from_template ("update_git_uuid", {
            "dataset_uuid": dataset_uuid,
            "git_uuid":     rdf.escape_string_value (str (uuid.uuid4()))
        })

        return self.__run_query (query)

    def insert_dataset (self,
                        title,
                        account_uuid,
                        container_uuid=None,
                        description=None,
                        defined_type=None,
                        defined_type_name=None,
                        funding=None,
                        license_url=None,
                        language=None,
                        doi=None,
                        handle=None,
                        resource_doi=None,
                        resource_title=None,
                        first_online=None,
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
            container_uri         = container,
            item_uri              = uri,
            revision              = revision,
            first_online          = first_online,
            publisher_publication = publisher_publication,
            posted                = posted,
            submission            = submission
        )

        self.insert_item_list   (graph, uri, references, "references")
        self.insert_item_list   (graph, uri, tags, "tags")
        categories = rdf.uris_from_records (categories, "category")
        self.insert_item_list (graph, uri, categories, "categories")
        self.insert_record_list (graph, uri, authors, "authors", self.insert_author)
        self.insert_record_list (graph, uri, files, "files", self.insert_file)
        self.insert_record_list (graph, uri, funding_list, "funding_list", self.insert_funding)
        self.insert_record_list (graph, uri, private_links, "private_links", self.insert_private_link)


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

        # Reserve a UUID for a Git repository.
        if git_uuid is None:
            git_uuid = str(uuid.uuid4())

        rdf.add (graph, uri, rdf.DJHT["git_uuid"], git_uuid, XSD.string)

        # Add the dataset to its container.
        graph.add ((container, rdf.DJHT["draft"],       uri))
        graph.add ((container, rdf.DJHT["account"],     account_uri))

        if self.add_triples_from_graph (graph):
            container_uuid = rdf.uri_to_uuid (container)
            logging.info ("Inserted dataset %s", container_uuid)
            self.cache.invalidate_by_prefix (f"datasets_{account_uuid}")
            return (container_uuid, rdf.uri_to_uuid (uri))

        return None

    def update_account (self, account_uuid, active=None, email=None, job_title=None,
                        first_name=None, last_name=None, institution_user_id=None,
                        institution_id=None, pending_quota_request=None,
                        maximum_file_size=None, modified_date=None, created_date=None,
                        location=None, biography=None, categories=None):
        """Procedure to update account settings."""

        if modified_date is None:
            modified_date = datetime.strftime (datetime.now(), "%Y-%m-%dT%H:%M:%S")

        query        = self.__query_from_template ("update_account", {
            "account_uuid":          account_uuid,
            "is_active":             active,
            "job_title":             job_title,
            "email":                 email,
            "first_name":            first_name,
            "last_name":             last_name,
            "location":              location,
            "biography":             biography,
            "institution_user_id":   institution_user_id,
            "institution_id":        institution_id,
            "pending_quota_request": pending_quota_request,
            "maximum_file_size":     maximum_file_size,
            "modified_date":         modified_date,
            "created_date":          created_date
        })

        self.cache.invalidate_by_prefix ("accounts")
        results = self.__run_query (query)
        if results and categories:

            if categories:
                graph = Graph()
                items = rdf.uris_from_records (categories, "category")
                self.delete_account_list (account_uuid, "categories")
                self.insert_item_list (graph,
                                       URIRef(rdf.uuid_to_uri (account_uuid, "account")),
                                       items,
                                       "categories")

                if not self.add_triples_from_graph (graph):
                    logging.error("Updating categories for account %d failed.",
                                  account_uuid)
                    return None

        return results

    def update_item_list (self, container_uuid, account_uuid, items, predicate):
        """Procedure to modify a list property of a container item."""
        try:
            graph   = Graph()
            dataset = self.container_items (container_uuid = container_uuid,
                                            is_published   = False,
                                            account_uuid   = account_uuid)[0]

            self.delete_associations (container_uuid, account_uuid, predicate)
            if items:
                self.insert_item_list (graph,
                                       URIRef(dataset["uri"]),
                                       items,
                                       predicate)

                if not self.add_triples_from_graph (graph):
                    logging.error ("%s insert query failed for %s",
                                   predicate, container_uuid)
                    return False

            return True

        except IndexError:
            logging.error ("Could not insert %s items for %s",
                           predicate, container_uuid)

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
            rdf.add (graph, author_uri, rdf.DJHT["account"], account_uri)

        if self.add_triples_from_graph (graph):
            return rdf.uri_to_uuid (author_uri)

        return None

    def insert_account (self, email=None, first_name=None, last_name=None,
                        full_name=None, location=None, biography=None,
                        categories=None):
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
        rdf.add (graph, account_uri, rdf.DJHT["full_name"],  full_name,  XSD.string)
        rdf.add (graph, account_uri, rdf.DJHT["email"],      email,      XSD.string)
        rdf.add (graph, account_uri, rdf.DJHT["domain"],     domain,     XSD.string)
        rdf.add (graph, account_uri, rdf.DJHT["location"],   location,   XSD.string)
        rdf.add (graph, account_uri, rdf.DJHT["biography"],  biography,  XSD.string)

        # Legacy properties.
        rdf.add (graph, account_uri, rdf.DJHT["institution_id"], 898)
        rdf.add (graph, account_uri, rdf.DJHT["url_name"],       "_", XSD.string)

        if self.add_triples_from_graph (graph):
            return rdf.uri_to_uuid (account_uri)

        return None

    def insert_timeline (self, graph, container_uri=None, item_uri=None,
                         revision=None, first_online=None, posted=None,
                         submission=None, publisher_publication=None):
        """Procedure to add a timeline to the state graph."""

        rdf.add (graph, item_uri, rdf.DJHT["revision_date"],          revision,     XSD.dateTime)
        rdf.add (graph, container_uri, rdf.DJHT["first_online_date"], first_online, XSD.dateTime)
        rdf.add (graph, item_uri, rdf.DJHT["posted_date"],            posted,       XSD.dateTime)
        rdf.add (graph, item_uri, rdf.DJHT["publisher_publication_date"], publisher_publication, XSD.dateTime)
        rdf.add (graph, item_uri, rdf.DJHT["submission_date"],        submission,   XSD.dateTime)

    def delete_associations (self, container_uuid, account_uuid, predicate):
        """Procedure to delete the list of PREDICATE of a dataset or collection."""

        query = self.__query_from_template ("delete_associations", {
            "container_uri": rdf.uuid_to_uri (container_uuid, "container"),
            "predicate":     predicate,
            "account_uuid":  account_uuid,
        })

        return self.__run_query(query)

    def delete_account_list (self, account_uuid, predicate):
        """Procedure to delete the list of PREDICATE of an account."""

        query = self.__query_from_template ("delete_account_list", {
            "predicate":     predicate,
            "account_uuid":  account_uuid,
        })

        return self.__run_query(query)

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

        return self.__run_query(query)

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

        self.cache.invalidate_by_prefix ("dataset")
        if self.add_triples_from_graph (graph):
            existing_files = self.dataset_files (dataset_uri  = dataset_uri,
                                                 limit        = None,
                                                 account_uuid = account_uuid)
            existing_files = list(map (lambda item: URIRef(rdf.uuid_to_uri(item["uuid"], "file")),
                                         existing_files))

            new_files    = existing_files + [URIRef(file_uri)]
            dataset_uuid = rdf.uri_to_uuid (dataset_uri)
            dataset      = self.datasets (dataset_uuid = dataset_uuid,
                                          account_uuid = account_uuid,
                                          is_published = False,
                                          limit        = 1)[0]

            container_uri = f"container:{dataset['container_uuid']}"
            self.cache.invalidate_by_prefix (f"{account_uuid}_storage")
            self.cache.invalidate_by_prefix (f"{container_uri}_dataset_storage")
            if self.update_item_list (dataset["container_uuid"],
                                      account_uuid,
                                      new_files,
                                      "files"):
                return rdf.uri_to_uuid (file_uri)

        return None

    def update_file (self, account_uuid, file_uuid, download_url=None,
                     computed_md5=None, viewer_type=None, preview_state=None,
                     file_size=None, status=None, filesystem_location=None):
        """Procedure to update file metadata."""

        query   = self.__query_from_template ("update_file", {
            "account_uuid":  account_uuid,
            "file_uuid":     file_uuid,
            "filesystem_location": filesystem_location,
            "download_url":  download_url,
            "computed_md5":  computed_md5,
            "viewer_type":   viewer_type,
            "preview_state": preview_state,
            "file_size":     file_size,
            "status":        status
        })

        return self.__run_query(query)

    def insert_license (self, license_id, name=None, url=None):
        """Procedure to add an license to the state graph."""

        graph    = Graph()
        license_uri = rdf.ROW[f"license_{license_id}"]

        graph.add ((license_uri, RDF.type,               rdf.DJHT["License"]))
        graph.add ((license_uri, rdf.DJHT["id"],          Literal(license_id)))

        rdf.add (graph, license_uri, rdf.DJHT["name"],  name, XSD.string)
        rdf.add (graph, license_uri, rdf.DJHT["url"],   url,  XSD.string)

        if self.add_triples_from_graph (graph):
            return license_id

        return None

    def insert_private_link (self, dataset_uuid, account_uuid,
                             read_only=True, id_string=None,
                             is_active=True, expires_date=None):
        """Procedure to add a private link to the state graph."""

        if dataset_uuid is None:
            return None

        if id_string is None:
            id_string = secrets.token_urlsafe()

        graph    = Graph()
        link_uri = rdf.unique_node ("private_link")

        graph.add ((link_uri, RDF.type,      rdf.DJHT["PrivateLink"]))

        rdf.add (graph, link_uri, rdf.DJHT["id"],           id_string,    XSD.string)
        rdf.add (graph, link_uri, rdf.DJHT["read_only"],    read_only)
        rdf.add (graph, link_uri, rdf.DJHT["is_active"],    is_active)
        rdf.add (graph, link_uri, rdf.DJHT["expires_date"], expires_date, XSD.string)

        if self.add_triples_from_graph (graph):
            dataset_uri    = rdf.uuid_to_uri (dataset_uuid, "dataset")
            existing_links = self.private_links (item_uri=dataset_uri, account_uuid=account_uuid)
            existing_links = list(map (lambda item: URIRef(rdf.uuid_to_uri(item["uuid"], "private_link")),
                                               existing_links))

            new_links    = existing_links + [URIRef(link_uri)]
            dataset      = self.datasets (dataset_uuid = dataset_uuid,
                                          account_uuid = account_uuid,
                                          is_published = False,
                                          limit        = 1)[0]

            if self.update_item_list (dataset["container_uuid"],
                                      account_uuid,
                                      new_links,
                                      "private_links"):
                return link_uri

        return None

    def insert_custom_field_value (self, name=None, value=None,
                                   item_uri=None, graph=None):
        """Procedure to add a custom field value to the state graph."""

        if name is None or value is None or item_uri is None or graph is None:
            logging.error ("insert_custom_field_value was passed None parameters.")
            return False

        name = conv.custom_field_name (name)
        rdf.add (graph, item_uri, rdf.DJHT[name], value)
        return True

    def delete_dataset_draft (self, container_uuid, account_uuid):
        """Remove the draft dataset from a container in the state graph."""

        query   = self.__query_from_template ("delete_dataset_draft", {
            "account_uuid":        account_uuid,
            "container_uri":       rdf.uuid_to_uri (container_uuid, "container")
        })

        result = self.__run_query (query)
        self.cache.invalidate_by_prefix (f"{account_uuid}_storage")
        self.cache.invalidate_by_prefix (f"container:{container_uuid}_dataset_storage")
        self.cache.invalidate_by_prefix (f"dataset_{container_uuid}")
        self.cache.invalidate_by_prefix (f"datasets_{account_uuid}")

        return result

    def publish_dataset (self, container_uuid):
        """Procedure to publish a draft dataset."""

        draft = None
        try:
            draft = self.datasets (container_uuid = container_uuid,
                                   is_published   = False)[0]
        except IndexError:
            return False

        new_version_number = 1
        latest             = None
        try:
            latest = self.datasets (container_uuid = container_uuid,
                                    is_published   = True,
                                    is_latest      = True)[0]
            new_version_number = latest["version"] + 1
        except IndexError:
            pass

        dataset_uuid = draft["uuid"]
        blank_node   = self.wrap_dataset_in_blank_node (dataset_uuid)
        query        = self.__query_from_template ("publish_draft_dataset", {
            "blank_node":        blank_node,
            "version":           new_version_number,
            "container_uuid":    container_uuid,
            "dataset_uuid":      dataset_uuid,
            "first_publication": not latest
        })

        if self.__run_query (query):
            self.cache.invalidate_by_prefix ("reviews")
            self.cache.invalidate_by_prefix (f"dataset_{container_uuid}")
            return True

        return False

    def create_draft_from_published_dataset (self, container_uuid):
        """Procedure to copy a published dataset as draft in its container."""

        latest_uri = None
        try:
            latest = self.datasets (container_uuid = container_uuid,
                                    is_published   = True,
                                    is_latest      = True,
                                    limit          = 1)[0]

            latest_uri      = latest["uri"]
        except (IndexError, TypeError):
            return None

        ## Derive the new draft from the published version.
        draft_authors       = self.authors(item_uri=latest_uri, limit=None)
        draft_files         = self.dataset_files(dataset_uri=latest_uri, limit=None)
        draft_tags          = self.tags(item_uri=latest_uri, limit=None)
        draft_categories    = self.categories(item_uri=latest_uri, limit=None)
        draft_references    = self.references(item_uri=latest_uri, limit=None)
        draft_derived_from  = self.derived_from(item_uri=latest_uri, limit=None)
        draft_fundings      = self.fundings(item_uri=latest_uri, limit=None)
        draft_custom_fields = self.custom_fields (item_uri=latest_uri, item_type="dataset")

        draft_funding_title = None
        if draft_fundings:
            draft_funding_title = draft_fundings[0]["title"]

        ## Insert dataset
        # We don't insert the DOI because the draft will get a new DOI.
        container_uuid, draft_uuid = self.insert_dataset (
                title                 = conv.value_or_none (latest, "title"),
                account_uuid          = conv.value_or_none (latest, "account_uuid"),
                container_uuid        = container_uuid,
                description           = conv.value_or_none (latest, "description"),
                defined_type          = conv.value_or_none (latest, "defined_type"),
                defined_type_name     = conv.value_or_none (latest, "defined_type_name"),
                funding               = draft_funding_title,
                license_url           = conv.value_or_none (latest, "license_url"),
                language              = conv.value_or_none (latest, "language"),
                resource_doi          = conv.value_or_none (latest, "resource_doi"),
                resource_title        = conv.value_or_none (latest, "resource_title"),
                first_online          = conv.value_or_none (latest, "timeline_first_online"),
                publisher_publication = conv.value_or_none (latest, "timeline_publisher_publication"),
                submission            = conv.value_or_none (latest, "timeline_submission"),
                posted                = conv.value_or_none (latest, "timeline_posted"),
                revision              = conv.value_or_none (latest, "timeline_revision"),
                group_id              = conv.value_or_none (latest, "group_id"),
                publisher             = conv.value_or_none (latest, "publisher"),
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
                git_uuid              = rdf.escape_string_value (str (uuid.uuid4())),
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

    def update_dataset (self, container_uuid, account_uuid, title=None,
                        description=None, resource_doi=None, doi=None,
                        resource_title=None, license_url=None, group_id=None,
                        time_coverage=None, publisher=None, language=None,
                        mimetype=None, contributors=None, license_remarks=None,
                        geolocation=None, longitude=None, latitude=None,
                        data_link=None, has_linked_file=None, derived_from=None,
                        same_as=None, organizations=None, categories=None,
                        defined_type=None, defined_type_name=None,
                        embargo_until_date=None, embargo_type=None,
                        embargo_title=None, embargo_reason=None,
                        embargo_allow_access_requests=None, is_embargoed=False,
                        agreed_to_deposit_agreement=False, agreed_to_publish=False,
                        is_metadata_record=False, metadata_reason=None):
        """Procedure to overwrite parts of a dataset."""

        query   = self.__query_from_template ("update_dataset", {
            "account_uuid":    account_uuid,
            "container_uri":   rdf.uuid_to_uri (container_uuid, "container"),
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
            "modified_date":   datetime.strftime (datetime.now(), "%Y-%m-%dT%H:%M:%SZ"),
            "organizations":   rdf.escape_string_value (organizations),
            "publisher":       rdf.escape_string_value (publisher),
            "resource_doi":    rdf.escape_string_value (resource_doi),
            "resource_title":  rdf.escape_string_value (resource_title),
            "same_as":         rdf.escape_string_value (same_as),
            "time_coverage":   rdf.escape_string_value (time_coverage),
            "title":           rdf.escape_string_value (title),
            "is_embargoed":    int(is_embargoed),
            "is_metadata_record": rdf.escape_boolean_value (is_metadata_record),
            "metadata_reason": rdf.escape_string_value (metadata_reason),
            "embargo_until_date": rdf.escape_date_value (embargo_until_date),
            "embargo_type":    rdf.escape_string_value (embargo_type),
            "embargo_title":   rdf.escape_string_value (embargo_title),
            "embargo_reason":  rdf.escape_string_value (embargo_reason),
            "embargo_allow_access_requests":
                               rdf.escape_boolean_value (embargo_allow_access_requests),
            "agreed_to_deposit_agreement":
                               rdf.escape_boolean_value (agreed_to_deposit_agreement),
            "agreed_to_publish": rdf.escape_boolean_value (agreed_to_publish),
        })

        self.cache.invalidate_by_prefix (f"datasets_{account_uuid}")
        self.cache.invalidate_by_prefix (f"dataset_{container_uuid}")
        results = self.__run_query (query)
        if results:
            items = []
            if categories:
                items = rdf.uris_from_records (categories, "category")
            self.update_item_list (container_uuid, account_uuid, items, "categories")
        else:
            return False

        return True

    def delete_dataset_embargo (self, dataset_uri, account_uuid):
        """Procedure to lift the embargo on a dataset."""

        query   = self.__query_from_template ("delete_dataset_embargo", {
            "account_uuid": account_uuid,
            "dataset_uri":  dataset_uri
        })

        return self.__run_query(query)

    def delete_private_links (self, container_uuid, account_uuid, link_id):
        """Procedure to remove private links to a dataset."""

        query   = self.__query_from_template ("delete_private_links", {
            "account_uuid":   account_uuid,
            "container_uuid": container_uuid,
            "id_string":      link_id
        })

        return self.__run_query(query)

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

        return self.__run_query(query)

    def dataset_update_thumb (self, dataset_id, version, account_uuid, file_id):
        """Procedure to update the thumbnail of a dataset."""

        filters = rdf.sparql_filter ("file_id", file_id)
        query   = self.__query_from_template ("update_dataset_thumb", {
            "account_uuid": account_uuid,
            "dataset_id":  dataset_id,
            "version":     version,
            "filters":     filters
        })

        return self.__run_query(query)

    def insert_collection (self, title,
                           account_uuid,
                           collection_id=None,
                           funding=None,
                           funding_list=None,
                           description=None,
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
                           resource_id=None,
                           resource_doi=None,
                           resource_link=None,
                           resource_title=None,
                           resource_version=None,
                           group_id=None,
                           first_online=None,
                           publisher_publication=None,
                           submission=None,
                           posted=None,
                           revision=None,
                           private_links=None):
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
        container               = self.container_uri (graph, None, "collection", account_uuid)
        account_uri             = URIRef(rdf.uuid_to_uri (account_uuid, "account"))

        ## TIMELINE
        ## --------------------------------------------------------------------
        self.insert_timeline (
            graph                 = graph,
            container_uri         = container,
            item_uri              = uri,
            revision              = revision,
            first_online          = first_online,
            publisher_publication = publisher_publication,
            posted                = posted,
            submission            = submission
        )

        self.insert_item_list   (graph, uri, references, "references")
        self.insert_item_list   (graph, uri, tags, "tags")

        categories = rdf.uris_from_records (categories, "category")
        self.insert_item_list (graph, uri, categories, "categories")
        self.insert_record_list (graph, uri, authors, "authors", self.insert_author)
        self.insert_record_list (graph, uri, funding_list, "funding_list", self.insert_funding)
        self.insert_record_list (graph, uri, private_links, "private_links", self.insert_private_link)

        ## DATASETS
        ## --------------------------------------------------------------------
        # ...

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
        rdf.add (graph, uri, rdf.DJHT["funding"],        funding,        XSD.string)
        rdf.add (graph, uri, rdf.DJHT["doi"],            doi,            XSD.string)
        rdf.add (graph, uri, rdf.DJHT["handle"],         handle,         XSD.string)
        rdf.add (graph, uri, rdf.DJHT["url"],            url,            XSD.string)
        rdf.add (graph, uri, rdf.DJHT["resource_id"],    resource_id,    XSD.string)
        rdf.add (graph, uri, rdf.DJHT["resource_doi"],   resource_doi,   XSD.string)
        rdf.add (graph, uri, rdf.DJHT["resource_link"],  resource_link,  XSD.string)
        rdf.add (graph, uri, rdf.DJHT["resource_title"], resource_title, XSD.string)
        rdf.add (graph, uri, rdf.DJHT["resource_version"], resource_version)
        rdf.add (graph, uri, rdf.DJHT["group_id"],       group_id)

        current_time = datetime.strftime (datetime.now(), "%Y-%m-%dT%H:%M:%S")
        rdf.add (graph, uri, rdf.DJHT["created_date"],   current_time, XSD.string)
        rdf.add (graph, uri, rdf.DJHT["modified_date"],  current_time, XSD.string)
        rdf.add (graph, uri, rdf.DJHT["is_public"],      0)

        # Add the collection to its container.
        graph.add ((container, rdf.DJHT["draft"],       uri))
        graph.add ((container, rdf.DJHT["account"],     account_uri))

        if self.add_triples_from_graph (graph):
            container_uuid = rdf.uri_to_uuid (container)
            logging.info ("Inserted collection %s", container_uuid)
            return container_uuid

        return None

    def delete_collection (self, container_uuid, account_uuid):
        """Procedure to remove a collection from the state graph."""

        query   = self.__query_from_template ("delete_collection_draft", {
            "account_uuid":   account_uuid,
            "container_uri":  rdf.uuid_to_uri (container_uuid, "container")
        })

        return self.__run_query(query)

    def update_collection (self, container_uuid, account_uuid, title=None,
                           description=None, resource_doi=None,
                           resource_title=None, group_id=None, datasets=None,
                           time_coverage=None, publisher=None, language=None,
                           contributors=None, geolocation=None, longitude=None,
                           latitude=None, organizations=None, categories=None):
        """Procedure to overwrite parts of a collection."""

        query   = self.__query_from_template ("update_collection", {
            "account_uuid":      account_uuid,
            "container_uri":     rdf.uuid_to_uri (container_uuid, "container"),
            "contributors":      contributors,
            "description":       description,
            "geolocation":       geolocation,
            "language":          language,
            "latitude":          latitude,
            "group_id":          group_id,
            "longitude":         longitude,
            "modified_date":     datetime.strftime (datetime.now(), "%Y-%m-%dT%H:%M:%S"),
            "organizations":     organizations,
            "publisher":         publisher,
            "resource_doi":      resource_doi,
            "resource_title":    resource_title,
            "time_coverage":     time_coverage,
            "title":             title
        })

        self.cache.invalidate_by_prefix ("collection")
        self.cache.invalidate_by_prefix (f"{container_uuid}_collection")

        results = self.__run_query (query, query, f"{container_uuid}_collection")
        if results and categories:
            items = rdf.uris_from_records (categories, "category")
            self.update_item_list (container_uuid, account_uuid, items, "categories")

        if results and datasets:
            items = rdf.uris_from_records (datasets, "dataset")
            self.update_item_list (container_uuid, account_uuid, items, "datasets")

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

        categories = self.root_categories ()
        for category in categories:
            subcategories = self.subcategories_for_category (category["uuid"])
            category["subcategories"] = subcategories

        return categories

    def group (self, group_id=None, parent_id=None, name=None,
               association=None, limit=None, offset=None,
               order=None, order_direction=None, starts_with=False):
        """Procedure to return group information."""

        filters = ""
        filters += rdf.sparql_filter ("id", group_id)
        filters += rdf.sparql_filter ("parent_id", parent_id)

        if name is not None:
            if starts_with:
                filters += f"FILTER (STRSTARTS(STR(?name), \"{name}\"))"
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
                filters += f"FILTER ((STRSTARTS(STR(?data_url), \"{ startswith[0] }\"))"
                for filter_item in startswith[1:]:
                    filters += f" OR (STRSTARTS(STR(?data_url), \"{filter_item}\"))"
                filters += ")\n"
            elif isinstance(startswith, str):
                filters += f"FILTER (STRSTARTS(STR(?data_url), \"{ startswith }\"))\n"
            else:
                logging.error("startswith of type %s is not supported", type(startswith))

        if endswith is not None:
            filters += f"FILTER (STRENDS(STR(?data_url), \"{ endswith }\"))\n"

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
            "status":         rdf.escape_string_value (status),
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

        rdf.add (graph, uri, rdf.DJHT["request_date"],   request_date,  XSD.dateTime)
        rdf.add (graph, uri, rdf.DJHT["reminder_date"],  reminder_date, XSD.dateTime)
        rdf.add (graph, uri, rdf.DJHT["assigned_to"],    assigned_to,   XSD.integer)
        rdf.add (graph, uri, rdf.DJHT["status"],         status,        XSD.string)

        if self.add_triples_from_graph (graph):
            self.cache.invalidate_by_prefix ("reviews")
            logging.info ("Inserted review for dataset %s", dataset_uri)
            return uri

        return None

    def update_review (self, review_uri, dataset_uri=None, assigned_to=None,
                       status=None, reminder_date=None):
        """Procedure to update a review."""

        query        = self.__query_from_template ("update_review", {
            "review_uri":            review_uri,
            "dataset_uri":           dataset_uri,
            "assigned_to":           assigned_to,
            "status":                status,
            "reminder_date":         reminder_date
        })

        self.cache.invalidate_by_prefix ("reviews")
        return self.__run_query (query)

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

    def account_quota (self, email, domain):
        """Return the account's quota in bytes."""

        account_quota = self.account_quotas.get (email)
        group_quota   = self.group_quotas.get (domain)

        if account_quota:
            return account_quota

        if group_quota:
            return group_quota

        return self.default_quota

    def __account_with_privileges_and_quotas (self, account):
        """Returns an account record with privileges and quotas."""

        try:
            privileges = self.privileges[account["email"]]
            domain     = conv.value_or (account, "domain", "")
            quota      = self.account_quota (account["email"], domain)
            account    = { **account, **privileges, "quota": quota }
        except (TypeError, KeyError):
            pass

        return account

    def account_by_session_token (self, session_token):
        """Returns an account record or None."""

        query = self.__query_from_template ("account_by_session_token", {
            "token":       session_token
        })

        results = self.__run_query (query)
        if results:
            return self.__account_with_privileges_and_quotas (results[0])

        return None

    def accounts (self, account_uuid=None, order=None, order_direction=None,
                  limit=None, offset=None, is_active=None, email=None,
                  id_lte=None, id_gte=None, institution_user_id=None):
        """Returns accounts."""

        query = self.__query_from_template ("accounts", {
            "account_uuid": account_uuid,
            "is_active": is_active,
            "email": rdf.escape_string_value(email),
            "institution_user_id": rdf.escape_string_value (institution_user_id),
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
            "email":  email
        })

        results = self.__run_query (query)
        if results:
            return self.__account_with_privileges_and_quotas (results[0])

        return None

    def initialize_privileged_accounts (self):
        """Ensures privileged accounts are present in the database."""

        privileged_accounts = list(self.privileges.keys())
        for email in privileged_accounts:
            account = self.account_by_email (email)
            if account is not None:
                logging.info ("Account for %s already exists.", email)
                return None

            account_uuid = self.insert_account (email=email)
            if not account_uuid:
                logging.error ("Creating account for %s failed.", email)
                return None

            logging.info ("Created account for %s.", email)

            orcid = self.privileges[email]["orcid"]
            if orcid is None:
                return None

            author_uuid = self.insert_author (
                email        = email,
                account_uuid = account_uuid,
                orcid_id     = orcid)
            if not author_uuid:
                logging.warning ("Failed to link author to account for %s.", email)
                return None

            logging.info ("Linked account of %s to ORCID: %s.", email, orcid)
            return None

    def insert_session (self, account_uuid, name=None, token=None, editable=False):
        """Procedure to add a session token for an account_uuid."""

        if account_uuid is None:
            return None, None

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

        if self.add_triples_from_graph (graph):
            return token, rdf.uri_to_uuid (link_uri)

        return None, None

    def update_session (self, account_uuid, session_uuid, name):
        """Procedure to edit a session."""

        query = self.__query_from_template ("update_session", {
            "account_uuid":  account_uuid,
            "session_uuid":  session_uuid,
            "name":          name
        })

        return self.__run_query (query)

    def delete_all_sessions (self):
        """Procedure to delete all sessions."""

        query = self.__query_from_template ("delete_sessions")
        return self.__run_query (query)

    def delete_session_by_uuid (self, account_uuid, session_uuid):
        """Procedure to remove a session from the state graph."""

        query   = self.__query_from_template ("delete_session_by_uuid", {
            "session_uuid":  session_uuid,
            "account_uuid":  account_uuid
        })

        return self.__run_query (query)

    def delete_session (self, token):
        """Procedure to remove a session from the state graph."""

        if token is None:
            return True

        query   = self.__query_from_template ("delete_session", {
            "token":       token
        })

        return self.__run_query(query)

    def sessions (self, account_uuid, session_uuid=None):
        """Returns the sessions for an account."""

        query = self.__query_from_template ("account_sessions", {
            "account_uuid":  account_uuid,
            "session_uuid":  session_uuid
        })

        return self.__run_query (query)

    def __may_execute_role (self, session_token, task):
        """Returns True when the sessions' account may perform 'task'."""
        account = self.account_by_session_token (session_token)
        try:
            return account[f"may_{task}"]
        except (KeyError, TypeError):
            pass

        return False

    def may_review (self, session_token):
        """Returns True when the session's account is a reviewer."""
        return self.__may_execute_role (session_token, "review")

    def may_administer (self, session_token):
        """Returns True when the session's account is an administrator."""
        return self.__may_execute_role (session_token, "administer")

    def may_impersonate (self, session_token):
        """Returns True when the session's account may impersonate other accounts."""
        return self.__may_execute_role (session_token, "impersonate")

    def is_depositor (self, session_token):
        """Returns True when the account linked to the session is a depositor, False otherwise"""
        account = self.account_by_session_token (session_token)
        return account is not None

    def is_logged_in (self, session_token):
        """Returns True when the session_token is valid, False otherwise."""
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

        logging.error ("Inserting triples from a graph failed.")
        self.__log_query (query)

        return False
