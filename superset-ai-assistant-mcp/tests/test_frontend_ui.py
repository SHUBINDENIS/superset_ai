import os
import unittest
from pathlib import Path
from unittest.mock import patch

import backend
from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).resolve().parents[1] / "frontend" / "app.py"
REMOVED_WS_STATE_KEYS = {
    "chat_transport",
    "chat_ws_base_url",
    "chat_last_trace",
    "chat_last_trace_error",
    "chat_last_latency_ms",
    "chat_last_finish_reason",
}
REMOVED_WS_TOKENS = (
    "AI_ASSISTANT_WS_BASE_URL",
    "CHAT_TRANSPORT_WS",
    "CHAT_TRANSPORT_HTTP",
    "handle_message_ws",
    "backend.ws_api",
)


class FakeAgent:
    def __init__(self, reply: str = "assistant-reply") -> None:
        self.reply = reply
        self.initialize_calls = 0
        self.chat_calls = []

    async def initialize(self) -> bool:
        self.initialize_calls += 1
        return True

    async def chat(self, messages):
        self.chat_calls.append([dict(item) for item in messages])
        return {"content": self.reply}


class FakeSessionManager:
    def __init__(self, agent: FakeAgent) -> None:
        self.agent = agent
        self.created_agents = {}
        self.get_agent_calls = []
        self.get_or_create_calls = []
        self.sessions = {}

    async def get_agent(self, session_id, owner=None):
        self.get_agent_calls.append((session_id, owner))
        return self.created_agents.get(session_id)

    async def get_or_create_agent(self, session_id, owner=None):
        self.get_or_create_calls.append((session_id, owner))
        agent = self.created_agents.get(session_id)
        if not agent:
            agent = self.agent
            self.created_agents[session_id] = agent
            self.sessions[session_id] = {"owner": owner}
        return agent


class FakeAuthService:
    def __init__(self) -> None:
        self.saved_messages = []
        self.authenticate_calls = []
        self.clear_history_calls = []
        self.rotate_calls = []
        self.sessions = {}
        self.history_by_user = {}

    def validate_token(self, token):
        raise ValueError("invalid token")

    def authenticate_user(self, username, password):
        self.authenticate_calls.append((username, password))
        session_id = self.get_or_create_user_session(username)
        return {
            "username": username,
            "role": "analyst",
            "auth_token": f"token-{username}",
            "session_id": session_id,
        }

    def list_chat_history(self, username, limit=None):
        return list(self.history_by_user.get(username, []))

    def get_or_create_user_session(self, username):
        return self.sessions.setdefault(username, f"session-{username}")

    def save_chat_message(self, username, session_id, role, content):
        payload = {
            "username": username,
            "session_id": session_id,
            "role": role,
            "content": content,
        }
        self.saved_messages.append(payload)
        self.history_by_user.setdefault(username, []).append({"role": role, "content": content})

    def clear_chat_history(self, username):
        self.clear_history_calls.append(username)
        removed = len(self.history_by_user.get(username, []))
        self.history_by_user[username] = []
        return removed

    def rotate_user_session(self, username):
        self.rotate_calls.append(username)
        rotated = f"rotated-{len(self.rotate_calls)}"
        self.sessions[username] = rotated
        return rotated


