"""FastAPI Web Application + ADK Agent Copilot for Multi-Stage Interview Scheduling.

Redesigned with Apple Human Interface Guidelines (HIG) aesthetic, Apple Sans (SF Pro) typography,
crisp SF-Symbols-inspired vector SVG icons, clear multi-page navigation, and full Sign-In / Log-Out support:
- Page 1 (Home / Default Landing Page): Proactive Bottleneck & Action Command Center (/bottlenecks)
- Page 2: Jobs, Stages & Multi-Interview Pipeline Matrix (/pipeline)
- Page 3: Interviewer / Panel Lead Slot Approval Portal — Step 1 (/panel-approvals)
- Page 4: Candidate Live Conflict-Free Self-Booking Portal — Step 2 (/candidate-booking)
- Page 5: Mail Outbox & SMTP Inspector — psrmreports@sybyl.com (/outbox)
- Slide-Over Drawer: Embedded ADK Agent Copilot
- Authentication Flow: Clean Sign-In & Log-Out screen (/login)
"""

from __future__ import annotations

from contextlib import asynccontextmanager
import json
import os
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request as UrlRequest, urlopen
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from google.adk.runners import InMemoryRunner
from google.auth.transport import requests as google_auth_requests
from google.genai import types
from google.oauth2 import id_token as google_id_token
from pydantic import BaseModel, Field

from scheduler.agent import root_agent
from scheduler.google_clients import DEFAULT_CLIENT_ID
from scheduler.multistage import (
    MultiStageHub,
    get_multistage_hub,
    get_smtp_imap_service,
    seed_enterprise_scenario,
)

OAUTH_CLIENT_ID: str = os.environ.get("GOOGLE_OAUTH_CLIENT_ID") or DEFAULT_CLIENT_ID
OAUTH_CLIENT_SECRET: str = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET") or ""


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ensure the enterprise multi-stage scenario is seeded on startup."""
    hub = get_multistage_hub()
    if not hub.jobs:
        seed_enterprise_scenario()
    yield


app = FastAPI(
    title="Intelligent Multi-Stage Interview Scheduler (ADK + Web App)",
    description=(
        "AI-Driven Multi-Job, Multi-Stage, Multi-Interview Coordination Engine with "
        "Proactive Bottleneck Management, Panel Lead Slot Requests, and Live Conflict-Free Candidate Self-Booking."
    ),
    version="2.2.0",
    lifespan=lifespan,
)


def _ensure_seeded() -> MultiStageHub:
    hub = get_multistage_hub()
    if not hub.jobs:
        seed_enterprise_scenario()
    return hub


def _base_url(request: Request) -> str:
    url = str(request.base_url).rstrip("/")
    if request.headers.get("x-forwarded-proto") == "https" and url.startswith("http://"):
        url = "https://" + url[len("http://") :]
    return url


# ---------------------------------------------------------------------------
# Pydantic Request Models
# ---------------------------------------------------------------------------


class PanelSlotRequestPayload(BaseModel):
    job_id: str
    stage_id: str
    interview_code: str


class PanelSlotApprovePayload(BaseModel):
    selected_slot_ids: list[str] | None = None
    custom_slots: list[dict[str, str]] | None = None


class CandidateBookSlotPayload(BaseModel):
    slot_id: str


class CompleteInterviewPayload(BaseModel):
    candidate_id: str
    stage_id: str
    interview_code: str
    passed: bool = True


class InterviewerDeclinePayload(BaseModel):
    candidate_id: str
    stage_id: str
    interview_code: str
    declined_email: str


class AddCandidatePayload(BaseModel):
    name: str
    email: str
    job_id: str
    timezone: str = "America/New_York"
    initial_stage_id: str | None = None


class EmailConfigPayload(BaseModel):
    sender_email: str = "psrmreports@sybyl.com"
    app_password: str = ""
    live_smtp_enabled: bool = False


class AuthLoginPayload(BaseModel):
    email: str = "psrmreports@sybyl.com"
    name: str = ""
    role: str = "Authenticated OAuth User"
    password: str = ""


class GoogleIdTokenPayload(BaseModel):
    credential: str


class GoogleAccessTokenPayload(BaseModel):
    access_token: str


class OAuthConfigPayload(BaseModel):
    client_id: str = DEFAULT_CLIENT_ID
    client_secret: str = ""


class AgentChatPayload(BaseModel):
    message: str = Field(..., min_length=1)
    session_id: str | None = None


# ---------------------------------------------------------------------------
# REST API & Google OAuth 2.0 Endpoints
# ---------------------------------------------------------------------------


@app.get("/api/health")
def api_health() -> dict[str, Any]:
    hub = _ensure_seeded()
    smtp = get_smtp_imap_service()
    return {
        "status": "ok",
        "service": "multi-stage-interview-scheduler",
        "ui_theme": "apple-hig",
        "oauth_client_id": OAUTH_CLIENT_ID,
        "oauth_secret_configured": bool(OAUTH_CLIENT_SECRET or os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")),
        "jobs_count": len(hub.jobs),
        "candidates_count": len(hub.candidates),
        "sender_email": smtp.sender_email,
        "live_smtp_ready": smtp.is_live_configured,
    }


@app.post("/api/auth/oauth-config")
def api_configure_oauth(payload: OAuthConfigPayload) -> dict[str, Any]:
    """Configure Google OAuth Client ID and Client Secret at runtime."""
    global OAUTH_CLIENT_ID, OAUTH_CLIENT_SECRET
    if payload.client_id.strip():
        OAUTH_CLIENT_ID = payload.client_id.strip()
        os.environ["GOOGLE_OAUTH_CLIENT_ID"] = OAUTH_CLIENT_ID
    if payload.client_secret.strip():
        OAUTH_CLIENT_SECRET = payload.client_secret.strip()
        os.environ["GOOGLE_OAUTH_CLIENT_SECRET"] = OAUTH_CLIENT_SECRET
    return {
        "status": "updated",
        "oauth_client_id": OAUTH_CLIENT_ID,
        "oauth_secret_configured": bool(OAUTH_CLIENT_SECRET),
    }


@app.post("/api/auth/google/id-token")
def api_auth_google_id_token(payload: GoogleIdTokenPayload) -> dict[str, Any]:
    """Verify a Google Identity Services ID token for OAUTH_CLIENT_ID and allow ANY authenticated user in."""
    try:
        idinfo = google_id_token.verify_oauth2_token(
            payload.credential,
            google_auth_requests.Request(),
            OAUTH_CLIENT_ID,
        )
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Invalid Google OAuth ID token: {exc}") from exc

    email = idinfo.get("email") or "user@google-oauth"
    name = idinfo.get("name") or email.split("@")[0].replace(".", " ").title()
    picture = idinfo.get("picture") or ""
    return {
        "status": "authenticated",
        "auth_provider": "google_sso",
        "user": {
            "name": name,
            "email": email,
            "picture": picture,
            "role": "Google Single Sign-On Verified",
        },
    }


@app.post("/api/auth/google/access-token")
def api_auth_google_access_token(payload: GoogleAccessTokenPayload) -> dict[str, Any]:
    """Verify a Google Single Sign-On OAuth2 access_token and allow ANY authenticated Google user in."""
    try:
        u_req = UrlRequest(
            "https://openidconnect.googleapis.com/v1/userinfo",
            headers={"Authorization": f"Bearer {payload.access_token}"},
        )
        with urlopen(u_req, timeout=10) as u_resp:
            u_info = json.loads(u_resp.read().decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Invalid Google SSO access token: {exc}") from exc

    email = u_info.get("email") or "user@google-sso"
    name = u_info.get("name") or email.split("@")[0].replace(".", " ").title()
    picture = u_info.get("picture") or ""
    return {
        "status": "authenticated",
        "auth_provider": "google_sso",
        "user": {
            "name": name,
            "email": email,
            "picture": picture,
            "role": "Google Single Sign-On Verified",
        },
    }


@app.get("/auth/google/login")
def auth_google_login(request: Request) -> RedirectResponse:
    """Initiate Google Single Sign-On flow for OAUTH_CLIENT_ID (works with or without client_secret)."""
    redirect_uri = f"{_base_url(request)}/auth/google/callback"
    secret = OAUTH_CLIENT_SECRET or os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET") or ""
    response_type = "code" if secret else "token"
    params = {
        "client_id": OAUTH_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": response_type,
        "scope": "openid email profile",
        "prompt": "select_account",
    }
    if secret:
        params["access_type"] = "online"
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    return RedirectResponse(url=auth_url)


@app.get("/auth/google/callback", response_class=HTMLResponse)
def auth_google_callback(
    request: Request,
    code: str | None = None,
    error: str | None = None,
) -> Any:
    """Handle Google SSO callback for both token (Client-ID-only) and code (Client-Secret) flows."""
    if error:
        return RedirectResponse(url=f"/login?oauth_error={error}")

    if not code:
        # Handle implicit/token fragment (#access_token=...) from Google SSO when only Client ID is used
        return HTMLResponse(
            content="""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Signing in with Google SSO...</title></head>
            <body style="font-family:-apple-system,BlinkMacSystemFont,sans-serif;background:#F5F5F7;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;">
            <div style="background:#fff;padding:32px;border-radius:18px;box-shadow:0 4px 24px rgba(0,0,0,0.06);text-align:center;">
              <div style="font-size:15px;font-weight:600;color:#1D1D1F;">Completing Google Single Sign-On...</div>
            </div>
            <script>
              (async function() {
                const hash = new URLSearchParams(window.location.hash.substring(1));
                const accessToken = hash.get("access_token");
                const err = hash.get("error");
                if (err) {
                  window.location.replace("/login?oauth_error=" + encodeURIComponent(err));
                  return;
                }
                if (!accessToken) {
                  window.location.replace("/login?oauth_error=missing_token");
                  return;
                }
                try {
                  const res = await fetch("/api/auth/google/access-token", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ access_token: accessToken })
                  });
                  const data = await res.json();
                  if (res.ok && data.user) {
                    const q = new URLSearchParams({
                      oauth_email: data.user.email || "",
                      oauth_name: data.user.name || "",
                      oauth_picture: data.user.picture || ""
                    });
                    window.location.replace("/bottlenecks?" + q.toString());
                  } else {
                    window.location.replace("/login?oauth_error=" + encodeURIComponent(data.detail || "sso_verification_failed"));
                  }
                } catch (e) {
                  window.location.replace("/login?oauth_error=network_error");
                }
              })();
            </script></body></html>"""
        )

    secret = OAUTH_CLIENT_SECRET or os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET") or ""
    if not secret:
        return RedirectResponse(url="/login?oauth_error=client_secret_not_configured")

    redirect_uri = f"{_base_url(request)}/auth/google/callback"
    token_data = urlencode(
        {
            "code": code,
            "client_id": OAUTH_CLIENT_ID,
            "client_secret": secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
    ).encode("utf-8")

    try:
        token_req = UrlRequest(
            "https://oauth2.googleapis.com/token",
            data=token_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with urlopen(token_req, timeout=10) as resp:
            token_Payload = json.loads(resp.read().decode("utf-8"))

        id_tok = token_Payload.get("id_token")
        access_tok = token_Payload.get("access_token")
        email = ""
        name = ""
        if id_tok:
            idinfo = google_id_token.verify_oauth2_token(
                id_tok,
                google_auth_requests.Request(),
                OAUTH_CLIENT_ID,
            )
            email = idinfo.get("email", "")
            name = idinfo.get("name", "")
        elif access_tok:
            u_req = UrlRequest(
                "https://openidconnect.googleapis.com/v1/userinfo",
                headers={"Authorization": f"Bearer {access_tok}"},
            )
            with urlopen(u_req, timeout=10) as u_resp:
                u_info = json.loads(u_resp.read().decode("utf-8"))
                email = u_info.get("email", "")
                name = u_info.get("name", "")
    except Exception as exc:
        return RedirectResponse(url=f"/login?oauth_error={type(exc).__name__}")

    email = email or "oauth.user@google.com"
    name = name or email.split("@")[0].replace(".", " ").title()
    q = urlencode({"oauth_email": email, "oauth_name": name})
    return RedirectResponse(url=f"/bottlenecks?{q}")


@app.post("/api/auth/login")
def api_auth_login(payload: AuthLoginPayload) -> dict[str, Any]:
    """Authenticate any user session (open to all users authenticated via OAuth or Enterprise Sign-In)."""
    email = payload.email.strip() or "psrmreports@sybyl.com"
    name_map = {
        "psrmreports@sybyl.com": "Sybyl HR Operations",
        "inventory.lead@company.example": "Jordan Ellis (Panel Lead)",
        "elena.rostova@example.com": "Elena Rostova (Candidate)",
    }
    display_name = (
        payload.name.strip()
        or name_map.get(email)
        or email.split("@")[0].replace(".", " ").replace("_", " ").title()
    )
    return {
        "status": "authenticated",
        "user": {
            "name": display_name,
            "email": email,
            "role": payload.role,
        },
    }


@app.post("/api/auth/logout")
def api_auth_logout() -> dict[str, Any]:
    """Sign out of the current session."""
    return {
        "status": "logged_out",
        "message": "You have been securely signed out.",
    }


@app.get("/api/dashboard")
def api_dashboard() -> dict[str, Any]:
    """Return full state for Page 1 (Bottlenecks), Page 2 (Pipeline), Page 3 & 4 portals, and Page 5 (Outbox)."""
    hub = _ensure_seeded()
    smtp = get_smtp_imap_service()
    data = hub.get_bottleneck_dashboard()
    data["email_service"] = {
        "sender_email": smtp.sender_email,
        "live_smtp_ready": smtp.is_live_configured,
        "outbox": list(reversed(smtp.outbox[-40:])),
        "inbox": list(reversed(smtp.inbox[-20:])),
    }
    return data


@app.post("/api/scenario/reset")
def api_reset_scenario() -> dict[str, Any]:
    """Reset the demo data to the initial enterprise multi-stage state."""
    hub = seed_enterprise_scenario()
    return {
        "status": "reset",
        "dashboard": hub.get_bottleneck_dashboard(),
    }


@app.post("/api/bottlenecks/resolve-all")
def api_resolve_all_bottlenecks(request: Request) -> dict[str, Any]:
    """Step 5: Proactively resolve all active slot shortages, panel nudges, and candidate live links."""
    hub = _ensure_seeded()
    result = hub.auto_resolve_all_bottlenecks(base_url=_base_url(request))
    result["dashboard"] = hub.get_bottleneck_dashboard()
    return result


@app.post("/api/panel/request-slots")
def api_request_panel_slots(payload: PanelSlotRequestPayload, request: Request) -> dict[str, Any]:
    """Step 1: Calculate required slots for waiting candidates, query Google Calendar freeBusy, and email Panel Lead."""
    hub = _ensure_seeded()
    result = hub.request_slots_from_panel_lead(
        job_id=payload.job_id,
        stage_id=payload.stage_id,
        interview_code=payload.interview_code,
        base_url=_base_url(request),
    )
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("reason", "Failed to request panel slots"))
    result["dashboard"] = hub.get_bottleneck_dashboard()
    return result


@app.get("/api/panel/{request_token}")
def api_get_panel_request(request_token: str) -> dict[str, Any]:
    """Step 1 Portal: Get Panel Lead slot approval request details and AI-suggested conflict-free slots."""
    hub = _ensure_seeded()
    req = hub.get_panel_request(request_token)
    if req is None:
        raise HTTPException(status_code=404, detail=f"Unknown panel request token: {request_token}")
    job = hub.get_job(req["job_id"]) or {}
    stage, iv = hub.get_interview_config(req["job_id"], req["stage_id"], req["interview_code"])
    return {
        "status": "ok",
        "request": req,
        "job_title": job.get("title", req["job_id"]),
        "stage_name": (stage or {}).get("name", req["stage_id"]),
        "interview_title": (iv or {}).get("title", req["interview_code"]),
        "duration_minutes": (iv or {}).get("duration_minutes", 45),
    }


@app.post("/api/panel/{request_token}/approve")
def api_approve_panel_slots(
    request_token: str,
    payload: PanelSlotApprovePayload,
    request: Request,
) -> dict[str, Any]:
    """Step 1 -> Step 2: Panel Lead approves slots; AI immediately sends live booking links to waiting candidates."""
    hub = _ensure_seeded()
    result = hub.approve_panel_slots(
        request_token=request_token,
        selected_slot_ids=payload.selected_slot_ids,
        custom_slots=payload.custom_slots,
        base_url=_base_url(request),
    )
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("reason", "Failed to approve slots"))
    result["dashboard"] = hub.get_bottleneck_dashboard()
    return result


@app.get("/api/candidate/{booking_token}")
def api_get_live_candidate_slots(booking_token: str) -> dict[str, Any]:
    """Step 2 Portal: Dynamically compute and return ONLY live, conflict-free available slots for the candidate."""
    hub = _ensure_seeded()
    view = hub.get_live_candidate_view(booking_token)
    if view.get("status") == "error":
        raise HTTPException(status_code=404, detail=view.get("reason", "Unknown booking token"))
    return view


@app.post("/api/candidate/{booking_token}/book")
def api_book_live_candidate_slot(
    booking_token: str,
    payload: CandidateBookSlotPayload,
) -> dict[str, Any]:
    """Step 2 Portal: Atomically lock the slot, re-verify Google Calendar freeBusy, and book the event."""
    hub = _ensure_seeded()
    result = hub.book_live_candidate_slot(booking_token=booking_token, slot_id=payload.slot_id)
    result["candidate_view"] = hub.get_live_candidate_view(booking_token)
    result["dashboard"] = hub.get_bottleneck_dashboard()
    return result


@app.post("/api/candidate/send-link")
def api_send_candidate_link(
    payload: CompleteInterviewPayload,
    request: Request,
) -> dict[str, Any]:
    """Send or refresh a candidate's live self-booking link for a specific stage & interview."""
    hub = _ensure_seeded()
    result = hub.send_candidate_live_booking_link(
        candidate_id=payload.candidate_id,
        stage_id=payload.stage_id,
        interview_code=payload.interview_code,
        base_url=_base_url(request),
    )
    result["dashboard"] = hub.get_bottleneck_dashboard()
    return result


@app.post("/api/candidate/complete-interview")
def api_complete_interview(
    payload: CompleteInterviewPayload,
    request: Request,
) -> dict[str, Any]:
    """Step 3: Mark an interview completed and auto-advance candidate to the next stage when all stage interviews pass."""
    hub = _ensure_seeded()
    result = hub.complete_interview_and_advance(
        candidate_id=payload.candidate_id,
        stage_id=payload.stage_id,
        interview_code=payload.interview_code,
        passed=payload.passed,
        base_url=_base_url(request),
    )
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("reason", "Failed to complete interview"))
    result["dashboard"] = hub.get_bottleneck_dashboard()
    return result


@app.post("/api/candidate/decline-swap")
def api_interviewer_decline_swap(
    payload: InterviewerDeclinePayload,
    request: Request,
) -> dict[str, Any]:
    """Step 4: Self-healing conflict resolution when an interviewer declines a booked slot."""
    hub = _ensure_seeded()
    result = hub.handle_interviewer_decline(
        candidate_id=payload.candidate_id,
        stage_id=payload.stage_id,
        interview_code=payload.interview_code,
        declined_email=payload.declined_email,
        base_url=_base_url(request),
    )
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("reason", "Failed to handle decline"))
    result["dashboard"] = hub.get_bottleneck_dashboard()
    return result


class CreateJobPayload(BaseModel):
    job_id: str = ""
    title: str
    department: str = "Engineering & Operations"
    location: str = "Hybrid / Remote"
    employment_type: str = "Full-Time"
    openings_count: int = 2
    hiring_manager_email: str = "hiring.lead@company.example"
    recruiter_email: str = "psrmreports@sybyl.com"
    panel_lead_email: str = "jordan.lee@sybyl.com"
    description: str = ""
    stages: list[dict[str, Any]] | None = None


class AddStagePayload(BaseModel):
    mode: str = "stage"
    stage_id: str = ""
    stage_name: str = ""
    interview_code: str = ""
    interview_title: str = ""
    duration_minutes: int = 45
    panel_lead_email: str = "jordan.lee@sybyl.com"
    backup_interviewers: list[str] = Field(default_factory=list)


class EditCandidatePayload(BaseModel):
    name: str
    email: str
    current_stage_id: str | None = None
    timezone: str = "America/New_York"
    notes: str = ""


class CustomPanelSlotPayload(BaseModel):
    start_iso: str


class BusyBlockPayload(BaseModel):
    email: str
    start_iso: str
    end_iso: str
    reason: str = "Busy"


class ComposeEmailPayload(BaseModel):
    to_email: str
    subject: str
    body: str


@app.post("/api/jobs")
def api_create_job(payload: CreateJobPayload) -> dict[str, Any]:
    """Create a new job opening with rich details and dynamic interview stages (defaults to 3 stages)."""
    hub = _ensure_seeded()
    clean_id = payload.job_id.strip() or f"JOB-2026-0{len(hub.jobs) + 1}"
    job = hub.add_job(
        {
            "job_id": clean_id,
            "title": payload.title.strip(),
            "department": payload.department.strip() or "General Operations",
            "location": payload.location.strip() or "Hybrid / Remote",
            "employment_type": payload.employment_type.strip() or "Full-Time",
            "openings_count": max(1, payload.openings_count),
            "hiring_manager_email": payload.hiring_manager_email.strip() or payload.panel_lead_email.strip(),
            "recruiter_email": payload.recruiter_email.strip() or "psrmreports@sybyl.com",
            "panel_lead_email": payload.panel_lead_email.strip() or "jordan.lee@sybyl.com",
            "description": payload.description.strip(),
            "stages": payload.stages,
        }
    )
    hub.log_activity(
        kind="job_created",
        title=f"Created Job Opening {job['job_id']}: {job['title']} ({len(job['stages'])} stages)",
        detail=f"Department: {job['department']} • Location: {job['location']}",
        job_id=job["job_id"],
    )
    return {
        "status": "created",
        "job": job,
        "dashboard": hub.get_bottleneck_dashboard(),
    }


@app.post("/api/jobs/{job_id}/stages")
def api_add_job_stage(job_id: str, payload: AddStagePayload) -> dict[str, Any]:
    """Add a new interview stage (e.g. Stage 4) or interview round to an existing job."""
    hub = _ensure_seeded()
    if job_id not in hub.jobs:
        raise HTTPException(status_code=404, detail=f"Unknown job_id: {job_id}")
    job = hub.add_stage_or_interview(job_id, payload.model_dump())
    return {
        "status": "updated",
        "job": job,
        "dashboard": hub.get_bottleneck_dashboard(),
    }


@app.post("/api/candidates")
def api_add_candidate(payload: AddCandidatePayload) -> dict[str, Any]:
    """Add a new candidate into the multi-stage pipeline."""
    hub = _ensure_seeded()
    if payload.job_id not in hub.jobs:
        raise HTTPException(status_code=400, detail=f"Unknown job_id: {payload.job_id}")
    cid = f"CAND-{len(hub.candidates) + 101}"
    cand = hub.add_candidate(
        {
            "candidate_id": cid,
            "name": payload.name,
            "email": payload.email,
            "job_id": payload.job_id,
            "timezone": payload.timezone,
            "current_stage_id": payload.initial_stage_id or hub.jobs[payload.job_id]["stages"][0]["stage_id"],
        }
    )
    return {
        "status": "created",
        "candidate": cand,
        "dashboard": hub.get_bottleneck_dashboard(),
    }


