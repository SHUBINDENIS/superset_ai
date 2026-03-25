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


def _mock_database(database_id: int, name: str, backend: str = "sqlite") -> Mock:
    database = Mock()
    database.id = database_id
    database.database_name = name
    database.backend = backend
    return database


@patch("superset.security_manager.can_access_database")
@patch("superset.extensions.db.session.query")
@pytest.mark.asyncio
async def test_list_databases_filters_to_accessible_results(
    mock_query, mock_can_access_database, mcp_server
):
    databases = [
        _mock_database(1, "examples", "sqlite"),
        _mock_database(2, "warehouse", "postgresql"),
    ]
    mock_query.return_value.order_by.return_value.all.return_value = databases
    mock_can_access_database.side_effect = [True, False]

    async with Client(mcp_server) as client:
        result = await client.call_tool(
            "mcp_ext.list_databases",
            {"request": {"page": 1, "page_size": 1000}},
        )

    data = result.structured_content
    assert data["count"] == 1
    assert data["total_count"] == 1
    assert data["databases"] == [
        {"id": 1, "name": "examples", "backend": "sqlite"}
    ]


@patch("superset.security_manager.can_access_database")
@patch("superset.extensions.db.session.query")
@pytest.mark.asyncio
async def test_list_databases_supports_search_and_pagination(
    mock_query, mock_can_access_database, mcp_server
):
    databases = [
        _mock_database(1, "examples", "sqlite"),
        _mock_database(2, "analytics", "postgresql"),
        _mock_database(3, "warehouse", "postgresql"),
    ]
    mock_query.return_value.order_by.return_value.all.return_value = databases
    mock_can_access_database.return_value = True

    async with Client(mcp_server) as client:
        result = await client.call_tool(
            "mcp_ext.list_databases",
            {"request": {"page": 1, "page_size": 1, "search": "post"}},
        )

    data = result.structured_content
    assert data["count"] == 1
    assert data["total_count"] == 2
    assert data["databases"][0]["name"] == "analytics"
    assert data["databases"][0]["backend"] == "postgresql"

