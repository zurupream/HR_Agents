"""main.py - FastAPI Backend for Agent #07: Employee HR Helpdesk Agent."""

from __future__ import annotations
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from auth_service import (
    GOOGLE_CLIENT_ID,
    format_name_from_email,
    generate_and_store_otp,
    get_otp_rejection_message,
    is_access_allowed,
    send_otp_email,
    verify_google_id_token,
    verify_stored_otp,
)
from seed_data import (
    answer_hr_question,
    get_handbook_categories,
    get_handbook_category_by_id,
    get_initial_helpdesk_requests,
)

app = FastAPI(
    title="Employee HR Helpdesk Agent",
    description="Focused Employee Self-Service HR Helpdesk Agent backed by the Official Employee Handbook",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

HELPDESK_REQUESTS_STORE: List[Dict[str, Any]] = get_initial_helpdesk_requests()
_QUESTIONS_ANSWERED_COUNT: int = 148


# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------
class OTPRequestPayload(BaseModel):
    email: str


class OTPVerifyPayload(BaseModel):
    email: str
    code: str


class GoogleAuthPayload(BaseModel):
    credential: str


class DemoSignInPayload(BaseModel):
    view_mode: Optional[str] = "employee"


class AskHelpdeskAgentPayload(BaseModel):
    question: str
    category_id: Optional[str] = None


class CreateHelpdeskRequestPayload(BaseModel):
    employee_name: Optional[str] = "Alex Mwangi"
    employee_email: Optional[str] = "alex.mwangi@sybyl.com"
    department: Optional[str] = "Product & Engineering"
    category_id: Optional[str] = "annual_maternity_leave"
    subject: str
    details: str


class ResolveHelpdeskRequestPayload(BaseModel):
    status: Optional[str] = "Resolved"
    hr_owner: Optional[str] = "People Services Desk"
    hr_response: Optional[str] = None


# ---------------------------------------------------------------------------
# KPI Helper
# ---------------------------------------------------------------------------
def _compute_helpdesk_summary() -> Dict[str, Any]:
    open_count = sum(1 for r in HELPDESK_REQUESTS_STORE if r["status"] in ("Open", "In Progress"))
    resolved_count = sum(1 for r in HELPDESK_REQUESTS_STORE if r["status"] == "Resolved")
    return {
        "handbook_categories_count": len(get_handbook_categories()),
        "questions_answered_instantly": _QUESTIONS_ANSWERED_COUNT,
        "instant_resolution_rate_pct": 78,
        "total_hr_requests": len(HELPDESK_REQUESTS_STORE),
        "open_hr_requests": open_count,
        "resolved_hr_requests": resolved_count,
    }


# ---------------------------------------------------------------------------
# Health & Single Sign-On (SSO) Endpoints
# ---------------------------------------------------------------------------
@app.get("/api/health")
def health_check() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service": "HR_HelpdeskAgent",
        "agent_number": 7,
        "title": "Employee HR Helpdesk Agent",
        "google_client_id": GOOGLE_CLIENT_ID,
        "handbook_topics_count": len(get_handbook_categories()),
        "helpdesk_requests_count": len(HELPDESK_REQUESTS_STORE),
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@app.post("/api/auth/otp/request")
def request_otp(payload: OTPRequestPayload) -> Dict[str, Any]:
    email = (payload.email or "").strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Please enter a valid company work email address.")
    if not is_access_allowed(email):
        raise HTTPException(status_code=403, detail=get_otp_rejection_message(email))
    code = generate_and_store_otp(email)
    sent_via_smtp = False
    try:
        sent_via_smtp = send_otp_email(email, code)
    except Exception:
        sent_via_smtp = False
    response: Dict[str, Any] = {
        "ok": True,
        "message": f"6-digit verification code sent to {email}.",
        "email": email,
    }
    if not sent_via_smtp:
        response["demo_otp_hint"] = code
    return response


@app.post("/api/auth/otp/verify")
def verify_otp(payload: OTPVerifyPayload) -> Dict[str, Any]:
    email = (payload.email or "").strip().lower()
    code = (payload.code or "").strip()
    ok, msg = verify_stored_otp(email, code)
    if not ok:
        raise HTTPException(status_code=401, detail=msg)
    return {
        "ok": True,
        "user": {
            "email": email,
            "name": format_name_from_email(email),
            "department": "People & Operations",
            "role": "Employee & HR Helpdesk View",
            "auth_method": "email_otp",
        },
    }


@app.post("/api/auth/google")
def google_auth(payload: GoogleAuthPayload) -> Dict[str, Any]:
    ok, user_info, err = verify_google_id_token(payload.credential)
    if not ok:
        raise HTTPException(status_code=401, detail=err or "Google Single Sign-On failed.")
    return {
        "ok": True,
        "user": {
            "email": user_info.get("email", ""),
            "name": user_info.get("name") or format_name_from_email(user_info.get("email", "")),
            "picture": user_info.get("picture", ""),
            "department": "People & Operations",
            "role": "Employee & HR Helpdesk View",
            "auth_method": "google_sso",
        },
    }


@app.post("/api/auth/demo")
def demo_sign_in(payload: Optional[DemoSignInPayload] = None) -> Dict[str, Any]:
    mode = (payload.view_mode if payload and payload.view_mode else "employee").strip().lower()
    if mode == "hr":
        user = {
            "email": "people.helpdesk@sybyl.com",
            "name": "Sarah Njoroge (HR Operations)",
            "department": "People & Culture Team",
            "role": "HR Team View",
            "auth_method": "instant_demo",
        }
    else:
        user = {
            "email": "alex.mwangi@sybyl.com",
            "name": "Alex Mwangi",
            "department": "Product & Engineering",
            "role": "Employee View",
            "auth_method": "instant_demo",
        }
    return {"ok": True, "user": user}


# ---------------------------------------------------------------------------
# Employee Handbook Knowledge Base Endpoints
# ---------------------------------------------------------------------------
@app.get("/api/handbook")
def list_handbook_topics() -> Dict[str, Any]:
    return {
        "categories": get_handbook_categories(),
        "summary": _compute_helpdesk_summary(),
    }


@app.get("/api/handbook/{category_id}")
def get_handbook_topic(category_id: str) -> Dict[str, Any]:
    category = get_handbook_category_by_id(category_id)
    if not category:
        raise HTTPException(status_code=404, detail=f"Handbook topic '{category_id}' not found.")
    return category


# ---------------------------------------------------------------------------
# Ask HR Helpdesk Agent Endpoint
# ---------------------------------------------------------------------------
@app.post("/api/helpdesk/ask")
@app.post("/api/agent/ask")
def ask_hr_helpdesk_agent(payload: AskHelpdeskAgentPayload) -> Dict[str, Any]:
    global _QUESTIONS_ANSWERED_COUNT
    question = (payload.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="Please type a question for the Employee HR Helpdesk Agent.")

    _QUESTIONS_ANSWERED_COUNT += 1
    structured = answer_hr_question(question, payload.category_id)
    plain_answer = structured["plain_english_answer"]
    model_used = "employee-handbook-engine-v1"

    # Optional Gemini 2.5 Flash refinement if credentials are active in environment
    if os.getenv("ENABLE_LIVE_GEMINI_HELPDESK", "0") == "1":
        try:
            from google import genai
            from google.genai import types

            project = os.getenv("GOOGLE_CLOUD_PROJECT", "gemini-enterprise-demo-498212")
            location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
            client = genai.Client(vertexai=True, project=project, location=location)
            entitlements_str = "; ".join(
                f"{e['label']}: {e['value']} ({e['note']})" for e in structured["entitlements_at_a_glance"]
            )
            prompt = (
                "You are the friendly, accurate Employee HR Helpdesk Agent. "
                "Answer the employee's question in clear, warm plain English (2 to 4 sentences) "
                "strictly using the official Employee Handbook rule and numbers below.\n\n"
                f"Handbook Section: {structured['handbook_section']}\n"
                f"Official Policy Rule: {structured['policy_rule']}\n"
                f"Key Entitlements: {entitlements_str}\n"
                f"Employee Question: {question}"
            )
            resp = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.15, max_output_tokens=300),
            )
            if resp.text and resp.text.strip():
                plain_answer = resp.text.strip()
                model_used = "gemini-2.5-flash"
        except Exception:
            pass

    return {
        "ok": True,
        "question": structured["question"],
        "answer": plain_answer,
        "plain_english_answer": plain_answer,
        "category_id": structured["category_id"],
        "category_title": structured["category_title"],
        "handbook_section": structured["handbook_section"],
        "policy_rule": structured["policy_rule"],
        "entitlements_at_a_glance": structured["entitlements_at_a_glance"],
        "steps_to_follow": structured["steps_to_follow"],
        "when_to_contact_hr": structured["when_to_contact_hr"],
        "suggested_request_subject": structured["suggested_request_subject"],
        "model": model_used,
    }


