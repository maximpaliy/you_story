"""Immutable context contract; trusted identity infrastructure owns issuance."""

from contextvars import ContextVar
from dataclasses import dataclass
from uuid import UUID

correlation_id: ContextVar[str] = ContextVar("correlation_id", default="unavailable")


@dataclass(frozen=True, slots=True, init=False, weakref_slot=True)
class ActorContext:
    actor_id: UUID
    tenant_id: UUID
    provenance: str

    def __init__(self) -> None:
        raise TypeError("ActorContext requires the approved identity validation boundary")
