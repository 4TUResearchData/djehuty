"""Physical sample creator (author) endpoints for the v3 API."""

from typing import Any

from fastapi import APIRouter, Body, Depends, Response
from fastapi.responses import JSONResponse

from djehuty.api.dependencies import get_current_account, get_db, require_auth
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
    _author_list_from_request_input,
    _editable_physical_sample_draft,
)
from djehuty.web import formatter

router = APIRouter(tags=["V3 / Physical samples / Creators"])

_CREATOR_EXAMPLE = {
    "uuid": "07d6e6ce-b1bf-43ca-86e6-7a3ab8bc8416",
    "first_name": "Ada",
    "last_name": "Lovelace",
    "full_name": "Ada Lovelace",
    "email": None,
    "orcid": None,
    "is_editable": True,
}


@router.get(
    "/physical-samples/{container_uuid}/creators",
    summary="List a physical sample's creators",
    responses={200: _ok("The creators", [_CREATOR_EXAMPLE]), 403: {"model": ErrorResponse}},
)
def list_creators(
    container_uuid: PhysicalSampleId,
    account=Depends(get_current_account),
    db=Depends(get_db),
):
    # AS-IS: an unauthenticated caller gets 403 "Not allowed." here (not the
    # "invalid session token" shape).
    if account is None:
        raise ForbiddenError()
    creators = db.physical_sample_creators(container_uuid, account["uuid"])
    return JSONResponse(content=[formatter.format_author_record_v3(c) for c in creators])


@router.post(
    "/physical-samples/{container_uuid}/creators",
    summary="Add creators to a physical sample",
    description=(
        "Accepts either a JSON object with an `authors` list (creating new author "
        "records and appending them) or a JSON array of existing author UUIDs."
    ),
    responses={204: {"description": "Creators added"}, 400: {"model": ErrorResponse}},
)
def add_creators(
    container_uuid: PhysicalSampleId,
    body: Any = Body(default=None),
    account=Depends(require_auth),
    db=Depends(get_db),
):
    from rdflib import URIRef

    from djehuty.utils.rdf import uuid_to_uri
    from djehuty.web import validator

    account_uuid = account["uuid"]
    try:
        if isinstance(body, dict):
            authors, errors = _author_list_from_request_input(db, body, created_by=account_uuid)
            if errors:
                raise InvalidInputError(errors, "ValidationFailed")
            item = _editable_physical_sample_draft(db, container_uuid, account_uuid)
            if item is None:
                raise NotFoundError()
            existing = db.physical_sample_creators(container_uuid, account_uuid)
            creators = [URIRef(uuid_to_uri(c["uuid"], "author")) for c in existing] + authors
            if not db.update_item_list(item["sample_uuid"], account_uuid, creators, "creators"):
                return Response(status_code=500)
            return Response(status_code=204)

        if isinstance(body, list):
            errors = []
            for author_uuid in body:
                if not validator.is_valid_uuid(author_uuid):
                    errors.append({"field_name": "author", "message": "Expected a valid UUID."})
            if errors:
                raise InvalidInputError(errors, "ValidationFailed")
            for author_uuid in body:
                if (
                    db.add_creator_to_physical_sample(container_uuid, author_uuid, account_uuid)
                    is None
                ):
                    errors.append({"field_name": "author", "message": "Failed database insert."})
            if errors:
                raise InvalidInputError(errors, "ValidationFailed")
            return Response(status_code=204)

        raise InvalidInputError("Expected a list.", "UnexpectedContent")
    except validator.ValidationException as error:
        raise InvalidInputError(error.message, error.code) from error


@router.get(
    "/physical-samples/{container_uuid}/creators/{creator_uuid}",
    summary="Get a single creator",
    responses={200: _ok("A creator", _CREATOR_EXAMPLE), 404: {"model": ErrorResponse}},
)
def get_creator(
    container_uuid: PhysicalSampleId,
    creator_uuid: str,
    account=Depends(get_current_account),
    db=Depends(get_db),
):
    from djehuty.utils.convenience import value_or
    from djehuty.web import validator

    # AS-IS: UUID validity is checked before authentication (bad UUID -> 404).
    if not validator.is_valid_uuid(container_uuid) or not validator.is_valid_uuid(creator_uuid):
        raise NotFoundError()
    if account is None:
        raise AuthorizationError()

    creators = db.physical_sample_creators(container_uuid, account["uuid"])
    creator = next((c for c in creators if value_or(c, "uuid", None) == creator_uuid), None)
    if creator is None:
        raise NotFoundError()
    return JSONResponse(content=formatter.format_author_record_v3(creator))


@router.delete(
    "/physical-samples/{container_uuid}/creators/{creator_uuid}",
    summary="Remove a creator",
    responses={204: {"description": "Creator removed"}, 404: {"model": ErrorResponse}},
)
def delete_creator(
    container_uuid: PhysicalSampleId,
    creator_uuid: str,
    account=Depends(get_current_account),
    db=Depends(get_db),
):
    from rdflib import URIRef

    from djehuty.utils.rdf import uuid_to_uri
    from djehuty.web import validator

    if not validator.is_valid_uuid(container_uuid) or not validator.is_valid_uuid(creator_uuid):
        raise NotFoundError()
    if account is None:
        raise AuthorizationError()

    account_uuid = account["uuid"]
    item = _editable_physical_sample_draft(db, container_uuid, account_uuid)
    if item is None:
        raise NotFoundError()

    try:
        creators = db.physical_sample_creators(container_uuid, account_uuid)
        # AS-IS: next(filter(...)) raises StopIteration for an absent creator on
        # an otherwise valid draft -> 500 (not 404).
        creators.remove(next(filter(lambda c: c["uuid"] == creator_uuid, creators)))
        creators = [URIRef(uuid_to_uri(c["uuid"], "author")) for c in creators]
        if db.update_item_list(item["sample_uuid"], account_uuid, creators, "creators"):
            return Response(status_code=204)
        return Response(status_code=500)
    except (IndexError, KeyError, StopIteration):
        return Response(status_code=500)


@router.post(
    "/physical-samples/{container_uuid}/reorder-creators",
    summary="Reorder creators",
    responses={205: {"description": "Creators reordered"}, 400: {"model": ErrorResponse}},
)
def reorder_creators(
    container_uuid: PhysicalSampleId,
    body: dict = Body(
        default={},
        openapi_examples={
            "move_up": {
                "summary": "Move a creator up",
                "value": {"author": "07d6e6ce-b1bf-43ca-86e6-7a3ab8bc8416", "direction": "up"},
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

    errors: list = []
    direction = validator.options_value(
        body, "direction", ["up", "down"], required=True, error_list=errors
    )
    author_uuid = validator.string_value(body, "author", required=True, error_list=errors)
    if not validator.is_valid_uuid(author_uuid):
        errors.append({"field_name": "author", "message": "Author should be a valid UUID."})
    if errors:
        raise InvalidInputError(errors, "ValidationFailed")

    if db.reorder_authors(
        account["uuid"], container_uuid, author_uuid, direction, predicate="creators"
    ):
        return Response(status_code=205)
    return Response(status_code=500)
