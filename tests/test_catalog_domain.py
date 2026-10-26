"""Independent boundary examples for source policy, cursor authority and public ports."""

from __future__ import annotations

from uuid import UUID

import pytest

from you_story.catalog.application.cursors import CursorSigner
from you_story.catalog.domain.policy import CatalogFailure, identifier, metadata, name
from you_story.catalog.public import CatalogService
from you_story.identity.public import AuthFailure
from you_story.shared.context import ActorContext


@pytest.mark.parametrize(
    ("kind", "given", "expected"),
    [
        ("song", {}, {"author": None}),
        ("song", {"author": "  Cafe\u0301  "}, {"author": "Café"}),
        ("version", {"level": 0}, {"level": 0}),
        ("version", {"level": 15}, {"level": 15}),
        ("fragment", {}, {"length_seconds": None, "notes_count": 0}),
        (
            "fragment",
            {"notes_count": 2147483647, "length_seconds": 1},
            {"notes_count": 2147483647, "length_seconds": 1},
        ),
    ],
)
def test_metadata_creation_defaults_and_normalization(kind, given, expected):
    assert metadata(kind, given, create=True) == expected


@pytest.mark.parametrize(
    ("kind", "given"),
    [
        ("song", {"author": " "}),
        ("song", {"visibility": "public"}),
        ("version", {}),
        ("version", {"level": True}),
        ("version", {"level": 1.0}),
        ("version", {"level": -1}),
        ("version", {"level": 16}),
        ("fragment", {"notes_count": None}),
        ("fragment", {"notes_count": False}),
        ("fragment", {"length_seconds": 0}),
        ("fragment", {"length_seconds": 2147483648}),
        ("fragment", {"notes_count": -1}),
        ("fragment", {"notes_count": 2147483648}),
        ("fragment", {"notes_count": 1, "extra": {}}),
    ],
)
def test_metadata_rejects_wrong_types_fields_and_bounds(kind, given):
    with pytest.raises(CatalogFailure) as failure:
        metadata(kind, given, create=True)
    assert (failure.value.status, failure.value.code) == (422, "invalid_input")


@pytest.mark.parametrize(
    ("kind", "given"), [("song", {}), ("fragment", {}), ("fragment", {"notes_count": 5})]
)
def test_replacement_cannot_silently_clear_or_default(kind, given):
    with pytest.raises(CatalogFailure):
        metadata(kind, given, create=False)


def test_nfc_name_limit_is_code_points_not_bytes():
    assert name(" e\u0301" * 100) == "é" + " é" * 99
    assert name("界" * 200) == "界" * 200
    with pytest.raises(CatalogFailure):
        name("界" * 201)
    with pytest.raises(CatalogFailure):
        name("\x00")


def test_cursor_integrity_scope_expiry_and_key_rotation():
    now = [1000.0]
    signer = CursorSigner(b"a" * 32, clock=lambda: now[0])
    binding = {"actor": "alice", "operation": "search", "filters": "author-a"}
    after = ["A song", "00000000-0000-0000-0000-000000000001"]
    token = signer.encode(binding, after)
    assert signer.decode(token, binding) == after
    for wrong in [
        binding | {"actor": "bob"},
        binding | {"filters": "author-b"},
        binding | {"operation": "children"},
    ]:
        with pytest.raises(CatalogFailure):
            signer.decode(token, wrong)
    with pytest.raises(CatalogFailure):
        CursorSigner(b"b" * 32, clock=lambda: now[0]).decode(token, binding)
    with pytest.raises(CatalogFailure):
        signer.decode(token[:-2] + "AA", binding)
    now[0] = 1900.0
    with pytest.raises(CatalogFailure):
        signer.decode(token, binding)


@pytest.mark.parametrize("token", ["", "a" * 2049, "é", "====", "abc=", "[]"])
def test_cursor_strict_bounds_and_canonical_encoding(token):
    with pytest.raises(CatalogFailure):
        CursorSigner(b"a" * 32).decode(token, {})


def test_cursor_key_required_and_payload_bounded():
    with pytest.raises(ValueError):
        CursorSigner(b"a" * 31)
    with pytest.raises(CatalogFailure):
        CursorSigner(b"a" * 32).encode({"filter": "界" * 600}, ["a", "b"])


