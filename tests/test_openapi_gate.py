import pytest
from fastapi import FastAPI

from tools import export_openapi
from you_story.app import create_app


def test_hidden_route_mutation(monkeypatch: pytest.MonkeyPatch) -> None:
    app = create_app(readiness=lambda: False)
    app.add_api_route("/media", lambda: {}, include_in_schema=False)
    monkeypatch.setattr(export_openapi, "create_app", lambda **kwargs: app)
    with pytest.raises(AssertionError, match="runtime route"):
        export_openapi.contract()


def test_unapproved_method_mutation(monkeypatch: pytest.MonkeyPatch) -> None:
    app: FastAPI = create_app(readiness=lambda: False)
    app.routes[0].methods.add("POST")
    monkeypatch.setattr(export_openapi, "create_app", lambda **kwargs: app)
    with pytest.raises(AssertionError, match="route/method"):
        export_openapi.contract()


def test_registered_route_cannot_be_hidden_from_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    app = create_app(readiness=lambda: False)
    route = next(route for route in app.routes if route.path == "/logout")
    route.include_in_schema = False
    monkeypatch.setattr(export_openapi, "create_app", lambda **kwargs: app)
    with pytest.raises(AssertionError, match="HTTP surface"):
        export_openapi.contract()


def test_authorized_surface_has_only_exact_methods() -> None:
    import json

    schema = json.loads(export_openapi.contract())
    assert set(schema["paths"]) == {path for path, _ in export_openapi.EXPECTED_ROUTES}
    assert set(schema["paths"]["/auth/google/callback"]) == {"get"}
    assert set(schema["paths"]["/logout"]) == {"post"}
