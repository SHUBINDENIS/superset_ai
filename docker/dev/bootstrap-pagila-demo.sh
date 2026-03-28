#!/usr/bin/env bash

set -euo pipefail

if [[ "${DEMO_PAGILA_ENABLED:-yes}" != "yes" ]]; then
  echo "[pagila-demo] demo bootstrap disabled; skipping"
  exit 0
fi

echo "[pagila-demo] ensuring Pagila demo source and datasets in Superset"
python /app/docker/dev/bootstrap_pagila_demo.py
