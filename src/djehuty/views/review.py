"""Reviewer UI routes (``/review/*``) on the new FastAPI stack.

AS-IS port of the legacy ``ui_review_*`` handlers: the read-only overview, the
impersonation "go to" redirects, assign/unassign, and the post-publish pages.
Auth, status codes, redirects and cookies match legacy so the ``review`` route
group flips new<->legacy invisibly. These routes render HTML; they are kept out
of the OpenAPI schema.
"""

import logging

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse

from djehuty.api.dependencies import get_db, get_token
from djehuty.utils.convenience import parses_to_int, value_or_none
from djehuty.utils.rdf import uri_to_uuid
from djehuty.views.rendering import (
    ViewError,
    accepts_html,
    error_406,
    error_500,
    html_authorization_failed,
    html_error,
    render_page,
)
from djehuty.web import validator
from djehuty.web.config import config

router = APIRouter(tags=["Review"])
logger = logging.getLogger(__name__)

# Every scalar field the author edits, shown read-only so the reviewer can
# comment on any of them (including empty ones). Each entry is
# (comment token = submit-validator name, label, record key for the displayed
# value -- which differs from the token for id-backed fields like group/licence).
_REVIEW_SCALAR_FIELDS = (
    ("title", "Title", "title"),
    ("description", "Description", "description"),
    ("defined_type", "Item type", "defined_type_name"),
    ("publisher", "Publisher", "publisher"),
    ("time_coverage", "Time coverage", "time_coverage"),
    ("language", "Language", "language"),
    ("license_id", "Licence", "license_name"),
    ("license_remarks", "Licence remarks", "license_remarks"),
    ("contributors", "Contributors", "contributors"),
    ("geolocation", "Geolocation", "geolocation"),
    ("longitude", "Longitude", "longitude"),
    ("latitude", "Latitude", "latitude"),
    ("format", "Format", "format"),
    ("data_link", "Data link", "data_link"),
    ("derived_from", "Derived from", "derived_from"),
    ("same_as", "Same as", "same_as"),
    ("organizations", "Organizations", "organizations"),
    ("resource_title", "Related resource title", "resource_title"),
    ("resource_doi", "Related resource DOI", "resource_doi"),
    ("group_id", "Group", "group_name"),
    ("categories", "Categories", "categories"),
    ("metadata_reason", "Metadata-only reason", "metadata_reason"),
    ("embargo_until_date", "Embargo until", "embargo_until_date"),
    ("embargo_type", "Embargo type", "embargo_type"),
    ("embargo_title", "Embargo title", "embargo_title"),
    ("embargo_reason", "Embargo reason", "embargo_reason"),
)


def _review_dataset_or_none(db, dataset_id):
    """Resolve a draft dataset that is under review, or None."""
    try:
        if parses_to_int(dataset_id):
            return db.datasets(
                dataset_id=int(dataset_id), is_published=False, is_under_review=True
            )[0]
        if validator.is_valid_uuid(dataset_id):
            return db.datasets(container_uuid=dataset_id, is_published=False, is_under_review=True)[
                0
            ]
    except (IndexError, TypeError):
        return None
    return None


def _review_fields(dataset):
    """All scalar fields to show read-only, with their comment tokens.

    Empty fields are included (value ``""``) so the reviewer can comment on a
    field the author left blank.
    """
    fields = []
    for token, label, value_key in _REVIEW_SCALAR_FIELDS:
        value = dataset.get(value_key)
        fields.append(
            {"token": token, "label": label, "value": "" if value is None else str(value)}
        )
    return fields


def _safe_list(fetch):
    """Run an entity query; never let it break the page (returns [] on error)."""
    try:
        return fetch() or []
    except Exception as error:  # noqa: BLE001 - entity queries must not break review
        logger.warning("Review page: entity query failed: %s", error)
        return []


def _details(record, specs):
    """Read-only (label, value) detail pairs for an entity, skipping empties."""
    out = []
    for label, key in specs:
        value = value_or_none(record, key)
        if value not in (None, ""):
            out.append({"label": label, "value": str(value)})
    return out


def _entity_section(target_type, label, records, label_fn, detail_specs=(), key_keys=("uuid",)):
    """Build one entity section: per-item anchors (key_keys) or section-level.

    Each item carries a primary label plus read-only ``details`` (e.g. an
    author's e-mail/ORCID) the reviewer can see but not edit.
    """
    items = []
    for record in records:
        key = next((value_or_none(record, k) for k in key_keys if value_or_none(record, k)), None)
        items.append(
            {
                "key": key,
                "label": label_fn(record) or "(unnamed)",
                "details": _details(record, detail_specs),
            }
        )
    return {
        "target_type": target_type,
        "label": label,
        "section": not key_keys,  # references/tags have no stable per-item id
        "items": items,
    }


