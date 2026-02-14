"""
US4: Query examples (RU) + glossary-driven entity autocomplete.
"""

from __future__ import annotations

from datetime import datetime
import re
from typing import Any, Dict, List, Optional

from .us2_glossary_service import GlossaryService, get_glossary_service


DEFAULT_US4_EXAMPLES: List[Dict[str, Any]] = [
    {
        "id": "sales_monthly",
        "title": "Выручка по месяцам",
        "description": "Показать динамику выручки по месяцам за выбранный период.",
        "query": "Покажи выручку по месяцам за 2025 год.",
        "tags": ["выручка", "месяц", "динамика", "продажи"],
    },
    {
        "id": "sales_regions",
        "title": "Продажи по регионам",
        "description": "Сравнить продажи между регионами и выделить лидеров.",
        "query": "Покажи топ-10 регионов по продажам за последний квартал.",
        "tags": ["регионы", "продажи", "top-n"],
    },
    {
        "id": "avg_check_segment",
        "title": "Средний чек по сегментам",
        "description": "Сравнить средний чек между сегментами клиентов.",
        "query": "Сравни средний чек по сегментам клиентов за текущий месяц.",
        "tags": ["средний чек", "сегмент", "клиенты"],
    },
    {
        "id": "conversion_funnel",
        "title": "Конверсия по воронке",
        "description": "Показать конверсию между этапами воронки продаж.",
        "query": "Покажи конверсию между этапами воронки по неделям.",
        "tags": ["конверсия", "воронка", "неделя"],
    },
    {
        "id": "retention_cohort",
        "title": "Удержание пользователей",
        "description": "Построить когортный анализ удержания пользователей.",
        "query": "Покажи retention пользователей по когортам регистрации.",
        "tags": ["retention", "когорты", "пользователи"],
    },
    {
        "id": "new_users_daily",
        "title": "Новые пользователи",
        "description": "Показать приток новых пользователей по дням.",
        "query": "Сколько новых пользователей было каждый день за последние 30 дней?",
        "tags": ["новые пользователи", "дни", "прирост"],
    },
    {
        "id": "active_users_weekly",
        "title": "Активные пользователи",
        "description": "Отобразить WAU/MAU для оценки вовлеченности.",
        "query": "Покажи weekly active users и monthly active users за 3 месяца.",
        "tags": ["wau", "mau", "активность"],
    },
    {
        "id": "refund_rate",
        "title": "Доля возвратов",
        "description": "Рассчитать долю возвратов по категориям товаров.",
        "query": "Покажи долю возвратов по категориям товаров за полугодие.",
        "tags": ["возвраты", "категории", "доля"],
    },
    {
        "id": "margin_by_product",
        "title": "Маржинальность товаров",
        "description": "Сравнить валовую маржу по товарным группам.",
        "query": "Сравни маржинальность по товарным группам за Q4 2025.",
        "tags": ["маржа", "товары", "группы"],
    },
    {
        "id": "nps_trend",
        "title": "Динамика NPS",
        "description": "Показать тренд NPS и сегментацию по каналам.",
        "query": "Покажи динамику NPS по каналам обслуживания.",
        "tags": ["nps", "каналы", "динамика"],
    },
    {
        "id": "orders_anomaly",
        "title": "Аномалии в заказах",
        "description": "Найти дни с аномальными всплесками или падениями заказов.",
        "query": "Найди аномалии по количеству заказов за последние 90 дней.",
        "tags": ["аномалии", "заказы", "всплеск"],
    },
    {
        "id": "plan_vs_fact",
        "title": "План-факт",
        "description": "Сравнить фактические показатели с планом по месяцам.",
        "query": "Сделай план-факт по выручке по месяцам за 2025 год.",
        "tags": ["план-факт", "выручка", "месяц"],
    },
]


_LAST_TOKEN_RE = re.compile(r"([0-9A-Za-z_А-Яа-яЁё]+)$")
_WORD_RE = re.compile(r"[0-9A-Za-z_А-Яа-яЁё]{2,}")


def _quote_ident(value: str) -> str:
    return '"' + str(value).replace('"', '""') + '"'


