# Runtime Switch Policy

Status: phase 6 cleanup snapshot before the dedicated legacy-removal commit.

This note explains the current runtime selection policy while the product is being
migrated from `superset-mcp/main.py` to the built-in Superset MCP service.

## Current Default

- Default requested runtime: `built_in_stdio`
- Default fallback runtime: disabled (`none`)
- Supported explicit runtimes:
  - `built_in_stdio`
  - `built_in_http`
  - `legacy` (still present in low-level code only; not part of standard deployment)

The assistant normal runtime now uses the built-in MCP path only. Standard deployment
should not configure a legacy fallback anymore.

## Standard Deployment Policy

- `SUPERSET_PRODUCT_MCP_RUNTIME=built_in_stdio` is the standard default.
- `SUPERSET_PRODUCT_MCP_FALLBACK_RUNTIME` should remain unset in normal deployment.
- `SUPERSET_MCP_PATH` and `SUPERSET_MCP_PYTHON` are no longer part of standard assistant configuration.

Current intended behavior:

1. Try the requested built-in runtime.
2. Preflight the built-in runtime through the unified product MCP client layer.
3. If startup or tool discovery fails, surface the failure explicitly instead of silently
   switching back to the legacy subprocess.

## Phase 4 Product Routing Status

The following product-facing flows now use the unified MCP client layer by default:

- database browsing for UI source pickers
- dataset browse and metadata resolution
- SQL preview / execute flows
- empty-dashboard-first widget creation
- chart generation and update flows
- explore-link generation

Current fallback policy for these flows:

1. Use built-in MCP tools and product extensions first.
2. Do not restore direct token-based auth helpers as a normal runtime path.
3. Keep any remaining legacy-only code explicitly isolated until the final removal commit.

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

## Why Legacy Code Is Still Present

Legacy runtime code remains in the repository only because the final dedicated removal
commit has not been made yet.

It is no longer part of standard deployment behavior.

Do not treat this note as approval to keep legacy as a fallback safety net.

## Phase 6 Status

Current phase 6 assessment:

- built-in MCP remains the default runtime
- default legacy fallback is disabled
- `open_sql_lab_with_context` is now part of the validated target tool surface
  and has live integration coverage
- the US1 schema-profiler flow now runs through `mcp_ext.list_databases` and `execute_sql`
  instead of direct REST login/CSRF/database-table dependencies

This means the remaining work is the dedicated final removal of the dormant legacy runtime
code and any last isolated compatibility branches.
