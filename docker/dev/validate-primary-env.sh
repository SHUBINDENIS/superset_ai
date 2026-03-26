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

is_placeholder() {
  local value="$1"
  shift
  local marker
  for marker in "$@"; do
    if [[ "${value}" == "${marker}" ]]; then
      return 0
    fi
  done
  return 1
}

require_nonempty() {
  local key="$1"
  local value
  value="$(value_for "${key}")"
  if [[ -z "${value}" ]]; then
    echo "[validate-primary-env] missing required ${key}" >&2
    return 1
  fi
  return 0
}

FAIL=0

docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" config >/dev/null

OPENAI_API_KEY_VALUE="$(value_for OPENAI_API_KEY)"
OPENAI_MODEL_VALUE="$(value_for OPENAI_MODEL)"
SUPERSET_PUBLIC_URL_VALUE="$(value_for SUPERSET_PUBLIC_URL)"
AUTH_JWT_SECRET_VALUE="$(value_for AUTH_JWT_SECRET)"
US15_SHARE_BASE_URL_VALUE="$(value_for US15_SHARE_BASE_URL)"
API_CORS_ORIGINS_VALUE="$(value_for API_CORS_ORIGINS)"

if ! require_nonempty OPENAI_API_KEY; then
  FAIL=1
elif is_placeholder "${OPENAI_API_KEY_VALUE}" "replace_me" "your_openai_api_key"; then
  echo "[validate-primary-env] OPENAI_API_KEY still uses a placeholder value" >&2
  FAIL=1
else
  echo "[validate-primary-env] OPENAI_API_KEY set"
fi

if ! require_nonempty OPENAI_MODEL; then
  FAIL=1
else
  echo "[validate-primary-env] OPENAI_MODEL set"
fi

if ! require_nonempty SUPERSET_PUBLIC_URL; then
  FAIL=1
else
  echo "[validate-primary-env] SUPERSET_PUBLIC_URL set"
fi

if [[ -n "${US15_SHARE_BASE_URL_VALUE}" ]]; then
  echo "[validate-primary-env] US15_SHARE_BASE_URL set"
else
  echo "[validate-primary-env] US15_SHARE_BASE_URL not set; runtime will fall back to SUPERSET_PUBLIC_URL"
fi

if [[ -n "${API_CORS_ORIGINS_VALUE}" ]]; then
  echo "[validate-primary-env] API_CORS_ORIGINS set"
else
  echo "[validate-primary-env] API_CORS_ORIGINS not set; local default will be used"
fi

if [[ -z "${AUTH_JWT_SECRET_VALUE}" ]]; then
  echo "[validate-primary-env] AUTH_JWT_SECRET missing" >&2
  FAIL=1
elif is_placeholder "${AUTH_JWT_SECRET_VALUE}" "dev-only-secret-change-me" "change_me_please"; then
  echo "[validate-primary-env] AUTH_JWT_SECRET still uses a weak default placeholder" >&2
else
  echo "[validate-primary-env] AUTH_JWT_SECRET set"
fi

echo "[validate-primary-env] ASSISTANT_RELEASE_VERSION=${ASSISTANT_RELEASE_VERSION:-<auto>}"
echo "[validate-primary-env] ASSISTANT_BUILD_SHA=${ASSISTANT_BUILD_SHA:-<auto>}"
echo "[validate-primary-env] ASSISTANT_BUILD_TIMESTAMP=${ASSISTANT_BUILD_TIMESTAMP:-<auto>}"

if (( FAIL != 0 )); then
  exit 64
fi
