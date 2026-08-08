"""Authenticated /v2/account/articles embargo endpoints."""

from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse

from djehuty.api.dependencies import get_db, require_auth
from djehuty.api.v2.account.articles._shared import _ok, _resolve_private_dataset
from djehuty.web import formatter

router = APIRouter(prefix="/account", tags=["V2 / Account / Articles / Embargo"])


_EMBARGO_EXAMPLE = {
    "is_embargoed": False,
    "embargo_date": None,
    "embargo_type": "file",
    "embargo_title": "",
    "embargo_reason": "",
    "embargo_options": [],
}


@router.get(
    "/articles/{dataset_id}/embargo",
    summary="Get embargo details",
    responses={200: _ok("Embargo details", _EMBARGO_EXAMPLE)},
)
def get_article_embargo(dataset_id: str, account=Depends(require_auth), db=Depends(get_db)):
    dataset = _resolve_private_dataset(db, dataset_id, account["uuid"])
    return JSONResponse(content=formatter.format_dataset_embargo_record(dataset))


@router.delete(
    "/articles/{dataset_id}/embargo",
    summary="Delete embargo",
)
def delete_article_embargo(dataset_id: str, account=Depends(require_auth), db=Depends(get_db)):
    dataset = _resolve_private_dataset(db, dataset_id, account["uuid"])
    db.delete_dataset_embargo(dataset["uri"], account["uuid"])
    return Response(status_code=204)
