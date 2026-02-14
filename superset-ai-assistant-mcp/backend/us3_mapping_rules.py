"""
US3: Mapping rules service (term -> column/metric) with match logs.
"""

from __future__ import annotations

import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


ALLOWED_PATTERN_TYPES = {"keyword", "regex"}
ALLOWED_TARGET_TYPES = {"column", "metric"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MappingRulesService:
    def __init__(self, db_path: Optional[str] = None):
        default_path = (
            Path(__file__).resolve().parent.parent / "data" / "us3_mapping_rules.db"
        )
        self.db_path = Path(
            db_path or os.getenv("US3_RULES_DB_PATH", str(default_path))
        )
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS us3_mapping_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rule_name TEXT NOT NULL UNIQUE,
                    pattern TEXT NOT NULL,
                    pattern_type TEXT NOT NULL DEFAULT 'keyword',
                    target_type TEXT NOT NULL DEFAULT 'column',
                    database_name TEXT,
                    dataset_name TEXT,
                    schema_name TEXT,
                    table_name TEXT,
                    column_name TEXT,
                    metric_name TEXT,
                    priority INTEGER NOT NULL DEFAULT 100,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    notes TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_used_at TEXT
                );

                CREATE TABLE IF NOT EXISTS us3_rule_match_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rule_id INTEGER NOT NULL,
                    session_id TEXT,
                    query_text TEXT NOT NULL,
                    matched_text TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (rule_id) REFERENCES us3_mapping_rules(id) ON DELETE CASCADE
                );
                """
            )

    def _validate_pattern(self, pattern: str, pattern_type: str) -> None:
        if pattern_type not in ALLOWED_PATTERN_TYPES:
            raise ValueError(f"Unsupported pattern_type: {pattern_type}")
        if not pattern.strip():
            raise ValueError("Pattern must not be empty.")
        if pattern_type == "regex":
            try:
                re.compile(pattern, flags=re.IGNORECASE)
            except re.error as exc:
                raise ValueError(f"Invalid regex pattern: {exc}") from exc

    def _validate_target(self, target_type: str, column_name: str, metric_name: str) -> None:
        if target_type not in ALLOWED_TARGET_TYPES:
            raise ValueError(f"Unsupported target_type: {target_type}")
        if target_type == "column" and not column_name.strip():
            raise ValueError("For target_type=column provide column_name.")
        if target_type == "metric" and not metric_name.strip():
            raise ValueError("For target_type=metric provide metric_name.")

    def create_rule(
        self,
        *,
        rule_name: str,
        pattern: str,
        pattern_type: str = "keyword",
        target_type: str = "column",
        database_name: str = "",
        dataset_name: str = "",
        schema_name: str = "",
        table_name: str = "",
        column_name: str = "",
        metric_name: str = "",
        priority: int = 100,
        enabled: bool = True,
        notes: str = "",
    ) -> Dict[str, Any]:
        if not rule_name.strip():
            raise ValueError("Rule name must not be empty.")
        self._validate_pattern(pattern, pattern_type)
        self._validate_target(target_type, column_name, metric_name)
        now = _utc_now()
        try:
            with self._connect() as conn:
                cur = conn.execute(
                    """
                    INSERT INTO us3_mapping_rules(
                        rule_name, pattern, pattern_type, target_type,
                        database_name, dataset_name, schema_name, table_name,
                        column_name, metric_name, priority, enabled, notes,
                        created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        rule_name.strip(),
                        pattern.strip(),
                        pattern_type,
                        target_type,
                        database_name.strip(),
                        dataset_name.strip(),
                        schema_name.strip(),
                        table_name.strip(),
                        column_name.strip(),
                        metric_name.strip(),
                        int(priority),
                        1 if enabled else 0,
                        notes.strip(),
                        now,
                        now,
                    ),
                )
                rule_id = int(cur.lastrowid)
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"Rule '{rule_name.strip()}' already exists.") from exc
        return self.get_rule(rule_id)

    def list_rules(self, search: str = "", include_disabled: bool = True) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM us3_mapping_rules"
        args: List[Any] = []
        where = []

        if not include_disabled:
            where.append("enabled = 1")
        if search.strip():
            where.append("(rule_name LIKE ? OR pattern LIKE ? OR notes LIKE ?)")
            pat = f"%{search.strip()}%"
            args.extend([pat, pat, pat])
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY priority DESC, id DESC"

        with self._connect() as conn:
            rows = conn.execute(sql, args).fetchall()
        return [self._row_to_rule(row) for row in rows]

    def get_rule(self, rule_id: int) -> Dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM us3_mapping_rules WHERE id = ?",
                (rule_id,),
            ).fetchone()
        if row is None:
            raise ValueError(f"Rule {rule_id} not found.")
        return self._row_to_rule(row)

    def update_rule(self, rule_id: int, **kwargs: Any) -> Dict[str, Any]:
        current = self.get_rule(rule_id)
        new_rule = {
            "rule_name": kwargs.get("rule_name", current["rule_name"]).strip(),
            "pattern": kwargs.get("pattern", current["pattern"]).strip(),
            "pattern_type": kwargs.get("pattern_type", current["pattern_type"]),
            "target_type": kwargs.get("target_type", current["target_type"]),
            "database_name": kwargs.get("database_name", current.get("database_name", "")).strip(),
            "dataset_name": kwargs.get("dataset_name", current.get("dataset_name", "")).strip(),
            "schema_name": kwargs.get("schema_name", current.get("schema_name", "")).strip(),
            "table_name": kwargs.get("table_name", current.get("table_name", "")).strip(),
            "column_name": kwargs.get("column_name", current.get("column_name", "")).strip(),
            "metric_name": kwargs.get("metric_name", current.get("metric_name", "")).strip(),
            "priority": int(kwargs.get("priority", current.get("priority", 100))),
            "enabled": bool(kwargs.get("enabled", current.get("enabled", True))),
            "notes": kwargs.get("notes", current.get("notes", "")).strip(),
        }

        if not new_rule["rule_name"]:
            raise ValueError("Rule name must not be empty.")
        self._validate_pattern(new_rule["pattern"], new_rule["pattern_type"])
        self._validate_target(
            new_rule["target_type"], new_rule["column_name"], new_rule["metric_name"]
        )
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    UPDATE us3_mapping_rules
                    SET rule_name = ?, pattern = ?, pattern_type = ?, target_type = ?,
                        database_name = ?, dataset_name = ?, schema_name = ?, table_name = ?,
                        column_name = ?, metric_name = ?, priority = ?, enabled = ?,
                        notes = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        new_rule["rule_name"],
                        new_rule["pattern"],
                        new_rule["pattern_type"],
                        new_rule["target_type"],
                        new_rule["database_name"],
                        new_rule["dataset_name"],
                        new_rule["schema_name"],
                        new_rule["table_name"],
                        new_rule["column_name"],
                        new_rule["metric_name"],
                        new_rule["priority"],
                        1 if new_rule["enabled"] else 0,
                        new_rule["notes"],
                        _utc_now(),
                        rule_id,
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"Rule '{new_rule['rule_name']}' already exists.") from exc
        return self.get_rule(rule_id)

    def delete_rule(self, rule_id: int) -> None:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM us3_mapping_rules WHERE id = ?", (rule_id,))
        if cur.rowcount == 0:
            raise ValueError(f"Rule {rule_id} not found.")

    def evaluate_query(
        self, query_text: str, session_id: str = "", max_matches: int = 20
    ) -> List[Dict[str, Any]]:
        if not query_text.strip():
            return []
        rules = self.list_rules(include_disabled=False)
        matched: List[Dict[str, Any]] = []

        for rule in rules:
            pattern = rule["pattern"]
            pattern_type = rule["pattern_type"]
            match_text = None

            if pattern_type == "keyword":
                if pattern.casefold() in query_text.casefold():
                    match_text = pattern
            else:
                regex = re.compile(pattern, flags=re.IGNORECASE)
                m = regex.search(query_text)
                if m:
                    match_text = m.group(0)

            if match_text is None:
                continue

            rule_copy = dict(rule)
            rule_copy["matched_text"] = match_text
            matched.append(rule_copy)
            self._log_match(
                rule_id=rule["id"],
                session_id=session_id,
                query_text=query_text,
                matched_text=match_text,
            )
            self._mark_rule_used(rule["id"])

            if len(matched) >= max_matches:
                break

        return matched

    def build_inference_context(
        self, matched_rules: List[Dict[str, Any]], max_lines: int = 30
    ) -> str:
        if not matched_rules:
            return ""
        lines = ["US3 правила маппинга, сработавшие в текущем запросе:"]
        for idx, rule in enumerate(matched_rules):
            if idx >= max_lines:
                break
            target = self._rule_target_as_string(rule)
            lines.append(
                f"- Rule '{rule['rule_name']}' (priority={rule['priority']}), "
                f"match='{rule.get('matched_text', '')}', target={target}"
            )
        lines.append(
            "Используй эти соответствия для устранения неоднозначности и выбора колонок/метрик."
        )
        return "\n".join(lines)

    def list_match_logs(self, session_id: str = "", limit: int = 50) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            if session_id.strip():
                rows = conn.execute(
                    """
                    SELECT l.*, r.rule_name
                    FROM us3_rule_match_logs l
                    JOIN us3_mapping_rules r ON r.id = l.rule_id
                    WHERE l.session_id = ?
                    ORDER BY l.id DESC
                    LIMIT ?
                    """,
                    (session_id.strip(), int(limit)),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT l.*, r.rule_name
                    FROM us3_rule_match_logs l
                    JOIN us3_mapping_rules r ON r.id = l.rule_id
                    ORDER BY l.id DESC
                    LIMIT ?
                    """,
                    (int(limit),),
                ).fetchall()
        return [dict(row) for row in rows]

    def _log_match(
        self, *, rule_id: int, session_id: str, query_text: str, matched_text: str
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO us3_rule_match_logs(rule_id, session_id, query_text, matched_text, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    rule_id,
                    session_id.strip(),
                    query_text,
                    matched_text,
                    _utc_now(),
                ),
            )

    def _mark_rule_used(self, rule_id: int) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE us3_mapping_rules SET last_used_at = ? WHERE id = ?",
                (_utc_now(), rule_id),
            )

    @staticmethod
    def _rule_target_as_string(rule: Dict[str, Any]) -> str:
        parts = [
            rule.get("database_name", ""),
            rule.get("dataset_name", ""),
            rule.get("schema_name", ""),
            rule.get("table_name", ""),
            rule.get("column_name", ""),
            rule.get("metric_name", ""),
        ]
        parts = [x for x in parts if x]
        return ".".join(parts) if parts else "-"

    @staticmethod
    def _row_to_rule(row: sqlite3.Row) -> Dict[str, Any]:
        payload = dict(row)
        payload["enabled"] = bool(payload.get("enabled", 0))
        return payload


def get_us3_mapping_rules_service() -> MappingRulesService:
    return MappingRulesService()


__all__ = [
    "MappingRulesService",
    "get_us3_mapping_rules_service",
]

