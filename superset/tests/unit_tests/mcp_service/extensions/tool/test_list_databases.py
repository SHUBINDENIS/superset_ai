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

import superset


def _mock_database(database_id: int, name: str, backend: str = "sqlite") -> Mock:
    database = Mock()
    database.id = database_id
    database.database_name = name
    database.backend = backend
    return database


class _SortableName:
    def asc(self):
        return self


def test_list_databases_filters_to_accessible_results(load_extension_module):
    module = load_extension_module("superset.mcp_service.extensions.tool.list_databases")
    databases = [
        _mock_database(1, "examples", "sqlite"),
        _mock_database(2, "warehouse", "postgresql"),
    ]
    fake_db = Mock()
    fake_db.session.query.return_value.order_by.return_value.all.return_value = databases
    fake_security_manager = Mock()
    fake_security_manager.can_access_database.side_effect = [True, False]
    fake_core_module = ModuleType("superset.models.core")
    fake_core_module.Database = type(
        "Database",
        (),
        {"database_name": _SortableName()},
    )

    with (
        patch.object(superset, "db", fake_db),
        patch.object(superset, "security_manager", fake_security_manager),
        patch.dict(sys.modules, {"superset.models.core": fake_core_module}),
    ):
        result = module.list_databases({"page": 1, "page_size": 1000}, Mock())

    assert result.count == 1
    assert result.total_count == 1
    assert [item.model_dump(mode="json") for item in result.databases] == [
        {"id": 1, "name": "examples", "backend": "sqlite"}
    ]


def test_list_databases_supports_search_and_pagination(load_extension_module):
    module = load_extension_module("superset.mcp_service.extensions.tool.list_databases")
    databases = [
        _mock_database(1, "examples", "sqlite"),
        _mock_database(2, "analytics", "postgresql"),
        _mock_database(3, "warehouse", "postgresql"),
    ]
    fake_db = Mock()
    fake_db.session.query.return_value.order_by.return_value.all.return_value = databases
    fake_security_manager = Mock()
    fake_security_manager.can_access_database.return_value = True
    fake_core_module = ModuleType("superset.models.core")
    fake_core_module.Database = type(
        "Database",
        (),
        {"database_name": _SortableName()},
    )

    with (
        patch.object(superset, "db", fake_db),
        patch.object(superset, "security_manager", fake_security_manager),
        patch.dict(sys.modules, {"superset.models.core": fake_core_module}),
    ):
        result = module.list_databases(
            {"page": 1, "page_size": 1, "search": "post"},
            Mock(),
        )

    assert result.count == 1
    assert result.total_count == 2
    assert result.databases[0].name == "analytics"
    assert result.databases[0].backend == "postgresql"
