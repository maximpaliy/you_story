from __future__ import annotations

import json
from importlib.resources import files
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.types.json import Jsonb

from tests.db_support import initialize

pytestmark = pytest.mark.postgres
MANIFEST = json.loads(files("you_story").joinpath("migrations/schema_manifest.json").read_text())


@pytest.fixture
def db():
    return initialize()


def test_exact_catalog_roles_grants_and_policies(db) -> None:
    admin, _, runtime = db
    expected = (
        set(MANIFEST["private"])
        | set(MANIFEST["control"])
        | set(MANIFEST["global"])
        | set(MANIFEST["technical"])
    )
    with psycopg.connect(admin) as connection:
        rows = connection.execute(
            "\n            SELECT n.nspname||'.'||c.relname, r.rolname, c.relr"
            "owsecurity,c.relforcerowsecurity\n            FROM pg_class c JOI"
            "N pg_namespace n ON n.oid=c.relnamespace\n            JOIN pg_rol"
            "es r ON r.oid=c.relowner\n            WHERE n.nspname IN ('identi"
            "ty','catalog','practice','media','foundation') AND c.relkind='r'"
            "\n        "
        ).fetchall()
        assert {row[0] for row in rows} == expected
        assert all(row[1] == "app_owner" for row in rows)
        for name, _, rls, forced in rows:
            assert (rls, forced) == (
                (True, True) if name in MANIFEST["private"] else (False, False)
            )
        for table in MANIFEST["private"]:
            schema, name = table.split(".")
            column = connection.execute(
                (
                    "SELECT is_nullable,data_type FROM information_schema.columns WHE"
                    "RE table_schema=%s AND table_name=%s AND column_name='tenant_id'"
                ),
                (schema, name),
            ).fetchone()
            assert column == ("NO", "uuid")
            policies = connection.execute(
                (
                    "SELECT roles,cmd,qual,with_check FROM pg_policies WHERE schemana"
                    "me=%s AND tablename=%s"
                ),
                (schema, name),
            ).fetchall()
            assert policies == [
                (
                    ["app_runtime"],
                    "ALL",
                    "(tenant_id = identity.current_tenant_id())",
                    "(tenant_id = identity.current_tenant_id())",
                )
            ]
            assert (
                connection.execute(
                    (
                        "SELECT count(*) FROM pg_trigger WHERE tgrelid=%s::regclass AND N"
                        "OT tgisinternal AND tgname='immutable_ownership'"
                    ),
                    (table,),
                ).fetchone()[0]
                == 1
            )
        for role in ["app_owner", "app_runtime"]:
            attributes = connection.execute(
                (
                    "SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypa"
                    "ssrls FROM pg_roles WHERE rolname=%s"
                ),
                (role,),
            ).fetchone()
            assert attributes == (False,) * 5
        assert not connection.execute(
            "SELECT rolinherit FROM pg_roles WHERE rolname='app_runtime'"
        ).fetchone()[0]
        assert (
            connection.execute(
                "SELECT count(*) FROM pg_auth_members m JOIN pg_roles r ON r.oid="
                "m.member WHERE r.rolname IN ('app_owner','app_runtime')"
            ).fetchone()[0]
            == 0
        )
        functions = connection.execute(
            "SELECT n.nspname,p.proname,p.prosecdef,p.proconfig,p.proacl FROM"
            " pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.n"
            "spname IN ('identity','catalog','practice','media')"
        ).fetchall()
        assert {(r[0], r[1]) for r in functions} == {
            ("identity", "current_tenant_id"),
            ("identity", "immutable_columns"),
            ("catalog", "immutable_columns"),
            ("practice", "immutable_columns"),
            ("practice", "immutable_snapshot"),
            ("media", "immutable_columns"),
        }
        assert all(
            not r[2] and r[3] and all(not acl.startswith("=") for acl in r[4] or [])
            for r in functions
        )
        assert (
            connection.execute(
                "SELECT count(*) FROM pg_default_acl WHERE defaclrole='app_owner'"
                "::regrole AND defaclobjtype='f' AND EXISTS (SELECT 1 FROM aclexp"
                "lode(defaclacl) WHERE grantee=0 AND privilege_type='EXECUTE')"
            ).fetchone()[0]
            == 0
        )
    with psycopg.connect(runtime) as connection:
        assert connection.execute("SELECT current_user, session_user").fetchone() == (
            "app_runtime",
            "app_runtime",
        )
        for table in expected:
            allowed = table in MANIFEST["private"] and not table.startswith("media.")
            select = allowed or table in MANIFEST["global"] or table in MANIFEST["technical"]
            assert (
                connection.execute(
                    (
                        "SELECT has_table_privilege(current_user,(SELECT c.oid FROM pg_cl"
                        "ass c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspnam"
                        "e||'.'||c.relname=%s),'SELECT')"
                    ),
                    (table,),
                ).fetchone()[0]
                == select
            )
            for privilege in ["INSERT", "UPDATE", "DELETE"]:
                granted = allowed and (
                    table != "practice.content_snapshot" or privilege == "INSERT"
                )
                assert (
                    connection.execute(
                        (
                            "SELECT has_table_privilege(current_user,(SELECT c.oid FROM pg_cl"
                            "ass c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspnam"
                            "e||'.'||c.relname=%s),%s)"
                        ),
                        (table, privilege),
                    ).fetchone()[0]
                    == granted
                )
        assert not connection.execute(
            "SELECT has_database_privilege(current_user,current_database(),'C"
            "REATE') OR has_database_privilege(current_user,current_database("
            "),'TEMP')"
        ).fetchone()[0]


