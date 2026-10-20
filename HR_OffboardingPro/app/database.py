"""SQLite persistence layer for HR Offboarding Pro."""

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

DB_PATH = os.environ.get(
    "HR_OFFBOARDING_DB",
    os.environ.get(
        "HR_ONBOARDING_DB",
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "hr_offboarding.db"),
    ),
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


DEFAULT_CLEARANCE_TEMPLATES = {
    "INTERN": {
        "company_name": "Acme Enterprise Corp.",
        "title": "Internship Completion, Clearance & Final Stipend Statement",
        "intro_text": (
            "Thank you for your valuable contributions during your internship at {company_name} as a "
            "{job_title} in our {department} team, reporting to {manager_name}. This statement confirms "
            "your final working day on {last_working_day} and outlines your exit clearance and final stipend settlement."
        ),
        "terms": [
            "Final Working Day: Your internship assignment concludes at the close of business on {last_working_day}.",
            "Final Stipend Calculation: Pro-rata stipend for days completed in the final billing cycle plus any approved expense reimbursements.",
            "IT Access & Work Email Deactivation: Your corporate email ({work_email}) and Single Sign-On access will be archived and deactivated upon completion of clearance.",
            "Confidentiality & Intellectual Property: All project deliverables, source code, and proprietary documentation remain the exclusive property of {company_name}.",
        ],
        "benefits": [
            "Official Internship Completion & Certificate of Service PDF issued upon clearance",
            "Automatic email forwarding to your manager ({manager_name}) for 30 days",
            "Fast-track alumni consideration for future Graduate Trainee and Full-Time openings",
            "Direct deposit of final pro-rata stipend within 5 business days of sign-off",
        ],
        "footer_text": (
            "By signing below, you confirm that you have handed over all project files and accept this Final Clearance & Settlement Statement."
        ),
    },
    "TRAINEE": {
        "company_name": "Acme Enterprise Corp.",
        "title": "Graduate Trainee Exit Clearance & Final Settlement Statement",
        "intro_text": (
            "We appreciate your dedication during your Graduate Rotational Traineeship at {company_name} as a "
            "{job_title} in the {department} division under {manager_name}. Please review your department "
            "clearance checklist, equipment return summary, and net final settlement effective {last_working_day}."
        ),
        "terms": [
            "Last Working Day: Your traineeship employment concludes on {last_working_day} ({exit_type}).",
            "Uber Commute Pass Revocation: Your monthly corporate Uber commute allowance ({uber_pass_id}) is audited and revoked effective on your last working day.",
            "Workstation & Equipment Return: Assigned laptop ({assigned_laptop_serial}) and accessories must be inspected and cleared by IT Equipment prior to final release.",
            "IT Email & Single Sign-On Deactivation: Once hardware handover is verified, {work_email} will be set to auto-reply and archived.",
        ],
        "benefits": [
            "Full pro-rata salary payout for days worked in the final month",
            "100% encashment of accrued unused annual leave days ({unused_leave_days} days)",
            "Official Certificate of Service & Experience Letter issued immediately upon sign-off",
            "Seamless digital handover verification with zero paper forms required",
        ],
        "footer_text": (
            "By signing below, you confirm that all company equipment has been returned and agree to the Final Settlement breakdown."
        ),
    },
    "EMPLOYEE": {
        "company_name": "Acme Enterprise Corp.",
        "title": "Employee Exit Clearance, Asset Handover & Final Settlement Statement",
        "intro_text": (
            "Thank you for your service at {company_name} as {job_title} in the {department} department, "
            "reporting to {manager_name}. This official statement records your exit notice ({exit_type}), "
            "tracks reverse de-provisioning across Benefits, Transport, IT Equipment, and IT Security, "
            "and details your Final Dues & Leave Encashment payable upon your last working day ({last_working_day})."
        ),
        "terms": [
            "Last Working Day & Handover: Your employment concludes on {last_working_day}. All knowledge transfer and team handovers are coordinated with {manager_name}.",
            "Health Insurance Termination: Corporate medical policy ({insurance_policy_id}) remains active through the end of your final day and is then terminated with a COBRA/continuation certificate.",
            "Uber Commute Pass Revocation: Corporate Uber Pass ({uber_pass_id}) is reconciled and removed from the enterprise billing profile.",
            "Laptop & Equipment Return: Assigned workstation ({assigned_laptop_serial}) must pass physical inspection and data wipe prior to final IT Email deactivation ({work_email}).",
        ],
        "benefits": [
            "Pro-rata base compensation for all days worked in the final payroll month",
            "Full encashment of unused accrued vacation & paid time off ({unused_leave_days} days)",
            "Verified Certificate of Service & Good Standing PDF issued automatically",
            "30-day continuation window to convert group health coverage to an individual plan",
        ],
        "footer_text": (
            "By signing below, you acknowledge receipt of your Final Dues breakdown, confirm return of all company property, and complete your exit clearance."
        ),
    },
}


