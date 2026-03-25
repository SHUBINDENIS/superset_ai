import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.ws_api import app


class _DummyAgent:
    async def chat_stream(self, messages, event_callback):
        await event_callback(
            {
                "type": "done",
                "content": "ok",
                "latency_ms": 1,
                "finish_reason": "stop",
            }
        )
        return {"ok": True}


class _DummyManager:
    def __init__(self):
        self.last_owner = None

    async def get_or_create_agent(self, session_id, owner=None):
        self.last_owner = owner
        return _DummyAgent()


class _DummyAuth:
    def validate_token(self, token):
        clean = str(token).strip()
        if clean != "valid-token":
            raise ValueError("Невалидный токен.")
        return {"username": "alice"}


class TestWSApiAuth(unittest.TestCase):
    def test_ws_chat_rejects_missing_token(self):
        dummy_manager = _DummyManager()
        dummy_auth = _DummyAuth()
        with (
            patch("backend.ws_api.get_session_manager", return_value=dummy_manager),
            patch("backend.ws_api.get_auth_service", return_value=dummy_auth),
        ):
            client = TestClient(app)
            with client.websocket_connect("/ws/chat/sess1") as ws:
                _ = ws.receive_json()  # connected
                ws.send_json(
                    {
                        "type": "chat",
                        "message": "hello",
                        "messages": [{"role": "user", "content": "hello"}],
                    }
                )
                event = ws.receive_json()
                self.assertEqual(event.get("type"), "error")
                self.assertEqual(event.get("stage"), "auth")

    def test_ws_chat_accepts_valid_token(self):
        dummy_manager = _DummyManager()
        dummy_auth = _DummyAuth()
        with (
            patch("backend.ws_api.get_session_manager", return_value=dummy_manager),
            patch("backend.ws_api.get_auth_service", return_value=dummy_auth),
        ):
            client = TestClient(app)
            with client.websocket_connect("/ws/chat/sess2") as ws:
                _ = ws.receive_json()  # connected
                ws.send_json(
                    {
                        "type": "chat",
                        "message": "hello",
                        "messages": [{"role": "user", "content": "hello"}],
                        "auth_token": "valid-token",
                    }
                )

                event = ws.receive_json()
                self.assertEqual(event.get("type"), "done")
                self.assertEqual(event.get("content"), "ok")
                self.assertEqual(dummy_manager.last_owner, "alice")


if __name__ == "__main__":
    unittest.main()
