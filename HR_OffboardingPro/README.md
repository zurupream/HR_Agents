# HR Offboarding Pro — Multi-Agent Employee Exit, Clearance & Final Settlement Platform

**HR Offboarding Pro** is an Apple-grade, multi-agent employee exit and clearance platform designed for People Operations teams. It operates in the exact reverse sequence of employee onboarding — coordinating benefits termination, commute pass revocation, physical laptop recovery, final IT email deactivation, deterministic final settlement calculations, and Certificate of Service issuance.

---

## High-Level 3-Step Reverse Architecture

1. **Step 1: Exit Notice & Clearance Launch (`Final Clearance & Settlement Agent`)**
   - Logs Voluntary Resignation, End-of-Contract, or Internship Completion notices.
   - Deterministically calculates **Pro-Rata Final Month Salary**, **Accrued Unused Leave Encashment**, and **Equipment Recovery Deductions** to produce **Net Final Settlement Payable**.
   - Dispatches an interactive Employee Clearance & Final Settlement E-Sign link (`/sign/{signing_token}`).

2. **Step 2: Reverse Role-Based De-Provisioning & Asset Recovery Agents (`Offboarding Orchestrator Agent`)**
   - **Full-Time Employee (`EMPLOYEE`)**: `1. Health Insurance Cancellation Agent` → `2. Uber Commute Pass Revocation Agent` → `3. Laptop Return & Asset Clearance Agent` → `4. IT Email & Access Deactivation Agent`
   - **Graduate Trainee (`TRAINEE`)**: `1. Uber Commute Pass Revocation Agent` → `2. Laptop Return & Asset Clearance Agent` → `3. IT Email & Access Deactivation Agent`
   - **Intern (`INTERN`)**: `1. IT Email & Access Deactivation Agent`
   - *Smart Dependency Protection*: Work Email & Single Sign-On deactivation automatically waits until physical Laptop Return & Data Wipe is completed so the exiting employee can coordinate handover logistics.

3. **Step 3: Employee E-Signature & Certificate of Service**
   - Employee digitally signs the **Final Clearance & Settlement Statement PDF** online (or raises a Final Settlement query that alerts the **HR Action Center**).
   - Once cleared, the platform releases the Net Final Settlement for payroll payout and generates the official **Certificate of Service & Good Standing PDF**.

---

## Quick Start

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

Run the automated test suite:

```bash
pytest -v
```
