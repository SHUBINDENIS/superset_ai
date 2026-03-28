# Developer Guide

This guide documents the current supported implementation of the Superset AI
Assistant as it exists in the repository today.

It focuses on:

- the active runtime path;
- the module layout that matters for day-to-day work;
- the chat/session/artifact data model;
- the built-in MCP integration;
- local development, testing, and debugging;
- known debts that should not be mistaken for release blockers.

## Current Runtime

Supported path:

`Next.js UI -> FastAPI API -> backend services -> built-in Superset MCP -> Superset`

Not supported as runtime:

- Streamlit UI
- external `superset-mcp/main.py`
- websocket assistant path

Relevant historical references:

- [streamlit-retirement-summary.md](/home/superset_ai/docs/streamlit-retirement-summary.md)
- [mcp-migration/](/home/superset_ai/docs/mcp-migration)

## Repository Structure

```text
/home/superset_ai
├── README.md
├── docker-compose.dev.yml
├── docker/dev/
├── docs/
├── superset/
└── superset-ai-assistant-mcp/
    ├── .env.example
    ├── Dockerfile
    ├── README.md
    ├── api/
    ├── backend/
    ├── data/
    ├── frontend-next/
    ├── tests/
    └── start_fastapi_stack.sh
```

## Key Modules

### Frontend

Core files:

- [`src/app/app/layout.tsx`](/home/superset_ai/superset-ai-assistant-mcp/frontend-next/src/app/app/layout.tsx)
- [`src/app/app/chat/page.tsx`](/home/superset_ai/superset-ai-assistant-mcp/frontend-next/src/app/app/chat/page.tsx)
- [`src/app/app/preview/page.tsx`](/home/superset_ai/superset-ai-assistant-mcp/frontend-next/src/app/app/preview/page.tsx)
- [`src/app/app/recommend/page.tsx`](/home/superset_ai/superset-ai-assistant-mcp/frontend-next/src/app/app/recommend/page.tsx)
- [`src/app/app/share/page.tsx`](/home/superset_ai/superset-ai-assistant-mcp/frontend-next/src/app/app/share/page.tsx)
- [`src/app/app/scan/page.tsx`](/home/superset_ai/superset-ai-assistant-mcp/frontend-next/src/app/app/scan/page.tsx)
- [`src/hooks/use-auth.ts`](/home/superset_ai/superset-ai-assistant-mcp/frontend-next/src/hooks/use-auth.ts)
- [`src/hooks/use-chats.tsx`](/home/superset_ai/superset-ai-assistant-mcp/frontend-next/src/hooks/use-chats.tsx)
- [`src/hooks/use-viz.tsx`](/home/superset_ai/superset-ai-assistant-mcp/frontend-next/src/hooks/use-viz.tsx)

### API

Core files:

- [`api/main.py`](/home/superset_ai/superset-ai-assistant-mcp/api/main.py)
- [`api/deps.py`](/home/superset_ai/superset-ai-assistant-mcp/api/deps.py)
- [`api/runtime_config.py`](/home/superset_ai/superset-ai-assistant-mcp/api/runtime_config.py)
- [`api/schemas.py`](/home/superset_ai/superset-ai-assistant-mcp/api/schemas.py)
- [`api/routers/auth.py`](/home/superset_ai/superset-ai-assistant-mcp/api/routers/auth.py)
- [`api/routers/chats.py`](/home/superset_ai/superset-ai-assistant-mcp/api/routers/chats.py)
- [`api/routers/viz.py`](/home/superset_ai/superset-ai-assistant-mcp/api/routers/viz.py)
- [`api/routers/scan.py`](/home/superset_ai/superset-ai-assistant-mcp/api/routers/scan.py)
- [`api/routers/health.py`](/home/superset_ai/superset-ai-assistant-mcp/api/routers/health.py)

### Backend services

Core files:

- [`backend/ai_agent.py`](/home/superset_ai/superset-ai-assistant-mcp/backend/ai_agent.py)
- [`backend/auth_service.py`](/home/superset_ai/superset-ai-assistant-mcp/backend/auth_service.py)
- [`backend/us13_15_viz_service.py`](/home/superset_ai/superset-ai-assistant-mcp/backend/us13_15_viz_service.py)
- [`backend/us1_schema_profiler.py`](/home/superset_ai/superset-ai-assistant-mcp/backend/us1_schema_profiler.py)
- [`backend/observability.py`](/home/superset_ai/superset-ai-assistant-mcp/backend/observability.py)
- [`backend/openai_safe_adapter.py`](/home/superset_ai/superset-ai-assistant-mcp/backend/openai_safe_adapter.py)

### MCP client layer

Core files:

