from types import ModuleType, SimpleNamespace

from backend.execution.mt5_terminal import Mt5TerminalAdapter
from backend.market.symbols import SymbolCatalog, logical_symbol_for


def test_logical_symbol_normalizes_common_broker_suffixes_and_prefixes() -> None:
    assert logical_symbol_for("EURUSD") == "EURUSD"
    assert logical_symbol_for("EURUSDm") == "EURUSD"
    assert logical_symbol_for("EURUSD.a") == "EURUSD"
    assert logical_symbol_for("FX_XAUUSDz") == "XAUUSD"


def test_logical_symbol_rejects_unknown_or_ambiguous_names() -> None:
    assert logical_symbol_for("US500") is None
    assert logical_symbol_for("EURUSDGBPUSD") is None


def test_catalog_preserves_symbols_and_does_not_choose_ambiguous_mapping() -> None:
    catalog = SymbolCatalog.from_mt5_symbols(
        [
            SimpleNamespace(name="EURUSD", visible=True, select=True, path="Forex", trade_mode=4),
            SimpleNamespace(
                name="EURUSDm", visible=False, select=False, path="Forex", trade_mode=4
            ),
            SimpleNamespace(name="XAUUSDz", visible=True, select=True, path="Metals", trade_mode=4),
            SimpleNamespace(name="US500", visible=True, select=False, path="Indices", trade_mode=4),
        ]
    )

    assert [symbol.broker_symbol for symbol in catalog.symbols] == [
        "EURUSD",
        "EURUSDm",
        "US500",
        "XAUUSDz",
    ]
    assert catalog.unambiguous_mappings == {"XAUUSD": "XAUUSDz"}
    assert catalog.ambiguous_mappings == {"EURUSD": ("EURUSD", "EURUSDm")}


class FakeMt5(ModuleType):
    def __init__(self) -> None:
        super().__init__("MetaTrader5")
        self.shutdown_calls = 0

    def initialize(self, **_: int | str) -> bool:
        return True

    def symbols_get(self) -> tuple[SimpleNamespace, ...]:
        return (
            SimpleNamespace(name="XAUUSDm", visible=True, select=True, path="Metals", trade_mode=4),
        )

    def shutdown(self) -> None:
        self.shutdown_calls += 1


def test_mt5_discovery_is_read_only_and_closes_connection() -> None:
    fake_mt5 = FakeMt5()
    result = Mt5TerminalAdapter(
        terminal_path=None,
        timeout_ms=10_000,
        module_loader=lambda _: fake_mt5,
    ).discover_symbols()

    assert result.connected is True
    assert result.symbols_available is True
    assert result.catalog is not None
    assert result.catalog.unambiguous_mappings == {"XAUUSD": "XAUUSDm"}
    assert fake_mt5.shutdown_calls == 1
