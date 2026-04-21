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
