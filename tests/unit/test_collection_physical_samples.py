"""Unit tests for physical samples in a collection"""

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
    """Reading the raw member list of a collection's physical samples."""

    def test_returns_every_member(self, db):
        """Every sample in the list comes back."""
        _seed_collection(db, samples=[SAMPLE_A, SAMPLE_B])
        rows = db.collection_physical_sample_containers(COLLECTION_URI, limit=None)
        assert {str(row["container_uri"]) for row in rows} == {
            f"container:{SAMPLE_A}",
            f"container:{SAMPLE_B}",
        }

    def test_is_empty_without_samples(self, db):
        """A collection with no samples has no members."""
        _seed_collection(db)
        assert db.collection_physical_sample_containers(COLLECTION_URI, limit=None) == []

    def test_ignores_the_datasets_list(self, db):
        """Datasets in the collection are not returned as samples."""
        _seed_collection(db, samples=[SAMPLE_A], datasets=[DATASET_A])
        rows = db.collection_physical_sample_containers(COLLECTION_URI, limit=None)
        assert [str(row["container_uri"]) for row in rows] == [f"container:{SAMPLE_A}"]


class TestCollectionsPhysicalSampleCount:
    """Counting the physical samples in a collection."""

    def test_counts_the_samples(self, db):
        """Each sample in the list is counted."""
        _seed_collection(db, samples=[SAMPLE_A, SAMPLE_B])
        assert db.collections_physical_sample_count(COLLECTION_URI) == 2

    def test_is_zero_without_samples(self, db):
        """A collection with no samples counts zero."""
        _seed_collection(db)
        assert db.collections_physical_sample_count(COLLECTION_URI) == 0

    def test_is_zero_without_a_collection(self, db):
        """No collection URI counts zero."""
        assert db.collections_physical_sample_count(None) == 0

    def test_lists_do_not_count_each_other(self, db):
        """Samples and datasets are counted separately."""
        _seed_collection(db, samples=[SAMPLE_A, SAMPLE_B], datasets=[DATASET_A])
        assert db.collections_physical_sample_count(COLLECTION_URI) == 2
        assert db.collections_dataset_count(COLLECTION_URI) == 1


class TestCollectionsFromPhysicalSample:
    """Finding the published collections that hold a physical sample."""

    def test_finds_the_published_collection(self, db):
        """A sample in a published collection returns that collection."""
        _seed_collection(db, samples=[SAMPLE_A], title="Rocks")
        rows = db.collections_from_physical_sample(SAMPLE_A)
        assert [(row["container_uuid"], row["title"]) for row in rows] == [(COLLECTION, "Rocks")]

    def test_ignores_samples_that_are_not_in_it(self, db):
        """A sample that is not in the list finds no collection."""
        _seed_collection(db, samples=[SAMPLE_A])
        assert db.collections_from_physical_sample(SAMPLE_B) == []

    def test_ignores_draft_collections(self, db):
        """A collection that is only a draft is not returned."""
        _seed_collection(db, samples=[SAMPLE_A], published=False)
        assert db.collections_from_physical_sample(SAMPLE_A) == []

    def test_ignores_the_datasets_list(self, db):
        """A container in the datasets list is not treated as a sample."""
        _seed_collection(db, datasets=[SAMPLE_A])
        assert db.collections_from_physical_sample(SAMPLE_A) == []


def _seed_sample(db, container_uuid, title):
    """Seed a published physical sample."""
    graph = Graph()
    container = URIRef(f"container:{container_uuid}")
    sample = URIRef(f"physical-sample:{container_uuid}")

    rdf.add(graph, container, RDF.type, rdf.DJHT["PhysicalSampleContainer"], "uri")
    rdf.add(graph, container, rdf.DJHT["account"], URIRef("account:owner"), "uri")
    rdf.add(graph, container, rdf.DJHT["latest_published_version"], sample, "uri")
    rdf.add(graph, sample, RDF.type, rdf.DJHT["PhysicalSample"], "uri")
    rdf.add(graph, sample, rdf.DJHT["container"], container, "uri")
    rdf.add(graph, sample, rdf.DJHT["title"], title, XSD.string)
    db.add_triples_from_graph(graph)


