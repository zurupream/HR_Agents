"""Tests for the Multi-Stage Interview Scheduler (Steps 1-5) and FastAPI Web Application."""

from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from scheduler.multistage import (
    MultiStageHub,
    SmtpImapService,
    get_multistage_hub,
    get_smtp_imap_service,
    seed_enterprise_scenario,
    set_multistage_hub,
    set_smtp_imap_service,
)
from scheduler.tools import calendar as cal
from scheduler.tools import scheduling_tools as t
from scheduler.tools.email import InMemoryMailer, set_mailer
from scheduler.webapp import app


@pytest.fixture
def multistage_env() -> tuple[MultiStageHub, cal.InMemoryCalendar, SmtpImapService]:
    """Reset calendar, mailer, SMTP service, and seed the enterprise multi-stage scenario."""
    calendar = cal.InMemoryCalendar()
    t.set_calendar(calendar)
    mailer = InMemoryMailer()
    set_mailer(mailer)
    smtp = SmtpImapService(sender_email="psrmreports@sybyl.com", live_smtp_enabled=False)
    set_smtp_imap_service(smtp)
    hub = seed_enterprise_scenario()
    return hub, calendar, smtp


def test_step1_panel_lead_slot_request_and_approval(multistage_env):
    """Step 1: AI calculates slot requirement for waiting candidates and emails the Panel Lead with AI options."""
    hub, _, smtp = multistage_env

    # Stage 2B of MERCH-2026-01 has 2 waiting candidates (Elena & Marcus) and 0 approved slots.
    calc = hub.calculate_slot_requirement("MERCH-2026-01", "STAGE-2", "2B")
    assert calc["waiting_candidates_count"] == 2
    assert calc["available_approved_slots"] == 0
    assert calc["slot_deficit"] >= 3  # 2 waiting + buffer

    # Trigger Step 1: Request slots from Panel Lead
    req = hub.request_slots_from_panel_lead("MERCH-2026-01", "STAGE-2", "2B", base_url="http://testserver")
    assert req["status"] == "requested"
    assert req["panel_lead_email"] == "inventory.lead@company.example"
    assert req["waiting_candidates_count"] == 2
    assert req["required_slots_count"] >= 3
    assert len(req["suggested_slots"]) >= req["required_slots_count"]

    # Verify email was sent from psrmreports@sybyl.com to the Panel Lead with approval link
    last_email = smtp.outbox[-1]
    assert last_email["from"] == "psrmreports@sybyl.com"
    assert last_email["to"] == "inventory.lead@company.example"
    assert req["request_token"] in last_email["body"]

    # Panel Lead approves 3 slots -> AI automatically sends live self-booking links to waiting candidates
    chosen_ids = [s["slot_id"] for s in req["suggested_slots"][:3]]
    approval = hub.approve_panel_slots(
        request_token=req["request_token"],
        selected_slot_ids=chosen_ids,
        base_url="http://testserver",
    )
    assert approval["status"] == "approved"
    assert approval["approved_count"] == 3
    assert len(approval["candidates_notified"]) == 2


def test_step2_live_candidate_booking_prevents_double_booking(multistage_env):
    """Step 2: Two candidates opening live booking links see live slots; once Candidate A books a slot, Candidate B cannot see or book it."""
    hub, _, _ = multistage_env

    # CAND-101 (Elena) and CAND-102 (Marcus) both have active live booking links for MERCH-2026-01 STAGE-2 2A
    elena_rec = hub.candidates["CAND-101"]["stage_progress"]["STAGE-2"]["2A"]
    marcus_rec = hub.candidates["CAND-102"]["stage_progress"]["STAGE-2"]["2A"]
    elena_token = elena_rec["booking_token"]
    marcus_token = marcus_rec["booking_token"]

    elena_view_before = hub.get_live_candidate_view(elena_token)
    marcus_view_before = hub.get_live_candidate_view(marcus_token)

    elena_slot_ids_before = [s["slot_id"] for s in elena_view_before["live_available_slots"]]
    marcus_slot_ids_before = [s["slot_id"] for s in marcus_view_before["live_available_slots"]]
    assert len(elena_slot_ids_before) >= 2
    assert elena_slot_ids_before == marcus_slot_ids_before

    target_slot_id = elena_slot_ids_before[0]

    # Elena books target_slot_id
    book_elena = hub.book_live_candidate_slot(booking_token=elena_token, slot_id=target_slot_id)
    assert book_elena["status"] == "booked"
    assert book_elena["event_id"]

    # Now Marcus opens/refreshes his live booking link -> target_slot_id MUST be gone!
    marcus_view_after = hub.get_live_candidate_view(marcus_token)
    marcus_slot_ids_after = [s["slot_id"] for s in marcus_view_after["live_available_slots"]]
    assert target_slot_id not in marcus_slot_ids_after

    # Even if Marcus had his browser tab open from earlier and clicks target_slot_id, atomic lock rejects it!
    race_attempt = hub.book_live_candidate_slot(booking_token=marcus_token, slot_id=target_slot_id)
    assert race_attempt["status"] == "slot_already_taken"

    # Marcus books one of the remaining live slots and succeeds
    remaining_slot_id = marcus_slot_ids_after[0]
    book_marcus = hub.book_live_candidate_slot(booking_token=marcus_token, slot_id=remaining_slot_id)
    assert book_marcus["status"] == "booked"


