"""Explicitly confirmed live execution through the connected MT5 account."""

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.api.dependencies import get_mt5_terminal
from backend.config.settings import Settings, TradingMode, get_settings
from backend.execution.live_auto_trader import live_auto_trader
from backend.execution.mt5_terminal import Mt5TerminalAdapter
from backend.market.models import CandleSeries, Timeframe
from backend.risk.management import calculate_position_risk, calculate_risk_plan
from backend.signals.deterministic import CandidateDecision, DeterministicAnalyzer

router = APIRouter(prefix="/live-execution")


def serialize_order_result(result: object) -> object:
    if hasattr(result, "__dict__"):
        return vars(result)
    return result


class LiveTradeRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=64)
    risk_percent: float = Field(default=0.5, gt=0, le=2)
    confirmation: str = Field(min_length=1, max_length=80)


class RiskPreflightRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=64)
    side: str = Field(pattern="^(buy|sell)$")
    stop_loss: float
    risk_percent: float = Field(default=0.5, gt=0, le=2)


class LiveAutoTradeRequest(BaseModel):
    symbols: list[str] = Field(min_length=1, max_length=5)
    risk_percent: float = Field(default=0.25, gt=0, le=0.5)
    interval_seconds: int = Field(default=60, ge=30, le=3600)
    confirmation: str = Field(min_length=1, max_length=80)


class LiveManualTradeRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=64)
    side: str = Field(pattern="^(buy|sell)$")
    volume: float = Field(default=0.01, gt=0, le=10.0)
    risk_percent: float = Field(default=0.25, gt=0, le=0.5)
    entry: float = Field(gt=0)
    stop_loss: float = Field(gt=0)
    take_profit: float = Field(gt=0)
    confirmation: str = Field(min_length=1, max_length=80)


def require_live_activation(settings: Settings, confirmation: str) -> None:
    if settings.trading_mode != TradingMode.LIVE or not settings.live_trading_enabled:
        raise HTTPException(status_code=403, detail="Live trading is not enabled in settings.")
    if not settings.trading_execution_enabled:
        raise HTTPException(status_code=403, detail="Live execution is not enabled in settings.")
    if confirmation != settings.live_trading_confirmation:
        raise HTTPException(status_code=403, detail="Live confirmation phrase is invalid.")


@router.get("/auto/status")
def live_auto_trade_status() -> dict[str, object]:
    return live_auto_trader.status()


