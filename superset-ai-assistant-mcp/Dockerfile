FROM python:3.12-slim

WORKDIR /app

# системные зависимости
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# зависимости
COPY superset-ai-assistant-mcp/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# код
COPY superset-ai-assistant-mcp ./superset-ai-assistant-mcp
COPY superset-mcp ./superset-mcp

# env
ENV PYTHONPATH=/app

EXPOSE 8051 8052

CMD ["bash", "superset-ai-assistant-mcp/start_assistant_stack.sh"]
