#!/usr/bin/env bash
set -euo pipefail
export PYTHONUNBUFFERED=1
[ -f .env ] && set -a && . ./.env && set +a
WORKERS="${WORKERS:-2}"
python -m uvicorn server:app --host 0.0.0.0 --port "${PORT:-8000}" --workers "$WORKERS"
