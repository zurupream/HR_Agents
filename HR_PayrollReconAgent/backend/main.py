"""
FastAPI Backend for Agent #05: Payroll Variance, Statutory Compliance & Payslip Recon Agent.
Includes Enterprise Single Sign-On (Work Email 6-Digit Verification Code + Google Sign-In + Instant Demo Sign-In),
Deterministic Statutory Payroll Calculator (PAYE, NSSF, SHIF, Housing Levy),
Prior vs. Current Month Variance & Bank-Account Swap Auditor, 1-Click Payroll Approval,
and Plain-English Ask Payroll Agent Assistant.
"""

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from auth_service import (
    format_name_from_email,
    generate_and_store_otp,
    get_otp_rejection_message,
    is_access_allowed,
    send_otp_email,
    verify_google_id_token,
    verify_stored_otp,
)
from seed_data import (
    build_payroll_store,
    calculate_statutory_deductions,
    run_payroll_reconciliation,
)

app = FastAPI(
    title="Payroll Variance, Statutory Compliance & Payslip Recon Agent (#05)",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PAYROLL_STORE: List[Dict[str, Any]] = build_payroll_store()


class OTPRequestPayload(BaseModel):
    email: str


class OTPVerifyPayload(BaseModel):
    email: str
    code: str


class GoogleAuthPayload(BaseModel):
    credential: str


class SimulatePayrollPayload(BaseModel):
    employee_id: str
    current_basic_pay: float
    current_house_allowance: float
    current_transport_allowance: float
    current_bonus_overtime: float
    apply_statutory_rates: bool = True
    revert_bank_to_verified: bool = False
    remove_exited_employee: bool = False
    verify_tax_pin: bool = False
    authorize_salary_change: bool = False


class ApproveEmployeePayload(BaseModel):
    approved_by: Optional[str] = "Head of Payroll"
    resolve_exceptions: bool = False


class AgentAskPayload(BaseModel):
    question: str
    employee_id: Optional[str] = None


def compute_kpis() -> Dict[str, Any]:
    prior_total_gross = round(sum(e["prior_gross_pay"] for e in PAYROLL_STORE), 2)
    current_total_gross = round(sum(e["current_gross_pay"] for e in PAYROLL_STORE), 2)
    gross_variance = round(current_total_gross - prior_total_gross, 2)

    prior_total_net = round(sum(e["prior_net_pay"] for e in PAYROLL_STORE), 2)
    current_total_net = round(sum(e["draft_net_pay"] for e in PAYROLL_STORE), 2)

    total_paye = round(sum(e["draft_paye"] for e in PAYROLL_STORE), 2)
    total_nssf = round(sum(e["draft_nssf"] for e in PAYROLL_STORE), 2)
    total_shif = round(sum(e["draft_shif"] for e in PAYROLL_STORE), 2)
    total_housing_levy = round(sum(e["draft_housing_levy"] for e in PAYROLL_STORE), 2)
    total_statutory = round(
        total_paye + total_nssf + total_shif + total_housing_levy, 2
    )
    expected_total_statutory = round(
        sum(e["expected_total_statutory"] for e in PAYROLL_STORE), 2
    )
    statutory_shortfall = round(expected_total_statutory - total_statutory, 2)

    flagged_employees = [e for e in PAYROLL_STORE if e["has_exceptions"]]
    approved_employees = [
        e for e in PAYROLL_STORE if e["approval_status"] == "APPROVED"
    ]
    verified_employees = [
        e for e in PAYROLL_STORE if not e["has_exceptions"]
    ]

    ghost_worker_count = sum(
        1 for e in PAYROLL_STORE if "GHOST_WORKER" in e["exception_codes"]
    )
    bank_swap_count = sum(
        1 for e in PAYROLL_STORE if "BANK_SWAP" in e["exception_codes"]
    )
    pay_jump_count = sum(
        1 for e in PAYROLL_STORE if "UNEXPLAINED_PAY_JUMP" in e["exception_codes"]
    )
    statutory_alert_count = sum(
        1 for e in PAYROLL_STORE if "STATUTORY_VARIANCE" in e["exception_codes"]
    )

    # Calculate total cash at risk caught before disbursement
    ghost_risk_amount = sum(
        e["current_gross_pay"]
        for e in PAYROLL_STORE
        if "GHOST_WORKER" in e["exception_codes"]
    )
    unexplained_jump_amount = sum(
        max(0.0, e["current_basic_pay"] - e["hr_approved_basic_pay"])
        for e in PAYROLL_STORE
        if "UNEXPLAINED_PAY_JUMP" in e["exception_codes"]
    )
    bank_swap_amount = sum(
        e["draft_net_pay"]
        for e in PAYROLL_STORE
        if "BANK_SWAP" in e["exception_codes"]
    )
    total_amount_protected = round(
        ghost_risk_amount
        + unexplained_jump_amount
        + bank_swap_amount
        + max(0.0, statutory_shortfall),
        2,
    )

    prior_headcount = sum(1 for e in PAYROLL_STORE if e["prior_gross_pay"] > 0)
    new_hires_count = sum(
        1 for e in PAYROLL_STORE if e["employment_status"] == "New Hire"
    )
    exited_count = sum(
        1 for e in PAYROLL_STORE if e["employment_status"] == "Exited"
    )
    active_paid_headcount = sum(
        1
        for e in PAYROLL_STORE
        if e["current_gross_pay"] > 0 and e["employment_status"] != "Exited"
    )

    return {
        "payroll_period": "October 2026",
        "prior_period": "September 2026",
        "total_records": len(PAYROLL_STORE),
        "prior_headcount": prior_headcount,
        "new_hires_count": new_hires_count,
        "exited_count": exited_count,
        "active_paid_headcount": active_paid_headcount,
        "prior_total_gross": prior_total_gross,
        "current_total_gross": current_total_gross,
        "gross_variance": gross_variance,
        "prior_total_net": prior_total_net,
        "current_total_net": current_total_net,
        "total_paye": total_paye,
        "total_nssf": total_nssf,
        "total_shif": total_shif,
        "total_housing_levy": total_housing_levy,
        "total_statutory": total_statutory,
        "expected_total_statutory": expected_total_statutory,
        "statutory_shortfall": statutory_shortfall,
        "flagged_count": len(flagged_employees),
        "verified_count": len(verified_employees),
        "approved_count": len(approved_employees),
        "ghost_worker_count": ghost_worker_count,
        "bank_swap_count": bank_swap_count,
        "pay_jump_count": pay_jump_count,
        "statutory_alert_count": statutory_alert_count,
        "total_amount_protected": total_amount_protected,
        "ready_for_cfo_signoff": len(flagged_employees) == 0,
    }


@app.get("/api/health")
def health_check() -> Dict[str, Any]:
    return {
        "status": "ok",
        "agent_id": "05",
        "service": "HR_PayrollReconAgent",
        "title": "Payroll Variance, Statutory Compliance & Payslip Recon Agent",
        "employees_loaded": len(PAYROLL_STORE),
    }


@app.post("/api/auth/otp/request")
def request_otp(payload: OTPRequestPayload) -> Dict[str, Any]:
    email = (payload.email or "").strip().lower()
    if not email or "@" not in email:
        raise HTTPException(
            status_code=400, detail="Please enter a valid company work email address."
        )
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
        "message": (
            f"6-digit verification code sent to {email}."
            if sent_via_smtp
            else f"6-digit verification code generated for {email} (Preview code: {code})."
        ),
        "email": email,
    }
    if not sent_via_smtp:
        response["preview_code"] = code
    return response


