"""Dataset collaborator endpoints for the v3 API."""

import logging

from fastapi import APIRouter, Body, Depends, Response
from fastapi.responses import JSONResponse

from djehuty.api.dependencies import get_db, require_auth
from djehuty.api.exceptions import ForbiddenError, InvalidInputError, NotFoundError
from djehuty.api.models.common import ErrorResponse
from djehuty.api.permissions import enforce_collaborative_permissions
from djehuty.api.v3._shared import _ok
from djehuty.web import formatter

router = APIRouter(tags=["V3 / Datasets / Collaborators"])
logger = logging.getLogger(__name__)

_COLLABORATOR_EXAMPLE = {
    "uuid": "5b8f2d1a-9c3e-4f7b-8a2d-1e6c4b9f0a3d",
    "account_uuid": "84cae99f-a691-4af2-9d21-f5c0817c26df",
    "first_name": "Dev",
    "last_name": "User",
    "email": "dev@djehuty.com",
    "metadata_read": True,
    "metadata_edit": True,
    "data_read": True,
    "data_edit": False,
    "data_remove": False,
    "is_supervisor": False,
    "group_id": 28586,
    "group_name": "Delft University of Technology",
    "is_inferred": False,
}

_PERMISSIONS_BODY_EXAMPLE = {
    "grant": {
        "summary": "Grant read/edit permissions",
        "value": {
            "metadata": {"read": True, "edit": True},
            "data": {"read": True, "edit": False, "remove": False},
        },
    }
}


def _resolve_dataset(db, dataset_uuid, account_uuid, is_published):
    """Resolve the dataset as legacy does: invalid UUID is 404, no match is 403."""
    from djehuty.web import validator

    if not validator.is_valid_uuid(dataset_uuid):
        raise NotFoundError()
    try:
        return db.datasets(
            container_uuid=dataset_uuid,
            account_uuid=account_uuid,
            is_published=is_published,
            is_latest=None,
            limit=1,
        )[0]
    except (IndexError, AttributeError, TypeError) as error:
        raise ForbiddenError(
            f"account:{account_uuid} attempted to access dataset:{dataset_uuid}."
        ) from error


@router.get(
    "/datasets/{container_uuid}/collaborators",
    summary="List collaborators",
    responses={
        200: _ok("The dataset's collaborators", [_COLLABORATOR_EXAMPLE]),
        403: {"model": ErrorResponse},
    },
)
def list_collaborators(container_uuid: str, account=Depends(require_auth), db=Depends(get_db)):
    dataset = _resolve_dataset(db, container_uuid, account["uuid"], is_published=None)
    enforce_collaborative_permissions(db, account["uuid"], dataset, "dataset", "metadata_read")
    collaborators = db.collaborators(dataset["uuid"])
    return JSONResponse(content=[formatter.format_collaborator_record(c) for c in collaborators])


@router.post(
    "/datasets/{container_uuid}/collaborators",
    summary="Add collaborator",
    responses={
        205: {"description": "Collaborator added"},
        400: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
)
def add_collaborator(
    container_uuid: str,
    body: dict = Body(
        ...,
        openapi_examples={
            "add": {
                "summary": "Add a collaborator account",
                "value": {
                    "account": "84cae99f-a691-4af2-9d21-f5c0817c26df",
                    "metadata": {"read": True, "edit": True},
                    "data": {"read": True, "edit": False, "remove": False},
                },
            }
        },
    ),
    account=Depends(require_auth),
    db=Depends(get_db),
):
    from djehuty.web import validator

    dataset = _resolve_dataset(db, container_uuid, account["uuid"], is_published=None)
    if dataset.get("is_shared_with_me", False):
        raise ForbiddenError(
            f"account:{account['uuid']} attempted to modify dataset:{container_uuid}."
        )

    try:
        metadata = body["metadata"]
        data = body["data"]
        collaborator_account_uuid = validator.string_value(body, "account")
        if not validator.is_valid_uuid(collaborator_account_uuid):
            raise validator.InvalidValueType(
                field_name="account",
                message="Expected a valid UUID for 'account'",
                code="WrongValueType",
            )
    except validator.ValidationException as error:
        raise InvalidInputError(error.message, error.code) from error

    if db.account_by_uuid(collaborator_account_uuid) is None:
        logger.error("Requesting collaborator account uuid failed. ")

    collaborators = db.insert_collaborator(
        dataset["uuid"],
        collaborator_account_uuid,
        account["uuid"],
        metadata["read"],
        metadata["edit"],
        False,
        data["read"],
        data["edit"],
        data["remove"],
    )
    if collaborators is None:
        return Response(status_code=500)
    return Response(status_code=205)


def _resolve_for_update(db, container_uuid, collaborator_uuid, account):
    """Shared PUT/DELETE resolution: draft only, edit permission, supervisor gate."""
    from djehuty.web import validator

    if not validator.is_valid_uuid(container_uuid) or not validator.is_valid_uuid(
        collaborator_uuid
    ):
        raise NotFoundError()
    dataset = _resolve_dataset(db, container_uuid, account["uuid"], is_published=False)
    enforce_collaborative_permissions(db, account["uuid"], dataset, "dataset", "metadata_edit")
    for collaborator in db.collaborators(dataset["uuid"]):
        if collaborator["account_uuid"] == account["uuid"] and not collaborator["is_supervisor"]:
            raise ForbiddenError(
                f"account:{account['uuid']} attempted to modify collaborators "
                f"for dataset:{container_uuid}."
            )
    return dataset


@router.put(
    "/datasets/{container_uuid}/collaborators/{collaborator_uuid}",
    summary="Update collaborator",
    responses={204: {"description": "Collaborator saved"}, 403: {"model": ErrorResponse}},
)
def update_collaborator(
    container_uuid: str,
    collaborator_uuid: str,
    body: dict = Body(..., openapi_examples=_PERMISSIONS_BODY_EXAMPLE),
    account=Depends(require_auth),
    db=Depends(get_db),
):
    dataset = _resolve_for_update(db, container_uuid, collaborator_uuid, account)
    metadata = body["metadata"]
    data = body["data"]
    if not db.update_collaborator(
        dataset["uuid"],
        collaborator_uuid,
        metadata["read"],
        metadata["edit"],
        False,
        data["read"],
        data["edit"],
        data["remove"],
    ):
        return Response(status_code=500)
    return Response(status_code=204)


@router.delete(
    "/datasets/{container_uuid}/collaborators/{collaborator_uuid}",
    summary="Remove collaborator",
    responses={204: {"description": "Collaborator removed"}, 403: {"model": ErrorResponse}},
)
def delete_collaborator(
    container_uuid: str,
    collaborator_uuid: str,
    account=Depends(require_auth),
    db=Depends(get_db),
):
    dataset = _resolve_for_update(db, container_uuid, collaborator_uuid, account)
    if db.delete_collaborator(dataset["uuid"], collaborator_uuid) is None:
        return Response(status_code=500)
    return Response(status_code=204)
