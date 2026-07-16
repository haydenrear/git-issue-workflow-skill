---
name: git-issue-workflow
description: >-
  Use when handed a GitHub issue to implement — a pasted issue body, a URL, a bare
  "#N", or `gh issue view` output — or asked to start, pick up, work on,
  complete, or close out a ticket, including one assigned from a shared epic spec
  workflow. Read BEFORE touching the repo: the issue body is a work order, and the
  `git-epic-workflow:assignment` marker selects a higher-priority epic mode before
  ordinary or integration provisioning. Epic tickets branch from the declared
  `origin/epic/*`, close/promote only their assigned spec ticket with evidence, and
  open a PR back to the epic branch for external review. Unmarked tickets retain
  the ordinary/integration flow: worktree provisioning, current→desired validation,
  workflow/issue close-out, merge verification, and integration fan-out. Trigger
  on "implement this issue", "complete this ticket", "pick up issue #N", "work
  this epic ticket", "open the MR", or "propagate the integration change".
  Also use when receiving an agent-tagged PR from an integration MR.
skill-imports:
  - unit: git-issue
    path: SKILL.md
    reason: This skill executes the worktree/spec/close-out moves that a git-issue work order names; the issue body is the input to provisioning.
  - unit: git-integration-repo
    path: references/propagation.md
    reason: Integration-repo provisioning (worktree, same-named branches) and fan-out (per-constituent branches, MRs, tracking issue) use its scripts and model.
  - unit: spec-double-compiler
    path: SKILL.md
    reason: The spec workflow — open/close ticket, spec-unit-tests, current→desired promotion — runs through the tla-spec-dev CLI this skill installs.
  - unit: test-graph
    path: SKILL.md
    reason: The validation loop runs named test_graph graphs (incl. the spec graph) via the test-graph scripts and its smart failure loop.
  - unit: deploy-helm
    path: SKILL.md
    reason: Tickets touching deployable surfaces validate against deploy-helm environments inside the test graph.
  - unit: skill-manager
    path: references/workflows.md
    reason: This skill is installed and synced as a skill-manager unit.
---

# git-issue-workflow

The **implementer side** of `git-issue`. A work order created by the `git-issue`
skill names the moves — worktree, spec workflow, regression graphs, close-out.
This skill is how an agent actually **runs** them. An epic assignment stops at a
PR into its shared epic branch; an ordinary ticket runs end to end (and, for an
integration repo, fans out to every constituent).

For ordinary and integration tickets it covers two downstream devops roles:

- **Role 2 — Provision (kick off).** Read the issue, set up the worktree and
  feature branch(es), detect whether this is an integration repo, and open the
  spec workflow so the branch starts spec-first. See `references/provision.md`.
- **Role 3 — Perform (complete).** Implement, run the current→desired validation
  loop until green, close the spec workflow and the GitHub issue, verify the
  merge, open the PR, and — for an integration repo — fan out per-constituent
  branches/PRs with agent tags. See `references/complete.md`.

`git-issue` files the work; this skill executes it. The role-1 author uses
`git-issue`; roles 2 and 3 use this skill. They can be the same agent in one
session or three different agents across a handoff. Epic assignments use the
same issue as their work order but deliberately leave the GitHub issue and epic
workflow open after the ticket PR is created.

## Select epic mode before any provisioning

Read the complete issue body before choosing a branch, worktree, repository mode,
or spec command. Search for the exact marker:

```text
<!-- git-epic-workflow:assignment:start -->
```

- **Marker present:** this is epic ticket mode. Read
  `references/epic-ticket.md` and follow it instead of Role 2, Role 3, the
  ordinary close-out sequence, or integration fan-out. The assignment's declared
  branch, worktree, ticket, validation, promotion, and PR base are authoritative.
  This selection happens even when the checkout also has integration-repo markers.
- **Marker absent:** continue with the existing PLAIN/INTEGRATION detection and
  ordinary procedures below.

Do not scaffold a workflow, create a default-branch worktree, or run an
integration provisioning script until this marker check is complete. An epic
assignment overrides ordinary instructions that say to branch from, merge to, or
sync the default branch.

## Three load-bearing rules for ordinary and integration tickets

These decide most of the mechanics — get them wrong and the rest breaks.

1. **Operate specs and the test graph only from the parent.** When the ticket
   spans sub-repos (an integration repo), you run the TLA+ spec workflow and the
   `test_graph` graphs **once, at the integration parent**, whose worktree holds
   every constituent's files as plain files. You do **not** run per-constituent
   specs/graphs during the ticket. Each constituent re-runs its own loops later,
   after fan-out, when it receives its agent-tagged PR
   (`references/agent-tag-pr.md`).
2. **Same branch name everywhere.** The ticket id drives one branch name —
   `feature/<ticket>` — on the parent and on every constituent, so a single change
   stays traceable across the parent PR and every sub-repo PR.
3. **A ticket lives in a worktree, never the primary checkout.** Generated spec
   doubles and manifests land on the feature branch from creation; the main tree
   stays clean so `git-integration-repo`'s constituent `.git`s are undisturbed.

## Is this an integration repo?

Decide first — it changes provisioning and fan-out. It **is** an integration repo
when the repo root carries the `git-integration-repo` markers:

```bash
test -f INTEGRATION.md && test -f integration.toml && echo INTEGRATION || echo PLAIN
```

- **PLAIN repo** → one worktree, one feature branch, one PR. Use plain `git
  worktree` and `gh`.
- **INTEGRATION repo** → one parent worktree spanning constituents, the spec/graph
  loop at the parent only, then fan-out to per-constituent branches + PRs. Use
  `git-integration-repo`'s scripts (`new-change.sh`, `propagate.sh`, `verify.sh`).

## Ordinary close-out sequence

