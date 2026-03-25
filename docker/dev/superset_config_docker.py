"""Overrides for the optional unified local dev compose stack.

This file is mounted only by `docker-compose.dev.yml`.
It keeps the baseline split deployment untouched while making the containerized
demo stack usable on a shared Docker network.
"""

from superset_config import *  # noqa: F403


FEATURE_FLAGS = {**FEATURE_FLAGS, "MCP_SERVICE": True}  # noqa: F405

# Single-user MCP auth context for local development only.
MCP_AUTH_ENABLED = False
MCP_DEV_USERNAME = "admin"

# Internal Docker-network URLs used by the MCP HTTP sidecar and generated links.
SUPERSET_WEBSERVER_ADDRESS = "http://superset:8088"
WEBDRIVER_BASEURL = "http://superset:8088/"
WEBDRIVER_BASEURL_USER_FRIENDLY = "http://localhost:8088/"
MCP_SERVICE_URL = "http://mcp-http:5008/mcp/"
