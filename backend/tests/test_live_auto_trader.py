from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from backend.api.dependencies import get_mt5_terminal
from backend.config.settings import Settings, get_settings
from backend.execution.live_auto_trader import LiveAutoTrader
from backend.execution.mt5_terminal import Mt5RiskContext
from backend.main import app
from backend.news.economic_calendar import EconomicEvent


def test_live_auto_start_is_blocked_before_mt5_access_when_disabled() -> None:
    class ForbiddenTerminal:
        def account_snapshot(self) -> None:
            raise AssertionError("Disabled live mode must stop before MT5 access.")

    app.dependency_overrides[get_settings] = lambda: Settings()
    app.dependency_overrides[get_mt5_terminal] = lambda: ForbiddenTerminal()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/live-execution/auto/start",
                json={
                    "symbols": ["EURUSD"],
                    "risk_percent": 0.25,
                    "confirmation": "I_UNDERSTAND_LIVE_TRADING",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json()["message"] == "Live trading is not enabled in settings."


def test_live_worker_halts_before_analysis_at_session_loss_limit() -> None:
    class DrawdownTerminal:
        def account_snapshot(self) -> object:
            return type(
                "Account",
                (),
                {
                    "connected": True,
                    "account_available": True,
                    "trade_mode": "real",
                    "trading_allowed": True,
                    "equity": 98.9,
                    "positions": (),
                    "orders": (),
                },
            )()

        def historical_candles(self, *_: object, **__: object) -> object:
            raise AssertionError("Session loss limit must stop before market analysis.")

    result = LiveAutoTrader.evaluate_once(
        "EURUSD",
        0.25,
        Settings(),
        DrawdownTerminal(),  # type: ignore[arg-type]
        starting_equity=100.0,
        orders_submitted=0,
    )

    assert result["executed"] is False
    assert result["halt"] is True
    assert result["reason"] == "Session loss limit reached."


def test_live_worker_refuses_demo_account_at_startup() -> None:
    class DemoTerminal:
        def account_snapshot(self) -> object:
            return type(
                "Account",
                (),
                {
                    "connected": True,
                    "account_available": True,
                    "trade_mode": "demo",
                    "trading_allowed": True,
                    "equity": 100.0,
                },
            )()

    with pytest.raises(ValueError, match="requires a real MT5 account"):
        LiveAutoTrader().start(
            ["EURUSD"],
            0.25,
            60,
            Settings(),
            DemoTerminal(),  # type: ignore[arg-type]
        )


def test_live_worker_blocks_xauusd_during_high_impact_usd_news() -> None:
    now = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)

    class NewsTerminal:
        def account_snapshot(self) -> object:
            return type(
                "Account",
                (),
                {
                    "connected": True,
                    "account_available": True,
                    "trade_mode": "real",
                    "trading_allowed": True,
                    "equity": 100.0,
                    "positions": (),
                    "orders": (),
                },
            )()

        def historical_candles(self, *_: object, **__: object) -> object:
            raise AssertionError("News blackout must block before technical analysis.")

    class NewsCalendar:
        def high_impact_usd_events(self, *_: object) -> tuple[EconomicEvent, ...]:
            return (EconomicEvent("CPI", "USD", "high", now + timedelta(minutes=20)),)

        @staticmethod
        def within_blackout(event_time: datetime, current_time: datetime) -> bool:
            return abs(event_time - current_time) <= timedelta(minutes=30)

    result = LiveAutoTrader.evaluate_once(
        "XAUUSD.a",
        0.25,
        Settings(),
        NewsTerminal(),  # type: ignore[arg-type]
        starting_equity=100.0,
        orders_submitted=0,
        calendar=NewsCalendar(),  # type: ignore[arg-type]
        now=now,
    )

    assert result["executed"] is False
    assert result["news_filter"] == "blackout"
    assert result["reason"] == "XAUUSD blocked near high-impact USD news: CPI."


