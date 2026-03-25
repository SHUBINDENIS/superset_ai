# Runtime Switch Policy

Status: phase 3 runtime switchover policy for the assistant product.

This note explains the current runtime selection policy while the product is being
migrated from `superset-mcp/main.py` to the built-in Superset MCP service.

## Current Default

- Default requested runtime: `built_in_stdio`
- Supported explicit runtimes:
  - `built_in_stdio`
  - `built_in_http`
  - `legacy`

The product should now try the built-in MCP path first unless configuration explicitly
requests `legacy`.

## Temporary Fallback Policy

- Default fallback runtime: `legacy`
- Fallback env var: `SUPERSET_PRODUCT_MCP_FALLBACK_RUNTIME`
- Disable fallback by setting:
  - `SUPERSET_PRODUCT_MCP_FALLBACK_RUNTIME=none`

Current intended behavior:

1. Try the requested built-in runtime.
2. Preflight the built-in runtime through the unified product MCP client layer.
3. If startup or tool discovery fails, fall back to `legacy` temporarily.

This fallback exists only to keep product safety while the real built-in runtime is
being validated. It is not the target steady state.

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
HTTP endpoint and still honor the temporary fallback policy unless disabled.

## Why Legacy Is Still Present

Legacy runtime code remains available because:

- live built-in integration coverage is still being added
- runtime environments differ in how the built-in service must be launched
- migration safety requires a controlled fallback until built-in checks are green

Do not treat this note as approval to keep legacy as the long-term default.
