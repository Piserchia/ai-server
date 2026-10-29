"""
Code-review sub-agent. Runs synchronously after code-touching sessions to evaluate
the diff. Returns a ReviewOutcome that drives the parent job's final status.

Called from main.py:_maybe_review(). Also usable standalone via the code-review skill.
"""

from __future__ import annotations

import enum
import logging
import re
import subprocess
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    query,
)

from src import audit_log
from src.config import settings
from src.runner.claude_env import claude_subprocess_env

logger = logging.getLogger(__name__)

MAX_DIFF_CHARS = 50_000

# The reviewer is FIXED here (never chosen by the reviewed skill). The
# pre-push gate (T5, 2026-10-21) names it in the `Reviewed-By:` trailer of
# the commit it approves, so the constant and `run_code_review` must agree.
REVIEWER_PROVIDER = "anthropic"
REVIEWER_MODEL = "claude-opus-4-7"
REVIEWER_EFFORT = "high"

# Pre-push gate ceiling (plan T5; old spec §5.3 belt 3b). A timeout is a
# `changes_requested` verdict, not a skip — the gate fails closed.
GATE_TIMEOUT_SECONDS = 600


class ReviewOutcome(enum.Enum):
    lgtm = "LGTM"
    changes_requested = "changes_requested"
    blocker = "blocker"
    error = "error"   # the review could NOT run — gate like a blocker (fail closed, INV-13)


REVIEW_SYSTEM_PROMPT = """\
You are a code reviewer for a personal assistant server. You are reviewing a diff
produced by an automated coding session. Your job is to evaluate the quality,
correctness, and safety of the changes AND the approach used to arrive at them.

Evaluate the diff for:
1. **Correctness**: Does the code do what it's supposed to? Any logic errors?
2. **Security**: Any hardcoded secrets, injection vulnerabilities, or unsafe patterns?
3. **Style**: Does it follow the existing codebase patterns?
4. **Completeness**: Are there missing error handlers, untested edge cases, or TODOs?

Deliver your verdict through the structured output schema:

- `verdict`: exactly one of
  - `LGTM` — the changes look good, no blocking issues
  - `CHANGES` — minor issues that should be fixed but aren't blocking
  - `BLOCKER` — serious issues (security, data loss, broken functionality) that must be fixed
- `review`: your assessment of the code changes. Be specific — reference file
  names and line numbers when pointing out issues.
- `approach`: if a tool-use summary was provided, comment on the session's
  methodology. Did it read enough context before writing? Did it grep before
  editing? Did it test after changing? Note any process concerns (e.g., "wrote
  3 files without reading any first"). Empty string if no summary was provided.
"""

# Enforced via ClaudeAgentOptions(output_format=...) — the SDK retries until
# the final output validates, so the verdict can't get lost in prose.
REVIEW_OUTPUT_FORMAT: dict = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "verdict": {"type": "string", "enum": ["LGTM", "CHANGES", "BLOCKER"]},
            "review": {"type": "string"},
            "approach": {"type": "string"},
        },
        "required": ["verdict", "review"],
        "additionalProperties": False,
    },
}


def outcome_from_structured(obj: Any) -> ReviewOutcome | None:
    """Map a structured-output object to a ReviewOutcome. Pure function.
    None = not usable (caller falls back to text parsing)."""
    if not isinstance(obj, dict):
        return None
    verdict = str(obj.get("verdict", "")).strip().upper()
    if verdict == "LGTM":
        return ReviewOutcome.lgtm
    if verdict == "BLOCKER":
        return ReviewOutcome.blocker
    if verdict == "CHANGES":
        return ReviewOutcome.changes_requested
    return None


def format_structured_review(obj: dict) -> str:
    """Human-readable rendering for the audit log. Pure function."""
    parts = [str(obj.get("verdict", "")).strip().upper()]
    if obj.get("review"):
        parts.append(f"Review: {obj['review']}")
    if obj.get("approach"):
        parts.append(f"Approach: {obj['approach']}")
    return "\n\n".join(p for p in parts if p)


