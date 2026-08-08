import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from git_issue_workflow.wt import (  # noqa: E402
    BootstrapFailed,
    CloseRefused,
    StaleBase,
    WtError,
    checkout_kind,
    parse_contract,
    wt_bin,
    wt_close,
    wt_info,
    wt_new,
)


def stub_wt(tmp_path: Path, script_body: str) -> Path:
    stub = tmp_path / "wt"
    stub.write_text("#!/usr/bin/env bash\n" + script_body)
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    return stub


@pytest.fixture
def use_stub(tmp_path, monkeypatch):
    def _install(body: str) -> None:
        monkeypatch.setenv("GIW_WT_BIN", str(stub_wt(tmp_path, body)))

    return _install


CONTRACT = """\
cat <<'EOF'
WORKTREE   /tmp/repo-T-1
BRANCH     feature/T-1 (new, from main)
LAUNCH     /tmp/repo-T-1/.skill-manager/bin/launch/claude
IF-EXIT-8  /tmp/repo-T-1/.skill-manager/bin/cli/skill-manager home drift --ack
CLOSE      /home/x/scripts/wt close T-1
PROPAGATE  /home/x/scripts/propagate.sh T-1
EOF
"""


def test_parse_contract_padded_keys():
    keys = parse_contract(
        "WORKTREE   /a/b\nIF-EXIT-8  cmd --ack\nnot a key line\nHOME-WORK  /h (details)\n"
    )
    assert keys == {
        "WORKTREE": "/a/b",
        "IF-EXIT-8": "cmd --ack",
        "HOME-WORK": "/h (details)",
    }


def test_wt_new_returns_full_contract(use_stub):
    use_stub(
        'if [ "$1" = new ]; then echo "created worktree /tmp/repo-T-1"; '
        "else\n" + CONTRACT + "fi\n"
    )
    contract = wt_new("T-1")
    assert contract.worktree == "/tmp/repo-T-1"
    assert contract.branch.startswith("feature/T-1")
    assert contract.if_exit_8.endswith("home drift --ack")
    assert contract.propagate.endswith("propagate.sh T-1")
    # `wt` summarises and prints no keys, so the branch point is not reported
    # through that path. None means "this invocation did not report one".
    assert contract.base is None
    assert contract.stale_base is None


def test_wt_new_reads_the_base_key_when_the_child_emits_one(use_stub):
    """new-change.sh called directly prints the keys; `wt` prints prose."""
    use_stub(
        'if [ "$1" = new ]; then printf "%-10s %s\\n" WORKTREE /tmp/repo-T-1 '
        'BASE "main @ 9a1c4f2" STALE-BASE "3 behind origin/main, taken anyway via --stale-base-ok"; '
        "else\n" + CONTRACT + "fi\n"
    )
    contract = wt_new("T-1")
    assert contract.base == "main @ 9a1c4f2"
    assert "--stale-base-ok" in contract.stale_base


def test_nothing_here_parses_the_created_worktree_summary(use_stub):
    """The rule an anchored `^created worktree (\\S+)$` elsewhere broke on.

    A summary carrying an extra clause must change NOTHING about what this
    wrapper reports, because it never reads that line.
    """
    use_stub(
        'if [ "$1" = new ]; then echo "created worktree /tmp/repo-T-1 (anything at all)"; '
        "else\n" + CONTRACT + "fi\n"
    )
    contract = wt_new("T-1")
    assert contract.worktree == "/tmp/repo-T-1"  # from the WORKTREE key, not the prose
    assert contract.base is None


def test_wt_info_carries_no_base_it_did_not_measure(use_stub):
    use_stub(CONTRACT)
    assert wt_info("T-1").base is None


def test_stale_base_refusal_maps_exit_7_not_close_refused(use_stub):
    """Exit 4 is close-change.sh's gate. A refused `new` must not borrow it."""
    use_stub(
        "echo 'error creating worktree: base epic/x is 21 commit(s) behind origin/epic/x"
        " — branching it would start from a superseded tree (--stale-base-ok to do it anyway)'\n"
        "echo 'fix: /abs/wt new T-9 origin/epic/x'\n"
        "echo 'log: /tmp/wt-run.log'\n"
        "exit 7\n"
    )
    with pytest.raises(StaleBase) as err:
        wt_new("T-9", "epic/x")
    assert not isinstance(err.value, CloseRefused)
    assert "21 commit(s) behind" in err.value.reason
    assert "--stale-base-ok" in err.value.reason
    assert err.value.fix.endswith("origin/epic/x")
    assert err.value.exit_code == 7


