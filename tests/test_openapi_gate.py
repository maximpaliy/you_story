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
