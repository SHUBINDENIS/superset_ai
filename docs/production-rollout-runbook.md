# Production-Like Rollout Runbook

Используйте этот runbook для rollout текущего поддерживаемого stack:

- `Next.js` as default user entrypoint
- `FastAPI` as primary API
- `Superset` on its own host

`Streamlit` fallback path removed from the supported runtime model.

## 1. Recommended Public URLs

- `https://assistant.example.com/` -> `Next.js`
- `https://assistant.example.com/api/*` -> `FastAPI`
- `https://superset.example.com/` -> `Superset`

## 2. Required Environment

Проверьте перед rollout:

- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `SUPERSET_PUBLIC_URL=https://superset.example.com`
- `US15_SHARE_BASE_URL=https://superset.example.com`
- `API_CORS_ORIGINS=https://assistant.example.com`
- `AUTH_JWT_SECRET`

## 3. Bring-Up Options

### Option A: unified compose

```bash
cd /home/superset_ai
cp .env.dev.example .env.dev
docker compose --env-file .env.dev -f docker-compose.dev.yml up -d --build
```

### Option B: split services

1. start Superset
2. start `FastAPI` on `:8100`
3. start `Next.js` on `:3001`
4. publish both through a reverse proxy

## 4. Health Checks

Internal:

```bash
./docker/dev/check-primary-stack.sh
./docker/dev/tail-primary-logs.sh compose assistant-api
```

External:

```bash
curl -I https://assistant.example.com/login
curl -I https://assistant.example.com/api/health
curl -I https://superset.example.com/health
```

## 5. Post-Deploy Smoke

1. run `./docker/dev/refresh-primary-stack.sh`
2. run `./docker/dev/check-primary-stack.sh`
3. open `https://assistant.example.com/login`
4. login or register
5. run `chat -> preview -> recommend -> share -> scan`
6. run `docs/demo-query-pack.md`
7. confirm trace correlation in logs via `./docker/dev/tail-primary-logs.sh structured`

## 6. Rollback

There is no separate runtime fallback host anymore. Rollback is deployment
rollback:

1. stop exposing the faulty release
2. restore the previous known-good assistant-web / assistant-api deployment
3. keep traces and logs for incident analysis
4. rerun `./docker/dev/check-primary-stack.sh`
5. rerun `docs/manual-smoke-checklist.md`

## 7. Proxy Reference

See:
- `docs/examples/nginx-primary-ui.conf.example`

## 8. Day-2 Update And Debug

See:
- `docs/update-and-debug.md`

## 9. Historical References

For the previous phased-cutover evidence only:
- `docs/dual-run-parity-readiness.md`
- `docs/phased-cutover-plan.md`
- `docs/phased-cutover-signoff.md`
