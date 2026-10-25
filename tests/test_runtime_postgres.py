"""Real runtime-role lifecycle evidence with synthetic contexts, never identity issuance."""

import asyncio
import random
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from uuid import UUID, uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.conninfo import conninfo_to_dict
from sqlalchemy import event, text
from sqlalchemy.engine import URL, Connection
from sqlalchemy.exc import DBAPIError

from tests.db_support import initialize
from tests.test_auth_crypto import settings as auth_fixture
from you_story.app import create_app
from you_story.shared import database as database_module
from you_story.shared.config import Settings
from you_story.shared.context import ActorContext
from you_story.shared.database import ContextFailure, Database

pytestmark = pytest.mark.postgres


def synthetic_actor(tenant: UUID | None = None) -> ActorContext:
    actor = object.__new__(ActorContext)
    object.__setattr__(actor, "actor_id", uuid4())
    object.__setattr__(actor, "tenant_id", tenant or uuid4())
    object.__setattr__(actor, "provenance", "validated_identity")
    return actor


@pytest.fixture(scope="module")
def database_settings() -> tuple[Settings, str, str]:
    admin, owner, runtime = initialize()
    values = conninfo_to_dict(runtime)
    url = URL.create(
        "postgresql+psycopg",
        username=values["user"],
        password=values["password"],
        host=values["host"],
        port=int(values["port"]),
        database=values["dbname"],
    ).render_as_string(hide_password=False)
    return Settings(database_url=url), owner, admin


@pytest.fixture
def db(database_settings: tuple[Settings, str, str]):
    instance = Database(database_settings[0], pool_size=1)
    yield instance
    instance.close()


def test_ready_real_and_health(database_settings: tuple[Settings, str, str], db: Database) -> None:
    assert db.ready()
    with TestClient(create_app(database_settings[0], auth_settings=auth_fixture())) as client:
        assert client.get("/live").status_code == 200
        assert client.get("/ready").status_code == 200


def test_ready_exact_revision_checksums(
    database_settings: tuple[Settings, str, str], db: Database
) -> None:
    with psycopg.connect(database_settings[1]) as owner:
        original = owner.execute(
            "SELECT checksum FROM foundation.schema_revision WHERE version='000_security'"
        ).fetchone()[0]
        owner.execute(
            "UPDATE foundation.schema_revision SET checksum='altered' WHERE version='000_security'"
        )
    try:
        assert not db.ready()
    finally:
        with psycopg.connect(database_settings[1]) as owner:
            owner.execute(
                "UPDATE foundation.schema_revision SET checksum=%s WHERE version='000_security'",
                (original,),
            )
    with psycopg.connect(database_settings[1]) as owner:
        owner.execute(
            "INSERT INTO foundation.schema_revision(version,checksum) "
            "VALUES ('999_unknown','unknown')"
        )
    try:
        assert not db.ready()
    finally:
        with psycopg.connect(database_settings[1]) as owner:
            owner.execute("DELETE FROM foundation.schema_revision WHERE version='999_unknown'")
    assert db.ready()


def test_wrong_role_and_extra_privilege_make_ready_false(
    database_settings: tuple[Settings, str, str], db: Database
) -> None:
    with psycopg.connect(database_settings[2], autocommit=True) as admin:
        admin.execute("ALTER ROLE app_runtime BYPASSRLS")
    try:
        assert not db.ready()
    finally:
        with psycopg.connect(database_settings[2], autocommit=True) as admin:
            admin.execute("ALTER ROLE app_runtime NOBYPASSRLS")
    with psycopg.connect(database_settings[1]) as owner:
        owner.execute("GRANT USAGE ON SCHEMA media TO app_runtime")
    try:
        assert not db.ready()
    finally:
        with psycopg.connect(database_settings[1]) as owner:
            owner.execute("REVOKE USAGE ON SCHEMA media FROM app_runtime")
    assert db.ready()