@router.post("/auto/start")
def start_live_auto_trade(
    request: LiveAutoTradeRequest,
    terminal: Mt5TerminalAdapter = Depends(get_mt5_terminal),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    require_live_activation(settings, request.confirmation)
    if request.risk_percent > settings.live_auto_max_risk_percent:
        raise HTTPException(
            status_code=422,
            detail=f"Risk cannot exceed {settings.live_auto_max_risk_percent}% per order.",
        )
    symbols = list(dict.fromkeys(symbol.strip() for symbol in request.symbols if symbol.strip()))
    if not symbols:
        raise HTTPException(status_code=422, detail="At least one non-empty symbol is required.")
    try:
        return live_auto_trader.start(
            symbols,
            request.risk_percent,
            request.interval_seconds,
            settings,
            terminal,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/auto/stop")
def stop_live_auto_trade() -> dict[str, object]:
    return live_auto_trader.stop()


@router.post("/manual")
def manual_live_trade(
    request: LiveManualTradeRequest,
    terminal: Mt5TerminalAdapter = Depends(get_mt5_terminal),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    """Submit a user-specified live order using explicit manual entry, stop, and target."""
    require_live_activation(settings, request.confirmation)
    if request.volume > settings.max_live_lots:
        raise HTTPException(
            status_code=422,
            detail=f"Live volume cannot exceed {settings.max_live_lots} lots.",
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

    if request.risk_percent > settings.live_auto_max_risk_percent:
        raise HTTPException(
            status_code=422,
            detail=f"Risk cannot exceed {settings.live_auto_max_risk_percent}% per order.",
        )

    risk_context = terminal.risk_context(request.symbol, request.side)
    risk_plan = calculate_risk_plan(risk_context, request.stop_loss, request.risk_percent)
    if not risk_plan.approved or risk_plan.volume is None:
        raise HTTPException(status_code=422, detail=risk_plan.reason)
    if (
        risk_context.volume_min is None
        or risk_context.volume_max is None
        or risk_context.volume_step is None
        or request.volume < risk_context.volume_min
        or request.volume > risk_context.volume_max
    ):
        raise HTTPException(status_code=422, detail="Volume violates broker volume limits.")
    volume_steps = (request.volume - risk_context.volume_min) / risk_context.volume_step
    if abs(volume_steps - round(volume_steps)) > 1e-8:
        raise HTTPException(status_code=422, detail="Volume does not match the broker volume step.")
    if request.volume > risk_plan.volume:
        raise HTTPException(
            status_code=422,
            detail=f"Requested volume exceeds risk-approved max ({risk_plan.volume} lots).",
        )

    estimated_risk = calculate_position_risk(
        risk_context,
        request.volume,
        risk_context.entry,
        request.stop_loss,
    )
    if estimated_risk is None:
        raise HTTPException(status_code=422, detail="Broker risk could not be calculated.")

    result = terminal.send_market_order(
        request.symbol,
        request.side,
        request.volume,
        request.stop_loss,
        request.take_profit,
        required_trade_mode="real",
        max_quote_age_seconds=settings.market_data_max_age_seconds,
        max_spread_points=settings.market_data_max_spread_points,
    )
    return {
        "executed": result.submitted,
        "side": request.side,
        "symbol": request.symbol,
        "volume": request.volume,
        "risk_percent": request.risk_percent,
        "risk_amount": estimated_risk,
        "currency": risk_context.currency,
        "entry": request.entry,
        "stop_loss": request.stop_loss,
        "take_profit": request.take_profit,
        "order": serialize_order_result(result),
    }


@router.post("/risk-preflight")
def risk_preflight(
    request: RiskPreflightRequest,
    terminal: Mt5TerminalAdapter = Depends(get_mt5_terminal),
) -> dict[str, object]:
    """Return the broker-aware volume before any order can be considered."""
    context = terminal.risk_context(request.symbol, request.side)
    plan = calculate_risk_plan(context, request.stop_loss, request.risk_percent)
    return {
        "approved": plan.approved,
        "reason": plan.reason,
        "broker_server": context.broker_server,
        "currency": context.currency,
        "equity": context.equity,
        "entry": context.entry,
        "volume": plan.volume,
        "risk_amount": plan.risk_amount,
        "loss_per_lot": plan.loss_per_lot,
        "stop_distance": plan.stop_distance,
        "volume_min": context.volume_min,
        "volume_max": context.volume_max,
        "volume_step": context.volume_step,
    }


@router.post("/analyse-and-trade")
def analyse_and_trade_live(
    request: LiveTradeRequest,
    terminal: Mt5TerminalAdapter = Depends(get_mt5_terminal),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    """Analyse completed candles, then submit one explicitly confirmed live order."""
    require_live_activation(settings, request.confirmation)
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
    risk_context = terminal.risk_context(request.symbol, signal.decision.value)
    risk_plan = calculate_risk_plan(risk_context, stop_loss, request.risk_percent)
    if not risk_plan.approved or risk_plan.volume is None:
        raise HTTPException(status_code=403, detail=risk_plan.reason)
    if risk_plan.volume > settings.max_live_lots:
        raise HTTPException(
            status_code=422,
            detail=f"Risk volume exceeds the configured cap of {settings.max_live_lots} lots.",
        )
    result = terminal.send_market_order(
        request.symbol,
        signal.decision.value,
        risk_plan.volume,
        round(stop_loss, 5),
        round(take_profit, 5),
        required_trade_mode="real",
        max_quote_age_seconds=settings.market_data_max_age_seconds,
        max_spread_points=settings.market_data_max_spread_points,
    )
    return {
        "executed": result.submitted,
        "side": signal.decision.value,
        "symbol": request.symbol,
        "volume": risk_plan.volume,
        "risk_percent": request.risk_percent,
        "risk_amount": risk_plan.risk_amount,
        "broker_server": risk_context.broker_server,
        "entry": entry,
        "stop_loss": round(stop_loss, 5),
        "take_profit": round(take_profit, 5),
        "order": asdict(result),
        "analysis": asdict(signal),
    }
