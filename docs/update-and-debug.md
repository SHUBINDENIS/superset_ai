# Update And Debug Guide

Используйте этот документ как day-2 operator/developer guide для единственного
поддерживаемого stack: `Next.js + FastAPI`.

## Supported Runtime

- UI: `assistant-web` / `frontend-next`
- API: `assistant-api` / `api`
- Superset: отдельный Superset stack

Historical only:
- `docs/dual-run-parity-readiness.md`
- `docs/phased-cutover-plan.md`
- `docs/phased-cutover-signoff.md`

Backend-only for future work:
- `backend/us2_glossary_service.py`
- `backend/us3_mapping_rules.py`
- `backend/us4_query_assistant.py`
- `backend/us5_query_builder.py`

## Default Local Run

```bash
cd /home/superset_ai
cp .env.dev.example .env.dev
docker compose --env-file .env.dev -f docker-compose.dev.yml up -d --build
```

## Fastest Health Check

```bash
cd /home/superset_ai
./docker/dev/check-primary-stack.sh
```

Если нужны non-default порты:

```bash
cd /home/superset_ai
DEV_API_PORT=18100 DEV_NEXTJS_PORT=13001 DEV_SUPERSET_PORT=18088 ./docker/dev/check-primary-stack.sh
```

## Rebuild Only What Changed

FastAPI/backend change:

```bash
cd /home/superset_ai
docker compose --env-file .env.dev -f docker-compose.dev.yml up -d --build assistant-api
```

Next.js/frontend change:

```bash
cd /home/superset_ai
docker compose --env-file .env.dev -f docker-compose.dev.yml up -d --build assistant-web
```

## Logs And Debug Flow

Primary logs:

```bash
cd /home/superset_ai
docker compose --env-file .env.dev -f docker-compose.dev.yml logs -f assistant-api
docker compose --env-file .env.dev -f docker-compose.dev.yml logs -f assistant-web
docker compose --env-file .env.dev -f docker-compose.dev.yml logs -f superset
```

Primary health/debug sequence:

1. `docker compose ... ps`
2. `./docker/dev/check-primary-stack.sh`
3. If API issue: inspect `assistant-api` logs first
4. If UI issue: inspect `assistant-web` logs and rerun `npm run build`
5. If chart/share/scan issue: confirm `SUPERSET_PUBLIC_URL` and Superset health

## Minimal Smoke Path

1. Open `/login`
2. Register or login
3. Run `chat -> preview -> recommend -> share -> scan`
4. Run `docs/demo-query-pack.md`

## Before Updating On A Server

1. pull the new revision
2. review `README.md` and `docs/production-rollout-runbook.md`
3. rebuild `assistant-api` and `assistant-web`
4. run `./docker/dev/check-primary-stack.sh`
5. rerun `docs/manual-smoke-checklist.md`
