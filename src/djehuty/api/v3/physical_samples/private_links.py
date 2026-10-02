"""Physical sample private-link endpoints for the v3 API."""

import secrets

from fastapi import APIRouter, Body, Depends, Response
from fastapi.responses import JSONResponse

from djehuty.api.dependencies import get_db, require_auth
from djehuty.api.exceptions import InvalidInputError, NotFoundError
from djehuty.api.models.physical_samples import PrivateLinkRecord
from djehuty.api.v3._shared import _err, _ok, _req
from djehuty.api.v3.physical_samples._shared import (
    ERR_NOT_FOUND,
    ERR_SESSION,
    ERR_VALIDATION,
    LinkId,
    PhysicalSampleId,
    _resolve_physical_sample,
)
from djehuty.web import formatter
from djehuty.web.config import config

router = APIRouter(tags=["V3 / Physical samples / Private links"])

_LINK_EXAMPLE = {"id": "9c8b7a6d5e4f", "is_active": True, "expires_date": None}

_LINK_CREATE_SCHEMA = {
    "type": "object",
    "properties": {
        "expires_date": {"type": "string", "format": "date", "description": "YYYY-MM-DD."},
        "read_only": {"type": "boolean"},
    },
}

_LINK_UPDATE_SCHEMA = {
    "type": "object",
    "properties": {
        "expires_date": {"type": "string", "maxLength": 255},
        "is_active": {"type": "boolean"},
    },
}


@router.get(
    "/physical-samples/{container_uuid}/private_links",
    summary="List a physical sample's private links",
    response_model=list[PrivateLinkRecord],
    responses={
        200: _ok("The private links", [_LINK_EXAMPLE]),
        403: _err("Not authenticated", ERR_SESSION),
        404: _err("No such sample", ERR_NOT_FOUND),
    },
)
def list_private_links(
    container_uuid: PhysicalSampleId,
    account=Depends(require_auth),
    db=Depends(get_db),
):
    sample = _resolve_physical_sample(db, container_uuid, account["uuid"], is_published=False)
    if sample is None:
        raise NotFoundError()
    links = db.private_links(item_uri=sample["uri"], account_uuid=account["uuid"])
    return JSONResponse(content=[formatter.format_private_links_record(link) for link in links])


@router.post(
    "/physical-samples/{container_uuid}/private_links",
    summary="Create a private link",
    description=(
        "Creates a private link. The body may set `expires_date` (YYYY-MM-DD) and "
        "`read_only`. AS-IS: returns 200 (not 201) with the link location."
    ),
    openapi_extra=_req(_LINK_CREATE_SCHEMA),
    responses={
        200: _ok("Created", {"location": "https://data.4tu.nl/private_physical_sample/TOKEN"}),
        400: _err("Invalid field values", ERR_VALIDATION),
        403: _err("Not authenticated", ERR_SESSION),
        404: _err("No such sample", ERR_NOT_FOUND),
        500: {"description": "Could not create the private link"},
    },
)
def create_private_link(
    container_uuid: PhysicalSampleId,
    body: dict = Body(
        default={},
        openapi_examples={"default": {"value": {"expires_date": "2027-01-01", "read_only": True}}},
    ),
    account=Depends(require_auth),
    db=Depends(get_db),
):
    from rdflib import URIRef

    from djehuty.web import validator

    account_uuid = account["uuid"]
    sample = _resolve_physical_sample(db, container_uuid, account_uuid, is_published=False)
    if sample is None:
        raise NotFoundError()

    try:
        id_string = secrets.token_urlsafe()
        expires_date = validator.date_value(body, "expires_date", False)
        # expires_date validates to YYYY-MM-DD but a full timestamp is stored.
        if expires_date:
            expires_date = expires_date + "T00:00:00Z"

        link_uri = db.insert_private_link(
            item_uuid=sample["sample_uuid"],
            account_uuid=account_uuid,
            item_type="physical_sample",
            expires_date=expires_date,
            read_only=validator.boolean_value(body, "read_only", False),
            id_string=id_string,
            is_active=True,
        )
        if link_uri is None:
            return Response(status_code=500)

        links = db.private_links(item_uri=sample["uri"], account_uuid=account_uuid)
        links = [URIRef(link["uri"]) for link in links] + [URIRef(link_uri)]
        if not db.update_item_list(sample["uuid"], account_uuid, links, "private_links"):
            return Response(status_code=500)

        return JSONResponse(
            content={"location": f"{config.base_url}/private_physical_sample/{id_string}"}
        )
    except validator.ValidationException as error:
        raise InvalidInputError(error.message, error.code) from error


