"""FastAPI backend for the HR Candidate Screening Web Application (T016, T017, T018, T019).

Reuses screening_agent functions without duplicating scoring logic:
- list_candidates, read_application, read_job_advert, write_results_excel, record_hr_decision
- run_screening_pipeline, apply_uncertainty_rules, compute_candidate_status
Supports multi-job management with unique Job IDs (JOB-2026-001, ...), per-job JD & CV uploads,
per-job screening runs, per-job HR decisions keyed by (job_id, candidate_id), and per-job Excel export.
"""

from __future__ import annotations

from datetime import datetime, timezone
import io
import json
import math
import os
from pathlib import Path
import re
import threading
from typing import Any
import uuid
import zipfile

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import desc
from sqlalchemy.orm import Session

from screening_agent import agent as agent_module
from screening_agent import tools as tools_module
from screening_agent.agent import (
    apply_uncertainty_rules,
    run_screening_pipeline,
    sync_decision_and_reasoning,
)
from screening_agent.schemas import CandidateEvaluation, JobRubric
from screening_agent.tools import (
    _extract_docx_text,
    _extract_eml_text,
    _extract_pdf_text,
    compute_candidate_status,
    get_candidate_mapping,
    list_candidates,
    read_application,
    read_job_advert,
    record_hr_decision,
    write_results_excel,
)

from .auth import (
    GOOGLE_CLIENT_ID,
    _is_test_json_fallback_active,
    get_allowlist_filename,
    is_demo_test_auth_enabled,
    is_root_admin,
    load_root_admins,
    migrate_access_control,
    require_admin_auth,
    require_hr_auth,
)
from .database import (
    DATA_DIR,
    WEBAPP_DIR,
    AllowedDomain,
    AllowedUser,
    AuditLog,
    CandidateResult,
    HrDecision,
    Job,
    Run,
    get_db,
    get_session,
    init_db,
)
from .plain_language import (
    build_plain_why_summary,
    format_ai_recommendation,
    format_review_reasons,
    format_status_badge,
)

PROJECT_ROOT = WEBAPP_DIR.parent.resolve()
DEFAULT_APPLICATIONS_DIR = (PROJECT_ROOT / "screening_agent" / "data" / "applications").resolve()
DEFAULT_ADVERT_PATH = (PROJECT_ROOT / "screening_agent" / "data" / "job_advert.docx").resolve()
SETTINGS_FILE_PATH = DATA_DIR / "settings.json"
WEBAPP_EXCEL_PATH = DATA_DIR / "screening_results.xlsx"
STATIC_DIR = WEBAPP_DIR / "static"

ALLOWED_MODELS = (
    "gemini-4-argon",
    "gemini-2.5-pro",
    "gemini-2.5-flash",
)

ALLOWED_JD_EXTENSIONS = {".docx", ".pdf", ".txt", ".md"}
ALLOWED_CV_EXTENSIONS = {".docx", ".pdf", ".eml", ".txt"}

# Concurrency state for background screening runs (only one run at a time)
_RUN_LOCK = threading.Lock()
_ACTIVE_RUN_ID: str | None = None
_RUN_PROGRESS: dict[str, dict[str, Any]] = {}


