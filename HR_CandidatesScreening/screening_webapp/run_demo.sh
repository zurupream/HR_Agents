#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

export DEMO_TEST_AUTH="${DEMO_TEST_AUTH:-1}"
export DATABASE_URL="${DATABASE_URL:-sqlite:///${SCRIPT_DIR}/data/app.db}"

exec "${PROJECT_ROOT}/screening_agent/.venv/bin/python" -m screening_webapp

