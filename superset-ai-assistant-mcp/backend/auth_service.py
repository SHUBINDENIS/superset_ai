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
_DEFAULT_CHAT_TITLE = "Новый чат"
_MAX_CHAT_TITLE_LENGTH = 120


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

                CREATE TABLE IF NOT EXISTS auth_chat_sessions (
                    username TEXT NOT NULL COLLATE NOCASE,
                    session_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_message_at TEXT NOT NULL,
                    is_archived INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (username, session_id),
                    FOREIGN KEY (username) REFERENCES auth_users(username) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_auth_users_username
                    ON auth_users(username);

                CREATE INDEX IF NOT EXISTS idx_auth_chat_history_user_created
                    ON auth_chat_history(username, created_at);

                CREATE INDEX IF NOT EXISTS idx_auth_chat_history_user_session_created
                    ON auth_chat_history(username, session_id, created_at);

                CREATE INDEX IF NOT EXISTS idx_auth_chat_sessions_user_updated
                    ON auth_chat_sessions(username, is_archived, last_message_at, updated_at, created_at);
                """
            )
            self._backfill_chat_sessions(conn)

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _new_session_id() -> str:
        return uuid.uuid4().hex[:8]

    @staticmethod
    def _normalize_username(username: str) -> str:
        return str(username or "").strip()

    @staticmethod
    def _normalize_chat_title(
        title: str | None,
        *,
        fallback: str = _DEFAULT_CHAT_TITLE,
    ) -> str:
        compact = re.sub(r"\s+", " ", str(title or "")).strip()
        if not compact:
            compact = str(fallback or _DEFAULT_CHAT_TITLE).strip() or _DEFAULT_CHAT_TITLE
        if len(compact) > _MAX_CHAT_TITLE_LENGTH:
            compact = compact[: _MAX_CHAT_TITLE_LENGTH - 3].rstrip() + "..."
        return compact

    def _synthesize_chat_title(self, content: str | None) -> str:
        return self._normalize_chat_title(content, fallback=_DEFAULT_CHAT_TITLE)

    def _load_history_session_metadata(
        self,
        conn: sqlite3.Connection,
        *,
        username: str,
        session_id: str,
    ) -> Dict[str, str]:
        history_window = conn.execute(
            """
            SELECT MIN(created_at) AS created_at, MAX(created_at) AS last_message_at
            FROM auth_chat_history
            WHERE username = ? COLLATE NOCASE AND session_id = ?
            """,
            (username, session_id),
        ).fetchone()

        created_at = str((history_window or {})["created_at"] or "").strip() if history_window else ""
        last_message_at = (
            str((history_window or {})["last_message_at"] or "").strip() if history_window else ""
        )

        title_row = conn.execute(
            """
            SELECT content
            FROM auth_chat_history
            WHERE username = ? COLLATE NOCASE
              AND session_id = ?
              AND role = 'user'
              AND TRIM(content) != ''
            ORDER BY id ASC
            LIMIT 1
            """,
            (username, session_id),
        ).fetchone()
        if title_row is None:
            title_row = conn.execute(
                """
                SELECT content
                FROM auth_chat_history
                WHERE username = ? COLLATE NOCASE
                  AND session_id = ?
                  AND TRIM(content) != ''
                ORDER BY id ASC
                LIMIT 1
                """,
                (username, session_id),
            ).fetchone()

        title = self._synthesize_chat_title(title_row["content"] if title_row else "")
        return {
            "title": title,
            "created_at": created_at,
            "last_message_at": last_message_at,
        }

    def _ensure_chat_session_row(
        self,
        conn: sqlite3.Connection,
        *,
        username: str,
        session_id: str,
        title: str | None = None,
        created_at: str | None = None,
        updated_at: str | None = None,
        last_message_at: str | None = None,
        is_archived: bool = False,
    ) -> None:
        clean_username = self._normalize_username(username)
        clean_session_id = str(session_id or "").strip()
        if not clean_username or not clean_session_id:
            return

        now = self._utc_now()
        safe_created_at = str(created_at or now).strip() or now
        safe_last_message_at = str(last_message_at or updated_at or safe_created_at).strip() or safe_created_at
        safe_updated_at = str(updated_at or safe_last_message_at or safe_created_at).strip() or safe_last_message_at
        safe_title = self._normalize_chat_title(title)

        row = conn.execute(
            """
            SELECT title, created_at, updated_at, last_message_at, is_archived
            FROM auth_chat_sessions
            WHERE username = ? COLLATE NOCASE AND session_id = ?
            LIMIT 1
            """,
            (clean_username, clean_session_id),
        ).fetchone()
        if row is None:
            conn.execute(
                """
                INSERT INTO auth_chat_sessions(
                    username, session_id, title, created_at, updated_at, last_message_at, is_archived
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    clean_username,
                    clean_session_id,
                    safe_title,
                    safe_created_at,
                    safe_updated_at,
                    safe_last_message_at,
                    1 if is_archived else 0,
                ),
            )
            return

        current_title = self._normalize_chat_title(row["title"], fallback="")
        merged_title = current_title or safe_title
        merged_created_at = str(row["created_at"] or safe_created_at).strip() or safe_created_at
        merged_updated_at = str(row["updated_at"] or safe_updated_at).strip() or safe_updated_at
        merged_last_message_at = (
            str(row["last_message_at"] or safe_last_message_at).strip() or safe_last_message_at
        )
        archived_flag = int(row["is_archived"] or 0)
        desired_archived = 1 if is_archived else archived_flag

        if (
            merged_title == str(row["title"])
            and merged_created_at == str(row["created_at"])
            and merged_updated_at == str(row["updated_at"])
            and merged_last_message_at == str(row["last_message_at"])
            and desired_archived == int(row["is_archived"] or 0)
        ):
            return

        conn.execute(
            """
            UPDATE auth_chat_sessions
            SET title = ?, created_at = ?, updated_at = ?, last_message_at = ?, is_archived = ?
            WHERE username = ? COLLATE NOCASE AND session_id = ?
            """,
            (
                merged_title,
                merged_created_at,
                merged_updated_at,
                merged_last_message_at,
                desired_archived,
                clean_username,
                clean_session_id,
            ),
        )

    def _set_active_session(
        self,
        conn: sqlite3.Connection,
        *,
        username: str,
        session_id: str,
        updated_at: str | None = None,
    ) -> None:
        clean_username = self._normalize_username(username)
        clean_session_id = str(session_id or "").strip()
        if not clean_username or not clean_session_id:
            return
        conn.execute(
            """
            UPDATE auth_users
            SET assistant_session_id = ?, updated_at = ?
            WHERE username = ? COLLATE NOCASE
            """,
            (
                clean_session_id,
                str(updated_at or self._utc_now()).strip() or self._utc_now(),
                clean_username,
            ),
        )

    def _sync_chat_session_activity(
        self,
        conn: sqlite3.Connection,
        *,
        username: str,
        session_id: str,
    ) -> None:
        clean_username = self._normalize_username(username)
        clean_session_id = str(session_id or "").strip()
        if not clean_username or not clean_session_id:
            return

        session_row = conn.execute(
            """
            SELECT title, created_at, is_archived
            FROM auth_chat_sessions
            WHERE username = ? COLLATE NOCASE AND session_id = ?
            LIMIT 1
            """,
            (clean_username, clean_session_id),
        ).fetchone()
        if session_row is None:
            return

        metadata = self._load_history_session_metadata(
            conn,
            username=clean_username,
            session_id=clean_session_id,
        )
        current_title = self._normalize_chat_title(session_row["title"], fallback=_DEFAULT_CHAT_TITLE)
        current_created_at = str(session_row["created_at"] or "").strip()
        created_at = metadata["created_at"] or current_created_at or self._utc_now()
        last_message_at = metadata["last_message_at"] or created_at
        title = current_title
        if current_title == _DEFAULT_CHAT_TITLE and metadata["title"] != _DEFAULT_CHAT_TITLE:
            title = metadata["title"]
        conn.execute(
            """
            UPDATE auth_chat_sessions
            SET title = ?, created_at = ?, updated_at = ?, last_message_at = ?, is_archived = ?
            WHERE username = ? COLLATE NOCASE AND session_id = ?
            """,
            (
                title,
                created_at,
                self._utc_now(),
                last_message_at,
                int(session_row["is_archived"] or 0),
                clean_username,
                clean_session_id,
            ),
        )

    def _backfill_chat_sessions(self, conn: sqlite3.Connection) -> None:
        # Lazy, idempotent runtime migration for legacy SQLite files.
        history_sessions = conn.execute(
            """
            SELECT username, session_id, MIN(created_at) AS created_at, MAX(created_at) AS last_message_at
            FROM auth_chat_history
            WHERE TRIM(session_id) != ''
            GROUP BY username, session_id
            """
        ).fetchall()
        for row in history_sessions:
            username = self._normalize_username(row["username"])
            session_id = str(row["session_id"] or "").strip()
            if not username or not session_id:
                continue
            metadata = self._load_history_session_metadata(
                conn,
                username=username,
                session_id=session_id,
            )
            self._ensure_chat_session_row(
                conn,
                username=username,
                session_id=session_id,
                title=metadata["title"],
                created_at=metadata["created_at"] or str(row["created_at"] or "").strip(),
                updated_at=metadata["last_message_at"] or str(row["last_message_at"] or "").strip(),
                last_message_at=metadata["last_message_at"] or str(row["last_message_at"] or "").strip(),
            )

        user_rows = conn.execute(
            """
            SELECT username, assistant_session_id, created_at, updated_at
            FROM auth_users
            """
        ).fetchall()
        for row in user_rows:
            username = self._normalize_username(row["username"])
            active_session_id = str(row["assistant_session_id"] or "").strip()
            if active_session_id:
                metadata = self._load_history_session_metadata(
                    conn,
                    username=username,
                    session_id=active_session_id,
                )
                self._ensure_chat_session_row(
                    conn,
                    username=username,
                    session_id=active_session_id,
                    title=metadata["title"],
                    created_at=metadata["created_at"] or str(row["created_at"] or "").strip(),
                    updated_at=metadata["last_message_at"] or str(row["updated_at"] or "").strip(),
                    last_message_at=metadata["last_message_at"] or str(row["updated_at"] or "").strip(),
                )
                continue

            latest_session = conn.execute(
                """
                SELECT session_id, last_message_at
                FROM auth_chat_sessions
                WHERE username = ? COLLATE NOCASE
                ORDER BY last_message_at DESC, updated_at DESC, created_at DESC, session_id DESC
                LIMIT 1
                """,
                (username,),
            ).fetchone()
            if latest_session is not None:
                self._set_active_session(
                    conn,
                    username=username,
                    session_id=str(latest_session["session_id"] or "").strip(),
                    updated_at=str(latest_session["last_message_at"] or "").strip(),
                )

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
                self._ensure_chat_session_row(
                    conn,
                    username=normalized,
                    session_id=session_id,
                    title=_DEFAULT_CHAT_TITLE,
                    created_at=now,
                    updated_at=now,
                    last_message_at=now,
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
        else:
            with self._connect() as conn:
                metadata = self._load_history_session_metadata(
                    conn,
                    username=clean_username,
                    session_id=session_id,
                )
                self._ensure_chat_session_row(
                    conn,
                    username=clean_username,
                    session_id=session_id,
                    title=metadata["title"],
                    created_at=metadata["created_at"] or str(row["created_at"] or "").strip(),
                    updated_at=metadata["last_message_at"] or str(row["updated_at"] or "").strip(),
                    last_message_at=metadata["last_message_at"] or str(row["updated_at"] or "").strip(),
                )

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
            with self._connect() as conn:
                metadata = self._load_history_session_metadata(
                    conn,
                    username=clean_username,
                    session_id=session_id,
                )
                self._ensure_chat_session_row(
                    conn,
                    username=clean_username,
                    session_id=session_id,
                    title=metadata["title"],
                    created_at=metadata["created_at"] or str(row["created_at"] or "").strip(),
                    updated_at=metadata["last_message_at"] or str(row["updated_at"] or "").strip(),
                    last_message_at=metadata["last_message_at"] or str(row["updated_at"] or "").strip(),
                )
            return session_id

        sessions = self.list_chat_sessions(username=clean_username, include_archived=True)
        if sessions:
            latest = sessions[0]
            session_id = str(latest["session_id"]).strip()
            with self._connect() as conn:
                self._set_active_session(
                    conn,
                    username=clean_username,
                    session_id=session_id,
                    updated_at=str(latest.get("last_message_at", "")).strip() or None,
                )
            return session_id

        return self.create_chat_session(clean_username)["session_id"]

    def rotate_user_session(self, username: str) -> str:
        return str(self.create_chat_session(username)["session_id"])

    def set_active_chat_session(
        self,
        *,
        username: str,
        session_id: str,
    ) -> Dict[str, Any]:
        clean_username = self._normalize_username(username)
        clean_session_id = str(session_id or "").strip()
        if not clean_username or not clean_session_id:
            raise ValueError("username and session_id are required")
        if self._get_user_row(clean_username) is None:
            raise ValueError("Пользователь не найден.")

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT session_id, last_message_at, updated_at
                FROM auth_chat_sessions
                WHERE username = ? COLLATE NOCASE AND session_id = ?
                LIMIT 1
                """,
                (clean_username, clean_session_id),
            ).fetchone()
            if row is None:
                raise ValueError("Chat session не найдена.")
            self._set_active_session(
                conn,
                username=clean_username,
                session_id=clean_session_id,
                updated_at=str(row["last_message_at"] or row["updated_at"] or "").strip() or None,
            )

        session = self.get_chat_session(username=clean_username, session_id=clean_session_id)
        if session is None:
            raise RuntimeError("Failed to load active chat session.")
        return session

    def list_chat_sessions(
        self,
        *,
        username: str,
        include_archived: bool = False,
    ) -> List[Dict[str, Any]]:
        clean_username = self._normalize_username(username)
        if not clean_username:
            return []

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT assistant_session_id, created_at, updated_at
                FROM auth_users
                WHERE username = ? COLLATE NOCASE
                LIMIT 1
                """,
                (clean_username,),
            ).fetchone()
            if row is not None:
                active_session_id = str(row["assistant_session_id"] or "").strip()
                if active_session_id:
                    metadata = self._load_history_session_metadata(
                        conn,
                        username=clean_username,
                        session_id=active_session_id,
                    )
                    self._ensure_chat_session_row(
                        conn,
                        username=clean_username,
                        session_id=active_session_id,
                        title=metadata["title"],
                        created_at=metadata["created_at"] or str(row["created_at"] or "").strip(),
                        updated_at=metadata["last_message_at"] or str(row["updated_at"] or "").strip(),
                        last_message_at=metadata["last_message_at"] or str(row["updated_at"] or "").strip(),
                    )

            where_clause = "WHERE username = ? COLLATE NOCASE"
            params: list[Any] = [clean_username]
            if not include_archived:
                where_clause += " AND is_archived = 0"
            rows = conn.execute(
                f"""
                SELECT username, session_id, title, created_at, updated_at, last_message_at, is_archived
                FROM auth_chat_sessions
                {where_clause}
                ORDER BY last_message_at DESC, updated_at DESC, created_at DESC, session_id DESC
                """
                ,
                tuple(params),
            ).fetchall()

        sessions: List[Dict[str, Any]] = []
        for item in rows:
            sessions.append(
                {
                    "username": str(item["username"]).strip(),
                    "session_id": str(item["session_id"]).strip(),
                    "title": self._normalize_chat_title(item["title"]),
                    "created_at": str(item["created_at"]),
                    "updated_at": str(item["updated_at"]),
                    "last_message_at": str(item["last_message_at"]),
                    "is_archived": bool(int(item["is_archived"] or 0)),
                }
            )
        return sessions

    def create_chat_session(
        self,
        username: str,
        title: Optional[str] = None,
    ) -> Dict[str, Any]:
        clean_username = self._normalize_username(username)
        if not clean_username:
            raise ValueError("username is required")
        if self._get_user_row(clean_username) is None:
            raise ValueError("Пользователь не найден.")

        safe_title = self._normalize_chat_title(title)
        now = self._utc_now()
        last_error: Optional[Exception] = None
        for _ in range(5):
            session_id = self._new_session_id()
            try:
                with self._connect() as conn:
                    self._ensure_chat_session_row(
                        conn,
                        username=clean_username,
                        session_id=session_id,
                        title=safe_title,
                        created_at=now,
                        updated_at=now,
                        last_message_at=now,
                    )
                    self._set_active_session(
                        conn,
                        username=clean_username,
                        session_id=session_id,
                        updated_at=now,
                    )
                session = self.get_chat_session(
                    username=clean_username,
                    session_id=session_id,
                )
                if session is None:
                    raise RuntimeError("Failed to load newly created chat session.")
                return session
            except sqlite3.IntegrityError as exc:
                last_error = exc
        raise RuntimeError("Не удалось создать chat session.") from last_error

    def get_chat_session(
        self,
        *,
        username: str,
        session_id: str,
    ) -> Optional[Dict[str, Any]]:
        clean_username = self._normalize_username(username)
        clean_session_id = str(session_id or "").strip()
        if not clean_username or not clean_session_id:
            return None

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT username, session_id, title, created_at, updated_at, last_message_at, is_archived
                FROM auth_chat_sessions
                WHERE username = ? COLLATE NOCASE AND session_id = ?
                LIMIT 1
                """,
                (clean_username, clean_session_id),
            ).fetchone()
        if row is None:
            return None
        return {
            "username": str(row["username"]).strip(),
            "session_id": str(row["session_id"]).strip(),
            "title": self._normalize_chat_title(row["title"]),
            "created_at": str(row["created_at"]),
            "updated_at": str(row["updated_at"]),
            "last_message_at": str(row["last_message_at"]),
            "is_archived": bool(int(row["is_archived"] or 0)),
        }

    def rename_chat_session(
        self,
        *,
        username: str,
        session_id: str,
        title: str,
    ) -> Dict[str, Any]:
        clean_username = self._normalize_username(username)
        clean_session_id = str(session_id or "").strip()
        if not clean_username or not clean_session_id:
            raise ValueError("username and session_id are required")
        raw_title = re.sub(r"\s+", " ", str(title or "")).strip()
        if not raw_title:
            raise ValueError("title is required")
        safe_title = self._normalize_chat_title(raw_title)

        now = self._utc_now()
        with self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE auth_chat_sessions
                SET title = ?, updated_at = ?
                WHERE username = ? COLLATE NOCASE AND session_id = ?
                """,
                (safe_title, now, clean_username, clean_session_id),
            )
        if int(cur.rowcount or 0) <= 0:
            raise ValueError("Chat session не найдена.")

        session = self.get_chat_session(username=clean_username, session_id=clean_session_id)
        if session is None:
            raise RuntimeError("Failed to load renamed chat session.")
        return session

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
            self._ensure_chat_session_row(
                conn,
                username=clean_username,
                session_id=clean_session_id,
            )
            created_at = self._utc_now()
            conn.execute(
                """
                INSERT INTO auth_chat_history(username, session_id, role, content, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (clean_username, clean_session_id, clean_role, clean_content, created_at),
            )
            self._sync_chat_session_activity(
                conn,
                username=clean_username,
                session_id=clean_session_id,
            )

    def list_chat_history(
        self,
        *,
        username: str,
        session_id: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        clean_username = self._normalize_username(username)
        if not clean_username:
            return []

        safe_limit = self.history_max_messages if limit is None else max(1, int(limit))
        with self._connect() as conn:
            clean_session_id = str(session_id or "").strip()
            if clean_session_id:
                rows = conn.execute(
                    """
                    SELECT session_id, role, content, created_at
                    FROM auth_chat_history
                    WHERE username = ? COLLATE NOCASE AND session_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (clean_username, clean_session_id, safe_limit),
                ).fetchall()
            else:
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

    def clear_chat_history(
        self,
        *,
        username: str,
        session_id: Optional[str] = None,
    ) -> int:
        clean_username = self._normalize_username(username)
        if not clean_username:
            return 0
        with self._connect() as conn:
            clean_session_id = str(session_id or "").strip()
            session_ids_to_sync: List[str] = []
            if clean_session_id:
                session_ids_to_sync = [clean_session_id]
                cur = conn.execute(
                    """
                    DELETE FROM auth_chat_history
                    WHERE username = ? COLLATE NOCASE AND session_id = ?
                    """,
                    (clean_username, clean_session_id),
                )
            else:
                rows = conn.execute(
                    """
                    SELECT DISTINCT session_id
                    FROM auth_chat_history
                    WHERE username = ? COLLATE NOCASE
                    """,
                    (clean_username,),
                ).fetchall()
                session_ids_to_sync = [
                    str(row["session_id"]).strip()
                    for row in rows
                    if str(row["session_id"] or "").strip()
                ]
                cur = conn.execute(
                    "DELETE FROM auth_chat_history WHERE username = ? COLLATE NOCASE",
                    (clean_username,),
                )
            for item_session_id in session_ids_to_sync:
                self._sync_chat_session_activity(
                    conn,
                    username=clean_username,
                    session_id=item_session_id,
                )
        return int(cur.rowcount or 0)


_auth_service: Optional[AuthService] = None


def get_auth_service() -> AuthService:
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service
