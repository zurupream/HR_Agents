"""Deterministic Final Settlement Calculator & PDF Generators for Final Clearance and Certificate of Service."""

import json
from typing import Any, Dict, List, Optional
from fpdf import FPDF


def _clean_latin1(text: str) -> str:
    if not text:
        return ""
    replacements = {
        "\u2014": "--",
        "\u2013": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2022": "*",
        "\u2192": "->",
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text.encode("latin-1", "replace").decode("latin-1")


def calculate_final_settlement(
    compensation_amount: float,
    compensation_period: str = "per year",
    days_worked_final_month: int = 18,
    unused_leave_days: float = 6.0,
    asset_deduction: float = 0.0,
) -> Dict[str, float]:
    """Deterministic Final Dues calculator for pro-rata pay, leave encashment, and net payout."""
    period = (compensation_period or "per year").lower()
    if "month" in period:
        annual_pay = float(compensation_amount) * 12.0
    elif "hour" in period:
        annual_pay = float(compensation_amount) * 2080.0
    else:
        annual_pay = float(compensation_amount)

    daily_rate = annual_pay / 260.0  # 260 standard working days per year
    pro_rata_pay = round(daily_rate * max(0, int(days_worked_final_month)), 2)
    leave_encashment = round(daily_rate * max(0.0, float(unused_leave_days)), 2)
    deduction = round(max(0.0, float(asset_deduction or 0.0)), 2)
    gross_settlement = round(pro_rata_pay + leave_encashment, 2)
    net_settlement = round(max(0.0, gross_settlement - deduction), 2)

    return {
        "annual_equivalent": round(annual_pay, 2),
        "daily_rate": round(daily_rate, 2),
        "pro_rata_pay": pro_rata_pay,
        "leave_encashment": leave_encashment,
        "gross_settlement": gross_settlement,
        "asset_deduction": deduction,
        "net_settlement": net_settlement,
    }


class ClearancePDF(FPDF):
    def __init__(self, company_name: str, doc_label: str = "FINAL CLEARANCE & SETTLEMENT STATEMENT"):
        super().__init__()
        self.company_name = _clean_latin1(company_name)
        self.doc_label = _clean_latin1(doc_label)

    def header(self):
        self.set_fill_color(29, 29, 31)
        self.rect(0, 0, 210, 28, "F")
        self.set_y(8)
        self.set_font("Helvetica", "B", 15)
        self.set_text_color(255, 255, 255)
        self.cell(0, 7, self.company_name, new_x="LMARGIN", new_y="NEXT", align="L")
        self.set_font("Helvetica", "", 8.5)
        self.set_text_color(190, 195, 205)
        self.cell(
            0,
            5,
            f"PEOPLE OPERATIONS  |  {self.doc_label}",
            new_x="LMARGIN",
            new_y="NEXT",
            align="L",
        )
        self.ln(8)

    def footer(self):
        self.set_y(-16)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(130, 130, 140)
        self.cell(
            0,
            8,
            f"{self.company_name} -- Confidential HR Exit & Final Settlement Record  |  Page {self.page_no()}",
            align="C",
        )


def generate_clearance_pdf_bytes(
    candidate: Dict[str, Any],
    offer: Dict[str, Any],
    template: Dict[str, Any],
    tasks: Optional[List[Dict[str, Any]]] = None,
) -> bytes:
    """Generate the official Final Clearance & Settlement Statement PDF."""
    company_name = template.get("company_name", "Acme Enterprise Corp.")
    pdf = ClearancePDF(company_name=company_name, doc_label="FINAL CLEARANCE & SETTLEMENT STATEMENT")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    comp_str = f"${candidate['compensation_amount']:,.2f} {candidate['compensation_period']}"
    last_day = candidate.get("last_working_day") or candidate.get("start_date") or "2026-05-22"
    join_date = candidate.get("join_date") or "2023-03-15"
    exit_type = candidate.get("exit_type") or "Voluntary Resignation"

    settlement = calculate_final_settlement(
        compensation_amount=candidate["compensation_amount"],
        compensation_period=candidate.get("compensation_period", "per year"),
        days_worked_final_month=candidate.get("days_worked_final_month", 18),
        unused_leave_days=candidate.get("unused_leave_days", 6.0),
        asset_deduction=candidate.get("asset_deduction", 0.0),
    )

    context = {
        "company_name": company_name,
        "full_name": candidate["full_name"],
        "job_title": candidate["job_title"],
        "department": candidate["department"],
        "manager_name": candidate["manager_name"],
        "location": candidate["location"],
        "compensation": comp_str,
        "start_date": last_day,
        "last_working_day": last_day,
        "join_date": join_date,
        "exit_type": exit_type,
        "unused_leave_days": str(candidate.get("unused_leave_days", 6.0)),
        "work_email": candidate.get("work_email") or "pending@acme.com",
        "assigned_laptop_serial": candidate.get("assigned_laptop_serial") or "N/A",
        "uber_pass_id": candidate.get("uber_pass_id") or "N/A",
        "insurance_policy_id": candidate.get("insurance_policy_id") or "N/A",
    }

    def render_vars(raw: str) -> str:
        out = raw
        for k, v in context.items():
            out = out.replace("{" + k + "}", str(v))
        return _clean_latin1(out)

    # Document Title & Reference
    pdf.set_text_color(29, 29, 31)
    pdf.set_font("Helvetica", "B", 15)
    pdf.cell(0, 9, render_vars(template["title"]), new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 9.5)
    pdf.set_text_color(100, 100, 110)
    ref_line = (
        f"Exit Ref: EXIT-{candidate['id']:04d}   |   Notice Date: {candidate.get('notice_date', offer['sent_at'][:10])}   |   "
        f"Role Tier: {candidate['role_category']}"
    )
    pdf.cell(0, 5, _clean_latin1(ref_line), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    # Greeting & Intro
    pdf.set_text_color(29, 29, 31)
    pdf.set_font("Helvetica", "B", 10.5)
    pdf.cell(0, 6, _clean_latin1(f"Dear {candidate['full_name']},"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)

    pdf.set_font("Helvetica", "", 9.5)
    pdf.multi_cell(0, 5, render_vars(template["intro_text"]))
    pdf.ln(3)

    # Summary Box: Exit & Service Details
    pdf.set_fill_color(245, 245, 247)
    pdf.set_draw_color(215, 215, 222)
    y_start = pdf.get_y()
    pdf.rect(10, y_start, 190, 38, "DF")
    pdf.set_xy(14, y_start + 3)

    rows = [
        ("Position / Title:", candidate["job_title"], "Department:", candidate["department"]),
        ("Reporting Manager:", candidate["manager_name"], "Exit Category:", exit_type),
        ("Date of Joining:", join_date, "Last Working Day:", last_day),
        ("Work Email:", context["work_email"], "Assigned Asset:", context["assigned_laptop_serial"]),
    ]
    for left_lbl, left_val, right_lbl, right_val in rows:
        pdf.set_x(14)
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.set_text_color(90, 90, 100)
        pdf.cell(32, 8, _clean_latin1(left_lbl))
        pdf.set_font("Helvetica", "", 8.5)
        pdf.set_text_color(25, 25, 30)
        pdf.cell(60, 8, _clean_latin1(str(left_val)))

        pdf.set_font("Helvetica", "B", 8.5)
        pdf.set_text_color(90, 90, 100)
        pdf.cell(34, 8, _clean_latin1(right_lbl))
        pdf.set_font("Helvetica", "", 8.5)
        pdf.set_text_color(25, 25, 30)
        pdf.cell(56, 8, _clean_latin1(str(right_val)), new_x="LMARGIN", new_y="NEXT")

    pdf.set_y(y_start + 42)

    # Financial Final Settlement Table
    pdf.set_font("Helvetica", "B", 10.5)
    pdf.set_text_color(0, 113, 227)
    pdf.cell(0, 6, "Final Dues & Settlement Calculation", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(40, 40, 45)

    days_worked = candidate.get("days_worked_final_month", 18)
    leave_days = candidate.get("unused_leave_days", 6.0)
    fin_rows = [
        (f"1. Pro-Rata Final Month Salary ({days_worked} working days @ ${settlement['daily_rate']:,.2f}/day)", f"+ ${settlement['pro_rata_pay']:,.2f}"),
        (f"2. Accrued Unused Leave Encashment ({leave_days} days @ ${settlement['daily_rate']:,.2f}/day)", f"+ ${settlement['leave_encashment']:,.2f}"),
        (f"3. Less: Unreturned Equipment / Advance Recovery ({candidate.get('deduction_notes') or 'None'})", f"- ${settlement['asset_deduction']:,.2f}"),
        ("NET FINAL SETTLEMENT PAYABLE", f"${settlement['net_settlement']:,.2f}"),
    ]
    for idx, (label, amount) in enumerate(fin_rows):
        is_total = idx == len(fin_rows) - 1
        pdf.set_font("Helvetica", "B" if is_total else "", 9.5 if is_total else 9)
        pdf.set_fill_color(235, 244, 255) if is_total else pdf.set_fill_color(252, 252, 253)
        pdf.cell(145, 6.5, _clean_latin1(label), border=1, fill=True)
        pdf.cell(45, 6.5, _clean_latin1(amount), border=1, fill=True, align="R", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(3)

    # Reverse De-Provisioning & Clearance Checklist
    if tasks:
        pdf.set_font("Helvetica", "B", 10.5)
        pdf.set_text_color(0, 113, 227)
        pdf.cell(0, 6, "Reverse De-Provisioning & Department Clearance Status", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 8.5)
        pdf.set_text_color(45, 45, 50)
        for t in tasks:
            line = f"  * {t['agent_name']} ({t['department']}): {t['status']} -- {t['current_stage']}"
            pdf.cell(0, 5, _clean_latin1(line), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

    # Terms & Conditions
    terms = (
        json.loads(template["terms_json"])
        if isinstance(template.get("terms_json"), str)
        else template.get("terms", [])
    )
    pdf.set_font("Helvetica", "B", 10.5)
    pdf.set_text_color(0, 113, 227)
    pdf.cell(0, 6, "Clearance Terms & Separation Commitments", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 8.5)
    pdf.set_text_color(45, 45, 50)
    for idx, term in enumerate(terms, start=1):
        pdf.multi_cell(0, 4.8, f"{idx}. {render_vars(term)}")
        pdf.ln(0.8)

    pdf.ln(2)

    # Signature Block
    sig_y = pdf.get_y()
    if sig_y > 235:
        pdf.add_page()
        sig_y = pdf.get_y()

    if offer["status"] == "ACCEPTED":
        pdf.set_fill_color(235, 250, 240)
        pdf.set_draw_color(52, 199, 89)
    elif offer["status"] == "DECLINED":
        pdf.set_fill_color(253, 238, 238)
        pdf.set_draw_color(255, 59, 48)
    else:
        pdf.set_fill_color(250, 248, 240)
        pdf.set_draw_color(230, 190, 100)

    pdf.rect(10, sig_y, 190, 28, "DF")
    pdf.set_xy(14, sig_y + 3)
    pdf.set_font("Helvetica", "B", 9.5)
    pdf.set_text_color(29, 29, 31)
    pdf.cell(
        0,
        5.5,
        _clean_latin1(f"Digital Clearance E-Signature Status: {offer['status']}"),
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.set_x(14)
    pdf.set_font("Helvetica", "", 8.5)
    if offer["status"] == "ACCEPTED":
        sig_line = (
            f"Electronically signed by: {offer.get('signature_text') or candidate['full_name']}   |   "
            f"Timestamp: {offer.get('responded_at') or ''}"
        )
    elif offer["status"] == "DECLINED":
        sig_line = (
            f"Settlement Query / Dispute Raised on {offer.get('responded_at') or ''}   |   "
            f"Reason: {offer.get('decline_reason') or 'Calculation review requested'}"
        )
    else:
        sig_line = "Awaiting employee digital signature via HR Offboarding E-Sign Portal."
    pdf.cell(0, 5, _clean_latin1(sig_line), new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(14)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(95, 95, 105)
    pdf.cell(0, 5, render_vars(template["footer_text"]), new_x="LMARGIN", new_y="NEXT")

    return bytes(pdf.output())


# Backward-compatible alias
generate_offer_pdf_bytes = generate_clearance_pdf_bytes


def generate_certificate_pdf_bytes(
    candidate: Dict[str, Any],
    offer: Optional[Dict[str, Any]] = None,
    template: Optional[Dict[str, Any]] = None,
) -> bytes:
    """Generate the official Certificate of Service & Good Standing PDF."""
    company_name = (template or {}).get("company_name", "Acme Enterprise Corp.")
    pdf = ClearancePDF(company_name=company_name, doc_label="OFFICIAL CERTIFICATE OF SERVICE & EXPERIENCE")
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    join_date = candidate.get("join_date") or "2023-03-15"
    last_day = candidate.get("last_working_day") or candidate.get("start_date") or "2026-05-22"

    pdf.ln(6)
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(29, 29, 31)
    pdf.cell(0, 10, "CERTIFICATE OF SERVICE & GOOD STANDING", align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(100, 100, 110)
    pdf.cell(
        0,
        6,
        _clean_latin1(f"Certificate ID: COS-{candidate['id']:04d}-2026   |   Issued by {company_name}"),
        align="C",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(8)

    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(29, 29, 31)
    pdf.cell(0, 8, "TO WHOM IT MAY CONCERN", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    body_p1 = (
        f"This is to certify that {candidate['full_name']} was employed with {company_name} "
        f"as {candidate['job_title']} in the {candidate['department']} department from "
        f"{join_date} through {last_day} ({candidate['role_category']} classification)."
    )
    body_p2 = (
        f"During their tenure reporting to {candidate['manager_name']}, {candidate['full_name']} "
        f"demonstrated strong professional dedication, domain leadership, and integrity. "
        f"All departmental responsibilities, company equipment returns, benefits closures, and IT security "
        f"handovers have been completed in full accordance with company policy."
    )
    body_p3 = (
        f"We thank {candidate['full_name']} for their valuable contributions to {company_name} "
        f"and wish them continued success in all future career endeavors."
    )

    pdf.set_font("Helvetica", "", 10.5)
    pdf.set_text_color(40, 40, 45)
    pdf.multi_cell(0, 6.5, _clean_latin1(body_p1))
    pdf.ln(4)
    pdf.multi_cell(0, 6.5, _clean_latin1(body_p2))
    pdf.ln(4)
    pdf.multi_cell(0, 6.5, _clean_latin1(body_p3))
    pdf.ln(8)

    # Employment Record Verification Box
    y_box = pdf.get_y()
    pdf.set_fill_color(245, 245, 247)
    pdf.set_draw_color(210, 210, 220)
    pdf.rect(10, y_box, 190, 36, "DF")
    pdf.set_xy(15, y_box + 4)

    summary_rows = [
        ("Employee Full Name:", candidate["full_name"], "Employment Classification:", candidate["role_category"]),
        ("Last Held Designation:", candidate["job_title"], "Department:", candidate["department"]),
        ("Service Start Date:", join_date, "Final Working Day:", last_day),
        ("Exit Classification:", candidate.get("exit_type", "Voluntary Resignation"), "Clearance Status:", "Verified & Cleared"),
    ]
    for l1, v1, l2, v2 in summary_rows:
        pdf.set_x(15)
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.set_text_color(95, 95, 105)
        pdf.cell(38, 7, _clean_latin1(l1))
        pdf.set_font("Helvetica", "", 8.5)
        pdf.set_text_color(25, 25, 30)
        pdf.cell(52, 7, _clean_latin1(str(v1)))

        pdf.set_font("Helvetica", "B", 8.5)
        pdf.set_text_color(95, 95, 105)
        pdf.cell(42, 7, _clean_latin1(l2))
        pdf.set_font("Helvetica", "", 8.5)
        pdf.set_text_color(25, 25, 30)
        pdf.cell(50, 7, _clean_latin1(str(v2)), new_x="LMARGIN", new_y="NEXT")

    pdf.set_y(y_box + 45)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(29, 29, 31)
    pdf.cell(0, 6, "Authorized Digitally by People Operations", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(90, 90, 100)
    pdf.cell(0, 5, _clean_latin1(f"Elena Rostova, VP of People Operations -- {company_name}"), new_x="LMARGIN", new_y="NEXT")

    return bytes(pdf.output())
