"""The default ASGI server access logger must not retain callback credentials."""

import logging

from fastapi.testclient import TestClient

from you_story.app import create_app


def test_access_record_canaries_are_suppressed_and_safe_events_observed(caplog) -> None:
    app = create_app(readiness=lambda: True)
    with caplog.at_level(logging.INFO):
        logging.getLogger("you_story.http").info("capture-positive-control")
        logging.getLogger("uvicorn.access").info(
            "GET /auth/google/callback?code=code-canary&state=state-canary"
        )
        with TestClient(app) as client:
            response = client.get("/auth/google/callback?code=provider-canary&state=state-canary")
    assert "capture-positive-control" in caplog.text
    assert response.status_code == 503
    assert "code-canary" not in caplog.text
    assert "state-canary" not in caplog.text
    assert "provider-canary" not in caplog.text
    assert "provider-canary" not in response.text


def test_origin_and_cookie_security_are_documented_in_generated_contract() -> None:
    schema = create_app(readiness=lambda: False).openapi()
    assert schema["components"]["securitySchemes"]["SessionCookie"] == {
        "type": "apiKey",
        "in": "cookie",
        "name": "__Host-you_story_session",
        "description": "Opaque browser session; request fields cannot select identity or tenant.",
    }
    own = schema["components"]["schemas"]["OwnProfile"]
    assert set(own["properties"]) == {"user_id", "provisioning_state"}
    assert own["additionalProperties"] is False
