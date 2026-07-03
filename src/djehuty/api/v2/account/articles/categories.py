"""Authenticated /v2/account/articles categories endpoints."""

from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse

from djehuty.api.dependencies import get_db, require_auth
from djehuty.api.v2.account.articles._shared import _resolve_private_dataset
from djehuty.web import formatter

router = APIRouter(prefix="/account", tags=["V2 / Account / Articles / Categories"])


@router.get(
    "/articles/{dataset_id}/categories",
    summary="List article categories",
)
def list_article_categories(dataset_id: str, account=Depends(require_auth), db=Depends(get_db)):
    dataset = _resolve_private_dataset(db, dataset_id, account["uuid"])
    categories = db.categories(
        item_uri=dataset["uri"], account_uuid=account["uuid"], is_published=False, limit=None
    )
    return JSONResponse(content=[formatter.format_category_record(c) for c in categories])


@router.post(
    "/articles/{dataset_id}/categories",
    summary="Add categories",
)
@router.put(
    "/articles/{dataset_id}/categories",
    summary="Replace categories",
)
def upsert_article_categories(
    dataset_id: str, body: dict, account=Depends(require_auth), db=Depends(get_db)
):
    from djehuty.utils.rdf import uris_from_records

    dataset = _resolve_private_dataset(db, dataset_id, account["uuid"])
    input_categories = body.get("categories", [])

    new_cat_records = []
    for cat_id in input_categories:
        try:
            cat = (
                db.category_by_id(category_id=int(cat_id))
                if str(cat_id).isdigit()
                else db.category_by_id(category_uuid=str(cat_id))
            )
            if cat and "uuid" in cat:
                new_cat_records.append(cat)
        except (TypeError, IndexError, KeyError):
            pass

    existing = db.categories(
        item_uri=dataset["uri"], account_uuid=account["uuid"], is_published=False, limit=None
    )
    existing_uuids = {c["uuid"] for c in existing if "uuid" in c}
    combined = existing + [c for c in new_cat_records if c.get("uuid") not in existing_uuids]
    uris = uris_from_records(combined, "category", "uuid")
    db.update_item_list(dataset["uuid"], account["uuid"], uris, "categories")
    return Response(status_code=205)


@router.delete(
    "/articles/{dataset_id}/categories/{category_id}",
    summary="Remove a category",
)
def delete_article_category(
    dataset_id: str, category_id: str, account=Depends(require_auth), db=Depends(get_db)
):
    from rdflib import URIRef

    from djehuty.utils.rdf import uuid_to_uri

    dataset = _resolve_private_dataset(db, dataset_id, account["uuid"])
    try:
        cat = (
            db.category_by_id(category_id=int(category_id))
            if category_id.isdigit()
            else db.category_by_id(category_uuid=category_id)
        )
        if cat and "uuid" in cat:
            db.delete_item_from_list(
                dataset["uri"], "categories", URIRef(uuid_to_uri(cat["uuid"], "category"))
            )
    except (TypeError, IndexError, KeyError):
        pass
    return Response(status_code=204)
