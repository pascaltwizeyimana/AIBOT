"""Read-only deterministic analysis endpoint with explicit NO_TRADE behavior."""

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.api.dependencies import get_mt5_terminal
from backend.execution.mt5_terminal import Mt5TerminalAdapter
from backend.market.models import CandleSeries, Timeframe
from backend.signals.deterministic import CandidateDecision, DeterministicAnalyzer
from backend.signals.technical import TechnicalAnalyzer

router = APIRouter(prefix="/analysis")


def parse_timeframes(value: str) -> tuple[Timeframe, ...]:
    """Parse a unique, bounded comma-separated timeframe list."""
    try:
        timeframes = tuple(Timeframe(item.strip().upper()) for item in value.split(","))
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail="Use MT5 timeframes such as M15,H1,H4."
        ) from exc
    if not 2 <= len(timeframes) <= 4 or len(set(timeframes)) != len(timeframes):
        raise HTTPException(status_code=422, detail="Provide two to four unique timeframes.")
    return timeframes


@router.get("/{broker_symbol}")
def analyze(
    broker_symbol: str,
    timeframes: str = Query(default="M15,H1,H4"),
    count: int = Query(default=250, ge=50, le=2_000),
    terminal: Mt5TerminalAdapter = Depends(get_mt5_terminal),
) -> dict[str, object]:
    """Produce an auditable candidate from completed MT5 candles; it never trades."""
    if not broker_symbol.strip() or len(broker_symbol) > 64:
        raise HTTPException(
            status_code=422, detail="A broker symbol between 1 and 64 characters is required."
        )
    completed: list[CandleSeries] = []
    for timeframe in parse_timeframes(timeframes):
        result = terminal.historical_candles(
            broker_symbol, timeframe, count, include_current_candle=False
        )
        if result.series is None:
            raise HTTPException(
                status_code=503,
                detail=result.error_message
                or f"Completed {timeframe.value} candles are unavailable.",
            )
        completed.append(result.series)
    signal = DeterministicAnalyzer().analyze(tuple(completed))
    h1 = next(item for item in completed if item.timeframe is Timeframe.H1)
    entry = h1.candles[-1].close
    h1_analysis = next(item for item in signal.timeframe_analyses if item.timeframe == "H1")
    atr = h1_analysis.atr
    trade_plan: dict[str, object] = {
        "action": signal.decision.value,
        "entry": None,
        "stop_loss": None,
        "take_profit": None,
        "risk_reward": None,
        "why": list(signal.reasons),
    }
    if signal.decision is not CandidateDecision.NO_TRADE and atr is not None:
        risk_distance = atr * 1.5
        reward_distance = atr * 3.0
        is_buy = signal.decision.value == "buy"
        trade_plan.update(
            entry=round(entry, 5),
            stop_loss=round(entry - risk_distance if is_buy else entry + risk_distance, 5),
            take_profit=round(entry + reward_distance if is_buy else entry - reward_distance, 5),
            risk_reward="1:2",
        )
    response = asdict(signal)
    response["data_source"] = "mt5"
    response["trade_plan"] = trade_plan
    response["technical"] = [asdict(TechnicalAnalyzer().analyze(series)) for series in completed]
    response["market_structure"] = [market_structure(series) for series in completed]
    return response


def market_structure(series: CandleSeries) -> dict[str, object]:
    """Derive conservative, completed-candle structure labels from the verified series."""
    candles = series.candles
    if len(candles) < 3:
        return {
            "timeframe": series.timeframe.value,
            "bos": None,
            "choch": None,
            "fvg": [],
            "order_blocks": [],
        }
    bos = None
    choch = None
    highs = [candle.high for candle in candles]
    lows = [candle.low for candle in candles]
    latest = candles[-1]
    prior_high = max(highs[-21:-1])
    prior_low = min(lows[-21:-1])
    if latest.close > prior_high:
        bos = "bullish"
    elif latest.close < prior_low:
        bos = "bearish"
    if len(candles) >= 4:
        previous = candles[-2]
        if bos == "bullish" and previous.close < previous.open:
            choch = "bullish"
        elif bos == "bearish" and previous.close > previous.open:
            choch = "bearish"
    fvg: list[dict[str, object]] = []
    for index in range(max(2, len(candles) - 20), len(candles)):
        left, right = candles[index - 2], candles[index]
        if left.high < right.low:
            fvg.append({"side": "bullish", "low": left.high, "high": right.low})
        elif left.low > right.high:
            fvg.append({"side": "bearish", "low": right.high, "high": left.low})
    order_blocks = []
    if bos and len(candles) >= 2:
        origin = candles[-2]
        order_blocks.append({"side": bos, "low": origin.low, "high": origin.high})
    return {
        "timeframe": series.timeframe.value,
        "bos": bos,
        "choch": choch,
        "fvg": fvg[-3:],
        "order_blocks": order_blocks,
    }
