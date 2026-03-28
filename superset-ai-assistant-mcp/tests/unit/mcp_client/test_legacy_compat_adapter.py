import unittest
from typing import Any, Mapping

from backend.mcp_client.base import ToolTransport
from backend.mcp_client.built_in_client import BuiltInMCPClient
from backend.mcp_client.errors import MCPClientError, MCPErrorCode
from backend.mcp_client.legacy_compat_adapter import LegacyCompatAdapter


class FakeTransport(ToolTransport):
    def __init__(
        self,
        *,
        responses: dict[str, Any] | None = None,
        exceptions: dict[str, Exception] | None = None,
    ):
        self.responses = responses or {}
        self.exceptions = exceptions or {}
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def call_tool(
        self, tool_name: str, arguments: Mapping[str, Any] | None = None
    ) -> Any:
        payload = dict(arguments or {})
        self.calls.append((tool_name, payload))
        if tool_name in self.exceptions:
            raise self.exceptions[tool_name]
        return self.responses[tool_name]


class TestLegacyCompatAdapter(unittest.IsolatedAsyncioTestCase):
    async def test_initial_legacy_mappings(self):
        transport = FakeTransport(
            responses={
                "list_dashboards": {
                    "dashboards": [{"id": 1, "dashboard_title": "Sales"}],
                    "count": 1,
                    "total_count": 1,
                    "page": 1,
                    "page_size": 1000,
                },
                "get_dashboard_info": {
                    "id": 10,
                    "dashboard_title": "Executive Dashboard",
                    "slug": "exec",
                },
                "list_charts": {
                    "charts": [{"id": 2, "slice_name": "Revenue", "viz_type": "bar"}],
                    "count": 1,
                    "total_count": 1,
                    "page": 1,
                    "page_size": 1000,
                },
                "get_chart_info": {
                    "id": 2,
                    "slice_name": "Revenue",
                    "viz_type": "bar",
                },
                "list_datasets": {
                    "datasets": [
                        {
                            "id": 3,
                            "table_name": "birth_names",
                            "schema": "main",
                            "database_name": "examples",
                        }
                    ],
                    "count": 1,
                    "total_count": 1,
                    "page": 1,
                    "page_size": 1000,
                },
                "get_dataset_info": {
                    "id": 3,
                    "table_name": "birth_names",
                    "schema": "main",
                    "database_name": "examples",
                },
                "execute_sql": {
                    "success": True,
                    "rows": [{"name": "Alice"}],
                    "columns": [{"name": "name", "type": "VARCHAR"}],
                    "row_count": 1,
                    "execution_time": 0.02,
                    "query_id": "q-1",
                },
            }
        )
        adapter = LegacyCompatAdapter(BuiltInMCPClient(transport))

        dashboards = await adapter.call_tool("superset_dashboard_list")
        self.assertEqual(dashboards["count"], 1)
        self.assertEqual(dashboards["result"][0]["dashboard_title"], "Sales")

        dashboard = await adapter.call_tool(
            "superset_dashboard_get_by_id", {"dashboard_id": 10}
        )
        self.assertEqual(dashboard["slug"], "exec")

        charts = await adapter.call_tool("superset_chart_list")
        self.assertEqual(charts["result"][0]["viz_type"], "bar")

        chart = await adapter.call_tool("superset_chart_get_by_id", {"chart_id": 2})
        self.assertEqual(chart["slice_name"], "Revenue")

        datasets = await adapter.call_tool("superset_dataset_list")
        self.assertEqual(datasets["result"][0]["table_name"], "birth_names")

        dataset = await adapter.call_tool(
            "superset_dataset_get_by_id", {"dataset_id": 3}
        )
        self.assertEqual(dataset["database_name"], "examples")

        sql = await adapter.call_tool(
            "superset_sqllab_execute_query",
            {"database_id": 7, "sql": "SELECT name FROM users", "schema": "public"},
        )
        self.assertTrue(sql["success"])
        self.assertEqual(sql["rows"][0]["name"], "Alice")

        self.assertEqual(
            transport.calls[0],
            ("list_dashboards", {"request": {"page": 1, "page_size": 1000}}),
        )
        self.assertEqual(
            transport.calls[6],
            (
                "execute_sql",
                {
                    "request": {
                        "database_id": 7,
                        "sql": "SELECT name FROM users",
                        "schema": "public",
                    }
                },
            ),
        )

    async def test_unsupported_auth_tool_does_not_expose_token_material(self):
        adapter = LegacyCompatAdapter(BuiltInMCPClient(FakeTransport()))

        with self.assertRaises(MCPClientError) as ctx:
            await adapter.call_tool(
                "superset_auth_authenticate_user",
                {"username": "admin", "password": "secret"},
            )

        err = ctx.exception
        self.assertEqual(err.code, MCPErrorCode.UNSUPPORTED_TOOL)
        payload = str(err.to_dict())
        self.assertNotIn("secret", payload)
        self.assertNotIn("token", payload.casefold())

    async def test_database_get_tables_is_not_supported_for_dataset_scoped_flows(self):
        adapter = LegacyCompatAdapter(BuiltInMCPClient(FakeTransport()))

        with self.assertRaises(MCPClientError) as ctx:
            await adapter.call_tool("superset_database_get_tables", {"database_id": 2})

        self.assertEqual(ctx.exception.code, MCPErrorCode.UNSUPPORTED_TOOL)
