"""Physical sample review and publication endpoints for the v3 API."""

import logging
from datetime import date, datetime

from fastapi import APIRouter, Body, Depends, Response
from fastapi.responses import JSONResponse

from djehuty.api.dependencies import (
    get_db,
    get_impersonator_token,
    get_token,
    require_auth,
)
from djehuty.api.exceptions import ForbiddenError, InvalidInputError, NotFoundError
from djehuty.api.models.common import ErrorResponse
from djehuty.api.v3._shared import _ok
from djehuty.api.v3.physical_samples._shared import (
    PhysicalSampleId,
    _category_list_from_request_input,
    _resolve_physical_sample,
)
from djehuty.web.config import config
from djehuty.web.locks import Locks

router = APIRouter(tags=["V3 / Physical samples / Publishing"])
logger = logging.getLogger(__name__)

# One process-wide instance, as legacy creates at server init. Instantiating
# Locks() per request would re-run its __init__ and replace held locks.
_process_locks = Locks()


def _reviewer_context(db, impersonator_token, token):
    """Resolve the reviewer token, preferring the impersonator cookie and
    falling back to the caller's own token (the API path). Returns
    ``(reviewer_token, may_review_all, may_review_institution)`` or raises
    ``ForbiddenError``. Faithful to the legacy publish/decline dance.
    """
    reviewer_token = impersonator_token
    may_review_all = db.may_review(reviewer_token)
    may_review_institution = db.may_review_institution(reviewer_token)
    if not may_review_all and not may_review_institution:
        reviewer_token = token
        may_review_all = db.may_review(reviewer_token)
        may_review_institution = db.may_review_institution(reviewer_token)
        if not may_review_all and not may_review_institution:
            raise ForbiddenError("Reviewer permissions required.")
    return reviewer_token, may_review_all, may_review_institution


@router.put(
    "/physical-samples/{container_uuid}/submit-for-review",
    summary="Submit a physical sample for review",
    responses={204: {"description": "Submitted for review"}, 403: {"model": ErrorResponse}},
)
def submit_for_review(
    container_uuid: PhysicalSampleId,
    body: dict = Body(default={}),
    account=Depends(require_auth),
    token: str = Depends(get_token),
    db=Depends(get_db),
):
    from djehuty.utils.convenience import value_or_none
    from djehuty.web import validator
    from djehuty.web.locks import LockTypes

    if not db.is_depositor(token):
        raise ForbiddenError("Depositor permissions required.")
    if not validator.is_valid_uuid(container_uuid):
        raise NotFoundError()

    account_uuid = account["uuid"]
    _process_locks.lock(LockTypes.SUBMIT_PHYSICAL_SAMPLE)
    try:
        sample = _resolve_physical_sample(
            db, container_uuid, account_uuid=account_uuid, is_published=False, is_under_review=False
        )
        if sample is None:
            raise NotFoundError()

        record = body
        errors: list = []
        # The Deposit Agreement does not yet cover physical samples, so agreeing
        # to it is not required for now (to be replaced by the Terms of Service).
        agreed_to_deposit_agreement = validator.boolean_value(
            record, "agreed_to_deposit_agreement", False, False, errors
        )
        agreed_to_publish = validator.boolean_value(
            record, "agreed_to_publish", True, False, errors
        )
        if not agreed_to_publish:
            errors.append(
                {
                    "field_name": "agreed_to_publish",
                    "message": (
                        "The physical sample cannot be published without giving the "
                        "reviewer permission to do so."
                    ),
                }
            )

        creators = db.physical_sample_creators(container_uuid, account_uuid)
        if not creators:
            errors.append(
                {
                    "field_name": "authors",
                    "message": "The physical sample must have at least one creator.",
                }
            )

        tags = db.tags(item_uri=sample["uri"], account_uuid=account_uuid)
        if len(tags) < config.minimum_keywords_count:
            keyword_noun = "keyword" if config.minimum_keywords_count == 1 else "keywords"
            errors.append(
                {
                    "field_name": "tag",
                    "message": (
                        f"The physical sample must have at least "
                        f"{config.minimum_keywords_count} {keyword_noun}."
                    ),
                }
            )

        categories, category_errors = _category_list_from_request_input(db, record)
        if category_errors:
            errors += category_errors
        if not categories:
            errors.append(
                {"field_name": "categories", "message": "Please specify at least one category."}
            )

        parameters = {
            "sample_uuid": sample["uuid"],
            "account_uuid": account_uuid,
            "container_uuid": container_uuid,
            "title": validator.string_value(record, "title", 3, 1000, True, errors),
            "abstract": validator.string_value(
                record, "abstract", 0, 8000, True, errors, strip_html=False
            ),
            "methods": validator.string_value(
                record, "methods", 0, 8000, False, errors, strip_html=False
            ),
            "resource_type": validator.string_value(record, "resource_type", 0, 512, False, errors),
            "subject": validator.string_value(record, "subject", 0, 512, False, errors),
            "publisher": validator.string_value(record, "publisher", 0, 10000, True, errors),
            "publication_year": datetime.now().strftime("%Y"),
            "alternate_identifier": validator.string_value(
                record, "alternate_identifier", 0, 255, False, errors
            ),
            "organizations": validator.string_value(record, "organizations", 0, 2048, True, errors),
            "physical_storage_location": validator.string_value(
                record, "physical_storage_location", 1, 2048, True, errors
            ),
            "geolocation": validator.string_value(record, "geolocation", 0, 255, False, errors),
            "longitude": validator.coordinate_value(record, "longitude", "E", False, errors),
            "latitude": validator.coordinate_value(record, "latitude", "N", False, errors),
            "sample_owner_name": validator.string_value(
                record, "sample_owner_name", 0, 255, True, errors
            ),
            "sample_owner_email": validator.email_value(record, "sample_owner_email", True, errors),
            "group_id": validator.integer_value(record, "group_id", 0, pow(2, 63), True, errors),
            "agreed_to_deposit_agreement": agreed_to_deposit_agreement,
            "agreed_to_publish": agreed_to_publish,
            "categories": categories,
        }

        if errors:
            raise InvalidInputError(errors, "ValidationFailed")

        account_record = db.account_by_uuid(sample["account_uuid"])
        if not account_record:
            return Response(status_code=500)

        if not db.update_physical_sample(**parameters):
            return Response(status_code=500)

        review_uri = db.insert_review(sample["uri"])
    except validator.ValidationException as error:
        raise InvalidInputError(error.message, error.code) from error
    finally:
        _process_locks.unlock(LockTypes.SUBMIT_PHYSICAL_SAMPLE)

    if review_uri is None:
        return Response(status_code=500)

    from djehuty.services import email as email_module

    subject = f"Request for review: {sample['container_uuid']}"
    email_module.send_email_to_reviewers(
        db,
        subject,
        "physical_sample_submitted_notification",
        account_email=value_or_none(account_record, "email"),
        dataset=sample,
        account=account_record,
    )
    return Response(status_code=204)