def _author_label(record):
    full = value_or_none(record, "full_name")
    if full:
        return full
    parts = [value_or_none(record, "first_name"), value_or_none(record, "last_name")]
    return " ".join(p for p in parts if p)


def _review_entities(db, dataset):
    """Entity/section fields (authors, categories, funding, files, …) to review."""
    uri = dataset["uri"]
    return [
        _entity_section(
            "author",
            "Authors",
            _safe_list(
                lambda: db.authors(item_uri=uri, item_type="dataset", is_published=False, limit=100)
            ),
            _author_label,
            detail_specs=(
                ("E-mail", "email"),
                ("ORCID", "orcid_id"),
                ("Job title", "job_title"),
            ),
        ),
        _entity_section(
            "category",
            "Categories",
            _safe_list(lambda: db.categories(item_uri=uri, is_published=False, limit=100)),
            lambda r: value_or_none(r, "title"),
            detail_specs=(("Code", "source_id"), ("Classification", "classification")),
        ),
        _entity_section(
            "funding",
            "Funding",
            _safe_list(
                lambda: db.fundings(
                    item_uri=uri, item_type="dataset", is_published=False, limit=100
                )
            ),
            lambda r: value_or_none(r, "title") or value_or_none(r, "funder_name"),
            detail_specs=(
                ("Funder", "funder_name"),
                ("Grant code", "grant_code"),
                ("URL", "url"),
            ),
        ),
        _entity_section(
            "file",
            "Files",
            _safe_list(lambda: db.dataset_files(dataset_uri=uri, limit=100)),
            lambda r: value_or_none(r, "name"),
            detail_specs=(
                ("Size (bytes)", "size"),
                ("MD5", "computed_md5"),
                ("MD5 (supplied)", "supplied_md5"),
                ("Download URL", "download_url"),
            ),
            key_keys=("uuid", "file_uuid"),
        ),
        _entity_section(
            "collaborator",
            "Collaborators",
            _safe_list(lambda: db.collaborators(dataset["uuid"])),
            lambda r: (
                value_or_none(r, "name")
                or value_or_none(r, "full_name")
                or value_or_none(r, "email")
            ),
            detail_specs=(
                ("E-mail", "email"),
                ("Metadata", "metadata_edit"),
                ("Data", "data_edit"),
            ),
        ),
        _entity_section(
            "references",
            "References",
            _safe_list(lambda: db.references(item_uri=uri, limit=1000)),
            lambda r: value_or_none(r, "url"),
            key_keys=(),
        ),
        _entity_section(
            "tags",
            "Keywords",
            _safe_list(lambda: db.tags(item_uri=uri, limit=1000)),
            lambda r: value_or_none(r, "tag"),
            key_keys=(),
        ),
    ]


def require_reviewer(request: Request, db=Depends(get_db)) -> str | None:
    """Port of legacy ``__reviewer_account_uuid``: requires ``may_review``.

    Resolves the caller by cookie-then-header token; a non-reviewer (or
    unauthenticated) caller gets a 403, matching legacy's error precedence.
    Returns the caller's own account UUID (used as the assignee).
    """
    token = get_token(request)
    account = db.account_by_session_token(token) if token else None
    if not db.may_review(token):
        raise ViewError(html_error(request, db, 403))
    return value_or_none(account, "uuid")


def require_impersonator(request: Request, db=Depends(get_db)) -> tuple:
    """Port of legacy ``default_authenticated_error_handling(..., may_impersonate)``.

    Method filtering (GET/HEAD) is handled by the router; this reproduces the
    remaining steps in order: content-type (406), authentication (403), then the
    ``may_impersonate`` privilege (403). Returns ``(account_uuid, caller_token)``.
    """
    if not accepts_html(request):
        raise ViewError(error_406("text/html"))
    token = get_token(request)
    account = db.account_by_session_token(token) if token else None
    if account is None:
        raise ViewError(html_authorization_failed(request, db))
    if not db.may_impersonate(token):
        raise ViewError(html_error(request, db, 403))
    return value_or_none(account, "uuid"), token


def _dataset_by_id_or_uri(db, identifier, is_published=True, is_latest=False):
    """Port of legacy ``__dataset_by_id_or_uri`` (numeric id or container UUID)."""
    parameters = {
        "is_published": is_published,
        "is_latest": is_latest,
        "is_under_review": None,
        "version": None,
        "account_uuid": None,
        "use_cache": True,
        "limit": 1,
    }
    try:
        if parses_to_int(identifier):
            return db.datasets(dataset_id=int(identifier), **parameters)[0]
        if validator.is_valid_uuid(identifier):
            return db.datasets(container_uuid=identifier, **parameters)[0]
        return None
    except IndexError:
        return None


