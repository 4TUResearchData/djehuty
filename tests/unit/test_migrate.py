"""Unit tests for the schema migration runner.

These tests exercise :class:`djehuty.schema.migrate.MigrationRunner`
against an in-memory rdflib ``Dataset`` so they run without a real
Virtuoso instance.  The real boot path is covered by the e2e suite.
"""

import hashlib
import os
import tempfile
from pathlib import Path

import pytest
from rdflib import Dataset, URIRef
from rdflib.plugins.stores import memory

from djehuty.schema.migrate import (
    DJH_MIG,
    DriftDetected,
    MU_MIGR,
    MigrationRunner,
)


STATE_GRAPH = "http://test/state"
MIG_GRAPH   = "http://test/migrations"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def real_migrations_dir():
    """Path to the production migrations directory (used for happy-path tests)."""
    return Path (__file__).resolve ().parents[2] / "src" / "djehuty" / "schema" / "migrations"


@pytest.fixture
def tmp_migrations_dir():
    """Fresh empty migrations directory; tests populate it as needed."""
    with tempfile.TemporaryDirectory () as tmp:
        yield Path (tmp)


@pytest.fixture
def in_memory_dataset():
    store = memory.Memory (identifier=URIRef (STATE_GRAPH))
    return Dataset (store=store, default_union=True)


@pytest.fixture
def runner_real (in_memory_dataset, real_migrations_dir):
    return MigrationRunner (
        sparql_graph     = in_memory_dataset,
        migrations_dir   = real_migrations_dir,
        target_graph     = STATE_GRAPH,
        migrations_graph = MIG_GRAPH,
        djehuty_version  = "test",
    )


@pytest.fixture
def runner_tmp (in_memory_dataset, tmp_migrations_dir):
    return MigrationRunner (
        sparql_graph     = in_memory_dataset,
        migrations_dir   = tmp_migrations_dir,
        target_graph     = STATE_GRAPH,
        migrations_graph = MIG_GRAPH,
        djehuty_version  = "test",
    )


def _write_migration (migrations_dir, identifier, kind, body):
    path = migrations_dir / f"{identifier}.{kind}"
    with open (path, "w", encoding="utf-8") as out:
        out.write (body)
    return path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestFresh:
    def test_apply_initial (self, runner_real, in_memory_dataset):
        """Fresh upgrade applies 0001_initial and writes a log row."""

        assert runner_real.current () is None
        assert runner_real.head () == "0001_initial"

        applied = runner_real.upgrade ()
        assert applied == 1
        assert runner_real.current () == "0001_initial"

        # State graph populated, log graph has exactly one Migration record.
        state = in_memory_dataset.graph (URIRef (STATE_GRAPH))
        log   = in_memory_dataset.graph (URIRef (MIG_GRAPH))
        assert len (state) > 1000, "0001_initial should produce >1000 triples"
        log_subjects = {s for s, _, _ in log.triples ((None, None, MU_MIGR.Migration))}
        assert len (log_subjects) == 1


class TestIdempotency:
    def test_second_upgrade_is_noop (self, runner_real):
        first  = runner_real.upgrade ()
        second = runner_real.upgrade ()
        assert first == 1
        assert second == 0
        assert runner_real.verify () is True


class TestStamp:
    def test_stamp_head_writes_log_without_body (self, runner_real, in_memory_dataset):
        stamped = runner_real.stamp ("head")
        assert stamped == 1
        # State graph is empty — only the log graph has triples.
        state = in_memory_dataset.graph (URIRef (STATE_GRAPH))
        log   = in_memory_dataset.graph (URIRef (MIG_GRAPH))
        assert len (state) == 0
        assert len (log) > 0
        # A subsequent upgrade is a no-op because 0001 is already recorded.
        assert runner_real.upgrade () == 0

    def test_stamp_skips_already_applied (self, runner_real):
        runner_real.upgrade ()
        # Nothing left to stamp.
        assert runner_real.stamp ("head") == 0


class TestDrift:
    def test_drift_detected_after_log_tampering (self, runner_real, in_memory_dataset):
        runner_real.upgrade ()
        assert runner_real.verify () is True

        # Tamper: replace the stored checksum with a bogus value.
        log = in_memory_dataset.graph (URIRef (MIG_GRAPH))
        cs_triples = list (log.triples ((None, DJH_MIG.checksum, None)))
        assert len (cs_triples) == 1
        subject, predicate, _ = cs_triples[0]
        log.remove ((subject, predicate, None))
        from rdflib import Literal
        log.add ((subject, predicate, Literal ("sha256:tampered")))

        assert runner_real.verify () is False
        with pytest.raises (DriftDetected):
            runner_real.upgrade ()


