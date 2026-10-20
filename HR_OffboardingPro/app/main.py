"""FastAPI application for HR Offboarding Pro — Multi-Agent Employee Exit, Clearance & Final Settlement Platform."""

from contextlib import asynccontextmanager
import json
import os
from typing import Dict
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .agents import ClearanceESignAgent, OffboardingOrchestrator
from .auth_service import (
    GOOGLE_CLIENT_ID,
    create_demo_session,
    request_email_otp,
    verify_email_otp,
    verify_google_credential,
)
from .database import get_db, init_db, utc_now_iso
from .models import (
    BatchExitCreate,
    EmployeeExitCreate,
    ROLE_OFFBOARDING_STEPS,
    RoleCategory,
    SMTPConfigUpdate,
     SUBAGENT_METADATA,
    SignActionRequest,
    TaskAdvanceRequest,
    TaskBlockerRequest,
    TemplateUpdate,
)
from .pdf_generator import (
    calculate_final_settlement,
    generate_certificate_pdf_bytes,
    generate_clearance_pdf_bytes,
)
from .seed import seed_demo_data_if_empty


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    seed_demo_data_if_empty()
    yield


app = FastAPI(
    title="HR Offboarding Pro — Multi-Agent Employee Exit & Clearance Platform",
    description="Role-aware employee exit orchestration, reverse de-provisioning agents, final settlement calculator, and Certificate of Service issuance.",
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
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class GoogleAuthRequest(BaseModel):
    credential: str


class OTPRequestModel(BaseModel):
    email: str


class OTPVerifyModel(BaseModel):
    email: str
    code: str


class DemoAuthModel(BaseModel):
    persona: str = "Elena Rostova"


class SettlementPreviewRequest(BaseModel):
    compensation_amount: float = 140000.0
    compensation_period: str = "per year"
    days_worked_final_month: int = 18
    unused_leave_days: float = 6.0
    asset_deduction: float = 0.0


@app.get("/", include_in_schema=False)
def serve_dashboard():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/sign/{signing_token}", include_in_schema=False)
def serve_signing_portal(signing_token: str):
    return FileResponse(os.path.join(STATIC_DIR, "sign.html"))


@app.get("/api/health")
def health_check():
    return {"status": "healthy", "service": "HR Offboarding Pro Agent"}


# ─── Single Sign-On (SSO) & Work Email Authentication ─────────────────────────

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
def auth_demo_session(payload: DemoAuthModel = DemoAuthModel()):
    return create_demo_session(payload.persona)


# ─── Executive Overview & HR Action Center ───────────────────────────────────

@app.get("/api/overview")
def get_overview():
    candidates = OffboardingOrchestrator.list_all_candidates()
    total = len(candidates)
    awaiting_sig = sum(
        1 for c in candidates if c["offer"] and c["offer"]["status"] in ("SENT", "VIEWED")
    )
    in_clearance = sum(
        1
        for c in candidates
        if c["offboarding_status"] in ("CLEARANCE_IN_PROGRESS", "CLEARANCE_SIGNED")
        and c["overall_progress_pct"] < 100
    )
    fully_offboarded = sum(
        1
        for c in candidates
        if c["offboarding_status"] == "OFFBOARDED" or c["overall_progress_pct"] == 100
    )
    disputed = sum(
        1 for c in candidates if c["offer"] and c["offer"]["status"] == "DECLINED"
    )
    blocked_tasks_count = sum(
        1 for c in candidates for t in c["tasks"] if t["status"] == "BLOCKED"
    )
    total_settlement_value = round(
        sum(c["settlement"]["net_settlement"] for c in candidates), 2
    )

    role_counts = {
        "INTERN": sum(1 for c in candidates if c["role_category"] == "INTERN"),
        "TRAINEE": sum(1 for c in candidates if c["role_category"] == "TRAINEE"),
        "EMPLOYEE": sum(1 for c in candidates if c["role_category"] == "EMPLOYEE"),
    }

    action_items = []
    for c in candidates:
        if c["offer"] and c["offer"]["status"] == "DECLINED":
            action_items.append(
                {
                    "type": "SETTLEMENT_DISPUTED",
                    "severity": "HIGH",
                    "candidate_id": c["id"],
                    "candidate_name": c["full_name"],
                    "role_category": c["role_category"],
                    "job_title": c["job_title"],
                    "department": c["department"],
                    "title": f"Final Settlement Query Raised by {c['full_name']}",
                    "reason": c["offer"].get("decline_reason")
                    or "Requested recalculation of unused leave encashment",
                    "timestamp": c["offer"].get("responded_at") or c["updated_at"],
                }
            )
        for t in c["tasks"]:
            if t["status"] == "BLOCKED":
                action_items.append(
                    {
                        "type": "TASK_BLOCKED",
                        "severity": "MEDIUM",
                        "candidate_id": c["id"],
                        "candidate_name": c["full_name"],
                        "role_category": c["role_category"],
                        "job_title": c["job_title"],
                        "department": t["department"],
                        "task_id": t["id"],
                        "agent_name": t["agent_name"],
                        "title": f"{t['agent_name']} Blocked for {c['full_name']}",
                        "reason": t["blocker_reason"] or "Unreturned company equipment requires attention",
                        "timestamp": t["updated_at"],
                    }
                )

    with get_db() as conn:
        recent_events = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM agent_events ORDER BY id DESC LIMIT 40"
            ).fetchall()
        ]
        recent_emails = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM email_notifications ORDER BY id DESC LIMIT 30"
            ).fetchall()
        ]

    role_matrix = {
        role.value: [step.value for step in steps]
        for role, steps in ROLE_OFFBOARDING_STEPS.items()
    }
    subagents = {
        k.value: {
            **v,
            "depends_on": v["depends_on"].value if v["depends_on"] else None,
        }
        for k, v in SUBAGENT_METADATA.items()
    }

    return {
        "kpis": {
            "total_exiting": total,
            "total_candidates": total,
            "awaiting_signature": awaiting_sig,
            "clearance_active": in_clearance,
            "provisioning_active": in_clearance,
            "fully_offboarded": fully_offboarded,
            "fully_onboarded": fully_offboarded,
            "disputed_settlements": disputed,
            "declined_offers": disputed,
            "blocked_tasks_count": blocked_tasks_count,
            "action_required_count": len(action_items),
            "total_final_settlement_value": total_settlement_value,
            "role_counts": role_counts,
        },
        "employees": candidates,
        "candidates": candidates,
        "action_items": action_items,
        "role_matrix": role_matrix,
        "subagent_metadata": subagents,
        "recent_events": recent_events,
        "recent_emails": recent_emails,
    }


