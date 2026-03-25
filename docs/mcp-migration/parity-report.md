# MCP Migration Parity Report

Status: phase 5 stabilization snapshot before legacy runtime removal.

This report describes the current migration state of the assistant product from
`superset-mcp/main.py` to the built-in Superset MCP service. It is a parity and
stability report, not final legacy-removal approval.

## Validated Green Paths

The following product-facing paths are now validated on the built-in MCP route:

- browse databases for source and scope pickers through `mcp_ext.list_databases`
- browse datasets, charts, and dashboards through built-in list/info tools
- execute SQL through `execute_sql`
- generate or update charts through `generate_chart` and `update_chart`
- create an empty dashboard shell through `mcp_ext.create_empty_dashboard`
- add charts to dashboards through `add_chart_to_existing_dashboard`
- generate dashboards through `generate_dashboard`
- generate explore links through `generate_explore_link`
- generate SQL Lab URLs through `open_sql_lab_with_context`

Automated coverage now includes:

- assistant-side unit tests for adapter mappings, runtime switching, inventory
  enforcement, and normalized error handling
- live built-in MCP integration tests for readonly and mutation flows
- Superset-side extension unit tests for the custom MCP extension tools

## Intentional Fixes Versus Legacy

The new runtime intentionally fixes known legacy defects instead of preserving
them:

- `L-001` broken `database/<id>/tables` dependence:
  dataset-scoped flows are validated through dataset tools and no longer require
  `superset_database_get_tables`.
- `L-002` token exposure:
  the migrated client and adapter redact sensitive fields and do not expose
  token material as a product contract.
- `L-003` flaky create flows:
  product chart/dashboard creation now prefers built-in MCP semantics and keeps
  `mcp_ext.legacy_chart_create` as a narrow compatibility bridge only for the
  remaining `pie` gap.
- `L-004` inconsistent error signaling:
  not-found, access-denied, invalid-payload, timeout, and DML-denied outcomes
  are normalized into one product error model.
- `L-005` tool discovery drift:
  tool inventory enforcement now keeps the target product tool set aligned with
  automated coverage, and live `tools/list` integration continues to validate
  the real runtime surface.

## Remaining Legacy or Direct-REST Dependencies

The migration is not finished yet. The following paths still remain outside the
final desired steady state:

- `superset-ai-assistant-mcp/backend/us1_schema_profiler.py`
  still uses direct REST login, CSRF, `sqllab/execute`, `database`, `schemas`,
  and `database/<id>/tables` endpoints.
- `superset-ai-assistant-mcp/frontend/app.py`
  still invokes the US1 scanner, so this direct REST path is part of normal
  product runtime today.
- `superset-ai-assistant-mcp/backend/ai_agent.py`
  still carries legacy launcher resolution helpers and legacy fallback support.
- `superset-ai-assistant-mcp/backend/mcp_client/runtime.py`
  and `superset-ai-assistant-mcp/backend/mcp_client/tool_registry.py`
  still support the temporary `legacy` runtime.
- `superset-ai-assistant-mcp/.env.example`,
  `superset-ai-assistant-mcp/README.md`, and `docs/deployment.md`
  still contain legacy runtime configuration or setup references.
- `superset-mcp/main.py`
  still exists as the temporary fallback process path.

## Legacy-Only Items Still Present

Current legacy-only or legacy-specific items that are still present:

- runtime name `legacy`
- fallback env var `SUPERSET_PRODUCT_MCP_FALLBACK_RUNTIME`
- legacy launcher env vars `SUPERSET_MCP_PATH` and `SUPERSET_MCP_PYTHON`
- legacy subprocess path resolution in `backend/ai_agent.py`
- the runtime implementation in `superset-mcp/main.py`

No product flow should require legacy token-based auth helpers anymore.

## `open_sql_lab_with_context` Status

The built-in tool is now part of the validated target surface and has live
integration coverage. There is still no dedicated frontend call site for it in
the current Streamlit product runtime, so it is covered as a required migration
capability rather than as a newly-added UI flow.

## Removal Plan

Legacy runtime removal is blocked until the following steps are complete:

1. Migrate or explicitly isolate the US1 schema-profiler flow away from direct
   REST and the broken database-tables dependency.
2. Remove legacy fallback as the default safety path, then disable it in normal
   deployment.
3. Delete legacy launcher env vars and the corresponding resolver code from the
   assistant runtime.
4. Update `.env.example`, deployment docs, and README files to remove legacy
   runtime instructions.
5. Remove `superset-mcp/main.py` only in a dedicated final commit after the
   parity and stability gates stay green.

## Current Gate Assessment

- Built-in MCP is the default runtime: yes
- Product-critical browse, SQL, chart, dashboard, and explore flows use the
  unified MCP client: yes
- Target product tool inventory is enforced by tests: yes
- Superset-side extension tools have standalone CI coverage: yes
- All normal product runtime paths are migrated off direct REST: no
- Legacy runtime can be removed now: no
