"""Dataset author endpoints for the v3 API."""

from fastapi import APIRouter, Body, Depends, Query, Response
from fastapi.responses import JSONResponse

from djehuty.api.dependencies import get_db, require_auth
from djehuty.api.exceptions import InvalidInputError, NotFoundError
from djehuty.api.models.common import ErrorResponse
from djehuty.api.permissions import enforce_collaborative_permissions
from djehuty.api.v3._shared import _ok
from djehuty.web import formatter

router = APIRouter(tags=["V3 / Datasets / Authors"])

_AUTHOR_EXAMPLE = {
    "uuid": "07d6e6ce-b1bf-43ca-86e6-7a3ab8bc8416",
    "first_name": "Ada",
    "last_name": "Lovelace",
    "full_name": "Ada Lovelace",
    "email": None,
    "orcid": None,
    "is_editable": False,
}


@router.get(
    "/datasets/{container_uuid}/authors",
    summary="List dataset authors (v3)",
    responses={200: _ok("The dataset's authors", [_AUTHOR_EXAMPLE]), 403: {"model": ErrorResponse}},
)
def list_dataset_authors_v3(
    container_uuid: str,
    account=Depends(require_auth),
    db=Depends(get_db),
    order: str | None = Query(None, max_length=32),
    order_direction: str | None = Query(None, pattern="^(asc|desc)$"),
    limit: int | None = Query(None, ge=1, le=10000),
):
    from djehuty.web import validator

    if not validator.is_valid_uuid(container_uuid):
        raise NotFoundError()
    try:
        dataset = db.datasets(
            container_uuid=container_uuid,
            account_uuid=account["uuid"],
            is_published=False,
            is_latest=False,
            limit=1,
        )[0]
    except (IndexError, AttributeError) as error:
        raise NotFoundError() from error

    # AS-IS: a collaborator (shared dataset) needs metadata_read; owners no-op.
    enforce_collaborative_permissions(db, account["uuid"], dataset, "dataset", "metadata_read")

    authors = db.authors(
        item_uri=dataset["uri"],
        account_uuid=account["uuid"],
        is_published=False,
        item_type="dataset",
        limit=limit,
        order=order or "order_index",
        order_direction=order_direction or "asc",
    )
    return JSONResponse(content=[formatter.format_author_record_v3(a) for a in authors])


@router.get(
    "/datasets/{container_uuid}/authors/{author_uuid}",
    summary="Get a single dataset author (v3)",
    responses={200: _ok("A single author", _AUTHOR_EXAMPLE), 403: {"model": ErrorResponse}},
)
def get_dataset_author_v3(
    container_uuid: str,
    author_uuid: str,
    account=Depends(require_auth),
    db=Depends(get_db),
    order: str | None = Query(None, max_length=32),
    order_direction: str | None = Query(None, pattern="^(asc|desc)$"),
    limit: int | None = Query(None, ge=1, le=10000),
):
    from djehuty.web import validator

    if not validator.is_valid_uuid(container_uuid):
        raise NotFoundError()
    try:
        dataset = db.datasets(
            container_uuid=container_uuid,
            account_uuid=account["uuid"],
            is_published=False,
            is_latest=False,
            limit=1,
        )[0]
    except (IndexError, AttributeError) as error:
        raise NotFoundError() from error

    enforce_collaborative_permissions(db, account["uuid"], dataset, "dataset", "metadata_read")

    authors = db.authors(
        item_uri=dataset["uri"],
        account_uuid=account["uuid"],
        author_uuid=author_uuid,
        is_published=False,
        item_type="dataset",
        limit=limit,
        order=order or "order_index",
        order_direction=order_direction or "asc",
    )
    if not authors:
        raise NotFoundError()
    return JSONResponse(content=formatter.format_author_record_v3(authors[0]))


@router.post(
    "/datasets/{container_uuid}/reorder-authors",
    summary="Reorder authors",
    responses={205: {"description": "Authors reordered"}, 403: {"model": ErrorResponse}},
)
def reorder_authors(
    container_uuid: str,
    body: dict = Body(
        ...,
        openapi_examples={
            "move_up": {
                "summary": "Move an author up",
                "value": {"author": "07d6e6ce-b1bf-43ca-86e6-7a3ab8bc8416", "direction": "up"},
            }
        },
    ),
    account=Depends(require_auth),
    db=Depends(get_db),
):
    from djehuty.web import validator

    if not validator.is_valid_uuid(container_uuid):
        raise NotFoundError()
    if not isinstance(body, dict):
        raise InvalidInputError("Request body must be a JSON object.", "BadBody")

    direction = body.get("direction")
    if direction not in ("up", "down"):
        raise InvalidInputError("direction must be 'up' or 'down'.", "BadDirection")
    author_uuid = body.get("author")
    if not author_uuid or not validator.is_valid_uuid(author_uuid):
        raise InvalidInputError("author must be a valid UUID.", "BadAuthor")

    if not db.reorder_authors(account["uuid"], container_uuid, author_uuid, direction):
        raise InvalidInputError("Failed to reorder authors.", "ReorderFailed")
    return Response(status_code=205)
