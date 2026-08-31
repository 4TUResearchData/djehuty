# api-v3 side-effect catalog

The side effects — writes, cache invalidations, e-mails, external-service
calls, filesystem and git writes — that each v3 route must reproduce from its
legacy handler. This is scaffolding for the HTTP migration (see
`http-migration.md`); the new stack implements every row, and the unit tests
pin the ones that are easy to get wrong. Delete this file when the v3 legacy
handlers are removed.

The method is described in `http-migration.md` under "Rules of the road";
read-only routes are omitted. Cache invalidations that live *inside* a shared
`database.py` method travel with the db call automatically (the new stack holds
the same `SparqlInterface`), so they are not re-listed per route — only the
invalidations a handler performs itself are noted.

## Datasets — publication and review

| Route | Side effects |
|---|---|
| `PUT /v3/datasets/<id>/submit-for-review` | `update_dataset` (full field set incl. category `update_item_list`), `insert_review`; reviewer-pool e-mail `submitted_for_review_notification`; depositor e-mail `dataset_submitted` (production, non-preproduction only). Held under the `SUBMIT_DATASET` process lock across resolve + both writes. |
| `POST /v3/datasets/<id>/publish` | Production only, for `version in (None, new_version)`: DataCite DOI reserve (`POST /dois`) + `update_dataset` (container/versioned DOI, `is_first_online`), then DataCite `PUT /dois/<doi>` with `event=publish` — via `services.datacite`. Always: `update_review` (assign reviewer), `publish_dataset`; git-statistics cache warm for software datasets (languages + contributors); owner e-mail `dataset_approved`; reviewer-pool e-mail `published_dataset_notification`. |
| `POST /v3/datasets/<id>/decline` | `decline_dataset`; owner e-mail `dataset_declined`; reviewer-pool e-mail `declined_dataset_notification`. |
| `POST /v3/collections/<id>/publish` | Production only, per version: DataCite reserve + `update_collection` (DOI, `is_first_online`) + DataCite `PUT /dois/<doi>`, via `services.datacite`. Always: `publish_collection`. |

## Datasets — sub-resources

| Route | Side effects |
|---|---|
| `POST /v3/datasets/<id>/collaborators` | `insert_collaborator` (triple insert + list attach + `datasets_<collaborator_account>` invalidation for the first collaborator). |
| `PUT /v3/datasets/<id>/collaborators/<cid>` | `update_collaborator` (SPARQL update; no cache invalidation). |
| `DELETE /v3/datasets/<id>/collaborators/<cid>` | `delete_collaborator` (invalidates `datasets_<dataset_uuid>`, `datasets`). |
| `POST /v3/datasets/<id>/upload` | `insert_file`, chunked write to `storage/<dataset_id>_<file_uuid>` (0o600 → 0o400), handle.net PID registration (`services.handles`), `update_file`. MD5 strict-check cleanup: `delete_item_from_list` + `<account>_storage` and `<dataset_uuid>_dataset_storage` invalidations + `os.remove`. Held under the `FILE_LIST` lock around the insert. |
| `PUT /v3/datasets/<id>/update-thumbnail` | `dataset_update_thumb` (clear or set); thumbnail written to `thumbnail_storage/<dataset_uuid>.<ext>` via `services.imaging`. |
| `POST/DELETE /v3/datasets/<id>/references` | `update_item_list(..., "references")`. |
| `POST/DELETE /v3/datasets/<id>/tags` | `update_item_list(..., "tags")`. |
| `POST /v3/datasets/<id>/reorder-authors` | `reorder_authors`. |
| `POST /v3/collections/<id>/reorder-authors` | `reorder_authors`. |
| `PUT /v3/authors/<uuid>` | `update_author`. |

## Collections — sub-resources

| Route | Side effects |
|---|---|
| `POST/DELETE /v3/collections/<id>/references` | `update_item_list(..., "references")`. |
| `POST/DELETE /v3/collections/<id>/tags` | `update_item_list(..., "tags")`. |

## Profile and account

| Route | Side effects |
|---|---|
| `PUT /v3/profile` | `update_account` (full field set; invalidates `group`, `accounts`); when categories given, `delete_account_property` + `insert_item_list`. |
| `POST /v3/profile/picture` | Multipart save to `profile_images_storage/<account_uuid>` (0o600), dimension gate (>800×800 → `os.remove` + 400), `update_account(profile_image=...)`. |
| `DELETE /v3/profile/picture` | `os.remove(profile_image)`, `delete_account_property(..., "profile_image")`. |
| `POST /v3/profile/quota-request` | `insert_quota_request`; quota-reviewer e-mail `quota_request`. |
| `PUT /v3/receive-from-ssi` | `insert_account` (when the e-mail is new), `insert_session`, `insert_dataset`. Gated on `config.ssi_psk`. |
| `GET /v3/redirect-from-ssi/<id>/<token>` | Sets the `djehuty_session` cookie (302 redirect; `secure` in production, no httponly/samesite — AS-IS). |

## Reviews and admin

