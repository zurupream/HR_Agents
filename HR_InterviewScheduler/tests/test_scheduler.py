from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from scheduler.tools import calendar as cal
from scheduler.tools import scheduling_tools as t
from scheduler.tools.email import InMemoryMailer, set_mailer
from scheduler.tools.store import InMemoryStore, set_store

AGENT = "agent-1"
PANEL = ["alice@company.example", "bob@company.example"]


@pytest.fixture
def env():
    store = InMemoryStore()
    set_store(store)
    calendar = cal.InMemoryCalendar()
    t.set_calendar(calendar)
    mailer = InMemoryMailer()
    set_mailer(mailer)
    store.add_job_rules({
        "job_id": "J1", "panel_emails": PANEL, "interview_type": "video", "duration_minutes": 45,
        "working_start": "09:00", "working_end": "17:00", "job_timezone": "America/New_York",
        "notice_hours": 1, "prep_notes": "Bring ID", "recruiter_email": "rec@company.example",
    })
    store.add_candidate({"candidate_id": "C1", "job_id": "J1", "name": "Sam", "email": "sam@example.com",
                         "timezone": "Europe/London"})
    return store, calendar, mailer


def _claim_and_offer(store, agent=AGENT):
    assert t.claim_candidate("C1", agent)["status"] == "claimed"
    offer = t.find_candidate_slots("C1", agent)
    assert offer["status"] == "ok", offer
    return offer


def test_generate_slots_respects_hours_busy_and_notice():
    tz = "America/New_York"
    now = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)  # 08:00 in New York
    busy = {"a": [(datetime(2026, 10, 14, 14, 0, tzinfo=timezone.utc), datetime(2026, 10, 14, 16, 0, tzinfo=timezone.utc))]}
    slots = cal.generate_slots(busy=busy, now=now, days_ahead=0, duration_minutes=45,
                               working_start="09:00", working_end="17:00", job_timezone=tz,
                               notice_hours=0, max_options=50)
    assert slots, "expected free slots"
    zone = ZoneInfo(tz)
    for start, end in slots:
        assert 9 <= start.astimezone(zone).hour
        assert end.astimezone(zone).hour <= 17
        assert not cal.overlaps(start, end, busy["a"])


def test_claim_is_exclusive(env):
    assert t.claim_candidate("C1", "agent-1")["status"] == "claimed"
    assert t.claim_candidate("C1", "agent-2")["status"] == "already_claimed_or_not_claimable"


def test_offers_require_claim(env):
    assert t.find_candidate_slots("C1", AGENT)["status"] == "error"


def test_offers_are_numbered_in_candidate_timezone(env):
    store, _, _ = env
    offer = _claim_and_offer(store)
    assert offer["candidate_timezone"] == "Europe/London"
    assert offer["numbered_list"][0].startswith("Option 1: ")
    assert len(store.get_candidate("C1")["offered_slots"]) == len(offer["options"])


def test_happy_path_books_logs_and_confirms(env):
    store, calendar, mailer = env
    _claim_and_offer(store)
    result = t.book_interview("C1", 2, AGENT)
    assert result["status"] == "booked", result
    assert store.get_candidate("C1")["status"] == "scheduled"
    assert len(store.interviews) == 1
    assert store.interviews[0]["event_id"] == result["event_id"]
    assert mailer.outbox[-1]["to"] == "sam@example.com"
    assert "meet.example.com" in mailer.outbox[-1]["body"]


def test_double_booking_is_refused_and_claim_kept(env):
    store, calendar, _ = env
    offer = _claim_and_offer(store)
    chosen = offer["options"][0]
    # A panel member gets booked elsewhere after the options were sent.
    start = datetime.fromisoformat(chosen["start"])
    end = datetime.fromisoformat(chosen["end"])
    calendar.create_event(attendees=[PANEL[0]], start=start, end=end, title="other")

    result = t.book_interview("C1", 1, AGENT)
    assert result["status"] == "slot_unavailable"
    assert store.interviews == []
    assert store.get_candidate("C1")["claimed_by"] == AGENT  # still held, so the agent can re-offer


def test_create_event_refuses_conflict_even_if_called_directly(env):
    _, calendar, _ = env
    start = datetime(2030, 1, 7, 14, 0, tzinfo=timezone.utc)
    end = start + timedelta(minutes=45)
    first = t.create_calendar_event(PANEL, "x@example.com", start.isoformat(), end.isoformat(), "", "A", "")
    second = t.create_calendar_event(PANEL, "y@example.com", start.isoformat(), end.isoformat(), "", "B", "")
    assert first["status"] == "created"
    assert second["status"] == "conflict"


def test_invalid_option_number(env):
    store, _, _ = env
    _claim_and_offer(store)
    result = t.book_interview("C1", 99, AGENT)
    assert result["status"] == "invalid_option"


def test_missing_rules_report_rules_invalid(env):
    store, _, _ = env
    store.add_candidate({"candidate_id": "C2", "job_id": "NO-SUCH-JOB", "email": "z@example.com"})
    t.claim_candidate("C2", AGENT)
    assert t.get_job_rules("NO-SUCH-JOB")["status"] == "rules_invalid"
    assert t.find_candidate_slots("C2", AGENT)["status"] == "rules_invalid"


def test_malformed_rules_are_listed(env):
    store, _, _ = env
    store.add_job_rules({"job_id": "BAD", "panel_emails": ["not-an-email"], "interview_type": "fax",
                         "duration_minutes": 5, "working_start": "18:00", "working_end": "09:00",
                         "job_timezone": "Mars/Olympus", "recruiter_email": "rec@company.example"})
    problems = t.get_job_rules("BAD")["problems"]
    assert len(problems) >= 5


def test_onsite_requires_location(env):
    store, _, _ = env
    rules = dict(store.get_job_rules("J1"), interview_type="onsite")
    store.add_job_rules(rules)
    assert any("location" in p for p in t.get_job_rules("J1")["problems"])


def test_free_busy_exposes_only_windows(env):
    _, calendar, _ = env
    start = datetime(2030, 1, 7, 9, 0, tzinfo=timezone.utc)
    calendar.create_event(attendees=[PANEL[0]], start=start, end=start + timedelta(hours=1), title="Secret 1:1")
    result = t.get_panel_free_busy(PANEL, "2030-01-07T00:00:00+00:00", "2030-01-08T00:00:00+00:00")
    blocks = result["busy"][PANEL[0]]
    assert blocks == [{"start": start.isoformat(), "end": (start + timedelta(hours=1)).isoformat()}]
    assert "Secret" not in str(result)


def test_escalation_releases_claim_and_emails_recruiter(env):
    store, _, mailer = env
    t.claim_candidate("C1", AGENT)
    result = t.escalate_to_recruiter("rec@company.example", "C1", "candidate asked for a Saturday")
    assert result["status"] == "escalated"
    assert store.get_candidate("C1")["status"] == "escalated"
    assert mailer.outbox[-1]["to"] == "rec@company.example"


def test_reply_after_offer_can_be_reclaimed_and_booked(env):
    store, _, _ = env
    _claim_and_offer(store)
    t.send_candidate_slots_email("sam@example.com", ["Option 1: ..."], "prep", "C1", AGENT)
    assert store.get_candidate("C1")["status"] == "awaiting_reply"
    assert t.claim_candidate("C1", "agent-2")["status"] == "claimed"
    assert t.find_candidate_slots("C1", AGENT)["status"] == "error"  # previous agent no longer owns it
