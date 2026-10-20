"""test_hr_helpdesk.py - Pytest verification suite for Agent #07: Employee HR Helpdesk Agent."""

from __future__ import annotations
import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from main import app  # noqa: E402

client = TestClient(app)


def test_health_endpoint():
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["service"] == "HR_HelpdeskAgent"
    assert data["agent_number"] == 7
    assert data["title"] == "Employee HR Helpdesk Agent"
    assert data["google_client_id"] == "259388273008-n8vg3ae8be86e56svvg09rbdciah17u1.apps.googleusercontent.com"
    assert data["handbook_topics_count"] == 6


def test_handbook_topics_and_lookup():
    res = client.get("/api/handbook")
    assert res.status_code == 200
    data = res.json()
    categories = data["categories"]
    assert len(categories) == 6

    expected_titles = {
        "Annual & Maternity/Paternity Leave",
        "Medical & Dental Insurance Cover",
        "Payroll Dates & Payslip Questions",
        "Transport & Expense Claims",
        "Working Hours & Remote Work",
        "Public Holidays & Compassionate Leave",
    }
    actual_titles = {c["title"] for c in categories}
    assert actual_titles == expected_titles

    # Verify individual category lookup
    single = client.get("/api/handbook/medical_dental_insurance")
    assert single.status_code == 200
    cat_detail = single.json()
    assert cat_detail["title"] == "Medical & Dental Insurance Cover"
    assert "Section 5.2" in cat_detail["handbook_section"]
    assert len(cat_detail["entitlements_at_a_glance"]) >= 4
    assert len(cat_detail["steps_to_follow"]) >= 3


def test_ask_hr_helpdesk_agent_questions():
    # 1. Leave question
    res1 = client.post(
        "/api/helpdesk/ask",
        json={"question": "How many annual leave days do I get and what about maternity leave?"},
    )
    assert res1.status_code == 200
    d1 = res1.json()
    assert d1["ok"] is True
    assert d1["category_id"] == "annual_maternity_leave"
    assert "21" in d1["plain_english_answer"] or "21" in d1["policy_rule"]
    assert len(d1["entitlements_at_a_glance"]) >= 4
    assert len(d1["steps_to_follow"]) >= 3

    # 2. Medical & Dental question
    res2 = client.post(
        "/api/helpdesk/ask",
        json={"question": "What are my dental and optical insurance limits and how do I add my newborn child?"},
    )
    assert res2.status_code == 200
    d2 = res2.json()
    assert d2["category_id"] == "medical_dental_insurance"
    assert "Section 5.2" in d2["handbook_section"]

    # 3. Payroll & Payslip question via /api/agent/ask alias
    res3 = client.post(
        "/api/agent/ask",
        json={"question": "What date is salary paid each month and what if the 25th is on a weekend?"},
    )
    assert res3.status_code == 200
    d3 = res3.json()
    assert d3["category_id"] == "payroll_payslip"
    assert "25th" in d3["plain_english_answer"]


def test_create_and_resolve_hr_helpdesk_request():
    # List initial requests
    list_res = client.get("/api/helpdesk/requests")
    assert list_res.status_code == 200
    initial_count = len(list_res.json()["requests"])
    assert initial_count >= 4

    # Create a new HR Helpdesk Request ("Send Request to HR Team")
    create_res = client.post(
        "/api/helpdesk/requests",
        json={
            "employee_name": "Brian Kiprop",
            "employee_email": "brian.kiprop@sybyl.com",
            "department": "Engineering",
            "category_id": "medical_dental_insurance",
            "subject": "Add spouse to Group Medical Cover",
            "details": "Please enroll my spouse on our medical insurance cover. Marriage certificate attached.",
        },
    )
    assert create_res.status_code == 200
    created_data = create_res.json()
    assert created_data["ok"] is True
    new_req = created_data["request"]
    req_id = new_req["request_id"]
    assert req_id.startswith("HR-2026-")
    assert new_req["status"] == "Open"

    # Resolve the request
    resolve_res = client.post(
        f"/api/helpdesk/requests/{req_id}/resolve",
        json={
            "status": "Resolved",
            "hr_owner": "People Services Desk",
            "hr_response": "Spouse enrolled with AAR Insurance and smart card activated.",
        },
    )
    assert resolve_res.status_code == 200
    resolved_data = resolve_res.json()
    assert resolved_data["request"]["status"] == "Resolved"
    assert "smart card activated" in resolved_data["request"]["hr_response"]


def test_sso_and_otp_authentication_flows():
    # 1. Reject personal consumer email domain
    bad_otp = client.post("/api/auth/otp/request", json={"email": "someone@gmail.com"})
    assert bad_otp.status_code == 403

    # 2. Request and verify OTP for business domain
    otp_req = client.post("/api/auth/otp/request", json={"email": "jane.mutua@sybyl.com"})
    assert otp_req.status_code == 200
    otp_data = otp_req.json()
    assert otp_data["ok"] is True
    code = otp_data.get("demo_otp_hint")
    assert code and len(code) == 6

    otp_verify = client.post(
        "/api/auth/otp/verify",
        json={"email": "jane.mutua@sybyl.com", "code": code},
    )
    assert otp_verify.status_code == 200
    user = otp_verify.json()["user"]
    assert user["email"] == "jane.mutua@sybyl.com"
    assert user["name"] == "Jane Mutua"

    # 3. Instant Demo Sign-In
    demo_res = client.post("/api/auth/demo", json={"view_mode": "employee"})
    assert demo_res.status_code == 200
    assert demo_res.json()["ok"] is True

    # 4. Invalid Google credential returns 401
    google_res = client.post("/api/auth/google", json={"credential": "invalid-token"})
    assert google_res.status_code == 401


def test_spa_frontend_served():
    res = client.get("/")
    assert res.status_code == 200
    assert "Employee HR Helpdesk Agent" in res.text


def test_zero_occurrences_of_forbidden_word():
    root = Path(__file__).resolve().parent.parent
    parts_plain = ["co", "pi", "lot"]
    parts_hyphen = ["co-", "pi", "lot"]
    forbidden_plain = "".join(parts_plain)
    forbidden_hyphen = "".join(parts_hyphen)

    checked_files = 0
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in (".git", "node_modules", "__pycache__", ".pytest_cache") for part in path.parts):
            continue
        if path.suffix.lower() in (".py", ".jsx", ".js", ".html", ".css", ".md", ".json"):
            content = path.read_text(encoding="utf-8", errors="ignore").lower()
            assert forbidden_plain not in content, f"Forbidden term found in {path}"
            assert forbidden_hyphen not in content, f"Forbidden hyphenated term found in {path}"
            checked_files += 1

    assert checked_files >= 8
