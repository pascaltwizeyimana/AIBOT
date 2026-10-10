"""Explainable, deterministic market analysis; it has no execution authority."""

from dataclasses import dataclass
from enum import StrEnum

from backend.market.models import CandleSeries
from backend.signals.technical import TechnicalAnalyzer


class Direction(StrEnum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class CandidateDecision(StrEnum):
    BUY = "buy"
    SELL = "sell"
    NO_TRADE = "no_trade"


@dataclass(frozen=True, slots=True)
class TimeframeAnalysis:
    timeframe: str
    trend: Direction
    structure: str
    volatility: str
    atr: float | None
    atr_percent: float | None
    support: float | None
    resistance: float | None
    liquidity: tuple[str, ...]
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DeterministicSignal:
    broker_symbol: str
    decision: CandidateDecision
    confidence: str
    timeframe_analyses: tuple[TimeframeAnalysis, ...]
    reasons: tuple[str, ...]
    disclaimer: str


class DeterministicAnalyzer:
    """Produces auditable candidates from completed candles, never an order instruction."""

    def analyze(self, series_by_timeframe: tuple[CandleSeries, ...]) -> DeterministicSignal:
        if not series_by_timeframe:
            raise ValueError("At least one completed candle series is required.")
        if any(series.includes_current_candle for series in series_by_timeframe):
            raise ValueError("Deterministic analysis requires completed candles only.")
        symbols = {series.broker_symbol for series in series_by_timeframe}
        if len(symbols) != 1:
            raise ValueError("All candle series must use the same broker symbol.")

        analyses = tuple(self._analyze_timeframe(series) for series in series_by_timeframe)
        bullish = sum(item.trend is Direction.BULLISH for item in analyses)
        bearish = sum(item.trend is Direction.BEARISH for item in analyses)
        usable = len(analyses) >= 2 and all(item.atr is not None for item in analyses)
        high_volatility = any(item.volatility == "high" for item in analyses)
        reasons: list[str] = []
        decision = CandidateDecision.NO_TRADE
        confidence = "low"
        if not usable:
            reasons.append("Insufficient completed history for multi-timeframe analysis.")
        elif high_volatility:
            reasons.append("At least one timeframe is in a high-volatility regime.")
        elif bullish >= 2 and bearish == 0:
            decision = CandidateDecision.BUY
            confidence = "moderate" if bullish == len(analyses) else "low"
            reasons.append(f"{bullish}/{len(analyses)} timeframes have bullish trend evidence.")
        elif bearish >= 2 and bullish == 0:
            decision = CandidateDecision.SELL
            confidence = "moderate" if bearish == len(analyses) else "low"
            reasons.append(f"{bearish}/{len(analyses)} timeframes have bearish trend evidence.")
        else:
            reasons.append("Timeframe trend evidence conflicts or is neutral.")
        reasons.append("Candidate is advisory only; risk and news validation are still required.")
        return DeterministicSignal(
            broker_symbol=next(iter(symbols)),
            decision=decision,
            confidence=confidence,
            timeframe_analyses=analyses,
            reasons=tuple(reasons),
            disclaimer=(
                "This deterministic analysis is not financial advice and does not place trades."
            ),
        )

    def _analyze_timeframe(self, series: CandleSeries) -> TimeframeAnalysis:
        technical = TechnicalAnalyzer().analyze(series)
        closes = [candle.close for candle in series.candles]
        highs = [candle.high for candle in series.candles]
        lows = [candle.low for candle in series.candles]
        last_close = closes[-1]
        trend = self._trend(last_close, technical.ema_20, technical.rsi_14)
        atr_percent = (technical.atr_14 / last_close * 100) if technical.atr_14 else None
        volatility = self._volatility(atr_percent)
        swing_highs = self._pivots(highs, "high")
        swing_lows = self._pivots(lows, "low")
        structure = self._structure(last_close, swing_highs, swing_lows, trend)
        support = max((value for _, value in swing_lows if value < last_close), default=None)
        resistance = min((value for _, value in swing_highs if value > last_close), default=None)
        liquidity = self._liquidity(swing_highs, swing_lows, technical.atr_14)
        reasons = [f"Close is {trend.value} versus EMA-20 / RSI evidence."]
        reasons.append(f"Structure classification: {structure}.")
        reasons.append(f"ATR regime: {volatility}.")
        return TimeframeAnalysis(
            timeframe=series.timeframe.value,
            trend=trend,
            structure=structure,
            volatility=volatility,
            atr=technical.atr_14,
            atr_percent=atr_percent,
            support=support,
            resistance=resistance,
            liquidity=liquidity,
            reasons=tuple(reasons),
        )

    @staticmethod
    def _trend(close: float, ema: float | None, rsi: float | None) -> Direction:
        if ema is None or rsi is None:
            return Direction.NEUTRAL
        if close > ema and rsi >= 55:
            return Direction.BULLISH
        if close < ema and rsi <= 45:
            return Direction.BEARISH
        return Direction.NEUTRAL

    @staticmethod
    def _volatility(atr_percent: float | None) -> str:
        if atr_percent is None:
            return "unknown"
        if atr_percent < 0.1:
            return "low"
        if atr_percent > 2.0:
            return "high"
        return "normal"

    @staticmethod
    def _pivots(values: list[float], kind: str, span: int = 2) -> tuple[tuple[int, float], ...]:
        pivots: list[tuple[int, float]] = []
        for index in range(span, len(values) - span):
            window = values[index - span : index + span + 1]
            if kind == "high" and values[index] == max(window) and window.count(values[index]) == 1:
                pivots.append((index, values[index]))
            if kind == "low" and values[index] == min(window) and window.count(values[index]) == 1:
                pivots.append((index, values[index]))
        return tuple(pivots)

    @staticmethod
    def _structure(
        close: float,
        highs: tuple[tuple[int, float], ...],
        lows: tuple[tuple[int, float], ...],
        trend: Direction,
    ) -> str:
        if not highs or not lows:
            return "insufficient_swings"
        last_high = highs[-1][1]
        last_low = lows[-1][1]
        if close > last_high:
            return "bullish_bos" if trend is Direction.BULLISH else "bullish_choch"
        if close < last_low:
            return "bearish_bos" if trend is Direction.BEARISH else "bearish_choch"
        return "range_or_unconfirmed"

    @staticmethod
    def _liquidity(
        highs: tuple[tuple[int, float], ...],
        lows: tuple[tuple[int, float], ...],
        atr: float | None,
    ) -> tuple[str, ...]:
        if atr is None:
            return ()
        tolerance = atr * 0.1
        labels: list[str] = []
        if len(highs) >= 2 and abs(highs[-1][1] - highs[-2][1]) <= tolerance:
            labels.append("equal_highs_liquidity")
        if len(lows) >= 2 and abs(lows[-1][1] - lows[-2][1]) <= tolerance:
            labels.append("equal_lows_liquidity")
        return tuple(labels)
