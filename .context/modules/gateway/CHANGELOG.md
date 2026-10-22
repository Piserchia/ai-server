# Changelog: gateway

<!-- Newest entries at top. Every session that modifies this module appends here. -->

## 2026-10-21 — A7 (docs only): Notifications section names `[Details]` / `/status` and the out-of-band alert path; `_job_to_chat` gotcha closed

**Agent task**: Observability Phase 1 re-cut plan A7, Docs-1 bucket (`docs/superpowers/plans/2026-10-21-observability-phase1-recut.md` §6).
**Files changed**:
- `.context/modules/gateway/CONTEXT.md` — "Notifications back to user" gains the owner-facing summary (which cards carry `[Details]`, `/status <prefix>` as the pull side, the launchd alerters' `python -m src.notify send` path that bypasses the bot) and points at the new TROUBLESHOOTING checklist.
- `.context/modules/gateway/skills/GOTCHAS.md` — the 2026-04-20 "done-listener mapping lost on bot restart" gotcha is closed by the outbox (A5/A6); the entry says in which mode it still applies.

**Why**: the A6 section described the mechanism; the owner-felt behaviour and the diagnosis path were the plan's Docs-1 bucket, assigned to A7.

**Side effects**: none (no code).

**Gotchas discovered**: none.

## 2026-10-21 — A6: the bot delivers the notifications outbox; `[Details]`; `format_job_status`; quota notices via the outbox; `NOTIFY_OUTBOX` on

**Agent task**: Observability Phase 1 re-cut plan A6 (`docs/superpowers/plans/2026-10-21-observability-phase1-recut.md` §6; design of record P0 plan Task 7 minus Step 3b).
**Files changed**:
- `src/gateway/telegram_bot.py` — `_OUTBOX_POLL_SECONDS = 30`; `_drain_outbox(app, *, legacy_mode) -> (sent, failed, skipped)` claims each pending row (`claim_notice`; rowcount 0 → counted `skipped`, never sent twice beside `python -m src.notify drain`), renders it with `src/notify/telegram.py`, `send_via_bot`, then `mark_sent` / `mark_failed` (token-free error text via `_safe_send_error`, backoff from the pre-claim attempts). In `legacy_mode` a row whose kind is not in `OPS_NOTICE_KINDS` is `mark_skipped(…, "legacy_mode")` — the legacy `jobs:done` / `tasks:notify` renderers cover job/task cards — and only the ops kinds are sent. `_outbox_listener(app, *, legacy_mode)`: `release_stuck_sending()` once (failure logged, not fatal), subscribe `notify:outbox`, `get_message(timeout=30)` → drain, so a bot restart loses no DM. `_post_init` ALWAYS starts it with `legacy_mode = not settings.notify_outbox` (D-P1-10: the kill switch keeps the ops notices flowing). `_handle_done_message(app, channel, data) -> bool` is the per-message gate of `_done_listener`: pops `_job_to_chat` either way, returns False with the switch on, else the slice's `_deliver_done` (DM text unchanged). `_task_notifier` gates on `settings.notify_outbox` right after the JSON decode. `_quota_notifier(app, *, poll_seconds=60)` writes `quota_paused` / `quota_resumed` OPS rows through `enqueue_notice(build_ops_notice(…, subject="quota:<lane>"))` instead of direct DMs (delivered in both switch positions), once per state change per lane: the global Anthropic pause (A3's `quota_paused_text`) and, new, every enabled non-Anthropic lane via `quota.is_provider_paused` (pure `provider_paused_text(provider, reset_at, reason)`, names the lane and `/resume <provider>`). `jd:<job8>` branch in `_handle_button` before the task lookup → `format_job_status(job)` reply WITHOUT `parse_mode` (`"Job not found."` otherwise). Pure `format_job_status(job) -> str`: status, kind, lane via `lane_label`, terminal reason, turns, tokens, api time, list-equivalent cost, origin, 300-char error, 600-char summary, ≤ 4000 chars. `_lane_label` is now a thin alias of `notify.outbox.lane_label` (one definition).
- `src/config.py` — `notify_outbox` default `False` → **`True`** (the consumer exists now). Recorded in the db CHANGELOG.
- `.context/SYSTEM.md` — `telegram_bot.py` Depends-on += `notify.outbox, notify.telegram`; the two notify rows drop their `(A6)` markers.
- `.context/modules/gateway/CONTEXT.md` — public interface (`format_job_status`, `provider_paused_text`, `jd:` callback, `_handle_done_message`, the outbox listener), Notifications section, Dependencies.
- `tests/test_notify_bot.py` (new, 36 collected), `tests/test_telegram_commands.py::TestParseCallback::test_job_details_callback_parses`.

**Why**: spec §9 Phase-1 exit criteria — every human launch (Telegram AND web) DMs on completion/failure, a scheduled failure DMs within 60 s with a `[Details]` button, a bot restart loses no DM, `NOTIFY_OUTBOX=0` + bot kickstart restores today's job/task DMs while a `quota_paused` notice still arrives.

