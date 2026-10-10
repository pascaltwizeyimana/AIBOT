"""Deterministic risk calculations for MT5 order preflight."""

import math
from dataclasses import dataclass

from backend.execution.mt5_terminal import Mt5RiskContext


@dataclass(frozen=True, slots=True)
class RiskPlan:
    approved: bool
    reason: str
    risk_amount: float | None = None
    stop_distance: float | None = None
    loss_per_lot: float | None = None
    volume: float | None = None


def calculate_risk_plan(
    context: Mt5RiskContext,
    stop_loss: float,
    risk_percent: float,
) -> RiskPlan:
    """Calculate a broker-step-aligned volume without exceeding the requested risk."""
    if not context.connected or not context.account_available:
        return RiskPlan(False, "MT5 account or symbol data is unavailable.")
    if not context.trading_allowed:
        return RiskPlan(False, "MT5 account does not allow trading.")
    if (
        context.entry is None
        or context.equity is None
        or context.tick_size is None
        or context.tick_value is None
    ):
        return RiskPlan(False, "MT5 returned incomplete risk data.")
    if context.volume_min is None or context.volume_max is None or context.volume_step is None:
        return RiskPlan(False, "MT5 returned incomplete volume rules.")
    if risk_percent <= 0 or risk_percent > 2:
        return RiskPlan(False, "Risk percent must be greater than 0 and no more than 2.")
    stop_distance = abs(context.entry - stop_loss)
    if stop_distance <= 0 or context.tick_size <= 0 or context.tick_value <= 0:
        return RiskPlan(False, "Stop-loss distance and tick economics must be positive.")
    if context.stops_level_points is not None:
        if context.stops_level_points < 0:
            return RiskPlan(False, "MT5 returned invalid broker stop-distance rules.")
        if context.stops_level_points > 0:
            if context.point is None or not math.isfinite(context.point) or context.point <= 0:
                return RiskPlan(False, "MT5 returned incomplete broker stop-distance rules.")
            if stop_distance < context.stops_level_points * context.point:
                return RiskPlan(False, "Stop-loss is closer than the broker's minimum distance.")
    risk_amount = context.equity * risk_percent / 100
    loss_per_lot = stop_distance / context.tick_size * context.tick_value
    raw_volume = risk_amount / loss_per_lot
    stepped_volume = math.floor(raw_volume / context.volume_step) * context.volume_step
    volume = min(context.volume_max, stepped_volume)
    if volume < context.volume_min:
        return RiskPlan(
            False,
            "Requested risk is below the broker minimum volume.",
            risk_amount,
            stop_distance,
            loss_per_lot,
            0.0,
        )
    return RiskPlan(
        True,
        "Risk limits passed.",
        risk_amount,
        stop_distance,
        loss_per_lot,
        round(volume, 8),
    )


def calculate_position_risk(
    context: Mt5RiskContext,
    volume: float | None,
    entry_price: float | None,
    stop_loss: float | None,
) -> float | None:
    """Return the cash risk of a protected open position, or None if it is unknowable."""
    if (
        volume is None
        or volume <= 0
        or entry_price is None
        or stop_loss is None
        or context.tick_size is None
        or context.tick_value is None
        or context.tick_size <= 0
        or context.tick_value <= 0
    ):
        return None
    return abs(entry_price - stop_loss) / context.tick_size * context.tick_value * volume
