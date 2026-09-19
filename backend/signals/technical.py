"""Deterministic technical indicators computed from validated completed candles."""

from dataclasses import dataclass
from math import isfinite

import numpy as np

from backend.market.models import CandleSeries


@dataclass(frozen=True, slots=True)
class TechnicalAnalysis:
    """Latest indicator values, tied to the latest completed candle in a series."""

    broker_symbol: str
    timeframe: str
    candle_open_time: str
    candle_count: int
    sma_20: float | None
    ema_20: float | None
    rsi_14: float | None
    macd_line: float | None
    macd_signal: float | None
    macd_histogram: float | None
    atr_14: float | None
    bollinger_upper: float | None
    bollinger_middle: float | None
    bollinger_lower: float | None
    stochastic_k: float | None
    stochastic_d: float | None


class TechnicalAnalyzer:
    """Baseline indicator calculator with no broker or execution dependency."""

    def analyze(self, candles: CandleSeries) -> TechnicalAnalysis:
        """Calculate indicators using completed candles only."""
        if candles.includes_current_candle:
            raise ValueError("Technical analysis requires completed candles only.")
        if not candles.candles:
            raise ValueError("Technical analysis requires at least one candle.")

        closes = np.array([candle.close for candle in candles.candles], dtype=float)
        highs = np.array([candle.high for candle in candles.candles], dtype=float)
        lows = np.array([candle.low for candle in candles.candles], dtype=float)
        sma_20 = sma(closes, 20)
        ema_20 = ema(closes, 20)
        rsi_14 = rsi(closes, 14)
        macd_line, macd_signal, macd_histogram = macd(closes)
        atr_14 = atr(highs, lows, closes, 14)
        bollinger_upper, bollinger_middle, bollinger_lower = bollinger(closes, 20, 2.0)
        stochastic_k, stochastic_d = stochastic(highs, lows, closes, 14, 3)
        return TechnicalAnalysis(
            broker_symbol=candles.broker_symbol,
            timeframe=candles.timeframe.value,
            candle_open_time=candles.candles[-1].open_time.isoformat(),
            candle_count=len(candles.candles),
            sma_20=last_value(sma_20),
            ema_20=last_value(ema_20),
            rsi_14=last_value(rsi_14),
            macd_line=last_value(macd_line),
            macd_signal=last_value(macd_signal),
            macd_histogram=last_value(macd_histogram),
            atr_14=last_value(atr_14),
            bollinger_upper=last_value(bollinger_upper),
            bollinger_middle=last_value(bollinger_middle),
            bollinger_lower=last_value(bollinger_lower),
            stochastic_k=last_value(stochastic_k),
            stochastic_d=last_value(stochastic_d),
        )


def sma(values: np.ndarray, period: int) -> np.ndarray:
    """Simple moving average aligned with the source values; unavailable values are NaN."""
    result = unavailable(values)
    if len(values) < period:
        return result
    cumulative = np.cumsum(np.insert(values, 0, 0.0))
    result[period - 1 :] = (cumulative[period:] - cumulative[:-period]) / period
    return result


def ema(values: np.ndarray, period: int) -> np.ndarray:
    """EMA seeded by the first complete SMA, avoiding a pre-history assumption."""
    result = unavailable(values)
    if len(values) < period:
        return result
    result[period - 1] = float(np.mean(values[:period]))
    multiplier = 2.0 / (period + 1)
    for index in range(period, len(values)):
        result[index] = (values[index] - result[index - 1]) * multiplier + result[index - 1]
    return result


def rsi(closes: np.ndarray, period: int) -> np.ndarray:
    """Wilder RSI, seeded only after a full period of completed price changes."""
    result = unavailable(closes)
    if len(closes) <= period:
        return result
    deltas = np.diff(closes)
    gains = np.maximum(deltas, 0.0)
    losses = np.maximum(-deltas, 0.0)
    average_gain = float(np.mean(gains[:period]))
    average_loss = float(np.mean(losses[:period]))
    result[period] = rsi_value(average_gain, average_loss)
    for index in range(period + 1, len(closes)):
        average_gain = ((average_gain * (period - 1)) + gains[index - 1]) / period
        average_loss = ((average_loss * (period - 1)) + losses[index - 1]) / period
        result[index] = rsi_value(average_gain, average_loss)
    return result


