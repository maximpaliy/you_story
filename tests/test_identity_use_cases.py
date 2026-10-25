"""Identity orchestration controls and production-port PostgreSQL integration."""

from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlencode, urlsplit
from uuid import uuid4

import pytest
from psycopg.conninfo import conninfo_to_dict
from sqlalchemy.engine import URL

from tests.test_auth_crypto import settings
from you_story.identity.application.service import WebIdentity
from you_story.identity.domain.contracts import FinishResult, LimitResult, PendingLogin, SessionRow
from you_story.identity.domain.contracts import StartResult as LoginStartResult
from you_story.identity.infrastructure.actors import issue_session
from you_story.identity.infrastructure.crypto import IdentityCrypto
from you_story.identity.public import (
    AuthenticatedSession,
    AuthFailure,
    VerifiedIdentity,
    create_identity_service,
    require_validated_actor,
)
from you_story.shared.config import Settings
from you_story.shared.context import ActorContext
from you_story.shared.database import Database


class Provider:
    def __init__(self):
        self.subject = "synthetic-subject"
        self.exchanges = 0
        self.fail = False

    def authorize_url(self, *, state, nonce, challenge):
        self.nonce = nonce
        self.challenge = challenge
        return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(
            {"state": state, "nonce": nonce, "code_challenge": challenge}
        )

    def exchange(self, *, code, verifier, nonce_digest):
        self.exchanges += 1
        assert IdentityCrypto.challenge(verifier) == self.challenge
        assert nonce_digest == IdentityCrypto.digest("nonce", IdentityCrypto.decode(self.nonce))
        if self.fail:
            raise RuntimeError("PRIVATE_PROVIDER_SENTINEL")
        return VerifiedIdentity("https://accounts.google.com", self.subject)


class Store:
    """Unit fixture, never substitutes for real SQL atomicity or isolation tests."""

    def __init__(self):
        self.time = datetime.now(UTC)
        self.transactions = {}
        self.sessions = {}
        self.calls = []
        self.denied_scope = None
        self.finished = 0
        self.ready_calls = 0
        self.unavailable = False

    def now(self):
        if self.unavailable:
            raise RuntimeError("PRIVATE_DATABASE_SENTINEL")
        return self.time

    def limit(self, scope, key):
        self.calls.append(scope)
        return LimitResult(scope != self.denied_scope, self.time + timedelta(seconds=600))

    def start(
        self,
        transaction_id,
        binder,
        state,
        nonce,
        challenge,
        ciphertext,
        invitation,
        destination,
        expires_at,
    ):
        for _, (old_binder, old, status, expiry) in list(self.transactions.items()):
            if old_binder == binder and status in {"claimed", "succeeded"} and expiry > self.time:
                return LoginStartResult("in_progress")
            if old_binder == binder and status == "pending":
                self.transactions[old.id] = (binder, old, "invalidated", expiry)
        pending = PendingLogin(
            transaction_id, nonce, ciphertext, challenge, "google-web", invitation, destination
        )
        self.transactions[transaction_id] = (binder, pending, "pending", expires_at)
        self.state = state
        return LoginStartResult("ok", transaction_id, expires_at)

    def claim(self, state, binder):
        for identifier, (bound, pending, status, expiry) in self.transactions.items():
            if (
                state == self.state
                and binder == bound
                and status == "pending"
                and self.time < expiry
            ):
                self.transactions[identifier] = (bound, pending, "claimed", expiry)
                return pending
        return None

    def fail(self, transaction_id, binder):
        bound, pending, status, expiry = self.transactions[transaction_id]
        if bound == binder and status == "claimed":
            self.transactions[transaction_id] = (bound, pending, "failed", expiry)
        return True

    def finish(self, transaction_id, binder, issuer, subject, session_id, token, csrf):
        self.finished += 1
        bound, pending, status, expiry = self.transactions[transaction_id]
        if status != "claimed" or bound != binder or self.time >= expiry:
            return FinishResult("invalid")
        row = SessionRow(
            uuid4(), uuid4(), session_id, "catalog_pending", self.time + timedelta(days=30)
        )
        self.sessions[token] = row
        self.transactions[transaction_id] = (bound, pending, "succeeded", expiry)
        return FinishResult("ok", row)

    def resolve(self, token):
        if self.unavailable:
            raise RuntimeError("PRIVATE_DATABASE_SENTINEL")
        row = self.sessions.get(token)
        return row if row is not None and self.time < row.absolute_expires_at else None

    def revoke(self, token):
        return self.sessions.pop(token, None) is not None

    def mark_ready(self, token):
        self.ready_calls += 1
        return token in self.sessions


