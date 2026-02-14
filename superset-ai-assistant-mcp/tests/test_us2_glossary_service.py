import tempfile
import unittest
from pathlib import Path

from backend.us2_glossary_service import GlossaryService


class TestGlossaryService(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(self.temp_dir.name) / "glossary_test.db"
        self.service = GlossaryService(db_path=str(db_path))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_term_crud(self):
        created = self.service.create_term(
            term="Выручка",
            definition="Сумма продаж за период",
            examples=["выручка за месяц", "общая выручка"],
        )
        self.assertEqual(created["term"], "Выручка")
        self.assertEqual(len(created["examples"]), 2)

        listed = self.service.list_terms()
        self.assertEqual(len(listed), 1)

        updated = self.service.update_term(
            created["id"],
            definition="Доход от продаж",
            examples=["выручка по регионам"],
        )
        self.assertEqual(updated["definition"], "Доход от продаж")
        self.assertEqual(updated["examples"], ["выручка по регионам"])

        self.service.delete_term(created["id"])
        self.assertEqual(self.service.list_terms(), [])

    def test_term_unique_constraint(self):
        self.service.create_term(term="Конверсия")
        with self.assertRaises(ValueError):
            self.service.create_term(term="конверсия")

    def test_mappings_crud(self):
        term = self.service.create_term(term="ARPU", definition="Revenue per user")
        mapping = self.service.add_mapping(
            term_id=term["id"],
            database_name="postgres_examples",
            dataset_name="sales_dataset",
            schema_name="public",
            table_name="sales",
            column_name="revenue",
            metric_name="sum_revenue",
            notes="Основной показатель",
        )
        self.assertEqual(mapping["term_id"], term["id"])
        self.assertEqual(mapping["column_name"], "revenue")

        with self.assertRaises(ValueError):
            self.service.add_mapping(term_id=term["id"])

        mappings = self.service.list_mappings(term_id=term["id"])
        self.assertEqual(len(mappings), 1)

        self.service.delete_mapping(mapping["id"])
        self.assertEqual(self.service.list_mappings(term_id=term["id"]), [])

    def test_agent_context_contains_term_and_mapping(self):
        term = self.service.create_term(
            term="LTV",
            definition="Lifetime value",
            examples=["ltv по сегментам"],
        )
        self.service.add_mapping(
            term_id=term["id"],
            database_name="postgres_examples",
            schema_name="public",
            table_name="customers",
            metric_name="ltv_metric",
        )
        context = self.service.build_agent_context()
        self.assertIn("LTV", context)
        self.assertIn("customers", context)
        self.assertIn("ltv_metric", context)


if __name__ == "__main__":
    unittest.main()

