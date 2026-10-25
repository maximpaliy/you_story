"""Web identity use cases over typed persistence, crypto and provider ports."""

from __future__ import annotations

import hmac
import logging
import math
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol, TypeVar
from uuid import UUID, uuid4

from you_story.identity.domain.contracts import (
    Binding,
    FinishResult,
    LimitResult,
    PendingLogin,
    SessionRow,
    StartResult,
)
from you_story.identity.public import (
    AuthenticatedSession,
    AuthFailure,
    LoginForm,
    LoginSuccess,
    VerifiedIdentity,
    require_validated_session,
)

_log = logging.getLogger("you_story.identity")
_T = TypeVar("_T")
_DESTINATIONS = {"home": "/", "calendar": "/calendar", "catalog": "/catalog"}
_ISSUER = "https://accounts.google.com"


class Store(Protocol):
    def now(self) -> datetime: ...
    def start(
        self,
        transaction_id: UUID,
        binder: bytes,
        state: bytes,
        nonce: bytes,
        challenge: str,
        ciphertext: bytes,
        invitation: bytes | None,
        destination: str,
        expires_at: datetime,
    ) -> StartResult: ...
    def claim(self, state: bytes, binder: bytes) -> PendingLogin | None: ...
    def fail(self, transaction_id: UUID, binder: bytes) -> bool: ...
    def finish(
        self,
        transaction_id: UUID,
        binder: bytes,
        issuer: str,
        subject: str,
        session_id: UUID,
        token: bytes,
        csrf: bytes,
    ) -> FinishResult: ...
    def resolve(self, token: bytes) -> SessionRow | None: ...
    def revoke(self, token: bytes) -> bool: ...
    def limit(self, scope: str, key: bytes) -> LimitResult | None: ...
    def mark_ready(self, token: bytes) -> bool: ...


class Crypto(Protocol):
    def random_token(self) -> str: ...
    def decode(self, value: str) -> bytes: ...
    def encode(self, value: bytes) -> str: ...
    def digest(self, label: str, raw: bytes) -> bytes: ...
    def challenge(self, verifier: str) -> str: ...
    def binding(self, now: datetime) -> Binding: ...
    def cookie(self, binding: Binding) -> str: ...
    def read_binding(self, cookie: str, now: datetime) -> Binding: ...
    def proof(self, binding: Binding) -> str: ...
    def valid_proof(self, binding: Binding, proof: str) -> bool: ...
    def encrypt_verifier(self, transaction_id: UUID, verifier: str) -> bytes: ...
    def decrypt_verifier(self, transaction_id: UUID, envelope: bytes) -> str: ...
    def csrf(self, bearer: bytes, session_id: UUID) -> str: ...
    def csrf_digest(self, token: str, session_id: UUID) -> bytes: ...
    def ip_digest(self, peer: str) -> bytes: ...


class Provider(Protocol):
    def authorize_url(self, *, state: str, nonce: str, challenge: str) -> str: ...
    def exchange(self, *, code: str, verifier: str, nonce_digest: bytes) -> VerifiedIdentity: ...


