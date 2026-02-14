import unittest

from backend.us1_schema_profiler import (
    _build_schema_query_rison,
    _build_heuristic_relations,
    _detect_backend_hint,
    _extract_db_id,
    _extract_db_name,
    _extract_result_items,
    _normalize_schemas,
    _normalize_tables,
)


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


if __name__ == "__main__":
    unittest.main()
