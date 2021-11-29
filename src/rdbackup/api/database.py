"""
This module provides the communication with the SPARQL endpoint to provide
data for the API server.
"""

import logging
from urllib.error import URLError
from SPARQLWrapper import SPARQLWrapper, JSON
from rdflib import Graph, Literal, RDF, XSD, URIRef, Namespace
from rdbackup.utils import counters
from rdbackup.utils import rdf

class UnknownDatabaseState(Exception):
    """Raised when the database is not queryable."""
    pass

class EmptyDatabase(Exception):
    """Raised when the database is empty."""
    pass

class SparqlInterface:

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

        current_article_id     = 0
        current_collection_id  = 0
        current_author_id      = 0
        current_account_id     = 0
        current_file_id        = 0
        current_category_id    = 0
        current_project_id     = 0
        current_timeline_id    = 0
        current_institution_id = 0
        current_tag_id         = 0

        # Set the article_id and collection_id iterator to continue
        # where we left off last time the program was run.
        try:
            current_article_id     = self.__highest_id (item_type="article")
            current_collection_id  = self.__highest_id (item_type="collection")
            current_author_id      = self.__highest_id (item_type="author")
            current_account_id     = self.__highest_id (item_type="account")
            current_file_id        = self.__highest_id (item_type="file")
            current_category_id    = self.__highest_id (item_type="category")
            current_project_id     = self.__highest_id (item_type="project")
            current_timeline_id    = self.__highest_id (item_type="timeline")
            current_institution_id = self.__highest_id (item_type="institution")
            current_tag_id         = self.__highest_id (item_type="tag")

            if (current_article_id     is None or
                current_collection_id  is None or
                current_author_id      is None or
                current_account_id     is None or
                current_file_id        is None or
                current_category_id    is None or
                current_project_id     is None or
                current_timeline_id    is None or
                current_institution_id is None or
                current_tag_id         is None):
                logging.error ("Cannot determine the database state.")
                raise UnknownDatabaseState

        except EmptyDatabase:
            logging.warning ("It looks like the database is empty.")

        self.ids.set_article_id (current_article_id)
        self.ids.set_collection_id (current_collection_id)
        self.ids.set_author_id (current_author_id)
        self.ids.set_account_id (current_account_id)
        self.ids.set_file_id (current_file_id)
        self.ids.set_category_id (current_category_id)
        self.ids.set_project_id (current_project_id)
        self.ids.set_timeline_id (current_timeline_id)
        self.ids.set_institution_id (current_institution_id)
        self.ids.set_tag_id (current_tag_id)

        logging.info ("Article enumerator set to %d", current_article_id)
        logging.info ("Collection enumerator set to %d", current_collection_id)
        logging.info ("Author enumerator set to %d", current_author_id)
        logging.info ("Account enumerator set to %d", current_account_id)
        logging.info ("File enumerator set to %d", current_file_id)
        logging.info ("Category enumerator set to %d", current_category_id)
        logging.info ("Project enumerator set to %d", current_project_id)
        logging.info ("Timeline enumerator set to %d", current_timeline_id)
        logging.info ("Institution enumerator set to %d", current_institution_id)
        logging.info ("Tag enumerator set to %d", current_tag_id)

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
            else:
                logging.error("Not a typed-literal: %s", record[item]['type'])
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
        except IndexError:
            raise EmptyDatabase
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

    def article_versions (self, limit=10, offset=0, order=None,
                          order_direction=None):
        if not order_direction:
            order_direction = "DESC"
        if order is None:
            order="?id"
        else:
            order = f"?{order}"

        query = f"""\
{self.default_prefixes}
SELECT DISTINCT ?id ?version ?url
WHERE {{
    ?article rdf:type    sg:Article .
    ?article col:id      ?id .
    ?article col:version ?version .
    ?article col:url     ?url .
}}
ORDER BY {order_direction}({order})
LIMIT {limit}
"""
        if offset is not None:
            query += f"OFFSET {offset}"

        return self.__run_query (query)

    def articles (self, limit=10, offset=None, order=None,
                  order_direction=None, institution=None,
                  published_since=None, modified_since=None,
                  group=None, resource_doi=None, item_type=None,
                  doi=None, handle=None, account_id=None,
                  search_for=None, article_id=None,
                  collection_id=None):

        if order_direction is None:
            order_direction = "DESC"
        if limit is None:
            limit = 10
        if order is None:
            order="?id"
        else:
            order = f"?{order}"

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

        if institution is not None:
            query += f"FILTER (?institution_id={institution})\n"

        if published_since is not None:
            query += "FILTER (BOUND(?published_date))\n"
            query += "FILTER (STR(?published_date) != \"NULL\")\n"
            query += f"FILTER (STR(?published_date) > \"{published_since}\")\n"

        if modified_since is not None:
            query += "FILTER (BOUND(?modified_date))\n"
            query += "FILTER (STR(?modified_date) != \"NULL\")\n"
            query += f"FILTER (STR(?modified_date) > \"{modified_since}\")\n"

        if group is not None:
            query += f"FILTER (?group_id = {group})\n"

        if resource_doi is not None:
            query += f"FILTER (STR(?resource_doi) = \"{resource_doi}\")\n"

        if item_type is not None:
            query += f"FILTER (?defined_type = {item_type})\n"

        if doi is not None:
            query += f"FILTER (STR(?doi) = \"{doi}\")\n"

        if handle is not None:
            query += f"FILTER (STR(?handle) = \"{handle}\")\n"

        if article_id is not None:
            query += f"FILTER (?id = {article_id})\n"

        if account_id is None:
            query += "FILTER (?is_public = 1)\n"
        else:
            query += f"FILTER (?account_id = {account_id})\n"

        if search_for is not None:
            query += f"FILTER(CONTAINS(?title, \"{search_for}\"))\n"
            query += f"FILTER(CONTAINS(?resource_title, \"{search_for}\"))\n"
            query += f"FILTER(CONTAINS(?description, \"{search_for}\"))\n"
            query += f"FILTER(CONTAINS(?citation, \"{search_for}\"))\n"

        query += "}\n"

        if order is not None:
            query += f"""\
ORDER BY {order_direction}({order})
LIMIT {limit}
"""
        if offset is not None:
            query += f"OFFSET {offset}"

        return self.__run_query (query)

    def authors (self, first_name=None, full_name=None, group_id=None,
                 author_id=None, institution_id=None, is_active=None,
                 is_public=None, job_title=None, last_name=None,
                 orcid_id=None, url_name=None, limit=10, order=None,
                 order_direction=None, item_id=None,
                 account_id=None, item_type="article"):

        prefix = "Article" if item_type == "article" else "Collection"

        if order_direction is None:
            order_direction = "ASC"
        if limit is None:
            limit = 10
        if order is None:
            order="?full_name"
        else:
            order = f"?{order}"

        query = f"""\
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

        if first_name is not None:
            query += f"FILTER (STR(?first_name) = \"{first_name}\")\n"

        if full_name is not None:
            query += f"FILTER (STR(?full_name) = \"{full_name}\")\n"

        if group_id is not None:
            query += f"FILTER (?group_id = {group_id})\n"

        if author_id is not None:
            query += f"FILTER (?id = {author_id})\n"

        if institution_id is not None:
            query += f"FILTER (?institution_id = {institution_id})\n"

        if is_active is not None:
            query += f"FILTER (?is_active = {is_active})\n"

        if is_public is not None:
            query += f"FILTER (?is_public = {is_public})\n"

        if job_title is not None:
            query += f"FILTER (?job_title = \"{job_title}\")\n"

        if last_name is not None:
            query += f"FILTER (?last_name = \"{last_name}\")\n"

        if orcid_id is not None:
            query += f"FILTER (?orcid_id = \"{orcid_id}\")\n"

        if url_name is not None:
            query += f"FILTER (?url_name = \"{url_name}\")\n"

        query += "}\n"

        if order is not None:
            query += f"""\
