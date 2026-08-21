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
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    RateLimitEvent,
    ResultMessage,
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
from src.registry.skills import SkillConfig, load as load_skill
from src.runner import agents as agents_mod
from src.runner import delivery, guards, quota, router, workspaces

logger = logging.getLogger(__name__)

# In-process registry of running sessions for /cancel.
_running_sessions: dict[str, ClaudeSDKClient] = {}


async def interrupt(job_id: str | uuid.UUID) -> bool:
    client = _running_sessions.get(str(job_id))
    if client is None:
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

# Approximate context windows by model family (input tokens).
_MODEL_BUDGETS: dict[str, int] = {
    "claude-haiku-4-5-20251001": 200_000,
    "claude-sonnet-4-6": 200_000,
    "claude-opus-4-7": 200_000,
}
_DEFAULT_BUDGET = 200_000


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


_USAGE_TOKEN_KEYS: tuple[str, ...] = (
    "input_tokens",
    "output_tokens",
    "cache_read_input_tokens",
    "cache_creation_input_tokens",
)


def usage_is_empty(usage: dict | None) -> bool:
    """True when a session's usage dict shows no real work.

    Pure function. Considers input / output / cache-read / cache-creation
    tokens; a real session (even a trivial one) consumes at least the
    system-prompt input, so all-zero across the four is the SDK's signature
    for "we never actually made it through a live Anthropic call". Missing
    or non-integer values count as zero (SDK versions vary).
    """
    if not usage:
        return True
    for key in _USAGE_TOKEN_KEYS:
        try:
            if int(usage.get(key) or 0) > 0:
                return False
        except (TypeError, ValueError):
            continue
    return True


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
            return matched, load_skill(matched)

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
            return llm_skill, load_skill(llm_skill)

        audit_log.append(str(job.id), "routing_decision",
                         method="fallback", skill="")
        return "", None   # generic task, use defaults + full tool set
    # Any other kind maps directly to a skill of the same name.
    # Underscores become dashes EXCEPT a leading underscore (marks internal skills):
    #   research_report → research-report
    #   _writeback      → _writeback   (leading _ preserved)
    skill_name = job.kind if job.kind.startswith("_") else job.kind.replace("_", "-")
    return skill_name, load_skill(skill_name)


def _build_options(
    job: Job,
    cwd: Path,
    skill_cfg: SkillConfig | None,
    task_turns: list[dict] | None = None,
    *,
    canonical_cwd: Path | None = None,
    guard_workspace: Path | None = None,
) -> ClaudeAgentOptions:
    """Assemble ClaudeAgentOptions. Skill frontmatter wins over server defaults.

    guard_workspace: when set (workspace-tier), PreToolUse guard hooks are
    attached that contain the session to this path (INV-17).
    """
    # System prompt — context-aware preamble + skill body + task context
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

    # Model + effort + permission + tools
    model = (skill_cfg.model if skill_cfg and skill_cfg.model else settings.default_model)

    # Per-request overrides from job.payload take precedence over skill frontmatter
    payload = job.payload or {}
    if payload.get("model"):
        model = payload["model"]

    effort = payload.get("effort") or (skill_cfg.effort if skill_cfg else "medium")
    permission_mode = payload.get("permission_mode") or (
        skill_cfg.permission_mode if skill_cfg else "acceptEdits"
    )
    tools = (skill_cfg.required_tools if skill_cfg else [
        "Read", "Write", "Edit", "Bash", "Glob", "Grep",
        "WebSearch", "WebFetch", "AskUserQuestion",
    ])

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

    ws: workspaces.Workspace | None = None
    cwd = canonical_cwd
    if isolation == "workspace":
        try:
            ws = workspaces.create_workspace(job_id, canonical_cwd, settings.workspaces_dir)
            cwd = ws.path
            # Manifest-declared gitignored secrets (delivery.env_files) — a
            # clone doesn't carry them, so owner-provisioned credentials
            # (e.g. atlas's Alpaca keys) must be copied in explicitly.
            env_files_copied: list[str] = []
            if deliv is not None and deliv.env_files:
                env_files_copied = workspaces.provision_env_files(
                    ws.path, canonical_cwd, deliv.env_files)
            audit_log.append(job_id, "workspace_created",
                             workspace=str(ws.path), canonical=str(canonical_cwd),
                             isolation=isolation, env_files=env_files_copied)
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

    options = _build_options(
        job, cwd, skill_cfg, task_turns,
        canonical_cwd=canonical_cwd if ws else None,
        guard_workspace=ws.path if ws else None,
    )

    # Log context budget usage (Rec 8)
    ctx_tokens, ctx_budget, ctx_fraction = context_budget_fraction(
        options.system_prompt or "", options.model or "",
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
                resolved_model=options.model,
                resolved_effort=effort_used,
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
        model=options.model,
        effort=effort_used,
        isolation=isolation,
        payload=job.payload,
        parent_job_id=str(job.parent_job_id) if job.parent_job_id else None,
    )

    started_at = datetime.now(timezone.utc)
    session_failed = False

    try:
        final_summary, usage = await _run_in_process(job_id, job.description, options)

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
                        audit_log.append(job_id, kind, **evt)
            except Exception:
                logger.exception("text-event extraction failed (non-fatal)")

        duration = (datetime.now(timezone.utc) - started_at).total_seconds()
        audit_log.append(
            job_id,
            "job_completed",
            duration_seconds=duration,
            usage=usage,
        )

        return {
            "summary": final_summary,
            "duration_seconds": duration,
            "usage": usage,
            "skill": skill_name,
            "isolation": isolation,
        }
    except BaseException:
        session_failed = True
        raise
    finally:
        if ws is not None:
            if not session_failed:
                ok, msg = workspaces.sync_canonical(ws)
                audit_log.append(job_id, "workspace_synced", ok=ok, detail=msg)
                if not ok:
                    logger.warning("canonical sync failed for %s: %s", job_id[:8], msg)
            # Keep failed-job workspaces for debugging; server-upkeep prunes.
            workspaces.cleanup_workspace(ws, keep=session_failed)


