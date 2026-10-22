"""Test-only simple probe oracle; not the deferred production query-shape registry."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import Column, MetaData, Table, Uuid, bindparam, select
from sqlalchemy.sql import operators
from sqlalchemy.sql.elements import BinaryExpression, BooleanClauseList

from tests.test_runtime_postgres import synthetic_actor

metadata = MetaData()
catalog = Table(
    "catalog", metadata, Column("tenant_id", Uuid), Column("id", Uuid), schema="catalog"
)
grant = Table(
    "catalog_grant", metadata, Column("tenant_id", Uuid), Column("id", Uuid), schema="catalog"
)


def assert_scoped(statement, actor_bind, actor) -> None:
    """Fail closed outside equality/AND probes, checking every private alias."""
    assert actor_bind.key == "actor_tenant_id"
    assert actor_bind.value is actor.tenant_id
    assert actor.provenance == "validated_identity"
    graph = {}

    def equalities(expression):
        if isinstance(expression, BooleanClauseList):
            assert expression.operator is operators.and_
            for clause in expression.clauses:
                equalities(clause)
        else:
            assert isinstance(expression, BinaryExpression)
            assert expression.operator is operators.eq
            left, right = expression.left, expression.right
            graph.setdefault(left, []).append(right)
            graph.setdefault(right, []).append(left)

    for criterion in statement._where_criteria:
        equalities(criterion)

    def reaches_actor(column):
        pending, visited = [column], set()
        while pending:
            item = pending.pop()
            if item is actor_bind:
                return True
            if id(item) not in visited:
                visited.add(id(item))
                pending.extend(graph.get(item, []))
        return False

    for relation in statement.get_final_froms():
        assert "tenant_id" in relation.c
        assert reaches_actor(relation.c.tenant_id), "Unanchored private relation"


def test_simple_scoped_probe_and_independent_mutations() -> None:
    actor = synthetic_actor()
    actor_bind = bindparam("actor_tenant_id", actor.tenant_id, type_=Uuid)
    other = catalog.alias("other")
    positive = select(catalog.c.id, other.c.id).where(
        catalog.c.tenant_id == actor_bind, other.c.tenant_id == catalog.c.tenant_id
    )
    assert_scoped(positive, actor_bind, actor)
    mutations = [
        select(catalog.c.id),
        select(catalog.c.id, other.c.id).where(catalog.c.tenant_id == actor_bind),
        select(catalog.c.id, other.c.id).where(other.c.tenant_id == catalog.c.tenant_id),
        select(catalog.c.id).where(catalog.c.id == actor_bind),
        select(catalog.c.id, other.c.id).where(
            (catalog.c.tenant_id == actor_bind) | (other.c.tenant_id == actor_bind)
        ),
    ]
    for mutation in mutations:
        with pytest.raises(AssertionError):
            assert_scoped(mutation, actor_bind, actor)
    request_bind = bindparam("actor_tenant_id", UUID(str(actor.tenant_id)), type_=Uuid)
    with pytest.raises(AssertionError):
        assert_scoped(
            select(catalog.c.id).where(catalog.c.tenant_id == request_bind), request_bind, actor
        )


@pytest.mark.postgres
def test_probe_bound_from_uow_actor_before_driver() -> None:
    from psycopg.conninfo import conninfo_to_dict
    from sqlalchemy import event, text
    from sqlalchemy.engine import URL

    from tests.db_support import initialize
    from you_story.shared.config import Settings
    from you_story.shared.database import Database

    runtime = conninfo_to_dict(initialize()[2])
    settings = Settings(
        database_url=URL.create(
            "postgresql+psycopg",
            username=runtime["user"],
            password=runtime["password"],
            host=runtime["host"],
            port=int(runtime["port"]),
            database=runtime["dbname"],
        ).render_as_string(hide_password=False)
    )
    database = Database(settings, pool_size=1)
    actor = synthetic_actor()
    actor_bind = bindparam("actor_tenant_id", actor.tenant_id, type_=Uuid)
    statement = select(catalog.c.id).where(catalog.c.tenant_id == actor_bind)
    observed = []

    def inspect(connection, cursor, sql, parameters, context, many):
        if context.compiled and context.compiled.statement is statement:
            assert_scoped(statement, actor_bind, actor)
            assert parameters["actor_tenant_id"] == actor.tenant_id
            observed.append(True)

    event.listen(database._engine, "before_cursor_execute", inspect)
    try:
        with database.unit_of_work(actor) as scope:
            identifier = uuid4()
            scope._connection.execute(
                text(
                    "INSERT INTO catalog.catalog(tenant_id,id,visibility) "
                    "VALUES (:tenant,:id,'personal')"
                ),
                {"tenant": actor.tenant_id, "id": identifier},
            )
            assert scope._connection.execute(statement).scalars().all() == [identifier]
        assert observed == [True]
    finally:
        database.close()
