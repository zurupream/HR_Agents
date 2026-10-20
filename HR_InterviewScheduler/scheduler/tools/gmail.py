"""Gmail API mailer backend implementing the same send(to, subject, body) interface as InMemoryMailer."""

from __future__ import annotations

import base64
from email.message import EmailMessage
from typing import Any

from scheduler.google_clients import build_gmail_service


class GmailMailer:
    """Gmail API client for sending plain-text emails."""

    def __init__(self, service: Any = None) -> None:
        self._service = service

    @property
    def service(self) -> Any:
        return self._get_service()

    @service.setter
    def service(self, value: Any) -> None:
        self._service = value

    def _get_service(self) -> Any:
        if self._service is None:
            self._service = build_gmail_service()
        return self._service

    def send(self, to: str, subject: str, body: str) -> dict[str, Any]:
        """Build an RFC 2822 message, base64url-encode it, and send via Gmail API."""
        msg = EmailMessage()
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")
        return (
            self._get_service()
            .users()
            .messages()
            .send(userId="me", body={"raw": raw})
            .execute()
        )
