# T015 - Human in the loop: HR decides when the AI is not sure, and can always override

## Principle
The AI recommends, a human decides. The agent must be smart enough to decide clear cases on its own, but it must hand over
to HR whenever it is unsure, and an HR decision always wins. The agent must never force an AI decision on HR.
It also must not hand over so many cases that it adds no value: most clear cases should be decided by the AI.

## 1. Uncertainty in the screening output (schemas.py, prompts/screening_prompt.md)
Add to CandidateEvaluation:
- confidence: float 0.0-1.0 (how sure the model is of the decision, based on the evidence)
- review_reasons: list of short reasons, empty if none. Allowed reasons:
  "borderline_score" (overall score within 10 points of the shortlist threshold),
  "missing_evidence" (a must-have criterion has no evidence in the application),
  "conflicting_evidence" (evidence contradicts itself or the rubric),
  "unreadable_document" (a file could not be read or is mostly empty),
  "low_confidence" (confidence below 0.6)
- needs_human_review = True if review_reasons is not empty.
Update the screening prompt so the model fills these fields honestly. It must never guess to avoid review, and must never invent evidence.

## 2. Decision status (tools.py, write_results_excel)
Each candidate gets one of these statuses:
- "AI decided" - clear case, no review reasons. The AI decision is the working decision.
- "Needs HR review" - review reasons present. The AI decision is shown as a RECOMMENDATION only, with the reasons.
- "HR decided" - an HR decision exists (see section 3). It overrides everything.
Do not silently treat a "Needs HR review" case as final.

## 3. Recording HR decisions
- Add a tool record_hr_decision(candidate_id, decision, note) where decision is "Shortlisted" or "Not Shortlisted".
  It writes to output/hr_decisions.json (candidate_id, decision, note, timestamp in UTC) and then regenerates output/screening_results.xlsx.
- The Excel must have these columns: Candidate ID, Name, AI Recommendation, AI Confidence, Review Reasons, Status,
  HR Decision (blank unless set), HR Note, Final Decision, Overall Score, Top Strengths, Gaps, Reasoning, Source Folder.
  Final Decision = HR Decision if set, otherwise AI Recommendation.
- Sort: "Needs HR review" first, then by score descending.
- Add a sheet "Review Queue" listing only the "Needs HR review" candidates with their reasons, so HR can work through them.
- Metadata sheet: add the number of AI decided, number needing HR review, number HR decided, and the flag rate.

## 4. Calibration guard (so the agent is not too dumb or too pushy)
- If more than 40% of candidates need HR review, the Metadata sheet and the final message must show a warning:
  "High review rate: the rubric or prompt may need tuning." Do not hide it.
- Test with the 3 dummy candidates and at least one extra dummy case that has missing evidence, to check the review path works.

## 5. ADK web
- record_hr_decision must be registered as a tool the agent can call from the chat, so HR can say e.g. "Shortlist C002, note: strong portfolio" and the agent records it.
- The first "hi" must still work (keep the T013 fix).

## Tests (tests/test_human_in_loop.py, pytest)
a. A clear candidate gets status "AI decided" and needs_human_review False.
b. A borderline score (within 10 of the threshold) gets "borderline_score" and status "Needs HR review".
c. Missing evidence for a must-have gets "missing_evidence".
d. record_hr_decision writes hr_decisions.json, regenerates the Excel, and Final Decision equals the HR decision.
e. An HR decision overrides an AI recommendation in both directions.
f. The review-rate warning appears when more than 40% need review.
Use fake/mocked model output for these tests. They must not need Vertex.

## Rules
- Work only inside ~/candidates_screening. Do not touch other folders.
- No keys or credentials in any file or message.
- Do not publish or deploy anything.
- Keep the existing tests passing.

## Done means
- All tests pass (show the pytest summary).
- The live run (T014 style) on the dummy data produces the new columns and statuses.
- demo/HITL_REPORT.md explains, in plain language: which cases the AI decided, which went to HR and why, and the review rate.
- Final message lists the changes and anything the user should check in ADK web.
