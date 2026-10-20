"""1-Page Printable Certification Compliance Audit Report PDF & CSV Generator."""

import csv
from datetime import date
import io
from typing import Any, Dict, List

try:
    from fpdf import FPDF
except ImportError:
    FPDF = None


def _clean_pdf_text(text: Any) -> str:
    """Ensure Latin-1 safe text for standard PDF core fonts."""
    val = str(text or "")
    replacements = {
        "—": "-",
        "–": "-",
        "•": "*",
        "“": '"',
        "”": '"',
        "’": "'",
        "‘": "'",
    }
    for k, v in replacements.items():
        val = val.replace(k, v)
    return val.encode("latin-1", "replace").decode("latin-1")


def _build_minimal_pdf_bytes(lines: List[str]) -> bytes:
    """Zero-dependency valid PDF-1.4 generator fallback when fpdf2 is not in current env."""
    escaped_lines = []
    y = 790
    for idx, line in enumerate(lines[:44]):
        safe = (
            _clean_pdf_text(line)
            .replace("\\", "\\\\")
            .replace("(", "\\(")
            .replace(")", "\\)")
        )
        font_size = 13 if idx == 0 else (10 if idx < 4 else 8.5)
        escaped_lines.append(f"BT /F1 {font_size} Tf 36 {y} Td ({safe}) Tj ET")
        y -= 16 if idx < 4 else 14

    stream_data = "\n".join(escaped_lines).encode("latin-1")
    objs = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n",
        b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
        f"5 0 obj\n<< /Length {len(stream_data)} >>\nstream\n".encode("latin-1")
        + stream_data
        + b"\nendstream\nendobj\n",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objs:
        offsets.append(len(out))
        out.extend(obj)
    xref_start = len(out)
    out.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode("latin-1"))
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode("latin-1"))
    out.extend(
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF\n".encode(
            "latin-1"
        )
    )
    return bytes(out)


