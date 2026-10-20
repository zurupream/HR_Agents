# Task 005 Results: ADK Web UI with Merchandiser Sample Data (Localhost Only)

## Files Added or Changed

### Added
- `scheduler/sample_data.py`: Implemented `seed_merchandiser()` which loads the `MERCH-2026-01` (`Merchandiser`) job rules and the three pending candidates (`MC-001` Amara Okafor in `Africa/Nairobi`, `MC-002` Liam Brennan in `Europe/London`, and `MC-003` Priya Nair with no timezone defaulting to `Africa/Nairobi`) into the module-level store returned by `get_store()`, and sets `InMemoryCalendar` and `InMemoryMailer`.
- `tests/test_sample_data.py`: Offline unit tests verifying `seed_merchandiser()` populates the job and three pending candidates (and `get_pending_candidates()` returns all three) and that importing/reloading `scheduler` with `SCHEDULER_SEED=merchandiser` seeds the store.
- `RESULTS-005.md`: This results summary.

### Changed
- `scheduler/__init__.py`: Calls `seed_merchandiser()` on import when `os.environ.get("SCHEDULER_SEED") == "merchandiser"`, while leaving existing behavior and `from . import agent` unchanged when unset.

## Pytest Summary

Command: `.venv/bin/python -m pytest -q`

Pytest summary line:
`42 passed, 423 warnings in 3.27s`

Full verbose summary line (`.venv/bin/python -m pytest -v`):
`======================= 42 passed, 423 warnings in 4.49s =======================`

## ADK Web Command Running

Command used to launch the server in `/home/ubuntu/interview-scheduler`:
```bash
cd ~/interview-scheduler && set -a && . ./.env && set +a && SCHEDULER_SEED=merchandiser setsid nohup .venv/bin/adk web --host 127.0.0.1 --port 8000 ~/interview-scheduler > ~/agy-queue/logs/adk-web.log 2>&1 < /dev/null &
```

Running process (`ps aux | grep "adk web"`):
```text
ubuntu     15442  0.5  2.8 205140 112720 ?       Ss   17:09   0:02 /home/ubuntu/interview-scheduler/.venv/bin/python3 .venv/bin/adk web --host 127.0.0.1 --port 8000 /home/ubuntu/interview-scheduler
```

## HTTP Check Results

- Root UI endpoint (`curl -sL -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/` and `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/dev-ui/`):
  ```text
  200
  ```
  *(Note: `GET http://127.0.0.1:8000/` returns `307 Temporary Redirect` to `/dev-ui/`, which returns `200 OK`.)*

- Listed ADK apps (`curl -s http://127.0.0.1:8000/list-apps`):
  ```json
  ["scheduler"]
  ```

## Socket Listener Check (`ss -ltn | grep 8000`)

Command: `ss -ltn | grep 8000`
```text
LISTEN 0      2048       127.0.0.1:8000       0.0.0.0:*
```
The server is bound exclusively to `127.0.0.1:8000` and is **not** listening on `0.0.0.0:8000`.

## SSH Tunnel Instructions

Run this command on your laptop to forward local port `8000` to `127.0.0.1:8000` on the server:
```bash
ssh -i <path-to-AGYCLI.pem> -L 8000:127.0.0.1:8000 ubuntu@<host>
```
Then open `http://localhost:8000` in your laptop browser and select the `scheduler` app.
