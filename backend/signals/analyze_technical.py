"""Explicit command-line technical analysis of completed MT5 candles."""

import argparse
import json
import sys
from dataclasses import asdict

from backend.config.settings import get_settings
from backend.execution.mt5_historical_data import Mt5HistoricalDataProvider
from backend.execution.mt5_terminal import Mt5TerminalAdapter
from backend.market.models import Timeframe
from backend.signals.technical import TechnicalAnalyzer


def main() -> int:
    """Retrieve completed candles and print deterministic indicator values."""
    parser = argparse.ArgumentParser(description="Analyze completed MT5 candles without trading.")
    parser.add_argument("--symbol", required=True, help="Exact broker symbol, e.g. EURUSDm")
    parser.add_argument("--timeframe", choices=[item.value for item in Timeframe], default="H1")
    parser.add_argument("--count", type=int, default=100)
    arguments = parser.parse_args()
    settings = get_settings()
    result = Mt5HistoricalDataProvider(
        Mt5TerminalAdapter(settings.mt5_terminal_path, settings.mt5_connection_timeout_ms)
    ).candles(arguments.symbol, Timeframe(arguments.timeframe), arguments.count)
    if result.series is None:
        print(json.dumps(asdict(result), indent=2, default=str))
        return 1
    analysis = TechnicalAnalyzer().analyze(result.series)
    print(json.dumps(asdict(analysis), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
