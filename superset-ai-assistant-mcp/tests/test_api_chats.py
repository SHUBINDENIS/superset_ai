"""
Tests for the FastAPI chat-session and message endpoints.

Chat CRUD tests hit the real AuthService (same pattern as test_api_auth.py).
The message-send test mocks the agent via FastAPI dependency overrides so
that langchain / MCP / OpenAI deps are never loaded.
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient


def _fresh_app():
    """Reset API singletons and return a fresh (app, deps_mod) tuple."""
    import api.deps as deps_mod

    deps_mod._auth_service_instance = None
    deps_mod._AuthService = None
    deps_mod._agent_session_manager = None

    from api.main import app

    # Clear any leftover dependency overrides
    app.dependency_overrides.clear()
    return app, deps_mod


class TestChatSessionCRUD(unittest.TestCase):
    """Tests for chat CRUD, activation, and message list/clear."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = str(Path(self.temp_dir.name) / "chat_test.db")
        self.env_patch = patch.dict(
            os.environ,
            {
                "AUTH_DB_PATH": db_path,
                "AUTH_JWT_SECRET": "test-chat-secret",
                "AUTH_JWT_TTL_HOURS": "1",
                "AUTH_PASSWORD_MIN_LENGTH": "8",
            },
            clear=False,
        )
        self.env_patch.start()

        self.app, self.deps_mod = _fresh_app()
        self.client = TestClient(self.app)

        # Register + login to get an auth cookie
        self.client.post(
            "/api/auth/register",
            json={"username": "chatuser", "password": "strongpass"},
        )
        login_resp = self.client.post(
            "/api/auth/login",
            json={"username": "chatuser", "password": "strongpass"},
        )
        self.token = login_resp.cookies.get("ai_assistant_auth_token")

        mock_manager = MagicMock()
        mock_manager.close_session = AsyncMock(return_value=None)
        from api.deps import get_agent_session_manager

        self.app.dependency_overrides[get_agent_session_manager] = lambda: mock_manager
        self.mock_agent_manager = mock_manager

    def tearDown(self):
        self.app.dependency_overrides.clear()
        self.deps_mod._auth_service_instance = None
        self.deps_mod._AuthService = None
        self.deps_mod._agent_session_manager = None
        self.env_patch.stop()
        self.temp_dir.cleanup()

    def _auth_cookies(self):
        return {"ai_assistant_auth_token": self.token}

    # ------------------------------------------------------------------
    # GET /api/chats
    # ------------------------------------------------------------------
    def test_list_chats_empty(self):
        resp = self.client.get("/api/chats", cookies=self._auth_cookies())
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        # A default session may exist from registration; just check shape
        self.assertIn("sessions", data)
        self.assertIsInstance(data["sessions"], list)

    def test_list_chats_unauthenticated_returns_401(self):
        anon = TestClient(self.app)
        resp = anon.get("/api/chats")
        self.assertEqual(resp.status_code, 401)

    # ------------------------------------------------------------------
    # POST /api/chats
    # ------------------------------------------------------------------
    def test_create_chat_session(self):
        resp = self.client.post(
            "/api/chats",
            json={"title": "My first chat"},
            cookies=self._auth_cookies(),
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["title"], "My first chat")
        self.assertTrue(data["session_id"])
        self.assertIn("created_at", data)
        self.assertEqual(
            data["settings"],
            {"response_style": "business", "detail_level": "standard"},
        )

    def test_create_chat_session_default_title(self):
        resp = self.client.post(
            "/api/chats",
            json={},
            cookies=self._auth_cookies(),
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertTrue(data["session_id"])

    def test_create_chat_unauthenticated_returns_401(self):
        anon = TestClient(self.app)
        resp = anon.post("/api/chats", json={"title": "test"})
        self.assertEqual(resp.status_code, 401)

    # ------------------------------------------------------------------
    # PATCH /api/chats/{session_id}
    # ------------------------------------------------------------------
    def test_rename_chat_session(self):
        create_resp = self.client.post(
            "/api/chats",
            json={"title": "Old name"},
            cookies=self._auth_cookies(),
        )
        session_id = create_resp.json()["session_id"]

        resp = self.client.patch(
            f"/api/chats/{session_id}",
            json={"title": "New name"},
            cookies=self._auth_cookies(),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["title"], "New name")

    def test_rename_nonexistent_session_returns_404(self):
        resp = self.client.patch(
            "/api/chats/00000000",
            json={"title": "Nope"},
            cookies=self._auth_cookies(),
        )
        self.assertEqual(resp.status_code, 404)

    def test_update_chat_settings(self):
        create_resp = self.client.post(
            "/api/chats",
            json={"title": "Settings chat"},
            cookies=self._auth_cookies(),
        )
        session_id = create_resp.json()["session_id"]

        resp = self.client.patch(
            f"/api/chats/{session_id}/settings",
            json={"response_style": "technical", "detail_level": "detailed"},
            cookies=self._auth_cookies(),
        )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.json()["settings"],
            {"response_style": "technical", "detail_level": "detailed"},
        )

        list_resp = self.client.get("/api/chats", cookies=self._auth_cookies())
        target = next(
            item for item in list_resp.json()["sessions"]
            if item["session_id"] == session_id
        )
        self.assertEqual(
            target["settings"],
            {"response_style": "technical", "detail_level": "detailed"},
        )

    def test_rename_empty_title_returns_422(self):
        create_resp = self.client.post(
            "/api/chats",
            json={"title": "X"},
            cookies=self._auth_cookies(),
        )
        session_id = create_resp.json()["session_id"]

        resp = self.client.patch(
            f"/api/chats/{session_id}",
            json={"title": ""},
            cookies=self._auth_cookies(),
        )
        self.assertEqual(resp.status_code, 422)

    # ------------------------------------------------------------------
    # POST /api/chats/{session_id}/activate
    # ------------------------------------------------------------------
    def test_activate_chat_session_updates_active_pointer(self):
        first = self.client.post(
            "/api/chats",
            json={"title": "First"},
            cookies=self._auth_cookies(),
        ).json()["session_id"]
        second = self.client.post(
            "/api/chats",
            json={"title": "Second"},
            cookies=self._auth_cookies(),
        ).json()["session_id"]

        activate_resp = self.client.post(
            f"/api/chats/{first}/activate",
            cookies=self._auth_cookies(),
        )
        self.assertEqual(activate_resp.status_code, 200)
        self.assertEqual(activate_resp.json()["session_id"], first)

        me_resp = self.client.get("/api/auth/me", cookies=self._auth_cookies())
        self.assertEqual(me_resp.status_code, 200)
        self.assertEqual(me_resp.json()["session_id"], first)
        self.assertNotEqual(me_resp.json()["session_id"], second)

    def test_activate_nonexistent_session_returns_404(self):
        resp = self.client.post(
            "/api/chats/00000000/activate",
            cookies=self._auth_cookies(),
        )
        self.assertEqual(resp.status_code, 404)

    # ------------------------------------------------------------------
    # GET /api/chats/{session_id}/messages
    # ------------------------------------------------------------------
    def test_list_messages_empty_session(self):
        create_resp = self.client.post(
            "/api/chats",
            json={"title": "Empty"},
            cookies=self._auth_cookies(),
        )
        session_id = create_resp.json()["session_id"]

        resp = self.client.get(
            f"/api/chats/{session_id}/messages",
            cookies=self._auth_cookies(),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["messages"], [])

    def test_list_messages_nonexistent_session_returns_404(self):
        resp = self.client.get(
            "/api/chats/00000000/messages",
            cookies=self._auth_cookies(),
        )
        self.assertEqual(resp.status_code, 404)

    # ------------------------------------------------------------------
    # DELETE /api/chats/{session_id}/messages
    # ------------------------------------------------------------------
    def test_clear_messages(self):
        create_resp = self.client.post(
            "/api/chats",
            json={"title": "To clear"},
            cookies=self._auth_cookies(),
        )
        session_id = create_resp.json()["session_id"]

        resp = self.client.delete(
            f"/api/chats/{session_id}/messages",
            cookies=self._auth_cookies(),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["deleted_count"], 0)

    def test_clear_messages_nonexistent_session_returns_404(self):
        resp = self.client.delete(
            "/api/chats/00000000/messages",
            cookies=self._auth_cookies(),
        )
        self.assertEqual(resp.status_code, 404)

    def test_delete_chat_archives_session_and_removes_from_list(self):
        first = self.client.post(
            "/api/chats",
            json={"title": "First"},
            cookies=self._auth_cookies(),
        ).json()["session_id"]
        second = self.client.post(
            "/api/chats",
            json={"title": "Second"},
            cookies=self._auth_cookies(),
        ).json()["session_id"]

        resp = self.client.delete(
            f"/api/chats/{first}",
            cookies=self._auth_cookies(),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["deleted_session_id"], first)
        self.assertFalse(resp.json()["was_active"])
        self.assertEqual(resp.json()["next_active_session_id"], second)
        self.mock_agent_manager.close_session.assert_awaited_with(first)

        list_resp = self.client.get("/api/chats", cookies=self._auth_cookies())
        ids = [s["session_id"] for s in list_resp.json()["sessions"]]
        self.assertNotIn(first, ids)
        self.assertIn(second, ids)

        for method, path, payload in (
            ("get", f"/api/chats/{first}/messages", None),
            ("delete", f"/api/chats/{first}/messages", None),
            ("post", f"/api/chats/{first}/activate", None),
            ("patch", f"/api/chats/{first}", {"title": "Renamed"}),
            ("post", f"/api/chats/{first}/messages", {"content": "hi"}),
        ):
            kwargs = {"cookies": self._auth_cookies()}
            if payload is not None:
                kwargs["json"] = payload
            response = getattr(self.client, method)(path, **kwargs)
            self.assertEqual(response.status_code, 404)

    def test_delete_last_chat_clears_active_session_pointer(self):
        created = self.client.post(
            "/api/chats",
            json={"title": "Only"},
            cookies=self._auth_cookies(),
        ).json()["session_id"]

        sessions = self.client.get("/api/chats", cookies=self._auth_cookies()).json()["sessions"]
        for session in sessions:
            if session["session_id"] != created:
                self.client.delete(
                    f"/api/chats/{session['session_id']}",
                    cookies=self._auth_cookies(),
                )

        resp = self.client.delete(
            f"/api/chats/{created}",
            cookies=self._auth_cookies(),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["deleted_session_id"], created)
        self.assertTrue(resp.json()["was_active"])
        self.assertIsNone(resp.json()["next_active_session_id"])

        me_resp = self.client.get("/api/auth/me", cookies=self._auth_cookies())
        self.assertEqual(me_resp.status_code, 200)
        self.assertEqual(me_resp.json()["session_id"], "")

    def test_delete_active_chat_reassigns_active_pointer(self):
        first = self.client.post(
            "/api/chats",
            json={"title": "First"},
            cookies=self._auth_cookies(),
        ).json()["session_id"]
        second = self.client.post(
            "/api/chats",
            json={"title": "Second"},
            cookies=self._auth_cookies(),
        ).json()["session_id"]
        self.client.post(f"/api/chats/{first}/activate", cookies=self._auth_cookies())

        resp = self.client.delete(
            f"/api/chats/{first}",
            cookies=self._auth_cookies(),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["was_active"])
        self.assertEqual(resp.json()["next_active_session_id"], second)

        me_resp = self.client.get("/api/auth/me", cookies=self._auth_cookies())
        self.assertEqual(me_resp.status_code, 200)
        self.assertEqual(me_resp.json()["session_id"], second)

    def test_delete_chat_unauthenticated_returns_401(self):
        anon = TestClient(self.app)
        resp = anon.delete("/api/chats/00000000")
        self.assertEqual(resp.status_code, 401)

    def test_delete_other_users_chat_returns_404(self):
        other_client = TestClient(self.app)
        other_client.post(
            "/api/auth/register",
            json={"username": "otheruser", "password": "strongpass"},
        )
        other_login = other_client.post(
            "/api/auth/login",
            json={"username": "otheruser", "password": "strongpass"},
        )
        other_cookies = {
            "ai_assistant_auth_token": other_login.cookies.get("ai_assistant_auth_token"),
        }

        foreign_session = self.client.post(
            "/api/chats",
            json={"title": "Foreign"},
            cookies=self._auth_cookies(),
        ).json()["session_id"]

        resp = other_client.delete(f"/api/chats/{foreign_session}", cookies=other_cookies)
        self.assertEqual(resp.status_code, 404)

    def test_delete_chat_still_succeeds_when_in_memory_cleanup_fails(self):
        session_id = self.client.post(
            "/api/chats",
            json={"title": "Cleanup failure"},
            cookies=self._auth_cookies(),
        ).json()["session_id"]
        self.mock_agent_manager.close_session = AsyncMock(side_effect=RuntimeError("close failed"))

        resp = self.client.delete(
            f"/api/chats/{session_id}",
            cookies=self._auth_cookies(),
        )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["deleted_session_id"], session_id)

    # ------------------------------------------------------------------
    # Full CRUD flow
    # ------------------------------------------------------------------
    def test_chat_session_full_flow(self):
        cookies = self._auth_cookies()

        # Create
        create_resp = self.client.post(
            "/api/chats", json={"title": "Flow test"}, cookies=cookies,
        )
        self.assertEqual(create_resp.status_code, 201)
        session_id = create_resp.json()["session_id"]

        # List — new session should appear
        list_resp = self.client.get("/api/chats", cookies=cookies)
        ids = [s["session_id"] for s in list_resp.json()["sessions"]]
        self.assertIn(session_id, ids)

        # Rename
        rename_resp = self.client.patch(
            f"/api/chats/{session_id}",
            json={"title": "Renamed"},
            cookies=cookies,
        )
        self.assertEqual(rename_resp.json()["title"], "Renamed")

        # Messages — initially empty
        msg_resp = self.client.get(
            f"/api/chats/{session_id}/messages", cookies=cookies,
        )
        self.assertEqual(msg_resp.json()["messages"], [])

        # Clear (no-op on empty) — just verify 200
        clr_resp = self.client.delete(
            f"/api/chats/{session_id}/messages", cookies=cookies,
        )
        self.assertEqual(clr_resp.status_code, 200)