@app.post("/api/auth/otp/verify")
def verify_otp(payload: OTPVerifyPayload) -> Dict[str, Any]:
    email = (payload.email or "").strip().lower()
    code = (payload.code or "").strip()
    ok, message = verify_stored_otp(email, code)
    if not ok:
        raise HTTPException(status_code=401, detail=message)
    return {
        "ok": True,
        "user": {
            "email": email,
            "name": format_name_from_email(email),
            "role": "Head of Payroll & Statutory Compliance",
            "auth_method": "otp",
        },
    }


@app.post("/api/auth/google")
def google_auth(payload: GoogleAuthPayload) -> Dict[str, Any]:
    ok, user_info, message = verify_google_id_token(payload.credential)
    if not ok:
        raise HTTPException(status_code=401, detail=message)
    return {
        "ok": True,
        "user": {
            "email": user_info.get("email"),
            "name": user_info.get("name"),
            "picture": user_info.get("picture"),
            "role": "Head of Payroll & Statutory Compliance",
            "auth_method": "google",
        },
    }


@app.post("/api/auth/demo")
def demo_auth() -> Dict[str, Any]:
    return {
        "ok": True,
        "user": {
            "email": "head.payroll@sybyl.com",
            "name": "Margaret Ndungu (Head of Payroll)",
            "role": "Head of Payroll & Statutory Compliance",
            "auth_method": "demo",
        },
    }


