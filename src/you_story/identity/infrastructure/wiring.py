"""Explicit composition of the only implemented web identity provider."""

from you_story.identity.application.service import Provider, WebIdentity
from you_story.identity.domain.contracts import SessionRow
from you_story.identity.infrastructure.actors import issue_session
from you_story.identity.infrastructure.config import AuthSettings
from you_story.identity.infrastructure.crypto import IdentityCrypto
from you_story.identity.infrastructure.google import GoogleOIDC
from you_story.identity.infrastructure.postgres import PostgresIdentity
from you_story.identity.public import AuthenticatedSession, IdentityService
from you_story.shared.database import Database


def _issuer(row: SessionRow, bearer: bytes) -> AuthenticatedSession:
    return issue_session(
        row.user_id,
        row.tenant_id,
        row.session_id,
        row.provisioning_state,
        row.absolute_expires_at,
        bearer,
    )


def create_identity_service(
    database: Database,
    settings: AuthSettings,
    *,
    provider: Provider | None = None,
) -> IdentityService:
    return WebIdentity(
        PostgresIdentity(database),
        IdentityCrypto(settings),
        provider if provider is not None else GoogleOIDC(settings),
        _issuer,
    )
