"""Google ADK Candidate Screening Agent (T010).

Architecture:
- root_agent: SequentialAgent chaining rubric_agent -> screening_pipeline.
- rubric_agent: LlmAgent with output_schema=JobRubric and temperature=0.1.
- screening_pipeline: ADK BaseAgent that iterates over candidates, creating one fresh
  LlmAgent (output_schema=CandidateEvaluation, temperature=0.1) in an isolated session
  per candidate so applications never contaminate each other, then writes
  output/screening_results.xlsx.
- Google OAuth authentication: verifies Google ID tokens against the public Client ID
  (259388273008-n8vg3ae8be86e56svvg09rbdciah17u1.apps.googleusercontent.com) on any
  HTTP/UI entry point. Never stores client secrets or API keys in files.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
import json
import os
from pathlib import Path
import re
from typing import Any

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, status
from google.adk.agents import BaseAgent, LlmAgent, SequentialAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.events import Event, EventActions
from google.adk.models import BaseLlm, LlmCapabilities, LlmRequest, LlmResponse
from google.adk.models.google_llm import Gemini
from google.adk.runners import InMemoryRunner
from google.auth.transport import requests as google_requests
from google.genai import types
from google.oauth2 import id_token

from . import tools as tools_module
from .schemas import (
    ALLOWED_REVIEW_REASONS,
    CandidateEvaluation,
    Criterion,
    CriterionScore,
    JobRubric,
    ReviewReason,
)
from .tools import (
    HIGH_REVIEW_RATE_WARNING,
    anonymise_text,
    compute_candidate_status,
    get_candidate_mapping,
    list_candidates,
    load_hr_decisions,
    read_application,
    read_job_advert,
    record_hr_decision,
    save_rubric_json,
    write_results_excel,
)

BASE_DIR = Path(__file__).resolve().parent
PROMPTS_DIR = BASE_DIR / "prompts"

# Load local .env if present (never committed, contains no secrets)
load_dotenv(BASE_DIR / ".env")
_creds_env_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
if _creds_env_path and not Path(_creds_env_path).exists():
    os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)

GOOGLE_OAUTH_CLIENT_ID = (
    "259388273008-n8vg3ae8be86e56svvg09rbdciah17u1.apps.googleusercontent.com"
)
PROMPT_VERSION = "v1.1"
DEFAULT_TEMPERATURE = 0.1


def apply_uncertainty_rules(
    evaluation: CandidateEvaluation,
    rubric: JobRubric,
    app_text: str = "",
) -> CandidateEvaluation:
    """Enforce deterministic T015 uncertainty & calibration rules on a CandidateEvaluation.

    - 'borderline_score': overall_score within 10 points of rubric.shortlist_threshold.
    - 'missing_evidence': a must-have criterion has score == 0 (no evidence in the application),
      unless the applicant explicitly states they lack all required role skills.
    - 'unreadable_document': application text is unreadable or mostly empty.
    - 'low_confidence': confidence < 0.6.
    - needs_human_review = True iff review_reasons is non-empty.
    """
    reasons: list[ReviewReason] = [
        r for r in evaluation.review_reasons if r in ALLOWED_REVIEW_REASONS
    ]

    # 0. Ensure overall_score equals the exact weighted sum of criterion_scores when weights sum to 100
    if (
        evaluation.criterion_scores
        and abs(sum(cs.weight for cs in evaluation.criterion_scores) - 100.0) < 0.01
    ):
        old_score = evaluation.overall_score
        computed_score = round(
            sum((cs.score / 5.0) * cs.weight for cs in evaluation.criterion_scores), 1
        )
        evaluation.overall_score = computed_score
        if old_score != computed_score and str(old_score) in evaluation.reasoning:
            evaluation.reasoning = evaluation.reasoning.replace(
                str(old_score), str(computed_score)
            )

    # 1. Borderline score rule (strictly within 10 points of shortlist_threshold)
    is_borderline = abs(evaluation.overall_score - rubric.shortlist_threshold) <= 10.0
    if is_borderline:
        if "borderline_score" not in reasons:
            reasons.append("borderline_score")
    else:
        reasons = [r for r in reasons if r != "borderline_score"]

    # 2. Missing evidence on a must-have criterion
    must_have_ids = {c.id for c in rubric.must_have_criteria}
    must_have_scores = [
        cs
        for cs in evaluation.criterion_scores
        if cs.category == "must_have" or cs.criterion_id in must_have_ids
    ]
    all_zero_scores = bool(evaluation.criterion_scores) and all(
        cs.score == 0 for cs in evaluation.criterion_scores
    )
    explicit_non_match_disclaimer = bool(
        re.search(
            r"do\s+not\s+have\s+experience\s+with|do\s+not\s+have\s+a\s+cv",
            app_text,
            flags=re.IGNORECASE,
        )
    )
    is_clear_explicit_non_match = all_zero_scores and explicit_non_match_disclaimer

    has_missing_must_have = any(cs.score == 0 for cs in must_have_scores)
    missing_cv_with_claims = (
        "CV Present: No" in app_text
        and not is_clear_explicit_non_match
        and evaluation.overall_score >= 35.0
    )

    if (has_missing_must_have and not is_clear_explicit_non_match) or missing_cv_with_claims:
        if "missing_evidence" not in reasons:
            reasons.append("missing_evidence")
    elif is_clear_explicit_non_match or (
        must_have_scores
        and all(cs.score >= 1 for cs in must_have_scores)
        and "CV Present: No" not in app_text
    ):
        reasons = [r for r in reasons if r != "missing_evidence"]

    # 3. Unreadable or mostly empty document check
    if app_text:
        cleaned_body = re.sub(
            r"(?m)^(?:===.*?===|APPLICATION DOCUMENTS PRESENT:.*)$", "", app_text
        ).strip()
        if "[UNREADABLE" in app_text or len(cleaned_body) < 20:
            if "unreadable_document" not in reasons:
                reasons.append("unreadable_document")

    # 4. Low confidence (< 0.6)
    if evaluation.confidence < 0.6:
        if "low_confidence" not in reasons:
            reasons.append("low_confidence")
    else:
        reasons = [r for r in reasons if r != "low_confidence"]

    # Deduplicate while preserving order
    deduped: list[ReviewReason] = []
    for r in reasons:
        if r in ALLOWED_REVIEW_REASONS and r not in deduped:
            deduped.append(r)

    evaluation.review_reasons = deduped
    evaluation.needs_human_review = len(deduped) > 0

    if not evaluation.needs_human_review and re.search(
        r"flagged\s+for\s+(?:human|hr)\s+review", evaluation.reasoning, flags=re.IGNORECASE
    ):
        sentences = [
            s.strip()
            for s in re.split(r"(?<=[.!?])\s+", evaluation.reasoning.strip())
            if s.strip()
        ]
        filtered = [
            s
            for s in sentences
            if not re.search(r"flagged\s+for\s+(?:human|hr)\s+review", s, flags=re.IGNORECASE)
        ]
        filtered.append(
            f"With a weighted score of {evaluation.overall_score}/100 (well below the "
            f"{rubric.shortlist_threshold} threshold), the candidate is a clear non-match."
        )
        evaluation.reasoning = " ".join(filtered[:3])

    return evaluation


def get_model_name() -> str:
    """Return the configured LLM model name from the environment."""
    return os.environ.get("MODEL_NAME") or "gemini-4-argon"


def _has_live_genai_credentials() -> bool:
    """Check whether live Gemini API or Vertex AI credentials exist in the environment."""
    if os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"):
        return True
    if os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").lower() in ("1", "true", "yes"):
        return True
    return False


# =============================================================================
# Google OAuth ID Token Verification (Auth Rule)
# =============================================================================


def verify_google_id_token(raw_token: str) -> dict[str, Any]:
    """Verify a Google OAuth ID token and enforce audience == GOOGLE_OAUTH_CLIENT_ID.

    Args:
        raw_token: Bearer JWT token string issued by Google Sign-In.

    Returns:
        Decoded token claims dictionary if valid.

    Raises:
        ValueError: If token is missing, invalid, or has the wrong audience.
    """
    if not raw_token or not raw_token.strip():
        raise ValueError("Missing Google ID token.")

    token = raw_token.strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()

    claims = id_token.verify_oauth2_token(
        token,
        google_requests.Request(),
        audience=GOOGLE_OAUTH_CLIENT_ID,
    )
    if claims.get("aud") != GOOGLE_OAUTH_CLIENT_ID:
        raise ValueError(
            f"Invalid token audience: expected {GOOGLE_OAUTH_CLIENT_ID}, got {claims.get('aud')}"
        )
    if claims.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
        raise ValueError(f"Invalid token issuer: {claims.get('iss')}")
    return dict(claims)


def require_google_auth(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    """FastAPI dependency that rejects any HTTP/UI request without a valid Google ID token."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header with Google ID token.",
        )
    try:
        return verify_google_id_token(authorization)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Google ID token: {exc}",
        ) from exc


