"""Private typed adapters for the exact reviewed revision-005 owner wrappers."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.sql.elements import TextClause

from you_story.identity.domain.contracts import (
    FinishResult,
    LimitResult,
    PendingLogin,
    SessionRow,
    StartResult,
)
from you_story.shared.database import Database


def _session(row: Mapping[str, Any]) -> SessionRow:
    result = SessionRow(
        row["user_id"],
        row["tenant_id"],
        row["session_id"],
        row["provisioning_state"],
        row["absolute_expires_at"],
    )
    if (
        not all(
            isinstance(value, UUID)
            for value in (result.user_id, result.tenant_id, result.session_id)
        )
        or result.provisioning_state not in {"catalog_pending", "ready"}
        or not isinstance(result.absolute_expires_at, datetime)
        or result.absolute_expires_at.tzinfo is None
    ):
        raise ValueError("Invalid session result")
    return result


class PostgresIdentity:
    def __init__(self, database: Database) -> None:
        self._database = database

    def _rows(self, statement: TextClause, parameters: dict[str, Any]) -> list[Mapping[str, Any]]:
        # Every statement supplied here is a fixed reviewed wrapper expression
        # below. Normal denied results commit, preserving outer attempt budgets.
        with self._database._engine.begin() as connection:
            return [dict(row) for row in connection.execute(statement, parameters).mappings().all()]

    def now(self) -> datetime:
        rows = self._rows(text("SELECT pg_catalog.clock_timestamp() AS now"), {})
        value = rows[0]["now"]
        if not isinstance(value, datetime) or value.tzinfo is None:
            raise ValueError("Invalid database clock")
        return value

    def start(
        self,
        transaction_id: UUID,
        binder: bytes,
        state: bytes,
        nonce: bytes,
        challenge: str,
        ciphertext: bytes,
        invitation: bytes | None,
        destination: str,
        expires_at: datetime,
    ) -> StartResult:
        row = self._rows(
            text(
                "SELECT * FROM identity.start_web_login(CAST(:id AS uuid),CAST(:binder AS bytea),"
                "CAST(:state AS bytea),CAST(:nonce AS bytea),CAST(:challenge AS text),"
                "CAST(:cipher AS bytea),'google-web',CAST(:invitation AS bytea),"
                "CAST(:destination AS text),CAST(:expiry AS timestamptz))"
            ),
            {
                "id": transaction_id,
                "binder": binder,
                "state": state,
                "nonce": nonce,
                "challenge": challenge,
                "cipher": ciphertext,
                "invitation": invitation,
                "destination": destination,
                "expiry": expires_at,
            },
        )[0]
        kind = row["result"]
        if kind not in {"ok", "invalid", "in_progress", "unavailable"}:
            raise ValueError("Invalid start result")
        if kind != "ok" and (row["id"] is not None or row["expires_at"] is not None):
            raise ValueError("Invalid start result")
        if kind == "ok" and (row["id"] != transaction_id or row["expires_at"] is None):
            raise ValueError("Invalid start result")
        return StartResult(kind, row["id"], row["expires_at"])

    def claim(self, state: bytes, binder: bytes) -> PendingLogin | None:
        rows = self._rows(
            text(
                "SELECT * FROM identity.claim_web_login(CAST(:state AS bytea),"
                "CAST(:binder AS bytea),'google-web')"
            ),
            {"state": state, "binder": binder},
        )
        if not rows:
            return None
        if len(rows) != 1:
            raise ValueError("Invalid claim result")
        row = rows[0]
        result = PendingLogin(
            row["id"],
            bytes(row["nonce_digest"]),
            bytes(row["encrypted_verifier"]),
            row["pkce_challenge"],
            row["client_config_id"],
            bytes(row["invitation_digest"]) if row["invitation_digest"] is not None else None,
            row["destination"],
        )
        if (
            not isinstance(result.id, UUID)
            or len(result.nonce_digest) != 32
            or result.client_config_id != "google-web"
            or result.destination not in {"home", "calendar", "catalog"}
        ):
            raise ValueError("Invalid claim result")
        return result

    def fail(self, transaction_id: UUID, binder: bytes) -> bool:
        row = self._rows(
            text(
                "SELECT identity.fail_web_login(CAST(:id AS uuid),CAST(:binder AS bytea)) AS result"
            ),
            {"id": transaction_id, "binder": binder},
        )[0]
        return row["result"] is True

    def finish(
        self,
        transaction_id: UUID,
        binder: bytes,
        issuer: str,
        subject: str,
        session_id: UUID,
        token: bytes,
        csrf: bytes,
    ) -> FinishResult:
        row = self._rows(
            text(
                "SELECT * FROM identity.finish_web_login(CAST(:id AS uuid),CAST(:binder AS bytea),"
                "CAST(:issuer AS text),CAST(:subject AS text),CAST(:session AS uuid),"
                "CAST(:token AS bytea),CAST(:csrf AS bytea))"
            ),
            {
                "id": transaction_id,
                "binder": binder,
                "issuer": issuer,
                "subject": subject,
                "session": session_id,
                "token": token,
                "csrf": csrf,
            },
        )[0]
        kind = row["result"]
        if kind not in {"ok", "invalid", "limited", "unavailable"}:
            raise ValueError("Invalid finish result")
        authority = (
            "user_id",
            "tenant_id",
            "session_id",
            "provisioning_state",
            "absolute_expires_at",
        )
        if kind != "ok" and any(row[key] is not None for key in authority):
            raise ValueError("Invalid finish result")
        if (row["window_end"] is not None) != (kind == "limited"):
            raise ValueError("Invalid finish result")
        return FinishResult(kind, _session(row) if kind == "ok" else None, row["window_end"])

    def resolve(self, token: bytes) -> SessionRow | None:
        rows = self._rows(
            text("SELECT * FROM identity.resolve_web_session(CAST(:token AS bytea))"),
            {"token": token},
        )
        if not rows:
            return None
        if len(rows) != 1:
            raise ValueError("Invalid session result")
        return _session(rows[0])

    def revoke(self, token: bytes) -> bool:
        return (
            self._rows(
                text("SELECT identity.revoke_web_session(CAST(:token AS bytea)) AS result"),
                {"token": token},
            )[0]["result"]
            is True
        )

    def limit(self, scope: str, key: bytes) -> LimitResult | None:
        rows = self._rows(
            text(
                "SELECT * FROM identity.consume_auth_limit("
                "CAST(:scope AS text),CAST(:key AS bytea))"
            ),
            {"scope": scope, "key": key},
        )
        if not rows:
            return None
        if len(rows) != 1 or not isinstance(rows[0]["allowed"], bool):
            raise ValueError("Invalid limit result")
        return LimitResult(rows[0]["allowed"], rows[0]["window_end"])

    def mark_ready(self, token: bytes) -> bool:
        return (
            self._rows(
                text("SELECT identity.mark_catalog_ready(CAST(:token AS bytea)) AS result"),
                {"token": token},
            )[0]["result"]
            is True
        )
