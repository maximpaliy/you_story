"""Actual HTTPS Chromium catalog journeys through production auth, forms and SQL.

Only Google's transport is synthetic, reused from the authentication harness.
No page routes, production security headers or request authority are replaced.
"""

import logging
import re
from urllib.parse import urlencode
from uuid import UUID

import pytest
from playwright.sync_api import expect

from tests.browser.test_auth_journeys import (
    _login,
)
from tests.browser.test_auth_journeys import (
    browser as browser,
)
from tests.browser.test_auth_journeys import (
    web_application as authentication_application,
)
from you_story.migrations.runner import migrate

pytestmark = [pytest.mark.browser, pytest.mark.postgres]


@pytest.fixture(scope="module")
def catalog_application(tmp_path_factory):
    harness = authentication_application.__wrapped__(tmp_path_factory)
    application = next(harness)
    try:
        # The auth harness deliberately supports its historical 005 upgrade
        # point. This real catalog fixture applies the additive catalog revision.
        migrate(application.owner, "006_catalog")
        yield application
    finally:
        harness.close()


def _identifier(page):
    result = page.url.rsplit("/", 1)[1]
    assert str(UUID(result)) == result
    return result


def _submit(page, fixture, button, action):
    with page.expect_response(
        lambda response: (
            response.url == fixture.origin + action and response.request.method == "POST"
        )
    ) as submitted:
        page.get_by_role("button", name=button, exact=True).click()
    response = submitted.value
    assert response.status == 303, (response.status, response.text())
    headers = response.request.all_headers()
    assert headers["sec-fetch-site"] == "same-origin"
    assert headers.get("origin") in (None, fixture.origin)
    if headers.get("origin") is None:
        assert headers["referer"].startswith(fixture.origin + "/catalog")
    assert response.headers["cache-control"] == "no-store"
    page.wait_for_url(re.compile(re.escape(fixture.origin) + r"/catalog/entries/[0-9a-f-]{36}$"))
    return _identifier(page)


def _song(page, fixture, name, author, instrument="Guitar"):
    response = page.goto(fixture.origin + "/catalog/entries/new")
    assert response.status == 200
    assert response.headers["referrer-policy"] == "same-origin"
    page.get_by_label("Instrument", exact=True).select_option(label=instrument)
    page.get_by_label("Name", exact=True).fill(name)
    page.get_by_label("Author", exact=True).fill(author)
    return _submit(page, fixture, "Create song", "/catalog/entries")


def _version(page, fixture, song, name, level):
    page.goto(fixture.origin + f"/catalog/entries/{song}")
    page.get_by_role("link", name="Add version", exact=True).click()
    page.get_by_label("Name", exact=True).fill(name)
    page.get_by_label("Level", exact=True).fill(str(level))
    return _submit(page, fixture, "Create version", "/catalog/entries")


def _fragment(page, fixture, version, name):
    page.goto(fixture.origin + f"/catalog/entries/{version}")
    page.get_by_role("link", name="Add fragment", exact=True).click()
    page.get_by_label("Name", exact=True).fill(name)
    return _submit(page, fixture, "Create fragment", "/catalog/entries")


def _search(context, fixture, **filters):
    response = context.request.get(fixture.origin + "/api/v1/catalog/entries?" + urlencode(filters))
    assert response.status == 200, response.text()
    return response.json()["items"]


