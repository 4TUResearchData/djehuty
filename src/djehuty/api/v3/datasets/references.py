"""Dataset reference endpoints for the v3 API."""

from fastapi import APIRouter, Body, Depends, Query, Response
from fastapi.responses import JSONResponse

from djehuty.api.dependencies import get_current_account, get_db, require_auth
from djehuty.api.exceptions import InvalidInputError
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
                "value": {"references": [{"url": "https://doi.org/10.1234/example"}]},
            }
        },
    ),
    account=Depends(require_auth),
    db=Depends(get_db),
):
    from djehuty.web import validator

    dataset = _resolve_dataset(db, dataset_id, account["uuid"])
    enforce_collaborative_permissions(db, account["uuid"], dataset, "dataset", "metadata_read")
    records = body.get("references")
    if not isinstance(records, list):
        raise InvalidInputError("Expected a 'references' field.", "NoReferencesField")
    new_urls: list[str] = []
    try:
        for record in records:
            new_urls.append(validator.string_value(record, "url", 0, 1024, True))
    except validator.ValidationException as error:
        raise InvalidInputError(error.message, error.code) from error

    existing = db.references(item_uri=dataset["uri"], account_uuid=account["uuid"])
    urls = [r["url"] for r in existing] + new_urls
    db.update_item_list(dataset["uuid"], account["uuid"], urls, "references")
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