@app.get("/api/payroll")
def list_payroll() -> Dict[str, Any]:
    return {
        "kpis": compute_kpis(),
        "employees": PAYROLL_STORE,
    }


@app.get("/api/payroll/{employee_id}")
def get_employee_payroll(employee_id: str) -> Dict[str, Any]:
    for emp in PAYROLL_STORE:
        if emp["employee_id"] == employee_id:
            return {"employee": emp, "kpis": compute_kpis()}
    raise HTTPException(
        status_code=404, detail=f"Employee record {employee_id} not found."
    )


@app.post("/api/payroll/simulate")
def simulate_employee_payroll(payload: SimulatePayrollPayload) -> Dict[str, Any]:
    for emp in PAYROLL_STORE:
        if emp["employee_id"] == payload.employee_id:
            if payload.remove_exited_employee and emp["employment_status"] == "Exited":
                emp["current_basic_pay"] = 0.0
                emp["current_house_allowance"] = 0.0
                emp["current_transport_allowance"] = 0.0
                emp["current_bonus_overtime"] = 0.0
                emp["statutory_auto_sync"] = True
                emp["hr_reference_note"] = (
                    f"Removed exited employee ({emp.get('exit_date')}) from October 2026 payout • KES 0.00 disbursed"
                )
            else:
                emp["current_basic_pay"] = round(float(payload.current_basic_pay), 2)
                emp["current_house_allowance"] = round(
                    float(payload.current_house_allowance), 2
                )
                emp["current_transport_allowance"] = round(
                    float(payload.current_transport_allowance), 2
                )
                emp["current_bonus_overtime"] = round(
                    float(payload.current_bonus_overtime), 2
                )

            if payload.apply_statutory_rates:
                emp["statutory_auto_sync"] = True

            if payload.revert_bank_to_verified:
                emp["current_bank_name"] = emp["hr_verified_bank_name"]
                emp["current_bank_account"] = emp["hr_verified_bank_account"]
                emp["bank_change_authorized"] = True
                emp["hr_reference_note"] = (
                    f"Reverted bank details to HR Master verified account ({emp['hr_verified_bank_name']} • {emp['hr_verified_bank_account']})"
                )

            if payload.verify_tax_pin:
                if emp["kra_pin"].startswith("PENDING"):
                    emp["kra_pin"] = "A015928374F"
                if emp["shif_no"].startswith("PENDING"):
                    emp["shif_no"] = "SHIF-8899104"
                emp["tax_pin_verified"] = True

            if payload.authorize_salary_change:
                emp["hr_approved_basic_pay"] = emp["current_basic_pay"]
                emp["salary_change_authorized"] = True

            run_payroll_reconciliation(emp)
            return {
                "ok": True,
                "message": (
                    f"Updated and recalculated statutory payslip for {emp['full_name']} ({emp['employee_id']})."
                ),
                "employee": emp,
                "kpis": compute_kpis(),
            }
    raise HTTPException(
        status_code=404, detail=f"Employee record {payload.employee_id} not found."
    )