def runtime_settings(connection_info):
    values = conninfo_to_dict(connection_info)
    url = URL.create(
        "postgresql+psycopg",
        username=values["user"],
        password=values["password"],
        host=values["host"],
        port=int(values["port"]),
        database=values["dbname"],
    ).render_as_string(hide_password=False)
    return Settings(database_url=url)


def issuer(row, bearer):
    return issue_session(
        row.user_id,
        row.tenant_id,
        row.session_id,
        row.provisioning_state,
        row.absolute_expires_at,
        bearer,
    )


def unit_service():
    store, crypto, provider = Store(), IdentityCrypto(settings()), Provider()
    return WebIdentity(store, crypto, provider, issuer), store, crypto, provider


def begin(service, *, session_cookie=None):
    form = service.get_login_form(None)
    location = service.start_login(
        binder_cookie=form.binder_cookie,
        proof=form.proof,
        ip_key="127.0.0.1",
        session_cookie=session_cookie,
    )
    return form, parse_qs(urlsplit(location).query)["state"][0]


def finish(service, form, state, **changes):
    return service.complete_login(
        **(
            {
                "binder_cookie": form.binder_cookie,
                "state": state,
                "code": "synthetic-code",
                "ip_key": "127.0.0.1",
            }
            | changes
        )
    )


def test_login_profile_logout_and_replay_public_ports():
    service, store, _, provider = unit_service()
    form, state = begin(service)
    result = finish(service, form, state)
    assert result.destination == "/"
    resolved = service.resolve_session(result.session_cookie)
    assert resolved.actor == result.session.actor
    require_validated_actor(resolved.actor)
    assert store.finished == 1 and provider.exchanges == 1
    csrf = service.csrf_token(resolved)
    assert service.validate_csrf(resolved, csrf)
    assert service.csrf_token(resolved) == csrf
    with pytest.raises(AuthFailure) as replay:
        finish(service, form, state)
    assert replay.value.status == 400
    assert provider.exchanges == 1 and store.finished == 1
    assert service.logout(resolved)
    assert service.resolve_session(result.session_cookie) is None
    assert not service.validate_csrf(resolved, csrf)
    with pytest.raises(AuthFailure):
        service.mark_catalog_ready(resolved)
    assert store.ready_calls == 0


def test_wrong_binder_does_not_consume_claim_or_exchange():
    service, store, _, provider = unit_service()
    form, state = begin(service)
    other = service.get_login_form(None)
    with pytest.raises(AuthFailure):
        finish(service, other, state)
    assert next(iter(store.transactions.values()))[2] == "pending"
    assert provider.exchanges == 0
    assert finish(service, form, state).session_cookie


@pytest.mark.parametrize("failure", ["provider", "aead", "challenge", "error", "issuer"])
def test_claimed_failure_is_terminal_no_authority_or_detail(failure):
    service, store, _, provider = unit_service()
    form, state = begin(service)
    changes = {}
    if failure == "provider":
        provider.fail = True
    elif failure in {"aead", "challenge"}:
        identifier, (binder, pending, status, expiry) = next(iter(store.transactions.items()))
        from dataclasses import replace

        if failure == "aead":
            pending = replace(pending, encrypted_verifier=b"corrupt")
        else:
            pending = replace(pending, pkce_challenge="A" * 43)
        store.transactions[identifier] = (binder, pending, status, expiry)
    elif failure == "error":
        changes = {"error": "PRIVATE_PROVIDER_SENTINEL", "code": None}
    else:
        changes = {"issuer": "https://attacker.example"}
    with pytest.raises(AuthFailure) as error:
        finish(service, form, state, **changes)
    assert error.value.status == 400
    assert "PRIVATE" not in str(error.value)
    assert next(iter(store.transactions.values()))[2] == "failed"
    assert store.finished == 0 and not store.sessions
    if failure != "provider":
        assert provider.exchanges == 0
    with pytest.raises(AuthFailure):
        finish(service, form, state)