def utc_now_iso() -> str:
    """Return current UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _get_jobs_root() -> Path:
    """Return the directory where uploaded job JDs, CV folders, and Excel exports are stored."""
    return (SETTINGS_FILE_PATH.parent / "jobs").resolve()


def _human_size(num_bytes: int) -> str:
    """Format file size in bytes into a friendly string."""
    if num_bytes < 1024:
        return f"{num_bytes} B"
    kb = num_bytes / 1024.0
    if kb < 1024:
        return f"{kb:.1f} KB"
    mb = kb / 1024.0
    return f"{mb:.1f} MB"


def _classify_file_type(file_path: Path) -> str:
    """Classify an application file into plain English type."""
    lower = file_path.name.lower()
    suffix = file_path.suffix.lower()
    if "cover" in lower:
        return "Cover Letter"
    if "cv" in lower or "resume" in lower:
        return "CV"
    if "email" in lower or suffix == ".eml":
        return "Email"
    return "Document"


def _extract_single_file_text(file_path: Path) -> tuple[str, str]:
    """Extract text from a single file and return (text, parse_status)."""
    suffix = file_path.suffix.lower()
    try:
        if suffix == ".docx":
            text = _extract_docx_text(file_path)
        elif suffix == ".pdf":
            text = _extract_pdf_text(file_path)
        elif suffix == ".eml":
            text = _extract_eml_text(file_path)
        elif suffix in (".txt", ".md"):
            text = file_path.read_text(encoding="utf-8", errors="replace").strip()
        else:
            return "", "Unsupported"
    except Exception:
        return "", "Unreadable"

    cleaned = text.strip()
    if not cleaned or "[UNREADABLE" in cleaned:
        return cleaned, "Unreadable" if "[UNREADABLE" in cleaned else "Empty"
    return cleaned, "OK"


def _truncate_why_text(text: str, max_chars: int = 140) -> tuple[str, bool]:
    """Return (short_text, is_truncated) clamped for a 2-line table cell preview."""
    cleaned = " ".join((text or "").split())
    if len(cleaned) <= max_chars:
        return cleaned, False
    cut = cleaned[: max_chars - 3].rsplit(" ", 1)[0]
    if not cut:
        cut = cleaned[: max_chars - 3]
    return f"{cut}...", True


def _allowed_data_roots() -> list[Path]:
    """Return allowed base directories for job descriptions and candidate application folders."""
    roots = [
        (PROJECT_ROOT / "screening_agent" / "data").resolve(),
        (PROJECT_ROOT / "screening_webapp" / "data").resolve(),
        _get_jobs_root(),
        SETTINGS_FILE_PATH.parent.resolve(),
        Path(tools_module.DEFAULT_APPLICATIONS_DIR).parent.resolve(),
        Path(tools_module.DEFAULT_ADVERT_PATH).parent.resolve(),
    ]
    extra_root = os.environ.get("ALLOWED_APPLICATIONS_ROOT")
    if extra_root:
        extra_resolved = Path(extra_root).resolve()
        if extra_resolved.is_relative_to(PROJECT_ROOT):
            roots.append(extra_resolved)
    return roots


def validate_applications_dir(raw_path: str) -> Path:
    """Ensure applications_dir is inside an allowed project/test data folder and exists."""
    if not raw_path or not str(raw_path).strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="applications_dir cannot be empty.",
        )

    raw_clean = str(raw_path).strip().replace("\\", "/")
    candidate = Path(raw_clean)
    if not candidate.is_absolute():
        resolved = (PROJECT_ROOT / candidate).resolve()
    else:
        resolved = candidate.resolve()

    allowed_roots = _allowed_data_roots()
    if not any(resolved.is_relative_to(root) for root in allowed_roots):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="applications_dir must be inside the project data folder.",
        )

    if not resolved.exists() or not resolved.is_dir():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Applications directory does not exist: {raw_path}",
        )

    return resolved


def validate_jd_path(raw_path: str) -> Path:
    """Ensure jd_path is inside an allowed project/test data folder and exists."""
    if not raw_path or not str(raw_path).strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job description path cannot be empty.",
        )

    raw_clean = str(raw_path).strip().replace("\\", "/")
    candidate = Path(raw_clean)
    if not candidate.is_absolute():
        resolved = (PROJECT_ROOT / candidate).resolve()
    else:
        resolved = candidate.resolve()

    allowed_roots = _allowed_data_roots()
    if not any(resolved.is_relative_to(root) for root in allowed_roots):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job description file must be inside the project data folder.",
        )

    if not resolved.exists() or not resolved.is_file():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job description file does not exist: {raw_path}",
        )

    if resolved.suffix.lower() not in ALLOWED_JD_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job description file must be a .docx, .pdf, or .txt file.",
        )

    return resolved


def load_settings() -> dict[str, Any]:
    """Load current screening settings from disk or return defaults."""
    default_app_dir = Path(tools_module.DEFAULT_APPLICATIONS_DIR).resolve()
    defaults: dict[str, Any] = {
        "threshold": 70.0,
        "requires_continuity": False,
        "model": "gemini-4-argon",
        "applications_dir": str(default_app_dir),
        "redact_before_scoring": True,
        "allowed_models": list(ALLOWED_MODELS),
    }
    if SETTINGS_FILE_PATH.exists():
        try:
            saved = json.loads(SETTINGS_FILE_PATH.read_text(encoding="utf-8"))
            if isinstance(saved, dict):
                if "threshold" in saved:
                    defaults["threshold"] = float(saved["threshold"])
                if "requires_continuity" in saved:
                    defaults["requires_continuity"] = bool(saved["requires_continuity"])
                if saved.get("model") in ALLOWED_MODELS:
                    defaults["model"] = saved["model"]
                if saved.get("applications_dir"):
                    try:
                        valid_dir = validate_applications_dir(str(saved["applications_dir"]))
                        defaults["applications_dir"] = str(valid_dir)
                    except HTTPException:
                        pass
        except Exception:
            pass
    defaults["redact_before_scoring"] = True
    defaults["allowed_models"] = list(ALLOWED_MODELS)
    defaults["allowed_emails_file"] = get_allowlist_filename()
    return defaults


def save_settings(new_settings: dict[str, Any]) -> dict[str, Any]:
    """Persist validated settings to screening_webapp/data/settings.json."""
    SETTINGS_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    to_save = {
        "threshold": float(new_settings["threshold"]),
        "requires_continuity": bool(new_settings["requires_continuity"]),
        "model": str(new_settings["model"]),
        "applications_dir": str(new_settings["applications_dir"]),
        "redact_before_scoring": True,
    }
    SETTINGS_FILE_PATH.write_text(json.dumps(to_save, indent=2), encoding="utf-8")
    return load_settings()


def _is_demo_applications_dir(app_dir: str | Path) -> bool:
    """Return True if the applications directory contains the dummy candidate data."""
    try:
        resolved = Path(app_dir).resolve()
        if resolved == DEFAULT_APPLICATIONS_DIR:
            return True
        folders = [p.name.lower() for p in resolved.iterdir() if p.is_dir()]
        return any("dummy" in name for name in folders)
    except Exception:
        return True


def _generate_next_job_id(db: Session) -> str:
    """Generate the next sequential unique Job ID, e.g. JOB-2026-001, JOB-2026-002."""
    existing_ids = [r[0] for r in db.query(Job.job_id).all() if r[0]]
    max_seq = 0
    for jid in existing_ids:
        m = re.match(r"^JOB-\d{4}-(\d+)$", str(jid).strip().upper())
        if m:
            max_seq = max(max_seq, int(m.group(1)))
    return f"JOB-2026-{max_seq + 1:03d}"


def _count_candidate_folders(app_dir: Path) -> int:
    """Count candidate entries (subfolders or standalone resume files) inside an applications directory."""
    if not app_dir.exists() or not app_dir.is_dir():
        return 0
    return len(tools_module._resolve_candidate_entries(app_dir))


def _count_candidate_documents(folder_path: Path) -> int:
    """Count readable application documents inside a single candidate folder or single file."""
    if not folder_path.exists():
        return 0
    if folder_path.is_file():
        return 1 if folder_path.suffix.lower() in ALLOWED_CV_EXTENSIONS else 0
    if not folder_path.is_dir():
        return 0
    return len(
        [
            f
            for f in folder_path.iterdir()
            if f.is_file() and f.suffix.lower() in ALLOWED_CV_EXTENSIONS
        ]
    )


def _serialize_job(db: Session, job: Job) -> dict[str, Any]:
    """Serialize a Job ORM instance with candidate count and latest run info."""
    job = _repair_default_job_paths(db, job)
    app_dir = Path(job.applications_dir)
    folder_count = _count_candidate_folders(app_dir)
    last_run = (
        db.query(Run)
        .filter(Run.job_id == job.job_id)
        .order_by(desc(Run.started_at), desc(Run.id))
        .first()
    )
    cand_count = folder_count if folder_count > 0 else (int(last_run.candidate_count) if last_run else 0)
    last_run_info = None
    last_run_status = "Not run"
    if last_run is not None:
        last_run_status = last_run.status
        last_run_info = {
            "id": last_run.id,
            "job_id": last_run.job_id,
            "status": last_run.status,
            "started_at": last_run.started_at,
            "finished_at": last_run.finished_at,
            "candidate_count": last_run.candidate_count,
            "model": last_run.model,
            "threshold": last_run.threshold,
            "error": last_run.error,
        }
    return {
        "job_id": job.job_id,
        "title": job.title,
        "jd_filename": job.jd_filename or Path(job.jd_path).name,
        "jd_path": job.jd_path,
        "applications_dir": job.applications_dir,
        "threshold": float(job.threshold),
        "requires_continuity": bool(job.requires_continuity),
        "model": job.model,
        "candidate_count": cand_count,
        "last_run_status": last_run_status,
        "last_run": last_run_info,
        "created_at_utc": job.created_at_utc,
        "created_by_email": job.created_by_email,
    }


def _repair_default_job_paths(db: Session, job: Job) -> Job:
    """Repair default JOB-2026-001 paths when running across environments (e.g., host vs Cloud Run /app)."""
    if job.job_id == "JOB-2026-001":
        changed = False
        if not Path(job.applications_dir).exists() and DEFAULT_APPLICATIONS_DIR.exists():
            job.applications_dir = str(DEFAULT_APPLICATIONS_DIR.resolve())
            changed = True
        if not Path(job.jd_path).exists() and DEFAULT_ADVERT_PATH.exists():
            job.jd_path = str(DEFAULT_ADVERT_PATH.resolve())
            job.jd_filename = DEFAULT_ADVERT_PATH.name
            changed = True
        if changed:
            db.commit()
            db.refresh(job)
    return job


def _ensure_default_job(db: Session, actor_email: str = "system") -> Job:
    """Return the latest Job in DB, or create JOB-2026-001 from current settings if none exists."""
    latest_job = db.query(Job).order_by(desc(Job.created_at_utc), desc(Job.job_id)).first()
    if latest_job is not None:
        return _repair_default_job_paths(db, latest_job)

    settings = load_settings()
    jd_default = Path(tools_module.DEFAULT_ADVERT_PATH).resolve()
    job_id = _generate_next_job_id(db)
    job = Job(
        job_id=job_id,
        title="Sales Executive - Retail and Business Clients",
        jd_filename=jd_default.name,
        jd_path=str(jd_default),
        applications_dir=str(Path(settings["applications_dir"]).resolve()),
        threshold=float(settings["threshold"]),
        requires_continuity=bool(settings["requires_continuity"]),
        model=str(settings["model"]),
        created_at_utc=utc_now_iso(),
        created_by_email=actor_email,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _ensure_demo_seeded_for_sso(
    db: Session, actor_email: str = "guruprem.saginadham@sybyl.com"
) -> None:
    """Seed JOB-2026-001 and its initial finished screening run if no finished run exists."""
    job = _ensure_default_job(db, actor_email=actor_email)
    existing_run = (
        db.query(Run)
        .filter(Run.job_id == job.job_id, Run.status == "finished")
        .first()
    )
    if existing_run is not None:
        return

    evals_path = DATA_DIR / "evaluations.json"
    if not evals_path.exists():
        evals_path = Path(tools_module.DEFAULT_EVALUATIONS_PATH)
    if not evals_path.exists():
        return

    try:
        raw_evals = json.loads(evals_path.read_text(encoding="utf-8"))
        app_dir = Path(job.applications_dir)
        if app_dir.exists():
            list_candidates(str(app_dir))
        mapping = get_candidate_mapping()
        now_iso = utc_now_iso()
        run_id = "run_demo_001"
        if db.query(Run).filter(Run.id == run_id).first() is None:
            new_run = Run(
                id=run_id,
                job_id=job.job_id,
                started_at=now_iso,
                finished_at=now_iso,
                status="finished",
                settings_json=json.dumps(
                    {
                        "job_id": job.job_id,
                        "title": job.title,
                        "threshold": float(job.threshold),
                        "requires_continuity": bool(job.requires_continuity),
                        "model": job.model,
                    }
                ),
                model=job.model,
                threshold=float(job.threshold),
                candidate_count=len(raw_evals),
                error=None,
            )
            db.add(new_run)
            db.flush()

            for item in raw_evals:
                eval_obj = CandidateEvaluation.model_validate(item)
                cid = eval_obj.candidate_id
                cand_info = mapping.get(cid, {})
                cand_name = cand_info.get("name", f"Candidate {cid}")
                source_folder = cand_info.get("source_folder", cid)
                cand_folder_path = Path(cand_info.get("folder_path", app_dir / source_folder))
                doc_count = _count_candidate_documents(cand_folder_path) or 3
                cand_status = compute_candidate_status(eval_obj, None)
                evidence_payload = {
                    "criterion_scores": [cs.model_dump() for cs in eval_obj.criterion_scores],
                    "strengths": eval_obj.strengths,
                    "gaps": eval_obj.gaps,
                    "reasoning": eval_obj.reasoning,
                    "needs_human_review": eval_obj.needs_human_review,
                    "source_folder": source_folder,
                    "document_count": doc_count,
                    "threshold": float(job.threshold),
                    "job_id": job.job_id,
                }
                db.add(
                    CandidateResult(
                        run_id=run_id,
                        candidate_id=cid,
                        job_id=job.job_id,
                        name=cand_name,
                        ai_decision=eval_obj.decision,
                        ai_score=float(eval_obj.overall_score),
                        confidence=float(eval_obj.confidence),
                        status=cand_status,
                        review_reasons_json=json.dumps(list(eval_obj.review_reasons)),
                        evidence_json=json.dumps(evidence_payload),
                    )
                )
            db.commit()
    except Exception:
        db.rollback()


def _get_job_or_404(db: Session, job_id: str) -> Job:
    """Fetch a Job by job_id (case-insensitive) or raise 404."""
    cleaned = (job_id or "").strip().upper()
    job = db.query(Job).filter(Job.job_id == cleaned).first()
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}",
        )
    return _repair_default_job_paths(db, job)


def _get_latest_hr_decisions_map(
    db: Session, job_id: str | None = None
) -> dict[str, HrDecision]:
    """Return a dict mapping candidate_id -> latest HrDecision row for the given job_id."""
    query = db.query(HrDecision)
    if job_id:
        query = query.filter(HrDecision.job_id == job_id.strip().upper())
    rows = query.order_by(desc(HrDecision.id)).all()
    latest: dict[str, HrDecision] = {}
    for row in rows:
        cid = row.candidate_id.strip().upper()
        if cid not in latest:
            latest[cid] = row
    return latest


def _job_excel_path(job_id: str) -> Path:
    """Return the per-job Excel output file path: jobs/<JOB-ID>/screening_results_<JOB-ID>.xlsx."""
    clean_id = job_id.strip().upper()
    job_dir = _get_jobs_root() / clean_id
    job_dir.mkdir(parents=True, exist_ok=True)
    return job_dir / f"screening_results_{clean_id}.xlsx"


def _regenerate_excel_from_db(
    db: Session, run: Run | None = None, job_id: str | None = None
) -> str:
    """Regenerate screening_results_<JOB-ID>.xlsx (and WEBAPP_EXCEL_PATH) with latest DB state."""
    target_run = run
    clean_job_id = job_id.strip().upper() if job_id else None

    if target_run is None:
        q = db.query(Run).filter(Run.status == "finished")
        if clean_job_id:
            q = q.filter(Run.job_id == clean_job_id)
        target_run = q.order_by(desc(Run.started_at), desc(Run.id)).first()

    if clean_job_id is None and target_run is not None and target_run.job_id:
        clean_job_id = target_run.job_id.strip().upper()

    job_row = (
        db.query(Job).filter(Job.job_id == clean_job_id).first()
        if clean_job_id
        else None
    )

    latest_hr_map = _get_latest_hr_decisions_map(db, job_id=clean_job_id)
    hr_decisions_dict: dict[str, dict[str, Any]] = {
        cid: {
            "candidate_id": cid,
            "job_id": clean_job_id or "JOB-2026-001",
            "decision": dec.decision,
            "note": dec.note,
            "timestamp": dec.decided_at_utc,
            "decided_by_email": dec.decided_by_email,
        }
        for cid, dec in latest_hr_map.items()
    }

    evaluations: list[CandidateEvaluation] = []
    candidate_mapping: dict[str, dict[str, str]] = {}
    threshold_val = float(job_row.threshold) if job_row else 70.0
    requires_continuity_val = bool(job_row.requires_continuity) if job_row else False
    model_val = str(job_row.model) if job_row else "gemini-4-argon"

    if target_run is not None:
        threshold_val = float(target_run.threshold)
        model_val = target_run.model
        try:
            s_data = json.loads(target_run.settings_json or "{}")
            requires_continuity_val = bool(s_data.get("requires_continuity", requires_continuity_val))
        except Exception:
            pass

        cand_rows = (
            db.query(CandidateResult)
            .filter(CandidateResult.run_id == target_run.id)
            .order_by(CandidateResult.candidate_id)
            .all()
        )
        for cr in cand_rows:
            ev_data = json.loads(cr.evidence_json or "{}")
            reasons = json.loads(cr.review_reasons_json or "[]")
            eval_obj = CandidateEvaluation(
                candidate_id=cr.candidate_id,
                criterion_scores=ev_data.get("criterion_scores", []),
                overall_score=cr.ai_score,
                decision=(
                    cr.ai_decision
                    if cr.ai_decision in ("Shortlisted", "Not Shortlisted")
                    else "Not Shortlisted"
                ),
                confidence=cr.confidence,
                review_reasons=reasons,
                strengths=ev_data.get("strengths") or ["None noted"],
                gaps=ev_data.get("gaps") or ["None noted"],
                reasoning=ev_data.get("reasoning") or f"Scored {cr.ai_score}/100.",
                needs_human_review=len(reasons) > 0,
            )
            evaluations.append(eval_obj)
            candidate_mapping[cr.candidate_id] = {
                "candidate_id": cr.candidate_id,
                "name": cr.name,
                "source_folder": ev_data.get("source_folder", cr.name),
            }

    # Resolve rubric for this job
    job_rubric_file = (
        (_get_jobs_root() / clean_job_id / "rubric.json")
        if clean_job_id
        else Path(tools_module.DEFAULT_RUBRIC_PATH)
    )
    rubric_file = (
        job_rubric_file
        if job_rubric_file.exists()
        else Path(tools_module.DEFAULT_RUBRIC_PATH)
    )
    if rubric_file.exists():
        rubric_obj = JobRubric.model_validate_json(rubric_file.read_text(encoding="utf-8"))
        if job_row and job_row.title:
            rubric_obj.job_title = job_row.title
        rubric_obj.shortlist_threshold = threshold_val
        rubric_obj.requires_continuity = requires_continuity_val
    else:
        jd_file = Path(job_row.jd_path) if (job_row and job_row.jd_path) else Path(tools_module.DEFAULT_ADVERT_PATH)
        advert_text = (
            read_job_advert(str(jd_file))
            if jd_file.exists()
            else f"Job Title: {job_row.title if job_row else 'Sales Executive - Retail and Business Clients'}"
        )
        llm_helper = agent_module.ScreeningAdkLlm(model=model_val)
        rubric_obj = llm_helper._build_rubric_from_advert(advert_text)
        if job_row and job_row.title:
            rubric_obj.job_title = job_row.title
        rubric_obj.shortlist_threshold = threshold_val
        rubric_obj.requires_continuity = requires_continuity_val

    if not evaluations and clean_job_id is None:
        evals_file = Path(tools_module.DEFAULT_EVALUATIONS_PATH)
        if evals_file.exists():
            raw_list = json.loads(evals_file.read_text(encoding="utf-8"))
            evaluations = [CandidateEvaluation.model_validate(item) for item in raw_list]
            default_app = Path(tools_module.DEFAULT_APPLICATIONS_DIR)
            if default_app.exists():
                list_candidates(str(default_app))
                candidate_mapping = get_candidate_mapping()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    effective_job_id = clean_job_id or "JOB-2026-001"
    per_job_excel = _job_excel_path(effective_job_id)

    if evaluations:
        write_results_excel(
            evaluations=evaluations,
            rubric=rubric_obj,
            output_path=str(per_job_excel),
            candidate_mapping=candidate_mapping,
            model_name=model_val,
            hr_decisions=hr_decisions_dict,
            job_id=effective_job_id,
        )
        write_results_excel(
            evaluations=evaluations,
            rubric=rubric_obj,
            output_path=str(WEBAPP_EXCEL_PATH),
            candidate_mapping=candidate_mapping,
            model_name=model_val,
            hr_decisions=hr_decisions_dict,
            job_id=effective_job_id,
        )
        write_results_excel(
            evaluations=evaluations,
            rubric=rubric_obj,
            output_path=str(tools_module.DEFAULT_EXCEL_PATH),
            candidate_mapping=candidate_mapping,
            model_name=model_val,
            hr_decisions=hr_decisions_dict,
            job_id=effective_job_id,
        )
        return str(per_job_excel)

    if per_job_excel.exists():
        return str(per_job_excel)
    if WEBAPP_EXCEL_PATH.exists():
        return str(WEBAPP_EXCEL_PATH)
    if Path(tools_module.DEFAULT_EXCEL_PATH).exists():
        return str(tools_module.DEFAULT_EXCEL_PATH)
    return str(per_job_excel)


def _execute_screening_run(
    run_id: str,
    settings: dict[str, Any],
    job_id: str | None = None,
    jd_path: str | None = None,
    job_title: str | None = None,
) -> None:
    """Background worker that runs the screening_agent pipeline for a specific job and stores results in SQLite."""
    global _ACTIVE_RUN_ID
    app_dir = Path(settings["applications_dir"]).resolve()
    model_name = str(settings["model"])
    threshold = float(settings["threshold"])
    requires_continuity = bool(settings["requires_continuity"])
    clean_job_id = job_id.strip().upper() if job_id else "JOB-2026-001"

    orig_app_dir = tools_module.DEFAULT_APPLICATIONS_DIR
    orig_advert_path = tools_module.DEFAULT_ADVERT_PATH
    orig_rubric_path = tools_module.DEFAULT_RUBRIC_PATH
    orig_excel_path = tools_module.DEFAULT_EXCEL_PATH
    orig_evals_path = tools_module.DEFAULT_EVALUATIONS_PATH
    orig_hr_path = tools_module.DEFAULT_HR_DECISIONS_PATH
    orig_model_env = os.environ.get("MODEL_NAME")
    orig_pipeline_model = agent_module.screening_pipeline.model_name
    orig_save_rubric = agent_module.save_rubric_json
    orig_build_screening = agent_module.build_screening_agent

    job_work_dir = _get_jobs_root() / clean_job_id
    job_work_dir.mkdir(parents=True, exist_ok=True)
    job_rubric_file = job_work_dir / "rubric.json"
    job_excel_file = _job_excel_path(clean_job_id)

    def _hooked_save_rubric(rubric: JobRubric | dict[str, Any], output_path: str | None = None) -> str:
        if isinstance(rubric, JobRubric):
            if job_title:
                rubric.job_title = job_title
            rubric.shortlist_threshold = threshold
            rubric.requires_continuity = requires_continuity
        elif isinstance(rubric, dict):
            if job_title:
                rubric["job_title"] = job_title
            rubric["shortlist_threshold"] = threshold
            rubric["requires_continuity"] = requires_continuity
        saved_path = orig_save_rubric(rubric, output_path=str(job_rubric_file))
        try:
            orig_save_rubric(rubric, output_path=str(orig_rubric_path))
        except Exception:
            pass
        return saved_path

    def _hooked_build_screening(candidate_id: str, model_name: str | None = None):
        prog = _RUN_PROGRESS.get(run_id)
        if prog is not None:
            prog["current_candidate_id"] = candidate_id
            prog["current_candidate_index"] = min(
                prog.get("current_candidate_index", 0) + 1,
                max(prog.get("total_candidates", 1), 1),
            )
        return orig_build_screening(candidate_id, model_name=model_name)

    try:
        tools_module.DEFAULT_APPLICATIONS_DIR = app_dir
        if jd_path and Path(jd_path).exists():
            tools_module.DEFAULT_ADVERT_PATH = Path(jd_path).resolve()
        tools_module.DEFAULT_RUBRIC_PATH = job_rubric_file
        tools_module.DEFAULT_EXCEL_PATH = job_excel_file
        tools_module.DEFAULT_EVALUATIONS_PATH = job_work_dir / "evaluations.json"
        tools_module.DEFAULT_HR_DECISIONS_PATH = job_work_dir / "hr_decisions.json"

        os.environ["MODEL_NAME"] = model_name
        agent_module.screening_pipeline.model_name = model_name
        agent_module.save_rubric_json = _hooked_save_rubric
        agent_module.build_screening_agent = _hooked_build_screening

        # Call screening_agent's run_screening_pipeline on this job's JD & applications_dir
        pipeline_result = run_screening_pipeline()
        raw_evaluations = pipeline_result.get("evaluations") or []

        # Populate candidate mapping for this job's app_dir
        list_candidates(str(app_dir))
        mapping = get_candidate_mapping()

        # Load rubric to enforce threshold & uncertainty rules consistently
        rubric_path = pipeline_result.get("rubric_path") or str(job_rubric_file)
        if rubric_path and Path(rubric_path).exists():
            rubric_obj = JobRubric.model_validate_json(
                Path(rubric_path).read_text(encoding="utf-8")
            )
        else:
            advert_text = read_job_advert(str(tools_module.DEFAULT_ADVERT_PATH))
            rubric_obj = agent_module.ScreeningAdkLlm(model=model_name)._build_rubric_from_advert(
                advert_text
            )
        if job_title:
            rubric_obj.job_title = job_title
        rubric_obj.shortlist_threshold = threshold
        rubric_obj.requires_continuity = requires_continuity

        db = get_session()
        try:
            latest_hr_map = _get_latest_hr_decisions_map(db, job_id=clean_job_id)
            eval_objs: list[CandidateEvaluation] = []

            # Clear any existing candidate_results for this run_id just in case
            db.query(CandidateResult).filter(CandidateResult.run_id == run_id).delete()

            for item in raw_evaluations:
                eval_obj = (
                    item
                    if isinstance(item, CandidateEvaluation)
                    else CandidateEvaluation.model_validate(item)
                )
                cid = eval_obj.candidate_id
                try:
                    raw_app_text = read_application(cid, str(app_dir))
                except Exception:
                    raw_app_text = ""

                # Re-verify decision against custom threshold
                must_have_scores = [
                    cs.score for cs in eval_obj.criterion_scores if cs.category == "must_have"
                ]
                has_core_must_haves = all(s >= 3 for s in must_have_scores) if must_have_scores else True
                if eval_obj.overall_score >= threshold and has_core_must_haves:
                    eval_obj.decision = "Shortlisted"
                else:
                    eval_obj.decision = "Not Shortlisted"

                eval_obj = apply_uncertainty_rules(eval_obj, rubric_obj, raw_app_text)
                eval_obj = sync_decision_and_reasoning(eval_obj, rubric_obj)
                eval_objs.append(eval_obj)

                cand_info = mapping.get(cid, {})
                cand_name = cand_info.get("name", f"Candidate {cid}")
                source_folder = cand_info.get("source_folder", cid)
                cand_folder_path = Path(cand_info.get("folder_path", app_dir / source_folder))
                doc_count = _count_candidate_documents(cand_folder_path)

                hr_dec_row = latest_hr_map.get(cid)
                hr_rec = (
                    {"decision": hr_dec_row.decision, "note": hr_dec_row.note}
                    if hr_dec_row
                    else None
                )
                cand_status = compute_candidate_status(eval_obj, hr_rec)

                evidence_payload = {
                    "criterion_scores": [cs.model_dump() for cs in eval_obj.criterion_scores],
                    "strengths": eval_obj.strengths,
                    "gaps": eval_obj.gaps,
                    "reasoning": eval_obj.reasoning,
                    "needs_human_review": eval_obj.needs_human_review,
                    "source_folder": source_folder,
                    "document_count": doc_count,
                    "threshold": threshold,
                    "job_id": clean_job_id,
                }

                db.add(
                    CandidateResult(
                        run_id=run_id,
                        candidate_id=cid,
                        job_id=clean_job_id,
                        name=cand_name,
                        ai_decision=eval_obj.decision,
                        ai_score=float(eval_obj.overall_score),
                        confidence=float(eval_obj.confidence),
                        status=cand_status,
                        review_reasons_json=json.dumps(list(eval_obj.review_reasons)),
                        evidence_json=json.dumps(evidence_payload),
                    )
                )

            db.flush()
            run_row = db.query(Run).filter(Run.id == run_id).first()

            # Regenerate per-job Excel with merged HR decisions from SQLite before marking run finished
            if run_row is not None:
                _regenerate_excel_from_db(db, run=run_row, job_id=clean_job_id)

            if run_id in _RUN_PROGRESS:
                _RUN_PROGRESS[run_id]["current_candidate_index"] = len(eval_objs)
                _RUN_PROGRESS[run_id]["total_candidates"] = len(eval_objs)

            # Restore globals before releasing lock and marking run finished
            tools_module.DEFAULT_APPLICATIONS_DIR = orig_app_dir
            tools_module.DEFAULT_ADVERT_PATH = orig_advert_path
            tools_module.DEFAULT_RUBRIC_PATH = orig_rubric_path
            tools_module.DEFAULT_EXCEL_PATH = orig_excel_path
            tools_module.DEFAULT_EVALUATIONS_PATH = orig_evals_path
            tools_module.DEFAULT_HR_DECISIONS_PATH = orig_hr_path
            if orig_model_env is None:
                os.environ.pop("MODEL_NAME", None)
            else:
                os.environ["MODEL_NAME"] = orig_model_env
            agent_module.screening_pipeline.model_name = orig_pipeline_model
            agent_module.save_rubric_json = orig_save_rubric
            agent_module.build_screening_agent = orig_build_screening

            with _RUN_LOCK:
                if run_row is not None:
                    run_row.status = "finished"
                    run_row.finished_at = utc_now_iso()
                    run_row.candidate_count = len(eval_objs)
                    run_row.error = None
                db.commit()
                if _ACTIVE_RUN_ID == run_id:
                    _ACTIVE_RUN_ID = None
        finally:
            db.close()

    except Exception as exc:
        db = get_session()
        try:
            with _RUN_LOCK:
                run_row = db.query(Run).filter(Run.id == run_id).first()
                if run_row is not None:
                    run_row.status = "failed"
                    run_row.finished_at = utc_now_iso()
                    run_row.error = str(exc)
                    db.commit()
                if _ACTIVE_RUN_ID == run_id:
                    _ACTIVE_RUN_ID = None
        finally:
            db.close()
    finally:
        tools_module.DEFAULT_APPLICATIONS_DIR = orig_app_dir
        tools_module.DEFAULT_ADVERT_PATH = orig_advert_path
        tools_module.DEFAULT_RUBRIC_PATH = orig_rubric_path
        tools_module.DEFAULT_EXCEL_PATH = orig_excel_path
        tools_module.DEFAULT_EVALUATIONS_PATH = orig_evals_path
        tools_module.DEFAULT_HR_DECISIONS_PATH = orig_hr_path
        if orig_model_env is None:
            os.environ.pop("MODEL_NAME", None)
        else:
            os.environ["MODEL_NAME"] = orig_model_env
        agent_module.screening_pipeline.model_name = orig_pipeline_model
        agent_module.save_rubric_json = orig_save_rubric
        agent_module.build_screening_agent = orig_build_screening
        with _RUN_LOCK:
            if _ACTIVE_RUN_ID == run_id:
                _ACTIVE_RUN_ID = None


# =============================================================================
# Pydantic Request Models
# =============================================================================


class SettingsUpdateRequest(BaseModel):
    """Payload for PUT /api/settings."""

    threshold: float = Field(default=70.0)
    requires_continuity: bool = Field(default=False)
    model: str = Field(default="gemini-4-argon")
    applications_dir: str | None = Field(default=None)
    redact_before_scoring: bool = Field(default=True)


class HrDecisionRequest(BaseModel):
    """Payload for POST /api/candidates/{candidate_id}/decision or /api/jobs/{job_id}/candidates/{candidate_id}/decision."""

    decision: str = Field(description="Shortlisted or Not Shortlisted")
    note: str = Field(default="", description="Optional HR rationale or note")
    job_id: str | None = Field(default=None, description="Optional Job ID when calling /api/candidates/{id}/decision")


class AdminAddUserRequest(BaseModel):
    """Payload for POST /api/admin/users."""

    email: str = Field(description="User email address (lowercase)")
    role: str = Field(default="hr", description="Role: admin or hr")


class AdminUpdateUserRequest(BaseModel):
    """Payload for PATCH/PUT /api/admin/users/{user_target}."""

    role: str | None = Field(default=None, description="Optional new role: admin or hr")
    active: bool | None = Field(default=None, description="Optional active status")


class AdminAddDomainRequest(BaseModel):
    """Payload for POST /api/admin/domains."""

    domain: str = Field(description="Organisation domain, e.g. example.gov")
    role: str = Field(default="hr", description="Role granted to domain users (hr)")


class AdminUpdateDomainRequest(BaseModel):
    """Payload for PATCH/PUT /api/admin/domains/{domain_target}."""

    role: str | None = Field(default=None, description="Optional role (hr)")
    active: bool | None = Field(default=None, description="Optional active status")


def _serialize_allowed_user(row: AllowedUser) -> dict[str, Any]:
    """Serialize an AllowedUser ORM row to a dictionary."""
    email_clean = row.email.strip().lower()
    return {
        "id": row.id,
        "email": email_clean,
        "role": row.role,
        "added_by": row.added_by,
        "added_at_utc": row.added_at_utc,
        "active": bool(row.active),
        "is_root_admin": is_root_admin(email_clean),
        "is_demo_user": email_clean == "hr.demo@example.com",
    }


def _serialize_allowed_domain(row: AllowedDomain) -> dict[str, Any]:
    """Serialize an AllowedDomain ORM row to a dictionary."""
    return {
        "id": row.id,
        "domain": row.domain.strip().lower(),
        "role": row.role,
        "added_by": row.added_by,
        "added_at_utc": row.added_at_utc,
        "active": bool(row.active),
    }


def _find_user_by_target(db: Session, user_target: str) -> AllowedUser | None:
    """Find an AllowedUser by numeric ID or lowercase email."""
    cleaned = user_target.strip()
    if cleaned.isdigit():
        by_id = db.query(AllowedUser).filter(AllowedUser.id == int(cleaned)).first()
        if by_id is not None:
            return by_id
    return db.query(AllowedUser).filter(AllowedUser.email == cleaned.lower()).first()


def _find_domain_by_target(db: Session, domain_target: str) -> AllowedDomain | None:
    """Find an AllowedDomain by numeric ID or lowercase domain string."""
    cleaned = domain_target.strip()
    if cleaned.isdigit():
        by_id = db.query(AllowedDomain).filter(AllowedDomain.id == int(cleaned)).first()
        if by_id is not None:
            return by_id
    dom = cleaned.lower().lstrip("@")
    return db.query(AllowedDomain).filter(AllowedDomain.domain == dom).first()


def _count_other_active_admins(db: Session, exclude_user_id: int) -> int:
    """Count active admin rows in allowed_users excluding the given user ID."""
    return (
        db.query(AllowedUser)
        .filter(
            AllowedUser.id != exclude_user_id,
            AllowedUser.role == "admin",
            AllowedUser.active.is_(True),
        )
        .count()
    )


def _safe_filename(name: str, default: str = "document.txt") -> str:
    """Sanitize a filename to prevent directory traversal."""
    base = Path(str(name).replace("\\", "/")).name.strip()
    base = re.sub(r"[^A-Za-z0-9._\-\s()]", "_", base)
    return base or default


def _safe_folder_name(name: str, default: str = "Candidate") -> str:
    """Sanitize a candidate folder name."""
    cleaned = Path(str(name).replace("\\", "/")).name.strip()
    cleaned = re.sub(r"[^A-Za-z0-9._\-\s()]", "_", cleaned)
    return cleaned or default


def _build_folders_response(app_dir: Path, job_id: str | None = None) -> dict[str, Any]:
    """List candidate folders (or standalone resume files) and their document counts/metadata for a given applications_dir."""
    if not app_dir.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Applications directory not found: {app_dir}",
        )

    candidates = list_candidates(str(app_dir))
    mapping = get_candidate_mapping()
    folders_out: list[dict[str, Any]] = []

    for cand in candidates:
        cid = cand["candidate_id"]
        info = mapping.get(cid, {})
        folder_path = Path(info.get("folder_path", app_dir / cand["source_folder"]))
        files_out: list[dict[str, Any]] = []

        if folder_path.exists():
            candidate_files = (
                [folder_path]
                if folder_path.is_file()
                else sorted(
                    [f for f in folder_path.iterdir() if f.is_file()],
                    key=lambda x: x.name.lower(),
                )
            )
            for fpath in candidate_files:
                fsize = fpath.stat().st_size
                _, parse_status = _extract_single_file_text(fpath)
                doc_type = _classify_file_type(fpath)
                if doc_type == "Document" and len(candidate_files) == 1 and fpath.suffix.lower() in (".pdf", ".docx", ".txt"):
                    doc_type = "CV"
                dl_url = (
                    f"/api/jobs/{job_id}/folders/{cid}/files/{fpath.name}"
                    if job_id
                    else f"/api/folders/{cid}/files/{fpath.name}"
                )
                files_out.append(
                    {
                        "name": fpath.name,
                        "type": doc_type,
                        "extension": fpath.suffix.lower(),
                        "size": fsize,
                        "size_human": _human_size(fsize),
                        "parse_status": parse_status,
                        "download_url": dl_url,
                    }
                )

        doc_count = len(files_out)
        bundle_url = (
            f"/api/jobs/{job_id}/folders/{cid}/download"
            if job_id
            else f"/api/folders/{cid}/download"
        )
        folders_out.append(
            {
                "job_id": job_id,
                "candidate_id": cid,
                "name": info.get("name", cand["source_folder"]),
                "folder_name": cand["source_folder"],
                "file_count": doc_count,
                "document_count": doc_count,
                "documents_label": f"{doc_count} document" if doc_count == 1 else f"{doc_count} documents",
                "download_url": bundle_url,
                "files": files_out,
            }
        )

    return {
        "job_id": job_id,
        "applications_dir": str(app_dir),
        "is_demo_data": _is_demo_applications_dir(app_dir),
        "folders": folders_out,
    }


def _resolve_target_candidate_info(app_dir: Path, candidate_id: str) -> dict[str, str]:
    """Resolve a candidate entry in _CANDIDATE_MAPPING by candidate_id, source_folder, or name."""
    if not app_dir.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Applications directory not found: {app_dir}",
        )

    list_candidates(str(app_dir))
    mapping = get_candidate_mapping()

    cid_upper = candidate_id.strip().upper()
    target_info: dict[str, str] | None = mapping.get(cid_upper)
    if target_info is None:
        for info in mapping.values():
            if (
                info.get("source_folder", "").lower() == candidate_id.strip().lower()
                or info.get("name", "").lower() == candidate_id.strip().lower()
            ):
                target_info = info
                break

    if target_info is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidate folder not found: {candidate_id}",
        )
    return target_info


def _build_candidate_preview_response(
    app_dir: Path, candidate_id: str, job_id: str | None = None
) -> dict[str, Any]:
    """Return extracted text preview (~1500 chars) for each file in a candidate folder or standalone file."""
    target_info = _resolve_target_candidate_info(app_dir, candidate_id)
    resolved_cid = target_info["candidate_id"]
    folder_path = Path(target_info["folder_path"])
    if not folder_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Folder path does not exist for candidate {resolved_cid}",
        )

    candidate_files = (
        [folder_path]
        if folder_path.is_file()
        else sorted(
            [f for f in folder_path.iterdir() if f.is_file()],
            key=lambda x: x.name.lower(),
        )
    )

    file_previews: list[dict[str, Any]] = []
    for fpath in candidate_files:
        text, parse_status = _extract_single_file_text(fpath)
        preview_text = text[:1500]
        doc_type = _classify_file_type(fpath)
        if doc_type == "Document" and len(candidate_files) == 1 and fpath.suffix.lower() in (".pdf", ".docx", ".txt"):
            doc_type = "CV"
        dl_url = (
            f"/api/jobs/{job_id}/folders/{resolved_cid}/files/{fpath.name}"
            if job_id
            else f"/api/folders/{resolved_cid}/files/{fpath.name}"
        )
        file_previews.append(
            {
                "name": fpath.name,
                "type": doc_type,
                "size": fpath.stat().st_size,
                "size_human": _human_size(fpath.stat().st_size),
                "parse_status": parse_status,
                "preview": preview_text,
                "total_chars": len(text),
                "truncated": len(text) > 1500,
                "download_url": dl_url,
            }
        )

    full_combined = read_application(resolved_cid, str(app_dir))
    bundle_url = (
        f"/api/jobs/{job_id}/folders/{resolved_cid}/download"
        if job_id
        else f"/api/folders/{resolved_cid}/download"
    )
    return {
        "job_id": job_id,
        "candidate_id": resolved_cid,
        "name": target_info.get("name", resolved_cid),
        "folder_name": target_info.get("source_folder", resolved_cid),
        "document_count": len(file_previews),
        "documents_label": (
            f"{len(file_previews)} document"
            if len(file_previews) == 1
            else f"{len(file_previews)} documents"
        ),
        "download_url": bundle_url,
        "combined_preview": full_combined[:1500],
        "files": file_previews,
    }


def _resolve_candidate_file_download(
    app_dir: Path, candidate_id: str, filename: str
) -> FileResponse:
    """Return a FileResponse for a specific original document in a candidate's application."""
    target_info = _resolve_target_candidate_info(app_dir, candidate_id)
    folder_path = Path(target_info["folder_path"]).resolve()
    if not folder_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidate path does not exist: {candidate_id}",
        )

    clean_fname = Path(filename.replace("\\", "/")).name.strip()
    if folder_path.is_file():
        if folder_path.name != clean_fname and _safe_filename(folder_path.name) != _safe_filename(clean_fname):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File '{clean_fname}' not found for candidate {candidate_id}",
            )
        target_file = folder_path
    else:
        target_file = (folder_path / clean_fname).resolve()
        if not target_file.is_relative_to(folder_path) or not target_file.is_file():
            # Try case-insensitive match within candidate folder
            matched = next(
                (f for f in folder_path.iterdir() if f.is_file() and f.name.lower() == clean_fname.lower()),
                None,
            )
            if matched is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"File '{clean_fname}' not found for candidate {candidate_id}",
                )
            target_file = matched.resolve()

    return FileResponse(
        path=str(target_file),
        filename=target_file.name,
        media_type="application/octet-stream",
    )


