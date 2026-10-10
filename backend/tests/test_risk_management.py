from backend.execution.mt5_terminal import Mt5RiskContext
from backend.risk.management import calculate_position_risk, calculate_risk_plan


def test_position_risk_uses_stop_distance_and_broker_tick_economics() -> None:
    context = Mt5RiskContext(
        connected=True,
        account_available=True,
        trading_allowed=True,
        tick_size=0.01,
        tick_value=1.0,
    )

    risk = calculate_position_risk(context, 0.2, 100.0, 99.5)

    assert risk == 10.0


def test_position_risk_fails_closed_without_a_stop_or_tick_data() -> None:
    context = Mt5RiskContext(
        connected=True,
        account_available=True,
        trading_allowed=True,
        tick_size=None,
        tick_value=1.0,
    )

    assert calculate_position_risk(context, 0.2, 100.0, None) is None
    assert calculate_position_risk(context, 0.2, 100.0, 99.5) is None


def test_risk_plan_rejects_stop_inside_broker_minimum_distance() -> None:
    context = Mt5RiskContext(
        connected=True,
        account_available=True,
        trading_allowed=True,
        equity=10_000.0,
        entry=1.1000,
        point=0.0001,
        tick_size=0.0001,
        tick_value=1.0,
        volume_min=0.01,
        volume_max=100.0,
        volume_step=0.01,
        stops_level_points=10,
    )

    plan = calculate_risk_plan(context, stop_loss=1.0995, risk_percent=1.0)

    assert plan.approved is False
    assert plan.reason == "Stop-loss is closer than the broker's minimum distance."
