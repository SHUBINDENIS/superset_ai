#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
HOST="${CHECK_HOST:-127.0.0.1}"
NEXTJS_PORT="${NEXTJS_PORT:-${DEV_NEXTJS_PORT:-3001}}"
API_PORT="${API_PORT:-${DEV_API_PORT:-8100}}"
SUPERSET_PORT="${SUPERSET_PORT:-${DEV_SUPERSET_PORT:-8088}}"

echo "[check-primary-stack] host=${HOST} ui=${NEXTJS_PORT} api=${API_PORT} superset=${SUPERSET_PORT}"

if command -v docker >/dev/null 2>&1 && [ -f "${ROOT_DIR}/docker-compose.dev.yml" ]; then
  if [ -f "${ROOT_DIR}/.env.dev" ]; then
    echo "[check-primary-stack] docker compose ps"
    docker compose --env-file "${ROOT_DIR}/.env.dev" -f "${ROOT_DIR}/docker-compose.dev.yml" ps
  else
    echo "[check-primary-stack] .env.dev not found; skipping docker compose ps"
  fi
fi

echo "[check-primary-stack] FastAPI health"
curl --fail --silent --show-error "http://${HOST}:${API_PORT}/api/health"
printf "\n"

echo "[check-primary-stack] Next.js login"
curl --fail --silent --show-error --head "http://${HOST}:${NEXTJS_PORT}/login"

echo "[check-primary-stack] Superset health"
curl --fail --silent --show-error --head "http://${HOST}:${SUPERSET_PORT}/health"
