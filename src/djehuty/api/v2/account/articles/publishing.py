"""Authenticated /v2/account/articles publishing endpoints."""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from djehuty.api.dependencies import get_db, require_auth
from djehuty.api.exceptions import ForbiddenError, InvalidInputError
from djehuty.api.models.common import ErrorResponse
from djehuty.api.v2.account.articles._shared import _ok, _resolve_private_dataset
from djehuty.web.config import config

router = APIRouter(prefix="/account", tags=["V2 / Account / Articles / Publishing"])


@router.post(
    "/articles/{dataset_id}/reserve_doi",
    summary="Reserve a DOI",
    responses={200: _ok("Reserved DOI", {"doi": "10.5074/d7b3daa5-45e2-47b0-9910-0f7fa6a995b1"})},
)
def reserve_doi(dataset_id: str, account=Depends(require_auth), db=Depends(get_db)):
    dataset = _resolve_private_dataset(db, dataset_id, account["uuid"])
    doi = db.reserve_doi(dataset["uri"], account["uuid"], item_type="dataset")
    if doi is None:
        raise InvalidInputError("Failed to reserve DOI.", "ReserveFailed")
    return JSONResponse(content={"doi": doi})


@router.post(
    "/articles/{dataset_id}/publish",
    summary="Publish an article",
    description=(
        "Publish a draft article. Requires reviewer permissions on the "
        "calling account. In production this also reserves DataCite DOIs "
        "for the container and the new version (the DOI flow is gated by "
        "``config.in_production`` and skipped in dev/preproduction)."
    ),
    responses={
        201: _ok(
            "Article published",
            {"location": "https://data.4tu.nl/review/published/9ce6daa5-45e2-47b0-9910-3976"},
        ),
        403: {"model": ErrorResponse, "description": "Reviewer permissions required"},
        500: {"model": ErrorResponse, "description": "Publication backend error"},
    },
)
def publish_article(dataset_id: str, account=Depends(require_auth), db=Depends(get_db)):
    # The /v2/account/articles/<id>/publish path delegates to the v3 dataset
    # publish handler in the legacy app — same business logic for both URLs.
    if not (db.may_review(account.get("uuid")) or db.may_review_institution(account.get("uuid"))):
        raise ForbiddenError("Reviewer permissions required.")

    dataset = _resolve_private_dataset(db, dataset_id, account["uuid"])
    container_uuid = dataset["container_uuid"]

    # For institutional reviewers, the reviewer's group must match the
    # dataset's group.
    if db.may_review_institution(account.get("uuid")):
        reviewer_group = account.get("group_id", "reviewer-group")
        dataset_group = dataset.get("group_id", "dataset-group")
        if reviewer_group != dataset_group:
            raise ForbiddenError("Reviewer group mismatch.")

    # Best-effort review-status update — legacy logs an error on failure
    # but does not block publication. We mirror that.
    review_uri = dataset.get("review_uri")
    if review_uri:
        db.update_review(
            review_uri,
            author_account_uuid=dataset["account_uuid"],
            assigned_to=account.get("uuid"),
            status="assigned",
        )

    # DOI reservation is production-only. The DataCite calls require helpers
    # that still live on the legacy server (``__reserve_and_save_doi`` /
    # ``__update_item_doi``). For dev/preproduction this block is skipped.
    if config.in_production and not config.in_preproduction:
        # TODO: extract DataCite DOI helpers into a shared module so the
        # production-only DOI reservation can run from here too. Until then,
        # production deployments must keep ``api-service = legacy`` for the
        # publish endpoint.
        raise InvalidInputError(
            "Publishing via the FastAPI implementation is not yet wired up "
            "for production DOI reservation.",
            "PublishUnavailableInProd",
        )

    if not db.publish_dataset(container_uuid, account["uuid"]):
        raise InvalidInputError("Failed to publish dataset.", "PublishFailed")

    return JSONResponse(
        content={"location": f"{config.base_url}/published/{dataset_id}"},
        status_code=201,
    )
