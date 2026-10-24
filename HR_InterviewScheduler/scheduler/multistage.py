"""Multi-Stage & Multi-Interview Coordination Engine for the Intelligent Interview Scheduler.

Implements the 5-step architecture approved in README.md:
1. Step 1 (Interviewer / Panel Lead Slot Request First):
   - Calculates required slot count based on candidate demand in that stage/interview.
   - Queries Google Calendar `freeBusy` across panel leads & stage interviewer pools to generate
     AI-suggested conflict-free options.
   - Emails the Panel Lead (`psrmreports@sybyl.com`) requesting the required number of slots with a
     1-click Panel Approval Portal link.
2. Step 2 (Live Conflict-Free Candidate Self-Booking Link):
   - Once panel slots are approved, candidates receive a unique link to the Web App's Live Slot Picker.
   - Opening the link dynamically displays ONLY live available slots (filtering out slots already booked
     by other candidates and re-verifying live Google Calendar availability).
   - Atomic Compare-and-Swap (`threading.RLock`) guarantees two candidates can never pick the same slot.
3. Step 3 (Multi-Stage & Multi-Interview Pipeline Progression):
   - Supports multiple sequential stages per job (`Stage 1`, `Stage 2`, `Stage 3`) and multiple
     interviews within a stage (e.g., `2A: Visual Portfolio Review`, `2B: Inventory & Space Analytics`).
   - Automatically advances a candidate to the next stage once all interviews in the current stage pass.
4. Step 4 (Self-Healing Conflict Resolution):
   - If an assigned interviewer declines a booked slot, the AI Agent automatically searches the stage's
     `interviewer_pool` for a free backup interviewer and hot-swaps them so the candidate's time stays
     unchanged (or sends a fresh live booking link if no backup is available).
5. Step 5 (Proactive Bottleneck Management — Screen 1 Command Center):
   - Computes real-time slot supply vs. candidate demand shortages, unresponsive panel leads,
     unresponsive candidates, escalations, and live AI activity logs.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
import imaplib
import math
import os
import smtplib
import threading
from typing import Any
import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from scheduler.tools import calendar as cal
from scheduler.tools import scheduling_tools as st
from scheduler.tools.email import get_mailer
from scheduler.tools.store import utcnow


def _safe_tz(tz_name: str | None, fallback: str = "UTC") -> ZoneInfo:
    for candidate_tz in (tz_name, fallback, "UTC"):
        if not candidate_tz:
            continue
        try:
            return ZoneInfo(candidate_tz)
        except ZoneInfoNotFoundError:
            continue
    return ZoneInfo("UTC")


def format_slot_window(start_iso: str, end_iso: str, tz_name: str = "UTC") -> str:
    """Format an ISO start/end window in a human-friendly timezone string."""
    start = datetime.fromisoformat(start_iso)
    end = datetime.fromisoformat(end_iso)
    tz = _safe_tz(tz_name)
    s_loc = start.astimezone(tz)
    e_loc = end.astimezone(tz)
    return f"{s_loc:%a %b %d, %Y • %I:%M %p} – {e_loc:%I:%M %p} ({tz.key})"


class SmtpImapService:
    """Outbound SMTP & Inbound IMAP service for `psrmreports@sybyl.com` with inspectable outbox."""

    def __init__(
        self,
        sender_email: str | None = None,
        app_password: str | None = None,
        smtp_host: str = "smtp.gmail.com",
        smtp_port: int = 587,
        imap_host: str = "imap.gmail.com",
        imap_port: int = 993,
        live_smtp_enabled: bool | None = None,
    ) -> None:
        self.sender_email = (
            sender_email
            or os.environ.get("SCHEDULER_EMAIL_ADDRESS")
            or "psrmreports@sybyl.com"
        )
        self.app_password = (
            app_password
            if app_password is not None
            else os.environ.get("SCHEDULER_EMAIL_APP_PASSWORD", "")
        )
        self.smtp_host = os.environ.get("SCHEDULER_SMTP_HOST", smtp_host)
        self.smtp_port = int(os.environ.get("SCHEDULER_SMTP_PORT", str(smtp_port)))
        self.imap_host = os.environ.get("SCHEDULER_IMAP_HOST", imap_host)
        self.imap_port = int(os.environ.get("SCHEDULER_IMAP_PORT", str(imap_port)))
        if live_smtp_enabled is None:
            env_flag = os.environ.get("SCHEDULER_LIVE_SMTP", "").strip().lower()
            self.live_smtp_enabled = env_flag in ("1", "true", "yes") and bool(self.app_password)
        else:
            self.live_smtp_enabled = live_smtp_enabled
        self.outbox: list[dict[str, Any]] = []
        self.inbox: list[dict[str, Any]] = []

    @property
    def is_live_configured(self) -> bool:
        return bool(self.sender_email and self.app_password and self.live_smtp_enabled)

    def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        category: str = "notification",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send an email via SMTP (if live enabled) and record in inspectable outbox + legacy mailer."""
        sent_via = "simulated_outbox"
        smtp_error: str | None = None

        if self.is_live_configured:
            try:
                msg = EmailMessage()
                msg["From"] = self.sender_email
                msg["To"] = to
                msg["Subject"] = subject
                msg.set_content(body)
                with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=8) as server:
                    server.starttls()
                    server.login(self.sender_email, self.app_password)
                    server.send_message(msg)
                sent_via = "live_smtp"
            except Exception as exc:
                smtp_error = str(exc)
                sent_via = "simulated_outbox_fallback"

        record = {
            "message_id": f"msg-{uuid.uuid4().hex[:8]}",
            "from": self.sender_email,
            "to": to,
            "subject": subject,
            "body": body,
            "category": category,
            "mode": sent_via,
            "smtp_error": smtp_error,
            "sent_at": utcnow().isoformat(),
            "metadata": metadata or {},
        }
        self.outbox.append(record)
        try:
            get_mailer().send(to, subject, body)
        except Exception:
            pass
        return record

    def poll_imap_replies(self, limit: int = 10) -> list[dict[str, Any]]:
        """Poll IMAP inbox for candidate/interviewer replies if live credentials are enabled."""
        if not self.is_live_configured:
            return list(self.inbox)
        try:
            with imaplib.IMAP4_SSL(self.imap_host, self.imap_port) as client:
                client.login(self.sender_email, self.app_password)
                client.select("INBOX")
                _, data = client.search(None, "UNSEEN")
                ids = (data[0] or b"").split()[-limit:]
                for msg_id in ids:
                    _, fetched = client.fetch(msg_id, "(RFC822)")
                    if fetched and fetched[0]:
                        self.inbox.append(
                            {
                                "imap_id": msg_id.decode("utf-8", errors="ignore"),
                                "received_at": utcnow().isoformat(),
                            }
                        )
        except Exception:
            pass
        return list(self.inbox)


