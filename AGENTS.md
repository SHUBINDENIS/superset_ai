# AGENTS.md

## Mission
Migrate the product from the legacy external MCP implementation in `superset-mcp/main.py` to the built-in Superset MCP service in `superset/superset/mcp_service`.

The end state must remove runtime dependency on `superset-mcp/main.py` while preserving required product behavior, documenting intentional changes, and providing strong automated test coverage.

## Non-negotiable rules
1. Do not delete or disable the legacy implementation until migration parity tests are green.
2. Use git for all work. Prefer small, scoped commits with clear messages.
3. Every migration phase must end with green tests and an explicit commit.
4. Preserve current product behavior through an adapter layer first; do not perform a big-bang rewrite.
5. Any missing parity with legacy MCP must be recorded in a migration matrix.
6. All product-facing MCP use cases must have automated tests.
7. Every target MCP tool used by the product must be covered by tests.
8. Update docs, env examples, deployment instructions, and CI in the same migration effort.
9. Never expose secrets, tokens, or credentials in code, tests, fixtures, or docs.
10. Before removing legacy code, produce a final parity report.

## Source of truth for current architecture
The current product path is:
`Streamlit UI / AI Agent -> superset-mcp/main.py -> Superset REST API`

The target path is:
`Streamlit UI / AI Agent -> built-in Superset MCP service -> internal Superset tools / DAO / RBAC`

## Scope
### In scope
- Replace product runtime integration with built-in MCP.
- Add an adapter layer from legacy tool contracts to built-in MCP tools.
- Add custom built-in MCP extension tools if direct parity is missing.
- Add unit, integration, and end-to-end tests.
- Update docs and CI.
- Remove legacy MCP path only after parity is proven.

### Out of scope unless explicitly needed for parity
- Unrelated refactors in Streamlit UI or agent logic.
- New product features unrelated to migration.
- Broad cleanup of Superset internals outside MCP migration.

## Required deliverables
- `docs/mcp-migration/legacy-contract.md`
- `docs/mcp-migration/tool-matrix.csv`
- adapter layer for product integration
- product migration to built-in MCP
- tests for every target tool and every product use case
- updated `.env.example`, runbooks, and deployment docs
- final migration parity report

## Branching and commits
Use a dedicated migration branch.
Recommended branch name:
`feature/migrate-to-built-in-mcp`

Recommended commit prefixes:
- `chore(...)`
- `docs(...)`
- `test(...)`
- `feat(...)`
- `refactor(...)`
- `ci(...)`

Recommended commit sequence:
1. `chore(repo): add AGENTS.md and migration docs scaffold`
2. `test(legacy): snapshot legacy MCP contract and use cases`
3. `feat(mcp-client): add built-in MCP client adapter`
4. `feat(mapping): migrate product calls to built-in MCP`
5. `feat(mcp-ext): add missing parity extension tools if needed`
6. `test(mcp): add unit, integration and e2e coverage`
7. `docs(migration): update env, deployment and runbooks`
8. `refactor(remove-legacy): remove superset-mcp runtime path`
9. `ci(mcp): enforce migration suites in CI`

## Execution strategy
### Phase 0 — Baseline and discovery
- Inventory all legacy tools from `superset-mcp/main.py`.
- Record signatures, request shapes, response shapes, and product call sites.
- Record product use cases that currently rely on the legacy MCP.
- Produce `legacy-contract.md` and `tool-matrix.csv`.

### Phase 1 — Define target integration
- Choose the built-in MCP transport and client strategy.
- Standardize product MCP access through a single client module.
- Ensure product code no longer talks directly to legacy subprocess APIs.

### Phase 2 — Compatibility adapter
- Build an adapter that maps legacy product calls to built-in MCP tools.
- Normalize arguments and responses to preserve current product expectations.
- Log and document mismatches.

### Phase 3 — Parity gap closure
- For each legacy tool, classify as one of:
  - `direct` — built-in replacement exists
  - `adapter` — replacement exists with mapping
  - `custom_extension` — add new built-in MCP extension tool
  - `drop` — remove only with explicit approval and docs

### Phase 4 — Product migration
- Switch product modules to the new MCP client.
- Remove direct subprocess dependency on `superset-mcp/main.py`.
- Keep legacy path behind a temporary flag only if required during rollout.

### Phase 5 — Verification
- Add or update unit tests, integration tests, and end-to-end use-case tests.
- Add a parity suite that compares legacy expectations to built-in MCP behavior.
- Keep legacy implementation until parity is proven.

### Phase 6 — Removal and cleanup
- Remove runtime references to legacy MCP.
- Update env vars, docs, scripts, Dockerfiles, and deployment instructions.
- Remove legacy code only in a final dedicated commit.

## Testing requirements
### Required layers
1. **Unit tests** for mapping, adapter, payload normalization, and error handling.
2. **Built-in MCP tool tests** for every tool the product uses after migration.
3. **Integration tests** against a running built-in MCP service.
4. **End-to-end tests** for representative product workflows.

### Tool coverage rule
Create and maintain a tool inventory fixture. Every target MCP tool used by the product must map to at least one automated test.

### Minimum product use cases to test
- browse datasets/charts/dashboards
- fetch detailed asset info
- execute SQL
- open SQL Lab with context
- generate or update chart flows
- dashboard generation/update flows
- explore-link flow
- permission denied / invalid payload / not found / DML denied cases
- adapter compatibility cases for legacy product calls

## CI requirements
Add separate CI jobs for:
- MCP unit tests
- MCP integration tests
- assistant end-to-end tests
- migration parity checks

Legacy removal is blocked until parity jobs are green.

## File and path guidance
Suggested new paths:
- `docs/mcp-migration/legacy-contract.md`
- `docs/mcp-migration/tool-matrix.csv`
- `docs/mcp-migration/CODEX_MIGRATION_CHECKLIST.md`
- `docs/mcp-migration/IMPORTANT_LEGACY_RELIABILITY_NOTE.md`
- `superset-ai-assistant-mcp/backend/mcp_client/`
- `superset-ai-assistant-mcp/tests/unit/mcp_client/`
- `tests/integration/mcp_migration/`
- `tests/e2e/assistant_mcp/`

## Definition of done
Migration is complete only when all conditions are satisfied:
1. Product no longer depends on `superset-mcp/main.py` at runtime.
2. Product uses built-in Superset MCP service.
3. All required product use cases pass on the new MCP path.
4. All target product MCP tools have automated coverage.
5. Docs, env, deployment, and CI are updated.
6. A final parity report exists.
7. Legacy runtime code is removed in a dedicated final commit.

## What to do first
1. Create migration docs scaffold.
2. Snapshot the legacy MCP contract.
3. Build the compatibility adapter.
4. Add parity tests.
5. Switch product modules one by one.
6. Remove legacy runtime path only after all checks are green.