ORDER BY {order_direction}({order})
LIMIT {limit}
"""

        return self.__run_query(query)

    def insert_article (self, title=None, description=None, tags=None,
                        keywords=None, references=None, categories=None,
                        authors=None, custom_fields=None, defined_type=None,
                        funding=None, funding_list=None, license_id=None, doi=None,
                        handle=None, resource_doi=None, resource_title=None,
                        first_online=None, publisher_publication=None,
                        publisher_acceptance=None, submission=None, posted=None,
                        revision=None, group_id=None):
        return False

    def article_files (self, name=None, size=None, is_link_only=None,
                       file_id=None, download_url=None, supplied_md5=None,
                       computed_md5=None, viewer_type=None, preview_state=None,
                       status=None, upload_url=None, upload_token=None,
                       order=None, order_direction=None, limit=None,
                       article_id=None, account_id=None):

        if order_direction is None:
            order_direction = "DESC"
        if limit is None:
            limit = 10
        if order is None:
            order="?id"
        else:
            order = f"?{order}"

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
            query += """\
    ?article           col:account_id           ?account_id .
"""

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
        if name is not None:
            query += f"FILTER (STR(?name) = \"{name}\")\n"

        if size is not None:
            query += f"FILTER (?size = {size})\n"

        if is_link_only is not None:
            query += f"FILTER (?is_link_only = {is_link_only})\n"

        if file_id is not None:
            query += f"FILTER (?id = {file_id})\n"

        if download_url is not None:
            query += f"FILTER (STR(?download_url) = \"{download_url}\")\n"

        if supplied_md5 is not None:
            query += f"FILTER (STR(?supplied_md5) = \"{supplied_md5}\")\n"

        if computed_md5 is not None:
            query += f"FILTER (STR(?computed_md5) = \"{computed_md5}\")\n"

        if viewer_type is not None:
            query += f"FILTER (STR(?viewer_type) = \"{viewer_type}\")\n"

        if preview_state is not None:
            query += f"FILTER (STR(?preview_state) = \"{preview_state}\")\n"

        if status is not None:
            query += f"FILTER (STR(?status) = \"{status}\")\n"

        if upload_url is not None:
            query += f"FILTER (STR(?upload_url) = \"{upload_url}\")\n"

        if upload_token is not None:
            query += f"FILTER (STR(?upload_token) = \"{upload_token}\")\n"

        query += "}\n"

        if order is not None:
            query += f"""\
