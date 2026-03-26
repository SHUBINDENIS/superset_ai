# Phased Primary-UI Cutover Signoff

Status: `GO` - manual signoff completed successfully and the repo now treats
`Next.js/FastAPI` as the default primary UI path for migrated core flows.

This document captures the final repo-backed operational signoff pass for the
phased primary-UI cutover where:
- `Next.js + FastAPI` is the primary path for migrated core flows
- `Streamlit` remains the fallback/helper-admin path for `US2-US5`

## Scope Of This Signoff

This signoff is based on the existing repo-backed source documents:
- `docs/phased-cutover-plan.md`
- `docs/manual-smoke-checklist.md`
- `docs/demo-query-pack.md`
- `docs/dual-run-parity-readiness.md`

It is intentionally limited to:
- launch/readiness of the primary path
- launch/readiness of the fallback path
- final blocker-level assessment for the actual switch decision

It now records the completed signoff outcome used for the actual switch.

## Repo-Backed Findings

### Primary path is operationally wired

The repository now provides an explicit primary launch path in
`docker-compose.dev.yml`:
- `assistant-api` on `:8100`
- `assistant-web` on `:3001`

The fallback path remains available:
- `assistant` (Streamlit) on `:8051`

### Tiny blocker fixes closed before the final switch

The direct blockers found during final signoff were:
- `assistant-web` still launched via `next dev`, which was too weak for final
  operational signoff
- chat replies rendered `![Chart Preview](explore-link)` as a broken image,
  because the reply contained a Superset explore URL rather than a real image

These blockers are now closed by:
- making `assistant-web` run in production-like mode by default
- building and starting Next.js through `docker/dev/start-nextjs-primary.sh`
- adding a dedicated `.next` volume and a longer startup health window
- normalizing pseudo-preview markdown in the Next.js chat renderer so broken
  inline images are no longer shown for explore links

### Runtime checks completed in this pass

The following checks were completed against the current repository state:

- `docker compose --env-file .env.dev -f docker-compose.dev.yml config`
- `docker compose --env-file .env.dev -f docker-compose.dev.yml ps`
- `curl http://127.0.0.1:8100/api/health`
- `curl -I http://127.0.0.1:3001/login`
- `curl -I http://127.0.0.1:8051`
- register/login/logout via the primary origin:
  - `POST http://127.0.0.1:3001/api/auth/register`
  - `GET  http://127.0.0.1:3001/api/auth/me`
  - `POST http://127.0.0.1:3001/api/auth/logout`
  - `GET  http://127.0.0.1:3001/api/auth/me` -> `401` after logout

Observed outcome:
- compose config is valid
- `assistant-api` is healthy
- `assistant-web` is healthy
- Streamlit fallback is reachable
- primary-origin auth cookie flow works correctly through Next.js proxying

### Manual signoff completed

The final required manual validation has now been completed successfully:
- `docs/manual-smoke-checklist.md` passed on `Next.js/FastAPI`
- `docs/demo-query-pack.md` passed on Pagila through the primary UI
- Streamlit fallback sanity passed for `US2-US5`
- log correlation was confirmed for the required core flows

## Decision

### Current decision: `GO`

Reason:
- there is no remaining repo/code blocker in the primary-path wiring
- the required manual browser signoff has been completed and recorded
- rollback remains available through the Streamlit fallback path

This means the repository is no longer merely prepared for the switch; the
actual phased primary switch can be treated as complete at the repo level.

## Current Default Operational Model

After this signoff:
- default primary UI: `http://<host>:3001/login`
- default primary API: `http://<host>:8100/api/health`
- Streamlit fallback/admin UI: `http://<host>:8051`
- Streamlit remains available during the rollout window only for:
  - `US2`
  - `US3`
  - `US4`
  - `US5`
  - rollback/fallback operations

## Next Step

The next step is unambiguous:
- operate `Next.js/FastAPI` as the default primary path
- keep Streamlit available as rollback/fallback for `US2-US5`
- do not treat Streamlit as the normal default user entrypoint anymore
