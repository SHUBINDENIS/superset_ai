# Superset AI Assistant (прототип)

Коротко: по умолчанию primary core UI path теперь использует
`Next.js + FastAPI`, а `Streamlit` остаётся только fallback/helper-admin UI для
`US2-US5` и rollback-сценариев.

## Что нужно
- Python 3.10+
- Ключ OpenAI (`OPENAI_API_KEY`)
- Запущенный Superset с доступным built-in MCP runtime (`superset.mcp_service`)

Текущая модель запуска разделена:
- Superset поднимается отдельно через `superset/docker-compose-image-tag.yml`
- этот каталог запускает только ассистентский UI/backend слой
- phased cutover scope сейчас такой:
  - primary core UI: `FastAPI + frontend-next`
  - Streamlit fallback/admin UI: `frontend/app.py` для `US2-US5`

Также в корне репозитория есть optional unified local dev stack:
- `docker-compose.dev.yml`
- он поднимает Superset + built-in MCP HTTP + assistant одной командой
- он не заменяет split deployment, а лишь упрощает локальный dev/demo запуск
- в этой фазе unified stack поднимает и primary `FastAPI + Next.js`, и Streamlit fallback console

## Как запустить primary core UI
Дефолтный repo-backed запуск primary path:

```bash
cd /home/superset_ai
cp .env.dev.example .env.dev
docker compose --env-file .env.dev -f docker-compose.dev.yml up -d --build
```

После этого по умолчанию доступны:
- primary Next.js UI: `http://localhost:3001/login`
- primary FastAPI health: `http://localhost:8100/api/health`
- Streamlit fallback/admin UI: `http://localhost:8051`

Ниже оставлен ручной split-run сценарий, если unified compose не используется.

1. Скопируйте `.env.example` в `.env` и заполните:
   - `OPENAI_API_KEY` — ключ OpenAI
   - `OPENAI_MODEL` — рекомендуемо `gpt-5.4-mini` для снижения риска 429 TPM
   - `SUPERSET_PRODUCT_MCP_RUNTIME` — `built_in_stdio` по умолчанию или `built_in_http`, если built-in MCP опубликован по HTTP
   - `SUPERSET_BUILT_IN_MCP_COMMAND`, `SUPERSET_BUILT_IN_MCP_ARGS` — опциональный launcher для `built_in_stdio`, если текущая среда не умеет запускать `python -m superset.mcp_service` напрямую
   - `SUPERSET_BUILT_IN_MCP_URL` — адрес built-in MCP только для режима `built_in_http`
   - `SUPERSET_BASE_URL`, `SUPERSET_PUBLIC_URL` — базовый URL Superset для всех ссылок (например, `http://103.54.18.91:8088`)
    - `AUTH_DB_PATH`, `AUTH_JWT_SECRET`, `AUTH_JWT_TTL_HOURS` — параметры локальной авторизации (логин/пароль + JWT)
   - `AUTH_PASSWORD_MIN_LENGTH`, `AUTH_HISTORY_MAX_MESSAGES` — политика паролей и лимит загружаемой истории чата
   - `AI_AGENT_MAX_STEPS`, `AI_AGENT_RECURSION_LIMIT` — лимиты шагов/рекурсии агента
   - `AI_AGENT_HISTORY_*`, `AI_AGENT_CONTEXT_CHARS`, `AI_AGENT_RATE_LIMIT_COOLDOWN_SECONDS` — ограничения на размер контекста и анти-спам cooldown после 429
2. Создайте `.venv` и установите зависимости:
   ```bash
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   ```
3. Запустите FastAPI backend:
   ```bash
   cd /home/superset_ai/superset-ai-assistant-mcp
   .venv/bin/python -m uvicorn api.main:app --host 0.0.0.0 --port 8100
   ```
4. В отдельном терминале запустите Next.js frontend:
   ```bash
   cd /home/superset_ai/superset-ai-assistant-mcp/frontend-next
   npm install
   NEXT_PUBLIC_API_URL=http://127.0.0.1:8100 npm run dev -- --hostname 0.0.0.0 --port 3001
   ```
