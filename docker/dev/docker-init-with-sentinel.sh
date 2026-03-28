#!/usr/bin/env bash

set -euo pipefail

INIT_SENTINEL="${SUPERSET_INIT_SENTINEL:-/app/superset_home/.init_done}"
rm -f "${INIT_SENTINEL}"
/app/docker/docker-init.sh
/app/docker/dev/bootstrap-pagila-demo.sh
touch "${INIT_SENTINEL}"
