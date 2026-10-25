"""Login-only empty catalog provisioning through runtime role and validated actors."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict
from sqlalchemy import event, select
from sqlalchemy.engine import URL
from sqlalchemy.sql import operators
from sqlalchemy.sql.dml import Insert
from sqlalchemy.sql.elements import BinaryExpression, BindParameter
from sqlalchemy.sql.selectable import Select

from tests.db_support import initialize
from you_story.catalog.infrastructure import provisioning
from you_story.catalog.public import ensure_personal_catalog
from you_story.identity.infrastructure.actors import _issue_actor
from you_story.identity.public import AuthFailure
from you_story.shared.config import Settings
from you_story.shared.context import ActorContext
from you_story.shared.database import Database


def test_forged_actor_rejected_before_database() -> None:
    database = MagicMock()
    forged = object.__new__(ActorContext)
    object.__setattr__(forged, "actor_id", uuid4())
    object.__setattr__(forged, "tenant_id", uuid4())
    object.__setattr__(forged, "provenance", "validated_identity")
    with pytest.raises(AuthFailure, match="Authentication request failed"):
        ensure_personal_catalog(database, forged)
    database.unit_of_work.assert_not_called()


def _assert_actor_scoped(statement, actor: ActorContext) -> None:
    """Independent semantic oracle for every private insert/read in this slice."""
    if isinstance(statement, Insert):
        tenant = statement._values["tenant_id"]
        assert isinstance(tenant, BindParameter)
        assert tenant.key == "actor_tenant_id" and tenant.value is actor.tenant_id
        if statement.table.name == "catalog_grant":
            assert statement._values["grantee_tenant_id"] is tenant
            assert statement._values["role"].value == "owner"
        return
    assert isinstance(statement, Select)
    for relation in statement.get_final_froms():
        scoped = False
        for criterion in statement._where_criteria:
            assert isinstance(criterion, BinaryExpression)
            assert criterion.operator is operators.eq
            if criterion.left is relation.c.tenant_id:
                tenant = criterion.right
                assert isinstance(tenant, BindParameter)
                assert tenant.key == "actor_tenant_id" and tenant.value is actor.tenant_id
                scoped = True
        assert scoped, "Private alias lacks explicit actor predicate"


def test_statement_scope_oracle_and_missing_predicate_mutation() -> None:
    actor = _issue_actor(uuid4(), uuid4())
    connection = MagicMock()
    identifier = uuid4()
    connection.execute.return_value.scalar_one.return_value = identifier
    assert provisioning._ensure_pair(connection, actor) == identifier
    statements = [call.args[0] for call in connection.execute.call_args_list]
    assert len(statements) == 4
    for statement in statements:
        _assert_actor_scoped(statement, actor)
    with pytest.raises(AssertionError, match="Private alias lacks explicit actor predicate"):
        _assert_actor_scoped(select(provisioning._catalog.c.id), actor)


@pytest.fixture(scope="module")
def catalog_database():
    admin, _, runtime = initialize()
    values = conninfo_to_dict(runtime)
    url = URL.create(
        "postgresql+psycopg",
        username=values["user"],
        password=values["password"],
        host=values["host"],
        port=int(values["port"]),
        database=values["dbname"],
    ).render_as_string(hide_password=False)
    database = Database(Settings(database_url=url), pool_size=4)
    try:
        yield database, admin
    finally:
        database.close()


@pytest.mark.postgres
def test_pair_atomic_idempotent_cross_tenant_and_empty(catalog_database) -> None:
    database, inspector = catalog_database
    a, b = _issue_actor(uuid4(), uuid4()), _issue_actor(uuid4(), uuid4())
    observed = []

    def inspect(connection, cursor, sql, parameters, context, many):
        statement = context.compiled.statement if context.compiled else None
        if isinstance(statement, (Insert, Select)):
            _assert_actor_scoped(statement, a)
            assert parameters["actor_tenant_id"] == a.tenant_id
            observed.append(statement)

    event.listen(database._engine, "before_cursor_execute", inspect)
    try:
        first = ensure_personal_catalog(database, a)
        assert ensure_personal_catalog(database, a) == first
        assert len(observed) == 8
    finally:
        event.remove(database._engine, "before_cursor_execute", inspect)
    second = ensure_personal_catalog(database, b)
    assert first != second
    with psycopg.connect(inspector) as connection:
        rows = connection.execute(
            "SELECT c.id,c.tenant_id,g.grantee_tenant_id,g.role,c.version,g.version "
            "FROM catalog.catalog c JOIN catalog.catalog_grant g "
            "ON g.tenant_id=c.tenant_id AND g.catalog_id=c.id "
            "WHERE c.tenant_id IN (%s,%s) ORDER BY c.id",
            (a.tenant_id, b.tenant_id),
        ).fetchall()
        assert sorted(rows) == sorted(
            [
                (first, a.tenant_id, a.tenant_id, "owner", 1, 1),
                (second, b.tenant_id, b.tenant_id, "owner", 1, 1),
            ]
        )
        assert connection.execute("SELECT count(*) FROM catalog.entry").fetchone() == (0,)
    # RLS independently protects an unscoped test-only query.
    with database.unit_of_work(a) as scope:
        assert scope._require_active().execute(
            select(provisioning._catalog.c.id)
        ).scalars().all() == [first]


@pytest.mark.postgres
def test_grant_failure_rolls_back_catalog(catalog_database) -> None:
    database, inspector = catalog_database
    actor = _issue_actor(uuid4(), uuid4())
    control = _issue_actor(uuid4(), uuid4())
    control_id = ensure_personal_catalog(database, control)

    def fail_grant(connection, cursor, sql, parameters, context, many):
        statement = context.compiled.statement if context.compiled else None
        if isinstance(statement, Insert) and statement.table.name == "catalog_grant":
            raise RuntimeError("synthetic grant failure")

    event.listen(database._engine, "before_cursor_execute", fail_grant)
    try:
        with pytest.raises(RuntimeError, match="synthetic grant failure"):
            ensure_personal_catalog(database, actor)
    finally:
        event.remove(database._engine, "before_cursor_execute", fail_grant)
    with psycopg.connect(inspector) as connection:
        assert connection.execute(
            "SELECT id FROM catalog.catalog WHERE tenant_id=%s", (control.tenant_id,)
        ).fetchone() == (control_id,)
        for table in ["catalog", "catalog_grant"]:
            assert connection.execute(
                f"SELECT count(*) FROM catalog.{table} WHERE tenant_id=%s", (actor.tenant_id,)
            ).fetchone() == (0,)
    assert isinstance(ensure_personal_catalog(database, actor), UUID)


@pytest.mark.postgres
def test_concurrent_logins_converge_to_single_pair(catalog_database) -> None:
    database, inspector = catalog_database
    actor = _issue_actor(uuid4(), uuid4())
    barrier = Barrier(4, timeout=10)

    def synchronize(connection, cursor, sql, parameters, context, many):
        statement = context.compiled.statement if context.compiled else None
        if isinstance(statement, Insert) and statement.table.name == "catalog":
            barrier.wait()

    event.listen(database._engine, "before_cursor_execute", synchronize)
    try:
        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(
                executor.map(lambda _: ensure_personal_catalog(database, actor), range(4))
            )
    finally:
        event.remove(database._engine, "before_cursor_execute", synchronize)
    assert len(set(results)) == 1
    with psycopg.connect(inspector) as connection:
        for table in ["catalog", "catalog_grant"]:
            assert connection.execute(
                f"SELECT count(*) FROM catalog.{table} WHERE tenant_id=%s", (actor.tenant_id,)
            ).fetchone() == (1,)