def test_direct_use_cases_never_accept_forged_actor_before_repository_access():
    class Repository:
        def transaction(self, *args, **kwargs):
            pytest.fail("repository must not be reached by forged actor")

    actor = object.__new__(ActorContext)
    object.__setattr__(actor, "actor_id", UUID(int=1))
    object.__setattr__(actor, "tenant_id", UUID(int=2))
    object.__setattr__(actor, "provenance", "validated_identity")
    service = CatalogService(Repository(), b"a" * 32)
    for operation in [
        lambda: service.get_catalog(actor),
        lambda: service.references(actor),
        lambda: service.search(actor, {}),
        lambda: service.create(actor, (UUID(int=3), 1), {}),
        lambda: service.update(actor, UUID(int=4), (UUID(int=3), 1), {}),
        lambda: service.move(actor, UUID(int=4), (UUID(int=3), 1), {}),
        lambda: service.tombstone(actor, UUID(int=4), (UUID(int=3), 1), {}),
    ]:
        with pytest.raises(AuthFailure):
            operation()


def test_identifiers_reject_alternate_or_non_string_forms():
    assert identifier(str(UUID(int=1))) == UUID(int=1)
    for value in [1, True, "{00000000-0000-0000-0000-000000000001}", "bad"]:
        with pytest.raises(CatalogFailure):
            identifier(value)


def test_retained_definition_controls_metadata_after_default_changes():
    from copy import deepcopy

    from you_story.catalog.domain.policy import defined_metadata

    v1 = {
        "metadata_rules": [
            {
                "entry_type": "version",
                "fields": [
                    {
                        "key": "level",
                        "kind": "integer",
                        "nullable": False,
                        "required_on_create": True,
                        "required_on_replace": True,
                        "min": 0,
                        "max": 15,
                        "default": None,
                    }
                ],
            }
        ]
    }
    v2 = deepcopy(v1)
    v2["metadata_rules"][0]["fields"][0]["max"] = 10
    assert defined_metadata(v1, "version", {"level": 15}, create=True) == {"level": 15}
    with pytest.raises(CatalogFailure):
        defined_metadata(v2, "version", {"level": 15}, create=True)
    assert defined_metadata(v2, "version", {"level": 10}, create=True) == {"level": 10}
    # Retained bindings keep their original interpretation even after new publication.
    assert defined_metadata(v1, "version", {"level": 15}, create=False) == {"level": 15}


def test_public_response_allowlists_drop_poisoned_repository_columns():
    from contextlib import contextmanager
    from types import SimpleNamespace
    from uuid import uuid4

    from you_story.identity.infrastructure.actors import _issue_actor

    actor = _issue_actor(uuid4(), uuid4())
    catalog_id, entry_id = uuid4(), uuid4()
    poison = {"tenant_id": "secret-tenant", "owner": "secret-owner", "grants": ["private"]}
    row = {
        "id": entry_id,
        "catalog_id": catalog_id,
        "parent_id": None,
        "source_key": "yousician",
        "source_definition_version": 1,
        "instrument_id": uuid4(),
        "type": "song",
        "name": "Song",
        "metadata": {"author": "Author", **poison},
        "state": "active",
        "version": 1,
        "_definition_id": uuid4(),
        **poison,
    }
    field = {
        "key": "author",
        "kind": "text",
        "nullable": True,
        "required_on_create": False,
        "required_on_replace": True,
        "min": 1,
        "max": 200,
        "default": None,
        **poison,
    }
    references = {
        "sources": [
            {
                "key": "yousician",
                "version": 1,
                **poison,
                "definition": {
                    "types": ["song"],
                    "parent_rules": [{"parent_type": None, "child_type": "song", **poison}],
                    "metadata_rules": [{"entry_type": "song", "fields": [field], **poison}],
                    "practiceable_types": [],
                    **poison,
                },
            }
        ],
        "instruments": [{"id": uuid4(), "key": "guitar", "name": "Guitar", **poison}],
        **poison,
    }

    class Repository:
        @contextmanager
        def transaction(self, actor, write=False):
            yield SimpleNamespace(
                catalog=lambda: {"id": catalog_id, "version": 1, **poison},
                entry=lambda identifier: row,
                references=lambda: references,
            )

    service = CatalogService(Repository(), b"a" * 32)
    assert service.get_catalog(actor) == {"id": str(catalog_id), "version": 1}
    result = service.get_entry(actor, entry_id)
    assert set(result) == {
        "id",
        "catalog_id",
        "parent_id",
        "source_key",
        "source_definition_version",
        "instrument_id",
        "type",
        "name",
        "metadata",
        "state",
        "version",
    }
    assert result["metadata"] == {"author": "Author"}
    import json

    public = json.dumps(service.references(actor))
    assert "secret-tenant" not in public and "secret-owner" not in public and "grants" not in public
