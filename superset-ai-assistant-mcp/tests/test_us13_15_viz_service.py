import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.us13_15_viz_service import (
    US13To15VizService,
    _extract_rows,
)


class TestUS13To15VizService(unittest.TestCase):
    def setUp(self):
        self.log_dir = tempfile.TemporaryDirectory()
        self.env_patcher = patch.dict(
            os.environ,
            {"ASSISTANT_LOG_DIR": self.log_dir.name},
            clear=False,
        )
        self.env_patcher.start()
        self.service = US13To15VizService(
            base_url="http://localhost:8088",
            timeout_seconds=5.0,
            default_preview_limit=20,
            share_base_url="http://localhost:8088",
        )

    def tearDown(self):
        self.service.close()
        self.env_patcher.stop()
        self.log_dir.cleanup()

    def _read_log_events(self, filename: str) -> list[dict]:
        path = Path(self.log_dir.name) / filename
        if not path.exists():
            return []
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def test_extract_rows_from_nested_result(self):
        payload = {
            "result": {
                "data": [
                    {"name": "Alice", "count": 10},
                    {"name": "Bob", "count": 7},
                ]
            }
        }
        rows = _extract_rows(payload)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["name"], "Alice")

    def test_profile_columns_infers_types_and_units(self):
        rows = [
            {"ds": "2026-02-11", "sales_amount": 120.5, "region": "RU"},
            {"ds": "2026-02-12", "sales_amount": 140.2, "region": "KZ"},
            {"ds": "2026-02-13", "sales_amount": 100.0, "region": "RU"},
        ]
        profiles = self.service.profile_columns(rows)
        by_col = {x["column"]: x for x in profiles}

        self.assertEqual(by_col["ds"]["inferred_type"], "temporal")
        self.assertEqual(by_col["sales_amount"]["inferred_type"], "numeric")
        self.assertEqual(by_col["sales_amount"]["unit"], "currency")
        self.assertEqual(by_col["region"]["inferred_type"], "text")

    def test_recommend_line_for_time_series(self):
        rows = [
            {"ds": "2026-02-11", "sales": 10},
            {"ds": "2026-02-12", "sales": 15},
            {"ds": "2026-02-13", "sales": 8},
        ]
        columns = self.service.profile_columns(rows)
        rec = self.service.recommend_viz_types(rows=rows, columns=columns)
        self.assertEqual(rec["recommended"], "line")

    def test_recommend_bar_for_category_metric(self):
        rows = [
            {"region": "RU", "orders_count": 10},
            {"region": "KZ", "orders_count": 7},
            {"region": "BY", "orders_count": 8},
        ]
        columns = self.service.profile_columns(rows)
        rec = self.service.recommend_viz_types(
            rows=rows,
            columns=columns,
            metric_column="orders_count",
            dimension_column="region",
        )
        all_types = [x["viz_type"] for x in rec["candidates"]]
        self.assertIn("bar", all_types)

    def test_build_chart_params_line(self):
        params = self.service.build_chart_params(
            dataset_id=42,
            viz_type="line",
            metric_column="sales",
            time_column="ds",
            row_limit=300,
        )
        self.assertEqual(params["datasource"], "42__table")
        self.assertEqual(params["viz_type"], "line")
        self.assertIn("metrics", params)
        self.assertEqual(params["granularity_sqla"], "ds")

    def test_build_chart_params_table(self):
        params = self.service.build_chart_params(
            dataset_id=15,
            viz_type="table",
            metric_column="sales",
            dimension_column="region",
            row_limit=100,
        )
        self.assertEqual(params["viz_type"], "table")
        self.assertIn("all_columns", params)
        self.assertIn("region", params["all_columns"])

    def test_to_absolute_url_rewrites_placeholder_host(self):
        rewritten = self.service._to_absolute_url(
            "https://your-superset-url/superset/dashboard/13/"
        )
        self.assertEqual(
            rewritten,
            "http://localhost:8088/superset/dashboard/13/",
        )

    def test_to_absolute_url_keeps_external_url(self):
        external = self.service._to_absolute_url("https://example.com/docs")
        self.assertEqual(external, "https://example.com/docs")

    def test_list_databases_uses_mcp_extension_instead_of_rest(self):
        calls = []

        def fake_call_product_client(method_name, request):
            calls.append((method_name, request))
            if method_name == "list_databases":
                return {
                    "databases": [
                        {"id": 1, "name": "examples", "backend": "sqlite"},
                        {"id": 2, "name": "warehouse", "backend": "postgresql"},
                    ]
                }
            raise AssertionError(f"unexpected method {method_name}")

        self.service._call_product_client = fake_call_product_client

        databases = self.service.list_databases()

        self.assertEqual(len(databases), 2)
        self.assertEqual(databases[0]["name"], "examples")
        self.assertEqual(calls[0][0], "list_databases")

    def test_list_databases_caches_results_until_ttl_expires(self):
        calls = []
        current_time = [100.0]
        self.service._cache_now = lambda: current_time[0]
        self.service.metadata_cache_ttl_seconds = 60.0

        def fake_call_product_client(method_name, request):
            calls.append((method_name, request))
            if method_name == "list_databases":
                return {
                    "databases": [
                        {"id": 2, "name": "pagila_demo", "backend": "postgresql"},
                    ]
                }
            raise AssertionError(f"unexpected method {method_name}")

        self.service._call_product_client = fake_call_product_client

        first = self.service.list_databases()
        second = self.service.list_databases()
        second[0]["name"] = "mutated"

        self.assertEqual(len(calls), 1)
        self.assertEqual(first[0]["name"], "pagila_demo")
        self.assertEqual(self.service.list_databases()[0]["name"], "pagila_demo")

        current_time[0] += 61.0
        refreshed = self.service.list_databases()
        self.assertEqual(len(calls), 2)
        self.assertEqual(refreshed[0]["name"], "pagila_demo")

    def test_list_datasets_cache_is_keyed_by_limit(self):
        calls = []

        def fake_call_product_client(method_name, request):
            calls.append((method_name, request))
            if method_name == "list_datasets":
                page_size = int(request["page_size"])
                return {
                    "datasets": [
                        {
                            "id": page_size,
                            "table_name": f"dataset_{page_size}",
                            "schema": "public",
                            "database_id": 7,
                            "database_name": "Pagila Demo (PostgreSQL)",
                        }
                    ]
                }
            raise AssertionError(f"unexpected method {method_name}")

        self.service._call_product_client = fake_call_product_client

        first = self.service.list_datasets(limit=10)
        second = self.service.list_datasets(limit=10)
        third = self.service.list_datasets(limit=25)

        self.assertEqual(first[0]["id"], 10)
        self.assertEqual(second[0]["id"], 10)
        self.assertEqual(third[0]["id"], 25)
        self.assertEqual([request["page_size"] for _, request in calls], [10, 25])

    def test_get_dataset_metadata_caches_results(self):
        calls = []

        def fake_call_product_client(method_name, request):
            calls.append((method_name, request))
            if method_name == "get_dataset_info":
                return {
                    "result": {
                        "id": 42,
                        "table_name": "sales_by_store",
                        "schema": "public",
                        "database_id": 7,
                        "database_name": "Pagila Demo (PostgreSQL)",
                        "columns": [
                            {
                                "column_name": "store",
                                "type": "TEXT",
                            }
                        ],
                    }
                }
            raise AssertionError(f"unexpected method {method_name}")

        self.service._call_product_client = fake_call_product_client

        first = self.service.get_dataset_metadata(42)
        second = self.service.get_dataset_metadata(42)
        second["columns"][0]["column_name"] = "mutated"

        self.assertEqual(len(calls), 1)
        self.assertEqual(first["table_name"], "sales_by_store")
        self.assertEqual(
            self.service.get_dataset_metadata(42)["columns"][0]["column_name"],
            "store",
        )

    def test_preview_sql_uses_execute_sql_through_mcp(self):
        calls = []

        def fake_call_product_client(method_name, request):
            calls.append((method_name, request))
            if method_name == "execute_sql":
                return {
                    "success": True,
                    "rows": [
                        {"ds": "2026-02-11", "sales": 10},
                        {"ds": "2026-02-12", "sales": 12},
                    ],
                }
            raise AssertionError(f"unexpected method {method_name}")

        self.service._call_product_client = fake_call_product_client

        preview = self.service.preview_sql(database_id=7, sql="SELECT ds, sales FROM fact_sales")

        self.assertEqual(preview["rows_count"], 2)
        self.assertEqual(calls[0][0], "execute_sql")
        self.assertIn("LIMIT 20", calls[0][1]["sql"])
        events = self._read_log_events("artifact.log")
        preview_event = next(item for item in events if item.get("event") == "preview_completed")
        self.assertEqual(preview_event.get("rows_count"), 2)
        self.assertEqual(preview_event.get("column_count"), 2)

    def test_preview_sql_is_not_cached(self):
        calls = []

        def fake_call_product_client(method_name, request):
            calls.append((method_name, request))
            if method_name == "execute_sql":
                return {
                    "success": True,
                    "rows": [{"store": "Store 1", "sales": 10}],
                }
            raise AssertionError(f"unexpected method {method_name}")

        self.service._call_product_client = fake_call_product_client

        self.service.preview_sql(database_id=7, sql="SELECT store, sales FROM sales_by_store")
        self.service.preview_sql(database_id=7, sql="SELECT store, sales FROM sales_by_store")

        self.assertEqual(len(calls), 2)

    def test_create_dashboard_widget_with_share_uses_built_in_mcp_flow(self):
        calls = []

        def fake_call_product_client(method_name, request):
            calls.append((method_name, request))
            if method_name == "create_empty_dashboard":
                return {
                    "dashboard": {"id": 11},
                    "dashboard_url": "/superset/dashboard/11/",
                }
            if method_name == "generate_chart":
                return {
                    "chart": {"id": 22, "url": "http://localhost:8088/explore/?slice_id=22"},
                    "explore_url": "http://localhost:8088/explore/?slice_id=22",
                    "success": True,
                }
            if method_name == "add_chart_to_existing_dashboard":
                return {
                    "dashboard": {"id": 11},
                    "dashboard_url": "/superset/dashboard/11/",
                }
            raise AssertionError(f"unexpected method {method_name}")

        self.service._call_product_client = fake_call_product_client

        result = self.service.create_dashboard_widget_with_share(
            dataset_id=7,
            dashboard_title="AI Dashboard",
            slice_name="Orders by Region",
            viz_type="bar",
            metric_column="sales",
            dimension_column="region",
        )

        self.assertEqual(result["dashboard_id"], 11)
        self.assertEqual(result["chart_id"], 22)
        self.assertEqual([name for name, _ in calls], [
            "create_empty_dashboard",
            "generate_chart",
            "add_chart_to_existing_dashboard",
        ])
        self.assertNotIn("token", str(result).casefold())
        events = self._read_log_events("artifact.log")
        event_names = [item.get("event") for item in events]
        self.assertIn("dashboard_created", event_names)
        self.assertIn("chart_created", event_names)
        self.assertIn("useful_links_produced", event_names)

    def test_create_dashboard_widget_with_share_uses_compat_chart_extension_for_pie(self):
        calls = []

        def fake_call_product_client(method_name, request):
            calls.append((method_name, request))
            if method_name == "create_empty_dashboard":
                return {
                    "dashboard": {"id": 11},
                    "dashboard_url": "/superset/dashboard/11/",
                }
            if method_name == "legacy_chart_create":
                return {
                    "chart_id": 22,
                    "chart_url": "/explore/?slice_id=22",
                }
            raise AssertionError(f"unexpected method {method_name}")

        self.service._call_product_client = fake_call_product_client

        result = self.service.create_dashboard_widget_with_share(
            dataset_id=7,
            dashboard_title="AI Dashboard",
            slice_name="Orders Share",
            viz_type="pie",
            dimension_column="region",
        )

        self.assertEqual(result["chart_id"], 22)
        self.assertEqual([name for name, _ in calls], [
            "create_empty_dashboard",
            "legacy_chart_create",
        ])

    def test_generate_explore_link_uses_built_in_tool(self):
        calls = []

        def fake_call_product_client(method_name, request):
            calls.append((method_name, request))
            if method_name == "generate_explore_link":
                return {"url": "http://localhost:8088/explore/?form_data_key=abc"}
            raise AssertionError(f"unexpected method {method_name}")

        self.service._call_product_client = fake_call_product_client
        self.service.get_dataset_metadata = lambda dataset_id: {
            "id": dataset_id,
            "columns": [{"column_name": "region"}],
        }

        url = self.service.generate_explore_link(dataset_id=7, viz_type="table")

        self.assertEqual(url, "http://localhost:8088/explore/?form_data_key=abc")
        self.assertEqual(calls[0][0], "generate_explore_link")

    def test_open_sql_lab_link_uses_built_in_tool(self):
        calls = []

        def fake_call_product_client(method_name, request):
            calls.append((method_name, request))
            if method_name == "open_sql_lab_with_context":
                return {"url": "http://localhost:8088/sqllab?dbid=7"}
            raise AssertionError(f"unexpected method {method_name}")

        self.service._call_product_client = fake_call_product_client

        url = self.service.open_sql_lab_link(
            database_id=7,
            schema_name="public",
            dataset_in_context="sales_by_store",
        )

        self.assertEqual(url, "http://localhost:8088/sqllab?dbid=7")
        self.assertEqual(calls[0][0], "open_sql_lab_with_context")


if __name__ == "__main__":
    unittest.main()
