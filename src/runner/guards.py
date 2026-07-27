"""
Session guardrails — SDK-native isolation (replaces the container lane, 2026-07-27).

Every workspace-tier session gets PreToolUse hooks that hard-deny:
  - file writes outside the per-job workspace clone (OS temp dirs excepted)
  - dangerous Bash commands: sudo, launchctl, keychain reads, force-push,
    process kills, crontab edits, ANTHROPIC_API_KEY injection, and
    destructive commands referencing protected roots (live checkouts,
    ~/.claude credentials, ~/.ssh, LaunchAgents)

Why hooks and not prompt rules: hooks run in the runner process BEFORE the
SDK's permission evaluation, so they bind even under
permission_mode=bypassPermissions (server-patch). A session cannot *prompt*
its way past them. This is policy-level isolation — weaker than the removed
docker lane against a kernel-level escape, but *enforced* rather than
requested, and it covers every workspace-tier session uniformly (the docker
lane only ever covered `server-patch`, and only when a container runtime was
configured — which by default it was not).

Residual bypasses (accepted under the single-tenant threat model): the
file-write guard is robust (paths are `.resolve()`d, defeating `~`, `..`,
and symlinks), but the Bash guard is a command-text denylist, so a
determined session could still mutate outside the clone via an interpreter
(`python -c "shutil.rmtree(...)"`), a symlink-then-redirect chain, or any
tool head not in the mutator set. These are inherent to text-level guarding;
the OS-level closure is the SDK `sandbox` (Seatbelt) follow-up tracked in
SYSTEM.md § technical debt.

Layout: pure predicates at the top (unit-tested, no I/O); the hook factory
at the bottom closes over the workspace path + job id and appends
`guard_denied` audit events on every denial.

`god` (isolation: host) deliberately gets NO guards — it is the break-glass
lane (INV-18).
"""

from __future__ import annotations

import logging
import re
import tempfile
from pathlib import Path
from typing import Any

from claude_agent_sdk import HookMatcher

from src import audit_log
from src.config import settings

logger = logging.getLogger(__name__)

# Tools whose input carries a filesystem write target.
FILE_WRITE_TOOLS = ("Write", "Edit", "MultiEdit", "NotebookEdit")

# The production checkout is protected even when the runner is started from
# the dev repo (settings.server_root would then point elsewhere).
_PROD_CHECKOUT = Path.home() / "Library" / "Application Support" / "ai-server"


def protected_roots() -> list[Path]:
    """Directories a workspace-tier session must never mutate."""
    roots = [
        settings.server_root,
        _PROD_CHECKOUT,
        Path.home() / ".claude",        # subscription credentials
        Path.home() / ".ssh",
        Path.home() / ".cloudflared",
        Path.home() / "Library" / "LaunchAgents",
    ]
    # Dedupe while preserving order (server_root == prod checkout on prod).
    seen: set[str] = set()
    out: list[Path] = []
    for r in roots:
        key = str(r)
        if key not in seen:
            seen.add(key)
            out.append(r.expanduser())
    return out


def allowed_scratch_dirs() -> list[Path]:
    """Temp locations sessions may write freely (resolved for macOS /tmp symlink)."""
    dirs = {Path("/tmp"), Path("/private/tmp"), Path("/var/folders"),
            Path(tempfile.gettempdir())}
    return [d.resolve() for d in dirs]


def _normalize(raw: str, workspace: Path) -> Path:
    """Absolute, symlink-resolved form of a tool-supplied path.
    Relative paths are anchored at the workspace (the session's cwd)."""
    p = Path(raw).expanduser()
    if not p.is_absolute():
        p = workspace / p
    return p.resolve()


def write_target_violation(
    tool_name: str,
    tool_input: dict[str, Any],
    workspace: Path,
    extra_allowed: list[Path] | None = None,
) -> str | None:
    """Return a denial reason if a file-write tool targets a path outside the
    workspace (and outside temp dirs). None = allowed. Pure function.

    INV-16/17: workspace-tier work leaves the clone only via git push, so
    strict containment IS the policy — not just protected-root avoidance.
    """
    if tool_name not in FILE_WRITE_TOOLS:
        return None
    raw = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
    if not raw:
        return None
    target = _normalize(str(raw), workspace)
    allowed = [workspace.resolve(), *(extra_allowed if extra_allowed is not None
                                      else allowed_scratch_dirs())]
    for root in allowed:
        if target == root or target.is_relative_to(root):
            return None
    return (f"{tool_name} outside the job workspace is denied "
            f"(target: {target}). Work only inside {workspace}; "
            f"changes leave via git push (INV-16/17).")


# ── Bash guard ──────────────────────────────────────────────────────────────