def test_proof_binding_expiry_and_counter_order():
    service, store, _, _ = unit_service()
    form = service.get_login_form(None)
    with pytest.raises(AuthFailure) as wrong:
        service.start_login(binder_cookie=form.binder_cookie, proof="wrong", ip_key="127.0.0.1")
    assert wrong.value.status == 403 and store.calls == ["IP-start"]
    store.calls.clear()
    store.denied_scope = "IP-start"
    with pytest.raises(AuthFailure) as limited:
        service.start_login(binder_cookie=form.binder_cookie, proof=form.proof, ip_key="127.0.0.1")
    assert limited.value.status == 429 and limited.value.retry_after == 600
    assert store.calls == ["IP-start"] and not store.transactions
    store.denied_scope = None
    store.time = form.expires_at
    with pytest.raises(AuthFailure):
        service.start_login(binder_cookie=form.binder_cookie, proof=form.proof, ip_key="127.0.0.1")
    fresh = service.get_login_form(form.binder_cookie)
    assert fresh.binder_cookie != form.binder_cookie
    assert fresh.expires_at > form.expires_at


def test_cookie_fixation_active_account_switch_and_independent_csrf():
    service, _, _, provider = unit_service()
    form, state = begin(service, session_cookie="A" * 43)
    first = finish(service, form, state, session_cookie="A" * 43)
    assert first.session_cookie != "A" * 43
    with pytest.raises(AuthFailure) as active:
        begin(service, session_cookie=first.session_cookie)
    assert active.value.status == 409
    form2, state2 = begin(service)
    with pytest.raises(AuthFailure) as switched:
        finish(service, form2, state2, session_cookie=first.session_cookie)
    assert switched.value.status == 409
    assert provider.exchanges == 1
    second = finish(service, form2, state2)
    assert second.session_cookie != first.session_cookie
    assert not service.validate_csrf(second.session, service.csrf_token(first.session))
    assert service.logout(first.session)
    assert service.resolve_session(second.session_cookie) is not None


def test_forged_actor_or_session_never_authorizes_use_case():
    service, _, _, _ = unit_service()
    result = finish(service, *begin(service))
    forged = object.__new__(ActorContext)
    for name in ["actor_id", "tenant_id", "provenance"]:
        object.__setattr__(forged, name, getattr(result.session.actor, name))
    assert forged == result.session.actor
    with pytest.raises(AuthFailure):
        require_validated_actor(forged)
    copied = AuthenticatedSession(
        result.session.actor,
        result.session.provisioning_state,
        result.session.session_id,
        result.session.absolute_expires_at,
        result.session._bearer,
    )
    with pytest.raises(AuthFailure):
        service.logout(copied)
    with pytest.raises(AuthFailure):
        service.csrf_token(copied)


def test_store_failure_is_safe_and_malformed_cookie_never_resolves():
    service, store, _, _ = unit_service()
    store.unavailable = True
    assert service.resolve_session("not-a-token") is None
    with pytest.raises(AuthFailure) as error:
        service.get_login_form(None)
    assert error.value.status == 503 and "PRIVATE" not in str(error.value)


@pytest.mark.postgres
def test_real_wrappers_with_actual_crypto_login_logout_and_digest_storage():
    from tests.auth_support import AuthDatabase

    auth = AuthDatabase.create()
    provider = Provider()
    auth.allowlist(provider.subject)
    database = Database(runtime_settings(auth.runtime_url))
    try:
        service = create_identity_service(database, settings(), provider=provider)
        form, state = begin(service)
        result = finish(service, form, state)
        resolved = service.resolve_session(result.session_cookie)
        assert resolved is not None
        assert resolved.actor == result.session.actor
        csrf = service.csrf_token(resolved)
        assert service.validate_csrf(resolved, csrf)
        with auth.admin() as admin:
            row = admin.execute(
                "SELECT token_digest,csrf_digest FROM identity.login_session WHERE id=%s",
                (resolved.session_id,),
            ).fetchone()
            assert bytes(row["token_digest"]) == IdentityCrypto.digest(
                "session", IdentityCrypto.decode(result.session_cookie)
            )
            assert bytes(row["csrf_digest"]) == IdentityCrypto.csrf_digest(
                csrf, resolved.session_id
            )
            transaction = admin.execute(
                "SELECT status,encrypted_verifier FROM identity.login_transaction"
            ).fetchone()
            assert transaction == {"status": "succeeded", "encrypted_verifier": None}
        with pytest.raises(AuthFailure):
            finish(service, form, state)
        assert provider.exchanges == 1
        assert service.logout(resolved)
        assert service.resolve_session(result.session_cookie) is None
    finally:
        database.close()


