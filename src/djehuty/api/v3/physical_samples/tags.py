"""Physical sample tag endpoints for the v3 API."""

from fastapi import APIRouter, Body, Depends, Query, Response
from fastapi.responses import JSONResponse

from djehuty.api.dependencies import get_db, require_auth
from djehuty.api.exceptions import InvalidInputError
from djehuty.api.models.common import ErrorResponse
from djehuty.api.permissions import enforce_collaborative_permissions
from djehuty.api.v3._shared import _ok
from djehuty.api.v3.physical_samples._shared import PhysicalSampleId, _resolve_physical_sample
from djehuty.web import formatter

router = APIRouter(tags=["V3 / Physical samples / Tags"])

_TAGS_EXAMPLE = ["basalt", "core sample", "north sea"]


def _resolve_for_tags(db, container_uuid, account_uuid):
    """Resolve the draft for a tag operation.

    AS-IS: a missing/unauthorized sample yields a 500 here — the legacy generic
    tag handler dereferences a None item's ``uri`` — rather than a 404.
    """
    item = _resolve_physical_sample(db, container_uuid, account_uuid, is_published=False)
    if item is None:
        return None
    enforce_collaborative_permissions(db, account_uuid, item, "physical-sample", "metadata_read")
    return item


@router.get(
    "/physical-samples/{container_uuid}/tags",
    summary="List a physical sample's tags",
    responses={200: _ok("The tags", _TAGS_EXAMPLE), 403: {"model": ErrorResponse}},
)
def list_tags(
    container_uuid: PhysicalSampleId,
    account=Depends(require_auth),
    db=Depends(get_db),
):
    item = _resolve_for_tags(db, container_uuid, account["uuid"])
    if item is None:
        return Response(status_code=500)
    tags = db.tags(item_uri=item["uri"], account_uuid=account["uuid"], limit=10000)
    return JSONResponse(content=[formatter.format_tag_record(t) for t in tags])


@router.post(
    "/physical-samples/{container_uuid}/tags",
    summary="Add tags to a physical sample",
    responses={205: {"description": "Tags added"}, 400: {"model": ErrorResponse}},
)
def add_tags(
    container_uuid: PhysicalSampleId,
    body: dict = Body(
        ...,
        openapi_examples={"default": {"value": {"tags": ["basalt", "core sample"]}}},
    ),
    account=Depends(require_auth),
    db=Depends(get_db),
):
    item = _resolve_for_tags(db, container_uuid, account["uuid"])
    if item is None:
        return Response(status_code=500)
    if not isinstance(body, dict) or "tags" not in body:
        raise InvalidInputError("Expected a 'tags' field.", "NoTagsField")

    new_tags = body["tags"]
    # Read the full existing list: update_item_list replaces it wholesale.
    existing = db.tags(item_uri=item["uri"], account_uuid=account["uuid"], limit=10000)
    existing_values = [formatter.format_tag_record(t) for t in existing]
    combined = list(dict.fromkeys(existing_values + new_tags))  # dedupe, preserve order
    if db.update_item_list(item["uuid"], account["uuid"], combined, "tags"):
        return Response(status_code=205)
    return Response(status_code=500)


@router.delete(
    "/physical-samples/{container_uuid}/tags",
    summary="Delete a tag",
    responses={204: {"description": "Tag removed"}, 403: {"model": ErrorResponse}},
)
def delete_tag(
    container_uuid: PhysicalSampleId,
    tag: str = Query(..., max_length=1024),
    account=Depends(require_auth),
    db=Depends(get_db),
):
    from requests.utils import unquote

    item = _resolve_for_tags(db, container_uuid, account["uuid"])
    if item is None:
        return Response(status_code=500)
    decoded_tag = unquote(tag)
    existing = db.tags(item_uri=item["uri"], account_uuid=account["uuid"], limit=10000)
    tag_values = [formatter.format_tag_record(t) for t in existing]
    # AS-IS: an absent tag or a failed update both fall through to a 500.
    if decoded_tag in tag_values:
        tag_values.remove(decoded_tag)
        if db.update_item_list(item["uuid"], account["uuid"], tag_values, "tags"):
            return Response(status_code=204)
    return Response(status_code=500)
