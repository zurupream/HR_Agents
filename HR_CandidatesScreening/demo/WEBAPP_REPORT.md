# HR Candidate Screening Web Application — Build & Verification Report (`T016`)

**Date (UTC):** 2026-10-14  
**Package:** `screening_webapp/`  
**Default Bind Address:** `http://127.0.0.1:8080` (localhost only)  
**Database:** `screening_webapp/data/app.db` (`SQLite` via SQLAlchemy; configurable via `DATABASE_URL`)  
**OAuth Client ID:** `259388273008-n8vg3ae8be86e56svvg09rbdciah17u1.apps.googleusercontent.com`

---

## 1. What Was Built

We built a self-contained HR Web Application in `screening_webapp/` on top of the existing `screening_agent/` package (without modifying `screening_agent/` or breaking any of its existing tests).

### 1.1 Architecture & Components
1. **Authentication & Email Allow-List (`screening_webapp/auth.py`, `screening_webapp/config/`)**
   - Uses Google Identity Services (GIS) in the browser to obtain a Google ID token and sends `Authorization: Bearer <id_token>` on all `/api/*` requests.
   - Verifies token signature, expiry, issuer, and audience against Client ID `259388273008-n8vg3ae8be86e56svvg09rbdciah17u1.apps.googleusercontent.com` using `google.oauth2.id_token`.
   - Enforces an email allow-list loaded from `screening_webapp/config/allowed_emails.json` (or `ALLOWED_EMAILS` env var). The default `allowed_emails.json` is empty (`[]`), returning `403 Forbidden` until HR adds authorised emails.
   - Supports a local demo sign-in mode (`DEMO_TEST_AUTH=1` with `screening_webapp/config/demo_allowed_emails.json`) for automated E2E tests and offline local demos.

2. **SQLite Database via SQLAlchemy (`screening_webapp/database.py`)**
   - Connects via `DATABASE_URL` (defaults to `sqlite:////home/ubuntu/candidates_screening/screening_webapp/data/app.db`), ready to swap to Cloud SQL (`postgresql+psycopg2://...`) later without code changes.
   - Automatically creates the 4 required tables on startup:
     - `runs`: `(id, started_at, finished_at, status, settings_json, model, threshold, candidate_count, error)`
     - `candidate_results`: `(run_id, candidate_id, name, ai_decision, ai_score, confidence, status, review_reasons_json, evidence_json)`
     - `hr_decisions`: `(id, candidate_id, run_id, decision, note, decided_by_email, decided_at_utc)`
     - `audit_log`: `(id, at_utc, actor_email, action, detail)`

3. **Plain-Language Mapper (`screening_webapp/plain_language.py`)**
   - Translates all internal uncertainty codes into plain English for HR:
     - `borderline_score` -> *"Borderline: score is 64 out of 100, 6 points below the threshold of 70."*
     - `missing_evidence` -> *"Missing evidence: no clear proof found in the CV for a required skill (...)."*
     - `conflicting_evidence` -> *"Conflicting information: dates or claims in the application do not match across documents."*
     - `unreadable_document` -> *"Unreadable file: one of the candidate's files could not be opened or was empty."*
     - `low_confidence` -> *"Low AI confidence: the application is unusual or ambiguous; please review manually."*
   - Maps internal statuses to friendly badges:
     - `Needs HR review` -> **Needs your review** (amber)
     - `AI decided` -> **AI decided** (blue/green)
     - `HR decided` -> **You decided** (purple)

4. **FastAPI Backend (`screening_webapp/app.py`, `screening_webapp/main.py`, `screening_webapp/__main__.py`)**
   - `GET /health` & `GET /`: Health check and single-page HR interface.
   - `GET /api/me`: Returns the signed-in user's verified email, name, and active OAuth Client ID.
   - `GET /api/folders` & `GET /api/folders/{candidate_id}/preview`: Lists candidate folders, file sizes, and parse statuses (`OK` / `Unreadable`), and previews up to 1,500 characters per document via `screening_agent.tools.read_application`.
   - `GET /api/settings` & `PUT /api/settings`: Manages shortlist threshold (`0–100`), continuity requirement (`true`/`false`), model allow-list (`gemini-4-argon`, `gemini-2.5-pro`, `gemini-2.5-flash`), and application folder path (strictly validated to stay inside `/home/ubuntu/candidates_screening`). Rejects any attempt to disable `redact_before_scoring`.
   - `POST /api/runs` & `GET /api/runs/{run_id}`: Runs `screening_agent.agent.run_screening_pipeline` in a background worker thread, tracks live per-candidate progress (`Screening candidate 2 of 4...`), prevents concurrent runs with `409 Conflict`, and stores all results in SQLite.
   - `GET /api/runs/latest/results`: Returns the latest run's results sorted with **Needs your review** first, then by score descending, with plain-language reasons, expandable criterion scores and CV quotes, and the latest HR decision per candidate.
   - `POST /api/candidates/{candidate_id}/decision`: Appends a new row to `hr_decisions` and `audit_log` (preserving full decision history while the latest decision wins), calls `record_hr_decision`, and regenerates the 3-sheet Excel workbook (`Results`, `Review Queue`, `Metadata`).
   - `GET /api/export.xlsx`: Streams the latest `.xlsx` workbook to the browser.
   - `GET /api/history`: Returns past runs, all HR decision records, and recent audit log entries.

