# Схема Развёртывания

Документ описывает актуальную схему deployment для проекта `superset_ai` в формате:
**облако → сервер → контейнеры**.

Текущее состояние после упрощения транспорта:

- чат ассистента работает только через HTTP/UI path
- отдельный streaming backend больше не используется
- Streamlit вызывает backend-модули и `AI Agent` внутри того же процесса
- поддерживаемый Docker-сценарий остаётся split-моделью: Superset через compose, ассистент отдельным процессом/контейнером
- дополнительно доступен optional unified local dev stack через `docker-compose.dev.yml`
- Celery worker/beat оставлены только как опциональный профиль для фоновых задач Superset, а не как обязательная часть базового запуска проекта

## 1) Диаграмма развёртывания

```mermaid
flowchart TB
    user[Пользователь<br/>Browser]

    subgraph cloud[Cloud / VPS провайдер]
        subgraph vm[Linux VM / выделенный сервер]
            subgraph docker[Docker Engine]
                subgraph supstack[Compose: superset/docker-compose-image-tag.yml]
                    superset_app[Container: superset_app<br/>Apache Superset<br/>:8088]
                    superset_db[Container: superset_db<br/>PostgreSQL metadata<br/>:5432]
                    superset_cache[Container: superset_cache<br/>Redis<br/>:6379]
                    superset_worker[Container: superset_worker<br/>Celery worker<br/>optional async profile]
                    superset_beat[Container: superset_worker_beat<br/>Celery beat<br/>optional async profile]
                end

                subgraph aistack[AI Assistant deployment]
                    streamlit[Container/Process: Streamlit UI + backend services<br/>superset-ai-assistant-mcp<br/>:8051]
                    agent[In-process AI Agent<br/>backend/ai_agent.py]
                    mcp[Process: Built-in Superset MCP<br/>superset.mcp_service<br/>stdio or HTTP]
                end
            end
        end
    end

    openai[External Cloud Service<br/>OpenAI API]

    user -->|HTTPS/HTTP| streamlit
    user -->|HTTPS/HTTP| superset_app
    streamlit -->|in-process backend call| agent
    agent -->|LLM API| openai
    agent -->|spawn + stdio or HTTP| mcp
    mcp -->|Superset internals / DAO / RBAC| superset_app

    superset_app --> superset_db
    superset_app --> superset_cache
    superset_worker --> superset_db
    superset_worker --> superset_cache
    superset_beat --> superset_cache
```

## 2) Где разворачиваются компоненты

| Уровень | Компоненты | Где размещены |
|---|---|---|
| Облако / датацентр | VM / сервер | IaaS/VPS или физический сервер |
| Сервер (OS) | Docker Engine | Linux host |
| Контейнеры Superset | `superset_app`, `superset_db`, `superset_cache` | Базовый проектный стек в `docker-compose-image-tag.yml` |
| Опциональные контейнеры Superset | `superset_worker`, `superset_worker_beat` | Профиль `async` для фоновых задач Superset |
| Контейнер/процесс AI | Streamlit UI + встроенный backend agent + built-in MCP runtime | Отдельный контейнер `ai_superset` или локальный процесс |
| Внешние сервисы | OpenAI API | Внешнее облако (SaaS API) |

## 3) Компоненты и их назначение

| Компонент | Расположение | Назначение |
|---|---|---|
| Streamlit UI | `superset-ai-assistant-mcp/frontend/app.py` + shared frontend helpers | Пользовательский интерфейс и HTTP-only точка входа ассистента |
| AI Agent | `superset-ai-assistant-mcp/backend/ai_agent.py` | Оркестрация запроса, guardrails, работа с LLM и built-in MCP внутри процесса Streamlit |
| MCP Server | `superset/superset/mcp_service` | Built-in MCP runtime для работы с Superset tools / DAO / RBAC |
| Superset App | `superset_app` | BI-платформа, SQL Lab, charts/dashboards |
| Superset DB | `superset_db` | Метаданные Superset (PostgreSQL) |
| Superset Cache | `superset_cache` | Redis для кэша/очередей |
| Worker/Beat | `superset_worker`, `superset_worker_beat` | Фоновые задачи Superset |
| OpenAI API | внешний сервис | LLM для NL→SQL и генерации/уточнений |

## 4) Сетевые точки и порты

