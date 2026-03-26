#!/usr/bin/env sh
set -eu

NEXTJS_PORT="${NEXTJS_PORT:-3001}"

cd /app/superset-ai-assistant-mcp/frontend-next

if [ ! -x node_modules/.bin/next ]; then
  npm ci
fi

exec npm run dev -- --hostname 0.0.0.0 --port "${NEXTJS_PORT}"
