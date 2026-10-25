"""Real Chromium/TLS/HTTP/DB journeys with a signed synthetic Google transport.

Only the fixed external provider transport is replaced. Browser redirects,
cookies, CSRF, templates, CSP, identity persistence and catalog wiring are real.
No screenshot, HAR or trace retaining credential-bearing DOM is produced.
"""

import base64
import hashlib
import ipaddress
import json
import os
import re
import secrets
import shutil
import socket
import threading
import time
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from urllib.parse import parse_qs, urlencode
from uuid import UUID, uuid4

import httpx
import jwt
import psycopg
import pytest
import uvicorn
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from playwright.sync_api import expect, sync_playwright
from psycopg.conninfo import conninfo_to_dict
from sqlalchemy.engine import URL

from tests.db_support import initialize
from you_story import app as app_module
from you_story.app import create_app
from you_story.identity.infrastructure.config import AuthSettings
from you_story.identity.infrastructure.google import JWKS_URL, TOKEN_URL, GoogleOIDC
from you_story.identity.infrastructure.wiring import create_identity_service
from you_story.shared.config import Settings
from you_story.shared.database import Database

pytestmark = [pytest.mark.browser, pytest.mark.postgres]
_PROVIDER_CANARY = '<img src="https://attacker.invalid/provider" onerror="window.__provider=true">'
_PREFERENCE_CANARY = '<img src="https://attacker.invalid/stored" onerror="window.__stored=true">'
_CONTROL_CANARY = "<script>window.__control=true</script>"


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


@pytest.fixture(scope="module")
def web_application(tmp_path_factory):
    admin, owner, runtime = initialize("005_identity")
    with psycopg.connect(owner) as connection:
        for subject in ["browser-a", "browser-b", "fault-before", "fault-after"]:
            connection.execute(
                "INSERT INTO identity.invitation "
                "(id,token_digest,issuer,expires_at,admission_kind,permitted_subject) "
                "VALUES (%s,%s,'https://accounts.google.com',"
                "clock_timestamp()+interval '1 day','allowlist',%s)",
                (uuid4(), secrets.token_bytes(32), subject),
            )
    values = conninfo_to_dict(runtime)
    url = URL.create(
        "postgresql+psycopg",
        username=values["user"],
        password=values["password"],
        host=values["host"],
        port=int(values["port"]),
        database=values["dbname"],
    ).render_as_string(hide_password=False)
    settings = Settings(database_url=url)
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    origin = f"https://127.0.0.1:{listener.getsockname()[1]}"
    auth = AuthSettings(
        origin=origin,
        client_id="browser-client",
        client_secret="synthetic-client-secret",
        preauth_key=_b64(secrets.token_bytes(32)),
        verifier_key=_b64(secrets.token_bytes(32)),
        ip_key=_b64(secrets.token_bytes(32)),
        production=False,
    )
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    public.update(kid="browser-key", alg="RS256", use="sig")
    pending = {}
    exchanges = []

    def transport(request):
        if str(request.url) == JWKS_URL:
            return httpx.Response(
                200, json={"keys": [public]}, headers={"Cache-Control": "max-age=60"}
            )
        assert str(request.url) == TOKEN_URL
        fields = parse_qs(request.content.decode(), strict_parsing=True)
        entry = pending.pop(fields["code"][0])
        assert (
            _b64(hashlib.sha256(fields["code_verifier"][0].encode()).digest()) == entry["challenge"]
        )
        assert fields["redirect_uri"] == [auth.redirect_uri]
        assert fields["client_id"] == [auth.client_id]
        now = int(time.time())
        token = jwt.encode(
            {
                "iss": "https://accounts.google.com",
                "sub": entry["subject"],
                "aud": auth.client_id,
                "iat": now,
                "exp": now + 120,
                "nonce": entry["nonce"],
                "name": _PROVIDER_CANARY,
                "picture": "https://attacker.invalid/provider-picture",
            },
            key,
            algorithm="RS256",
            headers={"kid": "browser-key"},
        )
        exchanges.append(True)
        return httpx.Response(200, json={"id_token": token, "access_token": "synthetic-discarded"})

    database = Database(settings)
    provider = GoogleOIDC(auth, transport=httpx.MockTransport(transport))
    service = create_identity_service(database, auth, provider=provider)
    app = create_app(settings, auth_settings=auth, auth_service=service)
    directory = tmp_path_factory.mktemp("auth-tls")
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = datetime.now(UTC)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(hours=1))
        .add_extension(
            x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    cert_path, key_path = directory / "certificate.pem", directory / "key.pem"
    cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            access_log=False,
            proxy_headers=False,
            log_level="error",
            ssl_certfile=str(cert_path),
            ssl_keyfile=str(key_path),
        )
    )
    thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started and thread.is_alive() and time.monotonic() < deadline:
            thread.join(0.02)
        assert server.started, "Synthetic HTTPS server failed to start"
        yield SimpleNamespace(
            origin=origin,
            pending=pending,
            exchanges=exchanges,
            owner=owner,
            admin=admin,
            service=service,
            database=database,
        )
    finally:
        server.should_exit = True
        thread.join(10)
        listener.close()
        database.close()
        assert not thread.is_alive(), "HTTPS fixture did not stop"


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as runner:
        chromium = os.environ.get("TEST_CHROMIUM_PATH") or runner.chromium.executable_path
        assert shutil.which(chromium), (
            "Pinned Chromium required; browser evidence cannot be skipped"
        )
        browser = runner.chromium.launch(
            executable_path=chromium, headless=True, args=["--no-sandbox"]
        )
        try:
            yield browser
        finally:
            browser.close()


