# Writing a migration

This folder holds the schema and reference-data migrations that
`djehuty.schema.migrate.MigrationRunner` applies. The full design is in
`doc/database-migrations.md`.

## What the runner gives you

- **Forward-only ordering.** Files run in numeric-prefix order.
- **Applied once.** Every applied migration is recorded in `<migrations_graph>` with
  a SHA-256 checksum and a timestamp. Already-applied migrations are skipped.
- **Drift detection.** If you edit a migration file after it was applied somewhere,
  the runner refuses to go.
- **Auto-stamp for old backups.** When you restore a backup that predates this
  runner, the runner spots the legacy init marker and stamps `0001_initial` (without
  running its body), so the seed data already in the backup is not duplicated. Later
  migrations run normally.

## What you have to give it: write **idempotent** migrations

The runner can't wrap a SPARQL `UPDATE` and the log `INSERT` in one transaction
(Virtuoso over HTTP has no cross-update transaction). Two things follow from that:

1. A crash mid-migration can leave the state graph half-changed and the log row
   unwritten. Re-running `upgrade` retries the migration.
2. The auto-stamp path skips `0001_initial`'s body when restoring an old backup. So a
   later migration must not assume the previous migration's body actually ran on this
   graph.

Both are fine if your migration is idempotent: running it twice has the same effect
as running it once. So always write them that way.

## File naming

```
NNNN_<lower_snake_case_slug>.{ttl,sparql}
```

- `NNNN`: zero-padded sequence, sets the order. `0001_initial` is reserved for the
  AS-IS seed.
- `slug`: describes the change in present tense (`add_orcid_field`,
  `fix_review_label`, `seed_new_licenses`).
- Use `.ttl` for **pure inserts**; `.sparql` for **updates**, deletes, and
  conditional inserts.

## Idempotency rules

### `.ttl` migrations

Use **deterministic URIs** in the subject. Re-applying then becomes a plain
set-merge no-op.

✅ Good:

```turtle
@prefix djht: <https://ontologies.data.4tu.nl/djehuty/0.0.1/> .

djht:ReviewExpedited a djht:ReviewType ;
    rdfs:label "expedited"^^xsd:string .
```

❌ Bad, a random URI means re-applying creates a duplicate:

```turtle
<review-type:9f3a-...> a djht:ReviewType ;
    rdfs:label "expedited"^^xsd:string .
```

`0001_initial.ttl` uses random `unique_node` URIs because it's an AS-IS extract of
the legacy code. Don't do that in new migrations.

### `.sparql` migrations

Always guard with `FILTER NOT EXISTS` (or `MINUS`) so re-running is a no-op.

✅ Add a property to every License that doesn't have it yet:

```sparql
PREFIX djht:  <https://ontologies.data.4tu.nl/djehuty/0.0.1/>
PREFIX rdfs:  <http://www.w3.org/2000/01/rdf-schema#>

INSERT { GRAPH <https://data.4tu.nl/portal/self-test> {
    ?license rdfs:comment "Open source license."@en .
}}
WHERE {
    GRAPH <https://data.4tu.nl/portal/self-test> {
        ?license a djht:License .
        FILTER NOT EXISTS { ?license rdfs:comment ?_ }
    }
}
```

✅ Delete is idempotent by nature, deleting what isn't there does nothing:

```sparql
DELETE WHERE {
    GRAPH <https://data.4tu.nl/portal/self-test> {
        ?subject djht:deprecated_field ?_
    }
}
```

❌ Naïve `INSERT DATA` with a hand-chosen subject already in the graph:

```sparql
INSERT DATA {
    GRAPH <https://data.4tu.nl/portal/self-test> {
        djht:NewType a djht:ReviewType ;
            rdfs:label "new" .
    }
}
```

Works once, and re-running is fine for typed assertions because RDF is set-semantic.
But if you re-apply after changing the label, you'd leave both labels in the graph.
Prefer `DELETE/INSERT WHERE` for mutations.

### Reference data by shape, not by URI

A migration can't assume a specific subject URI for, say, the Dutch language, because
(a) the legacy backup uses random UUIDs and (b) `0001_initial.ttl` uses different
random UUIDs. Look it up by shape instead:

```sparql
?lang a djht:Language ; djht:shortcode "nl" .
```

This works whatever URI happens to identify Dutch in the deployed graph.

## Local test loop

```
just dev                              # spin up the dev stack
djehuty migrate status -c <config>    # check before
djehuty migrate upgrade -c <config>   # apply
djehuty migrate status -c <config>    # verify
djehuty migrate upgrade -c <config>   # second run must report 0 applied
```

The second `upgrade` reporting `0 applied` is the idempotency check at runtime. If it
reapplies, your migration is wrongly recorded as a new file on disk. If it says
`0 applied` but you still see drift in the data, your migration body isn't idempotent
and needs a guard.

For testing a migration body on its own, see `tests/unit/test_migrate.py` for the
in-memory `rdflib` harness.
