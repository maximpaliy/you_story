"""Canonical identity envelopes and established AEAD/HKDF primitives."""

from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import secrets
import struct
from datetime import datetime
from uuid import UUID

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from you_story.identity.domain.contracts import Binding
from you_story.identity.infrastructure.config import AuthSettings, secret_key


def encode_token(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value: str, maximum: int) -> bytes:
    if not isinstance(value, str) or not value or len(value) > maximum or not value.isascii():
        raise ValueError("Invalid credential format")
    try:
        raw = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
    except (ValueError, UnicodeError):
        raise ValueError("Invalid credential format") from None
    if encode_token(raw) != value:
        raise ValueError("Invalid credential format")
    return raw


def decode_token(value: str) -> bytes:
    raw = _decode(value, 43)
    if len(value) != 43 or len(raw) != 32:
        raise ValueError("Invalid credential format")
    return raw


def token_digest(label: str, raw: bytes) -> bytes:
    if label not in {"session", "state", "nonce", "binder", "invitation"} or len(raw) != 32:
        raise ValueError("Invalid digest input")
    return hashlib.sha256(f"you-story:{label}:v1".encode("ascii") + b"\0" + raw).digest()


def _parts(*values: bytes) -> bytes:
    return b"".join(struct.pack("!I", len(value)) + value for value in values)


def _fields(raw: bytes, count: int) -> list[bytes]:
    result: list[bytes] = []
    offset = 0
    for _ in range(count):
        if len(raw) < offset + 4:
            raise ValueError("Invalid envelope")
        size = struct.unpack("!I", raw[offset : offset + 4])[0]
        offset += 4
        if size > 512 or len(raw) < offset + size:
            raise ValueError("Invalid envelope")
        result.append(raw[offset : offset + size])
        offset += size
    if offset != len(raw):
        raise ValueError("Invalid envelope")
    return result


class IdentityCrypto:
    def __init__(self, settings: AuthSettings) -> None:
        self._proof_key = secret_key(settings.preauth_key)
        self._aead = AESGCM(secret_key(settings.verifier_key))
        self._ip_key = secret_key(settings.ip_key)
        self._origin = settings.origin.encode("ascii")
        self._client_id = settings.client_id.encode("ascii")

    @staticmethod
    def random_token() -> str:
        return encode_token(secrets.token_bytes(32))

    @staticmethod
    def decode(value: str) -> bytes:
        return decode_token(value)

    @staticmethod
    def encode(value: bytes) -> str:
        return encode_token(value)

    @staticmethod
    def digest(label: str, raw: bytes) -> bytes:
        return token_digest(label, raw)

    @staticmethod
    def challenge(verifier: str) -> str:
        decode_token(verifier)
        return encode_token(hashlib.sha256(verifier.encode("ascii")).digest())

    def binding(self, now: datetime) -> Binding:
        issued = int(now.timestamp())
        return Binding(secrets.token_bytes(32), issued, issued + 600)

    @staticmethod
    def _binding_parts(binding: Binding) -> tuple[bytes, bytes, bytes, bytes]:
        return (
            b"1",
            binding.nonce,
            binding.issued_at.to_bytes(8, "big"),
            binding.expires_at.to_bytes(8, "big"),
        )

    def cookie(self, binding: Binding) -> str:
        payload = _parts(*self._binding_parts(binding))
        mac = hmac.digest(self._proof_key, b"you-story:login-cookie:v1\0" + payload, "sha256")
        return encode_token(payload + mac)

    def read_binding(self, cookie: str, now: datetime) -> Binding:
        raw = _decode(cookie, 512)
        payload, supplied = raw[:-32], raw[-32:]
        expected = hmac.digest(self._proof_key, b"you-story:login-cookie:v1\0" + payload, "sha256")
        if len(supplied) != 32 or not hmac.compare_digest(supplied, expected):
            raise ValueError("Invalid login binding")
        version, nonce, issued_raw, expires_raw = _fields(payload, 4)
        if version != b"1" or len(nonce) != 32 or len(issued_raw) != 8 or len(expires_raw) != 8:
            raise ValueError("Invalid login binding")
        issued, expires = int.from_bytes(issued_raw), int.from_bytes(expires_raw)
        if expires != issued + 600 or issued > now.timestamp() or now.timestamp() >= expires:
            raise ValueError("Invalid login binding")
        return Binding(nonce, issued, expires)

    def proof(self, binding: Binding) -> str:
        payload = _parts(
            b"1",
            token_digest("binder", binding.nonce),
            self._origin,
            binding.issued_at.to_bytes(8, "big"),
            binding.expires_at.to_bytes(8, "big"),
        )
        signature = hmac.digest(self._proof_key, b"you-story:login-proof:v1\0" + payload, "sha256")
        return encode_token(payload + signature)

    def valid_proof(self, binding: Binding, proof: str) -> bool:
        try:
            raw = _decode(proof, 512)
            expected = _decode(self.proof(binding), 512)
            return len(raw) == len(expected) and hmac.compare_digest(raw, expected)
        except ValueError:
            return False

    def encrypt_verifier(self, transaction_id: UUID, verifier: str) -> bytes:
        decode_token(verifier)
        nonce = secrets.token_bytes(12)
        associated = _parts(b"you-story:pkce:v1", transaction_id.bytes, self._client_id)
        return b"\x01" + nonce + self._aead.encrypt(nonce, verifier.encode("ascii"), associated)

    def decrypt_verifier(self, transaction_id: UUID, envelope: bytes) -> str:
        if len(envelope) != 72 or envelope[0] != 1:
            raise ValueError("Invalid verifier envelope")
        associated = _parts(b"you-story:pkce:v1", transaction_id.bytes, self._client_id)
        try:
            plaintext = self._aead.decrypt(envelope[1:13], envelope[13:], associated)
            verifier = plaintext.decode("ascii")
            decode_token(verifier)
            return verifier
        except (InvalidTag, ValueError, UnicodeError):
            raise ValueError("Invalid verifier envelope") from None

    @staticmethod
    def csrf(bearer: bytes, session_id: UUID) -> str:
        if len(bearer) != 32:
            raise ValueError("Invalid session credential")
        value = HKDF(
            algorithm=hashes.SHA256(), length=32, salt=session_id.bytes, info=b"you-story:csrf:v1"
        ).derive(bearer)
        return encode_token(value)

    @staticmethod
    def csrf_digest(token: str, session_id: UUID) -> bytes:
        return hashlib.sha256(
            b"you-story:csrf:v1\0" + session_id.bytes + b"\0" + decode_token(token)
        ).digest()

    def ip_digest(self, peer: str) -> bytes:
        try:
            canonical = str(ipaddress.ip_address(peer)).encode("ascii")
        except ValueError:
            raise ValueError("A trusted peer address is required") from None
        return hmac.digest(self._ip_key, b"you-story:auth-ip:v1\0" + canonical, "sha256")
