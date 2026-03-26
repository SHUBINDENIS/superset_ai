#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${ENV_FILE:-${ROOT_DIR}/.env.dev}"
COMPOSE_FILE="${COMPOSE_FILE:-${ROOT_DIR}/docker-compose.dev.yml}"

usage() {
  cat <<'EOF'
Usage:
  ./docker/dev/validate-primary-env.sh

Validates the effective deploy environment for the single supported stack.
Reads values from the current shell first, then from .env.dev.
Uses ASSISTANT_DEPLOYMENT_MODE=development|production to decide whether
unsafe values are warnings or hard failures.
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "[validate-primary-env] missing env file: ${ENV_FILE}" >&2
  exit 66
fi

value_for() {
  local key="$1"
  if [[ -n "${!key:-}" ]]; then
    printf '%s' "${!key}"
    return 0
  fi

  local line
  line="$(grep -E "^${key}=" "${ENV_FILE}" | tail -n 1 || true)"
  if [[ -n "${line}" ]]; then
    printf '%s' "${line#*=}"
  fi
}

docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" config >/dev/null

ASSISTANT_DEPLOYMENT_MODE_VALUE="$(value_for ASSISTANT_DEPLOYMENT_MODE)"
OPENAI_API_KEY_VALUE="$(value_for OPENAI_API_KEY)"
OPENAI_MODEL_VALUE="$(value_for OPENAI_MODEL)"
SUPERSET_PUBLIC_URL_VALUE="$(value_for SUPERSET_PUBLIC_URL)"
AUTH_JWT_SECRET_VALUE="$(value_for AUTH_JWT_SECRET)"
US15_SHARE_BASE_URL_VALUE="$(value_for US15_SHARE_BASE_URL)"
API_CORS_ORIGINS_VALUE="$(value_for API_CORS_ORIGINS)"
ASSISTANT_RELEASE_VERSION_VALUE="${ASSISTANT_RELEASE_VERSION:-$(value_for ASSISTANT_RELEASE_VERSION)}"
ASSISTANT_BUILD_SHA_VALUE="${ASSISTANT_BUILD_SHA:-$(value_for ASSISTANT_BUILD_SHA)}"
ASSISTANT_BUILD_TIMESTAMP_VALUE="${ASSISTANT_BUILD_TIMESTAMP:-$(value_for ASSISTANT_BUILD_TIMESTAMP)}"

ASSISTANT_DEPLOYMENT_MODE="${ASSISTANT_DEPLOYMENT_MODE_VALUE}" \
OPENAI_API_KEY="${OPENAI_API_KEY_VALUE}" \
OPENAI_MODEL="${OPENAI_MODEL_VALUE}" \
SUPERSET_PUBLIC_URL="${SUPERSET_PUBLIC_URL_VALUE}" \
AUTH_JWT_SECRET="${AUTH_JWT_SECRET_VALUE}" \
US15_SHARE_BASE_URL="${US15_SHARE_BASE_URL_VALUE}" \
API_CORS_ORIGINS="${API_CORS_ORIGINS_VALUE}" \
ASSISTANT_RELEASE_VERSION="${ASSISTANT_RELEASE_VERSION_VALUE}" \
ASSISTANT_BUILD_SHA="${ASSISTANT_BUILD_SHA_VALUE}" \
ASSISTANT_BUILD_TIMESTAMP="${ASSISTANT_BUILD_TIMESTAMP_VALUE}" \
PYTHONPATH="${ROOT_DIR}/superset-ai-assistant-mcp" \
python3 - <<'PY'
from api.runtime_config import RuntimeConfigError, validate_runtime_config
import os
import sys

try:
    report = validate_runtime_config()
except RuntimeConfigError as exc:
    print(f"[validate-primary-env] {exc}", file=sys.stderr)
    raise SystemExit(64)

for line in report["checks"]:
    print(f"[validate-primary-env] {line}")
for warning in report["warnings"]:
    print(f"[validate-primary-env] warning: {warning}")

print(
    "[validate-primary-env] "
    f"ASSISTANT_RELEASE_VERSION={os.getenv('ASSISTANT_RELEASE_VERSION', '<auto>') or '<auto>'}"
)
print(
    "[validate-primary-env] "
    f"ASSISTANT_BUILD_SHA={os.getenv('ASSISTANT_BUILD_SHA', '<auto>') or '<auto>'}"
)
print(
    "[validate-primary-env] "
    f"ASSISTANT_BUILD_TIMESTAMP={os.getenv('ASSISTANT_BUILD_TIMESTAMP', '<auto>') or '<auto>'}"
)
PY
