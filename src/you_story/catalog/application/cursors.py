"""Bounded authenticated pagination tokens; payloads are private but readable."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from collections.abc import Callable
from typing import Any

from you_story.catalog.domain.policy import invalid

_LABEL = b"you-story/catalog-cursor/v1\x00"


class CursorSigner:
    def __init__(self, key: bytes, *, clock: Callable[[], float] = time.time) -> None:
        if type(key) is not bytes or len(key) < 32:
            raise ValueError("Catalog cursor key must contain at least 32 bytes")
        self._key = key
        self._clock = clock

    @staticmethod
    def _encode(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")

    def encode(self, binding: dict[str, Any], after: list[Any]) -> str:
        payload = json.dumps(
            {"v": 1, "binding": binding, "after": after, "exp": int(self._clock()) + 900},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
        if len(payload) > 1500:
            raise invalid()
        signature = hmac.digest(self._key, _LABEL + payload, hashlib.sha256)
        token = self._encode(payload + signature)
        if len(token) > 2048:
            raise invalid()
        return token

    def decode(self, token: str, binding: dict[str, Any]) -> list[Any]:
        try:
            if type(token) is not str or not token or len(token) > 2048 or not token.isascii():
                raise ValueError
            raw = base64.b64decode(token + "=" * (-len(token) % 4), altchars=b"-_", validate=True)
            if len(raw) < 33 or len(raw) > 1532 or self._encode(raw) != token:
                raise ValueError
            payload, signature = raw[:-32], raw[-32:]
            if not hmac.compare_digest(
                signature, hmac.digest(self._key, _LABEL + payload, hashlib.sha256)
            ):
                raise ValueError
            value = json.loads(payload)
            if (
                type(value) is not dict
                or set(value) != {"v", "binding", "after", "exp"}
                or type(value["v"]) is not int
                or value["v"] != 1
                or type(value["exp"]) is not int
                or value["exp"] <= self._clock()
                or value["exp"] > self._clock() + 900
                or value["binding"] != binding
                or type(value["after"]) is not list
                or len(value["after"]) != 2
                or any(type(x) is not str for x in value["after"])
            ):
                raise ValueError
            return value["after"]
        except (ValueError, TypeError, UnicodeError, KeyError):
            raise invalid() from None
