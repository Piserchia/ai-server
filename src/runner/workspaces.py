"""
Per-job workspace isolation (P1).

A workspace is a throwaway local git clone of the job's canonical checkout
(a project under `projects/<slug>/`, or the server root itself). The session
runs with cwd = workspace, commits there, and pushes to the SAME remote the
canonical uses — so every skill's existing "commit and push origin main"
instructions keep working unchanged. After a successful push the canonical
checkout is fast-forwarded to pick the work up.

Why clones and not `git worktree`: worktrees share branches with the parent
checkout (two jobs on `main` would collide — the exact single-writer incident
class from 2026-07-09), and a worktree cannot check out the branch the
canonical already has. A local clone is cheap on APFS (objects are
hardlinked) and gives each job a fully independent index/HEAD.

Layout: `volumes/workspaces/<job8>-<name>/`
Cleanup: removed on job success; kept on failure for debugging (server-upkeep
prunes anything older than WORKSPACE_RETENTION_DAYS).

Isolation tiers (skill frontmatter `isolation:`):
  none      — cwd = canonical path (legacy behavior; read-only-ish skills)
  workspace — cwd = per-job clone (code-writing skills)
  container — workspace + execution inside a container (see executors.py);
              falls back to `workspace` when no container runtime configured
  host      — explicit full-host access (god; break-glass lane)
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

VALID_ISOLATION = ("none", "workspace", "container", "host")


@dataclass
class Workspace:
    path: Path              # the per-job clone the session runs in
    canonical: Path         # the checkout it was cloned from
    pushes_to_origin: bool  # True if canonical has a real remote configured


# ── Pure helpers (unit-tested) ──────────────────────────────────────────────


def workspace_dir_name(job_id: str, canonical: Path) -> str:
    """Deterministic workspace directory name: <job8>-<canonical-name>."""
    return f"{str(job_id)[:8]}-{canonical.name}"


def resolve_isolation(
    skill_isolation: str | None,
    payload_isolation: str | None,
    container_available: bool,
    needs_in_process_mcp: bool,
) -> str:
    """Resolve the effective isolation tier for a job. Pure function.

    Precedence: payload override > skill frontmatter > "none".
    Downgrades:
      container → workspace when no container runtime is available
      container → workspace when the skill needs in-process MCP servers
        (SDK MCP servers live in the runner process and can't cross a
        container boundary)
    """
    tier = payload_isolation or skill_isolation or "none"
    if tier not in VALID_ISOLATION:
        logger.warning("unknown isolation tier %r — treating as 'none'", tier)
        return "none"
    if tier == "container" and (not container_available or needs_in_process_mcp):
        return "workspace"
    return tier


# ── Git operations ──────────────────────────────────────────────────────────


def _run_git(args: list[str], cwd: Path, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, timeout=timeout,
    )


def is_git_repo(path: Path) -> bool:
    return (path / ".git").exists()


def create_workspace(job_id: str, canonical: Path, base_dir: Path) -> Workspace:
    """Create a per-job workspace clone of `canonical` under `base_dir`.

    - git repo canonical: `git clone --no-hardlinks=false` (local clone;
      objects shared) then point `origin` at the canonical's own origin URL
      so `git push origin main` goes to the real remote, exactly as the
      skill instructions say. If the canonical has no remote, origin stays
      pointed at the canonical itself (push lands there; canonical sync is
      then a no-op fetch).
    - non-git canonical: plain copy (isolation without git flow).

    Raises RuntimeError on clone failure — callers treat that as a job
    preflight error rather than running un-isolated.
    """
    base_dir.mkdir(parents=True, exist_ok=True)
    ws_path = base_dir / workspace_dir_name(job_id, canonical)
    if ws_path.exists():
        shutil.rmtree(ws_path)

    if not is_git_repo(canonical):
        shutil.copytree(canonical, ws_path, symlinks=True)
        logger.info("workspace (copy) created: %s", ws_path)
        return Workspace(path=ws_path, canonical=canonical, pushes_to_origin=False)

    res = _run_git(["clone", "--no-checkout", str(canonical), str(ws_path)], cwd=base_dir)
    if res.returncode != 0:
        raise RuntimeError(f"workspace clone failed: {res.stderr[:500]}")
    # Check out the canonical's current branch state
    res = _run_git(["checkout", "-f", "HEAD"], cwd=ws_path)
    branch = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=canonical).stdout.strip()
    if branch and branch != "HEAD":
        _run_git(["checkout", "-B", branch, f"origin/{branch}"], cwd=ws_path)

    # Re-point origin at the canonical's real remote (if any)
    real_origin = _run_git(["remote", "get-url", "origin"], cwd=canonical)
    pushes_to_origin = False
    if real_origin.returncode == 0 and real_origin.stdout.strip():
        url = real_origin.stdout.strip()
        _run_git(["remote", "set-url", "origin", url], cwd=ws_path)
        pushes_to_origin = True

    logger.info("workspace (clone) created: %s (origin→%s)",
                ws_path, "remote" if pushes_to_origin else "canonical")
    return Workspace(path=ws_path, canonical=canonical, pushes_to_origin=pushes_to_origin)


def sync_canonical(ws: Workspace) -> tuple[bool, str]:
    """After a session pushed from its workspace, fast-forward the canonical.

    Returns (ok, message). Never raises. A refused ff (dirty canonical /
    divergence) is reported, not forced — same single-writer discipline as
    atlas-redeploy.
    """
    if not is_git_repo(ws.canonical):
        return True, "canonical is not a git repo — nothing to sync"
    if not ws.pushes_to_origin:
        # Workspace pushed straight into the canonical (it *was* origin).
        # A push to a checked-out branch is refused by git by default, so
        # fetch from the workspace instead.
        res = _run_git(["fetch", str(ws.path)], cwd=ws.canonical)
        if res.returncode != 0:
            return False, f"canonical fetch from workspace failed: {res.stderr[:300]}"
        res = _run_git(["merge", "--ff-only", "FETCH_HEAD"], cwd=ws.canonical)
        return (res.returncode == 0,
                res.stderr[:300] if res.returncode != 0 else "canonical fast-forwarded from workspace")

    res = _run_git(["pull", "--ff-only"], cwd=ws.canonical, timeout=180)
    if res.returncode != 0:
        return False, f"canonical ff-pull refused: {res.stderr[:300]}"
    return True, "canonical fast-forwarded from origin"


def cleanup_workspace(ws: Workspace, *, keep: bool = False) -> None:
    """Remove the workspace directory (unless keep=True, e.g. failed jobs)."""
    if keep:
        logger.info("workspace kept for debugging: %s", ws.path)
        return
    try:
        shutil.rmtree(ws.path)
    except Exception as exc:  # noqa: BLE001 — cleanup must never kill the job flow
        logger.warning("workspace cleanup failed for %s: %s", ws.path, exc)


def prune_old_workspaces(base_dir: Path, max_age_days: int = 7) -> list[str]:
    """Delete workspace dirs older than max_age_days. Returns removed names.
    Called by server-upkeep."""
    import time
    removed: list[str] = []
    if not base_dir.exists():
        return removed
    cutoff = time.time() - max_age_days * 86400
    for child in base_dir.iterdir():
        try:
            if child.is_dir() and child.stat().st_mtime < cutoff:
                shutil.rmtree(child)
                removed.append(child.name)
        except Exception as exc:  # noqa: BLE001
            logger.warning("workspace prune failed for %s: %s", child, exc)
    return removed