5. Откройте `http://localhost:3001/login`:
   - сначала появится экран `Вход / Регистрация` (логин+пароль, без SMS/2FA),
   - после авторизации откроется основной интерфейс ассистента на `http://localhost:3001/app/chat`.
6. Production-like локальный старт для cutover signoff:
   ```bash
   cd /home/superset_ai/superset-ai-assistant-mcp/frontend-next
   npm run build
   NEXT_PUBLIC_API_URL=http://127.0.0.1:8100 npm run start -- --hostname 0.0.0.0 --port 3001
   ```

## Streamlit fallback/admin UI

Поднимайте Streamlit отдельно только если нужно проверить или использовать
оставшиеся Streamlit-only helper/admin окна:
- `US2: Глоссарий`
- `US3: Правила маппинга`
- `US4: Подсказки запросов`
- `US5: Конструктор запроса`

Запуск:
```bash
cd /home/superset_ai/superset-ai-assistant-mcp
streamlit run frontend/app.py --server.port 8051 --server.address 0.0.0.0
```

Открыть: `http://localhost:8051`

## Docker-режим ассистента

Сборка выполняется из корня репозитория:

```bash
cd /home/superset_ai
docker build -t ai_superset -f superset-ai-assistant-mcp/Dockerfile .
docker run --rm -p 8051:8051 --env-file superset-ai-assistant-mcp/.env ai_superset
```

Проверенный факт:
- образ собирается и поднимает Streamlit fallback UI на `:8051`
- в образ попадают только runtime-модули (`backend/`, `frontend/`, `.streamlit/`, `start_assistant_stack.sh`), без тестов, локальных БД и логов

Важно:
- этот образ не поднимает Superset
- этот образ пока не поднимает Next.js primary core UI
- этот образ не содержит код `superset.mcp_service`
- для контейнерного запуска ассистента обычно нужен либо `built_in_http`, либо явный `SUPERSET_BUILT_IN_MCP_COMMAND`

## Unified local dev stack

Для удобного локального dev/demo запуска из корня репозитория:

```bash
cd /home/superset_ai
cp .env.dev.example .env.dev
docker compose --env-file .env.dev -f docker-compose.dev.yml up -d
```

Этот сценарий:
- считается дефолтным repo-backed локальным запуском primary path
- поднимает `superset`, `mcp-http`, `assistant-api`, `assistant-web`, `assistant`, `db`, `pagila-db`, `redis`, `superset-init`
- подключает ассистент к built-in MCP по HTTP
- автоматически регистрирует `Pagila Demo (PostgreSQL)` и ключевые datasets для demo-сценариев
- поднимает Streamlit fallback/admin console на `:8051`
- поднимает primary FastAPI на `:8100`
- поднимает primary Next.js UI на `:3001`

Если порты заняты локально, переопределите в `.env.dev`:
- `DEV_SUPERSET_PORT`
- `DEV_API_PORT`
- `DEV_NEXTJS_PORT`
- `DEV_ASSISTANT_PORT`
- `DEV_PAGILA_PORT`

Рекомендуемый demo runbook и набор бизнес-вопросов:
- `docs/demo-pagila.md`
- `docs/manual-smoke-checklist.md`
- `docs/demo-query-pack.md`
- `docs/dual-run-parity-readiness.md`
- `docs/phased-cutover-plan.md`

## Primary core UI: Next.js + FastAPI

Текущий primary UI path живёт в `frontend-next/` и `api/`. В текущей фазе
там уже перенесены:
- auth shell с cookie-based FastAPI auth,
- `/app/chat` с multi-chat sidebar,
- отправка сообщений через FastAPI `/api/chats/...`,
- `/app/preview` для preview и объяснения полей,
- `/app/recommend` для рекомендаций по типу графика,
- `/app/share` для создания chart/dashboard и открытия ссылок,
- `/app/scan` для schema scan и чтения итогового отчёта.

