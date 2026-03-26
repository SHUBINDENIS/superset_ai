# Superset AI: NL→SQL→Chart

Проект для MVP/MUP этапов по курсу веб-разработки: AI-ассистент над Apache Superset, который помогает формулировать аналитические запросы на естественном языке, строить SQL, делать предпросмотр, рекомендовать тип визуализации и создавать виджеты/дашборды.

## Открытый репозиторий
- Исходный код размещён в открытом репозитории GitHub: `https://github.com/SHUBINDENIS/superset_ai`.
- Также может быть размещён в GitLab при необходимости (критерий допускает GitHub/GitLab).

## Что уже реализовано
- Базовая платформа: Apache Superset в Docker.
- MCP-интеграция: built-in Superset MCP service (`superset/superset/mcp_service`) для программного доступа к Superset tools / DAO / RBAC.
- Primary core UI path: `Next.js + FastAPI` стек в `superset-ai-assistant-mcp/frontend-next` и `superset-ai-assistant-mcp/api` для auth, chat, preview, recommend, share и schema scan.
- Fallback/helper-admin UI path: `Streamlit`-приложение `superset-ai-assistant-mcp/frontend` для US2-US5 и rollback-сценариев во время phased cutover.
- Реализованы продуктовые окна и сценарии для US1–US5, US10–US15 (скан схем, глоссарий, маппинг, подсказки, конструктор, guardrails, preview, рекомендации графиков, создание share-ссылок).
- Защитные механизмы US10–US12: anti prompt-injection, ограничение нерелевантных запросов, read-only/безопасность SQL, базовые квоты.

## Структура репозитория
Структура проекта разделена на модули и пакеты, навигация по коду организована по подсистемам:

- `superset/`
  - инфраструктура Apache Superset (docker-compose, конфиги, upstream-код).
- `superset-ai-assistant-mcp/`
  - основной продукт (frontend + backend).
  - `api/`: FastAPI auth/chat/viz/scan/logging endpoints для primary core UI path.
  - `frontend-next/`: Next.js primary core UI для migrated routes.
  - `frontend/`: UI Streamlit.
    - `app.py` — тонкий entrypoint Streamlit.
    - `state.py` — единый источник дефолтов и reset/auth state helpers.
    - `ui_helpers.py` — общие UI helpers и theme.
  - `backend/`: доменные сервисы по user story.
    - `us1_schema_profiler.py`
    - `us2_glossary_service.py`
    - `us3_mapping_rules.py`
    - `us4_query_assistant.py`
    - `us5_query_builder.py`
    - `us10_12_guardrails.py`
    - `us13_15_viz_service.py`
    - `ai_agent.py`
  - `tests/`: unit-тесты ключевых модулей.
  - `requirements.txt`, `Dockerfile`, `.env.example`.
- `.github/workflows/ci.yml`
  - CI workflow: автоматический запуск линтеров.
- `docker-compose.dev.yml`
  - опциональный unified local dev stack для Superset + built-in MCP HTTP + assistant.
- `docker/dev/`
  - dev-only helper scripts и overrides для unified compose stack.
- `.env.dev.example`
  - пример переменных окружения для `docker-compose.dev.yml`.
- `ruff.toml`
  - конфигурация линтера Ruff.
- `docs/phased-cutover-plan.md`
  - phased cutover plan: primary core UI, Streamlit fallback scope, dual-run validation и rollback.
- `docs/mcp-migration/`
  - исторические материалы миграции и parity-отчёты по удалённому legacy MCP runtime.

## Архитектура (кратко)
- Primary core path для текущего phased cutover: `Next.js UI -> FastAPI -> backend services / AI Agent -> built-in Superset MCP service`.
- Streamlit остаётся отдельным fallback/helper-admin UI path для `US2-US5` и rollback-сценариев.
- Оба UI path используют один и тот же built-in Superset MCP service и shared backend-модули.
- Superset выполняет SQL, строит графики и дашборды в подключённых источниках данных.