def _resolve_candidate_bundle_download(
    app_dir: Path, candidate_id: str
) -> Response:
    """Download the candidate's single CV file directly, or a .zip archive if multiple files exist."""
    target_info = _resolve_target_candidate_info(app_dir, candidate_id)
    resolved_cid = target_info["candidate_id"]
    folder_path = Path(target_info["folder_path"]).resolve()
    if not folder_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidate path does not exist: {candidate_id}",
        )

    if folder_path.is_file():
        return FileResponse(
            path=str(folder_path),
            filename=folder_path.name,
            media_type="application/octet-stream",
        )

    files = sorted([f for f in folder_path.iterdir() if f.is_file()], key=lambda x: x.name.lower())
    if not files:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No files found for candidate {resolved_cid}",
        )

    if len(files) == 1:
        return FileResponse(
            path=str(files[0]),
            filename=files[0].name,
            media_type="application/octet-stream",
        )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for fpath in files:
            zf.write(fpath, arcname=fpath.name)
    zip_bytes = buf.getvalue()
    safe_cand = _safe_folder_name(target_info.get("name", resolved_cid))
    zip_filename = f"{resolved_cid}_{safe_cand}.zip"
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_filename}"'},
    )


def _start_run_for_job(
    db: Session,
    actor_email: str,
    job: Job | None = None,
) -> dict[str, Any]:
    """Start a background screening run for the given job (or default settings if job is None)."""
    global _ACTIVE_RUN_ID
    with _RUN_LOCK:
        running_in_db = db.query(Run).filter(Run.status == "running").first()
        if _ACTIVE_RUN_ID is not None or running_in_db is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A screening run is already in progress. Please wait for it to finish.",
            )

        if job is None:
            job = _ensure_default_job(db, actor_email=actor_email)

        run_settings = {
            "job_id": job.job_id,
            "title": job.title,
            "jd_path": job.jd_path,
            "applications_dir": job.applications_dir,
            "threshold": float(job.threshold),
            "requires_continuity": bool(job.requires_continuity),
            "model": str(job.model),
            "redact_before_scoring": True,
        }
        app_dir = Path(job.applications_dir).resolve()
        if not app_dir.exists():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Applications directory does not exist for job {job.job_id}: {app_dir}",
            )

        candidates = list_candidates(str(app_dir))
        total_candidates = len(candidates)

        run_id = f"run_{uuid.uuid4().hex[:10]}"
        started_at = utc_now_iso()

        new_run = Run(
            id=run_id,
            job_id=job.job_id,
            started_at=started_at,
            finished_at=None,
            status="running",
            settings_json=json.dumps(run_settings),
            model=job.model,
            threshold=float(job.threshold),
            candidate_count=total_candidates,
            error=None,
        )
        db.add(new_run)

        db.add(
            AuditLog(
                at_utc=started_at,
                actor_email=actor_email,
                action="start_run",
                detail=(
                    f"Started screening run {run_id} for job {job.job_id} ({job.title}) "
                    f"on {total_candidates} candidates (model: {job.model}, threshold: {job.threshold})."
                ),
            )
        )
        db.commit()

        _ACTIVE_RUN_ID = run_id
        _RUN_PROGRESS[run_id] = {
            "job_id": job.job_id,
            "current_candidate_index": 0,
            "total_candidates": total_candidates,
            "current_candidate_id": None,
        }

        worker = threading.Thread(
            target=_execute_screening_run,
            args=(run_id, run_settings, job.job_id, job.jd_path, job.title),
            daemon=True,
        )
        worker.start()

    return {
        "run_id": run_id,
        "job_id": job.job_id,
        "job_title": job.title,
        "status": "running",
        "started_at": started_at,
        "candidate_count": total_candidates,
        "current_candidate_index": 0,
        "total_candidates": total_candidates,
    }


