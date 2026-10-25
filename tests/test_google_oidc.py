"""Synthetic maintained-library OIDC evidence; no live provider or credentials."""

from __future__ import annotations

import base64
import json
import time
from typing import Any
from urllib.parse import parse_qs, urlsplit

import anyio
import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from you_story.identity.infrastructure.config import AuthSettings
from you_story.identity.infrastructure.crypto import token_digest
from you_story.identity.infrastructure.google import (
    AUTHORIZE_URL,
    ISSUER,
    JWKS_URL,
    TOKEN_URL,
    GoogleOIDC,
    ProviderError,
)

NOW = 1800000000
NONCE_RAW = b"n" * 32
NONCE = base64.urlsafe_b64encode(NONCE_RAW).decode().rstrip("=")
VERIFIER = base64.urlsafe_b64encode(b"v" * 32).decode().rstrip("=")
NONCE_DIGEST = token_digest("nonce", NONCE_RAW)


@pytest.fixture(scope="module")
def signing_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def settings() -> AuthSettings:
    keys = [
        base64.urlsafe_b64encode(bytes([value]) * 32).decode().rstrip("=") for value in (1, 2, 3)
    ]
    return AuthSettings(
        origin="https://app.example",
        client_id="fixture.apps.googleusercontent.com",
        client_secret="synthetic-client-secret",
        preauth_key=keys[0],
        verifier_key=keys[1],
        ip_key=keys[2],
    )


def claims(settings: AuthSettings, **changes: Any) -> dict[str, Any]:
    return {
        "iss": ISSUER,
        "sub": "fixture-google-subject",
        "aud": settings.client_id,
        "exp": NOW + 300,
        "iat": NOW,
        "nonce": NONCE,
    } | changes


def signed(key: rsa.RSAPrivateKey, payload: dict[str, Any], **headers: Any) -> str:
    return jwt.encode(payload, key, algorithm="RS256", headers={"kid": "fixture-key"} | headers)


def jwk(key: rsa.RSAPrivateKey, kid: str = "fixture-key") -> dict[str, Any]:
    return json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key())) | {
        "kid": kid,
        "alg": "RS256",
        "use": "sig",
    }


