#!/usr/bin/env bash
set -euo pipefail

API_PORT="${API_PORT:-8100}"

cd /app/superset-ai-assistant-mcp

python - <<'PY'
from api.runtime_config import validate_runtime_config

report = validate_runtime_config()
print(f"[start_fastapi_stack] deployment_mode={report['mode']}")
for warning in report["warnings"]:
    print(f"[start_fastapi_stack] warning: {warning}")
PY

exec python -m uvicorn api.main:app \
  --host=0.0.0.0 \
  --port="${API_PORT}"