@pytest.mark.parametrize(
    "field,value", [("actor_id", uuid4()), ("tenant_id", uuid4()), ("provenance", "forged")]
)
def test_mutated_legitimate_actor_is_rejected_before_use_case(field, value):
    service, store, _, _ = unit_service()
    result = finish(service, *begin(service))
    object.__setattr__(result.session.actor, field, value)
    with pytest.raises(AuthFailure):
        require_validated_actor(result.session.actor)
    with pytest.raises(AuthFailure):
        service.mark_catalog_ready(result.session)
    assert store.ready_calls == 0


@pytest.mark.parametrize(
    "field", ["actor", "session_id", "provisioning_state", "absolute_expires_at", "_bearer"]
)
def test_mutated_legitimate_session_is_rejected_before_store(field):
    service, store, _, _ = unit_service()
    result = finish(service, *begin(service))
    values = {
        "actor": object.__new__(ActorContext),
        "session_id": uuid4(),
        "provisioning_state": "ready",
        "_bearer": b"x" * 32,
        "absolute_expires_at": result.session.absolute_expires_at + timedelta(days=1),
    }
    object.__setattr__(result.session, field, values[field])
    with pytest.raises(AuthFailure):
        service.logout(result.session)
    with pytest.raises(AuthFailure):
        service.mark_catalog_ready(result.session)
    assert store.ready_calls == 0 and len(store.sessions) == 1


@pytest.mark.postgres
def test_real_public_port_invalid_proof_replay_claim_expiry_and_session_expiry():
    from tests.auth_support import AuthDatabase

    auth = AuthDatabase.create()
    provider = Provider()
    auth.allowlist(provider.subject)
    database = Database(runtime_settings(auth.runtime_url))
    try:
        service = create_identity_service(database, settings(), provider=provider)
        form = service.get_login_form(None)
        with pytest.raises(AuthFailure) as forbidden:
            service.start_login(
                binder_cookie=form.binder_cookie, proof="invalid", ip_key="127.0.0.1"
            )
        assert forbidden.value.status == 403
        assert auth.counts() == {"user": 0, "tenant": 0, "external_identity": 0, "login_session": 0}
        form, state = begin(service)
        with auth.admin() as admin:
            admin.execute(
                "WITH moment AS MATERIALIZED (SELECT clock_timestamp() AS now) "
                "UPDATE identity.login_transaction SET "
                "created_at=moment.now-interval '601 seconds',"
                "expires_at=moment.now-interval '1 second' FROM moment"
            )
        with pytest.raises(AuthFailure) as expired:
            finish(service, form, state)
        assert expired.value.status == 400 and provider.exchanges == 0
        assert auth.counts()["user"] == 0
        form, state = begin(service)
        result = finish(service, form, state)
        with pytest.raises(AuthFailure):
            finish(service, form, state)
        assert provider.exchanges == 1
        with auth.admin() as admin:
            admin.execute(
                "UPDATE identity.login_session SET last_seen_at="
                "clock_timestamp()-interval '604801 seconds' WHERE id=%s",
                (result.session.session_id,),
            )
            seen = admin.execute(
                "SELECT last_seen_at FROM identity.login_session WHERE id=%s",
                (result.session.session_id,),
            ).fetchone()["last_seen_at"]
        assert service.resolve_session(result.session_cookie) is None
        with pytest.raises(AuthFailure):
            service.logout(result.session)
        with auth.admin() as admin:
            row = admin.execute(
                "SELECT last_seen_at,revoked_at FROM identity.login_session WHERE id=%s",
                (result.session.session_id,),
            ).fetchone()
            assert row["last_seen_at"] == seen and row["revoked_at"] is None
    finally:
        database.close()


def test_csrf_store_outage_remains_503_and_cannot_revoke():
    service, store, _, _ = unit_service()
    result = finish(service, *begin(service))
    csrf = service.csrf_token(result.session)
    store.unavailable = True
    with pytest.raises(AuthFailure) as error:
        service.validate_csrf(result.session, csrf)
    assert error.value.status == 503
    assert len(store.sessions) == 1