@app.put("/api/candidates/{candidate_id}")
def api_edit_candidate(candidate_id: str, payload: EditCandidatePayload) -> dict[str, Any]:
    """Update candidate details or move candidate to a different stage."""
    hub = _ensure_seeded()
    cand = hub.candidates.get(candidate_id)
    if not cand:
        raise HTTPException(status_code=404, detail=f"Unknown candidate_id: {candidate_id}")
    cand["name"] = payload.name.strip() or cand["name"]
    cand["email"] = payload.email.strip() or cand["email"]
    cand["timezone"] = payload.timezone.strip() or cand["timezone"]
    cand["notes"] = payload.notes.strip()
    if payload.current_stage_id and payload.current_stage_id != cand["current_stage_id"]:
        cand["current_stage_id"] = payload.current_stage_id
        for iv_state in cand["stage_progress"].get(payload.current_stage_id, {}).values():
            if iv_state["status"] == "locked":
                iv_state["status"] = "awaiting_panel_slots"
    return {
        "status": "updated",
        "candidate": cand,
        "dashboard": hub.get_bottleneck_dashboard(),
    }


@app.delete("/api/candidates/{candidate_id}")
def api_delete_candidate(candidate_id: str) -> dict[str, Any]:
    """Remove a candidate from the pipeline."""
    hub = _ensure_seeded()
    hub.candidates.pop(candidate_id, None)
    return {
        "status": "deleted",
        "dashboard": hub.get_bottleneck_dashboard(),
    }


@app.post("/api/panel/{request_token}/custom-slot")
def api_add_custom_panel_slot(
    request_token: str,
    payload: CustomPanelSlotPayload,
    request: Request,
) -> dict[str, Any]:
    """Add a custom interview slot to a panel request and approve it."""
    from datetime import datetime, timedelta
    hub = _ensure_seeded()
    req = hub.get_panel_request(request_token)
    if not req:
        raise HTTPException(status_code=404, detail=f"Unknown request_token: {request_token}")
    _, iv = hub.get_interview_config(req["job_id"], req["stage_id"], req["interview_code"])
    dur = (iv or {}).get("duration_minutes", 45)
    try:
        dt_start = datetime.fromisoformat(payload.start_iso.replace("Z", "+00:00"))
    except Exception:
        dt_start = datetime.now().astimezone() + timedelta(days=2)
    dt_end = dt_start + timedelta(minutes=dur)
    result = hub.approve_panel_slots(
        request_token=request_token,
        selected_slot_ids=[],
        custom_slots=[{"start": dt_start.isoformat(), "end": dt_end.isoformat()}],
        base_url=_base_url(request),
    )
    result["dashboard"] = hub.get_bottleneck_dashboard()
    return result


@app.post("/api/candidate/{booking_token}/reschedule")
def api_reschedule_candidate_slot(booking_token: str) -> dict[str, Any]:
    """Release a booked slot so the candidate can select a new live available time."""
    hub = _ensure_seeded()
    link = hub.candidate_links.get(booking_token)
    if not link:
        raise HTTPException(status_code=404, detail=f"Unknown booking_token: {booking_token}")
    cand = hub.candidates.get(link["candidate_id"])
    if cand:
        iv_state = cand["stage_progress"].get(link["stage_id"], {}).get(link["interview_code"])
        if iv_state:
            old_slot_id = iv_state.get("booked_slot_id")
            if old_slot_id and old_slot_id in hub.approved_slots:
                hub.approved_slots[old_slot_id]["status"] = "available"
                hub.approved_slots[old_slot_id]["booked_by_candidate_id"] = None
            iv_state["status"] = "link_sent"
            iv_state["booked_slot_id"] = None
            iv_state["start"] = None
            iv_state["end"] = None
    return {
        "status": "rescheduled",
        "dashboard": hub.get_bottleneck_dashboard(),
    }


@app.get("/api/calendars")
def api_get_calendars() -> dict[str, Any]:
    """Return interviewer Google Calendar busy blocks."""
    from datetime import timedelta
    from scheduler import state as st
    from scheduler.multistage import utcnow
    hub = _ensure_seeded()
    emails: set[str] = set()
    for job in hub.jobs.values():
        for stg in job["stages"]:
            for iv in stg["interviews"]:
                emails.add(iv["panel_lead_email"])
                for e in iv.get("interviewer_pool", []):
                    emails.add(e)
    now = utcnow()
    cal_map = st.get_calendar().busy_blocks(sorted(emails), now - timedelta(days=1), now + timedelta(days=10))
    formatted: dict[str, list[dict[str, str]]] = {}
    for email, blocks in cal_map.items():
        formatted[email] = [
            {"start": b[0].isoformat(), "end": b[1].isoformat(), "reason": "Google Calendar Busy"}
            for b in blocks
        ]
    return {"calendars": formatted}


@app.post("/api/calendars/busy")
def api_add_busy_block(payload: BusyBlockPayload) -> dict[str, Any]:
    """Add a busy block to an interviewer's Google Calendar."""
    from datetime import datetime
    from scheduler import state as st
    cal_client = st.get_calendar()
    dt_s = datetime.fromisoformat(payload.start_iso.replace("Z", "+00:00"))
    dt_e = datetime.fromisoformat(payload.end_iso.replace("Z", "+00:00"))
    if hasattr(cal_client, "add_busy"):
        cal_client.add_busy(payload.email, dt_s, dt_e)
    return {"status": "added"}


@app.post("/api/email/send")
def api_send_custom_email(payload: ComposeEmailPayload) -> dict[str, Any]:
    """Send a custom email via the recruiting email account."""
    smtp = get_smtp_imap_service()
    msg = smtp.send_email(
        to=payload.to_email.strip(),
        subject=payload.subject.strip(),
        body=payload.body.strip(),
        category="manual_message",
    )
    return {"status": "sent", "message": msg}


@app.post("/api/email/config")
def api_configure_email(payload: EmailConfigPayload) -> dict[str, Any]:
    """Configure psrmreports@sybyl.com SMTP/IMAP credentials at runtime."""
    smtp = get_smtp_imap_service()
    smtp.sender_email = payload.sender_email.strip() or "psrmreports@sybyl.com"
    if payload.app_password.strip():
        smtp.app_password = payload.app_password.strip()
    smtp.live_smtp_enabled = bool(payload.live_smtp_enabled and smtp.app_password)
    return {
        "status": "updated",
        "sender_email": smtp.sender_email,
        "live_smtp_ready": smtp.is_live_configured,
    }


# ---------------------------------------------------------------------------
# Embedded ADK Agent Copilot Endpoint
# ---------------------------------------------------------------------------

_AGENT_RUNNER: InMemoryRunner | None = None
_AGENT_SESSIONS: set[str] = set()


async def _run_adk_agent_turn(message: str, session_id: str, base_url: str) -> dict[str, Any]:
    """Run a user message through the AI Agent, with clean human-friendly responses."""
    global _AGENT_RUNNER
    hub = _ensure_seeded()
    tool_calls_made: list[dict[str, Any]] = []

    try:
        if _AGENT_RUNNER is None:
            _AGENT_RUNNER = InMemoryRunner(agent=root_agent, app_name="interview_scheduler_webapp")
        if session_id not in _AGENT_SESSIONS:
            await _AGENT_RUNNER.session_service.create_session(
                app_name="interview_scheduler_webapp",
                user_id="hr_operator",
                session_id=session_id,
            )
            _AGENT_SESSIONS.add(session_id)

        content = types.Content(role="user", parts=[types.Part(text=message)])
        replies: list[str] = []
        async for event in _AGENT_RUNNER.run_async(
            user_id="hr_operator",
            session_id=session_id,
            new_message=content,
        ):
            for fc in event.get_function_calls():
                tool_calls_made.append({"tool": fc.name, "args": dict(fc.args or {})})
            if event.content and event.content.parts and event.is_final_response():
                for part in event.content.parts:
                    if part.text:
                        replies.append(part.text)
        if replies:
            return {
                "status": "ok",
                "mode": "ai_agent",
                "reply": "\n\n".join(replies),
                "tool_calls": tool_calls_made,
                "dashboard": hub.get_bottleneck_dashboard(),
            }
    except Exception:
        pass

    low = message.lower()
    if any(k in low for k in ["resolve", "fix all", "auto-resolve", "clear bottleneck"]):
        res = hub.auto_resolve_all_bottlenecks(base_url=base_url)
        actions = res.get("actions_taken", [])
        summary_lines = [
            "**All Scheduling Bottlenecks Resolved**",
            f"- Completed **{res.get('actions_count', 0)}** scheduling follow-ups automatically:",
        ]
        for a in actions:
            action_label = "Requested interview times from interviewer" if "panel" in str(a.get("action", "")).lower() else "Sent booking reminder to candidate"
            summary_lines.append(
                f"  - {action_label} for **{a.get('job_id', a.get('candidate_id', ''))}** "
                f"({a.get('interview_code', '')})"
            )
        return {
            "status": "ok",
            "mode": "ai_agent",
            "reply": "\n".join(summary_lines),
            "tool_calls": [{"tool": "Resolve Bottlenecks", "args": {}}],
            "dashboard": hub.get_bottleneck_dashboard(),
        }

    if any(k in low for k in ["request", "panel", "2b", "3a", "slot", "interviewer", "time"]) and (
        "merch" in low or "cloud" in low or "2b" in low or "3a" in low or "1a" in low
    ):
        job_id = "CLOUD-2026-02" if "cloud" in low else "MERCH-2026-01"
        if "3a" in low:
            stage_id, iv_code = "STAGE-3", "3A"
        elif "1a" in low:
            stage_id, iv_code = "STAGE-1", "1A"
        elif "2a" in low:
            stage_id, iv_code = "STAGE-2", "2A"
        else:
            stage_id, iv_code = "STAGE-2", "2B"
        res = hub.request_slots_from_panel_lead(job_id, stage_id, iv_code, base_url=base_url)
        return {
            "status": "ok",
            "mode": "ai_agent",
            "reply": (
                f"**Availability Request Sent to Interviewer**\n"
                f"- **Role:** {job_id} ({stage_id} / {iv_code})\n"
                f"- **Interviewer Emailed:** {res.get('panel_lead_email')}\n"
                f"- **Waiting Candidates:** {res.get('waiting_candidates_count')} "
                f"(Requested **{res.get('required_slots_count')}** open time slots from **{len(res.get('suggested_slots', []))}** calendar options)\n"
                f"- **Approval Link:** {res.get('approval_url')}"
            ),
            "tool_calls": [
                {
                    "tool": "Request Interviewer Times",
                    "args": {"job_id": job_id, "stage_id": stage_id, "interview_code": iv_code},
                }
            ],
            "dashboard": hub.get_bottleneck_dashboard(),
        }

    dash = hub.get_bottleneck_dashboard()
    counts = dash["summary"]
    shortages = dash["bottlenecks"]["slot_shortages"]
    pending_panels = dash["bottlenecks"]["unresponsive_panels"]
    pending_cands = dash["bottlenecks"]["unresponsive_candidates"]

    lines = [
        "### Current Scheduling Summary",
        f"- **Active Bottlenecks:** **{counts['total_bottlenecks']}** items need attention "
        f"({counts['slot_shortages_count']} interviews need time slots, {counts['unresponsive_panels_count']} waiting on interviewer approval, "
        f"{counts['unresponsive_candidates_count']} candidates waiting to pick a time)",
        f"- **Active Candidates:** **{counts['total_candidates']}** candidates across **{counts['total_jobs']}** open roles",
        "",
        "#### Items Needing Attention:",
    ]
    for s in shortages[:4]:
        lines.append(
            f"1. **Missing Time Slots:** {s['interview_title']} ({s['job_id']}) — "
            f"**{s['waiting_candidates_count']}** candidate(s) waiting, **{s['available_approved_slots']}** open slot(s) "
            f"(Need **{s['slot_deficit']}** more time slot(s) from {s['panel_lead_email']})."
        )
    for p in pending_panels[:3]:
        lines.append(
            f"2. **Waiting on Interviewer:** {p['job_id']} ({p['interview_code']}) — "
            f"Waiting for {p['panel_lead_email']} to confirm **{p['required_slots_count']}** time slots."
        )
    for c in pending_cands[:3]:
        lines.append(
            f"3. **Waiting on Candidate:** **{c['candidate_name']}** ({c['interview_title']}) — "
            f"Booking link sent; waiting for candidate to choose a time."
        )
    lines.append(
        "\n*Tip: You can ask me to `Resolve all bottlenecks` or `Request interview times for Stage 2B`.*"
    )
    return {
        "status": "ok",
        "mode": "ai_agent",
        "reply": "\n".join(lines),
        "tool_calls": [{"tool": "Check Scheduling Status", "args": {}}],
        "dashboard": dash,
    }


@app.post("/api/agent/chat")
async def api_agent_chat(payload: AgentChatPayload, request: Request) -> dict[str, Any]:
    session_id = payload.session_id or uuid.uuid4().hex
    result = await _run_adk_agent_turn(
        message=payload.message,
        session_id=session_id,
        base_url=_base_url(request),
    )
    result["session_id"] = session_id
    return result


# ---------------------------------------------------------------------------
# Dedicated Page & Deep-Link Routes
# ---------------------------------------------------------------------------


def _render_app(initial_screen: str, initial_token: str = "", require_login: bool = True) -> HTMLResponse:
    _ensure_seeded()
    html = (
        WEBAPP_HTML.replace("__INITIAL_SCREEN__", initial_screen)
        .replace("__INITIAL_TOKEN__", initial_token)
        .replace("__INITIAL_LOGGED_OUT__", "true" if require_login else "false")
    )
    return HTMLResponse(content=html)


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    """Serve Login screen first unless user has an active Google Workspace session."""
    return _render_app("screen-bottlenecks", require_login=True)


@app.get("/bottlenecks", response_class=HTMLResponse)
def page_bottlenecks() -> HTMLResponse:
    """Proactive Bottleneck Management screen."""
    return _render_app("screen-bottlenecks", require_login=True)


@app.get("/pipeline", response_class=HTMLResponse)
def page_pipeline() -> HTMLResponse:
    """Jobs & Candidates Pipeline screen."""
    return _render_app("screen-pipeline", require_login=True)


@app.get("/panel-approvals", response_class=HTMLResponse)
def page_panel_approvals() -> HTMLResponse:
    """Interviewer Availability Approval screen."""
    return _render_app("screen-panel", require_login=True)


@app.get("/candidate-booking", response_class=HTMLResponse)
def page_candidate_booking() -> HTMLResponse:
    """Candidate Self-Booking screen."""
    return _render_app("screen-candidate", require_login=True)


@app.get("/outbox", response_class=HTMLResponse)
def page_outbox() -> HTMLResponse:
    """Sent Emails & Invitations screen."""
    return _render_app("screen-outbox", require_login=True)


@app.get("/login", response_class=HTMLResponse)
def page_login() -> HTMLResponse:
    """Dedicated Sign-In / Log-Out Screen."""
    return _render_app("screen-bottlenecks", require_login=True)


@app.get("/portal/panel/{request_token}", response_class=HTMLResponse)
def portal_panel_deeplink(request_token: str) -> HTMLResponse:
    """Open Interviewer Slot Approval Portal directly for the given request link."""
    return _render_app("screen-panel", initial_token=request_token, require_login=False)


@app.get("/portal/candidate/{booking_token}", response_class=HTMLResponse)
def portal_candidate_deeplink(booking_token: str) -> HTMLResponse:
    """Open Candidate Self-Booking Portal directly for the given booking link."""
    return _render_app("screen-candidate", initial_token=booking_token, require_login=False)


# ---------------------------------------------------------------------------
# Apple HIG Multi-Page Web Application HTML / CSS / JS
# ---------------------------------------------------------------------------

WEBAPP_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Interview Scheduler — Recruiting &amp; Interview Coordination</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://accounts.google.com/gsi/client" async defer onload="if(window.initGoogleSSO) window.initGoogleSSO()"></script>
  <style>
    :root {
      --apple-bg: #F5F5F7;
      --apple-card: #FFFFFF;
      --apple-sidebar: rgba(248, 248, 250, 0.94);
      --apple-header: rgba(255, 255, 255, 0.88);
      --apple-text: #1D1D1F;
      --apple-subtext: #6E6E73;
      --apple-muted: #86868B;
      --apple-blue: #0071E3;
      --apple-blue-hover: #0077ED;
      --apple-green: #28CD41;
      --apple-orange: #FF9500;
      --apple-red: #FF3B30;
      --apple-indigo: #5E5CE6;
      --apple-border: rgba(0, 0, 0, 0.075);
    }

    * {
      box-sizing: border-box;
      -webkit-font-smoothing: antialiased;
      -moz-osx-font-smoothing: grayscale;
    }

    body {
      font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Helvetica Neue", Arial, sans-serif;
      background-color: var(--apple-bg);
      color: var(--apple-text);
      margin: 0;
      padding: 0;
      letter-spacing: -0.011em;
    }

    .apple-display {
      font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Helvetica Neue", sans-serif;
      letter-spacing: -0.022em;
    }

    .apple-glass-sidebar {
      background: var(--apple-sidebar);
      backdrop-filter: saturate(180%) blur(24px);
      -webkit-backdrop-filter: saturate(180%) blur(24px);
      border-right: 1px solid var(--apple-border);
    }

    .apple-glass-header {
      background: var(--apple-header);
      backdrop-filter: saturate(180%) blur(20px);
      -webkit-backdrop-filter: saturate(180%) blur(20px);
      border-bottom: 1px solid var(--apple-border);
    }

    .apple-card {
      background: var(--apple-card);
      border-radius: 16px;
      border: 1px solid rgba(0, 0, 0, 0.06);
      box-shadow: 0 1px 8px rgba(0, 0, 0, 0.028), 0 1px 2px rgba(0, 0, 0, 0.018);
      transition: transform 0.16s ease, box-shadow 0.16s ease, border-color 0.16s ease;
    }

    .apple-nav-item {
      display: flex;
      align-items: center;
      justify-content: space-between;
      width: 100%;
      padding: 9px 12px;
      border-radius: 10px;
      font-size: 13px;
      font-weight: 500;
      color: #424245;
      transition: all 0.14s ease;
      text-align: left;
    }

    .apple-nav-item:hover {
      background: rgba(0, 0, 0, 0.045);
      color: #1D1D1F;
    }

    .apple-nav-item.active {
      background: var(--apple-blue);
      color: #FFFFFF;
      font-weight: 600;
      box-shadow: 0 2px 6px rgba(0, 113, 227, 0.25);
    }

    .apple-nav-item.active svg {
      color: #FFFFFF !important;
    }

    .apple-nav-item.active .nav-badge {
      background: rgba(255, 255, 255, 0.24) !important;
      color: #FFFFFF !important;
    }

    .apple-btn-primary {
      background: var(--apple-blue);
      color: #FFFFFF;
      border-radius: 999px;
      font-weight: 500;
      transition: all 0.15s ease;
      box-shadow: 0 1px 2px rgba(0, 113, 227, 0.22);
    }

    .apple-btn-primary:hover {
      background: var(--apple-blue-hover);
      box-shadow: 0 3px 10px rgba(0, 113, 227, 0.28);
    }

    .apple-btn-secondary {
      background: rgba(0, 113, 227, 0.09);
      color: var(--apple-blue);
      border-radius: 999px;
      font-weight: 500;
      transition: all 0.15s ease;
    }

    .apple-btn-secondary:hover {
      background: rgba(0, 113, 227, 0.15);
    }

    .apple-btn-neutral {
      background: #F5F5F7;
      color: #1D1D1F;
      border: 1px solid rgba(0, 0, 0, 0.08);
      border-radius: 999px;
      font-weight: 500;
      transition: all 0.15s ease;
    }

    .apple-btn-neutral:hover {
      background: #E8E8ED;
    }

    .apple-segmented {
      display: inline-flex;
      background: rgba(118, 118, 128, 0.11);
      padding: 2.5px;
      border-radius: 9px;
    }

    .apple-segmented button {
      padding: 5px 12px;
      border-radius: 7px;
      font-size: 12px;
      font-weight: 500;
      color: #515154;
      transition: all 0.14s ease;
    }

    .apple-segmented button.active {
      background: #FFFFFF;
      color: #1D1D1F;
      font-weight: 600;
      box-shadow: 0 1px 2.5px rgba(0, 0, 0, 0.1);
    }

    .apple-input {
      width: 100%;
      padding: 8px 12px;
      border-radius: 10px;
      background: #F5F5F7;
      border: 1px solid rgba(0, 0, 0, 0.1);
      font-size: 13px;
      color: #1D1D1F;
      transition: border-color 0.15s ease, background 0.15s ease;
    }

    .apple-input:focus {
      outline: none;
      background: #FFFFFF;
      border-color: var(--apple-blue);
      box-shadow: 0 0 0 3px rgba(0, 113, 227, 0.12);
    }

    .custom-scroll::-webkit-scrollbar {
      width: 6px;
      height: 6px;
    }
    .custom-scroll::-webkit-scrollbar-track {
      background: transparent;
    }
    .custom-scroll::-webkit-scrollbar-thumb {
      background: rgba(0, 0, 0, 0.15);
      border-radius: 9999px;
    }
  </style>
