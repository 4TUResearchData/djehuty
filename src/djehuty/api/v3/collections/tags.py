"""Collection tag endpoints for the v3 API."""

from fastapi import APIRouter, Body, Depends, Query, Response
from fastapi.responses import JSONResponse

from djehuty.api.dependencies import get_db, require_auth
from djehuty.api.exceptions import InvalidInputError, NotFoundError
from djehuty.api.models.common import ErrorResponse
from djehuty.api.v3._shared import _ok
from djehuty.api.v3.collections._shared import _resolve_collection_for_owner
from djehuty.web import formatter

router = APIRouter(tags=["V3 / Collections / Tags"])


@router.get(
    "/collections/{collection_id}/tags",
    summary="List collection tags",
    responses={
        200: _ok("The collection's tags", ["climate", "oceanography"]),
        403: {"model": ErrorResponse},
    },
)
def list_collection_tags(
    collection_id: str,
    account=Depends(require_auth),
    db=Depends(get_db),
):
    collection = _resolve_collection_for_owner(db, collection_id, account["uuid"])
    tags = db.tags(item_uri=collection["uri"], account_uuid=account["uuid"])
    return JSONResponse(content=[formatter.format_tag_record(t) for t in tags])


@router.post(
    "/collections/{collection_id}/tags",
    summary="Add tags to a collection",
    responses={205: {"description": "Tags added"}, 403: {"model": ErrorResponse}},
)
def add_collection_tags(
    collection_id: str,
    body: dict = Body(
        ...,
        openapi_examples={
            "default": {
                "summary": "Add keywords",
                "value": {"tags": ["climate", "oceanography"]},
            }
        },
    ),
    account=Depends(require_auth),
    db=Depends(get_db),
):
    from djehuty.utils.convenience import deduplicate_list
    from djehuty.web import validator

    collection = _resolve_collection_for_owner(db, collection_id, account["uuid"])
    new_tags_input = body.get("tags")
    if not isinstance(new_tags_input, list):
        raise InvalidInputError("Expected a 'tags' field.", "NoTagsField")
    new_tags: list[str] = []
    try:
        for index, _ in enumerate(new_tags_input):
            new_tags.append(
                validator.string_value(new_tags_input, index, 0, 512, True),
            )
    except validator.ValidationException as error:
        raise InvalidInputError(error.message, error.code) from error

    existing = db.tags(
        item_uri=collection["uri"],
        account_uuid=account["uuid"],
        limit=10000,
    )
    existing_tags = [t["tag"] for t in existing]
    merged = deduplicate_list(existing_tags + new_tags)
    if not db.update_item_list(
        collection["uuid"],
        account["uuid"],
        merged,
        "tags",
    ):
        raise InvalidInputError("Updating tags failed.", "UpdateFailed")
    return Response(status_code=205)


@router.delete(
    "/collections/{collection_id}/tags",
    summary="Delete a collection tag",
    responses={204: {"description": "Tag removed"}, 403: {"model": ErrorResponse}},
)
def delete_collection_tag(
    collection_id: str,
    tag: str = Query(..., max_length=1024),
    account=Depends(require_auth),
    db=Depends(get_db),
):
    from urllib.parse import unquote

    collection = _resolve_collection_for_owner(db, collection_id, account["uuid"])
    target = unquote(tag)
    existing = db.tags(
        item_uri=collection["uri"],
        account_uuid=account["uuid"],
        limit=10000,
    )
    tags = [t["tag"] for t in existing]
    try:
        tags.remove(target)
    except ValueError as error:
        raise NotFoundError() from error
    if not db.update_item_list(
        collection["uuid"],
        account["uuid"],
        tags,
        "tags",
    ):
        raise InvalidInputError(
            f"Deleting tag '{target}' failed.",
            "DeleteFailed",
        )
    return Response(status_code=204)
