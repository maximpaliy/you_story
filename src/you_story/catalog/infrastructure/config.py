"""Separately injected cursor integrity key; never a production default."""

import base64
import re

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class CatalogSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="YOU_STORY_CATALOG_", extra="ignore", hide_input_in_errors=True
    )
    cursor_key: SecretStr

    @field_validator("cursor_key")
    @classmethod
    def valid_key(cls, value: SecretStr) -> SecretStr:
        raw = value.get_secret_value()
        if not re.fullmatch(r"[A-Za-z0-9_-]{43}", raw):
            raise ValueError("A canonical 32-byte cursor key is required")
        decoded = base64.urlsafe_b64decode(raw + "=")
        if base64.urlsafe_b64encode(decoded).rstrip(b"=").decode() != raw:
            raise ValueError("A canonical 32-byte cursor key is required")
        return value

    def key_bytes(self) -> bytes:
        return base64.urlsafe_b64decode(self.cursor_key.get_secret_value() + "=")
