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
5. Run focused deterministic checks and verify the exact reviewed revision before merge.
6. Stop when the bounded release/capability is verified; if no new release or revision exists, do not manufacture activity.

## Branch lifecycle

- Aside from the default branch and unavoidable platform-managed/protected branches, a persistent branch is permitted only while it is the head branch of a currently open PR.
- Creating a work branch creates an obligation to open or reuse its canonical PR immediately; do not use branches as backlog, continuation state, backup, archive, or evidence storage.
- After a PR is merged or closed, delete its head branch after verifying PR/main state. A branch with no open PR is an orphan and must be deleted.
- Before and after work, compare repository branches with open PR heads. Do not report cleanup/fixed point while an orphan task branch remains.
- If the available tool cannot delete a branch, record that as a tooling blocker and do not claim cleanup complete. Never create another orphan branch as a workaround.

## Merge and release are separate

### PR merge conditions

A PR may merge when the repository-local release/vintage contract is correct on the exact head revision: BLS identity/period/revision semantics are preserved, deterministic tests pass, generated artifacts are reproducible when affected, and no unresolved review or correctness blocker remains.

A future BLS release, post-merge live fetch, public deployment, consensus availability, or market reaction is **not** a merge condition unless the PR specifically changes the release mechanism and pre-merge validation belongs to the bounded change.

### Product/data release conditions

Release is a separate post-merge decision. Treat employment data/views as released only after the merged `main` revision is read back and the release surfaces in scope are actually verified, including the official release observation when required, published artifacts/API/UI, deployment identity, and rollback/rebuild path where applicable.

A merged PR does not prove a new BLS release was acquired or published. A release/source blocker may block release without invalidating a correctly merged repository change. Report merge and release independently.

## Boundaries

- Preliminary and revised payroll values are distinct point-in-time observations.
- Do not infer missing series values, release times, consensus or revision magnitudes.
- Do not execute trades or account actions.
- Unobserved source, CI, deployment or market-reaction outcomes remain unverified.

## Completion report

Report verified releases/revisions Before -> After, primary source/canonical artifact, Issue/PR/commit/check evidence, then report `merged` and `released` separately with direct evidence for each. Include branch cleanup state, manual work removed and remaining blocker.

## Outcome-first task interpretation (Altitude / Depth / Range / Speed)

- **Altitude:** Interpret a task as a verifiable user outcome, not only the named intermediate step. Infer the smallest justified acceptance criteria from the request and current repository state; do not silently expand scope or override explicit instructions.
- **Depth:** Use primary/current evidence and real domain tools and methods. Verify the actual postcondition independently of agent self-report, preferably on the exact changed revision or target runtime.
- **Range:** Combine code, data, tests, runtime/UI, and domain expertise when that materially improves the outcome, while respecting canonical owners and avoiding duplicate systems.
- **Speed:** Complete authorized read-only and reversible work through implementation, focused checks, and read-back without unnecessary approval loops. Bound retries and stop at the proven outcome.
- These principles never bypass repository-specific security, privacy, permission, publication, spending, destructive-action, or release boundaries. State verified results and any remaining `UNVERIFIED` layers.
