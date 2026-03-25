#!/usr/bin/env bash

set -euo pipefail

INIT_SENTINEL="${SUPERSET_INIT_SENTINEL:-/app/superset_home/.init_done}"
WAIT_SECONDS="${SUPERSET_INIT_WAIT_SECONDS:-300}"

echo "Waiting for Superset init sentinel at ${INIT_SENTINEL}"
for ((i=0; i<WAIT_SECONDS; i++)); do
  if [ -f "${INIT_SENTINEL}" ]; then
    echo "Superset init complete, starting: $*"
    exec "$@"
  fi
  sleep 1
done

echo "Timed out waiting for ${INIT_SENTINEL}" >&2
exit 1
