"""Read-only MT5 implementation of the market-data provider contract."""

from dataclasses import dataclass

from backend.execution.mt5_terminal import Mt5MarketSnapshotResult, Mt5TerminalAdapter


@dataclass(frozen=True, slots=True)
class Mt5MarketDataProvider:
    """MT5-backed provider; it has no trade or symbol-selection methods."""

    terminal: Mt5TerminalAdapter

    def snapshot(self, broker_symbol: str) -> Mt5MarketSnapshotResult:
        """Read one quote through the terminal lifecycle adapter."""
        return self.terminal.market_snapshot(broker_symbol)
