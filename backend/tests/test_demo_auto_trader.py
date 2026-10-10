from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.api.dependencies import get_mt5_terminal
from backend.config.settings import Settings, get_settings
from backend.execution import demo_auto_trader as auto_trader_module
from backend.main import app


def test_auto_start_is_disabled_by_default() -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(demo_execution_enabled=False)
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/demo-execution/auto/start",
                json={"symbols": ["EURUSD"], "risk_percent": 0.25},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json()["message"] == "Demo execution is disabled in settings."


def test_worker_stops_before_market_reads_when_demo_trading_is_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BlockedDemoTerminal:
        def __init__(self, *_: object) -> None:
            pass

        def account_snapshot(self) -> SimpleNamespace:
            return SimpleNamespace(
                connected=True,
                account_available=True,
                trade_mode="demo",
                trading_allowed=False,
                error_message=None,
                positions=(),
                orders=(),
            )

        def historical_candles(self, *_: object, **__: object) -> None:
            pytest.fail("Worker must stop before reading candles when trading is blocked.")

    monkeypatch.setattr(auto_trader_module, "Mt5TerminalAdapter", BlockedDemoTerminal)

    result = auto_trader_module.DemoAutoTrader._evaluate(
        "EURUSD",
        0.25,
        Settings(demo_execution_enabled=True),
    )

    assert result["executed"] is False
    assert result["continue"] is False
    assert result["reason"] == "MT5 account does not allow trading."


def test_one_click_demo_trade_stops_before_analysis_when_trading_is_blocked() -> None:
    class BlockedDemoTerminal:
        def account_snapshot(self) -> SimpleNamespace:
            return SimpleNamespace(
                connected=True,
                account_available=True,
                trade_mode="demo",
                trading_allowed=False,
                error_message=None,
                positions=(),
                orders=(),
            )

        def historical_candles(self, *_: object, **__: object) -> None:
            pytest.fail("One-click execution must stop before reading candles when blocked.")

    app.dependency_overrides[get_settings] = lambda: Settings(demo_execution_enabled=True)
    app.dependency_overrides[get_mt5_terminal] = lambda: BlockedDemoTerminal()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/demo-execution/one-click",
                json={"symbol": "EURUSD", "risk_percent": 0.25},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["executed"] is False
    assert response.json()["reason"] == "MT5 account does not allow trading."


def test_manual_demo_trade_accepts_user_supplied_levels() -> None:
    class ManualDemoTerminal:
        def market_snapshot(self, *_: object, **__: object) -> SimpleNamespace:
            return SimpleNamespace(
                snapshot=SimpleNamespace(
                    bid=1.0950,
                    ask=1.0960,
                )
            )

        def send_market_order(
            self,
            broker_symbol: str,
            side: str,
            volume: float,
            stop_loss: float,
            take_profit: float,
            required_trade_mode: str,
            **__: object,
        ) -> SimpleNamespace:
            assert broker_symbol == "EURUSD"
            assert side == "buy"
            assert volume == 0.10
            assert stop_loss == 1.0900
            assert take_profit == 1.1100
            assert required_trade_mode == "demo"
            return SimpleNamespace(submitted=True, ticket=42, error_code=0, error_message=None)

    app.dependency_overrides[get_settings] = lambda: Settings(demo_execution_enabled=True)
    app.dependency_overrides[get_mt5_terminal] = lambda: ManualDemoTerminal()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/demo-execution/manual",
                json={
                    "symbol": "EURUSD",
                    "side": "buy",
                    "volume": 0.10,
                    "entry": 1.0960,
                    "stop_loss": 1.0900,
                    "take_profit": 1.1100,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["executed"] is True
    assert response.json()["side"] == "buy"
    assert response.json()["volume"] == 0.10
