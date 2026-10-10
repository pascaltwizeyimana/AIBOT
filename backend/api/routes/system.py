"""Safe system-capability endpoints for the dashboard."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.config.settings import Settings, get_settings

router = APIRouter()


class CapabilityResponse(BaseModel):
    """Public operating boundaries; intentionally excludes sensitive configuration."""

    database_configured: bool
    execution_available: bool
    demo_execution_available: bool
    live_trading_available: bool
    market_data_available: bool
    news_data_available: bool
    message: str


@router.get("/capabilities", response_model=CapabilityResponse)
def capabilities(settings: Settings = Depends(get_settings)) -> CapabilityResponse:
    """Report implemented capabilities without implying that trading is available."""
    live_available = (
        settings.trading_mode.value == "live"
        and settings.live_trading_enabled
        and settings.trading_execution_enabled
    )
    demo_available = settings.trading_mode.value == "demo" and settings.demo_execution_enabled
    return CapabilityResponse(
        database_configured=bool(settings.database_url),
        execution_available=live_available,
        demo_execution_available=demo_available,
        live_trading_available=live_available,
        market_data_available=True,
        news_data_available=False,
        message=(
            "Demo MT5 execution is enabled. Use a demo account and explicitly start automation."
            if demo_available
            else "Live execution is armed; use explicit confirmation."
            if live_available
            else (
                "Read-only MT5 market data is available; execution and news ingestion are "
                "unavailable."
            )
        ),
    )
