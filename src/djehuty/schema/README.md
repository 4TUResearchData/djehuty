# Writing a migration

Schema and reference-data migrations, applied by
`djehuty.schema.migrate.MigrationRunner`. Full design: `doc/database-migrations.md`.

## What the runner does

- **Forward-only.** Files run in numeric-prefix order.
- **Once.** Each applied migration is logged in `<migrations_graph>` with a SHA-256
  checksum and timestamp. Applied ones are skipped.
- **Drift detection.** Edit a migration after it ran somewhere and the runner refuses
  to continue.
- **Auto-stamp.** If the graph already holds the seed but the log is empty (restored
  backup, or Figshare import), `0001_initial` is stamped instead of re-run. Detected by
  the `<this> djht:initialized` marker every seeding path writes, or by existing
  `djht:Category` nodes on older graphs.

## Write idempotent migrations

The runner can't wrap the SPARQL `UPDATE` and the log `INSERT` in one transaction
(Virtuoso over HTTP has none). A crash can leave the graph half-changed with no log
row, and re-running `upgrade` retries the whole migration. That's only safe when
applying twice equals applying once, so make every migration idempotent.

## File naming

```
NNNN_<lower_snake_case_slug>.{ttl,sparql}
```

- `NNNN`: zero-padded sequence, sets the order. `0001_initial` is the seed.
- `slug`: present tense (`add_orcid_field`, `seed_new_licenses`).
- `.ttl` for pure inserts, `.sparql` for updates, deletes, and conditional inserts.

## Idempotency rules

### `.ttl`

Give subjects deterministic URIs, so re-applying is a set-merge no-op. Derive them from
the record's natural key with `rdf.stable_node(prefix, *seeds)` (UUIDv5), like
`insert_group` and `insert_category` do.

✅
```turtle
djht:ReviewExpedited a djht:ReviewType ; rdfs:label "expedited"^^xsd:string .
```

❌ random URI, re-applying duplicates:
```turtle
<review-type:9f3a-...> a djht:ReviewType ; rdfs:label "expedited"^^xsd:string .
```

### `.sparql`

Guard inserts with `FILTER NOT EXISTS` (or `MINUS`) so re-running is a no-op. Delete is
naturally idempotent. For updates use `DELETE/INSERT WHERE`, not `INSERT DATA`: a
changed label would otherwise leave both values.

```sparql
INSERT { GRAPH <...> { ?license rdfs:comment "Open source license."@en } }
WHERE  { GRAPH <...> { ?license a djht:License .
         FILTER NOT EXISTS { ?license rdfs:comment ?_ } } }
```

### Match reference data by shape, not URI

The same record has different URIs across graphs (random before `stable_node`,
deterministic after). Don't hardcode a URI, match on the key:

```sparql
?lang a djht:Language ; djht:shortcode "nl" .
```

## Test loop

```
just dev
djehuty migrate status  -c <config>
djehuty migrate upgrade -c <config>
djehuty migrate upgrade -c <config>   # must report 0 applied
```

The second `upgrade` reporting `0 applied` is the idempotency check. If it reapplies,
your body needs a guard. Unit harness: `tests/unit/test_migrate.py`.
