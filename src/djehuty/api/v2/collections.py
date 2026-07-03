"""Public and private collection endpoints for the v2 API."""

from fastapi import APIRouter, Body, Depends, Query
from fastapi.responses import JSONResponse

from djehuty.api.dependencies import get_db, pagination_params
from djehuty.api.exceptions import NotFoundError
from djehuty.api.models.collections import CollectionSearchRequest, CollectionSummary
from djehuty.api.models.common import OrderDirection, OrderField
from djehuty.api.services.collection_service import CollectionService

router = APIRouter(tags=["V2 / Collections"])

# Example payloads for the OpenAPI docs, based on doc/api.tex (v2 API reference).
_COLLECTION_SUMMARY_EXAMPLE = {
    "id": None,
    "uuid": "07a08d2a-1f7f-4e2b-8c9a-4d5e6f7a8b9c",
    "title": "4TU.ResearchData featured datasets",
    "doi": "10.4121/c.6453243.v3",
    "handle": None,
    "url": "https://data.4tu.nl/v2/collections/07a08d2a-1f7f-4e2b-8c9a-4d5e6f7a8b9c",
    "published_date": "2024-05-14T09:12:03",
    "timeline": {"posted": "2024-05-14T09:12:03"},
}

_COLLECTION_VERSIONS_EXAMPLE = [
    {
        "version": 3,
        "url": "https://data.4tu.nl/v2/collections/07a08d2a-1f7f-4e2b-8c9a-4d5e6f7a8b9c/versions/3",
    },
    {
        "version": 2,
        "url": "https://data.4tu.nl/v2/collections/07a08d2a-1f7f-4e2b-8c9a-4d5e6f7a8b9c/versions/2",
    },
]

_COLLECTION_DETAIL_EXAMPLE = {
    **_COLLECTION_SUMMARY_EXAMPLE,
    "version": 3,
    "description": "<p>A curated collection of featured datasets.</p>",
    "categories": [
        {
            "id": 13622,
            "uuid": "01fddd41-68d2-4e28-9d9c-18347847e7d1",
            "title": "Mining and Extraction of Energy Resources",
        }
    ],
    "references": [],
    "tags": ["featured"],
    "created_date": "2024-05-14T09:12:03",
    "modified_date": "2024-05-14T09:12:03",
}


def _ok(description, example):
    """Build a 200-response entry carrying an OpenAPI example."""
    return {"description": description, "content": {"application/json": {"example": example}}}


def _get_service(db=Depends(get_db)) -> CollectionService:
    return CollectionService(db)


# --- Public endpoints ---


@router.get(
    "/collections",
    response_model=list[CollectionSummary],
    summary="List public collections",
    responses={200: _ok("List of collections", [_COLLECTION_SUMMARY_EXAMPLE])},
)
def list_collections(
    service: CollectionService = Depends(_get_service),
    paging: dict = Depends(pagination_params),
    order: OrderField = Query("published_date"),
    order_direction: OrderDirection = Query("desc"),
):
    records = service.list_collections(
        limit=paging["limit"],
        offset=paging["offset"],
        order=order,
        order_direction=order_direction,
    )
    return JSONResponse(content=records)


@router.post(
    "/collections/search",
    response_model=list[CollectionSummary],
    summary="Search collections",
)
def search_collections(
    body: CollectionSearchRequest = Body(
        ...,
        openapi_examples={
            "keyword": {"summary": "Search for a keyword", "value": {"search_for": "climate"}},
        },
    ),
    service: CollectionService = Depends(_get_service),
):
    limit = body.limit or 10
    offset = body.offset or 0
    if body.page is not None:
        ps = body.page_size or 10
        limit, offset = ps, (body.page - 1) * ps

    records, _ = service.search_collections(
        limit=limit,
        offset=offset,
        order=body.order,
        order_direction=body.order_direction,
        search_for=body.search_for,
    )
    return JSONResponse(content=records)


@router.get(
    "/collections/{collection_id}",
    summary="Get collection details",
    responses={200: _ok("Collection details", _COLLECTION_DETAIL_EXAMPLE)},
)
def get_collection(collection_id: str, service: CollectionService = Depends(_get_service)):
    result = service.get_collection_details(collection_id)
    if result is None:
        raise NotFoundError()
    return JSONResponse(content=result)


@router.get(
    "/collections/{collection_id}/versions",
    summary="List collection versions",
    responses={200: _ok("List of versions", _COLLECTION_VERSIONS_EXAMPLE)},
)
def list_collection_versions(
    collection_id: str, service: CollectionService = Depends(_get_service)
):
    details = service.get_collection_details(collection_id)
    if details is None:
        raise NotFoundError()
    versions = service.get_collection_versions(details["uuid"])
    return JSONResponse(content=versions)


@router.get(
    "/collections/{collection_id}/versions/{version}",
    summary="Get collection version",
)
def get_collection_version(
    collection_id: str, version: int, service: CollectionService = Depends(_get_service)
):
    details = service.get_collection_details(collection_id, is_latest=False)
    if details is None:
        raise NotFoundError()
    return JSONResponse(content=details)


@router.get(
    "/collections/{collection_id}/articles",
    summary="List collection articles",
)
def list_collection_articles(
    collection_id: str,
    service: CollectionService = Depends(_get_service),
    paging: dict = Depends(pagination_params),
):
    datasets = service.get_collection_datasets(
        collection_id, limit=paging["limit"], offset=paging["offset"]
    )
    if datasets is None:
        raise NotFoundError()
    return JSONResponse(content=datasets)
