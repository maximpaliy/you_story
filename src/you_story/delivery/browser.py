"""Strict same-origin browser adapter; identity authority stays behind public ports."""

from __future__ import annotations

import ipaddress
import re
import secrets
from collections.abc import Callable, Coroutine
from typing import Any, Literal, cast
from urllib.parse import parse_qsl, urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from jinja2 import Environment, PackageLoader, select_autoescape
from starlette.concurrency import run_in_threadpool

from you_story.delivery.contracts import ErrorEnvelope, OwnProfile
from you_story.identity.public import (
    AuthenticatedSession,
    AuthFailure,
    IdentityService,
    LoginSuccess,
)

SESSION_COOKIE = "__Host-you_story_session"
LOGIN_COOKIE = "__Host-you_story_login"
_FORM_LIMIT = 4096
_QUERY_LIMIT = 8192
_TEMPLATES = Environment(
    loader=PackageLoader("you_story.delivery", "templates"),
    autoescape=select_autoescape(("html",)),
)
_MESSAGES = {
    "invalid_request": "Invalid request",
    "unauthenticated": "Authentication required",
    "forbidden": "Request forbidden",
    "already_authenticated": "Already signed in",
    "login_in_progress": "Login already in progress",
    "payload_too_large": "Request too large",
    "unsupported_media_type": "Unsupported request type",
    "rate_limited": "Too many requests",
    "unavailable": "Service unavailable",
    "login_failed": "Login could not be completed",
    "internal_error": "An unexpected error occurred",
}
_PERMISSIONS = (
    "accelerometer=(), autoplay=(), camera=(), display-capture=(), encrypted-media=(), "
    "fullscreen=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), midi=(), "
    "payment=(), picture-in-picture=(), publickey-credentials-get=(), screen-wake-lock=(), "
    "serial=(), usb=(), web-share=(), xr-spatial-tracking=()"
)
_COOKIE_AUTH: dict[str, object] = {"security": [{"SessionCookie": []}]}
_TOKEN_SCHEMA: dict[str, object] = {
    "type": "string",
    "pattern": "^[A-Za-z0-9_-]{43}$",
    "minLength": 43,
    "maxLength": 43,
}


def _response_docs(*statuses: int, callback: bool = False) -> dict[int | str, dict[str, Any]]:
    result: dict[int | str, dict[str, Any]] = {}
    for status in statuses:
        if callback:
            result[status] = {
                "description": "Generic sign-in failure with fixed /login retry link",
                "content": {"text/html": {"schema": {"type": "string"}}},
            }
        else:
            result[status] = {"model": ErrorEnvelope, "description": "Safe bounded failure"}
        if status == 429:
            result[status]["headers"] = {
                "Retry-After": {"schema": {"type": "integer", "minimum": 1}},
            }
    return result


def _form_docs(properties: dict[str, object], required: list[str]) -> dict[str, object]:
    return {
        "requestBody": {
            "required": True,
            "content": {
                "application/x-www-form-urlencoded": {
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": required,
                        "properties": properties,
                    }
                },
            },
        },
        "x-max-body-bytes": _FORM_LIMIT,
        "x-origin-and-csrf-required": True,
        "x-reject-duplicate-fields": True,
    }


class BrowserFailure(Exception):
    def __init__(self, status: int, code: str) -> None:
        self.status = status
        self.code = code
        super().__init__(code)


def _render(name: str, *, status: int = 200, **values: object) -> HTMLResponse:
    return HTMLResponse(_TEMPLATES.get_template(name).render(**values), status_code=status)


def callback_failure(
    request: Request, status: int = 400, retry_after: int | None = None
) -> HTMLResponse:
    """The same unreflected page for every exact callback GET failure."""
    response = _render("failure.html", status=status)
    if status == 429 and retry_after is not None:
        response.headers["Retry-After"] = str(max(1, retry_after))
    return response


