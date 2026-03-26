# Dual-Run Parity And Cutover Readiness

Status: continue dual-run; core-flow logging blocker closed, but keep cutover gated on one explicit dual-run smoke signoff.

Этот документ фиксирует repo-backed audit между:
- текущим Streamlit UI
- новым Next.js/FastAPI стеком

Цель: понять, достигнута ли практическая parity для основного demo/product path
и что ещё остаётся blocker’ом перед безопасным cutover.

## Audit Baseline

В качестве baseline использованы:
- `docs/manual-smoke-checklist.md`
- `docs/demo-query-pack.md`
- `docs/demo-pagila.md`

Repo-backed evidence для этого аудита:
- Streamlit product flows в `superset-ai-assistant-mcp/frontend/app.py`
- Next.js core routes в `superset-ai-assistant-mcp/frontend-next/src/app/app/`
- FastAPI routes в `superset-ai-assistant-mcp/api/routers/`
- automation:
  - `superset-ai-assistant-mcp/tests/test_frontend_ui.py`
  - `superset-ai-assistant-mcp/tests/test_api_auth.py`
  - `superset-ai-assistant-mcp/tests/test_api_chats.py`
  - `superset-ai-assistant-mcp/tests/test_api_viz.py`
  - `superset-ai-assistant-mcp/tests/test_api_scan.py`
  - `npm run build` в `superset-ai-assistant-mcp/frontend-next`
  - `superset-ai-assistant-mcp/tests/test_api_frontend_logs.py`

## Current Repo-Backed Coverage

### Streamlit UI
- Всё ещё покрывает полный текущий пользовательский и helper/admin контур:
  - US1 scan
  - US2 glossary
  - US3 mapping rules
  - US4 query hints
  - US5 query builder
  - chat
  - preview / recommend / share
  - guardrails UX
  - frontend-side structured logging

### Next.js/FastAPI stack
- Покрывает основной product/demo path:
  - auth
  - chat + multi-chat
  - preview
  - recommend
  - share
  - schema scan
- Current core routes:
  - `/login`
  - `/register`
  - `/app/chat`
  - `/app/preview`
  - `/app/recommend`
  - `/app/share`
  - `/app/scan`
- Current FastAPI routers:
  - `auth.py`
  - `chats.py`
  - `frontend_logs.py`
  - `viz.py`
  - `scan.py`
  - `health.py`

## Core-Flow Parity Matrix

| Flow | Streamlit baseline | Next.js/FastAPI status | Classification | Repo-backed evidence | Notes |
|---|---|---|---|---|---|
| Auth | Register/login/logout, protected UI | Present | parity achieved | `frontend-next/src/app/login/page.tsx`, `frontend-next/src/app/register/page.tsx`, `api/routers/auth.py`, `tests/test_api_auth.py` | Cookie-based auth preserved |
| Multi-chat | Create/switch/rename/clear/restore | Present | parity achieved | `frontend-next/src/components/chat-sidebar.tsx`, `frontend-next/src/hooks/use-chats.tsx`, `api/routers/chats.py`, `tests/test_api_chats.py` | Active chat pointer persists through `/activate` |
| Normal chat | Send message, immediate UX, onboarding | Present | parity achieved | `frontend-next/src/app/app/chat/page.tsx`, `frontend-next/src/components/chat-input.tsx`, `frontend-next/src/components/chat-empty.tsx`, `api/routers/chats.py` | Core user path migrated |
| Blocked request handling | Intentional policy-block rendering | Present | parity achieved | `frontend-next/src/components/chat-message.tsx`, `tests/test_api_chats.py::test_send_message_blocked_response`, `tests/test_frontend_ui.py::test_blocked_agent_reply_is_rendered_as_intentional_policy_block` | Finish-reason semantics preserved |
| Preview | Refresh sources, preview rows, field explanations | Present | parity acceptable with known limitations | `frontend-next/src/app/app/preview/page.tsx`, `api/routers/viz.py`, `tests/test_api_viz.py::test_preview_endpoint` | Missing explicit “preview -> prefilled business follow-up question” flow from Streamlit |
| Recommendation | Recommend viz type and explanations | Present | parity achieved | `frontend-next/src/app/app/recommend/page.tsx`, `api/routers/viz.py`, `tests/test_api_viz.py::test_recommend_endpoint` | Uses preview context as intended |
| Chart/dashboard creation | Create chart/dashboard and show results | Present | parity achieved | `frontend-next/src/app/app/share/page.tsx`, `api/routers/viz.py`, `tests/test_api_viz.py::test_share_widget_endpoint` | Core demo share path migrated |
| Useful links | Surface links in chat/share flows | Present | parity acceptable with known limitations | `frontend-next/src/components/chat-message.tsx`, `frontend-next/src/components/link-result-card.tsx`, `frontend-next/src/app/app/share/page.tsx` | Next.js chat currently extracts URLs heuristically; Streamlit shows richer outcome framing |
| Schema scan | Run scan, show summary/report | Present | parity acceptable with known limitations | `frontend-next/src/app/app/scan/page.tsx`, `api/routers/scan.py`, `tests/test_api_scan.py` | Next page does not yet expose report download button; scan remains synchronous |
| Structured logging compatibility | Frontend + agent + MCP + artifact correlation | Present for migrated core flows | parity achieved | `frontend-next/src/lib/observability.ts`, `frontend-next/src/lib/api-client.ts`, `api/routers/frontend_logs.py`, `tests/test_api_frontend_logs.py` | Next.js logs land in `frontend.log`; chat/viz/scan propagate `trace_id` / `request_id` into backend logs |

