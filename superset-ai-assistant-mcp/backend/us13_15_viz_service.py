"""
US13-US15 service:
- US13: preview query result + column explanations
- US14: chart type recommendations
- US15: save chart as dashboard widget + share links
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse, urlunparse

import httpx
from dotenv import load_dotenv

from backend.mcp_client.built_in_client import (
    _extract_result_payload,
    _unwrap_single_result_mapping,
)
from backend.mcp_client.runtime import ProductMCPRuntime, create_product_mcp_runtime
from backend.mcp_client.tool_registry import DEFAULT_SERVER_NAME


load_dotenv(Path(__file__).resolve().parent.parent / ".env")


COMMON_VIZ_TYPES = ["table", "line", "bar", "pie", "scatter", "area"]
DEFAULT_PUBLIC_SUPERSET_URL = "http://103.54.18.91:8088"


def _normalize_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def _extract_result_items(payload: Dict[str, Any]) -> List[Any]:
    if not isinstance(payload, dict):
        return []

    result = payload.get("result")
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        nested = result.get("result")
        if isinstance(nested, list):
            return nested
    return []


def _extract_rows(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not isinstance(payload, dict):
        return []

    candidates: List[Any] = [
        payload.get("data"),
        payload.get("result"),
    ]

    result = payload.get("result")
    if isinstance(result, dict):
        candidates.append(result.get("data"))
        candidates.append(result.get("result"))
    elif isinstance(result, list) and result:
        first = result[0]
        if isinstance(first, dict):
            candidates.append(first.get("data"))

    for candidate in candidates:
        if isinstance(candidate, list) and all(isinstance(x, dict) for x in candidate):
            return candidate

    return []


def _is_numeric(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, str):
        token = value.strip().replace(" ", "")
        if not token:
            return False
        token = token.replace(",", ".")
        return bool(re.fullmatch(r"[-+]?\d+(?:\.\d+)?", token))
    return False


def _is_temporal(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    token = value.strip()
    if not token:
        return False
    patterns = [
        r"^\d{4}-\d{2}-\d{2}$",
        r"^\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}(:\d{2})?",
        r"^\d{2}\.\d{2}\.\d{4}$",
    ]
    return any(re.fullmatch(pattern, token) for pattern in patterns)


def _infer_unit(column_name: str) -> str:
    name = _normalize_text(column_name).casefold()
    if not name:
        return ""

    mapping = [
        (r"(percent|pct|процент)", "%"),
        (r"(amount|price|cost|revenue|sales|income|выруч|цен|стоим)", "currency"),
        (r"(count|qty|quantity|колич|числ)", "count"),
        (r"(date|time|day|month|year|дат|врем)", "datetime"),
        (r"(rate|ratio|дол|коэфф)", "ratio"),
    ]
    for pattern, unit in mapping:
        if re.search(pattern, name):
            return unit
    return ""


@dataclass
class US13To15VizService:
    base_url: str
    username: str
    password: str
    timeout_seconds: float = 30.0
    default_preview_limit: int = 20
    share_base_url: str = ""
    _loop: asyncio.AbstractEventLoop | None = field(
        default=None,
        init=False,
        repr=False,
    )
    _mcp_runtime: ProductMCPRuntime | None = field(
        default=None,
        init=False,
        repr=False,
    )
    _legacy_session: Any = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self.base_url = self._normalize_base_url(
            self.base_url,
            fallback=DEFAULT_PUBLIC_SUPERSET_URL,
        )
        self.share_base_url = self._normalize_base_url(
            self.share_base_url or self.base_url,
            fallback=self.base_url,
        )
        base_netloc = urlparse(self.base_url).netloc.casefold()
        share_netloc = urlparse(self.share_base_url).netloc.casefold()
        if self._is_localhost_netloc(share_netloc) and not self._is_localhost_netloc(base_netloc):
            # Для внешних ссылок предпочитаем публичный host Superset.
            self.share_base_url = self.base_url
        self._token: Optional[str] = None
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout_seconds,
            follow_redirects=True,
            headers={"Accept": "application/json"},
        )

    @classmethod
    def from_env(cls) -> "US13To15VizService":
        base_url = os.getenv("SUPERSET_BASE_URL", DEFAULT_PUBLIC_SUPERSET_URL)
        username = os.getenv("SUPERSET_USERNAME", "")
        password = os.getenv("SUPERSET_PASSWORD", "")
        timeout = float(os.getenv("US13_15_TIMEOUT_SECONDS", "30"))
        preview_limit = int(os.getenv("US13_PREVIEW_LIMIT", "20"))
        public_base = os.getenv("SUPERSET_PUBLIC_URL", "").strip()
        share_base = os.getenv("US15_SHARE_BASE_URL", "").strip()
        return cls(
            base_url=base_url,
            username=username,
            password=password,
            timeout_seconds=timeout,
            default_preview_limit=preview_limit,
            share_base_url=public_base or share_base,
        )

    def close(self) -> None:
        if self._mcp_runtime is not None and self._loop is not None and not self._loop.is_closed():
            self._loop.run_until_complete(self._mcp_runtime.close())
        if self._loop is not None and not self._loop.is_closed():
            self._loop.close()
        self._mcp_runtime = None
        self._legacy_session = None
        self._loop = None
        self._client.close()

    def _get_loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is None or self._loop.is_closed():
            self._loop = asyncio.new_event_loop()
        return self._loop

    def _run_async(self, coro: Any) -> Any:
        return self._get_loop().run_until_complete(coro)

    async def _ensure_mcp_runtime_async(self) -> ProductMCPRuntime:
        if self._mcp_runtime is None:
            self._mcp_runtime = await create_product_mcp_runtime()
        return self._mcp_runtime

    def _ensure_mcp_runtime(self) -> ProductMCPRuntime:
        return self._run_async(self._ensure_mcp_runtime_async())

    async def _get_legacy_session_async(self) -> Any:
        runtime = await self._ensure_mcp_runtime_async()
        if runtime.runtime_name != "legacy":
            raise RuntimeError(
                "Legacy MCP session requested while runtime is not set to legacy."
            )
        if self._legacy_session is None:
            self._legacy_session = await runtime.mcp_use_client.create_session(
                DEFAULT_SERVER_NAME
            )
        return self._legacy_session

    def _get_legacy_session(self) -> Any:
        return self._run_async(self._get_legacy_session_async())

    def _call_product_client(self, method_name: str, *args: Any) -> Dict[str, Any]:
        runtime = self._ensure_mcp_runtime()
        if runtime.product_client is None:
            raise RuntimeError("Built-in product MCP client is not available.")
        method = getattr(runtime.product_client, method_name)
        return self._run_async(method(*args))

    def _call_legacy_tool(
        self, tool_name: str, arguments: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        session = self._get_legacy_session()
        raw_result = self._run_async(session.call_tool(tool_name, dict(arguments or {})))
        payload = _unwrap_single_result_mapping(_extract_result_payload(raw_result))
        if isinstance(payload, dict):
            return payload
        return {"result": payload}

    def _runtime_name(self) -> str:
        return self._ensure_mcp_runtime().runtime_name

    @staticmethod
    def _raise_if_tool_error(payload: Dict[str, Any], *, default_message: str) -> None:
        message = _normalize_text(payload.get("error"))
        if message:
            raise RuntimeError(message)
        if payload.get("success") is False:
            fallback = _normalize_text(payload.get("message")) or default_message
            raise RuntimeError(fallback)

    def authenticate(self, force: bool = False) -> str:
        if self._token and not force:
            return self._token

        if not self.username or not self.password:
            raise RuntimeError("SUPERSET_USERNAME/SUPERSET_PASSWORD are required.")

        payload = {
            "username": self.username,
            "password": self.password,
            "provider": "db",
            "refresh": True,
        }
        response = self._client.post("/api/v1/security/login", json=payload)
        response.raise_for_status()
        data = response.json() if response.content else {}
        token = data.get("access_token")
        if not isinstance(token, str) or not token:
            raise RuntimeError("Superset auth succeeded without access_token.")
        self._token = token
        return token

    def _get_csrf_token(self) -> str:
        self.authenticate()
        headers = {"Authorization": f"Bearer {self._token}"}
        response = self._client.get("/api/v1/security/csrf_token/", headers=headers)
        response.raise_for_status()
        payload = response.json() if response.content else {}
        token = payload.get("result")
        if not isinstance(token, str) or not token:
            raise RuntimeError("Failed to get CSRF token from Superset.")
        return token

    def _request(
        self,
        method: str,
        endpoint: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        requires_auth: bool = True,
        needs_csrf: bool = False,
    ) -> Dict[str, Any]:
        headers: Dict[str, str] = {"Accept": "application/json"}
        if requires_auth:
            self.authenticate()
            headers["Authorization"] = f"Bearer {self._token}"
        if needs_csrf:
            csrf_token = self._get_csrf_token()
            headers["X-CSRFToken"] = csrf_token
            headers["Content-Type"] = "application/json"

        response = self._client.request(
            method.upper(),
            endpoint,
            params=params,
            json=json_body,
            headers=headers,
        )
        response.raise_for_status()
        if not response.content:
            return {}
        return response.json()

    @staticmethod
    def _normalize_database_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        databases: List[Dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            db_id = item.get("id")
            if not isinstance(db_id, int):
                continue
            name = _normalize_text(item.get("database_name") or item.get("name") or "")
            backend = _normalize_text(
                item.get("backend")
                or item.get("engine")
                or item.get("database_backend")
                or ""
            )
            databases.append(
                {
                    "id": db_id,
                    "name": name or f"db_{db_id}",
                    "backend": backend or "unknown",
                }
            )
        return databases

    @staticmethod
    def _normalize_dataset_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        datasets: List[Dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            dataset_id = item.get("id")
            if not isinstance(dataset_id, int):
                continue
            table_name = _normalize_text(
                item.get("table_name")
                or item.get("dataset_name")
                or item.get("name")
                or ""
            )
            schema_name = _normalize_text(item.get("schema") or item.get("schema_name") or "")
            database_id = item.get("database_id")
            if not isinstance(database_id, int):
                database_id = None
                database_obj = item.get("database")
                if isinstance(database_obj, dict) and isinstance(database_obj.get("id"), int):
                    database_id = int(database_obj["id"])
                elif isinstance(database_obj, int):
                    database_id = int(database_obj)
            database_name = _normalize_text(
                item.get("database_name")
                or (
                    item.get("database", {}).get("database_name")
                    if isinstance(item.get("database"), dict)
                    else ""
                )
            )
            datasets.append(
                {
                    "id": dataset_id,
                    "table_name": table_name or f"dataset_{dataset_id}",
                    "schema": schema_name,
                    "database_name": database_name,
                    "database_id": database_id,
                }
            )
        return datasets

    @staticmethod
    def _normalize_dataset_metadata_payload(
        payload: Dict[str, Any], dataset_id: int
    ) -> Dict[str, Any]:
        result = payload.get("result") if isinstance(payload, dict) else None
        if not isinstance(result, dict):
            result = payload if isinstance(payload, dict) else {}

        table_name = _normalize_text(
            result.get("table_name") or result.get("dataset_name") or result.get("name") or ""
        )
        schema_name = _normalize_text(result.get("schema") or result.get("schema_name") or "")

        database_id = result.get("database_id")
        if not isinstance(database_id, int):
            database_id = None
        database_name = _normalize_text(result.get("database_name") or "")

        if isinstance(result.get("database"), dict):
            db_obj = result["database"]
            db_id_value = db_obj.get("id")
            if isinstance(db_id_value, int):
                database_id = db_id_value
            if not database_name:
                database_name = _normalize_text(
                    db_obj.get("database_name") or db_obj.get("name") or ""
                )
        elif isinstance(result.get("database"), int):
            database_id = int(result["database"])

        columns: List[Dict[str, Any]] = []
        columns_payload = result.get("columns")
        if isinstance(columns_payload, list):
            for column in columns_payload:
                if not isinstance(column, dict):
                    continue
                column_name = _normalize_text(
                    column.get("column_name")
                    or column.get("name")
                    or column.get("label")
                    or ""
                )
                if not column_name:
                    continue
                columns.append(
                    {
                        "column_name": column_name,
                        "verbose_name": _normalize_text(column.get("verbose_name") or ""),
                        "type": _normalize_text(
                            column.get("type") or column.get("type_generic") or ""
                        ),
                    }
                )

        metrics: List[str] = []
        metrics_payload = result.get("metrics")
        if isinstance(metrics_payload, list):
            for metric in metrics_payload:
                if not isinstance(metric, dict):
                    continue
                metric_name = _normalize_text(
                    metric.get("metric_name") or metric.get("label") or ""
                )
                if metric_name:
                    metrics.append(metric_name)

        return {
            "id": int(dataset_id),
            "table_name": table_name,
            "schema": schema_name,
            "database_id": database_id,
            "database_name": database_name,
            "columns": columns,
            "metrics": metrics,
        }

    def list_databases(self) -> List[Dict[str, Any]]:
        if self._runtime_name() == "legacy":
            payload = self._call_legacy_tool("superset_database_list")
            items = [x for x in _extract_result_items(payload) if isinstance(x, dict)]
            return self._normalize_database_items(items)

        payload = self._call_product_client(
            "list_databases",
            {"page": 1, "page_size": 1000},
        )
        items = payload.get("databases", [])
        if not isinstance(items, list):
            return []
        return self._normalize_database_items([x for x in items if isinstance(x, dict)])

    def list_datasets(self, limit: int = 200) -> List[Dict[str, Any]]:
        page_size = max(1, min(int(limit), 1000))
        if self._runtime_name() == "legacy":
            payload = self._call_legacy_tool("superset_dataset_list")
            items = [x for x in _extract_result_items(payload) if isinstance(x, dict)]
            return self._normalize_dataset_items(items[:page_size])

        payload = self._call_product_client(
            "list_datasets",
            {"page": 1, "page_size": page_size},
        )
        items = payload.get("datasets", [])
        if not isinstance(items, list):
            return []
        return self._normalize_dataset_items([x for x in items if isinstance(x, dict)])

    def get_dataset_metadata(self, dataset_id: int) -> Dict[str, Any]:
        if self._runtime_name() == "legacy":
            payload = self._call_legacy_tool(
                "superset_dataset_get_by_id",
                {"dataset_id": int(dataset_id)},
            )
            return self._normalize_dataset_metadata_payload(payload, int(dataset_id))

        payload = self._call_product_client("get_dataset_info", int(dataset_id))
        return self._normalize_dataset_metadata_payload(payload, int(dataset_id))

    def preview_sql(
        self,
        *,
        database_id: int,
        sql: str,
        schema: str = "",
        preview_limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        safe_sql = _normalize_text(sql)
        if not safe_sql:
            raise ValueError("SQL query must not be empty.")

        limit = int(preview_limit or self.default_preview_limit)
        limit = max(1, min(limit, 500))

        sql_to_run = safe_sql
        if not re.search(r"\blimit\b", safe_sql.casefold()):
            sql_to_run = f"{safe_sql}\nLIMIT {limit}"

        schema_name = _normalize_text(schema)
        if self._runtime_name() == "legacy":
            result = self._call_legacy_tool(
                "superset_sqllab_execute_query",
                {
                    "database_id": int(database_id),
                    "sql": sql_to_run,
                },
            )
            self._raise_if_tool_error(result, default_message="SQL preview failed.")
            rows = _extract_rows(result)
        else:
            result = self._call_product_client(
                "execute_sql",
                {
                    "database_id": int(database_id),
                    "sql": sql_to_run,
                    "schema": schema_name,
                    "limit": limit,
                },
            )
            self._raise_if_tool_error(result, default_message="SQL preview failed.")
            rows = result.get("rows", [])
            if not isinstance(rows, list):
                rows = []

        if len(rows) > limit:
            rows = rows[:limit]

        columns = self.profile_columns(rows)
        explanations = [
            {
                "column": item["column"],
                "explanation": item["explanation"],
            }
            for item in columns
        ]

        return {
            "database_id": int(database_id),
            "schema": schema_name,
            "sql_executed": sql_to_run,
            "preview_limit": limit,
            "rows_count": len(rows),
            "rows": rows,
            "columns": columns,
            "field_explanations": explanations,
        }

    def profile_columns(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not rows:
            return []

        column_order: List[str] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            for key in row.keys():
                if key not in column_order:
                    column_order.append(key)

        profiles: List[Dict[str, Any]] = []
        for column in column_order:
            values = [row.get(column) for row in rows if isinstance(row, dict)]
            non_null = [v for v in values if v is not None and str(v) != ""]
            inferred_type = self._infer_value_type(non_null)
            unit = _infer_unit(column)
            distinct = len({str(v) for v in non_null})
            sample_value = non_null[0] if non_null else None
            explanation = self._build_column_explanation(
                column=column,
                inferred_type=inferred_type,
                unit=unit,
                distinct_count=distinct,
            )
            profiles.append(
                {
                    "column": column,
                    "inferred_type": inferred_type,
                    "unit": unit,
                    "non_null_count": len(non_null),
                    "distinct_count": distinct,
                    "sample_value": sample_value,
                    "explanation": explanation,
                }
            )
        return profiles

    def recommend_viz_types(
        self,
        *,
        rows: List[Dict[str, Any]],
        columns: List[Dict[str, Any]],
        metric_column: str = "",
        dimension_column: str = "",
        time_column: str = "",
    ) -> Dict[str, Any]:
        if not rows or not columns:
            return {
                "recommended": "table",
                "candidates": [
                    {
                        "viz_type": "table",
                        "score": 1.0,
                        "reason": "Нет данных для подбора графика; используем табличный вид.",
                    }
                ],
                "selected_columns": {
                    "metric": "",
                    "dimension": "",
                    "time": "",
                },
            }

        numeric_cols = [c["column"] for c in columns if c.get("inferred_type") == "numeric"]
        temporal_cols = [c["column"] for c in columns if c.get("inferred_type") == "temporal"]
        text_cols = [
            c["column"]
            for c in columns
            if c.get("inferred_type") in {"text", "boolean"}
        ]

        metric = metric_column if metric_column in numeric_cols else (numeric_cols[0] if numeric_cols else "")
        dimension = (
            dimension_column if dimension_column in text_cols else (text_cols[0] if text_cols else "")
        )
        time_col = time_column if time_column in temporal_cols else (temporal_cols[0] if temporal_cols else "")

        candidates: List[Dict[str, Any]] = []

        if time_col and metric:
            candidates.append(
                {
                    "viz_type": "line",
                    "score": 0.95,
                    "reason": f"Есть временная колонка '{time_col}' и метрика '{metric}'.",
                }
            )
            candidates.append(
                {
                    "viz_type": "area",
                    "score": 0.8,
                    "reason": "Подходит для тренда во времени.",
                }
            )

        if dimension and metric:
            cardinality = self._column_cardinality(rows, dimension)
            if cardinality <= 12:
                candidates.append(
                    {
                        "viz_type": "bar",
                        "score": 0.9,
                        "reason": (
                            f"Категориальная колонка '{dimension}' с умеренной кардинальностью "
                            f"({cardinality}) и числовая метрика '{metric}'."
                        ),
                    }
                )
            if 2 <= cardinality <= 8:
                candidates.append(
                    {
                        "viz_type": "pie",
                        "score": 0.74,
                        "reason": "Небольшое число категорий, можно показать доли.",
                    }
                )

        if len(numeric_cols) >= 2:
            candidates.append(
                {
                    "viz_type": "scatter",
                    "score": 0.72,
                    "reason": "Есть минимум две числовые колонки — можно показать корреляцию.",
                }
            )

        candidates.append(
            {
                "viz_type": "table",
                "score": 0.5,
                "reason": "Универсальный fallback для проверки данных.",
            }
        )

        by_type: Dict[str, Dict[str, Any]] = {}
        for item in candidates:
            old = by_type.get(item["viz_type"])
            if old is None or float(item["score"]) > float(old["score"]):
                by_type[item["viz_type"]] = item

        ordered = sorted(by_type.values(), key=lambda x: float(x["score"]), reverse=True)
        recommended = ordered[0]["viz_type"] if ordered else "table"

        return {
            "recommended": recommended,
            "candidates": ordered,
            "selected_columns": {
                "metric": metric,
                "dimension": dimension,
                "time": time_col,
            },
        }

    def build_chart_params(
        self,
        *,
        dataset_id: int,
        viz_type: str,
        metric_column: str = "",
        dimension_column: str = "",
        time_column: str = "",
        row_limit: int = 1000,
    ) -> Dict[str, Any]:
        safe_viz = _normalize_text(viz_type).lower() or "table"
        if safe_viz not in COMMON_VIZ_TYPES:
            safe_viz = "table"

        params: Dict[str, Any] = {
            "datasource": f"{int(dataset_id)}__table",
            "viz_type": safe_viz,
            "row_limit": max(1, int(row_limit)),
        }

        if safe_viz == "table":
            all_columns: List[str] = []
            if dimension_column:
                all_columns.append(dimension_column)
            if metric_column:
                all_columns.append(metric_column)
            if time_column:
                all_columns.append(time_column)
            if all_columns:
                params["all_columns"] = all_columns
            return params

        adhoc_metric = None
        if metric_column:
            adhoc_metric = {
                "expressionType": "SIMPLE",
                "column": {"column_name": metric_column},
                "aggregate": "SUM",
                "label": f"SUM({metric_column})",
            }
            params["metrics"] = [adhoc_metric]

        if dimension_column:
            params["groupby"] = [dimension_column]

        if safe_viz in {"line", "area"} and time_column:
            params["granularity_sqla"] = time_column
            params["time_grain_sqla"] = "P1D"

        if safe_viz == "scatter" and metric_column:
            params.setdefault("x", metric_column)
            if dimension_column:
                params.setdefault("groupby", [dimension_column])

        return params

    @staticmethod
    def _unique_column_names(*groups: List[str]) -> List[str]:
        seen = set()
        ordered: List[str] = []
        for group in groups:
            for raw in group:
                value = _normalize_text(raw)
                if not value:
                    continue
                key = value.casefold()
                if key in seen:
                    continue
                seen.add(key)
                ordered.append(value)
        return ordered

    def _resolve_chart_columns(
        self,
        *,
        dataset_id: int,
        metric_column: str = "",
        dimension_column: str = "",
        time_column: str = "",
    ) -> List[str]:
        selected = self._unique_column_names(
            [dimension_column],
            [metric_column],
            [time_column],
        )
        if selected:
            return selected

        metadata = self.get_dataset_metadata(dataset_id)
        columns = metadata.get("columns", [])
        if not isinstance(columns, list):
            return []
        resolved: List[str] = []
        for column in columns:
            if not isinstance(column, dict):
                continue
            column_name = _normalize_text(column.get("column_name"))
            if column_name:
                resolved.append(column_name)
            if len(resolved) >= 3:
                break
        return resolved

    def _build_mcp_chart_config(
        self,
        *,
        dataset_id: int,
        viz_type: str,
        metric_column: str = "",
        dimension_column: str = "",
        time_column: str = "",
    ) -> Dict[str, Any]:
        safe_viz = _normalize_text(viz_type).lower() or "table"
        if safe_viz not in COMMON_VIZ_TYPES:
            safe_viz = "table"

        available_columns = self._resolve_chart_columns(
            dataset_id=dataset_id,
            metric_column=metric_column,
            dimension_column=dimension_column,
            time_column=time_column,
        )
        if not available_columns:
            raise RuntimeError(
                f"Dataset {dataset_id} does not expose usable columns for chart generation."
            )

        if safe_viz == "table":
            return {
                "chart_type": "table",
                "columns": [{"name": name} for name in available_columns],
            }

        if safe_viz == "pie":
            raise RuntimeError(
                "Pie chart creation uses the compatibility extension path, not the built-in schema."
            )

        x_name = _normalize_text(time_column) or _normalize_text(dimension_column) or available_columns[0]
        metric_name = _normalize_text(metric_column)
        count_base = _normalize_text(dimension_column) or x_name
        y_config: Dict[str, Any]
        if metric_name:
            y_config = {
                "name": metric_name,
                "aggregate": "SUM",
                "label": f"SUM({metric_name})",
            }
        else:
            y_config = {
                "name": count_base,
                "aggregate": "COUNT",
                "label": f"COUNT({count_base})",
            }

        config: Dict[str, Any] = {
            "chart_type": "xy",
            "x": {"name": x_name},
            "y": [y_config],
            "kind": safe_viz if safe_viz in {"line", "bar", "area", "scatter"} else "bar",
        }
        group_by = _normalize_text(dimension_column)
        if group_by and group_by != x_name:
            config["group_by"] = {"name": group_by}
        return config

    def create_dashboard_widget_with_share(
        self,
        *,
        dataset_id: int,
        dashboard_title: str,
        slice_name: str,
        viz_type: str,
        metric_column: str = "",
        dimension_column: str = "",
        time_column: str = "",
        row_limit: int = 1000,
        description: str = "",
    ) -> Dict[str, Any]:
        safe_dashboard_title = _normalize_text(dashboard_title) or "AI Dashboard"
        safe_slice_name = _normalize_text(slice_name) or "AI Widget"
        safe_viz_type = _normalize_text(viz_type).lower() or "table"

        dashboard = self._create_dashboard(safe_dashboard_title)
        dashboard_id = int(dashboard["dashboard_id"])

        params = self.build_chart_params(
            dataset_id=dataset_id,
            viz_type=viz_type,
            metric_column=metric_column,
            dimension_column=dimension_column,
            time_column=time_column,
            row_limit=row_limit,
        )

        chart = self._create_chart(
            slice_name=safe_slice_name,
            datasource_id=int(dataset_id),
            datasource_type="table",
            viz_type=safe_viz_type,
            params=params,
            dashboard_id=dashboard_id,
            description=description,
            metric_column=metric_column,
            dimension_column=dimension_column,
            time_column=time_column,
        )

        dashboard_url = dashboard.get("dashboard_url") or f"/superset/dashboard/{dashboard_id}/"
        chart_id = int(chart["chart_id"])
        chart_url = chart.get("chart_url") or f"/explore/?slice_id={chart_id}"

        return {
            "dashboard_id": dashboard_id,
            "chart_id": chart_id,
            "dashboard_url": dashboard_url,
            "chart_url": chart_url,
            "dashboard_link": self._to_absolute_url(dashboard_url),
            "chart_link": self._to_absolute_url(chart_url),
            "params": params,
            "viz_type": safe_viz_type,
        }

    def generate_dashboard(
        self,
        *,
        chart_ids: List[int],
        dashboard_title: str,
        description: str = "",
    ) -> Dict[str, Any]:
        safe_title = _normalize_text(dashboard_title) or "AI Dashboard"
        if not chart_ids:
            return self._create_dashboard(safe_title)
        if self._runtime_name() == "legacy":
            raise RuntimeError(
                "Legacy runtime does not support the migrated generate_dashboard flow."
            )
        payload = self._call_product_client(
            "generate_dashboard",
            {
                "chart_ids": [int(chart_id) for chart_id in chart_ids],
                "dashboard_title": safe_title,
                "description": _normalize_text(description) or None,
                "published": False,
            },
        )
        self._raise_if_tool_error(payload, default_message="Dashboard generation failed.")
        dashboard = payload.get("dashboard", {})
        dashboard_id = dashboard.get("id") if isinstance(dashboard, dict) else None
        dashboard_url = _normalize_text(
            payload.get("dashboard_url")
            or (dashboard.get("url") if isinstance(dashboard, dict) else "")
        )
        if not isinstance(dashboard_id, int):
            raise RuntimeError(f"Dashboard generate response does not contain id: {payload}")
        return {
            "dashboard_id": dashboard_id,
            "dashboard_url": dashboard_url or f"/superset/dashboard/{dashboard_id}/",
            "raw": payload,
        }

    def update_chart(
        self,
        *,
        chart_id: int,
        dataset_id: int,
        viz_type: str,
        metric_column: str = "",
        dimension_column: str = "",
        time_column: str = "",
    ) -> Dict[str, Any]:
        safe_viz = _normalize_text(viz_type).lower() or "table"
        if self._runtime_name() == "legacy":
            raise RuntimeError(
                "Legacy runtime does not support the migrated update_chart flow."
            )
        if safe_viz == "pie":
            raise RuntimeError(
                "Pie chart updates are not yet migrated to built-in MCP semantics."
            )
        payload = self._call_product_client(
            "update_chart",
            {
                "identifier": int(chart_id),
                "config": self._build_mcp_chart_config(
                    dataset_id=int(dataset_id),
                    viz_type=safe_viz,
                    metric_column=metric_column,
                    dimension_column=dimension_column,
                    time_column=time_column,
                ),
                "generate_preview": False,
            },
        )
        self._raise_if_tool_error(payload, default_message="Chart update failed.")
        chart = payload.get("chart", {})
        updated_chart_id = chart.get("id") if isinstance(chart, dict) else None
        chart_url = _normalize_text(
            payload.get("explore_url")
            or (chart.get("url") if isinstance(chart, dict) else "")
        )
        if not isinstance(updated_chart_id, int):
            raise RuntimeError(f"Chart update response does not contain id: {payload}")
        return {
            "chart_id": updated_chart_id,
            "chart_url": chart_url or f"/explore/?slice_id={updated_chart_id}",
            "raw": payload,
        }

    def generate_explore_link(
        self,
        *,
        dataset_id: int,
        viz_type: str,
        metric_column: str = "",
        dimension_column: str = "",
        time_column: str = "",
    ) -> str:
        safe_viz = _normalize_text(viz_type).lower() or "table"
        if self._runtime_name() == "legacy":
            raise RuntimeError(
                "Legacy runtime does not support the migrated generate_explore_link flow."
            )
        if safe_viz == "pie":
            raise RuntimeError(
                "Pie explore-link generation is not yet migrated to built-in MCP semantics."
            )
        payload = self._call_product_client(
            "generate_explore_link",
            {
                "dataset_id": int(dataset_id),
                "config": self._build_mcp_chart_config(
                    dataset_id=int(dataset_id),
                    viz_type=safe_viz,
                    metric_column=metric_column,
                    dimension_column=dimension_column,
                    time_column=time_column,
                ),
            },
        )
        self._raise_if_tool_error(payload, default_message="Explore link generation failed.")
        url = _normalize_text(payload.get("url"))
        if not url:
            raise RuntimeError(f"Explore link response does not contain url: {payload}")
        return self._to_absolute_url(url)

    def _create_dashboard(self, dashboard_title: str) -> Dict[str, Any]:
        if self._runtime_name() == "legacy":
            result = self._call_legacy_tool(
                "superset_dashboard_create",
                {"dashboard_title": dashboard_title, "json_metadata": {}},
            )
            self._raise_if_tool_error(result, default_message="Dashboard creation failed.")
            dashboard_id = result.get("dashboard_id")
            if not isinstance(dashboard_id, int):
                full_result = result.get("full_result")
                if isinstance(full_result, dict) and isinstance(full_result.get("id"), int):
                    dashboard_id = int(full_result["id"])
            dashboard_url = _normalize_text(result.get("dashboard_url"))
            if not dashboard_url and isinstance(result.get("full_result"), dict):
                dashboard_url = _normalize_text(result["full_result"].get("url"))
        else:
            result = self._call_product_client(
                "create_empty_dashboard",
                {"dashboard_title": dashboard_title},
            )
            self._raise_if_tool_error(result, default_message="Dashboard creation failed.")
            dashboard = result.get("dashboard")
            dashboard_id = dashboard.get("id") if isinstance(dashboard, dict) else None
            dashboard_url = _normalize_text(
                result.get("dashboard_url")
                or (dashboard.get("url") if isinstance(dashboard, dict) else "")
            )

        if not isinstance(dashboard_id, int):
            raise RuntimeError(f"Dashboard create response does not contain id: {result}")

        if not dashboard_url:
            dashboard_url = f"/superset/dashboard/{dashboard_id}/"

        return {
            "dashboard_id": dashboard_id,
            "dashboard_url": dashboard_url,
            "raw": result,
        }

    def _create_chart(
        self,
        *,
        slice_name: str,
        datasource_id: int,
        datasource_type: str,
        viz_type: str,
        params: Dict[str, Any],
        dashboard_id: Optional[int] = None,
        description: str = "",
        metric_column: str = "",
        dimension_column: str = "",
        time_column: str = "",
    ) -> Dict[str, Any]:
        safe_viz = _normalize_text(viz_type).lower() or "table"
        if self._runtime_name() == "legacy":
            result = self._call_legacy_tool(
                "superset_chart_create",
                {
                    "slice_name": slice_name,
                    "datasource_id": int(datasource_id),
                    "datasource_type": _normalize_text(datasource_type) or "table",
                    "viz_type": safe_viz,
                    "params": params,
                    "dashboard_id": int(dashboard_id) if dashboard_id is not None else None,
                    "description": _normalize_text(description) or None,
                },
            )
            self._raise_if_tool_error(result, default_message="Chart creation failed.")
            chart_id = result.get("chart_id")
            if not isinstance(chart_id, int):
                chart_info = result.get("chart_info")
                if isinstance(chart_info, dict) and isinstance(chart_info.get("id"), int):
                    chart_id = int(chart_info["id"])
            chart_url = _normalize_text(result.get("chart_url"))
            if not chart_url:
                chart_info = result.get("chart_info")
                if isinstance(chart_info, dict):
                    chart_url = _normalize_text(chart_info.get("url"))
        else:
            if safe_viz == "pie":
                result = self._call_product_client(
                    "legacy_chart_create",
                    {
                        "slice_name": slice_name,
                        "datasource_id": int(datasource_id),
                        "datasource_type": _normalize_text(datasource_type) or "table",
                        "viz_type": safe_viz,
                        "params": params,
                        "description": _normalize_text(description) or None,
                    },
                )
                self._raise_if_tool_error(result, default_message="Chart creation failed.")
                chart_id = result.get("chart_id")
                chart_url = _normalize_text(result.get("chart_url"))
            else:
                result = self._call_product_client(
                    "generate_chart",
                    {
                        "dataset_id": int(datasource_id),
                        "config": self._build_mcp_chart_config(
                            dataset_id=int(datasource_id),
                            viz_type=safe_viz,
                            metric_column=metric_column,
                            dimension_column=dimension_column,
                            time_column=time_column,
                        ),
                        "save_chart": True,
                        "generate_preview": False,
                    },
                )
                self._raise_if_tool_error(result, default_message="Chart creation failed.")
                chart = result.get("chart")
                chart_id = chart.get("id") if isinstance(chart, dict) else None
                chart_url = _normalize_text(
                    result.get("explore_url")
                    or (chart.get("url") if isinstance(chart, dict) else "")
                )
                if dashboard_id is not None and isinstance(chart_id, int):
                    attach_result = self._call_product_client(
                        "add_chart_to_existing_dashboard",
                        {
                            "dashboard_id": int(dashboard_id),
                            "chart_id": int(chart_id),
                        },
                    )
                    self._raise_if_tool_error(
                        attach_result,
                        default_message="Attaching chart to dashboard failed.",
                    )

        if not isinstance(chart_id, int):
            raise RuntimeError(f"Chart create response does not contain id: {result}")

        if not chart_url:
            chart_url = f"/explore/?slice_id={chart_id}"

        return {
            "chart_id": chart_id,
            "chart_url": chart_url,
            "raw": result,
        }

    def _to_absolute_url(self, relative_or_abs: str) -> str:
        value = _normalize_text(relative_or_abs)
        if not value:
            return self.share_base_url
        if value.startswith("http://") or value.startswith("https://"):
            parsed = urlparse(value)
            share_parsed = urlparse(self.share_base_url)
            path = parsed.path or ""
            # Superset иногда возвращает плейсхолдер-хосты вроде "your-superset-url".
            should_rewrite_host = (
                "your-superset-url" in (parsed.netloc or "").casefold()
                or path.startswith("/superset/")
                or path.startswith("/explore/")
                or path.startswith("/dashboard/")
                or path.startswith("/chart/")
            )
            if should_rewrite_host:
                return urlunparse(
                    (
                        share_parsed.scheme,
                        share_parsed.netloc,
                        parsed.path,
                        parsed.params,
                        parsed.query,
                        parsed.fragment,
                    )
                )
            return value
        if not value.startswith("/"):
            value = "/" + value
        return f"{self.share_base_url}{value}"

    @staticmethod
    def _normalize_base_url(url: str, *, fallback: str) -> str:
        raw = _normalize_text(url) or _normalize_text(fallback)
        if not raw:
            return DEFAULT_PUBLIC_SUPERSET_URL
        if not raw.startswith("http://") and not raw.startswith("https://"):
            raw = f"http://{raw}"
        parsed = urlparse(raw)
        fallback_parsed = urlparse(_normalize_text(fallback) or DEFAULT_PUBLIC_SUPERSET_URL)
        netloc = parsed.netloc
        if not netloc or "your-superset-url" in netloc.casefold():
            netloc = fallback_parsed.netloc
        scheme = parsed.scheme or fallback_parsed.scheme or "http"
        path = (parsed.path or "").rstrip("/")
        return urlunparse((scheme, netloc, path, "", "", ""))

    @staticmethod
    def _is_localhost_netloc(netloc: str) -> bool:
        token = str(netloc or "").casefold()
        return (
            token.startswith("localhost")
            or token.startswith("127.0.0.1")
            or token.startswith("0.0.0.0")
        )

    @staticmethod
    def _infer_value_type(values: List[Any]) -> str:
        if not values:
            return "unknown"

        numeric = sum(1 for v in values if _is_numeric(v))
        temporal = sum(1 for v in values if _is_temporal(v))
        boolean = sum(1 for v in values if isinstance(v, bool))
        total = len(values)

        if boolean == total:
            return "boolean"
        if numeric >= max(1, int(total * 0.7)):
            return "numeric"
        if temporal >= max(1, int(total * 0.7)):
            return "temporal"
        return "text"

    @staticmethod
    def _column_cardinality(rows: List[Dict[str, Any]], column: str) -> int:
        values = [row.get(column) for row in rows if isinstance(row, dict)]
        tokens = [str(v) for v in values if v is not None and str(v) != ""]
        return len(set(tokens))

    @staticmethod
    def _build_column_explanation(
        *,
        column: str,
        inferred_type: str,
        unit: str,
        distinct_count: int,
    ) -> str:
        prefix = f"{column}: тип={inferred_type}"
        if unit:
            prefix += f", единица={unit}"
        suffix = f", уникальных значений={distinct_count}"
        if inferred_type == "temporal":
            hint = "подходит для оси времени"
        elif inferred_type == "numeric":
            hint = "подходит для метрик/агрегаций"
        elif inferred_type == "text":
            hint = "подходит для группировок/категорий"
        else:
            hint = "используется как справочное поле"
        return f"{prefix}{suffix}; {hint}."


_us13_15_service: Optional[US13To15VizService] = None


def get_us13_15_viz_service() -> US13To15VizService:
    global _us13_15_service
    if _us13_15_service is None:
        _us13_15_service = US13To15VizService.from_env()
    return _us13_15_service


__all__ = [
    "US13To15VizService",
    "get_us13_15_viz_service",
    "COMMON_VIZ_TYPES",
]
