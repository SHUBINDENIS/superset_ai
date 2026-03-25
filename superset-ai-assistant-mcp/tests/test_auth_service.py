import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.auth_service import AuthService


class TestAuthService(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.env_patch = patch.dict(
            os.environ,
            {
                "AUTH_JWT_SECRET": "unit-test-secret",
                "AUTH_JWT_TTL_HOURS": "12",
                "AUTH_PASSWORD_MIN_LENGTH": "8",
                "AUTH_HISTORY_MAX_MESSAGES": "200",
            },
            clear=False,
        )
        self.env_patch.start()
        db_path = Path(self.temp_dir.name) / "auth_test.db"
        self.service = AuthService(db_path=str(db_path))

    def tearDown(self):
        self.env_patch.stop()
        self.temp_dir.cleanup()

    def test_register_and_duplicate_user(self):
        created = self.service.register_user("alice", "strongpass")
        self.assertEqual(created["username"], "alice")
        self.assertEqual(created["role"], "analyst")
        self.assertTrue(created["assistant_session_id"])

        with self.assertRaises(ValueError):
            self.service.register_user("Alice", "anotherpass")

    def test_authenticate_with_wrong_password(self):
        self.service.register_user("bob", "correctpass")
        with self.assertRaises(ValueError):
            self.service.authenticate_user("bob", "wrongpass")

    def test_issue_and_validate_token(self):
        self.service.register_user("carol", "superpass")
        auth_result = self.service.authenticate_user("carol", "superpass")
        validated = self.service.validate_token(auth_result["auth_token"])
        self.assertEqual(validated["username"], "carol")
        self.assertEqual(validated["role"], "analyst")

    def test_expired_token_rejected(self):
        self.service.register_user("dave", "superpass")
        expired = self.service.issue_token("dave", ttl_seconds=-60)
        with self.assertRaises(ValueError):
            self.service.validate_token(expired)

    def test_chat_history_roundtrip(self):
        self.service.register_user("eva", "superpass")
        session_id = self.service.get_or_create_user_session("eva")

        self.service.save_chat_message(
            username="eva",
            session_id=session_id,
            role="user",
            content="Привет",
        )
        self.service.save_chat_message(
            username="eva",
            session_id=session_id,
            role="assistant",
            content="Здравствуйте",
        )

        history = self.service.list_chat_history(username="eva", limit=20)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["role"], "user")
        self.assertEqual(history[1]["role"], "assistant")

        removed = self.service.clear_chat_history(username="eva")
        self.assertEqual(removed, 2)
        self.assertEqual(self.service.list_chat_history(username="eva"), [])


if __name__ == "__main__":
    unittest.main()
