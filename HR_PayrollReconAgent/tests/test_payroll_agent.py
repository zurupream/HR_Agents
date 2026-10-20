"""
Pytest verification suite for Agent #05: Payroll Variance, Statutory Compliance & Payslip Recon Agent.
Tests deterministic statutory math (PAYE, NSSF, SHIF, Housing Levy), exception detection
(Ghost Worker, Bank Swap, Unexplained Pay Jump, Statutory Mismatch), SSO & OTP auth,
interactive what-if simulation, 1-click payroll approval, and Ask Payroll Agent.
"""

import sys
from pathlib import Path

from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from main import app  # noqa: E402
from seed_data import calculate_statutory_deductions  # noqa: E402

client = TestClient(app)


def setup_function():
    client.post("/api/payroll/reset")


def test_health_endpoint():
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["agent_id"] == "05"
    assert data["employees_loaded"] == 12


def test_deterministic_statutory_math():
    # Zero gross pay
    zero = calculate_statutory_deductions(0.0)
    assert zero["gross_pay"] == 0.0
    assert zero["paye"] == 0.0
    assert zero["nssf"] == 0.0
    assert zero["shif"] == 0.0
    assert zero["housing_levy"] == 0.0
    assert zero["net_pay"] == 0.0

    # KES 200,000 gross pay
    # NSSF = min(12,000, 4,320) = 4,320.00
    # SHIF = 2.75% of 200,000 = 5,500.00
    # Housing Levy = 1.5% of 200,000 = 3,000.00
    # Taxable Pay = 200,000 - 4,320 = 195,680.00
    # Gross PAYE:
    #   First 24,000 @ 10% = 2,400.00
    #   Next 8,333 @ 25% = 2,083.25
    #   Remaining (195,680 - 32,333 = 163,347) @ 30% = 49,004.10
    #   Total Gross PAYE = 53,487.35
    #   Less Personal Relief 2,400.00 => PAYE = 51,087.35
    # Total Statutory = 51,087.35 + 4,320 + 5,500 + 3,000 = 63,907.35
    # Net Pay = 200,000 - 63,907.35 = 136,092.65
    calc = calculate_statutory_deductions(200000.0)
    assert calc["nssf"] == 4320.00
    assert calc["shif"] == 5500.00
    assert calc["housing_levy"] == 3000.00
    assert calc["taxable_pay"] == 195680.00
    assert calc["paye"] == 51087.35
    assert calc["total_statutory"] == 63907.35
    assert calc["net_pay"] == 136092.65


def test_list_payroll_and_exception_flags():
    res = client.get("/api/payroll")
    assert res.status_code == 200
    data = res.json()
    kpis = data["kpis"]
    employees = {e["employee_id"]: e for e in data["employees"]}

    assert len(employees) == 12
    assert kpis["flagged_count"] == 5
    assert kpis["ghost_worker_count"] == 1
    assert kpis["bank_swap_count"] == 1
    assert kpis["pay_jump_count"] == 1
    assert kpis["statutory_alert_count"] == 2

    # EMP-KE-102: Unexplained basic pay jump
    assert "UNEXPLAINED_PAY_JUMP" in employees["EMP-KE-102"]["exception_codes"]
    # EMP-KE-103: Unauthorized bank account change
    assert "BANK_SWAP" in employees["EMP-KE-103"]["exception_codes"]
    # EMP-KE-104: Terminated employee still on draft payroll (Ghost worker)
    assert "GHOST_WORKER" in employees["EMP-KE-104"]["exception_codes"]
    # EMP-KE-106: Manual PAYE override statutory variance
    assert "STATUTORY_VARIANCE" in employees["EMP-KE-106"]["exception_codes"]


def test_simulate_and_resolve_exceptions():
    # Simulate removing exited ghost worker EMP-KE-104 from payroll
    res = client.post(
        "/api/payroll/simulate",
        json={
            "employee_id": "EMP-KE-104",
            "current_basic_pay": 145000.0,
            "current_house_allowance": 25000.0,
            "current_transport_allowance": 15000.0,
            "current_bonus_overtime": 0.0,
            "apply_statutory_rates": True,
            "remove_exited_employee": True,
        },
    )
    assert res.status_code == 200
    emp = res.json()["employee"]
    assert emp["current_gross_pay"] == 0.0
    assert emp["draft_net_pay"] == 0.0
    assert emp["has_exceptions"] is False

    # Resolve & approve unauthorized bank swap on EMP-KE-103
    res_approve = client.post(
        "/api/payroll/EMP-KE-103/approve",
        json={"approved_by": "Margaret Ndungu", "resolve_exceptions": True},
    )
    assert res_approve.status_code == 200
    emp_103 = res_approve.json()["employee"]
    assert emp_103["current_bank_account"] == emp_103["hr_verified_bank_account"]
    assert emp_103["has_exceptions"] is False
    assert emp_103["approval_status"] == "APPROVED"


def test_otp_and_demo_auth():
    # Consumer Gmail domain should be rejected
    bad_res = client.post("/api/auth/otp/request", json={"email": "random.user@gmail.com"})
    assert bad_res.status_code == 403

    # Business work email should succeed
    req_res = client.post("/api/auth/otp/request", json={"email": "payroll.head@company.co.ke"})
    assert req_res.status_code == 200
    data = req_res.json()
    assert data["ok"] is True
    code = data.get("preview_code")
    if code:
        ver_res = client.post(
            "/api/auth/otp/verify",
            json={"email": "payroll.head@company.co.ke", "code": code},
        )
        assert ver_res.status_code == 200
        assert ver_res.json()["user"]["email"] == "payroll.head@company.co.ke"

    # Demo auth endpoint
    demo_res = client.post("/api/auth/demo")
    assert demo_res.status_code == 200
    assert demo_res.json()["ok"] is True


def test_ask_payroll_agent():
    res = client.post(
        "/api/agent/ask",
        json={
            "question": "Which employees had bank account changes this month?",
            "employee_id": "EMP-KE-103",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert "David Mwangi" in data["answer"]
    assert "Equity Bank" in data["answer"]


def test_spa_root_served():
    res = client.get("/")
    assert res.status_code == 200
    assert "Payroll Variance, Statutory Compliance" in res.text

