"""Generate/check the exact approved login/profile contract without credentials."""

import argparse
import json
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
}


def contract() -> str:
    app = create_app(readiness=lambda: False)
    assert len(app.routes) == len(EXPECTED_ROUTES), "Unapproved runtime route"
    assert {(route.path, frozenset(route.methods)) for route in app.routes} == EXPECTED_ROUTES, (
        "Unapproved runtime route/method"
    )
    schema = app.openapi()
    expected_paths = {path: {next(iter(methods)).lower()} for path, methods in EXPECTED_ROUTES}
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
