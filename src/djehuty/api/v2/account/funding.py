"""Authenticated /v2/account/funding endpoints (funding search)."""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from djehuty.api.dependencies import get_db, require_auth
from djehuty.api.exceptions import InvalidInputError
from djehuty.web import formatter

router = APIRouter(prefix="/account", tags=["V2 / Account / Funding"])


@router.post(
    "/funding/search",
    summary="Search funding",
)
def search_funding(
    body: dict,
    account=Depends(require_auth),
    db=Depends(get_db),
):
    # Legacy reads ``search`` from the JSON body (POST), not the query string.
    search_for = body.get("search") if isinstance(body, dict) else None
    if not isinstance(search_for, str) or len(search_for) > 255:
        raise InvalidInputError(
            "Field 'search' is required and must be a string of <= 255 chars.",
            "BadSearch",
        )
    records = db.fundings(search_for=search_for)
    return JSONResponse(content=[formatter.format_funding_record(r) for r in records])
