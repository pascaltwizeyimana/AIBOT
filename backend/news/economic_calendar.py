"""Strict reader for a configured economic-calendar JSON feed."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.error import URLError
from urllib.request import urlopen

from backend.config.settings import Settings


@dataclass(frozen=True, slots=True)
class EconomicEvent:
    name: str
    currency: str
    impact: str
    event_time: datetime


class EconomicCalendarError(ValueError):
    """Calendar data could not be trusted for a trading decision."""


class EconomicCalendarClient:
    """Fetch and validate an operator-configured calendar feed."""

    def high_impact_usd_events(
        self,
        settings: Settings,
        now: datetime | None = None,
    ) -> tuple[EconomicEvent, ...]:
        if not settings.economic_calendar_url:
            raise EconomicCalendarError("Economic calendar feed is not configured.")

        try:
            with urlopen(
                settings.economic_calendar_url,
                timeout=settings.economic_calendar_timeout_seconds,
            ) as response:
                payload = json.loads(response.read())
        except (OSError, TimeoutError, URLError, json.JSONDecodeError) as exc:
            raise EconomicCalendarError("Economic calendar feed is unavailable.") from exc

        if not isinstance(payload, dict):
            raise EconomicCalendarError("Economic calendar payload must be an object.")
        updated_at = self._parse_time(payload.get("updated_at"))
        current_time = now or datetime.now(UTC)
        age_seconds = (current_time - updated_at).total_seconds()
        if age_seconds < -60 or age_seconds > settings.economic_calendar_max_age_seconds:
            raise EconomicCalendarError("Economic calendar feed is stale.")

        rows = payload.get("events")
        if not isinstance(rows, list):
            raise EconomicCalendarError("Economic calendar events must be a list.")

        events: list[EconomicEvent] = []
        for row in rows:
            if not isinstance(row, dict):
                raise EconomicCalendarError("Economic calendar event has an invalid format.")
            currency = row.get("currency")
            impact = row.get("impact")
            if not isinstance(currency, str) or not isinstance(impact, str):
                raise EconomicCalendarError(
                    "Economic calendar event is missing currency or impact."
                )
            if currency.strip().upper() != "USD" or impact.strip().lower() not in {
                "high",
                "high impact",
            }:
                continue
            name = row.get("event")
            if not isinstance(name, str) or not name.strip():
                raise EconomicCalendarError("High-impact USD event is missing its name.")
            events.append(
                EconomicEvent(
                    name=name.strip(),
                    currency="USD",
                    impact="high",
                    event_time=self._parse_time(row.get("time")),
                )
            )
        return tuple(events)

    @staticmethod
    def within_blackout(
        event_time: datetime,
        now: datetime,
        window: timedelta = timedelta(minutes=30),
    ) -> bool:
        if event_time.tzinfo is None or now.tzinfo is None:
            raise ValueError("Calendar timestamps must include a timezone.")
        return abs(event_time.astimezone(UTC) - now.astimezone(UTC)) <= window

    @staticmethod
    def _parse_time(value: object) -> datetime:
        if not isinstance(value, str):
            raise EconomicCalendarError("Economic calendar timestamp is missing.")
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise EconomicCalendarError("Economic calendar timestamp is invalid.") from exc
        if parsed.tzinfo is None:
            raise EconomicCalendarError("Economic calendar timestamp must include a timezone.")
        return parsed.astimezone(UTC)
