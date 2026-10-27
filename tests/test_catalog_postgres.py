"""Catalog policy and isolation exercised through the real runtime PostgreSQL role."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from threading import Barrier
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict
from sqlalchemy.engine import URL

from tests.db_support import initialize, runtime_connection
from you_story.catalog.domain.policy import CatalogFailure
from you_story.catalog.infrastructure.repository import CatalogRepository
from you_story.catalog.public import ensure_personal_catalog
from you_story.identity.infrastructure.actors import _issue_actor
from you_story.shared.config import Settings
from you_story.shared.database import Database

GUITAR = UUID("20000000-0000-4000-8000-000000000001")
PIANO = UUID("20000000-0000-4000-8000-000000000002")


@contextmanager
def conflict():
    with pytest.raises(CatalogFailure) as caught:
        yield
    assert (caught.value.status, caught.value.code) == (409, "conflict")


@pytest.fixture(scope="module")
def catalog_fixture():
    admin, owner, runtime = initialize("006_catalog")
    values = conninfo_to_dict(runtime)
    url = URL.create(
        "postgresql+psycopg",
        username=values["user"],
        password=values["password"],
        host=values["host"],
        port=int(values["port"]),
        database=values["dbname"],
    )
    database = Database(
        Settings(database_url=url.render_as_string(hide_password=False)), pool_size=4
    )
    try:
        yield CatalogRepository(database), database, admin, owner
    finally:
        database.close()


def create(repository, actor, kind, parent=None, instrument=GUITAR, **metadata):
    with repository.transaction(actor, write=True) as store:
        catalog = store.catalog(lock=True)
        assert catalog is not None
        result = store.create(
            {
                "source_key": "yousician",
                "instrument_id": instrument,
                "entry_type": kind,
                "name": f"{kind}-{uuid4()}",
                "parent_entry_id": parent,
                "metadata": metadata,
            }
        )
        store.bump_catalog()
        return result


@pytest.mark.postgres
def test_seeded_reference_and_full_tree_author_search(catalog_fixture):
    repository, database, _, _ = catalog_fixture
    actor = _issue_actor(uuid4(), uuid4())
    ensure_personal_catalog(database, actor)
    song = create(repository, actor, "song", author="Literal %_ Author")
    version = create(repository, actor, "version", song["id"], level=0)
    fragment = create(
        repository, actor, "fragment", version["id"], length_seconds=None, notes_count=0
    )
    with repository.transaction(actor) as store:
        assert store.catalog()["version"] == 4
        references = store.references()
        assert [row["key"] for row in references["instruments"]] == ["guitar", "piano"]
        assert references["sources"][0]["definition"]["practiceable_types"] == [
            "version",
            "fragment",
        ]
        assert "max_depth" not in references["sources"][0]["definition"]
        assert [row["id"] for row in store.ancestors(fragment["id"])] == [song["id"], version["id"]]
        assert {row["id"] for row in store.entries({"author": "%_"}, None, 101)} == {
            song["id"],
            version["id"],
            fragment["id"],
        }
        assert len(store.entries({"text": "literal %_"}, None, 101)) == 3
        assert store.entries({"author": "unmatched"}, None, 101) == []
        rows = store.entries({}, None, 2)
        assert len(rows) == 2
        remaining = store.entries({}, rows[-1]["_sort"], 2)
        assert len(remaining) == 1
        assert not {r["id"] for r in rows} & {r["id"] for r in remaining}


@pytest.mark.postgres
def test_scope_terminal_and_metadata_constraints_rollback(catalog_fixture):
    repository, database, _, _ = catalog_fixture
    actor = _issue_actor(uuid4(), uuid4())
    ensure_personal_catalog(database, actor)
    song = create(repository, actor, "song", author=None)
    version = create(repository, actor, "version", song["id"], level=15)
    with conflict():
        create(repository, actor, "fragment", song["id"], length_seconds=None, notes_count=0)
    for value in [True, 1.5, -1, 16]:
        with conflict():
            create(repository, actor, "version", song["id"], level=value)
    with conflict():
        create(repository, actor, "song", author=None, unknown="x")
    with conflict():
        create(
            repository, actor, "fragment", version["id"], PIANO, length_seconds=None, notes_count=0
        )
    with conflict():
        with repository.transaction(actor, write=True) as store:
            store.catalog(lock=True)
            store.update(song["id"], {"lifecycle_state": "tombstoned"})
    with repository.transaction(actor) as store:
        assert store.catalog()["version"] == 3
        assert store.entry(song["id"])["state"] == "active"
    with repository.transaction(actor, write=True) as store:
        store.catalog(lock=True)
        store.update(version["id"], {"lifecycle_state": "tombstoned"})
        store.bump_catalog()
    with conflict():
        with repository.transaction(actor, write=True) as store:
            store.catalog(lock=True)
            store.update(version["id"], {"name": "restored"})
    with repository.transaction(actor) as store:
        assert store.entry(version["id"])["state"] == "tombstoned"
        assert len(store.entries({}, None, 101)) == 1


@pytest.mark.postgres
def test_cross_tenant_and_missing_context(catalog_fixture):
    repository, database, _, _ = catalog_fixture
    a, b = _issue_actor(uuid4(), uuid4()), _issue_actor(uuid4(), uuid4())
    for actor in [a, b]:
        ensure_personal_catalog(database, actor)
    song = create(repository, a, "song", author="Private canary")
    with repository.transaction(b) as store:
        assert store.entry(song["id"]) is None
        assert store.entries({"author": "Private canary"}, None, 101) == []
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with runtime_connection() as connection:
            connection.execute("SELECT id FROM catalog.entry WHERE id=%s", (song["id"],)).fetchall()
    with runtime_connection(str(b.tenant_id)) as connection:
        assert (
            connection.execute("SELECT id FROM catalog.entry WHERE id=%s", (song["id"],)).fetchall()
            == []
        )
    # Same pooled connection is reused under a fresh authenticated actor.
    with repository.transaction(a) as store:
        assert store.entry(song["id"])["id"] == song["id"]


@pytest.mark.postgres
def test_definition_immutable_and_fixture_storage_seam(catalog_fixture):
    repository, database, _, owner = catalog_fixture
    with psycopg.connect(owner) as connection:
        with pytest.raises(psycopg.errors.CheckViolation):
            connection.execute("UPDATE catalog.source_definition SET definition=definition")
    # Synthetic source uses a two-node work->part graph, proving storage is not
    # hardcoded to Yousician. Public creation still admits only Yousician.
    source, definition, root, child = uuid4(), uuid4(), uuid4(), uuid4()
    with psycopg.connect(owner) as connection:
        connection.execute(
            "INSERT INTO catalog.source(id,key,name) VALUES (%s,%s,%s)",
            (source, str(source), "Songsterr fixture"),
        )
        connection.execute(
            "INSERT INTO catalog.source_definition(id,source_id,definition_version,definition) "
            "VALUES (%s,%s,1,%s::jsonb)",
            (
                definition,
                source,
                '{"max_depth":2,"types":["work","part"],"parent_rules":[{"parent_type":null,"child_type":"work"},{"parent_type":"work","child_type":"part"}],"metadata_rules":[{"entry_type":"work","fields":[]},{"entry_type":"part","fields":[]}],"practiceable_types":["part"]}',
            ),
        )
    actor = _issue_actor(uuid4(), uuid4())
    catalog = ensure_personal_catalog(database, actor)
    query = """INSERT INTO catalog.entry(tenant_id,id,catalog_id,source_id,source_definition_id,
       instrument_id,parent_entry_id,entry_type,name,metadata,lifecycle_state)
       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'{}','active')"""
    with runtime_connection(str(actor.tenant_id)) as connection:
        connection.execute(
            query,
            (
                actor.tenant_id,
                root,
                catalog,
                source,
                definition,
                GUITAR,
                None,
                "work",
                "Fixture work",
            ),
        )
        connection.execute(
            query,
            (
                actor.tenant_id,
                child,
                catalog,
                source,
                definition,
                GUITAR,
                root,
                "part",
                "Fixture part",
            ),
        )
    with pytest.raises(psycopg.errors.CheckViolation):
        with runtime_connection(str(actor.tenant_id)) as connection:
            connection.execute(
                query,
                (
                    actor.tenant_id,
                    uuid4(),
                    catalog,
                    source,
                    definition,
                    GUITAR,
                    child,
                    "part",
                    "Too deep",
                ),
            )


@pytest.mark.postgres
def test_catalog_lock_serializes_shared_version(catalog_fixture):
    repository, database, _, _ = catalog_fixture
    actor = _issue_actor(uuid4(), uuid4())
    ensure_personal_catalog(database, actor)
    barrier = Barrier(2)

    def attempt():
        barrier.wait(timeout=5)
        with repository.transaction(actor, write=True) as store:
            catalog = store.catalog(lock=True)
            if catalog["version"] != 1:
                return False
            store.create(
                {
                    "source_key": "yousician",
                    "instrument_id": GUITAR,
                    "entry_type": "song",
                    "name": "Concurrent",
                    "parent_entry_id": None,
                    "metadata": {"author": None},
                }
            )
            store.bump_catalog()
            return True

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: attempt(), range(2)))
    assert sorted(results) == [False, True]
    with repository.transaction(actor) as store:
        assert store.catalog()["version"] == 2
        assert len(store.entries({}, None, 101)) == 1


@pytest.mark.postgres
def test_definition_default_evolution_and_retained_parent_binding(catalog_fixture):
    import json

    repository, database, _, owner = catalog_fixture
    actor = _issue_actor(uuid4(), uuid4())
    ensure_personal_catalog(database, actor)
    old_song = create(repository, actor, "song", author=None)
    v2 = uuid4()
    with psycopg.connect(owner) as connection:
        row = connection.execute(
            "SELECT source_id,definition FROM catalog.source_definition WHERE id=%s",
            (UUID("30000000-0000-4000-8000-000000000001"),),
        ).fetchone()
        policy = row[1]
        policy["metadata_rules"][1]["fields"][0]["max"] = 20
        connection.execute(
            "INSERT INTO catalog.source_definition(id,source_id,definition_version,definition) "
            "VALUES (%s,%s,2,%s::jsonb)",
            (v2, row[0], json.dumps(policy)),
        )
    future = CatalogRepository(database, default_definition_id=v2)
    new_song = create(future, actor, "song", author=None)
    assert new_song["source_definition_version"] == 2
    assert (
        create(future, actor, "version", new_song["id"], level=20)["source_definition_version"] == 2
    )
    assert (
        create(future, actor, "version", old_song["id"], level=15)["source_definition_version"] == 1
    )
    with conflict():
        create(future, actor, "version", old_song["id"], level=20)
    old_version = create(future, actor, "version", old_song["id"], level=4)
    with conflict():
        with future.transaction(actor, write=True) as store:
            store.catalog(lock=True)
            store.update(old_version["id"], {"parent_entry_id": new_song["id"]})


@contextmanager
def remove_entry_predicates(database):
    """Deliberate SQL mutation; never imported by production code."""
    import re

    from sqlalchemy import event, text
    from sqlalchemy.sql.elements import TextClause

    observed = []

    def mutate(connection, statement, multiparams, params, execution_options):
        if isinstance(statement, TextClause) and "FROM catalog.entry e JOIN" in statement.text:
            sql = statement.text
            # Remove all three private aliases' actor/catalog restrictions. UUID
            # targets and unrelated filters remain, so guessed foreign ID and
            # inherited-author joins exercise the production query shapes.
            sql, count = re.subn(r"[epg]\.tenant_id=:tenant", "true", sql)
            sql, catalog_count = re.subn(r"[epg]\.catalog_id=:catalog", "true", sql)
            assert count and catalog_count, "Mutation must remove actual production guards"
            observed.append(sql)
            statement = text(sql)
        return statement, multiparams, params

    event.listen(database._engine, "before_execute", mutate, retval=True)
    try:
        yield observed
        assert observed, "Mutation positive control must execute a changed production query"
    finally:
        event.remove(database._engine, "before_execute", mutate)


@pytest.mark.postgres
def test_independent_rls_and_explicit_predicates_with_author_join(catalog_fixture):
    repository, database, _, owner = catalog_fixture
    a, b = _issue_actor(uuid4(), uuid4()), _issue_actor(uuid4(), uuid4())
    for actor in (a, b):
        ensure_personal_catalog(database, actor)
    author = "Author-defense-" + str(uuid4())
    song = create(repository, a, "song", author=author)
    version = create(repository, a, "version", song["id"], level=3)
    fragment = create(repository, a, "fragment", version["id"], length_seconds=None, notes_count=0)
    foreign_ids = {song["id"], version["id"], fragment["id"]}

    def read_foreign():
        with repository.transaction(b) as store:
            assert store.catalog() is not None
            return store.entry(fragment["id"]), store.entries({"author": author}, None, 101)

    # Layer one: RLS rejects a query whose explicit actor predicates are gone.
    with remove_entry_predicates(database):
        assert read_foreign() == (None, [])

    def rls_state():
        with psycopg.connect(owner) as connection:
            return connection.execute(
                "SELECT relrowsecurity,relforcerowsecurity "
                "FROM pg_catalog.pg_class WHERE oid='catalog.entry'::regclass"
            ).fetchone()

    assert rls_state() == (True, True)
    try:
        # Controlled owner-only DDL on the marker-guarded disposable fixture.
        # Commit before runtime access so this genuinely removes RLS enforcement.
        with psycopg.connect(owner) as connection:
            connection.execute("ALTER TABLE catalog.entry DISABLE ROW LEVEL SECURITY")
        assert rls_state() == (False, True)
        # Layer two: original production predicates independently deny guessed
        # IDs and cross-tenant author ancestry even without database RLS.
        assert read_foreign() == (None, [])
        # Positive control: removing both layers must expose the seeded canary.
        # Without this control, an accidental unrelated filter could mask leakage.
        with remove_entry_predicates(database):
            entry, rows = read_foreign()
            assert entry["id"] == fragment["id"]
            assert {row["id"] for row in rows} == foreign_ids
    finally:
        with psycopg.connect(owner) as connection:
            connection.execute("ALTER TABLE catalog.entry ENABLE ROW LEVEL SECURITY")
            connection.execute("ALTER TABLE catalog.entry FORCE ROW LEVEL SECURITY")
        assert rls_state() == (True, True)
    with remove_entry_predicates(database):
        assert read_foreign() == (None, [])


@pytest.mark.postgres
def test_repeatable_read_ancestry_and_author_during_move(catalog_fixture):
    repository, database, _, _ = catalog_fixture
    actor = _issue_actor(uuid4(), uuid4())
    ensure_personal_catalog(database, actor)
    old_song = create(repository, actor, "song", author="Before move author")
    new_song = create(repository, actor, "song", author="After move author")
    old_version = create(repository, actor, "version", old_song["id"], level=2)
    new_version = create(repository, actor, "version", new_song["id"], level=2)
    fragment = create(
        repository, actor, "fragment", old_version["id"], length_seconds=None, notes_count=0
    )

    def move():
        with repository.transaction(actor, write=True) as store:
            store.catalog(lock=True)
            store.update(fragment["id"], {"parent_entry_id": new_version["id"]})
            store.bump_catalog()

    with repository.transaction(actor) as snapshot:
        assert snapshot.entry(fragment["id"])["parent_id"] == old_version["id"]
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(move).result(timeout=5)
        assert [row["id"] for row in snapshot.ancestors(fragment["id"])] == [
            old_song["id"],
            old_version["id"],
        ]
        assert fragment["id"] in {
            r["id"] for r in snapshot.entries({"author": "Before move"}, None, 101)
        }
        assert fragment["id"] not in {
            r["id"] for r in snapshot.entries({"author": "After move"}, None, 101)
        }
    with repository.transaction(actor) as current:
        assert [row["id"] for row in current.ancestors(fragment["id"])] == [
            new_song["id"],
            new_version["id"],
        ]
        assert fragment["id"] in {
            r["id"] for r in current.entries({"author": "After move"}, None, 101)
        }


@pytest.mark.postgres
def test_catalog_lock_timeout_rolls_back_without_partial_change(catalog_fixture):
    from threading import Event

    repository, database, _, _ = catalog_fixture
    actor = _issue_actor(uuid4(), uuid4())
    ensure_personal_catalog(database, actor)
    song = create(repository, actor, "song", author=None)
    entered = Event()

    def competing_edit():
        try:
            with repository.transaction(actor, write=True) as store:
                entered.set()
                store.catalog(lock=True)
                store.update(song["id"], {"name": "Must never commit"})
                store.bump_catalog()
        except CatalogFailure as error:
            assert (error.status, error.code) == (503, "unavailable")
            return "timed_out"
        raise AssertionError("Blocked catalog mutation unexpectedly committed")

    with repository.transaction(actor, write=True) as blocker:
        original = blocker.catalog(lock=True)
        with ThreadPoolExecutor(max_workers=1) as pool:
            attempt = pool.submit(competing_edit)
            assert entered.wait(timeout=2)
            assert attempt.result(timeout=6) == "timed_out"
    with repository.transaction(actor) as store:
        assert store.catalog() == original
        unchanged = store.entry(song["id"])
        assert unchanged["name"] == song["name"] and unchanged["version"] == song["version"]
