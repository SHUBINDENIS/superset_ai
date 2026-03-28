# Legacy MCP Contract Snapshot

Status: phase 0 discovery snapshot captured on 2026-03-25 before the final
repository cleanup removed `superset-mcp/`.

This document records what the legacy MCP server in `superset-mcp/main.py` did
before removal from the repository. It is not a golden oracle. When observed
legacy behavior conflicts with intended product behavior or built-in Superset
MCP semantics, the migration target is to fix the behavior, not freeze the bug.

See also:

- `docs/mcp-migration/tool-matrix.csv`
- `docs/mcp-migration/known-legacy-defects.md`

## 1. Interpretation rules

- Observed legacy behavior: what the current code path actually does.
- Intended or correct behavior: what the product should do for users.
- Target new behavior: what the built-in Superset MCP migration should implement.

The legacy server is only one input into migration design. Other sources of truth are:

- product call sites in `superset-ai-assistant-mcp/`
- built-in MCP tools in `superset/superset/mcp_service/`
- existing tests, especially `superset-ai-assistant-mcp/tests/test_ai_agent_clarifications.py`
- explicit migration instructions in `AGENTS.md`

## 2. Captured legacy runtime architecture

Expected legacy path for chat:

`Streamlit chat -> backend/ai_agent.py -> mcp-use MCPClient -> python subprocess -> superset-mcp/main.py -> Superset REST API`

Important discovery note from the snapshot:

- The repository is already hybrid, not purely legacy-MCP-based.
- `superset-ai-assistant-mcp/backend/ai_agent.py` launches `superset-mcp/main.py` and exposes its full tool surface to the LLM.
- Several structured UI flows in `superset-ai-assistant-mcp/frontend/app.py` use `superset-ai-assistant-mcp/backend/us13_15_viz_service.py`, which talks to Superset REST directly and bypasses the legacy MCP entirely.
- Migration must therefore replace both:
  - the runtime dependency on `superset-mcp/main.py`
  - the remaining product REST wrappers that should instead use a unified built-in MCP client layer

## 3. Product call sites in scope

| Module | Current behavior | Migration implication |
| --- | --- | --- |
| `superset-ai-assistant-mcp/backend/ai_agent.py` | Launches the legacy MCP via `SUPERSET_MCP_PYTHON` and `SUPERSET_MCP_PATH`; exposes all legacy tools to the model; prompt explicitly references `superset_auth_authenticate_user`, `superset_dataset_list`, dashboard tools, and chart tools | Primary runtime dependency to replace first with unified built-in MCP client |
| `superset-ai-assistant-mcp/tests/test_ai_agent_clarifications.py` | Encodes known legacy reliability issues, especially `GET /api/v1/database/<id>/tables/ -> 400` being non-fatal for scope resolution | Test evidence for known-bad legacy behavior; use regression tests, not parity snapshots |
| `superset-ai-assistant-mcp/backend/us13_15_viz_service.py` | Direct REST wrappers for databases, datasets, dataset metadata, SQL preview, dashboard create, chart create, and share links | Later migration phases should route these product flows through the same built-in MCP client layer |
| `superset-ai-assistant-mcp/frontend/app.py` | Product UI for browsing sources, previewing SQL, selecting datasets, and creating dashboard widgets; currently backed by direct REST service methods, not legacy MCP | Product-facing use cases must be covered by MCP migration tests even when not currently routed through `superset-mcp/main.py` |

## 4. Legacy transport contract

### 4.1 Launch and transport

- Server process: `python superset-mcp/main.py`
- Transport: stdio JSON-RPC
- Protocol methods implemented:
  - `initialize`
  - `tools/list`
  - `tools/call`
  - `ping`
  - `shutdown`
- The legacy server is custom. It does not use the built-in Superset MCP service.

### 4.2 `initialize`

Observed behavior:

- Loads a cached access token from `superset-mcp/.superset_token` if present.
- Returns protocol version `2024-11-05`.
- Declares tool capability only; roots/resources/prompts are always marked unchanged.

Target migration behavior:

- Client should speak to built-in Superset MCP service directly.
- Authentication should come from the built-in transport and Superset user context, not a sidecar token file.

### 4.3 `tools/list`

Observed behavior:

- Returns only tools present in `MinimalMCPServer.tools`.
- Validation schema is a mix of:
  - auto-generated schemas from Python signatures
  - hand-written overrides in `manual_schemas`
- `manual_schemas` contains helper tools that are not actually registered in `self.tools`, so they never appear in runtime `tools/list`.

Target migration behavior:

- One authoritative tool registry from built-in Superset MCP.
- No dead schema entries or undiscoverable helper tools.

### 4.4 `tools/call`

Observed behavior:

- Arguments are validated against JSON schema before the Python function runs.
- Missing tool returns JSON-RPC `-32601`.
- Invalid parameters return JSON-RPC `-32602`.
- Uncaught internal exceptions return JSON-RPC `-32603`.
- Most tool-level failures do not raise JSON-RPC errors; they return successful JSON-RPC results whose `content[0].text` is a JSON string containing fields such as `error`, `details`, `success: false`, `warning`, or tool-specific payloads.

Observed success envelope:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "{ ... pretty-printed JSON string ... }"
      }
    ]
  }
}
```

Migration implication:

- Adapter layer must normalize:
  - JSON-RPC errors
  - tool payload errors returned inside successful results
  - mismatched success shapes across legacy tools

## 5. Authentication, state, and side effects

Observed legacy behavior:

- `SUPERSET_BASE_URL`, `SUPERSET_USERNAME`, and `SUPERSET_PASSWORD` drive direct REST login.
- `superset_auth_authenticate_user` posts to `/api/v1/security/login`.
- Access token is cached in `superset-mcp/.superset_token`.
- Global mutable process state is used:
  - `_global_client`
  - `_global_access_token`
  - `_global_base_url`
- Tools guarded by `@requires_auth` return `{"error": "Not authenticated. Please authenticate first."}` if no cached token exists.
- The server writes local logs:
  - `superset_mcp_full.log`
  - `error_logs/*.txt`

Target migration behavior:

- Built-in Superset MCP should use internal Superset auth and RBAC.
- Do not preserve token-file caching or token echoing behavior.
- Errors should be structured and safe for logs and tests.

## 6. Legacy environment and runtime dependencies

Legacy-specific environment or runtime dependencies discovered in the snapshot:

- `SUPERSET_MCP_PATH`
- `SUPERSET_MCP_PYTHON`
- `SUPERSET_BASE_URL`
- `SUPERSET_USERNAME`
- `SUPERSET_PASSWORD`

Other related product env vars already used outside the legacy MCP path:

- `SUPERSET_PUBLIC_URL`
- `US15_SHARE_BASE_URL`

Migration implication:

- `SUPERSET_MCP_PATH` and `SUPERSET_MCP_PYTHON` are legacy-runtime-only and should disappear from runtime configuration after migration.
- `SUPERSET_BASE_URL`, `SUPERSET_PUBLIC_URL`, and share URL config may still be needed by the product client layer and UI links.

## 7. Tool inventory by family

Full per-tool classification is in `docs/mcp-migration/tool-matrix.csv`.

The legacy runtime surface currently exposes these tool families:

| Family | Legacy tools | Observed request shape | Observed success shape | Reliability note |
| --- | --- | --- | --- | --- |
| Auth | `superset_auth_authenticate_user`, `superset_auth_check_token_validity`, `superset_auth_refresh_token` | username/password or no args | custom dicts; auth tool returns token preview fields | Not a trustworthy target contract; security and state issues |
| Dashboards | `superset_dashboard_list`, `superset_dashboard_get_by_id`, `superset_dashboard_create`, `superset_dashboard_update`, `superset_dashboard_delete` | no args, integer IDs, or raw `data` payloads | raw REST payloads for list/get/update; custom dicts for create/delete | `create` is custom and brittle; list/get are closer to normal REST wrappers |
| Charts | `superset_chart_list`, `superset_chart_get_by_id`, `superset_chart_create`, `superset_chart_update`, `superset_chart_delete` | no args, integer IDs, or raw chart payloads with `viz_type` and `params` | raw REST payloads for list/get/update; custom dicts for create/delete | `create` uses hand-rolled CSRF/session logic and inconsistent responses |
| Databases | `superset_database_*` CRUD and helper tools | mostly integer IDs or raw objects | raw REST payloads, except delete message wrappers | Product only needs a small subset; `database_get_tables` is known-bad for scope flows |
| Datasets | `superset_dataset_list`, `superset_dataset_get_by_id`, `superset_dataset_create` | no args, integer ID, or raw create payload | raw REST payloads | Discovery paths are useful; create is not currently product-critical |
| SQL Lab | `superset_sqllab_execute_query`, `superset_sqllab_get_saved_queries`, `superset_sqllab_format_sql`, `superset_sqllab_get_results`, `superset_sqllab_estimate_query_cost`, `superset_sqllab_export_query_results`, `superset_sqllab_get_bootstrap_data` | database IDs, SQL strings, or simple identifiers | raw REST payloads or small wrappers | `execute_query` is the only clearly product-critical capability today |
| Saved query and query admin | `superset_saved_query_*`, `superset_query_*` | IDs or raw query objects | raw REST payloads | No confirmed product dependence today |
| User/activity/tag | `superset_activity_get_recent`, `superset_user_*`, `superset_tag_*` | mostly no args or simple IDs | raw REST payloads or delete message wrappers | No confirmed product dependence today |
| Explore | `superset_explore_form_data_create/get`, `superset_explore_permalink_create/get` | raw `form_data`, `state`, or cache keys | raw REST payloads | Product needs explore-link behavior, not necessarily these raw cache key APIs |
| Menu/config/advanced type | `superset_menu_get`, `superset_config_get_base_url`, `superset_advanced_data_type_*` | mostly no args | raw REST payloads or local env-derived dict | No confirmed product dependence today |

## 8. Known contract problems that should not be preserved

See `docs/mcp-migration/known-legacy-defects.md` for the defect log.

Important issues already confirmed from code and tests:

- `superset_database_get_tables` can fail with `GET /api/v1/database/<id>/tables/ -> 400` and must not be treated as a hard blocker for dataset-scoped workflows.
- Authentication tools persist bearer tokens to disk and echo token material back to the caller.
- Dashboard and chart creation use custom CSRF/session code paths with inconsistent response envelopes.
- Legacy error signaling is inconsistent across JSON-RPC errors and in-band tool payload errors.
- The declared schema surface and the actual registered tool surface diverge.

## 9. Built-in Superset MCP replacements discovered

Built-in tools already present in `superset/superset/mcp_service/` and relevant to product migration:

- `health_check`
- `get_instance_info`
- `list_datasets`
- `get_dataset_info`
- `list_charts`
- `get_chart_info`
- `generate_chart`
- `update_chart`
- `list_dashboards`
- `get_dashboard_info`
- `generate_dashboard`
- `add_chart_to_existing_dashboard`
- `execute_sql`
- `open_sql_lab_with_context`
- `generate_explore_link`

Immediate migration gaps identified from discovery:

- database discovery for product scope and picker UI (`list_databases` equivalent)
- empty dashboard creation if product still needs a dashboard before a chart exists
- legacy raw chart/dashboard payload compatibility if we want strict adapter coverage before prompt changes

## 10. Initial migration conclusions

- Stable parity candidates:
  - dataset list and get
  - chart list and get
  - dashboard list and get
  - SQL execute for validated read-only flows
- Fix, do not snapshot:
  - database tables scope resolution failures
  - auth token handling
  - chart and dashboard create quirks
  - inconsistent error payloads
- Likely drop from product runtime:
  - auth helper tools
  - raw admin CRUD not used by product
  - tag/query/saved-query helpers without confirmed product dependence
  - raw explore cache-key helpers if `generate_explore_link` covers the user-facing flow

The detailed row-by-row decision record lives in `docs/mcp-migration/tool-matrix.csv`.
