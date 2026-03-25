from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from mcp_use import MCPClient

from backend.mcp_client.base import BaseProductMCPClient
from backend.mcp_client.built_in_client import BuiltInMCPClient, McpUseToolTransport
from backend.mcp_client.legacy_compat_adapter import LegacyCompatAdapter
from backend.mcp_client.tool_registry import (
    build_agent_mcp_use_config,
    get_runtime_attempt_order,
)


@dataclass(slots=True)
class ProductMCPRuntime:
    runtime_name: str
    mcp_use_client: MCPClient
    product_client: BaseProductMCPClient | None
    legacy_adapter: LegacyCompatAdapter | None
    tool_names: tuple[str, ...] = ()

    async def close(self) -> None:
        if self.product_client is not None:
            await self.product_client.close()
        await self.mcp_use_client.close_all_sessions()


async def create_product_mcp_runtime(
    *,
    requested_runtime: str | None = None,
    fallback_runtime: str | None = None,
    legacy_python_resolver: Callable[[], str] | None = None,
    legacy_server_path_resolver: Callable[[], str] | None = None,
) -> ProductMCPRuntime:
    attempt_order = get_runtime_attempt_order(
        runtime=requested_runtime,
        fallback_runtime=fallback_runtime,
    )
    last_error: Exception | None = None

    for runtime_name in attempt_order:
        mcp_config = build_agent_mcp_use_config(
            runtime=runtime_name,
            legacy_python_resolver=legacy_python_resolver,
            legacy_server_path_resolver=legacy_server_path_resolver,
        )
        mcp_use_client = MCPClient.from_dict(mcp_config)

        if runtime_name == "legacy":
            return ProductMCPRuntime(
                runtime_name=runtime_name,
                mcp_use_client=mcp_use_client,
                product_client=None,
                legacy_adapter=None,
            )

        transport = McpUseToolTransport(mcp_config=mcp_config)
        product_client = BuiltInMCPClient(transport)

        try:
            tool_names = tuple(await transport.list_tools())
            return ProductMCPRuntime(
                runtime_name=runtime_name,
                mcp_use_client=mcp_use_client,
                product_client=product_client,
                legacy_adapter=LegacyCompatAdapter(product_client),
                tool_names=tool_names,
            )
        except Exception as exc:
            last_error = exc
            await product_client.close()
            await mcp_use_client.close_all_sessions()

    if last_error is not None:
        raise last_error
    raise RuntimeError("Unable to create product MCP runtime")