def test_stale_base_ok_is_forwarded_to_the_script(use_stub):
    use_stub(
        'if [ "$1" = new ]; then echo "args: $*" > "$GIW_ARGS_OUT"; '
        'echo "created worktree /tmp/repo-T-1"; '
        "else\n" + CONTRACT + "fi\n"
    )
    import tempfile

    with tempfile.NamedTemporaryFile("r+", suffix=".args") as fh:
        os.environ["GIW_ARGS_OUT"] = fh.name
        try:
            wt_new("T-1", "epic/x", stale_base_ok=True)
        finally:
            os.environ.pop("GIW_ARGS_OUT", None)
        fh.seek(0)
        assert "--stale-base-ok" in fh.read()


def test_wt_info_without_propagate_is_plain_repo(use_stub):
    use_stub(
        "cat <<'EOF'\nWORKTREE   /w\nBRANCH     feature/T-2\nCLOSE      wt close T-2\nEOF\n"
    )
    contract = wt_info("T-2")
    assert contract.propagate is None
    assert contract.launch is None


def test_bootstrap_failure_maps_exit_3(use_stub):
    use_stub(
        "echo 'error creating worktree: no Skill Manager home could be created'\n"
        "echo 'fix: /abs/bootstrap-home.sh --root /repo'\n"
        "echo 'log: /tmp/wt-run.log'\n"
        "exit 3\n"
    )
    with pytest.raises(BootstrapFailed) as err:
        wt_new("T-3")
    assert "no Skill Manager home" in err.value.reason
    assert err.value.fix.startswith("/abs/bootstrap-home.sh")
    assert err.value.log == "/tmp/wt-run.log"
    assert err.value.exit_code == 3


def test_close_refusal_maps_exit_4(use_stub):
    use_stub(
        "echo 'error closing worktree: the home still holds work (unit: test-graph)'\n"
        "echo 'fix: skill-manager home sync --from /w/.skill-manager --to /r/.skill-manager --merge'\n"
        "echo 'log: /tmp/wt-close.log'\n"
        "exit 4\n"
    )
    with pytest.raises(CloseRefused) as err:
        wt_close("T-4")
    assert "still holds work" in err.value.reason
    assert "home sync" in err.value.fix


def test_close_quiet_success_line(use_stub):
    use_stub(
        "echo 'closed worktree /tmp/repo-T-5 (branch feature/T-5 kept; home work went no further than /r/.skill-manager — push skill edits from there)'\n"
    )
    result = wt_close("T-5")
    assert result.worktree == "/tmp/repo-T-5"
    assert result.branch == "feature/T-5"


def test_close_dry_run_clean(use_stub):
    use_stub("echo 'CLEAN      /tmp/repo-T-6 — the gate found nothing'\nexit 0\n")
    result = wt_close("T-6", dry_run=True)
    assert result.dry_run_clean
    assert result.worktree == "/tmp/repo-T-6"


def test_unknown_failure_is_generic_wt_error(use_stub):
    use_stub("echo 'error: unknown verb: frobnicate'\nexit 1\n")
    with pytest.raises(WtError) as err:
        wt_info("T-7")
    assert not isinstance(err.value, (BootstrapFailed, CloseRefused, StaleBase))
    assert "unknown verb" in err.value.reason


def _git_init(path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(path)], check=True)


def test_checkout_kind_standalone(tmp_path):
    repo = tmp_path / "plain"
    repo.mkdir()
    _git_init(repo)
    assert checkout_kind(repo) == "standalone"


def test_checkout_kind_integration(tmp_path):
    repo = tmp_path / "integ"
    repo.mkdir()
    _git_init(repo)
    (repo / "integration.toml").write_text("[integration]\n")
    assert checkout_kind(repo) == "integration"


def test_checkout_kind_constituent(tmp_path):
    outer = tmp_path / "integ"
    outer.mkdir()
    _git_init(outer)
    (outer / "integration.toml").write_text("[integration]\n")
    inner = outer / "constituents" / "leaf"
    inner.mkdir(parents=True)
    _git_init(inner)
    assert checkout_kind(inner) == "constituent"


def test_wt_bin_prefers_unit_copy_without_env(monkeypatch):
    monkeypatch.delenv("GIW_WT_BIN", raising=False)
    resolved = wt_bin()
    assert resolved.name == "wt"
    assert (Path(__file__).resolve().parents[1] / "scripts" / "wt") == resolved
