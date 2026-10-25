"""Production browser adapter checks; identity is a deliberately isolated fake port."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.testclient import TestClient

from you_story.delivery.browser import (
    LOGIN_COOKIE,
    SESSION_COOKIE,
    _origin,
    apply_response_policy,
    callback_failure,
    register_browser_routes,
)
from you_story.identity.public import AuthFailure, LoginForm

ORIGIN = "https://app.example"
BEARER = "s" * 43
CSRF = "c" * 43
BINDER = "signed-binder"


class FakeIdentity:
    """No DB/OIDC evidence is inferred from these delivery-only tests."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.revoked = False
        self.proof = "proof-value"
        self.callback_failure: AuthFailure | None = None
        self.session = SimpleNamespace(
            actor=SimpleNamespace(actor_id=UUID(int=1), tenant_id=UUID(int=2)),
            provisioning_state="catalog_pending",
            session_id=UUID(int=3),
        )

    def resolve_session(self, cookie: str | None) -> Any:
        self.calls.append(("resolve", {"cookie": cookie}))
        return self.session if cookie == BEARER and not self.revoked else None

    def get_login_form(self, binder_cookie: str | None) -> LoginForm:
        self.calls.append(("form", {"binder_cookie": binder_cookie}))
        return LoginForm(BINDER, self.proof, datetime.now(UTC) + timedelta(seconds=600), 599)

    def start_login(self, **values: Any) -> str:
        self.calls.append(("start", values))
        if values.get("session_cookie") == BEARER and not self.revoked:
            raise AuthFailure(409, "already_authenticated")
        if values["proof"] != "proof-value" or values["binder_cookie"] != BINDER:
            raise AuthFailure(403, "forbidden")
        if values["destination"] not in {"home", "calendar", "catalog"}:
            raise AuthFailure(400, "invalid_request")
        return "https://accounts.google.com/o/oauth2/v2/auth?state=server-state"

    def complete_login(self, **values: Any) -> Any:
        self.calls.append(("complete", values))
        if self.callback_failure:
            raise self.callback_failure
        if not values.get("state") or not values.get("binder_cookie"):
            raise AuthFailure(400, "login_failed")
        return SimpleNamespace(session=self.session, session_cookie=BEARER, destination="/")

    def csrf_token(self, session: Any) -> str:
        assert session is self.session
        return CSRF

    def validate_csrf(self, session: Any, token: str) -> bool:
        assert session is self.session
        return token == CSRF

    def logout(self, session: Any) -> bool:
        assert session is self.session
        self.calls.append(("logout", {}))
        self.revoked = True
        return True


def browser_client(fake: FakeIdentity, *, production: bool = True) -> TestClient:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def outer(request: Request, call_next: Any) -> Any:
        request.state.correlation_id = str(uuid4())
        try:
            response = await call_next(request)
        except Exception:
            response = (
                callback_failure(request, 500)
                if request.url.path == "/auth/google/callback" and request.method == "GET"
                else JSONResponse({"error": "internal_error"}, status_code=500)
            )
        response.headers["X-Correlation-ID"] = request.state.correlation_id
        return apply_response_policy(
            response, production=production, method=request.method, path=request.url.path
        )

    register_browser_routes(
        app,
        fake,
        canonical_origin=ORIGIN,
        production=production,
    )
    return TestClient(app, base_url=ORIGIN, client=("127.0.0.1", 12345))


def auth_headers(**extra: str) -> dict[str, str]:
    return {"Cookie": f"{SESSION_COOKIE}={BEARER}", "Origin": ORIGIN, **extra}


@pytest.mark.parametrize(
    "value",
    [
        "null",
        "https://app.example/",
        "https://app.example.",
        "https://app.example:0",
        "https://app.example:",
        "https://app.example:65536",
        "https://u@app.example",
        "https://app%2eexample",
        "https://аpp.example",
        "https://app.example,https://evil.test",
        "https://app.example\\@evil.test",
        "https://app.example\n",
        "https://app.example?x=y",
        "https://app.example?",
        "https://app.example#",
    ],
)
def test_origin_parser_rejects_ambiguous_authority(value: str) -> None:
    with pytest.raises(ValueError):
        _origin(value)


