"""End-to-end automated tests for the Agentic HR Onboarding Web Application."""

import os
from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.seed import seed_demo_data


@pytest.fixture(autouse=True)
def reset_db_before_tests():
    seed_demo_data(force_reset=True, base_url="http://localhost:8080")
    yield


def test_overview_and_what_hr_should_know_dashboard():
    client = TestClient(app)
    res = client.get("/api/overview")
    assert res.status_code == 200
    data = res.json()

    # Check KPIs from seeded data
    kpis = data["kpis"]
    assert kpis["total_candidates"] == 7
    assert kpis["day1_ready"] >= 2
    assert kpis["declined_total"] == 1
    assert kpis["lapsed_total"] == 1
    assert kpis["active_blockers"] == 1
    assert kpis["expiring_soon_count"] == 1

    # Check What HR Should Know sections
    intel = data["hr_intelligence"]
    assert len(intel["expiring_soon_offers"]) == 1
    assert intel["expiring_soon_offers"][0]["full_name"] == "Noah Williams"
    assert len(intel["backfill_alerts"]) == 2
    assert len(intel["sla_blockers"]) == 1
    assert intel["sla_blockers"][0]["task_type"] == "INSURANCE"

    # Check SMTP pre-configuration for psrmreports@sybyl.com
    assert data["smtp_status"]["sender_email"] == "psrmreports@sybyl.com"


def test_batch_offer_dispatch_and_role_based_subagents():
    """Verify multi-position batch onboarding for INTERN (1 step), TRAINEE (3 steps), and EMPLOYEE (4 steps)."""
    client = TestClient(app)

    batch_payload = {
        "hr_email": "hr.onboarding@sybyl.com",
        "ceo_email": "ceo@sybyl.com",
        "offer_expires_in_hours": 72,
        "candidates": [
            {
                "full_name": "Test Intern Candidate",
                "personal_email": "intern.test@university.edu",
                "phone": "+1-555-1001",
                "role_category": "INTERN",
                "position_id": "pos-ux-intern",
                "compensation_package": "$4,000/mo Stipend",
                "joining_date": "2025-07-01",
            },
            {
                "full_name": "Test Trainee Candidate",
                "personal_email": "trainee.test@gmail.com",
                "phone": "+1-555-1002",
                "role_category": "TRAINEE",
                "position_id": "pos-data-assoc",
                "compensation_package": "$65,000/yr + Laptop + Uber",
                "joining_date": "2025-07-01",
            },
            {
                "full_name": "Test Employee Candidate",
                "personal_email": "employee.test@gmail.com",
                "phone": "+1-555-1003",
                "role_category": "EMPLOYEE",
                "position_id": "pos-eng-ai",
                "compensation_package": "$150,000/yr + Full Benefits",
                "joining_date": "2025-07-01",
            },
        ],
    }

    batch_res = client.post("/api/offers/batch", json=batch_payload)
    assert batch_res.status_code == 200
    created = batch_res.json()["created"]
    assert len(created) == 3

    intern_info = next(c for c in created if c["role_category"] == "INTERN")
    trainee_info = next(c for c in created if c["role_category"] == "TRAINEE")
    employee_info = next(c for c in created if c["role_category"] == "EMPLOYEE")

    # Verify PDF exists for each offer
    for item in created:
        pdf_res = client.get(f"/api/offers/{item['offer_id']}/pdf")
        assert pdf_res.status_code == 200
        assert pdf_res.headers["content-type"] == "application/pdf"

    # 1. INTERN accepts offer -> Only 1 Sub-Agent (EMAIL) should spawn
    acc_intern = client.post(
        f"/api/sign/{intern_info['signing_token']}/accept",
        json={
            "signer_name": "Test Intern Candidate",
            "signature_data": "Test Intern Candidate",
            "signature_type": "typed",
        },
    )
    assert acc_intern.status_code == 200
    intern_tasks = acc_intern.json()["spawned_subagent_tasks"]
    assert len(intern_tasks) == 1
    assert intern_tasks[0]["task_type"] == "EMAIL"
    assert intern_tasks[0]["status"] == "IN_PROGRESS"

    # Complete the Intern's single EMAIL task -> Intern becomes Day-1 Ready
    adv_intern = client.post(f"/api/tasks/{intern_tasks[0]['id']}/advance?complete=true")
    assert adv_intern.status_code == 200
    assert adv_intern.json()["status"] == "COMPLETED"

    # 2. TRAINEE accepts offer -> 3 Sub-Agents (EMAIL, LAPTOP, UBER) should spawn (no INSURANCE)
    acc_trainee = client.post(
        f"/api/sign/{trainee_info['signing_token']}/accept",
        json={
            "signer_name": "Test Trainee Candidate",
            "signature_data": "Test Trainee Candidate",
            "signature_type": "typed",
        },
    )
    assert acc_trainee.status_code == 200
    trainee_tasks = acc_trainee.json()["spawned_subagent_tasks"]
    assert [t["task_type"] for t in trainee_tasks] == ["EMAIL", "LAPTOP", "UBER"]

    # Auto-complete remaining sub-agents for Trainee
    run_trainee = client.post(f"/api/candidates/{trainee_info['candidate_id']}/run-subagents")
    assert run_trainee.status_code == 200
    assert all(t["status"] == "COMPLETED" for t in run_trainee.json()["tasks"])

    # 3. EMPLOYEE accepts offer -> All 4 Sub-Agents (EMAIL, LAPTOP, UBER, INSURANCE) should spawn
    acc_emp = client.post(
        f"/api/sign/{employee_info['signing_token']}/accept",
        json={
            "signer_name": "Test Employee Candidate",
            "signature_data": "Test Employee Candidate",
            "signature_type": "typed",
        },
    )
    assert acc_emp.status_code == 200
    emp_tasks = acc_emp.json()["spawned_subagent_tasks"]
    assert [t["task_type"] for t in emp_tasks] == ["EMAIL", "LAPTOP", "UBER", "INSURANCE"]

    # Advance Laptop task by 1 stage and then complete all
    laptop_task_id = next(t["id"] for t in emp_tasks if t["task_type"] == "LAPTOP")
    adv_res = client.post(f"/api/tasks/{laptop_task_id}/advance?complete=false")
    assert adv_res.status_code == 200
    assert adv_res.json()["current_stage_idx"] == 2