class Provider:
    def __init__(self, token: str, key: rsa.RSAPrivateKey) -> None:
        self.token = token
        self.keys = [jwk(key)]
        self.requests: list[httpx.Request] = []
        self.token_status = 200
        self.key_status = 200
        self.cache_control = "public, max-age=3600"
        self.age = "0"

    def respond(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if str(request.url) == TOKEN_URL:
            return httpx.Response(self.token_status, json={"id_token": self.token})
        assert str(request.url) == JWKS_URL
        return httpx.Response(
            self.key_status,
            json={"keys": self.keys},
            headers={"Cache-Control": self.cache_control, "Age": self.age},
        )

    def adapter(self, settings: AuthSettings, **kwargs: Any) -> GoogleOIDC:
        return GoogleOIDC(
            settings, transport=httpx.MockTransport(self.respond), clock=lambda: NOW, **kwargs
        )

    @property
    def key_calls(self) -> int:
        return sum(str(request.url) == JWKS_URL for request in self.requests)


def exchange(adapter: GoogleOIDC) -> Any:
    return adapter.exchange(code="synthetic-code", verifier=VERIFIER, nonce_digest=NONCE_DIGEST)


def test_exact_authorization_request(settings: AuthSettings) -> None:
    url = GoogleOIDC(settings).authorize_url(state=NONCE, nonce=NONCE, challenge=VERIFIER)
    assert url.split("?", 1)[0] == AUTHORIZE_URL
    assert parse_qs(urlsplit(url).query) == {
        "client_id": [settings.client_id],
        "redirect_uri": [settings.redirect_uri],
        "response_type": ["code"],
        "scope": ["openid profile"],
        "state": [NONCE],
        "nonce": [NONCE],
        "code_challenge": [VERIFIER],
        "code_challenge_method": ["S256"],
    }
    with pytest.raises(ProviderError):
        GoogleOIDC(settings).authorize_url(state="bad", nonce=NONCE, challenge=VERIFIER)


@pytest.mark.parametrize("issuer", [ISSUER, "accounts.google.com"])
def test_valid_library_signature_and_exact_token_request(
    settings: AuthSettings, signing_key: rsa.RSAPrivateKey, issuer: str
) -> None:
    provider = Provider(signed(signing_key, claims(settings, iss=issuer)), signing_key)
    identity = exchange(provider.adapter(settings))
    assert identity.issuer == ISSUER
    assert identity.subject == "fixture-google-subject"
    assert len(provider.requests) == 2
    token_request = provider.requests[0]
    assert token_request.method == "POST"
    assert parse_qs(token_request.content.decode()) == {
        "grant_type": ["authorization_code"],
        "code": ["synthetic-code"],
        "client_id": [settings.client_id],
        "client_secret": [settings.client_secret.get_secret_value()],
        "redirect_uri": [settings.redirect_uri],
        "code_verifier": [VERIFIER],
    }
    assert token_request.extensions["timeout"]["connect"] == 5
    assert token_request.extensions["timeout"]["read"] == 10
    assert token_request.headers["Accept-Encoding"] == "identity"


@pytest.mark.parametrize(
    "changes",
    [
        {"iss": "https://evil.example"},
        {"iss": [ISSUER]},
        {"sub": ""},
        {"sub": "x" * 256},
        {"sub": "שלום"},
        {"sub": 123},
        {"aud": "other-client"},
        {"aud": []},
        {"aud": ["other-client", ""]},
        {"aud": [True]},
        {"aud": None},
        {"azp": "other-client"},
        {"azp": True},
        {"exp": NOW - 60},
        {"exp": True},
        {"exp": str(NOW)},
        {"exp": float(NOW)},
        {"exp": None},
        {"iat": NOW + 61},
        {"iat": NOW - 661},
        {"iat": False},
        {"iat": str(NOW)},
        {"nbf": NOW + 61},
        {"nbf": True},
        {"nbf": "1800000000"},
        {"nonce": "x" * 43},
        {"nonce": NONCE + "="},
        {"nonce": None},
    ],
)
def test_strict_claim_rejections(
    settings: AuthSettings, signing_key: rsa.RSAPrivateKey, changes: dict[str, Any]
) -> None:
    provider = Provider(signed(signing_key, claims(settings, **changes)), signing_key)
    with pytest.raises(ProviderError, match="^Google sign-in failed$"):
        exchange(provider.adapter(settings))


@pytest.mark.parametrize("missing", ["iss", "sub", "aud", "exp", "iat", "nonce"])
def test_required_claims(
    settings: AuthSettings, signing_key: rsa.RSAPrivateKey, missing: str
) -> None:
    payload = claims(settings)
    del payload[missing]
    provider = Provider(signed(signing_key, payload), signing_key)
    with pytest.raises(ProviderError):
        exchange(provider.adapter(settings))


@pytest.mark.parametrize(
    "changes",
    [{"exp": NOW - 59}, {"iat": NOW + 60}, {"iat": NOW - 660}, {"nbf": NOW + 60}],
)
def test_exact_allowed_time_boundaries(
    settings: AuthSettings, signing_key: rsa.RSAPrivateKey, changes: dict[str, Any]
) -> None:
    provider = Provider(signed(signing_key, claims(settings, **changes)), signing_key)
    assert exchange(provider.adapter(settings)).subject == "fixture-google-subject"


def test_multiple_audiences_require_exact_azp(
    settings: AuthSettings, signing_key: rsa.RSAPrivateKey
) -> None:
    provider = Provider(
        signed(signing_key, claims(settings, aud=[settings.client_id, "other"])), signing_key
    )
    with pytest.raises(ProviderError):
        exchange(provider.adapter(settings))
    provider.token = signed(
        signing_key,
        claims(settings, aud=[settings.client_id, "other"], azp=settings.client_id),
    )
    assert exchange(provider.adapter(settings)).issuer == ISSUER


@pytest.mark.parametrize(
    "headers",
    [
        {"kid": "unknown"},
        {"kid": ""},
        {"jku": "https://attacker.example/keys"},
        {"x5u": "https://attacker.example/cert"},
        {"crit": ["unknown"]},
        {"b64": False},
    ],
)
def test_untrusted_signing_metadata_never_selects_url(
    settings: AuthSettings, signing_key: rsa.RSAPrivateKey, headers: dict[str, Any]
) -> None:
    provider = Provider(signed(signing_key, claims(settings), **headers), signing_key)
    with pytest.raises(ProviderError):
        exchange(provider.adapter(settings))
    assert all(str(request.url) in {TOKEN_URL, JWKS_URL} for request in provider.requests)
    assert provider.key_calls <= 1


@pytest.mark.parametrize("algorithm", ["none", "HS256"])
def test_unsigned_and_symmetric_rejected_before_key_fetch(
    settings: AuthSettings, signing_key: rsa.RSAPrivateKey, algorithm: str
) -> None:
    token = jwt.encode(
        claims(settings),
        "" if algorithm == "none" else "fixture-hmac-key",
        algorithm=algorithm,
        headers={"kid": "fixture-key"},
    )
    provider = Provider(token, signing_key)
    with pytest.raises(ProviderError):
        exchange(provider.adapter(settings))
    assert provider.key_calls == 0


def test_wrong_signature(settings: AuthSettings, signing_key: rsa.RSAPrivateKey) -> None:
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    provider = Provider(signed(other_key, claims(settings)), signing_key)
    with pytest.raises(ProviderError):
        exchange(provider.adapter(settings))


def raw_token(key: rsa.RSAPrivateKey, header: bytes, payload: bytes) -> str:
    def encode(value: bytes) -> bytes:
        return base64.urlsafe_b64encode(value).rstrip(b"=")

    body = encode(header) + b"." + encode(payload)
    signature = key.sign(body, padding.PKCS1v15(), hashes.SHA256())
    return (body + b"." + encode(signature)).decode()


@pytest.mark.parametrize("kind", ["header", "claim", "nan", "infinity"])
def test_duplicate_and_nonfinite_signed_json_rejected(
    settings: AuthSettings, signing_key: rsa.RSAPrivateKey, kind: str
) -> None:
    header = b'{"alg":"RS256","kid":"fixture-key"}'
    payload = json.dumps(claims(settings)).encode()
    if kind == "header":
        header = b'{"alg":"HS256","alg":"RS256","kid":"fixture-key"}'
    elif kind == "claim":
        payload = payload[:-1] + b',"sub":"other"}'
    elif kind == "nan":
        payload = payload[:-1] + b',"extra":NaN}'
    else:
        payload = payload[:-1] + b',"extra":Infinity}'
    provider = Provider(raw_token(signing_key, header, payload), signing_key)
    with pytest.raises(ProviderError):
        exchange(provider.adapter(settings))
    assert provider.key_calls == 0


@pytest.mark.parametrize("status", [302, 400, 500])
def test_token_failure_no_redirect_retry_or_detail(
    settings: AuthSettings, signing_key: rsa.RSAPrivateKey, status: int
) -> None:
    provider = Provider("canary-token", signing_key)
    provider.token_status = status
    with pytest.raises(ProviderError) as failure:
        exchange(provider.adapter(settings))
    assert str(failure.value) == "Google sign-in failed"
    assert len(provider.requests) == 1


def test_provider_network_error_never_exposes_exception(settings: AuthSettings) -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        raise httpx.ConnectError("credential-canary query-canary", request=request)

    adapter = GoogleOIDC(settings, transport=httpx.MockTransport(handler))
    with pytest.raises(ProviderError) as failure:
        exchange(adapter)
    assert str(failure.value) == "Google sign-in failed"
    assert calls == [TOKEN_URL]


@pytest.mark.parametrize(
    "code,verifier,digest",
    [
        ("", VERIFIER, NONCE_DIGEST),
        ("x" * 8193, VERIFIER, NONCE_DIGEST),
        ("synthetic", "malformed", NONCE_DIGEST),
        ("synthetic", VERIFIER, b"short"),
    ],
)
def test_invalid_exchange_values_fail_before_network(
    settings: AuthSettings, code: str, verifier: str, digest: bytes
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        pytest.fail("invalid input reached provider")

    adapter = GoogleOIDC(settings, transport=httpx.MockTransport(handler))
    with pytest.raises(ProviderError):
        adapter.exchange(code=code, verifier=verifier, nonce_digest=digest)


@pytest.mark.parametrize(
    "body,headers",
    [
        (b'{"id_token":"a","id_token":"b"}', {}),
        (b"[]", {}),
        (b"x" * 131073, {}),
        (b"{}", {"Content-Length": "131073"}),
        (b"{}", {"Content-Type": "text/html"}),
        (b"{}", {"Content-Encoding": "gzip"}),
    ],
)
def test_response_shape_and_byte_bounds(
    settings: AuthSettings, body: bytes, headers: dict[str, str]
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=body, headers={"Content-Type": "application/json"} | headers
        )

    adapter = GoogleOIDC(settings, transport=httpx.MockTransport(handler))
    with pytest.raises(ProviderError):
        exchange(adapter)


def test_streamed_size_without_content_length(settings: AuthSettings) -> None:
    class LargeStream(httpx.AsyncByteStream):
        async def __aiter__(self) -> Any:
            for _ in range(10):
                yield b"x" * 16384

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, stream=LargeStream(), headers={"Content-Type": "application/json"}
        )

    with pytest.raises(ProviderError):
        exchange(GoogleOIDC(settings, transport=httpx.MockTransport(handler)))


@pytest.mark.parametrize(
    "cache_control,age,ttl",
    [("max-age=7200", "0", 3600), ("max-age=30", "10", 20), ("no-store", "0", 0)],
)
def test_jwks_cache_ttl_and_refresh_failure_no_stale(
    settings: AuthSettings,
    signing_key: rsa.RSAPrivateKey,
    cache_control: str,
    age: str,
    ttl: int,
) -> None:
    provider = Provider(signed(signing_key, claims(settings)), signing_key)
    provider.cache_control, provider.age = cache_control, age
    clock = [float(NOW)]
    adapter = GoogleOIDC(
        settings,
        transport=httpx.MockTransport(provider.respond),
        clock=lambda: clock[0],
        cache_clock=lambda: clock[0],
    )
    assert exchange(adapter).issuer == ISSUER
    if ttl:
        assert exchange(adapter).issuer == ISSUER
        assert provider.key_calls == 1
    clock[0] += ttl
    provider.key_status = 503
    with pytest.raises(ProviderError):
        exchange(adapter)
    assert provider.key_calls == 2


def test_unknown_cached_kid_one_refresh(
    settings: AuthSettings, signing_key: rsa.RSAPrivateKey
) -> None:
    provider = Provider(signed(signing_key, claims(settings)), signing_key)
    adapter = provider.adapter(settings)
    assert exchange(adapter).issuer == ISSUER
    provider.token = signed(signing_key, claims(settings), kid="rotated")
    provider.keys = [jwk(signing_key, "rotated")]
    assert exchange(adapter).issuer == ISSUER
    assert provider.key_calls == 2
    provider.token = signed(signing_key, claims(settings), kid="unknown")
    with pytest.raises(ProviderError):
        exchange(adapter)
    assert provider.key_calls == 3


@pytest.mark.parametrize("mutation", ["duplicate", "private", "weak", "hmac", "not-signature"])
def test_jwks_key_constraints(
    settings: AuthSettings, signing_key: rsa.RSAPrivateKey, mutation: str
) -> None:
    provider = Provider(signed(signing_key, claims(settings)), signing_key)
    if mutation == "duplicate":
        provider.keys *= 2
    elif mutation == "private":
        provider.keys[0]["d"] = "AA"
    elif mutation == "weak":
        provider.keys = [jwk(rsa.generate_private_key(public_exponent=65537, key_size=1024))]
    elif mutation == "hmac":
        provider.keys[0]["kty"] = "oct"
    else:
        provider.keys[0]["use"] = "enc"
    with pytest.raises(ProviderError):
        exchange(provider.adapter(settings))


def test_overall_deadline_includes_streamed_body(settings: AuthSettings) -> None:
    class StalledStream(httpx.AsyncByteStream):
        async def __aiter__(self) -> Any:
            yield b"{"
            await anyio.sleep_forever()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, stream=StalledStream(), headers={"Content-Type": "application/json"}
        )

    start = time.monotonic()
    with pytest.raises(ProviderError):
        exchange(GoogleOIDC(settings, transport=httpx.MockTransport(handler)))
    assert 9 <= time.monotonic() - start < 12


@pytest.mark.parametrize("secondary", [" ", "a b", "a\x00b", "a\x7fb", "é", "x" * 256])
def test_every_audience_is_a_bounded_visible_ascii_client(
    settings: AuthSettings, signing_key: rsa.RSAPrivateKey, secondary: str
) -> None:
    token = signed(
        signing_key,
        claims(settings, aud=[settings.client_id, secondary], azp=settings.client_id),
    )
    with pytest.raises(ProviderError):
        exchange(Provider(token, signing_key).adapter(settings))


def test_combined_token_and_key_fetch_share_one_total_deadline(
    settings: AuthSettings, signing_key: rsa.RSAPrivateKey
) -> None:
    calls = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        await anyio.sleep(6)
        if str(request.url) == TOKEN_URL:
            return httpx.Response(200, json={"id_token": signed(signing_key, claims(settings))})
        return httpx.Response(200, json={"keys": [jwk(signing_key)]})

    start = time.monotonic()
    with pytest.raises(ProviderError):
        exchange(GoogleOIDC(settings, transport=httpx.MockTransport(handler), clock=lambda: NOW))
    assert calls == [TOKEN_URL, JWKS_URL]
    assert 9 <= time.monotonic() - start < 12