def test_live_worker_fails_closed_for_xauusd_without_calendar_feed() -> None:
    class NewsTerminal:
        def account_snapshot(self) -> object:
            return type(
                "Account",
                (),
                {
                    "connected": True,
                    "account_available": True,
                    "trade_mode": "real",
                    "trading_allowed": True,
                    "equity": 100.0,
                    "positions": (),
                    "orders": (),
                },
            )()

        def historical_candles(self, *_: object, **__: object) -> object:
            raise AssertionError("Missing calendar feed must block before technical analysis.")

    result = LiveAutoTrader.evaluate_once(
        "XAUUSD",
        0.25,
        Settings(economic_calendar_url=None),
        NewsTerminal(),  # type: ignore[arg-type]
        starting_equity=100.0,
        orders_submitted=0,
        now=datetime(2026, 9, 30, 12, 0, tzinfo=UTC),
    )

    assert result["executed"] is False
    assert result["news_filter"] == "unavailable"
    assert result["reason"] == "XAUUSD blocked: Economic calendar feed is not configured."


def test_manual_live_trade_accepts_user_supplied_levels() -> None:
    class ManualLiveTerminal:
        def market_snapshot(self, *_: object, **__: object) -> object:
            return type(
                "Quote",
                (),
                {"snapshot": type("Snapshot", (), {"bid": 1.0950, "ask": 1.0960})()},
            )()

        def risk_context(self, *_: object, **__: object) -> Mt5RiskContext:
            return Mt5RiskContext(
                connected=True,
                account_available=True,
                trading_allowed=True,
                currency="USD",
                equity=10_000.0,
                entry=1.0950,
                point=0.0001,
                digits=5,
                tick_size=0.0001,
                tick_value=1.0,
                volume_min=0.01,
                volume_max=10.0,
                volume_step=0.01,
                stops_level_points=10,
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
        ) -> object:
            assert broker_symbol == "EURUSD"
            assert side == "sell"
            assert volume == 0.10
            assert stop_loss == 1.1000
            assert take_profit == 1.0900
            assert required_trade_mode == "real"
            return type(
                "Result",
                (),
                {"submitted": True, "ticket": 99, "error_code": 0, "error_message": None},
            )()

    app.dependency_overrides[get_settings] = lambda: Settings(
        trading_mode="live",
        live_trading_enabled=True,
        trading_execution_enabled=True,
        live_trading_confirmation="I_UNDERSTAND_LIVE_TRADING",
    )
    app.dependency_overrides[get_mt5_terminal] = lambda: ManualLiveTerminal()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/live-execution/manual",
                json={
                    "symbol": "EURUSD",
                    "side": "sell",
                    "volume": 0.10,
                    "entry": 1.0960,
                    "stop_loss": 1.1000,
                    "take_profit": 1.0900,
                    "confirmation": "I_UNDERSTAND_LIVE_TRADING",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["executed"] is True
    assert response.json()["side"] == "sell"
    assert response.json()["volume"] == 0.10
    assert response.json()["risk_amount"] == pytest.approx(5.0)


def test_manual_live_trade_rejects_volume_above_risk_budget_before_submission() -> None:
    class RiskLimitedTerminal:
        def market_snapshot(self, *_: object, **__: object) -> object:
            return type(
                "Quote",
                (),
                {"snapshot": type("Snapshot", (), {"bid": 1.0950, "ask": 1.0960})()},
            )()

        def risk_context(self, *_: object, **__: object) -> Mt5RiskContext:
            return Mt5RiskContext(
                connected=True,
                account_available=True,
                trading_allowed=True,
                equity=1_000.0,
                entry=1.0950,
                point=0.0001,
                tick_size=0.0001,
                tick_value=1.0,
                volume_min=0.01,
                volume_max=10.0,
                volume_step=0.01,
            )

        def send_market_order(self, *_: object, **__: object) -> object:
            raise AssertionError("Risk-rejected manual trades must not reach MT5 submission.")

    app.dependency_overrides[get_settings] = lambda: Settings(
        trading_mode="live",
        live_trading_enabled=True,
        trading_execution_enabled=True,
        live_trading_confirmation="I_UNDERSTAND_LIVE_TRADING",
    )
    app.dependency_overrides[get_mt5_terminal] = lambda: RiskLimitedTerminal()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/live-execution/manual",
                json={
                    "symbol": "EURUSD",
                    "side": "sell",
                    "volume": 0.10,
                    "risk_percent": 0.25,
                    "entry": 1.0960,
                    "stop_loss": 1.1000,
                    "take_profit": 1.0900,
                    "confirmation": "I_UNDERSTAND_LIVE_TRADING",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert "risk-approved maximum" in response.json()["message"]
