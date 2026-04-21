"""
Append-only JSONL audit log per job. One file per job_id under volumes/audit_log/.

Why JSONL files, not a DB table:
- Grep-friendly. "What did Claude do on this job?" is `tail <file>`.
- Append-only is enforced by the filesystem, not by convention.
- No schema migrations when we add a new event kind.
- When future Claude reads audit logs to pick up context, it can `cat`/`head`/`tail` naturally.

Kinds used (keep this list honest — update when adding new kinds):
- job_started:      {"kind", "ts", "job_id", "description", "payload"}
- job_completed:    {"kind", "ts", "job_id", "result", "cost_usd", "duration_seconds"}
- job_failed:       {"kind", "ts", "job_id", "error"}
- job_cancelled:    {"kind", "ts", "job_id"}
- tool_use:         {"kind", "ts", "job_id", "tool_name", "tool_use_id", "input"}
- tool_result:      {"kind", "ts", "job_id", "tool_use_id", "is_error", "result_preview"}
- text:             {"kind", "ts", "job_id", "text"}             # assistant text blocks
- thinking:         {"kind", "ts", "job_id", "text"}             # only if thinking is on
- note:             {"kind", "ts", "job_id", "text"}             # runner-originated notes
- context_budget_used: {"kind", "ts", "job_id", "estimated_tokens", "model_budget", "fraction", "skill"}
- task_question:    {"kind", "ts", "job_id", "question"}           # skill asks user for input
- task_complete:    {"kind", "ts", "job_id", "summary"}            # skill declares work done
- task_choices:     {"kind", "ts", "job_id", "question", "options"} # skill presents structured choices as inline buttons

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
