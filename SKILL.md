---
name: git-issue-workflow
description: >-
  Use when an agent is asked to KICK OFF or COMPLETE a ticket that a git-issue
  work order describes — the implementer side of git-issue. Drives the two devops
  roles: (2) provision the ticket workflow — detect an integration repo, create a
  worktree and same-named feature branches, open the spec workflow with
  spec-double-compiler + tla-spec-dev; and (3) perform it — run the current→desired
  validation loop over spec unit tests, unit tests, test_graph, and the
  tla-spec-dev spec graph (operated only from the parent), close the spec workflow
  and the GitHub issue, merge/verify the worktree and open the PR, and for an
  integration repo fan out per-constituent feature branches + PRs with agent tags.
  Also carries the reference for an agent that RECEIVES an agent-tagged PR from an
  integration MR. Trigger on "complete this ticket", "start this ticket", "pick up
  issue #N", "open the MR", or "propagate the integration change".
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
This skill is how an agent actually **runs** them, end to end, and finishes with a
PR (and, for an integration repo, a fan-out to every constituent).

It covers the two downstream devops roles:

- **Role 2 — Provision (kick off).** Read the issue, set up the worktree and
  feature branch(es), detect whether this is an integration repo, and open the
  spec workflow so the branch starts spec-first. See `references/provision.md`.
- **Role 3 — Perform (complete).** Implement, run the current→desired validation
  loop until green, close the spec workflow and the GitHub issue, verify the
  merge, open the PR, and — for an integration repo — fan out per-constituent
  branches/PRs with agent tags. See `references/complete.md`.

`git-issue` files the work; this skill closes it. The role-1 author uses
`git-issue`; roles 2 and 3 use this skill. They can be the same agent in one
session or three different agents across a handoff.

## Three load-bearing rules

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

## Role 2 — Provision the ticket

Full flow in `references/provision.md`. In short:

1. Read the issue (References, Spec-workflow section, Regression checklist). Confirm
   `gh` auth and the right repo.
2. Detect PLAIN vs INTEGRATION (above).
3. Create the worktree + `feature/<ticket>`:
   - PLAIN: `git worktree add ../wt-<ticket> -b feature/<ticket> origin/main`.
   - INTEGRATION: `<git-integration-repo>/scripts/new-change.sh <ticket>`.
4. If the issue's Spec-workflow section is REQUIRED, open the spec workflow **now**,
   on the fresh branch: `tla-spec-dev --spec-root specs scaffold workflow <ticket>
   "<title>"` then `tla-spec-dev --spec-root specs open ticket <ticket>`. Commit the
   scaffolded `current/`/`desired/` so the branch is spec-first.

## Role 3 — Perform the ticket

Full flow in `references/complete.md`; the loop is `references/validation-loop.md`.
In short:

1. Implement in the worktree. For an integration repo, edit across constituent
   files in the one parent worktree.
2. Run the **current→desired validation loop** until `specs/current` semantically
   equals `specs/desired_program_model` and every named graph is green
   (`references/validation-loop.md`).
3. Close the spec workflow: `tla-spec-dev ... close ticket <ticket>` per ticket,
   then promote to `program_model` when current == desired.
4. Merge/verify the worktree, open the PR (`Closes #<n>`), close the issue
   (`references/complete.md`).
5. **INTEGRATION only:** fan out to every changed constituent — a `feature/<ticket>`
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
| Kicking off a ticket | `references/provision.md` |
| Completing a ticket | `references/complete.md` |
| Running the green loop | `references/validation-loop.md` |
| Fanning out to sub-repos | `references/integration-fanout.md` |
| Handed an agent-tagged PR | `references/agent-tag-pr.md` |

## Boundaries

- This skill **executes** a ticket; it does not author the issue. Issue creation,
  the References section, and the spec-required decision are `git-issue`'s job.
- It does not reimplement the spec, test-graph, or integration mechanics — it
  **sequences** them. The mechanics live in `spec-double-compiler` (the
  `tla-spec-dev` CLI), `test-graph` (the graph scripts), and `git-integration-repo`
  (the worktree/fan-out scripts).
- It never runs per-constituent specs/graphs during a ticket. Constituents
  validate themselves after fan-out, via their agent-tagged PRs.
