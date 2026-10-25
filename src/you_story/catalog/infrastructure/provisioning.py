"""Reviewed login-only pair writes, with explicit actor predicates and FORCE RLS."""

from uuid import UUID

from sqlalchemy import Column, MetaData, String, Table, Uuid, bindparam, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Connection

from you_story.identity.public import require_validated_actor
from you_story.shared.context import ActorContext
from you_story.shared.database import Database
from you_story.shared.primitives import new_id

_metadata = MetaData()
_catalog = Table(
    "catalog",
    _metadata,
    Column("tenant_id", Uuid, nullable=False),
    Column("id", Uuid, primary_key=True),
    Column("visibility", String, nullable=False),
    schema="catalog",
)
_grant = Table(
    "catalog_grant",
    _metadata,
    Column("tenant_id", Uuid, nullable=False),
    Column("id", Uuid, primary_key=True),
    Column("catalog_id", Uuid, nullable=False),
    Column("grantee_tenant_id", Uuid, nullable=False),
    Column("role", String, nullable=False),
    schema="catalog",
)


def ensure_personal_catalog(database: Database, actor: ActorContext) -> UUID:
    require_validated_actor(actor)
    with database.unit_of_work(actor) as scope:
        return _ensure_pair(scope._require_active(), actor)


def _ensure_pair(connection: Connection, actor: ActorContext) -> UUID:
    # Unique tenant insertion serializes competing first logins. The subsequent
    # locked read is a new READ COMMITTED statement and observes the winner.
    tenant = bindparam("actor_tenant_id", actor.tenant_id, type_=Uuid)
    connection.execute(
        insert(_catalog)
        .values(tenant_id=tenant, id=new_id(), visibility="personal")
        .on_conflict_do_nothing(index_elements=[_catalog.c.tenant_id])
    )
    catalog_id: UUID = connection.execute(
        select(_catalog.c.id).where(_catalog.c.tenant_id == tenant).with_for_update()
    ).scalar_one()
    connection.execute(
        insert(_grant)
        .values(
            tenant_id=tenant,
            id=new_id(),
            catalog_id=catalog_id,
            grantee_tenant_id=tenant,
            role="owner",
        )
        .on_conflict_do_nothing(index_elements=[_grant.c.tenant_id, _grant.c.catalog_id])
    )
    connection.execute(
        select(_grant.c.id).where(
            _grant.c.tenant_id == tenant,
            _grant.c.grantee_tenant_id == tenant,
            _grant.c.catalog_id == catalog_id,
            _grant.c.role == "owner",
        )
    ).scalar_one()
    return catalog_id
