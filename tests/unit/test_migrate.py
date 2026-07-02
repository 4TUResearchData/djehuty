"""Unit tests for the schema migration runner.

These tests exercise :class:`djehuty.schema.migrate.MigrationRunner`
against an in-memory rdflib ``Dataset`` so they run without a real
Virtuoso instance.  The real boot path is covered by the e2e suite.
"""

import tempfile
from pathlib import Path

import pytest
from rdflib import RDF, XSD, Dataset, Graph, Literal, Namespace, URIRef
from rdflib.plugins.stores import memory

from djehuty.schema.migrate import (
    DJH_MIG,
    MU_MIGR,
    DriftDetectedError,
    MigrationRunner,
)
from djehuty.utils import rdf as rdf_utils

STATE_GRAPH = "http://test/state"
MIG_GRAPH = "http://test/migrations"
DJHT = Namespace("https://ontologies.data.4tu.nl/djehuty/0.0.1/")
INIT_MARKER = (URIRef("this"), DJHT.initialized, Literal("true", datatype=XSD.boolean))


# --- Fixtures ---


@pytest.fixture
def real_migrations_dir():
    """Path to the production migrations directory."""
    root = Path(__file__).resolve().parents[2]
    return root / "src" / "djehuty" / "schema" / "migrations"


@pytest.fixture
def tmp_migrations_dir():
    """Fresh empty migrations directory; tests populate it as needed."""
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture
def in_memory_dataset():
    store = memory.Memory(identifier=URIRef(STATE_GRAPH))
    return Dataset(store=store, default_union=True)


@pytest.fixture
def runner_real(in_memory_dataset, real_migrations_dir):
    return MigrationRunner(
        sparql_graph=in_memory_dataset,
        migrations_dir=real_migrations_dir,
        target_graph=STATE_GRAPH,
        migrations_graph=MIG_GRAPH,
        djehuty_version="test",
    )


@pytest.fixture
def runner_tmp(in_memory_dataset, tmp_migrations_dir):
    return MigrationRunner(
        sparql_graph=in_memory_dataset,
        migrations_dir=tmp_migrations_dir,
        target_graph=STATE_GRAPH,
        migrations_graph=MIG_GRAPH,
        djehuty_version="test",
    )


def _write_migration(migrations_dir, identifier, kind, body):
    path = migrations_dir / f"{identifier}.{kind}"
    with open(path, "w", encoding="utf-8") as out:
        out.write(body)
    return path


# --- Tests ---


class TestFresh:
    def test_apply_initial(self, runner_real, in_memory_dataset):
        """Fresh upgrade seeds 0001_initial, writes a log row and the marker."""
        assert runner_real.current() is None
        assert runner_real.head() == "0001_initial"

        assert runner_real.upgrade() == 1
        assert runner_real.current() == "0001_initial"

        state = in_memory_dataset.graph(URIRef(STATE_GRAPH))
        log = in_memory_dataset.graph(URIRef(MIG_GRAPH))
        assert len(state) > 1000, "0001_initial should produce >1000 triples"
        assert INIT_MARKER in state
        log_subjects = {s for s, _, _ in log.triples((None, None, MU_MIGR.Migration))}
        assert len(log_subjects) == 1


class TestIdempotency:
    def test_second_upgrade_is_noop(self, runner_real):
        assert runner_real.upgrade() == 1
        assert runner_real.upgrade() == 0
        assert runner_real.verify() is True


class TestStamp:
    def test_stamp_head_writes_log_without_body(self, runner_real, in_memory_dataset):
        assert runner_real.stamp("head") == 1
        state = in_memory_dataset.graph(URIRef(STATE_GRAPH))
        log = in_memory_dataset.graph(URIRef(MIG_GRAPH))
        assert len(state) == 0  # body not run
        assert len(log) > 0
        assert runner_real.upgrade() == 0  # already recorded

    def test_stamp_skips_already_applied(self, runner_real):
        runner_real.upgrade()
        assert runner_real.stamp("head") == 0


class TestDrift:
    def test_drift_detected_after_log_tampering(self, runner_real, in_memory_dataset):
        runner_real.upgrade()
        assert runner_real.verify() is True

        # Tamper: replace the stored checksum with a bogus value.
        log = in_memory_dataset.graph(URIRef(MIG_GRAPH))
        cs_triples = list(log.triples((None, DJH_MIG.checksum, None)))
        assert len(cs_triples) == 1
        subject, predicate, _ = cs_triples[0]
        log.remove((subject, predicate, None))
        log.add((subject, predicate, Literal("sha256:tampered")))

        assert runner_real.verify() is False
        with pytest.raises(DriftDetectedError):
            runner_real.upgrade()


