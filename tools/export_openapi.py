"""Generate/check the reviewed health-only contract without a database credential."""

import argparse
import json
from pathlib import Path

from you_story.app import create_app


def contract() -> str:
    app = create_app(readiness=lambda: False)
    assert len(app.routes) == 2, "Unapproved runtime route"
    assert {(route.path, frozenset(route.methods)) for route in app.routes} == {
        ("/live", frozenset({"GET"})),
        ("/ready", frozenset({"GET"})),
    }, "Unapproved runtime route/method"
    schema = app.openapi()
    assert set(schema["paths"]) == {"/live", "/ready"}, "Unapproved HTTP surface"
    for operations in schema["paths"].values():
        assert set(operations) == {"get"}, "Unapproved HTTP method"
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
