"""Deterministic development candles for inspecting analysis without MT5."""

from datetime import UTC, datetime, timedelta

from backend.market.models import Candle, CandleSeries, Timeframe

_TIMEFRAME_MINUTES = {
    Timeframe.M15: 15,
    Timeframe.M30: 30,
    Timeframe.H1: 60,
    Timeframe.H4: 240,
    Timeframe.D1: 1_440,
    Timeframe.W1: 10_080,
}


def demo_candles(broker_symbol: str, timeframe: Timeframe, count: int) -> CandleSeries:
    """Create stable, completed candles for local UI development only."""
    interval = _TIMEFRAME_MINUTES.get(timeframe, 15)
    direction = 1 if sum(ord(character) for character in broker_symbol) % 2 else -1
    base = 1.0 + (sum(ord(character) for character in broker_symbol) % 100) / 100
    start = datetime(2024, 1, 1, tzinfo=UTC)
    candles: list[Candle] = []
    for index in range(count):
        close = base + direction * index * 0.001 + ((index % 5) - 2) * 0.0002
        open_price = close - direction * 0.0004
        candles.append(
            Candle(
                open_time=start + timedelta(minutes=interval * index),
                open=open_price,
                high=max(open_price, close) + 0.001,
                low=min(open_price, close) - 0.001,
                close=close,
                tick_volume=100 + index,
                spread_points=10,
                real_volume=float(100 + index),
            )
        )
    return CandleSeries(broker_symbol, timeframe, False, tuple(candles))
