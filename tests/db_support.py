"""Synthetic database administration only; never imported by the application."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from you_story.migrations.runner import migrate


def urls() -> tuple[str, str, str]:
    if os.environ.get("TEST_DATABASE_CONFIRM") != "disposable":
        raise RuntimeError(
            "TEST_DATABASE_CONFIRM=disposable required for destructive PostgreSQL suite"
        )
    admin = os.environ.get("TEST_ADMIN_URL")
    if not admin:
        raise RuntimeError("TEST_ADMIN_URL required; no database fallback/skip")
    values = conninfo_to_dict(admin)
    if values.get("dbname") != "you_story_issue9_test":
        raise RuntimeError("only dedicated you_story_issue9_test database is permitted")
    owner = make_conninfo(**(values | {"user": "app_owner", "password": "owner-fixture"}))
    runtime = make_conninfo(**(values | {"user": "app_runtime", "password": "runtime-fixture"}))
    return admin, owner, runtime


def initialize(target: str = "004_media") -> tuple[str, str, str]:
    admin, owner, runtime = urls()
    with psycopg.connect(admin, autocommit=True) as connection:
        marker = connection.execute(
            "SELECT pg_catalog.shobj_description(oid, 'pg_database') "
            "FROM pg_catalog.pg_database WHERE datname=current_database()"
        ).fetchone()
        if marker != ("codex-issue9-disposable-fixture-2026-10-22",):
            raise RuntimeError("dedicated test database marker missing")
        for role, password, attributes in [
            ("app_owner", "owner-fixture", ""),
            ("app_runtime", "runtime-fixture", "NOINHERIT"),
        ]:
            if not connection.execute(
                "SELECT 1 FROM pg_roles WHERE rolname=%s", (role,)
            ).fetchone():
                connection.execute(
                    f"CREATE ROLE {role} LOGIN PASSWORD '{password}' NOSUPERUSER NOCREATEDB "
                    f"NOCREATEROLE NOREPLICATION NOBYPASSRLS {attributes}"
                )
        database = connection.info.dbname
        from psycopg import sql

        for statement in [
            sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(sql.Identifier(database)),
            sql.SQL("REVOKE CREATE,TEMP ON DATABASE {} FROM app_runtime").format(
                sql.Identifier(database)
            ),
            sql.SQL("GRANT CONNECT ON DATABASE {} TO app_owner,app_runtime").format(
                sql.Identifier(database)
            ),
            sql.SQL("GRANT CREATE ON DATABASE {} TO app_owner").format(sql.Identifier(database)),
        ]:
            connection.execute(statement)
        connection.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
    reset_schemas()
    migrate(owner, target)
    return admin, owner, runtime


@contextmanager
def runtime_connection(tenant: str | None = None) -> Iterator[psycopg.Connection[Any]]:
    with psycopg.connect(urls()[2]) as connection:
        if tenant is not None:
            connection.execute("SELECT set_config('app.tenant_id', %s, true)", (tenant,))
        yield connection


def reset_schemas() -> None:
    admin = urls()[0]
    from psycopg import sql

    with psycopg.connect(admin, autocommit=True) as connection:
        marker = connection.execute(
            "SELECT pg_catalog.shobj_description(oid, 'pg_database') "
            "FROM pg_catalog.pg_database WHERE datname=current_database()"
        ).fetchone()
        if marker != ("codex-issue9-disposable-fixture-2026-10-22",):
            raise RuntimeError("dedicated test database marker missing")
        for schema in ["media", "practice", "catalog", "identity", "foundation"]:
            connection.execute(
                sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema))
            )


def catalog_fingerprint(connection):
    """Stable complete then-present DDL oracle, without OIDs or user data."""
    queries = {
        ("tables"): (
            "SELECT n.nspname,c.relname,r.rolname,c.relrowsecurity,c.relforce"
            "rowsecurity,c.relacl::text\n            FROM pg_class c JOIN pg_n"
            "amespace n ON n.oid=c.relnamespace JOIN pg_roles r ON r.oid=c.re"
            "lowner\n            WHERE n.nspname IN ('identity','catalog','pra"
            "ctice','media','foundation') AND c.relkind='r'\n            ORDER"
            " BY 1,2"
        ),
        ("columns"): (
            "SELECT n.nspname,c.relname,a.attname,pg_catalog.format_type(a.at"
            "ttypid,a.atttypmod),a.attnotnull,pg_get_expr(d.adbin,d.adrelid)\n"
            "            FROM pg_attribute a JOIN pg_class c ON c.oid=a.attre"
            "lid JOIN pg_namespace n ON n.oid=c.relnamespace\n            LEFT"
            " JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum\n"
            "            WHERE n.nspname IN ('identity','catalog','practice',"
            "'media','foundation') AND c.relkind='r' AND a.attnum>0 AND NOT a"
            ".attisdropped ORDER BY 1,2,a.attnum"
        ),
        "constraints": (
            "SELECT n.nspname,c.relname,k.conname,k.contype,pg_get_constraint"
            "def(k.oid)\n            FROM pg_constraint k JOIN pg_class c ON c"
            ".oid=k.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace\n    "
            "        WHERE n.nspname IN ('identity','catalog','practice','med"
            "ia','foundation') ORDER BY 1,2,3"
        ),
        ("indexes"): (
            "SELECT schemaname,tablename,indexname,indexdef FROM pg_indexes W"
            "HERE schemaname IN ('identity','catalog','practice','media','fou"
            "ndation') ORDER BY 1,2,3"
        ),
        ("triggers"): (
            "SELECT n.nspname,c.relname,t.tgname,pg_get_triggerdef(t.oid) FRO"
            "M pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namesp"
            "ace n ON n.oid=c.relnamespace WHERE n.nspname IN ('identity','ca"
            "talog','practice','media','foundation') AND NOT t.tgisinternal O"
            "RDER BY 1,2,3"
        ),
        ("policies"): (
            "SELECT schemaname,tablename,policyname,permissive,roles,cmd,qual"
            ",with_check FROM pg_policies WHERE schemaname IN ('identity','ca"
            "talog','practice','media','foundation') ORDER BY 1,2,3"
        ),
        ("functions"): (
            "SELECT n.nspname,p.proname,pg_get_function_identity_arguments(p."
            "oid),pg_get_function_result(p.oid),r.rolname,p.prosecdef,p.provo"
            "latile,p.proconfig,p.proacl::text,p.prosrc FROM pg_proc p JOIN p"
            "g_namespace n ON n.oid=p.pronamespace JOIN pg_roles r ON r.oid=p"
            ".proowner WHERE n.nspname IN ('identity','catalog','practice','m"
            "edia','foundation') ORDER BY 1,2,3"
        ),
    }
    import json

    return json.loads(
        json.dumps({key: connection.execute(query).fetchall() for key, query in queries.items()})
    )
