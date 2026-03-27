# Superset AI: NL→SQL→Chart

Проект для MVP/MUP этапов по веб-разработке: AI-ассистент над Apache Superset,
который помогает формулировать аналитические запросы на естественном языке,
делать preview данных, рекомендовать визуализации и создавать chart/dashboard
артефакты через built-in Superset MCP service.

## Current Supported Stack

В репозитории поддерживается один runtime path:

- UI: `Next.js` в `superset-ai-assistant-mcp/frontend-next`
- API: `FastAPI` в `superset-ai-assistant-mcp/api`
- Shared business logic: `superset-ai-assistant-mcp/backend`
- Superset access: built-in MCP service в `superset/superset/mcp_service`

`Streamlit` больше не является поддерживаемым runtime/UI path. Что было
удалено и что сохранено как backend-only код, зафиксировано в
`docs/streamlit-retirement-summary.md`.

## Repository Layout

- `superset/`
  - Apache Superset, docker assets и built-in MCP implementation
- `superset-ai-assistant-mcp/`
  - `api/`: auth/chat/viz/scan/logging routes
  - `frontend-next/`: primary UI
  - `backend/`: shared business modules and agent integration
  - `tests/`: Python tests for API, backend and observability
- `docker-compose.dev.yml`
  - unified local dev stack for Superset + MCP HTTP + FastAPI + Next.js
- `docker/dev/`
  - helper scripts for unified local dev stack
- `docs/`
  - deployment, rollout, smoke and historical migration/cutover material

## Default Local Bring-Up

Рекомендуемый repo-backed запуск:

```bash
cd /home/superset_ai
cp .env.dev.example .env.dev
./docker/dev/deploy-primary-stack.sh
```

После запуска доступны:

- primary UI: `http://<host>:3001/login`
- primary API health: `http://<host>:8100/api/health`
- Superset: `http://<host>:8088`

Low-level compose path for debugging only:

```bash
cd /home/superset_ai
docker compose --env-file .env.dev -f docker-compose.dev.yml up -d --build
```

## Split Local Bring-Up

Если unified compose не используется:

1. Поднять Superset:
```bash
cd /home/superset_ai/superset
docker compose -f docker-compose-image-tag.yml up -d db redis superset-init superset
```
2. Поднять FastAPI:
```bash
cd /home/superset_ai/superset-ai-assistant-mcp
.venv/bin/python -m uvicorn api.main:app --host 0.0.0.0 --port 8100
```
3. Поднять Next.js:
```bash
cd /home/superset_ai/superset-ai-assistant-mcp/frontend-next
npm install
NEXT_PUBLIC_API_URL=http://127.0.0.1:8100 npm run dev -- --hostname 0.0.0.0 --port 3001
```

## Default Production-Like Access Model

- `https://assistant.example.com/` -> `Next.js`
- `https://assistant.example.com/api/*` -> `FastAPI`
- `https://superset.example.com/` -> `Superset`

Reverse-proxy example:
- `docs/examples/nginx-primary-ui.conf.example`

Deployment and rollout docs:
- `docs/deployment.md`
- `docs/production-rollout-runbook.md`
- `docs/public-go-live-checklist.md`
- `docs/update-and-debug.md`

## Verification

Primary health checks:

```bash
./docker/dev/deploy-primary-stack.sh
./docker/dev/check-primary-stack.sh
```

Manual smoke:
- `docs/manual-smoke-checklist.md`
- `docs/demo-query-pack.md`
- `docs/public-go-live-checklist.md`
- `docs/update-and-debug.md`

Operator helpers:
- `docker/dev/deploy-primary-stack.sh`
- `docker/dev/refresh-primary-stack.sh`
- `docker/dev/check-primary-stack.sh`
- `docker/dev/validate-primary-env.sh`
- `docker/dev/tail-primary-logs.sh`

## Test Commands

Python API/backend suites:

```bash
cd /home/superset_ai
PYTHONPATH=./superset-ai-assistant-mcp superset-ai-assistant-mcp/.venv/bin/python -m unittest \
  superset-ai-assistant-mcp/tests/test_api_auth.py \
  superset-ai-assistant-mcp/tests/test_api_chats.py \
  superset-ai-assistant-mcp/tests/test_api_viz.py \
  superset-ai-assistant-mcp/tests/test_api_scan.py \
  superset-ai-assistant-mcp/tests/test_api_frontend_logs.py
```

Python unit suites:

```bash
cd /home/superset_ai
PYTHONPATH=./superset-ai-assistant-mcp superset-ai-assistant-mcp/.venv/bin/python -m unittest discover \
  -s superset-ai-assistant-mcp/tests/unit \
  -p "test_*.py"
```

Next.js build:

```bash
cd /home/superset_ai/superset-ai-assistant-mcp/frontend-next
npm run build
```

## Historical Transition Docs

Следующие документы сохранены как архив перехода от phased cutover к одному
runtime path:

- `docs/dual-run-parity-readiness.md`
- `docs/phased-cutover-plan.md`
- `docs/phased-cutover-signoff.md`

Они больше не являются текущими runbook’ами для эксплуатации.
