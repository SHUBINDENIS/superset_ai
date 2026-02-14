"""
US5: Interactive query criteria builder + selection journal.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_METRIC_SUGGESTIONS = [
    "выручка",
    "количество заказов",
    "средний чек",
    "конверсия",
    "активные пользователи",
]

DEFAULT_PERIOD_SUGGESTIONS = [
    "за сегодня",
    "за последние 7 дней",
    "за последние 30 дней",
    "за текущий месяц",
    "за 2025 год",
]

DEFAULT_DIMENSION_SUGGESTIONS = [
    "регион",
    "категория",
    "канал продаж",
    "менеджер",
    "сегмент клиентов",
]

DEFAULT_TABLE_SUGGESTIONS = [
    "birth_names",
    "main.birth_names",
    "wb_health_population",
    "main.wb_health_population",
]

TIME_GRAIN_OPTIONS = ["day", "week", "month", "quarter", "year"]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _json_loads_or_raw(raw: str) -> Any:
    try:
        return json.loads(raw)
    except Exception:
        return raw


def _normalize_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def _normalize_list(value: Any) -> List[str]:
    if isinstance(value, list):
        tokens = [str(x).strip() for x in value if str(x).strip()]
        return tokens
    if isinstance(value, str):
        parts = [x.strip() for x in value.replace("\n", ",").split(",")]
        return [x for x in parts if x]
    return []


class US5QueryBuilderService:
    def __init__(self, db_path: Optional[str] = None):
        default_path = (
            Path(__file__).resolve().parent.parent / "data" / "us5_query_builder.db"
        )
        self.db_path = Path(db_path or os.getenv("US5_DB_PATH", str(default_path)))
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS us5_selection_journal (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    criterion_key TEXT NOT NULL,
                    criterion_value_json TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT 'ui',
                    created_at TEXT NOT NULL
                );
                """
            )

    def normalize_criteria(self, criteria: Dict[str, Any]) -> Dict[str, Any]:
        normalized = {
            "objective": _normalize_text(criteria.get("objective", "")),
            "table_name": _normalize_text(criteria.get("table_name", "")),
            "metric": _normalize_text(criteria.get("metric", "")),
            "dimensions": _normalize_list(criteria.get("dimensions", [])),
            "period": _normalize_text(criteria.get("period", "")),
            "time_grain": _normalize_text(criteria.get("time_grain", "month")) or "month",
            "filters": self._normalize_filters(criteria.get("filters", [])),
            "sort_by": _normalize_text(criteria.get("sort_by", "")),
            "sort_direction": (
                _normalize_text(criteria.get("sort_direction", "desc")).lower() or "desc"
            ),
            "top_n": self._normalize_top_n(criteria.get("top_n")),
            "compare_to": _normalize_text(criteria.get("compare_to", "")),
            "chart_type": _normalize_text(criteria.get("chart_type", "auto")) or "auto",
        }
        if normalized["time_grain"] not in TIME_GRAIN_OPTIONS:
            normalized["time_grain"] = "month"
        if normalized["sort_direction"] not in {"asc", "desc"}:
            normalized["sort_direction"] = "desc"
        return normalized

    def validate_criteria(self, criteria: Dict[str, Any]) -> Dict[str, Any]:
        data = self.normalize_criteria(criteria)
        blocking_missing: List[str] = []
        optional_missing: List[str] = []

        if not data["table_name"]:
            blocking_missing.append("table_name")
        if not data["metric"]:
            blocking_missing.append("metric")
        if not data["period"]:
            blocking_missing.append("period")
        if not data["dimensions"]:
            optional_missing.append("dimensions")

        questions: List[Dict[str, Any]] = []
        if "table_name" in blocking_missing:
            questions.append(
                {
                    "field": "table_name",
                    "question": "Из какой таблицы/датасета строим отчёт?",
                    "suggestions": list(DEFAULT_TABLE_SUGGESTIONS),
                    "required": True,
                }
            )
        if "metric" in blocking_missing:
            questions.append(
                {
                    "field": "metric",
                    "question": "Какую метрику считаем?",
                    "suggestions": list(DEFAULT_METRIC_SUGGESTIONS),
                    "required": True,
                }
            )
        if "period" in blocking_missing:
            questions.append(
                {
                    "field": "period",
                    "question": "За какой период строим отчет?",
                    "suggestions": list(DEFAULT_PERIOD_SUGGESTIONS),
                    "required": True,
                }
            )
        if "dimensions" in optional_missing:
            questions.append(
                {
                    "field": "dimensions",
                    "question": "По каким срезам группировать результат?",
                    "suggestions": list(DEFAULT_DIMENSION_SUGGESTIONS),
                    "required": False,
                }
            )

        return {
            "is_ready": len(blocking_missing) == 0,
            "blocking_missing": blocking_missing,
            "optional_missing": optional_missing,
            "clarification_questions": questions,
            "normalized_criteria": data,
        }

    def build_query(self, criteria: Dict[str, Any]) -> str:
        data = self.normalize_criteria(criteria)
        table_name = data["table_name"] or "<таблица>"
        metric = data["metric"] or "<метрика>"
        dimensions = data["dimensions"]

        parts: List[str] = [
            f"Используй только таблицу/датасет: {table_name}",
            f"Покажи {metric}",
        ]
        if dimensions:
            parts.append("по " + ", ".join(dimensions))
        parts.append(f"за период: {data['period'] or '<период>'}")
        parts.append(f"гранулярность времени: {data['time_grain']}")

        if data["filters"]:
            filters_text = "; ".join(
                f"{flt.get('field', '')}={flt.get('value', '')}" for flt in data["filters"]
            )
            if filters_text.strip("; "):
                parts.append(f"фильтры: {filters_text}")
        if data["compare_to"]:
            parts.append(f"сравни с: {data['compare_to']}")
        if data["sort_by"]:
            parts.append(
                f"сортировка: {data['sort_by']} ({data['sort_direction']})"
            )
        if data["top_n"] and data["top_n"] > 0:
            parts.append(f"ограничение: top-{data['top_n']}")
        if data["chart_type"] and data["chart_type"] != "auto":
            parts.append(f"предпочитаемый график: {data['chart_type']}")
        if data["objective"]:
            parts.append(f"цель: {data['objective']}")

        return ". ".join(parts).strip() + "."

    def log_criteria_selection(
        self,
        session_id: str,
        criteria: Dict[str, Any],
        source: str = "ui",
    ) -> int:
        sid = _normalize_text(session_id)
        if not sid:
            raise ValueError("session_id must not be empty.")
        normalized = self.normalize_criteria(criteria)
        to_log = {
            key: value
            for key, value in normalized.items()
            if value not in ("", None, [], {})
        }
        if not to_log:
            return 0

        with self._connect() as conn:
            for key, value in to_log.items():
                conn.execute(
                    """
                    INSERT INTO us5_selection_journal(
                        session_id, criterion_key, criterion_value_json, source, created_at
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        sid,
                        key,
                        _json_dumps(value),
                        _normalize_text(source) or "ui",
                        _utc_now(),
                    ),
                )
        return len(to_log)

    def list_journal(self, session_id: str, limit: int = 200) -> List[Dict[str, Any]]:
        sid = _normalize_text(session_id)
        if not sid:
            return []
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM us5_selection_journal
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (sid, int(limit)),
            ).fetchall()
        result: List[Dict[str, Any]] = []
        for row in rows:
            payload = dict(row)
            payload["criterion_value"] = _json_loads_or_raw(payload["criterion_value_json"])
            result.append(payload)
        return result

    def clear_journal(self, session_id: str) -> int:
        sid = _normalize_text(session_id)
        if not sid:
            return 0
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM us5_selection_journal WHERE session_id = ?",
                (sid,),
            )
        return int(cur.rowcount)

    def get_latest_criteria(self, session_id: str) -> Dict[str, Any]:
        journal = self.list_journal(session_id, limit=500)
        if not journal:
            return {}

        latest: Dict[str, Any] = {}
        seen = set()
        for item in journal:
            key = item.get("criterion_key")
            if not isinstance(key, str) or key in seen:
                continue
            latest[key] = item.get("criterion_value")
            seen.add(key)
        return self.normalize_criteria(latest)

    def build_agent_context(self, session_id: str, max_lines: int = 30) -> str:
        sid = _normalize_text(session_id)
        if not sid:
            return ""
        latest = self.get_latest_criteria(sid)
        if not latest:
            return ""

        lines = ["US5 контекст критериев аналитика (из журнала):"]
        lines.append(
            f"- table_name={latest.get('table_name', '-')}; "
            f"metric={latest.get('metric', '-')}; period={latest.get('period', '-')}; "
            f"time_grain={latest.get('time_grain', '-')}"
        )
        dims = latest.get("dimensions", [])
        if dims:
            lines.append("- dimensions=" + ", ".join(dims))
        filters = latest.get("filters", [])
        if filters:
            filters_text = "; ".join(
                f"{flt.get('field', '')}={flt.get('value', '')}" for flt in filters
            )
            lines.append("- filters=" + filters_text)
        if latest.get("sort_by"):
            lines.append(
                f"- sort={latest.get('sort_by')} ({latest.get('sort_direction', 'desc')})"
            )
        if latest.get("top_n"):
            lines.append(f"- top_n={latest.get('top_n')}")
        if latest.get("compare_to"):
            lines.append(f"- compare_to={latest.get('compare_to')}")
        if latest.get("chart_type"):
            lines.append(f"- chart_type={latest.get('chart_type')}")
        if latest.get("objective"):
            lines.append(f"- objective={latest.get('objective')}")

        journal = self.list_journal(sid, limit=max_lines)
        if journal:
            lines.append("Последние выбранные значения (US5 журнал):")
            for item in journal[:max_lines]:
                created_at = str(item.get("created_at", ""))
                key = str(item.get("criterion_key", ""))
                value = item.get("criterion_value")
                if isinstance(value, (list, dict)):
                    value_text = _json_dumps(value)
                else:
                    value_text = str(value)
                lines.append(f"- [{created_at}] {key}={value_text}")

        lines.append(
            "Используй этот контекст для построения более корректного и согласованного запроса."
        )
        return "\n".join(lines)

    @staticmethod
    def _normalize_top_n(value: Any) -> Optional[int]:
        if value in ("", None):
            return None
        try:
            parsed = int(value)
        except Exception:
            return None
        if parsed <= 0:
            return None
        return parsed

    @staticmethod
    def _normalize_filters(value: Any) -> List[Dict[str, str]]:
        if isinstance(value, list):
            normalized: List[Dict[str, str]] = []
            for item in value:
                if not isinstance(item, dict):
                    continue
                field = _normalize_text(item.get("field", ""))
                v = _normalize_text(item.get("value", ""))
                if field and v:
                    normalized.append({"field": field, "value": v})
            return normalized
        return []

    @staticmethod
    def parse_filters_text(raw: str) -> List[Dict[str, str]]:
        rows: List[Dict[str, str]] = []
        if not isinstance(raw, str) or not raw.strip():
            return rows
        for line in raw.splitlines():
            chunk = line.strip()
            if not chunk:
                continue
            if "=" in chunk:
                field, value = chunk.split("=", 1)
            elif ":" in chunk:
                field, value = chunk.split(":", 1)
            else:
                continue
            field = field.strip()
            value = value.strip()
            if field and value:
                rows.append({"field": field, "value": value})
        return rows


def get_us5_query_builder_service() -> US5QueryBuilderService:
    return US5QueryBuilderService()


__all__ = [
    "US5QueryBuilderService",
    "get_us5_query_builder_service",
    "DEFAULT_METRIC_SUGGESTIONS",
    "DEFAULT_PERIOD_SUGGESTIONS",
    "DEFAULT_DIMENSION_SUGGESTIONS",
    "DEFAULT_TABLE_SUGGESTIONS",
    "TIME_GRAIN_OPTIONS",
]
