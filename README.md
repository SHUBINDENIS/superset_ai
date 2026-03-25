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
    - `superset-ai-assistant-mcp/frontend/app.py`
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
- `ruff.toml`
  - конфигурация линтера Ruff.

## Архитектура (кратко)
- Пользователь работает в `Streamlit UI`.
- UI отправляет задачи в `AI Agent`.
- AI Agent использует built-in Superset MCP service.
- Superset выполняет SQL/строит графики/дашборды в подключённых источниках данных.

Подробная схема развёртывания (Deployment): `docs/deployment.md`.

## Требования к окружению
- Docker + Docker Compose
- Python 3.10+ (для локального запуска сервисов)
- OpenAI API key (для AI-части)

## Быстрый запуск (рекомендуемый порядок)
Ниже порядок, который использовался в проекте: сначала Superset, затем UI/ассистент.

### 1) Поднять Apache Superset
```bash
cd /home/superset_ai/superset
docker compose -f docker-compose-image-tag.yml up -d
```

Проверка:
```bash
docker compose -f docker-compose-image-tag.yml ps
```

Обычно UI Superset доступен на `http://localhost:8088` (или на вашем внешнем IP/домене).

### 2) Настроить переменные окружения ассистента
```bash
cd /home/superset_ai/superset-ai-assistant-mcp
cp .env.example .env
```

Минимально проверьте в `.env`:
- `OPENAI_API_KEY=...`
- `OPENAI_MODEL=gpt-4o-mini` (рекомендуется для уменьшения 429)
- `SUPERSET_PRODUCT_MCP_RUNTIME=built_in_stdio`
- `SUPERSET_BUILT_IN_MCP_COMMAND=...` и `SUPERSET_BUILT_IN_MCP_ARGS=...` только если текущая среда не умеет запускать `python -m superset.mcp_service` напрямую
- `SUPERSET_BASE_URL=http://<host>:8088`
- `SUPERSET_PUBLIC_URL=http://<host>:8088`
- `AI_ASSISTANT_WS_BASE_URL=ws://<host>:8052/ws/chat`
- `AUTH_DB_PATH=/home/superset_ai/superset-ai-assistant-mcp/data/auth.db`
- `AUTH_JWT_SECRET=...` (обязательно поменять с дефолтного значения)
- `AUTH_JWT_TTL_HOURS=12`
- `AUTH_PASSWORD_MIN_LENGTH=8`
- `AUTH_HISTORY_MAX_MESSAGES=500`

### 3) Запустить WS API и UI ассистента (локально)
```bash
cd /home/superset_ai/superset-ai-assistant-mcp
pip install -r requirements.txt
uvicorn backend.ws_api:app --app-dir . --host 0.0.0.0 --port 8052
# в отдельном терминале:
streamlit run frontend/app.py --server.port 8051 --server.address 0.0.0.0
```

Открыть: `http://localhost:8051`, пройти `Вход/Регистрацию`, затем выбрать транспорт `WebSocket (stream)`.

## Запуск через Docker (ассистент)
Сборку нужно делать из корня репозитория:

```bash
cd /home/superset_ai
docker build -t ai_superset -f superset-ai-assistant-mcp/Dockerfile .
docker run --rm -p 8051:8051 -p 8052:8052 --env-file superset-ai-assistant-mcp/.env ai_superset
```

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
cd /home/superset_ai/superset-ai-assistant-mcp
pytest tests -q
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
- Ошибка авторизации Superset: проверить `SUPERSET_BASE_URL`, логин/пароль и доступность Superset.
- Ошибка built-in MCP запуска: либо обеспечьте доступность `python -m superset.mcp_service` в текущей среде, либо задайте `SUPERSET_BUILT_IN_MCP_COMMAND` и при необходимости `SUPERSET_BUILT_IN_MCP_ARGS`.
- Для HTTP-транспорта задайте `SUPERSET_PRODUCT_MCP_RUNTIME=built_in_http` и `SUPERSET_BUILT_IN_MCP_URL`.
- Пустые списки таблиц/датасетов: убедиться, что в Superset созданы подключения БД и datasets.

## Вклад команды
- Поддерживается командная разработка через GitHub flow.
- Для PR обязательны: зелёный CI, понятный changelog в описании, проверка сценариев запуска.
