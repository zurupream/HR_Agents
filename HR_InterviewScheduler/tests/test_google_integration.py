from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from email import message_from_bytes
import stat
from unittest.mock import MagicMock, patch

import pytest

from scheduler.google_clients import get_credentials, get_oauth_secret, save_token
from scheduler.tools import configure_from_env
from scheduler.tools.calendar import InMemoryCalendar
from scheduler.tools.email import InMemoryMailer, get_mailer
from scheduler.tools.gmail import GmailMailer
from scheduler.tools.google_calendar import GoogleCalendar
from scheduler.tools import scheduling_tools as t


def test_google_calendar_create_event_returns_none_on_conflict_and_skips_insert():
    service = MagicMock()
    start = datetime(2026, 10, 15, 14, 0, tzinfo=timezone.utc)
    end = start + timedelta(minutes=45)

    service.freebusy().query().execute.return_value = {
        "calendars": {
            "alice@company.example": {
                "busy": [
                    {
                        "start": "2026-10-15T14:15:00Z",
                        "end": "2026-10-15T15:00:00Z",
                    }
                ]
            },
            "sam@example.com": {"busy": []},
        }
    }

    calendar = GoogleCalendar(service=service)
    result = calendar.create_event(
        attendees=["alice@company.example", "sam@example.com"],
        start=start,
        end=end,
        title="Technical Interview",
    )

    assert result is None
    service.events().insert.assert_not_called()


def test_google_calendar_create_event_inserts_when_free():
    service = MagicMock()
    start = datetime(2026, 10, 15, 14, 0, tzinfo=timezone.utc)
    end = start + timedelta(minutes=45)

    service.freebusy().query().execute.return_value = {
        "calendars": {
            "alice@company.example": {"busy": []},
            "sam@example.com": {"busy": []},
        }
    }
    service.events().insert().execute.return_value = {
        "id": "gcal-evt-42",
        "hangoutLink": "https://meet.google.com/xyz-abcd-efg",
    }
    service.events().insert.reset_mock()

    calendar = GoogleCalendar(service=service)
    result = calendar.create_event(
        attendees=["alice@company.example", "sam@example.com"],
        start=start,
        end=end,
        title="Technical Interview",
        description="Bring laptop",
    )

    assert result == {
        "event_id": "gcal-evt-42",
        "meet_link": "https://meet.google.com/xyz-abcd-efg",
        "attendees": ["alice@company.example", "sam@example.com"],
        "start": start,
        "end": end,
    }
    service.events().insert.assert_called_once()
    kwargs = service.events().insert.call_args.kwargs
    assert kwargs["calendarId"] == "primary"
    assert kwargs["conferenceDataVersion"] == 1
    assert kwargs["sendUpdates"] == "all"
    assert "conferenceData" in kwargs["body"]
    assert kwargs["body"]["attendees"] == [
        {"email": "alice@company.example"},
        {"email": "sam@example.com"},
    ]


def test_google_calendar_busy_blocks_returns_only_start_and_end_without_titles():
    service = MagicMock()
    window_start = datetime(2026, 10, 15, 0, 0, tzinfo=timezone.utc)
    window_end = datetime(2026, 10, 16, 0, 0, tzinfo=timezone.utc)
    busy_start = datetime(2026, 10, 15, 14, 0, tzinfo=timezone.utc)
    busy_end = datetime(2026, 10, 15, 15, 0, tzinfo=timezone.utc)

    service.freebusy().query().execute.return_value = {
        "calendars": {
            "alice@company.example": {
                "busy": [
                    {
                        "start": "2026-10-15T14:00:00Z",
                        "end": "2026-10-15T15:00:00Z",
                        "title": "Confidential Executive Sync",
                        "summary": "Confidential Executive Sync",
                    }
                ]
            }
        }
    }

    calendar = GoogleCalendar(service=service)
    blocks = calendar.busy_blocks(["alice@company.example"], window_start, window_end)

    assert blocks == {"alice@company.example": [(busy_start, busy_end)]}
    assert "Confidential" not in str(blocks)

    t.set_calendar(calendar)
    try:
        tool_out = t.get_panel_free_busy(
            ["alice@company.example"],
            window_start.isoformat(),
            window_end.isoformat(),
        )
        assert tool_out == {
            "status": "ok",
            "busy": {
                "alice@company.example": [
                    {"start": busy_start.isoformat(), "end": busy_end.isoformat()}
                ]
            },
        }
        assert "Confidential" not in str(tool_out)
    finally:
        t.set_calendar(InMemoryCalendar())


def test_gmail_mailer_send_builds_message_and_calls_users_messages_send():
    service = MagicMock()
    service.users().messages().send().execute.return_value = {"id": "msg-1"}
    service.users().messages().send.reset_mock()

    mailer = GmailMailer(service=service)
    mailer.send(
        to="sam@example.com",
        subject="Interview time options",
        body="Option 1: Thursday @ 10:00 AM",
    )

    service.users().messages().send.assert_called_once()
    call_kwargs = service.users().messages().send.call_args.kwargs
    assert call_kwargs["userId"] == "me"
    raw_b64 = call_kwargs["body"]["raw"]
    raw_bytes = base64.urlsafe_b64decode(raw_b64.encode("ascii"))
    parsed = message_from_bytes(raw_bytes)

    assert parsed["To"] == "sam@example.com"
    assert parsed["Subject"] == "Interview time options"
    assert "Option 1: Thursday @ 10:00 AM" in parsed.get_payload(decode=True).decode("utf-8")


