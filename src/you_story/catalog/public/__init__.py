"""Login-only catalog provisioning; no user-facing catalog operation."""

from uuid import UUID

from you_story.shared.context import ActorContext
from you_story.shared.database import Database


def ensure_personal_catalog(database: Database, actor: ActorContext) -> UUID:
    """Ensure the empty personal catalog/owner pair in one tenant transaction."""
    from you_story.catalog.infrastructure.provisioning import ensure_personal_catalog as ensure

    return ensure(database, actor)
