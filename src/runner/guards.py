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

A second profile lives here too (2026-07-31): the READ-ONLY profile for
oversight skills (`privilege_class: read-only` — managers, the CEO,
connectors/auditors, deploy-director). Those skills observe and *dispatch*
(enqueue gated worker jobs) but must be physically unable to mutate anything.
Because `permission_mode: plan` blocks MCP tool calls (proven live
2026-07-30), dispatch-capable oversight skills run acceptEdits — so their
read-only-ness cannot rest on the permission mode; these hooks make it
structural. See `make_readonly_guard_hooks` for the honest guarantee.

Layout: pure predicates at the top (unit-tested, no I/O); the hook factories
at the bottom close over the job id (+ workspace path for the workspace
profile) and append `guard_denied` audit events on every denial.

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
# (grep/cat/git log on the canonical) stay allowed. Git write subcommands
# (reset/checkout/clean/restore/commit/add/rebase/merge) are included because
# `git -C <root> reset --hard` / `cd <runtime-clone> && git add -A && git
# commit` is the 2026-07-09 single-writer incident class AND the exact
# violation the delivery contract's pull-only rule forbids — but ONLY when a
# protected root is referenced, so in-workspace git (cwd = the clone, masked to
# «WS» before matching) stays free. Note: guards bind workspace-tier sessions
# only, so content projects that legitimately commit (isolation: none) are
# never affected.
_MUTATOR_PATTERN = re.compile(
    r"(?:^|[;&|]\s*)\s*(?:rm|rmdir|mv|cp|dd|tee|truncate|chmod|chown|ln|rsync)\b"
    r"|\bsed\s+(?:-[a-zA-Z]*i[a-zA-Z]*\b|--in-place\b)"
    r"|\bgit\b[^\n;|&]*\b(?:reset|checkout|clean|restore|commit|add|rebase|merge)\b"
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


# ── Read-only profile (oversight tier) ──────────────────────────────────────
#
# Structural enforcement of `privilege_class: read-only`. Unlike the workspace
# profile (which contains writers to their clone), this profile denies file
# mutation OUTRIGHT — no path exceptions, not even temp dirs. The one
# sanctioned state change of the tier is dispatch (`enqueue_job`), which these
# guards deliberately never match.

# The projects-MCP restart tool (registered as `restart_project` in
# mcp_projects.py, surfaced to sessions as `mcp__projects__restart_project`).
# Matched by suffix so the deny holds however the server name is prefixed.
RESTART_TOOL_SUFFIX = "restart_project"


def readonly_file_violation(tool_name: str) -> str | None:
    """Return a denial reason if a file-mutation tool is used AT ALL.
    None = not a file-mutation tool. Pure function — no path is consulted
    because no path makes the call legal for a read-only session."""
    if tool_name in FILE_WRITE_TOOLS:
        return (
            f"{tool_name} is denied: this session runs the read-only guard "
            f"profile and never mutates files — anywhere, temp dirs included. "
            f"Put the change in your report, or dispatch a gated worker via "
            f"enqueue_job (the profile's only sanctioned state change)."
        )
    return None


# Hard denials regardless of arguments — same class as the workspace profile's
# hard-deny list, EXCEPT bare `launchctl`: `launchctl list`/`print` are
# legitimate read-only preflight (deploy-director), so only launchctl's
# mutating subcommands are denied (in _RO_MUTATORS below).
_RO_HARD_DENY: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bsudo\b"), "sudo"),
    (re.compile(r"\b(?:killall|pkill|kill)\b"), "process kills"),
    (re.compile(r"\bcrontab\b"), "crontab"),
    (re.compile(r"\bsecurity\s+(?:find|dump|export|delete|unlock)"),
     "keychain access via `security`"),
    (re.compile(r"\bANTHROPIC_API_KEY\s*="), "ANTHROPIC_API_KEY assignment (INV-3)"),
    (re.compile(r"\bexport\s+ANTHROPIC_API_KEY\b"), "ANTHROPIC_API_KEY export (INV-3)"),
]

