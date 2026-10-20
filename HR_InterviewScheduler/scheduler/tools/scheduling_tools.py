"""Tool functions exposed to the ADK agent.

Every function returns a JSON-serialisable dict and never raises for expected
business outcomes (conflicts, missing rules, unknown candidates). The agent
reads the `status` field and follows its rules of engagement.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfoNotFoundError, ZoneInfo

from scheduler.tools import calendar as cal
from scheduler.tools.email import get_mailer, set_mailer
from scheduler.tools.store import get_store, utcnow

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
INTERVIEW_TYPES = {"video", "phone", "onsite"}
_calendar: Any = cal.InMemoryCalendar()


def get_calendar() -> Any:
    return _calendar


def set_calendar(calendar: Any) -> None:
    global _calendar
    _calendar = calendar


# ---------------------------------------------------------------- helpers

def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _format_slot(start: datetime, end: datetime, tz_name: str, option: int | None = None) -> str:
    local = start.astimezone(ZoneInfo(tz_name))
    text = f"{local:%A %b %d @ %I:%M %p} {local.tzname()} ({int((end - start).total_seconds() // 60)} min)"
    return f"Option {option}: {text}" if option is not None else text


def _require_claim(candidate_id: str, agent_id: str) -> dict[str, Any] | None:
    """Return an error dict unless `agent_id` currently holds the claim on the candidate."""
    row = get_store().get_candidate(candidate_id)
    if row is None:
        return {"status": "error", "reason": f"unknown candidate {candidate_id}"}
    if row.get("claimed_by") != agent_id:
        return {"status": "error", "reason": "candidate is not claimed by this agent; claim it first"}
    return None


def _validate_rules(rules: dict[str, Any] | None) -> list[str]:
    """Return a list of problems. An empty list means the rules are usable."""
    if rules is None:
        return ["no InterviewRules entry for this job"]
    problems: list[str] = []
    panel = rules.get("panel_emails")
    if not isinstance(panel, list) or not panel:
        problems.append("panel_emails must be a non-empty list")
    else:
        bad = [e for e in panel if not isinstance(e, str) or not EMAIL_RE.match(e)]
        if bad:
            problems.append(f"invalid panel email(s): {bad}")
    if rules.get("interview_type") not in INTERVIEW_TYPES:
        problems.append("interview_type must be one of video, phone, onsite")
    if rules.get("interview_type") == "onsite" and not rules.get("location"):
        problems.append("onsite interviews need a location")
    duration = rules.get("duration_minutes")
    if not isinstance(duration, int) or not 15 <= duration <= 240:
        problems.append("duration_minutes must be an integer between 15 and 240")
    try:
        ws = datetime.strptime(str(rules.get("working_start")), "%H:%M").time()
        we = datetime.strptime(str(rules.get("working_end")), "%H:%M").time()
        if ws >= we:
            problems.append("working_start must be earlier than working_end")
    except ValueError:
        problems.append("working_start and working_end must be HH:MM")
    try:
        ZoneInfo(str(rules.get("job_timezone")))
    except (ZoneInfoNotFoundError, ValueError):
        problems.append("job_timezone is not a valid IANA timezone")
    notice = rules.get("notice_hours", 0)
    if not isinstance(notice, (int, float)) or notice < 0:
        problems.append("notice_hours must be a non-negative number")
    recruiter = rules.get("recruiter_email")
    if not isinstance(recruiter, str) or not EMAIL_RE.match(recruiter):
        problems.append("recruiter_email must be a valid email")
    return problems


def _candidate_tz(candidate: dict[str, Any], rules: dict[str, Any]) -> str:
    """Candidate's timezone if valid, otherwise the job's timezone."""
    tz = candidate.get("timezone")
    if tz:
        try:
            ZoneInfo(tz)
            return tz
        except (ZoneInfoNotFoundError, ValueError):
            pass
    return rules["job_timezone"]


def _parse_aware(value: str, field: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        raise ValueError(f"{field} must include a UTC offset")
    return dt


# ------------------------------------------------- 1. database / tracking

def get_pending_candidates() -> dict[str, Any]:
    """List candidates flagged for scheduling (next_action = 'schedule_interview')."""
    candidates = get_store().get_pending_candidates()
    return {"status": "ok", "candidates": [
        {"candidate_id": c["candidate_id"], "job_id": c["job_id"], "name": c.get("name"),
         "email": c["email"], "timezone": c.get("timezone")}
        for c in candidates
    ]}


def claim_candidate(candidate_id: str, agent_id: str) -> dict[str, Any]:
    """Lock a candidate so no other agent works on them. Must succeed before any outreach."""
    if get_store().claim_candidate(candidate_id, agent_id):
        return {"status": "claimed", "candidate_id": candidate_id}
    return {"status": "already_claimed_or_not_claimable", "candidate_id": candidate_id}


def get_job_rules(job_id: str) -> dict[str, Any]:
    """Fetch scheduling constraints for a job, validated. Escalate if status != 'ok'."""
    rules = get_store().get_job_rules(job_id)
    problems = _validate_rules(rules)
    if problems:
        return {"status": "rules_invalid", "job_id": job_id, "problems": problems}
    return {"status": "ok", "job_id": job_id, "rules": rules}


def log_interview_record(record_data: dict[str, Any]) -> dict[str, Any]:
    """Write a booking into the Interviews log."""
    required = {"candidate_id", "job_id", "event_id", "start", "end", "panel_emails", "candidate_email"}
    missing = sorted(required - set(record_data))
    if missing:
        return {"status": "error", "reason": f"missing fields: {missing}"}
    get_store().log_interview_record(record_data)
    return {"status": "logged"}


def list_awaiting_reply(older_than_hours: float) -> dict[str, Any]:
    """Candidates who were sent slots but have not replied for `older_than_hours`. Used for chasing."""
    rows = get_store().list_awaiting_reply(older_than_hours)
    return {"status": "ok", "candidates": [
        {"candidate_id": c["candidate_id"], "email": c["email"], "offered_at": c.get("offered_at")}
        for c in rows
    ]}


# ------------------------------------------------------ 2. calendar

def get_panel_free_busy(interviewer_emails: list[str], start_date: str, end_date: str) -> dict[str, Any]:
    """Aggregate busy windows (no titles or details) for each panel member.

    start_date and end_date are ISO datetimes with a UTC offset.
    """
    try:
        start = _parse_aware(start_date, "start_date")
        end = _parse_aware(end_date, "end_date")
    except ValueError as exc:
        return {"status": "error", "reason": str(exc)}
    if end <= start:
        return {"status": "error", "reason": "end_date must be after start_date"}
    busy = get_calendar().busy_blocks(interviewer_emails, start, end)
    return {"status": "ok", "busy": {
        email: [{"start": _iso(s), "end": _iso(e)} for s, e in blocks] for email, blocks in busy.items()
    }}


def find_candidate_slots(candidate_id: str, agent_id: str, days_ahead: int = 7) -> dict[str, Any]:
    """Compute up to 5 slots free for the whole panel, and return them as a numbered list.

    The offered slots are saved on the candidate record so that a later booking
    can map 'option 2' back to a concrete time. The candidate must be claimed by `agent_id`.
    """
    err = _require_claim(candidate_id, agent_id)
    if err:
        return err
    store = get_store()
    candidate = store.get_candidate(candidate_id)
    checked = get_job_rules(candidate["job_id"])
    if checked["status"] != "ok":
        return checked
    rules = checked["rules"]
    now = utcnow()
    busy = get_calendar().busy_blocks(rules["panel_emails"], now, now + timedelta(days=days_ahead + 1))
    slots = cal.generate_slots(
        busy=busy, now=now, days_ahead=days_ahead, duration_minutes=rules["duration_minutes"],
        working_start=rules["working_start"], working_end=rules["working_end"],
        job_timezone=rules["job_timezone"], notice_hours=rules.get("notice_hours", 0),
    )
    if not slots:
        return {"status": "no_slots", "reason": "no common free slot in the search window"}
    tz = _candidate_tz(candidate, rules)
    offered = [{"option": i, "start": _iso(s), "end": _iso(e)} for i, (s, e) in enumerate(slots, 1)]
    store.save_offered_slots(candidate_id, offered)
    return {
        "status": "ok",
        "candidate_timezone": tz,
        "options": offered,
        "numbered_list": [_format_slot(s, e, tz, i) for i, (s, e) in enumerate(slots, 1)],
    }


def verify_slot_available(job_id: str, start_time: str, end_time: str) -> dict[str, Any]:
    """Re-check that every panel member is free for [start_time, end_time] right now."""
    checked = get_job_rules(job_id)
    if checked["status"] != "ok":
        return checked
    try:
        start = _parse_aware(start_time, "start_time")
        end = _parse_aware(end_time, "end_time")
    except ValueError as exc:
        return {"status": "error", "reason": str(exc)}
    busy = get_calendar().busy_blocks(checked["rules"]["panel_emails"], start, end)
    conflicts = [email for email, blocks in busy.items() if cal.overlaps(start, end, blocks)]
    return {"status": "available" if not conflicts else "unavailable", "conflicting_members": conflicts}


def create_calendar_event(
    panel_emails: list[str],
    candidate_email: str,
    start_time: str,
    end_time: str,
    location_or_link: str,
    title: str,
    description: str,
) -> dict[str, Any]:
    """Create the invitation. Refuses with status 'conflict' if any attendee is busy."""
    try:
        start = _parse_aware(start_time, "start_time")
        end = _parse_aware(end_time, "end_time")
    except ValueError as exc:
        return {"status": "error", "reason": str(exc)}
    event = get_calendar().create_event(
        attendees=[*panel_emails, candidate_email], start=start, end=end,
        location=location_or_link, title=title, description=description,
    )
    if event is None:
        return {"status": "conflict", "reason": "a panel member became busy; re-query availability"}
    return {"status": "created", "event_id": event["event_id"],
            "meet_link": location_or_link or event["meet_link"]}


# ------------------------------------------------- 3. messaging

def send_candidate_slots_email(
    candidate_email: str,
    slots_list: list[str],
    prep_notes: str,
    candidate_id: str,
    agent_id: str,
) -> dict[str, Any]:
    """Send the numbered slot options to the candidate. Moves the candidate to awaiting_reply and releases the claim."""
    err = _require_claim(candidate_id, agent_id)
    if err:
        return err
    body = (
        "Thank you for your application. Please reply with the number of the slot that suits you:\n\n"
        + "\n".join(slots_list)
        + ("\n\nPreparation notes:\n" + prep_notes if prep_notes else "")
        + "\n\nIf none of these work, reply with the times you are free and we will check again."
    )
    get_mailer().send(candidate_email, "Interview time options", body)
    get_store().release_candidate(candidate_id, "awaiting_reply")
    return {"status": "sent"}


def send_reminder_email(candidate_email: str, candidate_id: str, agent_id: str) -> dict[str, Any]:
    """Chase a candidate who has not replied to the offered slots."""
    err = _require_claim(candidate_id, agent_id)
    if err:
        return err
    get_mailer().send(
        candidate_email, "Reminder: interview time options",
        "Just following up on the interview time options we sent. Please reply with your preferred option number.",
    )
    get_store().release_candidate(candidate_id, "awaiting_reply")
    return {"status": "sent"}


def send_confirmation_email(
    candidate_email: str, chosen_slot: str, prep_notes: str, meet_link: str
) -> dict[str, Any]:
    """Send the booking confirmation with the chosen slot, prep notes and video link."""
    body = (
        f"Your interview is confirmed for {chosen_slot}.\n"
        f"Join: {meet_link}"
        + (f"\n\nPreparation notes:\n{prep_notes}" if prep_notes else "")
    )
    get_mailer().send(candidate_email, "Interview confirmed", body)
    return {"status": "sent"}


def book_interview(candidate_id: str, option_number: int, agent_id: str) -> dict[str, Any]:
    """Atomically book the option the candidate chose.

    Re-verifies availability right before creating the event. On a conflict it
    returns 'slot_unavailable' and keeps the claim, so the agent can re-query and
    offer fresh options, or escalate.
    """
    err = _require_claim(candidate_id, agent_id)
    if err:
        return err
    store = get_store()
    candidate = store.get_candidate(candidate_id)
    checked = get_job_rules(candidate["job_id"])
    if checked["status"] != "ok":
        return checked
    rules = checked["rules"]

    offered = {o["option"]: o for o in candidate.get("offered_slots", [])}
    if option_number not in offered:
        return {"status": "invalid_option", "reason": f"option {option_number} was not offered",
                "valid_options": sorted(offered)}
    chosen = offered[option_number]

    verify = verify_slot_available(candidate["job_id"], chosen["start"], chosen["end"])
    if verify["status"] != "available":
        return {"status": "slot_unavailable", "reason": "slot was taken; re-query availability or escalate"}

    panel = rules["panel_emails"]
    title = f"Interview: {candidate.get('name') or candidate['candidate_id']} ({rules['interview_type']})"
    description = rules.get("prep_notes", "")
    created = create_calendar_event(
        panel_emails=panel, candidate_email=candidate["email"], start_time=chosen["start"],
        end_time=chosen["end"],
        location_or_link=rules.get("location", "") if rules["interview_type"] == "onsite" else "",
        title=title, description=description,
    )
    if created["status"] != "created":
        return {"status": "slot_unavailable", "reason": created.get("reason", "conflict")}

    start = _parse_aware(chosen["start"], "start")
    end = _parse_aware(chosen["end"], "end")
    tz = _candidate_tz(candidate, rules)
    slot_text = _format_slot(start, end, tz)
    link = created["meet_link"]
    send_confirmation_email(candidate["email"], slot_text, description, link)
    log_interview_record({
        "candidate_id": candidate_id, "job_id": candidate["job_id"], "event_id": created["event_id"],
        "start": chosen["start"], "end": chosen["end"], "panel_emails": panel,
        "candidate_email": candidate["email"], "meet_link": link, "booked_at": utcnow().isoformat(),
    })
    store.release_candidate(candidate_id, "scheduled")
    return {"status": "booked", "event_id": created["event_id"], "slot": slot_text, "meet_link": link}


def escalate_to_recruiter(recruiter_email: str, candidate_id: str, reason: str) -> dict[str, Any]:
    """Hand the case to a human recruiter. Releases the claim with status 'escalated'."""
    store = get_store()
    row = store.get_candidate(candidate_id)
    if row is None:
        return {"status": "error", "reason": f"unknown candidate {candidate_id}"}
    get_mailer().send(
        recruiter_email, f"Interview scheduling needs help: {candidate_id}",
        f"Candidate: {row.get('name', '')} <{row['email']}>\nJob: {row['job_id']}\n"
        f"Reason: {reason}\n\nRaw candidate messages and offered slots are in the tracker.",
    )
    store.release_candidate(candidate_id, "escalated")
    return {"status": "escalated"}


# ---------------------------------------------------------------------------
# Multi-Stage & Multi-Interview ADK Tools (Steps 1 - 5)
# ---------------------------------------------------------------------------


def get_bottleneck_dashboard_tool() -> dict[str, Any]:
    """Step 5: Return the proactive bottleneck & action command center metrics, shortages, and pipeline matrix."""
    from scheduler.multistage import get_multistage_hub

    return get_multistage_hub().get_bottleneck_dashboard()


def request_panel_slots_tool(
    job_id: str,
    stage_id: str,
    interview_code: str,
    base_url: str = "http://localhost:8000",
) -> dict[str, Any]:
    """Step 1: Calculate required slots for waiting candidates, generate AI slot suggestions, and email the panel lead."""
    from scheduler.multistage import get_multistage_hub

    return get_multistage_hub().request_slots_from_panel_lead(
        job_id=job_id,
        stage_id=stage_id,
        interview_code=interview_code,
        base_url=base_url,
    )


def approve_panel_slots_tool(
    request_token: str,
    selected_slot_ids: list[str] | None = None,
    custom_slots: list[dict[str, str]] | None = None,
    base_url: str = "http://localhost:8000",
) -> dict[str, Any]:
    """Step 1 -> Step 2: Approve panel lead slots and automatically dispatch live conflict-free self-booking links to waiting candidates."""
    from scheduler.multistage import get_multistage_hub

    return get_multistage_hub().approve_panel_slots(
        request_token=request_token,
        selected_slot_ids=selected_slot_ids,
        custom_slots=custom_slots,
        base_url=base_url,
    )


def get_live_candidate_slots_tool(booking_token: str) -> dict[str, Any]:
    """Step 2: Fetch live conflict-free available slots for a candidate's self-booking token."""
    from scheduler.multistage import get_multistage_hub

    return get_multistage_hub().get_live_candidate_view(booking_token)


