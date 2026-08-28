"""Authenticated /v2/account/collections categories endpoints."""

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse

from djehuty.api.dependencies import get_db, require_auth
from djehuty.api.exceptions import InvalidInputError
from djehuty.api.services.request_lists import category_list_from_request_input
from djehuty.api.v2.account.collections._shared import _resolve_private_collection
from djehuty.web import formatter

router = APIRouter(tags=["V2 / Account / Collections / Categories"])


@router.get(
    "/account/collections/{collection_id}/categories",
    summary="List collection categories",
)
def list_collection_categories(
    collection_id: str, account=Depends(require_auth), db=Depends(get_db)
):
    collection = _resolve_private_collection(db, collection_id, account["uuid"])
    categories = db.categories(
        item_uri=collection["uri"], account_uuid=account["uuid"], is_published=False, limit=None
    )
    return JSONResponse(content=[formatter.format_category_record(c) for c in categories])


@router.post(
    "/account/collections/{collection_id}/categories",
    summary="Add categories",
)
@router.put(
    "/account/collections/{collection_id}/categories",
    summary="Replace categories",
)
def upsert_collection_categories(
    request: Request,
    collection_id: str,
    body: dict,
    account=Depends(require_auth),
    db=Depends(get_db),
):
    from djehuty.utils.rdf import uris_from_records

    if "categories" not in body:
        raise InvalidInputError("Expected an array for 'categories'.", "NoCategoriesField")
    if body["categories"] is None:
        raise InvalidInputError("Missing 'categories' parameter.", "MissingRequiredField")

    collection = _resolve_private_collection(db, collection_id, account["uuid"])
    records, errors = category_list_from_request_input(body, db)
    if errors:
        raise InvalidInputError(errors, "BadCategoriesInput")
    categories = [record["uuid"] for record in records if "uuid" in record]

    if request.method == "POST":
        existing = db.categories(
            item_uri=collection["uri"],
            account_uuid=account["uuid"],
            is_published=False,
            limit=None,
        )
        existing_uuids = [c["uuid"] for c in existing if "uuid" in c]
        categories = list(dict.fromkeys(existing_uuids + categories))

    uris = uris_from_records(categories, "category")
    if db.update_item_list(collection["uuid"], account["uuid"], uris, "categories"):
        return Response(status_code=205)
    raise InvalidInputError("Failed to update categories.", "UpdateFailed")


@router.delete(
    "/account/collections/{collection_id}/categories/{category_id}",
    summary="Remove category",
)
def delete_collection_category(
    collection_id: str, category_id: str, account=Depends(require_auth), db=Depends(get_db)
):
    from rdflib import URIRef

    from djehuty.utils.rdf import uuid_to_uri

    collection = _resolve_private_collection(db, collection_id, account["uuid"])
    try:
        category = (
            db.category_by_id(category_id=int(category_id))
            if category_id.isdigit()
            else db.category_by_id(category_uuid=category_id)
        )
        if category and "uuid" in category:
            db.delete_item_from_list(
                collection["uri"], "categories", URIRef(uuid_to_uri(category["uuid"], "category"))
            )
    except (TypeError, IndexError, KeyError):
        pass
    return Response(status_code=204)
