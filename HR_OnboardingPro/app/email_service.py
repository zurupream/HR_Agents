"""Dual-Mode Email & Stakeholder Notification Service.

Supports:
1. In-App Simulated Outbox Console (always active so every To/CC email is inspectable in the UI).
2. Live SMTP Dispatch via psrmreports@sybyl.com (or any configured SMTP server) when App Password is provided.
"""

from email.message import EmailMessage
import os
import smtplib
import ssl
import uuid
from typing import Any, Dict, List, Optional, Tuple

from app.database import dict_from_row, get_conn, utc_now_iso
from app.models import parse_cc_emails


def get_smtp_settings() -> Dict[str, Any]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM smtp_settings WHERE id = 1").fetchone()
    conn.close()
    data = dict_from_row(row) or {}
    # Mask password in general status responses while keeping boolean indicator
    has_password = bool(data.get("app_password"))
    data["has_app_password"] = has_password
    if not data.get("default_cc_emails"):
        hr = data.get("default_hr_email") or "hr@sybyl.com"
        ceo = data.get("default_ceo_email") or "ceo@sybyl.com"
        data["default_cc_emails"] = f"{hr}; {ceo}"
    return data


def update_smtp_settings(
    sender_email: str,
    app_password: Optional[str],
    smtp_host: str,
    smtp_port: int,
    use_tls: bool,
    live_mode_enabled: bool,
    default_hr_email: str,
    default_ceo_email: str,
    override_recipient_for_demo: Optional[str] = "",
    default_cc_emails: Optional[str] = None,
) -> Dict[str, Any]:
    conn = get_conn()
    existing = dict_from_row(conn.execute("SELECT * FROM smtp_settings WHERE id = 1").fetchone()) or {}

    # Preserve existing app password if None or masked placeholder is passed
    final_password = existing.get("app_password", "")
    if app_password is not None and app_password != "••••••••":
        final_password = app_password.strip()

    parsed_cc = parse_cc_emails(default_cc_emails, default_hr_email, default_ceo_email)
    cc_joined = "; ".join(parsed_cc) if parsed_cc else "hr@sybyl.com; ceo@sybyl.com"
    primary_hr = parsed_cc[0] if parsed_cc else (default_hr_email.strip() or "hr@sybyl.com")
    primary_ceo = parsed_cc[-1] if len(parsed_cc) > 1 else (default_ceo_email.strip() or "ceo@sybyl.com")

    conn.execute(
        """
        UPDATE smtp_settings
        SET sender_email = ?,
            app_password = ?,
            smtp_host = ?,
            smtp_port = ?,
            use_tls = ?,
            live_mode_enabled = ?,
            default_hr_email = ?,
            default_ceo_email = ?,
            default_cc_emails = ?,
            override_recipient_for_demo = ?,
            updated_at = ?
        WHERE id = 1
        """,
        (
            sender_email.strip(),
            final_password,
            smtp_host.strip(),
            int(smtp_port),
            1 if use_tls else 0,
            1 if live_mode_enabled else 0,
            primary_hr,
            primary_ceo,
            cc_joined,
            (override_recipient_for_demo or "").strip(),
            utc_now_iso(),
        ),
    )
    conn.commit()
    conn.close()
    return get_smtp_settings()


def test_smtp_connection(send_test_email_to: Optional[str] = None) -> Tuple[bool, str]:
    """Tests SMTP authentication with psrmreports@sybyl.com and optionally sends a test email."""
    settings = get_smtp_settings()
    sender = settings.get("sender_email", "psrmreports@sybyl.com")
    password = settings.get("app_password", "")
    host = settings.get("smtp_host", "smtp.gmail.com")
    port = int(settings.get("smtp_port", 587))
    use_tls = bool(settings.get("use_tls", 1))

    if not password:
        return False, f"App Password is not set for {sender}. Paste the App Password first."

    recipients = parse_cc_emails(send_test_email_to) if send_test_email_to else []
    to_header = ", ".join(recipients) if recipients else ""

    try:
        context = ssl.create_default_context()
        if port == 465:
            with smtplib.SMTP_SSL(host, port, context=context, timeout=12) as server:
                server.login(sender, password)
                if to_header:
                    msg = EmailMessage()
                    msg["Subject"] = "[Sybyl People] Email Connection Verified"
                    msg["From"] = sender
                    msg["To"] = to_header
                    msg.set_content(
                        f"Email connection verified for {sender}.\n"
                        "Sybyl People is ready to send offer letters and onboarding updates."
                    )
                    server.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=12) as server:
                server.ehlo()
                if use_tls:
                    server.starttls(context=context)
                    server.ehlo()
                server.login(sender, password)
                if to_header:
                    msg = EmailMessage()
                    msg["Subject"] = "[Sybyl People] Email Connection Verified"
                    msg["From"] = sender
                    msg["To"] = to_header
                    msg.set_content(
                        f"Email connection verified for {sender}.\n"
                        "Sybyl People is ready to send offer letters and onboarding updates."
                    )
                    server.send_message(msg)
        return True, f"Connected as {sender}"
    except Exception as exc:
        return False, f"Email connection failed: {str(exc)}"


