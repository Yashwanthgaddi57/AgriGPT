"""Domain exceptions with consistent JSON error contract."""
import logging

from fastapi import Request, status
from fastapi.responses import JSONResponse

logger = logging.getLogger("app.errors")


class AgriGPTError(Exception):
    """Base app exception."""

    status_code = 500
    detail = "Internal server error"

    def __init__(self, detail: str | None = None):
        if detail:
            self.detail = detail
        super().__init__(self.detail)


class NotFoundError(AgriGPTError):
    status_code = 404
    detail = "Resource not found"


class ValidationError(AgriGPTError):
    status_code = 422
    detail = "Validation error"


class AIError(AgriGPTError):
    status_code = 502
    detail = "AI service unavailable"


class AuthError(AgriGPTError):
    status_code = 401
    detail = "Unauthorized"


class ConflictError(AgriGPTError):
    """HTTP 409 — resource already exists (e.g. duplicate email on register)."""

    status_code = 409
    detail = "Conflict"


class ExternalServiceError(AgriGPTError):
    status_code = 502
    detail = "External service error"


async def agrigpt_error_handler(request: Request, exc: AgriGPTError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.__class__.__name__,
                "detail": exc.detail,
                "path": request.url.path,
            }
        },
    )


# User-friendly copy for unexpected failures. Stack traces stay in the logs.
_GENERIC_500 = "Something went wrong. Please try again in a moment."


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "InternalServerError",
                "detail": _GENERIC_500,
                "path": request.url.path,
            }
        },
    )


def register_exception_handlers(app) -> None:
    app.add_exception_handler(AgriGPTError, agrigpt_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