def book_live_candidate_slot_tool(booking_token: str, slot_id: str) -> dict[str, Any]:
    """Step 2: Atomically lock and book a candidate into a live available slot with zero double-booking."""
    from scheduler.multistage import get_multistage_hub

    return get_multistage_hub().book_live_candidate_slot(
        booking_token=booking_token,
        slot_id=slot_id,
    )


def complete_stage_interview_tool(
    candidate_id: str,
    stage_id: str,
    interview_code: str,
    passed: bool = True,
    base_url: str = "http://localhost:8000",
) -> dict[str, Any]:
    """Step 3: Mark a sub-interview completed and auto-advance the candidate to the next stage when all stage interviews pass."""
    from scheduler.multistage import get_multistage_hub

    return get_multistage_hub().complete_interview_and_advance(
        candidate_id=candidate_id,
        stage_id=stage_id,
        interview_code=interview_code,
        passed=passed,
        base_url=base_url,
    )


def handle_interviewer_decline_tool(
    candidate_id: str,
    stage_id: str,
    interview_code: str,
    declined_email: str,
    base_url: str = "http://localhost:8000",
) -> dict[str, Any]:
    """Step 4: Self-healing conflict resolution when an interviewer declines. Hot-swaps a free backup interviewer from the pool or sends a live reschedule link."""
    from scheduler.multistage import get_multistage_hub

    return get_multistage_hub().handle_interviewer_decline(
        candidate_id=candidate_id,
        stage_id=stage_id,
        interview_code=interview_code,
        declined_email=declined_email,
        base_url=base_url,
    )


def auto_resolve_bottlenecks_tool(base_url: str = "http://localhost:8000") -> dict[str, Any]:
    """Step 5: Proactively resolve all active slot shortages, nudge unresponsive leads/candidates, and send live booking links."""
    from scheduler.multistage import get_multistage_hub

    return get_multistage_hub().auto_resolve_all_bottlenecks(base_url=base_url)

