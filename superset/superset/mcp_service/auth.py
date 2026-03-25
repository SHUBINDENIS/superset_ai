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
Minimal authentication hooks for MCP tools.
This is a placeholder implementation that provides basic user context.

Future enhancements (to be added in separate PRs):
- JWT token authentication and validation
- User impersonation support
- Permission checking with scopes
- Comprehensive audit logging
- Field-level permissions
"""

import logging
from typing import Any, Callable, TYPE_CHECKING, TypeVar

from flask import g
from flask_appbuilder.security.sqla.models import User

if TYPE_CHECKING:
    from superset.connectors.sqla.models import SqlaTable

# Type variable for decorated functions
F = TypeVar("F", bound=Callable[..., Any])

logger = logging.getLogger(__name__)


def _load_session_bound_user(
    *,
    user_id: int | None,
    username: str | None,
) -> User | None:
    """Load a fresh, session-bound user with roles and groups eagerly loaded."""
    from sqlalchemy.orm import joinedload

    from superset.extensions import db

    query = db.session.query(User).options(
        joinedload(User.roles),
        joinedload(User.groups),
    )

    if user_id is not None:
        user = query.filter(User.id == user_id).first()
        if user is not None:
            return user

    if username:
        return query.filter(User.username == username).first()

    return None


def get_user_from_request() -> User:
    """
    Get the current user for the MCP tool request.

    Priority order:
    1. g.user if already set (by Preset workspace middleware)
    2. MCP_DEV_USERNAME from configuration (for development/testing)

    Returns:
        User object with roles and groups eagerly loaded

    Raises:
        ValueError: If user cannot be authenticated or found
    """
    from flask import current_app
    # First check if user is already set by Preset workspace middleware or
    # a previous MCP tool call. Always requery to avoid reusing detached users
    # across sequential or concurrent tool execution in the same session.
    existing_user = getattr(g, "user", None)
    if existing_user and not getattr(existing_user, "is_anonymous", False):
        fresh_user = _load_session_bound_user(
            user_id=getattr(existing_user, "id", None),
            username=getattr(existing_user, "username", None),
        )
        if fresh_user is not None:
            return fresh_user

    # Fall back to configured username for development/single-user deployments
    username = current_app.config.get("MCP_DEV_USERNAME")

    if not username:
        raise ValueError(
            "No authenticated user found. "
            "Either pass a valid JWT bearer token or configure "
            "MCP_DEV_USERNAME for development."
        )

    # Query user directly with eager loading to ensure fresh session-bound object.
    # Do NOT use security_manager.find_user() as it may return cached/detached user.
    user = _load_session_bound_user(user_id=None, username=username)

    if not user:
        raise ValueError(
            f"User '{username}' not found. "
            f"Please create admin user with: superset fab create-admin"
        )

    return user


def has_dataset_access(dataset: "SqlaTable") -> bool:
    """
    Validate user has access to the dataset.

    This function checks if the current user (from Flask g.user context)
    has permission to access the given dataset using Superset's security manager.

    Args:
        dataset: The SqlaTable dataset to check access for

    Returns:
        True if user has access, False otherwise

    Security Note:
        This should be called after mcp_auth_hook has set g.user.
        Returns False on any error to fail securely.
    """
    try:
        from superset import security_manager

        # Check if user has read access to the dataset
        if hasattr(g, "user") and g.user:
            # Use Superset's security manager to check dataset access
            return security_manager.can_access_datasource(datasource=dataset)

        # If no user context, deny access
        return False

    except Exception as e:
        logger.warning("Error checking dataset access: %s", e)
        return False  # Deny access on error


def _setup_user_context() -> User:
    """
    Set up user context for MCP tool execution.

    Returns:
        User object with roles and groups loaded
    """
    user = get_user_from_request()

    # Validate user has necessary relationships loaded
    # (Force access to ensure they're loaded if lazy)
    user_roles = user.roles  # noqa: F841
    if hasattr(user, "groups"):
        user_groups = user.groups  # noqa: F841

    g.user = user
    return user


def _cleanup_session_on_error() -> None:
    """Clean up database session after an exception."""
    from superset.extensions import db

    try:
        db.session.rollback()
    except Exception as e:
        logger.warning("Error cleaning up session after exception: %s", e)


def _cleanup_session_finally() -> None:
    """No-op cleanup.

    Flask app-context teardown removes the scoped session for each MCP tool call.
    Rolling back here expires objects inside the still-running context and breaks
    concurrent tool execution that relies on eager-loaded relationships.
    """


def mcp_auth_hook(tool_func: F) -> F:
    """
    Authentication and authorization decorator for MCP tools.

    This decorator assumes Flask application context and g.user
    have already been set by WorkspaceContextMiddleware.

    Supports both sync and async tool functions.

    TODO (future PR): Add permission checking
    TODO (future PR): Add JWT scope validation
    TODO (future PR): Add comprehensive audit logging
    """
    import functools
    import inspect

    is_async = inspect.iscoroutinefunction(tool_func)

    if is_async:

        @functools.wraps(tool_func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            user = _setup_user_context()

            try:
                logger.debug(
                    "MCP tool call: user=%s, tool=%s",
                    user.username,
                    tool_func.__name__,
                )
                result = await tool_func(*args, **kwargs)
                return result
            except Exception:
                _cleanup_session_on_error()
                raise
            finally:
                _cleanup_session_finally()

        return async_wrapper  # type: ignore[return-value]

    else:

        @functools.wraps(tool_func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            user = _setup_user_context()

            try:
                logger.debug(
                    "MCP tool call: user=%s, tool=%s",
                    user.username,
                    tool_func.__name__,
                )
                result = tool_func(*args, **kwargs)
                return result
            except Exception:
                _cleanup_session_on_error()
                raise
            finally:
                _cleanup_session_finally()

        return sync_wrapper  # type: ignore[return-value]
