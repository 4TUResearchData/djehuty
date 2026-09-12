"""OAuth stubs. djehuty does not implement OAuth; these exist for Figshare-API
parity and always return 404, exactly as the legacy handlers do."""

from fastapi import APIRouter

from djehuty.api.exceptions import NotFoundError
from djehuty.api.models.common import ErrorResponse

router = APIRouter(tags=["V2 / Account"])

_STUB = {
    "description": "Not implemented; always returns 404.",
    "responses": {404: {"model": ErrorResponse, "description": "Not implemented"}},
}


def oauth_authorize():
    raise NotFoundError()


def oauth_token():
    raise NotFoundError()


for _method in ("GET", "POST"):
    router.add_api_route(
        "/account/applications/authorize",
        oauth_authorize,
        methods=[_method],
        operation_id=f"oauth_authorize_{_method.lower()}",
        summary="OAuth authorize (stub)",
        **_STUB,
    )

for _method in ("GET", "POST", "PUT", "DELETE"):
    router.add_api_route(
        "/token",
        oauth_token,
        methods=[_method],
        operation_id=f"oauth_token_{_method.lower()}",
        summary="OAuth token (stub)",
        **_STUB,
    )