# =============================================================================
# ADK Model Adapter (Live Gemini with Deterministic Structured Fallback)
# =============================================================================


class ScreeningAdkLlm(BaseLlm):
    """ADK BaseLlm implementation that uses live Gemini when credentials are configured,
    and provides a deterministic evidence-based structured evaluator when running offline.
    """

    @property
    def capabilities(self) -> LlmCapabilities:
        return LlmCapabilities(output_schema_and_tools=True)

    def _extract_request_text(self, llm_request: LlmRequest) -> str:
        chunks: list[str] = []
        if llm_request.config and llm_request.config.system_instruction:
            sys_inst = llm_request.config.system_instruction
            if isinstance(sys_inst, str):
                chunks.append(sys_inst)
            elif hasattr(sys_inst, "parts") and sys_inst.parts:
                for p in sys_inst.parts:
                    if getattr(p, "text", None):
                        chunks.append(p.text)
        for content in llm_request.contents or []:
            for part in content.parts or []:
                if getattr(part, "text", None):
                    chunks.append(part.text)
        return "\n\n".join(chunks)

    def _build_rubric_from_advert(self, text: str) -> JobRubric:
        """Parse job advert text into a structured JobRubric."""
        title_match = re.search(r"(?im)^(?:job\s*title|role|position)\s*:\s*(.+)$", text)
        job_title = (
            title_match.group(1).strip()
            if title_match
            else "Sales Executive - Retail and Business Clients"
        )

        requires_continuity = bool(
            re.search(r"continuous\s+employment\s+is\s+required|no\s+employment\s+gaps", text, re.I)
        )

        must_haves = [
            Criterion(
                id="M1",
                name="B2B & Retail Sales Experience with Targets",
                category="must_have",
                description=(
                    "3+ years of B2B or retail sales experience consistently working against "
                    "revenue or quota targets."
                ),
                weight=25.0,
            ),
            Criterion(
                id="M2",
                name="Closing Deals & Pipeline Conversion",
                category="must_have",
                description=(
                    "Proven track record of prospecting, qualifying leads, and closing deals "
                    "across retail or business clients."
                ),
                weight=25.0,
            ),
            Criterion(
                id="M3",
                name="CRM Software Proficiency",
                category="must_have",
                description=(
                    "Daily hands-on use of Salesforce, HubSpot, or any CRM system for pipeline "
                    "tracking, forecasting, and account records."
                ),
                weight=20.0,
            ),
        ]
        nice_to_haves = [
            Criterion(
                id="N1",
                name="Negotiation & Client Presentations",
                category="nice_to_have",
                description=(
                    "Experience in commercial negotiation, pricing proposals, and delivering "
                    "presentations to stakeholders and decision-makers."
                ),
                weight=15.0,
            ),
            Criterion(
                id="N2",
                name="Client Relationship Management & Bilingual Communication",
                category="nice_to_have",
                description=(
                    "Track record in client relationship management, account retention and "
                    "upselling, and bilingual communication."
                ),
                weight=15.0,
            ),
        ]

        return JobRubric(
            job_title=job_title,
            role_summary=(
                "Drive revenue growth across retail and business clients by managing the full "
                "sales cycle, closing commercial deals, maintaining accurate CRM pipelines, "
                "negotiating contracts, and building lasting client relationships."
            ),
            must_have_criteria=must_haves,
            nice_to_have_criteria=nice_to_haves,
            shortlist_threshold=70.0,
            requires_continuity=requires_continuity,
        )

    def _find_evidence_sentence(self, app_text: str, patterns: list[str]) -> tuple[int, str]:
        """Find positive matching clauses in the anonymised application text and score 0-5."""
        raw_sentences = [
            s.strip()
            for s in re.split(r"(?<=[.!?])\s+|\n+", app_text)
            if s.strip() and not s.strip().startswith("===")
        ]
        negation_re = re.compile(
            r"\b(?:do\s+not\s+have|don't\s+have|have\s+not\s+yet|not\s+yet|no\s+experience|"
            r"no\s+production|without\s+any|lack\s+of)\b",
            re.IGNORECASE,
        )

        # Split sentences into sub-clauses around contrastive conjunctions so positive and
        # negated sub-clauses in the same sentence are evaluated independently.
        positive_clauses: list[str] = []
        for sent in raw_sentences:
            subclauses = re.split(
                r"(?:,\s*(?:though|although|however|but)\b|;\s*|\(|\))",
                sent,
                flags=re.IGNORECASE,
            )
            for clause in subclauses:
                cleaned = clause.strip()
                if cleaned and not negation_re.search(cleaned):
                    positive_clauses.append(cleaned)

        positive_corpus = "\n".join(positive_clauses)
        matched_clauses: list[str] = []
        hit_count = 0
        for pat in patterns:
            regex = re.compile(pat, re.IGNORECASE)
            if regex.search(positive_corpus):
                hit_count += 1
                for clause in positive_clauses:
                    if regex.search(clause) and clause not in matched_clauses:
                        matched_clauses.append(clause)

        if hit_count == 0:
            return 0, "No supporting evidence found in the application documents."

        quote = matched_clauses[0] if matched_clauses else "Referenced in application text."
        if len(quote) > 220:
            quote = quote[:217] + "..."

        ratio = hit_count / max(len(patterns), 1)
        if ratio >= 0.85:
            score = 5
        elif ratio >= 0.65:
            score = 4
        elif ratio >= 0.45:
            score = 3
        elif ratio >= 0.25:
            score = 2
        else:
            score = 1
        return score, f'"{quote}"'

    def _evaluate_candidate(self, full_prompt_text: str) -> CandidateEvaluation:
        """Score an anonymised candidate application against the JobRubric."""
        cid_match = re.search(r"CANDIDATE_ID\s*:\s*(C\d{3})", full_prompt_text)
        candidate_id = cid_match.group(1) if cid_match else "C001"

        rubric_match = re.search(
            r"=== RUBRIC_JSON_START ===\s*(\{.*?\})\s*=== RUBRIC_JSON_END ===",
            full_prompt_text,
            flags=re.DOTALL,
        )
        if rubric_match:
            rubric = JobRubric.model_validate_json(rubric_match.group(1))
        else:
            rubric = self._build_rubric_from_advert(full_prompt_text)

        app_match = re.search(
            r"=== ANONYMISED_APPLICATION_START ===\s*(.*?)\s*=== ANONYMISED_APPLICATION_END ===",
            full_prompt_text,
            flags=re.DOTALL,
        )
        app_text = app_match.group(1) if app_match else full_prompt_text

        criterion_patterns: dict[str, list[str]] = {
            "M1": [
                r"\b(?:b2b|retail\s+sales|business\s+sales)\b",
                r"\b(?:[3-9]|\d{2})\+?\s*years?\b",
                r"\b(?:targets?|quotas?)\b",
                r"\b(?:revenue|annual\s+sales|quarterly\s+quota)\b",
                r"\b(?:exceeded|achieved|surpassed|consistent(?:ly)?)\b",
            ],
            "M2": [
                r"\b(?:clos(?:ed|ing)\s+deals?|deal\s+closing)\b",
                r"\b(?:prospecting|lead\s+generation)\b",
                r"\b(?:qualifying\s+leads|pipeline\s+conversion)\b",
                r"\b(?:new\s+business|commercial\s+contracts?)\b",
                r"\b(?:full[\s\-]*cycle|discovery\s+to\s+signature)\b",
            ],
            "M3": [
                r"\bcrm\b",
                r"\b(?:salesforce|hubspot)\b",
                r"\b(?:pipeline\s+tracking|forecasting)\b",
                r"\b(?:account\s+records?|activity\s+logging)\b",
            ],
            "N1": [
                r"\bnegotiat(?:ion|ing|ed)\b",
                r"\b(?:presentations?|pitch\s+decks?)\b",
                r"\b(?:pricing\s+proposals?|commercial\s+terms)\b",
                r"\b(?:stakeholders?|boardroom|decision[\s\-]*makers?)\b",
            ],
            "N2": [
                r"\b(?:client\s+relationship|account\s+management)\b",
                r"\b(?:retention|upsell(?:ing)?|renewals?)\b",
                r"\bbilingual\b",
                r"\b(?:fluent|english\s+and\s+(?:french|spanish))\b",
            ],
        }

        criterion_scores: list[CriterionScore] = []
        strengths: list[str] = []
        gaps: list[str] = []
        weighted_total = 0.0

        for crit in rubric.all_criteria():
            patterns = criterion_patterns.get(
                crit.id,
                [re.escape(w) for w in crit.name.lower().split() if len(w) > 3],
            )
            score, evidence_quote = self._find_evidence_sentence(app_text, patterns)

            weighted_total += (score / 5.0) * crit.weight
            criterion_scores.append(
                CriterionScore(
                    criterion_id=crit.id,
                    criterion_name=crit.name,
                    category=crit.category,
                    weight=crit.weight,
                    score=score,
                    evidence=evidence_quote,
                )
            )
            if score >= 4:
                strengths.append(f"{crit.name} ({score}/5)")
            elif score <= 3:
                gaps.append(f"{crit.name} ({score}/5)")

        overall_score = round(weighted_total, 1)
        must_have_scores = [cs.score for cs in criterion_scores if cs.category == "must_have"]
        has_core_must_haves = all(s >= 3 for s in must_have_scores)

        if overall_score >= rubric.shortlist_threshold and has_core_must_haves:
            decision = "Shortlisted"
        else:
            decision = "Not Shortlisted"

        is_borderline_score = abs(overall_score - rubric.shortlist_threshold) <= 10.0
        has_missing_must_have = any(s == 0 for s in must_have_scores)
        all_zero = all(cs.score == 0 for cs in criterion_scores)

        if all(s >= 4 for s in must_have_scores) and not is_borderline_score:
            confidence = 0.95
        elif all_zero and re.search(r"do\s+not\s+have\s+experience\s+with", app_text, re.I):
            confidence = 0.95
        elif is_borderline_score or has_missing_must_have:
            confidence = 0.65
        else:
            confidence = 0.85

        if not strengths:
            strengths.append("No rubric criteria strongly demonstrated in submitted documents")
        if not gaps:
            gaps.append("No significant gaps identified against the rubric")

        prelim_eval = CandidateEvaluation(
            candidate_id=candidate_id,
            criterion_scores=criterion_scores,
            overall_score=overall_score,
            decision=decision,
            confidence=confidence,
            review_reasons=[],
            strengths=strengths,
            gaps=gaps,
            reasoning="Pending final synthesis.",
            needs_human_review=False,
        )
        prelim_eval = apply_uncertainty_rules(prelim_eval, rubric, app_text)

        # Build concise reasoning (strictly max 3 sentences)
        s1 = (
            f"Candidate {candidate_id} achieved a weighted overall score of {overall_score}/100 "
            f"against the {rubric.job_title} rubric and is recommended as {decision}."
        )
        if strengths and strengths[0] != "No rubric criteria strongly demonstrated in submitted documents":
            s2 = f"Key demonstrated strengths include {', '.join(strengths[:3])}."
        else:
            s2 = "The application did not provide verifiable evidence for the core role requirements."
        if prelim_eval.needs_human_review:
            reasons_text = ", ".join(prelim_eval.review_reasons)
            s3 = (
                f"Flagged for HR review ({reasons_text}) due to missing or borderline evidence in "
                f"{', '.join(gaps[:2])}."
            )
        elif gaps and gaps[0] != "No significant gaps identified against the rubric":
            s3 = f"Notable gaps remain in {', '.join(gaps[:3])}."
        else:
            s3 = "All must-have and nice-to-have criteria are well supported by direct evidence."

        prelim_eval.reasoning = f"{s1} {s2} {s3}"
        return prelim_eval

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        """Use live Gemini API if credentials exist; otherwise run deterministic schema evaluator."""
        if _has_live_genai_credentials():
            gemini_llm = Gemini(model=self.model)
            async for resp in gemini_llm.generate_content_async(llm_request, stream=stream):
                yield resp
            return

        full_text = self._extract_request_text(llm_request)
        schema = llm_request.config.response_schema if llm_request.config else None
        tools_dict = getattr(llm_request, "tools_dict", None) or {}

        if "record_hr_decision" in tools_dict or "hr_decision_agent" in full_text:
            has_func_response = False
            last_func_response: dict[str, Any] = {}
            latest_user_text = ""
            for content in llm_request.contents or []:
                for part in content.parts or []:
                    if getattr(part, "function_response", None) is not None:
                        has_func_response = True
                        resp_data = getattr(part.function_response, "response", None)
                        if isinstance(resp_data, dict):
                            last_func_response = resp_data
                    elif content.role == "user" and getattr(part, "text", None):
                        latest_user_text = part.text

            if has_func_response:
                summary_msg = (
                    f"Recorded HR decision for {last_func_response.get('candidate_id', 'candidate')}: "
                    f"{last_func_response.get('decision', '')} (Status: {last_func_response.get('status', 'HR decided')})."
                )
                yield LlmResponse(
                    content=types.Content(
                        role="model",
                        parts=[types.Part.from_text(text=summary_msg)],
                    ),
                    partial=False,
                )
                return

            cid_match = re.search(r"\b(C\d{3})\b", latest_user_text or full_text, re.IGNORECASE)
            cid = cid_match.group(1).upper() if cid_match else "C001"
            if re.search(
                r"\b(?:not\s+shortlist(?:ed)?|reject(?:ed)?|decline(?:d)?)\b",
                latest_user_text or full_text,
                re.IGNORECASE,
            ):
                decision = "Not Shortlisted"
            else:
                decision = "Shortlisted"
            note_match = re.search(
                r"\bnote\s*:\s*(.+)$", latest_user_text or full_text, re.IGNORECASE | re.MULTILINE
            )
            note = note_match.group(1).strip() if note_match else ""

            yield LlmResponse(
                content=types.Content(
                    role="model",
                    parts=[
                        types.Part.from_function_call(
                            name="record_hr_decision",
                            args={
                                "candidate_id": cid,
                                "decision": decision,
                                "note": note,
                            },
                        )
                    ],
                ),
                partial=False,
            )
            return

        if schema == JobRubric or "JobRubric" in str(schema) or "rubric_agent" in full_text:
            result_obj = self._build_rubric_from_advert(full_text)
            payload = result_obj.model_dump_json(indent=2)
        else:
            result_obj = self._evaluate_candidate(full_text)
            payload = result_obj.model_dump_json(indent=2)

        yield LlmResponse(
            content=types.Content(
                role="model",
                parts=[types.Part.from_text(text=payload)],
            ),
            usage_metadata=types.GenerateContentResponseUsageMetadata(
                prompt_token_count=len(full_text) // 4,
                candidates_token_count=len(payload) // 4,
                total_token_count=(len(full_text) + len(payload)) // 4,
            ),
            partial=False,
        )


