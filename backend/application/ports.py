"""Provider contracts; concrete MT5/news/database implementations arrive in later phases."""

from datetime import datetime
from typing import Protocol

from backend.domain.models import BrokerSymbol, MarketBar


class MarketDataProvider(Protocol):
    def discover_symbols(self) -> list[BrokerSymbol]: ...

    def completed_bars(
        self, symbol: str, timeframe: str, end_at: datetime, limit: int
    ) -> list[MarketBar]: ...


class EconomicCalendarProvider(Protocol):
    def has_current_data(self, now: datetime) -> bool: ...


class ExecutionGateway(Protocol):
    """Reserved for a later demo-only execution phase; it must not bypass risk validation."""

    def is_available(self) -> bool: ...