5. **Single-Page HR Frontend (`screening_webapp/static/index.html`, `styles.css`, `app.js`)**
   - Clean, responsive layout (`1280px` desktop friendly) with automatic light/dark mode support (`prefers-color-scheme`), clear status badges, a permanent `"Demo data - not real candidates"` notice, a left Settings panel, and three main tabs (**Candidates**, **Results**, **History**).

---

## 2. How to Run

### One-Command Demo Startup (`127.0.0.1:8080`)
```bash
cd /home/ubuntu/candidates_screening
./screening_webapp/run_demo.sh
```

### Standard Module Startup (`127.0.0.1:8080`)
```bash
cd /home/ubuntu/candidates_screening
./screening_agent/.venv/bin/python -m screening_webapp
```

See [`screening_webapp/README.md`](../screening_webapp/README.md) for instructions on configuring `screening_webapp/config/allowed_emails.json` and setting the `GOOGLE_APPLICATION_CREDENTIALS` file path.

---

## 3. What Was Verified

### 3.1 Automated Pytest Suites (`19 passed`)
Executed `./screening_agent/.venv/bin/pytest screening_agent/tests screening_webapp/tests -v`:
- **`screening_agent/tests/` (`11 passed`)**:
  - `test_adk_web_entry.py` (4 passed)
  - `test_human_in_loop.py` (7 passed)
- **`screening_webapp/tests/test_webapp.py` (`8 passed` covering all 6 required test areas)**:
  1. **Auth (`4 tests`)**: No token -> `401`; invalid token -> `401`; empty allow-list -> `403`; valid token for allowed email -> `200` and non-allowed email -> `403`.
  2. **Plain-language reasons (`1 test`)**: Verified exact wording `"Borderline: score is 64 out of 100, 6 points below the threshold of 70."` and verified that all 5 internal codes (`borderline_score`, `missing_evidence`, `conflicting_evidence`, `unreadable_document`, `low_confidence`) map to readable English sentences with no raw `snake_case` codes.
  3. **Settings validation (`1 test`)**: Model outside allow-list rejected (`400`); `applications_dir` outside project (`/etc`, `../../outside_project`) rejected (`400`); `redact_before_scoring: false` rejected (`400`); valid settings persisted (`200`).
  4. **Runs & Concurrency (`1 test`)**: Starting a run returns `run_id`; starting a second run while one is active returns `409 Conflict`; completed run populates `runs` and `candidate_results` in SQLite.
  5. **Decisions & End-to-End Demo Flow (`1 test`)**: Sign in -> list 4 candidate folders & preview extracted text (`<= 1500` chars) -> run screening -> verify `C004` is sorted first with `Needs your review` badge and plain-language reasons -> post two consecutive HR decisions on `C004` (`Not Shortlisted` then `Shortlisted`) -> verify latest decision wins in `GET /api/runs/latest/results` while both rows are preserved in `hr_decisions` and `audit_log` -> verify exported `.xlsx` workbook has `Status = HR decided` and `Final Decision = Shortlisted`.

### 3.2 Live Localhost Server & SQLite Verification
Started `./screening_webapp/run_demo.sh` on `127.0.0.1` and executed the full end-to-end flow against `screening_webapp/data/app.db`:
- Verified `/health`, `/api/me`, `/api/folders`, `/api/folders/C001/preview`, `POST /api/runs`, `GET /api/runs/latest/results`, `POST /api/candidates/C004/decision`, `GET /api/history`, and `GET /api/export.xlsx`.
- Verified `screening_webapp/data/app.db` contains populated rows across all 4 tables (`runs`, `candidate_results`, `hr_decisions`, `audit_log`).

---

## 4. What Still Needs a Live Google Sign-In Test on the Laptop

Because automated tests on the headless Linux server verify the Google OAuth flow using a mocked token verifier and the local demo token (`DEMO_TEST_AUTH=1`), the following steps should be verified interactively in a real browser on your laptop:

1. **Google Cloud Console Authorised JavaScript Origin**:
   - Ensure `http://localhost:8080` and `http://127.0.0.1:8080` are listed under **Authorised JavaScript origins** for OAuth Client ID `259388273008-n8vg3ae8be86e56svvg09rbdciah17u1.apps.googleusercontent.com`.
2. **Real Google Account Allow-List Check**:
   - Add your real Google email address to `screening_webapp/config/allowed_emails.json`.
   - Start the server (`./screening_agent/.venv/bin/python -m screening_webapp`), open `http://localhost:8080` in Chrome/Safari/Edge, and click the **Sign in with Google** button rendered by Google Identity Services.
   - Confirm that signing in with an allowed Google account loads the workspace (`200 OK`) and signing in with a non-listed Google account shows the `403 Forbidden` message.
