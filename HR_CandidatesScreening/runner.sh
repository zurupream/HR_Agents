#!/bin/bash
# Works through ~/candidates_screening/queue.json in priority order, 24/7.
export PATH=$HOME/.local/bin:$PATH
cd ~/candidates_screening || exit 1
while true; do
  if python3 -c "import json,sys; q=json.load(open('queue.json')); sys.exit(0 if any(t['status']=='todo' for t in q['tasks']) else 1)"; then
    echo "[$(date -u +%FT%TZ)] starting agy pass" >> runner.log
    timeout 3600 agy --model gemini-4-argon-high --effort high --dangerously-skip-permissions --print-timeout 55m -p="You are the coder for the Candidate Screening project. Work only inside ~/candidates_screening. Do not read or modify any other folder on this server. Read queue.json. Take the lowest-priority task with status todo, read its tasks/ file, do it fully, then set its status to done (or blocked with a reason in queue.json). Repeat until no todo tasks remain or you are blocked. Never write secrets, keys or client secrets into any file. Print a one-line summary per task." >> runner.log 2>&1
    echo "[$(date -u +%FT%TZ)] agy pass finished" >> runner.log
  else
    echo "[$(date -u +%FT%TZ)] queue empty, idle" >> runner.log
  fi
  sleep 300
done
