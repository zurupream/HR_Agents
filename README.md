# Enterprise HR AI Agents — Live Portfolio & Executive Demo Catalog

> **📸 Browser E2E & Enterprise SSO Verification Gallery (22 Screenshots):** **[`E2E_SSO_SCREENSHOTS.md`](./E2E_SSO_SCREENSHOTS.md)**  
> **Companion Industry Portfolios:** [`Banking_Agents`](https://github.com/zurupream/Banking_Agents) · [`Insurance_Agents`](https://github.com/zurupream/Insurance_Agents) · [`Retail_Distribution_Manufacturing_Agents`](https://github.com/zurupream/Retail_Distribution_Manufacturing_Agents)

A portfolio of **9 Live Enterprise Human Resources (HR) & People Operations AI Agents** (`#01`–`#09`) built for **Chief Human Resources Officers (CHROs), Heads of Talent Acquisition, HR Operations Teams, Payroll Leaders, and Employees**. Every live application is built around five core rules:

1. **One Focused Job Per Agent** — Each agent solves one high-impact HR workflow exceptionally well without mixing unrelated tasks.
2. **Apple Design Principles & Business Simplicity** — Clean `#F5F5F7` canvas, high-contrast `#FFFFFF` cards, `#0071E3` primary actions, SF Pro typography, and plain business HR English with zero technical jargon.
3. **Sign-In Page with High-Level Workflow Diagram + Single Sign-On (SSO)** — Every agent opens with a split-screen executive sign-in page illustrating its 3-step visual workflow diagram alongside Google Single Sign-On (SSO), Work Email verification code, and a 1-click Demo Sign-In button.
4. **Deterministic Python Math + Focused AI Reasoning** — Daily clock-in/clock-out hours, leave balances, payroll statutory deductions (PAYE, NSSF, SHIF/NHIF, Housing Levy), certificate expiry countdowns, and final settlement figures are calculated 100% deterministically in Python, while AI handles resume reading, handbook answers, and plain-English summaries.
5. **100% Human-in-the-Loop (HITL) Control & "Agent" Naming** — Every application uses the explicit **Agent** naming standard (never "Copilot"), keeping HR leaders in full control of every final decision.

---

## 1. Live HR AI Agents (#01–#09)

| # | HR Agent | Capabilities & HR Workflow | Business Value for HR & People Teams | Live Demonstrable Link | GitHub Repository |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **01** | **Candidates Screening Agent (`HR_CandidatesScreening`)** | Generates a weighted evaluation rubric from a Job Description, reads bulk candidate CVs (PDF and Word), checks mandatory knockout criteria, scores each applicant objectively, and exports a ranked Excel shortlist (`screening_results.xlsx`). | Cuts first-round CV screening time by **85%+** and evaluates every applicant against the same transparent standard. | [Launch App](https://candidates-screening-agent-259388273008.us-central1.run.app/)<br>[E2E Screenshots](./E2E_SSO_SCREENSHOTS.md#agent-01-candidates-screening-agent-hr_candidatesscreening) | [Candidates-Screening](https://github.com/zurupream/Candidates-Screening)<br>([Monorepo Folder](https://github.com/zurupream/HR_Agents/tree/main/HR_CandidatesScreening)) |
| **02** | **Interview Scheduler Agent (`HR_InterviewScheduler`)** | Coordinates multi-stage interview panels (`Screening → Technical → Final`) by checking real-time interviewer availability on Google Calendar, emailing conflict-free time-slot options to candidates via Gmail, and booking Google Meet invitations automatically. | Eliminates **5–10 back-and-forth scheduling emails per candidate** and prevents double-booked interview panels. | [Launch App](https://interview-scheduler-259388273008.us-central1.run.app/)<br>[E2E Screenshots](./E2E_SSO_SCREENSHOTS.md#agent-02-interview-scheduler-agent-hr_interviewscheduler) | [interview-scheduler](https://github.com/zurupream/interview-scheduler)<br>([Monorepo Folder](https://github.com/zurupream/HR_Agents/tree/main/HR_InterviewScheduler)) |
| **03** | **HR Onboarding Pro Agent (`HR_OnboardingPro`)** | Automates the post-offer onboarding journey: generates Offer Letter PDFs, captures online candidate e-signatures (`/sign/{token}`), and coordinates 4 role-based setup agents in sequence: `1. IT Email Setup` → `2. Laptop Request` → `3. Uber Commute Pass` → `4. Health Insurance`. | Prevents pre-Day-One candidate drop-off and ensures every new hire (`Employee`, `Trainee`, or `Intern`) has their email, laptop, transport pass, and medical cover ready on Day 1. | [Launch App](https://hr-onboarding-259388273008.us-central1.run.app/)<br>[E2E Screenshots](./E2E_SSO_SCREENSHOTS.md#agent-03-hr-onboarding-pro-agent-hr_onboardingpro) | [hr_onboarding](https://github.com/zurupream/hr_onboarding)<br>([Monorepo Folder](https://github.com/zurupream/HR_Agents/tree/main/HR_OnboardingPro)) |
| **04** | **HR Offboarding Pro Agent (`HR_OffboardingPro`)** | Executes the **exact reverse steps of Onboarding**: logs the exit notice, runs reverse clearance agents (`1. Health Insurance Cancellation` → `2. Uber Pass Revocation` → `3. Laptop Return & Inspection` → `4. IT Email & SSO Deactivation`), calculates Final Dues, captures employee clearance e-signature (`/sign/{token}`), and issues the Certificate of Service PDF. | Closes security gaps from active accounts after exit, ensures company laptops are returned before final payout, and produces instant Final Settlement and Certificate of Service PDFs. | [Launch App](https://hr-offboarding-pro-259388273008.us-central1.run.app/)<br>[E2E Screenshots](./E2E_SSO_SCREENSHOTS.md#agent-04-hr-offboarding-pro-agent-hr_offboardingpro--exact-reverse-of-onboarding) | [HR_OffboardingPro](https://github.com/zurupream/HR_OffboardingPro)<br>([Monorepo Folder](https://github.com/zurupream/HR_Agents/tree/main/HR_OffboardingPro)) |
| **05** | **Payroll Variance, Statutory Compliance & Payslip Recon Agent (`HR_PayrollReconAgent`)** | Compares current-month draft payroll against last month's payroll and HR master records; flags headcount changes, unexplained salary jumps, unauthorized bank-account changes, and exited employees still on draft payroll; verifies statutory deductions (PAYE, NSSF, SHIF, Housing Levy); and prints a **1-Page CFO/CHRO Payroll Sign-Off Sheet**. | Catches payroll calculation errors, ghost-worker payouts, and unauthorized bank account changes **before** salaries are disbursed. | [Launch App](https://hr-payroll-recon-agent-259388273008.us-central1.run.app/)<br>[E2E Screenshots](./E2E_SSO_SCREENSHOTS.md#agent-05-payroll-variance-statutory-compliance--payslip-recon-agent-hr_payrollreconagent) | [HR_PayrollReconAgent](https://github.com/zurupream/HR_PayrollReconAgent)<br>([Monorepo Folder](https://github.com/zurupream/HR_Agents/tree/main/HR_PayrollReconAgent)) |
| **06** | **Attendance Clock-In/Out & Leave Notification Agent (`HR_AttendanceLeaveAgent`)** | Checks attendance system clock-in and clock-out times against required daily shift hours (`8.0h`) and approved leave applications; flags every employee who missed hours or was absent with no approved leave; and sends one-click notifications to HR and the employee. | Gives HR an instant daily exception list of employees with missing hours or unapproved absences without manually cross-checking clock-in logs against leave spreadsheets. | [Launch App](https://hr-attendance-leave-agent-259388273008.us-central1.run.app/)<br>[E2E Screenshots](./E2E_SSO_SCREENSHOTS.md#agent-06-attendance-clock-inout--leave-notification-agent-hr_attendanceleaveagent) | [HR_AttendanceLeaveAgent](https://github.com/zurupream/HR_AttendanceLeaveAgent)<br>([Monorepo Folder](https://github.com/zurupream/HR_Agents/tree/main/HR_AttendanceLeaveAgent)) |
| **07** | **Employee HR Helpdesk Agent (`HR_HelpdeskAgent`)** | A simple, focused employee self-service HR Helpdesk Agent that answers everyday staff questions (annual/sick/parental leave rules, medical & dental cover benefits, payroll dates, expense claims, working hours) using the official Employee Handbook and creates a tracked HR support ticket (`HR-2026-XXXX`) when human follow-up is needed. | Resolves **70%+ of routine employee HR questions** immediately in plain English so HR teams can focus on high-priority people matters. | [Launch App](https://hr-helpdesk-agent-259388273008.us-central1.run.app/)<br>[E2E Screenshots](./E2E_SSO_SCREENSHOTS.md#agent-07-employee-hr-helpdesk-agent-hr_helpdeskagent) | [HR_HelpdeskAgent](https://github.com/zurupream/HR_HelpdeskAgent)<br>([Monorepo Folder](https://github.com/zurupream/HR_Agents/tree/main/HR_HelpdeskAgent)) |
| **08** | **Learning, Certification Expiry & Skills Matrix Agent (`HR_SkillsComplianceAgent`)** | Tracks mandatory professional licenses, safety certifications, regulatory training hours, and staff training bonds across departments; alerts HR and line managers 30, 60, and 90 days before any employee certificate expires; and generates a **1-Page Certification Compliance Audit Report**. | Prevents regulatory compliance breaches from expired staff licenses and gives HR a clear view of role-required certifications across every department. | [Launch App](https://hr-skills-compliance-agent-259388273008.us-central1.run.app/)<br>[E2E Screenshots](./E2E_SSO_SCREENSHOTS.md#agent-08-learning-certification-expiry--skills-matrix-agent-hr_skillscomplianceagent) | [HR_SkillsComplianceAgent](https://github.com/zurupream/HR_SkillsComplianceAgent)<br>([Monorepo Folder](https://github.com/zurupream/HR_Agents/tree/main/HR_SkillsComplianceAgent)) |
| **09** | **Executive "Talk-to-Your-Workforce" & Attrition Stress-Test Agent (`HR_WorkforceAnalyticsAgent`)** | Plain-English workforce analytics workspace for the CHRO, CEO, and CFO covering active headcount (`480`), department turnover (`13.8%`), hiring speed (`32 Days`), and interactive sliders to test the budget impact of annual salary increments, turnover changes, and planned new hires. | Replaces static monthly HR spreadsheets with instant answers and live wage-bill scenario planning for boardroom reviews. | [Launch App](https://hr-workforce-analytics-agent-259388273008.us-central1.run.app/)<br>[E2E Screenshots](./E2E_SSO_SCREENSHOTS.md#agent-09-executive-talk-to-your-workforce--attrition-stress-test-agent-hr_workforceanalyticsagent) | [HR_WorkforceAnalyticsAgent](https://github.com/zurupream/HR_WorkforceAnalyticsAgent)<br>([Monorepo Folder](https://github.com/zurupream/HR_Agents/tree/main/HR_WorkforceAnalyticsAgent)) |

---

## 2. Which Agent to Demo by HR & Executive Role

Tailor your 3-minute live walkthrough to the role of the HR or business leader in front of you:

```mermaid
flowchart LR
    Visitor["HR / Business Executive"] --> TA["Head of Talent Acquisition & Recruitment"]
    Visitor --> HROps["Head of HR Operations & People Services"]
    Visitor --> Payroll["Head of Payroll & Finance"]
    Visitor -->LD["Head of Learning, Development & Compliance"]
    Visitor --> CHRO["CHRO / CEO / Chief People Officer"]

    TA --> TA_Demos["#01 Candidates Screening Agent<br/>#02 Interview Scheduler Agent<br/>#03 HR Onboarding Pro Agent"]
    HROps --> Ops_Demos["#03 HR Onboarding Pro Agent<br/>#04 HR Offboarding Pro Agent<br/>#06 Attendance Clock-In/Out & Leave Agent<br/>#07 Employee HR Helpdesk Agent"]
    Payroll --> Pay_Demos["#04 HR Offboarding Pro Agent (Final Dues)<br/>#05 Payroll Variance & Statutory Recon Agent<br/>#06 Attendance Clock-In/Out & Leave Agent"]
    LD --> LD_Demos["#08 Certification Expiry & Skills Matrix Agent<br/>#07 Employee HR Helpdesk Agent"]
    CHRO --> C_Demos["#09 Executive Talk-to-Your-Workforce Agent<br/>#05 Payroll Variance & Statutory Recon Agent<br/>#04 HR Offboarding Pro Agent"]
```

---

## 3. Connected Multi-Agent Spotlight: End-to-End Hire-to-Retire Pipeline (`#01` → `#02` → `#03` ↔ `#04`)

The first four agents connect seamlessly across the employee lifecycle—and **Agent `#04` (`HR_OffboardingPro`)** is engineered as the exact mirror-reverse of **Agent `#03` (`HR_OnboardingPro`)**:

```mermaid
flowchart LR
    classDef stage fill:#ffffff,stroke:#0071e3,color:#1d1d1f,font-weight:bold

    S1["#01 Candidates Screening Agent<br/>1. Build Rubric from Job Description<br/>2. Score Bulk Candidate CVs<br/>3. Export Ranked Shortlist (.xlsx)"]:::stage
    S2["#02 Interview Scheduler Agent<br/>1. Check Panel Google Calendar<br/>2. Email Conflict-Free Slots via Gmail<br/>3. Book Google Meet Invite"]:::stage
    S3["#03 HR Onboarding Pro Agent<br/>1. Offer Letter PDF & Online E-Sign<br/>2. Forward Setup: Email → Laptop → Uber → Insurance<br/>3. Day-One Readiness Complete"]:::stage
    S4["#04 HR Offboarding Pro Agent (Reverse Steps)<br/>1. Reverse Clearance: Insurance → Uber → Laptop → Email<br/>2. Final Dues & Clearance E-Sign<br/>3. Certificate of Service PDF"]:::stage

    S1 -->|"Shortlisted Candidates"| S2
    S2 -->|"Selected Hire"| S3
    S3 -->|"Active Employee Lifecycle"| S4
```

---

## 4. 90-Second Live Demo Scripts for All 9 HR Agents

### Demo Script #01: Candidates Screening Agent (`HR_CandidatesScreening`)
* **Live URL:** [https://candidates-screening-agent-259388273008.us-central1.run.app/](https://candidates-screening-agent-259388273008.us-central1.run.app/)
* **GitHub Repository:** [zurupream/Candidates-Screening](https://github.com/zurupream/Candidates-Screening) • [Monorepo Folder](https://github.com/zurupream/HR_Agents/tree/main/HR_CandidatesScreening)
* **E2E SSO Screenshots:** [View Sign-In & Workspace Screenshots](./E2E_SSO_SCREENSHOTS.md#agent-01-candidates-screening-agent-hr_candidatesscreening)
* **90-Second Flow:**
  1. **Sign In (15s):** Open the split-screen Sign-In page showing the 3-step CV screening workflow diagram and sign in via Google SSO or **Instant Demo SSO Sign-In**.
  2. **Build Weighted Rubric (30s):** Paste or upload a Job Description to generate a structured evaluation rubric with weighted skills and mandatory criteria.
  3. **Screen CVs & Export Ranked Shortlist (45s):** Upload a batch of PDF/Word resumes, inspect each candidate's score and plain-English summary, and download the ranked Excel shortlist (`screening_results.xlsx`).

### Demo Script #02: Interview Scheduler Agent (`HR_InterviewScheduler`)
* **Live URL:** [https://interview-scheduler-259388273008.us-central1.run.app/](https://interview-scheduler-259388273008.us-central1.run.app/)
* **GitHub Repository:** [zurupream/interview-scheduler](https://github.com/zurupream/interview-scheduler) • [Monorepo Folder](https://github.com/zurupream/HR_Agents/tree/main/HR_InterviewScheduler)
* **E2E SSO Screenshots:** [View Sign-In & Workspace Screenshots](./E2E_SSO_SCREENSHOTS.md#agent-02-interview-scheduler-agent-hr_interviewscheduler)
* **90-Second Flow:**
  1. **Sign In (15s):** Review the 3-step interview scheduling diagram on the Sign-In page and sign in via Google SSO or **Instant Demo SSO Sign-In**.
  2. **Check Panel Availability (30s):** Select a candidate and interview stage (`Screening`, `Technical`, or `Final`); the agent checks real-time free/busy windows across all panel members on Google Calendar.
  3. **Send Slots & Auto-Book Google Meet (45s):** Dispatch conflict-free slot options to the candidate via Gmail and watch the agent auto-book the Google Meet invitation upon confirmation.

### Demo Script #03: HR Onboarding Pro Agent (`HR_OnboardingPro`)
* **Live URL:** [https://hr-onboarding-259388273008.us-central1.run.app/](https://hr-onboarding-259388273008.us-central1.run.app/)
* **GitHub Repository:** [zurupream/hr_onboarding](https://github.com/zurupream/hr_onboarding) • [Monorepo Folder](https://github.com/zurupream/HR_Agents/tree/main/HR_OnboardingPro)
* **E2E SSO Screenshots:** [View Sign-In & Workspace Screenshots](./E2E_SSO_SCREENSHOTS.md#agent-03-hr-onboarding-pro-agent-hr_onboardingpro)
* **90-Second Flow:**
  1. **Sign In & Launch Offer (15s):** Sign in via SSO, select a candidate role (`Employee`, `Trainee`, or `Intern`), generate the branded Offer Letter PDF, and open the candidate e-signature portal (`/sign/{token}`).
  2. **Role-Based Setup Agents (30s):** Watch the 4 setup agents run in forward dependency order: `1. IT Email Setup Agent` → `2. Laptop Request Agent` → `3. Uber Commute Pass Agent` → `4. Health Insurance Agent`.
  3. **Day-One Readiness & Action Center (45s):** Track live milestone completion across departments and resolve any blocked item in one click.

### Demo Script #04: HR Offboarding Pro Agent (`HR_OffboardingPro`)
* **Live URL:** [https://hr-offboarding-pro-259388273008.us-central1.run.app/](https://hr-offboarding-pro-259388273008.us-central1.run.app/)
* **GitHub Repository:** [zurupream/HR_OffboardingPro](https://github.com/zurupream/HR_OffboardingPro) • [Monorepo Folder](https://github.com/zurupream/HR_Agents/tree/main/HR_OffboardingPro)
* **E2E SSO Screenshots:** [View Sign-In & Workspace Screenshots](./E2E_SSO_SCREENSHOTS.md#agent-04-hr-offboarding-pro-agent-hr_offboardingpro--exact-reverse-of-onboarding)
* **90-Second Flow:**
  1. **Sign In & Log Exit Notice (15s):** Sign in via SSO on the reverse-workflow login page and select an exiting employee (`Employee`, `Trainee`, or `Intern`).
  2. **Reverse Clearance Agents (30s):** Watch the 4 clearance agents execute in exact reverse order of Onboarding: `1. Health Insurance Cancellation Agent` → `2. Uber Pass Revocation Agent` → `3. Laptop Return Agent` → `4. IT Email Deactivation Agent` (keeping email active until laptop handover is verified).
  3. **Final Dues E-Sign & Certificate of Service (45s):** Open the Employee Clearance E-Sign Portal (`/sign/{token}`) to sign the Final Settlement Statement and download the **Final Settlement PDF** and **Certificate of Service PDF**.

### Demo Script #05: Payroll Variance, Statutory Compliance & Payslip Recon Agent (`HR_PayrollReconAgent`)
* **Live URL:** [https://hr-payroll-recon-agent-259388273008.us-central1.run.app/](https://hr-payroll-recon-agent-259388273008.us-central1.run.app/)
* **GitHub Repository:** [zurupream/HR_PayrollReconAgent](https://github.com/zurupream/HR_PayrollReconAgent) • [Monorepo Folder](https://github.com/zurupream/HR_Agents/tree/main/HR_PayrollReconAgent)
* **E2E SSO Screenshots:** [View Sign-In & Workspace Screenshots](./E2E_SSO_SCREENSHOTS.md#agent-05-payroll-variance-statutory-compliance--payslip-recon-agent-hr_payrollreconagent)
* **90-Second Flow:**
  1. **Sign In & Inspect Monthly Payroll Bridge (15s):** Sign in via SSO and review current-month draft gross and net payroll against prior month totals.
  2. **Audit Variances & Bank-Swap Alerts (30s):** Inspect employees flagged for unexplained basic pay jumps, unauthorized bank account changes, or ghost-worker risk (exited employee still on draft payroll), alongside deterministic statutory calculations (PAYE, NSSF, SHIF, Housing Levy).
  3. **Approve & Print CFO/CHRO Sign-Off Sheet (45s):** Approve reconciled records and open the printable **1-Page Payroll Reconciliation Sign-Off Certificate**.

### Demo Script #06: Attendance Clock-In/Out & Leave Notification Agent (`HR_AttendanceLeaveAgent`)
* **Live URL:** [https://hr-attendance-leave-agent-259388273008.us-central1.run.app/](https://hr-attendance-leave-agent-259388273008.us-central1.run.app/)
* **GitHub Repository:** [zurupream/HR_AttendanceLeaveAgent](https://github.com/zurupream/HR_AttendanceLeaveAgent) • [Monorepo Folder](https://github.com/zurupream/HR_Agents/tree/main/HR_AttendanceLeaveAgent)
* **E2E SSO Screenshots:** [View Sign-In & Workspace Screenshots](./E2E_SSO_SCREENSHOTS.md#agent-06-attendance-clock-inout--leave-notification-agent-hr_attendanceleaveagent)
* **90-Second Flow:**
  1. **Sign In & Check Daily Clock-In/Out Log (15s):** Sign in via SSO and view daily employee clock-in and clock-out times compared against required shift hours (`8.0h`) and approved leave records.
  2. **Filter Missed Hours with No Leave (30s):** Filter directly to employees marked **`Missed Hours — No Leave`** or **`Absent — No Leave`** to see the exact hours shortfall calculated deterministically.
  3. **Notify HR & Employee in One Click (45s):** Click **Notify HR & Employee** (or **Notify HR for All Flagged Employees**) to send the attendance alert to HR and export the **1-Page Daily Attendance & Missed-Hours Report**.

### Demo Script #07: Employee HR Helpdesk Agent (`HR_HelpdeskAgent`)
* **Live URL:** [https://hr-helpdesk-agent-259388273008.us-central1.run.app/](https://hr-helpdesk-agent-259388273008.us-central1.run.app/)
* **GitHub Repository:** [zurupream/HR_HelpdeskAgent](https://github.com/zurupream/HR_HelpdeskAgent) • [Monorepo Folder](https://github.com/zurupream/HR_Agents/tree/main/HR_HelpdeskAgent)
* **E2E SSO Screenshots:** [View Sign-In & Workspace Screenshots](./E2E_SSO_SCREENSHOTS.md#agent-07-employee-hr-helpdesk-agent-hr_helpdeskagent)
* **90-Second Flow:**
  1. **Sign In & Pick a Handbook Topic (15s):** Sign in via SSO and click one of the 6 Employee Handbook topic cards (Annual & Parental Leave, Medical & Dental Cover, Payroll & Payslip Dates, Transport & Expense Claims, Working Hours & Remote Work, Compassionate Leave).
  2. **Read Instant Handbook-Backed Answer (30s):** Ask a question in plain English and review the instant answer showing exact handbook section citations, key entitlement numbers, and step-by-step instructions.
  3. **Escalate to HR Team in One Click (45s):** Click **Send Request to HR Team** when personal action is needed (e.g., adding a newborn dependent to medical insurance) and track the request under **My HR Requests**.

### Demo Script #08: Learning, Certification Expiry & Skills Matrix Agent (`HR_SkillsComplianceAgent`)
* **Live URL:** [https://hr-skills-compliance-agent-259388273008.us-central1.run.app/](https://hr-skills-compliance-agent-259388273008.us-central1.run.app/)
* **GitHub Repository:** [zurupream/HR_SkillsComplianceAgent](https://github.com/zurupream/HR_SkillsComplianceAgent) • [Monorepo Folder](https://github.com/zurupream/HR_Agents/tree/main/HR_SkillsComplianceAgent)
* **E2E SSO Screenshots:** [View Sign-In & Workspace Screenshots](./E2E_SSO_SCREENSHOTS.md#agent-08-learning-certification-expiry--skills-matrix-agent-hr_skillscomplianceagent)
* **90-Second Flow:**
  1. **Sign In & View Expiry Tracker (15s):** Sign in via SSO and inspect staff professional licenses and mandatory certificates grouped into **Expired — Action Required**, **Expiring in 30 Days**, **Expiring in 60–90 Days**, and **Active & Valid**.
  2. **Send Renewal Notices & Inspect Skills Matrix (30s):** Click **Send Renewal Notice** (or bulk notify) to alert employees and line managers, and switch to the **Department Skills Matrix** tab to review role-required certification coverage.
  3. **Print Compliance Audit Report (45s):** Open the **Compliance Audit Report** tab to print the 1-Page HR Certification Compliance Summary.

### Demo Script #09: Executive "Talk-to-Your-Workforce" & Attrition Stress-Test Agent (`HR_WorkforceAnalyticsAgent`)
* **Live URL:** [https://hr-workforce-analytics-agent-259388273008.us-central1.run.app/](https://hr-workforce-analytics-agent-259388273008.us-central1.run.app/)
* **GitHub Repository:** [zurupream/HR_WorkforceAnalyticsAgent](https://github.com/zurupream/HR_WorkforceAnalyticsAgent) • [Monorepo Folder](https://github.com/zurupream/HR_Agents/tree/main/HR_WorkforceAnalyticsAgent)
* **E2E SSO Screenshots:** [View Sign-In & Workspace Screenshots](./E2E_SSO_SCREENSHOTS.md#agent-09-executive-talk-to-your-workforce--attrition-stress-test-agent-hr_workforceanalyticsagent)
* **90-Second Flow:**
  1. **Sign In & Inspect Workforce Snapshot (15s):** Sign in via SSO and review total active headcount (`480`), annual attrition (`13.8%`), regrettable departures (`24`), average time to hire (`32 Days`), and monthly payroll cost (`$3,040,000`).
  2. **Run Interactive Salary & Attrition Stress Tests (30s):** Adjust the **Annual Salary Increment (`%`)**, **Projected Turnover Rate (`%`)**, and **Planned New Hires** sliders to see deterministic impacts on annual payroll and replacement recruitment costs.
  3. **Ask the Workforce Agent & Print CHRO Summary (45s):** Ask a plain-English question in **Ask Workforce Agent** and print the **1-Page CHRO Boardroom Summary**.

---

## 5. Reference HR AI Architecture

```mermaid
flowchart TB
    subgraph Channels["HR Leader Workbenches & Employee Self-Serve Portals"]
        TA["Talent Acquisition Workbenches<br/>(#01 Candidates Screening, #02 Interview Scheduler)"]
        Lifecycle["Hire-to-Retire & E-Sign Portals<br/>(#03 HR Onboarding Pro ↔ #04 HR Offboarding Pro)"]
        Ops["Payroll, Attendance, Helpdesk, Compliance & CHRO Portals<br/>(#05 Payroll Recon, #06 Attendance & Leave, #07 Helpdesk, #08 Certifications, #09 Workforce Analytics)"]
    end

    subgraph Orchestration["Enterprise HR Agent Layer"]
        Router["Focused Single-Purpose HR Agents"]
        DocAgent["CV Screening & Handbook Grounding Agent<br/>(Objective Rubric Scoring & Cited Handbook Answers)"]
        FlowAgent["Provisioning & Reverse Clearance Agents<br/>(Email, Laptop, Uber Pass & Medical Cover Orchestration)"]
        QuantAgent["Deterministic Payroll, Attendance & Workforce Math<br/>(100% Python Tax, Hours Shortfall, Final Dues & Stress-Test Math)"]
    end

    subgraph Grounding["HR Data & Knowledge Sources"]
        Handbook["Official Employee Handbook & Statutory Rules<br/>(Leave Entitlements, Medical Cover, PAYE/NSSF/SHIF/Levy Formulas)"]
        CoreHR["HR Master, Attendance Logs & Certification Records<br/>(Employee Roster, Clock-In/Out Logs, Leave Applications, License Expiry Dates)"]
        Workspace["Google Workspace Integration<br/>(Google Calendar Free/Busy, Gmail Notifications, Google Meet Links)"]
    end

    subgraph Security["Enterprise Security & Governance"]
        Sec["Google Single Sign-On (SSO) • Role-Based Access • 100% Human-in-the-Loop Sign-Off • Complete Audit Trail"]
    end

    Channels --> Router
    Router --> DocAgent
    Router --> FlowAgent
    Router --> QuantAgent
    DocAgent --> Handbook
    QuantAgent --> CoreHR
    FlowAgent --> Workspace
    Orchestration --- Security
```

---

## 6. End-to-End SSO & Visual Verification Gallery (All 9 Agents)

All 22 high-resolution E2E screenshots (`1440×900`) are stored in [`./screenshots/`](./screenshots/) and documented in **[`E2E_SSO_SCREENSHOTS.md`](./E2E_SSO_SCREENSHOTS.md)**:

| # | HR Agent | Sign-In Page (3-Step Diagram + SSO) | Authenticated E2E Workspace |
| :--- | :--- | :--- | :--- |
| **#01** | **[Candidates Screening Agent](https://candidates-screening-agent-259388273008.us-central1.run.app/)** | ![#01 Sign-In](./screenshots/agent_01_candidates_screening_signin_sso.png) | ![#01 Workspace](./screenshots/agent_01_candidates_screening_workspace_e2e.png) |
| **#02** | **[Interview Scheduler Agent](https://interview-scheduler-259388273008.us-central1.run.app/)** | ![#02 Sign-In](./screenshots/agent_02_interview_scheduler_signin_sso.png) | ![#02 Workspace](./screenshots/agent_02_interview_scheduler_workspace_e2e.png) |
| **#03** | **[HR Onboarding Pro Agent](https://hr-onboarding-259388273008.us-central1.run.app/)** | ![#03 Sign-In](./screenshots/agent_03_hr_onboarding_signin_sso.png) | ![#03 Workspace](./screenshots/agent_03_hr_onboarding_workspace_e2e.png) |
| **#04** | **[HR Offboarding Pro Agent](https://hr-offboarding-pro-259388273008.us-central1.run.app/)** | ![#04 Sign-In](./screenshots/agent_04_hr_offboarding_signin_sso.png) | ![#04 Workspace](./screenshots/agent_04_hr_offboarding_workspace_e2e.png) |
| **#05** | **[Payroll Recon Agent](https://hr-payroll-recon-agent-259388273008.us-central1.run.app/)** | ![#05 Sign-In](./screenshots/agent_05_payroll_recon_signin_sso.png) | ![#05 Workspace](./screenshots/agent_05_payroll_recon_workspace_e2e.png) |
| **#06** | **[Attendance & Leave Agent](https://hr-attendance-leave-agent-259388273008.us-central1.run.app/)** | ![#06 Sign-In](./screenshots/agent_06_attendance_leave_signin_sso.png) | ![#06 Workspace](./screenshots/agent_06_attendance_leave_workspace_e2e.png) |
| **#07** | **[Employee HR Helpdesk Agent](https://hr-helpdesk-agent-259388273008.us-central1.run.app/)** | ![#07 Sign-In](./screenshots/agent_07_hr_helpdesk_signin_sso.png) | ![#07 Workspace](./screenshots/agent_07_hr_helpdesk_workspace_e2e.png) |
| **#08** | **[Skills & Certification Agent](https://hr-skills-compliance-agent-259388273008.us-central1.run.app/)** | ![#08 Sign-In](./screenshots/agent_08_skills_compliance_signin_sso.png) | ![#08 Workspace](./screenshots/agent_08_skills_compliance_workspace_e2e.png) |
| **#09** | **[Workforce Analytics Agent](https://hr-workforce-analytics-agent-259388273008.us-central1.run.app/)** | ![#09 Sign-In](./screenshots/agent_09_workforce_analytics_signin_sso.png) | ![#09 Workspace](./screenshots/agent_09_workforce_analytics_workspace_e2e.png) |
