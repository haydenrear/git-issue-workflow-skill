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
  workflow/issue close-out, merge verification, and integration fan-out. A ticket
  that declares a goal reads its expected effect before implementing, runs the
  declared local signal as advisory evidence, and reports goal contribution in the
  PR; a `role: evaluation` ticket runs the goal harness on the integrated epic tip
  and reports a met/missed/unmeasured verdict. Trigger
  on "implement this issue", "complete this ticket", "pick up issue #N", "work
  this epic ticket", "run the evaluation ticket", "open the MR", or "propagate the
  integration change".
  Also use when receiving an agent-tagged PR from an integration MR.
skill-imports:
  - unit: git-issue
    path: SKILL.md
    reason: This skill executes the worktree/spec/close-out moves that a git-issue work order names; the issue body is the input to provisioning.
  - unit: git-epic-workflow
    path: references/goals-and-evaluation.md
    reason: Source of truth for goal field names and semantics — goal kinds, contribution kinds, baselines, and the evaluation-ticket contract this skill consumes from the assignment's `goals:` block.
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
  An assignment whose `ticket.role` is `evaluation` decides goals instead of
  producing a behavioral delta — read `references/goal-signal.md` alongside
  `references/epic-ticket.md` before provisioning it.
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

## Your Skill Manager home IS the worktree's

The skills you are running are not the operator's. On a machine with per-checkout
homes there are three tiers, and **each is a real copy, not a symlink**:

```
root       ~/.skill-manager              where the operator installs
   |  copy
project    <repo>/.skill-manager         one per repository, gitignored
   |  copy
worktree   <worktree>/.skill-manager     YOURS, for this ticket, gitignored
```

Copies, because a link is a single shared object: two tickets editing "their"
copy of a skill would be editing each other's, and last writer wins silently.
Your worktree home is the whole reason you can improve a skill mid-ticket at all.

Two consequences you have to act on, and neither is optional:

- **Launch through the home's shims**, `<worktree>/.skill-manager/bin/launch/{claude,codex,gemini}`,
  or `skill-manager exec`. Exporting `SKILL_MANAGER_HOME` by hand gets you the
  part you remembered: skills also load from the Claude config dir, and
  `skill-script` CLI wrappers are generated shell scripts with a home's absolute
  path in the body, which no variable redirects. The shims apply the whole
  contract.
- **An edit you make to a skill inside that home is in no diff.** The home is
  gitignored, so `git add -A` never sees it, the parent PR cannot carry it, and
  `git worktree remove` deletes it without a word — succeeding exactly as
  quietly whether the home held a week of work or nothing. Getting it out is
  step 4 of the close-out sequence below, and it is a gate, not a reminder.

Downward (root → project → worktree) is a copy and needs nothing from you.
**Upward is the whole difficulty**, and it is why the close-out order matters.

## Is this an integration repo?

Decide first — it changes provisioning and fan-out. It **is** an integration repo
when the repo root carries the `git-integration-repo` markers:

```bash
test -f INTEGRATION.md && test -f integration.toml && echo INTEGRATION || echo PLAIN
```

- **PLAIN repo** → one worktree, one feature branch, one PR; `gh` for the PR.
- **INTEGRATION repo** → one parent worktree spanning constituents, the spec/graph
  loop at the parent only, then fan-out to per-constituent branches + PRs
  (`propagate.sh`, `verify.sh`).

**The worktree itself is the same command in both.** `wt new` creates the
worktree *and* its Skill Manager home, and detects which repo shape it is
standing in, so this fork does not reach worktree creation — it decides the
spec/graph scope and whether there is a fan-out at the end.

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
   When the issue declared a goal, the PR body also carries a
   `## Goal contribution` section — one row per goal with the measured local
   signal and its classification, including "no measurable movement"
   (`references/goal-signal.md`).
4. **Close out the worktree's Skill Manager home, THEN remove the worktree, then
   sync the project root to the new `main`.** The gate runs *before* the
   removal — after it, there is nothing left to save:
   ```bash
   # 4a. One command, both repo shapes: it runs the gate and, only on a clean
   #     verdict, removes the worktree. Prefer it to spelling the two steps out —
   #     two commands on separate lines run the removal whatever the gate
   #     returned, which is exactly the loss the gate exists to prevent.
   WT="${SKILL_MANAGER_HOME:-$HOME/.skill-manager}/skills/git-integration-repo/scripts/wt"
   "$WT" close <ticket>

   # 4b. Only once that succeeded:
   git -C <repo-root> checkout main && git -C <repo-root> pull origin main
   git -C <repo-root> worktree prune
   ```
   Underneath, 4a is `skill-manager home close-out --home <worktree>/.skill-manager
   --into <repo-root>/.skill-manager && git worktree remove <worktree>`; run it
   that way only when you need to pass a flag `wt close` does not forward, and
   keep the `&&`.
   Exit 0 is the only one that means "proceed". The three non-zero exits are not
   interchangeable and only the first prints blockers:
   - **1** — the worktree still holds work. Every blocking unit is named with the
     literal command that clears it. Run those, then re-run. Do not work around
     it; this is the only notice you get.
   - **2** — the path given to `--home` is not a home. Almost always: you passed
     the worktree directory instead of its `.skill-manager`. No blockers printed,
     because nothing was assessed.
   - **9** — the destination home is `frozen`, so the gate was refused and
     **nothing was attempted**. Not a verdict about your work.
   `wt close` is the same wrapper in both repo shapes (it forwards to
   `close-change.sh`, which refuses on a non-zero verdict with exit 4). Details
   and the `--force` semantics are in `references/complete.md` step 6.
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
   ref; branch from the pinned commit). **One command, both repo shapes** — it
   creates the worktree and its own Skill Manager home together, which a bare
   `git worktree add` does not:
   ```bash
   WT="${SKILL_MANAGER_HOME:-$HOME/.skill-manager}/skills/git-integration-repo/scripts/wt"
   "$WT" new <ticket> "$commit_oid"      # prints: created worktree <path>
   ```
   `cd` to the path it printed — it is `<parent>/<repo>-<ticket>`, not
   `../wt-<ticket>`. If it exits 3 with "no project home yet", run the absolute
   `fix:` line it prints (once per repository) and re-run.
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
   (`references/validation-loop.md`). If the issue declares a goal, run its local
   signal once those are green, store it with the evidence, and classify it —
   advisory, never a gate (`references/goal-signal.md`).
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
| Handed a ticket that declares a goal, or one whose slice **is** the measurement (`role: evaluation`) | `references/goal-signal.md` |

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
- It does not invent goals, baselines, or targets, and it never edits one to
  match a result. Goals are agreed with the user by `git-issue` /
  `git-epic-workflow`; this skill consumes what the work order declares.
- **It does not tune to a metric.** The declared local signal is measured,
  recorded, and reported — never gated on, never re-run selectively for a better
  number, never a reason to widen scope past the ticket's slice or weaken a
  REQUIRED validation entry. Report the run that happened; where a goal turns out
  to be unreachable from this slice, that is a deferred finding for the plan
  owner, not extra work for this ticket (`references/goal-signal.md`).