def _login(page, fixture, subject="browser-a", *, emulate_provider_redirect=True):
    cdp = page.context.new_cdp_session(page)

    def authorize(event):
        target = httpx.URL(event["request"]["url"])
        assert str(target.copy_with(query=None)) == "https://accounts.google.com/o/oauth2/v2/auth"
        query = parse_qs(target.query.decode())
        assert query["scope"] == ["openid profile"]
        assert query["code_challenge_method"] == ["S256"]
        code = _b64(secrets.token_bytes(32))
        fixture.pending[code] = {
            "subject": subject,
            "nonce": query["nonce"][0],
            "challenge": query["code_challenge"][0],
        }
        cdp.send(
            "Fetch.fulfillRequest",
            {
                "requestId": event["requestId"],
                "responseCode": 303,
                "responseHeaders": [
                    {
                        "name": "Location",
                        "value": fixture.origin
                        + "/auth/google/callback?"
                        + urlencode({"code": code, "state": query["state"][0]}),
                    },
                    {"name": "Cache-Control", "value": "no-store"},
                ],
                "body": "",
            },
        )

    # CDP observes the actual redirected Google request after browser CSP checks;
    # unlike page.route, it can replace a later request in the redirect chain.
    # The original start303 and external authorize URL are never rewritten.
    if emulate_provider_redirect:
        cdp.on("Fetch.requestPaused", authorize)
        cdp.send(
            "Fetch.enable",
            {
                "patterns": [
                    {
                        "urlPattern": "https://accounts.google.com/o/oauth2/v2/auth*",
                        "requestStage": "Request",
                    }
                ]
            },
        )
    response = page.goto(fixture.origin + "/login")
    assert response.status == 200
    proof = page.locator('form[action="/auth/google/start"] input[name="proof"]')
    expect(proof).to_have_count(1)
    with page.expect_response(
        lambda response: response.url == fixture.origin + "/auth/google/start"
    ) as started:
        page.locator('form[action="/auth/google/start"] button[type="submit"]').click()
    selected = {
        name: started.value.request.headers.get(name)
        for name in ["origin", "sec-fetch-site", "referer", "content-type"]
    }
    assert started.value.status == 303, (
        "Login start must redirect before provider navigation",
        selected,
        [cookie["name"] for cookie in page.context.cookies()],
    )
    page.wait_for_url(fixture.origin + "/")
    expect(page.locator('form[action="/logout"]')).to_have_count(1)
    if emulate_provider_redirect:
        cdp.send("Fetch.disable")
    cdp.detach()


