"""
Tests for the FastAPI preview / recommend / share endpoints.

The underlying US13-US15 service is dependency-overridden with a lightweight
fake so these tests stay fast and do not require MCP, Superset, or OpenAI.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


def _fresh_app():
    import api.deps as deps_mod

    deps_mod._auth_service_instance = None
    deps_mod._AuthService = None
    deps_mod._agent_session_manager = None
    deps_mod._us13_15_viz_service_instance = None

    from api.main import app

    app.dependency_overrides.clear()
    return app, deps_mod


class FakeVizService:
    def __init__(self):
        self.last_dataset_limit = None
        self.last_preview_payload = None
        self.last_recommend_payload = None
        self.last_share_payload = None

    def list_databases(self):
        return [
            {"id": 7, "name": "Pagila Demo (PostgreSQL)", "backend": "postgresql"},
        ]

    def list_datasets(self, limit: int = 300):
        self.last_dataset_limit = limit
        return [
            {
                "id": 42,
                "table_name": "sales_by_store",
                "schema": "public",
                "database_name": "Pagila Demo (PostgreSQL)",
                "database_id": 7,
            }
        ]

    def get_dataset_metadata(self, dataset_id: int):
        return {
            "id": int(dataset_id),
            "table_name": "sales_by_store",
            "schema": "public",
            "database_id": 7,
            "database_name": "Pagila Demo (PostgreSQL)",
            "columns": [
                {"column_name": "store", "verbose_name": "", "type": "TEXT"},
                {"column_name": "total_sales", "verbose_name": "", "type": "NUMERIC"},
            ],
            "metrics": ["sum__total_sales"],
        }

    def preview_sql(self, *, database_id: int, sql: str, schema: str = "", preview_limit: int = 20):
        self.last_preview_payload = {
            "database_id": database_id,
            "sql": sql,
            "schema": schema,
            "preview_limit": preview_limit,
        }
        return {
            "database_id": int(database_id),
            "schema": schema,
            "sql_executed": sql,
            "preview_limit": int(preview_limit),
            "rows_count": 2,
            "rows": [
                {"store": "Store 1", "total_sales": 101.5},
                {"store": "Store 2", "total_sales": 88.0},
            ],
            "columns": [
                {
                    "column": "store",
                    "inferred_type": "text",
                    "unit": "",
                    "non_null_count": 2,
                    "distinct_count": 2,
                    "sample_value": "Store 1",
                    "explanation": "store: тип=text, уникальных значений=2; подходит для группировок/категорий.",
                },
                {
                    "column": "total_sales",
                    "inferred_type": "numeric",
                    "unit": "currency",
                    "non_null_count": 2,
                    "distinct_count": 2,
                    "sample_value": 101.5,
                    "explanation": "total_sales: тип=numeric, единица=currency, уникальных значений=2; подходит для метрик/агрегаций.",
                },
            ],
            "field_explanations": [
                {"column": "store", "explanation": "Категория магазина."},
                {"column": "total_sales", "explanation": "Сумма продаж."},
            ],
        }

    def recommend_viz_types(self, *, rows, columns, metric_column="", dimension_column="", time_column=""):
        self.last_recommend_payload = {
            "rows": rows,
            "columns": columns,
            "metric_column": metric_column,
            "dimension_column": dimension_column,
            "time_column": time_column,
        }
        return {
            "recommended": "bar",
            "candidates": [
                {"viz_type": "bar", "score": 0.92, "reason": "Подходит для категорий и метрики."},
                {"viz_type": "table", "score": 0.50, "reason": "Табличный fallback."},
            ],
            "selected_columns": {
                "metric": metric_column or "total_sales",
                "dimension": dimension_column or "store",
                "time": time_column or "",
            },
        }

    def create_dashboard_widget_with_share(
        self,
        *,
        dataset_id: int,
        dashboard_title: str,
        slice_name: str,
        viz_type: str,
        metric_column: str = "",
        dimension_column: str = "",
        time_column: str = "",
        row_limit: int = 1000,
        description: str = "",
    ):
        self.last_share_payload = {
            "dataset_id": dataset_id,
            "dashboard_title": dashboard_title,
            "slice_name": slice_name,
            "viz_type": viz_type,
            "metric_column": metric_column,
            "dimension_column": dimension_column,
            "time_column": time_column,
            "row_limit": row_limit,
            "description": description,
        }
        return {
            "dashboard_id": 11,
            "chart_id": 22,
            "dashboard_url": "/superset/dashboard/11/",
            "chart_url": "/explore/?slice_id=22",
            "dashboard_link": "http://localhost:8088/superset/dashboard/11/",
            "chart_link": "http://localhost:8088/explore/?slice_id=22",
            "params": {"viz_type": viz_type, "row_limit": row_limit},
            "viz_type": viz_type,
        }


class TestVizAPI(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = str(Path(self.temp_dir.name) / "viz_test.db")
        self.env_patch = patch.dict(
            os.environ,
            {
                "AUTH_DB_PATH": db_path,
                "AUTH_JWT_SECRET": "test-viz-secret",
                "AUTH_JWT_TTL_HOURS": "1",
                "AUTH_PASSWORD_MIN_LENGTH": "8",
            },
            clear=False,
        )
        self.env_patch.start()

        self.app, self.deps_mod = _fresh_app()
        self.client = TestClient(self.app)
        self.fake_viz_service = FakeVizService()

        from api.deps import get_viz_service

        self.app.dependency_overrides[get_viz_service] = lambda: self.fake_viz_service

        self.client.post(
            "/api/auth/register",
            json={"username": "vizuser", "password": "strongpass"},
        )
        login_resp = self.client.post(
            "/api/auth/login",
            json={"username": "vizuser", "password": "strongpass"},
        )
        self.token = login_resp.cookies.get("ai_assistant_auth_token")

    def tearDown(self):
        self.app.dependency_overrides.clear()
        self.deps_mod._auth_service_instance = None
        self.deps_mod._AuthService = None
        self.deps_mod._agent_session_manager = None
        self.deps_mod._us13_15_viz_service_instance = None
        self.env_patch.stop()
        self.temp_dir.cleanup()

    def _auth_cookies(self):
        return {"ai_assistant_auth_token": self.token}

    def test_list_databases(self):
        resp = self.client.get("/api/viz/databases", cookies=self._auth_cookies())
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["databases"][0]["id"], 7)
        self.assertEqual(data["databases"][0]["backend"], "postgresql")

    def test_list_datasets_passes_limit(self):
        resp = self.client.get("/api/viz/datasets?limit=123", cookies=self._auth_cookies())
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["datasets"][0]["id"], 42)
        self.assertEqual(self.fake_viz_service.last_dataset_limit, 123)

    def test_get_dataset_metadata(self):
        resp = self.client.get("/api/viz/datasets/42", cookies=self._auth_cookies())
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["id"], 42)
        self.assertEqual(len(data["columns"]), 2)

    def test_preview_endpoint(self):
        resp = self.client.post(
            "/api/viz/preview",
            json={
                "database_id": 7,
                "dataset_id": 42,
                "schema": "public",
                "sql": "SELECT * FROM public.sales_by_store LIMIT 2",
                "preview_limit": 20,
            },
            cookies=self._auth_cookies(),
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["dataset_id"], 42)
        self.assertEqual(data["rows_count"], 2)
        self.assertEqual(data["columns"][1]["column"], "total_sales")
        self.assertEqual(self.fake_viz_service.last_preview_payload["database_id"], 7)

    def test_recommend_endpoint(self):
        resp = self.client.post(
            "/api/viz/recommend",
            json={
                "rows": [{"store": "Store 1", "total_sales": 101.5}],
                "columns": [
                    {
                        "column": "store",
                        "inferred_type": "text",
                        "unit": "",
                        "non_null_count": 1,
                        "distinct_count": 1,
                        "sample_value": "Store 1",
                        "explanation": "Категория магазина.",
                    },
                    {
                        "column": "total_sales",
                        "inferred_type": "numeric",
                        "unit": "currency",
                        "non_null_count": 1,
                        "distinct_count": 1,
                        "sample_value": 101.5,
                        "explanation": "Сумма продаж.",
                    },
                ],
                "metric_column": "total_sales",
                "dimension_column": "store",
            },
            cookies=self._auth_cookies(),
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["recommended"], "bar")
        self.assertEqual(data["selected_columns"]["metric"], "total_sales")

    def test_share_widget_endpoint(self):
        resp = self.client.post(
            "/api/viz/share/widget",
            json={
                "dataset_id": 42,
                "dashboard_title": "Demo dashboard",
                "slice_name": "Demo chart",
                "viz_type": "bar",
                "metric_column": "total_sales",
                "dimension_column": "store",
                "row_limit": 1000,
            },
            cookies=self._auth_cookies(),
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["dashboard_id"], 11)
        self.assertEqual(data["chart_id"], 22)
        self.assertTrue(data["dashboard_link"].startswith("http://"))
        self.assertEqual(self.fake_viz_service.last_share_payload["dataset_id"], 42)

    def test_viz_endpoints_require_auth(self):
        anon = TestClient(self.app)
        resp = anon.get("/api/viz/databases")
        self.assertEqual(resp.status_code, 401)


if __name__ == "__main__":
    unittest.main()
