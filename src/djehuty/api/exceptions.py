"""Exception handlers that produce responses matching the legacy API format."""

import json
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse

logger = logging.getLogger(__name__)


class NotFoundError(Exception):
    """Raised when a resource is not found."""


class AuthorizationError(Exception):
    """Raised when authentication is missing or invalid."""


class ForbiddenError(Exception):
    """Raised when the user lacks required privileges."""

    def __init__(self, message: str = "Not allowed."):
        self.message = message


class InvalidInputError(Exception):
    """Raised when input validation fails."""

    def __init__(self, message: str, code: str = "InvalidValue"):
        self.message = message
        self.code = code


def register_exception_handlers(app: FastAPI):
    """Register custom exception handlers on the FastAPI app."""

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        errors = []
        for error in exc.errors():
            if error["type"] == "json_invalid":
                detail = error.get("ctx", {}).get("error", error["msg"])
                if getattr(exc, "body", None) is not None:
                    try:
                        json.loads(exc.body)
                    except json.JSONDecodeError as decode_error:
                        detail = str(decode_error)
                errors.append(
                    {
                        "message": f"Failed to decode JSON object: {detail}",
                        "code": 400,
                        "field": None,
                    }
                )
                continue
            field = ".".join(str(loc) for loc in error["loc"] if loc != "body")
            errors.append(
                {
                    "message": f"Invalid value for '{field}': {error['msg']}",
                    "code": "ValidationError",
                    "field": field,
                }
            )
        if len(errors) == 1:
            return JSONResponse(
                status_code=400,
                content={"message": errors[0]["message"], "code": errors[0]["code"]},
            )
        return JSONResponse(status_code=400, content=errors)

    @app.exception_handler(NotFoundError)
    async def not_found_handler(request: Request, exc: NotFoundError):
        return JSONResponse(
            status_code=404,
            content={"message": "This resource does not exist."},
        )

    @app.exception_handler(404)
    async def not_found_status_handler(request: Request, exc):
        # AS-IS: legacy error_404 returns this body for an unmatched route,
        # where Starlette's default would send {"detail": "Not Found"}.
        return JSONResponse(
            status_code=404,
            content={"message": "This resource does not exist."},
        )

    @app.exception_handler(AuthorizationError)
    async def authorization_handler(request: Request, exc: AuthorizationError):
        return JSONResponse(
            status_code=403,
            content={
                "message": "Invalid or unknown session token",
                "code": "InvalidSessionToken",
            },
        )

    @app.exception_handler(ForbiddenError)
    async def forbidden_handler(request: Request, exc: ForbiddenError):
        # AS-IS: legacy error_403 sends the descriptive text to the audit log
        # and always returns {"message": "Not allowed."} to the client.
        if exc.message and exc.message != "Not allowed.":
            logger.info("Forbidden on %s %s: %s", request.method, request.url.path, exc.message)
        return JSONResponse(
            status_code=403,
            content={"message": "Not allowed."},
        )

    @app.exception_handler(InvalidInputError)
    async def invalid_input_handler(request: Request, exc: InvalidInputError):
        # AS-IS: legacy error_400_list serialises a list of errors as a bare
        # JSON array; a single message keeps the {message, code} object shape.
        if isinstance(exc.message, list):
            return JSONResponse(status_code=400, content=exc.message)
        return JSONResponse(
            status_code=400,
            content={"message": exc.message, "code": exc.code},
        )

    @app.exception_handler(405)
    async def method_not_allowed_handler(request: Request, exc):
        return PlainTextResponse(
            status_code=405,
            content=f"Acceptable methods: {exc.detail}",
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception):
        logger.error("Unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
        return PlainTextResponse(status_code=500, content="Internal Server Error")
