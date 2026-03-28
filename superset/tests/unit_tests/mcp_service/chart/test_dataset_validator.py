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

"""Tests for dataset-aware validation of MCP chart configs."""

from unittest.mock import patch

from superset.mcp_service.chart.schemas import ColumnRef, XYChartConfig
from superset.mcp_service.chart.validation import DatasetValidator
from superset.mcp_service.common.error_schemas import DatasetContext


class TestDatasetValidator:
    def test_extract_column_references_skips_row_count_metric(self) -> None:
        config = XYChartConfig(
            chart_type="xy",
            x=ColumnRef(name="YEAR"),
            y=[ColumnRef(name="count", aggregate="COUNT")],
            kind="bar",
        )

        refs = DatasetValidator._extract_column_references(config)

        assert [ref.name for ref in refs] == ["YEAR"]

    @patch.object(DatasetValidator, "_get_dataset_context")
    def test_validate_against_dataset_allows_synthetic_row_count(
        self, mock_get_dataset_context
    ) -> None:
        mock_get_dataset_context.return_value = DatasetContext(
            id=1,
            table_name="flights",
            schema="public",
            database_name="examples",
            available_columns=[
                {
                    "name": "YEAR",
                    "type": "INTEGER",
                    "is_temporal": False,
                    "is_numeric": True,
                }
            ],
            available_metrics=[],
        )
        config = XYChartConfig(
            chart_type="xy",
            x=ColumnRef(name="YEAR"),
            y=[ColumnRef(name="count", aggregate="COUNT")],
            kind="bar",
        )

        is_valid, error = DatasetValidator.validate_against_dataset(config, 1)

        assert is_valid is True
        assert error is None
