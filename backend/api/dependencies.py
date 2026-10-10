"""Safe dependency factories for external read-only providers."""

from fastapi import Depends

from backend.config.settings import Settings, get_settings
from backend.execution.mt5_terminal import Mt5TerminalAdapter


def get_mt5_terminal(settings: Settings = Depends(get_settings)) -> Mt5TerminalAdapter:
    """Create a short-lived read-only MT5 adapter without accepting credentials."""
    return Mt5TerminalAdapter(
        terminal_path=settings.mt5_terminal_path,
        timeout_ms=settings.mt5_connection_timeout_ms,
    )
