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
from superset.utils import json


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


def _mock_dashboard(dashboard_id: int, title: str) -> Mock:
    dashboard = Mock()
    dashboard.id = dashboard_id
    dashboard.dashboard_title = title
    dashboard.slug = f"dashboard-{dashboard_id}"
    dashboard.description = "Created for product flow"
    dashboard.published = False
    dashboard.created_on = "2024-01-01"
    dashboard.changed_on = "2024-01-01"
    dashboard.created_by = Mock(username="admin")
    dashboard.changed_by = Mock(username="admin")
    dashboard.uuid = f"dashboard-uuid-{dashboard_id}"
    dashboard.owners = []
    dashboard.tags = []
    return dashboard


@patch("superset.commands.dashboard.create.CreateDashboardCommand")
@pytest.mark.asyncio
async def test_create_empty_dashboard_uses_empty_layout(
    mock_create_command, mcp_server
):
    mock_create_command.return_value.run.return_value = _mock_dashboard(
        11, "Product Empty Dashboard"
    )

    async with Client(mcp_server) as client:
        result = await client.call_tool(
            "mcp_ext.create_empty_dashboard",
            {
                "request": {
                    "dashboard_title": "Product Empty Dashboard",
                    "description": "Dashboard shell",
                    "published": False,
                }
            },
        )

    data = result.structured_content
    assert data["error"] is None
    assert data["dashboard"]["id"] == 11
    assert data["dashboard"]["chart_count"] == 0
    assert data["dashboard_url"].endswith("/superset/dashboard/11/")

    call_args = mock_create_command.call_args[0][0]
    position_json = json.loads(call_args["position_json"])
    assert position_json["ROOT_ID"]["children"] == ["GRID_ID"]
    assert position_json["GRID_ID"]["children"] == []
    assert position_json["DASHBOARD_VERSION_KEY"] == "v2"


@patch("superset.commands.dashboard.create.CreateDashboardCommand")
@pytest.mark.asyncio
async def test_create_empty_dashboard_returns_error_payload_on_failure(
    mock_create_command, mcp_server
):
    mock_create_command.return_value.run.side_effect = Exception("create failed")

    async with Client(mcp_server) as client:
        result = await client.call_tool(
            "mcp_ext.create_empty_dashboard",
            {"request": {"dashboard_title": "Broken Dashboard"}},
        )

    data = result.structured_content
    assert data["dashboard"] is None
    assert data["dashboard_url"] is None
    assert "Failed to create empty dashboard" in data["error"]