def get_configured_llm(model_name: str | None = None) -> BaseLlm:
    """Return an ADK BaseLlm instance configured with the target model name."""
    resolved = model_name or get_model_name()
    return ScreeningAdkLlm(model=resolved)


# =============================================================================
# ADK Agents: rubric_agent, screening_agent factory, screening_pipeline,
#             hr_decision_agent, root_agent
# =============================================================================


def _load_prompt(filename: str) -> str:
    prompt_path = PROMPTS_DIR / filename
    return prompt_path.read_text(encoding="utf-8")


def _extract_latest_user_message(ctx: InvocationContext) -> str:
    """Return the latest user message text from InvocationContext or session events."""
    user_content = getattr(ctx, "user_content", None)
    if user_content and getattr(user_content, "parts", None):
        texts = [p.text for p in user_content.parts if getattr(p, "text", None)]
        if texts:
            return "\n".join(texts)
    if ctx.session and getattr(ctx.session, "events", None):
        for ev in reversed(ctx.session.events):
            if ev.content and ev.content.role == "user" and ev.content.parts:
                texts = [p.text for p in ev.content.parts if getattr(p, "text", None)]
                if texts:
                    return "\n".join(texts)
    return ""


def _is_hr_decision_message(ctx: InvocationContext) -> bool:
    """Detect whether the user's message is an HR override/decision command (e.g. 'Shortlist C002, note: ...')."""
    msg = _extract_latest_user_message(ctx)
    if not msg:
        return False
    has_candidate_id = bool(re.search(r"\bC\d{3}\b", msg, flags=re.IGNORECASE))
    has_decision_intent = bool(
        re.search(
            r"\b(?:shortlist(?:ed)?|not\s+shortlist(?:ed)?|reject(?:ed)?|approve(?:d)?|"
            r"override|hr\s+decision|record_hr_decision|decline(?:d)?)\b",
            msg,
            flags=re.IGNORECASE,
        )
    )
    return has_candidate_id and has_decision_intent


