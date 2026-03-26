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

from types import SimpleNamespace
from unittest.mock import Mock, patch

from superset.mcp_service.chart.query_utils import (
    build_chart_query_context_json,
    build_runtime_form_data,
    execute_chart_query,
)


def test_build_runtime_form_data_adds_slice_metadata():
    chart = SimpleNamespace(
        id=7,
        viz_type="table",
        datasource_id=11,
        datasource_type="table",
        params='{"columns": ["region"]}',
    )

    form_data = build_runtime_form_data(chart)

    assert form_data["slice_id"] == 7
    assert form_data["viz_type"] == "table"
    assert form_data["datasource"] == "11__table"


def test_execute_chart_query_uses_saved_query_context_when_present():
    query_object = SimpleNamespace(row_limit=10, cache_timeout=None)
    query_context = SimpleNamespace(
        queries=[query_object],
        force=False,
        result_format=None,
        result_type=None,
        custom_cache_timeout=None,
    )
    chart = SimpleNamespace(get_query_context=Mock(return_value=query_context))

    fake_result = {"queries": [{"data": [{"region": "EMEA"}], "colnames": ["region"]}]}

    with patch(
        "superset.mcp_service.chart.query_utils._get_chart_data_command_cls"
    ) as command_factory:
        chart_data_command = command_factory.return_value
        chart_data_command.return_value.run.return_value = fake_result
        result = execute_chart_query(
            chart,
            row_limit=25,
            force_refresh=True,
            cache_timeout=30,
        )

    assert result["data"] == [{"region": "EMEA"}]
    assert query_context.force is True
    assert query_context.custom_cache_timeout == 30
    assert query_object.row_limit == 25
    assert query_object.cache_timeout == 30


def test_execute_chart_query_builds_query_context_from_form_data_when_missing():
    chart = SimpleNamespace(
        id=12,
        viz_type="table",
        datasource_id=5,
        datasource_type="table",
        params='{"columns": ["region"]}',
        get_query_context=Mock(return_value=None),
    )
    fake_query_object = SimpleNamespace(row_limit=50, cache_timeout=None)
    fake_query_context = SimpleNamespace(
        queries=[fake_query_object],
        force=False,
        result_format=None,
        result_type=None,
        custom_cache_timeout=None,
    )

    with patch(
        "superset.mcp_service.chart.query_utils._get_chart_query_context_schema"
    ) as schema_factory:
        schema_cls = schema_factory.return_value
        schema_cls.return_value.load.return_value = fake_query_context
        with patch(
            "superset.mcp_service.chart.query_utils._get_chart_data_command_cls"
        ) as command_factory:
            chart_data_command = command_factory.return_value
            chart_data_command.return_value.run.return_value = {
                "queries": [{"data": [], "colnames": []}]
            }
            execute_chart_query(
                chart,
                row_limit=15,
                force_refresh=False,
                cache_timeout=None,
            )

    load_payload = schema_cls.return_value.load.call_args.args[0]
    assert load_payload["datasource"] == {"id": 5, "type": "table"}
    assert load_payload["form_data"]["datasource"] == "5__table"


def test_build_chart_query_context_json_applies_cache_controls():
    payload = build_chart_query_context_json(
        form_data={
            "datasource": "3__table",
            "viz_type": "table",
            "columns": ["region"],
        },
        force_refresh=True,
        cache_timeout=42,
    )

    assert '"force": true' in payload.lower()
    assert '"cache_timeout": 42' in payload
