"""
Write-back verification. After a session ends, check whether the session
modified tracked files without updating a CHANGELOG. If yes, enqueue a
child `_writeback` job that will update the CHANGELOG(s).

This enforces the write-back protocol from `.context/PROTOCOL.md` even when
the primary skill's author forgot to include write-back in their procedure.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def _run(cmd: list[str], cwd: Path) -> str:
    """Run a command and return stdout; empty string on any error."""
    try:
        r = subprocess.run(
            cmd, cwd=str(cwd), check=False, capture_output=True, text=True, timeout=10
        )
        return r.stdout
    except Exception:
        return ""


def needs_writeback(cwd: Path) -> tuple[bool, list[str]]:
    """
    Return (needs_writeback, list_of_modified_files).

    `needs_writeback` is True iff:
      - cwd is a git repo, AND
      - there are modified/added tracked files (including untracked), AND
      - at least one non-doc file was modified, AND
      - no CHANGELOG.md was modified among the changes.

    "Doc file" = anything under .context/ or a top-level CHANGELOG.md.
    A non-doc file is code, config, a non-changelog .md, or anything else.

    When cwd is not a git repo, returns (False, []). This is intentional —
    write-back verification only applies to git-tracked directories.
    """
    if not (cwd / ".git").exists():
        return (False, [])

    # Get modified + added + untracked files (relative to cwd).
    # --untracked-files=all lists individual files inside new directories instead
    # of just showing the directory name.
    out = _run(["git", "status", "--porcelain", "--untracked-files=all"], cwd)
    if not out.strip():
        return (False, [])

    modified: list[str] = []
    for line in out.splitlines():
        # porcelain format: "XY <path>" where X, Y are status chars
        if len(line) < 4:
            continue
        path = line[3:].strip()
        # Handle renames like "R  old -> new"
        if "->" in path:
            path = path.split("->")[-1].strip()
        modified.append(path)

    if not modified:
        return (False, [])

    # Classify
    changelog_modified = any(
        p.endswith("CHANGELOG.md") or p.endswith("CHANGELOG.md\"") for p in modified
    )
    non_doc_modified = any(
        not _is_doc_path(p) for p in modified
    )

    return (non_doc_modified and not changelog_modified, modified)


def _is_doc_path(path: str) -> bool:
    """Is this path a documentation / context file that doesn't itself need a CHANGELOG?"""
    if path.startswith(".context/"):
        return True
    if path.endswith("CHANGELOG.md"):
        return True
    if path.endswith("CONTEXT.md"):
        return True
    if path.endswith("SKILL.md") or "/skills/" in path or path.startswith("skills/"):
        # Skill files are their own record
        return True
    if path.startswith("docs/"):
        return True
    # Top-level markdown files (README.md, MISSION.md, SERVER.md, CLAUDE.md,
    # TEARDOWN.md, GETSTARTED.md) are documentation, not code.
    if "/" not in path and path.endswith(".md"):
        return True
    return False
