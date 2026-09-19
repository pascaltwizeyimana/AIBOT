"""Broker-symbol discovery and conservative logical-instrument normalization."""

import re
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

# Currency, metal, and major crypto codes are logical asset codes, not broker names.
_ASSET_CODES = frozenset(
    {
        "AED",
        "AUD",
        "BTC",
        "CAD",
        "CHF",
        "CNY",
        "CZK",
        "DKK",
        "ETH",
        "EUR",
        "GBP",
        "HKD",
        "HUF",
        "JPY",
        "LTC",
        "MXN",
        "NOK",
        "NZD",
        "PLN",
        "SEK",
        "SGD",
        "SOL",
        "TRY",
        "USD",
        "XAG",
        "XAU",
        "XRP",
        "ZAR",
    }
)


@dataclass(frozen=True, slots=True)
class BrokerSymbol:
    """Read-only description of one broker-provided instrument."""

    broker_symbol: str
    logical_symbol: str | None
    visible: bool
    selected: bool
    path: str | None
    trade_mode: int | None


@dataclass(frozen=True, slots=True)
class SymbolCatalog:
    """Complete broker catalog plus mappings that are safe to use automatically."""

    symbols: tuple[BrokerSymbol, ...]
    unambiguous_mappings: dict[str, str]
    ambiguous_mappings: dict[str, tuple[str, ...]]

    @classmethod
    def from_mt5_symbols(cls, symbols: Iterable[object]) -> "SymbolCatalog":
        """Build a catalog without changing Market Watch or selecting symbols."""
        records = tuple(
            BrokerSymbol(
                broker_symbol=str(getattr(symbol, "name")),
                logical_symbol=logical_symbol_for(str(getattr(symbol, "name"))),
                visible=bool(getattr(symbol, "visible", False)),
                selected=bool(getattr(symbol, "select", False)),
                path=value_as_str(getattr(symbol, "path", None)),
                trade_mode=value_as_int(getattr(symbol, "trade_mode", None)),
            )
            for symbol in symbols
        )
        candidates: defaultdict[str, list[str]] = defaultdict(list)
        for record in records:
            if record.logical_symbol is not None:
                candidates[record.logical_symbol].append(record.broker_symbol)

        unambiguous = {
            logical: broker_symbols[0]
            for logical, broker_symbols in candidates.items()
            if len(broker_symbols) == 1
        }
        ambiguous = {
            logical: tuple(sorted(broker_symbols))
            for logical, broker_symbols in candidates.items()
            if len(broker_symbols) > 1
        }
        return cls(
            symbols=tuple(sorted(records, key=lambda record: record.broker_symbol)),
            unambiguous_mappings=dict(sorted(unambiguous.items())),
            ambiguous_mappings=dict(sorted(ambiguous.items())),
        )


def logical_symbol_for(broker_symbol: str) -> str | None:
    """Extract one recognized six-code instrument from a broker-specific name.

    A name that contains zero or multiple candidates is intentionally left unmapped.
    """
    letters_only = re.sub(r"[^A-Z]", "", broker_symbol.upper())
    candidates = {
        letters_only[index : index + 6]
        for index in range(len(letters_only) - 5)
        if letters_only[index : index + 3] in _ASSET_CODES
        and letters_only[index + 3 : index + 6] in _ASSET_CODES
    }
    return next(iter(candidates)) if len(candidates) == 1 else None


def value_as_int(value: object) -> int | None:
    """Convert optional MT5 integer values defensively."""
    return int(value) if value is not None else None


def value_as_str(value: object) -> str | None:
    """Convert optional MT5 string values defensively."""
    return str(value) if value is not None else None
