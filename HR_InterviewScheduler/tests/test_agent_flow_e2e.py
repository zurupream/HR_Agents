"""End-to-end tests of the ADK Interview Scheduler agent flow with a scripted model."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any
import uuid

from google.adk.agents import Agent
from google.adk.runners import InMemoryRunner
from google.genai import types
import pytest

from scheduler import demo_data
from scheduler.agent import root_agent
from scheduler.runner import APP_NAME, DEFAULT_INPUT, USER_ID
from scheduler.tools import calendar as cal
from scheduler.tools import scheduling_tools as t
from scheduler.tools.email import InMemoryMailer, set_mailer
from scheduler.tools.store import InMemoryStore, set_store
try:
    from tests.fake_model import ScriptedLlm, final_text, tool_call
except ModuleNotFoundError:
    from fake_model import ScriptedLlm, final_text, tool_call

AGENT_ID = "interview-scheduler"


@pytest.fixture
def env() -> tuple[InMemoryStore, cal.InMemoryCalendar, InMemoryMailer]:
    """Reset the in-memory store, calendar, and mailer before each test."""
    calendar = cal.InMemoryCalendar()
    t.set_calendar(calendar)
    mailer = InMemoryMailer()
    set_mailer(mailer)
    store = demo_data.seed()
    return store, calendar, mailer


async def _run_cycle_with_script(
    script: list[Any],
    message: str = DEFAULT_INPUT,
) -> tuple[list[str], list[dict[str, Any]], ScriptedLlm]:
    """Build an Agent with root_agent's tools/instruction and ScriptedLlm, then run one cycle."""
    fake_llm = ScriptedLlm(script)
    test_agent = Agent(
        name=root_agent.name,
        model=fake_llm,
        description=root_agent.description,
        instruction=root_agent.instruction,
        tools=list(root_agent.tools),
    )
    runner = InMemoryRunner(agent=test_agent, app_name=APP_NAME)
    session_id = uuid.uuid4().hex
    await runner.session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=session_id
    )

    content = types.Content(role="user", parts=[types.Part(text=message)])
    replies: list[str] = []
    tool_outputs: list[dict[str, Any]] = []
    async for event in runner.run_async(
        user_id=USER_ID, session_id=session_id, new_message=content
    ):
        for fr in event.get_function_responses():
            if isinstance(fr.response, dict):
                tool_outputs.append({"name": fr.name, "response": fr.response})
        if event.content and event.content.parts and event.is_final_response():
            for part in event.content.parts:
                if part.text:
                    replies.append(part.text)
    return replies, tool_outputs, fake_llm


def test_e2e_happy_path(env):
    store, calendar, mailer = env

    # First run: discover pending candidate, claim, check rules, find slots, email options.
    first_run_script = [
        tool_call("get_pending_candidates"),
        tool_call("claim_candidate", {"candidate_id": "C-001", "agent_id": AGENT_ID}),
        tool_call("get_job_rules", {"job_id": "ENG-101"}),
        tool_call("find_candidate_slots", {"candidate_id": "C-001", "agent_id": AGENT_ID}),
        tool_call(
            "send_candidate_slots_email",
            {
                "candidate_email": "sam@example.com",
                "slots_list": ["Option 1: Proposed slot 1", "Option 2: Proposed slot 2"],
                "prep_notes": "Bring a laptop. Be ready to discuss one past project in depth.",
                "candidate_id": "C-001",
                "agent_id": AGENT_ID,
            },
        ),
        final_text("Sent interview slot options to C-001."),
    ]
    _, first_outputs, _ = asyncio.run(_run_cycle_with_script(first_run_script))
    assert [o["name"] for o in first_outputs] == [
        "get_pending_candidates",
        "claim_candidate",
        "get_job_rules",
        "find_candidate_slots",
        "send_candidate_slots_email",
    ]
    assert store.get_candidate("C-001")["status"] == "awaiting_reply"
    assert len(store.get_candidate("C-001")["offered_slots"]) > 0

    # Second run: candidate replies selecting option 1 -> claim, book_interview(1), final text.
    second_run_script = [
        tool_call("claim_candidate", {"candidate_id": "C-001", "agent_id": AGENT_ID}),
        tool_call(
            "book_interview",
            {"candidate_id": "C-001", "option_number": 1, "agent_id": AGENT_ID},
        ),
        final_text("Booked interview for C-001 with Option 1."),
    ]
    replies, second_outputs, _ = asyncio.run(
        _run_cycle_with_script(second_run_script, message="reply: C-001 option 1")
    )
    assert [o["name"] for o in second_outputs] == ["claim_candidate", "book_interview"]
    assert second_outputs[1]["response"]["status"] == "booked"
    assert replies == ["Booked interview for C-001 with Option 1."]

    # Required state assertions:
    assert store.get_candidate("C-001")["status"] == "scheduled"
    assert len(store.interviews) == 1
    confirmation_emails = [
        m for m in mailer.outbox if m["subject"] == "Interview confirmed"
    ]
    assert len(confirmation_emails) == 1
    assert confirmation_emails[0]["to"] == "sam@example.com"
    assert len(calendar.events) == 1


