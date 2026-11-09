"""Unit tests for retracting every published version of a dataset"""

import logging
import tempfile

import pytest
from rdflib import RDF, XSD, Graph, Literal, URIRef

from djehuty.utils import rdf
from djehuty.web.config import config
from djehuty.web.database import RetractRefused, SparqlInterface

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
    db.insert_item_list(
        graph, container_uri, [_dataset_uri(u) for u in versions], "published_versions"
    )

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


def _values_of(db, subject, predicate):
    query = (
        f"SELECT ?value WHERE {{ GRAPH <{config.state_graph}> {{ "
        f"<{subject}> <{DJHT[predicate]}> ?value . }} }}"
    )
    return len(list(db.sparql.query(query)))


def _flag_is_set(db, uuid, flag):
    return _has(db, _dataset_uri(uuid), flag, f'"1"^^<{BOOLEAN}>')


def _retract(db, versions=None, container=CONTAINER):
    return db.admin_retract_dataset(container, ADMIN, version_uuids=versions)


def _members(db, predicate, container=CONTAINER):
    query = (
        f"SELECT ?item WHERE {{ GRAPH <{config.state_graph}> {{ "
        f"<{_container_uri(container)}> <{DJHT[predicate]}>/<{RDF.rest}>*/<{RDF.first}> ?item . "
        "} }"
    )
    return {str(row.item) for row in db.sparql.query(query)}


def _uris(uuids):
    return {str(_dataset_uri(uuid)) for uuid in uuids}


class TestRetractAllVersions:
    """Retracting a container that has several published versions."""

    @pytest.fixture(params=[True, False], ids=["older-flagged-latest", "older-not-latest"])
    def retracted(self, db, request):
        _seed_container(db, CONTAINER, VERSIONS, older_are_latest=request.param)
        _seed_container(db, OTHER_CONTAINER, OTHER_VERSIONS)
        assert _retract(db) is True
        return db

    def test_cached_reviews_list_is_invalidated(self, db):
        _seed_container(db, CONTAINER, VERSIONS)
        db.cache.cache_value("reviews", "stale", ["old"])
        assert _retract(db) is True
        assert db.cache.cached_value("reviews", "stale") is None

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

    def test_published_date_is_kept_as_retracted_published_date(self, retracted):
        """The year survives the strip, together with the time of the retract."""
        published = f'"2026-01-01T00:00:00"^^<{XSD.dateTime}>'
        for uuid in VERSIONS:
            assert _has(retracted, _dataset_uri(uuid), "retracted_published_date", published)
            assert _values_of(retracted, _dataset_uri(uuid), "retracted_date") == 1

    def test_other_containers_get_no_retraction_dates(self, retracted):
        other = _dataset_uri(OTHER_VERSIONS[0])
        assert _has(retracted, other, "published_date")
        assert not _has(retracted, other, "retracted_published_date")
        assert not _has(retracted, other, "retracted_date")

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
        with pytest.raises(RetractRefused) as refusal:
            _retract(db, container=OTHER_CONTAINER)
        assert refusal.value.code == "NoPublishedVersions"

    def test_container_with_a_draft_is_refused(self, db):
        _seed_container(db, CONTAINER, VERSIONS, draft=DRAFT)
        with pytest.raises(RetractRefused) as refusal:
            _retract(db)
        assert refusal.value.code == "DraftExists"
        for uuid in VERSIONS:
            for flag in FLAGS:
                assert _flag_is_set(db, uuid, flag)
        assert _has(db, _container_uri(CONTAINER), "published_versions")

    def test_already_retracted_container_is_refused(self, db):
        _seed_container(db, CONTAINER, VERSIONS)
        assert _retract(db) is True
        with pytest.raises(RetractRefused) as refusal:
            _retract(db)
        assert refusal.value.code == "NoPublishedVersions"


