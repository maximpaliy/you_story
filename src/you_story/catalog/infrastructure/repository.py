"""Actor-scoped catalog SQL, aggregate locking and coherent read snapshots."""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from you_story.catalog.domain.policy import CatalogFailure
from you_story.identity.public import require_validated_actor
from you_story.shared.context import ActorContext
from you_story.shared.database import Database

_SOURCE = UUID("10000000-0000-4000-8000-000000000001")
_DEFAULT = UUID("30000000-0000-4000-8000-000000000001")
_SELECT = """SELECT e.id,e.catalog_id,e.parent_entry_id AS parent_id,s.key AS source_key,
 d.definition_version AS source_definition_version,e.instrument_id,e.entry_type AS type,
 e.name,e.metadata,CASE WHEN e.lifecycle_state='tombstone' THEN 'tombstoned'
 ELSE e.lifecycle_state END AS state,e.version,e.created_at AS _created_at,
 e.source_definition_id AS _definition_id
 FROM catalog.entry e JOIN catalog.source s ON s.id=e.source_id
 JOIN catalog.source_definition d ON d.id=e.source_definition_id
 """


def _entry(row: Any) -> dict[str, Any]:
    return dict(row._mapping)


class CatalogRepository:
    def __init__(self, database: Database, default_definition_id: UUID = _DEFAULT) -> None:
        self.database = database
        self.default_definition_id = default_definition_id

    @contextmanager
    def transaction(self, actor: ActorContext, write: bool = False) -> Iterator[CatalogStore]:
        require_validated_actor(actor)
        # Setup precedes the first tenant SELECT, unlike the generic UoW. The
        # inherited pool reset hooks still clear context on every checkout/reset.
        try:
            with self.database._engine.connect() as connection:
                with connection.begin():
                    if not write:
                        connection.execute(
                            text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                        )
                    connection.execute(text("SET LOCAL lock_timeout = '2s'"))
                    connection.execute(text("SET LOCAL statement_timeout = '2s'"))
                    connection.execute(
                        text("SELECT pg_catalog.set_config('app.tenant_id', :tenant, true)"),
                        {"tenant": str(actor.tenant_id)},
                    )
                    store = CatalogStore(connection, actor, self.default_definition_id)
                    yield store
        except IntegrityError:
            raise CatalogFailure(409, "conflict") from None
        except SQLAlchemyError:
            raise CatalogFailure(503, "unavailable") from None