def test_e2e_rules_missing_escalates(env):
    store, calendar, mailer = env
    store.add_candidate(
        {
            "candidate_id": "C-002",
            "job_id": "MISSING-JOB-999",
            "name": "Alex Morgan",
            "email": "alex@example.com",
            "timezone": "America/New_York",
        }
    )

    script = [
        tool_call("claim_candidate", {"candidate_id": "C-002", "agent_id": AGENT_ID}),
        tool_call("get_job_rules", {"job_id": "MISSING-JOB-999"}),
        tool_call(
            "escalate_to_recruiter",
            {
                "recruiter_email": "recruiter@company.example",
                "candidate_id": "C-002",
                "reason": "no InterviewRules entry for this job",
            },
        ),
        final_text("Escalated C-002 to recruiter because job rules are missing."),
    ]
    _, outputs, _ = asyncio.run(_run_cycle_with_script(script))
    assert [o["name"] for o in outputs] == [
        "claim_candidate",
        "get_job_rules",
        "escalate_to_recruiter",
    ]
    assert outputs[1]["response"]["status"] == "rules_invalid"
    assert outputs[2]["response"]["status"] == "escalated"

    assert store.get_candidate("C-002")["status"] == "escalated"
    assert len(mailer.outbox) == 1
    assert mailer.outbox[0]["to"] == "recruiter@company.example"
    assert "C-002" in mailer.outbox[0]["subject"]
    assert len(calendar.events) == 0


def test_e2e_slot_taken_before_reply_reoffers(env):
    store, calendar, mailer = env

    # First run: send initial offers to C-001.
    initial_script = [
        tool_call("get_pending_candidates"),
        tool_call("claim_candidate", {"candidate_id": "C-001", "agent_id": AGENT_ID}),
        tool_call("get_job_rules", {"job_id": "ENG-101"}),
        tool_call("find_candidate_slots", {"candidate_id": "C-001", "agent_id": AGENT_ID}),
        tool_call(
            "send_candidate_slots_email",
            {
                "candidate_email": "sam@example.com",
                "slots_list": ["Option 1: initial slot"],
                "prep_notes": "Bring a laptop. Be ready to discuss one past project in depth.",
                "candidate_id": "C-001",
                "agent_id": AGENT_ID,
            },
        ),
        final_text("Initial slot options sent."),
    ]
    asyncio.run(_run_cycle_with_script(initial_script))

    initial_offers = list(store.get_candidate("C-001")["offered_slots"])
    assert len(initial_offers) > 0
    option_1 = initial_offers[0]
    opt1_start = datetime.fromisoformat(option_1["start"])
    opt1_end = datetime.fromisoformat(option_1["end"])

    # Add a conflicting busy block for a panel member at option 1's time.
    calendar.external_busy.setdefault("alice@company.example", []).append(
        (opt1_start, opt1_end)
    )

    # Second run: candidate replies with option 1; booking fails with slot_unavailable,
    # so the agent re-runs find_candidate_slots and send_candidate_slots_email.
    conflict_script = [
        tool_call("claim_candidate", {"candidate_id": "C-001", "agent_id": AGENT_ID}),
        tool_call(
            "book_interview",
            {"candidate_id": "C-001", "option_number": 1, "agent_id": AGENT_ID},
        ),
        tool_call("find_candidate_slots", {"candidate_id": "C-001", "agent_id": AGENT_ID}),
        tool_call(
            "send_candidate_slots_email",
            {
                "candidate_email": "sam@example.com",
                "slots_list": ["Option 1: new slot"],
                "prep_notes": "Bring a laptop. Be ready to discuss one past project in depth.",
                "candidate_id": "C-001",
                "agent_id": AGENT_ID,
            },
        ),
        final_text("Option 1 was taken; sent new slot options."),
    ]
    _, conflict_outputs, _ = asyncio.run(
        _run_cycle_with_script(conflict_script, message="reply: C-001 option 1")
    )
    assert [o["name"] for o in conflict_outputs] == [
        "claim_candidate",
        "book_interview",
        "find_candidate_slots",
        "send_candidate_slots_email",
    ]
    assert conflict_outputs[1]["response"]["status"] == "slot_unavailable"
    assert conflict_outputs[2]["response"]["status"] == "ok"
    assert conflict_outputs[3]["response"]["status"] == "sent"

    # Assert there is no duplicate/conflicting event and that a new offer exists.
    assert len(calendar.events) == 0
    assert len(store.interviews) == 0
    assert store.get_candidate("C-001")["status"] == "awaiting_reply"

    new_offers = store.get_candidate("C-001")["offered_slots"]
    assert len(new_offers) > 0
    assert new_offers != initial_offers
    assert all(o["start"] != option_1["start"] for o in new_offers)

    offer_emails = [
        m for m in mailer.outbox if m["subject"] == "Interview time options"
    ]
    assert len(offer_emails) == 2
