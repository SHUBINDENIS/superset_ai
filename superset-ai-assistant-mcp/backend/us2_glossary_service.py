"""
US2: Business glossary service (CRUD + mappings to columns/metrics).
"""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_examples(raw: str) -> List[str]:
    if not raw:
        return []
    parts = [x.strip() for x in raw.replace("\n", ",").split(",")]
    return [x for x in parts if x]


@dataclass
class GlossaryTermInput:
    term: str
    definition: str = ""
    examples: Optional[List[str]] = None


class GlossaryService:
    def __init__(self, db_path: Optional[str] = None):
        default_path = (
            Path(__file__).resolve().parent.parent / "data" / "glossary.db"
        )
        self.db_path = Path(
            db_path or os.getenv("GLOSSARY_DB_PATH", str(default_path))
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
                CREATE TABLE IF NOT EXISTS glossary_terms (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    term TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    definition TEXT NOT NULL DEFAULT '',
                    examples_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS glossary_mappings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    term_id INTEGER NOT NULL,
                    database_name TEXT,
                    dataset_name TEXT,
                    schema_name TEXT,
                    table_name TEXT,
                    column_name TEXT,
                    metric_name TEXT,
                    notes TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (term_id) REFERENCES glossary_terms(id) ON DELETE CASCADE
                );
                """
            )

    def create_term(
        self, term: str, definition: str = "", examples: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        normalized_term = term.strip()
        if not normalized_term:
            raise ValueError("Term must not be empty.")
        self._ensure_term_unique(normalized_term)

        now = _utc_now()
        examples = examples or []
        examples_json = json.dumps(examples, ensure_ascii=False)

        try:
            with self._connect() as conn:
                cur = conn.execute(
                    """
                    INSERT INTO glossary_terms(term, definition, examples_json, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (normalized_term, definition.strip(), examples_json, now, now),
                )
                term_id = int(cur.lastrowid)
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"Term '{normalized_term}' already exists.") from exc
        return self.get_term(term_id)

    def list_terms(self, search: str = "") -> List[Dict[str, Any]]:
        with self._connect() as conn:
            if search.strip():
                pattern = f"%{search.strip()}%"
                rows = conn.execute(
                    """
                    SELECT * FROM glossary_terms
                    WHERE term LIKE ? OR definition LIKE ?
                    ORDER BY term COLLATE NOCASE
                    """,
                    (pattern, pattern),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM glossary_terms ORDER BY term COLLATE NOCASE"
                ).fetchall()
        return [self._row_to_term_dict(row) for row in rows]

    def get_term(self, term_id: int) -> Dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM glossary_terms WHERE id = ?",
                (term_id,),
            ).fetchone()
        if row is None:
            raise ValueError(f"Term {term_id} not found.")
        term = self._row_to_term_dict(row)
        term["mappings"] = self.list_mappings(term_id=term_id)
        return term

    def update_term(
        self,
        term_id: int,
        *,
        term: Optional[str] = None,
        definition: Optional[str] = None,
        examples: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM glossary_terms WHERE id = ?",
                (term_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"Term {term_id} not found.")

            new_term = term.strip() if isinstance(term, str) else row["term"]
            if not new_term:
                raise ValueError("Term must not be empty.")
            self._ensure_term_unique(new_term, exclude_term_id=term_id)

            new_definition = (
                definition.strip()
                if isinstance(definition, str)
                else row["definition"]
            )
            new_examples = (
                examples if isinstance(examples, list) else json.loads(row["examples_json"])
            )

            try:
                conn.execute(
                    """
                    UPDATE glossary_terms
                    SET term = ?, definition = ?, examples_json = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        new_term,
                        new_definition,
                        json.dumps(new_examples, ensure_ascii=False),
                        _utc_now(),
                        term_id,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError(f"Term '{new_term}' already exists.") from exc
        return self.get_term(term_id)

    def delete_term(self, term_id: int) -> None:
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM glossary_terms WHERE id = ?",
                (term_id,),
            )
        if cur.rowcount == 0:
            raise ValueError(f"Term {term_id} not found.")

    def add_mapping(
        self,
        *,
        term_id: int,
        database_name: str = "",
        dataset_name: str = "",
        schema_name: str = "",
        table_name: str = "",
        column_name: str = "",
        metric_name: str = "",
        notes: str = "",
    ) -> Dict[str, Any]:
        if not column_name.strip() and not metric_name.strip():
            raise ValueError("Provide at least column_name or metric_name.")

        with self._connect() as conn:
            term_row = conn.execute(
                "SELECT id FROM glossary_terms WHERE id = ?",
                (term_id,),
            ).fetchone()
            if term_row is None:
                raise ValueError(f"Term {term_id} not found.")

            cur = conn.execute(
                """
                INSERT INTO glossary_mappings(
                    term_id, database_name, dataset_name, schema_name,
                    table_name, column_name, metric_name, notes, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    term_id,
                    database_name.strip(),
                    dataset_name.strip(),
                    schema_name.strip(),
                    table_name.strip(),
                    column_name.strip(),
                    metric_name.strip(),
                    notes.strip(),
                    _utc_now(),
                ),
            )
            mapping_id = int(cur.lastrowid)
        return self.get_mapping(mapping_id)

    def list_mappings(self, term_id: Optional[int] = None) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            if term_id is None:
                rows = conn.execute(
                    """
                    SELECT m.*, t.term
                    FROM glossary_mappings m
                    JOIN glossary_terms t ON t.id = m.term_id
                    ORDER BY m.id DESC
                    """
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT m.*, t.term
                    FROM glossary_mappings m
                    JOIN glossary_terms t ON t.id = m.term_id
                    WHERE m.term_id = ?
                    ORDER BY m.id DESC
                    """,
                    (term_id,),
                ).fetchall()
        return [dict(row) for row in rows]

    def get_mapping(self, mapping_id: int) -> Dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT m.*, t.term
                FROM glossary_mappings m
                JOIN glossary_terms t ON t.id = m.term_id
                WHERE m.id = ?
                """,
                (mapping_id,),
            ).fetchone()
        if row is None:
            raise ValueError(f"Mapping {mapping_id} not found.")
        return dict(row)

    def delete_mapping(self, mapping_id: int) -> None:
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM glossary_mappings WHERE id = ?",
                (mapping_id,),
            )
        if cur.rowcount == 0:
            raise ValueError(f"Mapping {mapping_id} not found.")

    def build_agent_context(
        self, max_terms: int = 30, max_mappings: int = 100
    ) -> str:
        terms = self.list_terms()[:max_terms]
        if not terms:
            return ""

        sections: List[str] = [
            "Глоссарий бизнес-терминов (US2):",
        ]
        mapping_counter = 0
        for term in terms:
            examples = term.get("examples", [])
            examples_text = ", ".join(examples) if examples else "-"
            sections.append(
                f"- Термин: {term['term']}; Определение: {term['definition'] or '-'}; "
                f"Примеры: {examples_text}"
            )
            mappings = self.list_mappings(term_id=term["id"])
            for mapping in mappings:
                if mapping_counter >= max_mappings:
                    break
                target_parts = [
                    x
                    for x in [
                        mapping.get("database_name"),
                        mapping.get("dataset_name"),
                        mapping.get("schema_name"),
                        mapping.get("table_name"),
                        mapping.get("column_name"),
                        mapping.get("metric_name"),
                    ]
                    if x
                ]
                target = ".".join(target_parts) if target_parts else "-"
                sections.append(f"  -> Mapping: {target}")
                mapping_counter += 1
        return "\n".join(sections)

    @staticmethod
    def _row_to_term_dict(row: sqlite3.Row) -> Dict[str, Any]:
        payload = dict(row)
        payload["examples"] = json.loads(payload.pop("examples_json", "[]"))
        return payload

    def _ensure_term_unique(
        self, candidate_term: str, exclude_term_id: Optional[int] = None
    ) -> None:
        candidate_key = candidate_term.casefold()
        with self._connect() as conn:
            rows = conn.execute("SELECT id, term FROM glossary_terms").fetchall()
        for row in rows:
            row_id = int(row["id"])
            if exclude_term_id is not None and row_id == exclude_term_id:
                continue
            if str(row["term"]).casefold() == candidate_key:
                raise ValueError(f"Term '{candidate_term}' already exists.")


def get_glossary_service() -> GlossaryService:
    return GlossaryService()


__all__ = [
    "GlossaryService",
    "GlossaryTermInput",
    "get_glossary_service",
    "_parse_examples",
]
