"""Authenticated /v2/account/collections authors endpoints."""

from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse

from djehuty.api.dependencies import get_db, require_auth
from djehuty.api.exceptions import InvalidInputError
from djehuty.api.v2.account.collections._shared import _resolve_private_collection
from djehuty.web import formatter

router = APIRouter(tags=["V2 / Account / Collections / Authors"])


@router.get(
    "/account/collections/{collection_id}/authors",
    summary="List collection authors",
)
def list_collection_authors(collection_id: str, account=Depends(require_auth), db=Depends(get_db)):
    collection = _resolve_private_collection(db, collection_id, account["uuid"])
    authors = db.authors(
        item_uri=collection["uri"],
        item_type="collection",
        account_uuid=account["uuid"],
        is_published=False,
        limit=10000,
    )
    return JSONResponse(content=[formatter.format_author_record(a) for a in authors])


@router.post(
    "/account/collections/{collection_id}/authors",
    summary="Add authors to collection",
)
@router.put(
    "/account/collections/{collection_id}/authors",
    summary="Replace collection authors",
)
def upsert_collection_authors(
    collection_id: str,
    body: dict,
    account=Depends(require_auth),
    db=Depends(get_db),
):
    from djehuty.utils.rdf import uris_from_records

    collection = _resolve_private_collection(db, collection_id, account["uuid"])
    input_authors = body.get("authors", [])
    if not isinstance(input_authors, list):
        raise InvalidInputError("Expected an 'authors' field.", "NoAuthorsField")

    new_author_uuids: list[str] = []
    for author_data in input_authors:
        if isinstance(author_data, dict) and author_data.get("uuid"):
            new_author_uuids.append(author_data["uuid"])
        elif isinstance(author_data, dict):
            first_name = author_data.get("first_name", "")
            last_name = author_data.get("last_name", "")
            author_uuid = db.insert_author(
                first_name=first_name,
                last_name=last_name,
                full_name=author_data.get("name") or f"{first_name} {last_name}".strip(),
                email=author_data.get("email"),
                orcid_id=author_data.get("orcid_id"),
            )
            if author_uuid:
                new_author_uuids.append(author_uuid)

    existing = db.authors(
        item_uri=collection["uri"],
        item_type="collection",
        account_uuid=account["uuid"],
        is_published=False,
        limit=10000,
    )
    existing_uuids = [a["uuid"] for a in existing if "uuid" in a]

    combined = existing_uuids + [u for u in new_author_uuids if u not in existing_uuids]
    combined_records = [{"uuid": u} for u in combined]
    uris = uris_from_records(combined_records, "author", "uuid")
    if not db.update_item_list(collection["uuid"], account["uuid"], uris, "authors"):
        raise InvalidInputError("Failed to update authors.", "UpdateFailed")
    return Response(status_code=205)


@router.delete(
    "/account/collections/{collection_id}/authors/{author_id}",
    summary="Remove author",
)
def delete_collection_author(
    collection_id: str, author_id: str, account=Depends(require_auth), db=Depends(get_db)
):
    from rdflib import URIRef

    from djehuty.utils.convenience import parses_to_int
    from djehuty.utils.rdf import uuid_to_uri

    collection = _resolve_private_collection(db, collection_id, account["uuid"])
    authors = db.authors(
        item_uri=collection["uri"],
        account_uuid=account["uuid"],
        is_published=False,
        item_type="collection",
        limit=10000,
    )
    try:
        if parses_to_int(author_id):
            authors.remove(next(filter(lambda item: item["id"] == author_id, authors)))
        else:
            authors.remove(next(filter(lambda item: item["uuid"] == author_id, authors)))
    except (StopIteration, KeyError):
        return Response(status_code=500)

    uris = [URIRef(uuid_to_uri(author["uuid"], "author")) for author in authors]
    if db.update_item_list(collection["uuid"], account["uuid"], uris, "authors"):
        return Response(status_code=204)
    return Response(status_code=500)
