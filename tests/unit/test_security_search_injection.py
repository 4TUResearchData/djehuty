"""
Security regression tests: search-query input handling.

Unauthenticated input reaching the search queries must be treated as data or
rejected, never as SPARQL syntax. These tests lock the three guards:

    - rdf.is_unsafe_sparql_name       (allow-list for names)
    - rdf.sparql_suffix               ("order" parameter)
    - SparqlInterface.__search_query_to_sparql_filters_v2  ("operator", "key")

They exercise the pure query-building layer, so no Virtuoso is needed.
"""

import tempfile

import pytest

from djehuty.utils import rdf
from djehuty.web.config import config
from djehuty.web.database import SparqlInterface


# SPARQL keywords that must never appear in a generated filter fragment. Their
# presence means an injected value escaped its intended string/name position.
# (Punctuation like '#' is not checked here: it legitimately occurs in the
# xsd datatype IRI of an escaped literal. The verbatim-payload check covers it.)
INJECTION_KEYWORDS = ["UNION", "SELECT", "DELETE", "INSERT", "DROP", "WHERE"]


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


class TestIsUnsafeSparqlName:
    @pytest.mark.parametrize("name", ["downloads", "title", "order_index", "_x", "a1"])
    def test_safe_names_allowed(self, name):
        assert rdf.is_unsafe_sparql_name(name) is False

    @pytest.mark.parametrize(
        "name",
        ["downloads)}#", "a b", "?x", "1;DROP", "", "ti)tle", "x UNION y"],
    )
    def test_unsafe_names_rejected(self, name):
        assert rdf.is_unsafe_sparql_name(name) is True

    def test_none_handling(self):
        assert rdf.is_unsafe_sparql_name(None, allow_none=False) is True
        assert rdf.is_unsafe_sparql_name(None, allow_none=True) is False


class TestSparqlSuffixOrder:
    def test_valid_order_emits_clause(self):
        out = rdf.sparql_suffix("downloads", "asc", 10, 5)
        assert "ORDER BY ASC(?downloads)" in out
        assert "LIMIT 10" in out and "OFFSET 5" in out

    def test_injection_order_is_dropped_but_paging_kept(self):
        payload = "downloads) } ; SELECT * { ?a ?b ?c "
        out = rdf.sparql_suffix(payload, "asc", 10, None)
        assert "ORDER BY" not in out  # unsafe -> no ordering emitted
        assert payload not in out  # payload never reaches the query
        assert "LIMIT 10" in out  # pagination still enforced

    def test_none_order_keeps_paging(self):
        out = rdf.sparql_suffix(None, None, 10, 5)
        assert "ORDER BY" not in out
        assert "LIMIT 10" in out and "OFFSET 5" in out


class TestSearchFilterInjection:
    """The v2 dict-filter builder must skip fake operators and unsafe keys."""

    def _build(self, db, search_for):
        # Private (name-mangled) method under test.
        return db._SparqlInterface__search_query_to_sparql_filters_v2(
            search_for, search_format=None
        )

    def test_benign_field_search_builds_contains(self, db):
        out = self._build(db, [{"title": "climate"}])
        assert "CONTAINS(LCASE(?title)" in out

    def test_fake_operator_is_skipped(self, db):
        evil = "}} ; SELECT ?s WHERE { ?s ?p ?o } #"
        out = self._build(db, [{"title": "a"}, {"operator": evil}, {"title": "b"}])
        assert evil not in out
        for marker in INJECTION_KEYWORDS:
            assert marker not in out

    def test_unsafe_key_is_skipped(self, db):
        evil_key = "title) } UNION SELECT ?s WHERE { ?s ?p ?o } #"
        out = self._build(db, [{evil_key: "value"}])
        assert evil_key not in out
        for marker in INJECTION_KEYWORDS:
            assert marker not in out
        # A safe key in the same request still works.
        out2 = self._build(db, [{evil_key: "value"}, {"tag": "ok"}])
        assert "CONTAINS(LCASE(?tag)" in out2
        for marker in INJECTION_KEYWORDS:
            assert marker not in out2
