# Role 2 — Provision the ticket workflow (kick off)

Provisioning turns a filed issue into a **ready-to-work branch**: a dedicated
worktree, the right feature branch(es), and — when the issue calls for it — an
open spec workflow, all committed spec-first before any implementation. Your job
ends when an implementing agent (role 3) can start editing code with everything
in place. Nothing here implements the change.

## 1. Read the work order

Open the issue and extract the three things `git-issue` embedded for you:

```bash
gh issue view <n>                 # or: gh issue view <n> --json title,body,labels
```

- **References** — the discovery starting point (files/symbols/specs to touch).
- **Spec workflow — REQUIRED | NOT REQUIRED** — decides whether step 4 runs.
- **Regression & close-out** — the named graphs role 3 will run; note them now.

Confirm the tracker and auth before touching git:

```bash
gh auth status
gh repo view --json nameWithOwner   # confirm you are in the right repo
```

Derive a stable ticket id and slug from the issue, e.g. `142-retry-budget`. Use
it verbatim as `<ticket>` everywhere below — it becomes every branch name.

## 2. Detect PLAIN vs INTEGRATION

```bash
test -f INTEGRATION.md && test -f integration.toml && echo INTEGRATION || echo PLAIN
```

This one check forks the rest of provisioning. For an integration repo, also read
`integration.toml` to see the constituents and the host (`gh`/`glab`) — you will
not branch them now, but the spec/graph loop runs at this parent and the fan-out
targets exactly these constituents (`references/integration-fanout.md`).

## 3. Create the worktree + feature branch

**Same branch name everywhere:** `feature/<ticket>`.

### Index-base pinning conventions (every worktree, both repo shapes)

Every worktree this workflow creates must be reproducible against an immutable
base. Apply these at creation time, before any daemon, indexer, or build tool
touches the worktree:

1. **Clean slate.** The source checkout must be fully committed —
   `git status --porcelain` empty. Never provision over staged or dirty state;
   stop and reconcile instead.
2. **Resolve the base rev to object IDs once.** Capture
   `commit_oid=$(git rev-parse <base-ref>)` and
   `tree_oid=$(git rev-parse "<base-ref>^{tree}")` at creation and record them
   in the ticket evidence (and the daemon version file where an indexing
   platform runs). Never re-resolve the branch name afterwards — a ref is a
   symbolic name, not an identity.
3. **Retention ref.** Pin the base objects with a create-only custom ref so no
   later rebase or git GC can orphan what the worktree depends on:
   `git update-ref refs/index-bases/<repo-id>/<tree_oid> <commit_oid> ""`
   (empty old-value = compare-and-swap create; an existing ref pointing at a
   different commit is a hard error). Reserved namespace — never public tags.
4. **Branch from the pinned commit.** Create the feature branch from
   `<commit_oid>` (equivalently `git worktree add --detach` then branch), so
   the worktree base stays the pinned object even if the source branch
   advances.

Repos onboarded to an index platform (e.g. commit-diff-context snapshot
branching) consume these OIDs as the immutable base-snapshot identity. The
conventions hold even where no indexer runs — worktrees stay reproducible.

### PLAIN repo

```bash
git fetch origin
test -z "$(git status --porcelain)" || { echo "dirty tree — reconcile first"; exit 1; }
commit_oid=$(git rev-parse origin/main)              # use the repo's default branch
tree_oid=$(git rev-parse "origin/main^{tree}")
git update-ref "refs/index-bases/$(basename "$(git rev-parse --show-toplevel)")/${tree_oid}" "$commit_oid" ""
git worktree add ../wt-<ticket> -b feature/<ticket> "$commit_oid"
cd ../wt-<ticket>
```

### INTEGRATION repo

Use `git-integration-repo`'s script — it creates the parent worktree with every
constituent's files as **plain files** (no constituent `.git` inside), which is
exactly what lets you edit and validate across sub-repos from one place. Requires
a clean parent tree.

```bash
INT=<git-integration-repo-skill>/scripts
$INT/new-change.sh <ticket>          # -> ../<repo>-<ticket> on feature/<ticket>
cd ../<repo>-<ticket>
```

Do **not** create per-constituent branches now. Constituent-level git happens
only at fan-out, after the change merges back to the integration main tree.

> Why "depend on the same ones": every constituent branch, the parent branch, the
> MR title prefix, and the tracking issue all key off `<ticket>`. A single id
> keeps one change traceable across the parent PR and every sub-repo PR. Never
> rename the branch per constituent.

## 4. Open the spec workflow (only if REQUIRED)

If the issue's Spec-workflow section is **REQUIRED**, open the workflow now, on the
fresh branch, so the generated spec doubles and manifests are committed spec-first.
This runs through the `tla-spec-dev` CLI from **spec-double-compiler**. Operate it
at the **parent** for an integration repo (rule 1 in `SKILL.md`).

```bash
# scaffold the desired/current workflow structure from the accepted program_model
tla-spec-dev --spec-root specs scaffold workflow <ticket> "<issue title>"

# open the ticket-local workspace (current/, desired/, results/, test-graph assets)
tla-spec-dev --spec-root specs open ticket <ticket>
```

Then, before implementation, set the plan up the way the loop expects:

- Confirm `specs/current` starts equal to the whole accepted `specs/program_model`
  (not just the slice being changed).
- Edit ticket-local `desired/` first to the whole-program **ending** state named
  by the issue's Internal.tla / External.tla / test-graph / adapter bullets.
- Leave `current/` at today's behavior; role 3 advances it toward `desired/`.

Commit the scaffold so the branch is spec-first from the start:

```bash
git add -A && git commit -m "<ticket>: open spec workflow (scaffold current/desired)"
```

If the section is **NOT REQUIRED**, skip this step — the issue states the reason;
challenge it only if you discover state-machine surface it missed
(`git-issue` references/spec-workflow.md).

## 5. Hand off

Provisioning is done when:

- [ ] Worktree exists on `feature/<ticket>` (parent worktree for integration).
- [ ] PLAIN vs INTEGRATION recorded; constituents/host noted if integration.
- [ ] Spec workflow opened and committed, or explicitly marked N/A with a reason.
- [ ] The issue's named regression graphs are captured for role 3.

Role 3 (`references/complete.md`) picks up here. In a single-agent session, just
continue.