@pytest.mark.parametrize(
    "command",
    [
        "SET ROLE app_owner",
        "CREATE TABLE public.escaped(id uuid)",
        "CREATE TEMP TABLE escaped(id uuid)",
        "CREATE TABLE catalog.escaped(id uuid)",
        "ALTER TABLE catalog.catalog DISABLE ROW LEVEL SECURITY",
        "ALTER TABLE catalog.catalog OWNER TO app_runtime",
        "ALTER POLICY tenant_isolation ON catalog.catalog USING (true)",
        "GRANT app_owner TO app_runtime",
        'SELECT * FROM identity."user"',
        "SELECT * FROM media.upload_intent",
        "SELECT identity.immutable_columns()",
    ],
)
def test_runtime_bypass_denied(db, command: str) -> None:
    with psycopg.connect(db[2]) as connection:
        with pytest.raises(psycopg.Error):
            connection.execute(command)


@pytest.mark.parametrize("value", [None, "", " ", "malformed", str(uuid4()) + "," + str(uuid4())])
def test_parser_fails_closed(db, value) -> None:
    with psycopg.connect(db[2]) as connection:
        if value is not None:
            connection.execute("SELECT set_config('app.tenant_id',%s,true)", (value,))
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute("SELECT identity.current_tenant_id()")


def sample_rows(connection, tenant, writer=None):
    """Build all then-present resources using synthetic nonbehavioral values."""
    source, instrument, definition = uuid4(), uuid4(), uuid4()
    connection.execute(
        "INSERT INTO catalog.source(id,key,name) VALUES (%s,%s,'fixture')", (source, str(source))
    )
    connection.execute(
        "INSERT INTO catalog.instrument(id,key,name) VALUES (%s,%s,'fixture')",
        (instrument, str(instrument)),
    )
    connection.execute(
        (
            "INSERT INTO catalog.source_definition(id,source_id,definition_ve"
            "rsion,definition) VALUES (%s,%s,1,'{}')"
        ),
        (definition, source),
    )
    connection.commit()
    ids = {name: uuid4() for name in MANIFEST["private"]}
    data = {
        "identity.user_preference": dict(user_id=uuid4(), settings=Jsonb({})),
        "catalog.catalog": dict(visibility="personal"),
        "catalog.catalog_grant": dict(
            catalog_id=ids["catalog.catalog"], grantee_tenant_id=tenant, role="owner"
        ),
        "catalog.entry": dict(
            catalog_id=ids["catalog.catalog"],
            source_id=source,
            source_definition_id=definition,
            instrument_id=instrument,
            entry_type="fixture",
            name="fixture",
            metadata=Jsonb({}),
            lifecycle_state="active",
        ),
        "practice.session": dict(
            local_date="2026-10-22", time_zone="Etc/UTC", notes="", status="fixture"
        ),
        "practice.record": dict(
            session_id=ids["practice.session"], catalog_entry_id=ids["catalog.entry"], notes=""
        ),
        "practice.content_snapshot": dict(
            record_id=ids["practice.record"], schema_version=1, content=Jsonb({})
        ),
        "media.upload_intent": dict(
            record_id=ids["practice.record"],
            object_key=str(uuid4()),
            content_type="fixture",
            state="fixture",
            retention_state="fixture",
        ),
        "media.attachment": dict(
            upload_intent_id=ids["media.upload_intent"],
            record_id=ids["practice.record"],
            object_key=str(uuid4()),
            content_type="fixture",
            state="fixture",
            retention_state="fixture",
        ),
    }
    for table, values in data.items():
        values.update(tenant_id=tenant, id=ids[table])
        insert(
            writer if writer is not None and not table.startswith("media.") else connection,
            table,
            values,
        )
    return ids, data


