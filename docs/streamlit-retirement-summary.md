# Streamlit Retirement Summary

Status: completed. Streamlit is no longer a supported runtime or UI path in
this repository.

## What Was Removed

- `superset-ai-assistant-mcp/frontend/` Streamlit UI package:
  - `app.py`
  - `state.py`
  - `ui_helpers.py`
  - `test.py`
  - `__init__.py`
- `superset-ai-assistant-mcp/.streamlit/config.toml`
- `superset-ai-assistant-mcp/start_assistant_stack.sh`
- `assistant` service on `:8051` from `docker-compose.dev.yml`
- Streamlit-specific test coverage:
  - `superset-ai-assistant-mcp/tests/test_frontend_ui.py`
  - `superset-ai-assistant-mcp/tests/unit/test_frontend_state.py`
- Streamlit package dependency from repository Python requirements
- Current run/deploy docs that advertised Streamlit as fallback/default

## What Was Intentionally Kept

- `superset-ai-assistant-mcp/backend/` business logic, including retained
  helper/admin modules:
  - `us2_glossary_service.py`
  - `us3_mapping_rules.py`
  - `us4_query_assistant.py`
  - `us5_query_builder.py`
- `superset-ai-assistant-mcp/api/` and `frontend-next/` as the only supported
  runtime stack
- `start_fastapi_stack.sh`, `docker/dev/start-nextjs-primary.sh`, and the
  unified compose stack for the supported runtime
- Historical cutover/parity documents, but only as archived references rather
  than current operator guidance
- Migration docs under `docs/mcp-migration/`, because they remain part of the
  repository audit trail

## Supported Runtime After This Iteration

- Primary UI: `Next.js` on `:3001`
- Primary API: `FastAPI` on `:8100`
- Superset: `:8088`
- Built-in MCP HTTP in unified local dev stack: `mcp-http:5008`

There is no longer a supported Streamlit runtime, fallback URL, or compose
service in the repository.

## Remaining Polish

- Regenerate Python requirements from a cleaner source-of-truth if the team
  wants to prune more transitive snapshot noise
- Decide whether `US2-US5` will get a new UI surface in `Next.js` or remain
  backend-only capabilities for future work
- Archive or compress more historical cutover documents if the team no longer
  needs the detailed transition trail