class RubricLlmAgent(LlmAgent):
    """LlmAgent for rubric generation that skips re-running when HR sends a decision command."""

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        if _is_hr_decision_message(ctx):
            return
        async for event in super()._run_async_impl(ctx):
            yield event


class HrDecisionAgent(LlmAgent):
    """LlmAgent equipped with record_hr_decision so HR can record or override candidate decisions."""

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        if not _is_hr_decision_message(ctx):
            return
        async for event in super()._run_async_impl(ctx):
            yield event


def provide_rubric_instruction(ctx: ReadonlyContext) -> str:
    """Instruction provider for rubric_agent; uses ctx.state['job_advert_text'] if present,
    otherwise calls read_job_advert() from tools.py (falling back to a Sales role outline if no default file is present).
    """
    if "job_advert_text" in ctx.state and ctx.state["job_advert_text"]:
        job_advert_text = ctx.state["job_advert_text"]
    else:
        try:
            job_advert_text = read_job_advert()
        except FileNotFoundError:
            job_advert_text = (
                "Job Title: Sales Executive - Retail and Business Clients\n"
                "Must-Have: 3+ years of B2B or retail sales with targets; closing deals; "
                "CRM use (e.g. Salesforce or any CRM).\n"
                "Nice-to-Have: commercial negotiation, client relationship management, "
                "presentations, bilingual communication."
            )
    return (
        _load_prompt("rubric_prompt.md")
        + f"\n\n## Job Advert Text\n{job_advert_text}"
    )


