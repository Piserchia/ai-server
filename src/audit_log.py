"""
Append-only JSONL audit log per job. One file per job_id under volumes/audit_log/.

Why JSONL files, not a DB table:
- Grep-friendly. "What did Claude do on this job?" is `tail <file>`.
- Append-only is enforced by the filesystem, not by convention.
- No schema migrations when we add a new event kind.
- When future Claude reads audit logs to pick up context, it can `cat`/`head`/`tail` naturally.

Kinds used (keep this list honest — update when adding new kinds):
- job_started:      {"kind", "ts", "job_id", "description", "payload"}  # + "provider" (additive, T4 2026-10-21)
- job_completed:    {"kind", "ts", "job_id", "duration_seconds", "usage"}  # usage = SDK token counts; no cost (subscription auth); + "provider", "model_served", "terminal_reason" (additive, T4)
- job_failed:       {"kind", "ts", "job_id", "error", "error_category"}  # category: quota|auth|timeout|…|skill_contract|deploy_refused|provider_refused|<executor terminal_reason: rate_limited|auth_expired|api_error|timeout|interrupted> (T4)
- provider_selected: {"kind", "ts", "job_id", "provider", "model", "reason"}  # which provider/model the job resolved to; reason ∈ payload|pin|default (T4, 2026-10-21)
- provider_refused: {"kind", "ts", "job_id", "provider", "model", "raw", "reason"}  # registry or lane rule refused `[provider/]model_id` before any clone or process (T1/T4, 2026-10-21)
- job_cancelled:    {"kind", "ts", "job_id"}
- tool_use:         {"kind", "ts", "job_id", "tool_name", "tool_use_id", "input"}
- tool_result:      {"kind", "ts", "job_id", "tool_use_id", "is_error", "result_preview"}  # + "exit_code", "output" from the Codex executor (additive, T3)
- text:             {"kind", "ts", "job_id", "text"}             # assistant text blocks
- thinking:         {"kind", "ts", "job_id", "text"}             # only if thinking is on
- note:             {"kind", "ts", "job_id", "text"}             # runner-originated notes
- context_budget_used: {"kind", "ts", "job_id", "estimated_tokens", "model_budget", "fraction", "skill"}
- task_question:    {"kind", "ts", "job_id", "question"}           # skill asks user for input
- task_complete:    {"kind", "ts", "job_id", "summary"}            # skill declares work done
- task_choices:     {"kind", "ts", "job_id", "question", "options"} # skill presents structured choices as inline buttons
- executor_started: {"kind", "ts", "job_id", "executor", "thread_id", "model", "cli_version", "env_keys"}  # non-Anthropic executor process started (T3, 2026-10-21)
- turn_completed:   {"kind", "ts", "job_id", "usage"}              # one vendor turn finished; usage in SDK key names (T3)
- executor_error:   {"kind", "ts", "job_id", "terminal_reason", "message"}  # vendor turn.failed/error, timeout or exit without turn.completed (T3)

Also writes a human-readable `<job_id>.summary.md` at job completion (written by the runner,
not here — it's the last turn the assistant produces).
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config import settings


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _log_path(job_id: uuid.UUID | str) -> Path:
    settings.audit_log_dir.mkdir(parents=True, exist_ok=True)
    return settings.audit_log_dir / f"{job_id}.jsonl"


def append(job_id: uuid.UUID | str, kind: str, **fields: Any) -> None:
    """Append a single event. Synchronous; filesystems are fast enough."""
    entry = {"ts": _now_iso(), "job_id": str(job_id), "kind": kind, **fields}
    with _log_path(job_id).open("a") as f:
        f.write(json.dumps(entry, default=str) + "\n")


def read(job_id: uuid.UUID | str, limit: int | None = None) -> list[dict]:
    """Read events for a job. Returns [] if no log exists yet."""
    path = _log_path(job_id)
    if not path.exists():
        return []
    entries: list[dict] = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    if limit is not None:
        return entries[-limit:]
    return entries


def summary_path(job_id: uuid.UUID | str) -> Path:
    return settings.audit_log_dir / f"{job_id}.summary.md"


def write_summary(job_id: uuid.UUID | str, text: str) -> None:
    """One-paragraph post-job summary. Overwrites; there is one summary per job."""
    p = summary_path(job_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
