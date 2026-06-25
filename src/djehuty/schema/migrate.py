"""Forward-only migration runner for djehuty's RDF store.

See ``doc/database-migrations.md`` for the full design.  In short, the
runner discovers ``NNNN_<slug>.{ttl,sparql}`` files under
``migrations/``, applies them in numeric-prefix order, and records each
application in a dedicated named graph using mu-semtech's ``muMigr:``
vocabulary plus a small djehuty extension (``djhmig:``).

The runner uses the SPARQL ``Graph`` already configured on
:class:`djehuty.web.database.SparqlInterface`; it does not open its own
SPARQL connection.
"""

import hashlib
import importlib.metadata
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from rdflib import Graph, Namespace, URIRef, XSD


MU_MIGR = Namespace ("http://mu.semte.ch/vocabularies/migrations/")
DJH_MIG = Namespace ("https://ontologies.data.4tu.nl/djehuty/migration/")

## Pre-runner djehuty wrote ``<this> djht:initialized "true"`` to gate
## one-shot init.  We use this triple as a signal that the state graph
## was bootstrapped by the legacy code path and must not be re-seeded.
_LEGACY_DJHT      = "https://ontologies.data.4tu.nl/djehuty/0.0.1/"
_LEGACY_INIT_URI  = f"{_LEGACY_DJHT}initialized"

_MIGRATION_RE = re.compile (r"^(\d{4})_([a-z0-9_]+)\.(ttl|sparql)$")
_INSERT_BATCH = 250


class DriftDetected (RuntimeError):
    """Raised when an applied migration's stored checksum no longer matches disk."""


@dataclass
class Migration:
    """A migration as discovered on disk."""

    identifier: str
    filename:   str
    kind:       str
    path:       Path
    checksum:   str


@dataclass
class MigrationStatus:
    """One row in the output of :meth:`MigrationRunner.status`."""

    identifier:       str
    on_disk_checksum: str
    applied_at:       Optional[str]
    applied_checksum: Optional[str]
    drift:            bool

    @property
    def is_applied (self):
        """True if this migration has a log row in the migrations graph."""
        return self.applied_at is not None


