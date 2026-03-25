# Target Product Tool Set

Status: phase 4 product-facing target tool set.

This file lists only the MCP capabilities actually needed by the product runtime.
It intentionally excludes legacy auth helpers, raw admin CRUD helpers, and known-bad
database-table discovery dependencies.

## Rules

- Token-based legacy auth tools are not part of the target product contract.
- Dataset-scoped flows must not depend on `database_get_tables`.
- Start from the minimum runtime tool set and extend only when a product use case requires it.

## Required Direct Built-in Tools

Direct built-in tools now required by the migrated product runtime:

- `list_dashboards`
- `get_dashboard_info`
- `list_charts`
- `get_chart_info`
- `list_datasets`
- `get_dataset_info`
- `execute_sql`
- `open_sql_lab_with_context`
- `generate_chart`
- `update_chart`
- `generate_dashboard`
- `add_chart_to_existing_dashboard`
- `generate_explore_link`

## Required Adapter Mappings

Legacy names still worth supporting through the compatibility adapter in phase 2:

- `superset_dashboard_list` -> `list_dashboards`
- `superset_dashboard_get_by_id` -> `get_dashboard_info`
- `superset_chart_list` -> `list_charts`
- `superset_chart_get_by_id` -> `get_chart_info`
- `superset_dataset_list` -> `list_datasets`
- `superset_dataset_get_by_id` -> `get_dataset_info`
- `superset_sqllab_execute_query` -> `execute_sql`

Explicit non-goals for the first adapter:

- legacy auth helpers
- `superset_database_get_tables`
- raw tag/query/admin helper tools
- raw explore form-data and permalink cache helpers

## Required Custom Extension Tools

Required by actual product runtime, but not available as direct built-in tools:

- `mcp_ext.list_databases`
  - Needed for source pickers, scope selection in the UI, and the US1 schema-profiler entrypoint.
- `mcp_ext.create_empty_dashboard`
  - Needed because the product still has an empty-dashboard-first flow and built-in `generate_dashboard` requires chart IDs.
- `mcp_ext.legacy_chart_create`
  - Needed only for the remaining compatibility gap where the current UI still exposes legacy-style `pie` creation that is not expressible through the built-in simplified chart schema.

## Why This Is The Minimum Set

The current runtime needs to support:

- browse datasets, charts, dashboards
- browse accessible databases for source pickers
- scan PostgreSQL schemas, tables, columns, row counts, and relations for US1
- fetch detailed asset info
- execute SQL
- generate and update charts through built-in schemas where possible
- create empty dashboards first, then attach charts
- generate user-ready explore links
- keep dataset-scoped flows independent from `database/tables`

Compatibility rule:

- Prefer direct built-in tools first.
- Use `mcp_ext.legacy_chart_create` only for the narrow unsupported `pie` gap.
- Do not reintroduce token-based auth helpers or raw database table discovery dependencies.
