# Feedback Capture Template

Use this template after each manual scenario run. It is designed for quick copy/paste into an issue, PR comment, or follow-up Codex session.

## Short Form

```md
Persona:
Scenario:
Route(s):
Prompt / action:

Expected:
Actual:

Pass / fail:
Severity: low / medium / high / critical
Reproducible: yes / no / unclear

Suspected area:
- chat
- preview
- recommend
- share
- scan
- auth
- security / guardrails
- data quality
- links / Superset handoff
- UX copy / onboarding

Suspected root cause:

What looked good:

What looked bad:

Improvement idea:

Notes / screenshots / trace_id:
```

## Detailed Run Log

### Session Metadata

```md
Run date:
Tester:
Environment:
Branch / commit:
Stack:
- assistant-web:
- assistant-api:
- superset:
- mcp-http:
- pagila-db:

Current build notes:
- mode selector visible? yes / no
- any known flakiness before start?
```

### Scenario Record

```md
Persona:
Scenario id / name:
User goal:

Starting page:
Navigation path:

Exact prompt(s) / input(s):
1.
2.
3.

Expected system behavior:
1.
2.
3.

Actual behavior:
1.
2.
3.

Pass / fail:
Severity:
Confidence in result: high / medium / low

Observed strengths:
- 
- 

Observed weaknesses:
- 
- 

Where the issue seems to live:
- frontend UX
- frontend state
- backend answer quality
- backend guardrails
- Superset handoff
- data / demo dataset
- unclear

Suspected root cause:

Suggested next step:

Artifacts:
- screenshot:
- video:
- trace_id:
- related logs:
```

## Fast Comparison Template

Use this when comparing two variants of the same scenario, for example:
- two different prompts;
- two different chats;
- business vs technical mode, if the selector exists in your current build.

```md
Comparison target:

Variant A:
- prompt / setup:
- output summary:
- strengths:
- weaknesses:

Variant B:
- prompt / setup:
- output summary:
- strengths:
- weaknesses:

Winner:
Why:
```

## End-Of-Run Summary

```md
Run summary:

Top 3 things that worked:
1.
2.
3.

Top 3 issues:
1.
2.
3.

Most important blocker before demo:

Most important blocker before broader user testing:

Recommended next implementation iteration:
```

## Severity Guidance

- `low`: cosmetic, wording, or small friction; product value still clear.
- `medium`: user confusion or extra manual steps; feature still usable.
- `high`: key scenario works poorly or unreliably; demo/story weakened.
- `critical`: primary flow blocked or result misleading/unsafe.