async def _run_in_process(
    job_id: str, prompt: str, options: ClaudeAgentOptions
) -> tuple[str, dict[str, Any]]:
    """The in-process Agent SDK execution path (the only execution path)."""
    final_text_chunks: list[str] = []
    usage: dict[str, Any] = {}

    client = ClaudeSDKClient(options=options)
    _running_sessions[job_id] = client

    try:
        async with client:
            await client.query(prompt)

            async for message in client.receive_response():
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
                        raise quota.QuotaExhausted(
                            reset_at,
                            reason=f"rate limit rejected "
                                   f"(window={getattr(info, 'rate_limit_type', '?')})",
                        )
                    continue

                # Heuristic fallback: error text in any message shape
                err = getattr(message, "error", None)
                if err:
                    detected = quota.detect_quota_error(str(err))
                    if detected is not None:
                        reset_at = detected if isinstance(detected, datetime) else None
                        raise quota.QuotaExhausted(reset_at, reason=str(err)[:500])

                await _handle_message(job_id, message, final_text_chunks)

                if isinstance(message, ResultMessage):
                    usage = getattr(message, "usage", {}) or {}
                    if message.is_error:
                        err_text = (message.result or "") or "; ".join(
                            getattr(message, "errors", None) or [])
                        detected = quota.detect_quota_error(err_text)
                        if detected is not None:
                            reset_at = detected if isinstance(detected, datetime) else None
                            raise quota.QuotaExhausted(reset_at, reason=err_text[:500])
                        # Fail loudly when the session errored AND produced no
                        # usable text (parity with the removed container lane).
                        if not final_text_chunks:
                            raise RuntimeError(
                                f"session error ({message.subtype}): "
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

        return summary_text, usage
    finally:
        _running_sessions.pop(job_id, None)


# ── Message handler ─────────────────────────────────────────────────────────


async def _handle_message(
    job_id: str, message: Any, final_text_chunks: list[str]
) -> None:
    if isinstance(message, AssistantMessage):
        for block in message.content:
            if isinstance(block, TextBlock):
                audit_log.append(job_id, "text", text=block.text)
                final_text_chunks.append(block.text)
                await _publish_stream(job_id, {"kind": "text", "text": block.text})
            elif isinstance(block, ToolUseBlock):
                audit_log.append(
                    job_id, "tool_use",
                    tool_name=block.name,
                    tool_use_id=block.id,
                    input=_truncate_for_log(block.input),
                )
                await _publish_stream(
                    job_id,
                    {"kind": "tool_use", "tool_name": block.name, "tool_use_id": block.id},
                )
            elif isinstance(block, ThinkingBlock):
                audit_log.append(job_id, "thinking", text=block.thinking)

    elif isinstance(message, UserMessage):
        for block in message.content:
            if isinstance(block, ToolResultBlock):
                audit_log.append(
                    job_id, "tool_result",
                    tool_use_id=block.tool_use_id,
                    is_error=bool(block.is_error),
                    result_preview=_preview_text(block.content),
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
