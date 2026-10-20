"""
Seed data & deterministic Statutory Payroll & Variance Reconciliation Engine for
Agent #05: Payroll Variance, Statutory Compliance & Payslip Recon Agent.
"""

from copy import deepcopy
from typing import Any, Dict, List


def calculate_statutory_deductions(gross_pay: float) -> Dict[str, float]:
    """
    Deterministic statutory payroll calculation (Kenya PAYE, NSSF, SHIF, Housing Levy):
      - NSSF (Tier I + Tier II): 6% of gross pensionable pay, capped at KES 4,320.00/month
      - SHIF (Social Health Insurance Fund): 2.75% of gross pay (min KES 300.00 when gross > 0)
      - Affordable Housing Levy (AHL): 1.5% of gross pay
      - Taxable Pay = Gross Pay - NSSF Employee Contribution
      - PAYE (Graduated Monthly Tax Bands less KES 2,400.00 Personal Relief):
          * First KES 24,000 @ 10%
          * Next KES 8,333 (24,001 - 32,333) @ 25%
          * Next KES 467,667 (32,334 - 500,000) @ 30%
          * Next KES 300,000 (500,001 - 800,000) @ 32.5%
          * Above KES 800,000 @ 35%
    """
    gross = max(0.0, round(float(gross_pay), 2))
    if gross <= 0.0:
        return {
            "gross_pay": 0.0,
            "nssf": 0.0,
            "shif": 0.0,
            "housing_levy": 0.0,
            "taxable_pay": 0.0,
            "gross_paye_before_relief": 0.0,
            "personal_relief": 0.0,
            "paye": 0.0,
            "total_statutory": 0.0,
            "net_pay": 0.0,
            "employer_nssf": 0.0,
            "employer_housing_levy": 0.0,
            "total_employer_cost": 0.0,
        }

    nssf = min(round(gross * 0.06, 2), 4320.00)
    shif = max(300.00, round(gross * 0.0275, 2))
    housing_levy = round(gross * 0.015, 2)
    taxable = max(0.0, round(gross - nssf, 2))

    # Graduated monthly PAYE calculation
    remaining = taxable
    tax = 0.0

    # Band 1: 0 - 24,000 @ 10%
    b1 = min(remaining, 24000.0)
    tax += b1 * 0.10
    remaining -= b1

    # Band 2: next 8,333 @ 25%
    if remaining > 0:
        b2 = min(remaining, 8333.0)
        tax += b2 * 0.25
        remaining -= b2

    # Band 3: next 467,667 @ 30%
    if remaining > 0:
        b3 = min(remaining, 467667.0)
        tax += b3 * 0.30
        remaining -= b3

    # Band 4: next 300,000 @ 32.5%
    if remaining > 0:
        b4 = min(remaining, 300000.0)
        tax += b4 * 0.325
        remaining -= b4

    # Band 5: above 800,000 @ 35%
    if remaining > 0:
        tax += remaining * 0.35

    gross_paye = round(tax, 2)
    personal_relief = 2400.00 if taxable > 24000.0 else round(min(gross_paye, 2400.00), 2)
    paye = max(0.0, round(gross_paye - personal_relief, 2))

    total_statutory = round(paye + nssf + shif + housing_levy, 2)
    net_pay = max(0.0, round(gross - total_statutory, 2))

    return {
        "gross_pay": gross,
        "nssf": nssf,
        "shif": shif,
        "housing_levy": housing_levy,
        "taxable_pay": taxable,
        "gross_paye_before_relief": gross_paye,
        "personal_relief": personal_relief,
        "paye": paye,
        "total_statutory": total_statutory,
        "net_pay": net_pay,
        "employer_nssf": nssf,
        "employer_housing_levy": housing_levy,
        "total_employer_cost": round(gross + nssf + housing_levy, 2),
    }