Подробная схема развёртывания (Deployment): `docs/deployment.md`.

## Требования к окружению
- Docker + Docker Compose
- Python 3.10+ (для локального запуска сервисов)
- OpenAI API key (для AI-части)

## Поддерживаемая модель запуска

Текущая поддерживаемая схема развёртывания разделена на две части:

- `superset/docker-compose-image-tag.yml` поднимает стек Apache Superset.
- `superset-ai-assistant-mcp/` запускается отдельно:
  - primary core path: `FastAPI + Next.js`
  - fallback/admin path: `streamlit run frontend/app.py` или отдельный Docker-образ

Ассистент не входит в текущий `docker compose` стек Superset.
`superset-worker` и `superset-worker-beat` больше не считаются обязательной частью базового проекта; они оставлены как opt-in профиль для фоновых задач Superset.

Дополнительно есть **опциональный** unified local dev stack:

- файл: `docker-compose.dev.yml`
- цель: локальный демо/дев-контур одной командой
- модель MCP: `built_in_http`
- baseline split deployment при этом остаётся основной и поддерживаемой схемой

## Быстрый запуск (рекомендуемый порядок)
Сначала запускается Superset, затем primary core UI (`FastAPI + Next.js`).
Streamlit поднимается отдельно только как fallback/helper-admin path.

### 1) Поднять Apache Superset
```bash
cd /home/superset_ai/superset
docker compose -f docker-compose-image-tag.yml up -d db redis superset-init superset
```

Проверка:
```bash
docker compose -f docker-compose-image-tag.yml config --services
docker compose -f docker-compose-image-tag.yml ps
```

Обычно UI Superset доступен на `http://localhost:8088` (или на вашем внешнем IP/домене).

Если нужны фоновые функции Superset, которые зависят от Celery, их можно включить отдельно:
```bash
docker compose -f docker-compose-image-tag.yml --profile async up -d superset-worker superset-worker-beat
```

### 2) Настроить переменные окружения ассистента
```bash
cd /home/superset_ai/superset-ai-assistant-mcp
cp .env.example .env
```

Минимально проверьте в `.env`:
- `OPENAI_API_KEY=...`
- `OPENAI_MODEL=gpt-5.4-mini` (рекомендуется для уменьшения 429)
- `SUPERSET_PRODUCT_MCP_RUNTIME=...`
- для `built_in_stdio`:
  - либо текущая среда ассистента умеет запускать `python -m superset.mcp_service`,
  - либо заданы `SUPERSET_BUILT_IN_MCP_COMMAND=...` и при необходимости `SUPERSET_BUILT_IN_MCP_ARGS=...`
- для отдельного assistant Docker image обычно проще использовать `built_in_http` с `SUPERSET_BUILT_IN_MCP_URL=...`, потому что сам image не содержит исходники Superset
- `SUPERSET_BASE_URL=http://<host>:8088`
- `SUPERSET_PUBLIC_URL=http://<host>:8088`
- `AUTH_DB_PATH=/home/superset_ai/superset-ai-assistant-mcp/data/auth.db`
- `AUTH_JWT_SECRET=...` (обязательно поменять с дефолтного значения)
- `AUTH_JWT_TTL_HOURS=12`
- `AUTH_PASSWORD_MIN_LENGTH=8`
- `AUTH_HISTORY_MAX_MESSAGES=500`

