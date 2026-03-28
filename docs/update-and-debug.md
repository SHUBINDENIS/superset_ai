# Update And Debug Guide

Используйте этот документ как основной day-2 operator/developer guide для
единственного поддерживаемого runtime stack: `Next.js + FastAPI`.

## Final Supported Scope

Fully supported now:
- `assistant-web` / `frontend-next`
- `assistant-api` / `api`
- `superset` + built-in MCP path
- current product UI flows: `login`, `chat`, `preview`, `recommend`, `share`, `scan`

Backend-only for future work:
- `backend/us2_glossary_service.py`
- `backend/us3_mapping_rules.py`
- `backend/us4_query_assistant.py`
- `backend/us5_query_builder.py`

Historical/archive only:
- `docs/dual-run-parity-readiness.md`
- `docs/phased-cutover-plan.md`
- `docs/phased-cutover-signoff.md`
- `docs/streamlit-retirement-summary.md`

## One Primary Local/Server Path

Deployment-mode contract:
- `ASSISTANT_DEPLOYMENT_MODE=development`
  - local/direct-port workflow
  - weak placeholder auth secrets stay warning-only
  - localhost `SUPERSET_PUBLIC_URL` and localhost CORS origins are allowed
- `ASSISTANT_DEPLOYMENT_MODE=production`
  - public/proxy-facing workflow
  - placeholder or short `AUTH_JWT_SECRET` becomes a hard failure
  - localhost/loopback `SUPERSET_PUBLIC_URL`, `US15_SHARE_BASE_URL`, or `API_CORS_ORIGINS` become hard failures
  - if `API_CORS_ORIGINS` is unset, same-origin proxy deployment is assumed

Default local or production-like compose run:

```bash
cd /home/superset_ai
cp .env.dev.example .env.dev
./docker/dev/deploy-primary-stack.sh
```

Primary endpoints:
- UI: `http://<host>:3001/login`
- API: `http://<host>:8100/api/health`
- Superset: `http://<host>:8088`

Low-level compose path for debugging only:

```bash
cd /home/superset_ai
docker compose --env-file .env.dev -f docker-compose.dev.yml up -d --build
```

## Operator Helpers

Primary health:

```bash
cd /home/superset_ai
./docker/dev/check-primary-stack.sh
```

Standard deploy/update path:

```bash
cd /home/superset_ai
./docker/dev/deploy-primary-stack.sh
```

Update or rebuild primary services:

```bash
cd /home/superset_ai
./docker/dev/refresh-primary-stack.sh
./docker/dev/refresh-primary-stack.sh rebuild assistant-api
./docker/dev/refresh-primary-stack.sh rebuild assistant-web
```

`refresh-primary-stack.sh` waits for touched HTTP services to answer before it exits.

Restart primary services without rebuild:

```bash
cd /home/superset_ai
./docker/dev/refresh-primary-stack.sh restart
```

Tail logs:

```bash
cd /home/superset_ai
./docker/dev/tail-primary-logs.sh
./docker/dev/tail-primary-logs.sh compose assistant-api
./docker/dev/tail-primary-logs.sh structured
```

Если нужны non-default порты для health helper:

```bash
cd /home/superset_ai
DEV_API_PORT=18100 DEV_NEXTJS_PORT=13001 DEV_SUPERSET_PORT=18088 ./docker/dev/check-primary-stack.sh
```

## Required Environment Checklist

Minimum variables before local smoke or server rollout:
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `SUPERSET_PUBLIC_URL`
- `AUTH_JWT_SECRET`
- `ASSISTANT_DEPLOYMENT_MODE`

Only when calling FastAPI directly outside the Next.js origin:
- `API_CORS_ORIGINS`

Optional log override:
- `ASSISTANT_LOG_DIR`

Optional share-link override:
- `US15_SHARE_BASE_URL`
  - if omitted, runtime falls back to `SUPERSET_PUBLIC_URL`

Optional release visibility:
- `ASSISTANT_RELEASE_VERSION`
- `ASSISTANT_BUILD_SHA`
- `ASSISTANT_BUILD_TIMESTAMP`

Preflight validation:

```bash
cd /home/superset_ai
./docker/dev/validate-primary-env.sh
```

`deploy-primary-stack.sh` runs the validation automatically before rebuild.

## Minimal Post-Update Verification Path

1. `./docker/dev/deploy-primary-stack.sh`
2. confirm release/build metadata in `/api/health`
3. Open `/login`
4. Run `chat -> preview -> recommend -> share -> scan`
5. Run `docs/demo-query-pack.md`

## Logs And Debug Flow

Compose logs:
- `./docker/dev/tail-primary-logs.sh`
- `./docker/dev/tail-primary-logs.sh compose assistant-api`

Structured assistant logs:
- `./docker/dev/tail-primary-logs.sh structured`

Structured log locations:
- direct local run default: `superset-ai-assistant-mcp/data/logs/`
- compose default: `/app/superset-ai-assistant-mcp/data/logs/` inside `assistant-api`
- optional override: `ASSISTANT_LOG_DIR`

What to check first:
1. `./docker/dev/check-primary-stack.sh`
2. If API issue: `./docker/dev/tail-primary-logs.sh compose assistant-api`
3. If UI issue: `./docker/dev/tail-primary-logs.sh compose assistant-web`
4. If chart/share/scan issue: check Superset health and `SUPERSET_PUBLIC_URL`
5. If correlation/logging issue: `./docker/dev/tail-primary-logs.sh structured`

## Rollback Guidance

Rollback is deployment rollback of the same single stack:

1. move the repo or deployment selection back to the previous known-good revision
2. rerun `./docker/dev/deploy-primary-stack.sh`
3. rerun `./docker/dev/check-primary-stack.sh`
4. rerun `docs/manual-smoke-checklist.md`
5. inspect compose + structured logs before reopening traffic

## Before Updating On A Server

1. pull the new revision
2. review `README.md` and `docs/production-rollout-runbook.md`
3. run `./docker/dev/deploy-primary-stack.sh`
4. run `./docker/dev/check-primary-stack.sh`
5. rerun `docs/manual-smoke-checklist.md`
