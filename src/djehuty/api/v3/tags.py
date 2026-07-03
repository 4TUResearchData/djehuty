"""Tag search endpoints for the v3 API."""

from fastapi import APIRouter, Body, Depends
from fastapi.responses import JSONResponse

from djehuty.api.dependencies import get_db
from djehuty.api.exceptions import InvalidInputError
from djehuty.api.models.common import ErrorResponse
from djehuty.api.v3._shared import _ok

router = APIRouter(tags=["V3 / Tags"])


@router.post(
    "/tags/search",
    summary="Search tags",
    responses={
        200: _ok("Matching tags", ["climate", "climatology"]),
        400: {"model": ErrorResponse},
    },
)
def search_tags(
    body: dict = Body(
        ...,
        openapi_examples={
            "default": {
                "summary": "Search previously used tags",
                "value": {"search_for": "climate"},
            }
        },
    ),
    db=Depends(get_db),
):
    # Legacy reads ``search_for`` from the JSON body (POST).
    search_for = body.get("search_for") if isinstance(body, dict) else None
    if not isinstance(search_for, str) or len(search_for) > 32:
        raise InvalidInputError(
            "Field 'search_for' is required and must be a string of <= 32 chars.",
            "BadSearchFor",
        )
    tags = db.previously_used_tags(search_for)
    tag_values = [item["tag"] if isinstance(item, dict) else item for item in tags]
    return JSONResponse(content=tag_values)
