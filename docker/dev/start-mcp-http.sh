#!/usr/bin/env bash

set -euo pipefail

cd /app
/app/docker/docker-bootstrap.sh
cd /app/pythonpath
exec python -m superset.mcp_service