# Commands denied outright for workspace-tier sessions, regardless of target.
_HARD_DENY_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bsudo\b"), "sudo"),
    (re.compile(r"\blaunchctl\b"), "launchctl (service management is host-tier only)"),
    (re.compile(r"\bsecurity\s+(?:find|dump|export|delete|unlock)"),
     "keychain access via `security`"),
    # Force-push in any spelling: -f / --force / --force-with-lease, or a
    # leading `+` on a refspec (`git push origin +main:main`).
    (re.compile(r"\bpush\b[^\n;|&]*\s(?:-f\b|--force\b|--force-with-lease\b|\+\S)"),
     "force-push"),
    (re.compile(r"\b(?:killall|pkill|kill)\b"), "process kills"),
    (re.compile(r"\bcrontab\b"), "crontab"),
    (re.compile(r"\bANTHROPIC_API_KEY\s*="), "ANTHROPIC_API_KEY assignment (INV-3)"),
    (re.compile(r"\bexport\s+ANTHROPIC_API_KEY\b"), "ANTHROPIC_API_KEY export (INV-3)"),
]

# Command heads that mutate the filesystem: when one of these appears in a
# command that also references a protected root, deny. Read-only commands
# (grep/cat/git log on the canonical) stay allowed. Git history-rewriting
# subcommands are included because `git -C <root> reset --hard` /
# `cd <root> && git checkout -- .` is the 2026-07-09 single-writer incident
# class — but only when a protected root is referenced, so in-workspace git
# (cwd = the clone, masked to «WS» before matching) stays free.
_MUTATOR_PATTERN = re.compile(
    r"(?:^|[;&|]\s*)\s*(?:rm|rmdir|mv|cp|dd|tee|truncate|chmod|chown|ln|rsync)\b"
    r"|\bsed\s+(?:-[a-zA-Z]*i[a-zA-Z]*\b|--in-place\b)"
    r"|\bgit\b[^\n;|&]*\b(?:reset|checkout|clean|restore)\b"
    r"|\bfind\b[^\n;|&]*\s-delete\b"
    r"|>{1,2}\s*\S"
)


def _spacify(literal: str) -> str:
    """Escape a path literal so each space matches a plain OR backslash-escaped
    space — sessions spell `Application Support` and `Application\\ Support`."""
    return r"(?:\\ | )".join(re.escape(part) for part in literal.split(" "))


def _root_ref_pattern(root: Path) -> re.Pattern[str]:
    # Match the root path only at a path boundary so /x/ai-server doesn't
    # match /x/ai-server-backup. Roots under $HOME also match the spellings a
    # shell command actually uses: ~/, $HOME/, ${HOME}/ (the production
    # checkout path contains a space, so those are the realistic forms).
    boundary = r"(?=/|['\"\s]|$)"
    root_str = str(root)
    alts = [_spacify(root_str)]
    home = str(Path.home())
    if root_str.startswith(home + "/"):
        tail = _spacify(root_str[len(home):])   # keeps leading /
        for prefix in (r"~", r"\$HOME", r"\$\{HOME\}"):
            alts.append(prefix + tail)
    return re.compile("(?:" + "|".join(alts) + ")" + boundary)


def bash_violation(
    command: str,
    workspace: Path,
    roots: list[Path] | None = None,
) -> str | None:
    """Return a denial reason for a Bash command, or None. Pure function.

    The workspace path is masked out first: workspace clones live UNDER
    server_root (volumes/workspaces/...), so a naive substring scan would
    deny legitimate in-workspace commands.
    """
    if not command:
        return None
    masked = command.replace(str(workspace.resolve()), "«WS»")
    masked = masked.replace(str(workspace), "«WS»")

    for pattern, label in _HARD_DENY_PATTERNS:
        if pattern.search(masked):
            return f"Bash denied: {label}."

    if _MUTATOR_PATTERN.search(masked):
        for root in (roots if roots is not None else protected_roots()):
            if _root_ref_pattern(root).search(masked):
                return (f"Bash denied: destructive command references protected "
                        f"path {root}. Work only inside your workspace clone "
                        f"(INV-16/17).")
    return None


# ── Hook factory ────────────────────────────────────────────────────────────


def _deny(reason: str) -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def make_guard_hooks(job_id: str, workspace: Path) -> dict[str, list[HookMatcher]]:
    """PreToolUse guard hooks for one workspace-tier session.

    Wire into ClaudeAgentOptions(hooks=...). Denials are audited as
    `guard_denied` events so retrospective can see attempted escapes.
    """
    roots = protected_roots()
    scratch = allowed_scratch_dirs()

    async def _guard_file(input_data: dict, tool_use_id: str | None, context: Any) -> dict:
        tool = input_data.get("tool_name", "")
        reason = write_target_violation(
            tool, input_data.get("tool_input") or {}, workspace, scratch,
        )
        if reason:
            audit_log.append(job_id, "guard_denied", tool_name=tool, reason=reason)
            logger.warning("guard denied %s for job %s: %s", tool, job_id[:8], reason)
            return _deny(reason)
        return {}

    async def _guard_bash(input_data: dict, tool_use_id: str | None, context: Any) -> dict:
        command = (input_data.get("tool_input") or {}).get("command", "")
        reason = bash_violation(command, workspace, roots)
        if reason:
            audit_log.append(job_id, "guard_denied", tool_name="Bash",
                             reason=reason, command=command[:300])
            logger.warning("guard denied Bash for job %s: %s", job_id[:8], reason)
            return _deny(reason)
        return {}

    return {
        "PreToolUse": [
            HookMatcher(matcher="|".join(FILE_WRITE_TOOLS), hooks=[_guard_file]),
            HookMatcher(matcher="Bash", hooks=[_guard_bash]),
        ]
    }