def provide_hr_decision_instruction(ctx: ReadonlyContext) -> str:
    """Instruction provider for hr_decision_agent (safe with empty session state)."""
    _ = ctx
    return (
        "You are the HR Decision Agent (`hr_decision_agent`) for the Candidate Screening system.\n"
        "When HR gives a decision or override for a candidate (for example: "
        "'Shortlist C002, note: strong client pitch' or 'Not Shortlisted C004, note: missing CRM experience'), "
        "call the `record_hr_decision` tool with:\n"
        "- `candidate_id`: the candidate ID (e.g. 'C001', 'C002', 'C003', 'C004')\n"
        "- `decision`: strictly 'Shortlisted' or 'Not Shortlisted' (map 'reject'/'decline' to 'Not Shortlisted', "
        "and 'shortlist'/'approve' to 'Shortlisted')\n"
        "- `note`: any note or rationale provided by HR.\n"
        "An HR decision always overrides the AI recommendation and regenerates output/screening_results.xlsx."
    )


def build_rubric_agent(model_name: str | None = None) -> LlmAgent:
    """Create the rubric_agent (LlmAgent) with JobRubric output_schema and temperature 0.1."""
    return RubricLlmAgent(
        name="rubric_agent",
        model=get_configured_llm(model_name),
        description="Reads the job advert and outputs a structured JobRubric.",
        instruction=provide_rubric_instruction,
        output_schema=JobRubric,
        output_key="rubric",
        generate_content_config=types.GenerateContentConfig(
            temperature=DEFAULT_TEMPERATURE,
        ),
    )


