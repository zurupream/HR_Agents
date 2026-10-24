"""Pytest Verification Suite for Agent #08: Learning, Certification Expiry & Skills Matrix Agent."""

from datetime import date, timedelta
import os
from pathlib import Path
from fastapi.testclient import TestClient
import pytest

from app.compliance_engine import (
    STATUS_ACTIVE,
    STATUS_EXPIRED,
    STATUS_EXPIRING_30,
    STATUS_EXPIRING_60_90,
    calculate_days_remaining,
    classify_certification_status,
    format_days_remaining_label,
)
from app.database import seed_demo_data
from app.main import app


@pytest.fixture(autouse=True)
def isolated_test_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test_hr_skills_compliance.db"
    monkeypatch.setenv("HR_SKILLS_DB", str(db_file))
    seed_demo_data(force_reset=True)
    yield


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def test_deterministic_days_remaining_and_status_classification():
    ref = date(2026, 10, 20)

    # 1. Expired (< 0 days)
    days_exp = calculate_days_remaining("2026-10-05", reference_date=ref)
    assert days_exp == -15
    assert classify_certification_status(days_exp) == STATUS_EXPIRED
    assert format_days_remaining_label(days_exp) == "15 days overdue"

    # 2. Expiring in 30 Days (0 <= days <= 30)
    days_today = calculate_days_remaining("2026-10-20", reference_date=ref)
    assert days_today == 0
    assert classify_certification_status(days_today) == STATUS_EXPIRING_30
    assert format_days_remaining_label(days_today) == "Expires today"

    days_14 = calculate_days_remaining("2026-11-03", reference_date=ref)
    assert days_14 == 14
    assert classify_certification_status(days_14) == STATUS_EXPIRING_30
    assert format_days_remaining_label(days_14) == "14 days left"

    days_30 = calculate_days_remaining("2026-11-19", reference_date=ref)
    assert days_30 == 30
    assert classify_certification_status(days_30) == STATUS_EXPIRING_30

    # 3. Expiring in 60–90 Days (31 <= days <= 90)
    days_65 = calculate_days_remaining("2026-12-24", reference_date=ref)
    assert days_65 == 65
    assert classify_certification_status(days_65) == STATUS_EXPIRING_60_90

    days_90 = calculate_days_remaining("2027-01-18", reference_date=ref)
    assert days_90 == 90
    assert classify_certification_status(days_90) == STATUS_EXPIRING_60_90

    # 4. Active & Valid (> 90 days)
    days_180 = calculate_days_remaining("2027-04-18", reference_date=ref)
    assert days_180 == 180
    assert classify_certification_status(days_180) == STATUS_ACTIVE


def test_sso_and_authentication_endpoints(client: TestClient):
    # 1. Auth config
    cfg = client.get("/api/auth/config")
    assert cfg.status_code == 200
    assert cfg.json()["google_client_id"].startswith("259388273008-")

    # 2. Google SSO
    g_res = client.post("/api/auth/google", json={"credential": "demo-google-sso-token"})
    assert g_res.status_code == 200
    g_data = g_res.json()
    assert g_data["authenticated"] is True
    assert g_data["method"] == "Google Single Sign-On"

    # 3. Email OTP Request & Verify
    otp_req = client.post("/api/auth/otp/request", json={"email": "amara.okafor@acme.com"})
    assert otp_req.status_code == 200
    code = otp_req.json()["demo_code"]

    otp_ver = client.post(
        "/api/auth/otp/verify", json={"email": "amara.okafor@acme.com", "code": code}
    )
    assert otp_ver.status_code == 200
    assert otp_ver.json()["authenticated"] is True

    # 4. Instant Demo Sign-In (L&D and Compliance Lead)
    demo_res = client.post("/api/auth/demo", json={"persona": "Amara Okafor"})
    assert demo_res.status_code == 200
    demo_data = demo_res.json()
    assert demo_data["authenticated"] is True
    assert demo_data["user"]["role"] == "L&D and Compliance Lead"


def test_overview_kpis_and_certification_tracker(client: TestClient):
    res = client.get("/api/overview")
    assert res.status_code == 200
    body = res.json()
    kpis = body["kpis"]
    assert kpis["total_tracked_certifications"] == 12
    assert kpis["expired_immediate_renewal"] == 3
    assert kpis["expiring_within_30_days"] == 3
    assert kpis["expiring_60_to_90_days"] == 2
    assert kpis["active_and_valid_over_90_days"] == 4
    assert kpis["valid_and_compliant"] == 9
    assert kpis["reminders_sent"] == 3

    # Filter by status badge
    exp_res = client.get("/api/certifications", params={"status": STATUS_EXPIRED})
    assert exp_res.status_code == 200
    assert exp_res.json()["count"] == 3


