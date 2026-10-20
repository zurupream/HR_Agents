# Task 004 Results: Run the Agent on Vertex AI, Configured from .env

## Files Added or Changed

### Added
- `scheduler/config.py`: Loads `/home/ubuntu/interview-scheduler/.env` relative to the project root using `python-dotenv` (`override=False`) without overriding existing environment variables, and exposes `MODEL_NAME` (from `SCHEDULER_MODEL`, default `"gemini-3.8-flash"`), `USE_VERTEX` (`GOOGLE_GENAI_USE_VERTEXAI` in `1`/`true`/`yes`, case-insensitive), `PROJECT` (`GOOGLE_CLOUD_PROJECT`), and `BACKEND` (`SCHEDULER_BACKEND`, default `"in-memory"`).
- `scripts/check_vertex.py`: Helper script that loads `scheduler.config` and `scheduler.agent` and prints only whether `.env` is found, `USE_VERTEX`, `project`, `model`, and the `location` used by the model client, without making any model call or printing credentials.
- `tests/test_config.py`: Offline unit tests covering `.env` loading when unset vs. existing environment variable precedence, `USE_VERTEX` parsing (`1`, `true`, `yes`, `0`, missing, etc.), `GlobalVertexGemini` client `location="global"` inspection when `USE_VERTEX=1`, plain model string fallback when `USE_VERTEX=0`, and `configure_from_env()` backend selection.
- `RESULTS-004.md`: This results summary.

### Changed
- `requirements.txt`: Added `python-dotenv`.
- `scheduler/agent.py`: Added `GlobalVertexGemini(Gemini)` (subclassing `google.adk.models.google_llm.Gemini` in `google-adk==2.12.0`) whose `@cached_property def api_client(self) -> Client` returns `Client(vertexai=True, location="global")`. Configured `root_agent` to use `GlobalVertexGemini(model=config.MODEL_NAME)` when `config.USE_VERTEX` is true and `config.MODEL_NAME` otherwise.
- `scheduler/__init__.py`: Imported `scheduler.config` before `scheduler.agent` so `.env` is loaded before `root_agent` is constructed.
- `scheduler/runner.py`: Imported `scheduler.config` first before importing `root_agent` and tools.
- `scheduler/tools/__init__.py`: Updated `configure_from_env()` to load `scheduler.config` first and use `SCHEDULER_BACKEND` (falling back to `config.BACKEND`), selecting `GoogleCalendar` and `GmailMailer` when `"google"` and `InMemoryCalendar` and `InMemoryMailer` otherwise.
- `scripts/authorize_google.py`: Imported `scheduler.config` first so `.env` settings are loaded when running the script directly.
- `README.md`: Added the **Vertex AI** section explaining the `.env` keys (names and meaning only), the Application Default Credentials (ADC) requirement on the server, and the interactive `gcloud auth application-default login --no-launch-browser` command.
- `.gitignore`: Verified `.env` is listed in `.gitignore`.

## Pytest Summary

Command: `.venv/bin/python -m pytest -v`

Pytest summary line:
`======================= 40 passed, 423 warnings in 2.09s =======================`

