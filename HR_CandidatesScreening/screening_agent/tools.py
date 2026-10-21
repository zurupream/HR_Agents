"""Plain Python tools for the Candidate Screening Agent (T010)."""

from __future__ import annotations

from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
import json
import os
from pathlib import Path
import re
from typing import Any

from docx import Document
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from pypdf import PdfReader

from .schemas import CandidateEvaluation, JobRubric

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
DEFAULT_ADVERT_PATH = DATA_DIR / "job_advert.docx"
DEFAULT_APPLICATIONS_DIR = DATA_DIR / "applications"
DEFAULT_RUBRIC_PATH = OUTPUT_DIR / "rubric.json"
DEFAULT_EXCEL_PATH = OUTPUT_DIR / "screening_results.xlsx"
DEFAULT_HR_DECISIONS_PATH = OUTPUT_DIR / "hr_decisions.json"
DEFAULT_EVALUATIONS_PATH = OUTPUT_DIR / "evaluations.json"

HIGH_REVIEW_RATE_WARNING = "High review rate: the rubric or prompt may need tuning."

# Local ID-to-name mapping kept strictly outside the LLM context.
_CANDIDATE_MAPPING: dict[str, dict[str, str]] = {}

# Cached state from the most recent screening run so record_hr_decision can regenerate Excel.
_LAST_EVALUATIONS: list[CandidateEvaluation] = []
_LAST_RUBRIC: JobRubric | None = None
_LAST_CANDIDATE_MAPPING: dict[str, dict[str, str]] = {}
_LAST_EXCEL_PATH: Path | None = None
_LAST_MODEL_NAME: str | None = None
_LAST_PROMPT_VERSION: str = "v1.1"


def get_candidate_mapping() -> dict[str, dict[str, str]]:
    """Return a copy of the local anonymous-ID-to-candidate mapping."""
    return dict(_CANDIDATE_MAPPING)


def read_job_advert(advert_path: str | None = None) -> str:
    """Extract full text from the job advert Word document (.docx) using python-docx.

    Args:
        advert_path: Optional path to the job description file (.docx, .pdf, or .txt).

    Returns:
        Extracted plain text from the job description document.
    """
    path = Path(advert_path) if advert_path else DEFAULT_ADVERT_PATH
    if not path.exists():
        raise FileNotFoundError(f"Job advert not found at: {path}")

    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _extract_pdf_text(path)
    if suffix in (".txt", ".md"):
        return path.read_text(encoding="utf-8", errors="replace").strip()
    return _extract_docx_text(path)


def _extract_docx_text(file_path: Path) -> str:
    """Extract text from a .docx file."""
    doc = Document(str(file_path))
    lines: list[str] = []
    for para in doc.paragraphs:
        if para.text.strip():
            lines.append(para.text.strip())
    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                lines.append(" | ".join(cells))
    return "\n".join(lines)


def _extract_pdf_text(file_path: Path) -> str:
    """Extract full text from all pages of a .pdf file using pypdf."""
    reader = PdfReader(str(file_path))
    pages: list[str] = []
    for idx, page in enumerate(reader.pages, start=1):
        page_text = page.extract_text() or ""
        if page_text.strip():
            pages.append(f"[Page {idx}]\n{page_text.strip()}")
    return "\n\n".join(pages)


def _extract_eml_text(file_path: Path) -> str:
    """Extract subject and body text from an .eml file."""
    raw_bytes = file_path.read_bytes()
    msg = BytesParser(policy=policy.default).parsebytes(raw_bytes)
    parts: list[str] = []
    subject = msg.get("Subject")
    if subject:
        parts.append(f"Subject: {subject}")

    body_part = msg.get_body(preferencelist=("plain", "html"))
    if body_part is not None:
        content = body_part.get_content()
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="replace")
        parts.append(str(content).strip())
    else:
        payload = msg.get_payload(decode=True)
        if isinstance(payload, bytes):
            parts.append(payload.decode("utf-8", errors="replace").strip())
        else:
            parts.append(raw_bytes.decode("utf-8", errors="replace").strip())

    return "\n\n".join(p for p in parts if p)


SUPPORTED_DOC_EXTENSIONS = {".docx", ".pdf", ".eml", ".txt"}


def _is_complementary_doc(file_path: Path) -> bool:
    """Return True if a file is a cover letter or email rather than a standalone CV/resume."""
    lower_name = file_path.name.lower()
    suffix = file_path.suffix.lower()
    return "cover" in lower_name or "email" in lower_name or suffix == ".eml"