def run_payroll_reconciliation(emp: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deterministic Payroll Reconciliation & Statutory Audit for an employee record.
    Compares:
      1. Prior Month Payroll (September 2026) vs. Current Draft Payroll (October 2026)
      2. HR Master Employment Status (catches Ghost Workers / Exited staff still on payroll)
      3. Bank Account Audit (catches unauthorized bank account swaps)
      4. Basic Pay & Allowance Variance Audit (catches unexplained pay jumps)
      5. Statutory Deductions Audit (verifies PAYE, NSSF, SHIF, and Housing Levy to the cent)
    """
    prior_gross = round(
        float(emp.get("prior_basic_pay", 0.0))
        + float(emp.get("prior_house_allowance", 0.0))
        + float(emp.get("prior_transport_allowance", 0.0))
        + float(emp.get("prior_bonus_overtime", 0.0)),
        2,
    )
    prior_calc = calculate_statutory_deductions(prior_gross)
    emp["prior_gross_pay"] = prior_gross
    emp["prior_net_pay"] = prior_calc["net_pay"]
    emp["prior_paye"] = prior_calc["paye"]
    emp["prior_nssf"] = prior_calc["nssf"]
    emp["prior_shif"] = prior_calc["shif"]
    emp["prior_housing_levy"] = prior_calc["housing_levy"]

    # Current draft gross pay components
    current_basic = round(float(emp.get("current_basic_pay", 0.0)), 2)
    current_house = round(float(emp.get("current_house_allowance", 0.0)), 2)
    current_transport = round(float(emp.get("current_transport_allowance", 0.0)), 2)
    current_bonus = round(float(emp.get("current_bonus_overtime", 0.0)), 2)
    current_gross = round(current_basic + current_house + current_transport + current_bonus, 2)

    emp["current_gross_pay"] = current_gross
    emp["gross_variance"] = round(current_gross - prior_gross, 2)
    emp["basic_pay_variance"] = round(current_basic - float(emp.get("prior_basic_pay", 0.0)), 2)
    emp["basic_pay_variance_pct"] = (
        round((emp["basic_pay_variance"] / float(emp["prior_basic_pay"])) * 100.0, 1)
        if float(emp.get("prior_basic_pay", 0.0)) > 0
        else 0.0
    )

    # Expected statutory deductions from our deterministic Python tax engine
    expected = calculate_statutory_deductions(current_gross)
    emp["expected_paye"] = expected["paye"]
    emp["expected_nssf"] = expected["nssf"]
    emp["expected_shif"] = expected["shif"]
    emp["expected_housing_levy"] = expected["housing_levy"]
    emp["expected_taxable_pay"] = expected["taxable_pay"]
    emp["expected_personal_relief"] = expected["personal_relief"]
    emp["expected_total_statutory"] = expected["total_statutory"]
    emp["expected_net_pay"] = expected["net_pay"]
    emp["employer_nssf"] = expected["employer_nssf"]
    emp["employer_housing_levy"] = expected["employer_housing_levy"]
    emp["total_employer_cost"] = expected["total_employer_cost"]

    # If the record does not have manual draft overrides or if statutory_auto_sync is True, sync draft to expected
    if emp.get("statutory_auto_sync", True):
        emp["draft_paye"] = expected["paye"]
        emp["draft_nssf"] = expected["nssf"]
        emp["draft_shif"] = expected["shif"]
        emp["draft_housing_levy"] = expected["housing_levy"]
    else:
        emp["draft_paye"] = round(float(emp.get("draft_paye", expected["paye"])), 2)
        emp["draft_nssf"] = round(float(emp.get("draft_nssf", expected["nssf"])), 2)
        emp["draft_shif"] = round(float(emp.get("draft_shif", expected["shif"])), 2)
        emp["draft_housing_levy"] = round(float(emp.get("draft_housing_levy", expected["housing_levy"])), 2)

    emp["draft_total_statutory"] = round(
        emp["draft_paye"] + emp["draft_nssf"] + emp["draft_shif"] + emp["draft_housing_levy"],
        2,
    )
    emp["draft_net_pay"] = max(0.0, round(current_gross - emp["draft_total_statutory"], 2))
    emp["statutory_discrepancy"] = round(expected["total_statutory"] - emp["draft_total_statutory"], 2)

    # Check all HR & Payroll exception conditions
    exceptions: List[Dict[str, str]] = []
    exception_codes: List[str] = []

    # 1. Ghost-worker check (Terminated employee still on active draft payroll)
    if emp.get("employment_status") == "Exited" and current_gross > 0:
        exception_codes.append("GHOST_WORKER")
        exceptions.append(
            {
                "code": "GHOST_WORKER",
                "severity": "CRITICAL",
                "title": "Terminated Employee Still on Draft Payroll (Ghost-Worker Alert)",
                "detail": (
                    f"{emp['full_name']} exited on {emp.get('exit_date', '28 Sep 2026')} "
                    f"({emp.get('hr_reference_note', 'Offboarding completed')}), but is still scheduled for "
                    f"KES {current_gross:,.2f} gross pay (KES {emp['draft_net_pay']:,.2f} net payout)."
                ),
            }
        )

    # 2. Unauthorized bank account change check
    bank_changed = (
        emp.get("current_bank_account") != emp.get("prior_bank_account")
        or emp.get("current_bank_name") != emp.get("prior_bank_name")
    )
    emp["bank_account_changed"] = bank_changed
    if bank_changed and not emp.get("bank_change_authorized", False):
        exception_codes.append("BANK_SWAP")
        exceptions.append(
            {
                "code": "BANK_SWAP",
                "severity": "CRITICAL",
                "title": "Unverified Bank Account Change Alert",
                "detail": (
                    f"Bank account changed from {emp.get('prior_bank_name')} ({emp.get('prior_bank_account')}) "
                    f"to {emp.get('current_bank_name')} ({emp.get('current_bank_account')}) without a signed HR Bank Change Authorization Form."
                ),
            }
        )

    # 3. Unexplained salary jump check
    if (
        emp.get("employment_status") != "Exited"
        and abs(current_basic - float(emp.get("hr_approved_basic_pay", current_basic))) > 1.0
        and not emp.get("salary_change_authorized", False)
    ):
        diff = current_basic - float(emp.get("hr_approved_basic_pay", current_basic))
        exception_codes.append("UNEXPLAINED_PAY_JUMP")
        exceptions.append(
            {
                "code": "UNEXPLAINED_PAY_JUMP",
                "severity": "CRITICAL",
                "title": "Unexplained Basic Pay Jump",
                "detail": (
                    f"Draft basic pay is KES {current_basic:,.2f} vs. HR Master approved basic pay of "
                    f"KES {float(emp['hr_approved_basic_pay']):,.2f} (+KES {diff:,.2f} / +{emp['basic_pay_variance_pct']}% jump) "
                    f"with no signed promotion or salary increment letter."
                ),
            }
        )

    # 4. Statutory deduction discrepancy or missing KRA Tax PIN
    if emp.get("employment_status") != "Exited" and abs(emp["statutory_discrepancy"]) > 1.0:
        exception_codes.append("STATUTORY_VARIANCE")
        exceptions.append(
            {
                "code": "STATUTORY_VARIANCE",
                "severity": "WARNING",
                "title": "Statutory Tax & Deduction Calculation Mismatch",
                "detail": (
                    f"Draft statutory deductions total KES {emp['draft_total_statutory']:,.2f}, but official KRA/NSSF/SHIF/Housing Levy "
                    f"formulas require KES {expected['total_statutory']:,.2f} (under-deducted by KES {emp['statutory_discrepancy']:,.2f})."
                ),
            }
        )

    if emp.get("employment_status") != "Exited" and not emp.get("tax_pin_verified", True):
        if "STATUTORY_VARIANCE" not in exception_codes:
            exception_codes.append("STATUTORY_VARIANCE")
        exceptions.append(
            {
                "code": "MISSING_TAX_PIN",
                "severity": "WARNING",
                "title": "Pending KRA Tax PIN / SHIF Registration Verification",
                "detail": (
                    f"Employee KRA PIN ({emp.get('kra_pin', 'Pending')}) or SHIF registration is flagged for verification before tax remittance."
                ),
            }
        )

    emp["exceptions"] = exceptions
    emp["exception_codes"] = exception_codes
    emp["has_exceptions"] = len(exceptions) > 0

    if any(e["severity"] == "CRITICAL" for e in exceptions):
        emp["risk_level"] = "CRITICAL"
        emp["status_color"] = "#FF3B30"
        if emp.get("approval_status") == "APPROVED":
            emp["approval_status"] = "FLAGGED"
    elif len(exceptions) > 0:
        emp["risk_level"] = "WARNING"
        emp["status_color"] = "#FF9500"
        if emp.get("approval_status") == "APPROVED":
            emp["approval_status"] = "FLAGGED"
    else:
        emp["risk_level"] = "VERIFIED"
        emp["status_color"] = "#34C759"
        if emp.get("approval_status") == "FLAGGED":
            emp["approval_status"] = "READY_FOR_APPROVAL"

    return emp


INITIAL_PAYROLL_RECORDS: List[Dict[str, Any]] = [
    {
        "employee_id": "EMP-KE-101",
        "full_name": "Wanjiru Kamau",
        "job_title": "Head of Finance & Treasury",
        "department": "Finance & Accounting",
        "employment_status": "Active",
        "join_date": "2021-03-15",
        "exit_date": None,
        "kra_pin": "A009482190K",
        "tax_pin_verified": True,
        "nssf_no": "NSSF-2091842",
        "shif_no": "SHIF-8841201",
        "prior_basic_pay": 340000.00,
        "prior_house_allowance": 50000.00,
        "prior_transport_allowance": 30000.00,
        "prior_bonus_overtime": 0.00,
        "current_basic_pay": 340000.00,
        "current_house_allowance": 50000.00,
        "current_transport_allowance": 30000.00,
        "current_bonus_overtime": 0.00,
        "hr_approved_basic_pay": 340000.00,
        "salary_change_authorized": True,
        "prior_bank_name": "Stanbic Bank Kenya",
        "prior_bank_account": "0100008471920",
        "current_bank_name": "Stanbic Bank Kenya",
        "current_bank_account": "0100008471920",
        "hr_verified_bank_name": "Stanbic Bank Kenya",
        "hr_verified_bank_account": "0100008471920",
        "bank_change_authorized": True,
        "statutory_auto_sync": True,
        "hr_reference_note": "No changes from September 2026 payroll • All statutory deductions verified",
        "approval_status": "APPROVED",
        "approved_by": "Head of Payroll",
        "approved_at": "2026-10-19T14:20:00Z",
    },
    {
        "employee_id": "EMP-KE-102",
        "full_name": "Grace Wanjiku",
        "job_title": "Operations Supervisor",
        "department": "Operations & Logistics",
        "employment_status": "Active",
        "join_date": "2022-07-01",
        "exit_date": None,
        "kra_pin": "A011294810M",
        "tax_pin_verified": True,
        "nssf_no": "NSSF-3104921",
        "shif_no": "SHIF-8843910",
        "prior_basic_pay": 150000.00,
        "prior_house_allowance": 25000.00,
        "prior_transport_allowance": 15000.00,
        "prior_bonus_overtime": 0.00,
        "current_basic_pay": 225000.00,
        "current_house_allowance": 25000.00,
        "current_transport_allowance": 15000.00,
        "current_bonus_overtime": 0.00,
        "hr_approved_basic_pay": 150000.00,
        "salary_change_authorized": False,
        "prior_bank_name": "KCB Bank Kenya",
        "prior_bank_account": "1104829104",
        "current_bank_name": "KCB Bank Kenya",
        "current_bank_account": "1104829104",
        "hr_verified_bank_name": "KCB Bank Kenya",
        "hr_verified_bank_account": "1104829104",
        "bank_change_authorized": True,
        "statutory_auto_sync": True,
        "hr_reference_note": "EXCEPTION: Basic pay jumped +50% (+KES 75,000) with no HR increment letter on file",
        "approval_status": "FLAGGED",
        "approved_by": None,
        "approved_at": None,
    },
    {
        "employee_id": "EMP-KE-103",
        "full_name": "David Mwangi",
        "job_title": "Senior Procurement Lead",
        "department": "Supply Chain & Procurement",
        "employment_status": "Active",
        "join_date": "2020-11-10",
        "exit_date": None,
        "kra_pin": "A008192045P",
        "tax_pin_verified": True,
        "nssf_no": "NSSF-1948201",
        "shif_no": "SHIF-8810294",
        "prior_basic_pay": 195000.00,
        "prior_house_allowance": 30000.00,
        "prior_transport_allowance": 15000.00,
        "prior_bonus_overtime": 0.00,
        "current_basic_pay": 195000.00,
        "current_house_allowance": 30000.00,
        "current_transport_allowance": 15000.00,
        "current_bonus_overtime": 0.00,
        "hr_approved_basic_pay": 195000.00,
        "salary_change_authorized": True,
        "prior_bank_name": "Stanbic Bank Kenya",
        "prior_bank_account": "0100004829101",
        "current_bank_name": "Equity Bank Kenya",
        "current_bank_account": "0470199823114",
        "hr_verified_bank_name": "Stanbic Bank Kenya",
        "hr_verified_bank_account": "0100004829101",
        "bank_change_authorized": False,
        "statutory_auto_sync": True,
        "hr_reference_note": "EXCEPTION: Bank account changed to Equity Bank (0470199823114) without HR sign-off",
        "approval_status": "FLAGGED",
        "approved_by": None,
        "approved_at": None,
    },
    {
        "employee_id": "EMP-KE-104",
        "full_name": "Kevin Omondi",
        "job_title": "Regional Sales Executive",
        "department": "Commercial & Sales",
        "employment_status": "Exited",
        "join_date": "2023-02-01",
        "exit_date": "2026-09-28",
        "kra_pin": "A013849201Z",
        "tax_pin_verified": True,
        "nssf_no": "NSSF-4401928",
        "shif_no": "SHIF-8892014",
        "prior_basic_pay": 145000.00,
        "prior_house_allowance": 25000.00,
        "prior_transport_allowance": 15000.00,
        "prior_bonus_overtime": 0.00,
        "current_basic_pay": 145000.00,
        "current_house_allowance": 25000.00,
        "current_transport_allowance": 15000.00,
        "current_bonus_overtime": 0.00,
        "hr_approved_basic_pay": 0.00,
        "salary_change_authorized": False,
        "prior_bank_name": "Absa Bank Kenya",
        "prior_bank_account": "2039481029",
        "current_bank_name": "Absa Bank Kenya",
        "current_bank_account": "2039481029",
        "hr_verified_bank_name": "Absa Bank Kenya",
        "hr_verified_bank_account": "2039481029",
        "bank_change_authorized": True,
        "statutory_auto_sync": True,
        "hr_reference_note": "CRITICAL: Offboarded on 28 Sep 2026 via Agent #04 (Exit Ref OFF-2026-019) — Still on Draft Payroll!",
        "approval_status": "FLAGGED",
        "approved_by": None,
        "approved_at": None,
    },
    {
        "employee_id": "EMP-KE-105",
        "full_name": "Amina Hassan",
        "job_title": "Senior HR Business Partner",
        "department": "People & Culture",
        "employment_status": "Active",
        "join_date": "2021-09-01",
        "exit_date": None,
        "kra_pin": "A010293847W",
        "tax_pin_verified": True,
        "nssf_no": "NSSF-2849102",
        "shif_no": "SHIF-8829104",
        "prior_basic_pay": 190000.00,
        "prior_house_allowance": 30000.00,
        "prior_transport_allowance": 15000.00,
        "prior_bonus_overtime": 0.00,
        "current_basic_pay": 220000.00,
        "current_house_allowance": 30000.00,
        "current_transport_allowance": 15000.00,
        "current_bonus_overtime": 0.00,
        "hr_approved_basic_pay": 220000.00,
        "salary_change_authorized": True,
        "prior_bank_name": "Standard Chartered Kenya",
        "prior_bank_account": "0102039481900",
        "current_bank_name": "Standard Chartered Kenya",
        "current_bank_account": "0102039481900",
        "hr_verified_bank_name": "Standard Chartered Kenya",
        "hr_verified_bank_account": "0102039481900",
        "bank_change_authorized": True,
        "statutory_auto_sync": True,
        "hr_reference_note": "Approved Promotion (+KES 30,000 basic pay) • Signed CHRO Ref HR-PROMO-2026-041",
        "approval_status": "APPROVED",
        "approved_by": "Head of Payroll",
        "approved_at": "2026-10-19T14:25:00Z",
    },
    {
        "employee_id": "EMP-KE-106",
        "full_name": "Brian Kiprop",
        "job_title": "Lead Software Engineer",
        "department": "Technology & Digital",
        "employment_status": "Active",
        "join_date": "2022-01-17",
        "exit_date": None,
        "kra_pin": "A012049581B",
        "tax_pin_verified": True,
        "nssf_no": "NSSF-3391024",
        "shif_no": "SHIF-8850192",
        "prior_basic_pay": 250000.00,
        "prior_house_allowance": 40000.00,
        "prior_transport_allowance": 20000.00,
        "prior_bonus_overtime": 0.00,
        "current_basic_pay": 250000.00,
        "current_house_allowance": 40000.00,
        "current_transport_allowance": 20000.00,
        "current_bonus_overtime": 0.00,
        "hr_approved_basic_pay": 250000.00,
        "salary_change_authorized": True,
        "prior_bank_name": "NCBA Bank Kenya",
        "prior_bank_account": "6501928374",
        "current_bank_name": "NCBA Bank Kenya",
        "current_bank_account": "6501928374",
        "hr_verified_bank_name": "NCBA Bank Kenya",
        "hr_verified_bank_account": "6501928374",
        "bank_change_authorized": True,
        "statutory_auto_sync": False,
        "draft_paye": 54597.25,
        "draft_nssf": 4320.00,
        "draft_shif": 8525.00,
        "draft_housing_levy": 4650.00,
        "hr_reference_note": "EXCEPTION: Manual PAYE override on draft file under-deducts KRA PAYE by KES 25,000.00",
        "approval_status": "FLAGGED",
        "approved_by": None,
        "approved_at": None,
    },
    {
        "employee_id": "EMP-KE-107",
        "full_name": "Esther Njuguna",
        "job_title": "Customer Success Manager",
        "department": "Customer Operations",
        "employment_status": "Active",
        "join_date": "2022-05-09",
        "exit_date": None,
        "kra_pin": "A011849203E",
        "tax_pin_verified": True,
        "nssf_no": "NSSF-3501928",
        "shif_no": "SHIF-8861029",
        "prior_basic_pay": 130000.00,
        "prior_house_allowance": 20000.00,
        "prior_transport_allowance": 15000.00,
        "prior_bonus_overtime": 0.00,
        "current_basic_pay": 130000.00,
        "current_house_allowance": 20000.00,
        "current_transport_allowance": 15000.00,
        "current_bonus_overtime": 25000.00,
        "hr_approved_basic_pay": 130000.00,
        "salary_change_authorized": True,
        "prior_bank_name": "Co-operative Bank Kenya",
        "prior_bank_account": "01109283741200",
        "current_bank_name": "Co-operative Bank Kenya",
        "current_bank_account": "01109283741200",
        "hr_verified_bank_name": "Co-operative Bank Kenya",
        "hr_verified_bank_account": "01109283741200",
        "bank_change_authorized": True,
        "statutory_auto_sync": True,
        "hr_reference_note": "Includes HR-approved Q3 Performance Bonus of KES 25,000 (Ref HR-BON-2026-088)",
        "approval_status": "APPROVED",
        "approved_by": "Head of Payroll",
        "approved_at": "2026-10-19T14:28:00Z",
    },
    {
        "employee_id": "EMP-KE-108",
        "full_name": "Samuel Otieno",
        "job_title": "Supply Chain & Fleet Coordinator",
        "department": "Operations & Logistics",
        "employment_status": "Active",
        "join_date": "2023-04-10",
        "exit_date": None,
        "kra_pin": "A014029384S",
        "tax_pin_verified": True,
        "nssf_no": "NSSF-4102938",
        "shif_no": "SHIF-8872019",
        "prior_basic_pay": 105000.00,
        "prior_house_allowance": 18000.00,
        "prior_transport_allowance": 12000.00,
        "prior_bonus_overtime": 0.00,
        "current_basic_pay": 105000.00,
        "current_house_allowance": 18000.00,
        "current_transport_allowance": 12000.00,
        "current_bonus_overtime": 0.00,
        "hr_approved_basic_pay": 105000.00,
        "salary_change_authorized": True,
        "prior_bank_name": "Equity Bank Kenya",
        "prior_bank_account": "0180293847102",
        "current_bank_name": "Equity Bank Kenya",
        "current_bank_account": "0180293847102",
        "hr_verified_bank_name": "Equity Bank Kenya",
        "hr_verified_bank_account": "0180293847102",
        "bank_change_authorized": True,
        "statutory_auto_sync": True,
        "hr_reference_note": "No variance from September 2026 • Statutory deductions 100% matched",
        "approval_status": "APPROVED",
        "approved_by": "Head of Payroll",
        "approved_at": "2026-10-19T14:30:00Z",
    },
    {
        "employee_id": "EMP-KE-109",
        "full_name": "Faith Mutua",
        "job_title": "Graduate Management Trainee",
        "department": "Commercial & Sales",
        "employment_status": "New Hire",
        "join_date": "2026-10-01",
        "exit_date": None,
        "kra_pin": "PENDING-PIN-VERIFY",
        "tax_pin_verified": False,
        "nssf_no": "NSSF-5910283",
        "shif_no": "PENDING-SHIF",
        "prior_basic_pay": 0.00,
        "prior_house_allowance": 0.00,
        "prior_transport_allowance": 0.00,
        "prior_bonus_overtime": 0.00,
        "current_basic_pay": 65000.00,
        "current_house_allowance": 12000.00,
        "current_transport_allowance": 8000.00,
        "current_bonus_overtime": 0.00,
        "hr_approved_basic_pay": 65000.00,
        "salary_change_authorized": True,
        "prior_bank_name": "N/A (New Hire Oct 2026)",
        "prior_bank_account": "N/A",
        "current_bank_name": "KCB Bank Kenya",
        "current_bank_account": "1290481920",
        "hr_verified_bank_name": "KCB Bank Kenya",
        "hr_verified_bank_account": "1290481920",
        "bank_change_authorized": True,
        "statutory_auto_sync": False,
        "draft_paye": 14833.25,
        "draft_nssf": 4320.00,
        "draft_shif": 0.00,
        "draft_housing_levy": 0.00,
        "hr_reference_note": "New Hire via Agent #03 (Joined 01 Oct 2026) • Missing SHIF (KES 2,337.50) & Housing Levy (KES 1,275.00) on draft sheet",
        "approval_status": "FLAGGED",
        "approved_by": None,
        "approved_at": None,
    },
    {
        "employee_id": "EMP-KE-110",
        "full_name": "Peter Karanja",
        "job_title": "Quality Assurance Specialist",
        "department": "Technology & Digital",
        "employment_status": "Active",
        "join_date": "2022-08-15",
        "exit_date": None,
        "kra_pin": "A012948102K",
        "tax_pin_verified": True,
        "nssf_no": "NSSF-3719204",
        "shif_no": "SHIF-8869102",
        "prior_basic_pay": 125000.00,
        "prior_house_allowance": 20000.00,
        "prior_transport_allowance": 10000.00,
        "prior_bonus_overtime": 0.00,
        "current_basic_pay": 125000.00,
        "current_house_allowance": 20000.00,
        "current_transport_allowance": 10000.00,
        "current_bonus_overtime": 0.00,
        "hr_approved_basic_pay": 125000.00,
        "salary_change_authorized": True,
        "prior_bank_name": "I&M Bank Kenya",
        "prior_bank_account": "001029384712",
        "current_bank_name": "I&M Bank Kenya",
        "current_bank_account": "001029384712",
        "hr_verified_bank_name": "I&M Bank Kenya",
        "hr_verified_bank_account": "001029384712",
        "bank_change_authorized": True,
        "statutory_auto_sync": True,
        "hr_reference_note": "No changes from September 2026 • Statutory deductions verified",
        "approval_status": "APPROVED",
        "approved_by": "Head of Payroll",
        "approved_at": "2026-10-19T14:32:00Z",
    },
    {
        "employee_id": "EMP-KE-111",
        "full_name": "Mercy Chebet",
        "job_title": "Regional Account Manager",
        "department": "Commercial & Sales",
        "employment_status": "Active",
        "join_date": "2021-06-01",
        "exit_date": None,
        "kra_pin": "A010847291C",
        "tax_pin_verified": True,
        "nssf_no": "NSSF-2610492",
        "shif_no": "SHIF-8831049",
        "prior_basic_pay": 160000.00,
        "prior_house_allowance": 25000.00,
        "prior_transport_allowance": 15000.00,
        "prior_bonus_overtime": 0.00,
        "current_basic_pay": 160000.00,
        "current_house_allowance": 25000.00,
        "current_transport_allowance": 15000.00,
        "current_bonus_overtime": 0.00,
        "hr_approved_basic_pay": 160000.00,
        "salary_change_authorized": True,
        "prior_bank_name": "KCB Bank Kenya",
        "prior_bank_account": "1109283741",
        "current_bank_name": "Absa Bank Kenya",
        "current_bank_account": "2048192034",
        "hr_verified_bank_name": "Absa Bank Kenya",
        "hr_verified_bank_account": "2048192034",
        "bank_change_authorized": True,
        "statutory_auto_sync": True,
        "hr_reference_note": "Authorized Bank Change to Absa Bank • Signed Form HR-BNK-2026-019 & Call-Back Verified",
        "approval_status": "READY_FOR_APPROVAL",
        "approved_by": None,
        "approved_at": None,
    },
    {
        "employee_id": "EMP-KE-112",
        "full_name": "Daniel Mutuku",
        "job_title": "IT Systems Administrator",
        "department": "Technology & Digital",
        "employment_status": "Active",
        "join_date": "2022-10-03",
        "exit_date": None,
        "kra_pin": "A013019284D",
        "tax_pin_verified": True,
        "nssf_no": "NSSF-3910482",
        "shif_no": "SHIF-8879012",
        "prior_basic_pay": 140000.00,
        "prior_house_allowance": 22000.00,
        "prior_transport_allowance": 13000.00,
        "prior_bonus_overtime": 0.00,
        "current_basic_pay": 140000.00,
        "current_house_allowance": 22000.00,
        "current_transport_allowance": 13000.00,
        "current_bonus_overtime": 0.00,
        "hr_approved_basic_pay": 140000.00,
        "salary_change_authorized": True,
        "prior_bank_name": "Stanbic Bank Kenya",
        "prior_bank_account": "0100009182734",
        "current_bank_name": "Stanbic Bank Kenya",
        "current_bank_account": "0100009182734",
        "hr_verified_bank_name": "Stanbic Bank Kenya",
        "hr_verified_bank_account": "0100009182734",
        "bank_change_authorized": True,
        "statutory_auto_sync": True,
        "hr_reference_note": "No changes from September 2026 • Statutory deductions verified",
        "approval_status": "APPROVED",
        "approved_by": "Head of Payroll",
        "approved_at": "2026-10-19T14:35:00Z",
    },
]


def build_payroll_store() -> List[Dict[str, Any]]:
    store = deepcopy(INITIAL_PAYROLL_RECORDS)
    for emp in store:
        run_payroll_reconciliation(emp)
    return store
