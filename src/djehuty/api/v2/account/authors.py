"""Authenticated /v2/account/authors endpoints (author search and details)."""

from fastapi import APIRouter, Body, Depends
from fastapi.responses import JSONResponse

from djehuty.api.dependencies import get_db, require_auth
from djehuty.api.exceptions import InvalidInputError, NotFoundError
from djehuty.web import formatter

router = APIRouter(prefix="/account", tags=["V2 / Account / Authors"])


@router.post(
    "/authors/search",
    summary="Search authors",
    description="Search for authors by name. Used for author autocomplete.",
)
def search_authors(
    body: dict = Body(
        ...,
        openapi_examples={
            "default": {
                "summary": "Search authors by name",
                "value": {"search": "Lovelace"},
            }
        },
    ),
    account=Depends(require_auth),
    db=Depends(get_db),
):
    from djehuty.web import validator

    # Legacy reads and validates ``search`` from the JSON body the same way
    # (wsgi.py api_private_authors_search), so the error code and message match.
    try:
        search_for = validator.string_value(body, "search", 0, 255, True)
    except validator.ValidationException as error:
        raise InvalidInputError(error.message, error.code) from error

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