class TestRetractSubset:
    """Retracting only some of the published versions."""

    def test_latest_only_promotes_the_previous_version(self, db):
        _seed_container(db, CONTAINER, VERSIONS, older_are_latest=False)
        assert _retract(db, VERSIONS[-1:]) is True
        container = _container_uri(CONTAINER)
        assert _members(db, "published_versions") == _uris(VERSIONS[:2])
        assert _members(db, "retracted_versions") == _uris(VERSIONS[2:])
        assert _has(db, container, "latest_published_version", _dataset_uri(VERSIONS[1]).n3())
        assert _flag_is_set(db, VERSIONS[1], "is_latest")
        assert _has(db, container, "draft", _dataset_uri(VERSIONS[2]).n3())
        assert _has(db, container, "first_online_date")

    def test_older_only_leaves_latest_and_draft_slot_alone(self, db):
        _seed_container(db, CONTAINER, VERSIONS)
        assert _retract(db, VERSIONS[:1]) is True
        container = _container_uri(CONTAINER)
        assert _members(db, "published_versions") == _uris(VERSIONS[1:])
        assert _members(db, "retracted_versions") == _uris(VERSIONS[:1])
        assert _has(db, container, "latest_published_version", _dataset_uri(VERSIONS[2]).n3())
        assert not _has(db, container, "draft")
        assert _has(db, container, "first_online_date")
        assert not _has(db, _dataset_uri(VERSIONS[0]), "posted_date")
        assert _has(db, _dataset_uri(VERSIONS[1]), "posted_date")

    def test_older_only_is_allowed_with_an_open_draft(self, db):
        _seed_container(db, CONTAINER, VERSIONS, draft=DRAFT)
        assert _retract(db, VERSIONS[:1]) is True
        assert _has(db, _container_uri(CONTAINER), "draft", _dataset_uri(DRAFT).n3())

    def test_unselected_versions_keep_their_flags_dates_and_reviews(self, db):
        _seed_container(db, CONTAINER, VERSIONS)
        assert _retract(db, VERSIONS[:1]) is True
        for flag in FLAGS:
            assert not _flag_is_set(db, VERSIONS[0], flag)
        assert not _has(db, _dataset_uri(VERSIONS[0]), "published_date")
        assert not _ask(db, f"<{_review_uri(VERSIONS[0])}> ?predicate ?value .")

        for uuid in VERSIONS[1:]:
            for flag in FLAGS:
                assert _flag_is_set(db, uuid, flag)
            assert _has(db, _dataset_uri(uuid), "published_date")
            assert _has(db, _dataset_uri(uuid), "posted_date")
            assert _ask(db, f"<{_review_uri(uuid)}> ?predicate ?value .")

    def test_only_selected_versions_get_retraction_dates(self, db):
        _seed_container(db, CONTAINER, VERSIONS)
        assert _retract(db, VERSIONS[:1]) is True
        assert _has(db, _dataset_uri(VERSIONS[0]), "retracted_published_date")
        assert _has(db, _dataset_uri(VERSIONS[0]), "retracted_date")
        for uuid in VERSIONS[1:]:
            assert not _has(db, _dataset_uri(uuid), "retracted_published_date")
            assert not _has(db, _dataset_uri(uuid), "retracted_date")

    def test_second_retract_replaces_the_retraction_dates(self, db):
        """A republished version that is retracted again keeps one pair of dates."""
        _seed_container(db, CONTAINER, VERSIONS)
        assert _retract(db, VERSIONS[:1]) is True
        dataset = _dataset_uri(VERSIONS[0])
        graph = Graph()
        rdf.add(graph, dataset, DJHT["published_date"], "2026-02-02T00:00:00", XSD.dateTime)
        db.add_triples_from_graph(graph)

        plan = {
            "selected": [{"dataset_uri": str(dataset)}],
            "remaining": [{"dataset_uri": "unused"}],
            "latest": {"dataset_uri": "unused"},
            "retracts_latest": False,
        }
        assert db._SparqlInterface__retract_strip_metadata(str(_container_uri(CONTAINER)), plan)

        assert _values_of(db, dataset, "retracted_date") == 1
        assert _values_of(db, dataset, "retracted_published_date") == 1
        assert _has(
            db,
            dataset,
            "retracted_published_date",
            f'"2026-02-02T00:00:00"^^<{XSD.dateTime}>',
        )

    def test_datasets_query_returns_the_retraction_dates(self, db):
        _seed_container(db, CONTAINER, VERSIONS)
        graph = Graph()
        rdf.add(graph, _dataset_uri(VERSIONS[0]), DJHT["title"], "A title", XSD.string)
        db.add_triples_from_graph(graph)
        assert _retract(db, VERSIONS[:1]) is True
        rows = db.datasets(
            container_uuid=CONTAINER,
            is_published=None,
            is_latest=None,
            version=1,
            use_cache=False,
            limit=1,
        )
        assert rows[0]["retracted_published_date"].startswith("2026-01-01")
        assert rows[0]["retracted_date"]

    def test_latest_and_older_together(self, db):
        _seed_container(db, CONTAINER, VERSIONS)
        assert _retract(db, [VERSIONS[0], VERSIONS[2]]) is True
        container = _container_uri(CONTAINER)
        assert _members(db, "published_versions") == _uris(VERSIONS[1:2])
        assert _members(db, "retracted_versions") == _uris([VERSIONS[0], VERSIONS[2]])
        assert _has(db, container, "latest_published_version", _dataset_uri(VERSIONS[1]).n3())
        assert _has(db, container, "draft", _dataset_uri(VERSIONS[2]).n3())

    def test_explicit_full_selection_matches_retract_all(self, db):
        _seed_container(db, CONTAINER, VERSIONS)
        assert _retract(db, VERSIONS) is True
        container = _container_uri(CONTAINER)
        assert not _has(db, container, "published_versions")
        assert not _has(db, container, "first_online_date")
        assert _members(db, "retracted_versions") == _uris(VERSIONS)

    def test_repeat_partial_retracts_accumulate(self, db):
        _seed_container(db, CONTAINER, VERSIONS)
        assert _retract(db, VERSIONS[:1]) is True
        assert _retract(db, VERSIONS[1:2]) is True
        assert _members(db, "published_versions") == _uris(VERSIONS[2:])
        assert _members(db, "retracted_versions") == _uris(VERSIONS[:2])

    def test_latest_with_an_open_draft_is_refused_and_changes_nothing(self, db):
        _seed_container(db, CONTAINER, VERSIONS, draft=DRAFT)
        with pytest.raises(RetractRefused) as refusal:
            _retract(db, VERSIONS[-1:])
        assert refusal.value.code == "DraftExists"
        assert _members(db, "published_versions") == _uris(VERSIONS)

    def test_unknown_version_is_refused_and_changes_nothing(self, db):
        _seed_container(db, CONTAINER, VERSIONS)
        with pytest.raises(RetractRefused) as refusal:
            _retract(db, [OTHER_VERSIONS[0]])
        assert refusal.value.code == "UnknownVersion"
        assert _members(db, "published_versions") == _uris(VERSIONS)

    def test_empty_selection_is_refused_and_changes_nothing(self, db):
        _seed_container(db, CONTAINER, VERSIONS)
        with pytest.raises(RetractRefused) as refusal:
            _retract(db, [])
        assert refusal.value.code == "NoVersionsSelected"
        assert _members(db, "published_versions") == _uris(VERSIONS)
        assert not _has(db, _container_uri(CONTAINER), "retracted_versions")