# ---------------------------------------------------------------------------
# HR Helpdesk Request (Ticket) Endpoints
# ---------------------------------------------------------------------------
@app.get("/api/helpdesk/requests")
@app.get("/api/tickets")
def list_helpdesk_requests() -> Dict[str, Any]:
    return {
        "requests": HELPDESK_REQUESTS_STORE,
        "summary": _compute_helpdesk_summary(),
    }


@app.get("/api/helpdesk/requests/{request_id}")
@app.get("/api/tickets/{request_id}")
def get_helpdesk_request(request_id: str) -> Dict[str, Any]:
    clean_id = (request_id or "").strip().upper()
    for req in HELPDESK_REQUESTS_STORE:
        if req["request_id"].upper() == clean_id:
            return req
    raise HTTPException(status_code=404, detail=f"HR Helpdesk Request '{request_id}' not found.")


@app.post("/api/helpdesk/requests")
@app.post("/api/tickets")
def create_helpdesk_request(payload: CreateHelpdeskRequestPayload) -> Dict[str, Any]:
    subject = (payload.subject or "").strip()
    details = (payload.details or "").strip()
    if not subject or not details:
        raise HTTPException(status_code=400, detail="Please provide both a subject and details for your HR request.")

    cat = get_handbook_category_by_id(payload.category_id or "annual_maternity_leave")
    if not cat:
        cat = get_handbook_categories()[0]

    next_number = 1041 + len(HELPDESK_REQUESTS_STORE)
    new_req = {
        "request_id": f"HR-2026-{next_number}",
        "created_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M EAT"),
        "employee_name": (payload.employee_name or "Alex Mwangi").strip(),
        "employee_email": (payload.employee_email or "alex.mwangi@sybyl.com").strip(),
        "department": (payload.department or "Product & Engineering").strip(),
        "category_id": cat["id"],
        "category_title": cat["title"],
        "subject": subject,
        "details": details,
        "handbook_reference": cat["handbook_section"],
        "status": "Open",
        "hr_owner": "People Services Desk",
        "hr_response": "Received by HR Helpdesk Team. A People Services specialist will respond within 4 working hours.",
    }
    HELPDESK_REQUESTS_STORE.insert(0, new_req)
    return {
        "ok": True,
        "message": f"HR Request {new_req['request_id']} sent to the HR Team.",
        "request": new_req,
        "summary": _compute_helpdesk_summary(),
    }


