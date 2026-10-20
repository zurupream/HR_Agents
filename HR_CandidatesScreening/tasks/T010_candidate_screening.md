# T010 - Candidate screening agent (Google ADK, Python)

## Goal
Screen job applications against a job advert and produce an Excel file marking each candidate Shortlisted / Not Shortlisted, with reasons.

## Auth rule
All agents must sign in with Google OAuth. Client ID (public, safe in config):
259388273008-n8vg3ae8be86e56svvg09rbdciah17u1.apps.googleusercontent.com
Never store a client secret in any file. Any HTTP or UI entry point must reject requests without a valid Google ID token (verify audience equals the Client ID).

## Design principles (non-negotiable)
1. Unbiased: score on job-relevant evidence only. Never use name, gender, age, nationality, photo, marital status or other protected attributes.
2. Fair chance: every candidate is evaluated against the same criteria and rubric. No candidate is dropped by a hard filter before being read.
3. Full context: the model sees the entire application (cover letter, email, CV if present), never truncated snippets.

## Inputs (under ~/candidates_screening/screening_agent/data/)
- job_advert.docx: one Word document.
- applications/: one subfolder per candidate, each with a cover letter (.docx/.pdf/.txt), an email (.txt/.eml/.docx), and optionally a CV (.pdf/.docx).
- For testing: create a DUMMY job_advert.docx and 3 DUMMY candidate folders (clearly fictional, e.g. "Dummy Candidate A"). Real candidate data is not to be committed or copied elsewhere.

## Flow
1. Load advert: extract text from the .docx with python-docx.
2. Build rubric (once): an LLM agent reads the advert and outputs a structured rubric (must-have criteria, nice-to-have criteria, weights). Save to output/rubric.json. The same rubric applies to everyone.
3. Load applications: for each candidate folder, extract text from all files into one record. Assign an anonymous ID (C001, C002, ...).
4. Anonymise: redact name, contact details, gender/age/nationality indicators, photo references before scoring. Keep the ID-to-name mapping locally, outside the LLM context.
5. Screen: for each candidate, an LLM agent scores the anonymised application against the rubric. Structured output (Pydantic):
   - per-criterion score (0-5) with an evidence quote or reference
   - overall score (0-100)
   - decision: Shortlisted / Not Shortlisted
   - strengths, gaps, short reasoning (max 3 sentences)
   - needs_human_review flag for borderline or unclear cases
6. Output: write output/screening_results.xlsx (openpyxl) after re-attaching real names via the mapping.

## Excel output
- Sheet "Results": one row per candidate. Columns: Candidate ID, Name, Decision, Overall Score, Top Strengths, Gaps, Reasoning, Needs Human Review, Source Folder. Sorted by score descending. Decision cells colour-coded.
- Sheet "Rubric": criteria and weights used.
- Metadata: rubric, prompt version and model used.

## ADK structure
- SequentialAgent as root: rubric_agent, then screening_pipeline.
- Candidate loop in Python, or LoopAgent/ParallelAgent over candidates, with one fresh screening agent call per candidate so applications never contaminate each other.
- Tools (plain Python functions): read_job_advert, list_candidates, read_application, anonymise_text, write_results_excel.
- output_schema (Pydantic) on screening and rubric agents. Temperature 0-0.2.
- Model configurable via env var. API keys read from environment or a local .env that is never committed. Never write a key into any file the agent creates.

## Fairness and reliability
- Same rubric and prompt for all candidates.
- Screening prompt must say: judge only demonstrated skills and experience; ignore writing style quirks, name origin, employment gaps unless the advert requires continuity, and anything not in the rubric.
- AI recommends, a human decides: borderline cases are flagged, never silently rejected.

## Project layout (under ~/candidates_screening/screening_agent/)
  agent.py, tools.py, schemas.py, prompts/ (rubric_prompt.md, screening_prompt.md), data/, output/, .env (not committed), requirements.txt (google-adk, python-docx, pypdf, openpyxl, pydantic)

## Deliverable order
1. Structure plus tools
2. Rubric agent
3. Screening agent
4. Excel writer
5. Test with the 3 dummy candidates

## Done means
- Project structure and tools exist under ~/candidates_screening/screening_agent/.
- Rubric agent, screening agent and Excel writer run end to end on the 3 dummy candidates.
- output/screening_results.xlsx and output/rubric.json exist and are checked by opening them.
- Nothing outside ~/candidates_screening/ is modified.
- Final summary lists what was built, the test result, and any blockers.
