# The current→desired validation loop

After implementation starts, this is the loop that finishes the ticket. Its goal
is a single convergence: drive **`specs/current` to `specs/desired_program_model`**
while every named graph stays green, then promote. It composes two smaller loops
you already have — spec-double-compiler's desired/current migration loop and
test-graph's smart failure loop — into one close-out.

**Parent-only:** for an integration repo, every command here runs at the
integration **parent** worktree, which holds all constituent files as plain
files. Do not run per-constituent specs or graphs during the ticket — that happens
after fan-out, per `references/agent-tag-pr.md`.

## The four validation layers

Each iteration proves the slice at four layers. Require green at each before
advancing the model:

1. **Spec unit tests** — the generated spec-double self-tests / spec-unit adapters
   for the ticket.
   ```bash
   tla-spec-dev --spec-root specs run spec-unit-tests --ticket <ticket>
   ```
2. **Unit tests** — the repo's own suite for the changed code (its normal runner:
   `pytest`, `./gradlew test`, etc.).
3. **Test graph** — the named regression graphs from the issue, run via the
   test-graph scripts.
   ```bash
   TG=<test-graph-skill>/scripts
   $TG/discover.py <graph>      # confirm composition before running
   $TG/run.py <graph>           # one graph; or: $TG/run.py --all
   ```
4. **Spec graph (tla-spec-dev spec graph)** — the graph that exercises the
   generated spec doubles against the real adapters, so a spec/impl divergence
   fails loudly. Always include it when the ticket has a spec workflow.
   ```bash
   $TG/discover.py specWorkflow
   $TG/run.py specWorkflow
   ```

## The fifth layer: the goal signal (advisory, never a gate)

When the work order declares a goal — an epic assignment's `goals:` block or an
ordinary issue's `## Goals & evaluation` section — there is one more thing to run
before close, and it is deliberately **not** one of the four above:

```bash
<the declared local_signal>          # store its output under the evidence root
```

It sits outside the four layers because it answers a different question. The four
layers ask *did this land correctly*, and each one is pass/fail. The goal signal
asks *did this move what the work was for*, and it has no pass state at all —
only a measurement and a classification: moved as expected, moved less than
expected, no measurable movement, or moved the wrong way. Record it, do not gate
on it.

Keeping it a separate layer is the whole point. Folded into the four, it becomes
a fifth thing to make green, and an agent will start tuning to the metric,
re-running until a number improves, or reaching outside the slice to move it —
which is how a set of individually-defensible tickets ends up optimizing proxies
instead of delivering the outcome. The REQUIRED matrix decides pass/fail; the
named evaluation ticket decides the goal. Details, classifications, and the
reporting format: `references/goal-signal.md`.

## The loop, per slice

Repeat until the ticket-local model has converged:

1. **Advance the model toward desired.** Update ticket-local `desired/` with
   anything learned from the last slice (ticket breakdown, status, validation
   commands). Update ticket-local `current/` to the whole-program behavior that
   actually landed, preserving baseline behavior unless this slice changed it.
2. **Update adapters/tests first.** Add or update the ticket-local spec-unit
   adapters and, if the observable surface moved, the External/Internal test-graph
   adapters and nodes — before or alongside the code.
3. **Run TLC + the four layers** (above) for the slice. Prefer the **narrow graph**
   for the slice while iterating; run the full named set before close-out.
4. **On a graph failure, don't blindly rerun the whole graph.** Use test-graph's
   smart failure loop: read `build/validation-reports/<runId>/report.md`, rerun the
   single failed node from its saved context (`run.py <graph> --resume-from-build
   <dir> --run-only-node <id>`), iterate on that node, then rerun the whole graph
   once from the start to confirm ordering and fresh context.
5. **Close the slice's ticket.** When ticket-local `current` semantically equals
   ticket-local `desired`, record evidence and close:
   ```bash
   tla-spec-dev --spec-root specs close ticket <ticket> \
     --result <evidence-path> --summary "<what landed>"
   ```
   Close moves the ticket dir to history, replaces project `specs/current` with the
   ticket's `desired/`, and merges ticket-local test-graph artifacts into project
   specs.
6. **Commit** the spec change, close record, and evidence together.

## Convergence and promotion

Keep looping slices until **project `specs/current` semantically equals
`specs/desired_program_model`** and the full named graph set (including the spec
graph) is green. Then promote the converged model into the accepted baseline and
clean up the workflow directories:

```bash
python <tla-spec-dev>/scripts/close_tickets.py --repo-root . \
  --summary "Promoted desired/current into program_model"
```

Promotion writes the workflow close record, replaces `program_model` with the
converged model, and removes `specs/current` + `specs/desired_program_model` once
they carry no distinct planning state. After this, the spec workflow is closed and
you return to `references/complete.md` to finish the PR and issue.

## Definition of done for the loop

- [ ] Spec unit tests green (`run spec-unit-tests --ticket <ticket>`)
- [ ] Repo unit tests green
- [ ] Named test_graph graphs green (smart-failure-loop clean, full rerun clean)
- [ ] tla-spec-dev spec graph green (`specWorkflow`)
- [ ] Every ticket closed in `ticket_plan.yaml`; `current == desired`
- [ ] Model promoted into `program_model`; workflow dirs cleaned
- [ ] Evidence recorded and committed

The goal signal has its own definition of done, and "green" is not part of it:

- [ ] Every declared `local_signal` run once (or `N/A: <reason>` recorded)
- [ ] Its output stored under the evidence root and classified
- [ ] The classification reported in the PR body — including "no measurable
      movement" and "moved the wrong way"

**Recorded and reported**, not green. A signal that moved the wrong way leaves
this loop done; it is reported and, where it shows the goal is unreachable from
this slice, filed as a deferred finding. It never blocks close, and it is never
grounds for another lap.