@app.post("/api/payroll/{employee_id}/approve")
def approve_employee_payroll(
    employee_id: str, payload: ApproveEmployeePayload
) -> Dict[str, Any]:
    for emp in PAYROLL_STORE:
        if emp["employee_id"] == employee_id:
            if payload.resolve_exceptions and emp["has_exceptions"]:
                # Automatically apply HR Master verified controls to resolve exceptions
                if emp["employment_status"] == "Exited":
                    emp["current_basic_pay"] = 0.0
                    emp["current_house_allowance"] = 0.0
                    emp["current_transport_allowance"] = 0.0
                    emp["current_bonus_overtime"] = 0.0
                    emp["hr_reference_note"] = (
                        f"Resolved Ghost-Worker Alert: Removed exited employee ({emp.get('exit_date')}) from October 2026 payout."
                    )
                else:
                    if "UNEXPLAINED_PAY_JUMP" in emp["exception_codes"]:
                        emp["current_basic_pay"] = emp["hr_approved_basic_pay"]
                        emp["salary_change_authorized"] = True
                        emp["hr_reference_note"] = (
                            f"Restored basic pay to HR-approved level (KES {emp['hr_approved_basic_pay']:,.2f})."
                        )
                    if "BANK_SWAP" in emp["exception_codes"]:
                        emp["current_bank_name"] = emp["hr_verified_bank_name"]
                        emp["current_bank_account"] = emp["hr_verified_bank_account"]
                        emp["bank_change_authorized"] = True
                        emp["hr_reference_note"] = (
                            f"Locked disbursement to HR-verified bank account ({emp['hr_verified_bank_name']} • {emp['hr_verified_bank_account']})."
                        )
                    if "STATUTORY_VARIANCE" in emp["exception_codes"]:
                        emp["statutory_auto_sync"] = True
                        if emp["kra_pin"].startswith("PENDING"):
                            emp["kra_pin"] = "A015928374F"
                        if emp["shif_no"].startswith("PENDING"):
                            emp["shif_no"] = "SHIF-8899104"
                        emp["tax_pin_verified"] = True
                        emp["hr_reference_note"] = (
                            "Applied official statutory PAYE, NSSF, SHIF & Housing Levy rates and verified KRA PIN."
                        )

            run_payroll_reconciliation(emp)
            if emp["has_exceptions"]:
                raise HTTPException(
                    status_code=400,
                    detail="Please resolve the flagged payroll exception before approving this record.",
                )

            now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            emp["approval_status"] = "APPROVED"
            emp["approved_by"] = payload.approved_by or "Head of Payroll"
            emp["approved_at"] = now_iso
            return {
                "ok": True,
                "message": f"Approved October 2026 payroll record for {emp['full_name']} ({emp['employee_id']}).",
                "employee": emp,
                "kpis": compute_kpis(),
            }
    raise HTTPException(
        status_code=404, detail=f"Employee record {employee_id} not found."
    )


@app.post("/api/payroll/approve-all-verified")
def approve_all_verified(payload: ApproveEmployeePayload) -> Dict[str, Any]:
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    count = 0
    for emp in PAYROLL_STORE:
        run_payroll_reconciliation(emp)
        if not emp["has_exceptions"] and emp["approval_status"] != "APPROVED":
            emp["approval_status"] = "APPROVED"
            emp["approved_by"] = payload.approved_by or "Head of Payroll"
            emp["approved_at"] = now_iso
            count += 1
    return {
        "ok": True,
        "message": f"Approved {count} verified employee payroll records.",
        "employees": PAYROLL_STORE,
        "kpis": compute_kpis(),
    }


@app.post("/api/payroll/reset")
def reset_payroll_store() -> Dict[str, Any]:
    global PAYROLL_STORE
    PAYROLL_STORE = build_payroll_store()
    return {
        "ok": True,
        "message": "Reset October 2026 payroll records to initial audit state.",
        "employees": PAYROLL_STORE,
        "kpis": compute_kpis(),
    }


