"""Authenticated /v2/account (current user)."""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from djehuty.api.dependencies import require_auth
from djehuty.api.models.common import ErrorResponse
from djehuty.web import formatter

router = APIRouter(tags=["V2 / Account"])


@router.get(
    "/account",
    summary="Get current account details",
    description="Returns the profile of the currently authenticated user.",
    responses={
        200: {
            "description": "Account details",
            "content": {
                "application/json": {
                    "example": {
                        "id": None,
                        "uuid": "2a795ead-f99c-499b-9134-da4fadee4936",
                        "first_name": "Dev",
                        "last_name": "User",
                        "full_name": None,
                        "is_active": True,
                        "is_public": False,
                        "job_title": None,
                        "orcid_id": "",
                    }
                }
            },
        },
        403: {"model": ErrorResponse, "description": "Invalid or missing session token"},
    },
)
def get_account(account=Depends(require_auth)):
    return JSONResponse(content=formatter.format_account_record(account))
