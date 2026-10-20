#!/bin/bash
# Pull the AGY server's candidate project into this laptop folder.
# Server is the source of truth: AGY codes there, this copies the result down.
# Local .venv and .env are never overwritten or uploaded.
set -e

KEY="/c/Users/guruprem.saginadham/Downloads/AGYCLI.pem"
HOST="ubuntu@ec2-3-110-154-63.ap-south-1.compute.amazonaws.com"
REMOTE="candidates_screening"
LOCAL="/c/Work/Candidates Screening"

echo "Pulling ~/$REMOTE from server into $LOCAL ..."
ssh -i "$KEY" -o BatchMode=yes -o ConnectTimeout=20 "$HOST" \
  "cd ~/$REMOTE && tar czf - --exclude=.venv --exclude=.env --exclude=__pycache__ --exclude=.pytest_cache --exclude=*.db --exclude=.adk screening_agent screening_webapp hr_recruitment_doc demo queue.json runner.log tasks" \
  | tar xzf - -C "$LOCAL"

echo "Done. Updated files:"
ls -la "$LOCAL/screening_agent/output" "$LOCAL/hr_recruitment_doc/output" 2>/dev/null
