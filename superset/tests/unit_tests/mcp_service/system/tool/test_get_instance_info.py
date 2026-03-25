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

from datetime import datetime
from unittest.mock import patch

import pytest
from fastmcp import Client

from superset.mcp_service.app import mcp
from superset.mcp_service.system.schemas import (
    DashboardBreakdown,
    DatabaseBreakdown,
    InstanceInfo,
    InstanceSummary,
    PopularContent,
    RecentActivity,
)


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


@pytest.mark.asyncio
async def test_get_instance_info_accepts_empty_arguments():
    with patch(
        "superset.mcp_service.system.tool.get_instance_info._instance_info_core.run_tool",
        return_value=_build_instance_info(),
    ):
        async with Client(mcp) as client:
            result = await client.call_tool("get_instance_info", {})

    assert result.data["instance_summary"]["total_dashboards"] == 1
    assert result.data["database_breakdown"]["by_type"]["postgresql"] == 1