**Gotchas**: `_quota_notifier` keeps `quota.last_source()` and `quota_paused_text(` inline (A3's `tests/test_quota.py::test_notifier_reads_last_source` pins them by source); its first tick after a bot start re-notifies a lane that is already paused (pre-A6 behaviour, kept — the outbox row is the alert history). `_drain_outbox` counts a lost claim as `skipped`, mirroring `python -m src.notify drain`. The `[Details]` reply goes through `query.message.reply_text` (not `edit_message_text`) so the card stays readable.

## 2026-10-21 — A3: the quota_paused DM names the reset time's source

**Agent task**: Observability Phase 1 re-cut plan A3 (`docs/superpowers/plans/2026-10-21-observability-phase1-recut.md` §6; design of record P0 plan Task 7 Step 3b).
**Files changed**:
- `src/gateway/telegram_bot.py` — pure `quota_paused_text(reset_at, reason, source) -> str` renders `⏸ Queue paused (subscription quota).\nReset at HH:MM UTC (vendor|estimated).\nReason: <reason[:200]>`; the label is `vendor` ONLY when `reset_at` is a datetime AND `source == "vendor"` (no time → `Reset at unknown (estimated)`, any other source value → `estimated`). `_quota_notifier` renders the body once per state change via `quota_paused_text(reset_at, reason, await quota.last_source())` and sends the same text to every allowed chat (the resume text is unchanged: `▶️ Queue resumed.`).
- `.context/modules/gateway/CONTEXT.md` (behaviour note + the `src.runner.quota` dependency line).

**Why**: spec §2.8 / review #4 — the owner must be able to tell a vendor-reported reset time from the runner's default window. Every other surface that names a reset time (`/status`, `/api/quota`, the runner log) is left as is and still never says "vendor".

**Side effects**: the pause DM gains a parenthesised label on its second line; the first and third lines are byte-identical to before. `quota.last_source()` is one extra Redis GET per pause transition (not per tick).

**Gotchas discovered**: none.

## 2026-10-21 — A2: every launch persists its origin (`jobs.origin_*`, `tasks.origin_*`); the bot stamps `tasks.awaiting_since`

**Agent task**: Observability Phase 1 re-cut plan A2 (`docs/superpowers/plans/2026-10-21-observability-phase1-recut.md` §6; design of record P0 plan Task 4 + Task 3b's `JobOut` fields).
**Files changed**:
- `src/gateway/jobs.py` — `enqueue_job` gains keyword-only `origin_channel=None, origin_ref=None, origin_thread=None`. When `origin_channel` is omitted both channel and ref are derived from `created_by` via A1's `origin_from_created_by` (an explicit `origin_ref` still wins); an explicit `origin_channel` is taken as-is and its ref is NOT derived (the web launch is `web`/NULL, matching 008's backfill CASE) and must be one of `ORIGIN_CHANNELS` (`ValueError` otherwise — review round 1; the vocabulary is fixed by 008's CASE and `models.py`, not widened per caller). An empty `origin_channel` derives like an omitted one; empty `origin_ref` / `origin_thread` land as NULL; ref/thread clipped to 64 (every declared channel already fits the 16-char column).
- `src/gateway/telegram_bot.py` — the two `Task(...)` constructors (`_create_task_with_job`, `cmd_god`) and the six owner-facing `enqueue_job` sites (`_create_task_with_job`, `_handle_plain_text`, `cmd_chat`, `cmd_god`, `_handle_thread_reply`, `choice`) pass `origin_channel="telegram", origin_ref=str(chat_id)`; the thread-reply and choice continuations also pass `origin_thread=str(task.thread_message_id)`. After the root reply is sent, `_create_task_with_job` and `cmd_god` persist `origin_thread=str(reply.message_id)` on BOTH the Task (beside the kept `thread_message_id`) and the Job — two `sql_update` calls in the one session. The self-diagnose enqueue (`bot-error-handler`) stays derived (`system`). `tasks.awaiting_since` is cleared (`None`) on the active transitions (thread reply, `approve_plan`, `choice`) and set to now on `reopen` (new `from datetime import datetime, timezone`). `_job_to_chat` is still populated everywhere it was (A6 retires its use).
- `src/gateway/web.py` — `create_job` passes `origin_channel="web"` (ref NULL); `JobOut`/`_serialize` gain `origin_channel`, `origin_ref`, `queue_wait_ms` through the existing `getattr(..., None)` idiom (additive; JSON consumers see extra keys only). `_check_auth` and every route decorator untouched.
- `tests/test_origin.py` (+26: `TestEnqueueSignature` drives `enqueue_job` against a recording session + fake redis; `TestAwaitingSince`; `test_queue_wait_ms`; the AST pins; `TestCancelledGuard` behavioural + AST), `tests/test_web.py` (+2 `TestJobOutOriginFields`), `tests/test_telegram_commands.py` (+3 `TestLaunchOrigin` incl. `test_web_and_telegram_launches_persist_origin`, which compiles the recorded `sql_update` statements and asserts `origin_thread` lands on `tasks` AND `jobs`).
- `.context/modules/gateway/CONTEXT.md` — `enqueue_job` signature; the helpers are no longer "uncalled".

**Why**: spec §0 bullet 2 — the in-process `_job_to_chat` dict was the only job→chat binding (lost on every bot restart) and web launches had none at all; A4's `build_job_notice` and A6's delivery read the persisted columns instead. `awaiting_since` gives stuck asks an age (spec §2.3).

**Side effects**: every new Job row from these producers carries `origin_channel ∈ {telegram, web}`; everything else derives (`scheduler` from the runner's own `_tick_schedules`, `system` for the long tail). Rows older than this commit are covered by 008's backfill. No behaviour change for the legacy `tasks:notify` / `jobs:done` consumers.

**Gotchas discovered**: `plans.spawn_plan_jobs` and the deferred branch of `mcp_dispatch` build `Job(...)` directly and bypass `enqueue_job`, so their rows carry NULL `origin_channel` / `origin_ref` / `origin_thread` — the channel is NOT derived for them (an earlier draft of this entry claimed it was; corrected in review round 1). Deliberately not expanded into `plans.py` / `mcp_dispatch.py`; A4/A5 must treat NULL as `system` or inherit through `parent_job_id` / `task_id`. Recorded in `.context/modules/runner/skills/GOTCHAS.md`.

## 2026-10-21 — A1: `ORIGIN_CHANNELS` + `origin_from_created_by` born in `jobs.py` (uncalled; wired in A2)

**Agent task**: Observability Phase 1 re-cut plan A1 (`docs/superpowers/plans/2026-10-21-observability-phase1-recut.md` §6; design of record P0 plan Task 4's pure part).
**Files changed**:
- `src/gateway/jobs.py` — `ORIGIN_CHANNELS = ("telegram", "web", "cli", "scheduler", "system")` and the pure `origin_from_created_by(created_by) -> (origin_channel, origin_ref | None)`: `telegram:<chat>` → `("telegram", <chat>)`, `web` → `("web", None)`, `scheduler` → `("scheduler", None)`, everything else (`dispatch-mcp`, `event-trigger*`, `learning:`, `writeback:`, `escalation*`, `plan:`, `evaluator:`, `eval-fix:`, `auto-continue:`, `bot-error-handler`, `deploy-autopilot`, `owner-*`, …) → `("system", created_by)`; refs clipped to 64 (the `String(64)` column), an empty ref is `None` never `''` (the SQL side's `NULLIF`). `enqueue_job` untouched.
- `tests/test_origin.py` (new) — `TestOriginFromCreatedBy` (parametrized over the producer vocabulary above incl. bare `telegram:`, whitespace, `''`, `None`), `test_ref_fits_column`, `test_telegram_ref_fits_column`, `test_every_channel_is_declared`.
- `.context/modules/gateway/CONTEXT.md` — public interface lists the two helpers and that they are uncalled until A2.

**Why**: migration 008's `_BACKFILL_ORIGIN` CASE and this helper must agree arm for arm so backfilled and new rows read the same; `tests/test_migrations.py::test_008_origin_backfill_case_matches_origin_from_created_by` drives the helper over the vocabulary and pins the SQL arms textually (the CASE cannot run on SQLite). Born in A1 so the migration and its Python twin land in one reviewed commit.

**Side effects**: none at runtime — nothing calls either symbol in this commit. A2 wires them into `enqueue_job(..., origin_channel=None, origin_ref=None, origin_thread=None)` and A4's notice builder reads the stamped columns.

**Gotchas discovered**: the `created_by` vocabulary in the tree is wider than the P0 plan's test table (`event-trigger`, `learning:`, `writeback:`, `evaluator:`, `eval-fix:`, `bot-error-handler`, `deploy-autopilot`, `owner-*`); all of it is `system`, which is why the helper has no allow-list and never raises.

## 2026-10-21 — T9: docs, registries, runbook (no code change)

**Agent task**: cross-vendor writer slice T9 (`docs/superpowers/plans/2026-10-21-cross-vendor-writer-slice.md` §5). No file under
`src/gateway/` changed. Docs that describe gateway behaviour were touched:
- `docs/TROUBLESHOOTING.md` — the new `provider_refused` symptom states that
  the web `POST /api/jobs` (HTTP 422) and `/task --model=` (`ModelFlagRefused`
  reply) run the same registry resolution at submit time, so a job that got as
  far as `provider_refused` came from a schedule payload or a stale client;
  the new `job_held` symptom documents `/resume <provider>`, the per-lane
  `/status` lines and `GET /api/quota`'s `providers` map (all T6/T7).
- `.context/INDEX.md` "Additions 2026-10-21" — points at the gateway CONTEXT
  for the provider surfaces.
`.context/modules/gateway/CONTEXT.md` was already current from T7 and is
unchanged.

## 2026-10-21 — T7: provider everywhere the owner looks

**Agent task**: cross-vendor writer slice T7
(`docs/superpowers/plans/2026-10-21-cross-vendor-writer-slice.md` §5).
**Files changed**:
- `src/gateway/telegram_bot.py` — `parse_flags` resolves `--model=` THROUGH
  the registry: alias tables first (unchanged), then
  `registry.models.resolve(...).canonical`, so the stored value is always
  the canonical `[provider/]model_id`; an unknown provider or model raises
  the new `ModelFlagRefused(raw, reason)` (a `ValueError`) at parse time
  instead of passing the raw string through. `/task`, `/chat` and `/god`
  go through `_parse_flags_or_reply`, which also applies
  `resolve_enabled` (ROUTER_PROVIDERS_ENABLED) and answers a refusal with
  the registry's reason plus the accepted list (`_model_flag_help`), as
  plain text — no Task row, no job, same rule as the web's 422. `/jobs`
  rows carry `` `provider/model` `` after the skill (`_lane_label`: pure;
  pre-007 rows show the model alone, queued rows nothing). The done/failed
  DM is `_deliver_done` → `_done_dm_text` (pure) and appends the lane plus a
  non-`ok` `terminal_reason`, read from the job ROW (`_job_lane`; the
  session stamps the provider before the process starts, so every terminal
  path has it) — a lookup failure degrades to the pre-T7 text. The task
  "details" card names the lane the same way.
- `src/gateway/web.py` — `JobOut` + `resolved_provider`, `model_served`,
  `terminal_reason` (additive, None on pre-007 rows; `_serialize` reads them
  with `getattr(..., None)` so older row stand-ins still serialize). Jobs
  table gains a **Provider** column (title = served model / non-ok reason);
  the page's `esc()` helper now also escapes `"` and `'` because that
  `title=""` is the first attribute-context use of it (review minor).
  The model `<select>` is grouped: one `<optgroup label="<provider>">` per
  ENABLED provider, `default` outside any group, models.yml order.
- Tests: `tests/test_telegram_commands.py` (+22: parse-time refusals with
  reasons, canonical storage, `_lane_label`, `_done_dm_text`, handler-level
  refusal creates nothing / enabled id enqueues canonical, `/jobs` rows,
  `_deliver_done` row lookup + DB-error degradation), `tests/test_web.py`
  (new, 9: JobOut fields, `/api/jobs` rows, Provider column, optgroups).
  Existing T1/T0 gateway tests untouched and green.

## 2026-10-21 — T6: per-provider quota on the surfaces

**Agent task**: cross-vendor writer slice T6
(`docs/superpowers/plans/2026-10-21-cross-vendor-writer-slice.md` §5).
**Files changed**:
- `src/gateway/web.py` — `GET /api/quota` keeps `{paused, reset_at, reason}`
  (the global = Anthropic pause) and ADDS `providers: {<p>: {paused,
  reset_at, reason}}` for every non-Anthropic registry provider. The
  dashboard banner also renders each paused lane ("<p> lane paused — its
  jobs are held").
- `src/gateway/telegram_bot.py` — `/status` opens with one line per paused
  provider lane (`_paused_lane_lines()`: name, reset HH:MM UTC, reason,
  the `/resume <p>` hint); nothing when no lane is paused. `/resume`
  without an argument is unchanged (global pause); `/resume <provider>`
  lifts ONE lane via `quota.clear_provider` and never touches the global
  key; an unknown provider name is refused with the known list.
- Tests: `tests/test_quota.py` (web shape + paused lane; `/status` with
  and without a paused lane; `/resume codex` vs bare `/resume`; unknown /
  not-paused provider).
- Review round (code-review T6, lgtm): literal `\u2014` escape in a
  `cmd_status` comment replaced with a plain dash. No behaviour change.

## 2026-10-21 — T1: alias table, dashboard dropdown and POST /api/jobs fed by the models registry

**Agent task**: cross-vendor writer slice T1
(`docs/superpowers/plans/2026-10-21-cross-vendor-writer-slice.md` §5).
**Files changed**:
- `src/gateway/telegram_bot.py` — `_MODEL_ALIASES = registry.models.alias_table()`
  (same keys and targets as the hand-written table after T0; add or move an
  alias in `models.yml` now). `_RETIRED_MODEL_ALIASES` and `parse_flags`
  unchanged: `--model=opus` → `claude-opus-4-7`, `--model=haiku` →
  `claude-sonnet-4-6`, and a qualified `--model=codex/gpt-6-luna` passes
  through raw for the session's registry check (parse-time refusal with a
  reason is T7).
- `src/gateway/web.py` — `POST /api/jobs` resolves `req.model` through
  `registry.models.resolve_enabled` and stores the canonical form in
  `payload["model"]`; an unknown id, unknown provider or disabled provider
  is **HTTP 422** `model refused: <reason>` (closes the T0-review hole where
  a stale client could still submit `claude-haiku-4-5-20251001`). The
  dashboard `<select name="model">` is rendered from the registry at import
  (`_model_options_html()`: enabled providers only, yml order, canonical
  values; grouping by provider is T7). `_INDEX_HTML` is now built from
  `_INDEX_TEMPLATE` via a `{{MODEL_OPTIONS}}` sentinel.
**Tests**: `tests/test_models_registry.py` §5 (alias table equality,
`parse_flags` pass-through) and §11 (422 on retired id / unknown provider /
disabled provider, alias canonicalised into payload, no-model path
unchanged, dropdown contents). `tests/test_web_god_gate.py`,
`tests/test_telegram_commands.py`, `tests/test_pure_functions.py` unchanged
and green.

## 2026-10-21 — T0: Haiku 4.5 retired from the alias table and dashboard

- `telegram_bot._MODEL_ALIASES`: `haiku` / `haiku-4-5` keys removed, so
  `VALID_MODELS` (derived from the VALUES) no longer admits
  `claude-haiku-4-5-20251001` in any SKILL.md. New `_RETIRED_MODEL_ALIASES`
  maps those two aliases to `claude-sonnet-4-6`; `parse_flags` consults it
  after `_MODEL_ALIASES` so `--model=haiku` typed from muscle memory lands on
  the replacement instead of leaking a bare `haiku` string into
  `job.payload.model`. Retired models must never be re-added to
  `_MODEL_ALIASES` (that re-admits them to the skill-contract allowlist).
- `web.py`: dashboard model `<select>` drops the `haiku 4.5` option.
- Plan: `docs/superpowers/plans/2026-10-21-cross-vendor-writer-slice.md` T0.
  Tests: `tests/test_haiku_retirement.py`, `tests/test_pure_functions.py`
  (`test_model_alias_expansion` now expects sonnet for `haiku`).

## 2026-08-31 — /task --kind=god rejected; httpx log noise cut (EVALUATION_2026-08-30 F1/F7)

- `telegram_bot`: `/task --kind=god` now replies with an error pointing at
  `/god` instead of creating a break-glass job through the ungated door.
- `telegram_bot.main()`: httpx logger set to WARNING — the INFO
  getUpdates line every ~10s had grown `bot.err.log` to ~46MB with no
  rotation.

## 2026-08-17 — /api/telemetry/schedules + dashboard Schedules section

- New pure fold `schedule_rollup(schedules, jobs, window_days)` and thin
  endpoint `GET /api/telemetry/schedules`: one row per schedules-table row
  with terminal-run counts, success rate, consecutive-failure streak,
  last/avg durations, in-flight count, over a clamped window (default
  30d). Jobs join by `schedule_id` (the column the scheduler stamps),
  NEVER by kind, and with no NULL fallback — kinds are hand-dispatchable,
  so a kind-join would let a manual re-run-and-cancel reset a schedule's
  failing streak (code-review finding, fixed pre-merge). `in_flight`
  counts every non-terminal status including awaiting_user/deferred, so a
  run parked for days is visible instead of reading healthy-and-idle
  (second review finding). Column-select instead of full ORM rows so the
  60s dashboard poll doesn't drag payload/result JSON along (third).
  Semantics pinned by tests/test_schedule_telemetry.py (15 tests):
  in-flight runs are not evidence, cancels end a streak without counting
  as success, manual jobs are invisible to schedule stats, absent
  timestamps yield absent durations (never zero), no runs → success_rate
  null (not 0% or 100%). Failing streaks sort first, paused last.
- Dashboard gains a Schedules section (htmx, 60s refresh) rendering the
  rollup — observability item 4 of 4 (atlas ledger E-0027 context).

## 2026-08-11 — CreateJobRequest.session_timeout_seconds (optional)

`POST /api/jobs` accepts `session_timeout_seconds` (60..5400) → forwarded in
job payload; the runner clamps identically (`main.resolve_session_timeout`).
Motivated by momo-cycle timeouts — see runner CHANGELOG same date.

## 2026-08-07 — register opus-5 in _MODEL_ALIASES (atlas loop de-fabled)

**Files changed**: `src/gateway/telegram_bot.py`.

**Why**: owner decision — the atlas loop's fable-5 slots (atlas-evaluate
primary+escalation, atlas-build/atlas-gap-scout escalations) drew from the
credit balance rather than the plan's included allotment; all swapped to
`claude-opus-5` (smoke-tested `claude -p --model claude-opus-5` PASS on
subscription auth 2026-08-07). VALID_MODELS derives from this map's values,
so the new SKILL.md model id must be registered or the deploy pytest gate
fails (2026-08-06 lesson). Explicit versioned alias `opus-5` only — bare
`opus` stays pinned to 4-7 (5 flag-parser tests pin it).

**Verify**: full pytest suite green incl. `test_skill_contracts.py`;
`_MODEL_ALIASES["opus-5"] == "claude-opus-5"`.

## 2026-08-06 — register opus-4-8 + fable-5 in _MODEL_ALIASES; review_flagged notify branch

**Files changed**: `src/gateway/telegram_bot.py`.

- `_MODEL_ALIASES` gained `opus-4-8→claude-opus-4-8` and `fable`/`fable-5→
  claude-fable-5`. The skill-contract test derives its allowlist as
  `VALID_MODELS = set(_MODEL_ALIASES.values())`, so a SKILL.md referencing a
  model absent here fails `test_skill_contracts.py` — and the atlas-loop
  skills (atlas-build/evaluate/gap-scout/refresh-knowledge) now use these
  newer models. **This was caught by the prod deploy's pytest gate, not
  dev** (a `pytest … | tail` misread hid the 7 failures locally — read the
  FULL summary line for gate-sensitive runs). Bare-name defaults
  (`opus`→4-7 etc.) left unchanged — moving `opus`→4-8 broke 5 flag-parser
  tests that pin the default, so newer models are explicit versioned
  aliases only.
- (Committed with 74be877) new `review_flagged` branch in the tasks:notify
  consumer — surfaces a post-session code-review blocker in-thread (⚠️)
  since post_review now actually fires.

## 2026-07-30 — /health: parse the epoch runner heartbeat (status semantics unchanged)

**Files changed**: `src/gateway/web.py` — new pure helper
`parse_heartbeat_age(raw, now)` replaces the inline ISO parsing in `health()`.
The runner now writes `heartbeat:runner` as epoch seconds with a 15-min TTL
(see runner CHANGELOG same date); the helper reads epoch first and falls back
to ISO-8601 so the mixed-version deploy window (new web + old runner, or the
reverse) never misreports a live runner as dead.

**Unchanged on purpose**: the JSON body still reports
`runner_heartbeat_age_s` (null when the key is missing/unparseable) under the
same field name, and the **HTTP status semantics are untouched** — 200 only
when the runner heartbeat is fresh AND DB + Redis are reachable, else 503.
The external `ops/heartbeat-worker` dead-man's-switch (config commit 5de688c,
2026-07-28; worker wrangler-deployed/activated 2026-07-30) alerts on exactly
that non-200, so flattening /health to always-200 would re-create the
invisible-runner-down incident.

**Tests**: `tests/test_health.py::TestParseHeartbeatAge` (7) alongside the
existing verdict tests.

## 2026-07-28 — test-only: stop leaking synthetic self-diagnose rows into prod DB

**Files changed**: `tests/test_telegram_commands.py` — mock `enqueue_job` in
`TestErrorSafeDecorator::test_exception_retries_then_replies` so the
Level-3 branch of `_error_safe` no longer inserts a real
`self-diagnose` row (with description "Telegram handler 'handler' failed
twice. Error: boom") into the production `jobs` table on every test run.

**Why**: five zombie self-diagnose sessions had spawned from the test
suite over ~30 minutes; each burned a real Claude agent investigating a
fake failure. Root cause was the test exercising the real decorator
against real `enqueue_job`. Test now `patch()`es the callable and
asserts it was awaited once with `kind="self-diagnose"`.

**Side effects**: none for production code. `docs/Troubleshooting.md`
"self-diagnose fires for Telegram handler with error 'boom'" section
updated with the corrected root cause (previous entry had misattributed
it to human-triggered synthetic payloads).

## 2026-07-27 — /api/projects surfaces the delivery contract (segregation Phase E)

**Files changed**: `src/gateway/web.py` — `_get_projects(include_delivery=)`;
the authenticated `/api/projects` now includes `topology`, `deployable`, and
`deploy_autonomy` read from each project's manifest (the public landing-page
endpoint stays minimal). Dashboard gains a "Delivery" column. Manifest remains
the source of truth — no DB columns added (avoids contract/DB drift).

**Why**: make each project's topology + deployability visible at a glance.
Part of `docs/superpowers/plans/2026-07-27-project-delivery-segregation.md`.

**Side effects**: `gateway.web` now depends on `runner.delivery` (declared in
SYSTEM.md module graph).

## 2026-07-12 — P2: NL-first ingestion + plan/eval notify types + DAG-aware cancel

**Files changed**:
- `src/gateway/telegram_bot.py` —
  - Bare messages (no /command, not a reply) are now first-class asks:
    `_handle_plain_text` + pure `triage_plain_text` (short questions → chat;
    everything else → task; router-matched text is always a task). Restores +
    upgrades the NL routing the legacy repo had.
  - Task creation factored into `_create_task_with_job` (used by /task and
    plain text) — task_id now set at enqueue time (no post-enqueue UPDATE race).
  - New notify types: `plan` (auto-approved, Cancel-gated), `plan_approval`
    (manual mode: Approve/Cancel), `completed` (evaluator-verified auto-close
    with evidence + Reopen + rating buttons).
  - New button actions: `approve_plan` (spawns the stored plan's DAG),
    `reopen` (overrule the evaluator). `cancel` now also cancels queued AND
    deferred sibling jobs so a cancelled plan can't keep spawning.
  - /help rewritten around "just text me".
- `src/gateway/jobs.py` — `enqueue_job` accepts `task_id` / `parent_job_id`
  at creation.

**Why**: the mission's "single Telegram ask" flow required a /task prefix and
had no decompose→execute→verify pipeline behind it.

**How to verify**: text the bot "update the bingo app to show a version
footer" with no command — expect an "On it..." thread; multi-step asks show a
plan card first; completion arrives as "completed and verified" with evidence.

## 2026-07-06 — Meaningful /health for external dead-man's-switch

**Files changed**:
- `src/gateway/web.py` — `/health` now reads the runner heartbeat + queue depth from
  Redis and pings Postgres; returns **503** (not 200) when the runner heartbeat is
  stale or DB/Redis is unreachable, with a JSON body `{status, runner_ok,
  runner_heartbeat_age_s, queue_depth, db_ok, redis_ok}`. Extracted pure helper
  `health_verdict()`.
- `tests/test_health.py` (new) — 6 pure-function tests for the verdict.

**Why**: Part of the external heartbeat monitor (A3). All in-process alerters go
silent if the runner dies, so `/health` had to actually reflect runner liveness for
an off-box Worker (`ops/heartbeat-worker/`) to detect outages. Previously `/health`
always returned `{"status":"ok"}` regardless of runner state.

**Depends on**: runner writes `heartbeat:runner` each loop (see runner CHANGELOG);
`KEY_RUNNER_HEARTBEAT` constant + `runner_heartbeat_stale_seconds` setting.

**How to verify**: `curl -s localhost:8080/health | jq` → 200 with a small
`runner_heartbeat_age_s` while the runner is up; `launchctl stop com.assistant.runner`
→ 503 within ~90s.

## 2026-04-20 — Telegram interface redesign: threads + inline buttons

**Files changed**: `src/gateway/telegram_bot.py` (major rewrite)

**What changed**:
- Added `_error_safe` decorator with 4-level error handling (reply → retry → self-diagnose → graceful degrade)
- `/task` now creates a Telegram reply chain (thread) and stores `thread_message_id` on the Task row
- Thread replies (plain text) auto-route as task continuations via `_handle_thread_reply` MessageHandler
- Inline keyboard buttons replace slash commands for: Approve, Cancel, Send Feedback, View Details, Rate 1–5, structured choices
- `_handle_button` CallbackQueryHandler parses `action:task_prefix[:extra]` callback data
- `_task_notifier` rewritten to reply in threads with buttons (approval_request, question, choices)
- `/help` rewritten to show 4 primary commands; `/status` updated with thread context hints
- Removed dead code: `cmd_cancel`, `cmd_rate`, `cmd_proposals`, `cmd_reply`, `cmd_approve`, `cmd_tasks`
- `_parse_callback` helper added for callback data parsing

**Why**: Replace 16 slash commands with conversational thread-based interaction.

## 2026-04-20 — Fix task notifications: remove parse_mode for AI content

**Files changed**: `src/gateway/telegram_bot.py` — `_task_notifier` now sends
AI-generated content (summaries, plans) without `parse_mode="Markdown"`.
Prevents 400 Bad Request from Telegram when content has unmatched markdown.

**Why**: Implementation plans with `##`, `**`, backticks crashed the notification.

## 2026-04-20 — Add /clear admin command

**Files changed**: `src/gateway/telegram_bot.py` — New `cmd_clear` handler.
Cancels all queued/running jobs, fails all active/awaiting/pending tasks,
flushes the Redis queue.

**Why**: Users needed a way to bulk-cancel everything without raw SQL.

## 2026-04-20 — Diagnose: cmd_jobs crashes on `_writeback` skill name

**Files changed**: none (diagnosis only — server code edit requires `server-patch` / manual apply).

**Root cause**: `cmd_jobs` (`src/gateway/telegram_bot.py:810`) interpolates
`skill = j.resolved_skill or j.kind` into a Markdown message without passing it
through `_esc_md()`. When the skill name begins with `_` (e.g. `_writeback`), the
leading underscore opens an italic entity that never closes, and the Telegram API
returns `400 Bad Request: can't find end of the entity starting at byte offset N`.

**Proposed fix**: wrap the assignment in `_esc_md(...)`, and audit sibling
renderers (`cmd_status`, `cmd_tasks`, callback handlers) for the same pattern.
See `docs/Troubleshooting.md` → "Telegram handler crashes with 'Can't parse entities'".

**Risk**: medium (server code). Not auto-applied; Phase 5 `server-patch` or manual edit required.

## 2026-04-20 — Thread-based Telegram interface with inline buttons

**Files changed**:
- `src/gateway/telegram_bot.py` — Rewrote interface from 16 slash commands to
  thread-based with inline buttons. `/task` creates reply thread with [Cancel]
  button. Plain text replies in threads auto-route as task continuations.
  Inline buttons handle approve/cancel/rate/feedback/details/choices.
  `_task_notifier` posts in threads + sends summary DM. `/help` shows 4
  commands. `/status` shows active tasks. Removed old slash commands
  (reply, approve, tasks, cancel, rate, proposals). `@_error_safe` applied
  to all handlers.
- `tests/test_telegram_commands.py` — Added `TestParseCallback` (3 tests).

**Why**: 16 slash commands created cognitive overhead. Thread-based approach
is more natural: start a task, reply in the thread to continue, tap buttons
for actions. Users no longer need to remember task IDs or command syntax.

**Side effects**: Old `/reply`, `/approve`, `/tasks`, `/cancel`, `/rate`,
`/proposals` commands removed. Functionality preserved via inline buttons
and thread replies.

## 2026-04-20 — Add _error_safe decorator for Telegram handlers

**Files changed**: `src/gateway/telegram_bot.py`

**Why**: Handlers crashed silently. Now: retry once, self-diagnose, graceful degradation.

## 2026-04-20 — Pin response options to /tasks and /jobs output

**Files changed**: `src/gateway/telegram_bot.py` — Each task and job in
the list output now shows its available actions inline based on status.
Cross-links between `/tasks` and `/jobs` at the bottom of each listing.

**Why**: Users had to remember which commands to run after seeing a listing.
Now the next action is right there.

## 2026-04-20 — Fix Markdown escaping in /tasks, /jobs + add command tests

**Files changed**:
- `src/gateway/telegram_bot.py` — Added `_esc_md()` helper to escape
  Telegram Markdown special chars in user-supplied text. Applied to
  description fields in `/tasks` and `/jobs` output. Fixed silent crash
  when descriptions contained underscores/backticks.
- `tests/test_telegram_commands.py` (NEW) — 13 tests for `_esc_md()` and
  `parse_flags()` regression.

**Why**: `/tasks` crashed with `BadRequest: can't find end of entity` when
task descriptions contained Markdown-breaking characters.

## 2026-04-20 — Added /jobs command

**Files changed**: `src/gateway/telegram_bot.py` — New `cmd_jobs` handler.
Shows recent jobs with status icon, skill, description, and linked task ID.
Usage: `/jobs` (default 10) or `/jobs 25` (max 25).

**Why**: Users couldn't see what jobs are running or recently completed
without using `/status` on individual job IDs.

## 2026-04-20 — Fix /approve handler broken query

**Files changed**: `src/gateway/telegram_bot.py` — Removed broken nested
`select(select(...))` in `cmd_approve` that crashed before the status update.

**Why**: `/approve` silently failed — task stayed in `pending_approval`.

## 2026-04-20 — Multi-turn task commands + API endpoints

**Files changed**:
- `src/gateway/telegram_bot.py` — New commands: `/reply` (respond to task),
  `/approve` (mark task complete), `/tasks` (list active tasks). Modified
  `/task` to create a Task + first turn before enqueueing the job. Added
  `_task_notifier` listener for `tasks:notify` Redis channel (DMs questions
  and approval requests). Updated `/help` text.
- `src/gateway/web.py` — New endpoints: `GET /api/tasks` (list with status
  filter), `GET /api/tasks/{id}` (task + turns).

**Why**: Users couldn't respond to task output or approve completion.
New commands close the interaction loop.

**Side effects**: `/task` now creates a Task row + TaskTurn in addition
to the Job. `chat_id` persisted on Task (fixes lost DM mapping on bot restart).

## 2026-04-20 — Documentation cleanup: updated CONTEXT.md

**Files changed**:
- `.context/modules/gateway/CONTEXT.md` — Updated public interface to include
  `/api/retrospective/context`, `/api/jobs/{id}/stream`, `/api/projects/public`
  routes. Added `/proposals` and `/schedule` to Telegram commands list.
  Removed stale Phase 2 references from Testing and Gotchas sections.

**Why**: CONTEXT.md was out of date — missing routes and commands added
in Phases 5-6 and evaluation recs.

**Side effects**: None.

## 2026-04-19 — Added GET /api/retrospective/context route (Rec 2)

**Files changed**:
- `src/gateway/web.py` — New `GET /api/retrospective/context?since=YYYY-MM-DD`
  route returning JSON array of context consumption data per (skill, file_path).
  Computes `read_rate` from `read_count / total_skill_jobs`. Auth-gated.

**Why**: Exposes the context consumption rollup (Rec 2) to the dashboard
and to skills like review-and-improve that consume it via HTTP.

**Side effects**: None; additive route only.

## 2026-04-18 — Added /proposals Telegram command (Rec 10)

**Files changed**:
- `src/gateway/telegram_bot.py` — new `cmd_proposals` handler with three
  modes: no-arg lists pending; `Nd` (e.g. `/proposals 30d`) lists all
  proposals from last N days; `<id_prefix>` shows details for one proposal.
  Registered via `CommandHandler("proposals", cmd_proposals)`. Added to
  `/help` text and module docstring command list.

**Why**: Users need visibility into what `review-and-improve` has proposed
and what's happened to those proposals. Per Rec 10, proposals are now
tracked in a DB table; the command is the Telegram-side window into it.

**Side effects**: None on existing commands. New command imports
`src.runner.proposals` lazily inside the handler so module load stays fast.

## 2026-04-18 — Seeded skills/ subdirectory per Rec 3 (§ 7 Seed module skills/ dirs)

**Change**: This module now has `.context/modules/gateway/skills/` containing stub `GOTCHAS.md`, `PATTERNS.md`, and `DEBUG.md` files. Stubs were created via `scripts/seed-module-skills.sh`; no source code modified.

**Why**: PROTOCOL.md directs sessions to append learnings to these files, but four of five modules had no skills/ directory at all, discouraging write-backs. Creating the directories with format-header stubs removes the friction and gives future sessions a template to append to. See `docs/EVALUATION_2026-04-18.md` § 7 Rec 3.

**Side effects**: None on module behavior. New lint check `check_module_skills_dirs` in `scripts/lint_docs.py` verifies these files continue to exist.


## 2026-04-17 — Public landing page + projects API

**Files changed**:
- `src/gateway/web.py` — Added `/api/projects/public` (no-auth endpoint returning project list for the landing page). Extracted shared `_get_projects()` helper used by both the auth'd and public endpoints.

**Why**: The public landing page at `chrispiserchia.com` needs to fetch project data without an auth token.

## 2026-04-16 — Initial bootstrap (Phase 1)

**Agent task**: Create the three gateway processes from scratch.

**Files created**:
- `src/gateway/jobs.py` — shared enqueue/cancel/find helpers
- `src/gateway/web.py` — FastAPI with 8 routes + HTMX dashboard
- `src/gateway/telegram_bot.py` — 9-command bot + done-listener + quota notifier

**Why**: Three submission pathways (Telegram, web form, programmatic API) with
one consistent backend.

**Side effects**: None — new module.

**Gotchas discovered**:
- Telegram's `Update` type collides with SQLAlchemy's `update` function. Import
  the latter as `sql_update` in telegram_bot.py.
- `_job_to_chat` dict is in-process; on bot restart any pending jobs lose their
  DM destination. Acceptable for now; users can `/status` to check.
- Dashboard renders JSON responses client-side for simplicity. Works but is ugly
  on slow connections; consider server-side rendering in Phase 2.