# Mutating command patterns, each with a label that lands in the denial reason.
_RO_MUTATORS: list[tuple[re.Pattern[str], str]] = [
    # File mutators at command-head position (start of command or after ;|&),
    # so `grep rm src/` or a filename containing "cp" can't trip it.
    (re.compile(
        r"(?:^|[;&|]\s*)\s*(?:rm|rmdir|mv|cp|dd|tee|truncate|mkdir|touch"
        r"|chmod|chown|ln|rsync)\b"),
     "file mutator (rm/mv/cp/mkdir/touch/chmod/chown/ln/tee/…)"),
    (re.compile(r"\bsed\s+(?:-[a-zA-Z]*i[a-zA-Z]*\b|--in-place\b)"),
     "sed -i (in-place edit; pipe-through sed is fine)"),
    (re.compile(r"\bfind\b[^\n;|&]*\s-delete\b"), "find -delete"),
    # Git mutators. `git fetch` is deliberately ABSENT — refs-only metadata,
    # the sanctioned exception (pending-range derivation needs current remote
    # refs). log/status/diff/rev-parse/remote/show carry no listed verb.
    # (?!-) keeps flag-words like `--merge-base` from false-positiving.
    (re.compile(
        r"\bgit\b[^\n;|&]*\b(?:push|commit|add|checkout|reset|merge|pull"
        r"|rebase|stash|cherry-pick|clean|restore)\b(?!-)"),
     "git mutator (only `git fetch` may touch refs; log/status/diff/rev-parse are fine)"),
    # Service management — list/print stay allowed.
    (re.compile(
        r"\blaunchctl\b[^\n;|&]*\b(?:kickstart|kill|bootout|bootstrap|stop"
        r"|start|load|unload|enable|disable)\b"),
     "launchctl service mutation (list/print are fine)"),
    # Schema/data migrations.
    (re.compile(r"\balembic\b[^\n;|&]*\b(?:upgrade|downgrade|revision|stamp)\b"),
     "alembic migration command (current/heads/history are fine)"),
    (re.compile(r"\bdbmate\b"), "dbmate"),
    (re.compile(r"\b(?:createdb|dropdb)\b"), "createdb/dropdb"),
    # Package/environment managers.
    (re.compile(r"\b(?:pip3?|pipenv)\b[^\n;|&]*\b(?:install|uninstall|sync|lock)\b"),
     "pip/pipenv environment mutation (pipenv run <read-only cmd> is fine)"),
    (re.compile(r"\b(?:npm|npx)\b[^\n;|&]*\b(?:install|ci|add|uninstall|update|publish)\b"),
     "npm/npx package mutation"),
    (re.compile(r"\bbrew\b[^\n;|&]*\b(?:install|uninstall|upgrade|services)\b"),
     "brew mutation"),
    # Redis mutators — get/llen/lrange/keys/ping stay allowed.
    (re.compile(
        r"\bredis-cli\b[^\n;|&]*\b(?:set|del|rpush|lpush|lpop|rpop|blpop"
        r"|brpop|flushall|flushdb|expire)\b", re.IGNORECASE),
     "redis-cli mutator (get/llen/lrange/ping are fine)"),
]

# SQL write verbs at statement-start position inside a psql invocation.
# Statement-start = right after a quote, paren, `;`, newline, or the string
# start — NOT after a hyphen/underscore, so identifiers like
# `project-update-poll` or `created_at` inside a SELECT never false-positive.
_RO_SQL_VERB = re.compile(
    r"""(?:^|["'();\n])\s*(?:insert|update|delete|drop|alter|create|truncate|grant)\b""",
    re.IGNORECASE,
)
_PSQL_REF = re.compile(r"\bpsql\b")

# Output redirection — checked with quoted segments masked out, so SQL
# comparisons (`WHERE created_at > NOW()`) and quoted sed/awk programs don't
# false-positive. `>/dev/null` (any fd) and fd-dups (`2>&1`) stay allowed.
_QUOTED_SEGMENT = re.compile(r"'[^']*'|\"[^\"]*\"")
_REDIRECT = re.compile(r"\d?>{1,2}\s*(\S+)")