Если `.venv` ещё не создана:
```bash
cd /home/superset_ai/superset-ai-assistant-mcp
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### 3) Запустить primary FastAPI backend
```bash
cd /home/superset_ai/superset-ai-assistant-mcp
.venv/bin/python -m uvicorn api.main:app --host 0.0.0.0 --port 8100
```

Проверка:
```bash
curl http://127.0.0.1:8100/api/health
```

### 4) Запустить primary Next.js frontend
В отдельном терминале:

```bash
cd /home/superset_ai/superset-ai-assistant-mcp/frontend-next
npm install
NEXT_PUBLIC_API_URL=http://127.0.0.1:8100 npm run dev -- --hostname 0.0.0.0 --port 3001
```

Проверка:
```bash
curl -I http://127.0.0.1:3001/login
```

Основные маршруты primary core UI:
- `http://localhost:3001/login`
- `http://localhost:3001/app/chat`
- `http://localhost:3001/app/preview`
- `http://localhost:3001/app/recommend`
- `http://localhost:3001/app/share`
- `http://localhost:3001/app/scan`

### 5) Запустить Streamlit fallback/admin UI
Только если нужно проверить `US2-US5` или держать fallback path доступным:

```bash
cd /home/superset_ai/superset-ai-assistant-mcp
pip install -r requirements.txt
streamlit run frontend/app.py --server.port 8051 --server.address 0.0.0.0
```

Открыть: `http://localhost:8051`.

### 6) Запустить ассистент отдельным Docker-образом
Сборку нужно делать из корня репозитория:

```bash
cd /home/superset_ai
docker build -t ai_superset -f superset-ai-assistant-mcp/Dockerfile .
docker run --rm -p 8051:8051 --env-file superset-ai-assistant-mcp/.env ai_superset
```

Важно:
- текущий assistant Docker image по-прежнему поднимает Streamlit fallback/admin path на `:8051`
- он не поднимает Next.js primary UI
- в image копируются только runtime-файлы ассистента, без тестов, локальных БД и логов
- он не поднимает Superset и не включает в себя код `superset.mcp_service`
- для рабочего MCP-подключения внутри такого контейнера нужен либо доступный `built_in_http` endpoint, либо явно заданный stdio launcher

### 7) Опциональный unified local dev stack
Этот сценарий добавлен для локальной разработки и демо и теперь является самым
коротким repo-backed способом поднять phased primary UI switch в dual-run.
Split deployment при этом остаётся основной поддерживаемой моделью.

Что поднимает `docker-compose.dev.yml`:
- `db`
- `redis`
- `superset-init`
- `superset`
- `mcp-http`
- `assistant-api` (primary FastAPI)
- `assistant-web` (primary Next.js)
- `assistant`
- опционально: `superset-worker`, `superset-worker-beat` через профиль `async`

Как запустить:
```bash
cd /home/superset_ai
cp .env.dev.example .env.dev
docker compose --env-file .env.dev -f docker-compose.dev.yml up -d
```

Проверка:
```bash
docker compose --env-file .env.dev -f docker-compose.dev.yml ps
curl -I http://127.0.0.1:8088
curl http://127.0.0.1:${DEV_API_PORT:-8100}/api/health
curl -I http://127.0.0.1:${DEV_NEXTJS_PORT:-3001}/login
curl -I http://127.0.0.1:8051
```

Что реально проверено:
- `docker compose -f docker-compose.dev.yml config`
- unified stack стартует в контейнерах
- Superset отвечает на HTTP
- primary FastAPI отвечает на `/api/health`
- primary Next.js отвечает на `/login`
- Streamlit fallback отвечает на HTTP
- assistant runtime подключается к built-in MCP по `http://mcp-http:5008/mcp/`

Важные детали:
- unified stack использует `SUPERSET_PRODUCT_MCP_RUNTIME=built_in_http`
- `mcp-http` запускает built-in MCP из локального дерева `superset/`, примонтированного в dev-контур
- в `.env.dev.example` по умолчанию `SUPERSET_LOAD_EXAMPLES=no`, чтобы первый `up -d` был быстрее и детерминированнее
- unified stack теперь поднимает отдельный `pagila-db` и автоматически регистрирует `Pagila Demo (PostgreSQL)` как реальный demo-source в Superset
- primary entrypoints по умолчанию:
  - Next.js: `:3001`
  - FastAPI: `:8100`
  - Streamlit fallback: `:8051`
