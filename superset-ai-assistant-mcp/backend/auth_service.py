"""
Authentication and per-user chat history service.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import jwt


_DEFAULT_JWT_SECRET = "change_me_in_env"
_USERNAME_PATTERN = re.compile(r"^\S{3,64}$")


class AuthService:
    def __init__(self, db_path: Optional[str] = None):
        default_path = Path(__file__).resolve().parent.parent / "data" / "auth.db"
        self.db_path = Path(db_path or os.getenv("AUTH_DB_PATH", str(default_path)))
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.jwt_secret = str(os.getenv("AUTH_JWT_SECRET", _DEFAULT_JWT_SECRET)).strip() or _DEFAULT_JWT_SECRET
        self.jwt_algorithm = "HS256"
        self.jwt_ttl_hours = max(1, int(os.getenv("AUTH_JWT_TTL_HOURS", "12")))
        self.password_min_length = max(4, int(os.getenv("AUTH_PASSWORD_MIN_LENGTH", "8")))
        self.history_max_messages = max(20, int(os.getenv("AUTH_HISTORY_MAX_MESSAGES", "500")))

        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS auth_users (
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

                CREATE TABLE IF NOT EXISTS auth_chat_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (username) REFERENCES auth_users(username) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_auth_users_username
                    ON auth_users(username);

                CREATE INDEX IF NOT EXISTS idx_auth_chat_history_user_created
                    ON auth_chat_history(username, created_at);
                """
            )

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _new_session_id() -> str:
        return uuid.uuid4().hex[:8]

    @staticmethod
    def _normalize_username(username: str) -> str:
        return str(username or "").strip()

    def _validate_username(self, username: str) -> None:
        if not username:
            raise ValueError("Логин обязателен.")
        if not _USERNAME_PATTERN.match(username):
            raise ValueError("Логин должен быть длиной 3-64 символа и без пробелов.")

    def _validate_password(self, password: str) -> None:
        value = str(password or "")
        if len(value) < self.password_min_length:
            raise ValueError(
                f"Пароль должен содержать минимум {self.password_min_length} символов."
            )

    @staticmethod
    def _hash_password(password: str, salt_hex: str) -> str:
        salt = bytes.fromhex(salt_hex)
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            str(password).encode("utf-8"),
            salt,
            210_000,
        )
        return digest.hex()

    def _get_user_row(self, username: str) -> Optional[sqlite3.Row]:
        normalized = self._normalize_username(username)
        if not normalized:
            return None
        with self._connect() as conn:
            return conn.execute(
                "SELECT * FROM auth_users WHERE username = ? COLLATE NOCASE",
                (normalized,),
            ).fetchone()

    def register_user(self, username: str, password: str) -> Dict[str, Any]:
        normalized = self._normalize_username(username)
        self._validate_username(normalized)
        self._validate_password(password)

        salt_hex = secrets.token_hex(16)
        password_hash = self._hash_password(password, salt_hex)
        session_id = self._new_session_id()
        now = self._utc_now()

        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO auth_users(
                        username, password_hash, password_salt, role, is_active,
                        created_at, updated_at, assistant_session_id
                    ) VALUES (?, ?, ?, 'analyst', 1, ?, ?, ?)
                    """,
                    (normalized, password_hash, salt_hex, now, now, session_id),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError("Пользователь с таким логином уже существует.") from exc

        return {
            "username": normalized,
            "role": "analyst",
            "is_active": True,
            "assistant_session_id": session_id,
        }

    def authenticate_user(self, username: str, password: str) -> Dict[str, Any]:
        row = self._get_user_row(username)
        if row is None or int(row["is_active"] or 0) != 1:
            raise ValueError("Неверный логин или пароль.")

        computed_hash = self._hash_password(password, str(row["password_salt"]))
        if not hmac.compare_digest(computed_hash, str(row["password_hash"])):
            raise ValueError("Неверный логин или пароль.")

        clean_username = str(row["username"]).strip()
        role = str(row["role"]).strip() or "analyst"
        session_id = str(row["assistant_session_id"] or "").strip()
        if not session_id:
            session_id = self.rotate_user_session(clean_username)

        token = self.issue_token(clean_username, role=role)
        return {
            "username": clean_username,
            "role": role,
            "session_id": session_id,
            "auth_token": token,
        }

    def issue_token(
        self,
        username: str,
        *,
        role: str = "analyst",
        ttl_seconds: Optional[int] = None,
    ) -> str:
        clean_username = self._normalize_username(username)
        if not clean_username:
            raise ValueError("username is required for token issue")

        now = datetime.now(timezone.utc)
        if ttl_seconds is None:
            ttl_seconds = int(self.jwt_ttl_hours * 3600)
        expires_at = now + timedelta(seconds=int(ttl_seconds))

        payload = {
            "sub": clean_username,
            "role": str(role or "analyst").strip() or "analyst",
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
        }
        return jwt.encode(payload, self.jwt_secret, algorithm=self.jwt_algorithm)

    def validate_token(self, token: str) -> Dict[str, Any]:
        clean_token = str(token or "").strip()
        if not clean_token:
            raise ValueError("Токен отсутствует.")

        try:
            payload = jwt.decode(
                clean_token,
                self.jwt_secret,
                algorithms=[self.jwt_algorithm],
            )
        except jwt.ExpiredSignatureError as exc:
            raise ValueError("Срок действия токена истек.") from exc
        except jwt.InvalidTokenError as exc:
            raise ValueError("Невалидный токен.") from exc

        username = self._normalize_username(payload.get("sub", ""))
        if not username:
            raise ValueError("Токен не содержит пользователя.")

        row = self._get_user_row(username)
        if row is None or int(row["is_active"] or 0) != 1:
            raise ValueError("Пользователь токена не найден или отключен.")

        return {
            "username": str(row["username"]).strip(),
            "role": str(row["role"]).strip() or "analyst",
            "session_id": str(row["assistant_session_id"] or "").strip(),
            "claims": payload,
        }

    def get_user(self, username: str) -> Optional[Dict[str, Any]]:
        row = self._get_user_row(username)
        if row is None:
            return None
        return {
            "username": str(row["username"]).strip(),
            "role": str(row["role"]).strip() or "analyst",
            "is_active": bool(int(row["is_active"] or 0)),
            "assistant_session_id": str(row["assistant_session_id"] or "").strip(),
        }

    def get_or_create_user_session(self, username: str) -> str:
        clean_username = self._normalize_username(username)
        row = self._get_user_row(clean_username)
        if row is None:
            raise ValueError("Пользователь не найден.")

        session_id = str(row["assistant_session_id"] or "").strip()
        if session_id:
            return session_id

        return self.rotate_user_session(clean_username)

    def rotate_user_session(self, username: str) -> str:
        clean_username = self._normalize_username(username)
        if not clean_username:
            raise ValueError("username is required")

        session_id = self._new_session_id()
        now = self._utc_now()
        with self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE auth_users
                SET assistant_session_id = ?, updated_at = ?
                WHERE username = ? COLLATE NOCASE
                """,
                (session_id, now, clean_username),
            )
        if int(cur.rowcount or 0) <= 0:
            raise ValueError("Пользователь не найден.")
        return session_id

    def get_session_owner(self, session_id: str) -> Optional[str]:
        clean_session_id = str(session_id or "").strip()
        if not clean_session_id:
            return None
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT username
                FROM auth_users
                WHERE assistant_session_id = ? AND is_active = 1
                LIMIT 1
                """,
                (clean_session_id,),
            ).fetchone()
        if row is None:
            return None
        return str(row["username"]).strip()

    def save_chat_message(
        self,
        *,
        username: str,
        session_id: str,
        role: str,
        content: str,
    ) -> None:
        clean_username = self._normalize_username(username)
        clean_session_id = str(session_id or "").strip()
        clean_role = str(role or "").strip().lower()
        clean_content = str(content or "").strip()

        if not clean_username or not clean_session_id:
            return
        if clean_role not in {"user", "assistant"}:
            raise ValueError("role must be user|assistant")
        if not clean_content:
            return

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO auth_chat_history(username, session_id, role, content, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (clean_username, clean_session_id, clean_role, clean_content, self._utc_now()),
            )

    def list_chat_history(
        self,
        *,
        username: str,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        clean_username = self._normalize_username(username)
        if not clean_username:
            return []

        safe_limit = self.history_max_messages if limit is None else max(1, int(limit))
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT session_id, role, content, created_at
                FROM auth_chat_history
                WHERE username = ? COLLATE NOCASE
                ORDER BY id DESC
                LIMIT ?
                """,
                (clean_username, safe_limit),
            ).fetchall()

        history: List[Dict[str, Any]] = []
        for row in reversed(rows):
            history.append(
                {
                    "session_id": str(row["session_id"]),
                    "role": str(row["role"]),
                    "content": str(row["content"]),
                    "created_at": str(row["created_at"]),
                }
            )
        return history

    def clear_chat_history(self, *, username: str) -> int:
        clean_username = self._normalize_username(username)
        if not clean_username:
            return 0
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM auth_chat_history WHERE username = ? COLLATE NOCASE",
                (clean_username,),
            )
        return int(cur.rowcount or 0)


_auth_service: Optional[AuthService] = None


def get_auth_service() -> AuthService:
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service
