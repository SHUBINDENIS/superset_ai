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
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from flask import current_app, Flask

from superset.core.mcp.core_mcp_injection import (
    create_resource_decorator,
    create_tool_decorator,
)


def _build_test_flask_app() -> Flask:
    app = Flask(__name__)
    app.config["APP_NAME"] = "MCP Test App"
    return app


@pytest.mark.asyncio
async def test_create_tool_decorator_pushes_app_context_for_async_tools():
    flask_app = _build_test_flask_app()
    expected_app_name = flask_app.config.get("APP_NAME", "Superset")

    fake_mcp = SimpleNamespace(add_tool=Mock())
    fake_app_module = ModuleType("superset.mcp_service.app")
    fake_app_module.mcp = fake_mcp
    fake_singleton_module = ModuleType("superset.mcp_service.flask_singleton")
    fake_singleton_module.get_flask_app = lambda: flask_app

    with patch.dict(
        sys.modules,
        {
            "superset.mcp_service.app": fake_app_module,
            "superset.mcp_service.flask_singleton": fake_singleton_module,
        },
    ):
        with patch("superset.mcp_service.auth.get_user_from_request") as mock_user:
            mock_user.return_value = SimpleNamespace(
                id=1,
                username="admin",
                roles=[],
                groups=[],
            )

            @create_tool_decorator(protect=True)
            async def context_tool() -> str:
                return current_app.config.get("APP_NAME", "missing")

            result = await context_tool()

    assert result == expected_app_name
    fake_mcp.add_tool.assert_called_once()


def test_create_resource_decorator_pushes_app_context_for_sync_resources():
    flask_app = _build_test_flask_app()
    expected_app_name = flask_app.config.get("APP_NAME", "Superset")

    fake_mcp = SimpleNamespace(
        resource=Mock(side_effect=lambda *args, **kwargs: (lambda func: func))
    )
    fake_app_module = ModuleType("superset.mcp_service.app")
    fake_app_module.mcp = fake_mcp
    fake_singleton_module = ModuleType("superset.mcp_service.flask_singleton")
    fake_singleton_module.get_flask_app = lambda: flask_app

    with patch.dict(
        sys.modules,
        {
            "superset.mcp_service.app": fake_app_module,
            "superset.mcp_service.flask_singleton": fake_singleton_module,
        },
    ):
        with patch("superset.mcp_service.auth.get_user_from_request") as mock_user:
            mock_user.return_value = SimpleNamespace(
                id=1,
                username="admin",
                roles=[],
                groups=[],
            )

            @create_resource_decorator("instance://metadata", protect=True)
            def context_resource() -> str:
                return current_app.config.get("APP_NAME", "missing")

            result = context_resource()

    assert result == expected_app_name
    fake_mcp.resource.assert_called_once()
