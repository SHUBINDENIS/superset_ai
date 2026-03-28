"""
US1: Schema/Profile/Relations collector for PostgreSQL sources in Superset.

This module builds a metadata report that contains:
1) discovered schemas and tables,
2) basic table profiling (row counts, column metadata),
3) relations from FK constraints and simple heuristic inference.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from dotenv import load_dotenv

from backend.mcp_client.base import BaseProductMCPClient
from backend.mcp_client.runtime import ProductMCPRuntime, create_product_mcp_runtime


load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def _quote_ident(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _quote_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _extract_result_items(payload: Dict[str, Any]) -> List[Any]:
    if not isinstance(payload, dict):
        return []

    result = payload.get("result")
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        nested = result.get("result")
        if isinstance(nested, list):
            return nested
    return []


def _extract_rows(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not isinstance(payload, dict):
        return []

    candidates: List[Any] = [
        payload.get("data"),
        payload.get("result"),
    ]

    result = payload.get("result")
    if isinstance(result, dict):
        candidates.append(result.get("data"))
        candidates.append(result.get("result"))
    elif isinstance(result, list) and result:
        first = result[0]
        if isinstance(first, dict):
            candidates.append(first.get("data"))

    for candidate in candidates:
        if isinstance(candidate, list) and all(isinstance(x, dict) for x in candidate):
            return candidate

    return []


def _is_postgres_backend(record: Dict[str, Any]) -> bool:
    return "postgres" in _detect_backend_hint(record).lower()


def _extract_db_id(record: Dict[str, Any]) -> Optional[int]:
    for key in ("id", "database_id", "value"):
        value = record.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return None


def _extract_db_name(record: Dict[str, Any], db_id: int) -> str:
    for key in ("database_name", "name", "label", "value"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return f"db_{db_id}"


def _detect_backend_hint(record: Dict[str, Any]) -> str:
    direct_str_keys = [
        "backend",
        "engine",
        "database_backend",
        "db_engine_spec",
        "dialect",
    ]
    for key in direct_str_keys:
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    uri_keys = ["sqlalchemy_uri", "masked_sqlalchemy_uri"]
    for key in uri_keys:
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            uri = value.strip()
            if "://" in uri:
                return uri.split("://", 1)[0]
            return uri

    nested_keys = ["parameters", "extra", "extra_json"]
    for key in nested_keys:
        value = record.get(key)
        if isinstance(value, dict):
            nested_hint = _detect_backend_hint(value)
            if nested_hint != "unknown":
                return nested_hint
        elif isinstance(value, str) and value.strip():
            try:
                parsed = json.loads(value)
                if isinstance(parsed, dict):
                    nested_hint = _detect_backend_hint(parsed)
                    if nested_hint != "unknown":
                        return nested_hint
            except Exception:
                pass

    serialized = json.dumps(record, ensure_ascii=False, default=str).lower()
    known_backends = [
        "postgresql",
        "postgres",
        "clickhouse",
        "mysql",
        "sqlite",
        "bigquery",
        "trino",
        "presto",
        "snowflake",
    ]
    for backend in known_backends:
        if backend in serialized:
            return backend

    return "unknown"


def _normalize_schemas(payload: Dict[str, Any]) -> List[str]:
    raw = _extract_result_items(payload)
    schemas: List[str] = []
    for item in raw:
        if isinstance(item, str):
            schemas.append(item)
        elif isinstance(item, dict):
            for key in ("value", "schema", "name"):
                value = item.get(key)
                if isinstance(value, str) and value:
                    schemas.append(value)
                    break
    unique = sorted({x for x in schemas if x})
    return unique


def _normalize_tables(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw = _extract_result_items(payload)
    tables: List[Dict[str, Any]] = []

    for item in raw:
        if isinstance(item, str):
            if "." in item:
                schema, table = item.split(".", 1)
            else:
                schema, table = "public", item
            tables.append({"schema": schema, "table": table})
            continue

        if not isinstance(item, dict):
            continue

        table_name = (
            item.get("table")
            or item.get("table_name")
            or item.get("value")
            or item.get("name")
        )
        if not isinstance(table_name, str) or not table_name:
            continue

        schema_name = (
            item.get("schema")
            or item.get("table_schema")
            or item.get("schema_name")
            or "public"
        )
        if not isinstance(schema_name, str) or not schema_name:
            schema_name = "public"

        tables.append(
            {
                "schema": schema_name,
                "table": table_name,
                "raw": item,
            }
        )

    dedup_keyed = {(x["schema"], x["table"]): x for x in tables}
    return list(dedup_keyed.values())


def _build_schema_query_rison(schema_name: str, force: bool = False) -> str:
    safe_schema = schema_name.replace("'", "\\'")
    force_flag = "true" if force else "false"
    return f"(schema_name:'{safe_schema}',force:{force_flag})"


def _build_heuristic_relations(
    columns_by_table: Dict[Tuple[str, str], Set[str]],
    fk_keys: Set[Tuple[str, str, str, str, str, str]],
) -> List[Dict[str, str]]:
    known_fk = set(fk_keys)
    relations: List[Dict[str, str]] = []
    table_map = {(schema, table): cols for (schema, table), cols in columns_by_table.items()}

    for (source_schema, source_table), source_cols in table_map.items():
        for column_name in source_cols:
            lower = column_name.lower()
            if not lower.endswith("_id"):
                continue

            base = lower[:-3]
            candidates = [base, f"{base}s", f"{base}es"]

            target: Optional[Tuple[str, str]] = None
            for candidate_table in candidates:
                probe = (source_schema, candidate_table)
                if probe in table_map and "id" in table_map[probe]:
                    target = probe
                    break

            if target is None:
                continue

            target_schema, target_table = target
            relation_key = (
                source_schema,
                source_table,
                column_name,
                target_schema,
                target_table,
                "id",
            )
            if relation_key in known_fk:
                continue

            relations.append(
                {
                    "source_schema": source_schema,
                    "source_table": source_table,
                    "source_column": column_name,
                    "target_schema": target_schema,
                    "target_table": target_table,
                    "target_column": "id",
                    "relation_type": "heuristic",
                    "confidence": "medium",
                }
            )

    return relations


@dataclass
class SupersetUS1SchemaProfiler:
    base_url: str
    timeout_seconds: float = 30.0
    max_tables_per_db: int = 120

    def __post_init__(self) -> None:
        self.base_url = self.base_url.rstrip("/")
        self._mcp_runtime: ProductMCPRuntime | None = None

    @classmethod
    def from_env(cls) -> "SupersetUS1SchemaProfiler":
        base_url = os.getenv("SUPERSET_BASE_URL", "http://localhost:8088")
        max_tables = int(os.getenv("US1_MAX_TABLES_PER_DB", "120"))
        timeout = float(os.getenv("US1_TIMEOUT_SECONDS", "30"))
        return cls(
            base_url=base_url,
            timeout_seconds=timeout,
            max_tables_per_db=max_tables,
        )

    async def close(self) -> None:
        if self._mcp_runtime is not None:
            await self._mcp_runtime.close()
            self._mcp_runtime = None

    async def _ensure_product_client(self) -> BaseProductMCPClient:
        if self._mcp_runtime is None:
            self._mcp_runtime = await create_product_mcp_runtime(
                fallback_runtime="none"
            )
        return self._mcp_runtime.product_client

    async def _call_product_client(
        self, method_name: str, request: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        product_client = await self._ensure_product_client()
        method = getattr(product_client, method_name)
        if request is None:
            response = await method()
        else:
            response = await method(dict(request))
        return dict(response or {})

    def _query_timeout_seconds(self) -> int:
        return max(1, min(int(self.timeout_seconds), 300))

    async def _list_accessible_databases(self) -> List[Dict[str, Any]]:
        databases: List[Dict[str, Any]] = []
        page = 1
        page_size = 1000

        while True:
            payload = await self._call_product_client(
                "list_databases",
                {
                    "page": page,
                    "page_size": page_size,
                },
            )
            items = [
                item
                for item in list(payload.get("databases", []) or [])
                if isinstance(item, dict)
            ]
            databases.extend(items)
            total_count = int(payload.get("total_count", len(databases)) or 0)
            if not items or len(databases) >= total_count or len(items) < page_size:
                break
            page += 1

        return databases

    async def _sql_query(
        self,
        database_id: int,
        sql: str,
        schema: str = "",
    ) -> List[Dict[str, Any]]:
        payload: Dict[str, Any] = {
            "database_id": database_id,
            "sql": sql,
            "limit": 10000,
            "timeout": self._query_timeout_seconds(),
        }
        if schema:
            payload["schema"] = schema
        result = await self._call_product_client("execute_sql", payload)
        if result.get("success") is False:
            error_text = str(
                result.get("error")
                or result.get("message")
                or "execute_sql returned success=false"
            ).strip()
            raise RuntimeError(error_text)
        rows = result.get("rows")
        if not isinstance(rows, list):
            return []
        return [dict(row) for row in rows if isinstance(row, dict)]

    async def _load_database_schemas(self, database_id: int) -> List[str]:
        rows = await self._sql_query(
            database_id=database_id,
            sql="""
                SELECT schema_name
                FROM information_schema.schemata
                WHERE schema_name <> 'information_schema'
                  AND schema_name NOT LIKE 'pg_%'
                ORDER BY schema_name
            """,
        )
        schemas = sorted(
            {
                schema_name
                for row in rows
                for schema_name in [
                    str(row.get("schema_name") or row.get("schema") or "").strip()
                ]
                if schema_name
                and schema_name != "information_schema"
                and not schema_name.startswith("pg_")
            }
        )
        return schemas or ["public"]

    async def _load_table_columns(
        self, database_id: int, schema_name: str, table_name: str
    ) -> List[Dict[str, Any]]:
        sql = f"""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = {_quote_literal(schema_name)}
              AND table_name = {_quote_literal(table_name)}
            ORDER BY ordinal_position
        """
        return await self._sql_query(database_id=database_id, sql=sql, schema=schema_name)

    async def _load_table_row_count(
        self, database_id: int, schema_name: str, table_name: str
    ) -> Optional[int]:
        sql = (
            f"SELECT COUNT(*) AS row_count FROM "
            f"{_quote_ident(schema_name)}.{_quote_ident(table_name)}"
        )
        rows = await self._sql_query(database_id=database_id, sql=sql, schema=schema_name)
        if not rows:
            return None
        value = rows[0].get("row_count")
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    async def _load_fk_relations(self, database_id: int) -> List[Dict[str, Any]]:
        sql = """
            SELECT
                tc.table_schema AS source_schema,
                tc.table_name AS source_table,
                kcu.column_name AS source_column,
                ccu.table_schema AS target_schema,
                ccu.table_name AS target_table,
                ccu.column_name AS target_column,
                tc.constraint_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage ccu
              ON ccu.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
            ORDER BY 1, 2, 3
        """
        return await self._sql_query(database_id=database_id, sql=sql)

    async def _load_tables_for_schema(
        self, database_id: int, schema_name: str
    ) -> List[Dict[str, Any]]:
        sql = f"""
            SELECT table_schema AS schema, table_name AS table
            FROM information_schema.tables
            WHERE table_schema = {_quote_literal(schema_name)}
              AND table_type IN ('BASE TABLE', 'VIEW')
            ORDER BY table_name
        """
        rows = await self._sql_query(database_id=database_id, sql=sql, schema=schema_name)
        tables: List[Dict[str, Any]] = []
        for row in rows:
            schema = str(row.get("schema") or schema_name)
            table = str(row.get("table") or row.get("table_name") or "")
            if table:
                tables.append({"schema": schema, "table": table})
        dedup_keyed = {(x["schema"], x["table"]): x for x in tables}
        return list(dedup_keyed.values())

    async def build_report(self) -> Dict[str, Any]:
        db_items = await self._list_accessible_databases()

        scan_only_postgres = (
            os.getenv("US1_ONLY_POSTGRES", "true").strip().lower()
            in {"1", "true", "yes", "y", "on"}
        )

        database_candidates: List[Dict[str, Any]] = []
        selected_dbs: List[Dict[str, Any]] = []

        for db in db_items:
            db_id = _extract_db_id(db)
            if db_id is None:
                continue

            db_name = _extract_db_name(db, db_id)
            backend_hint = _detect_backend_hint(db)
            backend_source = "mcp_ext.list_databases"

            is_postgres = "postgres" in backend_hint.lower()
            candidate = {
                "database_id": db_id,
                "database_name": db_name,
                "backend_hint": backend_hint,
                "backend_source": backend_source,
                "is_postgres": is_postgres,
            }
            database_candidates.append(candidate)

            if (scan_only_postgres and is_postgres) or (not scan_only_postgres):
                selected_dbs.append(
                    {
                        "id": db_id,
                        "database_name": db_name,
                        "backend": backend_hint,
                    }
                )

        report_databases: List[Dict[str, Any]] = []
        total_tables = 0
        total_relations = 0

        for db in selected_dbs:
            db_id = int(db["id"])
            db_name = str(db.get("database_name") or f"db_{db_id}")
            backend = str(db.get("backend") or "unknown")

            schemas = await self._load_database_schemas(db_id)

            tables: List[Dict[str, Any]] = []
            table_errors: List[Dict[str, str]] = []
            for schema_name in schemas:
                try:
                    schema_tables = await self._load_tables_for_schema(db_id, schema_name)
                    tables.extend(schema_tables)
                except Exception as exc:
                    table_errors.append(
                        {
                            "schema": schema_name,
                            "error": f"tables_fetch_failed: {exc}",
                        }
                    )

            if table_errors:
                # Keep non-fatal errors in report for troubleshooting.
                db.setdefault("diagnostics", {})
                db["diagnostics"]["tables_fetch_errors"] = table_errors

            if self.max_tables_per_db > 0:
                tables = tables[: self.max_tables_per_db]

            columns_by_table: Dict[Tuple[str, str], Set[str]] = {}
            profiled_tables: List[Dict[str, Any]] = []

            for table in tables:
                schema_name = table["schema"]
                table_name = table["table"]

                try:
                    column_rows = await self._load_table_columns(db_id, schema_name, table_name)
                except Exception as exc:
                    profiled_tables.append(
                        {
                            "schema": schema_name,
                            "table": table_name,
                            "error": f"column_profile_failed: {exc}",
                        }
                    )
                    continue

                column_names = {
                    str(row.get("column_name", "")).lower()
                    for row in column_rows
                    if row.get("column_name")
                }
                columns_by_table[(schema_name, table_name)] = column_names

                try:
                    row_count = await self._load_table_row_count(db_id, schema_name, table_name)
                except Exception:
                    row_count = None

                profiled_tables.append(
                    {
                        "schema": schema_name,
                        "table": table_name,
                        "row_count": row_count,
                        "columns": column_rows,
                        "column_count": len(column_rows),
                    }
                )

            fk_rows = []
            try:
                fk_rows = await self._load_fk_relations(db_id)
            except Exception:
                fk_rows = []

            fk_relations: List[Dict[str, Any]] = []
            fk_relation_keys: Set[Tuple[str, str, str, str, str, str]] = set()
            for row in fk_rows:
                relation = {
                    "source_schema": str(row.get("source_schema", "")),
                    "source_table": str(row.get("source_table", "")),
                    "source_column": str(row.get("source_column", "")),
                    "target_schema": str(row.get("target_schema", "")),
                    "target_table": str(row.get("target_table", "")),
                    "target_column": str(row.get("target_column", "")),
                    "constraint_name": str(row.get("constraint_name", "")),
                    "relation_type": "foreign_key",
                    "confidence": "high",
                }
                if not relation["source_table"] or not relation["target_table"]:
                    continue
                key = (
                    relation["source_schema"],
                    relation["source_table"],
                    relation["source_column"],
                    relation["target_schema"],
                    relation["target_table"],
                    relation["target_column"],
                )
                fk_relation_keys.add(key)
                fk_relations.append(relation)

            heuristic_relations = _build_heuristic_relations(columns_by_table, fk_relation_keys)

            db_report = {
                "database_id": db_id,
                "database_name": db_name,
                "backend": backend,
                "schemas": schemas,
                "tables_profiled": profiled_tables,
                "relations": {
                    "foreign_keys": fk_relations,
                    "heuristic": heuristic_relations,
                },
            }
            diagnostics = db.get("diagnostics")
            if diagnostics:
                db_report["diagnostics"] = diagnostics
            report_databases.append(db_report)
            total_tables += len(profiled_tables)
            total_relations += len(fk_relations) + len(heuristic_relations)

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "superset_base_url": self.base_url,
            "scan_config": {
                "scan_only_postgres": scan_only_postgres,
                "max_tables_per_db": self.max_tables_per_db,
                "timeout_seconds": self.timeout_seconds,
            },
            "database_candidates": database_candidates,
            "postgres_databases": report_databases,
            "summary": {
                "database_candidates_count": len(database_candidates),
                "postgres_candidates_count": sum(
                    1 for candidate in database_candidates if candidate.get("is_postgres")
                ),
                "selected_databases_count": len(selected_dbs),
                "postgres_databases_count": len(report_databases),
                "tables_profiled_count": total_tables,
                "relations_detected_count": total_relations,
            },
        }

    async def build_and_save_report(
        self, output_dir: Optional[Path] = None
    ) -> Dict[str, Any]:
        report = await self.build_report()
        target_dir = output_dir or (
            Path(__file__).resolve().parent.parent / "artifacts" / "us1"
        )
        target_dir.mkdir(parents=True, exist_ok=True)

        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")
        report_path = target_dir / f"us1_schema_profile_relations_{stamp}.json"
        with report_path.open("w", encoding="utf-8") as fp:
            json.dump(report, fp, ensure_ascii=False, indent=2)

        return {
            "report_path": str(report_path),
            "summary": report["summary"],
            "report": report,
        }


async def run_us1_scan_from_env() -> Dict[str, Any]:
    profiler = SupersetUS1SchemaProfiler.from_env()
    try:
        return await profiler.build_and_save_report()
    finally:
        await profiler.close()


if __name__ == "__main__":
    import asyncio

    try:
        result = asyncio.run(run_us1_scan_from_env())
        print(json.dumps(result["summary"], ensure_ascii=False))
        print(result["report_path"])
    except Exception as exc:
        print(f"US1 scan failed: {exc}")
