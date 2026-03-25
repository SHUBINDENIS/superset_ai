from __future__ import annotations

import os
import shlex
import sys
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from backend.mcp_client.errors import (
    MCPClientError,
    MCPErrorCode,
    unsupported_tool_error,
)


DEFAULT_SERVER_NAME = "superset"
DEFAULT_LIST_PAGE_SIZE = 1000
DEFAULT_RUNTIME = "built_in_stdio"
DEFAULT_FALLBACK_RUNTIME = "none"
SUPPORTED_PRODUCT_RUNTIMES: tuple[str, ...] = (
    "built_in_stdio",
    "built_in_http",
    "legacy",
)


REQUIRED_DIRECT_BUILTIN_TOOLS: tuple[str, ...] = (
    "list_dashboards",
    "get_dashboard_info",
    "list_charts",
    "get_chart_info",
    "list_datasets",
    "get_dataset_info",
    "execute_sql",
    "open_sql_lab_with_context",
    "generate_chart",
    "update_chart",
    "generate_dashboard",
    "add_chart_to_existing_dashboard",
    "generate_explore_link",
)

INITIAL_DIRECT_BUILTIN_TOOLS: tuple[str, ...] = (
    "list_dashboards",
    "get_dashboard_info",
    "list_charts",
    "get_chart_info",
    "list_datasets",
    "get_dataset_info",
    "execute_sql",
)

REQUIRED_CUSTOM_EXTENSION_TOOLS: tuple[str, ...] = (
    "mcp_ext.list_databases",
    "mcp_ext.create_empty_dashboard",
    "mcp_ext.legacy_chart_create",
)


def _legacy_list_request(arguments: Mapping[str, Any] | None = None) -> dict[str, Any]:
    args = dict(arguments or {})
    request: dict[str, Any] = {
        "page": int(args.pop("page", 1) or 1),
        "page_size": int(args.pop("page_size", DEFAULT_LIST_PAGE_SIZE) or DEFAULT_LIST_PAGE_SIZE),
    }
    for key in (
        "filters",
        "search",
        "select_columns",
        "order_column",
        "order_direction",
    ):
        if key in args and args[key] is not None:
            request[key] = args[key]
    return {"request": request}


def _require_argument(arguments: Mapping[str, Any] | None, key: str) -> Any:
    value = None if arguments is None else arguments.get(key)
    if value is None or value == "":
        raise MCPClientError(
            code=MCPErrorCode.INVALID_PAYLOAD,
            message=f"Missing required parameter: {key}",
            tool_name=key,
        )
    return value


def _legacy_get_request(
    arguments: Mapping[str, Any] | None, *, source_key: str
) -> dict[str, Any]:
    return {"request": {"identifier": _require_argument(arguments, source_key)}}


def _legacy_execute_sql_request(arguments: Mapping[str, Any] | None) -> dict[str, Any]:
    args = dict(arguments or {})
    database_id = _require_argument(args, "database_id")
    sql = _require_argument(args, "sql")
    request: dict[str, Any] = {
        "database_id": int(database_id),
        "sql": str(sql),
    }
    if args.get("schema"):
        request["schema"] = args["schema"]
    if args.get("schema_name"):
        request["schema"] = args["schema_name"]
    if args.get("limit") is not None:
        request["limit"] = int(args["limit"])
    if args.get("timeout") is not None:
        request["timeout"] = int(args["timeout"])
    if args.get("parameters") is not None:
        request["parameters"] = args["parameters"]
    return {"request": request}


def _normalize_list_response(payload: Mapping[str, Any], result_key: str) -> dict[str, Any]:
    items = list(payload.get(result_key, []) or [])
    return {
        "count": int(payload.get("total_count", payload.get("count", len(items))) or 0),
        "result": items,
        "page": payload.get("page"),
        "page_size": payload.get("page_size"),
    }


def _normalize_info_response(payload: Mapping[str, Any]) -> dict[str, Any]:
    return dict(payload)


def _normalize_execute_sql_response(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "success": bool(payload.get("success", False)),
        "rows": payload.get("rows"),
        "columns": payload.get("columns"),
        "row_count": payload.get("row_count"),
        "affected_rows": payload.get("affected_rows"),
        "query_id": payload.get("query_id"),
        "execution_time": payload.get("execution_time"),
        "error": payload.get("error"),
        "error_type": payload.get("error_type"),
    }