def _physical_sample_by_id_or_uri(db, identifier, is_published=False, is_latest=False):
    """Port of legacy ``__physical_sample_by_id_or_uri`` (container UUID only)."""
    parameters = {
        "is_published": is_published,
        "is_latest": is_latest,
        "is_under_review": None,
        "account_uuid": None,
    }
    try:
        sample = None
        if validator.is_valid_uuid(identifier):
            sample = db.physical_samples(container_uuid=identifier, **parameters)[0]
        if sample is not None:
            sample["uri"] = f"physical-sample:{sample['sample_uuid']}"
            sample["uuid"] = sample["sample_uuid"]
        return sample
    except IndexError:
        return None


def _set_review_cookies(response: Response, caller_token: str) -> None:
    """Set the impersonator + redirect-back cookies (legacy attributes)."""
    response.set_cookie(
        key="impersonator_djehuty_session",
        value=caller_token,
        secure=config.in_production,
        httponly=False,
        samesite=None,
    )
    response.set_cookie(
        key="redirect_to",
        value="/review/overview",
        secure=config.in_production,
        httponly=False,
        samesite=None,
    )


def _assign_or_unassign(request: Request, db, dataset_id: str, status: str, account_uuid):
    """Shared implementation for assign-to-me and unassign."""
    if not validator.is_valid_uuid(dataset_id):
        return html_error(request, db, 404)

    dataset = None
    try:
        dataset = db.datasets(dataset_uuid=dataset_id, is_published=False, is_under_review=True)[0]
    except (IndexError, TypeError):
        pass

    if dataset is None:
        return html_error(request, db, 403)

    if status == "unassigned":
        account_uuid = None

    if db.update_review(
        dataset["review_uri"],
        author_account_uuid=dataset["account_uuid"],
        assigned_to=account_uuid,
        status=status,
    ):
        return RedirectResponse("/review/overview", status_code=302)

    return error_500()


@router.api_route("/review/overview", methods=["GET", "HEAD"], include_in_schema=False)
def review_overview(request: Request, db=Depends(get_db)):
    """Implements /review/overview."""
    if not accepts_html(request):
        return error_406("text/html")

    token = request.cookies.get("djehuty_session")
    may_review_all = db.may_review(token)
    may_review_institution = db.may_review_institution(token)
    if not may_review_all and not may_review_institution:
        return html_error(request, db, 403)

    group_id = None
    if may_review_institution:
        account = db.account_by_session_token(token)
        group_id = value_or_none(account, "group_id")

    reviewers = db.reviewer_accounts()
    reviewers += db.institutional_reviewer_accounts(None)
    reviews = db.reviews(
        limit=10000, group_id=group_id, order="request_date", order_direction="desc"
    )
    return render_page(
        request,
        db,
        "review/overview.html",
        reviewers=reviewers,
        reviews=reviews,
        enable_dataset_review=config.enable_dataset_review,
    )


@router.api_route(
    "/review/goto-dataset/{dataset_id}", methods=["GET", "HEAD"], include_in_schema=False
)
def review_goto_dataset(
    dataset_id: str,
    request: Request,
    db=Depends(get_db),
    caller=Depends(require_impersonator),
):
    """Implements /review/goto-dataset/<id>."""
    account_uuid, caller_token = caller

    if not validator.is_valid_uuid(dataset_id):
        return html_error(request, db, 404)

    dataset = None
    try:
        dataset = db.datasets(dataset_uuid=dataset_id, is_published=False, is_under_review=True)[0]
    except (IndexError, TypeError):
        pass

    if dataset is None:
        return html_error(request, db, 403)

    try:
        review = db.reviews(dataset_uri=dataset["uri"])[0]
        if account_uuid == uri_to_uuid(review["assigned_to"]):
            db.dataset_update_seen_by_reviewer(dataset["uuid"])
    except (KeyError, TypeError, IndexError):
        pass

    response = RedirectResponse(f"/my/datasets/{dataset['container_uuid']}/edit", status_code=302)
    _set_review_cookies(response, caller_token)
    new_token, _, _ = db.insert_session(dataset["account_uuid"], name="Reviewer", override_mfa=True)
    response.set_cookie(
        key="djehuty_session",
        value=new_token,
        secure=config.in_production,
        httponly=False,
        samesite=None,
    )
    return response