def test_step3_multistage_and_multi_interview_progression(multistage_env):
    """Step 3: Candidate in Stage 2 (which has 2A and 2B) only advances to Stage 3 after BOTH 2A and 2B pass."""
    hub, _, _ = multistage_env

    # CAND-106 (Liam O'Connor) is in CLOUD-2026-02 STAGE-2:
    # 2A is already 'completed' (passed=True), and 2B is currently 'booked'.
    cand = hub.candidates["CAND-106"]
    assert cand["current_stage_id"] == "STAGE-2"
    assert cand["stage_progress"]["STAGE-2"]["2A"]["status"] == "completed"
    assert cand["stage_progress"]["STAGE-2"]["2B"]["status"] == "booked"
    assert cand["stage_progress"]["STAGE-3"]["3A"]["status"] == "locked"

    # Complete 2B -> should automatically unlock STAGE-3 (3A) and advance current_stage_id to STAGE-3!
    res = hub.complete_interview_and_advance("CAND-106", "STAGE-2", "2B", passed=True)
    assert res["status"] == "completed"
    assert res["stage_completed"] is True
    assert res["advanced_to_stage"] == "STAGE-3"
    assert hub.candidates["CAND-106"]["current_stage_id"] == "STAGE-3"
    assert hub.candidates["CAND-106"]["stage_progress"]["STAGE-3"]["3A"]["status"] in (
        "awaiting_panel_slots",
        "link_sent",
    )


def test_step4_self_healing_interviewer_decline_backup_swap(multistage_env):
    """Step 4: When an assigned interviewer declines, AI hot-swaps a free backup interviewer from the stage pool."""
    hub, _, _ = multistage_env

    # CAND-103 (Priya Nair) has a booked interview in MERCH-2026-01 STAGE-1 1A with hr.merch@company.example
    rec_before = hub.candidates["CAND-103"]["stage_progress"]["STAGE-1"]["1A"]
    assert rec_before["status"] == "booked"
    original_start = rec_before["start"]

    swap = hub.handle_interviewer_decline(
        candidate_id="CAND-103",
        stage_id="STAGE-1",
        interview_code="1A",
        declined_email="hr.merch@company.example",
    )
    assert swap["status"] == "swapped_backup_interviewer"
    assert swap["replacement_interviewer"] in (
        "hr.retail.backup1@company.example",
        "hr.retail.backup2@company.example",
    )
    rec_after = hub.candidates["CAND-103"]["stage_progress"]["STAGE-1"]["1A"]
    assert rec_after["status"] == "booked"
    assert rec_after["start"] == original_start  # Candidate's time slot stayed unchanged!