def _contains_any(name: str, keywords: List[str]) -> bool:
    token = name.casefold()
    return any(keyword in token for keyword in keywords)


def _is_identifier_column(name: str) -> bool:
    token = name.casefold()
    return bool(
        token == "id"
        or token.endswith("_id")
        or token.endswith("id")
        or "uuid" in token
        or token.endswith("_key")
        or token.endswith("key")
    )


def _metric_score(name: str) -> int:
    token = name.casefold()
    score = 0
    weighted_patterns = [
        ("выруч", 120),
        ("revenue", 120),
        ("sales", 110),
        ("gmv", 110),
        ("profit", 100),
        ("марж", 90),
        ("margin", 90),
        ("amount", 90),
        ("price", 80),
        ("cost", 70),
        ("income", 70),
        ("qty", 55),
        ("quantity", 55),
        ("count", 50),
    ]
    for pattern, weight in weighted_patterns:
        if pattern in token:
            score = max(score, weight)
    if _is_identifier_column(name):
        score -= 80
    return score


def _time_score(name: str) -> int:
    token = name.casefold()
    weighted_patterns = [
        ("date", 120),
        ("дат", 120),
        ("time", 110),
        ("врем", 110),
        ("created", 100),
        ("updated", 90),
        ("month", 90),
        ("day", 85),
        ("year", 80),
    ]
    score = 0
    for pattern, weight in weighted_patterns:
        if pattern in token:
            score = max(score, weight)
    return score


def _dimension_score(name: str, distinct_count: int) -> int:
    token = name.casefold()
    score = 0
    weighted_patterns = [
        ("region", 120),
        ("регион", 120),
        ("country", 110),
        ("city", 105),
        ("channel", 100),
        ("канал", 100),
        ("segment", 95),
        ("сегмент", 95),
        ("category", 95),
        ("категор", 95),
        ("product", 90),
        ("товар", 90),
        ("brand", 85),
        ("status", 80),
        ("stage", 80),
        ("source", 80),
        ("customer", 75),
        ("client", 75),
        ("user", 75),
    ]
    for pattern, weight in weighted_patterns:
        if pattern in token:
            score = max(score, weight)

    if _is_identifier_column(name):
        score -= 120
    if distinct_count <= 1:
        score -= 40
    elif 2 <= distinct_count <= 50:
        score += 25
    elif 51 <= distinct_count <= 300:
        score += 10
    elif distinct_count > 2000:
        score -= 10
    return score


def _humanize_column(name: str) -> str:
    token = str(name or "").strip()
    if not token:
        return "показателю"
    return token.replace("_", " ")


def _dimension_label(name: str) -> str:
    token = name.casefold()
    if _contains_any(token, ["region", "регион", "country", "city"]):
        return "географиям"
    if _contains_any(token, ["channel", "канал", "source"]):
        return "каналам"
    if _contains_any(token, ["segment", "сегмент"]):
        return "сегментам"
    if _contains_any(token, ["category", "категор", "product", "товар", "brand"]):
        return "категориям"
    if _contains_any(token, ["customer", "client", "user"]):
        return "клиентским группам"
    if _contains_any(token, ["status", "stage"]):
        return "статусам"
    return f"группам ({_humanize_column(name)})"


def _try_parse_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    token = str(value).strip()
    if not token:
        return None
    normalized = token.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        pass
    for pattern in (
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d",
    ):
        try:
            return datetime.strptime(token, pattern)
        except ValueError:
            continue
    return None


