from __future__ import annotations

import json
from typing import Any, Mapping

from mcp_use import MCPClient

from backend.mcp_client.base import BaseProductMCPClient, ToolTransport
from backend.mcp_client.errors import (
    normalize_mcp_error,
    payload_indicates_error,
    redact_sensitive_data,
)
from backend.mcp_client.tool_registry import (
    DEFAULT_SERVER_NAME,
    build_agent_mcp_use_config,
)


def _coerce_payload(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(k): _coerce_payload(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_coerce_payload(item) for item in value]
    if isinstance(value, tuple):
        return [_coerce_payload(item) for item in value]
    return value


def _extract_result_payload(result: Any) -> Any:
    if result is None:
        return {}
    for attr in ("structured_content", "structuredContent", "data"):
        if hasattr(result, attr):
            raw = getattr(result, attr)
            if raw not in (None, {}):
                return _coerce_payload(raw)
    content = getattr(result, "content", None)
    if isinstance(content, list) and content:
        first = content[0]
        text = getattr(first, "text", None)
        if isinstance(text, str) and text.strip():
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {"text": text}
    return _coerce_payload(result)


def _unwrap_single_result_mapping(payload: Any) -> Any:
    if not isinstance(payload, Mapping):
        return payload
    if tuple(payload.keys()) != ("result",):
        return payload
    inner = payload.get("result")
    if isinstance(inner, Mapping):
        return dict(inner)
    return payload


class McpUseToolTransport(ToolTransport):
    def __init__(
        self,
        *,
        mcp_config: Mapping[str, Any] | None = None,
        server_name: str = DEFAULT_SERVER_NAME,
    ):
        self._mcp_config = dict(
            mcp_config
            or build_agent_mcp_use_config(
                runtime="built_in_stdio",
            )
        )
        self._server_name = server_name
        self._client: MCPClient | None = None
        self._session: Any = None

    async def _get_session(self) -> Any:
        if self._session is not None:
            return self._session
        if self._client is None:
            self._client = MCPClient.from_dict(self._mcp_config)
        self._session = await self._client.create_session(self._server_name)
        return self._session

    async def call_tool(
        self, tool_name: str, arguments: Mapping[str, Any] | None = None
    ) -> Any:
        session = await self._get_session()
        return await session.call_tool(tool_name, dict(arguments or {}))

    async def list_tools(self) -> list[str]:
        session = await self._get_session()
        tools = await session.list_tools()
        return [str(getattr(tool, "name", "")) for tool in tools]

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close_all_sessions()
        self._session = None
        self._client = None


class BuiltInMCPClient(BaseProductMCPClient):
    async def call_tool(
        self, tool_name: str, arguments: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        try:
            result = await self.transport.call_tool(tool_name, arguments or {})
        except Exception as exc:
            raise normalize_mcp_error(tool_name=tool_name, exc=exc) from exc

        payload = redact_sensitive_data(
            _unwrap_single_result_mapping(_extract_result_payload(result))
        )
        is_error = bool(
            getattr(result, "isError", False) or getattr(result, "is_error", False)
        )

        if payload_indicates_error(payload) or is_error:
            raise normalize_mcp_error(
                tool_name=tool_name,
                payload=payload if isinstance(payload, Mapping) else None,
            )

        if isinstance(payload, Mapping):
            return dict(payload)
        return {"result": payload}
