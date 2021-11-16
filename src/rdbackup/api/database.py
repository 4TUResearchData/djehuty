from SPARQLWrapper import SPARQLWrapper, JSON
import json
import logging

class SparqlInterface:

    def __init__ (self):
        self.endpoint = "http://127.0.0.1:8890/sparql"
        self.sparql = SPARQLWrapper(self.endpoint)
        self.sparql.setReturnFormat(JSON)
        self.default_prefixes = """\
PREFIX col: <sg://0.99.12/table2rdf/Column/>
PREFIX sg:  <https://sparqling-genomics.org/0.99.12/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        """

    def normalize_binding (self, record):
        for item in record:
            if record[item]["type"] == "typed-literal":
                if record[item]["datatype"] == "http://www.w3.org/2001/XMLSchema#integer":
                    record[item] = int(record[item]["value"])
                elif record[item]["datatype"] == "http://www.w3.org/2001/XMLSchema#string":
                    if record[item]["value"] == "NULL":
                        record[item] = None
                    else:
                        record[item] = record[item]["value"]
            else:
                print(f"Not a typed-literal: {record[item]['type']}")
        return record

    def article_versions (self, limit=10, offset=0, order=None,
                          order_direction=None):
        if not order_direction:
            order_direction = "DESC"
        if not order:
            order="?id"

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

        self.sparql.setQuery(query)
        results = None
        try:
            results = self.sparql.query().convert()
        except:
            logging.error(f"SPARQL query failed.")
            logging.error(f"Query:\n{query}\n")

        return results

    def articles (self, limit=10, offset=None, order=None,
                  order_direction=None, institution=None,
                  published_since=None, modified_since=None,
                  group=None, resource_doi=None, item_type=None,
                  doi=None, handle=None, account_id=None,
                  search_for=None, id=None):

        if order_direction is None:
            order_direction = "DESC"
        if order is None:
            order="?id"
        if limit is None:
            limit = 10

        query = f"""\
{self.default_prefixes}
SELECT DISTINCT ?account_id ?authors_id ?citation
                ?confidential_reason ?created_date
                ?custom_fields_id ?defined_type
                ?defined_type_name ?description
                ?doi ?embargo_date ?embargo_options_id
                ?embargo_reason ?embargo_title
                ?embargo_type ?figshare_url ?files_id
                ?funding ?funding_id ?group_id
                ?has_linked_file ?id ?institution_id
                ?is_active ?is_confidential ?is_embargoed
                ?is_metadata_record ?is_public ?license_id
                ?license_name ?license_url
                ?metadata_reason ?modified_date
                ?published_date ?references_id
                ?resource_doi ?resource_title ?size
                ?status ?tags_id ?thumb ?timeline_posted
                ?timeline_publisher_acceptance
                ?timeline_publisher_publication
                ?timeline_first_online ?timeline_revision
                ?timeline_submission ?title ?url ?url_private_api
                ?url_private_html ?url_public_api
                ?url_public_html ?version
WHERE {{
  GRAPH <https://data.4tu.nl/portal/2021-09-22> {{
    ?article            rdf:type                 sg:Article .
    ?article            col:id                   ?id .
    ?article            col:timeline_id          ?timeline_id .

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

    OPTIONAL {{
        ?license            rdf:type                  sg:License .
        ?license            col:id                    ?license_id .
        ?license            col:name                  ?license_name .
        ?license            col:url                   ?license_url .
        ?article            col:license_id            ?license_id .
    }}

    OPTIONAL {{ ?article col:account_id            ?account_id . }}
    OPTIONAL {{ ?article col:authors_id            ?authors_id . }}
    OPTIONAL {{ ?article col:citation              ?citation . }}
    OPTIONAL {{ ?article col:confidential_reason   ?confidential_reason . }}
    OPTIONAL {{ ?article col:created_date          ?created_date . }}
    OPTIONAL {{ ?article col:custom_fields_id      ?custom_fields_id . }}
    OPTIONAL {{ ?article col:defined_type          ?defined_type . }}
    OPTIONAL {{ ?article col:defined_type_name     ?defined_type_name . }}
    OPTIONAL {{ ?article col:description           ?description . }}
    OPTIONAL {{ ?article col:doi                   ?doi . }}
    OPTIONAL {{ ?article col:embargo_date          ?embargo_date . }}
    OPTIONAL {{ ?article col:embargo_options_id    ?embargo_options_id . }}
    OPTIONAL {{ ?article col:embargo_reason        ?embargo_reason . }}
    OPTIONAL {{ ?article col:embargo_title         ?embargo_title . }}
    OPTIONAL {{ ?article col:embargo_type          ?embargo_type . }}
    OPTIONAL {{ ?article col:figshare_url          ?figshare_url . }}
    OPTIONAL {{ ?article col:files_id              ?files_id . }}
    OPTIONAL {{ ?article col:funding               ?funding . }}
    OPTIONAL {{ ?article col:funding_id            ?funding_id . }}
    OPTIONAL {{ ?article col:group_id              ?group_id . }}
    OPTIONAL {{ ?article col:handle                ?handle . }}
    OPTIONAL {{ ?article col:has_linked_file       ?has_linked_file . }}
    OPTIONAL {{ ?article col:institution_id        ?institution_id . }}
    OPTIONAL {{ ?article col:is_active             ?is_active . }}
    OPTIONAL {{ ?article col:is_confidential       ?is_confidential . }}
    OPTIONAL {{ ?article col:is_embargoed          ?is_embargoed . }}
    OPTIONAL {{ ?article col:is_metadata_record    ?is_metadata_record . }}
    OPTIONAL {{ ?article col:is_public             ?is_public . }}
    OPTIONAL {{ ?article col:metadata_reason       ?metadata_reason . }}
    OPTIONAL {{ ?article col:modified_date         ?modified_date . }}
    OPTIONAL {{ ?article col:published_date        ?published_date . }}
    OPTIONAL {{ ?article col:references_id         ?references_id . }}
    OPTIONAL {{ ?article col:resource_doi          ?resource_doi . }}
    OPTIONAL {{ ?article col:resource_title        ?resource_title . }}
    OPTIONAL {{ ?article col:size                  ?size . }}
    OPTIONAL {{ ?article col:status                ?status . }}
    OPTIONAL {{ ?article col:tags_id               ?tags_id . }}
    OPTIONAL {{ ?article col:thumb                 ?thumb . }}
    OPTIONAL {{ ?article col:title                 ?title . }}
    OPTIONAL {{ ?article col:url                   ?url . }}
    OPTIONAL {{ ?article col:url_private_api       ?url_private_api . }}
    OPTIONAL {{ ?article col:url_private_html      ?url_private_html . }}
    OPTIONAL {{ ?article col:url_public_api        ?url_public_api . }}
    OPTIONAL {{ ?article col:url_public_html       ?url_public_html . }}
    OPTIONAL {{ ?article col:version               ?version . }}
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

        if item_type is not None:
            query += f"FILTER (?defined_type = {item_type})\n"

        if doi is not None:
            query += f"FILTER (STR(?doi) = \"{doi}\")\n"

        if handle is not None:
            query += f"FILTER (STR(?handle) = \"{handle}\")\n"

        if id is not None:
            query += f"FILTER (?id = {id})\n"

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

        self.sparql.setQuery(query)
        results = None
        try:
            query_results = self.sparql.query().convert()
            results = list(map(self.normalize_binding, query_results["results"]["bindings"]))
        except:
            logging.error(f"SPARQL query failed.")
            logging.error(f"Query:\n---\n{query}\n---")

        return results
