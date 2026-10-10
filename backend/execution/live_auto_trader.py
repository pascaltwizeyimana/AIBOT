"""Explicitly armed, bounded MT5 real-account automation."""

from __future__ import annotations

import threading
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from backend.config.settings import Settings
from backend.execution.mt5_terminal import Mt5TerminalAdapter
from backend.market.models import CandleSeries, Timeframe
from backend.news.economic_calendar import EconomicCalendarClient, EconomicCalendarError
from backend.risk.management import calculate_position_risk, calculate_risk_plan
from backend.signals.deterministic import CandidateDecision, DeterministicAnalyzer


class LiveAutoTrader:
    """Run a manually armed, bounded live signal loop with account-level risk checks."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._state: dict[str, Any] = {"running": False, "status": "disarmed"}

    def status(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._state)

    def start(
        self,
        symbols: list[str],
        risk_percent: float,
        interval_seconds: int,
        settings: Settings,
        terminal: Mt5TerminalAdapter,
    ) -> dict[str, Any]:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                raise ValueError("Live automation is already running.")
            account = terminal.account_snapshot()
            if not account.connected or not account.account_available:
                raise ValueError(account.error_message or "MT5 account unavailable.")
            if account.trade_mode != "real":
                raise ValueError("Live automation requires a real MT5 account.")
            if not account.trading_allowed:
                raise ValueError("MT5 account does not allow trading.")
            if account.equity is None or account.equity <= 0:
                raise ValueError("Live account equity is unavailable.")

            self._stop = threading.Event()
            self._state = {
                "running": True,
                "status": "armed",
                "symbols": symbols,
                "risk_percent": risk_percent,
                "interval_seconds": interval_seconds,
                "starting_equity": account.equity,
                "evaluations": 0,
                "orders_submitted": 0,
                "last_result": None,
                "last_error": None,
            }
            self._thread = threading.Thread(
                target=self._run,
                args=(symbols, risk_percent, interval_seconds, settings, terminal, account.equity),
                daemon=True,
                name="mt5-live-auto-trader",
            )
            self._thread.start()
            return dict(self._state)

    def stop(self) -> dict[str, Any]:
        self._stop.set()
        with self._lock:
            if self._state.get("running"):
                self._state["status"] = "stopping"
            return dict(self._state)

    def _run(
        self,
        symbols: list[str],
        risk_percent: float,
        interval_seconds: int,
        settings: Settings,
        terminal: Mt5TerminalAdapter,
        starting_equity: float,
    ) -> None:
        try:
            for index in range(100):
                if self._stop.is_set():
                    break
                result = self.evaluate_once(
                    symbols[index % len(symbols)],
                    risk_percent,
                    settings,
                    terminal,
                    starting_equity,
                    self.status().get("orders_submitted", 0),
                )
                with self._lock:
                    self._state["evaluations"] += 1
                    self._state["last_result"] = result
                    self._state["status"] = "running"
                    if result.get("executed"):
                        self._state["orders_submitted"] += 1
                    submitted = self._state["orders_submitted"]
                if result.get("halt") or submitted >= settings.live_auto_max_orders:
                    break
                if self._stop.wait(interval_seconds):
                    break
        except Exception as exc:
            with self._lock:
                self._state["last_error"] = type(exc).__name__
                self._state["status"] = "error"
        finally:
            with self._lock:
                self._state["running"] = False
                if self._state["status"] != "error":
                    self._state["status"] = "disarmed"

    @staticmethod
    def evaluate_once(
        symbol: str,
        risk_percent: float,
        settings: Settings,
        terminal: Mt5TerminalAdapter,
        starting_equity: float,
        orders_submitted: int,
        calendar: EconomicCalendarClient | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Evaluate a symbol once, failing closed before any unbounded or oversized order."""
        account = terminal.account_snapshot()
        if not account.connected or not account.account_available:
            return {"executed": False, "reason": "Live account unavailable.", "halt": True}
        if account.trade_mode != "real" or not account.trading_allowed:
            return {
                "executed": False,
                "reason": "Real-account trading is not allowed.",
                "halt": True,
            }
        if account.equity is None or account.equity <= 0:
            return {"executed": False, "reason": "Live equity unavailable.", "halt": True}
        session_loss_limit = starting_equity * settings.live_auto_max_session_loss_percent / 100
        if starting_equity - account.equity >= session_loss_limit:
            return {"executed": False, "reason": "Session loss limit reached.", "halt": True}
        if len(account.positions) >= settings.live_auto_max_positions:
            return {"executed": False, "reason": "Open-position limit reached.", "halt": True}
        if account.orders:
            return {
                "executed": False,
                "reason": "Pending orders exist; their potential risk cannot be verified.",
                "halt": True,
            }
        if orders_submitted >= settings.live_auto_max_orders:
            return {"executed": False, "reason": "Session order limit reached.", "halt": True}
        if any(position.symbol == symbol for position in account.positions) or any(
            order.symbol == symbol for order in account.orders
        ):
            return {"executed": False, "reason": "Symbol already has an open position or order."}

        if LiveAutoTrader._is_xauusd(symbol):
            current_time = now or datetime.now(UTC)
            calendar_client = calendar or EconomicCalendarClient()
            try:
                events = calendar_client.high_impact_usd_events(settings, current_time)
            except EconomicCalendarError as exc:
                return {
                    "executed": False,
                    "reason": f"XAUUSD blocked: {exc}",
                    "news_filter": "unavailable",
                }
            active_event = next(
                (
                    event
                    for event in events
                    if calendar_client.within_blackout(event.event_time, current_time)
                ),
                None,
            )
            if active_event is not None:
                return {
                    "executed": False,
                    "reason": f"XAUUSD blocked near high-impact USD news: {active_event.name}.",
                    "news_filter": "blackout",
                    "event_time": active_event.event_time.isoformat(),
                }

        open_risk = 0.0
        for position in account.positions:
            if position.stop_loss is None or position.price_open is None:
                return {
                    "executed": False,
                    "reason": "Existing position risk is unknown.",
                    "halt": True,
                }
            position_context = terminal.risk_context(position.symbol, position.side)
            position_risk = calculate_position_risk(
                position_context,
                position.volume,
                position.price_open,
                position.stop_loss,
            )
            if position_risk is None:
                return {
                    "executed": False,
                    "reason": "Existing position risk is unknown.",
                    "halt": True,
                }
            open_risk += position_risk

        series: list[CandleSeries] = []
        for timeframe in (Timeframe.M15, Timeframe.H1, Timeframe.H4):
            result = terminal.historical_candles(symbol, timeframe, 250)
            if result.series is None:
                return {
                    "executed": False,
                    "reason": result.error_message or "MT5 history unavailable.",
                }
            series.append(result.series)
        signal = DeterministicAnalyzer().analyze(tuple(series))
        if signal.decision is CandidateDecision.NO_TRADE:
            return {"executed": False, "reason": "NO_TRADE"}

        side = signal.decision.value
        quote = terminal.market_snapshot(symbol)
        if quote.snapshot is None or quote.snapshot.bid is None or quote.snapshot.ask is None:
            return {"executed": False, "reason": "MT5 quote unavailable."}
        entry = quote.snapshot.ask if side == "buy" else quote.snapshot.bid
        atr = next(item.atr for item in signal.timeframe_analyses if item.timeframe == "H1")
        if atr is None or atr <= 0:
            return {"executed": False, "reason": "Valid H1 ATR is unavailable."}
        stop_loss = entry - atr * 1.5 if side == "buy" else entry + atr * 1.5
        take_profit = entry + atr * 3 if side == "buy" else entry - atr * 3
        context = terminal.risk_context(symbol, side)
        plan = calculate_risk_plan(context, stop_loss, risk_percent)
        if not plan.approved or plan.volume is None:
            return {"executed": False, "reason": plan.reason}
        if plan.volume > settings.max_live_lots:
            return {
                "executed": False,
                "reason": "Broker-sized volume exceeds the configured lot cap.",
            }
        total_risk_cap = account.equity * settings.live_auto_max_open_risk_percent / 100
        if plan.risk_amount is None or open_risk + plan.risk_amount > total_risk_cap:
            return {"executed": False, "reason": "Open-risk budget would be exceeded."}

        order = terminal.send_market_order(
            symbol,
            side,
            plan.volume,
            round(stop_loss, context.digits or 5),
            round(take_profit, context.digits or 5),
            required_trade_mode="real",
            max_quote_age_seconds=settings.market_data_max_age_seconds,
            max_spread_points=settings.market_data_max_spread_points,
        )
        return {
            "executed": order.submitted,
            "reason": order.error_message,
            "side": side,
            "symbol": symbol,
            "volume": plan.volume,
            "risk_amount": plan.risk_amount,
            "open_risk_before_order": open_risk,
            "order": asdict(order),
        }

    @staticmethod
    def _is_xauusd(symbol: str) -> bool:
        normalized = "".join(character for character in symbol.upper() if character.isalnum())
        return normalized.startswith("XAUUSD")


live_auto_trader = LiveAutoTrader()
