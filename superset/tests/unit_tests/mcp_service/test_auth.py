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

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from flask import Flask, g

from superset.mcp_service.auth import get_user_from_request


def _build_test_flask_app() -> Flask:
    app = Flask(__name__)
    app.config["MCP_DEV_USERNAME"] = "admin"
    return app


def test_get_user_from_request_rebinds_existing_g_user():
    flask_app = _build_test_flask_app()
    detached_user = SimpleNamespace(id=7, username="admin", is_anonymous=False)
    bound_user = MagicMock(id=7, username="admin", roles=[], groups=[])
    mock_query = MagicMock()
    mock_query.options.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.first.side_effect = [bound_user]

    with flask_app.app_context():
        g.user = detached_user
        with patch("superset.extensions.db.session.query", return_value=mock_query):
            resolved_user = get_user_from_request()

    assert resolved_user is bound_user
    mock_query.options.assert_called_once()
    mock_query.filter.assert_called_once()
    mock_query.first.assert_called_once()
