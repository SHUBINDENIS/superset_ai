import tempfile
import unittest
from pathlib import Path

from backend.us3_mapping_rules import MappingRulesService


class TestMappingRulesService(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(self.temp_dir.name) / "us3_rules.db"
        self.service = MappingRulesService(db_path=str(db_path))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_create_and_list_rule(self):
        rule = self.service.create_rule(
            rule_name="revenue keyword",
            pattern="выручка",
            pattern_type="keyword",
            target_type="column",
            table_name="sales",
            column_name="revenue",
            priority=500,
        )
        self.assertEqual(rule["rule_name"], "revenue keyword")
        rules = self.service.list_rules()
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0]["priority"], 500)

    def test_invalid_regex_rejected(self):
        with self.assertRaises(ValueError):
            self.service.create_rule(
                rule_name="bad regex",
                pattern="([a-z",
                pattern_type="regex",
                target_type="column",
                column_name="x",
            )

    def test_match_and_logs(self):
        self.service.create_rule(
            rule_name="users metric",
            pattern=r"активн(ых|ые) пользовател",
            pattern_type="regex",
            target_type="metric",
            metric_name="active_users",
            priority=300,
        )
        matches = self.service.evaluate_query(
            "Покажи активных пользователей по дням",
            session_id="sess-1",
        )
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["metric_name"], "active_users")

        logs = self.service.list_match_logs(session_id="sess-1", limit=10)
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["rule_name"], "users metric")

    def test_disabled_rule_is_skipped(self):
        created = self.service.create_rule(
            rule_name="disabled rule",
            pattern="продажи",
            pattern_type="keyword",
            target_type="column",
            column_name="sales",
            enabled=False,
        )
        self.assertFalse(created["enabled"])
        matches = self.service.evaluate_query("Покажи продажи", session_id="s2")
        self.assertEqual(matches, [])

    def test_context_contains_target(self):
        self.service.create_rule(
            rule_name="gmv",
            pattern="gmv",
            pattern_type="keyword",
            target_type="metric",
            database_name="postgres_examples",
            table_name="orders",
            metric_name="sum_gmv",
            priority=900,
        )
        matches = self.service.evaluate_query("gmv по неделям", session_id="s3")
        context = self.service.build_inference_context(matches)
        self.assertIn("sum_gmv", context)
        self.assertIn("gmv", context)


if __name__ == "__main__":
    unittest.main()

