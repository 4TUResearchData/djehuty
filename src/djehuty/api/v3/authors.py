"""Author lookup endpoints for the v3 API."""

from fastapi import APIRouter, Body, Depends, Response
from fastapi.responses import JSONResponse

from djehuty.api.dependencies import get_db, require_auth
from djehuty.api.exceptions import InvalidInputError, NotFoundError
from djehuty.api.models.common import ErrorResponse
from djehuty.api.v3._shared import _ok
from djehuty.web import formatter

router = APIRouter(tags=["V3 / Authors"])

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
    "/authors/{author_uuid}",
    summary="Get author details",
    responses={
        200: _ok("Author details", _AUTHOR_EXAMPLE),
        403: {"model": ErrorResponse},
    },
)
def get_author_details(author_uuid: str, account=Depends(require_auth), db=Depends(get_db)):
    from djehuty.web import validator

    if not validator.is_valid_uuid(author_uuid):
        raise NotFoundError()

    records = db.authors(author_uuid=author_uuid)
    if not records:
        raise NotFoundError()
    return JSONResponse(content=formatter.format_author_record_v3(records[0]))


@router.put(
    "/authors/{author_uuid}",
    summary="Update author details",
    responses={204: {"description": "Author updated"}, 403: {"model": ErrorResponse}},
)
def update_author_details(
    author_uuid: str,
    body: dict = Body(
        ...,
        openapi_examples={
            "default": {
                "summary": "Update author name and identifiers",
                "value": {
                    "first_name": "Ada",
                    "last_name": "Lovelace",
                    "email": "ada@example.org",
                    "orcid": "0000-0002-1825-0097",
                },
            }
        },
    ),
    account=Depends(require_auth),
    db=Depends(get_db),
):
    from djehuty.web import validator

    if not validator.is_valid_uuid(author_uuid):
        raise NotFoundError()

    try:
        parameters = {
            "first_name": validator.string_value(body, "first_name", 0, 255),
            "last_name": validator.string_value(body, "last_name", 0, 255),
            "email": validator.string_value(body, "email", 0, 255),
            "orcid": validator.string_value(body, "orcid", 0, 255),
        }

        if not db.update_author(author_uuid, account["uuid"], **parameters):
            return Response(status_code=500)

        return Response(status_code=204)
    except validator.ValidationException as error:
        raise InvalidInputError(error.message, error.code) from error