def _count(db, predicate, container=CONTAINER):
    query = (
        f"SELECT (COUNT(?value) AS ?total) WHERE {{ GRAPH <{config.state_graph}> {{ "
        f"<{_container_uri(container)}> <{DJHT[predicate]}> ?value . }} }}"
    )
    return int(next(iter(db.sparql.query(query))).total)


def _ordered(db, predicate, container=CONTAINER):
    query = (
        f"SELECT ?item WHERE {{ GRAPH <{config.state_graph}> {{ "
        f"<{_container_uri(container)}> <{DJHT[predicate]}>/<{RDF.rest}>*/<{RDF.first}> ?item . "
        f"?node <{RDF.first}> ?item ; <{DJHT['index']}> ?index . "
        "} } ORDER BY ?index"
    )
    return [str(row.item) for row in db.sparql.query(query)]


def _node_count(db):
    query = (
        f"SELECT (COUNT(DISTINCT ?node) AS ?total) WHERE {{ GRAPH <{config.state_graph}> {{ "
        f"?node <{RDF.first}> ?item . }} }}"
    )
    return int(next(iter(db.sparql.query(query))).total)


def _head(db, predicate, container=CONTAINER):
    query = (
        f"SELECT ?head WHERE {{ GRAPH <{config.state_graph}> {{ "
        f"<{_container_uri(container)}> <{DJHT[predicate]}> ?head . }} }}"
    )
    return next(iter(db.sparql.query(query))).head


