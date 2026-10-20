"""
seed_data.py - Deterministic Clock-In/Clock-Out Hours Calculation, Approved Leave Cross-Check,
and HR & Employee Notification Engine for Agent #06: Attendance Clock-In/Out & Leave Notification Agent.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

VALID_LEAVE_STATUSES = [
    "None",
    "Approved Annual Leave",
    "Approved Sick Leave",
    "Approved Half-Day Leave",
    "Pending",
]


def parse_time_to_minutes(time_str: Optional[str]) -> Optional[int]:
    """Converts a 24-hour 'HH:MM' timestamp into minutes since midnight."""
    if not time_str or not isinstance(time_str, str):
        return None
    cleaned = time_str.strip()
    if not cleaned or cleaned in ("—", "-", "None", "N/A"):
        return None
    parts = cleaned.split(":")
    if len(parts) < 2:
        return None
    try:
        hours = int(parts[0])
        minutes = int(parts[1])
        if 0 <= hours <= 23 and 0 <= minutes <= 59:
            return hours * 60 + minutes
    except ValueError:
        return None
    return None


def calculate_hours_worked(clock_in: Optional[str], clock_out: Optional[str]) -> float:
    """Deterministically calculates hours worked between Clock-In and Clock-Out."""
    in_min = parse_time_to_minutes(clock_in)
    out_min = parse_time_to_minutes(clock_out)
    if in_min is None or out_min is None or out_min <= in_min:
        return 0.0
    return round((out_min - in_min) / 60.0, 2)


def get_approved_leave_hours(leave_status: str, required_hours: float = 8.0) -> float:
    """Returns the number of required daily shift hours covered by an approved leave application."""
    status = (leave_status or "None").strip()
    if status in ("Approved Annual Leave", "Approved Sick Leave"):
        return round(float(required_hours), 2)
    if status == "Approved Half-Day Leave":
        return round(float(required_hours) / 2.0, 2)
    # 'None' and 'Pending' do not provide approved leave coverage
    return 0.0


def evaluate_employee_attendance(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Runs the 3-step deterministic attendance & leave evaluation for an employee record:
      Step 1: Calculate hours worked from Clock-In and Clock-Out against Required Hours (8.0h)
      Step 2: Cross-check Leave Application Status for approved full-day or half-day coverage
      Step 3: Determine Hours Shortfall, Status Badge, and HR Notification message
    """
    required_hours = round(float(record.get("required_hours", 8.0) or 8.0), 2)
    clock_in = (record.get("clock_in") or "").strip()
    clock_out = (record.get("clock_out") or "").strip()
    leave_status = (record.get("leave_status") or "None").strip()
    if leave_status not in VALID_LEAVE_STATUSES:
        leave_status = "None"

    hours_worked = calculate_hours_worked(clock_in, clock_out)
    approved_leave_hours = get_approved_leave_hours(leave_status, required_hours)
    effective_required = max(0.0, round(required_hours - approved_leave_hours, 2))
    hours_shortfall = max(0.0, round(effective_required - hours_worked, 2))

    if hours_shortfall == 0.0:
        if approved_leave_hours > 0.0:
            status_badge = "Approved Leave"
            hr_action_required = False
            if leave_status == "Approved Half-Day Leave":
                plain_english_finding = (
                    f"{record['employee_name']} worked {hours_worked:.2f} hrs ({clock_in}–{clock_out}) "
                    f"and holds an Approved Half-Day Leave ({approved_leave_hours:.1f} hrs covered). "
                    f"Full daily requirement of {required_hours:.1f} hrs is satisfied."
                )
            else:
                plain_english_finding = (
                    f"{record['employee_name']} is on {leave_status} ({record.get('leave_reference') or 'Approved in HR System'}). "
                    f"All {required_hours:.1f} required hours are covered — no HR action needed."
                )
        else:
            status_badge = "On Time / Full Hours"
            hr_action_required = False
            plain_english_finding = (
                f"{record['employee_name']} clocked in at {clock_in} and clocked out at {clock_out}, "
                f"completing {hours_worked:.2f} hrs against the {required_hours:.1f}-hour shift requirement."
            )
    else:
        hr_action_required = True
        if hours_worked == 0.0 and approved_leave_hours == 0.0:
            status_badge = "Absent — No Leave"
            leave_note = (
                "An unapproved leave request is still marked Pending."
                if leave_status == "Pending"
                else "No leave application was found in the HR system."
            )
            plain_english_finding = (
                f"{record['employee_name']} has no Clock-In or Clock-Out record on {record['attendance_date']} "
                f"(0.0 hrs worked vs. {required_hours:.1f} hrs required). {leave_note} "
                f"Full shortfall of {hours_shortfall:.2f} hrs flagged for immediate HR notification."
            )
        else:
            status_badge = "Missed Hours — No Leave"
            leave_note = (
                "Leave status is Pending (not approved)."
                if leave_status == "Pending"
                else (
                    "Half-day leave covered 4.0 hrs, but remaining shift hours were not completed."
                    if leave_status == "Approved Half-Day Leave"
                    else "No leave application was submitted."
                )
            )
            clock_desc = (
                f"clocked in at {clock_in} and clocked out at {clock_out}"
                if clock_in and clock_out
                else "had an incomplete clock log"
            )
            plain_english_finding = (
                f"{record['employee_name']} {clock_desc}, completing {hours_worked:.2f} hrs "
                f"against {effective_required:.1f} required shift hours (shortfall of {hours_shortfall:.2f} hrs). "
                f"{leave_note}"
            )

    # Build clear plain-English notification preview for HR and the employee
    clock_in_display = clock_in if clock_in else "No Clock-In"
    clock_out_display = clock_out if clock_out else "No Clock-Out"

    if hr_action_required:
        notification_subject = (
            f"HR Attendance Notice: {record['employee_name']} ({record['department']}) — "
            f"{status_badge} ({hours_shortfall:.2f}h Shortfall on {record['attendance_date']})"
        )
        notification_body = (
            f"To: HR Operations ({record.get('hr_partner_email', 'hr.operations@company.co.ke')}), "
            f"{record['employee_name']} ({record['email']})\n"
            f"Cc: {record.get('line_manager', 'Department Manager')} (Line Manager)\n\n"
            f"Daily Attendance & Leave Check Summary ({record['attendance_date']}):\n"
            f"• Employee: {record['employee_name']} ({record['employee_id']}) — {record['department']}\n"
            f"• Clock-In / Clock-Out: {clock_in_display} to {clock_out_display}\n"
            f"• Hours Worked vs. Required: {hours_worked:.2f} hrs worked of {required_hours:.1f} hrs required\n"
            f"• Leave Application Status: {leave_status}\n"
            f"• Unexplained Hours Shortfall: {hours_shortfall:.2f} hrs ({status_badge})\n\n"
            f"Required Action:\n"
            f"Please submit an approved leave application or confirm attendance regularization with HR Operations "
            f"and your line manager before payroll cut-off."
        )
    else:
        notification_subject = (
            f"Attendance Verified: {record['employee_name']} ({record['attendance_date']}) — {status_badge}"
        )
        notification_body = (
            f"{record['employee_name']} has no attendance shortfall on {record['attendance_date']} "
            f"({hours_worked:.2f} hrs worked, Leave Status: {leave_status}). No HR notification required."
        )

    record["clock_in"] = clock_in
    record["clock_out"] = clock_out
    record["required_hours"] = required_hours
    record["hours_worked"] = hours_worked
    record["leave_status"] = leave_status
    record["approved_leave_hours"] = approved_leave_hours
    record["hours_shortfall"] = hours_shortfall
    record["status_badge"] = status_badge
    record["hr_action_required"] = hr_action_required
    record["plain_english_finding"] = plain_english_finding
    record["notification_subject"] = notification_subject
    record["notification_body"] = notification_body
    return record


