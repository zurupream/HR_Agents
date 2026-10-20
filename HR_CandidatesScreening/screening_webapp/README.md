# Candidate Screening HR Web Application (`screening_webapp`)

A local web application for HR to browse candidate folders and CVs, adjust screening settings, run the AI screening pipeline, review plain-language explanations and quotes, and record or override hiring decisions with full SQLite audit history and Excel export.

---

## Key Features

- **Google Sign-In & Database Access Portal**: Protected by Google Identity Services (OAuth 2.0 ID token verification), root admin bootstrap (`config/root_admins.json`), and SQLite database access tables (`allowed_users` and `allowed_domains`) managed live through the **5. Access** tab.
- **Multi-Job Management (`1. Jobs`)**: Create multiple screening jobs (`JOB-2026-001`, `JOB-2026-002`, ...), upload a Job Description (`.docx`, `.pdf`, `.txt`) and a CV folder directly from the browser (or select an existing server folder), and configure per-job threshold, continuity, and model settings.
- **Clean Candidate Folder Browser (`2. Candidates`)**: Inspect candidate folders for the selected job with a clean document count badge (e.g. `3 documents`) and a modal **View** preview.
- **Role-Neutral Plain-Language Results (`3. Results`)**: Search or select any Job by Job ID or Title, filter by **Needs your review only**, search candidates by name or ID, sort by Review/Score/Name/Status, paginate (25 per page), expand 2-line clamped reasons with `Read more`, inspect criterion scores and CV quotes, record `Shortlist` / `Do Not Shortlist` decisions per `(job_id, candidate_id)`, and export per-job Excel workbooks (`screening_results_<JOB-ID>.xlsx`).
- **SQLite Persistence & Audit History (`4. History`)**: Every job, run, candidate result, HR decision, access change, and audit event is stored in `screening_webapp/data/app.db` (`SQLite` by default, or configurable via `DATABASE_URL`).

---

## 1. Installation

From the project root (`/home/ubuntu/candidates_screening`), install the dependencies into the virtual environment:

```bash
./screening_agent/.venv/bin/pip install -r screening_webapp/requirements.txt
```

---

## 2. Managing Access (Root Admin & Database Allow-List)

Access is managed directly in the web app database (`allowed_users` and `allowed_domains` tables in `screening_webapp/data/app.db`) through the **5. Access** tab (visible to admins only):

1. **Root Admin Bootstrap**: `screening_webapp/config/root_admins.json` defines the bootstrap root admin (`guruprem.saginadham@sybyl.com`). Root admins can always sign in, cannot be removed or deactivated from the UI, and can add or remove other admins, HR users, and organisation domains.
2. **One-Time Migration**: On first start, the app imports existing emails from `screening_webapp/config/demo_allowed_emails.json`, `screening_webapp/config/allowed_emails.json`, and `root_admins.json` (`guruprem.saginadham@sybyl.com` as `admin`) into `allowed_users` once and logs `migrate_allowlist` in `audit_log`.
3. **Documented Fallback for Automated Tests**: The legacy JSON files (`allowed_emails.json` and `demo_allowed_emails.json`) are kept as a documented fallback when `ALLOWED_EMAILS_FILE` or `ALLOWED_EMAILS` is explicitly set in the test environment.
4. **Detailed Admin Guide**: See `demo/ADMIN_REPORT.md` and `demo/UX_REPORT.md` for step-by-step instructions.


---

## 3. Configure Google Cloud Credentials (Path Only)

To run live Gemini models on Vertex AI, set the path to your local Google Cloud service account key file (never paste secret file contents into code or configuration files):

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/service-account-key.json"
export GOOGLE_GENAI_USE_VERTEXAI="TRUE"
export GOOGLE_CLOUD_PROJECT="your-gcp-project-id"
export GOOGLE_CLOUD_LOCATION="us-central1"
```

*(Optional)* To override the database location (for example, to point to Cloud SQL / PostgreSQL later), set `DATABASE_URL`:

```bash
export DATABASE_URL="sqlite:////home/ubuntu/candidates_screening/screening_webapp/data/app.db"
```

---

## 4. Starting the App on Localhost (`127.0.0.1:8080`)

### Option A: One-Command Startup (Linux / macOS)

Starts the server bound strictly to `127.0.0.1:8080`:

```bash
./screening_webapp/run_demo.sh
```

### Option B: Windows (PowerShell) Startup

On Windows PowerShell (from the repository root):

```powershell
$env:DEMO_TEST_AUTH="1"; $env:ALLOWED_EMAILS_FILE="screening_webapp\config\demo_allowed_emails.json"; python -m screening_webapp
```

### Option C: Standard Python Module Start

Starts the server on `127.0.0.1:8080`:

```bash
./screening_agent/.venv/bin/python -m screening_webapp
```

---

## 5. Using the Web App in Your Browser

1. Open **`http://127.0.0.1:8080`** in your browser on the same machine (or via SSH local port forwarding `ssh -L 8080:127.0.0.1:8080 ...`).
2. Sign in with your authorised Google account.
3. **1. Jobs Tab**: Create a new job by entering a Job Title (e.g. `Sales Executive`), uploading the Job Description file (`.docx`, `.pdf`, `.txt`), and choosing the folder of candidate CVs (or selecting an existing server folder). Each job receives a unique Job ID (`JOB-2026-001`, `JOB-2026-002`, ...). Click **Screen this job** on any job row to run AI screening, or **Open results** to view its results.
4. **2. Candidates Tab**: Inspect the candidate folders for the selected job (`3 documents`, `All readable`) and click **View** to open a clean modal preview of extracted CV and cover letter text.
5. **3. Results Tab**:
   - Select or search any job by Job ID or Title (`JOB-2026-001 — Sales Executive`).
   - Review the summary cards (`Total Screened`, `Shortlisted`, `Needs Your Review`, `Not Shortlisted`).
   - Use the **Needs your review only** toggle, candidate search box, sort dropdown, and 25-per-page pagination controls to navigate large candidate pools.
   - Click **Read more** on any truncated reason or **Show evidence & quotes** to view criterion-by-criterion scores (`0–5`) and direct quotes from the CV.
   - Enter an optional note and click **Shortlist** or **Do Not Shortlist** to record your decision for that job.
   - Click **Download Excel (.xlsx)** to download `screening_results_<JOB-ID>.xlsx`.
6. **4. History Tab**: View past screening runs (including their `Job ID`), the chronological audit trail of HR decisions, and recent system actions.
7. **5. Access Tab (Admins Only)**: Manage authorised users (`admin` / `hr`) and organisation domain rules.
