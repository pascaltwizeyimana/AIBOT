"""Read-only market API. These routes contain no order or terminal-mutating operation."""

from dataclasses import asdict
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.api.dependencies import get_mt5_terminal
from backend.config.settings import Settings, get_settings
from backend.execution.mt5_terminal import Mt5TerminalAdapter
from backend.market.models import Timeframe

router = APIRouter(prefix="/market")


def unavailable(message: str | None) -> HTTPException:
    """Return a non-sensitive provider-unavailable response rather than stale or fake data."""
    return HTTPException(status_code=503, detail=message or "MT5 market data is unavailable.")


@router.get("/symbols")
def symbols(terminal: Mt5TerminalAdapter = Depends(get_mt5_terminal)) -> dict[str, object]:
    """Discover broker symbols without selecting or changing any terminal symbol."""
    result = terminal.discover_symbols()
    if not result.symbols_available or result.catalog is None:
        raise unavailable(result.error_message)
    return asdict(result.catalog)


@router.get("/snapshots/{broker_symbol}")
def snapshot(
    broker_symbol: str,
    terminal: Mt5TerminalAdapter = Depends(get_mt5_terminal),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    """Return a single fresh quote only when MT5 supplies it."""
    if not broker_symbol.strip() or len(broker_symbol) > 64:
        raise HTTPException(
            status_code=422, detail="A broker symbol between 1 and 64 characters is required."
        )
    result = terminal.market_snapshot(broker_symbol)
    if result.snapshot is None or not result.snapshot.quote_available:
        raise unavailable(result.error_message or "MT5 did not return a current quote.")
    observed_at = result.snapshot.observed_at
    assert observed_at is not None
    age_seconds = (datetime.now(UTC) - observed_at).total_seconds()
    if age_seconds > settings.market_data_max_age_seconds:
        raise unavailable("MT5 returned a stale quote.")
    return asdict(result.snapshot)


@router.get("/candles/{broker_symbol}/{timeframe}")
def candles(
    broker_symbol: str,
    timeframe: Timeframe,
    count: int = Query(default=200, ge=1, le=10_000),
    terminal: Mt5TerminalAdapter = Depends(get_mt5_terminal),
) -> dict[str, object]:
    """Return completed UTC candles only; the forming candle is never used for analysis."""
    if not broker_symbol.strip() or len(broker_symbol) > 64:
        raise HTTPException(
            status_code=422, detail="A broker symbol between 1 and 64 characters is required."
        )
    result = terminal.historical_candles(
        broker_symbol,
        timeframe,
        count,
        include_current_candle=False,
    )
    if result.series is None:
        raise unavailable(result.error_message)
    return asdict(result.series)
