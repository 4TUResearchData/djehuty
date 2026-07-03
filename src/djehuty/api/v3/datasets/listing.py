"""Public dataset listing and search endpoints for the v3 API."""

from fastapi import APIRouter, Body, Depends, Query
from fastapi.responses import JSONResponse

from djehuty.api.dependencies import get_db
from djehuty.api.models.articles import ArticleSearchRequest, ArticleSummary
from djehuty.api.models.common import ErrorResponse, OrderDirection, OrderField
from djehuty.api.services.article_service import ArticleService
from djehuty.api.v3._shared import _ok
from djehuty.utils.convenience import parse_search_terms

router = APIRouter(tags=["V3 / Datasets"])

_DATASET_SUMMARY_EXAMPLE = [
    {
        "id": None,
        "uuid": "27e6a01d-3f09-4d90-ae02-1d749ae9efb8",
        "title": "Coastal water temperature measurements",
        "doi": "10.4121/27e6a01d-3f09-4d90-ae02-1d749ae9efb8.v1",
        "handle": None,
        "url": "https://data.4tu.nl/v2/articles/27e6a01d-3f09-4d90-ae02-1d749ae9efb8",
        "published_date": "2026-07-03T10:48:50",
        "thumb": None,
        "defined_type": 3,
        "defined_type_name": "dataset",
        "group_id": 28586,
        "url_private_api": "https://data.4tu.nl/v2/account/articles/27e6a01d-3f09-4d90-ae02-1d749ae9efb8",
        "url_public_api": "https://data.4tu.nl/v2/articles/27e6a01d-3f09-4d90-ae02-1d749ae9efb8",
        "url_private_html": "https://data.4tu.nl/my/datasets/27e6a01d-3f09-4d90-ae02-1d749ae9efb8/edit",
        "url_public_html": "https://data.4tu.nl/datasets/27e6a01d-3f09-4d90-ae02-1d749ae9efb8/1",
        "timeline": {"posted": "2026-07-03T10:48:50", "firstOnline": None, "revision": None},
        "resource_title": None,
        "resource_doi": None,
    }
]

_DATASET_SEARCH_EXAMPLE = [
    {
        **_DATASET_SUMMARY_EXAMPLE[0],
        "authors": [
            {
                "id": None,
                "uuid": "07d6e6ce-b1bf-43ca-86e6-7a3ab8bc8416",
                "full_name": "Ada Lovelace",
                "is_active": True,
                "url_name": None,
                "orcid_id": "",
            }
        ],
    }
]


def _get_service(db=Depends(get_db)) -> ArticleService:
    return ArticleService(db)


def _parse_id_list(value: str | None) -> list[int] | None:
    """Parse a comma-separated string of IDs into a list of integers."""
    if value is None:
        return None
    return [int(v) for v in value.split(",") if v.strip()]


@router.get(
    "/datasets",
    response_model=list[ArticleSummary],
    summary="List public datasets",
    description=(
        "Returns a paginated list of published datasets. "
        "Supports filtering by categories, groups, institution, DOI, and more.\n\n"
        "Set `return_count=true` to get a count of matching datasets instead of the results."
    ),
    responses={
        200: _ok("List of datasets or count object", _DATASET_SUMMARY_EXAMPLE),
        400: {"model": ErrorResponse, "description": "Invalid parameters"},
    },
)
def list_datasets(
    service: ArticleService = Depends(_get_service),
    db=Depends(get_db),
    limit: int | None = Query(None, ge=1, le=1000),
    offset: int | None = Query(None, ge=0),
    order: OrderField = Query("published_date", description="Field to sort by"),
    order_direction: OrderDirection = Query("desc", description="Sort direction"),
    categories: str | None = Query(
        None, max_length=512, description="Comma-separated category IDs"
    ),
    group_ids: str | None = Query(None, max_length=512, description="Comma-separated group IDs"),
    doi: str | None = Query(None, max_length=255),
    handle: str | None = Query(None, max_length=255),
    institution: int | None = Query(None),
    item_type: int | None = Query(None),
    modified_since: str | None = Query(None, max_length=32, description="ISO 8601 date"),
    published_since: str | None = Query(None, max_length=32, description="ISO 8601 date"),
    resource_doi: str | None = Query(None, max_length=255),
    return_count: bool | None = Query(None, description="If true, return count instead of results"),
):
    from djehuty.web import formatter
    from djehuty.web.config import config

    records = db.datasets(
        limit=limit,
        offset=offset,
        order=order,
        order_direction=order_direction,
        categories=_parse_id_list(categories),
        groups=_parse_id_list(group_ids),
        doi=doi,
        handle=handle,
        institution=institution,
        item_type=item_type,
        modified_since=modified_since,
        published_since=published_since,
        resource_doi=resource_doi,
        return_count=return_count,
    )

    if return_count:
        return JSONResponse(content=records[0] if records else {"datasets": 0})

    formatted = [
        formatter.format_dataset_record({**r, "base_url": config.base_url}) for r in records
    ]
    return JSONResponse(content=formatted)


@router.post(
    "/datasets/search",
    response_model=list[ArticleSummary],
    summary="Search datasets",
    description=(
        "Search published datasets using full-text search with optional filters.\n\n"
        "Supports boolean operators (AND, OR) and field-specific search."
    ),
    responses={
        200: _ok("Search results", _DATASET_SEARCH_EXAMPLE),
        400: {"model": ErrorResponse, "description": "Invalid search parameters"},
    },
)
def search_datasets(
    body: ArticleSearchRequest = Body(
        ...,
        openapi_examples={
            "keyword": {
                "summary": "Full-text search",
                "value": {"search_for": "climate", "limit": 10},
            },
            "filtered": {
                "summary": "Search with filters",
                "value": {
                    "search_for": "ocean",
                    "group_id": 28586,
                    "categories": "13555",
                    "limit": 10,
                },
            },
        },
    ),
    service: ArticleService = Depends(_get_service),
):
    groups = [body.group] if body.group is not None else None
    cat_list = _parse_id_list(body.categories)

    if body.page is not None:
        effective_page_size = body.page_size if body.page_size is not None else 10
        limit = effective_page_size
        offset = (body.page - 1) * effective_page_size
    else:
        limit = body.limit if body.limit is not None else 10
        offset = body.offset if body.offset is not None else 0

    records, total_count = service.search_articles(
        limit=limit,
        offset=offset,
        order=body.order,
        order_direction=body.order_direction,
        categories=cat_list,
        doi=body.doi,
        handle=body.handle,
        groups=groups,
        institution=body.institution,
        item_type=body.item_type,
        modified_since=body.modified_since,
        published_since=body.published_since,
        resource_doi=body.resource_doi,
        search_for=parse_search_terms(body.search_for),
    )

    response = JSONResponse(content=records)
    if total_count is not None:
        response.headers["Number-Of-Records"] = str(total_count)
        response.headers["Number-Of-Returned-Records"] = str(len(records))
    return response
