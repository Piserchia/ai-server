"""
Code-review sub-agent. Runs synchronously after code-touching sessions to evaluate
the diff. Returns a ReviewOutcome that drives the parent job's final status.

Called from main.py:_maybe_review(). Also usable standalone via the code-review skill.
"""

from __future__ import annotations

import enum
import logging
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

logger = logging.getLogger(__name__)

MAX_DIFF_CHARS = 50_000


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


async def run_code_review(
    parent_job_id: str,
    diff: str,
    cwd: Path,
) -> ReviewOutcome:
    """
    Run a code-review sub-agent on the given diff. Returns ReviewOutcome.
    Logs events to the parent job's audit log.

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
        model="claude-opus-4-7",
        effort="high",
        permission_mode="plan",  # read-only
        allowed_tools=["Read", "Glob", "Grep"],
        max_turns=6,
        output_format=REVIEW_OUTPUT_FORMAT,
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
        # that does not gate the job, so an SDK hiccup would let an unreviewed
        # diff ship (INV-13). Return `error`, which the caller gates like a
        # blocker (→ awaiting_user for a human look).
        logger.warning("code review could not run: %s (gating as error)", exc)
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
