"""Foundation HTTP response contracts."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class Health(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    status: Literal["live", "ready"]


class ErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    code: str
    message: str
    correlation_id: UUID


class ErrorEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    error: ErrorDetail


class OwnProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    user_id: UUID
    provisioning_state: Literal["catalog_pending", "ready"]
