"""Subprocess wrapper over ``scripts/wt`` with typed results and errors.

Output contracts parsed here (see ``scripts/lib.sh`` ``contract()``,
``scripts/wt`` error emission, and ``scripts/new-change.sh``
``emit_contract()``):

- contract lines: ``printf '%-10s %s'`` — first whitespace-delimited
  token is the key (``WORKTREE``, ``BRANCH``, ``LAUNCH``, ``IF-EXIT-8``,
  ``CLOSE``, ``PROPAGATE``; on close: ``CLOSED``, ``DELETE``,
  ``HOME-WORK``; on failure: ``FAILED``, ``FIX``), the rest is the value;
- quiet success lines: ``created worktree <path>`` and
  ``closed worktree <path> (branch <branch> kept; ...)``;
- quiet failure lines: ``error creating|closing worktree: <reason>`` /
  ``fix: <command>`` / ``log: <path>``.

Exit codes: 3 = bootstrap failed (worktree rolled back), 4 = refused by
the close-out gate. Anything else non-zero raises plain ``WtError``.

``wt new`` against a large source home can run ~a minute and prints a
progress line to stderr after ``WT_PROGRESS_AFTER`` seconds; no timeout
is imposed here.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

_CONTRACT_KEYS = {
    "WORKTREE",
    "BRANCH",
    "LAUNCH",
    "IF-EXIT-8",
    "CLOSE",
    "PROPAGATE",
    "CLOSED",
    "DELETE",
    "HOME-WORK",
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


@dataclass(frozen=True)
class WorktreeContract:
    worktree: str
    branch: str
    close: str
    launch: str | None = None
    if_exit_8: str | None = None
    propagate: str | None = None


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
    cls = {3: BootstrapFailed, 4: CloseRefused}.get(exit_code, WtError)
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
    cwd: str | Path | None = None,
) -> WorktreeContract:
    args = ["new", ticket]
    if base:
        args.append(base)
    if integration:
        args.append("--integration")
    if no_home:
        args.append("--no-home")
    proc = _run(args, cwd=cwd)
    if proc.returncode != 0:
        raise _parse_failure(_combined(proc), proc.returncode)
    return wt_info(ticket, cwd=cwd)


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
