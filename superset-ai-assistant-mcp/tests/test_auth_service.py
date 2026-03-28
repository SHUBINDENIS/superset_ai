import os
import sqlite3
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

    def _create_legacy_service(self, *, users, history_rows):
        db_path = Path(self.temp_dir.name) / f"legacy_{len(users)}_{len(history_rows)}.db"
        conn = sqlite3.connect(str(db_path))
        conn.executescript(
            """
            CREATE TABLE auth_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL COLLATE NOCASE UNIQUE,
                password_hash TEXT NOT NULL,
                password_salt TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'analyst',
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                assistant_session_id TEXT
            );

            CREATE TABLE auth_chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE INDEX idx_auth_users_username ON auth_users(username);
            CREATE INDEX idx_auth_chat_history_user_created ON auth_chat_history(username, created_at);
            """
        )
        for user in users:
            salt_hex = str(user.get("password_salt", "ab" * 16))
            password = str(user.get("password", "strongpass"))
            password_hash = self.service._hash_password(password, salt_hex)
            conn.execute(
                """
                INSERT INTO auth_users(
                    username, password_hash, password_salt, role, is_active,
                    created_at, updated_at, assistant_session_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user["username"],
                    password_hash,
                    salt_hex,
                    user.get("role", "analyst"),
                    int(user.get("is_active", 1)),
                    user["created_at"],
                    user["updated_at"],
                    user.get("assistant_session_id"),
                ),
            )
        for row in history_rows:
            conn.execute(
                """
                INSERT INTO auth_chat_history(username, session_id, role, content, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    row["username"],
                    row["session_id"],
                    row["role"],
                    row["content"],
                    row["created_at"],
                ),
            )
        conn.commit()
        conn.close()
        return AuthService(db_path=str(db_path))

    def test_register_and_duplicate_user(self):
        created = self.service.register_user("alice", "strongpass")
        self.assertEqual(created["username"], "alice")
        self.assertEqual(created["role"], "analyst")
        self.assertTrue(created["assistant_session_id"])
        sessions = self.service.list_chat_sessions(username="alice")
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["session_id"], created["assistant_session_id"])
        self.assertEqual(
            sessions[0]["settings"],
            {"response_style": "business", "detail_level": "standard"},
        )

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

    def test_create_and_rename_chat_session_updates_active_pointer(self):
        self.service.register_user("erica", "superpass")
        initial_session_id = self.service.get_or_create_user_session("erica")

        created = self.service.create_chat_session("erica", title="Продажи за квартал")
        self.assertNotEqual(created["session_id"], initial_session_id)
        self.assertEqual(created["title"], "Продажи за квартал")
        self.assertEqual(
            self.service.get_user("erica")["assistant_session_id"],
            created["session_id"],
        )

        renamed = self.service.rename_chat_session(
            username="erica",
            session_id=created["session_id"],
            title="Продажи за квартал / обновлено",
        )
        self.assertEqual(renamed["title"], "Продажи за квартал / обновлено")

        sessions = self.service.list_chat_sessions(username="erica")
        session_ids = {item["session_id"] for item in sessions}
        self.assertEqual(len(sessions), 2)
        self.assertIn(initial_session_id, session_ids)
        self.assertIn(created["session_id"], session_ids)

        activated = self.service.set_active_chat_session(
            username="erica",
            session_id=initial_session_id,
        )
        self.assertEqual(activated["session_id"], initial_session_id)
        self.assertEqual(
            self.service.get_user("erica")["assistant_session_id"],
            initial_session_id,
        )

    def test_chat_history_roundtrip_preserves_legacy_userwide_behavior(self):
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
        per_session = self.service.list_chat_history(
            username="eva",
            session_id=session_id,
            limit=20,
        )
        self.assertEqual(len(per_session), 2)

        removed = self.service.clear_chat_history(username="eva")
        self.assertEqual(removed, 2)
        self.assertEqual(self.service.list_chat_history(username="eva"), [])
        self.assertEqual(len(self.service.list_chat_sessions(username="eva")), 1)

    def test_update_chat_session_settings_persists_per_chat(self):
        self.service.register_user("frank", "superpass")
        first_session_id = self.service.get_or_create_user_session("frank")
        second_session_id = self.service.create_chat_session("frank", title="Тех чат")["session_id"]

        updated = self.service.update_chat_session_settings(
            username="frank",
            session_id=second_session_id,
            settings={"response_style": "technical", "detail_level": "detailed"},
        )

        self.assertEqual(
            updated["settings"],
            {"response_style": "technical", "detail_level": "detailed"},
        )
        first = self.service.get_chat_session(username="frank", session_id=first_session_id)
        second = self.service.get_chat_session(username="frank", session_id=second_session_id)
        self.assertEqual(
            first["settings"],
            {"response_style": "business", "detail_level": "standard"},
        )
        self.assertEqual(
            second["settings"],
            {"response_style": "technical", "detail_level": "detailed"},
        )

    def test_multi_session_history_is_separated_and_clearable_per_session(self):
        self.service.register_user("gina", "superpass")
        first_session_id = self.service.get_or_create_user_session("gina")

        self.service.save_chat_message(
            username="gina",
            session_id=first_session_id,
            role="user",
            content="Покажи выручку",
        )
        self.service.save_chat_message(
            username="gina",
            session_id=first_session_id,
            role="assistant",
            content="Показываю выручку",
        )

        second_session = self.service.create_chat_session("gina", title="Новый сценарий")
        second_session_id = second_session["session_id"]
        self.service.save_chat_message(
            username="gina",
            session_id=second_session_id,
            role="user",
            content="Покажи прибыль",
        )
        self.service.save_chat_message(
            username="gina",
            session_id=second_session_id,
            role="assistant",
            content="Показываю прибыль",
        )

        first_history = self.service.list_chat_history(
            username="gina",
            session_id=first_session_id,
            limit=20,
        )
        second_history = self.service.list_chat_history(
            username="gina",
            session_id=second_session_id,
            limit=20,
        )
        all_history = self.service.list_chat_history(username="gina", limit=20)

        self.assertEqual([item["session_id"] for item in first_history], [first_session_id] * 2)
        self.assertEqual([item["session_id"] for item in second_history], [second_session_id] * 2)
        self.assertEqual(len(all_history), 4)

        removed = self.service.clear_chat_history(
            username="gina",
            session_id=second_session_id,
        )
        self.assertEqual(removed, 2)
        self.assertEqual(
            len(self.service.list_chat_history(username="gina", session_id=first_session_id)),
            2,
        )
        self.assertEqual(
            self.service.list_chat_history(username="gina", session_id=second_session_id),
            [],
        )

    def test_chat_history_persists_message_metadata_and_artifacts(self):
        self.service.register_user("henry", "superpass")
        session_id = self.service.get_or_create_user_session("henry")

        self.service.save_chat_message(
            username="henry",
            session_id=session_id,
            role="assistant",
            content="Собрал preview",
            metadata={
                "finish_reason": "stop",
                "model": "gpt-5.4-mini",
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
                            "rows": [{"store": "A"}],
                        },
                    }
                ],
            },
        )

        history = self.service.list_chat_history(
            username="henry",
            session_id=session_id,
            limit=10,
        )

        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["finish_reason"], "stop")
        self.assertEqual(history[0]["model"], "gpt-5.4-mini")
        self.assertEqual(history[0]["response_style"], "technical")
        self.assertEqual(history[0]["detail_level"], "detailed")
        self.assertEqual(history[0]["artifacts"][0]["artifact_type"], "table_preview")
        self.assertEqual(history[0]["artifacts"][0]["payload"]["link_label"], "Открыть SQL Lab")

    def test_archive_non_active_chat_hides_it_from_default_list(self):
        self.service.register_user("helen", "superpass")
        first_session_id = self.service.get_or_create_user_session("helen")
        second_session = self.service.create_chat_session("helen", title="Второй чат")

        deleted = self.service.archive_chat_session(
            username="helen",
            session_id=first_session_id,
        )

        self.assertFalse(deleted["was_active"])
        self.assertEqual(deleted["deleted_session_id"], first_session_id)
        self.assertEqual(deleted["next_active_session_id"], second_session["session_id"])

        visible_ids = {
            item["session_id"] for item in self.service.list_chat_sessions(username="helen")
        }
        all_sessions = self.service.list_chat_sessions(username="helen", include_archived=True)

        self.assertNotIn(first_session_id, visible_ids)
        self.assertIn(second_session["session_id"], visible_ids)
        archived = next(item for item in all_sessions if item["session_id"] == first_session_id)
        self.assertTrue(archived["is_archived"])

    def test_archive_active_chat_reassigns_active_pointer(self):
        self.service.register_user("irene", "superpass")
        first_session_id = self.service.get_or_create_user_session("irene")
        second_session = self.service.create_chat_session("irene", title="Второй чат")

        self.service.set_active_chat_session(
            username="irene",
            session_id=first_session_id,
        )

        deleted = self.service.archive_chat_session(
            username="irene",
            session_id=first_session_id,
        )

        self.assertTrue(deleted["was_active"])
        self.assertEqual(deleted["next_active_session_id"], second_session["session_id"])
        self.assertEqual(
            self.service.get_user("irene")["assistant_session_id"],
            second_session["session_id"],
        )
        self.assertIsNone(
            self.service.get_chat_session(username="irene", session_id=first_session_id)
        )

    def test_archive_last_chat_clears_active_pointer(self):
        self.service.register_user("julia", "superpass")
        only_session_id = self.service.get_or_create_user_session("julia")

        deleted = self.service.archive_chat_session(
            username="julia",
            session_id=only_session_id,
        )

        self.assertTrue(deleted["was_active"])
        self.assertIsNone(deleted["next_active_session_id"])
        self.assertEqual(self.service.get_user("julia")["assistant_session_id"], "")
        self.assertEqual(self.service.list_chat_sessions(username="julia"), [])

    def test_backfill_creates_chat_sessions_from_legacy_history(self):
        service = self._create_legacy_service(
            users=[
                {
                    "username": "hank",
                    "password": "superpass",
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "updated_at": "2026-01-01T00:00:00+00:00",
                    "assistant_session_id": "sess_a",
                }
            ],
            history_rows=[
                {
                    "username": "hank",
                    "session_id": "sess_a",
                    "role": "user",
                    "content": "Первый исторический чат",
                    "created_at": "2026-01-02T10:00:00+00:00",
                },
                {
                    "username": "hank",
                    "session_id": "sess_a",
                    "role": "assistant",
                    "content": "Ответ по первому чату",
                    "created_at": "2026-01-02T10:01:00+00:00",
                },
                {
                    "username": "hank",
                    "session_id": "sess_b",
                    "role": "user",
                    "content": "Второй исторический чат",
                    "created_at": "2026-01-03T11:00:00+00:00",
                },
                {
                    "username": "hank",
                    "session_id": "sess_b",
                    "role": "assistant",
                    "content": "Ответ по второму чату",
                    "created_at": "2026-01-03T11:01:00+00:00",
                },
            ],
        )

        sessions = service.list_chat_sessions(username="hank", include_archived=True)
        self.assertEqual(len(sessions), 2)
        self.assertEqual(service.get_user("hank")["assistant_session_id"], "sess_a")
        self.assertEqual(
            service.get_chat_session(username="hank", session_id="sess_a")["title"],
            "Первый исторический чат",
        )
        self.assertEqual(
            service.get_chat_session(username="hank", session_id="sess_b")["title"],
            "Второй исторический чат",
        )

    def test_backfill_old_user_without_active_pointer_reuses_latest_session(self):
        service = self._create_legacy_service(
            users=[
                {
                    "username": "ivan",
                    "password": "superpass",
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "updated_at": "2026-01-01T00:00:00+00:00",
                    "assistant_session_id": "",
                }
            ],
            history_rows=[
                {
                    "username": "ivan",
                    "session_id": "legacy_1",
                    "role": "user",
                    "content": "Старый чат",
                    "created_at": "2026-01-02T08:00:00+00:00",
                },
                {
                    "username": "ivan",
                    "session_id": "legacy_2",
                    "role": "user",
                    "content": "Новый чат",
                    "created_at": "2026-01-03T09:00:00+00:00",
                },
            ],
        )

        active_session_id = service.get_or_create_user_session("ivan")
        self.assertEqual(active_session_id, "legacy_2")
        self.assertEqual(service.get_user("ivan")["assistant_session_id"], "legacy_2")
        self.assertEqual(len(service.list_chat_sessions(username="ivan")), 2)

    def test_backfill_old_user_without_history_preserves_active_pointer(self):
        service = self._create_legacy_service(
            users=[
                {
                    "username": "jane",
                    "password": "superpass",
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "updated_at": "2026-01-01T00:00:00+00:00",
                    "assistant_session_id": "seed_1",
                }
            ],
            history_rows=[],
        )

        sessions = service.list_chat_sessions(username="jane")
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["session_id"], "seed_1")
        self.assertEqual(sessions[0]["title"], "Новый чат")
        self.assertEqual(service.get_or_create_user_session("jane"), "seed_1")


if __name__ == "__main__":
    unittest.main()