```text
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.1.1, pluggy-1.6.0 -- /home/ubuntu/interview-scheduler/.venv/bin/python
cachedir: .pytest_cache
rootdir: /home/ubuntu/interview-scheduler
plugins: anyio-4.15.1
collecting ... collected 40 items

tests/test_agent_flow_e2e.py::test_e2e_happy_path PASSED                 [  2%]
tests/test_agent_flow_e2e.py::test_e2e_rules_missing_escalates PASSED    [  5%]
tests/test_agent_flow_e2e.py::test_e2e_slot_taken_before_reply_reoffers PASSED [  7%]
tests/test_config.py::test_dotenv_loads_values_when_env_unset PASSED     [ 10%]
tests/test_config.py::test_existing_env_var_wins_over_dotenv PASSED      [ 12%]
tests/test_config.py::test_use_vertex_parsing[1-True] PASSED             [ 15%]
tests/test_config.py::test_use_vertex_parsing[true-True] PASSED          [ 17%]
tests/test_config.py::test_use_vertex_parsing[TRUE-True] PASSED          [ 20%]
tests/test_config.py::test_use_vertex_parsing[yes-True] PASSED           [ 22%]
tests/test_config.py::test_use_vertex_parsing[YES-True] PASSED           [ 25%]
tests/test_config.py::test_use_vertex_parsing[0-False] PASSED            [ 27%]
tests/test_config.py::test_use_vertex_parsing[false-False] PASSED        [ 30%]
tests/test_config.py::test_use_vertex_parsing[no-False] PASSED           [ 32%]
tests/test_config.py::test_use_vertex_parsing[-False] PASSED             [ 35%]
tests/test_config.py::test_use_vertex_missing_is_false PASSED            [ 37%]
tests/test_config.py::test_agent_with_use_vertex_uses_global_location PASSED [ 40%]
tests/test_config.py::test_agent_without_use_vertex_uses_plain_model_name PASSED [ 42%]
tests/test_google_integration.py::test_google_calendar_create_event_returns_none_on_conflict_and_skips_insert PASSED [ 45%]
tests/test_google_integration.py::test_google_calendar_create_event_inserts_when_free PASSED [ 47%]
tests/test_google_integration.py::test_google_calendar_busy_blocks_returns_only_start_and_end_without_titles PASSED [ 50%]
tests/test_google_integration.py::test_gmail_mailer_send_builds_message_and_calls_users_messages_send PASSED [ 52%]
tests/test_google_integration.py::test_get_credentials_missing_token_raises_clear_error_without_secret PASSED [ 55%]
tests/test_google_integration.py::test_missing_oauth_secret_env_raises_clear_error PASSED [ 57%]
tests/test_google_integration.py::test_save_and_load_token_permissions_and_refresh PASSED [ 60%]
tests/test_google_integration.py::test_authorize_google_manual_flow_saves_mode_600_without_printing_secret PASSED [ 62%]
tests/test_google_integration.py::test_configure_from_env_defaults_to_in_memory_and_selects_google PASSED [ 65%]
tests/test_scheduler.py::test_generate_slots_respects_hours_busy_and_notice PASSED [ 67%]
tests/test_scheduler.py::test_claim_is_exclusive PASSED                  [ 70%]
tests/test_scheduler.py::test_offers_require_claim PASSED                [ 72%]
tests/test_scheduler.py::test_offers_are_numbered_in_candidate_timezone PASSED [ 75%]
tests/test_scheduler.py::test_happy_path_books_logs_and_confirms PASSED  [ 77%]
tests/test_scheduler.py::test_double_booking_is_refused_and_claim_kept PASSED [ 80%]
tests/test_scheduler.py::test_create_event_refuses_conflict_even_if_called_directly PASSED [ 82%]
tests/test_scheduler.py::test_invalid_option_number PASSED               [ 85%]
tests/test_scheduler.py::test_missing_rules_report_rules_invalid PASSED  [ 87%]
tests/test_scheduler.py::test_malformed_rules_are_listed PASSED          [ 90%]
tests/test_scheduler.py::test_onsite_requires_location PASSED            [ 92%]
tests/test_scheduler.py::test_free_busy_exposes_only_windows PASSED      [ 95%]
tests/test_scheduler.py::test_escalation_releases_claim_and_emails_recruiter PASSED [ 97%]
tests/test_scheduler.py::test_reply_after_offer_can_be_reclaimed_and_booked PASSED [100%]

======================= 40 passed, 423 warnings in 2.09s =======================
```

## `scripts/check_vertex.py` Output

Command: `.venv/bin/python scripts/check_vertex.py`

```text
.env found: True
USE_VERTEX: True
project: gemini-enterprise-demo-498212
model: gemini-3.8-flash
location: global
```

## Secret Check Output

Running the secret-check `grep` across the repository (excluding `.venv`) returned exit code 1 with zero matches:

```text
(no matches found)
```

## What Could Not Be Verified
- **Live Vertex AI model calls**: Per task instructions ("Do not make any live model call. Tests must stay offline."), no live network request was made to the Vertex AI endpoint. Making a live Vertex AI call on the server requires Application Default Credentials (ADC) to be configured interactively by a person via `gcloud auth application-default login --no-launch-browser`.
