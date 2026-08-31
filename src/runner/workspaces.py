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
  workspace — cwd = per-job clone (code-writing skills) + PreToolUse guard
              hooks (runner/guards.py) that deny writes outside the clone
              and dangerous host commands
  host      — explicit full-host access (god; break-glass lane, INV-18)

`container` is a retired tier (docker lane removed 2026-07-27, see
docs/SDK_MIGRATION_2026-07-27.md); frontmatter still declaring it resolves
to `workspace`.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

VALID_ISOLATION = ("none", "workspace", "host")
# Retired tiers that still parse (mapped in resolve_isolation).
_RETIRED_ISOLATION = {"container": "workspace"}


@dataclass
class Workspace:
    path: Path              # the per-job clone the session runs in
    canonical: Path         # the checkout it was cloned from
    pushes_to_origin: bool  # True if canonical has a real remote configured


# ── Pure helpers (unit-tested) ──────────────────────────────────────────────


def workspace_dir_name(job_id: str, canonical: Path) -> str:
    """Deterministic workspace directory name: <job8>-<canonical-name>."""
    return f"{str(job_id)[:8]}-{canonical.name}"


def _normalize_tier(tier: str | None, *, default: str, unknown: str) -> str | None:
    """Map a raw tier string to a valid one. Retired tiers map to their
    successor (`container` → `workspace` — INV-17); unknown strings map to
    ``unknown`` (fail closed), ``None``/empty to ``default``."""
    if not tier:
        return default
    if tier in _RETIRED_ISOLATION:
        mapped = _RETIRED_ISOLATION[tier]
        logger.info("isolation tier %r is retired — running as %r", tier, mapped)
        return mapped
    if tier not in VALID_ISOLATION:
        logger.warning("unknown isolation tier %r — treating as %r", tier, unknown)
        return unknown
    return tier


def resolve_isolation(
    skill_isolation: str | None,
    payload_isolation: str | None,
) -> str:
    """Resolve the effective isolation tier for a job. Pure function.

    Hardened 2026-08-31 (EVALUATION_2026-08-30 F1): the payload can only
    TIGHTEN isolation, never relax it. A payload may move a job onto the
    guarded ``workspace`` tier; it can never promote to ``host`` or strip a
    workspace-tier skill down to ``none`` (that was the unlabeled-god hole —
    any dispatcher could hand any skill an unguarded live-checkout session).
    Unknown tiers fail closed to ``workspace`` instead of ``none``.
    """
    skill_tier = _normalize_tier(skill_isolation, default="none", unknown="workspace")
    payload_tier = _normalize_tier(payload_isolation, default=None, unknown="workspace")
    if payload_tier is None or payload_tier == skill_tier:
        return skill_tier
    if payload_tier == "workspace":
        return "workspace"   # tightening — always allowed
    logger.warning(
        "payload isolation override %r ignored (skill tier %r) — payloads may "
        "only tighten to 'workspace'", payload_isolation, skill_tier)
    return skill_tier


# ── Git operations ──────────────────────────────────────────────────────────


def _run_git(args: list[str], cwd: Path, timeout: int = 120) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            ["git", *args], cwd=str(cwd), capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        # Never raise on a hung git (network stall). Callers branch on
        # returncode; `sync_canonical` promises "never raises", and letting a
        # timeout escape from run_session's finally would turn an already-pushed,
        # successful session into a failure that re-runs done work (M3).
        return subprocess.CompletedProcess(
            args=["git", *args], returncode=124, stdout="",
            stderr=f"git timed out after {timeout}s: git {' '.join(args)}",
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


def env_file_violation(entry: str) -> str | None:
    """Why this `delivery.env_files` entry may not be provisioned, or None if
    OK. Pure function.

    Only plain relative in-repo paths are allowed — a manifest must never be
    able to pull arbitrary host files (~/.ssh/*, /etc/*, keychain exports)
    into a workspace the session can read. Manifest validation enforces the
    same rules; this is the runner-side belt.
    """
    if not entry or not entry.strip() or entry != entry.strip():
        return "empty or whitespace-wrapped path"
    p = Path(entry)
    if p.is_absolute() or entry.startswith("~"):
        return "absolute or home-relative paths are not allowed"
    if ".." in p.parts:
        return "parent traversal is not allowed"
    return None


def provision_env_files(
    ws_path: Path, canonical: Path, env_files: list[str],
) -> list[str]:
    """Copy manifest-declared gitignored files (secrets like `.env`) from the
    canonical checkout into the workspace clone.

    `git clone` doesn't carry gitignored files, so a workspace-tier session
    otherwise never sees owner-provisioned credentials (the Alpaca-keys gap,
    2026-08-10). Opt-in per project via `delivery.env_files`; called by
    run_session right after create_workspace. Missing sources are skipped
    (the consuming code fails with its own clearer message), symlinks are
    refused (a symlink in the repo could smuggle an arbitrary host file into
    the readable workspace), and nothing here ever raises. Returns the
    entries actually copied — audited on the `workspace_created` event.
    """
    copied: list[str] = []
    for raw in env_files or []:
        entry = str(raw)
        reason = env_file_violation(entry)
        if reason:
            logger.warning("env_files entry %r refused: %s", entry, reason)
            continue
        src = canonical / entry
        dst = ws_path / entry
        try:
            if src.is_symlink():
                logger.warning("env_files entry %r refused: symlinks are not "
                               "allowed", entry)
                continue
            if not src.is_file():
                logger.info("env_files entry %r not present at canonical — "
                            "skipped", entry)
                continue
            # Resolve-containment (code-review 2026-08-10): a symlinked PARENT
            # dir (`sub/.env` where `sub` → a host dir) passes both checks
            # above — resolving catches it. Same on the write side: a
            # committed symlink in the clone (dir in the path, or dst itself)
            # would otherwise let copy2 write through to a host path.
            if not src.resolve().is_relative_to(canonical.resolve()):
                logger.warning("env_files entry %r refused: resolves outside "
                               "the canonical", entry)
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.is_symlink() or not dst.parent.resolve().is_relative_to(
                    ws_path.resolve()):
                logger.warning("env_files entry %r refused: destination "
                               "resolves outside the workspace", entry)
                continue
            shutil.copy2(src, dst)
            copied.append(entry)
        except Exception as exc:  # noqa: BLE001 — provisioning must never kill the job
            logger.warning("env_files provisioning failed for %r: %s", entry, exc)
    return copied


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
