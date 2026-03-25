# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

from __future__ import annotations

import logging
from typing import Any, Protocol

from superset.charts.schemas import ChartDataQueryContextSchema
from superset.commands.chart.data.get_data_command import ChartDataCommand
from superset.common.chart_data import ChartDataResultFormat, ChartDataResultType
from superset.mcp_service.utils.cache_utils import apply_cache_control_to_query_context
from superset.migrations.shared.migrate_viz.query_functions import (
    build_query_context as build_query_context_dict,
)
from superset.utils import json

logger = logging.getLogger(__name__)


class ChartQuerySource(Protocol):
    id: int | None
    viz_type: str | None
    datasource_id: int | None
    datasource_type: str | None
    params: str | None


def build_runtime_form_data(chart: ChartQuerySource) -> dict[str, Any]:
    """Build normalized form_data for runtime chart query execution."""
    if hasattr(chart, "form_data") and isinstance(chart.form_data, dict):  # type: ignore[attr-defined]
        form_data = dict(chart.form_data)  # type: ignore[attr-defined]
    elif chart.params:
        form_data = json.loads(chart.params)
    else:
        form_data = {}

    if chart.id is not None:
        form_data.setdefault("slice_id", chart.id)
    if chart.viz_type:
        form_data.setdefault("viz_type", chart.viz_type)
    if (
        "datasource" not in form_data
        and chart.datasource_id is not None
        and chart.datasource_type
    ):
        form_data["datasource"] = f"{chart.datasource_id}__{chart.datasource_type}"
    return form_data


def build_chart_query_context(chart: ChartQuerySource) -> Any:
    """Create a query context for a chart from saved query_context or form_data."""
    query_context_getter = getattr(chart, "get_query_context", None)
    if callable(query_context_getter):
        query_context = query_context_getter()
        if query_context is not None:
            return query_context

    form_data = build_runtime_form_data(chart)
    return ChartDataQueryContextSchema().load(build_query_context_dict(form_data))


def execute_chart_query(
    chart: ChartQuerySource,
    *,
    row_limit: int | None,
    force_refresh: bool,
    cache_timeout: int | None,
) -> dict[str, Any]:
    """Execute the first chart query using Superset-native query context semantics."""
    query_context = build_chart_query_context(chart)
    query_context.force = force_refresh
    query_context.result_format = ChartDataResultFormat.JSON
    query_context.result_type = ChartDataResultType.FULL

    if cache_timeout is not None:
        query_context.custom_cache_timeout = cache_timeout

    for query_object in query_context.queries:
        if row_limit is not None:
            query_object.row_limit = row_limit
        if cache_timeout is not None:
            query_object.cache_timeout = cache_timeout

    command = ChartDataCommand(query_context)
    result = command.run()
    if not result or ("queries" not in result) or len(result["queries"]) == 0:
        raise ValueError("No query results returned")

    query_result = dict(result["queries"][0])
    if (
        "cache_dttm" not in query_result
        and query_result.get("cached_dttm") is not None
    ):
        query_result["cache_dttm"] = query_result["cached_dttm"]
    return query_result


def build_chart_query_context_json(
    *,
    form_data: dict[str, Any],
    force_refresh: bool,
    cache_timeout: int | None,
) -> str:
    """Build serialized query_context payload suitable for chart persistence."""
    query_context = build_query_context_dict(form_data)
    query_context = apply_cache_control_to_query_context(
        query_context,
        use_cache=not force_refresh,
        force_refresh=force_refresh,
        cache_timeout=cache_timeout,
    )
    return json.dumps(query_context)
