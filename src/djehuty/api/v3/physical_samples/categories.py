"""Physical sample category endpoints for the v3 API."""

from fastapi import APIRouter, Body, Depends, Response
from fastapi.responses import JSONResponse

from djehuty.api.dependencies import get_db, require_auth
from djehuty.api.exceptions import InvalidInputError, NotFoundError
from djehuty.api.models.common import ErrorResponse
from djehuty.api.permissions import enforce_collaborative_permissions
from djehuty.api.v3._shared import _ok
from djehuty.api.v3.physical_samples._shared import PhysicalSampleId, _resolve_physical_sample
from djehuty.web import formatter

router = APIRouter(tags=["V3 / Physical samples / Categories"])

_CATEGORY_EXAMPLE = {
    "id": 13555,
    "uuid": "a9f8d3c1-2b4e-4c6a-8d1f-3e5b7c9a0d2f",
    "title": "Geochemistry",
    "parent_id": 13537,
    "parent_uuid": None,
    "path": None,
    "source_id": None,
    "taxonomy_id": None,
}


@router.get(
    "/physical-samples/{container_uuid}/categories",
    summary="List a physical sample's categories",
    responses={200: _ok("The categories", [_CATEGORY_EXAMPLE]), 403: {"model": ErrorResponse}},
)
def list_categories(
    container_uuid: PhysicalSampleId,
    account=Depends(require_auth),
    db=Depends(get_db),
):
    item = _resolve_physical_sample(db, container_uuid, account["uuid"], is_published=False)
    # AS-IS: a missing sample dereferences a None item and yields a 500, not 404.
    if item is None:
        return Response(status_code=500)
    categories = db.categories(
        item_uri=item["uri"], account_uuid=account["uuid"], is_published=False, limit=None
    )
    return JSONResponse(content=[formatter.format_category_record(c) for c in categories])


def _set_categories(db, account_uuid, container_uuid, body, overwrite):
    """Validate and persist categories. POST appends, PUT overwrites."""
    from djehuty.utils.rdf import uris_from_records
    from djehuty.web import validator

    if not isinstance(body, dict) or "categories" not in body:
        raise InvalidInputError("Expected an array for 'categories'.", "NoCategoriesField")
    categories = body["categories"]
    if categories is None:
        raise InvalidInputError("Missing 'categories' parameter.", "MissingRequiredField")

    item = _resolve_physical_sample(db, container_uuid, account_uuid, is_published=False)
    if item is None:
        raise NotFoundError()
    enforce_collaborative_permissions(db, account_uuid, item, "physical-sample", "metadata_edit")

    try:
        # Validate every value first, so a PUT can never leave the item with no
        # categories: a UUID string passes as-is; a numeric id resolves to one.
        for index, _ in enumerate(categories):
            try:
                categories[index] = validator.string_value(categories, index, 0, 36)
            except validator.ValidationException:
                category_id = validator.integer_value(categories, index)
                category = db.category_by_id(category_id=category_id)
                if category is not None:
                    categories[index] = category["uuid"]

        if not overwrite:  # POST appends to the existing set.
            existing = db.categories(
                item_uri=item["uri"], account_uuid=account_uuid, is_published=False, limit=None
            )
            existing = [category["uuid"] for category in existing]
            categories = list(dict.fromkeys(existing + categories))

        categories = uris_from_records(categories, "category")
        if db.update_item_list(item["uuid"], account_uuid, categories, "categories"):
            return Response(status_code=205)
        return Response(status_code=500)
    except IndexError:
        return Response(status_code=500)
    except validator.ValidationException as error:
        raise InvalidInputError(error.message, error.code) from error


@router.post(
    "/physical-samples/{container_uuid}/categories",
    summary="Add categories to a physical sample",
    responses={205: {"description": "Categories added"}, 400: {"model": ErrorResponse}},
)
def add_categories(
    container_uuid: PhysicalSampleId,
    body: dict = Body(..., openapi_examples={"default": {"value": {"categories": [13555]}}}),
    account=Depends(require_auth),
    db=Depends(get_db),
):
    return _set_categories(db, account["uuid"], container_uuid, body, overwrite=False)


@router.put(
    "/physical-samples/{container_uuid}/categories",
    summary="Replace a physical sample's categories",
    responses={205: {"description": "Categories replaced"}, 400: {"model": ErrorResponse}},
)
def replace_categories(
    container_uuid: PhysicalSampleId,
    body: dict = Body(..., openapi_examples={"default": {"value": {"categories": [13555]}}}),
    account=Depends(require_auth),
    db=Depends(get_db),
):
    return _set_categories(db, account["uuid"], container_uuid, body, overwrite=True)
