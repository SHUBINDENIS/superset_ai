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

"""Tests for MCP URL helpers."""

from unittest.mock import patch

from flask import Flask

from superset.mcp_service.utils.url_utils import get_superset_base_url


class TestGetSupersetBaseUrl:
    def test_prefers_public_url_env_outside_app_context(self) -> None:
        with patch.dict(
            "os.environ",
            {"SUPERSET_PUBLIC_URL": "http://103.54.18.91:8088/"},
            clear=False,
        ):
            assert get_superset_base_url() == "http://103.54.18.91:8088"

    def test_prefers_public_url_config_over_internal_address(self) -> None:
        app = Flask(__name__)
        app.config["SUPERSET_PUBLIC_URL"] = "https://demo.example.com/superset/"
        app.config["SUPERSET_WEBSERVER_ADDRESS"] = "http://superset:8088"

        with app.app_context():
            assert get_superset_base_url() == "https://demo.example.com/superset"
