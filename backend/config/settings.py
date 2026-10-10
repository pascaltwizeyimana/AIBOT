"""Centralized, validated application settings.

No credential is defined here. Secrets are read from environment variables only.
"""

from enum import StrEnum
from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class TradingMode(StrEnum):
    """Permitted operational modes for the platform."""

    DEMO = "demo"
    PAPER = "paper"
    LIVE = "live"


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables and an optional .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "AI Trading Platform"
    app_env: str = "development"
    log_level: str = "INFO"
    api_host: str = "127.0.0.1"
    api_port: int = Field(default=8000, ge=1, le=65535)
    trading_mode: TradingMode = TradingMode.DEMO
    live_trading_enabled: bool = False
    mt5_terminal_path: str | None = None
    auto_start_mt5: bool = False
    mt5_connection_timeout_ms: int = Field(default=60_000, ge=1_000, le=120_000)
    demo_execution_enabled: bool = False
    max_demo_lots: float = Field(default=0.1, gt=0, le=1.0)
    demo_auto_trade_max_risk_percent: float = Field(default=0.25, gt=0, le=0.5)
    live_trading_confirmation: str | None = None
    max_live_lots: float = Field(default=0.1, gt=0, le=1.0)
    live_auto_max_risk_percent: float = Field(default=0.25, gt=0, le=0.5)
    live_auto_max_session_loss_percent: float = Field(default=1.0, gt=0, le=5.0)
    live_auto_max_open_risk_percent: float = Field(default=0.75, gt=0, le=2.0)
    live_auto_max_positions: int = Field(default=3, ge=1, le=10)
    live_auto_max_orders: int = Field(default=3, ge=1, le=10)
    economic_calendar_url: str | None = None
    economic_calendar_timeout_seconds: float = Field(default=5.0, gt=0, le=30)
    economic_calendar_max_age_seconds: int = Field(default=900, ge=60, le=3600)
    market_data_max_age_seconds: int = Field(default=10, ge=1, le=300)
    market_data_max_spread_points: float = Field(default=50, gt=0, le=100_000)
    database_url: str | None = None
    cors_origins: tuple[str, ...] = (
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5175",
    )
    trading_execution_enabled: bool = False

    @model_validator(mode="after")
    def validate_live_trading_safety(self) -> "Settings":
        """Require every explicit gate before allowing a live configuration."""
        live_flags = (
            self.trading_mode == TradingMode.LIVE
            or self.live_trading_enabled
            or self.trading_execution_enabled
        )
        live_ready = (
            self.trading_mode == TradingMode.LIVE
            and self.live_trading_enabled
            and self.trading_execution_enabled
        )
        if live_flags and (
            not live_ready or self.live_trading_confirmation != "I_UNDERSTAND_LIVE_TRADING"
        ):
            raise ValueError(
                "Trading execution cannot be enabled by configuration alone. Live trading requires "
                "TRADING_MODE=live, LIVE_TRADING_ENABLED=true, "
                "TRADING_EXECUTION_ENABLED=true, and LIVE_TRADING_CONFIRMATION="
                "I_UNDERSTAND_LIVE_TRADING."
            )
        if self.demo_execution_enabled and self.trading_mode != TradingMode.DEMO:
            raise ValueError("Demo execution requires TRADING_MODE=demo.")
        return self


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide immutable settings instance."""
    return Settings()