@dataclass(frozen=True)
class LegacyToolMapping:
    legacy_tool: str
    built_in_tool: str
    request_builder: Callable[[Mapping[str, Any] | None], dict[str, Any]]
    response_normalizer: Callable[[Mapping[str, Any]], dict[str, Any]]
    note: str = ""


LEGACY_TOOL_MAPPINGS: dict[str, LegacyToolMapping] = {
    "superset_dashboard_list": LegacyToolMapping(
        legacy_tool="superset_dashboard_list",
        built_in_tool="list_dashboards",
        request_builder=_legacy_list_request,
        response_normalizer=lambda payload: _normalize_list_response(
            payload, "dashboards"
        ),
        note="Adapter preserves list semantics without legacy auth helpers.",
    ),
    "superset_dashboard_get_by_id": LegacyToolMapping(
        legacy_tool="superset_dashboard_get_by_id",
        built_in_tool="get_dashboard_info",
        request_builder=lambda args: _legacy_get_request(args, source_key="dashboard_id"),
        response_normalizer=_normalize_info_response,
    ),
    "superset_chart_list": LegacyToolMapping(
        legacy_tool="superset_chart_list",
        built_in_tool="list_charts",
        request_builder=_legacy_list_request,
        response_normalizer=lambda payload: _normalize_list_response(payload, "charts"),
    ),
    "superset_chart_get_by_id": LegacyToolMapping(
        legacy_tool="superset_chart_get_by_id",
        built_in_tool="get_chart_info",
        request_builder=lambda args: _legacy_get_request(args, source_key="chart_id"),
        response_normalizer=_normalize_info_response,
    ),
    "superset_dataset_list": LegacyToolMapping(
        legacy_tool="superset_dataset_list",
        built_in_tool="list_datasets",
        request_builder=_legacy_list_request,
        response_normalizer=lambda payload: _normalize_list_response(
            payload, "datasets"
        ),
    ),
    "superset_dataset_get_by_id": LegacyToolMapping(
        legacy_tool="superset_dataset_get_by_id",
        built_in_tool="get_dataset_info",
        request_builder=lambda args: _legacy_get_request(args, source_key="dataset_id"),
        response_normalizer=_normalize_info_response,
    ),
    "superset_sqllab_execute_query": LegacyToolMapping(
        legacy_tool="superset_sqllab_execute_query",
        built_in_tool="execute_sql",
        request_builder=_legacy_execute_sql_request,
        response_normalizer=_normalize_execute_sql_response,
    ),
}

SUPPORTED_LEGACY_TOOLS: tuple[str, ...] = tuple(LEGACY_TOOL_MAPPINGS.keys())


def get_legacy_mapping(tool_name: str) -> LegacyToolMapping:
    mapping = LEGACY_TOOL_MAPPINGS.get(tool_name)
    if mapping is None:
        raise unsupported_tool_error(tool_name)
    return mapping


def normalize_runtime_name(value: str | None) -> str:
    normalized = str(value or "").strip().casefold()
    if normalized not in SUPPORTED_PRODUCT_RUNTIMES:
        raise ValueError(
            "Unsupported SUPERSET_PRODUCT_MCP_RUNTIME value: "
            f"{value!r}"
        )
    return normalized


def get_runtime_attempt_order(
    runtime: str | None = None,
    fallback_runtime: str | None = None,
) -> tuple[str, ...]:
    primary = normalize_runtime_name(
        runtime or os.getenv("SUPERSET_PRODUCT_MCP_RUNTIME", DEFAULT_RUNTIME)
    )
    raw_fallback = (
        fallback_runtime
        if fallback_runtime is not None
        else os.getenv("SUPERSET_PRODUCT_MCP_FALLBACK_RUNTIME", DEFAULT_FALLBACK_RUNTIME)
    )
    normalized_fallback = str(raw_fallback or "").strip().casefold()
    if not normalized_fallback or normalized_fallback in {"none", "off", "disabled"}:
        return (primary,)
    secondary = normalize_runtime_name(normalized_fallback)
    if secondary == primary:
        return (primary,)
    return (primary, secondary)


