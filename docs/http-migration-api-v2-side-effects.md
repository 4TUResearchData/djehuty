# api-v2 side-effect catalog

The side effects — writes, cache invalidations, e-mails — that each v2 route
must reproduce from its legacy handler. This is scaffolding for the HTTP
migration (see `http-migration.md`); the new stack implements every row, and
the unit tests pin the ones that are easy to get wrong. Delete this file when
the v2 legacy handlers are removed.

The method is described in `http-migration.md` under "Rules of the road";
read-only routes are omitted.

## Datasets — under `/v2/account/articles`

| Route | Side effects |
|---|---|
| `POST /` | `insert_dataset` incl. the author/reference/tag/category/funding lists |
| `PUT /<id>` | `update_dataset` (full field set); assigns the review when a reviewer saves |
| `DELETE /<id>` | `delete_dataset_draft` |
| `POST/PUT /<id>/authors` | `insert_author` + `update_item_list` |
| `DELETE /<id>/authors/<aid>` | `update_item_list` |
| `POST/PUT /<id>/funding` | `insert_funding` + `update_item_list` |
| `DELETE /<id>/funding/<fid>` | `update_item_list` |
| `POST/PUT /<id>/categories` | `update_item_list` (known deviation: PUT merges instead of replacing) |
| `DELETE /<id>/categories/<cid>` | `delete_item_from_list` |
| `DELETE /<id>/embargo` | `delete_dataset_embargo` |
| `POST /<id>/files` | `insert_file` (upload initiation) |
| `DELETE /<id>/files` (`remove_all`) | `delete_items_all_from_list` + both storage-cache invalidations |
| `DELETE /<id>/files/<fid>` | `delete_item_from_list` + both storage-cache invalidations |
| `POST/PUT /<id>/private_links` | `insert_private_link` (attaches internally), `update_private_link` |
| `DELETE /<id>/private_links/<lid>` | `delete_private_links` |
| `POST /<id>/reserve_doi` | DataCite reserve + `update_dataset` (container DOI), via `services.datacite` |
| `POST /<id>/publish` | DOI reserve + metadata push (production-only), `publish_dataset`, review assignment, owner + reviewer e-mails (see deferrals for the git-statistics cache warm) |

## Collections — under `/v2/account/collections`

| Route | Side effects |
|---|---|
| `POST /` | `insert_collection` incl. the articles/authors/categories/tags/references/timeline lists |
| `PUT /<id>` | `update_collection` |
| `DELETE /<id>` | `delete_collection_draft` |
| `POST/PUT /<id>/authors` | `insert_author` + `update_item_list` |
| `DELETE /<id>/authors/<aid>` | filter the author list + `update_item_list` |
| `POST/PUT /<id>/categories` | `update_item_list` (POST merges, PUT replaces) |
| `DELETE /<id>/categories/<cid>` | `delete_item_from_list` |
| `POST/PUT /<id>/articles` | draft-from-published, `update_item_list`, datasets-cache invalidation |
| `DELETE /<id>/articles/<did>` | `delete_item_from_list` + datasets-cache invalidation |
| `POST/PUT /<id>/funding` | `insert_funding` + `update_item_list` |
| `DELETE /<id>/funding/<fid>` | filter the funding list + `update_item_list` |
| `POST /<id>/reserve_doi` | DataCite reserve + `update_collection`, via `services.datacite` |

## Behaviours pinned by unit tests

- Paging: `limit` has no upper bound (the web UI sends 10000), absent values
  run unbounded, and mixing page/limit styles is a 400.
- Private listings (collections, authors, funding, categories) pass
  `is_published=False`/`None` so drafts are visible.
- Submit-for-review creates a review *without a status*; a reviewer's save
  assigns it. Declining only matches reviews that have a status, so the
  reviewer-save assignment must be preserved.

## Known status-code deviations

Not every response is byte-for-byte AS-IS. The new stack resolves a private item
through one shared helper that raises 404 when the item is not the caller's draft,
and it does not re-raise the uncaught exceptions that make legacy answer HTTP 500.
Where legacy crashed, we keep the clean status rather than reintroduce the crash.
These are conscious; reproduce a specific one only if a client depends on the exact
legacy status.

| Route (condition) | Legacy | New |
|---|---|---|
| `DELETE /account/articles/<id>/authors/<aid>` (author absent) | 500 (`StopIteration`) | 204 |
| `DELETE /account/articles/<id>/funding/<fid>` (id absent from a non-empty list) | 500 (`StopIteration`) | 204 |
| `GET /account/articles/<id>/files/<fid>` (file absent) | 500 (`TypeError`) | 404 |
| `GET /articles/<id>/files/<fid>` (file absent) | 500 (`TypeError`) | 404 |
| `DELETE /account/articles/<id>/embargo` (dataset absent) | 500 (`TypeError`) | 404 |
| `GET /account/collections/<id>/categories` (published collection) | 500 (`TypeError`) | 404 |
| `DELETE /account/collections/<id>/categories/<cid>` (published collection) | 403 | 404 |

Reproduced to match legacy: `DELETE .../files/<fid>` and `.../funding/<fid>` on an
empty list return 404, and `DELETE .../categories/<cid>` for an unresolvable id
returns 403.

Other conscious deviations:

- Malformed JSON returns the legacy message (`Failed to decode JSON object: …`) but
  with a string `code` of `InvalidJson`, matching the new stack's string-code
  convention, where legacy used the integer `400`.
- CORS is applied by one middleware across all `/v2` routes (legacy set the headers
  on ~8 public reads); the header *values* match legacy — any origin,
  `Content-Type` only, all headers exposed, no credentials.
- The `POST /*/search` endpoints read `page`/`page_size`/`limit`/`offset` but do not
  reject mixing the two styles; the query-parameter listings still return 400.

## Deferrals

- Publish does not warm the git-statistics caches. Legacy does this by calling
  its own v3 handlers — a cache warm, not a behaviour change. Restore it when
  the api-v3 group ports those endpoints.
- The new stack sends e-mail through the same `EmailInterface` that ui.py
  configures for the legacy server (shared as `app.state.email`). Without that
  bootstrap, sends are skipped and logged — same as a legacy instance without
  SMTP settings.
