"""Dataset tag endpoints for the v3 API."""

from fastapi import APIRouter, Body, Depends, Query, Response
from fastapi.responses import JSONResponse

from djehuty.api.dependencies import get_current_account, get_db, require_auth
from djehuty.api.models.common import ErrorResponse
from djehuty.api.permissions import enforce_collaborative_permissions
from djehuty.api.v3._shared import _ok
from djehuty.api.v3.datasets._shared import _resolve_any_dataset, _resolve_dataset
from djehuty.web import formatter

router = APIRouter(tags=["V3 / Datasets / Tags"])

_TAGS_EXAMPLE = ["climate", "oceanography"]


@router.get(
    "/datasets/{dataset_id}/tags",
    summary="List dataset tags",
    responses={200: _ok("The dataset's tags", _TAGS_EXAMPLE)},
)
def list_tags(
    dataset_id: str, db=Depends(get_db), account: dict | None = Depends(get_current_account)
):
    dataset = _resolve_any_dataset(db, dataset_id, account)
    if account:
        enforce_collaborative_permissions(db, account["uuid"], dataset, "dataset", "metadata_read")
    tags = db.tags(item_uri=dataset["uri"])
    return JSONResponse(content=[formatter.format_tag_record(t) for t in tags])


@router.post(
    "/datasets/{dataset_id}/tags",
    summary="Add tags",
    responses={205: {"description": "Tags added"}, 403: {"model": ErrorResponse}},
)
def add_tags(
    dataset_id: str,
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
    dataset = _resolve_dataset(db, dataset_id, account["uuid"])
    enforce_collaborative_permissions(db, account["uuid"], dataset, "dataset", "metadata_read")
    new_tags = body.get("tags", [])
    # Read the full existing list: update_item_list replaces it wholesale, so a
    # truncated read (the default limit=10) would silently drop tags 11+.
    existing = db.tags(item_uri=dataset["uri"], account_uuid=account["uuid"], limit=10000)
    existing_values = [formatter.format_tag_record(t) for t in existing]
    combined = list(dict.fromkeys(existing_values + new_tags))  # deduplicate preserving order
    db.update_item_list(dataset["uuid"], account["uuid"], combined, "tags")
    return Response(status_code=205)


@router.delete(
    "/datasets/{dataset_id}/tags",
    summary="Delete a tag",
    responses={204: {"description": "Tag removed"}, 403: {"model": ErrorResponse}},
)
def delete_tag(
    dataset_id: str,
    tag: str = Query(..., max_length=1024),
    account=Depends(require_auth),
    db=Depends(get_db),
):
    from requests.utils import unquote

    dataset = _resolve_dataset(db, dataset_id, account["uuid"])
    enforce_collaborative_permissions(db, account["uuid"], dataset, "dataset", "metadata_read")
    decoded_tag = unquote(tag)
    # Read the full existing list before writing it back (see the add path).
    existing = db.tags(item_uri=dataset["uri"], account_uuid=account["uuid"], limit=10000)
    tag_values = [formatter.format_tag_record(t) for t in existing]
    if decoded_tag in tag_values:
        tag_values.remove(decoded_tag)
        db.update_item_list(dataset["uuid"], account["uuid"], tag_values, "tags")
    return Response(status_code=204)