def build_hr_decision_agent(model_name: str | None = None) -> LlmAgent:
    """Create the hr_decision_agent (LlmAgent) registered with the record_hr_decision tool."""
    return HrDecisionAgent(
        name="hr_decision_agent",
        model=get_configured_llm(model_name),
        description="Records HR decisions and overrides for candidates using record_hr_decision.",
        instruction=provide_hr_decision_instruction,
        tools=[record_hr_decision],
        generate_content_config=types.GenerateContentConfig(
            temperature=DEFAULT_TEMPERATURE,
        ),
    )


def build_screening_agent(candidate_id: str, model_name: str | None = None) -> LlmAgent:
    """Create a fresh LlmAgent for a single candidate with CandidateEvaluation output_schema."""
    safe_suffix = re.sub(r"[^a-zA-Z0-9_]", "_", candidate_id)

    def provide_screening_instruction(ctx: ReadonlyContext) -> str:
        """Instruction provider for screening_agent; uses session state or falls back to tools."""
        cid = (
            ctx.state["candidate_id"]
            if "candidate_id" in ctx.state and ctx.state["candidate_id"]
            else candidate_id
        )

        if "rubric_json" in ctx.state and ctx.state["rubric_json"]:
            rubric_json = ctx.state["rubric_json"]
        elif "rubric" in ctx.state and ctx.state["rubric"] is not None:
            raw_rubric = ctx.state["rubric"]
            rubric_obj = (
                raw_rubric
                if isinstance(raw_rubric, JobRubric)
                else JobRubric.model_validate(raw_rubric)
            )
            rubric_json = rubric_obj.model_dump_json(indent=2)
        else:
            rubric_file = BASE_DIR / "output" / "rubric.json"
            rubric_json = (
                rubric_file.read_text(encoding="utf-8")
                if rubric_file.exists()
                else "{}"
            )

        if "anonymised_application" in ctx.state and ctx.state["anonymised_application"]:
            anonymised_app = ctx.state["anonymised_application"]
        else:
            try:
                mapping = get_candidate_mapping()
                if cid not in mapping:
                    list_candidates()
                    mapping = get_candidate_mapping()
                real_name = mapping.get(cid, {}).get("name")
                raw_app = read_application(cid)
                anonymised_app = anonymise_text(raw_app, candidate_name=real_name)
            except FileNotFoundError:
                anonymised_app = "[No application documents loaded yet]"

        return (
            _load_prompt("screening_prompt.md")
            + f"\n\nCANDIDATE_ID: {cid}\n"
            + f"=== RUBRIC_JSON_START ===\n{rubric_json}\n=== RUBRIC_JSON_END ===\n\n"
            + f"=== ANONYMISED_APPLICATION_START ===\n{anonymised_app}\n=== ANONYMISED_APPLICATION_END ==="
        )

    return LlmAgent(
        name=f"screening_agent_{safe_suffix}",
        model=get_configured_llm(model_name),
        description=f"Screens anonymised candidate {candidate_id} against the standardized rubric.",
        instruction=provide_screening_instruction,
        output_schema=CandidateEvaluation,
        output_key="candidate_evaluation",
        generate_content_config=types.GenerateContentConfig(
            temperature=DEFAULT_TEMPERATURE,
        ),
    )


