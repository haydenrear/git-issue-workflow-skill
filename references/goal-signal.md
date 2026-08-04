# Goals, local signals, and evaluation tickets

A work order says what to change. A **goal** says what should be measurably
better once it is changed, and names the command that decides it. This reference
is the implementer's half of that contract: what to read before implementing,
what to run during validation, what to report, and — for a ticket whose whole
slice *is* the measurement — how to run and report the goal itself.

The authoring half lives upstream and is the source of truth for field names and
semantics: `git-epic-workflow/references/goals-and-evaluation.md` (kinds,
baselines, contribution kinds, warn-vs-error rules) and its
`$SKILL_MANAGER_HOME/skills/git-epic-workflow/scripts/validate_epic_plan.py`
(the plan schema, shipped by that unit). Never invent a goal, a
baseline, or a target here. If the work order declares none, this reference does
not apply; say so at close-out and move on.

## Where the goal context comes from

- **Epic ticket** — the marker-delimited assignment carries a `goals:` block, one
  entry per goal this ticket relates to. `references/epic-ticket.md` §1 verifies
  it against the canonical plan before anything else happens.
- **Ordinary or integration ticket** — the issue carries a `## Goals & evaluation`
  section written by `git-issue`. It is prose, not YAML, and it is filled or
  explicitly `N/A: <reason>` — never absent because nobody bothered.

Both shapes carry the same five things, and those five are all this skill needs:
the goal, how this ticket relates to it, what result the change should produce,
what cheap command predicts that result here, and who decides the goal for real.

## Field reference

Assignment `goals[]` entries on an implementation ticket:

| Field | Meaning |
|---|---|
| `goal` | Stable goal ID. Never reused, never renamed. |
| `kind` | `perf` \| `eval` \| `integration` \| `quality`. |
| `statement` | What should be measurably better after the epic. |
| `metric` | The measured quantity. |
| `baseline` | Today's value plus the commit it was measured on, or `unmeasured`. |
| `target` | The threshold that counts as success. |
| `decided_by.ticket` | The `role: evaluation` ticket that decides this goal. |
| `decided_by.harness` | The command that ticket runs on the integrated epic. |
| `contribution` | `direct` \| `enabling` \| `guard`. |
| `expected_effect` | Direction and magnitude **this ticket** should produce. |
| `local_signal` | A cheap in-worktree command, or `N/A: <reason>`. |

An evaluation ticket carries `role: evaluation` and `owns_goals: [...]` under
`ticket:`, and its `goals[]` entries replace `decided_by` with `harness` and
`evidence_root` — the command it runs and where its results land.

The canonical plan spells the same facts differently, which matters only for the
equality check in `references/epic-ticket.md` §1: the plan holds goal metadata
once under root `epic_goals[]` (`id`, `kind`, `statement`, `metric`, `harness`,
`baseline.value` / `baseline.measured_at` / `baseline.evidence`, `target`,
`evaluation_ticket`, `evidence_root`) and the per-ticket relation under that
ticket's `goals[]` (`goal`, `contribution`, `expected_effect`, `local_signal`),
plus `role` and `owns_goals`. Compare each rendered field against the plan field
it was rendered from — `decided_by.ticket` against `evaluation_ticket`,
`decided_by.harness` against the goal's `harness`, `baseline` against
`baseline.value` and the commit in `baseline.measured_at` — not name against
name.

## Before implementing: read the expected effect

Read the goal entries **first**, before the first edit. `expected_effect` is the
result the change is aiming at, and the relation exists to weight your work
toward the measured outcome — a ticket agent who implements the slice and reads
the goal afterwards has already made every design choice without it.

What each contribution kind asks of you:

- **`direct`** — your change is expected to move the metric. `expected_effect`
  states the direction and magnitude. When two implementations satisfy the
  assigned semantic delta equally, the expected effect is the tiebreaker.
- **`enabling`** — no movement expected from this ticket; it unblocks a `direct`
  one (a harness, a refactor, a fixture). What matters is that the thing it
  unblocks can actually use it — a harness whose output the evaluation ticket
  cannot consume is an enabling ticket that failed at exactly its job.
- **`guard`** — this metric must **not** regress while you work on another goal.
  The `local_signal` is the regression check, and it is the one signal you should
  expect to be flat.

Reading the goal never widens the assignment. The semantic delta and the conflict
keys still bound the work; the goal tells you which way to lean inside them.

## During validation: run the local signal

After the REQUIRED validation matrix is green (`references/validation-loop.md`),
and before close:

1. Run each declared `local_signal` in the ticket worktree. `N/A: <reason>` means
   there is nothing to run — record the reason, do not invent a substitute.
2. Store its output under the ticket evidence root, beside the validation
   reports. A number quoted in the PR body with no durable file behind it is not
   evidence; the evaluation ticket cannot re-read your terminal.
3. Compare it with `expected_effect` and classify it as exactly one of:
   - **moved as expected**
   - **moved less than expected**
   - **no measurable movement**
   - **moved the wrong way**

All four are reportable outcomes. "No measurable movement" in particular is a
result — omitting it reads as a signal nobody ran.

### Precedence: what decides what

This is the part that must not blur:

| Decides | What |
|---|---|
| The REQUIRED validation matrix | Whether this ticket passes or fails. |
| The local signal | Nothing. It is advisory. |
| The evaluation ticket | Whether the goal is met. |

So a local signal that moved the wrong way does **not** fail the ticket, and one
that moved beautifully does **not** excuse a red matrix entry. Concretely, never:

