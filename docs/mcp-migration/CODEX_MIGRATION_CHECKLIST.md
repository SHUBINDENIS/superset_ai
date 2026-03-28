# Codex Migration Checklist: Legacy MCP -> Built-in Superset MCP

This checklist is the execution plan for rewriting the product from the legacy external MCP server (`superset-mcp/main.py`) to the built-in Superset MCP service (`superset/superset/mcp_service`).

Status note:
- This is now a historical execution checklist for the completed migration.
- For the current supported architecture and runtime policy, use `docs/mcp-migration/parity-report.md` and `docs/mcp-migration/runtime-switch-policy.md`.
- The legacy `superset-mcp/` directory has been removed from the repository; references below to `superset-mcp/main.py` are historical.

Follow `AGENTS.md` first.

---

## 0. Preparation
- [ ] Work only on branch `feature/migrate-to-built-in-mcp`.
- [ ] Read `AGENTS.md` completely.
- [ ] Do not remove `superset-mcp/main.py` yet.
- [ ] Confirm current product path and current env variables.

Deliverables:
- [ ] `docs/mcp-migration/legacy-contract.md`
- [ ] `docs/mcp-migration/tool-matrix.csv`
- [ ] `docs/mcp-migration/parity-report.md`

Suggested commit:
- `chore(repo): add migration docs scaffold`

---

## 1. Snapshot the legacy MCP contract

Goal: capture the exact behavior of the current legacy MCP before migration.

Tasks:
- [ ] Inventory all legacy tools from `superset-mcp/main.py`.
- [ ] Record per-tool request schema, response schema, and error behavior.
- [ ] Record which product modules call which legacy tools.
- [ ] Record all current environment variables tied to legacy MCP.
- [ ] Record representative product use cases that depend on legacy MCP.

Output files:
- [ ] `docs/mcp-migration/legacy-contract.md`
- [ ] `docs/mcp-migration/tool-matrix.csv`

Tool matrix columns:
- `legacy_tool`
- `legacy_purpose`
- `product_call_sites`
- `new_tool_equivalent`
- `status`
- `notes`
- `test_file`

Suggested commit:
- `test(legacy): snapshot legacy MCP contract and use cases`

---

## 2. Create a single MCP access layer for the product

Goal: make the rest of the product talk to one abstraction instead of directly to a legacy subprocess.

Create:
- [ ] `superset-ai-assistant-mcp/backend/mcp_client/base.py`
- [ ] `superset-ai-assistant-mcp/backend/mcp_client/built_in_client.py`
- [ ] `superset-ai-assistant-mcp/backend/mcp_client/legacy_compat_adapter.py`
- [ ] `superset-ai-assistant-mcp/backend/mcp_client/tool_registry.py`
- [ ] `superset-ai-assistant-mcp/backend/mcp_client/errors.py`

Rules:
- [ ] Product modules must not directly call `superset-mcp/main.py` anymore after this layer is adopted.
- [ ] Keep adapter-based backward compatibility first.
- [ ] Hide transport details behind this client layer.

Suggested commit:
- `feat(mcp-client): add unified MCP client layer`

---

## 3. Implement a legacy compatibility adapter over built-in MCP

Goal: allow old product expectations to work on top of the built-in MCP.

Tasks:
- [ ] Map legacy tool names to built-in MCP tool names.
- [ ] Translate legacy payloads into built-in request payloads.
- [ ] Normalize built-in responses to the product’s current expected shape where needed.
- [ ] Normalize common errors: not found, access denied, invalid payload, timeout, DML denied.
- [ ] Log any parity mismatches in a structured way.

Examples to map:
- legacy dashboard list -> built-in `list_dashboards`
- legacy dashboard info -> built-in `get_dashboard_info`
- legacy chart info -> built-in `get_chart_info`
- legacy SQL execute -> built-in `execute_sql`
- legacy explore/permalink flows -> built-in equivalents where available

Suggested commit:
- `feat(mapping): add legacy compatibility adapter over built-in MCP`

---

## 4. Classify every legacy tool

For each legacy tool, classify it as exactly one of:
- `direct`
- `adapter`
- `custom_extension`
- `drop`

Tasks:
- [ ] Fill `tool-matrix.csv` completely.
- [ ] Mark every tool with one of the statuses above.
- [ ] For `custom_extension`, specify target file/module where the new built-in MCP extension tool will live.
- [ ] For `drop`, document why and who approved it.

Hard rule:
- [ ] No silent drops.

Suggested commit:
- `docs(migration): complete tool classification matrix`

---

## 5. Add missing built-in MCP extension tools if parity requires them

Goal: if the built-in MCP lacks some product-critical behavior, extend it using official MCP integration points.

Tasks:
- [ ] Add custom extension tools for missing parity behavior.
- [ ] Prefer official extension-style registration where possible.
- [ ] Add tests for every new extension tool.
- [ ] Update migration matrix accordingly.

Examples of likely gap areas to verify:
- database CRUD or admin helpers
- tag operations
- saved query wrappers
- special legacy formatting or helper flows

Suggested commit:
- `feat(mcp-ext): add missing built-in MCP extension tools`

---

## 6. Migrate product code to the new MCP client

Goal: make the product run on built-in MCP while preserving behavior.

