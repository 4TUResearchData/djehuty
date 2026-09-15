"""Authenticated /v2/account/articles publishing endpoints."""

import logging

from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse

from djehuty.api.dependencies import (
    get_db,
    get_email,
    get_impersonator_token,
    get_token,
    require_auth,
)
from djehuty.api.exceptions import ForbiddenError
from djehuty.api.models.common import ErrorResponse
from djehuty.api.services.article_service import ArticleService
from djehuty.api.v2.account.articles._shared import _ok
from djehuty.services import datacite, notifications
from djehuty.utils.convenience import value_or, value_or_none
from djehuty.web.config import config

router = APIRouter(prefix="/account", tags=["V2 / Account / Articles / Publishing"])
_log = logging.getLogger(__name__)


@router.post(
    "/articles/{dataset_id}/reserve_doi",
    summary="Reserve a DOI",
    responses={200: _ok("Reserved DOI", {"doi": "10.5074/d7b3daa5-45e2-47b0-9910-0f7fa6a995b1"})},
)
def reserve_doi(dataset_id: str, account=Depends(require_auth), db=Depends(get_db)):
    dataset = ArticleService(db)._resolve_dataset(
        dataset_id, account_uuid=account["uuid"], is_published=False
    )
    if dataset is None:
        raise ForbiddenError()

    reserved_doi = datacite.reserve_and_save_doi(db, account["uuid"], dataset)
    if reserved_doi:
        return JSONResponse(content={"doi": reserved_doi})
    return Response(status_code=500)


@router.post(
    "/articles/{dataset_id}/publish",
    summary="Publish an article",
    description=(
        "Publish a draft article. Requires reviewer permissions (via the "
        "review-impersonation cookie or the calling account's token). In "
        "production this reserves the container and version DOIs at DataCite "
        "and pushes their metadata; the DOI flow is skipped in "
        "dev/preproduction. Sends the approval e-mail to the owner and a "
        "notification to the reviewers."
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
def publish_article(
    dataset_id: str,
    account=Depends(require_auth),
    db=Depends(get_db),
    email=Depends(get_email),
    impersonator_token: str | None = Depends(get_impersonator_token),
    token: str | None = Depends(get_token),
):
    reviewer_token = impersonator_token
    may_review_all = db.may_review(reviewer_token)
    may_review_institution = db.may_review_institution(reviewer_token)
    if not may_review_all and not may_review_institution:
        may_review_all = db.may_review(token)
        may_review_institution = db.may_review_institution(token)
        if not may_review_all and not may_review_institution:
            raise ForbiddenError()

    dataset = ArticleService(db)._resolve_dataset(
        dataset_id, account_uuid=account["uuid"], is_published=False
    )
    if dataset is None:
        raise ForbiddenError()

    reviewer_account = db.account_by_session_token(reviewer_token)
    if may_review_institution:
        if value_or(dataset, "group_id", "A") != value_or(reviewer_account, "group_id", "not-A"):
            raise ForbiddenError()

    if not db.update_review(
        dataset["review_uri"],
        author_account_uuid=dataset["account_uuid"],
        assigned_to=reviewer_account["uuid"],
        status="assigned",
    ):
        _log.error("Unable to assign reviewer before publishing for %s.", dataset_id)

    container_uuid = dataset["container_uuid"]
    container = db.container(container_uuid)
    new_version = value_or(container, "latest_published_version_number", 0) + 1
    if config.in_production and not config.in_preproduction:
        for version in (None, new_version):
            reserved_doi = datacite.reserve_and_save_doi(
                db, account["uuid"], dataset, version=version
            )
            if not reserved_doi:
                _log.error("Reserving DOI for %s failed.", container_uuid)
                return Response(status_code=500)

            if not datacite.update_item_doi(
                db, container_uuid, item_type="dataset", version=version
            ):
                _log.error(
                    "Updating DOI %s for publication of %s failed.",
                    reserved_doi,
                    container_uuid,
                )
                return Response(status_code=500)

    if db.publish_dataset(container_uuid, account["uuid"]):
        try:
            owner_account = db.account_by_uuid(dataset["account_uuid"])
            dataset = db.datasets(dataset_uuid=dataset["uuid"], use_cache=False)[0]

            subject = f"Approved: {dataset['title']}"
            parameters = {
                "base_url": config.base_url,
                "support_email": config.support_email_address,
                "title": dataset["title"],
                "container_uuid": dataset["container_uuid"],
                "versioned_doi": value_or_none(dataset, "doi"),
                "container_doi": dataset["container_doi"],
            }
            notifications.send_templated_email(
                db, email, [owner_account["email"]], subject, "dataset_approved", **parameters
            )
            notifications.send_email_to_reviewers(
                db,
                email,
                subject,
                "published_dataset_notification",
                dataset=dataset,
                account_email=owner_account["email"],
                **parameters,
            )
        except (TypeError, IndexError, KeyError) as error:
            _log.error("Unable to send approval e-mail for dataset %s: %s.", dataset["uuid"], error)

        return JSONResponse(
            status_code=201,
            content={"location": f"{config.base_url}/review/published/{dataset_id}"},
        )

    return Response(status_code=500)