def apply_response_policy(
    response: Response,
    *,
    production: bool,
    method: str | None = None,
    path: str | None = None,
) -> Response:
    """Called by the outer composition middleware, including for framework errors."""
    html = response.headers.get("content-type", "").split(";", 1)[0].lower() == "text/html"
    form_page = (
        html
        and response.status_code == 200
        and method == "GET"
        and path in {"/login", "/", "/profile"}
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin" if form_page else "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Permissions-Policy"] = _PERMISSIONS
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    if production:
        response.headers["Strict-Transport-Security"] = "max-age=31536000"
    if html:
        nonce = secrets.token_urlsafe(32)
        form_action = "form-action 'self'"
        if form_page and path == "/login":
            form_action += " https://accounts.google.com/o/oauth2/v2/auth"
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; "
            f"script-src 'nonce-{nonce}' 'strict-dynamic'; "
            "style-src 'self'; img-src 'self'; font-src 'self'; connect-src 'self'; "
            "manifest-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; "
            f"{form_action}; frame-src 'none'; media-src 'none'; worker-src 'none'"
        )
    return response


def _origin(value: str, *, referer: bool = False) -> tuple[str, str, int]:
    if not value or any(ord(c) <= 32 for c in value):
        raise ValueError("invalid origin")
    parsed = urlsplit(value)
    scheme = parsed.scheme.lower()
    host = parsed.hostname
    if (
        scheme not in {"http", "https"}
        or not host
        or parsed.username is not None
        or parsed.password is not None
        or "%" in parsed.netloc
        or "\\" in parsed.netloc
        or "," in parsed.netloc
        or not parsed.netloc.isascii()
        or parsed.netloc.endswith(":")
        or host.endswith(".")
        or (
            not referer
            and (parsed.path or parsed.query or parsed.fragment or "?" in value or "#" in value)
        )
    ):
        raise ValueError("invalid origin")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        if len(host) > 253 or any(
            not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
            for label in host.lower().split(".")
        ):
            raise ValueError("invalid host") from None
    port = parsed.port if parsed.port is not None else (443 if scheme == "https" else 80)
    if not 1 <= port <= 65535:
        raise ValueError("invalid port")
    return scheme, host.lower(), port


def _one_header(request: Request, name: str) -> str | None:
    values = request.headers.getlist(name)
    if len(values) > 1:
        raise BrowserFailure(403, "forbidden")
    return values[0] if values else None


def _provenance(request: Request, expected: tuple[str, str, int]) -> None:
    origin = _one_header(request, "origin")
    referer = _one_header(request, "referer") if origin is None else None
    fetch_site = _one_header(request, "sec-fetch-site")
    try:
        if origin is not None:
            actual = _origin(origin)
        elif referer is not None:
            actual = _origin(referer, referer=True)
            if actual[0] != "https":
                raise ValueError("invalid referer")
        else:
            raise ValueError("missing provenance")
    except ValueError:
        raise BrowserFailure(403, "forbidden") from None
    if actual != expected or (fetch_site is not None and fetch_site != "same-origin"):
        raise BrowserFailure(403, "forbidden")


def _cookie(request: Request, name: str) -> str | None:
    headers = request.headers.getlist("cookie")
    if sum(len(v) for v in headers) > 8192:
        return None
    values: list[str] = []
    for header in headers:
        for item in header.split(";"):
            key, sep, value = item.strip().partition("=")
            if key == name:
                if not sep:
                    return None
                values.append(value)
    if len(values) != 1:
        return None
    value = values[0]
    if name == SESSION_COOKIE:
        return value if re.fullmatch(r"[A-Za-z0-9_-]{43}", value) else None
    return value if 0 < len(value) <= 512 and value.isascii() else None


async def _body(request: Request, limit: int) -> bytes:
    lengths = request.headers.getlist("content-length")
    encodings = request.headers.getlist("transfer-encoding")
    if (
        len(lengths) > 1
        or (lengths and encodings)
        or len(encodings) > 1
        or (encodings and encodings[0].lower() != "chunked")
    ):
        raise BrowserFailure(400, "invalid_request")
    expected: int | None = None
    if lengths:
        if not re.fullmatch(r"[0-9]+", lengths[0]) or len(lengths[0]) > 12:
            raise BrowserFailure(400, "invalid_request")
        expected = int(lengths[0])
        if expected > limit:
            raise BrowserFailure(
                413 if limit else 400, "payload_too_large" if limit else "invalid_request"
            )
    result = bytearray()
    async for chunk in request.stream():
        if len(result) + len(chunk) > limit:
            raise BrowserFailure(
                413 if limit else 400, "payload_too_large" if limit else "invalid_request"
            )
        result.extend(chunk)
    if expected is not None and expected != len(result):
        raise BrowserFailure(400, "invalid_request")
    return bytes(result)


