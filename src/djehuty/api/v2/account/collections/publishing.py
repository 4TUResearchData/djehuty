"""Authenticated /v2/account/collections publishing endpoints."""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from djehuty.api.dependencies import get_db, require_auth
from djehuty.api.exceptions import InvalidInputError
from djehuty.api.v2.account.collections._shared import _resolve_private_collection

router = APIRouter(tags=["V2 / Account / Collections / Publishing"])


@router.post(
    "/account/collections/{collection_id}/reserve_doi",
    summary="Reserve DOI",
)
def reserve_collection_doi(collection_id: str, account=Depends(require_auth), db=Depends(get_db)):
    collection = _resolve_private_collection(db, collection_id, account["uuid"])
    doi = db.reserve_doi(collection["uri"], account["uuid"], item_type="collection")
    if doi is None:
        raise InvalidInputError("Failed to reserve DOI.", "ReserveFailed")
    return JSONResponse(content={"doi": doi})