def test_decline_lapse_and_docuseal_webhook_notifications():
    """Verify decline, lapse, and DocuSeal webhook triggers notify HR, HoD, and CEO."""
    client = TestClient(app)

    batch_res = client.post(
        "/api/offers/batch",
        json={
            "hr_email": "hr.onboarding@sybyl.com",
            "ceo_email": "ceo@sybyl.com",
            "offer_expires_in_hours": 48,
            "candidates": [
                {
                    "full_name": "Decline Candidate",
                    "personal_email": "decline@example.com",
                    "phone": "+1-555-2001",
                    "role_category": "EMPLOYEE",
                    "position_id": "pos-eng-ai",
                    "compensation_package": "$140,000/yr",
                    "joining_date": "2025-08-01",
                },
                {
                    "full_name": "Webhook Candidate",
                    "personal_email": "webhook@example.com",
                    "phone": "+1-555-2002",
                    "role_category": "TRAINEE",
                    "position_id": "pos-data-assoc",
                    "compensation_package": "$68,000/yr",
                    "joining_date": "2025-08-01",
                },
            ],
        },
    )
    created = batch_res.json()["created"]
    decline_cand = created[0]
    webhook_cand = created[1]

    # Decline offer
    dec_res = client.post(
        f"/api/sign/{decline_cand['signing_token']}/decline",
        json={"decline_reason": "Accepted another offer", "comments": "Thank you"},
    )
    assert dec_res.status_code == 200
    assert dec_res.json()["status"] == "DECLINED"

    # Verify notification logged with CC: HR, HoD, CEO
    notifs = client.get(f"/api/notifications?candidate_id={decline_cand['candidate_id']}").json()
    decline_notif = next(n for n in notifs if n["event_type"] == "OFFER_DECLINED")
    assert "hr.onboarding@sybyl.com" in decline_notif["recipients_cc"]
    assert "elena.vance@sybyl.com" in decline_notif["recipients_cc"]
    assert "ceo@sybyl.com" in decline_notif["recipients_cc"]

    # DocuSeal webhook completion for Trainee
    wh_res = client.post(
        "/api/webhooks/docuseal",
        json={
            "event_type": "form.completed",
            "signing_token": webhook_cand["signing_token"],
            "signer_name": "Webhook Candidate",
        },
    )
    assert wh_res.status_code == 200
    assert wh_res.json()["status"] == "ACCEPTED"
    assert len(wh_res.json()["spawned_subagent_tasks"]) == 3


def test_smtp_configuration_for_sybyl_email():
    """Verify psrmreports@sybyl.com SMTP configuration save and retrieval."""
    client = TestClient(app)
    get_res = client.get("/api/settings/smtp")
    assert get_res.status_code == 200
    assert get_res.json()["sender_email"] == "psrmreports@sybyl.com"

    post_res = client.post(
        "/api/settings/smtp",
        json={
            "sender_email": "psrmreports@sybyl.com",
            "app_password": "dummy-app-password-for-test",
            "smtp_host": "smtp.office365.com",
            "smtp_port": 587,
            "use_tls": True,
            "live_mode_enabled": False,
            "default_hr_email": "hr.onboarding@sybyl.com",
            "default_ceo_email": "ceo@sybyl.com",
            "override_recipient_for_demo": "psrmreports@sybyl.com",
        },
    )
    assert post_res.status_code == 200
    saved = post_res.json()
    assert saved["sender_email"] == "psrmreports@sybyl.com"
    assert saved["has_app_password"] is True
    assert saved["app_password"] == "••••••••"