class MigrationRunner:
    """Forward-only runner for ``.ttl`` and ``.sparql`` migrations."""

    def __init__ (self, sparql_graph, migrations_dir,
                  target_graph, migrations_graph,
                  djehuty_version=None):
        self.log              = logging.getLogger (__name__)
        self.sparql           = sparql_graph
        self.migrations_dir   = Path (migrations_dir)
        self.target_graph     = target_graph
        self.migrations_graph = migrations_graph.rstrip ("/")
        self.djehuty_version  = djehuty_version or _detect_version ()

    @classmethod
    def from_config (cls, db, config):
        """Build a runner from a :class:`SparqlInterface` and config."""
        return cls (
            sparql_graph     = db.sparql,
            migrations_dir   = Path (__file__).parent / "migrations",
            target_graph     = config.state_graph,
            migrations_graph = config.migrations_graph,
        )

    ## ------------------------------------------------------------------
    ## Public API
    ## ------------------------------------------------------------------

    def head (self):
        """Return the latest migration id on disk, or ``None`` if there are none."""

        migrations = self._discover ()
        return migrations[-1].identifier if migrations else None

    def current (self):
        """Return the latest applied migration id, or ``None``."""

        applied = self._applied_map ()
        return sorted (applied.keys ())[-1] if applied else None

    def status (self):
        """Return a :class:`MigrationStatus` per migration on disk."""

        applied = self._applied_map ()
        report  = []
        for migration in self._discover ():
            at, checksum = applied.get (migration.identifier, (None, None))
            drift = checksum is not None and checksum != migration.checksum
            report.append (MigrationStatus (
                identifier       = migration.identifier,
                on_disk_checksum = migration.checksum,
                applied_at       = at,
                applied_checksum = checksum,
                drift            = drift,
            ))
        return report

    def verify (self):
        """Return ``True`` iff every applied migration matches its on-disk checksum."""

        clean = True
        for entry in self.status ():
            if entry.drift:
                self.log.error (
                    "Migration %s drifted: stored checksum %s != on-disk %s",
                    entry.identifier,
                    entry.applied_checksum,
                    entry.on_disk_checksum)
                clean = False
        return clean

    def upgrade (self, to=None):
        """Apply every pending migration up to TO (default: head)."""

        if not self.verify ():
            raise DriftDetected (
                "One or more applied migrations have drifted; refusing to apply more.")

        applied        = self._applied_map ()
        migrations     = self._discover ()
        applied_count  = 0

        # Auto-stamp when restoring a backup taken from pre-runner djehuty.
        # See doc/database-migrations.md §4.3.  Only the *first* migration
        # corresponds to the legacy ``insert_static_triplets`` content;
        # anything after that must actually execute.
        if (not applied
                and migrations
                and self._has_legacy_init_marker ()):
            initial = migrations[0]
            self.log.warning (
                "Detected legacy state-graph init marker but no migration log; "
                "auto-stamping %s (matches pre-runner static_triplets content). "
                "Subsequent migrations will run normally.",
                initial.identifier)
            self._record_application (initial)
            applied[initial.identifier] = (None, initial.checksum)
            applied_count += 1

        for migration in migrations:
            if migration.identifier in applied:
                continue
            if to is not None and migration.identifier > to:
                break
            self._apply_one (migration)
            applied_count += 1
        return applied_count

    def stamp (self, to="head"):
        """Write log rows up to TO without running the migration bodies."""

        migrations = self._discover ()
        applied    = self._applied_map ()

        if to == "head":
            target = migrations[-1].identifier if migrations else None
        else:
            target = to

        stamped = 0
        for migration in migrations:
            if migration.identifier in applied:
                continue
            if target is not None and migration.identifier > target:
                break
            self._record_application (migration)
            stamped += 1
        return stamped

    ## ------------------------------------------------------------------
    ## Discovery
    ## ------------------------------------------------------------------

    def _discover (self):
        """List migrations on disk ordered by numeric prefix."""

        if not self.migrations_dir.is_dir ():
            return []

        migrations = []
        for entry in sorted (os.listdir (self.migrations_dir)):
            match = _MIGRATION_RE.match (entry)
            if not match:
                if not entry.startswith ("."):
                    self.log.debug ("Skipping unrecognised entry %s", entry)
                continue
            seq, slug, kind = match.groups ()
            path = self.migrations_dir / entry
            with open (path, "rb") as source:
                digest = hashlib.sha256 (source.read ()).hexdigest ()
            migrations.append (Migration (
                identifier = f"{seq}_{slug}",
                filename   = entry,
                kind       = kind,
                path       = path,
                checksum   = f"sha256:{digest}",
            ))
        return migrations

    ## ------------------------------------------------------------------
    ## SPARQL primitives
    ## ------------------------------------------------------------------

    def _run_update (self, query):
        self.sparql.update (query)
        self.sparql.commit ()

    def _run_select (self, query):
        return list (self.sparql.query (query))

    def _has_legacy_init_marker (self):
        """True iff the state graph carries the pre-runner init marker."""

        query = (
            f"ASK {{ GRAPH <{self.target_graph}> {{\n"
            f"  <this> <{_LEGACY_INIT_URI}> \"true\"^^<{XSD.boolean}>\n"
            f"}} }}")
        try:
            return bool (self.sparql.query (query).askAnswer)
        except Exception as error:  # noqa: BLE001 — non-fatal probe
            self.log.debug ("Legacy-marker probe failed: %s", error)
            return False

    def _applied_map (self):
        """Return ``{identifier: (applied_at, checksum)}`` from the log graph."""

        query = (
            f"PREFIX muMigr: <{MU_MIGR}>\n"
            f"PREFIX djhmig: <{DJH_MIG}>\n"
            f"SELECT ?m ?at ?cs WHERE {{\n"
            f"  GRAPH <{self.migrations_graph}> {{\n"
            f"    ?m a muMigr:Migration ;\n"
            f"       muMigr:executedAt ?at .\n"
            f"    OPTIONAL {{ ?m djhmig:checksum ?cs }}\n"
            f"  }}\n"
            f"}}")

        prefix = f"{self.migrations_graph}/"
        out    = {}
        for row in self._run_select (query):
            uri = str (row[0])
            if not uri.startswith (prefix):
                continue
            identifier = uri[len (prefix):]
            applied_at = str (row[1])
            checksum   = str (row[2]) if row[2] is not None else None
            out[identifier] = (applied_at, checksum)
        return out

    ## ------------------------------------------------------------------
    ## Application
    ## ------------------------------------------------------------------

    def _apply_one (self, migration):
        self.log.info ("Applying migration %s", migration.filename)
        if migration.kind == "ttl":
            graph = Graph ()
            graph.parse (str (migration.path), format="turtle")
            self._insert_graph (graph)
        elif migration.kind == "sparql":
            with open (migration.path, "r", encoding="utf-8") as source:
                body = source.read ()
            self._run_update (body)
        else:
            raise ValueError (f"Unsupported migration kind: {migration.kind}")
        self._record_application (migration)

    def _insert_graph (self, graph):
        """Batch INSERT GRAPH into the target graph."""

        counter = 0
        batch   = Graph ()
        for triple in graph:
            batch.add (triple)
            counter += 1
            if counter >= _INSERT_BATCH:
                self._run_update (self._insert_data_query (batch))
                batch   = Graph ()
                counter = 0
        if counter > 0:
            self._run_update (self._insert_data_query (batch))

    def _insert_data_query (self, graph):
        body = graph.serialize (format="nt")
        if isinstance (body, bytes):
            body = body.decode ("utf-8")
        return (f"INSERT DATA {{ GRAPH <{self.target_graph}> {{\n"
                f"{body}\n"
                f"}} }}")

    def _record_application (self, migration):
        """Write the ``muMigr:Migration`` log row for MIGRATION."""

        applied_at = datetime.now (timezone.utc).strftime ("%Y-%m-%dT%H:%M:%SZ")
        uri        = URIRef (f"{self.migrations_graph}/{migration.identifier}")
        query = (
            f"PREFIX muMigr: <{MU_MIGR}>\n"
            f"PREFIX djhmig: <{DJH_MIG}>\n"
            f"INSERT DATA {{ GRAPH <{self.migrations_graph}> {{\n"
            f"  <{uri}> a muMigr:Migration ;\n"
            f"    muMigr:filename \"{migration.filename}\" ;\n"
            f"    muMigr:executedAt \"{applied_at}\"^^<{XSD.dateTime}> ;\n"
            f"    djhmig:checksum \"{migration.checksum}\" ;\n"
            f"    djhmig:appliedBy \"djehuty-{self.djehuty_version}\" .\n"
            f"}} }}")
        self._run_update (query)


def _detect_version ():
    try:
        return importlib.metadata.version ("djehuty")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"
