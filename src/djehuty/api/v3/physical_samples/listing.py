"""Physical sample detail endpoints (create / read / update) for the v3 API."""

from fastapi import APIRouter, Body, Depends, Response
from fastapi.responses import JSONResponse

from djehuty.api.dependencies import get_current_account, get_db, get_token, require_auth
from djehuty.api.exceptions import ForbiddenError, InvalidInputError, NotFoundError
from djehuty.api.models.common import ErrorResponse
from djehuty.api.v3._shared import _ok
from djehuty.api.v3.physical_samples._shared import (
    PhysicalSampleId,
    _account_can_use_igsn,
    _category_list_from_request_input,
    _resolve_physical_sample,
)
from djehuty.web import formatter
from djehuty.web.config import config

router = APIRouter(tags=["V3 / Physical samples"])

_SAMPLE_EXAMPLE = {
    "uuid": "27e6a01d-3f09-4d90-ae02-1d749ae9efb8",
    "title": "Basalt core sample BR-2025-014",
    "abstract": "<p>Drill core recovered off the coast of Texel.</p>",
    "methods": None,
    "resource_type": "Rock",
    "subject": None,
    "last_modified": "2026-07-03T10:48:50",
}


def _details_get(db, account, container_uuid):
    """Read one sample: the caller's draft when authenticated, else the
    published latest. AS-IS: an empty result is a 404 (the legacy
    ``if not physical_sample`` 403 branch is dead — IndexError fires first);
    a bad UUID also lands as a 404 via the same IndexError.
    """
    account_uuid = account["uuid"] if account else None
    params = {
        "is_published": account_uuid is None,
        "is_latest": account_uuid is None,
        "account_uuid": account_uuid,
    }
    if container_uuid is not None:
        params["container_uuid"] = container_uuid
    try:
        sample = db.physical_samples(**params)[0]
    except IndexError as error:
        raise NotFoundError() from error
    return JSONResponse(content=formatter.format_physical_sample_record(sample))


def _details_put(db, account, token, container_uuid, body):
    """Create (no UUID) or update (with UUID) a draft sample."""
    from djehuty.web import validator

    if not db.is_depositor(token):
        raise ForbiddenError("Depositor permissions required.")
    account_uuid = account["uuid"]
    if not _account_can_use_igsn(db, account_uuid):
        raise ForbiddenError()

    has_created_new = False
    if container_uuid is None:
        container_uuid, _ = db.insert_physical_sample(
            title="Untitled item", account_uuid=account_uuid
        )
        has_created_new = True
    elif not validator.is_valid_uuid(container_uuid):
        raise NotFoundError()

    try:
        sample = _resolve_physical_sample(
            db, container_uuid, account_uuid=account_uuid, is_published=False
        )
        if sample is None:
            raise NotFoundError()

        categories, errors = _category_list_from_request_input(db, body)
        if errors:
            raise InvalidInputError(errors, "ValidationFailed")

        parameters = {
            "sample_uuid": sample["uuid"],
            "account_uuid": account_uuid,
            "container_uuid": container_uuid,
            "title": validator.string_value(body, "title", 0, 1000, False),
            "abstract": validator.string_value(body, "abstract", 0, 8000, False),
            "methods": validator.string_value(body, "methods", 0, 8000, False),
            "resource_type": validator.string_value(body, "resource_type", 0, 512, False),
            "subject": validator.string_value(body, "subject", 0, 512, False),
            "alternate_identifier": validator.string_value(
                body, "alternate_identifier", 0, 512, False
            ),
            "organizations": validator.string_value(body, "organizations", 0, 2048, False),
            "physical_storage_location": validator.string_value(
                body, "physical_storage_location", 0, 2048, False
            ),
            "geolocation": validator.string_value(body, "geolocation", 0, 255, False),
            "longitude": validator.coordinate_value(body, "longitude", "E", False),
            "latitude": validator.coordinate_value(body, "latitude", "N", False),
            "sample_owner_name": validator.string_value(body, "sample_owner_name", 0, 255, False),
            "sample_owner_email": validator.string_value(body, "sample_owner_email", 0, 255, False),
            "group_id": validator.integer_value(body, "group_id", 0, pow(2, 63), False),
            "agreed_to_deposit_agreement": validator.boolean_value(
                body, "agreed_to_deposit_agreement", False, False
            ),
            "agreed_to_publish": validator.boolean_value(body, "agreed_to_publish", False, False),
            "categories": categories,
        }

        if not db.update_physical_sample(**parameters):
            return Response(status_code=500)

        if has_created_new:
            return JSONResponse(
                content={"location": f"{config.base_url}/v3/physical-samples/{container_uuid}"},
                status_code=201,
            )
        return Response(status_code=204)
    # AS-IS: a bare IndexError inside the update block maps to 403, not 500.
    except IndexError as error:
        raise ForbiddenError() from error
    except validator.ValidationException as error:
        raise InvalidInputError(error.message, error.code) from error


@router.get(
    "/physical-samples",
    summary="Read a physical sample (first match)",
    description=(
        "Returns a single physical sample record. AS-IS quirk: with no UUID this "
        "returns the *first* matching record (a single object, not a list) — the "
        "caller's first draft when authenticated, else the first published sample."
    ),
    responses={200: _ok("A physical sample", _SAMPLE_EXAMPLE), 404: {"model": ErrorResponse}},
)
def read_physical_sample_first(
    account=Depends(get_current_account),
    db=Depends(get_db),
):
    return _details_get(db, account, None)


@router.get(
    "/physical-samples/{container_uuid}",
    summary="Read a physical sample",
    description=(
        "Returns a single physical sample: the caller's draft when authenticated, "
        "otherwise the published latest version."
    ),
    responses={200: _ok("A physical sample", _SAMPLE_EXAMPLE), 404: {"model": ErrorResponse}},
)
def read_physical_sample(
    container_uuid: PhysicalSampleId,
    account=Depends(get_current_account),
    db=Depends(get_db),
):
    return _details_get(db, account, container_uuid)


@router.put(
    "/physical-samples",
    summary="Create a physical sample draft",
    responses={201: _ok("Created", {"location": "https://data.4tu.nl/v3/physical-samples/UUID"})},
)
def create_physical_sample(
    body: dict = Body(default={}),
    account=Depends(require_auth),
    token: str = Depends(get_token),
    db=Depends(get_db),
):
    return _details_put(db, account, token, None, body)


@router.put(
    "/physical-samples/{container_uuid}",
    summary="Update a physical sample draft",
    responses={204: {"description": "Updated"}, 403: {"model": ErrorResponse}},
)
def update_physical_sample(
    container_uuid: PhysicalSampleId,
    body: dict = Body(default={}),
    account=Depends(require_auth),
    token: str = Depends(get_token),
    db=Depends(get_db),
):
    return _details_put(db, account, token, container_uuid, body)
