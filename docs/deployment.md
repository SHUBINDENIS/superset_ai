# Схема Развёртывания

Документ описывает схему Deployment для проекта `superset_ai` в формате: **облако → сервер → контейнеры**.

## 1) Диаграмма развёртывания (Deployment: облако/сервер/контейнеры)

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
                    superset_worker[Container: superset_worker<br/>Celery worker]
                    superset_beat[Container: superset_worker_beat<br/>Celery beat]
                end

                subgraph aistack[AI Assistant deployment]
                    streamlit[Container/Process: Streamlit UI<br/>superset-ai-assistant-mcp<br/>:8051]
                    agent[Process: AI Agent<br/>backend/ai_agent.py]
                    mcp[Process: Superset MCP<br/>superset-mcp/main.py<br/>stdio]
                end
            end
        end
    end

    openai[External Cloud Service<br/>OpenAI API]

    user -->|HTTPS/HTTP| streamlit
    user -->|HTTPS/HTTP| superset_app

    streamlit --> agent
    agent -->|LLM API| openai
    agent -->|spawn + stdio| mcp
    mcp -->|REST /api/v1/*| superset_app

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
| Контейнеры Superset | `superset_app`, `superset_db`, `superset_cache`, `superset_worker`, `superset_worker_beat` | Один docker network (`docker-compose-image-tag.yml`) |
| Контейнер/процесс AI | Streamlit UI + backend сервисы + MCP subprocess | Отдельный контейнер `ai_superset` или локальный процесс |
| Внешние сервисы | OpenAI API | Внешнее облако (SaaS API) |

## 3) Компоненты и их назначение

| Компонент | Расположение | Назначение |
|---|---|---|
| Streamlit UI | `superset-ai-assistant-mcp/frontend/app.py` | Пользовательский интерфейс ассистента |
| AI Agent | `superset-ai-assistant-mcp/backend/ai_agent.py` | Оркестрация запроса, guardrails, работа с LLM и MCP |
| MCP Server | `superset-mcp/main.py` | Программный доступ к Superset API через MCP-инструменты |
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

Примечание: MCP-сервер в текущем проекте обычно запускается как subprocess и общается с агентом через `stdio` (без публичного HTTP порта).

## 5) Потоки данных

1. Пользователь отправляет запрос в `Streamlit`.
2. `AI Agent` применяет guardrails и готовит контекст.
3. Агент вызывает `OpenAI API` для генерации/интерпретации.
4. Для операций Superset агент вызывает MCP-инструменты (`superset-mcp/main.py`).
5. MCP ходит в `Superset REST API` (`/api/v1/...`).
6. Superset читает/пишет метаданные в PostgreSQL, использует Redis/worker при необходимости.
7. Результат возвращается пользователю (текст, preview, ссылки на dashboard/chart).

## 6) Переменные окружения, критичные для развёртывания

Основные переменные (см. `superset-ai-assistant-mcp/.env.example`):

- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `SUPERSET_BASE_URL`
- `SUPERSET_PUBLIC_URL`
- `SUPERSET_USERNAME`
- `SUPERSET_PASSWORD`
- `SUPERSET_MCP_PATH`
- `SUPERSET_MCP_PYTHON`
- `US15_SHARE_BASE_URL`

## 7) Минимальный сценарий запуска (для этой схемы)

1. Поднять Superset стек:
   - `cd superset`
   - `docker compose -f docker-compose-image-tag.yml up -d`
2. Поднять ассистент:
   - локально через `streamlit run`  
   или
   - контейнером `ai_superset` на порту `8051`
3. Проверить доступность:
   - `http://<host>:8088` (Superset)
   - `http://<host>:8051` (Assistant)

## 8) Ограничения текущего deployment

- Конфигурация ориентирована на MVP/демо и учебный контур.
- Для production требуются отдельные меры: TLS, секреты, hardening, отказоустойчивость, мониторинг/алертинг, backup-политики.