def dispatch_stakeholder_email(
    candidate_id: Optional[str],
    event_type: str,
    subject: str,
    recipient_to: str,
    recipients_cc: List[str],
    body_html: str,
    attachment_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Logs the email in the in-app Outbox AND sends via Live Email if enabled."""
    settings = get_smtp_settings()
    cc_clean = parse_cc_emails(*(recipients_cc or []))
    cc_str = "; ".join(cc_clean)

    delivery_mode = "LOGGED"
    delivery_status = "Logged in Sent Emails"

    if settings.get("live_mode_enabled") and settings.get("app_password"):
        sender = settings["sender_email"]
        password = settings["app_password"]
        host = settings["smtp_host"]
        port = int(settings["smtp_port"])
        use_tls = bool(settings["use_tls"])
        override_to = (settings.get("override_recipient_for_demo") or "").strip()

        try:
            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = sender
            if override_to:
                override_list = parse_cc_emails(override_to)
                msg["To"] = ", ".join(override_list) if override_list else override_to
                msg["X-Original-To"] = recipient_to
                msg["X-Original-CC"] = cc_str
            else:
                mock_placeholders = {
                    "hr@sybyl.com",
                    "ceo@sybyl.com",
                    "hod@sybyl.com",
                    "elena.vance@sybyl.com",
                    "marcus.sterling@sybyl.com",
                    "priya.nair@sybyl.com",
                    "david.kim@sybyl.com",
                    "rachel.adams@sybyl.com",
                    "daniel.okafor@sybyl.com",
                    "tariq.mansoor@sybyl.com",
                    "claire.bennett@sybyl.com",
                }
                to_candidates = parse_cc_emails(recipient_to) or [recipient_to.strip()]
                primary_to = to_candidates[0]
                is_mock_to = primary_to.endswith("@example.com") or primary_to.lower() in mock_placeholders
                live_to = sender if is_mock_to else primary_to
                live_cc = [
                    c for c in cc_clean
                    if not c.endswith("@example.com") and c.lower() not in mock_placeholders
                ]
                if sender.lower() not in [live_to.lower()] + [c.lower() for c in live_cc]:
                    live_cc.append(sender)
                msg["To"] = live_to
                if live_cc:
                    msg["Cc"] = ", ".join(live_cc)
                msg["X-Original-To"] = recipient_to
                msg["X-Original-CC"] = cc_str

            msg.set_content("Please view this message in an HTML-compatible email client.")
            msg.add_alternative(body_html, subtype="html")

            if attachment_path and os.path.exists(attachment_path):
                with open(attachment_path, "rb") as f:
                    file_data = f.read()
                msg.add_attachment(
                    file_data,
                    maintype="application",
                    subtype="pdf",
                    filename=os.path.basename(attachment_path),
                )

            context = ssl.create_default_context()
            if port == 465:
                with smtplib.SMTP_SSL(host, port, context=context, timeout=15) as server:
                    server.login(sender, password)
                    server.send_message(msg)
            else:
                with smtplib.SMTP(host, port, timeout=15) as server:
                    server.ehlo()
                    if use_tls:
                        server.starttls(context=context)
                        server.ehlo()
                    server.login(sender, password)
                    server.send_message(msg)

            delivery_mode = "LIVE_SMTP"
            delivery_status = f"SENT VIA LIVE SMTP ({sender})"
        except Exception as exc:
            delivery_mode = "LIVE_SMTP_FALLBACK"
            delivery_status = f"SANDBOX LOGGED (SMTP Error: {str(exc)[:80]})"

    notif_id = f"ntf-{uuid.uuid4().hex[:10]}"
    now = utc_now_iso()
    conn = get_conn()
    conn.execute(
        """
        INSERT INTO notification_logs (
            id, candidate_id, event_type, subject, recipient_to,
            recipients_cc, body_html, delivery_mode, delivery_status,
            attachment_path, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            notif_id,
            candidate_id,
            event_type,
            subject,
            recipient_to,
            cc_str,
            body_html,
            delivery_mode,
            delivery_status,
            attachment_path,
            now,
        ),
    )
    conn.commit()
    conn.close()

    return {
        "id": notif_id,
        "event_type": event_type,
        "subject": subject,
        "recipient_to": recipient_to,
        "recipients_cc": cc_clean,
        "delivery_mode": delivery_mode,
        "delivery_status": delivery_status,
        "created_at": now,
    }
