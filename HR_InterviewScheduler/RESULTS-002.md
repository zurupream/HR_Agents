# Task 002 Results: Real Google Calendar and Gmail Integration

## Files Added or Changed

### Added
- `scheduler/google_clients.py`: Implemented `get_credentials()`, `build_calendar_service()`, `build_gmail_service()`, `save_token()`, `get_client_id()`, and `get_oauth_secret()` using OAuth client ID `259388273008-n8vg3ae8be86e56svvg09rbdciah17u1.apps.googleusercontent.com` (overridable via `GOOGLE_OAUTH_CLIENT_ID`), runtime `GOOGLE_OAUTH_CLIENT_SECRET` from environment variables only, and scopes `calendar.events` and `gmail.send`.
- `scheduler/tools/google_calendar.py`: Implemented `GoogleCalendar` with `busy_blocks(emails, start, end)` (calling `freebusy().query` and returning only `(start, end)` `datetime` tuples with no event titles) and `create_event(attendees, start, end, **details)` (re-checking free/busy first and returning `None` on conflict, then inserting the event with Google Meet `conferenceData`, `conferenceDataVersion=1`, `sendUpdates="all"`, and `attendees`).
- `scheduler/tools/gmail.py`: Implemented `GmailMailer` with `send(to, subject, body)` building an RFC 2822 `EmailMessage`, base64url-encoding it, and calling `users().messages().send(userId="me", body={"raw": ...})`.
- `scripts/authorize_google.py`: Implemented the one-time OAuth consent script using `InstalledAppFlow` with redirect URI `http://localhost:8765/`, manual URL/code terminal fallback, and saving `secrets/google_token.json` with mode `600` inside `secrets/` (mode `700`) without printing the secret or token.
- `tests/test_google_integration.py`: Added 9 mocked unit tests (`unittest.mock`, no network calls) covering `GoogleCalendar.create_event` conflict & success paths, `GoogleCalendar.busy_blocks` privacy guarantee, `GmailMailer.send`, `get_credentials` missing token and refresh flows, `authorize_google.py`, and `configure_from_env()`.
- `RESULTS-002.md`: Recorded task deliverables, test execution summary, secret check output, and unverified items.

### Changed
- `scheduler/tools/__init__.py`: Added `configure_from_env()` to select `GoogleCalendar` and `GmailMailer` when `SCHEDULER_BACKEND=google` and default to `InMemoryCalendar` and `InMemoryMailer` otherwise.
- `scheduler/tools/scheduling_tools.py`: Re-exported `set_mailer` alongside `get_mailer` and `configure_from_env`.
- `requirements.txt`: Added `google-api-python-client`, `google-auth`, `google-auth-oauthlib`, and `google-auth-httplib2`.
- `.gitignore`: Added `secrets/`.
- `README.md`: Added the **Google setup** section documenting `(a)` setting `GOOGLE_OAUTH_CLIENT_SECRET` in the shell, `(b)` running `python scripts/authorize_google.py`, and `(c)` setting `SCHEDULER_BACKEND=google`, noting when the token file and secret are needed.

## Pytest Summary

Command executed:
```bash
.venv/bin/python -m pytest -v
```

Full pytest output:
```text
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.1.1, pluggy-1.6.0 -- /home/ubuntu/interview-scheduler/.venv/bin/python
cachedir: .pytest_cache
rootdir: /home/ubuntu/interview-scheduler
plugins: anyio-4.15.1
collecting ... collected 23 items

tests/test_google_integration.py::test_google_calendar_create_event_returns_none_on_conflict_and_skips_insert PASSED [  4%]
tests/test_google_integration.py::test_google_calendar_create_event_inserts_when_free PASSED [  8%]
tests/test_google_integration.py::test_google_calendar_busy_blocks_returns_only_start_and_end_without_titles PASSED [ 13%]
tests/test_google_integration.py::test_gmail_mailer_send_builds_message_and_calls_users_messages_send PASSED [ 17%]
tests/test_google_integration.py::test_get_credentials_missing_token_raises_clear_error_without_secret PASSED [ 21%]
tests/test_google_integration.py::test_missing_oauth_secret_env_raises_clear_error PASSED [ 26%]
tests/test_google_integration.py::test_save_and_load_token_permissions_and_refresh PASSED [ 30%]
tests/test_google_integration.py::test_authorize_google_manual_flow_saves_mode_600_without_printing_secret PASSED [ 34%]
tests/test_google_integration.py::test_configure_from_env_defaults_to_in_memory_and_selects_google PASSED [ 39%]
tests/test_scheduler.py::test_generate_slots_respects_hours_busy_and_notice PASSED [ 43%]
tests/test_scheduler.py::test_claim_is_exclusive PASSED                  [ 47%]
tests/test_scheduler.py::test_offers_require_claim PASSED                [ 52%]
tests/test_scheduler.py::test_offers_are_numbered_in_candidate_timezone PASSED [ 56%]
tests/test_scheduler.py::test_happy_path_books_logs_and_confirms PASSED  [ 60%]
tests/test_scheduler.py::test_double_booking_is_refused_and_claim_kept PASSED [ 65%]
tests/test_scheduler.py::test_create_event_refuses_conflict_even_if_called_directly PASSED [ 69%]
tests/test_scheduler.py::test_invalid_option_number PASSED               [ 73%]
tests/test_scheduler.py::test_missing_rules_report_rules_invalid PASSED  [ 78%]
tests/test_scheduler.py::test_malformed_rules_are_listed PASSED          [ 82%]
tests/test_scheduler.py::test_onsite_requires_location PASSED            [ 86%]
tests/test_scheduler.py::test_free_busy_exposes_only_windows PASSED      [ 91%]
tests/test_scheduler.py::test_escalation_releases_claim_and_emails_recruiter PASSED [ 95%]
tests/test_scheduler.py::test_reply_after_offer_can_be_reclaimed_and_booked PASSED [100%]

============================== 23 passed in 1.10s ==============================
```

Pytest summary line:
`============================== 23 passed in 1.10s ==============================`

## Secret Check Grep Result

Output of the secret check grep across the repository (excluding `.venv`):
```text
./scheduler/google_clients.py:86:    info["client_secret"] = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")
./scripts/authorize_google.py:48:            "client_secret": os.environ["GOOGLE_OAUTH_CLIENT_SECRET"],
```

All hits are exclusively runtime reads of `os.environ` for `GOOGLE_OAUTH_CLIENT_SECRET`. No secret values exist in any file.

## What Could Not Be Verified
- **Live Google OAuth browser consent and live Google Calendar / Gmail API calls**: Per task rules ("Do not send real email, create real calendar events, or call live Google APIs during this task. Tests must use mocks"), interactive OAuth login against a real Google account and live network calls to Google Calendar (`freebusy.query`, `events.insert`) and Gmail (`users.messages.send`) were not executed against live Google servers and were verified via `unittest.mock` instead.