@pytest.mark.parametrize("instrument", ["Guitar", "Piano"])
def test_native_tree_create_edit_move_tombstone_and_breadcrumbs(
    browser, catalog_application, instrument
):
    fixture = catalog_application
    context = browser.new_context(ignore_https_errors=True)
    try:
        page = context.new_page()
        _login(page, fixture)
        song = _song(page, fixture, instrument + " journey song", "Journey Author", instrument)
        first = _version(page, fixture, song, instrument + " version one", 0)
        second = _version(page, fixture, song, instrument + " version two", 15)
        fragment = _fragment(page, fixture, first, instrument + " journey fragment")
        expect(page.get_by_text("Measured length: Unknown", exact=True)).to_be_visible()
        expect(
            page.get_by_text("Musical note count: 0 (zero may mean not yet observed)")
        ).to_be_visible()
        crumbs = page.get_by_role("navigation", name="Breadcrumbs")
        expect(crumbs.get_by_role("link", name=instrument + " journey song")).to_be_visible()
        expect(crumbs.get_by_role("link", name=instrument + " version one")).to_be_visible()

        page.get_by_role("link", name="Edit details").click()
        page.get_by_label("Measured length in seconds (optional)").fill("37")
        page.get_by_label("Musical note count").fill("128")
        _submit(page, fixture, "Save changes", f"/catalog/entries/{fragment}/edit")
        expect(page.get_by_text("Measured length: 37", exact=True)).to_be_visible()
        expect(
            page.get_by_text("Musical note count: 128 (zero may mean not yet observed)")
        ).to_be_visible()

        page.get_by_label("New parent entry ID").fill(second)
        _submit(page, fixture, "Move entry", f"/catalog/entries/{fragment}/move")
        crumbs = page.get_by_role("navigation", name="Breadcrumbs")
        expect(crumbs.get_by_role("link", name=instrument + " version two")).to_be_visible()
        expect(crumbs.get_by_role("link", name=instrument + " version one")).to_have_count(0)
        persisted = context.request.get(fixture.origin + f"/api/v1/catalog/entries/{fragment}")
        assert persisted.json()["parent_id"] == second
        assert persisted.json()["metadata"] == {"length_seconds": 37, "notes_count": 128}

        _submit(page, fixture, "Tombstone entry", f"/catalog/entries/{fragment}/tombstone")
        expect(page.get_by_text("fragment — tombstoned", exact=True)).to_be_visible()
        assert (
            context.request.get(fixture.origin + f"/api/v1/catalog/entries/{fragment}").json()[
                "state"
            ]
            == "tombstoned"
        )
        assert fragment not in {
            row["id"] for row in _search(context, fixture, text=instrument + " journey fragment")
        }
    finally:
        context.close()


def test_author_search_inheritance_after_edit_and_cross_song_move(browser, catalog_application):
    fixture = catalog_application
    context = browser.new_context(ignore_https_errors=True)
    try:
        page = context.new_page()
        _login(page, fixture)
        first_song = _song(page, fixture, "Author source song", "Alpha Search Author")
        first_version = _version(page, fixture, first_song, "Inherited version", 4)
        fragment = _fragment(page, fixture, first_version, "Inherited fragment")
        second_song = _song(page, fixture, "Author destination song", "Beta Search Author")
        second_version = _version(page, fixture, second_song, "Destination version", 5)
        rows = _search(context, fixture, author="alpha search")
        assert {row["id"] for row in rows} == {first_song, first_version, fragment}
        assert {row["id"] for row in _search(context, fixture, text="ALPHA SEARCH")} == {
            first_song,
            first_version,
            fragment,
        }
        assert [
            row["id"]
            for row in _search(
                context, fixture, author="Alpha", text="Inherited", entry_type="fragment"
            )
        ] == [fragment]
        assert _search(context, fixture, author="Beta", text="Inherited") == []

        page.goto(fixture.origin + f"/catalog/entries/{first_song}/edit")
        page.get_by_label("Author", exact=True).fill("Gamma Search Author")
        _submit(page, fixture, "Save changes", f"/catalog/entries/{first_song}/edit")
        assert _search(context, fixture, author="Alpha Search") == []
        assert {row["id"] for row in _search(context, fixture, author="Gamma Search")} == {
            first_song,
            first_version,
            fragment,
        }

        page.goto(fixture.origin + f"/catalog/entries/{fragment}")
        page.get_by_label("New parent entry ID").fill(second_version)
        _submit(page, fixture, "Move entry", f"/catalog/entries/{fragment}/move")
        assert {row["id"] for row in _search(context, fixture, author="Beta Search")} == {
            second_song,
            second_version,
            fragment,
        }
        page.goto(fixture.origin + "/catalog")
        page.get_by_label("Author", exact=True).fill("Beta Search")
        page.get_by_role("button", name="Search", exact=True).click()
        expect(page.get_by_role("link", name="Inherited fragment", exact=True)).to_be_visible()
        expect(page.get_by_role("link", name="Inherited version", exact=True)).to_have_count(0)
    finally:
        context.close()