class FakeVizService:
    def __init__(self) -> None:
        self.calls = []
        self.databases = [
            {"id": 1, "name": "examples", "backend": "sqlite"},
            {"id": 2, "name": "warehouse", "backend": "postgresql"},
        ]
        self.datasets = [
            {
                "id": 11,
                "table_name": "birth_names",
                "schema": "public",
                "database_id": 1,
                "database_name": "examples",
            },
            {
                "id": 12,
                "table_name": "sales",
                "schema": "analytics",
                "database_id": 2,
                "database_name": "warehouse",
            },
        ]
        self.preview = {
            "database_id": 1,
            "schema": "public",
            "rows_count": 2,
            "preview_limit": 20,
            "sql_executed": "SELECT ds, sales, region FROM birth_names LIMIT 20",
            "rows": [
                {"ds": "2026-01-01", "sales": 10, "region": "RU"},
                {"ds": "2026-01-02", "sales": 12, "region": "KZ"},
            ],
            "columns": [
                {
                    "column": "ds",
                    "inferred_type": "temporal",
                    "unit": "",
                    "distinct_count": 2,
                    "sample_value": "2026-01-01",
                    "explanation": "Дата продажи.",
                },
                {
                    "column": "sales",
                    "inferred_type": "numeric",
                    "unit": "currency",
                    "distinct_count": 2,
                    "sample_value": "10",
                    "explanation": "Сумма продаж.",
                },
                {
                    "column": "region",
                    "inferred_type": "text",
                    "unit": "",
                    "distinct_count": 2,
                    "sample_value": "RU",
                    "explanation": "Регион продажи.",
                },
            ],
        }
        self.recommendation = {
            "recommended": "line",
            "selected_columns": {
                "metric": "sales",
                "dimension": "region",
                "time": "ds",
            },
            "candidates": [
                {"viz_type": "line", "score": 0.98, "reason": "Есть время и метрика"},
                {"viz_type": "bar", "score": 0.71, "reason": "Есть категория и метрика"},
            ],
        }
        self.dataset_metadata = {
            "columns": [
                {"column_name": "ds", "type": "TIMESTAMP"},
                {"column_name": "sales", "type": "DOUBLE"},
                {"column_name": "region", "type": "VARCHAR"},
            ]
        }
        self.widget_result = {
            "dashboard_id": 301,
            "chart_id": 501,
            "viz_type": "line",
            "dashboard_link": "http://localhost:8088/superset/dashboard/301/",
            "chart_link": "http://localhost:8088/explore/?slice_id=501",
            "params": {"viz_type": "line", "metrics": ["sales"]},
        }

    def list_databases(self):
        self.calls.append(("list_databases", {}))
        return list(self.databases)

    def list_datasets(self, limit=300):
        self.calls.append(("list_datasets", {"limit": limit}))
        return list(self.datasets)

    def preview_sql(self, **kwargs):
        self.calls.append(("preview_sql", dict(kwargs)))
        return dict(self.preview)

    def recommend_viz_types(self, **kwargs):
        self.calls.append(("recommend_viz_types", dict(kwargs)))
        return dict(self.recommendation)

    def get_dataset_metadata(self, dataset_id):
        self.calls.append(("get_dataset_metadata", {"dataset_id": dataset_id}))
        return dict(self.dataset_metadata)

    def create_dashboard_widget_with_share(self, **kwargs):
        self.calls.append(("create_dashboard_widget_with_share", dict(kwargs)))
        return dict(self.widget_result)


def make_us1_result():
    return {
        "summary": {
            "database_candidates_count": 1,
            "postgres_candidates_count": 1,
            "selected_databases_count": 1,
            "postgres_databases_count": 1,
            "tables_profiled_count": 2,
            "relations_detected_count": 1,
        },
        "report": {
            "postgres_databases": [
                {
                    "database_id": 2,
                    "database_name": "warehouse",
                    "backend": "postgresql",
                    "schemas": ["analytics"],
                    "tables_profiled": [
                        {"table_name": "sales"},
                        {"table_name": "orders"},
                    ],
                    "relations": {
                        "foreign_keys": [
                            {
                                "source_schema": "analytics",
                                "source_table": "sales",
                                "source_column": "order_id",
                                "target_schema": "analytics",
                                "target_table": "orders",
                                "target_column": "id",
                            }
                        ],
                        "heuristic": [],
                    },
                    "diagnostics": {"tables_fetch_errors": []},
                }
            ],
            "database_candidates": [
                {"id": 2, "database_name": "warehouse", "backend_hint": "postgresql"}
            ],
        },
    }