def _summarize_tool_usage(parent_job_id: str, max_lines: int = 30) -> str:
    """Summarize the parent job's tool usage from its audit log.

    Returns a compact summary like:
      Read: 8 files (models.py, session.py, ...)
      Grep: 3 searches
      Edit: 5 edits
      Bash: 2 commands
    """
    events = audit_log.read(parent_job_id)
    if not events:
        return ""

    tool_counts: dict[str, int] = {}
    read_files: list[str] = []

    for evt in events:
        if evt.get("kind") != "tool_use":
            continue
        tool = evt.get("tool_name", "")
        tool_counts[tool] = tool_counts.get(tool, 0) + 1
        if tool == "Read":
            fp = (evt.get("input") or {}).get("file_path", "")
            if fp:
                # Just the filename for brevity
                read_files.append(fp.rsplit("/", 1)[-1])

    if not tool_counts:
        return ""

    lines = ["Tool usage summary from the coding session:"]
    for tool in sorted(tool_counts, key=lambda t: -tool_counts[t]):
        count = tool_counts[tool]
        extra = ""
        if tool == "Read" and read_files:
            shown = read_files[:8]
            extra = f" ({', '.join(shown)}{'...' if len(read_files) > 8 else ''})"
        lines.append(f"  {tool}: {count}{extra}")

    return "\n".join(lines[:max_lines])


def _parse_outcome(text: str) -> ReviewOutcome:
    """Parse the reviewer's first line into a ReviewOutcome."""
    if not text or not text.strip():
        return ReviewOutcome.changes_requested

    first_line = text.strip().split("\n")[0].strip().upper()

    if first_line.startswith("LGTM"):
        return ReviewOutcome.lgtm
    if first_line.startswith("BLOCKER"):
        return ReviewOutcome.blocker
    if first_line.startswith("CHANGES"):
        return ReviewOutcome.changes_requested

    # Fallback: unknown format → conservative default
    return ReviewOutcome.changes_requested