def _build_job_results_payload(
    db: Session,
    job_id: str | None = None,
    needs_review_only: bool = False,
    search: str = "",
    sort_by: str = "default",
    page: int = 1,
    page_size: int = 25,
) -> dict[str, Any]:
    """Build the results response for a specific job_id (or the latest finished run if job_id is None)."""
    clean_job_id = job_id.strip().upper() if job_id else None
    job_row: Job | None = None
    if clean_job_id:
        job_row = _get_job_or_404(db, clean_job_id)

    run_query = db.query(Run).filter(Run.status == "finished")
    if clean_job_id:
        run_query = run_query.filter(Run.job_id == clean_job_id)
    latest_run = run_query.order_by(desc(Run.started_at), desc(Run.id)).first()

    if latest_run is None:
        return {
            "job": _serialize_job(db, job_row) if job_row else None,
            "job_id": clean_job_id,
            "run": None,
            "summary": {
                "total_candidates": 0,
                "needs_review": 0,
                "ai_decided": 0,
                "hr_decided": 0,
            },
            "pagination": {
                "page": max(1, page),
                "page_size": max(1, page_size),
                "total_items": 0,
                "total_pages": 1,
            },
            "results": [],
        }

    effective_job_id = clean_job_id or latest_run.job_id or "JOB-2026-001"
    if job_row is None and effective_job_id:
        job_row = db.query(Job).filter(Job.job_id == effective_job_id).first()

    cand_rows = (
        db.query(CandidateResult)
        .filter(CandidateResult.run_id == latest_run.id)
        .all()
    )
    latest_hr_map = _get_latest_hr_decisions_map(db, job_id=effective_job_id)
    threshold = float(latest_run.threshold)

    app_dir = Path(job_row.applications_dir) if job_row else Path(load_settings()["applications_dir"])

    merged_results: list[dict[str, Any]] = []
    needs_review_count = 0
    ai_decided_count = 0
    hr_decided_count = 0

    for cr in cand_rows:
        cid = cr.candidate_id
        review_codes: list[str] = json.loads(cr.review_reasons_json or "[]")
        evidence: dict[str, Any] = json.loads(cr.evidence_json or "{}")
        hr_dec = latest_hr_map.get(cid)

        if hr_dec is not None:
            effective_status = "HR decided"
            final_decision = hr_dec.decision
            hr_decision_info = {
                "job_id": effective_job_id,
                "decision": hr_dec.decision,
                "note": hr_dec.note,
                "decided_by_email": hr_dec.decided_by_email,
                "decided_at_utc": hr_dec.decided_at_utc,
            }
            hr_decided_count += 1
        else:
            if len(review_codes) > 0 or evidence.get("needs_human_review"):
                effective_status = "Needs HR review"
                needs_review_count += 1
            else:
                effective_status = "AI decided"
                ai_decided_count += 1
            final_decision = cr.ai_decision
            hr_decision_info = None

        plain_reasons = format_review_reasons(
            review_codes,
            score=cr.ai_score,
            threshold=threshold,
            confidence=cr.confidence,
            evidence=evidence,
        )
        why_plain = build_plain_why_summary(
            ai_decision=cr.ai_decision,
            ai_score=cr.ai_score,
            threshold=threshold,
            confidence=cr.confidence,
            review_reasons=review_codes,
            evidence=evidence,
        )
        why_short, why_truncated = _truncate_why_text(why_plain, max_chars=140)
        status_badge = format_status_badge(effective_status)
        ai_rec_plain = format_ai_recommendation(cr.ai_decision)

        source_folder = evidence.get("source_folder", cr.name)
        doc_count = evidence.get("document_count")
        if doc_count is None:
            doc_count = _count_candidate_documents(app_dir / source_folder)
        doc_count = int(doc_count)

        merged_results.append(
            {
                "job_id": effective_job_id,
                "candidate_id": cid,
                "name": cr.name,
                "source_folder": source_folder,
                "document_count": doc_count,
                "documents_label": f"{doc_count} document" if doc_count == 1 else f"{doc_count} documents",
                "ai_score": round(float(cr.ai_score), 1),
                "score_display": f"{round(float(cr.ai_score), 1)} / 100",
                "ai_decision": cr.ai_decision,
                "ai_recommendation_plain": ai_rec_plain,
                "confidence": round(float(cr.confidence), 2),
                "confidence_percent": int(round(float(cr.confidence) * 100)),
                "status": effective_status,
                "status_badge": status_badge,
                "review_reasons": review_codes,
                "review_reasons_plain": plain_reasons,
                "reasons_sentences": plain_reasons,
                "why": why_plain,
                "why_plain": why_plain,
                "why_full": why_plain,
                "why_short": why_short,
                "why_truncated": why_truncated,
                "reasoning": evidence.get("reasoning", why_plain),
                "strengths": evidence.get("strengths", []),
                "gaps": evidence.get("gaps", []),
                "criterion_scores": evidence.get("criterion_scores", []),
                "final_decision": final_decision,
                "hr_decision": hr_decision_info,
            }
        )

    total_all = len(merged_results)

    # Apply optional filter ("Needs your review" toggle) and search (name or candidate_id)
    filtered = list(merged_results)
    if needs_review_only:
        filtered = [r for r in filtered if r["status"] == "Needs HR review"]

    search_clean = (search or "").strip().lower()
    if search_clean:
        filtered = [
            r
            for r in filtered
            if search_clean in r["name"].lower()
            or search_clean in r["candidate_id"].lower()
        ]

    # Sort according to sort_by
    sort_key = (sort_by or "default").strip().lower()
    if sort_key == "score_desc":
        filtered.sort(key=lambda r: (-float(r["ai_score"]), r["candidate_id"]))
    elif sort_key == "score_asc":
        filtered.sort(key=lambda r: (float(r["ai_score"]), r["candidate_id"]))
    elif sort_key == "name":
        filtered.sort(key=lambda r: (r["name"].lower(), r["candidate_id"]))
    elif sort_key == "candidate_id":
        filtered.sort(key=lambda r: r["candidate_id"])
    elif sort_key == "status":
        status_order = {"Needs HR review": 0, "HR decided": 1, "AI decided": 2}
        filtered.sort(
            key=lambda r: (status_order.get(r["status"], 3), -float(r["ai_score"]))
        )
    else:
        # Default: "Needs HR review" first, then score descending
        filtered.sort(
            key=lambda r: (
                0 if r["status"] == "Needs HR review" else 1,
                -float(r["ai_score"]),
            )
        )

    # Pagination (default 25 per page)
    safe_page_size = max(1, min(int(page_size or 25), 200))
    total_items = len(filtered)
    total_pages = max(1, math.ceil(total_items / safe_page_size))
    safe_page = max(1, min(int(page or 1), total_pages))
    start_idx = (safe_page - 1) * safe_page_size
    paginated_results = filtered[start_idx : start_idx + safe_page_size]

    return {
        "job": _serialize_job(db, job_row) if job_row else None,
        "job_id": effective_job_id,
        "run": {
            "id": latest_run.id,
            "job_id": effective_job_id,
            "started_at": latest_run.started_at,
            "finished_at": latest_run.finished_at,
            "status": latest_run.status,
            "model": latest_run.model,
            "threshold": latest_run.threshold,
            "candidate_count": latest_run.candidate_count,
        },
        "summary": {
            "total_candidates": total_all,
            "needs_review": needs_review_count,
            "ai_decided": ai_decided_count,
            "hr_decided": hr_decided_count,
        },
        "pagination": {
            "page": safe_page,
            "page_size": safe_page_size,
            "total_items": total_items,
            "total_pages": total_pages,
        },
        "results": paginated_results,
    }


