# Dual-Run Parity And Cutover Readiness

Status: historical archive.

Этот документ описывал dual-run audit между `Streamlit` и новым
`Next.js/FastAPI` stack до retirement старого UI/runtime path.

Исторический outcome:
- core-flow parity was accepted
- manual signoff passed
- phased primary switch was marked complete

Current state after repository consolidation:
- only `Next.js/FastAPI` remains as a supported runtime path
- Streamlit runtime/UI was removed

See:
- `docs/streamlit-retirement-summary.md`
- `docs/deployment.md`
- `docs/production-rollout-runbook.md`