def insert(connection, table, values):
    schema, name = table.split(".")
    statement = sql.SQL("INSERT INTO {}.{} ({}) VALUES ({})").format(
        sql.Identifier(schema),
        sql.Identifier(name),
        sql.SQL(",").join(map(sql.Identifier, values)),
        sql.SQL(",").join(sql.Placeholder() for _ in values),
    )
    connection.execute(statement, list(values.values()))


def test_each_private_resource_rls_matrix_and_immutability(db) -> None:
    admin, _, runtime = db
    a, b = uuid4(), uuid4()
    with psycopg.connect(admin) as connection:
        with psycopg.connect(runtime) as own_writer:
            own_writer.execute("SELECT set_config('app.tenant_id',%s,true)", (str(a),))
            ids_a, data_a = sample_rows(connection, a, own_writer)
        ids_b, _ = sample_rows(connection, b)
    for table, shape in MANIFEST["private"].items():
        qualified = sql.Identifier(*table.split("."))
        with psycopg.connect(runtime) as connection:
            connection.execute("SELECT set_config('app.tenant_id',%s,true)", (str(a),))
            if table.startswith("media."):
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    connection.execute(sql.SQL("SELECT * FROM {}").format(qualified))
                continue
            # Deliberately omit repository predicates: this independently proves RLS.
            assert connection.execute(
                sql.SQL("SELECT id FROM {}").format(qualified)
            ).fetchall() == [(ids_a[table],)]
            assert connection.execute(
                sql.SQL("SELECT count(*) FROM {}").format(qualified)
            ).fetchone() == (1,)
            assert (
                connection.execute(
                    sql.SQL("SELECT id FROM {} WHERE id=%s").format(qualified), (ids_b[table],)
                ).fetchall()
                == []
            )
            if shape["mutable"]:
                assert (
                    connection.execute(
                        sql.SQL("UPDATE {} SET version=version+1 WHERE id=%s RETURNING id").format(
                            qualified
                        ),
                        (ids_b[table],),
                    ).fetchall()
                    == []
                )
                assert connection.execute(
                    sql.SQL("UPDATE {} SET version=version+1 RETURNING id").format(qualified)
                ).fetchall() == [(ids_a[table],)]
                assert (
                    connection.execute(
                        sql.SQL("DELETE FROM {} WHERE id=%s RETURNING id").format(qualified),
                        (ids_b[table],),
                    ).fetchall()
                    == []
                )
            with connection.transaction():
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    with connection.transaction():
                        bad = data_a[table] | {"id": uuid4(), "tenant_id": b}
                        insert(connection, table, bad)
        with psycopg.connect(runtime) as connection:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                connection.execute(sql.SQL("SELECT id FROM {}").format(qualified))
        # Trigger is tested as admin independently of runtime RLS/ACL masking.
        with psycopg.connect(admin) as connection:
            for column in shape["freeze"]:
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    with connection.transaction():
                        value = "not-owner" if column == "role" else uuid4()
                        connection.execute(
                            sql.SQL("UPDATE {} SET {}=%s WHERE id=%s").format(
                                qualified, sql.Identifier(column)
                            ),
                            (value, ids_a[table]),
                        )
    with psycopg.connect(admin) as connection:
        for statement in [
            "UPDATE practice.content_snapshot SET content='{\"changed\":true}'",
            "DELETE FROM practice.content_snapshot",
        ]:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with connection.transaction():
                    connection.execute(statement)


def test_same_tenant_composite_child_constraints(db) -> None:
    admin, _, runtime = db
    a, b = uuid4(), uuid4()
    with psycopg.connect(admin) as connection:
        ids_a, data_a = sample_rows(connection, a)
        ids_b, _ = sample_rows(connection, b)
    for table, parent in [
        ("catalog.catalog_grant", "catalog.catalog"),
        ("practice.record", "practice.session"),
        ("practice.content_snapshot", "practice.record"),
    ]:
        key = {
            "catalog.catalog_grant": "catalog_id",
            "practice.record": "session_id",
            "practice.content_snapshot": "record_id",
        }[table]
        with psycopg.connect(runtime) as connection:
            connection.execute("SELECT set_config('app.tenant_id',%s,true)", (str(a),))
            with pytest.raises(psycopg.errors.ForeignKeyViolation):
                insert(connection, table, data_a[table] | {"id": uuid4(), key: ids_b[parent]})
    with psycopg.connect(runtime) as connection:
        connection.execute("SELECT set_config('app.tenant_id',%s,true)", (str(a),))
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            insert(
                connection,
                "catalog.entry",
                data_a["catalog.entry"]
                | {"id": uuid4(), "parent_entry_id": ids_b["catalog.entry"]},
            )


