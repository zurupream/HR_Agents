"""Seed the in-memory stores with one job and one candidate for a local demo run."""

from datetime import datetime, timedelta, timezone

from scheduler.tools import scheduling_tools as t
from scheduler.tools.store import InMemoryStore, set_store


def seed() -> InMemoryStore:
    store = InMemoryStore()
    store.add_job_rules({
        "job_id": "ENG-101",
        "panel_emails": ["alice@company.example", "bob@company.example"],
        "interview_type": "video",
        "duration_minutes": 45,
        "working_start": "09:00",
        "working_end": "17:00",
        "job_timezone": "America/New_York",
        "notice_hours": 24,
        "prep_notes": "Bring a laptop. Be ready to discuss one past project in depth.",
        "recruiter_email": "recruiter@company.example",
    })
    store.add_candidate({
        "candidate_id": "C-001",
        "job_id": "ENG-101",
        "name": "Sam Rivera",
        "email": "sam@example.com",
        "timezone": "Europe/London",
    })
    set_store(store)
    # Panel members are free from tomorrow; calendar starts empty, so slots exist.
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    t.get_calendar().external_busy["alice@company.example"] = [
        (tomorrow + timedelta(hours=9), tomorrow + timedelta(hours=12)),
    ]
    return store