def get_git_diff(cwd: Path, ref: str = "HEAD~1") -> str:
    """Get git diff output from a directory. Returns empty string on any error."""
    try:
        result = subprocess.run(
            ["git", "diff", ref],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.stdout or ""
    except Exception:
        return ""


#: `git -c …` pins for every gate read of an UNTRUSTED clone (whole-branch
#: review, 2026-10-21). Mirrors `workspaces.UNTRUSTED_GIT_OPTS` for the
#: hook/fsmonitor part (kept separate so `review` does not import
#: `workspaces`); `core.quotePath=false` is the gate's own need.
GATE_GIT_OPTS: tuple[str, ...] = (
    "-c", "core.quotePath=false",
    "-c", "core.fsmonitor=false",
    "-c", "core.hooksPath=/dev/null",
)
#: Flags on every `git diff` the gate runs: attributes in the clone cannot
#: hide content (`--text`), substitute a driver (`--no-ext-diff`) or run a
#: converter over it (`--no-textconv` — `diff.<drv>.textconv` is honoured
#: even under `--no-ext-diff`, and an empty converter leaves the reviewer a
#: file with no content lines; final review, 2026-10-21). Git honours all
#: three on both `diff <base>` and `diff --no-index`.
GATE_DIFF_FLAGS: tuple[str, ...] = ("--no-color", "--text", "--no-ext-diff", "--no-textconv")


def diff_for_gate(cwd: Path, base_sha: str | None) -> str:
    """Everything a workspace job changed since `base_sha` — committed,
    staged, unstaged and untracked (gitignored files excluded) — as one
    unified diff for the pre-push review gate (T5, 2026-10-21; plan §4b:
    "if the job committed on its own, the diff is `git diff <base>` plus
    the index and working tree").

    `git diff <base>` compares the WORKING TREE to the base commit, which
    covers the job's own commits, its index and its unstaged edits in one
    pass; untracked files are appended via `git diff --no-index` against
    /dev/null so a brand-new file is reviewed too.

    Fails CLOSED: any git failure (not a repo, unknown base, missing base)
    raises RuntimeError rather than returning "" — an empty string means
    "nothing to review, complete the job", and a broken diff must never
    read as that.

    The clone is UNTRUSTED (whole-branch review, 2026-10-21): the job wrote
    it, so nothing in its working tree or `.git/config` may shape what the
    reviewer sees or run code under the runner — `--text` (a nested
    `.gitattributes` with `* -diff` would otherwise render every file as
    `Binary files … differ`), `--no-ext-diff` (no `diff=<driver>` /
    `diff.external` command), `--no-textconv` (no `diff.<driver>.textconv`
    converter — it runs and can empty the hunk even with `--no-ext-diff`),
    `core.quotePath=false` (non-ASCII paths print
    raw so the deny list sees them; tabs/quotes/newlines stay quoted and
    `gate_unparseable_headers` refuses those), `core.fsmonitor=false` and
    `core.hooksPath=/dev/null` (no config-driven command execution).
    """
    if not base_sha:
        raise RuntimeError("pre-push gate: no base commit recorded for the clone")

    def _run(args: list[str], ok_codes=(0,)) -> subprocess.CompletedProcess:
        try:
            res = subprocess.run(["git", *GATE_GIT_OPTS, *args], cwd=str(cwd),
                                 capture_output=True, text=True, timeout=60)
        except Exception as exc:  # noqa: BLE001 — surfaced as a gate failure
            raise RuntimeError(f"pre-push gate: git {args[0]} failed: {exc}") from exc
        if res.returncode not in ok_codes:
            raise RuntimeError(
                f"pre-push gate: git {' '.join(args[:2])} exited {res.returncode}: "
                f"{res.stderr.strip()[:300]}")
        return res

    tracked = _run(["diff", *GATE_DIFF_FLAGS, base_sha, "--"]).stdout or ""
    untracked = _run(["ls-files", "--others", "--exclude-standard", "-z"]).stdout
    parts = [tracked] if tracked else []
    for name in [n for n in untracked.split("\0") if n]:
        # `--no-index` exits 1 when the files differ (always, vs /dev/null).
        res = _run(["diff", *GATE_DIFF_FLAGS, "--no-index", "--", "/dev/null", name],
                   ok_codes=(0, 1))
        if res.stdout:
            parts.append(res.stdout)
    return "".join(parts)


_FINDING_LINE = re.compile(r"^\s*(?:[-*\u2022]|\d+[.)])\s+\S")


def count_findings(review_text: str | None) -> int:
    """How many list items the reviewer's text carries — a heuristic
    (bullets `-`/`*`/`•` and `1.`/`1)` items), recorded on
    `merge_gate_verdict.findings_n` for the scoreboard. Pure. A verdict
    with prose only counts 0; this is a signal, not a contract."""
    if not review_text:
        return 0
    return sum(1 for line in review_text.splitlines() if _FINDING_LINE.match(line))


#: Repo-root-relative paths a non-Anthropic job's diff may NEVER carry
#: through the pre-push gate (T5 review round 1, 2026-10-21) — a minimal
#: hardcoded deny list standing in for the old spec's per-target
#: `publish_allowlist` (§5.3 belt 3b: deny is evaluated first and wins;
#: a rename counts as both paths), applied BEFORE a reviewer session is
#: spent. Everything here is read as *instructions or executable config*
#: by some agent that later opens the checkout: Claude Code's settings
#: (hooks run as the owner), Codex's `.codex/` + `AGENTS.md`, `CLAUDE.md`
#: (loaded by every Anthropic session on the project), git hook/config
#: paths and CI workflows. The per-target allowlist stays T8/owner work.
GATE_DENIED_DIRS: tuple[str, ...] = (
    ".claude", ".codex", ".git", ".githooks", ".github",
)
GATE_DENIED_FILES: tuple[str, ...] = (
    ".gitmodules", ".gitattributes", ".gitconfig", ".mcp.json",
)
# `.gitattributes` at ANY depth (whole-branch review, 2026-10-21): a nested
# one applies to its subtree and is read by every later git in the checkout
# (diff drivers, filters, `-diff`), not only at the root.
GATE_DENIED_BASENAMES: tuple[str, ...] = ("AGENTS.md", "CLAUDE.md", ".gitattributes")
# Matching is CASE-INSENSITIVE (final review, 2026-10-21): the canonical and
# the agents that open it live on case-insensitive APFS, so a job-written
# `.CLAUDE/settings.json` or `agents.md` IS the file Claude Code / Codex /
# git later read as `.claude/settings.json` / `AGENTS.md`. Fail closed — a
# false positive on a case-sensitive host only costs a refusal.
_GATE_DENIED_DIRS_CF = frozenset(d.casefold() for d in GATE_DENIED_DIRS)
_GATE_DENIED_FILES_CF = frozenset(f.casefold() for f in GATE_DENIED_FILES)
_GATE_DENIED_BASENAMES_CF = frozenset(b.casefold() for b in GATE_DENIED_BASENAMES)

_DIFF_PATH_LINE = re.compile(
    r"^(?:\+\+\+ b/|--- a/|rename (?:from|to) |copy (?:from|to) )(?P<path>.+?)\s*$")
_DIFF_GIT_LINE = re.compile(r"^diff --git a/(?P<a>.+) b/(?P<b>.+)$")


def gate_diff_paths(diff: str) -> list[str]:
    """Every repo-relative path a unified diff names (both sides of a
    rename/copy, the `+++`/`---` headers and the `diff --git` line), in
    order of first appearance. Pure. `/dev/null` sides are ignored."""
    seen: list[str] = []

    def add(p: str) -> None:
        p = p.strip().strip('"')
        if not p or p == "/dev/null" or p.startswith("/dev/null"):
            return
        if p not in seen:
            seen.append(p)

    for line in diff.splitlines():
        m = _DIFF_GIT_LINE.match(line)
        if m:
            add(m.group("a"))
            add(m.group("b"))
            continue
        m = _DIFF_PATH_LINE.match(line)
        if m:
            add(m.group("path"))
    return seen


def gate_path_denied(path: str) -> bool:
    """True when `path` (repo-root-relative, POSIX) hits the deny list,
    compared case-insensitively (`str.casefold`). Pure."""
    norm = path.strip()
    while norm.startswith("./"):
        norm = norm[2:]
    parts = [p for p in norm.split("/") if p and p != "."]
    if not parts:
        return False
    top = parts[0].casefold()
    if top in _GATE_DENIED_DIRS_CF:
        return True          # anything under it, or the entry itself
    if len(parts) == 1 and top in _GATE_DENIED_FILES_CF:
        return True
    if parts[-1].casefold() in _GATE_DENIED_BASENAMES_CF:
        return True
    return False


def gate_path_denials(diff: str) -> list[str]:
    """The denied paths a gate diff touches (empty = clean). Pure; the
    session refuses the diff before `run_code_review` when non-empty."""
    return [p for p in gate_diff_paths(diff) if gate_path_denied(p)]


_HEADER_PREFIXES = ("--- ", "+++ ", "rename from ", "rename to ", "copy from ", "copy to ")


def gate_unparseable_headers(diff: str) -> list[str]:
    """Header lines of a unified diff that name a path the gate parser
    CANNOT read (whole-branch review, 2026-10-21) — git-quoted paths
    (`diff --git "a/…" "b/…"`, `+++ "b/…"`: tabs, quotes, control bytes,
    or non-ASCII when `core.quotePath` is on) and any `diff --git` line the
    strict regex rejects. Pure. The gate treats a non-empty result as a
    refusal (`merge_gate_refused reason=unparseable_path`): a path the
    deny list never saw must not reach a push. Only lines in a file's
    HEADER (from `diff --git` to the first `@@`) are examined for the
    `---`/`+++`/`rename`/`copy` forms, because hunk CONTENT may begin
    with `--- "` (a removed `-- "x"` line) legitimately."""
    bad: list[str] = []
    in_header = False
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            in_header = True
            if not _DIFF_GIT_LINE.match(line):
                bad.append(line)
            continue
        if line.startswith("@@") or line.startswith("Binary files "):
            in_header = False
            continue
        if not in_header:
            continue
        if line.startswith(_HEADER_PREFIXES):
            rest = line.split(" ", 1)[1] if line.startswith(("--- ", "+++ ")) \
                else line.split(" ", 2)[2]
            if rest.startswith("/dev/null"):
                continue
            if rest.startswith('"') or not _DIFF_PATH_LINE.match(line):
                bad.append(line)
    return bad


def gate_refusal(diff: str) -> tuple[str, list[str]] | None:
    """Why the gate must refuse `diff` BEFORE a reviewer is spent, or None:
    `("denied_path", paths)` (deny wins, evaluated first) or
    `("unparseable_path", header_lines)`. Pure; one call shared by
    `session._pre_push_gate` and the canary's `gate_dry_run`. The size
    rule (`MAX_DIFF_CHARS`) is the caller's — it needs the audit fields."""
    denied = gate_path_denials(diff)
    if denied:
        return "denied_path", denied
    unparseable = gate_unparseable_headers(diff)
    if unparseable:
        return "unparseable_path", unparseable
    return None


def head_commit_epoch(cwd: Path) -> int | None:
    """Committer epoch of HEAD in `cwd`, or None (not a repo / no commits)."""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%ct"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return None
        out = result.stdout.strip()
        return int(out) if out else None
    except Exception:
        return None


def is_stale_head(head_epoch: int | None, job_started_epoch: float | None,
                  slack_seconds: int = 120) -> bool:
    """True when the checkout's HEAD predates the job's start: nothing this
    job produced is at HEAD (the workspace's canonical ff-sync failed, or the
    session never committed), so a HEAD~1 review would grade someone else's
    commit and stamp review_outcome on the wrong diff (INV-13 wrong-diff
    guard). Unknown epochs fail open — the diff-empty check still applies."""
    if head_epoch is None or job_started_epoch is None:
        return False
    return head_epoch < (job_started_epoch - slack_seconds)


async def run_code_review(
    parent_job_id: str,
    diff: str,
    cwd: Path,
) -> ReviewOutcome:
    """
    Run a code-review sub-agent on the given diff. Returns ReviewOutcome.
    Logs events to the parent job's audit log.

    The reviewer model/effort are FIXED here (opus-4-7/high), deliberately
    not taken from the reviewed skill's own frontmatter — a skill must not be
    able to choose, let alone downgrade, the reviewer that grades its diffs.

    This is synchronous in the sense that the caller awaits the result —
    the parent job's final status depends on it.
    """
    audit_log.append(parent_job_id, "code_review_started", diff_chars=len(diff))

    # Truncate large diffs
    truncated = False
    if len(diff) > MAX_DIFF_CHARS:
        diff = diff[:MAX_DIFF_CHARS]
        truncated = True

    prompt = f"Review this diff:\n\n```diff\n{diff}\n```"
    if truncated:
        prompt += (
            f"\n\n(NOTE: This diff was truncated at {MAX_DIFF_CHARS} characters. "
            "You are seeing a partial diff.)"
        )

    # Append tool-use summary for approach critique (Rec 15)
    tool_summary = _summarize_tool_usage(parent_job_id)
    if tool_summary:
        prompt += f"\n\n{tool_summary}"

    options = ClaudeAgentOptions(
        cwd=str(cwd),
        system_prompt=REVIEW_SYSTEM_PROMPT,
        model=REVIEWER_MODEL,
        effort=REVIEWER_EFFORT,
        permission_mode="plan",  # read-only
        allowed_tools=["Read", "Glob", "Grep"],
        max_turns=6,
        output_format=REVIEW_OUTPUT_FORMAT,
        # SDK isolation mode (T5 review round 1, 2026-10-21): `None` would
        # load the reviewed checkout's `.claude/settings.json`,
        # `.claude/settings.local.json` and `CLAUDE.md` — a `hooks` block
        # planted there by the job under review (a Codex clone under
        # `workspace-write` can write exactly those files) would run as the
        # owner, in the runner's unscrubbed env, before the reviewer read a
        # line of the diff. The reviewer needs none of them: the prompt
        # carries the diff and the system prompt carries the instructions.
        setting_sources=[],
        env=claude_subprocess_env(),          # E7: telemetry off on every subprocess
    )

    final_text = ""
    structured: Any = None
    try:
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        final_text += block.text
            elif isinstance(message, ResultMessage):
                structured = message.structured_output

        outcome = outcome_from_structured(structured)
        if outcome is not None:
            final_text = format_structured_review(structured)
        else:
            # Structured output missing/malformed — fall back to text parsing
            # (conservative default inside _parse_outcome).
            logger.warning("review returned no usable structured output — "
                           "falling back to text verdict")
            outcome = _parse_outcome(final_text)

    except Exception as exc:
        # The review could not run. Do NOT fall through to changes_requested —
        # that reads as a benign verdict. Return `error`, which the flag-only
        # caller records + surfaces loudly (post_review_flagged) rather than
        # letting an unreviewable diff pass silently (INV-13).
        logger.warning("code review could not run: %s (recording as error)", exc)
        final_text = f"Review could not run: {exc}"
        outcome = ReviewOutcome.error

    audit_log.append(
        parent_job_id,
        "code_review_done",
        outcome=outcome.value,
        review_text=final_text[:2000],
    )

    logger.info(
        "code review complete for %s: %s", parent_job_id[:8], outcome.value
    )

    return outcome