def _record_decision_for_job_candidate(
    db: Session,
    candidate_id: str,
    payload: HrDecisionRequest,
    actor_email: str,
    job_id: str | None = None,
) -> dict[str, Any]:
    """Record an HR decision keyed by (job_id, candidate_id) and regenerate the job's Excel file."""
    cid = candidate_id.strip().upper()
    raw_dec = payload.decision.strip().lower()
    if raw_dec in ("shortlisted", "shortlist"):
        normalized_decision = "Shortlisted"
    elif raw_dec in ("not shortlisted", "not_shortlisted", "not shortlist", "rejected", "reject"):
        normalized_decision = "Not Shortlisted"
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="decision must be 'Shortlisted' or 'Not Shortlisted'.",
        )

    note = (payload.note or "").strip()
    now_utc = utc_now_iso()

    effective_job_id = (job_id or payload.job_id or "").strip().upper() or None
    if effective_job_id:
        _get_job_or_404(db, effective_job_id)

    run_query = db.query(Run).filter(Run.status == "finished")
    if effective_job_id:
        run_query = run_query.filter(Run.job_id == effective_job_id)
    latest_run = run_query.order_by(desc(Run.started_at), desc(Run.id)).first()

    if effective_job_id is None:
        if latest_run is not None and latest_run.job_id:
            effective_job_id = latest_run.job_id
        else:
            default_job = _ensure_default_job(db, actor_email=actor_email)
            effective_job_id = default_job.job_id

    run_id = latest_run.id if latest_run is not None else None

    hr_row = HrDecision(
        job_id=effective_job_id,
        candidate_id=cid,
        run_id=run_id,
        decision=normalized_decision,
        note=note,
        decided_by_email=actor_email,
        decided_at_utc=now_utc,
    )
    db.add(hr_row)

    if latest_run is not None:
        cand_res = (
            db.query(CandidateResult)
            .filter(
                CandidateResult.run_id == latest_run.id,
                CandidateResult.candidate_id == cid,
            )
            .first()
        )
        if cand_res is not None:
            cand_res.status = "HR decided"

    detail_msg = f"Recorded HR decision for {cid} on job {effective_job_id}: {normalized_decision}"
    if note:
        detail_msg += f" (Note: {note})"

    db.add(
        AuditLog(
            at_utc=now_utc,
            actor_email=actor_email,
            action="hr_decision",
            detail=detail_msg,
        )
    )
    db.commit()
    db.refresh(hr_row)

    try:
        record_hr_decision(candidate_id=cid, decision=normalized_decision, note=note)
    except Exception:
        pass
    excel_path = _regenerate_excel_from_db(db, run=latest_run, job_id=effective_job_id)

    return {
        "id": hr_row.id,
        "job_id": effective_job_id,
        "candidate_id": cid,
        "run_id": run_id,
        "decision": normalized_decision,
        "note": note,
        "decided_by_email": actor_email,
        "decided_at_utc": now_utc,
        "status": "HR decided",
        "status_badge": "You decided",
        "excel_path": excel_path,
    }


# =============================================================================
# FastAPI Application Factory
# =============================================================================


from contextlib import asynccontextmanager


