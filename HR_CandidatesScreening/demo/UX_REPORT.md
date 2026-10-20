# UX Polish, Role-Neutral Screening & Multi-Job Management Report (`T019`)

**Date (UTC):** 2026-10-14  
**Package:** `screening_agent/` & `screening_webapp/`  
**Overall Status:** **PASS (`26 passed`)**

---

## 1. What Changed (Plain-Language Summary)

### 1.1 Role-Neutral Screening (Works for Any Role)
- **Removed all software-engineering / tech bias**: All prompts (`screening_agent/prompts/rubric_prompt.md` and `screening_agent/prompts/screening_prompt.md`), fallback rubric/evaluation logic (`screening_agent/agent.py`), plain-language explanations (`screening_webapp/plain_language.py`), UI labels, and test fixtures are now completely role-neutral.
- **Role-neutral Sales Executive test fixture**: Created `screening_agent/tests/fixtures/create_dummy_data.py` (`build_dummy_dataset(base_dir)`), which builds a **Sales Executive - Retail and Business Clients** job description (`job_advert.docx`) and 4 candidate folders (`Dummy Candidate A` – `Dummy Candidate D`) inside pytest's temporary directory (`tmp_path`) during tests only.

### 1.2 Demo Data Cleanup & Freed Disk Space
- Deleted all persistent dummy/demo files on disk so the application starts with a clean slate:
  - `screening_agent/data/` (`192,704 bytes` / `248K` on disk)
  - `screening_agent/output/` (`25,202 bytes` / `40K` on disk)
  - `demo/dummy_data.zip` (`143,115 bytes` / `140K` on disk)
  - `demo/MANIFEST.txt` (`1,319 bytes` / `4.0K` on disk)
  - `screening_webapp/data/app.db` (`94,208 bytes` / `96K` on disk)
  - `screening_webapp/data/evaluations.json` (`11,378 bytes` / `12K` on disk)
  - `screening_webapp/data/screening_results.xlsx` (`12,444 bytes` / `16K` on disk)
  - `screening_agent/create_dummy_data.py` (moved to test fixture `screening_agent/tests/fixtures/create_dummy_data.py`)
- **Total Disk Space Freed:** **`480,370 bytes` (`556 KB` on disk)**.
- **Removed Demo UI Elements**:
  - Removed the yellow `"Demo data — not real candidates"` banner from the web app.
  - Removed the `"Sign in as Demo HR"` button from the sign-in screen.
  - Removed `hr.demo@example.com` from `screening_webapp/config/demo_allowed_emails.json` (leaving only the root admin `guruprem.saginadham@sybyl.com`).

### 1.3 Multi-Job Management (`1. Jobs` Tab)
- Added a `jobs` table in SQLite (`job_id`, `title`, `jd_filename`, `jd_path`, `applications_dir`, `threshold`, `requires_continuity`, `model`, `created_at_utc`, `created_by_email`) and linked `runs`, `candidate_results`, and `hr_decisions` to `job_id`.
- Every new job automatically receives a unique human-readable Job ID (`JOB-2026-001`, `JOB-2026-002`, ...).
- HR can upload a Job Description file (`.docx`, `.pdf`, `.txt`) and upload a folder of candidate CVs directly from the browser (`webkitdirectory`) or specify an existing server folder inside `/home/ubuntu/candidates_screening`. Uploaded files are stored cleanly under `screening_webapp/data/jobs/<job_id>/jd/` and `screening_webapp/data/jobs/<job_id>/applications/<Candidate Folder>/`.
- Added per-job API endpoints:
  - `POST /api/jobs` & `GET /api/jobs` & `GET /api/jobs/{job_id}`
  - `GET /api/jobs/{job_id}/folders` & `GET /api/jobs/{job_id}/folders/{candidate_id}/preview`
  - `POST /api/jobs/{job_id}/runs`
  - `GET /api/jobs/{job_id}/results`
  - `POST /api/jobs/{job_id}/candidates/{candidate_id}/decision`
  - `GET /api/jobs/{job_id}/export.xlsx` (downloads `screening_results_<JOB-ID>.xlsx`)