Локальный запуск:

```bash
cd /home/superset_ai/superset-ai-assistant-mcp
.venv/bin/python -m uvicorn api.main:app --host 0.0.0.0 --port 8100
```

В отдельном терминале:

```bash
cd /home/superset_ai/superset-ai-assistant-mcp/frontend-next
npm install
NEXT_PUBLIC_API_URL=http://127.0.0.1:8100 npm run dev -- --hostname 0.0.0.0 --port 3001
```

Открыть:
- `http://127.0.0.1:3001/login`
- после входа основной маршрут: `http://127.0.0.1:3001/app/chat`
- demo-critical аналитические страницы:
  - `http://127.0.0.1:3001/app/preview`
  - `http://127.0.0.1:3001/app/recommend`
  - `http://127.0.0.1:3001/app/share`
  - `http://127.0.0.1:3001/app/scan`

Важно:
- Next.js/FastAPI теперь считается primary core UI path для migrated routes;
- Streamlit UI остаётся рабочим fallback/admin path и не удаляется этим запуском;
- `chat/preview/recommend/share/scan` уже доступны и в Next.js;
- core Next.js routes теперь тоже пишут structured frontend events в `data/logs/frontend.log` через FastAPI `/api/frontend/logs`;
- для correlation Next.js прокидывает `x-trace-id` / `x-request-id` в chat/viz/scan API-вызовы, поэтому `frontend.log` можно сопоставлять с `agent.log`, `mcp.log` и `artifact.log`;
- Streamlit US1 тоже остаётся рабочим и не отключается этим запуском.
- helper/admin окна `US2-US5` пока остаются Streamlit-only; phased cutover scope зафиксирован в `docs/phased-cutover-plan.md`.

Полезные runbook’и:
- `docs/dual-run-parity-readiness.md`
- `docs/manual-smoke-checklist.md`
- `docs/demo-query-pack.md`
- `docs/phased-cutover-plan.md`
- `docs/phased-cutover-signoff.md`

## Как пользоваться Streamlit fallback path
- В `sidebar` есть кнопки навигации по окнам: `Чат`, `US1`, `US2`, `US3`, `US4`, `US5`, `US13`, `US14`, `US15`.
- Кнопка `Выход` завершает пользовательскую сессию в UI (аккаунт и история не удаляются).
- Каждый US-экран открывается отдельно в основной области, чтобы не перегружать один sidebar.
- Вводите текстовые запросы в чат — Streamlit обрабатывает их через встроенный backend-agent путь и built-in Superset MCP.
- История чата сохраняется по пользователю и подгружается после повторного входа.
- После успешного входа логин сохраняется в стандартной session-cookie браузера: при повторном открытии ссылки в том же браузерном сеансе повторный вход не требуется.
- Если нет ответа, проверьте, что built-in MCP runtime запускается и переменные окружения заданы верно.
- В окне `US1` есть кнопка `Запустить US1-сканирование`: она строит отчёт по схемам, таблицам, профилю и связям через built-in MCP (`mcp_ext.list_databases` + `execute_sql`).
- Если `postgres_databases=0`, откройте блок `Диагностика баз данных (US1)` — там будут `backend_hint` и причины фильтрации.
- В окне `US2: Глоссарий (CRUD + Mapping)`:
  - создание/редактирование/удаление терминов,
  - примеры для терминов,
  - привязки терминов к `database/dataset/schema/table/column/metric`.
- В окне `US3: Правила маппинга (term -> column/metric)`:
  - CRUD правил (keyword/regex, priority, enable/disable),
  - применение правил к текущему запросу перед инференсом,
  - логи срабатываний правил по сессии.
- В окне `US4: Подсказки запросов`:
  - каталог из 10+ примеров NL-запросов на русском с описанием,
  - кнопка "Использовать этот пример" для быстрого старта запроса,
  - автодополнение сущностей из US2-глоссария (термины + mapping), с fallback на доменные теги примеров.