def test_get_credentials_missing_token_raises_clear_error_without_secret(
    tmp_path, monkeypatch
):
    dummy_secret = " runtime-secret-do-not-leak-8472 "
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", dummy_secret)
    missing_file = tmp_path / "secrets" / "google_token.json"

    with pytest.raises(FileNotFoundError) as exc_info:
        get_credentials(token_path=missing_file)

    error_text = str(exc_info.value)
    assert "scripts/authorize_google.py" in error_text
    assert dummy_secret.strip() not in error_text


def test_missing_oauth_secret_env_raises_clear_error(monkeypatch):
    monkeypatch.delenv("GOOGLE_OAUTH_CLIENT_SECRET", raising=False)
    with pytest.raises(RuntimeError) as exc_info:
        get_oauth_secret()
    assert "GOOGLE_OAUTH_CLIENT_SECRET" in str(exc_info.value)


def test_save_and_load_token_permissions_and_refresh(tmp_path, monkeypatch):
    secret_val = " test-only-oauth-val-12345 "
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", secret_val)
    token_file = tmp_path / "secrets" / "google_token.json"

    mock_creds = MagicMock()
    mock_creds.token = "access-token-1"
    mock_creds.refresh_token = "refresh-token-1"
    mock_creds.token_uri = "https://oauth2.googleapis.com/token"
    mock_creds.client_id = "test-client-id"
    mock_creds.scopes = [
        "https://www.googleapis.com/auth/calendar.events",
        "https://www.googleapis.com/auth/gmail.send",
    ]
    mock_creds.expiry = datetime(2020, 1, 1, 0, 0)

    save_token(mock_creds, token_path=token_file)
    assert token_file.is_file()
    assert stat.S_IMODE(token_file.stat().st_mode) == 0o600
    assert stat.S_IMODE(token_file.parent.stat().st_mode) == 0o700
    assert secret_val.strip() not in token_file.read_text(encoding="utf-8")

    with patch("google.oauth2.credentials.Credentials.refresh") as mock_refresh:
        loaded = get_credentials(token_path=token_file)
        mock_refresh.assert_called_once()
        assert loaded.refresh_token == "refresh-token-1"


def test_authorize_google_manual_flow_saves_mode_600_without_printing_secret(
    tmp_path, monkeypatch, capsys
):
    from scripts import authorize_google

    secret_val = "consent-secret-never-print-777"
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", secret_val)
    token_file = tmp_path / "secrets" / "google_token.json"

    mock_flow = MagicMock()
    mock_flow.authorization_url.return_value = (
        "https://accounts.google.com/o/oauth2/auth?client_id=test",
        "state-1",
    )
    mock_flow.credentials.token = "tok-xyz-secret"
    mock_flow.credentials.refresh_token = "ref-xyz-secret"
    mock_flow.credentials.token_uri = "https://oauth2.googleapis.com/token"
    mock_flow.credentials.client_id = "test-client-id"
    mock_flow.credentials.scopes = [
        "https://www.googleapis.com/auth/calendar.events",
        "https://www.googleapis.com/auth/gmail.send",
    ]
    mock_flow.credentials.expiry = None

    with (
        patch.object(
            authorize_google.InstalledAppFlow,
            "from_client_config",
            return_value=mock_flow,
        ) as mock_from_cfg,
        patch(
            "builtins.input",
            return_value="http://localhost:8765/?code=auth-code-987&scope=all",
        ),
    ):
        saved = authorize_google.authorize(token_path=token_file)

    assert saved == token_file
    assert stat.S_IMODE(token_file.stat().st_mode) == 0o600
    assert stat.S_IMODE(token_file.parent.stat().st_mode) == 0o700
    mock_from_cfg.assert_called_once()
    mock_flow.fetch_token.assert_called_once_with(code="auth-code-987")

    captured = capsys.readouterr()
    assert "https://accounts.google.com/o/oauth2/auth" in captured.out
    assert secret_val not in captured.out
    assert "tok-xyz-secret" not in captured.out
    assert "ref-xyz-secret" not in captured.out


def test_configure_from_env_defaults_to_in_memory_and_selects_google(monkeypatch):
    monkeypatch.delenv("SCHEDULER_BACKEND", raising=False)
    cal_backend, mail_backend = configure_from_env()
    assert isinstance(cal_backend, InMemoryCalendar)
    assert isinstance(mail_backend, InMemoryMailer)
    assert isinstance(t.get_calendar(), InMemoryCalendar)
    assert isinstance(get_mailer(), InMemoryMailer)

    monkeypatch.setenv("SCHEDULER_BACKEND", "google")
    cal_backend, mail_backend = configure_from_env()
    assert isinstance(cal_backend, GoogleCalendar)
    assert isinstance(mail_backend, GmailMailer)
    assert isinstance(t.get_calendar(), GoogleCalendar)
    assert isinstance(get_mailer(), GmailMailer)

    monkeypatch.delenv("SCHEDULER_BACKEND", raising=False)
    configure_from_env()

