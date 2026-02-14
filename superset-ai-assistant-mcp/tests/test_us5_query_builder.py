import tempfile
import unittest
from pathlib import Path

from backend.us5_query_builder import US5QueryBuilderService


class TestUS5QueryBuilderService(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(self.temp_dir.name) / "us5_test.db"
        self.service = US5QueryBuilderService(db_path=str(db_path))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_validate_missing_required_fields(self):
        result = self.service.validate_criteria(
            {
                "table_name": "",
                "metric": "",
                "period": "",
                "dimensions": [],
            }
        )
        self.assertFalse(result["is_ready"])
        self.assertIn("table_name", result["blocking_missing"])
        self.assertIn("metric", result["blocking_missing"])
        self.assertIn("period", result["blocking_missing"])
        self.assertTrue(result["clarification_questions"])

    def test_build_query_from_criteria(self):
        query = self.service.build_query(
            {
                "objective": "Найти лучшие регионы",
                "table_name": "birth_names",
                "metric": "выручка",
                "dimensions": ["регион"],
                "period": "за последние 30 дней",
                "time_grain": "week",
                "filters": [{"field": "channel", "value": "online"}],
                "sort_by": "выручка",
                "sort_direction": "desc",
                "top_n": 10,
                "compare_to": "предыдущий месяц",
                "chart_type": "bar",
            }
        )
        self.assertIn("Используй только таблицу/датасет: birth_names", query)
        self.assertIn("Покажи выручка", query)
        self.assertIn("по регион", query)
        self.assertIn("за период: за последние 30 дней", query)
        self.assertIn("фильтры: channel=online", query)
        self.assertIn("top-10", query)

    def test_journal_log_and_read(self):
        written = self.service.log_criteria_selection(
            session_id="sess-us5",
            criteria={
                "table_name": "birth_names",
                "metric": "выручка",
                "period": "за 2025 год",
                "dimensions": ["регион", "категория"],
            },
            source="test",
        )
        self.assertGreaterEqual(written, 2)

        journal = self.service.list_journal("sess-us5", limit=50)
        self.assertTrue(journal)
        keys = {item["criterion_key"] for item in journal}
        self.assertIn("table_name", keys)
        self.assertIn("metric", keys)
        self.assertIn("period", keys)

        latest = self.service.get_latest_criteria("sess-us5")
        self.assertEqual(latest["table_name"], "birth_names")
        self.assertEqual(latest["metric"], "выручка")
        self.assertEqual(latest["period"], "за 2025 год")

    def test_parse_filters_text(self):
        parsed = self.service.parse_filters_text(
            "country=RU\nchannel:online\nbadline"
        )
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0]["field"], "country")
        self.assertEqual(parsed[0]["value"], "RU")

    def test_clear_journal(self):
        self.service.log_criteria_selection(
            session_id="sess-clear",
            criteria={"table_name": "birth_names", "metric": "заказы", "period": "за неделю"},
            source="test",
        )
        before = self.service.list_journal("sess-clear", limit=10)
        self.assertTrue(before)
        removed = self.service.clear_journal("sess-clear")
        self.assertGreaterEqual(removed, 1)
        after = self.service.list_journal("sess-clear", limit=10)
        self.assertEqual(after, [])


if __name__ == "__main__":
    unittest.main()
