from __future__ import annotations

import re
from typing import Any, NoReturn

from jsonschema_pydantic import jsonschema_to_pydantic
from langchain_core.tools import BaseTool
from mcp.types import CallToolResult, Prompt
from mcp.types import Tool as MCPTool
from pydantic import BaseModel, Field, create_model

from mcp_use.agents.adapters.langchain_adapter import LangChainAdapter
from mcp_use.client.connectors.base import BaseConnector
from mcp_use.errors.error_formatting import format_error
from mcp_use.logging import logger


_VALID_OPENAI_TOOL_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def sanitize_openai_tool_name(name: str) -> str:
    raw = str(name or "").strip()
    if not raw:
        return "tool"
    if _VALID_OPENAI_TOOL_NAME_RE.fullmatch(raw):
        return raw

    sanitized = re.sub(r"[^A-Za-z0-9_-]+", "_", raw).strip("_")
    if not sanitized:
        sanitized = "tool"
    if sanitized[0].isdigit():
        sanitized = f"tool_{sanitized}"
    return sanitized


class OpenAISafeLangChainAdapter(LangChainAdapter):
    """LangChain adapter that exposes OpenAI-safe tool names while preserving MCP calls."""

    def _convert_tool(self, mcp_tool: MCPTool, connector: BaseConnector) -> BaseTool | None:
        if mcp_tool.name in self.disallowed_tools:
            return None

        adapter_self = self
        original_name = mcp_tool.name or "NO NAME"
        public_name = sanitize_openai_tool_name(original_name)
        description_text = mcp_tool.description or ""
        if public_name != original_name:
            description_text = (
                f"{description_text}\n\n"
                f"Original MCP tool name: {original_name}"
            ).strip()

        class McpToLangChainAdapter(BaseTool):
            name: str = public_name
            description: str = description_text
            args_schema: type[BaseModel] = jsonschema_to_pydantic(
                adapter_self.fix_schema(mcp_tool.inputSchema)
            )
            tool_connector: BaseConnector = connector
            original_tool_name: str = original_name
            handle_tool_error: bool = True

            def __repr__(self) -> str:
                return f"MCP tool: {self.original_tool_name} as {self.name}: {self.description}"

            def _run(self, **kwargs: Any) -> NoReturn:
                raise NotImplementedError("MCP tools only support async operations")

            async def _arun(self, **kwargs: Any) -> str | dict:
                logger.debug(f'MCP tool alias: "{self.name}" ({self.original_tool_name}) received input: {kwargs}')

                try:
                    tool_result: CallToolResult = await self.tool_connector.call_tool(
                        self.original_tool_name, kwargs
                    )
                    try:
                        return str(tool_result.content)
                    except Exception as e:
                        logger.error(f"Error parsing tool result: {e}")
                        return format_error(e, tool=self.original_tool_name, tool_content=tool_result.content)
                except Exception as e:
                    if self.handle_tool_error:
                        return format_error(e, tool=self.original_tool_name)
                    raise

        return McpToLangChainAdapter()

    def _convert_prompt(self, mcp_prompt: Prompt, connector: BaseConnector) -> BaseTool:
        prompt_arguments = mcp_prompt.arguments
        original_name = mcp_prompt.name
        public_name = sanitize_openai_tool_name(original_name)

        base_model_name = re.sub(r"[^a-zA-Z0-9_]", "_", public_name)
        if not base_model_name or base_model_name[0].isdigit():
            base_model_name = "PromptArgs_" + base_model_name
        dynamic_model_name = f"{base_model_name}_InputSchema"

        if prompt_arguments:
            field_definitions_for_create: dict[str, Any] = {}
            for arg in prompt_arguments:
                param_type: type = getattr(arg, "type", str)
                if arg.required:
                    field_definitions_for_create[arg.name] = (
                        param_type,
                        Field(description=arg.description),
                    )
                else:
                    field_definitions_for_create[arg.name] = (
                        param_type | None,
                        Field(None, description=arg.description),
                    )
            input_schema = create_model(dynamic_model_name, **field_definitions_for_create, __base__=BaseModel)
        else:
            input_schema = create_model(dynamic_model_name, __base__=BaseModel)

        description_text = mcp_prompt.description or ""
        if public_name != original_name:
            description_text = (
                f"{description_text}\n\n"
                f"Original MCP prompt name: {original_name}"
            ).strip()

        class PromptTool(BaseTool):
            name: str = public_name
            description: str = description_text
            args_schema: type[BaseModel] = input_schema
            tool_connector: BaseConnector = connector
            original_prompt_name: str = original_name
            handle_tool_error: bool = True

            def _run(self, **kwargs: Any) -> NoReturn:
                raise NotImplementedError("Prompt tools only support async operations")

            async def _arun(self, **kwargs: Any) -> Any:
                logger.debug(
                    f'Prompt tool alias: "{self.name}" ({self.original_prompt_name}) called with args: {kwargs}'
                )
                try:
                    result = await self.tool_connector.get_prompt(self.original_prompt_name, kwargs)
                    return result.messages
                except Exception as e:
                    if self.handle_tool_error:
                        return format_error(e, tool=self.original_prompt_name)
                    raise

        return PromptTool()
