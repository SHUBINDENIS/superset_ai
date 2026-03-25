import os
import unittest
from unittest.mock import patch

from backend.us1_schema_profiler import (
    SupersetUS1SchemaProfiler,
    _build_schema_query_rison,
    _build_heuristic_relations,
    _detect_backend_hint,
    _extract_db_id,
    _extract_db_name,
    _extract_result_items,
    _normalize_schemas,
    _normalize_tables,
)


class FakeUS1ProductClient:
    def __init__(self):
        self.calls = []

    async def list_databases(self, request=None):
        self.calls.append(("list_databases", dict(request or {})))
        return {
            "databases": [
                {"id": 11, "name": "warehouse", "backend": "postgresql"},
                {"id": 12, "name": "examples", "backend": "sqlite"},
            ],
            "total_count": 2,
        }

    async def execute_sql(self, request):
        payload = dict(request or {})
        self.calls.append(("execute_sql", payload))
        sql = str(payload.get("sql") or "")

        if "FROM information_schema.schemata" in sql:
            return {
                "success": True,
                "rows": [
                    {"schema_name": "public"},
                    {"schema_name": "analytics"},
                    {"schema_name": "pg_catalog"},
                ],
            }
        if "FROM information_schema.tables" in sql and "table_schema = 'analytics'" in sql:
            return {"success": True, "rows": []}
        if "FROM information_schema.tables" in sql and "table_schema = 'public'" in sql:
            return {
                "success": True,
                "rows": [
                    {"schema": "public", "table": "orders"},
                    {"schema": "public", "table": "customers"},
                ],
            }
        if "FROM information_schema.columns" in sql and "table_name = 'orders'" in sql:
            return {
                "success": True,
                "rows": [
                    {"column_name": "id", "data_type": "integer", "is_nullable": "NO"},
                    {"column_name": "customer_id", "data_type": "integer", "is_nullable": "NO"},
                ],
            }
        if "FROM information_schema.columns" in sql and "table_name = 'customers'" in sql:
            return {
                "success": True,
                "rows": [
                    {"column_name": "id", "data_type": "integer", "is_nullable": "NO"},
                    {"column_name": "name", "data_type": "text", "is_nullable": "YES"},
                ],
            }
        if "COUNT(*) AS row_count" in sql and '"public"."orders"' in sql:
            return {"success": True, "rows": [{"row_count": 42}]}
        if "COUNT(*) AS row_count" in sql and '"public"."customers"' in sql:
            return {"success": True, "rows": [{"row_count": 7}]}
        if "FROM information_schema.table_constraints" in sql:
            return {
                "success": True,
                "rows": [
                    {
                        "source_schema": "public",
                        "source_table": "orders",
                        "source_column": "customer_id",
                        "target_schema": "public",
                        "target_table": "customers",
                        "target_column": "id",
                        "constraint_name": "orders_customer_id_fkey",
                    }
                ],
            }

        raise AssertionError(f"Unexpected SQL payload: {payload}")

    async def close(self):
        return None


class FakeUS1Runtime:
    def __init__(self, product_client):
        self.runtime_name = "built_in_stdio"
        self.product_client = product_client
        self.closed = False

    async def close(self):
        self.closed = True


