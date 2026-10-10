from datetime import UTC, datetime, timedelta

import pytest

from backend.market.models import Candle, CandleSeries, Timeframe
from backend.signals.deterministic import CandidateDecision, DeterministicAnalyzer


def series(timeframe: Timeframe, direction: int) -> CandleSeries:
    candles = tuple(
        Candle(
            open_time=datetime(2024, 1, 1, tzinfo=UTC) + timedelta(hours=index),
            open=100.0 + (direction * index),
            high=101.0 + (direction * index),
            low=99.0 + (direction * index),
            close=100.5 + (direction * index),
            tick_volume=100,
            spread_points=10,
            real_volume=1.0,
        )
        for index in range(60)
    )
    return CandleSeries("EURUSDm", timeframe, False, candles)


def test_deterministic_analyzer_returns_explainable_bullish_candidate() -> None:
    result = DeterministicAnalyzer().analyze((series(Timeframe.H1, 1), series(Timeframe.H4, 1)))

    assert result.decision is CandidateDecision.BUY
    assert result.confidence == "moderate"
    assert len(result.timeframe_analyses) == 2
    assert "risk and news validation" in result.reasons[-1]


def test_deterministic_analyzer_returns_no_trade_for_conflicting_timeframes() -> None:
    result = DeterministicAnalyzer().analyze((series(Timeframe.H1, 1), series(Timeframe.H4, -1)))

    assert result.decision is CandidateDecision.NO_TRADE
    assert result.reasons


def test_deterministic_analyzer_rejects_forming_candles() -> None:
    invalid = CandleSeries("EURUSDm", Timeframe.H1, True, series(Timeframe.H1, 1).candles)

    with pytest.raises(ValueError, match="completed candles"):
        DeterministicAnalyzer().analyze((invalid, series(Timeframe.H4, 1)))