@router.post(
    "/physical-samples/{container_uuid}/publish",
    summary="Publish a physical sample (reviewer)",
    description=(
        "Publish a draft physical sample. Requires reviewer permissions on the "
        "impersonator cookie session or, when absent, the calling session. In "
        "production this registers the IGSN with DataCite before publishing."
    ),
    responses={
        201: _ok("Published", {"location": "https://data.4tu.nl/physical_sample/UUID"}),
        403: {"model": ErrorResponse},
    },
)
def publish_physical_sample(
    container_uuid: PhysicalSampleId,
    account=Depends(require_auth),
    db=Depends(get_db),
    impersonator_token: str | None = Depends(get_impersonator_token),
    token: str | None = Depends(get_token),
):
    from djehuty.services import datacite
    from djehuty.services import email as email_module
    from djehuty.utils.convenience import value_or, value_or_none

    reviewer_token, _, may_review_institution = _reviewer_context(db, impersonator_token, token)

    account_uuid = account["uuid"]
    sample = _resolve_physical_sample(
        db, container_uuid, account_uuid=account_uuid, is_published=False
    )
    if sample is None:
        raise ForbiddenError("Physical sample not found.")

    reviewer_account = db.account_by_session_token(reviewer_token)
    if may_review_institution:
        if value_or(sample, "group_id", "A") != value_or(reviewer_account, "group_id", "not-A"):
            raise ForbiddenError("Reviewer group mismatch.")

    # The draft stays editable after submission, so re-check the fields DataCite
    # requires before minting: without a title the XML build raises, and without
    # a named creator DataCite rejects an empty <creators>.
    creators = db.physical_sample_creators(container_uuid, account_uuid)
    has_named_creator = any(str(value_or(c, "full_name", "")).strip() for c in creators)
    if not str(value_or(sample, "title", "")).strip() or not has_named_creator:
        raise InvalidInputError(
            "The physical sample needs a title and at least one creator "
            "before it can be published.",
            "PublishValidation",
        )

    review_uri = value_or_none(sample, "review_uri")
    if review_uri is not None and reviewer_account is not None:
        if not db.update_review(
            review_uri,
            author_account_uuid=sample["account_uuid"],
            assigned_to=reviewer_account["uuid"],
            status="assigned",
        ):
            logger.error("Unable to assign reviewer before publishing for %s.", container_uuid)

    # Persist the Issued date (= publication date) on first publication; kept
    # as-is on later updates so the original issue date is preserved.
    existing_dates = db.physical_sample_dates(container_uuid, account_uuid)
    if not any(value_or(entry, "date_type", "") == "Issued" for entry in existing_dates):
        if (
            db.add_date_to_physical_sample(
                container_uuid, "issued", date.today().isoformat(), account_uuid
            )
            is None
        ):
            logger.error("Failed to record Issued date for physical sample %s.", container_uuid)

    if config.igsn_prefix is not None and config.in_production and not config.in_preproduction:
        if not datacite.register_physical_sample_doi(db, sample, account_uuid):
            return Response(status_code=502)

    if db.publish_physical_sample(container_uuid, account_uuid):
        try:
            owner_account = db.account_by_uuid(sample["account_uuid"])
            subject = f"Approved: {sample['title']}"
            email_module.send_templated_email(
                db,
                [owner_account["email"]],
                subject,
                "physical_sample_approved",
                base_url=config.base_url,
                support_email=config.support_email_address,
                title=sample["title"],
                container_uuid=sample["container_uuid"],
            )
        except (TypeError, IndexError, KeyError) as error:
            logger.error(
                "Unable to send approval e-mail for physical sample %s: %s.", sample["uuid"], error
            )

        location = f"{config.base_url}/physical_sample/{container_uuid}"
        return JSONResponse(
            content={"location": location}, status_code=201, headers={"Location": location}
        )

    return Response(status_code=500)