def test_single_and_bulk_renewal_reminder_dispatch(client: TestClient):
    # Dispatch single reminder
    r1 = client.post(
        "/api/certifications/1/remind",
        json={"sender_name": "Amara Okafor (L&D and Compliance Lead)"},
    )
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["sent"] is True
    assert "David Kimani" in d1["message"]
    assert d1["kpis"]["reminders_sent"] == 4

    # Dispatch bulk reminders for all expired + 30-day + 60-90 day records (3 + 3 + 2 = 8)
    r_bulk = client.post(
        "/api/certifications/remind-bulk",
        json={"include_sixty_ninety": True, "sender_name": "Amara Okafor"},
    )
    assert r_bulk.status_code == 200
    b_data = r_bulk.json()
    assert b_data["sent"] is True
    assert b_data["dispatched_count"] == 8
    assert b_data["kpis"]["reminders_sent"] == 12


def test_mark_renewed_and_create_certificate(client: TestClient):
    # Renew an expired certificate (#1)
    renew_res = client.post("/api/certifications/1/renew", json={})
    assert renew_res.status_code == 200
    renew_data = renew_res.json()
    assert renew_data["certification"]["status_badge"] == STATUS_ACTIVE
    assert renew_data["kpis"]["expired_immediate_renewal"] == 2

    # Create a new certificate expiring in 15 days
    exp_15 = (date.today() + timedelta(days=15)).isoformat()
    create_res = client.post(
        "/api/certifications",
        json={
            "employee_name": "Joy Muthoni",
            "employee_email": "joy.muthoni@acme.com",
            "role_title": "Safety & Compliance Specialist",
            "department": "Operations & Safety",
            "manager_name": "Peter Njoroge",
            "manager_email": "peter.njoroge@acme.com",
            "certificate_name": "NEBOSH International General Certificate",
            "issuing_body": "NEBOSH Board",
            "expiry_date": exp_15,
        },
    )
    assert create_res.status_code == 200
    created_cert = create_res.json()["certification"]
    assert created_cert["status_badge"] == STATUS_EXPIRING_30
    assert created_cert["days_remaining"] == 15


def test_skills_matrix_and_ask_certification_agent_qa(client: TestClient):
    m_res = client.get("/api/skills-matrix")
    assert m_res.status_code == 200
    matrix = m_res.json()["skills_matrix"]
    assert len(matrix) == 6

    # Ask Certification Agent about expired licenses
    q1 = client.post(
        "/api/agent/ask",
        json={"question": "Which employees have expired licenses right now?"},
    )
    assert q1.status_code == 200
    ans1 = q1.json()
    assert ans1["agent_name"] == "Certification & Skills Agent"
    assert len(ans1["highlights"]) == 3

    # Ask Certification Agent about 30-day renewals
    q2 = client.post(
        "/api/agent/ask",
        json={"question": "Who has certificates expiring within 30 days?"},
    )
    assert q2.status_code == 200
    assert len(q2.json()["highlights"]) == 3

    # Ask Certification Agent about active training bonds
    q3 = client.post(
        "/api/agent/ask",
        json={"question": "Which employees have active training bonds?"},
    )
    assert q3.status_code == 200
    assert "training bonds" in q3.json()["answer"].lower()


def test_audit_report_pdf_csv_and_apple_ui(client: TestClient):
    ui_res = client.get("/")
    assert ui_res.status_code == 200
    html = ui_res.text
    assert "Step 1: Track Employee Licenses &amp; Mandatory Certifications" in html
    assert "Step 2: 30 / 60 / 90-Day Expiry Detection Agent" in html
    assert "Step 3: One-Click Renewal Reminders &amp; Compliance Report" in html
    assert "Instant Demo Sign-In (L&amp;D and Compliance Lead)" in html
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

    pdf_res = client.get("/api/audit-report/pdf")
    assert pdf_res.status_code == 200
    assert pdf_res.headers["content-type"] == "application/pdf"
    assert pdf_res.content.startswith(b"%PDF")

    csv_res = client.get("/api/audit-report/csv")
    assert csv_res.status_code == 200
    assert "Employee Name" in csv_res.text


def test_zero_occurrences_of_forbidden_word():
    """Confirm zero occurrences of the forbidden c-word across the entire codebase."""
    parts = ["co", "pi", "lot"]
    forbidden = "".join(parts)
    root = Path(__file__).resolve().parent.parent
    for path in root.rglob("*"):
        if path.is_file() and path.suffix in {".py", ".html", ".md", ".txt", ".json"}:
            content = path.read_text(encoding="utf-8", errors="ignore").lower()
            assert forbidden not in content, f"Forbidden term found in {path}"

