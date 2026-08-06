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

## Deferrals

- Publish does not warm the git-statistics caches. Legacy does this by calling
  its own v3 handlers — a cache warm, not a behaviour change. Restore it when
  the api-v3 group ports those endpoints.
- The new stack sends e-mail through the same `EmailInterface` that ui.py
  configures for the legacy server (shared as `app.state.email`). Without that
  bootstrap, sends are skipped and logged — same as a legacy instance without
  SMTP settings.
