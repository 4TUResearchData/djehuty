"""Unit tests for institution-group reconciliation

The reconcile tests drive the real ``SparqlInterface`` against an in-memory
rdflib store (same approach as ``test_migrate.py``), so no Virtuoso is needed.
"""

import tempfile

import pytest
from rdflib import Graph, RDF, XSD

from djehuty.utils import rdf
from djehuty.web.config import config
from djehuty.web.database import SparqlInterface


class TestStableNode:
    """The deterministic node generator behind the fix."""

    @pytest.mark.parametrize("seed_a, seed_b, equal", [
        (("group", 28586), ("group", 28586), True),    # same seed -> same uri
        (("group", 28586), ("group", 28598), False),   # different id
        (("group", 28586), ("account", 28586), False),  # different prefix
    ])
    def test_equality(self, seed_a, seed_b, equal):
        assert (rdf.stable_node(*seed_a) == rdf.stable_node(*seed_b)) is equal

    def test_shape_is_prefix_uuid(self):
        uri = str(rdf.stable_node("group", 28586))
        assert uri.startswith("group:")
        assert len(rdf.uri_to_uuid(uri)) == 36  # still UUID-shaped

    def test_unique_node_is_not_stable(self):
        assert rdf.unique_node("group") != rdf.unique_node("group")


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


# name, is_featured, id, parent_id, domain
CONFIG_GROUPS = [
    ("4TU.ResearchData", False, 28585, 0, "4tu.nl"),
    ("Delft University of Technology", True, 28586, 28585, "tudelft.nl"),
    ("Other institutions", True, 28598, 28585, "nogroup"),
]


def _seed_preexisting_groups(db, groups):
    """Seed groups already in the store under a random URI and without the
    is_inferred flag - the state delete_groups_by_id must reconcile by id."""
    graph = Graph()
    for name, group_id, parent_id, domain in groups:
        uri = rdf.unique_node("group")
        graph.add((uri, RDF.type, rdf.DJHT["InstitutionGroup"]))
        rdf.add(graph, uri, rdf.DJHT["id"], group_id, XSD.integer)
        rdf.add(graph, uri, rdf.DJHT["parent_id"], parent_id, XSD.integer)
        rdf.add(graph, uri, rdf.DJHT["name"], name, XSD.string)
        rdf.add(graph, uri, rdf.DJHT["association_criteria"], domain, XSD.string)
    db.add_triples_from_graph(graph)


def _count_groups(db):
    rows = list(db.sparql.query(
        f"SELECT (COUNT(DISTINCT ?g) AS ?n) WHERE {{ GRAPH <{config.state_graph}> {{ "
        f"?g a <{rdf.DJHT['InstitutionGroup']}> }} }}"))
    return int(rows[0][0])


def _refresh(db):
    db.delete_groups_by_id([g[2] for g in CONFIG_GROUPS])
    return [db.insert_group(name, True, is_featured, gid, pid, dom)
            for name, is_featured, gid, pid, dom in CONFIG_GROUPS]


class TestInsertGroup:
    def test_uri_derives_from_id(self, db):
        uuid_value = db.insert_group("Delft", True, True, 28586, 28585, "tudelft.nl")
        assert uuid_value == rdf.uri_to_uuid(rdf.stable_node("group", 28586))

    def test_reinsert_same_id_is_idempotent(self, db):
        first = db.insert_group("Delft", True, True, 28586, 28585, "tudelft.nl")
        second = db.insert_group("Delft", True, True, 28586, 28585, "tudelft.nl")
        assert first == second
        assert _count_groups(db) == 1


class TestDeleteGroupsById:
    def test_removes_group_regardless_of_uri(self, db):
        # A group already present under a random URI (not the deterministic one).
        _seed_preexisting_groups(db, [("Delft", 28586, 28585, "tudelft.nl")])
        db.delete_groups_by_id([28586])
        assert _count_groups(db) == 0

    def test_leaves_other_ids_alone(self, db):
        _seed_preexisting_groups(db, [("Keep", 99001, 28585, "keep.nl")])
        db.delete_groups_by_id([28586])  # different id
        assert _count_groups(db) == 1


class TestRefresh:
    @pytest.mark.parametrize("extra_existing, expected", [
        # Only the config-managed groups already present.
        ([], len(CONFIG_GROUPS)),
        # Plus a group not in the config: must be left alone.
        ([("Retired Institution", 99001, 28585, "retired.nl")], len(CONFIG_GROUPS) + 1),
    ])
    def test_no_duplicates_and_idempotent(self, db, extra_existing, expected):
        _seed_preexisting_groups(
            db, [(n, i, p, d) for n, _, i, p, d in CONFIG_GROUPS] + extra_existing)
        assert _count_groups(db) == expected  # pre-existing copies, not reconciled yet

        _refresh(db)
        assert _count_groups(db) == expected  # reconciled in place, no duplicates
        _refresh(db)
        assert _count_groups(db) == expected  # still stable across boots

    def test_deterministic_uris_across_boots(self, db):
        _seed_preexisting_groups(db, [(n, i, p, d) for n, _, i, p, d in CONFIG_GROUPS])
        assert _refresh(db) == _refresh(db)  # same URIs, no churn
