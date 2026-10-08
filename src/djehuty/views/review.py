"""Reviewer UI routes (``/review/*``) on the new FastAPI stack.

AS-IS port of the legacy ``ui_review_*`` handlers: the read-only overview, the
impersonation "go to" redirects, assign/unassign, and the post-publish pages.
Auth, status codes, redirects and cookies match legacy so the ``review`` route
group flips new<->legacy invisibly. These routes render HTML; they are kept out
of the OpenAPI schema.
"""

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
    return render_page(request, db, "review/overview.html", reviewers=reviewers, reviews=reviews)


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
