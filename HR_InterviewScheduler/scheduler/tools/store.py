"""Tracking store: candidates, job rules, offered slots and the Interviews log.

The in-memory implementation is for development and tests. A production
deployment should implement the same methods against the real sheet/DB, using
a conditional update (compare-and-set on `status`) inside `claim_candidate`.
"""

from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone
from typing import Any

PENDING_ACTION = "schedule_interview"
# A candidate can be claimed when new (pending) or when they reply to offered slots (awaiting_reply).
CLAIMABLE_STATUSES = {"pending", "awaiting_reply"}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class InMemoryStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.candidates: dict[str, dict[str, Any]] = {}
        self.job_rules: dict[str, dict[str, Any]] = {}
        self.interviews: list[dict[str, Any]] = []

    # --- seeding helpers (used by tests and the local demo) ---
    def add_candidate(self, candidate: dict[str, Any]) -> None:
        with self._lock:
            row = {
                "status": "pending",
                "next_action": PENDING_ACTION,
                "claimed_by": None,
                "claimed_at": None,
                "offered_slots": [],
                "offered_at": None,
                **candidate,
            }
            self.candidates[row["candidate_id"]] = row

    def add_job_rules(self, rules: dict[str, Any]) -> None:
        with self._lock:
            self.job_rules[rules["job_id"]] = rules

    # --- agent-facing operations ---
    def get_pending_candidates(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                dict(c)
                for c in self.candidates.values()
                if c.get("next_action") == PENDING_ACTION and c["status"] in CLAIMABLE_STATUSES
            ]

    def claim_candidate(self, candidate_id: str, agent_id: str) -> bool:
        """Atomically move a candidate from pending to claimed. Returns False if taken."""
        with self._lock:
            row = self.candidates.get(candidate_id)
            if row is None or row["status"] not in CLAIMABLE_STATUSES:
                return False
            row["status"] = "claimed"
            row["claimed_by"] = agent_id
            row["claimed_at"] = utcnow().isoformat()
            return True

    def release_candidate(self, candidate_id: str, status: str) -> None:
        """Release the claim and set the next status (e.g. 'awaiting_reply', 'escalated', 'scheduled')."""
        with self._lock:
            row = self.candidates[candidate_id]
            row["status"] = status
            row["claimed_by"] = None
            row["claimed_at"] = None
            if status != "pending":
                row["next_action"] = None

    def get_candidate(self, candidate_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self.candidates.get(candidate_id)
            return dict(row) if row else None

    def get_job_rules(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            rules = self.job_rules.get(job_id)
            return dict(rules) if rules else None

    def save_offered_slots(self, candidate_id: str, slots: list[dict[str, Any]]) -> None:
        with self._lock:
            row = self.candidates[candidate_id]
            row["offered_slots"] = slots
            row["offered_at"] = utcnow().isoformat()

    def list_awaiting_reply(self, older_than_hours: float) -> list[dict[str, Any]]:
        cutoff = utcnow() - timedelta(hours=older_than_hours)
        with self._lock:
            out = []
            for c in self.candidates.values():
                if c["status"] != "awaiting_reply" or not c.get("offered_at"):
                    continue
                if datetime.fromisoformat(c["offered_at"]) <= cutoff:
                    out.append(dict(c))
            return out

    def log_interview_record(self, record: dict[str, Any]) -> None:
        with self._lock:
            self.interviews.append(dict(record))


# Module-level store used by the ADK tool functions. Swap with `set_store()`.
_store: Any = InMemoryStore()


def get_store() -> Any:
    return _store


def set_store(store: Any) -> None:
    global _store
    _store = store