An unmarked ticket is not done when the code is green. It is done when these five
moves have all happened, in order. Every ordinary/integration agent runs this —
no exceptions, no leaving a PR "ready for someone to merge later". Epic tickets
do not run this sequence; their ticket-scoped close-out and external-review stop
are in `references/epic-ticket.md`.

1. **Close every open spec ticket, then the spec workflow, with the
   `tla-spec-dev` CLI** (installed by `spec-double-compiler`). Close each ticket
   still open in `ticket_plan.yaml` by id — not just the last one — then promote:
   ```bash
   tla-spec-dev --spec-root specs close ticket <ticket-id> --summary "<what landed>" --result <evidence-path>
   # repeat for every ticket still open
   python <spec-double-compiler-skill>/scripts/close_tickets.py --repo-root . \
     --summary "Promoted desired/current into program_model"
   ```
2. **Commit and push** the implementation, spec changes, and evidence together.
3. **Rebase and merge the PR into `main` with `gh`** — land it yourself rather
   than leaving it open for someone else to merge:
   ```bash
   gh pr create --fill --body "Closes #<n>"
   gh pr merge --rebase
   ```
4. **Remove the worktree and sync the project root to the new `main`.** The
   primary checkout must actually reflect the merge before the ticket counts as
   closed:
   ```bash
   git worktree remove ../wt-<ticket>
   git -C <repo-root> checkout main && git -C <repo-root> pull origin main
   git -C <repo-root> worktree prune
   ```
5. **Close the GitHub issue with `gh`.** A `Closes #<n>` merge usually closes it
   automatically — confirm that, don't assume it, and close it explicitly if not:
   ```bash
   gh issue view <n> --json state,closed
   gh issue close <n> --comment "<summary>"   # only if still open
   ```

**INTEGRATION repos** skip step 3's `gh pr merge` — the parent worktree has no
GitHub remote to merge against, so land it with `git merge --no-ff` and
`verify.sh` instead (`references/complete.md` step 5) — but still run 1, 2, 4,
and 5 at the parent, then fan out to constituents
(`references/integration-fanout.md`).

Full step-by-step, including the INTEGRATION variant of each move, lives in
`references/complete.md`; treat the list above as the checklist you're not
allowed to skip.

## Role 2 — Provision an ordinary or integration ticket

Full flow in `references/provision.md`. In short:

1. Read the issue (References, Spec-workflow section, Regression checklist). Confirm
   `gh` auth and the right repo.
2. Detect PLAIN vs INTEGRATION (above).
3. Create the worktree + `feature/<ticket>`, applying the index-base pinning
   conventions in `references/provision.md` §3 (clean tree; resolve the base
   rev to commit/tree OIDs once; create-only `refs/index-bases/*` retention
   ref; branch from the pinned commit):
   - PLAIN: `git worktree add ../wt-<ticket> -b feature/<ticket> <commit_oid>`.
   - INTEGRATION: `<git-integration-repo>/scripts/new-change.sh <ticket>`.
4. If the issue's Spec-workflow section is REQUIRED, open the spec workflow **now**,
   on the fresh branch: `tla-spec-dev --spec-root specs scaffold workflow <ticket>
   "<title>"` then `tla-spec-dev --spec-root specs open ticket <ticket>`. Commit the
   scaffolded `current/`/`desired/` so the branch is spec-first.

## Role 3 — Perform an ordinary or integration ticket

Full flow in `references/complete.md`; the loop is `references/validation-loop.md`.
In short:

1. Implement in the worktree. For an integration repo, edit across constituent
   files in the one parent worktree.
2. Run the **current→desired validation loop** until `specs/current` semantically
   equals `specs/desired_program_model` and every named graph is green
   (`references/validation-loop.md`).
3. Run the **close-out sequence** above: close every spec ticket and the workflow
   via `tla-spec-dev`, commit and push, rebase-merge the PR into `main` via `gh`,
   remove the worktree and sync the project root to the new `main`, and close the
   GitHub issue via `gh` (`references/complete.md`).
4. **INTEGRATION only:** fan out to every changed constituent — a `feature/<ticket>`
   branch, a PR, and an **agent tag** on each, so each constituent runs its own
   loops downstream (`references/integration-fanout.md`).

## Receiving an agent-tagged PR

When *this* repo is a constituent and an integration MR opened an agent-tagged PR
against it, the agent that picks up that tag runs a self-contained loop: update the
program-model specs, extend test-graph adapters/nodes if needed, run the spec-unit
/ unit / test_graph / spec-graph loop, then commit and push for review. That
receiver flow is `references/agent-tag-pr.md`.

## Reference map

| You are… | Read |
|---|---|
| Assigned one ticket from a shared epic workflow | `references/epic-ticket.md` |
| Kicking off a ticket | `references/provision.md` |
| Completing a ticket | `references/complete.md` |
| Running the green loop | `references/validation-loop.md` |
| Fanning out to sub-repos | `references/integration-fanout.md` |
| Handed an agent-tagged PR | `references/agent-tag-pr.md` |

## Boundaries

- This skill **executes** a ticket; it does not author the issue. Issue creation,
  the References section, and the spec-required decision are `git-issue`'s job.
- It does not create or amend an epic assignment. In epic mode it consumes the
  marker-delimited assignment exactly as written and stops when required fields
  or scheduling state are inconsistent.
- It does not reimplement the spec, test-graph, or integration mechanics — it
  **sequences** them. The mechanics live in `spec-double-compiler` (the
  `tla-spec-dev` CLI), `test-graph` (the graph scripts), and `git-integration-repo`
  (the worktree/fan-out scripts).
- It never runs per-constituent specs/graphs during a ticket. Constituents
  validate themselves after fan-out, via their agent-tagged PRs.
