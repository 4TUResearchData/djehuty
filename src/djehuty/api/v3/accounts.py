"""Account search endpoints for the v3 API."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from djehuty.api.dependencies import get_db, require_auth
from djehuty.api.exceptions import InvalidInputError
from djehuty.api.models.common import ErrorResponse
from djehuty.api.v3._shared import _ok
from djehuty.web import formatter

router = APIRouter(tags=["V3 / Accounts"])

_ACCOUNT_EXAMPLE = {
    "id": None,
    "uuid": "84cae99f-a691-4af2-9d21-f5c0817c26df",
    "first_name": "Dev",
    "last_name": "User",
    "full_name": None,
    "email": "dev@djehuty.com",
    "is_active": True,
    "is_public": False,
    "job_title": None,
    "orcid_id": "",
}


@router.api_route(
    "/accounts/search",
    methods=["GET", "POST"],
    summary="Search accounts",
    description="Search for user accounts (autocomplete for adding collaborators).",
    responses={
        200: _ok("Matching accounts", [_ACCOUNT_EXAMPLE]),
        400: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
)
async def search_accounts(
    request: Request,
    account=Depends(require_auth),
    db=Depends(get_db),
):
    from djehuty.web import validator

    # AS-IS: legacy checks authentication before the method, so an
    # unauthenticated GET is 403 (from require_auth above), not the 405 you
    # would expect from method enforcement. An authenticated non-POST is 405.
    if request.method != "POST":
        return PlainTextResponse(status_code=405, content="Acceptable methods: ['POST']")

    try:
        body = await request.json()
    except (ValueError, TypeError):
        body = {}
    if not isinstance(body, dict):
        body = {}
    try:
        search_for = validator.string_value(
            body, "search_for", 0, 32, required=True, strip_html=False
        )
        # AS-IS (#111): legacy reads `exclude` via array_value(required=False),
        # which returns None when the field is absent, then evaluates
        # `account["uuid"] in exclude` -> `... in None` -> TypeError. That is
        # not caught by legacy's `except (ValidationException, KeyError)`, so
        # it propagates -> HTTP 500 whenever the search matches at least one
        # account. Reproduce faithfully: no guard on `exclude`.
        exclude = validator.array_value(body, "exclude", required=False)
        accounts = db.accounts(search_for=search_for, limit=5)
        for index, _ in enumerate(accounts):
            record = accounts[index]
            if record["uuid"] in exclude:
                accounts.pop(index)
        return JSONResponse(content=[formatter.format_account_details_record(r) for r in accounts])
    except (validator.ValidationException, KeyError) as error:
        raise InvalidInputError(error.message, error.code) from error