def _resolve_candidate_entries(app_dir: Path) -> list[dict[str, str]]:
    """Resolve candidate entries from an applications directory.

    Supports both:
    - Per-candidate subfolders (containing complementary files such as CV + Cover Letter + Email)
    - Flat directories or batch subfolders where multiple standalone resume files sit in one folder
      (1 resume file = 1 candidate).
    """
    entries: list[dict[str, str]] = []
    items = sorted(app_dir.iterdir(), key=lambda p: p.name.lower())

    for item in items:
        if item.is_dir():
            sub_files = sorted(
                [
                    f
                    for f in item.iterdir()
                    if f.is_file() and f.suffix.lower() in SUPPORTED_DOC_EXTENSIONS
                ],
                key=lambda f: f.name.lower(),
            )
            primary_docs = [f for f in sub_files if not _is_complementary_doc(f)]
            if len(primary_docs) >= 2:
                # Batch folder containing multiple standalone CVs/resumes: treat each file as 1 candidate
                for fpath in sub_files:
                    display_name = fpath.stem.replace("_", " ").replace("-", " ").strip() or fpath.name
                    entries.append(
                        {
                            "name": display_name,
                            "source_folder": fpath.stem,
                            "folder_path": str(fpath.resolve()),
                        }
                    )
            else:
                display_name = item.name.replace("_", " ").strip()
                entries.append(
                    {
                        "name": display_name,
                        "source_folder": item.name,
                        "folder_path": str(item.resolve()),
                    }
                )
        elif item.is_file() and item.suffix.lower() in SUPPORTED_DOC_EXTENSIONS:
            display_name = item.stem.replace("_", " ").replace("-", " ").strip() or item.name
            entries.append(
                {
                    "name": display_name,
                    "source_folder": item.stem,
                    "folder_path": str(item.resolve()),
                }
            )

    return entries


def list_candidates(applications_dir: str | None = None) -> list[dict[str, str]]:
    """List candidate folders or standalone resume files, assign anonymous IDs (C001, C002, ...), and store local mapping.

    Args:
        applications_dir: Optional directory containing candidate subfolders or resume files.

    Returns:
        List of dicts with keys 'candidate_id' and 'source_folder' (real name stays in local mapping).
    """
    app_dir = Path(applications_dir) if applications_dir else DEFAULT_APPLICATIONS_DIR
    if not app_dir.exists():
        raise FileNotFoundError(f"Applications directory not found at: {app_dir}")

    resolved_entries = _resolve_candidate_entries(app_dir)
    _CANDIDATE_MAPPING.clear()
    public_records: list[dict[str, str]] = []

    for idx, entry in enumerate(resolved_entries, start=1):
        cid = f"C{idx:03d}"
        _CANDIDATE_MAPPING[cid] = {
            "candidate_id": cid,
            "name": entry["name"],
            "source_folder": entry["source_folder"],
            "folder_path": entry["folder_path"],
        }
        public_records.append(
            {
                "candidate_id": cid,
                "source_folder": entry["source_folder"],
            }
        )

    return public_records


def read_application(candidate_identifier: str, applications_dir: str | None = None) -> str:
    """Extract and concatenate full text from all files in a candidate folder (or single resume file).

    Never truncates snippets: cover letter, email, and CV (if present) are included in full.

    Args:
        candidate_identifier: Anonymous ID (e.g. 'C001'), folder/file name, or path to folder/file.
        applications_dir: Optional base directory for applications.

    Returns:
        Complete concatenated text of all files in the candidate's application.
    """
    folder_path: Path | None = None
    if applications_dir and candidate_identifier in _CANDIDATE_MAPPING:
        cached_path = Path(_CANDIDATE_MAPPING[candidate_identifier]["folder_path"]).resolve()
        app_dir_resolved = Path(applications_dir).resolve()
        if not cached_path.is_relative_to(app_dir_resolved):
            list_candidates(applications_dir)
    elif applications_dir and not _CANDIDATE_MAPPING:
        list_candidates(applications_dir)

    if candidate_identifier in _CANDIDATE_MAPPING:
        folder_path = Path(_CANDIDATE_MAPPING[candidate_identifier]["folder_path"])
    else:
        candidate_path = Path(candidate_identifier)
        if candidate_path.exists():
            folder_path = candidate_path
        else:
            base = Path(applications_dir) if applications_dir else DEFAULT_APPLICATIONS_DIR
            potential = base / candidate_identifier
            if potential.exists():
                folder_path = potential
            else:
                list_candidates(str(base))
                for info in _CANDIDATE_MAPPING.values():
                    if (
                        info.get("source_folder", "").lower() == candidate_identifier.strip().lower()
                        or info.get("name", "").lower() == candidate_identifier.strip().lower()
                    ):
                        folder_path = Path(info["folder_path"])
                        break

    if folder_path is None or not folder_path.exists():
        raise FileNotFoundError(f"Candidate folder not found for: {candidate_identifier}")

    if folder_path.is_file():
        files = [folder_path]
    else:
        files = sorted([f for f in folder_path.iterdir() if f.is_file()], key=lambda f: f.name.lower())
    sections: list[str] = []
    present_types: list[str] = []

    for file_path in files:
        suffix = file_path.suffix.lower()
        if suffix == ".docx":
            content = _extract_docx_text(file_path)
        elif suffix == ".pdf":
            content = _extract_pdf_text(file_path)
        elif suffix == ".eml":
            content = _extract_eml_text(file_path)
        elif suffix == ".txt":
            content = file_path.read_text(encoding="utf-8", errors="replace").strip()
        else:
            continue

        lower_name = file_path.name.lower()
        if "cover" in lower_name:
            doc_type = "COVER_LETTER"
        elif "email" in lower_name or suffix == ".eml":
            doc_type = "EMAIL"
        elif "cv" in lower_name or "resume" in lower_name or suffix in (".pdf", ".docx", ".txt"):
            doc_type = "CV"
        else:
            doc_type = "DOCUMENT"

        present_types.append(doc_type)
        sections.append(f"=== {doc_type} ({file_path.name}) ===\n{content}")

    has_cv = "CV" in present_types
    header = (
        f"APPLICATION DOCUMENTS PRESENT: {', '.join(present_types)} "
        f"(CV Present: {'Yes' if has_cv else 'No - Cover Letter & Email Only'})"
    )
    return header + "\n\n" + "\n\n".join(sections)