def build_built_in_stdio_server_config() -> dict[str, Any]:
    explicit_command = str(os.getenv("SUPERSET_BUILT_IN_MCP_COMMAND", "")).strip()
    explicit_args = shlex.split(str(os.getenv("SUPERSET_BUILT_IN_MCP_ARGS", "")).strip())
    if explicit_command:
        return {
            "command": explicit_command,
            "args": explicit_args,
            "env": {
                "FASTMCP_TRANSPORT": "stdio",
            },
        }

    python_cmd = str(
        os.getenv("SUPERSET_BUILT_IN_MCP_PYTHON", "") or sys.executable
    ).strip() or sys.executable
    module_name = str(
        os.getenv("SUPERSET_BUILT_IN_MCP_MODULE", "superset.mcp_service")
    ).strip() or "superset.mcp_service"
    extra_args = shlex.split(str(os.getenv("SUPERSET_BUILT_IN_MCP_EXTRA_ARGS", "")).strip())
    env = {
        "FASTMCP_TRANSPORT": "stdio",
    }
    return {
        "command": python_cmd,
        "args": ["-m", module_name, *extra_args],
        "env": env,
    }


def build_built_in_http_server_config() -> dict[str, Any]:
    url = str(os.getenv("SUPERSET_BUILT_IN_MCP_URL", "")).strip()
    if not url:
        raise ValueError(
            "SUPERSET_BUILT_IN_MCP_URL is required for built_in_http runtime."
        )
    timeout = float(os.getenv("SUPERSET_BUILT_IN_MCP_TIMEOUT", "5") or 5)
    sse_read_timeout = float(
        os.getenv("SUPERSET_BUILT_IN_MCP_SSE_READ_TIMEOUT", "300") or 300
    )
    return {
        "url": url,
        "timeout": timeout,
        "sse_read_timeout": sse_read_timeout,
    }


def build_legacy_stdio_server_config(
    *,
    python_resolver: Callable[[], str],
    server_path_resolver: Callable[[], str],
) -> dict[str, Any]:
    return {
        "command": python_resolver(),
        "args": [server_path_resolver()],
    }


def build_agent_mcp_use_config(
    *,
    runtime: str | None = None,
    legacy_python_resolver: Callable[[], str] | None = None,
    legacy_server_path_resolver: Callable[[], str] | None = None,
) -> dict[str, Any]:
    selected_runtime = normalize_runtime_name(
        runtime or os.getenv("SUPERSET_PRODUCT_MCP_RUNTIME", DEFAULT_RUNTIME)
    )

    if selected_runtime == "built_in_http":
        server_config = build_built_in_http_server_config()
    elif selected_runtime == "built_in_stdio":
        server_config = build_built_in_stdio_server_config()
    elif selected_runtime == "legacy":
        if legacy_python_resolver is None or legacy_server_path_resolver is None:
            raise ValueError(
                "Legacy runtime requires both python and server path resolvers."
            )
        server_config = build_legacy_stdio_server_config(
            python_resolver=legacy_python_resolver,
            server_path_resolver=legacy_server_path_resolver,
        )

    return {"mcpServers": {DEFAULT_SERVER_NAME: server_config}}


def build_agent_runtime_guidance(superset_public_url: str) -> str:
    return (
        "- Работай только с инструментами Superset MCP.\n"
        "- Аутентификация уже должна быть обеспечена настроенным MCP runtime; "
        "не пытайся выполнять логин, запрашивать токены или опираться на token-based helper tools.\n"
        "- Для browse и detailed info используй профильные dataset/chart/dashboard инструменты.\n"
        "- Для SQL используй execute_sql и соблюдай guardrails на DML/DDL.\n"
        f"- Для всех ссылок на Superset используй базовый URL: {superset_public_url}.\n"
        "- Если в запросе есть scope (база/таблица), сначала резолвь dataset через dataset-level инструменты.\n"
        "- Не используй database/tables endpoint как обязательный шаг для dataset-scoped flows.\n"
        "- Если пользователь указал таблицу/датасет, не подменяй datasource.\n"
        "- Если данных недостаточно или возникает ошибка инструмента, задай до 3 уточняющих вопросов "
        "про таблицу/метрику/период вместо общего отказа.\n"
    )
