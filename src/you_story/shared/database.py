"""Runtime-only connection lifecycle. No domain SQL or public execution handle."""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import DisconnectionError
from sqlalchemy.pool import QueuePool

from you_story.migrations.manifest import expected_revisions
from you_story.shared.config import Settings
from you_story.shared.context import ActorContext, correlation_id

_log = logging.getLogger("you_story.context")


def _signal(category: str, operation: str) -> None:
    _log.warning(
        "database_context_event",
        extra={
            "category": category,
            "operation": operation,
            "role": "app_runtime",
            "correlation_id": correlation_id.get(),
        },
    )


class ContextFailure(RuntimeError):
    def __init__(self, category: str) -> None:
        self.category = category
        super().__init__("Database context unavailable")


def _reset_connection(connection: Any) -> None:
    connection.rollback()
    previous = connection.autocommit
    try:
        connection.autocommit = True
        with connection.cursor() as cursor:
            cursor.execute("RESET app.tenant_id")
    finally:
        connection.autocommit = previous


@dataclass
class UnitOfWork:
    """Opaque transaction scope. Only future reviewed infrastructure may use internals."""

    _actor: ActorContext
    _connection: Connection
    _active: bool = True
    _rollback_only: bool = False

    def _require_active(self) -> Connection:
        if not self._active or not self._connection.in_transaction():
            raise ContextFailure("closed")
        return self._connection


class Database:
    def __init__(self, settings: Settings, *, pool_size: int = 5) -> None:
        self._engine: Engine = create_engine(
            settings.database_url.get_secret_value(),
            poolclass=QueuePool,
            pool_size=pool_size,
            max_overflow=0,
            pool_timeout=2,
            pool_reset_on_return=None,
            connect_args={"connect_timeout": 2, "options": "-c statement_timeout=2000"},
            hide_parameters=True,
        )
        self._current: ContextVar[UnitOfWork | None] = ContextVar(
            f"unit_of_work_{id(self)}", default=None
        )
        event.listen(self._engine, "checkout", self._checkout)
        event.listen(self._engine, "reset", self._reset)

    @staticmethod
    def _checkout(dbapi_connection: Any, record: Any, proxy: Any) -> None:
        try:
            _reset_connection(dbapi_connection)
        except Exception:
            record.invalidate()
            _signal("cleanup", "checkout_retire")
            raise DisconnectionError("Connection reset failed") from None

    @staticmethod
    def _reset(dbapi_connection: Any, record: Any, state: Any) -> None:
        if state.terminate_only:
            return
        try:
            _reset_connection(dbapi_connection)
        except Exception:
            record.invalidate()
            _signal("cleanup", "checkin_retire")

    def ready(self) -> bool:
        """Bounded non-tenant role and schema checks; errors remain private."""
        try:
            with self._engine.connect() as connection:
                role = connection.execute(
                    text(
                        "SELECT current_user = 'app_runtime' AND NOT rolsuper "
                        "AND NOT rolcreatedb AND NOT rolcreaterole AND NOT rolreplication "
                        "AND NOT rolbypassrls AND NOT rolinherit "
                        "AND NOT pg_catalog.pg_has_role(current_user, 'app_owner', 'MEMBER') "
                        "FROM pg_catalog.pg_roles WHERE rolname = current_user"
                    )
                ).scalar_one()
                if role is not True:
                    return False
                privileges = connection.execute(
                    text(
                        "SELECT NOT pg_catalog.has_database_privilege(current_user, "
                        "current_database(), 'CREATE,TEMP') "
                        "AND NOT pg_catalog.has_schema_privilege(current_user, 'public', 'CREATE') "
                        "AND NOT pg_catalog.has_schema_privilege(current_user, 'media', 'USAGE') "
                        "AND NOT EXISTS (SELECT 1 FROM (VALUES "
                        "('identity.user'),('identity.tenant'),('identity.external_identity'),"
                        "('identity.invitation'),('identity.login_session'),"
                        "('identity.login_transaction'),('identity.auth_rate_limit')) "
                        "AS control_plane(name) WHERE "
                        "pg_catalog.has_table_privilege(current_user, control_plane.name, "
                        "'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER') OR "
                        "pg_catalog.has_any_column_privilege(current_user, control_plane.name, "
                        "'SELECT,INSERT,UPDATE,REFERENCES'))"
                    )
                ).scalar_one()
                if privileges is not True:
                    return False
                revisions = connection.execute(
                    text("SELECT version, checksum FROM foundation.schema_revision")
                ).all()
                return dict(revisions) == expected_revisions()
        except Exception:
            _signal("unavailable", "readiness")
            return False

    @contextmanager
    def unit_of_work(self, actor: ActorContext) -> Iterator[UnitOfWork]:
        if not isinstance(actor, ActorContext):
            category = "missing" if actor is None else "invalid"
            _signal(category, "setup")
            raise ContextFailure(category)
        try:
            tenant = str(actor.tenant_id)
            if (
                actor.provenance != "validated_identity"
                or not isinstance(actor.tenant_id, UUID)
                or not isinstance(actor.actor_id, UUID)
            ):
                raise ValueError
        except (AttributeError, ValueError):
            _signal("invalid", "setup")
            raise ContextFailure("invalid") from None
        nested = self._current.get()
        if nested is not None:
            if actor != nested._actor:
                _signal("mismatch", "nested")
                raise ContextFailure("mismatch")
            nested._require_active()
            try:
                yield nested
            except BaseException:
                nested._rollback_only = True
                raise
            return
        with self._engine.connect() as connection:
            transaction = connection.begin()
            scope = UnitOfWork(actor, connection)
            token = self._current.set(scope)
            try:
                connection.execute(
                    text("SELECT pg_catalog.set_config('app.tenant_id', :tenant, true)"),
                    {"tenant": tenant},
                )
                actual = connection.execute(
                    text("SELECT identity.current_tenant_id()")
                ).scalar_one()
                if actual != actor.tenant_id:
                    _signal("mismatch", "setup")
                    raise ContextFailure("mismatch")
                yield scope
                if scope._rollback_only:
                    transaction.rollback()
                    raise ContextFailure("rollback_only")
                transaction.commit()
            except BaseException:
                if transaction.is_active:
                    transaction.rollback()
                raise
            finally:
                scope._active = False
                self._current.reset(token)

    def close(self) -> None:
        self._engine.dispose()