def build_initial_employees() -> List[Dict[str, Any]]:
    """Builds the realistic daily employee attendance & leave records."""
    raw_records: List[Dict[str, Any]] = [
        {
            "employee_id": "EMP-1001",
            "employee_name": "Kevin Otieno",
            "role_title": "Regional Account Executive",
            "department": "Sales & Distribution",
            "email": "kevin.otieno@company.co.ke",
            "line_manager": "peter.ndungu@company.co.ke",
            "hr_partner_email": "hr.operations@company.co.ke",
            "attendance_date": "2026-10-20",
            "clock_in": "09:45",
            "clock_out": "15:15",
            "required_hours": 8.0,
            "leave_status": "None",
            "leave_reference": "—",
            "notification_sent": False,
            "notification_sent_at": None,
            "notification_sent_by": None,
            "notification_ref": None,
        },
        {
            "employee_id": "EMP-1002",
            "employee_name": "Brenda Njoroge",
            "role_title": "Client Support Specialist",
            "department": "Customer Operations",
            "email": "brenda.njoroge@company.co.ke",
            "line_manager": "david.kimani@company.co.ke",
            "hr_partner_email": "hr.operations@company.co.ke",
            "attendance_date": "2026-10-20",
            "clock_in": "",
            "clock_out": "",
            "required_hours": 8.0,
            "leave_status": "None",
            "leave_reference": "—",
            "notification_sent": False,
            "notification_sent_at": None,
            "notification_sent_by": None,
            "notification_ref": None,
        },
        {
            "employee_id": "EMP-1003",
            "employee_name": "Brian Mutua",
            "role_title": "Logistics & Dispatch Coordinator",
            "department": "Supply Chain & Warehouse",
            "email": "brian.mutua@company.co.ke",
            "line_manager": "james.karanja@company.co.ke",
            "hr_partner_email": "hr.operations@company.co.ke",
            "attendance_date": "2026-10-20",
            "clock_in": "10:30",
            "clock_out": "15:00",
            "required_hours": 8.0,
            "leave_status": "Pending",
            "leave_reference": "LV-REQ-882 (Unapproved)",
            "notification_sent": False,
            "notification_sent_at": None,
            "notification_sent_by": None,
            "notification_ref": None,
        },
        {
            "employee_id": "EMP-1004",
            "employee_name": "Mercy Chebet",
            "role_title": "Accounts Payable Officer",
            "department": "Finance & Payroll",
            "email": "mercy.chebet@company.co.ke",
            "line_manager": "anne.githuku@company.co.ke",
            "hr_partner_email": "hr.operations@company.co.ke",
            "attendance_date": "2026-10-20",
            "clock_in": "08:30",
            "clock_out": "13:30",
            "required_hours": 8.0,
            "leave_status": "None",
            "leave_reference": "—",
            "notification_sent": False,
            "notification_sent_at": None,
            "notification_sent_by": None,
            "notification_ref": None,
        },
        {
            "employee_id": "EMP-1005",
            "employee_name": "Daniel Kiprop",
            "role_title": "Systems & Network Administrator",
            "department": "Information Technology",
            "email": "daniel.kiprop@company.co.ke",
            "line_manager": "martin.omondi@company.co.ke",
            "hr_partner_email": "hr.operations@company.co.ke",
            "attendance_date": "2026-10-20",
            "clock_in": "",
            "clock_out": "",
            "required_hours": 8.0,
            "leave_status": "Pending",
            "leave_reference": "LV-REQ-889 (Unapproved)",
            "notification_sent": True,
            "notification_sent_at": "2026-10-20 09:15 EAT",
            "notification_sent_by": "Sarah Wambui (HR Operations Manager)",
            "notification_ref": "HR-ATT-2026-001",
        },
        {
            "employee_id": "EMP-1006",
            "employee_name": "Grace Wanjiku",
            "role_title": "Senior Payroll Specialist",
            "department": "Finance & Payroll",
            "email": "grace.wanjiku@company.co.ke",
            "line_manager": "anne.githuku@company.co.ke",
            "hr_partner_email": "hr.operations@company.co.ke",
            "attendance_date": "2026-10-20",
            "clock_in": "08:15",
            "clock_out": "16:45",
            "required_hours": 8.0,
            "leave_status": "None",
            "leave_reference": "—",
            "notification_sent": False,
            "notification_sent_at": None,
            "notification_sent_by": None,
            "notification_ref": None,
        },
        {
            "employee_id": "EMP-1007",
            "employee_name": "Samuel Kamau",
            "role_title": "Senior Software Engineer",
            "department": "Information Technology",
            "email": "samuel.kamau@company.co.ke",
            "line_manager": "martin.omondi@company.co.ke",
            "hr_partner_email": "hr.operations@company.co.ke",
            "attendance_date": "2026-10-20",
            "clock_in": "08:30",
            "clock_out": "16:30",
            "required_hours": 8.0,
            "leave_status": "None",
            "leave_reference": "—",
            "notification_sent": False,
            "notification_sent_at": None,
            "notification_sent_by": None,
            "notification_ref": None,
        },
        {
            "employee_id": "EMP-1008",
            "employee_name": "Faith Achieng",
            "role_title": "Talent Acquisition Partner",
            "department": "People & Culture",
            "email": "faith.achieng@company.co.ke",
            "line_manager": "sarah.wambui@company.co.ke",
            "hr_partner_email": "hr.operations@company.co.ke",
            "attendance_date": "2026-10-20",
            "clock_in": "",
            "clock_out": "",
            "required_hours": 8.0,
            "leave_status": "Approved Annual Leave",
            "leave_reference": "LV-2026-441",
            "notification_sent": False,
            "notification_sent_at": None,
            "notification_sent_by": None,
            "notification_ref": None,
        },
        {
            "employee_id": "EMP-1009",
            "employee_name": "Peter Mwangi",
            "role_title": "Inventory Control Supervisor",
            "department": "Supply Chain & Warehouse",
            "email": "peter.mwangi@company.co.ke",
            "line_manager": "james.karanja@company.co.ke",
            "hr_partner_email": "hr.operations@company.co.ke",
            "attendance_date": "2026-10-20",
            "clock_in": "",
            "clock_out": "",
            "required_hours": 8.0,
            "leave_status": "Approved Sick Leave",
            "leave_reference": "LV-2026-448",
            "notification_sent": False,
            "notification_sent_at": None,
            "notification_sent_by": None,
            "notification_ref": None,
        },
        {
            "employee_id": "EMP-1010",
            "employee_name": "Esther Nyambura",
            "role_title": "Customer Experience Team Lead",
            "department": "Customer Operations",
            "email": "esther.nyambura@company.co.ke",
            "line_manager": "david.kimani@company.co.ke",
            "hr_partner_email": "hr.operations@company.co.ke",
            "attendance_date": "2026-10-20",
            "clock_in": "08:30",
            "clock_out": "12:45",
            "required_hours": 8.0,
            "leave_status": "Approved Half-Day Leave",
            "leave_reference": "LV-2026-452",
            "notification_sent": False,
            "notification_sent_at": None,
            "notification_sent_by": None,
            "notification_ref": None,
        },
        {
            "employee_id": "EMP-1011",
            "employee_name": "Christine Moraa",
            "role_title": "Key Account Manager",
            "department": "Sales & Distribution",
            "email": "christine.moraa@company.co.ke",
            "line_manager": "peter.ndungu@company.co.ke",
            "hr_partner_email": "hr.operations@company.co.ke",
            "attendance_date": "2026-10-20",
            "clock_in": "08:00",
            "clock_out": "16:15",
            "required_hours": 8.0,
            "leave_status": "None",
            "leave_reference": "—",
            "notification_sent": False,
            "notification_sent_at": None,
            "notification_sent_by": None,
            "notification_ref": None,
        },
        {
            "employee_id": "EMP-1012",
            "employee_name": "Victor Odhiambo",
            "role_title": "People Operations Coordinator",
            "department": "People & Culture",
            "email": "victor.odhiambo@company.co.ke",
            "line_manager": "sarah.wambui@company.co.ke",
            "hr_partner_email": "hr.operations@company.co.ke",
            "attendance_date": "2026-10-20",
            "clock_in": "08:20",
            "clock_out": "16:35",
            "required_hours": 8.0,
            "leave_status": "None",
            "leave_reference": "—",
            "notification_sent": False,
            "notification_sent_at": None,
            "notification_sent_by": None,
            "notification_ref": None,
        },
    ]
    return [evaluate_employee_attendance(rec) for rec in raw_records]