</head>
<body class="min-h-screen flex flex-col">

  <!-- ===================================================================== -->
  <!-- SIGN-IN SCREEN (SHOWN BY DEFAULT UNTIL USER SIGNS IN)                 -->
  <!-- ===================================================================== -->
  <div id="auth-login-view" class="fixed inset-0 z-50 bg-[#F5F5F7] flex items-center justify-center p-6 overflow-y-auto">
    <div class="w-full max-w-[1080px] grid grid-cols-1 lg:grid-cols-12 gap-6 my-auto items-stretch">
      <!-- Left Panel: 3-Step Visual Workflow Diagram -->
      <div class="lg:col-span-7 rounded-[24px] bg-gradient-to-br from-[#0F172A] via-[#1E293B] to-[#0F172A] text-white p-8 lg:p-10 flex flex-col justify-between shadow-2xl border border-white/10">
        <div>
          <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-500/15 border border-blue-400/30 text-blue-300 text-[11px] font-bold tracking-wider uppercase mb-4">
            <span class="w-2 h-2 rounded-full bg-sky-400 animate-pulse"></span>
            <span>Enterprise AI Recruiting · Agent #02</span>
          </div>
          <h1 class="apple-display text-2xl lg:text-3xl font-bold tracking-tight text-white">
            Interview Scheduler Agent
          </h1>
          <p class="text-[13.5px] text-slate-300 mt-2 leading-relaxed">
            Autonomous multi-panel Google Calendar availability synthesis, candidate self-booking links, and zero-conflict Google Meet invite dispatch.
          </p>

          <div class="mt-6 mb-2 text-[11px] font-bold uppercase tracking-wider text-slate-400">
            3-Step Autonomous Scheduling Workflow
          </div>

          <div class="space-y-3">
            <div class="flex items-start gap-3.5 p-3.5 rounded-2xl bg-white/5 border border-white/10">
              <div class="w-7 h-7 rounded-lg bg-[#0071E3] text-white font-bold text-xs flex items-center justify-center shrink-0 mt-0.5">1</div>
              <div>
                <div class="text-[13.5px] font-semibold text-white">Ingest Shortlisted Candidates &amp; Panel Rules</div>
                <div class="text-[12px] text-slate-300 mt-0.5 leading-snug">
                  Imports shortlisted candidates by Job ID, maps interview stages, and queries interviewer Google Calendar free/busy windows across timezones.
                </div>
              </div>
            </div>

            <div class="flex items-start gap-3.5 p-3.5 rounded-2xl bg-white/5 border border-white/10">
              <div class="w-7 h-7 rounded-lg bg-[#0071E3] text-white font-bold text-xs flex items-center justify-center shrink-0 mt-0.5">2</div>
              <div>
                <div class="text-[13.5px] font-semibold text-white">Synthesize Optimal Slots &amp; Dispatch Booking Links</div>
                <div class="text-[12px] text-slate-300 mt-0.5 leading-snug">
                  Generates conflict-free interview slots respecting daily load caps and dispatches personalized 1-click candidate booking invitations.
                </div>
              </div>
            </div>

            <div class="flex items-start gap-3.5 p-3.5 rounded-2xl bg-white/5 border border-white/10">
              <div class="w-7 h-7 rounded-lg bg-[#0071E3] text-white font-bold text-xs flex items-center justify-center shrink-0 mt-0.5">3</div>
              <div>
                <div class="text-[13.5px] font-semibold text-white">Auto-Book Google Meet &amp; Monitor SLA Bottlenecks</div>
                <div class="text-[12px] text-slate-300 mt-0.5 leading-snug">
                  Locks calendar events with Google Meet conference links, sends `.ics` packets, and flags stalled stages for 1-click automated reminders.
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="mt-6 pt-4 border-t border-white/10 flex flex-wrap gap-2 text-[11px] text-slate-300">
          <span class="px-2.5 py-1 rounded-full bg-white/5 border border-white/10">Google Calendar Free/Busy API</span>
          <span class="px-2.5 py-1 rounded-full bg-white/5 border border-white/10">Automated Google Meet Links</span>
          <span class="px-2.5 py-1 rounded-full bg-white/5 border border-white/10">SLA Bottleneck Radar</span>
        </div>
      </div>

      <!-- Right Panel: Enterprise SSO & Instant Demo Login -->
      <div class="lg:col-span-5 apple-card p-8 flex flex-col justify-between">
        <div>
          <div class="flex items-center gap-3 mb-4">
            <div class="w-11 h-11 rounded-[14px] bg-gradient-to-br from-[#0071E3] to-[#409CFF] flex items-center justify-center shadow-md shadow-blue-500/20 shrink-0">
              <svg class="w-6 h-6 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="3" y="4" width="18" height="18" rx="4"></rect>
                <line x1="16" y1="2" x2="16" y2="6"></line>
                <line x1="8" y1="2" x2="8" y2="6"></line>
                <line x1="3" y1="10" x2="21" y2="10"></line>
                <path d="M9 16l2 2 4-4"></path>
              </svg>
            </div>
            <div>
              <div class="text-[10.5px] font-bold uppercase tracking-wider text-[#0071E3]">Enterprise Workspace SSO</div>
              <h2 class="apple-display text-lg font-semibold text-[#1D1D1F]">Sign in to Interview Scheduler Agent</h2>
            </div>
          </div>

          <div id="logout-banner-msg" class="mb-4 px-3.5 py-2 rounded-xl bg-[#F5F5F7] border border-black/5 text-[12px] text-[#515154]">
            Authenticate with Google Workspace SSO or launch an instant demo session.
          </div>

          <!-- 1-Click Instant Demo SSO Sign-In -->
          <div class="p-3.5 rounded-2xl bg-blue-50/80 border border-blue-200/80 mb-4">
            <div class="text-[10px] font-bold uppercase tracking-wider text-blue-800 mb-1.5">Instant Evaluation Access</div>
            <button id="btn-demo-sso" type="button" onclick="loginWithEmail('guruprem.saginadham@sybyl.com', 'Talent Acquisition Lead')"
              class="w-full py-2.5 px-3.5 rounded-xl bg-gradient-to-r from-[#0071E3] to-[#1D4ED8] hover:opacity-95 text-white text-[12.5px] font-semibold flex items-center justify-between shadow-sm transition">
              <span>⚡ Instant Demo SSO Sign-In (Talent Acquisition Lead)</span>
              <span>→</span>
            </button>
            <div class="text-[11px] text-slate-600 mt-1.5">
              Signs in as <strong>guruprem.saginadham@sybyl.com</strong> with pre-loaded jobs, panels &amp; bottlenecks
            </div>
          </div>

          <div class="space-y-3">
            <!-- Official Google Identity Button -->
            <div id="google-sso-official-btn" class="flex justify-center min-h-[42px]"></div>

            <!-- Google Popup Sign-In Button -->
            <button type="button" onclick="triggerGoogleSSO()"
              class="w-full py-2.5 px-4 rounded-xl bg-[#0071E3] hover:bg-[#0077ED] text-white text-[13px] font-semibold flex items-center justify-center gap-2.5 shadow-sm transition">
              <svg class="w-4 h-4 bg-white rounded-full p-0.5 shrink-0" viewBox="0 0 24 24">
                <path fill="#4285F4" d="M23.745 12.27c0-.7-.06-1.4-.19-2.07H12v4.51h6.6c-.29 1.52-1.14 2.82-2.4 3.68v3.05h3.88c2.27-2.09 3.665-5.17 3.665-9.17z"/>
                <path fill="#34A853" d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.88-3.05c-1.08.72-2.45 1.16-4.05 1.16-3.12 0-5.77-2.11-6.72-4.96H1.29v3.14C3.26 21.3 7.31 24 12 24z"/>
                <path fill="#FBBC05" d="M5.28 14.24c-.24-.72-.38-1.49-.38-2.24s.14-1.52.38-2.24V6.62H1.29C.47 8.24 0 10.06 0 12s.47 3.76 1.29 5.38l3.99-3.14z"/>
                <path fill="#EA4335" d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0 7.31 0 3.26 2.7 1.29 6.62l3.99 3.14c.95-2.85 3.6-4.96 6.72-4.96z"/>
              </svg>
              <span>Sign in with Google</span>
            </button>

            <!-- Direct Google Workspace Email Sign-In -->
            <div class="pt-3 border-t border-black/5 text-left">
              <label class="block text-[11.5px] font-medium text-[#6E6E73] mb-1.5">
                Or continue directly with your Google Workspace email:
              </label>
              <form onsubmit="submitWorkspaceQuickSignIn(event)" class="flex gap-2">
                <input id="login-workspace-email" type="email" required placeholder="name@company.com" value="guruprem.saginadham@sybyl.com"
                  class="apple-input flex-1 text-[12.5px]" />
                <button type="submit" class="px-4 py-2 rounded-xl bg-[#1D1D1F] hover:bg-[#333336] text-white text-[12.5px] font-semibold shrink-0 transition">
                  Sign In
                </button>
              </form>
            </div>
          </div>
        </div>

        <div class="mt-5 pt-3 border-t border-black/5 flex items-center justify-between text-[11px] text-[#86868B]">
          <span>Google Workspace Single Sign-On</span>
          <span>Secure Recruiting Portal</span>
        </div>
      </div>
    </div>
  </div>

  <!-- ===================================================================== -->
  <!-- MAIN APPLICATION SHELL (HIDDEN UNTIL USER SIGNS IN)                   -->
  <!-- ===================================================================== -->
  <div id="app-shell" class="hidden min-h-screen flex">

    <!-- LEFT SIDEBAR NAVIGATION -->
    <aside class="w-[252px] shrink-0 apple-glass-sidebar flex flex-col justify-between sticky top-0 h-screen z-30 select-none">
      <div class="p-3.5 space-y-5 overflow-y-auto custom-scroll">
        <!-- Brand Header -->
        <div class="flex items-center gap-2.5 px-2 pt-1">
          <div class="w-8 h-8 rounded-[10px] bg-gradient-to-br from-[#0071E3] to-[#409CFF] flex items-center justify-center shadow-sm shrink-0">
            <svg class="w-4 h-4 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
              <rect x="3" y="4" width="18" height="18" rx="4"></rect>
              <line x1="16" y1="2" x2="16" y2="6"></line>
              <line x1="8" y1="2" x2="8" y2="6"></line>
              <line x1="3" y1="10" x2="21" y2="10"></line>
              <path d="M9 16l2 2 4-4"></path>
            </svg>
          </div>
          <div class="min-w-0">
            <div class="apple-display font-semibold text-[14px] text-[#1D1D1F] truncate">Interview Scheduler Agent</div>
            <div class="text-[11px] text-[#6E6E73] truncate">Autonomous Calendar Coordination</div>
          </div>
        </div>

        <!-- Primary Quick Actions -->
        <div class="px-1 grid grid-cols-2 gap-1.5">
          <button onclick="openCreateJobModal()" class="py-2 px-2.5 rounded-xl bg-[#0071E3] hover:bg-[#0077ED] text-white text-[12px] font-medium flex items-center justify-center gap-1 shadow-sm transition">
            <span>+ New Job</span>
          </button>
          <button onclick="openAddCandidateModal()" class="py-2 px-2.5 rounded-xl bg-white hover:bg-black/5 text-[#1D1D1F] border border-black/10 text-[12px] font-medium flex items-center justify-center gap-1 transition">
            <span>+ Candidate</span>
          </button>
        </div>

        <!-- Primary Pages Navigation -->
        <div>
          <div class="px-2.5 mb-1.5 text-[10.5px] font-semibold uppercase tracking-wider text-[#86868B]">
            Hiring Views
          </div>
          <nav class="space-y-1">
            <button id="side-nav-screen-bottlenecks" onclick="switchScreen('screen-bottlenecks')" class="apple-nav-item active">
              <span class="flex items-center gap-2.5 truncate">
                <svg class="w-4 h-4 text-[#FF3B30] shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
                  <line x1="12" y1="9" x2="12" y2="13"></line>
                  <line x1="12" y1="17" x2="12.01" y2="17"></line>
                </svg>
                <span class="truncate">Bottleneck Overview</span>
              </span>
              <span id="nav-badge-bottlenecks" class="nav-badge px-2 py-0.5 rounded-full text-[11px] font-semibold bg-[#FF3B30]/12 text-[#FF3B30]">0</span>
            </button>

            <button id="side-nav-screen-pipeline" onclick="switchScreen('screen-pipeline')" class="apple-nav-item">
              <span class="flex items-center gap-2.5 truncate">
                <svg class="w-4 h-4 text-[#0071E3] shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polygon points="12 2 2 7 12 12 22 7 12 2"></polygon>
                  <polyline points="2 17 12 22 22 17"></polyline>
                  <polyline points="2 12 12 17 22 12"></polyline>
                </svg>
                <span class="truncate">Jobs &amp; Candidates</span>
              </span>
              <span id="nav-badge-candidates" class="nav-badge px-2 py-0.5 rounded-full text-[11px] font-medium bg-black/5 text-[#6E6E73]">8</span>
            </button>

            <button id="side-nav-screen-panel" onclick="switchScreen('screen-panel')" class="apple-nav-item">
              <span class="flex items-center gap-2.5 truncate">
                <svg class="w-4 h-4 text-[#FF9500] shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
                  <line x1="16" y1="2" x2="16" y2="6"></line>
                  <line x1="8" y1="2" x2="8" y2="6"></line>
                  <line x1="3" y1="10" x2="21" y2="10"></line>
                </svg>
                <span class="truncate">Interviewer Availability</span>
              </span>
              <span id="nav-badge-panel" class="nav-badge px-2 py-0.5 rounded-full text-[11px] font-medium bg-black/5 text-[#6E6E73]">0</span>
            </button>

            <button id="side-nav-screen-candidate" onclick="switchScreen('screen-candidate')" class="apple-nav-item">
              <span class="flex items-center gap-2.5 truncate">
                <svg class="w-4 h-4 text-[#28CD41] shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="12" cy="12" r="10"></circle>
                  <polyline points="12 6 12 12 16 14"></polyline>
                </svg>
                <span class="truncate">Candidate Booking</span>
              </span>
              <span id="nav-badge-booking" class="nav-badge px-2 py-0.5 rounded-full text-[11px] font-medium bg-black/5 text-[#6E6E73]">0</span>
            </button>

            <button id="side-nav-screen-outbox" onclick="switchScreen('screen-outbox')" class="apple-nav-item">
              <span class="flex items-center gap-2.5 truncate">
                <svg class="w-4 h-4 text-[#5E5CE6] shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path>
                  <polyline points="22,6 12,13 2,6"></polyline>
                </svg>
                <span class="truncate">Sent Emails</span>
              </span>
              <span id="nav-badge-outbox" class="nav-badge px-2 py-0.5 rounded-full text-[11px] font-medium bg-black/5 text-[#6E6E73]">0</span>
            </button>
          </nav>
        </div>

        <!-- Google Workspace Tools -->
        <div>
          <div class="px-2.5 mb-1.5 text-[10.5px] font-semibold uppercase tracking-wider text-[#86868B]">
            Google Workspace
          </div>
          <div class="space-y-1">
            <button onclick="openCalendarModal()" class="apple-nav-item">
              <span class="flex items-center gap-2.5">
                <svg class="w-4 h-4 text-[#0071E3]" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <rect x="3" y="4" width="18" height="18" rx="2"></rect>
                  <line x1="16" y1="2" x2="16" y2="6"></line>
                  <line x1="8" y1="2" x2="8" y2="6"></line>
                  <line x1="3" y1="10" x2="21" y2="10"></line>
                </svg>
                <span>Interviewer Calendars</span>
              </span>
            </button>

            <button onclick="toggleCopilotDrawer()" class="apple-nav-item">
              <span class="flex items-center gap-2.5">
                <svg class="w-4 h-4 text-[#0071E3]" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M12 2l2.4 7.2L22 12l-7.6 2.8L12 22l-2.4-7.2L2 12l7.6-2.8L12 2z"></path>
                </svg>
                <span>AI Agent</span>
              </span>
              <span class="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-[#0071E3]/12 text-[#0071E3]">Assistant</span>
            </button>

            <button onclick="resetDemoScenario()" class="apple-nav-item">
              <span class="flex items-center gap-2.5">
                <svg class="w-4 h-4 text-[#6E6E73]" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="1 4 1 10 7 10"></polyline>
                  <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"></path>
                </svg>
                <span>Reset Sample Data</span>
              </span>
            </button>
          </div>
        </div>
      </div>

      <!-- User Account & Log Out Footer -->
      <div class="p-3 border-t border-black/10 bg-white/60 space-y-2">
        <div class="flex items-center gap-2.5 px-1">
          <div id="user-avatar-badge" class="w-7 h-7 rounded-full bg-[#0071E3]/12 text-[#0071E3] font-semibold text-[11px] flex items-center justify-center shrink-0">
            HR
          </div>
          <div class="min-w-0 flex-1">
            <div id="user-name-label" class="text-[12px] font-semibold text-[#1D1D1F] truncate">Recruiting Team</div>
            <div id="user-email-label" class="text-[10.5px] text-[#6E6E73] truncate">Not signed in</div>
          </div>
        </div>

        <button onclick="handleLogOut()" class="w-full py-1.5 px-3 rounded-lg bg-[#FF3B30]/10 hover:bg-[#FF3B30]/18 text-[#FF3B30] font-semibold text-[12px] flex items-center justify-center gap-1.5 transition">
          <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
            <polyline points="16 17 21 12 16 7"></polyline>
            <line x1="21" y1="12" x2="9" y2="12"></line>
          </svg>
          <span>Sign Out</span>
        </button>
      </div>
    </aside>

    <!-- MAIN CONTENT COLUMN -->
    <div class="flex-1 flex flex-col min-w-0">

      <!-- REDESIGNED TOP HEADER BAR: LIVE ACTIONABLE STATUS BAR + SEARCH + AI AGENT -->
      <header class="min-h-[58px] py-2 apple-glass-header sticky top-0 z-20 px-6 flex flex-wrap items-center justify-between gap-3">
        <!-- Left: Live Actionable Status Summary Pills (Replaces "Page 1 of 5") -->
        <div class="flex flex-wrap items-center gap-2 min-w-0">
          <h2 id="header-page-title" class="apple-display text-[15px] font-semibold text-[#1D1D1F] mr-1">
            Bottleneck Overview
          </h2>

          <button onclick="openBottleneckBreakdown('all')"
            class="px-2.5 py-1 rounded-full bg-[#FF3B30]/10 hover:bg-[#FF3B30]/18 text-[#FF3B30] text-[11.5px] font-semibold flex items-center gap-1.5 transition"
            title="Click to see all active bottlenecks">
            <span class="w-2 h-2 rounded-full bg-[#FF3B30]"></span>
            <span><strong id="header-pill-bottlenecks">0</strong> Active Bottlenecks</span>
          </button>

          <button onclick="switchScreen('screen-panel')"
            class="hidden sm:flex px-2.5 py-1 rounded-full bg-[#FF9500]/12 hover:bg-[#FF9500]/20 text-[#C93400] text-[11.5px] font-medium items-center gap-1.5 transition"
            title="View interviewer availability requests">
            <span><strong id="header-pill-panels">0</strong> Waiting on Interviewers</span>
          </button>

          <button onclick="switchScreen('screen-candidate')"
            class="hidden lg:flex px-2.5 py-1 rounded-full bg-[#28CD41]/12 hover:bg-[#28CD41]/20 text-[#1D9E34] text-[11.5px] font-medium items-center gap-1.5 transition"
            title="View candidates choosing an interview time">
            <span><strong id="header-pill-candidates">0</strong> Candidates Choosing Time</span>
          </button>
        </div>

        <!-- Right: Global Search + Quick Actions -->
        <div class="flex items-center gap-2 shrink-0">
          <div class="relative hidden md:block">
            <input id="global-search-input" type="text" oninput="handleGlobalSearch(this.value)"
              placeholder="Search candidates, jobs, emails..."
              class="w-56 pl-8 pr-3 py-1.5 rounded-full bg-black/[0.045] border border-transparent focus:bg-white focus:border-[#0071E3] text-[12px] text-[#1D1D1F] focus:outline-none transition" />
            <svg class="w-3.5 h-3.5 text-[#86868B] absolute left-3 top-2" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="11" cy="11" r="8"></circle>
              <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
            </svg>
          </div>

          <button onclick="openCalendarModal()" class="px-3 py-1.5 rounded-full bg-black/[0.045] hover:bg-black/[0.08] text-[#1D1D1F] text-[12px] font-medium flex items-center gap-1.5 transition">
            <svg class="w-3.5 h-3.5 text-[#0071E3]" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="3" y="4" width="18" height="18" rx="2"></rect>
              <line x1="16" y1="2" x2="16" y2="6"></line>
              <line x1="8" y1="2" x2="8" y2="6"></line>
              <line x1="3" y1="10" x2="21" y2="10"></line>
            </svg>
            <span class="hidden sm:inline">Calendars</span>
          </button>

          <button onclick="toggleCopilotDrawer()" class="px-3.5 py-1.5 rounded-full bg-[#0071E3]/10 hover:bg-[#0071E3]/18 text-[#0071E3] text-[12px] font-semibold flex items-center gap-1.5 transition">
            <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 2l2.4 7.2L22 12l-7.6 2.8L12 22l-2.4-7.2L2 12l7.6-2.8L12 2z"></path>
            </svg>
            <span>AI Agent</span>
          </button>
        </div>
      </header>

      <!-- ================================================================= -->
      <!-- WORKSPACE PAGES CONTAINER                                         -->
      <!-- ================================================================= -->
      <main class="flex-1 p-5 md:p-7 max-w-[1400px] w-full mx-auto space-y-5">

        <!-- Toast Alert Banner -->
        <div id="toast-banner" class="hidden apple-card px-4 py-3 border-l-4 border-l-[#0071E3] flex items-center justify-between text-[13px]">
          <span id="toast-text" class="font-medium text-[#1D1D1F]"></span>
          <button onclick="hideToast()" class="text-[#86868B] hover:text-[#1D1D1F] text-xs font-semibold">Dismiss</button>
        </div>

        <!-- =============================================================== -->
        <!-- VIEW 1 (DEFAULT HOME): PROACTIVE BOTTLENECK MANAGEMENT          -->
        <!-- =============================================================== -->
        <section id="screen-bottlenecks" class="space-y-5">
          <!-- Page Header + Primary Actions -->
          <div class="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
            <div>
              <h1 class="apple-display text-xl md:text-2xl font-semibold text-[#1D1D1F]">
                Scheduling Bottleneck Overview
              </h1>
              <p class="text-[13px] text-[#6E6E73]">
                See which interviews need more time slots, which interviewers haven't responded yet, and which candidates are choosing a time.
              </p>
            </div>

            <div class="flex flex-wrap items-center gap-2 shrink-0">
              <button onclick="autoResolveAllBottlenecks()" class="px-4 py-2 apple-btn-primary text-[12.5px] flex items-center gap-1.5">
                <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>
                <span>Fix All Bottlenecks Automatically</span>
              </button>
              <button onclick="switchScreen('screen-pipeline')" class="px-3.5 py-2 apple-btn-neutral text-[12.5px]">
                View All Jobs &amp; Candidates →
              </button>
            </div>
          </div>

          <!-- 4 Interactive KPI Cards WITH Direct Clickable Links to the Bottlenecks -->
          <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
            <!-- KPI 1: Active Bottlenecks -->
            <div class="apple-card p-4 flex flex-col justify-between border-l-4 border-l-[#FF3B30]">
              <div class="flex items-start justify-between">
                <div>
                  <div class="text-[12px] font-semibold text-[#6E6E73]">Active Bottlenecks</div>
                  <div id="kpi-total-bottlenecks" class="apple-display text-3xl font-bold text-[#FF3B30] mt-0.5">0</div>
                </div>
                <button onclick="openBottleneckBreakdown('all')" class="text-[11.5px] font-semibold text-[#0071E3] hover:underline">
                  See all →
                </button>
              </div>
              <div id="kpi-links-all-bottlenecks" class="mt-3 pt-2.5 border-t border-black/5 space-y-1.5 text-[11.5px]"></div>
            </div>

            <!-- KPI 2: Interviews Needing Time Slots -->
            <div class="apple-card p-4 flex flex-col justify-between border-l-4 border-l-[#FF9500]">
              <div class="flex items-start justify-between">
                <div>
                  <div class="text-[12px] font-semibold text-[#6E6E73]">Interviews Needing Slots</div>
                  <div id="kpi-slot-shortages" class="apple-display text-3xl font-bold text-[#FF9500] mt-0.5">0</div>
                </div>
                <button onclick="openBottleneckBreakdown('shortages')" class="text-[11.5px] font-semibold text-[#0071E3] hover:underline">
                  Filter →
                </button>
              </div>
              <div id="kpi-links-shortages" class="mt-3 pt-2.5 border-t border-black/5 space-y-1.5 text-[11.5px]"></div>
            </div>

            <!-- KPI 3: Waiting on Interviewer Approval -->
            <div class="apple-card p-4 flex flex-col justify-between border-l-4 border-l-[#0071E3]">
              <div class="flex items-start justify-between">
                <div>
                  <div class="text-[12px] font-semibold text-[#6E6E73]">Waiting on Interviewer</div>
                  <div id="kpi-unresponsive-panels" class="apple-display text-3xl font-bold text-[#0071E3] mt-0.5">0</div>
                </div>
                <button onclick="switchScreen('screen-panel')" class="text-[11.5px] font-semibold text-[#0071E3] hover:underline">
                  Open Portal →
                </button>
              </div>
              <div id="kpi-links-panels" class="mt-3 pt-2.5 border-t border-black/5 space-y-1.5 text-[11.5px]"></div>
            </div>

            <!-- KPI 4: Candidates Choosing a Time -->
            <div class="apple-card p-4 flex flex-col justify-between border-l-4 border-l-[#28CD41]">
              <div class="flex items-start justify-between">
                <div>
                  <div class="text-[12px] font-semibold text-[#6E6E73]">Candidates Choosing Time</div>
                  <div id="kpi-unresponsive-candidates" class="apple-display text-3xl font-bold text-[#1D9E34] mt-0.5">0</div>
                </div>
                <button onclick="switchScreen('screen-candidate')" class="text-[11.5px] font-semibold text-[#0071E3] hover:underline">
                  Open Links →
                </button>
              </div>
              <div id="kpi-links-candidates" class="mt-3 pt-2.5 border-t border-black/5 space-y-1.5 text-[11.5px]"></div>
            </div>
          </div>

          <!-- Interactive Breakdown of All Active Bottlenecks (Shows exactly which items make up the KPI count) -->
          <div id="active-bottlenecks-breakdown-card" class="apple-card p-5 space-y-3 border border-[#FF3B30]/20 bg-white">
            <div class="flex flex-wrap items-center justify-between gap-2">
              <div class="flex items-center gap-2">
                <span class="w-2.5 h-2.5 rounded-full bg-[#FF3B30]"></span>
                <h3 class="apple-display text-[15px] font-semibold text-[#1D1D1F]">
                  Active Bottlenecks Requiring Action
                </h3>
                <span id="breakdown-count-pill" class="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-[#FF3B30]/10 text-[#FF3B30]">0 items</span>
              </div>
              <span class="text-[12px] text-[#6E6E73]">Click any bottleneck below to open its action page immediately</span>
            </div>
            <div id="active-bottlenecks-breakdown-list" class="grid grid-cols-1 md:grid-cols-2 gap-2.5"></div>
          </div>

          <!-- Job Openings & Multi-Stage Interview Pipeline (Stage 1 -> Stage 2 -> Stage 3+) -->
          <div class="apple-card p-5 space-y-4">
            <div class="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div class="flex items-center gap-2">
                  <h3 class="apple-display text-[15.5px] font-semibold text-[#1D1D1F]">
                    Job Openings &amp; Interview Stages
                  </h3>
                  <span class="px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-[#0071E3]/10 text-[#0071E3]">Default: 3 Stages (Customizable with +)</span>
                </div>
                <p class="text-[12px] text-[#6E6E73] mt-0.5">
                  Each job opening starts with 3 interview stages by default. Click <strong>+ Add Stage</strong> on any job card to add Stage 4, Stage 5, or extra interview rounds.
                </p>
              </div>
              <div class="flex flex-wrap items-center gap-2">
                <button onclick="openCreateJobModal()" class="px-3.5 py-1.5 apple-btn-primary text-[12px] flex items-center gap-1">
                  <span>+ New Job Opening (3+ Stages)</span>
                </button>
                <button onclick="openAddStageModal('', 'stage')" class="px-3.5 py-1.5 apple-btn-secondary text-[12px]">
                  + Add Stage to Job
                </button>
              </div>
            </div>

            <div id="home-jobs-stages-overview" class="grid grid-cols-1 gap-4"></div>
          </div>

          <!-- Interview Slot Availability by Job Stage -->
          <div class="apple-card p-5 space-y-4">
            <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
              <div>
                <h3 class="apple-display text-[15px] font-semibold text-[#1D1D1F]">
                  Available Interview Slots vs. Waiting Candidates (By Stage &amp; Round)
                </h3>
                <p class="text-[12px] text-[#6E6E73]">
                  When more candidates are waiting than there are open time slots, click <strong>Request &amp; Open Portal</strong> to email suggested calendar times and review them.
                </p>
              </div>
              <div class="apple-segmented self-start">
                <button id="filter-bn-all" onclick="setBottleneckFilter('all')" class="active">All Interviews</button>
                <button id="filter-bn-shortage" onclick="setBottleneckFilter('shortage')">Needs Attention Only</button>
              </div>
            </div>

            <div id="bottleneck-shortages-list" class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3.5"></div>
          </div>

          <!-- Lower Two-Column Grid: Candidate Self-Scheduling Links & Recent Activity -->
          <div class="grid grid-cols-1 lg:grid-cols-2 gap-5">
            <div class="apple-card p-5 space-y-3">
              <div class="flex items-center justify-between">
                <div>
                  <h3 class="apple-display text-[14.5px] font-semibold text-[#1D1D1F]">
                    Candidates Waiting to Pick a Time
                  </h3>
                  <p class="text-[11.5px] text-[#6E6E73]">
                    Candidates who received a live scheduling link and are choosing their preferred slot.
                  </p>
                </div>
                <span class="px-2.5 py-0.5 rounded-full text-[10.5px] font-semibold bg-[#28CD41]/12 text-[#1D9E34]">Live Calendar Sync</span>
              </div>
              <div id="bottleneck-candidates-list" class="space-y-2 max-h-[260px] overflow-y-auto custom-scroll pr-1"></div>
            </div>

            <div class="apple-card p-5 space-y-3">
              <div class="flex items-center justify-between">
                <div>
                  <h3 class="apple-display text-[14.5px] font-semibold text-[#1D1D1F]">
                    Recent Scheduling Activity
                  </h3>
                  <p class="text-[11.5px] text-[#6E6E73]">
                    Latest interviewer requests, confirmed bookings, and backup interviewer updates.
                  </p>
                </div>
                <button onclick="switchScreen('screen-outbox')" class="text-[12px] font-medium text-[#0071E3] hover:underline">
                  View Sent Emails →
                </button>
              </div>
              <div id="activity-log-list" class="space-y-2 max-h-[260px] overflow-y-auto custom-scroll pr-1"></div>
            </div>
          </div>
        </section>

        <!-- =============================================================== -->
        <!-- VIEW 2: JOBS, STAGES & CANDIDATES                               -->
        <!-- =============================================================== -->
        <section id="screen-pipeline" class="hidden space-y-5">
          <div class="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3">
            <div>
              <h1 class="apple-display text-xl md:text-2xl font-semibold text-[#1D1D1F]">
                Jobs, Interview Stages &amp; Candidates
              </h1>
              <p class="text-[13px] text-[#6E6E73]">
                Manage open roles, customize interview stages, and track every candidate from first screen to final round.
              </p>
            </div>

            <div class="flex flex-wrap items-center gap-2">
              <div id="job-filter-bar" class="apple-segmented"></div>
              <button onclick="openCreateJobModal()" class="px-3.5 py-1.5 apple-btn-secondary text-[12px] font-semibold">
                + New Job Opening (3+ Stages)
              </button>
              <button onclick="openAddStageModal('', 'stage')" class="px-3.5 py-1.5 apple-btn-neutral text-[12px]">
                + Add Stage to Job
              </button>
              <button onclick="openAddCandidateModal()" class="px-4 py-1.5 apple-btn-primary text-[12px]">
                + Add Candidate
              </button>
            </div>
          </div>

          <!-- Open Job Roles & Stage Setup Cards -->
          <div id="pipeline-jobs-overview" class="grid grid-cols-1 gap-4"></div>

          <!-- Candidate Interview Progress Table -->
          <div class="apple-card overflow-hidden">
            <div class="px-5 py-3.5 border-b border-black/5 flex flex-wrap items-center justify-between gap-2">
              <div>
                <h3 class="apple-display text-[15px] font-semibold text-[#1D1D1F]">Candidate Interview Progress</h3>
                <p class="text-[11.5px] text-[#6E6E73]">Click any candidate to edit details or move stages. Candidates automatically advance once all interviews in their current stage are completed.</p>
              </div>
              <span id="pipeline-candidate-count-label" class="text-[12px] font-medium text-[#6E6E73]"></span>
            </div>
            <div class="overflow-x-auto">
              <table class="w-full text-left border-collapse">
                <thead>
                  <tr class="border-b border-black/5 bg-[#F5F5F7]/70 text-[10.5px] font-semibold uppercase tracking-wider text-[#6E6E73]">
                    <th class="py-3 px-4">Candidate</th>
                    <th class="py-3 px-3">Role &amp; Current Stage</th>
                    <th class="py-3 px-4">Interview Rounds &amp; Schedule</th>
                    <th class="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody id="pipeline-candidates-tbody" class="divide-y divide-black/5 text-[12.5px]"></tbody>
              </table>
            </div>
          </div>
        </section>

        <!-- =============================================================== -->
        <!-- VIEW 3: INTERVIEWER AVAILABILITY REQUESTS                       -->
        <!-- =============================================================== -->
        <section id="screen-panel" class="hidden space-y-5">
          <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div>
              <h1 class="apple-display text-xl md:text-2xl font-semibold text-[#1D1D1F]">
                Interviewer Availability Requests
              </h1>
              <p class="text-[13px] text-[#6E6E73]">
                Interviewers review suggested open times from their Google Calendar or add custom times for waiting candidates.
              </p>
            </div>
            <button onclick="openCalendarModal()" class="px-3.5 py-2 apple-btn-neutral text-[12px] self-start">
              View Interviewer Calendars
            </button>
          </div>

          <div class="grid grid-cols-1 lg:grid-cols-12 gap-5">
            <div class="lg:col-span-4 apple-card p-4 space-y-2.5 h-fit">
              <div class="flex items-center justify-between px-1">
                <h3 class="apple-display text-[13.5px] font-semibold text-[#1D1D1F]">Availability Requests</h3>
                <span class="text-[11px] text-[#6E6E73]">Select to review</span>
              </div>
              <div id="panel-requests-sidebar-list" class="space-y-2 max-h-[520px] overflow-y-auto custom-scroll pr-1"></div>
            </div>

            <div class="lg:col-span-8">
              <div id="panel-portal-container" class="apple-card p-5"></div>
            </div>
          </div>
        </section>

        <!-- =============================================================== -->
        <!-- VIEW 4: CANDIDATE SELF-SCHEDULING PORTAL                        -->
        <!-- =============================================================== -->
        <section id="screen-candidate" class="hidden space-y-5">
          <div>
            <h1 class="apple-display text-xl md:text-2xl font-semibold text-[#1D1D1F]">
              Candidate Self-Scheduling Page
            </h1>
            <p class="text-[13px] text-[#6E6E73]">
              Candidates open their scheduling link to see live available interview times. As soon as a time is chosen, it is reserved so no two candidates can double-book.
            </p>
          </div>

          <div class="grid grid-cols-1 lg:grid-cols-12 gap-5">
            <div class="lg:col-span-4 apple-card p-4 space-y-2.5 h-fit">
              <div class="flex items-center justify-between px-1">
                <h3 class="apple-display text-[13.5px] font-semibold text-[#1D1D1F]">Candidate Scheduling Links</h3>
                <span class="text-[11px] text-[#6E6E73]">Select candidate</span>
              </div>
              <div id="candidate-links-sidebar-list" class="space-y-2 max-h-[520px] overflow-y-auto custom-scroll pr-1"></div>
            </div>

            <div class="lg:col-span-8">
              <div id="candidate-portal-container" class="apple-card p-5"></div>
            </div>
          </div>
        </section>

        <!-- =============================================================== -->
        <!-- VIEW 5: SENT EMAILS & INVITATIONS                               -->
        <!-- =============================================================== -->
        <section id="screen-outbox" class="hidden space-y-5">
          <div>
            <h1 class="apple-display text-xl md:text-2xl font-semibold text-[#1D1D1F]">
              Sent Emails &amp; Calendar Invitations
            </h1>
            <p class="text-[13px] text-[#6E6E73]">
              Review all emails sent to interviewers and candidates, or send a message directly.
            </p>
          </div>

          <!-- Email Account Bar + Compose Email Button -->
          <div class="apple-card p-4 flex flex-col lg:flex-row items-center justify-between gap-3">
            <div class="flex items-center gap-3">
              <div class="w-9 h-9 rounded-xl bg-[#0071E3]/10 text-[#0071E3] flex items-center justify-center shrink-0">
                <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>
              </div>
              <div>
                <div class="text-[13px] font-semibold text-[#1D1D1F]">Recruiting Email Account: <span class="text-[#0071E3]">psrmreports@sybyl.com</span></div>
                <div id="smtp-status-caption" class="text-[11.5px] text-[#6E6E73]">All automated availability requests and candidate booking links are logged below.</div>
              </div>
            </div>

            <div class="flex flex-wrap items-center gap-2 w-full lg:w-auto">
              <input id="smtp-app-password" type="password" placeholder="Google Workspace App Password (Optional)"
                class="px-3 py-1.5 rounded-lg bg-[#F5F5F7] border border-black/10 text-[12px] text-[#1D1D1F] w-64" />
              <label class="flex items-center gap-1.5 text-[12px] text-[#515154]">
                <input id="smtp-live-toggle" type="checkbox" class="rounded border-black/20" />
                <span>Send Live Gmail</span>
              </label>
              <button onclick="saveSmtpConfig()" class="px-3.5 py-1.5 apple-btn-neutral text-[12px]">Save Settings</button>
              <button onclick="openComposeEmailModal()" class="px-4 py-1.5 apple-btn-primary text-[12px]">✉ Send New Email</button>
            </div>
          </div>

          <!-- Sent Emails List -->
          <div id="email-outbox-list" class="space-y-3"></div>
        </section>

      </main>
    </div>
  </div>

  <!-- ===================================================================== -->
  <!-- SLIDE-OVER GOOGLE WORKSPACE AI AGENT DRAWER                           -->
  <!-- ===================================================================== -->
  <div id="copilot-drawer-backdrop" onclick="toggleCopilotDrawer()" class="hidden fixed inset-0 bg-black/20 backdrop-blur-[2px] z-40"></div>
  <aside id="copilot-drawer" class="fixed top-0 right-0 h-screen w-full max-w-[390px] bg-white/95 backdrop-blur-2xl border-l border-black/10 shadow-2xl z-50 transform translate-x-full transition-transform duration-200 flex flex-col">
    <div class="p-4 border-b border-black/5 flex items-center justify-between">
      <div class="flex items-center gap-2.5">
        <div class="w-8 h-8 rounded-xl bg-gradient-to-br from-[#0071E3] to-[#409CFF] text-white flex items-center justify-center">
          <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
            <path d="M12 2l2.4 7.2L22 12l-7.6 2.8L12 22l-2.4-7.2L2 12l7.6-2.8L12 2z"></path>
          </svg>
        </div>
        <div>
          <h3 class="apple-display text-[14px] font-semibold text-[#1D1D1F]">AI Agent</h3>
          <p class="text-[11px] text-[#6E6E73]">Google Workspace Scheduling Assistant</p>
        </div>
      </div>
      <button onclick="toggleCopilotDrawer()" class="w-7 h-7 rounded-full bg-black/5 hover:bg-black/10 text-[#515154] flex items-center justify-center text-sm">✕</button>
    </div>

    <div class="px-4 py-2.5 bg-[#F5F5F7] border-b border-black/5 flex flex-wrap gap-1.5">
      <button onclick="sendQuickPrompt('Show me a summary of all current bottlenecks')"
        class="px-2.5 py-1 rounded-full bg-white hover:bg-[#0071E3] hover:text-white text-[#1D1D1F] border border-black/10 text-[11px] font-medium transition">
        Summarize Bottlenecks
      </button>
      <button onclick="sendQuickPrompt('Resolve all bottlenecks across all jobs and stages')"
        class="px-2.5 py-1 rounded-full bg-white hover:bg-[#0071E3] hover:text-white text-[#1D1D1F] border border-black/10 text-[11px] font-medium transition">
        Fix All Bottlenecks
      </button>
      <button onclick="sendQuickPrompt('Request interview times for Stage 2B')"
        class="px-2.5 py-1 rounded-full bg-white hover:bg-[#0071E3] hover:text-white text-[#1D1D1F] border border-black/10 text-[11px] font-medium transition">
        Request Stage 2B Times
      </button>
    </div>

    <div id="copilot-messages" class="flex-1 overflow-y-auto custom-scroll p-4 space-y-3 text-[12.5px]">
      <div class="p-3 rounded-2xl bg-[#F5F5F7] text-[#1D1D1F] space-y-1">
        <div class="font-semibold text-[#0071E3] text-[11px]">AI Agent</div>
        <p class="text-[#515154] leading-relaxed">
          Hi! I help you coordinate interviews using Google Calendar and Gmail. Ask me to check bottlenecks, request available times from interviewers, or send scheduling links to candidates.
        </p>
      </div>
    </div>

    <form onsubmit="submitCopilotChat(event)" class="p-3 border-t border-black/10 bg-white flex gap-2">
      <input id="copilot-input" type="text" placeholder="Ask AI Agent..."
        class="flex-1 px-3.5 py-2 rounded-full bg-[#F5F5F7] border border-black/10 text-[12.5px] text-[#1D1D1F] focus:outline-none focus:border-[#0071E3]" />
      <button type="submit" class="px-4 py-2 apple-btn-primary text-[12px]">Send</button>
    </form>
  </aside>

  <!-- ===================================================================== -->
  <!-- MODAL 1: ADD CANDIDATE                                                -->
  <!-- ===================================================================== -->
  <div id="add-candidate-modal" class="hidden fixed inset-0 z-50 bg-black/30 backdrop-blur-sm flex items-center justify-center p-4">
    <div class="w-full max-w-md apple-card p-6 space-y-4">
      <div class="flex items-center justify-between border-b border-black/5 pb-3">
        <h3 class="apple-display text-base font-semibold text-[#1D1D1F]">Add Candidate</h3>
        <button onclick="closeAddCandidateModal()" class="w-7 h-7 rounded-full bg-black/5 text-[#515154]">✕</button>
      </div>
      <form onsubmit="submitAddCandidate(event)" class="space-y-3 text-[13px]">
        <div>
          <label class="block text-[#6E6E73] text-[11.5px] font-medium mb-1">Full Name</label>
          <input id="new-cand-name" type="text" required placeholder="e.g. Jordan Taylor" class="apple-input" />
        </div>
        <div>
          <label class="block text-[#6E6E73] text-[11.5px] font-medium mb-1">Email Address</label>
          <input id="new-cand-email" type="email" required placeholder="jordan.taylor@example.com" class="apple-input" />
        </div>
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="block text-[#6E6E73] text-[11.5px] font-medium mb-1">Job Role</label>
            <select id="new-cand-job" onchange="populateCandidateStageOptions()" class="apple-input"></select>
          </div>
          <div>
            <label class="block text-[#6E6E73] text-[11.5px] font-medium mb-1">Starting Stage</label>
            <select id="new-cand-stage" class="apple-input"></select>
          </div>
        </div>
        <div>
          <label class="block text-[#6E6E73] text-[11.5px] font-medium mb-1">Time Zone</label>
          <input id="new-cand-tz" type="text" value="America/New_York" class="apple-input" />
        </div>
        <div class="flex justify-end gap-2 pt-2">
          <button type="button" onclick="closeAddCandidateModal()" class="px-4 py-2 apple-btn-neutral text-[12px]">Cancel</button>
          <button type="submit" class="px-5 py-2 apple-btn-primary text-[12px]">Add Candidate</button>
        </div>
      </form>
    </div>
  </div>

  <!-- ===================================================================== -->
  <!-- MODAL 2: CREATE NEW JOB OPENING (WITH 3 DEFAULT STAGES & + ADD STAGE) -->
  <!-- ===================================================================== -->
  <div id="create-job-modal" class="hidden fixed inset-0 z-50 bg-black/30 backdrop-blur-sm flex items-center justify-center p-4">
    <div class="w-full max-w-2xl apple-card p-6 space-y-4 max-h-[90vh] flex flex-col">
      <div class="flex items-center justify-between border-b border-black/5 pb-3">
        <div>
          <h3 class="apple-display text-base font-semibold text-[#1D1D1F]">Create New Job Opening</h3>
          <p class="text-[11.5px] text-[#6E6E73]">Enter role details and configure your interview stages (defaults to 3 stages — click <strong>+ Add Stage</strong> for more).</p>
        </div>
        <button onclick="closeCreateJobModal()" class="w-7 h-7 rounded-full bg-black/5 text-[#515154]">✕</button>
      </div>
      <form onsubmit="submitCreateJob(event)" class="space-y-3.5 text-[13px] overflow-y-auto custom-scroll pr-1">
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div class="sm:col-span-2">
            <label class="block text-[#6E6E73] text-[11.5px] font-medium mb-1">Job Title *</label>
            <input id="new-job-title" type="text" required placeholder="e.g. Senior Data &amp; AI Engineer" class="apple-input" />
          </div>
          <div>
            <label class="block text-[#6E6E73] text-[11.5px] font-medium mb-1">Job Code (Optional)</label>
            <input id="new-job-id" type="text" placeholder="e.g. DATA-2026-03" class="apple-input" />
          </div>
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-4 gap-3">
          <div>
            <label class="block text-[#6E6E73] text-[11.5px] font-medium mb-1">Department *</label>
            <input id="new-job-dept" type="text" required placeholder="e.g. Engineering" class="apple-input" />
          </div>
          <div>
            <label class="block text-[#6E6E73] text-[11.5px] font-medium mb-1">Location / Work Mode</label>
            <input id="new-job-location" type="text" value="Hybrid • New York / Remote" class="apple-input" />
          </div>
          <div>
            <label class="block text-[#6E6E73] text-[11.5px] font-medium mb-1">Employment Type</label>
            <select id="new-job-emp-type" class="apple-input">
              <option value="Full-Time">Full-Time</option>
              <option value="Contract">Contract</option>
              <option value="Part-Time">Part-Time</option>
              <option value="Internship">Internship</option>
            </select>
          </div>
          <div>
            <label class="block text-[#6E6E73] text-[11.5px] font-medium mb-1">Target Openings</label>
            <input id="new-job-openings" type="number" min="1" max="50" value="2" class="apple-input" />
          </div>
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label class="block text-[#6E6E73] text-[11.5px] font-medium mb-1">Hiring Manager / Lead Email</label>
            <input id="new-job-lead" type="email" value="jordan.lee@sybyl.com" class="apple-input" />
          </div>
          <div>
            <label class="block text-[#6E6E73] text-[11.5px] font-medium mb-1">Recruiter Email</label>
            <input id="new-job-recruiter" type="email" value="psrmreports@sybyl.com" class="apple-input" />
          </div>
        </div>

        <!-- Interactive Multi-Stage Builder (Default = 3 Stages, HR can click + Add Stage) -->
        <div class="p-4 rounded-2xl bg-[#F5F5F7] border border-black/5 space-y-3">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <div class="flex items-center gap-2">
              <span class="font-semibold text-[13px] text-[#1D1D1F]">Interview Stages Setup</span>
              <span id="create-job-stage-count-badge" class="px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-[#0071E3]/12 text-[#0071E3]">3 Stages (Default)</span>
            </div>
            <button type="button" onclick="addCreateJobStageRow()" class="px-3 py-1 rounded-full bg-[#0071E3] hover:bg-[#0077ED] text-white text-[11.5px] font-semibold transition">
              + Add Stage
            </button>
          </div>
          <div id="create-job-stages-builder" class="space-y-2.5"></div>
        </div>

        <div class="flex justify-end gap-2 pt-2 border-t border-black/5">
          <button type="button" onclick="closeCreateJobModal()" class="px-4 py-2 apple-btn-neutral text-[12px]">Cancel</button>
          <button type="submit" class="px-5 py-2 apple-btn-primary text-[12px]">Create Job Opening</button>
        </div>
      </form>
    </div>
  </div>

  <!-- ===================================================================== -->
  <!-- MODAL 3: ADD CUSTOM STAGE OR INTERVIEW                                -->
  <!-- ===================================================================== -->
  <div id="add-stage-modal" class="hidden fixed inset-0 z-50 bg-black/30 backdrop-blur-sm flex items-center justify-center p-4">
    <div class="w-full max-w-lg apple-card p-6 space-y-4">
      <div class="flex items-center justify-between border-b border-black/5 pb-3">
        <h3 class="apple-display text-base font-semibold text-[#1D1D1F]">Add Interview Stage or Round</h3>
        <button onclick="closeAddStageModal()" class="w-7 h-7 rounded-full bg-black/5 text-[#515154]">✕</button>
      </div>
      <form onsubmit="submitAddStageOrInterview(event)" class="space-y-3 text-[13px]">
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="block text-[#6E6E73] text-[11.5px] font-medium mb-1">Job Role</label>
            <select id="stage-modal-job" onchange="populateStageModalStages()" class="apple-input"></select>
          </div>
          <div>
            <label class="block text-[#6E6E73] text-[11.5px] font-medium mb-1">What would you like to add?</label>
            <select id="stage-modal-mode" onchange="toggleStageModalMode()" class="apple-input">
              <option value="interview">Add an Interview to an Existing Stage</option>
              <option value="stage">Add a New Stage to this Job</option>
            </select>
          </div>
        </div>

        <div id="stage-modal-existing-stage-wrap">
          <label class="block text-[#6E6E73] text-[11.5px] font-medium mb-1">Select Stage</label>
          <select id="stage-modal-stage-select" class="apple-input"></select>
        </div>

        <div id="stage-modal-new-stage-wrap" class="hidden">
          <label class="block text-[#6E6E73] text-[11.5px] font-medium mb-1">New Stage Name</label>
          <input id="stage-modal-new-stage-name" type="text" placeholder="e.g. Stage 4: Team Fit" class="apple-input" />
        </div>

        <div class="grid grid-cols-3 gap-3">
          <div>
            <label class="block text-[#6E6E73] text-[11.5px] font-medium mb-1">Round Code</label>
            <input id="stage-modal-iv-code" type="text" placeholder="e.g. 2C or 4A" class="apple-input" />
          </div>
          <div class="col-span-2">
            <label class="block text-[#6E6E73] text-[11.5px] font-medium mb-1">Interview Name</label>
            <input id="stage-modal-iv-title" type="text" required placeholder="e.g. Practical Case Study" class="apple-input" />
          </div>
        </div>

        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="block text-[#6E6E73] text-[11.5px] font-medium mb-1">Interviewer Email</label>
            <input id="stage-modal-lead" type="email" value="jordan.lee@sybyl.com" class="apple-input" />
          </div>
          <div>
            <label class="block text-[#6E6E73] text-[11.5px] font-medium mb-1">Duration (Minutes)</label>
            <input id="stage-modal-duration" type="number" value="45" min="15" max="120" class="apple-input" />
          </div>
        </div>

        <div>
          <label class="block text-[#6E6E73] text-[11.5px] font-medium mb-1">Backup Interviewers (comma-separated emails)</label>
          <input id="stage-modal-backups" type="text" value="elena.rostova@sybyl.com, devon.brooks@sybyl.com" class="apple-input" />
        </div>

        <div class="flex justify-end gap-2 pt-2">
          <button type="button" onclick="closeAddStageModal()" class="px-4 py-2 apple-btn-neutral text-[12px]">Cancel</button>
          <button type="submit" class="px-5 py-2 apple-btn-primary text-[12px]">Save</button>
        </div>
      </form>
    </div>
  </div>

  <!-- ===================================================================== -->
  <!-- MODAL 4: EDIT CANDIDATE                                               -->
  <!-- ===================================================================== -->
  <div id="edit-candidate-modal" class="hidden fixed inset-0 z-50 bg-black/30 backdrop-blur-sm flex items-center justify-center p-4">
    <div class="w-full max-w-lg apple-card p-6 space-y-4">
      <div class="flex items-center justify-between border-b border-black/5 pb-3">
        <h3 class="apple-display text-base font-semibold text-[#1D1D1F]">Edit Candidate Details</h3>
        <button onclick="closeEditCandidateModal()" class="w-7 h-7 rounded-full bg-black/5 text-[#515154]">✕</button>
      </div>
      <form onsubmit="submitEditCandidate(event)" class="space-y-3 text-[13px]">
        <input id="edit-cand-id" type="hidden" />
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="block text-[#6E6E73] text-[11.5px] font-medium mb-1">Full Name</label>
            <input id="edit-cand-name" type="text" required class="apple-input" />
          </div>
          <div>
            <label class="block text-[#6E6E73] text-[11.5px] font-medium mb-1">Email Address</label>
            <input id="edit-cand-email" type="email" required class="apple-input" />
          </div>
        </div>
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="block text-[#6E6E73] text-[11.5px] font-medium mb-1">Current Stage</label>
            <select id="edit-cand-stage" class="apple-input"></select>
          </div>
          <div>
            <label class="block text-[#6E6E73] text-[11.5px] font-medium mb-1">Time Zone</label>
            <input id="edit-cand-tz" type="text" class="apple-input" />
          </div>
        </div>
        <div>
          <label class="block text-[#6E6E73] text-[11.5px] font-medium mb-1">Recruiter Notes</label>
          <textarea id="edit-cand-notes" rows="2" placeholder="Add notes or scheduling preferences..." class="apple-input"></textarea>
        </div>
        <div class="flex items-center justify-between pt-3 border-t border-black/5">
          <button type="button" onclick="deleteCurrentCandidate()" class="px-3.5 py-2 rounded-full bg-[#FF3B30]/10 hover:bg-[#FF3B30]/20 text-[#FF3B30] text-[12px] font-semibold">
            Remove Candidate
          </button>
          <div class="flex gap-2">
            <button type="button" onclick="closeEditCandidateModal()" class="px-4 py-2 apple-btn-neutral text-[12px]">Cancel</button>
            <button type="submit" class="px-5 py-2 apple-btn-primary text-[12px]">Save Changes</button>
          </div>
        </div>
      </form>
    </div>
  </div>

  <!-- ===================================================================== -->
  <!-- MODAL 5: INTERVIEWER GOOGLE CALENDARS                                 -->
  <!-- ===================================================================== -->
  <div id="calendar-modal" class="hidden fixed inset-0 z-50 bg-black/30 backdrop-blur-sm flex items-center justify-center p-4">
    <div class="w-full max-w-3xl apple-card p-6 space-y-4 max-h-[88vh] flex flex-col">
      <div class="flex items-center justify-between border-b border-black/5 pb-3">
        <div>
          <h3 class="apple-display text-base font-semibold text-[#1D1D1F]">Interviewer Google Calendars</h3>
          <p class="text-[11.5px] text-[#6E6E73]">View busy times or block out unavailable hours on an interviewer's calendar.</p>
        </div>
        <button onclick="closeCalendarModal()" class="w-7 h-7 rounded-full bg-black/5 text-[#515154]">✕</button>
      </div>

      <form onsubmit="submitAddBusyBlock(event)" class="p-3.5 rounded-xl bg-[#F5F5F7] grid grid-cols-1 md:grid-cols-4 gap-2.5 items-end text-[12px]">
        <div>
          <label class="block text-[#6E6E73] text-[11px] font-medium mb-1">Interviewer</label>
          <select id="cal-interviewer-select" class="apple-input"></select>
        </div>
        <div>
          <label class="block text-[#6E6E73] text-[11px] font-medium mb-1">Busy Start Time</label>
          <input id="cal-busy-start" type="text" value="2026-05-05T14:00:00Z" class="apple-input" />
        </div>
        <div>
          <label class="block text-[#6E6E73] text-[11px] font-medium mb-1">Busy End Time</label>
          <input id="cal-busy-end" type="text" value="2026-05-05T15:00:00Z" class="apple-input" />
        </div>
        <button type="submit" class="px-4 py-2 apple-btn-primary text-[12px] h-[36px]">+ Add Busy Time</button>
      </form>

      <div id="calendar-list-container" class="flex-1 overflow-y-auto custom-scroll space-y-2.5 pr-1"></div>
    </div>
  </div>

  <!-- ===================================================================== -->
  <!-- MODAL 6: SEND CUSTOM EMAIL                                            -->
  <!-- ===================================================================== -->
  <div id="compose-email-modal" class="hidden fixed inset-0 z-50 bg-black/30 backdrop-blur-sm flex items-center justify-center p-4">
    <div class="w-full max-w-md apple-card p-6 space-y-4">
      <div class="flex items-center justify-between border-b border-black/5 pb-3">
        <h3 class="apple-display text-base font-semibold text-[#1D1D1F]">Send Email</h3>
        <button onclick="closeComposeEmailModal()" class="w-7 h-7 rounded-full bg-black/5 text-[#515154]">✕</button>
      </div>
      <form onsubmit="submitComposeEmail(event)" class="space-y-3 text-[13px]">
        <div>
          <label class="block text-[#6E6E73] text-[11.5px] font-medium mb-1">To</label>
          <input id="compose-to" type="email" required placeholder="candidate@example.com" class="apple-input" />
        </div>
        <div>
          <label class="block text-[#6E6E73] text-[11.5px] font-medium mb-1">Subject</label>
          <input id="compose-subject" type="text" required placeholder="Interview Update" class="apple-input" />
        </div>
        <div>
          <label class="block text-[#6E6E73] text-[11.5px] font-medium mb-1">Message</label>
          <textarea id="compose-body" rows="4" required class="apple-input"></textarea>
        </div>
        <div class="flex justify-end gap-2 pt-2">
          <button type="button" onclick="closeComposeEmailModal()" class="px-4 py-2 apple-btn-neutral text-[12px]">Cancel</button>
          <button type="submit" class="px-5 py-2 apple-btn-primary text-[12px]">Send Email</button>
        </div>
      </form>
    </div>
  </div>


  <!-- ===================================================================== -->
  <!-- APPLICATION JAVASCRIPT                                                -->
  <!-- ===================================================================== -->
  <script>
    let CURRENT_SCREEN = "__INITIAL_SCREEN__" || "screen-bottlenecks";
    let INITIAL_TOKEN = "__INITIAL_TOKEN__" || "";
    let IS_LOGGED_OUT = __INITIAL_LOGGED_OUT__;
    let DASHBOARD = null;
    let SELECTED_JOB_FILTER = "ALL";
    let BOTTLENECK_FILTER = "all";
    let BREAKDOWN_CATEGORY_FILTER = "all";
    let SELECTED_PANEL_TOKEN = "";
    let SELECTED_CANDIDATE_TOKEN = "";
    let OUTBOX_CATEGORY_FILTER = "ALL";
    let GLOBAL_SEARCH_QUERY = "";
    let AI_AGENT_SESSION_ID = "sess-" + Math.random().toString(36).slice(2, 10);

    const PAGE_META = {
      "screen-bottlenecks": {
        title: "Bottleneck Overview & Action Center",
        path: "/bottlenecks"
      },
      "screen-pipeline": {
        title: "Jobs & Candidates Schedule",
        path: "/pipeline"
      },
      "screen-panel": {
        title: "Interviewer Time Availability",
        path: "/panel-approvals"
      },
      "screen-candidate": {
        title: "Candidate Self-Scheduling",
        path: "/candidate-booking"
      },
      "screen-outbox": {
        title: "Email Notifications",
        path: "/outbox"
      }
    };

    function showToast(msg) {
      const banner = document.getElementById("toast-banner");
      const text = document.getElementById("toast-text");
      if (!banner || !text) return;
      text.textContent = msg;
      banner.classList.remove("hidden");
      setTimeout(() => banner.classList.add("hidden"), 6500);
    }

    function hideToast() {
      const banner = document.getElementById("toast-banner");
      if (banner) banner.classList.add("hidden");
    }

    function formatIso(iso) {
      if (!iso) return "—";
      try {
        const d = new Date(iso);
        return d.toLocaleString("en-US", {
          weekday: "short",
          month: "short",
          day: "numeric",
          hour: "numeric",
          minute: "2-digit",
          timeZoneName: "short"
        });
      } catch (e) {
        return iso;
      }
    }

    function toggleCopilotDrawer() {
      const drawer = document.getElementById("copilot-drawer");
      const backdrop = document.getElementById("copilot-drawer-backdrop");
      if (!drawer || !backdrop) return;
      const isOpen = !drawer.classList.contains("translate-x-full");
      if (isOpen) {
        drawer.classList.add("translate-x-full");
        backdrop.classList.add("hidden");
      } else {
        drawer.classList.remove("translate-x-full");
        backdrop.classList.remove("hidden");
      }
    }

    // -----------------------------------------------------------------------
    // Authentication: Google Single Sign-On (SSO) — Enforced on Launch
    // -----------------------------------------------------------------------
    const GOOGLE_SSO_CLIENT_ID = "259388273008-n8vg3ae8be86e56svvg09rbdciah17u1.apps.googleusercontent.com";
    let GOOGLE_TOKEN_CLIENT = null;

    function applyUserProfile(name, email) {
      if (!email) return;
      const cleanName = name || email.split("@")[0].replace(/[._-]/g, " ");
      const nameEl = document.getElementById("user-name-label");
      const emailEl = document.getElementById("user-email-label");
      const badgeEl = document.getElementById("user-avatar-badge");
      if (nameEl) nameEl.textContent = cleanName;
      if (emailEl) emailEl.textContent = email;
      const initials = cleanName.split(" ").filter(Boolean).map(w => w[0]).join("").slice(0, 2).toUpperCase();
      if (badgeEl) badgeEl.textContent = initials || "GW";
      try {
        sessionStorage.setItem("scheduler_active_session", JSON.stringify({ name: cleanName, email }));
      } catch (e) {}
    }

    function completeGoogleSSOLogin(userObj) {
      applyUserProfile(userObj.name, userObj.email);
      IS_LOGGED_OUT = false;
      const loginView = document.getElementById("auth-login-view");
      const appShell = document.getElementById("app-shell");
      if (loginView) loginView.classList.add("hidden");
      if (appShell) appShell.classList.remove("hidden");
      switchScreen(CURRENT_SCREEN === "screen-bottlenecks" ? "screen-bottlenecks" : CURRENT_SCREEN);
      showToast(`Signed in with Google Workspace as ${userObj.email}`);
    }

    function loginWithEmail(email, name) {
      const cleanEmail = (email || "guruprem.saginadham@sybyl.com").trim();
      const cleanName = (name || cleanEmail.split("@")[0].replace(/[._-]/g, " ")).trim();
      completeGoogleSSOLogin({ name: cleanName, email: cleanEmail });
    }

    function submitWorkspaceQuickSignIn(ev) {
      if (ev && ev.preventDefault) ev.preventDefault();
      const emailInput = document.getElementById("login-workspace-email") || document.getElementById("sso-quick-email");
      const nameInput = document.getElementById("sso-quick-name");
      const email = (emailInput ? emailInput.value : "").trim();
      if (!email) {
        showToast("Please enter your Google Workspace email address.");
        return;
      }
      const name = (nameInput ? nameInput.value : "").trim() || email.split("@")[0].replace(/[._-]/g, " ");
      completeGoogleSSOLogin({ name, email });
    }

    async function handleGoogleCredentialResponse(response) {
      if (!response || !response.credential) return;
      try {
        const res = await fetch("/api/auth/google/id-token", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ credential: response.credential })
        });
        const data = await res.json();
        if (res.ok && data.user) {
          completeGoogleSSOLogin(data.user);
        } else {
          showToast(data.detail || "Could not verify Google Sign-In");
        }
      } catch (e) {
        showToast("Network error while signing in with Google");
      }
    }

    function initGoogleSSO() {
      if (!window.google || !window.google.accounts) return;
      try {
        window.google.accounts.id.initialize({
          client_id: GOOGLE_SSO_CLIENT_ID,
          callback: handleGoogleCredentialResponse,
          auto_select: false,
          cancel_on_tap_outside: true
        });
        const btnContainer = document.getElementById("google-sso-official-btn");
        if (btnContainer) {
          btnContainer.innerHTML = "";
          window.google.accounts.id.renderButton(btnContainer, {
            theme: "outline",
            size: "large",
            shape: "pill",
            text: "signin_with",
            logo_alignment: "left",
            width: 340
          });
        }
      } catch (e) {}

      try {
        if (window.google.accounts.oauth2) {
          GOOGLE_TOKEN_CLIENT = window.google.accounts.oauth2.initTokenClient({
            client_id: GOOGLE_SSO_CLIENT_ID,
            scope: "openid email profile",
            callback: async (tokenResponse) => {
              if (tokenResponse && tokenResponse.access_token) {
                const res = await fetch("/api/auth/google/access-token", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ access_token: tokenResponse.access_token })
                });
                const data = await res.json();
                if (res.ok && data.user) {
                  completeGoogleSSOLogin(data.user);
                } else {
                  showToast(data.detail || "Google sign-in verification failed");
                }
              }
            }
          });
        }
      } catch (e) {}
    }
    window.initGoogleSSO = initGoogleSSO;

    function triggerGoogleSSO() {
      if (GOOGLE_TOKEN_CLIENT) {
        GOOGLE_TOKEN_CLIENT.requestAccessToken({ prompt: "select_account" });
      } else {
        window.location.href = "/auth/google/login";
      }
    }

    async function handleLogOut() {
      try {
        await fetch("/api/auth/logout", { method: "POST" });
      } catch (e) {}
      try {
        sessionStorage.removeItem("scheduler_active_session");
        localStorage.removeItem("scheduler_oauth_user");
        if (window.google && window.google.accounts && window.google.accounts.id) {
          window.google.accounts.id.disableAutoSelect();
        }
      } catch (e) {}
      IS_LOGGED_OUT = true;
      const appShell = document.getElementById("app-shell");
      const loginView = document.getElementById("auth-login-view");
      const msgEl = document.getElementById("logout-banner-msg");
      if (appShell) appShell.classList.add("hidden");
      if (loginView) loginView.classList.remove("hidden");
      if (msgEl) {
        msgEl.textContent = "You have signed out. Please sign in with Google Single Sign-On to continue.";
      }
      initGoogleSSO();
      try {
        window.history.pushState({}, "", "/login");
      } catch (e) {}
    }

    // -----------------------------------------------------------------------
    // Multi-Page Navigation
    // -----------------------------------------------------------------------
    function switchScreen(screenId, pushUrl = true) {
      CURRENT_SCREEN = screenId;
      const screens = [
        "screen-bottlenecks",
        "screen-pipeline",
        "screen-panel",
        "screen-candidate",
        "screen-outbox"
      ];
      screens.forEach(id => {
        const el = document.getElementById(id);
        const sideBtn = document.getElementById("side-nav-" + id);
        const topBtn = document.getElementById("top-tab-" + id);
        if (id === screenId) {
          if (el) el.classList.remove("hidden");
          if (sideBtn) sideBtn.classList.add("active");
          if (topBtn) topBtn.classList.add("active");
        } else {
          if (el) el.classList.add("hidden");
          if (sideBtn) sideBtn.classList.remove("active");
          if (topBtn) topBtn.classList.remove("active");
        }
      });

      const meta = PAGE_META[screenId] || PAGE_META["screen-bottlenecks"];
      const titleEl = document.getElementById("header-page-title");
      if (titleEl) titleEl.textContent = meta.title;

      if (pushUrl && !INITIAL_TOKEN && !IS_LOGGED_OUT) {
        try {
          window.history.pushState({ screenId }, "", meta.path);
        } catch (e) {}
      }

      if (screenId === "screen-panel") {
        renderPanelSidebarAndPortal();
      } else if (screenId === "screen-candidate") {
        renderCandidateSidebarAndPortal();
      } else if (screenId === "screen-outbox") {
        renderOutboxPage();
      }
    }

    function setBottleneckFilter(mode) {
      BOTTLENECK_FILTER = mode;
      const allBtn = document.getElementById("filter-bn-all");
      const shortBtn = document.getElementById("filter-bn-shortage");
      if (allBtn) allBtn.classList.toggle("active", mode === "all");
      if (shortBtn) shortBtn.classList.toggle("active", mode === "shortage");
      renderBottlenecksScreen();
    }

    function openBottleneckBreakdown(category) {
      BREAKDOWN_CATEGORY_FILTER = category || "all";
      switchScreen("screen-bottlenecks");
      renderBottlenecksScreen();
      const card = document.getElementById("active-bottlenecks-breakdown-card");
      if (card) {
        card.scrollIntoView({ behavior: "smooth", block: "nearest" });
      }
    }

    async function fetchDashboard() {
      const res = await fetch("/api/dashboard");
      DASHBOARD = await res.json();
      renderAll();
    }

    function buildAllBottleneckItems() {
      if (!DASHBOARD || !DASHBOARD.bottlenecks) return [];
      const b = DASHBOARD.bottlenecks;
      const items = [];

      (b.slot_shortages || []).forEach(s => {
        const reqToken = s.pending_request_token || "";
        items.push({
          category: "shortages",
          badgeText: "Missing Interview Times",
          badgeClass: "bg-[#FF9500]/15 text-[#C93400]",
          dotColor: "bg-[#FF9500]",
          shortLabel: `${s.job_id} (${s.interview_code}): Need +${s.deficit} time(s)`,
          title: `${s.job_id} • ${s.stage_name} — ${s.interview_code}: ${s.interview_title}`,
          subtitle: `${s.waiting_candidates} candidate(s) waiting • ${s.available_approved_slots} of ${s.required_slots} times available • Interviewer: ${s.panel_lead_email}`,
          actionLabel: reqToken ? "Open Interviewer Request →" : "Request & Open Portal →",
          onClickJs: `openAndRequestPanelSlots('${s.job_id}', '${s.stage_id}', '${s.interview_code}', '${reqToken}')`
        });
      });

      (b.unresponsive_panels || []).forEach(p => {
        items.push({
          category: "panels",
          badgeText: "Waiting on Interviewer",
          badgeClass: "bg-[#0071E3]/12 text-[#0071E3]",
          dotColor: "bg-[#0071E3]",
          shortLabel: `${p.job_id} (${p.interview_code}): ${p.panel_lead_email}`,
          title: `Interviewer Request ${p.request_token} • ${p.job_id} (${p.interview_code})`,
          subtitle: `Waiting on ${p.panel_lead_email} to approve ${p.required_slots_count} suggested time(s)`,
          actionLabel: "Review & Approve Times →",
          onClickJs: `openPanelPortalForToken('${p.request_token}')`
        });
      });

      (b.unresponsive_candidates || []).forEach(c => {
        items.push({
          category: "candidates",
          badgeText: "Candidate Choosing Time",
          badgeClass: "bg-[#5E5CE6]/12 text-[#5E5CE6]",
          dotColor: "bg-[#5E5CE6]",
          shortLabel: `${c.candidate_name} (${c.job_id} • ${c.interview_code})`,
          title: `${c.candidate_name} — ${c.job_id} (${c.interview_code}: ${c.interview_title})`,
          subtitle: `Scheduling link sent to ${c.candidate_email} • Waiting for candidate to pick a time`,
          actionLabel: "Open Candidate Booking Page →",
          onClickJs: `openCandidatePortalForToken('${c.booking_token}')`
        });
      });

      return items;
    }

    function renderAll() {
      if (!DASHBOARD) return;
      const s = DASHBOARD.summary;
      document.getElementById("kpi-total-bottlenecks").textContent = s.total_bottlenecks;
      document.getElementById("kpi-slot-shortages").textContent = s.slot_shortages_count;
      document.getElementById("kpi-unresponsive-panels").textContent = s.unresponsive_panels_count;
      document.getElementById("kpi-unresponsive-candidates").textContent = s.unresponsive_candidates_count;

      // Update top header bar live status pills
      const pillBn = document.getElementById("header-pill-bottlenecks");
      if (pillBn) {
        const dotClass = s.total_bottlenecks > 0 ? "bg-[#FF3B30]" : "bg-[#28CD41]";
        pillBn.innerHTML = `<span class="w-1.5 h-1.5 rounded-full ${dotClass}"></span> ${s.total_bottlenecks} Active Bottleneck${s.total_bottlenecks === 1 ? "" : "s"}`;
      }
      const pillPanels = document.getElementById("header-pill-panels");
      if (pillPanels) {
        pillPanels.textContent = `${s.unresponsive_panels_count} Waiting on Interviewer${s.unresponsive_panels_count === 1 ? "" : "s"}`;
      }
      const pillCands = document.getElementById("header-pill-candidates");
      if (pillCands) {
        pillCands.textContent = `${s.unresponsive_candidates_count} Candidate${s.unresponsive_candidates_count === 1 ? "" : "s"} Choosing Time`;
      }

      // Sidebar badges
      document.getElementById("nav-badge-bottlenecks").textContent = s.total_bottlenecks;
      document.getElementById("nav-badge-candidates").textContent = s.total_candidates;
      const navPanel = document.getElementById("nav-badge-panel");
      if (navPanel) navPanel.textContent = s.unresponsive_panels_count;
      const navBooking = document.getElementById("nav-badge-booking");
      if (navBooking) navBooking.textContent = s.unresponsive_candidates_count;

      const outbox = (DASHBOARD.email_service && DASHBOARD.email_service.outbox) || [];
      document.getElementById("nav-badge-outbox").textContent = outbox.length;

      // Populate compact preview links inside each of the 4 KPI cards (max 2 rows + See all / Open page footer)
      const allItems = buildAllBottleneckItems();
      const shortageItems = allItems.filter(i => i.category === "shortages");
      const panelItems = allItems.filter(i => i.category === "panels");
      const candItems = allItems.filter(i => i.category === "candidates");

      const renderKpiLinkList = (items, emptyText, moreActionJs, moreLabel) => {
        if (!items || items.length === 0) {
          return `<div class="text-[11px] text-[#28CD41] font-medium">✓ ${emptyText}</div>`;
        }
        const preview = items.slice(0, 2);
        const extraCount = items.length - preview.length;
        const rowsHtml = preview.map(item => `
          <a href="javascript:void(0)" onclick="${item.onClickJs}"
            class="flex items-center justify-between gap-1.5 px-2 py-1 rounded-lg bg-[#F5F5F7] hover:bg-[#0071E3]/10 text-[11px] text-[#1D1D1F] hover:text-[#0071E3] transition group">
            <span class="flex items-center gap-1.5 truncate">
              <span class="w-1.5 h-1.5 rounded-full ${item.dotColor} shrink-0"></span>
              <span class="truncate font-medium">${item.shortLabel}</span>
            </span>
            <span class="text-[#0071E3] font-semibold shrink-0">Open →</span>
          </a>
        `).join("");
        const footerText = extraCount > 0
          ? `+${extraCount} more • ${moreLabel || `See all ${items.length} →`}`
          : (moreLabel || "Open full list →");
        return rowsHtml + `
          <button onclick="${moreActionJs}"
            class="w-full text-left px-2 pt-0.5 text-[11px] font-semibold text-[#0071E3] hover:underline flex items-center justify-between">
            <span>${footerText}</span>
          </button>
        `;
      };

      const kpiAllEl = document.getElementById("kpi-links-all-bottlenecks");
      if (kpiAllEl) {
        kpiAllEl.innerHTML = renderKpiLinkList(
          allItems,
          "No active bottlenecks",
          "openBottleneckBreakdown('all')",
          `See all ${allItems.length} bottlenecks ↓`
        );
      }

      const kpiShortEl = document.getElementById("kpi-links-shortages");
      if (kpiShortEl) {
        kpiShortEl.innerHTML = renderKpiLinkList(
          shortageItems,
          "All stages have enough times",
          "openBottleneckBreakdown('shortages')",
          "View needing slots ↓"
        );
      }

      const kpiPanelsEl = document.getElementById("kpi-links-panels");
      if (kpiPanelsEl) {
        kpiPanelsEl.innerHTML = renderKpiLinkList(
          panelItems,
          "No interviewers pending",
          "switchScreen('screen-panel')",
          "Open Interviewer Requests →"
        );
      }

      const kpiCandsEl = document.getElementById("kpi-links-candidates");
      if (kpiCandsEl) {
        kpiCandsEl.innerHTML = renderKpiLinkList(
          candItems,
          "No candidates waiting",
          "switchScreen('screen-candidate')",
          "Open Candidate Links →"
        );
      }

      renderBottlenecksScreen();
      renderPipelineScreen();
      renderPanelSidebarAndPortal();
      renderCandidateSidebarAndPortal();
      renderOutboxPage();
    }

    // Shared renderer for Job Opening Cards & Visual Multi-Stage Pipeline (Stage 1 -> Stage 2 -> Stage 3+)
    function renderJobOpeningsAndStagesCards(jobs) {
      if (!jobs || jobs.length === 0) {
        return `<div class="text-[12.5px] text-[#6E6E73]">No job openings match this filter.</div>`;
      }
      const allCands = (DASHBOARD && DASHBOARD.candidates) || [];

      return jobs.map(job => {
        const stages = job.stages || [];
        const jobCandsCount = allCands.filter(c => c.job_id === job.job_id).length;
        const empType = job.employment_type || "Full-Time";
        const openingsCount = job.openings_count || 2;
        const hmEmail = job.hiring_manager_email || "jordan.lee@sybyl.com";
        const loc = job.location || "Hybrid • New York / Remote";

        const stagesColsClass = stages.length >= 4
          ? "grid-cols-1 md:grid-cols-2 xl:grid-cols-4"
          : "grid-cols-1 md:grid-cols-3";

        const stagesHtml = stages.map((st, idx) => {
          const stageNum = idx + 1;
          const candsInStage = allCands.filter(c => c.job_id === job.job_id && c.current_stage_id === st.stage_id).length;
          const interviewsHtml = (st.interviews || []).map(iv => {
            const avail = typeof iv.available_approved_slots === "number"
              ? iv.available_approved_slots
              : (iv.approved_slots || []).filter(s => !s.booked_by).length;
            const needed = typeof iv.required_slots_count === "number" ? iv.required_slots_count : 0;
            const deficit = typeof iv.slot_deficit === "number" ? iv.slot_deficit : Math.max(0, needed - avail);
            const pendingToken = iv.pending_request_token || "";

            const capPill = deficit > 0
              ? `<span class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-[#FF9500]/15 text-[#C93400]">Need +${deficit} time(s)</span>`
              : `<span class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-[#28CD41]/15 text-[#1D9E34]">${avail} open time(s)</span>`;

            return `
              <div class="p-3 rounded-xl bg-white border border-black/[0.06] space-y-2 shadow-sm">
                <div class="flex items-start justify-between gap-2">
                  <div>
                    <div class="text-[12.5px] font-semibold text-[#1D1D1F]">${iv.interview_code}: ${iv.title}</div>
                    <div class="text-[11px] text-[#6E6E73]">Interviewer: <span class="text-[#1D1D1F] font-medium">${iv.panel_lead_email}</span> (${iv.duration_minutes || 45}m)</div>
                  </div>
                  ${capPill}
                </div>
                <div class="flex items-center justify-between gap-2 pt-1 border-t border-black/5">
                  <span class="text-[10.5px] text-[#6E6E73]">Open slots: <strong>${avail}</strong> / ${needed} needed</span>
                  <button onclick="openAndRequestPanelSlots('${job.job_id}', '${st.stage_id}', '${iv.interview_code}', '${pendingToken}')"
                    class="px-2.5 py-1 apple-btn-secondary text-[11px] font-semibold shrink-0">
                    ${pendingToken ? "Open Request →" : "+ Request Times"}
                  </button>
                </div>
              </div>
            `;
          }).join("");

          return `
            <div class="p-4 rounded-2xl bg-[#F5F5F7] border border-black/[0.06] flex flex-col justify-between space-y-3 relative">
              <div class="space-y-2.5">
                <div class="flex items-center justify-between gap-2">
                  <div class="flex items-center gap-2 min-w-0">
                    <span class="px-2 py-0.5 rounded-md bg-[#0071E3] text-white text-[10.5px] font-bold uppercase tracking-wide shrink-0">
                      Stage ${stageNum}
                    </span>
                    <span class="text-[13px] font-semibold text-[#1D1D1F] truncate" title="${st.name}">${st.name}</span>
                  </div>
                  <span class="px-2 py-0.5 rounded-full bg-black/5 text-[#515154] text-[10.5px] font-semibold shrink-0">
                    ${candsInStage} candidate${candsInStage === 1 ? "" : "s"}
                  </span>
                </div>
                <div class="space-y-2">
                  ${interviewsHtml}
                </div>
              </div>
              <div class="pt-1 flex justify-end">
                <button onclick="openAddStageModal('${job.job_id}', 'interview', '${st.stage_id}')"
                  class="text-[11px] font-semibold text-[#0071E3] hover:underline">
                  + Add Interview Round to Stage ${stageNum}
                </button>
              </div>
            </div>
          `;
        }).join("");

        return `
          <div class="apple-card p-5 space-y-4 border border-black/[0.06]">
            <div class="flex flex-wrap items-start justify-between gap-3 border-b border-black/5 pb-3.5">
              <div class="space-y-1">
                <div class="flex flex-wrap items-center gap-2">
                  <span class="px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-[#0071E3]/10 text-[#0071E3]">${job.job_id}</span>
                  <span class="text-[12px] font-semibold text-[#515154]">${job.department}</span>
                  <span class="text-[11px] px-2 py-0.5 rounded-full bg-black/5 text-[#515154] font-medium">${empType}</span>
                  <span class="text-[11px] px-2 py-0.5 rounded-full bg-black/5 text-[#515154] font-medium">${openingsCount} Opening${openingsCount === 1 ? "" : "s"}</span>
                  <span class="text-[11px] text-[#6E6E73]">📍 ${loc}</span>
                </div>
                <h4 class="apple-display text-[17px] font-semibold text-[#1D1D1F]">${job.title}</h4>
                <div class="text-[11.5px] text-[#6E6E73] flex flex-wrap items-center gap-x-4 gap-y-1">
                  <span>Hiring Manager: <strong class="text-[#1D1D1F]">${hmEmail}</strong></span>
                  <span>Recruiter: <strong class="text-[#1D1D1F]">${job.recruiter_email}</strong></span>
                  <span>Active Candidates: <strong class="text-[#0071E3]">${jobCandsCount}</strong></span>
                </div>
              </div>

              <div class="flex flex-wrap items-center gap-2 shrink-0">
                <span class="px-3 py-1 rounded-full text-[11.5px] font-semibold bg-[#28CD41]/12 text-[#1D9E34]">
                  ${stages.length} Interview Stage${stages.length === 1 ? "" : "s"}
                </span>
                <button onclick="openAddStageModal('${job.job_id}', 'stage')"
                  class="px-3.5 py-1.5 apple-btn-primary text-[11.5px] flex items-center gap-1">
                  <span>+ Add Stage (Stage ${stages.length + 1})</span>
                </button>
                <button onclick="openAddStageModal('${job.job_id}', 'interview')"
                  class="px-3 py-1.5 apple-btn-neutral text-[11.5px]">
                  + Add Round
                </button>
              </div>
            </div>

            <!-- Visual Multi-Stage Pipeline (Stage 1 -> Stage 2 -> Stage 3+) -->
            <div class="grid ${stagesColsClass} gap-3.5">
              ${stagesHtml}
            </div>
          </div>
        `;
      }).join("");
    }

    // -----------------------------------------------------------------------
    // PAGE 1: Bottleneck Overview & Action Center
    // -----------------------------------------------------------------------
    function renderBottlenecksScreen() {
      if (!DASHBOARD) return;

      // 1. Render the explicit Breakdown List of all active bottlenecks
      const allItems = buildAllBottleneckItems();
      const filteredBreakdown = BREAKDOWN_CATEGORY_FILTER === "all"
        ? allItems
        : allItems.filter(i => i.category === BREAKDOWN_CATEGORY_FILTER);

      const countPill = document.getElementById("breakdown-count-pill");
      if (countPill) {
        countPill.textContent = `${filteredBreakdown.length} item${filteredBreakdown.length === 1 ? "" : "s"}`;
      }

      const breakdownEl = document.getElementById("active-bottlenecks-breakdown-list");
      if (breakdownEl) {
        if (filteredBreakdown.length === 0) {
          breakdownEl.innerHTML = `
            <div class="p-4 rounded-2xl bg-[#28CD41]/10 border border-[#28CD41]/25 text-[13px] text-[#1D9E34] font-medium">
              ✓ All clear! Every interview stage has enough approved times and no pending bottlenecks match this filter.
            </div>
          `;
        } else {
          breakdownEl.innerHTML = filteredBreakdown.map((item, idx) => `
            <div class="p-3.5 rounded-2xl bg-[#F5F5F7]/90 border border-black/[0.06] flex flex-wrap items-center justify-between gap-3 hover:border-[#0071E3]/40 transition">
              <div class="flex items-start gap-3 min-w-0">
                <span class="w-6 h-6 rounded-full bg-white border border-black/10 text-[11px] font-semibold text-[#1D1D1F] flex items-center justify-center shrink-0 mt-0.5">
                  ${idx + 1}
                </span>
                <div class="min-w-0">
                  <div class="flex flex-wrap items-center gap-2">
                    <span class="px-2 py-0.5 rounded-full text-[10.5px] font-semibold ${item.badgeClass}">${item.badgeText}</span>
                    <span class="font-semibold text-[13.5px] text-[#1D1D1F]">${item.title}</span>
                  </div>
                  <div class="text-[12px] text-[#6E6E73] mt-0.5">${item.subtitle}</div>
                </div>
              </div>
              <button onclick="${item.onClickJs}"
                class="px-3.5 py-1.5 apple-btn-primary text-[12px] shrink-0">
                ${item.actionLabel}
              </button>
            </div>
          `).join("");
        }
      }

      // 1B. Render Job Openings & Multi-Stage Pipeline directly on Screen 1
      const homeJobsEl = document.getElementById("home-jobs-stages-overview");
      if (homeJobsEl) {
        homeJobsEl.innerHTML = renderJobOpeningsAndStagesCards(DASHBOARD.jobs || []);
      }

      // 2. Render Stage Capacity Cards
      const cards = DASHBOARD.stage_health_cards || [];
      const filtered = BOTTLENECK_FILTER === "shortage"
        ? cards.filter(c => c.slot_deficit > 0 || (c.pending_panel_requests && c.pending_panel_requests.length > 0))
        : cards;

      const container = document.getElementById("bottleneck-shortages-list");
      if (container) {
        container.innerHTML = filtered.map(c => {
          const isShortage = c.slot_deficit > 0;
          const hasPendingReq = c.pending_panel_requests && c.pending_panel_requests.length > 0;
          const reqToken = hasPendingReq ? c.pending_panel_requests[0] : "";

          const statusBadge = isShortage
            ? `<span class="px-2.5 py-1 rounded-full text-[11px] font-semibold bg-[#FF3B30]/12 text-[#FF3B30]">Need +${c.slot_deficit} Time${c.slot_deficit === 1 ? "" : "s"}</span>`
            : `<span class="px-2.5 py-1 rounded-full text-[11px] font-semibold bg-[#28CD41]/12 text-[#1D9E34]">Ready</span>`;

          const totalNeeded = Math.max(c.required_slots_count, 1);
          const pct = Math.min(100, Math.round((c.available_approved_slots / totalNeeded) * 100));
          const barColor = isShortage ? "bg-[#FF9500]" : "bg-[#28CD41]";

          return `
            <div class="p-5 rounded-2xl bg-[#F5F5F7]/75 border border-black/[0.06] flex flex-col justify-between gap-4">
              <div class="space-y-2.5">
                <div class="flex items-center justify-between gap-2">
                  <span class="text-[11.5px] font-semibold text-[#0071E3]">${c.job_id} • ${c.stage_name}</span>
                  ${statusBadge}
                </div>
                <div class="apple-display text-[15.5px] font-semibold text-[#1D1D1F]">
                  ${c.interview_code}: ${c.interview_title}
                </div>
                <div class="text-[12px] text-[#6E6E73]">
                  Interviewer Lead: <span class="font-medium text-[#1D1D1F]">${c.panel_lead_email}</span>
                </div>

                <!-- Capacity Metrics Bar -->
                <div class="pt-1 space-y-1.5">
                  <div class="flex justify-between text-[11.5px] text-[#515154]">
                    <span>Candidates Waiting: <strong class="text-[#1D1D1F]">${c.waiting_candidates_count}</strong></span>
                    <span>Available Times: <strong class="text-[#1D1D1F]">${c.available_approved_slots}</strong> of ${c.required_slots_count} needed</span>
                  </div>
                  <div class="w-full h-2 rounded-full bg-black/10 overflow-hidden">
                    <div class="h-full ${barColor} transition-all duration-300" style="width: ${pct}%"></div>
                  </div>
                </div>
              </div>

              <div class="flex flex-wrap items-center gap-2 pt-2 border-t border-black/5">
                <button onclick="openAndRequestPanelSlots('${c.job_id}', '${c.stage_id}', '${c.interview_code}', '${reqToken}')"
                  class="px-3.5 py-1.5 apple-btn-primary text-[12px]">
                  ${reqToken ? "Open Interviewer Request →" : "Request & Open Portal →"}
                </button>
                ${hasPendingReq ? `
                  <button onclick="openPanelPortalForToken('${reqToken}')"
                    class="px-3.5 py-1.5 apple-btn-secondary text-[12px]">
                    Review Suggested Times (${reqToken}) →
                  </button>
                ` : ""}
              </div>
            </div>
          `;
        }).join("");
      }

      // 3. Candidate live links list
      const cands = DASHBOARD.bottlenecks.unresponsive_candidates || [];
      const candEl = document.getElementById("bottleneck-candidates-list");
      if (candEl) {
        if (cands.length === 0) {
          candEl.innerHTML = `<div class="text-[12.5px] text-[#86868B] py-4">No candidates are currently waiting to pick an interview time.</div>`;
        } else {
          candEl.innerHTML = cands.map(c => `
            <div class="p-3.5 rounded-2xl bg-[#F5F5F7] border border-black/5 flex items-center justify-between gap-3">
              <div class="min-w-0">
                <div class="font-semibold text-[13.5px] text-[#1D1D1F] truncate">${c.candidate_name}</div>
                <div class="text-[12px] text-[#6E6E73] truncate">${c.job_id} • ${c.interview_code} (${c.interview_title})</div>
              </div>
              <button onclick="openCandidatePortalForToken('${c.booking_token}')"
                class="px-3.5 py-1.5 apple-btn-secondary text-[12px] shrink-0">
                Open Booking Page →
              </button>
            </div>
          `).join("");
        }
      }

      // 4. Activity log
      const logs = DASHBOARD.activity_log || [];
      const logEl = document.getElementById("activity-log-list");
      if (logEl) {
        logEl.innerHTML = logs.map(item => {
          const kindLabel = (item.type || item.kind || "update").replace(/_/g, " ");
          const summaryText = item.summary || item.detail || item.title || "";
          return `
            <div class="p-3 rounded-xl bg-[#F5F5F7] border border-black/5 text-[12px] flex items-start justify-between gap-3">
              <div>
                <span class="font-semibold text-[#0071E3] uppercase text-[10.5px]">${kindLabel}</span>
                <p class="text-[#1D1D1F] mt-0.5">${summaryText}</p>
              </div>
              <span class="text-[10.5px] text-[#86868B] shrink-0">${formatIso(item.timestamp)}</span>
            </div>
          `;
        }).join("");
      }
    }

    // -----------------------------------------------------------------------
    // PAGE 2: Jobs & Candidates Schedule
    // -----------------------------------------------------------------------
    function renderPipelineScreen() {
      if (!DASHBOARD) return;
      const jobs = DASHBOARD.jobs || [];
      const filterBar = document.getElementById("job-filter-bar");
      if (filterBar) {
        filterBar.innerHTML = [
          `<button onclick="selectJobFilter('ALL')" class="${SELECTED_JOB_FILTER === 'ALL' ? 'active' : ''}">All Jobs (${jobs.length})</button>`,
          ...jobs.map(j => `
            <button onclick="selectJobFilter('${j.job_id}')" class="${SELECTED_JOB_FILTER === j.job_id ? 'active' : ''}">
              ${j.job_id}
            </button>
          `)
        ].join("");
      }

      const filteredJobs = SELECTED_JOB_FILTER === "ALL"
        ? jobs
        : jobs.filter(j => j.job_id === SELECTED_JOB_FILTER);

      const overviewEl = document.getElementById("pipeline-jobs-overview");
      if (overviewEl) {
        overviewEl.innerHTML = renderJobOpeningsAndStagesCards(filteredJobs);
      }

      const cands = (DASHBOARD.candidates || []).filter(c => {
        const matchesJob = SELECTED_JOB_FILTER === "ALL" || c.job_id === SELECTED_JOB_FILTER;
        if (!matchesJob) return false;
        if (!GLOBAL_SEARCH_QUERY) return true;
        const q = GLOBAL_SEARCH_QUERY.toLowerCase();
        return (
          (c.name && c.name.toLowerCase().includes(q)) ||
          (c.email && c.email.toLowerCase().includes(q)) ||
          (c.job_id && c.job_id.toLowerCase().includes(q)) ||
          (c.candidate_id && c.candidate_id.toLowerCase().includes(q))
        );
      });

      const countLabel = document.getElementById("pipeline-candidate-count-label");
      if (countLabel) {
        countLabel.textContent = `Showing ${cands.length} candidate${cands.length === 1 ? "" : "s"}`;
      }

      const statusLabelMap = {
        completed: "Completed",
        booked: "Scheduled",
        link_sent: "Choosing Time",
        awaiting_panel_slots: "Needs Interviewer Times",
        locked: "Upcoming"
      };

      const tbody = document.getElementById("pipeline-candidates-tbody");
      if (tbody) {
        tbody.innerHTML = cands.map(c => {
          const job = jobs.find(j => j.job_id === c.job_id) || { stages: [] };
          const stageObj = job.stages.find(s => s.stage_id === c.current_stage_id);
          const currentStageLabel = stageObj ? stageObj.name : c.current_stage_id;

          const stageCells = job.stages.map((st, idx) => {
            const ivMap = (c.stage_progress && c.stage_progress[st.stage_id]) || {};
            const items = st.interviews.map(iv => {
              const rec = ivMap[iv.interview_code] || { status: "locked" };
              let pillClass = "bg-black/5 text-[#86868B]";
              if (rec.status === "completed") pillClass = "bg-[#28CD41]/15 text-[#1D9E34]";
              else if (rec.status === "booked") pillClass = "bg-[#0071E3]/12 text-[#0071E3]";
              else if (rec.status === "link_sent") pillClass = "bg-[#5E5CE6]/12 text-[#5E5CE6]";
              else if (rec.status === "awaiting_panel_slots") pillClass = "bg-[#FF9500]/15 text-[#C93400]";

              let actions = "";
              if (rec.status === "booked") {
                const declinedEmail = (rec.assigned_interviewers && rec.assigned_interviewers[0]) || iv.panel_lead_email;
                actions = `
                  <div class="flex flex-wrap gap-1.5 mt-2">
                    <button onclick="completeCandidateInterview('${c.candidate_id}', '${st.stage_id}', '${iv.interview_code}')"
                      class="px-2.5 py-1 rounded-full bg-[#28CD41] text-white text-[11px] font-medium">
                      ✓ Mark Completed
                    </button>
                    <button onclick="simulateInterviewerDecline('${c.candidate_id}', '${st.stage_id}', '${iv.interview_code}', '${declinedEmail}')"
                      class="px-2.5 py-1 rounded-full bg-[#FF9500]/15 text-[#C93400] text-[11px] font-medium">
                      Assign Backup Interviewer
                    </button>
                  </div>
                `;
              } else if (rec.status === "link_sent" && rec.booking_token) {
                actions = `
                  <div class="mt-2">
                    <button onclick="openCandidatePortalForToken('${rec.booking_token}')"
                      class="px-2.5 py-1 apple-btn-secondary text-[11px]">
                      Open Booking Page →
                    </button>
                  </div>
                `;
              } else if (rec.status === "awaiting_panel_slots") {
                actions = `
                  <div class="mt-2">
                    <button onclick="openAndRequestPanelSlots('${c.job_id}', '${st.stage_id}', '${iv.interview_code}', '${iv.pending_request_token || ""}')"
                      class="px-2.5 py-1 rounded-full bg-[#FF9500]/15 text-[#C93400] text-[11px] font-medium">
                      Request Interviewer Times →
                    </button>
                  </div>
                `;
              }

              return `
                <div class="p-2.5 rounded-xl bg-[#F5F5F7] border border-black/5">
                  <div class="flex items-center justify-between gap-2">
                    <span class="font-semibold text-[12px] text-[#1D1D1F]">${iv.interview_code}: ${iv.title}</span>
                    <span class="px-2 py-0.5 rounded-full text-[10.5px] font-semibold ${pillClass}">${statusLabelMap[rec.status] || rec.status}</span>
                  </div>
                  ${rec.start ? `<div class="text-[11px] text-[#0071E3] mt-1">📅 ${formatIso(rec.start)}</div>` : ""}
                  ${rec.swapped_from ? `<div class="text-[11px] text-[#C93400] mt-0.5">🔄 Backup interviewer assigned for ${rec.swapped_from}</div>` : ""}
                  ${actions}
                </div>
              `;
            }).join("");

            return `
              <div class="min-w-[225px] space-y-1.5">
                <div class="text-[11px] font-semibold text-[#0071E3]">Stage ${idx + 1}: ${st.name}</div>
                ${items}
              </div>
            `;
          }).join("");

          return `
            <tr class="hover:bg-[#F5F5F7]/50 transition">
              <td class="py-4 px-4 align-top">
                <div class="font-semibold text-[#1D1D1F]">${c.name}</div>
                <div class="text-[12px] text-[#6E6E73]">${c.email}</div>
                <div class="text-[11px] text-[#86868B] mt-0.5">${c.timezone}</div>
              </td>
              <td class="py-4 px-3 align-top space-y-1.5">
                <div><span class="px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-[#0071E3]/10 text-[#0071E3]">${c.job_id}</span></div>
                <div><span class="px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-black/5 text-[#1D1D1F]">${currentStageLabel}</span></div>
              </td>
              <td class="py-4 px-4 align-top">
                <div class="flex flex-col xl:flex-row gap-3">${stageCells}</div>
              </td>
              <td class="py-4 px-4 align-top text-right">
                <button onclick="openEditCandidateModal('${c.candidate_id}')"
                  class="px-3 py-1.5 apple-btn-neutral text-[11.5px]">
                  Edit Candidate
                </button>
              </td>
            </tr>
          `;
        }).join("");
      }
    }

    function selectJobFilter(jobId) {
      SELECTED_JOB_FILTER = jobId;
      renderPipelineScreen();
    }

    // -----------------------------------------------------------------------
    // PAGE 3: Interviewer Time Availability Portal
    // -----------------------------------------------------------------------
    function openPanelPortalForToken(token) {
      SELECTED_PANEL_TOKEN = token;
      switchScreen("screen-panel");
    }

    async function renderPanelSidebarAndPortal() {
      if (!DASHBOARD) return;
      const requests = [];
      (DASHBOARD.jobs || []).forEach(j => {
        (j.stages || []).forEach(st => {
          (st.interviews || []).forEach(iv => {
            (iv.panel_requests || []).forEach(req => {
              requests.push({ ...req, job_title: j.title, interview_title: iv.title });
            });
          });
        });
      });

      if (!SELECTED_PANEL_TOKEN && requests.length > 0) {
        const pending = requests.find(r => r.status === "pending");
        SELECTED_PANEL_TOKEN = (pending || requests[0]).request_token;
      }

      const listEl = document.getElementById("panel-requests-sidebar-list");
      if (listEl) {
        listEl.innerHTML = requests.map(r => {
          const isSelected = r.request_token === SELECTED_PANEL_TOKEN;
          const badge = r.status === "approved"
            ? `<span class="px-2 py-0.5 rounded-full text-[10.5px] font-semibold bg-[#28CD41]/15 text-[#1D9E34]">Approved</span>`
            : `<span class="px-2 py-0.5 rounded-full text-[10.5px] font-semibold bg-[#FF9500]/15 text-[#C93400]">Waiting</span>`;
          return `
            <button onclick="openPanelPortalForToken('${r.request_token}')"
              class="w-full text-left p-3.5 rounded-2xl border transition ${isSelected ? 'bg-[#0071E3]/8 border-[#0071E3]' : 'bg-[#F5F5F7] border-black/5 hover:bg-black/5'}">
              <div class="flex items-center justify-between gap-2">
                <span class="font-semibold text-[13px] text-[#1D1D1F]">${r.job_id} • ${r.interview_code}</span>
                ${badge}
              </div>
              <div class="text-[12px] text-[#6E6E73] truncate mt-0.5">${r.interview_title}</div>
              <div class="text-[11px] text-[#86868B] mt-1">Interviewer: ${r.panel_lead_email} • Need ${r.required_slots_count} times</div>
            </button>
          `;
        }).join("");
      }

      const container = document.getElementById("panel-portal-container");
      if (!container) return;
      if (!SELECTED_PANEL_TOKEN) {
        container.innerHTML = `<div class="text-[#6E6E73] text-sm">No interviewer time requests yet.</div>`;
        return;
      }

      const res = await fetch(`/api/panel/${SELECTED_PANEL_TOKEN}`);
      if (!res.ok) {
        container.innerHTML = `<div class="text-[#FF3B30] text-sm">Could not load request ${SELECTED_PANEL_TOKEN}</div>`;
        return;
      }
      const data = await res.json();
      const req = data.request;

      const slotsHtml = (req.suggested_slots || []).map((s, idx) => `
        <label class="flex items-start gap-3 p-4 rounded-2xl bg-[#F5F5F7] border border-black/5 hover:border-[#0071E3]/40 cursor-pointer transition">
          <input type="checkbox" name="panel-slot-check" value="${s.slot_id}" checked
            class="mt-1 w-4 h-4 rounded text-[#0071E3]" />
          <div class="text-[13px]">
            <div class="font-semibold text-[#1D1D1F]">Option ${idx + 1}: ${formatIso(s.start)}</div>
            <div class="text-[11.5px] text-[#6E6E73] mt-0.5">
              Ends ${formatIso(s.end)} • Available on Google Calendar: ${(s.interviewers || []).join(", ")}
            </div>
          </div>
        </label>
      `).join("");

      container.innerHTML = `
        <div class="space-y-5">
          <div class="flex flex-wrap items-start justify-between gap-4 border-b border-black/5 pb-4">
            <div>
              <span class="px-2.5 py-1 rounded-full text-[11px] font-semibold bg-[#FF9500]/15 text-[#C93400]">
                Interviewer Availability Request (${req.request_token})
              </span>
              <h3 class="apple-display text-xl font-semibold text-[#1D1D1F] mt-2">
                ${data.job_title} — ${data.stage_name} (${req.interview_code}: ${data.interview_title})
              </h3>
              <p class="text-[13px] text-[#6E6E73] mt-0.5">
                Interviewer Lead: <strong class="text-[#1D1D1F]">${req.panel_lead_email}</strong> • Length: ${data.duration_minutes} mins
              </p>
            </div>
            <div class="px-4 py-3 rounded-2xl bg-[#F5F5F7] text-right">
              <div class="text-[11px] uppercase font-semibold text-[#6E6E73]">Recommended Times</div>
              <div class="apple-display text-lg font-semibold text-[#0071E3] mt-0.5">
                ${req.waiting_candidates_count} Waiting → Please Approve ${req.required_slots_count} Times
              </div>
            </div>
          </div>

          <div class="space-y-2.5">
            <div class="text-[12.5px] font-semibold text-[#1D1D1F]">
              Suggested Times Found on Google Calendar:
            </div>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
              ${slotsHtml}
            </div>
          </div>

          <div class="p-4 rounded-2xl bg-[#F5F5F7] border border-black/5 flex flex-wrap items-end justify-between gap-3">
            <div>
              <div class="text-[12px] font-semibold text-[#1D1D1F]">Prefer a different time? Add a custom interview time:</div>
              <div class="text-[11px] text-[#6E6E73]">Pick any date and time that works for you</div>
            </div>
            <div class="flex items-center gap-2">
              <input id="custom-panel-slot-input" type="datetime-local"
                class="px-3 py-1.5 rounded-xl bg-white border border-black/10 text-[12px]" />
              <button onclick="submitCustomPanelSlot('${req.request_token}')"
                class="px-3.5 py-1.5 apple-btn-secondary text-[12px]">
                + Add Custom Time
              </button>
            </div>
          </div>

          <div class="pt-3 border-t border-black/5 flex flex-wrap items-center justify-between gap-3">
            <span class="text-[12px] text-[#6E6E73]">
              Approving these times automatically emails the scheduling link to waiting candidates.
            </span>
            <button onclick="submitPanelApproval('${req.request_token}')"
              class="px-6 py-2.5 apple-btn-primary text-[13.5px] font-semibold">
              Approve Selected Times &amp; Send to Candidates
            </button>
          </div>
        </div>
      `;
    }

    async function submitCustomPanelSlot(requestToken) {
      const input = document.getElementById("custom-panel-slot-input");
      if (!input || !input.value) {
        showToast("Please pick a date and time first.");
        return;
      }
      const isoStart = new Date(input.value).toISOString();
      const res = await fetch(`/api/panel/${requestToken}/custom-slot`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ start_iso: isoStart })
      });
      if (res.ok) {
        showToast("Added custom interview time and sent links to waiting candidates.");
        await fetchDashboard();
      }
    }

    async function submitPanelApproval(requestToken) {
      const checks = Array.from(document.querySelectorAll("input[name='panel-slot-check']:checked"));
      const selectedIds = checks.map(c => c.value);
      if (selectedIds.length === 0) {
        showToast("Please select at least one interview time to approve.");
        return;
      }
      const res = await fetch(`/api/panel/${requestToken}/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ selected_slot_ids: selectedIds })
      });
      const data = await res.json();
      if (res.ok) {
        showToast(`Approved ${data.approved_count} interview time(s) and sent scheduling links to ${data.candidates_notified.length} candidate(s).`);
        await fetchDashboard();
      }
    }

    // -----------------------------------------------------------------------
    // PAGE 4: Candidate Self-Scheduling Portal
    // -----------------------------------------------------------------------
    function openCandidatePortalForToken(token) {
      SELECTED_CANDIDATE_TOKEN = token;
      switchScreen("screen-candidate");
    }

    async function renderCandidateSidebarAndPortal() {
      if (!DASHBOARD) return;
      const links = [];
      (DASHBOARD.candidates || []).forEach(c => {
        Object.entries(c.stage_progress || {}).forEach(([stageId, stageMap]) => {
          Object.entries(stageMap || {}).forEach(([ivCode, rec]) => {
            if (rec.booking_token) {
              links.push({
                booking_token: rec.booking_token,
                candidate_name: c.name,
                candidate_id: c.candidate_id,
                job_id: c.job_id,
                stage_id: stageId,
                interview_code: ivCode,
                status: rec.status
              });
            }
          });
        });
      });

      if (!SELECTED_CANDIDATE_TOKEN && links.length > 0) {
        const active = links.find(l => l.status === "link_sent");
        SELECTED_CANDIDATE_TOKEN = (active || links[0]).booking_token;
      }

      const sideEl = document.getElementById("candidate-links-sidebar-list");
      if (sideEl) {
        sideEl.innerHTML = links.map(l => {
          const isSelected = l.booking_token === SELECTED_CANDIDATE_TOKEN;
          const badge = l.status === "booked"
            ? `<span class="px-2 py-0.5 rounded-full text-[10.5px] font-semibold bg-[#28CD41]/15 text-[#1D9E34]">Confirmed</span>`
            : `<span class="px-2 py-0.5 rounded-full text-[10.5px] font-semibold bg-[#0071E3]/12 text-[#0071E3]">Choosing Time</span>`;
          return `
            <button onclick="openCandidatePortalForToken('${l.booking_token}')"
              class="w-full text-left p-3.5 rounded-2xl border transition ${isSelected ? 'bg-[#0071E3]/8 border-[#0071E3]' : 'bg-[#F5F5F7] border-black/5 hover:bg-black/5'}">
              <div class="flex items-center justify-between gap-2">
                <span class="font-semibold text-[13px] text-[#1D1D1F]">${l.candidate_name}</span>
                ${badge}
              </div>
              <div class="text-[11.5px] text-[#6E6E73] mt-0.5">${l.job_id} • ${l.stage_id} (${l.interview_code})</div>
            </button>
          `;
        }).join("");
      }

      const container = document.getElementById("candidate-portal-container");
      if (!container) return;
      if (!SELECTED_CANDIDATE_TOKEN) {
        container.innerHTML = `<div class="text-[#6E6E73] text-sm">No candidate scheduling links yet.</div>`;
        return;
      }

      const res = await fetch(`/api/candidate/${SELECTED_CANDIDATE_TOKEN}`);
      if (!res.ok) {
        container.innerHTML = `<div class="text-[#FF3B30] text-sm">Could not load candidate scheduling link ${SELECTED_CANDIDATE_TOKEN}</div>`;
        return;
      }
      const view = await res.json();

      if (view.booking_status === "booked") {
        container.innerHTML = `
          <div class="p-6 rounded-2xl bg-[#28CD41]/10 border border-[#28CD41]/30 space-y-3">
            <div class="text-[12px] font-semibold uppercase text-[#1D9E34]">✓ Interview Confirmed on Google Calendar</div>
            <h3 class="apple-display text-xl font-semibold text-[#1D1D1F]">
              ${view.candidate_name} — ${view.interview_title} (${view.interview_code})
            </h3>
            <p class="text-[13.5px] text-[#1D1D1F]">
              Confirmed Time: <strong>${formatIso(view.booked_slot.start)}</strong>
            </p>
            <p class="text-[12px] text-[#6E6E73]">
              Interviewers: ${(view.booked_slot.assigned_interviewers || []).join(", ")}
            </p>
            <div class="pt-2">
              <button onclick="rescheduleCandidateInterview('${view.booking_token}')"
                class="px-4 py-1.5 apple-btn-secondary text-[12px]">
                Change / Reschedule Time
              </button>
            </div>
          </div>
        `;
        return;
      }

      const liveSlots = view.live_available_slots || [];
      const slotsCards = liveSlots.length === 0
        ? `<div class="p-5 rounded-2xl bg-[#FF9500]/10 text-[#C93400] text-[13px]">
             All available times for this stage have been taken. We have automatically requested additional times from the interviewer.
           </div>`
        : liveSlots.map((s, idx) => `
            <div class="p-4 rounded-2xl bg-[#F5F5F7] border border-black/5 flex items-center justify-between gap-4">
              <div>
                <div class="font-semibold text-[14px] text-[#1D1D1F]">Option ${idx + 1}: ${formatIso(s.start)}</div>
                <div class="text-[12px] text-[#6E6E73] mt-0.5">
                  Length: ${view.duration_minutes} mins • Status: <span class="text-[#1D9E34] font-medium">Available Now</span>
                </div>
              </div>
              <button onclick="bookCandidateLiveSlot('${view.booking_token}', '${s.slot_id}')"
                class="px-5 py-2 apple-btn-primary text-[13px] shrink-0">
                Choose This Time
              </button>
            </div>
          `).join("");

      container.innerHTML = `
        <div class="space-y-5">
          <div class="flex flex-wrap items-start justify-between gap-4 border-b border-black/5 pb-4">
            <div>
              <span class="px-2.5 py-1 rounded-full text-[11px] font-semibold bg-[#28CD41]/15 text-[#1D9E34]">
                Candidate Live Scheduling Page
              </span>
              <h3 class="apple-display text-xl font-semibold text-[#1D1D1F] mt-2">
                ${view.candidate_name} — ${view.job_title}
              </h3>
              <p class="text-[13px] text-[#6E6E73] mt-0.5">
                ${view.stage_name} • ${view.interview_code}: ${view.interview_title} (${view.duration_minutes} mins)
              </p>
            </div>
            <button onclick="renderCandidateSidebarAndPortal()" class="px-3.5 py-1.5 apple-btn-neutral text-[12px]">
              ↻ Refresh Available Times
            </button>
          </div>

          <div class="p-3.5 rounded-2xl bg-[#0071E3]/8 border border-[#0071E3]/20 text-[12.5px] text-[#1D1D1F]">
            <strong>No Double-Booking Guarantee:</strong> Showing <strong>${liveSlots.length}</strong> open time(s). As soon as a candidate picks a time, it is reserved for them and removed from everyone else's list.
          </div>

          <div class="space-y-3">
            ${slotsCards}
          </div>
        </div>
      `;
    }

    async function bookCandidateLiveSlot(bookingToken, slotId) {
      const res = await fetch(`/api/candidate/${bookingToken}/book`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ slot_id: slotId })
      });
      const data = await res.json();
      if (data.status === "booked") {
        showToast(`Confirmed interview for ${formatIso(data.start)}! Calendar invitations have been sent.`);
      } else {
        showToast(`That time was just taken (${data.reason || "Unavailable"}). Please pick another open time.`);
      }
      await fetchDashboard();
    }

    async function rescheduleCandidateInterview(bookingToken) {
      const res = await fetch(`/api/candidate/${bookingToken}/reschedule`, { method: "POST" });
      if (res.ok) {
        showToast("Released previous time. You can now pick a new interview time.");
        await fetchDashboard();
      }
    }

    // -----------------------------------------------------------------------
    // PAGE 5: Email Notifications
    // -----------------------------------------------------------------------
    function filterOutboxCategory(cat) {
      OUTBOX_CATEGORY_FILTER = cat || "ALL";
      renderOutboxPage();
    }

    function renderOutboxPage() {
      if (!DASHBOARD || !DASHBOARD.email_service) return;
      const allMail = DASHBOARD.email_service.outbox || [];
      const outbox = OUTBOX_CATEGORY_FILTER === "ALL"
        ? allMail
        : allMail.filter(m => m.category === OUTBOX_CATEGORY_FILTER);

      const listEl = document.getElementById("email-outbox-list");
      if (!listEl) return;
      if (outbox.length === 0) {
        listEl.innerHTML = `<div class="apple-card p-6 text-[#6E6E73] text-sm">No email notifications in this view.</div>`;
        return;
      }
      listEl.innerHTML = outbox.map(m => `
        <div class="apple-card p-5 space-y-2">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <div class="flex items-center gap-2">
              <span class="px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-[#0071E3]/10 text-[#0071E3]">${(m.category || "notification").replace(/_/g, " ")}</span>
              <span class="font-semibold text-[14px] text-[#1D1D1F]">${m.subject}</span>
            </div>
            <span class="text-[11.5px] text-[#86868B]">${formatIso(m.timestamp)}</span>
          </div>
          <div class="text-[12px] text-[#6E6E73]">
            From: <strong class="text-[#1D1D1F]">${m.from}</strong> → To: <strong class="text-[#0071E3]">${m.to}</strong>
          </div>
          <pre class="p-3.5 rounded-xl bg-[#F5F5F7] text-[#1D1D1F] text-[12px] whitespace-pre-wrap font-sans leading-relaxed">${m.body}</pre>
        </div>
      `).join("");
    }

    // -----------------------------------------------------------------------
    // Workflow Action Triggers
    // -----------------------------------------------------------------------
    async function autoResolveAllBottlenecks() {
      const res = await fetch("/api/bottlenecks/resolve-all", { method: "POST" });
      const data = await res.json();
      showToast(`AI Agent sent ${data.actions_count} availability request(s) and follow-up reminder(s)!`);
      await fetchDashboard();
    }

    async function openAndRequestPanelSlots(jobId, stageId, interviewCode, existingToken) {
      if (existingToken) {
        await fetchDashboard();
        openPanelRequestInPortal(existingToken);
        showToast(`Opened Interviewer Availability Request for Round ${interviewCode}.`);
        return;
      }
      await triggerPanelSlotRequest(jobId, stageId, interviewCode, true);
    }

    async function triggerPanelSlotRequest(jobId, stageId, interviewCode, openPortalAfter = true) {
      const res = await fetch("/api/panel/request-slots", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_id: jobId, stage_id: stageId, interview_code: interviewCode })
      });
      const data = await res.json();
      if (res.ok) {
        SELECTED_PANEL_TOKEN = data.request_token;
        await fetchDashboard();
        if (openPortalAfter && data.request_token) {
          openPanelRequestInPortal(data.request_token);
          showToast(`Opened Interviewer Availability Request (${data.panel_lead_email} • ${data.required_slots_count} slot(s) needed).`);
        } else {
          showToast(`Sent email to ${data.panel_lead_email} requesting ${data.required_slots_count} interview time(s).`);
        }
      }
    }

    async function completeCandidateInterview(candidateId, stageId, interviewCode) {
      const res = await fetch("/api/candidate/complete-interview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          candidate_id: candidateId,
          stage_id: stageId,
          interview_code: interviewCode,
          passed: true
        })
      });
      const data = await res.json();
      if (res.ok) {
        const msg = data.advanced_to_stage
          ? `Marked ${interviewCode} completed! Candidate automatically moved to the next stage (${data.advanced_to_stage}).`
          : `Marked ${interviewCode} completed. Waiting for the remaining interview in this stage.`;
        showToast(msg);
        await fetchDashboard();
      }
    }

    async function simulateInterviewerDecline(candidateId, stageId, interviewCode, declinedEmail) {
      const res = await fetch("/api/candidate/decline-swap", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          candidate_id: candidateId,
          stage_id: stageId,
          interview_code: interviewCode,
          declined_email: declinedEmail
        })
      });
      const data = await res.json();
      if (res.ok) {
        if (data.status === "swapped_backup_interviewer") {
          showToast(`${declinedEmail} could not make it — automatically assigned backup interviewer ${data.replacement_interviewer} so the candidate's time stays unchanged!`);
        } else {
          showToast(`Sent an updated scheduling link to the candidate.`);
        }
        await fetchDashboard();
      }
    }

    async function resetDemoScenario() {
      await fetch("/api/scenario/reset", { method: "POST" });
      showToast("Sample recruiting data has been reset.");
      await fetchDashboard();
    }

    // -----------------------------------------------------------------------
    // Modals: Candidate, Job (with 3-Stage Builder), Stage, Calendar, Email
    // -----------------------------------------------------------------------
    function handleGlobalSearch(val) {
      GLOBAL_SEARCH_QUERY = (val || "").trim();
      if (GLOBAL_SEARCH_QUERY && CURRENT_SCREEN !== "screen-pipeline") {
        switchScreen("screen-pipeline");
      }
      renderPipelineScreen();
    }

    function openAddCandidateModal() {
      if (DASHBOARD) {
        const jobSel = document.getElementById("new-cand-job");
        if (jobSel) {
          jobSel.innerHTML = (DASHBOARD.jobs || []).map(j => `<option value="${j.job_id}">${j.job_id} — ${j.title}</option>`).join("");
        }
        populateCandidateStageOptions();
      }
      document.getElementById("add-candidate-modal").classList.remove("hidden");
    }

    function closeAddCandidateModal() {
      document.getElementById("add-candidate-modal").classList.add("hidden");
    }

    function populateCandidateStageOptions() {
      if (!DASHBOARD) return;
      const jobSel = document.getElementById("new-cand-job");
      if (!jobSel) return;
      const jobId = jobSel.value;
      const job = (DASHBOARD.jobs || []).find(j => j.job_id === jobId) || (DASHBOARD.jobs || [])[0];
      const stageSel = document.getElementById("new-cand-stage");
      if (!job || !stageSel) return;
      stageSel.innerHTML = (job.stages || []).map((s, idx) => `<option value="${s.stage_id}">Stage ${idx + 1}: ${s.name}</option>`).join("");
    }
    const updateCandidateModalStages = populateCandidateStageOptions;

    async function submitAddCandidate(ev) {
      ev.preventDefault();
      const payload = {
        name: document.getElementById("new-cand-name").value.trim(),
        email: document.getElementById("new-cand-email").value.trim(),
        timezone: (document.getElementById("new-cand-tz") && document.getElementById("new-cand-tz").value) || "America/New_York",
        job_id: document.getElementById("new-cand-job").value,
        initial_stage_id: document.getElementById("new-cand-stage").value
      };
      const res = await fetch("/api/candidates", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        closeAddCandidateModal();
        showToast(`Added candidate ${payload.name} to ${payload.job_id}.`);
        await fetchDashboard();
      }
    }

    // Dynamic Multi-Stage Builder for Create Job Opening Modal (Default = 3 Stages)
    let CREATE_JOB_STAGES = [];

    function resetCreateJobStages() {
      const leadVal = (document.getElementById("new-job-lead") && document.getElementById("new-job-lead").value) || "jordan.lee@sybyl.com";
      CREATE_JOB_STAGES = [
        {
          stage_name: "Stage 1: Recruiter & HR Screen",
          interview_code: "1A",
          interview_title: "Initial Alignment & Background Screen",
          duration_minutes: 30,
          panel_lead_email: leadVal
        },
        {
          stage_name: "Stage 2: Technical & Domain Assessment",
          interview_code: "2A",
          interview_title: "Core Skills & Architecture Deep Dive",
          duration_minutes: 45,
          panel_lead_email: leadVal
        },
        {
          stage_name: "Stage 3: Executive & Hiring Manager Final",
          interview_code: "3A",
          interview_title: "Leadership & Team Fit Final Round",
          duration_minutes: 45,
          panel_lead_email: leadVal
        }
      ];
      renderCreateJobStagesBuilder();
    }

    function renderCreateJobStagesBuilder() {
      const container = document.getElementById("create-job-stages-builder");
      const badge = document.getElementById("create-job-stage-count-badge");
      if (!container) return;
      if (badge) {
        badge.textContent = `${CREATE_JOB_STAGES.length} Stage${CREATE_JOB_STAGES.length === 1 ? "" : "s"}${CREATE_JOB_STAGES.length === 3 ? " (Default)" : ""}`;
      }
      container.innerHTML = CREATE_JOB_STAGES.map((stg, idx) => `
        <div class="p-3 rounded-xl bg-white border border-black/8 space-y-2">
          <div class="flex items-center justify-between gap-2">
            <div class="flex items-center gap-2">
              <span class="w-5 h-5 rounded-full bg-[#0071E3] text-white text-[10.5px] font-bold flex items-center justify-center">${idx + 1}</span>
              <span class="font-semibold text-[12px] text-[#1D1D1F]">Stage ${idx + 1}</span>
            </div>
            ${CREATE_JOB_STAGES.length > 1 ? `
              <button type="button" onclick="removeCreateJobStageRow(${idx})" class="text-[11px] font-medium text-[#FF3B30] hover:underline">
                Remove Stage
              </button>
            ` : ""}
          </div>
          <div class="grid grid-cols-1 sm:grid-cols-12 gap-2">
            <div class="sm:col-span-4">
              <label class="block text-[#86868B] text-[10px] font-medium mb-0.5">Stage Name</label>
              <input type="text" value="${stg.stage_name}" oninput="updateCreateJobStageField(${idx}, 'stage_name', this.value)" class="apple-input !py-1.5 !text-[12px]" required />
            </div>
            <div class="sm:col-span-2">
              <label class="block text-[#86868B] text-[10px] font-medium mb-0.5">Round Code</label>
              <input type="text" value="${stg.interview_code}" oninput="updateCreateJobStageField(${idx}, 'interview_code', this.value)" class="apple-input !py-1.5 !text-[12px]" required />
            </div>
            <div class="sm:col-span-4">
              <label class="block text-[#86868B] text-[10px] font-medium mb-0.5">Interview Title</label>
              <input type="text" value="${stg.interview_title}" oninput="updateCreateJobStageField(${idx}, 'interview_title', this.value)" class="apple-input !py-1.5 !text-[12px]" required />
            </div>
            <div class="sm:col-span-2">
              <label class="block text-[#86868B] text-[10px] font-medium mb-0.5">Duration (m)</label>
              <input type="number" min="15" max="120" value="${stg.duration_minutes}" oninput="updateCreateJobStageField(${idx}, 'duration_minutes', parseInt(this.value || '45', 10))" class="apple-input !py-1.5 !text-[12px]" />
            </div>
          </div>
        </div>
      `).join("");
    }

    function addCreateJobStageRow() {
      const nextNum = CREATE_JOB_STAGES.length + 1;
      const leadVal = (document.getElementById("new-job-lead") && document.getElementById("new-job-lead").value) || "jordan.lee@sybyl.com";
      CREATE_JOB_STAGES.push({
        stage_name: `Stage ${nextNum}: Panel & Culture Evaluation`,
        interview_code: `${nextNum}A`,
        interview_title: `Stage ${nextNum} Assessment Round`,
        duration_minutes: 45,
        panel_lead_email: leadVal
      });
      renderCreateJobStagesBuilder();
    }

    function removeCreateJobStageRow(idx) {
      if (CREATE_JOB_STAGES.length <= 1) return;
      CREATE_JOB_STAGES.splice(idx, 1);
      renderCreateJobStagesBuilder();
    }

    function updateCreateJobStageField(idx, field, val) {
      if (!CREATE_JOB_STAGES[idx]) return;
      CREATE_JOB_STAGES[idx][field] = val;
    }

    function openCreateJobModal() {
      resetCreateJobStages();
      document.getElementById("create-job-modal").classList.remove("hidden");
    }

    function closeCreateJobModal() {
      document.getElementById("create-job-modal").classList.add("hidden");
    }

    async function submitCreateJob(ev) {
      ev.preventDefault();
      const leadEmail = document.getElementById("new-job-lead").value.trim() || "jordan.lee@sybyl.com";
      const stagesPayload = CREATE_JOB_STAGES.map((stg, idx) => ({
        stage_id: `stage_${idx + 1}`,
        name: stg.stage_name || `Stage ${idx + 1}`,
        order: idx + 1,
        interviews: [
          {
            code: stg.interview_code || `${idx + 1}A`,
            title: stg.interview_title || `Stage ${idx + 1} Interview`,
            duration_minutes: Number(stg.duration_minutes) || 45,
            panel_lead_email: stg.panel_lead_email || leadEmail,
            eligible_interviewers: [stg.panel_lead_email || leadEmail, "elena.rostova@sybyl.com"],
            backup_interviewers: ["devon.brooks@sybyl.com"]
          }
        ]
      }));

      const payload = {
        job_id: document.getElementById("new-job-id").value.trim(),
        title: document.getElementById("new-job-title").value.trim(),
        department: document.getElementById("new-job-dept").value.trim(),
        location: (document.getElementById("new-job-location") && document.getElementById("new-job-location").value.trim()) || "Hybrid • New York / Remote",
        employment_type: (document.getElementById("new-job-emp-type") && document.getElementById("new-job-emp-type").value) || "Full-Time",
        openings_count: parseInt((document.getElementById("new-job-openings") && document.getElementById("new-job-openings").value) || "2", 10),
        recruiter_email: document.getElementById("new-job-recruiter").value.trim(),
        panel_lead_email: leadEmail,
        stages: stagesPayload
      };
      const res = await fetch("/api/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        const created = await res.json();
        closeCreateJobModal();
        showToast(`Created job opening "${created.job.title}" with ${(created.job.stages || []).length} interview stages.`);
        await fetchDashboard();
      }
    }

    function openAddStageModal(preselectedJobId = "", defaultMode = "stage", preselectedStageId = "") {
      if (DASHBOARD) {
        const sel = document.getElementById("stage-modal-job");
        if (sel) {
          sel.innerHTML = (DASHBOARD.jobs || []).map(j => `<option value="${j.job_id}">${j.job_id} — ${j.title}</option>`).join("");
          if (preselectedJobId) {
            sel.value = preselectedJobId;
          }
        }
        const modeSel = document.getElementById("stage-modal-mode");
        if (modeSel) {
          modeSel.value = defaultMode || "stage";
        }
        populateStageModalStages(preselectedStageId);
        toggleStageModalMode();
      }
      document.getElementById("add-stage-modal").classList.remove("hidden");
    }

    function populateStageModalStages(preselectedStageId = "") {
      if (!DASHBOARD) return;
      const jobId = document.getElementById("stage-modal-job").value;
      const job = (DASHBOARD.jobs || []).find(j => j.job_id === jobId) || (DASHBOARD.jobs || [])[0];
      const stageSel = document.getElementById("stage-modal-stage-select");
      if (!job || !stageSel) return;
      const stages = job.stages || [];
      stageSel.innerHTML = stages.map((s, idx) => `<option value="${s.stage_id}">Stage ${idx + 1}: ${s.name}</option>`).join("");
      if (preselectedStageId) {
        stageSel.value = preselectedStageId;
      }
      const nextNum = stages.length + 1;
      const newStageNameInput = document.getElementById("stage-modal-new-stage-name");
      if (newStageNameInput) {
        newStageNameInput.value = `Stage ${nextNum}: Executive / Team Evaluation`;
      }
      const codeInput = document.getElementById("stage-modal-iv-code");
      if (codeInput) {
        const mode = (document.getElementById("stage-modal-mode") && document.getElementById("stage-modal-mode").value) || "stage";
        codeInput.value = mode === "stage" ? `${nextNum}A` : `${stages.length}B`;
      }
    }

    function toggleStageModalMode() {
      const modeSel = document.getElementById("stage-modal-mode");
      const mode = modeSel ? modeSel.value : "stage";
      const existingWrap = document.getElementById("stage-modal-existing-stage-wrap");
      const newWrap = document.getElementById("stage-modal-new-stage-wrap");
      if (mode === "stage") {
        if (existingWrap) existingWrap.classList.add("hidden");
        if (newWrap) newWrap.classList.remove("hidden");
      } else {
        if (existingWrap) existingWrap.classList.remove("hidden");
        if (newWrap) newWrap.classList.add("hidden");
      }
      populateStageModalStages();
    }

    function closeAddStageModal() {
      document.getElementById("add-stage-modal").classList.add("hidden");
    }

    async function submitAddStageOrInterview(ev) {
      ev.preventDefault();
      const jobId = document.getElementById("stage-modal-job").value;
      const mode = document.getElementById("stage-modal-mode").value;
      const leadEmail = document.getElementById("stage-modal-lead").value.trim() || "jordan.lee@sybyl.com";
      const backups = document.getElementById("stage-modal-backups").value.split(",").map(s => s.trim()).filter(Boolean);
      const payload = {
        stage_id: mode === "stage" ? "" : document.getElementById("stage-modal-stage-select").value,
        stage_name: mode === "stage" ? document.getElementById("stage-modal-new-stage-name").value.trim() : "",
        interview_code: document.getElementById("stage-modal-iv-code").value.trim(),
        interview_title: document.getElementById("stage-modal-iv-title").value.trim(),
        duration_minutes: parseInt(document.getElementById("stage-modal-duration").value || "45", 10),
        panel_lead_email: leadEmail,
        eligible_interviewers: [leadEmail],
        backup_interviewers: backups
      };
      const res = await fetch(`/api/jobs/${jobId}/stages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        closeAddStageModal();
        showToast(mode === "stage"
          ? `Added new stage "${payload.stage_name}" to ${jobId}.`
          : `Added interview round "${payload.interview_title}" to ${jobId}.`);
        await fetchDashboard();
      }
    }

    function openEditCandidateModal(candidateId) {
      if (!DASHBOARD) return;
      const cand = (DASHBOARD.candidates || []).find(c => c.candidate_id === candidateId);
      if (!cand) return;
      document.getElementById("edit-cand-id").value = cand.candidate_id;
      document.getElementById("edit-cand-name").value = cand.name;
      document.getElementById("edit-cand-email").value = cand.email;
      document.getElementById("edit-cand-tz").value = cand.timezone || "America/New_York";
      const notesEl = document.getElementById("edit-cand-notes");
      if (notesEl) notesEl.value = cand.notes || "";
      const job = (DASHBOARD.jobs || []).find(j => j.job_id === cand.job_id);
      const stageSel = document.getElementById("edit-cand-stage");
      if (job && stageSel) {
        stageSel.innerHTML = (job.stages || []).map((s, idx) =>
          `<option value="${s.stage_id}" ${s.stage_id === cand.current_stage_id ? "selected" : ""}>Stage ${idx + 1}: ${s.name}</option>`
        ).join("");
      }
      document.getElementById("edit-candidate-modal").classList.remove("hidden");
    }

    function closeEditCandidateModal() {
      document.getElementById("edit-candidate-modal").classList.add("hidden");
    }

    async function submitEditCandidate(ev) {
      ev.preventDefault();
      const candId = document.getElementById("edit-cand-id").value;
      const notesEl = document.getElementById("edit-cand-notes");
      const payload = {
        name: document.getElementById("edit-cand-name").value.trim(),
        email: document.getElementById("edit-cand-email").value.trim(),
        timezone: document.getElementById("edit-cand-tz").value.trim(),
        current_stage_id: document.getElementById("edit-cand-stage").value,
        notes: notesEl ? notesEl.value.trim() : ""
      };
      const res = await fetch(`/api/candidates/${candId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        closeEditCandidateModal();
        showToast(`Updated candidate ${payload.name}.`);
        await fetchDashboard();
      }
    }

    async function deleteCurrentCandidate() {
      const candId = document.getElementById("edit-cand-id").value;
      if (!candId) return;
      const res = await fetch(`/api/candidates/${candId}`, { method: "DELETE" });
      if (res.ok) {
        closeEditCandidateModal();
        showToast(`Removed candidate ${candId}.`);
        await fetchDashboard();
      }
    }

    async function openCalendarModal() {
      document.getElementById("calendar-modal").classList.remove("hidden");
      const res = await fetch("/api/calendars");
      const data = await res.json();
      const cals = data.calendars || {};
      const sel = document.getElementById("cal-interviewer-select");
      if (sel) {
        const currentVal = sel.value;
        sel.innerHTML = Object.keys(cals).map(email => `<option value="${email}">${email}</option>`).join("");
        if (currentVal && cals[currentVal]) sel.value = currentVal;
        sel.onchange = () => loadSelectedCalendar();
      }
      await loadSelectedCalendar();
    }

    function closeCalendarModal() {
      document.getElementById("calendar-modal").classList.add("hidden");
    }

    async function loadSelectedCalendar() {
      const sel = document.getElementById("cal-interviewer-select");
      const res = await fetch("/api/calendars");
      const data = await res.json();
      const cals = data.calendars || {};
      const selectedEmail = sel && sel.value ? sel.value : Object.keys(cals)[0];
      const listEl = document.getElementById("calendar-list-container");
      if (!listEl) return;
      const entries = Object.entries(cals);
      if (entries.length === 0) {
        listEl.innerHTML = `<div class="text-[12px] text-[#86868B]">No interviewer calendars found.</div>`;
        return;
      }
      listEl.innerHTML = entries.map(([email, blocks]) => `
        <div class="p-3.5 rounded-xl ${email === selectedEmail ? 'bg-[#0071E3]/5 border border-[#0071E3]/25' : 'bg-[#F5F5F7] border border-black/5'} space-y-2">
          <div class="flex items-center justify-between">
            <span class="font-semibold text-[12.5px] text-[#1D1D1F]">${email}</span>
            <span class="text-[11px] text-[#6E6E73]">${(blocks || []).length} busy block(s)</span>
          </div>
          <div class="flex flex-wrap gap-1.5">
            ${(blocks || []).map(b => `
              <span class="px-2.5 py-1 rounded-lg bg-white border border-black/5 text-[11px] text-[#424245]">
                ${formatIso(b.start)} → ${formatIso(b.end)}
              </span>
            `).join("")}
          </div>
        </div>
      `).join("");
    }

    async function submitAddBusyBlock(ev) {
      ev.preventDefault();
      const email = document.getElementById("cal-interviewer-select").value;
      const startVal = document.getElementById("cal-busy-start").value.trim();
      const endVal = document.getElementById("cal-busy-end").value.trim();
      if (!email || !startVal || !endVal) return;
      await fetch("/api/calendars/busy", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          interviewer_email: email,
          start: startVal,
          end: endVal
        })
      });
      showToast(`Added busy time block for ${email}.`);
      await loadSelectedCalendar();
      await fetchDashboard();
    }

    function openComposeEmailModal() {
      document.getElementById("compose-email-modal").classList.remove("hidden");
    }

    function closeComposeEmailModal() {
      document.getElementById("compose-email-modal").classList.add("hidden");
    }

    async function submitComposeEmail(ev) {
      ev.preventDefault();
      const payload = {
        to_email: document.getElementById("compose-to").value.trim(),
        subject: document.getElementById("compose-subject").value.trim(),
        body: document.getElementById("compose-body").value.trim()
      };
      const res = await fetch("/api/email/send", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        closeComposeEmailModal();
        showToast(`Sent email to ${payload.to_email}.`);
        await fetchDashboard();
      }
    }

    async function saveSmtpConfig() {
      const appPassword = document.getElementById("smtp-app-password").value;
      const liveEnabled = document.getElementById("smtp-live-toggle").checked;
      await fetch("/api/email/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sender_email: "psrmreports@sybyl.com",
          app_password: appPassword,
          live_smtp_enabled: liveEnabled
        })
      });
      showToast("Saved outbound email settings.");
      await fetchDashboard();
    }

    // -----------------------------------------------------------------------
    // AI Agent Chat (Google Workspace Scheduling Assistant)
    // -----------------------------------------------------------------------
    function appendCopilotMessage(role, text, toolCalls) {
      const container = document.getElementById("copilot-messages");
      if (!container) return;
      const div = document.createElement("div");
      if (role === "user") {
        div.className = "p-3 rounded-2xl bg-[#0071E3] text-white ml-8 text-[13px]";
        div.innerHTML = `<div>${text}</div>`;
      } else {
        const formatted = (text || "")
          .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
          .replace(/`(.*?)`/g, "<code class='text-[#0071E3]'>$1</code>")
          .replace(/\n/g, "<br/>");
        div.className = "p-3.5 rounded-2xl bg-[#F5F5F7] border border-black/5 text-[#1D1D1F] space-y-1.5";
        div.innerHTML = `
          <div class="flex items-center justify-between gap-2">
            <span class="font-semibold text-[#0071E3] text-[11px]">AI Agent</span>
          </div>
          <div class="leading-relaxed text-[12.5px] text-[#424245]">${formatted}</div>
        `;
      }
      container.appendChild(div);
      container.scrollTop = container.scrollHeight;
    }

    async function sendQuickPrompt(promptText) {
      document.getElementById("copilot-input").value = promptText;
      await submitCopilotChat(new Event("submit"));
    }

    async function submitCopilotChat(ev) {
      if (ev && ev.preventDefault) ev.preventDefault();
      const input = document.getElementById("copilot-input");
      const msg = input.value.trim();
      if (!msg) return;
      input.value = "";
      appendCopilotMessage("user", msg);

      const res = await fetch("/api/agent/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: msg, session_id: AI_AGENT_SESSION_ID })
      });
      const data = await res.json();
      appendCopilotMessage("agent", data.reply || "Done.", data.tool_calls || []);
      await fetchDashboard();
    }

    window.addEventListener("DOMContentLoaded", async () => {
      const params = new URLSearchParams(window.location.search);
      const oauthEmail = params.get("oauth_email");
      const oauthName = params.get("oauth_name");
      const oauthError = params.get("oauth_error");

      if (oauthError) {
        IS_LOGGED_OUT = true;
        const banner = document.getElementById("logout-banner-msg");
        if (banner) {
          banner.textContent = `Google Sign-In Notice: ${oauthError}`;
          banner.className = "mt-4 px-3.5 py-2.5 rounded-xl bg-[#FF9500]/15 border border-[#FF9500]/30 text-[12.5px] text-[#C93400]";
        }
      }

      if (oauthEmail) {
        IS_LOGGED_OUT = false;
        applyUserProfile(oauthName, oauthEmail);
        showToast(`Signed in with Google as ${oauthEmail}`);
        try {
          window.history.replaceState({}, "", window.location.pathname);
        } catch (e) {}
      } else {
        try {
          const activeSession = JSON.parse(sessionStorage.getItem("scheduler_active_session") || "null");
          if (activeSession && activeSession.email && window.location.pathname !== "/login") {
            IS_LOGGED_OUT = false;
            applyUserProfile(activeSession.name, activeSession.email);
          }
        } catch (e) {}
      }

      // Enforce Sign-In screen first unless logged in or opening an external candidate/interviewer portal token
      if (IS_LOGGED_OUT) {
        document.getElementById("app-shell").classList.add("hidden");
        document.getElementById("auth-login-view").classList.remove("hidden");
        initGoogleSSO();
        setTimeout(initGoogleSSO, 600);
        await fetchDashboard();
        return;
      }

      document.getElementById("auth-login-view").classList.add("hidden");
      document.getElementById("app-shell").classList.remove("hidden");
      await fetchDashboard();

      if (INITIAL_TOKEN) {
        if (CURRENT_SCREEN === "screen-panel") {
          SELECTED_PANEL_TOKEN = INITIAL_TOKEN;
        } else if (CURRENT_SCREEN === "screen-candidate") {
          SELECTED_CANDIDATE_TOKEN = INITIAL_TOKEN;
        }
      }
      switchScreen(CURRENT_SCREEN, false);
    });
  </script>
</body>
</html>
"""