class TestVersionListSwap:
    """The version lists are replaced by building new nodes and swapping the heads."""

    def test_no_orphan_nodes_are_left_behind(self, db):
        _seed_container(db, CONTAINER, VERSIONS)
        assert _node_count(db) == len(VERSIONS)
        assert _retract(db, VERSIONS[:1]) is True
        assert _node_count(db) == len(VERSIONS)

    def test_old_heads_are_gone(self, db):
        _seed_container(db, CONTAINER, VERSIONS)
        old_head = _head(db, "published_versions")
        assert _retract(db, VERSIONS[:1]) is True
        assert not _ask(db, f"<{old_head}> ?p ?o .")
        assert _head(db, "published_versions") != old_head

    def test_repeat_retracts_append_in_order(self, db):
        _seed_container(db, CONTAINER, VERSIONS)
        assert _retract(db, VERSIONS[:1]) is True
        assert _retract(db, VERSIONS[1:2]) is True
        assert _ordered(db, "retracted_versions") == [
            str(_dataset_uri(uuid)) for uuid in VERSIONS[:2]
        ]

    def test_retract_all_leaves_no_published_link_and_no_orphans(self, db):
        _seed_container(db, CONTAINER, VERSIONS)
        assert _retract(db) is True
        assert not _has(db, _container_uri(CONTAINER), "published_versions")
        assert _node_count(db) == len(VERSIONS)

    def test_failed_swap_keeps_the_old_lists_linked(self, db, monkeypatch):
        _seed_container(db, CONTAINER, VERSIONS)
        original = SparqlInterface._SparqlInterface__run_logged_query

        def fail_on_swap(self, query, *args, **kwargs):
            if "?old_published" in query:
                return False
            return original(self, query, *args, **kwargs)

        monkeypatch.setattr(SparqlInterface, "_SparqlInterface__run_logged_query", fail_on_swap)
        assert _retract(db, VERSIONS[:1]) is False
        assert _members(db, "published_versions") == _uris(VERSIONS)
        assert not _has(db, _container_uri(CONTAINER), "retracted_versions")
        assert _node_count(db) == len(VERSIONS) + 2 + 1

    def test_failed_cleanup_still_retracts_and_warns(self, db, monkeypatch, caplog):
        _seed_container(db, CONTAINER, VERSIONS)
        original = SparqlInterface._SparqlInterface__run_logged_query

        def fail_on_cleanup(self, query, *args, **kwargs):
            if "rdf:rest*" in query:
                return False
            return original(self, query, *args, **kwargs)

        monkeypatch.setattr(SparqlInterface, "_SparqlInterface__run_logged_query", fail_on_cleanup)
        with caplog.at_level(logging.WARNING):
            assert _retract(db, VERSIONS[:1]) is True

        assert _members(db, "published_versions") == _uris(VERSIONS[1:])
        assert _members(db, "retracted_versions") == _uris(VERSIONS[:1])
        assert _node_count(db) == len(VERSIONS) + 2 + 1
        assert "orphan list nodes" in caplog.text

    def test_retry_after_a_later_step_failed_does_not_duplicate(self, db, monkeypatch):
        _seed_container(db, CONTAINER, VERSIONS)
        with monkeypatch.context() as patch:
            patch.setattr(
                SparqlInterface,
                "_SparqlInterface__retract_delete_reviews",
                lambda self, plan: False,
            )
            assert _retract(db, VERSIONS[:1]) is False

        assert _retract(db, VERSIONS[:1]) is True
        assert _ordered(db, "retracted_versions") == [str(_dataset_uri(VERSIONS[0]))]

    def test_latest_pointer_stays_single_valued(self, db):
        _seed_container(db, CONTAINER, VERSIONS, older_are_latest=False)
        assert _retract(db, VERSIONS[-1:]) is True
        assert _count(db, "latest_published_version") == 1
        assert _retract(db, VERSIONS[:1]) is True
        assert _count(db, "latest_published_version") == 1

    def test_retract_all_removes_the_latest_pointer(self, db):
        _seed_container(db, CONTAINER, VERSIONS)
        assert _retract(db) is True
        assert _count(db, "latest_published_version") == 0


class TestPlanRetract:
    def test_latest_only_promotes_a_draft(self, db):
        _seed_container(db, CONTAINER, VERSIONS)
        plan = db.plan_retract(CONTAINER, VERSIONS[-1:])
        assert [v["version"] for v in plan["selected"]] == [3]
        assert [v["version"] for v in plan["remaining"]] == [1, 2]
        assert plan["retracts_latest"] is True

    def test_older_only_keeps_the_latest(self, db):
        _seed_container(db, CONTAINER, VERSIONS, draft=DRAFT)
        plan = db.plan_retract(CONTAINER, VERSIONS[:1])
        assert plan["retracts_latest"] is False
        assert plan["latest"]["version"] == 3

    def test_everything_leaves_nothing_remaining(self, db):
        _seed_container(db, CONTAINER, VERSIONS)
        plan = db.plan_retract(CONTAINER, VERSIONS)
        assert plan["remaining"] == []

    def test_plan_does_not_modify_the_store(self, db):
        _seed_container(db, CONTAINER, VERSIONS)
        db.plan_retract(CONTAINER, VERSIONS)
        assert _members(db, "published_versions") == _uris(VERSIONS)

    def test_latest_with_an_open_draft_is_refused(self, db):
        _seed_container(db, CONTAINER, VERSIONS, draft=DRAFT)
        with pytest.raises(RetractRefused) as refusal:
            db.plan_retract(CONTAINER, VERSIONS[-1:])
        assert refusal.value.code == "DraftExists"

    def test_unknown_version_is_refused(self, db):
        _seed_container(db, CONTAINER, VERSIONS)
        with pytest.raises(RetractRefused) as refusal:
            db.plan_retract(CONTAINER, [OTHER_VERSIONS[0]])
        assert refusal.value.code == "UnknownVersion"
