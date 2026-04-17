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

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

from src import audit_log
from src.config import settings

logger = logging.getLogger(__name__)

MAX_DIFF_CHARS = 50_000


class ReviewOutcome(enum.Enum):
    lgtm = "LGTM"
    changes_requested = "changes_requested"
    blocker = "blocker"


REVIEW_SYSTEM_PROMPT = """\
You are a code reviewer for a personal assistant server. You are reviewing a diff
produced by an automated coding session. Your job is to evaluate the quality,
correctness, and safety of the changes.

Evaluate the diff for:
1. **Correctness**: Does the code do what it's supposed to? Any logic errors?
2. **Security**: Any hardcoded secrets, injection vulnerabilities, or unsafe patterns?
3. **Style**: Does it follow the existing codebase patterns?
4. **Completeness**: Are there missing error handlers, untested edge cases, or TODOs?

Your response MUST start with exactly one of these words on the first line:
- `LGTM` — the changes look good, no blocking issues
- `CHANGES` — minor issues that should be fixed but aren't blocking
- `BLOCKER` — serious issues (security, data loss, broken functionality) that must be fixed

After the verdict line, explain your reasoning. Be specific — reference file names and
line numbers when pointing out issues.
"""


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

    options = ClaudeAgentOptions(
        cwd=str(cwd),
        system_prompt=REVIEW_SYSTEM_PROMPT,
        model="claude-opus-4-7",
        effort="high",
        permission_mode="plan",  # read-only
        allowed_tools=["Read", "Glob", "Grep"],
        max_turns=3,
    )

    try:
        client = ClaudeSDKClient(options=options)
        final_text = ""

        async for message in client.process_message(prompt):
            from claude_agent_sdk import AssistantMessage, TextBlock
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        final_text += block.text

        outcome = _parse_outcome(final_text)

    except Exception as exc:
        logger.warning("code review failed: %s (defaulting to changes_requested)", exc)
        final_text = f"Review failed: {exc}"
        outcome = ReviewOutcome.changes_requested

    audit_log.append(
        parent_job_id,
        "code_review_done",
        outcome=outcome.value,
        review_text=final_text[:2000],
    )

    logger.info(
        "code review complete",
        parent_job=parent_job_id[:8],
        outcome=outcome.value,
    )

    return outcome
