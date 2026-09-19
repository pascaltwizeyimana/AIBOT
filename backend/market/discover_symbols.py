"""Explicit command-line broker symbol discovery.

Run with: python -m backend.market.discover_symbols
"""

import json
import sys
from dataclasses import asdict

from backend.config.settings import get_settings
from backend.execution.mt5_terminal import Mt5TerminalAdapter


def main() -> int:
    """Print the read-only catalog and return non-zero on a provider failure."""
    settings = get_settings()
    discovery = Mt5TerminalAdapter(
        terminal_path=settings.mt5_terminal_path,
        timeout_ms=settings.mt5_connection_timeout_ms,
    ).discover_symbols()
    print(json.dumps(asdict(discovery), indent=2))
    return 0 if discovery.symbols_available else 1


if __name__ == "__main__":
    sys.exit(main())
