"""Profile endpoints for the v3 API."""

import logging
import os
from typing import Annotated

from fastapi import APIRouter, Body, Depends, File, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from djehuty.api.dependencies import get_db, require_auth
from djehuty.api.exceptions import ForbiddenError, InvalidInputError, NotFoundError
from djehuty.api.models.common import ErrorResponse
from djehuty.api.v3._shared import _ok
from djehuty.web import formatter
from djehuty.web.config import config

logger = logging.getLogger(__name__)

router = APIRouter(tags=["V3 / Profile"])

_UPLOAD_CHUNK_SIZE = 4096

_PICTURE_LOCATION_EXAMPLE = {"location": "https://data.4tu.nl/v3/profile/picture"}

_CATEGORY_EXAMPLE = {
    "id": None,
    "uuid": "a9f8d3c1-2b4e-4c6a-8d1f-3e5b7c9a0d2f",
    "title": "Oceanography",
    "parent_id": None,
    "parent_uuid": None,
    "path": "/13431/13555",
    "source_id": 13555,
    "taxonomy_id": None,
}


@router.put(
    "/profile",
    summary="Update current user profile",
    responses={204: {"description": "Profile updated"}, 403: {"model": ErrorResponse}},
)
def update_profile(
    body: dict = Body(
        ...,
        openapi_examples={
            "default": {
                "summary": "Update name and job title",
                "value": {
                    "first_name": "Ada",
                    "last_name": "Lovelace",
                    "job_title": "Research Data Steward",
                    "email": "ada@example.org",
                },
            }
        },
    ),
    account=Depends(require_auth),
    db=Depends(get_db),
):
    from djehuty.web import validator

    if not isinstance(body, dict):
        raise InvalidInputError("Request body must be a JSON object.", "BadBody")

    try:
        categories = validator.array_value(body, "categories")
        if categories is not None:
            for index, _ in enumerate(categories):
                categories[index] = validator.string_value(categories, index, 36, 36)

        if db.update_account(
            account["uuid"],
            active=validator.integer_value(body, "active", 0, 1),
            job_title=validator.string_value(body, "job_title", 0, 255),
            email=validator.string_value(body, "email", 0, 255),
            first_name=validator.string_value(body, "first_name", 0, 255),
            last_name=validator.string_value(body, "last_name", 0, 255),
            location=validator.string_value(body, "location", 0, 255),
            twitter=validator.string_value(body, "twitter", 0, 255),
            linkedin=validator.string_value(body, "linkedin", 0, 255),
            website=validator.string_value(body, "website", 0, 255),
            biography=validator.string_value(body, "biography", 0, 32768),
            institution_user_id=validator.integer_value(body, "institution_user_id"),
            institution_id=validator.integer_value(body, "institution_id"),
            maximum_file_size=validator.integer_value(body, "maximum_file_size"),
            modified_date=validator.string_value(body, "modified_date", 0, 32),
            categories=categories,
        ):
            return Response(status_code=204)
        raise InvalidInputError("Failed to update account.", "UpdateFailed")
    except validator.ValidationException as error:
        raise InvalidInputError(error.message, error.code) from error


@router.get(
    "/profile/categories",
    summary="Get profile categories",
    responses={
        200: _ok("The current user's categories", [_CATEGORY_EXAMPLE]),
        403: {"model": ErrorResponse},
    },
)
def get_profile_categories(account=Depends(require_auth), db=Depends(get_db)):
    categories = db.account_categories(account["uuid"])
    return JSONResponse(content=[formatter.format_category_record(c) for c in categories])


@router.post(
    "/profile/quota-request",
    summary="Submit a quota request",
    responses={204: {"description": "Quota request submitted"}, 403: {"model": ErrorResponse}},
)
def submit_quota_request(
    body: dict = Body(
        ...,
        openapi_examples={
            "default": {
                "summary": "Request more storage",
                "value": {"new-quota": 100, "reason": "Large imaging dataset for project X."},
            }
        },
    ),
    account=Depends(require_auth),
    db=Depends(get_db),
):
    from djehuty.services import email as email_module
    from djehuty.web import validator

    try:
        quota_gb = validator.integer_value(body, "new-quota", required=True)
        reason = validator.string_value(body, "reason", 0, 10000, required=True, strip_html=False)

        if quota_gb < 1:
            raise InvalidInputError(
                "Requested quota must be at least 1 gigabyte.",
                "QuotaRequestSizeTooSmall",
            )

        new_quota = quota_gb * 1_000_000_000
        quota_uuid = db.insert_quota_request(account["uuid"], new_quota, reason)
        if quota_uuid is None:
            raise InvalidInputError("Failed to register quota request.", "QuotaRequestFailed")

        account_record = db.account_by_uuid(account["uuid"])
        email_module.send_email_to_quota_reviewers(
            db,
            f"Quota request for {account['uuid']}",
            "quota_request",
            email=account_record.get("email") if account_record else None,
            new_quota=quota_gb,
            reason=reason,
        )

        return Response(status_code=204)
    except validator.ValidationException as error:
        raise InvalidInputError(error.message, error.code) from error


