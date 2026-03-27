import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from backend.ai_agent import SupersetAIAgent
from backend.observability import bind_log_context, emit_event, hash_user


class _FakeGuardrailsService:
    def __init__(self, decision):
        self._decision = dict(decision)

    def evaluate_user_input(self, *args, **kwargs):
        return dict(self._decision)

    def build_policy_context(self, **kwargs):
        return "US10-US12 guardrails: test context"


class _FakeGlossaryService:
    def build_agent_context(self, **kwargs):
        return ""


class _FakeMappingRulesService:
    def evaluate_query(self, *args, **kwargs):
        return []

    def build_inference_context(self, *args, **kwargs):
        return ""


class _FakeQueryAssistantService:
    def build_agent_context_for_query(self, *args, **kwargs):
        return ""


class _FakeQueryBuilderService:
    def build_agent_context(self, *args, **kwargs):
        return ""

    def get_latest_criteria(self, *args, **kwargs):
        return {}


class TestObservability(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.log_dir = tempfile.TemporaryDirectory()
        self.env_patcher = patch.dict(
            os.environ,
            {"ASSISTANT_LOG_DIR": self.log_dir.name},
            clear=False,
        )
        self.env_patcher.start()
        self.addCleanup(self.env_patcher.stop)
        self.addCleanup(self.log_dir.cleanup)

    def _read_log_events(self, filename: str) -> list[dict]:
        path = Path(self.log_dir.name) / filename
        if not path.exists():
            return []
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def _make_agent(self) -> SupersetAIAgent:
        agent = SupersetAIAgent.__new__(SupersetAIAgent)
        agent.session_id = "session-alice"
        agent.model_name = "gpt-5.4-mini"
        agent.max_history_messages = 3
        agent.max_history_chars = 700
        agent.max_history_item_chars = 220
        agent.max_context_chars = 900
        agent.max_user_message_chars = 900
        agent.rate_limit_cooldown_seconds = 20
        agent._rate_limited_until_monotonic = None
        agent._ensure_initialized = AsyncMock(return_value=None)
        agent._safe_agent_run = AsyncMock(return_value="Готово")
        agent._get_rate_limit_remaining = lambda: 0
        agent._extract_table_hints_from_text = lambda text: []
        agent._parse_scope_from_text = lambda text: {}
        agent._get_superset_public_url = lambda: "http://localhost:8088"
        agent._looks_like_scope_tables_failure = lambda text: False
        return agent

    def test_emit_event_redacts_sensitive_strings(self):
        with bind_log_context(trace_id="trace-1", request_id="request-1"):
            emit_event(
                "frontend",
                "demo_event",
                username="alice",
                error_message=(
                    "Bearer abcdef token=secret-value "
                    "password=my-pass sk-test-secret eyJhbGciOiJIUzI1NiJ9.payload.signature"
                ),
            )

        events = self._read_log_events("frontend.log")
        self.assertEqual(len(events), 1)
        payload = json.dumps(events[0], ensure_ascii=False)
        self.assertIn(hash_user("alice"), payload)
        self.assertNotIn("alice", payload)
        self.assertNotIn("secret-value", payload)
        self.assertNotIn("my-pass", payload)
        self.assertNotIn("sk-test-secret", payload)
        self.assertNotIn("eyJhbGci", payload)

    async def test_agent_logs_turn_start_and_turn_end(self):
        agent = self._make_agent()

        with patch("backend.ai_agent.get_us10_12_guardrails_service", return_value=_FakeGuardrailsService({"allowed": True, "warnings": []})), \
             patch("backend.ai_agent.get_glossary_service", return_value=_FakeGlossaryService()), \
             patch("backend.ai_agent.get_us3_mapping_rules_service", return_value=_FakeMappingRulesService()), \
             patch("backend.ai_agent.get_us4_query_assistant_service", return_value=_FakeQueryAssistantService()), \
             patch("backend.ai_agent.get_us5_query_builder_service", return_value=_FakeQueryBuilderService()):
            with bind_log_context(
                trace_id="trace-ok",
                request_id="request-ok",
                session_id="session-alice",
                chat_id="session-alice",
                user_hash=hash_user("alice"),
            ):
                reply = await agent.chat([{"role": "user", "content": "Покажи выручку"}])

        self.assertEqual(reply["finish_reason"], "stop")
        events = self._read_log_events("agent.log")
        event_names = [item.get("event") for item in events]
        self.assertIn("turn_start", event_names)
        self.assertIn("turn_end", event_names)
        turn_end = next(item for item in events if item.get("event") == "turn_end")
        self.assertEqual(turn_end.get("status"), "ok")
        self.assertEqual(turn_end.get("finish_reason"), "stop")
        self.assertEqual(turn_end.get("trace_id"), "trace-ok")
        self.assertEqual(turn_end.get("request_id"), "request-ok")

    async def test_agent_logs_turn_start_with_response_style_and_rewritten_content(self):
        agent = self._make_agent()
        agent._safe_agent_run = AsyncMock(
            side_effect=[
                (
                    "Dataset sales_by_store содержит поле total_sales и поле store. "
                    "Ответ описывает метрику, группировку и ограничения по данным."
                ),
                "Что найдено\nПоле total_sales используется как метрика.",
            ]
        )

        with patch("backend.ai_agent.get_us10_12_guardrails_service", return_value=_FakeGuardrailsService({"allowed": True, "warnings": []})), \
             patch("backend.ai_agent.get_glossary_service", return_value=_FakeGlossaryService()), \
             patch("backend.ai_agent.get_us3_mapping_rules_service", return_value=_FakeMappingRulesService()), \
             patch("backend.ai_agent.get_us4_query_assistant_service", return_value=_FakeQueryAssistantService()), \
             patch("backend.ai_agent.get_us5_query_builder_service", return_value=_FakeQueryBuilderService()):
            with bind_log_context(
                trace_id="trace-style",
                request_id="request-style",
                session_id="session-alice",
                chat_id="session-alice",
                user_hash=hash_user("alice"),
            ):
                reply = await agent.chat(
                    [{"role": "user", "content": "Покажи выручку"}],
                    response_style="technical",
                    detail_level="detailed",
                )

        self.assertTrue(reply["content"].startswith("Технический разбор:"))
        self.assertEqual(agent._safe_agent_run.await_count, 2)
        events = self._read_log_events("agent.log")
        turn_start = next(item for item in events if item.get("event") == "turn_start")
        self.assertEqual(turn_start.get("response_style"), "technical")
        self.assertEqual(turn_start.get("detail_level"), "detailed")

    async def test_agent_logs_blocked_response(self):
        agent = self._make_agent()

        with patch("backend.ai_agent.get_us10_12_guardrails_service", return_value=_FakeGuardrailsService({
            "allowed": False,
            "code": "sql_blocked",
            "reason": "DDL/DML запрещены.",
        })):
            with bind_log_context(
                trace_id="trace-blocked",
                request_id="request-blocked",
                session_id="session-alice",
                chat_id="session-alice",
                user_hash=hash_user("alice"),
            ):
                reply = await agent.chat([{"role": "user", "content": "DELETE FROM sales"}])

        self.assertEqual(reply["finish_reason"], "blocked")
        events = self._read_log_events("agent.log")
        blocked = next(item for item in events if item.get("event") == "blocked_response")
        self.assertEqual(blocked.get("error_code"), "sql_blocked")
        self.assertEqual(blocked.get("finish_reason"), "blocked")
        self.assertEqual(blocked.get("trace_id"), "trace-blocked")


if __name__ == "__main__":
    unittest.main()
