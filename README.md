# Superset AI: NL→SQL→Chart

Проект для MVP/MUP этапов по курсу веб-разработки: AI-ассистент над Apache Superset, который помогает формулировать аналитические запросы на естественном языке, строить SQL, делать предпросмотр, рекомендовать тип визуализации и создавать виджеты/дашборды.

## Открытый репозиторий
- Исходный код размещён в открытом репозитории GitHub: `https://github.com/SHUBINDENIS/superset_ai`.
- Также может быть размещён в GitLab при необходимости (критерий допускает GitHub/GitLab).

## Что уже реализовано
- Базовая платформа: Apache Superset в Docker.
- MCP-интеграция: built-in Superset MCP service (`superset/superset/mcp_service`) для программного доступа к Superset tools / DAO / RBAC.
- UI продукта: `Streamlit`-приложение `superset-ai-assistant-mcp`.
- Реализованы продуктовые окна и сценарии для US1–US5, US10–US15 (скан схем, глоссарий, маппинг, подсказки, конструктор, guardrails, preview, рекомендации графиков, создание share-ссылок).
- Защитные механизмы US10–US12: anti prompt-injection, ограничение нерелевантных запросов, read-only/безопасность SQL, базовые квоты.

## Структура репозитория
Структура проекта разделена на модули и пакеты, навигация по коду организована по подсистемам:

- `superset/`
  - инфраструктура Apache Superset (docker-compose, конфиги, upstream-код).
- `superset-ai-assistant-mcp/`
  - основной продукт (frontend + backend).
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
- `docs/mcp-migration/`
  - исторические материалы миграции и parity-отчёты по удалённому legacy MCP runtime.

## Архитектура (кратко)
- Пользователь работает в `Streamlit UI`.
- `Streamlit` вызывает backend-модули и `AI Agent` внутри того же процесса.
- `AI Agent` использует built-in Superset MCP service.
- Superset выполняет SQL, строит графики и дашборды в подключённых источниках данных.

Подробная схема развёртывания (Deployment): `docs/deployment.md`.

## Требования к окружению
- Docker + Docker Compose
- Python 3.10+ (для локального запуска сервисов)
- OpenAI API key (для AI-части)

## Поддерживаемая модель запуска

Текущая поддерживаемая схема развёртывания разделена на две части:

- `superset/docker-compose-image-tag.yml` поднимает стек Apache Superset.
- `superset-ai-assistant-mcp/` запускается отдельно: локально через `streamlit run` или отдельным Docker-образом.

Ассистент не входит в текущий `docker compose` стек Superset.
`superset-worker` и `superset-worker-beat` больше не считаются обязательной частью базового проекта; они оставлены как opt-in профиль для фоновых задач Superset.

Дополнительно есть **опциональный** unified local dev stack:

- файл: `docker-compose.dev.yml`
- цель: локальный демо/дев-контур одной командой
- модель MCP: `built_in_http`
- baseline split deployment при этом остаётся основной и поддерживаемой схемой

## Быстрый запуск (рекомендуемый порядок)
Сначала запускается Superset, затем отдельно запускается ассистент.

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

### 3) Запустить UI ассистента (локально)
```bash
cd /home/superset_ai/superset-ai-assistant-mcp
pip install -r requirements.txt
streamlit run frontend/app.py --server.port 8051 --server.address 0.0.0.0
```

Открыть: `http://localhost:8051` и пройти `Вход/Регистрацию`.

### 4) Запустить ассистент отдельным Docker-образом
Сборку нужно делать из корня репозитория:

```bash
cd /home/superset_ai
docker build -t ai_superset -f superset-ai-assistant-mcp/Dockerfile .
docker run --rm -p 8051:8051 --env-file superset-ai-assistant-mcp/.env ai_superset
```

Проверка:
```bash
curl -I http://127.0.0.1:8051
```

Что было реально проверено в репозитории:
- compose-файл Superset успешно парсится:
  - базовый стек: `db`, `redis`, `superset-init`, `superset`
  - optional profile `async`: `superset-worker`, `superset-worker-beat`
- assistant Docker image успешно собирается
- контейнер `ai_superset` успешно стартует и отдаёт Streamlit UI на `:8051`

Важно:
- этот Docker image поднимает только ассистент
- в image теперь копируются только runtime-файлы ассистента, без тестов, локальных БД и логов
- он не поднимает Superset и не включает в себя код `superset.mcp_service`
- для рабочего MCP-подключения внутри такого контейнера нужен либо доступный `built_in_http` endpoint, либо явно заданный stdio launcher

### 5) Опциональный unified local dev stack
Этот сценарий добавлен для локальной разработки и демо, но не заменяет split deployment.

Что поднимает `docker-compose.dev.yml`:
- `db`
- `redis`
- `superset-init`
- `superset`
- `mcp-http`
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
curl -I http://127.0.0.1:8051
```

Что реально проверено:
- `docker compose -f docker-compose.dev.yml config`
- unified stack стартует в контейнерах
- Superset отвечает на HTTP
- Streamlit assistant отвечает на HTTP
- assistant runtime подключается к built-in MCP по `http://mcp-http:5008/mcp/`

Важные детали:
- unified stack использует `SUPERSET_PRODUCT_MCP_RUNTIME=built_in_http`
- `mcp-http` запускает built-in MCP из локального дерева `superset/`, примонтированного в dev-контур
- в `.env.dev.example` по умолчанию `SUPERSET_LOAD_EXAMPLES=no`, чтобы первый `up -d` был быстрее и детерминированнее
- unified stack теперь поднимает отдельный `pagila-db` и автоматически регистрирует `Pagila Demo (PostgreSQL)` как реальный demo-source в Superset
- если `8088` или `8051` уже заняты, задайте `DEV_SUPERSET_PORT` и `DEV_ASSISTANT_PORT` в `.env.dev`

Подробный demo runbook и набор рекомендованных вопросов:
- `docs/demo-pagila.md`
- `docs/manual-smoke-checklist.md`
- `docs/demo-query-pack.md`

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
