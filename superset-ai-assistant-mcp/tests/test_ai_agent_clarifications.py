import unittest
from unittest.mock import patch

from backend.ai_agent import SupersetAIAgent
from backend.mcp_client.tool_registry import (
    SUPPORTED_LEGACY_TOOLS,
    build_agent_runtime_guidance,
)


class TestAIAgentClarifications(unittest.TestCase):
    def setUp(self):
        self.agent = SupersetAIAgent.__new__(SupersetAIAgent)
        self.agent.rate_limit_cooldown_seconds = 20
        self.agent._rate_limited_until_monotonic = None

    def test_guardrail_offtopic_reply_requests_required_fields(self):
        reply = self.agent._build_guardrail_block_reply(
            reason_code="offtopic_blocked",
            reason_text="Запрос не относится к аналитике.",
            user_message="привет",
        )
        self.assertIn("Какая метрика", reply)
        self.assertIn("По какой таблице", reply)

    def test_error_clarification_for_missing_column(self):
        reply = self.agent._build_error_clarification_reply(
            user_message="Покажи выручку из таблицы birth_names",
            error_text=(
                'duckdb error: Binder Error: Referenced column "revenue" '
                "not found in FROM clause"
            ),
        )
        self.assertIn("проблемная колонка", reply)
        self.assertIn("показать структуру таблицы", reply)

    def test_error_clarification_for_timeout(self):
        reply = self.agent._build_error_clarification_reply(
            user_message="Покажи продажи",
            error_text="Authentication timeout",
        )
        self.assertIn("авторизации", reply)

    def test_parse_scope_from_text_ru(self):
        scope = self.agent._parse_scope_from_text(
            "Найди аномалии. Используй scope: база: examples; таблица: main.unicode_test."
        )
        self.assertEqual(scope.get("database"), "examples")
        self.assertEqual(scope.get("schema"), "main")
        self.assertEqual(scope.get("table_name"), "unicode_test")

    def test_detect_scope_tables_failure(self):
        text = (
            "Не смог получить доступ к таблицам в базе данных examples: "
            "GET /api/v1/database/2/tables/ -> 400"
        )
        self.assertTrue(self.agent._looks_like_scope_tables_failure(text))

    def test_runtime_guidance_does_not_require_legacy_auth_or_database_tables(self):
        guidance = build_agent_runtime_guidance("http://superset.local")
        self.assertNotIn("superset_auth_authenticate_user", guidance)
        self.assertIn("Аутентификация уже должна быть обеспечена", guidance)
        self.assertIn("dataset-level", guidance)
        self.assertIn("database/tables endpoint", guidance)
        self.assertNotIn("superset_database_get_tables", guidance)

    def test_supported_legacy_tools_exclude_auth_and_database_tables(self):
        self.assertNotIn("superset_auth_authenticate_user", SUPPORTED_LEGACY_TOOLS)
        self.assertNotIn("superset_database_get_tables", SUPPORTED_LEGACY_TOOLS)

    def test_resolve_mcp_python_prefers_explicit_executable_path(self):
        with (
            patch.dict("os.environ", {"SUPERSET_MCP_PYTHON": "/opt/python/bin/python3"}, clear=False),
            patch.object(
                SupersetAIAgent,
                "_is_executable_file",
                side_effect=lambda path: str(path) == "/opt/python/bin/python3",
            ),
        ):
            resolved = self.agent._resolve_mcp_python_command()
        self.assertEqual(resolved, "/opt/python/bin/python3")

    def test_resolve_mcp_python_falls_back_to_sys_executable(self):
        with (
            patch.dict("os.environ", {"SUPERSET_MCP_PYTHON": "python"}, clear=False),
            patch("backend.ai_agent.shutil.which", return_value=None),
            patch("backend.ai_agent.sys.executable", "/usr/bin/python3"),
            patch.object(
                SupersetAIAgent,
                "_is_executable_file",
                side_effect=lambda path: str(path) == "/usr/bin/python3",
            ),
        ):
            resolved = self.agent._resolve_mcp_python_command()
        self.assertEqual(resolved, "/usr/bin/python3")

    def test_resolve_mcp_python_raises_when_no_candidates(self):
        with (
            patch.dict("os.environ", {"SUPERSET_MCP_PYTHON": "python"}, clear=False),
            patch("backend.ai_agent.shutil.which", return_value=None),
            patch("backend.ai_agent.sys.executable", ""),
            patch.object(SupersetAIAgent, "_is_executable_file", return_value=False),
        ):
            with self.assertRaises(FileNotFoundError):
                self.agent._resolve_mcp_python_command()

    def test_resolve_mcp_server_path_fallbacks_to_repo_default(self):
        with (
            patch.dict("os.environ", {"SUPERSET_MCP_PATH": "/missing/main.py"}, clear=False),
            patch(
                "backend.ai_agent.os.path.isfile",
                side_effect=lambda path: str(path).endswith("/superset-mcp/main.py"),
            ),
        ):
            resolved = self.agent._resolve_mcp_server_path()
        self.assertTrue(resolved.endswith("/superset-mcp/main.py"))

    def test_resolve_mcp_server_path_raises_when_missing(self):
        with (
            patch.dict("os.environ", {"SUPERSET_MCP_PATH": "/missing/main.py"}, clear=False),
            patch("backend.ai_agent.os.path.isfile", return_value=False),
        ):
            with self.assertRaises(FileNotFoundError):
                self.agent._resolve_mcp_server_path()


if __name__ == "__main__":
    unittest.main()
