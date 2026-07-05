# Receiving an agent-tagged PR (constituent side)

This is the other end of the fan-out. An integration repo made a cross-repo change,
propagated it out, and opened a `feature/<ticket>` PR against **this** repo (a
constituent) with an agent tag. You are the agent that picked up that tag. Your job
is to make this one repo's specs and validation catch up to its slice of the
change, then hand the PR back for review.

The integration parent already validated the change as an integrated whole. You are
**not** re-validating the whole system — you are validating **this constituent** on
its own program model and test graph.

## 0. Orient

```bash
gh pr view <pr> --json headRefName,body,labels    # ticket id + parent PR link live here
git fetch origin
git checkout feature/<ticket>                      # the branch propagate.sh pushed
```

The branch already carries the constituent's slice of the diff (propagation
committed it). Work on that branch; do not open a new worktree unless you want
isolation — this repo's `feature/<ticket>` is already the change.

## 1. Update the program-model specs

Bring this repo's TLA+ program model in line with the behavior the slice
introduced. Operate the spec workflow **for this repo** (spec-double-compiler /
`tla-spec-dev`):

- If the slice changed state-machine behavior, open a workflow and advance the
  model just as in a normal ticket:
  ```bash
  tla-spec-dev --spec-root specs scaffold workflow <ticket> "<parent ticket title>"
  tla-spec-dev --spec-root specs open ticket <ticket>
  ```
  Edit ticket-local `desired/` to this repo's ending state, update `current/` to
  what the slice actually implements, and regenerate the spec doubles.
- If the slice did not move this repo's observable/internal behavior, update
  `program_model` only where the change touches it and note why no ticket workflow
  is needed.

## 2. Update test-graph adapters and nodes if necessary

If the slice changed what a harness can drive or observe in this repo, extend the
test graph so it exercises the new behavior — don't rely on the parent's graph:

- Add or update **test-graph adapters** (Internal for spec-unit, External for
  harness-driven) so the generated spec cases map to real entrypoints.
- Add or update **test-graph nodes** (testbed/fixture/action/assertion/evidence)
  for any new externally observable behavior, with explicit assertions against the
  real boundary.
- Verify composition before running:
  ```bash
  TG=<test-graph-skill>/scripts
  $TG/discover.py <graph>
  ```

Skip this only when the slice genuinely added no observable behavior in this repo.

## 3. Run the loop for this repo

Same four layers as the parent loop (`references/validation-loop.md`), scoped to
this constituent. Require green at each; use test-graph's smart failure loop on
graph failures.

```bash
tla-spec-dev --spec-root specs run spec-unit-tests --ticket <ticket>   # spec unit tests
<repo's unit test runner>                                              # unit tests, e.g. pytest / ./gradlew test
$TG/run.py <graph>                                                     # test graph
$TG/run.py specWorkflow                                                # spec graph (if a spec workflow ran)
```

If you opened a spec workflow in step 1, close it once `current == desired`:

```bash
tla-spec-dev --spec-root specs close ticket <ticket> --result <evidence-path>
# and promote when the workflow is fully converged:
python <tla-spec-dev-skill>/scripts/close_tickets.py --repo-root .
```

## 4. Commit and push for review

Land the spec, adapter/node, and evidence changes on top of the propagated slice,
then push the same branch so the existing PR updates:

```bash
git add -A
git commit -m "<ticket>: constituent specs + test-graph + validation for integration change"
git push origin feature/<ticket>
```

Leave the PR **open for review** — do not merge it yourself. Note on the PR that
the constituent loop is green (spec-unit, unit, test-graph, spec-graph) and
reference the parent PR. The integration tracking issue and human/CI review own the
merge.

## Receiver checklist

- [ ] On `feature/<ticket>`; ticket id + parent PR captured from the PR
- [ ] Program-model specs updated for this repo's slice (workflow if behavior moved)
- [ ] Test-graph adapters/nodes updated if observable behavior changed
- [ ] Spec unit tests, unit tests, test graph, and spec graph all green
- [ ] Spec workflow closed/promoted if one was opened
- [ ] Committed and pushed to the same `feature/<ticket>` branch
- [ ] PR left open for review with a green-loop summary and parent-PR link
