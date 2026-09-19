"""Provider-neutral market-data contracts."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol


@dataclass(frozen=True, slots=True)
class MarketSnapshot:
    """One point-in-time quote and broker-symbol status."""

    broker_symbol: str
    quote_available: bool
    market_status: str
    observed_at: datetime | None = None
    bid: float | None = None
    ask: float | None = None
    last: float | None = None
    volume: float | None = None
    spread: float | None = None
    spread_points: float | None = None
    point: float | None = None
    digits: int | None = None
    symbol_visible: bool | None = None
    symbol_selected: bool | None = None
    symbol_trade_mode: int | None = None


@dataclass(frozen=True, slots=True)
class MarketDataResult:
    """A market snapshot or a provider failure that callers must handle safely."""

    connected: bool
    snapshot: MarketSnapshot | None = None
    error_code: int | None = None
    error_message: str | None = None


class Timeframe(StrEnum):
    """Supported candle periods, expressed using MT5's canonical identifiers."""

    M1 = "M1"
    M5 = "M5"
    M15 = "M15"
    M30 = "M30"
    H1 = "H1"
    H4 = "H4"
    D1 = "D1"
    W1 = "W1"


@dataclass(frozen=True, slots=True)
class Candle:
    """A validated completed or explicitly requested OHLCV candle in UTC."""

    open_time: datetime
    open: float
    high: float
    low: float
    close: float
    tick_volume: int
    spread_points: int
    real_volume: float


@dataclass(frozen=True, slots=True)
class CandleSeries:
    """Chronologically ordered candles for one exact broker symbol and timeframe."""

    broker_symbol: str
    timeframe: Timeframe
    includes_current_candle: bool
    candles: tuple[Candle, ...]


@dataclass(frozen=True, slots=True)
class HistoricalDataResult:
    """Historical candle series or a provider failure that callers must handle safely."""

    connected: bool
    series: CandleSeries | None = None
    error_code: int | None = None
    error_message: str | None = None


class MarketDataProvider(Protocol):
    """Interface consumed by analysis services, independent of a broker implementation."""

    def snapshot(self, broker_symbol: str) -> MarketDataResult:
        """Return one read-only quote snapshot for an explicitly supplied broker symbol."""


class HistoricalDataProvider(Protocol):
    """Interface consumed by backtesting and analysis services without broker coupling."""

    def candles(
        self,
        broker_symbol: str,
        timeframe: Timeframe,
        count: int,
        *,
        include_current_candle: bool = False,
    ) -> HistoricalDataResult:
        """Return validated UTC candles for an explicitly supplied broker symbol."""
