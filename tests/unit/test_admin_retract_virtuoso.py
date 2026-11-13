"""Checks the retract cleanup query against a live Virtuoso, skipped when none is running."""

import os
import uuid

import pytest
import requests
from jinja2 import Environment, FileSystemLoader
from requests.auth import HTTPDigestAuth

from djehuty.web import database

ENDPOINT = os.environ.get("DJEHUTY_TEST_VIRTUOSO", "http://localhost:8890")
AUTH = HTTPDigestAuth(
    os.environ.get("DJEHUTY_TEST_VIRTUOSO_USER", "dba"),
    os.environ.get("DJEHUTY_TEST_VIRTUOSO_PASSWORD", "dba"),
)
TEMPLATES = os.path.join(os.path.dirname(database.__file__), "resources", "sparql_templates")
PREFIXES = (
    "PREFIX djht: <https://ontologies.data.4tu.nl/djehuty/0.0.1/> "
    "PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> "
)


def _run(query):
    response = requests.post(
        f"{ENDPOINT}/sparql-auth",
        data={"query": query},
        headers={"Accept": "application/sparql-results+json"},
        auth=AUTH,
        timeout=30,
    )
    response.raise_for_status()
    return response


@pytest.fixture
def graph():
    try:
        requests.get(f"{ENDPOINT}/sparql", timeout=2)
    except requests.RequestException:
        pytest.skip("no Virtuoso reachable")

    name = f"djehuty://test-retract-{uuid.uuid4()}"
    yield name
    _run(f"DROP SILENT GRAPH <{name}>")


def _count(graph, pattern):
    query = f"{PREFIXES} SELECT (COUNT(*) AS ?n) WHERE {{ GRAPH <{graph}> {{ {pattern} }} }}"
    return int(_run(query).json()["results"]["bindings"][0]["n"]["value"])


def _seed(graph):
    _run(
        f"{PREFIXES} INSERT DATA {{ GRAPH <{graph}> {{"
        "<blank:old-1> rdf:first <dataset:a> ; djht:index 0 ; "
        "rdf:rest <blank:old-2> ; rdf:type rdf:List . "
        "<blank:old-2> rdf:first <dataset:b> ; djht:index 1 ; "
        "rdf:rest rdf:nil ; rdf:type rdf:List . "
        "<blank:kept-1> rdf:first <dataset:c> ; djht:index 0 ; "
        "rdf:rest rdf:nil ; rdf:type rdf:List . "
        '<dataset:a> djht:title "unrelated" . '
        '<category:x> djht:title "unrelated" . '
        "} }"
    )


def test_cleanup_deletes_only_the_nodes_under_the_given_head(graph):
    _seed(graph)
    template = Environment(loader=FileSystemLoader(TEMPLATES)).get_template(
        "retract/admin_retract_drop_old_nodes.sparql"
    )
    _run(template.render(state_graph=graph, head_uri="blank:old-1"))

    assert _count(graph, "<blank:old-1> ?p ?o") == 0
    assert _count(graph, "<blank:old-2> ?p ?o") == 0
    assert _count(graph, "<blank:kept-1> ?p ?o") == 4
    assert _count(graph, "?s djht:title ?o") == 2
