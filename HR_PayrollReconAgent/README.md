# Agent #05: Payroll Variance, Statutory Compliance & Payslip Recon Agent (`HR_PayrollReconAgent`)

Built for **Heads of Payroll, Chief Human Resources Officers (CHROs), and Chief Financial Officers (CFOs)**, this agent reconciles the monthly draft payroll against prior-month payroll and HR Master records before salaries are disbursed.

## Core Capabilities
1. **Executive Sign-In Page with 3-Step Visual Workflow Diagram + Single Sign-On (SSO)**:
   - **Step 1**: Compare Prior vs. Current Payroll & HR Master
   - **Step 2**: Deterministic Statutory Tax & Bank-Swap Audit
   - **Step 3**: Approve Payroll & Print CFO/CHRO Sign-Off Sheet
   - Includes Google Single Sign-On (`GOOGLE_CLIENT_ID`), Work Email 6-Digit Verification Code, and 1-Click **Instant Demo Sign-In (Head of Payroll)**.
2. **Pre-Disbursement Exception Detection**:
   - **Ghost-Worker Alert**: Catches terminated/offboarded staff (`EMP-KE-104 Kevin Omondi`) still listed on the active draft payroll.
   - **Unauthorized Bank Account Change Alert**: Flags bank account swaps (`EMP-KE-103 David Mwangi`) lacking a signed HR Bank Change Authorization Form.
   - **Unexplained Basic Pay Jump Alert**: Flags unapproved salary jumps (`EMP-KE-102 Grace Wanjiku`, +50% basic pay jump).
   - **Statutory Tax & PIN Discrepancy Alert**: Catches manual PAYE overrides (`EMP-KE-106 Brian Kiprop`) and missing SHIF/Housing Levy/KRA PINs on new hires (`EMP-KE-109 Faith Mutua`).
3. **Deterministic Statutory Tax Engine (Python)**:
   - Calculates KRA PAYE (graduated monthly tax bands less KES 2,400 Personal Relief), NSSF (Tier I & II capped at KES 4,320), SHIF (2.75% of gross pay), and Affordable Housing Levy (1.5% of gross pay) to the exact cent.
4. **1-Page Printable CFO / CHRO Payroll Reconciliation Sign-Off Certificate** & **Ask Payroll Agent** plain-English Q&A assistant.
