# Agent #09: Executive "Talk-to-Your-Workforce" & Attrition Stress-Test Agent (`HR_WorkforceAnalyticsAgent`)

An Apple-inspired executive people analytics and wage-bill scenario planning workspace built for the **Chief Human Resources Officer (CHRO), Chief Executive Officer (CEO), and Chief Financial Officer (CFO)**.

---

## 1. Core Capabilities & Executive Workflow

1. **Step 1: Live Workforce & Turnover Overview**
   - Consolidates **Total Active Headcount (480)**, **Annual Attrition Rate % (13.8%)**, **Regrettable Departures (24)**, **Average Time to Hire (32 Days)**, and **Monthly Payroll Cost ($3,040,000)** in plain business English.
   - Displays the **Department Breakdown Table** across **Engineering**, **Sales & Commercial**, **Customer Operations**, **Finance & Admin**, and **People & Culture** with Headcount, Open Roles, Turnover %, Retention Status (`Action Needed`, `Watch Closely`, `Healthy`), and Monthly Cost.
2. **Step 2: Interactive Salary & Attrition Stress-Test**
   - Adjust **Annual Salary Increment %**, **Projected Turnover %**, and **Planned New Hires** sliders to calculate exact annual payroll impact, recruitment fees, and replacement hiring costs (`$19,000` per departure) deterministically in Python.
3. **Step 3: Ask the Workforce Agent & Board Summary**
   - Ask plain-English questions about department turnover, hiring velocity, or wage-bill scenarios using **Ask Workforce Agent** and print a 1-Page **CHRO Boardroom Summary**.

---

## 2. Single Sign-On (SSO) & Executive Authentication

- **Google Workspace Single Sign-On (`POST /api/auth/google`)**: Configured with `GOOGLE_CLIENT_ID = "259388273008-n8vg3ae8be86e56svvg09rbdciah17u1.apps.googleusercontent.com"`.
- **Work Email 6-Digit Verification Code (`POST /api/auth/otp/request` & `POST /api/auth/otp/verify`)**: Passwordless OTP verification blocking consumer/disposable domains.
- **Instant Demo Sign-In (`POST /api/auth/demo`)**: One-click **CHRO / Executive View** preview.

---

## 3. Running Locally & Running Tests

```bash
# Run pytest suite
cd backend
pytest -v

# Start FastAPI + compiled React SPA on port 8080
uvicorn main:app --host 0.0.0.0 --port 8080
```
