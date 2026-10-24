from __future__ import annotations

import hashlib

import psycopg
import pytest

from tests.db_support import initialize
from you_story.migrations.manifest import (
    REVISION_PATHS,
    expected_revisions,
    migration_sql,
    validate_migration,
)
from you_story.migrations.runner import migrate

pytestmark = pytest.mark.postgres


def test_empty_upgrade_and_replay() -> None:
    admin, owner, _ = initialize("000_security")
    with psycopg.connect(admin) as connection:
        assert dict(
            connection.execute("SELECT version, checksum FROM foundation.schema_revision")
        ) == {"000_security": expected_revisions()["000_security"]}
    migrate(owner)
    migrate(owner)
    with psycopg.connect(admin) as connection:
        assert (
            dict(connection.execute("SELECT version, checksum FROM foundation.schema_revision"))
            == expected_revisions()
        )


@pytest.mark.parametrize("revision", list(REVISION_PATHS))
@pytest.mark.parametrize("phase", ["before", "after_ddl", "after_mark"])
def test_every_real_revision_is_atomic_and_retryable(
    revision: str, phase: str, monkeypatch
) -> None:
    admin, owner, _ = initialize()
    # Reset only fixture-owned application schemas; initialize supports empty baseline.
    from tests.db_support import reset_schemas

    reset_schemas()

    original = psycopg.Connection.execute
    ddl = migration_sql(revision)

    def interrupted_execute(connection, query, params=None, **kwargs):
        is_ddl = query == ddl
        is_mark = (
            isinstance(query, str)
            and query.startswith("INSERT INTO foundation.schema_revision")
            and params
            and params[0] == revision
        )
        if is_ddl and phase == "before":
            raise RuntimeError("synthetic interrupted schema migration")
        result = original(connection, query, params, **kwargs)
        if (is_ddl and phase == "after_ddl") or (is_mark and phase == "after_mark"):
            raise RuntimeError("synthetic interrupted schema migration")
        return result

    with monkeypatch.context() as patch:
        patch.setattr(psycopg.Connection, "execute", interrupted_execute)
        with pytest.raises(RuntimeError, match="synthetic interrupted"):
            migrate(owner)
    with psycopg.connect(admin) as connection:
        present = connection.execute("SELECT to_regclass('foundation.schema_revision')").fetchone()[
            0
        ]
        applied = (
            list(
                connection.execute(
                    "SELECT version FROM foundation.schema_revision ORDER BY version"
                )
            )
            if present
            else []
        )
        assert [row[0] for row in applied] == list(REVISION_PATHS)[
            : list(REVISION_PATHS).index(revision)
        ]
        if revision == "005_identity":
            import json
            from pathlib import Path

            from tests.db_support import catalog_fingerprint

            baseline = json.loads(
                (Path(__file__).parent / "fixtures/schema-catalog.json").read_text()
            )
            assert catalog_fingerprint(connection) == baseline
    migrate(owner)
    with psycopg.connect(admin) as connection:
        assert (
            dict(connection.execute("SELECT version, checksum FROM foundation.schema_revision"))
            == expected_revisions()
        )


def test_runtime_cannot_migrate_and_changed_ledger_fails() -> None:
    admin, owner, runtime = initialize()
    with pytest.raises(PermissionError):
        migrate(runtime)
    with psycopg.connect(admin) as connection:
        connection.execute(
            "UPDATE foundation.schema_revision SET checksum='changed' WHERE version='001_identity'"
        )
    with pytest.raises(ValueError, match="ledger mismatch"):
        migrate(owner)


@pytest.mark.parametrize("version", list(REVISION_PATHS))
def test_classified_ast_positive_and_mutations(version: str) -> None:
    source = migration_sql(version)
    owner = version.split("_", 1)[1]
    validate_migration(owner, source + "\n-- formatting comment only\n")
    assert expected_revisions()[version] == hashlib.sha256(source.encode()).hexdigest()
    for statement in [
        "CREATE TABLE foreign_schema.x(id uuid);",
        "UPDATE catalog.catalog SET tenant_id = gen_random_uuid();",
        "ALTER TABLE catalog.catalog DISABLE ROW LEVEL SECURITY;",
        "GRANT app_owner TO app_runtime;",
        "CREATE FUNCTION identity.all_tenants() RETURNS int LANGUAGE SQL AS 'SELECT 1';",
    ]:
        with pytest.raises(ValueError, match="unreviewed"):
            validate_migration(owner, source + statement)


