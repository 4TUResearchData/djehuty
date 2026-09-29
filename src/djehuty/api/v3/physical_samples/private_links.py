"""Physical sample private-link endpoints for the v3 API."""

import secrets

from fastapi import APIRouter, Body, Depends, Response
from fastapi.responses import JSONResponse

from djehuty.api.dependencies import get_db, require_auth
from djehuty.api.exceptions import InvalidInputError, NotFoundError
from djehuty.api.models.common import ErrorResponse
from djehuty.api.v3._shared import _ok
from djehuty.api.v3.physical_samples._shared import PhysicalSampleId, _resolve_physical_sample
from djehuty.web import formatter
from djehuty.web.config import config

router = APIRouter(tags=["V3 / Physical samples / Private links"])

_LINK_EXAMPLE = {"id": "9c8b7a6d5e4f", "is_active": True, "expires_date": None}


@router.get(
    "/physical-samples/{container_uuid}/private_links",
    summary="List a physical sample's private links",
    responses={200: _ok("The private links", [_LINK_EXAMPLE]), 404: {"model": ErrorResponse}},
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
    description="Creates a private link. AS-IS: returns 200 (not 201) with the link location.",
    responses={
        200: _ok("Created", {"location": "https://data.4tu.nl/private_physical_sample/TOKEN"}),
        404: {"model": ErrorResponse},
    },
)
def create_private_link(
    container_uuid: PhysicalSampleId,
    body: dict = Body(default={}),
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
    responses={200: _ok("The private link", [_LINK_EXAMPLE]), 404: {"model": ErrorResponse}},
)
def get_private_link(
    container_uuid: PhysicalSampleId,
    link_id: str,
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
    responses={
        200: _ok("Updated", {"location": "https://data.4tu.nl/private_physical_sample/TOKEN"}),
        404: {"model": ErrorResponse},
    },
)
def update_private_link(
    container_uuid: PhysicalSampleId,
    link_id: str,
    body: dict = Body(default={}),
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
    responses={204: {"description": "Private link removed"}, 404: {"model": ErrorResponse}},
)
def delete_private_link(
    container_uuid: PhysicalSampleId,
    link_id: str,
    account=Depends(require_auth),
    db=Depends(get_db),
):
    sample = _resolve_physical_sample(db, container_uuid, account["uuid"], is_published=False)
    if sample is None:
        raise NotFoundError()
    if db.delete_private_links(sample["container_uuid"], account["uuid"], link_id) is None:
        return Response(status_code=500)
    return Response(status_code=204)
