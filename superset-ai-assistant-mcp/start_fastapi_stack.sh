#!/usr/bin/env bash
set -euo pipefail

API_PORT="${API_PORT:-8100}"

cd /app/superset-ai-assistant-mcp

exec python -m uvicorn api.main:app \
  --host=0.0.0.0 \
  --port="${API_PORT}"
