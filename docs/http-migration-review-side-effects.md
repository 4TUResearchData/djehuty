# review side-effect catalog

The side effects — writes, cache invalidations, e-mails, external-service
calls, cookies set, and redirects — that each `/review/*` route must reproduce
from its legacy handler. This is scaffolding for the HTTP migration (see
`http-migration.md`); the new stack (`djehuty.views.review`) implements every
row. Delete this file when the legacy `ui_review_*` handlers are removed.

The method is described in `http-migration.md` under "Rules of the road".
Cache invalidations that live *inside* a shared `database.py` method travel with
the db call automatically (the new stack holds the same `SparqlInterface`), so
they are not re-listed per route — only side effects a handler performs itself
are noted. Unlike the JSON API groups, these routes render HTML (via
`djehuty.views.rendering`) and set cookies / issue 302 redirects.

All seven routes are GET (declared `GET`/`HEAD` on the new stack). The reviewer
group runs on the new stack when `web-service.groups.review = new` (the default).

## Read-only routes (no writes, no cache invalidation, no e-mail)

| Route | Legacy handler | Side effects |
|---|---|---|
| `GET /review/overview` | `ui_review_overview` | None. Reads `reviewer_accounts`, `institutional_reviewer_accounts(None)`, `reviews(...)`; renders `review/overview.html`. The table itself is populated client-side by `review-overview.js` calling `/v3/reviews`. |
| `GET /review/published/<id>` | `ui_review_published` | None. Resolves the dataset (`__dataset_by_id_or_uri`, published/latest); renders `review/published.html`. |
| `GET /review/physical-sample/published/<uuid>` | `ui_review_physical_sample_published` | None. Resolves the sample (`__physical_sample_by_id_or_uri`, published/latest); renders `review/published.html` with `item_type="physical-sample"`. |

## Impersonation "go to" routes

| Route | Legacy handler | Side effects |
|---|---|---|
| `GET /review/goto-dataset/<id>` | `ui_review_impersonate_to_dataset` | **Conditional write:** `dataset_update_seen_by_reviewer(dataset_uuid)` — only when the caller is the assigned reviewer (`account_uuid == uri_to_uuid(review.assigned_to)`). **`insert_session(dataset.account_uuid, name="Reviewer", override_mfa=True)`** (creates the impersonation session). **302** to `/my/datasets/<container>/edit`. **Three cookies:** `impersonator_djehuty_session` = caller's token, `redirect_to` = `/review/overview`, `djehuty_session` = the new session token. All cookies: `secure=in_production`, no httponly, no SameSite, path `/` (legacy Werkzeug defaults). |
| `GET /review/goto-physical-sample/<uuid>` | `ui_review_impersonate_to_physical_sample` | Same as above minus the seen-by-reviewer step: `insert_session(sample.account_uuid, name="Reviewer", override_mfa=True)`; **302** to `/my/physical-samples/<container>/edit`; the same three cookies. |

## Assignment routes

| Route | Legacy handler | Side effects |
|---|---|---|
| `GET /review/assign-to-me/<id>` | `ui_review_assign_to_me` → `__review_assign_or_unassign(status="assigned")` | `update_review(review_uri, author_account_uuid=dataset.account_uuid, assigned_to=<caller>, status="assigned")` (invalidates `datasets_<author_account>` and `reviews` inside the db call). **302** to `/review/overview`; `error_500` (empty body) if the update returns falsy. |
| `GET /review/unassign/<id>` | `ui_review_unassign` → `__review_assign_or_unassign(status="unassigned")` | Same, with `assigned_to=None, status="unassigned"`. |

## Notes on parity

- **Auth** is cookie-only for `overview` (legacy `token_from_cookie`) and
  cookie-then-header for the others (legacy `__reviewer_account_uuid`); neither
  uses the impersonator-first precedence of `dependencies.resolve_reviewer_context`,
  so that dependency is intentionally **not** used here.
- **Error ordering (AS-IS):** `overview` and the two `goto-*` routes negotiate
  content type first (`406` when the client won't take HTML); `goto-*` and
  assign/unassign validate the UUID (`404`) before loading (`403`); the
  `published` routes have no `404` step (unknown id → `403`). Reviewer-privilege
  `403` is raised by the auth dependency before any of the above.
- **No cache prefix is invalidated by any handler directly**; the only cache
  effects are those inside `update_review`.
- **No e-mail is sent by any `/review/*` route.** (The request-changes /
  sent-back notifications belong to the later field-level-review feature, not to
  this migration.)
