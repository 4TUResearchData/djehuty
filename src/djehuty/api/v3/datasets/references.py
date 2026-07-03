"""Dataset reference endpoints for the v3 API."""

from fastapi import APIRouter, Body, Depends, Query, Response
from fastapi.responses import JSONResponse

from djehuty.api.dependencies import get_current_account, get_db, require_auth
from djehuty.api.models.common import ErrorResponse
from djehuty.api.permissions import enforce_collaborative_permissions
from djehuty.api.v3._shared import _ok
from djehuty.api.v3.datasets._shared import _resolve_any_dataset, _resolve_dataset
from djehuty.web import formatter

router = APIRouter(tags=["V3 / Datasets / References"])

_REFERENCES_EXAMPLE = ["https://doi.org/10.1234/example"]


@router.get(
    "/datasets/{dataset_id}/references",
    summary="List dataset references",
    responses={200: _ok("The dataset's references", _REFERENCES_EXAMPLE)},
)
def list_references(
    dataset_id: str, db=Depends(get_db), account: dict | None = Depends(get_current_account)
):
    dataset = _resolve_any_dataset(db, dataset_id, account)
    if account:
        enforce_collaborative_permissions(db, account["uuid"], dataset, "dataset", "metadata_read")
    refs = db.references(item_uri=dataset["uri"])
    return JSONResponse(content=[formatter.format_reference_record(r) for r in refs])


@router.post(
    "/datasets/{dataset_id}/references",
    summary="Add references",
    responses={205: {"description": "References added"}, 403: {"model": ErrorResponse}},
)
def add_references(
    dataset_id: str,
    body: dict = Body(
        ...,
        openapi_examples={
            "default": {
                "summary": "Add reference URLs",
                "value": {"references": ["https://doi.org/10.1234/example"]},
            }
        },
    ),
    account=Depends(require_auth),
    db=Depends(get_db),
):
    dataset = _resolve_dataset(db, dataset_id, account["uuid"])
    enforce_collaborative_permissions(db, account["uuid"], dataset, "dataset", "metadata_read")
    new_refs = body.get("references", [])
    existing = db.references(item_uri=dataset["uri"], account_uuid=account["uuid"])
    existing_urls = [r.get("url", "") for r in existing]
    combined = existing_urls + [
        r.get("url", r) if isinstance(r, dict) else r
        for r in new_refs
        if (r.get("url", r) if isinstance(r, dict) else r) not in existing_urls
    ]
    db.update_item_list(dataset["uuid"], account["uuid"], combined, "references")
    return Response(status_code=205)


@router.delete(
    "/datasets/{dataset_id}/references",
    summary="Delete a reference",
    responses={204: {"description": "Reference removed"}, 403: {"model": ErrorResponse}},
)
def delete_reference(
    dataset_id: str,
    url: str = Query(..., max_length=1024),
    account=Depends(require_auth),
    db=Depends(get_db),
):
    from requests.utils import unquote

    dataset = _resolve_dataset(db, dataset_id, account["uuid"])
    enforce_collaborative_permissions(db, account["uuid"], dataset, "dataset", "metadata_read")
    decoded_url = unquote(url)
    existing = db.references(item_uri=dataset["uri"], account_uuid=account["uuid"])
    urls = [r.get("url", "") for r in existing]
    if decoded_url in urls:
        urls.remove(decoded_url)
        db.update_item_list(dataset["uuid"], account["uuid"], urls, "references")
    return Response(status_code=204)
