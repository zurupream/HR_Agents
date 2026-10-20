"""Backend configuration factory for calendar and email tools."""

from __future__ import annotations

import os
from typing import Any

from scheduler import config
from scheduler.tools.calendar import InMemoryCalendar
from scheduler.tools.email import InMemoryMailer, get_mailer, set_mailer
from scheduler.tools.gmail import GmailMailer
from scheduler.tools.google_calendar import GoogleCalendar
from scheduler.tools import scheduling_tools
from scheduler.tools.scheduling_tools import get_calendar, set_calendar


def configure_from_env() -> tuple[Any, Any]:
    """Select calendar and mailer backends based on SCHEDULER_BACKEND.

    Uses GoogleCalendar and GmailMailer when SCHEDULER_BACKEND=google,
    and InMemoryCalendar and InMemoryMailer otherwise (default).
    """
    backend = (os.environ.get("SCHEDULER_BACKEND") or config.DEFAULT_BACKEND).strip().lower()
    config.BACKEND = backend
    if backend == "google":
        calendar: Any = GoogleCalendar()
        mailer: Any = GmailMailer()
    else:
        calendar = InMemoryCalendar()
        mailer = InMemoryMailer()
    set_calendar(calendar)
    set_mailer(mailer)
    return calendar, mailer


scheduling_tools.configure_from_env = configure_from_env  # type: ignore[attr-defined]

__all__ = [
    "GmailMailer",
    "GoogleCalendar",
    "InMemoryCalendar",
    "InMemoryMailer",
    "configure_from_env",
    "get_calendar",
    "get_mailer",
    "set_calendar",
    "set_mailer",
]