@router.post(
    "/physical-samples/{container_uuid}/decline",
    summary="Decline a physical sample (reviewer)",
    responses={204: {"description": "Declined"}, 403: {"model": ErrorResponse}},
)
def decline_physical_sample(
    container_uuid: PhysicalSampleId,
    account=Depends(require_auth),
    db=Depends(get_db),
    impersonator_token: str | None = Depends(get_impersonator_token),
    token: str | None = Depends(get_token),
):
    from djehuty.services import email as email_module
    from djehuty.utils.convenience import value_or

    reviewer_token, _, may_review_institution = _reviewer_context(db, impersonator_token, token)

    account_uuid = account["uuid"]
    sample = _resolve_physical_sample(
        db, container_uuid, account_uuid=account_uuid, is_published=False
    )
    if sample is None:
        raise ForbiddenError("Physical sample not found.")

    reviewer_account = db.account_by_session_token(reviewer_token)
    if may_review_institution:
        if value_or(sample, "group_id", "A") != value_or(reviewer_account, "group_id", "not-A"):
            raise ForbiddenError("Reviewer group mismatch.")

    if db.decline_physical_sample(container_uuid, account_uuid):
        try:
            owner_account = db.account_by_uuid(sample["account_uuid"])
            subject = f"Declined: {sample['title']}"
            email_module.send_templated_email(
                db,
                [owner_account["email"]],
                subject,
                "physical_sample_declined",
                base_url=config.base_url,
                support_email=config.support_email_address,
                title=sample["title"],
            )
        except (TypeError, IndexError, KeyError):
            logger.error("Unable to send decline e-mail for physical sample: %s.", sample["uuid"])

        return Response(status_code=204)

    return Response(status_code=500)


@router.put(
    "/physical-samples/{container_uuid}/assign-reviewer/{reviewer_uuid}",
    summary="Assign a reviewer to a physical sample",
    responses={204: {"description": "Reviewer assigned"}, 403: {"model": ErrorResponse}},
)
def assign_reviewer(
    container_uuid: PhysicalSampleId,
    reviewer_uuid: str,
    account=Depends(require_auth),
    db=Depends(get_db),
    account_token: str | None = Depends(get_token),
):
    from djehuty.utils.convenience import value_or, value_or_none
    from djehuty.web import validator

    if not validator.is_valid_uuid(reviewer_uuid):
        raise InvalidInputError("Invalid reviewer UUID.", "InvalidReviewerUuid")
    if not validator.is_valid_uuid(container_uuid):
        raise NotFoundError()

    if not db.may_review(account_token) and not db.may_review_institution(account_token):
        raise ForbiddenError("Reviewer permissions required.")

    reviewer = db.account_by_uuid(reviewer_uuid)
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

    if sample is None or reviewer is None:
        raise ForbiddenError("Physical sample or reviewer not found.")

    if db.may_review_institution(account_token):
        reviewing_account = db.account_by_session_token(account_token)
        if value_or(sample, "group_id", "A") != value_or(reviewing_account, "group_id", "not-A"):
            raise ForbiddenError("Reviewer group mismatch.")

    if db.update_review(
        value_or_none(sample, "review_uri"),
        author_account_uuid=sample["account_uuid"],
        assigned_to=reviewer["uuid"],
        status="assigned",
    ):
        db.cache.invalidate_by_prefix("physical-samples")
        db.cache.invalidate_by_prefix(f"physical-samples_{sample['account_uuid']}")
        return Response(status_code=204)

    return Response(status_code=500)