@router.get(
    "/physical-samples/{container_uuid}/private_links/{link_id}",
    summary="Get a private link",
    description=(
        "AS-IS: returns a list, not a single object, and responds 200 with an empty "
        "list when no link matches `link_id`."
    ),
    response_model=list[PrivateLinkRecord],
    responses={
        200: _ok("The matching private links (a list)", [_LINK_EXAMPLE]),
        403: _err("Not authenticated", ERR_SESSION),
        404: _err("No such sample", ERR_NOT_FOUND),
    },
)
def get_private_link(
    container_uuid: PhysicalSampleId,
    link_id: LinkId,
    account=Depends(require_auth),
    db=Depends(get_db),
):
    sample = _resolve_physical_sample(db, container_uuid, account["uuid"], is_published=False)
    if sample is None:
        raise NotFoundError()
    links = db.private_links(
        item_uri=sample["uri"], id_string=link_id, account_uuid=account["uuid"]
    )
    return JSONResponse(content=[formatter.format_private_links_record(link) for link in links])


@router.put(
    "/physical-samples/{container_uuid}/private_links/{link_id}",
    summary="Update a private link",
    description="Updates a private link. The body may set `expires_date` and `is_active`.",
    openapi_extra=_req(_LINK_UPDATE_SCHEMA),
    responses={
        200: _ok("Updated", {"location": "https://data.4tu.nl/private_physical_sample/TOKEN"}),
        400: _err("Invalid field values", ERR_VALIDATION),
        403: _err("Not authenticated", ERR_SESSION),
        404: _err("No such sample", ERR_NOT_FOUND),
        500: {"description": "Could not update the private link"},
    },
)
def update_private_link(
    container_uuid: PhysicalSampleId,
    link_id: LinkId,
    body: dict = Body(
        default={},
        openapi_examples={"default": {"value": {"expires_date": "2027-01-01", "is_active": False}}},
    ),
    account=Depends(require_auth),
    db=Depends(get_db),
):
    from djehuty.web import validator

    sample = _resolve_physical_sample(db, container_uuid, account["uuid"], is_published=False)
    if sample is None:
        raise NotFoundError()

    try:
        result = db.update_private_link(
            sample["uri"],
            account["uuid"],
            link_id,
            expires_date=validator.string_value(body, "expires_date", 0, 255, False),
            is_active=validator.boolean_value(body, "is_active", False),
        )
        if result is None:
            return Response(status_code=500)
        return JSONResponse(
            content={"location": f"{config.base_url}/private_physical_sample/{link_id}"}
        )
    except validator.ValidationException as error:
        raise InvalidInputError(error.message, error.code) from error


@router.delete(
    "/physical-samples/{container_uuid}/private_links/{link_id}",
    summary="Delete a private link",
    status_code=204,
    responses={
        204: {"description": "Private link removed"},
        403: _err("Not authenticated", ERR_SESSION),
        404: _err("No such sample", ERR_NOT_FOUND),
        500: {"description": "Could not remove the private link"},
    },
)
def delete_private_link(
    container_uuid: PhysicalSampleId,
    link_id: LinkId,
    account=Depends(require_auth),
    db=Depends(get_db),
):
    sample = _resolve_physical_sample(db, container_uuid, account["uuid"], is_published=False)
    if sample is None:
        raise NotFoundError()
    if db.delete_private_links(sample["container_uuid"], account["uuid"], link_id) is None:
        return Response(status_code=500)
    return Response(status_code=204)