def test_login_profile_logout_and_revoked_cookie(browser, web_application):
    context = browser.new_context(ignore_https_errors=True)
    try:
        page = context.new_page()
        _login(page, web_application)
        cookie = next(c for c in context.cookies() if c["name"] == "__Host-you_story_session")
        assert cookie["secure"] and cookie["httpOnly"] and cookie["sameSite"] == "Lax"
        assert cookie["path"] == "/"
        profile = context.request.get(web_application.origin + "/api/v1/profile")
        assert profile.status == 200 and profile.headers["cache-control"] == "no-store"
        assert set(profile.json()) == {"user_id", "provisioning_state"}
        assert UUID(profile.json()["user_id"])
        user = UUID(profile.json()["user_id"])
        with psycopg.connect(web_application.admin) as connection:
            tenant = connection.execute(
                "SELECT id FROM identity.tenant WHERE owner_user_id=%s", (user,)
            ).fetchone()[0]
            connection.execute(
                "INSERT INTO identity.user_preference(tenant_id,id,user_id,settings) "
                "VALUES (%s,%s,%s,%s::jsonb)",
                (tenant, uuid4(), user, json.dumps({"name": _PREFERENCE_CANARY})),
            )
            connection.execute(
                "INSERT INTO identity.invitation(id,token_digest,issuer,expires_at,"
                "consumed_at,consumed_provider,consumed_subject,consumed_user_id) "
                "VALUES (%s,%s,'https://accounts.google.com',clock_timestamp()+interval '1 day',"
                "clock_timestamp(),'https://accounts.google.com',%s,%s)",
                (uuid4(), secrets.token_bytes(32), _CONTROL_CANARY, user),
            )
        page.goto(web_application.origin + "/profile")
        for canary in [_PROVIDER_CANARY, _PREFERENCE_CANARY, _CONTROL_CANARY]:
            assert canary not in page.content()
            assert (
                canary not in context.request.get(web_application.origin + "/api/v1/profile").text()
            )
        assert "attacker.invalid" not in page.content() and "window.__control" not in page.content()
        assert page.locator("img").count() == 0
        assert page.evaluate(
            "[window.__provider,window.__stored,window.__control].every(v => v === undefined)"
        )
        page.locator('form[action="/logout"] button[type="submit"]').click()
        page.wait_for_url(web_application.origin + "/login")
        assert not any(c["name"] == "__Host-you_story_session" for c in context.cookies())
        replay = context.request.get(
            web_application.origin + "/api/v1/profile",
            headers={"Cookie": cookie["name"] + "=" + cookie["value"]},
        )
        assert replay.status == 401
        assert web_application.exchanges
    finally:
        context.close()


def test_invalid_csrf_get_logout_and_request_actor_cannot_switch(browser, web_application):
    context = browser.new_context(ignore_https_errors=True)
    try:
        page = context.new_page()
        _login(page, web_application, "browser-b")
        bad = page.evaluate("""async () => {
          const r = await fetch('/logout', {method:'POST',
            headers:{'Content-Type':'application/x-www-form-urlencoded'},
            body:'csrf='+'A'.repeat(43)}); return r.status;
        }""")
        assert bad == 403
        assert context.request.get(web_application.origin + "/logout").status == 405
        profile = context.request.get(
            web_application.origin
            + "/api/v1/profile?"
            + urlencode({"tenant_id": str(uuid4()), "actor_id": str(uuid4())})
        )
        assert profile.status == 400
        own = context.request.get(web_application.origin + "/api/v1/profile")
        assert own.status == 200
        with psycopg.connect(web_application.owner) as connection:
            assert connection.execute(
                "SELECT user_id FROM identity.external_identity WHERE subject='browser-b'"
            ).fetchone()[0] == UUID(own.json()["user_id"])
    finally:
        context.close()