class TestLegacyMarker:
    """`upgrade()` auto-stamps when restoring a pre-runner backup."""

    def test_upgrade_auto_stamps_when_legacy_marker_present (
            self, runner_real, in_memory_dataset):
        from rdflib import Literal, URIRef, XSD

        # Simulate a backup taken from pre-runner djehuty: state graph
        # carries the legacy <this> djht:initialized "true" marker.
        state = in_memory_dataset.graph (URIRef (STATE_GRAPH))
        state.add ((
            URIRef ("this"),
            URIRef ("https://ontologies.data.4tu.nl/djehuty/0.0.1/initialized"),
            Literal ("true", datatype=XSD.boolean),
        ))
        triples_before = len (state)

        applied = runner_real.upgrade ()
        assert applied == 1

        # Body did NOT run: state graph triple count unchanged.
        assert len (state) == triples_before
        # Log row written so subsequent upgrade is a no-op.
        assert runner_real.current () == "0001_initial"
        assert runner_real.upgrade () == 0

    def test_upgrade_applies_normally_when_no_marker (
            self, runner_real, in_memory_dataset):
        # No legacy marker → standard apply path; body runs.
        assert runner_real.upgrade () == 1
        state = in_memory_dataset.graph (URIRef (STATE_GRAPH))
        assert len (state) > 1000

    def test_legacy_marker_does_not_auto_stamp_later_migrations (
            self, in_memory_dataset, tmp_path):
        """When 0002 exists, the legacy marker stamps only 0001 — 0002 runs."""
        from rdflib import Literal, URIRef, XSD

        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir ()

        # 0001 has fixed-URI content so we can detect it being skipped.
        (migrations_dir / "0001_seed.ttl").write_text (
            "<http://test/legacy> <http://test/p> \"old\" .\n"
        )
        # 0002 inserts something brand-new that the legacy backup can't have.
        new_subject = "http://test/added-by-0002"
        (migrations_dir / "0002_new.sparql").write_text (
            f"INSERT DATA {{ GRAPH <{STATE_GRAPH}> {{ "
            f"<{new_subject}> <http://test/p> \"new\" . }} }}\n"
        )

        runner = MigrationRunner (
            sparql_graph     = in_memory_dataset,
            migrations_dir   = migrations_dir,
            target_graph     = STATE_GRAPH,
            migrations_graph = MIG_GRAPH,
            djehuty_version  = "test",
        )

        # Simulate pre-runner backup: legacy marker set, no 0001 body present.
        state = in_memory_dataset.graph (URIRef (STATE_GRAPH))
        state.add ((
            URIRef ("this"),
            URIRef ("https://ontologies.data.4tu.nl/djehuty/0.0.1/initialized"),
            Literal ("true", datatype=XSD.boolean),
        ))

        applied = runner.upgrade ()
        assert applied == 2  # 1 stamped + 1 actually applied

        # 0001 body skipped — no `<http://test/legacy>` triple in state graph.
        legacy = list (state.triples ((URIRef ("http://test/legacy"), None, None)))
        assert legacy == []

        # 0002 body ran — its new triple is present.
        new = list (state.triples ((URIRef (new_subject), None, None)))
        assert len (new) == 1


class TestDiscovery:
    def test_filename_pattern (self, runner_tmp, tmp_migrations_dir):
        # Non-conforming files are ignored; conforming files are sorted.
        _write_migration (tmp_migrations_dir, "0002_b", "ttl", "")
        _write_migration (tmp_migrations_dir, "0001_a", "ttl", "")
        (tmp_migrations_dir / "README.md").write_text ("ignore me")
        (tmp_migrations_dir / "0001-bad.ttl").write_text ("ignore me")  # wrong sep

        ids = [m.identifier for m in runner_tmp._discover ()]
        assert ids == ["0001_a", "0002_b"]


class TestSparqlMigration:
    def test_sparql_kind_runs_update (self, runner_tmp, tmp_migrations_dir,
                                      in_memory_dataset):
        body = (f"INSERT DATA {{ GRAPH <{STATE_GRAPH}> {{ "
                f"<http://test/x> <http://test/p> \"hello\" . }} }}")
        _write_migration (tmp_migrations_dir, "0001_marker", "sparql", body)

        assert runner_tmp.upgrade () == 1
        state = in_memory_dataset.graph (URIRef (STATE_GRAPH))
        triples = list (state.triples ((URIRef ("http://test/x"), None, None)))
        assert len (triples) == 1


class TestInitialFileShape:
    """Light-weight sanity checks on the committed 0001_initial.ttl."""

    def test_contains_expected_enum_types (self, real_migrations_dir):
        from rdflib import Graph, Namespace, RDF
        djht = Namespace ("https://ontologies.data.4tu.nl/djehuty/0.0.1/")
        graph = Graph ()
        graph.parse (str (real_migrations_dir / "0001_initial.ttl"), format="turtle")

        review_types = list (graph.subjects (RDF.type, djht.ReviewType))
        log_types    = list (graph.subjects (RDF.type, djht.LogEntryType))
        # Sanity bounds borrowed from insert_static_triplets:
        # 5 review states (approved/rejected/closed/assigned/unassigned)
        # and 6 log-entry types (cite/download/git_download/share/view/private_view).
        assert len (review_types) == 5
        assert len (log_types) == 6
