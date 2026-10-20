"""Seed the in-memory stores with the Merchandiser job and three sample candidates."""

from __future__ import annotations

from scheduler.tools.calendar import InMemoryCalendar
from scheduler.tools.email import InMemoryMailer, set_mailer
from scheduler.tools.scheduling_tools import set_calendar
from scheduler.tools.store import InMemoryStore, get_store, set_store

MERCHANDISER_JOB = {
    "job_id": "MERCH-2026-01",
    "title": "Merchandiser",
    "panel_emails": ["panel.a@example.com", "panel.b@example.com"],
    "interview_type": "video",
    "duration_minutes": 45,
    "working_start": "09:00",
    "working_end": "17:00",
    "job_timezone": "Africa/Nairobi",
    "notice_hours": 24,
    "prep_notes": (
        "Bring a portfolio of recent visual merchandising work. "
        "Be ready to walk through one store layout in detail."
    ),
    "recruiter_email": "recruiter@example.com",
    "location": "",
}

MERCHANDISER_CANDIDATES = [
    {
        "candidate_id": "MC-001",
        "job_id": "MERCH-2026-01",
        "name": "Amara Okafor",
        "email": "candidate1@example.com",
        "timezone": "Africa/Nairobi",
    },
    {
        "candidate_id": "MC-002",
        "job_id": "MERCH-2026-01",
        "name": "Liam Brennan",
        "email": "candidate2@example.com",
        "timezone": "Europe/London",
    },
    {
        "candidate_id": "MC-003",
        "job_id": "MERCH-2026-01",
        "name": "Priya Nair",
        "email": "candidate3@example.com",
    },
]


def seed_merchandiser() -> InMemoryStore:
    """Load the Merchandiser job and three candidates into the module-level store."""
    store = get_store()
    if not isinstance(store, InMemoryStore):
        store = InMemoryStore()
        set_store(store)
    else:
        with store._lock:
            store.candidates.clear()
            store.job_rules.clear()
            store.interviews.clear()

    store.add_job_rules(dict(MERCHANDISER_JOB))
    for candidate in MERCHANDISER_CANDIDATES:
        store.add_candidate(dict(candidate))

    set_calendar(InMemoryCalendar())
    set_mailer(InMemoryMailer())
    return store
