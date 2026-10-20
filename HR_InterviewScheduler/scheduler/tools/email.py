"""Email client. The in-memory version records messages in `outbox` for review."""

from __future__ import annotations

import threading
from typing import Any


class InMemoryMailer:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.outbox: list[dict[str, Any]] = []

    def send(self, to: str, subject: str, body: str) -> None:
        with self._lock:
            self.outbox.append({"to": to, "subject": subject, "body": body})


_mailer: Any = InMemoryMailer()


def get_mailer() -> Any:
    return _mailer


def set_mailer(mailer: Any) -> None:
    global _mailer
    _mailer = mailer