## Flow-Level Findings

### Parity achieved
- auth
- multi-chat
- normal chat
- blocked request handling
- recommendation
- chart/dashboard creation
- structured logging compatibility

### Parity acceptable with known limitations
- preview
  - Next.js preview covers the main data/field understanding path.
  - Streamlit still has the stronger “ask a business question from this preview” handoff.
- useful links
  - Share-page links are strong in both UIs.
  - Chat-side link rendering in Next.js is simpler than in Streamlit.
- schema scan
  - Core scan/report path is available in Next.js.
  - Streamlit still has a slightly richer operational affordance set around the result.

### No current blocker inside the migrated core path
- The previously missing frontend-side structured logging parity is now present for:
  - auth
  - navigation between migrated routes
  - chat + multi-chat actions
  - preview / recommend / share
  - schema scan
- Correlation now works practically through:
  - Next.js frontend events in `frontend.log`
  - `x-trace-id` / `x-request-id` propagation into chat/viz/scan API calls
  - existing `agent.log`, `mcp.log`, and `artifact.log`

## Cutover Readiness Assessment

### Current recommendation
- Safe to continue dual-run: `yes`
- Safe to cut over the primary user-facing core flow today: `almost, but run one explicit dual-run smoke signoff first`

### Why still not automatically yes
The main repo-backed blocker is closed, but this document still recommends one
more explicit dual-run smoke pass before changing the default route:
- confirm the new `frontend.log` events appear during real Next.js usage
- confirm `trace_id` / `request_id` match the downstream backend logs
- confirm no regression in the existing Streamlit fallback path

### What is already strong enough
- Core demo path exists in the new stack:
  - auth
  - chat + multi-chat
  - preview
  - recommend
  - share
  - scan
- FastAPI routes for these flows exist and have automated API coverage.
- `next build` passes for the new frontend.
- Streamlit remains available as a validated fallback during dual-run.

## Are Helper/Admin Pages Blockers?

Short answer: `no` for a phased primary-frontend cutover, `yes` for full Streamlit retirement.

### Why they are not blockers for primary cutover
The manual smoke checklist and demo query pack focus on:
- auth
- multi-chat
- normal/blocked chat
- preview
- recommendation
- widget/dashboard creation
- useful links
- schema scan

These are now present in the new stack.

The remaining Streamlit-only pages are:
- glossary (US2)
- mapping rules (US3)
- query hints (US4)
- query builder (US5)

They are helper/admin flows, not part of the current core demo baseline.

### Why they still matter
They remain blockers for the later milestone “remove Streamlit entirely”.

So the practical decision is:
- primary core-flow cutover: possible after one final dual-run smoke signoff
- Streamlit decommission: not possible until US2-US5 are either migrated or formally dropped

## Dual-Run Decision

Recommended near-term mode:
1. Keep Streamlit running as fallback/admin console.
2. Treat Next.js/FastAPI as the candidate primary UX for the core path.
3. Re-run `docs/manual-smoke-checklist.md` against both stacks.
4. Use `docs/demo-query-pack.md` for the live Pagila demo path on both stacks.
5. Use the new Next.js frontend logs as part of the signoff evidence before default-route cutover.

## Minimal Evidence Collected In This Audit

Validated during this audit:
- `python -m unittest superset-ai-assistant-mcp/tests/test_frontend_ui.py`
- `python -m unittest superset-ai-assistant-mcp/tests/test_api_auth.py superset-ai-assistant-mcp/tests/test_api_chats.py superset-ai-assistant-mcp/tests/test_api_viz.py superset-ai-assistant-mcp/tests/test_api_scan.py`
- `npm run build` in `superset-ai-assistant-mcp/frontend-next`

These checks support:
- Streamlit baseline stability
- FastAPI route coverage for the migrated core path
- successful compilation of the new frontend routes

## Safe Next Step Before Cutover

One more scoped iteration should focus on:
- running one explicit dual-run smoke signoff using `docs/manual-smoke-checklist.md`
- deciding whether to switch the default core route after that signoff

After that, the repo should be in a position to make a safer primary-frontend cutover decision.
