# Human-in-the-Loop (HITL) Screening Report

**Date (UTC):** 2026-10-14  
**Model:** `gemini-4-argon` (Vertex AI)  
**Prompt Version:** `v1.1`  
**Shortlist Threshold:** `70.0 / 100.0`

---

## 1. Plain-Language Overview

The Candidate Screening Agent follows a simple principle: **the AI recommends, and HR decides whenever a case is uncertain—while HR can always override any decision.**

Instead of forcing a final decision on every applicant or flagging everyone for manual review, the agent separates candidates into clear cases and uncertain cases:
- **AI decided:** When the application evidence is complete, clear, and well above or below the shortlist threshold (`70.0`), the AI makes the working decision on its own.
- **Needs HR review:** When an application is close to the pass mark (`borderline_score`), lacks proof for a required skill (`missing_evidence`), contradicts itself (`conflicting_evidence`), has unreadable files (`unreadable_document`), or leaves the model unsure (`low_confidence < 0.6`), the candidate is placed at the top of the results table and added to the **Review Queue** sheet for HR to decide.
- **HR decided:** Whenever HR records a decision (either for a flagged candidate or to override an AI decision), HR's choice becomes the **Final Decision** and the candidate's status changes to `HR decided`.

---

## 2. Live Run Results (`C001` – `C004`)

| Candidate ID | Name | Overall Score | AI Recommendation | AI Confidence | Review Reasons | Status | Final Decision |
| :--- | :--- | :---: | :---: | :---: | :--- | :---: | :---: |
| **C004** | Dummy Candidate D | `64.0` | Not Shortlisted | `0.70` | `borderline_score`, `missing_evidence` | **Needs HR review** | Not Shortlisted *(pending HR review)* |
| **C001** | Dummy Candidate A | `100.0` | Shortlisted | `0.98` | *(none)* | **AI decided** | Shortlisted |
| **C002** | Dummy Candidate B | `49.0` | Not Shortlisted | `0.85` | *(none)* | **AI decided** | Not Shortlisted |
| **C003** | Dummy Candidate C | `0.0` | Not Shortlisted | `0.98` | *(none)* | **AI decided** | Not Shortlisted |

*(Note: Rows in `output/screening_results.xlsx` are automatically sorted with `Needs HR review` candidates first, followed by highest score descending.)*

---

## 3. Which Cases the AI Decided

The AI decided **3 out of 4 candidates (75.0%)** on its own because the evidence in their applications was unambiguous:

1. **`C001` — Dummy Candidate A (`100.0 / 100`, `Shortlisted`, Confidence `0.98`, Status: `AI decided`)**
   - **Why the AI decided:** Clear, well-documented evidence for every must-have requirement (6 years of customer-facing sales and retail account management, 5 consecutive years achieving 115%+ of monthly sales targets, clear client communication and commercial contract negotiation, plus daily CRM & Excel pipeline reporting and retail/B2B portfolio retention). The score (`100.0`) is well above the `70.0` threshold with no missing or conflicting information.

2. **`C002` — Dummy Candidate B (`49.0 / 100`, `Not Shortlisted`, Confidence `0.85`, Status: `AI decided`)**
   - **Why the AI decided:** The CV clearly shows 2 years of retail sales assistant experience and only brief junior exposure to monthly sales targets (~6 months), falling short of the 3+ years sales and proven target achievement requirements. The weighted score (`49.0`) is 21 points below the `70.0` shortlist threshold, making it a clear non-shortlist case without needing HR escalation.

3. **`C003` — Dummy Candidate C (`0.0 / 100`, `Not Shortlisted`, Confidence `0.98`, Status: `AI decided`)**
   - **Why the AI decided:** The applicant's background is entirely in warehouse stock control and inventory dispatch with zero customer-facing sales, target tracking, or client account management evidence. Every criterion scored `0/5` with complete certainty.

---

## 4. Which Case Went to HR and Why

The agent handed over **1 out of 4 candidates (25.0%)** to HR:

1. **`C004` — Dummy Candidate D (`64.0 / 100`, AI Recommendation: `Not Shortlisted`, Confidence `0.70`, Status: `Needs HR review`)**
   - **Why it went to HR (`missing_evidence` + `borderline_score`):**
     - **`missing_evidence`:** Dummy Candidate D has strong evidence for Must-Have `M1` (4 years of customer-facing sales, `5/5`) and Must-Have `M2` (exceeded quarterly sales targets by 105%, `4/5`), as well as CRM & Excel pipeline tracking (`5/5`) and retail/B2B account management (`4/5`). However, the application **never mentions written/spoken client communication or commercial negotiation** (Must-Have `M3`, weight `20%`). Because a required must-have skill has no evidence in the submitted files, the agent flags `missing_evidence` rather than guessing.
     - **`borderline_score`:** Because `M3` scored `0/5` while all other criteria scored `4/5` or `5/5`, the candidate's overall score is `64.0`—within 10 points of the `70.0` shortlist threshold (`60.0 <= 64.0 <= 80.0`). A single clarifying question from HR (confirming whether the candidate has client communication and negotiation experience that was omitted from the brief CV) would move this candidate well past the shortlist threshold.

---

## 5. Review Rate & Calibration Check

- **Total Candidates Screened:** `4`
- **AI Decided:** `3` (`75.0%`)
- **Needs HR Review:** `1` (`25.0%`)
- **HR Decided:** `0` (`0.0%` prior to HR review)
- **Flag Rate:** `1/4 (25.0%)`
- **Calibration Guard (`<= 40%` threshold):** **OK** — Because the flag rate (`25.0%`) is below the `40%` ceiling, the calibration status is healthy (`OK`). If more than `40%` of candidates ever require review, both the Excel `Metadata` sheet and the agent's final response automatically display:  
  `"High review rate: the rubric or prompt may need tuning."`

---

## 6. How HR Records or Overrides a Decision

HR can record a decision for any candidate (`Needs HR review` or `AI decided`) directly in the ADK web chat—for example:
- `"Shortlist C004, note: confirmed client communication and negotiation skills in phone screen"`
- `"Reject C001, note: salary expectations out of range"`

When HR gives this instruction, the agent calls `record_hr_decision(candidate_id, decision, note)`, which:
1. Saves the decision, note, and UTC timestamp to `screening_agent/output/hr_decisions.json`.
2. Regenerates `screening_agent/output/screening_results.xlsx` so that `Status` becomes `"HR decided"`, `Final Decision` matches `HR Decision`, and the candidate is removed from the `"Review Queue"` sheet.
