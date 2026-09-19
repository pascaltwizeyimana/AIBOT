from datetime import UTC, datetime
from types import ModuleType

from backend.execution.mt5_historical_data import Mt5HistoricalDataProvider
from backend.execution.mt5_terminal import Mt5TerminalAdapter
from backend.market.models import Timeframe


class FakeMt5(ModuleType):
    TIMEFRAME_H1 = 16_385

    def __init__(self, rates: object) -> None:
        super().__init__("MetaTrader5")
        self.rates = rates
        self.request: tuple[str, int, int, int] | None = None
        self.shutdown_calls = 0

    def initialize(self, **_: int | str) -> bool:
        return True

    def copy_rates_from_pos(
        self, symbol: str, timeframe: int, start_pos: int, count: int
    ) -> object:
        self.request = (symbol, timeframe, start_pos, count)
        return self.rates

    def shutdown(self) -> None:
        self.shutdown_calls += 1


def rate(time: int, open_price: float, high: float, low: float, close: float) -> dict[str, object]:
    return {
        "time": time,
        "open": open_price,
        "high": high,
        "low": low,
        "close": close,
        "tick_volume": 123,
        "spread": 15,
        "real_volume": 2.5,
    }


def test_historical_candles_exclude_current_by_default_and_sort_utc() -> None:
    fake_mt5 = FakeMt5(
        [
            rate(1_700_003_600, 1.2, 1.3, 1.1, 1.25),
            rate(1_700_000_000, 1.1, 1.2, 1.0, 1.15),
        ]
    )
    result = Mt5HistoricalDataProvider(
        Mt5TerminalAdapter(None, 10_000, module_loader=lambda _: fake_mt5)
    ).candles("EURUSDm", Timeframe.H1, 2)

    assert result.connected is True
    assert result.series is not None
    assert result.series.includes_current_candle is False
    assert [candle.open_time for candle in result.series.candles] == [
        datetime(2023, 11, 14, 22, 13, 20, tzinfo=UTC),
        datetime(2023, 11, 14, 23, 13, 20, tzinfo=UTC),
    ]
    assert fake_mt5.request == ("EURUSDm", FakeMt5.TIMEFRAME_H1, 1, 2)
    assert fake_mt5.shutdown_calls == 1


def test_historical_candles_reject_invalid_ohlc_data() -> None:
    fake_mt5 = FakeMt5([rate(1_700_000_000, 1.1, 1.15, 1.2, 1.12)])
    result = Mt5TerminalAdapter(None, 10_000, module_loader=lambda _: fake_mt5).historical_candles(
        "EURUSDm", Timeframe.H1, 1
    )

    assert result.series is None
    assert result.error_message == "MT5 returned invalid candle data."
    assert fake_mt5.shutdown_calls == 1


def test_historical_candles_accept_explicit_current_candle_request() -> None:
    fake_mt5 = FakeMt5([rate(1_700_000_000, 1.1, 1.2, 1.0, 1.15)])
    result = Mt5TerminalAdapter(None, 10_000, module_loader=lambda _: fake_mt5).historical_candles(
        "EURUSDm", Timeframe.H1, 1, include_current_candle=True
    )

    assert result.series is not None
    assert result.series.includes_current_candle is True
    assert fake_mt5.request == ("EURUSDm", FakeMt5.TIMEFRAME_H1, 0, 1)


def test_historical_candles_reject_invalid_count_without_loading_mt5() -> None:
    def unexpected_load(_: str) -> ModuleType:
        raise AssertionError("MT5 should not be loaded")

    result = Mt5TerminalAdapter(None, 10_000, module_loader=unexpected_load).historical_candles(
        "EURUSDm", Timeframe.H1, 0
    )

    assert result.series is None
    assert result.error_message == "Candle count must be between 1 and 10000."