| Route | Side effects |
|---|---|
| `PUT /v3/datasets/<id>/assign-reviewer/<rid>` | `update_review(status="assigned")` (invalidates `datasets_<author_account>`, `reviews`). Reviewer privilege checked on the **cookie** session. |
| `POST /v3/datasets/<id>/repair_md5s` | Per missing-checksum file: recompute MD5 from disk + `update_file` (invalidates `<account>_storage`, `<dataset_uuid>_dataset_storage`). Admin (cookie) only. |
| `GET /v3/explore/clear-cache` | Invalidates `explorer_properties`, `explorer_types`, `explorer_property_types`. Admin. |
| `GET /v3/admin/accounts/clear-cache` | Invalidates `accounts`. Admin. |
| `GET /v3/admin/reviews/clear-cache` | Invalidates `reviews`. Admin. |

## Git — smart-HTTP and statistics

| Route | Side effects |
|---|---|
| `GET /v3/datasets/<git_uuid>.git/info/refs` | `__git_create_repository`: `pygit2.init_repository(storage/<git_uuid>.git, bare)` + append `[http] receivepack = true` to the repo config (unconditional, before dispatch). On the upload-pack service path, the `gitDownload` log entry (see below). Unauthenticated. |
| `POST /v3/datasets/<git_uuid>.git/git-upload-pack` | `insert_log_entry(event_type="gitDownload")`; git http-backend read (no repo write). Unauthenticated. |
| `POST /v3/datasets/<git_uuid>.git/git-receive-pack` | git http-backend push → objects/refs written to `storage/<git_uuid>.git`. **Deviation:** the port requires a session token + `may_write` (legacy is unauthenticated); see deviations. |
| `PUT /v3/datasets/<id>.git/set-default-branch` | `set_head` + `references.compress()`; `update_dataset_git_uuid` when the dataset lacks a `git_uuid`. |
| `GET /v3/datasets/<id>.git/{branches,files}` | Incidental: HEAD-guess write (`set_head` + `compress`) when HEAD is unresolvable; `git_uuid` auto-assignment when absent. |
| `GET /v3/datasets/<git_uuid>.git/languages` | Cache store `git_languages` key `<git_uuid>_<target>`; possible HEAD-guess write. Warmed by publish. |
| `GET /v3/datasets/<git_uuid>.git/contributors` | Cache store `git_contributors` key `<git_uuid>_<target>`; possible HEAD-guess write. Warmed by publish. |

## Behaviours pinned by unit tests

- Collaborator PUT/DELETE call `update_collaborator`/`delete_collaborator`
  with the legacy positional signature (`dataset_uuid`, `collaborator_uuid`,
  the six boolean permissions / the two identifiers) — not keyword arguments
  the db layer does not accept.
- The collaborator listing calls `db.collaborators(dataset_uuid)` with no
  account filter, so it returns the whole list, not just the caller's row.
- `submit-for-review` resolves with `is_under_review=False`, so a second
  submit of an already-under-review dataset 404s and cannot create a duplicate
  review.
- `assign-reviewer`, `/reviews` and `/reviewers` check reviewer privileges by
  passing a **session token** to `may_review`/`may_review_institution` (not an
  account UUID); `/reviewers` includes `institutional_reviewer_accounts`.
- The `SUBMIT_DATASET` and `FILE_LIST` locks are a single process-wide `Locks`
  instance created at import, never re-instantiated per request (a fresh
  `Locks()` re-runs `__init__` and replaces the held lock objects).
- codemeta and ro-crates pass `git_url` to the formatters, so software records
  keep their repository URL.
- `datasets/search` passes `search_for` to `db.datasets` as the structured
  `{"operator", "search_for": [tokens], "scope"}` form legacy builds — not the
  raw string. `db.datasets` builds its full-text SPARQL filter from that shape;
  a bare string makes the filter a no-op, so every query matches everything
  (see "Argument-shape parity" below).

## Argument-shape parity (a silent-failure class)

The database interface (`db.*`, `SparqlInterface`) is shared and unchanged, so
the port must hand each `db` method arguments in the **exact shape** the legacy
handler did. This is easy to miss because a wrong *shape* (not a wrong value)
usually raises nothing — the SPARQL builder just produces a query that filters
differently, and the endpoint returns wrong data with a 200.

The one that shipped and was caught by the legacy `/search` page driving
`/v3/datasets/search`: the port passed `search_for` as a raw string where
legacy passed the tokenised `{operator, search_for: [tokens], scope}` dict, so
the full-text filter matched nothing and every search returned all datasets.

Guard against the whole class the same way: for any ported endpoint a legacy UI
page or its JavaScript calls (grep `src/djehuty/web/resources/static/js` for the
route), diff every argument the port passes to a shared `db.*` method against
what legacy passed — watching specifically for a value legacy *transforms* first
(tokenising, splitting a comma string to a list, int-casting, `array_value`,
wrapping in a dict, a default like `is_latest`). Fake-db unit tests will not
catch this; only the real query does, so the UI e2e suites are the safety net.

## Error-response shape parity

The legacy error helpers have fixed body shapes a client can depend on, so the
port reproduces them exactly (`wsgi.py` `error_*` methods):

