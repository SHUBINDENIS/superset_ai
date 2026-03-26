FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# зависимости
COPY superset-ai-assistant-mcp/requirements.txt .
RUN python -m pip install --upgrade pip && python -m pip install -r requirements.txt

# runtime-only код
COPY superset-ai-assistant-mcp/api ./superset-ai-assistant-mcp/api
COPY superset-ai-assistant-mcp/backend ./superset-ai-assistant-mcp/backend
COPY superset-ai-assistant-mcp/frontend ./superset-ai-assistant-mcp/frontend
COPY superset-ai-assistant-mcp/.streamlit ./superset-ai-assistant-mcp/.streamlit
COPY superset-ai-assistant-mcp/start_assistant_stack.sh ./superset-ai-assistant-mcp/start_assistant_stack.sh
COPY superset-ai-assistant-mcp/start_fastapi_stack.sh ./superset-ai-assistant-mcp/start_fastapi_stack.sh

RUN chmod +x /app/superset-ai-assistant-mcp/start_assistant_stack.sh \
  && chmod +x /app/superset-ai-assistant-mcp/start_fastapi_stack.sh

EXPOSE 8051 8100

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8051/', timeout=5)" || exit 1

CMD ["bash", "superset-ai-assistant-mcp/start_assistant_stack.sh"]
