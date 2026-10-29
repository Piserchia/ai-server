"""
One function: `run_session(job)`. Resolves the skill + isolation tier, prepares a
per-job workspace when the tier calls for one, then runs an in-process Agent SDK
session, streaming output to audit log + Redis. Returns a result dict or raises
QuotaExhausted.

Auth: subscription via the Claude Code CLI bundled inside the SDK package. The
bootstrap script unsets ANTHROPIC_API_KEY before starting any process, so the
SDK uses the stored credentials from `claude login`. There is no API-key path
anywhere (INV-3).

Skill-driven config: the runner calls registry.skills.load() and uses the skill's
frontmatter for model/effort/permission_mode/required_tools/isolation/subagents.

Isolation tiers: none | workspace | host — see runner/workspaces.py. Workspace-
tier sessions additionally get PreToolUse guard hooks (runner/guards.py) that
hard-deny writes outside the clone and dangerous host commands, even under
permission_mode=bypassPermissions. This replaced the docker container lane on
2026-07-27 (docs/SDK_MIGRATION_2026-07-27.md).
"""

from __future__ import annotations

import asyncio
import functools
import json
import logging
import re
import subprocess
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    RateLimitEvent,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)

from src import audit_log
from src.config import settings
from src.db import CHANNEL_JOB_DONE, CHANNEL_JOB_STREAM, async_session, redis
from src.models import Job, JobKind, Project
from src.registry import models as models_registry
from src.registry.skills import (
    DEFAULT_REQUIRED_TOOLS,
    SkillConfig,
    SkillFrontmatterError,
    load as load_skill,
)


class SkillResolutionError(RuntimeError):
    """An explicit job kind names a skill that is missing or corrupt.

    Terminal by policy (2026-08-31, EVALUATION_2026-08-30 F1): running the
    job on registry defaults (full toolset, acceptEdits, no isolation) is the
    silent-host hole; escalating a contract failure to a bigger model would
    just re-fail it.
    """
from src.runner import agents as agents_mod
from src.runner import delivery, guards, quota, review, router, workspaces
from src.runner import pricing, secret_redact
from src.runner.claude_env import claude_subprocess_env
from src.runner.executors import codex_cli
from src.notify.outbox import build_ops_notice, enqueue_notice
from src.runner.result_capture import (
    API_RETRY_TO_TERMINAL,
    ENFORCEMENT_CATEGORIES,
    ResultCapture,
    capture_result_message,
    cli_version_column,
    derive_terminal_reason,
    result_columns,
    served_model_violation,
    usage_columns,
    usage_is_empty,  # noqa: F401 (re-export: is_api_terminal_session + tests)
)

logger = logging.getLogger(__name__)

# In-process registry of running sessions for /cancel.
_running_sessions: dict[str, ClaudeSDKClient] = {}


async def interrupt(job_id: str | uuid.UUID) -> bool:
    """Stop a running job (cancel listener, INV-8): the in-process SDK
    session when there is one, else whichever non-Anthropic executor holds
    the job's process (T4, 2026-10-21)."""
    client = _running_sessions.get(str(job_id))
    if client is None:
        for executor in _EXECUTORS.values():
            try:
                if await executor.interrupt(str(job_id)):
                    return True
            except Exception as exc:
                logger.warning("executor interrupt failed for %s: %s", job_id, exc)
        return False
    try:
        await client.interrupt()
        return True
    except Exception as exc:
        logger.warning("interrupt failed for %s: %s", job_id, exc)
        return False


# ── Skill resolution ────────────────────────────────────────────────────────


def _build_server_directive(
    skill_cfg: SkillConfig | None,
    cwd: Path,
    job_description: str = "",
    *,
    canonical_cwd: Path | None = None,
) -> str:
    """Build a context-appropriate server preamble. Reduces token waste by
    tailoring the directive to the task type.

    canonical_cwd: the real checkout when cwd is an isolated workspace clone.
    """
    base = "You are working inside the assistant server.\n\n"
    ctx_root = str(settings.server_root / ".context")
    is_workspace = canonical_cwd is not None and canonical_cwd != cwd

    # Chat: minimal directive
    if skill_cfg and skill_cfg.name == "chat":
        return base + "Respond directly. No tool use, no context reading needed.\n"

    # Project-scoped: point to project context + project protocol
    scope_root = canonical_cwd if is_workspace else cwd
    if scope_root != settings.server_root:
        project_slug = scope_root.name
        directive = base + (
            f"This job is scoped to the `{project_slug}` project.\n"
            f"Follow the project protocol at `{ctx_root}/PROJECT_PROTOCOL.md`.\n\n"
            "Read that project's CLAUDE.md and .context/CONTEXT.md (in your "
            "working directory) before acting.\n\n"
            "While working: prefer small committed steps. When you learn something "
            "non-obvious, append to the project's skills/GOTCHAS.md.\n\n"
            "Before finishing: update the project's .context/CHANGELOG.md. "
            "Write a one-paragraph summary as your final text message.\n"
        )
        if is_workspace:
            directive += (
                f"\n**Isolated workspace**: your working directory `{cwd}` is a "
                "per-job clone of the project. Work, commit, and push exactly as "
                "instructed (`git push origin <branch>` from your cwd) — the "
                "canonical checkout is fast-forwarded automatically after your "
                "push. Do NOT try to edit the canonical checkout directly.\n"
                "**Push gates**: verify before committing (tests/healthcheck/"
                "behavior probe green, no secrets in the diff, CHANGELOG "
                "updated); `git fetch origin && git pull --rebase origin "
                "<branch>` before pushing. Rejected push → rebase, re-verify, "
                "retry ONCE; still failing → report the divergence in your "
                "summary. NEVER force-push.\n"
            )
    else:
        # Server-scoped: full directive
        directive = base + (
            "Before acting:\n"
            f"1. Read `{ctx_root}/SYSTEM.md` and the relevant module CONTEXT.md.\n"
            "2. For debug/patch jobs, tail volumes/audit_log/*.jsonl for related work.\n\n"
            "While working: prefer small committed steps. When you learn something "
            "non-obvious, append to the relevant skill file (GOTCHAS.md / PATTERNS.md).\n\n"
            "Before finishing: update CHANGELOG.md for every module you touched. "
            "Write a one-paragraph summary as your final text message.\n"
        )
        if is_workspace:
            directive += (
                f"\n**Isolated workspace**: your working directory `{cwd}` is a "
                "per-job clone of the server repo. Server code lands via your "
                "skill's declared merge flow — the autonomous execution lane "
                "where your SKILL.md grants it (gate-green + in-session "
                "code-review LGTM + owner notification, MISSION §M 2026-07-31), "
                "else a branch push + PR (`git push origin HEAD:<branch-name>`). "
                "Protected paths ALWAYS stop at a PR for owner approval. Never "
                "edit the live checkout. The server's context docs are readable "
                f"at `{ctx_root}/`.\n"
                "**Push gates**: pytest green before committing (red never gets "
                "pushed), no secrets in the diff, CHANGELOG updated. Rejected "
                "push → fetch + rebase, retry ONCE; still failing → report. "
                "NEVER force-push. Push to main ONLY when your skill's lane "
                "explicitly authorizes it (server-patch/new-skill, post-LGTM); "
                "all other skills branch + PR.\n"
            )

        # Graph-walked context injection (Rec 4): if the job description
        # references known modules, append dependency context so the session
        # knows what else to check before making changes.
        if job_description:
            directive += _module_dependency_context(job_description)
            directive += _module_knowledge_context(job_description)

    # Append context_files reading list if the skill declares them
    if skill_cfg and skill_cfg.context_files:
        files_list = "\n".join(f"- `{f}`" for f in skill_cfg.context_files)
        directive += f"\n**Read these files first**:\n{files_list}\n"

    return directive


def _module_dependency_context(job_description: str) -> str:
    """If the job description mentions known modules, return a brief dependency
    note. Returns empty string if no modules detected or graph unavailable."""
    try:
        from src.context.module_graph import (
            detect_modules_in_text,
            parse_module_graph,
            reverse_graph,
        )
        system_md = (settings.server_root / ".context" / "SYSTEM.md").read_text()
        graph = parse_module_graph(system_md)
        if not graph:
            return ""
        rev = reverse_graph(graph)
        mentioned = detect_modules_in_text(job_description, set(graph.keys()))
        if not mentioned:
            return ""

        lines = ["\n**Module dependencies** (auto-detected from your task):"]
        for mod in sorted(mentioned):
            dependents = rev.get(mod, [])
            if dependents:
                dep_str = ", ".join(sorted(dependents))
                lines.append(
                    f"- `{mod}` is depended on by: {dep_str}. "
                    f"Read their CONTEXT.md before changing its API."
                )
            else:
                lines.append(f"- `{mod}` has no dependents in the graph.")
        lines.append("")
        return "\n".join(lines)
    except Exception:
        return ""


def parse_skill_file_entries(text: str) -> list[str]:
    """Parse entry titles from a module skills file (GOTCHAS.md, DEBUG.md, etc.).

    Entries start with '## ' after the APPEND_ENTRIES_BELOW marker.
    Returns a list of entry titles (the text after '## ').
    Pure function.
    """
    titles: list[str] = []
    after_marker = False
    for line in text.splitlines():
        if "APPEND_ENTRIES_BELOW" in line:
            after_marker = True
            continue
        if after_marker and line.startswith("## "):
            title = line[3:].strip()
            # Strip date prefix if present (e.g., "2026-04-20 — Title")
            if " — " in title:
                title = title.split(" — ", 1)[1]
            if title:
                titles.append(title)
    return titles


def _module_knowledge_context(job_description: str) -> str:
    """If the job description mentions known modules, surface relevant
    GOTCHAS and DEBUG entries from those modules' skill files.

    Returns a compact section with entry titles only (not full bodies)
    to keep token budget low. Returns empty string if nothing found.
    """
    try:
        from src.context.module_graph import detect_modules_in_text, parse_module_graph
        system_md = (settings.server_root / ".context" / "SYSTEM.md").read_text()
        graph = parse_module_graph(system_md)
        if not graph:
            return ""
        mentioned = detect_modules_in_text(job_description, set(graph.keys()))
        if not mentioned:
            return ""

        # Map module shorthands to top-level module names (runner, gateway, db, etc.)
        module_dirs: set[str] = set()
        for mod in mentioned:
            top = mod.split(".")[0]
            module_dir = settings.server_root / ".context" / "modules" / top / "skills"
            if module_dir.exists():
                module_dirs.add(top)

        if not module_dirs:
            return ""

        sections: list[str] = []
        for mod_name in sorted(module_dirs):
            skills_dir = settings.server_root / ".context" / "modules" / mod_name / "skills"
            entries: list[tuple[str, str]] = []  # (category, title)
            for fname in ("GOTCHAS.md", "DEBUG.md"):
                fpath = skills_dir / fname
                if not fpath.exists():
                    continue
                titles = parse_skill_file_entries(fpath.read_text())
                category = fname.replace(".md", "").lower()
                for t in titles:
                    entries.append((category, t))

            if entries:
                items = "\n".join(
                    f"  - [{cat}] {title}" for cat, title in entries
                )
                sections.append(f"- **{mod_name}**:\n{items}")

        if not sections:
            return ""

        return "\n**Known issues** (from module skill files):\n" + "\n".join(sections) + "\n"
    except Exception:
        return ""


# ── Task context (multi-turn) ──────────────────────────────────────────────


def format_task_turns(turns: list[dict]) -> str:
    """Format task turns into a compact conversation summary.

    turns: list of {"turn_number": int, "role": str, "content": str, "job_id": str|None}
    Pure function.

    The LAST assistant turn gets expanded (up to 8000 chars) because it
    typically contains the plan that the continuation should implement.
    Older turns are truncated to 500 chars.
    """
    if not turns:
        return ""

    # Find the last assistant turn index
    last_assistant_idx = -1
    for i, t in enumerate(turns):
        if t["role"] == "assistant":
            last_assistant_idx = i

    lines: list[str] = []
    for i, t in enumerate(turns):
        role = t["role"]
        content = t["content"]
        job_ref = f", job {t['job_id'][:8]}" if t.get("job_id") else ""

        # Expand the last assistant turn (the plan) — truncate others
        if i == last_assistant_idx:
            if len(content) > 8000:
                content = content[:8000] + "\n\n... (truncated)"
        else:
            if len(content) > 500:
                content = content[:500] + "..."

        lines.append(f"**Turn {t['turn_number']} ({role}{job_ref})**: {content}")
    return "\n\n".join(lines)


