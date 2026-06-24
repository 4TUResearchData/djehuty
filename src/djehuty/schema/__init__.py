"""Schema and migration runner for djehuty's RDF store.

The :mod:`djehuty.schema` package owns the lifecycle of the schema and
reference data stored in the SPARQL endpoint.  It provides:

* a forward-only, alembic-style migration runner
  (:class:`djehuty.schema.migrate.MigrationRunner`),
* the migrations themselves under :mod:`djehuty.schema.migrations`, as
  ``.ttl`` (inserts) or ``.sparql`` (updates) files,
* a ``djehuty migrate`` CLI subcommand
  (:mod:`djehuty.schema.cli`).

See ``doc/database-migrations.md`` for the design.
"""
