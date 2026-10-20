"""Multi-Agent Orchestrator for HR Offboarding Pro (Reverse De-Provisioning & Clearance)."""

import json
import secrets
from typing import Any, Dict, List, Optional
from .database import get_db, utc_now_iso
from .email_service import send_or_log_email
from .models import (
    EmployeeExitCreate,
    ClearanceStatus,
    ROLE_OFFBOARDING_STEPS,
    RoleCategory,
    SUBAGENT_METADATA,
    TaskStatus,
    TaskType,
)
from .pdf_generator import calculate_final_settlement


def log_agent_event(
    conn,
    candidate_id: Optional[int],
    agent_name: str,
    event_type: str,
    message: str,
    metadata: Optional[dict] = None,
):
    conn.execute(
        """
        INSERT INTO agent_events (candidate_id, agent_name, event_type, message, metadata_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            candidate_id,
            agent_name,
            event_type,
            message,
            json.dumps(metadata or {}),
            utc_now_iso(),
        ),
    )


def _generate_work_email(full_name: str, candidate_id: int) -> str:
    parts = [p.lower() for p in full_name.strip().split() if p.isalnum() or p.replace("-", "").isalnum()]
    if len(parts) >= 2:
        slug = f"{parts[0]}.{parts[-1]}"
    elif parts:
        slug = parts[0]
    else:
        slug = f"employee{candidate_id}"
    slug = "".join(c for c in slug if c.isalnum() or c == ".")
    return f"{slug}@acme.com"


class ClearanceESignAgent:
    """Subagent 0: Generates Final Clearance & Settlement Statements, dispatches e-sign links, and processes employee sign-offs or settlement queries."""

    AGENT_NAME = "Final Clearance & Settlement Agent"

    @classmethod
    def create_employee_exit_and_send_clearance(cls, payload: EmployeeExitCreate) -> Dict[str, Any]:
        now = utc_now_iso()
        signing_token = f"clr-{secrets.token_urlsafe(12)}"
        last_day = payload.last_working_day or payload.start_date or "2026-05-22"

        settlement = calculate_final_settlement(
            compensation_amount=payload.compensation_amount,
            compensation_period=payload.compensation_period,
            days_worked_final_month=payload.days_worked_final_month,
            unused_leave_days=payload.unused_leave_days,
            asset_deduction=payload.asset_deduction,
        )

        with get_db() as conn:
            cur = conn.execute(
                """
                INSERT INTO candidates (
                    full_name, personal_email, phone, role_category, job_title,
                    department, manager_name, location, compensation_amount,
                    compensation_period, join_date, notice_date, last_working_day,
                    start_date, exit_type, exit_reason, days_worked_final_month,
                    unused_leave_days, asset_deduction, deduction_notes,
                    pro_rata_pay, leave_encashment, net_settlement,
                    custom_notes, offboarding_status, onboarding_status,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'CLEARANCE_IN_PROGRESS', 'OFFER_SENT', ?, ?)
                """,
                (
                    payload.full_name,
                    payload.personal_email,
                    payload.phone,
                    payload.role_category.value,
                    payload.job_title,
                    payload.department,
                    payload.manager_name,
                    payload.location,
                    payload.compensation_amount,
                    payload.compensation_period,
                    payload.join_date,
                    payload.notice_date,
                    last_day,
                    last_day,
                    payload.exit_type,
                    payload.exit_reason,
                    payload.days_worked_final_month,
                    payload.unused_leave_days,
                    payload.asset_deduction,
                    payload.deduction_notes or "All company equipment accounted for",
                    settlement["pro_rata_pay"],
                    settlement["leave_encashment"],
                    settlement["net_settlement"],
                    payload.custom_notes,
                    now,
                    now,
                ),
            )
            candidate_id = cur.lastrowid

            # Populate existing active enterprise identifiers to be de-provisioned in reverse
            work_email = _generate_work_email(payload.full_name, candidate_id)
            laptop_serial = payload.assigned_laptop_serial or (
                f"MBP16-ACME-{4100 + candidate_id}" if payload.role_category != RoleCategory.INTERN else None
            )
            uber_pass = (
                f"UBER-CORP-{7100 + candidate_id}" if payload.role_category != RoleCategory.INTERN else None
            )
            insurance_id = (
                f"HLTH-ACME-{9100 + candidate_id}" if payload.role_category == RoleCategory.EMPLOYEE else None
            )

            conn.execute(
                """
                UPDATE candidates
                SET work_email = ?, assigned_laptop_serial = ?, uber_pass_id = ?, insurance_policy_id = ?
                WHERE id = ?
                """,
                (work_email, laptop_serial, uber_pass, insurance_id, candidate_id),
            )

            conn.execute(
                """
                INSERT INTO offer_letters (candidate_id, signing_token, status, sent_at, pdf_version)
                VALUES (?, ?, ?, ?, 1)
                """,
                (candidate_id, signing_token, ClearanceStatus.SENT.value, now),
            )

            log_agent_event(
                conn,
                candidate_id,
                cls.AGENT_NAME,
                "EXIT_NOTICE_LOGGED",
                (
                    f"Logged {payload.exit_type} for {payload.full_name} ({payload.role_category.value} - {payload.job_title}). "
                    f"Calculated Net Final Settlement: ${settlement['net_settlement']:,.2f} & dispatched e-sign link."
                ),
                {"signing_token": signing_token, "role_category": payload.role_category.value, "net_settlement": settlement["net_settlement"]},
            )

            # Immediately spawn reverse de-provisioning tasks for the exiting role
            OffboardingOrchestrator._spawn_role_tasks(
                conn, candidate_id, payload.role_category, payload.full_name
            )

        email_body = (
            f"Hello {payload.full_name},\n\n"
            f"Your exit notice ({payload.exit_type}) for the position of {payload.job_title} ({payload.department}) "
            f"has been logged with a Last Working Day of {last_day}.\n\n"
            f"Net Final Settlement Payable: ${settlement['net_settlement']:,.2f} "
            f"(Pro-Rata Salary: ${settlement['pro_rata_pay']:,.2f} + Leave Encashment: ${settlement['leave_encashment']:,.2f}).\n\n"
            f"Please review your department clearance checklist and digitally sign your Final Clearance & Settlement Statement:\n"
            f"Clearance E-Sign Link: /sign/{signing_token}\n\n"
            f"Warm regards,\n"
            f"Acme People Operations — Exit & Clearance Team"
        )
        send_or_log_email(
            candidate_id=candidate_id,
            recipient_email=payload.personal_email,
            recipient_name=payload.full_name,
            subject=f"Action Required: Final Clearance & Settlement Statement ({payload.job_title}) — Acme Corp.",
            body_text=email_body,
            category="CLEARANCE_STATEMENT_SENT",
            attach_clearance_pdf=True,
        )

        return OffboardingOrchestrator.get_candidate_detail(candidate_id)

    # Alias for compatibility
    create_candidate_and_send_offer = create_employee_exit_and_send_clearance

    @classmethod
    def mark_viewed(cls, signing_token: str) -> Optional[Dict[str, Any]]:
        now = utc_now_iso()
        with get_db() as conn:
            offer = conn.execute(
                "SELECT * FROM offer_letters WHERE signing_token = ?", (signing_token,)
            ).fetchone()
            if not offer:
                return None
            if offer["status"] == ClearanceStatus.SENT.value:
                conn.execute(
                    "UPDATE offer_letters SET status = ?, viewed_at = ? WHERE id = ?",
                    (ClearanceStatus.VIEWED.value, now, offer["id"]),
                )
                conn.execute(
                    "UPDATE candidates SET onboarding_status = 'OFFER_VIEWED', updated_at = ? WHERE id = ?",
                    (now, offer["candidate_id"]),
                )
                cand = conn.execute(
                    "SELECT full_name FROM candidates WHERE id = ?", (offer["candidate_id"],)
                ).fetchone()
                log_agent_event(
                    conn,
                    offer["candidate_id"],
                    cls.AGENT_NAME,
                    "CLEARANCE_VIEWED",
                    f"Employee {cand['full_name']} opened the Final Clearance & Settlement Statement in the E-Sign Portal.",
                )
        return OffboardingOrchestrator.get_candidate_by_token(signing_token)

    @classmethod
    def accept_clearance(
        cls,
        signing_token: str,
        signature_name: str,
        forwarding_address: Optional[str] = None,
        handover_confirmed: bool = True,
    ) -> Dict[str, Any]:
        now = utc_now_iso()
        with get_db() as conn:
            offer = conn.execute(
                "SELECT * FROM offer_letters WHERE signing_token = ?", (signing_token,)
            ).fetchone()
            if not offer:
                raise ValueError("Invalid signing token.")
            candidate_id = offer["candidate_id"]
            cand = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
            if not cand:
                raise ValueError("Employee record not found.")

            sig = (signature_name or cand["full_name"]).strip()
            fwd = (forwarding_address or cand["personal_email"]).strip()
            conn.execute(
                """
                UPDATE offer_letters
                SET status = ?, responded_at = ?, viewed_at = COALESCE(viewed_at, ?),
                    signature_text = ?, forwarding_address = ?, handover_confirmed = ?, decline_reason = NULL
                WHERE id = ?
                """,
                (
                    ClearanceStatus.ACCEPTED.value,
                    now,
                    now,
                    sig,
                    fwd,
                    1 if handover_confirmed else 0,
                    offer["id"],
                ),
            )

            # Ensure reverse de-provisioning tasks exist
            role_cat = RoleCategory(cand["role_category"])
            OffboardingOrchestrator._spawn_role_tasks(conn, candidate_id, role_cat, cand["full_name"])

            # Check if all clearance tasks are already completed
            remaining = conn.execute(
                "SELECT COUNT(*) as c FROM provisioning_tasks WHERE candidate_id = ? AND status != ?",
                (candidate_id, TaskStatus.COMPLETED.value),
            ).fetchone()["c"]

            if remaining == 0:
                new_off_status = "OFFBOARDED"
                new_onb_status = "ONBOARDED"
            else:
                new_off_status = "CLEARANCE_SIGNED"
                new_onb_status = "PROVISIONING"

            conn.execute(
                "UPDATE candidates SET offboarding_status = ?, onboarding_status = ?, updated_at = ? WHERE id = ?",
                (new_off_status, new_onb_status, now, candidate_id),
            )

            log_agent_event(
                conn,
                candidate_id,
                cls.AGENT_NAME,
                "CLEARANCE_SIGNED",
                (
                    f"Employee {cand['full_name']} e-signed Final Clearance & Settlement Statement as '{sig}'. "
                    f"Net Final Settlement of ${cand['net_settlement']:,.2f} approved for payout."
                ),
                {"signature": sig, "forwarding_address": fwd},
            )

        send_or_log_email(
            candidate_id=candidate_id,
            recipient_email="people-ops@acme.com",
            recipient_name="HR Exit & Payroll Team",
            subject=f"Clearance Signed: {cand['full_name']} ({cand['job_title']}) — Ready for Final Payout",
            body_text=(
                f"{cand['full_name']} has digitally signed their Final Clearance & Settlement Statement.\n"
                f"Signature: {sig}\n"
                f"Net Final Settlement: ${cand['net_settlement']:,.2f}\n"
                f"Forwarding Email: {fwd}\n"
                f"Reverse De-Provisioning Workflow: Active for {cand['role_category']}."
            ),
            category="HR_CLEARANCE_SIGNED_ALERT",
        )
        return OffboardingOrchestrator.get_candidate_detail(candidate_id)

    # Alias for compatibility
    accept_offer = accept_clearance

    @classmethod
    def dispute_clearance(cls, signing_token: str, reason: str) -> Dict[str, Any]:
        now = utc_now_iso()
        with get_db() as conn:
            offer = conn.execute(
                "SELECT * FROM offer_letters WHERE signing_token = ?", (signing_token,)
            ).fetchone()
            if not offer:
                raise ValueError("Invalid signing token.")
            candidate_id = offer["candidate_id"]
            cand = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
            reason_clean = (
                reason or "Employee requested recalculation of unused leave encashment / final settlement."
            ).strip()

            conn.execute(
                """
                UPDATE offer_letters
                SET status = ?, responded_at = ?, viewed_at = COALESCE(viewed_at, ?), decline_reason = ?
                WHERE id = ?
                """,
                (ClearanceStatus.DECLINED.value, now, now, reason_clean, offer["id"]),
            )
            conn.execute(
                "UPDATE candidates SET offboarding_status = 'SETTLEMENT_DISPUTED', onboarding_status = 'OFFER_DECLINED', updated_at = ? WHERE id = ?",
                (now, candidate_id),
            )
            log_agent_event(
                conn,
                candidate_id,
                cls.AGENT_NAME,
                "SETTLEMENT_DISPUTED",
                (
                    f"ALERT: {cand['full_name']} raised a Final Settlement / Leave Encashment query. "
                    f"Reason: \"{reason_clean}\". Escalated to HR Manager {cand['manager_name']}."
                ),
                {"reason": reason_clean},
            )

        send_or_log_email(
            candidate_id=candidate_id,
            recipient_email="people-ops@acme.com",
            recipient_name=f"HR Team & {cand['manager_name']}",
            subject=f"URGENT: Final Settlement Query Raised — {cand['full_name']} ({cand['job_title']})",
            body_text=(
                f"Attention HR Operations & {cand['manager_name']},\n\n"
                f"Exiting employee {cand['full_name']} ({cand['role_category']} - {cand['job_title']}) "
                f"has submitted a query regarding their Final Clearance & Settlement Statement.\n\n"
                f"Stated Query / Dispute Reason: {reason_clean}\n\n"
                f"Recommended Action: Review unused leave balance and asset deduction in the HR Action Center and reissue the clearance statement."
            ),
            category="HR_SETTLEMENT_DISPUTE_ALERT",
        )
        return OffboardingOrchestrator.get_candidate_detail(candidate_id)

    # Alias for compatibility
    decline_offer = dispute_clearance


# Compatibility alias
OfferLetterAgent = ClearanceESignAgent


class OffboardingOrchestrator:
    """Coordinates reverse role-based de-provisioning subagents across Benefits, Transport, IT Equipment, and IT Security."""

    AGENT_NAME = "Offboarding Orchestrator Agent"

    @classmethod
    def _spawn_role_tasks(
        cls, conn, candidate_id: int, role_category: RoleCategory, full_name: str
    ):
        existing = conn.execute(
            "SELECT COUNT(*) as c FROM provisioning_tasks WHERE candidate_id = ?",
            (candidate_id,),
        ).fetchone()
        if existing and existing["c"] > 0:
            return

        steps = ROLE_OFFBOARDING_STEPS[role_category]
        now = utc_now_iso()

        log_agent_event(
            conn,
            candidate_id,
            cls.AGENT_NAME,
            "REVERSE_WORKFLOW_STARTED",
            f"Launching {role_category.value} reverse offboarding workflow for {full_name}: "
            + " -> ".join(t.value for t in steps),
            {"role_category": role_category.value, "steps": [t.value for t in steps]},
        )

        for task_type in steps:
            meta = SUBAGENT_METADATA[task_type]
            # For INTERN, EMAIL has no LAPTOP prerequisite so it starts immediately at stage 1 (IN_PROGRESS).
            # For TRAINEE and EMPLOYEE, EMAIL depends on LAPTOP return first so email remains active during handover.
            depends_on = meta["depends_on"].value if meta["depends_on"] else None
            if role_category == RoleCategory.INTERN and task_type == TaskType.EMAIL:
                depends_on = None

            if depends_on is None:
                status = TaskStatus.IN_PROGRESS.value
                stage_idx = 1
                current_stage = meta["stages"][1]
            else:
                status = TaskStatus.PENDING.value
                stage_idx = 0
                current_stage = meta["stages"][0]

            conn.execute(
                """
                INSERT INTO provisioning_tasks (
                    candidate_id, task_type, agent_name, department, status,
                    stage_idx, current_stage, total_stages, depends_on, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate_id,
                    task_type.value,
                    meta["agent_name"],
                    meta["department"],
                    status,
                    stage_idx,
                    current_stage,
                    len(meta["stages"]),
                    depends_on,
                    now,
                ),
            )

            if status == TaskStatus.IN_PROGRESS.value:
                log_agent_event(
                    conn,
                    candidate_id,
                    meta["agent_name"],
                    "TASK_STARTED",
                    f"Dispatched to {meta['department']} for {full_name}: '{current_stage}'",
                    {"task_type": task_type.value, "stage_idx": stage_idx},
                )
            else:
                log_agent_event(
                    conn,
                    candidate_id,
                    meta["agent_name"],
                    "TASK_QUEUED",
                    f"Queued for {full_name} (keeps work email active until {depends_on} return is completed).",
                    {"task_type": task_type.value, "depends_on": depends_on},
                )

    @classmethod
    def advance_task_stage(cls, task_id: int, notes: Optional[str] = None) -> Dict[str, Any]:
        now = utc_now_iso()
        with get_db() as conn:
            task = conn.execute(
                "SELECT * FROM provisioning_tasks WHERE id = ?", (task_id,)
            ).fetchone()
            if not task:
                raise ValueError("Clearance task not found.")

            candidate_id = task["candidate_id"]
            cand = conn.execute(
                "SELECT * FROM candidates WHERE id = ?", (candidate_id,)
            ).fetchone()

            if task["status"] == TaskStatus.COMPLETED.value:
                return cls.get_candidate_detail(candidate_id)

            # Enforce reverse dependency: EMAIL cannot be deactivated until LAPTOP is returned (for Employee & Trainee)
            if task["depends_on"]:
                dep = conn.execute(
                    "SELECT status, agent_name FROM provisioning_tasks WHERE candidate_id = ? AND task_type = ?",
                    (candidate_id, task["depends_on"]),
                ).fetchone()
                if dep and dep["status"] != TaskStatus.COMPLETED.value:
                    return {
                        "error": (
                            f"Cannot advance {task['agent_name']} until {dep['agent_name']} is COMPLETED "
                            f"(employee work email remains active until physical laptop handover is verified)."
                        )
                    }

            task_type = TaskType(task["task_type"])
            stages = SUBAGENT_METADATA[task_type]["stages"]
            next_idx = min(task["stage_idx"] + 1, len(stages) - 1)
            next_stage = stages[next_idx]
            is_done = next_idx == len(stages) - 1
            new_status = TaskStatus.COMPLETED.value if is_done else TaskStatus.IN_PROGRESS.value

            artifact_val = task["artifact_value"]
            if is_done and not artifact_val:
                artifact_val = cls._produce_clearance_artifact(
                    conn, candidate_id, task_type, dict(cand)
                )

            conn.execute(
                """
                UPDATE provisioning_tasks
                SET status = ?, stage_idx = ?, current_stage = ?, blocker_reason = NULL,
                    artifact_value = ?, updated_at = ?
                WHERE id = ?
                """,
                (new_status, next_idx, next_stage, artifact_val, now, task_id),
            )

            log_agent_event(
                conn,
                candidate_id,
                task["agent_name"],
                "TASK_COMPLETED" if is_done else "STAGE_ADVANCED",
                f"{cand['full_name']} -> {next_stage}"
                + (f" ({artifact_val})" if is_done and artifact_val else "")
                + (f" [Note: {notes}]" if notes else ""),
                {"task_id": task_id, "stage_idx": next_idx, "status": new_status},
            )

            # If this task completed, unlock any dependent task (e.g. LAPTOP completed -> unlock EMAIL)
            if is_done:
                dependents = conn.execute(
                    "SELECT * FROM provisioning_tasks WHERE candidate_id = ? AND depends_on = ? AND status = ?",
                    (candidate_id, task_type.value, TaskStatus.PENDING.value),
                ).fetchall()
                for dep_task in dependents:
                    dep_type = TaskType(dep_task["task_type"])
                    dep_stages = SUBAGENT_METADATA[dep_type]["stages"]
                    unlocked_stage = dep_stages[1]
                    conn.execute(
                        """
                        UPDATE provisioning_tasks
                        SET status = ?, stage_idx = 1, current_stage = ?, updated_at = ?
                        WHERE id = ?
                        """,
                        (TaskStatus.IN_PROGRESS.value, unlocked_stage, now, dep_task["id"]),
                    )
                    log_agent_event(
                        conn,
                        candidate_id,
                        dep_task["agent_name"],
                        "TASK_UNLOCKED",
                        f"Dependency satisfied ({task_type.value} cleared) -> Unlocked {dep_task['agent_name']} for {cand['full_name']}. Moved to stage: '{unlocked_stage}'",
                    )

            # Check if all clearance tasks for this exiting employee are now COMPLETED
            remaining = conn.execute(
                "SELECT COUNT(*) as c FROM provisioning_tasks WHERE candidate_id = ? AND status != ?",
                (candidate_id, TaskStatus.COMPLETED.value),
            ).fetchone()["c"]

            all_completed_now = remaining == 0
            if all_completed_now:
                conn.execute(
                    """
                    UPDATE candidates
                    SET offboarding_status = 'OFFBOARDED', onboarding_status = 'ONBOARDED', updated_at = ?
                    WHERE id = ?
                    """,
                    (now, candidate_id),
                )
                # Also mark clearance statement ACCEPTED if not declined so Certificate of Service is unlocked
                conn.execute(
                    """
                    UPDATE offer_letters
                    SET status = 'ACCEPTED',
                        responded_at = COALESCE(responded_at, ?),
                        signature_text = COALESCE(signature_text, ?)
                    WHERE candidate_id = ? AND status != 'DECLINED'
                    """,
                    (now, cand["full_name"], candidate_id),
                )
                log_agent_event(
                    conn,
                    candidate_id,
                    cls.AGENT_NAME,
                    "OFFBOARDING_COMPLETED",
                    (
                        f"All {cand['role_category']} clearance & reverse de-provisioning steps completed for {cand['full_name']}! "
                        f"Certificate of Service issued and Final Settlement (${cand['net_settlement']:,.2f}) released."
                    ),
                )

        if all_completed_now:
            send_or_log_email(
                candidate_id=candidate_id,
                recipient_email=cand["personal_email"],
                recipient_name=cand["full_name"],
                subject=f"Exit Clearance Complete & Certificate of Service Issued — {cand['full_name']}",
                body_text=(
                    f"Dear {cand['full_name']},\n\n"
                    f"Your exit clearance at Acme Enterprise Corp. is 100% complete.\n"
                    f"All department clearances (Benefits, Transport, IT Equipment, and IT Security) have been verified.\n"
                    f"Your Net Final Settlement of ${cand['net_settlement']:,.2f} has been approved for direct deposit, "
                    f"and your official Certificate of Service PDF is now available for download.\n\n"
                    f"Thank you for your contributions and best wishes,\n"
                    f"Acme People Operations"
                ),
                category="OFFBOARDING_COMPLETE_CERTIFICATE",
            )

        return cls.get_candidate_detail(candidate_id)

    @classmethod
    def flag_task_blocker(cls, task_id: int, blocker_reason: str) -> Dict[str, Any]:
        now = utc_now_iso()
        with get_db() as conn:
            task = conn.execute(
                "SELECT * FROM provisioning_tasks WHERE id = ?", (task_id,)
            ).fetchone()
            if not task:
                raise ValueError("Clearance task not found.")
            candidate_id = task["candidate_id"]
            cand = conn.execute(
                "SELECT * FROM candidates WHERE id = ?", (candidate_id,)
            ).fetchone()

            conn.execute(
                """
                UPDATE provisioning_tasks
                SET status = ?, blocker_reason = ?, updated_at = ?
                WHERE id = ?
                """,
                (TaskStatus.BLOCKED.value, blocker_reason, now, task_id),
            )

            log_agent_event(
                conn,
                candidate_id,
                task["agent_name"],
                "TASK_BLOCKED",
                f"BLOCKER on {cand['full_name']} ({task['department']}): {blocker_reason}",
                {"task_id": task_id, "blocker_reason": blocker_reason},
            )

        send_or_log_email(
            candidate_id=candidate_id,
            recipient_email="people-ops@acme.com",
            recipient_name=f"HR Action Center & {task['department']}",
            subject=f"Clearance Blocker Alert: {cand['full_name']} — {task['agent_name']}",
            body_text=(
                f"A department clearance blocker was flagged by {task['agent_name']} ({task['department']}) "
                f"for exiting employee {cand['full_name']} ({cand['job_title']}):\n\n"
                f"Blocker Reason: {blocker_reason}\n\n"
                f"Please resolve in the HR Offboarding Action Center or apply an asset recovery deduction."
            ),
            category="CLEARANCE_BLOCKER_ALERT",
        )
        return cls.get_candidate_detail(candidate_id)

    @classmethod
    def _produce_clearance_artifact(
        cls, conn, candidate_id: int, task_type: TaskType, cand: dict
    ) -> str:
        if task_type == TaskType.INSURANCE:
            pol_id = cand.get("insurance_policy_id") or f"HLTH-ACME-{9100 + candidate_id}"
            artifact = f"Terminated Policy {pol_id} (Card Deactivated)"
            conn.execute(
                "UPDATE candidates SET insurance_policy_id = ? WHERE id = ?",
                (artifact, candidate_id),
            )
            return artifact
        elif task_type == TaskType.UBER:
            pass_id = cand.get("uber_pass_id") or f"UBER-CORP-{7100 + candidate_id}"
            artifact = f"Revoked Pass {pass_id} ($0 Balance)"
            conn.execute(
                "UPDATE candidates SET uber_pass_id = ? WHERE id = ?",
                (artifact, candidate_id),
            )
            return artifact
        elif task_type == TaskType.LAPTOP:
            serial = cand.get("assigned_laptop_serial") or f"MBP16-ACME-{4100 + candidate_id}"
            artifact = f"Returned & Wiped ({serial})"
            conn.execute(
                "UPDATE candidates SET assigned_laptop_serial = ? WHERE id = ?",
                (artifact, candidate_id),
            )
            return artifact
        elif task_type == TaskType.EMAIL:
            email = cand.get("work_email") or _generate_work_email(cand["full_name"], candidate_id)
            artifact = f"Archived & SSO Revoked ({email})"
            return artifact
        return "Cleared"

    @classmethod
    def get_candidate_detail(cls, candidate_id: int) -> Optional[Dict[str, Any]]:
        with get_db() as conn:
            cand = conn.execute(
                "SELECT * FROM candidates WHERE id = ?", (candidate_id,)
            ).fetchone()
            if not cand:
                return None
            offer = conn.execute(
                "SELECT * FROM offer_letters WHERE candidate_id = ?", (candidate_id,)
            ).fetchone()
            tasks = conn.execute(
                "SELECT * FROM provisioning_tasks WHERE candidate_id = ? ORDER BY id ASC",
                (candidate_id,),
            ).fetchall()
            events = conn.execute(
                "SELECT * FROM agent_events WHERE candidate_id = ? ORDER BY id DESC LIMIT 30",
                (candidate_id,),
            ).fetchall()
            emails = conn.execute(
                "SELECT * FROM email_notifications WHERE candidate_id = ? ORDER BY id DESC LIMIT 20",
                (candidate_id,),
            ).fetchall()

            return cls._format_candidate_bundle(
                dict(cand),
                dict(offer) if offer else None,
                [dict(t) for t in tasks],
                [dict(e) for e in events],
                [dict(m) for m in emails],
            )

    @classmethod
    def get_candidate_by_token(cls, signing_token: str) -> Optional[Dict[str, Any]]:
        with get_db() as conn:
            offer = conn.execute(
                "SELECT * FROM offer_letters WHERE signing_token = ?", (signing_token,)
            ).fetchone()
            if not offer:
                return None
            return cls.get_candidate_detail(offer["candidate_id"])

    @classmethod
    def list_all_candidates(cls) -> List[Dict[str, Any]]:
        with get_db() as conn:
            cands = conn.execute(
                "SELECT * FROM candidates ORDER BY id DESC"
            ).fetchall()
            results = []
            for c in cands:
                offer = conn.execute(
                    "SELECT * FROM offer_letters WHERE candidate_id = ?", (c["id"],)
                ).fetchone()
                tasks = conn.execute(
                    "SELECT * FROM provisioning_tasks WHERE candidate_id = ? ORDER BY id ASC",
                    (c["id"],),
                ).fetchall()
                results.append(
                    cls._format_candidate_bundle(
                        dict(c),
                        dict(offer) if offer else None,
                        [dict(t) for t in tasks],
                        [],
                        [],
                    )
                )
            return results

    @classmethod
    def _format_candidate_bundle(
        cls,
        cand: dict,
        offer: Optional[dict],
        tasks: List[dict],
        events: List[dict],
        emails: List[dict],
    ) -> Dict[str, Any]:
        role_cat = RoleCategory(cand["role_category"])
        expected_steps = [t.value for t in ROLE_OFFBOARDING_STEPS[role_cat]]

        enriched_tasks = []
        completed_tasks = 0
        blocked_tasks = 0
        for t in tasks:
            t_type = TaskType(t["task_type"])
            meta = SUBAGENT_METADATA[t_type]
            if t["status"] == TaskStatus.COMPLETED.value:
                completed_tasks += 1
            if t["status"] == TaskStatus.BLOCKED.value:
                blocked_tasks += 1
            pct = round((t["stage_idx"] / max(t["total_stages"] - 1, 1)) * 100)
            enriched_tasks.append(
                {
                    **t,
                    "title": meta["title"],
                    "icon": meta["icon"],
                    "description": meta["description"],
                    "stages": meta["stages"],
                    "progress_pct": pct,
                }
            )

        total_tasks = len(tasks) if tasks else len(expected_steps)
        clearance_pct = (
            round((completed_tasks / total_tasks) * 100) if tasks else 0
        )

        # 4-Milestone Offboarding Journey Progress:
        # 1. Exit Notice Logged
        # 2. Clearance & Handover In Progress
        # 3. Final Dues & Clearance Signed
        # 4. Offboarding Complete & Certificate Issued
        offer_status = offer["status"] if offer else "SENT"
        if cand.get("offboarding_status") == "OFFBOARDED" or (
            tasks and completed_tasks == len(tasks)
        ):
            overall_pct = 100
        elif offer_status == "DECLINED":
            overall_pct = 30
        elif offer_status == "ACCEPTED":
            overall_pct = 55 + round(clearance_pct * 0.45)
        elif tasks:
            overall_pct = 25 + round(clearance_pct * 0.50)
        else:
            overall_pct = 20

        settlement = calculate_final_settlement(
            compensation_amount=cand["compensation_amount"],
            compensation_period=cand.get("compensation_period", "per year"),
            days_worked_final_month=cand.get("days_worked_final_month", 18),
            unused_leave_days=cand.get("unused_leave_days", 6.0),
            asset_deduction=cand.get("asset_deduction", 0.0),
        )

        return {
            **cand,
            "settlement": settlement,
            "offer": offer,
            "clearance": offer,
            "tasks": enriched_tasks,
            "expected_steps": expected_steps,
            "provisioning_pct": clearance_pct,
            "clearance_pct": clearance_pct,
            "overall_progress_pct": overall_pct,
            "has_blocker": blocked_tasks > 0 or offer_status == "DECLINED",
            "events": events,
            "emails": emails,
        }


# Compatibility alias
OnboardingOrchestrator = OffboardingOrchestrator