- [`backend/mcp_client/runtime.py`](/home/superset_ai/superset-ai-assistant-mcp/backend/mcp_client/runtime.py)
- [`backend/mcp_client/built_in_client.py`](/home/superset_ai/superset-ai-assistant-mcp/backend/mcp_client/built_in_client.py)
- [`backend/mcp_client/legacy_compat_adapter.py`](/home/superset_ai/superset-ai-assistant-mcp/backend/mcp_client/legacy_compat_adapter.py)
- [`backend/mcp_client/tool_registry.py`](/home/superset_ai/superset-ai-assistant-mcp/backend/mcp_client/tool_registry.py)
- [`backend/mcp_client/errors.py`](/home/superset_ai/superset-ai-assistant-mcp/backend/mcp_client/errors.py)

### Superset built-in MCP

Core repo area:

- [`superset/superset/mcp_service/`](/home/superset_ai/superset/superset/mcp_service)

Relevant extension tools added for product parity:

- `mcp_ext.list_databases`
- `mcp_ext.create_empty_dashboard`
- `mcp_ext.legacy_chart_create`

## Frontend Architecture

The frontend uses the Next.js App Router and React Query.

### Routing

- `/login` and `/register` are public routes.
- `/app/*` is a protected layout.
- `/app` redirects to `/app/chat`.

### Auth model

- `useAuth()` calls `/api/auth/me`.
- `useLogin()` and `useRegister()` write the auth cookie through FastAPI.
- protected layout redirects unauthenticated users back to `/login`.

### Chat model

`use-chats.tsx` provides:

- active chat selection;
- per-chat pending-state tracking;
- React Query cache management for chat sessions and message history;
- mutations for create, rename, activate, delete, clear, send, and settings updates.

Important release behavior:

- a new chat can send the first message without a page refresh;
- pending state is tracked per session, not globally;
- cross-tab chat sync events invalidate relevant caches.

### Chat UI model

`/app/chat` is built from:

- helper area and help drawer;
- chat list sidebar;
- scroll-isolated message panel;
- collapsible settings bar;
- sticky composer;
- artifact rendering for chart/table/link payloads.

### Viz flow model

`use-viz.tsx` provides shared session-scoped viz context:

- preview result;
- selected dataset/database;
- recommendation result.

This state is persisted in `sessionStorage` under
`superset-ai-viz-flow-v1` and is reused across:

- preview;
- recommend;
- share.

### API access model

There are two frontend API paths:

1. same-origin proxy through [`src/app/api/[...path]/route.ts`](/home/superset_ai/superset-ai-assistant-mcp/frontend-next/src/app/api/[...path]/route.ts)
2. optional direct browser-to-FastAPI calls through `NEXT_PUBLIC_BROWSER_API_URL`

Why both exist:

- same-origin is the cleanest default;
- direct browser API avoids proxy timeout issues for long chat requests.

## Backend Architecture

### API layer

FastAPI is a thin contract layer around the backend services.

Routes:

- `/api/auth/*`
- `/api/chats/*`
- `/api/viz/*`
- `/api/scan`
- `/api/health`
- `/api/frontend-logs`

### Dependency model

`api/deps.py` is intentionally lazy:

- `AuthService` is loaded without importing the heavy `backend` package;
- the agent manager, viz service, and scan runner are created only when needed;
- this keeps startup lighter and avoids loading MCP/OpenAI dependencies for
  auth-only requests.

### Runtime validation

`api/runtime_config.py` validates:

- deployment mode;
- OpenAI presence;
- JWT secret strength;
- public Superset URL correctness;
- share-link origin alignment;
- production safety around localhost CORS and public URLs.

The API fails startup on invalid production-grade config.

### Auth and persistence

`AuthService` stores:

- users;
- auth JWT state;
- chat sessions;
- chat messages;
- message metadata/artifacts;
- per-chat settings.

Storage is SQLite-backed through `AUTH_DB_PATH`.

### Assistant orchestration

`backend/ai_agent.py` is the main orchestration layer.

It is responsible for:

- model setup;
- guardrail integration;
- structured dataset discovery;
- Pagila-aware chart/dashboard workflows;
- response-style and detail-level shaping;
- artifact construction for table/chart/link results;
- recent-object follow-up behavior such as `дай ссылку на дашборд`.

### Preview/recommend/share service

`backend/us13_15_viz_service.py` wraps the product MCP runtime and provides:

- database listing;
- dataset listing and metadata;
- preview SQL execution;
- column profiling;
- recommendation scoring;
- chart parameter building;
- chart/dashboard creation and share-link normalization.

### Scan flow

`backend/us1_schema_profiler.py` powers the scan route and produces:

- database candidates;
- PostgreSQL-focused database list;
- profiled tables;
- relation discovery;
- report path and summary.

## Chat, Session, History, And Settings Model

### Chat session

Persisted fields include:

- `session_id`
- `title`
- `created_at`
- `updated_at`
- `last_message_at`
- `is_archived`
- `settings_json`

