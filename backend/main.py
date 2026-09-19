"""FastAPI application entrypoint.

Trading adapters are deliberately absent until their dedicated implementation phase.
"""

import logging
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from backend.api.router import api_router
from backend.config.settings import get_settings
from backend.core.errors import http_exception_handler, validation_exception_handler
from backend.core.logging import configure_logging


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Attach a correlation ID to each response and request lifecycle."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request.state.request_id = request.headers.get("X-Request-ID", str(uuid4()))
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    logging.getLogger(__name__).info(
        "application_started environment=%s trading_mode=%s live_trading_enabled=%s",
        settings.app_env,
        settings.trading_mode,
        settings.live_trading_enabled,
    )
    yield
    logging.getLogger(__name__).info("application_stopped")


settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Safety-first foundation. No MT5 connection or execution is enabled.",
    lifespan=lifespan,
)
app.add_middleware(RequestIdMiddleware)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.include_router(api_router)
