"""PDF Offer Letter generator for Sybyl People."""

import hashlib
import os
from typing import Any, Dict, List, Optional
from fpdf import FPDF

from app.database import DEFAULT_OFFER_TEMPLATES, dict_from_row, get_conn
from app.models import ROLE_ONBOARDING_STEPS

PDF_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "generated_offers")
os.makedirs(PDF_DIR, exist_ok=True)


def _sanitize_latin1(text: str) -> str:
    if not text:
        return ""
    replacements = {
        "\u2014": "-",
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


def normalize_template_row(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Normalizes offer template fields so both DB column names and UI field names are present."""
    role_key = (raw.get("role_category") or "EMPLOYEE").upper()
    default_tpl = DEFAULT_OFFER_TEMPLATES.get(role_key, DEFAULT_OFFER_TEMPLATES["EMPLOYEE"])
    header_title = (
        raw.get("header_title")
        or raw.get("title")
        or default_tpl.get("header_title", "Official Offer of Appointment")
    )
    email_subject = (
        raw.get("email_subject")
        or raw.get("subject_line")
        or raw.get("email_subject_template")
        or default_tpl.get("email_subject", "[Offer Letter] {{position_title}} — {{candidate_name}}")
    )
    opening_text = (
        raw.get("opening_text")
        or raw.get("intro_text")
        or default_tpl.get("opening_text", "")
    )
    body_text = (
        raw.get("body_text")
        or raw.get("terms_text")
        or default_tpl.get("body_text", "")
    )
    closing_text = (
        raw.get("closing_text")
        or default_tpl.get("closing_text", "Warm regards,\nPeople & Culture Team — Sybyl")
    )
    template_name = raw.get("template_name") or default_tpl.get("template_name", f"{role_key.title()} Offer Letter")
    return {
        "role_category": role_key,
        "template_name": template_name,
        "header_title": header_title,
        "title": header_title,
        "email_subject": email_subject,
        "subject_line": email_subject,
        "email_subject_template": email_subject,
        "opening_text": opening_text,
        "intro_text": opening_text,
        "body_text": body_text,
        "terms_text": body_text,
        "closing_text": closing_text,
        "updated_at": raw.get("updated_at", ""),
    }


def get_offer_template(role_category: str) -> Dict[str, Any]:
    role_key = (role_category or "EMPLOYEE").upper()
    try:
        conn = get_conn()
        row = conn.execute(
            "SELECT * FROM offer_templates WHERE role_category = ?", (role_key,)
        ).fetchone()
        conn.close()
        if row:
            return normalize_template_row(dict_from_row(row))
    except Exception:
        pass
    return normalize_template_row(
        DEFAULT_OFFER_TEMPLATES.get(role_key, DEFAULT_OFFER_TEMPLATES["EMPLOYEE"])
    )


def get_all_offer_templates_map() -> Dict[str, Dict[str, Any]]:
    result: Dict[str, Dict[str, Any]] = {}
    for role_key, default_tpl in DEFAULT_OFFER_TEMPLATES.items():
        result[role_key] = normalize_template_row(default_tpl)
    try:
        conn = get_conn()
        rows = conn.execute("SELECT * FROM offer_templates ORDER BY role_category ASC").fetchall()
        conn.close()
        for r in rows:
            d = normalize_template_row(dict_from_row(r))
            result[d["role_category"]] = d
    except Exception:
        pass
    return result


def render_template_text(
    template_str: str,
    candidate: Dict,
    position: Dict,
    offer: Optional[Dict] = None,
) -> str:
    if not template_str:
        return ""
    offer_dict = offer or {}
    comp = candidate.get("compensation") or candidate.get("compensation_package") or ""
    expires_date = str(offer_dict.get("expires_at") or "")[:10]
    vars_map = {
        "candidate_name": str(candidate.get("full_name", "")),
        "position_title": str(position.get("title", "")),
        "department": str(position.get("department", "")),
        "hod_name": str(position.get("hod_name", "")),
        "hod_email": str(position.get("hod_email", "")),
        "compensation": str(comp),
        "joining_date": str(candidate.get("joining_date", "")),
        "role_category": str(candidate.get("role_category", "")).title(),
        "expires_at": expires_date,
    }
    out = template_str
    for k, v in vars_map.items():
        out = out.replace(f"{{{{{k}}}}}", v)
        out = out.replace(f"{{{k}}}", v)
    return out


def generate_offer_pdf(
    candidate: Dict,
    position: Dict,
    offer: Dict,
    signed: bool = False,
) -> str:
    """Generates an official PDF offer letter (unsigned or signed) using the role template."""
    tpl = get_offer_template(candidate.get("role_category", "EMPLOYEE"))
    header_title = render_template_text(tpl.get("header_title", ""), candidate, position, offer)
    opening_text = render_template_text(tpl.get("opening_text", ""), candidate, position, offer)
    body_text = render_template_text(tpl.get("body_text", ""), candidate, position, offer)
    closing_text = render_template_text(tpl.get("closing_text", ""), candidate, position, offer)


    cc_display = candidate.get("cc_emails") or (
        f"{candidate.get('hr_email', 'hr@sybyl.com')}; "
        f"{candidate.get('hod_email', '')}; "
        f"{candidate.get('ceo_email', 'ceo@sybyl.com')}"
    )

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    # Header Banner
    pdf.set_fill_color(29, 29, 31)  # Apple Ink #1D1D1F
    pdf.rect(0, 0, 210, 34, "F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_xy(15, 10)
    pdf.cell(120, 8, "SYBYL", ln=0)

    pdf.set_font("Helvetica", "B", 10)
    pdf.set_xy(135, 10)
    status_badge = "SIGNED & ACCEPTED" if signed else f"STATUS: {offer.get('status', 'SENT')}"
    pdf.cell(60, 8, _sanitize_latin1(status_badge), align="R", ln=1)

    pdf.set_font("Helvetica", "", 9.5)
    pdf.set_text_color(174, 174, 178)
    pdf.set_xy(15, 19)
    pdf.cell(180, 6, _sanitize_latin1(f"People & Culture | {header_title}"), ln=1)

    pdf.ln(14)
    pdf.set_text_color(29, 29, 31)

    # Metadata block
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(100, 6, _sanitize_latin1(f"Candidate: {candidate['full_name']}"), ln=0)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(80, 6, _sanitize_latin1(f"Offer Ref: {offer['id']}"), align="R", ln=1)

    pdf.cell(100, 5, _sanitize_latin1(f"Email: {candidate['personal_email']}"), ln=0)
    pdf.cell(80, 5, _sanitize_latin1(f"Date Issued: {offer['sent_at'][:10]}"), align="R", ln=1)

    pdf.cell(180, 5, _sanitize_latin1(f"Copied (CC): {cc_display}"), ln=1)
    pdf.cell(100, 5, _sanitize_latin1(f"Offer Valid Until: {offer['expires_at'][:10]}"), ln=1)

    pdf.ln(5)
    pdf.set_draw_color(210, 210, 215)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(6)

    # Salutation & Body from Template
    pdf.set_font("Helvetica", "B", 12.5)
    pdf.cell(
        180,
        8,
        _sanitize_latin1(f"{position['title']} ({candidate['role_category'].title()})"),
        ln=1,
    )
    pdf.ln(2)

    pdf.set_font("Helvetica", "", 10)
    full_body = f"{opening_text}\n\n{body_text}"
    pdf.multi_cell(180, 6, _sanitize_latin1(full_body))
    pdf.ln(4)

    # Role-Specific Onboarding Setup Box
    pdf.set_fill_color(245, 245, 247)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(
        180,
        8,
        _sanitize_latin1(f"  Included Day-1 Onboarding Setup ({candidate['role_category'].title()})"),
        ln=1,
        fill=True,
    )

    role_steps: List[str] = ROLE_ONBOARDING_STEPS.get(candidate["role_category"], ["EMAIL"])
    step_descriptions = {
        "EMAIL": "Company Email Account (@sybyl.com)",
        "LAPTOP": "Work Laptop Prepared for Day 1",
        "UBER": "Uber Corporate Commute Pass",
        "INSURANCE": "Group Health & Medical Insurance Coverage",
    }

    pdf.set_font("Helvetica", "", 9.5)
    for step in ["EMAIL", "LAPTOP", "UBER", "INSURANCE"]:
        included = step in role_steps
        prefix = "[INCLUDED]" if included else "[NOT INCLUDED]"
        pdf.cell(180, 6, _sanitize_latin1(f"   {prefix}  {step_descriptions[step]}"), ln=1)

    pdf.ln(5)
    pdf.multi_cell(180, 5.5, _sanitize_latin1(closing_text))
    pdf.ln(6)

    # Signature Block
    if signed:
        pdf.set_fill_color(232, 248, 238)
        pdf.set_draw_color(52, 199, 89)
        y_start = pdf.get_y()
        pdf.rect(15, y_start, 180, 32, "DF")
        pdf.set_xy(20, y_start + 4)
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(29, 122, 59)
        pdf.cell(170, 6, "OFFER SIGNED & ACCEPTED", ln=1)

        pdf.set_font("Helvetica", "", 9.5)
        pdf.set_text_color(29, 29, 31)
        pdf.set_x(20)
        pdf.cell(
            170,
            6,
            _sanitize_latin1(f"Signed By: {offer.get('signer_name') or candidate['full_name']}"),
            ln=1,
        )
        pdf.set_x(20)
        pdf.cell(
            170,
            6,
            _sanitize_latin1(
                f"Date Signed: {(offer.get('responded_at') or '')[:16].replace('T', ' ')}"
            ),
            ln=1,
        )
        pdf.set_x(20)
        pdf.cell(170, 6, _sanitize_latin1(f"Offer Reference: {offer.get('id', '')}"), ln=1)
    else:
        pdf.set_font("Helvetica", "I", 9.5)
        pdf.set_text_color(110, 110, 115)
        pdf.cell(
            180,
            8,
            _sanitize_latin1(f"Awaiting Candidate Signature (Reference: {offer['id']})"),
            ln=1,
        )

    filename = f"{'signed_' if signed else ''}offer_{offer['id']}.pdf"
    filepath = os.path.join(PDF_DIR, filename)
    pdf.output(filepath)
    return filepath


def compute_signature_hash(candidate_id: str, signer_name: str, responded_at: str) -> str:
    payload = f"{candidate_id}|{signer_name}|{responded_at}|SYBYL-SIGNED"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
