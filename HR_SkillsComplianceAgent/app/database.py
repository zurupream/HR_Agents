"""SQLite Persistence & Realistic Enterprise Seed Data for Learning, Certification Expiry & Skills Matrix Agent."""

from datetime import date, datetime, timedelta, timezone
import os
import sqlite3
from typing import Any, Dict, List

DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "hr_skills_compliance.db"
)


def get_db_path() -> str:
    return os.environ.get("HR_SKILLS_DB", DEFAULT_DB_PATH)


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def init_db() -> None:
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS certifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT NOT NULL,
            employee_name TEXT NOT NULL,
            employee_email TEXT NOT NULL,
            role_title TEXT NOT NULL,
            department TEXT NOT NULL,
            manager_name TEXT NOT NULL,
            manager_email TEXT NOT NULL,
            certificate_name TEXT NOT NULL,
            license_number TEXT NOT NULL,
            issuing_body TEXT NOT NULL,
            skill_category TEXT NOT NULL,
            issue_date TEXT NOT NULL,
            expiry_date TEXT NOT NULL,
            bond_amount_usd REAL DEFAULT 0.0,
            bond_end_date TEXT DEFAULT '',
            reminders_sent INTEGER DEFAULT 0,
            last_reminder_at TEXT DEFAULT ''
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS reminder_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cert_id INTEGER NOT NULL,
            employee_name TEXT NOT NULL,
            employee_email TEXT NOT NULL,
            manager_name TEXT NOT NULL,
            manager_email TEXT NOT NULL,
            certificate_name TEXT NOT NULL,
            status_at_send TEXT NOT NULL,
            subject TEXT NOT NULL,
            body TEXT NOT NULL,
            sent_by TEXT NOT NULL,
            sent_at TEXT NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS role_skill_requirements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            department TEXT NOT NULL,
            department_head TEXT NOT NULL,
            role_title TEXT NOT NULL,
            required_certificate TEXT NOT NULL,
            issuing_body TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def seed_demo_data(force_reset: bool = False) -> None:
    """Seed realistic enterprise certification & license records relative to today's date."""
    init_db()
    conn = get_db()
    cur = conn.cursor()

    if force_reset:
        cur.execute("DELETE FROM certifications")
        cur.execute("DELETE FROM reminder_logs")
        cur.execute("DELETE FROM role_skill_requirements")
        conn.commit()

    cur.execute("SELECT COUNT(*) AS cnt FROM certifications")
    if cur.fetchone()["cnt"] > 0:
        conn.close()
        return

    today = date.today()

    def rel_date(days_offset: int) -> str:
        return (today + timedelta(days=days_offset)).strftime("%Y-%m-%d")

    seed_certs = [
        # 1. Expired — Action Required (< 0 days)
        (
            "EMP-104",
            "David Kimani",
            "david.kimani@acme.com",
            "Senior Financial Controller",
            "Finance & Accounting",
            "Grace Mwangi",
            "grace.mwangi@acme.com",
            "CPA(K) Annual Practicing License",
            "ICPAK-88412",
            "ICPAK (Institute of Certified Public Accountants)",
            "Statutory Financial Reporting",
            rel_date(-380),
            rel_date(-14),
            2400.0,
            rel_date(180),
            1,
            "2026-10-12 09:15 UTC",
        ),
        (
            "EMP-112",
            "Samuel Ochieng",
            "samuel.ochieng@acme.com",
            "Plant Operations & HSE Supervisor",
            "Operations & Safety",
            "Peter Njoroge",
            "peter.njoroge@acme.com",
            "OSHA Occupational Health, Fire & Safety License",
            "DOSHS-44290",
            "Directorate of Occupational Safety & Health (DOSHS)",
            "Workplace Safety & Emergency Response",
            rel_date(-372),
            rel_date(-6),
            0.0,
            "",
            1,
            "2026-10-15 11:30 UTC",
        ),
        (
            "EMP-119",
            "Dr. Amina Hassan",
            "amina.hassan@acme.com",
            "Occupational Health Nurse",
            "Clinical & Field Services",
            "Dr. Victor Mutua",
            "victor.mutua@acme.com",
            "Basic Life Support (BLS) & Clinical Practicing License",
            "NCK-20941",
            "Nursing Council & AHA Clinical Board",
            "Clinical Emergency & Staff Care",
            rel_date(-385),
            rel_date(-19),
            1800.0,
            rel_date(240),
            0,
            "",
        ),
        # 2. Expiring in 30 Days (0 <= days <= 30)
        (
            "EMP-108",
            "Faith Wanjiku",
            "faith.wanjiku@acme.com",
            "HR Business Partner",
            "People & Culture",
            "Amara Okafor",
            "amara.okafor@acme.com",
            "IHRM Certified HR Practicing Certificate",
            "IHRM-55301",
            "Institute of Human Resource Management (IHRM)",
            "Labor Law & HR Compliance",
            rel_date(-356),
            rel_date(9),
            1500.0,
            rel_date(210),
            1,
            "2026-10-18 14:20 UTC",
        ),
        (
            "EMP-115",
            "Kelvin Otieno",
            "kelvin.otieno@acme.com",
            "Lead Cloud Security Architect",
            "Engineering & Cloud Security",
            "Liam Chen",
            "liam.chen@acme.com",
            "ISO 27001 Lead Information Security Auditor",
            "PECB-99104",
            "PECB / ISO Security Certification Board",
            "Information Security & Audit",
            rel_date(-348),
            rel_date(17),
            3500.0,
            rel_date(320),
            0,
            "",
        ),
        (
            "EMP-121",
            "Brenda Achieng",
            "brenda.achieng@acme.com",
            "Data Privacy & Legal Counsel",
            "Legal & Regulatory Compliance",
            "Evelyn Ndungu",
            "evelyn.ndungu@acme.com",
            "Certified Data Protection Officer (CDPO) License",
            "ODPC-77419",
            "Office of the Data Protection Commissioner (ODPC)",
            "Data Privacy & Regulatory Filing",
            rel_date(-340),
            rel_date(25),
            2800.0,
            rel_date(290),
            0,
            "",
        ),
        # 3. Expiring in 60–90 Days (31 <= days <= 90)
        (
            "EMP-126",
            "Brian Kiprop",
            "brian.kiprop@acme.com",
            "Senior Platform Reliability Engineer",
            "Engineering & Cloud Security",
            "Liam Chen",
            "liam.chen@acme.com",
            "AWS Certified Solutions Architect — Professional",
            "AWS-PRO-33198",
            "Amazon Web Services (AWS)",
            "Cloud Infrastructure & Resilience",
            rel_date(-295),
            rel_date(70),
            3200.0,
            rel_date(365),
            0,
            "",
        ),
        (
            "EMP-131",
            "Mercy Chebet",
            "mercy.chebet@acme.com",
            "Fleet & High-Voltage Equipment Lead",
            "Operations & Safety",
            "Peter Njoroge",
            "peter.njoroge@acme.com",
            "EPRA Electrical & Industrial Safety Operator Permit",
            "EPRA-61209",
            "Energy & Petroleum Regulatory Authority (EPRA)",
            "Industrial Equipment Safety",
            rel_date(-310),
            rel_date(55),
            0.0,
            "",
            0,
            "",
        ),
        # 4. Active & Valid (> 90 days)
        (
            "EMP-138",
            "Daniel Mwende",
            "daniel.mwende@acme.com",
            "Payroll & Tax Compliance Specialist",
            "Finance & Accounting",
            "Grace Mwangi",
            "grace.mwangi@acme.com",
            "Certified Tax & Statutory Payroll Practitioner",
            "KRA-ICPAK-11290",
            "ICPAK & Kenya Revenue Authority Academy",
            "Statutory Payroll & Tax Filing",
            rel_date(-150),
            rel_date(215),
            0.0,
            "",
            0,
            "",
        ),
        (
            "EMP-142",
            "Sophia Njeri",
            "sophia.njeri@acme.com",
            "Enterprise Program Delivery Manager",
            "Engineering & Cloud Security",
            "Liam Chen",
            "liam.chen@acme.com",
            "Project Management Professional (PMP)",
            "PMI-609182",
            "Project Management Institute (PMI)",
            "Enterprise Delivery Governance",
            rel_date(-120),
            rel_date(245),
            2200.0,
            rel_date(400),
            0,
            "",
        ),
        (
            "EMP-149",
            "Christine Wambui",
            "christine.wambui@acme.com",
            "Anti-Money Laundering (AML) Officer",
            "Legal & Regulatory Compliance",
            "Evelyn Ndungu",
            "evelyn.ndungu@acme.com",
            "Certified Anti-Money Laundering Specialist (CAMS)",
            "ACAMS-51820",
            "Association of Certified Anti-Money Laundering Specialists",
            "Financial Crime & KYC Compliance",
            rel_date(-185),
            rel_date(180),
            3000.0,
            rel_date(310),
            0,
            "",
        ),
        (
            "EMP-154",
            "Patrick Mutiso",
            "patrick.mutiso@acme.com",
            "Field Emergency & Wellness Coordinator",
            "Clinical & Field Services",
            "Dr. Victor Mutua",
            "victor.mutua@acme.com",
            "Advanced First Aid & Wilderness Rescue License",
            "KRCS-90814",
            "Red Cross Medical Training Institute",
            "Emergency Field Response",
            rel_date(-190),
            rel_date(175),
            0.0,
            "",
            0,
            "",
        ),
    ]

    cur.executemany(
        """
        INSERT INTO certifications (
            employee_id, employee_name, employee_email, role_title, department,
            manager_name, manager_email, certificate_name, license_number,
            issuing_body, skill_category, issue_date, expiry_date,
            bond_amount_usd, bond_end_date, reminders_sent, last_reminder_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        seed_certs,
    )

    # Seed initial reminder log entries matching the 3 initial reminders_sent
    seed_logs = [
        (
            1,
            "David Kimani",
            "david.kimani@acme.com",
            "Grace Mwangi",
            "grace.mwangi@acme.com",
            "CPA(K) Annual Practicing License",
            "Expired — Action Required",
            "[URGENT COMPLIANCE NOTICE] CPA(K) Annual Practicing License — David Kimani (Finance & Accounting)",
            "Urgent renewal notice sent to David Kimani and Line Manager Grace Mwangi.",
            "Amara Okafor",
            "2026-10-12 09:15 UTC",
        ),
        (
            2,
            "Samuel Ochieng",
            "samuel.ochieng@acme.com",
            "Peter Njoroge",
            "peter.njoroge@acme.com",
            "OSHA Occupational Health, Fire & Safety License",
            "Expired — Action Required",
            "[URGENT COMPLIANCE NOTICE] OSHA Occupational Health, Fire & Safety License — Samuel Ochieng (Operations & Safety)",
            "Urgent renewal notice sent to Samuel Ochieng and Line Manager Peter Njoroge.",
            "Amara Okafor",
            "2026-10-15 11:30 UTC",
        ),
        (
            4,
            "Faith Wanjiku",
            "faith.wanjiku@acme.com",
            "Amara Okafor",
            "amara.okafor@acme.com",
            "IHRM Certified HR Practicing Certificate",
            "Expiring in 30 Days",
            "[30-DAY RENEWAL REMINDER] IHRM Certified HR Practicing Certificate — Faith Wanjiku (People & Culture)",
            "30-day renewal reminder dispatched to Faith Wanjiku and Line Manager Amara Okafor.",
            "Amara Okafor",
            "2026-10-18 14:20 UTC",
        ),
    ]
    cur.executemany(
        """
        INSERT INTO reminder_logs (
            cert_id, employee_name, employee_email, manager_name, manager_email,
            certificate_name, status_at_send, subject, body, sent_by, sent_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        seed_logs,
    )

    seed_role_reqs = [
        ("Finance & Accounting", "Grace Mwangi", "Senior Financial Controller", "CPA(K) Annual Practicing License", "ICPAK"),
        ("Operations & Safety", "Peter Njoroge", "Plant Operations & HSE Supervisor", "OSHA Occupational Health, Fire & Safety License", "DOSHS"),
        ("Clinical & Field Services", "Dr. Victor Mutua", "Occupational Health Nurse", "Basic Life Support (BLS) & Clinical Practicing License", "Nursing Council"),
        ("People & Culture", "Amara Okafor", "HR Business Partner", "IHRM Certified HR Practicing Certificate", "IHRM"),
        ("Engineering & Cloud Security", "Liam Chen", "Lead Cloud Security Architect", "ISO 27001 Lead Information Security Auditor", "PECB"),
        ("Legal & Regulatory Compliance", "Evelyn Ndungu", "Data Privacy & Legal Counsel", "Certified Data Protection Officer (CDPO) License", "ODPC"),
    ]
    cur.executemany(
        """
        INSERT INTO role_skill_requirements (
            department, department_head, role_title, required_certificate, issuing_body
        ) VALUES (?, ?, ?, ?, ?)
        """,
        seed_role_reqs,
    )

    conn.commit()
    conn.close()


def fetch_all_certifications() -> List[Dict[str, Any]]:
    conn = get_db()
    rows = conn.execute("SELECT * FROM certifications ORDER BY expiry_date ASC, id ASC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def fetch_role_requirements() -> List[Dict[str, Any]]:
    conn = get_db()
    rows = conn.execute("SELECT * FROM role_skill_requirements ORDER BY department ASC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def fetch_reminder_logs() -> List[Dict[str, Any]]:
    conn = get_db()
    rows = conn.execute("SELECT * FROM reminder_logs ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def count_reminders_sent() -> int:
    conn = get_db()
    row = conn.execute("SELECT COUNT(*) AS cnt FROM reminder_logs").fetchone()
    conn.close()
    return int(row["cnt"]) if row else 0
