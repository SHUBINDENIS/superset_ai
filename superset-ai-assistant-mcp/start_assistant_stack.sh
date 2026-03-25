#!/usr/bin/env bash
set -euo pipefail

STREAMLIT_PORT="${STREAMLIT_PORT:-8051}"

exec streamlit run superset-ai-assistant-mcp/frontend/app.py \
  --server.port="${STREAMLIT_PORT}" \
  --server.address=0.0.0.0 \
  --theme.base=light
