"""Synthetic auth database probes. Never imported by production identity code."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from hashlib import sha256
from threading import Event
from time import monotonic
from typing import Any
from uuid import UUID, uuid4

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from tests.db_support import initialize

ISSUER = "https://accounts.google.com"
CONFIG = "google-web"
WRAPPERS = frozenset(
    {
        "start_web_login",
        "claim_web_login",
        "fail_web_login",
        "finish_web_login",
        "resolve_web_session",
        "revoke_web_session",
        "consume_auth_limit",
        "mark_catalog_ready",
    }
)


def digest(label: str | None = None) -> bytes:
    return sha256((label or str(uuid4())).encode("ascii")).digest()


@dataclass
class Login:
    id: UUID = field(default_factory=uuid4)
    binder: bytes = field(default_factory=digest)
    state: bytes = field(default_factory=digest)
    nonce: bytes = field(default_factory=digest)
    challenge: str = "A" * 43
    ciphertext: bytes = b"synthetic-authenticated-encryption-envelope"
    config: str = CONFIG
    invitation: bytes | None = None
    destination: str = "home"
    expires_at: datetime | None = None


@dataclass
class Issued:
    login: Login
    subject: str
    session_id: UUID
    token_digest: bytes
    csrf_digest: bytes
    result: dict[str, Any]


@dataclass
class AuthDatabase:
    admin_url: str
    owner_url: str
    runtime_url: str

    @classmethod
    def create(cls) -> AuthDatabase:
        return cls(*initialize("005_identity"))

    @contextmanager
    def admin(self) -> Iterator[psycopg.Connection[dict[str, Any]]]:
        with psycopg.connect(self.admin_url, row_factory=dict_row) as connection:
            yield connection

    def raw_call(
        self,
        function: str,
        *arguments: Any,
        session_timezone: str | None = None,
    ) -> list[dict[str, Any]]:
        assert function in WRAPPERS, "test helper permits only reviewed fixed wrappers"
        placeholders = sql.SQL(",").join(sql.Placeholder() for _ in arguments)
        statement = sql.SQL("SELECT * FROM identity.{}({})").format(
            sql.Identifier(function), placeholders
        )
        with psycopg.connect(self.runtime_url, row_factory=dict_row) as connection:
            if session_timezone is not None:
                connection.execute("SELECT set_config('TimeZone',%s,true)", (session_timezone,))
            return connection.execute(statement, arguments).fetchall()

    def call(self, function: str, *arguments: Any) -> list[dict[str, Any]]:
        return self.normalize(function, self.raw_call(function, *arguments))

    @staticmethod
    def normalize(function: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if function not in {"start_web_login", "finish_web_login"}:
            return rows
        assert len(rows) == 1, "start/finish must expose one fixed discriminated result"
        row = dict(rows[0])
        result = row.pop("result")
        if function == "start_web_login":
            assert set(row) == {"id", "expires_at"}
            assert result in {"ok", "invalid", "in_progress", "unavailable"}
        else:
            assert set(row) == {
                "user_id",
                "tenant_id",
                "session_id",
                "provisioning_state",
                "absolute_expires_at",
                "window_end",
            }
            assert result in {"ok", "invalid", "limited", "unavailable"}
            end = row.pop("window_end")
            assert (end is not None) == (result == "limited")
        if result != "ok":
            assert all(value is None for value in row.values()), "failure disclosed authority"
            return []
        assert all(value is not None for value in row.values())
        return [row]

    def race(
        self,
        function: str,
        arguments: list[tuple[Any, ...]],
        *,
        after_wait: Callable[[], None] | None = None,
    ) -> list[list[dict[str, Any]]]:
        return self.race_calls([(function, args) for args in arguments], after_wait=after_wait)

    def race_calls(
        self,
        calls: list[tuple[str, tuple[Any, ...]]],
        *,
        after_wait: Callable[[], None] | None = None,
    ) -> list[list[dict[str, Any]]]:
        """Observe every independent runtime caller blocked on the actual auth lock."""
        pids: list[int] = []
        assert all(function in WRAPPERS for function, _ in calls)

        def invoke(call: tuple[str, tuple[Any, ...]]) -> list[dict[str, Any]]:
            function, args = call
            with psycopg.connect(self.runtime_url, row_factory=dict_row) as connection:
                pids.append(connection.execute("SELECT pg_backend_pid() AS pid").fetchone()["pid"])
                placeholders = sql.SQL(",").join(sql.Placeholder() for _ in args)
                return connection.execute(
                    sql.SQL("SELECT * FROM identity.{}({})").format(
                        sql.Identifier(function), placeholders
                    ),
                    args,
                ).fetchall()

        with self.admin() as holder, ThreadPoolExecutor(max_workers=len(calls)) as pool:
            holder.execute("SELECT identity._auth_lock()")
            futures = [pool.submit(invoke, call) for call in calls]
            try:
                deadline = monotonic() + 10
                while monotonic() < deadline:
                    waiting = holder.execute(
                        "SELECT count(*) AS n FROM pg_locks WHERE locktype='advisory' "
                        "AND NOT granted AND pid=ANY(%s)",
                        (pids,),
                    ).fetchone()["n"]
                    if len(pids) == len(calls) and waiting == len(calls):
                        break
                    Event().wait(0.005)
                else:
                    raise AssertionError("independent callers did not all reach the auth lock")
                if after_wait is not None:
                    after_wait()
            finally:
                holder.commit()  # Release before executor exit, even on a failed observation.
            return [future.result() for future in futures]

    def row_wait(
        self,
        function: str,
        arguments: tuple[Any, ...],
        table: str,
        row_id: UUID,
        after_wait: Callable[[], None] | None = None,
        *,
        real_expiry_column: str | None = None,
    ) -> list[dict[str, Any]]:
        """Hold a real row lock and prove the runtime backend waits behind it."""
        pids: list[int] = []

        def invoke() -> list[dict[str, Any]]:
            with psycopg.connect(self.runtime_url, row_factory=dict_row) as connection:
                pids.append(connection.execute("SELECT pg_backend_pid() AS pid").fetchone()["pid"])
                return connection.execute(
                    sql.SQL("SELECT * FROM identity.{}({})").format(
                        sql.Identifier(function),
                        sql.SQL(",").join(sql.Placeholder() for _ in arguments),
                    ),
                    arguments,
                ).fetchall()

        with self.admin() as holder, ThreadPoolExecutor(max_workers=1) as pool:
            holder_pid = holder.execute("SELECT pg_backend_pid() AS pid").fetchone()["pid"]
            holder.execute(
                sql.SQL("SELECT id FROM identity.{} WHERE id=%s FOR UPDATE").format(
                    sql.Identifier(table)
                ),
                (row_id,),
            )
            expiry = None
            if real_expiry_column is not None:
                expiry = holder.execute(
                    sql.SQL(
                        "UPDATE identity.{} SET {}=clock_timestamp()+interval '300 milliseconds' "
                        "WHERE id=%s RETURNING {} AS expiry"
                    ).format(
                        sql.Identifier(table),
                        sql.Identifier(real_expiry_column),
                        sql.Identifier(real_expiry_column),
                    ),
                    (row_id,),
                ).fetchone()["expiry"]
            future = pool.submit(invoke)
            try:
                deadline = monotonic() + 10
                while monotonic() < deadline:
                    if pids:
                        blockers = holder.execute(
                            "SELECT pg_blocking_pids(%s) AS pids", (pids[0],)
                        ).fetchone()["pids"]
                        if holder_pid in blockers:
                            break
                    Event().wait(0.005)
                else:
                    raise AssertionError("runtime caller did not wait on the held target row")
                if expiry is not None:
                    while monotonic() < deadline:
                        if holder.execute(
                            "SELECT clock_timestamp()>=%s AS expired", (expiry,)
                        ).fetchone()["expired"]:
                            break
                        Event().wait(0.005)
                    else:
                        raise AssertionError("database clock did not pass the held expiry")
                if after_wait is not None:
                    after_wait()
            finally:
                holder.commit()
            return future.result()

    def ordered_calls(
        self,
        first_function: str,
        first_arguments: tuple[Any, ...],
        second_function: str,
        second_arguments: tuple[Any, ...],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Hold the first wrapper transaction and observe the second blocked behind it."""
        pids: list[int] = []

        def statement(function: str, arguments: tuple[Any, ...]):
            assert function in WRAPPERS
            return sql.SQL("SELECT * FROM identity.{}({})").format(
                sql.Identifier(function), sql.SQL(",").join(sql.Placeholder() for _ in arguments)
            )

        def invoke():
            with psycopg.connect(self.runtime_url, row_factory=dict_row) as connection:
                pids.append(connection.execute("SELECT pg_backend_pid() AS pid").fetchone()["pid"])
                return connection.execute(
                    statement(second_function, second_arguments), second_arguments
                ).fetchall()

        with (
            psycopg.connect(self.runtime_url, row_factory=dict_row) as first,
            self.admin() as observer,
            ThreadPoolExecutor(max_workers=1) as pool,
        ):
            first_pid = first.execute("SELECT pg_backend_pid() AS pid").fetchone()["pid"]
            first_result = first.execute(
                statement(first_function, first_arguments), first_arguments
            ).fetchall()
            future = pool.submit(invoke)
            try:
                deadline = monotonic() + 10
                while monotonic() < deadline:
                    if (
                        pids
                        and first_pid
                        in observer.execute(
                            "SELECT pg_blocking_pids(%s) AS pids", (pids[0],)
                        ).fetchone()["pids"]
                    ):
                        break
                    Event().wait(0.005)
                else:
                    raise AssertionError("second wrapper did not wait behind first transaction")
            finally:
                first.commit()
            return first_result, future.result()

    def scalar(self, function: str, *arguments: Any) -> Any:
        rows = self.call(function, *arguments)
        assert len(rows) == 1 and len(rows[0]) == 1
        return next(iter(rows[0].values()))

    def invitation(self, *, issuer: str = ISSUER, expired: bool = False) -> bytes:
        value = digest()
        with self.admin() as connection:
            connection.execute(
                "INSERT INTO identity.invitation(id,token_digest,issuer,expires_at) "
                "VALUES (%s,%s,%s,clock_timestamp()+%s::interval)",
                (uuid4(), value, issuer, "-1 second" if expired else "24 hours"),
            )
        return value

    def start(self, login: Login | None = None) -> Login:
        login = login or Login()
        if login.expires_at is None:
            with self.admin() as connection:
                login.expires_at = connection.execute(
                    "SELECT clock_timestamp()+interval '599 seconds' AS deadline"
                ).fetchone()["deadline"]
        rows = self.call(
            "start_web_login",
            login.id,
            login.binder,
            login.state,
            login.nonce,
            login.challenge,
            login.ciphertext,
            login.config,
            login.invitation,
            login.destination,
            login.expires_at,
        )
        assert len(rows) == 1 and rows[0]["id"] == login.id
        assert rows[0]["expires_at"] <= login.expires_at
        return login

    def claim(self, login: Login) -> list[dict[str, Any]]:
        return self.call("claim_web_login", login.state, login.binder, login.config)

    def finish(
        self,
        login: Login,
        subject: str,
        *,
        session_id: UUID | None = None,
        token_digest: bytes | None = None,
        csrf_digest: bytes | None = None,
        issuer: str = ISSUER,
    ) -> tuple[UUID, bytes, bytes, list[dict[str, Any]]]:
        session_id = session_id or uuid4()
        token_digest = token_digest or digest()
        csrf_digest = csrf_digest or digest()
        rows = self.call(
            "finish_web_login",
            login.id,
            login.binder,
            issuer,
            subject,
            session_id,
            token_digest,
            csrf_digest,
        )
        return session_id, token_digest, csrf_digest, rows

    def issue(self, *, subject: str | None = None, invitation: bytes | None = None) -> Issued:
        subject = subject or f"synthetic-subject-{uuid4()}"
        invitation = invitation or self.invitation()
        login = self.start(Login(invitation=invitation))
        assert len(self.claim(login)) == 1
        session_id, token_digest, csrf_digest, rows = self.finish(login, subject)
        assert len(rows) == 1
        return Issued(login, subject, session_id, token_digest, csrf_digest, rows[0])

    def allowlist(self, subject: str, *, expired: bool = False) -> bytes:
        value = digest()
        with self.admin() as connection:
            connection.execute(
                "INSERT INTO identity.invitation(id,token_digest,issuer,expires_at,"
                "admission_kind,permitted_subject) "
                "VALUES (%s,%s,%s,clock_timestamp()+%s::interval,'allowlist',%s)",
                (uuid4(), value, ISSUER, "-1 second" if expired else "24 hours", subject),
            )
        return value

    @contextmanager
    def clock(self, instant: datetime) -> Iterator[None]:
        with self.admin() as connection:
            definition = connection.execute(
                "SELECT pg_get_functiondef('identity._auth_now()'::regprocedure) AS definition"
            ).fetchone()["definition"]
        try:
            self.set_clock(instant)
            yield
        finally:
            with self.admin() as connection:
                connection.execute(definition)
                restored = connection.execute(
                    "SELECT pg_get_functiondef('identity._auth_now()'::regprocedure) AS definition"
                ).fetchone()["definition"]
                assert restored == definition

    def set_clock(self, instant: datetime) -> None:
        body = sql.SQL("SELECT {}::timestamptz").format(sql.Literal(instant)).as_string()
        with self.admin() as connection:
            connection.execute(
                sql.SQL(
                    "CREATE OR REPLACE FUNCTION identity._auth_now() RETURNS timestamptz "
                    "LANGUAGE sql VOLATILE SET search_path=pg_catalog,identity AS {}"
                ).format(sql.Literal(body))
            )

    @contextmanager
    def mutate_function(
        self,
        function: str,
        replacements: list[tuple[str, str]],
    ) -> Iterator[None]:
        """Fixture-only database guard mutation with exact body restoration."""
        with self.admin() as connection:
            original = connection.execute(
                "SELECT pg_get_functiondef(%s::regproc) AS definition",
                ("identity." + function,),
            ).fetchone()["definition"]
        mutated = original
        for before, after in replacements:
            assert before in mutated, "mutation no longer addresses an actual guard"
            mutated = mutated.replace(before, after)
        assert mutated != original
        try:
            with self.admin() as connection:
                connection.execute(mutated)
            yield
        finally:
            with self.admin() as connection:
                connection.execute(original)
                restored = connection.execute(
                    "SELECT pg_get_functiondef(%s::regproc) AS definition",
                    ("identity." + function,),
                ).fetchone()["definition"]
                assert restored == original

    def counts(self) -> dict[str, int]:
        with self.admin() as connection:
            return {
                table: connection.execute(
                    sql.SQL("SELECT count(*) AS count FROM identity.{}").format(
                        sql.Identifier(table)
                    )
                ).fetchone()["count"]
                for table in ["user", "tenant", "external_identity", "login_session"]
            }
