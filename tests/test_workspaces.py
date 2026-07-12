"""Tests for runner/workspaces.py — per-job isolation (P1).

Pure-function tests plus real-git integration tests using temp repos
(no network, no SDK, no DB).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from src.runner.workspaces import (
    Workspace,
    cleanup_workspace,
    create_workspace,
    is_git_repo,
    prune_old_workspaces,
    resolve_isolation,
    sync_canonical,
    workspace_dir_name,
)


# ── resolve_isolation (pure) ────────────────────────────────────────────────


class TestResolveIsolation:
    def test_default_is_none(self):
        assert resolve_isolation(None, None, False, False) == "none"

    def test_skill_frontmatter_wins_over_default(self):
        assert resolve_isolation("workspace", None, False, False) == "workspace"

    def test_payload_override_wins_over_skill(self):
        assert resolve_isolation("workspace", "none", False, False) == "none"
        assert resolve_isolation("none", "workspace", False, False) == "workspace"

    def test_container_downgrades_without_runtime(self):
        assert resolve_isolation("container", None, False, False) == "workspace"

    def test_container_downgrades_with_in_process_mcp(self):
        assert resolve_isolation("container", None, True, True) == "workspace"

    def test_container_sticks_when_available(self):
        assert resolve_isolation("container", None, True, False) == "container"

    def test_host_never_downgrades(self):
        assert resolve_isolation("host", None, False, False) == "host"

    def test_unknown_tier_treated_as_none(self):
        assert resolve_isolation("vmware", None, True, False) == "none"


def test_workspace_dir_name():
    assert workspace_dir_name("abcd1234-5678", Path("/x/projects/bingo")) == "abcd1234-bingo"


# ── git integration (temp repos) ────────────────────────────────────────────


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, check=False,
    )


@pytest.fixture()
def canonical_repo(tmp_path: Path) -> Path:
    """A 'remote' bare repo + a canonical clone of it, mimicking
    projects/<slug> with a real origin."""
    remote = tmp_path / "remote.git"
    remote.mkdir()
    _git(["init", "--bare", "--initial-branch=main"], remote)

    canonical = tmp_path / "canonical"
    _git(["clone", str(remote), str(canonical)], tmp_path)
    (canonical / "app.py").write_text("print('v1')\n")
    _git(["add", "-A"], canonical)
    _git(["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-m", "v1"], canonical)
    _git(["push", "origin", "main"], canonical)
    return canonical


class TestCreateWorkspace:
    def test_clone_created_with_real_origin(self, canonical_repo: Path, tmp_path: Path):
        ws = create_workspace("job12345", canonical_repo, tmp_path / "workspaces")
        assert ws.path.exists()
        assert (ws.path / "app.py").read_text() == "print('v1')\n"
        assert ws.pushes_to_origin is True
        # origin must point at the REAL remote, not the canonical clone
        url = _git(["remote", "get-url", "origin"], ws.path).stdout.strip()
        assert url.endswith("remote.git")

    def test_workspace_is_independent(self, canonical_repo: Path, tmp_path: Path):
        ws = create_workspace("job12345", canonical_repo, tmp_path / "workspaces")
        (ws.path / "app.py").write_text("print('v2')\n")
        # canonical untouched
        assert (canonical_repo / "app.py").read_text() == "print('v1')\n"

    def test_two_jobs_get_separate_workspaces(self, canonical_repo: Path, tmp_path: Path):
        ws1 = create_workspace("aaaa1111", canonical_repo, tmp_path / "workspaces")
        ws2 = create_workspace("bbbb2222", canonical_repo, tmp_path / "workspaces")
        assert ws1.path != ws2.path

    def test_non_git_canonical_copies(self, tmp_path: Path):
        canonical = tmp_path / "plain"
        canonical.mkdir()
        (canonical / "f.txt").write_text("x")
        ws = create_workspace("job12345", canonical, tmp_path / "workspaces")
        assert (ws.path / "f.txt").read_text() == "x"
        assert ws.pushes_to_origin is False


class TestSyncCanonical:
    def test_push_then_sync_fast_forwards_canonical(self, canonical_repo: Path, tmp_path: Path):
        ws = create_workspace("job12345", canonical_repo, tmp_path / "workspaces")
        # Session-style change: commit in workspace, push to origin main
        (ws.path / "app.py").write_text("print('v2')\n")
        _git(["add", "-A"], ws.path)
        _git(["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-m", "v2"], ws.path)
        push = _git(["push", "origin", "main"], ws.path)
        assert push.returncode == 0, push.stderr

        ok, msg = sync_canonical(ws)
        assert ok, msg
        assert (canonical_repo / "app.py").read_text() == "print('v2')\n"

    def test_sync_with_no_push_is_noop_ok(self, canonical_repo: Path, tmp_path: Path):
        ws = create_workspace("job12345", canonical_repo, tmp_path / "workspaces")
        ok, _ = sync_canonical(ws)
        assert ok

    def test_dirty_canonical_refuses_not_forces(self, canonical_repo: Path, tmp_path: Path):
        ws = create_workspace("job12345", canonical_repo, tmp_path / "workspaces")
        (ws.path / "app.py").write_text("print('v2')\n")
        _git(["add", "-A"], ws.path)
        _git(["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-m", "v2"], ws.path)
        _git(["push", "origin", "main"], ws.path)
        # canonical has conflicting local edit
        (canonical_repo / "app.py").write_text("print('local hack')\n")
        ok, msg = sync_canonical(ws)
        assert not ok
        # single-writer discipline: local edit is preserved, not clobbered
        assert (canonical_repo / "app.py").read_text() == "print('local hack')\n"
        assert msg


class TestCleanupAndPrune:
    def test_cleanup_removes(self, canonical_repo: Path, tmp_path: Path):
        ws = create_workspace("job12345", canonical_repo, tmp_path / "workspaces")
        cleanup_workspace(ws)
        assert not ws.path.exists()

    def test_cleanup_keep_preserves(self, canonical_repo: Path, tmp_path: Path):
        ws = create_workspace("job12345", canonical_repo, tmp_path / "workspaces")
        cleanup_workspace(ws, keep=True)
        assert ws.path.exists()

    def test_prune_old(self, tmp_path: Path):
        base = tmp_path / "workspaces"
        base.mkdir()
        old = base / "old-ws"
        old.mkdir()
        import os
        import time
        stale = time.time() - 10 * 86400
        os.utime(old, (stale, stale))
        fresh = base / "fresh-ws"
        fresh.mkdir()
        removed = prune_old_workspaces(base, max_age_days=7)
        assert removed == ["old-ws"]
        assert fresh.exists()


def test_is_git_repo(tmp_path: Path, canonical_repo: Path):
    assert is_git_repo(canonical_repo)
    assert not is_git_repo(tmp_path)
