#!/usr/bin/env bash

set -euo pipefail

INIT_SENTINEL="${SUPERSET_INIT_SENTINEL:-/app/superset_home/.init_done}"
rm -f "${INIT_SENTINEL}"
/app/docker/docker-init.sh
touch "${INIT_SENTINEL}"
