# Target Product Tool Set

Status: phase 2 initial tool-set definition for the migrated product MCP layer.

This file lists only the MCP capabilities actually needed by the product runtime.
It intentionally excludes legacy auth helpers, raw admin CRUD helpers, and known-bad
database-table discovery dependencies.

## Rules

- Token-based legacy auth tools are not part of the target product contract.
- Dataset-scoped flows must not depend on `database_get_tables`.
- Start from the minimum runtime tool set and extend only when a product use case requires it.

## Required Direct Built-in Tools

Phase 2 initial direct built-in tools:

- `list_dashboards`
- `get_dashboard_info`
- `list_charts`
- `get_chart_info`
- `list_datasets`
- `get_dataset_info`
- `execute_sql`

Required direct built-in tools for later migration phases:

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

Required by actual product runtime, but not available as direct built-in tools yet:

- `mcp_ext.list_databases`
  - Needed for source pickers and scope selection in the UI.
- `mcp_ext.create_empty_dashboard`
  - Needed because the product still has an empty-dashboard-first flow and built-in `generate_dashboard` requires chart IDs.

## Why This Is The Minimum Set

The current runtime needs to support:

- browse datasets, charts, dashboards
- fetch detailed asset info
- execute SQL
- keep dataset-scoped flows independent from `database/tables`

Everything else can be added after these paths are stable and covered by tests.
