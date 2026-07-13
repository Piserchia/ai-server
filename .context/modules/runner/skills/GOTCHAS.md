# Gotchas

> **What this file is for**: Non-obvious traps, unexpected behaviors, and things that look like they should work but don't.
>
> **When to add an entry here**: When a session hit a trap — something implicit, an ordering requirement, a race condition, an environment-specific behavior — that a future session should know about before making similar changes.
>
> Append entries newest-first. Each entry should include a date header,
> the symptom or pattern, the fix or approach, and (when possible) a
> reference to the audit log that led to the finding.
>
> This file is seeded empty. Claude sessions working in this module should
> append here when they learn something reusable (see `.context/PROTOCOL.md`).

<!-- Append entries below this marker. Do not delete the marker. -->
<!-- APPEND_ENTRIES_BELOW -->

## 2026-07-11 — Runner silently skips task execution during rapid redeploy cycles

When a new deployment lands while a task is already queued or in early execution, the runner may silently skip the task body — returning success with no output or side-effects. This happens because the runner's task dispatcher checks a "current deploy" version token at pickup time; if the token changed since enqueue, the task is dropped rather than retried. The symptom is a job that completes in under 5 seconds with no audit log entries beyond `task_start` and `task_end`. Fix: check `volumes/audit_log/<job_id>.jsonl` for missing intermediate events; if the gap between `task_start` and `task_end` is suspiciously short, a redeploy race is likely — re-submit the task after the deploy stabilises.

_Evidence: job `0651defb`_

## 2026-07-11 — Brainstorming clarifying questions get "Continue to next phase" hijacked

**Symptom**: User submits a task ("update baseball bingo to use lineup agent"), it
completes in ~51 seconds with no actual code changes, then a follow-up
auto-continued job silently works on a **completely unrelated plan** — usually
whatever plan is referenced in `MEMORY.md`. The task lands in `pending_approval`
with a summary that reads plausible but is about the wrong project. User
approves it. Nothing shipped.

**Root cause (two-part defect)**:

1. **`superpowers:brainstorming` skill asks a clarifying question and ends the
   turn without emitting a `task_question` audit event.** The runner's
   `_update_task_after_job` scans for `task_question | task_choices |
   task_complete` — sees none — and falls through to the *auto-continue* branch
   (main.py L676-L709). The task never enters `awaiting_user`, so the user
   never gets prompted to answer the clarifying question.

