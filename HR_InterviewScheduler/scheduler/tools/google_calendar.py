"""Google Calendar backend implementing the same interface as InMemoryCalendar."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from scheduler.google_clients import build_calendar_service
from scheduler.tools.calendar import merge_blocks, overlaps


def _parse_iso_dt(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


class GoogleCalendar:
    """Google Calendar API client matching the InMemoryCalendar interface."""

    def __init__(self, service: Any = None, calendar_id: str = "primary") -> None:
        self._service = service
        self._calendar_id = calendar_id

    @property
    def service(self) -> Any:
        return self._get_service()

    @service.setter
    def service(self, value: Any) -> None:
        self._service = value

    def _get_service(self) -> Any:
        if self._service is None:
            self._service = build_calendar_service()
        return self._service

    def busy_blocks(
        self, emails: list[str], start: datetime, end: datetime
    ) -> dict[str, list[tuple[datetime, datetime]]]:
        """Query Google Calendar freebusy API and return only (start, end) windows."""
        if not emails:
            return {}

        body = {
            "timeMin": start.isoformat(),
            "timeMax": end.isoformat(),
            "items": [{"id": email} for email in emails],
        }
        response = self._get_service().freebusy().query(body=body).execute()
        calendars = response.get("calendars", {}) if isinstance(response, dict) else {}

        result: dict[str, list[tuple[datetime, datetime]]] = {}
        for email in emails:
            cal_entry = calendars.get(email)
            if cal_entry is None and len(emails) == 1 and len(calendars) == 1:
                cal_entry = next(iter(calendars.values()))
            raw_busy = (cal_entry or {}).get("busy", [])
            blocks: list[tuple[datetime, datetime]] = []
            for item in raw_busy:
                if isinstance(item, dict) and "start" in item and "end" in item:
                    b_start = _parse_iso_dt(item["start"])
                    b_end = _parse_iso_dt(item["end"])
                    if b_start < end and b_end > start:
                        blocks.append((b_start, b_end))
            result[email] = merge_blocks(blocks)
        return result

    def create_event(
        self, attendees: list[str], start: datetime, end: datetime, **details: Any
    ) -> dict[str, Any] | None:
        """Create a Google Calendar event with a Meet link if all attendees are free.

        First re-checks busy blocks for every attendee in [start, end] and
        returns None if any attendee has a conflict.
        """
        attendee_list = list(attendees)
        busy = self.busy_blocks(attendee_list, start, end)
        for email in attendee_list:
            if overlaps(start, end, busy.get(email, [])):
                return None

        request_id = uuid.uuid4().hex
        summary = details.get("title") or details.get("summary") or "Interview"
        description = details.get("description", "")
        event_body: dict[str, Any] = {
            "summary": summary,
            "description": description,
            "start": {"dateTime": start.isoformat()},
            "end": {"dateTime": end.isoformat()},
            "attendees": [{"email": email} for email in attendee_list],
            "conferenceData": {
                "createRequest": {
                    "requestId": request_id,
                    "conferenceSolutionKey": {"type": "hangoutsMeet"},
                }
            },
        }
        if details.get("location"):
            event_body["location"] = details["location"]

        created = (
            self._get_service()
            .events()
            .insert(
                calendarId=self._calendar_id,
                body=event_body,
                conferenceDataVersion=1,
                sendUpdates="all",
            )
            .execute()
        )

        event_id = created.get("id") or created.get("event_id") or request_id
        meet_link = created.get("hangoutLink") or created.get("meet_link") or ""
        if not meet_link:
            entry_points = created.get("conferenceData", {}).get("entryPoints", [])
            for ep in entry_points:
                if ep.get("entryPointType") == "video" and ep.get("uri"):
                    meet_link = ep["uri"]
                    break
            if not meet_link and entry_points and entry_points[0].get("uri"):
                meet_link = entry_points[0]["uri"]

        return {
            "event_id": event_id,
            "meet_link": meet_link,
            "attendees": attendee_list,
            "start": start,
            "end": end,
        }