class MultiStageHub:
    """Thread-safe state & coordination engine for Many Jobs × Many Candidates × Multi-Stage × Multi-Interview."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.jobs: dict[str, dict[str, Any]] = {}
        self.candidates: dict[str, dict[str, Any]] = {}
        self.panel_requests: dict[str, dict[str, Any]] = {}
        self.approved_slots: dict[str, dict[str, Any]] = {}
        self.candidate_links: dict[str, dict[str, Any]] = {}
        self.activity_log: list[dict[str, Any]] = []

    def log_activity(
        self,
        kind: str,
        title: str,
        detail: str,
        job_id: str | None = None,
        candidate_id: str | None = None,
    ) -> dict[str, Any]:
        entry = {
            "id": f"act-{uuid.uuid4().hex[:8]}",
            "timestamp": utcnow().isoformat(),
            "kind": kind,
            "type": kind,
            "title": title,
            "detail": detail,
            "summary": f"{title} — {detail}" if detail else title,
            "job_id": job_id,
            "candidate_id": candidate_id,
        }
        with self._lock:
            self.activity_log.insert(0, entry)
            del self.activity_log[100:]
        return entry

    # ------------------------------------------------------------------
    # Job & Multi-Stage Configuration
    # ------------------------------------------------------------------

    def add_job(self, job: dict[str, Any]) -> dict[str, Any]:
        """Register a multi-stage job definition with stages and sub-interviews (defaults to 3 stages)."""
        with self._lock:
            job_id = str(job.get("job_id") or f"JOB-{len(self.jobs) + 101}").strip()
            default_lead = job.get("panel_lead_email") or job.get("hiring_manager_email") or "lead@company.example"
            raw_stages = job.get("stages") or [
                {
                    "stage_id": "STAGE-1",
                    "order": 1,
                    "name": "Stage 1: Initial HR & Recruiter Screen",
                    "interviews": [
                        {
                            "interview_code": "1A",
                            "title": "HR & Role Alignment Screen",
                            "duration_minutes": 30,
                            "panel_lead_email": job.get("recruiter_email") or "psrmreports@sybyl.com",
                        }
                    ],
                },
                {
                    "stage_id": "STAGE-2",
                    "order": 2,
                    "name": "Stage 2: Technical & Core Competency Assessment",
                    "interviews": [
                        {
                            "interview_code": "2A",
                            "title": "Technical & Practical Evaluation",
                            "duration_minutes": 45,
                            "panel_lead_email": default_lead,
                        }
                    ],
                },
                {
                    "stage_id": "STAGE-3",
                    "order": 3,
                    "name": "Stage 3: Executive & Hiring Manager Final Round",
                    "interviews": [
                        {
                            "interview_code": "3A",
                            "title": "Final Leadership & Team Fit Panel",
                            "duration_minutes": 60,
                            "panel_lead_email": job.get("hiring_manager_email") or default_lead,
                        }
                    ],
                },
            ]
            stages: list[dict[str, Any]] = []
            for idx, stg in enumerate(raw_stages, start=1):
                stage_id = str(stg.get("stage_id") or f"STAGE-{idx}")
                interviews: list[dict[str, Any]] = []
                raw_ivs = stg.get("interviews") or [
                    {
                        "interview_code": stg.get("interview_code") or f"{idx}A",
                        "title": stg.get("interview_title") or f"Stage {idx} Assessment",
                        "duration_minutes": int(stg.get("duration_minutes", 45)),
                        "panel_lead_email": stg.get("panel_lead_email") or default_lead,
                    }
                ]
                for iv_idx, iv in enumerate(raw_ivs, start=1):
                    iv_code = str(iv.get("interview_code") or f"{idx}{chr(64 + iv_idx)}")
                    lead_email = iv.get("panel_lead_email") or default_lead
                    interviews.append(
                        {
                            "interview_code": iv_code,
                            "title": iv.get("title") or f"Stage {idx} Interview {iv_code}",
                            "duration_minutes": int(iv.get("duration_minutes", 45)),
                            "interview_type": iv.get("interview_type", "video"),
                            "panel_lead_email": lead_email,
                            "required_panel_emails": list(
                                iv.get("required_panel_emails") or [lead_email]
                            ),
                            "interviewer_pool": list(iv.get("interviewer_pool") or []),
                            "prep_notes": iv.get("prep_notes", ""),
                            "location": iv.get("location", "Google Meet"),
                        }
                    )
                stages.append(
                    {
                        "stage_id": stage_id,
                        "order": int(stg.get("order", idx)),
                        "name": stg.get("name") or f"Stage {idx}",
                        "interviews": interviews,
                    }
                )
            stages.sort(key=lambda s: s["order"])
            stored = {
                "job_id": job_id,
                "title": job.get("title") or job_id,
                "department": job.get("department", "Engineering & Operations"),
                "location": job.get("location", "Hybrid / Remote"),
                "employment_type": job.get("employment_type", "Full-Time"),
                "openings_count": int(job.get("openings_count", 2)),
                "hiring_manager_email": job.get(
                    "hiring_manager_email",
                    stages[-1]["interviews"][0]["panel_lead_email"] if stages and stages[-1]["interviews"] else default_lead,
                ),
                "description": job.get("description", ""),
                "job_timezone": job.get("job_timezone", "America/New_York"),
                "working_start": job.get("working_start", "09:00"),
                "working_end": job.get("working_end", "17:00"),
                "notice_hours": int(job.get("notice_hours", 2)),
                "recruiter_email": job.get("recruiter_email", "psrmreports@sybyl.com"),
                "stages": stages,
            }
            self.jobs[job_id] = stored
            return dict(stored)

    def add_stage_or_interview(self, job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Add a new stage (e.g., Stage 4) or a new interview round to an existing stage of a job."""
        with self._lock:
            job = self.jobs.get(job_id)
            if not job:
                raise ValueError(f"Unknown job_id: {job_id}")

            mode = str(payload.get("mode") or "stage").strip().lower()
            lead_email = str(payload.get("panel_lead_email") or job.get("hiring_manager_email") or "lead@company.example").strip()
            duration = int(payload.get("duration_minutes") or 45)
            backups = list(payload.get("backup_interviewers") or payload.get("interviewer_pool") or [])

            if mode == "interview" and payload.get("stage_id"):
                target_stage_id = str(payload["stage_id"]).strip()
                target_stage = next((s for s in job["stages"] if s["stage_id"] == target_stage_id), None)
            else:
                target_stage = None

            if target_stage is not None:
                order_idx = target_stage["order"]
                iv_idx = len(target_stage["interviews"]) + 1
                iv_code = str(payload.get("interview_code") or f"{order_idx}{chr(64 + iv_idx)}").strip()
                iv_title = str(payload.get("interview_title") or f"Stage {order_idx} Interview {iv_code}").strip()
                new_iv = {
                    "interview_code": iv_code,
                    "title": iv_title,
                    "duration_minutes": duration,
                    "interview_type": "video",
                    "panel_lead_email": lead_email,
                    "required_panel_emails": [lead_email],
                    "interviewer_pool": backups,
                    "prep_notes": str(payload.get("prep_notes") or ""),
                    "location": "Google Meet",
                }
                target_stage["interviews"].append(new_iv)
                stage_id = target_stage["stage_id"]
                stage_name = target_stage["name"]
            else:
                next_order = len(job["stages"]) + 1
                stage_id = str(payload.get("stage_id") or f"STAGE-{next_order}").strip()
                raw_stage_name = str(payload.get("stage_name") or "").strip()
                if not raw_stage_name:
                    stage_name = f"Stage {next_order}: Final & Team Evaluation"
                elif not raw_stage_name.lower().startswith("stage"):
                    stage_name = f"Stage {next_order}: {raw_stage_name}"
                else:
                    stage_name = raw_stage_name
                iv_code = str(payload.get("interview_code") or f"{next_order}A").strip()
                iv_title = str(payload.get("interview_title") or raw_stage_name or f"Stage {next_order} Interview").strip()
                new_iv = {
                    "interview_code": iv_code,
                    "title": iv_title,
                    "duration_minutes": duration,
                    "interview_type": "video",
                    "panel_lead_email": lead_email,
                    "required_panel_emails": [lead_email],
                    "interviewer_pool": backups,
                    "prep_notes": str(payload.get("prep_notes") or ""),
                    "location": "Google Meet",
                }
                new_stage = {
                    "stage_id": stage_id,
                    "order": next_order,
                    "name": stage_name,
                    "interviews": [new_iv],
                }
                job["stages"].append(new_stage)
                job["stages"].sort(key=lambda s: s["order"])

            # Ensure all existing candidates for this job have progress initialized for the new stage/interview
            for cand in self.candidates.values():
                if cand["job_id"] != job_id:
                    continue
                if stage_id not in cand["stage_progress"]:
                    cand["stage_progress"][stage_id] = {}
                if iv_code not in cand["stage_progress"][stage_id]:
                    cand["stage_progress"][stage_id][iv_code] = {
                        "interview_code": iv_code,
                        "title": iv_title,
                        "status": "awaiting_panel_slots" if cand["current_stage_id"] == stage_id else "locked",
                        "passed": False,
                        "booking_token": None,
                        "booked_slot_id": None,
                        "event_id": None,
                        "meet_link": None,
                        "start": None,
                        "end": None,
                        "slot_label": None,
                        "assigned_panel": [],
                        "updated_at": utcnow().isoformat(),
                    }

            self.log_activity(
                kind="stage_configured",
                title=f"Added {stage_name} ({iv_code}: {iv_title}) to {job_id}",
                detail=f"Lead interviewer: {lead_email} • Duration: {duration} mins",
                job_id=job_id,
            )
            return dict(job)

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = self.jobs.get(job_id)
            return dict(job) if job else None

    def get_interview_config(
        self, job_id: str, stage_id: str, interview_code: str
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        """Return (stage_dict, interview_dict) for the given job/stage/interview_code."""
        job = self.jobs.get(job_id)
        if not job:
            return None, None
        for stg in job["stages"]:
            if stg["stage_id"] == stage_id:
                for iv in stg["interviews"]:
                    if iv["interview_code"] == interview_code:
                        return stg, iv
        return None, None

    # ------------------------------------------------------------------
    # Candidate Registration & Multi-Stage State
    # ------------------------------------------------------------------

    def add_candidate(self, candidate: dict[str, Any]) -> dict[str, Any]:
        """Add a candidate to a job and initialize their multi-stage / multi-interview progress matrix."""
        with self._lock:
            cid = str(candidate["candidate_id"]).strip()
            job_id = str(candidate["job_id"]).strip()
            job = self.jobs.get(job_id)
            if not job:
                raise ValueError(f"Unknown job_id: {job_id}")

            first_stage_id = candidate.get("current_stage_id") or job["stages"][0]["stage_id"]
            stage_progress: dict[str, dict[str, dict[str, Any]]] = {}
            first_stage_order = 1
            for stg in job["stages"]:
                if stg["stage_id"] == first_stage_id:
                    first_stage_order = stg["order"]
                    break

            for stg in job["stages"]:
                stage_progress[stg["stage_id"]] = {}
                for iv in stg["interviews"]:
                    code = iv["interview_code"]
                    if stg["order"] < first_stage_order:
                        initial_status = "completed"
                    elif stg["stage_id"] == first_stage_id:
                        initial_status = "awaiting_panel_slots"
                    else:
                        initial_status = "locked"
                    stage_progress[stg["stage_id"]][code] = {
                        "interview_code": code,
                        "title": iv["title"],
                        "status": initial_status,
                        "passed": stg["order"] < first_stage_order,
                        "booking_token": None,
                        "booked_slot_id": None,
                        "event_id": None,
                        "meet_link": None,
                        "start": None,
                        "end": None,
                        "slot_label": None,
                        "assigned_panel": [],
                        "updated_at": utcnow().isoformat(),
                    }

            if "stage_progress" in candidate and isinstance(candidate["stage_progress"], dict):
                for s_id, iv_map in candidate["stage_progress"].items():
                    if s_id in stage_progress:
                        for code, override in iv_map.items():
                            if code in stage_progress[s_id]:
                                stage_progress[s_id][code].update(override)

            stored = {
                "candidate_id": cid,
                "name": candidate.get("name") or cid,
                "email": candidate["email"],
                "job_id": job_id,
                "timezone": candidate.get("timezone") or job["job_timezone"],
                "current_stage_id": first_stage_id,
                "overall_status": candidate.get("overall_status", "in_progress"),
                "escalation_reason": candidate.get("escalation_reason"),
                "stage_progress": stage_progress,
                "created_at": candidate.get("created_at") or utcnow().isoformat(),
                "updated_at": utcnow().isoformat(),
            }
            self.candidates[cid] = stored
            return dict(stored)

    # ------------------------------------------------------------------
    # Step 1: Interviewer / Panel Lead Slot Request First
    # ------------------------------------------------------------------

    def calculate_slot_requirement(
        self, job_id: str, stage_id: str, interview_code: str, buffer_slots: int = 2
    ) -> dict[str, Any]:
        """Calculate waiting candidate demand vs. approved open slot supply for a stage interview."""
        with self._lock:
            job = self.jobs.get(job_id)
            stg, iv = self.get_interview_config(job_id, stage_id, interview_code)
            if not job or not stg or not iv:
                return {"status": "error", "reason": f"Unknown interview {job_id}/{stage_id}/{interview_code}"}

            waiting_candidates: list[dict[str, Any]] = []
            for cand in self.candidates.values():
                if cand["job_id"] != job_id or cand["overall_status"] in ("rejected", "hired"):
                    continue
                iv_state = cand["stage_progress"].get(stage_id, {}).get(interview_code)
                if not iv_state:
                    continue
                if iv_state["status"] in ("awaiting_panel_slots", "link_sent"):
                    waiting_candidates.append(cand)

            open_approved_slots = [
                s
                for s in self.approved_slots.values()
                if s["job_id"] == job_id
                and s["stage_id"] == stage_id
                and s["interview_code"] == interview_code
                and s["status"] == "available"
            ]

            waiting_count = len(waiting_candidates)
            available_count = len(open_approved_slots)
            recommended_total = waiting_count + buffer_slots if waiting_count > 0 else buffer_slots
            deficit = max(0, (waiting_count + 1) - available_count) if waiting_count > 0 else 0
            has_shortage = waiting_count > available_count

            return {
                "status": "ok",
                "job_id": job_id,
                "job_title": job["title"],
                "stage_id": stage_id,
                "stage_name": stg["name"],
                "interview_code": interview_code,
                "interview_title": iv["title"],
                "panel_lead_email": iv["panel_lead_email"],
                "waiting_candidates_count": waiting_count,
                "waiting_candidates": [
                    {"candidate_id": c["candidate_id"], "name": c["name"], "email": c["email"]}
                    for c in waiting_candidates
                ],
                "available_approved_slots": available_count,
                "recommended_slots_to_request": max(deficit, recommended_total - available_count, 2),
                "slot_deficit": deficit,
                "has_shortage": has_shortage,
            }

    def generate_ai_slot_suggestions(
        self,
        job_id: str,
        stage_id: str,
        interview_code: str,
        max_suggestions: int = 8,
    ) -> list[dict[str, Any]]:
        """Query Google Calendar freeBusy for the panel lead + interviewer pool and propose conflict-free windows."""
        with self._lock:
            job = self.jobs.get(job_id)
            stg, iv = self.get_interview_config(job_id, stage_id, interview_code)
            if not job or not stg or not iv:
                return []

            now = utcnow()
            end_horizon = now + timedelta(days=10)
            required_emails = list(iv["required_panel_emails"])
            pool_emails = [e for e in iv["interviewer_pool"] if e not in required_emails]
            all_emails = required_emails + pool_emails

            busy_map = st.get_calendar().busy_blocks(all_emails, now, end_horizon)
            raw_slots = cal.generate_slots(
                busy={e: busy_map.get(e, []) for e in required_emails},
                now=now,
                days_ahead=10,
                duration_minutes=iv["duration_minutes"],
                working_start=job["working_start"],
                working_end=job["working_end"],
                job_timezone=job["job_timezone"],
                notice_hours=job["notice_hours"],
                max_options=max_suggestions * 2,
            )

            existing_starts = {
                s["start"]
                for s in self.approved_slots.values()
                if s["job_id"] == job_id
                and s["stage_id"] == stage_id
                and s["interview_code"] == interview_code
                and s["status"] in ("available", "booked")
            }

            suggestions: list[dict[str, Any]] = []
            for start_dt, end_dt in raw_slots:
                start_iso = start_dt.isoformat()
                end_iso = end_dt.isoformat()
                if start_iso in existing_starts:
                    continue

                available_pool = [
                    p_email
                    for p_email in pool_emails
                    if not cal.overlaps(start_dt, end_dt, busy_map.get(p_email, []))
                ]
                assigned_panel = list(required_emails)
                if available_pool and len(assigned_panel) < 2:
                    assigned_panel.append(available_pool[0])

                suggestions.append(
                    {
                        "slot_id": f"sugg-{uuid.uuid4().hex[:8]}",
                        "start": start_iso,
                        "end": end_iso,
                        "label": format_slot_window(start_iso, end_iso, job["job_timezone"]),
                        "interviewer_emails": assigned_panel,
                        "backup_pool_available": available_pool,
                    }
                )
                if len(suggestions) >= max_suggestions:
                    break
            return suggestions

    def request_slots_from_panel_lead(
        self,
        job_id: str,
        stage_id: str,
        interview_code: str,
        base_url: str = "http://localhost:8000",
    ) -> dict[str, Any]:
        """Step 1: Email the Interviewer / Panel Lead with AI-suggested options & required slot count."""
        with self._lock:
            calc = self.calculate_slot_requirement(job_id, stage_id, interview_code)
            if calc.get("status") != "ok":
                return calc

            job = self.jobs[job_id]
            stg, iv = self.get_interview_config(job_id, stage_id, interview_code)
            assert stg is not None and iv is not None

            required_count = max(calc["recommended_slots_to_request"], 3)
            suggestions = self.generate_ai_slot_suggestions(
                job_id, stage_id, interview_code, max_suggestions=max(required_count + 3, 6)
            )
            request_token = f"panel-{uuid.uuid4().hex[:10]}"
            approval_url = f"{base_url.rstrip('/')}/portal/panel/{request_token}"

            req_record = {
                "request_token": request_token,
                "job_id": job_id,
                "job_title": job["title"],
                "stage_id": stage_id,
                "stage_name": stg["name"],
                "interview_code": interview_code,
                "interview_title": iv["title"],
                "panel_lead_email": iv["panel_lead_email"],
                "waiting_candidates_count": calc["waiting_candidates_count"],
                "waiting_candidates": calc["waiting_candidates"],
                "required_slots_count": required_count,
                "suggested_slots": suggestions,
                "approved_slot_ids": [],
                "status": "pending",
                "approval_url": approval_url,
                "requested_at": utcnow().isoformat(),
                "responded_at": None,
            }
            self.panel_requests[request_token] = req_record

            options_text = "\n".join(
                f"  • Option {idx}: {s['label']} (Panel: {', '.join(s['interviewer_emails'])})"
                for idx, s in enumerate(suggestions, start=1)
            )
            waiting_names = ", ".join(c["name"] for c in calc["waiting_candidates"]) or "Upcoming pipeline candidates"
            subject = (
                f"[Action Required] {required_count} Interview Slots Needed — "
                f"{job['title']} ({stg['name']}: {iv['title']})"
            )
            body = (
                f"Hello Panel Lead ({iv['panel_lead_email']}),\n\n"
                f"We currently have {calc['waiting_candidates_count']} candidate(s) waiting for "
                f"'{iv['title']}' in {stg['name']} for {job['title']} ({job_id}):\n"
                f"  Candidates Waiting: {waiting_names}\n\n"
                f"To prevent candidate bottlenecks and double-booking collisions, our AI Scheduler "
                f"analyzed your Google Calendar free/busy availability and recommends selecting at least "
                f"{required_count} slots ({iv['duration_minutes']} mins each) from the conflict-free options below:\n\n"
                f"{options_text}\n\n"
                f"👉 Click here to approve or customize your slots in 1 click:\n"
                f"{approval_url}\n\n"
                f"Once you confirm your slots, the AI Agent will automatically send each waiting candidate "
                f"a live conflict-free self-booking link.\n\n"
                f"— AI Interview Coordination Agent ({get_smtp_imap_service().sender_email})"
            )
            email_rec = get_smtp_imap_service().send_email(
                to=iv["panel_lead_email"],
                subject=subject,
                body=body,
                category="panel_slot_request",
                metadata={"request_token": request_token, "job_id": job_id, "stage_id": stage_id, "interview_code": interview_code},
            )
            self.log_activity(
                kind="panel_slot_request",
                title=f"Requested {required_count} slots from {iv['panel_lead_email']}",
                detail=f"{job['title']} • {stg['name']} ({iv['title']}) — {calc['waiting_candidates_count']} candidates waiting",
                job_id=job_id,
            )
            return {
                "status": "requested",
                "request_token": request_token,
                "approval_url": approval_url,
                "required_slots_count": required_count,
                "waiting_candidates_count": calc["waiting_candidates_count"],
                "panel_lead_email": iv["panel_lead_email"],
                "suggested_slots": suggestions,
                "email_message_id": email_rec["message_id"],
            }

    def get_panel_request(self, request_token: str) -> dict[str, Any] | None:
        with self._lock:
            req = self.panel_requests.get(request_token)
            return dict(req) if req else None

    def approve_panel_slots(
        self,
        request_token: str,
        selected_slot_ids: list[str] | None = None,
        custom_slots: list[dict[str, str]] | None = None,
        base_url: str = "http://localhost:8000",
    ) -> dict[str, Any]:
        """Step 1 -> Step 2 Transition: Panel Lead approves slots; AI unlocks live links for waiting candidates."""
        with self._lock:
            req = self.panel_requests.get(request_token)
            if not req:
                return {"status": "error", "reason": f"Unknown request_token: {request_token}"}

            job_id = req["job_id"]
            stage_id = req["stage_id"]
            interview_code = req["interview_code"]
            job = self.jobs[job_id]
            stg, iv = self.get_interview_config(job_id, stage_id, interview_code)
            assert stg is not None and iv is not None

            suggested_by_id = {s["slot_id"]: s for s in req["suggested_slots"]}
            if not selected_slot_ids and not custom_slots:
                selected_slot_ids = [
                    s["slot_id"] for s in req["suggested_slots"][: req["required_slots_count"]]
                ]

            newly_approved: list[dict[str, Any]] = []
            for sid in selected_slot_ids or []:
                sugg = suggested_by_id.get(sid)
                if not sugg:
                    continue
                approved_id = f"slot-{uuid.uuid4().hex[:8]}"
                slot_obj = {
                    "slot_id": approved_id,
                    "source_suggestion_id": sid,
                    "request_token": request_token,
                    "job_id": job_id,
                    "stage_id": stage_id,
                    "interview_code": interview_code,
                    "start": sugg["start"],
                    "end": sugg["end"],
                    "label": sugg["label"],
                    "interviewer_emails": list(sugg["interviewer_emails"]),
                    "status": "available",
                    "booked_by_candidate_id": None,
                    "booked_by_candidate_name": None,
                    "event_id": None,
                    "meet_link": None,
                    "approved_at": utcnow().isoformat(),
                }
                self.approved_slots[approved_id] = slot_obj
                newly_approved.append(slot_obj)

            for custom in custom_slots or []:
                start_iso = custom.get("start")
                end_iso = custom.get("end")
                if not start_iso or not end_iso:
                    continue
                approved_id = f"slot-{uuid.uuid4().hex[:8]}"
                slot_obj = {
                    "slot_id": approved_id,
                    "source_suggestion_id": "custom",
                    "request_token": request_token,
                    "job_id": job_id,
                    "stage_id": stage_id,
                    "interview_code": interview_code,
                    "start": start_iso,
                    "end": end_iso,
                    "label": format_slot_window(start_iso, end_iso, job["job_timezone"]),
                    "interviewer_emails": list(iv["required_panel_emails"]),
                    "status": "available",
                    "booked_by_candidate_id": None,
                    "booked_by_candidate_name": None,
                    "event_id": None,
                    "meet_link": None,
                    "approved_at": utcnow().isoformat(),
                }
                self.approved_slots[approved_id] = slot_obj
                newly_approved.append(slot_obj)

            req["status"] = "approved"
            req["responded_at"] = utcnow().isoformat()
            req["approved_slot_ids"] = [s["slot_id"] for s in newly_approved]

            # Automatically dispatch live self-booking links to all waiting candidates for this stage/interview
            dispatched_links: list[dict[str, Any]] = []
            for cand in self.candidates.values():
                if cand["job_id"] != job_id or cand["overall_status"] in ("rejected", "hired"):
                    continue
                iv_state = cand["stage_progress"].get(stage_id, {}).get(interview_code)
                if iv_state and iv_state["status"] in ("awaiting_panel_slots", "link_sent"):
                    link_res = self.send_candidate_live_booking_link(
                        candidate_id=cand["candidate_id"],
                        stage_id=stage_id,
                        interview_code=interview_code,
                        base_url=base_url,
                    )
                    if link_res.get("status") == "sent":
                        dispatched_links.append(link_res)

            self.log_activity(
                kind="panel_slots_approved",
                title=f"Panel Lead approved {len(newly_approved)} slots for {iv['title']}",
                detail=f"Auto-dispatched live conflict-free booking links to {len(dispatched_links)} waiting candidate(s).",
                job_id=job_id,
            )
            return {
                "status": "approved",
                "request_token": request_token,
                "approved_count": len(newly_approved),
                "approved_slots": newly_approved,
                "candidates_notified": dispatched_links,
            }

    # ------------------------------------------------------------------
    # Step 2: Live Conflict-Free Candidate Self-Booking Link & Atomic Lock
    # ------------------------------------------------------------------

    def send_candidate_live_booking_link(
        self,
        candidate_id: str,
        stage_id: str,
        interview_code: str,
        base_url: str = "http://localhost:8000",
    ) -> dict[str, Any]:
        """Send a candidate a unique link to view and lock live conflict-free slots."""
        with self._lock:
            cand = self.candidates.get(candidate_id)
            if not cand:
                return {"status": "error", "reason": f"Unknown candidate_id: {candidate_id}"}
            job_id = cand["job_id"]
            job = self.jobs[job_id]
            stg, iv = self.get_interview_config(job_id, stage_id, interview_code)
            if not stg or not iv:
                return {"status": "error", "reason": f"Unknown stage/interview {stage_id}/{interview_code}"}

            iv_state = cand["stage_progress"][stage_id][interview_code]
            booking_token = iv_state.get("booking_token") or f"book-{uuid.uuid4().hex[:10]}"
            booking_url = f"{base_url.rstrip('/')}/portal/candidate/{booking_token}"

            iv_state["booking_token"] = booking_token
            if iv_state["status"] != "booked" and iv_state["status"] != "completed":
                iv_state["status"] = "link_sent"
            iv_state["updated_at"] = utcnow().isoformat()
            cand["updated_at"] = utcnow().isoformat()

            link_record = {
                "booking_token": booking_token,
                "candidate_id": candidate_id,
                "candidate_name": cand["name"],
                "candidate_email": cand["email"],
                "job_id": job_id,
                "stage_id": stage_id,
                "interview_code": interview_code,
                "booking_url": booking_url,
                "sent_at": utcnow().isoformat(),
                "status": "active",
            }
            self.candidate_links[booking_token] = link_record

            live_view = self.get_live_candidate_view(booking_token)
            live_count = len(live_view.get("live_available_slots", []))

            subject = f"Schedule Your Interview: {job['title']} — {stg['name']} ({iv['title']})"
            body = (
                f"Hi {cand['name']},\n\n"
                f"You are invited to schedule your '{iv['title']}' ({iv['duration_minutes']} mins) "
                f"for {job['title']} ({stg['name']}).\n\n"
                f"To ensure zero scheduling conflicts and show you only real-time available times in your "
                f"timezone ({cand['timezone']}), please open your live booking link below:\n\n"
                f"👉 Book Your Live Slot Now ({live_count} live options currently open):\n"
                f"{booking_url}\n\n"
                f"Preparation Notes: {iv['prep_notes'] or 'Standard interview preparation.'}\n\n"
                f"— Recruiting Coordination Agent ({get_smtp_imap_service().sender_email})"
            )
            email_rec = get_smtp_imap_service().send_email(
                to=cand["email"],
                subject=subject,
                body=body,
                category="candidate_live_booking_link",
                metadata={
                    "booking_token": booking_token,
                    "candidate_id": candidate_id,
                    "job_id": job_id,
                    "stage_id": stage_id,
                    "interview_code": interview_code,
                },
            )
            self.log_activity(
                kind="candidate_link_sent",
                title=f"Sent live self-booking link to {cand['name']}",
                detail=f"{job['title']} • {stg['name']} ({iv['title']}) — {live_count} live conflict-free slots open",
                job_id=job_id,
                candidate_id=candidate_id,
            )
            return {
                "status": "sent",
                "booking_token": booking_token,
                "booking_url": booking_url,
                "candidate_id": candidate_id,
                "candidate_email": cand["email"],
                "available_live_slots": live_count,
                "email_message_id": email_rec["message_id"],
            }

    def get_live_candidate_view(self, booking_token: str) -> dict[str, Any]:
        """Step 2 Live View: Return ONLY currently available, conflict-free slots for the candidate.

        1. Filters out any slot already booked by another candidate (`status != 'available'`).
        2. Re-verifies live Google Calendar `freeBusy` right now so if an interviewer got a new
           calendar conflict, either a free backup from `interviewer_pool` is substituted or the
           slot is hidden from the live view.
        """
        with self._lock:
            link = self.candidate_links.get(booking_token)
            if not link:
                return {"status": "error", "reason": f"Unknown booking_token: {booking_token}"}

            cand = self.candidates.get(link["candidate_id"])
            job = self.jobs.get(link["job_id"])
            stg, iv = self.get_interview_config(
                link["job_id"], link["stage_id"], link["interview_code"]
            )
            if not cand or not job or not stg or not iv:
                return {"status": "error", "reason": "Invalid candidate or job configuration"}

            iv_state = cand["stage_progress"][link["stage_id"]][link["interview_code"]]
            pool_slots = [
                s
                for s in self.approved_slots.values()
                if s["job_id"] == link["job_id"]
                and s["stage_id"] == link["stage_id"]
                and s["interview_code"] == link["interview_code"]
                and s["status"] == "available"
            ]
            pool_slots.sort(key=lambda x: x["start"])

            live_slots: list[dict[str, Any]] = []
            calendar_backend = st.get_calendar()
            backup_pool = list(iv.get("interviewer_pool") or [])

            for slot in pool_slots:
                start_dt = datetime.fromisoformat(slot["start"])
                end_dt = datetime.fromisoformat(slot["end"])
                assigned = list(slot["interviewer_emails"])
                busy_now = calendar_backend.busy_blocks(assigned + backup_pool, start_dt, end_dt)

                resolved_panel: list[str] = []
                conflict_unresolvable = False
                for email_addr in assigned:
                    if not cal.overlaps(start_dt, end_dt, busy_now.get(email_addr, [])):
                        resolved_panel.append(email_addr)
                    else:
                        replacement = next(
                            (
                                b
                                for b in backup_pool
                                if b not in resolved_panel
                                and b not in assigned
                                and not cal.overlaps(start_dt, end_dt, busy_now.get(b, []))
                            ),
                            None,
                        )
                        if replacement:
                            resolved_panel.append(replacement)
                        else:
                            conflict_unresolvable = True
                            break

                if conflict_unresolvable:
                    continue

                live_slots.append(
                    {
                        "slot_id": slot["slot_id"],
                        "start": slot["start"],
                        "end": slot["end"],
                        "candidate_local_label": format_slot_window(
                            slot["start"], slot["end"], cand["timezone"]
                        ),
                        "job_tz_label": slot["label"],
                        "interviewer_emails": resolved_panel,
                    }
                )

            return {
                "status": "ok",
                "booking_token": booking_token,
                "candidate_id": cand["candidate_id"],
                "candidate_name": cand["name"],
                "candidate_email": cand["email"],
                "candidate_timezone": cand["timezone"],
                "job_id": job["job_id"],
                "job_title": job["title"],
                "stage_id": stg["stage_id"],
                "stage_name": stg["name"],
                "interview_code": iv["interview_code"],
                "interview_title": iv["title"],
                "duration_minutes": iv["duration_minutes"],
                "prep_notes": iv["prep_notes"],
                "interview_status": iv_state["status"],
                "already_booked": iv_state["status"] in ("booked", "completed"),
                "booked_details": (
                    {
                        "slot_id": iv_state["booked_slot_id"],
                        "slot_label": iv_state["slot_label"],
                        "event_id": iv_state["event_id"],
                        "meet_link": iv_state["meet_link"],
                        "assigned_panel": iv_state["assigned_panel"],
                    }
                    if iv_state["status"] in ("booked", "completed")
                    else None
                ),
                "live_available_slots": live_slots,
            }

    def book_live_candidate_slot(self, booking_token: str, slot_id: str) -> dict[str, Any]:
        """Step 2 Atomic Compare-and-Swap Booking: Guarantees two candidates can never pick the same slot."""
        with self._lock:
            link = self.candidate_links.get(booking_token)
            if not link:
                return {"status": "error", "reason": f"Unknown booking_token: {booking_token}"}

            cand = self.candidates.get(link["candidate_id"])
            job = self.jobs.get(link["job_id"])
            stg, iv = self.get_interview_config(
                link["job_id"], link["stage_id"], link["interview_code"]
            )
            if not cand or not job or not stg or not iv:
                return {"status": "error", "reason": "Invalid booking link state"}

            iv_state = cand["stage_progress"][link["stage_id"]][link["interview_code"]]
            if iv_state["status"] == "booked":
                return {
                    "status": "already_booked",
                    "reason": "Candidate has already booked a slot for this interview.",
                    "event_id": iv_state["event_id"],
                    "slot_label": iv_state["slot_label"],
                }

            slot = self.approved_slots.get(slot_id)
            if not slot or slot["job_id"] != job["job_id"] or slot["interview_code"] != iv["interview_code"]:
                return {"status": "error", "reason": f"Invalid slot_id: {slot_id}"}

            # ATOMIC COMPARE-AND-SWAP CHECK: If another candidate just claimed this slot, reject & refresh!
            if slot["status"] != "available":
                return {
                    "status": "slot_already_taken",
                    "reason": (
                        "This slot was just claimed by another candidate moments ago. "
                        "Please select from the refreshed live available slots."
                    ),
                    "refreshed_live_slots": self.get_live_candidate_view(booking_token).get(
                        "live_available_slots", []
                    ),
                }

            # Re-verify live Google Calendar freeBusy right before creating the event
            start_dt = datetime.fromisoformat(slot["start"])
            end_dt = datetime.fromisoformat(slot["end"])
            calendar_backend = st.get_calendar()
            backup_pool = list(iv.get("interviewer_pool") or [])
            busy_now = calendar_backend.busy_blocks(
                list(slot["interviewer_emails"]) + backup_pool, start_dt, end_dt
            )

            final_panel: list[str] = []
            for email_addr in slot["interviewer_emails"]:
                if not cal.overlaps(start_dt, end_dt, busy_now.get(email_addr, [])):
                    final_panel.append(email_addr)
                else:
                    replacement = next(
                        (
                            b
                            for b in backup_pool
                            if b not in final_panel
                            and b not in slot["interviewer_emails"]
                            and not cal.overlaps(start_dt, end_dt, busy_now.get(b, []))
                        ),
                        None,
                    )
                    if replacement:
                        final_panel.append(replacement)
                    else:
                        slot["status"] = "conflicted"
                        return {
                            "status": "slot_calendar_conflict",
                            "reason": "An interviewer just became busy at this time. Please pick another live slot.",
                            "refreshed_live_slots": self.get_live_candidate_view(booking_token).get(
                                "live_available_slots", []
                            ),
                        }

            title = f"[{job['job_id']}] {iv['title']} — {cand['name']} ({stg['name']})"
            created = calendar_backend.create_event(
                attendees=[*final_panel, cand["email"]],
                start=start_dt,
                end=end_dt,
                title=title,
                description=iv.get("prep_notes", ""),
                location=iv.get("location", "Google Meet"),
            )
            if created is None:
                slot["status"] = "conflicted"
                return {
                    "status": "slot_calendar_conflict",
                    "reason": "Calendar conflict detected during event creation; please pick another live slot.",
                    "refreshed_live_slots": self.get_live_candidate_view(booking_token).get(
                        "live_available_slots", []
                    ),
                }

            # Lock the slot to this candidate
            slot["status"] = "booked"
            slot["booked_by_candidate_id"] = cand["candidate_id"]
            slot["booked_by_candidate_name"] = cand["name"]
            slot["interviewer_emails"] = final_panel
            slot["event_id"] = created["event_id"]
            slot["meet_link"] = created["meet_link"]
            slot["booked_at"] = utcnow().isoformat()

            cand_label = format_slot_window(slot["start"], slot["end"], cand["timezone"])
            iv_state.update(
                {
                    "status": "booked",
                    "booked_slot_id": slot["slot_id"],
                    "event_id": created["event_id"],
                    "meet_link": created["meet_link"],
                    "start": slot["start"],
                    "end": slot["end"],
                    "slot_label": cand_label,
                    "assigned_panel": final_panel,
                    "updated_at": utcnow().isoformat(),
                }
            )
            link["status"] = "completed"
            cand["updated_at"] = utcnow().isoformat()

            # Send confirmation email via psrmreports@sybyl.com
            get_smtp_imap_service().send_email(
                to=cand["email"],
                subject=f"Interview Confirmed: {job['title']} — {iv['title']}",
                body=(
                    f"Hi {cand['name']},\n\n"
                    f"Your interview is confirmed and locked on the calendar!\n\n"
                    f"  • Job: {job['title']} ({job['job_id']})\n"
                    f"  • Stage & Interview: {stg['name']} — {iv['title']}\n"
                    f"  • Time: {cand_label}\n"
                    f"  • Panel: {', '.join(final_panel)}\n"
                    f"  • Google Meet Link: {created['meet_link']}\n\n"
                    f"Prep Notes: {iv.get('prep_notes') or 'See job description.'}\n"
                ),
                category="interview_confirmation",
                metadata={"candidate_id": cand["candidate_id"], "event_id": created["event_id"]},
            )

            self.log_activity(
                kind="candidate_slot_booked",
                title=f"{cand['name']} locked live slot for {iv['title']}",
                detail=f"{cand_label} • Panel: {', '.join(final_panel)} • Meet: {created['meet_link']}",
                job_id=job["job_id"],
                candidate_id=cand["candidate_id"],
            )
            return {
                "status": "booked",
                "candidate_id": cand["candidate_id"],
                "candidate_name": cand["name"],
                "job_id": job["job_id"],
                "stage_id": stg["stage_id"],
                "interview_code": iv["interview_code"],
                "slot_id": slot["slot_id"],
                "slot_label": cand_label,
                "event_id": created["event_id"],
                "meet_link": created["meet_link"],
                "assigned_panel": final_panel,
            }

    # ------------------------------------------------------------------
    # Step 3: Multi-Stage & Multi-Interview Pipeline Progression
    # ------------------------------------------------------------------

    def complete_interview_and_advance(
        self,
        candidate_id: str,
        stage_id: str,
        interview_code: str,
        passed: bool = True,
        base_url: str = "http://localhost:8000",
    ) -> dict[str, Any]:
        """Mark a sub-interview completed; if all interviews in the stage pass, auto-advance to the next stage."""
        with self._lock:
            cand = self.candidates.get(candidate_id)
            if not cand:
                return {"status": "error", "reason": f"Unknown candidate_id: {candidate_id}"}
            job = self.jobs[cand["job_id"]]
            stage_map = cand["stage_progress"].get(stage_id)
            if not stage_map or interview_code not in stage_map:
                return {"status": "error", "reason": f"Unknown stage/interview {stage_id}/{interview_code}"}

            iv_state = stage_map[interview_code]
            iv_state["status"] = "completed" if passed else "failed"
            iv_state["passed"] = passed
            iv_state["updated_at"] = utcnow().isoformat()

            if not passed:
                cand["overall_status"] = "rejected"
                self.log_activity(
                    kind="candidate_rejected",
                    title=f"{cand['name']} did not pass {stage_id} ({interview_code})",
                    detail="Pipeline progression stopped for this candidate.",
                    job_id=job["job_id"],
                    candidate_id=candidate_id,
                )
                return {"status": "rejected", "candidate_id": candidate_id, "stage_advanced": False}

            # Check whether ALL sub-interviews in this stage are now completed & passed
            all_stage_interviews_passed = all(
                sub["status"] == "completed" and sub.get("passed", True)
                for sub in stage_map.values()
            )
            advanced_to_stage: str | None = None
            auto_triggered_actions: list[dict[str, Any]] = []

            if all_stage_interviews_passed:
                ordered_stages = sorted(job["stages"], key=lambda s: s["order"])
                current_idx = next(
                    (i for i, s in enumerate(ordered_stages) if s["stage_id"] == stage_id), -1
                )
                if 0 <= current_idx < len(ordered_stages) - 1:
                    next_stage = ordered_stages[current_idx + 1]
                    next_stage_id = next_stage["stage_id"]
                    cand["current_stage_id"] = next_stage_id
                    advanced_to_stage = next_stage_id

                    for next_iv in next_stage["interviews"]:
                        ncode = next_iv["interview_code"]
                        next_iv_state = cand["stage_progress"][next_stage_id][ncode]
                        next_iv_state["status"] = "awaiting_panel_slots"
                        next_iv_state["updated_at"] = utcnow().isoformat()

                        # If approved slots already exist for this next stage interview, send the live link immediately!
                        req_calc = self.calculate_slot_requirement(
                            job["job_id"], next_stage_id, ncode
                        )
                        if req_calc.get("available_approved_slots", 0) > 0:
                            link_res = self.send_candidate_live_booking_link(
                                candidate_id=candidate_id,
                                stage_id=next_stage_id,
                                interview_code=ncode,
                                base_url=base_url,
                            )
                            auto_triggered_actions.append(link_res)
                else:
                    cand["overall_status"] = "completed_all_stages"

                self.log_activity(
                    kind="stage_advanced",
                    title=f"{cand['name']} completed all interviews in {stage_id}",
                    detail=(
                        f"Automatically advanced to {advanced_to_stage}"
                        if advanced_to_stage
                        else "Candidate completed all interview stages — Ready for Offer!"
                    ),
                    job_id=job["job_id"],
                    candidate_id=candidate_id,
                )

            return {
                "status": "completed",
                "candidate_id": candidate_id,
                "stage_id": stage_id,
                "interview_code": interview_code,
                "stage_completed": all_stage_interviews_passed,
                "advanced_to_stage": advanced_to_stage,
                "overall_status": cand["overall_status"],
                "auto_triggered_actions": auto_triggered_actions,
            }

    # ------------------------------------------------------------------
    # Step 4: Self-Healing Conflict Resolution (Backup Interviewer Swap)
    # ------------------------------------------------------------------

    def handle_interviewer_decline(
        self,
        candidate_id: str,
        stage_id: str,
        interview_code: str,
        declined_email: str,
        base_url: str = "http://localhost:8000",
    ) -> dict[str, Any]:
        """Step 4 Self-Healing: When an interviewer declines a booked slot, hot-swap a free backup from the pool."""
        with self._lock:
            cand = self.candidates.get(candidate_id)
            if not cand:
                return {"status": "error", "reason": f"Unknown candidate_id: {candidate_id}"}
            job = self.jobs[cand["job_id"]]
            stg, iv = self.get_interview_config(job["job_id"], stage_id, interview_code)
            if not stg or not iv:
                return {"status": "error", "reason": "Unknown stage/interview"}

            iv_state = cand["stage_progress"][stage_id][interview_code]
            if iv_state["status"] != "booked" or not iv_state.get("start") or not iv_state.get("end"):
                return {"status": "error", "reason": "Interview is not currently booked"}

            start_dt = datetime.fromisoformat(iv_state["start"])
            end_dt = datetime.fromisoformat(iv_state["end"])
            calendar_backend = st.get_calendar()

            # Mark the declining interviewer as busy during that window
            if hasattr(calendar_backend, "external_busy"):
                calendar_backend.external_busy.setdefault(declined_email, []).append((start_dt, end_dt))

            pool_candidates = [
                e
                for e in iv.get("interviewer_pool", [])
                if e != declined_email and e not in iv_state["assigned_panel"]
            ]
            busy_map = calendar_backend.busy_blocks(pool_candidates, start_dt, end_dt)
            replacement = next(
                (
                    e
                    for e in pool_candidates
                    if not cal.overlaps(start_dt, end_dt, busy_map.get(e, []))
                ),
                None,
            )

            if replacement:
                new_panel = [
                    replacement if e == declined_email else e for e in iv_state["assigned_panel"]
                ]
                if replacement not in new_panel:
                    new_panel.append(replacement)
                iv_state["assigned_panel"] = new_panel
                iv_state["updated_at"] = utcnow().isoformat()

                slot_id = iv_state.get("booked_slot_id")
                if slot_id and slot_id in self.approved_slots:
                    self.approved_slots[slot_id]["interviewer_emails"] = new_panel

                get_smtp_imap_service().send_email(
                    to=replacement,
                    subject=f"[Auto-Assigned Backup] {job['title']} — {iv['title']} with {cand['name']}",
                    body=(
                        f"Hi {replacement},\n\n"
                        f"{declined_email} had a schedule conflict for {cand['name']}'s '{iv['title']}' "
                        f"at {iv_state['slot_label']}.\n"
                        f"Since your calendar is free and you are in the Stage Backup Pool, the AI Scheduler "
                        f"hot-swapped you into the panel so the candidate's interview time remains unchanged.\n"
                        f"Google Meet: {iv_state['meet_link']}\n"
                    ),
                    category="self_healing_swap",
                )
                self.log_activity(
                    kind="self_healing_swap",
                    title=f"Hot-swapped backup interviewer {replacement} for {cand['name']}",
                    detail=f"{declined_email} declined {iv['title']} → {replacement} auto-assigned without moving candidate's time!",
                    job_id=job["job_id"],
                    candidate_id=candidate_id,
                )
                return {
                    "status": "swapped_backup_interviewer",
                    "candidate_id": candidate_id,
                    "declined_interviewer": declined_email,
                    "replacement_interviewer": replacement,
                    "updated_panel": new_panel,
                    "slot_label": iv_state["slot_label"],
                }

            # No backup interviewer available -> gracefully re-open candidate live booking link
            iv_state["status"] = "awaiting_panel_slots"
            link_res = self.send_candidate_live_booking_link(
                candidate_id=candidate_id,
                stage_id=stage_id,
                interview_code=interview_code,
                base_url=base_url,
            )
            self.log_activity(
                kind="self_healing_reschedule",
                title=f"No backup free for {declined_email}; sent fresh live booking link to {cand['name']}",
                detail=f"{job['title']} • {iv['title']}",
                job_id=job["job_id"],
                candidate_id=candidate_id,
            )
            return {
                "status": "reissued_live_booking_link",
                "candidate_id": candidate_id,
                "declined_interviewer": declined_email,
                "booking_link": link_res,
            }

    # ------------------------------------------------------------------
    # Step 5 / Screen 1: Proactive Bottleneck & Action Command Center
    # ------------------------------------------------------------------

    def get_bottleneck_dashboard(self) -> dict[str, Any]:
        """Compute Screen 1 (Proactive Bottleneck Management) metrics, shortages, stage health cards, and pipeline matrix."""
        with self._lock:
            slot_shortages: list[dict[str, Any]] = []
            unresponsive_panels: list[dict[str, Any]] = []
            unresponsive_candidates: list[dict[str, Any]] = []
            escalations: list[dict[str, Any]] = []
            stage_health_cards: list[dict[str, Any]] = []
            enriched_jobs: list[dict[str, Any]] = []

            for job_id, job in self.jobs.items():
                job_copy = dict(job)
                enriched_stages: list[dict[str, Any]] = []
                job_candidates = [c for c in self.candidates.values() if c["job_id"] == job_id]
                job_copy["candidates_count"] = len(job_candidates)

                for stg in job["stages"]:
                    stg_copy = dict(stg)
                    enriched_ivs: list[dict[str, Any]] = []
                    stage_cands_in_stage = sum(
                        1 for c in job_candidates if c.get("current_stage_id") == stg["stage_id"]
                    )
                    stg_copy["active_candidates_in_stage"] = stage_cands_in_stage

                    for iv in stg["interviews"]:
                        calc = self.calculate_slot_requirement(
                            job_id, stg["stage_id"], iv["interview_code"]
                        )
                        iv_requests = [
                            r
                            for r in self.panel_requests.values()
                            if r["job_id"] == job_id
                            and r["stage_id"] == stg["stage_id"]
                            and r["interview_code"] == iv["interview_code"]
                        ]
                        pending_reqs = [r for r in iv_requests if r["status"] == "pending"]
                        pending_req = pending_reqs[0] if pending_reqs else None
                        iv_slots = [
                            s
                            for s in self.approved_slots.values()
                            if s["job_id"] == job_id
                            and s["stage_id"] == stg["stage_id"]
                            and s["interview_code"] == iv["interview_code"]
                        ]
                        req_slots_count = (
                            calc["waiting_candidates_count"] + 2
                            if calc["waiting_candidates_count"] > 0
                            else 2
                        )
                        deficit_count = calc["recommended_slots_to_request"] if calc.get("has_shortage") else 0

                        iv_copy = dict(iv)
                        iv_copy["approved_slots"] = iv_slots
                        iv_copy["panel_requests"] = iv_requests
                        iv_copy["waiting_candidates_count"] = calc["waiting_candidates_count"]
                        iv_copy["available_approved_slots"] = calc["available_approved_slots"]
                        iv_copy["required_slots_count"] = req_slots_count
                        iv_copy["slot_deficit"] = deficit_count
                        iv_copy["pending_request_token"] = (
                            pending_req["request_token"] if pending_req else None
                        )
                        enriched_ivs.append(iv_copy)

                        stage_health_cards.append(
                            {
                                "job_id": job_id,
                                "job_title": job["title"],
                                "stage_id": stg["stage_id"],
                                "stage_order": stg.get("order", 1),
                                "stage_name": stg["name"],
                                "interview_code": iv["interview_code"],
                                "interview_title": iv["title"],
                                "duration_minutes": iv.get("duration_minutes", 45),
                                "panel_lead_email": iv["panel_lead_email"],
                                "waiting_candidates_count": calc["waiting_candidates_count"],
                                "available_approved_slots": calc["available_approved_slots"],
                                "required_slots_count": req_slots_count,
                                "slot_deficit": deficit_count,
                                "has_shortage": bool(calc.get("has_shortage")),
                                "pending_panel_requests": [r["request_token"] for r in pending_reqs],
                                "pending_request_token": (
                                    pending_req["request_token"] if pending_req else None
                                ),
                            }
                        )

                        if calc.get("has_shortage"):
                            slot_shortages.append(
                                {
                                    "bottleneck_id": f"shortage-{job_id}-{stg['stage_id']}-{iv['interview_code']}",
                                    "severity": "critical"
                                    if calc["available_approved_slots"] == 0
                                    else "warning",
                                    "job_id": job_id,
                                    "job_title": job["title"],
                                    "stage_id": stg["stage_id"],
                                    "stage_name": stg["name"],
                                    "interview_code": iv["interview_code"],
                                    "interview_title": iv["title"],
                                    "panel_lead_email": iv["panel_lead_email"],
                                    "waiting_candidates_count": calc["waiting_candidates_count"],
                                    "waiting_candidates": calc["waiting_candidates_count"],
                                    "waiting_candidate_names": [
                                        c["name"] for c in calc["waiting_candidates"]
                                    ],
                                    "available_approved_slots": calc["available_approved_slots"],
                                    "required_slots": req_slots_count,
                                    "slot_deficit": calc["recommended_slots_to_request"],
                                    "deficit": calc["recommended_slots_to_request"],
                                    "pending_request_token": pending_req["request_token"]
                                    if pending_req
                                    else None,
                                    "recommended_action": (
                                        f"Request {calc['recommended_slots_to_request']} suggested times "
                                        f"from {iv['panel_lead_email']}"
                                        if not pending_req
                                        else f"Review & approve pending request ({pending_req['request_token']})"
                                    ),
                                }
                            )

                    stg_copy["interviews"] = enriched_ivs
                    enriched_stages.append(stg_copy)

                job_copy["stages"] = enriched_stages
                enriched_jobs.append(job_copy)

            for req in self.panel_requests.values():
                if req["status"] == "pending":
                    unresponsive_panels.append(
                        {
                            "request_token": req["request_token"],
                            "job_id": req["job_id"],
                            "job_title": req["job_title"],
                            "stage_id": req["stage_id"],
                            "stage_name": req["stage_name"],
                            "interview_code": req["interview_code"],
                            "interview_title": req["interview_title"],
                            "panel_lead_email": req["panel_lead_email"],
                            "required_slots_count": req["required_slots_count"],
                            "waiting_candidates_count": req["waiting_candidates_count"],
                            "requested_at": req["requested_at"],
                            "approval_url": req["approval_url"],
                        }
                    )

            for cand in self.candidates.values():
                if cand.get("overall_status") == "escalated":
                    escalations.append(
                        {
                            "candidate_id": cand["candidate_id"],
                            "candidate_name": cand["name"],
                            "candidate_email": cand["email"],
                            "job_id": cand["job_id"],
                            "reason": cand.get("escalation_reason") or "Custom scheduling request",
                        }
                    )
                job = self.jobs.get(cand["job_id"], {})
                for stg in job.get("stages", []):
                    for iv in stg.get("interviews", []):
                        iv_state = cand["stage_progress"].get(stg["stage_id"], {}).get(
                            iv["interview_code"]
                        )
                        if iv_state and iv_state["status"] == "link_sent":
                            unresponsive_candidates.append(
                                {
                                    "candidate_id": cand["candidate_id"],
                                    "candidate_name": cand["name"],
                                    "candidate_email": cand["email"],
                                    "job_id": cand["job_id"],
                                    "job_title": job.get("title", cand["job_id"]),
                                    "stage_id": stg["stage_id"],
                                    "stage_name": stg["name"],
                                    "interview_code": iv["interview_code"],
                                    "interview_title": iv["title"],
                                    "booking_token": iv_state["booking_token"],
                                    "updated_at": iv_state["updated_at"],
                                }
                            )

            total_booked = 0
            total_completed = 0
            for cand in self.candidates.values():
                for stg_map in cand["stage_progress"].values():
                    for iv_state in stg_map.values():
                        if iv_state["status"] == "booked":
                            total_booked += 1
                        elif iv_state["status"] == "completed":
                            total_completed += 1

            return {
                "summary": {
                    "total_jobs": len(self.jobs),
                    "total_candidates": len(self.candidates),
                    "active_bottlenecks": len(slot_shortages)
                    + len(unresponsive_panels)
                    + len(escalations),
                    "slot_shortages_count": len(slot_shortages),
                    "unresponsive_panels_count": len(unresponsive_panels),
                    "unresponsive_candidates_count": len(unresponsive_candidates),
                    "escalations_count": len(escalations),
                    "total_bottlenecks": len(slot_shortages)
                    + len(unresponsive_panels)
                    + len(escalations),
                    "approved_available_slots": sum(
                        1 for s in self.approved_slots.values() if s["status"] == "available"
                    ),
                    "booked_interviews": total_booked,
                    "completed_interviews": total_completed,
                    "emails_sent": len(get_smtp_imap_service().outbox),
                },
                "bottlenecks": {
                    "slot_shortages": slot_shortages,
                    "unresponsive_panels": unresponsive_panels,
                    "unresponsive_candidates": unresponsive_candidates,
                    "escalations": escalations,
                },
                "stage_health_cards": stage_health_cards,
                "jobs": enriched_jobs,
                "candidates": list(self.candidates.values()),
                "panel_requests": list(self.panel_requests.values()),
                "approved_slots": list(self.approved_slots.values()),
                "candidate_links": list(self.candidate_links.values()),
                "activity_log": list(self.activity_log[:30]),
            }

    def auto_resolve_all_bottlenecks(self, base_url: str = "http://localhost:8000") -> dict[str, Any]:
        """Step 5 One-Click AI Resolution: Trigger Step 1 slot requests for all shortages & nudge pending items."""
        with self._lock:
            dashboard = self.get_bottleneck_dashboard()
            actions_taken: list[dict[str, Any]] = []

            for shortage in dashboard["bottlenecks"]["slot_shortages"]:
                if not shortage["pending_request_token"]:
                    res = self.request_slots_from_panel_lead(
                        job_id=shortage["job_id"],
                        stage_id=shortage["stage_id"],
                        interview_code=shortage["interview_code"],
                        base_url=base_url,
                    )
                    actions_taken.append(
                        {
                            "action": "requested_panel_slots",
                            "job_id": shortage["job_id"],
                            "interview_code": shortage["interview_code"],
                            "panel_lead_email": shortage["panel_lead_email"],
                            "request_token": res.get("request_token"),
                        }
                    )
                else:
                    req = self.panel_requests.get(shortage["pending_request_token"])
                    if req:
                        get_smtp_imap_service().send_email(
                            to=req["panel_lead_email"],
                            subject=f"[Reminder] {req['required_slots_count']} Slots Needed — {req['job_title']} ({req['interview_title']})",
                            body=(
                                f"Friendly AI reminder: {req['waiting_candidates_count']} candidates are waiting "
                                f"for your slot approval.\nApprove in 1 click: {req['approval_url']}"
                            ),
                            category="panel_reminder",
                        )
                        actions_taken.append(
                            {
                                "action": "nudged_panel_lead",
                                "panel_lead_email": req["panel_lead_email"],
                                "request_token": req["request_token"],
                            }
                        )

            for unresp_cand in dashboard["bottlenecks"]["unresponsive_candidates"]:
                link_res = self.send_candidate_live_booking_link(
                    candidate_id=unresp_cand["candidate_id"],
                    stage_id=unresp_cand["stage_id"],
                    interview_code=unresp_cand["interview_code"],
                    base_url=base_url,
                )
                actions_taken.append(
                    {
                        "action": "reminded_candidate_live_link",
                        "candidate_id": unresp_cand["candidate_id"],
                        "candidate_email": unresp_cand["candidate_email"],
                        "booking_token": link_res.get("booking_token"),
                    }
                )

            self.log_activity(
                kind="proactive_bottleneck_sweep",
                title=f"AI Agent executed {len(actions_taken)} proactive bottleneck resolution actions",
                detail="All slot shortages and pending scheduling links have been actioned.",
            )
            return {
                "status": "resolved",
                "actions_count": len(actions_taken),
                "actions_taken": actions_taken,
            }


_SMTP_IMAP_SERVICE: SmtpImapService | None = None
_MULTISTAGE_HUB: MultiStageHub | None = None


def get_smtp_imap_service() -> SmtpImapService:
    global _SMTP_IMAP_SERVICE
    if _SMTP_IMAP_SERVICE is None:
        _SMTP_IMAP_SERVICE = SmtpImapService()
    return _SMTP_IMAP_SERVICE


def set_smtp_imap_service(service: SmtpImapService) -> None:
    global _SMTP_IMAP_SERVICE
    _SMTP_IMAP_SERVICE = service


def get_multistage_hub() -> MultiStageHub:
    global _MULTISTAGE_HUB
    if _MULTISTAGE_HUB is None:
        _MULTISTAGE_HUB = MultiStageHub()
    return _MULTISTAGE_HUB


def set_multistage_hub(hub: MultiStageHub) -> None:
    global _MULTISTAGE_HUB
    _MULTISTAGE_HUB = hub


def seed_enterprise_scenario(base_url: str = "http://localhost:8000") -> MultiStageHub:
    """Seed realistic enterprise multi-job, multi-stage, multi-interview data with active bottlenecks."""
    hub = MultiStageHub()
    set_multistage_hub(hub)

    # Job 1: Senior Visual Merchandiser (3 Stages; Stage 2 has 2 parallel interviews: 2A & 2B)
    hub.add_job(
        {
            "job_id": "MERCH-2026-01",
            "title": "Senior Visual Merchandiser",
            "department": "Retail Brand & Merchandising",
            "location": "New York / Hybrid",
            "job_timezone": "America/New_York",
            "working_start": "09:00",
            "working_end": "17:00",
            "notice_hours": 2,
            "recruiter_email": "psrmreports@sybyl.com",
            "stages": [
                {
                    "stage_id": "STAGE-1",
                    "order": 1,
                    "name": "Stage 1: HR & Retail Screening",
                    "interviews": [
                        {
                            "interview_code": "1A",
                            "title": "HR Culture & Retail Screen",
                            "duration_minutes": 30,
                            "interview_type": "video",
                            "panel_lead_email": "hr.merch@company.example",
                            "required_panel_emails": ["hr.merch@company.example"],
                            "interviewer_pool": [
                                "hr.retail.backup1@company.example",
                                "hr.retail.backup2@company.example",
                            ],
                            "prep_notes": "Review seasonal retail campaign background and store launch experience.",
                        }
                    ],
                },
                {
                    "stage_id": "STAGE-2",
                    "order": 2,
                    "name": "Stage 2: Merchandising Deep-Dive (2 Interviews)",
                    "interviews": [
                        {
                            "interview_code": "2A",
                            "title": "Visual Portfolio & Floor Layout Review",
                            "duration_minutes": 45,
                            "interview_type": "video",
                            "panel_lead_email": "creative.director@company.example",
                            "required_panel_emails": ["creative.director@company.example"],
                            "interviewer_pool": [
                                "brand.stylist1@company.example",
                                "brand.stylist2@company.example",
                            ],
                            "prep_notes": "Bring 3 flagship visual merchandising lookbooks for screen-share.",
                        },
                        {
                            "interview_code": "2B",
                            "title": "Inventory & Space Analytics Assessment",
                            "duration_minutes": 45,
                            "interview_type": "video",
                            "panel_lead_email": "inventory.lead@company.example",
                            "required_panel_emails": ["inventory.lead@company.example"],
                            "interviewer_pool": [
                                "planner.ops1@company.example",
                                "planner.ops2@company.example",
                            ],
                            "prep_notes": "30-minute SKU velocity & planogram optimization case study.",
                        },
                    ],
                },
                {
                    "stage_id": "STAGE-3",
                    "order": 3,
                    "name": "Stage 3: Executive Retail Leadership Panel",
                    "interviews": [
                        {
                            "interview_code": "3A",
                            "title": "VP of Retail Final Panel",
                            "duration_minutes": 60,
                            "interview_type": "video",
                            "panel_lead_email": "vp.retail@company.example",
                            "required_panel_emails": [
                                "vp.retail@company.example",
                                "regional.gm@company.example",
                            ],
                            "interviewer_pool": ["director.stores@company.example"],
                            "prep_notes": "90-day regional store rollout strategy discussion.",
                        }
                    ],
                },
            ],
        }
    )

    # Job 2: Senior Cloud & AI Solutions Architect (3 Stages; Stage 2 has 2 parallel interviews: 2A & 2B)
    hub.add_job(
        {
            "job_id": "CLOUD-2026-02",
            "title": "Senior Cloud & AI Solutions Architect",
            "department": "Cloud Platform & AI Engineering",
            "location": "Remote (Global)",
            "job_timezone": "America/New_York",
            "working_start": "09:00",
            "working_end": "17:30",
            "notice_hours": 2,
            "recruiter_email": "psrmreports@sybyl.com",
            "stages": [
                {
                    "stage_id": "STAGE-1",
                    "order": 1,
                    "name": "Stage 1: Technical Recruiter Screen",
                    "interviews": [
                        {
                            "interview_code": "1A",
                            "title": "Cloud & AI Background Screen",
                            "duration_minutes": 30,
                            "interview_type": "video",
                            "panel_lead_email": "tech.recruiter@company.example",
                            "required_panel_emails": ["tech.recruiter@company.example"],
                            "interviewer_pool": ["tech.recruiter2@company.example"],
                            "prep_notes": "High-level review of distributed systems & enterprise AI architecture experience.",
                        }
                    ],
                },
                {
                    "stage_id": "STAGE-2",
                    "order": 2,
                    "name": "Stage 2: Technical Evaluations (2 Interviews)",
                    "interviews": [
                        {
                            "interview_code": "2A",
                            "title": "Distributed Cloud Architecture Design",
                            "duration_minutes": 60,
                            "interview_type": "video",
                            "panel_lead_email": "principal.arch@company.example",
                            "required_panel_emails": ["principal.arch@company.example"],
                            "interviewer_pool": [
                                "staff.cloud1@company.example",
                                "staff.cloud2@company.example",
                            ],
                            "prep_notes": "Multi-region high-availability system design whiteboard.",
                        },
                        {
                            "interview_code": "2B",
                            "title": "Agentic AI & Systems Live Coding",
                            "duration_minutes": 60,
                            "interview_type": "video",
                            "panel_lead_email": "ai.lead@company.example",
                            "required_panel_emails": ["ai.lead@company.example"],
                            "interviewer_pool": [
                                "ml.eng1@company.example",
                                "ml.eng2@company.example",
                            ],
                            "prep_notes": "Hands-on Python & tool-calling agent orchestration exercise.",
                        },
                    ],
                },
                {
                    "stage_id": "STAGE-3",
                    "order": 3,
                    "name": "Stage 3: Executive & Security Sign-Off",
                    "interviews": [
                        {
                            "interview_code": "3A",
                            "title": "CTO & Principal Security Review",
                            "duration_minutes": 45,
                            "interview_type": "video",
                            "panel_lead_email": "cto@company.example",
                            "required_panel_emails": ["cto@company.example", "ciso@company.example"],
                            "interviewer_pool": ["vp.infra@company.example"],
                            "prep_notes": "Enterprise governance, OAuth security, and executive alignment.",
                        }
                    ],
                },
            ],
        }
    )

    # Seed 8 Candidates across jobs and stages
    # 1. Elena Rostova -> MERCH-2026-01 Stage 2 (Passed Stage 1, now needs 2A & 2B)
    hub.add_candidate(
        {
            "candidate_id": "CAND-101",
            "name": "Elena Rostova",
            "email": "elena.rostova@example.org",
            "job_id": "MERCH-2026-01",
            "timezone": "America/New_York",
            "current_stage_id": "STAGE-2",
        }
    )
    # 2. Marcus Chen -> MERCH-2026-01 Stage 2 (Passed Stage 1, also needs 2A & 2B -> creates contention!)
    hub.add_candidate(
        {
            "candidate_id": "CAND-102",
            "name": "Marcus Chen",
            "email": "marcus.chen@example.org",
            "job_id": "MERCH-2026-01",
            "timezone": "America/Chicago",
            "current_stage_id": "STAGE-2",
        }
    )
    # 3. Priya Nair -> MERCH-2026-01 Stage 1 (Booked in 1A)
    hub.add_candidate(
        {
            "candidate_id": "CAND-103",
            "name": "Priya Nair",
            "email": "priya.nair@example.org",
            "job_id": "MERCH-2026-01",
            "timezone": "Europe/London",
            "current_stage_id": "STAGE-1",
        }
    )
    # 4. Devon Brooks -> MERCH-2026-01 Stage 1 (Waiting for 1A slots)
    hub.add_candidate(
        {
            "candidate_id": "CAND-104",
            "name": "Devon Brooks",
            "email": "devon.brooks@example.org",
            "job_id": "MERCH-2026-01",
            "timezone": "America/New_York",
            "current_stage_id": "STAGE-1",
        }
    )
    # 5. Aisha Al-Mansoor -> CLOUD-2026-02 Stage 2 (Needs 2A & 2B)
    hub.add_candidate(
        {
            "candidate_id": "CAND-105",
            "name": "Aisha Al-Mansoor",
            "email": "aisha.almansoor@example.org",
            "job_id": "CLOUD-2026-02",
            "timezone": "Europe/London",
            "current_stage_id": "STAGE-2",
        }
    )
    # 6. Liam O'Connor -> CLOUD-2026-02 Stage 2 (2A Completed, 2B Booked -> ready to test Step 3 Stage Promotion!)
    hub.add_candidate(
        {
            "candidate_id": "CAND-106",
            "name": "Liam O'Connor",
            "email": "liam.oconnor@example.org",
            "job_id": "CLOUD-2026-02",
            "timezone": "Europe/Dublin",
            "current_stage_id": "STAGE-2",
        }
    )
    # 7. Sofia Rossi -> CLOUD-2026-02 Stage 3 (Waiting for CTO Final Panel 3A slots -> Critical Bottleneck!)
    hub.add_candidate(
        {
            "candidate_id": "CAND-107",
            "name": "Sofia Rossi",
            "email": "sofia.rossi@example.org",
            "job_id": "CLOUD-2026-02",
            "timezone": "Europe/Rome",
            "current_stage_id": "STAGE-3",
        }
    )
    # 8. Kenji Takahashi -> CLOUD-2026-02 Stage 1 (Waiting for 1A)
    hub.add_candidate(
        {
            "candidate_id": "CAND-108",
            "name": "Kenji Takahashi",
            "email": "kenji.takahashi@example.org",
            "job_id": "CLOUD-2026-02",
            "timezone": "America/Los_Angeles",
            "current_stage_id": "STAGE-1",
        }
    )

    # Pre-create a Step 1 Panel Request for MERCH-2026-01 Stage 2A and approve 4 slots so Elena & Marcus
    # have live conflict-free self-booking links ready to demonstrate Step 2 immediately!
    req_2a = hub.request_slots_from_panel_lead(
        "MERCH-2026-01", "STAGE-2", "2A", base_url=base_url
    )
    hub.approve_panel_slots(
        req_2a["request_token"],
        selected_slot_ids=[s["slot_id"] for s in req_2a["suggested_slots"][:4]],
        base_url=base_url,
    )

    # Pre-create a pending Step 1 Panel Request for CLOUD-2026-02 Stage 2A (awaiting panel lead approval)
    hub.request_slots_from_panel_lead(
        "CLOUD-2026-02", "STAGE-2", "2A", base_url=base_url
    )

    # Book Priya Nair (CAND-103) into MERCH-2026-01 Stage 1A so she has a live booked interview
    req_1a = hub.request_slots_from_panel_lead(
        "MERCH-2026-01", "STAGE-1", "1A", base_url=base_url
    )
    hub.approve_panel_slots(
        req_1a["request_token"],
        selected_slot_ids=[s["slot_id"] for s in req_1a["suggested_slots"][:2]],
        base_url=base_url,
    )
    priya_token = hub.candidates["CAND-103"]["stage_progress"]["STAGE-1"]["1A"]["booking_token"]
    priya_view = hub.get_live_candidate_view(priya_token)
    if priya_view.get("live_available_slots"):
        hub.book_live_candidate_slot(
            priya_token, priya_view["live_available_slots"][0]["slot_id"]
        )

    # Set Liam O'Connor (CAND-106) Stage 2A as completed and Stage 2B as booked so 1 click completes Stage 2 -> Stage 3
    liam_s2 = hub.candidates["CAND-106"]["stage_progress"]["STAGE-2"]
    liam_s2["2A"]["status"] = "completed"
    liam_s2["2A"]["passed"] = True
    req_cloud_2b = hub.request_slots_from_panel_lead(
        "CLOUD-2026-02", "STAGE-2", "2B", base_url=base_url
    )
    hub.approve_panel_slots(
        req_cloud_2b["request_token"],
        selected_slot_ids=[s["slot_id"] for s in req_cloud_2b["suggested_slots"][:2]],
        base_url=base_url,
    )
    liam_token_2b = liam_s2["2B"]["booking_token"]
    liam_view_2b = hub.get_live_candidate_view(liam_token_2b)
    if liam_view_2b.get("live_available_slots"):
        hub.book_live_candidate_slot(
            liam_token_2b, liam_view_2b["live_available_slots"][0]["slot_id"]
        )

    return hub
