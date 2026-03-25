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

import sys
from types import ModuleType
from unittest.mock import Mock, patch

from superset.utils import json


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


def test_create_empty_dashboard_uses_empty_layout(load_extension_module):
    module = load_extension_module(
        "superset.mcp_service.extensions.tool.create_empty_dashboard"
    )
    mock_create_command = Mock()
    mock_create_command.return_value.run.return_value = _mock_dashboard(
        11, "Product Empty Dashboard"
    )
    command_module = ModuleType("superset.commands.dashboard.create")
    command_module.CreateDashboardCommand = mock_create_command

    with (
        patch.dict(sys.modules, {"superset.commands.dashboard.create": command_module}),
        patch.object(module, "get_superset_base_url", return_value="http://localhost:9001"),
    ):
        result = module.create_empty_dashboard(
            {
                "dashboard_title": "Product Empty Dashboard",
                "description": "Dashboard shell",
                "published": False,
            },
            Mock(),
        )

    assert result.error is None
    assert result.dashboard.id == 11
    assert result.dashboard.chart_count == 0
    assert result.dashboard_url.endswith("/superset/dashboard/11/")

    call_args = mock_create_command.call_args[0][0]
    position_json = json.loads(call_args["position_json"])
    assert position_json["ROOT_ID"]["children"] == ["GRID_ID"]
    assert position_json["GRID_ID"]["children"] == []
    assert position_json["DASHBOARD_VERSION_KEY"] == "v2"


def test_create_empty_dashboard_returns_error_payload_on_failure(load_extension_module):
    module = load_extension_module(
        "superset.mcp_service.extensions.tool.create_empty_dashboard"
    )
    mock_create_command = Mock()
    mock_create_command.return_value.run.side_effect = Exception("create failed")
    command_module = ModuleType("superset.commands.dashboard.create")
    command_module.CreateDashboardCommand = mock_create_command

    with (
        patch.dict(sys.modules, {"superset.commands.dashboard.create": command_module}),
        patch.object(module, "get_superset_base_url", return_value="http://localhost:9001"),
    ):
        result = module.create_empty_dashboard(
            {"dashboard_title": "Broken Dashboard"},
            Mock(),
        )

    assert result.dashboard is None
    assert result.dashboard_url is None
    assert "Failed to create empty dashboard" in result.error
