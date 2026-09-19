"""Explicit command-line real-time MT5 quote snapshot."""

import argparse
import json
import sys
from dataclasses import asdict

from backend.config.settings import get_settings
from backend.execution.mt5_market_data import Mt5MarketDataProvider
from backend.execution.mt5_terminal import Mt5TerminalAdapter


def main() -> int:
    """Print a quote for an explicitly requested broker symbol."""
    parser = argparse.ArgumentParser(
        description="Read one MT5 quote without changing terminal state."
    )
    parser.add_argument("--symbol", required=True, help="Exact broker symbol, e.g. EURUSDm")
    arguments = parser.parse_args()
    settings = get_settings()
    result = Mt5MarketDataProvider(
        Mt5TerminalAdapter(settings.mt5_terminal_path, settings.mt5_connection_timeout_ms)
    ).snapshot(arguments.symbol)
    print(json.dumps(asdict(result), indent=2, default=str))
    return 0 if result.snapshot is not None and result.snapshot.quote_available else 1


if __name__ == "__main__":
    sys.exit(main())
