"""Authenticated /v2/account/collections authors endpoints."""

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse

from djehuty.api.dependencies import get_db, require_auth
from djehuty.api.exceptions import InvalidInputError
from djehuty.api.services.request_lists import author_list_from_request_input
from djehuty.api.v2.account.collections._shared import _resolve_private_collection
from djehuty.web import formatter, validator

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
    request: Request,
    account=Depends(require_auth),
    db=Depends(get_db),
):
    from djehuty.utils.rdf import uris_from_records

    collection = _resolve_private_collection(db, collection_id, account["uuid"])

    try:
        new_authors, errors = author_list_from_request_input(body, db, account["uuid"])
    except validator.ValidationException as error:
        raise InvalidInputError(error.message, error.code) from error

    if errors:
        raise InvalidInputError(errors, "BadAuthorsInput")

    # POST appends to existing authors; PUT replaces.
    existing_authors = []
    if request.method == "POST":
        existing = db.authors(
            item_uri=collection["uri"],
            item_type="collection",
            account_uuid=account["uuid"],
            is_published=False,
            limit=10000,
        )
        existing_authors = uris_from_records(
            [a for a in existing if "uuid" in a],
            "author",
            "uuid",
        )

    authors = list(dict.fromkeys(existing_authors + new_authors))
    if not db.update_item_list(collection["uuid"], account["uuid"], authors, "authors"):
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
