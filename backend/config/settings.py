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
    mt5_connection_timeout_ms: int = Field(default=60_000, ge=1_000, le=120_000)

    @model_validator(mode="after")
    def validate_live_trading_safety(self) -> "Settings":
        """Prevent accidental live mode through configuration alone."""
        if self.trading_mode is TradingMode.LIVE or self.live_trading_enabled:
            raise ValueError(
                "Live trading cannot be enabled by configuration. "
                "A later controlled activation workflow is required."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide immutable settings instance."""
    return Settings()
