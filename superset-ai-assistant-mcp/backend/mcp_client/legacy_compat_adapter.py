from __future__ import annotations

from typing import Any, Mapping

from backend.mcp_client.base import BaseProductMCPClient
from backend.mcp_client.errors import (
    MCPClientError,
    redact_sensitive_data,
)
from backend.mcp_client.tool_registry import get_legacy_mapping


class LegacyCompatAdapter:
    def __init__(self, built_in_client: BaseProductMCPClient):
        self._built_in_client = built_in_client

    async def call_tool(
        self, legacy_tool_name: str, arguments: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        mapping = get_legacy_mapping(legacy_tool_name)
        built_in_arguments = mapping.request_builder(arguments or {})
        try:
            payload = await self._built_in_client.call_tool(
                mapping.built_in_tool,
                built_in_arguments,
            )
        except MCPClientError:
            raise

        normalized = mapping.response_normalizer(payload)
        return redact_sensitive_data(normalized)

    async def close(self) -> None:
        await self._built_in_client.close()
