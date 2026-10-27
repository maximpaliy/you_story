"""Delivery boundary tests: real parser/templates/routes, synthetic public ports."""

from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from you_story.delivery.catalog import register_catalog_routes

CAT = "10000000-0000-0000-0000-000000000001"
ENTRY = "10000000-0000-0000-0000-000000000002"
INSTRUMENT = "10000000-0000-0000-0000-000000000003"


class Identity:
    valid = True

    def resolve_session(self, cookie):
        return SimpleNamespace(actor=object()) if self.valid else None

    def csrf_token(self, session):
        return "csrf"

    def validate_csrf(self, session, token):
        return token == "csrf"


class Catalog:
    calls = 0
    values = None

    def get_catalog(self, actor):
        return {"id": CAT, "version": 1}

    def references(self, actor):
        return {
            "sources": [],
            "instruments": [{"id": INSTRUMENT, "key": "guitar", "name": "Guitar"}],
        }

    def get_entry(self, actor, entry_id):
        return {
            "id": ENTRY,
            "catalog_id": CAT,
            "parent_id": None,
            "source_key": "yousician",
            "source_definition_version": 1,
            "instrument_id": INSTRUMENT,
            "type": "song",
            "name": "<script>name</script>",
            "metadata": {"author": "<img src=x onerror=alert(1)>"},
            "state": "active",
            "version": 1,
        }

    def create(self, actor, expected_catalog, values):
        self.calls += 1
        self.values = values
        assert expected_catalog == (UUID(CAT), 1)
        return {"catalog": {"id": CAT, "version": 2}, "entry": self.get_entry(actor, None)}

    def search(self, actor, filters, size=50, cursor=None):
        self.values = filters
        return {"items": [self.get_entry(actor, None)], "next_cursor": None}

    def browse_roots(self, actor, size=50, cursor=None):
        return self.search(actor, {}, size, cursor)

    def ancestors(self, actor, entry_id):
        return {"items": []}

    def children(self, actor, entry_id, size=50, cursor=None):
        return {"items": [], "next_cursor": None}


@pytest.fixture
def adapter():
    app = FastAPI()
    identity, catalog = Identity(), Catalog()

    @app.middleware("http")
    async def correlation(request: Request, call_next):
        request.state.correlation_id = "fixed-correlation"
        return await call_next(request)

    register_catalog_routes(app, catalog, identity, canonical_origin="https://testserver")
    with TestClient(app, base_url="https://testserver") as client:
        yield client, identity, catalog


def headers():
    return {
        "Origin": "https://testserver",
        "X-CSRF-Token": "csrf",
        "If-Match": f'"catalog:{CAT}:1"',
    }


def test_api_create_and_etag(adapter):
    client, _, catalog = adapter
    response = client.post("/api/v1/catalog/entries", json={"name": "Song"}, headers=headers())
    assert response.status_code == 201
    assert response.headers["etag"] == f'"catalog:{CAT}:2"'
    assert response.headers["location"].endswith(ENTRY)
    assert catalog.calls == 1


