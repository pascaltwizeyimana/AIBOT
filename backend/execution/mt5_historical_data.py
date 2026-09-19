"""Read-only MT5 implementation of the historical-data provider contract."""

from dataclasses import dataclass

from backend.execution.mt5_terminal import Mt5TerminalAdapter
from backend.market.models import HistoricalDataResult, Timeframe


@dataclass(frozen=True, slots=True)
class Mt5HistoricalDataProvider:
    """MT5-backed historical-data provider with no execution methods."""

    terminal: Mt5TerminalAdapter

    def candles(
        self,
        broker_symbol: str,
        timeframe: Timeframe,
        count: int,
        *,
        include_current_candle: bool = False,
    ) -> HistoricalDataResult:
        """Read one validated series through the terminal lifecycle adapter."""
        return self.terminal.historical_candles(
            broker_symbol,
            timeframe,
            count,
            include_current_candle=include_current_candle,
        )
