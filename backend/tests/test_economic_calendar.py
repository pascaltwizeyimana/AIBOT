import json
from datetime import UTC, datetime, timedelta
from io import BytesIO

import pytest

from backend.config.settings import Settings
from backend.news.economic_calendar import (
    EconomicCalendarClient,
    EconomicCalendarError,
)


class CalendarResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._content = BytesIO(json.dumps(payload).encode())

    def __enter__(self) -> "CalendarResponse":
        return self

    def __exit__(self, *_: object) -> None:
        self._content.close()

    def read(self) -> bytes:
        return self._content.read()


def test_blackout_window_includes_both_thirty_minute_boundaries() -> None:
    now = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)

    assert EconomicCalendarClient.within_blackout(now - timedelta(minutes=30), now)
    assert EconomicCalendarClient.within_blackout(now + timedelta(minutes=30), now)
    assert not EconomicCalendarClient.within_blackout(now - timedelta(minutes=31), now)
    assert not EconomicCalendarClient.within_blackout(now + timedelta(minutes=31), now)


def test_calendar_keeps_only_high_impact_usd_events(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
    payload = {
        "updated_at": now.isoformat(),
        "events": [
            {"currency": "USD", "impact": "high", "event": "CPI", "time": now.isoformat()},
            {"currency": "USD", "impact": "low", "event": "Auction", "time": now.isoformat()},
            {"currency": "EUR", "impact": "high", "event": "CPI", "time": now.isoformat()},
        ],
    }
    monkeypatch.setattr(
        "backend.news.economic_calendar.urlopen",
        lambda *_args, **_kwargs: CalendarResponse(payload),
    )

    events = EconomicCalendarClient().high_impact_usd_events(
        Settings(economic_calendar_url="https://calendar.invalid/events"),
        now,
    )

    assert [event.name for event in events] == ["CPI"]


def test_calendar_rejects_stale_feed(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
    payload = {"updated_at": (now - timedelta(minutes=16)).isoformat(), "events": []}
    monkeypatch.setattr(
        "backend.news.economic_calendar.urlopen",
        lambda *_args, **_kwargs: CalendarResponse(payload),
    )

    with pytest.raises(EconomicCalendarError, match="stale"):
        EconomicCalendarClient().high_impact_usd_events(
            Settings(economic_calendar_url="https://calendar.invalid/events"),
            now,
        )
