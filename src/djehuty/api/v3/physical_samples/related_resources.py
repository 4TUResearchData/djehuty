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
from djehuty.api.models.physical_samples import PhysicalSampleRelatedResourceRecord
from djehuty.api.v3._shared import _err, _ok, _req
from djehuty.api.v3.physical_samples._shared import (
    ERR_FORBIDDEN,
    ERR_NOT_FOUND,
    ERR_SESSION,
    ERR_VALIDATION_LIST,
    PhysicalSampleId,
    ResourceId,
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
    "relation": "Is derived from",
    "type": "IGSN",
    "created_date": "2026-07-03T10:48:50",
}

_RELATED_BODY_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "identifier": {"type": "string", "maxLength": 2048},
            "identifier-type": {"type": "string", "enum": _IDENTIFIER_TYPES},
            "relation-type": {"type": "string", "enum": _RELATION_TYPES},
        },
        "required": ["identifier", "identifier-type", "relation-type"],
    },
}


@router.get(
    "/physical-samples/{container_uuid}/related-resources",
    summary="List a physical sample's related resources",
    response_model=list[PhysicalSampleRelatedResourceRecord],
    responses={
        200: _ok("The related resources", [_RESOURCE_EXAMPLE]),
        403: _err("Not allowed", ERR_FORBIDDEN),
        404: _err("No such sample", ERR_NOT_FOUND),
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
    description=(
        "Accepts a JSON array of related resources, each with an `identifier`, an "
        "`identifier-type` (IGSNDOI, OtherDOI or URL) and a `relation-type` "
        "(e.g. IsDerivedFrom, References)."
    ),
    status_code=204,
    openapi_extra=_req(_RELATED_BODY_SCHEMA),
    responses={
        204: {"description": "Related resources added"},
        400: _err("Invalid related-resource data", ERR_VALIDATION_LIST, model=None),
        403: _err("Not authenticated", ERR_SESSION),
        404: _err("No such sample", ERR_NOT_FOUND),
    },
)
def add_related_resources(
    container_uuid: PhysicalSampleId,
    body: Any = Body(
        default=None,
        openapi_examples={
            "default": {
                "summary": "A single derived-from relation",
                "value": [
                    {
                        "identifier": "10.4121/related-dataset",
                        "identifier-type": "IGSNDOI",
                        "relation-type": "IsDerivedFrom",
                    }
                ],
            }
        },
    ),
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
    status_code=204,
    responses={
        204: {"description": "Related resource removed"},
        403: _err("Not authenticated", ERR_SESSION),
        404: _err("No such sample", ERR_NOT_FOUND),
        500: {"description": "No such related resource, or the update failed"},
    },
)
def delete_related_resource(
    container_uuid: PhysicalSampleId,
    resource_uuid: ResourceId,
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
