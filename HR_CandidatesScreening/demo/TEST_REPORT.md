# End-to-End Live Test Report (T014)

**Date (UTC):** 2026-10-14  
**Model Used:** `gemini-4-argon` (Vertex AI)  
**Overall Status:** **PASS**

---

## Summary of Steps

| Step | Description | Status |
| :--- | :--- | :---: |
| **Step 1** | Run full live pipeline (`python -m screening_agent.agent`) on dummy data | **PASS** |
| **Step 2** | Verify `output/rubric.json` and `output/screening_results.xlsx` timestamps, rows, metadata, scores, decisions, and evidence | **PASS** |
| **Step 3** | Start `adk web` on port 8000, create session (`POST /apps/screening_agent/users/user/sessions`), send `"hi"` (`POST /run_sse`), verify no `KeyError` and full agent reply, stop server | **PASS** |
| **Step 4** | Run `pytest` on `screening_agent/tests/` | **PASS (4/4)** |
| **Step 5** | Fix any issues found and re-run Steps 1–4 | **PASS** |

---

## Step 1: Full Live Pipeline Execution

- **Status:** **PASS**
- **Command Run (from `~/candidates_screening`):**
  ```bash
  screening_agent/.venv/bin/python -m screening_agent.agent
  ```
- **Output Summary:**
  - `rubric_path`: `/home/ubuntu/candidates_screening/screening_agent/output/rubric.json`
  - `excel_path`: `/home/ubuntu/candidates_screening/screening_agent/output/screening_results.xlsx`
  - `candidates_screened`: `3` (`C001`, `C002`, `C003`)

---

## Step 2: Output & Evidence Verification

- **Status:** **PASS**
- **Command Run (from `~/candidates_screening`):**
  ```bash
  screening_agent/.venv/bin/python -c '
  from datetime import datetime, timezone
  from pathlib import Path
  from openpyxl import load_workbook

  base = Path("screening_agent/output")
  for fname in ["rubric.json", "screening_results.xlsx"]:
      p = base / fname
      st = p.stat()
      mtime = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
      print(f"{fname}: exists={p.exists()}, size={st.st_size}, mtime_utc={mtime}")

  wb = load_workbook(base / "screening_results.xlsx")
  for name in wb.sheetnames:
      ws = wb[name]
      print(f"\n--- Sheet: {name} (rows={ws.max_row}, cols={ws.max_column}) ---")
      for r in range(1, ws.max_row + 1):
          row_vals = [ws.cell(row=r, column=c).value for c in range(1, ws.max_column + 1)]
          print(f"Row {r}: {row_vals}")
  '
  ```
- **File Timestamps (UTC):**
  - `screening_agent/output/rubric.json`: `2026-10-14T16:58:31Z` (1,739 bytes)
  - `screening_agent/output/screening_results.xlsx`: `2026-10-14T16:58:58Z` (10,762 bytes)
- **Metadata Sheet Verification:**
  - `Job Title`: `Sales Executive - Retail and Business Clients`
  - `Shortlist Threshold`: `70.0`
  - `Requires Continuity`: `False`
  - `Prompt Version`: `v1.1`
  - `Model Used`: `gemini-4-argon`
- **Results Sheet & Per-Candidate Evidence Evaluation:**
  1. **`C001` (`Dummy Candidate A`) — `Shortlisted` | Score: `100.0/100` | Needs Human Review: `No`**
     - **Assessment:** Sensible and accurate.
     - **Criterion Scores & Evidence:**
       - `M1` (5/5, weight 25%): *"Sales Executive with 6 years of customer-facing sales and retail account management experience."*
       - `M2` (5/5, weight 25%): *"Consistently achieved 115%+ of monthly sales targets across 5 consecutive years."*
       - `M3` (5/5, weight 20%): *"Clear written and spoken communication; led client presentations and commercial contract negotiations."*
       - `N1` (5/5, weight 15%): *"4 years of daily CRM usage (Salesforce and HubSpot) and Excel pipeline reporting."*
       - `N2` (5/5, weight 15%): *"Managed a portfolio of 45 retail and SME business accounts with 94% annual retention."*
     - **Fairness Note:** The 2023 career break was properly ignored (`requires_continuity = False`), and PII/protected attributes were redacted prior to LLM evaluation.
  2. **`C002` (`Dummy Candidate B`) — `Not Shortlisted` | Score: `49.0/100` | Needs Human Review: `No`**
     - **Assessment:** Sensible and accurate. Candidate has 2 years of retail sales assistant experience (below the 3+ years requirement) and ~6 months of junior sales target exposure.
     - **Criterion Scores & Evidence:**
       - `M1` (3/5, weight 25%): *CV: "Retail Sales Assistant with 2 years of customer service and floor sales experience."*
       - `M2` (2/5, weight 25%): *CV: "6 months of exposure to monthly store sales targets as a junior sales associate."*
       - `M3` (3/5, weight 20%): *Cover Letter: "Assisted walk-in customers with product enquiries and written order quotes."*
       - `N1` (2/5, weight 15%): *CV: "Basic familiarity with Excel spreadsheets; no dedicated CRM software experience yet."*
       - `N2` (2/5, weight 15%): *CV: "Handled individual retail counter enquiries; no dedicated business client portfolio yet."*
  3. **`C003` (`Dummy Candidate C`) — `Not Shortlisted` | Score: `0.0/100` | Needs Human Review: `No`**
     - **Assessment:** Sensible decision and score (`Not Shortlisted`, `0.0/100`).
     - **Criterion Scores & Evidence:**
       - `M1`–`N2` (all 0/5): *Cover Letter & CV: "Background is solely in warehouse stock control, forklift operation, and inventory dispatch with no sales, target tracking, or client communication responsibilities."*