def test_same_backend_a_b_missing_and_session_stale(db: Database) -> None:
    pids = []
    for actor in [synthetic_actor(), synthetic_actor()]:
        with db.unit_of_work(actor) as work:
            connection = work._require_active()
            pids.append(connection.execute(text("SELECT pg_backend_pid()")).scalar_one())
            assert (
                connection.execute(text("SELECT identity.current_tenant_id()")).scalar_one()
                == actor.tenant_id
            )
            connection.execute(
                text("SELECT set_config('app.tenant_id', :stale, false)"), {"stale": str(uuid4())}
            )
        with pytest.raises(ContextFailure, match="Database context unavailable"):
            work._require_active()
    with db._engine.connect() as connection:
        pids.append(connection.execute(text("SELECT pg_backend_pid()")).scalar_one())
        with pytest.raises(DBAPIError):
            connection.execute(text("SELECT identity.current_tenant_id()"))
    assert len(set(pids)) == 1


def test_first_statements_nested_and_rollback_only(db: Database) -> None:
    statements = []

    def capture(connection, cursor, statement, parameters, context, many):
        statements.append(statement)

    event.listen(db._engine, "before_cursor_execute", capture)
    actor = synthetic_actor()
    with db.unit_of_work(actor) as work:
        assert statements[0].startswith("SELECT pg_catalog.set_config")
        assert statements[1] == "SELECT identity.current_tenant_id()"
        with db.unit_of_work(actor) as nested:
            assert nested is work
        before = len(statements)
        with pytest.raises(ContextFailure):
            with db.unit_of_work(synthetic_actor()):
                pytest.fail("foreign context entered")
        assert len(statements) == before
    with pytest.raises(ContextFailure) as error:
        with db.unit_of_work(actor):
            try:
                with db.unit_of_work(actor):
                    raise ValueError("domain error")
            except ValueError:
                pass
    assert error.value.category == "rollback_only"


@pytest.mark.parametrize("failure", [ValueError, asyncio.CancelledError])
def test_exception_and_cancellation_reset(db: Database, failure: type[BaseException]) -> None:
    with pytest.raises(failure):
        with db.unit_of_work(synthetic_actor()):
            raise failure()
    with db.unit_of_work(synthetic_actor()) as work:
        assert (
            work._require_active().execute(text("SELECT identity.current_tenant_id()")).scalar_one()
            == work._actor.tenant_id
        )


def test_failed_database_transaction_cleans_pool(db: Database) -> None:
    with pytest.raises(DBAPIError):
        with db.unit_of_work(synthetic_actor()) as work:
            work._require_active().execute(text("SELECT 1/0"))
    with db.unit_of_work(synthetic_actor()) as work:
        assert work._require_active().execute(text("SELECT 1")).scalar_one() == 1


def test_setup_mismatch_before_body(db: Database, monkeypatch: pytest.MonkeyPatch) -> None:
    original = Connection.execute

    def mismatch(self, statement, *args, **kwargs):
        if str(statement) == "SELECT identity.current_tenant_id()":
            return SimpleNamespace(scalar_one=lambda: uuid4())
        return original(self, statement, *args, **kwargs)

    monkeypatch.setattr(Connection, "execute", mismatch)
    with pytest.raises(ContextFailure) as error:
        with db.unit_of_work(synthetic_actor()):
            pytest.fail("setup mismatch reached body")
    assert error.value.category == "mismatch"


def test_invalid_context_before_any_checkout(db: Database) -> None:
    actor = synthetic_actor()
    object.__setattr__(actor, "tenant_id", "not-a-uuid")
    with pytest.raises(ContextFailure) as error:
        with db.unit_of_work(actor):
            pytest.fail("invalid context entered")
    assert error.value.category == "invalid"
    assert db._engine.pool.checkedout() == 0


