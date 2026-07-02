"""Exception handlers that produce responses matching the legacy API format."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse


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
        return JSONResponse(
            status_code=403,
            content={"message": exc.message},
        )

    @app.exception_handler(InvalidInputError)
    async def invalid_input_handler(request: Request, exc: InvalidInputError):
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
