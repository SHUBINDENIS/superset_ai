#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
HOST="${CHECK_HOST:-127.0.0.1}"
API_PORT="${API_PORT:-${DEV_API_PORT:-8100}}"

usage() {
  cat <<'EOF'
Usage:
  ./docker/dev/deploy-primary-stack.sh [services...]

Defaults:
  services: assistant-api assistant-web

This helper validates env, stamps release/build metadata for the current git
revision, rebuilds the selected services, runs health checks, and prints the
active release metadata from /api/health.
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ $# -gt 0 ]]; then
  SERVICES=("$@")
else
  SERVICES=(assistant-api assistant-web)
fi

BUILD_SHA="$(git -C "${ROOT_DIR}" rev-parse --short=12 HEAD 2>/dev/null || echo unknown)"
BRANCH_NAME="$(git -C "${ROOT_DIR}" rev-parse --abbrev-ref HEAD 2>/dev/null || echo detached)"
BUILD_TIMESTAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

export ASSISTANT_RELEASE_VERSION="${ASSISTANT_RELEASE_VERSION:-${BUILD_SHA}}"
export ASSISTANT_BUILD_SHA="${ASSISTANT_BUILD_SHA:-${BUILD_SHA}}"
export ASSISTANT_BUILD_TIMESTAMP="${ASSISTANT_BUILD_TIMESTAMP:-${BUILD_TIMESTAMP}}"

echo "[deploy-primary-stack] branch=${BRANCH_NAME} sha=${BUILD_SHA} release=${ASSISTANT_RELEASE_VERSION}"

"${ROOT_DIR}/docker/dev/validate-primary-env.sh"
"${ROOT_DIR}/docker/dev/refresh-primary-stack.sh" rebuild "${SERVICES[@]}"
"${ROOT_DIR}/docker/dev/check-primary-stack.sh"

echo "[deploy-primary-stack] active release metadata"
curl --fail --silent --show-error "http://${HOST}:${API_PORT}/api/health" | python3 -c '
import json, sys
data = json.load(sys.stdin)
print(
    "[deploy-primary-stack] "
    f"status={data.get('"'"'status'"'"')} "
    f"release_version={data.get('"'"'release_version'"'"')} "
    f"build_sha={data.get('"'"'build_sha'"'"')} "
    f"build_timestamp={data.get('"'"'build_timestamp'"'"')} "
    f"runtime={data.get('"'"'runtime'"'"')}"
)
'