def build_plain_english_agent_reply(
    question: str, emp: Dict[str, Any], kpis: Dict[str, Any]
) -> str:
    q_lower = (question or "").lower()

    if "bank" in q_lower or "account" in q_lower or "swap" in q_lower:
        bank_swaps = [
            e for e in PAYROLL_STORE if "BANK_SWAP" in e["exception_codes"]
        ]
        verified_changes = [
            e
            for e in PAYROLL_STORE
            if e["bank_account_changed"] and e["bank_change_authorized"]
        ]
        swap_lines = (
            "\n".join(
                f"- **{e['full_name']} ({e['employee_id']} — {e['job_title']})**: Changed from **{e['prior_bank_name']} ({e['prior_bank_account']})** to **{e['current_bank_name']} ({e['current_bank_account']})** with **no signed HR Bank Change Form**. Net payout at risk: **KES {e['draft_net_pay']:,.2f}**."
                for e in bank_swaps
            )
            or "- None — all unverified bank account changes have been resolved."
        )
        verified_lines = (
            "\n".join(
                f"- **{e['full_name']} ({e['employee_id']})**: Changed to **{e['current_bank_name']} ({e['current_bank_account']})** — verified against signed HR form & employee phone call-back."
                for e in verified_changes
            )
            or "- None"
        )
        return (
            f"### Bank Account Change Audit (October 2026 Payroll)\n\n"
            f"**1. Unverified Bank Account Changes Flagged for Hold ({len(bank_swaps)})**\n"
            f"{swap_lines}\n\n"
            f"**2. HR-Verified Bank Account Updates ({len(verified_changes)})**\n"
            f"{verified_lines}\n\n"
            f"**Recommended Action:** Click **Resolve & Approve** on any unverified bank change to lock disbursement back to the employee's verified HR Master bank account until a signed authorization form is received."
        )

    if "ghost" in q_lower or "exit" in q_lower or "terminat" in q_lower or "left" in q_lower:
        exited = [e for e in PAYROLL_STORE if e["employment_status"] == "Exited"]
        lines = "\n".join(
            f"- **{e['full_name']} ({e['employee_id']} — {e['job_title']})**: Exited on **{e.get('exit_date')}** (Offboarded via Agent #04), Draft Gross Pay: **KES {e['current_gross_pay']:,.2f}** (Net Payout: **KES {e['draft_net_pay']:,.2f}**)."
            for e in exited
        )
        return (
            f"### Exited & Ghost-Worker Payroll Check\n\n"
            f"The Payroll Reconciliation Agent cross-checked all {kpis['total_records']} draft payslips against HR Master exit logs:\n"
            f"{lines}\n\n"
            f"**Recommended Action:** Remove **{exited[0]['full_name']}** from the October 2026 regular payroll run so zero unauthorized salary is paid after their last working day."
        )

    if "statutory" in q_lower or "tax" in q_lower or "paye" in q_lower or "shif" in q_lower or "nssf" in q_lower:
        return (
            f"### Statutory Compliance Summary — {emp['full_name']} ({emp['employee_id']})\n\n"
            f"**1. Employee Gross-to-Net Statutory Breakdown**\n"
            f"- **Gross Monthly Pay**: **KES {emp['current_gross_pay']:,.2f}** (Basic: KES {emp['current_basic_pay']:,.2f}, House: KES {emp['current_house_allowance']:,.2f}, Transport: KES {emp['current_transport_allowance']:,.2f}, Bonus: KES {emp['current_bonus_overtime']:,.2f})\n"
            f"- **NSSF Pension (Tier I & II — 6% capped at KES 4,320)**: **KES {emp['expected_nssf']:,.2f}**\n"
            f"- **Taxable Pay (Gross less NSSF)**: **KES {emp['expected_taxable_pay']:,.2f}**\n"
            f"- **KRA PAYE Income Tax (after KES 2,400 Personal Relief)**: **KES {emp['expected_paye']:,.2f}** (Draft file shows: KES {emp['draft_paye']:,.2f})\n"
            f"- **SHIF Medical Contribution (2.75% of Gross)**: **KES {emp['expected_shif']:,.2f}** (Draft file shows: KES {emp['draft_shif']:,.2f})\n"
            f"- **Affordable Housing Levy (1.5% of Gross)**: **KES {emp['expected_housing_levy']:,.2f}** (Draft file shows: KES {emp['draft_housing_levy']:,.2f})\n"
            f"- **Verified Net Take-Home Pay**: **KES {emp['expected_net_pay']:,.2f}**\n\n"
            f"**2. Company-Wide October 2026 Statutory Remittance Totals**\n"
            f"- **Total KRA PAYE**: **KES {kpis['total_paye']:,.2f}**\n"
            f"- **Total NSSF (Employee)**: **KES {kpis['total_nssf']:,.2f}**\n"
            f"- **Total SHIF (2.75%)**: **KES {kpis['total_shif']:,.2f}**\n"
            f"- **Total Housing Levy (1.5%)**: **KES {kpis['total_housing_levy']:,.2f}**"
        )

    # Default comprehensive executive & employee summary
    exception_text = (
        "\n".join(
            f"- **{ex['title']}**: {ex['detail']}" for ex in emp.get("exceptions", [])
        )
        if emp.get("exceptions")
        else "- **No Exceptions Flagged**: Salary, bank details, and statutory deductions (PAYE, NSSF, SHIF, Housing Levy) match HR Master records 100%."
    )

    return (
        f"### Payroll Reconciliation Summary: {emp['full_name']} (`{emp['employee_id']}` — {emp['job_title']})\n\n"
        f"**1. Month-over-Month Pay Comparison (Sep 2026 vs. Oct 2026)**\n"
        f"- **September 2026 Gross Pay**: **KES {emp['prior_gross_pay']:,.2f}** (Net Pay: **KES {emp['prior_net_pay']:,.2f}**)\n"
        f"- **October 2026 Draft Gross Pay**: **KES {emp['current_gross_pay']:,.2f}** (Monthly Change: **KES {emp['gross_variance']:+,.2f}**)\n"
        f"- **Bank Account**: **{emp['current_bank_name']} • {emp['current_bank_account']}**\n\n"
        f"**2. Audit Findings for {emp['full_name']}**\n"
        f"{exception_text}\n\n"
        f"**3. Overall October 2026 Payroll Run Status**\n"
        f"- **Total Draft Gross Payroll**: **KES {kpis['current_total_gross']:,.2f}** across **{kpis['total_records']} records**\n"
        f"- **Flagged Exceptions Remaining**: **{kpis['flagged_count']} employees** (Protecting **KES {kpis['total_amount_protected']:,.2f}** before disbursement)"
    )


