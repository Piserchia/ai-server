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
        assert resolve_isolation(None, None) == "none"

    def test_skill_frontmatter_wins_over_default(self):
        assert resolve_isolation("workspace", None) == "workspace"

    def test_payload_may_only_tighten(self):
        # Hardened 2026-08-31 (EVALUATION_2026-08-30 F1): payloads tighten,
        # never relax or promote.
        assert resolve_isolation("none", "workspace") == "workspace"
        assert resolve_isolation("host", "workspace") == "workspace"
        assert resolve_isolation("workspace", "none") == "workspace"

    def test_payload_cannot_promote_to_host(self):
        assert resolve_isolation("none", "host") == "none"
        assert resolve_isolation("workspace", "host") == "workspace"

    def test_retired_container_tier_maps_to_workspace(self):
        # The docker lane was removed 2026-07-27; old frontmatter/payloads
        # must keep working and land on the guarded workspace tier.
        assert resolve_isolation("container", None) == "workspace"
        assert resolve_isolation(None, "container") == "workspace"

    def test_host_never_downgrades(self):
        assert resolve_isolation("host", None) == "host"
        assert resolve_isolation("host", "none") == "host"

    def test_unknown_tier_fails_closed_to_workspace(self):
        assert resolve_isolation("vmware", None) == "workspace"
        assert resolve_isolation("none", "vmware") == "workspace"


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


# ── provision_env_files (env-secret provisioning, 2026-08-10) ───────────────


from src.runner.workspaces import env_file_violation, provision_env_files  # noqa: E402


class TestEnvFileViolation:
    def test_plain_relative_ok(self):
        assert env_file_violation(".env") is None
        assert env_file_violation("config/.env.local") is None

    def test_absolute_refused(self):
        assert env_file_violation("/etc/passwd") is not None

    def test_home_refused(self):
        assert env_file_violation("~/.ssh/id_rsa") is not None

    def test_traversal_refused(self):
        assert env_file_violation("../other/.env") is not None

    def test_empty_and_whitespace_refused(self):
        assert env_file_violation("") is not None
        assert env_file_violation("  .env") is not None


class TestProvisionEnvFiles:
    def test_gitignored_env_reaches_workspace(self, canonical_repo: Path, tmp_path: Path):
        # The motivating case: .env is gitignored at the canonical, so the
        # clone doesn't carry it — provisioning must copy it in.
        (canonical_repo / ".gitignore").write_text(".env\n")
        (canonical_repo / ".env").write_text("ALPACA_KEY_ID=k\nALPACA_SECRET=s\n")
        ws = create_workspace("job12345", canonical_repo, tmp_path / "workspaces")
        assert not (ws.path / ".env").exists()  # clone alone doesn't carry it

        copied = provision_env_files(ws.path, canonical_repo, [".env"])
        assert copied == [".env"]
        assert (ws.path / ".env").read_text().startswith("ALPACA_KEY_ID=")

    def test_missing_source_skipped(self, canonical_repo: Path, tmp_path: Path):
        ws = create_workspace("job12345", canonical_repo, tmp_path / "workspaces")
        assert provision_env_files(ws.path, canonical_repo, [".env"]) == []

    def test_nested_path_creates_parent(self, canonical_repo: Path, tmp_path: Path):
        sub = canonical_repo / "svc"
        sub.mkdir()
        (sub / ".env").write_text("K=v\n")
        ws = create_workspace("job12345", canonical_repo, tmp_path / "workspaces")
        copied = provision_env_files(ws.path, canonical_repo, ["svc/.env"])
        assert copied == ["svc/.env"]
        assert (ws.path / "svc" / ".env").read_text() == "K=v\n"

    def test_violations_and_symlinks_refused(self, canonical_repo: Path, tmp_path: Path):
        outside = tmp_path / "outside-secret"
        outside.write_text("stolen")
        (canonical_repo / "link.env").symlink_to(outside)
        ws = create_workspace("job12345", canonical_repo, tmp_path / "workspaces")
        copied = provision_env_files(
            ws.path, canonical_repo,
            ["/etc/passwd", "../outside-secret", "link.env"])
        assert copied == []
        assert not (ws.path / "link.env").exists()

    def test_never_raises_on_unwritable_dst(self, canonical_repo: Path, tmp_path: Path):
        (canonical_repo / ".env").write_text("K=v\n")
        ws = create_workspace("job12345", canonical_repo, tmp_path / "workspaces")
        # dst parent path occupied by a FILE → mkdir/copy fails; must not raise
        (ws.path / "blocked").write_text("i am a file")
        copied = provision_env_files(ws.path, canonical_repo, ["blocked/.env", ".env"])
        assert copied == [".env"]

    def test_symlinked_parent_dir_refused(self, canonical_repo: Path, tmp_path: Path):
        # code-review 2026-08-10: `sub/.env` where `sub` is a symlink to a
        # host dir passes the final-component symlink check — resolve-
        # containment must catch it.
        host_dir = tmp_path / "host-secrets"
        host_dir.mkdir()
        (host_dir / ".env").write_text("stolen")
        (canonical_repo / "sub").symlink_to(host_dir)
        ws = create_workspace("job12345", canonical_repo, tmp_path / "workspaces")
        assert provision_env_files(ws.path, canonical_repo, ["sub/.env"]) == []

    def test_symlink_destination_not_written_through(self, canonical_repo: Path, tmp_path: Path):
        # A committed symlink at the dst path would let copy2 write through
        # to a host file — must be refused, host target untouched.
        (canonical_repo / ".env").write_text("K=v\n")
        ws = create_workspace("job12345", canonical_repo, tmp_path / "workspaces")
        host_target = tmp_path / "host-file"
        host_target.write_text("original")
        (ws.path / ".env").symlink_to(host_target)
        assert provision_env_files(ws.path, canonical_repo, [".env"]) == []
        assert host_target.read_text() == "original"