def assert_private_policy(connection, table):
    schema, name = table.split(".")
    assert connection.execute(
        "SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid=%s::regclass", (table,)
    ).fetchone() == (True, True)
    assert connection.execute(
        "SELECT roles,cmd,qual,with_check FROM pg_policies WHERE schemaname=%s AND tablename=%s",
        (schema, name),
    ).fetchall() == [
        (
            ["app_runtime"],
            "ALL",
            "(tenant_id = identity.current_tenant_id())",
            "(tenant_id = identity.current_tenant_id())",
        )
    ]
    assert connection.execute(
        (
            "SELECT is_nullable FROM information_schema.columns WHERE table_s"
            "chema=%s AND table_name=%s AND column_name='tenant_id'"
        ),
        (schema, name),
    ).fetchone() == ("NO",)


@pytest.mark.parametrize(
    "mutation",
    [
        "ALTER POLICY tenant_isolation ON catalog.catalog USING (true)",
        "ALTER POLICY tenant_isolation ON catalog.catalog WITH CHECK (true)",
        "DROP POLICY tenant_isolation ON catalog.catalog",
        "ALTER TABLE catalog.catalog NO FORCE ROW LEVEL SECURITY",
        "ALTER TABLE catalog.catalog DISABLE ROW LEVEL SECURITY",
        "ALTER TABLE catalog.catalog ALTER COLUMN tenant_id DROP NOT NULL",
    ],
)
def test_independent_policy_catalog_mutations(db, mutation):
    with psycopg.connect(db[0]) as connection:
        assert_private_policy(connection, "catalog.catalog")
        connection.execute(mutation)
        with pytest.raises(AssertionError):
            assert_private_policy(connection, "catalog.catalog")
        connection.rollback()


def test_own_delete_positive_and_snapshot_acl(db):
    a = uuid4()
    with psycopg.connect(db[0]) as connection:
        ids, _ = sample_rows(connection, a)
        # Remove only fixture media/snapshot rows; immutable-row denial is tested separately.
        connection.execute(
            "TRUNCATE media.attachment,media.upload_intent,practice.content_snapshot"
        )
    with psycopg.connect(db[2]) as connection:
        connection.execute("SELECT set_config('app.tenant_id',%s,true)", (str(a),))
        for table in [
            "practice.record",
            "practice.session",
            "catalog.entry",
            "catalog.catalog_grant",
            "catalog.catalog",
            "identity.user_preference",
        ]:
            assert connection.execute(
                sql.SQL("DELETE FROM {} WHERE id=%s RETURNING id").format(
                    sql.Identifier(*table.split("."))
                ),
                (ids[table],),
            ).fetchone() == (ids[table],)
        for command in [
            "UPDATE practice.content_snapshot SET content='{}'",
            "DELETE FROM practice.content_snapshot",
        ]:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with connection.transaction():
                    connection.execute(command)


