import tempfile
import unittest
from pathlib import Path

from backend.us2_glossary_service import GlossaryService
from backend.us4_query_assistant import (
    DEFAULT_US4_EXAMPLES,
    US4QueryAssistantService,
)


class TestUS4QueryAssistantService(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        glossary_db = Path(self.temp_dir.name) / "glossary_us4_test.db"
        self.glossary = GlossaryService(db_path=str(glossary_db))

        term = self.glossary.create_term(
            term="Выручка",
            definition="Сумма продаж",
            examples=["выручка по регионам"],
        )
        self.glossary.add_mapping(
            term_id=term["id"],
            database_name="analytics_pg",
            schema_name="public",
            table_name="orders",
            column_name="revenue",
        )
        term2 = self.glossary.create_term(
            term="Маржа",
            definition="Маржинальность",
            examples=["маржа по категориям"],
        )
        self.glossary.add_mapping(
            term_id=term2["id"],
            database_name="finance_pg",
            schema_name="public",
            table_name="costs",
            column_name="margin",
        )
        self.service = US4QueryAssistantService(glossary_service=self.glossary)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_examples_catalog_has_required_size(self):
        self.assertGreaterEqual(len(DEFAULT_US4_EXAMPLES), 10)
        titles = [item["title"] for item in DEFAULT_US4_EXAMPLES]
        self.assertIn("Выручка по месяцам", titles)

    def test_list_examples_search(self):
        result = self.service.list_examples(search="когорт")
        self.assertTrue(result)
        self.assertIn("когорт", result[0]["query"].casefold() + result[0]["description"].casefold())

    def test_entities_autocomplete_from_glossary(self):
        entities = self.service.suggest_entities(prefix="выр")
        self.assertIn("Выручка", entities)

        entities_by_column = self.service.suggest_entities(prefix="rev")
        self.assertIn("revenue", entities_by_column)

    def test_apply_entity_replaces_last_token(self):
        updated = self.service.apply_entity_to_query("Покажи выр", "Выручка")
        self.assertEqual(updated, "Покажи Выручка")

    def test_context_contains_examples_and_entities(self):
        context = self.service.build_agent_context_for_query("Покажи выр")
        self.assertIn("US4 примеры запросов", context)
        self.assertIn("US4 автодополнение сущностей", context)
        self.assertIn("Выручка", context)

    def test_entities_can_be_filtered_by_scope(self):
        entities = self.service.suggest_entities_for_query(
            "Покажи rev",
            preferred_database="analytics_pg",
            preferred_table="public.orders",
        )
        joined = " ".join(entities).casefold()
        self.assertIn("revenue", joined)
        self.assertNotIn("margin", joined)

    def test_generate_table_sql_candidates_uses_profile(self):
        candidates = self.service.generate_table_sql_candidates(
            table_name="orders",
            schema_name="public",
            columns=[
                {
                    "column": "order_date",
                    "inferred_type": "temporal",
                    "non_null_count": 10,
                },
                {
                    "column": "region",
                    "inferred_type": "text",
                    "non_null_count": 10,
                },
                {
                    "column": "revenue",
                    "inferred_type": "numeric",
                    "non_null_count": 10,
                },
            ],
            sample_rows=[],
            max_candidates=10,
        )
        self.assertGreaterEqual(len(candidates), 6)
        titles_blob = "\n".join(item["title"] for item in candidates)
        sql_blob = "\n".join(item["sql"] for item in candidates)
        self.assertIn("KPI", titles_blob)
        self.assertIn("Лидеры", titles_blob)
        self.assertIn("Динамика", titles_blob)
        self.assertIn('FROM "public"."orders"', sql_blob)
        self.assertIn('SUM("revenue") AS metric_total', sql_blob)
        self.assertIn("date_trunc('month', \"order_date\")", sql_blob)
        self.assertIn("ROUND(", sql_blob)

    def test_generate_table_sql_candidates_respects_limit(self):
        candidates = self.service.generate_table_sql_candidates(
            table_name="orders",
            schema_name="public",
            columns=[
                {
                    "column": "region",
                    "inferred_type": "text",
                    "non_null_count": 10,
                },
                {
                    "column": "revenue",
                    "inferred_type": "numeric",
                    "non_null_count": 10,
                },
            ],
            sample_rows=[],
            max_candidates=3,
        )
        self.assertEqual(len(candidates), 3)
        sql_set = {item["sql"] for item in candidates}
        self.assertEqual(len(sql_set), len(candidates))

    def test_generate_table_sql_candidates_uses_sample_business_context(self):
        candidates = self.service.generate_table_sql_candidates(
            table_name="orders",
            schema_name="public",
            columns=[
                {"column": "order_date", "inferred_type": "temporal", "non_null_count": 10},
                {"column": "region", "inferred_type": "text", "non_null_count": 10},
                {"column": "revenue", "inferred_type": "numeric", "non_null_count": 10},
            ],
            sample_rows=[
                {"order_date": "2025-01-01", "region": "Москва", "revenue": 1000},
                {"order_date": "2025-01-08", "region": "СПб", "revenue": 1300},
                {"order_date": "2025-02-01", "region": "Москва", "revenue": 1600},
                {"order_date": "2025-02-11", "region": "Казань", "revenue": 1200},
            ],
            max_candidates=10,
        )
        self.assertGreaterEqual(len(candidates), 8)
        descriptions_blob = "\n".join(item["description"] for item in candidates)
        titles_blob = "\n".join(item["title"] for item in candidates)
        self.assertIn("Примеры сегментов", descriptions_blob)
        self.assertIn("период:", descriptions_blob)
        self.assertIn("Концентрация", titles_blob)
        self.assertIn("Последний период vs предыдущий", titles_blob)


if __name__ == "__main__":
    unittest.main()
