"""
Tests for the FastAPI US1 schema scan endpoint.

The real US1 profiler is dependency-overridden with a lightweight async fake
so these tests stay fast and do not require MCP, Superset, or OpenAI.
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
    deps_mod._us1_scan_runner_instance = None

    from api.main import app

    app.dependency_overrides.clear()
    return app, deps_mod


async def _fake_scan_runner():
    return {
        "report_path": "/tmp/us1_report.json",
        "summary": {
            "database_candidates_count": 2,
            "postgres_candidates_count": 1,
            "selected_databases_count": 1,
            "postgres_databases_count": 1,
            "tables_profiled_count": 3,
            "relations_detected_count": 2,
        },
        "report": {
            "generated_at": "2026-03-26T20:00:00+00:00",
            "superset_base_url": "http://localhost:8088",
            "database_candidates": [
                {
                    "database_id": 11,
                    "database_name": "warehouse",
                    "backend_hint": "postgresql",
                    "backend_source": "mcp_ext.list_databases",
                    "is_postgres": True,
                },
                {
                    "database_id": 12,
                    "database_name": "examples",
                    "backend_hint": "sqlite",
                    "backend_source": "mcp_ext.list_databases",
                    "is_postgres": False,
                },
            ],
            "postgres_databases": [
                {
                    "database_id": 11,
                    "database_name": "warehouse",
                    "backend": "postgresql",
                    "schemas": ["public", "analytics"],
                    "tables_profiled": [
                        {
                            "schema": "public",
                            "table": "orders",
                            "row_count": 42,
                            "column_count": 5,
                            "columns": [],
                        },
                        {
                            "schema": "public",
                            "table": "customers",
                            "row_count": 7,
                            "column_count": 3,
                            "columns": [],
                        },
                    ],
                    "relations": {
                        "foreign_keys": [
                            {
                                "source_schema": "public",
                                "source_table": "orders",
                                "source_column": "customer_id",
                                "target_schema": "public",
                                "target_table": "customers",
                                "target_column": "id",
                                "constraint_name": "orders_customer_id_fkey",
                                "confidence": "high",
                            }
                        ],
                        "heuristic": [
                            {
                                "source_schema": "public",
                                "source_table": "payments",
                                "source_column": "order_id",
                                "target_schema": "public",
                                "target_table": "orders",
                                "target_column": "id",
                                "confidence": "medium",
                            }
                        ],
                    },
                }
            ],
        },
    }


async def _raising_scan_runner():
    raise RuntimeError("scan failed")


class TestScanAPI(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = str(Path(self.temp_dir.name) / "scan_test.db")
        self.env_patch = patch.dict(
            os.environ,
            {
                "AUTH_DB_PATH": db_path,
                "AUTH_JWT_SECRET": "test-scan-secret",
                "AUTH_JWT_TTL_HOURS": "1",
                "AUTH_PASSWORD_MIN_LENGTH": "8",
            },
            clear=False,
        )
        self.env_patch.start()

        self.app, self.deps_mod = _fresh_app()
        self.client = TestClient(self.app)

        from api.deps import get_us1_scan_runner

        self.app.dependency_overrides[get_us1_scan_runner] = lambda: _fake_scan_runner

        self.client.post(
            "/api/auth/register",
            json={"username": "scanuser", "password": "strongpass"},
        )
        login_resp = self.client.post(
            "/api/auth/login",
            json={"username": "scanuser", "password": "strongpass"},
        )
        self.token = login_resp.cookies.get("ai_assistant_auth_token")

    def tearDown(self):
        self.app.dependency_overrides.clear()
        self.deps_mod._auth_service_instance = None
        self.deps_mod._AuthService = None
        self.deps_mod._agent_session_manager = None
        self.deps_mod._us13_15_viz_service_instance = None
        self.deps_mod._us1_scan_runner_instance = None
        self.env_patch.stop()
        self.temp_dir.cleanup()

    def _auth_cookies(self):
        return {"ai_assistant_auth_token": self.token}

    def test_run_scan_success(self):
        resp = self.client.post("/api/scan", cookies=self._auth_cookies())
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["summary"]["tables_profiled_count"], 3)
        self.assertEqual(data["report"]["postgres_databases"][0]["database_name"], "warehouse")
        self.assertTrue(data["started_at"])
        self.assertTrue(data["finished_at"])

    def test_run_scan_requires_auth(self):
        anon = TestClient(self.app)
        resp = anon.post("/api/scan")
        self.assertEqual(resp.status_code, 401)

    def test_run_scan_maps_backend_error(self):
        from api.deps import get_us1_scan_runner

        self.app.dependency_overrides[get_us1_scan_runner] = lambda: _raising_scan_runner
        resp = self.client.post("/api/scan", cookies=self._auth_cookies())
        self.assertEqual(resp.status_code, 503)
        self.assertIn("scan failed", resp.json()["detail"])


if __name__ == "__main__":
    unittest.main()
