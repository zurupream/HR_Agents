# T014 - End-to-end live test on the server, then hand back for local ADK web test

## Context
- Vertex AI works on this server now (service key at ~/.config/gcp/vertex-sa.json, referenced from .env).
- MODEL_NAME is gemini-4-argon (verified on Vertex: text and structured JSON both work).
- T013 fixed the adk web crash (empty session state). Its tests are in tests/test_adk_web_entry.py.

## Steps (work only inside ~/candidates_screening)
1. Run the full live pipeline on the dummy data:
   cd ~/candidates_screening/screening_agent && .venv/bin/python -m screening_agent.agent
   Run it from ~/candidates_screening so the package import works (use: cd ~/candidates_screening && screening_agent/.venv/bin/python -m screening_agent.agent).
2. Verify the outputs:
   - output/rubric.json and output/screening_results.xlsx exist and were written by THIS run (check timestamps).
   - Results sheet has 3 rows (C001-C003), every row has a decision, a score 0-100, and evidence.
   - Metadata sheet says Model Used = gemini-4-argon.
   - Decisions are sensible for the dummy candidates (report any that look wrong, with the evidence).
3. Test the ADK web path the way the user will: start `adk web` from ~/candidates_screening in the background on port 8000,
   send a first message "hi" via the ADK HTTP API (POST /run_sse for app screening_agent after creating a session with POST /apps/screening_agent/users/user/sessions),
   and confirm there is no KeyError and that the agent replies. Stop the server afterwards.
4. Run pytest again (tests/): all must pass.
5. Fix anything that fails. If you change code, re-run steps 1-4.

## Rules
- Work only inside ~/candidates_screening. Do not touch other folders.
- Never print, copy or write the contents of vertex-sa.json or any key into a file or a message.
- Do not publish or deploy anything. Publishing waits for the user's approval.

## Done means
- A live run output exists from this run, with the verification results above.
- A file ~/candidates_screening/demo/TEST_REPORT.md lists: each step, pass/fail, the exact commands run, and any issues found and fixed.
- Final message summarises the result in plain language, and lists anything the user should check in the ADK web UI.