# ─── Exiting Employees & Final Settlement Endpoints ──────────────────────────

@app.post("/api/employees/calculate-settlement")
def preview_final_settlement(payload: SettlementPreviewRequest):
    return calculate_final_settlement(
        compensation_amount=payload.compensation_amount,
        compensation_period=payload.compensation_period,
        days_worked_final_month=payload.days_worked_final_month,
        unused_leave_days=payload.unused_leave_days,
        asset_deduction=payload.asset_deduction,
    )


@app.get("/api/employees")
@app.get("/api/candidates")
def list_employees():
    return OffboardingOrchestrator.list_all_candidates()


@app.get("/api/employees/{candidate_id}")
@app.get("/api/candidates/{candidate_id}")
def get_employee(candidate_id: int):
    detail = OffboardingOrchestrator.get_candidate_detail(candidate_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Exiting employee record not found")
    return detail


@app.post("/api/employees")
@app.post("/api/candidates")
def create_employee_exit(payload: EmployeeExitCreate):
    return ClearanceESignAgent.create_employee_exit_and_send_clearance(payload)


@app.post("/api/employees/batch")
@app.post("/api/candidates/batch")
def create_batch_employee_exits(payload: BatchExitCreate):
    items = payload.employees or payload.candidates or []
    created = []
    for item in items:
        created.append(ClearanceESignAgent.create_employee_exit_and_send_clearance(item))
    return {"created_count": len(created), "employees": created, "candidates": created}


# ─── Official PDF Endpoints (Clearance Statement & Certificate of Service) ───

@app.get("/api/employees/{candidate_id}/clearance-pdf")
@app.get("/api/offers/{candidate_id}/pdf")
def download_clearance_pdf(candidate_id: int):
    with get_db() as conn:
        cand = conn.execute(
            "SELECT * FROM candidates WHERE id = ?", (candidate_id,)
        ).fetchone()
        offer = conn.execute(
            "SELECT * FROM offer_letters WHERE candidate_id = ?", (candidate_id,)
        ).fetchone()
        if not cand or not offer:
            raise HTTPException(status_code=404, detail="Clearance statement not found")
        tpl = conn.execute(
            "SELECT * FROM offer_templates WHERE role_category = ?",
            (cand["role_category"],),
        ).fetchone()
        tasks = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM provisioning_tasks WHERE candidate_id = ? ORDER BY id ASC",
                (candidate_id,),
            ).fetchall()
        ]
        pdf_bytes = generate_clearance_pdf_bytes(
            dict(cand), dict(offer), dict(tpl), tasks=tasks
        )

    safe_name = cand["full_name"].replace(" ", "_")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="Final_Clearance_Statement_{safe_name}.pdf"'
        },
    )