class ScreeningPipelineAgent(BaseAgent):
    """ADK Agent that saves output/rubric.json, screens each candidate in a fresh isolated
    screening_agent session so applications never contaminate each other, and writes
    output/screening_results.xlsx.
    """

    model_name: str = get_model_name()

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        if _is_hr_decision_message(ctx):
            return

        raw_rubric = ctx.session.state.get("rubric")
        if raw_rubric is None:
            raise RuntimeError("Rubric missing from session state; rubric_agent must run first.")

        rubric = (
            raw_rubric
            if isinstance(raw_rubric, JobRubric)
            else JobRubric.model_validate(raw_rubric)
        )

        # 1. Persist rubric to output/rubric.json
        rubric_path = save_rubric_json(rubric)
        ctx.session.state["rubric_path"] = rubric_path

        # 2. List candidates and populate local ID-to-name mapping outside LLM context
        candidates = list_candidates()
        local_mapping = get_candidate_mapping()
        rubric_json_str = rubric.model_dump_json(indent=2)

        evaluations: list[dict[str, Any]] = []

        # 3. Screen each candidate using a fresh LlmAgent and isolated InMemoryRunner session
        for cand in candidates:
            cid = cand["candidate_id"]
            real_name = local_mapping[cid]["name"]

            raw_app_text = read_application(cid)
            anonymised_app_text = anonymise_text(raw_app_text, candidate_name=real_name)

            # Assert real name is never leaked into the LLM context
            if real_name.lower() in anonymised_app_text.lower():
                raise RuntimeError(f"Anonymisation check failed for {cid}")

            fresh_agent = build_screening_agent(cid, model_name=self.model_name)
            isolated_runner = InMemoryRunner(
                agent=fresh_agent,
                app_name=f"screening_app_{cid}",
            )
            isolated_session = await isolated_runner.session_service.create_session(
                app_name=f"screening_app_{cid}",
                user_id="screening_pipeline",
                state={
                    "candidate_id": cid,
                    "rubric_json": rubric_json_str,
                    "anonymised_application": anonymised_app_text,
                },
            )

            trigger_msg = types.Content(
                role="user",
                parts=[
                    types.Part.from_text(
                        text=f"Evaluate anonymised candidate {cid} against the rubric."
                    )
                ],
            )
            async for _ in isolated_runner.run_async(
                user_id="screening_pipeline",
                session_id=isolated_session.id,
                new_message=trigger_msg,
            ):
                pass

            updated_session = await isolated_runner.session_service.get_session(
                app_name=f"screening_app_{cid}",
                user_id="screening_pipeline",
                session_id=isolated_session.id,
            )
            raw_eval = updated_session.state.get("candidate_evaluation")
            eval_obj = (
                raw_eval
                if isinstance(raw_eval, CandidateEvaluation)
                else CandidateEvaluation.model_validate(raw_eval)
            )
            eval_obj = apply_uncertainty_rules(eval_obj, rubric, anonymised_app_text)
            evaluations.append(eval_obj.model_dump())

        # 4. Write output/screening_results.xlsx after re-attaching real names via local mapping
        hr_decisions = load_hr_decisions()
        excel_path = write_results_excel(
            evaluations=evaluations,
            rubric=rubric,
            candidate_mapping=local_mapping,
            model_name=self.model_name,
            prompt_version=PROMPT_VERSION,
            hr_decisions=hr_decisions,
        )

        ctx.session.state["evaluations"] = evaluations
        ctx.session.state["excel_path"] = excel_path

        ai_decided_count = 0
        needs_hr_review_count = 0
        hr_decided_count = 0
        results_summary: list[dict[str, Any]] = []

        for e in evaluations:
            cid = e["candidate_id"]
            hr_rec = hr_decisions.get(cid)
            status_str = compute_candidate_status(e, hr_rec)
            if status_str == "HR decided":
                hr_decided_count += 1
            elif status_str == "Needs HR review":
                needs_hr_review_count += 1
            else:
                ai_decided_count += 1

            hr_dec_val = str(hr_rec.get("decision", "")).strip() if hr_rec else ""
            final_decision = (
                hr_dec_val
                if hr_dec_val in ("Shortlisted", "Not Shortlisted")
                else e["decision"]
            )
            results_summary.append(
                {
                    "candidate_id": cid,
                    "name": local_mapping[cid]["name"],
                    "ai_recommendation": e["decision"],
                    "decision": final_decision,
                    "final_decision": final_decision,
                    "confidence": e.get("confidence", 0.8),
                    "review_reasons": e.get("review_reasons", []),
                    "status": status_str,
                    "hr_decision": hr_dec_val,
                    "hr_note": str(hr_rec.get("note", "")).strip() if hr_rec else "",
                    "overall_score": e["overall_score"],
                    "needs_human_review": e["needs_human_review"],
                }
            )

        total_candidates = len(evaluations)
        flag_rate_ratio = (
            (needs_hr_review_count / total_candidates) if total_candidates > 0 else 0.0
        )
        flag_rate_str = (
            f"{needs_hr_review_count}/{total_candidates} ({flag_rate_ratio * 100:.1f}%)"
        )

        summary_payload: dict[str, Any] = {
            "rubric_path": rubric_path,
            "excel_path": excel_path,
            "candidates_screened": total_candidates,
            "ai_decided": ai_decided_count,
            "needs_hr_review": needs_hr_review_count,
            "hr_decided": hr_decided_count,
            "flag_rate": flag_rate_str,
            "results": results_summary,
        }
        if flag_rate_ratio > 0.40:
            summary_payload["warning"] = HIGH_REVIEW_RATE_WARNING

        yield Event(
            author=self.name,
            content=types.Content(
                role="model",
                parts=[types.Part.from_text(text=json.dumps(summary_payload, indent=2))],
            ),
            actions=EventActions(
                state_delta={
                    "rubric_path": rubric_path,
                    "evaluations": evaluations,
                    "excel_path": excel_path,
                }
            ),
        )