def anonymise_text(text: str, candidate_name: str | None = None) -> str:
    """Redact name, contact details, gender/age/nationality/marital status, and photo references.

    Args:
        text: Raw application text.
        candidate_name: Optional known candidate name to redact explicitly.

    Returns:
        Anonymised application text with all job-relevant skills and experience preserved.
    """
    redacted = text

    # 1. Redact explicit candidate name and its distinct parts
    names_to_redact: list[str] = []
    if candidate_name:
        names_to_redact.append(candidate_name)
        for token in re.split(r"[\s_\-]+", candidate_name):
            clean = token.strip()
            if len(clean) >= 2 and clean.lower() not in {"dummy", "candidate", "applicant"}:
                names_to_redact.append(clean)

    # Also redact all known names from _CANDIDATE_MAPPING
    for info in _CANDIDATE_MAPPING.values():
        mapped_name = info.get("name", "")
        if mapped_name:
            names_to_redact.append(mapped_name)
            for token in re.split(r"[\s_\-]+", mapped_name):
                clean = token.strip()
                if len(clean) >= 3 and clean.lower() not in {"dummy", "candidate", "applicant"}:
                    names_to_redact.append(clean)

    # Sort longest first so full names are replaced before substrings
    for name_item in sorted(set(names_to_redact), key=len, reverse=True):
        pattern = re.compile(r"\b" + re.escape(name_item) + r"\b", flags=re.IGNORECASE)
        redacted = pattern.sub("[REDACTED_NAME]", redacted)

    # 2. Redact structured header lines containing personal identifiers
    redacted = re.sub(
        r"(?im)^(name|full\s*name|applicant\s*name|candidate\s*name|from)\s*:\s*.*$",
        r"\1: [REDACTED_NAME]",
        redacted,
    )
    redacted = re.sub(
        r"(?im)^(address|home\s*address|location|residence)\s*:\s*.*$",
        r"\1: [REDACTED_ADDRESS]",
        redacted,
    )
    redacted = re.sub(
        r"(?im)^(age|date\s*of\s*birth|dob|birth\s*date)\s*:\s*.*$",
        r"\1: [REDACTED_AGE]",
        redacted,
    )
    redacted = re.sub(
        r"(?im)^(gender|sex|pronouns|nationality|citizenship|marital\s*status|family\s*status)\s*:\s*.*$",
        r"\1: [REDACTED_PROTECTED]",
        redacted,
    )
    redacted = re.sub(
        r"(?im)^(photo|photograph|headshot|profile\s*picture|portrait)\s*:\s*.*$",
        r"\1: [REDACTED_PHOTO]",
        redacted,
    )

    # 3. Redact sign-off names (e.g., after Sincerely, / Best regards, / Kind regards,)
    redacted = re.sub(
        r"(?im)^((?:sincerely|best\s+regards|kind\s+regards|warm\s+regards|regards|yours\s+truly|cheers)[,\s]*\n+)([A-Z][A-Za-z\s\.\-]{1,50})$",
        r"\1[REDACTED_NAME]",
        redacted,
    )

    # 4. Redact emails, URLs, and phone numbers
    redacted = re.sub(
        r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b",
        "[REDACTED_EMAIL]",
        redacted,
    )
    redacted = re.sub(
        r"https?://[^\s,;)\]>]+|www\.[^\s,;)\]>]+|linkedin\.com/in/[^\s,;)\]>]+|github\.com/[^\s,;)\]>]+",
        "[REDACTED_URL]",
        redacted,
        flags=re.IGNORECASE,
    )
    redacted = re.sub(
        r"(?:(?:\+\d{1,3}[\s\-]?)?(?:\(\d{2,4}\)[\s\-]?|\d{2,4}[\s\-])\d{3,4}[\s\-]\d{3,4})",
        "[REDACTED_PHONE]",
        redacted,
    )

    # 5. Redact inline age, gender, nationality, marital status, and photo mentions
    redacted = re.sub(
        r"\b\d{2}\s*(?:-|\s)?\s*years?\s+old\b|\bborn\s+in\s+\d{4}\b|\b\d{2}-year-old\b",
        "[REDACTED_AGE]",
        redacted,
        flags=re.IGNORECASE,
    )
    redacted = re.sub(
        r"\b(?:mr|mrs|ms|miss|mx)\.?\s+(\[REDACTED_NAME\]|[A-Z][a-z]+)",
        "[REDACTED_NAME]",
        redacted,
        flags=re.IGNORECASE,
    )
    redacted = re.sub(
        r"\b(?:he/him|she/her|they/them|married|single|divorced|widowed|mother\s+of\s+\w+|father\s+of\s+\w+)\b",
        "[REDACTED_PROTECTED]",
        redacted,
        flags=re.IGNORECASE,
    )
    redacted = re.sub(
        r"\[[^\]]*(?:photo|headshot|portrait|picture)[^\]]*\]|\b(?:attached\s+photo|headshot\s+attached|see\s+my\s+photo|profile\s+photo|\w+\.(?:jpg|jpeg|png))\b",
        "[REDACTED_PHOTO]",
        redacted,
        flags=re.IGNORECASE,
    )

    return redacted


