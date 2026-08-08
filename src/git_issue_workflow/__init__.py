"""Typed Python surface over this skill's ``scripts/wt`` front door.

The bash stays the source of truth — it holds every policy decision and
is deliberately bash-3.2-compatible. This package registers it with the
Python interpreter so callers (notably the ``skt`` CLI) can drive the
worktree lifecycle programmatically instead of by path.
"""

from .wt import (
    BootstrapFailed,
    CloseRefused,
    CloseResult,
    StaleBase,
    WorktreeContract,
    WtError,
    checkout_kind,
    wt_close,
    wt_info,
    wt_new,
)

__version__ = "0.1.0"

__all__ = [
    "BootstrapFailed",
    "CloseRefused",
    "CloseResult",
    "StaleBase",
    "WorktreeContract",
    "WtError",
    "checkout_kind",
    "wt_close",
    "wt_info",
    "wt_new",
    "__version__",
]
