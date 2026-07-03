"""Institutional group endpoints for the v3 API."""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from djehuty.api.dependencies import get_db
from djehuty.api.exceptions import InvalidInputError
from djehuty.api.models.common import ErrorResponse
from djehuty.api.v3._shared import _ok
from djehuty.web import formatter

router = APIRouter(tags=["V3 / Groups"])

_GROUPS_EXAMPLE = [
    {
        "id": 28585,
        "parent_id": 0,
        "name": "4TU.ResearchData",
        "association": "4tu.nl",
        "is_featured": False,
    },
    {
        "id": 28586,
        "parent_id": 28585,
        "name": "Delft University of Technology",
        "association": "tudelft.nl",
        "is_featured": True,
    },
]


@router.get(
    "/groups",
    summary="List institutional groups",
    responses={
        200: _ok("Institutional groups", _GROUPS_EXAMPLE),
        400: {"model": ErrorResponse},
    },
)
def list_groups(
    db=Depends(get_db),
    id: str | None = Query(None),
    parent_id: str | None = Query(None),
    name: str | None = Query(None),
    association: str | None = Query(None),
    is_featured: str | None = Query(None),
    limit: str | None = Query(None),
    offset: str | None = Query(None),
    order: str | None = Query(None),
    order_direction: str | None = Query(None),
):
    from djehuty.web import validator

    args = {
        "id": id,
        "parent_id": parent_id,
        "name": name,
        "association": association,
        "is_featured": is_featured,
        "limit": limit,
        "offset": offset,
        "order": order,
        "order_direction": order_direction,
    }
    try:
        # AS-IS: legacy validates `order` as an integer, so a textual order
        # field is rejected with 400.
        records = db.group(
            group_id=validator.integer_value(args, "id"),
            parent_id=validator.integer_value(args, "parent_id"),
            name=validator.string_value(args, "name", 0, 255),
            association=validator.string_value(args, "association", 0, 255),
            is_featured=validator.boolean_value(args, "is_featured"),
            limit=validator.integer_value(args, "limit"),
            offset=validator.integer_value(args, "offset"),
            order=validator.integer_value(args, "order"),
            order_direction=validator.order_direction(args, "order_direction"),
        )
        return JSONResponse(content=[formatter.format_group_record(r) for r in records])
    except validator.ValidationException as error:
        raise InvalidInputError(error.message, error.code) from error