def save_rubric_json(rubric: JobRubric | dict[str, Any], output_path: str | None = None) -> str:
    """Save the generated JobRubric to output/rubric.json."""
    path = Path(output_path) if output_path else DEFAULT_RUBRIC_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    data = rubric.model_dump() if isinstance(rubric, JobRubric) else dict(rubric)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return str(path)


def compute_candidate_status(
    evaluation: CandidateEvaluation | dict[str, Any],
    hr_decision_record: dict[str, Any] | None = None,
) -> str:
    """Compute the candidate decision status per T015 section 2:
    - 'HR decided': an HR decision exists (overrides everything)
    - 'Needs HR review': review_reasons present / needs_human_review is True
    - 'AI decided': clear case, no review reasons
    """
    if hr_decision_record and hr_decision_record.get("decision") in (
        "Shortlisted",
        "Not Shortlisted",
    ):
        return "HR decided"
    if isinstance(evaluation, dict):
        needs_review = bool(evaluation.get("needs_human_review", False))
        reasons = evaluation.get("review_reasons") or []
    else:
        needs_review = evaluation.needs_human_review
        reasons = evaluation.review_reasons
    if needs_review or len(reasons) > 0:
        return "Needs HR review"
    return "AI decided"


def load_hr_decisions(
    decisions_path: str | Path | None = None,
) -> dict[str, dict[str, Any]]:
    """Load recorded HR decisions from output/hr_decisions.json keyed by candidate_id."""
    path = Path(decisions_path) if decisions_path else DEFAULT_HR_DECISIONS_PATH
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    decisions: dict[str, dict[str, Any]] = {}
    if isinstance(raw, dict):
        if "candidate_id" in raw and "decision" in raw:
            cid = str(raw["candidate_id"]).strip().upper()
            decisions[cid] = dict(raw)
        else:
            for k, val in raw.items():
                if isinstance(val, dict) and "decision" in val:
                    cid = str(val.get("candidate_id") or k).strip().upper()
                    decisions[cid] = dict(val)
    elif isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict) and "candidate_id" in item and "decision" in item:
                cid = str(item["candidate_id"]).strip().upper()
                decisions[cid] = dict(item)
    return decisions


