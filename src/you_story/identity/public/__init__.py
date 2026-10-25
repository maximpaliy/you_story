"""Typed identity boundary. Authentication evidence is issued only by infrastructure."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from hashlib import sha256
from typing import TYPE_CHECKING, Never, Protocol
from uuid import UUID
from weakref import ReferenceType

from you_story.shared.context import ActorContext

if TYPE_CHECKING:
    from you_story.shared.database import Database


class AuthFailure(Exception):
    """Safe bounded failure classification, never provider or credential detail."""

    def __init__(self, status: int, code: str, retry_after: int | None = None) -> None:
        self.status = status
        self.code = code
        self.retry_after = retry_after
        super().__init__("Authentication request failed")


@dataclass(frozen=True, slots=True)
class VerifiedIdentity:
    issuer: str
    subject: str


@dataclass(frozen=True, slots=True)
class LoginForm:
    binder_cookie: str = field(repr=False)
    proof: str = field(repr=False)
    expires_at: datetime
    max_age: int


@dataclass(frozen=True, slots=True, weakref_slot=True, eq=False)
class AuthenticatedSession:
    actor: ActorContext
    provisioning_state: str
    session_id: UUID
    absolute_expires_at: datetime
    _bearer: bytes = field(repr=False)


@dataclass(frozen=True, slots=True)
class LoginSuccess:
    session: AuthenticatedSession
    session_cookie: str = field(repr=False)
    destination: str


# Object identity, rather than dataclass equality/provenance strings, authenticates
# issued evidence. Weak references avoid retaining revoked or discarded sessions.
_ACTORS: dict[int, tuple[ReferenceType[ActorContext], bytes, bytes, str]] = {}
_SESSIONS: dict[
    int, tuple[ReferenceType[AuthenticatedSession], int, bytes, str, datetime, bytes]
] = {}


def require_validated_actor(actor: ActorContext) -> None:
    record = _ACTORS.get(id(actor))
    try:
        valid = (
            record is not None
            and record[0]() is actor
            and type(actor) is ActorContext
            and type(actor.actor_id) is UUID
            and type(actor.tenant_id) is UUID
            and record[1] == actor.actor_id.bytes
            and record[2] == actor.tenant_id.bytes
            and type(actor.provenance) is str
            and record[3] == actor.provenance
        )
    except (AttributeError, TypeError, ValueError):
        valid = False
    if not valid:
        raise AuthFailure(401, "unauthenticated")


def require_validated_session(session: AuthenticatedSession) -> None:
    record = _SESSIONS.get(id(session))
    try:
        valid = (
            record is not None
            and record[0]() is session
            and type(session) is AuthenticatedSession
            and record[1] == id(session.actor)
            and type(session.session_id) is UUID
            and record[2] == session.session_id.bytes
            and type(session.provisioning_state) is str
            and record[3] == session.provisioning_state
            and type(session.absolute_expires_at) is datetime
            and record[4] == session.absolute_expires_at
            and type(session._bearer) is bytes
            and record[5] == sha256(session._bearer).digest()
        )
    except (AttributeError, TypeError, ValueError):
        valid = False
    if not valid:
        raise AuthFailure(401, "unauthenticated")
    require_validated_actor(session.actor)


class IdentityService(Protocol):
    def get_login_form(self, binder_cookie: str | None) -> LoginForm: ...

    def start_login(
        self,
        *,
        binder_cookie: str,
        proof: str,
        ip_key: str,
        destination: str = "home",
        invitation: str | None = None,
        session_cookie: str | None = None,
    ) -> str: ...

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
    ) -> LoginSuccess: ...

    def resolve_session(self, cookie: str | None) -> AuthenticatedSession | None: ...

    def csrf_token(self, session: AuthenticatedSession) -> str: ...

    def validate_csrf(self, session: AuthenticatedSession, token: str) -> bool: ...

    def logout(self, session: AuthenticatedSession) -> bool: ...

    def mark_catalog_ready(self, session: AuthenticatedSession) -> bool: ...


class Provider(Protocol):
    def authorize_url(self, *, state: str, nonce: str, challenge: str) -> str: ...

    def exchange(self, *, code: str, verifier: str, nonce_digest: bytes) -> VerifiedIdentity: ...


# The explicitly reviewed public configuration facade contains no credentials
# unless the caller intentionally loads deployment settings.
from you_story.identity.infrastructure.config import AuthSettings as AuthSettings  # noqa: E402


def create_identity_service(
    database: Database,
    settings: AuthSettings,
    *,
    provider: Provider | None = None,
) -> IdentityService:
    from you_story.identity.infrastructure.wiring import create_identity_service as create

    return create(database, settings, provider=provider)


class _UnavailableIdentity:
    @staticmethod
    def _fail() -> Never:
        raise AuthFailure(503, "unavailable")

    def get_login_form(self, binder_cookie: str | None) -> LoginForm:
        self._fail()

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
        self._fail()

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
        self._fail()

    def resolve_session(self, cookie: str | None) -> AuthenticatedSession | None:
        self._fail()

    def csrf_token(self, session: AuthenticatedSession) -> str:
        self._fail()

    def validate_csrf(self, session: AuthenticatedSession, token: str) -> bool:
        self._fail()

    def logout(self, session: AuthenticatedSession) -> bool:
        self._fail()

    def mark_catalog_ready(self, session: AuthenticatedSession) -> bool:
        self._fail()


def unavailable_identity_service() -> IdentityService:
    """Credentials-free metadata/health composition; never a production fallback."""
    return _UnavailableIdentity()
