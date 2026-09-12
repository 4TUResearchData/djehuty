"""Authenticated /v2/account/collections publishing endpoints."""

from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse

from djehuty.api.dependencies import get_db, require_auth
from djehuty.api.exceptions import ForbiddenError
from djehuty.api.v2.account.collections._shared import _find_collection
from djehuty.services import datacite

router = APIRouter(tags=["V2 / Account / Collections / Publishing"])


@router.post(
    "/account/collections/{collection_id}/reserve_doi",
    summary="Reserve DOI",
)
def reserve_collection_doi(collection_id: str, account=Depends(require_auth), db=Depends(get_db)):
    collection = _find_collection(db, collection_id, account["uuid"], is_published=False)
    if collection is None:
        raise ForbiddenError()

    data = datacite.datacite_reserve_doi(datacite.standard_doi(collection_id))
    if data is None:
        return Response(status_code=500)

    reserved_doi = data["data"]["id"]
    if db.update_collection(collection["uuid"], account["uuid"], doi=reserved_doi):
        return JSONResponse(content={"doi": reserved_doi})
    return Response(status_code=500)
