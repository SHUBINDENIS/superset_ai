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
import os
import sys
from types import ModuleType
from typing import Callable
from unittest.mock import patch

import pytest
import superset_core.mcp
from _pytest.fixtures import SubRequest

from superset.app import SupersetApp
from superset.initialization import SupersetAppInitializer


def _identity_tool(
    func_or_name: str | Callable | None = None, **_: object
) -> Callable | object:
    def decorator(func: Callable) -> Callable:
        return func

    if callable(func_or_name):
        return func_or_name
    return decorator


@pytest.fixture
def load_extension_module() -> Callable[[str], ModuleType]:
    def _load(module_name: str) -> ModuleType:
        for loaded_name in list(sys.modules):
            if loaded_name == module_name or loaded_name.startswith(f"{module_name}."):
                sys.modules.pop(loaded_name, None)

        with patch.object(superset_core.mcp, "tool", _identity_tool):
            return importlib.import_module(module_name)

    return _load


@pytest.fixture(scope="module")
def app(request: SubRequest) -> SupersetApp:
    app = SupersetApp(__name__)
    app.config.from_object("superset.config")
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        os.environ.get("SUPERSET__SQLALCHEMY_DATABASE_URI") or "sqlite://"
    )
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["PREVENT_UNSAFE_DB_CONNECTIONS"] = False
    app.config["TESTING"] = True
    app.config["RATELIMIT_ENABLED"] = False
    app.config["CACHE_CONFIG"] = {}
    app.config["DATA_CACHE_CONFIG"] = {}
    app.config["SERVER_NAME"] = "example.com"
    app.config["APPLICATION_ROOT"] = "/"
    app.config["PREFERRED_URL_SCHEME="] = "http"

    if request and hasattr(request, "param"):
        for key, value in request.param.items():
            app.config[key] = value

    from superset.extensions import appbuilder

    appbuilder.baseviews = []

    app_initializer = SupersetAppInitializer(app)
    app_initializer.init_app()
    return app


@pytest.fixture(autouse=True)
def app_context(app: SupersetApp):
    with app.app_context():
        yield
