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
