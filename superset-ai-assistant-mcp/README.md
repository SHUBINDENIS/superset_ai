# Superset AI Assistant

Этот каталог теперь поддерживает один runtime path:

- `FastAPI` backend в `api/`
- `Next.js` frontend в `frontend-next/`
- shared backend services в `backend/`

`Streamlit` UI/runtime path удалён. История удаления и сохранённые backend-only
модули перечислены в `../docs/streamlit-retirement-summary.md`.

## What Lives Here

- `api/`
  - auth/chat/viz/scan/frontend-log routes
- `frontend-next/`
  - primary UI for login, chat, preview, recommend, share and scan
- `backend/`
  - agent orchestration and domain services
  - retained helper/admin business modules `US2-US5` remain here as backend
    code, but they no longer have a supported Streamlit runtime surface
- `tests/`
  - API, backend and unit coverage
- `start_fastapi_stack.sh`
  - container/runtime entrypoint for the API image
- `Dockerfile`
  - FastAPI runtime image used by `assistant-api`

## Supported Local Run

### Unified compose

```bash
cd /home/superset_ai
cp .env.dev.example .env.dev
./docker/dev/deploy-primary-stack.sh
```

Endpoints:
- UI: `http://localhost:3001/login`
- API: `http://localhost:8100/api/health`
- Superset: `http://localhost:8088`

Low-level compose path for debugging only:

```bash
cd /home/superset_ai
docker compose --env-file .env.dev -f docker-compose.dev.yml up -d --build
```

### Split run

FastAPI:

```bash
cd /home/superset_ai/superset-ai-assistant-mcp
.venv/bin/python -m uvicorn api.main:app --host 0.0.0.0 --port 8100
```

Next.js:

```bash
cd /home/superset_ai/superset-ai-assistant-mcp/frontend-next
npm install
NEXT_PUBLIC_API_URL=http://127.0.0.1:8100 npm run dev -- --hostname 0.0.0.0 --port 3001
```

## Docker Runtime

Assistant image:

```bash
cd /home/superset_ai
docker build -t ai_superset_api -f superset-ai-assistant-mcp/Dockerfile .
docker run --rm -p 8100:8100 --env-file superset-ai-assistant-mcp/.env ai_superset_api
```

Этот image поднимает только `FastAPI`. `Next.js` запускается отдельно либо
через `docker-compose.dev.yml`, либо напрямую через `npm run start`.

## Production-Like Public Model

- `https://assistant.example.com/` -> `Next.js`
- `https://assistant.example.com/api/*` -> `FastAPI`
- `https://superset.example.com/` -> `Superset`

Reverse proxy example:
- `../docs/examples/nginx-primary-ui.conf.example`

Runbooks:
- `../docs/deployment.md`
- `../docs/production-rollout-runbook.md`
- `../docs/public-go-live-checklist.md`
- `../docs/manual-smoke-checklist.md`
- `../docs/update-and-debug.md`

## Verification

```bash
cd /home/superset_ai
./docker/dev/deploy-primary-stack.sh
./docker/dev/check-primary-stack.sh
```

Operator helpers:
- `../docker/dev/deploy-primary-stack.sh`
- `../docker/dev/refresh-primary-stack.sh`
- `../docker/dev/check-primary-stack.sh`
- `../docker/dev/validate-primary-env.sh`
- `../docker/dev/tail-primary-logs.sh`

Recommended test set:

```bash
cd /home/superset_ai
PYTHONPATH=./superset-ai-assistant-mcp superset-ai-assistant-mcp/.venv/bin/python -m unittest \
  superset-ai-assistant-mcp/tests/test_api_auth.py \
  superset-ai-assistant-mcp/tests/test_api_chats.py \
  superset-ai-assistant-mcp/tests/test_api_viz.py \
  superset-ai-assistant-mcp/tests/test_api_scan.py \
  superset-ai-assistant-mcp/tests/test_api_frontend_logs.py
```

```bash
cd /home/superset_ai/superset-ai-assistant-mcp/frontend-next
npm run build
```
