"""Explicit command-line read-only account probe.

Run with: python -m backend.execution.mt5_account
"""

import json
import sys
from dataclasses import asdict

from backend.config.settings import get_settings
from backend.execution.mt5_terminal import Mt5TerminalAdapter


def main() -> int:
    """Print a redacted account snapshot without sending an MT5 login request."""
    settings = get_settings()
    snapshot = Mt5TerminalAdapter(
        terminal_path=settings.mt5_terminal_path,
        timeout_ms=settings.mt5_connection_timeout_ms,
    ).account_snapshot()
    print(json.dumps(asdict(snapshot), indent=2))
    return 0 if snapshot.account_available else 1


if __name__ == "__main__":
    sys.exit(main())
