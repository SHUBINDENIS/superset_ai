# Production-Like Primary UI Rollout Runbook

Статус: использовать для rollout текущего primary UI path:
- `Next.js` как default user entrypoint
- `FastAPI` как backend API для core flows
- `Streamlit` как fallback/helper-admin path только для `US2-US5`

Этот runbook не удаляет Streamlit и не заменяет будущий production hardening.
Он даёт оператору понятный и обратимый rollout path для серверного запуска.

## 1. Recommended Public Access Model

Рекомендуемая production-like схема доступа:

- primary UI host:
  - `https://assistant.example.com/`
- primary API path на том же host:
  - `https://assistant.example.com/api/*`
- Streamlit fallback host:
  - `https://assistant-fallback.example.com/`
- Superset public host:
  - `https://superset.example.com/`

Почему именно так:
- для пользователей есть один default primary URL
- `/api/*` остаётся на том же origin, что упрощает cookie auth
- Streamlit fallback не смешивается с primary path
- rollback можно делать операционно, не меняя код

## 2. Required Runtime Values

Перед rollout проверьте:

- `SUPERSET_PUBLIC_URL=https://superset.example.com`
- `US15_SHARE_BASE_URL=https://superset.example.com`
- `API_CORS_ORIGINS=https://assistant.example.com`
- `AUTH_JWT_SECRET` заменён на безопасное значение
- `OPENAI_API_KEY` задан
- `OPENAI_MODEL` выбран

Если primary UI публикуется под HTTPS-host, `SUPERSET_PUBLIC_URL` должен
указывать именно на публичный Superset host, иначе explore/share links будут
указывать не туда.

## 3. Bring-Up Sequence

### Option A: unified server bring-up

Используйте текущий repo-backed compose:

```bash
cd /home/superset_ai
cp .env.dev.example .env.dev
docker compose --env-file .env.dev -f docker-compose.dev.yml up -d --build
```

Поднимаются:
- `superset`
- `mcp-http`
- `assistant-api`
- `assistant-web`
- `assistant`

### Option B: split bring-up

1. Поднять Superset stack
2. Поднять FastAPI на `:8100`
3. Поднять Next.js на `:3001`
4. Поднять Streamlit fallback на `:8051`
5. Поставить reverse proxy перед ними

## 4. Health Verification

### Internal service checks

```bash
cd /home/superset_ai
docker compose --env-file .env.dev -f docker-compose.dev.yml ps
curl http://127.0.0.1:8100/api/health
curl -I http://127.0.0.1:3001/login
curl -I http://127.0.0.1:8051
curl -I http://127.0.0.1:8088/health
```

### External proxy checks

После публикации через reverse proxy:

```bash
curl -I https://assistant.example.com/login
curl -I https://assistant.example.com/api/health
curl -I https://assistant-fallback.example.com/
curl -I https://superset.example.com/health
```

Ожидаемо:
- primary `/login` отвечает `200`
- primary `/api/health` отвечает `200`
- fallback host отвечает `200`
- Superset public host отвечает `200`

## 5. Post-Deploy Smoke

После bring-up:

1. открыть primary URL
2. выполнить login
3. пройти `chat -> preview -> recommend -> share -> scan`
4. пройти `docs/demo-query-pack.md` на Pagila
5. проверить один blocked request
6. проверить trace correlation в логах
7. открыть fallback host и убедиться, что `US2-US5` доступны

## 6. Rollback Model

Rollback не требует удаления primary path.

Если rollout дал сбой:

1. объявить `assistant-fallback.example.com` временным operator/user path для
   `US2-US5` и критичных fallback use cases
2. при необходимости временно убрать primary host из пользовательской
   коммуникации
3. не выключать `assistant-api` и `assistant-web`, пока не сняты логи
4. сохранить `trace_id` / `request_id`
5. повторить critical smoke на fallback и на восстановленном primary path

## 7. What Remains Fallback-Only

Даже после rollout primary UI в Streamlit остаются только:
- `US2`
- `US3`
- `US4`
- `US5`

Это и есть допустимый phased model.

## 8. Ingress Example

Пример production-like reverse proxy находится в:

- `docs/examples/nginx-primary-ui.conf.example`

Он показывает рекомендуемую модель:
- `assistant.example.com` -> Next.js + `/api/*` на FastAPI
- `assistant-fallback.example.com` -> Streamlit
