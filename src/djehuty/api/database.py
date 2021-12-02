"""
This module provides the communication with the SPARQL endpoint to provide
data for the API server.
"""

import logging
from urllib.error import URLError
from SPARQLWrapper import SPARQLWrapper, JSON
from rdflib import Graph, Literal, RDF
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

        self.ids = counters.IdGenerator()
        self.endpoint = "http://127.0.0.1:8890/sparql"
        self.state_graph = "https://data.4tu.nl/portal/2021-11-19"
        self.sparql = SPARQLWrapper(self.endpoint)
        self.sparql.setReturnFormat(JSON)
        self.default_prefixes = """\
PREFIX col: <sg://0.99.12/table2rdf/Column/>
PREFIX sg:  <https://sparqling-genomics.org/0.99.12/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        """

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
                    record[item] = bool(record[item]["value"])
                elif datatype == "http://www.w3.org/2001/XMLSchema#string":
                    if record[item]["value"] == "NULL":
                        record[item] = None
                    else:
                        record[item] = record[item]["value"]
            elif record[item]["type"] == "literal":
                logging.info(record[item]['value'])
                return record[item]["value"]
            else:
                logging.info("Not a typed-literal: %s", record[item]['type'])
        return record

    def __run_query (self, query):
        self.sparql.method = 'POST'
        self.sparql.setQuery(query)
        results = []
        try:
            query_results = self.sparql.query().convert()
            results = list(map(self.__normalize_binding,
                               query_results["results"]["bindings"]))
        except URLError:
            logging.error("Connection to the SPARQL endpoint seems down.")
        except Exception as error:
            logging.error("SPARQL query failed.")
            logging.error("Exception: %s", error)
            logging.error("Query:\n---\n%s\n---", query)

        return results

    def __highest_id (self, item_type="article"):
        """Return the highest numeric ID for ITEM_TYPE."""
        prefix = item_type.capitalize()
        query  = f"""\
{self.default_prefixes}
SELECT ?id WHERE {{
  GRAPH <{self.state_graph}> {{
    ?item rdf:type    sg:{prefix} .
    ?item col:id      ?id .
  }}
}}
ORDER BY DESC(?id)
LIMIT 1
"""
        try:
            results = self.__run_query (query)
            return results[0]["id"]
        except IndexError as error:
            raise EmptyDatabase from error
        except KeyError:
            return None

    def __insert_query_for_graph (self, graph):
        query = "INSERT { GRAPH <%s> { %s } }" % (
            self.state_graph,
            graph.serialize(format="ntriples").decode('utf-8')
        )

        return query

    ## ------------------------------------------------------------------------
    ## GET METHODS
    ## ------------------------------------------------------------------------

    def article_versions (self, limit=1000, offset=0, order=None,
                          order_direction=None, article_id=None):

        query = f"""\
{self.default_prefixes}
SELECT DISTINCT ?id ?version ?url ?url_public_api
WHERE {{
  GRAPH <{self.state_graph}> {{
    ?article rdf:type           sg:Article .
    ?article col:id             ?id .
    ?article col:version        ?version .
    ?article col:url            ?url .
    ?article col:url_public_api ?url_public_api .
  }}
"""
        if article_id is not None:
            query += rdf.sparql_filter ("id", article_id)

        query += "}\n"
        query += rdf.sparql_suffix (order, order_direction, limit, offset)

        return self.__run_query (query)

    def articles (self, limit=10, offset=None, order=None,
                  order_direction=None, institution=None,
                  published_since=None, modified_since=None,
                  group=None, resource_doi=None, item_type=None,
                  doi=None, handle=None, account_id=None,
                  search_for=None, article_id=None,
                  collection_id=None, version=None):

        query = f"""\
{self.default_prefixes}
SELECT DISTINCT ?account_id ?authors_id ?citation
                ?confidential_reason ?created_date
                ?custom_fields_id ?defined_type
                ?defined_type_name ?description
                ?doi ?embargo_date ?embargo_options_id
                ?embargo_reason ?embargo_title
                ?embargo_type ?figshare_url
                ?funding ?funding_id ?group_id
                ?has_linked_file ?id ?institution_id
                ?is_active ?is_confidential ?is_embargoed
                ?is_metadata_record ?is_public ?license_id
                ?license_name ?license_url
                ?metadata_reason ?modified_date
                ?published_date
                ?resource_doi ?resource_title ?size
                ?status ?tags_id ?thumb ?timeline_posted
                ?timeline_publisher_acceptance
                ?timeline_publisher_publication
                ?timeline_first_online ?timeline_revision
                ?timeline_submission ?title ?url ?url_private_api
                ?url_private_html ?url_public_api
                ?url_public_html ?version
WHERE {{
  GRAPH <{self.state_graph}> {{
    ?article            rdf:type                 sg:Article .
    ?article            col:id                   ?id .
    ?article            col:timeline_id          ?timeline_id .
"""
        if collection_id is not None:
            query += f"""\
    ?link               rdf:type                 sg:CollectionArticle .
    ?link               col:article_id           ?id .
    ?link               col:collection_id        {collection_id} .
 """

        query += """\
    OPTIONAL {
        ?timeline           rdf:type                 sg:Timeline .
        ?timeline           col:id                   ?timeline_id .

        OPTIONAL { ?timeline col:firstonline          ?timeline_first_online . }
        OPTIONAL { ?timeline col:publisheracceptance  ?timeline_publisher_acceptance . }
        OPTIONAL { ?timeline col:publisherpublication ?timeline_publisher_publication . }
        OPTIONAL { ?timeline col:submission           ?timeline_submission . }
        OPTIONAL { ?timeline col:posted               ?timeline_posted . }
        OPTIONAL { ?timeline col:revision             ?timeline_revision . }
    }

    OPTIONAL {
        ?license            rdf:type                  sg:License .
        ?license            col:id                    ?license_id .
        ?license            col:name                  ?license_name .
        ?license            col:url                   ?license_url .
        ?article            col:license_id            ?license_id .
    }

    OPTIONAL { ?article col:account_id            ?account_id . }
    OPTIONAL { ?article col:authors_id            ?authors_id . }
    OPTIONAL { ?article col:citation              ?citation . }
    OPTIONAL { ?article col:confidential_reason   ?confidential_reason . }
    OPTIONAL { ?article col:created_date          ?created_date . }
    OPTIONAL { ?article col:custom_fields_id      ?custom_fields_id . }
    OPTIONAL { ?article col:defined_type          ?defined_type . }
    OPTIONAL { ?article col:defined_type_name     ?defined_type_name . }
    OPTIONAL { ?article col:description           ?description . }
    OPTIONAL { ?article col:doi                   ?doi . }
    OPTIONAL { ?article col:embargo_date          ?embargo_date . }
    OPTIONAL { ?article col:embargo_options_id    ?embargo_options_id . }
    OPTIONAL { ?article col:embargo_reason        ?embargo_reason . }
    OPTIONAL { ?article col:embargo_title         ?embargo_title . }
    OPTIONAL { ?article col:embargo_type          ?embargo_type . }
    OPTIONAL { ?article col:figshare_url          ?figshare_url . }
    OPTIONAL { ?article col:funding               ?funding . }
    OPTIONAL { ?article col:funding_id            ?funding_id . }
    OPTIONAL { ?article col:group_id              ?group_id . }
    OPTIONAL { ?article col:handle                ?handle . }
    OPTIONAL { ?article col:has_linked_file       ?has_linked_file . }
    OPTIONAL { ?article col:institution_id        ?institution_id . }
    OPTIONAL { ?article col:is_active             ?is_active . }
    OPTIONAL { ?article col:is_confidential       ?is_confidential . }
    OPTIONAL { ?article col:is_embargoed          ?is_embargoed . }
    OPTIONAL { ?article col:is_metadata_record    ?is_metadata_record . }
    OPTIONAL { ?article col:is_public             ?is_public . }
    OPTIONAL { ?article col:metadata_reason       ?metadata_reason . }
    OPTIONAL { ?article col:modified_date         ?modified_date . }
    OPTIONAL { ?article col:published_date        ?published_date . }
    OPTIONAL { ?article col:resource_doi          ?resource_doi . }
    OPTIONAL { ?article col:resource_title        ?resource_title . }
    OPTIONAL { ?article col:size                  ?size . }
    OPTIONAL { ?article col:status                ?status . }
    OPTIONAL { ?article col:tags_id               ?tags_id . }
    OPTIONAL { ?article col:thumb                 ?thumb . }
    OPTIONAL { ?article col:title                 ?title . }
    OPTIONAL { ?article col:url                   ?url . }
    OPTIONAL { ?article col:url_private_api       ?url_private_api . }
    OPTIONAL { ?article col:url_private_html      ?url_private_html . }
    OPTIONAL { ?article col:url_public_api        ?url_public_api . }
    OPTIONAL { ?article col:url_public_html       ?url_public_html . }
    OPTIONAL { ?article col:version               ?version . }
}
"""

        query += rdf.sparql_filter ("institution_id", institution)
        query += rdf.sparql_filter ("group_id",       group)
        query += rdf.sparql_filter ("defined_type",   item_type)
        query += rdf.sparql_filter ("id",             article_id)
        query += rdf.sparql_filter ("version",        version)
        query += rdf.sparql_filter ("resource_doi",   resource_doi, escape=True)
        query += rdf.sparql_filter ("doi",            doi,          escape=True)
        query += rdf.sparql_filter ("handle",         handle,       escape=True)
        query += rdf.sparql_filter ("title",          search_for,   escape=True)
        query += rdf.sparql_filter ("resource_title", search_for,   escape=True)
        query += rdf.sparql_filter ("description",    search_for,   escape=True)
        query += rdf.sparql_filter ("citation",       search_for,   escape=True)

        if published_since is not None:
            query += "FILTER (BOUND(?published_date))\n"
            query += "FILTER (STR(?published_date) != \"NULL\")\n"
            query += f"FILTER (STR(?published_date) > \"{published_since}\")\n"

        if modified_since is not None:
            query += "FILTER (BOUND(?modified_date))\n"
            query += "FILTER (STR(?modified_date) != \"NULL\")\n"
            query += f"FILTER (STR(?modified_date) > \"{modified_since}\")\n"

        if account_id is None:
            query += rdf.sparql_filter ("is_public", 1)
        else:
            query += rdf.sparql_filter ("account_id", account_id)

        query += "}\n"
        query += rdf.sparql_suffix (order, order_direction, limit, offset)

        return self.__run_query (query)

    def authors (self, first_name=None, full_name=None, group_id=None,
                 author_id=None, institution_id=None, is_active=None,
                 is_public=None, job_title=None, last_name=None,
                 orcid_id=None, url_name=None, limit=10, order=None,
                 order_direction=None, item_id=None,
                 account_id=None, item_type="article"):

        prefix = "Article" if item_type == "article" else "Collection"
        query  = f"""\
{self.default_prefixes}
SELECT DISTINCT ?first_name      ?full_name       ?group_id
                ?id              ?institution_id  ?is_active
                ?is_public       ?job_title       ?last_name
                ?orcid_id        ?url_name
WHERE {{
  GRAPH <{self.state_graph}> {{
    ?author            rdf:type                 sg:Author .
    ?author            col:id                   ?id .
"""

        if item_id is not None:
            query += f"""\
    ?item              rdf:type                 sg:{prefix} .
    ?link              rdf:type                 sg:{prefix}AuthorLink .
    ?link              col:{item_type}_id       {item_id} .
    ?link              col:author_id            ?id .
"""

        if (item_id is not None) and (account_id is not None):
            query += """\
    ?item              col:account_id           ?account_id .
"""

        query += """\
    OPTIONAL { ?author col:first_name            ?first_name . }
    OPTIONAL { ?author col:full_name             ?full_name . }
    OPTIONAL { ?author col:group_id              ?group_id . }
    OPTIONAL { ?author col:institution_id        ?institution_id . }
    OPTIONAL { ?author col:is_active             ?is_active . }
    OPTIONAL { ?author col:is_public             ?is_public . }
    OPTIONAL { ?author col:job_title             ?job_title . }
    OPTIONAL { ?author col:last_name             ?last_name . }
    OPTIONAL { ?author col:orcid_id              ?orcid_id . }
    OPTIONAL { ?author col:url_name              ?url_name . }
  }
"""

        query += rdf.sparql_filter ("group_id",       group_id)
        query += rdf.sparql_filter ("id",             author_id)
        query += rdf.sparql_filter ("institution_id", institution_id)
        query += rdf.sparql_filter ("is_active",      is_active)
        query += rdf.sparql_filter ("is_public",      is_public)
        query += rdf.sparql_filter ("job_title",      job_title,  escape=True)
        query += rdf.sparql_filter ("first_name",     first_name, escape=True)
        query += rdf.sparql_filter ("last_name",      last_name,  escape=True)
        query += rdf.sparql_filter ("full_name",      full_name,  escape=True)
        query += rdf.sparql_filter ("orcid_id",       orcid_id,   escape=True)
        query += rdf.sparql_filter ("url_name",       url_name,   escape=True)

        query += "}\n"
        query += rdf.sparql_suffix ("full_name" if order is None else order,
                                    "asc" if order_direction is None else order_direction,
                                    limit,
                                    None)

        return self.__run_query(query)

    def article_files (self, name=None, size=None, is_link_only=None,
                       file_id=None, download_url=None, supplied_md5=None,
                       computed_md5=None, viewer_type=None, preview_state=None,
                       status=None, upload_url=None, upload_token=None,
                       order=None, order_direction=None, limit=10,
                       article_id=None, account_id=None):

        query = f"""\
{self.default_prefixes}
SELECT DISTINCT ?name          ?size          ?is_link_only
                ?id            ?download_url  ?supplied_md5
                ?computed_md5  ?viewer_type   ?preview_state
                ?status        ?upload_url    ?upload_token
WHERE {{
  GRAPH <{self.state_graph}> {{
    ?file              rdf:type                 sg:File .
    ?file              col:id                   ?id .
"""

        if article_id is not None:
            query += f"""\
    ?article           rdf:type                 sg:Article .
    ?link              rdf:type                 sg:ArticleFileLink .
    ?link              col:article_id           {article_id} .
    ?link              col:file_id              ?id .
"""

        if (article_id is not None) and (account_id is not None):
            query += "    ?article           col:account_id           ?account_id ."

        query += """\
    OPTIONAL { ?file  col:name                 ?name . }
    OPTIONAL { ?file  col:size                 ?size . }
    OPTIONAL { ?file  col:is_link_only         ?is_link_only . }
    OPTIONAL { ?file  col:download_url         ?download_url . }
    OPTIONAL { ?file  col:supplied_md5         ?supplied_md5 . }
    OPTIONAL { ?file  col:computed_md5         ?computed_md5 . }
    OPTIONAL { ?file  col:viewer_type          ?viewer_type . }
    OPTIONAL { ?file  col:preview_state        ?preview_state . }
    OPTIONAL { ?file  col:status               ?status . }
    OPTIONAL { ?file  col:upload_url           ?upload_url . }
    OPTIONAL { ?file  col:upload_token         ?upload_token . }
  }
"""

        query += rdf.sparql_filter ("size",          size)
        query += rdf.sparql_filter ("is_link_only",  is_link_only)
        query += rdf.sparql_filter ("id",            file_id)
        query += rdf.sparql_filter ("name",          name,          escape=True)
        query += rdf.sparql_filter ("download_url",  download_url,  escape=True)
        query += rdf.sparql_filter ("supplied_md5",  supplied_md5,  escape=True)
        query += rdf.sparql_filter ("computed_md5",  computed_md5,  escape=True)
        query += rdf.sparql_filter ("viewer_type",   viewer_type,   escape=True)
        query += rdf.sparql_filter ("preview_state", preview_state, escape=True)
        query += rdf.sparql_filter ("status",        status,        escape=True)
        query += rdf.sparql_filter ("upload_url",    upload_url,    escape=True)
        query += rdf.sparql_filter ("upload_token",  upload_token,  escape=True)

        query += "}\n"
        query += rdf.sparql_suffix (order, order_direction, limit, None)

        return self.__run_query(query)

    def custom_fields (self, name=None, value=None, default_value=None,
                       field_id=None, placeholder=None, max_length=None,
                       min_length=None, field_type=None, is_multiple=None,
                       is_mandatory=None, order=None, order_direction=None,
                       limit=10, item_id=None, item_type="article"):

        prefix = "Article" if item_type == "article" else "Collection"

        query = f"""\
{self.default_prefixes}
SELECT DISTINCT ?name          ?value         ?default_value
                ?id            ?placeholder   ?max_length
                ?min_length    ?field_type    ?is_multiple
                ?is_mandatory
WHERE {{
  GRAPH <{self.state_graph}> {{
    ?field             rdf:type                 sg:{prefix}CustomField .
    ?field             col:id                   ?id .
"""

        if item_id is not None:
            query += f"""\
    ?field             col:{item_type}_id        {item_id} .
"""

        query += """\
    OPTIONAL { ?field  col:name                 ?name . }
    OPTIONAL { ?field  col:value                ?value . }
    OPTIONAL { ?field  col:default_value        ?default_value . }
    OPTIONAL { ?field  col:placeholder          ?placeholder . }
    OPTIONAL { ?field  col:max_length           ?max_length . }
    OPTIONAL { ?field  col:min_length           ?min_length . }
    OPTIONAL { ?field  col:field_type           ?field_type . }
    OPTIONAL { ?field  col:is_multiple          ?is_multiple . }
    OPTIONAL { ?field  col:is_mandatory         ?is_mandatory . }
  }
"""
        query += rdf.sparql_filter ("id",            field_id)
        query += rdf.sparql_filter ("max_length",    max_length)
        query += rdf.sparql_filter ("min_length",    min_length)
        query += rdf.sparql_filter ("is_multiple",   is_multiple)
        query += rdf.sparql_filter ("is_mandatory",  is_mandatory)
        query += rdf.sparql_filter ("name",          name,          escape=True)
        query += rdf.sparql_filter ("value",         value,         escape=True)
        query += rdf.sparql_filter ("default_value", default_value, escape=True)
        query += rdf.sparql_filter ("placeholder",   placeholder,   escape=True)
        query += rdf.sparql_filter ("field_type",    field_type,    escape=True)

        query += "}\n"
        query += rdf.sparql_suffix ("name" if order is None else order,
                                    order_direction,
                                    limit,
                                    None)

        return self.__run_query(query)

    def article_embargo_options (self, ip_name=None, embargo_type=None,
                                 order=None, order_direction=None,
                                 limit=10, article_id=None):

        if order_direction is None:
            order_direction = "DESC"
        if order is None:
            order="?id"

        query = f"""\
{self.default_prefixes}
SELECT DISTINCT ?id ?article_id ?type ?ip_name
WHERE {{
  GRAPH <{self.state_graph}> {{
    ?field             rdf:type                 sg:ArticleEmbargoOption .
    ?field             col:id                   ?id .
    ?field             col:article_id           ?article_id .
    OPTIONAL {{ ?field  col:type                 ?type . }}
    OPTIONAL {{ ?field  col:ip_name              ?ip_name . }}
  }}
"""
        query += rdf.sparql_filter ("article_id",   article_id)
        query += rdf.sparql_filter ("ip_name",      ip_name,      escape=True)
        query += rdf.sparql_filter ("embargo_type", embargo_type, escape=True)

        query += "}\n"
        query += rdf.sparql_suffix (order, order_direction, limit, None)

        return self.__run_query(query)

    def tags (self, order=None, order_direction=None, limit=10, item_id=None, item_type="article"):

        prefix = "Article" if item_type == "article" else "Collection"
        query  = f"""\
{self.default_prefixes}
SELECT DISTINCT ?id ?tag
WHERE {{
  GRAPH <{self.state_graph}> {{
    ?row             rdf:type                 sg:{prefix}Tag .
    ?row             col:id                   ?id .
    ?row             col:tag                  ?tag .
    ?row             col:{item_type}_id       ?item_id .
  }}
"""

        query += rdf.sparql_filter (f"{item_id}_id", item_id)
        query += "}\n"
        query += rdf.sparql_suffix (order, order_direction, limit, None)

        return self.__run_query(query)

    def categories (self, title=None, order=None, order_direction=None,
                    limit=10, item_id=None, account_id=None,
                    item_type="article"):
        prefix = "Article" if item_type == "article" else "Collection"

        query = f"""\
{self.default_prefixes}
SELECT DISTINCT ?id ?parent_id ?title ?source_id ?taxonomy_id
WHERE {{
  GRAPH <{self.state_graph}> {{
    ?row             rdf:type                 sg:Category .
    ?row             col:id                   ?id .
    ?row             col:title                ?title .
    OPTIONAL {{ ?row         col:parent_id        ?parent_id . }}
    OPTIONAL {{ ?row         col:source_id        ?source_id . }}
    OPTIONAL {{ ?row         col:taxonomy_id      ?taxonomy_id . }}
"""

        if item_id is not None:
            query += f"""\
    ?item            rdf:type                 sg:{prefix}CategoryLink .
    ?item            col:{item_type}_id       {item_id} .
    ?item            col:category_id          ?id .
"""

        if (item_id is not None) and (account_id is not None):
            query += "    ?item            col:account_id           ?account_id .\n"

        query += "  }\n"

        query += rdf.sparql_filter ("title", title, escape=True)
        query += "}\n"
        query += rdf.sparql_suffix (order, order_direction, limit, None)

        return self.__run_query(query)

    ## ------------------------------------------------------------------------
    ## COLLECTIONS
    ## ------------------------------------------------------------------------

    def collections (self, limit=10, offset=None, order=None,
                     order_direction=None, institution=None,
                     published_since=None, modified_since=None, group=None,
                     resource_doi=None, resource_id=None, doi=None, handle=None,
                     account_id=None, search_for=None, collection_id=None):

        query = f"""\
{self.default_prefixes}
SELECT DISTINCT ?account_id
                ?resource_id
                ?resource_doi
                ?resource_title
                ?resource_link
                ?resource_version
                ?version
                ?description
                ?institution_id
                ?group_id
                ?articles_count
                ?is_public
                ?citation
                ?group_resource_id
                ?custom_fields_id
                ?modified_date
                ?created_date
                ?timeline_posted
                ?timeline_publisher_acceptance
                ?timeline_publisher_publication
                ?timeline_first_online
                ?timeline_revision
                ?timeline_submission
                ?id
                ?title
                ?doi
                ?handle
                ?url
                ?published_date
WHERE {{
  GRAPH <{self.state_graph}> {{
    ?collection            rdf:type                 sg:Collection .
    ?collection            col:id                   ?id .
    ?collection            col:timeline_id          ?timeline_id .

    OPTIONAL {{
        ?timeline           rdf:type                 sg:Timeline .
        ?timeline           col:id                   ?timeline_id .

        OPTIONAL {{ ?timeline col:firstonline          ?timeline_first_online . }}
        OPTIONAL {{ ?timeline col:publisheracceptance  ?timeline_publisher_acceptance . }}
        OPTIONAL {{ ?timeline col:publisherpublication ?timeline_publisher_publication . }}
        OPTIONAL {{ ?timeline col:submission           ?timeline_submission . }}
        OPTIONAL {{ ?timeline col:posted               ?timeline_posted . }}
        OPTIONAL {{ ?timeline col:revision             ?timeline_revision . }}
    }}

    OPTIONAL {{ ?collection col:account_id         ?account_id . }}
    OPTIONAL {{ ?collection col:resource_id        ?resource_id . }}
    OPTIONAL {{ ?collection col:resource_doi       ?resource_doi . }}
    OPTIONAL {{ ?collection col:resource_title     ?resource_title . }}
    OPTIONAL {{ ?collection col:resource_link      ?resource_link . }}
    OPTIONAL {{ ?collection col:resource_version   ?resource_version . }}
    OPTIONAL {{ ?collection col:version            ?version . }}
    OPTIONAL {{ ?collection col:description        ?description . }}
    OPTIONAL {{ ?collection col:institution_id     ?institution_id . }}
    OPTIONAL {{ ?collection col:group_id           ?group_id . }}
    OPTIONAL {{ ?collection col:articles_count     ?articles_count . }}
    OPTIONAL {{ ?collection col:is_public          ?is_public . }}
    OPTIONAL {{ ?collection col:citation           ?citation . }}
    OPTIONAL {{ ?collection col:group_resource_id  ?group_resource_id . }}
    OPTIONAL {{ ?collection col:custom_fields_id   ?custom_fields_id . }}
    OPTIONAL {{ ?collection col:modified_date      ?modified_date . }}
    OPTIONAL {{ ?collection col:created_date       ?created_date . }}
    OPTIONAL {{ ?collection col:title              ?title . }}
    OPTIONAL {{ ?collection col:doi                ?doi . }}
    OPTIONAL {{ ?collection col:handle             ?handle . }}
    OPTIONAL {{ ?collection col:url                ?url . }}
    OPTIONAL {{ ?collection col:published_date     ?published_date . }}
  }}
"""

        query += rdf.sparql_filter ("institution_id", institution)
        query += rdf.sparql_filter ("group_id",       group)
        query += rdf.sparql_filter ("id",             collection_id)
        query += rdf.sparql_filter ("resource_doi",   resource_doi, escape=True)
        query += rdf.sparql_filter ("resource_id",    resource_id,  escape=True)
        query += rdf.sparql_filter ("doi",            doi,          escape=True)
        query += rdf.sparql_filter ("handle",         handle,       escape=True)
        query += rdf.sparql_filter ("title",          search_for,   escape=True)
        query += rdf.sparql_filter ("resource_title", search_for,   escape=True)
        query += rdf.sparql_filter ("description",    search_for,   escape=True)
        query += rdf.sparql_filter ("citation",       search_for,   escape=True)

        if published_since is not None:
            query += "FILTER (BOUND(?published_date))\n"
            query += "FILTER (STR(?published_date) != \"NULL\")\n"
            query += f"FILTER (STR(?published_date) > \"{published_since}\")\n"

        if modified_since is not None:
            query += "FILTER (BOUND(?modified_date))\n"
            query += "FILTER (STR(?modified_date) != \"NULL\")\n"
            query += f"FILTER (STR(?modified_date) > \"{modified_since}\")\n"

        if account_id is None:
            query += rdf.sparql_filter ("is_public", 1)
        else:
            query += rdf.sparql_filter ("account_id", account_id)

        query += "}\n"
        query += rdf.sparql_suffix (order, order_direction, limit, offset)

        return self.__run_query(query)

    def fundings (self, title=None, order=None, order_direction=None,
                  limit=10, item_id=None, account_id=None,
                  item_type="article"):

        prefix = "Article" if item_type == "article" else "Collection"
        query  = f"""\
{self.default_prefixes}
SELECT DISTINCT ?id ?title ?grant_code ?funder_name ?url
WHERE {{
  GRAPH <{self.state_graph}> {{
    ?row             rdf:type                 sg:{prefix}Funding .
    ?row             col:id                   ?id .
    ?row             col:{item_type}_id       ?{item_type}_id .
    OPTIONAL {{ ?row             col:title                ?title . }}
    OPTIONAL {{ ?row             col:grant_code           ?grant_code . }}
    OPTIONAL {{ ?row             col:funder_name          ?funder_name . }}
    OPTIONAL {{ ?row             col:url                  ?url . }}
"""

        if item_id is not None:
            query += f"""\
    ?item           rdf:type                 sg:{prefix}FundingLink .
    ?item           col:{item_type}_id       ?{item_type}_id .
    ?item           col:account_id           ?account_id .
  }}
"""

        query += rdf.sparql_filter ("account_id",      account_id)
        query += rdf.sparql_filter (f"{item_type}_id", item_id)
        query += rdf.sparql_filter ("title",           title,  escape=True)

        query += "}\n"
        query += rdf.sparql_suffix (order, order_direction, limit, None)

        return self.__run_query(query)

    def references (self, order=None, order_direction=None, limit=10,
                    item_id=None, account_id=None, item_type="article"):

        prefix = "Article" if item_type == "article" else "Collection"
        query  = f"""\
{self.default_prefixes}
SELECT DISTINCT ?id ?url
WHERE {{
  GRAPH <{self.state_graph}> {{
    ?row             rdf:type                 sg:{prefix}Reference .
    ?row             col:id                   ?id .
    ?row             col:{item_type}_id       ?{item_type}_id .
    ?row             col:url                  ?url .
"""

        if item_id is not None:
            query += f"""\
    ?item            rdf:type                 sg:{prefix} .
    ?item            col:{item_type}_id       ?{item_type}_id .
    ?item            col:account_id           ?account_id .
  }}
"""

        query += rdf.sparql_filter ("account_id",      account_id)
        query += rdf.sparql_filter (f"{item_type}_id", item_id)

        query += "}\n"
        query += rdf.sparql_suffix (order, order_direction, limit, None)

        return self.__run_query(query)

    ## ------------------------------------------------------------------------
    ## INSERT METHODS
    ## ------------------------------------------------------------------------

    def insert_article (self, title,
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
                        funding_list=[],
                        tags=[],
                        references=[],
                        categories=[],
                        authors=[],
                        custom_fields=[],
                        private_links=[],
                        files=[],
                        embargo_options=[]):
        """Procedure to insert an article to the state graph."""

        graph = Graph()

        if article_id is None:
            article_id = self.ids.next_id("article")

        article_uri = rdf.ROW[str(article_id)]

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
        for category in categories:
            category_id = self.insert_category (
                category_id = conv.value_or_none (category, "id"),
                title       = conv.value_or_none (category, "title"),
                parent_id   = conv.value_or_none (category, "parent_id"),
                source_id   = conv.value_or_none (category, "source_id"),
                taxonomy    = conv.value_or_none (category, "taxonomy"))
            self.insert_article_category (article_id, category_id)

        ## EMBARGOS
        ## --------------------------------------------------------------------
        for embargo in embargo_options:
            self.insert_embargo (
                embargo_id   = conv.value_or_none (embargo, "id"),
                article_id   = article_id,
                embargo_type = conv.value_or_none (embargo, "type"),
                ip_name      = conv.value_or_none (embargo, "ip_name"))

        ## LICENSE
        ## --------------------------------------------------------------------
        # Note: The license_id is also stored as a column in the article.
        self.insert_license (
            license_id = license_id,
            name       = conv.value_or_none (license, "name"),
            url        = conv.value_or_none (license, "url"))

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
            file_id = self.insert_file (
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
                upload_token  = conv.value_or_none (file_data, "upload_token"))
            self.insert_article_file (article_id, file_id)

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
        graph.add ((article_uri, rdf.COL["title"], Literal(title)))

        rdf.add (graph, article_uri, rdf.COL["description"],    description)
        rdf.add (graph, article_uri, rdf.COL["defined_type"],   defined_type)
        rdf.add (graph, article_uri, rdf.COL["funding"],        funding)
        rdf.add (graph, article_uri, rdf.COL["license_id"],     license_id)
        rdf.add (graph, article_uri, rdf.COL["doi"],            doi)
        rdf.add (graph, article_uri, rdf.COL["handle"],         handle)
        rdf.add (graph, article_uri, rdf.COL["resource_doi"],   resource_doi)
        rdf.add (graph, article_uri, rdf.COL["resource_title"], resource_title)
        rdf.add (graph, article_uri, rdf.COL["group_id"],       group_id)

        query = self.__insert_query_for_graph (graph)
        if self.__run_query(query):
            logging.info ("Inserted article %d", article_id)
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

        account_uri = rdf.ROW[str(account_id)]

        graph.add ((account_uri, RDF.type,      rdf.SG["Account"]))
        graph.add ((account_uri, rdf.COL["id"], Literal(account_id)))

        rdf.add (graph, account_uri, rdf.COL["active"],                active)
        rdf.add (graph, account_uri, rdf.COL["email"],                 email)
        rdf.add (graph, account_uri, rdf.COL["first_name"],            first_name)
        rdf.add (graph, account_uri, rdf.COL["last_name"],             last_name)
        rdf.add (graph, account_uri, rdf.COL["institution_user_id"],   institution_user_id)
        rdf.add (graph, account_uri, rdf.COL["institution_id"],        institution_id)
        rdf.add (graph, account_uri, rdf.COL["pending_quota_request"], pending_quota_request)
        rdf.add (graph, account_uri, rdf.COL["used_quota_public"],     used_quota_public)
        rdf.add (graph, account_uri, rdf.COL["used_quota_private"],    used_quota_private)
        rdf.add (graph, account_uri, rdf.COL["used_quota"],            used_quota)
        rdf.add (graph, account_uri, rdf.COL["maximum_file_size"],     maximum_file_size)
        rdf.add (graph, account_uri, rdf.COL["quota"],                 quota)
        rdf.add (graph, account_uri, rdf.COL["modified_date"],         modified_date)
        rdf.add (graph, account_uri, rdf.COL["created_date"],          created_date)

        query = self.__insert_query_for_graph (graph)
        if self.__run_query(query):
            return account_id

        return None

    def insert_institution (self, name, institution_id=None):
        """Procedure to add an institution to the state graph."""

        graph = Graph()

        if institution_id is None:
            institution_id = self.ids.next_id("institution")

        institution_uri = rdf.ROW[str(institution_id)]

        graph.add ((institution_uri, RDF.type,      rdf.SG["Institution"]))
        graph.add ((institution_uri, rdf.COL["id"], Literal(institution_id)))

        rdf.add (graph, institution_uri, rdf.COL["name"], name)

        query = self.__insert_query_for_graph (graph)
        if self.__run_query(query):
            return institution_id

        return None

    def insert_author (self, author_id=None, is_active=None, first_name=None,
                       last_name=None, full_name=None, institution_id=None,
                       job_title=None, is_public=None, url_name=None,
                       orcid_id=None):
        """Procedure to add an author to the state graph."""

        graph = Graph()

        if author_id is None:
            author_id = self.ids.next_id("author")

        author_uri = rdf.ROW[str(author_id)]

        graph.add ((author_uri, RDF.type,      rdf.SG["Author"]))
        graph.add ((author_uri, rdf.COL["id"], Literal(author_id)))

        rdf.add (graph, author_uri, rdf.COL["institution_id"], institution_id)
        rdf.add (graph, author_uri, rdf.COL["is_active"],      is_active)
        rdf.add (graph, author_uri, rdf.COL["is_public"],      is_public)
        rdf.add (graph, author_uri, rdf.COL["first_name"],     first_name)
        rdf.add (graph, author_uri, rdf.COL["last_name"],      last_name)
        rdf.add (graph, author_uri, rdf.COL["full_name"],      full_name)
        rdf.add (graph, author_uri, rdf.COL["job_title"],      job_title)
        rdf.add (graph, author_uri, rdf.COL["url_name"],       url_name)
        rdf.add (graph, author_uri, rdf.COL["orcid_id"],       orcid_id)

        query = self.__insert_query_for_graph (graph)
        if self.__run_query(query):
            return author_id

        return None

    def insert_timeline (self, revision=None, first_online=None,
                         publisher_publication=None, publisher_acceptance=None,
                         posted=None, submission=None):
        """Procedure to add a timeline to the state graph."""

        graph        = Graph()
        timeline_id  = self.ids.next_id("timeline")
        timeline_uri = rdf.ROW[str(timeline_id)]

        graph.add ((timeline_uri, RDF.type,      rdf.SG["Timeline"]))
        graph.add ((timeline_uri, rdf.COL["id"], Literal(timeline_id)))

        rdf.add (graph, timeline_uri, rdf.COL["revision"],             revision)
        rdf.add (graph, timeline_uri, rdf.COL["firstOnline"],          first_online)
        rdf.add (graph, timeline_uri, rdf.COL["publisherPublication"], publisher_publication)
        rdf.add (graph, timeline_uri, rdf.COL["publisherAcceptance"],  publisher_acceptance)
        rdf.add (graph, timeline_uri, rdf.COL["posted"],               posted)
        rdf.add (graph, timeline_uri, rdf.COL["submission"],           submission)

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

        category_uri = rdf.ROW[str(category_id)]

        graph.add ((category_uri, RDF.type,      rdf.SG["Category"]))
        graph.add ((category_uri, rdf.COL["id"], Literal(category_id)))

        rdf.add (graph, category_uri, rdf.COL["title"], title)
        rdf.add (graph, category_uri, rdf.COL["parent_id"], parent_id)
        rdf.add (graph, category_uri, rdf.COL["source_id"], source_id)
        rdf.add (graph, category_uri, rdf.COL["taxonomy"], taxonomy)

        query = self.__insert_query_for_graph (graph)
        if self.__run_query(query):
            return category_id

        return None

    def insert_article_category (self, article_id, category_id):
        """Procedure to add a link between an article and a category."""

        graph = Graph()

        link_id  = self.ids.next_id("article_category")
        link_uri = rdf.ROW[str(category_id)]

        graph.add ((link_uri, RDF.type,               rdf.SG["ArticleCategory"]))
        graph.add ((link_uri, rdf.COL["id"],          Literal(link_id)))
        graph.add ((link_uri, rdf.COL["category_id"], Literal(category_id)))
        graph.add ((link_uri, rdf.COL["article_id"],  Literal(article_id)))

        query = self.__insert_query_for_graph (graph)
        if self.__run_query(query):
            return link_id

        return None

    def insert_article_author (self, article_id, author_id):
        """Procedure to add a link between an article and a author."""

        graph = Graph()

        link_id  = self.ids.next_id("article_author")
        link_uri = rdf.ROW[str(author_id)]

        graph.add ((link_uri, RDF.type,              rdf.SG["ArticleAuthor"]))
        graph.add ((link_uri, rdf.COL["id"],         Literal(link_id)))
        graph.add ((link_uri, rdf.COL["author_id"],  Literal(author_id)))
        graph.add ((link_uri, rdf.COL["article_id"], Literal(article_id)))

        query = self.__insert_query_for_graph (graph)
        if self.__run_query(query):
            return link_id

        return None

    def insert_article_file (self, article_id, file_id):
        """Procedure to add a link between an article and a file."""

        graph = Graph()

        link_id  = self.ids.next_id("article_file")
        link_uri = rdf.ROW[str(file_id)]

        graph.add ((link_uri, RDF.type,              rdf.SG["ArticleFile"]))
        graph.add ((link_uri, rdf.COL["id"],         Literal(link_id)))
        graph.add ((link_uri, rdf.COL["file_id"],    Literal(file_id)))
        graph.add ((link_uri, rdf.COL["article_id"], Literal(article_id)))

        query = self.__insert_query_for_graph (graph)
        if self.__run_query(query):
            return link_id

        return None

    def insert_tag (self, tag, item_id=None, item_type=None):
        """Procedure to add an tag to the state graph."""

        prefix  = item_type.capitalize()
        graph   = Graph()
        tag_id  = self.ids.next_id("tag")
        tag_uri = rdf.ROW[str(tag_id)]

        graph.add ((tag_uri, RDF.type,                   rdf.SG[f"{prefix}Tag"]))
        graph.add ((tag_uri, rdf.COL["id"],              Literal(tag_id)))
        graph.add ((tag_uri, rdf.COL[f"{item_type}_id"], Literal(item_id)))

        rdf.add (graph, tag_uri, rdf.COL["tag"],                tag)

        query = self.__insert_query_for_graph (graph)
        if self.__run_query(query):
            return tag_id

        return None

    def insert_reference (self, url, item_id=None, item_type=None):
        """Procedure to add an reference to the state graph."""

        prefix        = item_type.capitalize()
        graph         = Graph()
        reference_id  = self.ids.next_id("reference")
        reference_uri = rdf.ROW[str(item_id)]

        graph.add ((reference_uri, RDF.type,                   rdf.SG[f"{prefix}Reference"]))
        graph.add ((reference_uri, rdf.COL["id"],              Literal(reference_id)))
        graph.add ((reference_uri, rdf.COL[f"{item_type}_id"], Literal(item_id)))
        graph.add ((reference_uri, rdf.COL["url"],             Literal(url)))

        query = self.__insert_query_for_graph (graph)
        if self.__run_query(query):
            return reference_id

        return None

    def insert_funding (self, title=None, grant_code=None, funder_name=None,
                        is_user_defined=None, url=None, item_id=None,
                        item_type=None):
        """Procedure to add an funding to the state graph."""

        prefix      = item_type.capitalize()
        graph       = Graph()
        funding_id  = self.ids.next_id("funding")
        funding_uri = rdf.ROW[str(item_id)]

        graph.add ((funding_uri, RDF.type,                   rdf.SG[f"{prefix}Funding"]))
        graph.add ((funding_uri, rdf.COL["id"],              Literal(funding_id)))
        graph.add ((funding_uri, rdf.COL[f"{item_type}_id"], Literal(item_id)))

        rdf.add (graph, funding_uri, rdf.COL["title"],           title)
        rdf.add (graph, funding_uri, rdf.COL["grant_code"],      grant_code)
        rdf.add (graph, funding_uri, rdf.COL["funder_name"],     funder_name)
        rdf.add (graph, funding_uri, rdf.COL["is_user_defined"], is_user_defined)
        rdf.add (graph, funding_uri, rdf.COL["url"],             url)

        query = self.__insert_query_for_graph (graph)
        if self.__run_query(query):
            return funding_id

        return None

    def insert_file (self, file_id=None, name=None, size=None,
                     is_link_only=None, download_url=None, supplied_md5=None,
                     computed_md5=None, viewer_type=None, preview_state=None,
                     status=None, upload_url=None, upload_token=None):
        """Procedure to add an file to the state graph."""

        graph    = Graph()
        file_id  = self.ids.next_id("file")
        file_uri = rdf.ROW[str(file_id)]

        graph.add ((file_uri, RDF.type,               rdf.SG["File"]))
        graph.add ((file_uri, rdf.COL["id"],          Literal(file_id)))

        rdf.add (graph, file_uri, rdf.COL["name"],          name)
        rdf.add (graph, file_uri, rdf.COL["size"],          size)
        rdf.add (graph, file_uri, rdf.COL["is_link_only"],  is_link_only)
        rdf.add (graph, file_uri, rdf.COL["download_url"],  download_url)
        rdf.add (graph, file_uri, rdf.COL["supplied_md5"],  supplied_md5)
        rdf.add (graph, file_uri, rdf.COL["computed_md5"],  computed_md5)
        rdf.add (graph, file_uri, rdf.COL["viewer_type"],   viewer_type)
        rdf.add (graph, file_uri, rdf.COL["preview_state"], preview_state)
        rdf.add (graph, file_uri, rdf.COL["status"],        status)
        rdf.add (graph, file_uri, rdf.COL["upload_url"],    upload_url)
        rdf.add (graph, file_uri, rdf.COL["upload_token"],  upload_token)

        query = self.__insert_query_for_graph (graph)
        if self.__run_query(query):
            return file_id

        return None

    def insert_license (self, license_id, name=None, url=None):
        """Procedure to add an license to the state graph."""

        graph    = Graph()
        license_uri = rdf.ROW[str(license_id)]

        graph.add ((license_uri, RDF.type,               rdf.SG["License"]))
        graph.add ((license_uri, rdf.COL["id"],          Literal(license_id)))

        rdf.add (graph, license_uri, rdf.COL["name"],  name)
        rdf.add (graph, license_uri, rdf.COL["url"],   url)

        query = self.__insert_query_for_graph (graph)
        if self.__run_query(query):
            return license_id

        return None

    def insert_private_link (self, private_link_id=None, is_active=None,
                                 expires_date=None, item_id=None,
                                 item_type="article"):

        prefix   = item_type.capitalize()
        graph    = Graph()
        link_uri = rdf.ROW[str(private_link_id)]

        graph.add ((link_uri, RDF.type,      rdf.SG[f"{prefix}PrivateLink"]))
        graph.add ((link_uri, rdf.COL["id"], Literal(private_link_id)))

        rdf.add (graph, link_uri, rdf.COL["is_active"],       is_active)
        rdf.add (graph, link_uri, rdf.COL["expires_date"],    expires_date)
        rdf.add (graph, link_uri, rdf.COL[f"{item_type}_id"], item_id)

        query = self.__insert_query_for_graph (graph)
        if self.__run_query(query):
            return private_link_id

        return None

    def insert_embargo (self, embargo_id, article_id, embargo_type=None, ip_name=None):
        """Procedure to add an license to the state graph."""

        graph    = Graph()
        embargo_uri = rdf.ROW[str(embargo_id)]

        graph.add ((embargo_uri, RDF.type,               rdf.SG["ArticleEmbargoOption"]))
        graph.add ((embargo_uri, rdf.COL["id"],          Literal(embargo_id)))
        graph.add ((embargo_uri, rdf.COL["article_id"],  Literal(article_id)))

        rdf.add (graph, embargo_uri, rdf.COL["type"],    embargo_type)
        rdf.add (graph, embargo_uri, rdf.COL["ip_name"], ip_name)

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
        custom_field_uri = rdf.ROW[str(custom_field_id)]

        graph.add ((custom_field_uri, RDF.type,                   rdf.SG[f"{prefix}CustomField"]))
        graph.add ((custom_field_uri, rdf.COL["id"],              Literal(custom_field_id)))
        graph.add ((custom_field_uri, rdf.COL[f"{item_type}_id"], Literal(item_id)))

        rdf.add (graph, custom_field_uri, rdf.COL["name"],          name)
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

        query = f"""\
{self.default_prefixes}
DELETE {{
  GRAPH <{self.state_graph}> {{
    ?article  ?predicate     ?object .
  }}
}}
WHERE {{
  GRAPH <{self.state_graph}> {{
    ?article  rdf:type       sg:Article .
    ?article  col:id         {article_id} .
    ?article  col:account_id {account_id} .
    ?article  ?predicate     ?object .
  }}
}}"""
        return self.__run_query(query)

    def update_article (self, article_id):
        return False

    def delete_article_embargo (self, article_id, account_id):
        """Procedure to lift the embargo on an article."""

        query = f"""\
{self.default_prefixes}
DELETE {{
  GRAPH <{self.state_graph}> {{
    ?embargo  ?predicate     ?object .
  }}
}}
WHERE {{
  GRAPH <{self.state_graph}> {{
    ?article  rdf:type        sg:Article .
    ?article  col:id          {article_id} .
    ?article  col:account_id  {account_id} .

    ?embargo  rdf:type        sg:ArticleEmbargoOption .
    ?embargo  col:article_id  {article_id} .
    ?embargo  ?predicate      ?object .
  }}
}}"""
        return self.__run_query(query)
