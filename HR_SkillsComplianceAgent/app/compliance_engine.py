"""Deterministic Expiry Detection, Status Classification, Role Skills Matrix & Ask Certification Agent Engine."""

from datetime import date, datetime
from typing import Any, Dict, List, Optional

STATUS_EXPIRED = "Expired — Action Required"
STATUS_EXPIRING_30 = "Expiring in 30 Days"
STATUS_EXPIRING_60_90 = "Expiring in 60–90 Days"
STATUS_ACTIVE = "Active & Valid"


def parse_iso_date(date_str: str) -> date:
    """Parse a YYYY-MM-DD date string into a Python date object."""
    clean = (date_str or "").strip()[:10]
    return datetime.strptime(clean, "%Y-%m-%d").date()


def calculate_days_remaining(expiry_date_str: str, reference_date: Optional[date] = None) -> int:
    """Deterministically calculate days remaining until expiry from reference_date (defaults to today)."""
    ref = reference_date or date.today()
    exp = parse_iso_date(expiry_date_str)
    return (exp - ref).days


def classify_certification_status(days_remaining: int) -> str:
    """
    Classify a certificate into one of the four mandatory status badges:
    - 'Expired — Action Required' (days_remaining < 0)
    - 'Expiring in 30 Days' (0 <= days_remaining <= 30)
    - 'Expiring in 60–90 Days' (31 <= days_remaining <= 90)
    - 'Active & Valid' (days_remaining > 90)
    """
    if days_remaining < 0:
        return STATUS_EXPIRED
    if days_remaining <= 30:
        return STATUS_EXPIRING_30
    if days_remaining <= 90:
        return STATUS_EXPIRING_60_90
    return STATUS_ACTIVE


def format_days_remaining_label(days_remaining: int) -> str:
    """Format days remaining in plain business English."""
    if days_remaining < 0:
        overdue = abs(days_remaining)
        return f"{overdue} day{'s' if overdue != 1 else ''} overdue"
    if days_remaining == 0:
        return "Expires today"
    if days_remaining == 1:
        return "1 day left"
    return f"{days_remaining} days left"


def enrich_certification_record(
    row: Dict[str, Any], reference_date: Optional[date] = None
) -> Dict[str, Any]:
    """Attach deterministic days_remaining, status_badge, and urgency rank to a certification record."""
    days = calculate_days_remaining(row["expiry_date"], reference_date=reference_date)
    status = classify_certification_status(days)
    enriched = dict(row)
    enriched["days_remaining"] = days
    enriched["days_remaining_label"] = format_days_remaining_label(days)
    enriched["status_badge"] = status
    enriched["needs_renewal"] = days <= 90
    return enriched


def compute_kpi_summary(
    enriched_certs: List[Dict[str, Any]], reminders_sent_total: int
) -> Dict[str, Any]:
    """Compute top-level executive KPI cards in plain business metrics."""
    total_tracked = len(enriched_certs)
    expired_count = sum(1 for c in enriched_certs if c["status_badge"] == STATUS_EXPIRED)
    expiring_30_count = sum(1 for c in enriched_certs if c["status_badge"] == STATUS_EXPIRING_30)
    expiring_60_90_count = sum(
        1 for c in enriched_certs if c["status_badge"] == STATUS_EXPIRING_60_90
    )
    active_valid_count = sum(1 for c in enriched_certs if c["status_badge"] == STATUS_ACTIVE)
    # All non-expired credentials are currently valid; active_valid_count is >90 days
    valid_and_compliant = total_tracked - expired_count
    compliance_rate = (
        round((valid_and_compliant / total_tracked) * 100, 1) if total_tracked > 0 else 100.0
    )

    active_bonds_count = sum(1 for c in enriched_certs if (c.get("bond_amount_usd") or 0) > 0)
    total_bond_value = sum(float(c.get("bond_amount_usd") or 0) for c in enriched_certs)

    return {
        "total_tracked_certifications": total_tracked,
        "valid_and_compliant": valid_and_compliant,
        "active_and_valid_over_90_days": active_valid_count,
        "expiring_within_30_days": expiring_30_count,
        "expiring_60_to_90_days": expiring_60_90_count,
        "expired_immediate_renewal": expired_count,
        "reminders_sent": reminders_sent_total,
        "overall_compliance_rate_pct": compliance_rate,
        "active_training_bonds_count": active_bonds_count,
        "total_training_bond_value_usd": round(total_bond_value, 2),
    }