- treat the local signal as a gate, or block close on it;
- tune the implementation to the metric — the semantic delta is the deliverable,
  and a change that moves the number without the delta is off-assignment;
- re-run the signal selectively until a better number appears, or report the best
  of several runs. Report the run that happened;
- widen scope, touch surfaces outside the conflict keys, or weaken a REQUIRED
  validation entry to chase the number.

The failure mode this prevents is the one every measured system produces: a fleet
of tickets optimizing their local proxy, each individually defensible, none
delivering the epic. The integrated evaluation is what the epic is judged on, and
that is deliberately not yours to run.

### When the goal is unreachable from this slice

Sometimes the signal shows the goal cannot be reached by the planned slice at
all — the bottleneck is elsewhere, the effect is an order of magnitude short, the
metric is dominated by something this ticket does not touch. That is real
information and it belongs to the epic owner, not to your scope.

Finish the assigned semantic delta, then file a **deferred finding** describing
what the goal would actually require: the surfaces a real fix would touch, the
measurement that showed it, and what you did instead. Do not expand this ticket
into the fix. Plan feedback is not ticket work, and a ticket that quietly grows
to chase a metric is the exact thing the deferment policy exists to stop.

## Reporting: the `## Goal contribution` PR section

Every ticket that declares a goal carries this section in its PR body, one row
per declared goal:

```markdown
## Goal contribution

| Goal | Contribution | Expected effect | Measured local signal | Decided by |
| --- | --- | --- | --- | --- |
| GOAL-ingest-p99 | direct | -120ms p99 from write batching; throughput unchanged | p99 431ms → 288ms (moved less than expected) — `results/<ticket>/goal/ingest.json` | EPIC-9 |
| GOAL-answer-match | guard | no regression | 0.83 → 0.83 (no measurable movement) — `results/<ticket>/goal/eval.json` | EPIC-11 |
```

Rules for the rows:

- One row per **declared** goal, including every goal whose signal was `N/A` —
  write `N/A: <reason>` in the measured column rather than dropping the row.
- Name the classification (as expected / less than expected / no measurable
  movement / wrong way) and link the durable evidence path.
- A ticket with no declared goal writes `## Goal contribution` + `None declared`
  — one line, so a reader can tell "no goal" from "goal ignored".

For an ordinary or integration ticket the same section goes in the PR body
(`references/complete.md` §5); "decided by" is whatever the issue's
`## Goals & evaluation` section named — a later evaluation issue, or this
issue's own harness run.

## The evaluation ticket (`role: evaluation`)

An evaluation ticket is a real ticket — a slice, a spec ticket, a close record,
a PR — whose slice is the **measurement** rather than a behavioral delta. It
decides the goals in its `owns_goals` list. Everything in
`references/epic-ticket.md` still applies; these are the differences.

### It runs last, on purpose

- It depends on every ticket contributing to the goals it owns, and the plan
  makes that reachable through `depends_on`. Verify it the ordinary way (§1):
  each contributor's PR merged into the epic branch, its merge commit reachable
  from the latest remote epic tip. A green contributor branch is not a merged
  contributor.
- It promotes **after** every one of those contributors. Its
  `promotion_predecessor` serializes it there; do not close it early because the
  code is trivially small. An evaluation that runs before the work it evaluates
  measures the wrong tree.

### It measures the integrated tip, from a fresh start

For each goal in `owns_goals`, run that goal's `harness` — the exact command,
unmodified — on the reconciled epic tip after §5's rebase/merge, from a clean
start: no warm caches carried from a previous attempt, no partially-completed
run resumed, no node re-run in isolation. Write results under the goal's
`evidence_root` (not the ticket evidence root — the goal's, so finalization can
find every measurement of a goal in one place).

A harness that fails to run is `unmeasured` with the reason. It is not a zero,
and it is not silently omitted.

### It reports baseline → measured → target with a verdict

```markdown
## Goal verdicts

| Goal | Kind | Baseline | Measured | Target | Verdict | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| GOAL-ingest-p99 | perf | p99 412ms, 5.1k events/s @ 8f21c0d | p99 268ms, 5.2k events/s | p99 <= 250ms and throughput >= 5.0k events/s | missed | results/epic-ingest/goals/GOAL-ingest-p99/run.json |
```

Verdicts are exactly `met`, `missed`, or `unmeasured` (with a reason). Report the
run that happened.

### What it must never do

- **Never edit a target to match a result.** The target is the epic owner's
  agreement with the user; moving it deletes the only thing the measurement was
  against.
- **Never re-run selectively until a number passes**, and never report the best
  of several runs. If a run is genuinely invalid — wrong tree, harness crash,
  contaminated environment — say that, discard it explicitly in the PR body, and
  re-run the whole thing from a fresh start.
- **Never fix the regressions it finds.** A shortfall or a regression uncovered
  here is a deferred finding for the epic owner, with the measurement attached.
  Fixing it inside the evaluation ticket destroys the only unbiased measurement
  of the epic — the ticket would then be evaluating its own patch.
- **Never fail the epic on its own.** A `missed` verdict hands the owner a
  decision at finalization (add a ticket, accept the shortfall with a recorded
  reason, re-scope the goal). This ticket's job is to make that decision
  informed, and then stop.

Its PR body carries the `## Goal verdicts` table above in place of the
per-contributor `## Goal contribution` rows, plus everything §7 already requires.
