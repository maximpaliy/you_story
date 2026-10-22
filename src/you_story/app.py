"""Health-only composition root. No product adapters are registered."""

import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from you_story.delivery.contracts import ErrorEnvelope, Health
from you_story.shared.config import Settings
from you_story.shared.context import correlation_id
from you_story.shared.database import Database

_log = logging.getLogger("you_story.http")


def _error(request: Request, status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        {
            "error": {
                "code": code,
                "message": message,
                "correlation_id": request.state.correlation_id,
            }
        },
        status_code=status,
    )


def create_app(
    settings: Settings | None = None, *, readiness: Callable[[], bool] | None = None
) -> FastAPI:
    database: Database | None = None
    if readiness is None:
        database = Database(settings or Settings())  # type: ignore[call-arg]
        readiness = database.ready
    check = readiness

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        yield
        if database is not None:
            database.close()

    app = FastAPI(
        title="You Story foundation",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
        responses={
            404: {"model": ErrorEnvelope, "description": "Not found"},
            405: {"model": ErrorEnvelope, "description": "Method not allowed"},
            422: {"model": ErrorEnvelope, "description": "Invalid request"},
            500: {"model": ErrorEnvelope, "description": "Unexpected error"},
        },
    )

    @app.middleware("http")
    async def correlate(request: Request, call_next: Any) -> Any:
        request.state.correlation_id = str(uuid4())
        token = correlation_id.set(request.state.correlation_id)
        try:
            try:
                response = await call_next(request)
            except Exception:
                _log.error("unexpected_http_error", extra={"correlation_id": correlation_id.get()})
                response = _error(request, 500, "internal_error", "An unexpected error occurred")
            response.headers["X-Correlation-ID"] = request.state.correlation_id
            response.headers["Cache-Control"] = "no-store"
            return response
        finally:
            correlation_id.reset(token)

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException) -> JSONResponse:
        codes = {
            404: ("not_found", "Resource not found"),
            405: ("method_not_allowed", "Method not allowed"),
        }
        code, message = codes.get(error.status_code, ("request_failed", "Request failed"))
        response = _error(request, error.status_code, code, message)
        if error.status_code == 405 and error.headers and "Allow" in error.headers:
            response.headers["Allow"] = error.headers["Allow"]
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
        return _error(request, 422, "invalid_request", "Request validation failed")

    @app.get("/live", operation_id="live", response_model=Health)
    def live() -> dict[str, str]:
        return {"status": "live"}

    @app.get(
        "/ready",
        operation_id="ready",
        response_model=Health,
        responses={503: {"model": ErrorEnvelope, "description": "Unavailable"}},
    )
    def ready(request: Request) -> Any:
        if check():
            return {"status": "ready"}
        return _error(request, 503, "not_ready", "Service is not ready")

    return app