ORDER BY {order_direction}({order})
LIMIT {limit}
"""

        return self.__run_query(query)

    def custom_fields (self, name=None, value=None, default_value=None,
                       field_id=None, placeholder=None, max_length=None,
                       min_length=None, field_type=None, is_multiple=None,
                       is_mandatory=None, order=None, order_direction=None,
                       limit=None, item_id=None, item_type="article"):

        prefix = "Article" if item_type == "article" else "Collection"

        if order_direction is None:
            order_direction = "DESC"
        if order is None:
            order="?name"
        if limit is None:
            limit = 10

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
        if name is not None:
            query += f"FILTER (STR(?name) = \"{name}\")\n"

        if value is not None:
            query += f"FILTER (STR(?value) = \"{value}\")\n"

        if default_value is not None:
            query += f"FILTER (STR(?default_value) = \"{default_value}\")\n"

        if field_id is not None:
            query += f"FILTER (?id = {field_id})\n"

        if placeholder is not None:
            query += f"FILTER (STR(?placeholder) = \"{placeholder}\")\n"

        if max_length is not None:
            query += f"FILTER (?max_length = {max_length})\n"

        if min_length is not None:
            query += f"FILTER (?min_length = {min_length})\n"

        if field_type is not None:
            query += f"FILTER (STR(?field_type) = \"{field_type}\")\n"

        if is_multiple is not None:
            query += f"FILTER (?is_multiple = {is_multiple})\n"

        if is_mandatory is not None:
            query += f"FILTER (?is_mandatory = {is_mandatory})\n"

        query += "}\n"

        if order is not None:
            query += f"""\
