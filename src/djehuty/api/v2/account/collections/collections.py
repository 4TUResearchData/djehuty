"""Authenticated /v2/account/collections collections endpoints."""

from fastapi import APIRouter, Body, Depends, Response
from fastapi.responses import JSONResponse

from djehuty.api.dependencies import get_db, pagination_params, require_auth
from djehuty.api.exceptions import InvalidInputError, NotFoundError
from djehuty.api.models.collections import CollectionSearchRequest
from djehuty.api.services.collection_service import CollectionService
from djehuty.api.v2.account.collections._shared import _ok, _resolve_private_collection
from djehuty.web.config import config

router = APIRouter(tags=["V2 / Account / Collections"])


def _get_service(db=Depends(get_db)) -> CollectionService:
    return CollectionService(db)


@router.post(
    "/account/collections",
    status_code=200,
    summary="Create a new draft collection",
    responses={
        200: _ok(
            "Collection created",
            {
                "location": "https://data.4tu.nl/v2/account/collections/08b702d6-98a0-4081-9445-5aeae720cfa8"
            },
        )
    },
)
def create_collection(
    body: dict = Body(
        ...,
        openapi_examples={
            "minimal": {"summary": "Title only", "value": {"title": "Example collection"}}
        },
    ),
    account=Depends(require_auth),
    db=Depends(get_db),
):
    from djehuty.utils.convenience import value_or_none
    from djehuty.web import validator

    try:
        group_id = validator.integer_value(body, "group_id", 0, pow(2, 63), False)
        if group_id is None:
            acct = db.account_by_uuid(account["uuid"])
            group_id = value_or_none(acct, "group_id")

        publisher = validator.string_value(body, "publisher", 0, 255, False)
        if publisher is None:
            publisher = config.site_name

        timeline = validator.object_value(body, "timeline", False)
        container_uuid, _ = db.insert_collection(
            title=validator.string_value(body, "title", 3, 1000, True),
            account_uuid=account["uuid"],
            description=validator.string_value(
                body, "description", 0, 10000, False, strip_html=False
            ),
            funding=validator.string_value(body, "funding", 0, 255, False),
            funding_list=validator.array_value(body, "funding_list", False),
            datasets=validator.array_value(body, "articles", False),
            authors=validator.array_value(body, "authors", False),
            categories=validator.array_value(body, "categories", False),
            categories_by_source_id=validator.array_value(body, "categories_by_source_id", False),
            tags=validator.array_value(body, "tags", False),
            references=validator.array_value(body, "references", False),
            language=validator.string_value(body, "language", 0, 8, False),
            doi=validator.string_value(body, "doi", 0, 255, False),
            handle=validator.string_value(body, "handle", 0, 255, False),
            url=validator.string_value(body, "url", 0, 512, False),
            resource_id=validator.string_value(body, "resource_id", 0, 255, False),
            resource_doi=validator.string_value(body, "resource_doi", 0, 255, False),
            resource_link=validator.string_value(body, "resource_link", 0, 255, False),
            resource_title=validator.string_value(body, "resource_title", 0, 255, False),
            resource_version=validator.integer_value(
                body, "resource_version", 0, pow(2, 63), False
            ),
            group_id=group_id,
            publisher=publisher,
            custom_fields=validator.object_value(body, "custom_fields", False),
            custom_fields_list=validator.array_value(body, "custom_fields_list", False),
            publisher_publication=validator.string_value(timeline, "publisherPublication", False)
            if timeline
            else None,
            submission=validator.string_value(timeline, "submission", False) if timeline else None,
            posted=validator.string_value(timeline, "posted", False) if timeline else None,
            revision=validator.string_value(timeline, "revision", False) if timeline else None,
        )
        return JSONResponse(
            content={
                "location": f"{config.base_url}/v2/account/collections/{container_uuid}",
                "warnings": [],
            }
        )
    except validator.ValidationException as error:
        raise InvalidInputError(error.message, error.code)


@router.delete(
    "/account/collections/{collection_id}",
    summary="Delete a draft collection",
)
def delete_collection(
    collection_id: str,
    account=Depends(require_auth),
    db=Depends(get_db),
):
    collection = _resolve_private_collection(db, collection_id, account["uuid"])
    if not db.delete_collection_draft(collection["container_uuid"], account["uuid"]):
        raise InvalidInputError("Failed to delete collection.", "DeleteFailed")
    return Response(status_code=204)


@router.get(
    "/account/collections",
    summary="List own draft collections",
)
def list_private_collections(
    account=Depends(require_auth),
    service: CollectionService = Depends(_get_service),
    paging: dict = Depends(pagination_params),
):
    records = service.list_collections(
        limit=paging["limit"],
        offset=paging["offset"],
        is_latest=None,
        is_published=None,
        account_uuid=account["uuid"],
    )
    return JSONResponse(content=records)


@router.post(
    "/account/collections/search",
    summary="Search own collections",
)
def search_private_collections(
    body: CollectionSearchRequest,
    account=Depends(require_auth),
    service: CollectionService = Depends(_get_service),
):
    limit = body.limit or 10
    offset = body.offset or 0

    records, _ = service.search_collections(
        limit=limit,
        offset=offset,
        order=body.order,
        order_direction=body.order_direction,
        search_for=body.search_for,
        account_uuid=account["uuid"],
    )
    return JSONResponse(content=records)


@router.get(
    "/account/collections/{collection_id}",
    summary="Get own collection details",
)
def get_private_collection(
    collection_id: str,
    account=Depends(require_auth),
    service: CollectionService = Depends(_get_service),
):
    result = service.get_collection_details(
        collection_id,
        account_uuid=account["uuid"],
        is_latest=False,
        is_published=False,
    )
    if result is None:
        raise NotFoundError()
    return JSONResponse(content=result)


@router.put(
    "/account/collections/{collection_id}",
    summary="Update collection metadata",
)
def update_private_collection(
    collection_id: str,
    body: dict,
    account=Depends(require_auth),
    db=Depends(get_db),
):
    from djehuty.web import validator

    collection = _resolve_private_collection(db, collection_id, account["uuid"])
    try:
        result = db.update_collection(
            collection["uuid"],
            account["uuid"],
            title=validator.string_value(body, "title", 3, 1000, False),
            description=validator.string_value(
                body,
                "description",
                0,
                10000,
                False,
                strip_html=False,
            ),
            resource_doi=validator.string_value(body, "resource_doi", 0, 255, False),
            resource_title=validator.string_value(body, "resource_title", 0, 255, False),
            group_id=validator.integer_value(body, "group_id", 0, pow(2, 63), False),
            time_coverage=validator.string_value(body, "time_coverage", 0, 512, False),
            publisher=validator.string_value(body, "publisher", 0, 10000, False),
            language=validator.string_value(body, "language", 0, 10000, False),
            contributors=validator.string_value(body, "contributors", 0, 10000, False),
            geolocation=validator.string_value(body, "geolocation", 0, 255, False),
            longitude=validator.string_value(body, "longitude", 0, 64, False),
            latitude=validator.string_value(body, "latitude", 0, 64, False),
            organizations=validator.string_value(body, "organizations", 0, 2048, False),
            categories=validator.array_value(body, "categories", False),
        )
    except validator.ValidationException as error:
        raise InvalidInputError(error.message, error.code)

    if result is None:
        raise InvalidInputError("Failed to update collection.", "UpdateFailed")
    return Response(status_code=205)