def readonly_bash_violation(command: str) -> str | None:
    """Return a denial reason for a Bash command under the READ-ONLY profile,
    or None. Pure function.

    Denies mutation by pattern: output redirection (except /dev/null and fd
    dups), file/git/service/migration/package/redis mutators, and psql with a
    write verb. Deliberately allows the inspection vocabulary oversight
    skills actually use: SELECT queries, `git log/status/diff/rev-parse/
    fetch`, grep/ls/cat/tail, `curl` healthchecks, `redis-cli get/llen/
    lrange/ping`, `pipenv run alembic current/heads`, `launchctl list`.

    This is a best-effort denylist, not a sandbox — see
    make_readonly_guard_hooks for the honest guarantee.
    """
    if not command:
        return None

    for pattern, label in _RO_HARD_DENY:
        if pattern.search(command):
            return f"Bash denied (read-only profile): {label}."

    for pattern, label in _RO_MUTATORS:
        if pattern.search(command):
            return (f"Bash denied (read-only profile): {label}. This session "
                    f"never mutates state; put the change in your report or "
                    f"dispatch a gated worker via enqueue_job.")

    if _PSQL_REF.search(command) and _RO_SQL_VERB.search(command):
        return ("Bash denied (read-only profile): psql with a write verb "
                "(INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/TRUNCATE/GRANT). "
                "SELECT and \\d/\\dt inspection are fine.")

    masked = _QUOTED_SEGMENT.sub("''", command)
    for m in _REDIRECT.finditer(masked):
        target = m.group(1)
        if target.startswith("/dev/null") or target.startswith("&"):
            continue  # bit bucket / fd duplication — no file is written
        return (f"Bash denied (read-only profile): output redirection to "
                f"`{target}` writes a file. Redirection to /dev/null is fine.")

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


def make_readonly_guard_hooks(job_id: str) -> dict[str, list[HookMatcher]]:
    """PreToolUse guard hooks for a read-only (oversight) session — the
    structural enforcement of `privilege_class: read-only`.

    The guarantee, stated honestly:
      - File-mutation TOOLS (Write/Edit/MultiEdit/NotebookEdit) and the
        projects-MCP `restart_project` tool are structurally denied — no
        path or argument makes them legal.
      - Bash is a best-effort mutation DENYLIST (redirection, file/git/
        service/migration/package mutators, non-SELECT psql). That is
        defense-in-depth, not a sandbox: an interpreter one-liner
        (`python -c "..."`) can still mutate state. The OS-level closure is
        the SDK Seatbelt sandbox tracked in SYSTEM.md § known debt.
      - The dispatch MCP tool (`enqueue_job`) is deliberately NOT matched:
        enqueueing gated worker jobs is this tier's one sanctioned way to
        cause change.

    Applies in EVERY isolation tier and permission mode — a belt under
    `plan`, load-bearing under `acceptEdits` (dispatch-capable oversight
    skills must run acceptEdits because plan blocks MCP tools; proven live
    2026-07-30). Hooks fire in the runner process before permission
    evaluation, so a session cannot prompt its way past them. Denials are
    audited as `guard_denied` with profile="read-only".
    """

    async def _guard_file(input_data: dict, tool_use_id: str | None, context: Any) -> dict:
        tool = input_data.get("tool_name", "")
        reason = readonly_file_violation(tool)
        if reason:
            audit_log.append(job_id, "guard_denied", tool_name=tool,
                             reason=reason, profile="read-only")
            logger.warning("read-only guard denied %s for job %s: %s",
                           tool, job_id[:8], reason)
            return _deny(reason)
        return {}

    async def _guard_bash(input_data: dict, tool_use_id: str | None, context: Any) -> dict:
        command = (input_data.get("tool_input") or {}).get("command", "")
        reason = readonly_bash_violation(command)
        if reason:
            audit_log.append(job_id, "guard_denied", tool_name="Bash",
                             reason=reason, command=command[:300],
                             profile="read-only")
            logger.warning("read-only guard denied Bash for job %s: %s",
                           job_id[:8], reason)
            return _deny(reason)
        return {}

    async def _guard_restart(input_data: dict, tool_use_id: str | None, context: Any) -> dict:
        tool = input_data.get("tool_name", "")
        if tool.endswith(RESTART_TOOL_SUFFIX):
            reason = (f"{tool} is denied (read-only profile): a service "
                      f"restart is a mutation. Recommend it in your report or "
                      f"dispatch a gated worker via enqueue_job.")
            audit_log.append(job_id, "guard_denied", tool_name=tool,
                             reason=reason, profile="read-only")
            logger.warning("read-only guard denied %s for job %s",
                           tool, job_id[:8])
            return _deny(reason)
        return {}

    return {
        "PreToolUse": [
            HookMatcher(matcher="|".join(FILE_WRITE_TOOLS), hooks=[_guard_file]),
            HookMatcher(matcher="Bash", hooks=[_guard_bash]),
            # Suffix-matched (regex) so the deny holds however the MCP server
            # name prefixes the tool (`mcp__projects__restart_project`); the
            # hook re-checks the suffix so a broader-than-intended matcher
            # can never deny an unrelated tool.
            HookMatcher(matcher=f".*{RESTART_TOOL_SUFFIX}", hooks=[_guard_restart]),
        ]
    }
