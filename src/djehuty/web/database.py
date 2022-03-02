"""
This module provides the communication with the SPARQL endpoint to provide
data for the API server.
"""

import secrets
import os.path
import logging
from datetime import datetime
from urllib.error import URLError
from SPARQLWrapper import SPARQLWrapper, JSON, SPARQLExceptions
from rdflib import Graph, Literal, RDF, XSD
from jinja2 import Environment, FileSystemLoader
from djehuty.web import cache
from djehuty.utils import counters
from djehuty.utils import rdf
from djehuty.utils import convenience as conv

class UnknownDatabaseState(Exception):
    """Raised when the database is not queryable."""

class EmptyDatabase(Exception):
    """Raised when the database is empty."""

class SparqlInterface:
    """This class reads and writes data from a SPARQL endpoint."""

    def __init__ (self):

        self.ids         = counters.IdGenerator()
        self.storage     = None
        self.endpoint    = "http://127.0.0.1:8890/sparql"
        self.state_graph = "https://data.4tu.nl/portal/self-test"
        self.privileges  = {}
        self.cache       = cache.CacheLayer(None)
        self.jinja       = Environment(loader = FileSystemLoader(
                            os.path.join(os.path.dirname(__file__),
                                         "resources/sparql_templates")),
                                       # Auto-escape is set to False because
                                       # we put quotes around strings in
                                       # filters.
                                       autoescape=False)

        self.sparql      = SPARQLWrapper(self.endpoint)
        self.sparql.setReturnFormat(JSON)

    def load_state (self):
        """Procedure to load the database state."""

        # Set the iterators to continue where we left off last time the
        # program was run.
        try:
            for item in self.ids.keys():
                self.ids.set_id (self.__highest_id (item_type=item), item)
                if self.ids.current_id (item) is None:
                    raise UnknownDatabaseState

        except EmptyDatabase:
            logging.warning ("It looks like the database is empty.")

        for item in self.ids.keys():
            logging.info ("%s enumerator set to %d", item, self.ids.current_id (item))

    ## ------------------------------------------------------------------------
    ## Private methods
    ## ------------------------------------------------------------------------

    def __normalize_binding (self, record):
        for item in record:
            if record[item]["type"] == "typed-literal":
                datatype = record[item]["datatype"]
                if datatype == "http://www.w3.org/2001/XMLSchema#integer":
                    record[item] = int(record[item]["value"])
                elif datatype == "http://www.w3.org/2001/XMLSchema#decimal":
                    record[item] = int(record[item]["value"])
                elif datatype == "http://www.w3.org/2001/XMLSchema#boolean":
                    record[item] = bool(int(record[item]["value"]))
                elif datatype == "http://www.w3.org/2001/XMLSchema#string":
                    if record[item]["value"] == "NULL":
                        record[item] = None
                    else:
                        record[item] = record[item]["value"]
            elif record[item]["type"] == "literal":
                logging.info("Literal: %s", record[item]['value'])
                return record[item]["value"]
            else:
                logging.info("Not a typed-literal: %s", record[item]['type'])
        return record

    def __query_from_template (self, name, args):
        template = self.jinja.get_template (f"{name}.sparql")
        return template.render (args)

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
                self.cache.cache_value (prefix, cache_key, results)

        except URLError:
            logging.error("Connection to the SPARQL endpoint seems down.")
        except SPARQLExceptions.QueryBadFormed as error:
            logging.error("Badly formed SPARQL query:")
            logging.error("Query:\n---\n%s\n---", query)
        except Exception as error:
            logging.error("SPARQL query failed.")
            logging.error("Exception: %s", error)
            logging.error("Query:\n---\n%s\n---", query)

        return results

    def __highest_id (self, item_type="article"):
        """Return the highest numeric ID for ITEM_TYPE."""
        prefix = conv.to_camel(item_type)
        query = self.__query_from_template ("highest_id", {
            "state_graph": self.state_graph,
            "item_type":   prefix
        })

        try:
            results = self.__run_query (query)
            return results[0]["id"]
        except IndexError:
            return 0
        except KeyError:
            return None

    def __insert_query_for_graph (self, graph):
        body  = graph.serialize(format="ntriples")
        query = "INSERT { GRAPH <%s> { %s } }" % (
            self.state_graph,
            body.decode('utf-8') if isinstance(body, bytes) else body
        )

        return query

    ## ------------------------------------------------------------------------
    ## GET METHODS
    ## ------------------------------------------------------------------------

    def article_storage_used (self, article_id):
        """Returns the number of bytes used by an article."""

        query = self.__query_from_template ("article_storage_used", {
            "state_graph": self.state_graph,
            "article_id":  article_id
        })

        results = self.__run_query (query, query, f"{article_id}_article")
        try:
            return results[0]["bytes"]
        except IndexError:
            logging.error ("Article %s looks to be empty.", article_id)
            return 0
        except KeyError:
            logging.error ("Failed to retrieve used storage for article %s", article_id)

        return None

    def article_versions (self, limit=1000, offset=0, order=None,
                          order_direction=None, article_id=None):
        """Procedure to retrieve the versions of an article."""
        filters = ""
        if article_id is not None:
            filters += rdf.sparql_filter ("id", article_id)

        query = self.__query_from_template ("article_versions", {
            "state_graph": self.state_graph,
            "filters":     filters
        })
        query += rdf.sparql_suffix (order, order_direction, limit, offset)

        return self.__run_query (query)

    def articles (self, limit=None, offset=None, order=None,
                  order_direction=None, institution=None,
                  published_since=None, modified_since=None,
                  group=None, group_ids=None, resource_doi=None, item_type=None,
                  doi=None, handle=None, account_id=None,
                  search_for=None, article_id=None,
                  collection_id=None, version=None, category_ids=None,
                  return_count=False, is_public=None):
        """Procedure to retrieve articles."""

        filters  = rdf.sparql_filter ("institution_id", institution)
        filters += rdf.sparql_filter ("group_id",       group)
        filters += rdf.sparql_filter ("defined_type",   item_type)
        filters += rdf.sparql_filter ("id",             article_id)
        filters += rdf.sparql_filter ("version",        version)
        filters += rdf.sparql_filter ("resource_doi",   resource_doi, escape=True)
        filters += rdf.sparql_filter ("doi",            doi,          escape=True)
        filters += rdf.sparql_filter ("handle",         handle,       escape=True)
        filters += rdf.sparql_filter ("title",          search_for,   escape=True)
        filters += rdf.sparql_filter ("resource_title", search_for,   escape=True)
        filters += rdf.sparql_filter ("description",    search_for,   escape=True)
        filters += rdf.sparql_filter ("citation",       search_for,   escape=True)

        if group_ids is not None:
            filters += f"FILTER ((?group_id) IN ({','.join(map(str, group_ids))}))\n"

        if category_ids is not None:
            filters += f"FILTER (?category_id={category_ids[0]} OR ?parent_category_id={category_ids[0]}"
            for category_id in category_ids[1:]:
                filters += f" OR ?category_id={category_id} OR ?parent_category_id={category_ids[0]}"
            filters += ")\n"

        if published_since is not None:
            filters += rdf.sparql_bound_filter ("published_date")
            filters += "FILTER (STR(?published_date) != \"NULL\")\n"
            filters += f"FILTER (STR(?published_date) > \"{published_since}\")\n"

        if modified_since is not None:
            filters += rdf.sparql_bound_filter ("modified_date")
            filters += "FILTER (STR(?modified_date) != \"NULL\")\n"
            filters += f"FILTER (STR(?modified_date) > \"{modified_since}\")\n"

        if account_id is None:
            filters += rdf.sparql_filter ("is_public", 1)
        elif is_public is not None:
            filters += rdf.sparql_filter ("is_public", int(is_public))

        query = self.__query_from_template ("articles", {
            "state_graph":   self.state_graph,
            "collection_id": collection_id,
            "category_ids":  category_ids,
            "account_id":    account_id,
            "filters":       filters,
            "return_count":  return_count
        })

        # Setting the default value for 'limit' to 10 makes passing
        # parameters from HTTP requests cumbersome. Therefore, we
        # set the default again here.
        if limit is None:
            limit = 10

        if not return_count:
            query += rdf.sparql_suffix (order, order_direction, limit, offset)

        return self.__run_query (query, query, "article")

    def repository_statistics (self):
        """Procedure to retrieve repository-wide statistics."""

        query = self.__query_from_template ("repository_statistics", {
            "state_graph":   self.state_graph,
        })

        query2 = self.__query_from_template ("repository_statistics_files", {
            "state_graph":   self.state_graph,
        })

        row = None
        try:
            results  = self.__run_query (query, query, "statistics")
            results2 = self.__run_query (query2, query2, "statistics")
            row = { **results[0], **results2[0] }
        except IndexError:
            return None
        except KeyError:
            return None

        return row

    def article_statistics (self, item_type="downloads",
                                  order="downloads",
                                  order_direction="desc",
                                  group_ids=None,
                                  category_ids=None,
                                  limit=10,
                                  offset=0):
        """Procedure to retrieve article statistics."""

        prefix  = item_type.capitalize()
        filters = ""

        if category_ids is not None:
            filters += f"FILTER (?category_id={category_ids[0]}"
            for category_id in category_ids[1:]:
                filters += f" OR ?category_id={category_id}"
            filters += ")\n"

        if group_ids is not None:
            filters += f"FILTER ((?group_id) IN ({','.join(map(str, group_ids))}))\n"


        query   = self.__query_from_template ("article_statistics", {
            "state_graph":   self.state_graph,
            "category_ids":  category_ids,
            "item_type":     item_type,
            "prefix":        prefix,
            "filters":       filters
        })

        query += rdf.sparql_suffix (order, order_direction, limit, offset)
        return self.__run_query (query, query, "statistics")

    def article_statistics_timeline (self,
                                     article_id=None,
                                     item_type="downloads",
                                     order="downloads",
                                     order_direction="desc",
                                     category_ids=None,
                                     limit=10,
                                     offset=0,
                                     aggregation_type="day"):
        """Procedure to retrieve article statistics per date."""

        item_class  = item_type.capitalize()
        filters = ""

        if article_id is not None:
            filters += rdf.sparql_filter("article_id", article_id)

        if category_ids is not None:
            filters += f"FILTER (?category_id={category_ids[0]}"
            for category_id in category_ids[1:]:
                filters += f" OR ?category_id={category_id}"
            filters += ")\n"

        query   = self.__query_from_template ("article_statistics_timeline", {
            "state_graph":   self.state_graph,
            "category_ids":  category_ids,
            "item_type":     item_type,
            "item_class":    item_class,
            "filters":       filters
        })

        order = "article_id" if order is None else order
        query += rdf.sparql_suffix (order, order_direction, limit, offset)
        return self.__run_query (query, query, "statistics")

    def authors (self, first_name=None, full_name=None, group_id=None,
                 author_id=None, institution_id=None, is_active=None,
                 is_public=None, job_title=None, last_name=None,
                 orcid_id=None, url_name=None, limit=10, order="full_name",
                 order_direction="asc", item_id=None, search_for=None,
                 account_id=None, item_type="article"):
        """Procedure to retrieve authors of an article."""

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
            filters += (f"FILTER (CONTAINS(STR(?first_name), \"{search_for}\") OR\n"
                        f"        CONTAINS(STR(?last_name),  \"{search_for}\") OR\n"
                        f"        CONTAINS(STR(?full_name),  \"{search_for}\") OR\n"
                        f"        CONTAINS(STR(?orcid_id),   \"{search_for}\"))")

        query = self.__query_from_template ("authors", {
            "state_graph": self.state_graph,
            "item_type":   item_type,
            "prefix":      prefix,
            "item_id":     item_id,
            "account_id":  account_id,
            "filters":     filters
        })
        query += rdf.sparql_suffix (order, order_direction, limit, None)

        return self.__run_query(query)

    def file_by_id (self, file_id, account_id):
        """Procedure to get a file by its identifier."""

        if file_id is None or account_id is None:
            return None

        query = self.__query_from_template ("file", {
            "state_graph": self.state_graph,
            "account_id":  account_id,
            "file_id":     file_id
        })

        return self.__run_query(query)

    def article_files (self, name=None, size=None, is_link_only=None,
                       file_id=None, download_url=None, supplied_md5=None,
                       computed_md5=None, viewer_type=None, preview_state=None,
                       status=None, upload_url=None, upload_token=None,
                       order=None, order_direction=None, limit=10,
                       article_id=None, account_id=None):
        """Procedure to retrieve files of an article."""

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

        query = self.__query_from_template ("article_files", {
            "state_graph": self.state_graph,
            "article_id":  article_id,
            "account_id":  account_id,
            "filters":     filters
        })

        query += rdf.sparql_suffix (order, order_direction, limit, None)

        return self.__run_query(query)

    def article_references (self, reference_id=None, url=None, order=None,
                            order_direction=None, limit=10,
                            article_id=None, account_id=None):
        """Procedure to retrieve article references."""

        filters  = rdf.sparql_filter ("id",            reference_id)
        filters += rdf.sparql_filter ("url",           url,  escape=True)

        query = self.__query_from_template ("article_references", {
            "state_graph": self.state_graph,
            "article_id":  article_id,
            "account_id":  account_id,
            "filters":     filters
        })

        query += rdf.sparql_suffix (order, order_direction, limit, None)

        return self.__run_query(query)

    def delete_article_reference (self, article_id, account_id, url=None):
        """Procedure to delete an article reference."""

        query = self.__query_from_template ("delete_article_reference", {
            "state_graph": self.state_graph,
            "account_id":  account_id,
            "article_id":  article_id,
            "url":         url.replace('"', '\\"')
        })

        return self.__run_query(query)

    def custom_fields (self, name=None, value=None, default_value=None,
                       field_id=None, placeholder=None, max_length=None,
                       min_length=None, field_type=None, is_multiple=None,
                       is_mandatory=None, order="name", order_direction=None,
                       limit=10, item_id=None, item_type="article"):

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
            "state_graph": self.state_graph,
            "item_id":     item_id,
            "item_type":   item_type,
            "prefix":      prefix,
            "filters":     filters
        })
        query += rdf.sparql_suffix (order, order_direction, limit, None)

        return self.__run_query(query)

    def article_embargo_options (self, ip_name=None, embargo_type=None,
                                 order=None, order_direction=None,
                                 limit=10, article_id=None):
        """Procedure to retrieve embargo options of an article."""

        filters  = rdf.sparql_filter ("article_id",   article_id)
        filters += rdf.sparql_filter ("ip_name",      ip_name,      escape=True)
        filters += rdf.sparql_filter ("embargo_type", embargo_type, escape=True)

        query = self.__query_from_template ("article_embargo_options", {
            "state_graph": self.state_graph,
            "filters":     filters
        })
        query += rdf.sparql_suffix (order, order_direction, limit, None)

        return self.__run_query(query)

    def tags (self, order=None, order_direction=None, limit=10, item_id=None, item_type="article"):

        prefix  = item_type.capitalize()
        filters = rdf.sparql_filter (f"{item_type}_id", item_id)
        query   = self.__query_from_template ("tags", {
            "state_graph": self.state_graph,
            "prefix":      prefix,
            "item_type":   item_type,
            "filters":     filters
        })
        query += rdf.sparql_suffix (order, order_direction, limit, None)

        return self.__run_query(query)

    def categories (self, title=None, order=None, order_direction=None,
                    limit=10, item_id=None, account_id=None,
                    item_type="article"):
        """Procedure to retrieve categories of an article."""

        prefix  = item_type.capitalize()
        filters = rdf.sparql_filter ("title", title, escape=True)
        query   = self.__query_from_template ("categories", {
            "state_graph": self.state_graph,
            "prefix":      prefix,
            "item_type":   item_type,
            "item_id":     item_id,
            "account_id":  account_id,
            "filters":     filters
        })
        query += rdf.sparql_suffix (order, order_direction, limit, None)

        return self.__run_query(query)

    def private_links (self, item_id=None, item_type="article", account_id=None, id_string=None):

        prefix  = item_type.capitalize()
        query   = self.__query_from_template ("private_links", {
            "state_graph": self.state_graph,
            "prefix":      prefix,
            "id_string":   id_string,
            "item_type":   item_type,
            "item_id":     item_id,
            "account_id":  account_id,
        })

        return self.__run_query(query)

    def licenses (self):
        query = self.__query_from_template ("licenses", {
            "state_graph": self.state_graph
        })

        return self.__run_query(query)

    ## ------------------------------------------------------------------------
    ## COLLECTIONS
    ## ------------------------------------------------------------------------

    def collection_versions (self, limit=1000, offset=0, order=None,
                             order_direction=None, collection_id=None):
        """Procedure to retrieve the versions of an collection."""
        filters = ""
        if collection_id is not None:
            filters += rdf.sparql_filter ("id", collection_id)

        query = self.__query_from_template ("collection_versions", {
            "state_graph": self.state_graph,
            "filters":     filters
        })
        query += rdf.sparql_suffix (order, order_direction, limit, offset)
        return self.__run_query (query)

    ## This procedure exists because the 'articles' procedure will only
    ## count articles that are either public, or were published using the
    ## same account_id as the collection.
    ##
    ## So to get the actual count, this separate procedure exists.
    def collections_article_count (self, collection_id):
        """Procedure to count the articles in a collection."""

        if collection_id is None:
            return 0

        query = self.__query_from_template ("collection_articles_count", {
            "state_graph":    self.state_graph,
            "collection_id":  collection_id
        })
        results = self.__run_query (query)

        try:
            return results[0]["articles"]
        except KeyError:
            return 0

    def collections (self, limit=10, offset=None, order=None,
                     order_direction=None, institution=None,
                     published_since=None, modified_since=None, group=None,
                     resource_doi=None, resource_id=None, doi=None, handle=None,
                     account_id=None, search_for=None, collection_id=None,
                     version=None):
        """Procedure to retrieve collections."""

        filters  = rdf.sparql_filter ("institution_id", institution)
        filters += rdf.sparql_filter ("group_id",       group)
        filters += rdf.sparql_filter ("id",             collection_id)
        filters += rdf.sparql_filter ("version",        version)
        filters += rdf.sparql_filter ("resource_doi",   resource_doi, escape=True)
        filters += rdf.sparql_filter ("resource_id",    resource_id,  escape=True)
        filters += rdf.sparql_filter ("doi",            doi,          escape=True)
        filters += rdf.sparql_filter ("handle",         handle,       escape=True)
        filters += rdf.sparql_filter ("title",          search_for,   escape=True)
        filters += rdf.sparql_filter ("resource_title", search_for,   escape=True)
        filters += rdf.sparql_filter ("description",    search_for,   escape=True)
        filters += rdf.sparql_filter ("citation",       search_for,   escape=True)

        if published_since is not None:
            filters += rdf.sparql_bound_filter ("published_date")
            filters += "FILTER (STR(?published_date) != \"NULL\")\n"
            filters += f"FILTER (STR(?published_date) > \"{published_since}\")\n"

        if modified_since is not None:
            filters += rdf.sparql_bound_filter ("modified_date")
            filters += "FILTER (STR(?modified_date) != \"NULL\")\n"
            filters += f"FILTER (STR(?modified_date) > \"{modified_since}\")\n"

        if account_id is None:
            filters += rdf.sparql_filter ("is_public", 1)
        else:
            filters += rdf.sparql_filter ("account_id", account_id)

        query   = self.__query_from_template ("collections", {
            "state_graph": self.state_graph,
            "filters":     filters
        })
        query += rdf.sparql_suffix (order, order_direction, limit, offset)

        return self.__run_query(query)

    def fundings (self, title=None, order=None, order_direction=None,
                  limit=10, item_id=None, account_id=None, item_type="article"):
        """Procedure to retrieve funding information."""

        filters = rdf.sparql_filter ("title", title, escape=True)
        query   = self.__query_from_template ("funding", {
            "state_graph": self.state_graph,
            "prefix":      item_type.capitalize(),
            "item_type":   item_type,
            "item_id":     item_id,
            "account_id":  account_id,
            "filters":     filters
        })
        query += rdf.sparql_suffix (order, order_direction, limit, None)

        return self.__run_query(query)

    def references (self, order=None, order_direction=None, limit=10,
                    item_id=None, account_id=None, item_type="article"):

        query   = self.__query_from_template ("references", {
            "state_graph": self.state_graph,
            "prefix":      item_type.capitalize(),
            "item_type":   item_type,
            "item_id":     item_id,
            "account_id":  account_id,
            "filters":     None
        })
        query += rdf.sparql_suffix (order, order_direction, limit, None)

        return self.__run_query(query)

    ## ------------------------------------------------------------------------
    ## INSERT METHODS
    ## ------------------------------------------------------------------------

    def insert_article (self, title,
                        account_id,
                        article_id=None,
                        description=None,
                        keywords=None,
                        defined_type=None,
                        funding=None,
                        license_id=None,
                        doi=None,
                        handle=None,
                        resource_doi=None,
                        resource_title=None,
                        first_online=None,
                        publisher_publication=None,
                        publisher_acceptance=None,
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
                        embargo_options=None):
        """Procedure to insert an article to the state graph."""

        funding_list    = [] if funding_list    is None else funding_list
        tags            = [] if tags            is None else tags
        references      = [] if references      is None else references
        categories      = [] if categories      is None else categories
        authors         = [] if authors         is None else authors
        custom_fields   = [] if custom_fields   is None else custom_fields
        private_links   = [] if private_links   is None else private_links
        files           = [] if files           is None else files
        embargo_options = [] if embargo_options is None else embargo_options

        graph = Graph()

        if article_id is None:
            article_id = self.ids.next_id("article")

        article_uri = rdf.ROW[f"article_{article_id}"]

        ## TIMELINE
        ## --------------------------------------------------------------------
        timeline_id = self.insert_timeline (
            revision              = revision,
            first_online          = first_online,
            publisher_publication = publisher_publication,
            publisher_acceptance  = publisher_acceptance,
            posted                = posted,
            submission            = submission
        )

        rdf.add (graph, article_uri, rdf.COL["timeline_id"], timeline_id)

        ## REFERENCES
        ## --------------------------------------------------------------------
        for url in references:
            self.insert_reference (url, item_id=article_id, item_type="article")

        ## TAGS
        ## --------------------------------------------------------------------
        for tag in tags:
            self.insert_tag (tag, item_id=article_id, item_type="article")

        ## FUNDING
        ## --------------------------------------------------------------------
        for fund in funding_list:
            self.insert_funding (
                title           = conv.value_or_none (fund, "title"),
                grant_code      = conv.value_or_none (fund, "grant_code"),
                funder_name     = conv.value_or_none (fund, "funder_name"),
                is_user_defined = conv.value_or_none (fund, "is_user_defined"),
                url             = conv.value_or_none (fund, "url"),
                item_id         = article_id,
                item_type       = "article")

        ## CATEGORIES
        ## --------------------------------------------------------------------
        for category_id in categories:
            self.insert_article_category (article_id, category_id)

        ## EMBARGOS
        ## --------------------------------------------------------------------
        for embargo in embargo_options:
            self.insert_embargo (
                embargo_id   = conv.value_or_none (embargo, "id"),
                article_id   = article_id,
                embargo_type = conv.value_or_none (embargo, "type"),
                ip_name      = conv.value_or_none (embargo, "ip_name"))

        ## AUTHORS
        ## --------------------------------------------------------------------
        for author in authors:
            author_id = self.insert_author (
                author_id      = conv.value_or_none (author, "id"),
                is_active      = conv.value_or_none (author, "is_active"),
                first_name     = conv.value_or_none (author, "first_name"),
                last_name      = conv.value_or_none (author, "last_name"),
                full_name      = conv.value_or_none (author, "full_name"),
                institution_id = conv.value_or_none (author, "institution_id"),
                job_title      = conv.value_or_none (author, "job_title"),
                is_public      = conv.value_or_none (author, "is_public"),
                url_name       = conv.value_or_none (author, "url_name"),
                orcid_id       = conv.value_or_none (author, "orcid_id"))
            self.insert_article_author (article_id, author_id)

        ## FILES
        ## --------------------------------------------------------------------
        for file_data in files:
            self.insert_file (
                file_id       = conv.value_or_none (file_data, "id"),
                name          = conv.value_or_none (file_data, "name"),
                size          = conv.value_or_none (file_data, "size"),
                is_link_only  = conv.value_or_none (file_data, "is_link_only"),
                download_url  = conv.value_or_none (file_data, "download_url"),
                supplied_md5  = conv.value_or_none (file_data, "supplied_md5"),
                computed_md5  = conv.value_or_none (file_data, "computed_md5"),
                viewer_type   = conv.value_or_none (file_data, "viewer_type"),
                preview_state = conv.value_or_none (file_data, "preview_state"),
                status        = conv.value_or_none (file_data, "status"),
                upload_url    = conv.value_or_none (file_data, "upload_url"),
                upload_token  = conv.value_or_none (file_data, "upload_token"),
                article_id    = article_id)

        ## CUSTOM FIELDS
        ## --------------------------------------------------------------------
        for field in custom_fields:
            self.insert_custom_field (
                name          = conv.value_or_none (field, "name"),
                value         = conv.value_or_none (field, "value"),
                default_value = conv.value_or_none (field, "default_value"),
                max_length    = conv.value_or_none (field, "max_length"),
                min_length    = conv.value_or_none (field, "min_length"),
                field_type    = conv.value_or_none (field, "field_type"),
                is_mandatory  = conv.value_or_none (field, "is_mandatory"),
                placeholder   = conv.value_or_none (field, "placeholder"),
                is_multiple   = conv.value_or_none (field, "is_multiple"),
                item_id       = article_id,
                item_type     = "article")

        ## PRIVATE LINKS
        ## --------------------------------------------------------------------
        for link in private_links:
            self.insert_private_link (
                item_id          = article_id,
                item_type        = "article",
                private_link_id  = conv.value_or_none (link, "id"),
                is_active        = conv.value_or_none (link, "is_active"),
                expires_date     = conv.value_or_none (link, "expires_date"))

        ## TOPLEVEL FIELDS
        ## --------------------------------------------------------------------

        graph.add ((article_uri, RDF.type,         rdf.SG["Article"]))
        graph.add ((article_uri, rdf.COL["id"],    Literal(article_id)))
        graph.add ((article_uri, rdf.COL["article_id"], Literal(article_id)))
        graph.add ((article_uri, rdf.COL["title"], Literal(title, datatype=XSD.string)))

        rdf.add (graph, article_uri, rdf.COL["account_id"],     account_id)
        rdf.add (graph, article_uri, rdf.COL["description"],    description,    XSD.string)
        rdf.add (graph, article_uri, rdf.COL["defined_type"],   defined_type,   XSD.string)
        rdf.add (graph, article_uri, rdf.COL["funding"],        funding,        XSD.string)
        rdf.add (graph, article_uri, rdf.COL["license_id"],     license_id)
        rdf.add (graph, article_uri, rdf.COL["doi"],            doi,            XSD.string)
        rdf.add (graph, article_uri, rdf.COL["handle"],         handle,         XSD.string)
        rdf.add (graph, article_uri, rdf.COL["resource_doi"],   resource_doi,   XSD.string)
        rdf.add (graph, article_uri, rdf.COL["resource_title"], resource_title, XSD.string)
        rdf.add (graph, article_uri, rdf.COL["group_id"],       group_id)

        current_time = datetime.strftime (datetime.now(), "%Y-%m-%d %H:%M:%S")
        rdf.add (graph, article_uri, rdf.COL["created_date"],   current_time, XSD.string)
        rdf.add (graph, article_uri, rdf.COL["modified_date"],  current_time, XSD.string)
        rdf.add (graph, article_uri, rdf.COL["published_date"], "NULL", XSD.string)
        rdf.add (graph, article_uri, rdf.COL["is_public"],      0)
        rdf.add (graph, article_uri, rdf.COL["is_active"],      1)

        query = self.__insert_query_for_graph (graph)
        if self.__run_query(query):
            logging.info ("Inserted article %d", article_id)
            self.cache.invalidate_by_prefix ("article")
            return article_id

        return None

    def insert_account (self, account_id=None, active=None, email=None,
                        first_name=None, last_name=None, institution_user_id=None,
                        institution_id=None, pending_quota_request=None,
                        used_quota_public=None, used_quota_private=None,
                        used_quota=None, maximum_file_size=None, quota=None,
                        modified_date=None, created_date=None):
        """Procedure to add an account to the state graph."""

        graph = Graph()

        if account_id is None:
            account_id = self.ids.next_id("account")

        account_uri = rdf.ROW[f"account_{account_id}"]

        graph.add ((account_uri, RDF.type,      rdf.SG["Account"]))
        graph.add ((account_uri, rdf.COL["id"], Literal(account_id)))

        rdf.add (graph, account_uri, rdf.COL["active"],                active)
        rdf.add (graph, account_uri, rdf.COL["email"],                 email,                 XSD.string)
        rdf.add (graph, account_uri, rdf.COL["first_name"],            first_name,            XSD.string)
        rdf.add (graph, account_uri, rdf.COL["last_name"],             last_name,             XSD.string)
        rdf.add (graph, account_uri, rdf.COL["institution_user_id"],   institution_user_id)
        rdf.add (graph, account_uri, rdf.COL["institution_id"],        institution_id)
        rdf.add (graph, account_uri, rdf.COL["pending_quota_request"], pending_quota_request)
        rdf.add (graph, account_uri, rdf.COL["used_quota_public"],     used_quota_public)
        rdf.add (graph, account_uri, rdf.COL["used_quota_private"],    used_quota_private)
        rdf.add (graph, account_uri, rdf.COL["used_quota"],            used_quota)
        rdf.add (graph, account_uri, rdf.COL["maximum_file_size"],     maximum_file_size)
        rdf.add (graph, account_uri, rdf.COL["quota"],                 quota)
        rdf.add (graph, account_uri, rdf.COL["modified_date"],         modified_date,         XSD.string)
        rdf.add (graph, account_uri, rdf.COL["created_date"],          created_date,          XSD.string)

        query = self.__insert_query_for_graph (graph)
        if self.__run_query(query):
            return account_id

        return None

    def insert_institution (self, name, institution_id=None):
        """Procedure to add an institution to the state graph."""

        graph = Graph()

        if institution_id is None:
            institution_id = self.ids.next_id("institution")

        institution_uri = rdf.ROW[f"institution_{institution_id}"]

        graph.add ((institution_uri, RDF.type,      rdf.SG["Institution"]))
        graph.add ((institution_uri, rdf.COL["id"], Literal(institution_id)))

        rdf.add (graph, institution_uri, rdf.COL["name"], name, XSD.string)

        query = self.__insert_query_for_graph (graph)
        if self.__run_query(query):
            return institution_id

        return None

    def insert_author (self, author_id=None, is_active=None, first_name=None,
                       last_name=None, full_name=None, institution_id=None,
                       job_title=None, is_public=None, url_name=None,
                       orcid_id=None, email=None):
        """Procedure to add an author to the state graph."""

        graph = Graph()

        if author_id is None:
            author_id = self.ids.next_id("author")

        author_uri = rdf.ROW[f"author_{author_id}"]

        graph.add ((author_uri, RDF.type,      rdf.SG["Author"]))
        graph.add ((author_uri, rdf.COL["id"], Literal(author_id)))

        rdf.add (graph, author_uri, rdf.COL["institution_id"], institution_id)
        rdf.add (graph, author_uri, rdf.COL["is_active"],      is_active)
        rdf.add (graph, author_uri, rdf.COL["is_public"],      is_public)
        rdf.add (graph, author_uri, rdf.COL["first_name"],     first_name,     XSD.string)
        rdf.add (graph, author_uri, rdf.COL["last_name"],      last_name,      XSD.string)
        rdf.add (graph, author_uri, rdf.COL["full_name"],      full_name,      XSD.string)
        rdf.add (graph, author_uri, rdf.COL["job_title"],      job_title,      XSD.string)
        rdf.add (graph, author_uri, rdf.COL["url_name"],       url_name,       XSD.string)
        rdf.add (graph, author_uri, rdf.COL["orcid_id"],       orcid_id,       XSD.string)
        rdf.add (graph, author_uri, rdf.COL["email"],          email,          XSD.string)

        query = self.__insert_query_for_graph (graph)
        if self.__run_query(query):
            return author_id

        return None

    def delete_authors_for_item (self, item_id, account_id, author_id=None, item_type="article"):
        """Procedure to delete all authors related to an article or collection."""

        query = self.__query_from_template ("delete_authors_for_item", {
            "state_graph": self.state_graph,
            "item_id":     item_id,
            "item_type":   item_type,
            "prefix":      item_type.capitalize(),
            "account_id":  account_id,
            "author_id":   author_id
        })

        return self.__run_query(query)

    def delete_authors_for_article (self, article_id, account_id, author_id=None):
        """Procedure to delete all authors related to an article."""
        return self.delete_authors_for_item (article_id, account_id, author_id, "article")

    def delete_authors_for_collection (self, collection_id, account_id, author_id=None):
        """Procedure to delete all authors related to a collection."""
        return self.delete_authors_for_item (collection_id, account_id, author_id, "collection")

    def insert_timeline (self, revision=None, first_online=None,
                         publisher_publication=None, publisher_acceptance=None,
                         posted=None, submission=None):
        """Procedure to add a timeline to the state graph."""

        graph        = Graph()
        timeline_id  = self.ids.next_id("timeline")
        timeline_uri = rdf.ROW[f"timeline_{timeline_id}"]

        graph.add ((timeline_uri, RDF.type,      rdf.SG["Timeline"]))
        graph.add ((timeline_uri, rdf.COL["id"], Literal(timeline_id)))

        rdf.add (graph, timeline_uri, rdf.COL["revision"],             revision,              XSD.string)
        rdf.add (graph, timeline_uri, rdf.COL["firstOnline"],          first_online,          XSD.string)
        rdf.add (graph, timeline_uri, rdf.COL["publisherPublication"], publisher_publication, XSD.string)
        rdf.add (graph, timeline_uri, rdf.COL["publisherAcceptance"],  publisher_acceptance,  XSD.string)
        rdf.add (graph, timeline_uri, rdf.COL["posted"],               posted,                XSD.string)
        rdf.add (graph, timeline_uri, rdf.COL["submission"],           submission,            XSD.string)

        query = self.__insert_query_for_graph (graph)
        if self.__run_query(query):
            return timeline_id

        return None

    def insert_category (self, category_id=None, title=None, parent_id=None,
                         source_id=None, taxonomy=None):
        """Procedure to add an category to the state graph."""

        graph = Graph()

        if category_id is None:
            category_id = self.ids.next_id("category")

        category_uri = rdf.ROW[f"category_{category_id}"]

        graph.add ((category_uri, RDF.type,      rdf.SG["Category"]))
        graph.add ((category_uri, rdf.COL["id"], Literal(category_id)))

        rdf.add (graph, category_uri, rdf.COL["title"], title,         XSD.string)
        rdf.add (graph, category_uri, rdf.COL["parent_id"], parent_id)
        rdf.add (graph, category_uri, rdf.COL["source_id"], source_id)
        rdf.add (graph, category_uri, rdf.COL["taxonomy"], taxonomy)

        query = self.__insert_query_for_graph (graph)
        if self.__run_query(query):
            return category_id

        return None

    def insert_item_category (self, item_id, category_id, item_type="article"):
        """Procedure to add a link between an article or collection and a category."""

        prefix   = item_type.capitalize()
        graph    = Graph()
        link_id  = self.ids.next_id(f"{item_type}_category")
        link_uri = rdf.ROW[f"{item_type}_category_link_{link_id}"]

        graph.add ((link_uri, RDF.type,                   rdf.SG[f"{prefix}Category"]))
        graph.add ((link_uri, rdf.COL["id"],              Literal(link_id, datatype=XSD.integer)))
        graph.add ((link_uri, rdf.COL["category_id"],     Literal(category_id, datatype=XSD.integer)))
        graph.add ((link_uri, rdf.COL[f"{item_type}_id"], Literal(item_id, datatype=XSD.integer)))

        query = self.__insert_query_for_graph (graph)
        if self.__run_query(query):
            return link_id

        return None

    def insert_article_category (self, article_id, category_id):
        """Procedure to add a link between an article and a category."""
        return self.insert_item_category (article_id, category_id, "article")

    def insert_collection_category (self, collection_id, category_id):
        """Procedure to add a link between a collection and a category."""
        return self.insert_item_category (collection_id, category_id, "collection")

    def insert_author_link (self, author_id, item_id, item_type="article"):
        """Procedure to add a link to an author."""

        graph = Graph()

        prefix = item_type.capitalize()
        link_id  = self.ids.next_id(f"{item_type}_author")
        link_uri = rdf.ROW[f"{item_type}_author_link_{link_id}"]

        graph.add ((link_uri, RDF.type,                   rdf.SG[f"{prefix}Author"]))
        graph.add ((link_uri, rdf.COL["id"],              Literal(link_id)))
        graph.add ((link_uri, rdf.COL["author_id"],       Literal(author_id)))
        graph.add ((link_uri, rdf.COL[f"{item_type}_id"], Literal(item_id)))

        query = self.__insert_query_for_graph (graph)
        if self.__run_query(query):
            return link_id

        return None

    def insert_article_author (self, article_id, author_id):
        """Procedure to add a link between an article and an author."""
        return self.insert_author_link (author_id, article_id, item_type="article")

    def insert_collection_author (self, collection_id, author_id):
        """Procedure to add a link between a collection and a author."""
        return self.insert_author_link (author_id, collection_id, item_type="collection")

    def insert_article_file (self, article_id, file_id):
        """Procedure to add a link between an article and a file."""

        graph = Graph()

        link_id  = self.ids.next_id("article_file")
        link_uri = rdf.ROW[f"article_file_link_{link_id}"]

        graph.add ((link_uri, RDF.type,              rdf.SG["ArticleFile"]))
        graph.add ((link_uri, rdf.COL["id"],         Literal(link_id)))
        graph.add ((link_uri, rdf.COL["file_id"],    Literal(file_id, datatype=XSD.integer)))
        graph.add ((link_uri, rdf.COL["article_id"], Literal(article_id, datatype=XSD.integer)))

        query = self.__insert_query_for_graph (graph)
        if self.__run_query(query):
            return link_id

        return None

    def delete_article_categories (self, article_id, account_id, category_id=None):
        """Procedure to delete the categories related to an article."""

        query = self.__query_from_template ("delete_article_categories", {
            "state_graph": self.state_graph,
            "article_id":  article_id,
            "account_id":  account_id,
            "category_id": category_id
        })

        return self.__run_query(query)

    def delete_file_for_article (self, article_id, account_id, file_id=None):
        """Procedure to delete a file related to an article."""

        query = self.__query_from_template ("delete_files_for_article", {
            "state_graph": self.state_graph,
            "article_id":  article_id,
            "account_id":  account_id,
            "file_id":     file_id
        })

        self.cache.invalidate_by_prefix (f"{article_id}_article")
        return self.__run_query(query)

    def insert_tag (self, tag, item_id=None, item_type=None):
        """Procedure to add an tag to the state graph."""

        prefix  = item_type.capitalize()
        graph   = Graph()
        tag_id  = self.ids.next_id("{item_type}_tag")
        tag_uri = rdf.ROW[f"{item_type}_tag_{tag_id}"]

        graph.add ((tag_uri, RDF.type,                   rdf.SG[f"{prefix}Tag"]))
        graph.add ((tag_uri, rdf.COL["id"],              Literal(tag_id)))
        graph.add ((tag_uri, rdf.COL[f"{item_type}_id"], Literal(item_id)))

        rdf.add (graph, tag_uri, rdf.COL["tag"], tag, XSD.string)

        query = self.__insert_query_for_graph (graph)
        if self.__run_query(query):
            return tag_id

        return None

    def insert_reference (self, url, item_id=None, item_type=None):
        """Procedure to add an reference to the state graph."""

        prefix        = item_type.capitalize()
        graph         = Graph()
        reference_id  = self.ids.next_id("reference")
        reference_uri = rdf.ROW[f"reference_{reference_id}"]

        graph.add ((reference_uri, RDF.type,                   rdf.SG[f"{prefix}Reference"]))
        graph.add ((reference_uri, rdf.COL["id"],              Literal(reference_id)))
        graph.add ((reference_uri, rdf.COL[f"{item_type}_id"], Literal(item_id)))
        graph.add ((reference_uri, rdf.COL["url"],             Literal(url, datatype=XSD.string)))

        query = self.__insert_query_for_graph (graph)
        if self.__run_query(query):
            return reference_id

        return None

    def insert_funding (self, title=None, grant_code=None, funder_name=None,
                        is_user_defined=None, url=None, item_id=None,
                        item_type=None, funding_id=None):
        """Procedure to add an funding to the state graph."""

        prefix      = item_type.capitalize()
        graph       = Graph()

        if funding_id is None:
            funding_id  = self.ids.next_id("funding")

        funding_uri = rdf.ROW[f"funding_{funding_id}"]

        graph.add ((funding_uri, RDF.type,                   rdf.SG[f"{prefix}Funding"]))
        graph.add ((funding_uri, rdf.COL["id"],              Literal(funding_id)))
        graph.add ((funding_uri, rdf.COL[f"{item_type}_id"], Literal(item_id)))

        rdf.add (graph, funding_uri, rdf.COL["title"],           title,           XSD.string)
        rdf.add (graph, funding_uri, rdf.COL["grant_code"],      grant_code,      XSD.string)
        rdf.add (graph, funding_uri, rdf.COL["funder_name"],     funder_name,     XSD.string)
        rdf.add (graph, funding_uri, rdf.COL["is_user_defined"], is_user_defined)
        rdf.add (graph, funding_uri, rdf.COL["url"],             url,             XSD.string)

        query = self.__insert_query_for_graph (graph)
        if self.__run_query(query):
            return funding_id

        return None

    def insert_file (self, file_id=None, name=None, size=None,
                     is_link_only=None, download_url=None, supplied_md5=None,
                     computed_md5=None, viewer_type=None, preview_state=None,
                     status=None, upload_url=None, upload_token=None,
                     article_id=None):
        """Procedure to add an file to the state graph."""

        graph    = Graph()

        if file_id is None:
            file_id  = self.ids.next_id("file")

        file_uri = rdf.ROW[f"file_{file_id}"]

        graph.add ((file_uri, RDF.type,               rdf.SG["File"]))
        graph.add ((file_uri, rdf.COL["id"],          Literal(file_id)))

        rdf.add (graph, file_uri, rdf.COL["name"],          name,          XSD.string)
        rdf.add (graph, file_uri, rdf.COL["size"],          size)
        rdf.add (graph, file_uri, rdf.COL["is_link_only"],  is_link_only)
        rdf.add (graph, file_uri, rdf.COL["download_url"],  download_url,  XSD.string)
        rdf.add (graph, file_uri, rdf.COL["supplied_md5"],  supplied_md5,  XSD.string)
        rdf.add (graph, file_uri, rdf.COL["computed_md5"],  computed_md5,  XSD.string)
        rdf.add (graph, file_uri, rdf.COL["viewer_type"],   viewer_type,   XSD.string)
        rdf.add (graph, file_uri, rdf.COL["preview_state"], preview_state, XSD.string)
        rdf.add (graph, file_uri, rdf.COL["status"],        status,        XSD.string)
        rdf.add (graph, file_uri, rdf.COL["upload_url"],    upload_url,    XSD.string)
        rdf.add (graph, file_uri, rdf.COL["upload_token"],  upload_token,  XSD.string)

        self.cache.invalidate_by_prefix ("article")
        query = self.__insert_query_for_graph (graph)
        if self.__run_query(query):
            if article_id is not None:
                link_id = self.insert_article_file (article_id, file_id)
                if link_id is not None:
                    return file_id
            else:
                return file_id

        return None

    def update_file (self, account_id, file_id, download_url=None,
                     computed_md5=None, viewer_type=None, preview_state=None,
                     file_size=None, status=None):
        """Procedure to update file metadata."""

        query   = self.__query_from_template ("update_file", {
            "state_graph":   self.state_graph,
            "account_id":    account_id,
            "file_id":       file_id,
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

        graph.add ((license_uri, RDF.type,               rdf.SG["License"]))
        graph.add ((license_uri, rdf.COL["id"],          Literal(license_id)))

        rdf.add (graph, license_uri, rdf.COL["name"],  name, XSD.string)
        rdf.add (graph, license_uri, rdf.COL["url"],   url,  XSD.string)

        query = self.__insert_query_for_graph (graph)
        if self.__run_query(query):
            return license_id

        return None

    def insert_private_link (self, private_link_id=None, read_only=True,
                             id_string=None, is_active=True, expires_date=None,
                             item_id=None, item_type="article"):

        if id_string is None:
            id_string = secrets.token_urlsafe()

        if private_link_id is None:
            private_link_id = self.ids.next_id("private_links")

        prefix   = item_type.capitalize()
        graph    = Graph()
        link_uri = rdf.ROW[f"private_link_{id_string}"]

        graph.add ((link_uri, RDF.type,      rdf.SG[f"{prefix}PrivateLink"]))
        graph.add ((link_uri, rdf.COL["id"], Literal(private_link_id)))

        rdf.add (graph, link_uri, rdf.COL["id_string"],       id_string,    XSD.string)
        rdf.add (graph, link_uri, rdf.COL["read_only"],       read_only)
        rdf.add (graph, link_uri, rdf.COL["is_active"],       is_active)
        rdf.add (graph, link_uri, rdf.COL["expires_date"],    expires_date, XSD.string)
        rdf.add (graph, link_uri, rdf.COL[f"{item_type}_id"], item_id)

        query = self.__insert_query_for_graph (graph)
        if self.__run_query(query):
            return id_string

        return None

    def insert_embargo (self, embargo_id, article_id, embargo_type=None, ip_name=None):
        """Procedure to add an license to the state graph."""

        graph    = Graph()
        embargo_uri = rdf.ROW[f"embargo_{embargo_id}"]

        graph.add ((embargo_uri, RDF.type,               rdf.SG["ArticleEmbargoOption"]))
        graph.add ((embargo_uri, rdf.COL["id"],          Literal(embargo_id)))
        graph.add ((embargo_uri, rdf.COL["article_id"],  Literal(article_id)))

        rdf.add (graph, embargo_uri, rdf.COL["type"],    embargo_type, XSD.string)
        rdf.add (graph, embargo_uri, rdf.COL["ip_name"], ip_name,      XSD.string)

        query = self.__insert_query_for_graph (graph)
        if self.__run_query(query):
            return embargo_id

        return None

    def insert_custom_field (self, name=None, value=None, default_value=None,
                             max_length=None, min_length=None, field_type=None,
                             is_mandatory=None, placeholder=None,
                             is_multiple=None, item_id=None,
                             item_type="article"):
        """Procedure to add a custom field to the state graph."""

        prefix           = item_type.capitalize()
        graph            = Graph()
        custom_field_id  = self.ids.next_id("custom_field")
        custom_field_uri = rdf.ROW[f"custom_field_{custom_field_id}"]

        graph.add ((custom_field_uri, RDF.type,                   rdf.SG[f"{prefix}CustomField"]))
        graph.add ((custom_field_uri, rdf.COL["id"],              Literal(custom_field_id)))
        graph.add ((custom_field_uri, rdf.COL[f"{item_type}_id"], Literal(item_id)))

        rdf.add (graph, custom_field_uri, rdf.COL["name"],          name,          XSD.string)
        rdf.add (graph, custom_field_uri, rdf.COL["value"],         value)
        rdf.add (graph, custom_field_uri, rdf.COL["default_value"], default_value)
        rdf.add (graph, custom_field_uri, rdf.COL["max_length"],    max_length)
        rdf.add (graph, custom_field_uri, rdf.COL["min_length"],    min_length)
        rdf.add (graph, custom_field_uri, rdf.COL["field_type"],    field_type)
        rdf.add (graph, custom_field_uri, rdf.COL["is_mandatory"],  is_mandatory)
        rdf.add (graph, custom_field_uri, rdf.COL["placeholder"],   placeholder)
        rdf.add (graph, custom_field_uri, rdf.COL["is_multiple"],   is_multiple)

        query = self.__insert_query_for_graph (graph)
        if self.__run_query(query):
            return custom_field_id

        return None

    def delete_article (self, article_id, account_id):
        """Procedure to remove an article from the state graph."""

        query   = self.__query_from_template ("delete_article", {
            "state_graph": self.state_graph,
            "account_id":  account_id,
            "article_id":  article_id
        })

        result = self.__run_query(query)
        self.cache.invalidate_by_prefix (f"{article_id}_article")
        self.cache.invalidate_by_prefix ("article")
        return result

    def update_article (self, article_id, account_id, title=None,
                        description=None, resource_doi=None,
                        resource_title=None, license_id=None,
                        time_coverage=None, publisher=None, language=None,
                        mimetype=None, contributors=None, license_remarks=None,
                        geolocation=None, longitude=None, latitude=None,
                        data_link=None, derived_from=None,
                        same_as=None, organizations=None, categories=None):
        query   = self.__query_from_template ("update_article", {
            "account_id":      account_id,
            "article_id":      article_id,
            "contributors":    contributors,
            "data_link":       data_link,
            "derived_from":    derived_from,
            "description":     description,
            "format":          mimetype,
            "geolocation":     geolocation,
            "language":        language,
            "latitude":        latitude,
            "license_id":      license_id,
            "license_remarks": license_remarks,
            "longitude":       longitude,
            "modified_date":   datetime.strftime (datetime.now(), "%Y-%m-%d %H:%M:%S"),
            "organizations":   organizations,
            "publisher":       publisher,
            "resource_doi":    resource_doi,
            "resource_title":  resource_title,
            "same_as":         same_as,
            "state_graph":     self.state_graph,
            "time_coverage":   time_coverage,
            "title":           title
        })

        self.cache.invalidate_by_prefix ("article")
        self.cache.invalidate_by_prefix (f"{article_id}_article")
        results = self.__run_query (query, query, f"{article_id}_article")
        if results:
            self.delete_article_categories (article_id, account_id)
            for category in categories:
                self.insert_article_category (article_id, category)

        return results

    def delete_article_embargo (self, article_id, account_id):
        """Procedure to lift the embargo on an article."""

        query   = self.__query_from_template ("delete_article_embargo", {
            "state_graph": self.state_graph,
            "account_id":  account_id,
            "article_id":  article_id
        })

        return self.__run_query(query)

    def delete_private_links (self, item_id, account_id, link_id, item_type="article"):
        """Procedure to remove private links to an article."""

        prefix  = item_type.capitalize()
        query   = self.__query_from_template ("delete_private_links", {
            "state_graph": self.state_graph,
            "account_id":  account_id,
            "item_id":     item_id,
            "item_type":   item_type,
            "prefix":      prefix,
            "id_string":   link_id
        })

        return self.__run_query(query)

    def update_private_link (self, item_id, account_id, link_id,
                             is_active=None, expires_date=None,
                             read_only=None, item_type="article"):
        """Procedure to update a private link to an article."""

        prefix  = item_type.capitalize()
        query   = self.__query_from_template ("update_private_link", {
            "state_graph":  self.state_graph,
            "account_id":   account_id,
            "item_id":      item_id,
            "item_type":    item_type,
            "prefix":       prefix,
            "id_string":    link_id,
            "is_active":    is_active,
            "expires_date": expires_date,
            "read_only":    read_only
        })

        return self.__run_query(query)

    def article_update_thumb (self, article_id, version, account_id, file_id):
        """Procedure to update the thumbnail of an article."""

        filters = rdf.sparql_filter ("file_id", file_id)
        query   = self.__query_from_template ("update_article_thumb", {
            "state_graph": self.state_graph,
            "account_id":  account_id,
            "article_id":  article_id,
            "version":     version,
            "filters":     filters
        })

        return self.__run_query(query)

    def insert_collection_article (self, collection_id, article_id):
        """Procedure to add an article to a collection."""

        if collection_id is None or article_id is None:
            return False

        graph       = Graph()
        link_id  = self.ids.next_id("collection_article")
        link_uri = rdf.ROW[f"collection_article_{link_id}"]

        graph.add ((link_uri, RDF.type,                  rdf.SG["CollectionArticle"]))
        graph.add ((link_uri, rdf.COL["id"],             Literal(link_id)))
        graph.add ((link_uri, rdf.COL["collection_id"],  Literal(collection_id)))
        graph.add ((link_uri, rdf.COL["article_id"],     Literal(article_id)))

        query = self.__insert_query_for_graph (graph)
        if self.__run_query(query):
            return link_id

        return None

    def insert_collection (self, title,
                           account_id,
                           collection_id=None,
                           funding=None,
                           funding_list=None,
                           description=None,
                           articles=None,
                           authors=None,
                           categories=None,
                           categories_by_source_id=None,
                           tags=None,
                           keywords=None,
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
                           publisher_acceptance=None,
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
        articles                = [] if articles                is None else articles

        graph = Graph()

        if collection_id is None:
            collection_id = self.ids.next_id("collection")

        collection_uri = rdf.ROW[f"collection_{collection_id}"]

        ## TIMELINE
        ## --------------------------------------------------------------------
        timeline_id = self.insert_timeline (
            revision              = revision,
            first_online          = first_online,
            publisher_publication = publisher_publication,
            publisher_acceptance  = publisher_acceptance,
            posted                = posted,
            submission            = submission
        )

        rdf.add (graph, collection_uri, rdf.COL["timeline_id"], timeline_id)

        ## REFERENCES
        ## --------------------------------------------------------------------
        for reference in references:
            self.insert_reference (reference, item_id=collection_id, item_type="collection")

        ## TAGS
        ## --------------------------------------------------------------------
        for tag in tags:
            self.insert_tag (tag, item_id=collection_id, item_type="collection")

        ## FUNDING
        ## --------------------------------------------------------------------
        for fund in funding_list:
            self.insert_funding (
                funding_id      = conv.value_or_none (fund, "id"),
                title           = conv.value_or_none (fund, "title"),
                grant_code      = conv.value_or_none (fund, "grant_code"),
                funder_name     = conv.value_or_none (fund, "funder_name"),
                is_user_defined = conv.value_or_none (fund, "is_user_defined"),
                url             = conv.value_or_none (fund, "url"),
                item_id         = collection_id,
                item_type       = "collection")

        ## CATEGORIES
        ## --------------------------------------------------------------------
        for category in categories:
            category_id = self.insert_category (
                category_id = conv.value_or_none (category, "id"),
                title       = conv.value_or_none (category, "title"),
                parent_id   = conv.value_or_none (category, "parent_id"),
                source_id   = conv.value_or_none (category, "source_id"),
                taxonomy    = conv.value_or_none (category, "taxonomy"))
            self.insert_collection_category (collection_id, category_id)

        ## ARTICLES
        ## --------------------------------------------------------------------
        for article_id in articles:
            self.insert_collection_article (collection_id, article_id)

        ## AUTHORS
        ## --------------------------------------------------------------------
        for author in authors:
            author_id = self.insert_author (
                author_id      = conv.value_or_none (author, "id"),
                is_active      = conv.value_or_none (author, "is_active"),
                first_name     = conv.value_or_none (author, "first_name"),
                last_name      = conv.value_or_none (author, "last_name"),
                full_name      = conv.value_or_none (author, "full_name"),
                institution_id = conv.value_or_none (author, "institution_id"),
                job_title      = conv.value_or_none (author, "job_title"),
                is_public      = conv.value_or_none (author, "is_public"),
                url_name       = conv.value_or_none (author, "url_name"),
                orcid_id       = conv.value_or_none (author, "orcid_id"))
            self.insert_collection_author (collection_id, author_id)

        ## CUSTOM FIELDS
        ## --------------------------------------------------------------------
        for field in custom_fields:
            self.insert_custom_field (
                name          = conv.value_or_none (field, "name"),
                value         = conv.value_or_none (field, "value"),
                default_value = conv.value_or_none (field, "default_value"),
                max_length    = conv.value_or_none (field, "max_length"),
                min_length    = conv.value_or_none (field, "min_length"),
                field_type    = conv.value_or_none (field, "field_type"),
                is_mandatory  = conv.value_or_none (field, "is_mandatory"),
                placeholder   = conv.value_or_none (field, "placeholder"),
                is_multiple   = conv.value_or_none (field, "is_multiple"),
                item_id       = collection_id,
                item_type     = "collection")

        ## PRIVATE LINKS
        ## --------------------------------------------------------------------
        for link in private_links:
            self.insert_private_link (
                item_id          = collection_id,
                item_type        = "collection",
                private_link_id  = conv.value_or_none (link, "id"),
                is_active        = conv.value_or_none (link, "is_active"),
                expires_date     = conv.value_or_none (link, "expires_date"))

        ## TOPLEVEL FIELDS
        ## --------------------------------------------------------------------

        graph.add ((collection_uri, RDF.type,         rdf.SG["Collection"]))
        graph.add ((collection_uri, rdf.COL["id"],    Literal(collection_id)))
        graph.add ((collection_uri, rdf.COL["collection_id"], Literal(collection_id)))
        graph.add ((collection_uri, rdf.COL["title"], Literal(title, datatype=XSD.string)))

        rdf.add (graph, collection_uri, rdf.COL["account_id"],     account_id)
        rdf.add (graph, collection_uri, rdf.COL["description"],    description,    XSD.string)
        rdf.add (graph, collection_uri, rdf.COL["funding"],        funding,        XSD.string)
        rdf.add (graph, collection_uri, rdf.COL["doi"],            doi,            XSD.string)
        rdf.add (graph, collection_uri, rdf.COL["handle"],         handle,         XSD.string)
        rdf.add (graph, collection_uri, rdf.COL["url"],            url,            XSD.string)
        rdf.add (graph, collection_uri, rdf.COL["resource_doi"],   resource_doi,   XSD.string)
        rdf.add (graph, collection_uri, rdf.COL["resource_title"], resource_title, XSD.string)
        rdf.add (graph, collection_uri, rdf.COL["group_id"],       group_id)

        query = self.__insert_query_for_graph (graph)
        if self.__run_query(query):
            logging.info ("Inserted collection %d", collection_id)
            return collection_id

        return None

    def delete_collection (self, collection_id, account_id):
        """Procedure to remove a collection from the state graph."""

        query   = self.__query_from_template ("delete_collection", {
            "state_graph":   self.state_graph,
            "account_id":    account_id,
            "collection_id": collection_id
        })

        return self.__run_query(query)

    def category_by_id (self, category_id):
        """Procedure to return category information by its identifier."""

        query = self.__query_from_template ("category_by_id", {
            "state_graph": self.state_graph,
            "category_id": category_id
        })

        try:
            results = self.__run_query (query, query, "category")
            return results[0]
        except IndexError:
            return None

    def subcategories_for_category (self, category_id):
        """Procedure to return the subcategories for a category."""

        query = self.__query_from_template ("subcategories_by_category", {
            "state_graph": self.state_graph,
            "category_id": category_id
        })

        return self.__run_query (query, query, "category")

    def root_categories (self):
        """Procedure to return the categories without a parent category."""

        query = self.__query_from_template ("root_categories", {
            "state_graph": self.state_graph
        })

        query += rdf.sparql_suffix ("title", "asc")
        return self.__run_query (query, query, "category")

    def group_by_name (self, group_name, startswith=False):
        """Procedure to return group information by its name."""

        query = self.__query_from_template ("group_by_name", {
            "state_graph": self.state_graph,
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

    def account_storage_used (self, account_id):
        """Returns the number of bytes used by an account."""

        query = self.__query_from_template ("account_storage_used", {
            "state_graph": self.state_graph,
            "account_id":  account_id
        })

        results = self.__run_query (query, query, "storage")
        try:
            return results[0]["bytes"]
        except IndexError:
            logging.error ("Account %s looks to be empty.", account_id)
            return 0
        except KeyError:
            logging.error ("Failed to retrieve used storage for account %s.", account_id)

        return None

    def opendap_to_doi(self, startswith=None, endswith=None):
        """Procedure to return DOI corresponding to opendap catalog url"""

        filters = ""

        if startswith is not None:
            if isinstance(startswith, list):
                filters += f"FILTER ((STRSTARTS(STR(?download_url), \"{ startswith[0] }\"))"
                for filter_item in startswith[1:]:
                    filters += f" OR (STRSTARTS(STR(?download_url), \"{filter_item}\"))"
                filters += ")\n"
            elif isinstance(startswith, str):
                filters += f"FILTER (STRSTARTS(STR(?download_url), \"{ startswith }\"))\n"
            else:
                logging.error("startswith of type %s is not supported", type(startswith))

        if endswith is not None:
            filters += f"FILTER (STRENDS(STR(?download_url), \"{ endswith }\"))\n"

        query = self.__query_from_template ("opendap_to_doi", {
            "state_graph": self.state_graph,
            "filters": filters
        })

        results = self.__run_query (query)
        return results

    def account_id_by_orcid (self, orcid):
        """Returns the account ID belonging to an ORCID."""

        query = self.__query_from_template ("account_id_by_orcid", {
            "state_graph": self.state_graph,
            "orcid":       orcid
        })

        try:
            results = self.__run_query (query)
            return results[0]["account_id"]
        except IndexError:
            return None
        except KeyError:
            return None

    def account_by_session_token (self, session_token):
        """Returns an account_id or None."""

        query = self.__query_from_template ("account_by_session_token", {
            "state_graph": self.state_graph,
            "token":       session_token
        })

        try:
            results = self.__run_query (query)
            account = results[0]
            privileges = self.privileges[int(account["account_id"])]
            account = { **account, **privileges }
            return account
        except IndexError:
            return None
        except KeyError:
            return account

    def account_by_id (self, account_id):
        """Returns an account_id or None."""

        query = self.__query_from_template ("account_by_id", {
            "state_graph": self.state_graph,
            "account_id":  account_id
        })

        try:
            results    = self.__run_query (query)
            account    = results[0]
            privileges = self.privileges[int(account["account_id"])]
            account    = { **account, **privileges }
            return account
        except IndexError:
            return None
        except KeyError:
            return account

    def insert_session (self, account_id, token=None):
        """Procedure to add a session token for an account_id."""

        if account_id is None:
            return False

        if token is None:
            token = secrets.token_hex (64)

        graph       = Graph()
        link_id     = self.ids.next_id("session")
        link_uri    = rdf.ROW[f"session_link_{link_id}"]
        graph.add ((link_uri, RDF.type,              rdf.SG["Session"]))
        graph.add ((link_uri, rdf.COL["account_id"], Literal(account_id)))
        graph.add ((link_uri, rdf.COL["id"],         Literal(link_id)))
        graph.add ((link_uri, rdf.COL["token"],      Literal(token, datatype=XSD.string)))

        query = self.__insert_query_for_graph (graph)
        if self.__run_query(query):
            return token

        return None

    def delete_session (self, token):
        """Procedure to remove a session from the state graph."""

        if token is None:
            return True

        query   = self.__query_from_template ("delete_session", {
            "state_graph": self.state_graph,
            "token":       token
        })

        return self.__run_query(query)

    def is_depositor (self, session_token):
        """Returns True when the account linked to the session is a depositor, False otherwise"""
        account = self.account_by_session_token (session_token)
        return account is not None

    def is_logged_in (self, session_token):
        """Returns True when the session_token is valid, False otherwise."""
        account = self.account_by_session_token (session_token)
        return account is not None