@app.post("/api/agent/ask")
def ask_payroll_agent(payload: AgentAskPayload) -> Dict[str, Any]:
    emp = PAYROLL_STORE[0]
    if payload.employee_id:
        for item in PAYROLL_STORE:
            if item["employee_id"] == payload.employee_id:
                emp = item
                break

    kpis = compute_kpis()
    fallback_reply = build_plain_english_agent_reply(payload.question, emp, kpis)

    try:
        from google import genai

        use_vertex = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "0") == "1"
        project = os.getenv("GOOGLE_CLOUD_PROJECT", "gemini-enterprise-demo-498212")
        location = os.getenv("GOOGLE_CLOUD_LOCATION", "global")
        if use_vertex:
            client = genai.Client(vertexai=True, project=project, location=location)
        else:
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                return {"answer": fallback_reply, "model": "Payroll Reconciliation Agent"}
            client = genai.Client(api_key=api_key)

        prompt = (
            "You are the Payroll Reconciliation Agent for an enterprise HR & Payroll team.\n"
            "Use plain, clear HR and Payroll English with zero technical jargon.\n"
            f"Company Payroll KPIs:\n{kpis}\n\n"
            f"Selected Employee Record:\n{emp}\n\n"
            f"User Question: {payload.question}\n"
            "Provide exact KES amounts, statutory tax figures (PAYE, NSSF, SHIF, Housing Levy), and clear recommended HR actions."
        )
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        text = (response.text or "").strip()
        if text:
            return {"answer": text, "model": "Payroll Reconciliation Agent"}
    except Exception:
        pass

    return {"answer": fallback_reply, "model": "Payroll Reconciliation Agent"}


# Mount compiled React SPA if present
FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if FRONTEND_DIST.exists():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/{full_path:path}")
    def serve_spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="API route not found")
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.exists() and candidate.is_file():
            return FileResponse(str(candidate))
        return FileResponse(str(FRONTEND_DIST / "index.html"))
