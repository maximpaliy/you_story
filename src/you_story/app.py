"""Composition root for the approved Google browser authentication slice."""

import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException

from you_story.catalog.public import ensure_personal_catalog
from you_story.delivery.browser import (
    apply_response_policy,
    callback_failure,
    register_browser_routes,
)
from you_story.delivery.contracts import ErrorEnvelope, Health
from you_story.identity.public import (
    AuthSettings,
    IdentityService,
    LoginSuccess,
    create_identity_service,
    unavailable_identity_service,
)
from you_story.shared.config import Settings
from you_story.shared.context import correlation_id
from you_story.shared.database import Database

_log = logging.getLogger("you_story.http")


class _SuppressAccessDetails(logging.Filter):
    """Default HTTP client/server access records contain secret-bearing URLs."""

    def filter(self, record: logging.LogRecord) -> bool:
        return False


_ACCESS_FILTER = _SuppressAccessDetails()


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
    settings: Settings | None = None,
    *,
    readiness: Callable[[], bool] | None = None,
    auth_settings: AuthSettings | None = None,
    auth_service: IdentityService | None = None,
) -> FastAPI:
    logging.getLogger("uvicorn.access").addFilter(_ACCESS_FILTER)
    logging.getLogger("httpx").addFilter(_ACCESS_FILTER)
    database: Database | None = None
    metadata_only = (
        settings is None
        and readiness is not None
        and auth_settings is None
        and auth_service is None
    )
    if not metadata_only:
        database = Database(settings or Settings())  # type: ignore[call-arg]
        auth_settings = auth_settings or AuthSettings()  # type: ignore[call-arg]
        auth_service = auth_service or create_identity_service(database, auth_settings)
    else:
        auth_service = unavailable_identity_service()
    if readiness is None:
        assert database is not None
        readiness = database.ready
    check = readiness
    production = auth_settings.production if auth_settings is not None else False
    origin = auth_settings.origin if auth_settings is not None else "https://metadata.invalid"

    def provision(result: LoginSuccess) -> LoginSuccess:
        if database is not None and result.session.provisioning_state == "catalog_pending":
            try:
                ensure_personal_catalog(database, result.session.actor)
                assert auth_service is not None
                auth_service.mark_catalog_ready(result.session)
            except Exception:
                _log.warning(
                    "catalog_provisioning_pending",
                    extra={"correlation_id": correlation_id.get()},
                )
        return result

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        yield
        if database is not None:
            database.close()

    app = FastAPI(
        title="You Story",
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
                response = (
                    callback_failure(request, 500)
                    if request.method == "GET" and request.url.path == "/auth/google/callback"
                    else _error(request, 500, "internal_error", "An unexpected error occurred")
                )
            response.headers["X-Correlation-ID"] = request.state.correlation_id
            return apply_response_policy(
                response, production=production, method=request.method, path=request.url.path
            )
        finally:
            correlation_id.reset(token)

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException) -> Response:
        if request.method == "GET" and request.url.path == "/auth/google/callback":
            return callback_failure(request, error.status_code)
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
    async def validation_error(request: Request, error: RequestValidationError) -> Response:
        if request.method == "GET" and request.url.path == "/auth/google/callback":
            return callback_failure(request, 400)
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

    assert auth_service is not None
    register_browser_routes(
        app, auth_service, canonical_origin=origin, production=production, complete_login=provision
    )
    generate_schema = app.openapi

    def openapi() -> dict[str, Any]:
        schema = generate_schema()
        schema.setdefault("components", {}).setdefault("securitySchemes", {})["SessionCookie"] = {
            "type": "apiKey",
            "in": "cookie",
            "name": "__Host-you_story_session",
            "description": (
                "Opaque browser session; request fields cannot select identity or tenant."
            ),
        }
        return schema

    app.openapi = openapi  # type: ignore[method-assign]
    return app
