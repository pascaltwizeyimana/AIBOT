"""Explicit command-line retrieval of validated MT5 historical candles."""

import argparse
import json
import sys
from dataclasses import asdict

from backend.config.settings import get_settings
from backend.execution.mt5_historical_data import Mt5HistoricalDataProvider
from backend.execution.mt5_terminal import Mt5TerminalAdapter
from backend.market.models import Timeframe


def main() -> int:
    """Print chronologically ordered candles for an explicit broker symbol/timeframe."""
    parser = argparse.ArgumentParser(
        description="Read MT5 OHLCV candles without changing terminal state."
    )
    parser.add_argument("--symbol", required=True, help="Exact broker symbol, e.g. EURUSDm")
    parser.add_argument("--timeframe", choices=[item.value for item in Timeframe], default="H1")
    parser.add_argument("--count", type=int, default=50)
    parser.add_argument("--include-current", action="store_true")
    arguments = parser.parse_args()
    settings = get_settings()
    result = Mt5HistoricalDataProvider(
        Mt5TerminalAdapter(settings.mt5_terminal_path, settings.mt5_connection_timeout_ms)
    ).candles(
        arguments.symbol,
        Timeframe(arguments.timeframe),
        arguments.count,
        include_current_candle=arguments.include_current,
    )
    print(json.dumps(asdict(result), indent=2, default=str))
    return 0 if result.series is not None else 1


if __name__ == "__main__":
    sys.exit(main())
