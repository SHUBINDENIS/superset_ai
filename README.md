# Superset AI Assistant

Analytics assistant for Apache Superset built on `Next.js + FastAPI + built-in Superset MCP`.

The system gives analysts one browser workflow for asking questions, previewing datasets, getting chart recommendations, and creating charts or dashboards in Superset without switching between disconnected tools. The supported runtime path is:

`Browser -> Next.js UI -> FastAPI API -> built-in Superset MCP -> Superset`

The legacy external `superset-mcp/main.py` runtime is not part of the active product path.

## What This System Does

- chat-driven business and technical analysis
- dataset preview and field inspection before charting
- chart recommendation from preview context
- chart and dashboard creation with normalized Superset links
- schema and database scan across Superset-connected PostgreSQL sources, including Pagila demo data

## Why The Architecture Matters

- `Next.js` owns the user-facing application shell and browser workflow
- `FastAPI` owns auth, chat, viz, scan, and runtime validation
- built-in `Superset MCP` keeps the assistant on the same product path as Superset datasets, charts, and dashboards
- the repository ships a single supported runtime instead of parallel legacy entrypoints

That separation keeps the UI responsive, backend behavior testable, and Superset integration explicit.

## System At A Glance

| Area | What is here |
| --- | --- |
| Product UI | Login, chat, preview, recommend, share, and scan flows |
| Backend API | Auth, chats, visualization flows, schema scan, and frontend logs |
| Analytics platform | Apache Superset for datasets, SQL Lab, charts, and dashboards |
| Tool layer | built-in Superset MCP service used by the assistant runtime |
| Local runtime | Docker Compose stack for Next.js, FastAPI, Superset, Pagila, and supporting services |

Current user-facing routes:

| Route | Purpose |
| --- | --- |
| `/login` | Sign in |
| `/register` | Self-service account creation |
| `/app/chat` | Main assistant workflow |
| `/app/preview` | Data preview and field inspection |
| `/app/recommend` | Chart recommendation based on preview context |
| `/app/share` | Chart and dashboard creation with links |
| `/app/scan` | Schema and database scan for source discovery |

## Key Capabilities

- stable new-chat and first-message flow
- per-chat settings for `business` vs `technical` mode and detail level
- inline table and chart artifacts in chat
- normalized link cards instead of raw Superset URLs
- Pagila-aware dataset discovery and chart/dashboard flows
- responsive shell with mobile and desktop support
- unified built-in MCP runtime with parity coverage and CI enforcement

## Quick Start

### Recommended local bring-up

```bash
cp .env.dev.example .env.dev
./docker/dev/deploy-primary-stack.sh
```

Default local endpoints:

- UI: `http://127.0.0.1:3001/login`
- API health: `http://127.0.0.1:8100/api/health`
- Superset: `http://127.0.0.1:8088`

Smoke-check the stack:

```bash
./docker/dev/check-primary-stack.sh
```

### Split local run

Superset:

```bash
cd superset
docker compose -f docker-compose-image-tag.yml up -d db redis superset-init superset
```

FastAPI:

```bash
cd superset-ai-assistant-mcp
.venv/bin/python -m uvicorn api.main:app --host 0.0.0.0 --port 8100
```

Next.js:

```bash
cd superset-ai-assistant-mcp/frontend-next
npm install
NEXT_PUBLIC_API_URL=http://127.0.0.1:8100 \
NEXT_PUBLIC_BROWSER_API_URL=http://127.0.0.1:8100 \
npm run dev -- --hostname 0.0.0.0 --port 3001
```

## Where To Look

### Docs map

- [Docs Index](docs/README.md)
- [Architecture](docs/architecture.md)
- [Deployment](docs/deployment.md)
- [User Guide](docs/user-guide.md)
- [Developer Guide](docs/developer-guide.md)
- [Release Notes](docs/release-notes.md)
- [Update And Debug](docs/update-and-debug.md)
- [Manual Smoke Checklist](docs/manual-smoke-checklist.md)

### Main code boundaries

- UI: [`superset-ai-assistant-mcp/frontend-next/`](superset-ai-assistant-mcp/frontend-next/)
- API: [`superset-ai-assistant-mcp/api/`](superset-ai-assistant-mcp/api/)
- backend services: [`superset-ai-assistant-mcp/backend/`](superset-ai-assistant-mcp/backend/)
- assistant tests: [`superset-ai-assistant-mcp/tests/`](superset-ai-assistant-mcp/tests/)
- Superset and built-in MCP: [`superset/`](superset/)