@app.post("/api/helpdesk/requests/{request_id}/resolve")
@app.post("/api/tickets/{request_id}/resolve")
def resolve_helpdesk_request(request_id: str, payload: ResolveHelpdeskRequestPayload) -> Dict[str, Any]:
    clean_id = (request_id or "").strip().upper()
    for idx, req in enumerate(HELPDESK_REQUESTS_STORE):
        if req["request_id"].upper() == clean_id:
            updated = dict(req)
            updated["status"] = payload.status or "Resolved"
            updated["hr_owner"] = payload.hr_owner or "People Services Desk"
            if payload.hr_response and payload.hr_response.strip():
                updated["hr_response"] = payload.hr_response.strip()
            else:
                updated["hr_response"] = (
                    f"Completed and verified by {updated['hr_owner']} per {updated['handbook_reference']}."
                )
            updated["resolved_at"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M EAT")
            HELPDESK_REQUESTS_STORE[idx] = updated
            return {
                "ok": True,
                "message": f"Request {updated['request_id']} marked as {updated['status']}.",
                "request": updated,
                "summary": _compute_helpdesk_summary(),
            }
    raise HTTPException(status_code=404, detail=f"HR Helpdesk Request '{request_id}' not found.")


# ---------------------------------------------------------------------------
# SPA Static File Hosting (../frontend/dist)
# ---------------------------------------------------------------------------
FRONTEND_DIST = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "dist"))

if os.path.isdir(FRONTEND_DIST):
    assets_dir = os.path.join(FRONTEND_DIST, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}")
    def serve_spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="API route not found")
        candidate = os.path.join(FRONTEND_DIST, full_path)
        if full_path and os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))
