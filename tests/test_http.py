from uuid import UUID

from fastapi.testclient import TestClient

from you_story.app import create_app


def test_health_and_correlation() -> None:
    app = create_app(readiness=lambda: True)
    with TestClient(app) as client:
        live = client.get("/live", headers={"X-Correlation-ID": "attacker-sentinel"})
        assert live.status_code == 200
        assert live.json() == {"status": "live"}
        UUID(live.headers["X-Correlation-ID"])
        assert live.headers["Cache-Control"] == "no-store"
        assert client.get("/ready").json() == {"status": "ready"}
        assert client.get("/live").headers["X-Correlation-ID"] != live.headers["X-Correlation-ID"]


def test_safe_error_envelopes_and_no_product_routes() -> None:
    with TestClient(create_app(readiness=lambda: False)) as client:
        cases = [
            ("GET", "/ready", 503, "not_ready"),
            ("GET", "/login", 404, "not_found"),
            ("POST", "/live", 405, "method_not_allowed"),
            ("GET", "/openapi.json", 404, "not_found"),
            ("GET", "/docs", 404, "not_found"),
            ("GET", "/redoc", 404, "not_found"),
        ]
        for method, path, status, code in cases:
            response = client.request(method, path)
            assert response.status_code == status
            if status == 405:
                assert response.headers["Allow"] == "GET"
            error = response.json()["error"]
            assert error["code"] == code
            assert error["correlation_id"] == response.headers["X-Correlation-ID"]
            assert set(error) == {"code", "message", "correlation_id"}


def test_unexpected_exception_is_sanitized() -> None:
    def broken() -> bool:
        raise ValueError("secret-token tenant-id SQL postgres-password")

    with TestClient(create_app(readiness=broken), raise_server_exceptions=False) as client:
        response = client.get("/ready")
        assert response.status_code == 500
        assert response.json()["error"]["code"] == "internal_error"
        assert "secret" not in response.text
        assert response.json()["error"]["correlation_id"] == response.headers["X-Correlation-ID"]


def test_openapi_health_only() -> None:
    schema = create_app(readiness=lambda: True).openapi()
    assert set(schema["paths"]) == {"/live", "/ready"}
    assert all(set(operation) == {"get"} for operation in schema["paths"].values())
