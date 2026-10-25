"""Positive/negative controls for real crypto and signed login representations."""

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from pydantic import ValidationError

from you_story.identity.infrastructure.config import AuthSettings
from you_story.identity.infrastructure.crypto import (
    IdentityCrypto,
    decode_token,
    encode_token,
    token_digest,
)


def settings(**changes):
    values = {
        "origin": "https://story.example",
        "client_id": "google-client",
        "client_secret": "synthetic-provider-secret",
        "preauth_key": encode_token(b"p" * 32),
        "verifier_key": encode_token(b"v" * 32),
        "ip_key": encode_token(b"i" * 32),
    }
    return AuthSettings(**(values | changes))


def test_binding_rerender_expiry_proof_domain_and_tampering():
    crypto = IdentityCrypto(settings())
    now = datetime(2026, 10, 25, tzinfo=UTC)
    binding = crypto.binding(now)
    cookie, proof = crypto.cookie(binding), crypto.proof(binding)
    assert crypto.read_binding(cookie, now + timedelta(seconds=599)) == binding
    assert crypto.cookie(crypto.read_binding(cookie, now)) == cookie
    assert crypto.valid_proof(binding, proof)
    assert not crypto.valid_proof(binding, cookie)
    with pytest.raises(ValueError):
        crypto.read_binding(proof, now)
    for index in [0, 15, 35, 60, len(decode_envelope(cookie)) - 1]:
        raw = bytearray(decode_envelope(cookie))
        raw[index] ^= 1
        with pytest.raises(ValueError):
            crypto.read_binding(encode_token(bytes(raw)), now)
    for invalid_time in [now - timedelta(seconds=1), now + timedelta(seconds=600)]:
        with pytest.raises(ValueError):
            crypto.read_binding(cookie, invalid_time)
    assert not crypto.valid_proof(binding, proof + "=")
    assert not IdentityCrypto(settings(origin="https://other.example")).valid_proof(binding, proof)


def decode_envelope(value):
    import base64

    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def test_aead_roundtrip_substitution_and_corruption():
    crypto = IdentityCrypto(settings())
    transaction = uuid4()
    verifier = crypto.random_token()
    encrypted = crypto.encrypt_verifier(transaction, verifier)
    assert crypto.decrypt_verifier(transaction, encrypted) == verifier
    assert encrypted != crypto.encrypt_verifier(transaction, verifier)
    for index in [0, 1, 12, 20, 71]:
        raw = bytearray(encrypted)
        raw[index] ^= 1
        with pytest.raises(ValueError):
            crypto.decrypt_verifier(transaction, bytes(raw))
    for other in [
        IdentityCrypto(settings(client_id="other")),
        IdentityCrypto(settings(verifier_key=encode_token(b"w" * 32))),
    ]:
        with pytest.raises(ValueError):
            other.decrypt_verifier(transaction, encrypted)
    with pytest.raises(ValueError):
        crypto.decrypt_verifier(uuid4(), encrypted)
    with pytest.raises(ValueError):
        crypto.decrypt_verifier(transaction, encrypted[:-1])


def test_hkdf_reference_digest_domain_and_rotation():
    crypto = IdentityCrypto(settings())
    bearer, session = b"b" * 32, uuid4()
    reference = HKDF(
        algorithm=hashes.SHA256(), length=32, salt=session.bytes, info=b"you-story:csrf:v1"
    ).derive(bearer)
    token = crypto.csrf(bearer, session)
    assert decode_token(token) == reference
    assert (
        crypto.csrf_digest(token, session)
        == sha256(b"you-story:csrf:v1\0" + session.bytes + b"\0" + reference).digest()
    )
    assert crypto.csrf(bearer, session) == token
    assert crypto.csrf(bearer, uuid4()) != token
    assert crypto.csrf(b"c" * 32, session) != token
    assert token_digest("session", bearer) != token_digest("nonce", bearer)
    assert token_digest("nonce", bearer) == sha256(b"you-story:nonce:v1\0" + bearer).digest()


@pytest.mark.parametrize(
    "value", ["", "A" * 42, "A" * 44, "A" * 42 + "=", "A" * 42 + "B", "é" * 43, "_" * 43]
)
def test_noncanonical_session_tokens_rejected(value):
    with pytest.raises(ValueError):
        decode_token(value)


def test_random_tokens_and_pkce():
    crypto = IdentityCrypto(settings())
    samples = {crypto.random_token() for _ in range(100)}
    assert len(samples) == 100
    for token in samples:
        assert len(token) == 43
        assert len(decode_token(token)) == 32
        assert crypto.challenge(token) == encode_token(sha256(token.encode("ascii")).digest())


def test_ip_key_uses_canonical_trusted_address_and_separate_hmac():
    crypto = IdentityCrypto(settings())
    assert crypto.ip_digest("::1") == crypto.ip_digest("0:0:0:0:0:0:0:1")
    assert crypto.ip_digest("127.0.0.1") != crypto.ip_digest("127.0.0.2")
    assert crypto.ip_digest("127.0.0.1") != sha256(b"127.0.0.1").digest()
    with pytest.raises(ValueError):
        crypto.ip_digest("unknown-forwarded-peer")


@pytest.mark.parametrize(
    "origin",
    [
        "http://story.example",
        "https://story.example/",
        "https://user@story.example",
        "https://story.example.",
        "https://story.example?q=a",
        "https://story.example?",
        "https://story.example#",
        "https://é.example",
        "https://%65xample.com",
        "https://story.example:invalid",
    ],
)
def test_invalid_deployment_origins_fail_closed(origin):
    with pytest.raises(ValidationError):
        settings(origin=origin)


def test_missing_invalid_or_reused_keys_fail_closed_without_secret_error():
    for changes in [
        {"preauth_key": "SECRET_SENTINEL"},
        {"client_secret": ""},
        {"verifier_key": encode_token(b"p" * 32)},
    ]:
        with pytest.raises(ValidationError) as error:
            settings(**changes)
        assert "SECRET_SENTINEL" not in str(error.value)
    assert settings(origin="http://127.0.0.1:8080", production=False).redirect_uri == (
        "http://127.0.0.1:8080/auth/google/callback"
    )
    with pytest.raises(ValidationError):
        settings(origin="http://remote.example", production=False)


@pytest.mark.parametrize("client_id", ["client\x00id", "client\x7fid"])
def test_client_identifier_rejects_nonvisible_ascii_controls(client_id):
    with pytest.raises(ValidationError):
        settings(client_id=client_id)
