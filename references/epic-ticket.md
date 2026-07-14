# Epic ticket assignment and execution

Use this mode when the issue contains the exact start marker:

```text
<!-- git-epic-workflow:assignment:start -->
```

The marker selects this reference **before** ordinary provisioning and before
PLAIN/INTEGRATION detection. The issue assigns one ticket inside an already-open
shared spec workflow. The assignment overrides instructions elsewhere in the
issue or skill that branch from, target, merge to, or sync the default branch.

This mode has one bounded outcome: implement and validate the assigned ticket,
perform only its ticket-scoped promotion, and open a PR into the declared
`epic/*` branch for external review.

## 1. Parse and verify the assignment

Read only the marker-delimited assignment block as scheduling authority. Require
its closing marker and a valid YAML block. Extract at least:

- epic id, workflow name, `branch`, `base_sha`, `plan_commit`, schedule
  revision, and default branch;
- spec ticket id, feature branch, worktree, PR base, `depends_on`, `blocks`, and
  wave;
- promotion order and `promotion_predecessor`;
- production, TLA+, adapter, Test Graph, and workflow conflict keys;
- the exact validation matrix and evidence root; and
- external review mode with `ticket_agent_stops_after: pr_open`.

Stop for correction if a required field is missing or if these invariants fail:

- epic branch and PR base are identical and have the form `epic/<slug>`;
- the feature branch and worktree are the declared ticket-specific values;
- the review mode is external and the ticket agent stops after opening the PR;
- the workflow and assigned spec ticket exist in `ticket_plan.yaml`;
- schedule revision, dependencies, blocks, wave, promotion order/predecessor,
  conflict keys, validation matrix, and evidence root exactly match the
  canonical plan entry; and
- the issue number matches the declared issue-specific branch/worktree values,
  while the spec ticket id matches the workflow plan entry.

Do not silently infer replacement values from the default branch or from ordinary
`git-issue-workflow` naming rules.

Fetch remote state before changing the checkout:

```bash
git fetch origin
git show-ref --verify refs/remotes/origin/epic/<slug>
git merge-base --is-ancestor <base-sha> origin/epic/<slug>
git merge-base --is-ancestor <plan-commit> origin/epic/<slug>
```

Both ancestry commands must succeed. `base_sha` is an ancestry floor, not the
commit to branch from; a new ticket worktree starts at the **latest** declared
epic tip.

Resolve every `depends_on` entry to its ticket PR. For each dependency, verify
both that the PR is merged into the declared epic branch and that its merge
commit is reachable from `origin/epic/<slug>`. A locally closed spec ticket, a
green dependency branch, a closed GitHub issue, or an open PR does not satisfy a
dependency. Wait when any dependency is not on the remote epic tip.

Also verify that the declared feature branch is not already merged and is not
owned by a different worktree. If the exact branch/worktree already represents
this assignment, resume it; do not create a duplicate.

## 2. Create or resume the declared epic-based worktree

For a new assignment, use the exact values from the assignment:

```bash
git worktree add ../wt-<issue-number>-<slug> \
  -b feature/<issue-number>-<slug> origin/epic/<slug>
cd ../wt-<issue-number>-<slug>
```

If the feature branch already exists legitimately, attach or enter its declared
worktree and reconcile it with the latest `origin/epic/<slug>` instead of running
the creation command again. Preserve any assigned work already present.

Never start an epic ticket from `origin/main`, another default branch, the stale
`base_sha`, or a sibling ticket branch. Do not use the ordinary integration
`new-change.sh` flow or create per-constituent branches: the epic assignment owns
the branch topology for this ticket.

## 3. Open only the assigned spec ticket

The epic workflow already exists. If the declared branch already contains the
assigned ticket workspace, verify it and resume it. Otherwise open exactly the
assigned ticket:

```bash
tla-spec-dev --spec-root specs open ticket <stable-ticket-id>
```

Never run `scaffold workflow`, create a second workflow, open sibling tickets,
reorder the plan, change another ticket's status, or rewrite workflow-wide
dependencies from this branch.

Treat ticket-local `desired/` as the whole-program state after this ticket. Edit
it first. Advance ticket-local `current/` to the whole-program behavior that the
implementation actually provides, preserving every baseline behavior outside the
assigned delta.

Implement every assigned surface, including when applicable:

- production code and repository tests;
- Internal/External TLA+ state, actions, invariants, and model configs;
- spec-unit adapters, generated cases, strategies, and conformance tests;
- Test Graph adapters, bindings, nodes, graph composition, and context contracts;
  and
- structured validation evidence beneath the declared evidence root.

Do not narrow the work to production code when the assignment names spec,
adapter, or Test Graph effects.

## 4. Run the assigned validation loop

Run every validation matrix entry marked REQUIRED, using the exact command from
the issue. At minimum for a spec ticket, record the assigned-ticket spec unit
result and discover each affected graph before running it:

```bash
tla-spec-dev --spec-root specs run spec-unit-tests --ticket <stable-ticket-id>
<test-graph-skill>/scripts/discover.py <affected-graph>
<test-graph-skill>/scripts/run.py <affected-graph>
```

Run the issue's TLC command, repository unit command, affected repository
graphs, assigned spec-conformance graph, and adapter checks when required.
`specWorkflow` is tla-spec-dev's own CLI-lifecycle graph; run it only when the
assignment explicitly targets that repository. Use Test Graph's saved-context
failure loop for isolated failures, then rerun each complete graph from a fresh
start. Store reports and other results under the declared evidence root; command
output without a durable result path is not close-out evidence.

At this stage parallel implementation may finish, but the ticket is not yet
allowed into the promotion lane.

## 5. Wait for and reconcile the promotion predecessor

`promotion_predecessor` serializes ticket-scoped promotion even when tickets were
implemented in parallel. When it is non-null, do not close the assigned ticket
until the predecessor's PR is merged into the declared epic branch and its merge
commit is reachable from the latest remote epic tip.

Fetch again and rebase or merge the latest `origin/epic/<slug>` into the ticket
branch before closing. Re-read the canonical plan and repeat the complete assignment
equality check. A changed schedule revision or field mismatch returns the issue
to the epic owner; do not promote from stale assignment metadata.

Then reconcile semantic state deliberately:

- preserve predecessor close-history entries and closed plan statuses;
- use the latest epic `specs/current` as the whole-program base;
- reapply only this ticket's semantic delta to its ticket-local desired/current;
- retain sibling Test Graph artifacts, bindings, and context contracts; and
- rerun the complete assigned validation matrix, writing fresh evidence.

Do not resolve promotion conflicts by discarding predecessor history, reopening
or editing sibling tickets, or silently broadening this ticket. If reconciliation
changes scope or reveals a semantic conflict, stop and request an explicit
amendment or reconciliation ticket.

## 6. Close and promote only the assigned ticket

When ticket-local current semantically equals desired and all required validation
is green, mark only the assigned entry in `ticket_plan.yaml` closed/done and
record its run ids and evidence paths. Leave every sibling entry and all
workflow-wide dependency/order metadata unchanged. Then close exactly the
assigned ticket with every durable evidence path:

```bash
tla-spec-dev --spec-root specs close ticket <stable-ticket-id> \
  --summary "<what landed>" \
  --result <evidence-path> \
  --result <another-evidence-path>
```

This command's ticket-scoped promotion into project `specs/current` is the only
promotion this agent performs. The default equality gate must pass.

Never:

- use `--accept-new` to bypass semantic equality;
- use `--no-promote-current` to suppress the assigned ticket's promotion;
- close or alter any other spec ticket; or
- run `close_tickets.py` or any other whole-workflow close/promotion command.

Inspect the append-only history entry, assigned plan status, promoted project
current, merged graph artifacts, and evidence paths. Commit the implementation,
specs, adapters, Test Graph changes, close history, and evidence together.

## 7. Open the ticket PR into the epic branch and stop

Push the declared feature branch and explicitly target the declared epic branch:

```bash
git push -u origin feature/<issue-number>-<slug>
gh pr create --base epic/<slug> --head feature/<issue-number>-<slug> \
  --title "<ticket-id>: <title>" --body-file <pr-body.md>
```

The PR body must contain:

- `Refs #<issue-number>` — never `Closes #<issue-number>`;
- epic branch, workflow name, and assigned spec ticket id;
- dependency and promotion-predecessor checks;
- exact validation commands and report/evidence paths;
- the append-only close-history path; and
- the resulting ticket commit SHA.

Stop for external review immediately after confirming that the PR base is the
declared epic branch and the body contains the evidence. Do not:

- target, merge, pull, or sync the default branch;
- run `gh pr merge` or otherwise self-merge the ticket PR;
- close the GitHub issue with `gh issue close` or via a `Closes` keyword;
- run whole-workflow close/promotion;
- run ordinary integration fan-out; or
- clean up by moving the primary checkout to the default branch.

The closed ticket head represents sealed evidence. Semantic changes requested in
review require an explicit amendment ticket rather than rewriting the recorded
close history.

## Epic ticket checklist

- [ ] Epic marker selected before ordinary/integration provisioning
- [ ] Assignment complete; branch/PR-base and canonical-plan equality verified
- [ ] `base_sha` and every dependency reachable from latest `origin/epic/*`
- [ ] Declared worktree created or resumed from the epic branch
- [ ] Only the assigned existing spec ticket opened; no workflow scaffolded
- [ ] Production, TLA+, spec-unit adapters, and Test Graph surfaces implemented
- [ ] Full assigned validation matrix green with durable evidence
- [ ] Promotion predecessor merged and latest epic tip reconciled
- [ ] Only the assigned ticket closed/promoted; no bypass or whole close used
- [ ] PR opened with `Refs #<issue>` and base `epic/*`
- [ ] Work stopped for external review; issue and default branch untouched