- **403 is uniform.** `error_403` sends its descriptive text to the audit log and
  always returns `{"message": "Not allowed."}` to the client; the auth-failure
  path (`error_authorization_failed`) is the separate
  `{"message": "Invalid or unknown session token", "code": "InvalidSessionToken"}`.
  The port keeps `ForbiddenError`'s descriptive message for the log only and
  renders `{"message": "Not allowed."}`; `AuthorizationError` renders the token
  body.
- **A validation *list* is a bare array.** `error_400_list` serialises a list of
  `{field_name, message}` errors as a top-level JSON array (used by
  `submit-for-review`), while a single `error_400` keeps the
  `{message, code}` object. The port's `InvalidInputError` mirrors this: a list
  payload renders as a bare array, a string keeps the object — so a client
  iterating the array is not handed an object.
- **Unknown sub-resource on `GET /v3/datasets/<id>/authors/<author_uuid>` is 500.**
  Legacy indexes `authors[0]`; an unknown author raises `IndexError` that falls
  through to `error_500` (empty body). The missing *parent* dataset stays 404
  (see the error-status-normalisation deviation).

## Deferrals

- **Git-statistics cache warm (api-v2 side only).** The v3 publish path now
  warms the `git_languages`/`git_contributors` caches through
  `services.git.languages_summary`/`contributors` (the same cache prefixes and
  payloads legacy writes), closing the api-v2 deferral for software published
  via v3. The api-v2 publish port (`api/v2/account/articles/publishing.py`)
  still does not warm — it predates the shared git service. Remove this note
  once the v2 publish path calls the same `services.git` warm.
- The new stack sends e-mail through the same `EmailInterface` that ui.py
  configures for the legacy server (`config.email_interface`). Without that
  bootstrap, sends are skipped and logged — same as a legacy instance without
  SMTP settings.

## Method / auth ordering

The legacy handlers do not all check the HTTP method before authentication, and
that order is observable: an endpoint that checks auth first answers an
unauthenticated request to the *wrong* method with 403, where a framework that
routes by method first would answer 405. Two families exist in `wsgi.py`:

- **Method-first** — every handler built on `default_error_handling` /
  `default_authenticated_error_handling` (groups, statistics, explore, git REST
  endpoints, reviews, reviewers, redirect-from-ssi, and most others). These
  reject the method (405) before auth, so FastAPI's native routing matches them
  and there is nothing to reproduce.
- **Custom-ordered** — four handlers check auth or config *before* the method:
  `accounts_search`, `receive_from_ssi`, `dataset_collaborators`, and the
  `dataset`/`collection` references handlers. FastAPI would return 405 on a
  wrong method here where legacy returns 403 (or, for SSI, 404 when `ssi_psk`
  is unset). Where a checked-in AS-IS contract test pins the legacy status, the
  port reproduces it exactly (`accounts_search` and `receive_from_ssi` register
  the extra method on one `api_route` and enforce the legacy order inside).
  Where nothing — no client, no e2e test — depends on the legacy status
  (`collaborators`, `references` on an unauthenticated wrong method), the port
  keeps FastAPI's 405, which is the more correct answer; see the deviations
  below.

## Conscious deviations from legacy (AS-IS exceptions)

These are intentional differences, safe because they do not change a
client-visible success path or a persisted side effect:

- **Git smart-HTTP is unauthenticated, matching legacy.** `git-receive-pack`
  and `info/refs?service=git-receive-pack` accept the push with no token — a
  draft dataset carrying the `git_uuid` must exist, nothing more (an earlier
  port hardened this to require a token + `may_write`, which broke `git push`
  for real clients and the e2e git suite; reverted). `git-upload-pack` is
  likewise open and records the `gitDownload` log entry. Only the *REST* git
  endpoints (`.git/branches`, `.git/files`, `.git/set-default-branch`) require
  an authenticated owner/collaborator, as legacy does.
- **Wrong-method status on the custom-ordered handlers.** For `collaborators`
  and the `references` handlers, an unauthenticated request with an unsupported
  method gets 405 from the port versus 403 from legacy, and an authenticated
  unsupported method gets 405 versus legacy's trailing 500. No client or e2e
  test depends on the legacy quirk, and 405 is the more accurate answer.
- **`dataset`/`collection` references and dataset `tags` GET is anonymous-capable.**
  Legacy requires a token for every method on these; the port lets an
  unauthenticated GET resolve a *published* item. Reads only; no write path or
  persisted side effect differs.
- **SSI redirect cookie flags** match legacy exactly (no `httponly`, no
  `samesite`); the hardened flags an earlier port added were reverted.
- **Error-status normalisation.** Several handlers return 400/404 where legacy
  returned an uncaught-exception 500 (e.g. deleting a non-existent reference,
  malformed paging). The success paths and all persisted side effects are
  identical; only the error status differs, and the AS-IS e2e suite records
  these as warnings rather than failures.
- **Thumbnail / image detection** uses the same `services.imaging` extraction as
  legacy; where the port filters image files by extension rather than the DB
  `is_image` flag, the persisted set is unchanged.
