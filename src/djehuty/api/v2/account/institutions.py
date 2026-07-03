"""Authenticated /v2/account/institution endpoints."""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from djehuty.api.dependencies import get_db, get_token, pagination_params, require_auth
from djehuty.api.exceptions import ForbiddenError, InvalidInputError
from djehuty.web import formatter
from djehuty.web.config import config

router = APIRouter(prefix="/account", tags=["V2 / Account / Institution"])


@router.get(
    "/institution",
    summary="Get institution details",
)
def get_institution(account=Depends(require_auth)):
    # Djehuty only serves one institution; the response is hardcoded like legacy.
    return JSONResponse(content={"id": 898, "name": config.site_name})


@router.get(
    "/institution/accounts",
    summary="List institution accounts",
)
def list_institution_accounts(
    token: str | None = Depends(get_token),
    db=Depends(get_db),
    paging: dict = Depends(pagination_params),
    institution_user_id: str | None = Query(None, max_length=4096),
    is_active: int | None = Query(None, ge=0, le=1),
    email: str | None = Query(None, max_length=4096),
    id_lte: int | None = Query(None, ge=0),
    id_gte: int | None = Query(None, ge=0),
):
    # Legacy gates this on may_administer (admin-only listing).
    if not token or not db.may_administer(token):
        raise ForbiddenError("Administrator permissions required.")

    accounts = db.accounts(
        limit=paging["limit"],
        offset=paging["offset"],
        institution_user_id=institution_user_id,
        is_active=is_active,
        email=email,
        id_lte=id_lte,
        id_gte=id_gte,
    )
    return JSONResponse(content=[formatter.format_account_record(a) for a in accounts])


@router.get(
    "/institution/users/{account_id}",
    summary="Get institution user",
)
def get_institution_account(
    account_id: str,
    account=Depends(require_auth),
    db=Depends(get_db),
):
    from djehuty.utils.convenience import parses_to_int
    from djehuty.web import validator

    # AS-IS (#111): the legacy guard validates the caller's OWN uuid
    # (account["uuid"]) instead of account_id, so it is always a valid UUID and
    # the 400 branch is effectively unreachable for any account_id. A bad
    # account_id therefore falls through to account_by_uuid(account_id), which
    # returns None, and format_account_record(None) yields a blank record at
    # HTTP 200. Reproduce the wrong-variable check and the missing None guard.
    if not parses_to_int(account_id) and not validator.is_valid_uuid(account["uuid"]):
        raise InvalidInputError(
            "'id' must be either an integer or a UUID.",
            "InvalidAccountId",
        )

    user = db.account_by_uuid(account_id)
    return JSONResponse(content=formatter.format_account_record(user))
