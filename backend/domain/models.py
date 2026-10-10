"""Core immutable types shared by later trading-system phases."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class Decision(StrEnum):
    BUY = "buy"
    SELL = "sell"
    NO_TRADE = "no_trade"


class AssetClass(StrEnum):
    FOREX = "forex"
    METAL = "metal"
    INDEX = "index"
    CRYPTO = "crypto"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class BrokerSymbol:
    broker_name: str
    canonical_name: str
    asset_class: AssetClass
    tick_size: Decimal
    tick_value: Decimal
    volume_min: Decimal
    volume_max: Decimal
    volume_step: Decimal


@dataclass(frozen=True, slots=True)
class MarketBar:
    symbol: str
    timeframe: str
    opened_at: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    tick_volume: int
    is_complete: bool
