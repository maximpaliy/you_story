"""Fixed-endpoint Google OIDC boundary with bounded I/O and strict claim validation."""

from __future__ import annotations

import base64
import hmac
import json
import re
import time
from collections.abc import Callable
from typing import Any
from urllib.parse import urlencode

import anyio
import httpx
import jwt

from you_story.identity.infrastructure.config import AuthSettings
from you_story.identity.infrastructure.crypto import decode_token, token_digest
from you_story.identity.public import VerifiedIdentity

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
ISSUER = "https://accounts.google.com"
_MAX_RESPONSE_BYTES = 131072
_MAX_TOKEN_BYTES = 32768
_MAX_CODE_BYTES = 8192
_SEGMENT = re.compile(r"^[A-Za-z0-9_-]+$")


class ProviderError(Exception):
    """Uniform failure without provider/request/credential data."""


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def _constant(_: str) -> Any:
    raise ValueError("nonfinite JSON value")


def _json_object(raw: bytes) -> dict[str, Any]:
    value: Any = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_constant)
    if not isinstance(value, dict):
        raise ValueError("JSON object required")
    return value


def _segment(value: str) -> dict[str, Any]:
    if not _SEGMENT.fullmatch(value):
        raise ValueError("invalid token encoding")
    raw = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
    if base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii") != value:
        raise ValueError("noncanonical token encoding")
    return _json_object(raw)


def _numeric_date(claims: dict[str, Any], name: str) -> int:
    value = claims.get(name)
    if type(value) is not int:
        raise ValueError("invalid NumericDate")
    return value


