"""Generate/check the exact approved login/profile contract without credentials."""

import argparse
import json
from collections import Counter
from pathlib import Path

from you_story.app import create_app

EXPECTED_ROUTES = {
    ("/live", frozenset({"GET"})),
    ("/ready", frozenset({"GET"})),
    ("/login", frozenset({"GET"})),
    ("/auth/google/start", frozenset({"POST"})),
    ("/auth/google/callback", frozenset({"GET"})),
    ("/", frozenset({"GET"})),
    ("/profile", frozenset({"GET"})),
    ("/api/v1/profile", frozenset({"GET"})),
    ("/logout", frozenset({"POST"})),
    ("/api/v1/catalog", frozenset({"GET"})),
    ("/api/v1/catalog/references", frozenset({"GET"})),
    ("/api/v1/catalog/entries", frozenset({"GET", "POST"})),
    ("/api/v1/catalog/entries/{entry_id}", frozenset({"GET", "PATCH"})),
    ("/api/v1/catalog/entries/{entry_id}/children", frozenset({"GET"})),
    ("/api/v1/catalog/entries/{entry_id}/ancestors", frozenset({"GET"})),
    ("/api/v1/catalog/entries/{entry_id}/move", frozenset({"POST"})),
    ("/api/v1/catalog/entries/{entry_id}/tombstone", frozenset({"POST"})),
    ("/catalog", frozenset({"GET"})),
    ("/catalog/entries/new", frozenset({"GET"})),
    ("/catalog/entries/{entry_id}", frozenset({"GET"})),
    ("/catalog/entries/{entry_id}/edit", frozenset({"GET", "POST"})),
    ("/catalog/entries", frozenset({"POST"})),
    ("/catalog/entries/{entry_id}/move", frozenset({"POST"})),
    ("/catalog/entries/{entry_id}/tombstone", frozenset({"POST"})),
}


def contract() -> str:
    app = create_app(readiness=lambda: False)
    expected = Counter((path, method) for path, methods in EXPECTED_ROUTES for method in methods)
    actual = Counter((route.path, method) for route in app.routes for method in route.methods)
    assert len(app.routes) == sum(expected.values()), "Unapproved runtime route"
    assert actual == expected, "Unapproved runtime route/method"
    schema = app.openapi()
    expected_paths: dict[str, set[str]] = {}
    for path, methods in EXPECTED_ROUTES:
        expected_paths.setdefault(path, set()).update(method.lower() for method in methods)
    assert set(schema["paths"]) == set(expected_paths), "Unapproved HTTP surface"
    for path, operations in schema["paths"].items():
        assert set(operations) == expected_paths[path], "Unapproved HTTP method"
    return json.dumps(schema, sort_keys=True, indent=2) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    file = Path("docs/api/openapi.json")
    generated = contract()
    if args.check:
        if not file.exists() or file.read_text() != generated:
            raise SystemExit("OpenAPI differs; regenerate and review the contract")
    else:
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(generated)


if __name__ == "__main__":
    main()
