from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from backend.api.dependencies import get_mt5_terminal
from backend.execution.mt5_terminal import Mt5SymbolDiscovery
from backend.main import app
from backend.market.models import MarketDataResult, MarketSnapshot


def test_market_snapshot_rejects_blank_symbol_before_calling_provider() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/market/snapshots/%20%20")

    assert response.status_code == 422
    assert response.json()["code"] == "http_error"


def test_market_routes_report_unavailable_provider_without_fake_data() -> None:
    class UnavailableTerminal:
        def discover_symbols(self) -> Mt5SymbolDiscovery:
            return Mt5SymbolDiscovery(
                connected=False,
                symbols_available=False,
                error_message="MT5 is unavailable.",
            )

    app.dependency_overrides[get_mt5_terminal] = UnavailableTerminal
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/market/symbols")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["code"] == "http_error"


def test_market_snapshot_rejects_stale_quote() -> None:
    class StaleTerminal:
        def market_snapshot(self, _: str) -> MarketDataResult:
            return MarketDataResult(
                connected=True,
                snapshot=MarketSnapshot(
                    broker_symbol="EURUSDm",
                    quote_available=True,
                    market_status="active",
                    observed_at=datetime.now(UTC) - timedelta(seconds=11),
                    bid=1.1,
                    ask=1.1001,
                ),
            )

    app.dependency_overrides[get_mt5_terminal] = StaleTerminal
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/market/snapshots/EURUSDm")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["message"] == "MT5 returned a stale quote."