| Endpoint | Порт | Использование |
|---|---|---|
| `http://<host>:8051` | 8051 | UI ассистента (Streamlit) |
| `http://<host>:8088` | 8088 | Apache Superset |
| `superset_db` | 5432 | Внутренняя БД Superset |
| `superset_cache` | 6379 | Внутренний Redis |

Примечание: built-in MCP в текущем проекте обычно запускается как subprocess через `stdio`, но также поддерживается режим `built_in_http`. Отдельный assistant Docker image не включает код `superset.mcp_service`, поэтому для контейнерного запуска нужен либо `built_in_http`, либо явный stdio launcher.

## 5) Потоки данных

1. Пользователь отправляет запрос в `Streamlit`.
2. `Streamlit` вызывает встроенный `AI Agent` через backend-модули внутри того же процесса.
3. Агент применяет guardrails и готовит контекст.
4. Агент вызывает `OpenAI API` для генерации/интерпретации.
5. Для операций Superset агент вызывает built-in MCP-инструменты (`superset.mcp_service`).
6. Built-in MCP использует внутренние Superset tools / DAO / RBAC вместо legacy REST-прокси.
7. `Streamlit` рендерит итоговый ответ без отдельного transport layer для чата.

## 6) Переменные окружения, критичные для развёртывания

Основные переменные:

- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `SUPERSET_PRODUCT_MCP_RUNTIME`
- `SUPERSET_BUILT_IN_MCP_COMMAND`
- `SUPERSET_BUILT_IN_MCP_ARGS`
- `SUPERSET_BUILT_IN_MCP_URL`
- `SUPERSET_BASE_URL`
- `SUPERSET_PUBLIC_URL`
- `US15_SHARE_BASE_URL`
- `AUTH_DB_PATH`
- `AUTH_JWT_SECRET`

## 7) Минимальный сценарий запуска

1. Поднять Superset стек:
   - `cd superset`
   - `docker compose -f docker-compose-image-tag.yml up -d db redis superset-init superset`
   - `docker compose -f docker-compose-image-tag.yml config --services`
   - если нужны Celery background jobs: `docker compose -f docker-compose-image-tag.yml --profile async up -d superset-worker superset-worker-beat`
2. Поднять ассистент:
   - локально: `streamlit run frontend/app.py --server.port 8051 --server.address 0.0.0.0`
   - или контейнером `ai_superset` на порту `8051` из `superset-ai-assistant-mcp/Dockerfile`
3. Проверить доступность:
   - `http://<host>:8088` (Superset)
   - `http://<host>:8051` (Assistant)

## 8) Опциональный unified local dev stack

Этот вариант предназначен для локальной разработки/демо одной командой и не заменяет split-модель как базовый deployment.

Состав:
- `db`
- `redis`
- `superset-init`
- `superset`
- `mcp-http`
- `assistant`
- optional profile `async`: `superset-worker`, `superset-worker-beat`

Ключевое решение:
- MCP для ассистента подключается по `built_in_http`
- `assistant` использует `SUPERSET_BUILT_IN_MCP_URL=http://mcp-http:5008/mcp/`
- контейнер `mcp-http` запускает built-in MCP из локального дерева `superset/`, а не из assistant image

Запуск:
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

Примечания:
- по умолчанию используется `SUPERSET_LOAD_EXAMPLES=no`, чтобы первый запуск не зависал на загрузке sample datasets
- если локально уже занят `8088` или `8051`, задайте `DEV_SUPERSET_PORT` и `DEV_ASSISTANT_PORT` в `.env.dev`
- verified path: compose config, container startup, HTTP-ответы Superset и assistant, и подключение assistant runtime к built-in MCP endpoint внутри compose-сети

## 9) Ограничения текущего deployment

- Конфигурация ориентирована на MVP/демо и учебный контур.
- Для production требуются отдельные меры: TLS, секреты, hardening, отказоустойчивость, мониторинг/алертинг, backup-политики.

## 10) Как показать текущий HTTP-only assistant path на практике

1. Поднять `Streamlit` и открыть `http://<host>:8051`.
2. Пройти авторизацию.
3. Отправить запрос в чате.
4. Показать, что ответ приходит через встроенный backend-agent путь без выбора транспорта и без отдельного streaming trace слоя.
