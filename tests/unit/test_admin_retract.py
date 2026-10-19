"""Unit tests for retracting every published version of a dataset"""

import tempfile

import pytest
from rdflib import RDF, XSD, Graph, Literal, URIRef

from djehuty.utils import rdf
from djehuty.web.config import config
from djehuty.web.database import SparqlInterface

DJHT = rdf.DJHT
BOOLEAN = XSD.boolean
OWNER = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
ADMIN = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
CONTAINER = "cccccccc-cccc-cccc-cccc-cccccccccccc"
OTHER_CONTAINER = "dddddddd-dddd-dddd-dddd-dddddddddddd"
DRAFT = "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"
VERSIONS = [
    "11111111-1111-1111-1111-111111111111",
    "22222222-2222-2222-2222-222222222222",
    "33333333-3333-3333-3333-333333333333",
]
OTHER_VERSIONS = ["44444444-4444-4444-4444-444444444444"]
FLAGS = ("is_active", "is_public", "is_latest")


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


def _dataset_uri(uuid):
    return URIRef(rdf.uuid_to_uri(uuid, "dataset"))


def _container_uri(uuid):
    return URIRef(rdf.uuid_to_uri(uuid, "container"))


def _review_uri(uuid):
    return URIRef(f"review:{uuid}")


def _seed_container(db, container, versions, draft=None, older_are_latest=True):
    """Seed a container with published VERSIONS (oldest first) and a review per version."""
    graph = Graph()
    container_uri = _container_uri(container)
    rdf.add(graph, container_uri, RDF.type, DJHT["DatasetContainer"], "uri")
    rdf.add(graph, container_uri, DJHT["first_online_date"], "2026-01-01T00:00:00", XSD.dateTime)
    rdf.add(graph, container_uri, DJHT["account"], URIRef(rdf.uuid_to_uri(OWNER, "account")), "uri")

    for number, uuid in enumerate(versions, start=1):
        dataset = _dataset_uri(uuid)
        is_newest = number == len(versions)
        rdf.add(graph, dataset, RDF.type, DJHT["Dataset"], "uri")
        rdf.add(graph, dataset, DJHT["container"], container_uri, "uri")
        rdf.add(graph, dataset, DJHT["version"], number, XSD.integer)
        rdf.add(graph, dataset, DJHT["published_date"], "2026-01-01T00:00:00", XSD.dateTime)
        rdf.add(graph, dataset, DJHT["posted_date"], "2026-01-01T00:00:00", XSD.dateTime)
        graph.add((dataset, DJHT["is_active"], _flag(True)))
        graph.add((dataset, DJHT["is_public"], _flag(True)))
        graph.add((dataset, DJHT["is_latest"], _flag(is_newest or older_are_latest)))

        review = _review_uri(uuid)
        rdf.add(graph, review, RDF.type, DJHT["Review"], "uri")
        rdf.add(graph, review, DJHT["dataset"], dataset, "uri")
        rdf.add(graph, review, DJHT["request_date"], "2026-01-01T00:00:00", XSD.dateTime)

    newest = _dataset_uri(versions[-1])
    rdf.add(graph, container_uri, DJHT["latest_published_version"], newest, "uri")
    db.insert_item_list(graph, container_uri, [_dataset_uri(u) for u in versions],
                        "published_versions")

    if draft is not None:
        draft_uri = _dataset_uri(draft)
        rdf.add(graph, draft_uri, RDF.type, DJHT["Dataset"], "uri")
        rdf.add(graph, draft_uri, DJHT["container"], container_uri, "uri")
        rdf.add(graph, draft_uri, DJHT["title"], "A draft", XSD.string)
        rdf.add(graph, container_uri, DJHT["draft"], draft_uri, "uri")

    db.add_triples_from_graph(graph)


def _flag(value):
    """Boolean kept in the lexical form the retract queries match on."""
    return Literal("1" if value else "0", datatype=BOOLEAN, normalize=False)


def _ask(db, pattern):
    query = f"ASK {{ GRAPH <{config.state_graph}> {{ {pattern} }} }}"
    return db.sparql.query(query).askAnswer


def _has(db, subject, predicate, value="?value"):
    return _ask(db, f"<{subject}> <{DJHT[predicate]}> {value} .")


def _flag_is_set(db, uuid, flag):
    return _has(db, _dataset_uri(uuid), flag, f'"1"^^<{BOOLEAN}>')


def _retract(db, container=CONTAINER):
    return db.admin_retract_dataset(container, ADMIN)


