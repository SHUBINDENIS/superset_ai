from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


SENSITIVE_KEY_FRAGMENTS = (
    "token",
    "password",
    "secret",
    "authorization",
    "cookie",
    "apikey",
    "api_key",
)


class MCPErrorCode(str, Enum):
    NOT_FOUND = "not_found"
    ACCESS_DENIED = "access_denied"
    INVALID_PAYLOAD = "invalid_payload"
    TIMEOUT = "timeout"
    DML_DENIED = "dml_denied"
    UNSUPPORTED_TOOL = "unsupported_tool"
    TRANSPORT_ERROR = "transport_error"
    UNKNOWN = "unknown"


@dataclass(slots=True)
class MCPClientError(Exception):
    code: MCPErrorCode
    message: str
    tool_name: str | None = None
    status_code: int | None = None
    details: dict[str, Any] = field(default_factory=dict)
    raw_error: Any = None

    def __post_init__(self) -> None:
        self.details = redact_sensitive_data(self.details)
        self.raw_error = redact_sensitive_data(self.raw_error)

    def __str__(self) -> str:
        return self.message

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "code": self.code.value,
            "message": self.message,
            "tool_name": self.tool_name,
            "status_code": self.status_code,
            "details": self.details,
        }
        return {k: v for k, v in payload.items() if v not in (None, {}, [])}


def _is_sensitive_key(key: str) -> bool:
    lowered = str(key or "").strip().casefold()
    return any(fragment in lowered for fragment in SENSITIVE_KEY_FRAGMENTS)


def redact_sensitive_data(value: Any) -> Any:
    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            if _is_sensitive_key(str(key)):
                continue
            sanitized[str(key)] = redact_sensitive_data(item)
        return sanitized
    if isinstance(value, list):
        return [redact_sensitive_data(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_sensitive_data(item) for item in value)
    return value


def _extract_error_text(payload: Mapping[str, Any] | None, fallback: str = "") -> str:
    if not payload:
        return str(fallback or "").strip()
    parts: list[str] = []
    for key in ("error", "message", "details", "exception_message", "error_type"):
        raw = payload.get(key)
        if raw:
            parts.append(str(raw))
    if fallback:
        parts.append(str(fallback))
    return " | ".join(parts).strip()


def _classify_error_code(
    payload: Mapping[str, Any] | None,
    error_text: str,
    exc: Exception | None = None,
) -> MCPErrorCode:
    if isinstance(exc, TimeoutError):
        return MCPErrorCode.TIMEOUT

    error_type = str((payload or {}).get("error_type", "")).casefold()
    low = str(error_text or "").casefold()

    if "timeout" in low or "timed out" in low:
        return MCPErrorCode.TIMEOUT
    if "dml_not_allowed" in error_type or "dml" in low and "allow" in low:
        return MCPErrorCode.DML_DENIED
    if error_type in {"security_error", "permissionerror"}:
        return MCPErrorCode.ACCESS_DENIED
    if any(token in low for token in ("access denied", "permission denied", "forbidden", "not authorized")):
        return MCPErrorCode.ACCESS_DENIED
    if error_type in {
        "notfounderror",
        "dataset_not_found_error",
        "database_not_found_error",
    }:
        return MCPErrorCode.NOT_FOUND
    if "not found" in low or "no dataset found" in low or "does not exist" in low:
        return MCPErrorCode.NOT_FOUND
    if any(token in low for token in ("validation", "invalid", "field required", "bad request")):
        return MCPErrorCode.INVALID_PAYLOAD
    if exc is not None:
        return MCPErrorCode.TRANSPORT_ERROR
    return MCPErrorCode.UNKNOWN


def normalize_mcp_error(
    *,
    tool_name: str,
    payload: Mapping[str, Any] | None = None,
    exc: Exception | None = None,
    message: str | None = None,
) -> MCPClientError:
    if isinstance(exc, MCPClientError):
        return exc

    sanitized_payload = redact_sensitive_data(payload or {})
    error_text = _extract_error_text(sanitized_payload, fallback=message or str(exc or ""))
    code = _classify_error_code(sanitized_payload, error_text, exc=exc)
    final_message = error_text or f"MCP tool '{tool_name}' failed"
    return MCPClientError(
        code=code,
        message=final_message,
        tool_name=tool_name,
        status_code=sanitized_payload.get("status_code")
        if isinstance(sanitized_payload, Mapping)
        else None,
        details=dict(sanitized_payload),
        raw_error=sanitized_payload or str(exc or ""),
    )


def unsupported_tool_error(tool_name: str) -> MCPClientError:
    return MCPClientError(
        code=MCPErrorCode.UNSUPPORTED_TOOL,
        message=f"Tool '{tool_name}' is not supported by the migrated product MCP layer.",
        tool_name=tool_name,
    )


def payload_indicates_error(payload: Any) -> bool:
    if not isinstance(payload, Mapping):
        return False
    if payload.get("success") is False:
        return True
    if payload.get("is_error") is True or payload.get("isError") is True:
        return True
    if payload.get("error") and payload.get("error_type"):
        return True
    return False
