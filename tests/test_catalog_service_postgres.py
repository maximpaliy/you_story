"""Real runtime PostgreSQL adversarial tests through owning catalog public ports."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID, uuid4

import pytest

from tests.test_catalog_postgres import GUITAR, PIANO, catalog_fixture  # noqa: F401
from you_story.catalog.public import CatalogFailure, CatalogService, ensure_personal_catalog
from you_story.identity.infrastructure.actors import _issue_actor
from you_story.identity.public import AuthFailure
from you_story.shared.context import ActorContext

pytestmark = pytest.mark.postgres


@pytest.fixture
def ports(catalog_fixture):  # noqa: F811
    repository, database, _, _ = catalog_fixture
    service = CatalogService(repository, b"s" * 32)
    a, b = _issue_actor(uuid4(), uuid4()), _issue_actor(uuid4(), uuid4())
    for actor in (a, b):
        ensure_personal_catalog(database, actor)
    return service, a, b


def expected(service, actor):
    catalog = service.get_catalog(actor)
    return UUID(catalog["id"]), catalog["version"]


def add(service, actor, kind="song", parent=None, instrument=GUITAR, name="Song", **metadata):
    return service.create(
        actor,
        expected(service, actor),
        {
            "source_key": "yousician",
            "instrument_id": str(instrument),
            "entry_type": kind,
            "parent_entry_id": parent,
            "name": name,
            "metadata": metadata,
        },
    )["entry"]


def tree(service, actor, author="Private author"):
    song = add(service, actor, author=author)
    version = add(service, actor, "version", song["id"], name="Version", level=4)
    fragment = add(service, actor, "fragment", version["id"], name="Fragment")
    return song, version, fragment


def failure(status, code, operation):
    with pytest.raises(CatalogFailure) as caught:
        operation()
    assert (caught.value.status, caught.value.code) == (status, code)


def test_public_tree_navigation_and_terminal_lifecycle(ports):
    service, a, _ = ports
    song, version, fragment = tree(service, a)
    assert [x["id"] for x in service.ancestors(a, UUID(fragment["id"]))["items"]] == [
        song["id"],
        version["id"],
    ]
    assert [x["id"] for x in service.children(a, UUID(song["id"]))["items"]] == [version["id"]]
    failure(
        409,
        "conflict",
        lambda: service.tombstone(
            a, UUID(song["id"]), expected(service, a), {"expected_entry_version": 1}
        ),
    )
    result = service.tombstone(
        a, UUID(fragment["id"]), expected(service, a), {"expected_entry_version": 1}
    )
    assert result["entry"]["state"] == "tombstoned"
    assert service.get_entry(a, UUID(fragment["id"]))["state"] == "tombstoned"
    assert service.children(a, UUID(version["id"]))["items"] == []
    failure(
        409,
        "conflict",
        lambda: service.update(
            a,
            UUID(fragment["id"]),
            expected(service, a),
            {"expected_entry_version": 2, "name": "Restore"},
        ),
    )


@pytest.mark.parametrize(
    "which",
    [
        "detail",
        "children",
        "ancestors",
        "filter",
        "update",
        "move_target",
        "move_parent",
        "create_parent",
        "tombstone",
    ],
)
def test_foreign_and_missing_selectors_have_identical_public_errors(ports, which):
    service, a, b = ports
    song, version, fragment = tree(service, a)
    own_song, own_version, own_fragment = tree(service, b, "Other author")
    del own_song

    def operation(target):
        cv = expected(service, b)
        if which == "detail":
            return service.get_entry(b, target)
        if which == "children":
            return service.children(b, target)
        if which == "ancestors":
            return service.ancestors(b, target)
        if which == "filter":
            return service.search(b, {"ancestor_id": str(target)})
        if which == "update":
            return service.update(b, target, cv, {"expected_entry_version": 99, "name": "X"})
        if which == "move_target":
            return service.move(
                b,
                target,
                cv,
                {"expected_entry_version": 99, "new_parent_entry_id": own_version["id"]},
            )
        if which == "move_parent":
            return service.move(
                b,
                UUID(own_fragment["id"]),
                cv,
                {"expected_entry_version": 1, "new_parent_entry_id": str(target)},
            )
        if which == "create_parent":
            return add(service, b, "fragment", str(target))
        return service.tombstone(b, target, cv, {"expected_entry_version": 99})

    before = service.get_catalog(b)
    for target in (UUID(fragment["id"]), uuid4()):
        failure(404, "resource_not_found", lambda target=target: operation(target))
    assert service.get_catalog(b) == before
    assert service.get_entry(a, UUID(song["id"]))["metadata"]["author"] == "Private author"
    assert service.search(b, {"author": "Private author"})["items"] == []
    assert service.search(b, {"text": "Private author"})["items"] == []
    assert service.get_entry(a, UUID(version["id"]))["version"] == 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("tenant_id", str(uuid4())),
        ("owner", str(uuid4())),
        ("visibility", "shared"),
        ("state", "tombstoned"),
        ("version", 99),
        ("source_definition_version", 2),
    ],
)
def test_mass_assignment_cannot_change_authority_or_versions(ports, field, value):
    service, a, _ = ports
    song = add(service, a)
    before = service.get_catalog(a)
    failure(
        422,
        "invalid_input",
        lambda: service.update(
            a,
            UUID(song["id"]),
            expected(service, a),
            {"expected_entry_version": 1, "name": "X", field: value},
        ),
    )
    failure(
        422,
        "invalid_input",
        lambda: service.create(
            a,
            expected(service, a),
            {
                "source_key": "yousician",
                "instrument_id": str(GUITAR),
                "entry_type": "song",
                "name": "X",
                "metadata": {},
                field: value,
            },
        ),
    )
    assert service.get_catalog(a) == before
    assert service.get_entry(a, UUID(song["id"]))["version"] == 1


def test_wrong_hierarchy_instrument_and_unknown_metadata_roll_back(ports):
    service, a, _ = ports
    song, version, fragment = tree(service, a)
    piano_song = add(service, a, instrument=PIANO)
    before = service.get_catalog(a)
    failure(409, "conflict", lambda: add(service, a, "fragment", song["id"]))
    failure(
        409,
        "conflict",
        lambda: service.move(
            a,
            UUID(version["id"]),
            expected(service, a),
            {"expected_entry_version": 1, "new_parent_entry_id": fragment["id"]},
        ),
    )
    failure(
        409,
        "conflict",
        lambda: service.move(
            a,
            UUID(version["id"]),
            expected(service, a),
            {"expected_entry_version": 1, "new_parent_entry_id": piano_song["id"]},
        ),
    )
    failure(
        422,
        "invalid_input",
        lambda: service.update(
            a,
            UUID(song["id"]),
            expected(service, a),
            {
                "expected_entry_version": 1,
                "metadata": {"author": None, "tenant_id": str(a.tenant_id)},
            },
        ),
    )
    assert service.get_catalog(a) == before
    assert service.get_entry(a, UUID(version["id"]))["parent_id"] == song["id"]


def test_version_preconditions_do_not_silently_overwrite(ports):
    service, a, _ = ports
    song = add(service, a)
    old = expected(service, a)
    edited = service.update(
        a, UUID(song["id"]), old, {"expected_entry_version": 1, "name": "Changed"}
    )
    assert edited["catalog"]["version"] == old[1] + 1
    assert edited["entry"]["version"] == 2
    failure(
        412,
        "version_conflict",
        lambda: service.update(
            a, UUID(song["id"]), old, {"expected_entry_version": 1, "name": "Stale"}
        ),
    )
    failure(
        412,
        "version_conflict",
        lambda: service.update(
            a,
            UUID(song["id"]),
            expected(service, a),
            {"expected_entry_version": 1, "name": "Stale"},
        ),
    )
    failure(
        428,
        "precondition_required",
        lambda: service.update(a, UUID(song["id"]), expected(service, a), {"name": "Missing"}),
    )
    failure(
        422,
        "invalid_input",
        lambda: service.update(
            a,
            UUID(song["id"]),
            expected(service, a),
            {"expected_entry_version": True, "name": "Bool"},
        ),
    )
    assert service.get_entry(a, UUID(song["id"]))["name"] == "Changed"
    assert service.get_catalog(a) == edited["catalog"]


def test_author_inheritance_follows_rename_and_move_and_cursor_is_bound(ports):
    service, a, b = ports
    song, version, fragment = tree(service, a, "Old Author")
    other = add(service, a, author="New Author", name="Other")
    other_version = add(service, a, "version", other["id"], level=2)
    results = service.search(a, {"author": "old author"}, 1)
    assert results["next_cursor"] is not None
    failure(
        422,
        "invalid_input",
        lambda: service.search(a, {"author": "New Author"}, 1, results["next_cursor"]),
    )
    failure(
        422,
        "invalid_input",
        lambda: service.search(b, {"author": "old author"}, 1, results["next_cursor"]),
    )
    assert (
        service.search(a, {"author": "Old Author", "text": "Fragment"})["items"][0]["id"]
        == fragment["id"]
    )
    moved = service.move(
        a,
        UUID(fragment["id"]),
        expected(service, a),
        {"expected_entry_version": 1, "new_parent_entry_id": other_version["id"]},
    )
    assert moved["entry"]["parent_id"] == other_version["id"]
    assert fragment["id"] not in {
        x["id"] for x in service.search(a, {"author": "Old Author"})["items"]
    }
    assert fragment["id"] in {x["id"] for x in service.search(a, {"author": "New Author"})["items"]}
    service.update(
        a,
        UUID(other["id"]),
        expected(service, a),
        {"expected_entry_version": 1, "metadata": {"author": "Renamed Author"}},
    )
    assert service.search(a, {"author": "New Author"})["items"] == []
    assert len(service.search(a, {"text": "renamed author"})["items"]) == 3
    assert service.get_entry(a, UUID(version["id"]))["parent_id"] == song["id"]


def test_same_catalog_version_public_writes_have_one_winner(ports):
    service, a, _ = ports
    cv = expected(service, a)
    barrier = Barrier(2)

    def write(index):
        barrier.wait(timeout=5)
        try:
            service.create(
                a,
                cv,
                {
                    "source_key": "yousician",
                    "instrument_id": str(GUITAR),
                    "entry_type": "song",
                    "name": f"Concurrent {index}",
                    "metadata": {},
                },
            )
            return "created"
        except CatalogFailure as error:
            return error.status, error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(write, [1, 2]))
    assert results.count("created") == 1
    assert results.count((412, "version_conflict")) == 1
    assert service.get_catalog(a)["version"] == cv[1] + 1
    assert len(service.search(a, {})["items"]) == 1


def test_forged_actor_rejected_at_all_real_service_ports(ports):
    service, a, _ = ports
    song = add(service, a)
    forged = object.__new__(ActorContext)
    for key in ("actor_id", "tenant_id", "provenance"):
        object.__setattr__(forged, key, getattr(a, key))
    operations = [
        lambda: service.get_catalog(forged),
        lambda: service.references(forged),
        lambda: service.get_entry(forged, UUID(song["id"])),
        lambda: service.children(forged, UUID(song["id"])),
        lambda: service.ancestors(forged, UUID(song["id"])),
        lambda: service.search(forged, {}),
        lambda: service.create(forged, expected(service, a), {}),
        lambda: service.update(forged, UUID(song["id"]), expected(service, a), {}),
        lambda: service.move(forged, UUID(song["id"]), expected(service, a), {}),
        lambda: service.tombstone(forged, UUID(song["id"]), expected(service, a), {}),
    ]
    for operation in operations:
        with pytest.raises(AuthFailure):
            operation()


def test_same_version_create_vs_parent_tombstone_has_one_valid_serialization(ports):
    service, actor, _ = ports
    parent = add(service, actor, name="Leaf song")
    cv = expected(service, actor)
    barrier = Barrier(2)

    def attempt(operation):
        barrier.wait(timeout=5)
        try:
            if operation == "create":
                result = service.create(
                    actor,
                    cv,
                    {
                        "source_key": "yousician",
                        "instrument_id": str(GUITAR),
                        "entry_type": "version",
                        "parent_entry_id": parent["id"],
                        "name": "Racing child",
                        "metadata": {"level": 3},
                    },
                )
            else:
                result = service.tombstone(
                    actor, UUID(parent["id"]), cv, {"expected_entry_version": 1}
                )
            return operation, result
        except CatalogFailure as error:
            return operation, (error.status, error.code)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = dict(pool.map(attempt, ["create", "tombstone"]))
    winner = [key for key, result in results.items() if isinstance(result, dict)]
    assert len(winner) == 1
    loser = "tombstone" if winner == ["create"] else "create"
    assert results[loser] == (412, "version_conflict")
    current_parent = service.get_entry(actor, UUID(parent["id"]))
    children = service.children(actor, UUID(parent["id"]))["items"]
    assert service.get_catalog(actor)["version"] == cv[1] + 1
    if winner == ["create"]:
        assert current_parent["state"] == "active"
        assert current_parent["version"] == 1
        assert [child["id"] for child in children] == [results["create"]["entry"]["id"]]
    else:
        assert current_parent["state"] == "tombstoned"
        assert current_parent["version"] == 2
        assert children == []
    # Inspect the current committed public tree, not only each thread's return.
    assert current_parent["state"] == "active" or not children


def test_same_version_move_vs_destination_tombstone_has_one_valid_serialization(ports):
    service, actor, _ = ports
    _, original_version, fragment = tree(service, actor)
    destination_song = add(service, actor, name="Destination")
    destination = add(service, actor, "version", destination_song["id"], level=2)
    cv = expected(service, actor)
    barrier = Barrier(2)

    def attempt(operation):
        barrier.wait(timeout=5)
        try:
            if operation == "move":
                result = service.move(
                    actor,
                    UUID(fragment["id"]),
                    cv,
                    {"expected_entry_version": 1, "new_parent_entry_id": destination["id"]},
                )
            else:
                result = service.tombstone(
                    actor, UUID(destination["id"]), cv, {"expected_entry_version": 1}
                )
            return operation, result
        except CatalogFailure as error:
            return operation, (error.status, error.code)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = dict(pool.map(attempt, ["move", "tombstone"]))
    winner = [key for key, result in results.items() if isinstance(result, dict)]
    assert len(winner) == 1
    loser = "tombstone" if winner == ["move"] else "move"
    assert results[loser] == (412, "version_conflict")
    current_destination = service.get_entry(actor, UUID(destination["id"]))
    current_fragment = service.get_entry(actor, UUID(fragment["id"]))
    children = service.children(actor, UUID(destination["id"]))["items"]
    assert service.get_catalog(actor)["version"] == cv[1] + 1
    if winner == ["move"]:
        assert current_destination["state"] == "active"
        assert current_fragment["parent_id"] == destination["id"]
        assert current_fragment["version"] == 2
        assert [child["id"] for child in children] == [fragment["id"]]
    else:
        assert current_destination["state"] == "tombstoned"
        assert current_fragment["parent_id"] == original_version["id"]
        assert current_fragment["version"] == 1
        assert children == []
    assert current_destination["state"] == "active" or not children
