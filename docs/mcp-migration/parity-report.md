# MCP Migration Parity Report

Status: phase 6 cleanup snapshot before the dedicated legacy-removal commit.

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
- run the US1 schema/profile/relations scan through `mcp_ext.list_databases` plus `execute_sql`

Automated coverage now includes:

- assistant-side unit tests for adapter mappings, runtime switching, inventory
  enforcement, and normalized error handling
- live built-in MCP integration tests for readonly and mutation flows
- Superset-side extension unit tests for the custom MCP extension tools, now
  isolated from full Flask app bootstrap so the CI job validates the extension
  logic itself instead of unrelated global app imports

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

The migration is not fully removed yet. The remaining legacy-specific items are now
isolated cleanup targets rather than normal runtime dependencies:

- `superset-ai-assistant-mcp/backend/mcp_client/runtime.py`
  and `superset-ai-assistant-mcp/backend/mcp_client/tool_registry.py`
  still carry low-level `legacy` runtime support for the final dedicated removal pass.
- `superset-ai-assistant-mcp/backend/us13_15_viz_service.py`
  still contains isolated legacy-only helper branches, but they are no longer part
  of the standard runtime path after default fallback removal.
- `superset-mcp/main.py`
  still exists because the final removal commit has not been executed yet.

## Legacy-Only Items Still Present

Current legacy-only or legacy-specific items that are still present:

- runtime name `legacy`
- `build_legacy_stdio_server_config()` and explicit legacy mapping code in the unified client layer
- isolated legacy branches in `backend/us13_15_viz_service.py`
- the runtime implementation in `superset-mcp/main.py`

No normal product flow should require legacy token-based auth helpers, CSRF, raw
`database/<id>/tables`, or legacy subprocess launcher env vars anymore.

## `open_sql_lab_with_context` Status

The built-in tool is now part of the validated target surface and has live
integration coverage. There is still no dedicated frontend call site for it in
the current Streamlit product runtime, so it is covered as a required migration
capability rather than as a newly-added UI flow.

## Removal Plan

The remaining dedicated removal sequence is:

1. Delete the remaining low-level `legacy` runtime mode and its isolated compatibility branches.
2. Remove `superset-mcp/main.py` in a dedicated final commit.
3. Re-run the parity and stability suites after that dedicated removal commit.

## Current Gate Assessment

- Built-in MCP is the default runtime: yes
- Product-critical browse, SQL, chart, dashboard, and explore flows use the
  unified MCP client: yes
- US1 schema-profiler flow uses the unified MCP client: yes
- Target product tool inventory is enforced by tests: yes
- Superset-side extension tools have standalone CI coverage: yes
- All normal product runtime paths are migrated off direct REST: yes
- Legacy runtime can be removed now: yes, but only in a dedicated final removal commit