@router.get(
    "/profile/picture",
    summary="Get own profile picture",
    responses={200: {"description": "Profile picture image", "content": {"image/*": {}}}},
)
def get_own_profile_picture(account=Depends(require_auth), db=Depends(get_db)):
    from djehuty.services.imaging import image_mimetype

    file_path = account.get("profile_image")
    if not file_path or not os.path.isfile(file_path):
        raise NotFoundError()

    mimetype = image_mimetype(file_path)
    if mimetype is None:
        raise ForbiddenError("Unsupported image format.")

    return FileResponse(file_path, media_type=mimetype)


@router.post(
    "/profile/picture",
    summary="Upload own profile picture",
    responses={
        200: _ok("Location of the uploaded picture", _PICTURE_LOCATION_EXAMPLE),
        403: {"model": ErrorResponse},
    },
)
async def upload_own_profile_picture(
    file: Annotated[UploadFile | None, File()] = None,
    account=Depends(require_auth),
    db=Depends(get_db),
):
    from PIL import Image

    if file is None:
        raise InvalidInputError("Uploading the profile image failed.", "UploadFailed")

    _, extension = os.path.splitext(file.filename)
    output_filename = os.path.join(config.profile_images_storage, account["uuid"])

    # AS-IS: only ".jpg" and ".png" are accepted; ".jpeg" is rejected.
    if extension.lower() not in (".jpg", ".png"):
        raise InvalidInputError("Only JPG and PNG images are supported.", "InvalidImageFormat")

    try:
        with open(output_filename, "wb") as output_file:
            while True:
                chunk = await file.read(_UPLOAD_CHUNK_SIZE)
                if not chunk:
                    break
                output_file.write(chunk)
        if os.name != "nt":
            os.chmod(output_filename, 0o600)

        with Image.open(output_filename) as image:
            width, height = image.size
        if width > 800 or height > 800:
            logger.warning(
                "Account %s uploaded an image of %d by %d pixels.",
                account["uuid"],
                width,
                height,
            )
            os.remove(output_filename)
            raise InvalidInputError(
                "The maximum image dimensions are 800 by 800 pixels.",
                "ImageTooLarge",
            )

        if db.update_account(account["uuid"], profile_image=output_filename):
            logger.info("Updated profile image for account %s", account["uuid"])
            return JSONResponse(content={"location": f"{config.base_url}/v3/profile/picture"})
    except OSError as error:
        # AS-IS: PIL's UnidentifiedImageError is an OSError subclass, so disk
        # write failures share this response with unrecognisable images.
        logger.error("Writing %s to disk failed.", output_filename)
        raise InvalidInputError(
            "Cannot determine the format of the uploaded image.",
            "InvalidImageFormat",
        ) from error

    # AS-IS: a failed db.update_account falls through to legacy's 405 catch-all.
    return Response(
        content="Acceptable methods: ['GET', 'POST', 'DELETE']",
        status_code=405,
        media_type="text/plain",
    )


@router.delete(
    "/profile/picture",
    summary="Delete own profile picture",
    responses={204: {"description": "Profile picture removed"}, 403: {"model": ErrorResponse}},
)
def delete_own_profile_picture(account=Depends(require_auth), db=Depends(get_db)):
    try:
        if "profile_image" in account:
            os.remove(account["profile_image"])
        if db.delete_account_property(account["uuid"], "profile_image"):
            logger.info("Removed profile image for account %s", account["uuid"])
        else:
            logger.error("Failed to remove profile image for %s", account["uuid"])
    except (KeyError, FileNotFoundError) as error:
        # AS-IS: when os.remove fails, delete_account_property is skipped and
        # the response is still 204.
        logger.error(
            "Failed to remove profile image for %s due to: %s",
            account["uuid"],
            error,
        )
    return Response(status_code=204)


@router.get(
    "/profile/picture/{account_uuid}",
    summary="Get profile picture for an account",
    responses={200: {"description": "Profile picture image", "content": {"image/*": {}}}},
)
def get_profile_picture_for_account(account_uuid: str, db=Depends(get_db)):
    from djehuty.services.imaging import image_mimetype
    from djehuty.web import validator

    if not validator.is_valid_uuid(account_uuid):
        raise NotFoundError()

    try:
        acct = db.account_by_uuid(account_uuid)
        file_path = acct["profile_image"]
        if not os.path.isfile(file_path):
            raise NotFoundError()

        mimetype = image_mimetype(file_path)
        if mimetype is None:
            raise ForbiddenError("Unsupported image format.")
        return FileResponse(file_path, media_type=mimetype)
    except (KeyError, FileNotFoundError):
        # AS-IS (#111): for a missing account, account_by_uuid returns None and
        # acct["profile_image"] raises TypeError, which legacy's
        # `except (KeyError, FileNotFoundError)` does not catch -> uncaught ->
        # HTTP 500. So TypeError is deliberately NOT caught here.
        raise NotFoundError() from None