def _to_float(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    token = str(value).strip().replace(" ", "").replace(",", ".")
    if not token:
        return None
    if not re.fullmatch(r"[-+]?\d+(?:\.\d+)?", token):
        return None
    try:
        return float(token)
    except Exception:
        return None


def _collect_sample_values(values: List[Any], limit: int = 3) -> List[str]:
    result: List[str] = []
    seen = set()
    for value in values:
        token = str(value).strip()
        if not token:
            continue
        key = token.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(token)
        if len(result) >= max(1, int(limit)):
            break
    return result


class US4QueryAssistantService:
    def __init__(
        self,
        glossary_service: Optional[GlossaryService] = None,
        examples: Optional[List[Dict[str, Any]]] = None,
    ):
        self.glossary = glossary_service or get_glossary_service()
        self.examples = list(examples or DEFAULT_US4_EXAMPLES)

    def list_examples(self, search: str = "", limit: int = 50) -> List[Dict[str, Any]]:
        items = self.examples
        if search.strip():
            needles = [x.casefold() for x in _WORD_RE.findall(search)]
            if needles:
                filtered: List[Dict[str, Any]] = []
                for item in items:
                    hay = " ".join(
                        [
                            str(item.get("title", "")),
                            str(item.get("description", "")),
                            str(item.get("query", "")),
                            " ".join(item.get("tags", [])),
                        ]
                    ).casefold()
                    if all(needle in hay for needle in needles):
                        filtered.append(item)
                items = filtered
        return items[: max(int(limit), 0)]

    @staticmethod
    def _mapping_matches_scope(
        mapping: Dict[str, Any],
        *,
        preferred_database: str = "",
        preferred_table: str = "",
    ) -> bool:
        db_scope = preferred_database.strip().casefold()
        table_scope = preferred_table.strip().casefold()
        if not db_scope and not table_scope:
            return True

        mapping_db = str(mapping.get("database_name", "")).strip().casefold()
        mapping_table = str(mapping.get("table_name", "")).strip().casefold()
        mapping_schema = str(mapping.get("schema_name", "")).strip().casefold()
        full_table = ".".join(
            [token for token in (mapping_schema, mapping_table) if token]
        )

        db_ok = (not db_scope) or (mapping_db == db_scope)
        table_ok = (not table_scope) or (
            table_scope in {mapping_table, full_table}
        )
        return db_ok and table_ok

    def get_dictionary_entities(
        self,
        limit: int = 500,
        *,
        preferred_database: str = "",
        preferred_table: str = "",
    ) -> List[str]:
        ordered_unique: Dict[str, str] = {}

        terms = self.glossary.list_terms()
        for term in terms:
            self._add_entity(ordered_unique, term.get("term", ""))
            for example in term.get("examples", []):
                self._add_entity(ordered_unique, example)

        mappings = self.glossary.list_mappings()
        for mapping in mappings:
            if not self._mapping_matches_scope(
                mapping,
                preferred_database=preferred_database,
                preferred_table=preferred_table,
            ):
                continue
            for key in (
                "database_name",
                "dataset_name",
                "schema_name",
                "table_name",
                "column_name",
                "metric_name",
            ):
                self._add_entity(ordered_unique, mapping.get(key, ""))

        for example in self.examples:
            for tag in example.get("tags", []):
                self._add_entity(ordered_unique, tag)

        entities = list(ordered_unique.values())
        if preferred_database.strip():
            self._add_entity(ordered_unique, preferred_database)
            entities = list(ordered_unique.values())
        if preferred_table.strip():
            self._add_entity(ordered_unique, preferred_table)
            entities = list(ordered_unique.values())
        entities.sort(key=lambda x: x.casefold())
        return entities[: max(int(limit), 0)]

    def suggest_entities(
        self,
        prefix: str = "",
        limit: int = 12,
        *,
        preferred_database: str = "",
        preferred_table: str = "",
    ) -> List[str]:
        entities = self.get_dictionary_entities(
            limit=1000,
            preferred_database=preferred_database,
            preferred_table=preferred_table,
        )
        normalized_prefix = prefix.strip().casefold()
        if not normalized_prefix:
            return entities[: max(int(limit), 0)]

        starts = [
            entity for entity in entities if entity.casefold().startswith(normalized_prefix)
        ]
        contains = [
            entity
            for entity in entities
            if normalized_prefix in entity.casefold() and entity not in starts
        ]
        return (starts + contains)[: max(int(limit), 0)]

    def suggest_entities_for_query(
        self,
        query_text: str,
        limit: int = 12,
        *,
        preferred_database: str = "",
        preferred_table: str = "",
    ) -> List[str]:
        last_token = self.extract_last_token(query_text)
        return self.suggest_entities(
            prefix=last_token,
            limit=limit,
            preferred_database=preferred_database,
            preferred_table=preferred_table,
        )

    def select_examples_for_query(
        self,
        query_text: str,
        max_examples: int = 5,
        *,
        preferred_database: str = "",
        preferred_table: str = "",
    ) -> List[Dict[str, Any]]:
        query_tokens = {x.casefold() for x in _WORD_RE.findall(query_text)}
        scope_tokens = {
            x.casefold()
            for x in _WORD_RE.findall(
                " ".join([preferred_database.strip(), preferred_table.strip()])
            )
        }
        all_tokens = query_tokens | scope_tokens
        if not all_tokens:
            return self.examples[: max(int(max_examples), 0)]

        scored: List[tuple[int, Dict[str, Any]]] = []
        for item in self.examples:
            blob = " ".join(
                [
                    str(item.get("title", "")),
                    str(item.get("description", "")),
                    str(item.get("query", "")),
                    " ".join(item.get("tags", [])),
                ]
            ).casefold()
            score = sum(1 for token in all_tokens if token in blob)
            if score > 0:
                scored.append((score, item))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        picked = [item for _, item in scored]
        if not picked:
            picked = self.examples
        return picked[: max(int(max_examples), 0)]

    def build_agent_context_for_query(
        self,
        query_text: str,
        *,
        max_examples: int = 4,
        max_entities: int = 10,
        preferred_database: str = "",
        preferred_table: str = "",
    ) -> str:
        examples = self.select_examples_for_query(
            query_text,
            max_examples=max_examples,
            preferred_database=preferred_database,
            preferred_table=preferred_table,
        )
        entities = self.suggest_entities_for_query(
            query_text,
            limit=max_entities,
            preferred_database=preferred_database,
            preferred_table=preferred_table,
        )

        lines: List[str] = []
        if preferred_database.strip() or preferred_table.strip():
            lines.append("US4 выбранный scope:")
            lines.append(
                f"- database={preferred_database.strip() or '-'}; "
                f"table={preferred_table.strip() or '-'}"
            )
        if examples:
            lines.append("US4 примеры запросов (русский язык):")
            for ex in examples:
                lines.append(
                    f"- {ex.get('title', 'Пример')}: {ex.get('query', '')} "
                    f"(описание: {ex.get('description', '-')})"
                )

        if entities:
            lines.append("US4 автодополнение сущностей из глоссария:")
            lines.append("- " + ", ".join(entities))

        if lines:
            lines.append(
                "Используй примеры и сущности как подсказки формулировки, "
                "не искажай фактические поля/метрики."
            )
        return "\n".join(lines)

    def generate_table_sql_candidates(
        self,
        *,
        table_name: str,
        schema_name: str = "",
        columns: Optional[List[Dict[str, Any]]] = None,
        sample_rows: Optional[List[Dict[str, Any]]] = None,
        max_candidates: int = 8,
    ) -> List[Dict[str, str]]:
        safe_table = _normalize_table_name(table_name)
        safe_schema = _normalize_table_name(schema_name)
        if not safe_table:
            return []

        table_ref = (
            f"{_quote_ident(safe_schema)}.{_quote_ident(safe_table)}"
            if safe_schema
            else _quote_ident(safe_table)
        )

        cols = [x for x in (columns or []) if isinstance(x, dict)]
        profile_map: Dict[str, Dict[str, Any]] = {}
        for item in cols:
            col_name = str(item.get("column", "")).strip()
            if not col_name:
                continue
            profile_map[col_name] = {
                "name": col_name,
                "inferred_type": str(item.get("inferred_type", "")).strip(),
                "non_null_count": int(item.get("non_null_count", 0) or 0),
                "distinct_count": int(item.get("distinct_count", 0) or 0),
            }

        sample_map: Dict[str, List[Any]] = {}
        if sample_rows:
            for row in sample_rows:
                if not isinstance(row, dict):
                    continue
                for key, value in row.items():
                    sample_map.setdefault(str(key).strip(), []).append(value)
            for col_name, values in sample_map.items():
                if not col_name:
                    continue
                values_non_null = [v for v in values if v is not None and str(v).strip() != ""]
                if not values_non_null:
                    continue
                profile = profile_map.get(
                    col_name,
                    {
                        "name": col_name,
                        "inferred_type": "",
                        "non_null_count": 0,
                        "distinct_count": 0,
                    },
                )
                if not profile.get("non_null_count"):
                    profile["non_null_count"] = len(values_non_null)
                if not profile.get("distinct_count"):
                    profile["distinct_count"] = len({str(v) for v in values_non_null})

                inferred = str(profile.get("inferred_type", "")).strip()
                if not inferred and all(_to_float(v) is not None for v in values_non_null):
                    inferred = "numeric"
                if not inferred and any(_try_parse_datetime(v) for v in values_non_null):
                    inferred = "temporal"
                if not inferred:
                    inferred = "text"
                profile["inferred_type"] = inferred
                profile_map[col_name] = profile

        profiles = list(profile_map.values())
        numeric_cols = [
            str(p["name"])
            for p in profiles
            if str(p.get("inferred_type", "")).strip() == "numeric"
            and int(p.get("non_null_count", 0) or 0) > 0
        ]
        temporal_cols = [
            str(p["name"])
            for p in profiles
            if str(p.get("inferred_type", "")).strip() == "temporal"
            and int(p.get("non_null_count", 0) or 0) > 0
        ]
        category_cols = [
            str(p["name"])
            for p in profiles
            if str(p.get("inferred_type", "")).strip() in {"text", "boolean"}
            and int(p.get("non_null_count", 0) or 0) > 0
        ]

        numeric_cols = sorted(
            numeric_cols,
            key=lambda c: (
                _is_identifier_column(c),
                -_metric_score(c),
                c.casefold(),
            ),
        )
        temporal_cols = sorted(
            temporal_cols,
            key=lambda c: (-_time_score(c), c.casefold()),
        )
        category_cols = sorted(
            category_cols,
            key=lambda c: (
                -_dimension_score(
                    c, int(profile_map.get(c, {}).get("distinct_count", 0) or 0)
                ),
                c.casefold(),
            ),
        )

        primary_metric = numeric_cols[0] if numeric_cols else ""
        primary_time = temporal_cols[0] if temporal_cols else ""
        primary_dimension = category_cols[0] if category_cols else ""

        metric_sample_values = sample_map.get(primary_metric, [])
        metric_numeric_values = [
            x for x in (_to_float(v) for v in metric_sample_values) if x is not None
        ]
        metric_hint = ""
        if metric_numeric_values:
            min_value = min(metric_numeric_values)
            max_value = max(metric_numeric_values)

            def _fmt_number(value: float) -> str:
                if abs(value - round(value)) < 0.000001:
                    return str(int(round(value)))
                return f"{value:.2f}"

            metric_hint = (
                f" По срезу данных диапазон метрики: {_fmt_number(min_value)}.."
                f"{_fmt_number(max_value)}."
            )

        dimension_examples = _collect_sample_values(
            sample_map.get(primary_dimension, []),
            limit=3,
        )
        dimension_hint = ""
        if dimension_examples:
            dimension_hint = (
                " Примеры сегментов в выборке: "
                + ", ".join(dimension_examples)
                + "."
            )

        time_values = [
            value
            for value in (_try_parse_datetime(v) for v in sample_map.get(primary_time, []))
            if value is not None
        ]
        time_hint = ""
        if time_values:
            min_ts = min(time_values).date().isoformat()
            max_ts = max(time_values).date().isoformat()
            time_hint = f" По срезу данных период: {min_ts}..{max_ts}."

        candidates: List[Dict[str, str]] = []

        def _append(title: str, description: str, sql: str) -> None:
            candidates.append({"title": title, "description": description, "sql": sql.strip()})

        if primary_metric:
            metric_q = _quote_ident(primary_metric)
            metric_label = _humanize_column(primary_metric)
            _append(
                f"KPI по {metric_label}",
                (
                    "Базовый управленческий срез: объем, среднее и экстремумы "
                    f"выбранной метрики.{metric_hint}"
                ),
                (
                    "SELECT\n"
                    "  COUNT(*) AS rows_total,\n"
                    "  SUM({metric}) AS metric_total,\n"
                    "  AVG({metric}) AS metric_avg,\n"
                    "  MIN({metric}) AS metric_min,\n"
                    "  MAX({metric}) AS metric_max\n"
                    "FROM {table}"
                ).format(metric=metric_q, table=table_ref),
            )
        else:
            _append(
                "KPI по объему данных",
                "Оперативная проверка объема данных в таблице.",
                f"SELECT COUNT(*) AS rows_total\nFROM {table_ref}",
            )

        if primary_dimension and primary_metric:
            dim_q = _quote_ident(primary_dimension)
            metric_q = _quote_ident(primary_metric)
            dim_label = _dimension_label(primary_dimension)
            metric_label = _humanize_column(primary_metric)

            _append(
                f"Лидеры по {metric_label} ({dim_label})",
                (
                    "Показывает топ-направления, где формируется основной вклад в метрику."
                    f"{dimension_hint}"
                ),
                (
                    "SELECT {dim} AS segment, SUM({metric}) AS metric_total\n"
                    "FROM {table}\n"
                    "GROUP BY 1\n"
                    "ORDER BY metric_total DESC\n"
                    "LIMIT 10"
                ).format(dim=dim_q, metric=metric_q, table=table_ref),
            )

            _append(
                f"Структура {metric_label} по {dim_label}",
                (
                    "Оценивает долю каждого сегмента в общем результате."
                    f"{dimension_hint}"
                ),
                (
                    "SELECT\n"
                    "  {dim} AS segment,\n"
                    "  SUM({metric}) AS metric_total,\n"
                    "  ROUND(\n"
                    "    100.0 * SUM({metric}) / NULLIF(SUM(SUM({metric})) OVER (), 0),\n"
                    "    2\n"
                    "  ) AS share_pct\n"
                    "FROM {table}\n"
                    "GROUP BY 1\n"
                    "ORDER BY metric_total DESC\n"
                    "LIMIT 10"
                ).format(dim=dim_q, metric=metric_q, table=table_ref),
            )

            _append(
                f"Эффективность сегментов по {metric_label}",
                (
                    "Сравнение среднего значения метрики между сегментами."
                    f"{dimension_hint}"
                ),
                (
                    "SELECT\n"
                    "  {dim} AS segment,\n"
                    "  AVG({metric}) AS metric_avg,\n"
                    "  COUNT(*) AS rows_total\n"
                    "FROM {table}\n"
                    "GROUP BY 1\n"
                    "ORDER BY metric_avg DESC\n"
                    "LIMIT 10"
                ).format(dim=dim_q, metric=metric_q, table=table_ref),
            )

            _append(
                f"Концентрация {metric_label}: топ-3 vs остальные",
                (
                    "Показывает, насколько результат сосредоточен в нескольких сегментах."
                    f"{dimension_hint}"
                ),
                (
                    "WITH ranked AS (\n"
                    "  SELECT {dim} AS segment, SUM({metric}) AS metric_total,\n"
                    "         ROW_NUMBER() OVER (ORDER BY SUM({metric}) DESC) AS rn\n"
                    "  FROM {table}\n"
                    "  GROUP BY 1\n"
                    ")\n"
                    "SELECT\n"
                    "  CASE WHEN rn <= 3 THEN segment ELSE 'Остальные' END AS segment_group,\n"
                    "  SUM(metric_total) AS metric_total,\n"
                    "  ROUND(\n"
                    "    100.0 * SUM(metric_total) / NULLIF(SUM(SUM(metric_total)) OVER (), 0),\n"
                    "    2\n"
                    "  ) AS share_pct\n"
                    "FROM ranked\n"
                    "GROUP BY 1\n"
                    "ORDER BY metric_total DESC"
                ).format(dim=dim_q, metric=metric_q, table=table_ref),
            )
        elif primary_dimension:
            dim_q = _quote_ident(primary_dimension)
            dim_label = _dimension_label(primary_dimension)
            _append(
                f"Где больше всего активности ({dim_label})",
                (
                    "Определяет сегменты с максимальным количеством операций/событий."
                    f"{dimension_hint}"
                ),
                (
                    "SELECT {dim} AS segment, COUNT(*) AS rows_total\n"
                    "FROM {table}\n"
                    "GROUP BY 1\n"
                    "ORDER BY rows_total DESC\n"
                    "LIMIT 10"
                ).format(dim=dim_q, table=table_ref),
            )

        if primary_time and primary_metric:
            ts_q = _quote_ident(primary_time)
            metric_q = _quote_ident(primary_metric)
            metric_label = _humanize_column(primary_metric)

            _append(
                f"Динамика {metric_label} по месяцам",
                (
                    "Тренд KPI во времени для контроля роста/падения."
                    f"{time_hint}"
                ),
                (
                    "SELECT date_trunc('month', {ts}) AS month, SUM({metric}) AS metric_total\n"
                    "FROM {table}\n"
                    "GROUP BY 1\n"
                    "ORDER BY 1\n"
                    "LIMIT 24"
                ).format(ts=ts_q, metric=metric_q, table=table_ref),
            )

            _append(
                f"MoM-изменение {metric_label}",
                (
                    "Помесячное изменение метрики к предыдущему месяцу."
                    f"{time_hint}"
                ),
                (
                    "WITH monthly AS (\n"
                    "  SELECT date_trunc('month', {ts}) AS month, SUM({metric}) AS metric_total\n"
                    "  FROM {table}\n"
                    "  GROUP BY 1\n"
                    ")\n"
                    "SELECT\n"
                    "  month,\n"
                    "  metric_total,\n"
                    "  metric_total - LAG(metric_total) OVER (ORDER BY month) AS delta_prev_month\n"
                    "FROM monthly\n"
                    "ORDER BY month\n"
                    "LIMIT 24"
                ).format(ts=ts_q, metric=metric_q, table=table_ref),
            )

            _append(
                f"Динамика {metric_label} по неделям",
                (
                    "Более детальный недельный тренд для поиска краткосрочных изменений."
                    f"{time_hint}"
                ),
                (
                    "SELECT date_trunc('week', {ts}) AS week, SUM({metric}) AS metric_total\n"
                    "FROM {table}\n"
                    "GROUP BY 1\n"
                    "ORDER BY 1\n"
                    "LIMIT 52"
                ).format(ts=ts_q, metric=metric_q, table=table_ref),
            )

            _append(
                f"Последний период vs предыдущий ({metric_label})",
                "Сравнение текущего и предыдущего периода для быстрого контроля отклонений.",
                (
                    "WITH monthly AS (\n"
                    "  SELECT date_trunc('month', {ts}) AS month, SUM({metric}) AS metric_total\n"
                    "  FROM {table}\n"
                    "  GROUP BY 1\n"
                    "), ranked AS (\n"
                    "  SELECT month, metric_total,\n"
                    "         ROW_NUMBER() OVER (ORDER BY month DESC) AS rn\n"
                    "  FROM monthly\n"
                    ")\n"
                    "SELECT\n"
                    "  MAX(CASE WHEN rn = 1 THEN month END) AS last_month,\n"
                    "  MAX(CASE WHEN rn = 1 THEN metric_total END) AS last_value,\n"
                    "  MAX(CASE WHEN rn = 2 THEN metric_total END) AS prev_value,\n"
                    "  MAX(CASE WHEN rn = 1 THEN metric_total END)\n"
                    "    - MAX(CASE WHEN rn = 2 THEN metric_total END) AS delta_value\n"
                    "FROM ranked\n"
                    "WHERE rn <= 2"
                ).format(ts=ts_q, metric=metric_q, table=table_ref),
            )

            if primary_dimension:
                dim_q = _quote_ident(primary_dimension)
                dim_label = _dimension_label(primary_dimension)
                _append(
                    f"Топ-5 сегментов в динамике ({dim_label})",
                    (
                        "Динамика ключевых сегментов для оперативного мониторинга."
                        f"{dimension_hint}{time_hint}"
                    ),
                    (
                        "WITH top_segments AS (\n"
                        "  SELECT {dim} AS segment, SUM({metric}) AS total_metric\n"
                        "  FROM {table}\n"
                        "  GROUP BY 1\n"
                        "  ORDER BY total_metric DESC\n"
                        "  LIMIT 5\n"
                        ")\n"
                        "SELECT\n"
                        "  date_trunc('month', t.{ts_raw}) AS month,\n"
                        "  t.{dim_raw} AS segment,\n"
                        "  SUM(t.{metric_raw}) AS metric_total\n"
                        "FROM {table} t\n"
                        "JOIN top_segments s ON t.{dim_raw} = s.segment\n"
                        "GROUP BY 1, 2\n"
                        "ORDER BY 1, 3 DESC\n"
                        "LIMIT 120"
                    ).format(
                        dim=dim_q,
                        metric=metric_q,
                        table=table_ref,
                        ts_raw=ts_q,
                        dim_raw=dim_q,
                        metric_raw=metric_q,
                    ),
                )

                _append(
                    f"Лидеры последнего месяца ({dim_label})",
                    "Помогает быстро увидеть, кто даёт результат в самом актуальном периоде.",
                    (
                        "WITH monthly AS (\n"
                        "  SELECT date_trunc('month', {ts}) AS month,\n"
                        "         {dim} AS segment,\n"
                        "         SUM({metric}) AS metric_total\n"
                        "  FROM {table}\n"
                        "  GROUP BY 1, 2\n"
                        "), last_month AS (\n"
                        "  SELECT MAX(month) AS month FROM monthly\n"
                        ")\n"
                        "SELECT m.segment, m.metric_total\n"
                        "FROM monthly m\n"
                        "JOIN last_month l ON m.month = l.month\n"
                        "ORDER BY m.metric_total DESC\n"
                        "LIMIT 10"
                    ).format(ts=ts_q, dim=dim_q, metric=metric_q, table=table_ref),
                )
        elif primary_time:
            ts_q = _quote_ident(primary_time)
            _append(
                "Динамика количества операций по месяцам",
                (
                    "Показывает сезонность и изменение нагрузки во времени."
                    f"{time_hint}"
                ),
                (
                    "SELECT date_trunc('month', {ts}) AS month, COUNT(*) AS rows_total\n"
                    "FROM {table}\n"
                    "GROUP BY 1\n"
                    "ORDER BY 1\n"
                    "LIMIT 24"
                ).format(ts=ts_q, table=table_ref),
            )

        _append(
            "Срез данных для проверки",
            "Проверочный срез: убедиться, что таблица и поля выбраны корректно.",
            f"SELECT *\nFROM {table_ref}\nLIMIT 20",
        )

        unique: List[Dict[str, str]] = []
        seen_sql = set()
        for item in candidates:
            sql = item["sql"]
            if sql in seen_sql:
                continue
            seen_sql.add(sql)
            unique.append(item)
            if len(unique) >= max(1, int(max_candidates)):
                break
        return unique

    @staticmethod
    def extract_last_token(text: str) -> str:
        if not text.strip():
            return ""
        match = _LAST_TOKEN_RE.search(text.strip())
        return match.group(1) if match else ""

    @staticmethod
    def apply_entity_to_query(query_text: str, entity: str) -> str:
        base = query_text.rstrip()
        token = US4QueryAssistantService.extract_last_token(base)
        if token and entity.casefold().startswith(token.casefold()):
            return _LAST_TOKEN_RE.sub(entity, base)
        if not base:
            return entity
        return f"{base} {entity}"

    @staticmethod
    def _add_entity(store: Dict[str, str], value: Any) -> None:
        if not isinstance(value, str):
            return
        cleaned = value.strip()
        if not cleaned:
            return
        key = cleaned.casefold()
        if key not in store:
            store[key] = cleaned


def _normalize_table_name(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    token = value.strip()
    if not token:
        return ""
    return token.strip('"')


def get_us4_query_assistant_service() -> US4QueryAssistantService:
    return US4QueryAssistantService()


__all__ = [
    "DEFAULT_US4_EXAMPLES",
    "US4QueryAssistantService",
    "get_us4_query_assistant_service",
]
