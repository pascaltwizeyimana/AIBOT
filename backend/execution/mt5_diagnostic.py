"""Explicit command-line MT5 connection diagnostic.

Run with: python -m backend.execution.mt5_diagnostic
"""

import json
import sys
from dataclasses import asdict

from backend.config.settings import get_settings
from backend.execution.mt5_terminal import Mt5TerminalAdapter


def main() -> int:
    """Run a read-only probe and return a meaningful shell exit code."""
    settings = get_settings()
    diagnostic = Mt5TerminalAdapter(
        terminal_path=settings.mt5_terminal_path,
        timeout_ms=settings.mt5_connection_timeout_ms,
    ).probe()
    print(json.dumps(asdict(diagnostic), indent=2))
    return 0 if diagnostic.connected else 1


if __name__ == "__main__":
    sys.exit(main())
