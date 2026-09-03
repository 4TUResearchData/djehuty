"""SSI intake endpoints for the v3 API."""

import logging

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse

from djehuty.api.dependencies import get_db
from djehuty.api.exceptions import ForbiddenError, NotFoundError
from djehuty.web.config import config

router = APIRouter(tags=["V3 / SSI"])
logger = logging.getLogger(__name__)


@router.api_route(
    "/receive-from-ssi",
    methods=["GET", "PUT", "POST", "DELETE"],
    summary="Receive dataset from SSI",
    responses={302: {"description": "Redirect to the newly created draft dataset editor"}},
)
async def receive_from_ssi(request: Request, db=Depends(get_db)):
    import hmac

    from djehuty.web import validator

    # AS-IS: legacy checks the ssi_psk config (404) and the method (405)
    # before reading the body, so an unconfigured instance answers 404 to any
    # method and never inspects the request.
    if config.ssi_psk is None:
        raise NotFoundError()

    if request.method != "PUT":
        return PlainTextResponse(status_code=405, content="Acceptable methods: ['PUT']")

    try:
        body = await request.json()
    except (ValueError, TypeError):
        body = {}
    if not isinstance(body, dict):
        body = {}

    psk = body.get("psk", "")
    if not hmac.compare_digest(str(psk), config.ssi_psk):
        raise ForbiddenError()

    errors: list = []
    title = validator.string_value(body, "title", 0, 255, True, error_list=errors)
    email = validator.string_value(body, "email", 0, 255, True, error_list=errors)
    if errors:
        return JSONResponse(status_code=400, content=errors)

    account = db.account_by_email(email)
    if account is None:
        account_uuid = db.insert_account(email=email)
        if not account_uuid:
            logger.error("Failed to create account for SSI user %s.", email)
            return Response(status_code=500)
        logger.info("Account %s created via SSI.", account_uuid)
    else:
        account_uuid = account["uuid"]

    token, _, session_uuid = db.insert_session(account_uuid, name="Login via SSI")
    if session_uuid is None:
        logger.error("Failed to create a session for account %s.", account_uuid)
        return Response(status_code=500)
    logger.info("Created session %s for account %s.", session_uuid, account_uuid)

    container_uuid, _ = db.insert_dataset(title=title, account_uuid=account_uuid)
    if container_uuid is None:
        logger.error("Failed to create dataset for account %s.", account_uuid)
        return Response(status_code=500)

    from fastapi.responses import RedirectResponse

    return RedirectResponse(
        url=f"{config.base_url}/v3/redirect-from-ssi/{container_uuid}/{token}",
        status_code=302,
    )


@router.get(
    "/redirect-from-ssi/{container_uuid}/{token}",
    summary="Complete SSI redirect",
    responses={302: {"description": "Set the session cookie and redirect to the dataset editor"}},
)
def redirect_from_ssi(container_uuid: str, token: str):
    from djehuty.web import validator

    if not validator.is_valid_uuid(container_uuid):
        raise ForbiddenError()

    from fastapi.responses import RedirectResponse

    response = RedirectResponse(url=f"/my/datasets/{container_uuid}/edit", status_code=302)
    response.set_cookie(
        key="djehuty_session",
        value=token,
        secure=config.in_production,
        httponly=False,
        samesite=None,
    )
    return response
