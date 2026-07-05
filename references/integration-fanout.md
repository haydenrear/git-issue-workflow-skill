# Integration fan-out — per-constituent branches, PRs, and agent tags

For an integration repo, completing the ticket at the parent is only half the job.
The parent PR proves the cross-repo change as a whole; the fan-out delivers each
constituent its **own** slice as a branch and PR so each sub-repo can run its own
spec and test-graph loops independently.

**Precondition:** the change is merged into the integration **main** tree (not
still in the worktree) and `git-integration-repo`'s `verify.sh` is clean — see
`references/complete.md` step 5. Propagation reads each constituent's working-tree
status in the main tree.

## Why every constituent gets its own loop

During the ticket you ran the spec workflow and test graph **once, at the parent**
(load-bearing rule 1 in `SKILL.md`). That validated the change as an integrated
whole. But each constituent is also its own repo with its own `program_model` and
its own `test_graph`. So each needs to:

- update its **program-model specs** for its slice,
- extend its **test-graph adapters and nodes** if the slice changed observable
  behavior, and
- run its own **spec-unit / unit / test-graph / spec-graph** loop.

You do **not** do that work here. You hand it off: open the PR with an agent tag,
and the receiving agent runs exactly that loop via `references/agent-tag-pr.md`.

## 1. Propagate

Use `git-integration-repo`'s `propagate.sh`. It is a dry run by default — inspect
before pushing.

```bash
INT=<git-integration-repo-skill>/scripts

$INT/propagate.sh <ticket>              # DRY RUN: branch + commit per changed constituent
$INT/propagate.sh <ticket> --push       # also push feature/<ticket> to each origin
$INT/propagate.sh <ticket> --push --mr   # also open a PR/MR per constituent + one tracking issue
```

Per changed constituent it: detects the change (skips unchanged ones), creates or
switches to `feature/<ticket>`, commits the slice, pushes with `--push`, and opens
a PR/MR against the constituent's default branch with `--mr` (using `gh` or `glab`
per `[integration].host`). Re-running is safe and converges — unchanged
constituents are skipped.

## 2. Add the agent tag to each constituent PR

`propagate.sh` opens the PRs and files one coordinating tracking issue, but the
**agent tag** is what actually routes each PR to an implementing agent. Add it to
every constituent PR the propagation opened. The tag is whatever marker your
automation watches to hand a PR to an agent — a label and/or a body marker. Keep it
identical across constituents so one runner picks them all up.

```bash
# per constituent PR (repo = the constituent's origin)
gh pr edit <pr> --repo <owner>/<constituent> --add-label "<agent-label>"
# or, if your runner triggers on a body marker, ensure the PR body carries it:
gh pr comment <pr> --repo <owner>/<constituent> --body "<agent-trigger-marker> ticket=<ticket>"
```

Give the receiving agent what it needs in the tag/body: the ticket id, the parent
PR link, and a one-line pointer to run its own loop (`references/agent-tag-pr.md`).
For GitLab hosts, use `glab mr` equivalents (`glab mr update`, labels via
`--label`).

## 3. Record the fan-out

The tracking issue `propagate.sh` files (in `[integration].tracker`, or written to
`.integration/tmp/<ticket>-issue.md` when no tracker/`--mr`) is the coordination
record: it lists each constituent, its `feature/<ticket>` branch, and its PR link.
Confirm every changed constituent appears with a pushed branch, an open PR, and the
agent tag applied.

## Fan-out checklist

- [ ] Change merged to integration main; `verify.sh` clean
- [ ] `propagate.sh <ticket> --push --mr` run; every changed constituent has a
      pushed `feature/<ticket>` branch and an open PR
- [ ] Agent tag applied to every constituent PR (label and/or body marker)
- [ ] Each tag carries ticket id + parent PR link + pointer to `agent-tag-pr.md`
- [ ] Tracking issue lists all constituents, branches, and PR links
- [ ] Unchanged constituents correctly skipped

The handoff is complete when branches are pushed, PRs are open and tagged, and the
tracking issue is filed. Each constituent's own loop then runs downstream.
