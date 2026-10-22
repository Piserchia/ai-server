# Changelog: notify

<!-- Newest entries at top. Every session that modifies this module appends here. -->

## 2026-10-21 — A7 (docs only): the launchd alerters are the first `python -m src.notify send` callers

**Agent task**: Observability Phase 1 re-cut plan A7 (`docs/superpowers/plans/2026-10-21-observability-phase1-recut.md` §6).
**Files changed**:
- `.context/modules/notify/CONTEXT.md` — the switch paragraph states the A6 default (True) and that the alerter scripts never read it; names the two callers of `send` and their curl fallback. No change to `src/notify/`.

**Why**: `__main__.py`'s docstring already described the `send` contract for bash callers (exit 0 only when delivered); the callers now exist (`scripts/healthcheck-all.sh` `notify_send`, `scripts/schedule-monitor.sh` `send_dm`), recorded in the hosting CHANGELOG.

**Side effects**: none.

**Gotchas discovered**: none.

## 2026-10-21 — A4: module created — outbox rows, Telegram renderer with limits, `python -m src.notify send|drain`

**Agent task**: Observability Phase 1 re-cut plan A4 (`docs/superpowers/plans/2026-10-21-observability-phase1-recut.md` §6; design of record P0 plan Task 5, deltas 1–6 applied).
**Files changed**:
- `src/notify/__init__.py` (new) — re-exports only.
- `src/notify/outbox.py` (new) — `Notice`, the kind vocabulary (`NOTICE_KINDS` = job ∪ task ∪ `OPS_NOTICE_KINDS`), `STATUSES`, `MAX_ATTEMPTS`, `SENDING_LEASE_SECONDS`, `COMPLETION_DM_CHANNELS = (telegram, web, cli)`; pure `should_notify_job`, `lane_label` (the one definition), `build_job_notice` (+ `resolved_provider`/`resolved_model`, plain-text lane header, `[Details]` → `jd:<job8>`), `build_task_notice` (no `rate:` row), `build_ops_notice`, retry math; async `enqueue_notice` (always inserts — never reads the switch), `record_notice`, `pending_notices`, `claim_notice`, `release_stuck_sending`, `mark_sent`, `mark_failed`, `mark_skipped`.
- `src/notify/telegram.py` (new) — `TelegramMessage`, `render_telegram` (4096 / 64-byte / 8-button limits, no `parse_mode`), `fit_text`, `validate_callback`, `build_buttons`, `keyboard_markup` (lazy import), `send_via_bot`, `send_via_http` (+ `transport=` test seam), `TelegramSendError` (the token chokepoint — never `raise_for_status()`).
- `src/notify/__main__.py` (new) — `send` (direct HTTP, then `record_notice(status=sent|failed)`; exit 0 only when delivered) and `drain` (claim → render → send → stamp; mirrors the bot's `legacy_mode` by marking job/task rows `skipped` when `NOTIFY_OUTBOX=0`); `_redact` on everything recorded or printed.
- `tests/test_notify_outbox.py`, `tests/test_notify_telegram.py` (new).

**Why**: spec §3/§9 — one durable outbox with delivery history replaces the in-process `_job_to_chat` dict and the unschema'd `tasks:notify` vocabulary as the record of what the owner was told; a bot restart loses nothing; out-of-band alerters get a shared, token-safe sender.

**Side effects**: none until A5 wires the runner producers and A6 the bot listener. `settings.notify_outbox` ships False (A6 flips it). `src/gateway/jobs.ORIGIN_CHANNELS` gains a consumer (`outbox.COMPLETION_DM_CHANNELS` asserts it is a subset at import).

**Gotchas discovered**: (1) `src/notify/telegram.py` shadows the third-party `telegram` package if `src/notify/` is ever on `sys.path` — keep the `from telegram import …` lazy inside `keyboard_markup`. (2) httpx exception messages embed the request URL, i.e. the bot token: `send_via_http` catches everything and re-raises `TelegramSendError` with the API `description` or the bare exception type name only; `__main__` redacts a second time. (3) A manual `drain` with the switch off must not send job/task rows — the legacy listeners already do — so it marks them `skipped`, exactly like A6's `legacy_mode`.