class TestRetractAllVersions:
    """Retracting a container that has several published versions."""

    @pytest.fixture(params=[True, False], ids=["older-flagged-latest", "older-not-latest"])
    def retracted(self, db, request):
        _seed_container(db, CONTAINER, VERSIONS, older_are_latest=request.param)
        _seed_container(db, OTHER_CONTAINER, OTHER_VERSIONS)
        assert _retract(db) is True
        return db

    def test_every_version_goes_offline(self, retracted):
        """No version stays public or latest, and only the draft is active."""
        for uuid in VERSIONS:
            for flag in ("is_public", "is_latest"):
                assert not _flag_is_set(retracted, uuid, flag), f"{uuid} still {flag}"
        for uuid in VERSIONS[:-1]:
            assert not _flag_is_set(retracted, uuid, "is_active")

    def test_every_version_is_marked_inactive(self, retracted):
        """Versions other than the draft are explicitly inactive."""
        for uuid in VERSIONS[:-1]:
            assert _has(retracted, _dataset_uri(uuid), "is_active", f'"0"^^<{BOOLEAN}>')

    def test_latest_version_becomes_the_draft(self, retracted):
        """The newest version is the container's draft, and it is active again."""
        container = _container_uri(CONTAINER)
        assert _has(retracted, container, "draft", _dataset_uri(VERSIONS[-1]).n3())
        assert _flag_is_set(retracted, VERSIONS[-1], "is_active")

    def test_older_versions_are_not_promoted(self, retracted):
        """Only the newest version becomes a draft."""
        container = _container_uri(CONTAINER)
        for uuid in VERSIONS[:-1]:
            assert not _has(retracted, container, "draft", _dataset_uri(uuid).n3())

    def test_versions_move_to_retracted(self, retracted):
        """The published list becomes the retracted list."""
        container = _container_uri(CONTAINER)
        assert not _has(retracted, container, "published_versions")
        assert not _has(retracted, container, "latest_published_version")
        assert _has(retracted, container, "retracted_versions")

    def test_publish_dates_are_stripped_from_every_version(self, retracted):
        """No version keeps a published or posted date, and the container loses first_online."""
        for uuid in VERSIONS:
            assert not _has(retracted, _dataset_uri(uuid), "published_date")
            assert not _has(retracted, _dataset_uri(uuid), "posted_date")
        assert not _has(retracted, _container_uri(CONTAINER), "first_online_date")

    def test_reviews_of_every_version_are_deleted(self, retracted):
        """Each version's review node is removed."""
        for uuid in VERSIONS:
            assert not _ask(retracted, f"<{_review_uri(uuid)}> ?predicate ?value .")

    def test_other_containers_are_untouched(self, retracted):
        """Another container keeps its flags, dates, list and review."""
        other = OTHER_VERSIONS[0]
        for flag in FLAGS:
            assert _flag_is_set(retracted, other, flag)
        assert _has(retracted, _dataset_uri(other), "posted_date")
        assert _has(retracted, _container_uri(OTHER_CONTAINER), "published_versions")
        assert _ask(retracted, f"<{_review_uri(other)}> ?predicate ?value .")


class TestRetractSingleVersion:
    """A container with one version keeps working as before."""

    def test_single_version_is_retracted(self, db):
        _seed_container(db, CONTAINER, VERSIONS[:1])
        assert _retract(db) is True
        for flag in ("is_public", "is_latest"):
            assert not _flag_is_set(db, VERSIONS[0], flag)
        assert _flag_is_set(db, VERSIONS[0], "is_active")
        assert _has(db, _container_uri(CONTAINER), "draft", _dataset_uri(VERSIONS[0]).n3())
        assert not _ask(db, f"<{_review_uri(VERSIONS[0])}> ?predicate ?value .")


class TestRetractRefusals:
    """Cases where nothing may be changed."""

    def test_unknown_container_is_refused(self, db):
        assert _retract(db, OTHER_CONTAINER) is False

    def test_container_with_a_draft_is_refused(self, db):
        _seed_container(db, CONTAINER, VERSIONS, draft=DRAFT)
        assert _retract(db) is False
        for uuid in VERSIONS:
            for flag in FLAGS:
                assert _flag_is_set(db, uuid, flag)
        assert _has(db, _container_uri(CONTAINER), "published_versions")

    def test_already_retracted_container_is_refused(self, db):
        _seed_container(db, CONTAINER, VERSIONS)
        assert _retract(db) is True
        assert _retract(db) is False