def test_succeeded_binder_blocks_competing_start_before_cookie_delivery():
    service, store, _, provider = unit_service()
    form, state = begin(service)
    result = finish(service, form, state)
    assert result.session_cookie
    with pytest.raises(AuthFailure) as error:
        service.start_login(binder_cookie=form.binder_cookie, proof=form.proof, ip_key="127.0.0.1")
    assert error.value.status == 409 and error.value.code == "login_in_progress"
    assert len(store.sessions) == 1 and provider.exchanges == 1


@pytest.mark.postgres
@pytest.mark.parametrize("failure", ["provider", "aead", "challenge", "error", "unknown_subject"])
def test_real_public_port_failures_consume_claim_without_provisioning(failure):
    from tests.auth_support import AuthDatabase

    auth = AuthDatabase.create()
    provider = Provider()
    if failure != "unknown_subject":
        auth.allowlist(provider.subject)
    database = Database(runtime_settings(auth.runtime_url))
    try:
        service = create_identity_service(database, settings(), provider=provider)
        form, state = begin(service)
        changes = {}
        if failure == "provider":
            provider.fail = True
        elif failure in {"aead", "challenge"}:
            with auth.admin() as admin:
                if failure == "aead":
                    admin.execute(
                        "UPDATE identity.login_transaction SET encrypted_verifier=%s",
                        (b"bad-aead-envelope",),
                    )
                else:
                    admin.execute(
                        "UPDATE identity.login_transaction SET pkce_challenge=%s", ("A" * 43,)
                    )
        elif failure == "error":
            changes = {"error": "PRIVATE_PROVIDER_DETAIL", "code": None}
        with pytest.raises(AuthFailure) as denied:
            finish(service, form, state, **changes)
        assert denied.value.status == 400
        assert "PRIVATE" not in str(denied.value)
        assert auth.counts() == {"user": 0, "tenant": 0, "external_identity": 0, "login_session": 0}
        with auth.admin() as admin:
            assert admin.execute(
                "SELECT status,encrypted_verifier FROM identity.login_transaction"
            ).fetchone() == {"status": "failed", "encrypted_verifier": None}
            assert (
                admin.execute(
                    "SELECT count(*) AS n FROM identity.invitation WHERE consumed_at IS NOT NULL"
                ).fetchone()["n"]
                == 0
            )
        assert provider.exchanges == (1 if failure in {"provider", "unknown_subject"} else 0)
        before = provider.exchanges
        with pytest.raises(AuthFailure):
            finish(service, form, state)
        assert provider.exchanges == before
    finally:
        database.close()


@pytest.mark.postgres
def test_real_public_ports_devices_csrf_forgery_and_logout_are_isolated():
    from tests.auth_support import AuthDatabase

    auth = AuthDatabase.create()
    provider = Provider()
    auth.allowlist(provider.subject)
    auth.allowlist("subject-b")
    database = Database(runtime_settings(auth.runtime_url))
    try:
        service = create_identity_service(database, settings(), provider=provider)
        a = finish(service, *begin(service))
        provider.subject = "subject-b"
        b = finish(service, *begin(service))
        assert a.session.actor.actor_id != b.session.actor.actor_id
        assert a.session.actor.tenant_id != b.session.actor.tenant_id
        a_csrf = service.csrf_token(a.session)
        assert service.validate_csrf(a.session, a_csrf)
        assert not service.validate_csrf(b.session, a_csrf)
        with pytest.raises(AuthFailure) as switching:
            begin(service, session_cookie=a.session_cookie)
        assert switching.value.status == 409
        copied = AuthenticatedSession(
            b.session.actor,
            b.session.provisioning_state,
            b.session.session_id,
            b.session.absolute_expires_at,
            b.session._bearer,
        )
        with pytest.raises(AuthFailure):
            service.logout(copied)
        with pytest.raises(AuthFailure):
            service.mark_catalog_ready(copied)
        assert service.logout(a.session)
        assert service.resolve_session(a.session_cookie) is None
        assert not service.validate_csrf(a.session, a_csrf)
        assert service.resolve_session(b.session_cookie) is not None
        assert auth.counts()["login_session"] == 2
        with auth.admin() as admin:
            revoked = admin.execute(
                "SELECT id,revoked_at IS NOT NULL AS revoked "
                "FROM identity.login_session ORDER BY id"
            ).fetchall()
            assert sum(row["revoked"] for row in revoked) == 1
    finally:
        database.close()