def test_origin_canonical_equivalence_and_referer_path_ignored() -> None:
    assert _origin("HTTPS://APP.EXAMPLE:443") == _origin(ORIGIN)
    assert _origin("https://app.example/path,unicode-עברית?q=a#b", referer=True) == _origin(ORIGIN)


def test_login_form_escaping_cookie_and_nonce_policy() -> None:
    fake = FakeIdentity()
    fake.proof = '"><svg onload="alert(1)">'
    with browser_client(fake) as client:
        response = client.get("/login")
        assert response.status_code == 200
        assert "&lt;svg" in response.text and "<svg" not in response.text
        cookie = response.headers["set-cookie"]
        assert "Secure" in cookie and "HttpOnly" in cookie and "SameSite=lax" in cookie
        assert "Path=/" in cookie and "Domain=" not in cookie and "Max-Age=599" in cookie
        policy = response.headers["content-security-policy"]
        assert "default-src 'none'" in policy and "'strict-dynamic'" in policy
        assert "form-action 'self'" in policy and "'unsafe-inline'" not in policy
        assert "form-action 'self' https://accounts.google.com/o/oauth2/v2/auth" in policy
        assert response.headers["referrer-policy"] == "same-origin"
        assert client.get("/login").headers["content-security-policy"] != policy
        assert response.headers["strict-transport-security"] == "max-age=31536000"


@pytest.mark.parametrize("path", ["/", "/profile", "/api/v1/profile"])
def test_private_projection_no_tenant_secrets_or_sliding_cookie(path: str) -> None:
    fake = FakeIdentity()
    with browser_client(fake) as client:
        response = client.get(path, headers=auth_headers())
        assert response.status_code == 200
        assert "set-cookie" not in response.headers
        assert str(fake.session.actor.tenant_id) not in response.text
        assert str(fake.session.session_id) not in response.text
        assert BEARER not in response.text and BINDER not in response.text
        if path == "/api/v1/profile":
            assert response.json() == {
                "user_id": str(UUID(int=1)),
                "provisioning_state": "catalog_pending",
            }
            assert CSRF not in response.text
        else:
            assert CSRF in response.text and 'action="/logout"' in response.text


@pytest.mark.parametrize(
    "cookie",
    [
        "",
        f"{SESSION_COOKIE}=",
        f"{SESSION_COOKIE}=bad",
        f'{SESSION_COOKIE}="{BEARER}"',
        f"{SESSION_COOKIE}={BEARER}; {SESSION_COOKIE}={BEARER}",
    ],
)
def test_ambiguous_session_cookies_cannot_authenticate(cookie: str) -> None:
    fake = FakeIdentity()
    with browser_client(fake) as client:
        assert client.get("/api/v1/profile", headers={"Cookie": cookie}).status_code == 401


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Origin": "null"},
        {"Origin": "https://evil.test"},
        {"Origin": "https://app.example."},
        {"Referer": "http://app.example/page"},
        {"Origin": ORIGIN, "Sec-Fetch-Site": "same-site"},
        {"Origin": "https://evil.test", "Referer": ORIGIN + "/safe"},
    ],
)
def test_logout_provenance_denial_has_no_revoke(headers: dict[str, str]) -> None:
    fake = FakeIdentity()
    with browser_client(fake) as client:
        response = client.post(
            "/logout",
            headers={"Cookie": f"{SESSION_COOKIE}={BEARER}", **headers},
            data={"csrf": CSRF},
        )
        assert response.status_code == 403
        assert not fake.revoked
        assert not any(name == "logout" for name, _ in fake.calls)


def test_https_referer_fallback_and_logout_current_session() -> None:
    fake = FakeIdentity()
    with browser_client(fake) as client:
        response = client.post(
            "/logout",
            headers={"Cookie": f"{SESSION_COOKIE}={BEARER}", "Referer": ORIGIN + "/profile?q=x"},
            data={"csrf": CSRF},
            follow_redirects=False,
        )
        assert response.status_code == 303 and response.headers["location"] == "/login"
        assert fake.revoked
        cookies = response.headers.get_list("set-cookie")
        assert len(cookies) == 2
        assert all(
            "Max-Age=0" in c and "Secure" in c and "Path=/" in c and "Domain=" not in c
            for c in cookies
        )
        assert (
            client.post("/logout", headers=auth_headers(), data={"csrf": CSRF}).status_code == 401
        )