def test_two_browser_accounts_and_logout_are_independent(browser, web_application):
    a, b = [browser.new_context(ignore_https_errors=True) for _ in range(2)]
    try:
        first, second = a.new_page(), b.new_page()
        _login(first, web_application, "browser-a")
        _login(second, web_application, "browser-b")
        a_profile = a.request.get(web_application.origin + "/api/v1/profile").json()
        b_profile = b.request.get(web_application.origin + "/api/v1/profile").json()
        assert a_profile["user_id"] != b_profile["user_id"]
        assert set(a_profile) == set(b_profile) == {"user_id", "provisioning_state"}
        first.locator('form[action="/logout"] button[type="submit"]').click()
        first.wait_for_url(web_application.origin + "/login")
        assert a.request.get(web_application.origin + "/api/v1/profile").status == 401
        assert b.request.get(web_application.origin + "/api/v1/profile").json() == b_profile
    finally:
        a.close()
        b.close()


def test_csp_blocks_injected_script_and_reflected_input(browser, web_application):
    context = browser.new_context(ignore_https_errors=True)
    try:
        page = context.new_page()

        def inject_probe(route):
            response = route.fetch()
            nonce = re.search(
                r"script-src 'nonce-([^']+)'", response.headers["content-security-policy"]
            )
            assert nonce
            body = response.text() + "<script>window.__xss_probe = true</script>"
            body += f'<script nonce="{nonce.group(1)}">window.__csp_positive = true</script>'
            route.fulfill(response=response, body=body)

        # Test-only response mutation retains the actual enforced production CSP.
        page.route(web_application.origin + "/auth/google/callback?**", inject_probe)
        payload = '<img src=x onerror="window.__reflected_probe=true">'
        response = page.goto(
            web_application.origin
            + "/auth/google/callback?"
            + urlencode({"state": "A" * 43, "error": "access_denied", "error_description": payload})
        )
        assert response.status == 400
        assert page.evaluate("window.__xss_probe === undefined")
        assert page.evaluate("window.__reflected_probe === undefined")
        assert page.evaluate("window.__csp_positive === true")
        assert payload not in page.content()
        assert response.headers["referrer-policy"] == "no-referrer"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
    finally:
        context.close()


@pytest.mark.parametrize(
    "document,target",
    [
        ("/login", "https://attacker.invalid/collect"),
        ("/login", "https://accounts.google.com/unapproved"),
        ("/profile", "https://accounts.google.com/o/oauth2/v2/auth"),
    ],
)
def test_form_exception_cannot_reach_other_provider_or_document(
    browser, web_application, document, target
):
    context = browser.new_context(ignore_https_errors=True)
    try:
        page = context.new_page()
        if document == "/profile":
            _login(page, web_application)
        response = page.goto(web_application.origin + document)
        assert response.status == 200
        assert response.headers["referrer-policy"] == "same-origin"
        cdp = context.new_cdp_session(page)
        requests = []

        def unexpected(event):
            requests.append(True)
            cdp.send(
                "Fetch.failRequest",
                {"requestId": event["requestId"], "errorReason": "BlockedByClient"},
            )

        cdp.on("Fetch.requestPaused", unexpected)
        cdp.send(
            "Fetch.enable",
            {
                "patterns": [
                    {"urlPattern": "https://accounts.google.com/*", "requestStage": "Request"},
                    {"urlPattern": "https://attacker.invalid/*", "requestStage": "Request"},
                ]
            },
        )
        # No raw blockedURI or secret-bearing form fields are collected.
        page.evaluate("""() => {
          window.__blockedForms = [];
          document.addEventListener('securitypolicyviolation', event =>
            window.__blockedForms.push(event.effectiveDirective));
        }""")
        page.evaluate(
            """target => {
          const form = document.createElement('form');
          form.action = target; form.method = 'POST';
          document.body.append(form); form.submit();
        }""",
            target,
        )
        page.wait_for_function("window.__blockedForms.includes('form-action')")
        assert requests == []
    finally:
        context.close()