def generate_compliance_audit_pdf_bytes(
    kpis: Dict[str, Any],
    enriched_certs: List[Dict[str, Any]],
    skills_matrix: List[Dict[str, Any]],
    prepared_by: str = "Amara Okafor (L&D and Compliance Lead)",
) -> bytes:
    """Generate a clean 1-Page Certification Compliance Audit Report PDF."""
    if FPDF is None:
        lines = [
            "1-PAGE CERTIFICATION COMPLIANCE AUDIT REPORT",
            f"Prepared by Certification & Skills Agent | Lead: {prepared_by} | Date: {date.today().isoformat()}",
            f"Total Tracked: {kpis['total_tracked_certifications']} | Valid & Compliant: {kpis['valid_and_compliant']} ({kpis['overall_compliance_rate_pct']}%) | Expired: {kpis['expired_immediate_renewal']} | Expiring 30d: {kpis['expiring_within_30_days']} | Reminders: {kpis['reminders_sent']}",
            "----------------------------------------------------------------------------------------------------",
            "DEPARTMENT SKILLS & CERTIFICATION MATRIX:",
        ]
        for dept in skills_matrix:
            lines.append(
                f"  * {dept['department']}: {dept['compliance_rate_pct']}% compliant ({dept['completed_valid_count']}/{dept['required_count']} valid, {dept['expired_gap_count']} expired)"
            )
        lines.append("EMPLOYEE CERTIFICATION REGISTER:")
        for cert in enriched_certs[:15]:
            lines.append(
                f"  * {cert['employee_name']} ({cert['department']}) - {cert['certificate_name']} | Exp: {cert['expiry_date']} | {cert['status_badge']}"
            )
        return _build_minimal_pdf_bytes(lines)

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_page()

    # Header bar
    pdf.set_fill_color(29, 29, 31)
    pdf.rect(0, 0, 210, 26, style="F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_xy(12, 6)
    pdf.cell(0, 7, "1-PAGE CERTIFICATION COMPLIANCE AUDIT REPORT", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_x(12)
    pdf.cell(
        0,
        5,
        _clean_pdf_text(
            f"Prepared by Certification & Skills Agent | Lead: {prepared_by} | Audit Date: {date.today().isoformat()}"
        ),
        new_x="LMARGIN",
        new_y="NEXT",
    )

    pdf.ln(8)
    pdf.set_text_color(29, 29, 31)

    # KPI Summary Box
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, "1. EXECUTIVE COMPLIANCE SUMMARY", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    summary_line = (
        f"Total Tracked: {kpis['total_tracked_certifications']}   |   "
        f"Valid & Compliant: {kpis['valid_and_compliant']} ({kpis['overall_compliance_rate_pct']}%)   |   "
        f"Expiring in 30 Days: {kpis['expiring_within_30_days']}   |   "
        f"Expired (Action Required): {kpis['expired_immediate_renewal']}   |   "
        f"Reminders Sent: {kpis['reminders_sent']}"
    )
    pdf.set_fill_color(245, 245, 247)
    pdf.cell(0, 8, _clean_pdf_text(summary_line), border=1, fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # Department Skills Matrix Table
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, "2. DEPARTMENT ROLE SKILLS & CERTIFICATION MATRIX", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(232, 232, 237)
    pdf.cell(62, 6, "Department", border=1, fill=True)
    pdf.cell(28, 6, "Required", border=1, fill=True, align="C")
    pdf.cell(28, 6, "Valid", border=1, fill=True, align="C")
    pdf.cell(28, 6, "Expired", border=1, fill=True, align="C")
    pdf.cell(44, 6, "Compliance Rate", border=1, fill=True, align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 8)
    for dept in skills_matrix:
        pdf.cell(62, 5.5, _clean_pdf_text(dept["department"][:34]), border=1)
        pdf.cell(28, 5.5, str(dept["required_count"]), border=1, align="C")
        pdf.cell(28, 5.5, str(dept["completed_valid_count"]), border=1, align="C")
        pdf.cell(28, 5.5, str(dept["expired_gap_count"]), border=1, align="C")
        pdf.cell(
            44,
            5.5,
            f"{dept['compliance_rate_pct']}%",
            border=1,
            align="C",
            new_x="LMARGIN",
            new_y="NEXT",
        )

    pdf.ln(4)

    # Certification & License Register
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(
        0,
        6,
        "3. EMPLOYEE CERTIFICATION & LICENSE COMPLIANCE REGISTER",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.set_font("Helvetica", "B", 7.5)
    pdf.set_fill_color(232, 232, 237)
    pdf.cell(34, 6, "Employee", border=1, fill=True)
    pdf.cell(36, 6, "Department", border=1, fill=True)
    pdf.cell(54, 6, "Certificate / License", border=1, fill=True)
    pdf.cell(22, 6, "Expiry Date", border=1, fill=True, align="C")
    pdf.cell(44, 6, "Status Badge", border=1, fill=True, align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 7.5)
    for cert in enriched_certs[:14]:
        pdf.cell(34, 5.2, _clean_pdf_text(cert["employee_name"][:20]), border=1)
        pdf.cell(36, 5.2, _clean_pdf_text(cert["department"][:21]), border=1)
        pdf.cell(54, 5.2, _clean_pdf_text(cert["certificate_name"][:32]), border=1)
        pdf.cell(22, 5.2, _clean_pdf_text(cert["expiry_date"]), border=1, align="C")
        pdf.cell(
            44,
            5.2,
            _clean_pdf_text(cert["status_badge"]),
            border=1,
            align="C",
            new_x="LMARGIN",
            new_y="NEXT",
        )

    pdf.ln(5)
    pdf.set_font("Helvetica", "I", 8)
    pdf.cell(
        0,
        5,
        _clean_pdf_text(
            "Certified by HR Compliance & People Operations | Generated by Certification & Skills Agent"
        ),
        new_x="LMARGIN",
        new_y="NEXT",
    )

    out = pdf.output()
    return bytes(out)


def generate_compliance_csv_string(enriched_certs: List[Dict[str, Any]]) -> str:
    """Export all tracked certifications and status badges as a clean CSV string."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "Employee ID",
            "Employee Name",
            "Role",
            "Department",
            "Line Manager",
            "Certificate / License Name",
            "Issuing Body",
            "Expiry Date",
            "Days Remaining",
            "Status Badge",
            "Training Bond (USD)",
            "Reminders Sent",
        ]
    )
    for c in enriched_certs:
        writer.writerow(
            [
                c["employee_id"],
                c["employee_name"],
                c["role_title"],
                c["department"],
                c["manager_name"],
                c["certificate_name"],
                c["issuing_body"],
                c["expiry_date"],
                c["days_remaining"],
                c["status_badge"],
                c.get("bond_amount_usd", 0.0),
                c.get("reminders_sent", 0),
            ]
        )
    return buf.getvalue()
