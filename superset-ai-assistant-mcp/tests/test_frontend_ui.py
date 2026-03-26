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
        self.chat_sessions_by_user = {}
        self.history_by_user = {}
        self._time_index = 0
        self._session_index = 0

    def _timestamp(self) -> str:
        self._time_index += 1
        minute = self._time_index % 60
        hour = self._time_index // 60
        return f"2026-01-01T{hour:02d}:{minute:02d}:00+00:00"

    def _ensure_user_structures(self, username):
        self.chat_sessions_by_user.setdefault(username, {})
        self.history_by_user.setdefault(username, {})

    def _session_sort_key(self, session):
        return (
            str(session.get("last_message_at", "")),
            str(session.get("updated_at", "")),
            str(session.get("created_at", "")),
            str(session.get("session_id", "")),
        )

    def _ensure_session(self, username, session_id, title="Новый чат", created_at=None):
        self._ensure_user_structures(username)
        clean_session_id = str(session_id).strip()
        created = str(created_at or self._timestamp()).strip()
        if clean_session_id not in self.chat_sessions_by_user[username]:
            self.chat_sessions_by_user[username][clean_session_id] = {
                "username": username,
                "session_id": clean_session_id,
                "title": str(title or "Новый чат").strip() or "Новый чат",
                "created_at": created,
                "updated_at": created,
                "last_message_at": created,
                "is_archived": False,
            }
        self.history_by_user[username].setdefault(clean_session_id, [])
        return self.chat_sessions_by_user[username][clean_session_id]

    def _new_session_id(self, username):
        self._session_index += 1
        return f"session-{username}-{self._session_index}"

    def _sync_session_activity(self, username, session_id):
        self._ensure_session(username, session_id)
        session = self.chat_sessions_by_user[username][session_id]
        history = self.history_by_user[username].get(session_id, [])
        updated_at = self._timestamp()
        session["updated_at"] = updated_at
        if history:
            session["last_message_at"] = str(history[-1]["created_at"])
            if session["title"] == "Новый чат":
                for item in history:
                    if item["role"] == "user" and item["content"].strip():
                        session["title"] = item["content"].strip()
                        break
        else:
            session["last_message_at"] = str(session["created_at"])

    def _set_active_session(self, username, session_id):
        self._ensure_session(username, session_id)
        self.sessions[username] = session_id

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

    def list_chat_sessions(self, username, include_archived=False):
        self._ensure_user_structures(username)
        sessions = list(self.chat_sessions_by_user.get(username, {}).values())
        if not include_archived:
            sessions = [item for item in sessions if not item.get("is_archived", False)]
        sessions.sort(key=self._session_sort_key, reverse=True)
        return [dict(item) for item in sessions]

    def create_chat_session(self, username, title=None):
        session_id = self._new_session_id(username)
        session = self._ensure_session(username, session_id, title=title or "Новый чат")
        self._set_active_session(username, session_id)
        return dict(session)

    def get_chat_session(self, username, session_id):
        self._ensure_user_structures(username)
        session = self.chat_sessions_by_user.get(username, {}).get(session_id)
        if session is None:
            return None
        return dict(session)

    def rename_chat_session(self, username, session_id, title):
        clean_title = str(title or "").strip()
        if not clean_title:
            raise ValueError("title is required")
        session = self._ensure_session(username, session_id)
        session["title"] = clean_title
        session["updated_at"] = self._timestamp()
        return dict(session)

    def set_active_chat_session(self, username, session_id):
        session = self.get_chat_session(username, session_id)
        if session is None:
            raise ValueError("Chat session не найдена.")
        self._set_active_session(username, session_id)
        return self.get_chat_session(username, session_id)

    def list_chat_history(self, username, session_id=None, limit=None):
        self._ensure_user_structures(username)
        safe_limit = None if limit is None else max(1, int(limit))
        if session_id:
            history = list(self.history_by_user.get(username, {}).get(session_id, []))
        else:
            history = []
            for items in self.history_by_user.get(username, {}).values():
                history.extend(items)
            history.sort(key=lambda item: str(item.get("created_at", "")))
        if safe_limit is not None:
            history = history[-safe_limit:]
        return [dict(item) for item in history]

    def get_or_create_user_session(self, username):
        self._ensure_user_structures(username)
        session_id = str(self.sessions.get(username, "")).strip()
        if session_id:
            self._ensure_session(username, session_id)
            return session_id
        sessions = self.list_chat_sessions(username)
        if sessions:
            session_id = str(sessions[0]["session_id"]).strip()
            self._set_active_session(username, session_id)
            return session_id
        session_id = f"session-{username}"
        self._ensure_session(username, session_id)
        self._set_active_session(username, session_id)
        return session_id

    def save_chat_message(self, username, session_id, role, content):
        self._ensure_session(username, session_id)
        created_at = self._timestamp()
        payload = {
            "username": username,
            "session_id": session_id,
            "role": role,
            "content": content,
            "created_at": created_at,
        }
        self.saved_messages.append(payload)
        self.history_by_user.setdefault(username, {}).setdefault(session_id, []).append(dict(payload))
        self._sync_session_activity(username, session_id)

    def clear_chat_history(self, username, session_id=None):
        self.clear_history_calls.append((username, session_id))
        self._ensure_user_structures(username)
        if session_id:
            removed = len(self.history_by_user.get(username, {}).get(session_id, []))
            self.history_by_user.setdefault(username, {})[session_id] = []
            self._sync_session_activity(username, session_id)
            return removed
        removed = sum(len(items) for items in self.history_by_user.get(username, {}).values())
        for item_session_id in list(self.history_by_user.get(username, {}).keys()):
            self.history_by_user[username][item_session_id] = []
            self._sync_session_activity(username, item_session_id)
        return removed

    def rotate_user_session(self, username):
        self.rotate_calls.append(username)
        return str(self.create_chat_session(username)["session_id"])


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

    def _click_button_by_key(self, at: AppTest, key: str) -> None:
        for button in at.button:
            if getattr(button, "key", None) == key:
                button.click()
                return
        available = [(getattr(button, "key", None), button.label) for button in at.button]
        self.fail(f"Button with key '{key}' not found. Available buttons: {available}")

    def _seed_chat(self, title: str, messages: list[tuple[str, str]]) -> str:
        session = self.auth_service.create_chat_session("alice", title=title)
        session_id = str(session["session_id"])
        for role, content in messages:
            self.auth_service.save_chat_message(
                username="alice",
                session_id=session_id,
                role=role,
                content=content,
            )
        return session_id

    def _text_values(self, items) -> list[str]:
        return [str(getattr(item, "value", "")).strip() for item in items]

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
        sessions = self.auth_service.list_chat_sessions("alice")
        self.assertEqual(sessions[0]["title"], "Покажи доступные датасеты")

    def test_authenticated_user_sees_chat_onboarding_and_quick_start_help(self):
        at = self._new_app(authenticated=True)
        at.run()

        info_values = self._text_values(at.info)
        markdown_values = self._text_values(at.markdown)

        self.assertTrue(any("Как начать:" in value for value in info_values))
        self.assertTrue(any("Рекомендуемый путь" in value for value in markdown_values))
        self.assertTrue(any("1. Спросите бизнес-вопрос" in value for value in markdown_values))

    def test_chat_examples_are_business_first_not_sql_first(self):
        at = self._new_app(authenticated=True)
        at.run()

        labels = [button.label for button in at.button]
        self.assertIn("Покажи выручку по месяцам", labels)
        self.assertIn("Какие категории товаров приносят больше всего продаж?", labels)
        self.assertIn("Сделай график по заказам за 2025 год", labels)
        self.assertFalse(any("SELECT" in label for label in labels))

    def test_authenticated_user_sees_chat_list_in_sidebar(self):
        first_session_id = self.auth_service.get_or_create_user_session("alice")
        self.auth_service.rename_chat_session("alice", first_session_id, "Основной чат")
        self._seed_chat(
            "Второй чат",
            [
                ("user", "Покажи прибыль"),
                ("assistant", "Готово"),
            ],
        )

        at = self._new_app(authenticated=True)
        at.run()

        labels = [button.label for button in at.button]
        self.assertIn("Основной чат", labels)
        self.assertIn("Второй чат", labels)
        self.assertIn("+ Новый чат", labels)
        self.assertEqual(len(at.session_state["chat_sessions"]), 2)

    def test_creating_new_chat_creates_separate_empty_chat(self):
        initial_session_id = self.auth_service.get_or_create_user_session("alice")
        self.auth_service.save_chat_message(
            username="alice",
            session_id=initial_session_id,
            role="user",
            content="Первый чат",
        )
        at = self._new_app(authenticated=True)
        at.run()

        self._click_button(at, "+ Новый чат")
        at.run()

        new_session_id = str(at.session_state["session_id"])
        self.assertNotEqual(new_session_id, initial_session_id)
        self.assertEqual(list(at.session_state["messages"]), [])
        self.assertEqual(len(at.session_state["chat_sessions"]), 2)
        old_history = self.auth_service.list_chat_history(username="alice", session_id=initial_session_id)
        new_history = self.auth_service.list_chat_history(username="alice", session_id=new_session_id)
        self.assertEqual(len(old_history), 1)
        self.assertEqual(new_history, [])

    def test_switching_between_chats_shows_isolated_histories(self):
        first_session_id = self.auth_service.get_or_create_user_session("alice")
        self.auth_service.rename_chat_session("alice", first_session_id, "Основной чат")
        self.auth_service.save_chat_message(
            username="alice",
            session_id=first_session_id,
            role="user",
            content="История первого чата",
        )
        second_session_id = self._seed_chat(
            "Отчёт по продажам",
            [
                ("user", "История второго чата"),
                ("assistant", "Ответ второго чата"),
            ],
        )
        self.auth_service.set_active_chat_session(username="alice", session_id=first_session_id)

        at = self._new_app(authenticated=True)
        at.run()

        self.assertEqual(str(at.session_state["session_id"]), first_session_id)
        self.assertEqual(at.session_state["messages"][0]["content"], "История первого чата")

        self._click_button(at, "Отчёт по продажам")
        at.run()

        self.assertEqual(str(at.session_state["session_id"]), second_session_id)
        self.assertEqual([item["content"] for item in at.session_state["messages"]], ["История второго чата", "Ответ второго чата"])

    def test_active_chat_restores_from_backend_pointer_on_new_app_run(self):
        first_session_id = self.auth_service.get_or_create_user_session("alice")
        self.auth_service.rename_chat_session("alice", first_session_id, "Основной чат")
        second_session_id = self._seed_chat(
            "Второй сценарий",
            [("user", "Переключённый чат")],
        )
        self.auth_service.set_active_chat_session(username="alice", session_id=first_session_id)

        at = self._new_app(authenticated=True)
        at.run()
        self._click_button(at, "Второй сценарий")
        at.run()

        self.assertEqual(str(at.session_state["session_id"]), second_session_id)
        self.assertEqual(self.auth_service.sessions["alice"], second_session_id)

        restored = self._new_app(authenticated=True)
        restored.run()
        self.assertEqual(str(restored.session_state["session_id"]), second_session_id)
        self.assertEqual(restored.session_state["messages"][0]["content"], "Переключённый чат")

    def test_clearing_chat_affects_only_current_chat(self):
        first_session_id = self.auth_service.get_or_create_user_session("alice")
        self.auth_service.rename_chat_session("alice", first_session_id, "Основной чат")
        self.auth_service.save_chat_message(
            username="alice",
            session_id=first_session_id,
            role="user",
            content="История первого чата",
        )
        second_session_id = self._seed_chat(
            "Второй чат",
            [
                ("user", "История второго чата"),
                ("assistant", "Ответ второго чата"),
            ],
        )

        at = self._new_app(authenticated=True)
        at.run()
        self._click_button(at, "Второй чат")
        at.run()

        self._click_button(at, "🗑 Очистить чат")
        at.run()

        self.assertEqual(str(at.session_state["session_id"]), second_session_id)
        self.assertEqual(list(at.session_state["messages"]), [])
        self.assertEqual(
            [item["content"] for item in self.auth_service.list_chat_history(username="alice", session_id=first_session_id)],
            ["История первого чата"],
        )
        self.assertEqual(
            self.auth_service.list_chat_history(username="alice", session_id=second_session_id),
            [],
        )
        self.assertIn(("alice", second_session_id), self.auth_service.clear_history_calls)

    def test_rename_flow_updates_backend_and_ui(self):
        session_id = self.auth_service.get_or_create_user_session("alice")
        self.auth_service.rename_chat_session("alice", session_id, "Старое имя")

        at = self._new_app(authenticated=True)
        at.run()

        self._click_button_by_key(at, f"chat_session_rename_{session_id}")
        at.run()
        at.text_input(key="chat_rename_value").set_value("Новое имя чата")
        self._click_button_by_key(at, f"chat_session_rename_save_{session_id}")
        at.run()

        labels = [button.label for button in at.button]
        self.assertIn("Новое имя чата", labels)
        self.assertEqual(
            self.auth_service.get_chat_session("alice", session_id)["title"],
            "Новое имя чата",
        )

    def test_us13_shows_guidance_that_table_inspection_is_optional(self):
        at = self._new_app(authenticated=True, active_window="us13")
        at.run()

        info_values = self._text_values(at.info)
        caption_values = self._text_values(at.caption)
        labels = [button.label for button in at.button]

        self.assertTrue(any("можно начать прямо с чата" in value for value in info_values))
        self.assertTrue(any("Не хотите писать запрос сами?" in value for value in caption_values))
        self.assertIn("Заполнить пример запроса", labels)

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
        initial_session_id = self.auth_service.get_or_create_user_session("alice")
        self.auth_service.save_chat_message(
            username="alice",
            session_id=initial_session_id,
            role="user",
            content="старый вопрос",
        )
        self.auth_service.save_chat_message(
            username="alice",
            session_id=initial_session_id,
            role="assistant",
            content="старый ответ",
        )
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

        self._click_button(at, "+ Новый чат")
        at.run()
        self.assertNotEqual(str(at.session_state["session_id"]), initial_session_id)
        self.assertEqual(list(at.session_state["messages"]), [])
        self.assertIsNone(at.session_state["pending_input"])
        self.assertEqual(at.session_state["us13_preview_result"], {"rows_count": 2})
        self.assertEqual(len(at.session_state["chat_sessions"]), 2)

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
