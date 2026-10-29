"""
Append-only JSONL audit log per job. One file per job_id under volumes/audit_log/.

Why JSONL files, not a DB table:
- Grep-friendly. "What did Claude do on this job?" is `tail <file>`.
- Append-only is enforced by the filesystem, not by convention.
- No schema migrations when we add a new event kind.
- When future Claude reads audit logs to pick up context, it can `cat`/`head`/`tail` naturally.

Kinds used (keep this list honest — update when adding new kinds):
- job_started:      {"kind", "ts", "job_id", "description", "payload"}  # + "provider" (additive, T4 2026-10-21)
- job_completed:    {"kind", "ts", "job_id", "duration_seconds", "usage"}  # usage = SDK token counts; no bill (subscription auth); + "provider", "model_served", "terminal_reason" (additive, T4); + "num_turns", "duration_api_ms", "cost_usd_list" (the runner's list-price figure, pricing.price_usage), "sdk_cost_usd" (the SDK's own), "stop_reason" (additive, B3 2026-10-21; all five None on the executor lane — no turns / API time / SDK figure / Codex price table there; the reconcile script reads both cost figures here); + "model_usage" (additive, 2026-10-28: the per-model token breakdown `{<model id>: {input_tokens, output_tokens, cache_read_input_tokens, cache_creation_input_tokens[, sdk_cost_usd]}}` normalised by result_capture.usage_by_model — None on the executor lane; the reconcile prices a job per model from it when the breakdown covers `usage` (in the bundled CLI it is a superset: subagent and utility calls are in modelUsage but not in usage)
- job_failed:       {"kind", "ts", "job_id", "error", "error_category"}  # + "terminal_reason" on every branch (additive, A2 2026-10-21: error|timeout|api_error|provider_refused|review_blocked|<executor terminal_reason>); category: quota|auth|timeout|…|skill_contract|deploy_refused|provider_refused|review_blocked (T5)|<executor terminal_reason: rate_limited|auth_expired|api_error|timeout|interrupted (T4)|publish_failed (T5: LGTM but the runner's push was rejected)>
- result_stamp_failed: {"kind", "ts", "job_id", "error"}  # the post-session jobs-row column stamp (tokens/cost/cli_version, B3) raised; the session goes on to job_completed and the terminal transition re-stamps the token/cost subset from the result dict — a finished job is never failed by its own bookkeeping (2026-10-28, after a Codex job overflowed cli_version)
- provider_selected: {"kind", "ts", "job_id", "provider", "model", "reason"}  # which provider/model the job resolved to; reason ∈ payload|pin|default (T4, 2026-10-21)
- provider_refused: {"kind", "ts", "job_id", "provider", "model", "raw", "reason"}  # registry or lane rule refused `[provider/]model_id` before any clone or process (T1/T4, 2026-10-21); + "key", "file", "auth_key" (additive, E1 2026-10-29: reason=`settings_override:<key>` — a project-scope .claude/settings*.json carrying a refused key, raised after the clone and before the SDK; None on registry/lane refusals)
- settings_override_observed: {"kind", "ts", "job_id", "key", "file", "project", "path"}  # E1 / D-P1-12: a code-channel key in a hosted PROJECT canonical's OWN tracked settings file (today exactly baseball-bingo → hooks) — audited, DM'd once per project per day (ops notice `settings_override`), and the job RUNS; flips to refuse once the inventory is empty
- utility_model_usage: {"kind", "ts", "job_id": "utility", "call", "requested", "served_models"}  # E7 2026-10-29: a utility call (router | learning) was served by more than the requested model — spec §9 exit "model_usage on utility calls lists only the requested model"; logged + audited under the synthetic job id "utility", never fails the call (a persisting second family is the harness's own side request)
- api_retry:        {"kind", "ts", "job_id", "error", "attempt"}  # a system/api_retry message on the Anthropic lane; `error` is the vendor category (rate_limit|overloaded|account_on_hold|oauth_org_not_allowed|billing_error|authentication_failed) — never the message text (B3, 2026-10-21)
- job_result_rejected: {"kind", "ts", "job_id", "reason", "detail", "requested_model"}  # the session's ResultMessage was a silent empty success / served a different model than requested; reason = "unrecognized_model"; the job then fails with that terminal_reason (B3, 2026-10-21)
- job_cancelled:    {"kind", "ts", "job_id"}  # + "stage" (E3 2026-10-29, D-P1-4): running | button | telegram | api | cleared — the site that cancelled; every site writes status=cancelled, terminal_reason=interrupted, error_message="cancelled by user (<stage>)"
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
- workspace_created: {"kind", "ts", "job_id", "workspace", "canonical", "isolation", "env_files"}  # + "base_sha" (additive, T5: the clone's HEAD before the job on non-Anthropic lanes; None otherwise)
- merge_gate_verdict: {"kind", "ts", "job_id", "belt": "pre_push", "reviewer_provider", "reviewer_model", "verdict", "findings_n", "timed_out", "diff_chars", "base_sha"}  # pre-push Anthropic review of a non-Anthropic job's clone diff; verdict ∈ LGTM|changes_requested|blocker|error (T5, 2026-10-21)
- merge_gate_skipped: {"kind", "ts", "job_id", "belt": "pre_push", "reason": "empty_diff", "base_sha"}  # nothing to review — no reviewer, no commit, job completes (T5)
- merge_gate_refused: {"kind", "ts", "job_id", "belt": "pre_push", "reason": "denied_path", "paths", "diff_chars", "base_sha"}  # the diff touches `review.GATE_DENIED_*` paths (.claude/, .codex/, .git*/.github, AGENTS.md, CLAUDE.md, .mcp.json, any-depth .gitattributes) — refused BEFORE any reviewer ran; terminal like a blocker (T5 review round 1). Whole-branch review 2026-10-21 (additive): reason "unparseable_path" carries "lines" (git-quoted diff headers the deny list could not read; blocker) and reason "diff_too_large" carries "max_chars" (= review.MAX_DIFF_CHARS; verdict changes_requested — a partial review is never an LGTM)
- executor_slot_wait: {"kind", "ts", "job_id", "executor", "waited_s", "concurrency"}  # the job waited for its executor's per-credential slot (plan §4f, `session.EXECUTOR_CONCURRENCY`; codex = 1) before its process started; the wait came out of the executor's budget (whole-branch review, 2026-10-21)
- workspace_published: {"kind", "ts", "job_id", "ok", "detail", "commit", "trailers"}  # the RUNNER committed (Executor/Job/Reviewed-By trailers) + pushed the clone after LGTM; ok=false = push rejected, clone kept (T5)
- post_review_skipped: {"kind", "ts", "job_id", "reason", ...}  # reason ∈ stale_head|no_diff|timeout|pre_push_gate (+ "provider", "verdict" for pre_push_gate — the gate is the review of record on non-Anthropic lanes, T5)
- job_requeued_for_quota: {"kind", "ts", "job_id", "reason"}  # the job hit a rate limit and was LPUSHed to the FRONT (INV-12); + "provider", "until" when a NON-Anthropic executor's `rate_limited` paused that provider's lane (additive, T6 2026-10-21; absent on the Anthropic/global path)
- job_held:         {"kind", "ts", "job_id", "provider", "reason", "until"}  # the job's provider lane is paused: NOT run, requeued at the TAIL after a bounded delay (plan §4g); written once per (job, pause window), not on every cycle (T6)
- notice_queued:    {"kind", "ts", "job_id", "notice_id", "notice_kind"}  # an outbox row for this job was inserted `pending` (src/notify/outbox.py; A4 2026-10-21). job_id = the notice's subject; JSONL only, not mirrored to jobs:stream
- notice_sent:      {"kind", "ts", "job_id", "notice_id", "external_ref"}  # the row was delivered (external_ref = Telegram message_id) — by the bot listener, `drain`, or a direct `python -m src.notify send` (A4)
- notice_failed:    {"kind", "ts", "job_id", "notice_id", "error"}  # the row reached its terminal `failed` (MAX_ATTEMPTS, or a direct send that failed); error is token-free (TelegramSendError) and ≤ 200 chars (A4)

Schedule streams (D1, 2026-10-21) live in a SUBDIRECTORY,
`volumes/audit_log/schedules/<schedule_id>.jsonl`, written by
`append_schedule_event` — the top-level glob of `runner/audit_index.rebuild_index`
would otherwise index every stream as a job. The key is "schedule_id", not "job_id".
- schedule_deferred: {"kind", "ts", "schedule_id", "schedule", "reason": "provisioning_gap", "missing", "project", "env_file"}  # the scheduler's provisioning pre-check skipped a due row (no Job, clock advanced) because the project's canonical .env lacks `missing` (names only, never values); written on EVERY deferral, the DM once per project per UTC day (src/runner/main.py); counted out-of-band by scripts/schedule-monitor.sh and read by schedule_adherence (`deferred`, never DARK) and the bot's /status

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


# ── Schedule streams (D1) ───────────────────────────────────────────────────

SCHEDULES_SUBDIR = "schedules"


def schedule_log_path(schedule_id: uuid.UUID | str) -> Path:
    """`volumes/audit_log/schedules/<schedule_id>.jsonl` — a subdirectory on
    purpose: `audit_index.rebuild_index` globs the top level as job logs."""
    d = settings.audit_log_dir / SCHEDULES_SUBDIR
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{schedule_id}.jsonl"


def append_schedule_event(schedule_id: uuid.UUID | str, kind: str, **fields: Any) -> None:
    """Append one event to a schedule's stream. Synchronous, like `append`."""
    entry = {"ts": _now_iso(), "schedule_id": str(schedule_id), "kind": kind, **fields}
    with schedule_log_path(schedule_id).open("a") as f:
        f.write(json.dumps(entry, default=str) + "\n")


def read_schedule_events(schedule_id: uuid.UUID | str, limit: int | None = None) -> list[dict]:
    """Events of a schedule's stream, oldest first. [] when there is none."""
    path = settings.audit_log_dir / SCHEDULES_SUBDIR / f"{schedule_id}.jsonl"
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
    return entries[-limit:] if limit is not None else entries


def summary_path(job_id: uuid.UUID | str) -> Path:
    return settings.audit_log_dir / f"{job_id}.summary.md"


def write_summary(job_id: uuid.UUID | str, text: str) -> None:
    """One-paragraph post-job summary. Overwrites; there is one summary per job."""
    p = summary_path(job_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
