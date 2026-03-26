#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-${ROOT_DIR}/docker-compose.dev.yml}"
ENV_FILE="${ENV_FILE:-${ROOT_DIR}/.env.dev}"
HOST="${CHECK_HOST:-127.0.0.1}"
NEXTJS_PORT="${NEXTJS_PORT:-${DEV_NEXTJS_PORT:-3001}}"
API_PORT="${API_PORT:-${DEV_API_PORT:-8100}}"
SUPERSET_PORT="${SUPERSET_PORT:-${DEV_SUPERSET_PORT:-8088}}"
WAIT_TIMEOUT_SECONDS="${WAIT_TIMEOUT_SECONDS:-180}"

usage() {
  cat <<'EOF'
Usage:
  ./docker/dev/refresh-primary-stack.sh [rebuild|restart] [services...]

Defaults:
  mode: rebuild
  services: assistant-api assistant-web

Examples:
  ./docker/dev/refresh-primary-stack.sh
  ./docker/dev/refresh-primary-stack.sh rebuild assistant-api
  ./docker/dev/refresh-primary-stack.sh restart assistant-api assistant-web
EOF
}

wait_for_http() {
  local label="$1"
  local url="$2"
  shift 2
  local deadline=$((SECONDS + WAIT_TIMEOUT_SECONDS))

  until curl --fail --silent --show-error "$@" "${url}" >/dev/null 2>&1; do
    if (( SECONDS >= deadline )); then
      echo "[refresh-primary-stack] timed out waiting for ${label}: ${url}" >&2
      return 1
    fi
    sleep 2
  done

  echo "[refresh-primary-stack] ${label} ready"
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

MODE="rebuild"
if [[ "${1:-}" == "rebuild" || "${1:-}" == "restart" ]]; then
  MODE="$1"
  shift
fi

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing env file: ${ENV_FILE}" >&2
  echo "Copy /home/superset_ai/.env.dev.example to .env.dev first." >&2
  exit 66
fi

if [[ $# -gt 0 ]]; then
  SERVICES=("$@")
else
  SERVICES=(assistant-api assistant-web)
fi

echo "[refresh-primary-stack] mode=${MODE} services=${SERVICES[*]}"

case "${MODE}" in
  rebuild)
    docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" up -d --build "${SERVICES[@]}"
    ;;
  restart)
    docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" restart "${SERVICES[@]}"
    ;;
  *)
    usage >&2
    exit 64
    ;;
esac

if [[ "${SKIP_WAIT:-0}" != "1" ]]; then
  for service in "${SERVICES[@]}"; do
    case "${service}" in
      assistant-api)
        wait_for_http "assistant-api" "http://${HOST}:${API_PORT}/api/health"
        ;;
      assistant-web)
        wait_for_http "assistant-web" "http://${HOST}:${NEXTJS_PORT}/login" --head
        ;;
      superset)
        wait_for_http "superset" "http://${HOST}:${SUPERSET_PORT}/health" --head
        ;;
    esac
  done
fi

echo "[refresh-primary-stack] next: ${ROOT_DIR}/docker/dev/check-primary-stack.sh"