def build_department_skills_matrix(
    enriched_certs: List[Dict[str, Any]],
    role_requirements: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Build a simple Role Skills & Certification Matrix view showing required vs. completed
    certifications by department and role.
    """
    dept_map: Dict[str, Dict[str, Any]] = {}

    for req in role_requirements:
        dept = req["department"]
        if dept not in dept_map:
            dept_map[dept] = {
                "department": dept,
                "department_head": req.get("department_head", "Department Lead"),
                "required_count": 0,
                "completed_valid_count": 0,
                "expiring_soon_count": 0,
                "expired_gap_count": 0,
                "roles": [],
                "active_bond_total_usd": 0.0,
            }

    # Match each certification to its department
    for cert in enriched_certs:
        dept = cert["department"]
        if dept not in dept_map:
            dept_map[dept] = {
                "department": dept,
                "department_head": cert.get("manager_name", "Department Lead"),
                "required_count": 0,
                "completed_valid_count": 0,
                "expiring_soon_count": 0,
                "expired_gap_count": 0,
                "roles": [],
                "active_bond_total_usd": 0.0,
            }
        entry = dept_map[dept]
        entry["required_count"] += 1
        if cert["status_badge"] == STATUS_EXPIRED:
            entry["expired_gap_count"] += 1
        else:
            entry["completed_valid_count"] += 1
            if cert["status_badge"] in (STATUS_EXPIRING_30, STATUS_EXPIRING_60_90):
                entry["expiring_soon_count"] += 1

        entry["active_bond_total_usd"] = round(
            entry["active_bond_total_usd"] + float(cert.get("bond_amount_usd") or 0), 2
        )
        entry["roles"].append(
            {
                "cert_id": cert["id"],
                "employee_name": cert["employee_name"],
                "role_title": cert["role_title"],
                "certificate_name": cert["certificate_name"],
                "issuing_body": cert["issuing_body"],
                "mandatory_skill_area": cert.get("skill_category", "Mandatory Role License"),
                "expiry_date": cert["expiry_date"],
                "days_remaining": cert["days_remaining"],
                "days_remaining_label": cert["days_remaining_label"],
                "status_badge": cert["status_badge"],
                "is_compliant": cert["status_badge"] != STATUS_EXPIRED,
                "bond_amount_usd": float(cert.get("bond_amount_usd") or 0),
                "bond_end_date": cert.get("bond_end_date") or "",
            }
        )

    matrix_list: List[Dict[str, Any]] = []
    for dept_name, data in dept_map.items():
        req_total = data["required_count"]
        valid_total = data["completed_valid_count"]
        pct = round((valid_total / req_total) * 100, 1) if req_total > 0 else 100.0
        if data["expired_gap_count"] > 0:
            dept_status = "Action Required — Expired License(s)"
        elif data["expiring_soon_count"] > 0:
            dept_status = "Renewal Window Open (30–90 Days)"
        else:
            dept_status = "100% Valid & Compliant"

        data["compliance_rate_pct"] = pct
        data["department_status"] = dept_status
        matrix_list.append(data)

    # Sort departments with expired gaps first, then lowest compliance rate
    matrix_list.sort(key=lambda d: (-d["expired_gap_count"], d["compliance_rate_pct"], d["department"]))
    return matrix_list


def build_renewal_notice(
    cert: Dict[str, Any], sender_name: str = "Amara Okafor (L&D and Compliance Lead)"
) -> Dict[str, str]:
    """Generate a plain-English renewal alert message for the employee and their line manager."""
    emp_name = cert["employee_name"]
    mgr_name = cert["manager_name"]
    cert_name = cert["certificate_name"]
    issuer = cert["issuing_body"]
    exp_date = cert["expiry_date"]
    status = cert["status_badge"]
    days_label = cert["days_remaining_label"]

    if status == STATUS_EXPIRED:
        urgency_prefix = "URGENT COMPLIANCE NOTICE"
        action_line = (
            f"Our records indicate that {emp_name}'s mandatory '{cert_name}' issued by {issuer} "
            f"expired on {exp_date} ({days_label}). Please submit renewal confirmation or booking proof "
            f"within 5 business days so role compliance can be restored immediately."
        )
    elif status == STATUS_EXPIRING_30:
        urgency_prefix = "30-DAY RENEWAL REMINDER"
        action_line = (
            f"This is a priority reminder that {emp_name}'s '{cert_name}' ({issuer}) will expire on "
            f"{exp_date} ({days_label}). Please complete the renewal assessment and upload the updated "
            f"certificate before the expiry date."
        )
    else:
        urgency_prefix = "UPCOMING CERTIFICATION RENEWAL NOTICE"
        action_line = (
            f"This is an advance notice that {emp_name}'s '{cert_name}' ({issuer}) is scheduled for "
            f"renewal on {exp_date} ({days_label}). Early scheduling is recommended to maintain continuous "
            f"department compliance."
        )

    subject = f"[{urgency_prefix}] {cert_name} — {emp_name} ({cert['department']})"
    body = (
        f"Dear {emp_name} (cc: {mgr_name}, Line Manager),\n\n"
        f"{action_line}\n\n"
        f"Certificate Details:\n"
        f"• Employee: {emp_name} ({cert['role_title']}, {cert['department']})\n"
        f"• Credential: {cert_name}\n"
        f"• Issuing Body: {issuer}\n"
        f"• Expiry Date: {exp_date} ({days_label})\n"
        f"• Current Status: {status}\n\n"
        f"Warm regards,\n"
        f"{sender_name}\n"
        f"Certification & Skills Agent — People & Compliance Operations"
    )
    return {
        "subject": subject,
        "body": body,
        "recipient_employee": f"{emp_name} <{cert['employee_email']}>",
        "recipient_manager": f"{mgr_name} <{cert['manager_email']}>",
    }


def answer_certification_question(
    question: str,
    enriched_certs: List[Dict[str, Any]],
    skills_matrix: List[Dict[str, Any]],
    kpis: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Plain-English 'Ask Certification Agent' assistant that answers HR & Compliance questions
    deterministically from live certification records.
    """
    q = (question or "").strip().lower()
    expired = [c for c in enriched_certs if c["status_badge"] == STATUS_EXPIRED]
    exp_30 = [c for c in enriched_certs if c["status_badge"] == STATUS_EXPIRING_30]
    exp_60_90 = [c for c in enriched_certs if c["status_badge"] == STATUS_EXPIRING_60_90]
    active = [c for c in enriched_certs if c["status_badge"] == STATUS_ACTIVE]
    bonds = [c for c in enriched_certs if (c.get("bond_amount_usd") or 0) > 0]

    if not q:
        return {
            "agent_name": "Certification & Skills Agent",
            "question": question,
            "answer": (
                f"We are currently tracking {kpis['total_tracked_certifications']} mandatory certifications "
                f"with an overall compliance rate of {kpis['overall_compliance_rate_pct']}%. "
                f"There are {len(expired)} expired certificates requiring immediate action and "
                f"{len(exp_30)} expiring within the next 30 days."
            ),
            "highlights": [
                f"{c['employee_name']} — {c['certificate_name']} ({c['days_remaining_label']})"
                for c in expired[:4]
            ],
        }

    if any(k in q for k in ["expired", "overdue", "lapsed", "immediate", "breach"]):
        if not expired:
            ans = "Great news — zero employee certifications are currently expired. All tracked credentials are valid."
            items = []
        else:
            ans = (
                f"There are currently {len(expired)} expired certifications that require immediate renewal action "
                f"across the organization:"
            )
            items = [
                f"{c['employee_name']} ({c['role_title']}, {c['department']}) — {c['certificate_name']} "
                f"issued by {c['issuing_body']} (Expired {c['expiry_date']}, {c['days_remaining_label']}; "
                f"Line Manager: {c['manager_name']})"
                for c in expired
            ]
        return {
            "agent_name": "Certification & Skills Agent",
            "question": question,
            "answer": ans,
            "highlights": items,
        }

    if any(k in q for k in ["30 day", "30-day", "thirty", "within 30", "soon", "urgent"]):
        ans = (
            f"There are {len(exp_30)} certifications expiring within the next 30 days. "
            f"Sending renewal notices now is recommended to prevent compliance lapses:"
        )
        items = [
            f"{c['employee_name']} ({c['department']}) — {c['certificate_name']} "
            f"(Expires {c['expiry_date']}, {c['days_remaining_label']})"
            for c in exp_30
        ]
        return {
            "agent_name": "Certification & Skills Agent",
            "question": question,
            "answer": ans,
            "highlights": items,
        }

    if any(k in q for k in ["60", "90", "upcoming", "quarter"]):
        ans = (
            f"There are {len(exp_60_90)} certifications in the 60–90 day renewal window, plus "
            f"{len(exp_30)} expiring within 30 days:"
        )
        items = [
            f"{c['employee_name']} ({c['department']}) — {c['certificate_name']} "
            f"(Expires {c['expiry_date']}, {c['days_remaining_label']})"
            for c in (exp_60_90 + exp_30)
        ]
        return {
            "agent_name": "Certification & Skills Agent",
            "question": question,
            "answer": ans,
            "highlights": items,
        }

    if any(k in q for k in ["bond", "reimbursement", "sponsored", "clawback", "cost"]):
        ans = (
            f"We are tracking {len(bonds)} active company-sponsored training bonds totaling "
            f"${kpis['total_training_bond_value_usd']:,.0f} in retention commitments:"
        )
        items = [
            f"{c['employee_name']} ({c['department']}) — {c['certificate_name']}: "
            f"${float(c.get('bond_amount_usd') or 0):,.0f} active bond until {c.get('bond_end_date') or 'N/A'}"
            for c in bonds
        ]
        return {
            "agent_name": "Certification & Skills Agent",
            "question": question,
            "answer": ans,
            "highlights": items,
        }

    if any(k in q for k in ["department", "matrix", "rate", "lowest", "team", "skill"]):
        ans = (
            f"Overall organizational certification compliance stands at {kpis['overall_compliance_rate_pct']}%. "
            f"Here is the breakdown by department from the Role Skills & Certification Matrix:"
        )
        items = [
            f"{d['department']}: {d['compliance_rate_pct']}% compliant "
            f"({d['completed_valid_count']}/{d['required_count']} valid, "
            f"{d['expired_gap_count']} expired, {d['expiring_soon_count']} expiring in 30–90 days)"
            for d in skills_matrix
        ]
        return {
            "agent_name": "Certification & Skills Agent",
            "question": question,
            "answer": ans,
            "highlights": items,
        }

    # Check if the question mentions a specific employee or department or certificate
    matched = [
        c
        for c in enriched_certs
        if c["employee_name"].lower() in q
        or c["department"].lower() in q
        or c["certificate_name"].lower() in q
        or c["issuing_body"].lower() in q
    ]
    if matched:
        ans = f"Found {len(matched)} matching certification record(s) for your query:"
        items = [
            f"{c['employee_name']} ({c['role_title']}, {c['department']}) — {c['certificate_name']} "
            f"[{c['status_badge']}, {c['days_remaining_label']}]"
            for c in matched
        ]
        return {
            "agent_name": "Certification & Skills Agent",
            "question": question,
            "answer": ans,
            "highlights": items,
        }

    # Default executive overview
    return {
        "agent_name": "Certification & Skills Agent",
        "question": question,
        "answer": (
            f"Certification & Skills Agent Summary: Across {kpis['total_tracked_certifications']} mandatory "
            f"staff credentials, {kpis['valid_and_compliant']} are valid & compliant ({len(active)} active beyond "
            f"90 days), {len(exp_30)} expire within 30 days, {len(exp_60_90)} expire within 60–90 days, and "
            f"{len(expired)} are expired and need immediate renewal. {kpis['reminders_sent']} renewal notices "
            f"have been sent to employees and line managers."
        ),
        "highlights": [
            f"Expired — Action Required: {len(expired)} certificate(s)",
            f"Expiring in 30 Days: {len(exp_30)} certificate(s)",
            f"Expiring in 60–90 Days: {len(exp_60_90)} certificate(s)",
            f"Active & Valid (>90 Days): {len(active)} certificate(s)",
        ],
    }
