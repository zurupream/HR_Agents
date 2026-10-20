# Agent #07: Employee HR Helpdesk Agent (`HR_HelpdeskAgent`)

A focused, friendly **Employee HR Helpdesk Agent** built to answer everyday employee questions using the official **Employee Handbook** and forward personal requests to the HR team in one click.

---

## 1. Focused Purpose (One Clear Idea)

Employees frequently have everyday HR questions—how many leave days they have, what their medical and dental limits are, when salaries are paid, or how to claim transport expenses.

The **Employee HR Helpdesk Agent** focuses 100% on solving this single workflow well:
1. **Employee Asks a Question:** Employees click one of 6 everyday HR category cards or type a question in plain English:
   - **Annual & Maternity/Paternity Leave** (`21 Working Days Annual`, `90 Calendar Days Maternity`, `14 Calendar Days Paternity`, `Max 5 Days Carry-Over`)
   - **Medical & Dental Insurance Cover** (`KES 2,500,000 Inpatient`, `KES 250,000 Outpatient`, `KES 50,000 Dental`, `KES 50,000 Optical`, `Spouse + Up to 4 Children`)
   - **Payroll Dates & Payslip Questions** (`Paid on the 25th of every month`, `15th Payroll Cut-Off`, `PAYE, NSSF, SHIF 2.75%, Housing Levy 1.5%`)
   - **Transport & Expense Claims** (`KES 65/km Mileage`, `Up to KES 2,500 Late-Work Taxi/Uber after 8:00 PM`, `Paid Every Friday`)
   - **Working Hours & Remote Work** (`8:30 AM – 5:00 PM Mon–Fri`, `Up to 2 Hybrid Remote Work Days/Week`)
   - **Public Holidays & Compassionate Leave** (`All Gazetted Public Holidays`, `5 Working Days Paid Compassionate Leave`, `5 Working Days Paid Study & Exam Leave`)
2. **HR Helpdesk Agent Checks Official Handbook:** Returns an immediate, crystal-clear answer in plain English showing the exact Employee Handbook section, key entitlement numbers at a glance, and simple steps to follow.
3. **Instant Resolution or HR Team Follow-Up:** If the employee needs personal human assistance (such as adding a newborn dependent to medical insurance or requesting a stamped payslip), clicking **"Send Request to HR Team"** creates a tracked HR Helpdesk Request (`HR-2026-XXXX`) with live status tracking (`Open`, `In Progress`, `Resolved`).

---

## 2. Sign-In Page & Single Sign-On (SSO)

When unauthenticated, the application presents an Apple-inspired Sign-In Page (`#F5F5F7` canvas, `#FFFFFF` cards, `#0071E3` buttons) featuring:
- **Left Panel:** High-level **3-Step Visual Workflow Diagram** (`Step 1: Employee Asks a Question` → `Step 2: HR Helpdesk Agent Checks Official Handbook` → `Step 3: Instant Resolution or HR Team Follow-Up`).
- **Right Panel:**
  - **Google Single Sign-On (SSO)** (`/api/auth/google`)
  - **Work Email 6-Digit Verification Code (OTP)** (`/api/auth/otp/request` and `/api/auth/otp/verify`)
  - **1-Click Instant Demo Sign-In (Employee / HR View)** (`/api/auth/demo`)

---

## 3. API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Service health check and seeded handbook/request counts |
| `POST` | `/api/auth/google` | Verify Google Single Sign-On ID token |
| `POST` | `/api/auth/otp/request` | Request a 6-digit verification code to a company work email |
| `POST` | `/api/auth/otp/verify` | Verify the 6-digit code and sign in |
| `POST` | `/api/auth/demo` | Instant 1-click demo sign-in (Employee / HR View) |
| `GET` | `/api/handbook` | List all 6 Employee Handbook categories, rules, and entitlement figures |
| `GET` | `/api/handbook/{category_id}` | Look up a single Employee Handbook category by ID |
| `POST` | `/api/helpdesk/ask` | Ask the Employee HR Helpdesk Agent any everyday HR question in plain English |
| `GET` | `/api/helpdesk/requests` | List all Employee HR Helpdesk Requests (`HR-2026-XXXX`) and summary metrics |
| `POST` | `/api/helpdesk/requests` | Create a new HR Helpdesk Request ("Send Request to HR Team") |
| `POST` | `/api/helpdesk/requests/{request_id}/resolve` | Resolve an HR Helpdesk Request with an HR team response note |

---

## 4. Running Locally & Testing

```bash
# Run pytest suite
pytest tests/ -v

# Start the FastAPI + React SPA server on port 8080
cd backend
uvicorn main:app --host 0.0.0.0 --port 8080
```