def test_step5_webapp_screens_and_api_endpoints(multistage_env):
    """Step 5: Verify FastAPI Web App serves Screen 1 (Proactive Bottleneck Center) first, Apple HIG pages, and Log Out."""
    client = TestClient(app)

    # 1. Home page enforces Google SSO Sign-In first and renders Bottleneck Overview & Action Center with AI Agent
    home = client.get("/")
    assert home.status_code == 200
    assert "Bottleneck Overview &amp; Action Center" in home.text or "Bottleneck Overview & Action Center" in home.text
    assert 'let CURRENT_SCREEN = "screen-bottlenecks"' in home.text
    assert "let IS_LOGGED_OUT = true" in home.text
    assert "SF Pro Display" in home.text
    assert "Sign Out" in home.text
    assert "AI Agent" in home.text

    # 2. Verify all 5 distinct page routes and /login route
    for route, expected_screen in [
        ("/bottlenecks", "screen-bottlenecks"),
        ("/pipeline", "screen-pipeline"),
        ("/panel-approvals", "screen-panel"),
        ("/candidate-booking", "screen-candidate"),
        ("/outbox", "screen-outbox"),
    ]:
        page_res = client.get(route)
        assert page_res.status_code == 200
        assert f'let CURRENT_SCREEN = "{expected_screen}"' in page_res.text

    login_page = client.get("/login")
    assert login_page.status_code == 200
    assert "let IS_LOGGED_OUT = true" in login_page.text

    # 3. Verify Log Out and Sign In APIs
    logout_res = client.post("/api/auth/logout")
    assert logout_res.status_code == 200
    assert logout_res.json()["status"] == "logged_out"

    login_res = client.post("/api/auth/login", json={"email": "psrmreports@sybyl.com", "role": "HR Operations Lead"})
    assert login_res.status_code == 200
    assert login_res.json()["status"] == "authenticated"

    # 4. Dashboard API returns bottlenecks, jobs, candidates, and psrmreports@sybyl.com email status
    dash_res = client.get("/api/dashboard")
    assert dash_res.status_code == 200
    dash = dash_res.json()
    assert dash["summary"]["total_jobs"] == 2
    assert dash["summary"]["total_candidates"] == 8
    assert dash["summary"]["slot_shortages_count"] >= 1
    assert dash["email_service"]["sender_email"] == "psrmreports@sybyl.com"

    # 5. Auto-resolve all bottlenecks via API
    resolve_res = client.post("/api/bottlenecks/resolve-all")
    assert resolve_res.status_code == 200
    resolved = resolve_res.json()
    assert resolved["status"] == "resolved"
    assert resolved["actions_count"] >= 1

    # 6. Embedded ADK Agent Copilot chat endpoint responds with tool calls & updated dashboard
    chat_res = client.post(
        "/api/agent/chat",
        json={"message": "Analyze all active bottlenecks and summarize priority actions"},
    )
    assert chat_res.status_code == 200
    chat_data = chat_res.json()
    assert chat_data["status"] == "ok"
    assert "Bottleneck" in chat_data["reply"]


def test_step6_job_opening_3_default_stages_plus_dynamic_stage_addition(multistage_env):
    """Verify creating a Job Opening defaults to 3 stages and HR can click + to add Stage 4+."""
    client = TestClient(app)

    # 1. Create a new job opening without passing stages -> should default to 3 stages
    create_res = client.post(
        "/api/jobs",
        json={
            "job_id": "DATA-2026-03",
            "title": "Senior Data & AI Engineer",
            "department": "Data Science & AI",
            "location": "Hybrid • New York / Remote",
            "employment_type": "Full-Time",
            "openings_count": 3,
            "recruiter_email": "psrmreports@sybyl.com",
            "panel_lead_email": "jordan.lee@sybyl.com",
        },
    )
    assert create_res.status_code == 200
    created_job = create_res.json()["job"]
    assert created_job["job_id"] == "DATA-2026-03"
    assert created_job["openings_count"] == 3
    assert len(created_job["stages"]) == 3

    # 2. HR clicks "+ Add Stage" to add Stage 4 to DATA-2026-03
    add_stage_res = client.post(
        "/api/jobs/DATA-2026-03/stages",
        json={
            "stage_name": "Stage 4: Executive Culture & Panel Fit",
            "interview_code": "4A",
            "interview_title": "Executive Panel Assessment",
            "duration_minutes": 45,
            "panel_lead_email": "jordan.lee@sybyl.com",
        },
    )
    assert add_stage_res.status_code == 200
    updated_job = add_stage_res.json()["job"]
    assert len(updated_job["stages"]) == 4
    assert updated_job["stages"][3]["name"] == "Stage 4: Executive Culture & Panel Fit"

    # 3. Verify dashboard exposes all stages and stage_health_cards
    dash = client.get("/api/dashboard").json()
    assert dash["summary"]["total_jobs"] == 3
    assert len(dash["stage_health_cards"]) >= 10  # 3 + 3 + 4 stages across 3 jobs

    home_html = client.get("/").text
    assert "home-jobs-stages-overview" in home_html
    assert "openAndRequestPanelSlots" in home_html
    assert 'data-theme="sand"' in home_html
    assert 'data-theme-dot="daylight"' in home_html
    assert 'data-theme-dot="sand"' in home_html
    assert 'data-theme-dot="dusk"' in home_html
    assert 'data-theme-dot="midnight"' in home_html
    assert "--bg-canvas: #F7F5F0" in home_html
    assert "--bg-canvas: #1C1E26" in home_html
    assert "--bg-canvas: #0B0C10" in home_html
    assert "ADK" not in home_html
    assert "Vertex AI" not in home_html

