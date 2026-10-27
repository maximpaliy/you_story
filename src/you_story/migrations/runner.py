"""Direct-owner, serialized, transactional schema-only runner."""

from __future__ import annotations

import psycopg

from you_story.migrations.manifest import (
    REVISION_PATHS,
    expected_revisions,
    migration_sql,
    validate_migration,
)


def migrate(dsn: str, target: str = "006_catalog") -> None:
    """Apply exact reviewed schema revisions without domain callbacks."""
    if target not in REVISION_PATHS:
        raise ValueError("unsupported migration target")
    with psycopg.connect(dsn, autocommit=True, connect_timeout=3) as connection:
        role = connection.execute("SELECT current_user, session_user").fetchone()
        if role != ("app_owner", "app_owner"):
            raise PermissionError("migration requires direct app_owner authentication")
        connection.execute("SELECT pg_catalog.pg_advisory_lock(91267309)")
        try:
            present = connection.execute(
                "SELECT pg_catalog.to_regclass('foundation.schema_revision')"
            ).fetchone()
            applied: dict[str, str] = (
                dict(
                    connection.execute(
                        "SELECT version, checksum FROM foundation.schema_revision"
                    ).fetchall()
                )
                if present and present[0]
                else {}
            )
            expected = expected_revisions()
            if any(key not in expected or expected[key] != value for key, value in applied.items()):
                raise ValueError("migration ledger mismatch")
            prefix = list(REVISION_PATHS)[: len(applied)]
            if set(applied) != set(prefix):
                raise ValueError("migration ledger is not a supported prefix")
            for version in REVISION_PATHS:
                if version not in applied:
                    sql = migration_sql(version)
                    validate_migration(version, sql)
                    with connection.transaction():
                        connection.execute(sql)
                        connection.execute(
                            (
                                "INSERT INTO foundation.schema_revision(version, checksum) VALUES"
                                " (%s,%s)"
                            ),
                            (version, expected[version]),
                        )
                if version == target:
                    break
        finally:
            connection.execute("SELECT pg_catalog.pg_advisory_unlock(91267309)")
