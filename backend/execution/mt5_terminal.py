"""Read-only MetaTrader 5 terminal lifecycle adapter.

This module intentionally provides no login, account, market-data, or trading methods.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib import import_module
from types import ModuleType

from backend.market.models import (
    Candle,
    CandleSeries,
    HistoricalDataResult,
    MarketDataResult,
    MarketSnapshot,
    Timeframe,
)
from backend.market.symbols import SymbolCatalog


@dataclass(frozen=True, slots=True)
class Mt5Diagnostic:
    """Safe result of an explicit terminal connection probe."""

    connected: bool
    package_available: bool
    terminal_version: str | None = None
    error_code: int | None = None
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class Mt5AccountSnapshot:
    """A non-sensitive, read-only subset of the current MT5 account state."""

    connected: bool
    account_available: bool
    account_id_masked: str | None = None
    trade_mode: str | None = None
    currency: str | None = None
    balance: float | None = None
    equity: float | None = None
    margin: float | None = None
    margin_free: float | None = None
    margin_level: float | None = None
    trading_allowed: bool | None = None
    error_code: int | None = None
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class Mt5SymbolDiscovery:
    """Safe result of a broker-symbol catalog read."""

    connected: bool
    symbols_available: bool
    catalog: SymbolCatalog | None = None
    error_code: int | None = None
    error_message: str | None = None


Mt5MarketSnapshotResult = MarketDataResult


class Mt5TerminalAdapter:
    """Explicit lifecycle adapter for terminal initialization and shutdown only."""

    def __init__(
        self,
        terminal_path: str | None,
        timeout_ms: int,
        module_loader: Callable[[str], ModuleType] = import_module,
    ) -> None:
        self._terminal_path = terminal_path
        self._timeout_ms = timeout_ms
        self._module_loader = module_loader
        self._mt5: ModuleType | None = None

    def probe(self) -> Mt5Diagnostic:
        """Initialize, inspect version, then always close the terminal connection.

        No credentials are passed to MetaTrader 5. The official API may locate or launch a
        terminal during initialization, so this operation is exposed only through an explicit CLI.
        """
        try:
            initialisation_failure = self._initialize()
            if initialisation_failure is not None:
                return initialisation_failure

            assert self._mt5 is not None
            version = self._mt5.version()
            return Mt5Diagnostic(
                connected=True,
                package_available=True,
                terminal_version=".".join(str(part) for part in version),
            )
        except Exception as exc:  # Broker library exceptions must never crash the API process.
            return Mt5Diagnostic(
                connected=False,
                package_available=True,
                error_message=f"MT5 terminal diagnostic failed: {type(exc).__name__}.",
            )
        finally:
            self._shutdown()

    def account_snapshot(self) -> Mt5AccountSnapshot:
        """Read the active terminal account without calling the MT5 login function."""
        try:
            initialisation_failure = self._initialize()
            if initialisation_failure is not None:
                return Mt5AccountSnapshot(
                    connected=False,
                    account_available=False,
                    error_code=initialisation_failure.error_code,
                    error_message=initialisation_failure.error_message,
                )

            assert self._mt5 is not None
            account = self._mt5.account_info()
            if account is None:
                error_code, error_message = self._last_error()
                return Mt5AccountSnapshot(
                    connected=True,
                    account_available=False,
                    error_code=error_code,
                    error_message=error_message,
                )

            return Mt5AccountSnapshot(
                connected=True,
                account_available=True,
                account_id_masked=self._mask_account_id(getattr(account, "login", None)),
                trade_mode=self._trade_mode_name(getattr(account, "trade_mode", None)),
                currency=self._value_as_str(getattr(account, "currency", None)),
                balance=self._value_as_float(getattr(account, "balance", None)),
                equity=self._value_as_float(getattr(account, "equity", None)),
                margin=self._value_as_float(getattr(account, "margin", None)),
                margin_free=self._value_as_float(getattr(account, "margin_free", None)),
                margin_level=self._value_as_float(getattr(account, "margin_level", None)),
                trading_allowed=bool(getattr(account, "trade_allowed", False)),
            )
        except Exception as exc:
            return Mt5AccountSnapshot(
                connected=False,
                account_available=False,
                error_message=f"MT5 account probe failed: {type(exc).__name__}.",
            )
        finally:
            self._shutdown()

    def discover_symbols(self) -> Mt5SymbolDiscovery:
        """Read the broker catalog without changing Market Watch or trading state."""
        try:
            initialisation_failure = self._initialize()
            if initialisation_failure is not None:
                return Mt5SymbolDiscovery(
                    connected=False,
                    symbols_available=False,
                    error_code=initialisation_failure.error_code,
                    error_message=initialisation_failure.error_message,
                )

            assert self._mt5 is not None
            symbols = self._mt5.symbols_get()
            if symbols is None:
                error_code, error_message = self._last_error()
                return Mt5SymbolDiscovery(
                    connected=True,
                    symbols_available=False,
                    error_code=error_code,
                    error_message=error_message,
                )
            return Mt5SymbolDiscovery(
                connected=True,
                symbols_available=True,
                catalog=SymbolCatalog.from_mt5_symbols(symbols),
            )
        except Exception as exc:
            return Mt5SymbolDiscovery(
                connected=False,
                symbols_available=False,
                error_message=f"MT5 symbol discovery failed: {type(exc).__name__}.",
            )
        finally:
            self._shutdown()

    def market_snapshot(self, broker_symbol: str) -> Mt5MarketSnapshotResult:
        """Read one selected broker symbol without modifying terminal state."""
        if not broker_symbol.strip():
            return Mt5MarketSnapshotResult(
                connected=False,
                error_message="A non-empty broker symbol is required.",
            )
        try:
            initialisation_failure = self._initialize()
            if initialisation_failure is not None:
                return Mt5MarketSnapshotResult(
                    connected=False,
                    error_code=initialisation_failure.error_code,
                    error_message=initialisation_failure.error_message,
                )

            assert self._mt5 is not None
            symbol = self._mt5.symbol_info(broker_symbol)
            if symbol is None:
                error_code, error_message = self._last_error()
                return Mt5MarketSnapshotResult(
                    connected=True,
                    error_code=error_code,
                    error_message=error_message,
                )

            tick = self._mt5.symbol_info_tick(broker_symbol)
            return Mt5MarketSnapshotResult(
                connected=True,
                snapshot=self._build_market_snapshot(broker_symbol, symbol, tick),
            )
        except Exception as exc:
            return Mt5MarketSnapshotResult(
                connected=False,
                error_message=f"MT5 market snapshot failed: {type(exc).__name__}.",
            )
        finally:
            self._shutdown()

    def historical_candles(
        self,
        broker_symbol: str,
        timeframe: Timeframe,
        count: int,
        *,
        include_current_candle: bool = False,
    ) -> HistoricalDataResult:
        """Read validated historical OHLCV candles without changing terminal state."""
        if not broker_symbol.strip():
            return HistoricalDataResult(
                connected=False, error_message="A non-empty broker symbol is required."
            )
        if not 1 <= count <= 10_000:
            return HistoricalDataResult(
                connected=False,
                error_message="Candle count must be between 1 and 10000.",
            )
        try:
            initialisation_failure = self._initialize()
            if initialisation_failure is not None:
                return HistoricalDataResult(
                    connected=False,
                    error_code=initialisation_failure.error_code,
                    error_message=initialisation_failure.error_message,
                )

            assert self._mt5 is not None
            mt5_timeframe = getattr(self._mt5, f"TIMEFRAME_{timeframe.value}", None)
            if mt5_timeframe is None:
                return HistoricalDataResult(
                    connected=True,
                    error_message=f"MT5 does not expose timeframe {timeframe.value}.",
                )
            start_pos = 0 if include_current_candle else 1
            rates = self._mt5.copy_rates_from_pos(broker_symbol, mt5_timeframe, start_pos, count)
            if rates is None:
                error_code, error_message = self._last_error()
                return HistoricalDataResult(
                    connected=True,
                    error_code=error_code,
                    error_message=error_message,
                )
            candles = self._validated_candles(rates)
            if not candles:
                return HistoricalDataResult(
                    connected=True,
                    error_message="MT5 returned no historical candles.",
                )
            return HistoricalDataResult(
                connected=True,
                series=CandleSeries(
                    broker_symbol=broker_symbol,
                    timeframe=timeframe,
                    includes_current_candle=include_current_candle,
                    candles=candles,
                ),
            )
        except (TypeError, ValueError, KeyError):
            return HistoricalDataResult(
                connected=True,
                error_message="MT5 returned invalid candle data.",
            )
        except Exception as exc:
            return HistoricalDataResult(
                connected=False,
                error_message=f"MT5 historical candle request failed: {type(exc).__name__}.",
            )
        finally:
            self._shutdown()

    def _initialize(self) -> Mt5Diagnostic | None:
        """Load the MT5 package and establish a terminal connection without credentials."""
        try:
            self._mt5 = self._module_loader("MetaTrader5")
        except ModuleNotFoundError:
            return Mt5Diagnostic(
                connected=False,
                package_available=False,
                error_message="MetaTrader5 Python package is not installed.",
            )

        options: dict[str, int | str] = {"timeout": self._timeout_ms}
        if self._terminal_path:
            options["path"] = self._terminal_path
        if self._mt5.initialize(**options):
            return None

        error_code, error_message = self._last_error()
        return Mt5Diagnostic(
            connected=False,
            package_available=True,
            error_code=error_code,
            error_message=error_message,
        )

    def _shutdown(self) -> None:
        """Close an active terminal connection without masking the primary result."""
        if self._mt5 is None:
            return
        try:
            self._mt5.shutdown()
        except Exception:
            logging.getLogger(__name__).exception("mt5_shutdown_failed")
        finally:
            self._mt5 = None

    def _last_error(self) -> tuple[int | None, str | None]:
        """Read a provider error defensively because error payloads are external data."""
        if self._mt5 is None:
            return None, None
        result = self._mt5.last_error()
        if not isinstance(result, tuple) or len(result) < 2:
            return None, "MT5 returned an unrecognized error payload."
        return int(result[0]), str(result[1])

    @staticmethod
    def _build_market_snapshot(
        broker_symbol: str, symbol: object, tick: object | None
    ) -> MarketSnapshot:
        """Convert external MT5 named tuples into a stable provider-neutral model."""
        point = Mt5TerminalAdapter._value_as_float(getattr(symbol, "point", None))
        digits = Mt5TerminalAdapter._value_as_int(getattr(symbol, "digits", None))
        common = {
            "broker_symbol": broker_symbol,
            "point": point,
            "digits": digits,
            "symbol_visible": bool(getattr(symbol, "visible", False)),
            "symbol_selected": bool(getattr(symbol, "select", False)),
            "symbol_trade_mode": Mt5TerminalAdapter._value_as_int(
                getattr(symbol, "trade_mode", None)
            ),
        }
        if tick is None:
            return MarketSnapshot(quote_available=False, market_status="unknown", **common)

        bid = Mt5TerminalAdapter._value_as_float(getattr(tick, "bid", None))
        ask = Mt5TerminalAdapter._value_as_float(getattr(tick, "ask", None))
        spread = ask - bid if ask is not None and bid is not None else None
        if spread is not None and digits is not None:
            spread = round(spread, digits)
        spread_points = (
            round(spread / point, 6) if spread is not None and point and point > 0 else None
        )
        observed_at = Mt5TerminalAdapter._tick_time(getattr(tick, "time_msc", None))
        quote_available = bid is not None and ask is not None and observed_at is not None
        return MarketSnapshot(
            quote_available=quote_available,
            market_status="active" if quote_available else "unknown",
            observed_at=observed_at,
            bid=bid,
            ask=ask,
            last=Mt5TerminalAdapter._value_as_float(getattr(tick, "last", None)),
            volume=Mt5TerminalAdapter._value_as_float(getattr(tick, "volume_real", None)),
            spread=spread,
            spread_points=spread_points,
            **common,
        )

    @staticmethod
    def _validated_candles(rates: object) -> tuple[Candle, ...]:
        """Convert MT5 records to chronologically ordered, validated UTC candles."""
        candles = tuple(
            sorted(
                (Mt5TerminalAdapter._to_candle(rate) for rate in rates),
                key=lambda candle: candle.open_time,
            )
        )
        if len({candle.open_time for candle in candles}) != len(candles):
            raise ValueError("duplicate candle times")
        return candles

    @staticmethod
    def _to_candle(rate: object) -> Candle:
        """Validate one externally sourced rate record before it reaches analysis code."""
        open_time = datetime.fromtimestamp(int(rate["time"]), tz=UTC)
        open_price = float(rate["open"])
        high = float(rate["high"])
        low = float(rate["low"])
        close = float(rate["close"])
        if low > min(open_price, close) or high < max(open_price, close) or low > high:
            raise ValueError("invalid OHLC")
        return Candle(
            open_time=open_time,
            open=open_price,
            high=high,
            low=low,
            close=close,
            tick_volume=int(rate["tick_volume"]),
            spread_points=int(rate["spread"]),
            real_volume=float(rate["real_volume"]),
        )

    @staticmethod
    def _mask_account_id(account_id: object) -> str | None:
        if account_id is None:
            return None
        value = str(account_id)
        return f"***{value[-4:]}" if len(value) > 4 else "***"

    @staticmethod
    def _trade_mode_name(trade_mode: object) -> str:
        names = {0: "demo", 1: "contest", 2: "real"}
        return names.get(trade_mode, "unknown")

    @staticmethod
    def _value_as_float(value: object) -> float | None:
        return float(value) if value is not None else None

    @staticmethod
    def _value_as_int(value: object) -> int | None:
        return int(value) if value is not None else None

    @staticmethod
    def _value_as_str(value: object) -> str | None:
        return str(value) if value is not None else None

    @staticmethod
    def _tick_time(value: object) -> datetime | None:
        """Convert MT5 millisecond timestamps into timezone-aware UTC datetimes."""
        if value is None:
            return None
        return datetime.fromtimestamp(int(value) / 1_000, tz=UTC)