class GoogleOIDC:
    """Synchronous public port; production calls run on the HTTP worker thread.

    Transport and clock injection are composition seams for synthetic tests;
    endpoint URLs, TLS verification, timeouts and algorithm policy are fixed.
    No token/claim/provider body is logged or placed in a failure exception.
    """

    def __init__(
        self,
        settings: AuthSettings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        clock: Callable[[], float] = time.time,
        cache_clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._settings = settings
        self._transport = transport
        self._clock = clock
        self._cache_clock = cache_clock
        self._keys: dict[str, jwt.PyJWK] = {}
        self._keys_expire_at = 0.0

    def authorize_url(self, *, state: str, nonce: str, challenge: str) -> str:
        try:
            decode_token(state)
            decode_token(nonce)
            decode_token(challenge)
        except (ValueError, TypeError):
            raise ProviderError("Google sign-in failed") from None
        return (
            AUTHORIZE_URL
            + "?"
            + urlencode(
                {
                    "client_id": self._settings.client_id,
                    "redirect_uri": self._settings.redirect_uri,
                    "response_type": "code",
                    "scope": "openid profile",
                    "state": state,
                    "nonce": nonce,
                    "code_challenge": challenge,
                    "code_challenge_method": "S256",
                }
            )
        )

    def exchange(self, *, code: str, verifier: str, nonce_digest: bytes) -> VerifiedIdentity:
        try:
            if not isinstance(code, str) or not 1 <= len(code.encode()) <= _MAX_CODE_BYTES:
                raise ValueError("invalid code")
            decode_token(verifier)
            if not isinstance(nonce_digest, bytes) or len(nonce_digest) != 32:
                raise ValueError("invalid nonce digest")
            return anyio.run(self._exchange, code, verifier, nonce_digest)
        except Exception:
            # Never propagate a provider response, token URL, credential or library
            # exception through HTTP/telemetry. An ambiguous exchange is not retried.
            raise ProviderError("Google sign-in failed") from None

    async def _request(
        self, client: httpx.AsyncClient, method: str, url: str, **kwargs: Any
    ) -> tuple[dict[str, Any], httpx.Headers]:
        # The scope includes connection, headers and the entire streamed body;
        # HTTPX's per-read timeout alone is not an overall deadline.
        with anyio.fail_after(10):
            async with client.stream(method, url, **kwargs) as response:
                if response.status_code != 200:
                    raise ValueError("provider unavailable")
                if response.headers.get("content-type", "").split(";", 1)[0] != "application/json":
                    raise ValueError("invalid response type")
                if response.headers.get("content-encoding", "identity").lower() != "identity":
                    raise ValueError("unsupported response encoding")
                content_length = response.headers.get("content-length")
                if content_length is not None and (
                    not content_length.isdecimal() or int(content_length) > _MAX_RESPONSE_BYTES
                ):
                    raise ValueError("oversized response")
                raw = bytearray()
                async for chunk in response.aiter_bytes():
                    if len(raw) + len(chunk) > _MAX_RESPONSE_BYTES:
                        raise ValueError("oversized response")
                    raw.extend(chunk)
                return _json_object(bytes(raw)), response.headers

    async def _exchange(self, code: str, verifier: str, nonce_digest: bytes) -> VerifiedIdentity:
        # The callback's exchange budget also covers a required JWKS refresh,
        # rather than silently granting another ten seconds per network stage.
        with anyio.fail_after(10):
            return await self._exchange_inner(code, verifier, nonce_digest)

    async def _exchange_inner(
        self, code: str, verifier: str, nonce_digest: bytes
    ) -> VerifiedIdentity:
        async with httpx.AsyncClient(
            transport=self._transport,
            timeout=httpx.Timeout(10, connect=5),
            follow_redirects=False,
            verify=True,
            headers={"Accept-Encoding": "identity"},
        ) as client:
            payload, _ = await self._request(
                client,
                "POST",
                TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": self._settings.client_id,
                    "client_secret": self._settings.client_secret.get_secret_value(),
                    "redirect_uri": self._settings.redirect_uri,
                    "code_verifier": verifier,
                },
                headers={"Accept": "application/json"},
            )
            token = payload.get("id_token")
            if not isinstance(token, str) or not 1 <= len(token) <= _MAX_TOKEN_BYTES:
                raise ValueError("invalid ID token")
            parts = token.split(".")
            if len(parts) != 3:
                raise ValueError("invalid ID token")
            header, claims = _segment(parts[0]), _segment(parts[1])
            kid = header.get("kid")
            if (
                header.get("alg") != "RS256"
                or not isinstance(kid, str)
                or not 1 <= len(kid) <= 256
                or "jku" in header
                or "x5u" in header
                or "crit" in header
                or "b64" in header
            ):
                raise ValueError("invalid signing metadata")
            key = await self._key(client, kid)
            jwt.decode(
                token,
                key.key,
                algorithms=["RS256"],
                options={
                    "verify_aud": False,
                    "verify_iss": False,
                    "verify_exp": False,
                    "verify_iat": False,
                    "verify_nbf": False,
                },
            )
            return self._identity(claims, nonce_digest)

    async def _key(self, client: httpx.AsyncClient, kid: str) -> jwt.PyJWK:
        if self._cache_clock() < self._keys_expire_at and kid in self._keys:
            return self._keys[kid]
        # One bounded load/refresh per token, including an unknown cached kid.
        # Clear first so refresh failure never leaves stale usable authority.
        self._keys = {}
        self._keys_expire_at = 0
        payload, headers = await self._request(
            client, "GET", JWKS_URL, headers={"Accept": "application/json"}
        )
        entries = payload.get("keys")
        if not isinstance(entries, list) or not 1 <= len(entries) <= 100:
            raise ValueError("invalid key set")
        keys: dict[str, jwt.PyJWK] = {}
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError("invalid key")
            key_id = entry.get("kid")
            if not isinstance(key_id, str) or not 1 <= len(key_id) <= 256 or key_id in keys:
                raise ValueError("invalid key id")
            if (
                entry.get("kty") != "RSA"
                or entry.get("alg", "RS256") != "RS256"
                or entry.get("use", "sig") != "sig"
                or entry.get("key_ops", ["verify"]) != ["verify"]
                or "d" in entry
            ):
                raise ValueError("invalid signing key")
            key = jwt.PyJWK.from_dict(entry, algorithm="RS256")
            if getattr(key.key, "key_size", 0) < 2048:
                raise ValueError("invalid signing key")
            keys[key_id] = key
        if kid not in keys:
            raise ValueError("unrecognized signing key")
        self._keys = keys
        self._keys_expire_at = self._cache_clock() + self._ttl(headers)
        return keys[kid]

    @staticmethod
    def _ttl(headers: httpx.Headers) -> int:
        ttl = 3600
        directives = [part.strip().lower() for part in headers.get("cache-control", "").split(",")]
        if "no-cache" in directives or "no-store" in directives:
            return 0
        for part in directives:
            if part.startswith("max-age="):
                value = part.removeprefix("max-age=").strip('"')
                if not value.isdecimal():
                    return 0
                ttl = min(ttl, int(value))
        age = headers.get("age", "0")
        if not age.isdecimal():
            return 0
        return max(0, ttl - int(age))

    def _identity(self, claims: dict[str, Any], nonce_digest: bytes) -> VerifiedIdentity:
        issuer = claims.get("iss")
        subject = claims.get("sub")
        audience = claims.get("aud")
        if issuer not in (ISSUER, "accounts.google.com") or not isinstance(subject, str):
            raise ValueError("invalid identity")
        if not 1 <= len(subject.encode("ascii")) <= 255:
            raise ValueError("invalid subject")
        audiences = [audience] if isinstance(audience, str) else audience
        if (
            not isinstance(audiences, list)
            or not audiences
            or any(
                not isinstance(item, str)
                or not 1 <= len(item) <= 255
                or not item.isascii()
                or any(ord(char) <= 32 or ord(char) == 127 for char in item)
                for item in audiences
            )
            or self._settings.client_id not in audiences
        ):
            raise ValueError("invalid audience")
        azp = claims.get("azp")
        if ("azp" in claims or len(audiences) > 1) and azp != self._settings.client_id:
            raise ValueError("invalid authorized party")
        expiry, issued = _numeric_date(claims, "exp"), _numeric_date(claims, "iat")
        now = self._clock()
        if not now < expiry + 60 or issued > now + 60 or issued < now - 660:
            raise ValueError("invalid token time")
        if "nbf" in claims and _numeric_date(claims, "nbf") > now + 60:
            raise ValueError("invalid token time")
        nonce = claims.get("nonce")
        if not isinstance(nonce, str) or not hmac.compare_digest(
            token_digest("nonce", decode_token(nonce)), nonce_digest
        ):
            raise ValueError("invalid nonce")
        return VerifiedIdentity(issuer=ISSUER, subject=subject)
