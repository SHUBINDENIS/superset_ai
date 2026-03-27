#!/usr/bin/env python3

from __future__ import annotations

import json
import os
from urllib.parse import quote_plus
from typing import Any
from uuid import UUID

from superset.app import create_app
from superset.utils.core import override_user


DEMO_DATABASE_NAME = "Pagila Demo (PostgreSQL)"
DEMO_DATABASE_UUID = UUID("7d1fac8f-a0d0-4700-b72c-5ac80e5f8171")
DEMO_SCHEMA = "public"
DEMO_DATASETS = [
    {
        "table_name": "sales_by_store",
        "description": "Готовый срез выручки по магазинам и сотрудникам.",
    },
    {
        "table_name": "sales_by_film_category",
        "description": "Готовый срез выручки по категориям фильмов.",
    },
    {
        "table_name": "payment",
        "description": "Платежи клиентов по арендам фильмов.",
        "main_dttm_col": "payment_date",
    },
    {
        "table_name": "rental",
        "description": "Факты проката с датами аренды и возврата.",
        "main_dttm_col": "rental_date",
    },
    {
        "table_name": "customer_list",
        "description": "Клиенты с городом, страной и статусом активности.",
    },
    {
        "table_name": "film_list",
        "description": "Фильмы с рейтингом, категорией и актерами.",
    },
    {
        "table_name": "film",
        "description": "Справочник фильмов с ценой аренды и длительностью.",
    },
    {
        "table_name": "category",
        "description": "Справочник категорий фильмов.",
    },
    {
        "table_name": "customer",
        "description": "Клиенты и привязка к магазинам.",
    },
    {
        "table_name": "inventory",
        "description": "Экземпляры фильмов по магазинам.",
    },
]


def _env_enabled(name: str, default: str = "yes") -> bool:
    value = str(os.getenv(name, default) or default).strip().casefold()
    return value in {"1", "true", "yes", "on"}


def _required_env(name: str, default: str) -> str:
    value = str(os.getenv(name, default) or default).strip()
    if not value:
        raise RuntimeError(f"Required environment variable is empty: {name}")
    return value


def _build_demo_sqlalchemy_uri() -> str:
    user = quote_plus(_required_env("DEMO_PAGILA_USER", "pagila"))
    password = quote_plus(_required_env("DEMO_PAGILA_PASSWORD", "pagila"))
    host = _required_env("DEMO_PAGILA_HOST", "pagila-db")
    port = _required_env("DEMO_PAGILA_PORT", "5432")
    database_name = _required_env("DEMO_PAGILA_DB", "pagila")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database_name}"


def _ensure_demo_database(sqlalchemy_uri: str) -> tuple[Any, bool]:
    from superset.commands.database.utils import add_permissions
    from superset.daos.database import DatabaseDAO
    from superset.extensions import db
    from superset.models.core import Database

    database = DatabaseDAO.get_database_by_name(DEMO_DATABASE_NAME)
    if database is None:
        database = (
            db.session.query(Database)
            .filter(Database.uuid == DEMO_DATABASE_UUID)
            .one_or_none()
        )

    created = False
    if database is None:
        database = Database(
            database_name=DEMO_DATABASE_NAME,
            expose_in_sqllab=True,
            allow_run_async=False,
            allow_file_upload=False,
            allow_ctas=False,
            allow_cvas=False,
            allow_dml=False,
            cache_timeout=None,
            extra=json.dumps({}),
            uuid=DEMO_DATABASE_UUID,
        )
        created = True

    database.database_name = DEMO_DATABASE_NAME
    database.expose_in_sqllab = True
    database.allow_run_async = False
    database.allow_file_upload = False
    database.allow_ctas = False
    database.allow_cvas = False
    database.allow_dml = False
    database.cache_timeout = None
    if not database.extra:
        database.extra = json.dumps({})
    if database.sqlalchemy_uri_decrypted != sqlalchemy_uri:
        database.set_sqlalchemy_uri(sqlalchemy_uri)

    db.session.add(database)
    db.session.flush()
    add_permissions(database)
    db.session.commit()
    return database, created


def _ensure_demo_datasets(database: Any) -> tuple[list[str], list[str]]:
    from superset.commands.dataset.create import CreateDatasetCommand
    from superset.connectors.sqla.models import SqlaTable
    from superset.extensions import db

    created: list[str] = []
    existing: list[str] = []

    for spec in DEMO_DATASETS:
        table_name = spec["table_name"]
        dataset = (
            db.session.query(SqlaTable)
            .filter(
                SqlaTable.database_id == database.id,
                SqlaTable.schema == DEMO_SCHEMA,
                SqlaTable.table_name == table_name,
            )
            .one_or_none()
        )
        if dataset is None:
            dataset = CreateDatasetCommand(
                {
                    "database": database.id,
                    "schema": DEMO_SCHEMA,
                    "table_name": table_name,
                }
            ).run()
            created.append(table_name)
        else:
            existing.append(table_name)

        changed = False
        description = str(spec.get("description") or "").strip()
        if description and dataset.description != description:
            dataset.description = description
            changed = True

        main_dttm_col = str(spec.get("main_dttm_col") or "").strip()
        if main_dttm_col and dataset.main_dttm_col != main_dttm_col:
            dataset.main_dttm_col = main_dttm_col
            changed = True

        if changed:
            db.session.add(dataset)

    db.session.commit()
    return created, existing


def main() -> int:
    if not _env_enabled("DEMO_PAGILA_ENABLED", "yes"):
        print("[pagila-demo] disabled")
        return 0

    app = create_app()
    with app.app_context():
        from superset import security_manager

        admin_user = security_manager.find_user(username="admin")
        if admin_user is None:
            raise RuntimeError("Superset admin user was not created before Pagila bootstrap.")

        with override_user(admin_user):
            sqlalchemy_uri = _build_demo_sqlalchemy_uri()
            database, created_database = _ensure_demo_database(sqlalchemy_uri)
            created_datasets, existing_datasets = _ensure_demo_datasets(database)
            database_name = str(database.database_name)

    created_summary = ", ".join(created_datasets) if created_datasets else "none"
    existing_summary = ", ".join(existing_datasets) if existing_datasets else "none"
    status = "created" if created_database else "updated"
    print(
        "[pagila-demo] "
        f"database={database_name!r} ({status}); "
        f"new_datasets={created_summary}; existing_datasets={existing_summary}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