## Runtime And Deployment

Primary runtime model:

- `https://assistant.example.com/` -> Next.js
- `https://assistant.example.com/api/*` -> FastAPI
- `https://superset.example.com/` -> Superset

Most important runtime files:

- dev stack: [`docker-compose.dev.yml`](docker-compose.dev.yml)
- primary deploy helper: [`docker/dev/deploy-primary-stack.sh`](docker/dev/deploy-primary-stack.sh)
- primary stack health check: [`docker/dev/check-primary-stack.sh`](docker/dev/check-primary-stack.sh)
- FastAPI entrypoint: [`superset-ai-assistant-mcp/api/main.py`](superset-ai-assistant-mcp/api/main.py)
- Next.js API proxy: [`superset-ai-assistant-mcp/frontend-next/src/app/api/[...path]/route.ts`](superset-ai-assistant-mcp/frontend-next/src/app/api/[...path]/route.ts)
- proxy example: [`docs/examples/nginx-primary-ui.conf.example`](docs/examples/nginx-primary-ui.conf.example)

Primary environment files:

- root dev stack: [`.env.dev.example`](.env.dev.example)
- assistant service env: [`superset-ai-assistant-mcp/.env.example`](superset-ai-assistant-mcp/.env.example)

## Testing And Reliability

The repository includes:

- assistant unit tests
- API and product-flow regression tests
- built-in MCP integration tests
- MCP tool inventory enforcement
- release smoke-check scripts for the unified stack

Representative test locations:

- API and product flow tests: [`superset-ai-assistant-mcp/tests/`](superset-ai-assistant-mcp/tests/)
- MCP integration tests: [`superset-ai-assistant-mcp/tests/integration/mcp_client/`](superset-ai-assistant-mcp/tests/integration/mcp_client/)
- unit suites: [`superset-ai-assistant-mcp/tests/unit/`](superset-ai-assistant-mcp/tests/unit/)
- CI workflows: [`.github/workflows/ci.yml`](.github/workflows/ci.yml), [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml)

Common local commands:

```bash
PYTHONPATH=./superset-ai-assistant-mcp \
superset-ai-assistant-mcp/.venv/bin/python -m unittest discover \
  -s superset-ai-assistant-mcp/tests/unit \
  -p "test_*.py"
```

```bash
cd superset-ai-assistant-mcp/frontend-next
npm ci
npm run build
```

## Repository Layout

```text
.
├── README.md
├── docker-compose.dev.yml
├── docker/dev/                     # deploy, validation, and stack helper scripts
├── docs/                           # architecture, deployment, user/dev guides, rollout docs
├── superset/                       # Apache Superset + built-in MCP implementation
└── superset-ai-assistant-mcp/
    ├── api/                        # FastAPI routes and app wiring
    ├── backend/                    # assistant, viz, auth, scan, and domain services
    ├── frontend-next/              # Next.js product UI
    ├── tests/                      # unit, regression, and integration tests
    └── start_fastapi_stack.sh
```

## Common Issues

`/api/health` returns config errors:
- check `OPENAI_API_KEY`, `OPENAI_MODEL`, `SUPERSET_PUBLIC_URL`, `AUTH_JWT_SECRET`, and `ASSISTANT_DEPLOYMENT_MODE`

Chat links open the wrong Superset host:
- fix `SUPERSET_PUBLIC_URL` and, if set, `US15_SHARE_BASE_URL`

UI works but long chat requests fail through the Next.js proxy:
- set `NEXT_PUBLIC_BROWSER_API_URL` so the browser can call FastAPI directly

Production validation blocks startup:
- in `production` mode, placeholder JWT secrets and localhost public URLs are hard failures by design

Pagila flows are unavailable:
- confirm `pagila-db`, `superset-init`, `superset`, and `mcp-http` are healthy, then rerun the scan flow

## Historical Migration Material

Migration evidence and parity artifacts remain in:

- [`docs/mcp-migration/`](docs/mcp-migration/)
- [`docs/streamlit-retirement-summary.md`](docs/streamlit-retirement-summary.md)

These documents are historical support material, not the primary runbooks for the current system.
