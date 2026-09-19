import pytest
from pydantic import ValidationError

from backend.config.settings import Settings, TradingMode


def test_settings_default_to_demo_mode() -> None:
    settings = Settings()

    assert settings.trading_mode is TradingMode.DEMO
    assert settings.live_trading_enabled is False


@pytest.mark.parametrize(
    "values",
    [{"trading_mode": "live"}, {"live_trading_enabled": True}],
)
def test_settings_reject_live_trading_configuration(values: dict[str, object]) -> None:
    with pytest.raises(ValidationError, match="Live trading cannot be enabled"):
        Settings(**values)
