"""Offline tests for Merchandiser sample data seeding."""

from __future__ import annotations

import importlib
import os
import subprocess
import sys

import pytest

import scheduler
from scheduler.sample_data import seed_merchandiser
from scheduler.tools import scheduling_tools as t
from scheduler.tools.calendar import InMemoryCalendar
from scheduler.tools.email import InMemoryMailer, get_mailer, set_mailer
from scheduler.tools.store import InMemoryStore, get_store, set_store


@pytest.fixture(autouse=True)
def _isolate_stores():
    """Reset module-level store, calendar, and mailer around each test."""
    set_store(InMemoryStore())
    t.set_calendar(InMemoryCalendar())
    set_mailer(InMemoryMailer())
    yield
    set_store(InMemoryStore())
    t.set_calendar(InMemoryCalendar())
    set_mailer(InMemoryMailer())


def test_seed_merchandiser_creates_job_and_three_pending_candidates():
    seed_merchandiser()
    store = get_store()

    rules_res = t.get_job_rules("MERCH-2026-01")
    assert rules_res["status"] == "ok"
    rules = rules_res["rules"]
    assert rules["job_id"] == "MERCH-2026-01"
    assert rules["title"] == "Merchandiser"
    assert rules["panel_emails"] == ["panel.a@example.com", "panel.b@example.com"]
    assert rules["interview_type"] == "video"
    assert rules["duration_minutes"] == 45
    assert rules["working_start"] == "09:00"
    assert rules["working_end"] == "17:00"
    assert rules["job_timezone"] == "Africa/Nairobi"
    assert rules["notice_hours"] == 24
    assert rules["prep_notes"] == (
        "Bring a portfolio of recent visual merchandising work. "
        "Be ready to walk through one store layout in detail."
    )
    assert rules["recruiter_email"] == "recruiter@example.com"
    assert rules["location"] == ""

    pending = t.get_pending_candidates()
    assert pending["status"] == "ok"
    candidates = pending["candidates"]
    assert len(candidates) == 3

    by_id = {c["candidate_id"]: c for c in candidates}
    assert set(by_id) == {"MC-001", "MC-002", "MC-003"}

    assert by_id["MC-001"]["name"] == "Amara Okafor"
    assert by_id["MC-001"]["email"] == "candidate1@example.com"
    assert by_id["MC-001"]["timezone"] == "Africa/Nairobi"
    assert by_id["MC-001"]["job_id"] == "MERCH-2026-01"

    assert by_id["MC-002"]["name"] == "Liam Brennan"
    assert by_id["MC-002"]["email"] == "candidate2@example.com"
    assert by_id["MC-002"]["timezone"] == "Europe/London"
    assert by_id["MC-002"]["job_id"] == "MERCH-2026-01"

    assert by_id["MC-003"]["name"] == "Priya Nair"
    assert by_id["MC-003"]["email"] == "candidate3@example.com"
    assert not by_id["MC-003"].get("timezone")
    assert by_id["MC-003"]["job_id"] == "MERCH-2026-01"

    # Verify MC-003 defaults to the job timezone (Africa/Nairobi) when slots are found.
    assert t.claim_candidate("MC-003", "test-agent")["status"] == "claimed"
    slots_res = t.find_candidate_slots("MC-003", "test-agent")
    assert slots_res["status"] == "ok"
    assert slots_res["candidate_timezone"] == "Africa/Nairobi"

    assert isinstance(t.get_calendar(), InMemoryCalendar)
    assert isinstance(get_mailer(), InMemoryMailer)
    assert store is get_store()


def test_import_with_scheduler_seed_merchandiser_seeds_store(monkeypatch):
    # Without SCHEDULER_SEED, reloading does not seed the store.
    monkeypatch.delenv("SCHEDULER_SEED", raising=False)
    importlib.reload(scheduler)
    assert t.get_pending_candidates()["candidates"] == []

    # With SCHEDULER_SEED=merchandiser, reloading seeds the store.
    monkeypatch.setenv("SCHEDULER_SEED", "merchandiser")
    importlib.reload(scheduler)
    pending = t.get_pending_candidates()
    assert len(pending["candidates"]) == 3
    assert get_store().get_job_rules("MERCH-2026-01") is not None

    # Also verify a fresh Python subprocess importing scheduler with SCHEDULER_SEED=merchandiser.
    env = dict(os.environ)
    env["SCHEDULER_SEED"] = "merchandiser"
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import scheduler; "
                "from scheduler.tools.scheduling_tools import get_pending_candidates; "
                "from scheduler.tools.store import get_store; "
                "cands = get_pending_candidates()['candidates']; "
                "assert len(cands) == 3, cands; "
                "assert get_store().get_job_rules('MERCH-2026-01')['title'] == 'Merchandiser'"
            ),
        ],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert proc.returncode == 0
