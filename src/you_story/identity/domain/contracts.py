"""Immutable internal identity values, separate from caller authority."""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Binding:
    nonce: bytes = field(repr=False)
    issued_at: int
    expires_at: int


@dataclass(frozen=True, slots=True)
class SessionRow:
    user_id: UUID
    tenant_id: UUID
    session_id: UUID
    provisioning_state: str
    absolute_expires_at: datetime


@dataclass(frozen=True, slots=True)
class PendingLogin:
    id: UUID
    nonce_digest: bytes = field(repr=False)
    encrypted_verifier: bytes = field(repr=False)
    pkce_challenge: str = field(repr=False)
    client_config_id: str
    invitation_digest: bytes | None = field(repr=False)
    destination: str


@dataclass(frozen=True, slots=True)
class StartResult:
    result: str
    id: UUID | None = None
    expires_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class FinishResult:
    result: str
    session: SessionRow | None = None
    window_end: datetime | None = None


@dataclass(frozen=True, slots=True)
class LimitResult:
    allowed: bool
    window_end: datetime
