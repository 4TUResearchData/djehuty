"""Collection reference endpoints for the v3 API."""

from fastapi import APIRouter, Body, Depends, Query, Response
from fastapi.responses import JSONResponse

from djehuty.api.dependencies import get_db, require_auth
from djehuty.api.exceptions import InvalidInputError
from djehuty.api.models.common import ErrorResponse
from djehuty.api.v3._shared import _ok
from djehuty.api.v3.collections._shared import _resolve_collection_for_owner
from djehuty.web import formatter

router = APIRouter(tags=["V3 / Collections / References"])


@router.get(
    "/collections/{collection_id}/references",
    summary="List collection references",
    responses={
        200: _ok("The collection's references", ["https://doi.org/10.1234/example"]),
        403: {"model": ErrorResponse},
    },
)
def list_collection_references(
    collection_id: str,
    account=Depends(require_auth),
    db=Depends(get_db),
):
    collection = _resolve_collection_for_owner(db, collection_id, account["uuid"])
    refs = db.references(item_uri=collection["uri"], account_uuid=account["uuid"])
    return JSONResponse(content=[formatter.format_reference_record(r) for r in refs])


@router.post(
    "/collections/{collection_id}/references",
    summary="Add references to a collection",
    responses={205: {"description": "References added"}, 403: {"model": ErrorResponse}},
)
def add_collection_references(
    collection_id: str,
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

    collection = _resolve_collection_for_owner(db, collection_id, account["uuid"])
    records = body.get("references")
    if not isinstance(records, list):
        raise InvalidInputError("Expected a 'references' field.", "NoReferencesField")
    new_urls: list[str] = []
    try:
        for record in records:
            new_urls.append(validator.string_value(record, "url", 0, 1024, True))
    except validator.ValidationException as error:
        raise InvalidInputError(error.message, error.code) from error

    existing = db.references(item_uri=collection["uri"], account_uuid=account["uuid"])
    urls = [r["url"] for r in existing] + new_urls
    if not db.update_item_list(
        collection["uuid"],
        account["uuid"],
        urls,
        "references",
    ):
        raise InvalidInputError("Updating references failed.", "UpdateFailed")
    return Response(status_code=205)


@router.delete(
    "/collections/{collection_id}/references",
    summary="Delete a collection reference",
    responses={204: {"description": "Reference removed"}, 403: {"model": ErrorResponse}},
)
def delete_collection_reference(
    collection_id: str,
    url: str = Query(..., max_length=1024),
    account=Depends(require_auth),
    db=Depends(get_db),
):
    collection = _resolve_collection_for_owner(db, collection_id, account["uuid"])
    existing = db.references(item_uri=collection["uri"], account_uuid=account["uuid"])
    urls = [r["url"] for r in existing]
    # AS-IS: legacy removes the reference and 204s on success; an absent
    # reference or a failed update_item_list both fall through to a 500.
    if url in urls:
        urls.remove(url)
        if db.update_item_list(collection["uuid"], account["uuid"], urls, "references"):
            return Response(status_code=204)
    return Response(status_code=500)
