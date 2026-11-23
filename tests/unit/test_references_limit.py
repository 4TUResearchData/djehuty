"""Checks that ``SparqlInterface.references`` returns every reference."""

import tempfile

import pytest
from rdflib import RDFS, Graph

from djehuty.utils import rdf
from djehuty.web.config import config
from djehuty.web.database import SparqlInterface

URLS = [f"https://doi.org/10.1234/ref{index:02d}" for index in range(12)]


@pytest.fixture
def db():
    config.endpoint = "memory://test"
    config.update_endpoint = None
    config.state_graph = "https://data.4tu.nl/portal/test"
    interface = SparqlInterface()
    interface.setup_sparql_endpoint()
    interface.cache.storage = tempfile.mkdtemp()
    graph = Graph()
    graph.add((rdf.DJHT["DatasetContainer"], RDFS.subClassOf, rdf.DJHT["Container"]))
    interface.add_triples_from_graph(graph)
    return interface


@pytest.fixture
def dataset(db):
    owner = db.insert_account(email="o@4tu.nl", first_name="O", last_name="W")
    _, version_uuid = db.insert_dataset(
        title="Many references",
        account_uuid=owner,
        references=[{"url": url} for url in URLS],
    )
    return owner, version_uuid


def stored_urls(db, version_uuid):
    records = db.references(item_uri=rdf.uuid_to_uri(version_uuid, "dataset"))
    return [record["url"] for record in records]


def test_references_are_not_capped_at_ten(db, dataset):
    _, version_uuid = dataset
    assert stored_urls(db, version_uuid) == URLS


def test_appending_past_ten_keeps_every_reference(db, dataset):
    """Mirrors the POST handlers: read the list, append, rewrite it."""
    owner, version_uuid = dataset
    new_url = "https://doi.org/10.1234/ref99"

    urls = stored_urls(db, version_uuid) + [new_url]
    assert db.update_item_list(version_uuid, owner, urls, "references")

    assert stored_urls(db, version_uuid) == URLS + [new_url]
