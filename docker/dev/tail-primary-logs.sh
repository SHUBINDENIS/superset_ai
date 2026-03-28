#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-${ROOT_DIR}/docker-compose.dev.yml}"
ENV_FILE="${ENV_FILE:-${ROOT_DIR}/.env.dev}"

usage() {
  cat <<'EOF'
Usage:
  ./docker/dev/tail-primary-logs.sh [compose|structured] [services...]

Modes:
  compose     Tail docker compose logs. Default services:
              assistant-api assistant-web superset
  structured  Tail assistant structured file logs inside assistant-api:
              frontend.log agent.log mcp.log artifact.log

Examples:
  ./docker/dev/tail-primary-logs.sh
  ./docker/dev/tail-primary-logs.sh compose assistant-api
  ./docker/dev/tail-primary-logs.sh structured
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

MODE="compose"
if [[ "${1:-}" == "compose" || "${1:-}" == "structured" ]]; then
  MODE="$1"
  shift
fi

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing env file: ${ENV_FILE}" >&2
  echo "Copy /home/superset_ai/.env.dev.example to .env.dev first." >&2
  exit 66
fi

case "${MODE}" in
  compose)
    if [[ $# -gt 0 ]]; then
      SERVICES=("$@")
    else
      SERVICES=(assistant-api assistant-web superset)
    fi
    exec docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" logs -f "${SERVICES[@]}"
    ;;
  structured)
    exec docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" exec -T assistant-api sh -lc \
      'mkdir -p /app/superset-ai-assistant-mcp/data/logs && tail -F \
        /app/superset-ai-assistant-mcp/data/logs/frontend.log \
        /app/superset-ai-assistant-mcp/data/logs/agent.log \
        /app/superset-ai-assistant-mcp/data/logs/mcp.log \
        /app/superset-ai-assistant-mcp/data/logs/artifact.log'
    ;;
  *)
    usage >&2
    exit 64
    ;;
esac