def _decode_pairs(
    raw: bytes, allowed: set[str], *, token_field: str | None = None
) -> dict[str, str]:
    try:
        text = raw.decode("utf-8", "strict")
        if re.search(r"%(?![0-9a-fA-F]{2})", text):
            raise ValueError("invalid percent encoding")
        pairs = parse_qsl(
            text,
            keep_blank_values=True,
            strict_parsing=True,
            encoding="utf-8",
            errors="strict",
            max_num_fields=12,
        )
        result: dict[str, str] = {}
        for key, value in pairs:
            if key == token_field and key in result:
                raise BrowserFailure(403, "forbidden")
            if key not in allowed or key in result:
                raise ValueError("unknown or duplicate field")
            result[key] = value
        return result
    except (ValueError, UnicodeError):
        raise BrowserFailure(400, "invalid_request") from None


async def _form(request: Request, allowed: set[str], *, token_field: str) -> dict[str, str]:
    if request.scope["query_string"]:
        raise BrowserFailure(400, "invalid_request")
    raw = await _body(request, _FORM_LIMIT)
    types = request.headers.getlist("content-type")
    if len(types) != 1:
        raise BrowserFailure(415, "unsupported_media_type")
    parts = [p.strip().lower() for p in types[0].split(";")]
    if parts[0] != "application/x-www-form-urlencoded" or (
        len(parts) > 1 and (len(parts) != 2 or parts[1] != "charset=utf-8")
    ):
        raise BrowserFailure(415, "unsupported_media_type")
    return _decode_pairs(raw, allowed, token_field=token_field)


async def _empty_request(request: Request) -> None:
    if request.scope["query_string"]:
        raise BrowserFailure(400, "invalid_request")
    await _body(request, 0)


def _error(request: Request, status: int, code: str, retry_after: int | None = None) -> Response:
    if code not in _MESSAGES:
        status, code = 500, "internal_error"
    if request.method == "GET" and request.url.path == "/auth/google/callback":
        return callback_failure(request, status, retry_after)
    response = JSONResponse(
        {
            "error": {
                "code": code,
                "message": _MESSAGES[code],
                "correlation_id": request.state.correlation_id,
            }
        },
        status_code=status,
    )
    if status == 429 and retry_after is not None:
        response.headers["Retry-After"] = str(max(1, retry_after))
    return response


