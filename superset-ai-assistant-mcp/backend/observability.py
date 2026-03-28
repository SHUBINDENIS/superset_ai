from __future__ import annotations

import contextlib
import contextvars
import hashlib
import json
import os
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping


LOG_FILE_NAMES = {
    "frontend": "frontend.log",
    "agent": "agent.log",
    "mcp": "mcp.log",
    "artifact": "artifact.log",
}

SENSITIVE_KEY_FRAGMENTS = (
    "token",
    "password",
    "secret",
    "authorization",
    "cookie",
    "apikey",
    "api_key",
)

_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9._-]+\.[A-Za-z0-9._-]+\b")
_BEARER_RE = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+\b")
_OPENAI_KEY_RE = re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b")
_KV_SECRET_RE = re.compile(
    r"(?i)\b("
    + "|".join(re.escape(fragment) for fragment in SENSITIVE_KEY_FRAGMENTS)
    + r")\b\s*[:=]\s*([^\s,;]+)"
)

_context_var: contextvars.ContextVar[dict[str, Any]] = contextvars.ContextVar(
    "assistant_log_context",
    default={},
)
_write_lock = threading.Lock()


def _assistant_root() -> Path:
    return Path(__file__).resolve().parent.parent


def get_log_dir() -> Path:
    raw_dir = str(os.getenv("ASSISTANT_LOG_DIR", "")).strip()
    if raw_dir:
        return Path(raw_dir)
    return _assistant_root() / "data" / "logs"


def get_log_path(component: str) -> Path:
    name = LOG_FILE_NAMES.get(str(component).strip().lower(), "assistant.log")
    return get_log_dir() / name


def get_log_paths() -> dict[str, str]:
    return {component: str(get_log_path(component)) for component in LOG_FILE_NAMES}


def new_trace_id() -> str:
    return uuid.uuid4().hex


def new_request_id() -> str:
    return uuid.uuid4().hex


def hash_user(username: str) -> str:
    clean = str(username or "").strip()
    if not clean:
        return ""
    return hashlib.sha256(clean.encode("utf-8")).hexdigest()[:16]


def _drop_empty_fields(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        str(key): value
        for key, value in payload.items()
        if value not in (None, "", [], {}, ())
    }


def sanitize_text(value: str, *, max_chars: int = 400) -> str:
    text = str(value or "")
    if not text:
        return ""
    text = _BEARER_RE.sub("Bearer [redacted]", text)
    text = _JWT_RE.sub("[redacted-jwt]", text)
    text = _OPENAI_KEY_RE.sub("[redacted-openai-key]", text)
    text = _KV_SECRET_RE.sub(lambda match: f"{match.group(1)}=[redacted]", text)
    if len(text) > max_chars:
        return text[: max_chars - 14].rstrip() + "...[truncated]"
    return text


def sanitize_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key).strip()
            key_low = key_text.casefold()
            if key_low == "username":
                user_hash = hash_user(str(item))
                if user_hash:
                    sanitized["user_hash"] = user_hash
                continue
            if any(fragment in key_low for fragment in SENSITIVE_KEY_FRAGMENTS):
                continue
            sanitized[key_text] = sanitize_value(item)
        return _drop_empty_fields(sanitized)
    if isinstance(value, list):
        return [sanitize_value(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize_value(item) for item in value]
    if isinstance(value, str):
        return sanitize_text(value)
    return value


def get_log_context() -> dict[str, Any]:
    return dict(_context_var.get({}))


@contextlib.contextmanager
def bind_log_context(**fields: Any) -> Iterator[dict[str, Any]]:
    current = get_log_context()
    current.update(_drop_empty_fields(sanitize_value(fields)))
    token = _context_var.set(current)
    try:
        yield current
    finally:
        _context_var.reset(token)


def emit_event(
    component: str,
    event: str,
    *,
    level: str = "INFO",
    **fields: Any,
) -> dict[str, Any]:
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": str(level or "INFO").upper(),
        "component": str(component or "").strip() or "assistant",
        "event": str(event or "").strip() or "event",
    }
    payload.update(get_log_context())
    payload.update(_drop_empty_fields(sanitize_value(fields)))
    payload = _drop_empty_fields(payload)

    log_path = get_log_path(str(component or "").strip().lower())
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with _write_lock:
            with log_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
                handle.write("\n")
    except Exception:
        return payload
    return payload
