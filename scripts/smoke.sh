#!/usr/bin/env bash
set -euo pipefail
BASE="http://localhost:${PORT:-8000}"
echo "health:" && curl -fsS "$BASE/health" && echo
echo "models:" && curl -fsS "$BASE/v1/models" && echo
echo "chat:" && curl -fsS "$BASE/v1/chat/completions" \
  -H 'Content-Type: application/json' \
  -d '{"model":"kai-graph:default","messages":[{"role":"user","content":"ping"}]}'
echo