class WebIdentity:
    def __init__(
        self,
        store: Store,
        crypto: Crypto,
        provider: Provider,
        issuer: Callable[[SessionRow, bytes], AuthenticatedSession],
    ) -> None:
        self._store = store
        self._crypto = crypto
        self._provider = provider
        self._issuer = issuer

    @staticmethod
    def _database(operation: Callable[[], _T]) -> _T:
        try:
            return operation()
        except AuthFailure:
            raise
        except Exception:
            raise AuthFailure(503, "unavailable") from None

    def _now(self) -> datetime:
        return self._database(self._store.now)

    def _retry_after(self, end: datetime) -> int:
        return max(1, math.ceil((end - self._now()).total_seconds()))

    def _limit(self, scope: str, key: bytes) -> None:
        result = self._database(lambda: self._store.limit(scope, key))
        if result is None:
            raise AuthFailure(503, "unavailable")
        if not result.allowed:
            raise AuthFailure(429, "rate_limited", self._retry_after(result.window_end))

    def _ip_limit(self, scope: str, peer: str) -> None:
        try:
            key = self._crypto.ip_digest(peer)
        except ValueError:
            raise AuthFailure(503, "unavailable") from None
        self._limit(scope, key)

    def get_login_form(self, binder_cookie: str | None) -> LoginForm:
        now = self._now()
        binding = None
        if binder_cookie is not None:
            try:
                binding = self._crypto.read_binding(binder_cookie, now)
            except ValueError:
                pass
        if binding is None:
            binding = self._crypto.binding(now)
        return LoginForm(
            self._crypto.cookie(binding),
            self._crypto.proof(binding),
            datetime.fromtimestamp(binding.expires_at, UTC),
            max(0, math.ceil(binding.expires_at - now.timestamp())),
        )

    def resolve_session(self, cookie: str | None) -> AuthenticatedSession | None:
        if cookie is None:
            return None
        try:
            bearer = self._crypto.decode(cookie)
        except ValueError:
            return None
        digest = self._crypto.digest("session", bearer)
        row = self._database(lambda: self._store.resolve(digest))
        if row is None:
            return None
        return self._issuer(row, bearer)

    def start_login(
        self,
        *,
        binder_cookie: str,
        proof: str,
        ip_key: str,
        destination: str = "home",
        invitation: str | None = None,
        session_cookie: str | None = None,
    ) -> str:
        self._ip_limit("IP-start", ip_key)
        if self.resolve_session(session_cookie) is not None:
            raise AuthFailure(409, "already_authenticated")
        try:
            binding = self._crypto.read_binding(binder_cookie, self._now())
            if not self._crypto.valid_proof(binding, proof):
                raise ValueError
        except ValueError:
            raise AuthFailure(403, "forbidden") from None
        binder = self._crypto.digest("binder", binding.nonce)
        self._limit("binder-start", binder)
        try:
            if destination not in _DESTINATIONS:
                raise ValueError
            invitation_digest = (
                self._crypto.digest("invitation", self._crypto.decode(invitation))
                if invitation is not None
                else None
            )
        except (ValueError, TypeError):
            raise AuthFailure(400, "invalid_request") from None
        transaction_id = uuid4()
        state, nonce, verifier = (self._crypto.random_token() for _ in range(3))
        challenge = self._crypto.challenge(verifier)
        ciphertext = self._crypto.encrypt_verifier(transaction_id, verifier)
        result = self._database(
            lambda: self._store.start(
                transaction_id,
                binder,
                self._crypto.digest("state", self._crypto.decode(state)),
                self._crypto.digest("nonce", self._crypto.decode(nonce)),
                challenge,
                ciphertext,
                invitation_digest,
                destination,
                datetime.fromtimestamp(binding.expires_at, UTC),
            )
        )
        if result.result == "in_progress":
            raise AuthFailure(409, "login_in_progress")
        if result.result == "unavailable":
            raise AuthFailure(503, "unavailable")
        if result.result != "ok" or result.id != transaction_id:
            raise AuthFailure(400, "invalid_request")
        try:
            return self._provider.authorize_url(state=state, nonce=nonce, challenge=challenge)
        except Exception:
            raise AuthFailure(503, "unavailable") from None

    def _fail_claim(self, claim: PendingLogin, binder: bytes) -> None:
        try:
            self._store.fail(claim.id, binder)
        except Exception:
            # The committed claim is already one-shot and cannot reopen. Its
            # authoritative deadline/next bounded cleanup handles an outage.
            _log.warning("authentication_cleanup_unavailable")

    def complete_login(
        self,
        *,
        binder_cookie: str,
        state: str,
        ip_key: str,
        code: str | None = None,
        error: str | None = None,
        issuer: str | None = None,
        session_cookie: str | None = None,
    ) -> LoginSuccess:
        self._ip_limit("IP-callback", ip_key)
        if self.resolve_session(session_cookie) is not None:
            raise AuthFailure(409, "already_authenticated")
        try:
            binding = self._crypto.read_binding(binder_cookie, self._now())
            state_digest = self._crypto.digest("state", self._crypto.decode(state))
        except (ValueError, TypeError):
            raise AuthFailure(400, "login_failed") from None
        binder = self._crypto.digest("binder", binding.nonce)
        claim = self._database(lambda: self._store.claim(state_digest, binder))
        if claim is None:
            raise AuthFailure(400, "login_failed")
        try:
            if (
                issuer not in {None, _ISSUER}
                or error is not None
                or code is None
                or not isinstance(code, str)
                or not code
                or len(code) > 8192
            ):
                raise AuthFailure(400, "login_failed")
            verifier = self._crypto.decrypt_verifier(claim.id, claim.encrypted_verifier)
            if not hmac.compare_digest(self._crypto.challenge(verifier), claim.pkce_challenge):
                raise AuthFailure(400, "login_failed")
            try:
                identity = self._provider.exchange(
                    code=code, verifier=verifier, nonce_digest=claim.nonce_digest
                )
            except Exception:
                raise AuthFailure(400, "login_failed") from None
            if (
                identity.issuer != _ISSUER
                or not isinstance(identity.subject, str)
                or not identity.subject
                or not identity.subject.isascii()
                or len(identity.subject) > 255
            ):
                raise AuthFailure(400, "login_failed")
            if self.resolve_session(session_cookie) is not None:
                raise AuthFailure(409, "already_authenticated")
            session_id = uuid4()
            session_cookie = self._crypto.random_token()
            bearer = self._crypto.decode(session_cookie)
            csrf = self._crypto.csrf(bearer, session_id)
            result = self._database(
                lambda: self._store.finish(
                    claim.id,
                    binder,
                    identity.issuer,
                    identity.subject,
                    session_id,
                    self._crypto.digest("session", bearer),
                    self._crypto.csrf_digest(csrf, session_id),
                )
            )
            if result.result == "limited" and result.window_end is not None:
                raise AuthFailure(429, "rate_limited", self._retry_after(result.window_end))
            if result.result == "unavailable":
                raise AuthFailure(503, "unavailable")
            if result.result != "ok" or result.session is None:
                raise AuthFailure(400, "login_failed")
            if result.session.session_id != session_id:
                raise AuthFailure(503, "unavailable")
            session = self._issuer(result.session, bearer)
            return LoginSuccess(session, session_cookie, _DESTINATIONS[claim.destination])
        except AuthFailure:
            self._fail_claim(claim, binder)
            raise
        except Exception:
            self._fail_claim(claim, binder)
            raise AuthFailure(400, "login_failed") from None

    def _current(self, session: AuthenticatedSession) -> SessionRow:
        require_validated_session(session)
        row = self._database(
            lambda: self._store.resolve(self._crypto.digest("session", session._bearer))
        )
        if (
            row is None
            or row.user_id != session.actor.actor_id
            or row.tenant_id != session.actor.tenant_id
            or row.session_id != session.session_id
        ):
            raise AuthFailure(401, "unauthenticated")
        return row

    def csrf_token(self, session: AuthenticatedSession) -> str:
        require_validated_session(session)
        return self._crypto.csrf(session._bearer, session.session_id)

    def validate_csrf(self, session: AuthenticatedSession, token: str) -> bool:
        try:
            self._current(session)
            expected = self._crypto.csrf_digest(self.csrf_token(session), session.session_id)
            supplied = self._crypto.csrf_digest(token, session.session_id)
            return hmac.compare_digest(supplied, expected)
        except AuthFailure as error:
            if error.status == 503:
                raise
            return False
        except (ValueError, TypeError):
            return False

    def logout(self, session: AuthenticatedSession) -> bool:
        self._current(session)
        revoked = self._database(
            lambda: self._store.revoke(self._crypto.digest("session", session._bearer))
        )
        if not revoked:
            raise AuthFailure(401, "unauthenticated")
        return True

    def mark_catalog_ready(self, session: AuthenticatedSession) -> bool:
        self._current(session)
        return self._database(
            lambda: self._store.mark_ready(self._crypto.digest("session", session._bearer))
        )
