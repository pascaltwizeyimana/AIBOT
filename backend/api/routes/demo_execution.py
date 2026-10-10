"""Explicitly enabled demo-account execution driven by real MT5 market data."""

from dataclasses import asdict, is_dataclass

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.api.dependencies import get_mt5_terminal
from backend.config.settings import Settings, get_settings
from backend.execution.demo_auto_trader import demo_auto_trader
from backend.execution.mt5_terminal import Mt5TerminalAdapter
from backend.market.models import CandleSeries, Timeframe
from backend.signals.deterministic import CandidateDecision, DeterministicAnalyzer

router = APIRouter(prefix="/demo-execution")


def serialize_order_result(result: object) -> object:
    if is_dataclass(result):
        return asdict(result)
    if hasattr(result, "__dict__"):
        return vars(result)
    return result


class DemoTradeRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=64)
    volume: float = Field(default=0.01, gt=0)


class DemoAutoTradeRequest(BaseModel):
    symbols: list[str] = Field(min_length=1, max_length=5)
    risk_percent: float = Field(default=0.25, gt=0, le=0.5)
    interval_seconds: int = Field(default=60, ge=30, le=3600)
    max_orders: int = Field(default=1, ge=1, le=3)


class DemoOneClickRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=64)
    risk_percent: float = Field(default=0.25, gt=0, le=0.5)


class DemoManualTradeRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=64)
    side: str = Field(pattern="^(buy|sell)$")
    volume: float = Field(default=0.01, gt=0, le=10.0)
    entry: float = Field(gt=0)
    stop_loss: float = Field(gt=0)
    take_profit: float = Field(gt=0)


