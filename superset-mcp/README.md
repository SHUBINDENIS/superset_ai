# Legacy Superset MCP Archive

This directory is retained only as historical migration reference material.

It is not part of the supported runtime path anymore:

- the assistant now uses the built-in Superset MCP service in
  `superset/superset/mcp_service`
- the legacy external runtime file `superset-mcp/main.py` has been removed
- standard deployment and CI must not depend on this package

What remains here:

- legacy packaging metadata
- old MCP contract/reference files
- archive-only configuration examples

If you need the current supported architecture, use:

- `docs/mcp-migration/parity-report.md`
- `docs/mcp-migration/runtime-switch-policy.md`
- `superset-ai-assistant-mcp/README.md`
- `docs/deployment.md`

Do not use this directory as a setup guide for the current product.