def init_db():
    with get_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                personal_email TEXT NOT NULL,
                phone TEXT NOT NULL,
                role_category TEXT NOT NULL,
                job_title TEXT NOT NULL,
                department TEXT NOT NULL,
                manager_name TEXT NOT NULL,
                location TEXT NOT NULL,
                compensation_amount REAL NOT NULL,
                compensation_period TEXT NOT NULL,
                join_date TEXT NOT NULL DEFAULT '2023-03-15',
                notice_date TEXT NOT NULL DEFAULT '2026-05-01',
                last_working_day TEXT NOT NULL DEFAULT '2026-05-22',
                start_date TEXT NOT NULL DEFAULT '2026-05-22',
                exit_type TEXT NOT NULL DEFAULT 'Voluntary Resignation',
                exit_reason TEXT NOT NULL DEFAULT 'Career progression',
                days_worked_final_month INTEGER NOT NULL DEFAULT 18,
                unused_leave_days REAL NOT NULL DEFAULT 6.0,
                asset_deduction REAL NOT NULL DEFAULT 0.0,
                deduction_notes TEXT DEFAULT 'All company equipment accounted for',
                pro_rata_pay REAL NOT NULL DEFAULT 0.0,
                leave_encashment REAL NOT NULL DEFAULT 0.0,
                net_settlement REAL NOT NULL DEFAULT 0.0,
                custom_notes TEXT,
                offboarding_status TEXT NOT NULL DEFAULT 'EXIT_INITIATED',
                onboarding_status TEXT NOT NULL DEFAULT 'OFFER_SENT',
                work_email TEXT,
                assigned_laptop_serial TEXT,
                uber_pass_id TEXT,
                insurance_policy_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS offer_letters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_id INTEGER NOT NULL UNIQUE,
                signing_token TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL DEFAULT 'SENT',
                sent_at TEXT NOT NULL,
                viewed_at TEXT,
                responded_at TEXT,
                signature_text TEXT,
                decline_reason TEXT,
                forwarding_address TEXT,
                handover_confirmed INTEGER NOT NULL DEFAULT 1,
                pdf_version INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (candidate_id) REFERENCES candidates(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS provisioning_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_id INTEGER NOT NULL,
                task_type TEXT NOT NULL,
                agent_name TEXT NOT NULL,
                department TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING',
                stage_idx INTEGER NOT NULL DEFAULT 0,
                current_stage TEXT NOT NULL,
                total_stages INTEGER NOT NULL,
                depends_on TEXT,
                blocker_reason TEXT,
                artifact_value TEXT,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (candidate_id) REFERENCES candidates(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS agent_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_id INTEGER,
                agent_name TEXT NOT NULL,
                event_type TEXT NOT NULL,
                message TEXT NOT NULL,
                metadata_json TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (candidate_id) REFERENCES candidates(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS email_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_id INTEGER,
                recipient_email TEXT NOT NULL,
                recipient_name TEXT NOT NULL,
                subject TEXT NOT NULL,
                body_preview TEXT NOT NULL,
                category TEXT NOT NULL,
                delivery_status TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS smtp_settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                smtp_host TEXT NOT NULL DEFAULT '',
                smtp_port INTEGER NOT NULL DEFAULT 587,
                smtp_user TEXT NOT NULL DEFAULT '',
                smtp_password TEXT NOT NULL DEFAULT '',
                from_email TEXT NOT NULL DEFAULT 'people-exits@acme-enterprise.com',
                from_name TEXT NOT NULL DEFAULT 'Acme People Operations — Exit & Clearance Team',
                enabled INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS offer_templates (
                role_category TEXT PRIMARY KEY,
                company_name TEXT NOT NULL,
                title TEXT NOT NULL,
                intro_text TEXT NOT NULL,
                terms_json TEXT NOT NULL,
                benefits_json TEXT NOT NULL,
                footer_text TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )

        row = conn.execute("SELECT id FROM smtp_settings WHERE id = 1").fetchone()
        if not row:
            conn.execute(
                """
                INSERT INTO smtp_settings (id, smtp_host, smtp_port, smtp_user, smtp_password, from_email, from_name, enabled, updated_at)
                VALUES (1, 'smtp.acme-enterprise.com', 587, '', '', 'people-exits@acme-enterprise.com', 'Acme People Operations — Exit & Clearance Team', 0, ?)
                """,
                (utc_now_iso(),),
            )

        for role_cat, tpl in DEFAULT_CLEARANCE_TEMPLATES.items():
            existing = conn.execute(
                "SELECT role_category FROM offer_templates WHERE role_category = ?",
                (role_cat,),
            ).fetchone()
            if not existing:
                conn.execute(
                    """
                    INSERT INTO offer_templates (role_category, company_name, title, intro_text, terms_json, benefits_json, footer_text, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        role_cat,
                        tpl["company_name"],
                        tpl["title"],
                        tpl["intro_text"],
                        json.dumps(tpl["terms"]),
                        json.dumps(tpl["benefits"]),
                        tpl["footer_text"],
                        utc_now_iso(),
                    ),
                )
