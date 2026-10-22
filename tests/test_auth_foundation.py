"""Approved database auth boundary; no provider, HTTP or browser verification claim."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql

from tests.auth_support import CONFIG, ISSUER, AuthDatabase, Login, digest

pytestmark = pytest.mark.postgres


@pytest.fixture
def auth() -> AuthDatabase:
    return AuthDatabase.create()


def test_exact_control_plane_and_runtime_function_inventory(auth: AuthDatabase) -> None:
    expected = {
        "user",
        "tenant",
        "external_identity",
        "invitation",
        "login_session",
        "login_transaction",
        "auth_rate_limit",
    }
    with auth.admin() as connection:
        rows = connection.execute(
            "SELECT c.relname,c.relrowsecurity,c.relforcerowsecurity,r.rolname "
            "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "JOIN pg_roles r ON r.oid=c.relowner WHERE n.nspname='identity' AND c.relkind='r'"
        ).fetchall()
        actual = {row["relname"] for row in rows if not row["relrowsecurity"]}
        assert actual == expected
        assert all(row["rolname"] == "app_owner" for row in rows)
        assert all(not row["relforcerowsecurity"] for row in rows if row["relname"] in expected)
        procedures = connection.execute(
            "SELECT p.proname,p.prosecdef,p.proconfig,p.proacl::text AS acl,"
            "has_function_privilege('app_runtime',p.oid,'EXECUTE') AS runtime, "
            "EXISTS (SELECT 1 FROM aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a "
            "WHERE a.grantee=0 AND a.privilege_type='EXECUTE') AS public "
            "FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
            "WHERE n.nspname='identity' ORDER BY p.proname"
        ).fetchall()
        names = [row["proname"] for row in procedures if row["runtime"]]
        assert len(names) == len(set(names)), "unreviewed overload"
        assert set(names) == {
            "current_tenant_id",
            "start_web_login",
            "claim_web_login",
            "fail_web_login",
            "finish_web_login",
            "resolve_web_session",
            "revoke_web_session",
            "consume_auth_limit",
            "mark_catalog_ready",
        }
        for row in procedures:
            if row["runtime"] and row["proname"] != "current_tenant_id":
                assert row["prosecdef"]
                assert row["proconfig"] == ["search_path=pg_catalog, identity"]
            assert not row["public"], "PUBLIC function execution"
    for table in sorted(expected):
        with psycopg.connect(auth.runtime_url) as runtime:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                runtime.execute(sql.SQL("SELECT * FROM identity.{}").format(sql.Identifier(table)))


def test_start_exact_binding_pending_replacement_and_claimed_block(auth: AuthDatabase) -> None:
    first = auth.start()
    second = auth.start(Login(binder=first.binder, destination="calendar"))
    assert auth.claim(first) == []
    claimed = auth.claim(second)
    assert len(claimed) == 1
    assert set(claimed[0]) == {
        "id",
        "nonce_digest",
        "encrypted_verifier",
        "pkce_challenge",
        "client_config_id",
        "invitation_digest",
        "destination",
    }
    assert claimed[0]["encrypted_verifier"] == second.ciphertext
    assert claimed[0]["nonce_digest"] == second.nonce
    assert claimed[0]["destination"] == "calendar"
    with auth.admin() as connection:
        before = connection.execute(
            "SELECT count(*) AS n FROM identity.login_transaction"
        ).fetchone()
    candidate = Login(binder=first.binder, expires_at=second.expires_at)
    assert (
        auth.call(
            "start_web_login",
            candidate.id,
            candidate.binder,
            candidate.state,
            candidate.nonce,
            candidate.challenge,
            candidate.ciphertext,
            candidate.config,
            None,
            "home",
            candidate.expires_at,
        )
        == []
    )
    with auth.admin() as connection:
        assert (
            connection.execute("SELECT count(*) AS n FROM identity.login_transaction").fetchone()
            == before
        )
        row = connection.execute(
            "SELECT status,encrypted_verifier FROM identity.login_transaction WHERE id=%s",
            (second.id,),
        ).fetchone()
    assert row == {"status": "claimed", "encrypted_verifier": None}
    assert auth.claim(second) == []
    assert auth.scalar("fail_web_login", second.id, second.binder) is True
    assert auth.scalar("fail_web_login", second.id, second.binder) is False
    auth.start(Login(binder=first.binder))


def test_start_duplicate_uuid_rolls_back_pending_invalidation(auth: AuthDatabase) -> None:
    first = auth.start()
    duplicate = Login(id=first.id, binder=first.binder, expires_at=first.expires_at)
    assert (
        auth.call(
            "start_web_login",
            duplicate.id,
            duplicate.binder,
            duplicate.state,
            duplicate.nonce,
            duplicate.challenge,
            duplicate.ciphertext,
            duplicate.config,
            None,
            "home",
            duplicate.expires_at,
        )
        == []
    )
    assert len(auth.claim(first)) == 1


@pytest.mark.parametrize("wrong", ["state", "binder", "config"])
def test_wrong_claim_never_consumes_valid_flow(auth: AuthDatabase, wrong: str) -> None:
    login = auth.start()
    args = [login.state, login.binder, login.config]
    args[{"state": 0, "binder": 1, "config": 2}[wrong]] = "other" if wrong == "config" else digest()
    assert auth.call("claim_web_login", *args) == []
    assert len(auth.claim(login)) == 1
    assert auth.claim(login) == []


def test_claim_concurrent_single_winner_and_no_ciphertext_recovery(auth: AuthDatabase) -> None:
    login = auth.start()
    results = auth.race("claim_web_login", [(login.state, login.binder, login.config)] * 6)
    assert sum(bool(rows) for rows in results) == 1
    with auth.admin() as connection:
        assert (
            connection.execute(
                "SELECT encrypted_verifier FROM identity.login_transaction WHERE id=%s", (login.id,)
            ).fetchone()["encrypted_verifier"]
            is None
        )
    assert auth.scalar("fail_web_login", login.id, digest()) is False
    assert auth.finish(login, "unknown-no-invitation")[3] == []
    assert auth.claim(login) == []


def test_expired_claim_and_finalization_authority_fail_closed(auth: AuthDatabase) -> None:
    login = auth.start(Login(invitation=auth.invitation()))
    assert auth.claim(login)
    with auth.admin() as connection:
        connection.execute(
            "UPDATE identity.login_transaction "
            "SET created_at=statement_timestamp()-interval '601 seconds', "
            "expires_at=statement_timestamp()-interval '1 second' "
            "WHERE id=%s",
            (login.id,),
        )
    assert auth.finish(login, "expired-claim")[3] == []
    assert auth.counts() == {"user": 0, "tenant": 0, "external_identity": 0, "login_session": 0}


def test_invited_issuance_linkage_digest_only_and_exact_deadlines(auth: AuthDatabase) -> None:
    issued = auth.issue()
    assert set(issued.result) == {
        "user_id",
        "tenant_id",
        "session_id",
        "provisioning_state",
        "absolute_expires_at",
    }
    assert issued.result["session_id"] == issued.session_id
    assert issued.result["provisioning_state"] == "catalog_pending"
    with auth.admin() as connection:
        session = connection.execute(
            "SELECT * FROM identity.login_session WHERE id=%s", (issued.session_id,)
        ).fetchone()
        identity = connection.execute("SELECT * FROM identity.external_identity").fetchone()
        invitation = connection.execute("SELECT * FROM identity.invitation").fetchone()
        transaction = connection.execute("SELECT * FROM identity.login_transaction").fetchone()
    assert session["token_digest"] == issued.token_digest
    assert session["csrf_digest"] == issued.csrf_digest
    assert session["external_identity_id"] == identity["id"]
    assert session["user_id"] == identity["user_id"] == issued.result["user_id"]
    assert session["issued_at"] == session["created_at"] == session["last_seen_at"]
    assert session["absolute_expires_at"] - session["created_at"] == timedelta(days=30)
    assert invitation["consumed_user_id"] == issued.result["user_id"]
    assert transaction["status"] == "succeeded" and transaction["encrypted_verifier"] is None
    assert auth.finish(issued.login, issued.subject)[3] == []
    assert auth.claim(issued.login) == []


@pytest.mark.parametrize(
    "kind", ["absent", "expired", "wrong_issuer", "consumed", "bad_subject", "bad_issuer"]
)
def test_invitation_and_subject_failures_have_no_identity_side_effects(
    auth: AuthDatabase, kind: str
) -> None:
    invitation = None
    if kind == "expired":
        invitation = auth.invitation(expired=True)
    elif kind == "wrong_issuer":
        invitation = auth.invitation(issuer="https://untrusted.invalid")
    elif kind == "consumed":
        issued = auth.issue()
        invitation = issued.login.invitation
    elif kind in {"bad_subject", "bad_issuer"}:
        invitation = auth.invitation()
    before = auth.counts()
    login = auth.start(Login(invitation=invitation))
    assert auth.claim(login)
    subject = "non-ascii-\N{SNOWMAN}" if kind == "bad_subject" else f"new-{uuid4()}"
    issuer = "accounts.google.com" if kind == "bad_issuer" else ISSUER
    assert auth.finish(login, subject, issuer=issuer)[3] == []
    assert auth.counts() == before
    assert auth.scalar("fail_web_login", login.id, login.binder) is True


def test_existing_identity_ignores_invitation_and_binder_success_blocks_second_session(
    auth: AuthDatabase,
) -> None:
    first = auth.issue()
    untouched = auth.invitation()
    login = auth.start(Login(invitation=untouched))
    assert auth.claim(login)
    _, _, _, result = auth.finish(login, first.subject)
    assert result[0]["user_id"] == first.result["user_id"]
    assert auth.counts()["user"] == 1 and auth.counts()["login_session"] == 2
    with auth.admin() as connection:
        assert (
            connection.execute(
                "SELECT consumed_at FROM identity.invitation WHERE token_digest=%s", (untouched,)
            ).fetchone()["consumed_at"]
            is None
        )
    candidate = Login(binder=login.binder, expires_at=login.expires_at)
    assert (
        auth.call(
            "start_web_login",
            candidate.id,
            candidate.binder,
            candidate.state,
            candidate.nonce,
            candidate.challenge,
            candidate.ciphertext,
            CONFIG,
            None,
            "home",
            candidate.expires_at,
        )
        == []
    )


def test_one_invitation_two_subjects_race_exactly_one_atomic_triple(auth: AuthDatabase) -> None:
    invitation = auth.invitation()
    logins = [auth.start(Login(invitation=invitation)) for _ in range(2)]
    assert all(auth.claim(login) for login in logins)
    raw = auth.race(
        "finish_web_login",
        [
            (login.id, login.binder, ISSUER, f"racing-{number}", uuid4(), digest(), digest())
            for number, login in enumerate(logins)
        ],
    )
    results = [auth.normalize("finish_web_login", rows) for rows in raw]
    assert sum(bool(result) for result in results) == 1
    assert auth.counts() == {"user": 1, "tenant": 1, "external_identity": 1, "login_session": 1}


def test_finish_same_claim_concurrency_cannot_issue_twice(auth: AuthDatabase) -> None:
    login = auth.start(Login(invitation=auth.invitation()))
    assert auth.claim(login)
    raw = auth.race(
        "finish_web_login",
        [
            (login.id, login.binder, ISSUER, "same-subject", uuid4(), digest(), digest())
            for _ in range(4)
        ],
    )
    results = [auth.normalize("finish_web_login", rows) for rows in raw]
    assert sum(bool(result) for result in results) == 1
    assert auth.counts()["login_session"] == 1


def test_session_conflict_rolls_back_bootstrap_invitation_and_issuance_budget(
    auth: AuthDatabase,
) -> None:
    existing = auth.issue()
    invitation = auth.invitation()
    login = auth.start(Login(invitation=invitation))
    assert auth.claim(login)
    before = auth.counts()
    assert auth.finish(login, "new-conflicting-session", session_id=existing.session_id)[3] == []
    assert auth.counts() == before
    with auth.admin() as connection:
        assert (
            connection.execute(
                "SELECT consumed_at FROM identity.invitation WHERE token_digest=%s", (invitation,)
            ).fetchone()["consumed_at"]
            is None
        )
        row = connection.execute(
            "SELECT count FROM identity.auth_rate_limit WHERE scope='invitation-attempt' "
            "ORDER BY count DESC LIMIT 1"
        ).fetchone()
        assert row["count"] >= 1
        assert (
            connection.execute(
                "SELECT status FROM identity.login_transaction WHERE id=%s", (login.id,)
            ).fetchone()["status"]
            == "claimed"
        )
    assert auth.scalar("fail_web_login", login.id, login.binder) is True


@pytest.mark.parametrize("target", ["user", "tenant", "external_identity"])
def test_disabled_linkage_blocks_resolve_finish_and_ready(auth: AuthDatabase, target: str) -> None:
    issued = auth.issue()
    with auth.admin() as connection:
        connection.execute(
            sql.SQL("UPDATE identity.{} SET state='disabled'").format(sql.Identifier(target))
        )
    assert auth.call("resolve_web_session", issued.token_digest) == []
    assert auth.scalar("mark_catalog_ready", issued.token_digest) is False
    login = auth.start(Login(invitation=auth.invitation()))
    assert auth.claim(login)
    before = auth.counts()
    assert auth.finish(login, issued.subject)[3] == []
    assert auth.counts() == before


def test_resolve_touches_only_valid_session_and_ready_is_target_derived(auth: AuthDatabase) -> None:
    issued = auth.issue()
    with auth.admin() as connection:
        connection.execute(
            "UPDATE identity.login_session SET last_seen_at=clock_timestamp()-interval '1 hour' "
            "WHERE id=%s",
            (issued.session_id,),
        )
        before = connection.execute(
            "SELECT created_at,last_seen_at,absolute_expires_at "
            "FROM identity.login_session WHERE id=%s",
            (issued.session_id,),
        ).fetchone()
        counters = connection.execute(
            "SELECT to_jsonb(rl) AS row FROM identity.auth_rate_limit rl "
            "ORDER BY scope,subject_digest,window_start"
        ).fetchall()
        txs = connection.execute("SELECT * FROM identity.login_transaction ORDER BY id").fetchall()
    rows = auth.call("resolve_web_session", issued.token_digest)
    assert rows[0]["user_id"] == issued.result["user_id"]
    assert rows[0]["provisioning_state"] == "catalog_pending"
    with auth.admin() as connection:
        after = connection.execute(
            "SELECT created_at,last_seen_at,absolute_expires_at "
            "FROM identity.login_session WHERE id=%s",
            (issued.session_id,),
        ).fetchone()
        assert after["last_seen_at"] > before["last_seen_at"]
        assert after["created_at"] == before["created_at"]
        assert after["absolute_expires_at"] == before["absolute_expires_at"]
        assert (
            connection.execute(
                "SELECT to_jsonb(rl) AS row FROM identity.auth_rate_limit rl "
                "ORDER BY scope,subject_digest,window_start"
            ).fetchall()
            == counters
        )
        assert (
            connection.execute("SELECT * FROM identity.login_transaction ORDER BY id").fetchall()
            == txs
        )
    assert auth.scalar("mark_catalog_ready", digest()) is False
    assert auth.scalar("mark_catalog_ready", issued.token_digest) is True
    assert auth.scalar("mark_catalog_ready", issued.token_digest) is True
    assert auth.call("resolve_web_session", issued.token_digest)[0]["provisioning_state"] == "ready"


@pytest.mark.parametrize(
    "failure", ["unknown", "revoked", "idle", "absolute", "legacy_csrf", "legacy_identity"]
)
def test_invalid_sessions_return_no_fields_and_never_touch(
    auth: AuthDatabase, failure: str
) -> None:
    issued = auth.issue()
    mutations = {
        "revoked": "revoked_at=clock_timestamp()",
        "idle": "last_seen_at=clock_timestamp()-interval '7 days'",
        "absolute": "absolute_expires_at=clock_timestamp()",
        "legacy_csrf": "csrf_digest=NULL",
        "legacy_identity": "external_identity_id=NULL",
    }
    with auth.admin() as connection:
        if failure in mutations:
            connection.execute(
                sql.SQL("UPDATE identity.login_session SET {} WHERE id=%s").format(
                    sql.SQL(mutations[failure])
                ),
                (issued.session_id,),
            )
        before = connection.execute(
            "SELECT last_seen_at FROM identity.login_session WHERE id=%s", (issued.session_id,)
        ).fetchone()
    assert (
        auth.call("resolve_web_session", digest() if failure == "unknown" else issued.token_digest)
        == []
    )
    with auth.admin() as connection:
        assert (
            connection.execute(
                "SELECT last_seen_at FROM identity.login_session WHERE id=%s", (issued.session_id,)
            ).fetchone()
            == before
        )


def test_revoke_is_independent_and_resolve_race_never_revives(auth: AuthDatabase) -> None:
    first = auth.issue()
    second = auth.issue(subject=first.subject)
    results = auth.race_calls(
        [
            ("resolve_web_session", (first.token_digest,)),
            ("revoke_web_session", (first.token_digest,)),
        ]
    )
    assert results[1] == [{"revoke_web_session": True}]
    assert auth.call("resolve_web_session", first.token_digest) == []
    assert auth.scalar("revoke_web_session", first.token_digest) is False
    assert auth.call("resolve_web_session", second.token_digest)


@pytest.mark.parametrize(
    "scope,maximum",
    [
        ("IP-start", 20),
        ("IP-callback", 20),
        ("binder-start", 5),
        ("invitation-attempt", 10),
        ("user-issuance", 10),
    ],
)
def test_fixed_rate_limits_saturate_without_authority_side_effects(
    auth: AuthDatabase, scope: str, maximum: int
) -> None:
    key = digest()
    with auth.admin() as connection:
        instant = connection.execute("SELECT clock_timestamp() AS instant").fetchone()["instant"]
    with auth.clock(instant):
        rows = [auth.call("consume_auth_limit", scope, key)[0] for _ in range(maximum + 3)]
    assert all(row["allowed"] for row in rows[:maximum])
    assert all(not row["allowed"] for row in rows[maximum:])
    assert len({row["window_end"] for row in rows}) == 1
    assert all(set(row) == {"allowed", "window_end"} for row in rows)
    with auth.admin() as connection:
        counter = connection.execute(
            "SELECT count,window_start,expires_at FROM identity.auth_rate_limit "
            "WHERE scope=%s AND subject_digest=%s",
            (scope, key),
        ).fetchone()
    assert counter["count"] == maximum + 1
    assert counter["expires_at"] == rows[0]["window_end"] + timedelta(hours=24)
    assert auth.counts() == {"user": 0, "tenant": 0, "external_identity": 0, "login_session": 0}


def test_user_issuance_limit_rolls_back_session_and_does_not_revoke_existing(
    auth: AuthDatabase,
) -> None:
    first = auth.issue()
    for _ in range(9):
        auth.issue(subject=first.subject)
    login = auth.start()
    assert auth.claim(login)
    assert auth.finish(login, first.subject)[3] == []
    raw = auth.raw_call(
        "finish_web_login",
        login.id,
        login.binder,
        ISSUER,
        first.subject,
        uuid4(),
        digest(),
        digest(),
    )
    assert raw[0]["result"] == "limited" and raw[0]["window_end"] is not None
    assert auth.normalize("finish_web_login", raw) == []
    with auth.admin() as connection:
        assert (
            connection.execute(
                "SELECT count(*) AS n FROM identity.login_session WHERE revoked_at IS NULL"
            ).fetchone()["n"]
            == 10
        )
    assert auth.call("resolve_web_session", first.token_digest)


def test_active_session_cap_revokes_deterministic_oldest_without_touching_new(
    auth: AuthDatabase,
) -> None:
    first = auth.issue()
    for _ in range(9):
        auth.issue(subject=first.subject)
    with auth.admin() as connection:
        oldest = connection.execute(
            "SELECT id FROM identity.login_session ORDER BY created_at,id LIMIT 1"
        ).fetchone()["id"]
        connection.execute(
            "UPDATE identity.auth_rate_limit SET count=0 WHERE scope='user-issuance'"
        )
    newest = auth.issue(subject=first.subject)
    with auth.admin() as connection:
        rows = connection.execute(
            "SELECT id,revoked_at FROM identity.login_session ORDER BY created_at,id"
        ).fetchall()
    assert {row["id"] for row in rows if row["revoked_at"] is not None} == {oldest}
    assert len([row for row in rows if row["revoked_at"] is None]) == 10
    assert auth.call("resolve_web_session", newest.token_digest)


def test_owner_subject_allowlist_admission_is_exact_atomic_and_not_runtime_managed(
    auth: AuthDatabase,
) -> None:
    subject = f"allowlisted-{uuid4()}"
    admission = auth.allowlist(subject)
    wrong = auth.start()
    assert auth.claim(wrong)
    assert auth.finish(wrong, subject + "-wrong")[3] == []
    assert auth.counts()["user"] == 0
    login = auth.start()
    assert auth.claim(login)
    _, _, _, rows = auth.finish(login, subject)
    assert len(rows) == 1
    with auth.admin() as connection:
        row = connection.execute(
            "SELECT consumed_subject,consumed_user_id FROM identity.invitation "
            "WHERE token_digest=%s",
            (admission,),
        ).fetchone()
    assert row == {"consumed_subject": subject, "consumed_user_id": rows[0]["user_id"]}
    assert auth.counts()["user"] == 1


def test_allowlist_expiry_and_failed_finish_preserve_admission(auth: AuthDatabase) -> None:
    existing = auth.issue()
    subject = f"allowlist-conflict-{uuid4()}"
    admission = auth.allowlist(subject)
    login = auth.start()
    assert auth.claim(login)
    assert auth.finish(login, subject, session_id=existing.session_id)[3] == []
    with auth.admin() as connection:
        assert (
            connection.execute(
                "SELECT consumed_at FROM identity.invitation WHERE token_digest=%s", (admission,)
            ).fetchone()["consumed_at"]
            is None
        )
    expired_subject = f"expired-allowlist-{uuid4()}"
    auth.allowlist(expired_subject, expired=True)
    other = auth.start()
    assert auth.claim(other)
    assert auth.finish(other, expired_subject)[3] == []
    assert auth.counts()["user"] == 1


def test_exact_database_clock_claim_and_session_deadlines(auth: AuthDatabase) -> None:
    with auth.admin() as connection:
        instant = connection.execute("SELECT clock_timestamp() AS instant").fetchone()["instant"]
    with auth.clock(instant):
        login = auth.start(Login(expires_at=instant + timedelta(seconds=600)))
        auth.set_clock(instant + timedelta(seconds=600))
        assert auth.claim(login) == []
        auth.set_clock(instant)
        issued = auth.issue()
        auth.set_clock(instant + timedelta(days=7))
        assert auth.call("resolve_web_session", issued.token_digest) == []
        with auth.admin() as connection:
            connection.execute(
                "UPDATE identity.login_session SET last_seen_at=%s WHERE id=%s",
                (instant + timedelta(days=29), issued.session_id),
            )
        auth.set_clock(instant + timedelta(days=30))
        assert auth.call("resolve_web_session", issued.token_digest) == []


def test_counter_window_equality_uses_database_clock_and_independent_keys(
    auth: AuthDatabase,
) -> None:
    with auth.admin() as connection:
        instant = connection.execute(
            "SELECT to_timestamp(floor(extract(epoch FROM clock_timestamp())/600)*600+599) "
            "AS instant"
        ).fetchone()["instant"]
    key = digest()
    with auth.clock(instant):
        for _ in range(5):
            assert auth.call("consume_auth_limit", "binder-start", key)[0]["allowed"]
        denied = auth.call("consume_auth_limit", "binder-start", key)[0]
        assert not denied["allowed"]
        assert denied["window_end"] == instant + timedelta(seconds=1)
        assert auth.call("consume_auth_limit", "binder-start", digest())[0]["allowed"]
        assert auth.call("consume_auth_limit", "IP-start", key)[0]["allowed"]
        auth.set_clock(denied["window_end"])
        assert auth.call("consume_auth_limit", "binder-start", key)[0]["allowed"]
    with auth.admin() as connection:
        rows = connection.execute(
            "SELECT count FROM identity.auth_rate_limit WHERE scope='binder-start' "
            "AND subject_digest=%s ORDER BY window_start",
            (key,),
        ).fetchall()
    assert [row["count"] for row in rows] == [6, 1]


def test_invitation_attempt_failure_budget_persists_and_known_identity_ignores_it(
    auth: AuthDatabase,
) -> None:
    expired = auth.invitation(expired=True)
    for _ in range(2):
        login = auth.start(Login(invitation=expired))
        assert auth.claim(login)
        assert auth.finish(login, "new-expired-subject")[3] == []
    with auth.admin() as connection:
        attempted = connection.execute(
            "SELECT count FROM identity.auth_rate_limit WHERE scope='invitation-attempt'"
        ).fetchall()
    assert attempted == [{"count": 2}]
    known = auth.issue()
    with auth.admin() as connection:
        before = connection.execute(
            "SELECT * FROM identity.auth_rate_limit WHERE scope='invitation-attempt' "
            "ORDER BY subject_digest,window_start"
        ).fetchall()
    login = auth.start(Login(invitation=expired))
    assert auth.claim(login)
    assert auth.finish(login, known.subject)[3]
    with auth.admin() as connection:
        after = connection.execute(
            "SELECT * FROM identity.auth_rate_limit WHERE scope='invitation-attempt' "
            "ORDER BY subject_digest,window_start"
        ).fetchall()
    assert after == before


@pytest.mark.parametrize("scope", ["__transaction_capacity", "__counter_capacity", "other"])
def test_reserved_or_unknown_limiter_scopes_never_authorize_caller_control(
    auth: AuthDatabase,
    scope: str,
) -> None:
    with auth.admin() as connection:
        before = connection.execute(
            "SELECT to_jsonb(rl) AS row FROM identity.auth_rate_limit rl ORDER BY scope"
        ).fetchall()
    try:
        rows = auth.call("consume_auth_limit", scope, digest())
    except psycopg.Error as error:
        assert error.sqlstate == "22023"
        assert scope not in str(error)
    else:
        assert not rows or rows[0]["allowed"] is False
    with auth.admin() as connection:
        assert (
            connection.execute(
                "SELECT to_jsonb(rl) AS row FROM identity.auth_rate_limit rl ORDER BY scope"
            ).fetchall()
            == before
        )


def test_cleanup_once_bounded_and_capacity_reservations_match_actual_rows(
    auth: AuthDatabase,
) -> None:
    logins = [auth.start() for _ in range(105)]
    for _ in range(105):
        assert auth.call("consume_auth_limit", "binder-start", digest())[0]["allowed"]
    with auth.admin() as connection:
        connection.execute(
            "UPDATE identity.login_transaction "
            "SET created_at=statement_timestamp()-interval '25 hours 10 minutes', "
            "expires_at=statement_timestamp()-interval '25 hours'"
        )
        connection.execute(
            "UPDATE identity.auth_rate_limit SET expires_at=clock_timestamp()-interval '1 hour' "
            "WHERE scope='binder-start'"
        )
        before = connection.execute(
            "SELECT count(*) AS n FROM identity.login_transaction"
        ).fetchone()["n"]
    assert before == len(logins)
    assert auth.call("consume_auth_limit", "IP-start", digest())[0]["allowed"]
    with auth.admin() as connection:
        remaining = connection.execute(
            "SELECT count(*) AS n FROM identity.login_transaction"
        ).fetchone()["n"]
        counters = connection.execute(
            "SELECT count(*) AS n FROM identity.auth_rate_limit"
        ).fetchone()["n"]
        capacities = connection.execute(
            "SELECT scope,count FROM identity.auth_rate_limit "
            "WHERE scope LIKE '__%capacity' ORDER BY scope"
        ).fetchall()
    assert remaining == 5
    assert counters == 8  # five old ordinary rows, the IP row and two protected reservations
    assert capacities == [
        {"scope": "__counter_capacity", "count": counters},
        {"scope": "__transaction_capacity", "count": remaining},
    ]
    auth.start()
    assert auth.call("consume_auth_limit", "binder-start", digest())[0]["allowed"]
    with auth.admin() as connection:
        assert (
            connection.execute("SELECT count(*) AS n FROM identity.login_transaction").fetchone()[
                "n"
            ]
            == 6
        )
        assert (
            connection.execute(
                "SELECT count(*) AS n FROM identity.auth_rate_limit WHERE scope='binder-start'"
            ).fetchone()["n"]
            == 6
        )


def test_transaction_capacity_concurrent_admission_is_exact(auth: AuthDatabase) -> None:
    # Fill actual synthetic rows, rather than corrupting the protected reservation count.
    with auth.admin() as connection:
        connection.execute(
            "INSERT INTO identity.login_transaction("
            "id,state_digest,nonce_digest,binder_digest,pkce_challenge,encrypted_verifier,"
            "client_config_id,destination,status,created_at,expires_at,claimed_at) "
            "SELECT md5(n::text)::uuid,decode(md5(n::text)||md5('s'||n::text),'hex'),"
            "%s,%s,%s,NULL,%s,'home','failed',statement_timestamp(),"
            "statement_timestamp()+interval '600 seconds',statement_timestamp() "
            "FROM generate_series(1,99999) AS n",
            (digest(), digest(), "A" * 43, CONFIG),
        )
        connection.execute(
            "UPDATE identity.auth_rate_limit SET count=99999 WHERE scope='__transaction_capacity'"
        )
        expiry = connection.execute(
            "SELECT clock_timestamp()+interval '599 seconds' AS expiry"
        ).fetchone()["expiry"]
    candidates = [Login(expires_at=expiry), Login(expires_at=expiry)]

    rows = [
        result[0]
        for result in auth.race(
            "start_web_login",
            [
                (
                    login.id,
                    login.binder,
                    login.state,
                    login.nonce,
                    login.challenge,
                    login.ciphertext,
                    CONFIG,
                    None,
                    "home",
                    login.expires_at,
                )
                for login in candidates
            ],
        )
    ]
    assert sorted(row["result"] for row in rows) == ["ok", "unavailable"]
    with auth.admin() as connection:
        assert (
            connection.execute("SELECT count(*) AS n FROM identity.login_transaction").fetchone()[
                "n"
            ]
            == 100000
        )
        assert (
            connection.execute(
                "SELECT count FROM identity.auth_rate_limit WHERE scope='__transaction_capacity'"
            ).fetchone()["count"]
            == 100000
        )


def test_counter_physical_capacity_never_blocks_existing_session_resolution(
    auth: AuthDatabase,
) -> None:
    existing = auth.issue()
    with auth.admin() as connection:
        current = connection.execute(
            "SELECT count(*) AS n FROM identity.auth_rate_limit"
        ).fetchone()["n"]
        connection.execute(
            "INSERT INTO identity.auth_rate_limit"
            "(scope,subject_digest,window_start,count,expires_at) "
            "SELECT 'binder-start',decode(md5(n::text)||md5('k'||n::text),'hex'),"
            "to_timestamp(floor(extract(epoch FROM statement_timestamp())/600)*600),1,"
            "statement_timestamp()+interval '25 hours' FROM generate_series(1,%s) AS n",
            (199999 - current,),
        )
        connection.execute(
            "UPDATE identity.auth_rate_limit SET count=199999 WHERE scope='__counter_capacity'"
        )
    admission = auth.race(
        "consume_auth_limit", [("binder-start", digest()), ("binder-start", digest())]
    )
    assert sum(bool(rows) for rows in admission) == 1
    assert [rows[0]["allowed"] for rows in admission if rows] == [True]
    assert auth.call("consume_auth_limit", "binder-start", digest()) == []
    assert auth.call("resolve_web_session", existing.token_digest)
    unavailable_login = auth.start(Login(invitation=auth.invitation()))
    assert auth.claim(unavailable_login)
    unavailable = auth.raw_call(
        "finish_web_login",
        unavailable_login.id,
        unavailable_login.binder,
        ISSUER,
        "capacity-denied-new-subject",
        uuid4(),
        digest(),
        digest(),
    )
    assert unavailable[0]["result"] == "unavailable"
    assert auth.normalize("finish_web_login", unavailable) == []
    assert auth.counts() == {"user": 1, "tenant": 1, "external_identity": 1, "login_session": 1}
    with auth.admin() as connection:
        assert (
            connection.execute("SELECT count(*) AS n FROM identity.auth_rate_limit").fetchone()["n"]
            == 200000
        )
        assert (
            connection.execute(
                "SELECT count FROM identity.auth_rate_limit WHERE scope='__counter_capacity'"
            ).fetchone()["count"]
            == 200000
        )
    with auth.admin() as connection:
        key = connection.execute(
            "SELECT subject_digest FROM identity.auth_rate_limit WHERE scope='binder-start' "
            "ORDER BY subject_digest LIMIT 1"
        ).fetchone()["subject_digest"]
        connection.execute(
            "UPDATE identity.auth_rate_limit "
            "SET expires_at=statement_timestamp()-interval '1 second' "
            "WHERE scope='binder-start' AND subject_digest=%s",
            (key,),
        )
    replacement_key = digest()
    assert auth.call("consume_auth_limit", "IP-start", replacement_key)[0]["allowed"]
    with auth.admin() as connection:
        assert (
            connection.execute(
                "SELECT count(*) AS n FROM identity.auth_rate_limit WHERE scope='binder-start' "
                "AND subject_digest=%s",
                (key,),
            ).fetchone()["n"]
            == 0
        )
        assert (
            connection.execute("SELECT count(*) AS n FROM identity.auth_rate_limit").fetchone()["n"]
            == 200000
        )
        assert (
            connection.execute(
                "SELECT count FROM identity.auth_rate_limit WHERE scope='__counter_capacity'"
            ).fetchone()["count"]
            == 200000
        )


@pytest.mark.parametrize(
    "phase",
    [
        "invitation",
        "user",
        "tenant",
        "external_identity",
        "user-issuance",
        "login_session",
        "succeeded",
    ],
)
def test_finish_each_authority_phase_fault_rolls_back_atomically(
    auth: AuthDatabase,
    phase: str,
) -> None:
    invitation = auth.invitation()
    login = auth.start(Login(invitation=invitation))
    assert auth.claim(login)
    table = {
        "user-issuance": "auth_rate_limit",
        "succeeded": "login_transaction",
    }.get(phase, phase)
    condition = {
        "invitation": "NEW.consumed_at IS NOT NULL",
        "user-issuance": "NEW.scope='user-issuance'",
        "succeeded": "NEW.status='succeeded'",
    }.get(phase, "true")
    operation = (
        "INSERT OR UPDATE"
        if phase == "user-issuance"
        else ("UPDATE" if phase in {"invitation", "succeeded"} else "INSERT")
    )
    with auth.admin() as connection:
        connection.execute(
            "CREATE FUNCTION identity.test_only_fail_authority() RETURNS trigger "
            "LANGUAGE plpgsql SET search_path=pg_catalog AS $$ BEGIN "
            "RAISE EXCEPTION 'synthetic-private-fault' USING ERRCODE='23514'; END; $$"
        )
        connection.execute(
            sql.SQL(
                "CREATE TRIGGER test_only_authority_fault AFTER {} ON identity.{} "
                "FOR EACH ROW WHEN ({}) EXECUTE FUNCTION identity.test_only_fail_authority()"
            ).format(sql.SQL(operation), sql.Identifier(table), sql.SQL(condition))
        )
    assert auth.finish(login, f"phase-{phase}")[3] == []
    assert auth.counts() == {"user": 0, "tenant": 0, "external_identity": 0, "login_session": 0}
    with auth.admin() as connection:
        assert (
            connection.execute(
                "SELECT consumed_at FROM identity.invitation WHERE token_digest=%s", (invitation,)
            ).fetchone()["consumed_at"]
            is None
        )
        assert (
            connection.execute(
                "SELECT count(*) AS n FROM identity.auth_rate_limit WHERE scope='user-issuance'"
            ).fetchone()["n"]
            == 0
        )
        assert (
            connection.execute(
                "SELECT count FROM identity.auth_rate_limit WHERE scope='invitation-attempt'"
            ).fetchone()["count"]
            == 1
        )
        assert (
            connection.execute(
                "SELECT status FROM identity.login_transaction WHERE id=%s", (login.id,)
            ).fetchone()["status"]
            == "claimed"
        )
    assert auth.scalar("fail_web_login", login.id, login.binder) is True


@pytest.mark.parametrize(
    "field,value",
    [
        ("binder", None),
        ("binder", b"short"),
        ("state", b""),
        ("nonce", b"a" * 33),
        ("challenge", "A" * 42),
        ("challenge", "=" * 43),
        ("ciphertext", b""),
        ("ciphertext", b"a" * 4097),
        ("config", "caller-client"),
        ("destination", "https://untrusted.invalid"),
        ("invitation", b"bad"),
    ],
)
def test_malformed_start_is_fixed_invalid_without_state_changes(
    auth: AuthDatabase,
    field: str,
    value,
) -> None:
    login = Login()
    with auth.admin() as connection:
        login.expires_at = connection.execute(
            "SELECT clock_timestamp()+interval '599 seconds' AS expiry"
        ).fetchone()["expiry"]
    setattr(login, field, value)
    rows = auth.raw_call(
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
    assert rows == [{"result": "invalid", "id": None, "expires_at": None}]
    with auth.admin() as connection:
        assert (
            connection.execute("SELECT count(*) AS n FROM identity.login_transaction").fetchone()[
                "n"
            ]
            == 0
        )
        assert (
            connection.execute(
                "SELECT count FROM identity.auth_rate_limit WHERE scope='__transaction_capacity'"
            ).fetchone()["count"]
            == 0
        )


def test_duplicate_state_cannot_invalidate_previous_pending_transaction(auth: AuthDatabase) -> None:
    first = auth.start()
    duplicate = Login(state=first.state, binder=first.binder, expires_at=first.expires_at)
    rows = auth.raw_call(
        "start_web_login",
        duplicate.id,
        duplicate.binder,
        duplicate.state,
        duplicate.nonce,
        duplicate.challenge,
        duplicate.ciphertext,
        CONFIG,
        None,
        "home",
        duplicate.expires_at,
    )
    assert rows == [{"result": "invalid", "id": None, "expires_at": None}]
    assert auth.claim(first)


@pytest.mark.parametrize("stage", ["claim", "finish", "resolve"])
def test_observed_lock_wait_over_exact_expiry_denies_authority(
    auth: AuthDatabase,
    stage: str,
) -> None:
    with auth.admin() as connection:
        instant = connection.execute("SELECT clock_timestamp() AS instant").fetchone()["instant"]
    with auth.clock(instant):
        if stage == "resolve":
            issued = auth.issue()
            function = "resolve_web_session"
            arguments = (issued.token_digest,)
            expiry = instant + timedelta(days=7)
        else:
            login = auth.start(
                Login(invitation=auth.invitation(), expires_at=instant + timedelta(seconds=600))
            )
            expiry = login.expires_at
            function = "claim_web_login"
            arguments = (login.state, login.binder, CONFIG)
            if stage == "finish":
                assert auth.claim(login)
                function = "finish_web_login"
                arguments = (
                    login.id,
                    login.binder,
                    ISSUER,
                    "waited-subject",
                    uuid4(),
                    digest(),
                    digest(),
                )
        result = auth.race(function, [arguments], after_wait=lambda: auth.set_clock(expiry))[0]
        if stage == "finish":
            assert result[0]["result"] == "invalid"
            assert auth.normalize(function, result) == []
        else:
            assert result == []
        if stage != "resolve":
            assert auth.counts()["user"] == 0


def test_invitation_exact_expiry_and_finish_claim_equality_are_invalid(auth: AuthDatabase) -> None:
    with auth.admin() as connection:
        instant = connection.execute("SELECT clock_timestamp() AS instant").fetchone()["instant"]
    with auth.clock(instant):
        invitation = auth.invitation()
        with auth.admin() as connection:
            connection.execute(
                "UPDATE identity.invitation SET expires_at=%s WHERE token_digest=%s",
                (instant, invitation),
            )
        login = auth.start(
            Login(invitation=invitation, expires_at=instant + timedelta(seconds=600))
        )
        assert auth.claim(login)
        raw = auth.raw_call(
            "finish_web_login",
            login.id,
            login.binder,
            ISSUER,
            "exact-expired-invite",
            uuid4(),
            digest(),
            digest(),
        )
        assert raw[0]["result"] == "invalid"
        assert auth.normalize("finish_web_login", raw) == []
        assert auth.counts()["user"] == 0


def test_distinct_claimed_callbacks_same_subject_converge_one_identity(auth: AuthDatabase) -> None:
    invitation = auth.invitation()
    logins = [auth.start(Login(invitation=invitation)) for _ in range(2)]
    assert all(auth.claim(login) for login in logins)
    rows = auth.race(
        "finish_web_login",
        [
            (login.id, login.binder, ISSUER, "same-external-subject", uuid4(), digest(), digest())
            for login in logins
        ],
    )
    assert all(result[0]["result"] == "ok" for result in rows)
    assert rows[0][0]["user_id"] == rows[1][0]["user_id"]
    assert auth.counts() == {"user": 1, "tenant": 1, "external_identity": 1, "login_session": 2}


@pytest.mark.parametrize("stage", ["claim", "finish", "resolve", "revoke", "ready"])
def test_observed_row_lock_wait_rechecks_expiry_after_wait(auth: AuthDatabase, stage: str) -> None:
    if stage in {"resolve", "revoke", "ready"}:
        issued = auth.issue()
        function = {
            "resolve": "resolve_web_session",
            "revoke": "revoke_web_session",
            "ready": "mark_catalog_ready",
        }[stage]
        arguments = (issued.token_digest,)
        table, row_id, expiry_column = "login_session", issued.session_id, "absolute_expires_at"
    else:
        login = auth.start(Login(invitation=auth.invitation()))
        table, row_id, expiry_column = "login_transaction", login.id, "expires_at"
        function = "claim_web_login"
        arguments = (login.state, login.binder, CONFIG)
        if stage == "finish":
            assert auth.claim(login)
            function = "finish_web_login"
            arguments = (
                login.id,
                login.binder,
                ISSUER,
                "row-wait-subject",
                uuid4(),
                digest(),
                digest(),
            )
    rows = auth.row_wait(function, arguments, table, row_id, real_expiry_column=expiry_column)
    if stage == "finish":
        assert rows[0]["result"] == "invalid"
        assert auth.normalize(function, rows) == []
    elif stage in {"revoke", "ready"}:
        assert next(iter(rows[0].values())) is False
    else:
        assert rows == []
    if stage not in {"resolve", "revoke", "ready"}:
        assert auth.counts()["user"] == 0


@pytest.mark.parametrize("timezone", ["America/New_York", "Europe/Amsterdam", "Pacific/Auckland"])
def test_non_utc_runtime_timezone_cannot_change_fixed_session_lifetimes(
    auth: AuthDatabase,
    timezone: str,
) -> None:
    instant = {
        "America/New_York": datetime(2026, 3, 1, 12, tzinfo=UTC),
        "Europe/Amsterdam": datetime(2026, 3, 20, 12, tzinfo=UTC),
        "Pacific/Auckland": datetime(2026, 9, 20, 12, tzinfo=UTC),
    }[timezone]
    with auth.clock(instant):
        login = auth.start(
            Login(invitation=auth.invitation(), expires_at=instant + timedelta(seconds=600))
        )
        assert auth.claim(login)
        session_id, session_digest, csrf_digest = uuid4(), digest(), digest()
        rows = auth.raw_call(
            "finish_web_login",
            login.id,
            login.binder,
            ISSUER,
            "timezone-subject",
            session_id,
            session_digest,
            csrf_digest,
            session_timezone=timezone,
        )
        assert rows[0]["result"] == "ok"
        assert rows[0]["absolute_expires_at"] - instant == timedelta(seconds=2592000)
        auth.set_clock(instant + timedelta(seconds=604800))
        assert auth.raw_call("resolve_web_session", session_digest, session_timezone=timezone) == []


def test_raw_start_in_progress_and_finish_invalid_categories_are_explicit(
    auth: AuthDatabase,
) -> None:
    login = auth.start()
    assert auth.claim(login)
    candidate = Login(binder=login.binder, expires_at=login.expires_at)
    blocked = auth.raw_call(
        "start_web_login",
        candidate.id,
        candidate.binder,
        candidate.state,
        candidate.nonce,
        candidate.challenge,
        candidate.ciphertext,
        CONFIG,
        None,
        "home",
        candidate.expires_at,
    )
    assert blocked == [{"result": "in_progress", "id": None, "expires_at": None}]
    invalid = auth.raw_call(
        "finish_web_login",
        login.id,
        login.binder,
        ISSUER,
        "no-admission-subject",
        uuid4(),
        digest(),
        digest(),
    )
    assert invalid == [
        {
            "result": "invalid",
            "user_id": None,
            "tenant_id": None,
            "session_id": None,
            "provisioning_state": None,
            "absolute_expires_at": None,
            "window_end": None,
        }
    ]


def test_cleanup_combines_deletion_and_expiry_in_one_hundred_row_budget(auth: AuthDatabase) -> None:
    deleted = [auth.start() for _ in range(80)]
    expired = [auth.start() for _ in range(80)]
    fresh = [auth.start() for _ in range(4)]
    with auth.admin() as connection:
        connection.execute(
            "UPDATE identity.login_transaction SET "
            "created_at=statement_timestamp()-interval '25 hours 10 minutes', "
            "expires_at=statement_timestamp()-interval '25 hours' WHERE id=ANY(%s)",
            ([login.id for login in deleted],),
        )
        connection.execute(
            "UPDATE identity.login_transaction SET "
            "created_at=statement_timestamp()-interval '601 seconds', "
            "expires_at=statement_timestamp()-interval '1 second' WHERE id=ANY(%s)",
            ([login.id for login in expired],),
        )
    assert auth.call("consume_auth_limit", "IP-callback", digest())[0]["allowed"]
    with auth.admin() as connection:
        rows = connection.execute(
            "SELECT id,status,encrypted_verifier FROM identity.login_transaction"
        ).fetchall()
        assert len(rows) == 84
        assert (
            connection.execute(
                "SELECT count FROM identity.auth_rate_limit WHERE scope='__transaction_capacity'"
            ).fetchone()["count"]
            == 84
        )
        assert sum(row["status"] == "expired" for row in rows) == 20
        assert all(row["encrypted_verifier"] is None for row in rows if row["status"] == "expired")
        assert all(
            row["status"] == "pending" and row["encrypted_verifier"] is not None
            for row in rows
            if row["id"] in {login.id for login in fresh}
        )
    auth.start()
    assert auth.claim(fresh[0])
    assert auth.finish(fresh[0], "not-admitted-subject")[3] == []
    with auth.admin() as connection:
        assert (
            connection.execute(
                "SELECT count(*) AS n FROM identity.login_transaction WHERE status='expired'"
            ).fetchone()["n"]
            == 20
        )
        assert (
            connection.execute(
                "SELECT count(*) AS n FROM identity.login_transaction "
                "WHERE id=ANY(%s) AND status='pending'",
                ([login.id for login in expired],),
            ).fetchone()["n"]
            == 60
        )
        assert (
            connection.execute(
                "SELECT count FROM identity.auth_rate_limit WHERE scope='__transaction_capacity'"
            ).fetchone()["count"]
            == 85
        )


@pytest.mark.parametrize("guard", ["binder", "expiry", "status", "claim_reset"])
def test_claim_guard_mutations_are_detected_by_behavioral_oracles(
    auth: AuthDatabase, guard: str
) -> None:
    login = auth.start()
    wrong_binder = digest()
    if guard == "binder":
        assert auth.call("claim_web_login", login.state, wrong_binder, CONFIG) == []
        replacements = [("AND tx.binder_digest = p_binder", "")]
        arguments = (login.state, wrong_binder, CONFIG)
    elif guard == "expiry":
        with auth.admin() as connection:
            connection.execute(
                "UPDATE identity.login_transaction SET "
                "created_at=statement_timestamp()-interval '601 seconds', "
                "expires_at=statement_timestamp()-interval '1 second' WHERE id=%s",
                (login.id,),
            )
        assert auth.claim(login) == []
        replacements = [
            ("AND tx.expires_at > v_now", ""),
            ("IF v_tx.expires_at <= v_now THEN RETURN; END IF;", ""),
        ]
        arguments = (login.state, login.binder, CONFIG)
    elif guard == "status":
        assert auth.claim(login)
        assert auth.claim(login) == []
        replacements = [("tx.status = 'pending'", "tx.status IN ('pending','claimed')")]
        arguments = (login.state, login.binder, CONFIG)
    else:
        replacements = [
            (
                "SET status = 'claimed',claimed_at = v_now,encrypted_verifier = NULL",
                "SET status='pending',claimed_at=NULL,encrypted_verifier=v_tx.encrypted_verifier",
            )
        ]
        arguments = (login.state, login.binder, CONFIG)
    with auth.mutate_function("claim_web_login", replacements):
        if guard == "claim_reset":
            assert auth.claim(login)
        leaked = auth.call("claim_web_login", *arguments)
        with pytest.raises(AssertionError, match="claim authority guard failed"):
            assert leaked == [], "claim authority guard failed"


@pytest.mark.parametrize("guard", ["active_user", "revocation", "absolute_expiry", "legacy_csrf"])
def test_session_guard_mutations_are_detected_by_behavioral_oracles(
    auth: AuthDatabase, guard: str
) -> None:
    issued = auth.issue()
    replacements = []
    with auth.admin() as connection:
        if guard == "active_user":
            connection.execute("UPDATE identity.\"user\" SET state='disabled'")
            replacements = [("AND u.state = 'active'", "")]
        elif guard == "revocation":
            assert auth.scalar("revoke_web_session", issued.token_digest) is True
            replacements = [("AND s.revoked_at IS NULL", "")]
        elif guard == "absolute_expiry":
            connection.execute(
                "UPDATE identity.login_session SET absolute_expires_at=clock_timestamp()"
            )
            replacements = [("AND s.absolute_expires_at > v_now", "")]
        else:
            connection.execute("UPDATE identity.login_session SET csrf_digest=NULL")
            replacements = [
                (" OR v_session.csrf_digest IS NULL", ""),
                ("AND s.csrf_digest IS NOT NULL", ""),
            ]
    assert auth.call("resolve_web_session", issued.token_digest) == []
    with auth.mutate_function("resolve_web_session", replacements):
        leaked = auth.call("resolve_web_session", issued.token_digest)
        with pytest.raises(AssertionError, match="session authority guard failed"):
            assert leaked == [], "session authority guard failed"


def test_capacity_reservation_omission_fails_conservation_oracle(auth: AuthDatabase) -> None:
    positive = auth.start()
    with auth.admin() as connection:
        before = connection.execute(
            "SELECT count FROM identity.auth_rate_limit WHERE scope='__transaction_capacity'"
        ).fetchone()["count"]
    assert before == 1
    replacement = [
        (
            "UPDATE identity.auth_rate_limit rl SET count = rl.count + 1 "
            "WHERE rl.scope = '__transaction_capacity';",
            "NULL;",
        )
    ]
    with auth.mutate_function("start_web_login", replacement):
        auth.start()
        with auth.admin() as connection:
            actual = connection.execute(
                "SELECT count(*) AS n FROM identity.login_transaction"
            ).fetchone()["n"]
            reserved = connection.execute(
                "SELECT count FROM identity.auth_rate_limit WHERE scope='__transaction_capacity'"
            ).fetchone()["count"]
        with pytest.raises(AssertionError, match="capacity conservation failed"):
            assert actual == reserved, "capacity conservation failed"
    assert auth.claim(positive)


def test_attempt_counter_rollback_mutation_fails_failure_budget_oracle(auth: AuthDatabase) -> None:
    existing = auth.issue()
    invitation = auth.invitation()
    login = auth.start(Login(invitation=invitation))
    assert auth.claim(login)
    consume = (
        "SELECT r.* INTO v_limit FROM identity._auth_consume('invitation-attempt',"
        "v_tx.invitation_digest,v_now) r;"
    )
    marker = (
        "-- Only this inner unit may create identity/session authority. "
        "Attempt budget above survives failure.\n  BEGIN"
    )
    replacements = [
        (consume, "SELECT true AS allowed,v_now AS window_end INTO v_limit;"),
        (marker, marker + "\n    " + consume),
    ]
    with auth.admin() as connection:
        before = connection.execute(
            "SELECT coalesce(sum(count),0) AS n FROM identity.auth_rate_limit "
            "WHERE scope='invitation-attempt'"
        ).fetchone()["n"]
    with auth.mutate_function("finish_web_login", replacements):
        assert (
            auth.finish(login, "rollback-budget-subject", session_id=existing.session_id)[3] == []
        )
        with auth.admin() as connection:
            after = connection.execute(
                "SELECT coalesce(sum(count),0) AS n FROM identity.auth_rate_limit "
                "WHERE scope='invitation-attempt'"
            ).fetchone()["n"]
        with pytest.raises(AssertionError, match="failed attempt was not retained"):
            assert after == before + 1, "failed attempt was not retained"


def test_failed_finish_partial_authority_mutation_fails_atomicity_oracle(
    auth: AuthDatabase,
) -> None:
    login = auth.start(Login(invitation=auth.invitation()))
    assert auth.claim(login)
    marker = "INSERT INTO identity.login_session("
    premature_failure = (
        "RETURN QUERY SELECT 'invalid'::text,NULL::uuid,NULL::uuid,NULL::uuid,NULL::text,"
        "NULL::timestamptz,NULL::timestamptz; RETURN;\n    "
    )
    with auth.mutate_function("finish_web_login", [(marker, premature_failure + marker)]):
        raw = auth.raw_call(
            "finish_web_login",
            login.id,
            login.binder,
            ISSUER,
            "partial-write-mutant",
            uuid4(),
            digest(),
            digest(),
        )
        assert raw[0]["result"] == "invalid"
        assert auth.normalize("finish_web_login", raw) == []
        counts = auth.counts()
        with auth.admin() as connection:
            consumed = connection.execute("SELECT consumed_at FROM identity.invitation").fetchone()[
                "consumed_at"
            ]
        with pytest.raises(AssertionError, match="failed finish committed authority"):
            assert (
                counts == {"user": 0, "tenant": 0, "external_identity": 0, "login_session": 0}
                and consumed is None
            ), "failed finish committed authority"


@pytest.mark.parametrize("first", ["resolve_web_session", "revoke_web_session"])
def test_revoke_touch_both_observed_serialization_orders(auth: AuthDatabase, first: str) -> None:
    issued = auth.issue()
    second = "revoke_web_session" if first == "resolve_web_session" else "resolve_web_session"
    first_rows, second_rows = auth.ordered_calls(
        first, (issued.token_digest,), second, (issued.token_digest,)
    )
    if first == "resolve_web_session":
        assert first_rows[0]["session_id"] == issued.session_id
        assert second_rows == [{"revoke_web_session": True}]
    else:
        assert first_rows == [{"revoke_web_session": True}]
        assert second_rows == []
    assert auth.call("resolve_web_session", issued.token_digest) == []
    with auth.admin() as connection:
        assert (
            connection.execute(
                "SELECT revoked_at FROM identity.login_session WHERE id=%s", (issued.session_id,)
            ).fetchone()["revoked_at"]
            is not None
        )


def test_finish_wrong_binder_cannot_consume_claim_admission_or_attempt_budget(
    auth: AuthDatabase,
) -> None:
    login = auth.start(Login(invitation=auth.invitation()))
    assert auth.claim(login)
    invalid = auth.raw_call(
        "finish_web_login", login.id, digest(), ISSUER, "bound-subject", uuid4(), digest(), digest()
    )
    assert invalid == [
        {
            "result": "invalid",
            "user_id": None,
            "tenant_id": None,
            "session_id": None,
            "provisioning_state": None,
            "absolute_expires_at": None,
            "window_end": None,
        }
    ]
    assert auth.counts() == {"user": 0, "tenant": 0, "external_identity": 0, "login_session": 0}
    with auth.admin() as connection:
        assert (
            connection.execute(
                "SELECT count(*) AS n FROM identity.auth_rate_limit "
                "WHERE scope='invitation-attempt'"
            ).fetchone()["n"]
            == 0
        )
        assert (
            connection.execute("SELECT consumed_at FROM identity.invitation").fetchone()[
                "consumed_at"
            ]
            is None
        )
    assert auth.finish(login, "bound-subject")[3]


def test_finish_binder_guard_mutation_is_detected_independently_of_claim(
    auth: AuthDatabase,
) -> None:
    login = auth.start(Login(invitation=auth.invitation()))
    assert auth.claim(login)
    arguments = (login.id, digest(), ISSUER, "mutated-finish-binder", uuid4(), digest(), digest())
    assert auth.raw_call("finish_web_login", *arguments)[0]["result"] == "invalid"
    with auth.mutate_function("finish_web_login", [("AND tx.binder_digest = p_binder", "")]):
        result = auth.raw_call("finish_web_login", *arguments)
        with pytest.raises(AssertionError, match="finalization binder guard failed"):
            assert result[0]["result"] == "invalid", "finalization binder guard failed"


def test_cleanup_eligibility_is_inclusive_at_exact_retention_deadline(
    auth: AuthDatabase,
) -> None:
    with auth.admin() as connection:
        instant = connection.execute(
            "SELECT date_trunc('second',clock_timestamp()) AS instant"
        ).fetchone()["instant"]
    microsecond = timedelta(microseconds=1)
    with auth.clock(instant):
        equal, later, fresh = [auth.start() for _ in range(3)]
        equal_key, later_key, fresh_key = [digest() for _ in range(3)]
        for key in [equal_key, later_key, fresh_key]:
            assert auth.call("consume_auth_limit", "binder-start", key)[0]["allowed"]
        with auth.admin() as connection:
            for login, eligibility in [(equal, instant), (later, instant + microsecond)]:
                expiry = eligibility - timedelta(seconds=86400)
                connection.execute(
                    "UPDATE identity.login_transaction SET created_at=%s,expires_at=%s WHERE id=%s",
                    (expiry - timedelta(seconds=600), expiry, login.id),
                )
            for key, eligibility in [(equal_key, instant), (later_key, instant + microsecond)]:
                # Cleanup is specified against expires_at. Producer window alignment has
                # its own tests; this fixture isolates the timestamp comparison at one us.
                connection.execute(
                    "UPDATE identity.auth_rate_limit SET window_start=%s,expires_at=%s "
                    "WHERE scope='binder-start' AND subject_digest=%s",
                    (eligibility - timedelta(seconds=87000), eligibility, key),
                )
        assert auth.call("consume_auth_limit", "IP-callback", digest())[0]["allowed"]
        with auth.admin() as connection:
            transactions = connection.execute(
                "SELECT id,status,encrypted_verifier FROM identity.login_transaction ORDER BY id"
            ).fetchall()
            assert {row["id"] for row in transactions} == {later.id, fresh.id}
            assert next(row for row in transactions if row["id"] == later.id) == {
                "id": later.id,
                "status": "expired",
                "encrypted_verifier": None,
            }
            assert next(row for row in transactions if row["id"] == fresh.id) == {
                "id": fresh.id,
                "status": "pending",
                "encrypted_verifier": fresh.ciphertext,
            }
            counter_keys = {
                row["subject_digest"]
                for row in connection.execute(
                    "SELECT subject_digest FROM identity.auth_rate_limit WHERE scope='binder-start'"
                ).fetchall()
            }
            assert counter_keys == {later_key, fresh_key}
            assert connection.execute(
                "SELECT count=(SELECT count(*) FROM identity.login_transaction) AS matches "
                "FROM identity.auth_rate_limit WHERE scope='__transaction_capacity'"
            ).fetchone()["matches"]
            assert connection.execute(
                "SELECT count=(SELECT count(*) FROM identity.auth_rate_limit) AS matches "
                "FROM identity.auth_rate_limit WHERE scope='__counter_capacity'"
            ).fetchone()["matches"]
        auth.set_clock(instant + microsecond)
        assert auth.call("consume_auth_limit", "IP-callback", digest())[0]["allowed"]
        with auth.admin() as connection:
            assert connection.execute(
                "SELECT id FROM identity.login_transaction ORDER BY id"
            ).fetchall() == [{"id": fresh.id}]
            assert connection.execute(
                "SELECT subject_digest FROM identity.auth_rate_limit WHERE scope='binder-start'"
            ).fetchall() == [{"subject_digest": fresh_key}]
            assert connection.execute(
                "SELECT count=(SELECT count(*) FROM identity.login_transaction) AS matches "
                "FROM identity.auth_rate_limit WHERE scope='__transaction_capacity'"
            ).fetchone()["matches"]
            assert connection.execute(
                "SELECT count=(SELECT count(*) FROM identity.auth_rate_limit) AS matches "
                "FROM identity.auth_rate_limit WHERE scope='__counter_capacity'"
            ).fetchone()["matches"]
