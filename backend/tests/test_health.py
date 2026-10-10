from fastapi.testclient import TestClient

from backend.config.settings import Settings, get_settings
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


def test_capabilities_make_execution_boundary_explicit() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/capabilities")

    assert response.status_code == 200
    assert response.json()["execution_available"] is False
    assert response.json()["demo_execution_available"] is False
    assert response.json()["live_trading_available"] is False
    assert response.json()["market_data_available"] is True
    assert response.json()["news_data_available"] is False


def test_capabilities_report_enabled_demo_execution() -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(
        trading_mode="demo",
        demo_execution_enabled=True,
    )
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/capabilities")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["demo_execution_available"] is True
    assert response.json()["live_trading_available"] is False
