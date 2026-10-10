"""Bounded, explicitly enabled MT5 demo-account automation."""

from __future__ import annotations

import threading
from dataclasses import asdict
from typing import Any

from backend.config.settings import Settings
from backend.execution.mt5_terminal import Mt5TerminalAdapter
from backend.market.models import CandleSeries, Timeframe
from backend.risk.management import calculate_risk_plan
from backend.signals.deterministic import CandidateDecision, DeterministicAnalyzer


class DemoAutoTrader:
    """Run a short, bounded signal loop; never targets a real MT5 account."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._state: dict[str, Any] = {"running": False, "status": "stopped"}

    def status(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._state)

    def start(
        self,
        symbols: list[str],
        risk_percent: float,
        interval_seconds: int,
        max_orders: int,
        settings: Settings,
    ) -> dict[str, Any]:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                raise ValueError("Demo auto-trading is already running.")
            self._stop = threading.Event()
            self._state = {
                "running": True,
                "status": "starting",
                "symbol": ", ".join(symbols),
                "symbols": symbols,
                "risk_percent": risk_percent,
                "interval_seconds": interval_seconds,
                "max_orders": max_orders,
                "evaluations": 0,
                "orders_submitted": 0,
                "last_result": None,
                "last_error": None,
            }
            self._thread = threading.Thread(
                target=self._run,
                args=(symbols, risk_percent, interval_seconds, max_orders, settings, self._stop),
                daemon=True,
                name="mt5-demo-auto-trader",
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
        max_orders: int,
        settings: Settings,
        stop_event: threading.Event,
    ) -> None:
        try:
            for index in range(10):
                if stop_event.is_set():
                    break
                symbol = symbols[index % len(symbols)]
                result = self._evaluate(symbol, risk_percent, settings)
                with self._lock:
                    self._state["evaluations"] += 1
                    self._state["last_result"] = result
                    self._state["status"] = "running"
                    if result.get("executed"):
                        self._state["orders_submitted"] += 1
                    orders = self._state["orders_submitted"]
                if orders >= max_orders or not result.get("continue", True):
                    break
                if stop_event.wait(interval_seconds):
                    break
        except Exception as exc:
            with self._lock:
                self._state["last_error"] = type(exc).__name__
                self._state["status"] = "error"
        finally:
            with self._lock:
                self._state["running"] = False
                if self._state["status"] != "error":
                    self._state["status"] = "stopped"

    @staticmethod
    def evaluate_once(
        symbol: str,
        risk_percent: float,
        settings: Settings,
        terminal: Mt5TerminalAdapter,
    ) -> dict[str, Any]:
        """Perform one guarded analysis and at most one order submission."""
        return DemoAutoTrader._evaluate(symbol, risk_percent, settings, terminal)

    @staticmethod
    def _evaluate(
        symbol: str,
        risk_percent: float,
        settings: Settings,
        terminal: Mt5TerminalAdapter | None = None,
    ) -> dict[str, Any]:
        if not settings.demo_execution_enabled:
            return {"executed": False, "reason": "Demo execution is disabled.", "continue": False}
        terminal = terminal or Mt5TerminalAdapter(
            settings.mt5_terminal_path, settings.mt5_connection_timeout_ms
        )
        account = terminal.account_snapshot()
        if not account.connected or not account.account_available:
            return {
                "executed": False,
                "reason": account.error_message or "MT5 account unavailable.",
                "continue": False,
            }
        if account.trade_mode != "demo":
            return {
                "executed": False,
                "reason": "Automation is restricted to MT5 demo accounts.",
                "continue": False,
            }
        if not account.trading_allowed:
            return {
                "executed": False,
                "reason": "MT5 account does not allow trading.",
                "continue": False,
            }
        if any(position.symbol == symbol for position in account.positions) or any(
            order.symbol == symbol for order in account.orders
        ):
            return {
                "executed": False,
                "reason": "An MT5 position or order already exists for this symbol.",
            }

        series: list[CandleSeries] = []
        for timeframe in (Timeframe.M15, Timeframe.H1, Timeframe.H4):
            result = terminal.historical_candles(symbol, timeframe, 250)
            if result.series is None:
                return {
                    "executed": False,
                    "reason": result.error_message or "MT5 history unavailable.",
                    "continue": False,
                }
            series.append(result.series)
        signal = DeterministicAnalyzer().analyze(tuple(series))
        if signal.decision is CandidateDecision.NO_TRADE:
            return {"executed": False, "reason": "NO_TRADE"}

        quote = terminal.market_snapshot(symbol)
        if quote.snapshot is None or quote.snapshot.bid is None or quote.snapshot.ask is None:
            return {"executed": False, "reason": "MT5 quote unavailable.", "continue": False}
        side = signal.decision.value
        entry = quote.snapshot.ask if side == "buy" else quote.snapshot.bid
        atr = next(item.atr for item in signal.timeframe_analyses if item.timeframe == "H1")
        if atr is None or atr <= 0:
            return {"executed": False, "reason": "Valid H1 ATR is unavailable."}
        stop_loss = entry - atr * 1.5 if side == "buy" else entry + atr * 1.5
        take_profit = entry + atr * 3 if side == "buy" else entry - atr * 3
        context = terminal.risk_context(symbol, side)
        risk_plan = calculate_risk_plan(context, stop_loss, risk_percent)
        if not risk_plan.approved or risk_plan.volume is None:
            return {"executed": False, "reason": risk_plan.reason}
        if risk_plan.volume > settings.max_demo_lots:
            return {
                "executed": False,
                "reason": "Broker-calculated volume exceeds the demo lot cap.",
            }
        order = terminal.send_market_order(
            symbol,
            side,
            risk_plan.volume,
            stop_loss,
            take_profit,
            required_trade_mode="demo",
            max_quote_age_seconds=settings.market_data_max_age_seconds,
            max_spread_points=settings.market_data_max_spread_points,
        )
        return {
            "executed": order.submitted,
            "reason": order.error_message,
            "side": side,
            "symbol": symbol,
            "volume": risk_plan.volume,
            "risk_amount": risk_plan.risk_amount,
            "order": asdict(order),
        }


demo_auto_trader = DemoAutoTrader()
