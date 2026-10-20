"""SQLite database initialization, persistence helpers, and default templates."""

from datetime import datetime, timezone
import os
import sqlite3
from typing import Any, Dict, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "hr_onboarding.db")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


DEFAULT_OFFER_TEMPLATES = {
    "EMPLOYEE": {
        "role_category": "EMPLOYEE",
        "template_name": "Full-Time Employee Offer Letter",
        "email_subject": "[Offer Letter] {{position_title}} — {{candidate_name}}",
        "header_title": "Official Offer of Appointment — Full-Time Employee",
        "opening_text": (
            "Dear {{candidate_name}},\n\n"
            "We are delighted to offer you the full-time position of {{position_title}} in the "
            "{{department}} department at Sybyl, reporting to {{hod_name}} (Head of Department)."
        ),
        "body_text": (
            "Your compensation package will be {{compensation}}, with a scheduled start date of {{joining_date}}. "
            "As a Full-Time Employee, your Day-1 onboarding package includes your Company Email account, "
            "Work Laptop, Corporate Uber Commute Pass, and Group Health Insurance coverage."
        ),
        "closing_text": (
            "Please review and sign this offer letter online before the expiration date. "
            "Once signed, HR, your Head of Department, and the CEO will be notified automatically, "
            "and our team will begin preparing your Day-1 onboarding items.\n\n"
            "Warm regards,\nPeople & Culture Team — Sybyl"
        ),
    },
    "TRAINEE": {
        "role_category": "TRAINEE",
        "template_name": "Trainee Offer Letter",
        "email_subject": "[Offer Letter] {{position_title}} (Trainee) — {{candidate_name}}",
        "header_title": "Official Offer of Appointment — Trainee Program",
        "opening_text": (
            "Dear {{candidate_name}},\n\n"
            "Congratulations! We are pleased to offer you the position of {{position_title}} (Trainee) "
            "in the {{department}} department at Sybyl, reporting to {{hod_name}} (Head of Department)."
        ),
        "body_text": (
            "Your trainee compensation package will be {{compensation}}, with a scheduled start date of {{joining_date}}. "
            "As a Trainee at Sybyl, your Day-1 onboarding setup includes your Company Email account, "
            "Work Laptop, and Corporate Uber Commute Pass."
        ),
        "closing_text": (
            "Please review and sign this offer letter online before the expiration date so our team can "
            "prepare your work email, laptop, and commute pass ahead of your first day.\n\n"
            "Warm regards,\nPeople & Culture Team — Sybyl"
        ),
    },
    "INTERN": {
        "role_category": "INTERN",
        "template_name": "Internship Offer Letter",
        "email_subject": "[Internship Offer] {{position_title}} — {{candidate_name}}",
        "header_title": "Official Internship Offer Letter",
        "opening_text": (
            "Dear {{candidate_name}},\n\n"
            "We are excited to welcome you to Sybyl as a {{position_title}} (Intern) in our "
            "{{department}} department, reporting to {{hod_name}} (Head of Department)."
        ),
        "body_text": (
            "Your internship stipend will be {{compensation}}, with a scheduled start date of {{joining_date}}. "
            "As an Intern, our IT team will create your official Sybyl email account as soon as you accept this offer."
        ),
        "closing_text": (
            "Please review and sign your internship offer online before the expiration date.\n\n"
            "Warm regards,\nPeople & Culture Team — Sybyl"
        ),
    },
}