@pytest.mark.parametrize("failure", ["before", "after"])
def test_pending_catalog_failure_keeps_session_and_fresh_login_retries(
    browser, web_application, monkeypatch, failure
):
    original_ensure = app_module.ensure_personal_catalog
    original_mark = web_application.service.mark_catalog_ready
    calls = {"ensure": 0, "mark": 0}
    injecting = True

    def ensure(database, actor):
        calls["ensure"] += 1
        if injecting and failure == "before":
            raise RuntimeError("synthetic pair failure")
        return original_ensure(database, actor)

    def mark(session):
        calls["mark"] += 1
        if injecting and failure == "after":
            raise RuntimeError("synthetic ready failure")
        return original_mark(session)

    monkeypatch.setattr(app_module, "ensure_personal_catalog", ensure)
    monkeypatch.setattr(web_application.service, "mark_catalog_ready", mark)
    context = browser.new_context(ignore_https_errors=True)
    try:
        page = context.new_page()
        _login(page, web_application, "fault-" + failure)
        pending = context.request.get(web_application.origin + "/api/v1/profile")
        assert pending.status == 200 and pending.json()["provisioning_state"] == "catalog_pending"
        user = UUID(pending.json()["user_id"])
        first_calls = {"ensure": 1, "mark": 0 if failure == "before" else 1}
        assert calls == first_calls

        def persisted():
            with psycopg.connect(web_application.admin) as connection:
                states = connection.execute(
                    "SELECT t.id,u.state,t.state,e.state,t.provisioning_state "
                    'FROM identity.tenant t JOIN identity."user" u ON u.id=t.owner_user_id '
                    "JOIN identity.external_identity e ON e.user_id=u.id WHERE u.id=%s",
                    (user,),
                ).fetchone()
                counts = [
                    connection.execute(
                        f"SELECT count(*) FROM catalog.{table} WHERE tenant_id=%s", (states[0],)
                    ).fetchone()[0]
                    for table in ["catalog", "catalog_grant"]
                ]
                consumed = connection.execute(
                    "SELECT id,consumed_at,consumed_user_id FROM identity.invitation "
                    "WHERE admission_kind='allowlist' AND permitted_subject=%s",
                    ("fault-" + failure,),
                ).fetchone()
                return states, counts, consumed

        initial_states, initial_counts, initial_invitation = persisted()
        assert initial_states[1:] == ("active", "active", "active", "catalog_pending")
        assert initial_counts == ([0, 0] if failure == "before" else [1, 1])
        assert initial_invitation[1] is not None and initial_invitation[2] == user
        for path in ["/profile", "/", "/profile"]:
            response = page.goto(web_application.origin + path)
            assert response.status == 200
            expect(page.locator('form[action="/logout"]')).to_have_count(1)
        assert calls == first_calls
        assert persisted() == (initial_states, initial_counts, initial_invitation)
        page.locator('form[action="/logout"] button[type="submit"]').click()
        page.wait_for_url(web_application.origin + "/login")
        assert context.request.get(web_application.origin + "/api/v1/profile").status == 401
        assert calls == first_calls

        injecting = False
        _login(page, web_application, "fault-" + failure)
        ready = context.request.get(web_application.origin + "/api/v1/profile")
        assert ready.status == 200 and ready.json() == {
            "user_id": str(user),
            "provisioning_state": "ready",
        }
        final_states, final_counts, final_invitation = persisted()
        assert final_states[1:] == ("active", "active", "active", "ready")
        assert final_counts == [1, 1] and final_invitation == initial_invitation
        assert calls == {"ensure": 2, "mark": 1 if failure == "before" else 2}
        page.goto(web_application.origin + "/profile")
        page.locator('form[action="/logout"] button[type="submit"]').click()
        page.wait_for_url(web_application.origin + "/login")
        assert context.request.get(web_application.origin + "/api/v1/profile").status == 401
    finally:
        context.close()