- если host-порты заняты, задайте `DEV_SUPERSET_PORT`, `DEV_API_PORT`, `DEV_NEXTJS_PORT`, `DEV_ASSISTANT_PORT` в `.env.dev`

Подробный demo runbook и набор рекомендованных вопросов:
- `docs/demo-pagila.md`
- `docs/manual-smoke-checklist.md`
- `docs/demo-query-pack.md`
- `docs/dual-run-parity-readiness.md`
- `docs/phased-cutover-plan.md`

## Линтеры и CI
В репозитории настроен рабочий pipeline/workflow для автоматического запуска линтеров:

- Workflow: `.github/workflows/ci.yml`
- Линтер: `ruff`
- Проверка синтаксиса: `python -m compileall`

### Локальный запуск линтера
```bash
cd /home/superset_ai
python3 -m pip install ruff
ruff check superset-ai-assistant-mcp/backend superset-ai-assistant-mcp/frontend superset-ai-assistant-mcp/tests
python3 -m compileall superset-ai-assistant-mcp/backend superset-ai-assistant-mcp/frontend superset-ai-assistant-mcp/tests
```

## Тесты
```bash
cd /home/superset_ai
PYTHONPATH=./superset-ai-assistant-mcp python -m unittest discover -s superset-ai-assistant-mcp/tests/unit -p "test_*.py"
PYTHONPATH=./superset-ai-assistant-mcp python -m unittest discover -s superset-ai-assistant-mcp/tests -p "test_frontend_ui.py"
PYTHONPATH=./superset-ai-assistant-mcp python -m unittest discover -s superset-ai-assistant-mcp/tests -p "test_ai_agent_clarifications.py"
PYTHONPATH=./superset-ai-assistant-mcp python -m unittest discover -s superset-ai-assistant-mcp/tests -p "test_us13_15_viz_service.py"
```

## Ключевые сценарии продукта
- Сканер схем и связей (US1)
- Глоссарий бизнес-терминов (US2)
- Правила маппинга термин → колонки/метрики (US3)
- Бизнес-подсказки запросов с учетом метаданных (US4)
- Конструктор запроса по критериям (US5)
- Guardrails/безопасность/квоты (US10–US12)
- Предпросмотр результата + объяснение полей (US13)
- Авто-рекомендация типа графика (US14)
- Создание виджета и share-ссылок (US15)

## Troubleshooting
- Ошибка `429` от OpenAI: уменьшить частоту запросов, использовать более экономичную модель, сократить контекст.
- Ошибка доступа к Superset или built-in MCP: проверить `SUPERSET_BASE_URL`, доступность built-in MCP endpoint/launcher и права текущего пользователя в Superset.
- Ошибка built-in MCP запуска в assistant Docker image: image не содержит исходники Superset, поэтому для `built_in_stdio` нужен явный launcher; без него используйте `built_in_http`.
- Ошибка built-in MCP запуска в локальном процессе: либо обеспечьте доступность `python -m superset.mcp_service` в текущей среде, либо задайте `SUPERSET_BUILT_IN_MCP_COMMAND` и при необходимости `SUPERSET_BUILT_IN_MCP_ARGS`.
- Для HTTP-транспорта задайте `SUPERSET_PRODUCT_MCP_RUNTIME=built_in_http` и `SUPERSET_BUILT_IN_MCP_URL`.
- Для unified local dev stack используйте `docker compose --env-file .env.dev -f docker-compose.dev.yml up -d`; если host-порты заняты, переопределите `DEV_SUPERSET_PORT` и `DEV_ASSISTANT_PORT`.
- Пустые списки таблиц/датасетов: убедиться, что в Superset созданы подключения БД и datasets.

## Вклад команды
- Поддерживается командная разработка через GitHub flow.
- Для PR обязательны: зелёный CI, понятный changelog в описании, проверка сценариев запуска.
