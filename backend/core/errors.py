"""Safe, consistent error responses for the public API."""

from typing import Any

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ApiError(BaseModel):
    """Non-sensitive error envelope returned by all API failures."""

    code: str
    message: str
    request_id: str
    details: list[dict[str, Any]] | None = None


def request_id_for(request: Request) -> str:
    """Read the request ID attached by middleware, with a safe fallback."""
    return getattr(request.state, "request_id", "unavailable")


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Convert expected HTTP failures into the documented API envelope."""
    message = exc.detail if isinstance(exc.detail, str) else "Request could not be completed."
    return JSONResponse(
        status_code=exc.status_code,
        content=ApiError(
            code="http_error",
            message=message,
            request_id=request_id_for(request),
        ).model_dump(),
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Return validation details without exposing internal exception state."""
    return JSONResponse(
        status_code=422,
        content=ApiError(
            code="validation_error",
            message="The request did not pass validation.",
            request_id=request_id_for(request),
            details=exc.errors(),
        ).model_dump(),
    )