---

## Step 3: ADK Web HTTP / SSE Test (`adk web`)

- **Status:** **PASS**
- **Note on Port 8000 Binding:** On this server, `127.0.0.1:8000` is already bound by another service (`uvicorn` PID 4870). We bound `adk web` to loopback address `127.0.0.2` on port `8000` (`--host 127.0.0.2 --port 8000`), which uses port `8000` without interfering with other processes.
- **Commands Run (from `~/candidates_screening`):**
  ```bash
  screening_agent/.venv/bin/adk web --host 127.0.0.2 --port 8000 > demo/adk_web_run.log 2>&1 &
  ADK_PID=$!
  trap "kill $ADK_PID 2>/dev/null || true; wait $ADK_PID 2>/dev/null || true; rm -rf demo/adk_web_run.log .adk screening_agent/.adk" EXIT

  # 1. Verify app discovery
  curl -sf http://127.0.0.2:8000/list-apps

  # 2. Create session with empty state
  SESSION_JSON=$(curl -sf -X POST http://127.0.0.2:8000/apps/screening_agent/users/user/sessions -H "Content-Type: application/json" -d "{}")
  SESSION_ID=$(screening_agent/.venv/bin/python -c "import sys, json; print(json.loads(sys.argv[1])['id'])" "$SESSION_JSON")

  # 3. Send first message "hi" via /run_sse
  curl -sf -N -X POST http://127.0.0.2:8000/run_sse \
    -H "Content-Type: application/json" \
    -d "{\"appName\": \"screening_agent\", \"userId\": \"user\", \"sessionId\": \"$SESSION_ID\", \"newMessage\": {\"role\": \"user\", \"parts\": [{\"text\": \"hi\"}]}}"
  ```
- **Results:**
  - `GET /list-apps` returned `["screening_agent"]`.
  - `POST /apps/screening_agent/users/user/sessions` created a session with `"state": {}`.
  - `POST /run_sse` with `"hi"` succeeded with HTTP 200 and zero `KeyError` exceptions.
  - Streamed two SSE `data:` events:
    1. `author: "rubric_agent"` (`modelVersion: "gemini-4-argon"`) containing the structured `JobRubric` JSON and `stateDelta.rubric`.
    2. `author: "screening_pipeline"` containing the JSON summary for `C001`–`C003` and `stateDelta` with `rubric_path`, `excel_path`, and `evaluations`.
  - Server process was cleanly terminated after the test.

---

## Step 4: Pytest Suite Execution

- **Status:** **PASS (4 passed in 1.86s)**
- **Command Run (from `~/candidates_screening`):**
  ```bash
  screening_agent/.venv/bin/python -m pytest screening_agent/tests/ -v
  ```
- **Output:**
  ```text
  screening_agent/tests/test_adk_web_entry.py::test_root_agent_exists PASSED [ 25%]
  screening_agent/tests/test_adk_web_entry.py::test_resolve_instructions_with_empty_session_state PASSED [ 50%]
  screening_agent/tests/test_adk_web_entry.py::test_adk_web_first_message_hi_with_empty_state PASSED [ 75%]
  screening_agent/tests/test_adk_web_entry.py::test_get_model_name_defaults_to_gemini_2_5_pro PASSED [100%]
  ```

---

## Issues Found and Fixed

1. **Issue Found (Step 4):** Running `pytest` executed `test_adk_web_first_message_hi_with_empty_state` in offline mode (with `GOOGLE_GENAI_USE_VERTEXAI` unset via `monkeypatch`), which wrote to the default `screening_agent/output/rubric.json` and `screening_agent/output/screening_results.xlsx` paths, overwriting the live `gemini-4-argon` outputs with offline deterministic outputs.
   - **Fix Applied:** Updated `test_adk_web_first_message_hi_with_empty_state` in `screening_agent/tests/test_adk_web_entry.py` to monkeypatch `screening_agent.tools.DEFAULT_RUBRIC_PATH` and `screening_agent.tools.DEFAULT_EXCEL_PATH` to pytest's isolated `tmp_path`.
   - **Verification:** Re-ran Steps 1–4 in full after the change and verified that `screening_agent/output/rubric.json` and `screening_agent/output/screening_results.xlsx` retain the live `gemini-4-argon` outputs after running `pytest`.
