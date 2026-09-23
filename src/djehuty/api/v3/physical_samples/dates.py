"""Physical sample date endpoints for the v3 API."""

from typing import Any

from fastapi import APIRouter, Body, Depends, Response
from fastapi.responses import JSONResponse

from djehuty.api.dependencies import get_current_account, get_db
from djehuty.api.exceptions import (
    AuthorizationError,
    ForbiddenError,
    InvalidInputError,
    NotFoundError,
)
from djehuty.api.models.common import ErrorResponse
from djehuty.api.v3._shared import _ok
from djehuty.api.v3.physical_samples._shared import (
    PhysicalSampleId,
    _editable_physical_sample_draft,
)
from djehuty.web import formatter

router = APIRouter(tags=["V3 / Physical samples / Dates"])

# "issued" is intentionally omitted: the Issued date is set automatically to the
# publication date at publish time and cannot be entered by hand.
_DATE_TYPES = ["collected", "created", "destroyed", "updated", "other"]

_DATE_EXAMPLE = {
    "uuid": "b6f8d3c1-2b4e-4c6a-8d1f-3e5b7c9a0d2f",
    "type": "Collected",
    "date": "2010-11-02",
    "date_end": None,
    "created_date": "2026-07-03T10:48:50",
}


@router.get(
    "/physical-samples/{container_uuid}/dates",
    summary="List a physical sample's dates",
    responses={200: _ok("The dates", [_DATE_EXAMPLE]), 403: {"model": ErrorResponse}},
)
def list_dates(
    container_uuid: PhysicalSampleId,
    account=Depends(get_current_account),
    db=Depends(get_db),
):
    from djehuty.web import validator

    if not validator.is_valid_uuid(container_uuid):
        raise NotFoundError()
    if account is None:
        raise ForbiddenError()
    records = db.physical_sample_dates(container_uuid, account["uuid"])
    return JSONResponse(content=[formatter.format_physical_sample_date_record(r) for r in records])


@router.post(
    "/physical-samples/{container_uuid}/dates",
    summary="Add dates to a physical sample",
    responses={204: {"description": "Dates added"}, 400: {"model": ErrorResponse}},
)
def add_dates(
    container_uuid: PhysicalSampleId,
    body: Any = Body(default=None),
    account=Depends(get_current_account),
    db=Depends(get_db),
):
    from djehuty.web import validator

    if not validator.is_valid_uuid(container_uuid):
        raise NotFoundError()
    if account is None:
        raise AuthorizationError()
    if not isinstance(body, list):
        raise InvalidInputError("Expected a list.", "UnexpectedContent")

    account_uuid = account["uuid"]
    errors: list = []
    for date_record in body:
        date_type = validator.options_value(date_record, "type", _DATE_TYPES, True, errors)
        date, date_end = validator.partial_date_range_value(date_record, "date", True, errors)
        if date_type is not None and date is not None:
            if (
                db.add_date_to_physical_sample(
                    container_uuid, date_type, date, account_uuid, date_end
                )
                is None
            ):
                errors.append(
                    {"field_name": "PhysicalSampleDate", "message": "Failed to create date."}
                )

    if errors:
        raise InvalidInputError(errors, "ValidationFailed")
    return Response(status_code=204)


@router.delete(
    "/physical-samples/{container_uuid}/dates/{date_uuid}",
    summary="Remove a date",
    responses={204: {"description": "Date removed"}, 404: {"model": ErrorResponse}},
)
def delete_date(
    container_uuid: PhysicalSampleId,
    date_uuid: str,
    account=Depends(get_current_account),
    db=Depends(get_db),
):
    from rdflib import URIRef

    from djehuty.utils.rdf import uuid_to_uri
    from djehuty.web import validator

    if not validator.is_valid_uuid(container_uuid) or not validator.is_valid_uuid(date_uuid):
        raise NotFoundError()
    if account is None:
        raise AuthorizationError()

    account_uuid = account["uuid"]
    item = _editable_physical_sample_draft(db, container_uuid, account_uuid)
    if item is None:
        raise NotFoundError()

    try:
        dates = db.physical_sample_dates(container_uuid, account_uuid)
        dates.remove(next(filter(lambda d: d["uuid"] == date_uuid, dates)))
        dates = [URIRef(uuid_to_uri(d["uuid"], "physical-sample-date")) for d in dates]
        if db.update_item_list(item["sample_uuid"], account_uuid, dates, "dates"):
            return Response(status_code=204)
        return Response(status_code=500)
    except (IndexError, KeyError, StopIteration):
        return Response(status_code=500)
