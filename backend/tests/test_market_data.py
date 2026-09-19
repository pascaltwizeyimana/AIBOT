from datetime import UTC, datetime
from types import ModuleType, SimpleNamespace

from backend.execution.mt5_market_data import Mt5MarketDataProvider
from backend.execution.mt5_terminal import Mt5TerminalAdapter


class FakeMt5(ModuleType):
    def __init__(self, tick: object | None) -> None:
        super().__init__("MetaTrader5")
        self.tick = tick
        self.shutdown_calls = 0
        self.symbol_info_calls: list[str] = []
        self.tick_calls: list[str] = []

    def initialize(self, **_: int | str) -> bool:
        return True

    def symbol_info(self, symbol: str) -> SimpleNamespace:
        self.symbol_info_calls.append(symbol)
        return SimpleNamespace(point=0.00001, digits=5, visible=True, select=True, trade_mode=4)

    def symbol_info_tick(self, symbol: str) -> object | None:
        self.tick_calls.append(symbol)
        return self.tick

    def shutdown(self) -> None:
        self.shutdown_calls += 1


def test_market_snapshot_maps_tick_and_calculates_spread() -> None:
    fake_mt5 = FakeMt5(
        SimpleNamespace(
            time_msc=1_700_000_000_123,
            bid=1.10000,
            ask=1.10020,
            last=1.10010,
            volume_real=2.5,
        )
    )
    provider = Mt5MarketDataProvider(
        Mt5TerminalAdapter(None, 10_000, module_loader=lambda _: fake_mt5)
    )

    result = provider.snapshot("EURUSDm")

    assert result.connected is True
    assert result.snapshot is not None
    assert result.snapshot.market_status == "active"
    assert result.snapshot.observed_at == datetime(2023, 11, 14, 22, 13, 20, 123000, tzinfo=UTC)
    assert result.snapshot.spread == 0.0002
    assert result.snapshot.spread_points == 20.0
    assert fake_mt5.symbol_info_calls == ["EURUSDm"]
    assert fake_mt5.tick_calls == ["EURUSDm"]
    assert fake_mt5.shutdown_calls == 1


def test_market_snapshot_does_not_claim_market_closed_when_tick_is_unavailable() -> None:
    fake_mt5 = FakeMt5(tick=None)
    result = Mt5MarketDataProvider(
        Mt5TerminalAdapter(None, 10_000, module_loader=lambda _: fake_mt5)
    ).snapshot("EURUSDm")

    assert result.snapshot is not None
    assert result.snapshot.quote_available is False
    assert result.snapshot.market_status == "unknown"
    assert fake_mt5.shutdown_calls == 1


def test_market_snapshot_rejects_empty_symbol_without_loading_mt5() -> None:
    def unexpected_load(_: str) -> ModuleType:
        raise AssertionError("MT5 should not be loaded")

    result = Mt5TerminalAdapter(None, 10_000, module_loader=unexpected_load).market_snapshot("  ")

    assert result.connected is False
    assert result.snapshot is None
    assert result.error_message == "A non-empty broker symbol is required."
