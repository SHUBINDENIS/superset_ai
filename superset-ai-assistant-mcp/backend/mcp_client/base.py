from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Mapping


class ToolTransport(ABC):
    @abstractmethod
    async def call_tool(
        self, tool_name: str, arguments: Mapping[str, Any] | None = None
    ) -> Any:
        raise NotImplementedError

    async def list_tools(self) -> list[str]:
        return []

    async def close(self) -> None:
        return None


class BaseProductMCPClient(ABC):
    def __init__(self, transport: ToolTransport):
        self.transport = transport

    @abstractmethod
    async def call_tool(
        self, tool_name: str, arguments: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        raise NotImplementedError

    async def close(self) -> None:
        await self.transport.close()

    async def list_dashboards(
        self, request: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        return await self.call_tool("list_dashboards", {"request": dict(request or {})})

    async def get_dashboard_info(self, identifier: int | str) -> dict[str, Any]:
        return await self.call_tool(
            "get_dashboard_info",
            {"request": {"identifier": identifier}},
        )

    async def list_charts(
        self, request: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        return await self.call_tool("list_charts", {"request": dict(request or {})})

    async def get_chart_info(self, identifier: int | str) -> dict[str, Any]:
        return await self.call_tool(
            "get_chart_info",
            {"request": {"identifier": identifier}},
        )

    async def list_datasets(
        self, request: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        return await self.call_tool("list_datasets", {"request": dict(request or {})})

    async def get_dataset_info(self, identifier: int | str) -> dict[str, Any]:
        return await self.call_tool(
            "get_dataset_info",
            {"request": {"identifier": identifier}},
        )

    async def execute_sql(self, request: Mapping[str, Any]) -> dict[str, Any]:
        return await self.call_tool("execute_sql", {"request": dict(request)})

    async def list_databases(
        self, request: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        return await self.call_tool(
            "mcp_ext.list_databases",
            {"request": dict(request or {})},
        )

    async def create_empty_dashboard(
        self, request: Mapping[str, Any]
    ) -> dict[str, Any]:
        return await self.call_tool(
            "mcp_ext.create_empty_dashboard",
            {"request": dict(request)},
        )

    async def open_sql_lab_with_context(
        self, request: Mapping[str, Any]
    ) -> dict[str, Any]:
        return await self.call_tool("open_sql_lab_with_context", {"request": dict(request)})

    async def generate_chart(self, request: Mapping[str, Any]) -> dict[str, Any]:
        return await self.call_tool("generate_chart", {"request": dict(request)})

    async def update_chart(self, request: Mapping[str, Any]) -> dict[str, Any]:
        return await self.call_tool("update_chart", {"request": dict(request)})

    async def generate_dashboard(self, request: Mapping[str, Any]) -> dict[str, Any]:
        return await self.call_tool("generate_dashboard", {"request": dict(request)})

    async def add_chart_to_existing_dashboard(
        self, request: Mapping[str, Any]
    ) -> dict[str, Any]:
        return await self.call_tool(
            "add_chart_to_existing_dashboard",
            {"request": dict(request)},
        )

    async def generate_explore_link(
        self, request: Mapping[str, Any]
    ) -> dict[str, Any]:
        return await self.call_tool("generate_explore_link", {"request": dict(request)})

    async def legacy_chart_create(
        self, request: Mapping[str, Any]
    ) -> dict[str, Any]:
        return await self.call_tool("mcp_ext.legacy_chart_create", {"request": dict(request)})
