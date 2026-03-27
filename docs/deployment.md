# Deployment

Текущая схема deployment после retirement Streamlit runtime:

- user-facing UI: `Next.js`
- primary API: `FastAPI`
- BI platform: `Superset`
- Superset access from assistant: built-in MCP service

`Streamlit` больше не является поддерживаемым runtime path.

## Current Architecture

```mermaid
flowchart TB
    user[Browser]

    subgraph host[Server / Docker host]
        nextjs[Next.js UI<br/>:3001]
        fastapi[FastAPI API<br/>:8100]
        superset[Apache Superset<br/>:8088]
        mcp[Built-in MCP HTTP or stdio]
        services[Shared assistant services<br/>backend/*]
    end

    openai[OpenAI API]

    user -->|HTTPS/HTTP| nextjs
    nextjs -->|/api/*| fastapi
    fastapi --> services
    services --> mcp
    mcp --> superset
    services --> openai
```

## Components

| Component | Path | Role |
|---|---|---|
| Next.js UI | `superset-ai-assistant-mcp/frontend-next/` | Primary user interface |
| FastAPI | `superset-ai-assistant-mcp/api/` | Auth, chats, viz, scan, frontend logs |
| Shared backend | `superset-ai-assistant-mcp/backend/` | Agent and domain services |
| Built-in MCP | `superset/superset/mcp_service/` | Superset tools / DAO / RBAC access |
| Superset | `superset/` compose stack | SQL Lab, charts, dashboards |

Retained but not exposed as UI runtime:
- `backend/us2_glossary_service.py`
- `backend/us3_mapping_rules.py`
- `backend/us4_query_assistant.py`
- `backend/us5_query_builder.py`

## Public Access Model

Recommended production-like publication:

- `https://assistant.example.com/` -> `Next.js`
- `https://assistant.example.com/api/*` -> `FastAPI`
- `https://superset.example.com/` -> `Superset`

Recommended public-host rules:
- publish one assistant host and keep API same-origin under `/api/*`
- keep `assistant-api` internal; do not expose `:8100` directly to the public internet
- leave `API_CORS_ORIGINS` unset unless you intentionally need cross-origin API access
- set `SUPERSET_PUBLIC_URL` to the public Superset host used in share/explore links
- if `US15_SHARE_BASE_URL` is set, keep it on the same origin as `SUPERSET_PUBLIC_URL`

Reverse proxy example:
- `docs/examples/nginx-primary-ui.conf.example`

## Local Ports

| Endpoint | Port | Purpose |
|---|---|---|
| `http://<host>:3001` | 3001 | Next.js UI |
| `http://<host>:8100` | 8100 | FastAPI API |
| `http://<host>:8088` | 8088 | Superset |
| `mcp-http:5008` | 5008 | Built-in MCP HTTP inside unified compose |

## Bring-Up

### Unified local dev stack

```bash
cd /home/superset_ai
cp .env.dev.example .env.dev
./docker/dev/deploy-primary-stack.sh
```

Stack services:
- `superset`
- `mcp-http`
- `assistant-api`
- `assistant-web`
- supporting `db`, `redis`, `pagila-db`, `superset-init`

Low-level compose path for debugging or manual recovery:

```bash
cd /home/superset_ai
docker compose --env-file .env.dev -f docker-compose.dev.yml up -d --build
```

### Split run

1. Superset:
```bash
cd /home/superset_ai/superset
docker compose -f docker-compose-image-tag.yml up -d db redis superset-init superset
```
2. FastAPI:
```bash
cd /home/superset_ai/superset-ai-assistant-mcp
.venv/bin/python -m uvicorn api.main:app --host 0.0.0.0 --port 8100
```
3. Next.js:
```bash
cd /home/superset_ai/superset-ai-assistant-mcp/frontend-next
npm install
NEXT_PUBLIC_API_URL=http://127.0.0.1:8100 npm run dev -- --hostname 0.0.0.0 --port 3001
```

## Health Verification

```bash
./docker/dev/validate-primary-env.sh
./docker/dev/deploy-primary-stack.sh
./docker/dev/check-primary-stack.sh
./docker/dev/tail-primary-logs.sh compose assistant-api
```

External checks after proxy publication:

```bash
curl -I https://assistant.example.com/login
curl -I https://assistant.example.com/api/health
curl -I https://superset.example.com/health
```

Final public signoff:
- `docs/public-go-live-checklist.md`

## Rollback Model

Rollback now means restoring the previous known-good `Next.js/FastAPI`
deployment, not redirecting users to a Streamlit fallback.

Recommended operator actions:

1. keep the failed deployment logs and trace identifiers
2. restore the previous compose revision, image tag, or application build
3. re-run `./docker/dev/check-primary-stack.sh`
4. re-run `docs/manual-smoke-checklist.md`
5. re-open traffic to the restored primary stack

## Operator Helpers

- `docker/dev/refresh-primary-stack.sh`
  - rebuild or restart `assistant-api` / `assistant-web`, then wait for HTTP readiness
- `docker/dev/deploy-primary-stack.sh`
  - validate env, stamp release/build metadata, rebuild the selected services, run health checks
- `docker/dev/check-primary-stack.sh`
  - one-command health verification
- `docker/dev/validate-primary-env.sh`
  - fail early on missing required env vars and show release/build metadata inputs
- `docker/dev/tail-primary-logs.sh`
  - compose log tail or structured assistant file logs

## Related Docs

- `docs/production-rollout-runbook.md`
- `docs/public-go-live-checklist.md`
- `docs/update-and-debug.md`
- `docs/manual-smoke-checklist.md`
- `docs/streamlit-retirement-summary.md`
- `docs/dual-run-parity-readiness.md` (historical archive)
- `docs/phased-cutover-plan.md` (historical archive)
- `docs/phased-cutover-signoff.md` (historical archive)
