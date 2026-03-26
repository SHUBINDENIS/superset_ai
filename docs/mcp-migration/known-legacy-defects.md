# Known Legacy Defects

This file records confirmed legacy defects and structural reliability problems in
the former `superset-mcp/main.py`. These are migration inputs, not parity targets.

Testing rule:

- Use parity tests only for behavior classified as correct and stable.
- For items below, add fixed-behavior regression tests instead of preserving the old output.

| ID | Status | Observed legacy behavior | Intended or correct behavior | Target new behavior | Evidence | Test implication |
| --- | --- | --- | --- | --- | --- | --- |
| L-001 | known_bad | Dataset scope flows can hit `GET /api/v1/database/<id>/tables/ -> 400`; chat logic already treats that as non-fatal and retries through dataset-level operations | Scope resolution should still succeed when dataset metadata is available | Use dataset discovery tools first (`list_datasets`, `get_dataset_info`); do not depend on database tables endpoint for core scope flows | `backend/ai_agent.py` contains explicit guardrails and retry logic; `tests/test_ai_agent_clarifications.py` asserts this failure pattern | Add regression tests that prove scope-based browse and chart flows work without `database_get_tables` |
| L-002 | known_bad | `superset_auth_authenticate_user` writes bearer tokens to `.superset_token` and returns `access_token` and `token_preview` values to callers | MCP runtime should not expose credential material or rely on a sidecar token file | Use built-in Superset auth context and remove tool-level credential exchange from runtime path | `save_access_token`, `load_stored_token`, and auth response payload in `superset-mcp/main.py` | Add regression tests that no token material is exposed by the new client or adapter |
| L-003 | flaky | `superset_dashboard_create` and `superset_chart_create` use custom CSRF/session handling, duplicate request code, and return tool-specific success, warning, and error shapes | Create flows should rely on one authoritative server-side implementation with stable request and response models | Route create flows through built-in chart/dashboard tools or explicit extension tools with normalized responses | Custom code paths in `superset_dashboard_create` and `superset_chart_create` in `superset-mcp/main.py` | Add regression tests for fixed create behavior, including permission denied, invalid payload, and not-found cases |
| L-004 | known_bad | Error signaling is inconsistent: some failures become JSON-RPC errors, others are successful JSON-RPC results whose text payload contains `error`, `warning`, or `success: false` | Product code should receive one normalized error model for adapter and direct built-in calls | Normalize not found, access denied, invalid payload, timeout, and DML denied errors in the unified client and compatibility adapter | `handle_request`, `requires_auth`, `handle_api_errors`, and multiple tool functions in `superset-mcp/main.py` | Add adapter unit tests for every normalized error category; avoid text-snapshot parity tests |
| L-005 | known_bad | Manual schema definitions mention helper tools such as `superset_auth_login`, `superset_chart_get_viz_types`, `superset_chart_validate_datasource`, and `superset_dashboard_create_with_session`, but these helpers are not registered in `MinimalMCPServer.tools` and are never exposed by `tools/list` | Tool discovery should exactly match the callable runtime surface | Built-in MCP registry and any extension registry must be single-source-of-truth | `manual_schemas` contains tool names that do not exist in `self.tools` in `superset-mcp/main.py` | Add tests that the tool registry and discovery output are in sync |
| L-006 | structural_gap | The legacy MCP is not a complete oracle for product behavior because several product flows already bypass it and use direct REST wrappers (`backend/us13_15_viz_service.py`) | Migration should preserve product capabilities, not only the legacy subprocess outputs | Move all product-facing Superset access behind one built-in MCP client layer | `backend/ai_agent.py` launches legacy MCP, while `backend/us13_15_viz_service.py` and `frontend/app.py` call REST directly | Build use-case tests from product behavior, not only from legacy tool snapshots |

## Defects intentionally not treated as parity requirements

- Token preview echoing in auth responses
- Token-file persistence in `.superset_token`
- Raw admin helper surface that is not needed by product use cases
- Reliance on `/api/v1/database/<id>/tables/` for dataset-scoped flows
- Legacy-specific response wording inside `suggestions`, `warning`, or traceback fields

## Migration guidance derived from the defect log

- Prefer built-in Superset MCP semantics over legacy sidecar semantics when they disagree.
- Preserve successful discovery and read-only user flows only when they are validated as stable.
- For create, update, permission, invalid-input, and DML cases, write new correctness tests against the intended behavior.
