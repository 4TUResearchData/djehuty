"""Data model explorer endpoints for the v3 API."""

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import JSONResponse

from djehuty.api.dependencies import get_db, require_admin
from djehuty.api.models.common import ErrorResponse
from djehuty.api.v3._shared import _ok

router = APIRouter(tags=["V3 / Explore"])

_TYPES_EXAMPLE = [
    "https://ontologies.data.4tu.nl/djehuty/0.0.1/Dataset",
    "https://ontologies.data.4tu.nl/djehuty/0.0.1/Author",
    "https://ontologies.data.4tu.nl/djehuty/0.0.1/Category",
]


@router.get(
    "/explore/types",
    summary="List data model types",
    responses={200: _ok("RDF type URIs", _TYPES_EXAMPLE), 403: {"model": ErrorResponse}},
)
def explore_types(account=Depends(require_admin), db=Depends(get_db)):
    types = db.types()
    return JSONResponse(content=[t["type"] for t in types])


@router.get(
    "/explore/properties",
    summary="List data model properties",
    responses={
        200: _ok(
            "Predicate URIs for the given type",
            ["https://ontologies.data.4tu.nl/djehuty/0.0.1/title"],
        ),
        403: {"model": ErrorResponse},
    },
)
def explore_properties(
    uri: str = Query(None, max_length=255),
    account=Depends(require_admin),
    db=Depends(get_db),
):
    from urllib.parse import unquote

    # AS-IS (#111): legacy unquotes the `uri` parameter unconditionally; when it
    # is absent the value is None and unquote(None) raises TypeError, which the
    # handler's `except ValidationException` does not catch -> uncaught -> 500.
    properties = db.properties_for_type(unquote(uri))
    return JSONResponse(content=[p["predicate"] for p in properties])


@router.get(
    "/explore/property_value_types",
    summary="List property value types",
    responses={
        200: _ok(
            "Value type URIs for the given property", ["http://www.w3.org/2001/XMLSchema#string"]
        ),
        403: {"model": ErrorResponse},
    },
)
def explore_property_value_types(
    type: str = Query(None, max_length=255),
    property: str = Query(None, max_length=255),
    account=Depends(require_admin),
    db=Depends(get_db),
):
    from urllib.parse import unquote

    # AS-IS (#111): legacy unquotes `type`/`property` unconditionally; when they
    # are absent the values are None and unquote(None) raises TypeError, which
    # the handler's `except ValidationException` does not catch -> 500.
    types = db.types_for_property(unquote(type), unquote(property))
    return JSONResponse(content=[t["type"] for t in types])


@router.get(
    "/explore/clear-cache",
    summary="Clear explorer cache",
    responses={204: {"description": "Explorer cache cleared"}, 403: {"model": ErrorResponse}},
)
def explore_clear_cache(account=Depends(require_admin), db=Depends(get_db)):
    db.cache.invalidate_by_prefix("explorer_properties")
    db.cache.invalidate_by_prefix("explorer_types")
    db.cache.invalidate_by_prefix("explorer_property_types")
    return Response(status_code=204)
