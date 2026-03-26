#!/usr/bin/env sh
set -eu

NEXTJS_PORT="${NEXTJS_PORT:-3001}"
NEXTJS_RUNTIME="${NEXTJS_RUNTIME:-production}"

cd /app/superset-ai-assistant-mcp/frontend-next

if [ ! -x node_modules/.bin/next ]; then
  npm ci
fi

case "${NEXTJS_RUNTIME}" in
  production)
    npm run build
    exec npm run start -- --hostname 0.0.0.0 --port "${NEXTJS_PORT}"
    ;;
  development)
    exec npm run dev -- --hostname 0.0.0.0 --port "${NEXTJS_PORT}"
    ;;
  *)
    echo "Unsupported NEXTJS_RUNTIME='${NEXTJS_RUNTIME}'. Use 'production' or 'development'." >&2
    exit 64
    ;;
esac
