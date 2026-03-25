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

"""
Product migration extension: create an empty dashboard before charts exist.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastmcp import Context
from pydantic import BaseModel, Field
from superset_core.mcp import tool

from superset.mcp_service.dashboard.schemas import (
    DashboardInfo,
    serialize_tag_object,
    serialize_user_object,
)
from superset.mcp_service.utils.schema_utils import parse_request
from superset.mcp_service.utils.url_utils import get_superset_base_url
from superset.utils import json

logger = logging.getLogger(__name__)


class CreateEmptyDashboardRequest(BaseModel):
    dashboard_title: str = Field(..., min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=5000)
    published: bool = Field(default=False)


class CreateEmptyDashboardResponse(BaseModel):
    dashboard: DashboardInfo | None = Field(default=None)
    dashboard_url: str | None = Field(default=None)
    error: str | None = Field(default=None)


def _empty_layout() -> Dict[str, Any]:
    return {
        "ROOT_ID": {
            "children": ["GRID_ID"],
            "id": "ROOT_ID",
            "type": "ROOT",
        },
        "GRID_ID": {
            "children": [],
            "id": "GRID_ID",
            "parents": ["ROOT_ID"],
            "type": "GRID",
        },
        "DASHBOARD_VERSION_KEY": "v2",
    }


def _default_dashboard_metadata() -> Dict[str, Any]:
    return {
        "filter_scopes": {},
        "expanded_slices": {},
        "refresh_frequency": 0,
        "timed_refresh_immune_slices": [],
        "color_scheme": None,
        "label_colors": {},
        "shared_label_colors": {},
        "color_scheme_domain": [],
        "cross_filters_enabled": False,
        "native_filter_configuration": [],
        "global_chart_configuration": {
            "scope": {"rootPath": ["ROOT_ID"], "excluded": []}
        },
        "chart_configuration": {},
    }


@tool(name="mcp_ext.create_empty_dashboard", tags=["extension"])
@parse_request(CreateEmptyDashboardRequest)
def create_empty_dashboard(
    request: CreateEmptyDashboardRequest, ctx: Context
) -> CreateEmptyDashboardResponse:
    """Create an empty dashboard for the product's dashboard-first flow."""
    del ctx

    try:
        from superset.commands.dashboard.create import CreateDashboardCommand

        payload: Dict[str, Any] = {
            "dashboard_title": request.dashboard_title,
            "slug": None,
            "css": "",
            "json_metadata": json.dumps(_default_dashboard_metadata()),
            "position_json": json.dumps(_empty_layout()),
            "published": request.published,
            "slices": [],
        }
        if request.description:
            payload["description"] = request.description

        dashboard = CreateDashboardCommand(payload).run()
        dashboard_url = f"{get_superset_base_url()}/superset/dashboard/{dashboard.id}/"

        dashboard_info = DashboardInfo(
            id=dashboard.id,
            dashboard_title=dashboard.dashboard_title,
            slug=dashboard.slug,
            description=dashboard.description,
            published=dashboard.published,
            created_on=dashboard.created_on,
            changed_on=dashboard.changed_on,
            created_by=dashboard.created_by.username if dashboard.created_by else None,
            changed_by=dashboard.changed_by.username if dashboard.changed_by else None,
            uuid=str(dashboard.uuid) if dashboard.uuid else None,
            url=dashboard_url,
            chart_count=0,
            owners=[
                serialize_user_object(owner)
                for owner in getattr(dashboard, "owners", [])
                if serialize_user_object(owner) is not None
            ],
            tags=[
                serialize_tag_object(tag)
                for tag in getattr(dashboard, "tags", [])
                if serialize_tag_object(tag) is not None
            ],
            roles=[],
            charts=[],
        )
        return CreateEmptyDashboardResponse(
            dashboard=dashboard_info,
            dashboard_url=dashboard_url,
            error=None,
        )
    except Exception as ex:
        logger.error("Error creating empty dashboard: %s", ex)
        return CreateEmptyDashboardResponse(
            dashboard=None,
            dashboard_url=None,
            error=f"Failed to create empty dashboard: {str(ex)}",
        )
