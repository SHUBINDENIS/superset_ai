"""
FastAPI application entrypoint.

Run locally:
    cd superset-ai-assistant-mcp
    uvicorn api.main:app --reload --port 8100

This app is designed to coexist with the Streamlit assistant.
It does NOT replace Streamlit; it provides a proper HTTP API layer
that future frontends (e.g. Next.js) will consume.
"""

from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager

# Ensure the assistant package root is on sys.path so that
# ``from backend.auth_service import …`` works regardless of CWD.
_PACKAGE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PACKAGE_ROOT not in sys.path:
    sys.path.insert(0, _PACKAGE_ROOT)

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from api.routers import auth, chats, frontend_logs, health, scan, viz  # noqa: E402


# ---------------------------------------------------------------------------
# Lifespan: clean up agent sessions / MCP runtimes on shutdown
# ---------------------------------------------------------------------------

@asynccontextmanager
async def _lifespan(app: FastAPI):
    yield
    try:
        from backend.ai_agent import shutdown_global_resources
        await shutdown_global_resources()
    except Exception:
        pass


app = FastAPI(
    title="Superset AI Assistant API",
    version="0.1.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=_lifespan,
)

# CORS — permissive for local dev; tighten for production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("API_CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(chats.router)
app.include_router(frontend_logs.router)
app.include_router(viz.router)
app.include_router(scan.router)
app.include_router(health.router)