def rsi_value(average_gain: float, average_loss: float) -> float:
    """Convert Wilder average gain/loss to a bounded RSI value without inventing data."""
    if average_gain == 0.0 and average_loss == 0.0:
        return 50.0
    if average_loss == 0.0:
        return 100.0
    if average_gain == 0.0:
        return 0.0
    relative_strength = average_gain / average_loss
    return 100.0 - (100.0 / (1.0 + relative_strength))


def macd(closes: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Standard 12/26/9 MACD, with all series aligned to the original candles."""
    fast = ema(closes, 12)
    slow = ema(closes, 26)
    line = unavailable(closes)
    valid_indices = np.flatnonzero(~np.isnan(fast) & ~np.isnan(slow))
    if valid_indices.size:
        line[valid_indices] = fast[valid_indices] - slow[valid_indices]
    signal = unavailable(closes)
    if valid_indices.size >= 9:
        signal_values = ema(line[valid_indices], 9)
        signal[valid_indices] = signal_values
    histogram = line - signal
    return line, signal, histogram


def atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int) -> np.ndarray:
    """Wilder ATR using true range from completed candles only."""
    result = unavailable(closes)
    if len(closes) < period:
        return result
    true_ranges = np.empty(len(closes), dtype=float)
    true_ranges[0] = highs[0] - lows[0]
    for index in range(1, len(closes)):
        true_ranges[index] = max(
            highs[index] - lows[index],
            abs(highs[index] - closes[index - 1]),
            abs(lows[index] - closes[index - 1]),
        )
    result[period - 1] = float(np.mean(true_ranges[:period]))
    for index in range(period, len(closes)):
        result[index] = ((result[index - 1] * (period - 1)) + true_ranges[index]) / period
    return result


def bollinger(
    closes: np.ndarray, period: int, deviations: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Bollinger upper, middle, and lower bands using population standard deviation."""
    middle = sma(closes, period)
    upper = unavailable(closes)
    lower = unavailable(closes)
    for index in range(period - 1, len(closes)):
        deviation = float(np.std(closes[index - period + 1 : index + 1], ddof=0))
        upper[index] = middle[index] + deviations * deviation
        lower[index] = middle[index] - deviations * deviation
    return upper, middle, lower


def stochastic(
    highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int, d_period: int
) -> tuple[np.ndarray, np.ndarray]:
    """Stochastic %K and %D aligned to each source candle while preserving NO-DATA semantics."""
    k = unavailable(closes)
    for index in range(len(closes)):
        if highs[index] > lows[index]:
            k[index] = ((closes[index] - lows[index]) / (highs[index] - lows[index])) * 100.0

    d = unavailable(closes)
    if len(closes) < max(period, d_period):
        return k, d

    valid_k_positions = np.flatnonzero(~np.isnan(k))
    if valid_k_positions.size >= d_period:
        valid_k_values = k[valid_k_positions]
        smoothed = sma(valid_k_values, d_period)
        aligned_positions = valid_k_positions[d_period - 1 :]
        aligned_values = smoothed[d_period - 1 :]
        finite_mask = np.isfinite(aligned_values)
        d[aligned_positions[finite_mask]] = aligned_values[finite_mask]
    return k, d


def unavailable(values: np.ndarray) -> np.ndarray:
    """Return an indicator-sized array whose values are explicitly unavailable."""
    return np.full(len(values), np.nan, dtype=float)


def last_value(values: np.ndarray) -> float | None:
    """Convert a latest finite indicator value to a JSON-safe optional number."""
    if values.size == 0:
        return None
    value = values[-1]
    return float(value) if isfinite(value) else None
