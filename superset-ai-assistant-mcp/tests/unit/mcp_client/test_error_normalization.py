import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.mcp_client.base import ToolTransport
from backend.mcp_client.built_in_client import BuiltInMCPClient
from backend.mcp_client.errors import MCPClientError, MCPErrorCode
from backend.observability import bind_log_context


class FakeTransport(ToolTransport):
    def __init__(self, *, responses=None, exceptions=None):
        self.responses = responses or {}
        self.exceptions = exceptions or {}

    async def call_tool(self, tool_name, arguments=None):
        if tool_name in self.exceptions:
            raise self.exceptions[tool_name]
        return self.responses[tool_name]


class FakeToolResult:
    def __init__(self, structured_content, *, is_error=False):
        self.structured_content = structured_content
        self.isError = is_error


class TestBuiltInClientErrorNormalization(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.log_dir = tempfile.TemporaryDirectory()
        self.env_patcher = patch.dict(
            os.environ,
            {"ASSISTANT_LOG_DIR": self.log_dir.name},
            clear=False,
        )
        self.env_patcher.start()
        self.addCleanup(self.env_patcher.stop)
        self.addCleanup(self.log_dir.cleanup)

    def _read_log_events(self, filename: str) -> list[dict]:
        path = Path(self.log_dir.name) / filename
        if not path.exists():
            return []
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    async def test_unwraps_single_result_mapping_for_info_tools(self):
        client = BuiltInMCPClient(
            FakeTransport(
                responses={
                    "get_dataset_info": {
                        "result": {
                            "id": 25,
                            "table_name": "birth_names",
                            "database_id": 1,
                        }
                    }
                }
            )
        )

        payload = await client.get_dataset_info(25)

        self.assertEqual(payload["id"], 25)
        self.assertEqual(payload["table_name"], "birth_names")
        self.assertEqual(payload["database_id"], 1)

    async def test_normalizes_error_categories(self):
        scenarios = [
            (
                "get_dashboard_info",
                {"error": "Dashboard with ID 999 not found", "error_type": "NotFoundError"},
                MCPErrorCode.NOT_FOUND,
            ),
            (
                "execute_sql",
                {"success": False, "error": "Access denied to database", "error_type": "SECURITY_ERROR"},
                MCPErrorCode.ACCESS_DENIED,
            ),
            (
                "list_datasets",
                {"error": "Validation failed: field required", "error_type": "ValidationError"},
                MCPErrorCode.INVALID_PAYLOAD,
            ),
            (
                "execute_sql",
                {"success": False, "error": "DML queries are not allowed", "error_type": "DML_NOT_ALLOWED"},
                MCPErrorCode.DML_DENIED,
            ),
        ]

        for tool_name, response, expected_code in scenarios:
            client = BuiltInMCPClient(FakeTransport(responses={tool_name: response}))
            with self.subTest(tool_name=tool_name, expected_code=expected_code):
                with self.assertRaises(MCPClientError) as ctx:
                    await client.call_tool(tool_name, {"request": {}})
                self.assertEqual(ctx.exception.code, expected_code)

    async def test_normalizes_timeout_transport_errors(self):
        client = BuiltInMCPClient(
            FakeTransport(exceptions={"execute_sql": TimeoutError("Request timeout")})
        )

        with self.assertRaises(MCPClientError) as ctx:
            await client.execute_sql({"database_id": 1, "sql": "SELECT 1"})

        self.assertEqual(ctx.exception.code, MCPErrorCode.TIMEOUT)

    async def test_normalizes_is_error_results_into_typed_errors(self):
        client = BuiltInMCPClient(
            FakeTransport(
                responses={
                    "execute_sql": FakeToolResult(
                        {
                            "error": "Permission denied for database",
                            "error_type": "PermissionError",
                        },
                        is_error=True,
                    )
                }
            )
        )

        with self.assertRaises(MCPClientError) as ctx:
            await client.execute_sql({"database_id": 1, "sql": "SELECT 1"})

        self.assertEqual(ctx.exception.code, MCPErrorCode.ACCESS_DENIED)

    async def test_redacts_token_material_from_error_details(self):
        client = BuiltInMCPClient(
            FakeTransport(
                responses={
                    "execute_sql": {
                        "success": False,
                        "error": "Access denied",
                        "error_type": "SECURITY_ERROR",
                        "details": {
                            "access_token": "secret-token",
                            "token_preview": "preview",
                            "password": "pw",
                            "safe_value": "ok",
                        },
                    }
                }
            )
        )

        with self.assertRaises(MCPClientError) as ctx:
            await client.execute_sql({"database_id": 1, "sql": "SELECT 1"})

        payload = str(ctx.exception.to_dict())
        self.assertIn("safe_value", payload)
        self.assertNotIn("secret-token", payload)
        self.assertNotIn("preview", payload)
        self.assertNotIn("password", payload.casefold())

    async def test_emits_structured_mcp_logs_without_raw_sql_payloads(self):
        client = BuiltInMCPClient(
            FakeTransport(
                responses={
                    "execute_sql": {
                        "success": True,
                        "rows": [{"region": "RU", "sales": 10}],
                    }
                }
            )
        )

        with bind_log_context(
            trace_id="trace-mcp",
            request_id="request-mcp",
            session_id="session-alice",
            chat_id="session-alice",
            user_hash="userhash",
        ):
            payload = await client.execute_sql(
                {"database_id": 1, "sql": "SELECT * FROM sales WHERE token='secret'"}
            )

        self.assertEqual(payload["rows"][0]["region"], "RU")
        events = self._read_log_events("mcp.log")
        event_names = [item.get("event") for item in events]
        self.assertIn("tool_call_start", event_names)
        self.assertIn("tool_call_end", event_names)
        serialized = json.dumps(events, ensure_ascii=False)
        self.assertIn("trace-mcp", serialized)
        self.assertNotIn("SELECT * FROM sales", serialized)
        self.assertNotIn("secret", serialized)
