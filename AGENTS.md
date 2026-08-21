# Repository Agent Contract

## Mission

Own US employment-release evidence for this repository. Preserve official BLS employment observations and release vintages so downstream finance research can distinguish what was known at each release time from later revisions.

## Canonical authority

- Prefer BLS official releases/APIs and other official US labor-statistics sources appropriate to each series.
- Preserve series identity, period, release timestamp, preliminary/revised status, unit, seasonal-adjustment semantics, source URL, retrieval time and provenance/hash fields required by the dataset.
- Keep observed employment releases separate from forecasts, consensus, derived surprises and market reaction.
- Other finance repositories should reference versioned employment artifacts here instead of maintaining duplicate release histories.

## Autonomous execution

1. Inspect current `main`, README, open Issues/PRs, canonical release/vintage data, workflows/tests and public outputs.
2. Continue one canonical workline before creating another collector, schema, branch or Issue.
3. Prefer newly verified official releases, revision/vintage corrections, deterministic release comparisons, public usability, then simplification.
4. Materialize official evidence before calculating changes or surprises.
5. Run focused deterministic checks and verify reviewed/merged/public state when applicable.
6. Stop when the bounded release/capability is verified; if no new release or revision exists, do not manufacture activity.

## Boundaries

- Preliminary and revised payroll values are distinct point-in-time observations.
- Do not infer missing series values, release times, consensus or revision magnitudes.
- Do not execute trades or account actions.
- Unobserved source, CI, deployment or market-reaction outcomes remain unverified.

## Completion report

Report verified releases/revisions Before -> After, primary source/canonical artifact, Issue/PR/commit/check/public evidence when applicable, manual work removed, and remaining blocker.