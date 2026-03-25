# Important note: legacy MCP is partially broken

This note is **mandatory context** for all migration work from `superset-mcp/main.py` to the built-in Superset MCP service.

## Core rule
The legacy MCP is **not** a fully trustworthy oracle.

Some parts of the old MCP are known or suspected to:
- return incorrect results
- behave inconsistently across runs
- expose partially broken tools
- implement behavior that does not match intended product requirements
- fail for some use cases that should logically work

## What this means for migration
1. Do **not** blindly preserve all current legacy outputs.
2. Do **not** write snapshot-style tests that freeze legacy bugs into the new MCP.
3. Separate these concepts clearly:
   - **observed legacy behavior**
   - **intended/correct behavior**
   - **new target behavior**
4. If a legacy behavior is wrong, the migration target is to **fix it**, not to preserve it.
5. Every known-bad legacy behavior must be explicitly documented.

## Required classification for each legacy tool/use case
For every legacy tool or product use case, record:
- tool or use case name
- whether the current behavior is `known_good`, `known_bad`, `flaky`, or `unknown`
- evidence for that classification
- intended/correct behavior
- whether the migration should `preserve`, `fix`, or `drop` it

## Testing policy
The migration test strategy must include **both**:

### 1. Parity tests
Use parity tests only for:
- validated correct behavior
- stable and trusted legacy behavior
- product flows that are already known to work properly

### 2. Bug-regression tests
Add explicit regression tests for:
- known legacy defects
- cases where the old MCP fails but the new implementation should work correctly
- incorrect legacy outputs that must not be preserved

## Documentation policy
The following migration files must reflect this rule:
- `AGENTS.md`
- `docs/mcp-migration/CODEX_MIGRATION_CHECKLIST.md`
- `docs/mcp-migration/legacy-contract.md`
- `docs/mcp-migration/tool-matrix.csv`
- `docs/mcp-migration/parity-report.md`

## Practical instruction for Codex
When legacy MCP behavior and intended product behavior disagree:
- trust intended product behavior
- trust working use cases
- trust built-in Superset MCP semantics
- trust explicit migration notes
- do **not** trust the buggy legacy behavior by default