def write_results_excel(
    evaluations: list[CandidateEvaluation | dict[str, Any]],
    rubric: JobRubric | dict[str, Any],
    output_path: str | None = None,
    candidate_mapping: dict[str, dict[str, str]] | None = None,
    model_name: str | None = None,
    prompt_version: str = "v1.1",
    hr_decisions: dict[str, dict[str, Any]] | None = None,
    job_id: str | None = None,
) -> str:
    """Write screening results, review queue, rubric, and metadata to output/screening_results.xlsx.

    Columns on 'Results' sheet (T015 section 3):
    Candidate ID, Name, AI Recommendation, AI Confidence, Review Reasons, Status,
    HR Decision, HR Note, Final Decision, Overall Score, Top Strengths, Gaps, Reasoning, Source Folder.
    Final Decision = HR Decision if set, otherwise AI Recommendation.
    Sorted with 'Needs HR review' first, then by Overall Score descending.
    """
    global _LAST_EVALUATIONS, _LAST_RUBRIC, _LAST_CANDIDATE_MAPPING
    global _LAST_EXCEL_PATH, _LAST_MODEL_NAME, _LAST_PROMPT_VERSION

    excel_path = Path(output_path) if output_path else DEFAULT_EXCEL_PATH
    excel_path.parent.mkdir(parents=True, exist_ok=True)

    mapping = candidate_mapping if candidate_mapping is not None else _CANDIDATE_MAPPING
    rubric_obj = rubric if isinstance(rubric, JobRubric) else JobRubric.model_validate(rubric)
    eval_objs: list[CandidateEvaluation] = [
        e if isinstance(e, CandidateEvaluation) else CandidateEvaluation.model_validate(e)
        for e in evaluations
    ]

    # Cache latest state in memory and on disk so record_hr_decision can regenerate the workbook
    _LAST_EVALUATIONS = list(eval_objs)
    _LAST_RUBRIC = rubric_obj
    _LAST_CANDIDATE_MAPPING = dict(mapping)
    _LAST_EXCEL_PATH = excel_path
    _LAST_MODEL_NAME = model_name
    _LAST_PROMPT_VERSION = prompt_version

    try:
        evals_cache_path = excel_path.parent / "evaluations.json"
        evals_cache_path.write_text(
            json.dumps([e.model_dump() for e in eval_objs], indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass

    if hr_decisions is not None:
        resolved_hr_decisions = hr_decisions
    else:
        local_hr_file = excel_path.parent / "hr_decisions.json"
        if DEFAULT_HR_DECISIONS_PATH.exists():
            resolved_hr_decisions = load_hr_decisions(DEFAULT_HR_DECISIONS_PATH)
        elif local_hr_file.exists():
            resolved_hr_decisions = load_hr_decisions(local_hr_file)
        else:
            resolved_hr_decisions = {}

    # Compute status for each candidate and sort: "Needs HR review" first, then Overall Score descending
    def _sort_key(ev: CandidateEvaluation) -> tuple[int, float]:
        hr_rec = resolved_hr_decisions.get(ev.candidate_id)
        st = compute_candidate_status(ev, hr_rec)
        return (0 if st == "Needs HR review" else 1, -ev.overall_score)

    eval_objs.sort(key=_sort_key)

    resolved_model = model_name or os.environ.get("MODEL_NAME") or "gemini-4-argon"
    wb = Workbook()

    # Styles
    header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, size=11)
    shortlisted_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
    shortlisted_font = Font(color="006100", bold=True)
    rejected_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
    rejected_font = Font(color="9C0006", bold=True)
    review_fill = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")
    review_font = Font(color="9C6500", bold=True)
    hr_decided_fill = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
    hr_decided_font = Font(color="1F4E78", bold=True)
    thin_border = Border(
        left=Side(style="thin", color="D9D9D9"),
        right=Side(style="thin", color="D9D9D9"),
        top=Side(style="thin", color="D9D9D9"),
        bottom=Side(style="thin", color="D9D9D9"),
    )

    # -------------------------------------------------------------------------
    # Sheet 1: "Results"
    # -------------------------------------------------------------------------
    ws_results = wb.active
    ws_results.title = "Results"

    results_headers = [
        "Candidate ID",
        "Name",
        "AI Recommendation",
        "AI Confidence",
        "Review Reasons",
        "Status",
        "HR Decision",
        "HR Note",
        "Final Decision",
        "Overall Score",
        "Top Strengths",
        "Gaps",
        "Reasoning",
        "Source Folder",
    ]
    ws_results.append(results_headers)
    for col_idx in range(1, len(results_headers) + 1):
        cell = ws_results.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    ai_decided_count = 0
    needs_hr_review_count = 0
    hr_decided_count = 0
    ai_flagged_count = 0
    review_queue_rows: list[list[Any]] = []

    for row_idx, ev in enumerate(eval_objs, start=2):
        cid = ev.candidate_id
        candidate_info = mapping.get(cid, {})
        real_name = candidate_info.get("name", f"Candidate {cid}")
        source_folder = candidate_info.get("source_folder", cid)

        hr_rec = resolved_hr_decisions.get(cid)
        hr_decision_val = hr_rec.get("decision", "") if hr_rec else ""
        hr_note_val = hr_rec.get("note", "") if hr_rec else ""
        status_str = compute_candidate_status(ev, hr_rec)
        final_decision = hr_decision_val if hr_decision_val else ev.decision
        reasons_str = ", ".join(ev.review_reasons) if ev.review_reasons else ""

        if ev.needs_human_review or len(ev.review_reasons) > 0:
            ai_flagged_count += 1

        if status_str == "AI decided":
            ai_decided_count += 1
        elif status_str == "Needs HR review":
            needs_hr_review_count += 1
            review_queue_rows.append(
                [
                    cid,
                    real_name,
                    ev.decision,
                    round(ev.confidence, 2),
                    reasons_str,
                    status_str,
                    round(ev.overall_score, 1),
                    "; ".join(ev.gaps) if ev.gaps else "None noted",
                    ev.reasoning,
                    source_folder,
                ]
            )
        elif status_str == "HR decided":
            hr_decided_count += 1

        row_values = [
            cid,
            real_name,
            ev.decision,
            round(ev.confidence, 2),
            reasons_str,
            status_str,
            hr_decision_val,
            hr_note_val,
            final_decision,
            round(ev.overall_score, 1),
            "; ".join(ev.strengths) if ev.strengths else "None noted",
            "; ".join(ev.gaps) if ev.gaps else "None noted",
            ev.reasoning,
            source_folder,
        ]
        ws_results.append(row_values)

        for col_idx in range(1, len(results_headers) + 1):
            cell = ws_results.cell(row=row_idx, column=col_idx)
            cell.border = thin_border
            cell.alignment = Alignment(vertical="top", wrap_text=True)

        # Colour-code AI Recommendation column (col 3)
        ai_rec_cell = ws_results.cell(row=row_idx, column=3)
        ai_rec_cell.alignment = Alignment(horizontal="center", vertical="top")
        if ev.decision == "Shortlisted":
            ai_rec_cell.fill = shortlisted_fill
            ai_rec_cell.font = shortlisted_font
        else:
            ai_rec_cell.fill = rejected_fill
            ai_rec_cell.font = rejected_font

        # Format Status column (col 6)
        status_cell = ws_results.cell(row=row_idx, column=6)
        status_cell.alignment = Alignment(horizontal="center", vertical="top")
        if status_str == "Needs HR review":
            status_cell.fill = review_fill
            status_cell.font = review_font
        elif status_str == "HR decided":
            status_cell.fill = hr_decided_fill
            status_cell.font = hr_decided_font

        # Colour-code Final Decision column (col 9)
        final_cell = ws_results.cell(row=row_idx, column=9)
        final_cell.alignment = Alignment(horizontal="center", vertical="top")
        if status_str == "Needs HR review":
            final_cell.fill = review_fill
            final_cell.font = review_font
        elif final_decision == "Shortlisted":
            final_cell.fill = shortlisted_fill
            final_cell.font = shortlisted_font
        else:
            final_cell.fill = rejected_fill
            final_cell.font = rejected_font

    column_widths_results = [14, 24, 18, 15, 28, 18, 18, 28, 18, 15, 42, 42, 55, 26]
    for idx, width in enumerate(column_widths_results, start=1):
        ws_results.column_dimensions[get_column_letter(idx)].width = width

    # -------------------------------------------------------------------------
    # Sheet 2: "Review Queue" (only "Needs HR review" candidates with reasons)
    # -------------------------------------------------------------------------
    ws_queue = wb.create_sheet(title="Review Queue")
    queue_headers = [
        "Candidate ID",
        "Name",
        "AI Recommendation",
        "AI Confidence",
        "Review Reasons",
        "Status",
        "Overall Score",
        "Gaps",
        "Reasoning",
        "Source Folder",
    ]
    ws_queue.append(queue_headers)
    for col_idx in range(1, len(queue_headers) + 1):
        cell = ws_queue.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    for row_idx, q_row in enumerate(review_queue_rows, start=2):
        ws_queue.append(q_row)
        for col_idx in range(1, len(queue_headers) + 1):
            cell = ws_queue.cell(row=row_idx, column=col_idx)
            cell.border = thin_border
            cell.alignment = Alignment(vertical="top", wrap_text=True)
        status_cell = ws_queue.cell(row=row_idx, column=6)
        status_cell.fill = review_fill
        status_cell.font = review_font

    column_widths_queue = [14, 24, 18, 15, 28, 18, 15, 42, 55, 26]
    for idx, width in enumerate(column_widths_queue, start=1):
        ws_queue.column_dimensions[get_column_letter(idx)].width = width

    # -------------------------------------------------------------------------
    # Sheet 3: "Rubric"
    # -------------------------------------------------------------------------
    ws_rubric = wb.create_sheet(title="Rubric")
    rubric_headers = [
        "Criterion ID",
        "Criterion Name",
        "Category",
        "Weight (%)",
        "Description",
    ]
    ws_rubric.append(rubric_headers)
    for col_idx in range(1, len(rubric_headers) + 1):
        cell = ws_rubric.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    for row_idx, crit in enumerate(rubric_obj.all_criteria(), start=2):
        ws_rubric.append(
            [
                crit.id,
                crit.name,
                crit.category,
                round(crit.weight, 1),
                crit.description,
            ]
        )
        for col_idx in range(1, len(rubric_headers) + 1):
            cell = ws_rubric.cell(row=row_idx, column=col_idx)
            cell.border = thin_border
            cell.alignment = Alignment(vertical="top", wrap_text=True)

    total_candidates = len(eval_objs)
    effective_review_count = max(needs_hr_review_count, ai_flagged_count)
    flag_rate = (effective_review_count / total_candidates) if total_candidates > 0 else 0.0
    flag_rate_pct = round(flag_rate * 100.0, 1)
    high_review_rate = flag_rate > 0.40

    # Append metadata block on the Rubric sheet as well
    ws_rubric.append([])
    metadata_rows: list[tuple[str, str]] = [
        ("Metadata Key", "Metadata Value"),
        *(
            [("Job ID", str(job_id))]
            if job_id
            else []
        ),
        ("Job Title", rubric_obj.job_title),
        ("Role Summary", rubric_obj.role_summary),
        ("Shortlist Threshold", str(rubric_obj.shortlist_threshold)),
        ("Requires Continuity", str(rubric_obj.requires_continuity)),
        ("Total Candidates", str(total_candidates)),
        ("AI Decided", str(ai_decided_count)),
        ("Needs HR Review", str(needs_hr_review_count)),
        ("HR Decided", str(hr_decided_count)),
        ("Flag Rate", f"{flag_rate_pct:.1f}%"),
        (
            "Calibration Status",
            HIGH_REVIEW_RATE_WARNING if high_review_rate else "OK (within 40% threshold)",
        ),
        ("Prompt Version", prompt_version),
        ("Model Used", resolved_model),
        ("Rubric File", "output/rubric.json"),
        ("Generated At (UTC)", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")),
    ]
    if high_review_rate:
        metadata_rows.append(("Warning", HIGH_REVIEW_RATE_WARNING))

    for meta_key, meta_val in metadata_rows:
        ws_rubric.append([meta_key, meta_val])
        curr_row = ws_rubric.max_row
        if meta_key == "Metadata Key":
            for c_i in (1, 2):
                cell = ws_rubric.cell(row=curr_row, column=c_i)
                cell.fill = header_fill
                cell.font = header_font
        else:
            ws_rubric.cell(row=curr_row, column=1).font = Font(bold=True)

    column_widths_rubric = [18, 30, 18, 15, 65]
    for idx, width in enumerate(column_widths_rubric, start=1):
        ws_rubric.column_dimensions[get_column_letter(idx)].width = width

    # -------------------------------------------------------------------------
    # Sheet 4: "Metadata" (includes HITL counts, flag rate, warning & evidence)
    # -------------------------------------------------------------------------
    ws_meta = wb.create_sheet(title="Metadata")
    ws_meta.append(["Key", "Value"])
    for c_i in (1, 2):
        cell = ws_meta.cell(row=1, column=c_i)
        cell.fill = header_fill
        cell.font = header_font

    for meta_key, meta_val in metadata_rows[1:]:
        ws_meta.append([meta_key, meta_val])
        if meta_val == HIGH_REVIEW_RATE_WARNING:
            warn_row = ws_meta.max_row
            ws_meta.cell(row=warn_row, column=2).fill = review_fill
            ws_meta.cell(row=warn_row, column=2).font = review_font

    ws_meta.append(["Rubric JSON", json.dumps(rubric_obj.model_dump())])
    ws_meta.append([])
    ws_meta.append(
        [
            "Candidate ID",
            "Criterion ID",
            "Criterion Name",
            "Category",
            "Score (0-5)",
            "Weight (%)",
            "Evidence",
        ]
    )
    header_row_idx = ws_meta.max_row
    for c_i in range(1, 8):
        cell = ws_meta.cell(row=header_row_idx, column=c_i)
        cell.fill = header_fill
        cell.font = header_font

    for ev in eval_objs:
        for cs in ev.criterion_scores:
            ws_meta.append(
                [
                    ev.candidate_id,
                    cs.criterion_id,
                    cs.criterion_name,
                    cs.category,
                    cs.score,
                    cs.weight,
                    cs.evidence,
                ]
            )

    ws_meta.column_dimensions["A"].width = 24
    ws_meta.column_dimensions["B"].width = 50
    ws_meta.column_dimensions["C"].width = 28
    ws_meta.column_dimensions["D"].width = 16
    ws_meta.column_dimensions["E"].width = 14
    ws_meta.column_dimensions["F"].width = 14
    ws_meta.column_dimensions["G"].width = 65

    wb.save(str(excel_path))
    return str(excel_path)


def record_hr_decision(
    candidate_id: str,
    decision: str,
    note: str = "",
) -> dict[str, Any]:
    """Record an HR decision for a candidate, write output/hr_decisions.json, and regenerate Excel.

    Args:
        candidate_id: Anonymous candidate ID (e.g., 'C002').
        decision: Must be 'Shortlisted' or 'Not Shortlisted'.
        note: Optional HR note explaining the decision or override.

    Returns:
        Dictionary containing the recorded HR decision and regenerated Excel path.
    """
    cid = candidate_id.strip().upper()
    cleaned_decision = decision.strip()
    if cleaned_decision.lower() == "shortlisted":
        normalized_decision = "Shortlisted"
    elif cleaned_decision.lower() in ("not shortlisted", "not_shortlisted", "rejected"):
        normalized_decision = "Not Shortlisted"
    else:
        raise ValueError(
            f"Invalid HR decision '{decision}'. Must be 'Shortlisted' or 'Not Shortlisted'."
        )

    timestamp_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    hr_path = DEFAULT_HR_DECISIONS_PATH
    hr_path.parent.mkdir(parents=True, exist_ok=True)

    existing = load_hr_decisions(hr_path)
    if not existing and _LAST_EXCEL_PATH is not None:
        alt_hr_path = _LAST_EXCEL_PATH.parent / "hr_decisions.json"
        if alt_hr_path.exists():
            existing = load_hr_decisions(alt_hr_path)

    record = {
        "candidate_id": cid,
        "decision": normalized_decision,
        "note": note,
        "timestamp": timestamp_utc,
    }
    existing[cid] = record
    serialized = json.dumps(existing, indent=2)
    hr_path.write_text(serialized, encoding="utf-8")

    target_excel_path = _LAST_EXCEL_PATH or DEFAULT_EXCEL_PATH
    if DEFAULT_EXCEL_PATH != OUTPUT_DIR / "screening_results.xlsx":
        target_excel_path = DEFAULT_EXCEL_PATH

    if target_excel_path.parent != hr_path.parent:
        target_excel_path.parent.mkdir(parents=True, exist_ok=True)
        (target_excel_path.parent / "hr_decisions.json").write_text(
            serialized, encoding="utf-8"
        )

    # Load evaluations and rubric from memory or disk to regenerate screening_results.xlsx
    eval_objs = list(_LAST_EVALUATIONS)
    if not eval_objs:
        evals_file = target_excel_path.parent / "evaluations.json"
        if not evals_file.exists():
            evals_file = DEFAULT_EVALUATIONS_PATH
        if evals_file.exists():
            raw_list = json.loads(evals_file.read_text(encoding="utf-8"))
            eval_objs = [CandidateEvaluation.model_validate(item) for item in raw_list]

    rubric_obj = _LAST_RUBRIC
    if rubric_obj is None:
        rubric_file = target_excel_path.parent / "rubric.json"
        if not rubric_file.exists():
            rubric_file = DEFAULT_RUBRIC_PATH
        if rubric_file.exists():
            rubric_obj = JobRubric.model_validate_json(
                rubric_file.read_text(encoding="utf-8")
            )

    mapping = _LAST_CANDIDATE_MAPPING or get_candidate_mapping()
    if not mapping and DEFAULT_APPLICATIONS_DIR.exists():
        list_candidates()
        mapping = get_candidate_mapping()

    regenerated_excel_path = str(target_excel_path)
    if eval_objs and rubric_obj is not None:
        regenerated_excel_path = write_results_excel(
            evaluations=eval_objs,
            rubric=rubric_obj,
            output_path=str(target_excel_path),
            candidate_mapping=mapping,
            model_name=_LAST_MODEL_NAME,
            prompt_version=_LAST_PROMPT_VERSION,
            hr_decisions=existing,
        )

    return {
        "candidate_id": cid,
        "decision": normalized_decision,
        "note": note,
        "timestamp": timestamp_utc,
        "status": "HR decided",
        "final_decision": normalized_decision,
        "hr_decisions_path": str(hr_path),
        "excel_path": regenerated_excel_path,
    }
