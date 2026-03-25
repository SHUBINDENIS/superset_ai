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

from unittest.mock import Mock, patch

import pytest


def _mock_chart(chart_id: int, slice_name: str, viz_type: str) -> Mock:
    chart = Mock()
    chart.id = chart_id
    chart.slice_name = slice_name
    chart.viz_type = viz_type
    chart.uuid = f"chart-uuid-{chart_id}"
    return chart


@patch("superset.commands.chart.create.CreateChartCommand")
@pytest.mark.asyncio
async def test_legacy_chart_create_uses_server_side_command(
    mock_create_command, load_extension_module
):
    module = load_extension_module("superset.mcp_service.extensions.tool.legacy_chart_create")
    mock_create_command.return_value.run.return_value = _mock_chart(21, "Revenue Pie", "pie")

    result = module.legacy_chart_create(
        {
            "slice_name": "Revenue Pie",
            "datasource_id": 7,
            "datasource_type": "table",
            "viz_type": "pie",
            "params": {"viz_type": "pie", "groupby": ["region"]},
        },
        Mock(),
    )

    assert result["error"] is None
    assert result["chart_id"] == 21
    assert result["chart"]["viz_type"] == "pie"
    assert result["chart_url"].endswith("/explore/?slice_id=21")


@patch("superset.commands.chart.create.CreateChartCommand")
@pytest.mark.asyncio
async def test_legacy_chart_create_returns_error_payload_on_failure(
    mock_create_command, load_extension_module
):
    module = load_extension_module("superset.mcp_service.extensions.tool.legacy_chart_create")
    mock_create_command.return_value.run.side_effect = Exception("chart failed")

    result = module.legacy_chart_create(
        {
            "slice_name": "Broken Chart",
            "datasource_id": 7,
            "datasource_type": "table",
            "viz_type": "pie",
            "params": {"viz_type": "pie"},
        },
        Mock(),
    )

    assert result["chart"] is None
    assert result["chart_id"] is None
    assert "Failed to create chart" in result["error"]