### 1.4 UX Polish for 100+ Candidates (`2. Candidates` & `3. Results` Tabs)
- **Clean Candidate Folder List (`2. Candidates`)**: Replaced noisy per-file `(.docx) OK` rows with a single clean badge (`"3 documents"`, `"All readable"` or `"1 unreadable"`) and a **"View"** button that opens a clean modal preview.
- **Job Search & Selector (`3. Results`)**: Added a Job ID / Title search filter and selector dropdown (`JOB-2026-001 — Sales Executive`) at the top of the Results tab, plus a job info bar showing the JD filename, candidate count, threshold, model, and last run status.
- **Filter, Search, Sort & Pagination**:
  - `"Needs your review only"` checkbox filter.
  - Candidate search box (`Search candidate by name or ID...`).
  - Sort dropdown (`Needs review first, then score`, `Score (high to low)`, `Score (low to high)`, `Name (A to Z)`, `Status`).
  - Client-side pagination (`25` candidates per page with `Previous` / `Next` controls and `"Showing 1–25 of N candidates"`).
- **Compact Results Table**: Clamped the `"Why"` column to 2 lines with an inline `"Read more"` / `"Show less"` toggle so rows remain compact and scannable.

---

## 2. How to Create a Job and Run Screening

1. Start the web app on localhost (`./screening_agent/.venv/bin/python -m screening_webapp` or `./screening_webapp/run_demo.sh`) and sign in at **`http://127.0.0.1:8080`** with an authorised Google account.
2. In the **`1. Jobs`** tab (left form **Create a New Job**):
   - Enter the **Job Title** (for example, `Sales Executive` or `Customer Support Lead`).
   - Select the **Job Description File** (`.docx`, `.pdf`, or `.txt`).
   - Choose the **Candidate Applications Folder** from your computer (browser folder picker) or enter a project-relative server folder path.
   - *(Optional)* Adjust the **Shortlist Threshold** (`0–100`, default `70`), **Work History Continuity** toggle, and **AI Model**.
   - Click **Create Job**. The job is assigned a unique ID (such as `JOB-2026-001`) and appears in the **All Jobs** table.
3. Click **Screen this job** next to the job (or select the job and click **Screen Candidates** in the top bar).
4. When screening finishes, the **`3. Results`** tab opens automatically for that job:
   - Review candidates flagged **Needs your review** at the top (or toggle **Needs your review only**).
   - Record **Shortlist** or **Do Not Shortlist** decisions (stored per `(job_id, candidate_id)` so decisions for one job never affect another job).
   - Click **Download Excel (.xlsx)** to download `screening_results_<JOB-ID>.xlsx`.

---

## 3. Verification Metrics

- **Disk Space Freed from Demo Data Deletion:** `480,370 bytes` (`556 KB` on disk)
- **`grep` Count for Old Tech Strings Across Project:** `0` matches
  ```bash
  grep -rnE "Senior Python|Python Software Engineering|Google ADK & LLMs|REST APIs & Google OAuth Security|Document & Spreadsheet Processing|Cloud Deployment & CI/CD|Adobe Illustrator|InDesign|FastAPI and OAuth" \
    --exclude-dir=.venv --exclude-dir=.git --exclude-dir=__pycache__ --exclude-dir=.pytest_cache --exclude="T019_ux_and_jobs.md" .
  # Output: 0 matches
  ```
- **Automated Test Suite (`pytest`):** **`26 passed in 2.67s`**
  - `screening_agent/tests/test_adk_web_entry.py`: `4 passed`
  - `screening_agent/tests/test_human_in_loop.py`: `7 passed`
  - `screening_webapp/tests/test_webapp.py`: `15 passed` (including `test_t019_create_jobs_run_filter_decisions_and_export` verifying multi-job creation `JOB-2026-001` & `JOB-2026-002`, per-job screening, `review_only=true` filtering, per-job HR decision isolation, and per-job `.xlsx` export)
