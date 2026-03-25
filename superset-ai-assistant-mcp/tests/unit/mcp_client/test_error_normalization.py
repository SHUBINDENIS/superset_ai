import unittest

from backend.mcp_client.base import ToolTransport
from backend.mcp_client.built_in_client import BuiltInMCPClient
from backend.mcp_client.errors import MCPClientError, MCPErrorCode


class FakeTransport(ToolTransport):
    def __init__(self, *, responses=None, exceptions=None):
        self.responses = responses or {}
        self.exceptions = exceptions or {}

    async def call_tool(self, tool_name, arguments=None):
        if tool_name in self.exceptions:
            raise self.exceptions[tool_name]
        return self.responses[tool_name]


class TestBuiltInClientErrorNormalization(unittest.IsolatedAsyncioTestCase):
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