Target modules to inspect and migrate:
- [ ] `superset-ai-assistant-mcp/backend/ai_agent.py`
- [ ] `superset-ai-assistant-mcp/backend/us4_query_assistant.py`
- [ ] `superset-ai-assistant-mcp/backend/us5_query_builder.py`
- [ ] `superset-ai-assistant-mcp/backend/us13_15_viz_service.py`
- [ ] any subprocess launcher of legacy MCP
- [ ] any config/env references to `SUPERSET_MCP_PATH`

Rules:
- [ ] Switch modules one by one.
- [ ] Keep feature flags or temporary fallback only if necessary.
- [ ] Do not remove the legacy implementation during this phase.

Suggested commit:
- `feat(product): switch assistant services to built-in MCP client`

---

## 7. Testing — unit coverage

### 7.1 Adapter and client tests
Create:
- [ ] `superset-ai-assistant-mcp/tests/unit/mcp_client/`

Add tests for:
- [ ] legacy tool name -> built-in tool name mapping
- [ ] request payload normalization
- [ ] response normalization
- [ ] unsupported tool behavior
- [ ] error normalization
- [ ] timeouts / retries if implemented

Suggested commit:
- `test(mcp-client): add adapter and mapping unit tests`

### 7.2 Built-in MCP tool tests
Use existing built-in MCP tests as a foundation and extend where needed.

Tasks:
- [ ] Identify all built-in MCP tools used by the product.
- [ ] Ensure each one has direct unit coverage.
- [ ] Add missing tests for custom extension tools.
- [ ] Avoid pointless duplication of already-good tests.

Suggested commit:
- `test(mcp): extend built-in MCP tool coverage for product needs`

---

## 8. Testing — integration coverage

Goal: validate a real running built-in MCP service.

Create:
- [ ] `tests/integration/mcp_migration/`

Scenarios:
- [ ] built-in MCP service boots successfully
- [ ] `tools/list` works
- [ ] auth/dev-user setup works
- [ ] `list_dashboards` works
- [ ] `list_datasets` works
- [ ] `list_charts` works
- [ ] `execute_sql` works against test DB
- [ ] chart flow works
- [ ] dashboard flow works
- [ ] negative permission/error cases work

Suggested commit:
- `test(integration): add built-in MCP migration integration tests`

---

## 9. Testing — end-to-end use cases

Goal: verify real product scenarios.

Create:
- [ ] `tests/e2e/assistant_mcp/`

Mandatory use cases:
- [ ] browse datasets/charts/dashboards
- [ ] fetch detailed dataset/chart/dashboard info
- [ ] run SQL analysis through built-in MCP
- [ ] open SQL Lab with context
- [ ] generate or update chart flow
- [ ] generate dashboard / add chart flow
- [ ] generate explore-link flow
- [ ] invalid payload case
- [ ] access denied case
- [ ] DML denied case
- [ ] adapter compatibility case for a representative legacy call

Suggested commit:
- `test(e2e): add assistant built-in MCP use-case coverage`

---

## 10. Tool inventory enforcement

Goal: enforce that every target product MCP tool is covered by tests.

Create:
- [ ] `tests/fixtures/mcp_tool_inventory.yaml`
- [ ] a test that fails if any target tool has no coverage references

For each tool, track:
- `name`
- `layer` (`builtin`, `adapter`, `custom_extension`)
- `covered_by`
- `use_cases`

Suggested commit:
- `test(inventory): enforce MCP tool coverage inventory`

---

## 11. Update env, scripts, docs, deployment

Tasks:
- [ ] remove or deprecate `SUPERSET_MCP_PATH` from docs and env examples
- [ ] add built-in MCP env/config variables
- [ ] update README usage instructions
- [ ] update deployment docs from legacy subprocess MCP to built-in MCP service
- [ ] update any Docker or compose scripts if needed
- [ ] document local dev and CI run commands for the new path

Suggested commit:
- `docs(migration): update env, deployment and runbooks for built-in MCP`

---

## 12. Update CI

Add jobs for:
- [ ] MCP unit tests
- [ ] MCP integration tests
- [ ] assistant e2e tests
- [ ] migration parity suite
- [ ] coverage inventory enforcement

Hard rule:
- [ ] legacy removal is blocked unless parity jobs are green

Suggested commit:
- `ci(mcp): add migration and parity test jobs`

---

## 13. Final parity report

Create:
- [ ] `docs/mcp-migration/parity-report.md`

It must include:
- [ ] all legacy tools and their final status
- [ ] what was directly replaced
- [ ] what required adapters
- [ ] what required custom extensions
- [ ] what was intentionally dropped
- [ ] test evidence and remaining known limitations

Suggested commit:
- `docs(migration): add final parity report`

---

## 14. Remove legacy runtime path

Only do this after all previous steps are complete and green.

Tasks:
- [ ] remove product runtime dependency on `superset-mcp/main.py`
- [ ] remove legacy subprocess launcher code
- [ ] remove legacy env usage
- [ ] remove stale docs
- [ ] optionally remove `superset-mcp/` or mark archived, depending on final decision

Suggested commit:
- `refactor(remove-legacy): remove legacy MCP runtime path`

---

## Definition of done
Migration is done only if all are true:
- [ ] Product no longer depends on `superset-mcp/main.py` at runtime.
- [ ] Built-in Superset MCP is the active path.
- [ ] All required product use cases pass.
- [ ] Every target MCP tool used by the product has automated test coverage.
- [ ] Docs, env, deployment, and CI are updated.
- [ ] Final parity report exists.
- [ ] Legacy code removal happened in a dedicated final commit.
