"""Outbox email service with optional live SMTP relay and SQLite audit logging."""

import smtplib
from email.message import EmailMessage
from typing import Optional
from .database import get_db, utc_now_iso
from .pdf_generator import generate_clearance_pdf_bytes


def send_or_log_email(
    candidate_id: Optional[int],
    recipient_email: str,
    recipient_name: str,
    subject: str,
    body_text: str,
    category: str = "CLEARANCE_DISPATCH",
    attach_clearance_pdf: bool = False,
) -> dict:
    """Send an email via configured SMTP or record in the simulated outbox log."""
    delivery_status = "SIMULATED_SENT"
    with get_db() as conn:
        smtp_row = conn.execute("SELECT * FROM smtp_settings WHERE id = 1").fetchone()
        smtp_cfg = dict(smtp_row) if smtp_row else {}

        pdf_bytes = None
        if attach_clearance_pdf and candidate_id:
            cand = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
            offer = conn.execute("SELECT * FROM offer_letters WHERE candidate_id = ?", (candidate_id,)).fetchone()
            if cand and offer:
                tpl = conn.execute(
                    "SELECT * FROM offer_templates WHERE role_category = ?",
                    (cand["role_category"],),
                ).fetchone()
                if tpl:
                    pdf_bytes = generate_clearance_pdf_bytes(dict(cand), dict(offer), dict(tpl))

        if smtp_cfg.get("enabled") and smtp_cfg.get("smtp_host"):
            try:
                msg = EmailMessage()
                msg["Subject"] = subject
                msg["From"] = f"{smtp_cfg.get('from_name', 'HR Exit Team')} <{smtp_cfg.get('from_email', 'exits@acme.com')}>"
                msg["To"] = f"{recipient_name} <{recipient_email}>"
                msg.set_content(body_text)
                if pdf_bytes:
                    msg.add_attachment(
                        pdf_bytes,
                        maintype="application",
                        subtype="pdf",
                        filename=f"Final_Clearance_Statement_{candidate_id}.pdf",
                    )
                with smtplib.SMTP(smtp_cfg["smtp_host"], int(smtp_cfg.get("smtp_port", 587)), timeout=5) as server:
                    server.starttls()
                    if smtp_cfg.get("smtp_user") and smtp_cfg.get("smtp_password"):
                        server.login(smtp_cfg["smtp_user"], smtp_cfg["smtp_password"])
                    server.send_message(msg)
                delivery_status = "SMTP_DELIVERED"
            except Exception as exc:
                delivery_status = f"FALLBACK_LOGGED ({type(exc).__name__})"

        preview = body_text[:300] + ("..." if len(body_text) > 300 else "")
        cur = conn.execute(
            """
            INSERT INTO email_notifications
            (candidate_id, recipient_email, recipient_name, subject, body_preview, category, delivery_status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                candidate_id,
                recipient_email,
                recipient_name,
                subject,
                preview,
                category,
                delivery_status,
                utc_now_iso(),
            ),
        )
        return {
            "id": cur.lastrowid,
            "recipient_email": recipient_email,
            "subject": subject,
            "delivery_status": delivery_status,
        }
