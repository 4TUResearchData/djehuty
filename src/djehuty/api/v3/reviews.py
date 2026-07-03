"""Review endpoints for the v3 API."""

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse

from djehuty.api.dependencies import get_db, get_token, require_auth
from djehuty.api.exceptions import ForbiddenError
from djehuty.api.models.common import ErrorResponse
from djehuty.api.v3._shared import _ok
from djehuty.web import formatter

router = APIRouter(tags=["V3 / Reviews"])

_REVIEW_EXAMPLE = {
    "uuid": "669c6802-75eb-44e2-a6f8-ea7a5a8d0f34",
    "container_uuid": "b07402ed-978b-439a-abb1-7f27c69d174e",
    "dataset_title": "Coastal water temperature measurements",
    "dataset_uuid": "8ffc3b0f-ec65-4dab-bae1-49ff984c2995",
    "dataset_version": 1,
    "group_name": "Delft University of Technology",
    "has_published_version": 1,
    "last_seen_by_reviewer": None,
    "modified_date": "2026-07-03T09:33:38",
    "published_date": "2026-07-03T09:33:40",
    "request_date": "2026-07-03T09:33:38",
    "reviewer_email": "dev@djehuty.com",
    "reviewer_first_name": "Ada",
    "reviewer_last_name": "Lovelace",
    "status": "approved",
    "submitter_email": "dev@djehuty.com",
    "submitter_first_name": "Ada",
    "submitter_last_name": "Lovelace",
}

_REVIEWER_EXAMPLE = {
    "id": None,
    "uuid": "84cae99f-a691-4af2-9d21-f5c0817c26df",
    "first_name": "Dev",
    "last_name": "User",
    "full_name": None,
    "is_active": True,
    "is_public": False,
    "job_title": None,
    "orcid_id": "",
}


def _reviewer_privileges(db, token):
    """Raise ForbiddenError unless TOKEN grants reviewer privileges."""
    may_review_all = db.may_review(token)
    may_review_institution = db.may_review_institution(token)
    if not may_review_all and not may_review_institution:
        raise ForbiddenError("Reviewer permissions required.")
    return may_review_all, may_review_institution


@router.get(
    "/reviews",
    summary="List reviews",
    responses={200: _ok("Review records", [_REVIEW_EXAMPLE]), 403: {"model": ErrorResponse}},
)
def list_reviews(token=Depends(get_token), db=Depends(get_db)):
    _, may_review_institution = _reviewer_privileges(db, token)

    group_id = None
    if may_review_institution:
        account = db.account_by_session_token(token)
        group_id = account.get("group_id") if account else None

    reviews = db.reviews(
        limit=10000, group_id=group_id, order="request_date", order_direction="desc"
    )
    return JSONResponse(content=[formatter.format_review_record(r) for r in reviews])


@router.get(
    "/reviewers",
    summary="List reviewers",
    responses={200: _ok("Reviewer accounts", [_REVIEWER_EXAMPLE]), 403: {"model": ErrorResponse}},
)
def list_reviewers(token=Depends(get_token), db=Depends(get_db)):
    _reviewer_privileges(db, token)
    reviewers = db.reviewer_accounts() + db.institutional_reviewer_accounts()
    return JSONResponse(content=[formatter.format_account_record(r) for r in reviewers])


@router.put(
    "/datasets/{dataset_uuid}/assign-reviewer/{reviewer_uuid}",
    summary="Assign reviewer",
    responses={204: {"description": "Reviewer assigned"}, 403: {"model": ErrorResponse}},
)
def assign_reviewer(
    dataset_uuid: str,
    reviewer_uuid: str,
    request: Request,
    _account=Depends(require_auth),
    db=Depends(get_db),
):
    from djehuty.web import validator

    if not validator.is_valid_uuid(reviewer_uuid):
        raise ForbiddenError("Invalid reviewer UUID.")

    # Legacy checks reviewer privileges on the cookie session specifically.
    cookie_token = request.cookies.get("djehuty_session")
    _reviewer_privileges(db, cookie_token)

    reviewer = db.account_by_uuid(reviewer_uuid)
    dataset = None
    try:
        dataset = db.datasets(dataset_uuid=dataset_uuid, is_published=False, is_under_review=True)[
            0
        ]
    except (IndexError, TypeError):
        pass

    if dataset is None or reviewer is None:
        raise ForbiddenError("Dataset not found or not under review.")

    if db.update_review(
        dataset["review_uri"],
        author_account_uuid=dataset["account_uuid"],
        assigned_to=reviewer["uuid"],
        status="assigned",
    ):
        return Response(status_code=204)
    return Response(status_code=500)
