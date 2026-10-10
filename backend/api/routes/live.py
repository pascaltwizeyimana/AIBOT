"""Live, read-only MT5 stream for dashboard updates."""

import asyncio
from dataclasses import asdict

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder

from backend.api.dependencies import get_mt5_terminal
from backend.config.settings import get_settings
from backend.execution.mt5_terminal import Mt5TerminalAdapter

router = APIRouter()


@router.get("/mt5/status")
def mt5_status(terminal: Mt5TerminalAdapter = Depends(get_mt5_terminal)) -> dict[str, object]:
    """Return an explicit connection probe; this endpoint never claims a connection by default."""
    return asdict(terminal.probe())


@router.get("/mt5/account")
def mt5_account(terminal: Mt5TerminalAdapter = Depends(get_mt5_terminal)) -> dict[str, object]:
    """Return the active MT5 account snapshot when the terminal supplies one."""
    return asdict(terminal.account_snapshot())


@router.websocket("/ws/market/{broker_symbol}")
async def market_stream(
    websocket: WebSocket,
    broker_symbol: str,
) -> None:
    """Push fresh MT5 quotes; failed reads are sent as unavailable states, never fake prices."""
    await websocket.accept()
    settings = get_settings()
    terminal = Mt5TerminalAdapter(
        terminal_path=settings.mt5_terminal_path,
        timeout_ms=settings.mt5_connection_timeout_ms,
    )
    try:
        while True:
            snapshot = terminal.market_snapshot(broker_symbol)
            await websocket.send_json(jsonable_encoder({"type": "quote", **asdict(snapshot)}))
            await asyncio.sleep(1)
    except (WebSocketDisconnect, RuntimeError):
        return
