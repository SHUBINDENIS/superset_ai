"""
US10-US12 guardrails:
- US10: static SQL safety checks (read-only + block-list)
- US11: access policy checks (PII guard, role-based table restrictions, row-filter hints)
- US12: quotas and cost/complexity simulation with usage journal
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_ANALYTICS_KEYWORDS = [
    "superset",
    "дашборд",
    "dashboard",
    "chart",
    "график",
    "sql",
    "таблиц",
    "table",
    "dataset",
    "датасет",
    "метрик",
    "metric",
    "данн",
    "аналит",
    "query",
    "запрос",
]

DEFAULT_ANALYTICS_INTENT_KEYWORDS = [
    "покажи",
    "выведи",
    "сравни",
    "найди",
    "сделай",
    "построй",
    "рассчитай",
    "посчитай",
    "сколько",
    "топ",
    "динам",
    "тренд",
    "show",
    "build",
    "compare",
    "analy",
    "plot",
]

DEFAULT_ANALYTICS_DOMAIN_KEYWORDS = [
    "продаж",
    "выруч",
    "заказ",
    "пользоват",
    "клиент",
    "регион",
    "категор",
    "сегмент",
    "конверс",
    "retention",
    "nps",
    "марж",
    "воронк",
    "когорт",
    "доход",
    "расход",
    "план",
    "факт",
    "birth",
    "name",
    "country",
    "channel",
]

DEFAULT_ASSISTANT_SUPPORT_KEYWORDS = [
    "ошиб",
    "не работает",
    "почему",
    "как",
    "помоги",
    "исправ",
    "подсказ",
    "пример",
    "чате",
    "assistant",
    "ассистент",
    "не получается",
]

DEFAULT_OFFTOPIC_PATTERNS = [
    r"\bпогод[аыуе]\b",
    r"\bанекдот\w*\b",
    r"\bстих\w*\b",
    r"\bрецепт\w*\b",
    r"\bперевед[иите]\b",
    r"\btranslate\b",
    r"\bwho\s+are\s+you\b",
]

DEFAULT_INJECTION_PATTERNS = [
    r"забуд[ьи]\s+вс[её]",
    r"игнорир\w+\s+инструкц",
    r"forget\s+all",
    r"ignore\s+(all\s+)?(previous|above)\s+instructions?",
    r"system\s+prompt",
    r"jailbreak",
]

DEFAULT_BLOCKED_SQL_KEYWORDS = [
    "drop",
    "delete",
    "update",
    "insert",
    "alter",
    "truncate",
    "create",
    "grant",
    "revoke",
    "merge",
    "execute",
    "call",
]

DEFAULT_ALLOWED_SQL_START = ["select", "with", "explain"]

DEFAULT_PII_PATTERNS = [
    "email",
    "e-mail",
    "mail",
    "phone",
    "телефон",
    "password",
    "парол",
    "token",
    "passport",
    "паспорт",
    "ssn",
    "inn",
    "snils",
    "адрес",
    "address",
    "фио",
    "surname",
    "lastname",
]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    return _utc_now().isoformat()


def _normalize_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def _normalize_csv(raw: str) -> List[str]:
    if not isinstance(raw, str) or not raw.strip():
        return []
    return [x.strip() for x in raw.split(",") if x.strip()]


def _normalize_table_policy_token(value: Any) -> str:
    token = _normalize_text(str(value))
    if not token:
        return ""
    token = token.strip("`'\"").casefold()
    token = token.rstrip(";")
    token = re.sub(r"\s+", "", token)
    return token


def _table_base_name(token: str) -> str:
    normalized = _normalize_table_policy_token(token)
    if not normalized:
        return ""
    return normalized.split(".")[-1]


class US10To12GuardrailsService:
    def __init__(
        self,
        db_path: Optional[str] = None,
        *,
        max_requests_per_minute: Optional[int] = None,
        max_requests_per_hour: Optional[int] = None,
        max_complexity_score: Optional[int] = None,
        default_role: Optional[str] = None,
        allowed_tables: Optional[List[str]] = None,
        block_non_service_inputs: Optional[bool] = None,
        block_prompt_injection: Optional[bool] = None,
    ):
        default_db = (
            Path(__file__).resolve().parent.parent / "data" / "us10_12_guardrails.db"
        )
        self.db_path = Path(db_path or os.getenv("US10_12_DB_PATH", str(default_db)))
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.max_requests_per_minute = (
            int(max_requests_per_minute)
            if max_requests_per_minute is not None
            else int(os.getenv("US12_MAX_REQUESTS_PER_MINUTE", "8"))
        )
        self.max_requests_per_hour = (
            int(max_requests_per_hour)
            if max_requests_per_hour is not None
            else int(os.getenv("US12_MAX_REQUESTS_PER_HOUR", "120"))
        )
        self.max_complexity_score = (
            int(max_complexity_score)
            if max_complexity_score is not None
            else int(os.getenv("US12_MAX_COMPLEXITY_SCORE", "16"))
        )

        self.default_role = _normalize_text(
            default_role or os.getenv("US11_DEFAULT_ROLE", "analyst")
        ).lower() or "analyst"

        if allowed_tables is not None:
            self.allowed_tables = [
                _normalize_table_policy_token(x)
                for x in allowed_tables
                if _normalize_text(x)
            ]
        else:
            self.allowed_tables = [
                _normalize_table_policy_token(x)
                for x in _normalize_csv(os.getenv("US11_ALLOWED_TABLES", ""))
            ]
        self.allowed_tables = [x for x in self.allowed_tables if x]
        self.allowed_table_variants = set(self.allowed_tables)
        self.allowed_table_variants.update(
            _table_base_name(table_name) for table_name in self.allowed_tables
        )
        self.allowed_table_variants.discard("")

        pii_patterns_raw = _normalize_csv(os.getenv("US11_PII_PATTERNS", ""))
        self.pii_patterns = pii_patterns_raw or list(DEFAULT_PII_PATTERNS)
        if block_non_service_inputs is not None:
            self.block_non_service_inputs = bool(block_non_service_inputs)
        else:
            self.block_non_service_inputs = (
                os.getenv("US10_BLOCK_NON_SERVICE_INPUT", "true").strip().lower()
                in {"1", "true", "yes", "on", "y"}
            )
        if block_prompt_injection is not None:
            self.block_prompt_injection = bool(block_prompt_injection)
        else:
            self.block_prompt_injection = (
                os.getenv("US10_BLOCK_PROMPT_INJECTION", "true").strip().lower()
                in {"1", "true", "yes", "on", "y"}
            )

        row_filters_raw = os.getenv("US11_ROW_FILTERS_JSON", "").strip()
        self.row_filters_by_role: Dict[str, str] = {}
        if row_filters_raw:
            try:
                parsed = json.loads(row_filters_raw)
                if isinstance(parsed, dict):
                    self.row_filters_by_role = {
                        str(k).strip().lower(): str(v).strip()
                        for k, v in parsed.items()
                        if str(k).strip() and str(v).strip()
                    }
            except Exception:
                self.row_filters_by_role = {}

        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS us12_usage_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    query_text TEXT NOT NULL,
                    complexity_score INTEGER NOT NULL,
                    allowed INTEGER NOT NULL,
                    decision_code TEXT NOT NULL,
                    decision_reason TEXT,
                    created_at TEXT NOT NULL
                );
                """
            )

    def evaluate_user_input(
        self,
        query_text: str,
        *,
        session_id: str,
        role: Optional[str] = None,
    ) -> Dict[str, Any]:
        text = _normalize_text(query_text)
        user_role = _normalize_text(role or self.default_role).lower() or "analyst"
        warnings: List[str] = []

        if not text:
            return self._decision(
                allowed=False,
                code="empty_input",
                reason="Пустой запрос.",
                session_id=session_id,
                role=user_role,
                query_text=text,
                complexity_score=0,
                warnings=warnings,
            )

        if self.block_prompt_injection:
            injection_reason = self._detect_prompt_injection(text)
            if injection_reason:
                return self._decision(
                    allowed=False,
                    code="prompt_injection_blocked",
                    reason=injection_reason,
                    session_id=session_id,
                    role=user_role,
                    query_text=text,
                    complexity_score=0,
                    warnings=warnings,
                )

        if self.block_non_service_inputs and not self._is_service_related(text):
            return self._decision(
                allowed=False,
                code="offtopic_blocked",
                reason=(
                    "Запрос не относится к аналитике Superset/SQL. "
                    "Сформулируйте задачу про дашборды, таблицы, метрики или данные."
                ),
                session_id=session_id,
                role=user_role,
                query_text=text,
                complexity_score=0,
                warnings=warnings,
            )

        sql_validation = self._validate_sql_read_only(text)
        if not sql_validation["allowed"]:
            return self._decision(
                allowed=False,
                code="sql_blocked",
                reason=sql_validation["reason"],
                session_id=session_id,
                role=user_role,
                query_text=text,
                complexity_score=0,
                warnings=warnings,
            )
        warnings.extend(sql_validation.get("warnings", []))

        pii_block = self._check_pii_policy(text=text, role=user_role)
        if pii_block is not None:
            return self._decision(
                allowed=False,
                code="pii_blocked",
                reason=pii_block,
                session_id=session_id,
                role=user_role,
                query_text=text,
                complexity_score=0,
                warnings=warnings,
            )

        table_policy_block = self._check_table_policy(text=text, role=user_role)
        if table_policy_block is not None:
            return self._decision(
                allowed=False,
                code="table_policy_blocked",
                reason=table_policy_block,
                session_id=session_id,
                role=user_role,
                query_text=text,
                complexity_score=0,
                warnings=warnings,
            )

        complexity_score = self._estimate_complexity(text)
        quota_check = self._check_quota(session_id=session_id, complexity_score=complexity_score)
        if not quota_check["allowed"]:
            return self._decision(
                allowed=False,
                code=quota_check["code"],
                reason=quota_check["reason"],
                session_id=session_id,
                role=user_role,
                query_text=text,
                complexity_score=complexity_score,
                warnings=warnings,
            )

        if complexity_score > self.max_complexity_score - 4:
            warnings.append(
                "Запрос выглядит тяжёлым; при необходимости добавьте LIMIT/фильтры."
            )

        return self._decision(
            allowed=True,
            code="allowed",
            reason="ok",
            session_id=session_id,
            role=user_role,
            query_text=text,
            complexity_score=complexity_score,
            warnings=warnings,
        )

    def build_policy_context(self, *, role: Optional[str] = None) -> str:
        user_role = _normalize_text(role or self.default_role).lower() or "analyst"
        row_filter = self.row_filters_by_role.get(user_role, "")
        allowed_tables = ", ".join(self.allowed_tables) if self.allowed_tables else "-"
        pii_preview = ", ".join(self.pii_patterns[:8])
        lines = [
            "US10-US12 guardrails:",
            "- SQL режим только read-only (SELECT/WITH/EXPLAIN), destructive SQL запрещён.",
            f"- Текущая роль: {user_role}.",
            f"- Разрешённые таблицы (role policy): {allowed_tables}.",
            f"- PII policy: для non-admin запросы к PII блокируются ({pii_preview}).",
            (
                f"- Row-level policy hint: обязательно применять фильтр '{row_filter}'."
                if row_filter
                else "- Row-level policy hint: нет явного фильтра для роли."
            ),
            (
                f"- Quota policy: <= {self.max_requests_per_minute}/мин, "
                f"<= {self.max_requests_per_hour}/час, complexity <= {self.max_complexity_score}."
            ),
        ]
        return "\n".join(lines)

    def list_usage_events(self, session_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        sid = _normalize_text(session_id)
        if not sid:
            return []
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM us12_usage_events
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (sid, int(limit)),
            ).fetchall()
        return [dict(row) for row in rows]

    def clear_usage_events(self, session_id: str) -> int:
        sid = _normalize_text(session_id)
        if not sid:
            return 0
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM us12_usage_events WHERE session_id = ?",
                (sid,),
            )
        return int(cur.rowcount)

    def _decision(
        self,
        *,
        allowed: bool,
        code: str,
        reason: str,
        session_id: str,
        role: str,
        query_text: str,
        complexity_score: int,
        warnings: List[str],
    ) -> Dict[str, Any]:
        self._log_usage(
            session_id=session_id,
            role=role,
            query_text=query_text,
            complexity_score=complexity_score,
            allowed=allowed,
            code=code,
            reason=reason,
        )
        return {
            "allowed": allowed,
            "code": code,
            "reason": reason,
            "complexity_score": complexity_score,
            "warnings": list(warnings),
        }

    def _log_usage(
        self,
        *,
        session_id: str,
        role: str,
        query_text: str,
        complexity_score: int,
        allowed: bool,
        code: str,
        reason: str,
    ) -> None:
        sid = _normalize_text(session_id)
        if not sid:
            return
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO us12_usage_events(
                    session_id, role, query_text, complexity_score,
                    allowed, decision_code, decision_reason, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sid,
                    _normalize_text(role) or self.default_role,
                    query_text,
                    int(complexity_score),
                    1 if allowed else 0,
                    _normalize_text(code),
                    _normalize_text(reason),
                    _utc_now_iso(),
                ),
            )

    def _detect_prompt_injection(self, text: str) -> Optional[str]:
        low = text.casefold()
        for pattern in DEFAULT_INJECTION_PATTERNS:
            if re.search(pattern, low, flags=re.IGNORECASE):
                return (
                    "Обнаружена попытка обхода инструкций/политик. "
                    "Запрос заблокирован политикой безопасности."
                )
        return None

    def _is_service_related(self, text: str) -> bool:
        low = text.casefold()
        if self._extract_sql_candidate(text) or self._looks_like_sql(text):
            return True

        is_explicit_offtopic = any(
            re.search(pattern, low, flags=re.IGNORECASE)
            for pattern in DEFAULT_OFFTOPIC_PATTERNS
        )
        if is_explicit_offtopic:
            return False

        has_analytics_keyword = any(keyword in low for keyword in DEFAULT_ANALYTICS_KEYWORDS)
        has_intent_keyword = any(keyword in low for keyword in DEFAULT_ANALYTICS_INTENT_KEYWORDS)
        has_domain_keyword = any(keyword in low for keyword in DEFAULT_ANALYTICS_DOMAIN_KEYWORDS)
        has_support_keyword = any(keyword in low for keyword in DEFAULT_ASSISTANT_SUPPORT_KEYWORDS)
        has_analytics_structure = bool(
            re.search(
                r"\b(по|за|период|грануляр|фильтр|сортир|group|aggregate|агрег)\b",
                low,
            )
        )

        has_math_only_pattern = bool(
            re.search(r"^\s*[\d\.\+\-\*\/\(\)\s=]+\s*$", text)
        ) or bool(
            re.search(
                r"\b(умнож\w*|слож\w*|вычти\w*|подел\w*|divide|multiply|sqrt|sin|cos)\b",
                low,
            )
        )
        if has_math_only_pattern:
            return False
        if has_analytics_keyword:
            return True
        if has_intent_keyword and (has_domain_keyword or has_analytics_structure):
            return True
        if has_support_keyword:
            return True
        if has_intent_keyword or has_domain_keyword or has_analytics_structure:
            return True
        # Разрешаем нейтральные фразы в чате, если нет явного оффтопа/абьюза.
        return True

    def _validate_sql_read_only(self, text: str) -> Dict[str, Any]:
        warnings: List[str] = []
        sql_candidate = self._extract_sql_candidate(text)
        looks_like_sql = self._looks_like_sql(text)
        if not sql_candidate and not looks_like_sql:
            return {"allowed": True, "reason": "ok", "warnings": warnings}

        normalized = (sql_candidate or text).strip().rstrip(";")
        statements = [x.strip() for x in normalized.split(";") if x.strip()]
        if len(statements) > 1:
            return {
                "allowed": False,
                "reason": "Множественные SQL-стейтменты запрещены политикой безопасности.",
                "warnings": warnings,
            }

        first_stmt = statements[0].casefold() if statements else ""
        if any(re.search(rf"\b{kw}\b", first_stmt) for kw in DEFAULT_BLOCKED_SQL_KEYWORDS):
            return {
                "allowed": False,
                "reason": (
                    "Обнаружены запрещённые SQL-операции (DDL/DML). "
                    "Разрешены только read-only запросы."
                ),
                "warnings": warnings,
            }

        if not any(first_stmt.startswith(prefix) for prefix in DEFAULT_ALLOWED_SQL_START):
            return {
                "allowed": False,
                "reason": "Разрешены только SELECT/WITH/EXPLAIN запросы.",
                "warnings": warnings,
            }

        if "select *" in first_stmt:
            warnings.append("Нежелательно использовать SELECT *; укажите явные поля.")
        if " limit " not in first_stmt and not first_stmt.endswith(" limit"):
            warnings.append("Рекомендуется добавить LIMIT для защиты от тяжёлых запросов.")

        return {"allowed": True, "reason": "ok", "warnings": warnings}

    def _extract_sql_candidate(self, text: str) -> str:
        low = text.casefold()
        markers = ["select ", "with ", "explain "]
        for marker in markers:
            idx = low.find(marker)
            if idx >= 0:
                return text[idx:]
        return ""

    def _looks_like_sql(self, text: str) -> bool:
        value = _normalize_text(text)
        if not value:
            return False
        low = value.casefold()
        tokens = re.findall(r"[a-z_]+", low)
        if not tokens:
            return False

        sql_starts = {
            "select",
            "with",
            "explain",
            "insert",
            "update",
            "delete",
            "drop",
            "alter",
            "truncate",
            "create",
            "grant",
            "revoke",
            "merge",
            "call",
            "execute",
        }
        if tokens[0] not in sql_starts:
            return False

        sql_structure = {
            "from",
            "where",
            "join",
            "group",
            "order",
            "limit",
            "into",
            "table",
            "view",
            "database",
            "schema",
        }
        return any(token in sql_structure for token in tokens[1:])

    def _check_pii_policy(self, *, text: str, role: str) -> Optional[str]:
        if role == "admin":
            return None
        low = text.casefold()
        for pii in self.pii_patterns:
            token = pii.casefold()
            if token and token in low:
                return (
                    f"Запрос затрагивает PII-поле/термин '{pii}'. "
                    "Для текущей роли доступ ограничен."
                )
        return None

    def _check_table_policy(self, *, text: str, role: str) -> Optional[str]:
        if role == "admin" or not self.allowed_table_variants:
            return None
        requested_tables = self._extract_table_hints(text)
        if not requested_tables:
            return None
        unauthorized: List[str] = []
        for table_name in requested_tables:
            normalized = _normalize_table_policy_token(table_name)
            base = _table_base_name(normalized)
            if normalized in self.allowed_table_variants or base in self.allowed_table_variants:
                continue
            unauthorized.append(normalized or table_name)
        if unauthorized:
            return (
                "Запрошена таблица вне разрешённого списка для роли. "
                f"Недопустимые таблицы: {', '.join(unauthorized)}."
            )
        return None

    def _extract_table_hints(self, text: str) -> List[str]:
        patterns = [
            r"(?:таблиц[аы]|датасет[а]?|dataset|table)\s*[`\"']?([A-Za-z_][A-Za-z0-9_\.]*)[`\"']?",
            r"(?:из|from)\s+[`\"']?([A-Za-z_][A-Za-z0-9_\.]*)[`\"']?",
        ]
        found: List[str] = []
        for pattern in patterns:
            for match in re.findall(pattern, text, flags=re.IGNORECASE):
                token = _normalize_text(match)
                if token and token not in found:
                    found.append(token)
        return found

    def _estimate_complexity(self, text: str) -> int:
        low = text.casefold()
        score = 1
        score += len(re.findall(r"\bjoin\b", low)) * 3
        score += len(re.findall(r"\bunion\b", low)) * 4
        score += len(re.findall(r"\bgroup\s+by\b", low)) * 2
        score += len(re.findall(r"\border\s+by\b", low)) * 1
        score += len(re.findall(r"\bcount\s*\(", low)) * 1
        score += len(re.findall(r"\bsum\s*\(", low)) * 1
        score += len(re.findall(r"\bover\s*\(", low)) * 3
        score += len(re.findall(r"\(\s*select\b", low)) * 4
        if "select *" in low:
            score += 2
        if " limit " not in low:
            score += 2
        return max(1, score)

    def _check_quota(self, *, session_id: str, complexity_score: int) -> Dict[str, Any]:
        sid = _normalize_text(session_id)
        if not sid:
            return {"allowed": True, "code": "quota_skip", "reason": "no_session"}

        now = _utc_now()
        per_min_from = (now - timedelta(minutes=1)).isoformat()
        per_hour_from = (now - timedelta(hours=1)).isoformat()

        with self._connect() as conn:
            per_min_count = conn.execute(
                """
                SELECT COUNT(*) AS c
                FROM us12_usage_events
                WHERE session_id = ? AND created_at >= ?
                """,
                (sid, per_min_from),
            ).fetchone()["c"]
            per_hour_count = conn.execute(
                """
                SELECT COUNT(*) AS c
                FROM us12_usage_events
                WHERE session_id = ? AND created_at >= ?
                """,
                (sid, per_hour_from),
            ).fetchone()["c"]

        if per_min_count >= self.max_requests_per_minute:
            return {
                "allowed": False,
                "code": "quota_per_minute",
                "reason": (
                    f"Превышен лимит запросов в минуту ({self.max_requests_per_minute}). "
                    "Подождите немного и повторите."
                ),
            }

        if per_hour_count >= self.max_requests_per_hour:
            return {
                "allowed": False,
                "code": "quota_per_hour",
                "reason": (
                    f"Превышен лимит запросов в час ({self.max_requests_per_hour}). "
                    "Снизьте частоту запросов."
                ),
            }

        if complexity_score > self.max_complexity_score:
            return {
                "allowed": False,
                "code": "complexity_limit",
                "reason": (
                    f"Запрос оценён как слишком тяжёлый (score={complexity_score}, "
                    f"limit={self.max_complexity_score}). "
                    "Сузьте период/фильтры или добавьте LIMIT."
                ),
            }

        return {"allowed": True, "code": "quota_ok", "reason": "ok"}


def get_us10_12_guardrails_service() -> US10To12GuardrailsService:
    return US10To12GuardrailsService()


__all__ = [
    "US10To12GuardrailsService",
    "get_us10_12_guardrails_service",
]