class TestUS1SchemaProfilerHelpers(unittest.TestCase):
    def test_extract_result_items(self):
        payload = {"result": [{"id": 1}, {"id": 2}]}
        self.assertEqual(len(_extract_result_items(payload)), 2)

    def test_normalize_schemas(self):
        payload = {"result": ["public", {"value": "sales"}, {"name": "analytics"}]}
        schemas = _normalize_schemas(payload)
        self.assertEqual(schemas, ["analytics", "public", "sales"])

    def test_normalize_tables(self):
        payload = {
            "result": [
                "public.orders",
                {"schema": "public", "table": "customers"},
                {"table_name": "payments", "table_schema": "billing"},
            ]
        }
        tables = _normalize_tables(payload)
        keyed = {(x["schema"], x["table"]) for x in tables}
        self.assertIn(("public", "orders"), keyed)
        self.assertIn(("public", "customers"), keyed)
        self.assertIn(("billing", "payments"), keyed)

    def test_heuristic_relations_from_id_suffix(self):
        columns_by_table = {
            ("public", "orders"): {"id", "customer_id", "amount"},
            ("public", "customers"): {"id", "name"},
        }
        fk_keys = set()
        heuristic = _build_heuristic_relations(columns_by_table, fk_keys)
        self.assertEqual(len(heuristic), 1)
        self.assertEqual(heuristic[0]["source_table"], "orders")
        self.assertEqual(heuristic[0]["target_table"], "customers")
        self.assertEqual(heuristic[0]["source_column"], "customer_id")

    def test_detect_backend_from_uri(self):
        record = {"masked_sqlalchemy_uri": "postgresql+psycopg2://***"}
        self.assertIn("postgres", _detect_backend_hint(record))

    def test_detect_backend_from_nested_json(self):
        record = {"extra": '{"engine":"clickhouse"}'}
        self.assertEqual(_detect_backend_hint(record), "clickhouse")

    def test_extract_db_identity(self):
        record = {"id": "42", "database_name": "analytics"}
        self.assertEqual(_extract_db_id(record), 42)
        self.assertEqual(_extract_db_name(record, 42), "analytics")

    def test_build_schema_query_rison(self):
        q = _build_schema_query_rison("public", force=False)
        self.assertEqual(q, "(schema_name:'public',force:false)")


class TestUS1SchemaProfilerRuntime(unittest.IsolatedAsyncioTestCase):
    async def test_build_report_uses_mcp_tools_without_rest_stack(self):
        fake_client = FakeUS1ProductClient()
        fake_runtime = FakeUS1Runtime(fake_client)
        profiler = SupersetUS1SchemaProfiler(
            base_url="http://localhost:8088",
            timeout_seconds=12.0,
            max_tables_per_db=10,
        )

        with patch(
            "backend.us1_schema_profiler.create_product_mcp_runtime",
            return_value=fake_runtime,
        ):
            report = await profiler.build_report()
            await profiler.close()

        self.assertTrue(fake_runtime.closed)
        self.assertEqual(report["summary"]["database_candidates_count"], 2)
        self.assertEqual(report["summary"]["selected_databases_count"], 1)
        self.assertEqual(report["summary"]["postgres_databases_count"], 1)
        self.assertEqual(report["summary"]["tables_profiled_count"], 2)
        self.assertEqual(report["summary"]["relations_detected_count"], 1)

        postgres_report = report["postgres_databases"][0]
        self.assertEqual(postgres_report["database_name"], "warehouse")
        self.assertEqual(postgres_report["schemas"], ["analytics", "public"])
        table_names = {
            (item["schema"], item["table"]) for item in postgres_report["tables_profiled"]
        }
        self.assertEqual(table_names, {("public", "orders"), ("public", "customers")})
        self.assertEqual(
            report["database_candidates"][0]["backend_source"],
            "mcp_ext.list_databases",
        )

        call_names = [name for name, _ in fake_client.calls]
        self.assertEqual(call_names[0], "list_databases")
        self.assertTrue(all(name in {"list_databases", "execute_sql"} for name in call_names))
        self.assertNotIn(
            "database/<id>/tables",
            " ".join(str(payload) for _, payload in fake_client.calls),
        )

    async def test_build_report_does_not_depend_on_database_tables_endpoint(self):
        fake_client = FakeUS1ProductClient()
        fake_runtime = FakeUS1Runtime(fake_client)
        profiler = SupersetUS1SchemaProfiler(base_url="http://localhost:8088")

        with (
            patch(
                "backend.us1_schema_profiler.create_product_mcp_runtime",
                return_value=fake_runtime,
            ),
            patch.dict(os.environ, {"US1_ONLY_POSTGRES": "true"}, clear=False),
        ):
            report = await profiler.build_report()
            await profiler.close()

        execute_payloads = [
            payload for name, payload in fake_client.calls if name == "execute_sql"
        ]
        self.assertGreater(len(execute_payloads), 0)
        self.assertTrue(
            all("database" not in str(payload.get("sql", "")).lower() or "/tables/" not in str(payload.get("sql", "")).lower() for payload in execute_payloads)
        )
        self.assertEqual(report["summary"]["selected_databases_count"], 1)


if __name__ == "__main__":
    unittest.main()