def register_browser_routes(
    app: FastAPI,
    service: IdentityService,
    *,
    canonical_origin: str,
    production: bool,
    complete_login: Callable[[LoginSuccess], LoginSuccess] | None = None,
) -> None:
    expected = _origin(canonical_origin)
    if expected[0] != "https":
        try:
            loopback = ipaddress.ip_address(expected[1]).is_loopback
        except ValueError:
            loopback = expected[1] == "localhost"
        if production or not loopback:
            raise ValueError("HTTPS canonical origin required")

    async def dispatch(
        request: Request, operation: Callable[[], Coroutine[Any, Any, Response]]
    ) -> Response:
        try:
            return await operation()
        except BrowserFailure as error:
            return _error(request, error.status, error.code)
        except AuthFailure as error:
            return _error(request, error.status, error.code, error.retry_after)

    def peer(request: Request) -> str:
        if request.client is None:
            raise BrowserFailure(503, "unavailable")
        return request.client.host

    @app.get(
        "/login",
        operation_id="loginForm",
        response_class=HTMLResponse,
        responses={
            **_response_docs(400, 500, 503),
            303: {"description": "Fixed / for authenticated user"},
        },
    )
    async def login(request: Request) -> Response:
        async def action() -> Response:
            await _empty_request(request)
            current = await run_in_threadpool(
                service.resolve_session, _cookie(request, SESSION_COOKIE)
            )
            if current is not None:
                return RedirectResponse("/", status_code=303)
            form = await run_in_threadpool(service.get_login_form, _cookie(request, LOGIN_COOKIE))
            response = _render("login.html", proof=form.proof)
            response.set_cookie(
                LOGIN_COOKIE,
                form.binder_cookie,
                max_age=form.max_age,
                secure=True,
                httponly=True,
                samesite="lax",
                path="/",
            )
            return response

        return await dispatch(request, action)

    @app.post(
        "/auth/google/start",
        operation_id="startGoogleLogin",
        response_class=RedirectResponse,
        status_code=303,
        responses=_response_docs(400, 403, 409, 413, 415, 429, 500, 503),
        openapi_extra=_form_docs(
            {
                "proof": {"type": "string", "minLength": 1, "maxLength": 512},
                "destination": {
                    "type": "string",
                    "enum": ["home", "calendar", "catalog"],
                    "default": "home",
                },
                "invitation": _TOKEN_SCHEMA,
            },
            ["proof"],
        ),
    )
    async def start(request: Request) -> Response:
        async def action() -> Response:
            _provenance(request, expected)
            try:
                form = await _form(
                    request, {"proof", "destination", "invitation"}, token_field="proof"
                )
            except BrowserFailure as failure:
                if failure.status == 403:
                    # A duplicate proof is still a proof attempt: charge IP only,
                    # with no binder authority, just like other invalid proofs.
                    try:
                        await run_in_threadpool(
                            service.start_login, binder_cookie="", proof="", ip_key=peer(request)
                        )
                    except AuthFailure as error:
                        if error.status in {429, 503}:
                            raise
                raise
            location = await run_in_threadpool(
                service.start_login,
                binder_cookie=_cookie(request, LOGIN_COOKIE) or "",
                proof=form.get("proof", ""),
                destination=form.get("destination", "home"),
                invitation=form.get("invitation") or None,
                ip_key=peer(request),
                session_cookie=_cookie(request, SESSION_COOKIE),
            )
            return RedirectResponse(location, status_code=303)

        return await dispatch(request, action)

    @app.get(
        "/auth/google/callback",
        operation_id="completeGoogleLogin",
        response_class=RedirectResponse,
        status_code=303,
        responses=_response_docs(400, 409, 429, 500, 503, callback=True),
        openapi_extra={
            "parameters": [
                {
                    "in": "query",
                    "name": name,
                    "required": name == "state",
                    "schema": _TOKEN_SCHEMA
                    if name == "state"
                    else {"type": "string", "maxLength": _QUERY_LIMIT},
                }
                for name in [
                    "state",
                    "code",
                    "error",
                    "scope",
                    "authuser",
                    "prompt",
                    "iss",
                    "error_description",
                    "error_uri",
                ]
            ],
            "x-max-query-bytes": _QUERY_LIMIT,
            "x-reject-duplicate-fields": True,
            "description": (
                "Exactly one state and one of code or error. Unknown/duplicate query fields "
                "and body rejected. HEAD never dispatches; every GET failure is generic HTML."
            ),
        },
    )
    async def callback(request: Request) -> Response:
        async def action() -> Response:
            try:
                raw = request.scope["query_string"]
                if len(raw) > _QUERY_LIMIT:
                    raise BrowserFailure(400, "invalid_request")
                await _body(request, 0)
                fields = _decode_pairs(
                    raw,
                    {
                        "state",
                        "code",
                        "error",
                        "scope",
                        "authuser",
                        "prompt",
                        "iss",
                        "error_description",
                        "error_uri",
                    },
                )
                if not fields.get("state") or (("code" in fields) == ("error" in fields)):
                    raise BrowserFailure(400, "invalid_request")
                if not fields.get("code", fields.get("error", "")):
                    raise BrowserFailure(400, "invalid_request")
            except BrowserFailure:
                # Charge the IP callback stage even for malformed queries. Empty
                # state and missing binder cannot claim or terminalize another flow.
                try:
                    await run_in_threadpool(
                        service.complete_login,
                        binder_cookie="",
                        state="",
                        ip_key=peer(request),
                    )
                except AuthFailure as error:
                    if error.status in {429, 503}:
                        raise
                raise BrowserFailure(400, "invalid_request") from None
            result = await run_in_threadpool(
                service.complete_login,
                binder_cookie=_cookie(request, LOGIN_COOKIE) or "",
                state=fields["state"],
                code=fields.get("code"),
                error=fields.get("error"),
                issuer=fields.get("iss"),
                session_cookie=_cookie(request, SESSION_COOKIE),
                ip_key=peer(request),
            )
            if complete_login is not None:
                result = await run_in_threadpool(complete_login, result)
            response = RedirectResponse(result.destination, status_code=303)
            response.set_cookie(
                SESSION_COOKIE,
                result.session_cookie,
                max_age=2592000,
                secure=True,
                httponly=True,
                samesite="lax",
                path="/",
            )
            return response

        return await dispatch(request, action)

    async def authenticated(request: Request) -> AuthenticatedSession:
        session = await run_in_threadpool(service.resolve_session, _cookie(request, SESSION_COOKIE))
        if session is None:
            raise BrowserFailure(401, "unauthenticated")
        return session

    async def page(request: Request) -> Response:
        async def action() -> Response:
            await _empty_request(request)
            try:
                session = await authenticated(request)
            except BrowserFailure as error:
                if error.status == 401:
                    return RedirectResponse("/login", status_code=303)
                raise
            token = await run_in_threadpool(service.csrf_token, session)
            return _render(
                "profile.html", csrf=token, provisioning_state=session.provisioning_state
            )

        return await dispatch(request, action)

    app.add_api_route(
        "/",
        page,
        methods=["GET"],
        operation_id="ownHome",
        response_class=HTMLResponse,
        responses={
            **_response_docs(400, 500, 503),
            303: {"description": "Fixed /login for anonymous user"},
        },
        openapi_extra=_COOKIE_AUTH,
    )
    app.add_api_route(
        "/profile",
        page,
        methods=["GET"],
        operation_id="ownProfilePage",
        response_class=HTMLResponse,
        responses={
            **_response_docs(400, 500, 503),
            303: {"description": "Fixed /login for anonymous user"},
        },
        openapi_extra=_COOKIE_AUTH,
    )

    @app.get(
        "/api/v1/profile",
        operation_id="getOwnProfile",
        response_model=OwnProfile,
        responses=_response_docs(400, 401, 500, 503),
        openapi_extra=_COOKIE_AUTH,
    )
    async def profile_json(request: Request) -> Response:
        async def action() -> Response:
            await _empty_request(request)
            session = await authenticated(request)
            if session.provisioning_state not in {"catalog_pending", "ready"}:
                raise BrowserFailure(503, "unavailable")
            profile = OwnProfile(
                user_id=session.actor.actor_id,
                provisioning_state=cast(
                    Literal["catalog_pending", "ready"], session.provisioning_state
                ),
            )
            return JSONResponse(profile.model_dump(mode="json"))

        return await dispatch(request, action)

    @app.post(
        "/logout",
        operation_id="logoutCurrentSession",
        response_class=RedirectResponse,
        status_code=303,
        responses=_response_docs(400, 401, 403, 413, 415, 500, 503),
        openapi_extra={**_form_docs({"csrf": _TOKEN_SCHEMA}, ["csrf"]), **_COOKIE_AUTH},
    )
    async def logout(request: Request) -> Response:
        async def action() -> Response:
            session = await authenticated(request)
            _provenance(request, expected)
            fields = await _form(request, {"csrf"}, token_field="csrf")
            if request.headers.getlist("x-csrf-token") or not await run_in_threadpool(
                service.validate_csrf,
                session,
                fields.get("csrf", ""),
            ):
                raise BrowserFailure(403, "forbidden")
            if not await run_in_threadpool(service.logout, session):
                raise BrowserFailure(401, "unauthenticated")
            response = RedirectResponse("/login", status_code=303)
            for name in (SESSION_COOKIE, LOGIN_COOKIE):
                response.delete_cookie(name, path="/", secure=True, httponly=True, samesite="lax")
            return response

        return await dispatch(request, action)