ORDER BY {order_direction}({order})
LIMIT {limit}
"""
        return self.__run_query(query)

    def article_embargo_options (self, ip_name=None, embargo_type=None,
                                 order=None, order_direction=None,
                                 limit=None, article_id=None):

        if order_direction is None:
            order_direction = "DESC"
        if order is None:
            order="?id"
        if limit is None:
            limit = 10

        query = f"""\
{self.default_prefixes}
SELECT DISTINCT ?id ?article_id ?type ?ip_name
WHERE {{
  GRAPH <{self.state_graph}> {{
    ?field             rdf:type                 sg:ArticleEmbargoOption .
    ?field             col:id                   ?id .
    OPTIONAL {{ ?field  col:type                 ?type . }}
    OPTIONAL {{ ?field  col:ip_name              ?ip_name . }}
"""

        if article_id is not None:
            query += f"    ?field  col:article_id  {article_id} .\n"

        query += "  }\n"

        if ip_name is not None:
            query += f"  FILTER (STR(?ip_name) = \"{ip_name}\")\n"

        if embargo_type is not None:
            query += f"  FILTER (STR(?type) = \"{embargo_type}\")\n"

        query += "}\n"

        if order is not None:
            query += f"""\
ORDER BY {order_direction}({order})
LIMIT {limit}
"""
        return self.__run_query(query)

    def tags (self, order=None, order_direction=None, limit=None, item_id=None, item_type="article"):

        prefix = "Article" if item_type == "article" else "Collection"

        if order_direction is None:
            order_direction = "DESC"
        if order is None:
            order="?id"
        if limit is None:
            limit = 10

        query = f"""\
{self.default_prefixes}
SELECT DISTINCT ?id ?tag
WHERE {{
  GRAPH <{self.state_graph}> {{
    ?row             rdf:type                 sg:{prefix}Tag .
    ?row             col:id                   ?id .
    ?row             col:tag                  ?tag .
"""

        if item_id is not None:
            query += f"""\
    ?row             col:{item_type}_id       {item_id} .
"""

        query += """\
  }
}
"""
        if order is not None:
            query += f"""\
ORDER BY {order_direction}({order})
LIMIT {limit}
"""

        return self.__run_query(query)

    def categories (self, title=None, order=None, order_direction=None,
                    limit=None, item_id=None, account_id=None,
                    item_type="article"):
        prefix = "Article" if item_type == "article" else "Collection"

        if order_direction is None:
            order_direction = "DESC"
        if order is None:
            order="?id"
        if limit is None:
            limit = 10

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
            query += """\
    ?item            col:account_id           ?account_id .
"""

        query += "  }\n"

        if title is not None:
            query += f"FILTER (STR(?title) = \"{title}\")\n"

        query += "}\n"

        if order is not None:
            query += f"""\
ORDER BY {order_direction}({order})
LIMIT {limit}
"""

        return self.__run_query(query)

    ## ------------------------------------------------------------------------
    ## COLLECTIONS
    ## ------------------------------------------------------------------------

    def collections (self, limit=10, offset=None, order=None,
                     order_direction=None, institution=None,
                     published_since=None, modified_since=None, group=None,
                     resource_doi=None, resource_id=None, doi=None, handle=None,
                     account_id=None, search_for=None, collection_id=None):

        if order_direction is None:
            order_direction = "DESC"
        if limit is None:
            limit = 10
        if order is None:
            order="?id"
        else:
            order = f"?{order}"

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

        if institution is not None:
            query += f"FILTER (?institution_id={institution})\n"

        if published_since is not None:
            query += "FILTER (BOUND(?published_date))\n"
            query += "FILTER (STR(?published_date) != \"NULL\")\n"
            query += f"FILTER (STR(?published_date) > \"{published_since}\")\n"

        if modified_since is not None:
            query += "FILTER (BOUND(?modified_date))\n"
            query += "FILTER (STR(?modified_date) != \"NULL\")\n"
            query += f"FILTER (STR(?modified_date) > \"{modified_since}\")\n"

        if group is not None:
            query += f"FILTER (?group_id = {group})\n"

        if resource_doi is not None:
            query += f"FILTER (STR(?resource_doi) = \"{resource_doi}\")\n"

        if resource_id is not None:
            query += f"FILTER (STR(?resource_id) = \"{resource_id}\")\n"

        if doi is not None:
            query += f"FILTER (STR(?doi) = \"{doi}\")\n"

        if handle is not None:
            query += f"FILTER (STR(?handle) = \"{handle}\")\n"

        if collection_id is not None:
            query += f"FILTER (?id = {collection_id})\n"

        if account_id is None:
            query += "FILTER (?is_public = 1)\n"
        else:
            query += f"FILTER (?account_id = {account_id})\n"

        if search_for is not None:
            query += f"FILTER(CONTAINS(?title, \"{search_for}\"))\n"
            query += f"FILTER(CONTAINS(?resource_title, \"{search_for}\"))\n"
            query += f"FILTER(CONTAINS(?description, \"{search_for}\"))\n"
            query += f"FILTER(CONTAINS(?citation, \"{search_for}\"))\n"

        query += "}\n"

        if order is not None:
            query += f"""\
ORDER BY {order_direction}({order})
LIMIT {limit}
"""

        if offset is not None:
            query += f"OFFSET {offset}"

        return self.__run_query(query)

    def fundings (self, title=None, order=None, order_direction=None,
                  limit=None, item_id=None, account_id=None,
                  item_type="article"):

        prefix = "Article" if item_type == "article" else "Collection"

        if order_direction is None:
            order_direction = "DESC"
        if order is None:
            order="?id"
        if limit is None:
            limit = 10

        query = f"""\
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
    ?item           col:{item_type}_id        ?{item_type}_id .
"""

        if (item_id is not None) and (account_id is not None):
            query += "    ?item  col:account_id  ?account_id .\n"

        query += "  }\n"

        if item_id is not None:
            query += f"FILTER(?{item_type}_id = {item_id})\n"

        if title is not None:
            query += f"FILTER (STR(?title) = \"{title}\")\n"

        query += "}\n"

        if order is not None:
            query += f"""\
ORDER BY {order_direction}({order})
LIMIT {limit}
"""

        return self.__run_query(query)

    def references (self, order=None, order_direction=None, limit=None,
                    item_id=None, account_id=None, item_type="article"):

        prefix = "Article" if item_type == "article" else "Collection"

        if order_direction is None:
            order_direction = "DESC"
        if order is None:
            order="?id"
        if limit is None:
            limit = 10

        query = f"""\
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
"""

        if (item_id is not None) and (account_id is not None):
            query += """\
    ?item            col:account_id           ?account_id .
"""

        query += "  }\n"

        if item_id is not None:
            query += f"FILTER(?{item_type}_id = {item_id})\n"

        query += "}\n"

        if order is not None:
            query += f"""\
ORDER BY {order_direction}({order})
LIMIT {limit}
"""

        return self.__run_query(query)