def init_db() -> None:
    conn = get_conn()
    cur = conn.cursor()

    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS smtp_settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            sender_email TEXT NOT NULL DEFAULT 'psrmreports@sybyl.com',
            app_password TEXT DEFAULT 'kfbx btjf hcfk rwyb',
            smtp_host TEXT NOT NULL DEFAULT 'smtp.gmail.com',
            smtp_port INTEGER NOT NULL DEFAULT 587,
            use_tls INTEGER NOT NULL DEFAULT 1,
            live_mode_enabled INTEGER NOT NULL DEFAULT 1,
            default_hr_email TEXT NOT NULL DEFAULT 'hr@sybyl.com',
            default_ceo_email TEXT NOT NULL DEFAULT 'ceo@sybyl.com',
            default_cc_emails TEXT NOT NULL DEFAULT 'hr@sybyl.com; hod@sybyl.com; ceo@sybyl.com',
            override_recipient_for_demo TEXT DEFAULT '',
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS offer_templates (
            role_category TEXT PRIMARY KEY,
            template_name TEXT NOT NULL,
            email_subject TEXT NOT NULL,
            header_title TEXT NOT NULL,
            opening_text TEXT NOT NULL,
            body_text TEXT NOT NULL,
            closing_text TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS positions (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            department TEXT NOT NULL,
            hod_name TEXT NOT NULL,
            hod_email TEXT NOT NULL,
            headcount_target INTEGER NOT NULL DEFAULT 1,
            location TEXT NOT NULL DEFAULT 'Hybrid / HQ',
            status TEXT NOT NULL DEFAULT 'OPEN',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS candidates (
            id TEXT PRIMARY KEY,
            batch_id TEXT NOT NULL,
            batch_name TEXT NOT NULL,
            position_id TEXT NOT NULL,
            full_name TEXT NOT NULL,
            personal_email TEXT NOT NULL,
            phone TEXT,
            corporate_email TEXT,
            role_category TEXT NOT NULL,
            compensation TEXT NOT NULL,
            joining_date TEXT NOT NULL,
            hr_email TEXT NOT NULL,
            hod_email TEXT NOT NULL,
            ceo_email TEXT NOT NULL,
            cc_emails TEXT NOT NULL DEFAULT 'hr@sybyl.com; ceo@sybyl.com',
            overall_stage TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (position_id) REFERENCES positions(id)
        );

        CREATE TABLE IF NOT EXISTS offer_letters (
            id TEXT PRIMARY KEY,
            candidate_id TEXT NOT NULL UNIQUE,
            signing_token TEXT NOT NULL UNIQUE,
            esign_provider TEXT NOT NULL DEFAULT 'ONLINE',
            status TEXT NOT NULL DEFAULT 'SENT',
            sent_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            viewed_at TEXT,
            responded_at TEXT,
            signer_name TEXT,
            signature_data TEXT,
            signature_type TEXT,
            signature_hash TEXT,
            decline_reason TEXT,
            comments TEXT,
            pdf_path TEXT,
            signed_pdf_path TEXT,
            FOREIGN KEY (candidate_id) REFERENCES candidates(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS provisioning_tasks (
            id TEXT PRIMARY KEY,
            candidate_id TEXT NOT NULL,
            task_type TEXT NOT NULL,
            agent_id TEXT NOT NULL,
            agent_name TEXT NOT NULL,
            department TEXT NOT NULL,
            depends_on TEXT,
            status TEXT NOT NULL DEFAULT 'PENDING',
            current_stage_idx INTEGER NOT NULL DEFAULT 0,
            total_stages INTEGER NOT NULL DEFAULT 5,
            stage_label TEXT NOT NULL,
            external_ref_id TEXT,
            output_summary TEXT,
            blocker_reason TEXT,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            started_at TEXT,
            completed_at TEXT,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (candidate_id) REFERENCES candidates(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS notification_logs (
            id TEXT PRIMARY KEY,
            candidate_id TEXT,
            event_type TEXT NOT NULL,
            subject TEXT NOT NULL,
            recipient_to TEXT NOT NULL,
            recipients_cc TEXT NOT NULL,
            body_html TEXT NOT NULL,
            delivery_mode TEXT NOT NULL DEFAULT 'SANDBOX_OUTBOX',
            delivery_status TEXT NOT NULL DEFAULT 'DELIVERED',
            attachment_path TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS agent_audit_events (
            id TEXT PRIMARY KEY,
            candidate_id TEXT,
            agent_name TEXT NOT NULL,
            event_type TEXT NOT NULL,
            message TEXT NOT NULL,
            details_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL
        );
        """
    )

    # Ensure backward-compatible columns on existing tables
    cand_cols = [r["name"] for r in cur.execute("PRAGMA table_info(candidates)").fetchall()]
    if "cc_emails" not in cand_cols:
        cur.execute(
            "ALTER TABLE candidates ADD COLUMN cc_emails TEXT NOT NULL DEFAULT 'hr@sybyl.com; ceo@sybyl.com'"
        )

    smtp_cols = [r["name"] for r in cur.execute("PRAGMA table_info(smtp_settings)").fetchall()]
    if "default_cc_emails" not in smtp_cols:
        cur.execute(
            "ALTER TABLE smtp_settings ADD COLUMN default_cc_emails TEXT NOT NULL DEFAULT 'hr@sybyl.com; hod@sybyl.com; ceo@sybyl.com'"
        )

    # Ensure SMTP singleton row exists
    cur.execute("SELECT COUNT(*) as cnt FROM smtp_settings WHERE id = 1")
    if cur.fetchone()["cnt"] == 0:
        cur.execute(
            """
            INSERT INTO smtp_settings (
                id, sender_email, app_password, smtp_host, smtp_port,
                use_tls, live_mode_enabled, default_hr_email, default_ceo_email,
                default_cc_emails, override_recipient_for_demo, updated_at
            ) VALUES (
                1, 'psrmreports@sybyl.com', 'kfbx btjf hcfk rwyb', 'smtp.gmail.com', 587,
                1, 1, 'hr@sybyl.com', 'ceo@sybyl.com',
                'hr@sybyl.com; hod@sybyl.com; ceo@sybyl.com', '', ?
            )
            """,
            (utc_now_iso(),),
        )

    # Seed default offer letter templates if not present
    now = utc_now_iso()
    for role_key, tpl in DEFAULT_OFFER_TEMPLATES.items():
        cur.execute(
            "SELECT COUNT(*) as cnt FROM offer_templates WHERE role_category = ?",
            (role_key,),
        )
        if cur.fetchone()["cnt"] == 0:
            cur.execute(
                """
                INSERT INTO offer_templates (
                    role_category, template_name, email_subject, header_title,
                    opening_text, body_text, closing_text, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tpl["role_category"],
                    tpl["template_name"],
                    tpl["email_subject"],
                    tpl["header_title"],
                    tpl["opening_text"],
                    tpl["body_text"],
                    tpl["closing_text"],
                    now,
                ),
            )

    conn.commit()
    conn.close()


def dict_from_row(row: Optional[sqlite3.Row]) -> Optional[Dict[str, Any]]:
    if row is None:
        return None
    return dict(row)