class TestSendMessage(unittest.TestCase):
    """Tests for POST /api/chats/{session_id}/messages.

    The agent is mocked via FastAPI dependency overrides so that
    langchain / MCP / OpenAI are never imported.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = str(Path(self.temp_dir.name) / "msg_test.db")
        self.env_patch = patch.dict(
            os.environ,
            {
                "AUTH_DB_PATH": db_path,
                "AUTH_JWT_SECRET": "test-msg-secret",
                "AUTH_JWT_TTL_HOURS": "1",
                "AUTH_PASSWORD_MIN_LENGTH": "8",
            },
            clear=False,
        )
        self.env_patch.start()

        self.app, self.deps_mod = _fresh_app()
        self.client = TestClient(self.app)

        # Register + login
        self.client.post(
            "/api/auth/register",
            json={"username": "msguser", "password": "strongpass"},
        )
        login_resp = self.client.post(
            "/api/auth/login",
            json={"username": "msguser", "password": "strongpass"},
        )
        self.token = login_resp.cookies.get("ai_assistant_auth_token")

        # Create a chat session to send messages to
        create_resp = self.client.post(
            "/api/chats",
            json={"title": "Agent test"},
            cookies=self._auth_cookies(),
        )
        self.session_id = create_resp.json()["session_id"]

        # Install a default mock agent so that backend.ai_agent is never
        # imported (avoids langchain / MCP / OpenAI deps in tests).
        self._install_mock_agent({
            "content": "default mock reply",
            "role": "assistant",
            "finish_reason": "stop",
            "model": "mock",
            "session_id": self.session_id,
        })

    def tearDown(self):
        self.app.dependency_overrides.clear()
        self.deps_mod._auth_service_instance = None
        self.deps_mod._AuthService = None
        self.deps_mod._agent_session_manager = None
        self.env_patch.stop()
        self.temp_dir.cleanup()

    def _auth_cookies(self):
        return {"ai_assistant_auth_token": self.token}

    def _install_mock_agent(self, chat_return):
        """Override get_agent_session_manager with a mock that returns
        an agent whose chat() resolves to *chat_return*."""
        mock_agent = AsyncMock()
        mock_agent.chat = AsyncMock(return_value=chat_return)

        mock_manager = MagicMock()
        mock_manager.get_or_create_agent = AsyncMock(return_value=mock_agent)

        from api.deps import get_agent_session_manager
        self.app.dependency_overrides[get_agent_session_manager] = lambda: mock_manager
        return mock_agent

    # ------------------------------------------------------------------
    # Successful message send
    # ------------------------------------------------------------------
    def test_send_message_success(self):
        mock_agent = self._install_mock_agent({
            "content": "Hello! I can help with that.",
            "role": "assistant",
            "finish_reason": "stop",
            "model": "test-model",
            "session_id": self.session_id,
            "response_style": "business",
            "detail_level": "standard",
            "artifacts": [],
        })

        resp = self.client.post(
            f"/api/chats/{self.session_id}/messages",
            json={"content": "What tables are available?"},
            cookies=self._auth_cookies(),
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["content"], "Hello! I can help with that.")
        self.assertEqual(data["finish_reason"], "stop")
        self.assertEqual(data["role"], "assistant")
        self.assertEqual(data["model"], "test-model")
        self.assertEqual(data["session_id"], self.session_id)
        self.assertEqual(data["response_style"], "business")
        self.assertEqual(data["detail_level"], "standard")
        self.assertEqual(data["artifacts"], [])
        mock_agent.chat.assert_awaited_once_with(
            [{"role": "user", "content": "What tables are available?"}],
            response_style="business",
            detail_level="standard",
        )

    def test_send_message_passes_technical_response_style(self):
        mock_agent = self._install_mock_agent({
            "content": "Technical answer",
            "role": "assistant",
            "finish_reason": "stop",
            "model": "test-model",
            "session_id": self.session_id,
            "response_style": "technical",
            "detail_level": "detailed",
            "artifacts": [],
        })

        resp = self.client.post(
            f"/api/chats/{self.session_id}/messages",
            json={
                "content": "Опиши поля датасета",
                "response_style": "technical",
                "detail_level": "detailed",
            },
            cookies=self._auth_cookies(),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["response_style"], "technical")
        self.assertEqual(resp.json()["detail_level"], "detailed")
        mock_agent.chat.assert_awaited_once_with(
            [{"role": "user", "content": "Опиши поля датасета"}],
            response_style="technical",
            detail_level="detailed",
        )

    def test_send_message_uses_persisted_chat_settings_when_body_omits_them(self):
        self.client.patch(
            f"/api/chats/{self.session_id}/settings",
            json={"response_style": "technical", "detail_level": "detailed"},
            cookies=self._auth_cookies(),
        )
        mock_agent = self._install_mock_agent({
            "content": "Technical answer",
            "role": "assistant",
            "finish_reason": "stop",
            "model": "test-model",
            "session_id": self.session_id,
            "response_style": "technical",
            "detail_level": "detailed",
            "artifacts": [],
        })

        resp = self.client.post(
            f"/api/chats/{self.session_id}/messages",
            json={"content": "Опиши источник данных"},
            cookies=self._auth_cookies(),
        )

        self.assertEqual(resp.status_code, 200)
        mock_agent.chat.assert_awaited_once_with(
            [{"role": "user", "content": "Опиши источник данных"}],
            response_style="technical",
            detail_level="detailed",
        )

    def test_send_message_persists_both_messages(self):
        """User message AND assistant reply should be in the DB afterward."""
        self._install_mock_agent({
            "content": "Here are the tables.",
            "role": "assistant",
            "finish_reason": "stop",
            "model": "m",
            "session_id": self.session_id,
            "response_style": "technical",
            "detail_level": "detailed",
            "artifacts": [
                {
                    "artifact_type": "table_preview",
                    "title": "Preview",
                    "description": "Rows",
                    "payload": {
                        "href": "http://host/sqllab?dbid=7",
                        "link_label": "Открыть SQL Lab",
                        "columns": [{"key": "store", "label": "store"}],
                        "rows": [{"store": "Store 1"}],
                    },
                }
            ],
        })

        self.client.post(
            f"/api/chats/{self.session_id}/messages",
            json={"content": "Show tables"},
            cookies=self._auth_cookies(),
        )

        # Verify messages persisted
        msg_resp = self.client.get(
            f"/api/chats/{self.session_id}/messages",
            cookies=self._auth_cookies(),
        )
        messages = msg_resp.json()["messages"]
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["role"], "user")
        self.assertEqual(messages[0]["content"], "Show tables")
        self.assertEqual(messages[1]["role"], "assistant")
        self.assertEqual(messages[1]["content"], "Here are the tables.")
        self.assertEqual(messages[1]["response_style"], "technical")
        self.assertEqual(messages[1]["detail_level"], "detailed")
        self.assertEqual(messages[1]["artifacts"][0]["artifact_type"], "table_preview")

    # ------------------------------------------------------------------
    # Blocked response (guardrails)
    # ------------------------------------------------------------------
    def test_send_message_blocked_response(self):
        self._install_mock_agent({
            "content": "I cannot help with that request.",
            "role": "assistant",
            "finish_reason": "blocked",
            "model": "test-model",
            "session_id": self.session_id,
        })

        resp = self.client.post(
            f"/api/chats/{self.session_id}/messages",
            json={"content": "Do something off-topic"},
            cookies=self._auth_cookies(),
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["finish_reason"], "blocked")

    # ------------------------------------------------------------------
    # Error response from agent
    # ------------------------------------------------------------------
    def test_send_message_error_response(self):
        self._install_mock_agent({
            "content": "An error occurred while processing.",
            "role": "assistant",
            "finish_reason": "error",
            "model": "test-model",
            "session_id": self.session_id,
        })

        resp = self.client.post(
            f"/api/chats/{self.session_id}/messages",
            json={"content": "Trigger error"},
            cookies=self._auth_cookies(),
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["finish_reason"], "error")

    # ------------------------------------------------------------------
    # Rate limit cooldown
    # ------------------------------------------------------------------
    def test_send_message_rate_limit_cooldown(self):
        self._install_mock_agent({
            "content": "Rate limit active, please wait.",
            "role": "assistant",
            "finish_reason": "rate_limit_cooldown",
            "model": "test-model",
            "session_id": self.session_id,
        })

        resp = self.client.post(
            f"/api/chats/{self.session_id}/messages",
            json={"content": "Another question"},
            cookies=self._auth_cookies(),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["finish_reason"], "rate_limit_cooldown")

    # ------------------------------------------------------------------
    # Agent exception → 503
    # ------------------------------------------------------------------
    def test_send_message_agent_exception_returns_503(self):
        mock_agent = AsyncMock()
        mock_agent.chat = AsyncMock(side_effect=RuntimeError("MCP init failed"))

        mock_manager = MagicMock()
        mock_manager.get_or_create_agent = AsyncMock(return_value=mock_agent)

        from api.deps import get_agent_session_manager
        self.app.dependency_overrides[get_agent_session_manager] = lambda: mock_manager

        resp = self.client.post(
            f"/api/chats/{self.session_id}/messages",
            json={"content": "Crash"},
            cookies=self._auth_cookies(),
        )
        self.assertEqual(resp.status_code, 503)
        self.assertIn("Agent processing failed", resp.json()["detail"])

    # ------------------------------------------------------------------
    # Edge cases
    # ------------------------------------------------------------------
    def test_send_message_nonexistent_session_returns_404(self):
        self._install_mock_agent({
            "content": "nope",
            "role": "assistant",
            "finish_reason": "stop",
            "model": "m",
            "session_id": "00000000",
        })

        resp = self.client.post(
            "/api/chats/00000000/messages",
            json={"content": "Hello"},
            cookies=self._auth_cookies(),
        )
        self.assertEqual(resp.status_code, 404)

    def test_send_message_empty_content_returns_422(self):
        resp = self.client.post(
            f"/api/chats/{self.session_id}/messages",
            json={"content": ""},
            cookies=self._auth_cookies(),
        )
        self.assertEqual(resp.status_code, 422)

    def test_send_message_unauthenticated_returns_401(self):
        anon = TestClient(self.app)
        resp = anon.post(
            f"/api/chats/{self.session_id}/messages",
            json={"content": "Hello"},
        )
        self.assertEqual(resp.status_code, 401)

    # ------------------------------------------------------------------
    # Regression: artifacts survive reload (list_messages returns them)
    # ------------------------------------------------------------------
    def test_artifacts_persist_through_reload(self):
        """Artifacts stored via send_message must be returned by list_messages."""
        artifacts = [
            {
                    "artifact_type": "table_preview",
                    "title": "Revenue by store",
                    "description": "Top 10 stores",
                    "payload": {
                        "href": "http://host/sqllab?dbid=7",
                        "link_label": "Открыть SQL Lab",
                        "columns": [
                            {"key": "store", "label": "Store"},
                            {"key": "revenue", "label": "Revenue"},
                        ],
                        "rows": [
                        {"store": "Store A", "revenue": 1500},
                        {"store": "Store B", "revenue": 1200},
                    ],
                },
            },
            {
                    "artifact_type": "chart_preview",
                    "title": "Revenue chart",
                    "description": "Bar chart",
                    "payload": {
                        "chart_type": "bar",
                        "href": "http://host/explore/?slice_id=22",
                        "link_label": "Открыть график",
                        "rows": [
                            {"store": "Store A", "revenue": 1500},
                            {"store": "Store B", "revenue": 1200},
                        ],
                        "x_key": "store",
                    "y_key": "revenue",
                },
            },
        ]
        self._install_mock_agent({
            "content": "Here is the data.",
            "role": "assistant",
            "finish_reason": "stop",
            "model": "m",
            "session_id": self.session_id,
            "response_style": "business",
            "detail_level": "standard",
            "artifacts": artifacts,
        })

        self.client.post(
            f"/api/chats/{self.session_id}/messages",
            json={"content": "Покажи выручку по магазинам"},
            cookies=self._auth_cookies(),
        )

        # Simulate reload: fresh list_messages call
        msg_resp = self.client.get(
            f"/api/chats/{self.session_id}/messages",
            cookies=self._auth_cookies(),
        )
        messages = msg_resp.json()["messages"]
        assistant_msg = messages[-1]
        self.assertEqual(assistant_msg["role"], "assistant")
        self.assertEqual(len(assistant_msg["artifacts"]), 2)
        self.assertEqual(assistant_msg["artifacts"][0]["artifact_type"], "table_preview")
        self.assertEqual(assistant_msg["artifacts"][0]["title"], "Revenue by store")
        self.assertEqual(
            assistant_msg["artifacts"][0]["payload"]["link_label"],
            "Открыть SQL Lab",
        )
        self.assertEqual(
            len(assistant_msg["artifacts"][0]["payload"]["rows"]), 2,
        )
        self.assertEqual(assistant_msg["artifacts"][1]["artifact_type"], "chart_preview")
        self.assertEqual(assistant_msg["artifacts"][1]["payload"]["chart_type"], "bar")
        self.assertEqual(
            assistant_msg["artifacts"][1]["payload"]["link_label"],
            "Открыть график",
        )

    # ------------------------------------------------------------------
    # Regression: detail_level concise passes through API correctly
    # ------------------------------------------------------------------
    def test_send_message_passes_concise_detail_level(self):
        mock_agent = self._install_mock_agent({
            "content": "Short answer.",
            "role": "assistant",
            "finish_reason": "stop",
            "model": "test-model",
            "session_id": self.session_id,
            "response_style": "business",
            "detail_level": "concise",
            "artifacts": [],
        })

        resp = self.client.post(
            f"/api/chats/{self.session_id}/messages",
            json={
                "content": "Краткая сводка",
                "response_style": "business",
                "detail_level": "concise",
            },
            cookies=self._auth_cookies(),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["detail_level"], "concise")
        mock_agent.chat.assert_awaited_once_with(
            [{"role": "user", "content": "Краткая сводка"}],
            response_style="business",
            detail_level="concise",
        )

    # ------------------------------------------------------------------
    # Regression: per-message metadata preserved after multiple sends
    # ------------------------------------------------------------------
    def test_multiple_messages_preserve_per_message_settings(self):
        """Each message should keep its own response_style/detail_level."""
        # First message: business/standard
        self._install_mock_agent({
            "content": "Business answer.",
            "role": "assistant",
            "finish_reason": "stop",
            "model": "m",
            "session_id": self.session_id,
            "response_style": "business",
            "detail_level": "standard",
            "artifacts": [],
        })
        self.client.post(
            f"/api/chats/{self.session_id}/messages",
            json={
                "content": "Business question",
                "response_style": "business",
                "detail_level": "standard",
            },
            cookies=self._auth_cookies(),
        )

        # Second message: technical/detailed
        self._install_mock_agent({
            "content": "Technical answer.",
            "role": "assistant",
            "finish_reason": "stop",
            "model": "m",
            "session_id": self.session_id,
            "response_style": "technical",
            "detail_level": "detailed",
            "artifacts": [],
        })
        self.client.post(
            f"/api/chats/{self.session_id}/messages",
            json={
                "content": "Technical question",
                "response_style": "technical",
                "detail_level": "detailed",
            },
            cookies=self._auth_cookies(),
        )

        # Reload messages
        msg_resp = self.client.get(
            f"/api/chats/{self.session_id}/messages",
            cookies=self._auth_cookies(),
        )
        messages = msg_resp.json()["messages"]
        # 4 messages: user1, assistant1, user2, assistant2
        self.assertEqual(len(messages), 4)
        self.assertEqual(messages[1]["response_style"], "business")
        self.assertEqual(messages[1]["detail_level"], "standard")
        self.assertEqual(messages[3]["response_style"], "technical")
        self.assertEqual(messages[3]["detail_level"], "detailed")

    # ------------------------------------------------------------------
    # Regression: partial settings update preserves other field
    # ------------------------------------------------------------------
    def test_settings_partial_update_preserves_other_field(self):
        """Updating only response_style must not reset detail_level."""
        # Set both fields
        self.client.patch(
            f"/api/chats/{self.session_id}/settings",
            json={"response_style": "technical", "detail_level": "detailed"},
            cookies=self._auth_cookies(),
        )

        # Update only response_style
        resp = self.client.patch(
            f"/api/chats/{self.session_id}/settings",
            json={"response_style": "business"},
            cookies=self._auth_cookies(),
        )
        self.assertEqual(resp.status_code, 200)
        settings = resp.json()["settings"]
        self.assertEqual(settings["response_style"], "business")
        self.assertEqual(settings["detail_level"], "detailed")

    # ------------------------------------------------------------------
    # Regression: first send in new chat with non-default settings
    # ------------------------------------------------------------------
    def test_first_message_in_new_chat_with_custom_settings(self):
        """Settings sent in the body of the first message must be used."""
        # Create a new chat
        create_resp = self.client.post(
            "/api/chats",
            json={"title": "Technical chat"},
            cookies=self._auth_cookies(),
        )
        new_session_id = create_resp.json()["session_id"]
        self.assertEqual(
            create_resp.json()["settings"],
            {"response_style": "business", "detail_level": "standard"},
        )

        mock_agent = self._install_mock_agent({
            "content": "Technical first reply.",
            "role": "assistant",
            "finish_reason": "stop",
            "model": "m",
            "session_id": new_session_id,
            "response_style": "technical",
            "detail_level": "concise",
            "artifacts": [],
        })

        resp = self.client.post(
            f"/api/chats/{new_session_id}/messages",
            json={
                "content": "First message",
                "response_style": "technical",
                "detail_level": "concise",
            },
            cookies=self._auth_cookies(),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["response_style"], "technical")
        self.assertEqual(resp.json()["detail_level"], "concise")
        # Agent must receive the body-specified settings, not the chat defaults
        mock_agent.chat.assert_awaited_once_with(
            [{"role": "user", "content": "First message"}],
            response_style="technical",
            detail_level="concise",
        )


if __name__ == "__main__":
    unittest.main()
