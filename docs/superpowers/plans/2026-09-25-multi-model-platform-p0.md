# Multi-Model Platform — Phase 0 (foundations + hygiene) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Re-cut 2026-09-25 against round 1 of the reviewed spec; round-2 delta applied 2026-09-27.** This plan was first drafted from the pre-review spec, then re-cut against the spec's **round-1** review log (rows #16, #17, #27, #28, #29, #31, #50, #51, #61, #64 and the window-labelling rule of #4 — round-1 numbering). The spec's **round 2** restarts its own numbering at #1 and has 58 rows; its P0-relevant rows (#2, #3, #4, #6, #8, #18, #19, #22, #28, #29, #32, #43, #48, #49, #50, #56, #58) were applied to this plan on **2026-09-27** — see "Alignment with the reviewed spec" (two tables, one per round) and the Verification log entry of that date. The authoritative P0 scope is the spec's §9 table row "P0" plus its test-gate and rollback paragraphs, the §12/§12a runbook rows that name P0, and every review-log row (either round) whose "What changed" cell names P0. **D1 approves P0–P1 only** (spec §12 D1, review r1 #51): P2 starts only after the owner reads the P1 retro.
>
> **Round-3 delta NOT yet applied to this plan (2026-09-27; spec Appendix B row "The first executable slice" is the authoritative list, and merging this re-cut is a P0 *entry* criterion in spec §9).** Round 3 verified that this plan's round-2 re-cut already landed — no `priority` column, settings refusal, audit redactor, `provisioning_gap` with `PROVISIONING_EXEMPT`, `WEB_AUTH_TOKEN` as a P0-entry row, trading tokens, R2 `--min-age 60d`, the 1-h ≈ $963 anchor, old open question 7 closed — so only these ten items remain: **(1)** add `jobs.sdk_cost_usd` and populate `cost_usd_list` from `src/runner/pricing.py`, not `capture.total_cost_usd` (`:1240`, `:1577`) — as written the P0 exit reconcile compares the SDK figure to itself, so nothing ever checks it against the 1-h computation; the criterion becomes "the two agree within 1 %, or the divergence is recorded with the rate the CLI uses"; **(2)** broaden the `.claude/settings*.json` check from auth keys to `hooks`/`permissions`/`mcpServers`/`enableAllProjectMcpServers`/`apiKeyHelper`/`env`, hash-pinned in `restraints.py`, refusing `provider_refused{reason: settings_override}`, plus `test_settings_no_hooks` over the two **tracked** files in this repo (`enabledPlugins` / `permissions` today); **(3)** add `scripts/install-dev-hooks.sh` (protected-path pre-commit guard keyed on `Approved-Protected-Path: ap-<id>`) + `test_protected_paths_hook`; **(4)** extend `terminal_reason` and `test_result_capture` with `account_on_hold`/`oauth_revoked`/`billing_error`, mapped from `system/api_retry`'s `error` category rather than an HTTP status; **(5)** write `SDK_RECORD` output to `volumes/sdk_recordings/<id>.json` (outside `volumes/audit_log/`, which three consumers glob with `*.jsonl`) and assert the flag is unset after the ≥20 recordings; **(6)** add the spec §14 Q2 Seatbelt probe (`sandbox.failIfUnavailable`/`strictAllowlist` on the pinned CLI); **(7)** remove `_check_idle_queue_review` + `_should_trigger_idle_review` + the `main` wiring **unconditionally** (it is the autonomous `server-patch` dispatcher, spec §2.6 (c)) and record that this leaves no retrospective loop until P4; **(8)** have Task 16 also print the weekly-allowance calibration from the `seven_day` utilization series (≈ $200/week working denominator) and the lane-budget seed table the P2 reader consumes, and paste one internally consistent per-model job-count set; **(9)** reconcile the Goal sentence's "every human-launched **and scheduled** job DMs on completion or failure" with spec §4.2's card-eligibility rule (`notify=failures`, the default for all 41 rows, gets only a FailedCard); **(10)** re-point owner-row citations to §12a 0, 1, 2, 2b, 4, 4b, 5, 6, 6b and add row 2b.

**Goal:** Make every job observable and every launch notified — tokens/cost/provider/terminal reason land in Postgres and a 30-day cost-reconcile script proves the cost view against the JSONL ledger; every human-launched and scheduled job DMs on completion or failure through a durable outbox that survives bot restarts while the legacy `tasks:notify`/`_job_to_chat` consumer stays wired (dual-write, `NOTIFY_OUTBOX=0` is a real switch); the four ghost Telegram commands become real, `/clear` asks first, `AskUserQuestion` leaves the default tool list; a daily credential canary proves the Keychain subscription login still serves through the runner's own SDK path with the runner's env; every Claude subprocess runs with error reporting and telemetry off; an opt-in raw SDK recorder (`SDK_RECORD=1`) accumulates the ≥20 real fixtures the P3 replay gate needs; the alembic chain gains the "every applied revision exists on disk" test and the rollback rule; and the owner gets a runbook for the DR/host hygiene debt and the §12a rows marked P0. The Haiku 4.5 retirement swap ships **ahead of P0** as a standalone `server-patch` (Task 0).

**Architecture:** Everything is additive. Migration 007 adds nullable columns on `jobs`/`tasks` and a new `notifications` outbox table; `jobs.status` and its CHECK constraint (migration 006) are untouched. A new pure module `src/runner/result_capture.py` reads the full SDK `ResultMessage` (today `session.py:1095` keeps only `usage`) and derives a typed `terminal_reason`; `session.py`/`main.py` stamp the columns. A new package `src/notify/` owns the outbox rows, a Telegram renderer that is the only code that knows the 4096-char / 64-byte / 8-button limits, and a `python -m src.notify send` CLI; the runner writes rows on job terminal + task lifecycle events **and** keeps publishing the legacy channels byte-identically (dual-write), the bot delivers whichever renderer the switch selects (pub/sub nudge + 30 s poll, so a restart loses nothing), out-of-band bash alerters call the CLI. Three small runner-side belts ride along: `src/runner/sdk_record.py` (opt-in raw message recorder to `volumes/audit_log/<id>.sdk.jsonl`, secrets redacted), `claude_env.claude_subprocess_env()` (the `ClaudeAgentOptions.env` overlay carrying `DISABLE_ERROR_REPORTING=1`/`DISABLE_TELEMETRY=1` into every Claude subprocess — the runner's, the router's, the learning classifier's, the reviewer's, the canary's), and `src/runner/pricing.py` + `scripts/cost-reconcile.py` (list-price ledger from `job_started.model` × `job_completed.usage`, reconciled against `jobs.cost_usd_list`). The canary (`python -m src.runner.canary`) pings through `claude_agent_sdk.query()` with the same options builder conventions, the same env overlay and the same `result_capture` assertion the runner uses — the P0 stand-in for the P3 `ClaudeSdkExecutor` path. `alembic/applied_history.txt` + its two pytest assertions make the spec's rollback rule enforceable inside the gate `server-deploy` already runs; `scripts/alembic-current-check.sh` rides along as an owner-run diagnostic and is deliberately **not** wired into the protected `server-deploy/SKILL.md` (spec §9 rollback paragraph; the §9 P0 "Protected touches" cell is `none`).

**Tech Stack:** Python 3.12, SQLAlchemy 2 async + Alembic, Redis (`redis.asyncio`, `fakeredis` in tests), python-telegram-bot 22.8 (Pipfile.lock; `reply_to_message_id` is still accepted by `send_message`), httpx, `claude-agent-sdk>=0.1.81,<0.2` (bundled CLI 2.1.139; `ClaudeAgentOptions.env` is an overlay on the inherited `os.environ`, `subprocess_cli.py:430-436`), pytest (`asyncio_mode=auto`), bash under launchd.

**Spec:** `docs/superpowers/specs/2026-09-25-multi-model-platform-design.md` (review rounds 1–2 applied in the spec; **round 2 applied to this plan 2026-09-27**) — **§9 P0 row + its test-gate paragraph + its rollback paragraph** (authoritative scope), §9 kill-switch paragraph (`NOTIFY_OUTBOX=0` dual-write semantics), §9 "Who executes" (per-phase 15 % window cap, D1 = P0–P1), §9 "Shipped ahead of P0" (Haiku swap as a standalone patch), §0 (decision summary), §0a rows 5–6 and the last rows (Ollama, Haiku retirement, Keychain-primary auth, sealed setup-token, canary through the runner's path, `plutil` exit test), §2.3 (migration 007 rows), §2.4 (`SDK_RECORD=1` recorder, executor env + telemetry flags), §2.7 (event model), §2.8 (cost ledger + the 30-d calibration table the reconcile script reproduces; window figures labelled by source), §3 (Anthropic row: auth + env), §4.5 (notifications), §10 (`tasks:notify` legacy path deleted only in P5), §11 (canary/pin-bump risk row), §12 D1/D3/D4/D12/D17, **§12a rows 0, 1, 2, 2b, 4, 4b, 5, 6, 6b** (owner runbook rows due at P0 entry / P0 exit; row 3 = `claude setup-token` is **P3, not P0**) and row 23 (P0 sign-off); §4.2 "Card eligibility"; §8.3 "Blockers" (P0 trading blockers); round-1 review-log rows **#4, #16, #17, #27, #28, #29, #31, #50, #51, #61, #64** and round-2 rows **#2, #3, #4, #6, #8, #18, #19, #22, #28, #29, #32, #43, #48, #49, #50, #56, #58** (each applied — see the Alignment section's two tables). Current-state citations: the 2026-09-24 state map (§2.1 executor path, §2.2 job lifecycle, §2.3 user surfaces, §2.8 ops, §3 constraints C1–C26, §4 coupling inventory). List prices: `docs/research/llm-landscape-2026-09/claude-anthropic.md` §4 table. Every `file:line` below was re-read on 2026-09-25.

## Global Constraints

Every task's requirements implicitly include this section.

- **INV-3 / C1 — three enforcement points, all three in P0** (spec §3 Anthropic row, §2.4, round-2 rows #2/#4): (1) the `guards.py` Bash-assignment deny (protected, untouched); (2) the **runner-startup `os.environ` assertion** (Task 17) refusing to start when any of `GEMINI_*|CEREBRAS_*|GROQ_*|CODEX_*|OPENROUTER_*|OPENAI_*|XAI_*|*_API_KEY|CLAUDE_CODE_OAUTH_TOKEN|ANTHROPIC_*` is present; (3) the **`<cwd>/.claude/settings*.json` auth-override refusal** (Task 19) — `session.py:716` passes `setting_sources=["project"]`, so a clone's `settings.json`/`settings.local.json` is loaded and `apiKeyHelper`, `env.ANTHROPIC_API_KEY`, `env.ANTHROPIC_AUTH_TOKEN`, `env.CLAUDE_CODE_OAUTH_TOKEN` and `ANTHROPIC_BASE_URL` outrank `/login`. `ANTHROPIC_API_KEY` is never set anywhere; the canary script `unset`s it exactly as `scripts/install-launchd.sh:90` does. Never pass `--bare` to the CLI (spec §0a last rows).
- **C12 fail-closed set** stays intact: `SkillResolutionError`, forced workspace, deploy gate before session, API-terminal reclassification (`session.py:1124-1128` banner regex is KEPT as a belt), tighten-only isolation. Two new fail-closed rejections are added beside them, never replacing them: silent empty success → `unrecognized_model` (Task 2/3), and a project-scope auth override → `provider_refused{settings_auth_override}` with `terminal_reason="provider_refused"` (Task 19, the C1 row of the spec's compliance checklist).
- **C14 audit kinds unchanged**: the 33 existing kinds keep their names and existing fields. Only new kinds are added (`notice_queued`, `notice_sent`, `notice_failed`, `job_result_rejected`, `provider_refused` (Task 19), `schedule_deferred` (Task 21), `utility_model_usage` (Task 17)) and only new fields are appended to `job_completed` / `job_failed` (existing `duration_seconds`, `usage`, `error`, `error_category` stay).
- **`jobs.status` CHECK untouched**: migration 007 never touches `ck_jobs_status_valid`; done-ness/terminal reason are columns, not statuses (spec §2.3 row 008 rationale, D17).
- **Protected paths untouched by every task**: `src/runner/guards.py`, `scripts/lint_docs.py`, `.env`, `.context/PROTOCOL.md`, `MISSION.md` §M, `skills/{server-patch,server-deploy,new-skill}/SKILL.md`, `TELEGRAM_ALLOWED_CHAT_IDS`, web auth checks (`web.py:49-63`). Anything needing them is in "Owner actions".
- **CHANGELOG per module per commit**: the pre-commit hook (`.git/hooks/pre-commit`) rejects any commit touching `src/` without a `CHANGELOG.md` in the same commit. Module changelogs live at `.context/modules/{runner,gateway,db,hosting,registry,notify}/CHANGELOG.md`, newest entry at top, PROTOCOL.md §3.1 format (`## YYYY-MM-DD — summary` + Agent task / Files changed / Why / Side effects / Gotchas discovered).
- **Kill switch `NOTIFY_OUTBOX=0`** (env → `settings.notify_outbox: bool`; ships `False` in Task 5 and is flipped to `True` in the same commit that adds the bot consumer, Task 7): P0 **dual-writes** (spec §9 kill-switch paragraph, §10 row "`tasks:notify` string vocabulary…", review #28). The runner ALWAYS publishes `tasks:notify` and `jobs:done:<id>` byte-identically to today and, only when the switch is on, ALSO writes the outbox row. The switch is **renderer-side**: the bot's legacy `_done_listener`/`_task_notifier` send only when it is off, `_outbox_listener` runs only when it is on — so a bot-only restart flips delivery. The legacy consumer (`_done_listener`, `_job_to_chat`, `_task_notifier`, the nine `tasks:notify` types) is **kept, never deleted, through P5** (spec §10 "Delete (P5, after two releases of outbox soak)"); the P0 test `test_done_message_sends_legacy_when_outbox_off` (Task 7) is the spec's exit-criterion test "with `NOTIFY_OUTBOX=0` a Telegram-launched job still DMs via the legacy path".
- **Rollback rule (spec §9 rollback paragraph, review #29)**: to roll P0 back, flip `NOTIFY_OUTBOX=0`, then `git revert` **application code only** — `alembic/versions/007_p0_observability.py` is never reverted (its columns are nullable and ignored by older ORM models; reverting it leaves prod `alembic_version` pointing at a revision with no script on disk and the next `server-deploy`'s `alembic upgrade head` fails with "Can't locate revision" mid-incident). If the migration itself must go: `alembic downgrade -1` on prod **before** removing the file, and remove its line from `alembic/applied_history.txt` in the same commit (Task 18 makes the test fail otherwise). The P0 PR description carries a rollback note naming the switch and the merge SHA (Task 14 Step 5).
- **Auth posture (spec §0a last rows, §3 Anthropic row, review #31)**: the Keychain `claude login` on the Mini is the live credential and the only one P0 code ever uses. The `claude setup-token` is **minted before P3, NOT at P0** (§12a row 3 as round 2 re-scoped it: "the Keychain login is the only credential until the executor seam exists; the sealed token is unused before P3") — this plan therefore asks the owner for no token, and the Owner-actions table carries it as a "P3, not P0" line. When it is minted it is sealed 0600 outside any workspace and is a **canary-triggered fallback for P3's `ClaudeSdkExecutor`** — it is never read by P0 code, never written to `.env`, never exported into any launchd plist, never passed to the canary (which must prove the Keychain login, not the token). P0 exit test (§0a): `plutil -p ~/Library/LaunchAgents/com.assistant.*.plist | grep -c CLAUDE_CODE_OAUTH_TOKEN` → `0` (runbook §7; pinned at the installer level by `tests/test_claude_env.py::test_installer_never_exports_credentials`, Task 17).
- **Claude subprocess env (spec §2.4, §3, review #61)**: every `ClaudeAgentOptions` the server builds carries `env=claude_env.claude_subprocess_env()` = `{"DISABLE_ERROR_REPORTING": "1", "DISABLE_TELEMETRY": "1"}` (the SDK overlays it on the inherited env, `subprocess_cli.py:430-436`), and the service + timer plists export the same two keys (Task 17, Task 12). Vendor keys (`GEMINI_*`, `CEREBRAS_*`, `GROQ_*`, `CODEX_*`, `OPENROUTER_*`) never enter `os.environ`: the runner refuses to start if any is set (Task 17 startup assertion beside `_check_subscription_auth`). The full explicit-`env=` replacement (no inheritance) is P3's `claude_sdk.py`, not P0.
- **Raw SDK recorder (spec §2.4, review #27)**: `SDK_RECORD=1` (env → `settings.sdk_record: bool = False`) makes `_run_in_process` append every SDK message it receives, in arrival order, to `volumes/audit_log/<id>.sdk.jsonl` (dataclass → JSON, secrets redacted by the **shared** `src/runner/secret_redact.redact` that Task 20 creates for the always-on JSONL/stream path — `sdk_record` imports it so there is one pattern set, never a second copy). The recorder is opt-in, best-effort (a write error is logged once and never fails the job), records exactly what the loop sees (no `StreamEvent`s unless `include_partial_messages` is ever turned on), and ≥ 20 jobs across skill classes must be recorded before P3 (`python -m src.runner.sdk_record coverage`). Owner turns it on in prod `.env` (protected path) and off again once coverage is met.
- **Always-on audit/stream redaction (spec §2.4 "Audit/stream redaction (P0)", round-2 #3)**: `session._handle_message` runs `src/runner/secret_redact.redact()` over every `tool_result` preview and every `text` **before** the per-job JSONL append and the `jobs:stream:<id>` publish (Task 20). This is *not* the opt-in recorder: with `SDK_RECORD=0` — the shipped default — the durable trace is still redacted, so a `printenv` or a `curl -H 'Authorization: …'` in any of the 72 skills never lands a credential value in `volumes/audit_log/<id>.jsonl`, in the stream, in `ai-mcp` reads or in the learning extractor's input. Pattern set: `sk-ant-…`, `Authorization: Bearer …`, and `NAME=value` assignments/dumps for `CLAUDE_CODE_OAUTH_TOKEN`, `ANTHROPIC_*`, `GEMINI_*`, `CEREBRAS_*`, `GROQ_*`, `CODEX_*`, `OPENROUTER_*`, `OPENAI_*`, `XAI_*` and any `*_TOKEN|*_SECRET|*_API_KEY|*_PASSWORD` name. P0 test gate: `test_audit_redactor`.
- **`pipenv run` exports `.env` into `os.environ`** (verified on this host: `pipenv run` prints "Loading .env environment variables…" and its values *win* over inherited ones — `SERVER_ROOT=$PWD pipenv run …` does **not** override the `.env` value, while `pipenv run env SERVER_ROOT=$PWD …` does). Two consequences this plan must respect: (1) any test that needs `settings` pointed at the repo's own tree runs as `pipenv run env SERVER_ROOT="$PWD" pytest …` (or monkeypatches the property), because the dev `.env` points `SERVER_ROOT` at the **production** checkout; (2) once a vendor key lands in `.env` (P3, §12a rows 10/11) Task 17's fail-closed startup assertion would refuse a `pipenv`-launched runner, so `scripts/run.sh` sets `PIPENV_DONT_LOAD_ENV=1` on its three `_start_one` lines (Task 17 Step 3; launchd runs the venv python directly and is unaffected).
- **Window figures are labelled by source (spec §2.8 Claude row, review #4)**: no P0 surface may present a Claude 5-h/7-d figure as vendor-sourced unless a `RateLimitEvent` carried it. In P0 the only such surface is the `quota_paused` DM: its "Reset at …" line says `(vendor)` when the reset time came from `RateLimitInfo.resets_at` and `(estimated)` when it came from the text heuristic or the default pause window (Task 7 Step 3b; `quota.pause_queue(..., source=)`).
- **Phase economics — the spec's own figures, verbatim (spec §9 "Who executes", §2.8 "Load during build", §13; round-1 #51, round-2 #22)**: build sessions draw the same Max window as the 41 live schedules and cost **≈ 28 M tokens/week ≈ $115/month list-equivalent for ~13 weeks, `purpose=build`** (§2.8: server-patch's measured shape, 15 jobs / 52.3 M tokens / $50 at 1-h rates ≈ $0.95/M); a phase may not consume more than **15 % of the weekly window** (hold the remaining tasks if the running total crosses it); and **D1 must state what build displaces** — *either* the alpha valve drops 12 → 6 (`ALPHA_DAILY_JOB_VALVE`, `src/runner/events.py:364`, ≈ −40 M/day) **and** `review-and-improve`'s idle trigger is removed in P0 rather than P4 (≈ −36 M/month), *or* D1 explicitly accepts "N `rejected` windows/week during build". The P0 PR template (Task 14 Step 5) carries both sentences; Task 13 Step 6b executes the displacement **only if D1 picked it**. Runtime delta of the Haiku→Sonnet swap: **+≈ $8/month list-equivalent, 0 token change** (a model swap changes price, not tokens — round-2 #49; the old "+≈ 8 M tokens/month" phrasing was wrong). **D1 approves P0–P1 only**; nothing in this plan pre-empts P2.
- **Pre-P0 standalone patch (spec §9 "Shipped ahead of P0", review #50)**: the Haiku 4.5 retirement swap (Task 0) is its own `server-patch` PR on the INV-4 lane, shipped and deployed before Task 1 and not gated on D1; the P0 test gate "registry-less Haiku swap smoke" is its live check.
- **Telegram limits (C23)**: 4096 chars per message, 64 bytes per `callback_data`, ≤ 8 inline buttons per keyboard. Enforced in `src/notify/telegram.py` only; every other module hands it unbounded text.
- **Tests are pure-function / fixture style**: no network, no live SDK subprocess (constructing the SDK's message dataclasses in a test is fine; spawning the CLI is not), no Postgres (DB-backed tests stay opt-in behind `AI_SERVER_RUN_DB_TESTS=1`); Redis paths use the `fake_redis` fixture from `tests/conftest.py`. `tests/test_migrations.py` keeps the chain single-headed **and** (Task 18) asserts every revision in `alembic/applied_history.txt` has its script on disk.
- **SDK pin `>=0.1.81,<0.2`** (`pyproject.toml`) is not touched; `ResultMessage` fields used are exactly those in the installed `claude_agent_sdk/types.py:1143-1166` (`@dataclass` at :1143; `subtype, duration_ms, duration_api_ms, is_error, num_turns, stop_reason, total_cost_usd, usage, result, model_usage, permission_denials, errors, api_error_status`).
- **Runner keeps working after every commit**: each commit is deployable on its own with `pipenv run alembic upgrade head` + restart. **Execution order** (task numbers are stable; the 09-25 re-cut appended 15–18 and moved the Haiku swap to Task 0; the 09-27 round-2 delta appended 19–21): **0** (pre-P0 standalone patch, its own PR + deploy) → **1** (migration) → **18** (alembic history manifest) → **2** → **3** (capture) → **19** (settings-file auth-override refusal — edits the `run_session` path Task 3 touches) → **20** (always-on audit/stream redactor — `_handle_message`, which Task 3 also touches) → **15** (raw SDK recorder — hooks into Task 3's `_run_in_process`, imports Task 20's redactor) → **17** (Claude subprocess env + startup assertion + the utility `model_usage` check) → **4** (origin) → **5** → **6** → **21** (scheduler `provisioning_gap` pre-check — needs Task 6's outbox producer) → **7** (notify + bot) → **8** → **9** → **10** (Telegram hygiene) → **12** (canary — needs 2, 5, 17) → **16** (cost reconcile — needs 3's token columns for the DB leg) → **13** (ops hygiene + runbook + the D1 displacement step) → **14** (docs, PR note, deploy). Task 11 is **not a task** — it is a retired number pointing at Task 0; do not dispatch it.

  **File order ≠ execution order.** The task sections appear in this file as **0, 1, 2, 3, 19, 20, 4, 5, 6, 21, 7, 8, 9, 10, 11, 12, 13, 15, 16, 17, 18, 14** (the 09-25 re-cut appended 15-18 after 13; the 09-27 delta placed 19/20 beside Task 3 and 21 beside Task 6, where a reader looking for them will be). Every task heading therefore carries an `**Execution position:**` line naming its predecessor and successor, and Tasks 12, 15, 16, 17, 18, 19, 20 and 21 each open with a **Step 0 prerequisite check** — a one-line import/grep probe that stops with "execute Task &lt;n&gt; first" when its dependency is not in the tree yet. A subagent-driven runner that dispatches one agent per checkbox-bearing heading must follow the order above, not the file order.

  **Line numbers are as-of the pre-P0 tree.** `session.py`, `main.py` and `telegram_bot.py` are edited by several tasks; any task that runs after another task edited the same file must re-locate its anchors **by symbol** (function/constant name) rather than trusting the `file:line` citation, which will have drifted by the number of lines the earlier task inserted above it.
- **Single-writer topology (C20)**: all commits are born in this dev repo; `git fetch origin && git merge origin/main` before starting and before pushing; never commit on prod.
- **Lint gate**: `pipenv run python scripts/lint_docs.py` prints `All clean!` before every commit that touches docs or `src/` layout. Two lint checks are wired into pytest (`tests/test_doc_lint.py`): `check_runner_context` (every `src/runner/*.py` named in the runner CONTEXT.md Paths line) and `check_module_graph_imports` (every `from src.X import …` whose target is a SYSTEM.md module-graph row must appear in the importer's Depends-on cell). So **the task that creates a `src/` file or adds a cross-module import also edits `.context/modules/runner/CONTEXT.md` / `.context/SYSTEM.md` in the same commit** (Tasks 2, 3, 5, 6, 7, 8, 12, 15, 16, 17 each carry that step; Task 18 adds only a script + a manifest, whose SYSTEM.md rows are not lint-checked but are added there per CLAUDE.md's table) and runs `pipenv run pytest tests/test_doc_lint.py -q` before committing; Task 14 keeps only the prose/interface/INDEX/README/TROUBLESHOOTING updates.
- **Never `pipenv run` in a launchd-run script**: `pipenv` lives in `~/.pyenv/shims`, which launchd's `bash -lc` never sees (no `~/.bash_profile`; `~/.zprofile` is zsh-only) — `volumes/logs/schedule-monitor.log` on prod shows `pipenv: command not found` / `run rc=127` since 2026-09-24. From Task 12 on the timer plists export `VENV_PY=${VENV_DIR}/bin/python` (and a PATH with `${VENV_DIR}/bin`, which `bash -lc`'s `path_helper` demotes behind the system dirs — verified on this host — so PATH alone is not a contract). Every script a timer runs resolves the interpreter as `VENV_PY="${VENV_PY:-}"` → `$PROJECT_DIR/.venv/bin/python` → `command -v python`, guards it with `"$VENV_PY" -c 'import src.config'`, and treats "no interpreter" as a logged failure (curl DM where an alert is due), never as a reason to fall back to `pipenv`; `tests/test_scripts_syntax.py` asserts no `pipenv run` remains in any of the four timer scripts and that `install_timer` writes the env block.

## Review Focus

The five failure modes the spec implies but no task's tests would otherwise exercise, most likely first; each is pinned by a test in the named task.

1. **Bot restart loses DMs** — a job finishes while `com.assistant.bot` is restarting; a reasonable owner still expects the completion DM. Pinned in Task 7 (`test_pending_rows_survive_listener_restart`: a pending row with no pub/sub message is delivered by the 30 s poll on the next drain) and Task 5 (`test_retry_delay_backoff`, `test_mark_failed_keeps_pending_until_max_attempts`).
2. **Scheduled failure with no `task_id`** — today every failure DM path requires `task_id` (state map §2.3), so a scheduler job failing at 03:00 is silent. Pinned in Task 5 (`test_build_job_notice_scheduled_failure_targets_owner`) and Task 6 (`test_finish_job_failed_enqueues_notice_without_task`).
3. **All-zero usage on short chat jobs** — `Job.result.usage` is often all zeros for chat jobs that produced real text (state map §2.1 pain points); the new served-model assertion must not fail them. Pinned in Task 2 (`test_zero_usage_with_text_and_api_duration_is_ok`).
4. **A queued job cancelled twice** — the owner taps `/cancel <prefix>` twice (or `/cancel` then the task Cancel button); the second must be a no-op with one `job_cancelled` event, no exception. Pinned in Task 8 (`test_cancel_action_noop_for_terminal`, `test_remove_from_queue_idempotent`).
5. **A `ResultMessage` without `model_usage` under SDK 0.1.81** — older CLI shapes / some subtypes omit `modelUsage`; the assertion must treat "absent" differently from "present but wrong". Pinned in Task 2 (`test_missing_model_usage_with_real_usage_is_ok`, `test_missing_model_usage_and_empty_everything_is_rejected`).

Added by the 2026-09-25 re-cut (each pinned in the named task):

6. **The recorder must never cost a job** — with `SDK_RECORD=1` a full disk, a read-only `volumes/`, or an unserialisable message must be logged once and the job must finish exactly as it would with the switch off. Pinned in Task 15 (`test_write_error_never_raises`, `test_unserialisable_message_is_recorded_as_repr`).
7. **A tool result that echoes a secret must not land in a recording** — `curl -H 'Authorization: Bearer …'` command text and `.env` dumps routinely appear in Bash tool results (spec §2.4, `learning.py:138-170`); the raw recording is the one file that keeps them verbatim unless redacted. Pinned in Task 15 (`test_redaction_covers_bearer_env_and_anthropic_keys`, `test_nested_content_is_redacted`).
8. **The canary must fail loudly on every "logged out" shape and must never prove the wrong credential** — `is_error` with `authentication_failed`, a `ResultMessage` that never arrives (CLI exits early), `model_usage` missing, zero API time; and it must run without `CLAUDE_CODE_OAUTH_TOKEN` in its env so a pass means the Keychain login works. Pinned in Task 12 (`test_no_result_message_fails`, `test_is_error_fails`, `test_missing_model_usage_fails`, `test_canary_never_reads_the_setup_token`) and Task 17 (`test_installer_never_exports_credentials`).
9. **Reverting the P0 merge must not strand prod's `alembic_version`** — a revert that deletes `007_p0_observability.py` while prod is at 007 breaks the next deploy's `alembic upgrade head`; the failure must surface in the pytest gate, not mid-incident. Pinned in Task 18 (`test_every_revision_in_applied_history_exists_on_disk`, `test_applied_history_matches_disk_chain`).
10. **A job whose `job_started.model` is a bare alias or an unknown id must be counted, never mispriced** — web/dispatch launches pass free-text models (state map §2.3), and Opus 5.5 / Sonnet 5 ids will appear after D13; the reconcile table must list them under `unpriced` with their token counts rather than dropping them or pricing them as another family. Pinned in Task 16 (`test_unknown_model_is_reported_not_priced`, `test_longest_prefix_wins`).

## File structure (what is created / modified and why)

| Path | Responsibility |
|---|---|
| `alembic/versions/007_p0_observability.py` (create) | additive columns on `jobs`/`tasks`, `notifications` table, token/provider/origin backfill |
| `src/models.py` (modify) | ORM columns for the above + `Notification` model |
| `src/runner/result_capture.py` (create) | pure: `ResultCapture`, `capture_result_message`, `derive_terminal_reason`, `served_model_violation`, `result_columns`, `terminal_reason_for_exception`, `parse_cli_version`, `same_model`, `requested_matches_served` |
| `src/runner/session.py` (modify) | wire capture into `_run_in_process`/`run_session`; stamp columns; `job_completed` extra fields; default tool list without `AskUserQuestion`; `SdkRecorder` hook at the top of the message loop (Task 15); `claude_subprocess_env()` + `env=` on `_build_options` (Task 17); `QuotaExhausted(source=)` on the `RateLimitEvent` path (Task 7) |
| `src/runner/main.py` (modify) | `queue_wait_ms`; `terminal_reason` on failure branches; `_notify_task` → outbox; `_finish_job` → job notice; scheduler origin; `awaiting_since`; vendor-key startup assertion (Task 17); `pause_queue(..., source=exc.source)` (Task 7) |
| `src/runner/quota.py` (modify) | `pause_queue(reset_at, reason, *, source)` stores `quota:last_source`; `last_source()` (Task 7 — window figures labelled by source) |
| `src/runner/secret_redact.py` (create) | **always-on** secret redactor (`redact`, `redact_tree`) applied in `session._handle_message` before every JSONL append and `jobs:stream` publish — P0, spec §2.4 (Task 20) |
| `src/runner/sdk_record.py` (create) | opt-in raw SDK message recorder (`SdkRecorder`, `message_to_record`, `coverage_report`, `python -m src.runner.sdk_record coverage`) — the P3 replay-gate fixtures; re-exports `secret_redact.redact` so there is one pattern set (Task 15) |
| `src/runner/pricing.py` (create) | list-price table (`claude-anthropic.md §4`), `family_for`, `cache_write_buckets`, `price_usage` (each TTL bucket at its own rate), `lane_for`, `summarize`/`summarize_windows`, `render_table`, `lane_seed` — pure core of the two-window cost reconcile (Task 16) |
| `src/registry/manifest.py` (modify) | `Manifest.env_required` is **read** (it was ignored) so the scheduler can pre-check provisioning (Task 21) |
| `scripts/cost-reconcile.py`, `scripts/cost-reconcile-run.sh` (create) | CLI over `pricing.py`: **both** windows (30 d + 7 d) per model, the per-kind step table, SDK-reported vs computed cost, `--db` leg against `jobs.cost_usd_list`, `--seed-lane-budgets`; the `-run.sh` wrapper is what the weekly `com.assistant.cost-reconcile` timer executes (Task 16) |
| `alembic/applied_history.txt` (create), `scripts/alembic-current-check.sh` (create) | append-only manifest of applied revisions + an **owner-run diagnostic** "`alembic current` has a script on disk" (Task 18). **No `server-deploy/SKILL.md` edit** — round 2 cancelled it; the pytest gate is what protects the deploy |
| `src/runner/session.py` (modify, Task 19) | `settings_auth_override(cwd)` + `ProviderRefused` — a clone's `.claude/settings*.json` carrying `apiKeyHelper`/`env.ANTHROPIC_*`/`ANTHROPIC_BASE_URL` refuses the job fail-closed (INV-3 third enforcement point, spec §2.4) |
| `src/runner/main.py` (modify, Task 21) | `provisioning_gap` / `env_keys_present` / `PROVISIONING_EXEMPT` + the `_tick_schedules` pre-check: a due row whose project `.env` lacks a manifest-required key defers with `schedule_deferred{provisioning_gap}` + one DM/day instead of burning a session (spec §8.3) |
| `src/gateway/jobs.py` (modify) | `enqueue_job(origin_*)`, `origin_from_created_by`, `cancel_action_for_status`, `remove_from_queue`, `cancel_job_durable` |
| `src/gateway/web.py` (modify) | origin on web launches; new `JobOut` fields; durable DELETE |
| `src/gateway/telegram_bot.py` (modify) | origin + `awaiting_since`; outbox listener; `/cancel <prefix>`, `/status <prefix>`, `/proposals`; `/clear` confirm; `/rate` out of help |
| `src/notify/__init__.py`, `outbox.py`, `telegram.py`, `__main__.py` (create) | outbox rows + Redis nudge; Telegram renderer with limits; `python -m src.notify send|drain` |
| `src/config.py` (modify) | `notify_outbox`, `utility_model` settings |
| `src/registry/skills.py` (modify) | `DEFAULT_REQUIRED_TOOLS` constant (no `AskUserQuestion`) |
| `src/runner/llm_router.py`, `src/runner/learning.py`, `src/gateway/telegram_bot.py:132-133`, `skills/project-update-poll/SKILL.md:4`, `src/gateway/web.py:691`, `tests/test_pure_functions.py:143` (modify) | **Task 0, pre-P0 standalone patch**: Haiku 4.5 → `settings.utility_model` (`claude-sonnet-4-6`, effort low) via extracted option builders; the `haiku` aliases, the one Haiku skill frontmatter and the dashboard option repointed |
| `src/runner/review.py:247`, `evals/run.py:82` (modify) | `env=claude_subprocess_env()` on the reviewer's and the eval judge's options (Task 17) |
| `src/runner/canary.py` (create), `scripts/credential-canary.sh` (create), `scripts/install-launchd.sh` (modify) | daily canary **through `claude_agent_sdk.query()`** with the runner's options conventions, env overlay and `result_capture` assertion (the P0 stand-in for `ClaudeSdkExecutor`); `timers-only` installer mode; timer plists get `PATH`/`VENV_PY` + the two telemetry keys; service plists get the two telemetry keys (Task 17) |
| `scripts/backup.sh` (modify), `scripts/restore-drill.sh` (create), `scripts/healthcheck-all.sh`, `scripts/schedule-monitor.sh` (modify) | atlas dump, sealed secrets, restore drill, alerters call `notify send` first |
| `docs/runbooks/2026-09-25-p0-ops-hygiene.md` (create) | owner-run steps (pmset, Ollama, R2, seal key, drill, timer install) |
| `tests/test_migrations.py`, `tests/test_result_capture.py`, `tests/test_origin.py`, `tests/test_notify_outbox.py`, `tests/test_notify_telegram.py`, `tests/test_notify_runner_hooks.py`, `tests/test_notify_bot.py`, `tests/test_cancel_durable.py`, `tests/test_telegram_commands.py`, `tests/test_default_tools.py`, `tests/test_utility_model.py`, `tests/test_canary.py`, `tests/test_scripts_syntax.py`, `tests/test_sdk_record.py`, `tests/test_pricing.py`, `tests/test_claude_env.py`, `tests/test_quota.py`, **`tests/test_settings_auth_override.py`** (Task 19), **`tests/test_audit_redactor.py`** (Task 20), **`tests/test_provisioning_gap.py`** (Task 21) (append/create) | one test file per deliverable; the four named P0 test gates are `test_result_capture`, `test_startup_env`, `test_settings_auth_override`, `test_audit_redactor` (spec §9 test-gate paragraph) |
| `.context/modules/notify/{CONTEXT.md,CHANGELOG.md,skills/*}` (create), other module CONTEXT/CHANGELOG, `.context/SYSTEM.md`, `.context/INDEX.md`, `docs/README.md`, `docs/TROUBLESHOOTING.md` | documentation per CLAUDE.md's update map |

---

### Task 0 (PRE-P0 STANDALONE `server-patch`): Haiku 4.5 retirement — the four edit sites → `claude-sonnet-4-6` @ `low`

**Execution position:** 1 of 21 — previous: none, next: Task 1 (see Global Constraints "Execution order"). Ships on its own PR and is deployed before Task 1 starts.

**Ships ahead of P0, not gated on D1** (spec §9 "Shipped ahead of P0", §11 Haiku row, review #50). Haiku 4.5 retires ≥ 2026-10-15 (`claude-anthropic.md` §1 [56]); after that date the router fallback (`llm_router.py:148`), the learning classifier (`learning.py:258`), the one skill still pinned to it (`skills/project-update-poll/SKILL.md:4`) and any `/task --model=haiku` launch (`telegram_bot.py:132-133`) fail as `unrecognized_model`. This task is its **own `server-patch` PR** on the INV-4 lane (in-session `code-review` LGTM + owner notification, per `skills/server-patch/SKILL.md` — protected, read-only for this task), merged and deployed with `/task deploy server` **before Task 1 starts**. Rollback = `git revert` of the one commit (no migration). Only the registry alias (`registry/models.py`) waits for P3. The P0 test gate "registry-less Haiku swap smoke" (spec §9 test-gate paragraph) is Step 4's live check.

**Files:**
- Modify: `src/config.py` (add `utility_model`), `src/runner/llm_router.py:145-154`, `src/runner/learning.py:255-264`
- Modify: `src/gateway/telegram_bot.py:117-134` (`_MODEL_ALIASES` — the `haiku`/`haiku-4-5` values and the comment that says bare defaults stay put), `skills/project-update-poll/SKILL.md:4`, `skills/README.md:12`, `skills/TEMPLATE.md:15` (the two authoring docs that also advertise the retiring id — not protected paths), `src/gateway/web.py:691` (dashboard `<option>`), `tests/test_pure_functions.py:143`
- Modify: `.context/modules/runner/CHANGELOG.md`, `.context/modules/db/CHANGELOG.md`, `.context/modules/gateway/CHANGELOG.md`
- Test: `tests/test_utility_model.py`

**Interfaces:**
- Consumes: nothing new.
- Produces:
  - `settings.utility_model: str = "claude-sonnet-4-6"` (env `UTILITY_MODEL`).
  - `llm_router.router_options() -> ClaudeAgentOptions` and `learning.classifier_options() -> ClaudeAgentOptions` — the extracted option builders (model = `settings.utility_model`, `effort="low"`, `permission_mode="plan"`, `allowed_tools=[]`, `max_turns=2`, the module's `output_format`). Both `llm_route` and `extract_learning` call them; behaviour otherwise unchanged. Task 17 adds `env=claude_subprocess_env()` to both; P3's `utility_call` replaces them.
  - `_MODEL_ALIASES["haiku"] == _MODEL_ALIASES["haiku-4-5"] == "claude-sonnet-4-6"`. Consequence: `VALID_MODELS` (`tests/test_skill_contracts.py:24`, derived from the alias VALUES) no longer contains `claude-haiku-4-5-20251001`, so every `SKILL.md` must be off Haiku in the same commit. `grep -rln "claude-haiku" skills/` → **three** files: `skills/project-update-poll/SKILL.md:4` (the only real skill, repointed below) plus `skills/README.md:12` and `skills/TEMPLATE.md:15` — authoring docs that `registry.list_all()` never sees (`src/registry/skills.py:145-146` walks only directories containing a `SKILL.md`), so they break no test, but `TEMPLATE.md` is what new skills are copied from and both are repointed in the same commit.
  - Left alone on purpose: `session.py:467` (`_MODEL_BUDGETS` haiku key — dead, harmless, deleted with the table in P3 per spec §10).
  - **Not built here:** the spec's P0 exit criterion "`model_usage` on utility calls lists only the requested model" (§9 exit cell, §2.8 Claude row, round-2 #49) needs the `ResultMessage` inspection that Task 17 adds to `llm_route`/`extract_learning`. Task 0 only records the *pre*-swap baseline for it (Step 4); the assertion, its pure test and the audit event `utility_model_usage` land in **Task 17 Step 2**. Its purpose is to reveal whether the harness's Haiku side request (`claude-anthropic.md` line 157 — every `-p`/SDK call also bills one) survives the swap, so it can be ledgered `purpose=harness` rather than silently mispriced; a second model in the list is a **finding to record, not a job failure**.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_utility_model.py`:

```python
"""
Haiku 4.5 retires ≥ 2026-10-15 (spec §0a row 6, §9 "Shipped ahead of P0").
The two utility call sites build their options from settings.utility_model
(claude-sonnet-4-6, low); the `haiku` aliases, the one Haiku skill and the
dashboard option are repointed in the same commit.

Run: pipenv run pytest tests/test_utility_model.py -v
"""

from __future__ import annotations

from pathlib import Path

from src.config import settings
from src.gateway.telegram_bot import _MODEL_ALIASES, parse_flags
from src.registry.skills import list_all
from src.runner.learning import LEARNING_OUTPUT_FORMAT, classifier_options
from src.runner.llm_router import ROUTE_OUTPUT_FORMAT, router_options

REPO = Path(__file__).resolve().parent.parent

# The four edit sites the spec names (+ the dashboard option, one line).
SITES = (
    "src/runner/llm_router.py",
    "src/runner/learning.py",
    "src/gateway/telegram_bot.py",
    "skills/project-update-poll/SKILL.md",
    "skills/README.md",
    "skills/TEMPLATE.md",
    "src/gateway/web.py",
)


def test_setting_default():
    assert settings.utility_model == "claude-sonnet-4-6"


def test_router_options():
    o = router_options()
    assert o.model == "claude-sonnet-4-6" and o.effort == "low"
    assert o.permission_mode == "plan" and o.allowed_tools == [] and o.max_turns == 2
    assert o.output_format == ROUTE_OUTPUT_FORMAT


def test_classifier_options():
    o = classifier_options()
    assert o.model == "claude-sonnet-4-6" and o.effort == "low"
    assert o.permission_mode == "plan" and o.allowed_tools == [] and o.max_turns == 2
    assert o.output_format == LEARNING_OUTPUT_FORMAT


def test_options_follow_the_setting(monkeypatch):
    monkeypatch.setattr(settings, "utility_model", "claude-opus-4-7")
    assert router_options().model == "claude-opus-4-7"
    assert classifier_options().model == "claude-opus-4-7"


def test_haiku_aliases_repointed():
    assert _MODEL_ALIASES["haiku"] == "claude-sonnet-4-6"
    assert _MODEL_ALIASES["haiku-4-5"] == "claude-sonnet-4-6"
    assert parse_flags("--model=haiku x")[1]["model"] == "claude-sonnet-4-6"


def test_no_haiku_literal_left_at_the_sites():
    for rel in SITES:
        assert "claude-haiku-4-5" not in (REPO / rel).read_text(), rel


def test_no_skill_frontmatter_on_haiku(monkeypatch):
    # settings.skills_dir is a computed property off SERVER_ROOT, and the DEV
    # checkout's .env points SERVER_ROOT at the PRODUCTION tree — so a bare
    # list_all() here would grade prod's skills, not the ones this commit
    # edits, and would stay red until the deploy propagates. Patch the
    # property on the class (same trick as tests/test_registry_failclosed.py:23-27).
    monkeypatch.setattr(type(settings), "skills_dir",
                        property(lambda self: REPO / "skills"))
    on_haiku = [s.name for s in list_all() if "haiku" in (getattr(s, "model", "") or "")]
    assert on_haiku == [], on_haiku
```

**Why the monkeypatch is load-bearing, not cosmetic.** Verified on this host: `settings.skills_dir` resolves to `/Users/alfredbot.ai.butler/Library/Application Support/ai-server/skills` (the prod checkout), where `load("project-update-poll").model` is still `claude-haiku-4-5-20251001`. Without the patch, this test *and* the existing `tests/test_skill_contracts.py` (whose `VALID_MODELS` is derived from the dev `telegram_bot._MODEL_ALIASES` values) both go red the moment Step 3 repoints the aliases, and CLAUDE.md push gate 1 forbids committing red.

Change `tests/test_pure_functions.py:143` from `== "claude-haiku-4-5-20251001"` to `== "claude-sonnet-4-6"`.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pipenv run pytest tests/test_utility_model.py -v`
Expected: `ImportError: cannot import name 'classifier_options'` (collection fails). `tests/test_pure_functions.py::TestParseFlags::test_model_alias_expansion` now FAILS too (alias still Haiku).

- [ ] **Step 3: Implement**

`src/config.py` — after `default_model`:

```python
    # Utility model for the two one-shot classifier calls (router fallback,
    # learning extractor). Was claude-haiku-4-5-20251001 — Haiku 4.5 retires
    # ≥ 2026-10-15 (spec §0a row 6); Sonnet at effort=low is the pinned
    # CLI's cheapest known id. P3 moves these calls to utility_call().
    utility_model: str = "claude-sonnet-4-6"
```

`src/runner/llm_router.py` — add a module-level builder and use it (replace lines 145-154):

```python
def router_options() -> ClaudeAgentOptions:
    """One-shot structured classification: settings.utility_model, low effort,
    plan mode, no tools, two turns."""
    return ClaudeAgentOptions(
        cwd=str(settings.server_root),
        system_prompt=ROUTER_SYSTEM_PROMPT,
        model=settings.utility_model,
        effort="low",
        permission_mode="plan",
        allowed_tools=[],
        max_turns=2,
        output_format=ROUTE_OUTPUT_FORMAT,
    )
```

and inside `llm_route` replace the inline `options = ClaudeAgentOptions(...)` with `options = router_options()`.

`src/runner/learning.py` — same shape (replace lines 255-264):

```python
def classifier_options() -> ClaudeAgentOptions:
    """Learning classifier: settings.utility_model, low effort, read-only."""
    return ClaudeAgentOptions(
        cwd=str(settings.server_root),
        system_prompt=CLASSIFIER_SYSTEM_PROMPT,
        model=settings.utility_model,
        effort="low",
        permission_mode="plan",  # read-only; classifier does not need to act
        allowed_tools=[],
        max_turns=2,
        output_format=LEARNING_OUTPUT_FORMAT,
    )
```

and inside `extract_learning` use `options = classifier_options()`.

`src/gateway/telegram_bot.py:132-133` — repoint both aliases:

```python
    "haiku": "claude-sonnet-4-6",       # Haiku 4.5 retires ≥ 2026-10-15; Sonnet @ low is the cheap lane until P3's registry
    "haiku-4-5": "claude-sonnet-4-6",
```

and in the comment block above the dict (lines 119-121) replace `Bare-name defaults (opus/sonnet/haiku) are left on their established targets` with `Bare-name defaults (opus/sonnet) are left on their established targets; haiku points at Sonnet since the 2026-10-15 retirement (spec §9)`.

`skills/project-update-poll/SKILL.md:4`: `model: claude-haiku-4-5-20251001` → `model: claude-sonnet-4-6` (`effort: low` on line 5 already; not an atlas two-repo skill, no second copy to sync).

`skills/README.md:12` and `skills/TEMPLATE.md:15`: drop `claude-haiku-4-5-20251001` from the model-choice lists (`model: claude-sonnet-4-6 | claude-opus-4-7` and `model: <claude-opus-4-7 | claude-sonnet-4-6>`). Neither is read by `registry.list_all()`, so no test enforces it — but `TEMPLATE.md` is the file new skills are copied from, and after 2026-10-15 that id stops resolving.

`src/gateway/web.py:691`: delete the line `      <option value="claude-haiku-4-5-20251001">haiku 4.5</option>` (the dropdown is replaced by the registry-fed picker in P3, spec §10).

- [ ] **Step 4: Run the tests to verify they pass**

Run the contract gate with `SERVER_ROOT` repointed at this checkout — **`pipenv run env` and not `SERVER_ROOT=… pipenv run`**, because `pipenv run` loads `.env` *after* the inherited environment and its `SERVER_ROOT` (the prod path) wins (verified: `SERVER_ROOT=$PWD pipenv run python -c …` → the prod skills dir; `pipenv run env SERVER_ROOT=$PWD python -c …` → the repo's):

```bash
pipenv run env SERVER_ROOT="$PWD" pytest tests/test_utility_model.py tests/test_learning.py \
    tests/test_pure_functions.py tests/test_skill_contracts.py -q
```

Expected: all PASS (`test_skill_contracts` proves no SKILL.md in **this checkout** references the id that just left `VALID_MODELS`). Without the `env SERVER_ROOT` prefix `test_skill_contracts` reads the production skills tree, where `project-update-poll` is still on Haiku until the deploy lands, and fails for the wrong reason.

Live smoke (the P0 test gate "registry-less Haiku swap smoke" — one real routed job). First record the baseline: `grep -c 'llm router SDK error' volumes/logs/runner.err.log` (note the number; the router logs nothing on success, so "no new error line" is the pass signal). Restart the runner (`launchctl kickstart -k gui/$(id -u)/com.assistant.runner`), then from Telegram send `please summarise the last three completed jobs for me` (no rule matches → LLM fallback), find the job (`/jobs`), and check:
- `grep -c '"method": "llm"' volumes/audit_log/<job>.jsonl` → `1` (the `routing_decision` event went through `router_options()`);
- `grep -c 'llm router SDK error' volumes/logs/runner.err.log` → the same number as the baseline;
- `/task --model=haiku reply with the word pong` → `psql assistant -tAc "SELECT resolved_model FROM jobs ORDER BY created_at DESC LIMIT 1"` → `claude-sonnet-4-6`.

**Also record the utility-`model_usage` baseline here** (spec §9 P0 exit criterion, §2.8 Claude row, round-2 #49). Task 17 Step 2 adds the assertion in code; Task 0 only needs the *before* reading so the after/before pair says whether the harness's Haiku side request survived the swap:

```bash
# Every model family named by any job's ResultMessage in the last day.
python3 - <<'EOF'
import json, pathlib, collections
seen = collections.Counter()
for p in sorted(pathlib.Path("volumes/audit_log").glob("*.jsonl"))[-40:]:
    for line in p.read_text().splitlines():
        try: e = json.loads(line)
        except Exception: continue
        if e.get("kind") == "job_completed":
            for m in (e.get("model_usage") or {}): seen[m] += 1
print(seen)
EOF
```

Note the counter in the PR body. If `claude-haiku-*` still appears after the swap, that is the harness side request, to be ledgered `purpose=harness` (spec §2.8) — a finding for the PR, never a reason to fail the patch.

- [ ] **Step 5: CHANGELOGs, commit on the patch branch, gates, merge, deploy**

Prepend to `.context/modules/runner/CHANGELOG.md`:

```markdown
## 2026-09-25 — Haiku 4.5 retirement (standalone pre-P0 server-patch): router + learning classifier on settings.utility_model (claude-sonnet-4-6, effort low)

- `llm_router.router_options()` / `learning.classifier_options()` extracted (tested); the hardcoded `claude-haiku-4-5-20251001` at `llm_router.py:148` and `learning.py:258` is gone. Haiku 4.5 retires ≥ 2026-10-15. Shipped ahead of the multi-model P0 (spec §9 "Shipped ahead of P0").
```

Prepend to `.context/modules/db/CHANGELOG.md`:

```markdown
## 2026-09-25 — settings.utility_model

- `src/config.py`: `utility_model: str = "claude-sonnet-4-6"` (env `UTILITY_MODEL`).
```

Prepend to `.context/modules/gateway/CHANGELOG.md`:

```markdown
## 2026-09-25 — `haiku`/`haiku-4-5` aliases → claude-sonnet-4-6; dashboard haiku option removed

- `telegram_bot._MODEL_ALIASES`: both Haiku aliases point at `claude-sonnet-4-6` (VALID_MODELS therefore drops `claude-haiku-4-5-20251001`; `skills/project-update-poll/SKILL.md` repointed in the same commit). `web.py` dashboard dropdown loses the haiku option. Haiku 4.5 retires ≥ 2026-10-15.
```

```bash
git checkout -b server-patch/haiku-4-5-retirement            # branch/merge conventions: skills/server-patch/SKILL.md
git add src/config.py src/runner/llm_router.py src/runner/learning.py src/gateway/telegram_bot.py src/gateway/web.py skills/project-update-poll/SKILL.md skills/README.md skills/TEMPLATE.md tests/test_utility_model.py tests/test_pure_functions.py .context/modules/runner/CHANGELOG.md .context/modules/db/CHANGELOG.md .context/modules/gateway/CHANGELOG.md
git commit -m "fix: Haiku 4.5 retirement (≥2026-10-15) — router/learning on settings.utility_model, haiku aliases + project-update-poll + dashboard option → claude-sonnet-4-6 @ low (pre-P0 standalone patch)"
git fetch origin && git merge origin/main                     # CLAUDE.md push gate 2
pipenv run env SERVER_ROOT="$PWD" pytest -q                   # see Step 4: the dev .env points SERVER_ROOT at prod
pipenv run python scripts/lint_docs.py                        # expect: All clean!
git diff origin/main | grep -iE 'api[_-]?key|token|secret|password' || true   # expect nothing
```

Then the INV-4 lane merge (in-session `code-review` LGTM, owner notification) and `/task deploy server`. This patch is complete and deployed before Task 1 begins; the P0 PR later lists it under "shipped ahead".

---

### Task 1: Migration 007 — additive columns + `notifications` outbox + backfill

**Execution position:** 2 of 21 — previous: Task 0 (shipped and deployed as its own patch), next: Task 18 (see Global Constraints "Execution order").

**Prerequisite check (host only — needs DB access; skip in an isolated worktree and confirm with the owner instead).** Task 0 must be merged and deployed before 007 lands, because the swap is a separate PR:

```bash
git log --oneline origin/main | grep -c "Haiku 4.5 retirement"     # → 1
psql assistant -tAc "SELECT resolved_model FROM jobs WHERE resolved_model LIKE 'claude-haiku%' AND created_at > now() - interval '1 day'" | wc -l   # → 0
```

**Files:**
- Create: `alembic/versions/007_p0_observability.py`
- Modify: `src/models.py:1-14` (docstring), `:82-135` (Job), `:264-297` (Task), append `Notification` after `TaskTurn`
- Modify: `.context/modules/db/CHANGELOG.md`
- Test: `tests/test_migrations.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `Job.resolved_provider, model_served, executor, cli_version, lane, origin_channel, origin_ref, origin_thread, queue_wait_ms, first_event_at, input_tokens, output_tokens, cache_read_tokens, cache_write_1h_tokens, cache_write_5m_tokens, num_turns, duration_api_ms, cost_usd_list, terminal_reason, task_class, sensitivity` (all nullable — **no `priority` column**: spec §2.3 row 007 as round-2 #56 left it, "lanes replace priority and `--priority` is explicitly not built"; the two `cache_write_*` columns are the round-2 #19 shape, sourced from `usage.cache_creation.ephemeral_{1h,5m}_input_tokens` and priced at their own rates); `Task.origin_channel, origin_ref, origin_thread, awaiting_since`; `class Notification(Base)` with columns `id, notice_kind, subject_type, subject_id, severity, body, actions, channel, target, thread, external_ref, status, attempts, last_error, next_attempt_at, sent_at, created_at`. Consumed by Tasks 2–9.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_migrations.py` (after `test_revision_chain_walkable`):

```python
# ── Layer 1b: migration 007 shape (no DB) ───────────────────────────────────

P0_JOB_COLUMNS = (
    "resolved_provider", "model_served", "executor", "cli_version", "lane",
    "origin_channel", "origin_ref", "origin_thread", "queue_wait_ms",
    "first_event_at", "input_tokens", "output_tokens", "cache_read_tokens",
    # Two cache-write columns, not one: the subscription's TTL is 1 h and prod
    # records 100 % of writes as 1-h, priced $10/M Opus vs the $6.25/M 5-m rate
    # (spec §2.3 row 007, §2.8; round-2 #19). A 5-m reading is itself the
    # credit-overflow signature (spec §2.8 tripwires).
    "cache_write_1h_tokens", "cache_write_5m_tokens",
    "num_turns", "duration_api_ms", "cost_usd_list",
    "terminal_reason", "task_class", "sensitivity",
)
# NOT in 007: `priority`. Round-2 #56 dropped it — lanes replace priority and
# `--priority` is on the explicit NOT-building list (spec §0, §2.3 row 007).
FORBIDDEN_007_COLUMNS = ("priority",)
P0_TASK_COLUMNS = ("origin_channel", "origin_ref", "origin_thread", "awaiting_since")
P0_NOTIFICATION_COLUMNS = (
    "id", "notice_kind", "subject_type", "subject_id", "severity", "body", "actions",
    "channel", "target", "thread", "external_ref", "status", "attempts", "last_error",
    "next_attempt_at", "sent_at", "created_at",
)


def test_head_is_007():
    from alembic.script import ScriptDirectory
    script = ScriptDirectory.from_config(_alembic_config())
    assert script.get_heads() == ["007"]


def test_migration_007_is_additive_and_leaves_status_check_alone():
    src = (REPO / "alembic" / "versions" / "007_p0_observability.py").read_text()
    assert 'down_revision: Union[str, None] = "006"' in src
    for col in P0_JOB_COLUMNS + P0_TASK_COLUMNS:
        assert f'"{col}"' in src, f"007 must add column {col}"
    assert 'op.create_table(\n        "notifications"' in src
    for col in FORBIDDEN_007_COLUMNS:
        assert f'"{col}"' not in src, f"007 must NOT add column {col} (spec §2.3 r007)"
    assert "ck_jobs_status_valid" not in src          # C16: status CHECK untouched
    assert "drop_column" not in src.split("def downgrade")[0]  # upgrade never drops


def test_models_declare_every_007_column():
    from src.models import Job, Notification, Task
    job_cols = set(Job.__table__.columns.keys())
    task_cols = set(Task.__table__.columns.keys())
    notif_cols = set(Notification.__table__.columns.keys())
    assert set(P0_JOB_COLUMNS) <= job_cols
    assert not (set(FORBIDDEN_007_COLUMNS) & job_cols), "priority is not a 007 column"
    assert set(P0_TASK_COLUMNS) <= task_cols
    assert set(P0_NOTIFICATION_COLUMNS) == notif_cols
    assert Notification.__tablename__ == "notifications"
    for col in P0_JOB_COLUMNS:
        assert Job.__table__.columns[col].nullable, f"{col} must be nullable (additive)"
```

Also change the existing assertion `assert len(revs) >= 5` in `test_revision_chain_walkable` to `assert len(revs) >= 7`.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pipenv run pytest tests/test_migrations.py -v`
Expected: `test_head_is_007` FAILS (`['006'] != ['007']`), `test_migration_007_is_additive...` FAILS with `FileNotFoundError`, `test_models_declare_every_007_column` FAILS with `ImportError: cannot import name 'Notification'`.

- [ ] **Step 3: Add the ORM columns and the `Notification` model**

In `src/models.py`, replace the docstring header `ORM models. Six tables.` with `ORM models. Seven tables.` and add the bullet `- notifications: outbox rows for owner DMs (P0, spec §4.5); delivered by the bot, written by the runner / CLI.`; change the docstring line `{kind, model, effort, outcome, user_rating, tokens_used}` to `{kind, model, effort, outcome, user_rating, input_tokens/output_tokens}`.

Add `Numeric` to the `from sqlalchemy import (...)` list.

In `class Job`, after the `review_outcome` column **and its explanatory comment** (`src/models.py:105-107`; inserting at 106 would orphan the `# ^ "LGTM" | …` comment from its column) add:

```python
    # ── P0 observability + origin (migration 007; every column nullable) ──
    # Spec §2.3 row 007. Stamped by runner/session.py (result capture) and
    # runner/main.py (queue wait, terminal reason); origin_* by the producers
    # (gateway/jobs.py enqueue_job, scheduler). lane/task_class/
    # sensitivity/first_event_at are RESERVED here so P1–P3 need no migration;
    # they stay NULL in P0. There is deliberately NO `priority` column: lanes
    # replace it and `--priority` is never built (spec §2.3 row 007).
    resolved_provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    model_served: Mapped[str | None] = mapped_column(String(64), nullable=True)
    executor: Mapped[str | None] = mapped_column(String(24), nullable=True)
    cli_version: Mapped[str | None] = mapped_column(String(24), nullable=True)
    lane: Mapped[str | None] = mapped_column(String(16), nullable=True)
    origin_channel: Mapped[str | None] = mapped_column(String(16), nullable=True)
    origin_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    origin_thread: Mapped[str | None] = mapped_column(String(64), nullable=True)
    queue_wait_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    first_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    cache_read_tokens: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # Cache writes split by TTL: the subscription writes 1-h entries ($10/M
    # Opus, $6/M Sonnet), and a non-zero 5-m count is the usage-credits
    # signature (spec §2.8 metered-spend tripwires).
    cache_write_1h_tokens: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    cache_write_5m_tokens: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    num_turns: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_api_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd_list: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    terminal_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # ^ ok | max_turns | interrupted | timeout | api_error | rate_limited |
    #   auth_expired | unrecognized_model | error   (runner/result_capture.py)
    task_class: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sensitivity: Mapped[str | None] = mapped_column(String(16), nullable=True)
```

In `class Task`, after `thread_message_id` (line 286) add:

```python
    # P0 origin binding (migration 007). chat_id/thread_message_id above are
    # KEPT (spec §10 "keep columns, stop depending on them"); new code reads
    # origin_* first and falls back to them.
    origin_channel: Mapped[str | None] = mapped_column(String(16), nullable=True)
    origin_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    origin_thread: Mapped[str | None] = mapped_column(String(64), nullable=True)
    awaiting_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # ^ set when status enters awaiting_user/pending_approval, cleared on
    #   active/completed — stuck asks finally have an age (state map §5.24)
```

Append after `class TaskTurn`:

```python
class Notification(Base):
    """Outbox row for an owner-facing notice (P0, spec §4.5 / §2.3 row 007).

    Written by the runner (job terminal + task lifecycle), the bot (quota
    pause/resume) and `python -m src.notify send` (launchd alerters); delivered
    by the bot's outbox listener, which stamps status/attempts/external_ref so
    delivery history is queryable. `target` is the destination chat id (None
    → owner = first TELEGRAM_ALLOWED_CHAT_IDS entry); `thread` the Telegram
    message id to reply under.
    """

    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    notice_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    subject_type: Mapped[str | None] = mapped_column(String(16), nullable=True)   # job | task | schedule | ops
    subject_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    severity: Mapped[str] = mapped_column(String(8), nullable=False, default="info")  # info | warn | critical
    body: Mapped[str] = mapped_column(Text, nullable=False)
    actions: Mapped[dict | None] = mapped_column(JSON, nullable=True)   # {"buttons": [[[label, callback], ...]], ...}
    channel: Mapped[str] = mapped_column(String(16), nullable=False, default="telegram")
    target: Mapped[str | None] = mapped_column(String(64), nullable=True)
    thread: Mapped[str | None] = mapped_column(String(64), nullable=True)
    external_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)  # Telegram message_id once sent
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", index=True)
    # ^ pending | sending | sent | failed | skipped   (`sending` = claimed by one
    #   drainer; next_attempt_at doubles as the 5-min lease expiry — outbox.py)
    attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, index=True
    )
```

- [ ] **Step 4: Write migration 007**

Create `alembic/versions/007_p0_observability.py`:

```python
"""P0 observability + origin + notifications outbox (all additive, nullable).

Spec: docs/superpowers/specs/2026-09-25-multi-model-platform-design.md §2.3
row 007. Adds the ResultMessage columns session.py:1095 used to drop, the
persisted job/task origin that replaces the bot's in-process _job_to_chat
dict, and the notifications outbox. Backfills token columns from
jobs.result->'usage' (642 completed rows on 2026-09-24), provider/executor
for every claude-* row, and origin from created_by. jobs.status and its
CHECK (006) are untouched.

Revision ID: 007
Revises: 006
Create Date: 2026-09-25
"""
from __future__ import annotations
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_JOB_COLUMNS: list[sa.Column] = [
    sa.Column("resolved_provider", sa.String(32), nullable=True),
    sa.Column("model_served", sa.String(64), nullable=True),
    sa.Column("executor", sa.String(24), nullable=True),
    sa.Column("cli_version", sa.String(24), nullable=True),
    sa.Column("lane", sa.String(16), nullable=True),
    sa.Column("origin_channel", sa.String(16), nullable=True),
    sa.Column("origin_ref", sa.String(64), nullable=True),
    sa.Column("origin_thread", sa.String(64), nullable=True),
    sa.Column("queue_wait_ms", sa.Integer, nullable=True),
    sa.Column("first_event_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("input_tokens", sa.BigInteger, nullable=True),
    sa.Column("output_tokens", sa.BigInteger, nullable=True),
    sa.Column("cache_read_tokens", sa.BigInteger, nullable=True),
    # ephemeral_1h / ephemeral_5m, priced at their own rates (spec §2.3 r007).
    sa.Column("cache_write_1h_tokens", sa.BigInteger, nullable=True),
    sa.Column("cache_write_5m_tokens", sa.BigInteger, nullable=True),
    sa.Column("num_turns", sa.Integer, nullable=True),
    sa.Column("duration_api_ms", sa.Integer, nullable=True),
    sa.Column("cost_usd_list", sa.Numeric(10, 4), nullable=True),
    sa.Column("terminal_reason", sa.String(32), nullable=True),
    sa.Column("task_class", sa.String(32), nullable=True),
    sa.Column("sensitivity", sa.String(16), nullable=True),
]

_TASK_COLUMNS: list[sa.Column] = [
    sa.Column("origin_channel", sa.String(16), nullable=True),
    sa.Column("origin_ref", sa.String(64), nullable=True),
    sa.Column("origin_thread", sa.String(64), nullable=True),
    sa.Column("awaiting_since", sa.DateTime(timezone=True), nullable=True),
]

# Backfill tokens from result->'usage' (Anthropic usage keys; see
# session.py _USAGE_TOKEN_KEYS). Only rows whose values are all digit strings
# are touched — anything else stays NULL rather than failing the migration on
# one odd row.
#
# Cache writes split by TTL (spec §2.3 row 007, §2.8): the nested
# usage.cache_creation.ephemeral_{1h,5m}_input_tokens are authoritative. When
# the nested object is absent (older rows) the flat
# cache_creation_input_tokens goes into the 1-h arm and 5-m stays NULL —
# verified against prod's newest 30 job_completed events carrying
# cache_creation: 2,157,923 tokens 1-h, 0 tokens 5-m, and the flat key equal
# to the 1-h figure to the token. Assigning the flat value to 5-m instead
# would misprice every backfilled row by ~40 % (spec: $10/M 1-h Opus vs
# $6.25/M 5-m).
_BACKFILL_TOKENS = """
UPDATE jobs SET
  input_tokens          = NULLIF(result->'usage'->>'input_tokens', '')::bigint,
  output_tokens         = NULLIF(result->'usage'->>'output_tokens', '')::bigint,
  cache_read_tokens     = NULLIF(result->'usage'->>'cache_read_input_tokens', '')::bigint,
  cache_write_1h_tokens = COALESCE(
      NULLIF(result->'usage'->'cache_creation'->>'ephemeral_1h_input_tokens', '')::bigint,
      NULLIF(result->'usage'->>'cache_creation_input_tokens', '')::bigint),
  cache_write_5m_tokens =
      NULLIF(result->'usage'->'cache_creation'->>'ephemeral_5m_input_tokens', '')::bigint
WHERE input_tokens IS NULL
  AND jsonb_typeof(result->'usage') = 'object'
  AND COALESCE(result->'usage'->>'input_tokens', '0') ~ '^[0-9]+$'
  AND COALESCE(result->'usage'->>'output_tokens', '0') ~ '^[0-9]+$'
  AND COALESCE(result->'usage'->>'cache_read_input_tokens', '0') ~ '^[0-9]+$'
  AND COALESCE(result->'usage'->>'cache_creation_input_tokens', '0') ~ '^[0-9]+$'
  AND COALESCE(result->'usage'->'cache_creation'->>'ephemeral_1h_input_tokens', '0') ~ '^[0-9]+$'
  AND COALESCE(result->'usage'->'cache_creation'->>'ephemeral_5m_input_tokens', '0') ~ '^[0-9]+$'
"""

_BACKFILL_PROVIDER = """
UPDATE jobs SET resolved_provider = 'anthropic', executor = 'claude_sdk'
WHERE resolved_provider IS NULL AND resolved_model LIKE 'claude-%'
"""

# NULLIF on both ref arms: a bare `telegram:` (or empty created_by) must give
# origin_ref NULL, exactly what gateway.jobs.origin_from_created_by returns
# for the same input, so backfilled and new rows agree.
_BACKFILL_ORIGIN = """
UPDATE jobs SET
  origin_channel = CASE
    WHEN created_by LIKE 'telegram:%' THEN 'telegram'
    WHEN created_by = 'web'           THEN 'web'
    WHEN created_by = 'scheduler'     THEN 'scheduler'
    ELSE 'system' END,
  origin_ref = CASE
    WHEN created_by LIKE 'telegram:%' THEN NULLIF(LEFT(split_part(created_by, ':', 2), 64), '')
    ELSE NULLIF(LEFT(created_by, 64), '') END
WHERE origin_channel IS NULL
"""

_BACKFILL_TASK_ORIGIN = """
UPDATE tasks SET
  origin_channel = 'telegram',
  origin_ref = chat_id::text,
  origin_thread = thread_message_id::text
WHERE origin_channel IS NULL AND chat_id IS NOT NULL
"""


def upgrade() -> None:
    for col in _JOB_COLUMNS:
        op.add_column("jobs", col)
    for col in _TASK_COLUMNS:
        op.add_column("tasks", col)

    op.create_table(
        "notifications",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("notice_kind", sa.String(32), nullable=False),
        sa.Column("subject_type", sa.String(16), nullable=True),
        sa.Column("subject_id", sa.String(64), nullable=True),
        sa.Column("severity", sa.String(8), nullable=False, server_default="info"),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("actions", JSONB, nullable=True),
        sa.Column("channel", sa.String(16), nullable=False, server_default="telegram"),
        sa.Column("target", sa.String(64), nullable=True),
        sa.Column("thread", sa.String(64), nullable=True),
        sa.Column("external_ref", sa.String(64), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.SmallInteger, nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_notifications_status", "notifications", ["status"])
    op.create_index("ix_notifications_created_at", "notifications", ["created_at"])
    op.create_index("ix_notifications_pending", "notifications", ["status", "created_at"],
                    postgresql_where=sa.text("status = 'pending'"))

    op.execute(_BACKFILL_TOKENS)
    op.execute(_BACKFILL_PROVIDER)
    op.execute(_BACKFILL_ORIGIN)
    op.execute(_BACKFILL_TASK_ORIGIN)


def downgrade() -> None:
    op.drop_index("ix_notifications_pending", table_name="notifications")
    op.drop_index("ix_notifications_created_at", table_name="notifications")
    op.drop_index("ix_notifications_status", table_name="notifications")
    op.drop_table("notifications")
    for col in reversed(_TASK_COLUMNS):
        op.drop_column("tasks", col.name)
    for col in reversed(_JOB_COLUMNS):
        op.drop_column("jobs", col.name)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pipenv run pytest tests/test_migrations.py -v`
Expected: all Layer-1 tests PASS (`test_head_is_007`, `test_migration_007_is_additive...`, `test_models_declare_every_007_column`, `test_single_migration_head`, `test_revision_chain_walkable`); `test_migrations_apply_cleanly` SKIPPED unless `AI_SERVER_RUN_DB_TESTS=1`.

Then run the opt-in apply test once locally (Postgres is up on this box):
Run: `AI_SERVER_RUN_DB_TESTS=1 pipenv run pytest tests/test_migrations.py::test_migrations_apply_cleanly -v`
Expected: PASS (creates a throwaway DB, upgrades to head, drops it).

- [ ] **Step 6: Apply the migration to the dev database**

Run: `pipenv run alembic upgrade head && psql assistant -tAc "SELECT count(*) FROM jobs WHERE input_tokens IS NOT NULL" && psql assistant -tAc "SELECT count(*) FROM jobs WHERE jsonb_typeof(result->'usage')='object'" && psql assistant -tAc "SELECT count(*) FROM jobs WHERE resolved_provider='anthropic'"`
Expected: `Running upgrade 006 -> 007`, then three non-zero counts: the first is close to the second (every completed row with a `result->'usage'` object backfills — all-zero usage passes the digit-regex guard and lands as 0, so the count is ≥ 642, not ≈ 642), and the third ≈ 1500 on the 2026-09-24 baseline. Also `psql assistant -tAc "SELECT count(*) FROM jobs WHERE origin_ref = ''"` → `0` (the NULLIF arms).

- [ ] **Step 7: CHANGELOG + commit**

Prepend to `.context/modules/db/CHANGELOG.md`:

```markdown
## 2026-09-25 — migration 007: P0 observability columns, task origin, notifications outbox

- **Agent task**: multi-model platform P0 (plan `docs/superpowers/plans/2026-09-25-multi-model-platform-p0.md`, Task 1).
- **Files changed**: `alembic/versions/007_p0_observability.py` (new), `src/models.py` (21 nullable Job columns, 4 Task columns, `Notification` model), `tests/test_migrations.py` (head==007, shape + model consistency).
- **Why**: `session.py:1095` dropped num_turns/duration_api_ms/total_cost_usd/model_usage/stop_reason/api_error_status; `models.py` promised a tokens column that did not exist; the bot's `_job_to_chat` dict was the only job→chat binding. Columns first so every later P0 task is a small write.
- **Side effects**: backfills tokens from `result->'usage'`, provider/executor for claude-* rows, origin from created_by. No status/CHECK change (C16). `lane/task_class/sensitivity/first_event_at` stay NULL until P2/P3; there is no `priority` column (spec §2.3 row 007).
- **Gotchas discovered**: `jobs.result` is JSONB in the DB (migration 001) although models.py declares `JSON` — `->>` works either way; the backfill guards every value with a digit regex so one odd row cannot fail the migration.
```

```bash
git add alembic/versions/007_p0_observability.py src/models.py tests/test_migrations.py .context/modules/db/CHANGELOG.md
git commit -m "feat(db): migration 007 — P0 observability columns, task origin, notifications outbox (additive)"
```

---

### Task 2: `result_capture.py` — typed `ResultMessage` capture + terminal reason (pure)


**Execution position:** 4 of 21 — previous: Task 18, next: Task 3 (see Global Constraints "Execution order").

**Files:**
- Create: `src/runner/result_capture.py`
- Modify: `.context/modules/runner/CHANGELOG.md`, `.context/modules/runner/CONTEXT.md` (Paths line — `check_runner_context` goes red the moment the file exists), `.context/SYSTEM.md` (module-graph row)
- Test: `tests/test_result_capture.py`

**Interfaces:**
- Consumes: nothing (no SDK import — takes any object with the `ResultMessage` attribute names).
- Produces (all pure, consumed by Tasks 3, 12):
  - `@dataclass(frozen=True) class ResultCapture` with fields `subtype: str, is_error: bool, num_turns: int | None, duration_ms: int | None, duration_api_ms: int | None, total_cost_usd: float | None, stop_reason: str | None, api_error_status: int | None, usage: dict, model_usage: dict, permission_denials: int, result_text: str, errors: tuple[str, ...]` and properties `input_tokens, output_tokens, cache_read_tokens, cache_write_1h_tokens, cache_write_5m_tokens: int`, `usage_empty: bool`, `model_served: str | None`. The two cache-write properties read `usage["cache_creation"]["ephemeral_{1h,5m}_input_tokens"]` and fall back to the flat `cache_creation_input_tokens` **into the 1-h arm only** when the nested object is absent (spec §2.3 row 007 / §2.8: the subscription's TTL is 1 h, prod records 100 % of writes there, and a non-zero 5-m reading is the usage-credits signature).
  - `capture_result_message(message: Any) -> ResultCapture`
  - `derive_terminal_reason(capture: ResultCapture, *, banner_terminal: bool = False) -> str`
  - `served_model_violation(capture: ResultCapture, requested_model: str, final_text: str) -> str | None`
  - `result_columns(capture: ResultCapture, *, terminal_reason: str, cli_version: str | None) -> dict[str, Any]`
  - `terminal_reason_for_exception(exc: BaseException) -> str`
  - `parse_cli_version(text: str) -> str`
  - `same_model(served: str, requested: str) -> bool`
  - `requested_matches_served(served: str, requested: str) -> bool` (`same_model` OR a bare hyphen-bounded alias such as `sonnet` / `opus-4-7` inside the served id)
  - `TERMINAL_REASONS: tuple[str, ...]`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_result_capture.py`:

```python
"""
Pure tests for src/runner/result_capture.py — the typed ResultMessage capture
that replaces `usage = getattr(message, "usage", {})` (session.py:1095).

No SDK import: a SimpleNamespace with the ResultMessage field names
(claude_agent_sdk/types.py:1143-1166, SDK 0.1.81) stands in for the message.

Run: pipenv run pytest tests/test_result_capture.py -v
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from src.runner.result_capture import (
    TERMINAL_REASONS,
    ResultCapture,
    capture_result_message,
    derive_terminal_reason,
    parse_cli_version,
    result_columns,
    same_model,
    served_model_violation,
    terminal_reason_for_exception,
)

# Real prod shape (verified on prod's audit log 2026-09-27): the nested
# cache_creation object carries the TTL split and the flat
# cache_creation_input_tokens equals the 1-h figure to the token.
REAL_USAGE = {
    "input_tokens": 15, "output_tokens": 9363,
    "cache_read_input_tokens": 379675, "cache_creation_input_tokens": 12000,
    "cache_creation": {"ephemeral_1h_input_tokens": 12000,
                       "ephemeral_5m_input_tokens": 0},
    "server_tool_use": {"web_search_requests": 0}, "service_tier": "standard",
}
# An older row with no nested object: the flat count must land in the 1-h arm.
LEGACY_USAGE = {
    "input_tokens": 15, "output_tokens": 9363,
    "cache_read_input_tokens": 379675, "cache_creation_input_tokens": 12000,
}
# The credits signature: TTL dropped to 5 m (spec §2.8 metered-spend tripwires).
FIVE_MIN_USAGE = dict(REAL_USAGE, cache_creation={
    "ephemeral_1h_input_tokens": 0, "ephemeral_5m_input_tokens": 12000})
ZERO_USAGE = {"input_tokens": 0, "output_tokens": 0,
              "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}


def _msg(**over):
    base = dict(
        subtype="success", duration_ms=201000, duration_api_ms=180500, is_error=False,
        num_turns=12, session_id="s", stop_reason="end_turn", total_cost_usd=0.0812,
        usage=REAL_USAGE, result="TASK_COMPLETE: done", structured_output=None,
        model_usage={"claude-sonnet-4-6": {"inputTokens": 15, "outputTokens": 9363}},
        permission_denials=[], errors=None, api_error_status=None, uuid="u",
    )
    base.update(over)
    return SimpleNamespace(**base)


class TestCapture:
    def test_full_message_captured(self):
        cap = capture_result_message(_msg())
        assert cap.num_turns == 12
        assert cap.duration_api_ms == 180500
        assert cap.total_cost_usd == pytest.approx(0.0812)
        assert cap.input_tokens == 15 and cap.output_tokens == 9363
        assert cap.cache_read_tokens == 379675
        assert cap.cache_write_1h_tokens == 12000 and cap.cache_write_5m_tokens == 0
        assert cap.model_served == "claude-sonnet-4-6"
        assert cap.usage_empty is False
        assert cap.permission_denials == 0

    def test_ephemeral_1h_is_the_1h_arm_and_the_flat_key_falls_back_to_it(self):
        # Spec §9 P0 test gate: "the 1-h cache-write rate is used when
        # ephemeral_1h_input_tokens > 0" — the split has to survive capture,
        # and a legacy row with no nested object must not be priced at 5 m.
        assert capture_result_message(_msg()).cache_write_1h_tokens == 12000
        legacy = capture_result_message(_msg(usage=LEGACY_USAGE))
        assert legacy.cache_write_1h_tokens == 12000
        assert legacy.cache_write_5m_tokens == 0

    def test_five_minute_writes_are_reported_separately(self):
        # A non-zero 5-m count is the usage-credits signature (spec §2.8), so it
        # must never be folded into the 1-h column.
        cap = capture_result_message(_msg(usage=FIVE_MIN_USAGE))
        assert cap.cache_write_1h_tokens == 0 and cap.cache_write_5m_tokens == 12000

    def test_missing_optional_fields_default(self):
        # An older CLI shape: no model_usage/api_error_status/permission_denials attrs at all.
        cap = capture_result_message(SimpleNamespace(subtype="success", is_error=False,
                                                     usage=ZERO_USAGE, result=""))
        assert cap.model_usage == {} and cap.model_served is None
        assert cap.api_error_status is None and cap.num_turns is None
        assert cap.usage_empty is True

    def test_non_dict_usage_is_ignored(self):
        cap = capture_result_message(_msg(usage="garbage", model_usage=None))
        assert cap.usage == {} and cap.model_usage == {}


class TestTerminalReason:
    def test_vocabulary_matches_spec(self):
        assert TERMINAL_REASONS == ("ok", "max_turns", "interrupted", "timeout", "api_error",
                                    "rate_limited", "auth_expired", "unrecognized_model", "error")

    @pytest.mark.parametrize("over,expected", [
        ({}, "ok"),
        ({"api_error_status": 529, "is_error": True}, "api_error"),
        ({"api_error_status": 500, "is_error": True}, "api_error"),
        ({"api_error_status": 429, "is_error": True}, "rate_limited"),
        ({"api_error_status": 401, "is_error": True}, "auth_expired"),
        ({"api_error_status": 403, "is_error": True}, "auth_expired"),
        ({"subtype": "error_max_turns", "is_error": True}, "max_turns"),
        ({"subtype": "error_during_execution", "is_error": True}, "error"),
    ])
    def test_typed_fields_drive_reason(self, over, expected):
        assert derive_terminal_reason(capture_result_message(_msg(**over))) == expected

    def test_banner_belt_when_typed_fields_silent(self):
        # The 143c8cfb shape: is_error unset, no api_error_status, banner text.
        cap = capture_result_message(_msg(usage=ZERO_USAGE, result="API Error: 529 Overloaded."))
        assert derive_terminal_reason(cap, banner_terminal=True) == "api_error"
        assert derive_terminal_reason(cap, banner_terminal=False) == "ok"

    def test_every_reason_fits_column(self):
        assert all(len(r) <= 32 for r in TERMINAL_REASONS)


class TestServedModel:
    def test_matching_model_is_ok(self):
        assert served_model_violation(capture_result_message(_msg()),
                                      "claude-sonnet-4-6", "text") is None

    def test_date_suffixed_served_id_matches_requested_family(self):
        cap = capture_result_message(_msg(model_usage={"claude-opus-4-7-20260301": {}}))
        assert served_model_violation(cap, "claude-opus-4-7", "text") is None

    def test_wrong_served_model_is_rejected(self):
        cap = capture_result_message(_msg(model_usage={"claude-sonnet-4-6": {}}))
        v = served_model_violation(cap, "claude-opus-5-5", "text")
        assert v is not None and "claude-opus-5-5" in v

    def test_bare_alias_request_is_not_rejected(self):
        # POST /api/jobs and the dispatch MCP pass free-text model strings
        # through unvalidated (state map §2.3/§2.4); the CLI accepts family
        # aliases and reports the canonical id in modelUsage. A job that ran
        # correctly on `sonnet` must not fail as unrecognized_model.
        cap = capture_result_message(_msg(model_usage={"claude-sonnet-4-6": {}}))
        assert served_model_violation(cap, "sonnet", "text") is None
        cap = capture_result_message(_msg(model_usage={"claude-opus-4-7-20260301": {}}))
        assert served_model_violation(cap, "opus-4-7", "text") is None
        assert served_model_violation(cap, "sonnet", "text") is not None

    def test_zero_usage_with_text_and_api_duration_is_ok(self):
        # Review Focus 3: short chat jobs often report all-zero usage but real text.
        cap = capture_result_message(_msg(usage=ZERO_USAGE, model_usage={}))
        assert served_model_violation(cap, "claude-sonnet-4-6", "The answer is 42.") is None

    def test_missing_model_usage_with_real_usage_is_ok(self):
        # Review Focus 5: SDK 0.1.81 ResultMessage without modelUsage → absent ≠ wrong.
        cap = capture_result_message(_msg(model_usage=None))
        assert served_model_violation(cap, "claude-sonnet-4-6", "TASK_COMPLETE: x") is None

    def test_missing_model_usage_and_empty_everything_is_rejected(self):
        # The silent-empty-success trap (claude-anthropic.md §7): unknown id →
        # no text, zero usage, zero api time, no error flag.
        cap = capture_result_message(_msg(model_usage=None, usage=ZERO_USAGE,
                                          duration_api_ms=0, result=""))
        v = served_model_violation(cap, "claude-opus-5-5", "")
        assert v is not None and "empty" in v

    def test_present_model_usage_but_no_api_time_and_no_usage_is_rejected(self):
        cap = capture_result_message(_msg(usage=ZERO_USAGE, duration_api_ms=0))
        assert served_model_violation(cap, "claude-sonnet-4-6", "") is not None


class TestColumnsAndHelpers:
    def test_result_columns_shape(self):
        cols = result_columns(capture_result_message(_msg()), terminal_reason="ok",
                              cli_version="2.1.139")
        assert cols == {
            "resolved_provider": "anthropic", "executor": "claude_sdk",
            "cli_version": "2.1.139", "model_served": "claude-sonnet-4-6",
            "input_tokens": 15, "output_tokens": 9363, "cache_read_tokens": 379675,
            "cache_write_1h_tokens": 12000, "cache_write_5m_tokens": 0,
            "num_turns": 12, "duration_api_ms": 180500,
            "cost_usd_list": pytest.approx(0.0812), "terminal_reason": "ok",
        }

    def test_result_columns_cli_version_none_when_unknown(self):
        cols = result_columns(capture_result_message(_msg()), terminal_reason="ok", cli_version="")
        assert cols["cli_version"] is None

    @pytest.mark.parametrize("exc,expected", [
        (asyncio.TimeoutError(), "timeout"),
        (asyncio.CancelledError(), "interrupted"),
        (RuntimeError("unrecognized_model: silent empty success — x"), "unrecognized_model"),
        (RuntimeError("API terminal error (session produced no work): API Error: 529"), "api_error"),
        (RuntimeError("workspace creation failed for a workspace-tier job: boom"), "error"),
        (RuntimeError("session error (error_during_execution): 401 unauthorized auth expired"), "auth_expired"),
    ])
    def test_exception_mapping(self, exc, expected):
        assert terminal_reason_for_exception(exc) == expected

    def test_quota_exhausted_maps_to_rate_limited(self):
        from src.runner.quota import QuotaExhausted
        assert terminal_reason_for_exception(QuotaExhausted(None, "x")) == "rate_limited"

    def test_parse_cli_version(self):
        assert parse_cli_version("2.1.139 (Claude Code)\n") == "2.1.139"
        assert parse_cli_version("") == "unknown"
        assert len(parse_cli_version("x" * 100)) <= 24

    def test_same_model_prefix_rules(self):
        assert same_model("claude-sonnet-4-6", "claude-sonnet-4-6")
        assert same_model("claude-sonnet-4-6-20260101", "claude-sonnet-4-6")
        assert same_model("CLAUDE-SONNET-4-6", "claude-sonnet-4-6")
        assert not same_model("claude-sonnet-4-6", "claude-opus-4-7")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pipenv run pytest tests/test_result_capture.py -v`
Expected: collection error `ModuleNotFoundError: No module named 'src.runner.result_capture'`.

- [ ] **Step 3: Implement `src/runner/result_capture.py`**

```python
"""
Typed capture of the Claude Agent SDK `ResultMessage` (P0; spec §2.4 / §2.7).

Pure functions only — no SDK import, no I/O — so the terminal-reason and
served-model logic is testable with a fake message. Wiring:
  - session._run_in_process → capture_result_message + served_model_violation
  - session.run_session     → derive_terminal_reason + result_columns
  - main._process_job       → terminal_reason_for_exception on failure branches
  - runner/canary.py        → same_model

Field names are those of claude_agent_sdk/types.py:1143-1166 (SDK 0.1.81):
subtype, duration_ms, duration_api_ms, is_error, num_turns, stop_reason,
total_cost_usd, usage, result, model_usage (CLI key `modelUsage`),
permission_denials, errors, api_error_status. Every read is getattr-with-
default so an older/newer CLI shape degrades to NULL columns, never a crash.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

TERMINAL_REASONS: tuple[str, ...] = (
    "ok", "max_turns", "interrupted", "timeout", "api_error",
    "rate_limited", "auth_expired", "unrecognized_model", "error",
)

_USAGE_KEYS = ("input_tokens", "output_tokens",
               "cache_read_input_tokens", "cache_creation_input_tokens")


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _opt_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _opt_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class ResultCapture:
    subtype: str = "success"
    is_error: bool = False
    num_turns: int | None = None
    duration_ms: int | None = None
    duration_api_ms: int | None = None
    total_cost_usd: float | None = None
    stop_reason: str | None = None
    api_error_status: int | None = None
    usage: dict[str, Any] = field(default_factory=dict)
    model_usage: dict[str, Any] = field(default_factory=dict)
    permission_denials: int = 0
    result_text: str = ""
    errors: tuple[str, ...] = ()

    @property
    def input_tokens(self) -> int:
        return _int(self.usage.get("input_tokens"))

    @property
    def output_tokens(self) -> int:
        return _int(self.usage.get("output_tokens"))

    @property
    def cache_read_tokens(self) -> int:
        return _int(self.usage.get("cache_read_input_tokens"))

    @property
    def _cache_creation(self) -> dict:
        nested = self.usage.get("cache_creation")
        return nested if isinstance(nested, dict) else {}

    @property
    def cache_write_1h_tokens(self) -> int:
        """1-hour cache writes — the TTL the subscription actually uses.

        usage.cache_creation.ephemeral_1h_input_tokens when present; the flat
        cache_creation_input_tokens otherwise (older rows), because the
        subscription's TTL is 1 h and prod records 100 % of writes there
        (spec §2.3 row 007, §2.8). Pricing the flat value at the 5-m rate was
        round 1's ~19 % error.
        """
        nested = self._cache_creation
        if "ephemeral_1h_input_tokens" in nested or "ephemeral_5m_input_tokens" in nested:
            return _int(nested.get("ephemeral_1h_input_tokens"))
        return _int(self.usage.get("cache_creation_input_tokens"))

    @property
    def cache_write_5m_tokens(self) -> int:
        """5-minute cache writes — 0 on this account; non-zero is the
        usage-credits signature (spec §2.8 metered-spend tripwires)."""
        return _int(self._cache_creation.get("ephemeral_5m_input_tokens"))

    @property
    def usage_empty(self) -> bool:
        """Same signature as session.usage_is_empty: all four counters zero."""
        return not any(_int(self.usage.get(k)) > 0 for k in _USAGE_KEYS)

    @property
    def model_served(self) -> str | None:
        return next(iter(self.model_usage), None) if self.model_usage else None


def capture_result_message(message: Any) -> ResultCapture:
    """Read every field of a ResultMessage-shaped object (getattr, defaulted)."""
    usage = getattr(message, "usage", None)
    model_usage = getattr(message, "model_usage", None)
    denials = getattr(message, "permission_denials", None) or []
    errors = getattr(message, "errors", None) or []
    return ResultCapture(
        subtype=str(getattr(message, "subtype", "") or "success"),
        is_error=bool(getattr(message, "is_error", False)),
        num_turns=_opt_int(getattr(message, "num_turns", None)),
        duration_ms=_opt_int(getattr(message, "duration_ms", None)),
        duration_api_ms=_opt_int(getattr(message, "duration_api_ms", None)),
        total_cost_usd=_opt_float(getattr(message, "total_cost_usd", None)),
        stop_reason=getattr(message, "stop_reason", None),
        api_error_status=_opt_int(getattr(message, "api_error_status", None)),
        usage=dict(usage) if isinstance(usage, dict) else {},
        model_usage=dict(model_usage) if isinstance(model_usage, dict) else {},
        permission_denials=len(denials) if isinstance(denials, (list, tuple)) else 0,
        result_text=str(getattr(message, "result", "") or ""),
        errors=tuple(str(e) for e in errors),
    )


def derive_terminal_reason(capture: ResultCapture, *, banner_terminal: bool = False) -> str:
    """Typed terminal reason. `banner_terminal` is session.is_api_terminal_session(...)
    — the regex belt kept for one release (spec §2.4: 'kept as a belt')."""
    status = capture.api_error_status
    if status == 429:
        return "rate_limited"
    if status in (401, 403):
        return "auth_expired"
    if status is not None and status >= 500:
        return "api_error"
    if capture.subtype == "error_max_turns" or capture.stop_reason == "max_turns":
        return "max_turns"
    if capture.is_error:
        return "error"
    if banner_terminal:
        return "api_error"
    return "ok"


def same_model(served: str, requested: str) -> bool:
    """Case-insensitive family match: exact, or one id is a prefix of the other
    (the CLI may report a date-suffixed id for an un-suffixed request)."""
    s, r = (served or "").lower(), (requested or "").lower()
    return bool(s) and bool(r) and (s == r or s.startswith(r) or r.startswith(s))


def requested_matches_served(served: str, requested: str) -> bool:
    """same_model, OR a bare family alias the CLI expanded itself: `sonnet`,
    `opus-4-7` (hyphen-bounded token inside the served id). Needed because
    POST /api/jobs (web.py:388-389) and the dispatch MCP pass free-text model
    strings through unvalidated; Telegram expands aliases before enqueue and
    every SKILL.md uses a full id, so this only widens the web/dispatch path."""
    if same_model(served, requested):
        return True
    s, r = (served or "").lower(), (requested or "").lower().strip()
    if not s or not r or r.startswith("claude-"):
        return False
    return f"-{r}-" in f"-{s}-"


def served_model_violation(capture: ResultCapture, requested_model: str,
                           final_text: str) -> str | None:
    """The silent-empty-success trap (spec §0a row 6; claude-anthropic.md §7):
    the pinned CLI may answer an unknown model id with a 'success' that has no
    text, zero usage and zero API time. Returns a reason string to fail the
    job with, or None.

    Two regimes, deliberately different:
      * model_usage PRESENT: the requested family (full id or bare alias, see
        requested_matches_served) must appear in it, and a present-but-zero
        result (no API time AND empty usage) is rejected.
      * model_usage ABSENT (older shape): reject only the fully empty
        signature — no text, empty usage, zero API time. All-zero usage WITH
        text (common on short chat jobs) stays a success.
    """
    api_ms = capture.duration_api_ms or 0
    if capture.model_usage:
        if not any(requested_matches_served(k, requested_model) for k in capture.model_usage):
            return (f"model_usage {sorted(capture.model_usage)} does not contain "
                    f"requested {requested_model}")
        if api_ms <= 0 and capture.usage_empty:
            return "model_usage present but duration_api_ms=0 and usage empty"
        return None
    if not (final_text or "").strip() and capture.usage_empty and api_ms <= 0:
        return "empty result: no text, zero usage, duration_api_ms=0 (unknown model id?)"
    return None


def result_columns(capture: ResultCapture, *, terminal_reason: str,
                   cli_version: str | None) -> dict[str, Any]:
    """The jobs-row UPDATE payload for a finished session (migration 007 columns)."""
    return {
        "resolved_provider": "anthropic",
        "executor": "claude_sdk",
        "cli_version": (cli_version or None),
        "model_served": capture.model_served,
        "input_tokens": capture.input_tokens,
        "output_tokens": capture.output_tokens,
        "cache_read_tokens": capture.cache_read_tokens,
        "cache_write_1h_tokens": capture.cache_write_1h_tokens,
        "cache_write_5m_tokens": capture.cache_write_5m_tokens,
        "num_turns": capture.num_turns,
        "duration_api_ms": capture.duration_api_ms,
        "cost_usd_list": capture.total_cost_usd,
        "terminal_reason": terminal_reason,
    }


def terminal_reason_for_exception(exc: BaseException) -> str:
    """Map the exceptions main._process_job catches onto TERMINAL_REASONS."""
    name = type(exc).__name__
    if isinstance(exc, asyncio.TimeoutError) or name == "TimeoutError":
        return "timeout"
    if isinstance(exc, asyncio.CancelledError):
        return "interrupted"
    if name == "QuotaExhausted":
        return "rate_limited"
    text = str(exc).lower()
    if "unrecognized_model" in text:
        return "unrecognized_model"
    if "api terminal error" in text:
        return "api_error"
    if ("auth" in text and any(t in text for t in ("401", "403", "expired", "unauthorized"))):
        return "auth_expired"
    return "error"


def parse_cli_version(text: str) -> str:
    """'2.1.139 (Claude Code)' → '2.1.139'; fits the String(24) column."""
    first = (text or "").strip().split()
    if not first:
        return "unknown"
    return first[0][:24]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pipenv run pytest tests/test_result_capture.py -v`
Expected: 35 PASS (TestCapture 5 — the three original plus the two named cache-write-TTL cases, TestTerminalReason 11, TestServedModel 8, TestColumnsAndHelpers 11), 0 failed.

- [ ] **Step 5: Docs the lint gate needs, CHANGELOG, commit**

`check_runner_context` (scripts/lint_docs.py:96-111 → `tests/test_doc_lint.py::test_runner_context_complete`) fails as soon as `src/runner/result_capture.py` exists unless the runner CONTEXT.md names it, so both doc edits ride this commit:

- `.context/modules/runner/CONTEXT.md`: append `` , `src/runner/result_capture.py` `` to the `**Paths:**` line.
- `.context/SYSTEM.md` module graph (keep the four columns), insert after the `src/runner/session.py` row:

```markdown
| `src/runner/result_capture.py` | Typed ResultMessage capture, terminal_reason, silent-empty-success check (pure) | — | runner.session, runner.main, runner.canary |
```

Run: `pipenv run pytest tests/test_doc_lint.py -q && pipenv run python scripts/lint_docs.py` → Expected: PASS and `All clean!`.

Prepend to `.context/modules/runner/CHANGELOG.md`:

```markdown
## 2026-09-25 — result_capture: typed ResultMessage capture + terminal_reason (pure)

- **Agent task**: multi-model P0, Task 2 (plan `docs/superpowers/plans/2026-09-25-multi-model-platform-p0.md`).
- **Files changed**: `src/runner/result_capture.py` (new; `ResultCapture`, `capture_result_message`, `derive_terminal_reason`, `served_model_violation`, `result_columns`, `terminal_reason_for_exception`, `parse_cli_version`, `same_model`, `requested_matches_served`), `tests/test_result_capture.py` (35 pure cases, incl. the spec's named 1-h cache-write gate), runner `CONTEXT.md` Paths line, `SYSTEM.md` module-graph row.
- **Why**: `session.py:1095` read only `usage/is_error/subtype/result/errors`; `num_turns`, `duration_api_ms`, `total_cost_usd`, `model_usage`, `stop_reason`, `api_error_status` were dropped and terminal-failure detection was a banner regex. This module is the typed replacement; the regex stays as a belt.
- **Side effects**: none yet — not wired until Task 3.
- **Gotchas discovered**: all-zero usage with real text is a NORMAL chat-job shape; the served-model assertion must only reject the fully-empty signature when `model_usage` is absent. The web/dispatch launch paths pass bare aliases (`sonnet`) through unvalidated, so the served-model check accepts a hyphen-bounded alias inside the served id.
```

```bash
git add src/runner/result_capture.py tests/test_result_capture.py .context/modules/runner/CHANGELOG.md .context/modules/runner/CONTEXT.md .context/SYSTEM.md
git commit -m "feat(runner): result_capture — typed ResultMessage capture, terminal_reason, silent-empty-success check (pure)"
```

---

### Task 3: Wire capture into `session.py` / `main.py` / `web.py` — columns, `job_completed` fields, silent-empty-success rejection, `queue_wait_ms`


**Execution position:** 5 of 21 — previous: Task 2, next: Task 19 (see Global Constraints "Execution order"). Tasks 19, 20 and 15 all edit the functions this task touches, so their anchors must be re-located by symbol.

**Files:**
- Modify: `src/runner/session.py:46-66` (imports), `:471` (`_DEFAULT_BUDGET`, `cli_version()` goes after it), `:864` (`run_session` — stamping at `:975-983`, the `_run_in_process` call at `:1003`, `job_completed` + return at `:1019-1033`), `:1048-1130` (`_run_in_process`)
- Modify: `src/runner/main.py:333-335` (`_process_job` running flip), `:364-366` (preflight failure), `:460-511` (SkillResolutionError / DeployRefused / DeployNeedsApproval branches — the audit+finish pairs are at `:481-483` and `:502-504`), `:513-551` (timeout + generic failure branches), `:1269-1300` (`_finish_job`). **`_check_subscription_auth` is NOT touched** — `cli_version()` no longer spawns anything, so there is nothing to warm.
- Modify: `src/gateway/web.py:85-100` (`JobOut`), `:107-124` (`_serialize`)
- Modify: `.context/modules/runner/CHANGELOG.md`, `.context/modules/gateway/CHANGELOG.md`, `.context/SYSTEM.md` (Depends-on cells of `session.py` / `main.py` gain `runner.result_capture` — `check_module_graph_imports` flags the new import otherwise)
- Test: `tests/test_result_capture.py` (append), `tests/test_job_visibility.py` (append), `tests/test_timeout_escalation.py` (append)

**Interfaces:**
- Consumes: Task 1 columns; Task 2 functions.
- Produces:
  - `session._run_in_process(job_id, prompt, options) -> tuple[str, dict, ResultCapture]` (was 2-tuple; only `run_session` calls it).
  - `session.cli_version() -> str` (`lru_cache`; `"unknown"` on failure) — **reads `claude_agent_sdk._cli_version.__cli_version__`, no subprocess and no `SystemMessage` parse** (spec §2.3 row 007 states the column exactly that way; round-2 #58: "`cli_version` needed no subprocess"). Verified in the pinned wheel during Step 1: `pipenv run python -c "from claude_agent_sdk import _cli_version; print(_cli_version.__cli_version__)"` → `2.1.139`, module path `…/site-packages/claude_agent_sdk/_cli_version.py`. Because nothing is spawned there is no cold start to hide and no startup warm-up: `main._check_subscription_auth` is left alone. `parse_cli_version` stays as the length/normalisation helper (the canary reuses it on CLI banner text).
  - `run_session` return dict gains keys `terminal_reason: str`, `model_served: str | None`, `num_turns: int | None` (existing keys unchanged).
  - `main._finish_job(job_id, status, *, result=None, error=None, terminal_reason: str | None = None)`.
  - `main.queue_wait_ms(created_at, started_at) -> int | None` (pure).
  - `job_completed` audit event gains `terminal_reason, num_turns, duration_api_ms, model_served, cost_usd_list, stop_reason`; `job_failed` gains `terminal_reason` on EVERY failure branch of `_process_job` (preflight `"error"`, SkillResolutionError / DeployRefused / DeployNeedsApproval `"error"`, timeout `"timeout"`, generic `terminal_reason_for_exception(exc)`), and every `_finish_job(..., JobStatus.failed, ...)` call passes it (AST-pinned).
  - `_process_job`'s timeout and generic branches skip `_maybe_escalate` when the refetched job is already `cancelled` (a `/cancel` that interrupts a session before its first API call now trips the silent-empty check; escalating a job the owner just cancelled is wrong).
  - New audit kind `job_result_rejected{reason, detail, requested_model}` (a P0 addition beyond spec §2.7's added-kinds list — recorded in the runner CONTEXT.md, Task 14).
  - `JobOut` gains `model_served, terminal_reason, num_turns, duration_api_ms, input_tokens, output_tokens, cache_read_tokens, cost_usd_list, origin_channel, queue_wait_ms` (all Optional).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_result_capture.py`:

```python
class TestSessionWiring:
    def test_run_in_process_signature_returns_capture(self):
        import inspect
        from src.runner import session
        sig = inspect.signature(session._run_in_process)
        assert str(sig.return_annotation).endswith("tuple[str, dict[str, Any], ResultCapture]")

    def test_cli_version_comes_from_the_sdk_package_not_a_subprocess(self, monkeypatch):
        # Spec §2.3 row 007: "= claude_agent_sdk._cli_version.__cli_version__
        # … no subprocess or SystemMessage parse". Verified against the pinned
        # wheel: the attribute is "2.1.139".
        from claude_agent_sdk import _cli_version
        from src.runner import session
        session.cli_version.cache_clear()
        monkeypatch.setattr(_cli_version, "__cli_version__", "2.1.140", raising=False)
        assert session.cli_version() == "2.1.140"
        assert session.cli_version() == "2.1.140"        # cached
        session.cli_version.cache_clear()

    def test_cli_version_is_short_and_unknown_when_the_attribute_is_gone(self, monkeypatch):
        from claude_agent_sdk import _cli_version
        from src.runner import session
        session.cli_version.cache_clear()
        monkeypatch.delattr(_cli_version, "__cli_version__", raising=False)
        assert session.cli_version() == "unknown"
        session.cli_version.cache_clear()
        monkeypatch.setattr(_cli_version, "__cli_version__", "x" * 100, raising=False)
        assert len(session.cli_version()) <= 24
        session.cli_version.cache_clear()

    def test_session_spawns_no_subprocess_for_the_cli_version(self):
        # The subprocess apparatus round 1 planned here is gone; a future
        # reader must not reintroduce it (spec §2.3 row 007).
        import inspect
        from src.runner import session
        assert "subprocess" not in inspect.getsource(session.cli_version)


class TestMainWiring:
    def test_queue_wait_ms(self):
        from datetime import datetime, timedelta, timezone
        from src.runner.main import queue_wait_ms
        t0 = datetime(2026, 9, 25, 12, 0, tzinfo=timezone.utc)
        assert queue_wait_ms(t0, t0 + timedelta(seconds=2.5)) == 2500
        assert queue_wait_ms(None, t0) is None
        assert queue_wait_ms(t0 + timedelta(seconds=5), t0) == 0   # clock skew never negative

    def test_finish_job_accepts_terminal_reason(self):
        import inspect
        from src.runner.main import _finish_job
        assert "terminal_reason" in inspect.signature(_finish_job).parameters

    def test_every_failed_finish_passes_terminal_reason(self):
        # Source-level pin (same style as tests/test_timeout_escalation.py):
        # every `_finish_job(<id>, JobStatus.failed, ...)` in _process_job
        # carries terminal_reason=, so no failed job is left with NULL.
        import ast
        from pathlib import Path
        src = (Path(__file__).resolve().parent.parent / "src" / "runner" / "main.py").read_text()
        tree = ast.parse(src)
        process_job = next(n for n in ast.walk(tree)
                           if isinstance(n, ast.AsyncFunctionDef) and n.name == "_process_job")
        sites = [n for n in ast.walk(process_job)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                 and n.func.id == "_finish_job" and len(n.args) >= 2
                 and ast.unparse(n.args[1]) == "JobStatus.failed"]
        assert len(sites) >= 6, "expected preflight + 3 typed + timeout + generic"
        for call in sites:
            assert any(k.arg == "terminal_reason" for k in call.keywords), ast.unparse(call)
```

Append to `tests/test_job_visibility.py` (a pure test file — it imports `src.runner.main` only, so the appended test imports `JobOut` itself):

```python
def test_jobout_carries_p0_columns():
    from src.gateway.web import JobOut
    fields = set(JobOut.model_fields)
    assert {"model_served", "terminal_reason", "num_turns", "duration_api_ms",
            "input_tokens", "output_tokens", "cache_read_tokens", "cost_usd_list",
            "origin_channel", "queue_wait_ms"} <= fields
```

Append to `tests/test_timeout_escalation.py` (reuses its `_awaited_names` / `_timeout_handler` helpers and `MAIN`):

```python
def _generic_handler() -> ast.ExceptHandler:
    """The top-level `except Exception as exc` of _process_job (the one that
    awaits _finish_job) — not the nested ones around escalation."""
    tree = ast.parse(MAIN.read_text())
    process_job = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.AsyncFunctionDef) and n.name == "_process_job"
    )
    for node in ast.walk(process_job):
        if (isinstance(node, ast.ExceptHandler) and isinstance(node.type, ast.Name)
                and node.type.id == "Exception" and node.name == "exc"
                and "_finish_job" in _awaited_names(node.body)):
            return node
    raise AssertionError("_process_job has no generic `except Exception as exc` handler")


def _returns_when_cancelled(handler: ast.ExceptHandler) -> bool:
    for node in ast.walk(ast.Module(body=handler.body, type_ignores=[])):
        if isinstance(node, ast.If) and "cancelled" in ast.unparse(node.test):
            if any(isinstance(n, ast.Return) for n in ast.walk(node)):
                return True
    return False


class TestCancelledGuard:
    def test_cancelled_job_is_not_escalated(self):
        # P0: /cancel before the first API call now trips the silent-empty
        # check → generic branch; the refetched row is `cancelled` and must
        # short-circuit before _maybe_escalate (main.py:704-740 has no guard).
        assert _returns_when_cancelled(_timeout_handler())
        assert _returns_when_cancelled(_generic_handler())
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pipenv run pytest tests/test_result_capture.py::TestSessionWiring tests/test_result_capture.py::TestMainWiring tests/test_job_visibility.py::test_jobout_carries_p0_columns tests/test_timeout_escalation.py::TestCancelledGuard -v`
Expected: 9 FAIL (`AttributeError: module 'src.runner.session' has no attribute 'cli_version'` ×3, `ImportError: cannot import name 'queue_wait_ms'`, missing `terminal_reason` parameter, no `_finish_job(..., JobStatus.failed` site passes `terminal_reason`, JobOut assertion, no cancelled guard in either handler, `_run_in_process` return annotation still a 2-tuple).

- [ ] **Step 3: Wire `session.py`**

Add imports near line 46-66 of `src/runner/session.py`:

```python
import functools

from src.runner.result_capture import (
    ResultCapture,
    capture_result_message,
    derive_terminal_reason,
    parse_cli_version,
    result_columns,
    served_model_violation,
)
```

Add after `_DEFAULT_BUDGET = 200_000` (line 471):

```python
@functools.lru_cache(maxsize=1)
def cli_version() -> str:
    """Version of the SDK-bundled Claude CLI (stamped into jobs.cli_version).

    Read from the SDK package itself — `claude_agent_sdk._cli_version.
    __cli_version__` ("2.1.139" in the pinned 0.1.81 wheel) — NOT by running
    `claude --version` and NOT by parsing a SystemMessage (spec §2.3 row 007).
    The pin moves the attribute and the binary together, so this is the same
    number with no 200 MB cold start to hide and nothing to warm at startup.
    'unknown' if a future pin drops the module or the attribute.
    """
    try:
        from claude_agent_sdk import _cli_version
        return parse_cli_version(getattr(_cli_version, "__cli_version__", "") or "")
    except Exception:  # noqa: BLE001 — a missing attribute must never fail a job
        return "unknown"
```

`parse_cli_version("")` already returns `"unknown"` and truncates at 24 chars (Task 2), so the guard is one call, not a branch.

Change `_run_in_process` (line 1048):

```python
async def _run_in_process(
    job_id: str, prompt: str, options: ClaudeAgentOptions
) -> tuple[str, dict[str, Any], ResultCapture]:
    """The in-process Agent SDK execution path (the only execution path).
    Returns (final_text, usage, capture) — `capture` is the full typed
    ResultMessage (P0), `usage` is kept for every existing consumer."""
    final_text_chunks: list[str] = []
    usage: dict[str, Any] = {}
    capture = ResultCapture()
```

Inside the loop, replace lines 1094-1095 — the existing `if isinstance(message, ResultMessage):` line AND its body line `usage = getattr(message, "usage", {}) or {}` — with the three-line block below (same indentation as the line 1094 `if`; replacing only line 1095 would nest a second `if isinstance(...)` inside the first and put the `is_error` block under the inner one):

```python
                if isinstance(message, ResultMessage):
                    capture = capture_result_message(message)
                    usage = capture.usage
```

The `if message.is_error:` block that follows stays byte-identical at its current indentation (it remains inside this `if isinstance(...)`).

After the existing banner check (lines 1124-1128) and before `return summary_text, usage`, add:

```python
        # Silent-empty-success trap (spec §0a row 6 / §2.4): the pinned CLI can
        # return a 'success' with no text, zero usage and zero API time for an
        # id it does not know (Opus 5.5 / Sonnet 5 before the D13 bump). Typed
        # check beside the banner regex above; fails the job so escalation
        # (a known-good model) engages instead of recording a completed no-op.
        violation = served_model_violation(capture, options.model or "", summary_text)
        if violation:
            audit_log.append(job_id, "job_result_rejected", reason="unrecognized_model",
                             detail=violation, requested_model=options.model)
            raise RuntimeError(f"unrecognized_model: silent empty success — {violation}")

        return summary_text, usage, capture
```

In `run_session`, change the `resolved_*` UPDATE (lines 975-983) to also stamp provider/executor/CLI so failed jobs carry them:

```python
            sql_update(Job).where(Job.id == job.id).values(
                resolved_skill=skill_name or None,
                resolved_model=options.model,
                resolved_effort=effort_used,
                resolved_provider="anthropic",
                executor="claude_sdk",
                cli_version=cli_version(),
            )
```

Change the call (`session.py:1003` in the pre-P0 tree — locate it by symbol) to `final_summary, usage, capture = await _run_in_process(job_id, job.description, options)`.

Replace the `job_completed` block + return (lines 1019-1032) with:

```python
        duration = (datetime.now(timezone.utc) - started_at).total_seconds()
        terminal_reason = derive_terminal_reason(capture)   # banner case raised above
        columns = result_columns(capture, terminal_reason=terminal_reason,
                                 cli_version=cli_version())
        async with async_session() as s:
            await s.execute(sql_update(Job).where(Job.id == job.id).values(**columns))
            await s.commit()
        audit_log.append(
            job_id,
            "job_completed",
            duration_seconds=duration,
            usage=usage,
            terminal_reason=terminal_reason,
            num_turns=capture.num_turns,
            duration_api_ms=capture.duration_api_ms,
            model_served=capture.model_served,
            cost_usd_list=capture.total_cost_usd,
            stop_reason=capture.stop_reason,
        )

        return {
            "summary": final_summary,
            "duration_seconds": duration,
            "usage": usage,
            "skill": skill_name,
            "isolation": isolation,
            "terminal_reason": terminal_reason,
            "model_served": capture.model_served,
            "num_turns": capture.num_turns,
        }
```

Also replace the default tools list is NOT touched here (Task 10 owns `session.py:706-709`).

- [ ] **Step 4: Wire `main.py`**

Add the import at the top of `src/runner/main.py` (after `from src.runner import delivery, quota, ...`):

```python
from src.runner.result_capture import terminal_reason_for_exception
```

Add a pure helper after `note_missing_job` (line ~257):

```python
def queue_wait_ms(created_at: datetime | None, started_at: datetime | None) -> int | None:
    """Pure. Milliseconds a job sat between enqueue and the running flip;
    None when either stamp is missing, never negative (clock skew)."""
    if created_at is None or started_at is None:
        return None
    return max(0, int((started_at - created_at).total_seconds() * 1000))
```

`_check_subscription_auth` is **not** modified: `cli_version()` reads an attribute, so there is no blocking call to move off the event loop.

In `_process_job` (lines 333-335), stamp the wait when flipping to running:

```python
                job.status = JobStatus.running.value
                job.started_at = datetime.now(timezone.utc)
                job.queue_wait_ms = queue_wait_ms(job.created_at, job.started_at)
                await s.commit()
```

Preflight failure (lines 364-366) becomes:

```python
        audit_log.append(str(job_id), "job_failed", error=preflight_error,
                         error_category="preflight", terminal_reason="error")
        await _finish_job(job_id, JobStatus.failed, error=preflight_error,
                          terminal_reason="error")
```

The three typed branches (lines 460-511) each get `terminal_reason="error"` on both calls. `SkillResolutionError` (lines 466-468):

```python
        audit_log.append(str(job_id), "job_failed", error=reason,
                         error_category="skill_contract", terminal_reason="error")
        await _finish_job(job_id, JobStatus.failed, error=f"Skill contract: {reason}",
                          terminal_reason="error")
```

`DeployRefused` (lines 480-482):

```python
        audit_log.append(str(job_id), "job_failed", error=reason,
                         error_category="deploy_refused", terminal_reason="error")
        await _finish_job(job_id, JobStatus.failed, error=f"Deploy refused: {reason}",
                          terminal_reason="error")
```

`DeployNeedsApproval` (lines 500-502):

```python
        audit_log.append(str(job_id), "job_failed", error=guidance,
                         error_category="deploy_needs_approval", terminal_reason="error")
        await _finish_job(job_id, JobStatus.failed, error=guidance,
                          terminal_reason="error")
```

Timeout branch (lines 513-529) becomes — note the cancelled guard between the refetch and the escalation:

```python
    except asyncio.TimeoutError:
        audit_log.append(str(job_id), "job_failed", error="session_timeout",
                         error_category="timeout", terminal_reason="timeout")
        await _finish_job(job_id, JobStatus.failed, error="Session timed out",
                          terminal_reason="timeout")
        log.warning("job timeout")

        # (existing comment block about timeouts escalating stays)
        job = await _refetch_job(job_id, job, log)
        if job is not None and job.status == JobStatus.cancelled.value:
            return      # owner cancelled mid-flight (INV-9 kept the row); never escalate it
        try:
            await _maybe_escalate(job)
        except Exception:
            log.exception("escalation attempt failed (non-fatal)")
```

Generic branch (lines 531-551) becomes:

```python
    except Exception as exc:
        from src.runner.audit_index import categorize_error
        err_str = str(exc)[:500]
        reason = terminal_reason_for_exception(exc)
        audit_log.append(str(job_id), "job_failed", error=err_str,
                         error_category=categorize_error(err_str), terminal_reason=reason)
        await _finish_job(job_id, JobStatus.failed, error=err_str, terminal_reason=reason)
        log.exception("job failed")

        # (existing refetch comment block stays)
        job = await _refetch_job(job_id, job, log)
        # A /cancel that interrupts the session before its first API call now
        # surfaces here as unrecognized_model (empty result); the row is
        # already `cancelled` — escalating it would enqueue a retry the owner
        # just killed (_maybe_escalate has no cancelled guard, main.py:704-740).
        if job is not None and job.status == JobStatus.cancelled.value:
            return
        try:
            await _maybe_escalate(job)
        except Exception:
            log.exception("escalation attempt failed (non-fatal)")
```

`_finish_job` (line 1269):

```python
async def _finish_job(
    job_id: uuid.UUID,
    status: JobStatus,
    *,
    result: dict | None = None,
    error: str | None = None,
    terminal_reason: str | None = None,
) -> None:
    values: dict[str, Any] = dict(
        status=status.value,
        result=result,
        error_message=error,
        completed_at=datetime.now(timezone.utc),
    )
    if terminal_reason:
        values["terminal_reason"] = terminal_reason
    async with session_scope() as s:
        # INV-9 comment block unchanged …
        result_proxy = await s.execute(
            update(Job)
            .where(Job.id == job_id)
            .where(Job.status != JobStatus.cancelled.value)
            .values(**values)
        )
```

(`from typing import Any` must be added to main.py's imports.) The completed path already stamps `terminal_reason` via `result_columns` in `run_session`, so `_finish_job(..., completed, result=result)` passes nothing extra.

- [ ] **Step 5: Extend `JobOut` / `_serialize` in `web.py`**

Append to `class JobOut` (after `created_by: str`):

```python
    # P0 observability (migration 007) — all optional, additive
    model_served: str | None = None
    terminal_reason: str | None = None
    num_turns: int | None = None
    duration_api_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_read_tokens: int | None = None
    cost_usd_list: float | None = None
    origin_channel: str | None = None
    queue_wait_ms: int | None = None
```

In `_serialize` add the matching kwargs:

```python
        created_by=job.created_by,
        model_served=job.model_served,
        terminal_reason=job.terminal_reason,
        num_turns=job.num_turns,
        duration_api_ms=job.duration_api_ms,
        input_tokens=job.input_tokens,
        output_tokens=job.output_tokens,
        cache_read_tokens=job.cache_read_tokens,
        cost_usd_list=float(job.cost_usd_list) if job.cost_usd_list is not None else None,
        origin_channel=job.origin_channel,
        queue_wait_ms=job.queue_wait_ms,
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `pipenv run pytest tests/test_result_capture.py tests/test_job_visibility.py tests/test_api_terminal.py tests/test_timeout_escalation.py tests/test_orphaned_jobs.py -v`
Expected: all PASS (the api-terminal + timeout suites prove the belts and the failure branches still behave).

Then the whole suite: `pipenv run pytest -q` → Expected: only pre-existing skips, 0 failures.

- [ ] **Step 7: Smoke against the live dev runner (no SDK mock exists; one real chat job)**

Run: `launchctl kickstart -k gui/$(id -u)/com.assistant.runner; pipenv run python -c "
import asyncio; from src.gateway.jobs import enqueue_job
print(asyncio.run(enqueue_job('reply with the single word pong', kind='chat', created_by='owner-terminal')).id)"`
(`scripts/run.sh` refuses to start/restart when launchd units exist — its own header, lines 24-28 — so the kickstart is the only way to be sure the smoke runs the new code.)
Then after ~60 s: `psql assistant -tAc "SELECT status, terminal_reason, model_served, num_turns, duration_api_ms, output_tokens, cli_version, queue_wait_ms FROM jobs ORDER BY created_at DESC LIMIT 1"`
Expected: `completed | ok | claude-sonnet-4-6… | 1 | <positive> | <positive> | 2.1.139 | <small int>`.

- [ ] **Step 8: SYSTEM.md Depends-on, CHANGELOGs, commit**

`session.py` and `main.py` now import `src.runner.result_capture`, whose row exists in the module graph since Task 2, so `check_module_graph_imports` warns until their Depends-on cells name it. In `.context/SYSTEM.md` append `, runner.result_capture` to the Depends-on cell of the `src/runner/session.py` row and of the `src/runner/main.py` row.

Run: `pipenv run pytest tests/test_doc_lint.py -q && pipenv run python scripts/lint_docs.py` → Expected: PASS and `All clean!`.

Prepend to `.context/modules/runner/CHANGELOG.md`:

```markdown
## 2026-09-25 — full ResultMessage captured into jobs columns; typed terminal_reason; silent-empty-success rejection

- **Agent task**: multi-model P0, Task 3.
- **Files changed**: `src/runner/session.py` (`_run_in_process` returns the `ResultCapture`; `run_session` stamps 12 columns + provider/executor/cli_version; `job_completed` gains terminal_reason/num_turns/duration_api_ms/model_served/cost_usd_list/stop_reason; new `cli_version()`; new audit kind `job_result_rejected`), `src/runner/main.py` (`queue_wait_ms` stamped at the running flip; `terminal_reason` on EVERY failure branch — preflight, skill-contract, deploy-refused, deploy-needs-approval, timeout, generic — and on `_finish_job`; timeout/generic branches return before `_maybe_escalate` when the refetched job is `cancelled`), `.context/SYSTEM.md` (Depends-on), tests.
- **Why**: spec §9 P0 exit criterion "every completed job has tokens/cost/provider in Postgres"; the banner regex stays as a belt (C12) while `api_error_status`/`stop_reason` drive the typed reason.
- **Side effects**: a session whose ResultMessage names a different model than requested, or is fully empty (no text, zero usage, zero API time), now FAILS with `unrecognized_model` and engages escalation — previously recorded `completed`. All-zero usage with text remains a success. A cancelled job is never escalated.
- **Gotchas discovered**: `job_completed` keeps `duration_seconds` + `usage` byte-for-byte (C14 consumers: retrospective, audit_index, learning); new fields are appended only. `cli_version()` reads `claude_agent_sdk._cli_version.__cli_version__` (spec §2.3 row 007) — the `claude --version` subprocess round 1 planned here does not exist, so there is nothing to warm at startup and no event-loop stall to avoid; a future reader must not reintroduce it (pinned by `test_session_spawns_no_subprocess_for_the_cli_version`).
```

Prepend to `.context/modules/gateway/CHANGELOG.md`:

```markdown
## 2026-09-25 — JobOut carries P0 observability columns

- `web.py`: `JobOut`/`_serialize` expose `model_served`, `terminal_reason`, `num_turns`, `duration_api_ms`, token counts, `cost_usd_list`, `origin_channel`, `queue_wait_ms` (all optional). Dashboard JSON consumers see extra keys only.
```

```bash
git add src/runner/session.py src/runner/main.py src/gateway/web.py tests/test_result_capture.py tests/test_job_visibility.py tests/test_timeout_escalation.py .context/modules/runner/CHANGELOG.md .context/modules/gateway/CHANGELOG.md .context/SYSTEM.md
git commit -m "feat(runner): capture full ResultMessage into jobs columns, typed terminal_reason, unrecognized_model rejection, queue_wait_ms"
```

---

### Task 19: Project-scope auth override is refused before the session starts — `provider_refused{settings_auth_override}`

**Execution position:** 6 of 21 — previous: Task 3, next: Task 20 (see Global Constraints "Execution order"). It edits the `run_session` path Task 3 has just touched.

- [ ] **Step 0: Prerequisite check** — `pipenv run python -c "from src.runner.result_capture import terminal_reason_for_exception; print('ok')"` must print `ok`. If it fails: **execute Task 3 first.**

**Why this is P0 and not P3.** `session.py:716` passes `setting_sources=["project"]` (verified in the current tree, inside `_build_options`'s `kwargs` dict) so the SDK loads `<cwd>/.claude/settings.json` and `<cwd>/.claude/settings.local.json` from whatever clone the job runs in. In those files `apiKeyHelper`, `env.ANTHROPIC_API_KEY`, `env.ANTHROPIC_AUTH_TOKEN`, `env.CLAUDE_CODE_OAUTH_TOKEN` and `ANTHROPIC_BASE_URL` **outrank the Keychain `/login`** (`claude-anthropic.md` line 53). Atlas is GitHub-canonical with other machines committing to it, so one such file arriving in a project repo would silently move Anthropic work to API billing or redirect it entirely — an INV-3 hole that neither the `guards.py` Bash-assignment deny nor Task 17's `os.environ` assertion can see. Spec §2.4 ("**INV-3 from project scope (P0, no protected path)**"), §3 Anthropic row ("enforced at three points"), §9 P0 scope cell and the named P0 test gate `test_settings_auth_override` (round-2 #4). The move into `ClaudeSdkExecutor` is P3; the check itself is P0.

**Files:**
- Modify: `src/runner/session.py` (a new pure `settings_auth_override()` near `_build_options`, and one call in `run_session` immediately before `options = _build_options(...)` — `:950` in the pre-P0 tree, **locate it by symbol**: Task 3 inserted code above it)
- Modify: `src/runner/result_capture.py` (`TERMINAL_REASONS` gains `provider_refused`; `terminal_reason_for_exception` maps the new exception)
- Modify: `.context/modules/runner/CHANGELOG.md`, `.context/modules/runner/CONTEXT.md` (public interface + the C1 row note)
- Test: `tests/test_settings_auth_override.py` (new)

**Interfaces:**
- Consumes: Task 3's `terminal_reason_for_exception`; `audit_log.append`.
- Produces:
  - `session.SETTINGS_AUTH_KEYS: tuple[str, ...] = ("apiKeyHelper", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_BASE_URL")`.
  - `session.settings_auth_override(cwd: Path) -> str | None` (pure except for two file reads) — the name of the first offending key found in `<cwd>/.claude/settings.json` then `settings.local.json`, else `None`. It looks at the top level **and** inside an `env` object (that is where `ANTHROPIC_*` lives in a settings file), is case-sensitive on the key names the CLI honours, treats unreadable/invalid JSON as "no override" (a malformed settings file is the CLI's problem, not an auth bypass), and never reads anything outside `<cwd>/.claude/`.
  - `class ProviderRefused(RuntimeError)` with `.reason: str` and `.detail: str`.
  - `run_session` raises `ProviderRefused("settings_auth_override", key)` **before** `_build_options`, having appended `provider_refused{reason: "settings_auth_override", key, path}` to the job's JSONL. `main._process_job` already funnels unexpected exceptions through `terminal_reason_for_exception(exc)`, which now returns `"provider_refused"` for this class, so the job finishes `failed` with `terminal_reason="provider_refused"` and the FailedCard says why. New audit kind `provider_refused` (Global Constraints C14 list).
  - **No escalation.** Like `DeployRefused`, this is a policy refusal, not a transient failure: retrying it on a bigger model would run the same poisoned clone. `_process_job`'s refusal branch is the existing pattern (`main.py:481-483`).

- [ ] **Step 1: Write the failing test**

Create `tests/test_settings_auth_override.py`:

```python
"""
INV-3 from project scope (P0; spec §2.4, §9 test gate `test_settings_auth_override`).

`setting_sources=["project"]` loads <cwd>/.claude/settings*.json, where
apiKeyHelper / env.ANTHROPIC_* / ANTHROPIC_BASE_URL outrank the Keychain
/login. A clone carrying one of those must refuse fail-closed, not run.

Pure: tmp_path fixture clones, no SDK, no DB.

Run: pipenv run pytest tests/test_settings_auth_override.py -v
"""

from __future__ import annotations

import json

import pytest

from src.runner.session import SETTINGS_AUTH_KEYS, settings_auth_override


def _clone(tmp_path, settings_obj=None, local_obj=None):
    d = tmp_path / ".claude"
    d.mkdir(parents=True)
    if settings_obj is not None:
        (d / "settings.json").write_text(json.dumps(settings_obj))
    if local_obj is not None:
        (d / "settings.local.json").write_text(json.dumps(local_obj))
    return tmp_path


def test_clean_clone_passes(tmp_path):
    assert settings_auth_override(_clone(tmp_path, {"permissions": {"allow": ["Bash"]}})) is None


def test_no_claude_dir_at_all_passes(tmp_path):
    assert settings_auth_override(tmp_path) is None


def test_api_key_helper_is_refused(tmp_path):
    cwd = _clone(tmp_path, {"apiKeyHelper": "/bin/echo sk-ant-x"})
    assert settings_auth_override(cwd) == "apiKeyHelper"


@pytest.mark.parametrize("key", ["ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN",
                                 "CLAUDE_CODE_OAUTH_TOKEN"])
def test_env_credentials_are_refused(tmp_path, key):
    cwd = _clone(tmp_path, {"env": {key: "leak"}})
    assert settings_auth_override(cwd) == key


def test_base_url_is_refused(tmp_path):
    # The one that redirects rather than re-bills: a proxy host in front of the
    # Max credential.
    assert settings_auth_override(_clone(tmp_path, {"env": {"ANTHROPIC_BASE_URL": "https://x"}})) \
        == "ANTHROPIC_BASE_URL"
    assert settings_auth_override(_clone(tmp_path, {"ANTHROPIC_BASE_URL": "https://x"})) \
        == "ANTHROPIC_BASE_URL"


def test_settings_local_is_checked_too(tmp_path):
    # .claude/settings.local.json is gitignored in most repos, so it is the more
    # likely carrier — and it wins over settings.json in the CLI.
    cwd = _clone(tmp_path, {"permissions": {}}, {"apiKeyHelper": "x"})
    assert settings_auth_override(cwd) == "apiKeyHelper"


def test_malformed_json_is_not_an_override(tmp_path):
    d = tmp_path / ".claude"
    d.mkdir()
    (d / "settings.json").write_text("{not json")
    assert settings_auth_override(tmp_path) is None


def test_every_key_in_the_constant_is_detected(tmp_path):
    # The spec names five; a future addition must come with a case.
    assert set(SETTINGS_AUTH_KEYS) == {
        "apiKeyHelper", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN",
        "CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_BASE_URL"}


def test_run_session_checks_before_building_options():
    # Source pin: the refusal must precede _build_options, or the poisoned
    # settings file has already been handed to the SDK.
    import inspect
    from src.runner import session
    src = inspect.getsource(session.run_session)
    assert src.index("settings_auth_override(") < src.index("_build_options(")


def test_provider_refused_maps_to_a_terminal_reason():
    from src.runner.result_capture import TERMINAL_REASONS, terminal_reason_for_exception
    from src.runner.session import ProviderRefused
    assert "provider_refused" in TERMINAL_REASONS
    assert terminal_reason_for_exception(
        ProviderRefused("settings_auth_override", "apiKeyHelper")) == "provider_refused"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pipenv run pytest tests/test_settings_auth_override.py -v`
Expected: collection error `ImportError: cannot import name 'SETTINGS_AUTH_KEYS' from 'src.runner.session'`.

- [ ] **Step 3: Implement**

In `src/runner/session.py`, above `_build_options`:

```python
# INV-3 from project scope (spec §2.4, §9 P0). `setting_sources=["project"]`
# below loads <cwd>/.claude/settings.json and settings.local.json from the
# clone the job runs in, and these keys outrank the Keychain /login
# (claude-anthropic.md line 53) — apiKeyHelper and the two token names re-bill
# the work to an API key, ANTHROPIC_BASE_URL redirects it. Atlas is
# GitHub-canonical with other machines committing, so the file can arrive
# without anyone here doing anything. Refuse the job; never strip the file.
SETTINGS_AUTH_KEYS: tuple[str, ...] = (
    "apiKeyHelper",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "CLAUDE_CODE_OAUTH_TOKEN",
    "ANTHROPIC_BASE_URL",
)


class ProviderRefused(RuntimeError):
    """A policy refusal before the session starts (never escalated, never retried)."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


def settings_auth_override(cwd: Path) -> str | None:
    """The first SETTINGS_AUTH_KEYS name present in <cwd>/.claude/settings*.json.

    settings.local.json is checked first: it is gitignored in most repos (so it
    is the likelier carrier) and the CLI gives it precedence. Unreadable or
    invalid JSON is NOT treated as an override — a malformed settings file is
    the CLI's problem; inventing a refusal from it would fail honest jobs.
    """
    for name in ("settings.local.json", "settings.json"):
        path = cwd / ".claude" / name
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        env = data.get("env") if isinstance(data.get("env"), dict) else {}
        for key in SETTINGS_AUTH_KEYS:
            if key in data or key in env:
                return key
    return None
```

(`json` and `Path` are already imported in `session.py`; check and add only what is missing.)

In `run_session`, immediately before `options = _build_options(` (**find it by symbol** — `:950` in the pre-P0 tree, moved by Task 3):

```python
    # INV-3 third enforcement point (spec §2.4/§3; the first two are
    # guards.py's assignment deny and main's os.environ assertion). The cwd
    # here is the workspace clone when the skill is isolated, the canonical
    # checkout otherwise — both are loaded by setting_sources=["project"].
    offending = settings_auth_override(Path(cwd))
    if offending:
        audit_log.append(job_id, "provider_refused",
                         reason="settings_auth_override", key=offending,
                         path=str(Path(cwd) / ".claude"))
        raise ProviderRefused(
            "settings_auth_override",
            f"{offending} in {Path(cwd) / '.claude'} outranks the Keychain login "
            f"(spec §2.4) — remove it from the clone; never strip it automatically",
        )
```

In `src/runner/result_capture.py`: add `"provider_refused"` to `TERMINAL_REASONS`, and in `terminal_reason_for_exception` add, before the text heuristics:

```python
    if name == "ProviderRefused":
        return "provider_refused"
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pipenv run pytest tests/test_settings_auth_override.py tests/test_result_capture.py -v`
Expected: all PASS.

**Host step (needs a live SDK job; skip in an isolated worktree and confirm with the owner instead).** Plant and remove the file in a scratch clone, never in a real project:

```bash
mkdir -p /tmp/p0-override/.claude && echo '{"env":{"ANTHROPIC_BASE_URL":"https://example.invalid"}}' > /tmp/p0-override/.claude/settings.json
# enqueue a job with cwd=/tmp/p0-override (a scratch project row, or call run_session directly in a REPL)
grep -c '"kind": "provider_refused"' volumes/audit_log/<job>.jsonl   # → 1
psql assistant -tAc "SELECT status, terminal_reason FROM jobs ORDER BY created_at DESC LIMIT 1"  # → failed | provider_refused
rm -rf /tmp/p0-override
```

- [ ] **Step 5: Docs, CHANGELOG, commit**

- `.context/modules/runner/CONTEXT.md` — public interface gains `session.settings_auth_override(cwd) -> str | None`, `session.ProviderRefused`, `SETTINGS_AUTH_KEYS`, and a **C1 row note**: "INV-3 is enforced at three points — `guards.py` assignment deny, the `os.environ` startup assertion (`claude_env.vendor_keys_in`), and this project-scope settings check. All three are P0; the third moves into `ClaudeSdkExecutor` in P3." No new `src/runner/*.py` file, so `check_runner_context` needs no Paths change; no new cross-module import, so `check_module_graph_imports` is unaffected — run the lint anyway.

Run: `pipenv run pytest tests/test_doc_lint.py -q && pipenv run python scripts/lint_docs.py` → Expected: PASS and `All clean!`.

Prepend to `.context/modules/runner/CHANGELOG.md`:

```markdown
## 2026-09-25 — project-scope auth override refused before the session (provider_refused{settings_auth_override})

- **Agent task**: multi-model P0, Task 19 (spec §2.4 "INV-3 from project scope (P0, no protected path)", §9 P0 scope + test gate `test_settings_auth_override`, round-2 #4).
- **Files changed**: `session.py` (`SETTINGS_AUTH_KEYS`, `ProviderRefused`, `settings_auth_override()`, one call before `_build_options`), `result_capture.py` (`provider_refused` terminal reason), `tests/test_settings_auth_override.py` (new), runner CONTEXT.md (C1 row).
- **Why**: `setting_sources=["project"]` loads the clone's `.claude/settings*.json`, and `apiKeyHelper` / `env.ANTHROPIC_*` / `ANTHROPIC_BASE_URL` there outrank the Keychain `/login` — a settings file committed to atlas from another machine would silently move Max work onto API billing. `guards.py` only denies Bash-side assignment; the startup assertion only sees `os.environ`.
- **Side effects**: a job whose cwd carries one of the five keys fails immediately with `terminal_reason=provider_refused` and is NOT escalated (a policy refusal, like `DeployRefused`). New audit kind `provider_refused`.
- **Gotchas discovered**: `settings.local.json` is the likelier carrier (gitignored) and wins over `settings.json` in the CLI, so it is checked first. Malformed JSON is deliberately **not** an override — treating it as one would fail honest jobs on a typo. The check never edits or strips the offending file: rewriting another machine's committed settings from a job is how you lose the audit trail.
```

```bash
git add src/runner/session.py src/runner/result_capture.py tests/test_settings_auth_override.py .context/modules/runner/CHANGELOG.md .context/modules/runner/CONTEXT.md
git commit -m "fix(runner): refuse a project-scope auth override before the session — provider_refused{settings_auth_override} (INV-3 third enforcement point, spec §2.4)"
```

---

### Task 20: Always-on audit/stream secret redactor — `src/runner/secret_redact.py` wired into `_handle_message`

**Execution position:** 7 of 21 — previous: Task 19, next: Task 15 (which imports this module's `redact`, so its own copy is never written). See Global Constraints "Execution order".

- [ ] **Step 0: Prerequisite check** — `pipenv run python -c "import inspect; from src.runner import session; assert 'tool_result' in inspect.getsource(session._handle_message); print('ok')"` must print `ok`. If it fails: **execute Task 3 first** (it edits the same function).

**Why this is P0 and separate from Task 15.** Spec §2.4 has a dedicated "**Audit/stream redaction (P0)**" paragraph: `_handle_message` (`session.py:1138-1170`) "runs the §8.3 secret redactor over `tool_result` previews and `text` before the JSONL/`jobs:stream` write, with `CLAUDE_CODE_OAUTH_TOKEN`, `ANTHROPIC_*` and every vendor-key name in its pattern set, so a `printenv` in any session never lands a credential value in the per-job JSONL, the stream, `ai-mcp` reads or the learning extractor's input". `test_audit_redactor` is a named P0 test gate (§9). Round-2 #3 added it because the setup-token fallback makes any leaked value a **one-year** credential. Task 15's recorder is **opt-in** (`SDK_RECORD=0` ships), so it protects the side file and nothing else: without this task the always-on `volumes/audit_log/<id>.jsonl` and `jobs:stream:<id>` keep a `printenv` or a `curl -H 'Authorization: …'` verbatim. Task 15's own Review Focus item 7 concedes those results "routinely appear in Bash tool results".

**Files:**
- Create: `src/runner/secret_redact.py` (pure, import-free apart from `re`)
- Modify: `src/runner/session.py` `_handle_message` (the `text` path and the `tool_result` preview path; `:1138-1170` pre-P0 — **locate by symbol**, Task 3 edited this file)
- Modify: `.context/modules/runner/CHANGELOG.md`, `.context/modules/runner/CONTEXT.md` (Paths line — `check_runner_context` goes red the moment the file exists), `.context/SYSTEM.md` (module-graph row + `session.py` Depends-on)
- Test: `tests/test_audit_redactor.py` (new)

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `secret_redact.REDACTED = "[REDACTED]"`.
  - `secret_redact.redact(text: str) -> str` — pure; byte-identical output for text with nothing credential-shaped. Pattern set (the spec's): bare `sk-ant-…` keys, `Authorization: Bearer …`, and `NAME=value` / `NAME: value` assignments for `CLAUDE_CODE_OAUTH_TOKEN`, `ANTHROPIC_*`, `GEMINI_*`, `CEREBRAS_*`, `GROQ_*`, `CODEX_*`, `OPENROUTER_*`, `OPENAI_*`, `XAI_*` and any `*_TOKEN|*_SECRET|*_API_KEY|*_PASSWORD` name. Keeps the **name** and replaces only the value, so a redacted `printenv` is still useful for debugging ("`ANTHROPIC_BASE_URL=[REDACTED]` was set" is the finding).
  - `secret_redact.redact_tree(value: Any) -> Any` — the same over nested dict/list/tuple structures (what `tool_use.input` needs).
  - `session._handle_message` applies `redact()` to `block.text` (both the `audit_log.append(job_id, "text", …)` and the `_publish_stream` payload), to `block.thinking`, to `_preview_text(block.content)` for `tool_result`, and `redact_tree()` to `_truncate_for_log(block.input)` for `tool_use` — **after** truncation, so the pattern set sees whole lines.
  - Task 15's `sdk_record` imports `redact`/`redact_tree` from here instead of defining its own (one pattern set, per the Global Constraints bullet).
- **Explicitly not changed**: `final_text_chunks` keeps the **unredacted** text. That list becomes the job's `result`/summary the owner reads and the marker parser scans (`session.py:405-460`); redacting it could break a `TASK_COMPLETE:` line and would change job outcomes, not just the trace. The durable trace is what §2.4 names. Note it in the CONTEXT.md entry so P2 does not "fix" the asymmetry by accident.

- [ ] **Step 1: Write the failing test**

Create `tests/test_audit_redactor.py`:

```python
"""
Always-on audit/stream redaction (P0; spec §2.4 "Audit/stream redaction (P0)",
§9 test gate `test_audit_redactor`, round-2 #3).

A `printenv` or `curl -H 'Authorization: …'` in ANY of the 72 skills must not
land a credential value in volumes/audit_log/<id>.jsonl or jobs:stream:<id> —
with SDK_RECORD=0, which is the shipped default.

Pure: fake SDK blocks, monkeypatched audit_log/publish. No SDK, no Redis.

Run: pipenv run pytest tests/test_audit_redactor.py -v
"""

from __future__ import annotations

import pytest

from src.runner.secret_redact import REDACTED, redact, redact_tree

PRINTENV = """\
PATH=/usr/bin:/bin
ANTHROPIC_BASE_URL=https://proxy.example.invalid
CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-AAAAAAAAAAAAAAAAAAAAAAAA
GEMINI_API_KEY=AIzaSyFAKEFAKEFAKEFAKEFAKEFAKEFAKE
TELEGRAM_BOT_TOKEN=123456:AAFAKEFAKEFAKEFAKE
HOME=/Users/x
"""
SECRETS = ("sk-ant-oat01-AAAAAAAAAAAAAAAAAAAAAAAA",
           "AIzaSyFAKEFAKEFAKEFAKEFAKEFAKEFAKE",
           "123456:AAFAKEFAKEFAKEFAKEFAKE",
           "https://proxy.example.invalid")


class TestPatterns:
    def test_printenv_values_are_gone_but_names_remain(self):
        out = redact(PRINTENV)
        for secret in SECRETS:
            assert secret not in out, secret
        # The finding is still legible: which names were set.
        for name in ("ANTHROPIC_BASE_URL", "CLAUDE_CODE_OAUTH_TOKEN", "GEMINI_API_KEY"):
            assert f"{name}={REDACTED}" in out, name
        assert "PATH=/usr/bin:/bin" in out and "HOME=/Users/x" in out   # not credentials

    def test_bearer_header(self):
        out = redact("curl -H 'Authorization: Bearer sk-ant-api03-ZZZZZZZZZZZZ' https://x")
        assert "sk-ant-api03-ZZZZZZZZZZZZ" not in out and REDACTED in out

    def test_bare_key_anywhere(self):
        assert redact("oops sk-ant-api03-QQQQQQQQQQQQ oops") == f"oops {REDACTED} oops"

    def test_innocent_text_is_byte_identical(self):
        for text in ("", "hello world", "PATH=/bin", "rate=5", "token_count: 12"):
            assert redact(text) == text, text

    @pytest.mark.parametrize("prefix", ["ANTHROPIC_", "GEMINI_", "CEREBRAS_", "GROQ_",
                                        "CODEX_", "OPENROUTER_", "OPENAI_", "XAI_"])
    def test_every_vendor_prefix(self, prefix):
        assert "leaked" not in redact(f"{prefix}SECRET_THING=leaked")

    def test_tree(self):
        tree = {"cmd": "printenv", "out": ["GEMINI_API_KEY=abc123def456"], "n": 3}
        out = redact_tree(tree)
        assert "abc123def456" not in str(out) and out["n"] == 3


class TestHandleMessage:
    @pytest.mark.asyncio
    async def test_tool_result_preview_never_lands_a_credential(self, monkeypatch):
        """The gate: a printenv-shaped tool_result reaches neither sink raw."""
        from src.runner import session
        appended: list[tuple] = []
        published: list[dict] = []
        monkeypatch.setattr(session.audit_log, "append",
                            lambda job_id, kind, **f: appended.append((kind, f)))

        async def _pub(job_id, payload):
            published.append(payload)

        monkeypatch.setattr(session, "_publish_stream", _pub)

        msg = _user_message_with_tool_result(PRINTENV)   # see the fakes below
        await session._handle_message("job1", msg, [])

        blob = repr(appended) + repr(published)
        for secret in SECRETS:
            assert secret not in blob, secret
        assert appended and appended[0][0] == "tool_result"

    @pytest.mark.asyncio
    async def test_text_is_redacted_in_both_sinks_but_not_in_the_summary(self, monkeypatch):
        from src.runner import session
        appended: list[tuple] = []
        published: list[dict] = []
        monkeypatch.setattr(session.audit_log, "append",
                            lambda job_id, kind, **f: appended.append((kind, f)))

        async def _pub(job_id, payload):
            published.append(payload)

        monkeypatch.setattr(session, "_publish_stream", _pub)

        chunks: list[str] = []
        leaky = "here it is: sk-ant-api03-WWWWWWWWWWWW"
        await session._handle_message("job1", _assistant_text(leaky), chunks)

        assert "sk-ant-api03-WWWWWWWWWWWW" not in repr(appended)
        assert "sk-ant-api03-WWWWWWWWWWWW" not in repr(published)
        # final_text_chunks is deliberately NOT redacted: it becomes the job's
        # result and feeds the TASK_COMPLETE marker parser (session.py:405-460).
        assert chunks == [leaky]
```

Build `_assistant_text` / `_user_message_with_tool_result` from the real SDK dataclasses (`AssistantMessage`, `TextBlock`, `UserMessage`, `ToolResultBlock` — constructing them is allowed; spawning the CLI is not, Global Constraints).

- [ ] **Step 2: Run the test to verify it fails**

Run: `pipenv run pytest tests/test_audit_redactor.py -v`
Expected: collection error `ModuleNotFoundError: No module named 'src.runner.secret_redact'`.

- [ ] **Step 3: Implement `src/runner/secret_redact.py`**

```python
"""
Secret redaction for the durable trace (P0; spec §2.4 "Audit/stream redaction",
§8.3 redactor).

ALWAYS ON — unlike the SDK_RECORD recorder (src/runner/sdk_record.py), which is
opt-in and only protects its own side file. Every `tool_result` preview and
every assistant `text` passes through redact() before it is appended to
volumes/audit_log/<id>.jsonl or published to jobs:stream:<id>, so a `printenv`
or a `curl -H 'Authorization: …'` in any of the 72 skills cannot leave a
credential in the JSONL, the stream, `ai-mcp` reads, or the learning
extractor's input (learning.py:138-170 reads Bash command text verbatim).
A leaked CLAUDE_CODE_OAUTH_TOKEN is a ONE-YEAR credential (spec §0a).

The NAME is kept and only the VALUE is replaced, so the trace still says which
variable was set — that is the finding a debugger needs.

Pure module: no I/O, no src imports (session.py, sdk_record.py and P3's
executors all import it).
"""

from __future__ import annotations

import re
from typing import Any

REDACTED = "[REDACTED]"

# Vendor/auth name prefixes — the same set the runner refuses at startup
# (src/runner/claude_env.py VENDOR_KEY_PREFIXES; kept as a literal here so this
# module stays import-free, and pinned equal by tests/test_audit_redactor.py).
_NAME_ALTS = (
    r"CLAUDE_CODE_OAUTH_TOKEN"
    r"|(?:ANTHROPIC|GEMINI|CEREBRAS|GROQ|CODEX|OPENROUTER|OPENAI|XAI)_[A-Z0-9_]*"
    r"|[A-Z0-9_]*(?:_TOKEN|_SECRET|_API_KEY|_PASSWORD)"
)

# A bare Anthropic key anywhere in free text — the whole token goes.
_BARE_KEY = re.compile(r"sk-ant-[A-Za-z0-9_-]{8,}")

# Prefix-preserving patterns: group(1) is kept, the value is replaced.
_PREFIXED: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)(authorization\s*:\s*bearer\s+)\S+"),
    # `NAME=value` / `export NAME=value` at the start of a line — printenv, env,
    # `.env` dumps, `set -x` traces.
    re.compile(rf"(?m)^(\s*(?:export\s+)?(?:{_NAME_ALTS})\s*=\s*)\S+"),
    # `NAME=value` mid-line (a command line: `FOO=1 GEMINI_API_KEY=x cmd`).
    re.compile(rf"(?:(?<=\s)|(?<=^))((?:{_NAME_ALTS})=)[^\s\"']+"),
    # `"api_key": "value"` / `token = value` in JSON, YAML and prose.
    re.compile(r"(?i)([\"']?(?:api[_-]?key|auth[_-]?token|secret|password)[\"']?\s*[:=]\s*[\"']?)"
               r"[^\s\"',}]{6,}"),
)


def redact(text: str) -> str:
    """Pure. Strip credential-shaped values; everything else byte-identical."""
    if not text:
        return text
    out = _BARE_KEY.sub(REDACTED, text)
    for pat in _PREFIXED:
        out = pat.sub(lambda m: m.group(1) + REDACTED, out)
    return out


def redact_tree(value: Any) -> Any:
    """redact() over nested dict / list / tuple structures (tool_use.input)."""
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, dict):
        return {str(k): redact_tree(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact_tree(v) for v in value]
    return value
```

Then wire it into `_handle_message` (locate the function by name; Task 3 has edited this file). Four call sites, each wrapping a value that is already being computed:

```python
            if isinstance(block, TextBlock):
                safe = secret_redact.redact(block.text)
                audit_log.append(job_id, "text", text=safe)
                final_text_chunks.append(block.text)      # NOT redacted — see below
                await _publish_stream(job_id, {"kind": "text", "text": safe})
            elif isinstance(block, ToolUseBlock):
                audit_log.append(
                    job_id, "tool_use",
                    tool_name=block.name,
                    tool_use_id=block.id,
                    input=secret_redact.redact_tree(_truncate_for_log(block.input)),
                )
                ...
            elif isinstance(block, ThinkingBlock):
                audit_log.append(job_id, "thinking",
                                 text=secret_redact.redact(block.thinking))
    ...
            if isinstance(block, ToolResultBlock):
                audit_log.append(
                    job_id, "tool_result",
                    tool_use_id=block.tool_use_id,
                    is_error=bool(block.is_error),
                    result_preview=secret_redact.redact(_preview_text(block.content)),
                )
```

with `from src.runner import secret_redact` in the imports. `final_text_chunks` stays raw on purpose: it becomes the job's `result`/summary and feeds the `TASK_COMPLETE:` marker parser (`session.py:405-460`), so redacting it could change job outcomes rather than just the trace. §2.4 names the trace.

- [ ] **Step 4: Have Task 15's recorder delegate**

If Task 15 already landed (it does, in execution order it comes next — but if you are re-running, check): replace `sdk_record`'s own `_KEY_PATTERN`/`_PREFIX_PATTERNS`/`redact`/`_redact_tree` with `from src.runner.secret_redact import REDACTED, redact, redact_tree` and keep `sdk_record.redact` as a re-export so `tests/test_sdk_record.py`'s existing imports still resolve. One pattern set, two callers — a future narrowing cannot leave the always-on path behind. Add to `tests/test_audit_redactor.py`:

```python
def test_sdk_record_uses_the_shared_redactor():
    from src.runner import sdk_record, secret_redact
    assert sdk_record.redact is secret_redact.redact
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pipenv run pytest tests/test_audit_redactor.py tests/test_sdk_record.py tests/test_api_terminal.py -v`
Expected: all PASS (`test_api_terminal` proves the banner regex belt still sees what it needs — the API-error banner is not credential-shaped, so redaction does not touch it).

**Host check (skip in an isolated worktree).** One real job that prints its environment, in a scratch project only:

```bash
# enqueue: `run printenv | sort | head -40 and then say TASK_COMPLETE: done`
grep -c 'sk-ant-\|oat01' volumes/audit_log/<job>.jsonl     # → 0
grep -c 'REDACTED' volumes/audit_log/<job>.jsonl           # → ≥ 1 if anything was set
```

- [ ] **Step 6: Docs the lint gate needs, CHANGELOG, commit**

- `.context/modules/runner/CONTEXT.md`: append `` , `src/runner/secret_redact.py` `` to the `**Paths:**` line (`check_runner_context` fails otherwise), plus a public-interface bullet: "`secret_redact.redact(text)` / `redact_tree(value)` — always-on redaction of every `tool_result` preview, `text`, `thinking` and `tool_use.input` before the JSONL/stream write (P0, spec §2.4). `final_text_chunks` is deliberately NOT redacted (it is the job result and the marker-parser input)."
- `.context/SYSTEM.md` module graph — insert before the `src/runner/sdk_record.py` row, and append `, runner.secret_redact` to the Depends-on cells of `src/runner/session.py` and `src/runner/sdk_record.py`:

```markdown
| `src/runner/secret_redact.py` | Always-on secret redaction for the audit JSONL and `jobs:stream` (pure, import-free) | — | runner.session, runner.sdk_record |
```

Run: `pipenv run pytest tests/test_doc_lint.py -q && pipenv run python scripts/lint_docs.py` → Expected: PASS and `All clean!`.

Prepend to `.context/modules/runner/CHANGELOG.md`:

```markdown
## 2026-09-25 — always-on secret redaction on the audit JSONL and jobs:stream

- **Agent task**: multi-model P0, Task 20 (spec §2.4 "Audit/stream redaction (P0)", §9 P0 scope + test gate `test_audit_redactor`, round-2 #3).
- **Files changed**: `src/runner/secret_redact.py` (new, pure), `session._handle_message` (four call sites), `sdk_record` (delegates to the shared redactor), `tests/test_audit_redactor.py` (new), runner CONTEXT.md Paths + interface, SYSTEM.md row.
- **Why**: `SDK_RECORD` ships OFF, so the opt-in recorder's redaction protected nothing by default while the always-on per-job JSONL, `jobs:stream:<id>`, `ai-mcp` reads and the learning extractor's input kept a `printenv` or `curl -H 'Authorization: …'` verbatim. A leaked `CLAUDE_CODE_OAUTH_TOKEN` is a one-year credential.
- **Side effects**: audit entries and stream payloads for `text`/`thinking`/`tool_use.input`/`tool_result` now carry `[REDACTED]` in place of credential-shaped values. Names are kept, so the trace still says which variable was set. Job results, summaries and the `TASK_COMPLETE:` marker path are untouched.
- **Gotchas discovered**: redact AFTER truncation (`_truncate_for_log`), or a cut line can hide half a pattern from the regex. `final_text_chunks` must stay raw — it is the job result and the marker-parser input, not the trace. One pattern set only: `sdk_record` re-exports this module's `redact`, pinned by `test_sdk_record_uses_the_shared_redactor`, so a future narrowing of the recorder cannot silently leave the always-on path behind.
```

```bash
git add src/runner/secret_redact.py src/runner/session.py src/runner/sdk_record.py tests/test_audit_redactor.py tests/test_sdk_record.py .context/modules/runner/CHANGELOG.md .context/modules/runner/CONTEXT.md .context/SYSTEM.md
git commit -m "feat(runner): always-on secret redaction of the audit JSONL and jobs:stream (secret_redact.py wired into _handle_message; sdk_record delegates) — spec §2.4"
```

---

### Task 4: Persisted origin on jobs and tasks + `awaiting_since`


**Execution position:** 10 of 21 — previous: Task 17, next: Task 5 (see Global Constraints "Execution order").

**Files:**
- Modify: `src/gateway/jobs.py:16-47` (`enqueue_job`), add `origin_from_created_by`
- Modify: `src/gateway/telegram_bot.py:221-270` (`_create_task_with_job`), `:320-324` (plain-text chat branch — `enqueue_job(` at 320, closing paren at 324), `:347-352` (`cmd_chat`), `:374-407` (`cmd_god`), `:775-813` (`_handle_thread_reply`; its continuation `enqueue_job(` is at `:800-805`), `:916-929` (`approve_plan`, `reopen`), `:989-1011` (`choice`; its `enqueue_job(` is at `:1000-1005`)
- Modify: `src/gateway/web.py:398-404` (`create_job`)
- Modify: `src/runner/main.py:876-882` (`_set_task_status` — `async def` at 876, body through 882), `:1105-1110` and `:1121-1126` (direct awaiting_user updates), `:1193-1198` (sentinel pending_approval), `:1338-1346` (`_tick_schedules`)
- Modify: `.context/modules/gateway/CHANGELOG.md`, `.context/modules/runner/CHANGELOG.md`
- Test: `tests/test_origin.py`

**Interfaces:**
- Consumes: Task 1 columns.
- Produces:
  - `jobs.enqueue_job(description, *, kind, payload, project_id, created_by, task_id, parent_job_id, origin_channel: str | None = None, origin_ref: str | None = None, origin_thread: str | None = None) -> Job` — when `origin_channel` is None it is derived with `origin_from_created_by`.
  - `jobs.origin_from_created_by(created_by: str) -> tuple[str, str | None]` (pure; channels `telegram | web | scheduler | system`).
  - `main.awaiting_since_for(status: str, now: datetime) -> datetime | None` (pure).
  - `main._set_task_status(task_id, status)` now also writes `awaiting_since`.
  - Every Telegram/web launch carries `origin_channel/origin_ref/origin_thread` on the Job (and Task); scheduler jobs carry `origin_channel="scheduler", origin_ref=<schedule name>`. Consumed by Task 5's `build_job_notice` and Task 6.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_origin.py`:

```python
"""
Persisted job/task origin (P0) — pure tests.

Run: pipenv run pytest tests/test_origin.py -v
"""

from __future__ import annotations

import inspect
from datetime import datetime, timezone

import pytest

from src.gateway.jobs import enqueue_job, origin_from_created_by
from src.runner.main import awaiting_since_for


class TestOriginFromCreatedBy:
    @pytest.mark.parametrize("created_by,expected", [
        ("telegram:123456789", ("telegram", "123456789")),
        ("telegram:", ("telegram", None)),
        ("web", ("web", None)),
        ("scheduler", ("scheduler", None)),
        ("dispatch-mcp", ("system", "dispatch-mcp")),
        ("escalation:abcd1234", ("system", "escalation:abcd1234")),
        ("auto-continue:abcd1234", ("system", "auto-continue:abcd1234")),
        ("", ("system", None)),
        ("unknown", ("system", "unknown")),
    ])
    def test_mapping(self, created_by, expected):
        assert origin_from_created_by(created_by) == expected

    def test_ref_fits_column(self):
        channel, ref = origin_from_created_by("owner-" + "x" * 200)
        assert channel == "system" and len(ref) <= 64


class TestEnqueueSignature:
    def test_enqueue_job_accepts_origin_kwargs(self):
        params = inspect.signature(enqueue_job).parameters
        for name in ("origin_channel", "origin_ref", "origin_thread"):
            assert name in params and params[name].kind is inspect.Parameter.KEYWORD_ONLY
            assert params[name].default is None


class TestAwaitingSince:
    NOW = datetime(2026, 9, 25, 12, 0, tzinfo=timezone.utc)

    def test_awaiting_statuses_get_a_stamp(self):
        assert awaiting_since_for("awaiting_user", self.NOW) == self.NOW
        assert awaiting_since_for("pending_approval", self.NOW) == self.NOW

    def test_other_statuses_clear_it(self):
        assert awaiting_since_for("active", self.NOW) is None
        assert awaiting_since_for("completed", self.NOW) is None
        assert awaiting_since_for("failed", self.NOW) is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pipenv run pytest tests/test_origin.py -v`
Expected: `ImportError: cannot import name 'origin_from_created_by'` (collection fails).

- [ ] **Step 3: `jobs.py` — origin kwargs + derivation**

Replace `enqueue_job` in `src/gateway/jobs.py` with:

```python
ORIGIN_CHANNELS: tuple[str, ...] = ("telegram", "web", "cli", "scheduler", "system")


def origin_from_created_by(created_by: str) -> tuple[str, str | None]:
    """Pure. Fallback (origin_channel, origin_ref) for producers that do not
    pass an explicit origin — mirrors the migration-007 backfill CASE so old
    and new rows agree. Refs are clipped to the String(64) column."""
    cb = (created_by or "").strip()
    if cb.startswith("telegram:"):
        ref = cb.split(":", 1)[1].strip()
        return "telegram", (ref[:64] or None)
    if cb == "web":
        return "web", None
    if cb == "scheduler":
        return "scheduler", None
    return "system", (cb[:64] or None)


async def enqueue_job(
    description: str,
    *,
    kind: str = JobKind.task.value,
    payload: dict[str, Any] | None = None,
    project_id: uuid.UUID | None = None,
    created_by: str = "unknown",
    task_id: uuid.UUID | None = None,
    parent_job_id: uuid.UUID | None = None,
    origin_channel: str | None = None,
    origin_ref: str | None = None,
    origin_thread: str | None = None,
) -> Job:
    """Create a Job row and push it onto the queue.

    task_id / parent_job_id are set at creation (P2) — previously every call
    site did a separate UPDATE after enqueue, which left a small window where
    the runner could pick up a task job before its task linkage existed.

    origin_* (P0, spec §2.3 row 007) is the persisted job→channel binding that
    replaces the bot's in-process `_job_to_chat`; producers that know their
    origin pass it, everyone else gets it derived from `created_by`.
    """
    if origin_channel is None:
        origin_channel, derived_ref = origin_from_created_by(created_by)
        origin_ref = origin_ref if origin_ref is not None else derived_ref
    job = Job(
        kind=kind,
        description=description,
        payload=payload,
        project_id=project_id,
        status=JobStatus.queued.value,
        created_by=created_by,
        task_id=task_id,
        parent_job_id=parent_job_id,
        origin_channel=origin_channel[:16],
        origin_ref=(origin_ref or None) and origin_ref[:64],
        origin_thread=(origin_thread or None) and origin_thread[:64],
    )
    async with async_session() as s:
        s.add(job)
        await s.commit()
        await s.refresh(job)
    await redis.rpush(QUEUE_JOBS, str(job.id))
    return job
```

- [ ] **Step 4: `main.py` — `awaiting_since` + scheduler origin**

Add after `queue_wait_ms` (Task 3):

```python
_AWAITING_STATUSES = ("awaiting_user", "pending_approval")


def awaiting_since_for(status: str, now: datetime) -> datetime | None:
    """Pure. Stamp when a task starts waiting on the owner; clear otherwise."""
    return now if status in _AWAITING_STATUSES else None
```

Replace `_set_task_status` (lines 876-882):

```python
async def _set_task_status(task_id, status: str) -> None:
    from src.models import Task
    now = datetime.now(timezone.utc)
    async with session_scope() as s:
        await s.execute(
            update(Task).where(Task.id == task_id).values(
                status=status, updated_at=now,
                awaiting_since=awaiting_since_for(status, now))
        )
```

In `_update_task_after_job`, the `if choices_event:` branch (lines 1104-1110) and the `elif question:` branch (lines 1120-1126) each open `session_scope()` and run `update(Task)...values(status=TaskStatus.awaiting_user.value, updated_at=...)`. Replace each of those two `async with session_scope() as s: ...` blocks with the single line:

```python
        await _set_task_status(job.task_id, TaskStatus.awaiting_user.value)
```

In the sentinel branch (lines 1193-1198), change `.values(status=TaskStatus.pending_approval.value, updated_at=datetime.now(timezone.utc))` to:

```python
                    .values(status=TaskStatus.pending_approval.value,
                            updated_at=datetime.now(timezone.utc),
                            awaiting_since=datetime.now(timezone.utc))
```

In `_tick_schedules` (lines 1338-1346) add two kwargs to `Job(...)`:

```python
            job = Job(
                kind=sched.job_kind,
                description=sched.job_description,
                payload=sched.job_payload,
                project_id=sched.project_id,
                schedule_id=sched.id,
                status=JobStatus.queued.value,
                created_by="scheduler",
                origin_channel="scheduler",
                origin_ref=sched.name[:64],
            )
```

- [ ] **Step 5: `telegram_bot.py` — origin on every launch, `awaiting_since` on user turns**

Add `from datetime import datetime, timezone` to the bot's imports (used by the `reopen` branch below). Every edited call is shown in full; nothing else in these functions changes.

`_create_task_with_job` (lines 221-270) — three edits. The `Task(...)` constructor (lines 231-235):

```python
    task = Task(
        description=description,
        created_by=f"telegram:{chat_id}",
        chat_id=chat_id,
        origin_channel="telegram",
        origin_ref=str(chat_id),
    )
```

The `enqueue_job(...)` call (lines 250-256):

```python
    job = await enqueue_job(
        description,
        kind=kind,
        payload=flags or None,
        created_by=f"telegram:{chat_id}",
        task_id=task.id,
        origin_channel="telegram",
        origin_ref=str(chat_id),
    )
    _job_to_chat[str(job.id)] = chat_id
```

The final UPDATE after the reply (lines 267-270) persists the thread on BOTH rows:

```python
    async with async_session() as s:
        await s.execute(sql_update(Task).where(Task.id == task.id).values(
            thread_message_id=reply.message_id,
            origin_thread=str(reply.message_id)))
        await s.execute(sql_update(Job).where(Job.id == job.id).values(
            origin_thread=str(reply.message_id)))
        await s.commit()
```

`cmd_god` — the `Task(...)` constructor (line 374):

```python
    task = Task(description=description, created_by=f"telegram:{chat_id}", chat_id=chat_id,
                origin_channel="telegram", origin_ref=str(chat_id))
```

its `enqueue_job(...)` (lines 384-389; the `sql_update(Job)...values(task_id=task.id)` that follows stays):

```python
    job = await enqueue_job(
        description,
        kind="god",
        payload=flags or None,
        created_by=f"telegram:{chat_id}",
        origin_channel="telegram",
        origin_ref=str(chat_id),
    )
```

and its final UPDATE (lines 403-405):

```python
    async with async_session() as s:
        await s.execute(sql_update(Task).where(Task.id == task.id).values(
            thread_message_id=reply.message_id,
            origin_thread=str(reply.message_id)))
        await s.execute(sql_update(Job).where(Job.id == job.id).values(
            origin_thread=str(reply.message_id)))
        await s.commit()
```

`_handle_plain_text` chat branch (lines 319-323):

```python
        job = await enqueue_job(
            text,
            kind=JobKind.chat.value,
            created_by=f"telegram:{chat_id}",
            origin_channel="telegram",
            origin_ref=str(chat_id),
        )
```

`cmd_chat` (lines 346-351):

```python
    job = await enqueue_job(
        description,
        kind=JobKind.chat.value,
        payload=flags or None,
        created_by=f"telegram:{chat_id}",
        origin_channel="telegram",
        origin_ref=str(chat_id),
    )
```

`_handle_thread_reply` — the UPDATE to active (lines 773-777):

```python
        await s.execute(
            sql_update(Task).where(Task.id == task.id).values(
                status=TaskStatus.active.value,
                awaiting_since=None,
            )
        )
```

and its continuation `enqueue_job(...)` (lines 800-805):

```python
    job = await enqueue_job(
        response_text,
        kind=continuation_kind,
        payload=continuation_payload,
        created_by=f"telegram:{chat_id}",
        origin_channel="telegram",
        origin_ref=str(chat_id),
        origin_thread=str(task.thread_message_id) if task.thread_message_id else None,
    )
```

`_handle_button` — `approve_plan` UPDATE (lines 915-918):

```python
            await s.execute(
                sql_update(Task).where(Task.id == task.id).values(
                    status=TaskStatus.active.value, awaiting_since=None)
            )
```

`reopen` UPDATE (lines 926-929):

```python
            await s.execute(
                sql_update(Task).where(Task.id == task.id).values(
                    status=TaskStatus.awaiting_user.value,
                    awaiting_since=datetime.now(timezone.utc))
            )
```

`choice` — the UPDATE to active (lines 994-998):

```python
            await s.execute(
                sql_update(Task).where(Task.id == task.id).values(
                    status=TaskStatus.active.value,
                    awaiting_since=None,
                )
            )
```

and its `enqueue_job(...)` (lines 1000-1005):

```python
        job = await enqueue_job(
            f"User selected: {extra}",
            kind=JobKind.task.value,
            payload=None,
            created_by=f"telegram:{chat_id}",
            origin_channel="telegram",
            origin_ref=str(chat_id),
            origin_thread=str(task.thread_message_id) if task.thread_message_id else None,
        )
```

- [ ] **Step 6: `web.py` — origin on dashboard launches**

In `create_job` (line 398-404):

```python
    job = await enqueue_job(
        req.description,
        kind=req.kind,
        payload=payload or None,
        created_by="web",
        origin_channel="web",
        origin_ref="dashboard",
    )
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `pipenv run pytest tests/test_origin.py tests/test_telegram_commands.py tests/test_pure_functions.py tests/test_plans.py tests/test_events.py -v`
Expected: all PASS.

Live check: `pipenv run python -c "
import asyncio; from src.gateway.jobs import enqueue_job
j = asyncio.run(enqueue_job('reply pong', kind='chat', created_by='telegram:42'))
print(j.origin_channel, j.origin_ref)"` → Expected: `telegram 42`.

- [ ] **Step 8: CHANGELOGs + commit**

Prepend to `.context/modules/gateway/CHANGELOG.md`:

```markdown
## 2026-09-25 — persisted origin on every launch (jobs.origin_*, tasks.origin_*)

- `jobs.enqueue_job` gains keyword-only `origin_channel/origin_ref/origin_thread` (derived from `created_by` via the pure `origin_from_created_by` when omitted); every Telegram launch site (`/task`, `/god`, `/chat`, bare text, thread replies, choice buttons) and `POST /api/jobs` pass an explicit origin; the Telegram root reply's message id is persisted as `origin_thread` on both the Task and the Job. `_job_to_chat` is still populated (kill-switch fallback until P1).
- Why: spec §0 bullet 2 — the in-process dict was the only job→chat binding (`telegram_bot.py:38,1028`); web launches had none.
```

Prepend to `.context/modules/runner/CHANGELOG.md`:

```markdown
## 2026-09-25 — scheduler stamps origin; tasks.awaiting_since maintained

- `main._tick_schedules` sets `origin_channel="scheduler", origin_ref=<schedule name>`; `_set_task_status` (and the two direct awaiting_user updates in `_update_task_after_job`, now routed through it) stamp/clear `tasks.awaiting_since` via the pure `awaiting_since_for`.
```

```bash
git add src/gateway/jobs.py src/gateway/telegram_bot.py src/gateway/web.py src/runner/main.py tests/test_origin.py .context/modules/gateway/CHANGELOG.md .context/modules/runner/CHANGELOG.md
git commit -m "feat(gateway+runner): persist job/task origin on every launch; tasks.awaiting_since"
```

---

### Task 5: `src/notify/` — outbox rows, Telegram renderer with limits, `python -m src.notify` CLI


**Execution position:** 11 of 21 — previous: Task 4, next: Task 6 (see Global Constraints "Execution order").

**Files:**
- Create: `src/notify/__init__.py`, `src/notify/outbox.py`, `src/notify/telegram.py`, `src/notify/__main__.py`
- Modify: `src/config.py` (add `notify_outbox`), `src/db.py` (add `CHANNEL_NOTIFY_OUTBOX`)
- Create: `.context/modules/notify/CONTEXT.md`, `.context/modules/notify/CHANGELOG.md`, `.context/modules/notify/skills/{GOTCHAS,PATTERNS,DEBUG}.md` (via `scripts/seed-module-skills.sh`)
- Modify: `.context/modules/db/CHANGELOG.md`, `.context/SYSTEM.md` (three `src/notify/*` module-graph rows — added here so `main.py`'s import in Task 6 and the bot's in Task 7 have rows to point at)
- Test: `tests/test_notify_outbox.py`, `tests/test_notify_telegram.py`

**Interfaces:**
- Consumes: `Notification` model (Task 1); `settings.allowed_chat_ids`, `settings.telegram_bot_token`.
- Produces (consumed by Tasks 6, 7, 12, 13):
  - `settings.notify_outbox: bool = False` (env `NOTIFY_OUTBOX`) — ships OFF here and in Task 6 (rows written by the runner would have no consumer until Task 7 adds `_outbox_listener`; a runner+bot restart between those commits must not go dark and must not accumulate a backlog that Task 7's first drain would re-send). Task 7 flips the default to `True` in the same commit as the listener.
  - `db.CHANNEL_NOTIFY_OUTBOX = "notify:outbox"` (pub: body = notification id).
  - `outbox.Notice` frozen dataclass: `notice_kind: str, body: str, severity: str = "info", subject_type: str | None = None, subject_id: str | None = None, actions: dict | None = None, channel: str = "telegram", target: str | None = None, thread: str | None = None`.
  - `outbox.NOTICE_KINDS: frozenset[str]`, `outbox.TASK_NOTIFY_TYPES: tuple[str, ...]`, `outbox.STATUSES = ("pending", "sending", "sent", "failed", "skipped")`, `outbox.MAX_ATTEMPTS = 5`, `outbox.SENDING_LEASE_SECONDS = 300`.
  - `outbox.notice_kind_for_task_type(notify_type: str) -> str` (pure; raises `ValueError` on unknown).
  - `outbox.should_notify_job(*, status: str, kind: str, task_id, origin_channel: str | None) -> bool` (pure) — **this function is the spec's §4.2 "Card eligibility" paragraph in code**, which the P0 scope cell names as part of the `src/notify/` deliverable (round-2 #32 wrote it to stop ~20 machine jobs/day flooding the chat). The rules it encodes, verbatim from §4.2:
    - a JobCard/DoneCard goes to jobs whose `origin_channel` is in the eligible set `{telegram, pwa, cli}`. **P0 alias:** the current dashboard's channel string is `web`, and `pwa` does not exist until P2 — so `COMPLETION_DM_CHANNELS = ("telegram", "web", "pwa", "cli")` carries both spellings and a comment says `web` is the P0 name for `pwa`'s predecessor;
    - `notify=never` rows send nothing and `notify=always` rows get the full card set — **but `schedules.notify` lands in migration 008 (P1)**, so P0 has no such column and treats **every** schedule row as `failures`: the FailedCard only. The plan states this rather than pretending the column exists;
    - failures are always eligible (a scheduled failure was silent before — state map §2.3);
    - **dispatch-MCP / escalation / self-diagnose children inherit the parent's eligibility**, they do not resolve their own: Task 6 passes the *parent* job's `origin_channel` (`jobs.origin_channel` of the job named by `created_by="job:<id>"` / `escalation:<id>`) rather than the child's own `system`, so a child of a Telegram launch reports and a child of a scheduler row does not;
    - `watch <job>`/`mute <job>` (any job, machine ones included) are **P1** (§4.2 last sentence, `test_views`), not P0.
  - `outbox.build_job_notice(*, job_id, status, kind, resolved_skill, summary, error_message, terminal_reason, origin_channel, origin_ref, origin_thread, created_by, task_id=None, model_served=None, num_turns=None, duration_seconds=None) -> Notice | None` (pure).
  - `outbox.build_task_notice(*, task_id, notify_type, text, question=None, choices=None, target=None, thread=None) -> Notice` (pure).
  - `outbox.build_ops_notice(*, kind: str, severity: str, text: str, subject: str | None = None, target: str | None = None) -> Notice` (pure).
  - `outbox.retry_delay_seconds(attempts: int) -> int`, `outbox.transition_after_failure(attempts_so_far: int, now: datetime) -> tuple[str, int, datetime]` (pure).
  - `async outbox.enqueue_notice(notice: Notice) -> uuid.UUID | None` (None when the switch is off or the insert fails — the runner/bot producers), `async outbox.record_notice(notice, *, status, external_ref=None, last_error=None) -> uuid.UUID | None` (NOT gated by the switch: it is the CLI's alert-history write after a direct send), `async outbox.pending_notices(limit: int = 20, now=None) -> list[Notification]`, `async outbox.claim_notice(notice_id, now=None) -> bool` (`UPDATE … SET status='sending', attempts=attempts+1, next_attempt_at=now+lease WHERE id=:id AND status='pending'`; rowcount 0 → another drainer has it — the bot listener and a manual `python -m src.notify drain` can otherwise both send the same DM), `async outbox.release_stuck_sending(now=None) -> int` (rows left `sending` past their 5-min lease go back to `pending`; the listener calls it at startup), `async outbox.mark_sent(notice_id, external_ref: str, *, subject_type=None, subject_id=None) -> None` (does NOT bump `attempts` — the claim did), `async outbox.mark_failed(notice_id, error: str, *, attempts_so_far: int, subject_type=None, subject_id=None) -> str` (returns the new status; `attempts_so_far` is the value read BEFORE the claim).
  - `telegram.TelegramMessage` frozen dataclass: `chat_id: int, text: str, buttons: tuple[tuple[tuple[str, str], ...], ...] = (), reply_to_message_id: int | None = None`.
  - `telegram.render_telegram(notice_like, *, owner_chat_id: int) -> TelegramMessage` (pure; accepts a `Notice` or a `Notification` row), `telegram.fit_text(head, body, *, footer="", limit=4096) -> str`, `telegram.validate_callback(data: str) -> str`, `telegram.build_buttons(actions) -> tuple`, `telegram.keyboard_markup(buttons)`, `async telegram.send_via_bot(bot, msg) -> int`, `async telegram.send_via_http(token: str, msg) -> int`.
  - CLI: `python -m src.notify send --kind <ops_alert|credential_canary|…> --severity <info|warn|critical> --text "<text>" [--subject job:<uuid>] [--target <chat_id>]` (exit 0 when delivered OR recorded; 1 when neither), `python -m src.notify drain [--limit N]`.
  - Audit kinds appended to a job's JSONL when `subject_type == "job"`: `notice_queued{notice_id, notice_kind}`, `notice_sent{notice_id, external_ref}`, `notice_failed{notice_id, error}`. `record_notice` emits the kind that matches the status it writes (`sent` → `notice_sent`, `failed` → `notice_failed`, otherwise `notice_queued`), so a CLI-delivered canary/ops notice on a job subject is audited as sent. P0 deviation from spec §2.7, stated in the notify CONTEXT.md: these three kinds go to the JSONL only and are NOT mirrored to `jobs:stream:<id>` (P1, with the `jobs:reviewed` work).

- [ ] **Step 1: Write the failing outbox tests**

Create `tests/test_notify_outbox.py`:

```python
"""
Notification outbox — pure builders + retry math (no DB). The async wrappers
are thin SQLAlchemy calls exercised live in Task 6/7 smoke steps.

Run: pipenv run pytest tests/test_notify_outbox.py -v
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from src.notify.outbox import (
    MAX_ATTEMPTS,
    NOTICE_KINDS,
    STATUSES,
    TASK_NOTIFY_TYPES,
    Notice,
    build_job_notice,
    build_ops_notice,
    build_task_notice,
    notice_kind_for_task_type,
    retry_delay_seconds,
    should_notify_job,
    transition_after_failure,
)

JOB = uuid.uuid4()
NOW = datetime(2026, 9, 25, 3, 0, tzinfo=timezone.utc)


def _job(**over):
    base = dict(job_id=JOB, status="completed", kind="chat", resolved_skill="chat",
                summary="pong", error_message=None, terminal_reason="ok",
                origin_channel="telegram", origin_ref="123", origin_thread="777",
                created_by="telegram:123", task_id=None, model_served="claude-sonnet-4-6",
                num_turns=1, duration_seconds=3.2)
    base.update(over)
    return build_job_notice(**base)


class TestVocabulary:
    def test_every_tasks_notify_type_has_an_outbox_kind(self):
        # spec §9 P0 test gate: "every tasks:notify kind has an outbox equivalent"
        legacy = ("approval_request", "question", "choices", "plan", "plan_approval",
                  "completed", "progress", "failed", "review_flagged")   # telegram_bot.py:1087-1271
        assert TASK_NOTIFY_TYPES == legacy
        for t in legacy:
            # two asserts, not a chained comparison: `a == b in c` is valid
            # Python but reads as a precedence bug and invites a wrong "fix".
            assert notice_kind_for_task_type(t) == f"task_{t}"
            assert f"task_{t}" in NOTICE_KINDS

    def test_unknown_task_type_rejected(self):
        with pytest.raises(ValueError):
            notice_kind_for_task_type("bogus")

    def test_kinds_fit_column(self):
        assert all(len(k) <= 32 for k in NOTICE_KINDS)
        assert {"job_completed", "job_failed", "ops_alert", "credential_canary",
                "quota_paused", "quota_resumed"} <= NOTICE_KINDS

    def test_statuses_include_sending(self):
        # `sending` = claimed by exactly one drainer (bot listener OR the CLI drain).
        assert STATUSES == ("pending", "sending", "sent", "failed", "skipped")


class TestShouldNotify:
    def test_completed_task_less_job_dms(self):
        assert should_notify_job(status="completed", kind="chat", task_id=None,
                                 origin_channel="telegram")

    def test_completed_task_bound_job_is_covered_by_task_card(self):
        assert not should_notify_job(status="completed", kind="task", task_id=uuid.uuid4(),
                                     origin_channel="telegram")

    def test_failed_always_dms_even_task_bound(self):
        assert should_notify_job(status="failed", kind="task", task_id=uuid.uuid4(),
                                 origin_channel="telegram")

    def test_internal_kinds_never_dm(self):
        assert not should_notify_job(status="failed", kind="_writeback", task_id=None,
                                     origin_channel="scheduler")
        assert not should_notify_job(status="completed", kind="_evaluate", task_id=None,
                                     origin_channel="telegram")

    def test_cancelled_never_dms(self):
        assert not should_notify_job(status="cancelled", kind="chat", task_id=None,
                                     origin_channel="telegram")

    def test_scheduled_completion_is_quiet(self):
        # spec §4.5: per-schedule notify defaults to `failures` — 79 scheduler
        # completions a week must not become 79 DMs.
        assert not should_notify_job(status="completed", kind="atlas-report", task_id=None,
                                     origin_channel="scheduler")

    def test_dispatch_completion_is_quiet(self):
        # dispatch-mcp / event-trigger / self-diagnose / escalation children all
        # derive origin_channel="system" (origin_from_created_by).
        assert not should_notify_job(status="completed", kind="self-diagnose", task_id=None,
                                     origin_channel="system")
        assert not should_notify_job(status="completed", kind="chat", task_id=None,
                                     origin_channel=None)

    def test_scheduled_failure_still_dms(self):
        # The P0 exit criterion: a scheduled FAILURE DMs within 60 s.
        assert should_notify_job(status="failed", kind="atlas-report", task_id=None,
                                 origin_channel="scheduler")
        assert should_notify_job(status="failed", kind="self-diagnose", task_id=None,
                                 origin_channel="system")

    def test_human_launchers_get_completion_dms(self):
        # spec §4.2 eligible set {telegram, pwa, cli} + the dashboard's current
        # `web` spelling (pwa arrives in P2).
        for ch in ("telegram", "web", "pwa", "cli"):
            assert should_notify_job(status="completed", kind="chat", task_id=None,
                                     origin_channel=ch), ch

    def test_a_child_inherits_the_parents_eligibility(self):
        # spec §4.2: "dispatch-MCP / escalation / self-diagnose children
        # inherit the parent's eligibility". The child's own created_by derives
        # origin_channel="system"; Task 6 resolves the PARENT's channel and
        # passes that, so this pure function only has to honour what it is
        # given — both directions are asserted here so a regression in Task 6's
        # lookup shows up as a failing pair, not a silent flood.
        assert should_notify_job(status="completed", kind="chat", task_id=None,
                                 origin_channel="telegram")      # parent = Telegram launch
        assert not should_notify_job(status="completed", kind="chat", task_id=None,
                                     origin_channel="scheduler")  # parent = schedule row


class TestBuildJobNotice:
    def test_completed_telegram_job_targets_its_chat_and_thread(self):
        n = _job()
        assert isinstance(n, Notice)
        assert n.notice_kind == "job_completed" and n.severity == "info"
        assert n.target == "123" and n.thread == "777"
        assert n.subject_type == "job" and n.subject_id == str(JOB)
        assert "pong" in n.body and str(JOB)[:8] in n.body
        assert n.actions["buttons"] == []

    def test_build_job_notice_scheduled_failure_targets_owner(self):
        # Review Focus 2: scheduler job, no task, no chat → owner DM (target None).
        n = _job(status="failed", kind="atlas-daily-brief", resolved_skill="atlas-daily-brief",
                 origin_channel="scheduler", origin_ref="atlas-daily-brief", origin_thread=None,
                 created_by="scheduler", error_message="API terminal error: 529",
                 terminal_reason="api_error", summary=None)
        assert n is not None and n.notice_kind == "job_failed" and n.severity == "warn"
        assert n.target is None and n.thread is None
        assert "atlas-daily-brief" in n.body and "api_error" in n.body and "529" in n.body
        assert n.actions["buttons"] == [[["Details", f"jd:{str(JOB)[:8]}"]]]

    def test_web_launch_targets_owner(self):
        n = _job(origin_channel="web", origin_ref="dashboard", origin_thread=None, created_by="web")
        assert n.target is None

    def test_scheduler_origin_without_ref_says_via_scheduler(self):
        # enqueue_job(created_by="scheduler") derives ("scheduler", None): the
        # card must read "via scheduler", never "via None".
        n = _job(status="failed", origin_channel="scheduler", origin_ref=None, origin_thread=None,
                 created_by="scheduler", error_message="boom", terminal_reason="error", summary=None)
        assert n is not None and "via scheduler" in n.body and "None" not in n.body

    def test_returns_none_when_not_notifying(self):
        assert _job(kind="_learning_apply", resolved_skill="_learning_apply") is None
        assert _job(origin_channel="scheduler", origin_ref="atlas-report", created_by="scheduler") is None

    def test_body_is_unbounded_here(self):
        # Limits belong to the renderer (Task 5 telegram.py), not the builder.
        n = _job(summary="x" * 10_000)
        assert len(n.body) > 4096


class TestBuildTaskNotice:
    TASK = uuid.uuid4()

    def test_approval_request_buttons_match_legacy_callbacks(self):
        n = build_task_notice(task_id=self.TASK, notify_type="approval_request",
                              text="done", target="123", thread="777")
        p = str(self.TASK)[:8]
        assert n.notice_kind == "task_approval_request"
        assert n.actions["buttons"] == [[["Approve", f"approve:{p}"],
                                         ["Send Feedback", f"feedback:{p}"],
                                         ["View Details", f"details:{p}"]]]
        assert "rate:" not in str(n.actions)     # spec §4.1: /rate leaves the cards

    def test_choices_become_one_button_per_row_capped_at_8(self):
        n = build_task_notice(task_id=self.TASK, notify_type="choices", text="",
                              question="Pick", choices=[f"opt{i}" for i in range(12)])
        assert len(n.actions["buttons"]) == 8
        assert n.actions["buttons"][0] == [["opt0", f"choice:{str(self.TASK)[:8]}:0"]]
        assert n.body == "Pick"

    @pytest.mark.parametrize("t,expected", [("failed", "warn"), ("review_flagged", "warn"),
                                            ("progress", "info"), ("completed", "info")])
    def test_severity(self, t, expected):
        assert build_task_notice(task_id=self.TASK, notify_type=t, text="x").severity == expected


class TestOpsNotice:
    def test_ops_notice_shape(self):
        n = build_ops_notice(kind="credential_canary", severity="critical", text="FAILED",
                             subject="job:abc")
        assert n.notice_kind == "credential_canary" and n.subject_type == "job"
        assert n.subject_id == "abc" and n.target is None

    def test_unknown_kind_rejected(self):
        with pytest.raises(ValueError):
            build_ops_notice(kind="nope", severity="info", text="x")


class TestRetry:
    def test_retry_delay_backoff(self):
        assert [retry_delay_seconds(a) for a in (1, 2, 3, 4, 5, 9)] == [30, 60, 120, 240, 480, 600]

    def test_mark_failed_keeps_pending_until_max_attempts(self):
        status, attempts, nxt = transition_after_failure(0, NOW)
        assert (status, attempts) == ("pending", 1) and nxt == NOW + timedelta(seconds=30)
        status, attempts, nxt = transition_after_failure(MAX_ATTEMPTS - 1, NOW)
        assert (status, attempts) == ("failed", MAX_ATTEMPTS)
```

- [ ] **Step 2: Write the failing renderer tests**

Create `tests/test_notify_telegram.py`:

```python
"""
Telegram renderer — the ONLY code that knows the 4096-char / 64-byte callback
/ 8-button limits (C23). Pure.

Run: pipenv run pytest tests/test_notify_telegram.py -v
"""

from __future__ import annotations

import pytest

from src.notify.outbox import Notice
from src.notify.telegram import (
    CALLBACK_LIMIT_BYTES,
    MAX_BUTTONS,
    TELEGRAM_TEXT_LIMIT,
    TelegramMessage,
    build_buttons,
    fit_text,
    render_telegram,
    validate_callback,
)

OWNER = 999


def _n(**over):
    base = dict(notice_kind="job_completed", body="pong", severity="info",
                subject_type="job", subject_id="abcdef12-0000", actions={"buttons": [], "job8": "abcdef12"},
                target="123", thread="777")
    base.update(over)
    return Notice(**base)


class TestLimits:
    def test_constants(self):
        assert (TELEGRAM_TEXT_LIMIT, CALLBACK_LIMIT_BYTES, MAX_BUTTONS) == (4096, 64, 8)

    def test_fit_text_never_exceeds_limit(self):
        text = fit_text("✅ done", "x" * 10_000, footer="\n/status abcdef12")
        assert len(text) <= 4096
        assert text.startswith("✅ done") and text.endswith("/status abcdef12")
        assert "… (truncated)" in text

    def test_fit_text_short_untouched(self):
        assert fit_text("h", "body", footer="") == "h\nbody"

    def test_callback_over_64_bytes_rejected(self):
        with pytest.raises(ValueError):
            validate_callback("choice:" + "é" * 40)     # 87 bytes
        assert validate_callback("jd:abcdef12") == "jd:abcdef12"

    def test_buttons_capped_at_8_total(self):
        rows = [[[f"b{i}", f"choice:abcdef12:{i}"]] for i in range(12)]
        out = build_buttons({"buttons": rows})
        assert sum(len(r) for r in out) == 8

    def test_buttons_none_or_missing(self):
        assert build_buttons(None) == () and build_buttons({}) == ()


class TestRender:
    def test_job_completed_targets_chat_and_thread(self):
        msg = render_telegram(_n(), owner_chat_id=OWNER)
        assert isinstance(msg, TelegramMessage)
        assert msg.chat_id == 123 and msg.reply_to_message_id == 777
        assert msg.text.startswith("✅ done") and "/status abcdef12" in msg.text
        assert msg.buttons == ()

    def test_owner_fallback_when_no_target(self):
        msg = render_telegram(_n(target=None, thread=None), owner_chat_id=OWNER)
        assert msg.chat_id == OWNER and msg.reply_to_message_id is None

    def test_non_numeric_target_falls_back_to_owner(self):
        assert render_telegram(_n(target="dashboard"), owner_chat_id=OWNER).chat_id == OWNER

    def test_failed_job_has_details_button(self):
        msg = render_telegram(_n(notice_kind="job_failed", severity="warn",
                                 actions={"buttons": [[["Details", "jd:abcdef12"]]], "job8": "abcdef12"}),
                              owner_chat_id=OWNER)
        assert msg.text.startswith("❌ failed")
        assert msg.buttons == ((("Details", "jd:abcdef12"),),)

    def test_every_notice_kind_renders(self):
        from src.notify.outbox import NOTICE_KINDS
        for kind in sorted(NOTICE_KINDS):
            msg = render_telegram(_n(notice_kind=kind, actions=None), owner_chat_id=OWNER)
            assert msg.text and len(msg.text) <= 4096

    def test_renders_a_row_object_too(self):
        from types import SimpleNamespace
        row = SimpleNamespace(notice_kind="ops_alert", body="runner down", severity="critical",
                              subject_type="ops", subject_id=None, actions=None, target=None, thread=None)
        assert render_telegram(row, owner_chat_id=OWNER).text.startswith("🚨 ops")
```

- [ ] **Step 3: Run both test files to verify they fail**

Run: `pipenv run pytest tests/test_notify_outbox.py tests/test_notify_telegram.py -v`
Expected: `ModuleNotFoundError: No module named 'src.notify'`.

- [ ] **Step 4: Settings + Redis constant**

`src/config.py` — after `max_eval_rounds`:

```python
    # Notifications (P0, spec §4.5). The runner ALWAYS publishes the legacy
    # tasks:notify / jobs:done channels; with this on it ALSO writes
    # `notifications` rows and the bot's outbox listener (not the legacy
    # _job_to_chat / _task_notifier renderers) delivers them. Ships False:
    # flipped to True in the bot-listener commit (P0 plan Task 7) — rows
    # without a consumer would only pile up. NOTIFY_OUTBOX=0 is the kill switch.
    notify_outbox: bool = False
```

`src/db.py` — after `CHANNEL_JOB_CANCEL`:

```python
CHANNEL_NOTIFY_OUTBOX = "notify:outbox"           # pub: body = notifications.id (bot drains on nudge + 30s poll)
```

- [ ] **Step 5: Implement `src/notify/outbox.py`**

```python
"""
Notification outbox (P0; spec §4.5, §2.3 row 007, §2.7 notice_* events).

Rows in `notifications` are the durable record of every owner-facing notice.
Producers (runner, bot, `python -m src.notify send`) only INSERT + nudge; the
bot's outbox listener (gateway/telegram_bot._outbox_listener) and the CLI's
`drain` deliver and stamp status/attempts/external_ref. A bot restart
therefore loses nothing: whatever is `pending` is picked up by the 30 s poll.

Pure builders (build_*_notice, should_notify_job, retry math) carry the
policy and are tested without I/O; the async functions are thin wrappers.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from sqlalchemy import select, update as sql_update

from src import audit_log
from src.config import settings
from src.db import CHANNEL_NOTIFY_OUTBOX, async_session, redis
from src.models import Notification

logger = structlog.get_logger(__name__)

# The nine legacy `tasks:notify` types (telegram_bot.py:1087-1271), in order.
TASK_NOTIFY_TYPES: tuple[str, ...] = (
    "approval_request", "question", "choices", "plan", "plan_approval",
    "completed", "progress", "failed", "review_flagged",
)
NOTICE_KINDS: frozenset[str] = frozenset(
    {"job_completed", "job_failed"}
    | {f"task_{t}" for t in TASK_NOTIFY_TYPES}
    | {"ops_alert", "credential_canary", "quota_paused", "quota_resumed"}
)
SEVERITIES: tuple[str, ...] = ("info", "warn", "critical")
# `sending` = claimed by one drainer (bot listener or `python -m src.notify
# drain`); next_attempt_at holds the lease expiry while a row is `sending`.
STATUSES: tuple[str, ...] = ("pending", "sending", "sent", "failed", "skipped")
MAX_ATTEMPTS = 5
SENDING_LEASE_SECONDS = 300
# Card eligibility (spec §4.2 "Card eligibility", the P0 scope cell's
# "card eligibility per §4.2"). The spec's eligible set is {telegram, pwa,
# cli}; `web` is the CURRENT dashboard's channel string and `pwa` only exists
# from P2, so both spellings are listed and mean the same thing in P0.
# Machine launchers (scheduler, dispatch-mcp / event-trigger / escalation =
# "system") DM on failure only. schedules.notify (never|failures|always) is a
# migration-008 column (P1): in P0 every schedule row behaves as `failures`.
COMPLETION_DM_CHANNELS: tuple[str, ...] = ("telegram", "web", "pwa", "cli")


@dataclass(frozen=True)
class Notice:
    notice_kind: str
    body: str
    severity: str = "info"
    subject_type: str | None = None      # job | task | schedule | ops
    subject_id: str | None = None
    actions: dict[str, Any] | None = None  # {"buttons": [[[label, callback], ...], ...], ...}
    channel: str = "telegram"
    target: str | None = None            # chat id; None → owner
    thread: str | None = None            # Telegram message id to reply under


# ── Pure policy ─────────────────────────────────────────────────────────────


def notice_kind_for_task_type(notify_type: str) -> str:
    if notify_type not in TASK_NOTIFY_TYPES:
        raise ValueError(f"unknown tasks:notify type {notify_type!r}")
    return f"task_{notify_type}"


def should_notify_job(*, status: str, kind: str, task_id: Any,
                      origin_channel: str | None) -> bool:
    """Card eligibility, spec §4.2 — the only place P0 decides who gets a card.

    - internal kinds (`_writeback`, `_evaluate`, `_learning_apply`): never;
    - `failed`: always eligible (a scheduled failure was silent before —
      state map §2.3), so the FailedCard is what a `notify=failures` row gets;
    - `completed`: only when no task card already covers it AND the launch
      channel is eligible (COMPLETION_DM_CHANNELS = the spec's
      {telegram, pwa, cli} plus the dashboard's current `web` spelling) —
      scheduler / dispatch / self-diagnose completions would otherwise be
      10-20 DMs a day (state map §2.3: scheduler 79, dispatch-mcp 67,
      event-trigger 312 vs Telegram 55 in 7 d);
    - `notify=never|always` per schedule row: a migration-008 column (P1).
      P0 has no such column, so every schedule row behaves as `failures`;
    - children (dispatch-MCP, escalation, self-diagnose) INHERIT the parent's
      eligibility: the caller passes the parent job's origin_channel, so this
      function never sees the child's own "system". Task 6 does that lookup.
    """
    if (kind or "").startswith("_"):
        return False
    if status == "failed":
        return True
    if status == "completed":
        return task_id is None and (origin_channel or "") in COMPLETION_DM_CHANNELS
    return False


def _fmt_duration(seconds: float | None) -> str:
    if not seconds or seconds < 0:
        return ""
    m, s = divmod(int(seconds), 60)
    return f" · {m}m{s:02d}s" if m else f" · {s}s"


def build_job_notice(
    *, job_id: Any, status: str, kind: str, resolved_skill: str | None,
    summary: str | None, error_message: str | None, terminal_reason: str | None,
    origin_channel: str | None, origin_ref: str | None, origin_thread: str | None,
    created_by: str, task_id: Any = None, model_served: str | None = None,
    num_turns: int | None = None, duration_seconds: float | None = None,
) -> Notice | None:
    """Pure. The DoneCard / FailedCard body for a job terminal, or None."""
    if not should_notify_job(status=status, kind=kind, task_id=task_id,
                             origin_channel=origin_channel):
        return None
    job8 = str(job_id)[:8]
    label = resolved_skill or kind
    # "via <schedule name>" when known, else the channel, else created_by —
    # never "via None" (enqueue_job(created_by="scheduler") derives ref None).
    source = ((origin_ref if origin_channel == "scheduler" and origin_ref else None)
              or origin_channel or created_by)
    header = f"{job8} · {label}{_fmt_duration(duration_seconds)}"
    if model_served:
        header += f" · {model_served}"
    if num_turns:
        header += f" · {num_turns} turns"
    if status == "completed":
        body = f"{header}\n\n{(summary or '').strip() or '(no summary)'}"
        buttons: list[list[list[str]]] = []
        severity = "info"
    else:
        body = (f"{header} · {terminal_reason or 'error'} · via {source}\n\n"
                f"{(error_message or 'unknown error').strip()}")
        buttons = [[["Details", f"jd:{job8}"]]]
        severity = "warn"
    target = origin_ref if (origin_channel == "telegram" and origin_ref) else None
    return Notice(
        notice_kind=f"job_{status}", body=body, severity=severity,
        subject_type="job", subject_id=str(job_id),
        actions={"buttons": buttons, "job8": job8},
        target=target, thread=(origin_thread if target else None),
    )


def build_task_notice(
    *, task_id: Any, notify_type: str, text: str, question: str | None = None,
    choices: list[str] | None = None, target: str | None = None, thread: str | None = None,
) -> Notice:
    """Pure. One card per legacy tasks:notify type; callback strings are the
    ones `_handle_button` already parses. No rating rows (spec §4.1)."""
    kind = notice_kind_for_task_type(notify_type)
    prefix = str(task_id)[:8]
    buttons: list[list[list[str]]] = []
    if notify_type == "approval_request":
        buttons = [[["Approve", f"approve:{prefix}"],
                    ["Send Feedback", f"feedback:{prefix}"],
                    ["View Details", f"details:{prefix}"]]]
    elif notify_type == "choices":
        buttons = [[[str(c)[:40], f"choice:{prefix}:{i}"]]
                   for i, c in enumerate((choices or [])[:8])]
    elif notify_type == "plan":
        buttons = [[["Cancel plan", f"cancel:{prefix}"]]]
    elif notify_type == "plan_approval":
        buttons = [[["Approve plan", f"approve_plan:{prefix}"], ["Cancel", f"cancel:{prefix}"]]]
    elif notify_type == "completed":
        buttons = [[["Reopen", f"reopen:{prefix}"], ["View Details", f"details:{prefix}"]]]
    body = (question or "Pick one:") if notify_type == "choices" else (text or "")
    severity = "warn" if notify_type in ("failed", "review_flagged") else "info"
    return Notice(
        notice_kind=kind, body=body, severity=severity,
        subject_type="task", subject_id=str(task_id),
        actions={"buttons": buttons, "prefix": prefix, "choices": list(choices or [])},
        target=target, thread=thread,
    )


def build_ops_notice(*, kind: str, severity: str, text: str,
                     subject: str | None = None, target: str | None = None) -> Notice:
    """Pure. Out-of-band alerts (launchd scripts, canary, quota notifier)."""
    if kind not in NOTICE_KINDS:
        raise ValueError(f"unknown notice kind {kind!r}")
    if severity not in SEVERITIES:
        raise ValueError(f"unknown severity {severity!r}")
    subject_type = subject_id = None
    if subject and ":" in subject:
        subject_type, subject_id = subject.split(":", 1)
    return Notice(notice_kind=kind, body=text, severity=severity,
                  subject_type=subject_type, subject_id=subject_id,
                  actions=None, target=target)


def retry_delay_seconds(attempts: int) -> int:
    """30 s · 2^(attempts-1), capped at 600 s."""
    return min(30 * (2 ** max(attempts - 1, 0)), 600)


def transition_after_failure(attempts_so_far: int, now: datetime) -> tuple[str, int, datetime]:
    """Pure. (status, attempts, next_attempt_at) after one failed delivery."""
    attempts = attempts_so_far + 1
    status = "failed" if attempts >= MAX_ATTEMPTS else "pending"
    return status, attempts, now + timedelta(seconds=retry_delay_seconds(attempts))


# ── Async wrappers ──────────────────────────────────────────────────────────


def _row(notice: Notice, *, status: str, external_ref: str | None = None,
         last_error: str | None = None, attempts: int = 0) -> Notification:
    return Notification(
        notice_kind=notice.notice_kind, subject_type=notice.subject_type,
        subject_id=notice.subject_id, severity=notice.severity, body=notice.body,
        actions=notice.actions, channel=notice.channel, target=notice.target,
        thread=notice.thread, status=status, attempts=attempts,
        external_ref=external_ref, last_error=last_error,
        sent_at=datetime.now(timezone.utc) if status == "sent" else None,
    )


def _audit(notice_subject_type: str | None, subject_id: str | None, kind: str, **fields: Any) -> None:
    if notice_subject_type == "job" and subject_id:
        try:
            audit_log.append(subject_id, kind, **fields)
        except Exception:  # noqa: BLE001 — audit is best-effort here
            logger.debug("notice audit append failed", kind=kind)


async def record_notice(notice: Notice, *, status: str, external_ref: str | None = None,
                        last_error: str | None = None) -> uuid.UUID | None:
    """Insert a row in a given status. NOT gated by settings.notify_outbox: the
    CLI calls this after a DIRECT send and the row is the alert history."""
    if notice.notice_kind not in NOTICE_KINDS:
        raise ValueError(f"unknown notice kind {notice.notice_kind!r}")
    if status not in STATUSES:
        raise ValueError(f"unknown status {status!r}")
    row = _row(notice, status=status, external_ref=external_ref, last_error=last_error,
               attempts=1 if status in ("sent", "failed") else 0)
    async with async_session() as s:
        s.add(row)
        await s.commit()
        await s.refresh(row)
    # Audit the kind that matches what was written (spec §2.7 notice_*).
    if status == "sent":
        _audit(notice.subject_type, notice.subject_id, "notice_sent",
               notice_id=str(row.id), external_ref=external_ref or "")
    elif status == "failed":
        _audit(notice.subject_type, notice.subject_id, "notice_failed",
               notice_id=str(row.id), error=(last_error or "")[:200])
    else:
        _audit(notice.subject_type, notice.subject_id, "notice_queued",
               notice_id=str(row.id), notice_kind=notice.notice_kind)
    return row.id


async def enqueue_notice(notice: Notice) -> uuid.UUID | None:
    """Insert a pending row and nudge the bot. None when the outbox is off or
    the insert failed (logged) — producers never raise on a notice."""
    if not settings.notify_outbox:
        return None
    try:
        row_id = await record_notice(notice, status="pending")
    except Exception:  # noqa: BLE001
        logger.exception("notice insert failed", kind=notice.notice_kind)
        return None
    try:
        await redis.publish(CHANNEL_NOTIFY_OUTBOX, str(row_id))
    except Exception:  # noqa: BLE001 — the 30 s poll delivers without the nudge
        logger.warning("outbox nudge failed — poll will deliver", notice_id=str(row_id))
    return row_id


async def pending_notices(limit: int = 20, now: datetime | None = None) -> list[Notification]:
    now = now or datetime.now(timezone.utc)
    async with async_session() as s:
        result = await s.execute(
            select(Notification)
            .where(Notification.status == "pending",
                   Notification.attempts < MAX_ATTEMPTS,
                   (Notification.next_attempt_at.is_(None)) | (Notification.next_attempt_at <= now))
            .order_by(Notification.created_at)
            .limit(limit)
        )
        return list(result.scalars())


async def claim_notice(notice_id: uuid.UUID, now: datetime | None = None) -> bool:
    """Take exclusive ownership of one pending row before sending. The bot's
    listener and a manual `python -m src.notify drain` both select the same
    `pending` rows; without this claim each could send the DM. Bumps
    `attempts` and parks the lease expiry in `next_attempt_at`. False when
    someone else already has it (rowcount 0) — the caller skips the row."""
    now = now or datetime.now(timezone.utc)
    async with async_session() as s:
        res = await s.execute(
            sql_update(Notification)
            .where(Notification.id == notice_id, Notification.status == "pending")
            .values(status="sending", attempts=Notification.attempts + 1,
                    next_attempt_at=now + timedelta(seconds=SENDING_LEASE_SECONDS))
        )
        await s.commit()
    return bool(res.rowcount)


async def release_stuck_sending(now: datetime | None = None) -> int:
    """Rows a crashed drainer left `sending` past their lease go back to
    `pending` (the bot listener calls this once at startup). Returns count."""
    now = now or datetime.now(timezone.utc)
    async with async_session() as s:
        res = await s.execute(
            sql_update(Notification)
            .where(Notification.status == "sending", Notification.next_attempt_at <= now)
            .values(status="pending", next_attempt_at=None)
        )
        await s.commit()
    return int(res.rowcount or 0)


async def mark_sent(notice_id: uuid.UUID, external_ref: str, *,
                    subject_type: str | None = None, subject_id: str | None = None) -> None:
    """`attempts` is NOT bumped here — claim_notice already counted this try."""
    async with async_session() as s:
        await s.execute(
            sql_update(Notification).where(Notification.id == notice_id).values(
                status="sent", external_ref=external_ref[:64],
                sent_at=datetime.now(timezone.utc), next_attempt_at=None, last_error=None)
        )
        await s.commit()
    _audit(subject_type, subject_id, "notice_sent", notice_id=str(notice_id), external_ref=external_ref)


async def mark_failed(notice_id: uuid.UUID, error: str, *, attempts_so_far: int,
                      subject_type: str | None = None, subject_id: str | None = None) -> str:
    status, attempts, next_at = transition_after_failure(attempts_so_far, datetime.now(timezone.utc))
    async with async_session() as s:
        await s.execute(
            sql_update(Notification).where(Notification.id == notice_id).values(
                status=status, attempts=attempts, last_error=error[:500], next_attempt_at=next_at)
        )
        await s.commit()
    if status == "failed":
        _audit(subject_type, subject_id, "notice_failed", notice_id=str(notice_id), error=error[:200])
    return status
```

- [ ] **Step 6: Implement `src/notify/telegram.py`**

```python
"""
Telegram renderer for outbox rows (P0). The ONLY module that knows Telegram's
limits (C23): 4096 chars/message, 64 bytes/callback_data, ≤ 8 buttons. Text is
sent WITHOUT parse_mode — the legacy Markdown crash class
(TROUBLESHOOTING.md "Can't parse entities") cannot occur here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

TELEGRAM_TEXT_LIMIT = 4096
CALLBACK_LIMIT_BYTES = 64
MAX_BUTTONS = 8
_TRAILER = "\n… (truncated)"

_HEADERS: dict[str, str] = {
    "job_completed": "✅ done",
    "job_failed": "❌ failed",
    "task_approval_request": "✋ task needs your approval",
    "task_question": "❓ task needs your input — reply to this message",
    "task_choices": "🔀 task — pick one",
    "task_plan": "📋 plan (executing now)",
    "task_plan_approval": "📋 plan — needs your approval",
    "task_completed": "✅ task completed and verified",
    "task_progress": "🔄 progress",
    "task_failed": "❌ task failed",
    "task_review_flagged": "⚠️ post-review flagged",
    "ops_alert": "🚨 ops",
    "credential_canary": "🔑 credential canary",
    "quota_paused": "⏸ queue paused",
    "quota_resumed": "▶️ queue resumed",
}


@dataclass(frozen=True)
class TelegramMessage:
    chat_id: int
    text: str
    buttons: tuple[tuple[tuple[str, str], ...], ...] = ()
    reply_to_message_id: int | None = None


def validate_callback(data: str) -> str:
    if len(data.encode("utf-8")) > CALLBACK_LIMIT_BYTES:
        raise ValueError(f"callback_data exceeds {CALLBACK_LIMIT_BYTES} bytes: {data[:32]!r}…")
    return data


def fit_text(head: str, body: str, *, footer: str = "", limit: int = TELEGRAM_TEXT_LIMIT) -> str:
    """head + newline + body + footer, body clipped so the whole fits `limit`."""
    frame = len(head) + 1 + len(footer)
    room = limit - frame
    body = body or ""
    if len(body) <= room:
        return f"{head}\n{body}{footer}"
    clipped = body[: max(room - len(_TRAILER), 0)] + _TRAILER
    return f"{head}\n{clipped}{footer}"


def build_buttons(actions: dict[str, Any] | None) -> tuple[tuple[tuple[str, str], ...], ...]:
    rows_in = (actions or {}).get("buttons") or []
    rows_out: list[tuple[tuple[str, str], ...]] = []
    total = 0
    for row in rows_in:
        cells: list[tuple[str, str]] = []
        for label, cb in row:
            if total >= MAX_BUTTONS:
                break
            cells.append((str(label)[:40], validate_callback(str(cb))))
            total += 1
        if cells:
            rows_out.append(tuple(cells))
        if total >= MAX_BUTTONS:
            break
    return tuple(rows_out)


def _chat_id(target: str | None, owner_chat_id: int) -> int:
    try:
        return int(target) if target else owner_chat_id
    except (TypeError, ValueError):
        return owner_chat_id


def render_telegram(notice_like: Any, *, owner_chat_id: int) -> TelegramMessage:
    """Pure. Accepts a Notice or a Notification row (same attribute names)."""
    kind = getattr(notice_like, "notice_kind", "") or ""
    actions = getattr(notice_like, "actions", None) or {}
    head = _HEADERS.get(kind, kind or "notice")
    footer = ""
    if kind.startswith("job_") and actions.get("job8"):
        footer = f"\n/status {actions['job8']}"
    thread = getattr(notice_like, "thread", None)
    reply_to = int(thread) if isinstance(thread, str) and thread.isdigit() else None
    return TelegramMessage(
        chat_id=_chat_id(getattr(notice_like, "target", None), owner_chat_id),
        text=fit_text(head, getattr(notice_like, "body", "") or "", footer=footer),
        buttons=build_buttons(actions),
        reply_to_message_id=reply_to,
    )


def keyboard_markup(buttons: tuple[tuple[tuple[str, str], ...], ...]):
    """python-telegram-bot markup or None (lazy import keeps the module pure)."""
    if not buttons:
        return None
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(label, callback_data=cb) for label, cb in row] for row in buttons]
    )


async def send_via_bot(bot: Any, msg: TelegramMessage) -> int:
    """Deliver through a running python-telegram-bot Bot; returns message_id.
    A reply target that no longer exists is retried once without reply_to."""
    kwargs: dict[str, Any] = dict(chat_id=msg.chat_id, text=msg.text,
                                  reply_markup=keyboard_markup(msg.buttons))
    if msg.reply_to_message_id:
        kwargs["reply_to_message_id"] = msg.reply_to_message_id
    try:
        sent = await bot.send_message(**kwargs)
    except Exception as exc:  # noqa: BLE001
        if msg.reply_to_message_id and "repl" in str(exc).lower():
            kwargs.pop("reply_to_message_id", None)
            sent = await bot.send_message(**kwargs)
        else:
            raise
    return int(sent.message_id)


async def send_via_http(token: str, msg: TelegramMessage) -> int:
    """Deliver straight to api.telegram.org (CLI / launchd alerters, where the
    bot process may be the thing that is down). Returns message_id."""
    import json

    import httpx

    payload: dict[str, Any] = {"chat_id": msg.chat_id, "text": msg.text}
    if msg.reply_to_message_id:
        payload["reply_to_message_id"] = msg.reply_to_message_id
    if msg.buttons:
        payload["reply_markup"] = json.dumps({"inline_keyboard": [
            [{"text": label, "callback_data": cb} for label, cb in row] for row in msg.buttons]})
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(f"https://api.telegram.org/bot{token}/sendMessage", data=payload)
        r.raise_for_status()
        return int(r.json()["result"]["message_id"])
```

- [ ] **Step 7: Implement `src/notify/__init__.py` and `src/notify/__main__.py`**

`src/notify/__init__.py`:

```python
"""Notification outbox (P0). outbox.py = rows + policy, telegram.py = renderer,
__main__.py = `python -m src.notify send|drain`. See .context/modules/notify/CONTEXT.md."""
```

`src/notify/__main__.py`:

```python
"""
CLI for out-of-band alerters (launchd scripts, credential canary) and ops.

  python -m src.notify send --kind ops_alert --severity warn --text "runner down" [--subject job:<uuid>] [--target <chat>]
  python -m src.notify drain [--limit 20]

`send` tries a DIRECT Telegram HTTP send first (the bot may be the thing that
is down), then records the row. Exit 0 when delivered OR recorded; 1 when
neither — so bash callers can fall back to their legacy curl.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from src.config import settings
from src.notify.outbox import (
    build_ops_notice,
    claim_notice,
    mark_failed,
    mark_sent,
    pending_notices,
    record_notice,
)
from src.notify.telegram import render_telegram, send_via_http


def _owner_chat_id() -> int | None:
    ids = settings.allowed_chat_ids
    return ids[0] if ids else None


async def _send(args: argparse.Namespace) -> int:
    notice = build_ops_notice(kind=args.kind, severity=args.severity, text=args.text,
                              subject=args.subject, target=args.target)
    owner = _owner_chat_id()
    ref: str | None = None
    err: str | None = None
    if owner is not None and settings.telegram_bot_token:
        try:
            ref = str(await send_via_http(settings.telegram_bot_token,
                                          render_telegram(notice, owner_chat_id=owner)))
        except Exception as exc:  # noqa: BLE001
            err = str(exc)[:300]
    else:
        err = "telegram token / chat id not configured"
    row_id = None
    try:
        row_id = await record_notice(notice, status="sent" if ref else "pending",
                                     external_ref=ref, last_error=err)
    except Exception as exc:  # noqa: BLE001
        print(f"notify: row not recorded: {exc}", file=sys.stderr)
    print(f"notice {row_id or '-'} {'sent' if ref else 'pending'}{(' (' + err + ')') if err else ''}")
    return 0 if (ref or row_id) else 1


async def _drain(args: argparse.Namespace) -> int:
    owner = _owner_chat_id()
    if owner is None or not settings.telegram_bot_token:
        print("notify: telegram not configured", file=sys.stderr)
        return 1
    rows = await pending_notices(limit=args.limit)
    sent = failed = skipped = 0
    for row in rows:
        attempts_before = row.attempts
        if not await claim_notice(row.id):
            skipped += 1          # the bot's listener took it between select and claim
            continue
        try:
            ref = await send_via_http(settings.telegram_bot_token,
                                      render_telegram(row, owner_chat_id=owner))
            await mark_sent(row.id, str(ref), subject_type=row.subject_type, subject_id=row.subject_id)
            sent += 1
        except Exception as exc:  # noqa: BLE001
            await mark_failed(row.id, str(exc), attempts_so_far=attempts_before,
                              subject_type=row.subject_type, subject_id=row.subject_id)
            failed += 1
    print(f"drained sent={sent} failed={failed} skipped={skipped} pending_before={len(rows)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m src.notify")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("send")
    s.add_argument("--kind", required=True)
    s.add_argument("--severity", default="info", choices=("info", "warn", "critical"))
    s.add_argument("--text", required=True)
    s.add_argument("--subject", default=None, help="job:<uuid> | task:<uuid> | schedule:<name>")
    s.add_argument("--target", default=None, help="chat id; default owner")
    d = sub.add_parser("drain")
    d.add_argument("--limit", type=int, default=20)
    args = p.parse_args(argv)
    return asyncio.run(_send(args) if args.cmd == "send" else _drain(args))


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 8: Run the tests to verify they pass**

Run: `pipenv run pytest tests/test_notify_outbox.py tests/test_notify_telegram.py -v`
Expected: 41 PASS, 0 failed (outbox 29: TestVocabulary 4, TestShouldNotify 9, TestBuildJobNotice 6, TestBuildTaskNotice 6, TestOpsNotice 2, TestRetry 2; renderer 12: TestLimits 6, TestRender 6).

CLI smoke (sends one real DM to the owner and records a row — `record_notice` is not gated by the switch, so this works with `notify_outbox=False`): `pipenv run python -m src.notify send --kind ops_alert --severity info --text "P0 outbox CLI smoke — ignore"`
Expected: prints `notice <uuid> sent`; `psql assistant -tAc "SELECT notice_kind,status,attempts,external_ref FROM notifications ORDER BY created_at DESC LIMIT 1"` → `ops_alert|sent|1|<message id>`.

- [ ] **Step 9: Module context docs, skills stubs, CHANGELOGs, commit**

Create `.context/modules/notify/CONTEXT.md`:

```markdown
# Notify module

**Paths:** `src/notify/outbox.py`, `src/notify/telegram.py`, `src/notify/__main__.py`

## Purpose

Durable, channel-agnostic notifications (P0 of the multi-model platform,
spec §4.5). Producers INSERT a `notifications` row and nudge `notify:outbox`;
the Telegram bot's outbox listener delivers (pub/sub nudge + 30 s poll) and
stamps delivery status, so a bot restart loses nothing and alert history is
queryable. Kill switch: `NOTIFY_OUTBOX=0` (legacy `tasks:notify` + `_job_to_chat`).

## Public interface

- `outbox.Notice` (frozen dataclass), `outbox.NOTICE_KINDS`, `outbox.TASK_NOTIFY_TYPES`, `outbox.MAX_ATTEMPTS`
- pure: `build_job_notice(...) -> Notice | None`, `build_task_notice(...) -> Notice`, `build_ops_notice(...) -> Notice`, `should_notify_job(status=, kind=, task_id=, origin_channel=)` (spec §4.2 card eligibility: completions DM only for `COMPLETION_DM_CHANNELS = telegram/web/pwa/cli`; failures always; `_` kinds never; children inherit the parent's channel; `schedules.notify` is a P1/008 column so every P0 schedule row is `failures`), `notice_kind_for_task_type(t)`, `retry_delay_seconds(n)`, `transition_after_failure(n, now)`
- async: `enqueue_notice(notice) -> id | None` (switch-gated producer path), `record_notice(notice, status=...)` (not switch-gated — CLI alert history), `pending_notices(limit)`, `claim_notice(id) -> bool` (exactly one drainer sends a row; `sending` status + 5-min lease in `next_attempt_at`), `release_stuck_sending()`, `mark_sent(id, external_ref)`, `mark_failed(id, error, attempts_so_far) -> status`
- `telegram.render_telegram(notice_or_row, owner_chat_id=) -> TelegramMessage` (4096 / 64-byte / 8-button limits live here and only here; plain text, no parse_mode), `keyboard_markup`, `send_via_bot(bot, msg)`, `send_via_http(token, msg)`
- CLI: `python -m src.notify send --kind … --severity … --text …` (direct HTTP first, then record; exit 1 only when neither worked), `python -m src.notify drain` (claims before sending, so it is safe beside the running bot)
- Audit kinds on job subjects: `notice_queued`, `notice_sent`, `notice_failed` (`record_notice` emits the one matching the status it writes). **P0 deviation from spec §2.7**: these are appended to the job's JSONL only — not mirrored to `jobs:stream:<id>`; P1 adds the mirror with `jobs:reviewed`.
- Kill switch: `settings.notify_outbox` (default False until the bot listener ships, then True). The runner always publishes the legacy channels; the switch selects which bot renderer sends.

## Dependencies

config, db, models, audit_log; `telegram` and `httpx` imported lazily inside functions.

## Testing

`tests/test_notify_outbox.py`, `tests/test_notify_telegram.py` (pure). Delivery paths are smoke-tested live (`python -m src.notify send`).
```

Create `.context/modules/notify/CHANGELOG.md`:

```markdown
# Changelog: notify

<!-- Newest entries at top. Every session that modifies this module appends here. -->

## 2026-09-25 — module created: outbox rows, Telegram renderer, send/drain CLI

- **Agent task**: multi-model P0, Task 5 (plan `docs/superpowers/plans/2026-09-25-multi-model-platform-p0.md`).
- **Files changed**: `src/notify/{__init__,outbox,telegram,__main__}.py` (new), `src/config.py` (`notify_outbox`), `src/db.py` (`CHANNEL_NOTIFY_OUTBOX`), tests.
- **Why**: spec §0 bullet 2 / §4.5 — one outbox with delivery history replaces the in-process `_job_to_chat` dict and the unschema'd `tasks:notify` vocabulary; out-of-band alerters get a shared sender.
- **Side effects**: none until Task 6/7 wire producers and the bot listener.
- **Gotchas discovered**: the renderer sends plain text (no parse_mode) on purpose — every legacy Markdown-entity crash came from interpolated `_`/`*` in skill names.
```

Then: `bash scripts/seed-module-skills.sh` (creates `.context/modules/notify/skills/{GOTCHAS,PATTERNS,DEBUG}.md`), and prepend to `.context/modules/db/CHANGELOG.md`:

```markdown
## 2026-09-25 — settings.notify_outbox + CHANNEL_NOTIFY_OUTBOX

- `src/config.py`: `notify_outbox: bool = False` (env `NOTIFY_OUTBOX`, P0 kill switch; ships off, flipped to True in the bot-listener commit). `src/db.py`: `CHANNEL_NOTIFY_OUTBOX = "notify:outbox"`.
```

`.context/SYSTEM.md` module graph — insert after the `src/gateway/telegram_bot.py` row (three rows, four columns; `telegram.py` imports nothing from `src`, hence `—`). **No literal `|` anywhere in a cell**, not even backslash-escaped: `src/context/module_graph.py:47` splits each row on the raw `|` character, so `` `send\|drain` `` would give the row two extra cells and read Depends-on out of the wrong one — verified: `parse_module_graph` then returns `notify.__main__ -> ['drain` for launchd alerters and ops']` and `check_module_graph_imports` emits three spurious warnings, `scripts/lint_docs.py` stops printing `All clean!` and `tests/test_doc_lint.py::test_module_graph_imports` fails for Tasks 5-8, 12, 15-17 and the whole-suite gate in Task 14. Write `` `python -m src.notify send` / `drain` `` (or `&#124;`) instead. Safe now: `check_module_graph_imports` ignores import targets that have no row, and these rows are what Task 6's `main.py` import and Task 7's bot import will point at:

```markdown
| `src/notify/outbox.py` | Notifications outbox: rows, policy (which job/task events DM), claim/lease, retry math | config, db, models, audit_log | runner.main, gateway.telegram_bot, notify.__main__ |
| `src/notify/telegram.py` | Telegram renderer (4096/64-byte/8-button limits), bot + HTTP senders | — | gateway.telegram_bot, notify.__main__ |
| `src/notify/__main__.py` | `python -m src.notify send` / `drain` for launchd alerters and ops | config, notify.outbox, notify.telegram | scripts/credential-canary.sh, healthcheck-all.sh, schedule-monitor.sh |
```

Run: `pipenv run pytest tests/test_doc_lint.py -q && pipenv run python scripts/lint_docs.py` → Expected: PASS and `All clean!` (module skills dirs seeded; graph rows parse).

```bash
git add src/notify src/config.py src/db.py tests/test_notify_outbox.py tests/test_notify_telegram.py .context/modules/notify .context/modules/db/CHANGELOG.md .context/SYSTEM.md
git commit -m "feat(notify): outbox rows + Telegram renderer (4096/64B/8-button limits) + python -m src.notify send|drain; NOTIFY_OUTBOX kill switch (ships off)"
```

---

### Task 6: Runner writes the outbox — job terminals and every task lifecycle card


**Execution position:** 12 of 21 — previous: Task 5, next: Task 21 (see Global Constraints "Execution order").

**Files:**
- Modify: `src/runner/main.py` — imports; `_finish_job` (after `publish_done`, originally `:1300`); `_notify_task` (originally `:885-888`); the five direct `redis.publish("tasks:notify", …)` sites (originally `:732-739` — the local `from src.db import redis as _redis` at 732 plus the publish at 733-739, both deleted together — `:1111-1119`, `:1128-1135`, `:1215-1222`, `:1259-1266`)
- Modify: `.context/modules/runner/CHANGELOG.md`, `.context/SYSTEM.md` (`main.py` Depends-on gains `notify.outbox` — its row exists since Task 5, so the import is lint-checked)
- Test: `tests/test_notify_runner_hooks.py`

**Interfaces:**
- Consumes: `outbox.build_job_notice`, `build_task_notice`, `enqueue_notice` (Task 5); `Job.origin_*`, `Task.origin_*` (Tasks 1, 4).
- Produces:
  - `main.job_notice_kwargs(job) -> dict` (pure: the `build_job_notice` kwargs from a Job row; it takes the **effective** origin channel, see next line).
  - `main.effective_origin_channel(own: str | None, parent: str | None) -> str | None` (pure) — spec §4.2: "dispatch-MCP / escalation / self-diagnose children **inherit the parent's eligibility**". A child's own `created_by` (`dispatch-mcp`, `event-trigger*`, `escalation:<job8>`) derives `origin_channel="system"`, which would silence the completion DM of a child the owner launched from Telegram and — worse — is the wrong answer in both directions. Rule: `return parent if (own in (None, "system")) and parent else own`. The parent is found by `jobs.parent_job_id`, which **both** child paths already set (`mcp_dispatch.py:120/134` and `main.py:770-773` `update(Job)…values(parent_job_id=job.id…)`), so no `created_by` parsing is needed.
  - `async main._enqueue_job_notice(job_id: uuid.UUID, status: str) -> None` — loads the job, and when `job.parent_job_id` is set also loads the parent's `origin_channel` (one extra indexed read on a terminal path, only for children) and passes `effective_origin_channel(...)` into `job_notice_kwargs`.
  - `async main._task_target(task_id) -> tuple[str | None, str | None]` (origin_ref/chat_id, origin_thread/thread_message_id).
  - `main._notify_task(task_id, notify_type, **fields)` is now the single chokepoint for all nine task card types and **dual-writes** (spec §9/§10): it ALWAYS publishes `tasks:notify` byte-identically to today, and when `settings.notify_outbox` is on it ALSO writes an outbox row. The switch never changes what the runner publishes — only the bot (Task 7) decides which renderer sends.
  - `_finish_job` keeps `publish_done` unconditional and, when the switch is on, adds the `job_completed`/`job_failed` row.
  - Behaviour: every `completed`/`failed` job terminal that `should_notify_job` accepts becomes a `job_completed`/`job_failed` row within the same `_finish_job` call (a scheduled failure is therefore in the outbox < 1 s after the terminal event; Task 7's listener delivers on the nudge, else within 30 s). With the switch still `False` at this commit nothing changes on the wire: the legacy bot renderers keep delivering — this commit is deployable alone.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_notify_runner_hooks.py`:

```python
"""
Runner → outbox wiring (P0). DB and Redis are monkeypatched; the policy
itself lives in src/notify/outbox.py (tests/test_notify_outbox.py).

Run: pipenv run pytest tests/test_notify_runner_hooks.py -v
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from src.models import JobStatus
from src.runner import main as main_mod

TASK = uuid.uuid4()
NOW = datetime(2026, 9, 25, 3, 0, tzinfo=timezone.utc)


def _job(**over):
    base = dict(id=uuid.uuid4(), kind="atlas-daily-brief", resolved_skill="atlas-daily-brief",
                result=None, error_message="API terminal error: 529", terminal_reason="api_error",
                origin_channel="scheduler", origin_ref="atlas-daily-brief", origin_thread=None,
                created_by="scheduler", task_id=None, model_served="claude-opus-5",
                num_turns=3, started_at=NOW, completed_at=NOW + timedelta(seconds=123))
    base.update(over)
    return SimpleNamespace(**base)


class TestEligibilityInheritance:
    def test_child_inherits_the_parent_channel(self):
        # spec §4.2: children inherit the parent's eligibility.
        f = main_mod.effective_origin_channel
        assert f("system", "telegram") == "telegram"      # Telegram launch → child reports
        assert f("system", "scheduler") == "scheduler"    # schedule row → child stays quiet
        assert f(None, "telegram") == "telegram"
        assert f("telegram", "scheduler") == "telegram"   # an own human channel always wins
        assert f("system", None) == "system"              # no parent: unchanged
        assert f(None, None) is None


class TestJobNoticeKwargs:
    def test_scheduled_failure_kwargs(self):
        kw = main_mod.job_notice_kwargs(_job())
        assert kw["origin_channel"] == "scheduler" and kw["task_id"] is None
        assert kw["summary"] is None and kw["duration_seconds"] == 123
        assert kw["error_message"].startswith("API terminal")

    def test_summary_pulled_from_result(self):
        kw = main_mod.job_notice_kwargs(_job(result={"summary": "pong", "usage": {}}))
        assert kw["summary"] == "pong"

    def test_missing_timestamps_give_no_duration(self):
        assert main_mod.job_notice_kwargs(_job(completed_at=None))["duration_seconds"] is None


class TestNotifyTask:
    # Every test here patches main_mod.redis: the legacy publish is
    # unconditional now (dual-write), so no path skips Redis.
    async def test_outbox_on_enqueues_task_notice(self, monkeypatch, fake_redis):
        recorded = []

        async def fake_target(task_id):
            return ("123", "777")

        async def fake_enqueue(notice):
            recorded.append(notice)
            return uuid.uuid4()

        monkeypatch.setattr(main_mod, "redis", fake_redis)
        monkeypatch.setattr(main_mod, "_task_target", fake_target)
        monkeypatch.setattr(main_mod, "enqueue_notice", fake_enqueue)
        monkeypatch.setattr(main_mod.settings, "notify_outbox", True)
        await main_mod._notify_task(TASK, "question", text="which one?")
        assert len(recorded) == 1
        n = recorded[0]
        assert n.notice_kind == "task_question" and n.target == "123" and n.thread == "777"
        assert n.body == "which one?" and n.subject_id == str(TASK)

    async def test_outbox_on_never_raises(self, monkeypatch, fake_redis):
        async def boom(task_id):
            raise RuntimeError("db down")

        monkeypatch.setattr(main_mod, "redis", fake_redis)
        monkeypatch.setattr(main_mod, "_task_target", boom)
        monkeypatch.setattr(main_mod.settings, "notify_outbox", True)
        await main_mod._notify_task(TASK, "progress", text="x")   # must not raise

    @pytest.mark.parametrize("switch", [False, True])
    async def test_legacy_channel_published_in_both_modes(self, monkeypatch, fake_redis, switch):
        # Spec §9/§10 dual-write: the runner's wire format never depends on
        # the switch; only the bot's renderer choice does (Task 7).
        monkeypatch.setattr(main_mod, "redis", fake_redis)   # main binds `redis` at import
        monkeypatch.setattr(main_mod.settings, "notify_outbox", switch)

        async def fake_target(task_id):
            return ("123", "777")

        async def fake_enqueue(notice):
            return uuid.uuid4()

        monkeypatch.setattr(main_mod, "_task_target", fake_target)
        monkeypatch.setattr(main_mod, "enqueue_notice", fake_enqueue)
        pubsub = fake_redis.pubsub()
        await pubsub.subscribe("tasks:notify")
        await main_mod._notify_task(TASK, "progress", text="hi")
        msg = None
        for _ in range(20):
            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.1)
            if msg:
                break
        assert msg is not None, f"legacy publish missing with notify_outbox={switch}"
        data = json.loads(msg["data"])
        assert data == {"task_id": str(TASK), "type": "progress", "text": "hi"}

    async def test_outbox_off_writes_no_row(self, monkeypatch, fake_redis):
        monkeypatch.setattr(main_mod, "redis", fake_redis)
        monkeypatch.setattr(main_mod.settings, "notify_outbox", False)
        calls = []

        async def fake_enqueue(notice):
            calls.append(notice)

        monkeypatch.setattr(main_mod, "enqueue_notice", fake_enqueue)
        await main_mod._notify_task(TASK, "progress", text="hi")
        assert calls == []


class TestFinishJobNotice:
    async def test_finish_job_failed_enqueues_notice_without_task(self, monkeypatch):
        # Review Focus 2: a failing scheduler job (no task_id) must reach the outbox.
        class _Res:
            rowcount = 1

        class _Sess:
            async def execute(self, *a, **k):
                return _Res()

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

        async def fake_done(*a, **k):
            return None

        calls = []

        async def fake_notice(job_id, status):
            calls.append((job_id, status))

        monkeypatch.setattr(main_mod, "session_scope", lambda: _Sess())
        monkeypatch.setattr(main_mod.session_mod, "publish_done", fake_done)
        monkeypatch.setattr(main_mod, "_enqueue_job_notice", fake_notice)
        monkeypatch.setattr(main_mod.settings, "notify_outbox", True)
        jid = uuid.uuid4()
        await main_mod._finish_job(jid, JobStatus.failed, error="boom", terminal_reason="api_error")
        assert calls == [(jid, "failed")]

    async def test_finish_job_cancelled_writes_no_notice(self, monkeypatch):
        class _Res:
            rowcount = 1

        class _Sess:
            async def execute(self, *a, **k):
                return _Res()

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

        async def fake_done(*a, **k):
            return None

        calls = []

        async def fake_notice(job_id, status):
            calls.append(status)

        monkeypatch.setattr(main_mod, "session_scope", lambda: _Sess())
        monkeypatch.setattr(main_mod.session_mod, "publish_done", fake_done)
        monkeypatch.setattr(main_mod, "_enqueue_job_notice", fake_notice)
        monkeypatch.setattr(main_mod.settings, "notify_outbox", True)
        await main_mod._finish_job(uuid.uuid4(), JobStatus.cancelled)
        assert calls == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pipenv run pytest tests/test_notify_runner_hooks.py -v`
Expected: FAIL — `AttributeError: module 'src.runner.main' has no attribute 'job_notice_kwargs'` / `_task_target` / `enqueue_notice`.

- [ ] **Step 3: Implement in `main.py`**

Imports (with the other `src.` imports):

```python
from src.notify.outbox import build_job_notice, build_task_notice, enqueue_notice
```

Add after `awaiting_since_for` (Task 4):

```python
def job_notice_kwargs(job: Any) -> dict[str, Any]:
    """Pure. build_job_notice(**kwargs) from a Job row (or any object with
    the same attributes)."""
    result = job.result if isinstance(job.result, dict) else None
    duration = None
    if job.started_at and job.completed_at:
        duration = max(0.0, (job.completed_at - job.started_at).total_seconds())
    return dict(
        job_id=str(job.id), status=None, kind=job.kind, resolved_skill=job.resolved_skill,
        summary=(result or {}).get("summary") if result else None,
        error_message=job.error_message, terminal_reason=job.terminal_reason,
        origin_channel=job.origin_channel, origin_ref=job.origin_ref,
        origin_thread=job.origin_thread, created_by=job.created_by, task_id=job.task_id,
        model_served=job.model_served, num_turns=job.num_turns, duration_seconds=duration,
    )


async def _enqueue_job_notice(job_id: uuid.UUID, status: str) -> None:
    """Outbox row for a job terminal (DoneCard / FailedCard, spec §4.2)."""
    async with async_session() as s:
        job = await s.get(Job, job_id)
    if job is None:
        return
    kwargs = job_notice_kwargs(job)
    kwargs["status"] = status
    notice = build_job_notice(**kwargs)
    if notice is not None:
        await enqueue_notice(notice)


async def _task_target(task_id) -> tuple[str | None, str | None]:
    """(chat, thread) for a task: origin_* first, legacy chat_id/thread_message_id second."""
    from src.models import Task
    async with async_session() as s:
        task = await s.get(Task, task_id)
    if task is None:
        return None, None
    target = task.origin_ref or (str(task.chat_id) if task.chat_id else None)
    thread = task.origin_thread or (str(task.thread_message_id) if task.thread_message_id else None)
    return target, thread
```

Replace `_notify_task` (originally `main.py:885-888`):

```python
async def _notify_task(task_id, notify_type: str, **fields) -> None:
    """The single chokepoint for task lifecycle cards. DUAL-WRITE (spec
    §9/§10): the legacy tasks:notify publish is unconditional and byte-
    identical to before P0; when the outbox is on a durable row + nudge is
    written AS WELL. Which renderer sends is the bot's decision
    (telegram_bot._task_notifier vs _outbox_listener), so flipping
    NOTIFY_OUTBOX needs a bot restart only."""
    await redis.publish("tasks:notify", json.dumps({
        "task_id": str(task_id), "type": notify_type, **fields,
    }))
    if not settings.notify_outbox:
        return
    try:
        target, thread = await _task_target(task_id)
        notice = build_task_notice(
            task_id=str(task_id), notify_type=notify_type,
            text=str(fields.get("text", "") or ""),
            question=fields.get("question"), choices=fields.get("choices"),
            target=target, thread=thread,
        )
        await enqueue_notice(notice)
    except Exception:
        logger.exception("task notice enqueue failed (non-fatal)",
                         task_id=str(task_id)[:8], notify_type=notify_type)
```

Route the five direct publishes through it (search for `"tasks:notify"` in `main.py` — after this step the only remaining occurrence is inside `_notify_task`):

1. `_maybe_escalate` L3 (originally `:732-739`): delete `from src.db import redis as _redis` and replace the `await _redis.publish("tasks:notify", json.dumps({...}))` with

```python
            await _notify_task(
                job.task_id, "failed",
                text=(f"Task failed after 3 escalation attempts. "
                      f"Last error: {(job.error_message or 'unknown')[:300]}. "
                      f"Reply to retry or /clear to abandon."),
            )
```

2. `_update_task_after_job` choices branch (originally `:1111-1119`): replace the `await redis.publish("tasks:notify", json.dumps({... "type": "choices" ...}))` with

```python
        await _notify_task(job.task_id, "choices",
                           question=choices_event.get("question", "Pick one:"),
                           choices=choices_event.get("options", []))
```

3. question branch (originally `:1128-1135`): replace with `await _notify_task(job.task_id, "question", text=question)`.

4. sentinel branch (originally `:1215-1222`): replace with `await _notify_task(job.task_id, "approval_request", text=summary)`.

5. auto-continue branch (originally `:1259-1266`): replace with

```python
            await _notify_task(job.task_id, "progress",
                               text=f"Phase complete. Auto-continuing... (job {str(child.id)[:8]})")
```

`_finish_job`: after `await session_mod.publish_done(str(job_id), status.value, payload=payload)` add

```python
    # P0 outbox: DoneCard / FailedCard for every eligible terminal (task-less
    # completions, every non-internal failure — scheduled ones included).
    if settings.notify_outbox and status in (JobStatus.completed, JobStatus.failed):
        try:
            await _enqueue_job_notice(job_id, status.value)
        except Exception:
            logger.exception("job notice enqueue failed (non-fatal)", job_id=str(job_id)[:8])
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pipenv run pytest tests/test_notify_runner_hooks.py tests/test_plans.py tests/test_timeout_escalation.py tests/test_events.py -v && grep -c '"tasks:notify"' src/runner/main.py`
Expected: all PASS; grep prints `1`.

Live check (runner restarted with `launchctl kickstart -k gui/$(id -u)/com.assistant.runner`; the switch is still `False` at this commit, so NO row is written yet — what this proves is the spec's P0 exit criterion "with `NOTIFY_OUTBOX=0` a Telegram-launched job still DMs via the legacy path"): from Telegram send `/task reply with the word pong` → the legacy task card (`✅ task completed and verified`, via `_task_notifier`) arrives as before; then `psql assistant -tAc "SELECT count(*) FROM notifications WHERE notice_kind LIKE 'job_%' OR notice_kind LIKE 'task_%'"` → `0` (the CLI smoke row from Task 5 is `ops_alert`). The row-writing path is exercised live in Task 7 Step 5 once the switch flips.

- [ ] **Step 5: SYSTEM.md Depends-on, CHANGELOG, commit**

`main.py` now imports `src.notify.outbox`, whose row exists since Task 5, so `check_module_graph_imports` warns until the `src/runner/main.py` row's Depends-on cell names it. In `.context/SYSTEM.md` append `, notify.outbox` to that cell (it already ends `…, audit_log, runner.result_capture` after Task 3).

Run: `pipenv run pytest tests/test_doc_lint.py -q && pipenv run python scripts/lint_docs.py` → Expected: PASS and `All clean!`.

Prepend to `.context/modules/runner/CHANGELOG.md`:

```markdown
## 2026-09-25 — runner writes the notifications outbox (job terminals + every task card)

- **Files changed**: `src/runner/main.py` — `_finish_job` enqueues `job_completed`/`job_failed` notices after the unconditional `publish_done` (`job_notice_kwargs`, `_enqueue_job_notice`); `_notify_task` is now the single chokepoint and DUAL-WRITES (always the legacy `tasks:notify` publish, plus `build_task_notice` + `enqueue_notice` with `_task_target` when `settings.notify_outbox`); the five direct `redis.publish("tasks:notify")` sites (escalation L3, choices, question, sentinel approval, auto-continue progress) route through it. `.context/SYSTEM.md` `main.py` Depends-on += `notify.outbox`.
- **Why**: spec §9 P0 exit "a scheduled failure DMs within 60 s" — every failure DM path used to require `task_id`. Spec §9/§10: P0 dual-writes so the switch is renderer-side (bot-only restart).
- **Side effects**: none on the wire — the runner publishes exactly what it did before P0 in both switch positions. With the switch on (Task 7 flips it) rows are ALSO written; which renderer sends is decided in the bot. `NOTIFY_OUTBOX=0` never changes runner behaviour beyond "no row".
- **Gotchas discovered**: `_finish_job(completed)` runs before post-steps, so the DoneCard cannot show review verdicts yet (P2 adds `jobs:reviewed`).
```

```bash
git add src/runner/main.py tests/test_notify_runner_hooks.py .context/modules/runner/CHANGELOG.md .context/SYSTEM.md
git commit -m "feat(runner): job terminals and task lifecycle cards dual-write the notifications outbox (NOTIFY_OUTBOX selects the bot renderer)"
```

---

### Task 21: Interim scheduler `provisioning_gap` pre-check — a schedule whose manifest needs a key the project's `.env` lacks defers with a DM instead of burning a session

**Execution position:** 13 of 21 — previous: Task 6, next: Task 7 (see Global Constraints "Execution order"). It needs Task 6's outbox producer for the DM.

- [ ] **Step 0: Prerequisite check** — `pipenv run python -c "from src.notify.outbox import build_ops_notice; print('ok')"` must print `ok`. If it fails: **execute Tasks 5 and 6 first.**

**Why this is P0.** Spec §9's P0 scope cell: "**trading blockers**: `TRADIER_SANDBOX_TOKEN` + `FINNHUB_TOKEN` (§12a row 6b) and the interim scheduler `provisioning_gap` pre-check (§8.3)". Spec §8.3 spells it out: "an **interim `provisioning_gap` pre-check that needs no `ScriptExecutor`** — the scheduler skips an atlas row whose manifest `env_required` key is absent from `projects/atlas/.env`, emitting `schedule_deferred{reason=provisioning_gap}` and a `notify=failures` DM (≈ −20 M/month, the §2.8/§13 delta, booked against P0)". Round-2 #43 put it in P0 precisely because the `ScriptExecutor` version cannot land before P3 while §2.8 and §13 already book the saving. Today `37/37 provisioning_gap runs report success` (spec §8.2 table) — a schedule with a missing key runs a full session, produces nothing usable, and says "completed".

**Files:**
- Modify: `src/registry/manifest.py` — `Manifest` gains `env_required: list[str]`. It is currently **ignored** by the loader (`:49`, `:247`: "web_strategy, env_required, services, … are ignored here"), so the field has to be read before anything can pre-check on it. Not a protected path; the loader keeps failing **open** on a missing/invalid manifest exactly as it does today.
- Modify: `src/runner/main.py` — `provisioning_gap()` (pure) + the call in `_tick_schedules` (`:1327-1362`) before `s.add(job)`
- Modify: `.context/modules/runner/CHANGELOG.md`, `.context/modules/registry/CHANGELOG.md`, `.context/modules/runner/CONTEXT.md`, `.context/modules/registry/CONTEXT.md` (manifest public interface)
- Test: `tests/test_provisioning_gap.py` (new)
- **Not modified**: `projects/atlas/manifest.yml`. Atlas is its own GitHub-canonical repo and spec §8.3 is explicit that atlas patches are "born in the atlas dev clone, dispositioned through LOOP.md §7, executed by the `atlas-build` worker or an owner-dispatched atlas PR, **never INV-4 server patches**". Declaring `TRADIER_SANDBOX_TOKEN`/`FINNHUB_TOKEN` in atlas's `env_required` is therefore an **atlas-front-door item**, recorded in Owner actions. Until it lands, the pre-check simply finds nothing to defer — fail-open, today's behaviour.

**Interfaces:**
- Consumes: `registry.manifest.load`/`load_all` (Task 21's new field), `notify.outbox.build_ops_notice` + `enqueue_notice` (Tasks 5, 6), `audit_log.append`.
- Produces:
  - `manifest.Manifest.env_required: list[str]` (default `[]`; non-string entries coerced to `str`, like `env_files` at `:153`).
  - `main.PROVISIONING_EXEMPT: frozenset[str]` — names that must **never** be required in a project `.env` because this server refuses them everywhere: the whole `claude_env` refusal set (`ANTHROPIC_*`, `CLAUDE_CODE_OAUTH_TOKEN`, `GEMINI_*`, …). **This is not decoration.** Verified on prod: `projects/atlas/manifest.yml:18-20` already declares `env_required: [DATABASE_URL, ANTHROPIC_API_KEY]`, and `ANTHROPIC_API_KEY` is correctly **absent** from `projects/atlas/.env` (INV-3). Without the exemption this pre-check would defer **every atlas schedule row on its first tick** — a self-inflicted fleet outage dressed as a safety feature.
  - `main.env_keys_present(env_path: Path) -> set[str]` (pure-ish: one file read) — the `NAME=` keys in a `.env`, ignoring blanks, `#` comments and `export ` prefixes. Values are never read, never logged.
  - `main.provisioning_gap(env_required: list[str], present: set[str], *, exempt: frozenset[str] = PROVISIONING_EXEMPT) -> list[str]` (pure) — sorted required names that are absent and not exempt.
  - `_tick_schedules`: for a due row with a `project_id`, resolve the project's manifest and `.env`; on a non-empty gap it **does not** `s.add(job)` and **does not** RPUSH, still advances `next_run_at` and `last_run_at` (so the row does not thunder on every 30 s tick), appends `schedule_deferred{schedule, reason: "provisioning_gap", missing: [...], project}` to a schedule-scoped audit stream, and enqueues one ops notice through the outbox. New audit kind `schedule_deferred` (Global Constraints C14 list).
  - **Notice throttling**: one DM per schedule per UTC day, keyed in Redis (`schedule:gap_notified:<schedule_id>:<YYYY-MM-DD>`, `SETNX` + 36 h TTL). A row that fires four times a day must not produce four identical DMs; the audit entry is written every time.
  - **Fail-open, always.** No `project_id`, no manifest, an invalid manifest, an empty `env_required`, or a missing/unreadable `.env` → **run the job**, exactly as today. The only thing that defers a row is a manifest that positively declares a key which the `.env` positively lacks. A pre-check that can silence 41 schedules on a file-read error is worse than the waste it prevents.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_provisioning_gap.py`:

```python
"""
Interim scheduler provisioning pre-check (P0; spec §8.3 "Blockers", §9 P0 scope
"the interim scheduler provisioning_gap pre-check", round-2 #43).

A schedule whose manifest declares an env key the project's .env lacks must be
deferred with schedule_deferred{provisioning_gap} + one DM, not run as a full
session that "completes" having produced nothing (spec §8.2: 37/37
provisioning_gap runs report success today).

Pure: tmp_path .env and manifest fixtures. No live atlas read, no DB, no SDK.

Run: pipenv run pytest tests/test_provisioning_gap.py -v
"""

from __future__ import annotations

from src.runner.main import (
    PROVISIONING_EXEMPT,
    env_keys_present,
    provisioning_gap,
)

ENV_TEXT = """\
# comment
DATABASE_URL=postgresql://localhost/atlas

export FRED_API_KEY=abc
EMPTY=
not a line
"""


class TestEnvKeys:
    def test_names_only_comments_and_export_handled(self, tmp_path):
        p = tmp_path / ".env"
        p.write_text(ENV_TEXT)
        assert env_keys_present(p) == {"DATABASE_URL", "FRED_API_KEY", "EMPTY"}

    def test_missing_file_is_an_empty_set(self, tmp_path):
        assert env_keys_present(tmp_path / "nope.env") == set()


class TestGap:
    def test_present_keys_are_not_a_gap(self):
        assert provisioning_gap(["DATABASE_URL"], {"DATABASE_URL"}) == []

    def test_missing_keys_are_reported_sorted(self):
        assert provisioning_gap(["FINNHUB_TOKEN", "TRADIER_SANDBOX_TOKEN"], {"DATABASE_URL"}) \
            == ["FINNHUB_TOKEN", "TRADIER_SANDBOX_TOKEN"]

    def test_the_inv3_name_atlas_already_declares_is_exempt(self):
        # VERIFIED ON PROD: projects/atlas/manifest.yml declares
        # env_required: [DATABASE_URL, ANTHROPIC_API_KEY], and
        # ANTHROPIC_API_KEY is absent from projects/atlas/.env BY DESIGN
        # (INV-3, subscription auth only). Without this exemption the
        # pre-check would defer every atlas row on its first tick.
        assert "ANTHROPIC_API_KEY" in PROVISIONING_EXEMPT
        assert provisioning_gap(["DATABASE_URL", "ANTHROPIC_API_KEY"], {"DATABASE_URL"}) == []

    def test_the_whole_refusal_set_is_exempt(self):
        from src.runner.claude_env import vendor_keys_in
        for name in ("ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN", "GEMINI_API_KEY"):
            assert vendor_keys_in({name: "x"}) == [name]      # the runner refuses it...
            assert provisioning_gap([name], set()) == []      # ...so a project may not require it

    def test_empty_requirements_never_defer(self):
        assert provisioning_gap([], set()) == []
        assert provisioning_gap([], {"X"}) == []


class TestSchedulerIntegration:
    def test_tick_defers_and_notifies_but_does_not_enqueue(self, monkeypatch, tmp_path):
        """The row is skipped, next_run_at still advances, one notice, no RPUSH."""
        ...  # build a fake Schedule + fake manifest/.env via monkeypatched
             # resolvers; assert: redis.rpush not called, s.add not called,
             # sched.next_run_at advanced, audit kind "schedule_deferred" with
             # missing=["FINNHUB_TOKEN"], exactly one enqueue_notice call.

    def test_tick_runs_the_row_when_nothing_is_missing(self, monkeypatch, tmp_path):
        ...  # rpush called once, no schedule_deferred entry

    def test_a_row_with_no_project_runs(self, monkeypatch):
        ...  # project_id=None → fail-open, rpush called

    def test_an_unreadable_manifest_runs_the_row(self, monkeypatch):
        ...  # manifest loader raises → fail-open, rpush called, no notice

    def test_one_dm_per_schedule_per_day(self, monkeypatch, fake_redis):
        ...  # two deferrals of the same schedule in one UTC day → two audit
             # entries, ONE enqueue_notice (SETNX key)
```

Fill the `...` bodies from the fixtures `tests/test_notify_runner_hooks.py` already establishes for monkeypatching `main`'s DB/Redis (same style, `fake_redis` from `tests/conftest.py`).

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pipenv run pytest tests/test_provisioning_gap.py -v`
Expected: collection error `ImportError: cannot import name 'PROVISIONING_EXEMPT' from 'src.runner.main'`.

- [ ] **Step 3: Read `env_required` in the manifest loader**

`src/registry/manifest.py` — add the field to `Manifest` beside the others and populate it in the loader the way `Delivery.env_files` is populated at `:153`:

```python
    # Owner-provisioned environment keys the project needs to do real work.
    # Read since 2026-09-25 (spec §8.3): the scheduler pre-checks them against
    # projects/<slug>/.env and DEFERS a due row rather than running a session
    # that cannot succeed. Ignored before that date, so a project that lists a
    # name it never actually needed will now defer — which is the point, but it
    # means additions are reviewed. Never a value, only a name.
    env_required: list[str] = field(default_factory=list)
```

```python
            env_required=[str(e) for e in (data.get("env_required", []) or [])],
```

The loader's fail-open contract is unchanged (`:20`: "a project with no/invalid manifest … falls back to legacy behavior"), and no validation is added: a bad `env_required` entry must not make a manifest unloadable, because that would take the project's deploy path down with it.

- [ ] **Step 4: Implement the pre-check in `main.py`**

```python
# Names a project may never be required to carry in its own .env, because this
# server refuses them everywhere (INV-3 / spec §2.4). Without this, the
# pre-check below would defer every atlas row forever: atlas's manifest.yml
# declares env_required: [DATABASE_URL, ANTHROPIC_API_KEY] and the second one
# is absent from projects/atlas/.env BY DESIGN.
PROVISIONING_EXEMPT: frozenset[str] = frozenset({"ANTHROPIC_API_KEY"})


def env_keys_present(env_path: Path) -> set[str]:
    """Pure-ish. The NAME= keys declared in a .env. Values are never read."""
    try:
        text = env_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()
    out: set[str] = set()
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name = line.split("=", 1)[0].strip()
        if name.startswith("export "):
            name = name[len("export "):].strip()
        if name:
            out.add(name)
    return out


def provisioning_gap(env_required: list[str], present: set[str], *,
                     exempt: frozenset[str] = PROVISIONING_EXEMPT) -> list[str]:
    """Pure. Required env names the project's .env does not declare.

    Exempt names are skipped: the runner refuses the whole vendor/auth set in
    its own environment (claude_env.vendor_keys_in), so a project cannot be
    'missing' one. Empty result ⇒ run the row.
    """
    from src.runner.claude_env import vendor_keys_in
    return sorted(
        name for name in (env_required or [])
        if name not in present and name not in exempt and not vendor_keys_in({name: ""})
    )
```

In `_tick_schedules`, inside the `for sched in due:` loop **before** `job = Job(...)`:

```python
            # Interim provisioning pre-check (spec §8.3, §9 P0). A row whose
            # project manifest needs a key the project's .env lacks cannot
            # succeed: today it runs a full session and reports "completed"
            # (spec §8.2: 37/37 provisioning_gap runs report success). Defer
            # it instead, DM once a day, and let the clock advance so the row
            # does not thunder. FAIL-OPEN on every unknown — a pre-check that
            # can silence 41 schedules on a file-read error is worse than the
            # waste it prevents.
            missing: list[str] = []
            if sched.project_id is not None:
                try:
                    slug = await _project_slug(sched.project_id)     # existing helper or one select
                    mf = load_manifest(settings.projects_dir / slug / "manifest.yml")
                    missing = provisioning_gap(
                        mf.env_required,
                        env_keys_present(settings.projects_dir / slug / ".env"),
                    )
                except Exception:      # noqa: BLE001 — never let this stop a schedule
                    logger.debug("provisioning pre-check skipped for schedule %s",
                                 sched.name, exc_info=True)
                    missing = []
            if missing:
                audit_log.append(f"schedule-{sched.id}", "schedule_deferred",
                                 schedule=sched.name, reason="provisioning_gap",
                                 missing=missing, project=slug)
                sched.last_run_at = now
                sched.next_run_at = croniter(sched.cron_expression, now).get_next(
                    datetime).replace(tzinfo=timezone.utc)
                if await _claim_gap_notice(sched.id, now):      # one DM per row per UTC day
                    await enqueue_notice(build_ops_notice(
                        kind="schedule_deferred", severity="warn",
                        text=(f"⏸ {sched.name} deferred — {slug}/.env is missing "
                              f"{', '.join(missing)}. The schedule will keep deferring "
                              f"until the key is provisioned (spec §12a row 6b)."),
                        subject=f"schedule:{sched.id}"))
                logger.warning("schedule deferred: provisioning gap",
                               schedule=sched.name, missing=missing)
                continue
```

`_claim_gap_notice(schedule_id, now)` is three lines over Redis: `await redis.set(f"schedule:gap_notified:{schedule_id}:{now:%Y-%m-%d}", "1", nx=True, ex=129600)`, returning truthy only for the first caller that day.

Add `schedule_deferred` to the `notify.outbox` `NOTICE_KINDS` tuple (Task 5) so the renderer's `test_every_notice_kind_renders` covers it.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pipenv run pytest tests/test_provisioning_gap.py tests/test_notify_outbox.py tests/test_notify_runner_hooks.py -v`
Expected: all PASS.

**Sanity check against the live tree, read-only** (do this even in a worktree — it is a `cat`, and it is the check that would have caught the exemption trap):

```bash
grep -A4 '^env_required:' "$SERVER_ROOT/projects/atlas/manifest.yml"
cut -d= -f1 "$SERVER_ROOT/projects/atlas/.env" | grep -v '^#' | sort
```

Today that prints `env_required: [DATABASE_URL, ANTHROPIC_API_KEY]` against an `.env` that has `DATABASE_URL` but (correctly) no `ANTHROPIC_API_KEY`, and no `TRADIER_SANDBOX_TOKEN`/`FINNHUB_TOKEN` in either. So **at this commit the pre-check defers nothing** — it goes live for the trading rows only when the atlas-front-door change adds those two names to `env_required` (Owner actions), and it must never defer on `ANTHROPIC_API_KEY`.

- [ ] **Step 6: Docs, CHANGELOGs, commit**

- `.context/modules/registry/CONTEXT.md` — public interface: `Manifest.env_required: list[str]` is now **read** (it was ignored before 2026-09-25) and consumed by the scheduler pre-check; adding a name to a project's `env_required` can defer that project's schedules.
- `.context/modules/runner/CONTEXT.md` — public interface: `provisioning_gap`, `env_keys_present`, `PROVISIONING_EXEMPT`, the new audit kind `schedule_deferred`, and the fail-open contract.
- `.context/SYSTEM.md` — `src/runner/main.py`'s Depends-on gains `registry.manifest` if it is not already listed (`check_module_graph_imports` flags the new import otherwise).
- `docs/TROUBLESHOOTING.md` — a symptom entry (Task 14 collects it): "**Symptom: a schedule stops running and DMs `⏸ … deferred — <project>/.env is missing <KEY>`**. Cause: the project manifest's `env_required` names a key the project's `.env` does not declare (spec §8.3 pre-check). Fix: provision the key (§12a row 6b for the trading tokens) or remove it from `env_required` in the project repo. Diagnostic: `grep schedule_deferred volumes/audit_log/schedule-*.jsonl | tail`."

Run: `pipenv run pytest tests/test_doc_lint.py -q && pipenv run python scripts/lint_docs.py` → Expected: PASS and `All clean!`.

Prepend to `.context/modules/runner/CHANGELOG.md`:

```markdown
## 2026-09-25 — scheduler defers a row whose project .env lacks a manifest-required key (schedule_deferred{provisioning_gap})

- **Agent task**: multi-model P0, Task 21 (spec §8.3 "Blockers" P0 bullet, §9 P0 scope, §2.8/§13 −$20–30/month, round-2 #43).
- **Files changed**: `registry/manifest.py` (`Manifest.env_required` is now READ), `runner/main.py` (`PROVISIONING_EXEMPT`, `env_keys_present`, `provisioning_gap`, the `_tick_schedules` pre-check + one-DM-per-day claim), `notify/outbox.py` (`schedule_deferred` notice kind), `tests/test_provisioning_gap.py` (new).
- **Why**: a schedule missing its provisioning runs a full session and reports `completed` having produced nothing — spec §8.2 measured 37/37 such runs "successful". Deferring costs one audit line and one DM instead of a session. The `ScriptExecutor` version of this check is P3; this is the interim that needs nothing new.
- **Side effects**: a due row with a positive gap does not run; `next_run_at` still advances (no thundering) and one DM per row per UTC day. Fail-open on everything else, so the 41 schedules are never silenced by a missing manifest or an unreadable `.env`. New audit kind `schedule_deferred`.
- **Gotchas discovered**: `Manifest.env_required` was **ignored** by the loader before this commit (`manifest.py:49,247`), so reading it is itself the behaviour change — and the live data is a trap: `projects/atlas/manifest.yml` declares `env_required: [DATABASE_URL, ANTHROPIC_API_KEY]` while `ANTHROPIC_API_KEY` is absent from `projects/atlas/.env` **by design** (INV-3). Without `PROVISIONING_EXEMPT` this pre-check would have deferred every atlas schedule on its first tick. Declaring `TRADIER_SANDBOX_TOKEN`/`FINNHUB_TOKEN` in atlas's `env_required` is an **atlas-repo** change (LOOP.md §7 / `atlas-build`), never an INV-4 server patch (spec §8.3) — until it lands, this pre-check defers nothing.
```

Prepend to `.context/modules/registry/CHANGELOG.md`:

```markdown
## 2026-09-25 — Manifest.env_required is read (was ignored)

- `src/registry/manifest.py`: `Manifest.env_required: list[str]` is populated by the loader and consumed by the scheduler's `provisioning_gap` pre-check (spec §8.3). Still no validation and still fail-open: a bad entry must not make a manifest unloadable, or the project's deploy path goes down with it. Adding a name to a project's `env_required` can now defer that project's schedules until the key is in its `.env`.
```

```bash
git add src/registry/manifest.py src/runner/main.py src/notify/outbox.py tests/test_provisioning_gap.py .context/modules/runner/CHANGELOG.md .context/modules/registry/CHANGELOG.md .context/modules/runner/CONTEXT.md .context/modules/registry/CONTEXT.md .context/SYSTEM.md
git commit -m "feat(runner): interim scheduler provisioning_gap pre-check — defer + DM instead of running a schedule whose project .env lacks a manifest-required key (spec §8.3)"
```

---

### Task 7: Bot delivers the outbox — listener + 30 s poll, `Details` button, `format_job_status`, quota notices


**Execution position:** 14 of 21 — previous: Task 21, next: Task 8 (see Global Constraints "Execution order").

**Files:**
- Modify: `src/gateway/telegram_bot.py` — imports (`:26-31`), `_handle_button` (`:820-860` head), `_done_listener` (`:1019-1048`), `_quota_notifier` (`:1054-1081`), `_task_notifier` (`:1087-1100` loop head — switch gate), `_post_init` (`:1274-1277`); add `format_job_status`, `_handle_done_message`, `_drain_outbox`, `_outbox_listener`
- Modify: `src/config.py` (`notify_outbox` default `False` → `True`: the consumer now exists), `.context/modules/db/CHANGELOG.md`
- Modify (Step 3b — window figures labelled by source, spec §2.8 / review #4): `src/runner/quota.py:95-101` (`pause_queue` gains `source`; new `last_source()`), `src/runner/session.py:1077-1104` (the three `QuotaExhausted(...)` raises pass `source=`), `src/runner/main.py:448` (`pause_queue(..., source=exc.source)`)
- Modify: `.context/modules/gateway/CHANGELOG.md`, `.context/modules/runner/CHANGELOG.md`, `.context/SYSTEM.md` (`telegram_bot.py` Depends-on gains `notify.outbox, notify.telegram` — both rows exist since Task 5, so `check_module_graph_imports` flags the new imports otherwise)
- Test: `tests/test_notify_bot.py`, `tests/test_quota.py` (append)

**Interfaces:**
- Consumes: `outbox.pending_notices/claim_notice/release_stuck_sending/mark_sent/mark_failed/build_ops_notice/enqueue_notice`, `telegram.render_telegram/send_via_bot` (Task 5); `db.CHANNEL_NOTIFY_OUTBOX`; Task 3's job columns.
- Produces:
  - `settings.notify_outbox` default flips to `True` in this commit (Task 5 shipped it `False` because nothing consumed the rows). The runner keeps dual-writing (Task 6); the switch selects the bot renderer only.
  - `telegram_bot.format_job_status(job) -> str` (pure; used by the `jd:` button here and `/status <prefix>` in Task 8).
  - `async telegram_bot._handle_done_message(app, channel: str, data: str) -> bool` — the per-message body of `_done_listener`, extracted so the spec's exit criterion (`NOTIFY_OUTBOX=0` → legacy `_job_to_chat` DM) is testable without pub/sub. Returns True when it sent.
  - `async telegram_bot._drain_outbox(app) -> tuple[int, int]` (sent, failed). Claims each row with `claim_notice` before sending (rowcount 0 → skipped: a concurrent `python -m src.notify drain` has it).
  - `async telegram_bot._outbox_listener(app)` — calls `release_stuck_sending()` once at startup, subscribes `notify:outbox`, drains on every nudge and at least every `_OUTBOX_POLL_SECONDS = 30`.
  - Callback `jd:<job8>` → job details reply.
  - Renderer-side switch: `_done_listener` and `_task_notifier` receive the (always-published) legacy messages but send only while `settings.notify_outbox` is False; `_outbox_listener` is started only while it is True. A bot-only restart flips delivery.
  - `quota.QuotaExhausted(reset_at, reason="", source="estimated")` — `source ∈ {"vendor", "estimated"}`; `session._run_in_process` passes `source="vendor"` only on the `RateLimitEvent` path whose `resets_at` produced the datetime (`detect_from_rate_limit` returned a datetime), `"estimated"` on the text-heuristic paths and when the reset is unknown. `async quota.pause_queue(reset_at, reason, *, source="estimated") -> datetime` stores `quota:last_source` beside `quota:paused_until`; `async quota.last_source() -> str` (`"estimated"` when unset). `_quota_notifier` renders `Reset at HH:MM UTC (vendor)` or `Reset at HH:MM UTC (estimated)`; every other P0 surface that names a reset time (`/status`, runner log) is left as is but MUST NOT say "vendor". Spec §2.8 Claude row: the SDK emits `resets_at` only on transitions; nothing else in P0 is a vendor gauge.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_notify_bot.py`:

```python
"""
Bot-side outbox delivery (P0). Everything touching python-telegram-bot or the
DB is monkeypatched; what is tested is the drain loop's bookkeeping and the
pure job-status formatter.

Run: pipenv run pytest tests/test_notify_bot.py -v
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

from src.gateway import telegram_bot as bot_mod
from src.gateway.telegram_bot import format_job_status


def _job(**over):
    base = dict(id=uuid.UUID("abcdef12-0000-4000-8000-000000000000"), status="failed",
                kind="task", resolved_skill="app-patch", resolved_model="claude-sonnet-4-6",
                model_served="claude-sonnet-4-6", terminal_reason="api_error", num_turns=4,
                input_tokens=15, output_tokens=900, cache_read_tokens=20000,
                duration_api_ms=4200, cost_usd_list=None, origin_channel="scheduler",
                origin_ref="nightly", error_message="API Error: 529 Overloaded",
                result={"summary": "did things"})
    base.update(over)
    return SimpleNamespace(**base)


class TestFormatJobStatus:
    def test_shows_p0_columns_and_summary(self):
        text = format_job_status(_job())
        assert text.startswith("Job abcdef12 — failed")
        for needle in ("app-patch", "claude-sonnet-4-6", "terminal: api_error", "turns: 4",
                       "out 900", "4.2s", "origin: scheduler:nightly", "529", "did things"):
            assert needle in text, needle

    def test_never_exceeds_telegram_limit(self):
        assert len(format_job_status(_job(result={"summary": "x" * 9000},
                                          error_message="e" * 9000))) <= 4000

    def test_minimal_job(self):
        text = format_job_status(_job(model_served=None, resolved_model=None, terminal_reason=None,
                                      num_turns=None, output_tokens=None, duration_api_ms=None,
                                      origin_channel=None, error_message=None, result=None))
        assert text == "Job abcdef12 — failed\nkind: app-patch"


class _Store:
    """Fake notifications table for the drain loop (mirrors outbox.py's
    claim → send → mark_sent/mark_failed contract)."""

    def __init__(self, rows):
        self.rows = {r.id: r for r in rows}
        self.sent, self.failed = [], []

    async def pending(self, limit=20):
        return [r for r in self.rows.values() if r.status == "pending"]

    async def claim(self, nid, now=None):
        row = self.rows[nid]
        if row.status != "pending":
            return False
        row.status, row.attempts = "sending", row.attempts + 1
        return True

    async def mark_sent(self, nid, ref, **kw):
        self.rows[nid].status = "sent"
        self.sent.append((nid, ref))

    async def mark_failed(self, nid, err, *, attempts_so_far, **kw):
        self.rows[nid].attempts = attempts_so_far + 1
        self.rows[nid].status = "failed" if self.rows[nid].attempts >= 5 else "pending"
        self.failed.append((nid, err))
        return self.rows[nid].status


def _row(kind="job_completed", target="123"):
    return SimpleNamespace(id=uuid.uuid4(), notice_kind=kind, body="pong", severity="info",
                           subject_type="job", subject_id="j", actions={"buttons": [], "job8": "abcdef12"},
                           target=target, thread=None, status="pending", attempts=0)


def _wire(monkeypatch, store, send):
    monkeypatch.setattr(bot_mod, "pending_notices", store.pending)
    monkeypatch.setattr(bot_mod, "claim_notice", store.claim)
    monkeypatch.setattr(bot_mod, "mark_sent", store.mark_sent)
    monkeypatch.setattr(bot_mod, "mark_failed", store.mark_failed)
    monkeypatch.setattr(bot_mod, "send_via_bot", send)
    monkeypatch.setattr(bot_mod.settings, "telegram_allowed_chat_ids", "999")


class TestDrainOutbox:
    async def test_delivers_and_stamps(self, monkeypatch):
        store = _Store([_row(), _row(kind="job_failed")])

        async def send(bot, msg):
            return 4242

        _wire(monkeypatch, store, send)
        sent, failed = await bot_mod._drain_outbox(SimpleNamespace(bot=object()))
        assert (sent, failed) == (2, 0)
        assert all(r.status == "sent" for r in store.rows.values())
        assert store.sent[0][1] == "4242"

    async def test_pending_rows_survive_listener_restart(self, monkeypatch):
        # Review Focus 1: a row written while the bot was down / a send that
        # failed is retried by a later drain (the 30 s poll) — no pub/sub needed.
        row = _row()
        store = _Store([row])
        calls = {"n": 0}

        async def flaky(bot, msg):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("Telegram 502")
            return 7

        _wire(monkeypatch, store, flaky)
        app = SimpleNamespace(bot=object())
        assert await bot_mod._drain_outbox(app) == (0, 1)
        assert row.status == "pending" and row.attempts == 1
        assert await bot_mod._drain_outbox(app) == (1, 0)      # "restart": fresh drain, same row
        assert row.status == "sent"

    async def test_row_claimed_elsewhere_is_skipped(self, monkeypatch):
        # A concurrent `python -m src.notify drain` won the claim: never send twice.
        store = _Store([_row()])

        async def send(bot, msg):
            raise AssertionError("must not send an unclaimed row")

        async def lost_claim(nid, now=None):
            return False

        _wire(monkeypatch, store, send)
        monkeypatch.setattr(bot_mod, "claim_notice", lost_claim)
        assert await bot_mod._drain_outbox(SimpleNamespace(bot=object())) == (0, 0)

    async def test_no_owner_chat_means_no_delivery(self, monkeypatch):
        store = _Store([_row()])

        async def send(bot, msg):
            raise AssertionError("must not send")

        _wire(monkeypatch, store, send)
        monkeypatch.setattr(bot_mod.settings, "telegram_allowed_chat_ids", "")
        assert await bot_mod._drain_outbox(SimpleNamespace(bot=object())) == (0, 0)


class _FakeBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text, **kw):
        self.sent.append((chat_id, text))
        return SimpleNamespace(message_id=1)


class TestLegacyRenderersGatedBySwitch:
    """Spec §9 P0 exit criterion: with NOTIFY_OUTBOX=0 a Telegram-launched job
    still DMs via the legacy `_job_to_chat` path. The runner publishes
    `jobs:done:<id>` in both modes (Task 6 dual-write); only the bot decides."""

    async def test_done_message_sends_legacy_when_outbox_off(self, monkeypatch):
        monkeypatch.setattr(bot_mod.settings, "notify_outbox", False)
        job_id = str(uuid.uuid4())
        monkeypatch.setitem(bot_mod._job_to_chat, job_id, 123)
        bot = _FakeBot()
        sent = await bot_mod._handle_done_message(
            SimpleNamespace(bot=bot), f"jobs:done:{job_id}",
            '{"status": "completed", "summary": "pong"}')
        assert sent is True
        assert bot.sent and bot.sent[0][0] == 123 and "pong" in bot.sent[0][1]
        assert "/rate" not in bot.sent[0][1]                 # spec §4.1
        assert job_id not in bot_mod._job_to_chat

    async def test_done_message_is_dropped_when_outbox_on(self, monkeypatch):
        monkeypatch.setattr(bot_mod.settings, "notify_outbox", True)
        job_id = str(uuid.uuid4())
        monkeypatch.setitem(bot_mod._job_to_chat, job_id, 123)
        bot = _FakeBot()
        sent = await bot_mod._handle_done_message(
            SimpleNamespace(bot=bot), f"jobs:done:{job_id}", '{"status": "completed"}')
        assert sent is False and bot.sent == []
        assert job_id not in bot_mod._job_to_chat             # popped either way: no leak

    def test_task_notifier_and_listener_start_are_gated(self):
        import inspect
        src = inspect.getsource(bot_mod._task_notifier)
        assert "if settings.notify_outbox:" in src and "continue" in src
        post = inspect.getsource(bot_mod._post_init)
        assert "if settings.notify_outbox:" in post and "_outbox_listener" in post


class TestCallbackParsing:
    def test_job_details_callback_parses(self):
        assert bot_mod._parse_callback("jd:abcdef12") == ("jd", "abcdef12", None)


class TestQuotaNoticeLabelsTheSource:
    """Spec §2.8 / review #4: a reset time is 'vendor' only when a RateLimitEvent
    carried it; the text heuristic and the default window are 'estimated'."""

    def test_reset_line_names_the_source(self):
        from datetime import datetime, timezone
        at = datetime(2026, 9, 25, 14, 0, tzinfo=timezone.utc)
        assert "Reset at 14:00 UTC (vendor)" in bot_mod.quota_paused_text(at, "rate limit rejected", "vendor")
        assert "Reset at 14:00 UTC (estimated)" in bot_mod.quota_paused_text(at, "x", "estimated")
        assert "Reset at unknown (estimated)" in bot_mod.quota_paused_text(None, "x", "vendor")   # no time → never 'vendor'

    def test_notifier_reads_last_source(self):
        import inspect
        assert "quota.last_source()" in inspect.getsource(bot_mod._quota_notifier)
```

Append to `tests/test_quota.py` (fakeredis round-trip, same style as `TestPauseResume`):

```python
class TestPauseSource:
    async def test_default_source_is_estimated(self, fake_redis):
        await quota.pause_queue(datetime.now(timezone.utc) + timedelta(minutes=5), "x")
        assert await quota.last_source() == "estimated"

    async def test_vendor_source_round_trips(self, fake_redis):
        await quota.pause_queue(datetime.now(timezone.utc) + timedelta(minutes=5), "x", source="vendor")
        assert await quota.last_source() == "vendor"

    async def test_clear_forgets_source(self, fake_redis):
        await quota.pause_queue(datetime.now(timezone.utc) + timedelta(minutes=5), "x", source="vendor")
        await quota.clear()
        assert await quota.last_source() == "estimated"

    def test_exception_carries_source(self):
        assert quota.QuotaExhausted(None, "r").source == "estimated"
        assert quota.QuotaExhausted(None, "r", source="vendor").source == "vendor"


class TestSessionPassesVendorOnlyForRateLimitEvent:
    def test_three_raise_sites_are_labelled(self):
        import ast, inspect
        from src.runner import session
        src = inspect.getsource(session._run_in_process)
        raises = [ast.unparse(n) for n in ast.walk(ast.parse(src))
                  if isinstance(n, ast.Raise) and "QuotaExhausted" in ast.unparse(n)]
        assert len(raises) == 3, raises
        vendor = [r for r in raises if 'source="vendor"' in r or "source='vendor'" in r]
        assert len(vendor) == 1, "exactly the RateLimitEvent path may claim a vendor reset"
        assert all("source=" in r for r in raises)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pipenv run pytest tests/test_notify_bot.py tests/test_quota.py -v`
Expected: `ImportError: cannot import name 'format_job_status'` (collection fails; once it collects, the gate tests fail on `_handle_done_message` missing and the `_task_notifier` source assertion).

- [ ] **Step 3: Implement in `telegram_bot.py`**

Imports (add beside the existing `from src.db import …` / `from src.gateway.jobs import …` lines):

```python
from src.db import CHANNEL_JOB_DONE, CHANNEL_NOTIFY_OUTBOX, async_session, redis
from src.notify.outbox import (
    build_ops_notice,
    claim_notice,
    enqueue_notice,
    mark_failed,
    mark_sent,
    pending_notices,
    release_stuck_sending,
)
from src.notify.telegram import render_telegram, send_via_bot
```

`src/config.py` — flip the default written in Task 5 and shorten its comment:

```python
    # Notifications (P0, spec §4.5). The runner ALWAYS publishes the legacy
    # tasks:notify / jobs:done channels and, with this on, ALSO writes
    # `notifications` rows. The switch is renderer-side: on → the bot's
    # outbox listener delivers; off → the legacy _job_to_chat / _task_notifier
    # renderers do. Flipping it needs a bot restart only. NOTIFY_OUTBOX=0 is
    # the kill switch.
    notify_outbox: bool = True
```

Add after `_parse_callback`:

```python
def format_job_status(job) -> str:
    """Pure. `/status <prefix>` and the [Details] button. Plain text (no
    parse_mode — skill names with `_` crash Markdown, TROUBLESHOOTING.md)."""
    lines = [f"Job {str(job.id)[:8]} — {job.status}", f"kind: {job.resolved_skill or job.kind}"]
    model = job.model_served or job.resolved_model
    if model:
        lines.append(f"model: {model}")
    if job.terminal_reason:
        lines.append(f"terminal: {job.terminal_reason}")
    if job.num_turns is not None:
        lines.append(f"turns: {job.num_turns}")
    if job.output_tokens is not None:
        lines.append(f"tokens: in {job.input_tokens or 0} · out {job.output_tokens or 0} "
                     f"· cache-read {job.cache_read_tokens or 0}")
    if job.duration_api_ms:
        lines.append(f"api time: {job.duration_api_ms / 1000:.1f}s")
    if job.cost_usd_list is not None:
        lines.append(f"list-equiv cost: ${float(job.cost_usd_list):.4f}")
    if job.origin_channel:
        ref = f":{job.origin_ref}" if job.origin_ref else ""
        lines.append(f"origin: {job.origin_channel}{ref}")
    if job.error_message:
        lines.append(f"error: {job.error_message[:300]}")
    summary = job.result.get("summary") if isinstance(job.result, dict) else None
    if summary:
        lines.append("")
        lines.append(summary[:600])
    return "\n".join(lines)[:4000]
```

In `_handle_button`, right after `action, task_prefix, extra = _parse_callback(query.data or "")` / `if not task_prefix: return`, and BEFORE `task = await _find_task_by_prefix(task_prefix)`:

```python
    # Job-level callbacks (P0 cards) — the prefix is a JOB id, not a task id.
    if action == "jd":
        job = await find_job_by_prefix(task_prefix)
        await query.message.reply_text(format_job_status(job) if job else "Job not found.")
        return
```

`_done_listener` (lines 1019-1048): replace the whole function with the pair below — the loop body moves into `_handle_done_message` so the switch behaviour is unit-testable, and the `/rate` hint line is gone (spec §4.1: `/rate` leaves the copy):

```python
async def _handle_done_message(app: Application, channel: str, data: str) -> bool:
    """One `jobs:done:<id>` message. Legacy renderer: sends only while the
    outbox is OFF (renderer-side switch; the runner publishes in both modes).
    The _job_to_chat entry is popped either way so the dict never leaks.
    Returns True when a DM was sent."""
    job_id = channel.rsplit(":", 1)[-1]
    chat_id = _job_to_chat.pop(job_id, None)
    if not chat_id or settings.notify_outbox:
        return False     # outbox on: the DoneCard comes from _outbox_listener
    try:
        payload = json.loads(data or "{}")
    except json.JSONDecodeError:
        payload = {}
    status = payload.get("status", "unknown")
    summary = (payload.get("summary") or "")[:1500]
    text = f"Job `{job_id[:8]}` *{status}*"
    if summary:
        text += f"\n\n{summary}"
    try:
        await app.bot.send_message(chat_id, text, parse_mode="Markdown")
    except Exception:
        logger.exception("failed to DM result", chat_id=chat_id, job_id=job_id)
        return False
    return True


async def _done_listener(app: Application) -> None:
    pubsub = redis.pubsub()
    await pubsub.psubscribe(f"{CHANNEL_JOB_DONE}:*")
    try:
        async for msg in pubsub.listen():
            if msg.get("type") != "pmessage":
                continue
            await _handle_done_message(app, msg.get("channel", ""), msg.get("data", "{}"))
    finally:
        await pubsub.punsubscribe(f"{CHANNEL_JOB_DONE}:*")
```

`_task_notifier` (loop head, lines 1092-1098): the legacy card renderer now receives every publish in both modes (Task 6 dual-write), so gate it. Directly after the `except json.JSONDecodeError: continue` that follows `data = json.loads(msg.get("data", "{}"))`, insert:

```python
            if settings.notify_outbox:
                continue     # renderer-side switch: _outbox_listener sends these cards
```

(the rest of `_task_notifier` stays byte-identical).

`_quota_notifier`: replace the inner `for chat_id in settings.allowed_chat_ids: … send_message(...)` block with

```python
            if paused:
                text = quota_paused_text(reset_at, reason, await quota.last_source())
                kind, sev = "quota_paused", "warn"
            else:
                text, kind, sev = "Queue resumed.", "quota_resumed", "info"
            if settings.notify_outbox:
                await enqueue_notice(build_ops_notice(kind=kind, severity=sev, text=text))
            else:
                for chat_id in settings.allowed_chat_ids:
                    try:
                        await app.bot.send_message(chat_id, ("⏸ " if paused else "▶️ ") + text)
                    except Exception:
                        logger.exception("failed to send quota notification")
            last_state = state
```

Add before `_post_init`:

```python
# ── Outbox delivery (P0) ────────────────────────────────────────────────────

_OUTBOX_POLL_SECONDS = 30


async def _drain_outbox(app: Application) -> tuple[int, int]:
    """Deliver every pending outbox row once. Returns (sent, failed). Each
    row is CLAIMED first (status → sending, attempts+1): a concurrent
    `python -m src.notify drain` selects the same pending rows, and without
    the claim both would send the DM."""
    ids = settings.allowed_chat_ids
    if not ids:
        return 0, 0
    owner = ids[0]
    sent = failed = 0
    for row in await pending_notices(limit=20):
        attempts_before = row.attempts          # claim bumps it; mark_failed re-derives from this
        if not await claim_notice(row.id):
            continue                            # someone else has it
        try:
            ref = await send_via_bot(app.bot, render_telegram(row, owner_chat_id=owner))
            await mark_sent(row.id, str(ref), subject_type=row.subject_type, subject_id=row.subject_id)
            sent += 1
        except Exception as exc:  # noqa: BLE001 — recorded on the row, retried with backoff
            await mark_failed(row.id, str(exc)[:300], attempts_so_far=attempts_before,
                              subject_type=row.subject_type, subject_id=row.subject_id)
            failed += 1
            logger.warning("outbox delivery failed", notice_id=str(row.id), error=str(exc)[:120])
    return sent, failed


async def _outbox_listener(app: Application) -> None:
    """Drain on every `notify:outbox` nudge and at least every 30 s. The poll
    is what makes a bot restart lossless: rows written while we were down
    are still `pending` (exit criterion 'bot restart loses no DM'). Rows a
    crashed drainer left `sending` past their 5-min lease are released first."""
    try:
        released = await release_stuck_sending()
        if released:
            logger.warning("outbox: released stuck sending rows", count=released)
    except Exception:
        logger.exception("outbox: release_stuck_sending failed (continuing)")
    pubsub = redis.pubsub()
    await pubsub.subscribe(CHANNEL_NOTIFY_OUTBOX)
    try:
        while True:
            try:
                await pubsub.get_message(ignore_subscribe_messages=True,
                                         timeout=_OUTBOX_POLL_SECONDS)
                await _drain_outbox(app)
            except Exception:
                logger.exception("outbox listener iteration failed (continuing)")
                await asyncio.sleep(2)
    finally:
        await pubsub.unsubscribe(CHANNEL_NOTIFY_OUTBOX)
```

`_post_init`:

```python
async def _post_init(app: Application) -> None:
    # Both legacy listeners always run (the runner dual-writes); they send
    # only while notify_outbox is off. Renderer-side switch = bot-only restart.
    asyncio.create_task(_done_listener(app))
    asyncio.create_task(_task_notifier(app))
    asyncio.create_task(_quota_notifier(app))
    if settings.notify_outbox:
        asyncio.create_task(_outbox_listener(app))
```

- [ ] **Step 3b: Label the reset time by its source (spec §2.8 Claude row, review #4)**

Add to `telegram_bot.py` (pure, next to `format_job_status`):

```python
def quota_paused_text(reset_at: datetime | None, reason: str, source: str) -> str:
    """The quota_paused DM body. A reset time is labelled 'vendor' ONLY when a
    RateLimitEvent carried it (spec §2.8: the SDK emits resets_at on status
    transitions, never a 5h/7d gauge); the text heuristic and the default
    pause window are 'estimated'. No time → always 'estimated'."""
    label = "vendor" if (reset_at is not None and source == "vendor") else "estimated"
    reset_str = reset_at.strftime("%H:%M UTC") if reset_at else "unknown"
    return (f"Queue paused (subscription quota).\nReset at {reset_str} ({label}).\n"
            f"Reason: {reason[:200]}")
```

`src/runner/quota.py` — `QuotaExhausted.__init__(self, reset_at, reason="", source="estimated")` stores `self.source`; add `_KEY_LAST_SOURCE = "quota:last_source"`; `pause_queue(reset_at, reason, *, source="estimated")` also does `await redis.set(_KEY_LAST_SOURCE, source)`; `is_paused()`'s auto-resume branch and `clear()` delete it too; new:

```python
async def last_source() -> str:
    """'vendor' when the current pause's reset time came from a RateLimitEvent, else 'estimated'."""
    return (await redis.get(_KEY_LAST_SOURCE)) or "estimated"
```

`src/runner/session.py` `_run_in_process` — the `RateLimitEvent` branch (`:1075-1081`):

```python
                    detected = quota.detect_from_rate_limit(info)
                    if detected is not None:
                        reset_at = detected if isinstance(detected, datetime) else None
                        raise quota.QuotaExhausted(
                            reset_at,
                            reason=f"rate limit rejected "
                                   f"(window={getattr(info, 'rate_limit_type', '?')})",
                            source="vendor" if reset_at is not None else "estimated",
                        )
```

and the two text-heuristic raises (`:1090`, `:1102`) gain `source="estimated"`. `src/runner/main.py:448`: `await quota.pause_queue(exc.reset_at, exc.reason, source=getattr(exc, "source", "estimated"))`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pipenv run pytest tests/test_notify_bot.py tests/test_telegram_commands.py tests/test_quota.py -v`
Expected: all PASS.

- [ ] **Step 5: Live check — the P0 exit criteria for notifications**

1. Restart the bot (`launchctl kickstart -k gui/$(id -u)/com.assistant.bot` on the dev box if it runs under launchd, otherwise `pipenv run python -m src.gateway.telegram_bot` in a terminal).
2. Send `/task reply with the word pong` from Telegram → within ~60 s a `✅ done` reply arrives under the thread; `psql assistant -tAc "SELECT status, external_ref FROM notifications ORDER BY created_at DESC LIMIT 1"` → `sent|<message id>`.
3. Restart test: `pipenv run python -c "import asyncio; from src.gateway.jobs import enqueue_job; asyncio.run(enqueue_job('reply pong', kind='chat', created_by='owner-terminal'))"` while the bot is STOPPED; start the bot after the job completes → the DM arrives within 30 s of bot start.
4. Scheduled failure: `pipenv run python -c "import asyncio; from src.gateway.jobs import enqueue_job; asyncio.run(enqueue_job('x', kind='no-such-skill', created_by='scheduler'))"` → a `❌ failed` DM whose header line ends `· error · via scheduler` (FailedCard wording from `build_job_notice`; `terminal: error` is `format_job_status` wording and appears only after the tap) arrives within 60 s and carries a `[Details]` button that answers with `format_job_status`.
5. Kill-switch check (bot-only restart): `NOTIFY_OUTBOX=0 pipenv run python -m src.gateway.telegram_bot` in a terminal (stop the launchd bot first), send `/task reply pong` → the legacy card arrives from `_task_notifier`, and the row the runner still writes stays `pending` (`SELECT status FROM notifications ORDER BY created_at DESC LIMIT 1`). Restore the launchd bot; on its next drain that pending row is delivered — mark it `skipped` first if you do not want the duplicate: `psql assistant -c "UPDATE notifications SET status='skipped' WHERE status='pending'"`.

- [ ] **Step 6: SYSTEM.md Depends-on, CHANGELOGs, commit**

`.context/SYSTEM.md` module graph: append `, notify.outbox, notify.telegram` to the Depends-on cell of the `src/gateway/telegram_bot.py` row (today `config, db, models, gateway.jobs, audit_log, runner.router, runner.plans`).

Run: `pipenv run pytest tests/test_doc_lint.py -q && pipenv run python scripts/lint_docs.py` → Expected: PASS and `All clean!`.

Prepend to `.context/modules/gateway/CHANGELOG.md`:

```markdown
## 2026-09-25 — bot delivers the notifications outbox (nudge + 30 s poll); [Details] job button; quota notices via outbox; NOTIFY_OUTBOX flipped on

- `telegram_bot`: `_outbox_listener`/`_drain_outbox` claim (`claim_notice`) and render rows with `src/notify/telegram.py`, stamp sent/failed (+backoff), release stuck `sending` rows at startup — a bot restart loses no DM; `_done_listener` (body now `_handle_done_message`, tested) and `_task_notifier` send only while `NOTIFY_OUTBOX=0` (renderer-side switch: the runner dual-writes, a bot-only restart flips delivery); `_quota_notifier` writes `quota_paused/resumed` notices; new `jd:<job8>` callback → `format_job_status` (pure). `/rate` hint removed from the legacy done DM. `.context/SYSTEM.md` telegram_bot Depends-on += `notify.outbox, notify.telegram`.
- Why: spec §9 P0 exit criteria (every launch DMs, scheduled failures within 60 s, bot restart lossless, `NOTIFY_OUTBOX=0` still DMs via the legacy path).
- `quota_paused_text` (pure): the reset line says `(vendor)` only when the pause's reset time came from a `RateLimitEvent`, else `(estimated)` — spec §2.8 / review #4.
```

Prepend to `.context/modules/db/CHANGELOG.md`:

```markdown
## 2026-09-25 — settings.notify_outbox default → True

- `src/config.py`: `notify_outbox` ships `True` now that the bot's `_outbox_listener` consumes the rows (was `False` since the Task 5 commit). `NOTIFY_OUTBOX=0` is the kill switch; it changes which bot renderer sends, never what the runner publishes.
```

Prepend to `.context/modules/runner/CHANGELOG.md`:

```markdown
## 2026-09-25 — quota pause records the reset-time source (vendor vs estimated)

- `quota.QuotaExhausted(..., source=)`, `quota.pause_queue(..., source=)` → Redis `quota:last_source`, `quota.last_source()`. `session._run_in_process` claims `vendor` only on the `RateLimitEvent` path with a real `resets_at`; the text heuristic and the default window are `estimated`. Consumed by the bot's `quota_paused` DM (spec §2.8 Claude row, review #4: never label a window figure vendor-sourced unless a vendor event carried it).
```

```bash
git add src/gateway/telegram_bot.py src/config.py src/runner/quota.py src/runner/session.py src/runner/main.py tests/test_notify_bot.py tests/test_quota.py .context/modules/gateway/CHANGELOG.md .context/modules/db/CHANGELOG.md .context/modules/runner/CHANGELOG.md .context/SYSTEM.md
git commit -m "feat(gateway): bot delivers the notifications outbox (claim + pub/sub nudge + 30s poll, retry with backoff), job Details button; quota_paused DM labels the reset source; NOTIFY_OUTBOX on"
```

---

### Task 8: Ghost commands become real — durable `/cancel <prefix>`, `/status <prefix>`, `/proposals`; `/rate` leaves the copy


**Execution position:** 15 of 21 — previous: Task 7, next: Task 9 (see Global Constraints "Execution order").

**Files:**
- Modify: `src/gateway/jobs.py` — add `cancel_action_for_status`, `remove_from_queue`, `cancel_job_durable`
- Modify: `src/gateway/web.py:428-436` (`delete_job`)
- Modify: `src/gateway/telegram_bot.py` — `cmd_help` (`:179-196`), `cmd_status` (`:409-447`), `cmd_jobs` (`:704-716`), add `cmd_cancel`, `cmd_proposals`, `format_cancel_reply`; `main()` handler registration (`:1296-1308`)
- Modify: `.context/modules/gateway/CHANGELOG.md`, `.context/SYSTEM.md` (two Depends-on cells: `jobs.py` gains `audit_log`, `telegram_bot.py` gains `runner.proposals` — `check_module_graph_imports` walks the whole AST, so the function-level import in `cmd_proposals` counts)
- Test: `tests/test_cancel_durable.py`, `tests/test_telegram_commands.py` (append)

**Interfaces:**
- Consumes: `format_job_status` (Task 7); `proposals.list_pending_proposals(limit)`, `proposals.format_proposal_line(...)` (existing, `src/runner/proposals.py:73-99, 178-186`); `audit_log.append`.
- Produces:
  - `jobs.cancel_action_for_status(status: str) -> str` — `"lrem_and_flip" | "publish" | "noop"` (pure).
  - `async jobs.remove_from_queue(job_id) -> int` — `LREM jobs:queue 0 <id>`; returns removed count.
  - `async jobs.cancel_job_durable(job: Job) -> str` — `"cancelled_queued" | "cancel_requested" | "already_terminal"`; queued/deferred rows are LREM'd and flipped to `cancelled` in one place (INV-9 safe: `WHERE status IN (queued, deferred)`), running jobs get the existing `jobs:cancel` publish, everything else is a no-op. Writes one `job_cancelled{stage="queued"}` audit event on a real flip.
  - `telegram_bot.format_cancel_reply(result: str, prefix: str) -> str` (pure).
  - Telegram handlers `/cancel <prefix>`, `/status <prefix>` (falls back to the task list with no argument), `/proposals`; `/rate` removed from `/jobs` output and help (the `POST /api/jobs/{id}/rate` endpoint and the `rate:` callback stay).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_cancel_durable.py`:

```python
"""
Durable cancel (P0 ghost-command fix): queued jobs are removed from Redis and
flipped, running jobs get the cancel publish, terminal jobs are a no-op.

Run: pipenv run pytest tests/test_cancel_durable.py -v
"""

from __future__ import annotations

import uuid

import pytest

from src.db import QUEUE_JOBS
from src.gateway import jobs as jobs_mod
from src.gateway.jobs import cancel_action_for_status, remove_from_queue


class TestCancelAction:
    @pytest.mark.parametrize("status,expected", [
        ("queued", "lrem_and_flip"), ("deferred", "lrem_and_flip"),
        ("running", "publish"), ("awaiting_user", "noop"),
        ("completed", "noop"), ("failed", "noop"), ("cancelled", "noop"),
    ])
    def test_mapping(self, status, expected):
        assert cancel_action_for_status(status) == expected

    def test_cancel_action_noop_for_terminal(self):
        # Review Focus 4: the second /cancel of the same job must be a no-op.
        assert cancel_action_for_status("cancelled") == "noop"


class TestRemoveFromQueue:
    async def test_remove_from_queue_idempotent(self, fake_redis, monkeypatch):
        monkeypatch.setattr(jobs_mod, "redis", fake_redis)
        jid = str(uuid.uuid4())
        other = str(uuid.uuid4())
        await fake_redis.rpush(QUEUE_JOBS, other, jid, jid)   # duplicates from a requeue race
        assert await remove_from_queue(jid) == 2
        assert await remove_from_queue(jid) == 0               # second cancel: nothing to remove
        assert await fake_redis.lrange(QUEUE_JOBS, 0, -1) == [other]
```

Append to `tests/test_telegram_commands.py`:

```python
class TestCancelReply:
    def test_replies(self):
        from src.gateway.telegram_bot import format_cancel_reply
        assert format_cancel_reply("cancelled_queued", "abcdef12") == "🚫 Job abcdef12 removed from the queue."
        assert format_cancel_reply("cancel_requested", "abcdef12") == "🚫 Cancel sent to running job abcdef12 (honoured within 2 s)."
        assert format_cancel_reply("already_terminal", "abcdef12") == "Job abcdef12 is already finished — nothing to cancel."
        assert format_cancel_reply("not_found", "abcdef12") == "No job matches abcdef12 (need a unique 8-char prefix)."


class TestHelpCopy:
    def test_help_and_jobs_no_longer_advertise_rate(self):
        import inspect
        from src.gateway import telegram_bot
        src = inspect.getsource(telegram_bot.cmd_help) + inspect.getsource(telegram_bot.cmd_jobs)
        assert "/rate" not in src
        assert "/cancel <prefix>" in inspect.getsource(telegram_bot.cmd_help)
        assert "/proposals" in inspect.getsource(telegram_bot.cmd_help)

    def test_ghost_commands_are_registered(self):
        import inspect
        from src.gateway import telegram_bot
        src = inspect.getsource(telegram_bot.main)
        for cmd in ('CommandHandler("cancel", cmd_cancel)', 'CommandHandler("proposals", cmd_proposals)'):
            assert cmd in src
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pipenv run pytest tests/test_cancel_durable.py tests/test_telegram_commands.py -v`
Expected: `ImportError: cannot import name 'cancel_action_for_status'`; the appended Telegram tests fail on `format_cancel_reply` import / missing handlers.

- [ ] **Step 3: `jobs.py` — durable cancel**

Append to `src/gateway/jobs.py` (add `from datetime import datetime, timezone` and `from src import audit_log` to its imports):

```python
def cancel_action_for_status(status: str) -> str:
    """Pure. queued/deferred → remove from Redis + flip the row here;
    running → publish jobs:cancel (the runner interrupts, INV-8);
    anything else → no-op (a second /cancel is harmless)."""
    if status in (JobStatus.queued.value, JobStatus.deferred.value):
        return "lrem_and_flip"
    if status == JobStatus.running.value:
        return "publish"
    return "noop"


async def remove_from_queue(job_id: uuid.UUID | str) -> int:
    """LREM every copy of the id from jobs:queue. Idempotent."""
    return int(await redis.lrem(QUEUE_JOBS, 0, str(job_id)))


async def cancel_job_durable(job: Job) -> str:
    """Cancel a job whatever its state (P0; today main.py:1368-1404 reaches
    running jobs only). Returns cancelled_queued | cancel_requested |
    already_terminal."""
    from sqlalchemy import update as sql_update

    action = cancel_action_for_status(job.status)
    if action == "publish":
        await cancel_job(job.id)
        return "cancel_requested"
    if action == "noop":
        return "already_terminal"
    await remove_from_queue(job.id)
    async with async_session() as s:
        res = await s.execute(
            sql_update(Job)
            .where(Job.id == job.id,
                   Job.status.in_([JobStatus.queued.value, JobStatus.deferred.value]))
            .values(status=JobStatus.cancelled.value,
                    error_message="cancelled by user before it started",
                    completed_at=datetime.now(timezone.utc))
        )
        await s.commit()
    if res.rowcount == 0:
        return "already_terminal"       # raced with the runner's running flip / another cancel
    audit_log.append(job.id, "job_cancelled", stage="queued")
    return "cancelled_queued"
```

- [ ] **Step 4: `web.py` — DELETE uses the durable path**

Replace the body of `delete_job` (lines 429-436):

```python
async def delete_job(job_id: str) -> dict:
    job = await find_job_by_prefix(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    result = await cancel_job_durable(job)
    return {"ok": True, "note": result.replace("_", " ")}
```

and import `cancel_job_durable` from `src.gateway.jobs` (the `cancel_job` import may be removed if no longer referenced).

- [ ] **Step 5: `telegram_bot.py` — the three commands + copy fixes**

Import: `from src.gateway.jobs import cancel_job, cancel_job_durable, enqueue_job, find_job_by_prefix`.

Add after `format_job_status`:

```python
_CANCEL_REPLIES = {
    "cancelled_queued": "🚫 Job {p} removed from the queue.",
    "cancel_requested": "🚫 Cancel sent to running job {p} (honoured within 2 s).",
    "already_terminal": "Job {p} is already finished — nothing to cancel.",
    "not_found": "No job matches {p} (need a unique 8-char prefix).",
}


def format_cancel_reply(result: str, prefix: str) -> str:
    """Pure."""
    return _CANCEL_REPLIES.get(result, _CANCEL_REPLIES["not_found"]).format(p=prefix)


@_error_safe
async def cmd_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/cancel <job-prefix> — durable: queued jobs leave Redis and flip; running
    jobs are interrupted; a second call is a no-op."""
    if await _guard(update) is None:
        return
    args = ctx.args or []
    if not args:
        await update.message.reply_text("Usage: /cancel <job prefix>  (see /jobs)")
        return
    prefix = args[0].strip()
    job = await find_job_by_prefix(prefix)
    result = await cancel_job_durable(job) if job else "not_found"
    await update.message.reply_text(format_cancel_reply(result, prefix))


@_error_safe
async def cmd_proposals(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """/proposals — pending review-and-improve proposals (SYSTEM.md:51 gap)."""
    if await _guard(update) is None:
        return
    from src.runner.proposals import format_proposal_line, list_pending_proposals
    rows = await list_pending_proposals(limit=15)
    if not rows:
        await update.message.reply_text("No pending proposals.")
        return
    lines = [f"Pending proposals ({len(rows)}):"]
    lines += [format_proposal_line(p.id, p.target_file, p.change_type, p.outcome, p.proposed_at)
              for p in rows]
    await update.message.reply_text("\n".join(lines)[:4000])   # plain text: paths carry `_`
```

`cmd_status` (line 409): add the job-prefix branch at the top of the body, after the guard:

```python
    args = ctx.args or []
    if args:
        job = await find_job_by_prefix(args[0].strip())
        await update.message.reply_text(
            format_job_status(job) if job else f"No job matches {args[0]}.")
        return
```

(change its signature to `async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE)`).

`cmd_jobs` (line 709): change the completed line to `line += f"\n  → `/status {prefix}`"`.

`cmd_help` (lines 182-195): replace the commands block with

```python
        "*Commands (still work):*\n\n"
        "/task <description> — start a new task explicitly\n"
        "  _Reply in the thread to continue. Buttons for actions._\n\n"
        "/status — active tasks · /status <prefix> — one job's details\n"
        "/jobs — recent job runs\n"
        "/cancel <prefix> — cancel a queued or running job\n"
        "/proposals — pending self-improvement proposals\n"
        "/help — this message\n\n"
        "_Admin: /god, /chat, /resume, /clear (asks first), /schedule_",
```

`main()`: after `app.add_handler(CommandHandler("jobs", cmd_jobs))` add

```python
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(CommandHandler("proposals", cmd_proposals))
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `pipenv run pytest tests/test_cancel_durable.py tests/test_telegram_commands.py tests/test_web_god_gate.py -v`
Expected: all PASS.

Live check: enqueue a job while the runner is STOPPED (`pipenv run python -c "import asyncio; from src.gateway.jobs import enqueue_job; print(asyncio.run(enqueue_job('will be cancelled', kind='chat', created_by='owner-terminal')).id)"`), then `/cancel <prefix>` from Telegram → `🚫 Job … removed from the queue.`; `redis-cli lrange jobs:queue 0 -1` no longer lists it; `/cancel <prefix>` again → `already finished`; `tail -1 volumes/audit_log/<id>.jsonl` shows exactly one `job_cancelled`.

- [ ] **Step 7: SYSTEM.md Depends-on, CHANGELOG, commit**

`.context/SYSTEM.md` module graph, two cells (both import targets already have rows, so `check_module_graph_imports` warns until the importers declare them):
- `src/gateway/jobs.py` row — Depends-on `db, models` → `db, models, audit_log` (`from src import audit_log` is extracted as `audit_log` by `src.context.module_graph.extract_imports`).
- `src/gateway/telegram_bot.py` row — append `, runner.proposals` (the cell reads `…, runner.plans, notify.outbox, notify.telegram` after Task 7; `cmd_proposals`'s function-level `from src.runner.proposals import …` is still an import of a graph module).

Run: `pipenv run pytest tests/test_doc_lint.py -q && pipenv run python scripts/lint_docs.py` → Expected: PASS and `All clean!`.

Prepend to `.context/modules/gateway/CHANGELOG.md`:

```markdown
## 2026-09-25 — ghost commands fixed: durable /cancel <prefix>, /status <prefix>, /proposals; /rate out of the copy

- `jobs.cancel_job_durable` (LREM + row flip for queued/deferred; publish for running; no-op otherwise; one `job_cancelled{stage=queued}` event) — used by `/cancel`, the task Cancel path stays as is, and `DELETE /api/jobs/{id}`. `/status <prefix>` → `format_job_status`; `/proposals` → `list_pending_proposals`. `/jobs` and `/help` no longer advertise `/rate` (endpoint + `rate:` callback kept). `.context/SYSTEM.md`: `jobs.py` Depends-on += `audit_log`, `telegram_bot.py` += `runner.proposals`.
- Why: `/jobs` advertised three unregistered commands (state map §2.3); queued jobs could not be cancelled at all (`main.py:1368-1404` reaches running jobs only).
```

```bash
git add src/gateway/jobs.py src/gateway/web.py src/gateway/telegram_bot.py tests/test_cancel_durable.py tests/test_telegram_commands.py .context/modules/gateway/CHANGELOG.md .context/SYSTEM.md
git commit -m "feat(gateway): durable /cancel <prefix> (LREM + flip), /status <prefix>, /proposals; /rate removed from help"
```

---

### Task 9: `/clear` requires a confirm button


**Execution position:** 16 of 21 — previous: Task 8, next: Task 10 (see Global Constraints "Execution order").

**Files:**
- Modify: `src/gateway/telegram_bot.py` — `cmd_clear` (`:484-517`), `_handle_button` (job-level branch from Task 7), add `clear_token_valid`, `_do_clear`
- Modify: `.context/modules/gateway/CHANGELOG.md`
- Test: `tests/test_telegram_commands.py` (append)

**Interfaces:**
- Consumes: `cancel_job` (existing), `_parse_callback`.
- Produces:
  - `telegram_bot.clear_token_valid(stored: tuple[str, float] | None, token: str, now: float, ttl: int = 120) -> bool` (pure).
  - `async telegram_bot._do_clear() -> tuple[int, int]` (jobs, tasks cleared) — the old `cmd_clear` body plus a `jobs:cancel` publish for each running job so sessions actually stop, **plus one deliberate semantic widening**: the job filter goes from `[queued, running]` (today's `telegram_bot.py:493`) to `[queued, deferred, running]`, so `/clear` also cancels plan-DAG children parked in `deferred`. This is intended — today those children survive a `/clear` and are promoted later by `plans.promote_deferred_for` once their (now cancelled) parent is looked at, which is not what "clear everything" means to the person typing it — but it is a **behaviour change**, not an incidental diff, and a reviewer should read it as one. `tests/test_telegram_commands.py` gets a case asserting a `deferred` job is cancelled by `/clear`.
  - Callbacks `clear_confirm:<token>` and `clear_abort:0` (≤ 64 bytes).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_telegram_commands.py`:

```python
class TestClearConfirm:
    def test_token_valid_within_ttl(self):
        from src.gateway.telegram_bot import clear_token_valid
        assert clear_token_valid(("abcd1234", 1000.0), "abcd1234", 1050.0)

    def test_token_expired_or_wrong_or_missing(self):
        from src.gateway.telegram_bot import clear_token_valid
        assert not clear_token_valid(("abcd1234", 1000.0), "abcd1234", 1121.0)   # 121 s > 120
        assert not clear_token_valid(("abcd1234", 1000.0), "zzzz0000", 1001.0)
        assert not clear_token_valid(None, "abcd1234", 1001.0)

    def test_callbacks_fit_64_bytes(self):
        from src.gateway.telegram_bot import _parse_callback
        cb = "clear_confirm:" + "a" * 8
        assert len(cb.encode()) <= 64
        assert _parse_callback(cb) == ("clear_confirm", "a" * 8, None)
        assert _parse_callback("clear_abort:0") == ("clear_abort", "0", None)

    def test_cmd_clear_no_longer_clears_directly(self):
        import inspect
        from src.gateway import telegram_bot
        src = inspect.getsource(telegram_bot.cmd_clear)
        assert "clear_confirm:" in src and "sql_update(Job)" not in src
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pipenv run pytest tests/test_telegram_commands.py::TestClearConfirm -v`
Expected: 4 FAIL (`ImportError: cannot import name 'clear_token_valid'`, source assertion).

- [ ] **Step 3: Implement**

Add `import time` to the bot's imports. Replace `cmd_clear` (lines 484-517) with:

```python
_CLEAR_TOKEN_TTL_SECONDS = 120


def clear_token_valid(stored: tuple[str, float] | None, token: str, now: float,
                      ttl: int = _CLEAR_TOKEN_TTL_SECONDS) -> bool:
    """Pure. The confirm button must carry the token /clear just issued, and
    be pressed within the TTL — an old card cannot wipe the fleet later."""
    if not stored:
        return False
    issued_token, issued_at = stored
    return token == issued_token and 0 <= now - issued_at <= ttl


async def _do_clear() -> tuple[int, int]:
    """Cancel every queued/deferred/running job and fail every open task.

    The old /clear body, plus two deliberate changes:
      * a jobs:cancel publish per running job so the live sessions stop instead
        of finishing into a suppressed finish (INV-9);
      * `deferred` joins the status filter (was [queued, running],
        telegram_bot.py:493). Plan-DAG children parked in `deferred` used to
        survive a /clear and be promoted later; "clear everything" should mean
        them too. Stated in the Interfaces block as a semantic change.
    """
    async with async_session() as s:
        running = await s.execute(select(Job.id).where(Job.status == JobStatus.running.value))
        running_ids = [row[0] for row in running.all()]
        result = await s.execute(
            sql_update(Job)
            .where(Job.status.in_([JobStatus.queued.value, JobStatus.deferred.value,
                                   JobStatus.running.value]))
            .values(status=JobStatus.cancelled.value, error_message="cleared by /clear")
        )
        jobs_cleared = result.rowcount or 0
        result = await s.execute(
            sql_update(Task)
            .where(Task.status.in_([TaskStatus.active.value, TaskStatus.awaiting_user.value,
                                    TaskStatus.pending_approval.value]))
            .values(status=TaskStatus.failed.value)
        )
        tasks_cleared = result.rowcount or 0
        await s.commit()
    for jid in running_ids:
        try:
            await cancel_job(jid)
        except Exception:
            logger.exception("clear: cancel publish failed", job_id=str(jid)[:8])
    await redis.delete("jobs:queue")
    return jobs_cleared, tasks_cleared


@_error_safe
async def cmd_clear(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/clear — show what would be wiped and ask for a confirm tap (spec §4.1)."""
    if await _guard(update) is None:
        return
    async with async_session() as s:
        from sqlalchemy import func as sqlfunc
        n_jobs = (await s.execute(select(sqlfunc.count()).select_from(Job).where(
            Job.status.in_([JobStatus.queued.value, JobStatus.deferred.value,
                            JobStatus.running.value])))).scalar() or 0
        n_tasks = (await s.execute(select(sqlfunc.count()).select_from(Task).where(
            Task.status.in_([TaskStatus.active.value, TaskStatus.awaiting_user.value,
                             TaskStatus.pending_approval.value])))).scalar() or 0
    token = uuid.uuid4().hex[:8]
    ctx.bot_data["clear_token"] = (token, time.time())
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(f"Yes — clear {n_jobs} job(s), {n_tasks} task(s)",
                             callback_data=f"clear_confirm:{token}"),
        InlineKeyboardButton("Abort", callback_data="clear_abort:0"),
    ]])
    await update.message.reply_text(
        f"⚠️ /clear cancels {n_jobs} queued/running job(s) and fails {n_tasks} open task(s). "
        f"Confirm within {_CLEAR_TOKEN_TTL_SECONDS} s:", reply_markup=keyboard)
```

In `_handle_button`, first rename its second parameter — the `@_error_safe` wrapper passes the context positionally, so the rename is safe and nothing else references `_` inside the function:

```python
@_error_safe
async def _handle_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
```

then extend the job-level block added in Task 7 (before the task lookup):

```python
    if action == "clear_abort":
        await query.edit_message_text("Clear aborted.")
        return
    if action == "clear_confirm":
        if not clear_token_valid(ctx.bot_data.get("clear_token"), task_prefix, time.time()):
            await query.edit_message_text("This confirm expired — send /clear again.")
            return
        ctx.bot_data.pop("clear_token", None)
        jobs_cleared, tasks_cleared = await _do_clear()
        await query.edit_message_text(f"Cleared {jobs_cleared} job(s) and {tasks_cleared} task(s).")
        return
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pipenv run pytest tests/test_telegram_commands.py -v`
Expected: all PASS.

Live check: `/clear` on an idle fleet → card with `Yes — clear 0 job(s), 0 task(s)` / `Abort`; tap Abort → "Clear aborted."; `/clear`, wait 125 s, tap Yes → "This confirm expired".

- [ ] **Step 5: CHANGELOG + commit**

Prepend to `.context/modules/gateway/CHANGELOG.md`:

```markdown
## 2026-09-25 — /clear asks first (confirm button, 120 s token)

- `cmd_clear` now previews counts and issues `clear_confirm:<token>` / `clear_abort:0`; `_do_clear` (the old body) also publishes `jobs:cancel` per running job. Pure `clear_token_valid` tested.
```

```bash
git add src/gateway/telegram_bot.py tests/test_telegram_commands.py .context/modules/gateway/CHANGELOG.md
git commit -m "feat(gateway): /clear requires a confirm button (token, 120s TTL); running jobs get a cancel publish"
```

---

### Task 10: `AskUserQuestion` leaves the default tool list


**Execution position:** 17 of 21 — previous: Task 9, next: Task 12 (see Global Constraints "Execution order").

**Files:**
- Modify: `src/registry/skills.py:46-49` (dataclass default), `:123-125` (loader default) — introduce `DEFAULT_REQUIRED_TOOLS`
- Modify: `src/runner/session.py:706-709` (generic-task default)
- Modify: `.context/modules/registry/CHANGELOG.md`, `.context/modules/runner/CHANGELOG.md`
- Test: `tests/test_default_tools.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `registry.skills.DEFAULT_REQUIRED_TOOLS: tuple[str, ...] = ("Read", "Write", "Edit", "Bash", "Glob", "Grep", "WebSearch", "WebFetch")` — the one definition used by `SkillConfig.required_tools`'s default, the loader's fallback and `session._build_options`. Skills that declare `AskUserQuestion` explicitly (7 today: new-project, project-evaluate, new-skill, research-report, restore, research-deep, self-diagnose) are unchanged — that is an open question for the owner, not this task.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_default_tools.py`:

```python
"""
AskUserQuestion is off the DEFAULT tool list (spec §4.5; TROUBLESHOOTING
'Root cause #5': nothing consumes the question, the job hangs in running).

Run: pipenv run pytest tests/test_default_tools.py -v
"""

from __future__ import annotations

import inspect

from src.config import settings
from src.registry.skills import DEFAULT_REQUIRED_TOOLS, SkillConfig, load


def test_default_list_has_no_ask_user_question():
    assert "AskUserQuestion" not in DEFAULT_REQUIRED_TOOLS
    assert DEFAULT_REQUIRED_TOOLS == ("Read", "Write", "Edit", "Bash", "Glob", "Grep",
                                      "WebSearch", "WebFetch")


def test_dataclass_default_uses_the_constant():
    assert SkillConfig(name="x", body="").required_tools == list(DEFAULT_REQUIRED_TOOLS)


def _skill(tmp_path, monkeypatch, frontmatter: str):
    # load(name) reads settings.skills_dir/<name>/SKILL.md (src/registry/skills.py:98-106).
    # `Settings.skills_dir` is a read-only @property (src/config.py:95-97) and
    # pydantic routes setattr to property.__set__ → "no setter"; patch the
    # CLASS, exactly as tests/test_registry_failclosed.py:24-27 does.
    (tmp_path / "t").mkdir()
    (tmp_path / "t" / "SKILL.md").write_text(f"---\n{frontmatter}\n---\nbody\n")
    monkeypatch.setattr(type(settings), "skills_dir", property(lambda self: tmp_path))
    return load("t")


def test_loader_fallback_uses_the_constant(tmp_path, monkeypatch):
    cfg = _skill(tmp_path, monkeypatch, "name: t\ndescription: d")
    assert cfg.required_tools == list(DEFAULT_REQUIRED_TOOLS)


def test_explicit_declaration_still_honoured(tmp_path, monkeypatch):
    cfg = _skill(tmp_path, monkeypatch,
                 "name: t\ndescription: d\nrequired_tools: [Read, AskUserQuestion]")
    assert cfg.required_tools == ["Read", "AskUserQuestion"]


def test_session_generic_default_uses_the_constant():
    from src.runner import session
    src = inspect.getsource(session._build_options)
    assert "AskUserQuestion" not in src
    assert "DEFAULT_REQUIRED_TOOLS" in src
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pipenv run pytest tests/test_default_tools.py -v`
Expected: `ImportError: cannot import name 'DEFAULT_REQUIRED_TOOLS'`.

- [ ] **Step 3: Implement**

`src/registry/skills.py` — add above `class SkillConfig`:

```python
# Default tool set for skills that do not declare `required_tools` and for the
# generic (no-skill) task. AskUserQuestion is deliberately ABSENT (P0, spec
# §4.5): nothing consumes the question headless, the job hangs in `running`
# (TROUBLESHOOTING.md "Root cause #5"). Skills that truly need it declare it.
DEFAULT_REQUIRED_TOOLS: tuple[str, ...] = (
    "Read", "Write", "Edit", "Bash", "Glob", "Grep", "WebSearch", "WebFetch",
)
```

Change the dataclass field (lines 46-49) to `required_tools: list[str] = field(default_factory=lambda: list(DEFAULT_REQUIRED_TOOLS))` and the loader fallback (lines 123-125) to `required_tools=fm.get("required_tools", list(DEFAULT_REQUIRED_TOOLS)),`.

`src/runner/session.py:706-709` — import `DEFAULT_REQUIRED_TOOLS` in the existing `from src.registry.skills import (...)` block (line 50) and replace the literal list:

```python
    tools = (skill_cfg.required_tools if skill_cfg else list(DEFAULT_REQUIRED_TOOLS))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pipenv run pytest tests/test_default_tools.py tests/test_skill_contracts.py tests/test_agents.py tests/test_registry_failclosed.py -q`
Expected: all PASS.

- [ ] **Step 5: CHANGELOGs + commit**

Prepend to `.context/modules/registry/CHANGELOG.md`:

```markdown
## 2026-09-25 — DEFAULT_REQUIRED_TOOLS constant; AskUserQuestion removed from the default list

- `src/registry/skills.py`: one `DEFAULT_REQUIRED_TOOLS` tuple (8 tools) feeds the dataclass default, the loader fallback and `session._build_options`. Skills declaring `AskUserQuestion` explicitly are untouched.
```

Prepend to `.context/modules/runner/CHANGELOG.md`:

```markdown
## 2026-09-25 — generic-task default tools from registry.DEFAULT_REQUIRED_TOOLS (no AskUserQuestion)

- `session._build_options`: the no-skill default list now imports the registry constant; headless generic tasks can no longer hang on an unanswered question.
```

```bash
git add src/registry/skills.py src/runner/session.py tests/test_default_tools.py .context/modules/registry/CHANGELOG.md .context/modules/runner/CHANGELOG.md
git commit -m "fix(registry+runner): AskUserQuestion removed from the default tool list (single DEFAULT_REQUIRED_TOOLS constant)"
```

---

### Task 11: (retired number — see Task 0) — NOT A TASK, do not dispatch

**There is no work here and no step to check off.** The reviewed spec took the Haiku 4.5 retirement swap **out of P0** (spec §9 "Shipped ahead of P0", §11 Haiku row, round-1 #50: "Standalone `server-patch` shipped ahead of P0 (four edit sites incl. the skill and the aliases)"). Its full content — `settings.utility_model`, the extracted `router_options()`/`classifier_options()`, the `haiku`/`haiku-4-5` aliases, `skills/project-update-poll/SKILL.md:4`, the two authoring docs, the dashboard option, the `test_pure_functions.py:143` update, the live "registry-less Haiku swap smoke" — lives in **Task 0** at the top of this plan and is executed, merged and deployed on its own `server-patch` PR before Task 1. The number is kept only so cross-references in Tasks 12–17 and the Alignment section stay valid.

A subagent-driven runner that dispatches one agent per checkbox-bearing heading must **skip this heading**: it has no deliverable, no commit, and its former verification step needed prod DB access an isolated worktree does not have. That step now lives where it belongs — as the **Prerequisite check** paragraph at the top of Task 1, marked host-only.

**Files:** none. **Interfaces:** see Task 0.

---

### Task 12: Daily credential canary — a ping through the runner's own SDK path with the runner's env, served-model + API-time assertion, failure → `notify send`

**Execution position:** 18 of 21 — previous: Task 10, next: Task 16 (see Global Constraints "Execution order"). **It appears in this file BEFORE Tasks 15-21 but runs after them**: `tests/test_canary.py` and `canary_options()` import `claude_env.claude_subprocess_env()`, which **Task 17** creates. A runner that walks headings in file order gets a collection error at Step 1.

- [ ] **Step 0: Prerequisite check** — `pipenv run python -c "from src.runner.claude_env import claude_subprocess_env; print('ok')"` must print `ok`. If it fails: **execute Task 17 first** (and Tasks 2 and 5 before it — the canary also needs `result_capture.served_model_violation` and `python -m src.notify send`).

Re-cut against spec §0a (last rows: "`claude -p ping` smoke through the runner's own path … using the SDK-bundled CLI from the runner venv … never the brew binary; the Keychain login stays the live credential"), §9 P0 row ("credential canary schedules (Claude via `ClaudeSdkExecutor`)"), §11 and review #64 ("canary runs through `ClaudeSdkExecutor` with the runner env"). `ClaudeSdkExecutor` is P3; the P0 stand-in is `claude_agent_sdk.query()` from the runner venv with `ClaudeAgentOptions` built the way the runner builds them (server-root cwd, plan mode, no tools, one turn) and carrying `claude_env.claude_subprocess_env()` (Task 17 — the same overlay every runner session gets), judged by the same `result_capture.served_model_violation` rule the runner applies. The canary never sees `CLAUDE_CODE_OAUTH_TOKEN`: a pass means the Keychain login the fleet runs on still serves (Global Constraints "Auth posture").

**Files:**
- Create: `src/runner/canary.py`, `scripts/credential-canary.sh`
- Modify: `scripts/install-launchd.sh:68-122` (services loop `for svc … done` → skippable), `:166-192` (`install_timer` — add the `EnvironmentVariables` block the service plists at `:96-100` already have), `:193-198` (timer calls: add the canary)
- Modify: `scripts/schedule-monitor.sh:18-21` (interpreter resolution + the collector call at line 21 — `pipenv run python -m src.runner.schedule_adherence`, the exact line that has been rc=127 on prod since 2026-09-24; it consumes the `VENV_PY` this task's plist exports, and the `pipenv run` ban test below would otherwise be red at this commit)
- Modify: `.context/modules/runner/CHANGELOG.md`, `.context/modules/hosting/CHANGELOG.md`, `.context/modules/runner/CONTEXT.md` (Paths line — `check_runner_context` goes red the moment `canary.py` exists), `.context/SYSTEM.md` (module-graph row for `canary.py`)
- Test: `tests/test_canary.py`, `tests/test_scripts_syntax.py`

**Interfaces:**
- Consumes: `result_capture.ResultCapture`, `capture_result_message`, `served_model_violation` (Task 2); `claude_env.claude_subprocess_env()` (Task 17 — execute Task 17 first); `settings.utility_model` (Task 0); `python -m src.notify send` (Task 5); `claude_agent_sdk.query`, `ClaudeAgentOptions`, `AssistantMessage`, `TextBlock`, `ResultMessage` (SDK 0.1.81).
- Produces:
  - `canary.PING_PROMPT = "Reply with exactly the word: pong"`, `canary.DEFAULT_TIMEOUT_S = 180`.
  - `canary.canary_options(model: str) -> ClaudeAgentOptions` (pure) — `cwd=settings.server_root`, `effort="low"`, `permission_mode="plan"`, `allowed_tools=[]`, `max_turns=1`, `env=claude_subprocess_env()`.
  - `async canary.run_ping(model, *, timeout_s: float = 180, query_fn=None) -> tuple[ResultCapture | None, str]` — one ping through `query_fn or claude_agent_sdk.query` (injectable for tests); `(capture, final_text)`; `capture is None` when no `ResultMessage` arrived; raises `asyncio.TimeoutError` on the ceiling.
  - `canary.evaluate_ping(capture: ResultCapture | None, final_text: str, requested_model: str) -> tuple[bool, str]` (pure) — the runner's `served_model_violation` first, then the canary-only tightening: `model_usage` must be present, `duration_api_ms > 0`, usage non-empty.
  - `canary.telemetry_record(ok, detail, requested_model, now) -> dict`.
  - `python -m src.runner.canary [--model <id>] [--telemetry <path>] [--timeout <s>]` — exit 0 ok / 1 the ping ran and failed the assertion / 2 the SDK could not run at all (CLI missing, transport error, timeout); prints the one-line verdict. Default model = `settings.utility_model` (`claude-sonnet-4-6`).
  - `scripts/credential-canary.sh [model]` — launchd label `com.assistant.credential-canary`, daily 06:50, telemetry at `volumes/telemetry/credential_canary.json`, log `volumes/logs/credential-canary.log`. **Never `pipenv run`** (Global Constraints): the interpreter is `VENV_PY` — `${VENV_PY}` from the timer plist, else `$PROJECT_DIR/.venv/bin/python` when an in-project venv exists, else `command -v python` (a `pipenv shell`) — guarded with `"$VENV_PY" -c 'import src.config'`; a missing interpreter is itself a FAIL (curl DM, exit 1).
  - `scripts/install-launchd.sh timers-only` — installs/refreshes only the timer plists (no runner/web/bot restart). `install_timer` now writes an `EnvironmentVariables` dict with `PATH` (`${VENV_DIR}/bin` first, then Homebrew and the system dirs) **and** `VENV_PY=${VENV_DIR}/bin/python`, plus `DISABLE_ERROR_REPORTING=1` / `DISABLE_TELEMETRY=1` (the two keys Task 17 puts in the service plists, so the canary timer's env matches the runner's; never `CLAUDE_CODE_OAUTH_TOKEN`). `PATH` and `VENV_PY` are both needed: launchd's `bash -lc` runs `/etc/profile` → `path_helper`, which moves every non-system PATH entry to the END (verified on this host: `${VENV_DIR}/bin` lands after `/opt/homebrew/bin`), so `VENV_PY` is the reliable handle and PATH only helps `command -v` fallbacks. `timers-only` therefore also re-renders the three existing timers (`backup`, `healthcheck-all`, `schedule-monitor`) — which is exactly what un-breaks `schedule-monitor` on prod (dead since 2026-09-24 with `pipenv: command not found` / `run rc=127`).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_canary.py`:

```python
"""
Credential canary (P0; spec §0a last rows, §11, review #64): the ping goes
through the SDK path the runner uses. These tests feed the message loop a
fake `query` that yields the SDK's own message dataclasses — no subprocess,
no network (constructing the dataclasses is not a "live SDK" call).

Run: pipenv run pytest tests/test_canary.py -v
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock

from src.runner import canary
from src.runner.canary import canary_options, evaluate_ping, run_ping, telemetry_record
from src.runner.result_capture import capture_result_message

REPO = Path(__file__).resolve().parent.parent
USAGE = {"input_tokens": 12, "output_tokens": 3,
         "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}


def _result(**over) -> ResultMessage:
    base = dict(subtype="success", duration_ms=2400, duration_api_ms=1900, is_error=False,
                num_turns=1, session_id="s", total_cost_usd=0.0031, usage=USAGE, result="pong",
                model_usage={"claude-sonnet-4-6": {"inputTokens": 12, "outputTokens": 3}})
    base.update(over)
    return ResultMessage(**base)


def _fake_query(messages):
    """An async generator standing in for claude_agent_sdk.query."""
    async def q(*, prompt, options):
        q.calls.append((prompt, options))
        for m in messages:
            yield m
    q.calls = []
    return q


GOOD = [AssistantMessage(content=[TextBlock(text="pong")], model="claude-sonnet-4-6"), _result()]


class TestOptions:
    def test_runner_conventions_and_env_overlay(self):
        o = canary_options("claude-sonnet-4-6")
        assert o.model == "claude-sonnet-4-6" and o.max_turns == 1
        assert o.permission_mode == "plan" and o.allowed_tools == []
        # Task 17's overlay: telemetry off, exactly like every runner session.
        assert o.env == {"DISABLE_ERROR_REPORTING": "1", "DISABLE_TELEMETRY": "1"}
        assert "CLAUDE_CODE_OAUTH_TOKEN" not in o.env      # proves the Keychain login, never the token


class TestRunPing:
    async def test_collects_text_and_capture(self):
        q = _fake_query(GOOD)
        cap, text = await run_ping("claude-sonnet-4-6", query_fn=q)
        assert text == "pong" and cap is not None and cap.model_served == "claude-sonnet-4-6"
        assert q.calls[0][0] == canary.PING_PROMPT

    async def test_no_result_message_gives_none(self):
        cap, text = await run_ping("claude-sonnet-4-6", query_fn=_fake_query(GOOD[:1]))
        assert cap is None and text == "pong"

    async def test_timeout_propagates(self):
        async def slow(*, prompt, options):
            await asyncio.sleep(1)
            yield GOOD[1]
        with pytest.raises(asyncio.TimeoutError):
            await run_ping("claude-sonnet-4-6", timeout_s=0.05, query_fn=slow)


class TestEvaluatePing:
    def _cap(self, **over):
        return capture_result_message(_result(**over))

    def test_good_ping_passes(self):
        ok, detail = evaluate_ping(self._cap(), "pong", "claude-sonnet-4-6")
        assert ok and "served=claude-sonnet-4-6" in detail

    def test_no_result_message_fails(self):
        ok, detail = evaluate_ping(None, "", "claude-sonnet-4-6")
        assert not ok and "no ResultMessage" in detail

    def test_is_error_fails(self):
        ok, detail = evaluate_ping(self._cap(is_error=True, result="Not logged in"), "",
                                   "claude-sonnet-4-6")
        assert not ok and "Not logged in" in detail

    def test_wrong_model_fails(self):
        ok, detail = evaluate_ping(self._cap(), "pong", "claude-opus-5-5")
        assert not ok and "claude-opus-5-5" in detail

    def test_date_suffixed_served_passes(self):
        ok, _ = evaluate_ping(self._cap(model_usage={"claude-sonnet-4-6-20260101": {}}),
                              "pong", "claude-sonnet-4-6")
        assert ok

    def test_missing_model_usage_fails(self):
        # The runner tolerates an absent model_usage on a short chat job
        # (Review Focus 5); a credential PROBE must not.
        ok, detail = evaluate_ping(self._cap(model_usage=None), "pong", "claude-sonnet-4-6")
        assert not ok and "model_usage" in detail

    def test_zero_api_time_fails(self):
        ok, detail = evaluate_ping(self._cap(duration_api_ms=0), "pong", "claude-sonnet-4-6")
        assert not ok and "duration_api_ms" in detail

    def test_zero_usage_fails(self):
        zero = {k: 0 for k in USAGE}
        ok, detail = evaluate_ping(self._cap(usage=zero), "pong", "claude-sonnet-4-6")
        assert not ok and "usage" in detail


class TestTelemetryAndMain:
    def test_telemetry_record(self):
        now = datetime(2026, 9, 25, 6, 50, tzinfo=timezone.utc)
        rec = telemetry_record(True, "ok", "claude-sonnet-4-6", now)
        assert rec == {"ok": True, "detail": "ok", "requested_model": "claude-sonnet-4-6",
                       "checked_at": "2026-09-25T06:50:00+00:00"}

    def test_main_ok_writes_telemetry(self, monkeypatch, tmp_path):
        monkeypatch.setattr(canary, "query", _fake_query(GOOD))
        out = tmp_path / "canary.json"
        assert canary.main(["--model", "claude-sonnet-4-6", "--telemetry", str(out)]) == 0
        assert json.loads(out.read_text())["ok"] is True

    def test_main_failure_exit_1(self, monkeypatch):
        monkeypatch.setattr(canary, "query",
                            _fake_query([GOOD[0], _result(is_error=True, result="Not logged in")]))
        assert canary.main(["--model", "claude-sonnet-4-6"]) == 1

    def test_main_sdk_crash_exit_2(self, monkeypatch):
        async def boom(*, prompt, options):
            raise RuntimeError("Claude Code not found")
            yield  # noqa: unreachable — makes this an async generator
        monkeypatch.setattr(canary, "query", boom)
        assert canary.main(["--model", "claude-sonnet-4-6"]) == 2

    def test_main_defaults_to_utility_model(self, monkeypatch):
        from src.config import settings
        q = _fake_query(GOOD)
        monkeypatch.setattr(canary, "query", q)
        canary.main([])
        assert q.calls[0][1].model == settings.utility_model

    def test_canary_never_reads_the_setup_token(self):
        # Review Focus 8 / Global Constraints "Auth posture": the canary must
        # prove the Keychain login. Neither file may mention the token or --bare.
        for rel in ("src/runner/canary.py", "scripts/credential-canary.sh"):
            src = (REPO / rel).read_text()
            assert "CLAUDE_CODE_OAUTH_TOKEN" not in src, rel
            assert "--bare" not in src, rel
```

Create `tests/test_scripts_syntax.py`:

```python
"""
Bash scripts shipped by P0: syntax-checked with `bash -n` (local, no network)
plus the invariants the timer scripts must never break — chiefly: NO
`pipenv run` in anything launchd runs. pipenv lives in ~/.pyenv/shims, which
launchd's `bash -lc` never sees (no ~/.bash_profile; ~/.zprofile is zsh-only);
prod's schedule-monitor.log shows `pipenv: command not found` / rc=127 since
2026-09-24. `bash -n` cannot catch that; these greps can.

Run: pipenv run pytest tests/test_scripts_syntax.py -v
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = [
    "scripts/credential-canary.sh",
    "scripts/install-launchd.sh",
    "scripts/healthcheck-all.sh",
    "scripts/schedule-monitor.sh",
    "scripts/backup.sh",
]
# Everything a launchd timer executes (install-launchd.sh install_timer calls).
TIMER_SCRIPTS = [
    "scripts/credential-canary.sh",
    "scripts/healthcheck-all.sh",
    "scripts/schedule-monitor.sh",
    "scripts/backup.sh",
]


@pytest.mark.parametrize("rel", SCRIPTS)
def test_bash_syntax(rel):
    r = subprocess.run(["bash", "-n", str(REPO / rel)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


@pytest.mark.parametrize("rel", TIMER_SCRIPTS)
def test_timer_scripts_never_use_pipenv_run(rel):
    src = (REPO / rel).read_text()
    assert "pipenv run" not in src, f"{rel}: launchd has no pipenv on PATH (rc=127)"


@pytest.mark.parametrize("rel", ["scripts/credential-canary.sh", "scripts/schedule-monitor.sh"])
def test_python_timer_scripts_resolve_and_guard_the_interpreter(rel):
    # healthcheck-all.sh joins this list in Task 13 (it gains its python call there).
    src = (REPO / rel).read_text()
    assert 'VENV_PY="${VENV_PY:-' in src, rel                  # plist env first, then fallbacks
    assert "import src.config" in src, rel                     # guard: never run on a random python


def test_canary_script_invariants():
    src = (REPO / "scripts/credential-canary.sh").read_text()
    assert "--bare" not in src                    # spec §0a: never --bare (OAuth never read)
    assert "unset ANTHROPIC_API_KEY" in src       # INV-3
    assert "-m src.notify send" in src            # via "$VENV_PY", never `pipenv run python`
    assert '-m src.runner.canary --model "$MODEL"' in src   # the ping runs INSIDE the SDK, not a raw `claude -p`
    assert "claude -p" not in src and "--output-format" not in src   # no brew-binary path left (spec §0a)
    assert "CLAUDE_CODE_OAUTH_TOKEN" not in src  # proves the Keychain login, never the sealed token


def test_installer_has_canary_timer_and_timers_only_mode():
    src = (REPO / "scripts/install-launchd.sh").read_text()
    assert 'install_timer "credential-canary" "scripts/credential-canary.sh"' in src
    assert "timers-only" in src


def test_installer_timer_plists_carry_venv_env():
    # The timer plists must export the interpreter like the service plists do;
    # `bash -lc` → path_helper reorders PATH, so VENV_PY is the reliable handle.
    src = (REPO / "scripts/install-launchd.sh").read_text()
    timer_fn = src.split("install_timer() {", 1)[1].split("\n}\n", 1)[0]
    assert "<key>EnvironmentVariables</key>" in timer_fn
    assert "<key>VENV_PY</key><string>${VENV_DIR}/bin/python</string>" in timer_fn
    assert "<key>PATH</key>" in timer_fn and "${VENV_DIR}/bin:" in timer_fn
    # Same telemetry posture as the runner's service plist (Task 17; spec §2.4/§3).
    assert "<key>DISABLE_ERROR_REPORTING</key><string>1</string>" in timer_fn
    assert "<key>DISABLE_TELEMETRY</key><string>1</string>" in timer_fn


def test_schedule_monitor_collector_runs_on_venv_python():
    # The line that has been `pipenv: command not found` on prod since 2026-09-24.
    src = (REPO / "scripts/schedule-monitor.sh").read_text()
    assert '"$VENV_PY" -m src.runner.schedule_adherence' in src
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pipenv run pytest tests/test_canary.py tests/test_scripts_syntax.py -v`
Expected: `ModuleNotFoundError: No module named 'src.runner.canary'`; syntax tests fail on the missing script, the installer assertions (no `timers-only`, no `EnvironmentVariables` in `install_timer`), `test_timer_scripts_never_use_pipenv_run[scripts/schedule-monitor.sh]`, `test_python_timer_scripts_resolve_and_guard_the_interpreter[scripts/schedule-monitor.sh]` and `test_schedule_monitor_collector_runs_on_venv_python` (line 21 is `pipenv run python -m src.runner.schedule_adherence` today — repaired in Step 5; `healthcheck-all.sh` and `backup.sh` contain no `pipenv` and already pass the ban).

- [ ] **Step 3: Implement `src/runner/canary.py`**

```python
"""
Credential canary (P0; spec §0a last rows, §9 P0 row, §11 "claude -p ping smoke
… through the runner's executor path", review #64).

scripts/credential-canary.sh runs `python -m src.runner.canary` once a day
under launchd. The ping goes through the SAME path the runner uses — the
claude_agent_sdk in the runner venv (its bundled CLI, the Keychain login),
a ClaudeAgentOptions built with the runner's one-shot conventions
(llm_router.router_options) and the runner's `claude_subprocess_env()`
overlay — and is judged by the SAME rule the runner applies to every
session (result_capture.served_model_violation), tightened for a probe.
P3 swaps the `query()` call for `ClaudeSdkExecutor.start(spec)`; nothing
else changes. Never the brew `claude`; never the CLI's bare mode (it skips
OAuth — the flag name is kept out of this file on purpose, the tests grep
for it); never the sealed setup-token — a pass means the Keychain login
the fleet runs on serves.

Exit codes: 0 ok · 1 the ping ran and failed the assertion · 2 the SDK
could not run at all (CLI missing, transport error, timeout) — also an alert.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import AsyncIterator, Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    query,
)

from src.config import settings
from src.runner.result_capture import (
    ResultCapture,
    capture_result_message,
    served_model_violation,
)
from src.runner.claude_env import claude_subprocess_env

PING_PROMPT = "Reply with exactly the word: pong"
DEFAULT_TIMEOUT_S = 180


def canary_options(model: str) -> ClaudeAgentOptions:
    """The runner's conventions for a one-shot utility session (cf.
    llm_router.router_options): server_root cwd, low effort, plan mode, no
    tools, one turn, and the runner's subprocess env overlay (telemetry off).
    No `env` key beyond that overlay — in particular never the setup-token."""
    return ClaudeAgentOptions(
        cwd=str(settings.server_root),
        model=model,
        effort="low",
        permission_mode="plan",
        allowed_tools=[],
        max_turns=1,
        env=claude_subprocess_env(),
    )


async def run_ping(
    model: str,
    *,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    query_fn: Callable[..., AsyncIterator[Any]] | None = None,
) -> tuple[ResultCapture | None, str]:
    """One ping through the SDK. Returns (capture, final_text); capture is
    None when no ResultMessage arrived (the CLI died before answering).
    `query_fn` is resolved at call time so tests can monkeypatch `query`."""
    q = query_fn or query
    capture: ResultCapture | None = None
    chunks: list[str] = []

    async def _consume() -> None:
        nonlocal capture
        async for message in q(prompt=PING_PROMPT, options=canary_options(model)):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        chunks.append(block.text)
            elif isinstance(message, ResultMessage):
                capture = capture_result_message(message)

    await asyncio.wait_for(_consume(), timeout=timeout_s)
    return capture, "\n".join(chunks).strip()


def evaluate_ping(capture: ResultCapture | None, final_text: str,
                  requested_model: str) -> tuple[bool, str]:
    """Pure. The runner's served-model rule first, then the canary-only
    tightening: a probe must see model_usage, real API time and non-zero
    usage. The "absent model_usage" leniency the runner grants short chat
    jobs (Review Focus 3/5) does not apply to a ping whose whole point is
    proving the credential served."""
    if capture is None:
        return False, "no ResultMessage (CLI exited without a result — logged out? unknown model?)"
    if capture.is_error:
        err = capture.result_text or "; ".join(capture.errors)
        return False, f"is_error ({capture.subtype}): {err[:200] or 'no detail'}"
    violation = served_model_violation(capture, requested_model, final_text)
    if violation:
        return False, violation
    if not capture.model_usage:
        return False, "model_usage missing (unknown model id? logged out?)"
    if (capture.duration_api_ms or 0) <= 0:
        return False, "duration_api_ms is 0 (no API call happened)"
    if capture.usage_empty:
        return False, "usage all-zero"
    total = (capture.input_tokens + capture.output_tokens
             + capture.cache_read_tokens
             + capture.cache_write_1h_tokens + capture.cache_write_5m_tokens)
    return True, f"ok served={capture.model_served} api_ms={capture.duration_api_ms} tokens={total}"


def telemetry_record(ok: bool, detail: str, requested_model: str, now: datetime) -> dict[str, Any]:
    return {"ok": ok, "detail": detail, "requested_model": requested_model,
            "checked_at": now.isoformat()}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m src.runner.canary")
    p.add_argument("--model", default=settings.utility_model)
    p.add_argument("--telemetry", default=None, help="write the verdict JSON here")
    p.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S)
    args = p.parse_args(argv)
    try:
        capture, text = asyncio.run(run_ping(args.model, timeout_s=args.timeout, query_fn=query))
    except asyncio.TimeoutError:
        ok, detail, rc = False, f"canary timeout after {args.timeout:g}s", 2
    except Exception as exc:  # noqa: BLE001 — CLINotFoundError, ProcessError, transport errors
        ok, detail, rc = False, f"sdk failed to run: {type(exc).__name__}: {str(exc)[:160]}", 2
    else:
        ok, detail = evaluate_ping(capture, text, args.model)
        rc = 0 if ok else 1
    if args.telemetry:
        try:
            out = Path(args.telemetry)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(telemetry_record(
                ok, detail, args.model, datetime.now(timezone.utc)), indent=2))
        except OSError as exc:
            print(f"telemetry write failed: {exc}", file=sys.stderr)
    print(detail)
    return rc


if __name__ == "__main__":
    sys.exit(main())
```

(`query_fn=query` in `main` is looked up in the module namespace at call time, which is what lets the tests monkeypatch `canary.query`; the `run_ping` default is `None` for the same reason.)

- [ ] **Step 4: Write `scripts/credential-canary.sh`**

```bash
#!/usr/bin/env bash
# scripts/credential-canary.sh — daily Claude subscription credential canary.
#
# OUT-OF-BAND by design (same doctrine as healthcheck-all.sh): if the Max
# login lapses, the runner's first job of the day fails only after burning a
# slot and an escalation. This probe fails BEFORE that and DMs the owner via
# `python -m src.notify send` (direct Telegram HTTP first, outbox row second),
# with the healthcheck-all.sh curl path as the last-resort fallback.
# The ping itself runs INSIDE `python -m src.runner.canary` — through the
# claude_agent_sdk in the runner venv (bundled CLI, Keychain login), the
# runner's option conventions and env overlay, the runner's served-model rule
# (spec §0a/§11, review #64). Never the brew `claude`, never the CLI's bare
# mode (it skips OAuth), never the sealed setup-token: a pass means the
# Keychain login serves. (The literal flag name is deliberately absent here —
# tests/test_scripts_syntax.py greps this file for it.)
#
# launchd: com.assistant.credential-canary, daily 06:50 (install-launchd.sh).
# Usage: bash scripts/credential-canary.sh [model]     (default claude-sonnet-4-6)
set -uo pipefail
export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
unset ANTHROPIC_API_KEY        # INV-3: subscription auth only — never API billing

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG="$PROJECT_DIR/volumes/logs/credential-canary.log"
TELEMETRY="$PROJECT_DIR/volumes/telemetry/credential_canary.json"
MODEL="${1:-${CANARY_MODEL:-claude-sonnet-4-6}}"
mkdir -p "$(dirname "$LOG")" "$(dirname "$TELEMETRY")"
cd "$PROJECT_DIR"

# Interpreter: NEVER `pipenv run` here — pipenv is a ~/.pyenv shim launchd's
# `bash -lc` cannot see (rc=127; prod schedule-monitor.log 2026-09-24). The
# timer plist exports VENV_PY (install-launchd.sh); an in-project .venv or a
# `pipenv shell` covers manual runs. Guard: the venv must import the server.
VENV_PY="${VENV_PY:-}"
[[ -z "$VENV_PY" && -x "$PROJECT_DIR/.venv/bin/python" ]] && VENV_PY="$PROJECT_DIR/.venv/bin/python"
[[ -z "$VENV_PY" ]] && VENV_PY="$(command -v python || true)"

notify_fail() {   # $1 = detail
    local msg token chat_ids chat_id
    msg="🔑 Claude credential canary FAILED on $(hostname -s): $1 (model $MODEL). Fix on the Mini: \`claude login\` (Max, Keychain — the fleet's only credential), then re-run scripts/credential-canary.sh."
    if [[ -n "$VENV_PY" ]] && "$VENV_PY" -m src.notify send --kind credential_canary --severity critical \
            --text "$msg" >> "$LOG" 2>&1; then
        echo "$(date -u +%FT%TZ) ALERT sent via notify" >> "$LOG"
        return 0
    fi
    # Fallback: the notify CLI itself is broken → direct curl (healthcheck-all.sh pattern).
    token=$(grep -E '^TELEGRAM_BOT_TOKEN=' "$PROJECT_DIR/.env" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'" || true)
    chat_ids=$(grep -E '^TELEGRAM_ALLOWED_CHAT_IDS=' "$PROJECT_DIR/.env" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'" || true)
    chat_id=$(printf '%s' "$chat_ids" | cut -d, -f1 | tr -d '[:space:]')
    if [[ -z "$token" || -z "$chat_id" ]]; then
        echo "$(date -u +%FT%TZ) WARN alert skipped: telegram creds missing in .env" >> "$LOG"
        return 0
    fi
    curl -sf --max-time 10 "https://api.telegram.org/bot${token}/sendMessage" \
        --data-urlencode "chat_id=${chat_id}" --data-urlencode "text=${msg}" > /dev/null 2>&1 \
        && echo "$(date -u +%FT%TZ) ALERT sent via curl fallback" >> "$LOG" \
        || echo "$(date -u +%FT%TZ) WARN alert failed (telegram unreachable?)" >> "$LOG"
}

# The venv must exist and import the server before anything else is trusted:
# the SDK (and its bundled CLI) live there — the runner's path, never the
# brew `claude` (spec §0a) — and `src.runner.canary` needs the server config.
if [[ -z "$VENV_PY" ]] || ! "$VENV_PY" -c 'import src.config, claude_agent_sdk' 2>>"$LOG"; then
    echo "$(date -u +%FT%TZ) FAIL venv python not found or SDK missing (VENV_PY='${VENV_PY:-}')" >> "$LOG"
    notify_fail "venv python not found / claude_agent_sdk missing — reinstall the timer with scripts/install-launchd.sh timers-only"
    exit 1
fi

# One ping through the runner's own SDK path (options, env overlay and the
# served-model rule live in src/runner/canary.py; 180 s ceiling inside).
# rc 0 ok · 1 ran and failed the assertion · 2 the SDK could not run at all.
verdict=$("$VENV_PY" -m src.runner.canary --model "$MODEL" --telemetry "$TELEMETRY" --timeout 180 2>>"$LOG")
vrc=$?
echo "$(date -u +%FT%TZ) verdict rc=$vrc $verdict" >> "$LOG"
if (( vrc != 0 )); then
    notify_fail "${verdict:-canary produced no verdict (rc=$vrc)}"
    exit 1
fi
exit 0
```

Then `chmod +x scripts/credential-canary.sh`.

- [ ] **Step 5: `install-launchd.sh` — `timers-only` mode, timer env block, the canary timer**

After the line `[ "${1:-}" = "uninstall" ] && uninstall` (line 61) add:

```bash
# `timers-only`: (re)install only the launchd TIMERS below without touching the
# runner/web/bot services (which unload/load would restart). Used when a new
# timer lands (credential canary, 2026-09-25) on a busy fleet. It re-renders
# the existing timers too — that is what gives backup/healthcheck-all/
# schedule-monitor the EnvironmentVariables block below on prod.
TIMERS_ONLY=0
[ "${1:-}" = "timers-only" ] && TIMERS_ONLY=1
```

Wrap the services loop: keep lines 68-122 (`for svc in "${SERVICES[@]}"; do` through its `done`) byte-identical, indented one level, between these two wrapper lines:

```bash
if (( ! TIMERS_ONLY )); then
```

```bash
fi
```

In `install_timer` (lines 166-192), the plist it writes has no `EnvironmentVariables` at all — unlike the service plists at lines 96-100 — which is why every timer script that calls python has been dead under launchd. Insert, between the `<key>WorkingDirectory</key><string>${PROJECT_DIR}</string>` line and the `$3` line:

```bash
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>${VENV_DIR}/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    <key>VENV_PY</key><string>${VENV_DIR}/bin/python</string>
    <key>DISABLE_ERROR_REPORTING</key><string>1</string>
    <key>DISABLE_TELEMETRY</key><string>1</string>
  </dict>
```

(The two `DISABLE_*` keys mirror the service plists — Task 17 adds them there — so a timer's Claude subprocess has the runner's posture; no credential key is ever written here. `VENV_DIR` is already computed at line 33. `VENV_PY` is the handle the scripts use: `bash -lc` sources `/etc/profile` → `path_helper`, which rebuilds PATH from `/etc/paths` and appends the plist's entries AFTER the system dirs — verified on this host — so `${VENV_DIR}/bin` is never actually first and PATH alone would be a coincidence, not a contract.)

`scripts/schedule-monitor.sh` — the first consumer of the new env block. **First move `cd "$PROJECT_DIR"` (line 20) up so it runs BEFORE the interpreter block**, then insert the block after it. This ordering is load-bearing: the editable install is inert on this host (the macOS hidden-`.pth` gotcha), so `"$VENV_PY" -c 'import src.config'` only succeeds from the project root — verified: `cd /tmp && <venv>/bin/python -c "import src.config"` → `ModuleNotFoundError: No module named 'src'`, while `__editable__.ai_server-0.1.0.pth` is present in site-packages. Under launchd the plist's `cd "${PROJECT_DIR}" && bash …` hides it, but a manual run from any other directory would blank `VENV_PY`, log `run rc=127 venv python not found (VENV_PY unset; reinstall timers)` and `exit 0` — the watchdog goes dark while blaming the timer install. (`credential-canary.sh` and `alembic-current-check.sh` already `cd` before their guards; `healthcheck-all.sh` has no `cd` at all, so Task 13 uses the subshell form there.)

So the head of the file becomes `ALERT_INTERVAL=43200` → `cd "$PROJECT_DIR"` → the block below → the collector call, and `tests/test_scripts_syntax.py` gains `assert src.index('cd "$PROJECT_DIR"') < src.index('VENV_PY="${VENV_PY:-')`:

```bash
# Interpreter: NEVER `pipenv run` here — pipenv is a ~/.pyenv shim launchd's
# `bash -lc` cannot see (this script logged `pipenv: command not found` /
# `run rc=127` on prod from 2026-09-24 until this fix). The timer plist
# exports VENV_PY (install-launchd.sh); .venv / `pipenv shell` cover manual
# runs. The guard makes sure the interpreter can import the server.
VENV_PY="${VENV_PY:-}"
[[ -z "$VENV_PY" && -x "$PROJECT_DIR/.venv/bin/python" ]] && VENV_PY="$PROJECT_DIR/.venv/bin/python"
[[ -z "$VENV_PY" ]] && VENV_PY="$(command -v python || true)"
if [[ -n "$VENV_PY" ]] && ! "$VENV_PY" -c 'import src.config' 2>/dev/null; then
    echo "$(date -u +%FT%TZ) WARN venv python unusable ($VENV_PY); collector needs the venv" >> "$LOG"
    VENV_PY=""
fi
```

then replace line 21, `out=$(pipenv run python -m src.runner.schedule_adherence 2>>"$LOG")`, with:

```bash
if [[ -z "$VENV_PY" ]]; then
    echo "$(date -u +%FT%TZ) run rc=127 venv python not found (VENV_PY unset; reinstall timers)" >> "$LOG"
    exit 0
fi
out=$("$VENV_PY" -m src.runner.schedule_adherence 2>>"$LOG")
```

(`send_dm()` in the same file is Task 13's; it still contains only curl at this commit, so the `pipenv run` ban already holds for it.)

After the `install_timer "schedule-monitor" …` call (lines 197-198) add:

```bash
# Daily Claude credential canary (P0, spec §6): `claude -p ping` + served-model
# assertion; failure DMs via `python -m src.notify send`.
install_timer "credential-canary" "scripts/credential-canary.sh" \
  "<key>StartCalendarInterval</key><dict><key>Hour</key><integer>6</integer><key>Minute</key><integer>50</integer></dict>"
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `pipenv run pytest tests/test_canary.py tests/test_scripts_syntax.py -v`
Expected: all PASS.

Live run (one real ping on the dev box; costs one tiny Max call) — run it the way launchd will, i.e. with NO shell profile and only the plist's environment, so a `pipenv`/PATH regression cannot hide behind your interactive shell:
`VENV=$(pipenv --venv); env -i HOME="$HOME" PATH="$VENV/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin" VENV_PY="$VENV/bin/python" /bin/bash -lc "cd '$PWD' && bash scripts/credential-canary.sh"; echo rc=$?; cat volumes/telemetry/credential_canary.json`
Expected: `rc=0`, telemetry `"ok": true, "detail": "ok served=claude-sonnet-4-6… api_ms=… tokens=…"`, and `grep -c 'command not found' volumes/logs/credential-canary.log` → `0`. Negative check (same `env -i` prefix): `… bash scripts/credential-canary.sh claude-does-not-exist-9; echo rc=$?` → `rc=1` (the pinned CLI answers an unknown id with the silent-empty shape, which `evaluate_ping` rejects) and a `🔑 Claude credential canary FAILED` DM arrives (row `credential_canary|sent` in `notifications`). Interpreter-missing check: `env -i HOME="$HOME" PATH=/usr/bin:/bin /bin/bash -lc "cd '$PWD' && bash scripts/credential-canary.sh"; echo rc=$?` → `rc=1`, log line `FAIL venv python not found`, DM via the curl fallback. Credential-posture check (the spec §0a P0 exit test, also runbook §7): `plutil -p ~/Library/LaunchAgents/com.assistant.credential-canary.plist | grep -c CLAUDE_CODE_OAUTH_TOKEN` → `0` and `grep -c CLAUDE_CODE_OAUTH_TOKEN src/runner/canary.py scripts/credential-canary.sh` → `0` for both files — the pass above was produced by the Keychain login.

- [ ] **Step 7: Docs the lint gate needs, CHANGELOGs, commit**

`check_runner_context` fails as soon as `src/runner/canary.py` exists unless the runner CONTEXT.md names it, and `canary.py` imports `src.config`, `src.runner.result_capture` and `src.runner.claude_env` (all graph rows — `claude_env` since Task 17), so both doc edits ride this commit:

- `.context/modules/runner/CONTEXT.md`: append `` , `src/runner/canary.py` `` to the `**Paths:**` line.
- `.context/SYSTEM.md` module graph, insert after the `src/runner/result_capture.py` row:

```markdown
| `src/runner/canary.py` | Credential canary through the runner's SDK path (`python -m src.runner.canary`): runner option conventions + env overlay + served-model rule | config, runner.result_capture, runner.claude_env, claude_agent_sdk | scripts/credential-canary.sh |
```

Run: `pipenv run pytest tests/test_doc_lint.py -q && pipenv run python scripts/lint_docs.py` → Expected: PASS and `All clean!`.

Prepend to `.context/modules/runner/CHANGELOG.md`:

```markdown
## 2026-09-25 — canary.py: credential canary through the runner's SDK path + `python -m src.runner.canary`

- `src/runner/canary.py` (`canary_options`, `run_ping`, `evaluate_ping`, `telemetry_record`, `main`); consumed by `scripts/credential-canary.sh`. The ping runs through `claude_agent_sdk.query()` in the runner venv with the runner's one-shot option conventions and `claude_subprocess_env()` overlay, and is judged by `result_capture.served_model_violation` plus the probe-only tightening (model_usage present, API time > 0, usage non-empty). Never the brew CLI, never `--bare`, never `CLAUDE_CODE_OAUTH_TOKEN` (spec §0a/§11, review #64). P3 swaps `query()` for `ClaudeSdkExecutor`. Runner `CONTEXT.md` Paths line + `SYSTEM.md` graph row added in the same commit (lint gate).
```

Prepend to `.context/modules/hosting/CHANGELOG.md`:

```markdown
## 2026-09-25 — credential-canary.sh (daily 06:50 timer); install-launchd.sh timers-only + timer plists get PATH/VENV_PY + telemetry-off keys

- `scripts/credential-canary.sh`: one ping via `"$VENV_PY" -m src.runner.canary --model … --telemetry …` (the SDK in the runner venv — no raw `claude -p`, no brew binary), failure → `"$VENV_PY" -m src.notify send` (curl fallback). Never `--bare`; `unset ANTHROPIC_API_KEY`; never `pipenv run`; never the setup-token.
- `scripts/install-launchd.sh`: new `com.assistant.credential-canary` timer; `timers-only` argument installs/re-renders timers without restarting runner/web/bot; `install_timer` now writes `EnvironmentVariables` (`PATH` with `${VENV_DIR}/bin`, `VENV_PY`, `DISABLE_ERROR_REPORTING=1`, `DISABLE_TELEMETRY=1`) like the service plists.
- `scripts/schedule-monitor.sh`: collector runs on `"$VENV_PY"` (was `pipenv run python` — rc=127 under launchd on prod since 2026-09-24); `send_dm` is changed in Task 13.
- **Gotchas discovered**: the timer plists never had an env block, and `pipenv` is a `~/.pyenv/shims` entry that launchd's `bash -lc` cannot see — `schedule-monitor` has logged `pipenv: command not found` / `run rc=127` on prod since 2026-09-24. `bash -n` passes such a script; `tests/test_scripts_syntax.py` now greps for `pipenv run` and the `VENV_PY` guard instead. `bash -lc` also runs `path_helper`, which moves the plist's PATH entries behind the system dirs — hence the explicit `VENV_PY`. Prod needs `bash scripts/install-launchd.sh timers-only` after the deploy (runbook §6) for the fix to take effect there.
```

```bash
git add src/runner/canary.py scripts/credential-canary.sh scripts/install-launchd.sh scripts/schedule-monitor.sh tests/test_canary.py tests/test_scripts_syntax.py .context/modules/runner/CHANGELOG.md .context/modules/hosting/CHANGELOG.md .context/modules/runner/CONTEXT.md .context/SYSTEM.md
git commit -m "feat(ops): daily Claude credential canary through the runner's SDK path (served-model/API-time assertion → notify send); install-launchd timers-only + timer env block (VENV_PY, telemetry off); schedule-monitor off pipenv (rc=127 under launchd)"
```

---

### Task 13: Ops hygiene — atlas dump + sealed secrets + the 60-day R2 retention rule in `backup.sh`, `restore-drill.sh`, alerters call `notify send`, owner runbook, the D1 displacement

**Execution position:** 20 of 21 — previous: Task 16, next: Task 14 (see Global Constraints "Execution order").

**Files:**
- Modify: `scripts/backup.sh:20-33` (dumps + config snapshot), `:46-59` (the rclone block **gains the 60-day retention rule** — spec §9 P0 ops-debt cell, §12a row 4, round-2 #50; today `:59` reads "# 7. No retention cap locally — 2TB SSD, keep everything" and the bucket grows one tarball per day forever, which is what round 2 flagged when it qualified R2's "free" as "free ≤ 10 GB-month, payment method required, retention rule 60 d")
- Create: `scripts/restore-drill.sh`, `docs/runbooks/2026-09-25-p0-ops-hygiene.md`
- Modify: `scripts/healthcheck-all.sh:16` (interpreter resolution + `notify_send` inserted after `LOG=`), `:127-134` (runner-down `if curl … fi`), `:180-185` (swing `if curl … fi`); `scripts/schedule-monitor.sh` `send_dm()` (lines 32-43 before Task 12's insertions — locate by name; the interpreter block and the line-21 collector repair already landed in Task 12)
- Modify: `.context/modules/hosting/CHANGELOG.md`
- Test: `tests/test_scripts_syntax.py` (append)

**Interfaces:**
- Consumes: `python -m src.notify send` (Task 5); the `VENV_PY` contract from Task 12 (timer plist env, `.venv` fallback, `command -v python` fallback, `import src.config` guard).
- Produces:
  - `backup-<date>.tar.gz` now also contains `atlas.sql` (when the `atlas` DB exists) and `secrets.tar.enc` (AES-256-CBC, PBKDF2 200k iters, key file `~/.config/ai-server/backup-seal.key`, override `BACKUP_SEAL_KEY`); no key → logged SKIP.
  - `scripts/restore-drill.sh [tarball]` → prints `PASS`/`FAIL`, exit 0/1; appends one line to `volumes/logs/backup.log`.
  - `healthcheck-all.sh`/`schedule-monitor.sh` alert through `notify_send` = `"$VENV_PY" -m src.notify send …` with the existing curl as fallback (out-of-band doctrine kept: no dependency on the bot or on Postgres for delivery; no `VENV_PY` → straight to curl, and the alert-delivery-status row is simply absent). `schedule-monitor.sh`'s collector already runs on `"$VENV_PY"` since Task 12.
  - The runbook lists every owner-run step (pmset, Ollama, R2, seal key, drill, timer install) with verification commands.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_scripts_syntax.py`:

```python
def test_restore_drill_exists_and_parses():
    r = subprocess.run(["bash", "-n", str(REPO / "scripts/restore-drill.sh")],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_backup_dumps_atlas_and_seals_secrets():
    src = (REPO / "scripts/backup.sh").read_text()
    assert "pg_dump atlas" in src
    assert "openssl enc -aes-256-cbc -pbkdf2" in src
    assert "backup-seal.key" in src
    assert 'cp "$PROJECT_DIR/.env" "$TMP/' not in src       # plain .env never lands in the tarball


def test_backup_has_retention_rule():
    # spec §9 P0 ops-debt cell + §12a row 4 (round-2 #50): R2 is free only
    # under 10 GB-month, and the sealed bundle + atlas dump are now in every
    # nightly tarball — unbounded growth is the finding.
    src = (REPO / "scripts/backup.sh").read_text()
    assert "--min-age 60d" in src                 # off-site prune
    assert "-mtime +60" in src                    # local prune
    assert "No retention cap locally" not in src  # the old comment is gone


def test_alerters_prefer_notify_send_with_curl_fallback():
    for rel in ("scripts/healthcheck-all.sh", "scripts/schedule-monitor.sh"):
        src = (REPO / rel).read_text()
        assert '"$VENV_PY" -m src.notify send' in src, rel     # never `pipenv run python`
        assert "api.telegram.org" in src, rel                 # fallback kept


def test_healthcheck_resolves_and_guards_the_interpreter():
    # healthcheck-all.sh gains its first python call here (notify_send); same
    # VENV_PY contract as the canary and schedule-monitor (Task 12).
    src = (REPO / "scripts/healthcheck-all.sh").read_text()
    assert 'VENV_PY="${VENV_PY:-' in src and "import src.config" in src


def test_runbook_exists():
    doc = (REPO / "docs/runbooks/2026-09-25-p0-ops-hygiene.md").read_text()
    for needle in ("pmset -a autorestart 1", "ollama rm", "qwen3.5:4b", "embeddinggemma",
                   "rclone config", "backup-seal.key", "restore-drill.sh", "timers-only",
                   # reviewed-spec rows: §12a 1/2/2b auth posture, §0a plutil
                   # exit test, SDK_RECORD fixtures, the alembic diagnostic,
                   # the R2 60-day retention rule (round-2 #50)
                   "Login method: Claude account", "plutil -p", "SDK_RECORD=1",
                   "alembic-current-check.sh", "overflow_credits", "--min-age 60d"):
        assert needle in doc, needle
    # The old runbook offered to put the token in the launchd env; the reviewed
    # spec forbids it (§0a last rows, round-1 #31).
    assert "into the launchd env" not in doc
    # Round-2 #28 moved `claude setup-token` to "needed before P3": the runbook
    # must say so rather than instruct the mint at P0 exit.
    assert "is NOT a P0 step" in doc
    # Round-2 #8 cancelled the server-deploy/SKILL.md wiring. The runbook may
    # NAME that path (§11 explains why the script is not wired into it) but
    # must not instruct the edit.
    assert "a DIAGNOSTIC, not a deploy step" in doc
    assert "NOT wired into" in doc
    for instruction in ("Wire it into", "add `bash scripts/alembic-current-check.sh` to"):
        assert instruction not in doc, instruction
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pipenv run pytest tests/test_scripts_syntax.py -v`
Expected: the four new tests FAIL (missing script/doc, missing strings).

- [ ] **Step 3: `backup.sh` — atlas dump + sealed secrets**

Replace step 1 (`pg_dump assistant > "$TMP/db.sql"`) with:

```bash
# 1. Postgres dumps (plain text, small, grep-friendly). `assistant` is the
#    server DB. `atlas` (trading verticals) lived OUTSIDE this dump until
#    2026-09-25 (state map §2.8) — dumped when present, never fatal.
pg_dump assistant > "$TMP/db.sql"
if psql -lqt 2>/dev/null | cut -d'|' -f1 | tr -d ' ' | grep -qx atlas; then
    if pg_dump atlas > "$TMP/atlas.sql" 2>>"$PROJECT_DIR/volumes/logs/backup.log"; then
        echo "$(date -u +%FT%TZ) atlas dump OK ($(du -h "$TMP/atlas.sql" | cut -f1))" \
            >> "$PROJECT_DIR/volumes/logs/backup.log"
    else
        echo "$(date -u +%FT%TZ) WARN atlas dump failed" >> "$PROJECT_DIR/volumes/logs/backup.log"
    fi
fi
```

Replace step 4's comment line `# 4. Config snapshot — NEVER include .env (secrets!)` with `# 4. Config snapshot — plain copies NEVER include .env; secrets travel only in the sealed bundle (4b).` and add after the two `cp` lines:

```bash
# 4b. Sealed secrets (2026-09-25, spec §9 P0 / D12): .env, projects/atlas/.env
#     and ~/.cloudflared/{config.yml,cert.pem,<tunnel>.json} tar'd and
#     AES-256 encrypted with a key that lives OUTSIDE every backup
#     (~/.config/ai-server/backup-seal.key — owner-created, chmod 600, copy
#     in the password manager; see docs/runbooks/2026-09-25-p0-ops-hygiene.md).
#     No key → SKIP (logged). Never fatal. Restore: scripts/restore-drill.sh.
SEAL_KEY="${BACKUP_SEAL_KEY:-$HOME/.config/ai-server/backup-seal.key}"
if [[ -r "$SEAL_KEY" ]]; then
    SEAL_TMP=$(mktemp -d)
    mkdir -p "$SEAL_TMP/secrets/cloudflared"
    cp "$PROJECT_DIR/.env" "$SEAL_TMP/secrets/env" 2>/dev/null || true
    cp "$PROJECT_DIR/projects/atlas/.env" "$SEAL_TMP/secrets/atlas.env" 2>/dev/null || true
    cp "$HOME"/.cloudflared/config.yml "$HOME"/.cloudflared/cert.pem "$HOME"/.cloudflared/*.json \
        "$SEAL_TMP/secrets/cloudflared/" 2>/dev/null || true
    tar -cf "$SEAL_TMP/secrets.tar" -C "$SEAL_TMP" secrets
    if openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt \
            -in "$SEAL_TMP/secrets.tar" -out "$TMP/secrets.tar.enc" \
            -pass file:"$SEAL_KEY" 2>>"$PROJECT_DIR/volumes/logs/backup.log"; then
        echo "$(date -u +%FT%TZ) sealed secrets OK" >> "$PROJECT_DIR/volumes/logs/backup.log"
    else
        echo "$(date -u +%FT%TZ) WARN sealing failed (bundle omitted)" >> "$PROJECT_DIR/volumes/logs/backup.log"
        rm -f "$TMP/secrets.tar.enc"
    fi
    rm -rf "$SEAL_TMP"
else
    echo "$(date -u +%FT%TZ) seal SKIP (no key at $SEAL_KEY)" >> "$PROJECT_DIR/volumes/logs/backup.log"
fi
```

**Retention (spec §9 P0 ops-debt cell, §12a row 4, round-2 #50).** Inside the existing `if command -v rclone … r2: …` block (`:46-57`), directly after the successful `rclone copy`, add the off-site prune — guarded exactly like the upload, never fatal, always logged:

```bash
        # 60-day retention off-site (spec §12a row 4): R2 is free only under
        # 10 GB-month on a card-on-file account, and since 2026-09-25 every
        # nightly tarball carries the atlas dump AND the sealed bundle. An
        # unpruned bucket grows one tarball a day forever.
        if rclone delete r2:ai-server-backups/ --min-age 60d \
                2>>"$PROJECT_DIR/volumes/logs/backup.log"; then
            echo "$(date -u +%FT%TZ) offsite prune OK (>60d)" \
                >> "$PROJECT_DIR/volumes/logs/backup.log"
        else
            echo "$(date -u +%FT%TZ) WARN offsite prune failed" \
                >> "$PROJECT_DIR/volumes/logs/backup.log"
        fi
```

and replace step 7's comment (`:59`, `# 7. No retention cap locally — 2TB SSD, keep everything`) with a matching local cap, so the two sides agree and the drill always has recent tarballs:

```bash
# 7. Retention: 60 days, locally and off-site (spec §12a row 4). The tarball
#    now carries the atlas dump and the sealed secrets bundle, so "keep
#    everything" is no longer free in either place.
find "$BACKUP_DIR" -name 'backup-*.tar.gz' -mtime +60 -delete 2>/dev/null || true
```

(check the actual variable name for the backup directory when implementing — `scripts/backup.sh` defines it near the top; the needle the test greps for is `-mtime +60`.)

- [ ] **Step 4: Create `scripts/restore-drill.sh`**

```bash
#!/usr/bin/env bash
# scripts/restore-drill.sh — prove the newest backup restores (P0 exit
# criterion "restore drill passes", spec §9). OWNER-RUN. Touches no live
# state: restores db.sql (+ atlas.sql) into throwaway databases, unseals the
# secrets bundle into a temp dir and lists entry NAMES only, then drops
# everything. Prints PASS/FAIL, exit 0/1, one line appended to backup.log.
#
# Usage: bash scripts/restore-drill.sh [path/to/backup-YYYY-MM-DD.tar.gz]
set -uo pipefail
export PATH="/opt/homebrew/opt/postgresql@15/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="$PROJECT_DIR/volumes/backups"
LOG="$PROJECT_DIR/volumes/logs/backup.log"
SEAL_KEY="${BACKUP_SEAL_KEY:-$HOME/.config/ai-server/backup-seal.key}"
TARBALL="${1:-$(ls -t "$BACKUP_DIR"/backup-*.tar.gz 2>/dev/null | head -1)}"
[[ -n "$TARBALL" && -f "$TARBALL" ]] || { echo "FAIL no backup tarball in $BACKUP_DIR"; exit 1; }

TMP=$(mktemp -d)
STAMP=$(date +%s)
DB="aiserver_restore_$STAMP"
ATLAS_DB="atlas_restore_$STAMP"
fail=0
cleanup() {
    dropdb --if-exists "$DB" 2>/dev/null || true
    dropdb --if-exists "$ATLAS_DB" 2>/dev/null || true
    rm -rf "$TMP"
}
trap cleanup EXIT

tar -xzf "$TARBALL" -C "$TMP" || { echo "FAIL untar $TARBALL"; exit 1; }
echo "drill: $(basename "$TARBALL")"

# 1. assistant DB → throwaway; must contain jobs rows.
if createdb "$DB" 2>/dev/null && psql -q "$DB" < "$TMP/db.sql" > /dev/null 2>&1; then
    n=$(psql -tAc "SELECT count(*) FROM jobs" "$DB" 2>/dev/null || echo 0)
    if [[ "$n" =~ ^[0-9]+$ ]] && (( n > 0 )); then
        echo "OK assistant restore: $n jobs"
    else
        echo "FAIL assistant restore: jobs=$n"; fail=1
    fi
else
    echo "FAIL assistant restore (createdb/psql)"; fail=1
fi

# 2. atlas DB (in backups since 2026-09-25).
if [[ -s "$TMP/atlas.sql" ]]; then
    if createdb "$ATLAS_DB" 2>/dev/null && psql -q "$ATLAS_DB" < "$TMP/atlas.sql" > /dev/null 2>&1; then
        t=$(psql -tAc "SELECT count(*) FROM information_schema.tables WHERE table_schema NOT IN ('pg_catalog','information_schema')" "$ATLAS_DB" 2>/dev/null || echo 0)
        if [[ "$t" =~ ^[0-9]+$ ]] && (( t > 0 )); then
            echo "OK atlas restore: $t tables"
        else
            echo "FAIL atlas restore: 0 tables"; fail=1
        fi
    else
        echo "FAIL atlas restore (createdb/psql)"; fail=1
    fi
else
    echo "WARN atlas.sql absent (backup predates 2026-09-25 or atlas DB missing)"
fi

# 3. Sealed secrets: unseal + list NAMES only (values never printed).
if [[ -s "$TMP/secrets.tar.enc" ]]; then
    if [[ -r "$SEAL_KEY" ]] && openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 \
            -in "$TMP/secrets.tar.enc" -out "$TMP/secrets.tar" -pass file:"$SEAL_KEY" 2>/dev/null; then
        names=$(tar -tf "$TMP/secrets.tar")
        if printf '%s\n' "$names" | grep -qx 'secrets/env'; then
            echo "OK sealed secrets: $(printf '%s\n' "$names" | grep -c .) entries"
        else
            echo "FAIL sealed bundle lacks secrets/env"; fail=1
        fi
        rm -f "$TMP/secrets.tar"
    else
        echo "FAIL cannot unseal (key missing at $SEAL_KEY, or wrong key)"; fail=1
    fi
else
    echo "WARN no sealed secrets in this backup (seal key absent when it ran?)"
fi

# 4. Off-site copy (informational — the drill is about restorability).
if command -v rclone >/dev/null 2>&1 && rclone listremotes 2>/dev/null | grep -q '^r2:'; then
    if rclone lsf "r2:ai-server-backups/$(basename "$TARBALL")" >/dev/null 2>&1; then
        echo "OK off-site copy present"
    else
        echo "WARN off-site copy of $(basename "$TARBALL") not found"
    fi
else
    echo "WARN rclone r2: remote not configured"
fi

verdict=$([[ $fail == 0 ]] && echo PASS || echo FAIL)
echo "$(date -u +%FT%TZ) restore-drill $(basename "$TARBALL") result=$verdict" >> "$LOG"
echo "$verdict"
exit $fail
```

Then `chmod +x scripts/restore-drill.sh`.

- [ ] **Step 5: Alerters prefer `notify send`, keep curl as fallback; no `pipenv run` under launchd**

`scripts/healthcheck-all.sh` — after `LOG="$PROJECT_DIR/volumes/logs/healthcheck.log"` (line 16) add:

```bash
# Interpreter for the notify CLI. NEVER `pipenv run` in a launchd script (it is
# a ~/.pyenv shim `bash -lc` cannot see → rc=127). The timer plist exports
# VENV_PY (install-launchd.sh); .venv / `pipenv shell` cover manual runs. An
# interpreter that cannot import the server is treated as absent → curl path.
# The probe runs in a SUBSHELL that cd's first: this script never cd's, and the
# editable install is inert on this host (the macOS hidden-`.pth` gotcha), so
# `import src.config` only resolves from the project root — verified:
# `cd /tmp && <venv>/bin/python -c "import src.config"` → ModuleNotFoundError.
# Without the subshell every manual run would blank VENV_PY and silently take
# the curl path, losing the alert-history row.
VENV_PY="${VENV_PY:-}"
[[ -z "$VENV_PY" && -x "$PROJECT_DIR/.venv/bin/python" ]] && VENV_PY="$PROJECT_DIR/.venv/bin/python"
[[ -z "$VENV_PY" ]] && VENV_PY="$(command -v python || true)"
if [[ -n "$VENV_PY" ]] && ! (cd "$PROJECT_DIR" && "$VENV_PY" -c 'import src.config') 2>/dev/null; then
    echo "$(date -u +%FT%TZ) WARN venv python unusable ($VENV_PY); alerts fall back to curl" >> "$LOG"
    VENV_PY=""
fi

# Owner DM path (2026-09-25): the notifications outbox CLI first (direct
# Telegram HTTP + a `notifications` row for alert history), the raw curl
# below as the fallback when the CLI itself cannot run. Both are out-of-band:
# neither depends on the bot or the runner being alive.
notify_send() {   # $1 = kind  $2 = text ; returns 0 when delivered/recorded
    [[ -n "$VENV_PY" ]] || return 1
    (cd "$PROJECT_DIR" && "$VENV_PY" -m src.notify send --kind "$1" --severity critical \
        --text "$2" >> "$LOG" 2>&1)
}
```

In `check_runner_liveness` replace ONLY the `if curl -sf … then … else … fi` block (lines 127-134) with the block below. The `token=` / `chat_ids=` / `chat_id=` reads at lines 118-120 and the creds-missing guard at 121-124 stay — the curl fallback uses them:

```bash
    if notify_send ops_alert "$msg"; then
        echo "$now" > "$ALERT_STATE" 2>/dev/null || true
        echo "$(date -u +%FT%TZ) ALERT runner-down sent via notify" >> "$LOG"
    elif curl -sf --max-time 10 "https://api.telegram.org/bot${token}/sendMessage" \
            --data-urlencode "chat_id=${chat_id}" \
            --data-urlencode "text=${msg}" > /dev/null 2>&1; then
        echo "$now" > "$ALERT_STATE" 2>/dev/null || true
        echo "$(date -u +%FT%TZ) ALERT runner-down DM sent to chat $chat_id (curl fallback)" >> "$LOG"
    else
        echo "$(date -u +%FT%TZ) WARN runner-down DM failed (telegram unreachable?)" >> "$LOG"
    fi
```

In `check_swing_freshness` replace ONLY its `if curl -sf … fi` block (lines 180-185) with:

```bash
    if notify_send ops_alert "$msg"; then
        echo "$now" > "$SWING_ALERT_STATE" 2>/dev/null || true
        echo "$(date -u +%FT%TZ) ALERT swing-watchdog sent via notify" >> "$LOG"
    elif curl -sf --max-time 10 "https://api.telegram.org/bot${token}/sendMessage" \
            --data-urlencode "chat_id=${chat_id}" \
            --data-urlencode "text=${msg}" > /dev/null 2>&1; then
        echo "$now" > "$SWING_ALERT_STATE" 2>/dev/null || true
        echo "$(date -u +%FT%TZ) ALERT swing-watchdog DM sent (curl fallback)" >> "$LOG"
    fi
```

(its `token=`/`chat_ids=`/`chat_id=` reads at lines 175-177 and the `[[ -z … ]] && return 0` at 178 stay).

`scripts/schedule-monitor.sh` — one edit (its `VENV_PY` block and the line-21 collector repair are Task 12's): replace the body of `send_dm()` (originally lines 32-43; locate by name) with:

```bash
send_dm() {
    local msg="$1" token chat_ids chat_id
    if [[ -n "$VENV_PY" ]] && (cd "$PROJECT_DIR" && "$VENV_PY" -m src.notify send --kind ops_alert --severity warn \
            --text "$msg" >> "$LOG" 2>&1); then
        echo "$(date -u +%FT%TZ) ALERT sent via notify" >> "$LOG"; return 0
    fi
    token=$(grep -E '^TELEGRAM_BOT_TOKEN=' "$PROJECT_DIR/.env" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'" || true)
    chat_ids=$(grep -E '^TELEGRAM_ALLOWED_CHAT_IDS=' "$PROJECT_DIR/.env" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'" || true)
    chat_id=$(printf '%s' "$chat_ids" | cut -d, -f1 | tr -d '[:space:]')
    [[ -z "$token" || -z "$chat_id" ]] && { echo "$(date -u +%FT%TZ) WARN DM skipped: creds missing" >> "$LOG"; return 0; }
    curl -sf --max-time 10 "https://api.telegram.org/bot${token}/sendMessage" \
        --data-urlencode "chat_id=${chat_id}" \
        --data-urlencode "text=${msg}" > /dev/null 2>&1 \
        && echo "$(date -u +%FT%TZ) ALERT DM sent (curl fallback)" >> "$LOG" \
        || echo "$(date -u +%FT%TZ) WARN DM failed" >> "$LOG"
}
```

- [ ] **Step 6: Write the runbook `docs/runbooks/2026-09-25-p0-ops-hygiene.md`**

```markdown
# P0 ops hygiene — owner runbook (2026-09-25)

Spec: `docs/superpowers/specs/2026-09-25-multi-model-platform-design.md` §9 (P0 row), §12 D3/D12.
These steps need `sudo`, account credentials or a human judgement call, so no
job runs them. Do them in order; each has a verification line. Total ≈ 1.5 h
(§1–§6 ≈ 45 min; §7 auth rows ≈ 25 min; §9–§11 ≈ 20 min).

## 1. Auto-restart after power loss (sudo)

    sudo pmset -a autorestart 1
    pmset -g | grep autorestart          # → autorestart 1   (was 0 on 2026-09-24)

## 2. Ollama: drop the 14 GB of stale weights, pull the two P3 models

Nothing in `src/` references Ollama today (state map §2.8); the three models
below are six months old and were never called.

    ollama rm phi3:mini deepseek-coder-v2:16b mistral:latest
    ollama pull qwen3.5:4b            # ~3.4 GB, routing/classification (spec §0a row 5)
    ollama pull embeddinggemma        # embeddings
    ollama list                       # → exactly qwen3.5:4b and embeddinggemma
    df -h /                           # ≈ 10 GB freed

## 3. Off-site backups to Cloudflare R2 (account credentials)

`scripts/backup.sh` already uploads when an `r2:` rclone remote exists (it
logs `offsite SKIP` today). One-time:

1. Cloudflare dashboard → R2 → create bucket `ai-server-backups`; create an
   R2 API token (Object Read & Write, this bucket only). Note account id,
   access key id, secret access key.
2. `rclone config` → new remote `r2`, storage `s3`, provider `Cloudflare`,
   the three values above, endpoint `https://<account-id>.r2.cloudflarestorage.com`.
3. Verify: `rclone lsd r2:` lists `ai-server-backups`.
4. Run one backup now: `bash scripts/backup.sh && tail -4 volumes/logs/backup.log`
   → `offsite OK r2:ai-server-backups/backup-<date>.tar.gz` **and**
   `offsite prune OK (>60d)`.
5. **The free tier has two conditions** (spec §12a row 4 as round 2 rewrote it,
   §13): R2 is free only **≤ 10 GB-month** and only on an account with a
   **payment method on file**. Add the card, then confirm the bucket stays
   inside the allowance — `rclone size r2:ai-server-backups` — knowing that
   `backup.sh` now prunes anything older than 60 days on both sides
   (`rclone delete --min-age 60d` off-site, `find -mtime +60` locally). Bucket
   size joins the CostCard in P2.

## 4. Seal key for the encrypted secrets bundle

`backup.sh` now includes `secrets.tar.enc` (.env, atlas .env, cloudflared
config/cert/tunnel json) — only when this key exists. The key must live
outside every backup AND in the password manager, or the bundle is useless.

    mkdir -p ~/.config/ai-server
    openssl rand -base64 48 > ~/.config/ai-server/backup-seal.key
    chmod 600 ~/.config/ai-server/backup-seal.key
    cat ~/.config/ai-server/backup-seal.key     # paste into the password manager as "ai-server backup seal key"
    bash scripts/backup.sh && grep 'sealed secrets OK' volumes/logs/backup.log | tail -1

## 5. Restore drill (P0 exit criterion)

    bash scripts/restore-drill.sh
    # expected: OK assistant restore: <n> jobs / OK atlas restore: <t> tables /
    #           OK sealed secrets: <k> entries / OK off-site copy present / PASS

A `FAIL` line names the leg; fix and re-run. Record the date of the first
PASS in `.context/modules/hosting/skills/GOTCHAS.md`.

## 6. Install the credential-canary timer on prod (no service restart)

Run in the PRODUCTION checkout after the P0 deploy (`server-deploy`):

    cd ~/Library/Application\ Support/ai-server
    bash scripts/install-launchd.sh timers-only
    launchctl list | grep credential-canary
    bash scripts/credential-canary.sh && cat volumes/telemetry/credential_canary.json   # "ok": true

## 7. Auth config by hand (spec D3 + §12a rows 1, 2, 2b — protected path #2, never by a job)

The Keychain `claude login` on the Mini is the live credential and the only
one the fleet uses (spec §3, §0a last rows, review #31). Nothing in P0 reads a
token from the environment; the canary (§6) proves the Keychain login daily.

- **§12a row 1 (P0 exit, ~10 min)**: confirm the Max tier (5x / 20x) and, on
  claude.ai → Billing, that usage credits are $0, auto-reload is OFF and the
  monthly spend limit is $0 (`overflow_credits: disabled` — the only metered
  Anthropic path is usage credits, spec §2.8). Write both facts with the date
  in `.context/modules/runner/skills/GOTCHAS.md` (P3's `providers.yml` copies
  them from there; the P2 window forecast needs the tier).
- **§12a row 2 (P0 exit, 2 min)**: claude.ai → Settings → Privacy → "Help
  improve Claude" OFF (30-day retention instead of 5 years, spec D4). Note the
  date in the same GOTCHAS entry; P1's `approvals(kind=attestation)` row
  replaces the note.
- **§12a row 2b (P0 exit, 2 min)**: confirm Devin's bundled `claude` is the
  **unmodified binary signed in on the owner's own `/login`** — `claude /status`
  in a Devin session should read "Login method: Claude account" and Devin must
  not intermediate the token. If it does anything else, sign Devin out of the
  Max credential: the standing rule is "no third-party harness signs in with
  the Max credential" (`crosscut-tos §3.7`, spec §2.8 Claude row). Record the
  answer with the date in the same GOTCHAS entry; it joins the quarterly
  attestation card (§12a row 22).
- **§12a row 3 — `claude setup-token` — is NOT a P0 step.** Round 2 re-scoped
  it to "**needed before P3** (the Keychain login is the only credential until
  the executor seam exists; the sealed token is unused before P3)". No P0 code
  reads a token (Global Constraints "Auth posture"), so minting a one-year
  credential that outranks `/login` three phases early only widens exposure.
  **Do not run `claude setup-token` during P0.** When P3 arrives the rules
  are: seal it 0600 at `~/.config/ai-server/claude-setup-token`, OUTSIDE every
  workspace and every backup's plain tree (`backup.sh` never copies
  `~/.config/ai-server/`); **never** paste it into `.env`, a launchd plist, a
  shell profile or `scripts/install-launchd.sh`; record the mint date in
  GOTCHAS (a T−30 d expiry alarm is a P2 schedule). The exit test below is
  independent of whether a token exists and **is** a P0 step.
- **P0 exit test (spec §0a)** — run after the deploy and after any installer run:

      plutil -p ~/Library/LaunchAgents/com.assistant.*.plist | grep -c CLAUDE_CODE_OAUTH_TOKEN   # → 0
      grep -c CLAUDE_CODE_OAUTH_TOKEN .env                                                       # → 0 (protected file; read only)
      plutil -p ~/Library/LaunchAgents/com.assistant.runner.plist | grep -c DISABLE_TELEMETRY     # → 1 after the full installer run (§9)

## 8. Optional: NOTIFY_OUTBOX kill switch

If DMs misbehave after the deploy, add `NOTIFY_OUTBOX=0` to prod `.env` (auth
config file — owner-only edit) and `launchctl kickstart -k gui/$(id -u)/com.assistant.bot`
— the bot only. The switch is renderer-side: the runner publishes the legacy
channels in both modes (P0 dual-write), so the legacy `_done_listener` /
`_task_notifier` cards resume the moment the bot restarts. The runner keeps
writing `notifications` rows until its own next restart; they are harmless,
but before you remove the line to re-enable, park them so they are not
delivered late: `psql assistant -c "UPDATE notifications SET status='skipped' WHERE status='pending'"`.
Then remove the line and kickstart the bot again.

## 9. Full installer run on prod (service restart — owner-run, spec §2.4/§3)

The P0 deploy gives every Claude subprocess `DISABLE_ERROR_REPORTING=1` /
`DISABLE_TELEMETRY=1` through `ClaudeAgentOptions.env` (in code, no restart
needed beyond the deploy's own). The belt in the service plists needs one
full installer run, which restarts runner/web/bot — pick a quiet moment:

    cd ~/Library/Application\ Support/ai-server
    bash scripts/install-launchd.sh           # re-renders + reloads runner/web/bot + all timers
    plutil -p ~/Library/LaunchAgents/com.assistant.runner.plist | grep -c DISABLE_TELEMETRY   # → 1
    plutil -p ~/Library/LaunchAgents/com.assistant.*.plist | grep -c CLAUDE_CODE_OAUTH_TOKEN  # → 0

## 10. Raw SDK recorder: collect the P3 replay fixtures (spec §2.4, review #27)

`SDK_RECORD=1` is read by `Settings` (`.env` is a protected file — owner edit):

    cd ~/Library/Application\ Support/ai-server
    echo 'SDK_RECORD=1' >> .env && launchctl kickstart -k gui/$(id -u)/com.assistant.runner
    # … a few days later (the 41 schedules cover the skill classes on their own):
    .venv/bin/python -m src.runner.sdk_record coverage      # prints jobs per skill + "coverage OK (≥ 20 jobs, ≥ N classes)"
    sed -i '' '/^SDK_RECORD=1$/d' .env && launchctl kickstart -k gui/$(id -u)/com.assistant.runner

Recordings are `volumes/audit_log/<id>.sdk.jsonl` (secrets redacted; ~1–5 MB
per agentic job). `retention.rotate_audit_logs` archives them with the
per-job JSONL after 30 days, so P3 copies its 20 fixtures into
`tests/replay/` before then.

## 11. Alembic history — a DIAGNOSTIC, not a deploy step

`scripts/alembic-current-check.sh` (Task 18) reports when prod's
`alembic_version` names a revision with no script on disk — the state a bad
revert leaves behind. **Run it by hand after any migration revert.** It is
deliberately NOT wired into `skills/server-deploy/SKILL.md`: round 2 of the
spec review cancelled that edit (§9 rollback paragraph — "alembic already
fails loudly on a missing revision, so **no `server-deploy/SKILL.md` edit** is
needed for this, which round 1 had hidden inside P0"), and the §9 P0 row's
"Protected touches" cell is **none**. What protects the deploy is the pytest
gate `server-deploy` already runs: `tests/test_migrations.py` layer 1c
(Task 18) fails if any revision in `alembic/applied_history.txt` has no script
on disk, so a `git revert` of a migration file goes red in the gate rather
than mid-deploy.

    bash scripts/alembic-current-check.sh    # exit 0 ok · 1 mismatch · 2 cannot determine
```

- [ ] **Step 6b (CONDITIONAL — only if D1 chose the displacement): drop the alpha valve to 6 and take `review-and-improve` off the idle trigger**

Spec §9's P0 scope cell ends with "`review-and-improve` idle trigger removed here if D1 picks that displacement", and §2.8/§13 state the alternative: *either* `ALPHA_DAILY_JOB_VALVE` 12 → 6 (≈ −40 M tokens/day) **and** `review-and-improve`'s idle trigger off in P0 rather than P4 (≈ −36 M/month), *or* D1 explicitly accepts "N `rejected` windows/week during build". **Read D1's answer first** (Owner-actions row "P0 entry", §12a row 0). If D1 accepted the rejected-windows option, skip this step and record that in the PR's window-cost block.

If D1 chose the displacement:

1. `src/runner/events.py:364` — `ALPHA_DAILY_JOB_VALVE = 12` → `6`, with a comment citing D1 and the date, so P4 knows to consider restoring it.
2. `src/runner/events.py` — disable **only** `_check_idle_queue_review`'s trigger: both live in `events.py` (`_check_idle_queue_alpha` at `:392`, `_check_idle_queue_review` at `:432`, dispatched at `:497` and `:504`), so remove the `:497` call and leave `:504`. **`_check_idle_queue_alpha` stays**: spec round-1 #44 protects the alpha drainer and the P4 exit criterion is literally "`_check_idle_queue_alpha` still enqueues `alpha-governor` (test)".
3. Test, in `tests/test_idle_queue.py` (or wherever the breaker-gating tests from commit `ef375b7` live — they already mock `_check_idle_queue_alpha`):

```python
def test_alpha_drainer_survives_the_review_trigger_removal(monkeypatch):
    # spec §9 P4 exit criterion + round-1 #44: the alpha drainer is never the
    # thing that gets switched off to pay for build weeks.
    from src.runner import main as main_mod
    assert hasattr(main_mod, "_check_idle_queue_alpha")
    calls = []
    monkeypatch.setattr(main_mod, "enqueue_job", lambda *a, **k: calls.append(k))
    ...   # drive one idle tick; assert an alpha-governor enqueue happened


def test_alpha_valve_is_at_the_d1_value():
    from src.runner.events import ALPHA_DAILY_JOB_VALVE
    assert ALPHA_DAILY_JOB_VALVE == 6        # D1 displacement (spec §2.8)
```

4. Record both numbers in the PR's `## P0 — window cost` block and in `.context/modules/runner/CHANGELOG.md` with "D1 displacement" in the summary line. This is a **behaviour change the owner asked for**, so it is never applied on the plan's own initiative.

- [ ] **Step 7: Run the tests, then a local backup + drill**

Run: `pipenv run pytest tests/test_scripts_syntax.py -v`
Expected: all PASS.

Run: `bash scripts/backup.sh && bash scripts/restore-drill.sh; echo rc=$?`
Expected on the dev box: `OK assistant restore: <n> jobs`, `OK atlas restore: <t> tables` (the atlas DB exists here), `WARN no sealed secrets …` or `OK sealed secrets` depending on whether step 4 of the runbook has been done, `WARN rclone r2: remote not configured` until step 3, then `PASS` and `rc=0` (the sealed/off-site legs only WARN when unconfigured; they FAIL only when configured and broken).

- [ ] **Step 8: CHANGELOG + commit**

Prepend to `.context/modules/hosting/CHANGELOG.md`:

```markdown
## 2026-09-25 — backup.sh dumps atlas + seals secrets; restore-drill.sh; alerters via notify send; P0 ops runbook

- `scripts/backup.sh`: `pg_dump atlas` when the DB exists; `secrets.tar.enc` (AES-256-CBC/PBKDF2, key `~/.config/ai-server/backup-seal.key`, SKIP when absent). `scripts/restore-drill.sh` (new): throwaway restore of both dumps + unseal names-only + off-site presence → PASS/FAIL. `healthcheck-all.sh` (gains the `VENV_PY` block) / `schedule-monitor.sh` (`send_dm`): `"$VENV_PY" -m src.notify send` first, curl fallback kept — never `pipenv run` (Task 12 gotcha). Runbook `docs/runbooks/2026-09-25-p0-ops-hygiene.md` holds the owner-only steps (pmset, Ollama, R2, seal key, drill, timer install, D3 auth, kill switch = bot-only restart).
```

```bash
chmod +x scripts/restore-drill.sh
git add scripts/backup.sh scripts/restore-drill.sh scripts/healthcheck-all.sh scripts/schedule-monitor.sh docs/runbooks/2026-09-25-p0-ops-hygiene.md tests/test_scripts_syntax.py .context/modules/hosting/CHANGELOG.md
git commit -m "feat(ops): backup dumps atlas + sealed secrets, restore drill, alerters through notify send, P0 ops runbook"
```

---

### Task 15: `SDK_RECORD=1` — opt-in raw SDK message recorder (the P3 replay-gate fixtures)

**Execution position:** 8 of 21 — previous: Task 20, next: Task 17 (see Global Constraints "Execution order").

- [ ] **Step 0: Prerequisite check** — `pipenv run python -c "from src.runner.secret_redact import redact; print('ok')"` must print `ok` (Task 20 owns the single pattern set this module re-exports). If it fails: **execute Task 20 first.** Also confirm Task 3's 3-tuple `_run_in_process`: `pipenv run python -c "import inspect; from src.runner import session; print(inspect.signature(session._run_in_process).return_annotation)"`.

Spec §2.4 ("An opt-in raw recorder (`SDK_RECORD=1`, P0) dumps every SDK message (dataclass → JSON, secrets redacted) to `volumes/audit_log/<id>.sdk.jsonl` so the P3 replay gate has real fixtures — the per-job JSONL is a lossy derived view … and cannot exercise `_run_in_process`'s isinstance dispatch; ≥20 jobs across skill classes are recorded before P3"), §9 P0 row, review #27. Executed after Task 3 (it hooks the `_run_in_process` Task 3 leaves behind) and before Task 17.

**Files:**
- Create: `src/runner/sdk_record.py`
- Modify: `src/config.py` (add `sdk_record`), `src/runner/session.py` (`_run_in_process`: the `client = ClaudeSDKClient(options=options)` line and the head of the `async for message in client.receive_response():` body)
- Modify: `.context/modules/runner/CHANGELOG.md`, `.context/modules/db/CHANGELOG.md`, `.context/modules/runner/CONTEXT.md` (Paths line — `check_runner_context` goes red the moment the file exists), `.context/SYSTEM.md` (module-graph row; `session.py` Depends-on += `runner.sdk_record`)
- Test: `tests/test_sdk_record.py`

**Interfaces:**
- Consumes: `settings.audit_log_dir`; Task 3's `_run_in_process` (3-tuple return, `cli_version()`).
- Produces:
  - `settings.sdk_record: bool = False` (env `SDK_RECORD`; opt-in per spec).
  - `sdk_record.SUFFIX = ".sdk.jsonl"`, `sdk_record.REDACTED = "[REDACTED]"`.
  - `sdk_record.redact(text: str) -> str` (pure): Anthropic keys (`sk-ant-…`), `Authorization: Bearer …`, `NAME=value` lines where `NAME` is `CLAUDE_CODE_OAUTH_TOKEN` or ends in `_TOKEN|_SECRET|_API_KEY|_PASSWORD`, and JSON/assignment pairs keyed `api_key|token|secret|password`.
  - `sdk_record.message_to_record(message, *, seq: int, ts: str) -> dict` (pure): `{"seq", "ts", "type": <class name>, "data": <dataclasses.asdict, every str redacted>}`; a non-dataclass or unserialisable message → `{"type", "repr": redact(repr(message))[:2000]}`. **`RateLimitEvent` — including `rate_limit_info.overage_status` / `overage_resets_at` / `overage_disabled_reason` — is recorded**, because the recorder's `record()` is the *first* statement in the loop body, ahead of the `RateLimitEvent` branch that can `continue` or raise, and `dataclasses.asdict` walks the nested `rate_limit_info`. The P0 scope cell asks for the recorder "(§2.4, **`overage_*` fields included**)" and §2.8 makes `overage_status == "allowed"` while `status == "rejected"` the **primary** `possible_credit_overflow` trigger that P2 reads (round-2 #58) — so `test_rate_limit_event_overage_fields_are_recorded` pins it and a future field allowlist cannot drop it silently.
  - `sdk_record.header_record(job_id, *, model, cli_version, sdk_version, prompt) -> dict` — `type="_recorder_start"`, `seq=0`, carries `prompt_sha256` + `prompt_chars`, never the prompt text.
  - `sdk_record.sdk_version() -> str` (`importlib.metadata`, `"unknown"` on failure).
  - `class SdkRecorder` — `SdkRecorder.for_job(job_id, *, enabled: bool | None = None, audit_dir: Path | None = None)` (defaults: `settings.sdk_record`, `settings.audit_log_dir`); `.enabled`, `.path`; `.start(**header_kwargs)`; `.record(message)`. Never raises: the first write failure logs one `warning` ("sdk recorder disabled …") and sets `enabled = False` for the rest of the job.
  - `sdk_record.scan_recordings(audit_dir) -> list[tuple[str, str | None]]` (job_id, skill from the sibling `<id>.jsonl`'s `job_started`), `sdk_record.coverage_report(pairs, *, min_jobs=20, min_classes=3) -> dict` (pure: `jobs, by_skill, classes, ok`), CLI `python -m src.runner.sdk_record coverage [--audit-dir P] [--min-jobs 20] [--min-classes 3]` → prints the table, exit 0 when `ok`, 1 otherwise.
  - Hook contract (pinned by test): in `_run_in_process`, `recorder = SdkRecorder.for_job(job_id)` is created before the client; `recorder.start(model=…, cli_version=…, sdk_version=…, prompt=…)` runs right after `async with client:`; `recorder.record(message)` is the **first statement** of the `async for message …` body — before the `RateLimitEvent` branch can `continue`/raise — so every message the loop sees (`SystemMessage`, `RateLimitEvent`, `AssistantMessage`, `UserMessage`, `ResultMessage`; `StreamEvent` only if `include_partial_messages` is ever enabled) is recorded in arrival order. What is recorded is exactly what the isinstance dispatch received, which is what P3's replay feeds back.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_sdk_record.py`:

```python
"""
Raw SDK recorder (P0; spec §2.4, review #27): opt-in, best-effort, redacted.
Pure — small dataclasses stand in for the SDK's message types; the write
path uses tmp_path; the session hook is pinned at the AST level.

Run: pipenv run pytest tests/test_sdk_record.py -v
"""

from __future__ import annotations

import ast
import inspect
import json
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from src.runner import sdk_record
from src.runner.sdk_record import (
    REDACTED,
    SUFFIX,
    SdkRecorder,
    coverage_report,
    header_record,
    message_to_record,
    redact,
)


@dataclass
class _Text:
    text: str


@dataclass
class _ToolUse:
    id: str
    name: str
    input: dict


@dataclass
class _Assistant:
    content: list
    model: str
    parent_tool_use_id: str | None = None


@dataclass
class _Result:
    subtype: str
    is_error: bool
    usage: dict = field(default_factory=dict)
    result: str | None = None


class _Opaque:
    def __repr__(self) -> str:
        return "<Opaque token=sk-ant-api03-abcdefgh>"


class TestRedact:
    @pytest.mark.parametrize("raw,leak", [
        ("key sk-ant-api03-AAAAbbbbCCCC123 end", "sk-ant-api03"),
        ("curl -H 'Authorization: Bearer eyJhbGciOi.xyz' https://x", "eyJhbGciOi"),
        ("CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-zzzzzzzz\nFOO=bar", "sk-ant-oat01"),
        ("TELEGRAM_BOT_TOKEN=123456:ABC-def", "123456:ABC"),
        ('{"api_key": "gsk_live_0123456789"}', "gsk_live"),
        ("password = 'hunter2hunter2'", "hunter2"),
    ])
    def test_redaction_covers_bearer_env_and_anthropic_keys(self, raw, leak):
        out = redact(raw)
        assert leak not in out and REDACTED in out

    def test_plain_text_untouched(self):
        assert redact("FOO=bar and no secrets here") == "FOO=bar and no secrets here"
        assert redact("PATH=/usr/bin") == "PATH=/usr/bin"
        assert redact('"output_tokens": 9363, "max_tokens": 20000') == '"output_tokens": 9363, "max_tokens": 20000'


class TestMessageToRecord:
    def test_dataclass_round_trip_in_order(self):
        msg = _Assistant(content=[_Text("hi"), _ToolUse("t1", "Bash", {"command": "ls"})],
                         model="claude-sonnet-4-6")
        rec = message_to_record(msg, seq=3, ts="2026-09-25T00:00:00+00:00")
        assert rec["seq"] == 3 and rec["type"] == "_Assistant"
        assert rec["data"]["content"][1]["input"]["command"] == "ls"
        json.dumps(rec)                                   # serialisable as-is

    def test_nested_content_is_redacted(self):
        msg = _Assistant(content=[_ToolUse("t1", "Bash",
                                           {"command": "curl -H 'Authorization: Bearer abcdef123456' x"})],
                         model="m")
        assert "abcdef123456" not in json.dumps(message_to_record(msg, seq=1, ts="t"))

    def test_unserialisable_message_is_recorded_as_repr(self):
        rec = message_to_record(_Opaque(), seq=1, ts="t")
        assert rec["type"] == "_Opaque" and "data" not in rec
        assert "sk-ant-api03" not in rec["repr"] and REDACTED in rec["repr"]

    def test_rate_limit_event_overage_fields_are_recorded(self):
        # The P0 scope cell says "SDK_RECORD=1 raw recorder (§2.4, `overage_*`
        # fields included)" because §2.8 makes RateLimitInfo.overage_status the
        # PRIMARY possible_credit_overflow trigger (round-2 #58): overage_status
        # == "allowed" while status == "rejected" means usage credits are
        # carrying the lane past the window with no `rejected` to key on.
        # dataclasses.asdict already walks the nested rate_limit_info, but
        # NOTHING named these fields — so a future field allowlist in the
        # recorder would silently drop the one signal P2 depends on. This test
        # is the pin.
        from dataclasses import dataclass

        @dataclass
        class _Info:
            status: str = "rejected"
            resets_at: str = "2026-10-02T00:00:00Z"
            utilization: float = 0.98
            overage_status: str = "allowed"
            overage_resets_at: str = "2026-10-02T00:00:00Z"
            overage_disabled_reason: str | None = None

        @dataclass
        class _RateLimitEvent:
            rate_limit_type: str = "five_hour"
            rate_limit_info: _Info = None            # type: ignore[assignment]

        rec = message_to_record(_RateLimitEvent(rate_limit_info=_Info()), seq=4, ts="t")
        blob = json.dumps(rec)
        for field_name in ("overage_status", "overage_resets_at", "status",
                           "resets_at", "utilization"):
            assert field_name in blob, field_name
        assert rec["data"]["rate_limit_info"]["overage_status"] == "allowed"

    def test_header_never_carries_the_prompt(self):
        h = header_record("job1", model="claude-sonnet-4-6", cli_version="2.1.139",
                          sdk_version="0.1.81", prompt="secret prompt text")
        assert h["type"] == "_recorder_start" and h["seq"] == 0
        assert "secret prompt" not in json.dumps(h)
        assert h["prompt_chars"] == 18 and len(h["prompt_sha256"]) == 64


class TestRecorder:
    HEADER = dict(model="m", cli_version="v", sdk_version="s", prompt="p")

    def test_disabled_writes_nothing(self, tmp_path):
        r = SdkRecorder.for_job("job1", enabled=False, audit_dir=tmp_path)
        r.start(**self.HEADER)
        r.record(_Text("x"))
        assert not (tmp_path / f"job1{SUFFIX}").exists()

    def test_enabled_appends_in_order_with_header(self, tmp_path):
        r = SdkRecorder.for_job("job1", enabled=True, audit_dir=tmp_path)
        r.start(**self.HEADER)
        r.record(_Text("a"))
        r.record(_Result("success", False))
        lines = [json.loads(l) for l in (tmp_path / f"job1{SUFFIX}").read_text().splitlines()]
        assert [l["type"] for l in lines] == ["_recorder_start", "_Text", "_Result"]
        assert [l["seq"] for l in lines] == [0, 1, 2]

    def test_write_error_never_raises(self, tmp_path, caplog):
        # Review Focus 6: point the recording path at a DIRECTORY so open("a")
        # fails; the recorder must swallow it, log once, and disable itself.
        (tmp_path / f"job2{SUFFIX}").mkdir()
        r = SdkRecorder.for_job("job2", enabled=True, audit_dir=tmp_path)
        r.record(_Text("x"))
        r.record(_Text("y"))
        assert r.enabled is False
        assert sum("sdk recorder disabled" in m for m in caplog.messages) == 1

    def test_default_enabled_follows_settings(self, monkeypatch, tmp_path):
        from src.config import settings
        monkeypatch.setattr(settings, "sdk_record", True)
        assert SdkRecorder.for_job("j", audit_dir=tmp_path).enabled is True
        monkeypatch.setattr(settings, "sdk_record", False)
        assert SdkRecorder.for_job("j", audit_dir=tmp_path).enabled is False


class TestCoverage:
    def test_report_math(self):
        pairs = ([("a", "chat")] * 8 + [("b", "atlas-report")] * 7
                 + [("c", "code-review")] * 5 + [("d", None)] * 2)
        rep = coverage_report(pairs, min_jobs=20, min_classes=3)
        assert rep["jobs"] == 22 and rep["classes"] == 3 and rep["ok"] is True
        assert rep["by_skill"]["(none)"] == 2

    def test_report_not_ok_below_threshold(self):
        assert coverage_report([("a", "chat")] * 19)["ok"] is False
        assert coverage_report([("a", "chat")] * 25, min_classes=2)["ok"] is False

    def test_scan_pairs_recordings_with_job_started(self, tmp_path):
        (tmp_path / f"j1{SUFFIX}").write_text("{}\n")
        (tmp_path / "j1.jsonl").write_text(json.dumps({"kind": "job_started", "skill": "chat"}) + "\n")
        (tmp_path / f"j2{SUFFIX}").write_text("{}\n")          # no sibling JSONL
        assert sorted(sdk_record.scan_recordings(tmp_path)) == [("j1", "chat"), ("j2", None)]

    def test_audit_index_ignores_recordings(self, tmp_path):
        # audit_index.rebuild_index globs *.jsonl; a recording has no job_started
        # event and must be skipped, not indexed as a job.
        from src.runner.audit_index import rebuild_index
        (tmp_path / f"j1{SUFFIX}").write_text(json.dumps({"seq": 0, "type": "_recorder_start"}) + "\n")
        (tmp_path / "j1.jsonl").write_text(
            json.dumps({"ts": "2026-09-25T00:00:00+00:00", "job_id": "j1", "kind": "job_started",
                        "description": "d", "skill": "chat", "model": "m"}) + "\n"
            + json.dumps({"ts": "2026-09-25T00:01:00+00:00", "job_id": "j1", "kind": "job_completed",
                          "duration_seconds": 1, "usage": {}}) + "\n")
        assert rebuild_index(tmp_path) == 1


class TestSessionHook:
    def test_record_is_the_first_statement_of_the_message_loop(self):
        # Every message — RateLimitEvent, SystemMessage, … — in arrival order,
        # before any isinstance branch can `continue` or raise.
        from src.runner import session
        src = inspect.getsource(session._run_in_process)
        loops = [n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.AsyncFor)]
        assert loops, "no `async for` in _run_in_process"
        first = ast.unparse(loops[0].body[0])
        assert first.startswith("recorder.record(message)"), first
        assert "SdkRecorder.for_job(job_id" in src and "recorder.start(" in src
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pipenv run pytest tests/test_sdk_record.py -v`
Expected: collection error `ModuleNotFoundError: No module named 'src.runner.sdk_record'`.

- [ ] **Step 3: Implement `src/runner/sdk_record.py` + the setting**

`src/config.py` — after `utility_model` (Task 0):

```python
    # Opt-in raw recorder for SDK messages (spec §2.4, P0): every message
    # _run_in_process receives → volumes/audit_log/<id>.sdk.jsonl (redacted).
    # The P3 replay gate needs ≥ 20 recorded jobs across skill classes; the
    # owner sets SDK_RECORD=1 in prod .env for a few days, then removes it.
    sdk_record: bool = False
```

`src/runner/sdk_record.py`:

```python
"""
Opt-in raw recorder for Claude Agent SDK messages (P0; spec §2.4, review #27).

SDK_RECORD=1 → every message `_run_in_process` receives is appended, in
arrival order, to volumes/audit_log/<job_id>.sdk.jsonl as JSON (dataclass →
dict, every string redacted). The per-job JSONL is a lossy derived view
(tool inputs truncated at 2000 chars, tool results previewed at 500, no
SystemMessage/RateLimitEvent); the P3 replay gate feeds THESE files through
ClaudeSdkExecutor and asserts a byte-identical derived JSONL, so what is
recorded must be exactly what the loop's isinstance dispatch saw.

Best-effort by contract: a recorder failure is logged once, the recorder
disables itself for the rest of the job, and the job never notices.
Recordings share the audit dir: retention.rotate_audit_logs archives them
with the per-job JSONL after 30 days (P3 copies its fixtures into
tests/replay/ before then); audit_index skips them (no job_started event).
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import logging
import re
import sys
from collections import Counter
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config import settings

logger = logging.getLogger(__name__)

SUFFIX = ".sdk.jsonl"
REDACTED = "[REDACTED]"

# Order matters: the bare-key pattern runs first and replaces the whole
# token; the others keep their prefix (group 1) and replace the value.
_KEY_PATTERN = re.compile(r"sk-ant-[A-Za-z0-9_-]{8,}")
_PREFIX_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)(authorization\s*:\s*bearer\s+)\S+"),
    re.compile(r"(?m)^(\s*(?:export\s+)?(?:CLAUDE_CODE_OAUTH_TOKEN|[A-Z0-9_]*(?:_TOKEN|_SECRET|_API_KEY|_PASSWORD))\s*=\s*)\S+"),
    re.compile(r"(?i)([\"']?(?:api[_-]?key|token|secret|password)[\"']?\s*[:=]\s*[\"']?)[^\s\"',}]{6,}"),
)


def redact(text: str) -> str:
    """Pure. Strip credential-shaped substrings; everything else byte-identical."""
    out = _KEY_PATTERN.sub(REDACTED, text)
    for pat in _PREFIX_PATTERNS:
        out = pat.sub(lambda m: m.group(1) + REDACTED, out)
    return out


def _redact_tree(value: Any) -> Any:
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, dict):
        return {str(k): _redact_tree(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact_tree(v) for v in value]
    return value


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def message_to_record(message: Any, *, seq: int, ts: str) -> dict[str, Any]:
    """Pure. One JSON-able line per SDK message; dataclass → dict, redacted."""
    rec: dict[str, Any] = {"seq": seq, "ts": ts, "type": type(message).__name__}
    if dataclasses.is_dataclass(message) and not isinstance(message, type):
        try:
            data = json.loads(json.dumps(dataclasses.asdict(message), default=str))
            rec["data"] = _redact_tree(data)
            return rec
        except Exception:  # noqa: BLE001 — fall through to repr
            pass
    rec["repr"] = redact(repr(message))[:2000]
    return rec


def header_record(job_id: str, *, model: str, cli_version: str, sdk_version: str,
                  prompt: str) -> dict[str, Any]:
    """The first line of a recording. Never the prompt text — only its hash/size."""
    return {
        "seq": 0, "ts": _now(), "type": "_recorder_start", "job_id": str(job_id),
        "model": model, "cli_version": cli_version, "sdk_version": sdk_version,
        "prompt_sha256": hashlib.sha256((prompt or "").encode("utf-8")).hexdigest(),
        "prompt_chars": len(prompt or ""),
    }


def sdk_version() -> str:
    try:
        from importlib.metadata import version
        return version("claude-agent-sdk")
    except Exception:  # noqa: BLE001
        return "unknown"


class SdkRecorder:
    """Best-effort append-only recorder for one job."""

    def __init__(self, path: Path, enabled: bool) -> None:
        self.path = path
        self.enabled = enabled
        self._seq = 0

    @classmethod
    def for_job(cls, job_id: str, *, enabled: bool | None = None,
                audit_dir: Path | None = None) -> "SdkRecorder":
        on = settings.sdk_record if enabled is None else enabled
        base = Path(audit_dir) if audit_dir is not None else settings.audit_log_dir
        return cls(base / f"{job_id}{SUFFIX}", bool(on))

    @property
    def job_id(self) -> str:
        return self.path.name[: -len(SUFFIX)]

    def start(self, **header: Any) -> None:
        self._write(header_record(self.job_id, **header))

    def record(self, message: Any) -> None:
        if not self.enabled:
            return
        self._seq += 1
        self._write(message_to_record(message, seq=self._seq, ts=_now()))

    def _write(self, rec: dict[str, Any]) -> None:
        if not self.enabled:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, default=str) + "\n")
        except Exception as exc:  # noqa: BLE001 — never fail a job for a recording
            self.enabled = False
            logger.warning("sdk recorder disabled for %s: %s", self.path.name, exc)


# ── Coverage (the "≥ 20 jobs across skill classes" deliverable) ────────────


def scan_recordings(audit_dir: Path) -> list[tuple[str, str | None]]:
    """(job_id, skill) per recording; skill from the sibling <id>.jsonl's job_started."""
    out: list[tuple[str, str | None]] = []
    for rec in sorted(Path(audit_dir).glob(f"*{SUFFIX}")):
        job_id = rec.name[: -len(SUFFIX)]
        skill: str | None = None
        sibling = rec.with_name(f"{job_id}.jsonl")
        if sibling.exists():
            for line in sibling.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    evt = json.loads(line)
                except ValueError:
                    continue
                if evt.get("kind") == "job_started":
                    skill = evt.get("skill") or None
                    break
        out.append((job_id, skill))
    return out


def coverage_report(pairs: Iterable[tuple[str, str | None]], *, min_jobs: int = 20,
                    min_classes: int = 3) -> dict[str, Any]:
    by_skill: Counter[str] = Counter((skill or "(none)") for _, skill in pairs)
    jobs = sum(by_skill.values())
    classes = len([k for k in by_skill if k != "(none)"])
    return {"jobs": jobs, "by_skill": dict(by_skill), "classes": classes,
            "ok": jobs >= min_jobs and classes >= min_classes}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m src.runner.sdk_record")
    sub = p.add_subparsers(dest="cmd", required=True)
    cov = sub.add_parser("coverage", help="how many jobs / skill classes are recorded")
    cov.add_argument("--audit-dir", default=None)
    cov.add_argument("--min-jobs", type=int, default=20)
    cov.add_argument("--min-classes", type=int, default=3)
    args = p.parse_args(argv)
    audit_dir = Path(args.audit_dir) if args.audit_dir else settings.audit_log_dir
    rep = coverage_report(scan_recordings(audit_dir), min_jobs=args.min_jobs,
                          min_classes=args.min_classes)
    for skill, n in sorted(rep["by_skill"].items(), key=lambda kv: -kv[1]):
        print(f"{n:5d}  {skill}")
    print(f"total {rep['jobs']} recorded job(s) across {rep['classes']} skill class(es) — "
          f"{'coverage OK' if rep['ok'] else 'NOT enough yet'} "
          f"(need ≥ {args.min_jobs} jobs, ≥ {args.min_classes} classes; spec §2.4)")
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Hook the recorder into `session._run_in_process`**

Add `from src.runner.sdk_record import SdkRecorder, sdk_version` to the imports. In `_run_in_process` (as left by Task 3):

```python
    capture = ResultCapture()
    recorder = SdkRecorder.for_job(job_id)          # SDK_RECORD=1 → <id>.sdk.jsonl; no-op otherwise

    client = ClaudeSDKClient(options=options)
    _running_sessions[job_id] = client

    try:
        async with client:
            recorder.start(model=options.model or "", cli_version=cli_version(),
                           sdk_version=sdk_version(), prompt=prompt)
            await client.query(prompt)

            async for message in client.receive_response():
                recorder.record(message)   # FIRST: every message, in order, before any branch continues/raises
                # Typed rate-limit signal — the CLI emits these on status
                # transitions; "rejected" means the current window is spent.
                if isinstance(message, RateLimitEvent):
```

Everything after that line is byte-identical.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pipenv run pytest tests/test_sdk_record.py tests/test_result_capture.py tests/test_api_terminal.py -v`
Expected: all PASS.

Live check (one real chat job, recorder on for this process only): `SDK_RECORD=1 pipenv run python -m src.runner.main` in a terminal with the launchd runner stopped (`launchctl bootout gui/$(id -u)/com.assistant.runner` … `launchctl kickstart -k gui/$(id -u)/com.assistant.runner` afterwards), enqueue `reply with the single word pong` (`kind='chat'`, `created_by='owner-terminal'`), then:
- `ls volumes/audit_log/<job>.sdk.jsonl` exists; `head -c 300 volumes/audit_log/<job>.sdk.jsonl` shows `"type": "_recorder_start"` with `prompt_sha256` and no prompt text;
- `python - <<'EOF'` … `[json.loads(l)["type"] for l in open(path)]` → starts `["_recorder_start", "SystemMessage", …]` and ends with `"ResultMessage"`;
- `grep -c 'sk-ant-\|Authorization: Bearer' volumes/audit_log/<job>.sdk.jsonl` → `0`;
- the job row is `completed` with the same columns Task 3 produced (the recorder changed nothing else);
- `pipenv run python -m src.runner.sdk_record coverage` prints `1  chat` and `NOT enough yet` (exit 1).

- [ ] **Step 6: Docs the lint gate needs, CHANGELOGs, commit**

- `.context/modules/runner/CONTEXT.md`: append `` , `src/runner/sdk_record.py` `` to the `**Paths:**` line.
- `.context/SYSTEM.md` module graph, insert after the `src/runner/result_capture.py` row, and append `, runner.sdk_record` to the `src/runner/session.py` row's Depends-on cell:

```markdown
| `src/runner/sdk_record.py` | Opt-in raw SDK message recorder (`SDK_RECORD=1` → `<id>.sdk.jsonl`, redacted) + `coverage` CLI — P3 replay fixtures | config | runner.session |
```

Run: `pipenv run pytest tests/test_doc_lint.py -q && pipenv run python scripts/lint_docs.py` → Expected: PASS and `All clean!`.

Prepend to `.context/modules/runner/CHANGELOG.md`:

```markdown
## 2026-09-25 — SDK_RECORD=1 raw SDK message recorder (P3 replay fixtures)

- **Agent task**: multi-model P0, Task 15 (spec §2.4, review #27).
- **Files changed**: `src/runner/sdk_record.py` (new: `redact`, `message_to_record`, `header_record`, `SdkRecorder`, `scan_recordings`, `coverage_report`, `python -m src.runner.sdk_record coverage`), `src/runner/session.py` (`_run_in_process`: recorder created before the client, `start()` after `async with client:`, `record(message)` first in the loop body), `src/config.py` (`sdk_record`), tests, runner CONTEXT Paths, SYSTEM.md row.
- **Why**: the per-job JSONL truncates tool inputs/results and drops SystemMessage/RateLimitEvent, so P3's replay gate had no fixtures; ≥ 20 recorded jobs across skill classes are required before P3.
- **Side effects**: none unless `SDK_RECORD=1` (default off). On: one `<id>.sdk.jsonl` per job in `volumes/audit_log/`, ~1–5 MB per agentic job; `retention.rotate_audit_logs` archives them with the JSONL after 30 days; `audit_index` skips them.
- **Gotchas discovered**: `dataclasses.asdict` on SDK messages holds non-JSON leaves for some block types — the recorder round-trips through `json.dumps(default=str)` first. The recorder must be the first statement in the loop body: the `RateLimitEvent` branch `continue`s and the error branches raise before `_handle_message`.
```

Prepend to `.context/modules/db/CHANGELOG.md`:

```markdown
## 2026-09-25 — settings.sdk_record

- `src/config.py`: `sdk_record: bool = False` (env `SDK_RECORD`); opt-in raw SDK recorder (runner Task 15).
```

```bash
git add src/runner/sdk_record.py src/runner/session.py src/config.py tests/test_sdk_record.py .context/modules/runner/CHANGELOG.md .context/modules/db/CHANGELOG.md .context/modules/runner/CONTEXT.md .context/SYSTEM.md
git commit -m "feat(runner): SDK_RECORD=1 opt-in raw SDK message recorder (redacted <id>.sdk.jsonl) + coverage CLI — P3 replay-gate fixtures"
```

---

### Task 16: Two-window cost-reconcile script — both windows, the per-kind step, and the weekly lane-budget seed

**Execution position:** 19 of 21 — previous: Task 12, next: Task 13 (see Global Constraints "Execution order").

- [ ] **Step 0: Prerequisite check** — `pipenv run python -c "from src.runner.result_capture import result_columns; print('ok')"` must print `ok` (Task 3's token columns feed the `--db` leg). If it fails: **execute Task 3 first.**

Spec §9 P0 row: "the cost-reconcile script printing **both** the trailing-30-d and trailing-7-d windows **and the per-kind step** (the §2.8 anchor) **and re-seeding lane budgets weekly**, §13 restated from the current run-rate". Spec §9 P0 **exit criterion**: "cost view reconciles with JSONL sums **at both windows and the 1-h rate**". Spec §2.8 says the same twice ("The P0 reconcile script emits both windows and the per-kind step every week and re-seeds the lane budgets"). Round-2 #18 is the critical row that made this a P0 deliverable and a *weekly* one: the whole budget model had been seeded from a 30-d mean taken **before** the alpha flywheel went live on 2026-09-23 and tripled daily load, so a 30-d-only report reproduces exactly the number the review rejected. List prices: `docs/research/llm-landscape-2026-09/claude-anthropic.md` §4 table (2026-09-24). Executed after Task 3 (the `--db` leg reads `jobs.cost_usd_list` and the two `cache_write_*` columns); the JSONL leg works on any checkout today.

**Files:**
- Create: `src/runner/pricing.py` (pure core), `scripts/cost-reconcile.py` (CLI)
- Modify: `scripts/install-launchd.sh` (a weekly `com.assistant.cost-reconcile` timer beside Task 12's canary timer, same `VENV_PY` resolution)
- Modify: `.context/modules/runner/CHANGELOG.md`, `.context/modules/runner/CONTEXT.md` (Paths line), `.context/modules/hosting/CHANGELOG.md` (the new timer), `.context/SYSTEM.md` (module row + script row)
- Test: `tests/test_pricing.py`, `tests/test_scripts_syntax.py` (append: the timer is installed and the script never says `pipenv run`)

**Interfaces:**
- Consumes: audit events `{"ts", "job_id", "kind", …}` (`audit_log.append`): `job_started.model` / `.skill` / `.job_kind` (verified field names on a real prod event) / `.origin_channel` (Task 4), `job_completed.usage` (keys `input_tokens, output_tokens, cache_read_input_tokens, cache_creation_input_tokens` **and the nested `cache_creation.ephemeral_{1h,5m}_input_tokens`**) and, from Task 3 on, `job_completed.cost_usd_list`; for `--db`: `jobs.resolved_model/status/completed_at/cost_usd_list` (Tasks 1, 3).
- Produces:
  - `pricing.Price` frozen dataclass `(input, cache_write_5m, cache_write_1h, cache_read, output)` — `Decimal` USD per MTok. **Both cache-write rates are kept in the table and both are used**, each against its own token count; there is no global TTL choice any more (spec §2.8, round-2 #19).
  - `pricing.LIST_PRICES: dict[str, Price]` keyed by family prefix: `claude-fable-5-1`, `claude-fable-5`, `claude-opus-5-5`, `claude-opus-5`, `claude-opus-4-8`, `claude-opus-4-7`, `claude-opus-4-6`, `claude-opus-4-5`, `claude-sonnet-5`, `claude-sonnet-4-6`, `claude-sonnet-4-5`, `claude-haiku-4-5` (values from the §4 table; `PRICES_AS_OF = "2026-09-24"`).
  - `pricing.family_for(model: str) -> str | None` — longest matching family prefix, case-insensitive, boundary at end-of-string or `-` (so `claude-opus-5-5` beats `claude-opus-5`, a date suffix maps to its family); `None` for bare aliases (`sonnet`) and unknown ids.
  - `pricing.price_usage(model, usage: dict) -> Decimal | None` — prices each cache-write bucket at **its own** rate: `usage["cache_creation"]["ephemeral_1h_input_tokens"] × cache_write_1h + …["ephemeral_5m_input_tokens"] × cache_write_5m`, falling back to the flat `cache_creation_input_tokens` **into the 1-h arm** when the nested object is absent (spec §2.3 row 007 / §2.8: the subscription's TTL is 1 h and prod records 100 % of writes there). **No `cache_write_ttl` parameter and no `--cache-write-ttl` flag** — the TTL is data, not an operator choice; round 1's single global rate was the ≈ 19 % error.
  - `pricing.lane_for(skill: str | None, job_kind: str | None, origin_channel: str | None) -> str` (pure) — the **P0 approximation** of the §2.5 lane set used only to shape the seed: `owner` for `telegram`/`web`/`pwa`/`cli` launches, `atlas` for a skill starting `atlas-`/`alpha-`/`momentum-`/`swing-`/`firm-`, `kernel` for `server-patch`/`server-deploy`/`deploy-director`/`review-and-improve`/`self-diagnose`, `utility` for `_`-prefixed and `chat` kinds, else `background`. `jobs.lane` is NULL in P0 (P2 fills it), so the seed is explicitly labelled an approximation in the output, and **`routing-policy.yml` consumption of the seed is P3** — P0 only writes the artefact.
  - `pricing.lane_seed(report: LedgerReport, *, multiplier: Decimal = Decimal("1.2")) -> dict[str, str]` — trailing-7-d `cost_usd_list` per lane × 1.2, the seed spec §2.8/§2.5 and round-2 #18 name. Written to `volumes/telemetry/lane_budget_seed.json` as `{"as_of", "window_days", "multiplier", "approximated_lanes": true, "weekly_budget_usd": {lane: str(Decimal)}}` — P2 reads it for `lanes.<lane>.weekly_budget`, P3 moves it into `routing-policy.yml`.
  - `pricing.JobCost` frozen dataclass `(job_id, model, family, skill, lane, completed_at: datetime | None, input, cache_read, cache_write_1h, cache_write_5m, output, usd_sdk: Decimal | None)` — `skill` = `job_started.skill` or `job_started.job_kind` (verified field names on a real prod event), which is the row label §2.8's "Where the tokens go" uses; `pricing.read_events(path) -> list[dict]`; `pricing.job_cost_from_events(job_id, events) -> JobCost | None` (needs `job_started` and `job_completed`; `completed_at` = the `job_completed` event's `ts`).
  - `pricing.ModelRow(model, jobs, input, cache_read, cache_write_1h, cache_write_5m, output, usd, usd_sdk, sdk_jobs)` — **one** `usd` column, each bucket at its own rate; `pricing.KindRow(kind, jobs, tokens, usd)` for the per-kind step table.
  - `pricing.LedgerReport` (`days: int`, `since`, `until`, `per_model: list[ModelRow]`, `per_kind: list[KindRow]`, `unpriced: list[ModelRow]`, `per_lane: dict[str, Decimal]`, `totals: ModelRow`, `median_job: dict`, `median_usd_by_family: dict[str, Decimal]`, `credit_signature: bool` = `totals.cache_write_5m > 0`); `pricing.summarize(jobs, *, since, until, days) -> LedgerReport`; `pricing.summarize_windows(jobs, *, until, windows: Sequence[int]) -> list[LedgerReport]`; `pricing.render_table(report) -> str` (per-model block, the **per-kind step** block, the unpriced block, medians, and a `⚠ 5-minute cache writes present — possible usage-credit overflow (spec §2.8)` line when `credit_signature`); `pricing.render_db_delta(report, rows) -> str`; `LedgerReport.to_dict()`.
  - `scripts/cost-reconcile.py [--windows 30,7] [--audit-dir P] [--db] [--json] [--seed-lane-budgets] [--seed-out PATH]` — exit 0 (a report), 2 on a missing audit dir, **1 when `credit_signature` is true** (a non-zero 5-m cache-write total is the usage-credits signature, spec §2.8, and the weekly timer's non-zero exit is what gets it noticed). `--windows` takes a comma list and **defaults to `30,7`**, so one invocation prints both blocks; `--days N` is kept as an alias for `--windows N`. Default audit dir = `settings.audit_log_dir` (on this box the dev `.env` points `SERVER_ROOT` at the prod tree, so the dev checkout reads the prod ledger).
  - Weekly launchd timer `com.assistant.cost-reconcile` (Mondays 07:10), installed by `install-launchd.sh` with the same `PATH`/`VENV_PY` env block and the same `VENV_PY` → `.venv` → `command -v python` resolution + `import src.config` guard Task 12 establishes, running `--windows 30,7 --db --seed-lane-budgets` and appending to `volumes/logs/cost-reconcile.log`. Never `pipenv run` (Task 12's gotcha).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_pricing.py`:

```python
"""
List-price ledger + 30-d reconcile core (P0; spec §2.8/§9, review #17). Pure.

Run: pipenv run pytest tests/test_pricing.py -v
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from src.runner.pricing import (
    LIST_PRICES,
    family_for,
    job_cost_from_events,
    lane_for,
    lane_seed,
    price_usage,
    render_db_delta,
    render_table,
    summarize,
    summarize_windows,
)


def _usage(inp=0, out=0, read=0, w1h=0, w5m=0):
    """The real prod shape: nested cache_creation + the flat key equal to their sum."""
    return {"input_tokens": inp, "output_tokens": out,
            "cache_read_input_tokens": read,
            "cache_creation_input_tokens": w1h + w5m,
            "cache_creation": {"ephemeral_1h_input_tokens": w1h,
                               "ephemeral_5m_input_tokens": w5m}}


# The FLEET median shape (spec §2.8: "fleet-median completed job 376 k cache-read /
# 47 k cache-write / 9.0 k output — a Sonnet atlas-report shape, ≈ $0.59"). It is
# NOT an Opus-5 job: §2.8 calls "median Opus 5 job ≈ $0.71" a mislabelling.
FLEET_MEDIAN = _usage(out=9_000, read=376_000, w1h=47_000)
# Today's real opus-5 atlas-swing-research job (spec §2.8, the DoneCard example).
OPUS5_REAL = _usage(out=47_000, read=2_400_000, w1h=111_000)
SINCE = datetime(2026, 9, 1, tzinfo=timezone.utc)
UNTIL = datetime(2026, 10, 1, tzinfo=timezone.utc)


def _events(model, usage, ts="2026-09-20T10:00:00+00:00", cost=None, skill="chat",
            channel="telegram"):
    done = {"ts": ts, "job_id": "x", "kind": "job_completed", "usage": usage, "duration_seconds": 5}
    if cost is not None:
        done["cost_usd_list"] = cost
    return [{"ts": ts, "job_id": "x", "kind": "job_started", "model": model,
             "skill": skill, "job_kind": skill, "origin_channel": channel}, done]


class TestPrices:
    def test_table_covers_every_family_the_fleet_uses(self):
        for fam in ("claude-opus-5", "claude-opus-4-7", "claude-opus-4-8", "claude-sonnet-4-6",
                    "claude-fable-5", "claude-haiku-4-5", "claude-opus-5-5", "claude-sonnet-5"):
            assert fam in LIST_PRICES

    def test_each_cache_write_bucket_is_priced_at_its_own_rate(self):
        # spec §2.8 / §2.3 row 007 (round-2 #19): 1-h writes at $10/M for Opus,
        # 5-m writes at $6.25/M; never one global rate.
        p = price_usage("claude-opus-5", _usage(w1h=1_000_000))
        assert p == Decimal(10)
        assert price_usage("claude-opus-5", _usage(w5m=1_000_000)) == Decimal("6.25")
        assert price_usage("claude-opus-5", _usage(w1h=1_000_000, w5m=1_000_000)) == Decimal("16.25")

    def test_flat_cache_creation_key_falls_back_to_the_1h_rate(self):
        # Older rows carry only the flat key; prod records 100 % of writes as 1-h,
        # so the flat value must NOT be priced at the 5-m rate.
        legacy = {"cache_creation_input_tokens": 1_000_000}
        assert price_usage("claude-opus-5", legacy) == Decimal(10)

    def test_the_real_opus5_job_is_the_specs_3_49(self):
        # spec §2.8, as round 2 left it: "today's real opus-5
        # atlas-swing-research job (2.40 M read / 111 k 1-h write / 47 k out)
        # = $3.49, the DoneCard example in §4.2". Exact, at the 1-h rate:
        # 2.40M×$0.50 + 111k×$10 + 47k×$25 = 1.200 + 1.110 + 1.175.
        assert round(price_usage("claude-opus-5", OPUS5_REAL), 2) == Decimal("3.49")
        # Round 1's "$0.71" for the same-shaped job used the 5-m rate.
        assert price_usage("claude-opus-5", OPUS5_REAL) != price_usage(
            "claude-opus-5", _usage(out=47_000, read=2_400_000, w5m=111_000))

    def test_the_fleet_median_SHAPE_prices_at_the_sonnet_1h_rate(self):
        # spec §2.8's median shape is 376 k cache-read / 47 k cache-write /
        # 9.0 k output on "a Sonnet atlas-report shape": 376k×$0.30 +
        # 47k×$6 + 9k×$15 = $0.5298. NOTE: §2.8's "fleet ≈ $0.59" is the
        # median of per-job COSTS, a different statistic from the cost of the
        # median shape — the report prints both (median_job and
        # median_usd_by_family), and Step 5 compares the per-job median
        # against §2.8's $0.59 / $3.43, never this figure.
        assert price_usage("claude-sonnet-4-6", FLEET_MEDIAN) == Decimal("0.5298")

    def test_longest_prefix_wins(self):
        assert family_for("claude-opus-5-5") == "claude-opus-5-5"
        assert family_for("claude-opus-5") == "claude-opus-5"
        assert family_for("claude-opus-5-20260401") == "claude-opus-5"
        assert family_for("claude-fable-5-1") == "claude-fable-5-1"
        assert family_for("claude-haiku-4-5-20251001") == "claude-haiku-4-5"
        assert family_for("CLAUDE-SONNET-4-6") == "claude-sonnet-4-6"

    def test_unknown_model_is_reported_not_priced(self):
        assert family_for("sonnet") is None
        assert family_for("claude-opus-9") is None and family_for("claude-opus-50") is None
        assert price_usage("sonnet", {"output_tokens": 5}) is None


class TestLanes:
    def test_lane_for_is_the_documented_p0_approximation(self):
        assert lane_for("chat", "chat", "telegram") == "owner"
        assert lane_for("atlas-report", "atlas-report", "scheduler") == "atlas"
        assert lane_for("alpha-research", "alpha-research", "scheduler") == "atlas"
        assert lane_for("review-and-improve", "review-and-improve", "system") == "kernel"
        assert lane_for(None, "_writeback", "system") == "utility"
        assert lane_for("project-update-poll", "task", "scheduler") == "background"


class TestLedger:
    def test_job_cost_from_events_and_summary(self):
        a = job_cost_from_events("a", _events("claude-opus-5", OPUS5_REAL, cost=3.485,
                                              skill="atlas-swing-research", channel="scheduler"))
        b = job_cost_from_events("b", _events("claude-sonnet-4-6", _usage(out=1000)))
        c = job_cost_from_events("c", _events("sonnet", _usage(out=10)))
        old = job_cost_from_events("d", _events("claude-opus-5", _usage(out=10),
                                                ts="2026-07-01T00:00:00+00:00"))
        rep = summarize([a, b, c, old], since=SINCE, until=UNTIL, days=30)
        assert rep.days == 30
        assert rep.totals.jobs == 3                      # `old` is outside the window
        assert [r.model for r in rep.unpriced] == ["sonnet"]
        opus = next(r for r in rep.per_model if r.model == "claude-opus-5")
        assert opus.jobs == 1 and opus.cache_read == 2_400_000
        assert opus.cache_write_1h == 111_000 and opus.cache_write_5m == 0
        assert round(opus.usd, 2) == Decimal("3.49")     # ONE usd column, each bucket at its rate
        assert opus.usd_sdk == Decimal("3.485") and opus.sdk_jobs == 1
        sonnet = next(r for r in rep.per_model if r.model == "claude-sonnet-4-6")
        assert sonnet.usd_sdk is None and sonnet.sdk_jobs == 0      # pre-P0 jobs carry no cost_usd_list
        assert set(rep.median_job) == {"cache_read", "cache_write_1h", "cache_write_5m",
                                       "output", "input"}
        assert round(rep.median_usd_by_family["claude-opus-5"], 2) == Decimal("3.49")
        # The per-kind step table — the §2.8 "where the tokens go" view.
        kinds = {k.kind: k for k in rep.per_kind}
        assert kinds["atlas-swing-research"].jobs == 1
        assert kinds["atlas-swing-research"].tokens == 2_400_000 + 111_000 + 47_000
        assert rep.credit_signature is False
        table = render_table(rep)
        for needle in ("claude-opus-5", "unpriced", "sonnet", "atlas-swing-research",
                       "by kind", "30 d"):
            assert needle in table, needle

    def test_five_minute_writes_raise_the_credit_signature(self):
        # spec §2.8: "a cache_write_5m_tokens > 0 reading, since the TTL drop to
        # 5 m is itself the credits signature".
        a = job_cost_from_events("a", _events("claude-opus-5", _usage(w5m=1000)))
        rep = summarize([a], since=SINCE, until=UNTIL, days=30)
        assert rep.credit_signature is True
        assert "possible usage-credit overflow" in render_table(rep)

    def test_two_windows_in_one_pass(self):
        # spec §9 P0: "printing BOTH the trailing-30-d and trailing-7-d windows".
        recent = job_cost_from_events("r", _events("claude-opus-5", OPUS5_REAL,
                                                   ts="2026-09-28T10:00:00+00:00"))
        older = job_cost_from_events("o", _events("claude-opus-5", OPUS5_REAL,
                                                  ts="2026-09-10T10:00:00+00:00"))
        until = datetime(2026, 9, 30, tzinfo=timezone.utc)
        reps = summarize_windows([recent, older], until=until, windows=(30, 7))
        assert [r.days for r in reps] == [30, 7]
        assert reps[0].totals.jobs == 2 and reps[1].totals.jobs == 1

    def test_lane_seed_is_trailing_7d_times_1_2(self):
        # spec §2.8/§2.5, round-2 #18: the seed is trailing-7-d × 1.2, re-seeded
        # weekly by THIS script — never the stale 30-d mean.
        a = job_cost_from_events("a", _events("claude-opus-5", OPUS5_REAL,
                                              skill="atlas-report", channel="scheduler"))
        b = job_cost_from_events("b", _events("claude-sonnet-4-6", FLEET_MEDIAN,
                                              skill="chat", channel="telegram"))
        rep = summarize([a, b], since=SINCE, until=UNTIL, days=7)
        seed = lane_seed(rep)
        assert Decimal(seed["atlas"]) == (Decimal("3.485") * Decimal("1.2")).quantize(Decimal("0.01"))
        assert Decimal(seed["owner"]) == (Decimal("0.5298") * Decimal("1.2")).quantize(Decimal("0.01"))

    def test_missing_job_started_gives_none(self):
        assert job_cost_from_events("x", [{"ts": "t", "job_id": "x", "kind": "job_completed", "usage": {}}]) is None

    def test_db_delta_table(self):
        a = job_cost_from_events("a", _events("claude-opus-5", OPUS5_REAL, cost=3.485))
        rep = summarize([a], since=SINCE, until=UNTIL, days=30)
        out = render_db_delta(rep, [("claude-opus-5", 1, Decimal("3.485")), ("claude-opus-4-7", 2, Decimal("1.0"))])
        assert "claude-opus-5" in out and "0.0%" in out
        assert "claude-opus-4-7" in out and "JSONL: none" in out   # rows only the DB has are shown, never hidden
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pipenv run pytest tests/test_pricing.py -v`
Expected: collection error `ModuleNotFoundError: No module named 'src.runner.pricing'`.

- [ ] **Step 3: Implement `src/runner/pricing.py`**

```python
"""
List-price ledger for Claude usage (P0; spec §2.8, §9 P0 row, review #17).

`cost_usd_list` is a LIST-PRICE EQUIVALENT — never a bill (the fleet runs on
the Max subscription). Two consumers:
  * scripts/cost-reconcile.py — the §2.8 calibration table from the JSONL
    ledger (`job_started.model` × `job_completed.usage` × list price) and the
    P0 exit criterion "cost view reconciles with JSONL sums for 30 d"
    (JSONL sums vs SUM(jobs.cost_usd_list) — the SDK's total_cost_usd).
  * P2's provider_ledger / CostCard (same table, per purpose).

Prices: docs/research/llm-landscape-2026-09/claude-anthropic.md §4 (fetched
2026-09-24). EACH cache-write bucket is priced at ITS OWN rate — 1-h writes at
cache_write_1h, 5-m writes at cache_write_5m, read from
usage.cache_creation.ephemeral_{1h,5m}_input_tokens (spec §2.3 row 007, §2.8).
There is no global TTL setting: the subscription's TTL is 1 h and prod records
100 % of writes there, so a single 5-m rate made round 1's anchor ≈ 19 % low,
and a non-zero 5-m reading is itself the usage-credits signature (§2.8).
Pure module: no I/O beyond read_events() and write_lane_seed().
"""

from __future__ import annotations

import json
import statistics
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

PRICES_AS_OF = "2026-09-24"
SDK_RECORD_SUFFIX = ".sdk.jsonl"
_M = Decimal(1_000_000)


@dataclass(frozen=True)
class Price:
    input: Decimal
    cache_write_5m: Decimal
    cache_write_1h: Decimal
    cache_read: Decimal
    output: Decimal


def _p(i, w5, w1, r, o) -> Price:
    return Price(Decimal(str(i)), Decimal(str(w5)), Decimal(str(w1)), Decimal(str(r)), Decimal(str(o)))


# claude-anthropic.md §4 "API list prices ($/MTok)"; family prefix → price.
LIST_PRICES: dict[str, Price] = {
    "claude-fable-5-1": _p(10, 12.50, 20, 0.25, 50),
    "claude-fable-5":   _p(10, 12.50, 20, 1.00, 50),
    "claude-opus-5-5":  _p(4, 5, 8, 0.20, 20),
    "claude-opus-5":    _p(5, 6.25, 10, 0.50, 25),
    "claude-opus-4-8":  _p(5, 6.25, 10, 0.50, 25),
    "claude-opus-4-7":  _p(5, 6.25, 10, 0.50, 25),
    "claude-opus-4-6":  _p(5, 6.25, 10, 0.50, 25),
    "claude-opus-4-5":  _p(5, 6.25, 10, 0.50, 25),
    "claude-sonnet-5":  _p(2, 2.50, 4, 0.20, 10),
    "claude-sonnet-4-6": _p(3, 3.75, 6, 0.30, 15),
    "claude-sonnet-4-5": _p(3, 3.75, 6, 0.30, 15),
    "claude-haiku-4-5": _p(1, 1.25, 2, 0.10, 5),
}

_USAGE_KEYS = {"input": "input_tokens", "output": "output_tokens",
               "cache_read": "cache_read_input_tokens", "cache_write": "cache_creation_input_tokens"}

# P0 lane approximation (jobs.lane is NULL until P2 fills it). Only used to
# shape the weekly budget seed, and labelled "approximated" in its output.
_ATLAS_PREFIXES = ("atlas-", "alpha-", "momentum-", "swing-", "firm-")
_KERNEL_SKILLS = frozenset({"server-patch", "server-deploy", "deploy-director",
                            "review-and-improve", "self-diagnose"})
_OWNER_CHANNELS = frozenset({"telegram", "web", "pwa", "cli"})


def lane_for(skill: str | None, job_kind: str | None, origin_channel: str | None) -> str:
    """The §2.5 lane a job would land in — the P0 APPROXIMATION (jobs.lane is
    NULL in P0; P2 fills it and P3 moves the seed into routing-policy.yml)."""
    s = (skill or "").strip().lower()
    k = (job_kind or "").strip().lower()
    if (origin_channel or "").strip().lower() in _OWNER_CHANNELS:
        return "owner"
    if any(s.startswith(p) for p in _ATLAS_PREFIXES):
        return "atlas"
    if s in _KERNEL_SKILLS:
        return "kernel"
    if k.startswith("_") or s.startswith("_") or k == "chat":
        return "utility"
    return "background"


def cache_write_buckets(usage: dict[str, Any] | None) -> tuple[int, int]:
    """(1-hour, 5-minute) cache-write tokens. The nested cache_creation object
    is authoritative; when it is absent the flat cache_creation_input_tokens is
    attributed to the 1-HOUR arm (spec §2.8: prod records 100 % as 1-h, and the
    flat key equals the 1-h figure on every row checked)."""
    nested = (usage or {}).get("cache_creation")
    if isinstance(nested, dict) and (
            "ephemeral_1h_input_tokens" in nested or "ephemeral_5m_input_tokens" in nested):
        return (_tok(nested, "ephemeral_1h_input_tokens"),
                _tok(nested, "ephemeral_5m_input_tokens"))
    return _tok(usage, "cache_creation_input_tokens"), 0


def family_for(model: str) -> str | None:
    """Longest family prefix with a boundary (end or '-') after it; None for aliases/unknown."""
    m = (model or "").strip().lower()
    best: str | None = None
    for fam in LIST_PRICES:
        if m == fam or m.startswith(fam + "-"):
            if best is None or len(fam) > len(best):
                best = fam
    return best


def _tok(usage: dict[str, Any] | None, key: str) -> int:
    try:
        return int((usage or {}).get(key) or 0)
    except (TypeError, ValueError):
        return 0


def price_usage(model: str, usage: dict[str, Any] | None) -> Decimal | None:
    """List-price equivalent for one job's usage. Each cache-write bucket at
    its own rate (spec §2.3 row 007, §2.8); None for a bare alias / unknown id
    so the caller can COUNT it under `unpriced` instead of mispricing it."""
    fam = family_for(model)
    if fam is None:
        return None
    p = LIST_PRICES[fam]
    w1h, w5m = cache_write_buckets(usage)
    total = (Decimal(_tok(usage, "input_tokens")) * p.input
             + Decimal(_tok(usage, "output_tokens")) * p.output
             + Decimal(_tok(usage, "cache_read_input_tokens")) * p.cache_read
             + Decimal(w1h) * p.cache_write_1h
             + Decimal(w5m) * p.cache_write_5m) / _M
    return total.normalize() if total else Decimal(0)


@dataclass(frozen=True)
class JobCost:
    job_id: str
    model: str
    family: str | None
    skill: str                   # job_started.skill or .job_kind — the §2.8 row label
    lane: str                    # lane_for(...) — P0 approximation, seed only
    completed_at: datetime | None
    input: int
    cache_read: int
    cache_write_1h: int
    cache_write_5m: int
    output: int
    usd_sdk: Decimal | None      # job_completed.cost_usd_list (P0+), the SDK's total_cost_usd

    @property
    def usage(self) -> dict[str, Any]:
        return {"input_tokens": self.input, "output_tokens": self.output,
                "cache_read_input_tokens": self.cache_read,
                "cache_creation_input_tokens": self.cache_write_1h + self.cache_write_5m,
                "cache_creation": {"ephemeral_1h_input_tokens": self.cache_write_1h,
                                   "ephemeral_5m_input_tokens": self.cache_write_5m}}

    @property
    def tokens(self) -> int:
        return (self.input + self.cache_read + self.cache_write_1h
                + self.cache_write_5m + self.output)

    @property
    def usd(self) -> Decimal | None:
        return price_usage(self.model, self.usage)


def read_events(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            evt = json.loads(line)
        except ValueError:
            continue
        if isinstance(evt, dict):
            out.append(evt)
    return out


def _ts(value: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def job_cost_from_events(job_id: str, events: Iterable[dict[str, Any]]) -> JobCost | None:
    started = done = None
    for evt in events:
        kind = evt.get("kind")
        if kind == "job_started" and started is None:
            started = evt
        elif kind == "job_completed":
            done = evt                      # last terminal wins (reconcile.py semantics)
    if started is None or done is None:
        return None
    model = str(started.get("model") or "")
    usage = done.get("usage") if isinstance(done.get("usage"), dict) else {}
    sdk = done.get("cost_usd_list")
    skill = str(started.get("skill") or started.get("job_kind") or "(none)")
    w1h, w5m = cache_write_buckets(usage)
    return JobCost(
        job_id=job_id, model=model, family=family_for(model),
        skill=skill,
        lane=lane_for(started.get("skill"), started.get("job_kind"),
                      started.get("origin_channel")),
        completed_at=_ts(done.get("ts")),
        input=_tok(usage, "input_tokens"), cache_read=_tok(usage, "cache_read_input_tokens"),
        cache_write_1h=w1h, cache_write_5m=w5m, output=_tok(usage, "output_tokens"),
        usd_sdk=Decimal(str(sdk)) if sdk is not None else None,
    )


@dataclass
class ModelRow:
    model: str
    jobs: int = 0
    input: int = 0
    cache_read: int = 0
    cache_write_1h: int = 0
    cache_write_5m: int = 0
    output: int = 0
    usd: Decimal = Decimal(0)        # each bucket at its own rate (spec §2.8)
    usd_sdk: Decimal | None = None
    sdk_jobs: int = 0

    def add(self, jc: JobCost) -> None:
        self.jobs += 1
        self.input += jc.input
        self.cache_read += jc.cache_read
        self.cache_write_1h += jc.cache_write_1h
        self.cache_write_5m += jc.cache_write_5m
        self.output += jc.output
        self.usd += jc.usd or Decimal(0)
        if jc.usd_sdk is not None:
            self.usd_sdk = (self.usd_sdk or Decimal(0)) + jc.usd_sdk
            self.sdk_jobs += 1

    @property
    def tokens(self) -> int:
        return (self.input + self.cache_read + self.cache_write_1h
                + self.cache_write_5m + self.output)


@dataclass
class KindRow:
    """The §2.8 "where the tokens go" step, per skill — the view that makes the
    alpha-flywheel line item visible instead of averaged away."""
    kind: str
    jobs: int = 0
    tokens: int = 0
    usd: Decimal = Decimal(0)

    def add(self, jc: JobCost) -> None:
        self.jobs += 1
        self.tokens += jc.tokens
        self.usd += jc.usd or Decimal(0)


@dataclass
class LedgerReport:
    since: datetime
    until: datetime
    days: int
    per_model: list[ModelRow] = field(default_factory=list)
    per_kind: list[KindRow] = field(default_factory=list)
    unpriced: list[ModelRow] = field(default_factory=list)
    per_lane: dict[str, Decimal] = field(default_factory=dict)
    totals: ModelRow = field(default_factory=lambda: ModelRow("total"))
    median_job: dict[str, int] = field(default_factory=dict)
    median_usd_by_family: dict[str, Decimal] = field(default_factory=dict)

    @property
    def credit_signature(self) -> bool:
        """A 5-m cache write on this account means the TTL dropped to 5 m, which
        is the usage-credits signature (spec §2.8 metered-spend tripwires)."""
        return self.totals.cache_write_5m > 0

    def to_dict(self) -> dict[str, Any]:
        row = lambda r: {k: (str(v) if isinstance(v, Decimal) else v) for k, v in r.__dict__.items()}  # noqa: E731
        return {"since": self.since.isoformat(), "until": self.until.isoformat(),
                "days": self.days,
                "per_model": [row(r) for r in self.per_model],
                "per_kind": [row(r) for r in self.per_kind],
                "unpriced": [row(r) for r in self.unpriced],
                "per_lane": {k: str(v) for k, v in self.per_lane.items()},
                "totals": row(self.totals), "median_job": self.median_job,
                "median_usd_by_family": {k: str(v) for k, v in self.median_usd_by_family.items()},
                "credit_signature": self.credit_signature, "prices_as_of": PRICES_AS_OF}


def summarize(jobs: Iterable[JobCost], *, since: datetime, until: datetime,
              days: int) -> LedgerReport:
    rep = LedgerReport(since=since, until=until, days=days)
    rows: dict[str, ModelRow] = {}
    kinds: dict[str, KindRow] = {}
    unpriced: dict[str, ModelRow] = {}
    lanes: dict[str, Decimal] = {}
    kept: list[JobCost] = []
    by_family: dict[str, list[Decimal]] = {}
    for jc in jobs:
        if jc.completed_at is None or not (since <= jc.completed_at < until):
            continue
        kept.append(jc)
        target = rows if jc.family is not None else unpriced
        key = jc.family or (jc.model or "(empty)")
        target.setdefault(key, ModelRow(key)).add(jc)
        kinds.setdefault(jc.skill, KindRow(jc.skill)).add(jc)
        lanes[jc.lane] = lanes.get(jc.lane, Decimal(0)) + (jc.usd or Decimal(0))
        if jc.family is not None:
            by_family.setdefault(jc.family, []).append(jc.usd or Decimal(0))
        rep.totals.add(jc)
    rep.per_model = sorted(rows.values(), key=lambda r: -r.usd)
    rep.per_kind = sorted(kinds.values(), key=lambda r: -r.tokens)
    rep.unpriced = sorted(unpriced.values(), key=lambda r: -r.jobs)
    rep.per_lane = dict(sorted(lanes.items(), key=lambda kv: -kv[1]))
    if kept:
        rep.median_job = {k: int(statistics.median(getattr(j, k) for j in kept))
                          for k in ("cache_read", "cache_write_1h", "cache_write_5m",
                                    "output", "input")}
        rep.median_usd_by_family = {fam: statistics.median(vals)
                                    for fam, vals in sorted(by_family.items())}
    return rep


def summarize_windows(jobs: Iterable[JobCost], *, until: datetime,
                      windows: Sequence[int] = (30, 7)) -> list[LedgerReport]:
    """One report per window, in the order given. Spec §9 P0 requires BOTH the
    trailing 30 d and the trailing 7 d in one invocation, because the load's
    largest step (the alpha flywheel, 2026-09-23) post-dates the 30-d mean."""
    kept = list(jobs)
    return [summarize(kept, since=until - timedelta(days=d), until=until, days=d)
            for d in windows]


def lane_seed(rep: LedgerReport, *,
              multiplier: Decimal = Decimal("1.2")) -> dict[str, str]:
    """Per-lane weekly budget seed = this report's per-lane cost × 1.2 (spec
    §2.5 `lanes.<lane>.weekly_budget`, §2.8, round-2 #18: re-seeded WEEKLY from
    the trailing 7 d, never from the 30-d mean). Lanes are the P0 approximation
    of lane_for(); P2 recomputes them from jobs.lane and P3 takes the file over
    into routing-policy.yml."""
    return {lane: str((usd * multiplier).quantize(Decimal("0.01")))
            for lane, usd in rep.per_lane.items()}


def write_lane_seed(rep: LedgerReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "as_of": rep.until.isoformat(), "window_days": rep.days,
        "multiplier": "1.2", "approximated_lanes": True,
        "weekly_budget_usd": lane_seed(rep),
    }, indent=2) + "\n", encoding="utf-8")
    return path


def _fmt_m(n: int) -> str:
    return f"{n / 1_000_000:8.1f}M"


def render_table(rep: LedgerReport) -> str:
    lines = [f"== trailing {rep.days} d == {rep.since:%Y-%m-%d} → {rep.until:%Y-%m-%d} "
             f"(prices as of {PRICES_AS_OF}; list-equivalent, never a bill; "
             f"each cache-write bucket at its own rate)",
             f"{'model':<20} {'jobs':>5} {'cache_read':>10} {'cw_1h':>9} {'cw_5m':>9} {'output':>9} {'$ list':>10} {'$ SDK (n)':>14}"]
    for r in rep.per_model + [rep.totals]:
        sdk = f"{r.usd_sdk:.2f} ({r.sdk_jobs})" if r.usd_sdk is not None else "—"
        lines.append(f"{r.model:<20} {r.jobs:>5} {_fmt_m(r.cache_read):>10} {_fmt_m(r.cache_write_1h):>9} {_fmt_m(r.cache_write_5m):>9} {_fmt_m(r.output):>9} {r.usd:>10.2f} {sdk:>14}")
    if rep.unpriced:
        lines.append("unpriced (bare alias / unknown id — counted, never priced):")
        for r in rep.unpriced:
            lines.append(f"  {r.model:<18} {r.jobs:>5} {_fmt_m(r.cache_read):>10} {_fmt_m(r.cache_write_1h):>9} {_fmt_m(r.cache_write_5m):>9} {_fmt_m(r.output):>9}")
    if rep.per_kind:
        # The §2.8 step: three skills are ≈ 38 % of the window and one of them
        # (alpha-research) tripled the load on 2026-09-23. A per-model table
        # alone hides that.
        lines.append(f"-- by kind (the §2.8 step) --   {'jobs':>5} {'tokens':>10} {'$ list':>10}")
        for k in rep.per_kind[:15]:
            share = (k.tokens / rep.totals.tokens * 100) if rep.totals.tokens else 0.0
            lines.append(f"  {k.kind:<28} {k.jobs:>5} {_fmt_m(k.tokens):>10} {k.usd:>10.2f}  ({share:4.1f} %)")
    if rep.per_lane:
        lines.append("-- by lane (P0 approximation of §2.5 lanes; jobs.lane is NULL until P2) --")
        for lane, usd in rep.per_lane.items():
            lines.append(f"  {lane:<28} {usd:>10.2f}")
    if rep.median_job:
        m = rep.median_job
        lines.append(f"median job: {m['cache_read'] / 1000:.0f}k cache-read / "
                     f"{m['cache_write_1h'] / 1000:.0f}k 1-h write / "
                     f"{m['cache_write_5m'] / 1000:.0f}k 5-m write / {m['output'] / 1000:.1f}k output")
    if rep.median_usd_by_family:
        meds = "  ".join(f"{fam.replace('claude-', '')} ${v:.2f}"
                         for fam, v in rep.median_usd_by_family.items())
        lines.append(f"median $ per job by family: {meds}")
    if rep.credit_signature:
        lines.append("⚠ 5-minute cache writes present — possible usage-credit overflow "
                     "(spec §2.8 metered-spend tripwires): the TTL drop to 5 m is the "
                     "credits signature. Check claude.ai billing (D3) before anything else.")
    return "\n".join(lines)


def render_db_delta(rep: LedgerReport, rows: Iterable[tuple[str, int, Decimal | None]]) -> str:
    """Per-model SUM(jobs.cost_usd_list) vs the JSONL usd_sdk sum — the reconcile."""
    jsonl = {r.model: r for r in rep.per_model}
    seen: set[str] = set()
    lines = [f"{'model':<20} {'DB jobs':>7} {'DB $':>10} {'JSONL $ (SDK)':>14} {'delta':>8}"]
    for model, n, usd in rows:
        fam = family_for(model or "") or (model or "(empty)")
        seen.add(fam)
        db = Decimal(str(usd or 0))
        j = jsonl.get(fam)
        if j is None or j.usd_sdk is None:
            lines.append(f"{fam:<20} {n:>7} {db:>10.2f} {'JSONL: none':>14} {'':>8}")
            continue
        delta = (db - j.usd_sdk) / j.usd_sdk * 100 if j.usd_sdk else Decimal(0)
        lines.append(f"{fam:<20} {n:>7} {db:>10.2f} {j.usd_sdk:>14.2f} {delta:>7.1f}%")
    for fam, j in jsonl.items():
        if fam not in seen and j.usd_sdk is not None:
            lines.append(f"{fam:<20} {'DB: none':>7} {'':>10} {j.usd_sdk:>14.2f} {'':>8}")
    return "\n".join(lines)
```

- [ ] **Step 4: Write `scripts/cost-reconcile.py`**

```python
#!/usr/bin/env python
"""
scripts/cost-reconcile.py — the spec §2.8 calibration anchor from the JSONL
ledger at BOTH windows, the per-kind step, the weekly lane-budget seed, and the
P0 exit criterion "cost view reconciles with JSONL sums at both windows and the
1-h rate" (--db: SUM(jobs.cost_usd_list) per model vs the JSONL SDK sum).

Run: pipenv run python scripts/cost-reconcile.py [--windows 30,7] [--db]
                                                 [--seed-lane-budgets] [--json]
     (from the dev checkout, settings.audit_log_dir is the prod tree — see
      docs/superpowers/plans/2026-09-25-multi-model-platform-p0.md Task 16)

WIRED INTO LAUNCHD, weekly (com.assistant.cost-reconcile, Mon 07:10): spec §2.8
requires the reconcile to emit both windows and the per-kind step "every week"
and to re-seed the lane budgets, because the 30-d mean predates the alpha
flywheel. Exit 1 when 5-minute cache writes appear (the usage-credits
signature, §2.8) so the timer's failure is what gets it noticed.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import settings  # noqa: E402
from src.runner import pricing  # noqa: E402


async def _db_rows(since: datetime, until: datetime):
    from sqlalchemy import text

    from src.db import async_session
    async with async_session() as s:
        res = await s.execute(text(
            "SELECT COALESCE(resolved_model, ''), COUNT(*), COALESCE(SUM(cost_usd_list), 0) "
            "FROM jobs WHERE status = 'completed' AND completed_at >= :since AND completed_at < :until "
            "GROUP BY 1 ORDER BY 3 DESC"), {"since": since, "until": until})
        return [(m, int(n), usd) for m, n, usd in res.all()]


def _windows(spec: str) -> list[int]:
    out = [int(x) for x in str(spec).replace(" ", "").split(",") if x]
    return out or [30, 7]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    # Spec §9 P0: BOTH windows in one invocation. --days N is kept as an alias.
    p.add_argument("--windows", default="30,7",
                   help="comma list of trailing-day windows (default 30,7)")
    p.add_argument("--days", type=int, default=None, help="alias for --windows N")
    p.add_argument("--audit-dir", default=None)
    p.add_argument("--db", action="store_true", help="also reconcile against jobs.cost_usd_list")
    p.add_argument("--json", action="store_true")
    p.add_argument("--seed-lane-budgets", action="store_true",
                   help="write the trailing-7-d × 1.2 per-lane seed (spec §2.5/§2.8)")
    p.add_argument("--seed-out", default=None,
                   help="default volumes/telemetry/lane_budget_seed.json")
    args = p.parse_args(argv)
    windows = [args.days] if args.days else _windows(args.windows)
    audit_dir = Path(args.audit_dir) if args.audit_dir else settings.audit_log_dir
    if not audit_dir.is_dir():
        print(f"no such audit dir: {audit_dir}", file=sys.stderr)
        return 2
    until = datetime.now(timezone.utc)
    jobs = []
    for f in sorted(audit_dir.glob("*.jsonl")):
        if f.name == "INDEX.jsonl" or f.name.endswith(pricing.SDK_RECORD_SUFFIX):
            continue
        jc = pricing.job_cost_from_events(f.stem, pricing.read_events(f))
        if jc is not None:
            jobs.append(jc)
    reports = pricing.summarize_windows(jobs, until=until, windows=windows)
    if args.json:
        print(json.dumps([r.to_dict() for r in reports], indent=2))
    else:
        for rep in reports:
            print(pricing.render_table(rep))
            print()
    if args.db:
        for rep in reports:
            print(f"-- DB reconcile, trailing {rep.days} d --")
            print(pricing.render_db_delta(rep, asyncio.run(_db_rows(rep.since, rep.until))))
            print()
    if args.seed_lane_budgets:
        # The seed is ALWAYS the shortest window (spec §2.8: trailing-7-d × 1.2,
        # never the 30-d mean, which predates the alpha flywheel).
        seed_rep = min(reports, key=lambda r: r.days)
        out = Path(args.seed_out) if args.seed_out else (
            settings.server_root / "volumes" / "telemetry" / "lane_budget_seed.json")
        pricing.write_lane_seed(seed_rep, out)
        print(f"lane budget seed (trailing {seed_rep.days} d × 1.2) → {out}")
        print(json.dumps(pricing.lane_seed(seed_rep), indent=2))
    # A 5-minute cache write is the usage-credits signature (§2.8): non-zero exit
    # so the weekly timer's failure is what surfaces it.
    return 1 if any(r.credit_signature for r in reports) else 0


if __name__ == "__main__":
    sys.exit(main())
```

`chmod +x scripts/cost-reconcile.py`.

- [ ] **Step 5: Run the tests, then the script against the real ledger**

Run: `pipenv run pytest tests/test_pricing.py -v` → Expected: all PASS.

Run: `pipenv run python scripts/cost-reconcile.py` (defaults to `--windows 30,7`) → **two blocks**, each with per-model rows for `claude-opus-5`, `claude-opus-4-7`, `claude-opus-4-8`, `claude-sonnet-4-6`, the `by kind` step table, the by-lane block, and the two median lines.

Compare with spec §2.8 **as round 2 left it** — these are the current figures; the round-1 numbers (`≈ $809/month`, `$0.71`, `opus-5 111 jobs $361`) are superseded and §2.8 calls the $809 figure "≈ 19 % low" because it used the 5-m rate:

| §2.8 figure (trailing 30 d to 2026-09-25) | Expected in the 30-d block |
|---|---|
| **≈ $963/month-equivalent** at the 1-h rate | `total` row `$ list` |
| opus-5 **109 jobs $414**, opus-4-7 **168 $255**, sonnet-4-6 **337 $151**, opus-4-8 **31 $143** | the four per-model rows, in that cost order |
| 749 M cache-read + **45.3 M cache-write (all 1-h)** + 9.35 M output + 20 k input | the `total` row's token columns; `cw_5m` must be **0.0M** |
| fleet-median job 376 k read / 47 k write / 9.0 k out | the `median job:` line |
| medians **opus-5 ≈ $3.43, fleet ≈ $0.59** | the `median $ per job by family` line |
| where the tokens go: alpha-research 27 = 162 M (≈ 22 %), atlas-build 9 = 66 M, atlas-report 157 = 57 M, review-and-improve 27 = 36 M | the `by kind` block's top rows and their `%` |

And in the **7-d block** (the anchor §2.8 says matters, because the load's largest step post-dates the 30-d mean): `alpha-research` ≈ 58 % of the window's tokens, and week-39-scale daily volume (2026-09-23 = 98.7 M, 09-24 = 68.0 M).

**The spec is the authority; this plan never rewrites §2.8 to match a run.** The window has moved since 2026-09-25, so absolute totals drift — but the per-model ordering, the all-1-h cache-write split and the median shape must match. **If the run disagrees with §2.8 by more than 10 %, stop and report the delta to the owner** (P0 PR + a line in the Verification log) rather than editing the spec: round 1's "restate §2.8 in the same commit" instruction is exactly how round-1 arithmetic would get written back over round-2 arithmetic. §13's restatement is the owner's call on the spec, not a side effect of a plan task.

After Task 3 has been deployed for ≥ 1 day: `pipenv run python scripts/cost-reconcile.py --windows 1 --db` → the delta column ≤ 1.0 % for every model with both legs (the exit criterion "cost view reconciles with JSONL sums **at both windows and the 1-h rate**" — the same SDK figure written twice by different code paths must agree; a larger delta means a job wrote `job_completed.cost_usd_list` without the column or vice versa — find it with `SELECT id FROM jobs WHERE status='completed' AND completed_at > now() - interval '1 day' AND cost_usd_list IS NULL`). Record the **30-d and 7-d** deltas at P0 exit in the P0 PR.

Seed check: `pipenv run python scripts/cost-reconcile.py --seed-lane-budgets` → `volumes/telemetry/lane_budget_seed.json` with `window_days: 7`, `multiplier: "1.2"`, `approximated_lanes: true` and one entry per lane. P2 reads this file for `lanes.<lane>.weekly_budget`; **`routing-policy.yml` consumption is P3** (spec §2.5 is a P3 deliverable) — P0 only writes the artefact.

- [ ] **Step 5b: Install the weekly timer**

`scripts/install-launchd.sh` — add a fifth timer beside Task 12's `credential-canary`, using the **same** `install_timer` helper and the same `PATH`/`VENV_PY` env block, so it inherits the "never `pipenv run`" contract:

```bash
# Weekly cost reconcile (P0, spec §2.8/§9): both windows + the per-kind step +
# the lane-budget seed. Exit 1 = 5-minute cache writes seen (credits signature).
install_timer cost-reconcile "bash ${PROJECT_DIR}/scripts/cost-reconcile-run.sh" 1 7 10
```

and `scripts/cost-reconcile-run.sh` (new, 20 lines) resolves the interpreter exactly as `credential-canary.sh` does — **`cd "$PROJECT_DIR"` FIRST**, then `VENV_PY="${VENV_PY:-}"` → `$PROJECT_DIR/.venv/bin/python` → `command -v python`, guarded with `"$VENV_PY" -c 'import src.config'` (the editable install is inert on this host, so the probe only succeeds from the project root — see Task 12's gotcha) — and runs:

```bash
"$VENV_PY" scripts/cost-reconcile.py --windows 30,7 --db --seed-lane-budgets \
    >> "$PROJECT_DIR/volumes/logs/cost-reconcile.log" 2>&1
rc=$?
[[ $rc -eq 1 ]] && "$VENV_PY" -m src.notify send --kind ops_alert --severity high \
    --text "cost-reconcile: 5-minute cache writes present — possible usage-credit overflow (spec §2.8). Check claude.ai billing." || true
```

Append to `tests/test_scripts_syntax.py`: `"cost-reconcile" in install_src`, `"--windows 30,7" in run_src`, `"--seed-lane-budgets" in run_src`, `"pipenv run" not in run_src`, and `'cd "$PROJECT_DIR"'` appears **before** the first `VENV_PY=` assignment in `cost-reconcile-run.sh`.

- [ ] **Step 6: Docs the lint gate needs, CHANGELOG, commit**

- `.context/modules/runner/CONTEXT.md`: append `` , `src/runner/pricing.py` `` to the `**Paths:**` line.
- `.context/SYSTEM.md` module graph — insert after the `src/runner/sdk_record.py` row, and a script row after the `scripts/restore-drill.sh` row:

```markdown
| `src/runner/pricing.py` | Claude list-price table (`claude-anthropic.md §4`), family matching, JSONL ledger summary + DB reconcile (pure) | — | scripts/cost-reconcile.py |
| `scripts/cost-reconcile.py` | Two-window (30 d + 7 d) list-price ledger from the JSONL (spec §2.8 anchor) + per-kind step + `--db` reconcile vs `jobs.cost_usd_list` + weekly lane-budget seed | config, db, runner.pricing | `scripts/cost-reconcile-run.sh` (weekly `com.assistant.cost-reconcile` timer) |
```

Run: `pipenv run pytest tests/test_doc_lint.py -q && pipenv run python scripts/lint_docs.py` → Expected: PASS and `All clean!`.

Prepend to `.context/modules/runner/CHANGELOG.md`:

```markdown
## 2026-09-25 — pricing.py + scripts/cost-reconcile.py: two-window list-price ledger, per-kind step, weekly lane-budget seed

- **Agent task**: multi-model P0, Task 16 (spec §2.8 calibration anchor at both windows, §9 P0 scope + exit criterion, round-1 #17, round-2 #18/#19).
- **Files changed**: `src/runner/pricing.py` (new, pure: `LIST_PRICES` from `claude-anthropic.md §4`, `family_for`, `cache_write_buckets`, `price_usage`, `lane_for`, `job_cost_from_events`, `summarize`, `summarize_windows`, `render_table`, `render_db_delta`, `lane_seed`, `write_lane_seed`), `scripts/cost-reconcile.py` + `scripts/cost-reconcile-run.sh` (new), `scripts/install-launchd.sh` (weekly `com.assistant.cost-reconcile` timer, Mon 07:10), tests, runner CONTEXT Paths, hosting CHANGELOG, SYSTEM.md rows.
- **Why**: the spec's **≈ $963/month** anchor at the **1-h cache-write rate** must be reproducible from the ledger *at both windows* — the 30-d mean predates the alpha flywheel (2026-09-23), which tripled daily load, so a 30-d-only report reproduces exactly the number round 2 rejected (round 1's $809 used the 5-m rate and was ≈ 19 % low). The per-kind step makes the flywheel line item visible instead of averaged away, the weekly run re-seeds the lane budgets from trailing-7-d × 1.2 (never the stale mean), and the P0 column `cost_usd_list` must agree with what the JSONL recorded at both windows.
- **Side effects**: one new weekly launchd timer and one new log (`volumes/logs/cost-reconcile.log`) + `volumes/telemetry/lane_budget_seed.json`. Otherwise a report.
- **Gotchas discovered**: cache-write has two list rates and **both are used, each against its own token count** (`usage.cache_creation.ephemeral_{1h,5m}_input_tokens`); prod records 100 % as 1-h and the flat `cache_creation_input_tokens` equals the 1-h figure, so a legacy row's flat value is attributed to the 1-h arm — pricing it at 5-m is the ≈ 19 % error. A non-zero 5-m total is the usage-credits signature (§2.8) and exits 1. `jobs.lane` is NULL until P2, so `lane_for()` is an explicitly-labelled approximation and the seed file says `approximated_lanes: true`; `routing-policy.yml` consumption is P3. §2.8's "fleet ≈ $0.59" is the median of per-job **costs**, not the cost of the median **shape** ($0.5298 at Sonnet 1-h rates) — the report prints both and the test asserts each against the statistic it actually is. Bare-alias launches (`sonnet` from web/dispatch) cannot be priced from `job_started.model`; they are listed under `unpriced`, never dropped. Every `-p`/SDK run also bills a Haiku side request (`claude-anthropic.md` line 157): `usage` is the aggregate, so per-model splits are by the REQUESTED model until P2's `provider_ledger` reads `model_usage` (Task 17's `utility_model_usage` check is the P0 detector).
```

```bash
git add src/runner/pricing.py scripts/cost-reconcile.py scripts/cost-reconcile-run.sh scripts/install-launchd.sh tests/test_pricing.py tests/test_scripts_syntax.py .context/modules/runner/CHANGELOG.md .context/modules/runner/CONTEXT.md .context/modules/hosting/CHANGELOG.md .context/SYSTEM.md
git commit -m "feat(runner): two-window list-price ledger (pricing.py) + cost-reconcile at 30d/7d with the per-kind step and the weekly lane-budget seed (spec §2.8, round-2 #18/#19)"
```

---

### Task 17: Every Claude subprocess runs with error reporting + telemetry off; the runner refuses to start with ANY vendor/auth key in its env; utility calls prove they were served by the requested model

**Execution position:** 9 of 21 — previous: Task 15, next: Task 4 (see Global Constraints "Execution order"). Tasks 12 and 16 both consume `claude_env`, so this task runs well before them even though it appears later in the file.

- [ ] **Step 0: Prerequisite check** — `pipenv run python -c "from src.runner.llm_router import router_options; from src.runner.learning import classifier_options; print('ok')"` must print `ok` (Task 0 extracted both builders). If it fails: **Task 0 has not been merged — stop.**

Spec §2.4 ("`DISABLE_ERROR_REPORTING=1` and `DISABLE_TELEMETRY=1` … error reports and operational metrics are on by default for Pro/Max sign-ins"), §3 Anthropic row ("runner env sets `DISABLE_ERROR_REPORTING=1` + `DISABLE_TELEMETRY=1`"), §9 P0 row, review #61; the "keep the runner's `os.environ` free of secrets (fail-closed startup assertion beside `_check_subscription_auth`)" sentence of §0a's last row and review #31. In SDK 0.1.81 `ClaudeAgentOptions.env` is an **overlay** on the inherited environment (`subprocess_cli.py:430-436`), so passing the two keys through `env=` reaches every subprocess from the next runner restart with no launchd change; the plist keys are the belt for anything else that spawns `claude` under the service env. Executed after Task 15 and before Task 12 (the canary consumes the helper).

**Files:**
- Create: `src/runner/claude_env.py` (import-free, so `session.py`, `llm_router.py`, `learning.py`, `review.py`, `canary.py` and `evals/run.py` can all import it without a cycle — `session.py` imports `llm_router`, so the helper cannot live in `session.py`)
- Modify: `src/runner/session.py` (`_build_options`, the `return ClaudeAgentOptions(**kwargs)` at the end), `src/runner/llm_router.py` (`router_options`, Task 0), `src/runner/learning.py` (`classifier_options`, Task 0), `src/runner/review.py:247-256` (the reviewer's `ClaudeAgentOptions(`), `evals/run.py:82-87` (the judge's), `src/runner/main.py:70-104` (`_check_subscription_auth`), `scripts/install-launchd.sh:96-100` (service `EnvironmentVariables`)
- Modify: `.context/modules/runner/CHANGELOG.md`, `.context/modules/hosting/CHANGELOG.md`, `.context/modules/runner/CONTEXT.md` (Paths line), `.context/SYSTEM.md` (row for `claude_env.py`; Depends-on of `session.py`, `llm_router.py`, `learning.py`, `review.py`, `main.py` += `runner.claude_env`)
- Test: `tests/test_claude_env.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `claude_env.CLAUDE_SUBPROCESS_ENV: dict[str, str] = {"DISABLE_ERROR_REPORTING": "1", "DISABLE_TELEMETRY": "1"}`; `claude_env.claude_subprocess_env() -> dict[str, str]` (a fresh copy every call).
  - `claude_env.VENDOR_KEY_PREFIXES` and `claude_env.VENDOR_KEY_SUFFIXES` + `claude_env.VENDOR_KEY_EXACT`, together covering **the spec's own refusal set, verbatim** (§2.4 item (2), round-2 #2): `GEMINI_*|CEREBRAS_*|GROQ_*|CODEX_*|OPENROUTER_*|OPENAI_*|XAI_*|*_API_KEY|CLAUDE_CODE_OAUTH_TOKEN|ANTHROPIC_*`. Prefixes `("GEMINI_", "CEREBRAS_", "GROQ_", "CODEX_", "OPENROUTER_", "OPENAI_", "XAI_", "ANTHROPIC_")`, suffix rule `("_API_KEY",)`, exact `("CLAUDE_CODE_OAUTH_TOKEN",)`; `claude_env.vendor_keys_in(env: Mapping[str, str]) -> list[str]` (sorted names present). **All of them are fail-closed.** `ANTHROPIC_` as a prefix is what catches `ANTHROPIC_BASE_URL` and `ANTHROPIC_AUTH_TOKEN` — the two keys that silently move Max work to API billing — and `CLAUDE_CODE_OAUTH_TOKEN` is in the set rather than warn-only (Open question 8, closed) because it too outranks `/login` for every Bash child of every job.
  - Every `ClaudeAgentOptions` the server builds carries `env=claude_subprocess_env()` (six sites; pinned by test). Canary (Task 12) and P3's `claude_sdk.py` reuse the helper.
  - `main._check_subscription_auth()` exits 1 when `vendor_keys_in(os.environ)` is non-empty — **fail-closed on every name in the set**, with the existing `ANTHROPIC_API_KEY` INV-3 message kept as a special case so that failure still reads as the INV-3 violation it is. The P0 test gate the spec names for this is `test_startup_env` (§9 test-gate paragraph), so the test bears that name.
  - `scripts/run.sh` gets `PIPENV_DONT_LOAD_ENV=1` on its three `_start_one` lines (`:116-118`). `pipenv run` auto-loads `.env` into `os.environ` (verified on this host), and spec §12a rows 10/11 put `GEMINI_*`/`CEREBRAS_*`/`GROQ_*` in `.env` at P3 — without this, the fail-closed assertion would refuse every `pipenv`-launched runner/web/bot the moment the owner adds a vendor key, while the launchd services (which run the venv python directly) stay fine. Pinned by `test_run_sh_does_not_export_dotenv`.
  - `utility_model_usage` check (the spec's P0 **exit criterion** "`model_usage` on utility calls lists only the requested model", §9 exit cell / §2.8 Claude row / round-2 #49): `llm_route` and `extract_learning` pass their `ResultMessage` through `result_capture.capture_result_message` and call the new pure `claude_env.utility_model_violation(model_usage: dict, requested: str) -> list[str]` (the extra families, sorted). A non-empty list logs `WARNING utility_model_usage call=<router|learning> requested=<m> served=<list>` and appends an audit entry `utility_model_usage{call, requested, served_models}` — **it never fails the call**: a persisting second family is the harness's own Haiku side request (`claude-anthropic.md` line 157), to be ledgered `purpose=harness` (spec §2.8), not an error. This is the only P0 assertion that looks at `model_usage` for *extra* entries; Task 2's `served_model_violation` is the main-job silent-empty-success trap and passes when a second model is also listed.
  - Service plists (`install-launchd.sh` services loop) export the two keys; no plist ever exports a credential (test).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_claude_env.py`:

```python
"""
Claude subprocess env posture (P0; spec §2.4/§3, review #61; §0a plutil exit
test + review #31). Pure — source pins and string pins only.

Run: pipenv run pytest tests/test_claude_env.py -v
"""

from __future__ import annotations

import inspect
import os
from pathlib import Path

import pytest

from src.runner.claude_env import (
    CLAUDE_SUBPROCESS_ENV,
    VENDOR_KEY_EXACT,
    VENDOR_KEY_PREFIXES,
    VENDOR_KEY_SUFFIXES,
    claude_subprocess_env,
    utility_model_violation,
    vendor_keys_in,
)

REPO = Path(__file__).resolve().parent.parent


def _clear_vendor_keys(monkeypatch):
    """Remove every key the assertion would refuse. NOTE: VENDOR_KEY_PREFIXES
    holds PREFIXES — `monkeypatch.delenv("GEMINI_")` removes nothing, so the
    environment has to be scanned. This matters in practice: `pipenv run`
    exports .env into os.environ, and spec §12a rows 10/11 put vendor keys
    there at P3."""
    for k in [k for k in list(os.environ) if k in vendor_keys_in(os.environ)]:
        monkeypatch.delenv(k, raising=False)


def test_overlay_is_exactly_the_two_flags():
    assert claude_subprocess_env() == {"DISABLE_ERROR_REPORTING": "1", "DISABLE_TELEMETRY": "1"}
    assert claude_subprocess_env() is not CLAUDE_SUBPROCESS_ENV       # a copy: callers may not mutate the constant


def test_router_and_classifier_builders_carry_the_overlay():
    from src.runner.learning import classifier_options
    from src.runner.llm_router import router_options
    for o in (router_options(), classifier_options()):
        assert o.env == claude_subprocess_env()


def test_build_options_reviewer_and_judge_set_env():
    # Source pins for the three inline ClaudeAgentOptions(...) sites.
    import evals.run as evals_run
    from src.runner import review, session
    assert 'kwargs["env"] = claude_subprocess_env()' in inspect.getsource(session._build_options)
    assert "env=claude_subprocess_env()" in inspect.getsource(review)
    assert "env=claude_subprocess_env()" in inspect.getsource(evals_run)


def test_vendor_keys_detector_covers_the_specs_whole_set():
    # spec §2.4 item (2), verbatim:
    # GEMINI_*|CEREBRAS_*|GROQ_*|CODEX_*|OPENROUTER_*|OPENAI_*|XAI_*|*_API_KEY
    # |CLAUDE_CODE_OAUTH_TOKEN|ANTHROPIC_*
    assert vendor_keys_in({"GEMINI_API_KEY": "x", "PATH": "/bin"}) == ["GEMINI_API_KEY"]
    assert vendor_keys_in({"OPENROUTER_API_KEY": "w", "CEREBRAS_KEY": "x", "GROQ_API_KEY": "y",
                           "CODEX_API_KEY": "z", "ANTHROPIC_API_KEY": "v"}) == [
        "ANTHROPIC_API_KEY", "CEREBRAS_KEY", "CODEX_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY"]
    # The names round 1 let through, each of which reaches every Bash child:
    for name in ("ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL", "OPENAI_API_KEY",
                 "XAI_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN", "TOGETHER_API_KEY"):
        assert vendor_keys_in({name: "x"}) == [name], name
    assert vendor_keys_in({"HOME": "/x", "ANTHROPIC_API_KEY_HINT": ""}) == ["ANTHROPIC_API_KEY_HINT"]  # prefix match is deliberate
    assert vendor_keys_in({"PATH": "/bin", "LANG": "C"}) == []          # no false positives
    assert "ANTHROPIC_" in VENDOR_KEY_PREFIXES
    assert "_API_KEY" in VENDOR_KEY_SUFFIXES
    assert "CLAUDE_CODE_OAUTH_TOKEN" in VENDOR_KEY_EXACT


@pytest.mark.parametrize("name", [
    "GEMINI_API_KEY", "ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN",
    "CLAUDE_CODE_OAUTH_TOKEN", "OPENAI_API_KEY", "XAI_API_KEY", "TOGETHER_API_KEY",
])
def test_startup_env(monkeypatch, name):
    """The P0 test gate the spec names (§9 test-gate paragraph: "test_startup_env
    — runner refuses to start with a planted vendor key in os.environ").
    EVERY name in the §2.4 set is fail-closed; none of them warns and continues."""
    from src.runner import main as main_mod
    _clear_vendor_keys(monkeypatch)
    monkeypatch.setenv(name, "leak")
    with pytest.raises(SystemExit):
        main_mod._check_subscription_auth()


def test_startup_passes_on_a_clean_env(monkeypatch):
    from src.runner import main as main_mod
    _clear_vendor_keys(monkeypatch)
    monkeypatch.setattr(main_mod.session_mod, "cli_version", lambda: "2.1.139")
    main_mod._check_subscription_auth()          # no SystemExit


def test_anthropic_api_key_still_reads_as_the_inv3_violation(monkeypatch, capsys):
    from src.runner import main as main_mod
    _clear_vendor_keys(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-x")
    with pytest.raises(SystemExit):
        main_mod._check_subscription_auth()
    assert "INV-3" in capsys.readouterr().err


def test_utility_model_violation_reports_extra_families_only():
    # spec §9 P0 exit: "model_usage on utility calls lists ONLY the requested
    # model". A second family is the harness's Haiku side request — a finding
    # to ledger purpose=harness, never a failure (round-2 #49).
    assert utility_model_violation({"claude-sonnet-4-6": {}}, "claude-sonnet-4-6") == []
    assert utility_model_violation(
        {"claude-sonnet-4-6": {}, "claude-haiku-4-5-20251001": {}},
        "claude-sonnet-4-6") == ["claude-haiku-4-5-20251001"]
    assert utility_model_violation({}, "claude-sonnet-4-6") == []      # absent ≠ wrong (Review Focus 5)


def test_utility_call_model_usage_is_single_model(caplog):
    # The router logs the finding and names both sets.
    import logging
    from src.runner import claude_env
    with caplog.at_level(logging.WARNING):
        claude_env.log_utility_model_usage(
            "router", requested="claude-sonnet-4-6",
            model_usage={"claude-sonnet-4-6": {}, "claude-haiku-4-5-20251001": {}})
    text = caplog.text
    assert "utility_model_usage" in text
    assert "claude-sonnet-4-6" in text and "claude-haiku-4-5-20251001" in text


def test_run_sh_does_not_export_dotenv():
    # `pipenv run` loads .env into os.environ, and the P3 vendor keys live in
    # .env (§12a rows 10/11) — without this the fail-closed assertion above
    # would refuse every pipenv-launched service. launchd is unaffected (it runs
    # the venv python directly).
    src = (REPO / "scripts/run.sh").read_text()
    for svc in ("runner", "web", "bot"):
        line = next(l for l in src.splitlines() if f"_start_one {svc} " in l)
        assert "PIPENV_DONT_LOAD_ENV=1" in line, line


def test_installer_service_plists_carry_the_flags():
    src = (REPO / "scripts/install-launchd.sh").read_text()
    # Slice between two markers Task 12 does NOT move. Task 12 wraps the
    # services loop in `if (( ! TIMERS_ONLY )); then … fi` and indents it, so
    # the old `for svc …` / "\ndone\n" pair stops matching and the slice would
    # silently grow to the end of the file (the assertion would still pass and
    # stop pinning anything).
    services = src.split("<key>PATH</key>", 1)[1].split("<key>RunAtLoad</key>", 1)[0]
    assert "<key>DISABLE_ERROR_REPORTING</key><string>1</string>" in services
    assert "<key>DISABLE_TELEMETRY</key><string>1</string>" in services


def test_installer_never_exports_credentials():
    # Spec §0a P0 exit test at the source: no plist the installer writes can carry a credential.
    src = (REPO / "scripts/install-launchd.sh").read_text()
    for name in ("CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY=", "GEMINI_API_KEY",
                 "TELEGRAM_BOT_TOKEN", "setup-token"):
        assert name not in src, name
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pipenv run pytest tests/test_claude_env.py -v`
Expected: collection error `ModuleNotFoundError: No module named 'src.runner.claude_env'`.

- [ ] **Step 3: Implement**

`src/runner/claude_env.py`:

```python
"""
Environment posture for every Claude subprocess the server spawns (P0; spec
§2.4/§3, review #61, #31).

`claude_subprocess_env()` is passed as `ClaudeAgentOptions.env` at every
construction site. In SDK 0.1.81 that dict is an OVERLAY on the inherited
os.environ (subprocess_cli.py:430-436) — enough for these two flags (Pro/Max
sign-ins have error reports and operational metrics on by default,
claude-anthropic.md §3 [68]); the full explicit env (no inheritance) is P3's
claude_sdk.py. Import-free on purpose: session.py imports llm_router, so a
helper both need cannot live in either.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping

logger = logging.getLogger(__name__)

CLAUDE_SUBPROCESS_ENV: dict[str, str] = {
    "DISABLE_ERROR_REPORTING": "1",
    "DISABLE_TELEMETRY": "1",
}

# Names that must never be in the runner's os.environ. Vendor keys are read
# from .env by Settings IN-PROCESS only (spec §2.4); anything in os.environ is
# inherited by every Claude subprocess and through it by every Bash call in the
# 72 skills. This is the spec's own set, verbatim (§2.4 item (2)):
#   GEMINI_*|CEREBRAS_*|GROQ_*|CODEX_*|OPENROUTER_*|OPENAI_*|XAI_*
#   |*_API_KEY|CLAUDE_CODE_OAUTH_TOKEN|ANTHROPIC_*
# ANTHROPIC_* (not just ANTHROPIC_API_KEY) because ANTHROPIC_BASE_URL and
# ANTHROPIC_AUTH_TOKEN outrank /login and silently move Max work to API
# billing; CLAUDE_CODE_OAUTH_TOKEN for the same reason (it is a one-year
# credential, spec §0a/§12a row 3). Every name here is FAIL-CLOSED.
VENDOR_KEY_PREFIXES: tuple[str, ...] = (
    "GEMINI_", "CEREBRAS_", "GROQ_", "CODEX_", "OPENROUTER_", "OPENAI_", "XAI_",
    "ANTHROPIC_",
)
VENDOR_KEY_SUFFIXES: tuple[str, ...] = ("_API_KEY",)
VENDOR_KEY_EXACT: tuple[str, ...] = ("CLAUDE_CODE_OAUTH_TOKEN",)


def claude_subprocess_env() -> dict[str, str]:
    """A fresh copy of the overlay for one ClaudeAgentOptions."""
    return dict(CLAUDE_SUBPROCESS_ENV)


def vendor_keys_in(env: Mapping[str, str]) -> list[str]:
    """Pure. Sorted names in `env` that the runner refuses to start with."""
    return sorted(
        k for k in env
        if k in VENDOR_KEY_EXACT
        or any(k.startswith(p) for p in VENDOR_KEY_PREFIXES)
        or any(k.endswith(s) for s in VENDOR_KEY_SUFFIXES)
    )


def utility_model_violation(model_usage: Mapping[str, object] | None,
                            requested: str) -> list[str]:
    """Pure. Families in `model_usage` other than the requested one, sorted.

    The spec's P0 exit criterion is "`model_usage` on utility calls lists only
    the requested model" (§9, §2.8 Claude row). An EMPTY/absent model_usage is
    not a violation (older CLI shapes omit it — Review Focus 5); an extra
    family is the harness's own Haiku side request, to be ledgered
    `purpose=harness` (§2.8), never an error.
    """
    return sorted(k for k in (model_usage or {}) if k != requested)


def log_utility_model_usage(call: str, *, requested: str,
                            model_usage: Mapping[str, object] | None) -> list[str]:
    """Log (never raise) when a utility call was served by more than the
    requested model. Returns the extra families so the caller can audit them."""
    extra = utility_model_violation(model_usage, requested)
    if extra:
        logger.warning("utility_model_usage call=%s requested=%s served=%s "
                       "(harness side request? ledger purpose=harness, spec §2.8)",
                       call, requested, sorted(model_usage or {}))
    return extra
```

`src/runner/session.py` — add `from src.runner.claude_env import claude_subprocess_env`; in `_build_options`, directly before `return ClaudeAgentOptions(**kwargs)`:

```python
    # Telemetry posture (spec §2.4/§3): error reports + operational metrics
    # off for every session. SDK 0.1.81 overlays this on os.environ.
    kwargs["env"] = claude_subprocess_env()
```

`src/runner/llm_router.py` / `src/runner/learning.py` — `router_options()` / `classifier_options()` (Task 0) gain `env=claude_subprocess_env(),` (import the helper). `src/runner/review.py:247` and `evals/run.py:82` — add `env=claude_subprocess_env(),` to the `ClaudeAgentOptions(` call (import the helper; in `evals/run.py` inside `_run_judge` next to the SDK import).

`src/runner/main.py` `_check_subscription_auth` — directly after the existing `ANTHROPIC_API_KEY` block:

```python
    # Spec §2.4 item (2): vendor and auth keys live in .env and are read by
    # Settings in-process only. Anything in os.environ is inherited by every
    # Claude subprocess and every Bash child of every job — refuse to start
    # rather than leak. FAIL-CLOSED on the whole set, CLAUDE_CODE_OAUTH_TOKEN
    # and ANTHROPIC_BASE_URL/ANTHROPIC_AUTH_TOKEN included: those three are
    # exactly what outranks the Keychain /login.
    from src.runner.claude_env import vendor_keys_in
    leaked = vendor_keys_in(os.environ)
    if leaked:
        # Keep the INV-3 wording for the one name that IS an invariant, so the
        # failure still reads as the invariant it violates.
        inv3 = "ANTHROPIC_API_KEY" in leaked
        print(
            ("ERROR: ANTHROPIC_API_KEY is set — INV-3: this server runs on subscription auth "
             "only.\n" if inv3 else "")
            + f"ERROR: forbidden credentials in the runner environment: {', '.join(leaked)}.\n"
            "  Every one of these is inherited by each Claude subprocess and by every Bash\n"
            "  call in the 72 skills; CLAUDE_CODE_OAUTH_TOKEN, ANTHROPIC_AUTH_TOKEN and\n"
            "  ANTHROPIC_BASE_URL also outrank the Keychain /login (spec §2.4, §0a).\n"
            "  Remove them from the launchd plist / shell profile and restart; vendor keys\n"
            "  belong in .env (Settings reads them in-process, pydantic-settings does not\n"
            "  export). If you launched through `pipenv run`, set PIPENV_DONT_LOAD_ENV=1 —\n"
            "  `pipenv run` copies .env into os.environ (scripts/run.sh does this already).",
            file=sys.stderr,
        )
        sys.exit(1)
```

`scripts/run.sh:116-118` — prefix each service with the switch (see the Interfaces note; `pipenv run` would otherwise copy `.env` into `os.environ` and trip the assertion above once the P3 vendor keys land):

```bash
    _start_one runner PIPENV_DONT_LOAD_ENV=1 pipenv run python3 -m src.runner.main
    _start_one web PIPENV_DONT_LOAD_ENV=1 pipenv run uvicorn src.gateway.web:app --host 127.0.0.1 --port 8080
    _start_one bot PIPENV_DONT_LOAD_ENV=1 pipenv run python3 -m src.gateway.telegram_bot
```

(`_start_one` execs its arguments, so a leading `VAR=value` needs `env` if the helper does not go through a shell — check `scripts/run.sh:57-70` when implementing and use `env PIPENV_DONT_LOAD_ENV=1 pipenv run …` if it execs directly.)

`src/runner/llm_router.py` `llm_route` and `src/runner/learning.py` `extract_learning` — after the `ResultMessage` is in hand, add the utility `model_usage` check (spec §9 P0 exit criterion). It logs and audits; it never changes the call's outcome:

```python
        from src.runner.claude_env import log_utility_model_usage
        extra = log_utility_model_usage("router", requested=options.model or "",
                                        model_usage=getattr(message, "model_usage", None) or {})
        if extra:
            audit_log.append(job_id or "utility", "utility_model_usage",
                             call="router", requested=options.model or "",
                             served_models=sorted(getattr(message, "model_usage", None) or {}))
```

(`extract_learning` gets the same three lines with `call="learning"`. Both callers already hold the `ResultMessage`; neither gains a new failure mode.)

`scripts/install-launchd.sh` services loop (lines 96-100) — the `EnvironmentVariables` dict gains, after the `PATH` string:

```bash
    <key>DISABLE_ERROR_REPORTING</key><string>1</string>
    <key>DISABLE_TELEMETRY</key><string>1</string>
```

(no other key; the plist is the belt, `options.env` is the mechanism — a runner restarted by `server-deploy` gets the flags without the installer running; the installer run is runbook §9.)

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pipenv run pytest tests/test_claude_env.py tests/test_utility_model.py tests/test_review.py tests/test_evals.py -v`
Expected: all PASS.

**Host steps (run on the box with launchd and a live SDK; skip in an isolated worktree and confirm with the owner instead).** Restart the dev runner (`launchctl kickstart -k gui/$(id -u)/com.assistant.runner`), enqueue `reply pong` (`kind='chat'`), and while it runs: `ps -eo pid,command | grep -m1 '[_]bundled/claude' | awk '{print $1}' | xargs -I{} ps eww -o command= -p {} | tr ' ' '\n' | grep -c '^DISABLE_\(TELEMETRY\|ERROR_REPORTING\)=1$'` → `2` (macOS `ps eww` prints the child's environment; the overlay reached the subprocess).

Negatives — **`pipenv run env`, not `VAR=x pipenv run`** (`pipenv run` loads `.env` *after* the inherited environment, so an inline assignment can be overwritten; verified on this host with `SERVER_ROOT`):

```bash
pipenv run env GEMINI_API_KEY=x python -c "from src.runner.main import _check_subscription_auth as c; c()"        # → exit 1
pipenv run env ANTHROPIC_BASE_URL=https://x python -c "from src.runner.main import _check_subscription_auth as c; c()"   # → exit 1
pipenv run env CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-x python -c "from src.runner.main import _check_subscription_auth as c; c()"  # → exit 1
```

Then one routed job (the P0 exit criterion "`model_usage` on utility calls lists only the requested model"): send a Telegram message no rule matches, then `grep 'utility_model_usage' volumes/logs/runner.err.log` → **no line** is the pass; a line naming `claude-haiku-*` is the harness side request, to be recorded in the PR and ledgered `purpose=harness`, not a failure.

- [ ] **Step 5: Docs the lint gate needs, CHANGELOGs, commit**

- `.context/modules/runner/CONTEXT.md`: append `` , `src/runner/claude_env.py` `` to the `**Paths:**` line.
- `.context/SYSTEM.md` module graph — insert after the `src/runner/sdk_record.py` row; append `, runner.claude_env` to the Depends-on cells of `src/runner/session.py`, `src/runner/main.py`, `src/runner/llm_router.py`, `src/runner/learning.py`, `src/runner/review.py`:

```markdown
| `src/runner/claude_env.py` | Env posture for every Claude subprocess: telemetry-off overlay + the §2.4 forbidden-key detector + utility `model_usage` check (import-free) | — | runner.session, runner.main, runner.llm_router, runner.learning, runner.review, runner.canary, evals.run |
```

Run: `pipenv run pytest tests/test_doc_lint.py -q && pipenv run python scripts/lint_docs.py` → Expected: PASS and `All clean!`.

Prepend to `.context/modules/runner/CHANGELOG.md`:

```markdown
## 2026-09-25 — DISABLE_ERROR_REPORTING/DISABLE_TELEMETRY on every Claude subprocess; the §2.4 key set refused at startup; utility model_usage checked

- **Agent task**: multi-model P0, Task 17 (spec §2.4/§3, §9 P0 scope + exit criteria, round-1 #61/#31, round-2 #2/#49).
- **Files changed**: `src/runner/claude_env.py` (new: overlay, the §2.4 key set, `utility_model_violation`/`log_utility_model_usage`), `session._build_options` (`kwargs["env"]`), `llm_router.router_options` + `llm_route`, `learning.classifier_options` + `extract_learning`, `review.py` reviewer options, `evals/run.py` judge options (all `env=claude_subprocess_env()`), `main._check_subscription_auth` (exit 1 on the whole `GEMINI_*|CEREBRAS_*|GROQ_*|CODEX_*|OPENROUTER_*|OPENAI_*|XAI_*|*_API_KEY|CLAUDE_CODE_OAUTH_TOKEN|ANTHROPIC_*` set), `scripts/run.sh` (`PIPENV_DONT_LOAD_ENV=1`), `scripts/install-launchd.sh` service plists (belt), tests, CONTEXT Paths, SYSTEM.md rows.
- **Why**: Pro/Max sign-ins ship error reports and operational metrics on by default; proprietary (atlas/alpha) sessions must not. `ClaudeAgentOptions.env` overlays `os.environ` in SDK 0.1.81 — enough for the flags; the explicit no-inherit env is P3. And the refusal set is the spec's: `ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN` and `CLAUDE_CODE_OAUTH_TOKEN` outrank the Keychain `/login`, so a warn-and-continue on any of them is a silent move of Max work onto API billing.
- **Side effects**: a runner started with ANY name in that set refuses to start (none is set on prod today — `plutil -p` the plists to confirm before deploying). `scripts/run.sh` stops copying `.env` into `os.environ`, which is what keeps the assertion compatible with the P3 vendor keys (§12a rows 10/11). The plist belt needs one full `install-launchd.sh` run on prod (runbook §9). `utility_model_usage` is log+audit only and can never fail a call.
- **Gotchas discovered**: the helper cannot live in `session.py` (it imports `llm_router`, which would import it back); `ps eww` is the only way to see a running subprocess's env on macOS without `sudo`; **`VENDOR_KEY_PREFIXES` holds prefixes, so `monkeypatch.delenv("GEMINI_")` clears nothing** — a test that wants a clean env must scan `os.environ` (this is live, not hypothetical: `pipenv run` copies `.env` in); and **`pipenv run` loads `.env` AFTER the inherited environment**, so `VAR=x pipenv run …` is silently overridden while `pipenv run env VAR=x …` works (verified with `SERVER_ROOT`).
```

Prepend to `.context/modules/hosting/CHANGELOG.md`:

```markdown
## 2026-09-25 — service plists export DISABLE_ERROR_REPORTING=1 / DISABLE_TELEMETRY=1

- `scripts/install-launchd.sh`: runner/web/bot `EnvironmentVariables` gain the two keys (belt under the runner's own `options.env` overlay). Never a credential key (`tests/test_claude_env.py::test_installer_never_exports_credentials`). Takes effect on prod after the owner's full installer run (runbook §9).
```

```bash
git add src/runner/claude_env.py src/runner/session.py src/runner/llm_router.py src/runner/learning.py src/runner/review.py evals/run.py src/runner/main.py scripts/run.sh scripts/install-launchd.sh tests/test_claude_env.py .context/modules/runner/CHANGELOG.md .context/modules/hosting/CHANGELOG.md .context/modules/runner/CONTEXT.md .context/SYSTEM.md
git commit -m "feat(runner): telemetry-off env overlay on every Claude subprocess; fail-closed on the spec §2.4 key set (incl. ANTHROPIC_*/CLAUDE_CODE_OAUTH_TOKEN); PIPENV_DONT_LOAD_ENV in run.sh; utility model_usage check; plist belt"
```

---

### Task 18: Alembic applied-history manifest + the rollback rule as a pytest gate (the `alembic current` script is an owner diagnostic)

**Execution position:** 3 of 21 — previous: Task 1, next: Task 2 (see Global Constraints "Execution order"). It appears near the end of this file but runs immediately after the migration it manifests.

- [ ] **Step 0: Prerequisite check** — `ls alembic/versions/007_p0_observability.py` must exist. If it does not: **execute Task 1 first.**

Spec §9 rollback paragraph ("`tests/test_migrations.py` only asserts one head + a walkable chain today, so the P0 test 'every revision in history exists on disk' is added and `server-deploy` checks `alembic current` ∈ scripts"; "if a migration itself must go, run `alembic downgrade -1` on prod before reverting the file"), §9 P0 row, review #29. Executed right after Task 1 (so 007 is on the manifest from its first deploy).

Why a manifest: `alembic_version` on prod is one row, unreachable from a pure test; a deleted HEAD migration file leaves the on-disk chain perfectly walkable (head silently becomes 006) — exactly the state that breaks the next `alembic upgrade head`. `alembic/applied_history.txt` is the append-only list of revisions that have been applied; the pure test asserts every listed id has a script and that the on-disk chain equals the list, so a revert that deletes a migration file fails the pytest gate in `server-deploy` instead of failing mid-incident. Removing a line is a deliberate, reviewed act that is legal only after `alembic downgrade -1` ran on prod. `scripts/alembic-current-check.sh` is the DB-side **diagnostic** the owner runs by hand after a revert (runbook §11); it is **not** wired into `skills/server-deploy/SKILL.md` — round-2 #8 resolved this as "P0 alembic check kept as a test only (no SKILL.md edit)", and §9's rollback paragraph says alembic already fails loudly on a missing revision. The pytest gate is the belt.

**Files:**
- Create: `alembic/applied_history.txt`, `scripts/alembic-current-check.sh`
- Modify: `tests/test_migrations.py` (append; the script's syntax/string pins live here too, because `tests/test_scripts_syntax.py` is created later in Task 12)
- Modify: `.context/modules/db/CHANGELOG.md`, `.context/modules/hosting/CHANGELOG.md`, `.context/SYSTEM.md` (script row)

**Interfaces:**
- Consumes: Task 1's `007_p0_observability.py`.
- Produces:
  - `alembic/applied_history.txt` — comment lines (`#`) + one revision id per line, oldest first: `001` … `007`. Every future migration task appends its id in the same commit.
  - `scripts/alembic-current-check.sh` — exit 0 when the configured DB's `alembic_version` names a revision with a script under `alembic/versions/`, 1 when it does not (prints the `downgrade -1` rule), 2 when it cannot tell (no interpreter, no DB). Never `pipenv run`; resolves `VENV_PY` like the Task 12/13 scripts (and `cd`s to `$PROJECT_DIR` **before** the guard probe). **An owner-run diagnostic only** — nothing wires it into `skills/server-deploy/SKILL.md` (a protected path; round-2 #8, §9 "Protected touches: none"). The deploy is protected by this task's two pytest assertions, which `server-deploy`'s existing `pytest -q` gate already runs.
  - Tests: `test_every_revision_in_applied_history_exists_on_disk`, `test_applied_history_matches_disk_chain`, `test_applied_history_ends_at_007`, `test_alembic_current_check_script_invariants`, and the opt-in `test_configured_db_current_revision_has_a_script` (`AI_SERVER_RUN_DB_TESTS=1`).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_migrations.py`:

```python
# ── Layer 1c: applied history vs disk (no DB) — spec §9 rollback rule ──────

HISTORY = REPO / "alembic" / "applied_history.txt"


def _applied_history() -> list[str]:
    return [ln.strip() for ln in HISTORY.read_text().splitlines()
            if ln.strip() and not ln.lstrip().startswith("#")]


def _disk_chain() -> list[str]:
    """base → head by following down_revision from the single head."""
    from alembic.script import ScriptDirectory
    script = ScriptDirectory.from_config(_alembic_config())
    rev = script.get_revision(script.get_current_head())
    chain: list[str] = []
    while rev is not None:
        chain.append(rev.revision)
        rev = script.get_revision(rev.down_revision) if rev.down_revision else None
    return chain[::-1]


def test_every_revision_in_applied_history_exists_on_disk():
    missing = [r for r in _applied_history() if r not in set(_disk_chain())]
    assert not missing, (
        f"applied revisions with no script on disk: {missing} — a revert deleted a migration "
        f"file; run `alembic downgrade -1` on prod BEFORE removing it (spec §9 rollback rule)")


def test_applied_history_matches_disk_chain():
    assert _applied_history() == _disk_chain(), (
        "alembic/applied_history.txt must list exactly the on-disk chain base→head: append "
        "the new id in the same commit as a migration; remove one only after downgrade -1")


def test_applied_history_ends_at_007():
    assert _applied_history()[-1] == "007"


def test_alembic_current_check_script_invariants():
    path = REPO / "scripts" / "alembic-current-check.sh"
    r = subprocess.run(["bash", "-n", str(path)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    src = path.read_text()
    assert "pipenv run" not in src                       # launchd / bash -lc has no pipenv (rc=127)
    assert 'VENV_PY="${VENV_PY:-' in src and "import src.config" in src
    assert "-m alembic current" in src and "alembic/versions" in src
    assert "downgrade -1" in src                          # the rule, printed at the moment it matters


@pytest.mark.skipif(not _db_tests_enabled(),
                    reason="opt-in: set AI_SERVER_RUN_DB_TESTS=1 (needs local Postgres)")
def test_configured_db_current_revision_has_a_script():
    # The live-DB form of the rule — what scripts/alembic-current-check.sh does at deploy time.
    import asyncio

    from sqlalchemy import text

    from src.db import async_session

    async def _current():
        async with async_session() as s:
            return (await s.execute(text("SELECT version_num FROM alembic_version"))).scalar()

    current = asyncio.run(_current())
    assert current in set(_disk_chain()), f"alembic_version={current} has no script on disk"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pipenv run pytest tests/test_migrations.py -v`
Expected: `FileNotFoundError: … alembic/applied_history.txt` ×3, the script test fails on the missing file; the DB test is skipped.

- [ ] **Step 3: Write the manifest and the script**

`alembic/applied_history.txt`:

```text
# alembic/applied_history.txt — every revision that has been applied to prod,
# oldest first, APPEND-ONLY (spec §9 rollback rule, review #29).
# tests/test_migrations.py asserts each id has a script on disk and that the
# on-disk chain base→head equals this list, so `git revert` of a migration
# file fails the pytest gate instead of breaking `alembic upgrade head` on
# prod. Removing a line is a deliberate, reviewed act that is legal ONLY
# after `alembic downgrade -1` ran on prod. Every migration commit appends
# its id here.
001
002
003
004
005
006
007
```

`scripts/alembic-current-check.sh`:

```bash
#!/usr/bin/env bash
# scripts/alembic-current-check.sh — owner-run diagnostic for the spec §9 rollback
# rule (review #29): the DB's alembic_version must name a revision that has a
# script on disk, or the next `alembic upgrade head` fails "Can't locate
# revision" mid-deploy. Exit 0 ok · 1 mismatch · 2 cannot determine.
# RUN BY HAND after any migration revert (runbook §11). NOT wired into
# skills/server-deploy/SKILL.md — that file is a protected path and spec §9's
# rollback paragraph says no edit is needed: what protects the deploy is
# tests/test_migrations.py layer 1c, inside the pytest gate server-deploy
# already runs. Never `pipenv run` (bash -lc under launchd has no pipenv).
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

VENV_PY="${VENV_PY:-}"
[[ -z "$VENV_PY" && -x "$PROJECT_DIR/.venv/bin/python" ]] && VENV_PY="$PROJECT_DIR/.venv/bin/python"
[[ -z "$VENV_PY" ]] && VENV_PY="$(command -v python || true)"
if [[ -z "$VENV_PY" ]] || ! "$VENV_PY" -c 'import src.config, alembic' 2>/dev/null; then
    echo "alembic-current-check: no usable interpreter (VENV_PY='${VENV_PY:-}')" >&2
    exit 2
fi

# `alembic current` prints e.g. "007 (head)"; empty on a DB with no alembic_version row.
current=$("$VENV_PY" -m alembic current 2>/dev/null | awk 'NF {print $1; exit}')
if [[ -z "$current" ]]; then
    echo "alembic-current-check: could not read alembic_version (empty DB? alembic env broken?)" >&2
    exit 2
fi
if ls "$PROJECT_DIR"/alembic/versions/"${current}"_*.py >/dev/null 2>&1; then
    echo "alembic-current-check: OK alembic_version=$current has a script on disk"
    exit 0
fi
echo "alembic-current-check: FAIL alembic_version=$current has NO script under alembic/versions/ — a revert removed a migration file. Restore the file; only if the migration itself must go, run: \"$VENV_PY\" -m alembic downgrade -1 BEFORE removing it (spec §9 rollback rule)." >&2
exit 1
```

`chmod +x scripts/alembic-current-check.sh`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pipenv run pytest tests/test_migrations.py -v` → Expected: all PASS (DB test skipped unless opted in).
Run: `bash scripts/alembic-current-check.sh; echo rc=$?` on the dev box (its `.env` DB is at 007 once Task 1's `alembic upgrade head` ran) → `OK alembic_version=007 has a script on disk`, `rc=0`. Negative: `mv alembic/versions/007_p0_observability.py /tmp/ && bash scripts/alembic-current-check.sh; echo rc=$?; mv /tmp/007_p0_observability.py alembic/versions/` → `FAIL alembic_version=007 has NO script …`, `rc=1`; and `pipenv run pytest tests/test_migrations.py -q` with the file moved → `test_every_revision_in_applied_history_exists_on_disk` FAILS (the gate that protects prod). Restore the file.

- [ ] **Step 5: SYSTEM.md row, CHANGELOGs, commit**

`.context/SYSTEM.md` module graph — script row after `scripts/restore-drill.sh`:

```markdown
| `scripts/alembic-current-check.sh` | Owner-run diagnostic: `alembic current` must have a script on disk (spec §9 rollback rule; the pytest gate is the belt — no SKILL.md wiring) | alembic | — (owner-run after a migration revert) |
```

Prepend to `.context/modules/db/CHANGELOG.md`:

```markdown
## 2026-09-25 — alembic/applied_history.txt + "every applied revision exists on disk" tests

- `alembic/applied_history.txt` (append-only manifest 001…007); `tests/test_migrations.py` layer 1c asserts every listed id has a script and the on-disk chain equals the list (+ an opt-in live-DB check). Rollback rule (spec §9, review #29): revert application code only; `alembic downgrade -1` on prod BEFORE removing a migration file, then drop its manifest line in the same commit. Every migration commit appends its id.
```

Prepend to `.context/modules/hosting/CHANGELOG.md`:

```markdown
## 2026-09-25 — scripts/alembic-current-check.sh (owner-run diagnostic: alembic_version ∈ scripts)

- New script: exit 0/1/2; `VENV_PY` contract (`cd "$PROJECT_DIR"` before the guard), never `pipenv run`. **Owner-run by hand after a migration revert (runbook §11) — deliberately NOT wired into `skills/server-deploy/SKILL.md`**: round-2 #8 of the spec review cancelled that edit ("P0 alembic check kept as a test only"), §9's rollback paragraph says alembic already fails loudly on a missing revision, and the §9 P0 "Protected touches" cell is `none`. The belt is `tests/test_migrations.py` layer 1c, inside the `pytest -q` gate `server-deploy` already runs.
```

```bash
git add alembic/applied_history.txt scripts/alembic-current-check.sh tests/test_migrations.py .context/modules/db/CHANGELOG.md .context/modules/hosting/CHANGELOG.md .context/SYSTEM.md
git commit -m "feat(db+ops): alembic applied-history manifest + tests, alembic-current-check.sh deploy belt (spec §9 rollback rule)"
```

---

### Task 14: Docs to update — CONTEXT.md interfaces, SYSTEM.md module graph, INDEX/README rows, TROUBLESHOOTING, lint

**Execution position:** 21 of 21 — previous: Task 13, next: none (see Global Constraints "Execution order"). Last by design: it carries the whole-suite gate, the PR note and the deploy request.

**Files:**
- Modify: `.context/modules/runner/CONTEXT.md` (Paths line + public interface), `.context/modules/gateway/CONTEXT.md` (paths, commands, "Notifications back to user"), `.context/modules/db/CONTEXT.md` (schema, migrations, channels), `.context/modules/hosting/CONTEXT.md` (Paths + scripts), `.context/modules/notify/CONTEXT.md` (already created in Task 5 — verify), `.context/modules/gateway/skills/GOTCHAS.md`
- Modify: `.context/SYSTEM.md:27-66` (module graph rows), `:92-99` (data flow), `:100-106` (conventions: migrations)
- Modify: `.context/INDEX.md:185-191` (Additions 2026-09-25 table), `docs/README.md:19-23` (docs table), `docs/TROUBLESHOOTING.md:380-440` (AskUserQuestion + `_job_to_chat` passages) + two new symptom sections
- Test: `pipenv run python scripts/lint_docs.py`, `pipenv run pytest -q`

**Interfaces:** consumes every earlier task; produces no code.

- [ ] **Step 1: Module CONTEXT.md updates**

`.context/modules/runner/CONTEXT.md`:
- Paths line: already names `src/runner/result_capture.py` (Task 2), `src/runner/sdk_record.py` (Task 15), `src/runner/claude_env.py` (Task 17), `src/runner/pricing.py` (Task 16) and `src/runner/canary.py` (Task 12) — verify, do not re-append.
- Public interface — add bullets:

```markdown
- `result_capture.capture_result_message(msg) -> ResultCapture` / `derive_terminal_reason(cap, banner_terminal=)` / `served_model_violation(cap, requested_model, final_text)` / `result_columns(cap, terminal_reason=, cli_version=)` / `terminal_reason_for_exception(exc)` / `same_model(a, b)` — pure (P0). `_run_in_process` returns `(text, usage, capture)`; `run_session` stamps `resolved_provider/executor/cli_version` at start and `model_served/tokens/num_turns/duration_api_ms/cost_usd_list/terminal_reason` at the end; a silent empty success (`unrecognized_model`) raises and engages escalation. `job_completed` carries `terminal_reason, num_turns, duration_api_ms, model_served, cost_usd_list, stop_reason` in addition to `duration_seconds, usage`; `job_failed` carries `terminal_reason` on the timeout/generic branches; new kind `job_result_rejected`.
- `session.cli_version() -> str` — cached bundled-CLI version (`jobs.cli_version`).
- `main.queue_wait_ms(created_at, started_at)`, `main.awaiting_since_for(status, now)`, `main.job_notice_kwargs(job)` — pure. `main._finish_job(..., terminal_reason=)` publishes `jobs:done:<id>` as before and, when `settings.notify_outbox`, also enqueues a `job_completed`/`job_failed` outbox notice; `main._notify_task(task_id, type, **fields)` is the single task-card chokepoint and dual-writes (always the legacy `tasks:notify` publish; plus an outbox row when `settings.notify_outbox`). The switch selects the bot's renderer, never the runner's output.
- `canary.canary_options(model)` / `async canary.run_ping(model, *, timeout_s, query_fn)` / `canary.evaluate_ping(capture, final_text, requested_model) -> (ok, detail)`; `python -m src.runner.canary [--model …] [--telemetry …] [--timeout …]` (used by `scripts/credential-canary.sh`) — the daily credential canary through the SDK in the runner venv with the runner's option conventions, `claude_env.claude_subprocess_env()` and the `result_capture` rule (P3 swaps `query()` for `ClaudeSdkExecutor`); never the brew CLI, never `--bare`, never `CLAUDE_CODE_OAUTH_TOKEN`.
- `claude_env.claude_subprocess_env()` — the `ClaudeAgentOptions.env` overlay (`DISABLE_ERROR_REPORTING=1`, `DISABLE_TELEMETRY=1`) on every options site (`_build_options`, router, learning classifier, reviewer, canary, eval judge); `claude_env.vendor_keys_in(env)` — `_check_subscription_auth` exits 1 when a `GEMINI_*|CEREBRAS_*|GROQ_*|CODEX_*|OPENROUTER_*|ANTHROPIC_API_KEY` name is in the runner env, warns on `CLAUDE_CODE_OAUTH_TOKEN`.
- `sdk_record.SdkRecorder` — `SDK_RECORD=1` → every SDK message `_run_in_process` receives is appended (redacted) to `volumes/audit_log/<id>.sdk.jsonl`, first statement of the message loop; best-effort (never fails a job); `python -m src.runner.sdk_record coverage` reports recorded jobs per skill (≥ 20 / ≥ 3 classes before P3).
- `pricing.LIST_PRICES` / `family_for` / `price_usage` / `job_cost_from_events` / `summarize` / `render_table` / `render_db_delta` (pure) behind `scripts/cost-reconcile.py [--days N] [--db]` — the spec §2.8 list-price ledger; `cost_usd_list` is list-equivalent, never a bill.
- `quota.pause_queue(reset_at, reason, *, source)` / `quota.last_source()` / `QuotaExhausted.source` — `vendor` only when a `RateLimitEvent` carried the reset time; the bot's `quota_paused` DM labels it.
- `llm_router.router_options()` / `learning.classifier_options()` — the two utility-call option builders on `settings.utility_model` (`claude-sonnet-4-6`, effort low; Haiku 4.5 retired — shipped ahead of P0 as a standalone patch, Task 0) with the `claude_env` overlay.
- Scheduler jobs carry `origin_channel="scheduler", origin_ref=<schedule name>`.
```

`.context/modules/gateway/CONTEXT.md`:
- Public interface: `enqueue_job(description, *, kind, payload, project_id, created_by, task_id, parent_job_id, origin_channel, origin_ref, origin_thread) -> Job`; add `origin_from_created_by(created_by) -> (channel, ref)`, `cancel_action_for_status(status)`, `remove_from_queue(job_id)`, `cancel_job_durable(job) -> str`; `DELETE /api/jobs/{id}` uses the durable path; `JobOut` P0 fields.
- Telegram primary commands: `/task`, `/status [<prefix>]`, `/jobs`, `/cancel <prefix>`, `/proposals`, `/help`; admin: `/chat`, `/god`, `/resume`, `/clear` (confirm button, 120 s token), `/schedule`, `/projects`. Buttons: `jd:<job8>` (job details), `clear_confirm:<token>`, `clear_abort:0` beside the task-scoped ones.
- Replace the "Notifications back to user" section:

```markdown
## Notifications back to user

P0 (2026-09-25): the runner writes `notifications` rows (job terminals and every
task card) and nudges `notify:outbox`; the bot's `_outbox_listener` renders them
with `src/notify/telegram.py` (plain text, 4096/64-byte/8-button limits) on the
nudge and at least every 30 s, stamping `status/attempts/external_ref` — a bot
restart loses no DM. Targets come from `jobs.origin_*` / `tasks.origin_*`
(fallback `tasks.chat_id`/`thread_message_id`); non-Telegram origins DM the
owner (first `TELEGRAM_ALLOWED_CHAT_IDS`). Kill switch `NOTIFY_OUTBOX=0` is
renderer-side: the runner publishes `tasks:notify` / `jobs:done:<id>` in both
modes (P0 dual-write), and with the switch off the legacy `_done_listener`
(`_handle_done_message`) / `_task_notifier` send instead of `_outbox_listener`
— a bot-only restart flips delivery.
```

`.context/modules/db/CONTEXT.md`: "Schema (7 tables)" — add `notifications` (outbox: `notice_kind, subject_type/id, severity, body, actions, channel, target, thread, external_ref, status, attempts, last_error, next_attempt_at, sent_at, created_at`); `jobs` gains the 21 P0 columns (list the observability ones + `origin_*`; note the two TTL-split `cache_write_{1h,5m}_tokens` columns and that `lane/task_class/sensitivity/first_event_at` are reserved — **no `priority` column**, spec §2.3 row 007); `tasks` gains `origin_*`, `awaiting_since`. Migrations: seven files (`007_p0_observability`) + `alembic/applied_history.txt` (append-only manifest; the rollback rule: revert application code only, `alembic downgrade -1` on prod before removing a migration file, then drop its manifest line). Redis: `CHANNEL_NOTIFY_OUTBOX = "notify:outbox"`, `quota:last_source`. Settings: `notify_outbox`, `utility_model`, `sdk_record`.

`.context/modules/hosting/CONTEXT.md`: Paths line add `` `scripts/credential-canary.sh`, `scripts/restore-drill.sh`, `scripts/alembic-current-check.sh`, `scripts/cost-reconcile.py` ``; public interface bullets for `credential-canary.sh` (daily 06:50 timer `com.assistant.credential-canary`; the ping runs inside `python -m src.runner.canary` through the SDK), `restore-drill.sh`, `backup.sh` (atlas dump + sealed secrets; key file), `install-launchd.sh timers-only` (+ every plist exports `DISABLE_ERROR_REPORTING`/`DISABLE_TELEMETRY`, never a credential), `alembic-current-check.sh` (owner-run diagnostic after a migration revert; **not** wired into `server-deploy` — round-2 #8), `cost-reconcile.py` (report); alerters DM via `python -m src.notify send` with curl fallback.

Append to `.context/modules/gateway/skills/GOTCHAS.md` (below its APPEND marker):

```markdown
### Outbox rows stuck `pending` (2026-09-25)
`SELECT notice_kind, attempts, last_error FROM notifications WHERE status='pending' ORDER BY created_at` — `attempts` climbing with a Telegram error means the bot is up but the chat/thread is wrong (a deleted root message is retried once without `reply_to`); zero attempts and an old `created_at` means the bot's `_outbox_listener` is not running (`launchctl list | grep com.assistant.bot`). `python -m src.notify drain` delivers from a terminal.
```

- [ ] **Step 2: `.context/SYSTEM.md`**

Module graph — the `src/` rows already exist (added with their files so the lint gate stayed green: `result_capture.py` in Task 2, the three `src/notify/*` rows in Task 5, `sdk_record.py` in Task 15, `pricing.py` in Task 16, `claude_env.py` in Task 17, `canary.py` in Task 12) and the Depends-on cells were updated in the commits that added the imports (`session.py`/`main.py` += `runner.result_capture` in Task 3; `session.py` += `runner.sdk_record` in Task 15; `session.py`/`main.py`/`llm_router.py`/`learning.py`/`review.py` += `runner.claude_env` in Task 17; `main.py` += `notify.outbox` in Task 6; `telegram_bot.py` += `notify.outbox, notify.telegram` in Task 7; `jobs.py` += `audit_log` and `telegram_bot.py` += `runner.proposals` in Task 8). Verify they read as follows (four columns; `src/notify/telegram.py` imports nothing from `src`, so its Depends-on is `—`, not `notify.outbox`):

```markdown
| `src/runner/result_capture.py` | Typed ResultMessage capture, terminal_reason, silent-empty-success check (pure) | — | runner.session, runner.main, runner.canary |
| `src/runner/sdk_record.py` | Opt-in raw SDK message recorder (`SDK_RECORD=1` → `<id>.sdk.jsonl`, redacted) + `coverage` CLI — P3 replay fixtures | config | runner.session |
| `src/runner/claude_env.py` | Env posture for every Claude subprocess: telemetry-off overlay + vendor-key detector (import-free) | — | runner.session, runner.main, runner.llm_router, runner.learning, runner.review, runner.canary, evals.run |
| `src/runner/pricing.py` | Claude list-price table (`claude-anthropic.md §4`), family matching, JSONL ledger summary + DB reconcile (pure) | — | scripts/cost-reconcile.py |
| `src/runner/canary.py` | Credential canary through the runner's SDK path (`python -m src.runner.canary`): runner option conventions + env overlay + served-model rule | config, runner.result_capture, runner.claude_env, claude_agent_sdk | scripts/credential-canary.sh |
| `src/notify/outbox.py` | Notifications outbox: rows, policy (which job/task events DM), claim/lease, retry math | config, db, models, audit_log | runner.main, gateway.telegram_bot, notify.__main__ |
| `src/notify/telegram.py` | Telegram renderer (4096/64-byte/8-button limits), bot + HTTP senders | — | gateway.telegram_bot, notify.__main__ |
| `src/notify/__main__.py` | `python -m src.notify send` / `drain` for launchd alerters and ops | config, notify.outbox, notify.telegram | scripts/credential-canary.sh, healthcheck-all.sh, schedule-monitor.sh |
```

and that the `src/gateway/telegram_bot.py` row's Depends-on is exactly `config, db, models, gateway.jobs, audit_log, runner.router, runner.plans, notify.outbox, notify.telegram, runner.proposals`, `src/gateway/jobs.py`'s is `db, models, audit_log`, `src/runner/main.py`'s ends `…, audit_log, runner.result_capture, notify.outbox, runner.claude_env`, and `src/runner/session.py`'s ends `…, context.module_graph, runner.result_capture, runner.sdk_record, runner.claude_env`.

Verify the four script rows (added in Tasks 12/13/16/18 — scripts are not lint-checked):

```markdown
| `scripts/credential-canary.sh` | Daily credential canary through the runner's SDK path (served-model + API-time rule) → notify send | runner.canary, notify | — (launchd timer 06:50) |
| `scripts/restore-drill.sh` | Throwaway restore of the newest backup (PASS/FAIL) | psql, openssl, rclone | — (owner-run) |
| `scripts/cost-reconcile.py` | Two-window (30 d + 7 d) list-price ledger from the JSONL (spec §2.8 anchor) + per-kind step + `--db` reconcile vs `jobs.cost_usd_list` + weekly lane-budget seed | config, db, runner.pricing | `scripts/cost-reconcile-run.sh` (weekly `com.assistant.cost-reconcile` timer) |
| `scripts/alembic-current-check.sh` | Owner-run diagnostic: `alembic current` must have a script on disk (spec §9 rollback rule; the pytest gate is the belt — no SKILL.md wiring) | alembic | — (owner-run after a migration revert) |
```

Update existing script rows: `scripts/backup.sh` purpose → "Nightly pg_dump (assistant + atlas) + audit/log snapshot + sealed secrets → R2"; `scripts/healthcheck-all.sh` and `scripts/schedule-monitor.sh` "Depends on" += `notify`.

Data flow: after the `jobs:done:<id>` line add `→ notifications row + notify:outbox nudge`; replace the last block with `Bot's outbox listener → DMs + thread cards (job done/failed, plan, completed, question, progress); legacy done_listener/task_notifier only when NOTIFY_OUTBOX=0`.

Conventions: `- **Migrations**: Alembic, seven files (`001_initial` … `007_p0_observability`). Tables: `jobs`, `schedules`, `projects`, `proposals`, `tasks`, `task_turns`, `notifications` (+ `alembic_version`).`

- [ ] **Step 3: `.context/INDEX.md` and `docs/README.md`**

The working tree already carries (uncommitted, from the spec session) the rows for the spec and this plan in both files — keep them, and add the rows below. **CLAUDE.md's update map requires an `.context/INDEX.md` row for every new documentation file**, and Task 5 creates one (`.context/modules/notify/CONTEXT.md`), so it gets a row too:

`.context/INDEX.md` "Additions 2026-09-25" table:

```markdown
| I need to understand or extend owner notifications (outbox rows, the Telegram renderer's limits, the `send`/`drain` CLI, which job and task events DM) | `.context/modules/notify/CONTEXT.md` |
| Do the owner-only P0 hygiene (pmset, Ollama weights, R2 + its 60-day retention rule, seal key, restore drill, canary timer, §12a P0 rows 1/2/2b auth posture, full installer run, `SDK_RECORD` fixtures) | `docs/runbooks/2026-09-25-p0-ops-hygiene.md` |
| Reproduce the spec §2.8 cost anchor at both windows / check `jobs.cost_usd_list` against the JSONL ledger / re-seed the lane budgets | `scripts/cost-reconcile.py --windows 30,7 [--db] [--seed-lane-budgets]` (pure core `src/runner/pricing.py`; weekly `com.assistant.cost-reconcile` timer) |
| Collect raw SDK recordings for the P3 replay gate / see how many are recorded | `SDK_RECORD=1` (runbook §10); `python -m src.runner.sdk_record coverage`; `src/runner/sdk_record.py` docstring |
| Know why a credential value never appears in an audit JSONL / extend the redaction pattern set | `src/runner/secret_redact.py` docstring (always-on, spec §2.4) |
| Know why a schedule deferred instead of running | `docs/TROUBLESHOOTING.md` "a schedule stops running and DMs `⏸ … deferred`"; `src/runner/main.py` `provisioning_gap` |
```

Also update the existing "Execute the first slice (…)" row's parenthetical to `(Task 0 Haiku standalone patch, migration 007, ResultMessage capture, notify outbox + origin (dual-write), project-scope auth-override refusal, always-on audit redactor, scheduler provisioning pre-check, ghost commands, credential canary via the SDK path, SDK_RECORD recorder, telemetry-off env, two-window cost reconcile, alembic history, ops hygiene)`.

`docs/README.md` table, after the P0 plan row (and amend the plan row's description the same way):

```markdown
| [`runbooks/2026-09-25-p0-ops-hygiene.md`](runbooks/2026-09-25-p0-ops-hygiene.md) | Owner runbook for the P0 ops debt and the §12a P0 rows: `pmset autorestart`, stale Ollama weights → `qwen3.5:4b`/`embeddinggemma`, R2 off-site via rclone **with the 60-day retention rule and its payment-method caveat**, backup seal key, restore drill, credential-canary timer, Keychain-primary auth (the setup-token is a **P3** row) + `plutil` check, Devin login-method check, full installer run (telemetry off), `SDK_RECORD` fixtures, the alembic history diagnostic | Once, after the P0 deploy; again on a bare-metal rebuild |
```

- [ ] **Step 4: `docs/TROUBLESHOOTING.md`**

Replace the `_job_to_chat` passage (lines 435-440) with:

````markdown
# Since 2026-09-25 the binding is persisted: jobs.origin_channel/origin_ref/origin_thread.
psql assistant -tAc "SELECT origin_channel, origin_ref, origin_thread FROM jobs WHERE id='<job>'"
psql assistant -tAc "SELECT notice_kind, status, attempts, last_error FROM notifications WHERE subject_id='<job>'"
```

**Fix**: a `pending` row with attempts > 0 shows the Telegram error in `last_error`; no row at all means `NOTIFY_OUTBOX=0` is set or the job kind is internal (`_`-prefixed) / task-bound completion (the task card covers it). `python -m src.notify drain` delivers from a terminal. (The old in-process `_job_to_chat` dict is only used when the outbox is switched off.)
````

Append two symptom sections at the end of the file:

```markdown
## Symptom: job failed with `unrecognized_model: silent empty success` (terminal_reason `unrecognized_model`)

**Diagnostic**: `jobs.terminal_reason='unrecognized_model'`, audit event `job_result_rejected{requested_model, detail}`; the session produced no text, zero usage and `duration_api_ms=0`, or `model_usage` named a different model than requested.

### Root cause
The pinned bundled CLI (2.1.139) answers an id it does not know (e.g. Opus 5.5 / Sonnet 5 before the D13 bump) with a 'success' that did no work (`docs/research/llm-landscape-2026-09/claude-anthropic.md` §7). The runner now fails the job so `escalation.on_failure` retries on a known id. **Fix**: use an id from `_MODEL_ALIASES` (`telegram_bot.py`) / a `VALID_MODELS` member; new ids enter only after the SDK bump passes the replay gate (spec D13).

## Symptom: no completion/failure DM, or the daily 🔑 credential-canary alert fired

**Diagnostic**: `SELECT status, attempts, last_error FROM notifications ORDER BY created_at DESC LIMIT 5`; `cat volumes/telemetry/credential_canary.json`; `tail volumes/logs/credential-canary.log`.

### Root causes
1. Bot down → rows stay `pending` with `attempts=0`; `launchctl kickstart -k gui/$(id -u)/com.assistant.bot` — the 30 s poll delivers the backlog, nothing is lost.
2. Telegram rejected the send → `last_error` says why (chat not found = wrong `origin_ref`; entity errors cannot happen, the renderer sends plain text).
3. Canary `is_error` / `no ResultMessage` / `model_usage missing` / `sdk failed to run` → the Max Keychain login lapsed (or the SDK venv is broken): `claude login` on the Mini, re-run `bash scripts/credential-canary.sh`. The canary never uses the sealed setup-token, so a failure always means the fleet's own credential.

## Symptom: a launchd timer logs `pipenv: command not found` / `run rc=127` (schedule-monitor, credential-canary, healthcheck alerts)

**Diagnostic**: `grep -c 'command not found' volumes/logs/schedule-monitor.log volumes/logs/credential-canary.log volumes/logs/healthcheck.log`; `plutil -p ~/Library/LaunchAgents/com.assistant.schedule-monitor.plist | grep -A3 EnvironmentVariables` (empty → the plist predates 2026-09-25).

### Root cause
`pipenv` is a `~/.pyenv/shims` entry; launchd runs timers with `bash -lc`, which reads no `~/.bash_profile` (only `~/.zprofile` exists, and bash never reads it) and then runs `path_helper`, which demotes every non-system PATH entry. `bash -n` and the string-grep tests passed while the timer had been dead for days (prod `schedule-monitor.log`, 2026-09-24 onward). **Fix**: never `pipenv run` in a timer script — resolve `VENV_PY` (exported by `install-launchd.sh`'s `install_timer` since 2026-09-25, fallbacks `.venv/bin/python` → `command -v python`) and guard it with `import src.config`; on prod re-render the timers with `bash scripts/install-launchd.sh timers-only`. `tests/test_scripts_syntax.py::test_timer_scripts_never_use_pipenv_run` pins it.

## Symptom: `server-deploy` fails at `alembic upgrade head` with `Can't locate revision identified by '00N'`

**Diagnostic**: `bash scripts/alembic-current-check.sh` → `FAIL alembic_version=00N has NO script under alembic/versions/`; `git log --oneline -5 -- alembic/versions/` shows a revert or a deleted file.

### Root cause
A phase rollback reverted a migration FILE while prod's `alembic_version` still names it (spec §9 rollback rule: revert application code only — columns are nullable and ignored by older ORM models). **Fix**: restore the file (`git revert` of the revert, or `git checkout <sha> -- alembic/versions/00N_*.py`) and redeploy; only if the migration itself must go: `pipenv run alembic downgrade -1` on prod FIRST, then remove the file and its line in `alembic/applied_history.txt` in one commit. `tests/test_migrations.py::test_applied_history_matches_disk_chain` blocks the bad revert at the pytest gate `server-deploy` already runs — that is the whole belt. `scripts/alembic-current-check.sh` (runbook §11) is the owner-run diagnostic for confirming the live DB's state; it is not a deploy step (round-2 #8: "P0 alembic check kept as a test only, no SKILL.md edit").

## Symptom: `SDK_RECORD=1` is set but no `*.sdk.jsonl` files appear (or a job's recording stops mid-way)

**Diagnostic**: `grep -c 'sdk recorder disabled' volumes/logs/runner.err.log`; `ls -la volumes/audit_log/*.sdk.jsonl | tail`; `pipenv run python -c "from src.config import settings; print(settings.sdk_record)"` (run from the checkout whose `.env` the runner uses).

### Root causes
1. The setting is read at runner start — `launchctl kickstart -k gui/$(id -u)/com.assistant.runner` after editing `.env` (runbook §10).
2. A write error (disk full, `volumes/audit_log/` unwritable) disables the recorder for that job only and logs `sdk recorder disabled for <id>.sdk.jsonl: …` once; the job itself is unaffected by design (Review Focus 6). Fix the disk, the next job records again.
3. Recordings older than 30 days were archived by `retention.rotate_audit_logs` into `volumes/audit_log/archive/YYYY-MM.jsonl.gz` — copy P3 fixtures into `tests/replay/` before that (Open question 9).
```

Also update the "Root cause #5" paragraph (lines 383-387): append `Since 2026-09-25 `AskUserQuestion` is also OFF the default tool list (`registry.skills.DEFAULT_REQUIRED_TOOLS`); seven skills still declare it explicitly in `required_tools` — an owner decision (P0 plan, open question 2).`

- [ ] **Step 5: Lint, full suite, commit, sync, push — with the P0 PR note (rollback + token cost)**

Run: `pipenv run python scripts/lint_docs.py` → Expected: `All clean!` (module-graph imports declared; every module dir seeded; registries in sync).
Run: `pipenv run pytest -q` → Expected: 0 failures (skips: DB opt-in only).
Run: `git diff | grep -iE 'api[_-]?key|token|secret|password' | grep -v 'TELEGRAM_BOT_TOKEN=' | grep -v 'backup-seal.key' | grep -v 'setup-token'` → Expected: only documentation lines that name variables, no values.

```bash
git add .context/modules/runner/CONTEXT.md .context/modules/gateway/CONTEXT.md .context/modules/db/CONTEXT.md .context/modules/hosting/CONTEXT.md .context/modules/notify/CONTEXT.md .context/modules/gateway/skills/GOTCHAS.md .context/SYSTEM.md .context/INDEX.md docs/README.md docs/TROUBLESHOOTING.md docs/superpowers/specs/2026-09-25-multi-model-platform-design.md docs/superpowers/plans/2026-09-25-multi-model-platform-p0.md docs/research
git commit -m "docs: P0 multi-model — CONTEXT/SYSTEM/INDEX/README/TROUBLESHOOTING for result capture, notify outbox (dual-write), ghost commands, SDK-path canary, SDK_RECORD recorder, telemetry-off env, cost reconcile, alembic history, ops runbook; spec + plan + research set"
git fetch origin && git merge origin/main          # CLAUDE.md push gate 2
pipenv run pytest -q && pipenv run python scripts/lint_docs.py
git push origin main
```

The P0 merge/PR description (INV-4 lane) carries, per spec §9 ("Each phase's PR carries a rollback note naming the switch and the merge SHA"; "each phase's PR states its expected token cost"):

```markdown
## P0 — rollback note
- Kill switch: `NOTIFY_OUTBOX=0` in prod `.env` + bot-only kickstart (renderer-side; runner keeps dual-writing).
- Revert: `git revert` of the application commits <sha list> ONLY. Never revert `alembic/versions/007_p0_observability.py` (nullable columns, ignored by older models); if it must go: `alembic downgrade -1` on prod first, then remove the file + its `alembic/applied_history.txt` line. Merge SHA: <sha>.
- Shipped ahead (own PR): Task 0 Haiku 4.5 retirement patch <sha>.
## P0 — window cost (the spec's standing figure, §2.8/§9/§13)
- Build programme: **≈ 28 M tokens/week ≈ $115/month list-equivalent for ~13 weeks, `purpose=build`** (server-patch's measured shape: 15 jobs / 52.3 M tokens / $50 at 1-h rates ≈ $0.95/M). A phase may not exceed **15 % of the weekly Max window**; hold the remaining tasks if the running total crosses it.
- P0's share, measured at sign-off: <N> server-patch sessions, <tokens> tokens, $<usd> list-equivalent = <x> % of the week (cap 15 %).
- **D1's displacement decision** (spec §9 "Who executes", §2.8, §13 — D1 must name one): *either* `ALPHA_DAILY_JOB_VALVE` 12 → 6 (≈ −40 M/day) **and** `review-and-improve`'s idle trigger off in P0 rather than P4 (≈ −36 M/month), *or* D1 explicitly accepts "N `rejected` windows/week during build". Which was chosen: <A/B>. If A, Task 13 Step 6b executed it — link the commit.
- Runtime delta, Haiku→Sonnet on router/learning: **+≈ $8/month list-equivalent, 0 token change** (a model swap changes price, not tokens — spec §2.8, round-2 #49). Canary ≈ 30 tiny calls/month; recorder $0.
## P0 — exit evidence (fill at sign-off)
- tokens/cost/provider on every completed job: `SELECT count(*) FILTER (WHERE cost_usd_list IS NULL) FROM jobs WHERE status='completed' AND completed_at > <deploy ts>` → 0
- scheduled failure DM < 60 s; bot-restart lossless; `NOTIFY_OUTBOX=0` legacy path (Task 7 Step 5 log)
- **cost view reconciles at BOTH windows and at the 1-h rate** (spec §9 P0 exit): `scripts/cost-reconcile.py --windows 30,7 --db` → the 30-d block and the 7-d block each within 1 % of the JSONL sums, the per-kind step table present, `cache_write_5m_tokens` total = 0 (a non-zero value is the credits signature, spec §2.8) (Task 16)
- **lane-budget seed written**: `scripts/cost-reconcile.py --seed-lane-budgets` → `volumes/telemetry/lane_budget_seed.json` exists, trailing-7-d × 1.2 per lane (Task 16)
- **`model_usage` on utility calls lists only the requested model**: `grep -c 'utility_model_usage' volumes/logs/runner.err.log` after one routed job → the logged `served` list is exactly `["claude-sonnet-4-6"]` (Task 17; a second family is a finding to ledger `purpose=harness`, not a failure)
- **runner refuses to start with a planted vendor key**: `tests/test_claude_env.py::test_startup_env` green, and on prod `GEMINI_API_KEY=x <venv>/bin/python -m src.runner.main` exits non-zero with the INV-3 message (Task 17)
- **a project-scope auth override is refused**: `tests/test_settings_auth_override.py` green; one `provider_refused{reason=settings_auth_override}` in the fixture run (Task 19)
- **the durable trace is redacted**: `tests/test_audit_redactor.py` green; `grep -rc 'sk-ant-' volumes/audit_log/*.jsonl` → 0 (Task 20)
- **the provisioning-gap pre-check no longer defers the atlas rows** (after §12a row 6b is done): `grep -c 'provisioning_gap' volumes/audit_log/*.jsonl` over the last 24 h → 0, and the two previously-deferred atlas schedules ran (Task 21)
- `scripts/restore-drill.sh` → PASS (runbook §5); `plutil -p … | grep -c CLAUDE_CODE_OAUTH_TOKEN` → 0 (runbook §7)
- `python -m src.runner.sdk_record coverage` → OK (runbook §10) — may complete after sign-off; blocks P3, not P0 exit
```

Then request the deploy (INV-4 lane): `/task deploy server` — `server-deploy` runs `alembic upgrade head` (007), the pytest gate, seeds schedules and restarts; afterwards the owner runs runbook §6 (`install-launchd.sh timers-only`), §9 (full installer run at a quiet moment) and §10 (`SDK_RECORD=1` for a few days) on prod. **There is no runbook §11**: round 2 cancelled the `server-deploy/SKILL.md` edit round 1 had hidden inside P0 (spec §9 rollback paragraph: "alembic already fails loudly on a missing revision, so **no `server-deploy/SKILL.md` edit** is needed for this"; the §9 P0 row's "Protected touches" cell is **none**). Task 18's pytest assertions are the whole deliverable.

---

## Owner actions (auth config / sudo / protected paths) — exactly what, and when

Re-derived on 2026-09-27 from §12a **as round 2 left it** (round-2 #29 rewrote that table; round-2 #8 removed the one protected-path edit round 1 had hidden inside P0). The P0 row set is **0, 1, 2, 2b, 4, 4b, 5, 6, 6b** (+ 12's P0 half per D12, + 23 = the phase sign-off). Two corrections against the 09-25 cut: **§12a row 3 (`claude setup-token`) is now "needed before P3", not P0** — nothing at P0 can consume it, and minting a one-year credential three phases early is the exposure round 2 re-phased — and the `skills/server-deploy/SKILL.md` wiring row is **deleted**, not deferred. Nothing in this plan edits `.env`, a launchd plist's credentials, or a protected `SKILL.md`; the §9 P0 "Protected touches" cell is **none**, and every owner step is below.

| When | Action | Spec row | Why it is owner-only |
|---|---|---|---|
| **P0 entry** (45 min) | Decide **D0** (branch, as corrected), **D1** (design sign-off for P0–P1, *including what build weeks displace* — see the PR-note block above) and the **D25 posture** on the ≈ $963/month list-equivalent exposure | **§12a row 0**; §9 P0 entry cell | phase + posture decisions; D1 also gates Task 13 Step 6b |
| **P0 entry** (5 min) | Set `WEB_AUTH_TOKEN` in prod `.env` — **every §4.6 route is open while it is unset** (§12 D10) — and create the laptop Keychain item `ai login` will read | **§12a row 6**; §9 P0 entry cell | `.env` is a protected path; this is the only thing standing in front of the web surface until D10 lands at P1 |
| Before P0 sign-off (D1) | Read this plan and the spec; **approve P0–P1 only** (P2 waits for the P1 retro) | §12 D1; §12a row 23 | phase gate (round-1 #51) |
| Before Task 1 is merged | Confirm Task 0 (the Haiku standalone patch) is merged and deployed | §9 "Shipped ahead of P0" | the pre-P0 patch ships on its own INV-4 PR; the owner is notified per lane rules |
| P0 exit (~10 min) | Runbook §7 row 1: confirm Max tier (5x/20x); on claude.ai billing confirm usage credits $0, auto-reload OFF, spend limit $0; record both in runner GOTCHAS with the date | **§12a row 1**; D3 | account settings (`overflow_credits: disabled` lands in `providers.yml` in P3) |
| P0 exit (2 min) | Runbook §7 row 2: "Help improve Claude" OFF; record the date | **§12a row 2**; D4 | consumer privacy toggle |
| P0 exit (2 min) | Runbook §7 row 2b: confirm Devin's bundled `claude` is the **unmodified binary on the owner's own `/login`** (`claude /status` → "Login method: Claude account") and that Devin does not intermediate the token; otherwise sign Devin out of the Max credential. Record on the quarterly attestation card | **§12a row 2b**; §2.8 Claude row; round-2 #48 | the standing rule is "no third-party harness signs in with the Max credential"; only the owner can read that status |
| **P3, NOT P0** (~10 min — listed here only so it is not done early) | `claude setup-token` → sealed 0600 at `~/.config/ai-server/claude-setup-token`; mint date in GOTCHAS; NEVER in `.env`/plist/profile. §12a row 3 now reads "**needed before P3** (the Keychain login is the only credential until the executor seam exists; the sealed token is unused before P3)" | **§12a row 3** as round 2 re-scoped it; §12 D3; round-2 #28 | minting a one-year credential that outranks `/login` three phases before anything can consume it widens exposure for no gain. **The P0 half of this row survives on its own**: `plutil -p ~/Library/LaunchAgents/com.assistant.*.plist \| grep -c CLAUDE_CODE_OAUTH_TOKEN` → `0` is a P0 exit test and does not depend on a token existing (runbook §7) |
| P0 exit (10 min) | Set **`TRADIER_SANDBOX_TOKEN`** + **`FINNHUB_TOKEN`** in `projects/atlas/.env` — the P0 trading blockers. Until they are in, Task 21's pre-check defers the atlas rows that need them (`schedule_deferred{provisioning_gap}` + one DM), which is the intended behaviour, not a bug | **§12a row 6b**; §8.3 "Blockers"; §9 P0 scope; round-2 #43 | atlas `.env` is provisioning the owner holds; ≈ −$20–30/month of wasted runs is booked against P0 in §2.8/§13 |
| P0 exit (~20 min) | Runbook §3: create R2 bucket `ai-server-backups` + API token, `rclone config` remote `r2`, verify `rclone lsd r2:`; **confirm a payment method is on the Cloudflare account** (the R2 free tier requires one) and that `rclone size r2:ai-server-backups` stays under 10 GB — the 60-day retention rule is enforced by `backup.sh` (Task 13) | **§12a row 4** ("free ≤ 10 GB-month, payment method required, retention rule 60 d"); D12; round-2 #50 | account credentials (spec D3 "R2 credentials for backup") |
| P0 (2 min) | Runbook §1: `sudo pmset -a autorestart 1` | **§12a row 5**; D12 | sudo |
| Before Task 13's drill can fully PASS (5 min) | Runbook §4: `openssl rand -base64 48 > ~/.config/ai-server/backup-seal.key`, `chmod 600`, copy to the password manager | **§12a row 4b**; D12 (sealed `.env`/cloudflared copies) | a secret that must never be produced or stored by a job |
| Any time after Task 13 (≈10 min, network) | Runbook §2: `ollama rm phi3:mini deepseek-coder-v2:16b mistral:latest && ollama pull qwen3.5:4b && ollama pull embeddinggemma` | D12 (P0 row: "stale Ollama weights removed + `qwen3.5:4b`/`embeddinggemma` pulled"); §12a row 12 is the P3 bench | deletes host artefacts; RAM/disk judgement |
| After the P0 `server-deploy` | Runbook §6: on prod `bash scripts/install-launchd.sh timers-only`; then `bash scripts/credential-canary.sh` once | §9 P0 row (canary schedule) | launchd changes on the production host |
| After the P0 deploy, quiet moment | Runbook §9: full `bash scripts/install-launchd.sh` on prod (restarts runner/web/bot) so the service plists carry `DISABLE_ERROR_REPORTING`/`DISABLE_TELEMETRY`; verify with `plutil -p` | §2.4/§3; review #61 | service restart on prod |
| After the P0 deploy | Runbook §5: `bash scripts/restore-drill.sh` → PASS (the P0 exit criterion) | §9 P0 exit criteria | restore is a human-verified DR step |
| After the P0 deploy, for a few days | Runbook §10: `SDK_RECORD=1` in prod `.env` + runner kickstart; run `python -m src.runner.sdk_record coverage` until it says OK (≥ 20 jobs, ≥ 3 classes); remove the line | §2.4; §9 P0 row; review #27 | `.env` is a protected path |
| Only if DMs misbehave post-deploy | add `NOTIFY_OUTBOX=0` to prod `.env`, kickstart the **bot only** (renderer-side switch; runbook §8 covers parking the rows the runner keeps writing until its next restart) | §9 kill switch; review #28 | `.env` is a protected path |
| P0 exit (30 d after Task 3's deploy) | Read the `scripts/cost-reconcile.py --windows 30,7 --db` output in the P0 PR: **both windows** within 1 %, the per-kind step table, and the lane-budget seed. If the run disagrees with spec §2.8's ≈ $963/month anchor by > 10 %, Task 16 Step 5 stops and reports the delta — **the spec is the authority; the plan never rewrites §2.8 to match a run** | §2.8; §9 P0 exit criterion; round-1 #17, round-2 #18/#19 | sign-off evidence |
| Deploy approval | `server-deploy` on the INV-4 lane needs the in-session `code-review` LGTM + owner notification; no protected path is touched by any task, so no explicit approval beyond the lane's gates | INV-4 / C6 | — |

## Open questions (not blocking P0; carried to the owner)

1. **Seven skills still declare `AskUserQuestion` explicitly** (`new-project`, `project-evaluate`, `new-skill`, `research-report`, `restore`, `research-deep`, `self-diagnose`; `research-report/SKILL.md:32` even instructs its use) while `TROUBLESHOOTING.md` "Root cause #5" claims it was removed everywhere. Task 10 fixes only the default list. Strip it from those seven (a `SKILL.md` edit per skill, atlas two-repo rule does not apply) or leave until P1's `approvals(kind=question)` consumes it?
2. ~~Haiku residue outside P0 scope~~ — **resolved by the re-cut**: Task 0 (the pre-P0 standalone patch) covers all four spec-named sites plus the dashboard option; only `session._MODEL_BUDGETS`'s dead haiku key waits for P3's `registry/models.py`.
3. ~~Completion DM policy~~ — **closed 2026-09-27: it was never an open question.** Spec §4.2 has a "Card eligibility" paragraph (added by round-2 #32 precisely to stop ~20 machine jobs/day flooding the chat) and the §9 P0 scope cell names "card eligibility per §4.2" as part of the `src/notify/` deliverable. Task 5 now encodes it as the contract of `should_notify_job`: eligible completion channels `{telegram, pwa, cli}` (+ `web`, the current dashboard's spelling of the pre-P2 surface), failures always eligible, children inherit the parent's eligibility (`main.effective_origin_channel`, Task 6), and `schedules.notify ∈ {never, failures, always}` is a migration-008 column (P1) so every P0 schedule row behaves as `failures`.
4. **Escalation children**: a scheduled job that fails at L0 now DMs `❌ failed`, then its L1 retry may succeed silently (task-less completion DMs — so it will DM `✅ done`). Two DMs per incident; acceptable, or suppress the L0 failure DM when `escalation.on_failure` is declared (P2 FailedCard shows "escalation L1 queued" instead)?
5. **Where `queue_wait_ms` should stop** once P2 lanes add holds (`held_ms` separately) — spec §14 Q8; P0 measures enqueue→running only.
6. ~~`cli_version` via a `claude --version` subprocess~~ — **closed 2026-09-27: the spec already answers it.** §2.3 row 007 defines the column as "= `claude_agent_sdk._cli_version.__cli_version__`, \"2.1.139\" … **no subprocess or `SystemMessage` parse**" (round-2 #58). Verified in the pinned 0.1.81 wheel: the attribute exists and reads `2.1.139`. Task 3 reads it; the subprocess, the startup warm-up and their three tests are gone.
7. ~~Which cache-write rate is canonical~~ — **closed 2026-09-27: round-2 #19 decided it, and the question misquoted the current spec.** §2.8 now reads: cache writes priced from `usage.cache_creation.ephemeral_{1h,5m}_input_tokens` at the matching rate; **the subscription's TTL is 1 h and prod records 100 % of writes there** (45.3 M 1-h, **0** 5-m over 634 jobs); anchor **≈ $963/month** list-equivalent (opus-5 $414 / opus-4-7 $255 / sonnet-4-6 $151 / opus-4-8 $143), medians **opus-5 ≈ $3.43 / fleet ≈ $0.59**, DoneCard example **$3.49**; "round 1's $809 used the 5-m rate and was ≈ 19 % low", and "median Opus 5 job ≈ $0.71" is the figure §2.8 calls mislabelled. The 5-m column survives only as the **credit-overflow signature** (a non-zero reading means the TTL dropped, i.e. usage credits are being consumed — §2.8 tripwires). Task 16 prices each bucket at its own rate; `--cache-write-ttl` is deleted.
8. ~~`CLAUDE_CODE_OAUTH_TOKEN` warn-and-continue~~ — **closed 2026-09-27 in favour of fail-closed.** Spec §2.4 item (2) names the refusal set as `GEMINI_*|CEREBRAS_*|GROQ_*|CODEX_*|OPENROUTER_*|OPENAI_*|XAI_*|*_API_KEY|CLAUDE_CODE_OAUTH_TOKEN|ANTHROPIC_*` with no warn-only members (round-2 #2), and every one of those names reaches every Bash child of every job through the SDK's env overlay. `ANTHROPIC_BASE_URL` and `ANTHROPIC_AUTH_TOKEN` in particular are exactly the keys that redirect Max work to API billing. Task 17 refuses on all of them. The "could take the fleet down on a deploy" worry is answered by the same task's P0 exit evidence: the `plutil -p` scan proves no plist exports any of them, and `scripts/run.sh` gets `PIPENV_DONT_LOAD_ENV=1` so a P3 `.env` vendor key cannot trip a `pipenv`-launched runner.
9. **Raw recordings and the 30-day archive** (Task 15): `retention.rotate_audit_logs` gzips `*.jsonl` older than 30 days, recordings included. P3 must copy its 20 fixtures into `tests/replay/` before that, or Task 15 gains an exclusion. Which?

## Alignment with the reviewed spec (2026-09-25 round 1; round-2 delta 2026-09-27)

**Which round this reflects.** The 2026-09-25 re-cut was made against the spec's **round 1** only. The spec's **round 2** restarts its own numbering at #1 and has 58 rows (so a "#61"/"#64" exists only in round 1), and it changed P0 in ways the 09-25 cut did not carry. The round-2 delta was applied on **2026-09-27** — see the Verification log entry of that date for exactly what changed and what was skipped. Below: the authoritative P0 scope (spec §9 row "P0" — scope cell, entry, exit criteria, kill switch, "Protected touches" — plus the §9 test-gate and rollback paragraphs and the §12/§12a rows that name P0) mapped to tasks, then **two** review-log tables, one per round, then an honest list of what is still deferred.

### Spec P0 requirement → task

| Spec P0 requirement (source) | Task(s) | Tests / evidence |
|---|---|---|
| migration 007 (jobs/tasks columns, notifications outbox, token backfill) — §9 P0 row, §2.3 | 1 | `test_migrations.py` layer 1b |
| capture the full `ResultMessage` (`session.py:1094-1128`); typed `terminal_reason` (regex kept as belt); `model_usage ∋ requested ∧ duration_api_ms > 0` (silent-empty-success trap) — §9 P0 row, §2.4 | 2, 3 | `test_result_capture.py` (33 + wiring), `test_timeout_escalation.py` |
| `src/notify/` outbox + persisted origin; done/failed DMs for every launch, FailedCard for scheduled, **card eligibility per §4.2**; delivery status; `python -m src.notify send` for scripts — §9 P0 row, §4.5, §4.2 "Card eligibility" | 4, 5, 6, 7, 13 | `test_origin.py`, `test_notify_outbox.py` (eligible set `{telegram, pwa, cli}` + the `web` alias, failures always, `effective_origin_channel` child inheritance, `notify` is a P1/008 column), `test_notify_telegram.py`, `test_notify_runner_hooks.py`, `test_notify_bot.py` |
| runner-startup `os.environ` secret assertion on `GEMINI_*\|CEREBRAS_*\|GROQ_*\|CODEX_*\|OPENROUTER_*\|OPENAI_*\|XAI_*\|*_API_KEY\|CLAUDE_CODE_OAUTH_TOKEN\|ANTHROPIC_*` — §9 P0 row, §2.4 item (2) | 17 | `test_startup_env` (parametrized over the whole set, all fail-closed), `test_run_sh_does_not_export_dotenv` |
| `<cwd>/.claude/settings*.json` auth-override refusal → `provider_refused{settings_auth_override}` in `run_session` — §9 P0 row, §2.4 "INV-3 from project scope (P0, no protected path)" | **19** | `test_settings_auth_override.py` (fixture clone per key + a clean-clone pass + the source pin that the check precedes `_build_options`) |
| audit/stream redactor over `tool_result` previews and `text` before the JSONL / `jobs:stream` write — §9 P0 row, §2.4 "Audit/stream redaction (P0)" | **20** | `test_audit_redactor.py` (a `printenv`-shaped `tool_result` reaches neither sink raw; `sdk_record` delegates to the same pattern set) |
| **trading blockers**: `TRADIER_SANDBOX_TOKEN` + `FINNHUB_TOKEN` (§12a row 6b) **and the interim scheduler `provisioning_gap` pre-check** — §9 P0 row, §8.3 "Blockers" | **21** + Owner actions (§12a row 6b) | `test_provisioning_gap.py` (fixture manifest + `.env`; the INV-3 exemption; fail-open cases; one DM/day; row deferred, not enqueued) |
| `SDK_RECORD=1` recorder **with the `overage_*` fields included** — §9 P0 row, §2.8 metered-spend tripwires | 15 | `test_rate_limit_event_overage_fields_are_recorded` |
| `model_usage` on utility calls lists only the requested model (P0 **exit** criterion) — §9 exit cell, §2.8 Claude row | 17 (+0 for the baseline) | `test_utility_model_violation_reports_extra_families_only`, `test_utility_call_model_usage_is_single_model`; `utility_model_usage` audit line after one routed job |
| `review-and-improve` idle trigger removed here **if D1 picks that displacement** — §9 P0 row last clause, §2.8 "Load during build" | 13 Step 6b (conditional) | `test_alpha_valve_is_at_the_d1_value`, `test_alpha_drainer_survives_the_review_trigger_removal` |
| **dual-write**: runner keeps publishing `tasks:notify`/`jobs:done:<id>`; legacy consumer (`_done_listener`, `_job_to_chat`, `_task_notifier`) kept through P5; `NOTIFY_OUTBOX=0` is a real renderer-side switch — §9 kill-switch paragraph, §10 "Delete (P5 …)", exit criterion "with `NOTIFY_OUTBOX=0` a Telegram-launched job still DMs via the legacy path (test)" | 5, 6, 7 | `test_legacy_channel_published_in_both_modes`, `test_done_message_sends_legacy_when_outbox_off`, `test_done_message_is_dropped_when_outbox_on`, `test_task_notifier_and_listener_start_are_gated` |
| ghost commands fixed: `/cancel <prefix>` (durable, LREM + flip), `/status <prefix>`, `/proposals`; `/rate` out of help — §9 P0 row, §10 | 8 | `test_cancel_durable.py`, `test_telegram_commands.py` |
| `/clear` confirm — §9 P0 row | 9 | `test_telegram_commands.py` |
| `AskUserQuestion` off the default list — §9 P0 row, §10 | 10 | `test_default_tools.py` |
| Haiku swap "already shipped, above" — §9 "Shipped ahead of P0" (four edit sites: `llm_router.py:148`, `learning.py:258`, `skills/project-update-poll/SKILL.md:4`, `telegram_bot.py:132-133`), §11 Haiku row; test gate "registry-less Haiku swap smoke" | **0** (pre-P0 standalone patch; 11 is a pointer) | `test_utility_model.py`, `test_pure_functions.py`, `test_skill_contracts.py`; live smoke in Task 0 Step 4 |
| **credential canaries as `scripts/credential-canary.sh` on a launchd timer using the SDK-bundled CLI from the runner venv** — "the executor seam is P3" (§9 P0 row as round 2 rewrote it; never the brew binary; the runner's own path with the runner env) — §9 P0 row, §0a last rows, §11 | 12 (+17 for the env) | `test_canary.py` (SDK-path tests, `test_canary_never_reads_the_setup_token`), `test_scripts_syntax.py` |
| `SDK_RECORD=1` raw recorder (§2.4) and ≥ 20 recorded jobs across skill classes — §9 P0 row | 15 + Owner actions (runbook §10) | `test_sdk_record.py` (redaction, ordering, never-raises, coverage, AST hook pin) |
| the cost-reconcile script printing **both** the trailing-30-d and trailing-7-d windows **and the per-kind step** (the §2.8 anchor) **and re-seeding lane budgets weekly**; exit criterion "cost view reconciles with JSONL sums **at both windows and the 1-h rate**" — §9 P0 row + exit cell, §2.8 | 16 | `test_pricing.py` (each cache-write bucket at its own rate; the real opus-5 job = **$3.49**; the 5-m arm flags the credits signature; two windows in one pass; the trailing-7-d × 1.2 lane seed; unpriced never dropped); `--windows 30,7 --db` delta ≤ 1 % at P0 exit; weekly `com.assistant.cost-reconcile` timer |
| `DISABLE_ERROR_REPORTING=1`/`DISABLE_TELEMETRY=1` in the runner env — §9 P0 row, §2.4, §3 | 17 (+12 timer plists; runbook §9) | `test_claude_env.py`, `test_installer_timer_plists_carry_venv_env` |
| `tests/test_migrations.py` gains "every revision in `alembic_version` history exists on disk" — **"no `server-deploy` edit"** (§9 P0 row's own parenthesis; the §9 P0 "Protected touches" cell is **none**), rollback rule — §9 P0 row, §9 rollback paragraph | 18 (the script is an owner-run diagnostic, runbook §11 — **no SKILL.md wiring**) | `test_migrations.py` layer 1c, inside the `pytest -q` gate `server-deploy` already runs |
| ops debt: rclone→R2 off-site backup **with a 60-d retention rule** (`rclone delete --min-age 60d`; free ≤ 10 GB-month on a card-on-file account), `pg_dump atlas`, sealed `.env`/cloudflared copies, `pmset autorestart 1`, stale Ollama weights removed + `qwen3.5:4b`/`embeddinggemma` pulled (D12); exit criterion "restore drill passes" — §9 P0 row, §12a row 4, §12 D12 | 13 + Owner actions | `test_scripts_syntax.py` (backup/drill/runbook pins incl. `test_backup_has_retention_rule`); drill PASS |
| P0 entry: design sign-off (**D0 + D1** = P0–P1, §12a row 0); R2 creds; **`WEB_AUTH_TOKEN` set (§12a row 6 — every §4.6 route is open when unset)**; D3 items marked "P0" in §12a — §9 P0 row entry cell, §12 D1/D3/D10, §12a | Owner actions (rows cite §12a 0, 1, 2, 2b, 4, 4b, 5, 6, 6b, 12, 23; row 3 is **P3**, not P0) | runbook §7 verification commands |
| P0 exit: every completed job has tokens/cost/provider in Postgres; a scheduled failure DMs within 60 s; bot restart loses no DM — §9 P0 row | 3 (+1 backfill), 6+7, 7 | Task 7 Step 5 live checks |
| Window figures labelled by source (Claude row: vendor only for transitions; everything else "inferred"/"estimated") — §2.8, review #4 | 7 Step 3b | `TestQuotaNoticeLabelsTheSource`, `TestPauseSource`, `TestSessionPassesVendorOnlyForRateLimitEvent` |
| Keychain-primary auth; sealed setup-token only as a canary-triggered fallback; never in the plist; P0 exit test `plutil -p … \| grep -c CLAUDE_CODE_OAUTH_TOKEN` → 0 — §0a last rows, §3, §12a row 3 | 12, 17, 13 (runbook §7) + Owner actions | `test_canary_never_reads_the_setup_token`, `test_installer_never_exports_credentials`, runbook needles |
| per-phase re-approval gate; D1 approves P0–P1 only; phase ≤ 15 % of the weekly window; PR states expected token cost; rollback note with switch + merge SHA — §9 "Who executes", §9 rollback, §12 D1 | Global Constraints; 14 Step 5 | PR description checklist |
| C14 audit kinds unchanged; `jobs.status` CHECK untouched; protected paths untouched; CHANGELOG per module; pure/fixture tests; lint gate — Global Constraints | every task | `test_migrations.py`, `test_doc_lint.py`, `scripts/lint_docs.py` |
| P0 test gates, the spec's full list: `test_result_capture` (fake `ResultMessage` → columns; **the 1-h cache-write rate is used when `ephemeral_1h_input_tokens > 0`**), `test_notify_outbox`, every `tasks:notify` kind has an outbox equivalent, registry-less Haiku swap smoke, **`test_startup_env`**, **`test_settings_auth_override`**, **`test_audit_redactor`**, plist scan — §9 test-gate paragraph | 2 (incl. `test_ephemeral_1h_is_the_1h_arm…`), 5, 5 (`test_every_tasks_notify_type_has_an_outbox_kind`), 0, 17, 19, 20, 17 (`test_installer_never_exports_credentials`) | as named |

### Round 1 rows applied (spec review log, round 1 — 66 rows; these are the P0-relevant ones)

| # | What the reviewed spec changed | Applied in this plan |
|---|---|---|
| 4 | Claude window figures never labelled vendor-sourced unless a vendor event carried them (`RateLimitEvent` is a transition signal, not a gauge) | Global Constraints "Window figures are labelled by source"; Task 7 Step 3b (`quota_paused_text`, `QuotaExhausted.source`, `quota:last_source`) |
| 16 | The P0 plan "must be re-cut against the round-1 P0 row" | this re-cut: header note, Spec line, this section; Deferred table removed (every item now has a task) |
| 17 | Cost anchor re-based on the prod 30-d ledger; reconcile script made a P0 deliverable; §13 restated from it | Task 16 (`pricing.py`, `scripts/cost-reconcile.py`, §2.8/§13 restatement step) |
| 27 | `SDK_RECORD=1` raw recorder in P0; two-layer replay gate in P3 | Task 15; runbook §10; Owner actions |
| 28 | `NOTIFY_OUTBOX=0` restored nothing if the legacy path was deleted → P0 dual-writes, legacy consumer stays through P5, P0 test | Global Constraints kill-switch bullet (reworded to cite §10); Tasks 5–7 (already dual-write; tests named above) |
| 29 | Rollback rule rewritten (revert application code only; `downgrade -1` before removing a migration); alembic-history test in P0 | Global Constraints "Rollback rule"; Task 18; runbook §11 (**diagnostic only** after round-2 #8); Task 14 Step 5 rollback note |
| 31 | Keychain primary; sealed setup-token via `options.env` on canary-triggered fallback only; explicit executor env; vendor keys in `Settings` only; Claude-subprocess env assertion | Global Constraints "Auth posture"; Task 17 (overlay + the startup assertion, widened to the full §2.4 set by round-2 #2); Task 12 (canary never reads the token); runbook §7 rewritten (the old "into the launchd env" option removed); Owner actions (§12a row 3 moved to **P3** by round-2 #28) |
| 50 | Haiku 4.5 swap decoupled from spec approval; `project-update-poll` added; standalone `server-patch` ahead of P0 with four edit sites | Task 0 (new, executed first); Task 11 → pointer; Global Constraints "Pre-P0 standalone patch" |
| 51 | Programme too large → D1 approves P0–P1 only; re-approval gate; per-phase window cap; "who executes" | header note; Global Constraints "Phase economics"; Owner actions first row; Task 14 Step 5 PR checklist |
| 61 | `DISABLE_ERROR_REPORTING=1`/`DISABLE_TELEMETRY=1` in the executor env; checklist + P0 | Task 17 (`claude_env.py`, six option sites, plist belt); Task 12 timer plists; runbook §9 |
| 64 | Canary not on the runner's path → runs with the runner env and the runner's option conventions | Task 12 re-cut: **`scripts/credential-canary.sh` on a launchd timer invoking the SDK-bundled CLI from the runner venv** via `python -m src.runner.canary` (`claude_agent_sdk.query()` + runner option conventions + `claude_subprocess_env()` + the `result_capture` rule). **The executor seam is P3** — round-2 #28 found round 1's "canary via `ClaudeSdkExecutor`" to be a P0 dependency on a P3 component, and Appendix B orders the phrase removed by name; no `ClaudeSdkExecutor` appears anywhere in this plan's P0 mapping |

### Round 2 rows applied (spec review log, round 2 — 58 rows, separate numbering; applied to this plan 2026-09-27)

| # | What the reviewed spec changed | Applied in this plan |
|---|---|---|
| 2 | `env=` is an overlay, not a replacement; isolation rests on a secret-free runner environment; the fail-closed startup assertion names `GEMINI_*\|CEREBRAS_*\|GROQ_*\|CODEX_*\|OPENROUTER_*\|OPENAI_*\|XAI_*\|*_API_KEY\|CLAUDE_CODE_OAUTH_TOKEN\|ANTHROPIC_*` | Task 17: `VENDOR_KEY_PREFIXES`/`SUFFIXES`/`EXACT` cover the whole set, **all fail-closed** (`ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN`, `OPENAI_*`, `XAI_*`, any `*_API_KEY` and `CLAUDE_CODE_OAUTH_TOKEN` included); the parametrized `test_startup_env`; Open question 8 closed; `PIPENV_DONT_LOAD_ENV=1` in `run.sh` so the P3 `.env` keys cannot trip a `pipenv`-launched service |
| 3 | Setup-token fallback narrowed to owner-resumed jobs; **audit/stream redactor in `_handle_message` for `CLAUDE_CODE_OAUTH_TOKEN`/`ANTHROPIC_*`/vendor keys (P0)** | **Task 20** (new): `src/runner/secret_redact.py` wired into `_handle_message` on `text`, `thinking`, `tool_use.input` and `tool_result`; always on with `SDK_RECORD=0`; `sdk_record` re-exports the same `redact`; `test_audit_redactor.py`; Global Constraints bullet |
| 4 | INV-3 guarded only Bash-side assignment; `setting_sources=["project"]` loads `<cwd>/.claude/settings*.json`, which outranks `/login` → **P0 pre-session refusal `provider_refused{settings_auth_override}`** | **Task 19** (new): `session.settings_auth_override()`, `ProviderRefused`, the call before `_build_options`, `provider_refused` terminal reason + audit kind, `test_settings_auth_override.py`, the C1 row in runner CONTEXT.md |
| 6 | D10 reframed as a security prerequisite; **`WEB_AUTH_TOKEN` → a P0 runbook row with the "unset ⇒ open" note** | Owner actions: a **P0 entry** row for `WEB_AUTH_TOKEN` + the `ai login` Keychain item (§12a row 6) |
| 8 | "Exactly two owner PRs" was false — P0's alembic check edited `server-deploy/SKILL.md`; **kept as a test only, no SKILL.md edit**; "Protected touches" column added to the §9 table (P0 = none) | Task 18 keeps `applied_history.txt` + the pytest assertions as the whole deliverable; `scripts/alembic-current-check.sh` is an **owner-run diagnostic**; runbook §11 rewritten; the Owner-actions row and the "Alignment" claim removed; script header comment corrected |
| 18 | The budget model was seeded from a 30-d mean predating the alpha flywheel; anchor printed at **both** windows with the per-day series; **lane seed = trailing-7-d × 1.2, re-seeded weekly by the P0 reconcile script** | Task 16: `summarize_windows` + `--windows 30,7` by default, the per-kind step table, `lane_for`/`lane_seed`/`write_lane_seed` + `--seed-lane-budgets`, the weekly `com.assistant.cost-reconcile` timer; exit evidence cites both windows |
| 19 | Cache writes priced from `usage.cache_creation.ephemeral_{1h,5m}` at the matching rate (`cache_write_1h/5m_tokens` columns); anchor **≈ $963** with the per-model split; medians opus-5 ≈ $3.43 / fleet ≈ $0.59; DoneCard example $3.49; `test_result_capture` 1-h case | Task 1 (the two columns + the TTL-aware backfill, `priority` dropped), Task 2 (`cache_write_1h_tokens`/`_5m_tokens` + the spec's named 1-h case), Task 3 (`result_columns`), Task 16 (`price_usage` per bucket, `--cache-write-ttl` deleted, figures re-pinned to $3.49/$963, the 5-m credits flag), Open question 7 closed |
| 22 | The build programme's own window cost stated in tokens **and** dollars, repeated in each phase's PR template; D1 must name what build displaces | Global Constraints "Phase economics" (verbatim ≈ 28 M tokens/week ≈ $115/month for ~13 weeks, `purpose=build`); Task 14 Step 5's PR block filled in; Task 13 Step 6b executes the displacement if D1 chose it |
| 28 | P0's canary and setup-token both ran "through `ClaudeSdkExecutor`" — a P3 component; the runbook minted the token before anything could consume it | Task 12's mapping reworded to `scripts/credential-canary.sh` + the SDK-bundled CLI ("the executor seam is P3"); every `ClaudeSdkExecutor` mention gone from the P0 mapping; §12a row 3 moved to a "**P3, not P0**" line in Owner actions; the `plutil -p` exit test kept, since it does not depend on a token existing |
| 29 | §12a rewritten: rows 0, 2b, 4b, 6b, 7b, 9, 12b, 13/13b, 15b, 18b, 19b, 19c, 20b added or re-scoped; footer recomputed | Owner-actions table re-derived against the current §12a: the P0 row set is **0, 1, 2, 2b, 4, 4b, 5, 6, 6b** (+12's P0 half, +23); rows 0, 2b, 6, 6b added; row 4 gains the retention + payment-method caveat; row 4b cited by number |
| 32 | "Card eligibility" paragraph added at the top of §4.2 (human launches + `notify=always` get cards; `failures` default → FailedCard only; children inherit; `watch` posts a card for any job) | Task 5: §4.2 becomes the contract and docstring of `should_notify_job`; `COMPLETION_DM_CHANNELS` carries `{telegram, pwa, cli}` + the `web` alias; Task 6 adds `effective_origin_channel` so children inherit the parent's eligibility; `schedules.notify` stated as a P1/008 column; Open question 3 closed |
| 43 | "Blockers first" given phases: **P0** = the two trading tokens (§12a row 6b) + an **interim scheduler pre-check on manifest `env_required`** emitting `schedule_deferred{provisioning_gap}`; P1 = the two atlas patches; P3 = the `ScriptExecutor` version | **Task 21** (new): `Manifest.env_required` is read, `provisioning_gap`/`env_keys_present`/`PROVISIONING_EXEMPT`, the `_tick_schedules` pre-check + one DM/day, `test_provisioning_gap.py`; the atlas `manifest.yml` declaration is an atlas-front-door item; Owner-actions row for the two tokens |
| 48 | Devin's bundled `claude` classified against the "no third-party harness" rule — §12a row 2b, a P0 owner check | Owner actions: a P0-exit row for the Devin login-method check (`claude /status` → "Login method: Claude account") |
| 49 | Haiku→Sonnet is "**+≈ $8/month list-equivalent, 0 token change**", not "+8 M tokens"; **a P0 check that `model_usage` on utility calls lists only the requested model**; the side request ledgered `purpose=harness` if it persists | Global Constraints "Phase economics" and the PR note both corrected; Task 17 adds `utility_model_violation`/`log_utility_model_usage` + the `utility_model_usage` audit kind and its two tests; Task 0 Step 4 records the pre-swap baseline; P0 exit evidence line |
| 50 | R2 labelled "free" with unbounded growth → **60-d retention rule in `backup.sh`**; row 4 notes free ≤ 10 GB-month + payment method | Task 13 Step 3: `rclone delete --min-age 60d` in the guarded rclone block + `find -mtime +60` locally, replacing the "No retention cap locally" comment; `test_backup_has_retention_rule`; runbook §3 step 5; Owner-actions row 4 |
| 56 | `priority` had no consumer → **dropped from 007** (lanes replace it; `--priority` is not built) | Task 1: `priority` removed from `P0_JOB_COLUMNS`, the ORM block, the `sa.Column` list, and added to a `FORBIDDEN_007_COLUMNS` assertion so it cannot come back; the db CONTEXT.md line corrected |
| 58 | `overage_status`/`overage_resets_at` recorded on `quota_snapshots` and in `SDK_RECORD`, the **primary** `possible_credit_overflow` trigger; **`cli_version` needed no subprocess** | Task 15: `test_rate_limit_event_overage_fields_are_recorded` + the Interfaces note on why `RateLimitEvent` is recorded at all; Task 3: `cli_version()` reads `claude_agent_sdk._cli_version.__cli_version__` (verified `2.1.139` in the pinned wheel), the subprocess + startup warm-up + their three tests deleted, Open question 6 closed |

### Still deferred after the 2026-09-27 delta (honest list)

Nothing from the spec's §9 P0 **scope** cell is deferred. What remains outside this plan, each by the spec's own phasing rather than by omission:

- **Atlas's `manifest.yml` declaring `TRADIER_SANDBOX_TOKEN`/`FINNHUB_TOKEN` in `env_required`** — an atlas-repo change (LOOP.md §7 / `atlas-build` / an owner-dispatched atlas PR), never an INV-4 server patch (spec §8.3). Task 21 ships the mechanism; until that declaration lands the pre-check correctly defers nothing.
- **`watch <job>` / `mute <job>`** — §4.2's last sentence puts them in P1 (`test_views`), not P0.
- **`schedules.notify ∈ {never, failures, always}`** — migration 008, P1. P0 treats every schedule row as `failures`.
- **The P2 consumers of what P0 writes**: `quota_snapshots.overage_*` (009), `provider_ledger`, `lanes.<lane>.weekly_budget` reading `lane_budget_seed.json`, the CostCard's bucket-size line. P0 produces the inputs; P2 consumes them.
- **`routing-policy.yml`** consumption of the lane seed — P3 (§2.5 is a P3 deliverable).
- **`claude setup-token`** — §12a row 3 is now "needed before **P3**"; P0 asks the owner for no token and no P0 code reads one.
- **The `ScriptExecutor` `provisioning_gap` pre-check** and the migration of the credential canary and the settings check onto `ClaudeSdkExecutor` — all P3 by §9.
- **Open questions 1, 4, 5 and 9** (the seven skills that declare `AskUserQuestion`; double DMs on an escalation L0→L1; where `queue_wait_ms` stops once P2 adds holds; the 30-day gzip of raw recordings) remain owner questions. Questions 2, 3, 6, 7 and 8 are closed.

Placeholder scan: no "TBD/TODO/implement later/similar to Task N" in this document; every code step carries the code; every referenced function is defined in a task's Interfaces block. (Task 21's `TestSchedulerIntegration` bodies are `...` with the assertions spelled out in comments and the fixture style named — the only ellipses in the document, and they are test scaffolding whose contract is stated, not a deferred decision.) Type consistency checked across both re-cuts: `claude_subprocess_env()` (Task 17) ← Task 12 `canary_options` and Task 0's builders; `ResultCapture`/`served_model_violation` (Task 2) ← Task 12 `evaluate_ping`; `cache_write_1h_tokens`/`_5m_tokens` (Tasks 1, 2) ← Task 3's `result_columns` ← Task 16's `price_usage`; `secret_redact.redact` (Task 20) ← Task 15's `sdk_record`; `SdkRecorder` hook ← Task 3's `_run_in_process` shape; `ProviderRefused` (Task 19) ← Task 2's `terminal_reason_for_exception`; `build_ops_notice`/`enqueue_notice` (Tasks 5, 6) ← Task 21's deferral DM; `Manifest.env_required` (Task 21) ← the scheduler tick; `QuotaExhausted(source=)` ← Task 7's `pause_queue`; `job_completed.cost_usd_list` (Task 3) ← Task 16's `usd_sdk`; `applied_history.txt` ← Task 1's 007.

---

**Execution handoff.** Plan complete and saved to `docs/superpowers/plans/2026-09-25-multi-model-platform-p0.md`. Recommended execution: **subagent-driven**, in the Global Constraints execution order — **0** (own PR) → 1 → 18 → 2 → 3 → 19 → 20 → 15 → 17 → 4 → 5 → 6 → 21 → 7 → 8 → 9 → 10 → 12 → 16 → 13 → 14 = **21 executable tasks; Task 11 is a retired number, do not dispatch it**. File order is not execution order: every heading carries an `**Execution position:**` line and Tasks 12, 15, 16, 17, 18, 19, 20 and 21 open with a Step 0 prerequisite probe. Each task gets its own test cycle; Tasks 5–7 share the `Notice`/renderer interfaces and a fresh reviewer per task catches a drifted signature before the bot task builds on it; Tasks 12 and 17 share `claude_subprocess_env()`; Tasks 15 and 20 share `secret_redact.redact`. Steps marked **host step** need launchd, a live SDK or the prod DB and cannot run in an isolated worktree — skip them there and confirm with the owner. A shipped mistake costs the owner missed DMs, a wrongly-failed job, a mispriced ledger, or a leaked credential in the durable trace.

---

## Verification log (2026-09-25)

Findings from the 2026-09-25 verification pass applied in place. A first pass had already folded the Task 1–7 corrections in; this pass verified those and completed Tasks 6–14 plus the closing sections.

**Critical — `pipenv run` under launchd (Tasks 12, 13, Global Constraints, Task 14).** `install_timer` now writes an `EnvironmentVariables` dict with `PATH` (`${VENV_DIR}/bin` first) **and** `VENV_PY=${VENV_DIR}/bin/python`; verified on this host that `bash -lc` → `path_helper` demotes the plist PATH behind the system dirs, so `VENV_PY` (not PATH) is the contract. `credential-canary.sh`, `healthcheck-all.sh` (`notify_send`) and `schedule-monitor.sh` (collector line 21 **and** `send_dm`) resolve `VENV_PY` → `.venv/bin/python` → `command -v python`, guard with `import src.config`, and treat "no interpreter" as a logged failure with the curl fallback; no `pipenv run` remains in any timer script. The line-21 repair rides Task 12 (which exports the env it consumes) so Task 12's new `test_timer_scripts_never_use_pipenv_run` is green at its own commit; Task 13 keeps only `send_dm`. `tests/test_scripts_syntax.py` asserts the ban for the four timer scripts, the `VENV_PY` guard, the installer env block, and matches `-m src.notify send` / `-m src.runner.canary` instead of `python -m …`. Task 12's live run uses `env -i … /bin/bash -lc` to reproduce launchd's environment (positive, negative and interpreter-missing checks). `timers-only` is documented as re-rendering the three existing timers — the prod `schedule-monitor` fix. New TROUBLESHOOTING symptom "`pipenv: command not found` / `run rc=127`" in Task 14 Step 4; hosting CHANGELOG gotcha.

**Major — `skills_dir` monkeypatch (Task 10).** `_skill` patches the class (`monkeypatch.setattr(type(settings), "skills_dir", property(lambda self: tmp_path))`), the `tests/test_registry_failclosed.py:24-27` precedent; layout `tmp_path/'t'/SKILL.md` kept.

**Major — doc-lint sequencing (Tasks 2, 3, 5, 6, 7, 8, 12 vs 14).** Verified Tasks 2/3/5 already carry the Paths line / graph rows / Depends-on edits and the `tests/test_doc_lint.py` run. Added the missing ones: Task 6 (`main.py` += `notify.outbox`, git add `.context/SYSTEM.md`), Task 7 (`telegram_bot.py` += `notify.outbox, notify.telegram`), Task 8 (`jobs.py` += `audit_log`; `telegram_bot.py` += `runner.proposals` — the function-level import in `cmd_proposals` counts), Task 12 (`canary.py` Paths line + graph row). Task 14 Steps 1–2 are now verify-only for those items, with the exact expected cells; the `src/notify/telegram.py` row's Depends-on is `—`.

**Major — `NOTIFY_OUTBOX` dual-write semantics (Global Constraints, Tasks 5, 6, 7, 13, 14).** Global Constraints bullet was already correct; the Task 6 implementation was not: `_notify_task` now always publishes `tasks:notify` and adds the row only when the switch is on; `_finish_job` keeps `publish_done` unconditional. Task 7 makes the switch renderer-side: `_done_listener`'s body is extracted into `_handle_done_message` (sends only when off; pops `_job_to_chat` either way), `_task_notifier` gets an `if settings.notify_outbox: continue` gate, `_outbox_listener` starts only when on. Task 7 also flips `settings.notify_outbox` to `True` in the same commit as the listener (Task 5 ships `False`; db CHANGELOG entry added). Tests: `test_legacy_channel_published_in_both_modes` (parametrized; `import pytest` added to the file) and the spec exit-criterion tests `test_done_message_sends_legacy_when_outbox_off` / `test_done_message_is_dropped_when_outbox_on` / `test_task_notifier_and_listener_start_are_gated`. Task 6's live check now proves the legacy path with the switch off; Task 7 Step 5 gains the bot-only kill-switch check; runbook §8 and the Owner-actions row say "kickstart the bot only" and how to park stale pending rows. Task 6/7 CHANGELOGs, runner CONTEXT bullet and gateway CONTEXT section reworded.

**Major — served-model alias (Tasks 2, 3).** Verified already applied: `requested_matches_served`, `test_bare_alias_request_is_not_rejected`.

**Major — notification policy (Tasks 5, 6).** Verified already applied: `should_notify_job(..., origin_channel=)`, `COMPLETION_DM_CHANNELS`, the three scheduler/dispatch tests. Open question 3 now names the tuple to widen.

**Major — deployability between Tasks 6 and 7.** Verified `notify_outbox: bool = False` in Task 5; the flip is now an explicit Task 7 step (see above).

**Minor — concurrent delivery (Tasks 5, 7).** Task 5's `claim_notice` / `release_stuck_sending` / `sending` status were already present; Task 7's `_drain_outbox` now claims before sending (`attempts_before` captured for `mark_failed`), `_outbox_listener` releases stuck rows at startup, the `_Store` fake and `_wire` mirror the contract, and `test_row_claimed_elsewhere_is_skipped` pins it.

**Minor — `cli_version` warm-up, `terminal_reason` on all failure branches + AST pin, cancelled-job escalation guard, Task 3 Step 3 line 1094-1095 wording, `test_job_visibility` justification, `kickstart` instead of `run.sh restart`, NULLIF backfill + Step 6 expectation, `notice_sent`/`notice_failed` audit kinds + §2.7 deviation + `job_result_rejected` note, `via scheduler` builder fix + test, expected test counts (33 / 41), Task 4 Step 5 code blocks, PTB 22.8, `session.py:471`, `main.py:333-335`, `types.py:1143`.** All verified present from the first pass.

**Minor — this pass.** Task 7 live check #4 expects `· error · via scheduler` (FailedCard wording), not `terminal: …`. Task 9 shows the `_handle_button(update, ctx)` signature and uses `ctx.bot_data`. Task 11 (now Task 0 after the re-cut) Step 4's live smoke is concrete (`grep -c '"method": "llm"'` → 1; `llm router SDK error` count unchanged from a recorded baseline); Step 3 and Open question 2 named `skills/project-update-poll/SKILL.md:4` and `tests/test_pure_functions.py:143` (both now edited by Task 0 itself). Task 12 Step 5 shows only the two wrapper lines around the byte-identical `for svc … done` (lines 68-122); Files cites `:68-122`, `:166-192`, `:193-198`. Task 13 cites `:127-134` / `:180-185` and states that the `token=`/`chat_ids=`/`chat_id=` reads stay; the swing replacement is shown in full. A "Deferred from spec §9 P0 row" table listed the `SDK_RECORD=1` recorder, the 30-day cost-reconcile script, the `DISABLE_ERROR_REPORTING`/`DISABLE_TELEMETRY` env pair and the `alembic_version` history test — **superseded by the re-cut below** (Tasks 15, 16, 17, 18; nothing is deferred any more).

Not changed: no other file was touched; protected paths, migration 007's additive/nullable shape and the `ck_jobs_status_valid` constraint are as before.

## Verification log (2026-09-27 — the round-2 delta)

Second verification pass, against the spec **as round 2 left it**. The 09-25 re-cut was made against round 1 only; the header and the Alignment section said "rounds 1–2" while the applied-rows table listed eleven round-1 numbers and no round-2 row. That mislabelling is corrected and the round-2 delta is applied in place. Ground truth re-checked on this box before applying anything: `pipenv run python -c "from claude_agent_sdk import _cli_version; print(_cli_version.__cli_version__)"` → **2.1.139**; prod's newest 30 `job_completed` events carrying `cache_creation` sum to **2,157,923 tokens 1-h, 0 tokens 5-m**, with the flat `cache_creation_input_tokens` equal to the 1-h figure to the token; `grep -rln "claude-haiku" skills/` → **three** files; `settings.skills_dir` → the **production** tree; `SERVER_ROOT=$PWD pipenv run …` does **not** override `.env` while `pipenv run env SERVER_ROOT=$PWD …` does; `cd /tmp && <venv>/bin/python -c "import src.config"` → `ModuleNotFoundError`; `projects/atlas/manifest.yml` declares `env_required: [DATABASE_URL, ANTHROPIC_API_KEY]` against an `.env` holding `DATABASE_URL` and (correctly) no `ANTHROPIC_API_KEY`; `parse_module_graph` on the plan's three notify rows returned `notify.__main__ -> ['drain` for launchd alerters and ops']`.

### Corrected — critical

1. **Migration 007's column set (Tasks 1, 2, 3, 16).** Replaced the single flat `cache_write_tokens` with `cache_write_1h_tokens` + `cache_write_5m_tokens` in `P0_JOB_COLUMNS`, the `Job` ORM block, the `sa.Column` list and the backfill (nested `ephemeral_{1h,5m}_input_tokens`, with the flat key falling back into the **1-h** arm), and **deleted the `priority` column** (round-2 #56: "no `priority` column — lanes replace priority and `--priority` is explicitly not built") with a `FORBIDDEN_007_COLUMNS` assertion so it cannot return. Propagated into `ResultCapture.cache_write_1h_tokens`/`_5m_tokens` (+ the spec's named gate `test_ephemeral_1h_is_the_1h_arm_and_the_flat_key_falls_back_to_it`), `result_columns`, the canary's token sum and `pricing.price_usage`. 007 is additive and never reverted (Global Constraints rollback rule), so this is the one shape a later task could not cheaply undo.
2. **The `src/notify/__main__.py` SYSTEM.md row broke the lint gate.** `src/context/module_graph.py:47` splits each table row on the raw `|`, so `` `python -m src.notify send\|drain` `` gave the row two extra cells and read Depends-on out of the wrong one — reproduced exactly: `notify.__main__ -> ['drain` for launchd alerters and ops']`, three spurious `check_module_graph_imports` warnings, `scripts/lint_docs.py` no longer printing `All clean!`, and `tests/test_doc_lint.py::test_module_graph_imports` red for Tasks 5-8, 12, 15-17 and Task 14's whole-suite gate. Rewritten as `` `python -m src.notify send` / `drain` `` in both places, with a note forbidding a literal `|` in any cell.
3. **Task 0's gates could not go green in this checkout.** The dev `.env` points `SERVER_ROOT` at the **production** tree, so `registry.list_all()` grades prod's skills: the moment Task 0 repoints `_MODEL_ALIASES`, both `test_skill_contracts` and the new `test_no_skill_frontmatter_on_haiku` go red until the deploy propagates, and CLAUDE.md push gate 1 forbids committing red. `test_no_skill_frontmatter_on_haiku` now monkeypatches `type(settings).skills_dir` at the repo's own tree (the `tests/test_registry_failclosed.py:23-27` precedent), and Steps 4/5 run `pipenv run env SERVER_ROOT="$PWD" pytest …` — verified to be the form that works, unlike `SERVER_ROOT=$PWD pipenv run`.
4. **Two P0 deliverables had no task at all.** Added **Task 19** (the `<cwd>/.claude/settings*.json` auth-override refusal → `provider_refused{settings_auth_override}` in `run_session`, with the fixture-clone test the spec names as `test_settings_auth_override` and the C1 row) and **Task 20** (the always-on `src/runner/secret_redact.py` wired into `_handle_message`, with `test_audit_redactor`). Both are in §9's P0 scope cell and its test-gate list; the plan had zero occurrences of either name. Task 15's recorder is opt-in, so with the shipped `SDK_RECORD=0` nothing had been redacting the durable JSONL, the stream, `ai-mcp` reads or the learning extractor's input.
5. **A third missing P0 deliverable: the trading blockers.** Added **Task 21** (the interim scheduler `provisioning_gap` pre-check — `Manifest.env_required` is read for the first time, `provisioning_gap`/`env_keys_present`, the `_tick_schedules` skip + `schedule_deferred` + one DM per row per UTC day, fail-open on everything else) and the Owner-actions row for `TRADIER_SANDBOX_TOKEN`/`FINNHUB_TOKEN` (§12a row 6b). **The live data was a trap**: atlas's manifest already declares `ANTHROPIC_API_KEY` in `env_required` and that key is absent from its `.env` **by design** (INV-3), so a naive pre-check would have deferred every atlas row on its first tick — hence `PROVISIONING_EXEMPT` and its named test.
6. **The plan asked the owner to edit a protected path round 2 had cancelled.** Runbook §11 and an Owner-actions row told the owner to wire `scripts/alembic-current-check.sh` into `skills/server-deploy/SKILL.md`, one line below the plan's own claim that nothing edits a protected `SKILL.md`. Round-2 #8 resolved this as "P0 alembic check kept as a test only (no SKILL.md edit)" and §9's P0 "Protected touches" cell is **none**. The row is deleted, runbook §11 is now "a DIAGNOSTIC, not a deploy step", the script's header comment says so, and the Alignment row no longer claims `server-deploy` checks `alembic current`.

### Corrected — major

7. **Task 16 met neither half of its re-stated scope.** It printed one window with per-model rows only. Now: `summarize_windows` + `--windows 30,7` **by default**, a per-kind (skill) step table rowed from `job_started.skill`, `lane_for`/`lane_seed`/`write_lane_seed` + `--seed-lane-budgets` writing `volumes/telemetry/lane_budget_seed.json` (trailing-7-d × 1.2), a weekly `com.assistant.cost-reconcile` launchd timer with Task 12's `VENV_PY` contract, and a non-zero exit when 5-minute cache writes appear (the credits signature). `--cache-write-ttl` deleted (it was parsed and never used).
8. **Task 16's numbers were round-1 numbers.** Re-pinned to §2.8 as it now reads: anchor **≈ $963**, the four per-model rows, medians **opus-5 ≈ $3.43 / fleet ≈ $0.59**, and the real opus-5 job at **$3.49** (verified exactly: 2.40 M × $0.50 + 111 k × $10 + 47 k × $25 = 3.485). The `$0.70675` / `$809` / `$0.71` assertions are gone, and so is Step 5's instruction to "restate §2.8 and §13 in the same commit" — replaced by "if the run disagrees by > 10 %, stop and report the delta; the spec is the authority". **One honest correction against the finding as written**: §2.8's "fleet ≈ $0.59" is the median of per-job *costs*, not the cost of the median *shape* (which prices at **$0.5298** at Sonnet 1-h rates). The test now asserts each figure against the statistic it actually is and the report prints both (`median_job`, `median_usd_by_family`); asserting `$0.59` for the shape would have been a fabricated number.
9. **Task 17's startup refusal set was narrower than the spec's, and one key was warn-only.** Widened to §2.4 item (2) verbatim — prefixes `GEMINI_ CEREBRAS_ GROQ_ CODEX_ OPENROUTER_ OPENAI_ XAI_ ANTHROPIC_`, suffix `*_API_KEY`, exact `CLAUDE_CODE_OAUTH_TOKEN` — **all fail-closed**, with the `ANTHROPIC_API_KEY` INV-3 message kept as a special case. Open question 8 closed. The spec's named gate `test_startup_env` now exists and is parametrized over the whole set. Also fixed the clearing loop in the existing test: it iterated *prefixes* and called `delenv("GEMINI_")`, which removes nothing — live, not hypothetical, because `pipenv run` copies `.env` into `os.environ` and §12a rows 10/11 put vendor keys there at P3. Added `PIPENV_DONT_LOAD_ENV=1` to `scripts/run.sh`'s three service lines with a string pin.
10. **`cli_version` was obtained the way the spec forbids.** Replaced the `lru_cache`d `claude --version` subprocess, the synchronous warm-up inside `_check_subscription_auth`, the AST pin and two monkeypatched-subprocess tests with a read of `claude_agent_sdk._cli_version.__cli_version__` (§2.3 row 007: "**no subprocess or `SystemMessage` parse**"; round-2 #58), verified present in the pinned 0.1.81 wheel. Added `test_session_spawns_no_subprocess_for_the_cli_version` so it cannot come back; Open question 6 closed; the Task 17 monkeypatch comment corrected; Task 3's Step-2 failure list and both CHANGELOG entries updated.
11. **The Owner-actions table was keyed to round 1's §12a.** Re-derived against the current table: the P0 row set is **0, 1, 2, 2b, 4, 4b, 5, 6, 6b** (+12's P0 half, +23). Added row 0 (D0 + D1 *including the displacement* + D25, P0 **entry**), row 2b (the Devin login-method check), row 6 (`WEB_AUTH_TOKEN` — "every §4.6 route is open when unset" — P0 **entry**), row 6b (the two trading tokens); cited row 4b by number; row 4 gains the 60-day retention and payment-method caveat. **Moved `claude setup-token` to a "P3, NOT P0" line** (§12a row 3 as round 2 re-scoped it) while keeping the `plutil -p … | grep -c CLAUDE_CODE_OAUTH_TOKEN` → 0 exit test, which does not depend on a token existing.
12. **Card eligibility was an open question instead of a contract.** §4.2's "Card eligibility" paragraph is now the docstring and contract of `should_notify_job`: eligible completion channels `{telegram, pwa, cli}` with `web` as the P0 alias for the current dashboard, failures always eligible, `schedules.notify` stated as a migration-008 (P1) column so P0 treats every schedule row as `failures`, and **children inherit the parent's eligibility** via a new pure `main.effective_origin_channel(own, parent)` resolved from `jobs.parent_job_id` (verified set on both child paths: `mcp_dispatch.py:120/134` and `main.py:770-773`). Open question 3 closed; two tests added.
13. **Phase economics carried no figures and one wrong one.** Global Constraints and the PR template now quote the spec verbatim (≈ 28 M tokens/week ≈ $115/month list-equivalent for ~13 weeks, `purpose=build`; the 15 % cap; D1 names the displacement), and the runtime-delta line is corrected from "+≈ 8 M tokens/month" to "**+≈ $8/month list-equivalent, 0 token change**" (round-2 #49). Task 13 gains a **conditional** Step 6b that drops `ALPHA_DAILY_JOB_VALVE` 12 → 6 and removes only `_check_idle_queue_review`'s trigger *if D1 chose that option* — `_check_idle_queue_alpha` is explicitly protected, with a regression test, per the P4 exit criterion.
14. **The `model_usage` utility check did not exist.** Every `model_usage` assertion in the plan was the main-job silent-empty-success trap, which passes when a second model is also listed. Added `claude_env.utility_model_violation` / `log_utility_model_usage`, the `utility_model_usage` audit kind, two tests, the wiring in `llm_route`/`extract_learning`, a pre-swap baseline command in Task 0 Step 4, and a P0 exit-evidence line. A second family logs a finding to ledger `purpose=harness` — it never fails the call.
15. **R2 grew without bound.** Task 13 adds `rclone delete --min-age 60d` inside the existing guarded rclone block and `find -mtime +60` locally, replacing `backup.sh:59`'s "No retention cap locally — 2TB SSD, keep everything"; `test_backup_has_retention_rule` pins both needles; runbook §3 gains the free-tier conditions (≤ 10 GB-month, payment method required).
16. **File order ≠ execution order, and one disagreement broke the build.** In file order Task 12 precedes Task 17, but `tests/test_canary.py` imports `claude_env.claude_subprocess_env()`, which Task 17 creates — a checkbox-walking runner got a collection error at Task 12 Step 1. Rather than move ~4,000 lines of sections (and risk breaking cross-references mid-rewrite), every task heading now carries an `**Execution position:** N of 21 — previous / next` line, Tasks 12, 15, 16, 17, 18, 19, 20 and 21 open with a **Step 0 prerequisite check** that stops with "execute Task <n> first", and Global Constraints states the file-order caveat plus the rule that `session.py`/`main.py`/`telegram_bot.py` anchors must be re-located by symbol after an earlier task edited the same file.
17. **Two launchd guards ran before their `cd`.** `schedule-monitor.sh`'s `"$VENV_PY" -c 'import src.config'` was inserted at line 18, above its own `cd "$PROJECT_DIR"` at line 20 — and the editable install is inert on this host, so the probe only resolves from the project root. A manual run from anywhere else would blank `VENV_PY`, log `run rc=127 … reinstall timers` and exit 0: the watchdog dark while blaming the timer install. The `cd` now moves above the block (with a test asserting the order), and `healthcheck-all.sh` — which never `cd`s — uses the subshell form `(cd "$PROJECT_DIR" && "$VENV_PY" -c 'import src.config')`.
18. **A test that would silently stop pinning what it claims.** `test_installer_service_plists_carry_the_flags` sliced the installer on `for svc in "${SERVICES[@]}"; do` … `\ndone\n`; Task 12 indents that loop inside `if (( ! TIMERS_ONLY )); then … fi`, after which the marker stops matching and the slice grows to the end of the file while the assertion still passes. Re-sliced between `<key>PATH</key>` and `<key>RunAtLoad</key>` — markers Task 12 does not move (verified at `install-launchd.sh:98` and `:102`, inside the services block).
19. **`overage_*` was satisfied only incidentally.** Task 15 relied on `dataclasses.asdict` walking `RateLimitEvent.rate_limit_info` without naming the fields, so a future field allowlist would silently drop the signal §2.8 makes the **primary** `possible_credit_overflow` trigger. Added `test_rate_limit_event_overage_fields_are_recorded` and an Interfaces note.
20. **The Alignment section was not honest about its round.** The applied-rows table is relabelled "Round 1 rows applied", a second table covers the seventeen round-2 rows with the task each landed in, the canary rows drop every `ClaudeSdkExecutor` mention (Appendix B orders the phrase removed by name), and "nothing is deferred" is replaced by an explicit list of what remains deferred and why.

### Corrected — minor

21. **Line citations.** `_set_task_status` 876-882 (was 878-883); `session.py`'s `_run_in_process` call at `:1003` (was 1005) and the `job_completed`+return block `:1019-1033`; `main.py` DeployRefused `:481-483` and DeployNeedsApproval `:502-504`; `telegram_bot.py` plain-text enqueue `:320-324`, `cmd_chat` `:347-352`, the thread-reply continuation `:800-805`, the `choice` enqueue `:1000-1005`; Task 6's escalation publish unified at `:732-739` (the local `import` at 732 plus the publish at 733-739, deleted together). All read off `cat -n` of the current tree.
22. **Task 1 Step 3** now says "after the `review_outcome` column **and its explanatory comment** (`:105-107`)" — inserting at 106 would have orphaned the `# ^ "LGTM" | …` comment from its column.
23. **Task 9's `/clear` widening is now stated.** `_do_clear` also moves the filter from `[queued, running]` (`telegram_bot.py:493`) to `[queued, deferred, running]`; that is intended, but it is a semantic change and is labelled as one in the Interfaces block, the docstring and a new test.
24. **Task 5's chained assert** (`a == b in c`) split into two asserts — correct Python that reads as a precedence bug.
25. **Task 14 Step 3** gains the `.context/INDEX.md` row for `.context/modules/notify/CONTEXT.md` (CLAUDE.md requires one per new documentation file; Task 5 creates it), plus rows for the redactor and the deferral symptom.
26. **Task 0's grep claim** corrected from "one file" to the three the command actually returns, with `skills/README.md:12` and `skills/TEMPLATE.md:15` added to the edit list, the `SITES` tuple and the `git add` line — `TEMPLATE.md` is what new skills are copied from, and the id it advertises stops resolving on 2026-10-15.
27. **Task 11 is no longer a dispatchable heading.** Retitled "(retired number — see Task 0) — NOT A TASK, do not dispatch", its checkbox removed, and its two verification commands moved into Task 1 as a host-only **Prerequisite check** paragraph (they need `psql assistant`, which an isolated worktree does not have). Task 3's live smoke, Task 17's `ps eww` check and Task 19's/Task 20's live probes are likewise marked as host steps.
28. **Test counts and expectations** updated where the edits changed them: Task 2 33 → 35 PASS (the two named cache-write-TTL cases), Task 3's Step-2 nine-failure list (the warm-up pin is gone, the 3-tuple annotation is in).

### Skipped, and why

- **Physically reordering the task sections** to match execution order (one finding's first option). Moving Tasks 15-18 and 14 would rewrite ~4,000 lines and invalidate cross-references mid-edit for no behavioural gain; the finding's own second option — per-heading `**Execution position:**` lines plus Step 0 prerequisite probes — is implemented instead, and it also documents the dependency rather than just hiding it. The risk the finding names (a checkbox-walking runner hitting Task 12 before Task 17) is closed by the Step 0 probe.
- **Editing `projects/atlas/manifest.yml`** to declare `TRADIER_SANDBOX_TOKEN`/`FINNHUB_TOKEN` in `env_required`. Atlas is its own GitHub-canonical repo and spec §8.3 is explicit that atlas changes are "born in the atlas dev clone, dispositioned through LOOP.md §7, executed by the `atlas-build` worker or an owner-dispatched atlas PR, **never INV-4 server patches**". Recorded as an atlas-front-door item in Task 21 and in the deferred list; Task 21's mechanism is inert until it lands, which is the safe direction.
- **Asserting `$0.59` as the price of §2.8's median shape** (see item 8). That figure is a median of per-job costs; the median shape prices at $0.5298. Writing `$0.59` into a test would have been a fabricated constant, so the test asserts both statistics honestly and Step 5 compares the per-job median against §2.8.
- **Deleting `scripts/alembic-current-check.sh`** (one finding's first option). Kept as an explicitly-labelled owner-run diagnostic — the second option the same finding offers — because it is the only way to inspect the live `alembic_version` after a revert, and keeping it costs nothing now that no SKILL.md wiring is implied. Its `test_alembic_current_check_script_invariants` needles stay.
- **Relabelling the plan header "round-2 delta NOT yet applied"** (one finding's literal instruction). That instruction was conditional on the delta not being applied; it is now applied, so the header says "re-cut against round 1 of the reviewed spec; round-2 delta applied 2026-09-27" and names the seventeen rows. Where the two findings on this point conflicted, the one that leaves the document self-consistent after the edits wins.

**Where findings conflicted, the safer-for-the-running-server reading won**, and each is noted above: the `model_usage` utility check lives in Task 17 (which already edits both utility builders) with only a read-only baseline in Task 0, rather than being duplicated; the `provisioning_gap` pre-check fails **open** on every unknown, because a pre-check that can silence 41 schedules on a file-read error is worse than the waste it prevents; the redactor deliberately leaves `final_text_chunks` unredacted, because that string is the job result and the `TASK_COMPLETE:` marker input, so redacting it would change outcomes rather than the trace.

Not changed: no file other than this plan was touched. Protected paths (`src/runner/guards.py`, `scripts/lint_docs.py`, `.env`, `.context/PROTOCOL.md`, `MISSION.md`, `skills/{server-patch,server-deploy,new-skill}/SKILL.md`) are edited by no task — the §9 P0 "Protected touches" cell is `none` and the plan now matches it. Migration 007 remains additive and nullable-only, `ck_jobs_status_valid` is untouched, no audit event kind is renamed (three are added: `provider_refused`, `schedule_deferred`, `utility_model_usage`, plus the four from the 09-25 cut), and every task that touches a module still carries its CHANGELOG entry.

## Re-cut log (2026-09-25, against the reviewed spec — round 1)

The draft above was written from the pre-review spec; **round 1** of the review then changed the P0 scope (round-1 #16 says this plan "must be re-cut against the round-1 P0 row"). Applied in place, no other file touched. **Round 2's delta was applied separately on 2026-09-27 — see the Verification log entry of that date; this log covers round 1 only.**

- **Scope now authoritative**: spec §9 P0 row + test-gate + rollback paragraphs, §12/§12a rows naming P0, and **round-1** review rows #4, #16, #17, #27, #28, #29, #31, #50, #51, #61, #64 — header note, Spec line, and the "Alignment with the reviewed spec" section (which replaces the old Self-review and the "Deferred from spec §9 P0 row" table).
- **Tasks added**: 0 (pre-P0 standalone Haiku patch, four spec-named sites + dashboard option + `test_pure_functions.py:143`), 15 (`SDK_RECORD=1` raw recorder + coverage CLI), 16 (`pricing.py` + `scripts/cost-reconcile.py`), 17 (`claude_env.py` telemetry-off overlay on all six `ClaudeAgentOptions` sites + vendor-key startup assertion + plist belt), 18 (`alembic/applied_history.txt` + tests + `scripts/alembic-current-check.sh` as an owner-run diagnostic).
- **Tasks re-labelled / re-cut**: 11 → pointer to Task 0 (the reviewed spec moved the Haiku swap out of P0); 12 re-cut so the canary pings through `claude_agent_sdk.query()` with the runner's option conventions, `claude_subprocess_env()` and the `result_capture` rule (never the brew CLI, never the setup-token; timer plists gain the telemetry keys); 7 gains Step 3b (reset-time source label: `vendor` only from a `RateLimitEvent`); 13's runbook §7 rewritten for Keychain-primary auth + sealed token + the `plutil -p` exit test, and §9–§11 added (full installer run, `SDK_RECORD` fixtures, alembic deploy check); 14 gains the new modules/scripts, TROUBLESHOOTING symptoms and the PR rollback/token-cost note.
- **Global Constraints** gain: rollback rule, auth posture, Claude subprocess env, raw recorder, window-figure labelling, phase economics (D1 = P0–P1, 15 % window cap), pre-P0 patch; the kill-switch bullet cites §10's "delete only in P5"; execution order made explicit (task numbers stable, 15–18 appended).
- **Review Focus** gains items 6–10 (recorder never costs a job; secrets never land in a recording; canary fails loudly and proves the Keychain login; a revert never strands `alembic_version`; unpriced models are counted, never mispriced) — each pinned in the named task.
- **Owner actions** rewritten with §12a row numbers (1–5, 12, 23) and the protected-path steps (`.env` `SDK_RECORD`, `server-deploy` SKILL.md preflight, full installer run).
- **Open questions**: #2 resolved by Task 0; #7 (5-m vs 1-h cache-write rate — the spec header and §2.8 disagree), #8 (`CLAUDE_CODE_OAUTH_TOKEN` warn vs fail-closed), #9 (recordings vs the 30-day archive) added.
- Verified against the working tree while re-cutting: all four Haiku sites are still on `claude-haiku-4-5-20251001` (the standalone patch has not shipped yet — Task 0 is real work, not a pointer to done work); `SDK_RECORD`/`DISABLE_TELEMETRY` appear nowhere in `src/`; `ClaudeAgentOptions.env` exists in SDK 0.1.81 and is an overlay (`subprocess_cli.py:430-436`); `session.py` imports `llm_router`, hence the import-free `claude_env.py`; `audit_index.rebuild_index` globs `*.jsonl` (Task 15 pins that recordings are skipped); `audit_log.append` writes `{"ts", "job_id", "kind", …}` (Task 16 keys on `ts`); `tests/test_scripts_syntax.py` is created in Task 12, so Task 18's script pins live in `tests/test_migrations.py`.
