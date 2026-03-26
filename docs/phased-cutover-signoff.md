# Phased Primary-UI Cutover Signoff

Status: `NO-GO` until the final manual browser signoff is executed and recorded.

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

It is not a replacement for the last manual browser signoff required by the
cutover plan.

## Repo-Backed Findings

### Primary path is operationally wired

The repository now provides an explicit primary launch path in
`docker-compose.dev.yml`:
- `assistant-api` on `:8100`
- `assistant-web` on `:3001`

The fallback path remains available:
- `assistant` (Streamlit) on `:8051`

### Tiny blocker fixed in this signoff pass

The direct blocker found in this pass was that `assistant-web` still launched
via `next dev`, which is not strong enough for final operational signoff.

That blocker is now closed by:
- making `assistant-web` run in production-like mode by default
- building and starting Next.js through `docker/dev/start-nextjs-primary.sh`
- adding a dedicated `.next` volume and a longer startup health window

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

## Decision

### Current decision: `NO-GO`

Reason:
- there is no remaining repo/code blocker in the primary-path wiring
- but the cutover plan still requires the final manual browser signoff to be
  executed and recorded before the actual switch

This means the repository is operationally prepared for the switch, but the
actual switch should not be declared complete until the last human-run signoff
is done.

## Exact Remaining Manual Validation

The remaining required signoff is:

1. Run `docs/manual-smoke-checklist.md` against the primary `Next.js/FastAPI`
   path in a browser.
2. Run `docs/demo-query-pack.md` on the Pagila demo path through the primary
   UI.
3. Run the Streamlit fallback sanity from `docs/phased-cutover-plan.md` for
   `US2-US5`.
4. Confirm log correlation for at least:
   - one normal chat request
   - one blocked chat request
   - one preview/recommend/share flow
   - one schema scan

These steps remain manual because they validate browser-visible UX, fallback
availability, and operator signoff expectations that are not fully captured by
the current automated suite.

## Switch Recommendation

Once the manual validation above is completed successfully:
- the decision can move from `NO-GO` to `GO`
- the actual primary UI switch can proceed
- Streamlit should remain available during the rollout window as fallback for
  `US2-US5`

## Next Step

The next step is unambiguous:
- execute the final browser signoff from the existing runbooks
- if it passes, perform the actual primary-UI switch