### Per-chat settings

Current settings contract:

- `response_style`: `business | technical`
- `detail_level`: `concise | standard | detailed`

These settings are:

- normalized on write;
- returned in chat list payloads;
- updated through `PATCH /api/chats/{session_id}/settings`;
- applied to subsequent assistant replies.

### Message history

Message records include:

- `role`
- `content`
- `created_at`
- `finish_reason`
- `model`
- normalized response settings
- structured artifacts

### Artifact model

Supported artifact types:

- `table_preview`
- `chart_preview`
- `link`

Why this matters:

- UI rendering stays deterministic;
- the assistant can surface chart/dashboard/SQL Lab links without raw URLs in
  the text body;
- follow-up prompts can mine recent artifacts from prior assistant messages.

## Preview And Artifact Model

Preview payloads include:

- `database_id`
- `dataset_id`
- `schema`
- `sql_executed`
- `preview_limit`
- `rows_count`
- `rows`
- profiled `columns`
- `field_explanations`

Chart artifacts include:

- chart type;
- row sample;
- `x_key`;
- `y_key`;
- optional href and label.

Link artifacts include:

- href;
- link label;
- link kind such as `chart`, `dashboard`, or `sql_lab`;
- optional object id;
- optional table/database context.

## Database Discovery, Chart, And Dashboard Workflow

### Discovery

The assistant no longer relies only on naive dataset-name matching.

It uses:

- database-level evidence from `list_databases`;
- dataset search terms built from the user prompt;
- dataset metadata scoring;
- Pagila-specific priority heuristics.

### Direct chart flow

For chart-like prompts, the agent can:

1. resolve a likely dataset;
2. inspect dataset metadata;
3. build a safe preview query;
4. create chart params;
5. create a chart;
6. return chart preview and labeled links.

### Dashboard flow

For dashboard-like prompts, the agent can:

1. build several chart candidates;
2. create charts through the viz service;
3. create a dashboard;
4. persist artifacts and useful links in chat history.

### Numeric year handling

The release includes a specific guard against treating numeric `year` columns
as temporal `DATE_TRUNC` inputs. This matters for chart safety in datasets that
store year as an integer dimension.

## Built-in MCP Integration

### Product runtime

`create_product_mcp_runtime()` creates:

- an `mcp_use` client config for the selected runtime;
- a `BuiltInMCPClient`;
- a `LegacyCompatAdapter` for old tool contracts;
- runtime metadata including available tool names.

Supported product runtimes:

- `built_in_stdio`
- `built_in_http`

### Tool inventory

Product-required direct built-in tools are defined in
[`tool_registry.py`](/home/superset_ai/superset-ai-assistant-mcp/backend/mcp_client/tool_registry.py)
and enforced by:

- [`mcp_tool_inventory.yaml`](/home/superset_ai/superset-ai-assistant-mcp/tests/fixtures/mcp_tool_inventory.yaml)
- [`test_tool_inventory.py`](/home/superset_ai/superset-ai-assistant-mcp/tests/unit/mcp_client/test_tool_inventory.py)

### Legacy compatibility

`LegacyCompatAdapter` preserves selected legacy tool contracts while routing
them to built-in tools and normalizing the response shape.

This keeps migration parity without preserving the old runtime dependency.

## Local Development

### Recommended local stack

```bash
cd /home/superset_ai
cp .env.dev.example .env.dev
./docker/dev/deploy-primary-stack.sh
```

### Split run

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

### Main operator/developer helpers

- [`deploy-primary-stack.sh`](/home/superset_ai/docker/dev/deploy-primary-stack.sh)
- [`refresh-primary-stack.sh`](/home/superset_ai/docker/dev/refresh-primary-stack.sh)
- [`check-primary-stack.sh`](/home/superset_ai/docker/dev/check-primary-stack.sh)
- [`validate-primary-env.sh`](/home/superset_ai/docker/dev/validate-primary-env.sh)
- [`tail-primary-logs.sh`](/home/superset_ai/docker/dev/tail-primary-logs.sh)

## Important Environment Variables

| Variable | Scope | Meaning |
| --- | --- | --- |
| `OPENAI_API_KEY` | API/backend | Required for model calls |
| `OPENAI_MODEL` | API/backend | Active model name |
| `ASSISTANT_DEPLOYMENT_MODE` | API/helpers | `development` or `production` |
| `SUPERSET_PRODUCT_MCP_RUNTIME` | MCP client | `built_in_stdio` or `built_in_http` |
| `SUPERSET_BUILT_IN_MCP_URL` | MCP client | HTTP MCP endpoint when using HTTP transport |
| `SUPERSET_BUILT_IN_MCP_COMMAND` | MCP client | Optional stdio launcher override |
| `SUPERSET_BASE_URL` | backend | Internal Superset URL |
| `SUPERSET_PUBLIC_URL` | backend/UI links | Public Superset URL |
| `US15_SHARE_BASE_URL` | backend/UI links | Optional share-link override |
| `AUTH_DB_PATH` | auth service | SQLite path for users and chat history |
| `AUTH_JWT_SECRET` | auth service | JWT signing secret |
| `API_CORS_ORIGINS` | API | Explicit cross-origin allowlist |
| `NEXT_PUBLIC_API_URL` | Next.js server runtime | Upstream FastAPI base for proxying |
| `NEXT_PUBLIC_BROWSER_API_URL` | browser runtime | Optional direct FastAPI base |

