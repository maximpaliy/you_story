"""Actor-bound catalog use cases; repository scopes retain the authorization locks."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Any
from uuid import UUID

from you_story.catalog.application.cursors import CursorSigner
from you_story.catalog.domain.policy import (
    MAX_VERSION,
    CatalogFailure,
    defined_metadata,
    exact,
    identifier,
    integer,
    invalid,
    name,
    require_version,
)
from you_story.identity.public import require_validated_actor
from you_story.shared.context import ActorContext


def _json_value(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _json_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_value(v) for v in value]
    return value


def _catalog(value: dict[str, Any]) -> dict[str, Any]:
    return {"id": str(value["id"]), "version": value["version"]}


def _entry(value: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "id",
        "catalog_id",
        "parent_id",
        "source_key",
        "source_definition_version",
        "instrument_id",
        "type",
        "name",
        "state",
        "version",
    )
    result = {key: _json_value(value[key]) for key in keys}
    metadata_keys = {
        "song": ("author",),
        "version": ("level",),
        "fragment": ("length_seconds", "notes_count"),
    }[value["type"]]
    result["metadata"] = {key: value["metadata"][key] for key in metadata_keys}
    return result


def _references(value: dict[str, Any]) -> dict[str, Any]:
    field_keys = (
        "key",
        "kind",
        "nullable",
        "required_on_create",
        "required_on_replace",
        "min",
        "max",
        "default",
    )
    sources = []
    for source in value["sources"]:
        definition = source["definition"]
        sources.append(
            {
                "key": source["key"],
                "version": source["version"],
                "definition": {
                    "types": list(definition["types"]),
                    "parent_rules": [
                        {"parent_type": rule["parent_type"], "child_type": rule["child_type"]}
                        for rule in definition["parent_rules"]
                    ],
                    "metadata_rules": [
                        {
                            "entry_type": rule["entry_type"],
                            "fields": [
                                {key: field[key] for key in field_keys} for field in rule["fields"]
                            ],
                        }
                        for rule in definition["metadata_rules"]
                    ],
                    "practiceable_types": list(definition["practiceable_types"]),
                },
            }
        )
    return {
        "sources": sources,
        "instruments": [
            {"id": str(item["id"]), "key": item["key"], "name": item["name"]}
            for item in value["instruments"]
        ],
    }


def _mutation(catalog: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any]:
    return {"catalog": _catalog(catalog), "entry": _entry(entry)}


def _found(value: Any) -> Any:
    if value is None:
        raise CatalogFailure(404, "resource_not_found")
    return value


class CatalogService:
    def __init__(self, repository: Any, cursor_key: bytes) -> None:
        self._repository = repository
        self._cursors = CursorSigner(cursor_key)

    @contextmanager
    def _scope(self, actor: ActorContext, *, write: bool = False) -> Iterator[Any]:
        require_validated_actor(actor)
        with self._repository.transaction(actor, write=write) as store:
            yield store

    def get_catalog(self, actor: ActorContext) -> dict[str, Any]:
        with self._scope(actor) as store:
            return _catalog(_found(store.catalog()))

    def references(self, actor: ActorContext) -> dict[str, Any]:
        with self._scope(actor) as store:
            return _references(store.references())

    def get_entry(self, actor: ActorContext, entry_id: UUID) -> dict[str, Any]:
        with self._scope(actor) as store:
            _found(store.catalog())
            return _entry(_found(store.entry(identifier(entry_id))))

    def ancestors(self, actor: ActorContext, entry_id: UUID) -> dict[str, Any]:
        with self._scope(actor) as store:
            _found(store.catalog())
            entry_id = identifier(entry_id)
            _found(store.entry(entry_id))
            return {"items": [_entry(item) for item in store.ancestors(entry_id)]}

    def search(
        self,
        actor: ActorContext,
        filters: dict[str, Any],
        page_size: int = 50,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        return self._page(actor, filters, page_size, cursor, None)

    def browse_roots(
        self,
        actor: ActorContext,
        page_size: int = 50,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        return self._page(actor, {}, page_size, cursor, None, roots_only=True)

    def children(
        self,
        actor: ActorContext,
        entry_id: UUID,
        page_size: int = 50,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        return self._page(actor, {}, page_size, cursor, identifier(entry_id))

    def _page(
        self,
        actor: ActorContext,
        filters: dict[str, Any],
        page_size: int,
        cursor: str | None,
        parent_id: UUID | None,
        *,
        roots_only: bool = False,
    ) -> dict[str, Any]:
        require_validated_actor(actor)
        size = integer(page_size, 1, 100)
        values = dict(
            exact(
                filters,
                {"text", "author", "source_key", "instrument_id", "entry_type", "ancestor_id"},
                set(),
            )
        )
        for field in ("text", "author"):
            if field in values:
                values[field] = name(values[field], empty=True)
                if not values[field]:
                    del values[field]
        for field in ("instrument_id", "ancestor_id"):
            if field in values:
                values[field] = identifier(values[field])
        if "source_key" in values and values["source_key"] != "yousician":
            raise invalid()
        if "entry_type" in values and values["entry_type"] not in ("song", "version", "fragment"):
            raise invalid()
        binding = {
            "actor": str(actor.actor_id),
            "tenant": str(actor.tenant_id),
            "operation": "children" if parent_id else ("roots" if roots_only else "search"),
            "parent": str(parent_id) if parent_id else None,
            "filters": hashlib.sha256(
                json.dumps(
                    _json_value(values), sort_keys=True, separators=(",", ":"), ensure_ascii=False
                ).encode()
            ).hexdigest(),
        }
        after = self._cursors.decode(cursor, binding) if cursor is not None else None
        with self._scope(actor) as store:
            _found(store.catalog())
            if parent_id is not None:
                _found(store.entry(parent_id))
            if "ancestor_id" in values:
                _found(store.entry(values["ancestor_id"]))
            if "instrument_id" in values:
                instruments = store.references()["instruments"]
                if not any(str(item["id"]) == str(values["instrument_id"]) for item in instruments):
                    raise invalid()
            query_values = values | ({"roots_only": True} if roots_only else {})
            rows = store.entries(query_values, after=after, limit=size + 1, parent_id=parent_id)
            token = None
            if len(rows) > size:
                rows = rows[:size]
                token = self._cursors.encode(binding, [str(x) for x in rows[-1]["_sort"]])
            return {"items": [_entry(item) for item in rows], "next_cursor": token}

    @staticmethod
    def _catalog_version(catalog: dict[str, Any], expected: tuple[UUID, int]) -> None:
        if type(expected) is not tuple or len(expected) != 2:
            raise invalid()
        expected_id = identifier(expected[0])
        version = integer(expected[1], 1, MAX_VERSION)
        if str(catalog["id"]) != str(expected_id) or catalog["version"] != version:
            raise CatalogFailure(412, "version_conflict")

    @staticmethod
    def _entry_version(entry: dict[str, Any], values: dict[str, Any]) -> None:
        if entry["version"] != require_version(values):
            raise CatalogFailure(412, "version_conflict")
        if entry["state"] != "active":
            raise CatalogFailure(409, "conflict")

    def create(
        self,
        actor: ActorContext,
        expected_catalog: tuple[UUID, int],
        values: dict[str, Any],
    ) -> dict[str, Any]:
        require_validated_actor(actor)
        fields = {
            "parent_entry_id",
            "source_key",
            "instrument_id",
            "entry_type",
            "name",
            "metadata",
        }
        data = dict(exact(values, fields, fields - {"parent_entry_id"}))
        data["instrument_id"] = identifier(data["instrument_id"])
        if data.get("parent_entry_id") is not None:
            data["parent_entry_id"] = identifier(data["parent_entry_id"])
        with self._scope(actor, write=True) as store:
            catalog = _found(store.catalog(lock=True))
            parent = (
                _found(store.entry(data["parent_entry_id"]))
                if data.get("parent_entry_id")
                else None
            )
            self._catalog_version(catalog, expected_catalog)
            if data["source_key"] != "yousician" or data["entry_type"] not in (
                "song",
                "version",
                "fragment",
            ):
                raise invalid()
            instruments = store.references()["instruments"]
            if not any(str(item["id"]) == str(data["instrument_id"]) for item in instruments):
                raise invalid()
            if parent is None:
                if data["entry_type"] != "song":
                    raise CatalogFailure(409, "conflict")
            elif (
                parent["state"] != "active"
                or parent["source_key"] != data["source_key"]
                or str(parent["instrument_id"]) != str(data["instrument_id"])
                or (parent["type"], data["entry_type"])
                not in (("song", "version"), ("version", "fragment"))
            ):
                raise CatalogFailure(409, "conflict")
            data["name"] = name(data["name"])
            definition = store.definition(parent["_definition_id"] if parent else None)
            data["metadata"] = defined_metadata(
                definition, data["entry_type"], data["metadata"], create=True
            )
            entry = store.create(data)
            return _mutation(store.bump_catalog(), entry)

    def update(
        self,
        actor: ActorContext,
        entry_id: UUID,
        expected_catalog: tuple[UUID, int],
        values: dict[str, Any],
    ) -> dict[str, Any]:
        require_validated_actor(actor)
        data = dict(exact(values, {"expected_entry_version", "name", "metadata"}, set()))
        with self._scope(actor, write=True) as store:
            catalog = _found(store.catalog(lock=True))
            entry = _found(store.entry(identifier(entry_id)))
            self._catalog_version(catalog, expected_catalog)
            self._entry_version(entry, data)
            if not {"name", "metadata"} & data.keys():
                raise invalid()
            changes: dict[str, Any] = {}
            if "name" in data:
                changes["name"] = name(data["name"])
            if "metadata" in data:
                changes["metadata"] = defined_metadata(
                    store.definition(entry["_definition_id"]),
                    entry["type"],
                    data["metadata"],
                    create=False,
                )
            result = store.update(identifier(entry_id), changes)
            return _mutation(store.bump_catalog(), result)

    def move(
        self,
        actor: ActorContext,
        entry_id: UUID,
        expected_catalog: tuple[UUID, int],
        values: dict[str, Any],
    ) -> dict[str, Any]:
        require_validated_actor(actor)
        data = exact(
            values, {"expected_entry_version", "new_parent_entry_id"}, {"new_parent_entry_id"}
        )
        parent_id = identifier(data["new_parent_entry_id"])
        with self._scope(actor, write=True) as store:
            catalog = _found(store.catalog(lock=True))
            entry = _found(store.entry(identifier(entry_id)))
            parent = _found(store.entry(parent_id))
            self._catalog_version(catalog, expected_catalog)
            self._entry_version(entry, data)
            if (
                parent["state"] != "active"
                or entry["type"] == "song"
                or (parent["type"], entry["type"])
                not in (("song", "version"), ("version", "fragment"))
                or any(
                    str(parent[k]) != str(entry[k])
                    for k in (
                        "catalog_id",
                        "source_key",
                        "instrument_id",
                        "source_definition_version",
                    )
                )
            ):
                raise CatalogFailure(409, "conflict")
            result = store.update(identifier(entry_id), {"parent_entry_id": parent_id})
            return _mutation(store.bump_catalog(), result)

    def tombstone(
        self,
        actor: ActorContext,
        entry_id: UUID,
        expected_catalog: tuple[UUID, int],
        values: dict[str, Any],
    ) -> dict[str, Any]:
        require_validated_actor(actor)
        data = exact(values, {"expected_entry_version"}, set())
        with self._scope(actor, write=True) as store:
            catalog = _found(store.catalog(lock=True))
            entry = _found(store.entry(identifier(entry_id)))
            self._catalog_version(catalog, expected_catalog)
            self._entry_version(entry, data)
            if store.entries({}, after=None, limit=1, parent_id=identifier(entry_id)):
                raise CatalogFailure(409, "conflict")
            result = store.update(identifier(entry_id), {"lifecycle_state": "tombstoned"})
            return _mutation(store.bump_catalog(), result)
