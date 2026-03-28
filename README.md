# Superset AI Assistant

`Superset AI Assistant` is a release-ready analytics assistant built on top of
`Next.js + FastAPI + Apache Superset + built-in Superset MCP`.

The product gives analysts and demo users one browser workflow for:

- asking business or technical questions in chat;
- previewing datasets before asking or charting;
- getting chart recommendations from previewed data;
- creating charts and dashboards in Superset with usable links;
- scanning Superset-connected PostgreSQL sources, including Pagila demo data.

The only supported runtime path is:

`Browser -> Next.js UI -> FastAPI API -> built-in Superset MCP -> Superset`

The legacy external `superset-mcp/main.py` runtime is no longer part of the
supported product path.

## Product Overview

Current user-facing routes:

| Route | Purpose |
| --- | --- |
| `/login` | Sign in |
| `/register` | Self-service account creation |
| `/app/chat` | Main assistant workflow |
| `/app/preview` | Data preview and field inspection |
| `/app/recommend` | Chart recommendation based on preview context |
| `/app/share` | Chart and dashboard creation with links |
| `/app/scan` | Schema/database scan for source discovery |

Release highlights in the current branch:

- stable new-chat and first-message flow;
- per-chat settings with persisted `business/technical` and detail levels;
- inline table/chart preview artifacts in chat;
- cleaned link cards instead of raw Superset URLs;
- Pagila-aware dataset discovery and real chart/dashboard flows;
- responsive shell with desktop collapse, mobile drawer, sticky composer, and
  mobile helper toggle;
- unified built-in MCP client/runtime path with parity coverage and CI jobs.

## Stack

| Layer | Technology | Main path |
| --- | --- | --- |
| UI | Next.js 14, React 18, Tailwind | `superset-ai-assistant-mcp/frontend-next/` |
| API | FastAPI | `superset-ai-assistant-mcp/api/` |
| Shared backend | Python services | `superset-ai-assistant-mcp/backend/` |
| Analytics platform | Apache Superset | `superset/` |
| MCP | built-in Superset MCP service | `superset/superset/mcp_service/` |
| Dev stack | Docker Compose | `docker-compose.dev.yml` |

## Repository Structure

```text
.
├── README.md
├── docker-compose.dev.yml
├── docker/dev/
├── docs/
├── superset/
└── superset-ai-assistant-mcp/
    ├── api/
    ├── backend/
    ├── frontend-next/
    ├── tests/
    ├── .env.example
    └── start_fastapi_stack.sh
```

Key docs:

- [User Guide](/home/superset_ai/docs/user-guide.md)
- [Developer Guide](/home/superset_ai/docs/developer-guide.md)
- [Architecture](/home/superset_ai/docs/architecture.md)
- [Release Notes](/home/superset_ai/docs/release-notes.md)
- [Deployment](/home/superset_ai/docs/deployment.md)
- [Update And Debug](/home/superset_ai/docs/update-and-debug.md)
- [Manual Smoke Checklist](/home/superset_ai/docs/manual-smoke-checklist.md)

## Quick Start

### Recommended local bring-up

```bash
cd /home/superset_ai
cp .env.dev.example .env.dev
./docker/dev/deploy-primary-stack.sh
```

Default local endpoints:

- UI: `http://127.0.0.1:3001/login`
- API health: `http://127.0.0.1:8100/api/health`
- Superset: `http://127.0.0.1:8088`

Smoke-check the stack:

```bash
cd /home/superset_ai
./docker/dev/check-primary-stack.sh
```

### Split local run

Superset:

```bash
cd /home/superset_ai/superset
docker compose -f docker-compose-image-tag.yml up -d db redis superset-init superset
```

FastAPI:

```bash
cd /home/superset_ai/superset-ai-assistant-mcp
.venv/bin/python -m uvicorn api.main:app --host 0.0.0.0 --port 8100
```

Next.js:

```bash
cd /home/superset_ai/superset-ai-assistant-mcp/frontend-next
npm install
NEXT_PUBLIC_API_URL=http://127.0.0.1:8100 \
NEXT_PUBLIC_BROWSER_API_URL=http://127.0.0.1:8100 \
npm run dev -- --hostname 0.0.0.0 --port 3001
```

## Requirements And Environment

Baseline runtime assumptions used in CI and docs:

- Python `3.12`
- Node.js `20`
- Docker / Docker Compose for the unified stack
- reachable Superset instance and built-in MCP runtime
- OpenAI API key

Primary environment files:

- root dev stack: [`.env.dev.example`](/home/superset_ai/.env.dev.example)
- assistant service env: [`superset-ai-assistant-mcp/.env.example`](/home/superset_ai/superset-ai-assistant-mcp/.env.example)

Most important variables:

| Variable | Meaning |
| --- | --- |
| `OPENAI_API_KEY` | Required for assistant generation |
| `OPENAI_MODEL` | Active OpenAI model |
| `ASSISTANT_DEPLOYMENT_MODE` | `development` or `production` |
| `SUPERSET_PRODUCT_MCP_RUNTIME` | `built_in_stdio` or `built_in_http` |
| `SUPERSET_PUBLIC_URL` | Public Superset host used for links |
| `SUPERSET_BASE_URL` | Internal Superset URL for backend access |
| `AUTH_JWT_SECRET` | Auth signing secret |
| `API_CORS_ORIGINS` | Only needed for intentional cross-origin API access |
| `US15_SHARE_BASE_URL` | Optional share-link override |

Runtime config validation runs on API startup and in deploy helpers.

## Running Frontend And Backend

Primary service entrypoints:

- FastAPI container/start script: [`start_fastapi_stack.sh`](/home/superset_ai/superset-ai-assistant-mcp/start_fastapi_stack.sh)
- Next.js proxy route: [`route.ts`](/home/superset_ai/superset-ai-assistant-mcp/frontend-next/src/app/api/[...path]/route.ts)
- FastAPI app: [`api/main.py`](/home/superset_ai/superset-ai-assistant-mcp/api/main.py)

Production-like publication model:

- `https://assistant.example.com/` -> Next.js
- `https://assistant.example.com/api/*` -> FastAPI
- `https://superset.example.com/` -> Superset

Proxy reference:

- [nginx-primary-ui.conf.example](/home/superset_ai/docs/examples/nginx-primary-ui.conf.example)

## Testing

Assistant API/backend regression set:

```bash
cd /home/superset_ai
PYTHONPATH=./superset-ai-assistant-mcp \
superset-ai-assistant-mcp/.venv/bin/python -m unittest \
  superset-ai-assistant-mcp/tests/test_api_auth.py \
  superset-ai-assistant-mcp/tests/test_api_chats.py \
  superset-ai-assistant-mcp/tests/test_api_viz.py \
  superset-ai-assistant-mcp/tests/test_api_scan.py \
  superset-ai-assistant-mcp/tests/test_api_frontend_logs.py \
  superset-ai-assistant-mcp/tests/test_auth_service.py \
  superset-ai-assistant-mcp/tests/test_ai_agent_clarifications.py \
  superset-ai-assistant-mcp/tests/test_us13_15_viz_service.py
```

Unit suites:

```bash
cd /home/superset_ai
PYTHONPATH=./superset-ai-assistant-mcp \
superset-ai-assistant-mcp/.venv/bin/python -m unittest discover \
  -s superset-ai-assistant-mcp/tests/unit \
  -p "test_*.py"
```

Frontend build:

```bash
cd /home/superset_ai/superset-ai-assistant-mcp/frontend-next
npm ci
npm run build
```

CI also runs:

- assistant unit tests;
- assistant product-flow tests;
- built-in MCP integration tests;
- MCP tool inventory enforcement;
- Superset MCP extension and core unit tests.

## Common Issues

`/api/health` returns config errors:
- check `OPENAI_API_KEY`, `OPENAI_MODEL`, `SUPERSET_PUBLIC_URL`,
  `AUTH_JWT_SECRET`, and `ASSISTANT_DEPLOYMENT_MODE`.

Chat links open the wrong Superset host:
- fix `SUPERSET_PUBLIC_URL` and, if set, `US15_SHARE_BASE_URL`.

UI works but long chat requests fail through the Next.js proxy:
- set `NEXT_PUBLIC_BROWSER_API_URL` so the browser can call FastAPI directly.

Production validation blocks startup:
- in `production` mode, placeholder JWT secrets and localhost public URLs are
  hard failures by design.

Pagila flows are unavailable:
- confirm `pagila-db`, `superset-init`, `superset`, and `mcp-http` are healthy,
  then rerun the scan flow.

## Documentation

Start here depending on your role:

- product usage: [docs/user-guide.md](/home/superset_ai/docs/user-guide.md)
- codebase and local dev: [docs/developer-guide.md](/home/superset_ai/docs/developer-guide.md)
- system design and flows: [docs/architecture.md](/home/superset_ai/docs/architecture.md)
- rollout and day-2 ops: [docs/deployment.md](/home/superset_ai/docs/deployment.md)
- update/debug runbook: [docs/update-and-debug.md](/home/superset_ai/docs/update-and-debug.md)
- current release summary: [docs/release-notes.md](/home/superset_ai/docs/release-notes.md)

## Historical Migration Material

Migration evidence and parity artifacts remain in:

- [`docs/mcp-migration/`](/home/superset_ai/docs/mcp-migration)
- [`docs/streamlit-retirement-summary.md`](/home/superset_ai/docs/streamlit-retirement-summary.md)

These are historical/supporting documents, not the primary runbooks for the
current product.