@router.post("/manual")
def manual_demo_trade(
    request: DemoManualTradeRequest,
    terminal: Mt5TerminalAdapter = Depends(get_mt5_terminal),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    """Submit a user-selected demo trade using explicit entry and risk levels."""
    if not settings.demo_execution_enabled:
        raise HTTPException(status_code=403, detail="Demo execution is disabled in settings.")
    if request.volume > settings.max_demo_lots:
        raise HTTPException(
            status_code=422,
            detail=f"Demo volume cannot exceed {settings.max_demo_lots} lots.",
        )

    quote = terminal.market_snapshot(request.symbol)
    if quote.snapshot is None or quote.snapshot.bid is None or quote.snapshot.ask is None:
        raise HTTPException(status_code=503, detail="MT5 quote unavailable.")

    bid = float(quote.snapshot.bid)
    ask = float(quote.snapshot.ask)
    low = min(bid, ask)
    high = max(bid, ask)
    if not low <= float(request.entry) <= high:
        raise HTTPException(
            status_code=422,
            detail="Entry must fall within the current bid/ask range for the selected symbol.",
        )

    if request.side == "buy":
        if not request.stop_loss < request.entry or not request.take_profit > request.entry:
            raise HTTPException(
                status_code=422,
                detail="Buy trades require stop_loss < entry and take_profit > entry.",
            )
    else:
        if not request.stop_loss > request.entry or not request.take_profit < request.entry:
            raise HTTPException(
                status_code=422,
                detail="Sell trades require stop_loss > entry and take_profit < entry.",
            )

    result = terminal.send_market_order(
        request.symbol,
        request.side,
        request.volume,
        request.stop_loss,
        request.take_profit,
        required_trade_mode="demo",
        max_quote_age_seconds=settings.market_data_max_age_seconds,
        max_spread_points=settings.market_data_max_spread_points,
    )
    return {
        "executed": result.submitted,
        "side": request.side,
        "symbol": request.symbol,
        "volume": request.volume,
        "entry": request.entry,
        "stop_loss": request.stop_loss,
        "take_profit": request.take_profit,
        "order": serialize_order_result(result),
    }


@router.post("/one-click")
def one_click_demo_trade(
    request: DemoOneClickRequest,
    terminal: Mt5TerminalAdapter = Depends(get_mt5_terminal),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    """Evaluate once and submit at most one broker-sized order on a demo account."""
    if not settings.demo_execution_enabled:
        raise HTTPException(status_code=403, detail="Demo execution is disabled in settings.")
    if request.risk_percent > settings.demo_auto_trade_max_risk_percent:
        raise HTTPException(
            status_code=422,
            detail=f"Risk cannot exceed {settings.demo_auto_trade_max_risk_percent}% per order.",
        )
    return demo_auto_trader.evaluate_once(
        request.symbol,
        request.risk_percent,
        settings,
        terminal,
    )


@router.get("/auto/status")
def auto_trade_status() -> dict[str, object]:
    return demo_auto_trader.status()


@router.post("/auto/start")
def start_auto_trade(
    request: DemoAutoTradeRequest,
    terminal: Mt5TerminalAdapter = Depends(get_mt5_terminal),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    if not settings.demo_execution_enabled:
        raise HTTPException(status_code=403, detail="Demo execution is disabled in settings.")
    if request.risk_percent > settings.demo_auto_trade_max_risk_percent:
        raise HTTPException(
            status_code=422,
            detail=f"Risk cannot exceed {settings.demo_auto_trade_max_risk_percent}% per order.",
        )
    account = terminal.account_snapshot()
    if not account.connected or not account.account_available:
        raise HTTPException(
            status_code=503, detail=account.error_message or "MT5 account unavailable."
        )
    if account.trade_mode != "demo":
        raise HTTPException(
            status_code=403, detail="Automation is restricted to MT5 demo accounts."
        )
    if not account.trading_allowed:
        raise HTTPException(status_code=403, detail="MT5 account does not allow trading.")
    symbols = list(dict.fromkeys(symbol.strip() for symbol in request.symbols if symbol.strip()))
    if not symbols:
        raise HTTPException(status_code=422, detail="At least one non-empty symbol is required.")
    try:
        return demo_auto_trader.start(
            symbols,
            request.risk_percent,
            request.interval_seconds,
            request.max_orders,
            settings,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/auto/stop")
def stop_auto_trade() -> dict[str, object]:
    return demo_auto_trader.stop()


@router.post("/analyse-and-trade")
def analyse_and_trade(
    request: DemoTradeRequest,
    terminal: Mt5TerminalAdapter = Depends(get_mt5_terminal),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    """Analyse real completed candles, then submit one bounded demo order."""
    if not settings.demo_execution_enabled:
        raise HTTPException(status_code=403, detail="Demo execution is disabled in settings.")
    if request.volume > settings.max_demo_lots:
        raise HTTPException(
            status_code=422,
            detail=f"Demo volume cannot exceed {settings.max_demo_lots} lots.",
        )

    series: list[CandleSeries] = []
    for timeframe in (Timeframe.M15, Timeframe.H1, Timeframe.H4):
        result = terminal.historical_candles(request.symbol, timeframe, 250)
        if result.series is None:
            raise HTTPException(
                status_code=503,
                detail=result.error_message or "MT5 history unavailable.",
            )
        series.append(result.series)
    signal = DeterministicAnalyzer().analyze(tuple(series))
    if signal.decision is CandidateDecision.NO_TRADE:
        return {"executed": False, "reason": "NO_TRADE", "analysis": asdict(signal)}

    quote = terminal.market_snapshot(request.symbol)
    if quote.snapshot is None or quote.snapshot.bid is None or quote.snapshot.ask is None:
        raise HTTPException(status_code=503, detail="MT5 quote unavailable.")
    entry = quote.snapshot.ask if signal.decision is CandidateDecision.BUY else quote.snapshot.bid
    atr = next(item.atr for item in signal.timeframe_analyses if item.timeframe == "H1")
    if atr is None:
        return {"executed": False, "reason": "Missing H1 ATR", "analysis": asdict(signal)}
    risk_distance = atr * 1.5
    reward_distance = atr * 3.0
    stop_loss = (
        entry - risk_distance if signal.decision is CandidateDecision.BUY else entry + risk_distance
    )
    take_profit = (
        entry + reward_distance
        if signal.decision is CandidateDecision.BUY
        else entry - reward_distance
    )
    result = terminal.send_market_order(
        request.symbol,
        signal.decision.value,
        request.volume,
        round(stop_loss, 5),
        round(take_profit, 5),
        required_trade_mode="demo",
        max_quote_age_seconds=settings.market_data_max_age_seconds,
        max_spread_points=settings.market_data_max_spread_points,
    )
    return {
        "executed": result.submitted,
        "side": signal.decision.value,
        "symbol": request.symbol,
        "volume": request.volume,
        "entry": entry,
        "stop_loss": round(stop_loss, 5),
        "take_profit": round(take_profit, 5),
        "order": asdict(result),
        "analysis": asdict(signal),
    }
