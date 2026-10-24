"""End-to-end automated tests for HR Offboarding Pro Agent."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Use an isolated temporary SQLite DB for tests
_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_db.close()
os.environ["HR_OFFBOARDING_DB"] = _tmp_db.name

from fastapi.testclient import TestClient
from app.main import app
from app.database import init_db
from app.seed import seed_demo_data_if_empty

init_db()
seed_demo_data_if_empty()
client = TestClient(app)


def test_sso_and_otp_authentication():
    """Verify Google SSO config, Demo SSO login, and Work Email OTP verification."""
    cfg = client.get("/api/auth/config")
    assert cfg.status_code == 200
    assert "googleusercontent.com" in cfg.json()["google_client_id"]

    demo = client.post("/api/auth/demo", json={"persona": "Elena Rostova"})
    assert demo.status_code == 200
    assert demo.json()["authenticated"] is True

    otp_req = client.post("/api/auth/otp/request", json={"email": "hr.lead@acme.com"})
    assert otp_req.status_code == 200
    code = otp_req.json()["demo_code"]

    otp_ver = client.post("/api/auth/otp/verify", json={"email": "hr.lead@acme.com", "code": code})
    assert otp_ver.status_code == 200
    assert otp_ver.json()["authenticated"] is True


def test_overview_and_role_matrix():
    """Verify overview KPIs and reverse role-based offboarding matrix."""
    res = client.get("/api/overview")
    assert res.status_code == 200
    data = res.json()
    assert data["kpis"]["total_exiting"] >= 6
    assert data["role_matrix"]["INTERN"] == ["EMAIL"]
    assert data["role_matrix"]["TRAINEE"] == ["UBER", "LAPTOP", "EMAIL"]
    assert data["role_matrix"]["EMPLOYEE"] == ["INSURANCE", "UBER", "LAPTOP", "EMAIL"]


def test_intern_offboarding_spawns_only_email_deactivation():
    """Intern exit should ONLY spawn the IT Email & Access Deactivation Agent (1 task)."""
    res = client.post(
        "/api/employees",
        json={
            "full_name": "Test Intern Maya",
            "personal_email": "maya.intern@edu.org",
            "phone": "+1 555-0100",
            "role_category": "INTERN",
            "job_title": "Design Intern",
            "department": "Brand Design",
            "manager_name": "Hannah Abbott",
            "location": "Remote",
            "compensation_amount": 4000,
            "compensation_period": "per month",
            "last_working_day": "2026-06-30",
            "exit_type": "End of Internship Term",
            "days_worked_final_month": 15,
            "unused_leave_days": 1.0,
            "asset_deduction": 0.0,
        },
    )
    assert res.status_code == 200
    emp = res.json()
    tasks = emp["tasks"]
    assert len(tasks) == 1
    assert tasks[0]["task_type"] == "EMAIL"
    assert tasks[0]["status"] == "IN_PROGRESS"

    token = emp["offer"]["signing_token"]
    acc = client.post(f"/api/sign/{token}/accept", json={"signature_name": "Test Intern Maya"})
    assert acc.status_code == 200

    # Advance EMAIL through remaining stages to complete offboarding
    task_id = tasks[0]["id"]
    for _ in range(4):
        adv = client.post(f"/api/tasks/{task_id}/advance", json={})
        assert adv.status_code == 200
    final_state = adv.json()
    assert final_state["offboarding_status"] == "OFFBOARDED"
    assert final_state["overall_progress_pct"] == 100


def test_trainee_offboarding_spawns_uber_laptop_email_in_reverse():
    """Trainee exit spawns UBER, LAPTOP, and EMAIL (no Health Insurance), with EMAIL waiting on LAPTOP."""
    res = client.post(
        "/api/employees",
        json={
            "full_name": "Test Trainee Leo",
            "personal_email": "leo.trainee@uni.edu",
            "phone": "+1 555-0101",
            "role_category": "TRAINEE",
            "job_title": "Operations Graduate Trainee",
            "department": "Operations",
            "manager_name": "Marcus Sterling",
            "location": "Chicago, IL",
            "compensation_amount": 72000,
            "compensation_period": "per year",
            "last_working_day": "2026-07-15",
            "exit_type": "End of Rotational Contract",
        },
    )
    assert res.status_code == 200
    emp = res.json()
    task_types = [t["task_type"] for t in emp["tasks"]]
    assert task_types == ["UBER", "LAPTOP", "EMAIL"]
    assert "INSURANCE" not in task_types

    email_task = next(t for t in emp["tasks"] if t["task_type"] == "EMAIL")
    assert email_task["status"] == "PENDING"

    # Advancing EMAIL before LAPTOP return is completed must return 400
    blocked_adv = client.post(f"/api/tasks/{email_task['id']}/advance", json={})
    assert blocked_adv.status_code == 400


def test_employee_full_reverse_offboarding_and_pdfs():
    """Full-time employee exit spawns INSURANCE, UBER, LAPTOP, EMAIL, enforces LAPTOP->EMAIL dependency, and generates both PDFs."""
    res = client.post(
        "/api/employees",
        json={
            "full_name": "Test Employee Jordan",
            "personal_email": "jordan.emp@gmail.com",
            "phone": "+1 555-0102",
            "role_category": "EMPLOYEE",
            "job_title": "Principal Platform Engineer",
            "department": "Cloud Engineering",
            "manager_name": "Elena Rostova",
            "location": "San Francisco, CA",
            "compensation_amount": 195000,
            "compensation_period": "per year",
            "last_working_day": "2026-08-01",
            "exit_type": "Voluntary Resignation",
            "days_worked_final_month": 20,
            "unused_leave_days": 8.0,
            "asset_deduction": 150.0,
        },
    )
    assert res.status_code == 200
    emp = res.json()
    cid = emp["id"]
    assert emp["settlement"]["net_settlement"] > 0

    task_types = [t["task_type"] for t in emp["tasks"]]
    assert task_types == ["INSURANCE", "UBER", "LAPTOP", "EMAIL"]

    # Both Clearance Statement PDF and Certificate of Service PDF must return valid %PDF-1.4 bytes
    clr_pdf = client.get(f"/api/employees/{cid}/clearance-pdf")
    assert clr_pdf.status_code == 200
    assert clr_pdf.headers["content-type"] == "application/pdf"
    assert clr_pdf.content[:4] == b"%PDF"

    cert_pdf = client.get(f"/api/employees/{cid}/certificate-pdf")
    assert cert_pdf.status_code == 200
    assert cert_pdf.headers["content-type"] == "application/pdf"
    assert cert_pdf.content[:4] == b"%PDF"

    # Complete INSURANCE, UBER, and LAPTOP first
    for t in emp["tasks"]:
        if t["task_type"] != "EMAIL":
            for _ in range(4):
                r = client.post(f"/api/tasks/{t['id']}/advance", json={})
                assert r.status_code == 200

    # Verify EMAIL is now automatically unlocked to IN_PROGRESS
    mid_state = client.get(f"/api/employees/{cid}").json()
    email_task = next(t for t in mid_state["tasks"] if t["task_type"] == "EMAIL")
    assert email_task["status"] == "IN_PROGRESS"

    # Complete EMAIL to finish 100% offboarding
    for _ in range(4):
        r = client.post(f"/api/tasks/{email_task['id']}/advance", json={})
        assert r.status_code == 200

    done_state = r.json()
    assert done_state["offboarding_status"] == "OFFBOARDED"
    assert done_state["overall_progress_pct"] == 100


def test_settlement_dispute_creates_hr_action_center_alert():
    """Raising a Final Settlement query logs a dispute and adds a high-priority HR Action Center item."""
    res = client.post(
        "/api/employees",
        json={
            "full_name": "Dispute Test Employee",
            "personal_email": "dispute.test@gmail.com",
            "phone": "+1 555-0199",
            "role_category": "EMPLOYEE",
            "job_title": "Product Manager",
            "department": "Product",
            "manager_name": "Elena Rostova",
            "location": "New York, NY",
            "compensation_amount": 160000,
            "compensation_period": "per year",
            "last_working_day": "2026-08-15",
        },
    )
    emp = res.json()
    token = emp["offer"]["signing_token"]

    disp = client.post(
        f"/api/sign/{token}/dispute",
        json={"reason": "Unused PTO balance is missing 3 carryover days from 2025."},
    )
    assert disp.status_code == 200
    assert disp.json()["offboarding_status"] == "SETTLEMENT_DISPUTED"

    ov = client.get("/api/overview").json()
    reasons = [a["reason"] for a in ov["action_items"]]
    assert any("carryover days" in r for r in reasons)


def test_apple_reading_themes_and_appearance_switcher():
    """Verify the 4 Apple-inspired reading themes and compact 4-dot switcher in index.html & sign.html."""
    for route in ["/", "/sign/demo-token-check"]:
        res = client.get(route)
        assert res.status_code == 200
        html = res.text
        for theme_id in ["daylight", "sand", "dusk", "midnight"]:
            assert f'data-theme="{theme_id}"' in html
            assert f"setTheme('{theme_id}')" in html
        for css_var in [
            "--bg-canvas",
            "--bg-sidebar",
            "--bg-card",
            "--text-primary",
            "--text-muted",
            "--border-subtle",
        ]:
            assert css_var in html

