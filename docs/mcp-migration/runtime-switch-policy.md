# Runtime Switch Policy

Status: built-in-only runtime policy after final legacy runtime removal.

This note explains the current runtime selection policy while the product is being
migrated from `superset-mcp/main.py` to the built-in Superset MCP service.

## Current Default

- Default requested runtime: `built_in_stdio`
- Default fallback runtime: disabled (`none`)
- Supported explicit runtimes:
  - `built_in_stdio`
  - `built_in_http`

The assistant runtime is now built-in-only. There is no supported `legacy` runtime
mode anymore.

## Standard Deployment Policy

- `SUPERSET_PRODUCT_MCP_RUNTIME=built_in_stdio` is the standard default.
- `SUPERSET_PRODUCT_MCP_FALLBACK_RUNTIME` is not part of the supported deployment contract.
- `SUPERSET_MCP_PATH` and `SUPERSET_MCP_PYTHON` are removed from assistant runtime support.

Current intended behavior:

1. Try the requested built-in runtime.
2. Preflight the built-in runtime through the unified product MCP client layer.
3. If startup or tool discovery fails, surface the failure explicitly.

## Phase 4 Product Routing Status

The following product-facing flows now use the unified MCP client layer by default:

- database browsing for UI source pickers
- dataset browse and metadata resolution
- SQL preview / execute flows
- empty-dashboard-first widget creation
- chart generation and update flows
- explore-link generation

Current policy for these flows:

1. Use built-in MCP tools and product extensions only.
2. Do not restore direct token-based auth helpers or REST login/CSRF fallbacks.

## Built-in STDIO Launcher Policy

The built-in stdio path may need an explicit launcher when the assistant runtime
environment does not itself contain a runnable `superset.mcp_service` installation.

Supported override env vars:

- `SUPERSET_BUILT_IN_MCP_COMMAND`
- `SUPERSET_BUILT_IN_MCP_ARGS`

Use these to point the assistant at a known-good launcher script or wrapper command
for the built-in MCP service.

If no explicit command override is provided, the assistant uses the direct Python
module strategy:

- `SUPERSET_BUILT_IN_MCP_PYTHON` or current interpreter
- `python -m superset.mcp_service`

## Built-in HTTP Policy

For HTTP transport:

- set `SUPERSET_PRODUCT_MCP_RUNTIME=built_in_http`
- set `SUPERSET_BUILT_IN_MCP_URL`

The product will use the unified MCP client layer against the configured built-in MCP
HTTP endpoint without enabling a legacy fallback by default.

## Post-Removal Status

- built-in MCP remains the default runtime
- `open_sql_lab_with_context` is part of the validated target tool surface
  and has live integration coverage
- the US1 schema-profiler flow runs through `mcp_ext.list_databases` and `execute_sql`
- the legacy external MCP subprocess path has been removed

Compatibility note:

- `backend/mcp_client/legacy_compat_adapter.py` remains intentionally
  because it adapts old product call contracts onto built-in MCP tools.
- `mcp_ext.legacy_chart_create` remains intentionally
  because it is still the narrow bridge for the pie-chart gap.