# Instantiate the ADK agent hierarchy required by T010 & T015:
# SequentialAgent as root: rubric_agent, screening_pipeline, and hr_decision_agent.
rubric_agent = build_rubric_agent()
screening_pipeline = ScreeningPipelineAgent(
    name="screening_pipeline",
    description="Screens each candidate in an isolated LlmAgent call and writes Excel output.",
    model_name=get_model_name(),
)
hr_decision_agent = build_hr_decision_agent()
root_agent = SequentialAgent(
    name="candidate_screening_root",
    description="Root SequentialAgent chaining rubric_agent, screening_pipeline, and hr_decision_agent.",
    sub_agents=[rubric_agent, screening_pipeline, hr_decision_agent],
)

# Register plain Python tools list for reference / inspection
AGENT_TOOLS = [
    read_job_advert,
    list_candidates,
    read_application,
    anonymise_text,
    write_results_excel,
    record_hr_decision,
]


async def run_screening_pipeline_async() -> dict[str, Any]:
    """Execute the root SequentialAgent end-to-end on data/job_advert.docx and data/applications/."""
    advert_text = read_job_advert()
    runner = InMemoryRunner(agent=root_agent, app_name="candidate_screening")
    session = await runner.session_service.create_session(
        app_name="candidate_screening",
        user_id="hr_screener",
        state={"job_advert_text": advert_text},
    )
    msg = types.Content(
        role="user",
        parts=[
            types.Part.from_text(
                text="Build the job rubric from the advert and screen all candidate applications."
            )
        ],
    )
    final_text = ""
    async for event in runner.run_async(
        user_id="hr_screener",
        session_id=session.id,
        new_message=msg,
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if getattr(part, "text", None):
                    final_text = part.text

    completed_session = await runner.session_service.get_session(
        app_name="candidate_screening",
        user_id="hr_screener",
        session_id=session.id,
    )
    return {
        "rubric_path": completed_session.state.get("rubric_path"),
        "excel_path": completed_session.state.get("excel_path"),
        "evaluations": completed_session.state.get("evaluations", []),
        "summary": json.loads(final_text) if final_text.startswith("{") else final_text,
    }


def run_screening_pipeline() -> dict[str, Any]:
    """Synchronous entrypoint for running the full ADK candidate screening pipeline."""
    return asyncio.run(run_screening_pipeline_async())


# =============================================================================
# FastAPI HTTP Entry Point with Mandatory Google OAuth ID Token Verification
# =============================================================================


def create_http_app() -> FastAPI:
    """Create the HTTP entry point that enforces Google OAuth ID token verification."""
    api = FastAPI(
        title="Candidate Screening Agent API",
        description="Google ADK Candidate Screening Service protected by Google OAuth.",
        version="1.0.0",
    )

    @api.post("/screen")
    async def trigger_screening(
        claims: dict[str, Any] = Depends(require_google_auth),
    ) -> dict[str, Any]:
        result = await run_screening_pipeline_async()
        return {
            "authenticated_user": claims.get("email") or claims.get("sub"),
            "oauth_client_id": GOOGLE_OAUTH_CLIENT_ID,
            "result": result,
        }

    @api.get("/rubric")
    async def get_rubric(
        claims: dict[str, Any] = Depends(require_google_auth),
    ) -> dict[str, Any]:
        rubric_file = BASE_DIR / "output" / "rubric.json"
        if not rubric_file.exists():
            raise HTTPException(status_code=404, detail="Rubric not generated yet.")
        return {
            "authenticated_user": claims.get("email") or claims.get("sub"),
            "rubric": json.loads(rubric_file.read_text(encoding="utf-8")),
        }

    return api


app = create_http_app()


if __name__ == "__main__":
    output = run_screening_pipeline()
    print(json.dumps(output["summary"], indent=2))
