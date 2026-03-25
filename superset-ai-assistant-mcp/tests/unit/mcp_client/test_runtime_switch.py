import unittest
from unittest.mock import patch

from backend.mcp_client.runtime import create_product_mcp_runtime
from backend.mcp_client.tool_registry import (
    DEFAULT_RUNTIME,
    build_built_in_stdio_server_config,
    get_runtime_attempt_order,
)


class FakeMCPClient:
    def __init__(self, config):
        self.config = config
        self.closed = False

    async def close_all_sessions(self):
        self.closed = True


class FakeToolTransport:
    should_fail = False

    def __init__(self, *, mcp_config=None, server_name="superset"):
        self.mcp_config = mcp_config or {}
        self.server_name = server_name
        self.closed = False

    async def list_tools(self):
        if self.should_fail:
            raise RuntimeError("built-in startup failed")
        return ["list_datasets", "get_dataset_info"]

    async def close(self):
        self.closed = True


class TestRuntimeSwitch(unittest.IsolatedAsyncioTestCase):
    def test_default_runtime_is_built_in_stdio(self):
        self.assertEqual(DEFAULT_RUNTIME, "built_in_stdio")
        self.assertEqual(get_runtime_attempt_order(), ("built_in_stdio", "legacy"))

    def test_stdio_command_override(self):
        with patch.dict(
            "os.environ",
            {
                "SUPERSET_BUILT_IN_MCP_COMMAND": "/tmp/custom-mcp-launcher.sh",
                "SUPERSET_BUILT_IN_MCP_ARGS": "--flag value",
            },
            clear=False,
        ):
            config = build_built_in_stdio_server_config()

        self.assertEqual(config["command"], "/tmp/custom-mcp-launcher.sh")
        self.assertEqual(config["args"], ["--flag", "value"])
        self.assertEqual(config["env"]["FASTMCP_TRANSPORT"], "stdio")

    async def test_runtime_creation_prefers_built_in_when_preflight_passes(self):
        def fake_from_dict(config):
            return FakeMCPClient(config)

        FakeToolTransport.should_fail = False
        with patch("backend.mcp_client.runtime.MCPClient.from_dict", side_effect=fake_from_dict):
            with patch("backend.mcp_client.runtime.McpUseToolTransport", FakeToolTransport):
                runtime = await create_product_mcp_runtime(
                    requested_runtime="built_in_stdio",
                    fallback_runtime="legacy",
                    legacy_python_resolver=lambda: "/usr/bin/python3",
                    legacy_server_path_resolver=lambda: "/tmp/legacy.py",
                )

        self.assertEqual(runtime.runtime_name, "built_in_stdio")
        self.assertIsNotNone(runtime.product_client)
        self.assertIsNotNone(runtime.legacy_adapter)
        self.assertEqual(runtime.tool_names, ("list_datasets", "get_dataset_info"))
        await runtime.close()

    async def test_runtime_creation_falls_back_to_legacy(self):
        def fake_from_dict(config):
            return FakeMCPClient(config)

        FakeToolTransport.should_fail = True
        with patch("backend.mcp_client.runtime.MCPClient.from_dict", side_effect=fake_from_dict):
            with patch("backend.mcp_client.runtime.McpUseToolTransport", FakeToolTransport):
                runtime = await create_product_mcp_runtime(
                    requested_runtime="built_in_stdio",
                    fallback_runtime="legacy",
                    legacy_python_resolver=lambda: "/usr/bin/python3",
                    legacy_server_path_resolver=lambda: "/tmp/legacy.py",
                )

        self.assertEqual(runtime.runtime_name, "legacy")
        self.assertIsNone(runtime.product_client)
        self.assertIsNone(runtime.legacy_adapter)
        await runtime.close()
