r"""Subprocess wrapper over ``scripts/wt`` with typed results and errors.

Output contracts parsed here (see ``scripts/lib.sh`` ``contract()``,
``scripts/wt`` error emission, and ``scripts/new-change.sh``
``emit_contract()``):

- contract lines: ``printf '%-10s %s'`` — first whitespace-delimited
  token is the key (``WORKTREE``, ``BRANCH``, ``BASE``, ``LAUNCH``,
  ``IF-EXIT-8``, ``CLOSE``, ``PROPAGATE``, ``STALE-BASE``; on close:
  ``CLOSED``, ``DELETE``, ``HOME-WORK``; on failure: ``FAILED``,
  ``FIX``), the rest is the value;
- quiet success lines: ``created worktree <path>`` and
  ``closed worktree <path> (branch <branch> kept; ...)``. These are PROSE.
  Nothing here parses the ``new`` summary and nothing else should: an
  anchored ``^created worktree (\S+)$`` in another repository is exactly
  what a one-word addition to it breaks. Read the keys;
- quiet failure lines: ``error creating|closing worktree: <reason>`` /
  ``fix: <command>`` / ``log: <path>``.

``BASE`` (and ``STALE-BASE``, when ``--stale-base-ok`` was used) is
emitted only by the run that CREATES a worktree, because it is a
measurement of that run; ``wt info`` never carries it. That is why
:func:`wt_new` reads the keys off its own stdout instead of taking the
whole contract from the follow-up :func:`wt_info`. ``wt`` itself
summarises and prints no keys, so both are ``None`` through that path.

Exit codes: 3 = bootstrap failed (worktree rolled back), 4 = refused by
the close-out gate, 7 = ``new`` refused because the base branch is behind
its remote counterpart. Anything else non-zero raises plain ``WtError``.
The numbers are an interface — 4 belongs to close-change.sh's
``REFUSED_EXIT`` and must not be reused by another gate, or a refused
``new`` surfaces as :class:`CloseRefused`.

``wt new`` against a large source home can run ~a minute and prints a
progress line to stderr after ``WT_PROGRESS_AFTER`` seconds; no timeout
is imposed here.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, replace
from pathlib import Path

_CONTRACT_KEYS = {
    "WORKTREE",
    "BRANCH",
    "BASE",
    "LAUNCH",
    "IF-EXIT-8",
    "CLOSE",
    "PROPAGATE",
    "CLOSED",
    "DELETE",
    "HOME-WORK",
    "STALE-BASE",
    "CLEAN",
    "FAILED",
    "FIX",
}


class WtError(RuntimeError):
    """A wt invocation failed. Carries the printed reason/fix/log."""

    def __init__(self, reason: str, fix: str = "", log: str = "", exit_code: int = 1):
        super().__init__(reason)
        self.reason = reason
        self.fix = fix
        self.log = log
        self.exit_code = exit_code


class BootstrapFailed(WtError):
    """Exit 3: the home bootstrap failed and the worktree was rolled back."""


class CloseRefused(WtError):
    """Exit 4: the close-out gate refused; ``reason`` names the blockers."""


class StaleBase(WtError):
    """Exit 7: ``new`` refused — the base branch is behind its remote.

    ``reason`` carries the counted comparison and ``fix`` the command that
    branches from the published tip. Pass ``stale_base_ok=True`` to
    :func:`wt_new` to take the local ref deliberately instead.
    """


@dataclass(frozen=True)
class WorktreeContract:
    worktree: str
    branch: str
    close: str
    launch: str | None = None
    if_exit_8: str | None = None
    propagate: str | None = None
    # Only set by wt_new, and only when it was driven by something that emits
    # the keys (new-change.sh directly). `wt info` answers about a worktree some
    # other run created and never measured a branch point, so None here means
    # "not measured", never "branched from nothing".
    base: str | None = None
    # Present only when --stale-base-ok was used: the counted comparison the
    # gate would otherwise have refused over.
    stale_base: str | None = None


@dataclass(frozen=True)
class CloseResult:
    worktree: str
    branch: str | None = None
    delete: str | None = None
    home_work: str | None = None
    dry_run_clean: bool = False


def wt_bin() -> Path:
    """Resolve scripts/wt: env override, then this unit's own copy, then the home's."""
    env = os.environ.get("GIW_WT_BIN")
    if env:
        return Path(env)
    unit_root = Path(__file__).resolve().parents[2]
    candidate = unit_root / "scripts" / "wt"
    if candidate.is_file():
        return candidate
    home = os.environ.get("SKILL_MANAGER_HOME") or str(Path.home() / ".skill-manager")
    return Path(home) / "skills" / "git-issue-workflow" / "scripts" / "wt"


def parse_contract(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        parts = line.split(None, 1)
        if len(parts) == 2 and parts[0] in _CONTRACT_KEYS:
            out[parts[0]] = parts[1].strip()
    return out


def _parse_failure(text: str, exit_code: int) -> WtError:
    reason, fix, log = f"exit {exit_code}", "", ""
    for line in text.splitlines():
        if line.startswith(("error creating worktree:", "error closing worktree:")):
            reason = line.split(":", 1)[1].strip()
        elif line.startswith("error:"):
            reason = line.split(":", 1)[1].strip()
        elif line.startswith("fix:"):
            fix = line.split(":", 1)[1].strip()
        elif line.startswith("log:"):
            log = line.split(":", 1)[1].strip()
    cls = {3: BootstrapFailed, 4: CloseRefused, 7: StaleBase}.get(exit_code, WtError)
    return cls(reason, fix=fix, log=log, exit_code=exit_code)


def _run(args: list[str], cwd: str | Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(wt_bin()), *args],
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
    )


def _combined(proc: subprocess.CompletedProcess) -> str:
    return proc.stdout + "\n" + proc.stderr


def wt_info(ticket: str, cwd: str | Path | None = None) -> WorktreeContract:
    proc = _run(["info", ticket], cwd=cwd)
    if proc.returncode != 0:
        raise _parse_failure(_combined(proc), proc.returncode)
    keys = parse_contract(proc.stdout)
    return WorktreeContract(
        worktree=keys.get("WORKTREE", ""),
        branch=keys.get("BRANCH", ""),
        close=keys.get("CLOSE", ""),
        launch=keys.get("LAUNCH"),
        if_exit_8=keys.get("IF-EXIT-8"),
        propagate=keys.get("PROPAGATE"),
    )


def wt_new(
    ticket: str,
    base: str | None = None,
    *,
    integration: bool = False,
    no_home: bool = False,
    stale_base_ok: bool = False,
    cwd: str | Path | None = None,
) -> WorktreeContract:
    """Create the worktree and its home.

    Raises :class:`StaleBase` (exit 7) when ``base`` names a local branch
    that is behind its remote counterpart. ``stale_base_ok=True`` takes
    the local ref anyway, and ``stale_base`` then records that it did.
    """
    args = ["new", ticket]
    if base:
        args.append(base)
    if integration:
        args.append("--integration")
    if no_home:
        args.append("--no-home")
    if stale_base_ok:
        args.append("--stale-base-ok")
    proc = _run(args, cwd=cwd)
    if proc.returncode != 0:
        raise _parse_failure(_combined(proc), proc.returncode)
    # KEYS ONLY. The branch point is on THIS run's output and on no other, so it
    # is read here rather than left to the wt_info below — which answers about
    # the worktree, not about the run that made it. Read from the CONTRACT, never
    # from the `created worktree …` summary: that line is prose, and parsing it
    # is what broke three callers in two other repositories.
    #
    # `wt` summarises and prints no keys, so these are None when driven through
    # it and populated when a caller runs new-change.sh directly (or points
    # GIW_WT_BIN at it). That is the honest answer either way — None means "this
    # invocation did not report one", never "it branched from nothing".
    keys = parse_contract(proc.stdout)
    info = wt_info(ticket, cwd=cwd)
    return replace(info, base=keys.get("BASE"), stale_base=keys.get("STALE-BASE"))


def wt_close(
    ticket_or_path: str,
    *,
    force: bool = False,
    dry_run: bool = False,
    cwd: str | Path | None = None,
) -> CloseResult:
    args = ["close", ticket_or_path]
    if force:
        args.append("--force")
    if dry_run:
        args.append("--dry-run")
    proc = _run(args, cwd=cwd)
    if proc.returncode != 0:
        raise _parse_failure(_combined(proc), proc.returncode)
    keys = parse_contract(proc.stdout)
    if dry_run and "CLEAN" in keys:
        return CloseResult(worktree=keys["CLEAN"].split(" — ")[0], dry_run_clean=True)
    if "CLOSED" in keys:
        return CloseResult(
            worktree=keys["CLOSED"],
            branch=keys.get("BRANCH"),
            delete=keys.get("DELETE"),
            home_work=keys.get("HOME-WORK"),
        )
    for line in proc.stdout.splitlines():
        if line.startswith("closed worktree "):
            rest = line[len("closed worktree "):]
            path, _, tail = rest.partition(" (")
            branch = None
            if tail.startswith("branch "):
                branch = tail[len("branch "):].split(" ", 1)[0]
            return CloseResult(worktree=path.strip(), branch=branch)
    return CloseResult(worktree=ticket_or_path)


def checkout_kind(path: str | Path = ".") -> str:
    """Port of lib.sh checkout_kind(): marker-file presence only.

    'integration' — the checkout root itself carries integration.toml;
    'constituent' — some ancestor does; 'standalone' — nobody does.
    """
    proc = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    root = Path(proc.stdout.strip() or path).resolve()
    if (root / "integration.toml").is_file():
        return "integration"
    for parent in root.parents:
        if (parent / "integration.toml").is_file():
            return "constituent"
    return "standalone"


def cli_main() -> int:
    """Passthrough entry point: ``wt-py <verb> ...`` forwards to scripts/wt."""
    import sys

    proc = subprocess.run([str(wt_bin()), *sys.argv[1:]])
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(cli_main())
