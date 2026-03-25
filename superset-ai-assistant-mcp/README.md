# Superset AI Assistant (прототип)

Коротко: простой чат на Streamlit, который через MCP ходит в ваш Apache Superset.

## Что нужно
- Python 3.10+
- Ключ OpenAI (`OPENAI_API_KEY`)
- Запущенный Superset с доступным built-in MCP runtime (`superset.mcp_service`)

## Как запустить
1. Скопируйте `.env.example` в `.env` и заполните:
   - `OPENAI_API_KEY` — ключ OpenAI
   - `OPENAI_MODEL` — рекомендуемо `gpt-4o-mini` для снижения риска 429 TPM
   - `SUPERSET_PRODUCT_MCP_RUNTIME` — `built_in_stdio` по умолчанию или `built_in_http`, если built-in MCP опубликован по HTTP
   - `SUPERSET_BUILT_IN_MCP_COMMAND`, `SUPERSET_BUILT_IN_MCP_ARGS` — опциональный launcher для `built_in_stdio`, если текущая среда не умеет запускать `python -m superset.mcp_service` напрямую
   - `SUPERSET_BUILT_IN_MCP_URL` — адрес built-in MCP только для режима `built_in_http`
   - `SUPERSET_BASE_URL`, `SUPERSET_PUBLIC_URL` — базовый URL Superset для всех ссылок (например, `http://103.54.18.91:8088`)
    - `AUTH_DB_PATH`, `AUTH_JWT_SECRET`, `AUTH_JWT_TTL_HOURS` — параметры локальной авторизации (логин/пароль + JWT)
   - `AUTH_PASSWORD_MIN_LENGTH`, `AUTH_HISTORY_MAX_MESSAGES` — политика паролей и лимит загружаемой истории чата
   - `AI_AGENT_MAX_STEPS`, `AI_AGENT_RECURSION_LIMIT` — лимиты шагов/рекурсии агента
   - `AI_AGENT_HISTORY_*`, `AI_AGENT_CONTEXT_CHARS`, `AI_AGENT_RATE_LIMIT_COOLDOWN_SECONDS` — ограничения на размер контекста и анти-спам cooldown после 429
2. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```
3. Запустите Streamlit UI:
   ```bash
   streamlit run frontend/app.py --server.port 8051 --server.address 0.0.0.0
   ```
4. Откройте `http://localhost:8051`:
   - сначала появится экран `Вход / Регистрация` (логин+пароль, без SMS/2FA),
   - после авторизации откроется основной интерфейс ассистента.

## Как пользоваться
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
- Ошибка про ключ: убедитесь, что `OPENAI_API_KEY` есть в `.env`.
- Ошибка `GRAPH_RECURSION_LIMIT`: увеличьте `AI_AGENT_MAX_STEPS` и `AI_AGENT_RECURSION_LIMIT` в `.env`.
- Ошибка `429 rate_limit_exceeded`: используйте `OPENAI_MODEL=gpt-4o-mini`, уменьшите контекст (`AI_AGENT_HISTORY_*`, `AI_AGENT_CONTEXT_CHARS`) и повторите запрос после cooldown.
- Ошибка `Запрос заблокирован политикой безопасности US10-US12`: уточните формулировку в рамках Superset/SQL и используйте разрешённые таблицы/метрики.