class TestFrontendUISmoke(unittest.TestCase):
    def setUp(self):
        self.auth_service = FakeAuthService()
        self.agent = FakeAgent()
        self.session_manager = FakeSessionManager(agent=self.agent)
        self.viz_service = FakeVizService()
        self.us1_result = make_us1_result()

        async def fake_us1_scan():
            return self.us1_result

        self._patchers = [
            patch.dict(
                os.environ,
                {
                    "MCP_USE_ANONYMIZED_TELEMETRY": "false",
                    "AUTH_PASSWORD_MIN_LENGTH": "8",
                },
                clear=False,
            ),
            patch.object(backend, "get_auth_service", new=lambda: self.auth_service),
            patch.object(backend, "get_session_manager", new=lambda: self.session_manager),
            patch.object(backend, "get_us13_15_viz_service", new=lambda: self.viz_service),
            patch.object(backend, "run_us1_scan_from_env", new=fake_us1_scan),
        ]
        for patcher in self._patchers:
            patcher.start()
        self.addCleanup(self._stop_patchers)

    def _stop_patchers(self):
        while self._patchers:
            self._patchers.pop().stop()

    def _new_app(self, *, authenticated: bool = False, active_window: str | None = None, extra_state=None):
        at = AppTest.from_file(str(APP_PATH), default_timeout=10)
        if authenticated:
            at.session_state["auth_is_authenticated"] = True
            at.session_state["auth_username"] = "alice"
            at.session_state["auth_role"] = "analyst"
            at.session_state["auth_token"] = "token-alice"
            at.session_state["session_id"] = self.auth_service.get_or_create_user_session("alice")
        if active_window:
            at.session_state["active_window"] = active_window
        if extra_state:
            for key, value in extra_state.items():
                at.session_state[key] = value
        return at

    def _click_button(self, at: AppTest, label: str) -> None:
        for button in at.button:
            if button.label == label:
                button.click()
                return
        available = [button.label for button in at.button]
        self.fail(f"Button '{label}' not found. Available buttons: {available}")

    def _login(self, at: AppTest, username: str = "alice", password: str = "secret-pass") -> None:
        at.text_input(key="auth_login_username").set_value(username)
        at.text_input(key="auth_login_password").set_value(password)
        self._click_button(at, "Войти")
        at.run()

    def test_auth_screen_smoke_and_login_transition(self):
        at = self._new_app()
        at.run()

        self.assertTrue(any(button.label == "Войти" for button in at.button))
        self.assertTrue(any(tab.label == "Вход" for tab in at.tabs))
        self.assertIn("auth_login_username", {widget.key for widget in at.text_input})

        self._login(at)

        self.assertTrue(at.session_state["auth_is_authenticated"])
        self.assertEqual(at.session_state["auth_username"], "alice")
        self.assertEqual(at.session_state["active_window"], "chat")
        self.assertEqual(self.auth_service.authenticate_calls, [("alice", "secret-pass")])

    def test_chat_screen_submits_message_via_backend_agent_and_persists_history(self):
        at = self._new_app()
        at.run()
        self._login(at)

        self.assertEqual(len(at.chat_input), 1)
        self.assertFalse(any("WebSocket" in button.label for button in at.button))

        at.chat_input[0].set_value("Покажи доступные датасеты")
        at.run()

        messages = list(at.session_state["messages"])
        self.assertEqual(messages[-2]["role"], "user")
        self.assertEqual(messages[-2]["content"], "Покажи доступные датасеты")
        self.assertEqual(messages[-1]["role"], "assistant")
        self.assertEqual(messages[-1]["content"], "assistant-reply")
        self.assertEqual(
            [item["role"] for item in self.auth_service.saved_messages[-2:]],
            ["user", "assistant"],
        )
        self.assertTrue(self.session_manager.get_or_create_calls)
        self.assertEqual(self.session_manager.get_or_create_calls[0], ("session-alice", "alice"))
        self.assertEqual(self.agent.initialize_calls, 1)
        self.assertEqual(
            self.agent.chat_calls[-1][-1],
            {"role": "user", "content": "Покажи доступные датасеты"},
        )

    def test_navigation_smoke_respects_active_window(self):
        at = self._new_app(authenticated=True, active_window="us1")
        at.run()

        self.assertEqual(at.title[0].value, "Сканер схем и связей")
        self.assertEqual(at.session_state["active_window"], "us1")

        self._click_button(at, "🔎 Предпросмотр")
        at.run()
        self.assertEqual(at.title[0].value, "Предпросмотр результата и объяснение полей")
        self.assertEqual(at.session_state["active_window"], "us13")

        self._click_button(at, "🎯 Рекомендации")
        at.run()
        self.assertEqual(at.title[0].value, "Авто-рекомендация типа графика")
        self.assertEqual(at.session_state["active_window"], "us14")

        self._click_button(at, "💬 Чат")
        at.run()
        self.assertEqual(at.session_state["active_window"], "chat")
        self.assertEqual(len(at.chat_input), 1)

    def test_us1_scan_smoke_renders_result_sections(self):
        at = self._new_app(authenticated=True, active_window="us1")
        at.run()

        self._click_button(at, "▶ Запустить сканирование")
        at.run()

        self.assertEqual(at.session_state["us1_scan_status"], "success")
        self.assertIsInstance(at.session_state["us1_scan_result"], dict)
        self.assertIn("Отчёт построен", [item.value for item in at.success])
        self.assertGreaterEqual(len(at.dataframe), 2)
        self.assertFalse(any(button.label == "Скачать JSON-отчёт" for button in at.button))

    def test_us13_us14_us15_smoke_flow_renders_preview_recommendation_and_widget_result(self):
        at = self._new_app(authenticated=True, active_window="us13")
        at.run()

        self._click_button(at, "Обновить источники")
        at.run()
        self.assertTrue(any(name == "list_databases" for name, _ in self.viz_service.calls))
        self.assertTrue(any(name == "list_datasets" for name, _ in self.viz_service.calls))

        self._click_button(at, "Запустить предпросмотр")
        at.run()
        self.assertEqual(at.session_state["us13_preview_result"]["rows_count"], 2)
        self.assertIn("Preview готов: 2 строк.", [item.value for item in at.success])
        self.assertGreaterEqual(len(at.dataframe), 1)

        self._click_button(at, "🎯 Рекомендации")
        at.run()
        self._click_button(at, "Подобрать тип графика")
        at.run()
        self.assertEqual(at.session_state["us14_recommendation"]["recommended"], "line")
        self.assertIn("Рекомендуемый тип: line.", [item.value for item in at.success])

        self._click_button(at, "Перейти к созданию виджета")
        at.run()
        self._click_button(at, "Создать виджет")
        at.run()
        self.assertEqual(at.session_state["us15_result"]["chart_id"], 501)
        self.assertIn("Виджет создан и привязан к дашборду.", [item.value for item in at.success])
        self.assertTrue(
            any(name == "create_dashboard_widget_with_share" for name, _ in self.viz_service.calls)
        )

    def test_reset_and_logout_clear_expected_state(self):
        self.auth_service.history_by_user["alice"] = [
            {"role": "user", "content": "старый вопрос"},
            {"role": "assistant", "content": "старый ответ"},
        ]
        at = self._new_app(
            authenticated=True,
            extra_state={
                "messages": [
                    {"role": "user", "content": "draft"},
                    {"role": "assistant", "content": "reply"},
                ],
                "pending_input": "queued",
                "us13_preview_result": {"rows_count": 2},
            },
        )
        at.run()

        self._click_button(at, "🔄 Новая сессия")
        at.run()
        self.assertEqual(at.session_state["session_id"], "rotated-1")
        self.assertEqual(list(at.session_state["messages"]), [])
        self.assertIsNone(at.session_state["pending_input"])
        self.assertIsNone(at.session_state["us13_preview_result"])

        self._click_button(at, "🚪 Выход")
        at.run()
        self.assertFalse(at.session_state["auth_is_authenticated"])
        self.assertEqual(at.session_state["messages"], [])
        self.assertTrue(any(button.label == "Войти" for button in at.button))

    def test_ui_regression_has_no_removed_websocket_controls_or_state(self):
        source = APP_PATH.read_text(encoding="utf-8")
        for token in REMOVED_WS_TOKENS:
            self.assertNotIn(token, source)

        at = self._new_app(authenticated=True)
        at.run()

        self.assertTrue(
            REMOVED_WS_STATE_KEYS.isdisjoint(set(at.session_state.filtered_state.keys()))
        )
        labels = [button.label.casefold() for button in at.button]
        self.assertFalse(any("websocket" in label for label in labels))
        self.assertFalse(any("transport" in label for label in labels))

    def test_ui_chat_path_does_not_depend_on_deleted_legacy_runtime_artifacts(self):
        with patch.dict(
            os.environ,
            {
                "SUPERSET_MCP_PATH": "/definitely-missing/legacy-runtime.py",
                "SUPERSET_MCP_PYTHON": "/definitely-missing/python",
            },
            clear=False,
        ):
            at = self._new_app(authenticated=True)
            at.run()
            at.chat_input[0].set_value("Покажи список дашбордов")
            at.run()

        self.assertTrue(self.session_manager.get_agent_calls)
        self.assertTrue(self.session_manager.get_or_create_calls)
        self.assertEqual(self.agent.chat_calls[-1][-1]["content"], "Покажи список дашбордов")
        self.assertEqual(at.session_state["messages"][-1]["content"], "assistant-reply")


if __name__ == "__main__":
    unittest.main()
