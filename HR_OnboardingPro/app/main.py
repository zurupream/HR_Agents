"""FastAPI application for the Agentic HR Onboarding Web App."""

from datetime import datetime, timezone
import json
import os
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.agents import OfferESignAgent, OnboardingOrchestrator, log_agent_event
from app.auth_service import (
    GOOGLE_CLIENT_ID,
    create_demo_session,
    request_email_otp,
    verify_email_otp,
    verify_google_credential,
)
from app.database import (
    DEFAULT_OFFER_TEMPLATES,
    dict_from_row,
    get_conn,
    init_db,
    utc_now_iso,
)
from app.email_service import (
    dispatch_stakeholder_email,
    get_smtp_settings,
    test_smtp_connection,
    update_smtp_settings,
)
from app.models import (
    BatchOnboardingRequest,
    DocuSealWebhookPayload,
    OfferAcceptRequest,
    OfferDeclineRequest,
    OfferTemplateUpdateRequest,
    PositionCreateRequest,
    ROLE_ONBOARDING_STEPS,
    SMTPConfigRequest,
    SUBAGENT_METADATA,
    TaskStatus,
    parse_cc_emails,
)
from app.pdf_generator import (
    generate_offer_pdf,
    get_all_offer_templates_map,
    get_offer_template,
    normalize_template_row,
    render_template_text,
)
from app.seed import seed_demo_data

