# Phased Core Cutover Plan

Status: repository prepared for phased primary-frontend cutover; do not remove Streamlit in this phase.

## Goal

Зафиксировать безопасный переходный режим, в котором:
- `Next.js + FastAPI` считается primary UI path для migrated core flows
- `Streamlit` остаётся fallback/helper-admin path только для `US2-US5`
- cutover делается как управляемый switch, а не как удаление старого пути

## Primary vs Fallback Scope

### Primary core UI

Primary path для пользователей и demo/signoff:
- `http://<host>:3001/login`
- `http://<host>:3001/register`
- `http://<host>:3001/app/chat`
- `http://<host>:3001/app/preview`
- `http://<host>:3001/app/recommend`
- `http://<host>:3001/app/share`
- `http://<host>:3001/app/scan`

Primary backend/API path:
- `http://<host>:8100/api/auth/*`
- `http://<host>:8100/api/chats/*`
- `http://<host>:8100/api/viz/*`
- `http://<host>:8100/api/scan`
- `http://<host>:8100/api/frontend/logs`

### Streamlit fallback/helper-admin scope

Streamlit path остаётся доступным на `http://<host>:8051` только для:
- `US2: Глоссарий`
- `US3: Правила маппинга`
- `US4: Подсказки запросов`
- `US5: Конструктор запроса`
- rollback window, если primary core UI нужно временно обойти

### Explicit non-goals of this phase

В эту фазу не входят:
- удаление Streamlit
- миграция `US2-US5`
- изменение backend business logic
- redesign UI

## Preconditions Before Switching The Default Entry

Перед фактическим switch primary entrypoint должны быть выполнены все пункты:

- [ ] `docs/dual-run-parity-readiness.md` актуален и не содержит blocker внутри migrated core path
- [ ] `docs/manual-smoke-checklist.md` пройден для `Next.js/FastAPI`
- [ ] `docs/demo-query-pack.md` пройден на Pagila в primary path
- [ ] `frontend.log`, `agent.log`, `mcp.log`, `artifact.log` показывают рабочую trace correlation для Next.js core flows
- [ ] Streamlit fallback sanity-check для `US2-US5` пройден
- [ ] Команда понимает, какой URL объявляется primary и какой URL остаётся fallback

## Recommended Dual-Run Launch

### 1. Superset and built-in MCP

Используйте либо split deployment, либо unified local dev stack:

```bash
cd /home/superset_ai
cp .env.dev.example .env.dev
docker compose --env-file .env.dev -f docker-compose.dev.yml up -d
```

Этот стек поднимает Superset, built-in MCP HTTP и Streamlit fallback console.

### 2. FastAPI primary backend

```bash
cd /home/superset_ai/superset-ai-assistant-mcp
.venv/bin/python -m uvicorn api.main:app --host 0.0.0.0 --port 8100
```

Проверка:

```bash
curl http://127.0.0.1:8100/api/health
```

### 3. Next.js primary frontend

В отдельном терминале:

```bash
cd /home/superset_ai/superset-ai-assistant-mcp/frontend-next
npm install
NEXT_PUBLIC_API_URL=http://127.0.0.1:8100 npm run dev -- --hostname 0.0.0.0 --port 3001
```

Для production-like signoff:

```bash
cd /home/superset_ai/superset-ai-assistant-mcp/frontend-next
npm run build
NEXT_PUBLIC_API_URL=http://127.0.0.1:8100 npm run start -- --hostname 0.0.0.0 --port 3001
```

### 4. Streamlit fallback/admin UI

Если unified compose не используется, поднимите отдельно:

```bash
cd /home/superset_ai/superset-ai-assistant-mcp
streamlit run frontend/app.py --server.port 8051 --server.address 0.0.0.0
```

## Signoff Sequence Before Actual Cutover

### A. Primary path signoff

Обязательный прогон:
1. пройти `docs/manual-smoke-checklist.md` на `Next.js/FastAPI`
2. пройти `docs/demo-query-pack.md` на `Next.js/FastAPI`
3. подтвердить frontend/backend log correlation по одному normal request, одному blocked request, preview и widget/dashboard creation

### B. Streamlit fallback sanity

Минимальный sanity-check для fallback path:
1. открыть `http://<host>:8051`
2. войти под тестовым пользователем
3. открыть `US2`, `US3`, `US4`, `US5`
4. убедиться, что страницы рендерятся без traceback
5. выполнить хотя бы по одному базовому действию в `US2` и `US5`, если эти экраны нужны текущей команде в rollout window

### C. Go / No-Go decision

Go на actual primary switch только если:
- core-flow signoff на Next.js зелёный
- fallback sanity на Streamlit зелёный
- лог-корреляция подтверждена
- команда знает rollback entrypoint

## User And Tester Expectations During Rollout

- По умолчанию для core flows используется `Next.js/FastAPI`
- Streamlit не рекламируется как основной пользовательский путь
- Если issue найден в `US2-US5`, его воспроизводят в Streamlit fallback
- Если issue найден в chat/preview/recommend/share/scan, его воспроизводят в primary Next.js path
- В баг-репортах нужно явно указывать UI path: `nextjs` или `streamlit`

## Rollback Guidance

Если после switch возникла проблема:

1. вернуть primary ссылку/entrypoint на Streamlit или временно направить пользователей на fallback URL
2. не выключать FastAPI/Next.js, пока не собраны логи и trace correlation для инцидента
3. сохранить `trace_id` / `request_id` из `frontend.log` и downstream logs
4. повторно пройти критические сценарии из `docs/manual-smoke-checklist.md`
5. фиксировать rollback как operational event, а не как сигнал к удалению нового пути

## What Still Remains On Streamlit After This Phase

После phased cutover в Streamlit по-прежнему остаются:
- `US2`
- `US3`
- `US4`
- `US5`

Это допустимо для phased primary cutover, но блокирует полную деактивацию Streamlit.

## Concrete Next Step After This Document

После этого документа следующая итерация должна быть уже про одно из двух:
1. actual switch primary entrypoint на `Next.js/FastAPI`
2. либо фиксацию одного последнего operational blocker, если он проявится на signoff