## Tests

### High-signal assistant tests

- [`test_api_auth.py`](/home/superset_ai/superset-ai-assistant-mcp/tests/test_api_auth.py)
- [`test_api_chats.py`](/home/superset_ai/superset-ai-assistant-mcp/tests/test_api_chats.py)
- [`test_api_viz.py`](/home/superset_ai/superset-ai-assistant-mcp/tests/test_api_viz.py)
- [`test_api_scan.py`](/home/superset_ai/superset-ai-assistant-mcp/tests/test_api_scan.py)
- [`test_ai_agent_clarifications.py`](/home/superset_ai/superset-ai-assistant-mcp/tests/test_ai_agent_clarifications.py)
- [`test_us13_15_viz_service.py`](/home/superset_ai/superset-ai-assistant-mcp/tests/test_us13_15_viz_service.py)
- [`tests/unit/mcp_client/`](/home/superset_ai/superset-ai-assistant-mcp/tests/unit/mcp_client)
- [`tests/integration/mcp_client/test_built_in_live.py`](/home/superset_ai/superset-ai-assistant-mcp/tests/integration/mcp_client/test_built_in_live.py)

### Common commands

Assistant regression set:

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

Assistant unit tests:

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

### CI coverage

The main workflow at [`.github/workflows/ci.yml`](/home/superset_ai/.github/workflows/ci.yml)
currently runs:

- `lint`
- `assistant-unit`
- `assistant-product-flows`
- `assistant-web-build`
- `mcp-tool-inventory`
- `assistant-integration`
- `superset-mcp-extension-tests`
- `superset-mcp-core-tests`

## Debugging Guide

### First checks

1. Run `./docker/dev/check-primary-stack.sh`.
2. Open `/api/health`.
3. Confirm release metadata and `runtime=nextjs-fastapi`.
4. Confirm Superset health separately.

### If login is failing

- inspect `AUTH_JWT_SECRET`;
- inspect `AUTH_DB_PATH`;
- run [`test_api_auth.py`](/home/superset_ai/superset-ai-assistant-mcp/tests/test_api_auth.py).

### If chat is failing

- inspect `assistant-api` logs;
- confirm OpenAI and MCP config;
- run [`test_api_chats.py`](/home/superset_ai/superset-ai-assistant-mcp/tests/test_api_chats.py);
- run [`test_ai_agent_clarifications.py`](/home/superset_ai/superset-ai-assistant-mcp/tests/test_ai_agent_clarifications.py).

### If preview/recommend/share is failing

- confirm dataset/database listing works;
- confirm `SUPERSET_PUBLIC_URL` is correct;
- run [`test_api_viz.py`](/home/superset_ai/superset-ai-assistant-mcp/tests/test_api_viz.py);
- run [`test_us13_15_viz_service.py`](/home/superset_ai/superset-ai-assistant-mcp/tests/test_us13_15_viz_service.py).

### If scan is failing

- confirm Superset and MCP are healthy;
- rerun [`test_api_scan.py`](/home/superset_ai/superset-ai-assistant-mcp/tests/test_api_scan.py);
- inspect the scan report path returned by the endpoint.

### If links are wrong

- check `SUPERSET_PUBLIC_URL`;
- check `US15_SHARE_BASE_URL`;
- check whether the browser should use `NEXT_PUBLIC_BROWSER_API_URL`.

### Log locations

Structured assistant logs are described in:

- [update-and-debug.md](/home/superset_ai/docs/update-and-debug.md)

## Known Debts And Caveats

Current non-blocking debts:

- frontend typechecking around `.next/types` is not treated as the main repo-wide
  release signal;
- browser-level E2E automation is still lighter than the Python/API regression
  coverage;
- some final UX verification is still smoke-based rather than Playwright-based;
- login and auth UI text still mix English labels with a mostly Russian product
  interface;
- the share page creates a new dashboard instead of exposing existing-dashboard
  selection;
- scan remains synchronous in the current UI.

Important scope guard:

- do not treat unrelated local edits in
  `backend/us10_12_guardrails.py`,
  `tests/test_us10_12_guardrails.py`,
  or `data/auth.db` as part of the release scope unless explicitly reviewed and
  intentionally included.
