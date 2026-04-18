"""
Learning extractor hook. Runs after successful non-chat, non-internal jobs.

Pipeline:
1. `should_extract(audit_entries)` (pure function): only run the classifier if
   the job actually modified files (tool_use: Write or Edit events present).
   Chat/read-only jobs skip extraction entirely, saving Haiku tokens.
2. `extract_learning(parent_job, audit_entries, summary)`: one-turn Haiku call
   that returns a LearningProposal. JSON-structured output. Returns
   had_learning=False when no learning was found.
3. `maybe_extract_and_enqueue(...)`: the full pipeline entry point called from
   the runner. On a positive classification, enqueues a `_learning_apply`
   internal child job that appends the learning to the right file.

Module/category selection:
- Classifier chooses from installed modules + explicit "project" / "none"
- Categories: GOTCHA (trap), PATTERN (right-way), DEBUG (diagnostic)
- Paths resolve to `.context/modules/<module>/skills/<CATEGORY>.md`

Token hygiene: target runtime < 5 seconds per job, < 2K tokens per call.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    TextBlock,
)

from src import audit_log
from src.config import settings

logger = logging.getLogger(__name__)


# Categories the classifier may assign to a learning
VALID_CATEGORIES = ("GOTCHA", "PATTERN", "DEBUG")


@dataclass
class LearningProposal:
    had_learning: bool
    module: str = ""          # e.g., "runner", "gateway", "db", "registry", "hosting", "project", "none"
    category: str = ""        # GOTCHA | PATTERN | DEBUG
    title: str = ""           # <=~80 chars
    content: str = ""         # markdown body, 2-6 sentences
    evidence_job_id: str = ""


# ── Pure helpers (unit-tested) ─────────────────────────────────────────────


def should_extract(audit_entries: list[dict]) -> bool:
    """Return True iff the job modified files (indicated by Write or Edit tool use).

    Pure function: no IO, takes a list of already-loaded audit entries.
    """
    for entry in audit_entries:
        if entry.get("kind") != "tool_use":
            continue
        tool_name = entry.get("tool_name", "")
        if tool_name in ("Write", "Edit"):
            return True
    return False


def list_installed_modules(modules_dir: Path) -> list[str]:
    """Return sorted list of module names that exist in .context/modules/.
    Pure function modulo filesystem state."""
    if not modules_dir.exists():
        return []
    out = []
    for child in sorted(modules_dir.iterdir()):
        if child.is_dir() and (child / "CONTEXT.md").exists():
            out.append(child.name)
    return out


def parse_learning_response(text: str) -> LearningProposal:
    """Parse the Haiku classifier's JSON response. Tolerant of surrounding text
    and markdown fences. Returns a no-learning proposal if parsing fails."""
    if not text or not text.strip():
        return LearningProposal(had_learning=False)

    stripped = text.strip()
    # Extract the first balanced JSON object — handles markdown fences,
    # preamble, postamble.
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start < 0 or end < 0 or end < start:
        return LearningProposal(had_learning=False)
    candidate = stripped[start:end + 1]

    try:
        obj = json.loads(candidate)
    except json.JSONDecodeError:
        return LearningProposal(had_learning=False)

    if not obj.get("had_learning"):
        return LearningProposal(had_learning=False)

    category = str(obj.get("category", "")).strip().upper()
    if category not in VALID_CATEGORIES:
        return LearningProposal(had_learning=False)

    module = str(obj.get("module", "")).strip()
    title = (str(obj.get("title") or "")).strip()[:200]
    content = (str(obj.get("content") or "")).strip()

    # Minimum content bar: both title and content must be non-empty.
    if not title or not content:
        return LearningProposal(had_learning=False)

    return LearningProposal(
        had_learning=True,
        module=module,
        category=category,
        title=title,
        content=content,
        evidence_job_id=str(obj.get("evidence_job_id", "")),
    )


def format_audit_excerpt(audit_entries: list[dict], max_entries: int = 40) -> str:
    """Compact, human-readable summary of the audit log for the classifier prompt.
    Skips raw tool results; keeps kind/tool_name/short input summary."""
    lines: list[str] = []
    for entry in audit_entries[-max_entries:]:
        kind = entry.get("kind", "?")
        if kind == "tool_use":
            tool = entry.get("tool_name", "?")
            inp = entry.get("input", {})
            path = ""
            if isinstance(inp, dict):
                path = inp.get("file_path") or inp.get("path") or ""
                if not path and "command" in inp:
                    cmd = str(inp["command"])[:80]
                    path = f"cmd={cmd!r}"
            lines.append(f"[tool_use] {tool} {path}"[:200])
        elif kind == "tool_result":
            is_err = entry.get("is_error")
            lines.append(f"[tool_result] error={bool(is_err)}"[:120])
        elif kind == "text":
            txt = (entry.get("text") or "")[:160].replace("\n", " ")
            lines.append(f"[text] {txt}")
        elif kind == "thinking":
            txt = (entry.get("text") or "")[:120].replace("\n", " ")
            lines.append(f"[thinking] {txt}")
        elif kind == "job_failed":
            err = (entry.get("error") or "")[:200]
            lines.append(f"[job_failed] {err}")
    return "\n".join(lines) if lines else "(empty audit log)"


# ── Classifier prompt ───────────────────────────────────────────────────────


CLASSIFIER_SYSTEM_PROMPT = """\
You are a documentation learning extractor for the ai-server repo.