app = FastAPI(
    title="Sybyl People — HR Onboarding",
    description="Offer Management, Candidate Signatures & Onboarding Tracking",
    version="1.0.0",
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


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    default_base = os.environ.get("PUBLIC_BASE_URL", "http://localhost:8080")
    seed_demo_data(force_reset=False, base_url=default_base)


def _get_public_base_url(request: Request) -> str:
    env_url = os.environ.get("PUBLIC_BASE_URL")
    if env_url:
        return env_url.rstrip("/")
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme or "https"
    host = (
        request.headers.get("x-forwarded-host")
        or request.headers.get("host")
        or request.url.netloc
    )
    if host:
        return f"{proto}://{host}".rstrip("/")
    return str(request.base_url).rstrip("/")


def _enrich_candidate(cand: Dict[str, Any], conn) -> Dict[str, Any]:
    pos = dict_from_row(
        conn.execute("SELECT * FROM positions WHERE id = ?", (cand["position_id"],)).fetchone()
    )
    offer = dict_from_row(
        conn.execute("SELECT * FROM offer_letters WHERE candidate_id = ?", (cand["id"],)).fetchone()
    )
    tasks_raw = [
        dict_from_row(r)
        for r in conn.execute(
            "SELECT * FROM provisioning_tasks WHERE candidate_id = ? ORDER BY rowid ASC",
            (cand["id"],),
        ).fetchall()
    ]

    tasks = []
    for t in tasks_raw:
        meta = json.loads(t.get("metadata_json") or "{}")
        sub_meta = SUBAGENT_METADATA.get(t["task_type"], {})
        stages = sub_meta.get("stages", [])
        pct = 0
        if t["status"] == TaskStatus.COMPLETED.value:
            pct = 100
        elif stages:
            pct = int(round((t["current_stage_idx"] / max(len(stages) - 1, 1)) * 100))
        t["progress_pct"] = pct
        t["stages"] = stages
        t["artifacts"] = meta.get("artifacts", {})
        t["current_stage_label"] = t.get("stage_label")
        t["target_system"] = sub_meta.get("department", "")
        tasks.append(t)

    role_steps = ROLE_ONBOARDING_STEPS.get(cand["role_category"], ["EMAIL"])
    completed_tasks = sum(1 for t in tasks if t["status"] == TaskStatus.COMPLETED.value)
    blocked_tasks = sum(1 for t in tasks if t["status"] == TaskStatus.BLOCKED.value)
    total_role_steps = len(role_steps)

    # Calculate 4-milestone onboarding tracker status
    offer_status = offer["status"] if offer else "SENT"
    if offer_status in ("DECLINED", "LAPSED"):
        amazon_step = 1
        overall_pct = 15
    elif offer_status in ("SENT", "VIEWED"):
        amazon_step = 1
        overall_pct = 25 if offer_status == "VIEWED" else 15
    elif cand["overall_stage"] == "COMPLETED" or (tasks and completed_tasks == total_role_steps):
        amazon_step = 4
        overall_pct = 100
    else:
        amazon_step = 3
        overall_pct = 50 + int(round((completed_tasks / max(total_role_steps, 1)) * 45))

    # Calculate hours until offer expiry
    hours_until_expiry = None
    is_expiring_soon = False
    if offer and offer.get("expires_at"):
        try:
            exp_dt = datetime.strptime(offer["expires_at"], "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc
            )
            diff_hours = (exp_dt - datetime.now(timezone.utc)).total_seconds() / 3600.0
            hours_until_expiry = round(diff_hours, 1)
            if offer_status in ("SENT", "VIEWED") and 0 < diff_hours <= 24:
                is_expiring_soon = True
        except Exception:
            pass

    if cand.get("cc_emails"):
        cc_list = parse_cc_emails(cand.get("cc_emails"), cand.get("hod_email"))
    else:
        cc_list = parse_cc_emails(cand.get("hr_email"), cand.get("hod_email"), cand.get("ceo_email"))
    cc_emails_display = "; ".join(cc_list)

    tpl_norm = get_offer_template(cand["role_category"])

    rendered_template = {
        "role_category": cand["role_category"],
        "title": render_template_text(tpl_norm.get("title", "Official Offer of Appointment"), cand, pos or {}, offer or {}),
        "intro_text": render_template_text(tpl_norm.get("intro_text", ""), cand, pos or {}, offer or {}),
        "terms_text": render_template_text(tpl_norm.get("terms_text", ""), cand, pos or {}, offer or {}),
        "closing_text": render_template_text(tpl_norm.get("closing_text", ""), cand, pos or {}, offer or {}),
    }

    return {
        **cand,
        "cc_emails_display": cc_emails_display,
        "cc_list": cc_list,
        "compensation_package": cand.get("compensation"),
        "position": pos,
        "offer": offer,
        "offer_template": rendered_template,
        "signing_url": f"/sign/{offer['signing_token']}" if offer else None,
        "role_required_steps": role_steps,
        "tasks": tasks,
        "completed_tasks": completed_tasks,
        "total_role_steps": total_role_steps,
        "blocked_tasks": blocked_tasks,
        "amazon_step": amazon_step,
        "overall_pct": overall_pct,
        "hours_until_expiry": hours_until_expiry,
        "is_expiring_soon": is_expiring_soon,
    }


@app.get("/", response_class=HTMLResponse)
def serve_index() -> HTMLResponse:
    index_path = os.path.join(STATIC_DIR, "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.get("/sign/{signing_token}", response_class=HTMLResponse)
def serve_signing_portal(signing_token: str) -> HTMLResponse:
    sign_path = os.path.join(STATIC_DIR, "sign.html")
    with open(sign_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


# ---------------------------------------------------------------------------
# Enterprise SSO, Google OAuth 2.0, Work Email OTP & Instant Demo Auth APIs
# ---------------------------------------------------------------------------


class GoogleAuthRequest(BaseModel):
    credential: str


class EmailOtpRequest(BaseModel):
    email: str


class EmailOtpVerifyRequest(BaseModel):
    email: str
    code: str


class DemoAuthRequest(BaseModel):
    persona: Optional[str] = "HR Director"


@app.get("/api/auth/config")
def get_auth_config() -> Dict[str, Any]:
    return {"google_client_id": GOOGLE_CLIENT_ID}


@app.post("/api/auth/google")
def auth_google(req: GoogleAuthRequest) -> Dict[str, Any]:
    try:
        return verify_google_credential(req.credential)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@app.post("/api/auth/otp/request")
def auth_otp_request(req: EmailOtpRequest) -> Dict[str, Any]:
    try:
        return request_email_otp(req.email)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/auth/otp/verify")
def auth_otp_verify(req: EmailOtpVerifyRequest) -> Dict[str, Any]:
    try:
        return verify_email_otp(req.email, req.code)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@app.post("/api/auth/demo")
def auth_demo(req: Optional[DemoAuthRequest] = None) -> Dict[str, Any]:
    persona = req.persona if req else "HR Director"
    return create_demo_session(persona=persona)


@app.get("/api/overview")
def get_overview() -> Dict[str, Any]:
    conn = get_conn()
    positions = [
        dict_from_row(r)
        for r in conn.execute("SELECT * FROM positions ORDER BY created_at ASC").fetchall()
    ]
    candidates_raw = [
        dict_from_row(r)
        for r in conn.execute("SELECT * FROM candidates ORDER BY created_at DESC").fetchall()
    ]
    candidates = [_enrich_candidate(c, conn) for c in candidates_raw]

    notif_count = conn.execute("SELECT COUNT(*) as cnt FROM notification_logs").fetchone()["cnt"]
    recent_events_raw = conn.execute(
        "SELECT * FROM agent_audit_events ORDER BY created_at DESC LIMIT 35"
    ).fetchall()
    conn.close()

    recent_events = []
    for r in recent_events_raw:
        d = dict_from_row(r)
        d["details"] = json.loads(d.get("details_json") or "{}")
        recent_events.append(d)

    # Build "What HR Should Know" Proactive Intelligence sections
    expiring_soon_offers = [c for c in candidates if c["is_expiring_soon"]]
    backfill_alerts = [
        c for c in candidates if c["offer"] and c["offer"]["status"] in ("DECLINED", "LAPSED")
    ]

    sla_blockers = []
    for c in candidates:
        for t in c["tasks"]:
            if t["status"] == TaskStatus.BLOCKED.value:
                sla_blockers.append(
                    {
                        "task_id": t["id"],
                        "task_type": t["task_type"],
                        "agent_name": t["agent_name"],
                        "blocker_reason": t["blocker_reason"],
                        "candidate_id": c["id"],
                        "candidate_name": c["full_name"],
                        "role_category": c["role_category"],
                        "position_title": c["position"]["title"] if c["position"] else "",
                        "hod_name": c["position"]["hod_name"] if c["position"] else "",
                        "joining_date": c["joining_date"],
                    }
                )

    day1_readiness = [
        c
        for c in candidates
        if c["offer"] and c["offer"]["status"] == "ACCEPTED"
    ]
    day1_readiness.sort(key=lambda x: x["joining_date"])

    # Position Fill Summary
    position_fill_summary = []
    for p in positions:
        pos_cands = [c for c in candidates if c["position_id"] == p["id"]]
        sent_cnt = sum(1 for c in pos_cands if c["offer"] and c["offer"]["status"] in ("SENT", "VIEWED"))
        accepted_cnt = sum(1 for c in pos_cands if c["offer"] and c["offer"]["status"] == "ACCEPTED")
        declined_cnt = sum(1 for c in pos_cands if c["offer"] and c["offer"]["status"] == "DECLINED")
        lapsed_cnt = sum(1 for c in pos_cands if c["offer"] and c["offer"]["status"] == "LAPSED")
        ready_cnt = sum(1 for c in pos_cands if c["overall_stage"] == "COMPLETED")
        open_slots = max(p["headcount_target"] - accepted_cnt, 0)
        position_fill_summary.append(
            {
                **p,
                "total_offers": len(pos_cands),
                "awaiting_signature": sent_cnt,
                "accepted": accepted_cnt,
                "declined": declined_cnt,
                "lapsed": lapsed_cnt,
                "day1_ready": ready_cnt,
                "open_slots": open_slots,
                "needs_attention": (declined_cnt + lapsed_cnt) > 0 and open_slots > 0,
            }
        )

    kpis = {
        "total_candidates": len(candidates),
        "awaiting_signature": sum(
            1 for c in candidates if c["offer"] and c["offer"]["status"] in ("SENT", "VIEWED")
        ),
        "accepted_total": sum(
            1 for c in candidates if c["offer"] and c["offer"]["status"] == "ACCEPTED"
        ),
        "day1_ready": sum(1 for c in candidates if c["overall_stage"] == "COMPLETED"),
        "provisioning_in_progress": sum(
            1 for c in candidates if c["overall_stage"] == "PROVISIONING"
        ),
        "declined_total": sum(
            1 for c in candidates if c["offer"] and c["offer"]["status"] == "DECLINED"
        ),
        "lapsed_total": sum(
            1 for c in candidates if c["offer"] and c["offer"]["status"] == "LAPSED"
        ),
        "active_blockers": len(sla_blockers),
        "expiring_soon_count": len(expiring_soon_offers),
        "notifications_sent": notif_count,
    }

    templates_map = get_all_offer_templates_map()

    smtp_cfg = get_smtp_settings()
    return {
        "kpis": kpis,
        "positions": position_fill_summary,
        "candidates": candidates,
        "hr_intelligence": {
            "expiring_soon_offers": expiring_soon_offers,
            "backfill_alerts": backfill_alerts,
            "sla_blockers": sla_blockers,
            "day1_readiness": day1_readiness,
        },
        "recent_agent_events": recent_events,
        "role_matrix": ROLE_ONBOARDING_STEPS,
        "subagent_catalog": SUBAGENT_METADATA,
        "offer_templates": templates_map,
        "smtp_status": {
            "sender_email": smtp_cfg.get("sender_email"),
            "live_mode_enabled": bool(smtp_cfg.get("live_mode_enabled")),
            "has_app_password": bool(smtp_cfg.get("has_app_password")),
            "default_cc_emails": smtp_cfg.get("default_cc_emails") or "hr@sybyl.com; ceo@sybyl.com",
        },
    }


@app.get("/api/positions")
def list_positions() -> List[Dict[str, Any]]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM positions ORDER BY created_at ASC").fetchall()
    conn.close()
    return [dict_from_row(r) for r in rows]


@app.post("/api/positions")
def create_position(req: PositionCreateRequest) -> Dict[str, Any]:
    import uuid

    pos_id = f"pos-{uuid.uuid4().hex[:8]}"
    now = utc_now_iso()
    conn = get_conn()
    conn.execute(
        """
        INSERT INTO positions (
            id, title, department, hod_name, hod_email,
            headcount_target, location, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'OPEN', ?)
        """,
        (
            pos_id,
            req.title,
            req.department,
            req.hod_name,
            req.hod_email,
            req.headcount_target,
            req.location,
            now,
        ),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM positions WHERE id = ?", (pos_id,)).fetchone()
    conn.close()
    return dict_from_row(row)


@app.post("/api/offers/batch")
def dispatch_batch_offers(req: BatchOnboardingRequest, request: Request) -> Dict[str, Any]:
    if not req.candidates:
        raise HTTPException(status_code=400, detail="At least one candidate is required")
    base_url = _get_public_base_url(request)
    try:
        return OfferESignAgent.create_batch_offers(req, base_url=base_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/sign/{signing_token}")
def get_signing_portal_details(signing_token: str) -> Dict[str, Any]:
    conn = get_conn()
    offer_row = conn.execute(
        "SELECT * FROM offer_letters WHERE signing_token = ?", (signing_token,)
    ).fetchone()
    if not offer_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Offer signing token not found")
    offer = dict_from_row(offer_row)

    # Mark as VIEWED if first time opening while SENT
    if offer["status"] == "SENT":
        now = utc_now_iso()
        conn.execute(
            "UPDATE offer_letters SET status = 'VIEWED', viewed_at = ? WHERE signing_token = ?",
            (now, signing_token),
        )
        conn.commit()
        offer["status"] = "VIEWED"
        offer["viewed_at"] = now

    cand = _enrich_candidate(
        dict_from_row(
            conn.execute("SELECT * FROM candidates WHERE id = ?", (offer["candidate_id"],)).fetchone()
        ),
        conn,
    )
    conn.close()
    return cand


@app.post("/api/sign/{signing_token}/accept")
def accept_offer_endpoint(signing_token: str, req: OfferAcceptRequest) -> Dict[str, Any]:
    try:
        return OfferESignAgent.accept_offer(
            signing_token=signing_token,
            signer_name=req.signer_name,
            signature_data=req.signature_data,
            signature_type=req.signature_type,
            comments=req.comments,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/sign/{signing_token}/decline")
def decline_offer_endpoint(signing_token: str, req: OfferDeclineRequest) -> Dict[str, Any]:
    try:
        return OfferESignAgent.decline_offer(
            signing_token=signing_token,
            decline_reason=req.decline_reason,
            comments=req.comments,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/candidates/{candidate_id}/lapse")
def trigger_offer_lapse(candidate_id: str) -> Dict[str, Any]:
    try:
        return OfferESignAgent.lapse_offer(candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.post("/api/candidates/{candidate_id}/nudge")
def nudge_candidate_offer(candidate_id: str, request: Request) -> Dict[str, Any]:
    conn = get_conn()
    cand_row = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    if not cand_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Candidate not found")
    cand = dict_from_row(cand_row)
    offer = dict_from_row(
        conn.execute("SELECT * FROM offer_letters WHERE candidate_id = ?", (candidate_id,)).fetchone()
    )
    pos = dict_from_row(
        conn.execute("SELECT * FROM positions WHERE id = ?", (cand["position_id"],)).fetchone()
    )
    conn.close()

    base_url = _get_public_base_url(request)
    signing_url = f"{base_url}/sign/{offer['signing_token']}"
    cc_list = parse_cc_emails(
        cand.get("cc_emails"), cand.get("hr_email"), cand.get("hod_email"), cand.get("ceo_email")
    )
    cc_str = "; ".join(cc_list)

    log_agent_event(
        candidate_id=candidate_id,
        agent_name="Offer Management",
        event_type="OFFER_REMINDER_SENT",
        message=f"Sent offer reminder to {cand['full_name']} (CC: {cc_str}) — Offer valid until {offer['expires_at'][:10]}.",
        details={"signing_url": signing_url, "expires_at": offer["expires_at"], "cc": cc_list},
    )

    notif = dispatch_stakeholder_email(
        candidate_id=candidate_id,
        event_type="OFFER_REMINDER",
        subject=f"[Reminder: Offer Expiring Soon] {pos['title']} — {cand['full_name']}",
        recipient_to=cand["personal_email"],
        recipients_cc=cc_list,
        body_html=f"""
        <div style="font-family:-apple-system,BlinkMacSystemFont,'SF Pro Text','Helvetica Neue',Arial,sans-serif;padding:20px;border:1px solid #f59e0b;border-radius:12px;background:#fffbeb;">
            <h3 style="margin-top:0;color:#b45309;">Friendly Reminder: Your Offer Letter Expires Soon</h3>
            <p>Dear <strong>{cand['full_name']}</strong>,</p>
            <p>This is a friendly reminder from the People &amp; HR Team that your offer for <strong>{pos['title']}</strong> ({cand['role_category'].title()}) is scheduled to expire on <strong>{offer['expires_at'][:10]}</strong>.</p>
            <p><a href="{signing_url}" style="background:#d97706;color:#ffffff;padding:10px 18px;border-radius:980px;text-decoration:none;font-weight:600;display:inline-block;">Review &amp; Sign Offer Letter</a></p>
            <p style="font-size:12px;color:#475569;">Copied (CC): {cc_str}</p>
        </div>
        """,
    )
    return {"status": "NUDGE_SENT", "notification": notif}


@app.post("/api/webhooks/docuseal")
def docuseal_webhook_adapter(payload: DocuSealWebhookPayload) -> Dict[str, Any]:
    """Pluggable webhook receiver for external signature providers."""
    if payload.event_type == "form.completed":
        return OfferESignAgent.accept_offer(
            signing_token=payload.signing_token,
            signer_name=payload.signer_name or "Verified Candidate",
            signature_type="external_signature",
        )
    if payload.event_type == "form.declined":
        return OfferESignAgent.decline_offer(
            signing_token=payload.signing_token,
            decline_reason=payload.decline_reason or "Declined by candidate",
        )
    if payload.event_type == "form.expired":
        conn = get_conn()
        row = conn.execute(
            "SELECT candidate_id FROM offer_letters WHERE signing_token = ?",
            (payload.signing_token,),
        ).fetchone()
        conn.close()
        if not row:
            raise HTTPException(status_code=404, detail="Token not found")
        return OfferESignAgent.lapse_offer(row["candidate_id"], reason="Offer expired without signature")
    return {"status": "IGNORED", "event_type": payload.event_type}


class AdvanceInput(BaseModel):
    complete_immediately: bool = False


@app.post("/api/tasks/{task_id}/advance")
def advance_subagent_task(
    task_id: str,
    complete: bool = False,
    req: Optional[AdvanceInput] = None,
) -> Dict[str, Any]:
    try:
        comp = complete or (req.complete_immediately if req else False)
        return OnboardingOrchestrator.advance_task_stage(task_id, complete_immediately=comp)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


class BlockerInput(BaseModel):
    reason: Optional[str] = None
    blocker_reason: Optional[str] = None


@app.post("/api/tasks/{task_id}/block")
def block_subagent_task(task_id: str, req: BlockerInput) -> Dict[str, Any]:
    try:
        msg = (
            req.blocker_reason
            or req.reason
            or "Laptop model temporarily out of stock — waiting for IT delivery confirmation"
        )
        return OnboardingOrchestrator.simulate_task_blocker(task_id, msg)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.post("/api/candidates/{candidate_id}/run-subagents")
def run_all_candidate_subagents(candidate_id: str) -> Dict[str, Any]:
    tasks = OnboardingOrchestrator.run_all_subagents_for_candidate(candidate_id)
    return {"status": "COMPLETED", "candidate_id": candidate_id, "tasks": tasks}


@app.get("/api/agents/board")
def get_subagents_visual_board() -> Dict[str, Any]:
    """Returns live visual status across all 4 onboarding assistants."""
    conn = get_conn()
    tasks_raw = [
        dict_from_row(r)
        for r in conn.execute(
            """
            SELECT t.*, c.full_name, c.role_category, c.joining_date, p.title as position_title
            FROM provisioning_tasks t
            JOIN candidates c ON c.id = t.candidate_id
            JOIN positions p ON p.id = c.position_id
            ORDER BY t.updated_at DESC
            """
        ).fetchall()
    ]
    conn.close()

    agents_board = []
    for task_type, meta in SUBAGENT_METADATA.items():
        agent_tasks = []
        for t in tasks_raw:
            if t["task_type"] == task_type:
                t_meta = json.loads(t.get("metadata_json") or "{}")
                stages = meta["stages"]
                pct = (
                    100
                    if t["status"] == "COMPLETED"
                    else int(round((t["current_stage_idx"] / max(len(stages) - 1, 1)) * 100))
                )
                agent_tasks.append(
                    {
                        **t,
                        "current_stage_label": t.get("stage_label"),
                        "progress_pct": pct,
                        "artifacts": t_meta.get("artifacts", {}),
                    }
                )
        agents_board.append(
            {
                "task_type": task_type,
                "target_system": meta.get("department", ""),
                **meta,
                "total_tasks": len(agent_tasks),
                "completed_count": sum(1 for t in agent_tasks if t["status"] == "COMPLETED"),
                "in_progress_count": sum(
                    1 for t in agent_tasks if t["status"] in ("IN_PROGRESS", "PENDING")
                ),
                "blocked_count": sum(1 for t in agent_tasks if t["status"] == "BLOCKED"),
                "tasks": agent_tasks,
            }
        )

    return {"subagents": agents_board}


@app.get("/api/notifications")
def list_notifications(candidate_id: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_conn()
    if candidate_id:
        rows = conn.execute(
            """
            SELECT n.*, c.full_name as candidate_name, c.role_category,
                   o.id as offer_id, o.status as offer_status
            FROM notification_logs n
            LEFT JOIN candidates c ON c.id = n.candidate_id
            LEFT JOIN offer_letters o ON o.candidate_id = n.candidate_id
            WHERE n.candidate_id = ?
            ORDER BY n.created_at DESC
            """,
            (candidate_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT n.*, c.full_name as candidate_name, c.role_category,
                   o.id as offer_id, o.status as offer_status
            FROM notification_logs n
            LEFT JOIN candidates c ON c.id = n.candidate_id
            LEFT JOIN offer_letters o ON o.candidate_id = n.candidate_id
            ORDER BY n.created_at DESC
            LIMIT 150
            """
        ).fetchall()
    conn.close()
    return [dict_from_row(r) for r in rows]


@app.get("/api/offers/{offer_id}/pdf")
def download_offer_pdf(offer_id: str, signed: bool = False):
    conn = get_conn()
    row = conn.execute("SELECT * FROM offer_letters WHERE id = ?", (offer_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Offer not found")
    offer = dict_from_row(row)
    want_signed = bool(signed or offer.get("status") == "ACCEPTED")
    path = offer.get("signed_pdf_path") if (want_signed and offer.get("signed_pdf_path")) else offer.get("pdf_path")

    if not path or not os.path.exists(path):
        cand_row = conn.execute("SELECT * FROM candidates WHERE id = ?", (offer["candidate_id"],)).fetchone()
        if not cand_row:
            conn.close()
            raise HTTPException(status_code=404, detail="Candidate not found")
        cand = dict_from_row(cand_row)
        pos = dict_from_row(
            conn.execute("SELECT * FROM positions WHERE id = ?", (cand["position_id"],)).fetchone()
        )
        path = generate_offer_pdf(cand, pos, offer, signed=want_signed)
        col = "signed_pdf_path" if want_signed else "pdf_path"
        conn.execute(f"UPDATE offer_letters SET {col} = ? WHERE id = ?", (path, offer_id))
        conn.commit()
    conn.close()
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=os.path.basename(path),
    )


@app.get("/api/settings/smtp")
def get_smtp_config_endpoint() -> Dict[str, Any]:
    data = get_smtp_settings()
    if data.get("app_password"):
        data["app_password"] = "••••••••"
    return data


@app.post("/api/settings/smtp")
def save_smtp_config_endpoint(req: SMTPConfigRequest) -> Dict[str, Any]:
    updated = update_smtp_settings(
        sender_email=req.sender_email,
        app_password=req.app_password,
        smtp_host=req.smtp_host,
        smtp_port=req.smtp_port,
        use_tls=req.use_tls,
        live_mode_enabled=req.live_mode_enabled,
        default_hr_email=req.default_hr_email,
        default_ceo_email=req.default_ceo_email,
        override_recipient_for_demo=req.override_recipient_for_demo,
        default_cc_emails=req.default_cc_emails,
    )
    if updated.get("app_password"):
        updated["app_password"] = "••••••••"
    return updated


class SMTPTestInput(BaseModel):
    test_recipient: Optional[str] = "psrmreports@sybyl.com"


@app.post("/api/settings/smtp/test")
def test_smtp_config_endpoint(req: SMTPTestInput) -> Dict[str, Any]:
    ok, message = test_smtp_connection(send_test_email_to=req.test_recipient)
    return {"success": ok, "message": message}


@app.get("/api/settings/templates")
def list_offer_templates_endpoint() -> Dict[str, Any]:
    templates_map = get_all_offer_templates_map()
    return {"templates": templates_map}


@app.post("/api/settings/templates")
def update_offer_template_endpoint(req: OfferTemplateUpdateRequest) -> Dict[str, Any]:
    role_key = req.role_category.value
    default_tpl = DEFAULT_OFFER_TEMPLATES.get(role_key, DEFAULT_OFFER_TEMPLATES["EMPLOYEE"])
    template_name = (
        req.template_name
        or default_tpl.get("template_name", f"{role_key.title()} Offer Letter")
    ).strip()
    header_title = (
        req.title
        or req.header_title
        or default_tpl.get("header_title", "Official Offer of Appointment")
    ).strip()
    email_subject = (
        req.subject_line
        or req.email_subject
        or req.email_subject_template
        or default_tpl.get("email_subject", "[Offer Letter] {{position_title}} — {{candidate_name}}")
    ).strip()
    opening_text = (
        req.intro_text
        or req.opening_text
        or default_tpl.get("opening_text", "")
    ).strip()
    body_text = (
        req.terms_text
        or req.body_text
        or default_tpl.get("body_text", "")
    ).strip()
    closing_text = (
        req.closing_text
        or default_tpl.get("closing_text", "Warm regards,\nPeople & Culture Team — Sybyl")
    ).strip()

    now = utc_now_iso()
    conn = get_conn()
    conn.execute(
        """
        INSERT INTO offer_templates (
            role_category, template_name, email_subject, header_title,
            opening_text, body_text, closing_text, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(role_category) DO UPDATE SET
            template_name = excluded.template_name,
            email_subject = excluded.email_subject,
            header_title = excluded.header_title,
            opening_text = excluded.opening_text,
            body_text = excluded.body_text,
            closing_text = excluded.closing_text,
            updated_at = excluded.updated_at
        """,
        (
            role_key,
            template_name,
            email_subject,
            header_title,
            opening_text,
            body_text,
            closing_text,
            now,
        ),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM offer_templates WHERE role_category = ?", (role_key,)
    ).fetchone()
    conn.close()
    updated_tpl = normalize_template_row(dict_from_row(row))
    return {"templates": get_all_offer_templates_map(), "updated": updated_tpl}


class TemplateResetInput(BaseModel):
    role_category: Optional[str] = None


@app.post("/api/settings/templates/reset")
def reset_offer_templates_endpoint(req: Optional[TemplateResetInput] = None) -> Dict[str, Any]:
    now = utc_now_iso()
    conn = get_conn()
    target_roles = (
        [req.role_category.upper()]
        if (req and req.role_category and req.role_category.upper() in DEFAULT_OFFER_TEMPLATES)
        else list(DEFAULT_OFFER_TEMPLATES.keys())
    )
    for role_key in target_roles:
        tpl = DEFAULT_OFFER_TEMPLATES[role_key]
        conn.execute(
            """
            INSERT INTO offer_templates (
                role_category, template_name, email_subject, header_title,
                opening_text, body_text, closing_text, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(role_category) DO UPDATE SET
                template_name = excluded.template_name,
                email_subject = excluded.email_subject,
                header_title = excluded.header_title,
                opening_text = excluded.opening_text,
                body_text = excluded.body_text,
                closing_text = excluded.closing_text,
                updated_at = excluded.updated_at
            """,
            (
                role_key,
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
    return {"templates": get_all_offer_templates_map()}



@app.post("/api/demo/reset")
def reset_demo_endpoint(request: Request) -> Dict[str, Any]:
    base_url = _get_public_base_url(request)
    seed_demo_data(force_reset=True, base_url=base_url)
    return {"status": "RESET_COMPLETE"}