@pytest.mark.parametrize(
    "raw",
    [
        '{"name":"x","name":"y"}',
        '{"metadata":{"author":"x","author":"y"}}',
        '{"name":NaN}',
        "[1,2]",
    ],
)
def test_json_ambiguity_rejected_before_command(adapter, raw):
    client, _, catalog = adapter
    response = client.post(
        "/api/v1/catalog/entries",
        content=raw,
        headers={**headers(), "Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert catalog.calls == 0


def test_auth_and_provenance_before_mutation(adapter):
    client, identity, catalog = adapter
    identity.valid = False
    assert client.post("/api/v1/catalog/entries", json={}, headers=headers()).status_code == 401
    assert client.get("/catalog", follow_redirects=False).headers["location"] == "/login"
    identity.valid = True
    assert (
        client.post(
            "/api/v1/catalog/entries",
            json={},
            headers={**headers(), "Origin": "https://evil.invalid"},
        ).status_code
        == 403
    )
    assert catalog.calls == 0


@pytest.mark.parametrize(
    "match,status", [(None, 428), ('W/"x"', 422), ("*", 422), (f'"entry:{ENTRY}:1"', 422)]
)
def test_etag_shape_required(adapter, match, status):
    client, _, catalog = adapter
    values = headers()
    if match is None:
        del values["If-Match"]
    else:
        values["If-Match"] = match
    assert client.post("/api/v1/catalog/entries", json={}, headers=values).status_code == status
    assert catalog.calls == 0


def test_search_author_filters_and_repeated_queries(adapter):
    client, _, catalog = adapter
    assert client.get("/api/v1/catalog/entries?author=Artist&text=Song").status_code == 200
    assert catalog.values == {"author": "Artist", "text": "Song"}
    assert client.get("/api/v1/catalog/entries?author=x&author=y").status_code == 422
    assert client.get("/api/v1/catalog/entries?owner=x").status_code == 422


def test_html_escapes_stored_name_and_author(adapter):
    client, _, _ = adapter
    response = client.get(f"/catalog/entries/{ENTRY}")
    assert response.status_code == 200
    assert "<script>name</script>" not in response.text
    assert "&lt;script&gt;name&lt;/script&gt;" in response.text
    assert "<img src=x" not in response.text
    assert "&lt;img src=x" in response.text


def test_native_form_create(adapter):
    client, _, catalog = adapter
    response = client.post(
        "/catalog/entries",
        data={
            "csrf": "csrf",
            "expected_catalog_version": "1",
            "source_key": "yousician",
            "entry_type": "song",
            "instrument_id": INSTRUMENT,
            "name": "Example",
            "author": "Artist",
        },
        headers={"Origin": "https://testserver"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert catalog.values["metadata"] == {"author": "Artist"}
    assert response.headers["location"].endswith(ENTRY)


def test_body_limit_and_csrf_no_command(adapter):
    client, _, catalog = adapter
    response = client.post(
        "/api/v1/catalog/entries",
        content=b"x" * 16385,
        headers={**headers(), "Content-Type": "application/json"},
    )
    assert response.status_code == 413
    response = client.post(
        "/api/v1/catalog/entries", json={}, headers={**headers(), "X-CSRF-Token": "wrong"}
    )
    assert response.status_code == 403
    assert catalog.calls == 0


def test_large_child_list_links_to_paginated_descendant_browse(adapter, monkeypatch):
    client, _, catalog = adapter
    entry = catalog.get_entry(None, None)
    monkeypatch.setattr(
        catalog, "children", lambda *args: {"items": [entry] * 100, "next_cursor": "child-cursor"}
    )
    seen = []

    def search(actor, filters, size=50, cursor=None):
        seen.append((filters, cursor))
        return {"items": [entry], "next_cursor": "search-cursor" if cursor is None else None}

    monkeypatch.setattr(catalog, "search", search)
    response = client.get(f"/catalog/entries/{ENTRY}")
    assert response.status_code == 200
    assert "Showing the first 100 children." in response.text
    assert f'href="/catalog?ancestor_id={ENTRY}"' in response.text
    assert "Browse all descendants (paginated)" in response.text
    first = client.get(f"/catalog?ancestor_id={ENTRY}")
    assert first.status_code == 200
    assert f"/catalog?ancestor_id={ENTRY}&amp;cursor=search-cursor" in first.text
    final = client.get(f"/catalog?ancestor_id={ENTRY}&cursor=search-cursor")
    assert final.status_code == 200
    assert "Next page" not in final.text
    assert seen == [({"ancestor_id": ENTRY}, None), ({"ancestor_id": ENTRY}, "search-cursor")]


def test_packaged_schema_matches_approved_candidate():
    import json
    from pathlib import Path

    candidate = json.loads(Path("docs/work/issue-11/openapi.candidate.json").read_text())
    packaged = json.loads(Path("src/you_story/delivery/catalog-contract.json").read_text())
    assert packaged["paths"] == {
        key: value for key, value in candidate["paths"].items() if key.startswith("/api/v1/catalog")
    }
    assert packaged["components"] == {
        key: value
        for key, value in candidate["components"]["schemas"].items()
        if key.startswith("Catalog")
    }
