"""main.py - FastAPI Backend for Agent #09: Executive Talk-to-Your-Workforce & Attrition Stress-Test Agent."""

from __future__ import annotations
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

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
    aggregate_workforce_kpis,
    get_initial_state,
    run_workforce_stress_test,
)

app = FastAPI(
    title="Workforce Analytics Agent — Executive Talk-to-Your-Workforce & Attrition Stress-Test Workspace",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATE: Dict[str, Any] = get_initial_state()


class OTPRequestPayload(BaseModel):
    email: str


class OTPVerifyPayload(BaseModel):
    email: str
    code: str


class GoogleAuthPayload(BaseModel):
    credential: str


class DemoSignInPayload(BaseModel):
    role: Optional[str] = Field(default="Chief Human Resources Officer (CHRO)")


class WorkforceSimulationPayload(BaseModel):
    annual_salary_increment_pct: float = Field(default=5.0, ge=0.0, le=25.0)
    projected_turnover_pct: float = Field(default=13.8, ge=0.0, le=40.0)
    planned_new_hires: int = Field(default=25, ge=0, le=200)


class AskWorkforceAgentPayload(BaseModel):
    question: str
    annual_salary_increment_pct: Optional[float] = Field(default=5.0)
    projected_turnover_pct: Optional[float] = Field(default=13.8)
    planned_new_hires: Optional[int] = Field(default=25)


@app.get("/api/health")
def health_check() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service": "hr-workforce-analytics-agent",
        "agent_number": 9,
        "agent_name": "Workforce Analytics Agent",
        "google_client_id": GOOGLE_CLIENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/api/auth/otp/request")
def request_otp(payload: OTPRequestPayload) -> Dict[str, Any]:
    email = (payload.email or "").strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Please enter a valid work email address.")
    if not is_access_allowed(email):
        raise HTTPException(status_code=403, detail=get_otp_rejection_message(email))
    code = generate_and_store_otp(email)
    try:
        send_otp_email(email, code)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to send verification code: {exc}")
    return {
        "status": "sent",
        "email": email,
        "message": f"6-digit verification code sent to {email}.",
    }


@app.post("/api/auth/otp/verify")
def verify_otp(payload: OTPVerifyPayload) -> Dict[str, Any]:
    email = (payload.email or "").strip().lower()
    code = (payload.code or "").strip()
    ok, message = verify_stored_otp(email, code)
    if not ok:
        raise HTTPException(status_code=401, detail=message)
    return {
        "status": "authenticated",
        "user": {
            "email": email,
            "name": format_name_from_email(email),
            "role": "CHRO / Executive View",
            "auth_method": "email_otp",
        },
    }


@app.post("/api/auth/google")
def google_auth(payload: GoogleAuthPayload) -> Dict[str, Any]:
    ok, profile, error = verify_google_id_token(payload.credential)
    if not ok:
        raise HTTPException(status_code=401, detail=error or "Google Single Sign-On failed.")
    return {
        "status": "authenticated",
        "user": {
            "email": profile.get("email"),
            "name": profile.get("name") or format_name_from_email(profile.get("email", "")),
            "picture": profile.get("picture", ""),
            "role": "CHRO / Executive View",
            "auth_method": "google_sso",
        },
    }


@app.post("/api/auth/demo")
def demo_auth(payload: Optional[DemoSignInPayload] = None) -> Dict[str, Any]:
    role = (payload.role if payload and payload.role else "CHRO / Executive View")
    return {
        "status": "authenticated",
        "user": {
            "email": "grace.njeri@sybyl.com",
            "name": "Grace Njeri (CHRO)",
            "role": role,
            "auth_method": "instant_demo_sso",
        },
    }


@app.get("/api/workforce/overview")
def get_workforce_overview() -> Dict[str, Any]:
    kpis = aggregate_workforce_kpis(STATE["departments"])
    STATE["executive_kpis"] = kpis
    default_simulation = run_workforce_stress_test(
        STATE,
        annual_salary_increment_pct=5.0,
        projected_turnover_pct=kpis["annual_attrition_rate_pct"],
        planned_new_hires=25,
    )
    return {
        "company_profile": STATE["company_profile"],
        "executive_kpis": kpis,
        "departments": STATE["departments"],
        "quarterly_trends": STATE["quarterly_trends"],
        "board_highlights": STATE["board_highlights"],
        "sample_questions": STATE["sample_questions"],
        "default_simulation": default_simulation,
    }


@app.post("/api/workforce/simulate")
def simulate_workforce_budget(payload: WorkforceSimulationPayload) -> Dict[str, Any]:
    return run_workforce_stress_test(
        STATE,
        annual_salary_increment_pct=payload.annual_salary_increment_pct,
        projected_turnover_pct=payload.projected_turnover_pct,
        planned_new_hires=payload.planned_new_hires,
    )


# Alias for compatibility with executive stress-test naming
@app.post("/api/workforce/stress-test")
def stress_test_workforce_budget(payload: WorkforceSimulationPayload) -> Dict[str, Any]:
    return run_workforce_stress_test(
        STATE,
        annual_salary_increment_pct=payload.annual_salary_increment_pct,
        projected_turnover_pct=payload.projected_turnover_pct,
        planned_new_hires=payload.planned_new_hires,
    )


@app.post("/api/workforce/reset")
def reset_workforce_state() -> Dict[str, Any]:
    global STATE
    STATE = get_initial_state()
    return {"status": "reset", "overview": get_workforce_overview()}


def _build_plain_english_workforce_answer(
    question: str,
    salary_increment_pct: float = 5.0,
    projected_turnover_pct: float = 13.8,
    planned_new_hires: int = 25,
) -> Dict[str, Any]:
    q_lower = question.lower()
    kpis = aggregate_workforce_kpis(STATE["departments"])
    sim = run_workforce_stress_test(
        STATE,
        annual_salary_increment_pct=salary_increment_pct,
        projected_turnover_pct=projected_turnover_pct,
        planned_new_hires=planned_new_hires,
    )

    if any(k in q_lower for k in ["budget", "salary", "increment", "cost", "payroll", "what-if", "simulate", "slider", "6%", "10%", "impact"]):
        proj = sim["projected"]
        return {
            "agent_badge": "Workforce Analytics Agent • Wage-Bill & Replacement Cost Simulation",
            "headline": (
                f"Projected Annual Payroll: ${proj['annual_payroll_cost']:,.0f} "
                f"(+${proj['net_annual_budget_impact']:,.0f} Net Budget Impact)"
            ),
            "executive_summary": (
                f"Under a {salary_increment_pct:.1f}% annual salary increment, {projected_turnover_pct:.1f}% projected turnover, and "
                f"{planned_new_hires} planned new hires, monthly payroll moves from ${kpis['monthly_payroll_cost']:,.0f} to ${proj['monthly_payroll_cost']:,.0f}."
            ),
            "key_points": [
                f"Annual Salary Increment ({salary_increment_pct:.1f}%): Adds ${proj['annual_salary_increment_cost']:,.0f}/year (${proj['monthly_salary_increment_cost']:,.0f}/month) across {kpis['total_active_headcount']} current staff.",
                f"Planned New Hires ({planned_new_hires} roles): Adds ${proj['new_hires_annual_payroll_cost']:,.0f}/year in salary plus ${proj['new_hires_recruitment_cost']:,.0f} in one-time recruitment fees.",
                f"Turnover Replacement Cost ({projected_turnover_pct:.1f}% / {proj['annual_departures']} exits): Costs ${proj['annual_replacement_cost']:,.0f} at $19,000 per replacement ({proj['replacement_cost_variance']:+,.0f} vs current baseline).",
                f"Year-End Headcount reaches {proj['headcount']} employees with a total people budget of ${proj['total_projected_people_budget']:,.0f}.",
            ],
            "recommended_action": sim["board_guidance"],
        }

    if any(k in q_lower for k in ["turnover", "attrition", "regrettable", "leaving", "exit", "retention", "sales"]):
        return {
            "agent_badge": "Workforce Analytics Agent • Retention & Turnover Analysis",
            "headline": "Sales & Commercial (18.2%) and Customer Operations (14.6%) Lead Company Turnover",
            "executive_summary": (
                f"Company-wide annual attrition stands at {kpis['annual_attrition_rate_pct']}% ({kpis['total_annual_departures']} departures across "
                f"{kpis['total_active_headcount']} active employees), with {kpis['regrettable_departures']} regrettable departures from key roles."
            ),
            "key_points": [
                "Sales & Commercial (18.2% turnover, 8 regrettable exits): Driven by Q3 commission threshold changes among mid-tenure Account Executives ($715,000 monthly payroll).",
                "Engineering (13.8% turnover, 9 regrettable exits): Highest number of regrettable departures as Senior Cloud & AI Engineers receive remote offers ($1,160,000 monthly payroll).",
                "Customer Operations (14.6% turnover, 5 regrettable exits): Concentrated in 18-to-24 month frontline support staff seeking clear promotion pathways ($585,000 monthly payroll).",
                "Finance & Admin (7.3%) and People & Culture (7.5%) remain in the Healthy retention band with only 1 regrettable exit each.",
            ],
            "recommended_action": (
                "Rebalance Sales Q4 commission accelerators and target a 7% retention salary adjustment for top-quartile Engineering staff to prevent an estimated $285,000 in avoidable replacement costs."
            ),
        }

    if any(k in q_lower for k in ["hire", "hiring", "speed", "time to hire", "open role", "recruiting", "engineering", "42", "days"]):
        return {
            "agent_badge": "Workforce Analytics Agent • Hiring Velocity & Open Roles",
            "headline": f"{kpis['total_open_roles']} Open Roles Active | Average Time to Hire is {kpis['avg_time_to_hire_days']} Days",
            "executive_summary": (
                "Hiring speed has improved from 35 days in Q1 to 32 days in Q4, but Engineering remains the primary bottleneck at 42 days per hire."
            ),
            "key_points": [
                "Engineering (12 open roles, 42 days avg time to hire): Four sequential technical interview rounds are slowing down senior offer acceptance.",
                "Sales & Commercial (9 open roles, 31 days avg time to hire): Active backfilling of enterprise Account Executives ahead of Q1 quota launch.",
                "Customer Operations (8 open roles, 21 days avg time to hire): Fastest hiring pipeline supported by batch assessment days.",
                "Finance & Admin (3 open roles, 29 days) and People & Culture (2 open roles, 26 days) are tracking on schedule.",
            ],
            "recommended_action": (
                "Consolidate Engineering technical assessments from 4 rounds to 2 structured panel interviews and assign a dedicated technical sourcer from People & Culture to cut Engineering hiring time to 30 days."
            ),
        }

    return {
        "agent_badge": "Workforce Analytics Agent • CHRO & CEO Boardroom Summary",
        "headline": (
            f"{kpis['total_active_headcount']} Active Employees | {kpis['annual_attrition_rate_pct']}% Annual Attrition | "
            f"${kpis['monthly_payroll_cost']:,.0f} Monthly Payroll"
        ),
        "executive_summary": (
            "The workforce grew from 452 to 480 employees over the past four quarters while reducing average time to hire from 35 to 32 days. "
            "Executive focus for the upcoming quarter centers on curbing regrettable departures in Engineering and Sales."
        ),
        "key_points": [
            f"Headcount & Open Roles: {kpis['total_active_headcount']} active staff across 5 departments with {kpis['total_open_roles']} open roles (21 of 34 open roles are in Engineering and Sales).",
            f"Retention Health: {kpis['total_annual_departures']} annual departures ({kpis['annual_attrition_rate_pct']}% rate), including {kpis['regrettable_departures']} regrettable departures concentrated in the 2-to-3 year tenure window.",
            f"Payroll & Cost Baseline: ${kpis['monthly_payroll_cost']:,.0f} monthly payroll (${kpis['annual_payroll_cost']:,.0f} annualized), averaging ${kpis['avg_monthly_cost_per_employee']:,.0f}/month per employee.",
            f"What-If Scenario ({salary_increment_pct:.1f}% salary review, {planned_new_hires} hires, {projected_turnover_pct:.1f}% turnover): Projects ${sim['projected']['annual_payroll_cost']:,.0f} annual payroll and ${sim['projected']['annual_replacement_cost']:,.0f} in replacement hiring costs.",
        ],
        "recommended_action": (
            "Approve the Q1 targeted retention package for Engineering & Sales, streamline Engineering interview panels to 2 rounds, and review the 1-Page CHRO Boardroom Summary with the Compensation Committee."
        ),
    }


@app.post("/api/agent/ask")
def ask_workforce_agent(payload: AskWorkforceAgentPayload) -> Dict[str, Any]:
    question = (payload.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="Please enter a question for the Workforce Analytics Agent.")

    deterministic = _build_plain_english_workforce_answer(
        question=question,
        salary_increment_pct=payload.annual_salary_increment_pct if payload.annual_salary_increment_pct is not None else 5.0,
        projected_turnover_pct=payload.projected_turnover_pct if payload.projected_turnover_pct is not None else 13.8,
        planned_new_hires=payload.planned_new_hires if payload.planned_new_hires is not None else 25,
    )

    use_vertex = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "").strip() == "1"
    if use_vertex:
        try:
            from google import genai

            client = genai.Client()
            kpis = aggregate_workforce_kpis(STATE["departments"])
            prompt = (
                "You are the Executive Workforce Analytics Agent for the CEO, CHRO, and CFO.\n"
                "Use plain business English with zero technical jargon.\n"
                f"Company Workforce Metrics: Total Active Headcount {kpis['total_active_headcount']}, "
                f"Annual Attrition Rate {kpis['annual_attrition_rate_pct']}%, "
                f"Regrettable Departures {kpis['regrettable_departures']}, "
                f"Average Time to Hire {kpis['avg_time_to_hire_days']} days, "
                f"Monthly Payroll Cost ${kpis['monthly_payroll_cost']:,.0f}.\n"
                f"Executive Question: {question}\n"
                "Provide a concise 3-sentence boardroom answer with exact numbers and practical people recommendations."
            )
            resp = client.models.generate_content(
                model=os.getenv("GEMINI_FLASH_MODEL", "gemini-2.5-flash"),
                contents=prompt,
            )
            if resp and resp.text:
                deterministic["ai_live_summary"] = resp.text.strip()
                deterministic["engine"] = "Enterprise People & Analytics Engine"
                return deterministic
        except Exception:
            pass

    deterministic["engine"] = "Enterprise People & Analytics Engine"
    return deterministic


# Mount compiled React SPA static bundle
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
