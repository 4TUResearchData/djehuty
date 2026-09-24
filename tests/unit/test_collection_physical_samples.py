"""Unit tests for physical samples in a collection
"""

import tempfile

import pytest
from rdflib import RDF, XSD, Graph, URIRef

from djehuty.utils import rdf
from djehuty.web.config import config
from djehuty.web.database import SparqlInterface

SAMPLE_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
SAMPLE_B = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
DATASET_A = "dddddddd-dddd-dddd-dddd-dddddddddddd"
COLLECTION = "cccccccc-cccc-cccc-cccc-cccccccccccc"
COLLECTION_URI = f"collection:{COLLECTION}"


@pytest.fixture
def db():
    """A SparqlInterface backed by a fresh in-memory store per test."""
    config.endpoint = "memory://test"
    config.update_endpoint = None
    config.state_graph = "https://data.4tu.nl/portal/test"
    interface = SparqlInterface()
    interface.setup_sparql_endpoint()
    interface.cache.storage = tempfile.mkdtemp()
    return interface


def _seed_collection(db, samples=(), datasets=(), published=True, title="A collection"):
    """Seed a collection whose lists point at the given container UUIDs."""
    graph = Graph()
    container = URIRef(f"container:{COLLECTION}")
    collection = URIRef(COLLECTION_URI)
    link = "latest_published_version" if published else "draft"

    rdf.add(graph, container, RDF.type, rdf.DJHT["CollectionContainer"], "uri")
    rdf.add(graph, container, rdf.DJHT[link], collection, "uri")
    rdf.add(graph, collection, RDF.type, rdf.DJHT["Collection"], "uri")
    rdf.add(graph, collection, rdf.DJHT["title"], title, XSD.string)
    db.insert_item_list(
        graph, collection, [URIRef(f"container:{u}") for u in samples], "physical_samples"
    )
    db.insert_item_list(graph, collection, [URIRef(f"container:{u}") for u in datasets], "datasets")
    db.add_triples_from_graph(graph)


class TestCollectionPhysicalSampleContainers:
    def test_returns_every_member(self, db):
        _seed_collection(db, samples=[SAMPLE_A, SAMPLE_B])
        rows = db.collection_physical_sample_containers(COLLECTION_URI, limit=None)
        assert {str(row["container_uri"]) for row in rows} == {
            f"container:{SAMPLE_A}",
            f"container:{SAMPLE_B}",
        }

    def test_is_empty_without_samples(self, db):
        _seed_collection(db)
        assert db.collection_physical_sample_containers(COLLECTION_URI, limit=None) == []

    def test_ignores_the_datasets_list(self, db):
        _seed_collection(db, samples=[SAMPLE_A], datasets=[DATASET_A])
        rows = db.collection_physical_sample_containers(COLLECTION_URI, limit=None)
        assert [str(row["container_uri"]) for row in rows] == [f"container:{SAMPLE_A}"]


class TestCollectionsPhysicalSampleCount:
    def test_counts_the_samples(self, db):
        _seed_collection(db, samples=[SAMPLE_A, SAMPLE_B])
        assert db.collections_physical_sample_count(COLLECTION_URI) == 2

    def test_is_zero_without_samples(self, db):
        _seed_collection(db)
        assert db.collections_physical_sample_count(COLLECTION_URI) == 0

    def test_is_zero_without_a_collection(self, db):
        assert db.collections_physical_sample_count(None) == 0

    def test_lists_do_not_count_each_other(self, db):
        _seed_collection(db, samples=[SAMPLE_A, SAMPLE_B], datasets=[DATASET_A])
        assert db.collections_physical_sample_count(COLLECTION_URI) == 2
        assert db.collections_dataset_count(COLLECTION_URI) == 1


class TestCollectionsFromPhysicalSample:
    def test_finds_the_published_collection(self, db):
        _seed_collection(db, samples=[SAMPLE_A], title="Rocks")
        rows = db.collections_from_physical_sample(SAMPLE_A)
        assert [(row["container_uuid"], row["title"]) for row in rows] == [(COLLECTION, "Rocks")]

    def test_ignores_samples_that_are_not_in_it(self, db):
        _seed_collection(db, samples=[SAMPLE_A])
        assert db.collections_from_physical_sample(SAMPLE_B) == []

    def test_ignores_draft_collections(self, db):
        _seed_collection(db, samples=[SAMPLE_A], published=False)
        assert db.collections_from_physical_sample(SAMPLE_A) == []

    def test_ignores_the_datasets_list(self, db):
        _seed_collection(db, datasets=[SAMPLE_A])
        assert db.collections_from_physical_sample(SAMPLE_A) == []