class TestPhysicalSamplesByCollection:
    """Filtering physical samples by the collection that lists them."""

    def test_returns_only_the_samples_in_the_collection(self, db):
        """Only the samples in the collection's list are returned."""
        _seed_sample(db, SAMPLE_A, "In the collection")
        _seed_sample(db, SAMPLE_B, "Not in the collection")
        _seed_collection(db, samples=[SAMPLE_A])
        rows = db.physical_samples(
            collection_uri=COLLECTION_URI, is_published=True, is_latest=True, use_cache=False
        )
        assert [row["container_uuid"] for row in rows] == [SAMPLE_A]

    def test_is_empty_for_a_collection_without_samples(self, db):
        """A collection with only datasets returns no samples."""
        _seed_sample(db, SAMPLE_A, "A sample")
        _seed_collection(db, datasets=[DATASET_A])
        rows = db.physical_samples(
            collection_uri=COLLECTION_URI, is_published=True, is_latest=True, use_cache=False
        )
        assert rows == []

    def test_without_a_collection_all_samples_are_returned(self, db):
        """Without a collection URI the filter does not apply."""
        _seed_sample(db, SAMPLE_A, "First")
        _seed_sample(db, SAMPLE_B, "Second")
        _seed_collection(db, samples=[SAMPLE_A])
        rows = db.physical_samples(is_published=True, is_latest=True, use_cache=False)
        assert {row["container_uuid"] for row in rows} == {SAMPLE_A, SAMPLE_B}


def _count_list_heads(db, collection_uri, predicate):
    """Count the distinct list heads a collection has for PREDICATE."""
    rows = list(
        db.sparql.query(
            f"SELECT (COUNT(DISTINCT ?head) AS ?n) WHERE {{ GRAPH <{config.state_graph}> {{ "
            f"<{collection_uri}> <{rdf.DJHT[predicate]}> ?head }} }}"
        )
    )
    return int(rows[0][0])


def _insert_collection(db, **lists):
    """Insert a collection with the given lists and return its URI."""
    _, collection_uuid = db.insert_collection(title="A collection", account_uuid="owner", **lists)
    return f"collection:{collection_uuid}"


class TestInsertCollection:
    """Storing physical samples when a collection is inserted."""

    def test_writes_one_list_with_every_sample(self, db):
        """All samples go into a single list."""
        uri = _insert_collection(
            db,
            physical_samples=[URIRef(f"container:{SAMPLE_A}"), URIRef(f"container:{SAMPLE_B}")],
        )
        assert _count_list_heads(db, uri, "physical_samples") == 1
        rows = db.collection_physical_sample_containers(uri, limit=None)
        assert {str(row["container_uri"]) for row in rows} == {
            f"container:{SAMPLE_A}",
            f"container:{SAMPLE_B}",
        }

    def test_writes_no_list_without_samples(self, db):
        """No samples means no list is written."""
        uri = _insert_collection(db)
        assert _count_list_heads(db, uri, "physical_samples") == 0

    def test_keeps_datasets_and_samples_apart(self, db):
        """Datasets and samples are stored in separate lists."""
        uri = _insert_collection(
            db,
            datasets=[URIRef(f"container:{DATASET_A}")],
            physical_samples=[URIRef(f"container:{SAMPLE_A}")],
        )
        samples = db.collection_physical_sample_containers(uri, limit=None)
        datasets = db.collection_dataset_containers(uri, limit=None)
        assert [str(row["container_uri"]) for row in samples] == [f"container:{SAMPLE_A}"]
        assert [str(row["container_uri"]) for row in datasets] == [f"container:{DATASET_A}"]
