#!/usr/bin/env sh
set -eu

NEXTJS_PORT="${NEXTJS_PORT:-3001}"
NEXTJS_RUNTIME="${NEXTJS_RUNTIME:-production}"

cd /app/superset-ai-assistant-mcp/frontend-next

if [ ! -x node_modules/.bin/next ]; then
  npm ci
fi

if [ "${NEXTJS_RUNTIME}" = "production" ]; then
  npm run build
  exec npm run start -- --hostname 0.0.0.0 --port "${NEXTJS_PORT}"
fi

exec npm run dev -- --hostname 0.0.0.0 --port "${NEXTJS_PORT}"