@pytest.mark.parametrize("body", ["", "csrf=wrong", f"csrf={CSRF}&csrf={CSRF}"])
def test_logout_bad_csrf_has_uniform_forbidden_without_revoke(body: str) -> None:
    fake = FakeIdentity()
    with browser_client(fake) as client:
        response = client.post(
            "/logout",
            headers=auth_headers(**{"Content-Type": "application/x-www-form-urlencoded"}),
            content=body,
        )
        assert response.status_code == 403 and not fake.revoked
        assert response.json()["error"]["code"] == "forbidden"


@pytest.mark.parametrize(
    "content_type",
    [
        "text/plain",
        "application/json",
        "multipart/form-data",
        "application/x-www-form-urlencoded; charset=latin-1",
        "application/x-www-form-urlencoded; charset=UTF-8; charset=UTF-8",
        "application/x-www-form-urlencoded;foo=bar",
    ],
)
def test_exact_media_type_before_logout_dispatch(content_type: str) -> None:
    fake = FakeIdentity()
    with browser_client(fake) as client:
        response = client.post(
            "/logout",
            headers=auth_headers(**{"Content-Type": content_type}),
            content=f"csrf={CSRF}",
        )
        assert response.status_code == 415 and not fake.revoked


def test_form_size_content_length_and_streaming_bounds() -> None:
    fake = FakeIdentity()
    with browser_client(fake) as client:
        headers = auth_headers(**{"Content-Type": "application/x-www-form-urlencoded"})
        assert (
            client.post("/logout", headers=headers, content="csrf=" + "x" * 4096).status_code == 413
        )
        assert (
            client.post(
                "/logout", headers={**headers, "Content-Length": "2"}, content="csrf=long"
            ).status_code
            == 400
        )
        assert (
            client.post(
                "/logout", headers=headers, content=iter([b"csrf=", b"x" * 5000])
            ).status_code
            == 413
        )
        assert not fake.revoked


@pytest.mark.parametrize(
    "query",
    [
        "state=a&state=b&code=x",
        "state=x&code=a&error=denied",
        "state=x",
        "code=x",
        "state=x&code=a&tenant_id=evil",
        "state=x&code=%GG",
        "state=x&code=%ff",
        "state=x&code=",
    ],
)
def test_malformed_callback_generic_html_charges_only_ip_stage(query: str) -> None:
    fake = FakeIdentity()
    with browser_client(fake) as client:
        response = client.get("/auth/google/callback?" + query)
        assert response.status_code == 400
        assert response.headers["content-type"].startswith("text/html")
        assert 'href="/login"' in response.text
        assert "tenant_id" not in response.text and "denied" not in response.text
        calls = [values for name, values in fake.calls if name == "complete"]
        assert len(calls) == 1 and calls[0]["state"] == "" and calls[0]["binder_cookie"] == ""


@pytest.mark.parametrize(
    "status,code",
    [
        (400, "login_failed"),
        (409, "already_authenticated"),
        (429, "rate_limited"),
        (503, "unavailable"),
    ],
)
def test_all_callback_failures_same_unreflected_page(status: int, code: str) -> None:
    fake = FakeIdentity()
    fake.callback_failure = AuthFailure(status, code, 7 if status == 429 else None)
    with browser_client(fake) as client:
        response = client.get(
            "/auth/google/callback?state=x&code=secret&error_description=evil",
            headers={"Cookie": f"{LOGIN_COOKIE}={BINDER}"},
        )
        assert response.status_code == status
        assert (
            "secret" not in response.text
            and "evil" not in response.text
            and code not in response.text
        )
        assert "set-cookie" not in response.headers
        assert "content-security-policy" in response.headers
        if status == 429:
            assert response.headers["retry-after"] == "7"


def test_head_callback_and_get_logout_never_dispatch() -> None:
    fake = FakeIdentity()
    with browser_client(fake) as client:
        assert client.head("/auth/google/callback?state=x&code=y").status_code == 405
        assert client.get("/logout").status_code == 405
        assert not fake.calls