def test_ancestry_boundaries_and_media_composite(db):
    admin, _, runtime = db
    a, b = uuid4(), uuid4()
    with psycopg.connect(admin) as connection:
        ids_a, data_a = sample_rows(connection, a)
        ids_b, _ = sample_rows(connection, b)
        values = data_a["catalog.entry"]
        instrument2, source2, def2, version2 = uuid4(), uuid4(), uuid4(), uuid4()
        connection.execute(
            "INSERT INTO catalog.instrument(id,key,name) VALUES (%s,%s,'fixture')",
            (instrument2, str(instrument2)),
        )
        connection.execute(
            "INSERT INTO catalog.source(id,key,name) VALUES (%s,%s,'fixture')",
            (source2, str(source2)),
        )
        connection.execute(
            (
                "INSERT INTO catalog.source_definition(id,source_id,definition_ve"
                "rsion,definition) VALUES (%s,%s,1,'{}'),(%s,%s,2,'{}')"
            ),
            (def2, source2, version2, values["source_id"]),
        )
        for key in ["tenant_id", "id"]:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with connection.transaction():
                    connection.execute(
                        sql.SQL("UPDATE media.attachment SET {}=%s WHERE id=%s").format(
                            sql.Identifier(key)
                        ),
                        (uuid4(), ids_a["media.attachment"]),
                    )
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            with connection.transaction():
                insert(
                    connection,
                    "media.attachment",
                    data_a["media.attachment"]
                    | {
                        "id": uuid4(),
                        "object_key": str(uuid4()),
                        "upload_intent_id": ids_b["media.upload_intent"],
                    },
                )
    for mismatch in [
        dict(instrument_id=instrument2),
        dict(source_id=source2, source_definition_id=def2),
        dict(source_definition_id=version2),
        dict(catalog_id=uuid4()),
    ]:
        with psycopg.connect(runtime) as connection:
            connection.execute("SELECT set_config('app.tenant_id',%s,true)", (str(a),))
            with pytest.raises(psycopg.errors.ForeignKeyViolation):
                insert(
                    connection,
                    "catalog.entry",
                    values | {"id": uuid4(), "parent_entry_id": ids_a["catalog.entry"]} | mismatch,
                )
    with psycopg.connect(runtime) as connection:
        connection.execute("SELECT set_config('app.tenant_id',%s,true)", (str(a),))
        assert connection.execute(
            "SELECT count(*) FROM practice.record r JOIN practice.session s O"
            "N (r.tenant_id,r.session_id)=(s.tenant_id,s.id)"
        ).fetchone() == (1,)
        assert connection.execute(
            "SELECT count(*) FROM catalog.entry e JOIN catalog.catalog c ON ("
            "e.tenant_id,e.catalog_id)=(c.tenant_id,c.id)"
        ).fetchone() == (1,)
        # A second personal catalog cannot bypass same-catalog ancestry with another owner row.
        with pytest.raises(psycopg.errors.UniqueViolation):
            insert(
                connection,
                "catalog.catalog",
                {"tenant_id": a, "id": uuid4(), "visibility": "personal"},
            )


def test_local_private_foreign_keys_are_tenant_composite(db):
    with psycopg.connect(db[0]) as connection:
        rows = connection.execute(
            "SELECT n.nspname||'.'||c.relname, rn.nspname||'.'||rc.relname,\n "
            "           ARRAY(SELECT a.attname FROM unnest(k.conkey) WITH ORD"
            "INALITY u(num,ord) JOIN pg_attribute a ON a.attrelid=k.conrelid "
            "AND a.attnum=u.num ORDER BY u.ord),\n            ARRAY(SELECT a.a"
            "ttname FROM unnest(k.confkey) WITH ORDINALITY u(num,ord) JOIN pg"
            "_attribute a ON a.attrelid=k.confrelid AND a.attnum=u.num ORDER "
            "BY u.ord)\n            FROM pg_constraint k JOIN pg_class c ON c."
            "oid=k.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace JOIN "
            "pg_class rc ON rc.oid=k.confrelid JOIN pg_namespace rn ON rn.oid"
            "=rc.relnamespace\n            WHERE k.contype='f' AND n.nspname I"
            "N ('identity','catalog','practice','media')"
        ).fetchall()
        assert len(rows) == 14
        for source, target, columns, parent_columns in rows:
            assert source.split(".")[0] == target.split(".")[0]
            if source in MANIFEST["private"] and target in MANIFEST["private"]:
                assert len(columns) >= 2 and columns[0] == parent_columns[0] == "tenant_id"
        assert (
            "catalog.entry",
            "catalog.entry",
            [
                "tenant_id",
                "parent_entry_id",
                "catalog_id",
                "source_id",
                "source_definition_id",
                "instrument_id",
            ],
            ["tenant_id", "id", "catalog_id", "source_id", "source_definition_id", "instrument_id"],
        ) in rows


def test_fixed_full_schema_catalog_oracle(db):
    from pathlib import Path

    from tests.db_support import catalog_fingerprint

    expected = json.loads((Path(__file__).parent / "fixtures/schema-catalog.json").read_text())
    with psycopg.connect(db[0]) as connection:
        assert catalog_fingerprint(connection) == expected
        for mutation in [
            "CREATE TABLE identity.sixth_control_table(id uuid)",
            "ALTER TABLE catalog.entry ALTER COLUMN name DROP NOT NULL",
            "ALTER TABLE catalog.catalog OWNER TO app_runtime",
            'GRANT SELECT ON identity."user" TO app_runtime',
            "DROP TRIGGER immutable_ownership ON catalog.entry",
            "ALTER TABLE practice.record DROP CONSTRAINT record_tenant_id_session_id_fkey",
            "GRANT EXECUTE ON FUNCTION identity.current_tenant_id() TO PUBLIC",
        ]:
            connection.execute(mutation)
            assert catalog_fingerprint(connection) != expected
            connection.rollback()