2. **The auto-continue sentinel is a fixed literal string** ("Continue to the
   next phase of the plan.") with no task context attached. When the next job
   fires, it reads `MEMORY.md`, `.context/INDEX.md`, and any plan documents,
   picks the most recently-touched plan (e.g. `docs/superpowers/plans/2026-07-10-eval-remediation.md`),
   and continues *that*. The bingo task, atlas task, or whatever the user
   actually asked for is silently swapped out.

**Evidence — 2026-07-11 baseball bingo**:
- Task `b59375a8` — user: "update and redeploy the baseball bingo generator to
  use an agent to pull lineup data".
- Job `137c27eb` — ran brainstorming, asked "Claude AI agent vs. data-fetching
  agent?", ended at 51s. Zero `task_question` events in audit log.
- Auto-continue `1681307a` — description "Continue to the next phase of the
  plan." — worked on the **eval-remediation Wave 1 PR (T4–T9)** instead. The
  bingo `.py` files were never opened, no commit on `projects/baseball-bingo`.
- Task marked `pending_approval`, user approved thinking bingo shipped, but
  `git log projects/baseball-bingo` stops at commit `699f427` (an earlier
  session's expand-event-pool work).

**Fix** (both required):

1. In `superpowers:brainstorming`, emit `task_question` (or `task_choices`)
   via the audit log immediately before asking a clarifying question. Then the
   task hits `awaiting_user` and the user's follow-up message routes back as a
   turn in the same task, not a fresh one.

2. In `_update_task_after_job` (runner/main.py L676), when auto-continuing,
   append the original task description to the sentinel (e.g. `"Continue to
   the next phase of the plan. Original task: <task.description>"`) — or
   better, pull the task's turn history into the continuation job's payload so
   the next session actually has the context.

**Sibling entry** — see the two `2026-07-09` entries below. Those are earlier
manifestations of the same defect family ("silent auto-continue loop"); this
2026-07-11 entry is the **task-hijack** variant where the loop *does* make
progress, just on the wrong plan.

_Evidence: tasks `b59375a8` (bingo) and `3bfb65aa` (bingo); jobs `137c27eb`,
`1681307a`, `2867bcd7`._

## 2026-07-09 — Missing task_complete signal causes silent auto-continue loop

When a job finishes its work but never emits a `task_complete` signal, the runner does not mark the job as done and instead re-enters the auto-continue handler on each polling cycle. This produces a silent loop that consumes turns without any visible error. Always ensure every code path in a skill or job handler reaches a `task_complete` (or equivalent terminal signal) before returning, and check the audit log for repeated `auto-continue` entries if a job appears to hang or spin.

_Evidence: job `426cfc49`_

## 2026-07-09 — Unmatched job descriptions trigger silent auto-continue chains

When a dispatched sub-agent's description string does not match any expected pattern in the runner's routing logic, the job may silently fall through to an auto-continue handler instead of failing loudly. This produces a chain of continuation turns that consume quota without making progress. Always verify that Agent tool `description` values match a known routing key, and check the audit log for repeated `auto-continue` entries if a job seems to loop without resolution.

_Evidence: job `5045d25b`_

## 2026-04-20 — System Python dependencies are not inherited by scripts

Scripts invoked as `python3 <script>` use the system Python 3.9 on this machine, which does **not** include user-level pip packages. The server has no `.venv/`; all runtime dependencies are installed into the user's pip path (`pip3 install`). When a script fails with `ModuleNotFoundError` for a package you know is installed, verify which Python is resolving the import (`which python3` vs the Python that owns the package). The fix is either `pip3 install <package>` under system python, or run the script with the correct interpreter explicitly.

_Evidence: job `78a4c95b`_

## 2026-04-20 — `audit_index.py` requires `pydantic-settings` via system python

**Symptom**: `PYTHONPATH=. python3 -m src.runner.audit_index` fails with `ModuleNotFoundError: No module named 'pydantic_settings'` when using system python3 (3.9).

**Root cause**: The server's Python dependencies are installed in the user's pip path (not a venv), and system python3 lacks `pydantic-settings`.

**Fix**: Run `pip3 install pydantic-settings` once, or use whichever python has the server deps. The server has no `.venv/` — deps are in user site-packages.

## 2026-04-20 — Restart grep false positives (updated)

**Pattern**: grep for `Starting\|Restarting\|restarted` in `volumes/logs/*.log` will match:
  - Telegram polling error messages containing "restarted" (bot.err.log)  
  - Application startup log lines like "Starting Crypto Dashboard" (project logs)
These are not actual process crashes. Always inspect matched lines before flagging restarts as anomalies.

## 2026-04-20 — `audit_log.append()` kind parameter collision

**Symptom**: Every job fails with `TypeError: append() got multiple values for argument 'kind'`. `volumes/audit_log/` is empty.

**Root cause**: `audit_log.append(job_id, kind, **fields)` uses `kind` as a positional param. Passing `kind=job.kind` as a keyword in `**fields` collides.

**Fix**: Use `job_kind=job.kind` instead of `kind=job.kind` in the `**fields` dict. Never name any keyword argument `kind` when calling `audit_log.append()`.

## 2026-04-20 — `_writeback` false positives from editor temp files

**Symptom**: `_writeback` child jobs spawn on every job, even chat.

**Root cause**: `_is_doc_path` in `writeback.py` doesn't recognize editor-generated files (`.DS_Store`, `__pycache__/`, `.ruff_cache/`). They show up in `git status` and trigger write-back verification.

**Fix**: Add patterns to `.gitignore` and `git rm -r --cached` the offending paths. Preferred fix is `.gitignore` — the files shouldn't be in git status at all.

## 2026-04-20 — Stuck jobs after runner crash

**Symptom**: Job stuck in `running` status forever. `SESSION_TIMEOUT_SECONDS` (1800s) didn't fire.

**Root cause**: Runner process died (crash, OOM, launchd restart) while a job was active. The timeout is in-process and dies with the runner.

**Fix**: `UPDATE jobs SET status = 'failed', error_message = 'runner crashed' WHERE status = 'running';` then restart runner.

## 2026-04-20 — SDK version mismatch / missing tools

**Symptom**: `tool_result` with `is_error: true` and "Tool not found" message immediately after `tool_use`.

**Root cause**: `claude-agent-sdk` version too old. Tools like `WebSearch`, `WebFetch` require >= 0.1.60.

**Fix**: `pipenv install "claude-agent-sdk>=0.1.60"` then restart runner. On Max 5x plan, all tools should be available.

## 2026-04-20 — `from src.runner import quota` extracts `runner` not `runner.quota`

**Symptom**: Module graph lint check reports undeclared imports.

**Root cause**: `from src.runner import quota` in AST gives `module = "src.runner"`, which maps to shorthand `runner`. But the declared dep is `runner.quota`. The lint check must handle package-level imports as covering their submodules.

**Fix**: In `check_module_graph_imports()`, when import target is a package prefix of any declared dep, skip the warning.
