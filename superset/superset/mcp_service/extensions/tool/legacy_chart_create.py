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
Product migration extension: server-side legacy-style chart creation without REST CSRF.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastmcp import Context
from pydantic import BaseModel, Field
from superset_core.mcp import tool

from superset.mcp_service.utils.schema_utils import parse_request
from superset.mcp_service.utils.url_utils import get_superset_base_url
from superset.utils import json

logger = logging.getLogger(__name__)


class LegacyChartCreateRequest(BaseModel):
    slice_name: str = Field(..., min_length=1, max_length=255)
    datasource_id: int = Field(..., gt=0)
    datasource_type: str = Field(default="table", min_length=1, max_length=32)
    viz_type: str = Field(..., min_length=1, max_length=64)
    params: Dict[str, Any] = Field(default_factory=dict)
    description: str | None = Field(default=None, max_length=5000)


@tool(name="mcp_ext.legacy_chart_create", tags=["extension"])
@parse_request(LegacyChartCreateRequest)
def legacy_chart_create(
    request: LegacyChartCreateRequest, ctx: Context
) -> Dict[str, Any]:
    """Create a saved chart from raw Superset params when built-in schema is too narrow."""
    del ctx

    try:
        from superset.commands.chart.create import CreateChartCommand

        payload: Dict[str, Any] = {
            "slice_name": request.slice_name,
            "viz_type": request.viz_type,
            "datasource_id": request.datasource_id,
            "datasource_type": request.datasource_type,
            "params": json.dumps(request.params),
        }
        if request.description:
            payload["description"] = request.description

        chart = CreateChartCommand(payload).run()
        chart_url = f"{get_superset_base_url()}/explore/?slice_id={chart.id}"
        return {
            "chart": {
                "id": chart.id,
                "slice_name": chart.slice_name,
                "viz_type": chart.viz_type,
                "url": chart_url,
                "uuid": str(chart.uuid) if chart.uuid else None,
            },
            "chart_id": chart.id,
            "chart_url": chart_url,
            "error": None,
        }
    except Exception as ex:
        logger.error("Error creating legacy-style chart: %s", ex)
        return {
            "chart": None,
            "chart_id": None,
            "chart_url": None,
            "error": f"Failed to create chart: {str(ex)}",
        }
