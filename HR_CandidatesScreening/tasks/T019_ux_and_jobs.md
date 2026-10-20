# T019 - Owner feedback: generic (non-tech) examples, remove demo data, job-based workflow, compact results

## 1. Use a non-tech example: Sales hiring
- The owner does not want software or tech examples anywhere in the product.
- Replace every tech example in: the dummy job advert, dummy candidate CVs and cover letters, prompts (prompts/*.md), rubric examples,
  the plain-language texts in the web app, README and reports.
- The new example is a SALES role, e.g. "Sales Executive - Retail and Business Clients". Rubric criteria example:
  must-have: 3+ years of B2B or retail sales with targets; closing deals; CRM use (e.g. Salesforce or any CRM).
  nice-to-have: negotiation, client relationship management, presentations, bilingual communication.
- Keep the agent logic generic (it must work for any job). Only example text changes.
- Update all tests that assumed the old tech examples.

## 2. Remove demo data completely
- Delete the dummy candidates and dummy job advert from the project (screening_agent/data/, the demo zip, MANIFEST, and any demo folders
  in demo/). Keep create_dummy_data.py only if it is moved to tests/fixtures and generates the SALES example into a temp folder used by tests only.
- Remove the yellow "Demo data - not real candidates" banner from the UI.
- Remove the "Sign in as Demo HR" button from the UI. Local testing uses Google sign-in with the allow-list (T017/T018).
  Keep the DEMO_TEST_AUTH mechanism only for automated tests (not shown in the UI).
- Remove the demo user (hr.demo@example.com) from the allow-lists.
- Confirm that no demo data remains in the synced folders (report the sizes freed).

## 3. Home screen: create a Job, then run screening
- The first screen is "Jobs". HR creates a job with:
  - Job title
  - Job ID, generated automatically (e.g. JOB-2026-001), shown everywhere
  - Job description file (upload .docx or .pdf)
  - CV folder: HR picks a folder in the browser (use a folder picker that uploads the files, e.g. the input with webkitdirectory), OR
    a path under a configured root. Uploaded files are stored under screening_webapp/data/jobs/<JOB-ID>/ (inside the project only).
  - Settings for this job (threshold, continuity, model). Default to the global settings.
- Clicking "Run screening" on a job runs the agent on THAT job's JD and CV folder, then opens the Results for that job.
- Re-running a job creates a new run under the same Job ID (keep history).

### 3.1 Every job has its own Job ID
- Results, History, Excel export and HR decisions are always linked to a Job ID.
- The Results screen has a Job ID selector at the top (dropdown plus search by job ID or title). It never mixes candidates from different jobs.
- Excel export is per job and its file name includes the Job ID.
- Decisions in the database are keyed by (job_id, candidate_id).

## 4. Compact results for large numbers of candidates
- Results is a dense table, with pagination (25 per page) and sorting. Default sort: needs-review first, then score.
- Show the number of documents per candidate (e.g. "3 documents" with a small icon), not the file list.
- The "Why" column shows at most 2 lines with an ellipsis. Clicking "Read more" expands the full text inline. Keep the full text in the data.
- Add a "Needs your review" filter and a search box (name or candidate ID).
- Cards and tables must work at 1280px wide, and the candidates page must not show full CVs by default (use "View" to open a preview).

## 5. Keep the rest
- Google sign-in with the allow-list, the access rule, audit log, decisions and Excel export all stay.
- The agent logic (scoring, review reasons, HR override) does not change except for example text.

## Tests
- Creating a job with an uploaded JD and a CV folder works; the Job ID is unique and shown.
- Running a job only reads that job's files; results are stored with job_id.
- Results filter by Job ID; decisions are keyed by (job_id, candidate_id).
- Long "why" text is truncated in the list view and complete in the detail.
- No tech examples remain (grep the project for the old example words and report the count, which must be zero outside the test fixtures of the old example, which must also be removed).
- All tests pass (agent and web app).

## Rules
- Work only inside ~/candidates_screening. No keys, client secrets or personal data in files or messages.
- Do not publish or deploy. Localhost only.

## Done means
- demo/UX_REPORT.md: what changed, how to create a job and run it, the freed disk size, and the test summary.
- Tests pass (show summary).
