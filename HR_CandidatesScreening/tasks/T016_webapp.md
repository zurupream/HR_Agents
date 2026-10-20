# T016 - Human-friendly web app for HR (keep the agent unchanged)

## Feedback that drives this task
ADK web shows raw JSON (rubric dumps, schema fields, tool calls). HR users cannot read that. The screening agent must stay as it is,
but HR needs a normal web app to: see the candidate folders and CVs, run the agent with simple settings, read the results in plain
language, and record decisions. Build that as a separate app that CALLS the agent code.

## Scope
Create a new folder ~/candidates_screening/screening_webapp/ (do NOT change the agent package except to expose functions the app needs;
if you must change the agent, say exactly what and why in the final report, and keep all tests passing).

### Backend (FastAPI)
- Reuse screening_agent functions: list_candidates, read_application, read_job_advert, run_screening_pipeline, write_results_excel,
  record_hr_decision logic. Do not duplicate the scoring logic.
- Database: SQLite file screening_webapp/data/app.db via SQLAlchemy, with the URL in an env var (DATABASE_URL) so Cloud SQL can be
  switched in later without code changes. Tables:
  - runs (id, started_at, finished_at, status, settings_json, model, threshold, candidate_count, error)
  - candidate_results (run_id, candidate_id, name, ai_decision, ai_score, confidence, status, review_reasons_json, evidence_json)
  - hr_decisions (id, candidate_id, run_id, decision, note, decided_by_email, decided_at_utc). Keep history; the latest one is the current decision.
  - audit_log (id, at_utc, actor_email, action, detail)
- API endpoints:
  - GET /api/folders : the application folders and their files (name, type, size, parse status) for the configured applications directory.
  - GET /api/folders/{candidate_id}/preview : extracted text preview of each file (first ~1500 chars) for a CV/cover letter.
  - GET /api/settings and PUT /api/settings : threshold (default 70), requires_continuity (default false), model (choose from a fixed allow-list:
    gemini-4-argon, gemini-2.5-pro, gemini-2.5-flash), applications_dir (must be inside the project data folder), redact_before_scoring (default true, cannot be turned off for production; shown as on).
  - POST /api/runs : start a screening run in a background task; returns run_id. Only one run at a time.
  - GET /api/runs/{run_id} : status and progress (current candidate index / total).
  - GET /api/runs/latest/results : results for the latest finished run, merged with the latest HR decision.
  - POST /api/candidates/{candidate_id}/decision : body {decision: Shortlisted|Not Shortlisted, note}. Writes hr_decisions and audit_log, regenerates the Excel.
  - GET /api/export.xlsx : the current Excel file.
- Auth: Google Sign-In. Verify the Google ID token server-side (google-auth) against the Client ID
  259388273008-n8vg3ae8be86e56svvg09rbdciah17u1.apps.googleusercontent.com. Only emails in an allow-list (config file, default: empty means nobody) can use the app.
  Never store a client secret. Every API call except /health and the sign-in page requires a valid token.
- Plain-language decisions: the API returns the reasons as sentences, e.g. "Borderline: score is 64 out of 100, 6 points below the threshold of 70."
  Map the internal codes (borderline_score, missing_evidence, conflicting_evidence, unreadable_document, low_confidence) to human sentences.

### Frontend (single page, no build step, plain HTML + CSS + vanilla JS, or a small React build if you prefer; keep it simple)
- Sign-in page with Google button.
- Top bar: app name, signed-in user, logout.
- Left panel "Settings": threshold slider, requires-continuity toggle, model dropdown, applications folder shown read-only, redaction shown as on, and a big "Run screening" button (disabled while a run is in progress, shows a progress bar).
- Main area tabs:
  1. "Candidates": a card per candidate: name, folder, files found (with icons), a "View CV" expand showing the text preview.
  2. "Results": table sorted with "Needs your review" first. Columns: Candidate, Score, AI recommendation (plain words), Why (plain sentences), Status badge
     (AI decided / Needs your review / You decided). Buttons "Shortlist" and "Not shortlist" with an optional note. Show the current decision and who made it.
  3. "History": past runs with date, settings used, number of candidates, and the audit log for decisions.
- Export button for the Excel file.
- Plain English everywhere. No JSON shown to the user. Responsive for a laptop screen; readable at 1280px wide.
- Light and dark themes via CSS variables, default follows the OS.

### Demo mode
- Works with the dummy data by default, with a clear banner "Demo data - not real candidates".

## Tests (screening_webapp/tests, pytest)
- Auth: no token -> 401; invalid token -> 401; valid token (mocked verifier) for an allowed email -> 200; allowed-list empty -> 403.
- Runs: starting a run returns a run_id; a second run while one is running returns 409; results are stored in the database.
- Decisions: POST decision writes hr_decisions, audit_log, and the Excel is regenerated; the latest decision wins in GET results.
- Plain-language reasons: each internal review code maps to a readable sentence.
- Settings validation: model must be in the allow-list; applications_dir outside the project is rejected.
- Keep all existing tests in screening_agent/tests passing.

## Run instructions for HR (write them in screening_webapp/README.md)
- How to install, set GOOGLE_APPLICATION_CREDENTIALS (path only) and the env vars, start the app, open it in a browser.

## Rules
- Work only inside ~/candidates_screening. Do not touch other folders.
- No keys, client secrets, or personal data in files or messages. Real candidate data must never be committed or shown in logs.
- Do not publish or deploy. Do not open the app to the internet. Run it on localhost only.

## Done means
- The app starts with one command and the demo flow works end to end: sign in (test mode with mocked token), see candidates, run screening, see plain-language results, record a decision, see it in History.
- All tests pass (show the pytest summary).
- screening_webapp/README.md and demo/WEBAPP_REPORT.md (what was built, how to run, what was verified, what still needs a live Google sign-in test on the laptop).
