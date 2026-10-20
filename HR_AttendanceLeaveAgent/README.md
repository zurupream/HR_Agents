# Agent #06: Attendance Clock-In/Out & Leave Notification Agent (`HR_AttendanceLeaveAgent`)

**Enterprise HR & People Operations Portfolio — Agent #06**

The **Attendance Clock-In/Out & Leave Notification Agent** checks daily employee clock-in and clock-out times against required daily shift hours (**8.0 hours**), cross-checks approved leave applications, flags every employee who missed hours or was absent with no approved leave, and dispatches one-click notifications to HR Operations and the employee.

---

## 3-Step Autonomous HR Workflow

1. **Step 1: Daily Clock-In & Clock-Out Log**
   - Reads each employee's daily clock-in and clock-out times against the required daily shift hours (`8.0 hours`).
2. **Step 2: Cross-Check Approved Leave Applications**
   - Matches missing hours or full-day absences against approved leave records (`Approved Annual Leave`, `Approved Sick Leave`, `Approved Half-Day Leave`) vs. unapproved statuses (`None`, `Pending`).
3. **Step 3: Notify HR for Missed Hours with No Leave**
   - Flags each employee with `Missed Hours — No Leave` or `Absent — No Leave` and dispatches one-click or bulk notifications to HR Operations, the employee, and their line manager.

---

## Key Capabilities for HR Operations Teams

- **Apple-Inspired Executive Sign-In Page with 3-Step Visual Workflow Diagram + Single Sign-On (SSO)**:
  - Supports **Google Single Sign-On (SSO)** (`/api/auth/google`), **Work Email 6-Digit Verification Code** (`/api/auth/otp/request` & `/api/auth/otp/verify`), and a 1-click **Instant Demo Sign-In (HR Operations Manager)** button.
- **5 Executive Summary Cards**:
  - Total Employees Checked
  - Full Hours Completed (`On Time / Full Hours`)
  - Covered by Approved Leave (`Approved Leave`)
  - **Missed Hours / Absent with No Leave (HR Action Required)**
  - HR Notifications Sent
- **Interactive Clock-In, Clock-Out & Leave Status Tester**:
  - Edit Clock-In, Clock-Out, or Leave Application Status for any employee and immediately inspect the deterministic hours shortfall calculation and notification preview.
- **1-Click Single & Bulk HR Notifications**:
  - Send individual **Notify HR & Employee** notices or click **Notify HR for All Flagged Employees** to notify HR Operations for every employee with missed hours and no approved leave.
- **Ask Attendance Agent & Printable 1-Page HR Report**:
  - Ask plain-English questions via **Ask Attendance Agent** and print a clean **1-Page Daily Attendance & Missed-Hours HR Report**.

---

## Running Locally

```bash
cd backend
pip install -r requirements.txt
pytest -v
uvicorn main:app --host 0.0.0.0 --port 8080
```