def test_stale_native_form_cannot_overwrite_and_error_headers_stay_strict(
    browser, catalog_application
):
    fixture = catalog_application
    context = browser.new_context(ignore_https_errors=True)
    try:
        first = context.new_page()
        _login(first, fixture)
        song = _song(first, fixture, "Original concurrency name", "Concurrency Author")
        second = context.new_page()
        edit = fixture.origin + f"/catalog/entries/{song}/edit"
        first.goto(edit)
        second.goto(edit)
        first.get_by_label("Name", exact=True).fill("First committed name")
        _submit(first, fixture, "Save changes", f"/catalog/entries/{song}/edit")
        second.get_by_label("Name", exact=True).fill("Must never overwrite")
        with second.expect_response(
            lambda response: response.url == edit and response.request.method == "POST"
        ) as submitted:
            second.get_by_role("button", name="Save changes", exact=True).click()
        assert submitted.value.status == 412
        assert submitted.value.headers["referrer-policy"] == "no-referrer"
        assert submitted.value.headers["cache-control"] == "no-store"
        expect(second.get_by_role("alert")).to_have_text(
            "Catalog changed; reload before trying again"
        )
        result = context.request.get(fixture.origin + f"/api/v1/catalog/entries/{song}")
        assert result.json()["name"] == "First committed name"
    finally:
        context.close()


def test_stored_and_reflected_text_stays_escaped_in_browser_and_logs(
    browser, catalog_application, caplog
):
    fixture = catalog_application
    context = browser.new_context(ignore_https_errors=True)
    name = '<img src=x onerror="window.__catalog_name=true">'
    author = "<script>window.__catalog_author=true</script>"
    query = 'catalog-query-canary-11-<svg onload="window.__catalog_query=true">'
    cursor = "catalog-cursor-canary-11-private"
    caplog.set_level(logging.INFO)
    error_logger = logging.getLogger("uvicorn.error")
    error_logger.addHandler(caplog.handler)
    try:
        logging.getLogger("you_story.http").info("catalog-browser-log-positive-control")
        error_logger.error("catalog-browser-error-sink-positive-control")
        page = context.new_page()
        _login(page, fixture)
        song = _song(page, fixture, name, author)
        expect(page.get_by_role("heading", level=1)).to_have_text(name)
        expect(page.get_by_text("Author: " + author, exact=True)).to_be_visible()
        assert page.locator("img, script, svg").count() == 0
        page.goto(fixture.origin + f"/catalog/entries/{song}/edit")
        expect(page.get_by_label("Name", exact=True)).to_have_value(name)
        expect(page.get_by_label("Author", exact=True)).to_have_value(author)
        response = page.goto(fixture.origin + "/catalog?" + urlencode({"text": query}))
        assert response.status == 200
        assert response.headers["referrer-policy"] == "same-origin"
        expect(page.get_by_label("Song, version, fragment or author")).to_have_value(query)
        assert page.locator("img, script, svg").count() == 0
        assert page.evaluate(
            "[window.__catalog_name,window.__catalog_author,window.__catalog_query]"
            ".every(value => value === undefined)"
        )
        # A native same-origin search carries the previous private query in
        # Referer. Exercise the actual enabled server/app sinks at INFO level.
        with page.expect_response(
            lambda result: "/catalog?" in result.url and result.request.method == "GET"
        ) as searched:
            page.get_by_role("button", name="Search", exact=True).click()
        referer = searched.value.request.all_headers().get("referer")
        assert referer is not None and "catalog-query-canary-11" in referer
        invalid_cursor = page.goto(
            fixture.origin + "/catalog?" + urlencode({"text": query, "cursor": cursor})
        )
        assert invalid_cursor.status == 422
        assert "catalog-browser-log-positive-control" in caplog.text
        assert "catalog-browser-error-sink-positive-control" in caplog.text
        for canary in [name, author, query, cursor, referer]:
            assert canary not in caplog.text
    finally:
        error_logger.removeHandler(caplog.handler)
        context.close()


