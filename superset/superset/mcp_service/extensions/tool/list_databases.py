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
Product migration extension: list accessible databases.
"""

from __future__ import annotations

from typing import List

from fastmcp import Context
from pydantic import BaseModel, Field, PositiveInt
from superset_core.mcp import tool

from superset.mcp_service.utils.schema_utils import parse_request


class ListDatabasesRequest(BaseModel):
    page: PositiveInt = Field(default=1, description="1-based page number")
    page_size: PositiveInt = Field(
        default=1000,
        description="Maximum number of databases to return",
    )
    search: str | None = Field(
        default=None,
        description="Optional case-insensitive search against database name/backend",
    )


class DatabaseSummary(BaseModel):
    id: int = Field(..., description="Database identifier")
    name: str = Field(..., description="Database name")
    backend: str = Field(..., description="Database backend/engine")


class ListDatabasesResponse(BaseModel):
    databases: List[DatabaseSummary] = Field(default_factory=list)
    count: int = Field(..., description="Count of items in current page")
    total_count: int = Field(..., description="Total accessible database count")
    page: int = Field(..., description="1-based page number")
    page_size: int = Field(..., description="Requested page size")


@tool(name="mcp_ext.list_databases", tags=["extension"])
@parse_request(ListDatabasesRequest)
def list_databases(
    request: ListDatabasesRequest, ctx: Context
) -> ListDatabasesResponse:
    """List accessible databases for product source pickers."""
    del ctx

    from superset import db, security_manager
    from superset.models.core import Database

    search_token = str(request.search or "").strip().casefold()

    candidates = (
        db.session.query(Database).order_by(Database.database_name.asc()).all()
    )
    accessible = []
    for database in candidates:
        if not security_manager.can_access_database(database):
            continue
        name = str(getattr(database, "database_name", "") or "").strip()
        backend = str(
            getattr(database, "backend", None)
            or getattr(database, "engine", None)
            or "unknown"
        ).strip()
        haystack = f"{name} {backend}".casefold()
        if search_token and search_token not in haystack:
            continue
        accessible.append(
            DatabaseSummary(
                id=int(database.id),
                name=name or f"db_{database.id}",
                backend=backend or "unknown",
            )
        )

    total_count = len(accessible)
    start = (request.page - 1) * request.page_size
    end = start + request.page_size
    page_items = accessible[start:end]

    return ListDatabasesResponse(
        databases=page_items,
        count=len(page_items),
        total_count=total_count,
        page=request.page,
        page_size=request.page_size,
    )