def test_start_blank_optional_invitation_and_trusted_peer_only() -> None:
    fake = FakeIdentity()
    with browser_client(fake) as client:
        response = client.post(
            "/auth/google/start",
            headers={
                "Origin": ORIGIN,
                "Cookie": f"{LOGIN_COOKIE}={BINDER}",
                "X-Forwarded-For": "victim-ip",
            },
            data={"proof": "proof-value", "destination": "home", "invitation": ""},
            follow_redirects=False,
        )
        assert response.status_code == 303
        values = next(v for name, v in fake.calls if name == "start")
        assert values["invitation"] is None and values["ip_key"] == "127.0.0.1"


def test_duplicate_start_proof_charges_only_ip_without_binder_authority() -> None:
    fake = FakeIdentity()
    with browser_client(fake) as client:
        response = client.post(
            "/auth/google/start",
            headers={"Origin": ORIGIN, "Content-Type": "application/x-www-form-urlencoded"},
            content="proof=proof-value&proof=proof-value",
        )
        assert response.status_code == 403
        calls = [values for name, values in fake.calls if name == "start"]
        assert len(calls) == 1
        assert calls[0]["binder_cookie"] == "" and calls[0]["proof"] == ""


def test_query_body_and_header_cannot_supply_actor_or_authenticate() -> None:
    fake = FakeIdentity()
    with browser_client(fake) as client:
        assert (
            client.get("/api/v1/profile?tenant_id=other", headers=auth_headers()).status_code == 400
        )
        assert (
            client.request(
                "GET", "/api/v1/profile", headers=auth_headers(), content="actor=x"
            ).status_code
            == 400
        )
        assert (
            client.get("/api/v1/profile", headers={"Authorization": "Bearer " + BEARER}).status_code
            == 401
        )


def test_safe_headers_apply_to_framework_errors_and_json_no_csp() -> None:
    fake = FakeIdentity()
    with browser_client(fake, production=False) as client:
        for path in ["/unknown", "/api/v1/profile"]:
            response = client.get(path)
            assert response.headers["cache-control"] == "no-store"
            assert response.headers["x-content-type-options"] == "nosniff"
            assert response.headers["referrer-policy"] == "no-referrer"
            assert response.headers["x-frame-options"] == "DENY"
            assert response.headers["cross-origin-opener-policy"] == "same-origin"
            assert "camera=()" in response.headers["permissions-policy"]
            assert "strict-transport-security" not in response.headers
            assert "content-security-policy" not in response.headers


@pytest.mark.parametrize(
    "extra,status",
    [
        ([("Origin", ORIGIN), ("Origin", ORIGIN)], 403),
        (
            [
                ("Origin", ORIGIN),
                ("Sec-Fetch-Site", "same-origin"),
                ("Sec-Fetch-Site", "same-origin"),
            ],
            403,
        ),
        (
            [
                ("Origin", ORIGIN),
                ("Content-Type", "application/x-www-form-urlencoded"),
                ("Content-Type", "application/x-www-form-urlencoded"),
            ],
            415,
        ),
        ([("Origin", ORIGIN), ("Content-Length", "48"), ("Content-Length", "48")], 400),
    ],
)
def test_duplicate_raw_headers_cannot_reach_logout(
    extra: list[tuple[str, str]], status: int
) -> None:
    fake = FakeIdentity()
    headers = [("Cookie", f"{SESSION_COOKIE}={BEARER}"), *extra]
    if not any(name.lower() == "content-type" for name, _ in headers):
        headers.append(("Content-Type", "application/x-www-form-urlencoded"))
    with browser_client(fake) as client:
        response = client.post("/logout", headers=headers, content="csrf=" + CSRF)
        assert response.status_code == status and not fake.revoked


