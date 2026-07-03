"""Dataset statistics endpoints for the v3 API."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from djehuty.api.dependencies import get_db
from djehuty.api.exceptions import InvalidInputError
from djehuty.api.models.common import ErrorResponse
from djehuty.api.v3._shared import _ok

router = APIRouter(tags=["V3 / Statistics"])

_TOP_EXAMPLE = [
    {
        "container_uuid": "27e6a01d-3f09-4d90-ae02-1d749ae9efb8",
        "dataset_id": 12873,
        "title": "Coastal water temperature measurements",
        "downloads": 4567,
        "figshare_url": "https://data.4tu.nl/articles/27e6a01d-3f09-4d90-ae02-1d749ae9efb8",
    }
]

_TIMELINE_EXAMPLE = [
    {"dataset_id": 12873, "date": "2026-05", "views": 214},
    {"dataset_id": 12873, "date": "2026-06", "views": 189},
]


def _datasets_parameters(args, item_type):
    """Faithful port of the legacy __api_v3_datasets_parameters helper."""
    from djehuty.utils.convenience import split_string
    from djehuty.web import validator

    record = {
        "dataset_id": validator.integer_value(args.get("id"), None),
        "limit": validator.integer_value(args.get("limit"), None),
        "offset": validator.integer_value(args.get("offset"), None),
        "order": validator.string_value(args.get("order"), None, maximum_length=32),
        "order_direction": validator.order_direction(args.get("order_direction"), None),
        "categories": validator.string_value(args.get("categories"), None, maximum_length=512),
        "group_ids": validator.string_value(args.get("group_ids"), None, maximum_length=512),
    }

    if item_type not in {"downloads", "views", "shares", "cites"}:
        raise validator.InvalidValue(
            field_name="item_type",
            message=(
                "The last URL parameter must be one of 'downloads', 'views', 'shares' or 'cites'."
            ),
            code="InvalidURLParameterValue",
        )

    record["categories"] = split_string(record["categories"], delimiter=",")
    if record["categories"] is not None:
        for index, _ in enumerate(record["categories"]):
            record["categories"][index] = validator.integer_value(record["categories"], index)

    record["group_ids"] = split_string(record["group_ids"], delimiter=",")
    if record["group_ids"] is not None:
        for index, _ in enumerate(record["group_ids"]):
            record["group_ids"][index] = validator.integer_value(record["group_ids"], index)

    return record


@router.get(
    "/datasets/top/{item_type}",
    summary="Get top datasets by type",
    responses={
        200: _ok("Top datasets for the requested metric", _TOP_EXAMPLE),
        400: {"model": ErrorResponse, "description": "Invalid parameters"},
    },
)
def datasets_top(item_type: str, request: Request, db=Depends(get_db)):
    from djehuty.web import validator

    args = request.query_params
    try:
        record = _datasets_parameters(args, item_type)
    except validator.ValidationException as error:
        raise InvalidInputError(error.message, error.code) from error

    offset, limit = validator.paging_to_offset_and_limit(
        {
            "page": args.get("page"),
            "page_size": args.get("page_size"),
            "limit": args.get("limit"),
            "offset": args.get("offset"),
        }
    )
    if "group_ids" in record and record["group_ids"] is not None and record["group_ids"] != "":
        validator.array_value(record, "group_ids")
        for index, _ in enumerate(record["group_ids"]):
            record["group_ids"][index] = validator.integer_value(record["group_ids"], index)

    records = db.dataset_statistics(
        limit=limit,
        offset=offset,
        order=validator.string_value(args, "order", 0, 255),
        order_direction=validator.order_direction(args, "order_direction"),
        group_ids=record["group_ids"],
        category_ids=record["categories"],
        item_type=item_type,
    )
    return JSONResponse(content=records)


@router.get(
    "/datasets/timeline/{item_type}",
    summary="Get dataset timeline",
    responses={
        200: _ok("Time-series counts for the requested metric", _TIMELINE_EXAMPLE),
        400: {"model": ErrorResponse, "description": "Invalid parameters"},
    },
)
def datasets_timeline(item_type: str, request: Request, db=Depends(get_db)):
    from djehuty.web import validator

    try:
        record = _datasets_parameters(request.query_params, item_type)
    except validator.ValidationException as error:
        raise InvalidInputError(error.message, error.code) from error

    records = db.dataset_statistics_timeline(
        dataset_id=record["dataset_id"],
        limit=record["limit"],
        offset=record["offset"],
        order=record["order"],
        order_direction=record["order_direction"],
        category_ids=record["categories"],
        item_type=item_type,
    )
    return JSONResponse(content=records)