def build_task_context(turns_data: list[dict], task_id) -> str:
    """Format pre-fetched task turns as conversation context. Pure function.

    Returns a markdown section to prepend to the system prompt, or empty
    string if no prior turns exist. The turns are fetched asynchronously in
    run_session (the old version ran a nested event loop in a thread pool
    from sync code — fragile, and it silently dropped the task's memory on
    any failure).
    """
    if not turns_data:
        return ""

    formatted = format_task_turns(turns_data)
    task_id_short = str(task_id)[:8]

    # Find the last user turn to extract their latest instruction
    last_user_msg = ""
    for t in reversed(turns_data):
        if t["role"] == "user":
            last_user_msg = t["content"]
            break

    instructions = (
        "---\n"
        "## Your instructions for this turn\n\n"
    )
    if last_user_msg:
        instructions += f"The user replied: \"{last_user_msg[:500]}\"\n\n"
    instructions += (
        "Implement the plan from the conversation above. "
        "Work only within the project directory. "
        "If you need more information from the user, emit a "
        "`task_question` audit event and complete normally. "
        "When you have committed and pushed working code, emit `task_complete`.\n"
    )

    return (
        f"## Task conversation ({task_id_short})\n\n"
        f"{formatted}\n\n"
        f"{instructions}"
    )


async def _fetch_task_turns(task_id) -> list[dict]:
    """Fetch task turns from DB. Returns list of dicts."""
    from src.models import TaskTurn
    from sqlalchemy import select

    async with async_session() as s:
        result = await s.execute(
            select(
                TaskTurn.turn_number,
                TaskTurn.role,
                TaskTurn.content,
                TaskTurn.job_id,
            )
            .where(TaskTurn.task_id == task_id)
            .order_by(TaskTurn.turn_number)
        )
        return [
            {
                "turn_number": row.turn_number,
                "role": row.role,
                "content": row.content,
                "job_id": str(row.job_id) if row.job_id else None,
            }
            for row in result.all()
        ]


# ── Text-marker task events (P2) ────────────────────────────────────────────
#
# Sessions signal the task lifecycle by including markers in their FINAL text.
# The runner parses them and synthesizes the corresponding audit events. This
# is executor-agnostic (works identically in-process and inside containers,
# where the host audit log isn't mounted) and race-free (no session ever has
# to guess its own job id or audit file). The legacy python
# `audit_log.append(job_id, "task_complete", ...)` path keeps working — the
# job id is now injected into every task session's directive.

_PLAN_START = "<<<TASK_PLAN"
_PLAN_END = "TASK_PLAN>>>"

_LINE_MARKERS: list[tuple[str, str, str]] = [
    # (prefix, event kind, payload field)
    ("TASK_COMPLETE:", "task_complete", "summary"),
    ("TASK_QUESTION:", "task_question", "question"),
    ("EVAL_PASS:", "eval_pass", "evidence"),
    ("EVAL_FAIL:", "eval_fail", "feedback"),
]


def extract_text_events(final_text: str) -> list[dict[str, Any]]:
    """Parse lifecycle markers out of a session's final text. Pure function.

    Line markers: TASK_COMPLETE: / TASK_QUESTION: / EVAL_PASS: / EVAL_FAIL:
    Block marker (multi-line JSON plan):
        <<<TASK_PLAN
        { ...plan json... }
        TASK_PLAN>>>
    Malformed plan JSON is skipped (defensive), never raises.
    """
    if not final_text:
        return []
    events: list[dict[str, Any]] = []

    # Plan block
    start = final_text.find(_PLAN_START)
    end = final_text.find(_PLAN_END)
    if start != -1 and end > start:
        raw = final_text[start + len(_PLAN_START):end].strip()
        try:
            plan_obj = json.loads(raw)
            if isinstance(plan_obj, dict):
                events.append({"kind": "task_plan", "plan": plan_obj})
        except json.JSONDecodeError:
            logger.warning("TASK_PLAN block present but JSON is malformed — ignored")

    for line in final_text.splitlines():
        s = line.strip()
        for prefix, kind, field in _LINE_MARKERS:
            if s.startswith(prefix):
                value = s[len(prefix):].strip()
                events.append({"kind": kind, field: value})
                break
    return events


# ── Budget accounting (Rec 8) ──────────────────────────────────────────────

# Context windows (input tokens) by bare model id, fed from the repo-root
# `models.yml` via the registry (T1, 2026-10-21). Keyed by `ModelRef.model_id`
# — the string `options.model` carries — so the lookup below is unchanged.
_MODEL_BUDGETS: dict[str, int] = models_registry.context_windows()
_DEFAULT_BUDGET = 200_000


@functools.lru_cache(maxsize=1)
def cli_version() -> str:
    """Version of the SDK-bundled Claude CLI (stamped into `jobs.cli_version`
    on the Anthropic lane; the Codex lane stamps `ExecResult.cli_version`).

    Read from the SDK package itself — `claude_agent_sdk._cli_version.
    __cli_version__` ("2.1.139" in the pinned wheel) — NOT by spawning the
    CLI binary and NOT by parsing a SystemMessage (spec §2.3 row 007).
    The pin moves the attribute and the binary together, so this is the same
    number with no cold start to hide and nothing to warm at startup.
    'unknown' if a future pin drops the module or the attribute; truncated to
    the column's 24 chars.
    """
    try:
        from claude_agent_sdk import _cli_version
        value = str(getattr(_cli_version, "__cli_version__", "") or "").strip()
    except Exception:  # noqa: BLE001 — a missing attribute must never fail a job
        value = ""
    return (value or "unknown")[:24]