def test_valid_callback_cookie_and_oversized_query_bound() -> None:
    fake = FakeIdentity()
    with browser_client(fake) as client:
        response = client.get(
            "/auth/google/callback?state=state&code=code",
            headers={"Cookie": f"{LOGIN_COOKIE}={BINDER}"},
            follow_redirects=False,
        )
        assert response.status_code == 303 and response.headers["location"] == "/"
        cookie = response.headers["set-cookie"]
        assert cookie.startswith(SESSION_COOKIE + "=")
        assert all(
            flag in cookie
            for flag in ["Secure", "HttpOnly", "SameSite=lax", "Max-Age=2592000", "Path=/"]
        )
        assert "Domain=" not in cookie
        oversized = client.get("/auth/google/callback?state=s&code=" + "x" * 8192)
        assert oversized.status_code == 400
        assert "set-cookie" not in oversized.headers and "x" * 50 not in oversized.text


def test_unexpected_callback_exception_remains_generic_html() -> None:
    class BrokenIdentity(FakeIdentity):
        def complete_login(self, **values: Any) -> Any:
            raise ValueError("provider-token-secret subject private-key")

    with browser_client(BrokenIdentity()) as client:
        response = client.get("/auth/google/callback?state=x&code=y")
        assert response.status_code == 500
        assert response.headers["content-type"].startswith("text/html")
        assert "secret" not in response.text and "subject" not in response.text
        assert "content-security-policy" in response.headers


def test_size_precedes_content_type_and_ambiguous_csrf_transport_denied() -> None:
    fake = FakeIdentity()
    with browser_client(fake) as client:
        assert (
            client.post(
                "/logout",
                headers=auth_headers(**{"Content-Type": "text/plain"}),
                content="x" * 4097,
            ).status_code
            == 413
        )
        assert (
            client.post(
                "/logout",
                headers=auth_headers(**{"X-CSRF-Token": CSRF}),
                data={"csrf": CSRF},
            ).status_code
            == 403
        )
        assert not fake.revoked


@pytest.mark.parametrize("method", ["GET", "POST", "HEAD"])
@pytest.mark.parametrize("path", ["/login", "/", "/profile", "/auth/google/callback", "/unknown"])
@pytest.mark.parametrize("status", [200, 303, 400, 500])
@pytest.mark.parametrize("content_type", ["text/html", "application/json"])
def test_adr012_exact_native_form_policy_matrix(
    method: str, path: str, status: int, content_type: str
) -> None:
    response = Response("", status_code=status, media_type=content_type)
    apply_response_policy(response, production=True, method=method, path=path)
    native_form_page = (
        method == "GET"
        and path in {"/login", "/", "/profile"}
        and status == 200
        and content_type == "text/html"
    )
    assert response.headers["referrer-policy"] == (
        "same-origin" if native_form_page else "no-referrer"
    )
    if content_type == "text/html":
        policy = response.headers["content-security-policy"]
        permitted_google_navigation = native_form_page and path == "/login"
        assert (
            "https://accounts.google.com/o/oauth2/v2/auth" in policy
        ) == permitted_google_navigation
        expected_action = "form-action 'self'" + (
            " https://accounts.google.com/o/oauth2/v2/auth" if permitted_google_navigation else ""
        )
        directives = policy.split("; ")
        assert expected_action in directives
        parsed = dict(d.split(" ", 1) for d in directives)
        assert len(directives) == len(parsed) == 14
        assert re.fullmatch(r"'nonce-[A-Za-z0-9_-]{43}' 'strict-dynamic'", parsed.pop("script-src"))
        assert parsed == {
            "default-src": "'none'",
            "style-src": "'self'",
            "img-src": "'self'",
            "font-src": "'self'",
            "connect-src": "'self'",
            "manifest-src": "'self'",
            "object-src": "'none'",
            "base-uri": "'none'",
            "frame-ancestors": "'none'",
            "form-action": expected_action.removeprefix("form-action "),
            "frame-src": "'none'",
            "media-src": "'none'",
            "worker-src": "'none'",
        }
    else:
        assert "content-security-policy" not in response.headers
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["strict-transport-security"] == "max-age=31536000"


def test_policy_without_request_classification_keeps_strict_default() -> None:
    response = apply_response_policy(HTMLResponse("form"), production=False)
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "form-action 'self';" in response.headers["content-security-policy"]
    assert "accounts.google.com" not in response.headers["content-security-policy"]
    assert "strict-transport-security" not in response.headers
