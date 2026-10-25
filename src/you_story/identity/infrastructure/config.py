"""Fail-closed deployment configuration for the Google web identity adapter."""

from __future__ import annotations

import base64
import ipaddress
import re
from urllib.parse import urlsplit

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def canonical_origin(value: str, *, allow_loopback: bool = False) -> str:
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
        if (
            host is None
            or not value.isascii()
            or any(ord(char) <= 32 or ord(char) == 127 for char in value)
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path
            or parsed.query
            or parsed.fragment
            or host.endswith(".")
            or "%" in parsed.netloc
            or "\\" in value
            or "?" in value
            or "#" in value
            or parsed.scheme not in {"http", "https"}
        ):
            raise ValueError
        try:
            ipaddress.ip_address(host)
        except ValueError:
            if len(host) > 253 or any(
                re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) is None
                for label in host.split(".")
            ):
                raise ValueError from None
        port = parsed.port
        if parsed.scheme == "http":
            loopback = host == "localhost"
            try:
                loopback = loopback or ipaddress.ip_address(host).is_loopback
            except ValueError:
                pass
            if not allow_loopback or not loopback:
                raise ValueError
        rendered_host = f"[{host}]" if ":" in host else host
        suffix = "" if port in {None, 443 if parsed.scheme == "https" else 80} else f":{port}"
        return f"{parsed.scheme}://{rendered_host}{suffix}"
    except (ValueError, UnicodeError):
        raise ValueError("A canonical trusted web origin is required") from None


def secret_key(value: SecretStr) -> bytes:
    try:
        encoded = value.get_secret_value()
        raw = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        if len(raw) != 32 or base64.urlsafe_b64encode(raw).decode().rstrip("=") != encoded:
            raise ValueError
        return raw
    except (ValueError, UnicodeError):
        raise ValueError("A canonical encoded 32-byte key is required") from None


class AuthSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="YOU_STORY_AUTH_", extra="ignore", hide_input_in_errors=True
    )
    origin: str
    client_id: str
    client_secret: SecretStr
    preauth_key: SecretStr
    verifier_key: SecretStr
    ip_key: SecretStr
    production: bool = True

    @field_validator("client_id")
    @classmethod
    def valid_client(cls, value: str) -> str:
        if not value or len(value) > 255 or any(not 33 <= ord(c) <= 126 for c in value):
            raise ValueError("A configured Google client is required")
        return value

    @field_validator("client_secret")
    @classmethod
    def valid_secret(cls, value: SecretStr) -> SecretStr:
        raw = value.get_secret_value()
        if not raw or len(raw) > 4096 or any(ord(char) < 32 for char in raw):
            raise ValueError("A Google client secret is required")
        return value

    @field_validator("preauth_key", "verifier_key", "ip_key")
    @classmethod
    def valid_key(cls, value: SecretStr) -> SecretStr:
        secret_key(value)
        return value

    @model_validator(mode="after")
    def validate_deployment(self) -> AuthSettings:
        self.origin = canonical_origin(self.origin, allow_loopback=not self.production)
        keys = [
            secret_key(self.preauth_key),
            secret_key(self.verifier_key),
            secret_key(self.ip_key),
        ]
        if len(set(keys)) != 3:
            raise ValueError("Authentication keys must be separate")
        return self

    @property
    def redirect_uri(self) -> str:
        return self.origin + "/auth/google/callback"
