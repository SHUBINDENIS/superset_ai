import unittest

from backend.us13_15_viz_service import (
    US13To15VizService,
    _extract_rows,
)


class TestUS13To15VizService(unittest.TestCase):
    def setUp(self):
        self.service = US13To15VizService(
            base_url="http://localhost:8088",
            username="admin",
            password="admin",
            timeout_seconds=5.0,
            default_preview_limit=20,
            share_base_url="http://localhost:8088",
        )

    def tearDown(self):
        self.service.close()

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


if __name__ == "__main__":
    unittest.main()
