"""Plain-language translation for screening evaluations and review codes (T016).

Maps internal review codes (borderline_score, missing_evidence, conflicting_evidence,
unreadable_document, low_confidence) to clear sentences suitable for HR users.
"""

from __future__ import annotations

import re
from typing import Any


def _fmt_num(val: float | int) -> str:
    """Format a number without a trailing .0 if it is a whole integer."""
    rounded = round(float(val), 1)
    if rounded.is_integer():
        return str(int(rounded))
    return f"{rounded:.1f}"


def format_review_reason(
    code: str,
    score: float | None = None,
    threshold: float = 70.0,
    confidence: float | None = None,
    evidence: dict[str, Any] | None = None,
) -> str:
    """Convert a single internal review reason code into a human-readable sentence.

    Args:
        code: One of 'borderline_score', 'missing_evidence', 'conflicting_evidence',
              'unreadable_document', 'low_confidence'.
        score: Candidate's overall score (0-100), if available.
        threshold: Shortlist pass threshold (0-100), defaults to 70.0.
        confidence: Model confidence (0.0-1.0), if available.
        evidence: Optional evidence dictionary containing criterion_scores or gaps.

    Returns:
        A plain-English sentence explaining the review reason.
    """
    clean_code = str(code).strip().lower()

    if clean_code == "borderline_score":
        if score is not None:
            s_str = _fmt_num(score)
            t_str = _fmt_num(threshold)
            diff = round(threshold - score, 1)
            if diff > 0:
                return (
                    f"Borderline: score is {s_str} out of 100, "
                    f"{_fmt_num(diff)} points below the threshold of {t_str}."
                )
            if diff < 0:
                return (
                    f"Borderline: score is {s_str} out of 100, "
                    f"only {_fmt_num(abs(diff))} points above the threshold of {t_str}."
                )
            return (
                f"Borderline: score is {s_str} out of 100, "
                f"right at the threshold of {t_str}."
            )
        return (
            f"Borderline: score is within 10 points of the pass threshold of {_fmt_num(threshold)}."
        )

    if clean_code == "missing_evidence":
        missing_skills: list[str] = []
        if isinstance(evidence, dict):
            for cs in evidence.get("criterion_scores") or []:
                if (
                    isinstance(cs, dict)
                    and cs.get("category") == "must_have"
                    and cs.get("score") == 0
                    and cs.get("criterion_name")
                ):
                    missing_skills.append(str(cs["criterion_name"]))
        if missing_skills:
            skills_str = ", ".join(missing_skills)
            return (
                f"Missing evidence: the application does not mention required skill(s): {skills_str}."
            )
        return (
            "Missing evidence: one or more essential job requirements could not be verified from the submitted documents."
        )

    if clean_code == "conflicting_evidence":
        return (
            "Conflicting evidence: statements across the CV, cover letter, or email contradict each other and need HR verification."
        )

    if clean_code == "unreadable_document":
        return (
            "Unreadable document: one or more submitted files could not be read or contained almost no text."
        )

    if clean_code == "low_confidence":
        if confidence is not None:
            pct = int(round(float(confidence) * 100))
            return (
                f"Low confidence: the AI confidence level is {pct}%, which is below the 60% certainty threshold."
            )
        return (
            "Low confidence: the AI is less than 60% certain about this recommendation and requires HR review."
        )

    # Fallback for any unexpected code: convert underscores to plain text sentence
    humanized = clean_code.replace("_", " ").capitalize()
    return f"{humanized}: flagged for HR review."


def format_review_reasons(
    codes: list[str],
    score: float | None = None,
    threshold: float = 70.0,
    confidence: float | None = None,
    evidence: dict[str, Any] | None = None,
) -> list[str]:
    """Convert a list of internal review codes into a list of plain-English sentences."""
    return [
        format_review_reason(
            code,
            score=score,
            threshold=threshold,
            confidence=confidence,
            evidence=evidence,
        )
        for code in (codes or [])
    ]


def format_status_badge(status_str: str) -> str:
    """Map internal status string to the HR-facing status badge label.

    - 'AI decided' -> 'AI decided'
    - 'Needs HR review' -> 'Needs your review'
    - 'HR decided' -> 'You decided'
    """
    normalized = str(status_str).strip().lower()
    if normalized in ("needs hr review", "needs your review"):
        return "Needs your review"
    if normalized in ("hr decided", "you decided"):
        return "You decided"
    return "AI decided"


def format_ai_recommendation(decision: str) -> str:
    """Format the AI recommendation in plain words."""
    cleaned = str(decision).strip().lower()
    if cleaned == "shortlisted":
        return "Recommend shortlist"
    return "Do not shortlist"


def build_plain_why_summary(
    ai_decision: str,
    ai_score: float,
    threshold: float,
    confidence: float,
    review_reasons: list[str],
    evidence: dict[str, Any] | None = None,
) -> str:
    """Build a friendly plain-language explanation combining review sentences and key evidence."""
    ev = evidence or {}
    reason_sentences = format_review_reasons(
        review_reasons,
        score=ai_score,
        threshold=threshold,
        confidence=confidence,
        evidence=ev,
    )

    parts: list[str] = []
    if reason_sentences:
        parts.extend(reason_sentences)

    reasoning_text = str(ev.get("reasoning") or "").strip()
    # Replace any raw internal code tokens if they appear in model reasoning
    for raw_code in (
        "borderline_score",
        "missing_evidence",
        "conflicting_evidence",
        "unreadable_document",
        "low_confidence",
    ):
        reasoning_text = reasoning_text.replace(raw_code, raw_code.replace("_", " "))

    if reasoning_text:
        if str(ai_decision).strip().lower() == "shortlisted":
            reasoning_text = re.sub(
                r"recommended\s+as\s+Not\s+Shortlisted",
                "recommended as Shortlisted",
                reasoning_text,
                flags=re.IGNORECASE,
            )
            reasoning_text = re.sub(
                r"\bis\s+not\s+shortlisted\b",
                "is recommended as Shortlisted",
                reasoning_text,
                flags=re.IGNORECASE,
            )
            reasoning_text = re.sub(
                r"\bdo\s+not\s+shortlist\b",
                "recommend for shortlisting",
                reasoning_text,
                flags=re.IGNORECASE,
            )
            reasoning_text = re.sub(
                r"\(well\s+below\s+the\s+[\d.]+\s+threshold\),\s*the\s+candidate\s+is\s+a\s+clear\s+non-match\.?",
                f"(above the {_fmt_num(threshold)} threshold), the candidate is a strong match for shortlisting.",
                reasoning_text,
                flags=re.IGNORECASE,
            )
        else:
            reasoning_text = re.sub(
                r"recommended\s+as\s+Shortlisted",
                "recommended as Not Shortlisted",
                reasoning_text,
                flags=re.IGNORECASE,
            )
            reasoning_text = re.sub(
                r"\bis\s+recommended\s+for\s+shortlisting\b",
                "is recommended as Not Shortlisted",
                reasoning_text,
                flags=re.IGNORECASE,
            )
        parts.append(reasoning_text)
    else:
        score_str = _fmt_num(ai_score)
        thresh_str = _fmt_num(threshold)
        if ai_decision == "Shortlisted":
            parts.append(
                f"Scored {score_str} out of 100 (pass mark is {thresh_str}) with strong evidence across required skills."
            )
        else:
            parts.append(
                f"Scored {score_str} out of 100, below the shortlist threshold of {thresh_str}."
            )

    return " ".join(parts)