def test_reset_failure_retires_backend(db: Database, monkeypatch: pytest.MonkeyPatch) -> None:
    original = database_module._reset_connection
    count = 0

    def fail_checkin(connection):
        nonlocal count
        count += 1
        if count == 2:
            raise RuntimeError("private sentinel")
        original(connection)

    monkeypatch.setattr(database_module, "_reset_connection", fail_checkin)
    with db.unit_of_work(synthetic_actor()) as work:
        first = work._require_active().execute(text("SELECT pg_backend_pid()")).scalar_one()
    with db.unit_of_work(synthetic_actor()) as work:
        second = work._require_active().execute(text("SELECT pg_backend_pid()")).scalar_one()
    assert first != second


def test_concurrent_random_tenants_no_bleed(db: Database) -> None:
    seed = 90210
    values = [UUID(int=random.Random(seed + n).getrandbits(128)) for n in range(24)]

    def visit(tenant):
        with db.unit_of_work(synthetic_actor(tenant)) as work:
            return (
                work._require_active()
                .execute(text("SELECT identity.current_tenant_id()"))
                .scalar_one()
            )

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert list(pool.map(visit, values)) == values, f"seed={seed}"


def test_missing_revision_and_unreachable_database(
    database_settings: tuple[Settings, str, str], db: Database
) -> None:
    with psycopg.connect(database_settings[1]) as owner:
        checksum = owner.execute(
            "DELETE FROM foundation.schema_revision WHERE version='004_media' RETURNING checksum"
        ).fetchone()[0]
    try:
        assert not db.ready()
    finally:
        with psycopg.connect(database_settings[1]) as owner:
            owner.execute(
                "INSERT INTO foundation.schema_revision(version,checksum) VALUES ('004_media',%s)",
                (checksum,),
            )
    unavailable = Database(
        Settings(database_url="postgresql+psycopg://app_runtime:synthetic@127.0.0.1:1/absent")
    )
    try:
        assert not unavailable.ready()
        with TestClient(create_app(readiness=unavailable.ready)) as client:
            response = client.get("/ready")
            assert response.status_code == 503
            assert "synthetic" not in response.text
    finally:
        unavailable.close()


def test_context_signals_are_observed_and_safe(
    db: Database, caplog: pytest.LogCaptureFixture
) -> None:
    import logging

    logger = logging.getLogger("you_story.context")
    with caplog.at_level(logging.WARNING, logger="you_story.context"):
        logger.warning("positive_capture_sentinel")
        assert caplog.records[-1].message == "positive_capture_sentinel"
        caplog.clear()
        with pytest.raises(ContextFailure):
            with db.unit_of_work(None):
                pytest.fail("missing context entered")
        actor = synthetic_actor()
        object.__setattr__(actor, "provenance", "secret-content-sentinel")
        with pytest.raises(ContextFailure):
            with db.unit_of_work(actor):
                pytest.fail("invalid context entered")
    assert [record.category for record in caplog.records] == ["missing", "invalid"]
    assert all(record.role == "app_runtime" for record in caplog.records)
    assert all(record.operation == "setup" for record in caplog.records)
    assert all(hasattr(record, "correlation_id") for record in caplog.records)
    assert "secret-content-sentinel" not in caplog.text
    assert str(actor.tenant_id) not in caplog.text


@pytest.mark.parametrize(
    "grant",
    [
        "GRANT SELECT ON identity.login_transaction TO app_runtime",
        "GRANT SELECT (subject_digest) ON identity.auth_rate_limit TO app_runtime",
    ],
)
def test_new_auth_control_plane_grants_make_ready_false(
    database_settings: tuple[Settings, str, str], db: Database, grant: str
) -> None:
    revoke = grant.replace("GRANT SELECT", "REVOKE SELECT").replace(" TO ", " FROM ")
    with psycopg.connect(database_settings[1]) as owner:
        owner.execute(grant)
    try:
        assert not db.ready()
    finally:
        with psycopg.connect(database_settings[1]) as owner:
            owner.execute(revoke)
    assert db.ready()