def test_changed_packaged_migration_is_rejected(monkeypatch) -> None:
    import you_story.migrations.manifest as manifest

    original = manifest.migration_sql
    monkeypatch.setattr(
        manifest,
        "migration_sql",
        lambda version: original(version) + "CREATE TABLE catalog.bad(id uuid);",
    )
    with pytest.raises(ValueError, match="packaged migration checksum"):
        manifest.validate_migration("catalog", original("002_catalog"))


def test_populated_004_upgrade_preserves_legacy_session_and_original_artifacts() -> None:
    import json
    from pathlib import Path
    from uuid import uuid4

    from tests.db_support import catalog_fingerprint

    admin, owner, runtime = initialize("004_media")
    user_id, tenant_id, identity_id, session_id = (uuid4() for _ in range(4))
    token = b"L" * 32
    invitation_id = uuid4()
    with psycopg.connect(admin) as connection:
        baseline = json.loads((Path(__file__).parent / "fixtures/schema-catalog.json").read_text())
        assert catalog_fingerprint(connection) == baseline
        connection.execute(
            "INSERT INTO identity.\"user\"(id,state) VALUES(%s,'active')", (user_id,)
        )
        connection.execute(
            "INSERT INTO identity.tenant(id,owner_user_id,state,provisioning_state) "
            "VALUES(%s,%s,'active','catalog_pending')",
            (tenant_id, user_id),
        )
        connection.execute(
            "INSERT INTO identity.external_identity(id,provider,subject,user_id,state) "
            "VALUES(%s,'https://accounts.google.com','legacy-subject',%s,'active')",
            (identity_id, user_id),
        )
        connection.execute(
            "INSERT INTO identity.login_session(id,token_digest,user_id,tenant_id,issued_at,"
            "last_seen_at,absolute_expires_at) VALUES(%s,%s,%s,%s,clock_timestamp(),"
            "clock_timestamp(),clock_timestamp()+interval '30 days')",
            (session_id, token, user_id, tenant_id),
        )
        connection.execute(
            "INSERT INTO identity.invitation(id,token_digest,issuer,expires_at) "
            "VALUES(%s,%s,'https://accounts.google.com',clock_timestamp()+interval '24 hours')",
            (invitation_id, b"I" * 32),
        )
        before = connection.execute(
            "SELECT to_jsonb(s) FROM identity.login_session s WHERE id=%s", (session_id,)
        ).fetchone()[0]
        prior_control = {
            table: connection.execute(f'SELECT to_jsonb(r) FROM identity."{table}" r').fetchall()
            for table in ["user", "tenant", "external_identity", "invitation"]
        }
    migrate(owner)
    with psycopg.connect(admin) as connection:
        after = connection.execute(
            "SELECT to_jsonb(s)-'external_identity_id'-'csrf_digest',"
            "external_identity_id,csrf_digest FROM identity.login_session s WHERE id=%s",
            (session_id,),
        ).fetchone()
        assert after == (before, None, None)
        for table, rows in prior_control.items():
            document = (
                "to_jsonb(r)-'admission_kind'-'permitted_subject'"
                if table == "invitation"
                else "to_jsonb(r)"
            )
            assert (
                connection.execute(f'SELECT {document} FROM identity."{table}" r').fetchall()
                == rows
            )
        assert connection.execute(
            "SELECT admission_kind,permitted_subject FROM identity.invitation WHERE id=%s",
            (invitation_id,),
        ).fetchone() == (None, None)
    with psycopg.connect(runtime) as connection:
        assert (
            connection.execute(
                "SELECT * FROM identity.resolve_web_session(%s)", (token,)
            ).fetchall()
            == []
        )
    with psycopg.connect(admin) as connection:
        assert (
            connection.execute(
                "SELECT to_jsonb(s)-'external_identity_id'-'csrf_digest' "
                "FROM identity.login_session s WHERE id=%s",
                (session_id,),
            ).fetchone()[0]
            == before
        )