- В окне `US5: Конструктор запроса по критериям`:
  - интерактивные уточнения по обязательным полям (таблица/датасет, метрика, период),
  - сбор общего корректного запроса по нескольким критериям,
  - журнал выбранных значений по сессии (сохранение, просмотр, очистка),
  - строгая фиксация datasource: если указана таблица, chart не должен создаваться на другой таблице.
- В окне `US13: Предпросмотр`:
  - выполнение SQL в Superset SQL Lab (sync),
  - первые N строк результата,
  - авто-профиль колонок: типы, единицы и объяснение полей.
- В окне `US14: Рекомендации`:
  - авто-рекомендация типа графика по типам/кардинальности,
  - применение типа графика в 1 клик в US5/US15.
- В окне `US15: Шеринг`:
  - создание chart и dashboard через Superset API,
  - привязка chart к dashboard как виджета,
  - выдача share-ссылок на dashboard и chart.
- Для US10-US12 добавлены guardrails в чате:
  - US10: блок prompt-injection и нерелевантных запросов (например, математика вне сервиса),
  - US10: read-only SQL политика (DDL/DML запрещены),
  - US11: роль + ограничение по таблицам и PII,
  - US12: квоты (rate-limit) и ограничение сложности запроса.

## Структура
- `api/` — FastAPI auth/chat/viz/scan/frontend-logs routes для primary core UI
- `frontend-next/` — Next.js primary core UI
- `frontend/app.py` — entrypoint Streamlit UI
- `frontend/state.py` — единые state defaults и reset/auth helpers
- `frontend/ui_helpers.py` — общие UI helpers и theme
- `backend/ai_agent.py` — обертка LangChain + mcp-use
- `backend/us1_schema_profiler.py` — US1 scanner (schema/profile/relations)
- `backend/us2_glossary_service.py` — US2 glossary service (CRUD + mappings)
- `backend/us3_mapping_rules.py` — US3 mapping rules + match logs
- `backend/us4_query_assistant.py` — US4 examples + entity autocomplete
- `backend/us5_query_builder.py` — US5 criteria builder + journal
- `backend/us10_12_guardrails.py` — US10-US12 policy guardrails
- `backend/us13_15_viz_service.py` — US13-US15 preview/recommend/share service
- `.env.example` — образец настроек

## Быстрые подсказки
- Ошибка подключения: проверьте `SUPERSET_PRODUCT_MCP_RUNTIME` и запуск built-in MCP.
- Для `built_in_stdio`:
  - если `python -m superset.mcp_service` доступен в текущей среде, дополнительных переменных не нужно,
  - если нет, задайте `SUPERSET_BUILT_IN_MCP_COMMAND` и при необходимости `SUPERSET_BUILT_IN_MCP_ARGS`.
- Для `built_in_http`:
  - задайте `SUPERSET_BUILT_IN_MCP_URL`,
  - проверьте, что endpoint built-in MCP доступен из среды ассистента.
- Для отдельного assistant Docker image:
  - не рассчитывайте на `built_in_stdio` без явного launcher,
  - по умолчанию безопаснее документировать `built_in_http` или явно заданный stdio launcher.
- Ошибка про ключ: убедитесь, что `OPENAI_API_KEY` есть в `.env`.
- Ошибка `GRAPH_RECURSION_LIMIT`: увеличьте `AI_AGENT_MAX_STEPS` и `AI_AGENT_RECURSION_LIMIT` в `.env`.
- Ошибка `429 rate_limit_exceeded`: используйте `OPENAI_MODEL=gpt-5.4-mini`, уменьшите контекст (`AI_AGENT_HISTORY_*`, `AI_AGENT_CONTEXT_CHARS`) и повторите запрос после cooldown.
- Ошибка `Запрос заблокирован политикой безопасности US10-US12`: уточните формулировку в рамках Superset/SQL и используйте разрешённые таблицы/метрики.