class TestAutoStamp:
    """`upgrade()` auto-stamps 0001_initial when the graph is already seeded."""

    @pytest.mark.parametrize(
        "seed_triple",
        [
            pytest.param(INIT_MARKER, id="legacy-marker"),
            pytest.param(
                (URIRef("category:legacy-random"), RDF.type, DJHT.Category),
                id="seed-content",
            ),
        ],
    )
    def test_auto_stamps_when_already_seeded(
        self, seed_triple, runner_real, in_memory_dataset
    ):
        # Marker present, or seeded without one (Figshare import): stamp 0001,
        # don't re-run its body, or the static data doubles up.
        state = in_memory_dataset.graph(URIRef(STATE_GRAPH))
        state.add(seed_triple)
        before = len(state)

        assert runner_real.upgrade() == 1
        assert len(state) == before  # stamped, not run
        assert runner_real.current() == "0001_initial"
        assert runner_real.upgrade() == 0

    def test_seed_probe_never_fatal(self, runner_real, monkeypatch):
        # A failing ASK (endpoint down) must not crash: the probe returns False
        # so upgrade falls through to applying the seed instead of raising.
        def boom(*_):
            raise RuntimeError("endpoint down")

        monkeypatch.setattr(runner_real.sparql, "query", boom)
        assert runner_real._state_graph_is_seeded() is False

    def test_auto_stamp_only_affects_the_initial_migration(
        self, in_memory_dataset, tmp_path
    ):
        """With 0002 present, the marker stamps only 0001; 0002 still runs."""
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()
        (migrations_dir / "0001_seed.ttl").write_text(
            '<http://test/legacy> <http://test/p> "old" .\n'
        )
        new_subject = "http://test/added-by-0002"
        (migrations_dir / "0002_new.sparql").write_text(
            f"INSERT DATA {{ GRAPH <{STATE_GRAPH}> {{ "
            f'<{new_subject}> <http://test/p> "new" . }} }}\n'
        )
        runner = MigrationRunner(
            sparql_graph=in_memory_dataset,
            migrations_dir=migrations_dir,
            target_graph=STATE_GRAPH,
            migrations_graph=MIG_GRAPH,
            djehuty_version="test",
        )

        # Pre-runner backup: marker set, no 0001 body present.
        state = in_memory_dataset.graph(URIRef(STATE_GRAPH))
        state.add(INIT_MARKER)

        assert runner.upgrade() == 2  # 0001 stamped, 0002 applied
        assert list(state.triples((URIRef("http://test/legacy"), None, None))) == []
        assert len(list(state.triples((URIRef(new_subject), None, None)))) == 1


class TestDiscovery:
    def test_filename_pattern(self, runner_tmp, tmp_migrations_dir):
        # Non-conforming files are ignored; conforming files are sorted.
        _write_migration(tmp_migrations_dir, "0002_b", "ttl", "")
        _write_migration(tmp_migrations_dir, "0001_a", "ttl", "")
        (tmp_migrations_dir / "README.md").write_text("ignore me")
        (tmp_migrations_dir / "0001-bad.ttl").write_text("ignore me")  # wrong sep

        ids = [m.identifier for m in runner_tmp._discover()]
        assert ids == ["0001_a", "0002_b"]


class TestSparqlMigration:
    def test_sparql_kind_runs_update(
        self, runner_tmp, tmp_migrations_dir, in_memory_dataset
    ):
        body = (
            f"INSERT DATA {{ GRAPH <{STATE_GRAPH}> {{ "
            f'<http://test/x> <http://test/p> "hello" . }} }}'
        )
        _write_migration(tmp_migrations_dir, "0001_marker", "sparql", body)

        assert runner_tmp.upgrade() == 1
        state = in_memory_dataset.graph(URIRef(STATE_GRAPH))
        assert len(list(state.triples((URIRef("http://test/x"), None, None)))) == 1


class TestInitialFileShape:
    """Checks on the committed 0001_initial.ttl."""

    def test_contains_expected_enum_types(self, real_migrations_dir):
        graph = Graph()
        graph.parse(str(real_migrations_dir / "0001_initial.ttl"), format="turtle")
        # 5 review states, 6 log-entry types (from insert_static_triplets).
        assert len(list(graph.subjects(RDF.type, DJHT.ReviewType))) == 5
        assert len(list(graph.subjects(RDF.type, DJHT.LogEntryType))) == 6

    def test_reference_data_uses_stable_uris(self, real_migrations_dir):
        # Seed URIs are deterministic (stable_node), not random.
        graph = Graph()
        graph.parse(str(real_migrations_dir / "0001_initial.ttl"), format="turtle")
        for category in graph.subjects(RDF.type, DJHT.Category):
            cid = graph.value(category, DJHT.id)
            assert category == rdf_utils.stable_node("category", int(cid))
        for language in graph.subjects(RDF.type, DJHT.Language):
            code = graph.value(language, DJHT.shortcode)
            assert language == rdf_utils.stable_node("language", str(code))


class TestInitialSeedIdempotency:
    def test_reapplying_seed_body_is_a_noop(self, runner_real, in_memory_dataset):
        runner_real.upgrade()
        state = in_memory_dataset.graph(URIRef(STATE_GRAPH))
        before = len(list(state.subjects(RDF.type, DJHT.Category)))
        assert before == 294

        # Re-run the body directly: deterministic URIs make it a set-merge no-op.
        runner_real._apply_one(runner_real._discover()[0])
        assert len(list(state.subjects(RDF.type, DJHT.Category))) == before
