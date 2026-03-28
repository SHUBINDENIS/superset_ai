"""
Tests for the FastAPI frontend structured-log ingest endpoint.

The endpoint is intentionally thin: it should write a privacy-safe JSONL event
into frontend.log and preserve trace/request ids from the browser.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


def _fresh_app():
    import api.deps as deps_mod

    deps_mod._auth_service_instance = None
    deps_mod._AuthService = None
    deps_mod._agent_session_manager = None
    deps_mod._us13_15_viz_service_instance = None
    deps_mod._us1_scan_runner_instance = None
    deps_mod._observability_module = None

    from api.main import app

    app.dependency_overrides.clear()
    return app, deps_mod


class TestFrontendLogIngestAPI(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.log_dir = tempfile.TemporaryDirectory()
        db_path = str(Path(self.temp_dir.name) / "frontend_log_test.db")
        self.env_patch = patch.dict(
            os.environ,
            {
                "AUTH_DB_PATH": db_path,
                "AUTH_JWT_SECRET": "test-frontend-log-secret",
                "AUTH_JWT_TTL_HOURS": "1",
                "AUTH_PASSWORD_MIN_LENGTH": "8",
                "ASSISTANT_LOG_DIR": self.log_dir.name,
            },
            clear=False,
        )
        self.env_patch.start()

        self.app, self.deps_mod = _fresh_app()
        self.client = TestClient(self.app)

        self.client.post(
            "/api/auth/register",
            json={"username": "loguser", "password": "strongpass"},
        )
        login_resp = self.client.post(
            "/api/auth/login",
            json={"username": "loguser", "password": "strongpass"},
        )
        self.token = login_resp.cookies.get("ai_assistant_auth_token")

    def tearDown(self):
        self.app.dependency_overrides.clear()
        self.deps_mod._auth_service_instance = None
        self.deps_mod._AuthService = None
        self.deps_mod._agent_session_manager = None
        self.deps_mod._us13_15_viz_service_instance = None
        self.deps_mod._us1_scan_runner_instance = None
        self.deps_mod._observability_module = None
        self.env_patch.stop()
        self.temp_dir.cleanup()
        self.log_dir.cleanup()

    def _auth_cookies(self):
        return {"ai_assistant_auth_token": self.token}

    def _read_frontend_log(self) -> list[dict]:
        path = Path(self.log_dir.name) / "frontend.log"
        if not path.exists():
            return []
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def test_frontend_log_ingest_writes_sanitized_event(self):
        resp = self.client.post(
            "/api/frontend/logs",
            json={
                "event": "chat_submit",
                "trace_id": "trace-123",
                "request_id": "request-123",
                "session_id": "session-abc",
                "chat_id": "session-abc",
                "route": "/app/chat",
                "metadata": {
                    "message_chars": 48,
                    "error_message": (
                        "Bearer abcdef token=secret-value "
                        "password=my-pass sk-test-secret"
                    ),
                },
            },
            cookies=self._auth_cookies(),
            headers={
                "x-trace-id": "trace-123",
                "x-request-id": "request-123",
                "x-session-id": "session-abc",
                "x-chat-id": "session-abc",
                "x-frontend-source": "nextjs",
            },
        )
        self.assertEqual(resp.status_code, 200)

        events = self._read_frontend_log()
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event["event"], "chat_submit")
        self.assertEqual(event["trace_id"], "trace-123")
        self.assertEqual(event["request_id"], "request-123")
        self.assertEqual(event["session_id"], "session-abc")
        self.assertEqual(event["chat_id"], "session-abc")
        self.assertEqual(event["source"], "nextjs")
        self.assertEqual(event["route"], "/app/chat")
        self.assertEqual(event["metadata"]["message_chars"], 48)
        payload = json.dumps(event, ensure_ascii=False)
        self.assertNotIn("loguser", payload)
        self.assertNotIn("secret-value", payload)
        self.assertNotIn("my-pass", payload)
        self.assertNotIn("sk-test-secret", payload)
        self.assertIn("user_hash", payload)

    def test_frontend_log_ingest_allows_anon_event(self):
        anon = TestClient(self.app)
        resp = anon.post(
            "/api/frontend/logs",
            json={
                "event": "auth_login_success",
                "trace_id": "trace-login",
                "request_id": "request-login",
                "route": "/login",
                "metadata": {"role": "analyst"},
            },
        )
        self.assertEqual(resp.status_code, 200)
        events = self._read_frontend_log()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event"], "auth_login_success")
        self.assertNotIn("user_hash", events[0])


if __name__ == "__main__":
    unittest.main()