def test_catalog_form_policy_is_exact_and_suppresses_cross_origin_referrer(
    browser, catalog_application
):
    fixture = catalog_application
    context = browser.new_context(ignore_https_errors=True)
    try:
        page = context.new_page()
        _login(page, fixture)
        song = _song(page, fixture, "Browser header policy song", "Header Author")
        for path in [
            "/catalog",
            "/catalog?text=private-query-referrer-canary-11",
            "/catalog/entries/new",
            f"/catalog/entries/{song}",
            f"/catalog/entries/{song}/edit",
        ]:
            response = page.goto(fixture.origin + path)
            assert response.status == 200
            assert response.headers["referrer-policy"] == "same-origin"
            assert response.headers["cache-control"] == "no-store"
            policy = response.headers["content-security-policy"]
            assert "form-action 'self';" in policy
            assert "accounts.google.com" not in policy

        for path in [
            "/catalog/entries/not-a-uuid",
            "/catalog/entries/00000000-0000-4000-8000-000000000000",
            "/api/v1/catalog",
        ]:
            response = context.request.get(fixture.origin + path)
            assert response.headers["referrer-policy"] == "no-referrer"
            assert response.headers["cache-control"] == "no-store"

        page.goto(fixture.origin + "/catalog?text=private-query-referrer-canary-11")
        cdp = context.new_cdp_session(page)
        observed_referrers = []

        def external_request(event):
            # Intercept only the external destination after Chromium has applied
            # the real page's referrer policy. No production response is changed.
            headers = {key.lower(): value for key, value in event["request"]["headers"].items()}
            observed_referrers.append(headers.get("referer"))
            cdp.send(
                "Fetch.fulfillRequest",
                {
                    "requestId": event["requestId"],
                    "responseCode": 200,
                    "responseHeaders": [{"name": "Content-Type", "value": "text/html"}],
                    "body": "",
                },
            )

        cdp.on("Fetch.requestPaused", external_request)
        cdp.send(
            "Fetch.enable",
            {"patterns": [{"urlPattern": "https://attacker.invalid/*", "requestStage": "Request"}]},
        )
        page.evaluate("window.location.href = 'https://attacker.invalid/referrer-check'")
        page.wait_for_url("https://attacker.invalid/referrer-check")
        assert observed_referrers == [None]
        cdp.send("Fetch.disable")
        cdp.detach()
    finally:
        context.close()