@app.get("/api/employees/{candidate_id}/certificate-pdf")
def download_certificate_of_service_pdf(candidate_id: int):
    with get_db() as conn:
        cand = conn.execute(
            "SELECT * FROM candidates WHERE id = ?", (candidate_id,)
        ).fetchone()
        offer = conn.execute(
            "SELECT * FROM offer_letters WHERE candidate_id = ?", (candidate_id,)
        ).fetchone()
        if not cand:
            raise HTTPException(status_code=404, detail="Employee record not found")
        tpl = conn.execute(
            "SELECT * FROM offer_templates WHERE role_category = ?",
            (cand["role_category"],),
        ).fetchone()
        pdf_bytes = generate_certificate_pdf_bytes(
            dict(cand),
            dict(offer) if offer else None,
            dict(tpl) if tpl else None,
        )

    safe_name = cand["full_name"].replace(" ", "_")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="Certificate_of_Service_{safe_name}.pdf"'
        },
    )


# ─── Employee Clearance E-Sign Portal Endpoints ──────────────────────────────

@app.get("/api/sign/{signing_token}")
def get_signing_portal_data(signing_token: str):
    bundle = ClearanceESignAgent.mark_viewed(signing_token)
    if not bundle:
        raise HTTPException(status_code=404, detail="Invalid or expired clearance link")
    with get_db() as conn:
        tpl = conn.execute(
            "SELECT * FROM offer_templates WHERE role_category = ?",
            (bundle["role_category"],),
        ).fetchone()
        template_dict = dict(tpl) if tpl else {}
        if "terms_json" in template_dict:
            template_dict["terms"] = json.loads(template_dict["terms_json"])
        if "benefits_json" in template_dict:
            template_dict["benefits"] = json.loads(template_dict["benefits_json"])
    return {
        "employee": bundle,
        "candidate": bundle,
        "template": template_dict,
    }