class CatalogStore:
    def __init__(
        self, connection: Connection, actor: ActorContext, default_definition_id: UUID = _DEFAULT
    ) -> None:
        self.connection = connection
        self.actor = actor
        self.catalog_id: UUID | None = None
        self.default_definition_id = default_definition_id

    def _parameters(self, **values: Any) -> dict[str, Any]:
        return {"tenant": self.actor.tenant_id, **values}

    def catalog(self, lock: bool = False) -> dict[str, Any] | None:
        row = self.connection.execute(
            text(
                """SELECT c.id,c.version FROM catalog.catalog c
            JOIN catalog.catalog_grant g ON g.catalog_id=c.id
            WHERE c.tenant_id=:tenant AND g.tenant_id=:tenant
            AND g.grantee_tenant_id=:tenant AND g.role='owner' AND c.visibility='personal'
            """
                + ("FOR UPDATE OF c" if lock else "")
            ),
            self._parameters(),
        ).first()
        if row is None:
            return None
        self.catalog_id = row.id
        return dict(row._mapping)

    def entry(self, identifier: UUID) -> dict[str, Any] | None:
        if self.catalog_id is None and self.catalog() is None:
            return None
        row = self.connection.execute(
            text(_SELECT + " WHERE e.tenant_id=:tenant AND e.catalog_id=:catalog AND e.id=:id"),
            self._parameters(catalog=self.catalog_id, id=identifier),
        ).first()
        return None if row is None else _entry(row)

    def ancestors(self, identifier: UUID) -> list[dict[str, Any]]:
        node = self.entry(identifier)
        result: list[dict[str, Any]] = []
        seen = {identifier}
        while node is not None and node["parent_id"] is not None:
            if len(result) >= 15 or node["parent_id"] in seen:
                raise ValueError("Invalid catalog ancestry")
            seen.add(node["parent_id"])
            node = self.entry(node["parent_id"])
            if node is None:
                raise ValueError("Invalid catalog ancestry")
            result.append(node)
        result.reverse()
        return result

    def definition(self, identifier: UUID | None = None) -> dict[str, Any]:
        row = self.connection.execute(
            text(
                "SELECT definition FROM catalog.source_definition "
                "WHERE id=:id AND source_id=:source"
            ),
            {"id": identifier or self.default_definition_id, "source": _SOURCE},
        ).one()
        return dict(row.definition)

    def references(self) -> dict[str, Any]:
        source = self.connection.execute(
            text("""SELECT s.key,d.definition_version AS version,d.definition
            FROM catalog.source s JOIN catalog.source_definition d ON d.source_id=s.id
            WHERE s.key='yousician' AND d.id=:definition"""),
            {"definition": self.default_definition_id},
        ).one()
        definition = {
            key: value
            for key, value in source.definition.items()
            if key in {"types", "parent_rules", "metadata_rules", "practiceable_types"}
        }
        instruments = self.connection.execute(
            text(
                "SELECT id,key,name FROM catalog.instrument "
                "WHERE key IN ('guitar','piano') ORDER BY key"
            )
        ).all()
        return {
            "sources": [{"key": source.key, "version": source.version, "definition": definition}],
            "instruments": [dict(row._mapping) for row in instruments],
        }

    def entries(
        self,
        filters: dict[str, Any],
        after: list[Any] | None,
        limit: int,
        parent_id: UUID | None = None,
    ) -> list[dict[str, Any]]:
        if self.catalog_id is None and self.catalog() is None:
            return []
        parameters = self._parameters(catalog=self.catalog_id, limit=limit)
        joins = """ LEFT JOIN catalog.entry p ON p.id=e.parent_entry_id AND p.tenant_id=:tenant
            AND p.catalog_id=:catalog
            LEFT JOIN catalog.entry g ON g.id=p.parent_entry_id AND g.tenant_id=:tenant
            AND g.catalog_id=:catalog """
        author = (
            "CASE WHEN e.entry_type='song' THEN e.metadata->>'author' "
            "WHEN p.entry_type='song' THEN p.metadata->>'author' "
            "WHEN g.entry_type='song' THEN g.metadata->>'author' END"
        )
        conditions = ["e.tenant_id=:tenant", "e.catalog_id=:catalog", "e.lifecycle_state='active'"]
        for key, column in [
            ("source_key", "s.key"),
            ("instrument_id", "e.instrument_id"),
            ("entry_type", "e.entry_type"),
        ]:
            if filters.get(key) is not None:
                conditions.append(f"{column}=:{key}")
                parameters[key] = filters[key]
        for key in ["text", "author"]:
            if filters.get(key):
                value = filters[key].replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                parameters[key] = "%" + value + "%"
                if key == "text":
                    conditions.append(
                        f"(e.name ILIKE :text ESCAPE '\\' OR ({author}) ILIKE :text ESCAPE '\\')"
                    )
                else:
                    conditions.append(f"({author}) ILIKE :author ESCAPE '\\'")
        if filters.get("ancestor_id") is not None:
            conditions.append("(p.id=:ancestor_id OR g.id=:ancestor_id)")
            parameters["ancestor_id"] = filters["ancestor_id"]
        if filters.get("roots_only"):
            conditions.append("e.parent_entry_id IS NULL")
        if parent_id is not None:
            conditions.append("e.parent_entry_id=:parent_id")
            parameters["parent_id"] = parent_id
        order = "e.created_at" if parent_id is not None else 'e.name COLLATE "C"'
        if after is not None:
            conditions.append(f"({order},e.id) > (:after_value,:after_id)")
            parameters["after_value"] = (
                datetime.fromisoformat(after[0]) if parent_id is not None else after[0]
            )
            parameters["after_id"] = UUID(str(after[1]))
        query = (
            _SELECT
            + joins
            + " WHERE "
            + " AND ".join(conditions)
            + f" ORDER BY {order},e.id LIMIT :limit"
        )
        rows = self.connection.execute(text(query), parameters).all()
        result = [_entry(row) for row in rows]
        for item in result:
            first = item["_created_at"].isoformat() if parent_id is not None else item["name"]
            item["_sort"] = [first, str(item["id"])]
        return result

    def create(self, values: dict[str, Any]) -> dict[str, Any]:
        identifier = uuid4()
        definition = self.default_definition_id
        parent = values.get("parent_entry_id")
        if parent is not None:
            row = self.entry(parent)
            if row is None:
                raise ValueError("Parent unavailable")
            definition = row["_definition_id"]
        parameters = self._parameters(
            id=identifier,
            catalog=self.catalog_id,
            source=_SOURCE,
            definition=definition,
            instrument=values["instrument_id"],
            parent=parent,
            entry_type=values["entry_type"],
            name=values["name"],
            metadata=json.dumps(values["metadata"]),
        )
        self.connection.execute(
            text("""INSERT INTO catalog.entry(tenant_id,id,catalog_id,source_id,
            source_definition_id,instrument_id,parent_entry_id,entry_type,name,metadata,lifecycle_state)
            SELECT :tenant,:id,c.id,:source,:definition,:instrument,:parent,:entry_type,:name,
            CAST(:metadata AS jsonb),'active' FROM catalog.catalog c
            WHERE c.tenant_id=:tenant AND c.id=:catalog"""),
            parameters,
        )
        result = self.entry(identifier)
        assert result is not None
        return result

    def update(self, identifier: UUID, values: dict[str, Any]) -> dict[str, Any]:
        allowed = {
            "name": "name",
            "metadata": "metadata",
            "parent_entry_id": "parent_entry_id",
            "lifecycle_state": "lifecycle_state",
        }
        if not values or not set(values) <= set(allowed):
            raise ValueError("Invalid update fields")
        clauses = []
        parameters = self._parameters(id=identifier, catalog=self.catalog_id)
        for key, value in values.items():
            if key == "metadata":
                parameters[key] = json.dumps(value)
                clauses.append("metadata=CAST(:metadata AS jsonb)")
            else:
                parameters[key] = (
                    "tombstone" if key == "lifecycle_state" and value == "tombstoned" else value
                )
                clauses.append(f"{allowed[key]}=:{key}")
        self.connection.execute(
            text(
                "UPDATE catalog.entry SET "
                + ",".join(clauses)
                + ",version=version+1,updated_at=pg_catalog.clock_timestamp() "
                "WHERE tenant_id=:tenant AND catalog_id=:catalog AND id=:id"
            ),
            parameters,
        )
        result = self.entry(identifier)
        assert result is not None
        return result

    def bump_catalog(self) -> dict[str, Any]:
        row = self.connection.execute(
            text("""UPDATE catalog.catalog SET version=version+1,
            updated_at=pg_catalog.clock_timestamp() WHERE tenant_id=:tenant AND id=:catalog
            RETURNING id,version"""),
            self._parameters(catalog=self.catalog_id),
        ).one()
        return dict(row._mapping)