def test_real_json_mutations_preconditions_and_cross_tenant_api_isolation(
    browser, catalog_application
):
    fixture = catalog_application
    first, second = [browser.new_context(ignore_https_errors=True) for _ in range(2)]
    base = fixture.origin + "/api/v1/catalog"
    try:
        first_page, second_page = first.new_page(), second.new_page()
        _login(first_page, fixture, "browser-a")
        _login(second_page, fixture, "browser-b")

        def credentials(page):
            page.goto(fixture.origin + "/catalog/entries/new")
            return {
                "Origin": fixture.origin,
                "Sec-Fetch-Site": "same-origin",
                "Content-Type": "application/json",
                "X-CSRF-Token": page.locator('input[name="csrf"]').input_value(),
            }

        first_headers, second_headers = credentials(first_page), credentials(second_page)
        initial_catalog = first.request.get(base)
        catalog_tag = initial_catalog.headers["etag"]
        catalog_version = initial_catalog.json()["version"]
        instrument = next(
            item["id"]
            for item in first.request.get(base + "/references").json()["instruments"]
            if item["key"] == "guitar"
        )

        def mutate(method, suffix, payload, *, context=first, headers=None, tag=None):
            selected = dict(headers or first_headers)
            if tag is not None:
                selected["If-Match"] = tag
            return context.request.fetch(
                base + suffix, method=method, headers=selected, data=payload
            )

        def create(kind, name, metadata, parent=None):
            nonlocal catalog_tag, catalog_version
            payload = {
                "source_key": "yousician",
                "instrument_id": instrument,
                "entry_type": kind,
                "name": name,
                "metadata": metadata,
                "parent_entry_id": parent,
            }
            response = mutate("POST", "/entries", payload, tag=catalog_tag)
            assert response.status == 201, response.text()
            result = response.json()
            assert result["catalog"]["version"] == catalog_version + 1
            assert result["entry"]["version"] == 1
            assert (
                response.headers["location"] == "/api/v1/catalog/entries/" + result["entry"]["id"]
            )
            assert response.headers["etag"] == (
                f'"catalog:{result["catalog"]["id"]}:{result["catalog"]["version"]}"'
            )
            catalog_tag = response.headers["etag"]
            catalog_version = result["catalog"]["version"]
            return result["entry"]

        song = create("song", "JSON API song", {"author": "JSON API author"})
        first_version = create("version", "JSON version one", {"level": 0}, song["id"])
        second_version = create("version", "JSON version two", {"level": 15}, song["id"])
        fragment = create("fragment", "JSON fragment", {}, first_version["id"])
        assert fragment["metadata"] == {"length_seconds": None, "notes_count": 0}
        detail = first.request.get(base + "/entries/" + fragment["id"])
        assert detail.headers["etag"] == f'"entry:{fragment["id"]}:1"'
        original_tag = catalog_tag
        updated = mutate(
            "PATCH",
            "/entries/" + fragment["id"],
            {"expected_entry_version": 1, "metadata": {"length_seconds": 42, "notes_count": 16}},
            tag=catalog_tag,
        )
        assert updated.status == 200, updated.text()
        assert updated.json()["entry"]["version"] == 2
        assert updated.json()["catalog"]["version"] == catalog_version + 1
        catalog_tag = updated.headers["etag"]
        catalog_version = updated.json()["catalog"]["version"]

        for tag, payload, status in [
            (original_tag, {"expected_entry_version": 1, "name": "Stale replacement"}, 412),
            (None, {"expected_entry_version": 2, "name": "Missing catalog version"}, 428),
            (catalog_tag, {"name": "Missing entry version"}, 428),
            (detail.headers["etag"], {"expected_entry_version": 2, "name": "Wrong ETag kind"}, 422),
            (catalog_tag, {"expected_entry_version": 2, "tenant_id": song["id"]}, 422),
        ]:
            denied = mutate("PATCH", "/entries/" + fragment["id"], payload, tag=tag)
            assert denied.status == status, denied.text()
            assert denied.headers["cache-control"] == "no-store"
        assert first.request.get(base).headers["etag"] == catalog_tag
        assert (
            first.request.get(base + "/entries/" + fragment["id"]).json()["name"] == "JSON fragment"
        )

        moved = mutate(
            "POST",
            "/entries/" + fragment["id"] + "/move",
            {"expected_entry_version": 2, "new_parent_entry_id": second_version["id"]},
            tag=catalog_tag,
        )
        assert moved.status == 200, moved.text()
        assert moved.json()["entry"]["parent_id"] == second_version["id"]
        assert moved.json()["entry"]["version"] == 3
        assert moved.json()["catalog"]["version"] == catalog_version + 1
        catalog_tag = moved.headers["etag"]
        catalog_version = moved.json()["catalog"]["version"]
        assert [
            item["id"]
            for item in first.request.get(
                base + "/entries/" + fragment["id"] + "/ancestors"
            ).json()["items"]
        ] == [song["id"], second_version["id"]]

        other_tag = second.request.get(base).headers["etag"]
        absent = "00000000-0000-4000-8000-000000000000"
        for suffix in ["", "/children", "/ancestors"]:
            failures = [
                second.request.get(base + "/entries/" + target + suffix)
                for target in [fragment["id"], absent]
            ]
            assert [response.status for response in failures] == [404, 404]
            errors = [response.json()["error"] for response in failures]
            assert errors[0]["code"] == errors[1]["code"] == "resource_not_found"
            assert errors[0]["message"] == errors[1]["message"]
            assert all(response.headers["cache-control"] == "no-store" for response in failures)
        for method, suffix, payload in [
            ("PATCH", "", {"expected_entry_version": 3, "name": "Foreign replacement"}),
            (
                "POST",
                "/move",
                {"expected_entry_version": 3, "new_parent_entry_id": first_version["id"]},
            ),
            ("POST", "/tombstone", {"expected_entry_version": 3}),
        ]:
            for target in [fragment["id"], absent]:
                response = mutate(
                    method,
                    "/entries/" + target + suffix,
                    payload,
                    context=second,
                    headers=second_headers,
                    tag=other_tag,
                )
                assert response.status == 404, response.text()
                assert response.json()["error"]["code"] == "resource_not_found"
        foreign_filter = second.request.get(
            base + "/entries?" + urlencode({"ancestor_id": song["id"]})
        )
        assert foreign_filter.status == 404
        assert _search(second, fixture, author="JSON API author") == []
        forbidden_assignment = mutate(
            "POST",
            "/entries",
            {
                "source_key": "yousician",
                "instrument_id": instrument,
                "entry_type": "song",
                "name": "Forbidden sharing",
                "metadata": {},
                "visibility": "public",
            },
            tag=catalog_tag,
        )
        assert forbidden_assignment.status == 422
        assert first.request.get(base).headers["etag"] == catalog_tag
        assert second.request.get(base).headers["etag"] == other_tag

        tombstoned = mutate(
            "POST",
            "/entries/" + fragment["id"] + "/tombstone",
            {"expected_entry_version": 3},
            tag=catalog_tag,
        )
        assert tombstoned.status == 200, tombstoned.text()
        assert tombstoned.json()["entry"]["version"] == 4
        assert tombstoned.json()["entry"]["state"] == "tombstoned"
        assert tombstoned.json()["catalog"]["version"] == catalog_version + 1
        assert first.request.get(base + "/entries/" + fragment["id"]).status == 200
        assert second.request.get(base + "/entries/" + fragment["id"]).status == 404
    finally:
        first.close()
        second.close()
