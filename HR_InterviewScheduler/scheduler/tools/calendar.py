"""Calendar client: aggregate free/busy, slot generation, and event creation.

Only time windows leave this module through `get_panel_free_busy`; event titles
and descriptions are never returned to the agent. `create_calendar_event`
re-checks conflicts itself, so a double-booking is refused even if the agent
skips its own re-verification.
"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo


def _parse(dt: str) -> datetime:
    value = datetime.fromisoformat(dt)
    if value.tzinfo is None:
        raise ValueError(f"datetime must include a UTC offset: {dt!r}")
    return value


def merge_blocks(blocks: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    merged: list[tuple[datetime, datetime]] = []
    for start, end in sorted(blocks):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def overlaps(start: datetime, end: datetime, blocks: list[tuple[datetime, datetime]]) -> bool:
    return any(start < b_end and end > b_start for b_start, b_end in blocks)


class InMemoryCalendar:
    """Stand-in for Google Calendar / Outlook. Holds events per attendee email."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.events: dict[str, dict[str, Any]] = {}
        # Busy blocks that are not events (personal schedule, out-of-office, etc.)
        self.external_busy: dict[str, list[tuple[datetime, datetime]]] = {}

    def busy_blocks(self, emails: list[str], start: datetime, end: datetime) -> dict[str, list[tuple[datetime, datetime]]]:
        result: dict[str, list[tuple[datetime, datetime]]] = {}
        with self._lock:
            for email in emails:
                blocks = list(self.external_busy.get(email, []))
                for ev in self.events.values():
                    if email in ev["attendees"]:
                        blocks.append((ev["start"], ev["end"]))
                result[email] = merge_blocks([b for b in blocks if b[0] < end and b[1] > start])
        return result

    def create_event(self, attendees: list[str], start: datetime, end: datetime, **details: Any) -> dict[str, Any] | None:
        """Create the event only if no attendee is busy. Returns None on conflict."""
        with self._lock:
            for email in attendees:
                blocks = list(self.external_busy.get(email, []))
                blocks += [(ev["start"], ev["end"]) for ev in self.events.values() if email in ev["attendees"]]
                if overlaps(start, end, blocks):
                    return None
            event_id = uuid.uuid4().hex
            event = {
                "event_id": event_id,
                "attendees": list(attendees),
                "start": start,
                "end": end,
                "meet_link": f"https://meet.example.com/{event_id[:10]}",
                **details,
            }
            self.events[event_id] = event
            return event


def generate_slots(
    *,
    busy: dict[str, list[tuple[datetime, datetime]]],
    now: datetime,
    days_ahead: int,
    duration_minutes: int,
    working_start: str,
    working_end: str,
    job_timezone: str,
    notice_hours: float,
    max_options: int = 5,
) -> list[tuple[datetime, datetime]]:
    """Return up to `max_options` free slots that all panel members can attend.

    Slots are laid out on the hour/half-hour inside working hours in the job's
    timezone, start no earlier than `now + notice_hours`, and never overlap busy time.
    """
    tz = ZoneInfo(job_timezone)
    earliest = now + timedelta(hours=notice_hours)
    duration = timedelta(minutes=duration_minutes)
    ws, we = time.fromisoformat(working_start), time.fromisoformat(working_end)
    step = timedelta(minutes=30)
    all_busy = [b for blocks in busy.values() for b in blocks]

    slots: list[tuple[datetime, datetime]] = []
    local_today = now.astimezone(tz).date()
    for day_offset in range(days_ahead + 1):
        day = local_today + timedelta(days=day_offset)
        cursor = datetime.combine(day, ws, tzinfo=tz)
        day_end = datetime.combine(day, we, tzinfo=tz)
        while cursor + duration <= day_end:
            start, end = cursor, cursor + duration
            if start >= earliest and not overlaps(start, end, all_busy):
                slots.append((start, end))
                if len(slots) == max_options:
                    return slots
            cursor += step
    return slots
