# Release Notes

This document summarizes the current release-ready state of the
`feature/migrate-to-built-in-mcp` branch.

## Release Theme

The branch completes the move to the built-in Superset MCP path and finishes
the product as a single-stack assistant built on:

- `Next.js`
- `FastAPI`
- `Apache Superset`
- built-in `Superset MCP`

## What Changed In This Version

### Runtime and architecture

- retired the legacy external MCP runtime path from normal product usage;
- standardized product MCP access through the built-in client/runtime layer;
- added migration parity assets, tool matrix, and inventory enforcement;
- expanded Superset-side MCP extensions where direct parity was missing.

### Product UI and UX

- migrated the primary user UI to Next.js;
- added protected auth flow with login/register pages;
- added app routes for chat, preview, recommend, share, and scan;
- stabilized first-message delivery in a new chat;
- added per-chat settings and persistence;
- improved response quality and structured artifacts;
- added responsive shell behavior for desktop and mobile;
- added sticky composer, collapsible settings, and mobile helper toggle.

### Analytics workflows

- added live preview/recommend/share pages backed by FastAPI;
- improved chart-generation safety for numeric `year` dimensions;
- improved Pagila discovery and creation flows;
- enabled real chart and dashboard creation with follow-up link reuse;
- improved link handling so user-facing replies show labeled actions instead of
  raw URLs.

### Testing and operations

- added assistant API tests for auth, chats, viz, scan, and frontend logs;
- added MCP client unit coverage and tool inventory enforcement;
- added built-in MCP integration coverage;
- added Superset MCP extension/core unit coverage in CI;
- added deploy, health-check, and update/debug helpers for the single stack.

## User-Facing Outcome

The release is suitable for:

- direct question answering in chat;
- preview-driven chart creation;
- Pagila demo flows;
- mobile and desktop smoke demos;
- deployment as a Next.js + FastAPI assistant over Superset.

## Developer-Facing Outcome

Developers now have:

- one supported runtime path;
- a clearer API and frontend contract;
- migration parity docs and inventory coverage;
- CI jobs aligned with assistant, MCP, and Superset MCP behavior;
- documented deploy and debug entrypoints.

## Main Known Limitations

Current non-blocking limitations:

- share UI creates a new dashboard instead of selecting an existing one;
- browser-level E2E automation is lighter than Python/API coverage;
- scan is synchronous in the current UI;
- auth UI labels remain partially English;
- some final verification is still manual smoke rather than browser automation.

## Recommended Merge Notes

Before merge:

- keep unrelated local guardrails edits out of scope;
- do not include `superset-ai-assistant-mcp/data/auth.db`;
- treat `docs/user-guide.md`, `docs/developer-guide.md`,
  `docs/architecture.md`, `docs/release-notes.md`, and top-level `README.md`
  as the intended release doc set.

After merge:

- use [manual-smoke-checklist.md](/home/superset_ai/docs/manual-smoke-checklist.md)
  for smoke verification;
- use [deployment.md](/home/superset_ai/docs/deployment.md) and
  [production-rollout-runbook.md](/home/superset_ai/docs/production-rollout-runbook.md)
  for rollout;
- use [update-and-debug.md](/home/superset_ai/docs/update-and-debug.md) for
  day-2 operations.
