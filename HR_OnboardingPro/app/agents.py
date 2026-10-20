"""Onboarding Workflows & Automated Assistants for HR Onboarding."""

import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.database import dict_from_row, get_conn, utc_now_iso
from app.email_service import dispatch_stakeholder_email
from app.models import (
    BatchOnboardingRequest,
    OfferStatus,
    ROLE_ONBOARDING_STEPS,
    RoleCategory,
    SUBAGENT_METADATA,
    TaskStatus,
    TaskType,
    parse_cc_emails,
)
from app.pdf_generator import (
    compute_signature_hash,
    generate_offer_pdf,
    get_offer_template,
    render_template_text,
)


STEP_FRIENDLY_LABELS = {
    "EMAIL": "Work Email",
    "LAPTOP": "Laptop",
    "UBER": "Uber Commute Pass",
    "INSURANCE": "Health Insurance",
}


def _candidate_cc_list(cand: Dict[str, Any]) -> List[str]:
    if cand.get("cc_emails"):
        return parse_cc_emails(cand.get("cc_emails"), cand.get("hod_email"))
    return parse_cc_emails(cand.get("hr_email"), cand.get("hod_email"), cand.get("ceo_email"))


def log_agent_event(
    candidate_id: Optional[str],
    agent_name: str,
    event_type: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    event_id = f"evt-{uuid.uuid4().hex[:10]}"
    now = utc_now_iso()
    conn = get_conn()
    conn.execute(
        """
        INSERT INTO agent_audit_events (
            id, candidate_id, agent_name, event_type, message, details_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_id,
            candidate_id,
            agent_name,
            event_type,
            message,
            json.dumps(details or {}),
            now,
        ),
    )
    conn.commit()
    conn.close()
    return {
        "id": event_id,
        "candidate_id": candidate_id,
        "agent_name": agent_name,
        "event_type": event_type,
        "message": message,
        "details": details or {},
        "created_at": now,
    }


def _slugify_email_handle(full_name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z\s]", "", full_name).strip().lower()
    parts = cleaned.split()
    if not parts:
        return "user"
    if len(parts) == 1:
        return parts[0]
    return f"{parts[0]}.{parts[-1]}"


class SubAgentSimulator:
    """Generates clean, HR-readable summaries for the 4 onboarding assistants."""

    @staticmethod
    def build_completion_artifacts(
        task_type: str, candidate: Dict[str, Any], position: Dict[str, Any]
    ) -> Dict[str, Any]:
        short_id = candidate["id"].split("-")[-1].upper()[:5]
        handle = _slugify_email_handle(candidate["full_name"])
        corp_email = candidate.get("corporate_email") or f"{handle}@sybyl.com"
        role = candidate["role_category"]

        if task_type == TaskType.EMAIL.value:
            return {
                "external_ref_id": f"IT-{short_id}",
                "work_email": corp_email,
                "department_group": position["department"],
                "status": "Active & Ready",
                "output_summary": f"Work email {corp_email} is active and ready",
            }

        if task_type == TaskType.LAPTOP.value:
            is_emp = role == RoleCategory.EMPLOYEE.value
            model = (
                'Apple MacBook Pro 16"'
                if is_emp
                else 'Dell Latitude 14" Laptop'
            )
            return {
                "external_ref_id": f"LAP-{short_id}",
                "laptop_model": model,
                "handover_status": f"Ready for pickup on {candidate['joining_date']}",
                "output_summary": f"{model} assigned and ready for Day 1",
            }

        if task_type == TaskType.UBER.value:
            allowance = "$400/month Commute Pass" if role == RoleCategory.EMPLOYEE.value else "$200/month Commute Pass"
            return {
                "external_ref_id": f"UBER-{short_id}",
                "work_email": corp_email,
                "monthly_pass": allowance,
                "status": "Invitation sent",
                "output_summary": f"Uber commute pass ({allowance}) active for {corp_email}",
            }

        if task_type == TaskType.INSURANCE.value:
            return {
                "external_ref_id": f"INS-{short_id}",
                "plan_type": "Employee & Family Health Cover",
                "member_card": f"HC-{short_id}",
                "start_date": candidate["joining_date"],
                "output_summary": f"Health insurance active from {candidate['joining_date']} (Card: HC-{short_id})",
            }

        return {"external_ref_id": f"REF-{short_id}", "output_summary": "Completed"}


class OnboardingOrchestrator:
    """Manages role-based onboarding checklists and task progress."""

    @staticmethod
    def spawn_provisioning_tasks_for_candidate(candidate_id: str) -> List[Dict[str, Any]]:
        conn = get_conn()
        cand_row = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
        if not cand_row:
            conn.close()
            return []
        candidate = dict_from_row(cand_row)
        pos_row = conn.execute("SELECT * FROM positions WHERE id = ?", (candidate["position_id"],)).fetchone()
        position = dict_from_row(pos_row)

        role = candidate["role_category"]
        required_steps = ROLE_ONBOARDING_STEPS.get(role, [TaskType.EMAIL.value])

        existing = conn.execute(
            "SELECT * FROM provisioning_tasks WHERE candidate_id = ?", (candidate_id,)
        ).fetchall()
        if existing:
            conn.close()
            return [dict_from_row(r) for r in existing]

        now = utc_now_iso()
        created_tasks = []

        for step_type in required_steps:
            meta = SUBAGENT_METADATA[step_type]
            task_id = f"tsk-{uuid.uuid4().hex[:10]}"
            depends_on = meta["depends_on"]
            if depends_on is None:
                status = TaskStatus.IN_PROGRESS.value
                stage_idx = 1
                stage_label = meta["stages"][1]
                started_at = now
            else:
                status = TaskStatus.PENDING.value
                stage_idx = 0
                stage_label = meta["stages"][0]
                started_at = None

            conn.execute(
                """
                INSERT INTO provisioning_tasks (
                    id, candidate_id, task_type, agent_id, agent_name,
                    department, depends_on, status, current_stage_idx,
                    total_stages, stage_label, external_ref_id, output_summary,
                    blocker_reason, metadata_json, started_at, completed_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    candidate_id,
                    step_type,
                    meta["agent_id"],
                    meta["agent_name"],
                    meta["department"],
                    depends_on,
                    status,
                    stage_idx,
                    len(meta["stages"]),
                    stage_label,
                    None,
                    None,
                    None,
                    json.dumps({"stages": meta["stages"], "role": role}),
                    started_at,
                    None,
                    now,
                ),
            )
            created_tasks.append(
                {
                    "id": task_id,
                    "task_type": step_type,
                    "agent_name": meta["agent_name"],
                    "status": status,
                    "stage_label": stage_label,
                }
            )

        conn.execute(
            "UPDATE candidates SET overall_stage = 'PROVISIONING', updated_at = ? WHERE id = ?",
            (now, candidate_id),
        )
        conn.commit()
        conn.close()

        friendly_list = ", ".join(STEP_FRIENDLY_LABELS.get(s, s) for s in required_steps)
        log_agent_event(
            candidate_id=candidate_id,
            agent_name="Onboarding Coordinator",
            event_type="ONBOARDING_STARTED",
            message=(
                f"Started {role.title()} onboarding for {candidate['full_name']} ({position['title']}): "
                f"{friendly_list}."
            ),
            details={"role_category": role, "spawned_tasks": required_steps},
        )

        for t in created_tasks:
            if t["status"] == TaskStatus.IN_PROGRESS.value:
                log_agent_event(
                    candidate_id=candidate_id,
                    agent_name=t["agent_name"],
                    event_type="STEP_STARTED",
                    message=f"{t['agent_name']} started for {candidate['full_name']}: {t['stage_label']}",
                    details={"task_id": t["id"], "task_type": t["task_type"]},
                )

        return created_tasks

    @staticmethod
    def advance_task_stage(task_id: str, complete_immediately: bool = False) -> Dict[str, Any]:
        """Moves an onboarding step forward by one stage (or completes it) and unlocks dependent steps."""
        conn = get_conn()
        task_row = conn.execute("SELECT * FROM provisioning_tasks WHERE id = ?", (task_id,)).fetchone()
        if not task_row:
            conn.close()
            raise ValueError(f"Task {task_id} not found")

        task = dict_from_row(task_row)
        cand_row = conn.execute("SELECT * FROM candidates WHERE id = ?", (task["candidate_id"],)).fetchone()
        candidate = dict_from_row(cand_row)
        pos_row = conn.execute("SELECT * FROM positions WHERE id = ?", (candidate["position_id"],)).fetchone()
        position = dict_from_row(pos_row)

        meta = SUBAGENT_METADATA[task["task_type"]]
        stages = meta["stages"]
        max_idx = len(stages) - 1
        now = utc_now_iso()

        if task["depends_on"]:
            dep_row = conn.execute(
                "SELECT * FROM provisioning_tasks WHERE candidate_id = ? AND task_type = ?",
                (task["candidate_id"], task["depends_on"]),
            ).fetchone()
            if dep_row and dep_row["status"] != TaskStatus.COMPLETED.value:
                conn.close()
                return {
                    "error": f"{task['agent_name']} is waiting for Work Email setup to finish first.",
                    "task": task,
                }

        if task["status"] == TaskStatus.COMPLETED.value:
            conn.close()
            return {"task": task}

        next_idx = max_idx if complete_immediately else min(task["current_stage_idx"] + 1, max_idx)
        next_label = stages[next_idx]
        started_at = task["started_at"] or now

        if next_idx >= max_idx:
            artifacts = SubAgentSimulator.build_completion_artifacts(
                task["task_type"], candidate, position
            )
            new_status = TaskStatus.COMPLETED.value
            completed_at = now
            ext_ref = artifacts["external_ref_id"]
            summary = artifacts["output_summary"]

            existing_meta = json.loads(task["metadata_json"] or "{}")
            existing_meta["artifacts"] = artifacts

            conn.execute(
                """
                UPDATE provisioning_tasks
                SET status = ?, current_stage_idx = ?, stage_label = ?,
                    external_ref_id = ?, output_summary = ?, blocker_reason = NULL,
                    metadata_json = ?, started_at = ?, completed_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    new_status,
                    next_idx,
                    next_label,
                    ext_ref,
                    summary,
                    json.dumps(existing_meta),
                    started_at,
                    completed_at,
                    now,
                    task_id,
                ),
            )

            if task["task_type"] == TaskType.EMAIL.value:
                corp_email = artifacts.get("work_email")
                conn.execute(
                    "UPDATE candidates SET corporate_email = ?, updated_at = ? WHERE id = ?",
                    (corp_email, now, candidate["id"]),
                )
                candidate["corporate_email"] = corp_email

                dep_tasks = conn.execute(
                    "SELECT * FROM provisioning_tasks WHERE candidate_id = ? AND depends_on = 'EMAIL' AND status = 'PENDING'",
                    (candidate["id"],),
                ).fetchall()
                for dt in dep_tasks:
                    dt_meta = SUBAGENT_METADATA[dt["task_type"]]
                    conn.execute(
                        """
                        UPDATE provisioning_tasks
                        SET status = 'IN_PROGRESS', current_stage_idx = 1,
                            stage_label = ?, started_at = ?, updated_at = ?
                        WHERE id = ?
                        """,
                        (dt_meta["stages"][1], now, now, dt["id"]),
                    )

            conn.commit()
            conn.close()

            log_agent_event(
                candidate_id=candidate["id"],
                agent_name=task["agent_name"],
                event_type="STEP_COMPLETED",
                message=f"{task['agent_name']} completed for {candidate['full_name']}: {summary}",
                details=artifacts,
            )

            OnboardingOrchestrator.check_candidate_completion(candidate["id"])
        else:
            new_status = TaskStatus.IN_PROGRESS.value
            conn.execute(
                """
                UPDATE provisioning_tasks
                SET status = ?, current_stage_idx = ?, stage_label = ?,
                    blocker_reason = NULL, started_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (new_status, next_idx, next_label, started_at, now, task_id),
            )
            conn.commit()
            conn.close()

            log_agent_event(
                candidate_id=candidate["id"],
                agent_name=task["agent_name"],
                event_type="STEP_PROGRESS",
                message=f"{task['agent_name']} ({candidate['full_name']}): {next_label}",
                details={"task_id": task_id, "stage": next_label},
            )

        conn2 = get_conn()
        updated = dict_from_row(
            conn2.execute("SELECT * FROM provisioning_tasks WHERE id = ?", (task_id,)).fetchone()
        )
        conn2.close()
        updated["current_stage_label"] = updated.get("stage_label")
        return {**updated, "task": updated}

    @staticmethod
    def simulate_task_blocker(task_id: str, reason: str) -> Dict[str, Any]:
        """Flags a delay on an onboarding step so HR can review it in the HR Action Center."""
        conn = get_conn()
        task_row = conn.execute("SELECT * FROM provisioning_tasks WHERE id = ?", (task_id,)).fetchone()
        if not task_row:
            conn.close()
            raise ValueError("Task not found")
        task = dict_from_row(task_row)
        cand = dict_from_row(
            conn.execute("SELECT * FROM candidates WHERE id = ?", (task["candidate_id"],)).fetchone()
        )
        now = utc_now_iso()
        conn.execute(
            """
            UPDATE provisioning_tasks
            SET status = 'BLOCKED', blocker_reason = ?, stage_label = ?, updated_at = ?
            WHERE id = ?
            """,
            (reason, f"Delayed: {reason}", now, task_id),
        )
        conn.commit()
        conn.close()

        log_agent_event(
            candidate_id=task["candidate_id"],
            agent_name=task["agent_name"],
            event_type="STEP_DELAYED",
            message=f"Delay flagged on {task['agent_name']} for {cand['full_name']}: {reason}",
            details={"task_id": task_id, "blocker_reason": reason},
        )

        cc_list = _candidate_cc_list(cand)
        dispatch_stakeholder_email(
            candidate_id=cand["id"],
            event_type="ONBOARDING_DELAY",
            subject=f"[Attention Needed] Onboarding Delay for {cand['full_name']} — {task['agent_name']}",
            recipient_to=cand["hr_email"],
            recipients_cc=cc_list,
            body_html=f"""
            <div style="font-family:-apple-system,BlinkMacSystemFont,'Helvetica Neue',Arial,sans-serif;padding:20px;border-left:4px solid #FF9500;background:#FFF9F0;border-radius:12px;">
                <h3 style="margin-top:0;color:#B25000;">Onboarding Step Needs Attention</h3>
                <p><strong>Candidate:</strong> {cand['full_name']} ({cand['role_category'].title()})</p>
                <p><strong>Onboarding Step:</strong> {task['agent_name']}</p>
                <p><strong>Reason for Delay:</strong> {reason}</p>
                <p><strong>Start Date:</strong> {cand['joining_date']}</p>
                <p>Please open the <strong>HR Action Center</strong> in Sybyl People to review and resolve this item.</p>
                <p style="font-size:12px;color:#6E6E73;">Copied (CC): {'; '.join(cc_list)}</p>
            </div>
            """,
        )

        conn2 = get_conn()
        updated = dict_from_row(
            conn2.execute("SELECT * FROM provisioning_tasks WHERE id = ?", (task_id,)).fetchone()
        )
        conn2.close()
        return {"task": updated}

    @staticmethod
    def run_all_subagents_for_candidate(candidate_id: str) -> List[Dict[str, Any]]:
        """Completes all remaining onboarding steps for a candidate in order."""
        conn = get_conn()
        tasks = [
            dict_from_row(r)
            for r in conn.execute(
                "SELECT * FROM provisioning_tasks WHERE candidate_id = ? ORDER BY CASE WHEN depends_on IS NULL THEN 0 ELSE 1 END",
                (candidate_id,),
            ).fetchall()
        ]
        conn.close()

        for t in tasks:
            if t["depends_on"] is None and t["status"] != TaskStatus.COMPLETED.value:
                OnboardingOrchestrator.advance_task_stage(t["id"], complete_immediately=True)

        conn = get_conn()
        dep_tasks = [
            dict_from_row(r)
            for r in conn.execute(
                "SELECT * FROM provisioning_tasks WHERE candidate_id = ? AND depends_on IS NOT NULL",
                (candidate_id,),
            ).fetchall()
        ]
        conn.close()

        for t in dep_tasks:
            if t["status"] != TaskStatus.COMPLETED.value:
                OnboardingOrchestrator.advance_task_stage(t["id"], complete_immediately=True)

        conn = get_conn()
        final_tasks = [
            dict_from_row(r)
            for r in conn.execute(
                "SELECT * FROM provisioning_tasks WHERE candidate_id = ?", (candidate_id,)
            ).fetchall()
        ]
        conn.close()
        return final_tasks

    @staticmethod
    def check_candidate_completion(candidate_id: str) -> bool:
        conn = get_conn()
        tasks = [
            dict_from_row(r)
            for r in conn.execute(
                "SELECT * FROM provisioning_tasks WHERE candidate_id = ?", (candidate_id,)
            ).fetchall()
        ]
        if not tasks:
            conn.close()
            return False

        all_done = all(t["status"] == TaskStatus.COMPLETED.value for t in tasks)
        if all_done:
            cand = dict_from_row(
                conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
            )
            if cand["overall_stage"] != "COMPLETED":
                now = utc_now_iso()
                conn.execute(
                    "UPDATE candidates SET overall_stage = 'COMPLETED', updated_at = ? WHERE id = ?",
                    (now, candidate_id),
                )
                conn.commit()
                conn.close()

                summaries = "<br>".join(
                    f"• <strong>{t['agent_name']}:</strong> {t['output_summary']}"
                    for t in tasks
                )
                log_agent_event(
                    candidate_id=candidate_id,
                    agent_name="Onboarding Coordinator",
                    event_type="READY_FOR_DAY_1",
                    message=f"All {len(tasks)} onboarding steps completed for {cand['full_name']} ({cand['role_category'].title()}). Ready for Day 1!",
                    details={"completed_tasks": [t["task_type"] for t in tasks]},
                )

                cc_list = _candidate_cc_list(cand)
                dispatch_stakeholder_email(
                    candidate_id=candidate_id,
                    event_type="READY_FOR_DAY_1",
                    subject=f"[Ready for Day 1] Onboarding Complete for {cand['full_name']}",
                    recipient_to=cand["personal_email"],
                    recipients_cc=cc_list,
                    body_html=f"""
                    <div style="font-family:-apple-system,BlinkMacSystemFont,'Helvetica Neue',Arial,sans-serif;padding:24px;border:1px solid #34C759;border-radius:14px;background:#F2FBF5;">
                        <h2 style="margin-top:0;color:#1D7A3B;">Ready for Day 1 — Onboarding Complete</h2>
                        <p>All onboarding items for <strong>{cand['full_name']}</strong> (<strong>{cand['role_category'].title()}</strong>) are now complete:</p>
                        <div style="background:#ffffff;padding:16px;border-radius:10px;margin:14px 0;line-height:1.7;">
                            {summaries}
                        </div>
                        <p><strong>Start Date:</strong> {cand['joining_date']}</p>
                        <p style="font-size:12px;color:#6E6E73;">Copied (CC): {'; '.join(cc_list)}</p>
                    </div>
                    """,
                )
                return True
        conn.close()
        return all_done


class OfferESignAgent:
    """Handles sending offer letters, recording candidate signatures, and tracking offer expiry."""

    @staticmethod
    def create_batch_offers(
        req: BatchOnboardingRequest, base_url: str = "http://localhost:8080"
    ) -> Dict[str, Any]:
        batch_id = f"batch-{uuid.uuid4().hex[:8]}"
        now_dt = datetime.now(timezone.utc)
        now = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        created_records = []

        for item in req.candidates:
            conn = get_conn()
            pos_row = conn.execute(
                "SELECT * FROM positions WHERE id = ?", (item.position_id,)
            ).fetchone()
            if not pos_row:
                conn.close()
                raise ValueError(f"Position {item.position_id} not found")
            position = dict_from_row(pos_row)

            cand_id = f"cand-{uuid.uuid4().hex[:8]}"
            offer_id = f"off-{uuid.uuid4().hex[:8]}"
            signing_token = f"sig-{uuid.uuid4().hex[:12]}"
            valid_hours = item.offer_valid_hours or req.offer_expires_in_hours or 72
            expires_dt = now_dt + timedelta(hours=valid_hours)
            expires_at = expires_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            comp_val = item.compensation or item.compensation_package or "$95,000 / yr"

            if req.cc_emails and req.cc_emails.strip():
                cc_list = parse_cc_emails(req.cc_emails, position["hod_email"])
            else:
                cc_list = parse_cc_emails(req.hr_email, position["hod_email"], req.ceo_email)
            cc_joined = "; ".join(cc_list)
            primary_hr = cc_list[0] if cc_list else (req.hr_email or "hr@sybyl.com")
            primary_ceo = cc_list[-1] if len(cc_list) > 1 else (req.ceo_email or "ceo@sybyl.com")

            candidate = {
                "id": cand_id,
                "batch_id": batch_id,
                "batch_name": req.batch_name,
                "position_id": item.position_id,
                "full_name": item.full_name,
                "personal_email": item.personal_email,
                "phone": item.phone or "+1-555-0199",
                "corporate_email": None,
                "role_category": item.role_category.value,
                "compensation": comp_val,
                "joining_date": item.joining_date,
                "hr_email": primary_hr,
                "hod_email": position["hod_email"],
                "ceo_email": primary_ceo,
                "cc_emails": cc_joined,
                "overall_stage": "OFFER_SENT",
                "created_at": now,
                "updated_at": now,
            }

            offer = {
                "id": offer_id,
                "candidate_id": cand_id,
                "signing_token": signing_token,
                "esign_provider": item.esign_provider,
                "status": OfferStatus.SENT.value,
                "sent_at": now,
                "expires_at": expires_at,
            }

            pdf_path = generate_offer_pdf(candidate, position, offer, signed=False)

            conn.execute(
                """
                INSERT INTO candidates (
                    id, batch_id, batch_name, position_id, full_name,
                    personal_email, phone, corporate_email, role_category,
                    compensation, joining_date, hr_email, hod_email, ceo_email,
                    cc_emails, overall_stage, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate["id"],
                    candidate["batch_id"],
                    candidate["batch_name"],
                    candidate["position_id"],
                    candidate["full_name"],
                    candidate["personal_email"],
                    candidate["phone"],
                    candidate["corporate_email"],
                    candidate["role_category"],
                    candidate["compensation"],
                    candidate["joining_date"],
                    candidate["hr_email"],
                    candidate["hod_email"],
                    candidate["ceo_email"],
                    candidate["cc_emails"],
                    candidate["overall_stage"],
                    candidate["created_at"],
                    candidate["updated_at"],
                ),
            )

            conn.execute(
                """
                INSERT INTO offer_letters (
                    id, candidate_id, signing_token, esign_provider, status,
                    sent_at, expires_at, pdf_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    offer_id,
                    cand_id,
                    signing_token,
                    item.esign_provider,
                    OfferStatus.SENT.value,
                    now,
                    expires_at,
                    pdf_path,
                ),
            )
            conn.commit()
            conn.close()

            signing_url = f"{base_url.rstrip('/')}/sign/{signing_token}"
            role_steps = ", ".join(
                STEP_FRIENDLY_LABELS.get(s, s)
                for s in ROLE_ONBOARDING_STEPS[item.role_category.value]
            )

            tpl = get_offer_template(item.role_category.value)
            intro_text = render_template_text(
                tpl.get("intro_text", ""), candidate, position, offer
            )
            subject_line = render_template_text(
                tpl.get("email_subject_template", "[Offer Letter] {position_title} — {candidate_name}"),
                candidate,
                position,
                offer,
            )

            log_agent_event(
                candidate_id=cand_id,
                agent_name="Offer Management",
                event_type="OFFER_SENT",
                message=(
                    f"Sent offer letter to {item.full_name} for {position['title']} "
                    f"({item.role_category.value.title()}) — CC: {cc_joined}."
                ),
                details={
                    "offer_id": offer_id,
                    "signing_url": signing_url,
                    "expires_at": expires_at,
                    "cc": cc_list,
                },
            )

            email_html = f"""
            <div style="font-family:-apple-system,BlinkMacSystemFont,'Helvetica Neue',Arial,sans-serif;max-width:640px;margin:0 auto;padding:24px;border:1px solid #E5E5EA;border-radius:16px;background:#ffffff;color:#1D1D1F;">
                <div style="background:#1D1D1F;color:#ffffff;padding:18px 22px;border-radius:12px;margin-bottom:20px;">
                    <h2 style="margin:0;font-size:18px;font-weight:600;">Sybyl — {tpl.get('title', 'Official Offer of Appointment')}</h2>
                    <p style="margin:4px 0 0;color:#A1A1A6;font-size:13px;">{position['title']} ({position['department']})</p>
                </div>
                <p>Dear <strong>{item.full_name}</strong>,</p>
                <p>{intro_text}</p>
                <table style="width:100%;border-collapse:collapse;margin:16px 0;background:#F5F5F7;border-radius:12px;padding:12px;">
                    <tr><td style="padding:8px 14px;color:#6E6E73;"><strong>Role Category:</strong></td><td style="padding:8px 14px;">{item.role_category.value.title()} ({role_steps})</td></tr>
                    <tr><td style="padding:8px 14px;color:#6E6E73;"><strong>Compensation:</strong></td><td style="padding:8px 14px;">{comp_val}</td></tr>
                    <tr><td style="padding:8px 14px;color:#6E6E73;"><strong>Start Date:</strong></td><td style="padding:8px 14px;">{item.joining_date}</td></tr>
                    <tr><td style="padding:8px 14px;color:#6E6E73;"><strong>Offer Valid Until:</strong></td><td style="padding:8px 14px;color:#D93025;font-weight:600;">{expires_at[:10]}</td></tr>
                </table>
                <div style="margin:24px 0;text-align:center;">
                    <a href="{signing_url}" style="background:#0071E3;color:#ffffff;text-decoration:none;padding:12px 26px;border-radius:999px;font-weight:600;display:inline-block;">Review &amp; Sign Offer Letter</a>
                </div>
                <p style="font-size:12px;color:#86868B;border-top:1px solid #E5E5EA;padding-top:12px;">
                    <strong>Copied (CC):</strong> {cc_joined}
                </p>
            </div>
            """

            dispatch_stakeholder_email(
                candidate_id=cand_id,
                event_type="OFFER_SENT",
                subject=subject_line,
                recipient_to=item.personal_email,
                recipients_cc=cc_list,
                body_html=email_html,
                attachment_path=pdf_path,
            )

            created_records.append(
                {
                    "candidate_id": cand_id,
                    "full_name": item.full_name,
                    "role_category": item.role_category.value,
                    "position_title": position["title"],
                    "offer_id": offer_id,
                    "offer": {
                        "id": offer_id,
                        "signing_token": signing_token,
                        "status": OfferStatus.SENT.value,
                    },
                    "cc_emails": cc_joined,
                    "signing_token": signing_token,
                    "signing_url": f"/sign/{signing_token}",
                    "public_signing_url": signing_url,
                }
            )

        return {
            "batch_id": batch_id,
            "batch_name": req.batch_name,
            "count": len(created_records),
            "dispatched_count": len(created_records),
            "dispatched": created_records,
            "created_offers": created_records,
            "offers": created_records,
            "created": created_records,
        }

    @staticmethod
    def accept_offer(
        signing_token: str,
        signer_name: str,
        signature_data: Optional[str] = None,
        signature_type: str = "typed",
        comments: Optional[str] = None,
        auto_advance_first_step: bool = True,
    ) -> Dict[str, Any]:
        conn = get_conn()
        offer_row = conn.execute(
            "SELECT * FROM offer_letters WHERE signing_token = ?", (signing_token,)
        ).fetchone()
        if not offer_row:
            conn.close()
            raise ValueError("Invalid offer link")

        offer = dict_from_row(offer_row)
        if offer["status"] == OfferStatus.LAPSED.value:
            conn.close()
            raise ValueError("This offer has expired and can no longer be signed.")
        if offer["status"] == OfferStatus.DECLINED.value:
            conn.close()
            raise ValueError("This offer was previously declined.")
        if offer["status"] == OfferStatus.ACCEPTED.value:
            conn.close()
            return {"status": "ALREADY_ACCEPTED", "candidate_id": offer["candidate_id"]}

        cand_row = conn.execute(
            "SELECT * FROM candidates WHERE id = ?", (offer["candidate_id"],)
        ).fetchone()
        candidate = dict_from_row(cand_row)
        pos_row = conn.execute(
            "SELECT * FROM positions WHERE id = ?", (candidate["position_id"],)
        ).fetchone()
        position = dict_from_row(pos_row)

        now = utc_now_iso()
        sig_hash = compute_signature_hash(candidate["id"], signer_name, now)

        offer_updated = dict(offer)
        offer_updated.update(
            {
                "status": OfferStatus.ACCEPTED.value,
                "responded_at": now,
                "signer_name": signer_name,
                "signature_data": signature_data or signer_name,
                "signature_type": signature_type,
                "signature_hash": sig_hash,
                "comments": comments,
            }
        )

        signed_pdf_path = generate_offer_pdf(candidate, position, offer_updated, signed=True)

        conn.execute(
            """
            UPDATE offer_letters
            SET status = 'ACCEPTED',
                responded_at = ?,
                signer_name = ?,
                signature_data = ?,
                signature_type = ?,
                signature_hash = ?,
                comments = ?,
                signed_pdf_path = ?
            WHERE signing_token = ?
            """,
            (
                now,
                signer_name,
                signature_data or signer_name,
                signature_type,
                sig_hash,
                comments,
                signed_pdf_path,
                signing_token,
            ),
        )
        conn.execute(
            "UPDATE candidates SET overall_stage = 'ACCEPTED', updated_at = ? WHERE id = ?",
            (now, candidate["id"]),
        )
        conn.commit()
        conn.close()

        cc_list = _candidate_cc_list(candidate)
        log_agent_event(
            candidate_id=candidate["id"],
            agent_name="Offer Management",
            event_type="OFFER_ACCEPTED",
            message=(
                f"{candidate['full_name']} signed and accepted the offer for {position['title']}. "
                f"CC recipients notified ({'; '.join(cc_list)})."
            ),
            details={
                "signer_name": signer_name,
                "role_category": candidate["role_category"],
            },
        )

        steps_list = [
            STEP_FRIENDLY_LABELS.get(s, s)
            for s in ROLE_ONBOARDING_STEPS.get(candidate["role_category"], ["EMAIL"])
        ]
        dispatch_stakeholder_email(
            candidate_id=candidate["id"],
            event_type="OFFER_ACCEPTED",
            subject=f"[Offer Accepted] {candidate['full_name']} — {position['title']}",
            recipient_to=candidate["personal_email"],
            recipients_cc=cc_list,
            body_html=f"""
            <div style="font-family:-apple-system,BlinkMacSystemFont,'Helvetica Neue',Arial,sans-serif;padding:22px;border:1px solid #34C759;border-radius:14px;background:#F2FBF5;color:#1D1D1F;">
                <h2 style="margin-top:0;color:#1D7A3B;">Offer Signed &amp; Accepted</h2>
                <p><strong>{candidate['full_name']}</strong> has signed and accepted the offer for <strong>{position['title']}</strong> ({position['department']}).</p>
                <ul style="line-height:1.7;">
                    <li><strong>Onboarding Category:</strong> {candidate['role_category'].title()}</li>
                    <li><strong>Start Date:</strong> {candidate['joining_date']}</li>
                    <li><strong>Onboarding Setup Started:</strong> {', '.join(steps_list)}</li>
                </ul>
                <p style="font-size:12px;color:#6E6E73;">Copied (CC): {'; '.join(cc_list)}</p>
            </div>
            """,
            attachment_path=signed_pdf_path,
        )

        spawned_tasks = OnboardingOrchestrator.spawn_provisioning_tasks_for_candidate(candidate["id"])

        return {
            "status": "ACCEPTED",
            "candidate_id": candidate["id"],
            "role_category": candidate["role_category"],
            "signature_hash": sig_hash,
            "spawned_tasks": spawned_tasks,
            "spawned_subagent_tasks": spawned_tasks,
        }

    @staticmethod
    def decline_offer(
        signing_token: str, decline_reason: str, comments: Optional[str] = None
    ) -> Dict[str, Any]:
        conn = get_conn()
        offer_row = conn.execute(
            "SELECT * FROM offer_letters WHERE signing_token = ?", (signing_token,)
        ).fetchone()
        if not offer_row:
            conn.close()
            raise ValueError("Invalid offer link")

        offer = dict_from_row(offer_row)
        cand = dict_from_row(
            conn.execute("SELECT * FROM candidates WHERE id = ?", (offer["candidate_id"],)).fetchone()
        )
        pos = dict_from_row(
            conn.execute("SELECT * FROM positions WHERE id = ?", (cand["position_id"],)).fetchone()
        )

        now = utc_now_iso()
        conn.execute(
            """
            UPDATE offer_letters
            SET status = 'DECLINED', responded_at = ?, decline_reason = ?, comments = ?
            WHERE signing_token = ?
            """,
            (now, decline_reason, comments, signing_token),
        )
        conn.execute(
            "UPDATE candidates SET overall_stage = 'DECLINED', updated_at = ? WHERE id = ?",
            (now, cand["id"]),
        )
        conn.commit()
        conn.close()

        cc_list = _candidate_cc_list(cand)
        log_agent_event(
            candidate_id=cand["id"],
            agent_name="Offer Management",
            event_type="OFFER_DECLINED",
            message=(
                f"{cand['full_name']} declined the offer for {pos['title']} ({decline_reason}). "
                f"CC recipients notified ({'; '.join(cc_list)})."
            ),
            details={"decline_reason": decline_reason, "comments": comments},
        )

        dispatch_stakeholder_email(
            candidate_id=cand["id"],
            event_type="OFFER_DECLINED",
            subject=f"[Offer Declined] {cand['full_name']} — {pos['title']}",
            recipient_to=cand["hr_email"],
            recipients_cc=cc_list,
            body_html=f"""
            <div style="font-family:-apple-system,BlinkMacSystemFont,'Helvetica Neue',Arial,sans-serif;padding:22px;border:1px solid #FF3B30;border-radius:14px;background:#FFF2F2;color:#1D1D1F;">
                <h2 style="margin-top:0;color:#D93025;">Offer Declined</h2>
                <p><strong>{cand['full_name']}</strong> has declined the offer for <strong>{pos['title']}</strong> ({pos['department']}).</p>
                <p><strong>Reason:</strong> {decline_reason}</p>
                {f"<p><strong>Candidate Note:</strong> {comments}</p>" if comments else ""}
                <p><strong>Next Step:</strong> You can send a replacement offer from the Offer Launchpad.</p>
                <p style="font-size:12px;color:#6E6E73;">Copied (CC): {'; '.join(cc_list)}</p>
            </div>
            """,
        )

        return {
            "status": "DECLINED",
            "candidate_id": cand["id"],
            "decline_reason": decline_reason,
        }

    @staticmethod
    def lapse_offer(candidate_id: str, reason: str = "Offer validity period ended without a response") -> Dict[str, Any]:
        conn = get_conn()
        cand_row = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
        if not cand_row:
            conn.close()
            raise ValueError("Candidate not found")
        cand = dict_from_row(cand_row)
        offer = dict_from_row(
            conn.execute("SELECT * FROM offer_letters WHERE candidate_id = ?", (candidate_id,)).fetchone()
        )
        pos = dict_from_row(
            conn.execute("SELECT * FROM positions WHERE id = ?", (cand["position_id"],)).fetchone()
        )

        now = utc_now_iso()
        conn.execute(
            """
            UPDATE offer_letters
            SET status = 'LAPSED', responded_at = ?, decline_reason = ?
            WHERE candidate_id = ?
            """,
            (now, reason, candidate_id),
        )
        conn.execute(
            "UPDATE candidates SET overall_stage = 'LAPSED', updated_at = ? WHERE id = ?",
            (now, candidate_id),
        )
        conn.commit()
        conn.close()

        cc_list = _candidate_cc_list(cand)
        log_agent_event(
            candidate_id=cand["id"],
            agent_name="Offer Management",
            event_type="OFFER_LAPSED",
            message=(
                f"Offer for {cand['full_name']} ({pos['title']}) expired without a signature. "
                f"CC recipients notified ({'; '.join(cc_list)})."
            ),
            details={"offer_id": offer["id"], "expires_at": offer["expires_at"], "reason": reason},
        )

        dispatch_stakeholder_email(
            candidate_id=cand["id"],
            event_type="OFFER_EXPIRED",
            subject=f"[Offer Expired] {cand['full_name']} — {pos['title']}",
            recipient_to=cand["personal_email"],
            recipients_cc=cc_list,
            body_html=f"""
            <div style="font-family:-apple-system,BlinkMacSystemFont,'Helvetica Neue',Arial,sans-serif;padding:22px;border:1px solid #FF9500;border-radius:14px;background:#FFF9F0;color:#1D1D1F;">
                <h2 style="margin-top:0;color:#B25000;">Offer Expired</h2>
                <p>The offer extended to <strong>{cand['full_name']}</strong> for <strong>{pos['title']}</strong> ({pos['department']}) expired on <strong>{offer['expires_at'][:10]}</strong> without a response.</p>
                <p style="font-size:12px;color:#6E6E73;">Copied (CC): {'; '.join(cc_list)}</p>
            </div>
            """,
        )

        return {"status": "LAPSED", "candidate_id": candidate_id}

    @staticmethod
    def scan_and_expire_overdue_offers() -> List[str]:
        now = utc_now_iso()
        conn = get_conn()
        overdue = conn.execute(
            """
            SELECT candidate_id FROM offer_letters
            WHERE status IN ('SENT', 'VIEWED') AND expires_at < ?
            """,
            (now,),
        ).fetchall()
        conn.close()

        lapsed_ids = []
        for row in overdue:
            cid = row["candidate_id"]
            OfferESignAgent.lapse_offer(cid)
            lapsed_ids.append(cid)
        return lapsed_ids
