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
from fastmcp import Client

from superset.mcp_service.app import mcp


@pytest.fixture
def mcp_server():
    return mcp


@pytest.fixture(autouse=True)
def mock_auth():
    with patch("superset.mcp_service.auth.get_user_from_request") as mock_get_user:
        mock_user = Mock()
        mock_user.id = 1
        mock_user.username = "admin"
        mock_get_user.return_value = mock_user
        yield mock_get_user


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
    mock_create_command, mcp_server
):
    mock_create_command.return_value.run.return_value = _mock_chart(21, "Revenue Pie", "pie")

    async with Client(mcp_server) as client:
        result = await client.call_tool(
            "mcp_ext.legacy_chart_create",
            {
                "request": {
                    "slice_name": "Revenue Pie",
                    "datasource_id": 7,
                    "datasource_type": "table",
                    "viz_type": "pie",
                    "params": {"viz_type": "pie", "groupby": ["region"]},
                }
            },
        )

    data = result.structured_content
    assert data["error"] is None
    assert data["chart_id"] == 21
    assert data["chart"]["viz_type"] == "pie"
    assert data["chart_url"].endswith("/explore/?slice_id=21")


@patch("superset.commands.chart.create.CreateChartCommand")
@pytest.mark.asyncio
async def test_legacy_chart_create_returns_error_payload_on_failure(
    mock_create_command, mcp_server
):
    mock_create_command.return_value.run.side_effect = Exception("chart failed")

    async with Client(mcp_server) as client:
        result = await client.call_tool(
            "mcp_ext.legacy_chart_create",
            {
                "request": {
                    "slice_name": "Broken Chart",
                    "datasource_id": 7,
                    "datasource_type": "table",
                    "viz_type": "pie",
                    "params": {"viz_type": "pie"},
                }
            },
        )

    data = result.structured_content
    assert data["chart"] is None
    assert data["chart_id"] is None
    assert "Failed to create chart" in data["error"]
