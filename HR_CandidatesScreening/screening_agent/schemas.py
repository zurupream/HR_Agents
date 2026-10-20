"""Pydantic schemas for the Candidate Screening Agent (T010, T015)."""

from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field, model_validator

ALLOWED_REVIEW_REASONS = (
    "borderline_score",
    "missing_evidence",
    "conflicting_evidence",
    "unreadable_document",
    "low_confidence",
)

ReviewReason = Literal[
    "borderline_score",
    "missing_evidence",
    "conflicting_evidence",
    "unreadable_document",
    "low_confidence",
]


class Criterion(BaseModel):
    """A single evaluation criterion extracted from the job advert."""

    id: str = Field(description="Unique criterion identifier, e.g., M1, M2, N1")
    name: str = Field(description="Short name of the criterion")
    category: Literal["must_have", "nice_to_have"] = Field(
        description="Whether this criterion is a must-have or nice-to-have requirement"
    )
    description: str = Field(
        description="Clear description of what job-relevant evidence satisfies this criterion"
    )
    weight: float = Field(
        ge=0.0,
        le=100.0,
        description="Relative weight of this criterion (all criteria weights sum to 100)",
    )


class JobRubric(BaseModel):
    """Structured scoring rubric generated once from the job advert."""

    job_title: str = Field(description="Title of the open role from the job advert")
    role_summary: str = Field(description="Brief summary of the role and core responsibilities")
    must_have_criteria: list[Criterion] = Field(
        description="Essential criteria required for the role"
    )
    nice_to_have_criteria: list[Criterion] = Field(
        description="Desirable criteria that strengthen an application"
    )
    shortlist_threshold: float = Field(
        default=70.0,
        ge=0.0,
        le=100.0,
        description="Minimum overall score (0-100) for Shortlisted recommendation",
    )
    requires_continuity: bool = Field(
        default=False,
        description="True only if the advert explicitly requires continuous employment without gaps",
    )

    def all_criteria(self) -> list[Criterion]:
        """Return all criteria in order: must-have followed by nice-to-have."""
        return list(self.must_have_criteria) + list(self.nice_to_have_criteria)


class CriterionScore(BaseModel):
    """Per-criterion score and supporting evidence for a single candidate."""

    criterion_id: str = Field(description="Criterion ID matching the rubric (e.g., M1, N1)")
    criterion_name: str = Field(description="Criterion name matching the rubric")
    category: Literal["must_have", "nice_to_have"] = Field(
        description="Criterion category (must_have or nice_to_have)"
    )
    weight: float = Field(description="Criterion weight from the rubric")
    score: int = Field(
        ge=0,
        le=5,
        description="Score from 0 (no evidence) to 5 (strong, direct evidence)",
    )
    evidence: str = Field(
        description="Verbatim quote or specific reference from the application supporting the score"
    )


class CandidateEvaluation(BaseModel):
    """Structured screening output for an anonymised candidate application."""

    candidate_id: str = Field(description="Anonymous candidate ID (e.g., C001)")
    criterion_scores: list[CriterionScore] = Field(
        description="Per-criterion score (0-5) with an evidence quote or reference"
    )
    overall_score: float = Field(
        ge=0.0,
        le=100.0,
        description="Weighted overall score (0-100) computed from the rubric weights",
    )
    decision: Literal["Shortlisted", "Not Shortlisted"] = Field(
        description="Screening recommendation: Shortlisted or Not Shortlisted"
    )
    confidence: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="How sure the model is of the decision (0.0 to 1.0), based on the evidence",
    )
    review_reasons: list[ReviewReason] = Field(
        default_factory=list,
        description=(
            "Short reasons requiring HR review, empty if none. Allowed values: "
            "borderline_score, missing_evidence, conflicting_evidence, "
            "unreadable_document, low_confidence"
        ),
    )
    strengths: list[str] = Field(
        description="Top job-relevant strengths demonstrated in the application"
    )
    gaps: list[str] = Field(
        description="Gaps or unverified criteria relative to the rubric"
    )
    reasoning: str = Field(
        description="Short reasoning explaining the score and decision (max 3 sentences)"
    )
    needs_human_review: bool = Field(
        default=False,
        description="True if review_reasons is not empty (candidate requires HR decision)",
    )

    @model_validator(mode="after")
    def _sync_review_flags(self) -> CandidateEvaluation:
        reasons: list[ReviewReason] = []
        for r in self.review_reasons:
            if r in ALLOWED_REVIEW_REASONS and r not in reasons:
                reasons.append(r)
        if self.confidence < 0.6 and "low_confidence" not in reasons:
            reasons.append("low_confidence")
        self.review_reasons = reasons
        self.needs_human_review = len(self.review_reasons) > 0
        return self
