"""
Pytest test suite for Agent #06: Attendance Clock-In/Out & Leave Notification Agent.
Tests deterministic clock-in/clock-out hours calculation, approved leave cross-check logic,
single/bulk HR notification endpoints, SSO authentication endpoints, and naming compliance.
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "0"

from fastapi.testclient import TestClient

from auth_service import _OTP_STORE, GOOGLE_CLIENT_ID
from main import app
from seed_data import (
    calculate_hours_worked,
    evaluate_employee_attendance,
    get_approved_leave_hours,
)

client = TestClient(app)


def setup_function() -> None:
    client.post("/api/attendance/reset")


def test_health_check() -> None:
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["agent_id"] == "06"
    assert data["service"] == "HR_AttendanceLeaveAgent"
    assert data["google_client_id"] == GOOGLE_CLIENT_ID
    assert data["employees_loaded"] == 12


def test_deterministic_clock_in_out_hours_calculation() -> None:
    assert calculate_hours_worked("08:30", "16:30") == 8.0
    assert calculate_hours_worked("09:45", "15:15") == 5.5
    assert calculate_hours_worked("08:15", "16:45") == 8.5
    assert calculate_hours_worked("10:30", "15:00") == 4.5
    assert calculate_hours_worked("", "") == 0.0
    assert calculate_hours_worked("09:00", "") == 0.0
    assert calculate_hours_worked("", "17:00") == 0.0
    assert calculate_hours_worked("16:00", "09:00") == 0.0


def test_leave_cross_check_logic() -> None:
    assert get_approved_leave_hours("None", 8.0) == 0.0
    assert get_approved_leave_hours("Pending", 8.0) == 0.0
    assert get_approved_leave_hours("Approved Annual Leave", 8.0) == 8.0
    assert get_approved_leave_hours("Approved Sick Leave", 8.0) == 8.0
    assert get_approved_leave_hours("Approved Half-Day Leave", 8.0) == 4.0

    # Missed hours with no leave -> Missed Hours — No Leave
    rec_missed = evaluate_employee_attendance(
        {
            "employee_id": "EMP-TEST-1",
            "employee_name": "Test Employee",
            "department": "Operations",
            "email": "test@company.co.ke",
            "attendance_date": "2026-10-20",
            "clock_in": "09:30",
            "clock_out": "14:30",
            "required_hours": 8.0,
            "leave_status": "None",
        }
    )
    assert rec_missed["hours_worked"] == 5.0
    assert rec_missed["hours_shortfall"] == 3.0
    assert rec_missed["status_badge"] == "Missed Hours — No Leave"
    assert rec_missed["hr_action_required"] is True

    # Absent with Pending (unapproved) leave -> Absent — No Leave
    rec_absent = evaluate_employee_attendance(
        {
            "employee_id": "EMP-TEST-2",
            "employee_name": "Test Absent",
            "department": "Finance",
            "email": "absent@company.co.ke",
            "attendance_date": "2026-10-20",
            "clock_in": "",
            "clock_out": "",
            "required_hours": 8.0,
            "leave_status": "Pending",
        }
    )
    assert rec_absent["hours_worked"] == 0.0
    assert rec_absent["hours_shortfall"] == 8.0
    assert rec_absent["status_badge"] == "Absent — No Leave"
    assert rec_absent["hr_action_required"] is True

    # Approved Annual Leave -> Approved Leave (0.0 shortfall)
    rec_leave = evaluate_employee_attendance(
        {
            "employee_id": "EMP-TEST-3",
            "employee_name": "Test Leave",
            "department": "HR",
            "email": "leave@company.co.ke",
            "attendance_date": "2026-10-20",
            "clock_in": "",
            "clock_out": "",
            "required_hours": 8.0,
            "leave_status": "Approved Annual Leave",
        }
    )
    assert rec_leave["hours_shortfall"] == 0.0
    assert rec_leave["status_badge"] == "Approved Leave"
    assert rec_leave["hr_action_required"] is False

    # Full Hours -> On Time / Full Hours
    rec_full = evaluate_employee_attendance(
        {
            "employee_id": "EMP-TEST-4",
            "employee_name": "Test Full",
            "department": "IT",
            "email": "full@company.co.ke",
            "attendance_date": "2026-10-20",
            "clock_in": "08:00",
            "clock_out": "16:30",
            "required_hours": 8.0,
            "leave_status": "None",
        }
    )
    assert rec_full["hours_worked"] == 8.5
    assert rec_full["hours_shortfall"] == 0.0
    assert rec_full["status_badge"] == "On Time / Full Hours"
    assert rec_full["hr_action_required"] is False


def test_list_and_update_attendance_endpoint() -> None:
    res = client.get("/api/attendance")
    assert res.status_code == 200
    data = res.json()
    summary = data["summary"]
    assert summary["total_employees_checked"] == 12
    assert summary["full_hours_completed"] == 4
    assert summary["covered_by_approved_leave"] == 3
    assert summary["flagged_for_hr_action"] == 5

    # Update EMP-1001 from Missed Hours (5.5h) to Approved Annual Leave
    upd = client.post(
        "/api/attendance/EMP-1001/update",
        json={
            "clock_in": "",
            "clock_out": "",
            "leave_status": "Approved Annual Leave",
            "required_hours": 8.0,
        },
    )
    assert upd.status_code == 200
    upd_data = upd.json()
    assert upd_data["employee"]["status_badge"] == "Approved Leave"
    assert upd_data["employee"]["hours_shortfall"] == 0.0
    assert upd_data["summary"]["covered_by_approved_leave"] == 4
    assert upd_data["summary"]["flagged_for_hr_action"] == 4


def test_single_and_bulk_hr_notifications() -> None:
    # Single notification for flagged employee EMP-1001 (Kevin Otieno - 2.5h shortfall)
    res_single = client.post(
        "/api/attendance/EMP-1001/notify",
        json={"sent_by": "Sarah Wambui (HR Operations Manager)"},
    )
    assert res_single.status_code == 200
    single_data = res_single.json()
    assert single_data["ok"] is True
    assert single_data["employee"]["notification_sent"] is True
    assert single_data["notification"]["hours_shortfall"] == 2.5
    assert single_data["summary"]["hr_notifications_sent"] == 2

    # Attempting to notify an employee who worked full hours (EMP-1006) should return 400
    res_compliant = client.post(
        "/api/attendance/EMP-1006/notify",
        json={"sent_by": "Sarah Wambui"},
    )
    assert res_compliant.status_code == 400

    # Bulk notification for remaining unnotified flagged employees
    res_bulk = client.post(
        "/api/attendance/notify-all",
        json={"sent_by": "Sarah Wambui (HR Operations Manager)"},
    )
    assert res_bulk.status_code == 200
    bulk_data = res_bulk.json()
    assert bulk_data["ok"] is True
    assert bulk_data["notified_count"] == 3
    assert bulk_data["summary"]["hr_notifications_sent"] == 5
    assert bulk_data["summary"]["pending_hr_notifications"] == 0


def test_sso_and_otp_endpoints() -> None:
    # 1. Instant demo sign-in
    res_demo = client.post("/api/auth/demo")
    assert res_demo.status_code == 200
    assert res_demo.json()["user"]["role"] == "HR Operations Manager"

    # 2. Consumer domain rejection on OTP
    res_gmail = client.post(
        "/api/auth/otp/request", json={"email": "randomuser@gmail.com"}
    )
    assert res_gmail.status_code == 403

    # 3. Valid corporate email OTP request & verification
    corp_email = "hr.lead@company.co.ke"
    res_req = client.post("/api/auth/otp/request", json={"email": corp_email})
    assert res_req.status_code == 200
    assert corp_email in _OTP_STORE
    raw_code = _OTP_STORE[corp_email]["raw_code"]

    res_ver = client.post(
        "/api/auth/otp/verify", json={"email": corp_email, "code": raw_code}
    )
    assert res_ver.status_code == 200
    ver_data = res_ver.json()
    assert ver_data["ok"] is True
    assert ver_data["user"]["email"] == corp_email
    assert ver_data["user"]["role"] == "HR Operations Manager"

    # 4. Invalid Google credential returns 401
    res_google = client.post(
        "/api/auth/google", json={"credential": "invalid-jwt-token"}
    )
    assert res_google.status_code == 401


def test_ask_attendance_agent_endpoint() -> None:
    res = client.post(
        "/api/agent/ask",
        json={
            "question": "Which employees missed hours today with no leave?",
            "employee_id": "EMP-1001",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert "Kevin Otieno" in data["answer"]
    assert "2.5" in data["answer"]


def test_zero_occurrences_of_forbidden_word() -> None:
    forbidden = "co" + "pilot"
    root = Path(__file__).resolve().parent.parent
    checked_files = 0
    for path in root.rglob("*"):
        if any(
            part in ("node_modules", ".git", "__pycache__", ".pytest_cache", "dist")
            for part in path.parts
        ):
            continue
        if path.is_file() and path.suffix in (
            ".py",
            ".jsx",
            ".js",
            ".html",
            ".css",
            ".md",
            ".json",
        ):
            content = path.read_text(encoding="utf-8", errors="ignore").lower()
            assert (
                forbidden not in content
            ), f"Forbidden term found in {path}"
            checked_files += 1
    assert checked_files >= 8