def estimate_context_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token. Pure function."""
    return len(text) // 4


# ── API-terminal session detection (2026-08-21) ────────────────────────────
#
# The bundled Claude CLI, on an Anthropic-side 5xx (e.g. 529 Overloaded) or a
# request timeout, emits the failure as a plain TextBlock ("API Error: 529
# Overloaded. ...") and returns a ResultMessage whose usage dict is all-zeros
# and whose `is_error` is not usefully set — the SDK's normal error-parity
# check (`is_error AND no text`) below therefore does NOT trigger, so we
# happily record the job as `completed`. Escalation.on_failure never fires,
# self-diagnose is never enqueued, and the schedule's last_run_at looks
# healthy. Job 143c8cfb (atlas-evaluate, 2026-08-17 13:48Z) is the flag case:
# the summary is literally the CLI banner, ran 200s with zero output — and
# the atlas governor was silently dark for 10 days as a result.
#
# The classifier is deliberately conservative: BOTH the banner shape AND
# empty usage must hold before we reclassify a completed session as failed.

_API_TERMINAL_BANNER = re.compile(
    r"""
    ^\s*
    (?:
        # "API Error: 529 Overloaded", "API Error: 500 Internal Server ...",
        # "API Error: 503 Service Unavailable", "API Error: Request timed
        # out ...", "API Error: Overloaded".
        API\s*Error\s*:\s*
        (?:5\d\d\b|Request\s*timed\s*out\b|Overloaded\b|overloaded_error\b)
        |
        # SDK error-type prefixes: "Error: overloaded_error", "Error:
        # internal_server_error", "Error: api_error".
        Error\s*:\s*
        (?:overloaded_error|internal_server_error|api_error)\b
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

# CLI banner bodies are short (~1-3 sentences). Anything longer is
# overwhelmingly a real skill summary that legitimately leads with the phrase
# (e.g. a self-diagnose report). Keeps the classifier conservative.
_API_TERMINAL_MAX_SUMMARY_LEN = 800


def is_api_terminal_summary(summary: str | None) -> bool:
    """True when the session's final text is *only* the bundled Claude CLI's
    Anthropic-side terminal banner (e.g. "API Error: 529 Overloaded. ...").

    Pure function. Matches only 5xx / timeout / overloaded / api_error /
    internal_server_error shapes anchored at the start of the summary; caps
    the total length to filter out legitimate summaries that lead with the
    phrase. Never matches 4xx client errors (those are our bug, not the API's).
    """
    if not summary:
        return False
    text = summary.strip()
    if not text or len(text) > _API_TERMINAL_MAX_SUMMARY_LEN:
        return False
    return bool(_API_TERMINAL_BANNER.match(text))


# `usage_is_empty` lives in `runner.result_capture` since B2 (2026-10-21) and
# is re-exported here: `is_api_terminal_session` and `tests/test_api_terminal.py`
# import it from this module.
def is_api_terminal_session(summary: str | None, usage: dict | None) -> bool:
    """Combined predicate: the session's final text is an API-terminal
    banner AND usage shows no work. Pure function.

    Both signals must hold. A banner shape alone can appear in a legitimate
    report; empty usage alone would over-trigger for edge cases we can't
    audit here. The intersection is the specific SDK failure mode that hid
    a 529 as `completed` for job 143c8cfb (2026-08-17).
    """
    return is_api_terminal_summary(summary) and usage_is_empty(usage)


def context_budget_fraction(
    system_prompt: str,
    model: str,
) -> tuple[int, int, float]:
    """Return (estimated_tokens, model_budget, fraction). Pure function."""
    tokens = estimate_context_tokens(system_prompt)
    budget = _MODEL_BUDGETS.get(model, _DEFAULT_BUDGET)
    return tokens, budget, tokens / budget if budget > 0 else 0.0


# ── Session timeout (moved here from main.py in T4; main re-exports) ────────

# Hard ceiling on per-job session-timeout extension. A payload can raise the
# global default for a legitimately heavy session (atlas-momo-research cycles
# — three cycle-2 attempts died at the 30-min ceiling, 2026-08-11) but can
# never disable the ceiling entirely.
SESSION_TIMEOUT_CAP_SECONDS = 5400


def resolve_session_timeout(payload: dict | None, default: int,
                            cap: int = SESSION_TIMEOUT_CAP_SECONDS) -> int:
    """Effective session timeout for a job. Pure function.

    `payload.session_timeout_seconds` overrides the global default, clamped
    to [60, cap]; missing or unparseable values fall back to the default.
    Used by `main._process_job`'s `wait_for` and, since T4, as the CLI
    executor's own `timeout_s` so both ceilings agree.
    """
    try:
        raw = (payload or {}).get("session_timeout_seconds")
        if raw is None:
            return default
        val = int(raw)
    except (TypeError, ValueError, OverflowError):
        return default
    return max(60, min(val, cap))


#: How far under `main._process_job`'s `wait_for` ceiling the CLI executor's
#: own `timeout_s` sits (review round 1, 2026-10-21). Main's timer starts
#: before skill resolution and the clone, so an equal deadline always lost
#: to main's and the executor's `timeout` terminal reason was unreachable;
#: the margin covers the pre-process setup plus the executor's kill grace.
EXECUTOR_TIMEOUT_MARGIN_S = 30.0
#: Never hand the executor less than this, whatever the ceiling.
EXECUTOR_TIMEOUT_FLOOR_S = 30.0


#: Wall-clock the pre-push gate's commit + push + audit take after the
#: reviewer returns (T5 review round 1, 2026-10-21) — reserved, with
#: `review.GATE_TIMEOUT_SECONDS`, out of the executor's budget so the gate
#: completes INSIDE main's `wait_for` ceiling instead of being cancelled
#: mid-review (which would fail a successful job as `timeout`).
GATE_PUBLISH_MARGIN_S = 60.0


def gate_reserve_s() -> float:
    """Seconds a non-Anthropic lane keeps back for the pre-push gate: the
    reviewer's ceiling plus the publish margin. Pure (reads the gate
    constant at call time so a test can shrink it)."""
    return float(review.GATE_TIMEOUT_SECONDS) + GATE_PUBLISH_MARGIN_S


def executor_timeout_s(ceiling_s: float, reserve_s: float = 0.0) -> float:
    """The CLI executor's `timeout_s` for a session ceiling. Pure: strictly
    below the ceiling by `EXECUTOR_TIMEOUT_MARGIN_S` plus `reserve_s` (the
    gate allowance on non-Anthropic lanes, `gate_reserve_s()`), floored at
    `EXECUTOR_TIMEOUT_FLOOR_S` (the ceiling itself is never below 60)."""
    return max(EXECUTOR_TIMEOUT_FLOOR_S,
               float(ceiling_s) - EXECUTOR_TIMEOUT_MARGIN_S - float(reserve_s))


# ── Provider dispatch (cross-vendor writer slice T4, 2026-10-21) ────────────
#
# One dispatch branch in `run_session` (plan §4a — no `ExecSpec` extraction):
# Anthropic runs in-process through the SDK exactly as before; any other
# provider runs through the executor module the registry names for it
# (`models.yml` `executor:` → `_EXECUTORS`). Everything before the branch
# (skill, cwd, isolation, clone, system prompt) and after it (marker parse,
# summary, `job_completed`) is shared.

#: Registry `executor:` name → module with `run(job, *, cwd, prompt, model_id,
#: sandbox, timeout_s, …) -> ExecResult` and `interrupt(job_id) -> bool`.
#: Anthropic is NOT here (it is the in-process SDK, not an executor module).
_EXECUTORS: dict[str, Any] = {codex_cli.EXECUTOR_NAME: codex_cli}

#: Plan §4f — "one credential, one stream": how many of an executor's
#: processes may run at once in this runner, keyed by the registry's
#: `executor:` name (whole-branch review, 2026-10-21). Codex is 1 because
#: concurrent streams on one `auth.json` race the refresh-token rotation
#: (lockout → every later job `auth_expired`). An executor missing here
#: gets 1 too (fail closed). `main`'s global `MAX_CONCURRENT_JOBS` still
#: bounds everything; this slot is the per-credential cap under it.
EXECUTOR_CONCURRENCY: dict[str, int] = {codex_cli.EXECUTOR_NAME: 1}
_EXECUTOR_SLOTS: dict[str, asyncio.Semaphore] = {}


def executor_slot(executor_name: str) -> asyncio.Semaphore:
    """The per-executor semaphore (created lazily so it binds to the loop
    that first contends on it; tests reset `_EXECUTOR_SLOTS`)."""
    slot = _EXECUTOR_SLOTS.get(executor_name)
    if slot is None:
        slot = asyncio.Semaphore(EXECUTOR_CONCURRENCY.get(executor_name, 1))
        _EXECUTOR_SLOTS[executor_name] = slot
    return slot


def executor_name_for(provider: str) -> str | None:
    """The registry's `executor:` name for a non-Anthropic provider (the
    `_EXECUTORS` / `EXECUTOR_CONCURRENCY` key), or None."""
    if provider == models_registry.DEFAULT_PROVIDER:
        return None
    entry = models_registry.REGISTRY.provider(provider)
    return entry.executor if entry is not None else None


def executor_for(provider: str) -> Any | None:
    """The executor module for a non-Anthropic provider, or None (Anthropic,
    or a registry provider whose `executor:` this runner does not have)."""
    if provider == models_registry.DEFAULT_PROVIDER:
        return None
    entry = models_registry.REGISTRY.provider(provider)
    if entry is None:
        return None
    return _EXECUTORS.get(entry.executor)


def resolve_model_choice(
    payload: dict | None, skill_cfg: SkillConfig | None,
) -> tuple[models_registry.ModelRef, str]:
    """Pick and validate the job's model: `payload.model > skill.model >
    settings.default_model`, resolved through the registry (T1, 2026-10-21).
    Returns `(ref, reason)` with `reason ∈ payload | pin | default` — the
    `provider_selected` audit field (T4).

    Pure. Raises `ProviderRefused` (terminal in `main._process_job`, never
    escalated) when the id is unknown (C12), its provider is not in
    `settings.router_providers_enabled`, or no executor exists for it. The
    Anthropic path is unchanged: `ref.model_id` is the same bare string the
    SDK was handed before.
    """
    payload = payload or {}
    if payload.get("model"):
        raw, reason = payload["model"], "payload"
    elif skill_cfg is not None and skill_cfg.model:
        raw, reason = skill_cfg.model, "pin"
    else:
        raw, reason = settings.default_model, "default"
    ref = models_registry.resolve_enabled(raw)
    if ref.provider != models_registry.DEFAULT_PROVIDER and executor_for(ref.provider) is None:
        raise models_registry.ProviderRefused(
            raw, f"no executor for provider {ref.provider!r} in this runner",
            provider=ref.provider, model_id=ref.model_id)
    return ref, reason


def _resolve_model(payload: dict | None, skill_cfg: SkillConfig | None) -> models_registry.ModelRef:
    """`resolve_model_choice(...)[0]` — the value-only form `_build_options` uses."""
    return resolve_model_choice(payload, skill_cfg)[0]


#: Skills that write to THIS repo or deploy it (plan D-A): a non-Anthropic
#: provider may run them only when `settings.router_code_server_providers`
#: lists it. Default off — the review gate is one Anthropic session's
#: judgement, and `guards.py` / `lint_docs.py` are what an injected diff
#: would target.
CODE_SERVER_SKILLS: frozenset[str] = frozenset({
    "server-patch", "server-deploy", "new-skill", "deploy-director",
    "atlas-redeploy", "project-redeploy",
})


def code_server_providers() -> frozenset[str]:
    """`settings.router_code_server_providers` as a set (CSV, case-folded)."""
    raw = settings.router_code_server_providers or ""
    return frozenset(p.strip().lower() for p in raw.split(",") if p.strip())


def is_owner_origin(created_by: str | None) -> bool:
    """True when the job was launched by the owner directly — Telegram, the
    web dashboard or the CLI. Pure. Everything the runner's own machinery
    spawns (scheduler, escalation, dispatch MCP, event triggers, plans,
    evaluators, …) and an unknown/empty origin is NOT the owner — an
    allowlist, so a new autonomous origin can never pass by omission."""
    cb = (created_by or "").strip().lower()
    if cb.startswith("telegram:"):
        return True
    return cb in ("web", "cli") or cb.startswith("cli:")


def lane_refusal(
    ref: models_registry.ModelRef,
    *,
    skill_name: str,
    skill_cfg: SkillConfig | None,
    isolation: str,
    payload: dict | None,
    created_by: str | None,
    code_server_providers: frozenset[str],
) -> str | None:
    """Why a non-Anthropic provider may NOT run this job, or None. Pure.

    Fail-closed lane rules (plan T4; old spec §2.6 Codex row: workspace
    only, no MCP, no subagents, `code-server` pinned by setting):
    - isolation tier must be `workspace` (the executor's Seatbelt confines
      writes to the clone; `none`/`host` would be an unconfined host session);
    - the skill declares no `subagents:` and no `needs-*-mcp` tag (there is
      no delegation and no MCP on a non-Anthropic executor — silently running
      without them would change the skill's contract);
    - a `code-server` skill needs the provider in `router_code_server_providers`;
    - a `payload.model` override that moves an Anthropic-pinned skill to
      another provider is honoured only from the owner (Telegram/web/CLI),
      never from the scheduler, an escalation, the dispatch MCP, … — a
      scheduled routine runs another provider by pinning it in the skill
      frontmatter or by overriding a skill with no pin (plan §2).
    The provider-enabled check is `models.resolve_enabled` (earlier).
    """
    if ref.provider == models_registry.DEFAULT_PROVIDER:
        return None
    if isolation != "workspace":
        return (f"isolation tier {isolation!r}: non-Anthropic executors run on the "
                f"'workspace' tier only")
    if skill_cfg is not None:
        if skill_cfg.subagents:
            return (f"skill {skill_cfg.name!r} declares subagents "
                    f"({', '.join(skill_cfg.subagents)}): no delegation on a "
                    f"non-Anthropic executor")
        mcp_tags = [t for t in skill_cfg.tags
                    if t.startswith("needs-") and t.endswith("-mcp")]
        if mcp_tags:
            return (f"skill {skill_cfg.name!r} needs MCP ({', '.join(mcp_tags)}): "
                    f"no MCP on a non-Anthropic executor")
    if skill_name in CODE_SERVER_SKILLS and ref.provider not in code_server_providers:
        return (f"skill {skill_name!r} is in the code-server set; provider "
                f"{ref.provider!r} is not in ROUTER_CODE_SERVER_PROVIDERS "
                f"({','.join(sorted(code_server_providers)) or '<empty>'})")
    payload = payload or {}
    if payload.get("model") and skill_cfg is not None and skill_cfg.model \
            and skill_cfg.provider == models_registry.DEFAULT_PROVIDER \
            and not is_owner_origin(created_by):
        return (f"payload model override to {ref.qualified!r} on a job from "
                f"{(created_by or '<unknown>')!r}: skill {skill_cfg.name!r} pins "
                f"{skill_cfg.model!r} and only the owner (telegram/web/cli) may override it")
    return None


def canonical_refusal(
    canonical_cwd: Path,
    *,
    slug: str | None,
    provider: str,
    code_server_providers: frozenset[str],
    server_root: Path,
    projects_dir: Path,
) -> str | None:
    """Why a non-Anthropic provider may NOT write to this canonical, or
    None. Pure (T5 review round 1, 2026-10-21; plan D-A).

    `lane_refusal` pins the `code-server` rule on skill NAMES, but a
    slug-less job (a generic task, a project whose directory is missing)
    resolves its canonical to `settings.server_root` — THIS repo — and the
    T5 publish path would then commit and push a Codex diff to
    `origin/main` (deploy autopilot) from a clone of the production
    checkout, which D-A keeps off and the single-writer topology forbids.
    So, unless the provider is in `ROUTER_CODE_SERVER_PROVIDERS`, refuse
    when: the job has no project slug; the canonical IS the server root;
    or the canonical lies inside the server root but outside
    `projects_dir` (`.context/`, `skills/`, `volumes/` …). A dev-repo
    project's clone elsewhere on disk (atlas) is a project and passes.
    """
    if provider == models_registry.DEFAULT_PROVIDER or provider in code_server_providers:
        return None
    try:
        canon = canonical_cwd.resolve()
        root = server_root.resolve()
        projects = projects_dir.resolve()
    except OSError:
        canon, root, projects = canonical_cwd, server_root, projects_dir
    what = (f"provider {provider!r} is not in ROUTER_CODE_SERVER_PROVIDERS "
            f"({','.join(sorted(code_server_providers)) or '<empty>'}; plan D-A)")
    if not slug:
        return f"job has no project slug, so its canonical is the server root; {what}"
    if canon == root:
        return f"canonical {canonical_cwd} is the server root; {what}"
    if canon.is_relative_to(root) and not canon.is_relative_to(projects):
        return (f"canonical {canonical_cwd} is inside the server root but not a "
                f"project directory; {what}")
    return None


class ExecutorFailed(RuntimeError):
    """A non-Anthropic executor ended without `terminal_reason == "ok"`.

    Terminal in `main._process_job` (stamps `terminal_reason`/`model_served`,
    `error_category=<terminal_reason>`), never escalated: an escalation would
    silently re-run the job on the skill's Anthropic escalation target — a
    vendor switch this slice does not make (T6 adds the per-provider hold
    and front-requeue for `rate_limited`).
    """

    def __init__(self, provider: str, model_id: str, terminal_reason: str,
                 message: str | None, *, model_served: str | None = None):
        self.provider = provider
        self.model_id = model_id
        self.terminal_reason = terminal_reason
        self.model_served = model_served
        super().__init__(
            f"{provider}/{model_id} executor ended {terminal_reason}: "
            f"{(message or 'no detail')[:500]}")


class ReviewBlocked(RuntimeError):
    """The pre-push Anthropic review gate (T5, 2026-10-21; INV-21(c)) did
    not return LGTM for a non-Anthropic job's diff: `changes_requested`,
    `blocker`, `error` (the reviewer could not run) or a timeout (counted as
    `changes_requested`). Terminal in `main._process_job`
    (`error_category=review_blocked`, `terminal_reason=review_blocked`,
    `review_outcome=<verdict>`), never escalated; the clone is kept with
    its uncommitted diff, nothing was committed, pushed or ff-synced.
    """

    def __init__(self, provider: str, model_id: str, *, verdict: str,
                 findings_n: int = 0, timed_out: bool = False,
                 denied_paths: list[str] | None = None,
                 refused_reason: str | None = None, diff_chars: int = 0):
        self.provider = provider
        self.model_id = model_id
        self.verdict = verdict
        self.findings_n = findings_n
        self.timed_out = timed_out
        # Non-empty = the diff was refused BEFORE a reviewer ran because it
        # touches `review.GATE_DENIED_*` paths (T5 review round 1).
        self.denied_paths = list(denied_paths or [])
        # Why the gate refused BEFORE any reviewer ran, or None when a
        # reviewer returned the verdict (whole-branch review, 2026-10-21):
        # `denied_path` | `unparseable_path` | `diff_too_large`. Mirrors
        # `merge_gate_refused.reason`.
        self.refused_reason = refused_reason or ("denied_path" if self.denied_paths else None)
        self.diff_chars = diff_chars
        head = f"pre-push review gate refused the diff for {provider}/{model_id}"
        if self.refused_reason == "denied_path":
            why = f"diff touches denied paths: {', '.join(self.denied_paths)}"
        elif self.refused_reason == "unparseable_path":
            why = (f"diff names {len(self.denied_paths)} path(s) the gate cannot parse "
                   f"(git-quoted); the deny list could not be applied")
        elif self.refused_reason == "diff_too_large":
            why = (f"diff too large: {diff_chars} chars > {review.MAX_DIFF_CHARS}; "
                   f"the reviewer would only see part of it")
        else:
            why = "reviewer timed out" if timed_out else f"{findings_n} finding(s)"
            head = f"pre-push review gate returned {verdict} for {provider}/{model_id}"
        super().__init__(f"{head} ({why}); nothing was pushed — the clone is kept")


def build_executor_prompt(system_prompt: str, description: str) -> str:
    """The single prompt string a CLI executor gets: the system prompt
    (directive + job id + marker protocol + transcript + skill body)
    prepended to the task (plan §4h — never written to `AGENTS.md`, which
    the job would commit). Pure. Never begins with `-` (the argv builder
    would refuse it as a flag)."""
    head = (system_prompt or "").rstrip()
    body = (description or "").strip()
    text = f"{head}\n\n---\n\n# Task\n\n{body}\n" if head else f"# Task\n\n{body}\n"
    return text


async def _resolve_skill(job: Job) -> tuple[str, SkillConfig | None]:
    """
    Determine the skill for this job:
      - explicit kind (not "task" / "chat") → that skill
      - kind = "chat" → chat skill
      - kind = "task" → rule-based router; on no match, LLM fallback
        (llm_router.llm_route); "" means generic task.
    Every routing decision is audited (`routing_decision`) so retrospective
    can measure routing precision.
    Returns (skill_name_or_empty, SkillConfig_or_None).
    """
    if job.kind == JobKind.task.value:
        matched = router.route(job.description)
        if matched:
            audit_log.append(str(job.id), "routing_decision",
                             method="rule", skill=matched)
            try:
                return matched, load_skill(matched)
            except SkillFrontmatterError as exc:
                raise SkillResolutionError(
                    f"router matched skill '{matched}' but its frontmatter is "
                    f"corrupt: {exc}") from exc

        # LLM fallback (P2) — the router docstring promised this since Phase 4
        try:
            from src.runner.llm_router import llm_route
            llm_skill, confidence = await llm_route(job.description)
        except Exception as exc:
            logger.warning("llm route failed for %s: %s", str(job.id)[:8], exc)
            llm_skill, confidence = "", 0.0

        if llm_skill:
            audit_log.append(str(job.id), "routing_decision",
                             method="llm", skill=llm_skill,
                             confidence=round(confidence, 3))
            try:
                return llm_skill, load_skill(llm_skill)
            except SkillFrontmatterError as exc:
                raise SkillResolutionError(
                    f"LLM router chose skill '{llm_skill}' but its frontmatter "
                    f"is corrupt: {exc}") from exc

        audit_log.append(str(job.id), "routing_decision",
                         method="fallback", skill="")
        return "", None   # generic task, use defaults + full tool set
    # Any other kind maps directly to a skill of the same name.
    # Underscores become dashes EXCEPT a leading underscore (marks internal skills):
    #   research_report → research-report
    #   _writeback      → _writeback   (leading _ preserved)
    skill_name = job.kind if job.kind.startswith("_") else job.kind.replace("_", "-")
    try:
        cfg = load_skill(skill_name)
    except SkillFrontmatterError as exc:
        raise SkillResolutionError(
            f"skill '{skill_name}' (kind '{job.kind}') has corrupt frontmatter: {exc}"
        ) from exc
    if cfg is None:
        raise SkillResolutionError(
            f"kind '{job.kind}' names no skill (skills/{skill_name}/SKILL.md missing) "
            "— refusing to run it as an unlabeled generic session")
    return skill_name, cfg


def _build_system_prompt(
    job: Job,
    cwd: Path,
    skill_cfg: SkillConfig | None,
    task_turns: list[dict] | None = None,
    *,
    canonical_cwd: Path | None = None,
) -> str:
    """The system prompt every executor gets: context-aware server directive
    + job id + task-event marker protocol + task transcript + skill body.
    Split out of `_build_options` unchanged (T4, 2026-10-21) so the SDK path
    and the CLI-executor path assemble the one prompt the same way."""
    server_directive = _build_server_directive(
        skill_cfg, cwd, job.description,
        canonical_cwd=canonical_cwd,
    )
    system_prompt = server_directive

    # Job identity + task-event protocol (P2). Applies to every non-chat job
    # so sessions never have to guess their own job id, and so lifecycle
    # markers work identically in-process and inside containers.
    if not (skill_cfg and skill_cfg.name == "chat"):
        system_prompt += (
            f"\n**Job id**: `{job.id}`.\n"
            "**Task events**: signal the task lifecycle by putting a marker in "
            "your FINAL text message (the runner parses it): "
            "`TASK_COMPLETE: <one-line summary>` when ALL work is committed/done; "
            "`TASK_QUESTION: <question>` to ask the user and pause. "
            "These replace (and are more reliable than) the audit_log.append "
            "python snippet.\n"
        )

    # Multi-turn task context injection
    if job.task_id and task_turns:
        task_ctx = build_task_context(task_turns, job.task_id)
        if task_ctx:
            system_prompt += f"\n{task_ctx}\n"

    if skill_cfg and skill_cfg.body.strip():
        system_prompt = f"{system_prompt}\n\n---\n\n# Active skill\n\n{skill_cfg.body}"
    return system_prompt


# ── E1: INV-3 from project scope — the settings-channel override refusal ─────
# (spec §6 "Settings-channel override refusal, keyed on provenance", §2.4;
# design of record P0 plan Task 19 + the re-cut E1 Deltas; D-P1-12.)
#
# `setting_sources=["project"]` in _build_options loads <cwd>/.claude/
# settings.json and settings.local.json from the clone the job runs in — and
# from the SERVER ROOT for the isolation:none skills. Those files are a code
# channel, not just an auth channel: `hooks` runs arbitrary commands at
# SessionStart/PreToolUse, `permissions.allow` widens what any later session
# may do, `mcpServers` adds tools, and `apiKeyHelper`/`env.ANTHROPIC_*`/
# `ANTHROPIC_BASE_URL` outrank the Keychain /login — the first two re-bill Max
# work to an API key, the last redirects it. Atlas is GitHub-canonical with
# other machines committing, so the file can arrive without anyone here doing
# anything. Refuse the job; never strip or rewrite the file.
SETTINGS_OVERRIDE_KEYS: tuple[str, ...] = (
    "hooks",
    "permissions",
    "mcpServers",
    "enableAllProjectMcpServers",
    "apiKeyHelper",
    "env",
    "ANTHROPIC_BASE_URL",
    # Recorded deviation from spec §6's seven (review 2026-10-29): the
    # per-server form of `enableAllProjectMcpServers` — approving named
    # servers from the clone's own `.mcp.json` adds tools exactly as the
    # "all" form does, so refusing one and not the other would be a hole.
    "enabledMcpjsonServers",
)

# The subset that outranks /login. Not a second check — a LABEL, so the audit
# event and the failed card can distinguish "someone committed a hook" from
# "someone redirected your billing". Auth keys are refused in every checkout,
# tracked or not, canonical or clone; the observe arm never covers them.
SETTINGS_AUTH_KEYS: tuple[str, ...] = (
    "apiKeyHelper",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "CLAUDE_CODE_OAUTH_TOKEN",
    "ANTHROPIC_BASE_URL",
)

# This repo's OWN .claude/ is loaded as project scope by every isolation:none
# skill (cwd == server root), and its two TRACKED files carry `enabledPlugins`
# and `permissions` — the second is in the refusal set above. So the server
# root's own files may carry `permissions` (the one allowed key the refusal
# set names; `enabledPlugins` is listed for the record and is never refused),
# and `tests/test_settings_auth_override.py::test_settings_no_hooks` pins that
# they carry nothing else. The exemption is per KEY, never per path (a hook
# there is refused like anywhere).
#
# It is keyed on PROVENANCE, not on the cwd path: a workspace-tier job's cwd
# is ws.path — a `git clone` of the canonical — and both tracked files travel
# with the clone, so a path test would refuse server-patch, new-skill,
# atlas-build and every skill-less job. The allowance applies when the
# canonical is the server root and the file's bytes equal the canonical's
# copy (working tree OR tracked HEAD blob — a clone carries HEAD's bytes, and
# the dev checkout's settings.local.json is routinely dirty). A clone is a
# copy; a clone with a key added is not. `test_settings_no_hooks` pins the
# two files' contents inside the deploy gate; the content-hash pin of spec
# §2.4 is deferred with `restraints.py` (spec §14 item 10), and the residual
# (a file edited directly on prod) is what D6's first half — MISSION §M — is
# for. Nothing here edits either file.
TRACKED_SETTINGS_ALLOWED_KEYS: frozenset[str] = frozenset({"enabledPlugins", "permissions"})
TRACKED_SETTINGS_FILES: tuple[str, ...] = (".claude/settings.json",
                                           ".claude/settings.local.json")
_SETTINGS_FILE_NAMES: tuple[str, ...] = ("settings.local.json", "settings.json")

# D-P1-12's observe arm, SIZED IN CODE (review 2026-10-29): which code-channel
# key, in which hosted project's own tracked file, is audited + DM'd instead
# of refused. Today exactly bingo's PostToolUse hook. Anything a project
# canonical acquires beyond this — including a `hooks`/`mcpServers`/`env` key
# that another machine commits to a GitHub-canonical project such as atlas
# and that arrives here on the next rebase — is REFUSED, because "the
# canonical's own tracked copy" is not a bound on its own for a canonical
# other people commit to. `tests/test_settings_auth_override.py::
# test_project_settings_inventory` keeps this table and the checkout in step;
# a new row is an owner decision (plan §7 row 11 / D-P1-12), never a drift.
OBSERVED_PROJECT_SETTINGS: dict[tuple[str, str], frozenset[str]] = {
    ("baseball-bingo", "settings.json"): frozenset({"hooks"}),
}
# Claude Code itself writes `permissions.allow` into any project's
# <project>/.claude/settings.local.json when a session approves a tool, so
# that one key in that one (gitignored-by-convention) file is observed for
# every project; `permissions` committed into a project's settings.json is
# not (it widens what every later session may do, and nothing writes it there).
OBSERVED_LOCAL_SETTINGS_KEYS: frozenset[str] = frozenset({"permissions"})

#: One `settings_override` DM per project per UTC day (D-P1-12; same shape as
#: D1's schedule-gap claim: SET NX only after the notice row exists).
KEY_SETTINGS_OVERRIDE_NOTIFIED_PREFIX = "settings_override:notified:"
TTL_SETTINGS_OVERRIDE_NOTIFIED = 129_600   # 36 h: one per day with slack


@dataclass(frozen=True)
class SettingsOverride:
    """What `settings_override` found: the first offending key, the file it
    sits in, whether it is an auth key (re-bills/redirects — never observed),
    whether D-P1-12's observe arm applies, and the project (the canonical's
    directory name; None when the canonical is the server root)."""
    key: str
    file: str
    auth_key: bool
    observed_only: bool
    project: str | None


class SettingsOverrideRefused(models_registry.ProviderRefused):
    """A settings-channel override refused before the session starts. A
    subclass of the registry's `ProviderRefused` so `main._process_job`'s
    existing handler stamps `terminal_reason="provider_refused"` and never
    escalates (a bigger model would run the same poisoned clone); `reason` is
    `settings_override:<key>` and `key`/`file`/`auth_key` ride the audit row
    additively (E1 Deltas — no `observed_only` field here: the observe arm
    has its own audit kind)."""

    def __init__(self, found: SettingsOverride, *, path: Path,
                 provider: str | None = "anthropic", model_id: str | None = None,
                 raw: str | None = None) -> None:
        self.key = found.key
        self.file = found.file
        self.auth_key = found.auth_key
        what = ("outranks the Keychain login and re-bills or redirects this work"
                if found.auth_key else
                "executes with owner privileges in every later session and bypasses "
                "guards.py/lint_docs.py")
        reason = (f"settings_override:{found.key}")
        super().__init__(raw or "", reason, provider=provider, model_id=model_id)
        # ProviderRefused's own message is about model refs; say what this is.
        self.args = (f"{found.key} in {path / found.file} {what} (spec §6) — remove it "
                     f"from the clone; never strip it automatically",)

    def __str__(self) -> str:
        return self.args[0]


def settings_override(cwd: Path, *, canonical: Path | None = None) -> SettingsOverride | None:
    """The first offending key in <cwd>/.claude/settings*.json, else None.

    settings.local.json is checked first: it is gitignored in most repos (so it
    is the likelier carrier) and the CLI gives it precedence. When the offender
    is `env`, the specific auth key inside it is reported instead of the
    container, so the card can say what was actually done. Unreadable or
    invalid JSON is NOT an override — a malformed settings file is the CLI's
    problem; inventing a refusal from it would fail honest jobs.

    `canonical` is the real checkout when `cwd` is a workspace clone (the
    value run_session holds as `canonical_cwd`); for an isolation:none job it
    is `cwd` itself. The server root's own two tracked files — and
    byte-identical copies of them in a clone of the server root — may carry
    TRACKED_SETTINGS_ALLOWED_KEYS and nothing else; every other key is refused
    there exactly as in any other clone, and with no canonical there is no
    allowance at all. Pure except for file reads under <cwd>/.claude and
    <canonical>/.claude (plus `git show HEAD:` of the canonical's copy).
    """
    cwd = Path(cwd)
    canon = Path(canonical) if canonical is not None else None
    own_root = canon is not None and _same_dir(canon, settings.server_root)
    project = None if (canon is None or own_root) else canon.name
    for name in _SETTINGS_FILE_NAMES:
        path = cwd / ".claude" / name
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        env = data.get("env") if isinstance(data.get("env"), dict) else {}
        # Name the auth key inside `env` before the generic `env` container.
        for key in SETTINGS_AUTH_KEYS:
            if key in env:
                return SettingsOverride(key=key, file=name, auth_key=True,
                                        observed_only=False, project=project)
        allowed = own_root and _matches_canonical(cwd, name, canon)
        hits: list[SettingsOverride] = []
        for key in SETTINGS_OVERRIDE_KEYS:
            if allowed and key in TRACKED_SETTINGS_ALLOWED_KEYS:
                continue
            if key in data:
                hits.append(SettingsOverride(
                    key=key, file=name, auth_key=key in SETTINGS_AUTH_KEYS,
                    observed_only=settings_override_observe_only(
                        key, cwd=cwd, file_name=name, canonical=canon),
                    project=project))
        if hits:
            # A refused key is never masked by an observed one in the same
            # file (bingo's observed `hooks` beside a committed `mcpServers`
            # must refuse): report the first REFUSED hit, else the observed one.
            return next((h for h in hits if not h.observed_only), hits[0])
    return None


def settings_override_observe_only(key: str, *, cwd: Path, file_name: str,
                                  canonical: Path | None) -> bool:
    """True when this override is AUDITED but must not fail the job
    (D-P1-12, "the third belt"): a code-channel key in a hosted PROJECT
    canonical's OWN tracked settings file. Auth keys are never observe-only,
    the server root is never observe-only, and a file whose bytes differ from
    the canonical's (one introduced inside the clone) is never observe-only.

    Why this arm exists rather than a blanket refusal: the only such file
    today is projects/baseball-bingo/.claude/settings.json (one key, `hooks`),
    present in dev and prod and cloned into every workspace; refusing it would
    take every job of a live public service down on the deploy. Claude Code
    also writes `permissions` into any <project>/.claude/settings.local.json
    when a session approves a tool. The arm is SIZED IN CODE
    (`OBSERVED_PROJECT_SETTINGS` + `OBSERVED_LOCAL_SETTINGS_KEYS`) and kept in
    step with the checkout by `test_project_settings_inventory`; a key a
    GitHub-canonical project acquires upstream is refused, not observed. The
    bingo row goes once its hook is retired through the bingo repo (plan §7
    row 11).
    """
    if key in SETTINGS_AUTH_KEYS:
        return False
    if canonical is None or _same_dir(canonical, settings.server_root):
        return False
    canonical = Path(canonical)
    sized = OBSERVED_PROJECT_SETTINGS.get((canonical.name, file_name), frozenset())
    if file_name == "settings.local.json":
        sized = sized | OBSERVED_LOCAL_SETTINGS_KEYS
    if key not in sized:
        return False
    return _matches_canonical(Path(cwd), file_name, canonical)


def _matches_canonical(cwd: Path, name: str, canonical: Path) -> bool:
    """<cwd>/.claude/<name> is byte-identical to the canonical's copy — its
    working-tree file, or its tracked HEAD blob (what a `git clone` carries)."""
    try:
        here = (cwd / ".claude" / name).read_bytes()
    except OSError:
        return False
    try:
        if here == (canonical / ".claude" / name).read_bytes():
            return True
    except OSError:
        pass
    try:
        res = subprocess.run(
            ["git", "-C", str(canonical), "show", f"HEAD:.claude/{name}"],
            capture_output=True, timeout=10, check=False)
    except (OSError, subprocess.SubprocessError):
        return False
    return res.returncode == 0 and res.stdout == here


def _same_dir(a: Path, b: Path) -> bool:
    try:
        return Path(a).resolve() == Path(b).resolve()
    except OSError:
        return False


async def _observe_settings_override(job_id: str, found: SettingsOverride, *,
                                     cwd: Path, project: str) -> None:
    """The observe arm: audit `settings_override_observed{key, file, project}`
    and DM once per project per UTC day (ops kind → delivered with the outbox
    switch on or off, D-P1-10). The day claim is SET NX only after
    `enqueue_notice` returned an id, so a dropped insert does not burn the
    day (the half A5 dropped; same shape as main._notify_schedule_deferral)."""
    audit_log.append(job_id, "settings_override_observed",
                     key=found.key, file=found.file, project=project,
                     path=str(Path(cwd) / ".claude"))
    logger.warning("settings_override observed (job runs): key=%s file=%s project=%s cwd=%s",
                   found.key, found.file, project, cwd)
    key = f"{KEY_SETTINGS_OVERRIDE_NOTIFIED_PREFIX}{project}:{datetime.now(timezone.utc):%Y-%m-%d}"
    try:
        if await redis.exists(key):
            return
        nid = await enqueue_notice(build_ops_notice(
            kind="settings_override", severity="warn",
            text=(f"⚠ settings override observed in project {project}: `{found.key}` in "
                  f".claude/{found.file} (its own tracked copy) — the job ran; retire or "
                  f"relocate it through the project's repo (plan §7 row 11), after which "
                  f"this arm refuses"),
            subject=f"job:{job_id}",
        ))
        if nid is not None:
            await redis.set(key, "1", nx=True, ex=TTL_SETTINGS_OVERRIDE_NOTIFIED)
    except Exception:  # noqa: BLE001 — the audit row is the record; a DM failure never fails the job
        logger.exception("settings_override notice failed for %s", job_id)


def _build_options(
    job: Job,
    cwd: Path,
    skill_cfg: SkillConfig | None,
    task_turns: list[dict] | None = None,
    *,
    canonical_cwd: Path | None = None,
    guard_workspace: Path | None = None,
    system_prompt: str | None = None,
) -> ClaudeAgentOptions:
    """Assemble ClaudeAgentOptions. Skill frontmatter wins over server defaults.

    guard_workspace: when set (workspace-tier), PreToolUse guard hooks are
    attached that contain the session to this path (INV-17).
    system_prompt: a prompt already assembled by `_build_system_prompt` (what
    `run_session` passes); None builds it here — identical bytes either way.
    """
    # System prompt — context-aware preamble + skill body + task context
    if system_prompt is None:
        system_prompt = _build_system_prompt(
            job, cwd, skill_cfg, task_turns, canonical_cwd=canonical_cwd)

    # Model + effort + permission + tools. Per-request overrides from
    # job.payload take precedence over skill frontmatter; the registry
    # validates the pick (T1) and hands the SDK the bare Anthropic id.
    payload = job.payload or {}
    model = _resolve_model(payload, skill_cfg).model_id

    effort = payload.get("effort") or (skill_cfg.effort if skill_cfg else "medium")
    permission_mode = payload.get("permission_mode") or (
        skill_cfg.permission_mode if skill_cfg else "acceptEdits"
    )
    tools = (skill_cfg.required_tools if skill_cfg else list(DEFAULT_REQUIRED_TOOLS))

    kwargs: dict[str, Any] = dict(
        cwd=str(cwd),
        system_prompt=system_prompt,
        allowed_tools=tools,
        permission_mode=permission_mode,
        setting_sources=["project"],   # picks up CLAUDE.md from cwd
        session_id=str(job.id),
        model=model,
    )
    effort_norm = agents_mod.normalize_effort(effort)
    if effort_norm and effort_norm != "medium":
        kwargs["effort"] = effort_norm  # SDK ladder: low | medium | high | xhigh | max
    if skill_cfg and skill_cfg.max_turns:
        kwargs["max_turns"] = skill_cfg.max_turns

    # In-session subagents (frontmatter `subagents:` → SDK agents=). The Task
    # tool is what dispatches to a subagent, so ensure it's allowed whenever
    # agents are present — otherwise a skill on a non-bypass permission mode
    # would get its delegations silently denied.
    if skill_cfg and skill_cfg.subagents:
        subs = agents_mod.build_subagents(skill_cfg, settings.default_model)
        if subs:
            kwargs["agents"] = subs
            if "Task" not in tools:
                tools = [*tools, "Task"]
                kwargs["allowed_tools"] = tools

    # Guard hooks — two profiles (runner/guards.py):
    #   read-only (skill declares privilege_class: read-only — oversight
    #   skills): file tools + restart_project denied outright, Bash mutation
    #   denylist; enqueue_job stays open. Attached in EVERY isolation tier
    #   and permission mode — a belt under plan, load-bearing under
    #   acceptEdits (dispatch-capable oversight skills must run acceptEdits
    #   because plan blocks the dispatch MCP; proven live 2026-07-30).
    #   workspace (workspace-tier writers, INV-17): contain writes to the
    #   clone + deny dangerous host commands, even under bypassPermissions.
    # A read-only skill should never also be workspace-tier (that tier exists
    # to contain WRITERS, and a read-only session has nothing to push); if
    # both somehow apply, read-only wins — it is strictly stronger (the
    # workspace profile would permit writes inside the clone, which a
    # read-only skill must never make).
    if skill_cfg is not None and skill_cfg.privilege_class == "read-only":
        kwargs["hooks"] = guards.make_readonly_guard_hooks(str(job.id))
    elif guard_workspace is not None:
        kwargs["hooks"] = guards.make_guard_hooks(str(job.id), guard_workspace)

    # ── MCP server injection ──────────────────────────────────────────
    # Skills opt in via "needs-projects-mcp" / "needs-dispatch-mcp" tags
    # in their SKILL.md frontmatter. Tags are the sole source of truth.
    mcp_servers: dict[str, Any] = {}
    skill_tags = skill_cfg.tags if skill_cfg else []

    if "needs-projects-mcp" in skill_tags:
        from src.runner.mcp_projects import create_server as create_projects_mcp
        mcp_servers["projects"] = create_projects_mcp()

    if "needs-dispatch-mcp" in skill_tags:
        from src.runner.mcp_dispatch import create_server as create_dispatch_mcp
        # Pass the job so dispatched children inherit task_id/parent_job_id
        mcp_servers["dispatch"] = create_dispatch_mcp(job)

    if mcp_servers:
        kwargs["mcp_servers"] = mcp_servers
        # Injected MCP tools must ALSO be in allowed_tools: acceptEdits
        # auto-accepts EDITS only, so an MCP call otherwise raises a
        # permission request no headless session can answer (proven live
        # 2026-07-31 — deploy-director's enqueue_job denied twice under
        # acceptEdits; dispatch had only ever worked under bypassPermissions,
        # which is why review-and-improve's dispatch stayed dead even after
        # its plan→acceptEdits fix). Same pattern as the Task auto-add above.
        # The readonly guard profile still hook-denies restart_project for
        # read-only skills — hooks fire before permission evaluation.
        mcp_tool_names: list[str] = []
        if "projects" in mcp_servers:
            mcp_tool_names += [
                "mcp__projects__list_projects",
                "mcp__projects__get_project",
                "mcp__projects__read_project_logs",
                "mcp__projects__restart_project",
            ]
        if "dispatch" in mcp_servers:
            mcp_tool_names.append("mcp__dispatch__enqueue_job")
        missing = [t for t in mcp_tool_names if t not in tools]
        if missing:
            tools = [*tools, *missing]
            kwargs["allowed_tools"] = tools

    # Effective-options one-liner (2026-09-03): the `job_started` audit event
    # records model/effort/isolation but NOT max_turns or permission_mode, so a
    # failure like `error_max_turns: Reached maximum number of turns (N)` gives
    # no trace of what the SDK was actually configured with. This surfaces the
    # four knobs that most often explain SDK-side terminations for a session
    # (e.g. _writeback job f6c9e375 on 2026-09-01 hit max_turns=6 while
    # SKILL.md declared 10 — the load-time state was invisible in the log).
    logger.info(
        "session options resolved: job=%s skill=%s model=%s effort=%s "
        "max_turns=%s permission_mode=%s",
        str(job.id)[:8],
        (skill_cfg.name if skill_cfg else "<generic>"),
        kwargs.get("model"),
        kwargs.get("effort", "medium"),
        kwargs.get("max_turns"),
        kwargs.get("permission_mode"),
    )

    # SDK transport buffer ceiling (2026-10-10): the SDK's subprocess_cli
    # transport buffers each JSON message from the bundled Claude CLI in
    # memory before yielding it, and its default is 1 MiB (see
    # `claude_agent_sdk/_internal/transport/subprocess_cli.py`
    # `_DEFAULT_MAX_BUFFER_SIZE = 1024 * 1024`). Three recent long-running
    # sessions overflowed that cap and died with
    # `JSON message exceeded maximum buffer size of 1048576 bytes`:
    #   8d848d17-2df7-4e41-9de6-9d0f504d69b5  (alpha-governor)
    #   4bce7355-59a1-415e-8c6b-5822543b8b13  (alpha-governor)
    #   3c7c8c56-a580-4e26-a048-e1e7845bbb67  (alpha-research)
    # Raising to 20 MiB keeps us well above typical ToolResult payloads
    # without unbounded growth. `setdefault` so a payload or skill override
    # (none today) can still tighten or widen per-session.
    kwargs.setdefault("max_buffer_size", 20 * 1024 * 1024)

    # E7 (spec §2.4/§3): error reports + operational metrics off for every
    # session. The SDK overlays this dict on os.environ.
    kwargs["env"] = {**(kwargs.get("env") or {}), **claude_subprocess_env()}

    return ClaudeAgentOptions(**kwargs)


async def _project_slug(job: Job) -> str | None:
    """The project slug this job is scoped to (from project_id or payload), or None."""
    if job.project_id:
        async with async_session() as s:
            project = await s.get(Project, job.project_id)
            if project:
                return project.slug
    slug = (job.payload or {}).get("project_slug")
    return slug or None


async def _resolve_project(
    job: Job, skill_name: str | None = None,
) -> tuple[Path, "Any", bool, str | None]:
    """Resolve the session's working dir honoring the delivery contract.

    Returns (cwd, delivery_or_None, is_deploy, slug). For `topology: dev-repo`,
    a non-deploy session is scoped to the canonical dev repo (the separate git
    thread) instead of the runtime clone. Deploy jobs, in-place, content, and
    legacy (no delivery block) all resolve to the runtime clone / server root —
    so this is behavior-preserving until a project opts in with a dev-repo block.
    """
    slug = await _project_slug(job)
    if not slug:
        return settings.server_root, None, False, None
    runtime = settings.projects_dir / slug
    if not runtime.exists():
        return settings.server_root, None, False, slug
    manifest = delivery.load_project_manifest(slug)
    deliv = manifest.delivery if manifest else None
    is_deploy = delivery.is_deploy_skill(
        skill_name if skill_name is not None else job.kind, deliv)
    cwd, _scoped = delivery.resolve_delivery_cwd(runtime, deliv, is_deploy)
    return cwd, deliv, is_deploy, slug


async def _resolve_cwd(job: Job, skill_name: str | None = None) -> Path:
    """Working directory for the session (delivery-contract aware)."""
    cwd, _deliv, _is_deploy, _slug = await _resolve_project(job, skill_name)
    return cwd


# ── Main entry ──────────────────────────────────────────────────────────────


async def run_session(job: Job) -> dict[str, Any]:
    job_id = str(job.id)
    skill_name, skill_cfg = await _resolve_skill(job)

    # Model/provider validation — before the deploy gate, the workspace clone
    # and any process, so an unknown or disabled provider never leaves a
    # clone behind or reaches the SDK (T1, 2026-10-21; C12 fail-closed).
    # `_build_options` resolves again for the value; this call is the gate.
    # `ProviderRefused` is terminal in main._process_job, not escalated.
    model_ref, model_reason = resolve_model_choice(job.payload, skill_cfg)
    provider = model_ref.provider
    audit_log.append(job_id, "provider_selected",
                     provider=provider, model=model_ref.model_id, reason=model_reason)

    canonical_cwd, deliv, is_deploy, slug = await _resolve_project(job, skill_name)

    # Deploy-authority gate (delivery contract) — before any work, so a
    # contract violation never spins up a session. Raised exceptions are
    # handled in main._process_job (terminal; no escalation of a policy refusal).
    if is_deploy and deliv is not None:
        trigger = delivery.classify_trigger(job.created_by)
        verdict = delivery.deploy_permitted(deliv, trigger)
        audit_log.append(job_id, "deploy_authority",
                         decision=verdict.decision.value, reason=verdict.reason,
                         autonomy=deliv.deploy.autonomy, trigger=trigger, slug=slug)
        if verdict.decision is delivery.DeployDecision.refuse:
            raise delivery.DeployRefused(verdict.reason)
        if verdict.decision is delivery.DeployDecision.needs_approval:
            raise delivery.DeployNeedsApproval(verdict.reason)

    if slug:
        audit_log.append(job_id, "project_cwd_resolved", slug=slug,
                         topology=(deliv.topology if deliv else "legacy"),
                         cwd=str(canonical_cwd), is_deploy=is_deploy,
                         scoped_to_dev_repo=(deliv is not None
                                             and deliv.topology == "dev-repo"
                                             and not is_deploy
                                             and str(canonical_cwd) != str(settings.projects_dir / slug)))

    # Task turns for multi-turn context — fetched here (async) instead of the
    # old nested-event-loop hack. A failure is logged loudly: losing the task
    # conversation silently is the worst failure mode for a continuation job.
    task_turns: list[dict] = []
    if job.task_id:
        try:
            task_turns = await _fetch_task_turns(job.task_id)
        except Exception:
            logger.exception("task-turn fetch failed for job %s — continuing WITHOUT "
                             "task context (continuation may lose the plan)", job_id[:8])
            audit_log.append(job_id, "task_context_load_failed")

    # ── Isolation tier resolution + workspace ───────────────────────────
    isolation = workspaces.resolve_isolation(
        skill_cfg.isolation if skill_cfg else None,
        (job.payload or {}).get("isolation"),
    )
    # Generic unmatched task: no skill body, full default toolset — the one
    # session shape with no contract at all. Force the guarded workspace tier
    # so it gets a throwaway clone + PreToolUse denylist instead of an
    # unlabeled host session (2026-08-31, EVALUATION_2026-08-30 F1.5).
    # Owner-driven host work goes through /god, which keeps a skill contract.
    if skill_cfg is None and isolation != "workspace":
        audit_log.append(job_id, "isolation_forced",
                         from_tier=isolation, to_tier="workspace",
                         reason="generic task has no skill contract")
        isolation = "workspace"

    # Non-Anthropic lane rules (T4, 2026-10-21) — fail closed, here, so a
    # refused job never leaves a clone behind and no process ever starts.
    # `ProviderRefused` is terminal in main._process_job (audit
    # `provider_refused` + `job_failed error_category=provider_refused`).
    refusal = lane_refusal(
        model_ref, skill_name=skill_name, skill_cfg=skill_cfg, isolation=isolation,
        payload=job.payload, created_by=job.created_by,
        code_server_providers=code_server_providers())
    if refusal is not None:
        raise models_registry.ProviderRefused(
            model_ref.canonical, refusal,
            provider=provider, model_id=model_ref.model_id)
    is_anthropic = provider == models_registry.DEFAULT_PROVIDER
    canonical_why = canonical_refusal(
        canonical_cwd, slug=slug, provider=provider,
        code_server_providers=code_server_providers(),
        server_root=settings.server_root, projects_dir=settings.projects_dir)
    if canonical_why is not None:
        # D-A: this repo is off-limits to non-Anthropic writers unless the
        # owner lists the provider in ROUTER_CODE_SERVER_PROVIDERS — by
        # canonical PATH, not only by skill name (T5 review round 1).
        raise models_registry.ProviderRefused(
            model_ref.canonical, canonical_why,
            provider=provider, model_id=model_ref.model_id)
    if not is_anthropic and not workspaces.is_git_repo(canonical_cwd):
        # The pre-push gate (T5) diffs and commits in a git clone; a copied
        # non-git canonical has no diff to review and no publish path, so
        # the lane cannot be made safe — refuse before the copy exists.
        raise models_registry.ProviderRefused(
            model_ref.canonical,
            f"the {provider} lane needs a git canonical for the pre-push "
            f"review gate; {canonical_cwd} is not a git checkout",
            provider=provider, model_id=model_ref.model_id)

    ws: workspaces.Workspace | None = None
    base_sha: str | None = None
    cwd = canonical_cwd
    if isolation == "workspace":
        try:
            ws = workspaces.create_workspace(job_id, canonical_cwd, settings.workspaces_dir)
            cwd = ws.path
            # Manifest-declared gitignored secrets (delivery.env_files) — a
            # clone doesn't carry them, so owner-provisioned credentials
            # (e.g. atlas's Alpaca keys) must be copied in explicitly.
            # NEVER for a non-Anthropic executor (plan §6; old spec §2.6):
            # its scrubbed env and Seatbelt are the containment, and a
            # vendor process must not find broker keys in its clone.
            env_files_copied: list[str] = []
            if is_anthropic and deliv is not None and deliv.env_files:
                env_files_copied = workspaces.provision_env_files(
                    ws.path, canonical_cwd, deliv.env_files)
            if not is_anthropic:
                # The base the pre-push gate diffs against (T5). Recorded
                # before any process runs; a missing base fails the gate
                # closed (`review.diff_for_gate` raises).
                base_sha = workspaces.head_sha(ws.path)
            audit_log.append(job_id, "workspace_created",
                             workspace=str(ws.path), canonical=str(canonical_cwd),
                             isolation=isolation, env_files=env_files_copied,
                             base_sha=base_sha)
        except Exception as exc:
            # Fail CLOSED. Guard hooks are keyed to the workspace path, so a
            # workspace-tier skill that can't get its clone would otherwise run
            # in the live canonical checkout with its own permission mode
            # (bypassPermissions for the patch skills) and NO containment —
            # the exact hole INV-17 exists to close. Failing the job hands it
            # to the escalation chain instead of degrading silently.
            logger.error("workspace creation failed for %s — FAILING the job "
                         "(workspace-tier requires containment): %s", job_id[:8], exc)
            audit_log.append(job_id, "workspace_failed", error=str(exc)[:300])
            raise RuntimeError(
                f"workspace creation failed for a workspace-tier job: {exc}"
            ) from exc

    # INV-3's third enforcement point (E1; spec §6): the clone — or the
    # canonical itself for isolation:none — is what setting_sources=["project"]
    # loads, so its .claude/settings*.json is checked HERE, after the clone
    # exists and before the SDK sees it. Anthropic lane only: the executor
    # lane runs with a scrubbed env and its own sandbox and never reads these
    # files. canonical_cwd goes in unconditionally — the allowance is keyed
    # on provenance, and the `if ws else None` form would refuse every
    # isolation:none skill at the server root.
    if is_anthropic:
        found = settings_override(Path(cwd), canonical=canonical_cwd)
        if found is not None:
            if found.observed_only:
                await _observe_settings_override(
                    job_id, found, cwd=Path(cwd),
                    project=slug or found.project or Path(canonical_cwd).name)
            else:
                # The clone is the evidence: keep it (as a failed session's
                # clone is kept) and say so, so a refused job never leaves an
                # unaudited directory under volumes/workspaces.
                if ws is not None:
                    workspaces.cleanup_workspace(ws, keep=True)
                    audit_log.append(job_id, "note",
                                     text=f"workspace kept for forensics after a "
                                          f"settings_override refusal: {ws.path}")
                raise SettingsOverrideRefused(
                    found, path=Path(cwd) / ".claude", provider=provider,
                    model_id=model_ref.model_id,
                    raw=str((job.payload or {}).get("model") or model_ref.model_id))

    # One system prompt for every executor (T4); the SDK path wraps it in
    # ClaudeAgentOptions exactly as before, the CLI path prepends it to the
    # task text (plan §4h).
    system_prompt = _build_system_prompt(
        job, cwd, skill_cfg, task_turns,
        canonical_cwd=canonical_cwd if ws else None,
    )
    options: ClaudeAgentOptions | None = None
    if is_anthropic:
        options = _build_options(
            job, cwd, skill_cfg, task_turns,
            canonical_cwd=canonical_cwd if ws else None,
            guard_workspace=ws.path if ws else None,
            system_prompt=system_prompt,
        )
        model_used = options.model or ""
    else:
        model_used = model_ref.model_id

    # Log context budget usage (Rec 8)
    ctx_tokens, ctx_budget, ctx_fraction = context_budget_fraction(
        system_prompt or "", model_used,
    )
    audit_log.append(
        job_id,
        "context_budget_used",
        estimated_tokens=ctx_tokens,
        model_budget=ctx_budget,
        fraction=round(ctx_fraction, 4),
        skill=skill_name,
    )

    # Record what was actually resolved, for the auto-tuning loop
    effort_used = (
        (job.payload or {}).get("effort")
        or (skill_cfg.effort if skill_cfg else "medium")
    )
    from sqlalchemy import update as sql_update
    async with async_session() as s:
        await s.execute(
            sql_update(Job).where(Job.id == job.id).values(
                resolved_skill=skill_name or None,
                resolved_model=model_used,
                resolved_effort=effort_used,
                resolved_provider=provider,
            )
        )
        await s.commit()

    audit_log.append(
        job_id,
        "job_started",
        description=job.description,
        job_kind=job.kind,
        skill=skill_name,
        cwd=str(cwd),
        model=model_used,
        effort=effort_used,
        isolation=isolation,
        provider=provider,
        payload=job.payload,
        parent_job_id=str(job.parent_job_id) if job.parent_job_id else None,
    )

    started_at = datetime.now(timezone.utc)
    session_failed = False
    model_served: str | None = None
    terminal_reason = "ok"
    review_outcome: str | None = None
    published = False
    capture: ResultCapture | None = None
    columns: dict[str, Any]
    by_model: dict[str, dict[str, Any]] | None = None

    try:
        if options is not None:
            final_summary, usage, capture = await _run_in_process(
                job_id, job.description, options)
            model_served = capture.model_served
            # Typed reason from the ResultMessage (B2); the banner belt and
            # the enforcement / silent-empty checks raised inside
            # _run_in_process, so a value here is a finished session.
            terminal_reason = derive_terminal_reason(capture)
            # cost_usd_list is OUR number, from tokens, each cache-write
            # bucket at its own rate (spec §2.8: "exactly one definition …
            # in src/runner/pricing.py"). The served model is what was
            # billed; the requested id is the fallback for the shapes where
            # model_usage is absent. None when the id is unknown to the price
            # table — the reconcile reports it as `unpriced`, never as $0.
            # Per model first (2026-10-28): `usage` is one aggregate across
            # every model the session touched, so a multi-model session is
            # priced from its `model_usage` breakdown when that breakdown
            # covers the aggregate; otherwise the aggregate at the served
            # model, as before.
            by_model = capture.usage_by_model or None
            cost_usd_list = pricing.price_model_usage(by_model, aggregate=usage)
            if cost_usd_list is None:
                cost_usd_list = pricing.price_usage(capture.model_served or model_used, usage)
            columns = result_columns(capture, terminal_reason=terminal_reason,
                                     cost_usd_list=cost_usd_list,
                                     cli_version=cli_version())
        else:
            final_summary, usage, model_served, lane_cli_version = await _run_executor(
                job, model_ref, cwd=cwd, system_prompt=system_prompt, skill_cfg=skill_cfg)
            # The executor lane keeps "ok" / ExecutorFailed as its terminal
            # reason (ExecResult.terminal_reason, never derive_terminal_reason).
            # Token columns through the same `usage_columns` as the Anthropic
            # lane (the mapped SDK key names), `cli_version` is the Codex CLI's;
            # `price_usage` is None for a non-Anthropic id (no Codex price
            # table in Phase 1); num_turns / duration_api_ms / sdk_cost_usd
            # have no source on this lane and stay NULL.
            cost_usd_list = pricing.price_usage(model_served or model_used, usage)
            columns = dict(usage_columns(usage),
                           cli_version=cli_version_column(lane_cli_version),
                           cost_usd_list=cost_usd_list)
            # Pre-push Anthropic review gate (T5; INV-21(c)) — a RULE keyed
            # on the provider, not a switch: every non-Anthropic diff is
            # reviewed by Anthropic before the runner commits, pushes and
            # ff-syncs. Non-LGTM raises ReviewBlocked (clone kept, nothing
            # published); an empty diff skips the gate and the commit.
            if ws is not None:
                review_outcome, published = await _pre_push_gate(
                    job, model_ref, ws, base_sha=base_sha, skill_name=skill_name)

        # One stamp site for both lanes (B3): the migration-008 result
        # columns, written before `job_completed` so that, when the stamp
        # succeeds, the row and the JSONL agree (a refused stamp is audited
        # below and the terminal transition re-stamps the token/cost subset). main._finish_job re-stamps the token/cost subset
        # from the result dict on the terminal transition.
        # A finished job is never failed by its own bookkeeping: the first
        # real Codex job after the Phase-1 deploy (2026-10-28, 0e09233d) did
        # its work and then died HERE on a varchar(24) overflow. The failure
        # is audited with its error; `job_completed` still follows, and
        # main._finish_job re-stamps the token/cost subset from the result
        # dict on the terminal transition (so a real DB outage still fails
        # the job loudly, one write later).
        try:
            async with async_session() as s:
                await s.execute(sql_update(Job).where(Job.id == job.id).values(**columns))
                await s.commit()
        except Exception as exc:  # noqa: BLE001
            logger.exception("post-session column stamp failed for %s (job goes on)",
                             job_id)
            audit_log.append(job_id, "result_stamp_failed", error=str(exc)[:500])

        if final_summary:
            audit_log.write_summary(job_id, final_summary)
            # Synthesize lifecycle events from text markers (P2) — executor-
            # agnostic replacement for sessions appending to the audit log
            # themselves. Deduped against events the session already wrote.
            try:
                existing_kinds = {e.get("kind") for e in audit_log.read(job_id)}
                for evt in extract_text_events(final_summary):
                    kind = evt.pop("kind")
                    if kind not in existing_kinds:
                        # E6: parsed from the RAW text (so markers still work),
                        # redacted before it lands in the trace.
                        audit_log.append(job_id, kind, **secret_redact.redact_tree(evt))
            except Exception:
                logger.exception("text-event extraction failed (non-fatal)")

        duration = (datetime.now(timezone.utc) - started_at).total_seconds()
        cost_usd_float = float(cost_usd_list) if cost_usd_list is not None else None
        audit_log.append(
            job_id,
            "job_completed",
            duration_seconds=duration,
            usage=usage,
            provider=provider,
            model_served=model_served,
            terminal_reason=terminal_reason,
            # B3 (additive, C14): both cost figures, both labelled — the
            # JSONL is where the reconcile script (B4) reads them, and
            # comparing one against the other is a Phase-1 exit criterion.
            # The executor lane has no turns / API time / SDK figure → None.
            num_turns=capture.num_turns if capture else None,
            duration_api_ms=capture.duration_api_ms if capture else None,
            cost_usd_list=cost_usd_float,
            sdk_cost_usd=capture.total_cost_usd if capture else None,
            stop_reason=capture.stop_reason if capture else None,
            # 2026-10-28 (additive): the per-model breakdown, so the ledger
            # can attribute a multi-model session — None on the executor lane.
            model_usage=by_model,
        )

        return {
            "summary": final_summary,
            "duration_seconds": duration,
            "usage": usage,
            "skill": skill_name,
            "isolation": isolation,
            "provider": provider,
            "model": model_used,
            "model_served": model_served,
            "terminal_reason": terminal_reason,
            "review_outcome": review_outcome,
            # B3: the two headline numbers (JSON-safe: this dict is
            # jobs.result). Phase-1 cards read num_turns from the row.
            "num_turns": capture.num_turns if capture else None,
            "cost_usd_list": cost_usd_float,
            # → jobs.result JSON: the breakdown persisted per job, no migration.
            "model_usage": by_model,
        }
    except BaseException:
        session_failed = True
        raise
    finally:
        if ws is not None:
            # ff-sync the canonical after the session pushed: the Anthropic
            # session pushes itself; on a non-Anthropic lane only the runner
            # pushes, and only after the gate's LGTM (`published`). A
            # non-LGTM, an empty diff or any failure never reaches here
            # with `published` set, so nothing un-reviewed is ever synced.
            if not session_failed and (is_anthropic or published):
                ok, msg = workspaces.sync_canonical(ws)
                audit_log.append(job_id, "workspace_synced", ok=ok, detail=msg)
                if not ok:
                    logger.warning("canonical sync failed for %s: %s", job_id[:8], msg)
            # Keep failed-job workspaces for debugging (a review-blocked
            # clone holds the un-pushed diff); server-upkeep prunes.
            workspaces.cleanup_workspace(ws, keep=session_failed)


async def _pre_push_gate(
    job: Job,
    ref: models_registry.ModelRef,
    ws: workspaces.Workspace,
    *,
    base_sha: str | None,
    skill_name: str | None,
) -> tuple[str | None, bool]:
    """The pre-push Anthropic review gate for non-Anthropic lanes (T5,
    2026-10-21; old spec §5.3 belt 3b; INV-21(c)). Returns
    `(review_outcome, published)`.

    Reads NO settings — there is no switch (round-1 critical #1).

    - `review.diff_for_gate(clone, base)` — committed + staged + unstaged +
      untracked; a git failure raises (fail closed, never "empty").
    - Empty diff → audit `merge_gate_skipped{reason=empty_diff}`, no
      reviewer, no commit; the job completes (research-class jobs).
    - Otherwise `review.run_code_review` (the fixed Anthropic reviewer)
      under `asyncio.wait_for(GATE_TIMEOUT_SECONDS)`; a timeout IS a
      `changes_requested` verdict. Audit `merge_gate_verdict{belt=pre_push,
      reviewer_provider, reviewer_model, verdict, findings_n, timed_out,
      diff_chars}`.
    - LGTM → `workspaces.publish_workspace` (runner commits with the
      `Executor:`/`Job:`/`Reviewed-By:` trailers and pushes; audit
      `workspace_published`); a failed publish raises RuntimeError (terminal
      on the lane, clone kept — never retried with a rebase, never forced).
    - Anything else → `ReviewBlocked` (terminal, clone kept, no sync).
    """
    job_id = str(job.id)
    diff = review.diff_for_gate(ws.path, base_sha)
    if not diff.strip():
        audit_log.append(job_id, "merge_gate_skipped", belt="pre_push",
                         reason="empty_diff", base_sha=base_sha)
        return None, False

    # Path deny list BEFORE a reviewer session is spent (review round 1;
    # old spec §5.3 belt 3b "a diff outside it is refused before the gate
    # runs"): settings/hooks, Codex + Claude instruction files, git
    # hook/config paths, CI workflows. Terminal like a `blocker` verdict —
    # clone kept, nothing committed, pushed or synced.
    refusal = review.gate_refusal(diff)
    if refusal is not None:
        reason, items = refusal
        if reason == "denied_path":
            audit_log.append(job_id, "merge_gate_refused", belt="pre_push",
                             reason=reason, paths=items,
                             diff_chars=len(diff), base_sha=base_sha)
        else:
            # A header the parser cannot read (git-quoted path): the deny
            # list was never applied to it, so fail closed (whole-branch
            # review, 2026-10-21).
            audit_log.append(job_id, "merge_gate_refused", belt="pre_push",
                             reason=reason, lines=[ln[:200] for ln in items],
                             diff_chars=len(diff), base_sha=base_sha)
        raise ReviewBlocked(ref.provider, ref.model_id,
                            verdict=review.ReviewOutcome.blocker.value,
                            findings_n=len(items), denied_paths=items,
                            refused_reason=reason, diff_chars=len(diff))

    # The reviewer truncates at `MAX_DIFF_CHARS` and would LGTM a diff it
    # only saw part of; for the GATE that would push unreviewed bytes to a
    # canonical repo (whole-branch review, 2026-10-21). Refuse instead —
    # the clone is kept for the owner, who can split the work.
    if len(diff) > review.MAX_DIFF_CHARS:
        audit_log.append(job_id, "merge_gate_refused", belt="pre_push",
                         reason="diff_too_large", diff_chars=len(diff),
                         max_chars=review.MAX_DIFF_CHARS, base_sha=base_sha)
        raise ReviewBlocked(ref.provider, ref.model_id,
                            verdict=review.ReviewOutcome.changes_requested.value,
                            refused_reason="diff_too_large", diff_chars=len(diff))

    timed_out = False
    try:
        outcome = await asyncio.wait_for(
            review.run_code_review(job_id, diff, ws.path),
            timeout=review.GATE_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        timed_out = True
        outcome = review.ReviewOutcome.changes_requested
        audit_log.append(job_id, "code_review_done", outcome=outcome.value,
                         review_text=f"Review timed out after "
                                     f"{review.GATE_TIMEOUT_SECONDS}s (gate: changes_requested)")

    done = [e for e in audit_log.read(job_id) if e.get("kind") == "code_review_done"]
    findings_n = review.count_findings((done[-1].get("review_text") if done else "") or "")
    verdict = outcome.value
    audit_log.append(
        job_id, "merge_gate_verdict", belt="pre_push",
        reviewer_provider=review.REVIEWER_PROVIDER, reviewer_model=review.REVIEWER_MODEL,
        verdict=verdict, findings_n=findings_n, timed_out=timed_out,
        diff_chars=len(diff), base_sha=base_sha,
    )
    if outcome is not review.ReviewOutcome.lgtm:
        raise ReviewBlocked(ref.provider, ref.model_id, verdict=verdict,
                            findings_n=findings_n, timed_out=timed_out)

    reviewer = f"{review.REVIEWER_PROVIDER}/{review.REVIEWER_MODEL}"
    # An empty/whitespace description is legal (web POST, schedule rows):
    # fall back to the job kind rather than IndexError after an LGTM.
    lines = (job.description or "").strip().splitlines()
    subject = (lines[0] if lines else job.kind)[:72]
    message = f"{skill_name or job.kind}: {subject}"
    trailers = workspaces.provenance_trailers(
        provider=ref.provider, model_id=ref.model_id, job_id=job_id, reviewer=reviewer)
    ok, detail, commit = workspaces.publish_workspace(
        ws, base_sha=base_sha, message=message, trailers=trailers)
    audit_log.append(job_id, "workspace_published", ok=ok, detail=detail,
                     commit=commit, trailers=trailers)
    if not ok:
        # Typed so the ledger can tell "reviewed, approved, push rejected"
        # from a vendor `api_error` (review round 1): main's ExecutorFailed
        # handler stamps `terminal_reason=publish_failed`, clone kept.
        raise ExecutorFailed(ref.provider, ref.model_id, "publish_failed",
                             f"publish after LGTM failed: {detail}")
    return verdict, True


async def _run_executor(
    job: Job,
    ref: models_registry.ModelRef,
    *,
    cwd: Path,
    system_prompt: str,
    skill_cfg: SkillConfig | None,
) -> tuple[str, dict[str, Any], str | None, str | None]:
    """The non-Anthropic execution path (T4): one CLI-executor process in the
    clone. Returns `(final_text, usage, model_served, cli_version)` on `ok`
    (`cli_version` is the vendor CLI's, stamped into `jobs.cli_version`
    by run_session — B3; it was dropped by the old 3-tuple); raises
    `ExecutorFailed` on any other terminal reason (terminal in main, never
    escalated). The executor audits/streams its own events (C14 kinds).
    """
    executor = executor_for(ref.provider)
    if executor is None:   # pragma: no cover — resolve_model_choice refused earlier
        raise models_registry.ProviderRefused(
            ref.canonical, f"no executor for provider {ref.provider!r} in this runner",
            provider=ref.provider, model_id=ref.model_id)
    # Sandbox: the configured default, tightened to read-only for read-only
    # skills (mirrors the SDK path's read-only guard profile). Never relaxed.
    sandbox = settings.codex_sandbox_default
    if skill_cfg is not None and skill_cfg.privilege_class == "read-only":
        sandbox = "read-only"
    # Strictly under the ceiling main._process_job's wait_for applies (which
    # started before the clone), so the executor's own `timeout` terminal
    # reason is reachable; main's deadline remains the backstop and its
    # cancellation terminates the child too (review round 1).
    # … minus the pre-push gate's allowance (reviewer ceiling + publish
    # margin): the gate runs AFTER the executor under the same `wait_for`,
    # so without the reserve a long run that produced a diff was cancelled
    # mid-review and mislabelled `timeout` (review round 1).
    ceiling = resolve_session_timeout(job.payload, settings.session_timeout_seconds)
    job_id = job.id if isinstance(job.id, str) else str(job.id)

    # Plan §4f — one credential, one stream (whole-branch review,
    # 2026-10-21): the per-executor slot serialises this provider's
    # processes. A wait is audited and comes OUT of the executor's budget
    # (main's `wait_for` ceiling started before the clone and does not
    # move), so the executor's own `timeout` reason stays reachable.
    executor_name = executor_name_for(ref.provider) or ref.provider
    slot = executor_slot(executor_name)
    loop = asyncio.get_running_loop()
    contended = slot.locked()          # a free slot costs the budget nothing
    wait_started = loop.time()
    try:
        async with slot:
            waited_s = (loop.time() - wait_started) if contended else 0.0
            if contended:
                audit_log.append(job_id, "executor_slot_wait", executor=executor_name,
                                 waited_s=round(waited_s, 2),
                                 concurrency=EXECUTOR_CONCURRENCY.get(executor_name, 1))
            timeout_s = executor_timeout_s(ceiling - waited_s, reserve_s=gate_reserve_s())
            result = await executor.run(
                job,
                cwd=cwd,
                prompt=build_executor_prompt(system_prompt, job.description),
                model_id=ref.model_id,
                sandbox=sandbox,
                timeout_s=timeout_s,
            )
    except (FileNotFoundError, ValueError) as exc:
        # Pre-process infrastructure failures (`CodexNotFound` is a
        # FileNotFoundError; a bad sandbox/prompt/cwd is a ValueError): no
        # child ever started, so there is no ExecResult — surface them on
        # the same terminal path as a vendor error instead of letting the
        # generic `except Exception` in main escalate onto an Anthropic
        # model (review round 1, 2026-10-21).
        audit_log.append(job_id, "executor_error", terminal_reason="api_error",
                         message=f"{type(exc).__name__}: {exc}"[:500])
        raise ExecutorFailed(ref.provider, ref.model_id, "api_error",
                             f"{type(exc).__name__}: {exc}") from exc
    if result.terminal_reason != "ok":
        raise ExecutorFailed(ref.provider, ref.model_id, result.terminal_reason,
                             result.error, model_served=result.model_served)
    return ((result.final_text or "").strip(), dict(result.usage or {}),
            result.model_served, result.cli_version)


async def _run_in_process(
    job_id: str, prompt: str, options: ClaudeAgentOptions
) -> tuple[str, dict[str, Any], ResultCapture]:
    """The in-process Agent SDK execution path (the Anthropic lane).
    Returns (final_text, usage, capture) — `capture` is the full typed
    ResultMessage (B2/B3), `usage` is kept for every existing consumer. Also
    collects the `error` category of every `SystemMessage(subtype="api_retry")`
    it sees (last one wins) and hands it to the capture / the raised error
    text, so an enforcement signal (account hold, revoked OAuth grant,
    billing) is classified the same way on the completed and failed paths
    (spec §2.4)."""
    final_text_chunks: list[str] = []
    usage: dict[str, Any] = {}
    capture = ResultCapture()
    api_retry_error: str | None = None      # last system/api_retry `error` category

    client = ClaudeSDKClient(options=options)
    _running_sessions[job_id] = client

    try:
        async with client:
            await client.query(prompt)

            async for message in client.receive_response():
                # system/api_retry carries `error ∈ {rate_limit, overloaded,
                # account_on_hold, oauth_org_not_allowed, billing_error,
                # authentication_failed}` + `attempt`. Recorded at the HEAD of
                # the loop body — before the RateLimitEvent branch, which can
                # `continue` or raise — so an enforcement signal is never lost
                # on the paths that never reach the ResultMessage. The audit
                # row carries the category and the attempt only, never the
                # message text (B3).
                if isinstance(message, SystemMessage) and message.subtype == "api_retry":
                    data = message.data if isinstance(message.data, dict) else {}
                    cat = str(data.get("error") or "").strip()
                    if cat:
                        api_retry_error = cat
                        audit_log.append(job_id, "api_retry", error=cat,
                                         attempt=data.get("attempt"))

                # Typed rate-limit signal — the CLI emits these on status
                # transitions; "rejected" means the current window is spent.
                if isinstance(message, RateLimitEvent):
                    info = message.rate_limit_info
                    audit_log.append(
                        job_id, "rate_limit_status",
                        status=getattr(info, "status", ""),
                        utilization=getattr(info, "utilization", None),
                        resets_at=getattr(info, "resets_at", None),
                        rate_limit_type=getattr(info, "rate_limit_type", None),
                    )
                    detected = quota.detect_from_rate_limit(info)
                    if detected is not None:
                        reset_at = detected if isinstance(detected, datetime) else None
                        # A3: only a reset time the vendor event carried is
                        # labelled "vendor"; a rejected status without
                        # `resets_at` falls back to the estimated window.
                        raise quota.QuotaExhausted(
                            reset_at,
                            reason=f"rate limit rejected "
                                   f"(window={getattr(info, 'rate_limit_type', '?')})",
                            source="vendor" if reset_at is not None else "estimated",
                        )
                    continue

                # Heuristic fallback: error text in any message shape
                err = getattr(message, "error", None)
                if err:
                    detected = quota.detect_quota_error(str(err))
                    if detected is not None:
                        reset_at = detected if isinstance(detected, datetime) else None
                        raise quota.QuotaExhausted(reset_at, reason=str(err)[:500],
                                                   source="estimated")

                await _handle_message(job_id, message, final_text_chunks)

                if isinstance(message, ResultMessage):
                    capture = capture_result_message(message, api_retry_error=api_retry_error)
                    usage = capture.usage
                    if capture.is_error:
                        err_text = capture.result_text or "; ".join(capture.errors)
                        detected = quota.detect_quota_error(err_text)
                        if detected is not None:
                            reset_at = detected if isinstance(detected, datetime) else None
                            raise quota.QuotaExhausted(reset_at, reason=err_text[:500],
                                                       source="estimated")
                        # Fail loudly when the session errored AND produced no
                        # usable text (parity with the removed container lane).
                        # The api_retry category rides in the text so
                        # terminal_reason_for_exception maps it (B2).
                        if not final_text_chunks:
                            raise RuntimeError(
                                f"session error ({capture.subtype}"
                                f"{f'; api_retry {api_retry_error}' if api_retry_error else ''}): "
                                f"{err_text[:500] or 'no output'}"
                            )

        summary_text = "\n".join(final_text_chunks).strip()

        # API-terminal shape check (2026-08-21): the SDK sometimes lets an
        # Anthropic-side 5xx / timeout through as a plain TextBlock + a
        # ResultMessage with all-zero usage and is_error unset — the branch
        # above never triggers, and the session records `completed` with
        # no real work. Classifying this as a failure engages the existing
        # escalation.on_failure retry (opus/xhigh) and the self-diagnose
        # chain. Job 143c8cfb (atlas-evaluate, 2026-08-17) proved the hole:
        # a 200s session whose summary was literally "API Error: 529
        # Overloaded. ..." → completed → atlas governor silently dark for
        # 10 days. See `is_api_terminal_session` above for the (deliberately
        # conservative) predicate: banner-shape AND empty usage both required.
        if is_api_terminal_session(summary_text, usage):
            raise RuntimeError(
                f"API terminal error (session produced no work): "
                f"{summary_text[:300]}"
            )

        # An enforcement signal is never an unknown model id: if the vendor
        # said account_on_hold / oauth_org_not_allowed / billing_error, the
        # session is that, and escalating to another model would burn the
        # escalation ladder against a suspended account (spec §2.4). Fail
        # with the category so terminal_reason_for_exception maps it. Phase 1
        # records the reason (A5's failed-job DM is the signal); the lane
        # hold and the provider_enforcement notice are Phase 3.
        if API_RETRY_TO_TERMINAL.get((api_retry_error or "").lower()) in ENFORCEMENT_CATEGORIES:
            raise RuntimeError(f"session error (api_retry {api_retry_error}): "
                               f"vendor enforcement — no retry")

        # Silent-empty-success trap (spec §2.4 / claude-anthropic.md §7): the
        # pinned CLI can return a 'success' with no text, zero usage and zero
        # API time for an id it does not know. Typed check beside the banner
        # regex above; fails the job so escalation (a known-good model)
        # engages instead of recording a completed no-op. Anthropic lane
        # only — the Codex executor already refuses "no turn.completed".
        violation = served_model_violation(capture, options.model or "",
                                           final_text=summary_text)
        if violation:
            audit_log.append(job_id, "job_result_rejected", reason="unrecognized_model",
                             detail=violation, requested_model=options.model)
            raise RuntimeError(f"unrecognized_model: silent empty success — {violation}")

        return summary_text, usage, capture
    finally:
        _running_sessions.pop(job_id, None)


# ── Message handler ─────────────────────────────────────────────────────────


async def _handle_message(
    job_id: str, message: Any, final_text_chunks: list[str]
) -> None:
    if isinstance(message, AssistantMessage):
        for block in message.content:
            if isinstance(block, TextBlock):
                # E6: the durable trace is redacted, ALWAYS; the result text
                # (final_text_chunks → job result / TASK_COMPLETE parser) is not.
                safe = secret_redact.redact(block.text)
                audit_log.append(job_id, "text", text=safe)
                final_text_chunks.append(block.text)
                await _publish_stream(job_id, {"kind": "text", "text": safe})
            elif isinstance(block, ToolUseBlock):
                audit_log.append(
                    job_id, "tool_use",
                    tool_name=block.name,
                    tool_use_id=block.id,
                    input=secret_redact.redact_tree(_truncate_for_log(block.input)),
                )
                await _publish_stream(
                    job_id,
                    {"kind": "tool_use", "tool_name": block.name, "tool_use_id": block.id},
                )
            elif isinstance(block, ThinkingBlock):
                audit_log.append(job_id, "thinking", text=secret_redact.redact(block.thinking))

    elif isinstance(message, UserMessage):
        for block in message.content:
            if isinstance(block, ToolResultBlock):
                audit_log.append(
                    job_id, "tool_result",
                    tool_use_id=block.tool_use_id,
                    is_error=bool(block.is_error),
                    # After truncation, so the pattern set sees whole lines.
                    result_preview=secret_redact.redact(_preview_text(block.content)),
                )


def _truncate_for_log(value: Any, limit: int = 2000) -> Any:
    if isinstance(value, str) and len(value) > limit:
        return value[:limit] + f"... [{len(value) - limit} chars truncated]"
    if isinstance(value, dict):
        return {k: _truncate_for_log(v, limit) for k, v in value.items()}
    if isinstance(value, list):
        return [_truncate_for_log(v, limit) for v in value[:20]]
    return value


def _preview_text(content: Any, limit: int = 500) -> str:
    try:
        s = content if isinstance(content, str) else json.dumps(content, default=str)
    except Exception:
        s = str(content)
    return s[:limit] + (f"... [{len(s) - limit} more]" if len(s) > limit else "")


async def _publish_stream(job_id: str, payload: dict[str, Any]) -> None:
    try:
        await redis.publish(f"{CHANNEL_JOB_STREAM}:{job_id}", json.dumps(payload))
    except Exception as exc:  # noqa: BLE001 — streaming is best-effort, but never silent
        logger.debug("stream publish failed for %s: %s", job_id[:8], exc)


async def publish_done(job_id: str, status: str, payload: dict[str, Any] | None = None) -> None:
    body = json.dumps({"status": status, **(payload or {})}, default=str)
    try:
        await redis.publish(f"{CHANNEL_JOB_DONE}:{job_id}", body)
    except Exception as exc:  # noqa: BLE001 — a lost done-notification is worth a log line
        logger.warning("done publish failed for %s: %s", job_id[:8], exc)
