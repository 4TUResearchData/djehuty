"""Authenticated /v2/account/collections funding endpoints."""

from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse

from djehuty.api.dependencies import get_db, require_auth
from djehuty.api.exceptions import NotFoundError
from djehuty.api.v2.account.collections._shared import _resolve_private_collection
from djehuty.web import formatter

router = APIRouter(tags=["V2 / Account / Collections / Funding"])


@router.get(
    "/account/collections/{collection_id}/funding",
    summary="List funding",
)
def list_collection_funding(collection_id: str, account=Depends(require_auth), db=Depends(get_db)):
    collection = _resolve_private_collection(db, collection_id, account["uuid"])
    fundings = db.fundings(
        item_uri=collection["uri"],
        item_type="collection",
        account_uuid=account["uuid"],
        is_published=False,
    )
    return JSONResponse(content=[formatter.format_funding_record(f) for f in fundings])


@router.delete(
    "/account/collections/{collection_id}/funding/{funding_id}",
    summary="Remove funding",
)
def delete_collection_funding(
    collection_id: str, funding_id: str, account=Depends(require_auth), db=Depends(get_db)
):
    from rdflib import URIRef

    from djehuty.utils.rdf import uuid_to_uri

    collection = _resolve_private_collection(db, collection_id, account["uuid"])
    fundings = db.fundings(
        item_uri=collection["uri"],
        account_uuid=account["uuid"],
        is_published=False,
        item_type="collection",
        limit=10000,
    )
    if not fundings:
        raise NotFoundError()
    try:
        fundings.remove(next(filter(lambda item: item["uuid"] == funding_id, fundings)))
    except (StopIteration, KeyError):
        return Response(status_code=500)

    uris = [URIRef(uuid_to_uri(funding["uuid"], "funding")) for funding in fundings]
    if db.update_item_list(collection["uuid"], account["uuid"], uris, "funding_list"):
        return Response(status_code=204)
    return Response(status_code=500)
