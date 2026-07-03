"""Authenticated /v2/account/authors endpoints (author search and details)."""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from djehuty.api.dependencies import get_db, require_auth
from djehuty.api.exceptions import InvalidInputError, NotFoundError
from djehuty.web import formatter

router = APIRouter(prefix="/account", tags=["V2 / Account / Authors"])


@router.post(
    "/authors/search",
    summary="Search authors",
    description="Search for authors by name. Used for author autocomplete. Admin-only.",
)
def search_authors(
    body: dict,
    account=Depends(require_auth),
    db=Depends(get_db),
):
    # Legacy gates this behind may_administer and reads ``search`` from the
    # JSON body (POST).
    search_for = body.get("search") if isinstance(body, dict) else None
    if not isinstance(search_for, str) or len(search_for) > 255:
        raise InvalidInputError(
            "Field 'search' is required and must be a string of <= 255 chars.",
            "BadSearch",
        )

    records = db.authors(search_for=search_for, limit=10)
    return JSONResponse(content=[formatter.format_author_details_record(r) for r in records])


@router.get(
    "/authors/{author_id}",
    summary="Get author details",
)
def get_author(
    author_id: str,
    account=Depends(require_auth),
    db=Depends(get_db),
):
    author = db.authors(author_uuid=author_id)
    if not author:
        raise NotFoundError()
    return JSONResponse(content=formatter.format_author_details_record(author[0]))
