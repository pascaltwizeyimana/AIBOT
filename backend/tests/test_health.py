from fastapi.testclient import TestClient

from backend.main import app


def test_health_reports_safe_default_mode() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "environment": "development",
        "trading_mode": "demo",
        "live_trading_enabled": False,
    }


def test_unknown_route_uses_safe_error_envelope() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/not-a-route", headers={"X-Request-ID": "test-request"})

    assert response.status_code == 404
    assert response.headers["X-Request-ID"] == "test-request"
    assert response.json() == {
        "code": "http_error",
        "message": "Not Found",
        "request_id": "test-request",
        "details": None,
    }
