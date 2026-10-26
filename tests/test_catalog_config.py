"""Cursor configuration rejects missing/noncanonical secrets without disclosure."""

import base64

import pytest
from pydantic import ValidationError

from you_story.catalog.public import CatalogSettings


def test_catalog_key_is_required_and_hidden(monkeypatch):
    monkeypatch.delenv("YOU_STORY_CATALOG_CURSOR_KEY", raising=False)
    with pytest.raises(ValidationError):
        CatalogSettings()
    encoded = base64.urlsafe_b64encode(bytes(range(32))).rstrip(b"=").decode()
    settings = CatalogSettings(cursor_key=encoded)
    assert settings.key_bytes() == bytes(range(32))
    assert encoded not in repr(settings)
    for invalid in [encoded + "=", encoded[:-1], "!" * 43, "B" * 43]:
        with pytest.raises(ValidationError) as error:
            CatalogSettings(cursor_key=invalid)
        assert invalid not in str(error.value)
