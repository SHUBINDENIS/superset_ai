import unittest
from unittest.mock import AsyncMock

from mcp.types import CallToolResult, Prompt, Tool

from backend.openai_safe_adapter import OpenAISafeLangChainAdapter, sanitize_openai_tool_name


class DummyConnector:
    def __init__(self):
        self.call_tool = AsyncMock()
        self.get_prompt = AsyncMock()


class TestOpenAISafeAdapter(unittest.IsolatedAsyncioTestCase):
    def test_sanitize_openai_tool_name_preserves_valid_names(self):
        self.assertEqual(sanitize_openai_tool_name("list_datasets"), "list_datasets")
        self.assertEqual(sanitize_openai_tool_name("generate-chart"), "generate-chart")

    def test_sanitize_openai_tool_name_rewrites_dotted_names(self):
        self.assertEqual(
            sanitize_openai_tool_name("mcp_ext.list_databases"),
            "mcp_ext_list_databases",
        )
        self.assertEqual(
            sanitize_openai_tool_name("123.bad/tool"),
            "tool_123_bad_tool",
        )

    async def test_adapter_exposes_openai_safe_name_but_calls_original_tool(self):
        connector = DummyConnector()
        connector.call_tool.return_value = CallToolResult(
            content=[{"type": "text", "text": "ok"}],
            isError=False,
        )
        adapter = OpenAISafeLangChainAdapter()
        tool = Tool(
            name="mcp_ext.list_databases",
            description="List databases",
            inputSchema={"type": "object", "properties": {}},
        )

        converted = adapter._convert_tool(tool, connector)

        self.assertEqual(converted.name, "mcp_ext_list_databases")
        await converted._arun()
        connector.call_tool.assert_awaited_once_with("mcp_ext.list_databases", {})

    async def test_adapter_sanitizes_prompt_name_but_calls_original_prompt(self):
        connector = DummyConnector()
        connector.get_prompt.return_value = type("PromptResult", (), {"messages": ["ok"]})()
        adapter = OpenAISafeLangChainAdapter()
        prompt = Prompt(
            name="mcp.prompt/example",
            description="Example prompt",
            arguments=[],
        )

        converted = adapter._convert_prompt(prompt, connector)

        self.assertEqual(converted.name, "mcp_prompt_example")
        await converted._arun()
        connector.get_prompt.assert_awaited_once_with("mcp.prompt/example", {})