You will be shown a compact audit log of a single job that modified files, plus
the job's final summary. Your task: decide whether the job revealed a reusable
**learning** that should be appended to the repo's institutional-knowledge
files (`.context/modules/<module>/skills/GOTCHAS.md` / `PATTERNS.md` / `DEBUG.md`).

Most jobs do NOT produce a new learning. Be strict. Only say `had_learning: true`
when ALL of these hold:
- The finding is non-obvious (not "restart the service" or "fix the typo")
- The finding is reusable (applies to future work, not one-off)
- The finding fits one of the three categories below

Categories:
- **GOTCHA**: A trap. Something that looks like it should work but doesn't.
  Implicit orderings, env-specific behavior, race conditions, misleading errors.
- **PATTERN**: A correct, reusable approach for extending or working within a
  module that isn't obvious from the code alone.
- **DEBUG**: A fast path for diagnosing a failure — a useful log location, a
  specific grep, an error whose real meaning differs from its text.

Module selection: match the finding to ONE of the installed modules the caller
lists in the prompt. If the finding belongs to a project (not the server code),
use `project`. If the finding is scoped to just one skill, still pick the
most-related module (often `runner` for skill infrastructure, `registry` for
skill loading, etc.). If you can't confidently pick, return had_learning=false.

**Output format**: a single JSON object, nothing else. No markdown fences. No
preamble. No postamble. Example of a positive case:

{
  "had_learning": true,
  "module": "runner",
  "category": "GOTCHA",
  "title": "MCP tool args are a dict, not kwargs",
  "content": "When defining @tool functions for create_sdk_mcp_server, the wrapped function receives a single `args: dict` parameter, not keyword arguments. Calling it with `tool(name, description)` and writing `async def f(slug: str)` silently fails.\\n\\nFix: write `async def f(args: dict) -> dict` and access fields via `args[\\"slug\\"]`.",
  "evidence_job_id": "abc12345"
}