@router.api_route(
    "/review/goto-physical-sample/{container_uuid}",
    methods=["GET", "HEAD"],
    include_in_schema=False,
)
def review_goto_physical_sample(
    container_uuid: str,
    request: Request,
    db=Depends(get_db),
    caller=Depends(require_impersonator),
):
    """Implements /review/goto-physical-sample/<id>."""
    _account_uuid, caller_token = caller

    if not validator.is_valid_uuid(container_uuid):
        return html_error(request, db, 404)

    sample = None
    try:
        sample = db.physical_samples(
            container_uuid=container_uuid,
            is_published=False,
            is_latest=False,
            is_under_review=True,
        )[0]
    except (IndexError, TypeError):
        pass

    if sample is None:
        return html_error(request, db, 403)

    response = RedirectResponse(
        f"/my/physical-samples/{sample['container_uuid']}/edit", status_code=302
    )
    _set_review_cookies(response, caller_token)
    new_token, _, _ = db.insert_session(sample["account_uuid"], name="Reviewer", override_mfa=True)
    response.set_cookie(
        key="djehuty_session",
        value=new_token,
        secure=config.in_production,
        httponly=False,
        samesite=None,
    )
    return response


@router.api_route(
    "/review/assign-to-me/{dataset_id}", methods=["GET", "HEAD"], include_in_schema=False
)
def review_assign_to_me(
    dataset_id: str,
    request: Request,
    db=Depends(get_db),
    account_uuid=Depends(require_reviewer),
):
    """Implements /review/assign-to-me/<id>."""
    return _assign_or_unassign(request, db, dataset_id, "assigned", account_uuid)


@router.api_route("/review/unassign/{dataset_id}", methods=["GET", "HEAD"], include_in_schema=False)
def review_unassign(
    dataset_id: str,
    request: Request,
    db=Depends(get_db),
    account_uuid=Depends(require_reviewer),
):
    """Implements /review/unassign/<id>."""
    return _assign_or_unassign(request, db, dataset_id, "unassigned", account_uuid)


@router.api_route(
    "/review/published/{dataset_id}", methods=["GET", "HEAD"], include_in_schema=False
)
def review_published(
    dataset_id: str,
    request: Request,
    db=Depends(get_db),
    _reviewer=Depends(require_reviewer),
):
    """Implements /review/published/<id>."""
    dataset = _dataset_by_id_or_uri(db, dataset_id, is_published=True, is_latest=True)
    if dataset is None:
        return html_error(request, db, 403)
    return render_page(
        request, db, "review/published.html", container_uuid=dataset["container_uuid"]
    )


@router.api_route(
    "/review/physical-sample/published/{container_uuid}",
    methods=["GET", "HEAD"],
    include_in_schema=False,
)
def review_physical_sample_published(
    container_uuid: str,
    request: Request,
    db=Depends(get_db),
    _reviewer=Depends(require_reviewer),
):
    """Implements /review/physical-sample/published/<id>."""
    sample = _physical_sample_by_id_or_uri(db, container_uuid, is_published=True, is_latest=True)
    if sample is None:
        return html_error(request, db, 403)
    return render_page(
        request,
        db,
        "review/published.html",
        container_uuid=sample["container_uuid"],
        item_type="physical-sample",
    )


@router.api_route("/review/dataset/{dataset_id}", methods=["GET", "HEAD"], include_in_schema=False)
def review_dataset(
    dataset_id: str,
    request: Request,
    db=Depends(get_db),
    account_uuid=Depends(require_reviewer),
):
    """Implements /review/dataset/<id> -- the read-only field-level review page.

    Renders the deposit read-only with per-field comment anchors; the
    conversation itself is loaded by review-reviewer.js from the /v3 API. Off
    unless the feature is enabled.
    """
    if not config.enable_dataset_review:
        return html_error(request, db, 404)

    dataset = _review_dataset_or_none(db, dataset_id)
    if dataset is None:
        return html_error(request, db, 403)

    # Stamp last-seen when the assigned reviewer opens the page so the overview's
    # "modified after seen" badge is accurate (and invalidate that cache, which
    # dataset_update_seen_by_reviewer does not do itself).
    try:
        review = db.reviews(dataset_uri=dataset["uri"])[0]
        if account_uuid == uri_to_uuid(review["assigned_to"]):
            db.dataset_update_seen_by_reviewer(dataset["uuid"])
            db.cache.invalidate_by_prefix("reviews")
    except (KeyError, TypeError, IndexError):
        pass

    return render_page(
        request,
        db,
        "review/dataset.html",
        container_uuid=dataset["container_uuid"],
        dataset_title=dataset.get("title"),
        author_uuid=dataset["account_uuid"],
        review_fields=_review_fields(dataset),
        review_entities=_review_entities(db, dataset),
    )
