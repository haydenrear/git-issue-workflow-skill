# Role 3 — Perform the ticket (complete)

Provisioning left you a worktree on `feature/<ticket>` with the spec workflow
open. This is the rest: implement, run the loop to green, close the spec workflow
and the issue, verify the merge, open the PR, and — for an integration repo — fan
out to the constituents.

## 1. Implement in the worktree

Edit in the worktree only, never the primary checkout.

- **PLAIN repo:** edit the files the References section pointed at.
- **INTEGRATION repo:** edit across constituent files in the **one parent
  worktree** — `constituents/<name>/...` are plain files here. Do not run git
  inside a constituent directory; there is no `.git` there during the ticket.

## 2. Run the validation loop to green

Drive `specs/current` → `specs/desired_program_model` with all four layers green,
per `references/validation-loop.md`. For an integration repo this loop runs **at
the parent only**. Do not exit this step until the loop's definition-of-done is
fully checked.

## 3. Close the spec workflow

The loop already closes each ticket and promotes the model when `current ==
desired`. Confirm the workflow is actually closed out, not just the last ticket:

```bash
# every ticket closed in the plan, model promoted, workflow dirs removed
python <tla-spec-dev-skill>/scripts/close_tickets.py --repo-root . \
  --summary "Promoted desired/current into program_model"
ls specs/                     # specs/current and specs/desired_program_model should be gone
```

Attach the test-graph reports to the in-repo spec ticket the workflow tracked, so
the passing evidence is tied to the ticket that closed — not only to the PR.

## 4. Commit the change

Only after the loop is green and the spec workflow is closed:

```bash
git add -A
git commit -m "<ticket>: <what changed> — specs, graph, adapters, tests"
```

## 5. Bring the branch back and verify the merge

### PLAIN repo

Push and open the PR; the merge is done by review/CI, so verify **after** it
merges before removing the worktree.

```bash
git push -u origin feature/<ticket>
gh pr create --fill --body "Closes #<n>

Graphs run: <named graphs incl. specWorkflow>. Reports attached to the spec ticket."
```

Verify it actually merged before cleanup:

```bash
gh pr view --json state,mergedAt,mergeCommit   # state MERGED, mergedAt set
git -C <repo-root> fetch origin
git -C <repo-root> branch --merged origin/main | grep feature/<ticket>   # branch is in main
```

### INTEGRATION repo

Merge the parent feature branch back into the integration **main** tree, then let
`git-integration-repo`'s verifier assert the tree is clean and every constituent is
still wired — this is how you confirm the change landed properly across the parent:

```bash
INT=<git-integration-repo-skill>/scripts
git -C <repo-root> merge --no-ff feature/<ticket>
$INT/verify.sh                 # parent tree clean + every constituent has its .git + origin
```

A dirty tree or an unwired constituent here means the merge is not safe to fan out
— stop and reconcile before step 7.

## 6. Remove the worktree

Only once the merge is verified (PLAIN: PR merged; INTEGRATION: merged to main and
`verify.sh` clean):

```bash
git worktree remove ../wt-<ticket>          # PLAIN
git worktree remove ../<repo>-<ticket>      # INTEGRATION parent worktree
```

## 7. Close the GitHub issue

If the PR carried `Closes #<n>`, merging closes the issue automatically — confirm
it. Otherwise close it with a summary:

```bash
gh issue view <n> --json state,closed          # confirm CLOSED after PR merge
# if still open:
gh issue close <n> --comment "Completed on feature/<ticket>. Graphs: <named graphs incl. specWorkflow>. Spec workflow promoted; reports attached to the spec ticket."
```

## 8. INTEGRATION only — fan out to constituents

For an integration repo, the parent PR is not the end. Each constituent needs its
own `feature/<ticket>` branch, PR, and **agent tag**, because each constituent runs
its *own* spec/test-graph loops downstream. Do this now via
`references/integration-fanout.md`.

## Close-out checklist

- [ ] Implemented in the worktree (parent worktree for integration)
- [ ] Validation loop green; spec workflow promoted and closed
- [ ] Test-graph reports attached to the in-repo spec ticket
- [ ] Committed and pushed to `feature/<ticket>`
- [ ] PR opened with `Closes #<n>`; merge verified
- [ ] INTEGRATION: parent merged to main and `verify.sh` clean
- [ ] Worktree removed
- [ ] GitHub issue closed
- [ ] INTEGRATION: fan-out done (`references/integration-fanout.md`)