@app.post("/api/sign/{signing_token}/accept")
def accept_clearance_endpoint(signing_token: str, payload: SignActionRequest):
    try:
        return ClearanceESignAgent.accept_clearance(
            signing_token,
            payload.signature_name or "",
            forwarding_address=payload.forwarding_address,
            handover_confirmed=payload.handover_confirmed,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/sign/{signing_token}/dispute")
@app.post("/api/sign/{signing_token}/decline")
def dispute_clearance_endpoint(signing_token: str, payload: SignActionRequest):
    try:
        return ClearanceESignAgent.dispute_clearance(
            signing_token, payload.reason or ""
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ─── Reverse De-Provisioning Subagent Task Controls ──────────────────────────

@app.post("/api/tasks/{task_id}/advance")
def advance_task_endpoint(
    task_id: int, payload: TaskAdvanceRequest = TaskAdvanceRequest()
):
    result = OffboardingOrchestrator.advance_task_stage(task_id, payload.notes)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/api/tasks/{task_id}/block")
def block_task_endpoint(task_id: int, payload: TaskBlockerRequest):
    return OffboardingOrchestrator.flag_task_blocker(task_id, payload.blocker_reason)


@app.post("/api/employees/{candidate_id}/advance-all")
@app.post("/api/candidates/{candidate_id}/advance-all")
def advance_all_candidate_tasks(candidate_id: int):
    detail = OffboardingOrchestrator.get_candidate_detail(candidate_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Exiting employee not found")

    # Advance non-EMAIL tasks first (INSURANCE, UBER, LAPTOP) so LAPTOP completion unlocks EMAIL
    for task in detail["tasks"]:
        if task["status"] in ("IN_PROGRESS", "BLOCKED") and task["task_type"] != "EMAIL":
            OffboardingOrchestrator.advance_task_stage(task["id"])

    detail = OffboardingOrchestrator.get_candidate_detail(candidate_id)
    for task in detail["tasks"]:
        if task["status"] == "IN_PROGRESS" and task["task_type"] == "EMAIL":
            OffboardingOrchestrator.advance_task_stage(task["id"])

    return OffboardingOrchestrator.get_candidate_detail(candidate_id)


@app.get("/api/agents/board")
def get_subagents_board():
    """Returns all 4 reverse de-provisioning subagents and their live tasks across departments."""
    candidates = OffboardingOrchestrator.list_all_candidates()
    board: Dict[str, dict] = {}
    for task_type, meta in SUBAGENT_METADATA.items():
        board[task_type.value] = {
            "task_type": task_type.value,
            "agent_name": meta["agent_name"],
            "title": meta["title"],
            "department": meta["department"],
            "icon": meta["icon"],
            "description": meta["description"],
            "stages": meta["stages"],
            "applicable_roles": meta["applicable_roles"],
            "depends_on": meta["depends_on"].value if meta["depends_on"] else None,
            "tasks": [],
        }

    for c in candidates:
        for t in c["tasks"]:
            t_type = t["task_type"]
            if t_type in board:
                board[t_type]["tasks"].append(
                    {
                        **t,
                        "candidate_name": c["full_name"],
                        "candidate_role": c["role_category"],
                        "job_title": c["job_title"],
                        "last_working_day": c.get("last_working_day") or c["start_date"],
                        "start_date": c["start_date"],
                    }
                )
    return list(board.values())


# ─── Settings, Templates & Activity History ──────────────────────────────────

@app.get("/api/settings/smtp")
def get_smtp_settings():
    with get_db() as conn:
        row = conn.execute("SELECT * FROM smtp_settings WHERE id = 1").fetchone()
        return dict(row) if row else {}


@app.put("/api/settings/smtp")
def update_smtp_settings(payload: SMTPConfigUpdate):
    now = utc_now_iso()
    with get_db() as conn:
        conn.execute(
            """
            UPDATE smtp_settings
            SET smtp_host = ?, smtp_port = ?, smtp_user = ?, smtp_password = ?,
                from_email = ?, from_name = ?, enabled = ?, updated_at = ?
            WHERE id = 1
            """,
            (
                payload.smtp_host,
                payload.smtp_port,
                payload.smtp_user,
                payload.smtp_password,
                payload.from_email,
                payload.from_name,
                1 if payload.enabled else 0,
                now,
            ),
        )
        row = conn.execute("SELECT * FROM smtp_settings WHERE id = 1").fetchone()
        return dict(row)


@app.get("/api/settings/templates")
def get_all_templates():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM offer_templates").fetchall()
        out = {}
        for r in rows:
            d = dict(r)
            d["terms"] = json.loads(d["terms_json"])
            d["benefits"] = json.loads(d["benefits_json"])
            out[d["role_category"]] = d
        return out


@app.put("/api/settings/templates/{role_category}")
def update_template(role_category: RoleCategory, payload: TemplateUpdate):
    now = utc_now_iso()
    with get_db() as conn:
        conn.execute(
            """
            UPDATE offer_templates
            SET company_name = ?, title = ?, intro_text = ?, terms_json = ?,
                benefits_json = ?, footer_text = ?, updated_at = ?
            WHERE role_category = ?
            """,
            (
                payload.company_name,
                payload.title,
                payload.intro_text,
                json.dumps(payload.terms_json),
                json.dumps(payload.benefits_json),
                payload.footer_text,
                now,
                role_category.value,
            ),
        )
    return get_all_templates()[role_category.value]


@app.get("/api/notifications")
def list_notifications():
    with get_db() as conn:
        emails = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM email_notifications ORDER BY id DESC LIMIT 50"
            ).fetchall()
        ]
        events = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM agent_events ORDER BY id DESC LIMIT 60"
            ).fetchall()
        ]
    return {"emails": emails, "events": events}


@app.post("/api/demo/reset")
def reset_demo_data():
    with get_db() as conn:
        conn.executescript(
            """
            DELETE FROM email_notifications;
            DELETE FROM agent_events;
            DELETE FROM provisioning_tasks;
            DELETE FROM offer_letters;
            DELETE FROM candidates;
            """
        )
    seed_demo_data_if_empty()
    return {"status": "reset_complete"}
