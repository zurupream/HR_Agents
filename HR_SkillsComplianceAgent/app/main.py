"""FastAPI Application for Agent #08: Learning, Certification Expiry & Skills Matrix Agent."""

from contextlib import asynccontextmanager
from datetime import date, timedelta
import os
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .auth_service import (
    GOOGLE_CLIENT_ID,
    create_demo_session,
    request_email_otp,
    verify_email_otp,
    verify_google_credential,
)
from .compliance_engine import (
    STATUS_ACTIVE,
    STATUS_EXPIRED,
    STATUS_EXPIRING_30,
    STATUS_EXPIRING_60_90,
    answer_certification_question,
    build_department_skills_matrix,
    build_renewal_notice,
    compute_kpi_summary,
    enrich_certification_record,
)
from .database import (
    count_reminders_sent,
    fetch_all_certifications,
    fetch_reminder_logs,
    fetch_role_requirements,
    get_db,
    init_db,
    seed_demo_data,
    utc_now_iso,
)
from .pdf_report import (
    generate_compliance_audit_pdf_bytes,
    generate_compliance_csv_string,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    seed_demo_data(force_reset=False)
    yield


app = FastAPI(
    title="Learning, Certification Expiry & Skills Matrix Agent",
    description="Monitors mandatory professional licenses, safety certificates, and role skills compliance with 30/60/90-day expiry detection and 1-click renewal notices.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ─── Request / Response Schemas ───────────────────────────────────────────────


class GoogleAuthRequest(BaseModel):
    credential: str


class OTPRequestModel(BaseModel):
    email: str


class OTPVerifyModel(BaseModel):
    email: str
    code: str


class DemoAuthModel(BaseModel):
    persona: str = "Amara Okafor"


class RemindRequest(BaseModel):
    sender_name: str = "Amara Okafor (L&D and Compliance Lead)"


class BulkRemindRequest(BaseModel):
    include_sixty_ninety: bool = True
    sender_name: str = "Amara Okafor (L&D and Compliance Lead)"


class RenewCertificateRequest(BaseModel):
    new_expiry_date: Optional[str] = None


class CreateCertificateRequest(BaseModel):
    employee_id: str = Field(default="EMP-160")
    employee_name: str
    employee_email: str
    role_title: str
    department: str
    manager_name: str
    manager_email: str
    certificate_name: str
    license_number: str = Field(default="LIC-2026-901")
    issuing_body: str
    skill_category: str = Field(default="Mandatory Role License")
    expiry_date: str
    bond_amount_usd: float = 0.0
    bond_end_date: str = ""


class AskAgentRequest(BaseModel):
    question: str


def _load_full_state() -> Dict[str, Any]:
    raw_certs = fetch_all_certifications()
    enriched = [enrich_certification_record(c) for c in raw_certs]
    # Sort by days_remaining ascending so expired and urgent items appear at the top
    enriched.sort(key=lambda x: (x["days_remaining"], x["id"]))
    reminders_total = count_reminders_sent()
    kpis = compute_kpi_summary(enriched, reminders_total)
    role_reqs = fetch_role_requirements()
    matrix = build_department_skills_matrix(enriched, role_reqs)
    logs = fetch_reminder_logs()
    return {
        "kpis": kpis,
        "certifications": enriched,
        "skills_matrix": matrix,
        "reminder_logs": logs,
    }


# ─── Routes ───────────────────────────────────────────────────────────────────


@app.get("/", include_in_schema=False)
def serve_index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "service": "Learning, Certification Expiry & Skills Matrix Agent",
        "agent_id": "HR-AGENT-08",
    }


# ─── Authentication (Google SSO, Email OTP, Instant Demo Sign-In) ─────────────


@app.get("/api/auth/config")
def get_auth_config():
    return {"google_client_id": GOOGLE_CLIENT_ID}


@app.post("/api/auth/google")
def auth_google_sso(payload: GoogleAuthRequest):
    try:
        return verify_google_credential(payload.credential)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@app.post("/api/auth/otp/request")
def auth_otp_request(payload: OTPRequestModel):
    try:
        return request_email_otp(payload.email)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/auth/otp/verify")
def auth_otp_verify(payload: OTPVerifyModel):
    try:
        return verify_email_otp(payload.email, payload.code)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@app.post("/api/auth/demo")
def auth_demo_signin(payload: Optional[DemoAuthModel] = None):
    persona = payload.persona if payload else "Amara Okafor"
    return create_demo_session(persona)


# ─── Certification & Skills Compliance Endpoints ──────────────────────────────


@app.get("/api/overview")
def get_dashboard_overview():
    return _load_full_state()


@app.get("/api/certifications")
def list_certifications(
    status: Optional[str] = Query(default=None),
    department: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
):
    state = _load_full_state()
    certs = state["certifications"]

    if status and status != "All":
        certs = [c for c in certs if c["status_badge"] == status]
    if department and department != "All":
        certs = [c for c in certs if c["department"].lower() == department.lower()]
    if search:
        q = search.strip().lower()
        certs = [
            c
            for c in certs
            if q in c["employee_name"].lower()
            or q in c["certificate_name"].lower()
            or q in c["issuing_body"].lower()
            or q in c["role_title"].lower()
            or q in c["department"].lower()
        ]

    return {
        "kpis": state["kpis"],
        "count": len(certs),
        "certifications": certs,
    }


@app.post("/api/certifications")
def create_certification(payload: CreateCertificateRequest):
    conn = get_db()
    cur = conn.cursor()
    issue_date_str = (date.today() - timedelta(days=30)).isoformat()
    cur.execute(
        """
        INSERT INTO certifications (
            employee_id, employee_name, employee_email, role_title, department,
            manager_name, manager_email, certificate_name, license_number,
            issuing_body, skill_category, issue_date, expiry_date,
            bond_amount_usd, bond_end_date, reminders_sent, last_reminder_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, '')
        """,
        (
            payload.employee_id,
            payload.employee_name,
            payload.employee_email,
            payload.role_title,
            payload.department,
            payload.manager_name,
            payload.manager_email,
            payload.certificate_name,
            payload.license_number,
            payload.issuing_body,
            payload.skill_category,
            issue_date_str,
            payload.expiry_date,
            payload.bond_amount_usd,
            payload.bond_end_date,
        ),
    )
    new_id = cur.lastrowid
    conn.commit()
    row = conn.execute("SELECT * FROM certifications WHERE id = ?", (new_id,)).fetchone()
    conn.close()

    enriched = enrich_certification_record(dict(row))
    state = _load_full_state()
    return {
        "created": True,
        "certification": enriched,
        "kpis": state["kpis"],
    }


@app.post("/api/certifications/{cert_id}/remind")
def send_single_renewal_reminder(cert_id: int, payload: Optional[RemindRequest] = None):
    sender = payload.sender_name if payload else "Amara Okafor (L&D and Compliance Lead)"
    conn = get_db()
    row = conn.execute("SELECT * FROM certifications WHERE id = ?", (cert_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Certification record not found.")

    enriched = enrich_certification_record(dict(row))
    notice = build_renewal_notice(enriched, sender_name=sender)
    now_str = utc_now_iso()

    conn.execute(
        """
        UPDATE certifications
        SET reminders_sent = reminders_sent + 1,
            last_reminder_at = ?
        WHERE id = ?
        """,
        (now_str, cert_id),
    )
    conn.execute(
        """
        INSERT INTO reminder_logs (
            cert_id, employee_name, employee_email, manager_name, manager_email,
            certificate_name, status_at_send, subject, body, sent_by, sent_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            cert_id,
            enriched["employee_name"],
            enriched["employee_email"],
            enriched["manager_name"],
            enriched["manager_email"],
            enriched["certificate_name"],
            enriched["status_badge"],
            notice["subject"],
            notice["body"],
            sender,
            now_str,
        ),
    )
    conn.commit()
    updated_row = conn.execute("SELECT * FROM certifications WHERE id = ?", (cert_id,)).fetchone()
    conn.close()

    state = _load_full_state()
    return {
        "sent": True,
        "message": (
            f"Renewal notice sent to {enriched['employee_name']} and Line Manager {enriched['manager_name']}."
        ),
        "notice": notice,
        "certification": enrich_certification_record(dict(updated_row)),
        "kpis": state["kpis"],
    }


@app.post("/api/certifications/remind-bulk")
def send_bulk_renewal_reminders(payload: Optional[BulkRemindRequest] = None):
    sender = payload.sender_name if payload else "Amara Okafor (L&D and Compliance Lead)"
    include_60_90 = payload.include_sixty_ninety if payload is not None else True

    target_statuses = {STATUS_EXPIRED, STATUS_EXPIRING_30}
    if include_60_90:
        target_statuses.add(STATUS_EXPIRING_60_90)

    raw_certs = fetch_all_certifications()
    enriched_all = [enrich_certification_record(c) for c in raw_certs]
    targets = [c for c in enriched_all if c["status_badge"] in target_statuses]

    conn = get_db()
    now_str = utc_now_iso()
    dispatched: List[Dict[str, Any]] = []

    for cert in targets:
        notice = build_renewal_notice(cert, sender_name=sender)
        conn.execute(
            """
            UPDATE certifications
            SET reminders_sent = reminders_sent + 1,
                last_reminder_at = ?
            WHERE id = ?
            """,
            (now_str, cert["id"]),
        )
        conn.execute(
            """
            INSERT INTO reminder_logs (
                cert_id, employee_name, employee_email, manager_name, manager_email,
                certificate_name, status_at_send, subject, body, sent_by, sent_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cert["id"],
                cert["employee_name"],
                cert["employee_email"],
                cert["manager_name"],
                cert["manager_email"],
                cert["certificate_name"],
                cert["status_badge"],
                notice["subject"],
                notice["body"],
                sender,
                now_str,
            ),
        )
        dispatched.append(
            {
                "cert_id": cert["id"],
                "employee_name": cert["employee_name"],
                "manager_name": cert["manager_name"],
                "certificate_name": cert["certificate_name"],
                "status_badge": cert["status_badge"],
                "subject": notice["subject"],
            }
        )

    conn.commit()
    conn.close()

    state = _load_full_state()
    return {
        "sent": True,
        "dispatched_count": len(dispatched),
        "message": f"Sent {len(dispatched)} renewal notices to employees and their line managers.",
        "dispatched": dispatched,
        "kpis": state["kpis"],
    }


@app.post("/api/certifications/{cert_id}/renew")
def mark_certificate_renewed(cert_id: int, payload: Optional[RenewCertificateRequest] = None):
    conn = get_db()
    row = conn.execute("SELECT * FROM certifications WHERE id = ?", (cert_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Certification record not found.")

    new_exp = (
        payload.new_expiry_date
        if (payload and payload.new_expiry_date)
        else (date.today() + timedelta(days=365)).isoformat()
    )
    today_iso = date.today().isoformat()
    conn.execute(
        """
        UPDATE certifications
        SET issue_date = ?, expiry_date = ?
        WHERE id = ?
        """,
        (today_iso, new_exp, cert_id),
    )
    conn.commit()
    updated_row = conn.execute("SELECT * FROM certifications WHERE id = ?", (cert_id,)).fetchone()
    conn.close()

    state = _load_full_state()
    enriched = enrich_certification_record(dict(updated_row))
    return {
        "renewed": True,
        "message": f"{enriched['employee_name']}'s '{enriched['certificate_name']}' renewed until {new_exp}.",
        "certification": enriched,
        "kpis": state["kpis"],
    }


@app.get("/api/skills-matrix")
def get_role_skills_matrix():
    state = _load_full_state()
    return {
        "kpis": state["kpis"],
        "skills_matrix": state["skills_matrix"],
    }


@app.get("/api/reminders")
def get_reminder_history():
    logs = fetch_reminder_logs()
    return {
        "count": len(logs),
        "reminder_logs": logs,
    }


@app.post("/api/agent/ask")
def ask_certification_agent(payload: AskAgentRequest):
    state = _load_full_state()
    return answer_certification_question(
        payload.question,
        state["certifications"],
        state["skills_matrix"],
        state["kpis"],
    )


@app.get("/api/audit-report")
def get_compliance_audit_report():
    state = _load_full_state()
    return {
        "report_title": "1-Page Certification Compliance Audit Report",
        "generated_date": date.today().isoformat(),
        "prepared_by": "Certification & Skills Agent — People & Compliance Operations",
        "kpis": state["kpis"],
        "skills_matrix": state["skills_matrix"],
        "certifications": state["certifications"],
        "recent_reminders": state["reminder_logs"][:8],
    }


@app.get("/api/audit-report/pdf")
def download_compliance_audit_pdf():
    state = _load_full_state()
    pdf_bytes = generate_compliance_audit_pdf_bytes(
        state["kpis"],
        state["certifications"],
        state["skills_matrix"],
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="Certification_Compliance_Audit_Report.pdf"'
        },
    )


@app.get("/api/audit-report/csv")
def download_compliance_csv():
    state = _load_full_state()
    csv_str = generate_compliance_csv_string(state["certifications"])
    return Response(
        content=csv_str.encode("utf-8"),
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="Certification_License_Tracker.csv"'
        },
    )


@app.post("/api/demo/reset")
def reset_demo_state():
    seed_demo_data(force_reset=True)
    return _load_full_state()
