#!/usr/bin/env bash
set -euo pipefail

STREAMLIT_PORT="${STREAMLIT_PORT:-8051}"
WS_PORT="${WS_PORT:-8052}"

uvicorn backend.ws_api:app \
  --app-dir /app/superset-ai-assistant-mcp \
  --host 0.0.0.0 \
  --port "${WS_PORT}" &
WS_PID=$!

cleanup() {
  kill "${WS_PID}" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

streamlit run superset-ai-assistant-mcp/frontend/app.py \
  --server.port="${STREAMLIT_PORT}" \
  --server.address=0.0.0.0 \
  --theme.base=light