Negative case (most jobs):
{"had_learning": false}
"""


async def extract_learning(
    parent_job_id: str,
    audit_entries: list[dict],
    summary: str,
    module_list: list[str],
) -> LearningProposal:
    """Run the Haiku classifier. Returns a proposal (possibly had_learning=False).

    Never raises — on any SDK error, returns had_learning=False.
    """
    excerpt = format_audit_excerpt(audit_entries)
    modules_str = ", ".join(module_list) if module_list else "(none)"

    user_prompt = (
        f"Job id: {parent_job_id[:8]}\n"
        f"Installed modules: {modules_str}\n\n"
        f"Final summary:\n{summary[:1500]}\n\n"
        f"Audit log excerpt:\n{excerpt}\n\n"
        f"Emit the JSON object now."
    )

    options = ClaudeAgentOptions(
        cwd=str(settings.server_root),
        system_prompt=CLASSIFIER_SYSTEM_PROMPT,
        model="claude-haiku-4-5-20251001",
        effort="low",
        permission_mode="plan",  # read-only; classifier does not need to act
        allowed_tools=[],
        max_turns=1,
    )

    final_text = ""
    try:
        client = ClaudeSDKClient(options=options)
        async with client:
            await client.query(user_prompt)
            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            final_text += block.text
    except Exception as exc:
        logger.warning("learning extractor SDK error: %s", exc)
        return LearningProposal(had_learning=False)

    proposal = parse_learning_response(final_text)

    if proposal.had_learning:
        # Validate module is in the allowed list (plus 'project' / 'none')
        valid_modules = set(module_list) | {"project", "none"}
        if proposal.module not in valid_modules:
            logger.info(
                "discarding learning with invalid module: %s", proposal.module,
            )
            return LearningProposal(had_learning=False)
        if proposal.module == "none":
            return LearningProposal(had_learning=False)

    # Ensure evidence job id is set
    if proposal.had_learning and not proposal.evidence_job_id:
        proposal.evidence_job_id = parent_job_id[:8]

    return proposal


# ── Entry point called from runner ──────────────────────────────────────────


async def maybe_extract_and_enqueue(
    parent_job_id: str,
    summary: str,
) -> bool:
    """Full pipeline: read audit log, decide should-extract, classify, enqueue
    apply job if a learning was found.

    Returns True if an apply job was enqueued, False otherwise.
    Never raises; logs and swallows errors.
    """
    try:
        audit_entries = audit_log.read(parent_job_id)
    except Exception as exc:
        logger.warning("could not read audit log for %s: %s", parent_job_id, exc)
        return False

    if not should_extract(audit_entries):
        return False

    modules_dir = settings.server_root / ".context" / "modules"
    module_list = list_installed_modules(modules_dir)

    proposal = await extract_learning(
        parent_job_id, audit_entries, summary, module_list,
    )

    audit_log.append(
        parent_job_id,
        "learning_extraction_done",
        had_learning=proposal.had_learning,
        module=proposal.module,
        category=proposal.category,
        title=proposal.title[:120],
    )

    if not proposal.had_learning:
        return False

    # Enqueue _learning_apply child job (deferred imports to avoid cycles)
    from src.gateway.jobs import enqueue_job
    from sqlalchemy import update
    from src.db import session_scope
    from src.models import Job

    description = (
        f"Apply learning from parent job {parent_job_id[:8]}: "
        f"[{proposal.category}] {proposal.title}"
    )
    payload = {
        "module": proposal.module,
        "category": proposal.category,
        "title": proposal.title,
        "content": proposal.content,
        "evidence_job_id": proposal.evidence_job_id or parent_job_id[:8],
        "parent_job_id": parent_job_id,
    }
    try:
        child = await enqueue_job(
            description,
            kind="_learning_apply",
            payload=payload,
            created_by=f"learning:{parent_job_id[:8]}",
        )
    except Exception as exc:
        logger.warning("failed to enqueue learning_apply job: %s", exc)
        return False

    # Link child → parent
    try:
        import uuid as _uuid
        async with session_scope() as s:
            await s.execute(
                update(Job).where(Job.id == child.id).values(
                    parent_job_id=_uuid.UUID(parent_job_id),
                )
            )
    except Exception:
        logger.exception("failed to link learning_apply child to parent")

    audit_log.append(
        parent_job_id,
        "learning_apply_enqueued",
        child_job_id=str(child.id),
        module=proposal.module,
        category=proposal.category,
    )
    logger.info(
        "learning extracted: parent=%s child=%s module=%s category=%s",
        parent_job_id[:8], str(child.id)[:8],
        proposal.module, proposal.category,
    )
    return True
