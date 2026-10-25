"""Sole identity issuance boundary, called only for validated persistence results."""

from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from uuid import UUID
from weakref import ref

from you_story.identity.public import (
    _ACTORS,
    _SESSIONS,
    AuthenticatedSession,
)
from you_story.shared.context import ActorContext


def _issue_actor(user_id: UUID, tenant_id: UUID) -> ActorContext:
    if not isinstance(user_id, UUID) or not isinstance(tenant_id, UUID):
        raise ValueError("Invalid identity result")
    actor = object.__new__(ActorContext)
    object.__setattr__(actor, "actor_id", user_id)
    object.__setattr__(actor, "tenant_id", tenant_id)
    object.__setattr__(actor, "provenance", "validated_identity")
    identity = id(actor)
    _ACTORS[identity] = (
        ref(actor, lambda _: _ACTORS.pop(identity, None)),
        user_id.bytes,
        tenant_id.bytes,
        "validated_identity",
    )
    return actor


def issue_session(
    user_id: UUID,
    tenant_id: UUID,
    session_id: UUID,
    provisioning_state: str,
    absolute_expires_at: datetime,
    bearer: bytes,
) -> AuthenticatedSession:
    if (
        provisioning_state not in {"catalog_pending", "ready"}
        or not isinstance(session_id, UUID)
        or absolute_expires_at.tzinfo is None
        or len(bearer) != 32
    ):
        raise ValueError("Invalid identity result")
    session = AuthenticatedSession(
        _issue_actor(user_id, tenant_id),
        provisioning_state,
        session_id,
        absolute_expires_at,
        bearer,
    )
    identity = id(session)
    _SESSIONS[identity] = (
        ref(session, lambda _: _SESSIONS.pop(identity, None)),
        id(session.actor),
        session_id.bytes,
        provisioning_state,
        absolute_expires_at,
        sha256(bearer).digest(),
    )
    return session
