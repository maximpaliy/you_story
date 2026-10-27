"""Actor-bound catalog use cases and reviewed composition boundary."""

from uuid import UUID

from you_story.catalog.application.service import CatalogService as CatalogService
from you_story.catalog.domain.policy import CatalogFailure as CatalogFailure
from you_story.catalog.infrastructure.config import CatalogSettings as CatalogSettings
from you_story.shared.context import ActorContext
from you_story.shared.database import Database


def ensure_personal_catalog(database: Database, actor: ActorContext) -> UUID:
    """Ensure the empty personal catalog/owner pair in one tenant transaction."""
    from you_story.catalog.infrastructure.provisioning import ensure_personal_catalog as ensure

    return ensure(database, actor)


def create_catalog_service(database: Database, settings: CatalogSettings) -> CatalogService:
    """Compose catalog adapters without exposing private persistence to delivery."""
    from you_story.catalog.infrastructure.repository import CatalogRepository

    return CatalogService(CatalogRepository(database), settings.key_bytes())
