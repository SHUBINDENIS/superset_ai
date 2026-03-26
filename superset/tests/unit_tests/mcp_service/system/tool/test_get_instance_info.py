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

import importlib
import sys
from datetime import datetime
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

import superset_core.mcp

from superset.mcp_service.system.schemas import (
    DashboardBreakdown,
    DatabaseBreakdown,
    InstanceInfo,
    InstanceSummary,
    PopularContent,
    RecentActivity,
)


def _identity_tool(func_or_name=None, **_kwargs):
    def decorator(func):
        return func

    if callable(func_or_name):
        return func_or_name
    return decorator


def _load_get_instance_info():
    module_name = "superset.mcp_service.system.tool.get_instance_info"
    with patch.object(superset_core.mcp, "tool", _identity_tool):
        module = importlib.import_module(module_name)
    return module.get_instance_info


def _build_instance_info() -> InstanceInfo:
    return InstanceInfo(
        instance_summary=InstanceSummary(
            total_dashboards=1,
            total_charts=2,
            total_datasets=3,
            total_databases=4,
            total_users=5,
            total_roles=6,
            total_tags=7,
            avg_charts_per_dashboard=2.0,
        ),
        recent_activity=RecentActivity(
            dashboards_created_last_30_days=1,
            charts_created_last_30_days=1,
            datasets_created_last_30_days=1,
            dashboards_modified_last_7_days=1,
            charts_modified_last_7_days=1,
            datasets_modified_last_7_days=1,
        ),
        dashboard_breakdown=DashboardBreakdown(
            published=1,
            unpublished=0,
            certified=0,
            with_charts=1,
            without_charts=0,
        ),
        database_breakdown=DatabaseBreakdown(by_type={"postgresql": 1}),
        popular_content=PopularContent(top_tags=["tag"], top_creators=["admin"]),
        timestamp=datetime(2026, 1, 1, 12, 0, 0),
    )


def test_get_instance_info_accepts_empty_arguments():
    get_instance_info = _load_get_instance_info()
    fake_chart_module = ModuleType("superset.daos.chart")
    fake_chart_module.ChartDAO = SimpleNamespace
    fake_dashboard_module = ModuleType("superset.daos.dashboard")
    fake_dashboard_module.DashboardDAO = SimpleNamespace
    fake_database_module = ModuleType("superset.daos.database")
    fake_database_module.DatabaseDAO = SimpleNamespace
    fake_dataset_module = ModuleType("superset.daos.dataset")
    fake_dataset_module.DatasetDAO = SimpleNamespace
    fake_tag_module = ModuleType("superset.daos.tag")
    fake_tag_module.TagDAO = SimpleNamespace
    fake_user_module = ModuleType("superset.daos.user")
    fake_user_module.UserDAO = SimpleNamespace

    with patch(
        "superset.mcp_service.system.tool.get_instance_info._instance_info_core.run_tool",
        return_value=_build_instance_info(),
    ):
        with patch.dict(
            sys.modules,
            {
                "superset.daos.chart": fake_chart_module,
                "superset.daos.dashboard": fake_dashboard_module,
                "superset.daos.database": fake_database_module,
                "superset.daos.dataset": fake_dataset_module,
                "superset.daos.tag": fake_tag_module,
                "superset.daos.user": fake_user_module,
            },
        ):
            result = get_instance_info({})

    assert result.instance_summary.total_dashboards == 1
    assert result.database_breakdown.by_type["postgresql"] == 1