def create_webapp(initialize_db: bool = True) -> FastAPI:
    """Create and configure the HR Screening Web Application."""
    if initialize_db:
        init_db()
        if not _is_test_json_fallback_active():
            migrate_access_control()

    @asynccontextmanager
    async def _lifespan(_app: FastAPI):
        init_db()
        if not _is_test_json_fallback_active():
            migrate_access_control()
        yield

    app = FastAPI(
        title="Candidate Screening HR Web Application",
        description="Human-friendly web app for HR to manage jobs, view CVs, run screening, and record decisions.",
        version="1.1.0",
        lifespan=_lifespan,
    )

    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/health")
    def health_check() -> dict[str, Any]:
        """Public health check endpoint."""
        return {
            "status": "ok",
            "service": "screening_webapp",
            "oauth_client_id": GOOGLE_CLIENT_ID,
            "demo_test_auth_enabled": is_demo_test_auth_enabled(),
        }

    @app.get("/", response_class=HTMLResponse)
    def index_page() -> HTMLResponse:
        """Serve the single-page HR web application (includes the Google Sign-In screen)."""
        index_file = STATIC_DIR / "index.html"
        if not index_file.exists():
            return HTMLResponse("<h1>HR Candidate Screening App</h1>")
        return HTMLResponse(index_file.read_text(encoding="utf-8"))

    @app.post("/api/auth/demo")
    def demo_sso_sign_in(
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        """Instant 1-click Demo SSO Sign-In (Head of Talent Acquisition)."""
        init_db()
        email = "guruprem.saginadham@sybyl.com"
        _ensure_demo_seeded_for_sso(db, actor_email=email)
        return {
            "authenticated": True,
            "token": f"sso-session:{email}",
            "email": email,
            "name": "Head of Talent Acquisition",
            "role": "admin",
        }

    @app.post("/api/auth/sso-email")
    async def work_email_sso_sign_in(
        request: Request,
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        """Work Email Enterprise SSO Sign-In."""
        init_db()
        try:
            body = await request.json()
        except Exception:
            body = {}
        email = str(body.get("email") or "").strip().lower()
        if not email or "@" not in email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please enter a valid work email address.",
            )
        _ensure_demo_seeded_for_sso(db, actor_email=email)
        return {
            "authenticated": True,
            "token": f"sso-session:{email}",
            "email": email,
            "name": email.split("@")[0].replace(".", " ").title(),
        }

    @app.get("/api/me")
    def get_current_user(
        claims: dict[str, Any] = Depends(require_hr_auth),
    ) -> dict[str, Any]:
        """Return the signed-in HR user profile, role, admin status, and demo status."""
        settings = load_settings()
        role = str(claims.get("role") or "hr")
        return {
            "email": claims.get("email"),
            "name": claims.get("name") or claims.get("email"),
            "role": role,
            "is_admin": bool(claims.get("is_admin", role == "admin")),
            "is_root_admin": bool(claims.get("is_root_admin", False)),
            "is_demo_user": bool(claims.get("is_demo_user", False)),
            "demo_mode": bool(claims.get("demo_mode")) or _is_demo_applications_dir(settings["applications_dir"]),
            "oauth_client_id": GOOGLE_CLIENT_ID,
        }

    # =========================================================================
    # T019: Job Management & Per-Job Screening Endpoints
    # =========================================================================

    @app.get("/api/jobs")
    def list_jobs_endpoint(
        search: str = Query(default="", description="Optional search by Job ID or title"),
        claims: dict[str, Any] = Depends(require_hr_auth),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        """Return all configured jobs ordered newest first, with candidate counts and last run status."""
        _ = claims
        init_db()
        jobs = db.query(Job).order_by(desc(Job.created_at_utc), desc(Job.job_id)).all()
        search_clean = (search or "").strip().lower()
        serialized = [_serialize_job(db, j) for j in jobs]
        if search_clean:
            serialized = [
                j
                for j in serialized
                if search_clean in j["job_id"].lower() or search_clean in j["title"].lower()
            ]
        return {"jobs": serialized}

    @app.post("/api/jobs")
    async def create_job_endpoint(
        request: Request,
        claims: dict[str, Any] = Depends(require_hr_auth),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        """Create a new job with an auto-generated unique Job ID (JOB-2026-001, ...).

        Accepts either:
        - multipart/form-data: title, jd_file (.docx/.pdf/.txt) or jd_path, cv_files + cv_paths
          (from folder picker) or applications_dir, threshold, requires_continuity, model
        - application/json: title, jd_path (or jd_text + jd_filename), applications_dir,
          threshold, requires_continuity, model
        """
        init_db()
        defaults = load_settings()
        actor_email = str(claims.get("email") or "unknown")
        content_type = (request.headers.get("content-type") or "").lower()

        job_id = _generate_next_job_id(db)
        job_root = _get_jobs_root() / job_id
        jd_dir = job_root / "jd"
        apps_upload_dir = job_root / "applications"

        title = ""
        threshold = float(defaults["threshold"])
        requires_continuity = bool(defaults["requires_continuity"])
        model = str(defaults["model"])
        jd_filename = ""
        resolved_jd_path: Path | None = None
        resolved_apps_dir: Path | None = None

        if "application/json" in content_type:
            body = await request.json()
            title = str(body.get("title") or "").strip()
            if "threshold" in body and body["threshold"] is not None:
                threshold = float(body["threshold"])
            if "requires_continuity" in body and body["requires_continuity"] is not None:
                requires_continuity = bool(body["requires_continuity"])
            if body.get("model"):
                model = str(body["model"]).strip()

            if body.get("jd_path"):
                resolved_jd_path = validate_jd_path(str(body["jd_path"]))
                jd_filename = resolved_jd_path.name
            elif body.get("jd_text"):
                jd_dir.mkdir(parents=True, exist_ok=True)
                jd_filename = _safe_filename(str(body.get("jd_filename") or "job_advert.txt"))
                if Path(jd_filename).suffix.lower() not in ALLOWED_JD_EXTENSIONS:
                    jd_filename += ".txt"
                resolved_jd_path = jd_dir / jd_filename
                resolved_jd_path.write_text(str(body["jd_text"]), encoding="utf-8")
            elif Path(tools_module.DEFAULT_ADVERT_PATH).exists():
                resolved_jd_path = Path(tools_module.DEFAULT_ADVERT_PATH).resolve()
                jd_filename = resolved_jd_path.name

            if body.get("applications_dir"):
                resolved_apps_dir = validate_applications_dir(str(body["applications_dir"]))
        else:
            form = await request.form()
            title = str(form.get("title") or "").strip()
            if form.get("threshold") not in (None, ""):
                threshold = float(str(form.get("threshold")))
            if form.get("requires_continuity") not in (None, ""):
                raw_cont = str(form.get("requires_continuity")).strip().lower()
                requires_continuity = raw_cont in ("1", "true", "yes", "on")
            if form.get("model"):
                model = str(form.get("model")).strip()

            # 1. Handle JD upload or path
            jd_upload = form.get("jd_file")
            if jd_upload is not None and hasattr(jd_upload, "filename") and jd_upload.filename:
                safe_jd = _safe_filename(jd_upload.filename, default="job_advert.docx")
                ext = Path(safe_jd).suffix.lower()
                if ext not in ALLOWED_JD_EXTENSIONS:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Job description file must be a .docx, .pdf, or .txt file.",
                    )
                jd_dir.mkdir(parents=True, exist_ok=True)
                resolved_jd_path = jd_dir / safe_jd
                content_bytes = await jd_upload.read()
                if not content_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Uploaded job description file is empty.",
                    )
                resolved_jd_path.write_bytes(content_bytes)
                jd_filename = safe_jd
            elif form.get("jd_path"):
                resolved_jd_path = validate_jd_path(str(form.get("jd_path")))
                jd_filename = resolved_jd_path.name

            # 2. Handle CV folder upload (cv_files + optional cv_paths) or applications_dir path
            cv_uploads = [
                item
                for item in form.getlist("cv_files")
                if hasattr(item, "filename") and item.filename
            ]
            cv_rel_paths = [str(p) for p in form.getlist("cv_paths")]

            if cv_uploads:
                apps_upload_dir.mkdir(parents=True, exist_ok=True)
                saved_any = False
                parsed_uploads: list[tuple[Any, list[str], str]] = []
                subfolder_primary_counts: dict[str, int] = {}
                for idx, upload_item in enumerate(cv_uploads):
                    rel_raw = (
                        cv_rel_paths[idx]
                        if idx < len(cv_rel_paths) and cv_rel_paths[idx].strip()
                        else (upload_item.filename or "")
                    )
                    parts = [
                        p.strip()
                        for p in rel_raw.replace("\\", "/").split("/")
                        if p.strip() and p.strip() not in (".", "..")
                    ]
                    if not parts:
                        continue
                    fname = _safe_filename(parts[-1])
                    if Path(fname).suffix.lower() not in ALLOWED_CV_EXTENSIONS:
                        continue
                    parsed_uploads.append((upload_item, parts, fname))
                    if len(parts) >= 3 and not tools_module._is_complementary_doc(Path(fname)):
                        sub_key = _safe_folder_name(parts[-2])
                        subfolder_primary_counts[sub_key] = subfolder_primary_counts.get(sub_key, 0) + 1

                for upload_item, parts, fname in parsed_uploads:
                    if len(parts) >= 3:
                        sub_key = _safe_folder_name(parts[-2])
                        if subfolder_primary_counts.get(sub_key, 0) >= 2:
                            cand_folder_name = _safe_folder_name(Path(fname).stem)
                        else:
                            cand_folder_name = sub_key
                    else:
                        # Flat folder upload (e.g. Sample_Resumes/Resume1.pdf) or single file:
                        # 1 file = 1 candidate review
                        cand_folder_name = _safe_folder_name(Path(fname).stem)

                    dest_folder = apps_upload_dir / cand_folder_name
                    dest_folder.mkdir(parents=True, exist_ok=True)
                    file_bytes = await upload_item.read()
                    (dest_folder / fname).write_bytes(file_bytes)
                    saved_any = True

                if not saved_any:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="No supported candidate documents (.pdf, .docx, .eml, .txt) were found in the selected folder.",
                    )
                resolved_apps_dir = apps_upload_dir
            elif form.get("applications_dir"):
                resolved_apps_dir = validate_applications_dir(str(form.get("applications_dir")))

        if not title:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Job Title is required.",
            )
        if model not in ALLOWED_MODELS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid model '{model}'. Allowed models: {', '.join(ALLOWED_MODELS)}.",
            )
        if threshold < 0.0 or threshold > 100.0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Threshold must be between 0 and 100.",
            )
        if resolved_jd_path is None or not resolved_jd_path.exists():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please upload a Job Description file (.docx, .pdf, or .txt) or provide a valid jd_path.",
            )
        if resolved_apps_dir is None or not resolved_apps_dir.exists():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please upload a Candidate CVs folder or provide a valid applications_dir path.",
            )
        if _count_candidate_folders(resolved_apps_dir) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The candidate CVs folder does not contain any candidate sub-folders.",
            )

        now_utc = utc_now_iso()
        job_row = Job(
            job_id=job_id,
            title=title,
            jd_filename=jd_filename or resolved_jd_path.name,
            jd_path=str(resolved_jd_path.resolve()),
            applications_dir=str(resolved_apps_dir.resolve()),
            threshold=threshold,
            requires_continuity=requires_continuity,
            model=model,
            created_at_utc=now_utc,
            created_by_email=actor_email,
        )
        db.add(job_row)
        db.add(
            AuditLog(
                at_utc=now_utc,
                actor_email=actor_email,
                action="create_job",
                detail=(
                    f"Created job {job_id} ('{title}') with {_count_candidate_folders(resolved_apps_dir)} "
                    f"candidate folders (threshold={threshold}, model={model})."
                ),
            )
        )
        db.commit()
        db.refresh(job_row)
        serialized = _serialize_job(db, job_row)
        return {**serialized, "job": serialized}

    @app.get("/api/jobs/{job_id}")
    def get_job_endpoint(
        job_id: str,
        claims: dict[str, Any] = Depends(require_hr_auth),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        """Return details for a specific job_id."""
        _ = claims
        init_db()
        job = _get_job_or_404(db, job_id)
        return _serialize_job(db, job)

    @app.get("/api/jobs/{job_id}/folders")
    def get_job_folders_endpoint(
        job_id: str,
        claims: dict[str, Any] = Depends(require_hr_auth),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        """List candidate folders and document counts for a specific job."""
        _ = claims
        init_db()
        job = _get_job_or_404(db, job_id)
        return _build_folders_response(Path(job.applications_dir).resolve(), job_id=job.job_id)

    @app.get("/api/jobs/{job_id}/folders/{candidate_id}/preview")
    def get_job_candidate_preview_endpoint(
        job_id: str,
        candidate_id: str,
        claims: dict[str, Any] = Depends(require_hr_auth),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        """Return extracted text preview (~1500 chars) for each file in a candidate folder of a job."""
        _ = claims
        init_db()
        job = _get_job_or_404(db, job_id)
        return _build_candidate_preview_response(
            Path(job.applications_dir).resolve(), candidate_id=candidate_id, job_id=job.job_id
        )

    @app.get("/api/jobs/{job_id}/folders/{candidate_id}/files/{filename}")
    def download_job_candidate_file_endpoint(
        job_id: str,
        candidate_id: str,
        filename: str,
        claims: dict[str, Any] = Depends(require_hr_auth),
        db: Session = Depends(get_db),
    ) -> Response:
        """Download a specific original document for a candidate in a job."""
        _ = claims
        init_db()
        job = _get_job_or_404(db, job_id)
        return _resolve_candidate_file_download(
            Path(job.applications_dir).resolve(), candidate_id=candidate_id, filename=filename
        )

    @app.get("/api/jobs/{job_id}/folders/{candidate_id}/download")
    def download_job_candidate_bundle_endpoint(
        job_id: str,
        candidate_id: str,
        claims: dict[str, Any] = Depends(require_hr_auth),
        db: Session = Depends(get_db),
    ) -> Response:
        """Download original document (or ZIP bundle of documents) for a candidate in a job."""
        _ = claims
        init_db()
        job = _get_job_or_404(db, job_id)
        return _resolve_candidate_bundle_download(
            Path(job.applications_dir).resolve(), candidate_id=candidate_id
        )

    @app.post("/api/jobs/{job_id}/runs")
    def start_job_screening_run_endpoint(
        job_id: str,
        claims: dict[str, Any] = Depends(require_hr_auth),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        """Start a screening run specifically for job_id using its JD, CV folder, and settings."""
        init_db()
        job = _get_job_or_404(db, job_id)
        actor_email = str(claims.get("email") or "unknown")
        return _start_run_for_job(db=db, actor_email=actor_email, job=job)

    @app.get("/api/jobs/{job_id}/results")
    def get_job_results_endpoint(
        job_id: str,
        needs_review_only: bool = Query(default=False),
        search: str = Query(default=""),
        sort_by: str = Query(default="default"),
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=25, ge=1, le=200),
        claims: dict[str, Any] = Depends(require_hr_auth),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        """Return candidate results for the latest finished run of job_id."""
        _ = claims
        init_db()
        return _build_job_results_payload(
            db=db,
            job_id=job_id,
            needs_review_only=needs_review_only,
            search=search,
            sort_by=sort_by,
            page=page,
            page_size=page_size,
        )

    @app.post("/api/jobs/{job_id}/candidates/{candidate_id}/decision")
    def post_job_candidate_decision_endpoint(
        job_id: str,
        candidate_id: str,
        payload: HrDecisionRequest,
        claims: dict[str, Any] = Depends(require_hr_auth),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        """Record an HR decision keyed by (job_id, candidate_id) and regenerate the job's Excel file."""
        init_db()
        actor_email = str(claims.get("email") or "unknown")
        return _record_decision_for_job_candidate(
            db=db,
            candidate_id=candidate_id,
            payload=payload,
            actor_email=actor_email,
            job_id=job_id,
        )

    @app.get("/api/jobs/{job_id}/export.xlsx")
    def export_job_excel_endpoint(
        job_id: str,
        claims: dict[str, Any] = Depends(require_hr_auth),
        db: Session = Depends(get_db),
    ) -> FileResponse:
        """Download screening_results_<JOB-ID>.xlsx for the specified job."""
        _ = claims
        init_db()
        job = _get_job_or_404(db, job_id)
        excel_path_str = _regenerate_excel_from_db(db, job_id=job.job_id)
        excel_path = Path(excel_path_str)
        if not excel_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Excel results file has not been generated yet for {job.job_id}. Please run screening first.",
            )
        return FileResponse(
            path=str(excel_path),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=f"screening_results_{job.job_id}.xlsx",
        )

    # =========================================================================
    # Existing / Shared Endpoints (with optional job_id support)
    # =========================================================================

    @app.get("/api/folders")
    def get_folders(
        job_id: str | None = Query(default=None),
        claims: dict[str, Any] = Depends(require_hr_auth),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        """List candidate application folders and their files (name, type, size, parse status, document_count)."""
        _ = claims
        init_db()
        if job_id:
            job = _get_job_or_404(db, job_id)
            return _build_folders_response(Path(job.applications_dir).resolve(), job_id=job.job_id)

        settings = load_settings()
        app_dir = Path(settings["applications_dir"]).resolve()
        if not app_dir.exists():
            latest_job = db.query(Job).order_by(desc(Job.created_at_utc), desc(Job.job_id)).first()
            if latest_job is not None and Path(latest_job.applications_dir).exists():
                return _build_folders_response(
                    Path(latest_job.applications_dir).resolve(), job_id=latest_job.job_id
                )
        return _build_folders_response(app_dir, job_id=None)

    @app.get("/api/folders/{candidate_id}/preview")
    def get_candidate_preview(
        candidate_id: str,
        job_id: str | None = Query(default=None),
        claims: dict[str, Any] = Depends(require_hr_auth),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        """Return extracted text preview (~1500 chars) for each file in a candidate folder."""
        _ = claims
        init_db()
        if job_id:
            job = _get_job_or_404(db, job_id)
            return _build_candidate_preview_response(
                Path(job.applications_dir).resolve(), candidate_id=candidate_id, job_id=job.job_id
            )

        settings = load_settings()
        app_dir = Path(settings["applications_dir"]).resolve()
        if not app_dir.exists():
            latest_job = db.query(Job).order_by(desc(Job.created_at_utc), desc(Job.job_id)).first()
            if latest_job is not None and Path(latest_job.applications_dir).exists():
                return _build_candidate_preview_response(
                    Path(latest_job.applications_dir).resolve(),
                    candidate_id=candidate_id,
                    job_id=latest_job.job_id,
                )
        return _build_candidate_preview_response(app_dir, candidate_id=candidate_id, job_id=None)

    @app.get("/api/folders/{candidate_id}/files/{filename}")
    def download_candidate_file(
        candidate_id: str,
        filename: str,
        job_id: str | None = Query(default=None),
        claims: dict[str, Any] = Depends(require_hr_auth),
        db: Session = Depends(get_db),
    ) -> Response:
        """Download a specific original document for a candidate."""
        _ = claims
        init_db()
        if job_id:
            job = _get_job_or_404(db, job_id)
            return _resolve_candidate_file_download(
                Path(job.applications_dir).resolve(), candidate_id=candidate_id, filename=filename
            )

        settings = load_settings()
        app_dir = Path(settings["applications_dir"]).resolve()
        if not app_dir.exists():
            latest_job = db.query(Job).order_by(desc(Job.created_at_utc), desc(Job.job_id)).first()
            if latest_job is not None and Path(latest_job.applications_dir).exists():
                return _resolve_candidate_file_download(
                    Path(latest_job.applications_dir).resolve(),
                    candidate_id=candidate_id,
                    filename=filename,
                )
        return _resolve_candidate_file_download(app_dir, candidate_id=candidate_id, filename=filename)

    @app.get("/api/folders/{candidate_id}/download")
    def download_candidate_bundle(
        candidate_id: str,
        job_id: str | None = Query(default=None),
        claims: dict[str, Any] = Depends(require_hr_auth),
        db: Session = Depends(get_db),
    ) -> Response:
        """Download original document (or ZIP bundle) for a candidate."""
        _ = claims
        init_db()
        if job_id:
            job = _get_job_or_404(db, job_id)
            return _resolve_candidate_bundle_download(
                Path(job.applications_dir).resolve(), candidate_id=candidate_id
            )

        settings = load_settings()
        app_dir = Path(settings["applications_dir"]).resolve()
        if not app_dir.exists():
            latest_job = db.query(Job).order_by(desc(Job.created_at_utc), desc(Job.job_id)).first()
            if latest_job is not None and Path(latest_job.applications_dir).exists():
                return _resolve_candidate_bundle_download(
                    Path(latest_job.applications_dir).resolve(), candidate_id=candidate_id
                )
        return _resolve_candidate_bundle_download(app_dir, candidate_id=candidate_id)

    @app.get("/api/settings")
    def get_settings_endpoint(
        claims: dict[str, Any] = Depends(require_hr_auth),
    ) -> dict[str, Any]:
        """Return current screening settings."""
        _ = claims
        return load_settings()

    @app.put("/api/settings")
    def update_settings_endpoint(
        payload: SettingsUpdateRequest,
        claims: dict[str, Any] = Depends(require_hr_auth),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        """Validate and update screening settings."""
        init_db()
        if payload.model not in ALLOWED_MODELS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid model '{payload.model}'. Allowed models: {', '.join(ALLOWED_MODELS)}.",
            )

        if payload.threshold < 0.0 or payload.threshold > 100.0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Threshold must be between 0 and 100.",
            )

        if payload.redact_before_scoring is False:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="redact_before_scoring cannot be turned off for production.",
            )

        current = load_settings()
        if payload.applications_dir is not None:
            validated_dir = validate_applications_dir(payload.applications_dir)
            app_dir_str = str(validated_dir)
        else:
            app_dir_str = current["applications_dir"]

        updated = save_settings(
            {
                "threshold": payload.threshold,
                "requires_continuity": payload.requires_continuity,
                "model": payload.model,
                "applications_dir": app_dir_str,
                "redact_before_scoring": True,
            }
        )

        actor_email = str(claims.get("email") or "unknown")
        db.add(
            AuditLog(
                at_utc=utc_now_iso(),
                actor_email=actor_email,
                action="update_settings",
                detail=(
                    f"Updated settings: model={updated['model']}, "
                    f"threshold={updated['threshold']}, "
                    f"requires_continuity={updated['requires_continuity']}"
                ),
            )
        )
        db.commit()
        return updated

    @app.post("/api/runs")
    def start_screening_run(
        job_id: str | None = Query(default=None),
        claims: dict[str, Any] = Depends(require_hr_auth),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        """Start a screening run in a background task. Only one run is permitted at a time."""
        init_db()
        actor_email = str(claims.get("email") or "unknown")
        if job_id:
            target_job = _get_job_or_404(db, job_id)
        else:
            # Ensure default job exists synced to current settings when /api/runs is called directly
            settings = load_settings()
            target_job = _ensure_default_job(db, actor_email=actor_email)
            target_job.threshold = float(settings["threshold"])
            target_job.requires_continuity = bool(settings["requires_continuity"])
            target_job.model = str(settings["model"])
            if Path(settings["applications_dir"]).exists():
                target_job.applications_dir = str(Path(settings["applications_dir"]).resolve())
            db.commit()
        return _start_run_for_job(db=db, actor_email=actor_email, job=target_job)

    @app.get("/api/runs/latest/results")
    def get_latest_run_results(
        job_id: str | None = Query(default=None),
        needs_review_only: bool = Query(default=False),
        search: str = Query(default=""),
        sort_by: str = Query(default="default"),
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=25, ge=1, le=200),
        claims: dict[str, Any] = Depends(require_hr_auth),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        """Return results for the latest finished run (filtered by job_id when provided)."""
        _ = claims
        init_db()
        return _build_job_results_payload(
            db=db,
            job_id=job_id,
            needs_review_only=needs_review_only,
            search=search,
            sort_by=sort_by,
            page=page,
            page_size=page_size,
        )

    @app.get("/api/runs/{run_id}")
    def get_run_status(
        run_id: str,
        claims: dict[str, Any] = Depends(require_hr_auth),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        """Return status and candidate progress (current_candidate_index / total_candidates) for a run."""
        _ = claims
        init_db()

        run_row = db.query(Run).filter(Run.id == run_id).first()
        if run_row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Run not found: {run_id}",
            )

        total = int(run_row.candidate_count or 0)
        prog = _RUN_PROGRESS.get(run_id, {})
        if run_row.status == "finished":
            current_idx = total
        else:
            current_idx = int(prog.get("current_candidate_index", 0))

        pct = (
            int(round((current_idx / total) * 100))
            if total > 0
            else (100 if run_row.status == "finished" else 0)
        )

        return {
            "run_id": run_row.id,
            "job_id": run_row.job_id,
            "status": run_row.status,
            "started_at": run_row.started_at,
            "finished_at": run_row.finished_at,
            "model": run_row.model,
            "threshold": run_row.threshold,
            "candidate_count": total,
            "current_candidate_index": current_idx,
            "total_candidates": total,
            "progress": f"{current_idx}/{total}",
            "progress_percent": pct,
            "error": run_row.error,
        }

    @app.post("/api/candidates/{candidate_id}/decision")
    def post_candidate_decision(
        candidate_id: str,
        payload: HrDecisionRequest,
        job_id: str | None = Query(default=None),
        claims: dict[str, Any] = Depends(require_hr_auth),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        """Record an HR decision in hr_decisions and audit_log, and regenerate the Excel workbook."""
        init_db()
        actor_email = str(claims.get("email") or "unknown")
        return _record_decision_for_job_candidate(
            db=db,
            candidate_id=candidate_id,
            payload=payload,
            actor_email=actor_email,
            job_id=job_id or payload.job_id,
        )

    @app.get("/api/export.xlsx")
    def export_excel(
        job_id: str | None = Query(default=None),
        claims: dict[str, Any] = Depends(require_hr_auth),
        db: Session = Depends(get_db),
    ) -> FileResponse:
        """Return the screening_results_<JOB-ID>.xlsx file for the specified or latest job."""
        _ = claims
        init_db()
        clean_job_id = job_id.strip().upper() if job_id else None
        if clean_job_id:
            _get_job_or_404(db, clean_job_id)

        excel_path_str = _regenerate_excel_from_db(db, job_id=clean_job_id)
        excel_path = Path(excel_path_str)
        if not excel_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Excel results file has not been generated yet. Please run screening first.",
            )
        effective_jid = clean_job_id
        if not effective_jid:
            latest_run = (
                db.query(Run)
                .filter(Run.status == "finished")
                .order_by(desc(Run.started_at), desc(Run.id))
                .first()
            )
            effective_jid = (latest_run.job_id if latest_run else None) or "JOB-2026-001"
        return FileResponse(
            path=str(excel_path),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=f"screening_results_{effective_jid}.xlsx",
        )

    @app.get("/api/history")
    def get_history(
        job_id: str | None = Query(default=None),
        claims: dict[str, Any] = Depends(require_hr_auth),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        """Return past runs, HR decisions history, and audit log entries (optionally filtered by job_id)."""
        _ = claims
        init_db()
        clean_job_id = job_id.strip().upper() if job_id else None

        runs_q = db.query(Run)
        decisions_q = db.query(HrDecision)
        if clean_job_id:
            runs_q = runs_q.filter(Run.job_id == clean_job_id)
            decisions_q = decisions_q.filter(HrDecision.job_id == clean_job_id)

        runs = runs_q.order_by(desc(Run.started_at), desc(Run.id)).all()
        decisions = decisions_q.order_by(desc(HrDecision.id)).all()
        audits = db.query(AuditLog).order_by(desc(AuditLog.id)).all()

        runs_out: list[dict[str, Any]] = []
        for r in runs:
            try:
                parsed_settings = json.loads(r.settings_json or "{}")
            except Exception:
                parsed_settings = {}
            runs_out.append(
                {
                    "id": r.id,
                    "job_id": r.job_id or parsed_settings.get("job_id") or "JOB-2026-001",
                    "started_at": r.started_at,
                    "finished_at": r.finished_at,
                    "status": r.status,
                    "model": r.model,
                    "threshold": r.threshold,
                    "requires_continuity": bool(parsed_settings.get("requires_continuity", False)),
                    "candidate_count": r.candidate_count,
                    "error": r.error,
                }
            )

        decisions_out: list[dict[str, Any]] = [
            {
                "id": d.id,
                "job_id": d.job_id,
                "candidate_id": d.candidate_id,
                "run_id": d.run_id,
                "decision": d.decision,
                "note": d.note,
                "decided_by_email": d.decided_by_email,
                "decided_at_utc": d.decided_at_utc,
            }
            for d in decisions
        ]

        audits_out: list[dict[str, Any]] = [
            {
                "id": a.id,
                "at_utc": a.at_utc,
                "actor_email": a.actor_email,
                "action": a.action,
                "detail": a.detail,
            }
            for a in audits
        ]

        return {
            "job_id": clean_job_id,
            "runs": runs_out,
            "hr_decisions": decisions_out,
            "audit_log": audits_out,
        }

    # =========================================================================
    # T018: Admin Access Control Endpoints (visible/accessible to admins only)
    # =========================================================================

    @app.get("/api/admin/access")
    def get_admin_access(
        claims: dict[str, Any] = Depends(require_admin_auth),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        """Return allowed_users, allowed_domains, root_admins, and access audit trail."""
        _ = claims
        init_db()
        if not _is_test_json_fallback_active():
            migrate_access_control(db=db)

        users = db.query(AllowedUser).order_by(AllowedUser.id).all()
        domains = db.query(AllowedDomain).order_by(AllowedDomain.id).all()
        access_actions = (
            "migrate_allowlist",
            "access_grant_user",
            "access_revoke_user",
            "access_remove_user",
            "access_change_role",
            "access_grant_domain",
            "access_revoke_domain",
            "access_remove_domain",
        )
        audits = (
            db.query(AuditLog)
            .filter(AuditLog.action.in_(access_actions))
            .order_by(desc(AuditLog.id))
            .all()
        )

        return {
            "users": [_serialize_allowed_user(u) for u in users],
            "domains": [_serialize_allowed_domain(d) for d in domains],
            "root_admins": load_root_admins(),
            "audit_log": [
                {
                    "id": a.id,
                    "at_utc": a.at_utc,
                    "actor_email": a.actor_email,
                    "action": a.action,
                    "detail": a.detail,
                }
                for a in audits
            ],
        }

    @app.post("/api/admin/users")
    def admin_add_user(
        payload: AdminAddUserRequest,
        claims: dict[str, Any] = Depends(require_admin_auth),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        """Add or reactivate a user in allowed_users and log the grant in audit_log."""
        init_db()
        email = (payload.email or "").strip().lower()
        if not email or "@" not in email or " " in email or "." not in email.split("@", 1)[1]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please provide a valid email address.",
            )

        role = (payload.role or "hr").strip().lower()
        if role not in ("admin", "hr"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Role must be 'admin' or 'hr'.",
            )

        if is_root_admin(email) and role != "admin":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Root admin cannot be assigned a non-admin role.",
            )

        actor_email = str(claims.get("email") or "unknown")
        now_utc = utc_now_iso()

        existing = db.query(AllowedUser).filter(AllowedUser.email == email).first()
        if existing is not None:
            existing.role = role
            existing.active = True
            existing.added_by = actor_email
            existing.added_at_utc = now_utc
            user_row = existing
            detail_msg = f"Updated/reactivated user {email} with role '{role}'."
        else:
            user_row = AllowedUser(
                email=email,
                role=role,
                added_by=actor_email,
                added_at_utc=now_utc,
                active=True,
            )
            db.add(user_row)
            detail_msg = f"Added user {email} with role '{role}'."

        db.add(
            AuditLog(
                at_utc=now_utc,
                actor_email=actor_email,
                action="access_grant_user",
                detail=detail_msg,
            )
        )
        db.commit()
        db.refresh(user_row)
        return _serialize_allowed_user(user_row)

    @app.patch("/api/admin/users/{user_target}")
    @app.put("/api/admin/users/{user_target}")
    def admin_update_user(
        user_target: str,
        payload: AdminUpdateUserRequest,
        claims: dict[str, Any] = Depends(require_admin_auth),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        """Change a user's role or active status, enforcing root-admin and last-admin guards."""
        init_db()
        user_row = _find_user_by_target(db, user_target)
        if user_row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User not found: {user_target}",
            )

        new_role = user_row.role
        if payload.role is not None:
            candidate_role = payload.role.strip().lower()
            if candidate_role not in ("admin", "hr"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Role must be 'admin' or 'hr'.",
                )
            new_role = candidate_role

        new_active = user_row.active if payload.active is None else bool(payload.active)

        # Guard 1: Root admins cannot be deactivated or demoted
        if is_root_admin(user_row.email):
            if not new_active or new_role != "admin":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Root admin cannot be deactivated or removed from the admin role.",
                )

        # Guard 2: The last active admin cannot be deactivated or demoted
        if user_row.role == "admin" and user_row.active:
            if not new_active or new_role != "admin":
                if _count_other_active_admins(db, exclude_user_id=user_row.id) == 0:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Cannot remove or deactivate the last active admin.",
                    )

        actor_email = str(claims.get("email") or "unknown")
        now_utc = utc_now_iso()
        old_role = user_row.role
        old_active = bool(user_row.active)

        user_row.role = new_role
        user_row.active = new_active

        if old_role != new_role:
            db.add(
                AuditLog(
                    at_utc=now_utc,
                    actor_email=actor_email,
                    action="access_change_role",
                    detail=f"Changed role for {user_row.email} from '{old_role}' to '{new_role}'.",
                )
            )

        if old_active != new_active:
            act_code = "access_grant_user" if new_active else "access_revoke_user"
            state_label = "Reactivated" if new_active else "Deactivated"
            db.add(
                AuditLog(
                    at_utc=now_utc,
                    actor_email=actor_email,
                    action=act_code,
                    detail=f"{state_label} access for user {user_row.email}.",
                )
            )

        if old_role == new_role and old_active == new_active:
            db.add(
                AuditLog(
                    at_utc=now_utc,
                    actor_email=actor_email,
                    action="access_change_role",
                    detail=f"Updated user {user_row.email} (role='{new_role}', active={new_active}).",
                )
            )

        db.commit()
        db.refresh(user_row)
        return _serialize_allowed_user(user_row)

    @app.delete("/api/admin/users/{user_target}")
    def admin_delete_user(
        user_target: str,
        claims: dict[str, Any] = Depends(require_admin_auth),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        """Remove a user from allowed_users, enforcing root-admin and last-active-admin guards."""
        init_db()
        user_row = _find_user_by_target(db, user_target)
        if user_row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User not found: {user_target}",
            )

        # Guard 1: Root admins cannot be removed
        if is_root_admin(user_row.email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Root admin cannot be removed or deactivated.",
            )

        # Guard 2: The last active admin cannot be removed
        if user_row.role == "admin" and user_row.active:
            if _count_other_active_admins(db, exclude_user_id=user_row.id) == 0:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Cannot remove the last active admin.",
                )

        actor_email = str(claims.get("email") or "unknown")
        now_utc = utc_now_iso()
        removed_email = user_row.email
        removed_id = user_row.id

        db.delete(user_row)
        db.add(
            AuditLog(
                at_utc=now_utc,
                actor_email=actor_email,
                action="access_remove_user",
                detail=f"Removed user {removed_email} from allowed_users.",
            )
        )
        db.commit()
        return {"removed": True, "id": removed_id, "email": removed_email}

    @app.post("/api/admin/domains")
    def admin_add_domain(
        payload: AdminAddDomainRequest,
        claims: dict[str, Any] = Depends(require_admin_auth),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        """Add or reactivate an allowed organisation domain and log it in audit_log."""
        init_db()
        domain = (payload.domain or "").strip().lower().lstrip("@")
        if not domain or "." not in domain or "@" in domain or " " in domain:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please provide a valid domain name (e.g. 'example.gov').",
            )

        role = (payload.role or "hr").strip().lower()
        if role not in ("hr", "admin"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Domain role must be 'hr'.",
            )

        actor_email = str(claims.get("email") or "unknown")
        now_utc = utc_now_iso()

        existing = db.query(AllowedDomain).filter(AllowedDomain.domain == domain).first()
        if existing is not None:
            existing.role = role
            existing.active = True
            existing.added_by = actor_email
            existing.added_at_utc = now_utc
            dom_row = existing
            detail_msg = f"Updated/reactivated domain {domain} with role '{role}'."
        else:
            dom_row = AllowedDomain(
                domain=domain,
                role=role,
                added_by=actor_email,
                added_at_utc=now_utc,
                active=True,
            )
            db.add(dom_row)
            detail_msg = f"Added allowed domain {domain} with role '{role}'."

        db.add(
            AuditLog(
                at_utc=now_utc,
                actor_email=actor_email,
                action="access_grant_domain",
                detail=detail_msg,
            )
        )
        db.commit()
        db.refresh(dom_row)
        return _serialize_allowed_domain(dom_row)

    @app.patch("/api/admin/domains/{domain_target}")
    @app.put("/api/admin/domains/{domain_target}")
    def admin_update_domain(
        domain_target: str,
        payload: AdminUpdateDomainRequest,
        claims: dict[str, Any] = Depends(require_admin_auth),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        """Deactivate or reactivate an allowed domain and log the change in audit_log."""
        init_db()
        dom_row = _find_domain_by_target(db, domain_target)
        if dom_row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Domain not found: {domain_target}",
            )

        if payload.role is not None:
            role_clean = payload.role.strip().lower()
            if role_clean not in ("hr", "admin"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Domain role must be 'hr'.",
                )
            dom_row.role = role_clean

        if payload.active is not None:
            dom_row.active = bool(payload.active)

        actor_email = str(claims.get("email") or "unknown")
        now_utc = utc_now_iso()
        act_code = "access_grant_domain" if dom_row.active else "access_revoke_domain"
        state_label = "Activated" if dom_row.active else "Deactivated"

        db.add(
            AuditLog(
                at_utc=now_utc,
                actor_email=actor_email,
                action=act_code,
                detail=f"{state_label} domain rule for {dom_row.domain} (role='{dom_row.role}').",
            )
        )
        db.commit()
        db.refresh(dom_row)
        return _serialize_allowed_domain(dom_row)

    @app.delete("/api/admin/domains/{domain_target}")
    def admin_delete_domain(
        domain_target: str,
        claims: dict[str, Any] = Depends(require_admin_auth),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        """Deactivate a domain rule and log the change in audit_log."""
        init_db()
        dom_row = _find_domain_by_target(db, domain_target)
        if dom_row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Domain not found: {domain_target}",
            )

        dom_row.active = False
        actor_email = str(claims.get("email") or "unknown")
        now_utc = utc_now_iso()
        db.add(
            AuditLog(
                at_utc=now_utc,
                actor_email=actor_email,
                action="access_revoke_domain",
                detail=f"Deactivated domain rule for {dom_row.domain}.",
            )
        )
        db.commit()
        db.refresh(dom_row)
        return _serialize_allowed_domain(dom_row)

    return app


app = create_webapp(initialize_db=False)

