from dataclasses import FrozenInstanceError
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from you_story.shared.config import Settings
from you_story.shared.context import ActorContext
from you_story.shared.database import Database, _reset_connection
from you_story.shared.primitives import new_id, utc_now


def test_configuration_runtime_only_and_secret_errors() -> None:
    sentinel = "private-password-sentinel"
    settings = Settings(database_url=f"postgresql+psycopg://app_runtime:{sentinel}@localhost/db")
    assert sentinel not in repr(settings)
    for url in [f"postgresql+psycopg://app_owner:{sentinel}@host/db", "sqlite://", sentinel]:
        with pytest.raises(ValidationError) as error:
            Settings(database_url=url)
        assert sentinel not in str(error.value)


def test_technical_primitives_and_no_actor_issuer() -> None:
    assert new_id() != new_id()
    assert utc_now().utcoffset().total_seconds() == 0
    with pytest.raises(TypeError):
        ActorContext()
    actor = object.__new__(ActorContext)
    object.__setattr__(actor, "tenant_id", uuid4())
    with pytest.raises(FrozenInstanceError):
        actor.tenant_id = uuid4()


def test_pool_reset_rollback_autocommit_restore() -> None:
    connection = MagicMock()
    connection.autocommit = False
    _reset_connection(connection)
    connection.rollback.assert_called_once()
    connection.cursor.return_value.__enter__.return_value.execute.assert_called_once_with(
        "RESET app.tenant_id"
    )
    assert connection.autocommit is False


def test_pool_reset_failure_retires_and_sanitizes(caplog: pytest.LogCaptureFixture) -> None:
    connection = MagicMock()
    connection.rollback.side_effect = RuntimeError("tenant-secret-sentinel")
    record = MagicMock()
    state = MagicMock(terminate_only=False)
    Database._reset(connection, record, state)
    record.invalidate.assert_called_once()
    assert "tenant-secret-sentinel" not in caplog.text
    assert caplog.records[-1].category == "cleanup"
    assert caplog.records[-1].operation == "checkin_retire"
