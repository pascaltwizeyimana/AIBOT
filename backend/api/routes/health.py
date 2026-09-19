"""Non-sensitive service health endpoint."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.config.settings import Settings, get_settings

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    environment: str
    trading_mode: str
    live_trading_enabled: bool


@router.get("/health", response_model=HealthResponse)
def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    """Report application status without revealing credentials or account data."""
    return HealthResponse(
        status="ok",
        environment=settings.app_env,
        trading_mode=settings.trading_mode,
        live_trading_enabled=settings.live_trading_enabled,
    )
