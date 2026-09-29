"""Physical sample related-resource endpoints for the v3 API."""

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

router = APIRouter(tags=["V3 / Physical samples / Related resources"])

_IDENTIFIER_TYPES = ["IGSNDOI", "OtherDOI", "URL"]
_RELATION_TYPES = [
    "IsPartOf",
    "HasPart",
    "IsDerivedFrom",
    "IsSourceOf",
    "IsReferencedBy",
    "References",
    "IsCitedBy",
    "Cites",
    "IsDescribedBy",
    "Describes",
]

_RESOURCE_EXAMPLE = {
    "uuid": "d1e2f3a4-5b6c-7d8e-9f0a-1b2c3d4e5f6a",
    "url": "10.4121/related-dataset",
    "relation": "IsDerivedFrom",
    "type": "IGSNDOI",
    "created_date": "2026-07-03T10:48:50",
}


@router.get(
    "/physical-samples/{container_uuid}/related-resources",
    summary="List a physical sample's related resources",
    responses={
        200: _ok("The related resources", [_RESOURCE_EXAMPLE]),
        403: {"model": ErrorResponse},
    },
)
def list_related_resources(
    container_uuid: PhysicalSampleId,
    account=Depends(get_current_account),
    db=Depends(get_db),
):
    from djehuty.web import validator

    if not validator.is_valid_uuid(container_uuid):
        raise NotFoundError()
    if account is None:
        raise ForbiddenError()
    records = db.physical_sample_related_resources(container_uuid, account["uuid"])
    return JSONResponse(
        content=[formatter.format_physical_sample_related_resource_record(r) for r in records]
    )


@router.post(
    "/physical-samples/{container_uuid}/related-resources",
    summary="Add related resources to a physical sample",
    responses={204: {"description": "Related resources added"}, 400: {"model": ErrorResponse}},
)
def add_related_resources(
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
    for resource in body:
        url = validator.string_value(resource, "identifier", 0, 2048, True, errors)
        identifier_type = validator.options_value(
            resource, "identifier-type", _IDENTIFIER_TYPES, True, errors
        )
        identifier_relation = validator.options_value(
            resource, "relation-type", _RELATION_TYPES, True, errors
        )
        if url is not None and identifier_type is not None and identifier_relation is not None:
            if (
                db.add_related_resource_to_physical_sample(
                    container_uuid, url, identifier_type, identifier_relation, account_uuid
                )
                is None
            ):
                errors.append(
                    {
                        "field_name": "PhysicalSampleRelatedResource",
                        "message": "Failed to create record of related identifier.",
                    }
                )

    if errors:
        raise InvalidInputError(errors, "ValidationFailed")
    return Response(status_code=204)


@router.delete(
    "/physical-samples/{container_uuid}/related-resources/{resource_uuid}",
    summary="Remove a related resource",
    responses={204: {"description": "Related resource removed"}, 404: {"model": ErrorResponse}},
)
def delete_related_resource(
    container_uuid: PhysicalSampleId,
    resource_uuid: str,
    account=Depends(get_current_account),
    db=Depends(get_db),
):
    from rdflib import URIRef

    from djehuty.utils.rdf import uuid_to_uri
    from djehuty.web import validator

    if not validator.is_valid_uuid(container_uuid) or not validator.is_valid_uuid(resource_uuid):
        raise NotFoundError()
    if account is None:
        raise AuthorizationError()

    account_uuid = account["uuid"]
    item = _editable_physical_sample_draft(db, container_uuid, account_uuid)
    if item is None:
        raise NotFoundError()

    try:
        resources = db.physical_sample_related_resources(container_uuid, account_uuid)
        resources.remove(next(filter(lambda r: r["uuid"] == resource_uuid, resources)))
        resources = [
            URIRef(uuid_to_uri(r["uuid"], "physical-sample-related-resource")) for r in resources
        ]
        if db.update_item_list(item["sample_uuid"], account_uuid, resources, "related_resources"):
            return Response(status_code=204)
        return Response(status_code=500)
    except (IndexError, KeyError, StopIteration):
        return Response(status_code=500)
