# Superset AI Assistant (прототип)

Коротко: простой чат на Streamlit, который через MCP ходит в ваш Apache Superset.

## Что нужно
- Python 3.10+
- Ключ OpenAI (`OPENAI_API_KEY`)
- Запущенный Superset и путь к скрипту Superset MCP (`superset-mcp/main.py`)

## Как запустить
1. Скопируйте `.env.example` в `.env` и заполните:
   - `OPENAI_API_KEY` — ключ OpenAI
   - `SUPERSET_MCP_PATH` — полный путь до `superset-mcp/main.py`
   - `SUPERSET_BASE_URL`, `SUPERSET_USERNAME`, `SUPERSET_PASSWORD` — доступ к Superset
2. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```
3. Запустите приложение:
   ```bash
   streamlit run frontend/app.py
   ```
4. Откройте в браузере `http://localhost:8501` и пишите запросы в чат.

## Как пользоваться
- Вводите текстовые запросы в чат — ассистент дергает MCP и Superset API.
- Если нет ответа, проверьте, что Superset MCP сервер запущен и переменные окружения заданы верно.

## Структура
- `frontend/app.py` — чат на Streamlit
- `backend/ai_agent.py` — обертка LangChain + mcp-use
- `.env.example` — образец настроек

## Быстрые подсказки
- Ошибка подключения: проверьте `SUPERSET_MCP_PATH` и работу Superset MCP.
- Ошибка про ключ: убедитесь, что `OPENAI_API_KEY` есть в `.env`.
