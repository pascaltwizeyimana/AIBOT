from datetime import UTC, datetime, timedelta

import pytest

from backend.market.models import Candle, CandleSeries, Timeframe
from backend.signals.technical import TechnicalAnalyzer


def candle_series(count: int, *, includes_current_candle: bool = False) -> CandleSeries:
    candles = tuple(
        Candle(
            open_time=datetime(2024, 1, 1, tzinfo=UTC) + timedelta(hours=index),
            open=100.0 + index,
            high=101.0 + index,
            low=99.0 + index,
            close=100.5 + index,
            tick_volume=100,
            spread_points=10,
            real_volume=1.0,
        )
        for index in range(count)
    )
    return CandleSeries("EURUSDm", Timeframe.H1, includes_current_candle, candles)


def test_technical_analysis_calculates_deterministic_latest_values() -> None:
    analysis = TechnicalAnalyzer().analyze(candle_series(50))

    assert analysis.broker_symbol == "EURUSDm"
    assert analysis.timeframe == "H1"
    assert analysis.candle_count == 50
    assert analysis.sma_20 == 140.0
    assert analysis.ema_20 == pytest.approx(140.0)
    assert analysis.rsi_14 == 100.0
    assert analysis.macd_line is not None
    assert analysis.macd_signal is not None
    assert analysis.macd_histogram is not None
    assert analysis.atr_14 == pytest.approx(2.0)
    assert analysis.bollinger_middle == 140.0
    assert analysis.stochastic_k == pytest.approx(75.0)
    assert analysis.stochastic_d == pytest.approx(75.0)


def test_technical_analysis_returns_unavailable_values_when_history_is_short() -> None:
    analysis = TechnicalAnalyzer().analyze(candle_series(10))

    assert analysis.sma_20 is None
    assert analysis.ema_20 is None
    assert analysis.rsi_14 is None
    assert analysis.macd_line is None
    assert analysis.atr_14 is None


def test_technical_analysis_rejects_current_forming_candle() -> None:
    with pytest.raises(ValueError, match="completed candles only"):
        TechnicalAnalyzer().analyze(candle_series(50, includes_current_candle=True))
