"""
FastAPI Backend for Agent #06: Attendance Clock-In/Out & Leave Notification Agent.
Checks daily employee clock-in and clock-out logs against required shift hours (8.0h),
cross-checks approved leave applications, flags each employee who missed hours or was
absent with no approved leave, and dispatches one-click notifications to HR and the employee.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from auth_service import (
    GOOGLE_CLIENT_ID,
    format_name_from_email,
    generate_and_store_otp,
    get_otp_rejection_message,
    is_access_allowed,
    send_otp_email,
    verify_google_id_token,
    verify_stored_otp,
)
from seed_data import (
    VALID_LEAVE_STATUSES,
    build_initial_employees,
    evaluate_employee_attendance,
)

app = FastAPI(
    title="Attendance Clock-In/Out & Leave Notification Agent (#06)",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

EMPLOYEE_STORE: List[Dict[str, Any]] = build_initial_employees()
NOTIFICATION_LOG: List[Dict[str, Any]] = [
    {
        "notification_ref": "HR-ATT-2026-001",
        "employee_id": "EMP-1005",
        "employee_name": "Daniel Kiprop",
        "department": "Information Technology",
        "attendance_date": "2026-10-20",
        "status_badge": "Absent — No Leave",
        "hours_shortfall": 8.0,
        "sent_at": "2026-10-20 09:15 EAT",
        "sent_by": "Sarah Wambui (HR Operations Manager)",
        "recipients": "hr.operations@company.co.ke, daniel.kiprop@company.co.ke, martin.omondi@company.co.ke",
        "subject": "HR Attendance Notice: Daniel Kiprop (Information Technology) — Absent — No Leave (8.00h Shortfall on 2026-10-20)",
    }
]


class OTPRequestPayload(BaseModel):
    email: str


class OTPVerifyPayload(BaseModel):
    email: str
    code: str


class GoogleAuthPayload(BaseModel):
    credential: str


class UpdateAttendancePayload(BaseModel):
    clock_in: Optional[str] = ""
    clock_out: Optional[str] = ""
    leave_status: str = "None"
    required_hours: Optional[float] = 8.0


class SimulateAttendancePayload(BaseModel):
    employee_id: str
    clock_in: Optional[str] = ""
    clock_out: Optional[str] = ""
    leave_status: str = "None"
    required_hours: Optional[float] = 8.0


class NotifyPayload(BaseModel):
    sent_by: Optional[str] = "Sarah Wambui (HR Operations Manager)"
    custom_note: Optional[str] = None


class AgentAskPayload(BaseModel):
    question: str
    employee_id: Optional[str] = None


def compute_summary() -> Dict[str, Any]:
    total_employees = len(EMPLOYEE_STORE)
    full_hours_completed = sum(
        1 for e in EMPLOYEE_STORE if e["status_badge"] == "On Time / Full Hours"
    )
    covered_by_approved_leave = sum(
        1 for e in EMPLOYEE_STORE if e["status_badge"] == "Approved Leave"
    )
    missed_hours_no_leave = sum(
        1 for e in EMPLOYEE_STORE if e["status_badge"] == "Missed Hours — No Leave"
    )
    absent_no_leave = sum(
        1 for e in EMPLOYEE_STORE if e["status_badge"] == "Absent — No Leave"
    )
    flagged_for_hr_action = sum(
        1 for e in EMPLOYEE_STORE if e["hr_action_required"]
    )
    hr_notifications_sent = sum(
        1 for e in EMPLOYEE_STORE if e.get("notification_sent")
    )
    pending_hr_notifications = sum(
        1
        for e in EMPLOYEE_STORE
        if e["hr_action_required"] and not e.get("notification_sent")
    )
    total_shortfall_hours = round(
        sum(e["hours_shortfall"] for e in EMPLOYEE_STORE if e["hr_action_required"]),
        2,
    )

    return {
        "attendance_date": "2026-10-20",
        "total_employees_checked": total_employees,
        "full_hours_completed": full_hours_completed,
        "covered_by_approved_leave": covered_by_approved_leave,
        "flagged_for_hr_action": flagged_for_hr_action,
        "missed_hours_no_leave_count": missed_hours_no_leave,
        "absent_no_leave_count": absent_no_leave,
        "hr_notifications_sent": hr_notifications_sent,
        "pending_hr_notifications": pending_hr_notifications,
        "total_shortfall_hours": total_shortfall_hours,
    }


@app.get("/api/health")
def health_check() -> Dict[str, Any]:
    return {
        "status": "ok",
        "agent_id": "06",
        "service": "HR_AttendanceLeaveAgent",
        "title": "Attendance Clock-In/Out & Leave Notification Agent",
        "google_client_id": GOOGLE_CLIENT_ID,
        "employees_loaded": len(EMPLOYEE_STORE),
    }


@app.post("/api/auth/otp/request")
def request_otp(payload: OTPRequestPayload) -> Dict[str, Any]:
    email = (payload.email or "").strip().lower()
    if not email or "@" not in email:
        raise HTTPException(
            status_code=400, detail="Please enter a valid work email address."
        )
    if not is_access_allowed(email):
        raise HTTPException(status_code=403, detail=get_otp_rejection_message(email))
    code = generate_and_store_otp(email)
    try:
        send_otp_email(email, code)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send verification code: {str(exc)}",
        ) from exc
    return {
        "ok": True,
        "message": f"6-digit verification code sent to {email}.",
        "email": email,
    }


@app.post("/api/auth/otp/verify")
def verify_otp(payload: OTPVerifyPayload) -> Dict[str, Any]:
    email = (payload.email or "").strip().lower()
    code = (payload.code or "").strip()
    ok, message = verify_stored_otp(email, code)
    if not ok:
        raise HTTPException(status_code=401, detail=message)
    return {
        "ok": True,
        "user": {
            "email": email,
            "name": format_name_from_email(email),
            "role": "HR Operations Manager",
            "auth_method": "otp",
        },
    }


@app.post("/api/auth/google")
def google_auth(payload: GoogleAuthPayload) -> Dict[str, Any]:
    ok, user_info, message = verify_google_id_token(payload.credential)
    if not ok:
        raise HTTPException(status_code=401, detail=message)
    return {
        "ok": True,
        "user": {
            "email": user_info.get("email"),
            "name": user_info.get("name"),
            "picture": user_info.get("picture"),
            "role": "HR Operations Manager",
            "auth_method": "google",
        },
    }


@app.post("/api/auth/demo")
def demo_auth() -> Dict[str, Any]:
    return {
        "ok": True,
        "user": {
            "email": "sarah.wambui@company.co.ke",
            "name": "Sarah Wambui",
            "role": "HR Operations Manager",
            "auth_method": "demo",
        },
    }


@app.get("/api/attendance")
def list_attendance() -> Dict[str, Any]:
    return {
        "summary": compute_summary(),
        "employees": EMPLOYEE_STORE,
        "notifications_log": NOTIFICATION_LOG,
        "leave_status_options": VALID_LEAVE_STATUSES,
    }


@app.get("/api/attendance/{employee_id}")
def get_employee_attendance(employee_id: str) -> Dict[str, Any]:
    for emp in EMPLOYEE_STORE:
        if emp["employee_id"] == employee_id:
            return {
                "employee": emp,
                "summary": compute_summary(),
            }
    raise HTTPException(
        status_code=404, detail=f"Employee {employee_id} not found."
    )


def _apply_employee_update(
    emp: Dict[str, Any],
    clock_in: Optional[str],
    clock_out: Optional[str],
    leave_status: str,
    required_hours: Optional[float],
) -> Dict[str, Any]:
    emp["clock_in"] = (clock_in or "").strip()
    emp["clock_out"] = (clock_out or "").strip()
    emp["leave_status"] = (leave_status or "None").strip()
    if required_hours is not None and float(required_hours) > 0:
        emp["required_hours"] = round(float(required_hours), 2)

    evaluate_employee_attendance(emp)

    # If the updated record no longer requires HR action, clear any pending notification flag
    if not emp["hr_action_required"]:
        emp["notification_sent"] = False
        emp["notification_sent_at"] = None
        emp["notification_sent_by"] = None
        emp["notification_ref"] = None

    return emp


@app.post("/api/attendance/{employee_id}/update")
def update_employee_attendance(
    employee_id: str, payload: UpdateAttendancePayload
) -> Dict[str, Any]:
    for emp in EMPLOYEE_STORE:
        if emp["employee_id"] == employee_id:
            _apply_employee_update(
                emp,
                payload.clock_in,
                payload.clock_out,
                payload.leave_status,
                payload.required_hours,
            )
            return {
                "ok": True,
                "message": (
                    f"Updated attendance & leave check for {emp['employee_name']}: "
                    f"{emp['hours_worked']:.2f}h worked vs {emp['required_hours']:.1f}h required "
                    f"({emp['status_badge']})."
                ),
                "employee": emp,
                "summary": compute_summary(),
            }
    raise HTTPException(
        status_code=404, detail=f"Employee {employee_id} not found."
    )


@app.post("/api/attendance/simulate")
def simulate_employee_attendance(payload: SimulateAttendancePayload) -> Dict[str, Any]:
    for emp in EMPLOYEE_STORE:
        if emp["employee_id"] == payload.employee_id:
            _apply_employee_update(
                emp,
                payload.clock_in,
                payload.clock_out,
                payload.leave_status,
                payload.required_hours,
            )
            return {
                "ok": True,
                "message": (
                    f"Recalculated attendance & leave check for {emp['employee_name']}: "
                    f"{emp['hours_worked']:.2f}h worked, shortfall {emp['hours_shortfall']:.2f}h "
                    f"({emp['status_badge']})."
                ),
                "employee": emp,
                "summary": compute_summary(),
            }
    raise HTTPException(
        status_code=404, detail=f"Employee {payload.employee_id} not found."
    )


def _dispatch_notification_for_employee(
    emp: Dict[str, Any], sent_by: str, custom_note: Optional[str] = None
) -> Dict[str, Any]:
    evaluate_employee_attendance(emp)
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    ref_num = len(NOTIFICATION_LOG) + 1
    notification_ref = f"HR-ATT-2026-{ref_num:03d}"

    emp["notification_sent"] = True
    emp["notification_sent_at"] = now_str
    emp["notification_sent_by"] = sent_by
    emp["notification_ref"] = notification_ref

    body_text = emp["notification_body"]
    if custom_note and custom_note.strip():
        body_text = f"{body_text}\n\nHR Note: {custom_note.strip()}"

    receipt = {
        "notification_ref": notification_ref,
        "employee_id": emp["employee_id"],
        "employee_name": emp["employee_name"],
        "department": emp["department"],
        "attendance_date": emp["attendance_date"],
        "status_badge": emp["status_badge"],
        "hours_shortfall": emp["hours_shortfall"],
        "sent_at": now_str,
        "sent_by": sent_by,
        "recipients": f"{emp['hr_partner_email']}, {emp['email']}, {emp['line_manager']}",
        "subject": emp["notification_subject"],
        "body": body_text,
    }
    NOTIFICATION_LOG.insert(0, receipt)
    return receipt


@app.post("/api/attendance/{employee_id}/notify")
def notify_single_employee(
    employee_id: str, payload: Optional[NotifyPayload] = None
) -> Dict[str, Any]:
    sent_by = (
        payload.sent_by
        if payload and payload.sent_by
        else "Sarah Wambui (HR Operations Manager)"
    )
    custom_note = payload.custom_note if payload else None

    for emp in EMPLOYEE_STORE:
        if emp["employee_id"] == employee_id:
            evaluate_employee_attendance(emp)
            if not emp["hr_action_required"]:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"{emp['employee_name']} has no attendance shortfall "
                        f"({emp['status_badge']}). HR notification is only required for employees who missed hours or were absent without approved leave."
                    ),
                )
            receipt = _dispatch_notification_for_employee(emp, sent_by, custom_note)
            return {
                "ok": True,
                "message": (
                    f"Notification {receipt['notification_ref']} sent to HR ({emp['hr_partner_email']}) "
                    f"and {emp['employee_name']} ({emp['email']}) for {emp['hours_shortfall']:.2f}h shortfall."
                ),
                "notification": receipt,
                "employee": emp,
                "summary": compute_summary(),
                "notifications_log": NOTIFICATION_LOG,
            }
    raise HTTPException(
        status_code=404, detail=f"Employee {employee_id} not found."
    )


@app.post("/api/attendance/notify-all")
def notify_all_flagged_employees(
    payload: Optional[NotifyPayload] = None,
) -> Dict[str, Any]:
    sent_by = (
        payload.sent_by
        if payload and payload.sent_by
        else "Sarah Wambui (HR Operations Manager)"
    )
    custom_note = payload.custom_note if payload else None

    notified_receipts: List[Dict[str, Any]] = []
    # First notify all flagged employees who haven't been notified yet;
    # if all flagged employees were already notified, re-notify all flagged employees so the button always gives clear feedback.
    unnotified_flagged = [
        emp
        for emp in EMPLOYEE_STORE
        if emp["hr_action_required"] and not emp.get("notification_sent")
    ]
    targets = (
        unnotified_flagged
        if unnotified_flagged
        else [emp for emp in EMPLOYEE_STORE if emp["hr_action_required"]]
    )

    for emp in targets:
        receipt = _dispatch_notification_for_employee(emp, sent_by, custom_note)
        notified_receipts.append(receipt)

    names_str = ", ".join(r["employee_name"] for r in notified_receipts)
    return {
        "ok": True,
        "notified_count": len(notified_receipts),
        "message": (
            f"Sent HR & Employee attendance shortfall notifications for {len(notified_receipts)} "
            f"flagged employee(s): {names_str}."
            if notified_receipts
            else "No employees currently have missed hours or unapproved absences."
        ),
        "notifications": notified_receipts,
        "employees": EMPLOYEE_STORE,
        "summary": compute_summary(),
        "notifications_log": NOTIFICATION_LOG,
    }


@app.post("/api/attendance/reset")
def reset_attendance_demo() -> Dict[str, Any]:
    global EMPLOYEE_STORE, NOTIFICATION_LOG
    EMPLOYEE_STORE = build_initial_employees()
    NOTIFICATION_LOG = [
        {
            "notification_ref": "HR-ATT-2026-001",
            "employee_id": "EMP-1005",
            "employee_name": "Daniel Kiprop",
            "department": "Information Technology",
            "attendance_date": "2026-10-20",
            "status_badge": "Absent — No Leave",
            "hours_shortfall": 8.0,
            "sent_at": "2026-10-20 09:15 EAT",
            "sent_by": "Sarah Wambui (HR Operations Manager)",
            "recipients": "hr.operations@company.co.ke, daniel.kiprop@company.co.ke, martin.omondi@company.co.ke",
            "subject": "HR Attendance Notice: Daniel Kiprop (Information Technology) — Absent — No Leave (8.00h Shortfall on 2026-10-20)",
        }
    ]
    return {
        "ok": True,
        "message": "Daily attendance & leave records reset to initial demo state.",
        "summary": compute_summary(),
        "employees": EMPLOYEE_STORE,
        "notifications_log": NOTIFICATION_LOG,
    }


def build_deterministic_agent_reply(
    question: str, selected_emp: Optional[Dict[str, Any]] = None
) -> str:
    summary = compute_summary()
    flagged = [e for e in EMPLOYEE_STORE if e["hr_action_required"]]
    approved_leave = [
        e for e in EMPLOYEE_STORE if e["status_badge"] == "Approved Leave"
    ]

    if selected_emp:
        emp = selected_emp
        return (
            f"### Attendance & Leave Agent Summary — {emp['employee_name']} ({emp['department']})\n\n"
            f"- **Date Checked**: {emp['attendance_date']}\n"
            f"- **Clock-In / Clock-Out**: {emp['clock_in'] or 'No Clock-In'} to {emp['clock_out'] or 'No Clock-Out'}\n"
            f"- **Hours Worked vs. Required**: **{emp['hours_worked']:.2f} hrs** worked against **{emp['required_hours']:.1f} hrs** required\n"
            f"- **Leave Application Status**: **{emp['leave_status']}** ({emp.get('leave_reference', '—')})\n"
            f"- **Hours Shortfall**: **{emp['hours_shortfall']:.2f} hrs**\n"
            f"- **Status**: **{emp['status_badge']}**\n"
            f"- **Agent Assessment**: {emp['plain_english_finding']}"
        )

    flagged_lines = "\n".join(
        f"- **{e['employee_name']}** ({e['department']}): Clock-In `{e['clock_in'] or '—'}` / Clock-Out `{e['clock_out'] or '—'}` "
        f"• **{e['hours_worked']:.2f}h** worked vs **{e['required_hours']:.1f}h** required "
        f"• Leave: **{e['leave_status']}** • Shortfall: **{e['hours_shortfall']:.2f}h** (**{e['status_badge']}**)"
        for e in flagged
    )
    leave_lines = "\n".join(
        f"- **{e['employee_name']}** ({e['department']}): **{e['leave_status']}** ({e.get('leave_reference', 'Approved')})"
        for e in approved_leave
    )

    return (
        f"### Daily Attendance & Leave Check Summary ({summary['attendance_date']})\n\n"
        f"- **Total Employees Checked**: {summary['total_employees_checked']}\n"
        f"- **Full Hours Completed (8.0h+)**: {summary['full_hours_completed']}\n"
        f"- **Covered by Approved Leave**: {summary['covered_by_approved_leave']}\n"
        f"- **Missed Hours / Absent with No Leave (HR Action Required)**: **{summary['flagged_for_hr_action']} employees** "
        f"({summary['total_shortfall_hours']:.2f} total hours shortfall)\n"
        f"- **HR Notifications Sent**: {summary['hr_notifications_sent']}\n\n"
        f"#### Employees Flagged for Missed Hours or Absence with No Approved Leave\n"
        f"{flagged_lines or '- None'}\n\n"
        f"#### Employees Covered by Approved Leave\n"
        f"{leave_lines or '- None'}"
    )


@app.post("/api/agent/ask")
def ask_attendance_agent(payload: AgentAskPayload) -> Dict[str, Any]:
    selected_emp = None
    if payload.employee_id:
        for emp in EMPLOYEE_STORE:
            if emp["employee_id"] == payload.employee_id:
                selected_emp = emp
                break

    fallback_reply = build_deterministic_agent_reply(payload.question, selected_emp)

    try:
        from google import genai

        use_vertex = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "1") == "1"
        project = os.getenv("GOOGLE_CLOUD_PROJECT", "gemini-enterprise-demo-498212")
        location = os.getenv("GOOGLE_CLOUD_LOCATION", "global")
        if use_vertex:
            client = genai.Client(vertexai=True, project=project, location=location)
        else:
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                return {"answer": fallback_reply, "model": "Enterprise People & Analytics Engine"}
            client = genai.Client(api_key=api_key)

        prompt = (
            "You are the Attendance & Leave Agent for HR Operations.\n"
            "Use plain, friendly business English with zero technical jargon.\n"
            "Always refer to yourself as the Attendance & Leave Agent.\n"
            f"Daily Summary: {compute_summary()}\n"
            f"Employee Records: {EMPLOYEE_STORE}\n"
            f"Selected Employee: {selected_emp}\n\n"
            f"HR Question: {payload.question}\n"
            "Provide a clear, concise answer highlighting employee names, clock-in/clock-out times, "
            "hours worked vs required (8.0h), leave status, hours shortfall, and recommended HR notification action."
        )
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        text = (response.text or "").strip()
        if text:
            return {"answer": text, "model": "Enterprise People & Analytics Engine"}
    except Exception:
        pass

    return {"answer": fallback_reply, "model": "Enterprise People & Analytics Engine"}


# Mount compiled React SPA if present
FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if FRONTEND_DIST.exists():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/{full_path:path}")
    def serve_spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="API route not found")
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.exists() and candidate.is_file():
            return FileResponse(str(candidate))
        return FileResponse(str(FRONTEND_DIST / "index.html"))
