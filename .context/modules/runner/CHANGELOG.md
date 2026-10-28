# Changelog: runner

<!-- Newest entries at top. Every session that modifies this module appends here. -->

## 2026-10-28 — pricing: the request is the cost basis when `model_served` names another family (+ the 39-row recompute)

**Agent task**: owner instruction "fix the 39 rows and re-run the baseline", following the `model_served` defect in the entry below.
**Files changed**:
- `src/runner/pricing.py` — `job_cost_from_events` prices `job_started.model` when `model_served` resolves to a DIFFERENT family, records it on `JobCost.served_mismatch`, counts it in `LedgerReport.served_mismatches` (also in `to_dict`) and prints a note in `render_sdk_reconcile`. A request with no resolvable family (a bare alias like `sonnet`, or an unknown id) still prices from the served id — that case is the reason the field is read at all, and the first version of this change regressed it.
- `tests/test_pricing.py::TestServedModelMismatch` (5 cases: different family priced at the request, same-family dated snapshot still preferred, served-with-no-request, the bare-alias refinement, and the count rendered rather than silent).

**Why**: the audit JSONL is append-only and still carries the wrong `model_served` on 39 jobs, so correcting the DB rows alone would have left every JSONL-derived report mispriced. Evidence for the request as the basis: those rows price to $122.66 at the request against the SDK's $121.89 (+0.6 %), versus $24.84 at the recorded served id.

**Side effects**: a genuine substitution is now reported rather than silently priced at the served rate — intended, and the note persists for ~30 days while the affected JSONL stays in the window. **Prod data corrected in the same pass** (one-off, dry-run first): 39 rows got `model_served = NULL` and a recomputed `cost_usd_list`; `rows still matching the bug: 0`. Re-run baseline: 30 d ≈ $1,802.07 (789 jobs), 7 d ≈ $231.68 (137). The earlier "the CLI prices cache writes at the 5-minute rate" conclusion is **withdrawn** — post-fix the divergence is family-dependent (opus-5 −2.4 %, opus-4-8 −3.2 %, opus-4-7 −17.9 %, sonnet-4-6 −23.4 %) and the implied rates straddle both rates.

**Gotchas discovered**: `ResultMessage.usage` is a per-session aggregate across every model the session touched, while the ledger prices it as one model — so any multi-model session is mispriced by construction. That is the standing limitation behind the residual divergence, and the `model_served` bug was its extreme case.

## 2026-10-28 — `model_served` names the model that did the work (Opus sessions were stamped and priced as Haiku)

**Agent task**: Observability Phase 1 §8 verification, first full week of stamped jobs.
**Files changed**:
- `src/runner/result_capture.py` — new `dominant_model(model_usage)`; `ResultCapture.model_served` uses it instead of `next(iter(model_usage))`. The bundled CLI makes its own small-model calls inside a session, so `model_usage` carries a second, tiny entry — `claude-haiku-4-5-20251001` on prod — and it is often FIRST in the dict. Degenerate shapes (no countable tokens) still yield the first key, so `{"<model>": {}}` captures are unchanged.
- `tests/test_result_capture.py::TestDominantModel` (5 cases, incl. a genuinely haiku-dominated session still reporting haiku).

**Why**: measured on prod 2026-10-22..28 — `model_served` was `claude-haiku-4-5-20251001` on **39 of 111** completed jobs whose `resolved_model` was opus-5 (28), sonnet-4-6 (9) or opus-4-8 (2). Because `pricing.price_usage` keys on `model_served`, those jobs' `cost_usd_list` was computed at Haiku rates: $24.84 against the SDK's $121.89 for the same 39 jobs (+390.7 %, implied cache-write rate $25.60 — the giveaway that the pairing was wrong, not the rate). `served_model_violation` did not fire and could not: it checks that the requested model is PRESENT among the keys, which it was.

**Side effects**: new jobs stamp the right id and price correctly. **Rows already written stay wrong** — `jobs.model_served` and `jobs.cost_usd_list` on those 39 rows, and the §8 30-day baseline (≈ $2,101.63) that was computed from the same `job_completed.model_served` values in the append-only JSONL. Recompute is a one-off over `jobs` (see the handoff doc); it is a prod data write and is left for the owner.

**Gotchas discovered**: `model_usage` is `dict[str, Any]` in the pinned SDK with no declared value shape; counters appear camelCase (`inputTokens`) from the CLI, and `costUSD`/`contextWindow` sit in the same dict.

## 2026-10-22 — cost-reconcile: the computed-vs-SDK comparison is paired

**Agent task**: Observability Phase 1 §8 measurement (first prod `scripts/cost-reconcile.py --db` run after B3 stamped the first job).
**Files changed**:
- `src/runner/pricing.py` — `ModelRow` tracks the paired subset (tokens + computed $ of the jobs that carry `sdk_cost_usd`); `implied_cache_write_rate` and `render_sdk_reconcile` compare over that subset and print `(n)`. The window total `usd` is unchanged. First prod run compared one stamped opus-4-7 job's SDK figure with the computed sum of all twelve in the window (−96.9 %, implied rate −6.63).
- `tests/test_pricing.py::test_reconcile_pairs_only_jobs_with_an_sdk_figure`.

**Why**: the exit criterion ("within 1 %, or record the rate the CLI uses") is only meaningful like for like. Measured on the first stamped job (bfc449b5, opus-4-7): computed $0.6470 at the 1-h cache-write rate, SDK $0.4847 — exactly the same arithmetic with cache writes at the 5-minute rate ($6.25/M); the CLI prices cache writes at the 5-m rate.

**Side effects**: none at runtime (report only).

## 2026-10-22 — Post-deploy follow-ups: tests can no longer reach the live DB/Redis; weekly-allowance window filter

**Agent task**: Observability Phase 1 Tier A post-deploy verification (plan `docs/superpowers/plans/2026-10-21-observability-phase1-recut.md` §8).
**Files changed**:
- `tests/conftest.py` — before any `src` import, `POSTGRES_DSN`/`REDIS_URL` are pointed at a closed port (`127.0.0.1:1`) unless `AI_SERVER_RUN_DB_TESTS=1`: `pydantic-settings` reads `.env` from the CWD even under `PIPENV_DONT_LOAD_ENV=1`, the dev `.env` points at PRODUCTION, and the prod deploy gate runs with prod's `.env` exported. On 2026-10-22 03:40 local the deploy gate's pytest run drove the dual-write `_notify_task` from `tests/test_origin.py::test_level_3_escalation_fails_the_task_through_set_task_status` with only `src.db.redis` patched (main.py binds its own `redis` at import), inserted a real `notifications` row ("Last error: boom") on prod, and the new bot delivered it (Telegram message 940). The row was deleted by hand; `tests/test_no_live_services.py` pins the guard.
- `tests/test_origin.py` — that test now patches `runner_main.redis`, `enqueue_notice` and `_task_target`.
- `src/runner/pricing.py` — `weekly_allowance` keeps only the readings of the CURRENT fixed window (those sharing the newest `resets_at`); the first prod `cost-reconcile` run scored 09-25 readings against the 10-16 window opening and printed "allowance ≈ $0/week". `tests/test_pricing.py::test_readings_from_an_earlier_window_are_excluded`.

**Why**: a test with a side effect on production is a blocker-class defect regardless of how it passed; the guard makes the class impossible rather than fixing one instance.

**Side effects**: any test that silently relied on the live Postgres/Redis now fails with a connection error on `127.0.0.1:1` — exactly one did. The opt-in migration test is exempt (it needs the real DSN prefix for its throwaway database).

## 2026-10-22 — Whole-tier review applied: a recovered `api_retry` on a success is `ok`; anchored exception heuristics; no empty `choices` card

**Agent task**: whole-tier review of `observability/phase-1` (plan "Whole-tier review applied 2026-10-22").
**Files changed**:
- `src/runner/result_capture.py` — `derive_terminal_reason` consults `API_RETRY_TO_TERMINAL` only when the capture FAILED (`is_error`, an `api_error_status`, or `banner_terminal`) or the mapped reason is an enforcement category: the CLI emits `system/api_retry` before the retry's outcome is known, and on a subscription account under 529 load the retry usually succeeds — a success-shaped capture was being stamped `api_error` / `rate_limited` / `auth_expired` beside `status=completed`, which `outbox.lane_label` (` · api_error` on the DoneCard), the web badge and the `job_completed` audit row all surface. The `api_retry` audit row still records the recovered retry. `terminal_reason_for_exception`: the category match is anchored to the session's own raise shape (`\bapi_retry ([a-z_]+)`) and the generic auth heuristic is word-bounded (`\b401\b|\b403\b|\bexpired\b|unauthori[sz]ed`) and applies only to `session error …` text — a git `rate_limit` / `Authentication failed … 403` from workspace creation is `error`, not `rate_limited` / `auth_expired`.
- `src/runner/main.py` — `_notify_task`: a `choices` card with no options writes no outbox row (the legacy `_task_notifier` skips it: `elif notify_type == "choices" and choices`); the legacy publish is unchanged.
- `src/runner/pricing.py` — `price_usage` docstring: `usage` is the session total, a multi-model session is priced at one family.
- `tests/test_result_capture.py` (+6: `test_recovered_api_retry_on_a_success_is_ok` ×3, `test_enforcement_category_maps_even_on_a_success_shape` ×3, three anchored-heuristic exception cases), `tests/test_notify_runner_hooks.py::test_choices_without_options_writes_no_row`.
- `.context/modules/runner/CONTEXT.md` — D1 bullet: `_resolve_schedule_slug` (payload first) vs `session._project_slug` (`project_id` first) precedence note; B1 bullet: multi-model pricing note. This file: B2 gotcha (3) and the B3 `CancelledError` sentence corrected.
**Why**: review findings (one major — completed jobs flagged `api_error` on day one; three minors).
**Side effects**: `jobs.terminal_reason` for a completed Anthropic session that saw a recovered transient retry is now `ok` (was the mapped category); nothing else changes — `session._run_in_process` still raises on an enforcement category before `derive_terminal_reason` runs.
**Gotchas discovered**: the `ENFORCEMENT_CATEGORIES` exemption is what keeps `test_api_retry_category_outranks_the_http_status`-style guarantees independent of `is_error`; gate on `failed` alone and a success-shaped capture with `account_on_hold` would read `ok`.

## 2026-10-21 — D1: scheduler `provisioning_gap` pre-check — a due row whose project `.env` lacks a declared key is deferred (+ one DM per project per day), never run

**Agent task**: Observability Phase 1 re-cut plan D1 (`docs/superpowers/plans/2026-10-21-observability-phase1-recut.md` §6; design of record P0 plan Task 21, adapted by symbol with the D1 Deltas and D-P1-7/D-P1-10).
**Files changed**:
- `src/runner/main.py` — `PROVISIONING_EXEMPT` (the three INV-3 names) + `PROVISIONING_EXEMPT_PREFIXES = ("ANTHROPIC_",)` (a LOCAL set, deliberately not `codex_cli.DENIED_ENV_*`); pure `env_keys_present`, `provisioning_gap`, `schedule_env_required` (manifest ∪ `job_payload.env_required`); `_resolve_schedule_slug` (payload `project_slug` first, then `project_id → Project.slug` in the open session), `_project_env_files` (the canonical `resolve_delivery_cwd(..., is_deploy=False)` + `delivery.env_files or [".env"]` — the same file `provision_env_files` copies from), `_schedule_provisioning_gap` (per-slug cache within a tick; any exception → the row runs), `_notify_schedule_deferral` (ops notice `schedule_deferred`/warn, day claim `schedule:gap_notified:<slug>:<date>` SET NX 36 h taken only after the insert returned an id); the pre-check in `_tick_schedules` before `Job(...)` — once `missing` is non-empty the deferral is unconditional (clock advanced, no Job, no RPUSH), audit + DM each best-effort.
- `src/runner/schedule_adherence.py` — pure `latest_deferral(events)`, `deferral_covers_slot(deferred_at, last_slot)`, `is_deferred(cron, deferred_at, now)`; `adherence_report` gives a row whose newest deferral covers its latest slot status `deferred` (sorted with `paused`, row carries `missing`) + a `DEFERRED` finding instead of DARK; `_collect` reads each schedule's stream; the `OK …` line counts deferred rows.
- `tests/test_provisioning_gap.py` (new: `TestEnvKeys`, `TestGap`, `TestSchedulerIntegration`, `TestStatusLine`), `tests/test_schedule_adherence.py` (`TestDeferred`).
- `.context/modules/runner/CONTEXT.md` (D1 bullet, scheduler loop line, adherence bullet), `.context/SYSTEM.md` (`main.py` Depends-on += `registry.manifest`; `schedule-monitor.sh` row), `docs/TROUBLESHOOTING.md` (symptom "schedule deferred (provisioning_gap)"), `.context/INDEX.md` (row).
**Why**: spec §8.3 / §9 — a schedule missing its provisioning ran a full session and reported `completed` having produced nothing (spec §8.2: 37/37 such runs "successful"). Deferring costs one audit line and one DM a day instead of a session; the swing rows (D-P1-7) are the first governed rows it protects.
**Side effects**: after deploy + `bash scripts/seed-schedules.sh`, the four swing supervise/trade rows defer at their next slot (the atlas canonical `.env` lacks `TRADIER_SANDBOX_TOKEN`) with one DM naming `~/Documents/repos/atlas/.env`; `/status` lists them; Sunday shows `DEFERRED`. Every other row is unaffected: today's manifests declare nothing their `.env` lacks except atlas's `ANTHROPIC_API_KEY`, which is exempt. New Redis key prefix `schedule:gap_notified:` (36 h TTL). New audit kind `schedule_deferred` in a NEW stream location `volumes/audit_log/schedules/<schedule_id>.jsonl`.
**Gotchas discovered**: (1) the exemption is load-bearing, not decoration — `projects/atlas/manifest.yml` declares `env_required: [DATABASE_URL, ANTHROPIC_API_KEY]` and the atlas `.env` lacks the second BY DESIGN; without `PROVISIONING_EXEMPT` every atlas row would defer on the first tick. (2) The `.env` to check is NOT `projects/<slug>/.env` for dev-repo projects: `provision_env_files` copies from the canonical dev clone, and a complete runtime-clone `.env` would mask a gap in the one the session actually gets (`test_checks_the_canonical_dev_repo_not_the_runtime_clone`). (3) `Job.id` is a column default applied at flush — the fake session in the tests assigns it in `add` so `redis.rpush(str(job.id))` is meaningful. (4) `Schedule.job_payload` is JSON that older rows may hold as a non-dict; the helpers treat anything but a dict as empty.

## 2026-10-21 — B4 (docs + consumer): `scripts/cost-reconcile.py` is `pricing`'s ledger consumer

**Agent task**: Observability Phase 1 re-cut plan B4 (`docs/superpowers/plans/2026-10-21-observability-phase1-recut.md` §6). No `src/runner/` code change — the script and its timer are recorded in the hosting CHANGELOG.
**Files changed**: `.context/modules/runner/CONTEXT.md` — the B1 pricing bullet's "ledger side for B4" now names its consumer (`scripts/cost-reconcile.py`: both windows, the per-kind step, `render_sdk_reconcile`, `render_weekly_allowance`, the `--db` leg through `render_db_delta`, the seed through `write_lane_seed`/`lane_seed`) and the DB leg's grouping key (`COALESCE(model_served, resolved_model)` — the same precedence `job_cost_from_events` uses).
**Why**: the Phase-1 exit criterion (computed vs SDK within 1 %, or the divergence recorded with the implied cache-write rate) is measured by that script's first prod run; the module's docs should say who calls what.
**Side effects**: none at runtime.
**Gotchas discovered**: none.

## 2026-10-21 — B3: capture + pricing wired into `session.py` / `main.py` (both lanes); typed `terminal_reason`; silent-empty-success rejection

**Agent task**: Observability Phase 1 re-cut plan B3 (`docs/superpowers/plans/2026-10-21-observability-phase1-recut.md` §6; design of record P0 plan Task 3 "3a", adapted by symbol with the seven B3 Deltas).
**Files changed**:
- `src/runner/session.py` — `SystemMessage` joins the SDK import; `from src.runner import pricing` + the `result_capture` names. New `cli_version()` (`lru_cache`; reads `claude_agent_sdk._cli_version.__cli_version__` = `2.1.139` on the pinned wheel, `unknown` if absent, ≤ 24 chars; no subprocess — pinned). `_run_in_process` returns `(text, usage, ResultCapture)`: the last `system/api_retry` `error` category is collected at the HEAD of the message loop (before the `RateLimitEvent` branch, which can `continue`/raise) and audited as `api_retry{error, attempt}` (category + attempt only, never the message text); the `ResultMessage` branch is `capture_result_message(message, api_retry_error=)`; the errored-empty-session `RuntimeError` carries the category (`session error (<subtype>; api_retry <cat>): …`); after the `is_api_terminal_session` banner belt (kept) it raises on an enforcement category (`vendor enforcement — no retry`) and, when `served_model_violation(...)` returns a reason, audits `job_result_rejected{reason="unrecognized_model", detail, requested_model}` and raises `unrecognized_model: silent empty success — …`. The three `QuotaExhausted` raises keep A3's `source=`. `_run_executor` returns `(text, usage, model_served, cli_version)` — `ExecResult.cli_version` is no longer dropped. `run_session`: the Anthropic branch sets `model_served = capture.model_served`, `terminal_reason = derive_terminal_reason(capture)` (replacing the literal `"ok"`), `cost_usd_list = pricing.price_usage(capture.model_served or model_used, usage)` and `columns = result_columns(..., cli_version=cli_version())`; the executor branch keeps `"ok"`/`ExecutorFailed`, `columns = usage_columns(usage) + cli_version (the Codex CLI's) + cost_usd_list` (`price_usage` → None for a non-Anthropic id; `num_turns`/`duration_api_ms`/`sdk_cost_usd` stay NULL — no source on that lane). Both lanes stamp the row at ONE `sql_update` site after the lane branch, before `job_completed`. `job_completed` gains `num_turns, duration_api_ms, cost_usd_list, sdk_cost_usd, stop_reason` (keeping `provider`; the C14 fields byte-identical); the result dict gains `num_turns`, `cost_usd_list` (float/None — it is `jobs.result`).
- `src/runner/main.py` — imports `terminal_reason_for_exception`, `usage_columns`; `_terminal_values` / `_finish_job` accept `usage=` (→ the five token columns through `usage_columns`), `num_turns=`, `cost_usd_list=` (→ `Decimal(str(x))` for `numeric(10,4)`), written only when known; the completed path passes `result.get("usage"/"num_turns"/"cost_usd_list")`. The generic `except Exception` handler stamps `reason = terminal_reason_for_exception(exc)` on the `job_failed` audit line and on BOTH lanes' `_finish_job` (A2's interim `"api_error"` is gone).
- `src/gateway/web.py` — see the gateway CHANGELOG (`JobOut`/`_serialize` + the Cost · Turns column).
- `src/audit_log.py` — docstring: `job_completed`'s five new fields; new kinds `api_retry`, `job_result_rejected`.
- `tests/test_result_capture.py` (append: `TestSessionWiring` 14, `TestMainWiring` 3), `tests/test_web.py` (`test_jobout_carries_token_and_cost_columns`), `tests/test_job_visibility.py` (`test_job_completed_carries_cost_and_turns`); `tests/test_provider_dispatch.py` (the `_run_in_process` fake → 3-tuple with a capture whose `model_usage` names `claude-sonnet-4-6`; the Anthropic `job_completed`/result asserts read the captured `model_served`; `_FakeDB.params` is the resolved_* stamp (`statements[0]`), `column_params` the post-session stamp; the T4 lane pin `RuntimeError("clone exploded") → "api_error"` → `"error"`), `tests/test_pre_push_gate.py` (fake → 3-tuple), `tests/test_origin.py` (A2's cancelled-guard pin `RuntimeError("boom") → "api_error"` → `"error"`).
- `.context/modules/runner/CONTEXT.md` (B3 bullet; `run_session` result dict; `_finish_job` kwargs; B1/B2 "no caller until B3" closed), `.context/SYSTEM.md` (Depends-on: `session.py` += `runner.pricing`, `main.py` += `runner.result_capture`; the `(B3)` forward markers dropped).

**Why**: spec §9's Phase-1 exit criterion — every completed job has tokens / cost / turns / API time / CLI version in Postgres, on both lanes, with `cost_usd_list` computed by the ONE definition (`pricing.price_usage`) and the SDK's figure kept beside it so B4's reconcile can compare them; the typed `terminal_reason` (B2) replaces the literal `"ok"` and A2's interim `"api_error"`; the silent-empty-success shape (an unknown model id answered with a text-less, usage-less "success") fails as `unrecognized_model` so escalation engages instead of a completed no-op.

**Decisions recorded here (plan §3)**: **D-P1-2** — an SDK `error_max_turns` (or `stop_reason=max_turns`) with partial text completes: `status=completed`, `terminal_reason=max_turns`, no escalation (done-ness is a column; the text produced is real work; the owner may choose fail + escalate instead). **D-P1-5** — `DeployRefused`, `DeployNeedsApproval`, `SkillResolutionError` and preflight failures stamp `terminal_reason="error"`: a **deviation from spec §2.4**, which calls `DeployRefused` a `provider_refused{reason}` — the tree reserves `provider_refused` for `models_registry.ProviderRefused` (pinned by `tests/test_models_registry.py` and `tests/test_provider_dispatch.py`). Enforcement categories (`account_on_hold`, `oauth_revoked`, `billing_error`) only map to `terminal_reason` in Phase 1; the lane hold, the `provider_enforcement` notice and the ApprovalCard are Phase 3 — A5's failed-job DM is the Phase-1 signal (the kind name is already reserved in `NOTICE_KINDS`). `audit_index.categorize_error` keeps its own vocabulary; consumers read `terminal_reason` first, `error_category` as the fallback.

**Side effects**: an Anthropic session whose `ResultMessage` is fully empty (no text, zero usage, zero API time) or whose `model_usage` does not contain the requested family now FAILS with `unrecognized_model` and engages escalation — previously recorded `completed`; all-zero usage WITH text remains a success. A session that saw a `system/api_retry` with an enforcement category fails with that category even if a later retry produced text (P0 design: never escalate onto a suspended account). A bare infrastructure `RuntimeError` in the generic handler is now `terminal_reason="error"` on both lanes (was the blanket `api_error`); `QuotaExhausted` `rate_limited`; the `CancelledError → interrupted` arm of `terminal_reason_for_exception` has NO caller today (`_process_job`'s generic branch catches `Exception`; cancellation is the `/cancel` path's `cancelled` stamp) — mapped, not stamped. `run_session` issues one extra `UPDATE jobs` per job (the column stamp); `_finish_job(completed)` re-writes the token/cost subset with the same values. Every existing monkeypatch of `_run_in_process`/`_finish_job` keeps working (the fakes were widened, the kwargs are optional).

**Gotchas discovered**: (1) `run_session`'s second UPDATE means a test's "last captured statement" is the column stamp, not the `resolved_*` stamp — `_FakeDB.params` in `tests/test_provider_dispatch.py` now reads `statements[0]`. (2) Driving the real `_run_in_process` with a fake SDK client reaches `_handle_message → _publish_stream` on `session`'s own `redis` binding; without `monkeypatch.setattr(session, "redis", fake_redis)` the real client's pool binds to that test's event loop and a LATER redis-using test fails with "attached to a different loop" — order-dependent and invisible in a single-file run. (3) `ast.unparse` renders string constants with single quotes; source pins must accept either quote. (4) The review-blocked Codex path raises inside the lane branch (the gate runs before the one-site stamp), so a `review_blocked` job keeps `cli_version`/tokens NULL — a follow-up if the ledger wants them. (5) `jobs.result` is JSON: the result dict carries `cost_usd_list` as a float; the Decimal lives only in the column stamp and `_terminal_values`.

## 2026-10-21 — B2: `result_capture.py` — typed `ResultMessage` capture + the one terminal-reason vocabulary (pure)

**Agent task**: Observability Phase 1 re-cut plan B2 (`docs/superpowers/plans/2026-10-21-observability-phase1-recut.md` §6; design of record P0 plan Task 2 with the five B2 Deltas applied).
**Files changed**:
- `src/runner/result_capture.py` (new, pure; no SDK import; imports only `pricing.cache_write_buckets`; nothing in `src/` calls it until B3 except the `usage_is_empty` re-export) — `TERMINAL_REASONS` (15: spec §2.4's 13 + `review_blocked`, `publish_failed`, D-P1-1), `API_RETRY_TO_TERMINAL` (the single `system/api_retry` category → reason table, six vendor categories; `oauth_org_not_allowed` → `oauth_revoked`), `ENFORCEMENT_CATEGORIES`, `ResultCapture` (frozen dataclass: `subtype, is_error, num_turns, duration_ms, duration_api_ms, total_cost_usd, stop_reason, api_error_status, usage, model_usage, permission_denials, result_text, errors, api_retry_error`; properties `input_tokens, output_tokens, cache_read_tokens, cache_write_1h_tokens, cache_write_5m_tokens, usage_empty, model_served`), `capture_result_message(message, *, api_retry_error=None)`, `derive_terminal_reason(capture, *, banner_terminal=False)` (Anthropic lane only), `same_model`, `requested_matches_served`, `served_model_violation(capture, requested_model, *, final_text)`, **`usage_columns(usage)`** (capture-free, both lanes), `result_columns(capture, *, terminal_reason, cost_usd_list, cli_version)` (token keys built through `usage_columns`; `cost_usd_list` has no default), `terminal_reason_for_exception(exc)`, `usage_is_empty` (relocated from `session.py`).
- `src/runner/session.py` — `usage_is_empty` + `_USAGE_TOKEN_KEYS` removed; `from src.runner.result_capture import usage_is_empty` re-exports it (`is_api_terminal_session` and `tests/test_api_terminal.py` are unchanged consumers). No other `session.py` change — the capture is wired in B3.
- `src/models.py` — `terminal_reason` comment: `completed` → `ok` (the value the tree stamps), pointing at `result_capture.TERMINAL_REASONS`.
- `tests/test_result_capture.py` (new, 70: `TestCapture` 8, `TestTerminalReason` 23, `test_codex_terminal_reasons_are_a_subset` 1, `TestServedModel` 9, `TestColumnsAndHelpers` 20, `TestUsageColumns` 5, `TestUsageIsEmpty` 4).
- `.context/modules/runner/CONTEXT.md` (Paths line + public-interface bullet), `.context/SYSTEM.md` (module-graph row after `session.py`; `session.py` Depends-on += `runner.result_capture`; the pricing row's `(B2)` marker dropped).

**Why**: `session._run_in_process` reads only `usage/is_error/subtype/result/errors` off the `ResultMessage`; `num_turns`, `duration_api_ms`, `total_cost_usd`, `model_usage`, `stop_reason`, `api_error_status` are dropped and terminal-failure detection is a banner regex. This module is the typed replacement (the regex stays as a belt through `banner_terminal`). The B2 Deltas honoured: (1) the 15-value tuple; (2) no `parse_cli_version` — B3's `session.cli_version()` reads `claude_agent_sdk._cli_version.__cli_version__`, no subprocess; (3) `result_columns` is documented as the 008 column payload; (4) `derive_terminal_reason` is the Anthropic-lane source only — the Codex lane keeps `ExecResult.terminal_reason`, and the subset relation `codex_cli.TERMINAL_REASONS <= TERMINAL_REASONS` is a test, not a module-level assert (`codex_cli.py` untouched); (5) `usage_columns` is capture-free so B3 stamps the token columns on both lanes through one function.

**Side effects**: none at runtime — no caller yet, no I/O, no audit kinds or fields, no settings. `session.usage_is_empty` is the same function object as before (identity pinned).

**Gotchas discovered**: (1) All-zero usage with real text is a NORMAL short-chat-job shape; the served-model check only rejects the fully-empty signature when `model_usage` is absent. (2) The web/dispatch launch paths pass bare aliases (`sonnet`) through unvalidated, so the served-model check accepts a hyphen-bounded alias inside the served id — but a `claude-` prefixed request only ever goes through `same_model`'s prefix rule. (3) An account hold and an expired login are both HTTP 403: the three enforcement reasons come from the `system/api_retry` `error` category, which outranks the status unconditionally; a transient category (`overloaded`, `rate_limit`, `authentication_failed`) outranks the status only on a FAILED capture — a recovered retry on a success is `ok` (whole-tier review 2026-10-22). (4) `result_columns(cost_usd_list=…)` deliberately has no default — a default would let a call site silently re-introduce the SDK figure the B4 reconcile is supposed to check against. (5) The `_USAGE_TOKEN_KEYS` name moved with `usage_is_empty`; nothing else referenced it.

## 2026-10-21 — B1: `pricing.py` — the single definition of `cost_usd_list` (pure core; two-window ledger, computed-vs-SDK reconcile, weekly-allowance calibration, lane seed)

**Agent task**: Observability Phase 1 re-cut plan B1 (`docs/superpowers/plans/2026-10-21-observability-phase1-recut.md` §6; design of record P0 plan Task 16 — the pure module only; the CLI, the `-run.sh` wrapper and the `com.assistant.cost-reconcile` timer are B4).
**Files changed**:
- `src/runner/pricing.py` (new, pure; nothing in `src/` imports it yet) — `Price`, `LIST_PRICES` (`claude-anthropic.md §4`, `PRICES_AS_OF = "2026-09-24"`, 12 families), `family_for` (longest prefix with a `-`/end boundary, case-insensitive; `None` for `sonnet`, unknown ids and provider-qualified ids), `cache_write_buckets` (nested `cache_creation.ephemeral_{1h,5m}` authoritative; the flat `cache_creation_input_tokens` → the 1-h arm — B2's `usage_columns` reuses it), **`price_usage(model, usage) -> Decimal | None`** — each cache-write bucket at its own rate, `Decimal(0)` for a known family with no tokens, `None` for anything unpriceable —, `usd_2dp` (half-UP cents), `JobCost` (+ `requested_model`, `provider`, `unpriced_label`), `read_events`, `_ts` (epoch int/float/numeric-string **and** ISO, `Z` accepted, naive read as UTC), `job_cost_from_events` (model = `job_completed.model_served` else `job_started.model`; provider from `job_completed.provider` else `job_started.provider`; a non-Anthropic provider is never priced as a Claude family), `ModelRow`, `KindRow`, `LedgerReport` (+ `to_dict`), `summarize`, `summarize_windows(jobs, *, until, windows=(30, 7))`, `lane_for` (the Phase-1 approximation, P0's 4-channel owner set), `lane_seed`, `write_lane_seed`, `implied_cache_write_rate`, `render_sdk_reconcile`, `QuotaReading`, `quota_readings` (`seven_day` only), `WeeklyCalibration` (+ `to_dict`), `weekly_allowance(jobs, readings, *, working=200)`, `render_weekly_allowance`, `render_table`, `render_db_delta`.
- `tests/test_pricing.py` (new, 27: `TestPrices` 9, `TestLanes` 1, `TestTs` 1, `TestLedger` 8, `TestSdkReconcile` 4, `TestWeeklyAllowance` 4).
- `.context/modules/runner/CONTEXT.md` (Paths line + public-interface bullet), `.context/SYSTEM.md` (module-graph row after `learning.py`; Depended-on-by names B2/B3/B4 as the consumers to come).

**Why**: `cost_usd_list` has exactly one definition and it is this module (spec §2.8, P0 round-3 #10 — populating the column from the SDK's `total_cost_usd` made the exit criterion compare that figure to itself). B3 stamps `jobs.cost_usd_list` by calling `price_usage` on the Anthropic lane and stores the SDK's figure separately as `sdk_cost_usd`; B4's script is what compares them. Re-cut deltas honoured: no `result_capture` prerequisite (the module is pure and B2 imports **from** it); `_ts` reads prod's epoch `resets_at`; a Codex job lands under `unpriced` as `codex/<id>` with its tokens counted (Review Focus 7) — there is no Codex price table in Phase 1 (`models.yml` has no price field); `lane_for` is labelled "approximated" (`jobs.lane` is NULL until Phase 3).

**Side effects**: none at runtime — no caller yet, no I/O beyond `read_events`/`write_lane_seed`, no audit kinds or fields, no settings. The three P0 test assertions of the form `round(Decimal("3.485"), 2) == Decimal("3.49")` were arithmetically wrong (Decimal rounds half-EVEN → `3.48`); the tests now assert the exact `Decimal("3.485")` and the spec's `$3.49` through `usd_2dp`, and every `$` cell the renderers print goes through `usd_2dp` so the tables show the spec's figures.

**Gotchas discovered**: (1) `round()` / `:.2f` on a `Decimal` is banker's rounding — a `$x.xx5` list price prints one cent under the spec's figure unless quantized `ROUND_HALF_UP`. (2) Prod's `rate_limit_status.resets_at` is an epoch integer while every other stamp is ISO; a `_ts` that only knew ISO would silently drop every weekly reading and report "no readings" as if the series did not exist. (3) A non-Anthropic provider must gate `family_for`, not just the unpriced label: a Codex job whose served id happened to start with `claude-` would otherwise be priced as a Claude family. (4) `WeeklyCalibration` keeps the P0 dataclass signature (`weekly_allowance(jobs, readings)`) rather than the B1 Interfaces line's `(readings) -> dict` paraphrase, because the named P0 tests call it with two positionals; `to_dict()` gives the dict form.

## 2026-10-21 — A5: the runner writes the notifications outbox (job terminals + every task lifecycle card), dual-write

**Agent task**: Observability Phase 1 re-cut plan A5 (`docs/superpowers/plans/2026-10-21-observability-phase1-recut.md` §6; design of record P0 plan Task 6 minus its `session.py` half (→ E1) and minus its switch gating (D-P1-10)).
**Files changed**:
- `src/runner/main.py` — imports `build_job_notice`, `build_task_notice`, `enqueue_notice` from `src.notify.outbox` (+ `typing.Any`). New pure `effective_origin_channel(own, parent) -> str | None` (spec §4.2: a child whose own channel is `None`/`system` inherits the parent's; an own human channel always wins) and `job_notice_kwargs(job) -> dict` (the `build_job_notice` kwargs off a Job row: `status=None` for the caller, `summary` from a dict `result`, `duration_seconds` from `started_at`/`completed_at`, the 007 lane columns `resolved_provider`/`resolved_model`/`model_served` and `num_turns` — 008, NULL until B3). New `_enqueue_job_notice(job_id, status)` loads the ROW (never the `jobs:done` payload), loads the parent once when `parent_job_id` is set and, when the channel is inherited, takes the parent's `origin_ref`/`origin_thread` with it (so the card lands in the parent's chat, not at a `target` of `dispatch-mcp`); `build_job_notice` → `enqueue_notice` when eligible. New `_task_target(task_id) -> (target, thread)` (`Task.origin_ref`/`origin_thread` first, `str(chat_id)`/`str(thread_message_id)` second, `(None, None)` = owner chat). `_notify_task` is the dual-write chokepoint: the legacy `tasks:notify` publish is unconditional and byte-identical, THEN the outbox row is written unconditionally inside a non-fatal try/except (the DB read included). The five direct `redis.publish("tasks:notify", …)` sites — escalation L3 (its local `from src.db import redis as _redis` deleted), choices, question, sentinel approval, auto-continue progress — route through it; `grep -c '"tasks:notify"' src/runner/main.py` → 1. `_finish_job` enqueues the `job_completed`/`job_failed` notice AFTER `publish_done` and only for those two statuses, non-fatal; an INV-9-suppressed finish returns before either.
- `tests/test_notify_runner_hooks.py` (new, 40: `TestEligibilityInheritance` 2, `TestJobNoticeKwargs` 6 incl. `test_passes_provider_and_model` + `test_kwargs_fit_build_job_notice`, `TestEnqueueJobNotice` 8 incl. `test_completed_web_job_enqueues_notice` + the parent-inheritance trio, `TestTaskTarget` 4, `TestNotifyTask` 8 incl. `test_outbox_row_written_in_both_modes`, `test_outbox_insert_failure_never_raises`, `test_legacy_channel_published_byte_identically`, `TestFinishJobNotice` 6 incl. `test_finish_job_failed_enqueues_notice_without_task`, `test_finish_job_cancelled_writes_no_notice`, `test_suppressed_finish_writes_no_row`, plus 6 source pins incl. `test_only_one_tasks_notify_literal_remains` and `test_switch_is_not_read_by_the_runner`).
- `.context/SYSTEM.md` — `src/runner/main.py` Depends-on += `notify.outbox`; the outbox row's Depended-on-by drops the `(A5)` marker. `.context/modules/runner/CONTEXT.md` (public interface bullet), `skills/GOTCHAS.md` (one entry).

**Why**: spec §9 P0 exit "a scheduled failure DMs within 60 s" — every failure DM path required `task_id`, and a web launch never entered `_job_to_chat` (Review Focus 2 and 3). D-P1-10: the runner dual-writes so the kill switch is renderer-side (bot-only restart); `settings.notify_outbox` is read nowhere under `src/runner/` (source-scanned).

**Side effects**: nothing changes on the wire — the runner publishes exactly what it did before in both switch positions. Every eligible terminal and every task card now ALSO inserts a `notifications` row + `notify:outbox` nudge (and a `notice_queued` audit line for job-subject rows, A4's kind). Until A6 flips the switch the bot's listener delivers only ops kinds, so job/task rows accumulate as `pending` (A6 marks them `skipped` in legacy mode). One extra `jobs` read per terminal, two for a child. `_finish_job`'s signature is unchanged; every existing monkeypatch of `_notify_task`/`_finish_job` stays green.

**Gotchas discovered**: (1) inheriting only the parent's CHANNEL is not enough — a `telegram` channel makes `build_job_notice` use `origin_ref` as the chat id, and a child's own ref is its `created_by` (`dispatch-mcp`); the ref/thread must travel with the channel. (2) `test_switch_is_not_read_by_the_runner` is a token scan, so even a docstring under `src/runner/` must not spell the setting's name.

## 2026-10-21 — A3: the quota reset time is labelled by its source (`vendor` vs `estimated`)

**Agent task**: Observability Phase 1 re-cut plan A3 (`docs/superpowers/plans/2026-10-21-observability-phase1-recut.md` §6; design of record P0 plan Task 7 Step 3b).
**Files changed**:
- `src/runner/quota.py` — `QuotaExhausted(reset_at, reason="", source="estimated")` stores `.source`; `pause_queue(reset_at, reason, *, source="estimated")` writes `quota:last_source` (`KEY_QUOTA_LAST_SOURCE`) beside the global pair (a value outside `SOURCES = ("vendor", "estimated")` is stored as `estimated` — the label may never over-claim); new `last_source() -> str` (`"estimated"` when unset or unknown); `clear()` deletes the three keys; `_read_pause` gains keyword-only `extra_keys=()` which the global `is_paused()` passes as `(quota:last_source,)` so BOTH the auto-resume and the corrupt-value branch forget the label with the pair. The per-provider lanes (`pause_provider` for a non-Anthropic name) never write the label; `pause_provider("anthropic", …)` delegates to `pause_queue` and so records `estimated`.
- `src/runner/session.py` — the three `raise quota.QuotaExhausted(...)` nodes in `_run_in_process` carry `source=`: the `RateLimitEvent` branch `"vendor" if reset_at is not None else "estimated"` (a rejected status without `resets_at` is the default window, not a vendor figure); the two text-heuristic raises (`message.error`, `ResultMessage.is_error`) `"estimated"`. Pinned by the AST test `test_three_raise_sites_are_labelled` (exactly three raises, exactly one may say vendor) — **B3 rewrites this loop and must keep the three nodes and their kwargs**.
- `src/runner/main.py` — the `QuotaExhausted` handler in `_process_job` passes `source=getattr(exc, "source", "estimated")` to `pause_queue` (the `getattr` keeps a test double without `.source` on the estimated path).
- `tests/test_quota.py` (+18: `TestPauseSource` 10, `TestSessionPassesVendorOnlyForRateLimitEvent` 2, `TestMainPassesTheSourceToThePause` 2 through the existing `main_harness`, `TestQuotaNoticeLabelsTheSource` 4).
- `.context/modules/runner/CONTEXT.md` (public interface line for `quota`).

**Why**: spec §2.8 Claude row / review #4 — the SDK emits `resets_at` only on status transitions and nothing else in Phase 1 is a vendor gauge, so a window figure may be called vendor-sourced only when a vendor event carried it. The runner is the only writer of the label; the bot reads it (gateway CHANGELOG, same date).

**Side effects**: `pause_queue`'s positional signature is unchanged (the new kwarg is keyword-only with the legacy default), so every caller/monkeypatch that passes two positionals keeps working. One more Redis key under `quota:` (string, no TTL — it is deleted with the pair). The runner log line `quota queue pause set` gains `source=`. No audit kind or field changes.

**Gotchas discovered**: `_read_pause` is shared by the global and per-provider scopes, so "the auto-resume branch deletes it" had to be expressed as an opt-in key list rather than an unconditional delete — otherwise a Codex lane expiring would delete the Anthropic label out from under a live global pause.

## 2026-10-21 — A2: `queue_wait_ms` at the running flip; `tasks.awaiting_since` has one writer; typed `terminal_reason` on every Anthropic-lane failure; a cancelled job is never escalated; scheduler rows carry origin

**Agent task**: Observability Phase 1 re-cut plan A2 (`docs/superpowers/plans/2026-10-21-observability-phase1-recut.md` §6; design of record P0 plan Task 4 + the 3b half of Task 3).
**Files changed**:
- `src/runner/main.py` — (1) pure `queue_wait_ms(created_at, started_at) -> int | None` (never negative; `None` when a stamp is missing), stamped on `jobs.queue_wait_ms` at the one `queued → running` flip in `_process_job` (reads `created_at` via `getattr(..., None)` because the `_process_job` test harnesses' row stand-ins have no `created_at`; the ORM row always does). (2) `_AWAITING_STATUSES = ("awaiting_user", "pending_approval")` + pure `awaiting_since_for(status, now)`; `_set_task_status` stamps/clears `tasks.awaiting_since` with the same clock read as `updated_at` and is now the ONLY runner writer of `tasks.status` outside the sentinel block: the two inline `awaiting_user` UPDATEs in `_update_task_after_job` (choices / question) and — review round 1 — the level-3 terminal `failed` write in `_maybe_escalate` (previously inline, without `updated_at` / `awaiting_since`; it already ran in its own `session_scope`) are routed through it; the auto-continue sentinel block keeps its shared session (it also inserts a TaskTurn) and stamps `awaiting_since` itself. Pinned by `test_no_inline_awaiting_user_update_remains_in_main`, `test_no_inline_task_failed_update_remains_in_main` and the behavioural `test_level_3_escalation_fails_the_task_through_set_task_status`. (3) `terminal_reason=` on the six Anthropic-lane `_finish_job(JobStatus.failed, …)` sites — preflight / `SkillResolutionError` / `DeployRefused` / `DeployNeedsApproval` → `"error"`, Anthropic timeout → `"timeout"`, Anthropic generic → `"api_error"` (B3 replaces the last with `terminal_reason_for_exception`) — and the additive `terminal_reason` key on EVERY `job_failed` audit line in `_process_job` (the five typed non-Anthropic sites included: `provider_refused`, `review_blocked`, `<executor terminal_reason>`). (4) **Cancelled guard**: both the `asyncio.TimeoutError` and the generic `Exception` handlers return right after `_refetch_job` when the fresh row is `cancelled` — before the lane decision, the terminal stamp and `_maybe_escalate` (which has no guard of its own and would enqueue a retry the owner just killed). The real `_finish_job`'s INV-9 WHERE would have suppressed the stamp anyway; the audit `job_failed` line (typed) is still written. (5) `_tick_schedules` stamps `origin_channel="scheduler", origin_ref=sched.name[:64]` on the Job it builds.
- `src/audit_log.py` — docstring: `job_failed` gains `terminal_reason` (additive, C14).
- `tests/test_origin.py` (A2 part), `tests/test_provider_dispatch.py::test_main_anthropic_timeout_still_escalates` — its `"terminal_reason" not in h.finished[0]` was the pre-A2 contract; now `h.finished[0]["terminal_reason"] == "timeout"` while `provider` stays unstamped (plan delta 3).
- `.context/modules/runner/CONTEXT.md` (public interface), `.context/modules/runner/skills/GOTCHAS.md` (plan-DAG children carry no `origin_thread`).

**Why**: spec §2.3 — queue wait and the age of a stuck ask are the two numbers the owner cannot get today; a NULL `terminal_reason` on a failed Anthropic job made B4's cost reconcile and A4's failed card guess; escalating a cancelled job re-ran work the owner had killed.

**Side effects**: `terminal_reason` is now non-NULL on every job the Anthropic lane fails (it already was on the non-Anthropic lanes and on completed jobs). A cancelled job that dies in the session no longer produces an escalation child. The `job_failed` audit shape keeps every existing field.

**Gotchas discovered**: the guard sits BEFORE `_finish_job` in both handlers because T4 already moved the refetch ahead of the stamp (the lane decision reads `resolved_provider`); the P0 plan drew it after the stamp. Same outcome, one round-trip fewer — the behavioural test pins `finished == []` for a cancelled row.

## 2026-10-21 — Final review of the cross-vendor writer slice: two gate findings applied (textconv, case-insensitive deny list)

**Agent task**: apply the final code-review findings on `multi-model/cross-vendor-writer` (code-review (final), 2 majors → lgtm). No protected path touched; nothing pushed.
**Files changed**:
- `src/runner/review.py` — (1) **`--no-ext-diff` did not close the diff-driver hole**: `diff.<drv>.textconv` in the clone's `.git/config` plus `*.py diff=<drv>` in a `.gitattributes` still RAN the converter under `GATE_GIT_OPTS` + `--text --no-ext-diff` (verified on git 2.53.0: marker file written, and with an empty converter the reviewer-visible diff carried NO content lines for the file — on both `diff <base>` and `diff --no-index`), so `diff_for_gate`'s "nothing in `.git/config` may shape what the reviewer sees" was false. `GATE_DIFF_FLAGS` gains `--no-textconv` (git honours it on both diff forms); docstring and flag comment name the converter. Precondition is a writable `.git/` (the canary's `git_dir_protected` probe says Seatbelt denies it) — defense in depth, same as the hooksPath pin. (2) **Deny list was case-sensitive on a case-insensitive host** (pre-existing, sibling of the quoted-path bypass): `gate_path_denied(".CLAUDE/settings.json")`, `("agents.md")`, `("sub/.GitAttributes")` were all False, yet on APFS (this Mac, the canonical, every agent that opens it) those ARE `.claude/settings.json` / `AGENTS.md` / `.gitattributes` — a Codex job could plant hooks or instructions past the belt. `gate_path_denied` now compares `top`, the single-segment file name and `parts[-1]` with `.casefold()` against casefolded frozensets (`_GATE_DENIED_DIRS_CF/_FILES_CF/_BASENAMES_CF`); fail closed — on a case-sensitive host a false positive only costs a refusal. **Behaviour change**: `research/claude.md`, `agents.md`, `.Github/…`, `.GITMODULES` etc. are now refused (they were listed as allowed in `TestGatePathDenials.test_allowed`; those two cases are replaced by `research/claude-notes.md` / `agents.txt`).
**Tests**: `tests/test_pre_push_gate.py` 92 → 114 collected — `TestGateDiffCannotBeBlinded.test_textconv_driver_is_never_invoked` (real repo: textconv planted in `.git/config`, tracked + untracked file under the attribute; asserts the marker is absent and both `+` lines are present — fails without the flag), `test_deny_list_is_case_insensitive` (15 variants incl. `.CLAUDE/x`, `.Github/workflows/x.yml`, `agents.md`, `claude.md`, `sub/.GitAttributes`, `.GITMODULES`, `.MCP.json`) and `test_casefold_does_not_overreach` (`claude.py`, `agents/x.py`, `github/x.yml`, `src/.claude_cache/x`, `sub/gitattributes` stay allowed). Suite 2139 passed, 1 skipped; `scripts/lint_docs.py` clean; ruff on the two files unchanged (13 pre-existing findings, none new).
**Not done / residual**: unchanged from the whole-branch entry below (per-target publish allowlist = T8/owner work).

## 2026-10-21 — Whole-branch review of the cross-vendor writer slice: five gate/containment findings applied

**Agent task**: apply the whole-branch code-review findings on `multi-model/cross-vendor-writer` (plan `docs/superpowers/plans/2026-10-21-cross-vendor-writer-slice.md`, notes under T5/T10, §6, §8). No protected path touched.
**Files changed**:
- `src/runner/review.py` — (1) `diff_for_gate` treats the clone as UNTRUSTED: `GATE_DIFF_FLAGS = --no-color --text --no-ext-diff` on both `git diff` calls (a nested `sub/.gitattributes` with `* -diff` rendered every file under it as `Binary files … differ` while `publish_workspace` shipped the real bytes — confirmed by the reviewer; `--text` shows the content, `--no-ext-diff` ignores `diff=<driver>`/`diff.external`), `GATE_GIT_OPTS = -c core.quotePath=false -c core.fsmonitor=false -c core.hooksPath=/dev/null` on every gate git call. `.gitattributes` added to `GATE_DENIED_BASENAMES` (denied at ANY depth). (2) The deny list could be bypassed by a git-QUOTED path (`diff --git "a/.github/workflows/\303\244.yml" …` matched neither header regex, so the path was never collected — a workflow with repo secrets could pass): `core.quotePath=false` prints non-ASCII raw, and new pure `gate_unparseable_headers(diff)` + `gate_refusal(diff) -> ("denied_path"|"unparseable_path", items) | None` make the parser FAIL CLOSED on any header it cannot read (quoted `diff --git`/`---`/`+++`/`rename`/`copy` lines; hunk content starting with `--- "` is not a header and is ignored).
- `src/runner/session.py` — (2) `_pre_push_gate` uses `review.gate_refusal`; `unparseable_path` audits `merge_gate_refused{reason=unparseable_path, lines}` + `ReviewBlocked(verdict=blocker, refused_reason=)`. (3) **Oversized diff**: `run_code_review` truncates at `MAX_DIFF_CHARS` (50 000) and any LGTM on the partial read used to publish the WHOLE clone; the gate now refuses first — `merge_gate_refused{reason=diff_too_large, diff_chars, max_chars}` + `ReviewBlocked(verdict=changes_requested, refused_reason="diff_too_large", diff_chars=)`; a diff of exactly `MAX_DIFF_CHARS` is still reviewed. `ReviewBlocked` gains `refused_reason` (`denied_path|unparseable_path|diff_too_large|None`) and `diff_chars`; the message names each. (4) **Plan §4f enforced**: `EXECUTOR_CONCURRENCY = {codex_cli: 1}`, lazily created `_EXECUTOR_SLOTS` (`executor_slot(name)`, `executor_name_for(provider)` = the registry's `executor:` key); `_run_executor` runs `executor.run` under `async with slot` — a contended wait audits `executor_slot_wait{executor, waited_s, concurrency}` and is subtracted from the executor's budget (main's ceiling does not move), an uncontended slot changes nothing (the budget tests stay exact).
- `src/runner/workspaces.py` — (5) `UNTRUSTED_GIT_OPTS = -c core.hooksPath=/dev/null -c core.fsmonitor=false`; `_run_git(..., untrusted=True)` for `head_sha`, `current_branch` and every call in `publish_workspace` (add, diff --cached, the commit, the push), and the push is `git push --no-verify`. A `.git/hooks/*`, `core.hooksPath` or `core.fsmonitor` planted in the clone never runs as the owner under the runner's unscrubbed env — whether or not Codex's Seatbelt keeps `.git/` read-only.
- `src/runner/main.py` — the `ReviewBlocked` done card branches on `refused_reason` (denied paths / unparseable quoted paths / diff too large, with the char count and `MAX_DIFF_CHARS`).
- `src/runner/executors/codex_cli.py` — canary (5): prompt step 4 `touch '.git/codex-canary'` (`CANARY_GIT_PROBE`), new check `git_dir_protected` (file must not exist after the run; `touch_in_stream` recorded; removed after), `CANARY_CHECKS` now ten; `gate_dry_run` applies the same three pre-reviewer refusals as the session (`gate_refusal` + `diff_too_large`) and reports `refused_reason`.
- `src/audit_log.py` — docstring: `merge_gate_refused` reasons `unparseable_path` (+`lines`) and `diff_too_large` (+`max_chars`), additive; new kind `executor_slot_wait`. No kind renamed or reshaped (C14).
**Tests**: `tests/test_pre_push_gate.py` 74 → 92 (nested/any-depth `.gitattributes` + external diff driver + fsmonitor on real temp repos; quoted/tab paths pure and real; unparseable + oversized through `run_session` and main's card; two Codex jobs serialise on the slot, the slot is released on an executor exception, slot keyed by registry name; planted hooks never run during publish). `tests/test_codex_canary.py` 48 → 50 (git-dir probe detected and not double-reported; dry-run refuses quoted and oversized diffs). Existing Anthropic-path tests untouched.
**Not done / residual**: the per-target publish allowlist (old spec §2.5) stays T8/owner work; the live canary result for `git_dir_protected` is in plan §8.

## 2026-10-21 — T10: live canary entry points + first real `codex exec` run

**Agent task**: cross-vendor writer slice T10 (`docs/superpowers/plans/2026-10-21-cross-vendor-writer-slice.md` §5 T10, §8).
**Files changed**:
- `src/runner/executors/codex_cli.py` — new section: `main()` CLI
  (`--canary <clone>` / `--gate-dry-run <clone>`), `run_canary()`,
  `check_canary()` (the nine T10 assertions as `{name: {ok, detail}}`),
  `check_kind_sequence()`, `build_canary_prompt()`, `canary_environ()` (a
  sentinel value under every denied name), `is_denied_env_name()`,
  `gate_dry_run()` (`review.diff_for_gate` → `gate_path_denials` →
  `run_code_review`, verdict only, no publish/sync; lazy `review` import),
  `_refuse_clone()` (exit 3 under this repo / the production checkout /
  any `volumes/`, or while `settings.server_root` is the production path).
  Nothing in `run()`/`EventMapper` changed; `tests/test_codex_executor.py`
  untouched and green.
- `scripts/codex-canary.sh` (new) — seed repo + clone under `CANARY_ROOT`
  (refused under the repo / prod / volumes), `PIPENV_DONT_LOAD_ENV=1
  SERVER_ROOT=<root>/fake-server-root`, runs the canary then the gate
  dry-run; exit 2 = did not run (rate-limited / login lapsed), never retried.
- `tests/fixtures/codex/sandbox_denied.jsonl` (recorded) +
  `tests/test_codex_canary.py` (new, 48): fixture-driven canary (the factory
  replays `command_and_file.jsonl` and performs that run's side effects),
  each check's failure mode, gate dry-run with a stubbed reviewer, `main()`
  exit codes and location refusals.
**Live result (plan §8)**: PASS — 9.42 s, 65,359 in / 405 out tokens, not
rate-limited, 0 denied env names of 33 visible, escape `touch ~/…` blocked by
Seatbelt, `-o` written outside the clone under `workspace-write` (T3 (g)
verified), `model_served` not reported by this build; gate dry-run
`changes_requested` (6 findings, 28.1 s, opus-4-7) — correct for a diff that
adds two canary files.
**Finding (residual, plan §6)**: a Seatbelt-denied command emits NO
`command_execution` item on codex-cli 0.162.0-alpha.17.2 — the audit log
under-reports attempts; and `/bin/zsh -lc` sources the owner's rc files, so
the child's env is the scrubbed allowlist PLUS whatever those files export.
**Docs**: runner CONTEXT (entry points + test), SYSTEM.md (row + script),
runner GOTCHAS (3 entries), TROUBLESHOOTING (1 symptom).

## 2026-10-21 — T8: protected-path bundle (branch `multi-model/protected-bundle`, owner-merged)

**Agent task**: cross-vendor writer slice T8 (`docs/superpowers/plans/2026-10-21-cross-vendor-writer-slice.md` §5, D-D). Protected paths — the owner reviews and merges this branch by hand (INV-4); it is never merged by the slice itself.
**Files changed**:
- `src/runner/guards.py` — `VENDOR_CREDENTIAL_NAMES` (`OPENAI_API_KEY`,
  `CODEX_API_KEY`, `GEMINI_API_KEY`, `OPENROUTER_API_KEY`, `XAI_API_KEY`,
  `CLAUDE_CODE_OAUTH_TOKEN`) denied at assignment and export beside
  `ANTHROPIC_API_KEY`, in BOTH hard-deny lists (workspace + read-only
  profiles); the two existing `ANTHROPIC_API_KEY` rows are untouched. INV-22
  server-side deny (the "open follow-up" on the SYSTEM.md row): `api.tradier.com`
  wholesale, `sandbox.tradier.com/v1/accounts/*/orders` and
  `*.alpaca.markets/v2/orders` in both lists — market-data/account reads on the
  sandbox, paper and data hosts stay free. Reads of a credential name
  (`printenv`, `echo $X`, grep) are still allowed: the deny is on assignment,
  the scrubbed executor env is why no key is inheritable. Text-level belt;
  the atlas kernel tripwires remain the INV-22 enforcement of record.
  KNOWN FALSE POSITIVE (review, 2026-10-21): because `api.tradier.com` is
  denied wholesale, a read-only mention of the production host on a command
  line (`grep -rn api.tradier.com swing/`, a `git commit -m` naming it) is
  denied too, inside atlas workspace build jobs as well. It fails closed with
  a `Bash denied: production brokerage host api.tradier.com` reason — use
  `grep -f <pattern-file>` or split the host across variables; it is not a
  bug (`tests/test_guards.py::test_production_tradier_host_mention_is_a_known_false_positive`).
- `scripts/lint_docs.py` — checks 14 (`check_model_pins`: every skill
  `model:`/escalation target resolves in `models.yml`; non-Anthropic ⇒
  `isolation: workspace`; a `code-server` skill may pin a non-Anthropic
  provider only when `ROUTER_CODE_SERVER_PROVIDERS` — the same setting the
  session reads — lists it; and, after review, an `escalation.on_failure.model`
  must resolve to Anthropic — `main.py:_maybe_escalate` enqueues the retry
  with `payload.model=<target>`/`created_by="escalation:…"`, which
  `lane_refusal`'s owner-origin rule refuses on an Anthropic-pinned skill, so
  a non-Anthropic target was a retry that could never run) and 15 (`check_code_server_set`: the protected
  `CODE_SERVER_SKILLS` here is the set of record; `runner/session.py`'s copy
  is AST-read and must be byte-equal, so neither yml nor an INV-4-lane edit
  can widen the lane). Wired into `run_all()`.
- `.context/SYSTEM.md` — INV-21 row rewritten to the implemented profile
  (workspace-only + Seatbelt + scrubbed env + no MCP/subagents; code-server
  and in-repo canonicals pinned by setting; pre-push Anthropic gate, runner
  commits/pushes; provider keys never session-assignable; per-provider lane
  pause; ships dark) with the enforcement column naming every mechanism and
  test; the "Model router" workstream sentence that said the row still
  carried the 08-17 wording updated to match.
- `tests/test_guards.py` — vendor-credential deny (parametrised over the
  set), assignment-vs-read distinction, broker order hosts denied / non-order
  broker reads allowed, both profiles, reason names INV-22.
- `tests/test_doc_lint.py` — repo-level + fixture tests for checks 14/15
  (each rule fires and stays silent; the setting flip relaxes rule 3; set
  drift and a missing literal are reported; `run_all` wiring).

**Why**: D-D — the slice's own tests enforce these rules without the
protected files (T1/T4 lint-equivalents, T3 env scrub); the bundle makes
them structural in the files an injected diff would target. `MISSION.md`
untouched (its non-goal wording stays true while D-A is off).

**Side effects**: none on the Anthropic path — existing guard cases are
unchanged and `test_guards` 207/207; `python scripts/lint_docs.py` prints
"All clean!" on the live tree. Audit event kinds unchanged (C14).
`.context/modules/runner/CONTEXT.md` still says the SYSTEM.md INV-21 row
"carries the 08-17 wording until the owner merges plan T8" — true until this
branch merges; the sentence is outside T8's allowed edit set and should be
dropped on merge.

## 2026-10-21 — T9: docs, registries, runbook (no code change)

**Agent task**: cross-vendor writer slice T9 (`docs/superpowers/plans/2026-10-21-cross-vendor-writer-slice.md` §5).
**Files changed** (docs only):
- `.context/modules/runner/CONTEXT.md` — the two pre-dispatch notes left by
  T1/T3 ("declared in T1, not yet consumed", "not called by `run_session`
  until T4") replaced with the shipped state; Configuration now documents
  `ROUTER_CODE_SERVER_PROVIDERS` as D-A's one setting (skill-name rule +
  canonical-path rule), `CODEX_BIN` discovery order + fail-closed misconfig,
  `CODEX_HOME`, `CODEX_SANDBOX_DEFAULT`, `CODEX_RUN_AS_USER` (unusable until
  materialisation, §6 D-C) and `QUOTA_PAUSE_MINUTES` on the lane pause;
  Testing lists `test_codex_executor` / `test_provider_dispatch` /
  `test_quota` / `test_cross_vendor_docs`; Key invariants gains INV-21's
  implemented profile (the SYSTEM.md row itself is T8/owner).
- `.context/SYSTEM.md` — "Model router" workstream line: BUILT 2026-10-21,
  ships dark, INV-21 row deferred to T8. Module-graph rows were already added
  by T1/T3/T4.
- `.context/INDEX.md` — "Additions 2026-10-21" block (what ships, the owner
  runbook, debugging a Codex job, where to change what, what was not built,
  the protected bundle) + the 2026-09-25 spec row's "deferred, not planned"
  caveated with the reopening.
- `docs/README.md` — row for the slice plan; the 2026-09-25 spec row caveated.
- `docs/TROUBLESHOOTING.md` — five symptoms: `provider_refused` (reason
  table, one row per rule), "codex not found" (`CODEX_BIN` discovery), the
  `codex exec` hang (stdin / silent 429), `auth_expired` (`codex login
  --device-auth` into the runner's `CODEX_HOME`), `job_held` (lane pause,
  `/resume codex`). The T5 `review_blocked` entry already existed.
- `docs/superpowers/specs/2026-10-05-observability-and-trading-unblock-design.md`
  §14 items 1, 9, 10 — annotated "reopened 2026-10-21 by this slice" with
  exactly which half shipped. (The plan header names the 2026-09-25 spec's
  §14; that section is "Open questions" — the fifteen deferred items live in
  the cut spec's §14. Noted in the plan's T9 section.)
- `.context/modules/runner/skills/GOTCHAS.md` — entry: nothing caps Codex-lane
  concurrency at 1 (plan §4f is an assumption; only the global
  `MAX_CONCURRENT_JOBS` semaphore exists) — found while writing the
  `auth_expired` symptom; recorded in plan §6 as residual, follow-up is a
  per-provider `asyncio.Semaphore(1)` with its own test.
- `tests/test_cross_vendor_docs.py` (new, 33 collected) — the T9 docs
  contract as pure file-content checks: every `src/runner/executors/*.py`
  named in this CONTEXT (the protected `lint_docs.py` only globs the top
  level), SYSTEM.md rows, INDEX/README rows + caveats, the five TROUBLESHOOTING
  headings, cut-spec annotations, no stale notes here, db CONTEXT lists the
  slice's audit kinds, each module CHANGELOG records T9, the plan's T9 note.
**Tests**: suite green, lint clean (numbers in the plan's T9 note).

## 2026-10-21 — T7: `provider` in INDEX.jsonl entries

**Agent task**: cross-vendor writer slice T7
(`docs/superpowers/plans/2026-10-21-cross-vendor-writer-slice.md` §5).
**Files changed**:
- `src/runner/audit_index.py` — `IndexEntry.provider: str | None` (placed
  after `model`), filled from `job_started.provider` (additive since T4);
  `None` for audit logs written before that — a pre-007 entry is never
  guessed to be Anthropic. `search_index(..., provider=)` optional filter;
  entries without the key never match a provider filter. `rebuild_index` /
  `append_to_index` emit the field via `asdict` unchanged.
- Tests: `tests/test_audit_index.py` (+4).

## 2026-10-21 — T6: per-provider quota keys (lane pause + hold-to-tail)

**Agent task**: cross-vendor writer slice T6
(`docs/superpowers/plans/2026-10-21-cross-vendor-writer-slice.md` §5).
**Files changed**:
- `src/runner/quota.py` — the global pair (`quota:paused_until` /
  `quota:last_reason`, now the `src.db.KEY_QUOTA_*` constants) keeps its
  Anthropic meaning and INV-12 semantics; `pause_queue` / `is_paused` /
  `clear` are behaviourally unchanged (shared `_write_pause` / `_read_pause`
  internals). NEW per-provider lane pause over `quota:provider:<p>:paused_until`
  / `:last_reason`: `provider_keys(p)` (pure; refuses `anthropic`, empty, or
  `:`/`/` in the name), `pause_provider(p, reset_at, reason)`,
  `is_provider_paused(p)` (auto-resume on expiry, corrupt value deleted),
  `clear_provider(p)`, `paused_providers(names)`. The Anthropic name
  delegates to the global functions so one call answers for any provider.
  `GLOBAL_PROVIDER = "anthropic"` (asserted equal to the registry default in
  tests; the registry is NOT imported — module row stays config+db).
- `src/runner/main.py` — (1) **Hold**: inside `_process_job`'s fetch
  transaction, BEFORE the row is flipped to `running`,
  `_hold_if_provider_paused(job)` checks the job's lane: provider =
  the session's `resolved_provider` stamp from an earlier attempt, else
  `preresolve_provider(kind, description, payload)` (pure given
  `load`/`route`: `payload.model > skill pin > settings.default_model` with
  `_resolve_skill`'s kind→skill mapping and the RULE router only — no LLM
  fallback; never raises, `None` = cannot tell → run and let the session
  refuse properly). Paused ⇒ audit `job_held{provider, reason, until}` (once
  per (job, pause window) via `_held_audited`, not every cycle), schedule
  `_requeue_held(job_id, hold_delay(until, now))` — an RPUSH to the TAIL
  (plan §4g) after `min(remaining, HOLD_RECHECK_SECONDS=30)` seconds as its
  own task (no concurrency slot, no DB write; `_job_loop` cancels the
  pending ones on shutdown so they push immediately; a crash is healed by
  `requeue_stranded_queued`) — and return without touching the row. A
  Redis blip on the check fails OPEN to the session. Anthropic jobs never
  reach the Redis read (the global pause gates the loop before BLPOP).
  (2) **Codex 429**: the `ExecutorFailed` handler's `rate_limited` branch
  now mirrors `QuotaExhausted` on the lane: `quota.pause_provider(provider,
  None, reason)` (never the global key; the stream has no reset time →
  `settings.quota_pause_minutes`), `LPUSH` FRONT, row back to `queued` with
  `error_message="queued for <provider> quota reset (…)"`, audit
  `job_requeued_for_quota{reason, +provider, +until}` (additive fields),
  no `job_failed`, no `_finish_job`, no DM, no escalation. Every other
  terminal reason is unchanged (terminal, never escalated). `router` is
  now a top-level import (already in the SYSTEM.md row).
- `src/audit_log.py` — docstring: `job_held` (new kind) and the additive
  `provider`/`until` fields on `job_requeued_for_quota`.
- Tests: `tests/test_quota.py` +50 (keys; provider pause/resume round
  trips; independence from the global key both ways; expiry; Anthropic
  delegation; `preresolve_provider` precedence/mapping/None cases;
  `hold_delay`; `_process_job` held → tail with audit, dedupe, stamp wins,
  Anthropic never held, fail-open, cancel-pushes-now; Codex `rate_limited`
  → lane pause + FRONT + queued, global key untouched, other reasons
  terminal, Anthropic `QuotaExhausted` shape untouched; web `/api/quota`
  map; Telegram `/status` lane line and `/resume [provider]`). Suite 1977
  passed, 1 skipped; lint clean.
- **Review round (code-review T6, lgtm; minors applied)**:
  `preresolve_provider` now resolves `load` / `route` at CALL time
  (`None` defaults → module-level `load_skill` / `router.route`), so a
  module-level monkeypatch is honoured — the test harness's
  `load_skill` patch was previously dead (default captured at
  definition time). The `main_harness` fixture also stubs
  `plans.promote_deferred_for`: it ran for every completing job and
  opened a REAL asyncpg connection through plans.py's own
  `async_session`, the source of the `coroutine 'Connection._cancel'
  was never awaited` warning. SYSTEM.md INV-12 row notes the
  hold-to-tail exception.

## 2026-10-21 — T5 review round 1 applied (code-review T5, blocker → lgtm)

**Agent task**: cross-vendor writer slice T5, reviewer findings (2 blockers,
1 major, 3 minors). **Files changed**:
- `src/runner/review.py` — `run_code_review` passes `setting_sources=[]`
  (SDK isolation mode): with the default `None` the reviewer `claude`
  process loaded the REVIEWED checkout's `.claude/settings.json` /
  `settings.local.json` (hooks run as the owner, unscrubbed env) and
  `CLAUDE.md` — a Codex clone under `workspace-write` can plant exactly
  those. Applies to belt 2 as well. New pure helpers `gate_diff_paths(diff)`,
  `gate_path_denied(path)`, `gate_path_denials(diff)` over a hardcoded deny
  list (`GATE_DENIED_DIRS` = `.claude .codex .git .githooks .github`,
  `GATE_DENIED_FILES` = `.gitmodules .gitattributes .gitconfig .mcp.json`,
  `GATE_DENIED_BASENAMES` = `AGENTS.md CLAUDE.md`; deny wins, a rename
  counts both sides) — the minimal stand-in for the old spec's per-target
  `publish_allowlist` (T8/owner).
- `src/runner/session.py` — (1) `_pre_push_gate` refuses a diff touching a
  denied path BEFORE spending a reviewer: audit `merge_gate_refused{belt,
  reason=denied_path, paths}` + `ReviewBlocked(..., verdict="blocker",
  denied_paths=)` (new attr); clone kept. (2) NEW pure
  `canonical_refusal(canonical_cwd, *, slug, provider, code_server_providers,
  server_root, projects_dir)` called in `run_session` beside the git-canonical
  check, before `create_workspace`: unless the provider is in
  `ROUTER_CODE_SERVER_PROVIDERS`, a non-Anthropic job with no project slug,
  a canonical equal to `settings.server_root`, or one inside the server
  root but outside `projects_dir` is `ProviderRefused` naming D-A —
  `lane_refusal` keyed `code-server` on skill NAMES only, so a generic
  (router-unmatched) `/task --model=codex/…` resolved to THIS repo and T5's
  publish path would have pushed it to `origin/main` from a clone of the
  production checkout. (3) Budget: `executor_timeout_s(ceiling, reserve_s=)`
  + `gate_reserve_s()` (= `review.GATE_TIMEOUT_SECONDS` + new
  `GATE_PUBLISH_MARGIN_S` 60 s); `_run_executor` reserves it, so the gate
  completes inside main's `wait_for` instead of being cancelled mid-review
  and mislabelled `timeout` (1800 s ceiling → executor 1110 s). (4) Commit
  subject falls back to `job.kind` on an empty/whitespace description
  (was IndexError after LGTM). (5) A rejected push after LGTM raises
  `ExecutorFailed(..., "publish_failed")` (was a bare RuntimeError →
  `api_error`), so the ledger separates "approved, push rejected" from a
  vendor error.
- `src/runner/main.py` — the review-blocked card names the denied paths.
- `src/audit_log.py` — docstring: `merge_gate_refused` kind; `job_failed`
  category `publish_failed`.
**Tests**: `tests/test_pre_push_gate.py` 33 → 74 collected (deny-list parse/rules,
refusal before the reviewer, `setting_sources=[]` captured off a faked
`query` + source assertion, D-A canonical rule pure + through `run_session`
both ways, budget arithmetic + a shrunk-clock run under main's ceiling,
empty description, typed publish failure, main card); both harnesses'
`_resolve_project` now return a slug (the rule refuses slug-less jobs) and
`test_run_session_executor_gets_a_timeout_under_mains_ceiling` asserts the
reserved budget. Suite green; lint clean. Not done (hard rule): no
`guards.py`/`lint_docs.py` change — the per-target allowlist stays T8.

## 2026-10-21 — T5: pre-push Anthropic review gate for non-Anthropic lanes (INV-21(c))

**Agent task**: cross-vendor writer slice T5
(`docs/superpowers/plans/2026-10-21-cross-vendor-writer-slice.md` §5; plan
§4b, old spec §5.3 belt 3b). Closes the ff-sync-before-review hole for
vendor writers: Anthropic reviews every non-Anthropic diff BEFORE anything
reaches a canonical repo, and the runner is the only committer/pusher.
**Files changed**:
- `src/runner/session.py` — `_pre_push_gate(job, ref, ws, *, base_sha,
  skill_name) -> (review_outcome, published)` runs in `run_session` right
  after `_run_executor` returns and before `job_completed`, keyed on the
  provider alone (a RULE, no setting — the test asserts the function reads
  nothing from `settings`). `review.diff_for_gate(clone, base_sha)` →
  empty → audit `merge_gate_skipped{belt=pre_push, reason=empty_diff}`,
  job completes with no commit; otherwise `review.run_code_review` (the
  fixed Anthropic reviewer) under `asyncio.wait_for(review.GATE_TIMEOUT_SECONDS
  = 600)` — a timeout IS `changes_requested` — audited as
  `merge_gate_verdict{belt, reviewer_provider, reviewer_model, verdict,
  findings_n, timed_out, diff_chars, base_sha}`. LGTM →
  `workspaces.publish_workspace` (runner commits with `Executor:`/`Job:`/
  `Reviewed-By:` trailers, pushes; audit `workspace_published`) and only
  then the existing `sync_canonical` in `finally` (gated on `published`);
  a failed publish raises `RuntimeError` (terminal on the lane, clone kept).
  Anything else raises the new `session.ReviewBlocked(provider, model_id,
  *, verdict, findings_n, timed_out)` — clone kept, no commit, no sync.
  `base_sha` (`workspaces.head_sha(clone)`) is captured right after
  `create_workspace` for non-Anthropic jobs and rides `workspace_created`
  additively; a non-Anthropic job on a NON-git canonical is `ProviderRefused`
  before the clone (no diff, no publish path). The T4 "clone kept for T5"
  `note` is gone: successful non-Anthropic jobs now clean up like Anthropic
  ones; `cleanup_workspace(keep=session_failed)` for every lane. Result dict
  gains `review_outcome` (None on Anthropic / empty diff).
- `src/runner/review.py` — `REVIEWER_PROVIDER`/`REVIEWER_MODEL`/
  `REVIEWER_EFFORT` constants (`run_code_review` now reads them — same
  opus-4-7/high, so the trailer and the reviewer cannot drift),
  `GATE_TIMEOUT_SECONDS`, `diff_for_gate(cwd, base_sha)` (committed +
  staged + unstaged via `git diff <base>` on the working tree, plus
  untracked via `git diff --no-index /dev/null <f>`; gitignored excluded;
  RAISES on any git failure — fail closed, never an "empty" diff),
  `count_findings(text)` (list-item heuristic for `findings_n`).
- `src/runner/workspaces.py` — `head_sha(path)`, `current_branch(path)`,
  `provenance_trailers(provider=, model_id=, job_id=, reviewer=)`,
  `publish_workspace(ws, *, base_sha, message, trailers) -> (ok, detail,
  sha)`: `git add -A`, commit (`--no-verify`, message + trailers; an empty
  provenance commit when the job committed on its own — never amend),
  `git push origin <branch>:<branch>` when the canonical has a remote. ONE
  push attempt: a rejection is reported (`ok=False`, sha kept), never
  rebased, never forced. Never raises.
- `src/runner/main.py` — `except session_mod.ReviewBlocked` (before
  `ExecutorFailed`): audit `job_failed error_category=review_blocked`,
  `_finish_job(failed, provider=, terminal_reason="review_blocked",
  review_outcome=<verdict>, done_payload={summary: <card>})`, task
  `failed` card naming the verdict/findings, never escalated.
  `_terminal_values`/`_finish_job` gain `review_outcome=` (+ `_finish_job`
  `done_payload=` to override the `jobs:done` DM text); the completed path
  stamps `result["review_outcome"]`. `_maybe_review` skips non-Anthropic
  lanes with `post_review_skipped{reason=pre_push_gate, provider, verdict}`
  — the gate is the review of record (T4-review note resolved: no more
  `stale_head` WARNING on every Codex job).
- `src/audit_log.py` — docstring: `merge_gate_verdict`,
  `merge_gate_skipped`, `workspace_published`, `post_review_skipped`
  reasons, `workspace_created.base_sha`, `job_failed` category
  `review_blocked`.
**Tests**: `tests/test_pre_push_gate.py` (33: diff/publish on real temp
repos, every gate outcome through `run_session` with spies, main's
terminal handling, belt-2 skip, rule-not-switch AST check);
`tests/test_provider_dispatch.py` harness gained a git-looking canonical
and an empty-diff gate stub, and the T4 end-to-end test's tail now asserts
the empty-diff skip instead of the kept clone. Suite 1886 passed, 1
skipped; lint clean.


## 2026-10-21 — T4: dispatch at the single executor call site (`session.run_session`)

**Agent task**: cross-vendor writer slice T4
(`docs/superpowers/plans/2026-10-21-cross-vendor-writer-slice.md` §5; plan
§4a/§4h, old spec §2.4/§2.6/§5.3 belt 3b).
**Files changed**:
- `src/runner/session.py` — `run_session` now dispatches on the resolved
  provider: Anthropic runs in-process through the SDK exactly as before;
  any other provider runs through the executor module the registry names
  (`models.yml` `executor:` → `_EXECUTORS = {"codex_cli": codex_cli}`,
  `executor_for(provider)`), sharing skill/cwd/isolation/clone/system-prompt
  assembly before and marker-parse/summary/`job_completed` after.
  `resolve_model_choice(payload, skill_cfg) -> (ModelRef, reason)` replaces
  the body of `_resolve_model` (which is now the value-only wrapper) and
  refuses `no executor` from the registry's executor name instead of T1's
  interim `_EXECUTABLE_PROVIDERS`. **Fail-closed lane rules** (pure
  `lane_refusal(...)`, raised as `ProviderRefused` BEFORE `create_workspace`
  so a refusal never leaves a clone): isolation tier must be `workspace`;
  no `subagents:`; no `needs-*-mcp` tag; `CODE_SERVER_SKILLS`
  (`server-patch`, `server-deploy`, `new-skill`, `deploy-director`,
  `atlas-redeploy`, `project-redeploy`) need the provider in
  `settings.router_code_server_providers` (`code_server_providers()`); a
  `payload.model` override that moves an Anthropic-pinned skill to another
  provider is honoured only from an owner origin (`is_owner_origin`:
  `telegram:*`, `web`, `cli`/`cli:*` — an allowlist). New audit
  `provider_selected{provider, model, reason ∈ payload|pin|default}`;
  `job_started` gains `provider`; `job_completed` gains `provider`,
  `model_served`, `terminal_reason`; the result dict gains `provider`,
  `model`, `model_served`, `terminal_reason`; the `resolved_*` DB stamp
  gains `resolved_provider` (`resolved_model` stays the bare id).
  `_build_system_prompt(...)` split out of `_build_options` unchanged
  (`_build_options(..., system_prompt=)` accepts the pre-built prompt;
  identical bytes either way); `build_executor_prompt(system_prompt,
  description)` prepends it to the task for CLI executors (§4h — never
  `AGENTS.md`). `_run_executor(...)` calls `executor.run(job, cwd=<clone>,
  prompt=…, model_id=<bare id>, sandbox=settings.codex_sandbox_default —
  tightened to `read-only` for `privilege_class: read-only` skills,
  timeout_s=resolve_session_timeout(...))`; any `terminal_reason != "ok"`
  raises `ExecutorFailed(provider, model_id, terminal_reason, message,
  model_served=)`. Non-Anthropic lanes NEVER get `delivery.env_files`
  provisioned, never `sync_canonical`, and their clone is KEPT (audit
  `note`) for the T5 pre-push Anthropic gate. `interrupt(job_id)` falls
  through to the executors' `interrupt` when no SDK session holds the job
  (INV-8). The Anthropic path is behaviourally identical apart from the
  additive fields. `resolve_session_timeout` + `SESSION_TIMEOUT_CAP_SECONDS`
  moved here from `main.py` (same code; `main` re-exports both) so the
  executor branch shares the ceiling without a `session → main` import.
- `src/runner/main.py` — `_terminal_values(...)` (pure) + `_finish_job(...,
  provider=, terminal_reason=, model_served=)` stamp the migration-007
  columns only when known; the completed path stamps from the result dict,
  `ProviderRefused` stamps `provider` + `terminal_reason=provider_refused`;
  new `except session_mod.ExecutorFailed` handler ahead of the generic
  `except` — `job_failed error_category=<terminal_reason>`, stamps
  provider/terminal_reason/model_served, task DM, **no escalation** (a
  vendor switch is a routing decision this slice does not make; T6 adds
  the `rate_limited` hold + front-requeue).
- `src/audit_log.py` — docstring: `provider_selected` kind; additive
  fields on `job_started`/`job_completed`; executor terminal reasons as
  `job_failed.error_category` values. Existing kinds untouched (C14).
**Tests**: `tests/test_provider_dispatch.py` (53: each refusal as a pure
predicate and through `run_session` with a fake executor behind
`_EXECUTORS` and a captured DB stamp; precedence + reason; Codex branch
call shape, audit sequence, marker parse, no env_files / no sync / clone
kept; `ExecutorFailed`; `interrupt` fall-through; Anthropic path unchanged;
`main` AST + `_terminal_values`). `tests/test_models_registry.py::
test_session_refuses_enabled_provider_without_executor` now empties
`_EXECUTORS` to keep its rule under test (codex has an executor since T4).
**Review (code-review T4, 2026-10-21) applied before commit** — one major,
two minors: (a) **No Anthropic escalation off a non-Anthropic lane, on any
failure path.** Main's `wait_for` timer starts before skill resolution and
the clone, so with equal deadlines it always won over the executor's own
`timeout_s`; the resulting `asyncio.TimeoutError`, and a pre-process
`CodexNotFound`/`ValueError` from `executor.run`, fell into the generic
branches of `_process_job` and `_maybe_escalate` re-ran the job on the
skill's Anthropic `on_failure` model. Now: `main._non_anthropic_lane(job)`
(pure read of the `resolved_provider` stamp the session writes before the
process starts) guards both the `asyncio.TimeoutError` and generic
`Exception` branches — refetch first, then `_finish_job(..., provider=,
terminal_reason="timeout"|"api_error")`, audit `note`, no escalation; an
unstamped job (died before the stamp) keeps the old escalation path.
`session._run_executor` converts `FileNotFoundError` (incl. `CodexNotFound`)
and `ValueError` from `executor.run` into `ExecutorFailed(provider,
model_id, "api_error", …)` (plus an `executor_error` audit) so pre-process
infrastructure failures take the typed terminal path; and the executor's
`timeout_s` is `session.executor_timeout_s(ceiling)` = ceiling −
`EXECUTOR_TIMEOUT_MARGIN_S` (30 s), floored at `EXECUTOR_TIMEOUT_FLOOR_S`
(30 s), so its own `timeout` terminal reason is reachable (main's deadline
stays the backstop). (b) The unrelated `.claude/settings.local.json` hunk
is not staged. (c) GOTCHAS + plan T5 note: `_maybe_review` is a
`stale_head` no-op for Codex jobs until T5 commits/syncs. Tests 53 → 63
(`executor_timeout_s`; pre-process errors → `ExecutorFailed`;
`_non_anthropic_lane`; `_process_job` driven with faked collaborators:
codex timeout and codex generic exception never escalate and stamp the
typed reason, Anthropic timeout and unstamped failure still escalate).
**Not in this task**: the pre-push review gate + runner commit (T5),
per-provider quota keys (T6), surfaces (T7).

## 2026-10-21 — T3: the Codex executor (`src/runner/executors/codex_cli.py`)

**Agent task**: cross-vendor writer slice T3
(`docs/superpowers/plans/2026-10-21-cross-vendor-writer-slice.md` §5; old
spec §2.4 JSONL mapping, §2.6 EnvScrubber contract).
**Files changed**:
- `src/runner/executors/__init__.py` (new) — package for non-Anthropic
  executor adapters; re-exports `ExecResult`.
- `src/runner/executors/codex_cli.py` (new) — `run(job, *, cwd, prompt,
  model_id, sandbox, timeout_s, on_event, process_factory=…) -> ExecResult`
  and `interrupt(job_id)` (SIGTERM → SIGKILL after `KILL_GRACE_S=1.5`,
  INV-8). One `codex exec --json --ephemeral --ignore-user-config
  --skip-git-repo-check --sandbox <read-only|workspace-write> -C <clone>
  -m <id> -c features.goals=false -c analytics.enabled=false
  -c otel.metrics_exporter="none" -c sandbox_workspace_write.network_access=false
  -o <audit_log_dir>/<job_id>.codex-last.md <prompt>` per job, `stdin=DEVNULL`
  (plan §4d), env = `scrubbed_env()` = exactly `{PATH, HOME, LANG, TMPDIR,
  CODEX_HOME}`. `settings.codex_run_as_user` set → argv prefixed `sudo -n
  -u <user> --preserve-env=<allowlist> --`. Binary: `settings.codex_bin`
  (must exist) → `shutil.which("codex")` → the ChatGPT.app bundle path →
  `CodexNotFound`. `EventMapper` maps the JSONL stream onto the EXISTING
  audit kinds (`tool_use` Bash/Edit/WebSearch, `tool_result`, `text`,
  `thinking` — C14 shapes unchanged, `tool_result` gains `exit_code` +
  `output`) plus three new kinds `executor_started`, `turn_completed`,
  `executor_error`; `default_sink` audits every event and publishes a
  compact view on `jobs:stream:<id>` like `session._handle_message`.
  Terminal reasons: `ok | rate_limited | auth_expired | api_error | timeout
  | interrupted`; no `turn.completed` ⇒ `api_error` whatever the exit code
  (the silent-empty-success trap). Final text of record = the `-o` file,
  fallback the last `agent_message` (plan §4i). Never commits, pushes,
  writes `AGENTS.md`, or accepts `danger-full-access`. NOT wired into
  `run_session` yet — T4 adds the dispatch branch; nothing runs Codex today.
- `src/config.py` — `codex_run_as_user: str = ""` (env `CODEX_RUN_AS_USER`,
  D-C; unset by default).
- `src/audit_log.py` — docstring lists the three new kinds and the two
  additive `tool_result` fields; existing kinds untouched (C14).
- `tests/test_codex_executor.py` (54, new) + fixture
  `tests/fixtures/codex/file_change_and_failure.jsonl` (hand-authored,
  labelled so in its header; `ok`/`command_and_file` are recorded truth).
  Pure/fixture style: a process factory is injected — no live `codex`, no
  network, no SDK.

**Review (code-review T3, 2026-10-21) applied before commit**:
- `run()` wraps the consume/wait block in `except BaseException` that
  terminates the child (SIGTERM → SIGKILL) before re-raising — a sink that
  raises (`audit_log.append` on a full disk) or a stream line over
  `_STREAM_LINE_LIMIT` no longer orphans `codex exec`.
- Stale `-o` guard: `out_path.unlink(missing_ok=True)` before the spawn, and
  the `-o` file is only the text of record once `turn.completed` was seen
  (job ids are reused on requeue; a `TASK_COMPLETE:` from a previous attempt
  must not pair with this attempt's `terminal_reason`).
- D-C run-as-user: `codex_run_as_user` now REQUIRES `codex_home` (else
  `ValueError` before any process) and forwards the stream home as `HOME`,
  `TMPDIR=<codex_home>/tmp` and `CODEX_HOME` — never the owner's HOME or
  0700 TMPDIR. `scrubbed_env` gained a `tmpdir=` override. Still NOT
  delivered: clone readability for the unprivileged user (the
  `volumes/workspaces/` clone is `drwx------`; materialisation unbuilt) —
  D-C stays an owner-gated residual, plan §6/§7.4 amended.
- `classify_error` uses word-bounded regexes (`\b429\b`, `\b401\b`,
  `\blog(ged)? in\b`): "140123 input tokens" / "plugin" no longer classify
  as rate_limited / auth_expired (T6 parks the lane on those classes).
- `ExecResult.model_served` is None when the stream never reported a model
  (was: defaulted to the requested id) — T4 stamps `jobs.model_served` from
  observation only; T10 canary to assert.
- `probe_cli_version` terminates a hung `--version` process in a `finally`.
- `build_argv` refuses a prompt beginning with `-` (clap would read it as a
  flag; no unverified `--` separator added — T10 may verify one).
- Tests: `tests/test_codex_executor.py` 54 → 67 (sink-raises, stale `-o`,
  `-o` without `turn.completed`, run-as-user stream home + required
  `codex_home`, hung probe, classify negatives, `model_served` observed-only,
  `-`-prompt refusal).

## 2026-10-21 — T1: job model resolved through the models registry (fail-closed)

**Agent task**: cross-vendor writer slice T1
(`docs/superpowers/plans/2026-10-21-cross-vendor-writer-slice.md` §5).
**Files changed**:
- `src/config.py` — `router_providers_enabled: str = "anthropic"`,
  `router_code_server_providers: str = "anthropic"`, `codex_bin: str = ""`,
  `codex_home: str = ""`, `codex_sandbox_default: str = "workspace-write"`.
  Fail-closed defaults; flipping them is the owner's call (plan §7).
- `src/runner/session.py` — `_resolve_model(payload, skill_cfg) ->
  ModelRef` (pure): `payload.model > skill.model > settings.default_model`,
  resolved via `registry.models.resolve_enabled`; raises `ProviderRefused`
  on an unknown id (C12), a provider outside `router_providers_enabled`, or
  a provider with no executor in this runner (`_EXECUTABLE_PROVIDERS =
  {anthropic}` — interim until T4 adds the dispatch branch). `run_session`
  calls it right after `_resolve_skill`, BEFORE the deploy gate and the
  workspace clone, so a refusal never leaves a clone behind or reaches the
  SDK; `_build_options` uses `ref.model_id` — the same bare Anthropic id as
  before, so the Anthropic path is behaviourally identical.
  `_MODEL_BUDGETS` is now `registry.models.context_windows()`.
- `src/runner/main.py` — `_process_job` handles `ProviderRefused`
  terminally: audit `provider_refused{provider, model, raw, reason}` +
  `job_failed error_category=provider_refused`, task notified, NO
  escalation (a policy refusal would re-refuse on a bigger model).
- `src/audit_log.py` — docstring lists the `provider_refused` kind and
  `job_failed.error_category`; existing kinds untouched (C14).
**Why**: T0's review found `job.payload["model"]` reached the SDK
unvalidated (a stale client or old schedule payload could still name the
retired Haiku id), and the slice needs one place that says which provider
a job belongs to before T4 can dispatch on it.
**Tests**: `tests/test_models_registry.py` §9–10 (precedence, retired id,
unknown pin, disabled provider, enabled-without-executor, unknown default,
AST check that the main handler fails the job and never escalates).
`tests/test_context_budget.py`, `tests/test_haiku_retirement.py` unchanged
and green.

## 2026-10-21 — T0: Haiku 4.5 retirement; utility classifiers read `settings.utility_model`

**Agent task**: cross-vendor writer slice T0
(`docs/superpowers/plans/2026-10-21-cross-vendor-writer-slice.md` §5) — retire
the hard-coded `claude-haiku-4-5-20251001` pin whose retirement window opened
2026-10-15 while it was still being served by the two fail-open classifiers.
**Files changed**:
- `src/config.py` — new `utility_model: str = "claude-sonnet-4-6"` and
  `utility_effort: str = "low"` (env-overridable like `default_model`).
- `src/runner/llm_router.py` — `llm_route` builds `ClaudeAgentOptions` with
  `model=settings.utility_model, effort=settings.utility_effort`; docstrings
  no longer name Haiku.
- `src/runner/learning.py` — `extract_learning` likewise; docstrings updated.
- `src/runner/router.py` — docstring wording only.
- `src/runner/session.py` — `_MODEL_BUDGETS` drops the Haiku row (sonnet row
  already present; `_DEFAULT_BUDGET` covers unknown ids unchanged).
**Why**: both classifiers fail open (router → generic task, learning →
`had_learning=False`), so a retired model would have silently degraded routing
and learning capture with no job failure to notice. One setting replaces three
literals so the next swap is a `.env` change, not a code change.
**Tests**: new `tests/test_haiku_retirement.py` (no retired literal under
`src/` or skill docs; settings defaults; both classifiers' options carry the
setting and follow an override — SDK `query` monkeypatched, no network; alias
table; dashboard; budget row). Full suite 1500 passed, 1 skipped.
**Side effects**: none on the job path — `default_model` and every skill pin
are untouched. `skills/project-update-poll/SKILL.md` moves to
`claude-sonnet-4-6`. Review fix (same commit): `test_skill_contracts` now
reads the repo's own `skills/` via `registry.skills.list_all(skills_dir)`
(see registry CHANGELOG 2026-10-21) instead of `settings.skills_dir`, so the
plain `pipenv run pytest -q -p no:cacheprovider` is green from the dev
checkout; the `PIPENV_DONT_LOAD_ENV=1` workaround in
`.context/modules/runner/skills/GOTCHAS.md` still applies to anything else
that reads through `settings.server_root`. The two `llm_route` tests also
patch `src.registry.skills.list_all` so the catalog build is
filesystem-independent.

## 2026-10-10 — session: raise SDK transport buffer ceiling to 20 MiB

**Files created**: none
**Files changed**: `src/runner/session.py` (`_build_options` sets
`kwargs.setdefault("max_buffer_size", 20 * 1024 * 1024)` just before
constructing `ClaudeAgentOptions`).
**Why**: implements proposal
`0f3b5acc-3e44-4dc0-a5f2-4b736bf89b85`. The Claude Agent SDK's
`subprocess_cli` transport buffers each JSON message from the bundled
Claude CLI in memory before yielding it; its
`_DEFAULT_MAX_BUFFER_SIZE = 1024 * 1024` (1 MiB) is overridable only via
`ClaudeAgentOptions.max_buffer_size`, which `_build_options` never set.
Three recent long-running sessions overflowed that cap and died with
`JSON message exceeded maximum buffer size of 1048576 bytes` in the last
48 h: alpha-governor jobs
`8d848d17-2df7-4e41-9de6-9d0f504d69b5` and
`4bce7355-59a1-415e-8c6b-5822543b8b13`, and alpha-research job
`3c7c8c56-a580-4e26-a048-e1e7845bbb67`. Lifting the ceiling to 20 MiB
accommodates realistic ToolResult payloads (large diffs, grep outputs,
file reads) without unbounded growth.
**Side effects**: every session now runs with a 20× larger per-message
buffer. The buffer is per in-flight JSON message, not retained, so peak
memory impact per session is bounded by the largest single message the
CLI emits. `setdefault` leaves the knob overridable per payload / skill
in the future.
**Gotchas discovered**: `ClaudeAgentOptions.max_buffer_size` must be an
int; `None` falls back to the SDK default (confirmed via
`inspect.signature` — annotation `int | None`, default `None`). The
cap is enforced in `claude_agent_sdk/_internal/transport/subprocess_cli.py`.

## 2026-10-05 — writeback: classify agent-config dirs as docs

**Files created**: `tests/test_writeback.py` (17 new cases).
**Files changed**: `src/runner/writeback.py` (added `.codex/agents/`,
`.agents/`, `.claude/agents/` prefix checks and an `AGENTS.md` comment in
`_is_doc_path()`).
**Why**: implements proposal `a164301b-34ed-497c-a9db-98a6522de454`. Over
the preceding 30 days, 5 of 23 `_writeback` jobs (21.7%) failed with
`max_turns=20` exhaustion; all 5 parents were atlas-repo sessions whose
`git status` consistently showed `.codex/agents/*.toml`, top-level
`AGENTS.md`, and `.agents/skills/*.md` as the only modified paths. The
classifier treated those as code, so the runner kept spawning writeback
jobs on diffs that are entirely agent-config documentation. Bucketing them
with the existing `/skills/` heuristic stops the false-positive dispatches
at the source. Top-level `AGENTS.md` was already matched by the top-level
`.md` rule; the new tests pin that behavior so a future refactor cannot
regress it silently.
**Side effects**: fewer `_writeback` jobs will be dispatched. Sessions
whose ONLY modifications are agent-config files will no longer trip the
"needs writeback" check — but those files are configuration documents, not
code, so the CHANGELOG rule doesn't apply to them anyway. If a session
mixes agent-config edits with real code changes, the real code still
triggers writeback as before.
**Gotchas discovered**: nested `.codex/agents/` under a project (e.g.
`projects/atlas/.codex/agents/x.toml`) is NOT caught by the new rules —
only top-level prefixes match. That's intentional: when the server-repo
session has a project nested writable, the project's own config files are
project code, and the project's own CHANGELOG should record them.

## 2026-09-23 — mcp_dispatch: normalize dispatched job kinds

**Files created**: none
**Files changed**: `src/runner/mcp_dispatch.py` (+`_normalize_kind` pure
helper; called in `enqueue_job_tool` right after `_validate_enqueue_args`
returns clean, before the DB write / queue push), `tests/test_mcp_tools.py`
(+`TestNormalizeKind` class, 9 cases).
**Why**: implements proposal `abd0a223-44e9-4b8c-9a65-02be7458bcfc`. The
runner already normalized at skill-resolution time (`session.py:_resolve_skill`
— underscored kinds still ran the correct skill), but the DB stored the raw
`kind` from the LLM, so 30-day rollups split each skill into two buckets
(`server_deploy` 17 + `server-deploy` 3 = 20 real runs, `deploy_director` 17
+ `deploy-director` 17 = 34, etc.). The prior docstring-only fix (commit
6781f31, 2026-09-12) didn't move the needle — 15/17 subsequent
`server_deploy` dispatches still came in underscored. This normalizes at
dispatch time so `jobs.kind` has one canonical hyphenated spelling per skill
going forward. Existing rows keep their raw kinds; underscored buckets fade
naturally.
**Side effects**: none observed. Retrospective/rollup queries by
`Job.kind` see fewer synthetic splits; downstream consumers that already
handled either spelling continue to work. Historical rows unchanged (no
migration).
**Gotchas discovered**: the proposal's example test case for
`_learning_apply` (→ `_learning-apply`) would have broken skill resolution
because the on-disk skill directory is literally `skills/_learning_apply/`
and `session.py:_resolve_skill` leaves `_`-prefixed kinds untouched.
Implementation mirrors `session.py:_resolve_skill` verbatim instead:
kinds starting with `_` pass through unchanged (documented in the helper's
docstring and the test `test_leading_underscore_kind_passes_through_verbatim`).
Renaming `skills/_learning_apply/` → `skills/_learning-apply/` is out of
scope; internal-`_` kinds are enqueued only by the runner itself
(`main._verify_writeback`, `main._spawn_evaluate`, `learning.maybe_extract_and_enqueue`),
never by LLM MCP dispatch in practice, so this is theoretical.

## 2026-09-23 — events: idle-queue alpha drainer (flywheel)

- **Agent task**: alpha-flywheel implementation (owner-approved spec
  2026-09-23-alpha-flywheel-design.md), interactive owner session.
- **Files changed**: `src/runner/events.py` (+`_should_trigger_idle_alpha`,
  `_check_idle_queue_alpha`, constants ALPHA_IDLE_COOLDOWN_HOURS=4 /
  ALPHA_DAILY_JOB_VALVE=12; wired into event_loop beside the idle review
  check, breaker-exempt), `tests/test_events.py` (+TestIdleQueueAlpha, 7
  cases).
- **Why**: turn idle queue hours into flywheel hours — enqueue an
  alpha-governor (payload project_slug atlas) when the queue is empty, the
  last completed governor is ≥4h old, and alpha-research jobs in 24h are
  under the valve mirroring budget.yaml's 12/day.
- **Side effects**: up to ~5 extra governor runs/day on quiet days (each
  no-ops cheaply on a quiet vertical); any queued job suppresses the
  trigger so every other loop wins by construction.
- **Gotchas discovered**: none new; the valve constant intentionally
  duplicates the atlas-side budget (server code must not parse atlas repo
  files) — if the owner changes budget.yaml, revisit ALPHA_DAILY_JOB_VALVE.

## 2026-09-14 — router: alpha rule moved to top of _RULES (final review)

Final whole-branch review verified live that the plan-decomposer rules
("and then", "then also") hijacked "alpha:"-prefixed ideas containing
those connectives. The anchored alpha rule now runs first — it can
shadow nothing (^ anchor). Two regression cases added.

## 2026-09-14 — router: alpha-lab intake rule

Added anchored rule `^alpha( idea)?:` → `alpha-intake` (before the
coding-intent rules; anchored so "research alpha decay…" keeps routing to
research-report). Part of the alpha-lab vertical
(docs/superpowers/plans/2026-09-14-alpha-lab-implementation.md).

## 2026-09-12 — mcp_dispatch: fix `enqueue_job` kind example to use hyphens

**Agent task**: apply review-and-improve proposal 2f214c24 from
retrospective f4e2fdea (idle-queue, 30d window).

**Files changed**: `src/runner/mcp_dispatch.py`.

**Why**: the `enqueue_job` tool's Annotated `kind` description showed
`'research_report'` and `'app_patch'` (underscored), which actively coached
LLM sessions to enqueue underscore-form kinds. The runner normalizes at
`session.py:634` so execution works, but the Job row is stored with the
underscore form, fragmenting every kind-based aggregate: rows table showed
deploy_director 31 vs deploy-director 22; server_deploy 26 vs server-deploy
0; atlas_redeploy 13 vs atlas-redeploy 10; server_patch 3 vs server-patch
14 over the last 30 days. Swapping the two examples to
`'research-report'`, `'app-patch'` steers new sessions to the canonical
hyphenated form. Docstring-only; behaviour unchanged.

**Side effects**: none. `_validate_enqueue_args` still accepts any
non-empty string. The deeper enqueue-time normalization
(`src/gateway/jobs.py`) remains stuck proposal 2f4f34c1, flagged out of
scope by the retrospective.

**Gotchas discovered**: none.

## 2026-09-03 — session._build_options: log effective ClaudeAgentOptions (INV-1 observability)

**Files changed**: `src/runner/session.py`.

Added a single `logger.info` at the tail of `_build_options` recording the
resolved job id, skill, model, effort, `max_turns`, and `permission_mode`.
The existing `job_started` audit event carries model / effort / isolation
but omits `max_turns` and `permission_mode`, so an SDK-side termination
like `error_max_turns: Reached maximum number of turns (N)` used to leave
no trace of what the SDK was actually configured with. Root case: on
2026-09-01, `_writeback` job `f6c9e375-376f-423f-9566-40a686131f60`
failed with N=6 while the *current* `SKILL.md` says 10 — the 6 → 10 bump
(commit `12a7851`) landed on 2026-09-02, so at run time SKILL.md really
was 6. Diagnosing that required git-archaeology on the SKILL.md history
because nothing in the audit log said "SDK max_turns=6". Pure additive
observability — the returned `ClaudeAgentOptions` and every existing test
expectation are unchanged.

## 2026-09-01 — schedule-adherence monitor: the missing-run axis (firm WS1)

**Files changed**: `src/runner/schedule_adherence.py` (new),
`tests/test_schedule_adherence.py` (new), `scripts/schedule-monitor.sh`
(new), `scripts/install-launchd.sh`.

`schedule_rollup` grades runs that exist; nothing noticed a schedule that
silently stopped producing runs (08-17 governor-dark: scheduler-task death
looks healthy; scout-never-ran: a row that never fired sorts as fine). New
pure fold `adherence_report(schedules, jobs, now)` → findings
DARK / NEVER_RAN / STUCK / FAILURE_STREAK + per-schedule status rows;
schedule_id join, never kind (2026-08-17 review doctrine). CLI main writes
`volumes/telemetry/schedule_adherence.json` (consumed by atlas firm
`liveness.py`, spec 2026-09-01-atlas-firm-org-design). Out-of-band delivery:
`scripts/schedule-monitor.sh` on launchd timer `com.assistant.schedule-monitor`
(daily 07:15 local) — the scheduler must not watchdog itself — with the
healthcheck-all curl-DM idiom, 12h alert rate limit, Sunday always-summary.
Artifact shape: `{generated_at, findings[], schedules[{name, cron, paused,
status: ok|paused|dark|never_ran|failing|stuck, last_expected,
observed_job_at}]}`. First live run 2026-09-01: 33 schedules, 0 findings.
Review catch (same day, INV-13 pass): status overwrites now run in
ascending severity (failing → stuck → dark/never_ran) so a hung job is
never downgraded to "failing" by a coincident streak; overlap test added.

## 2026-08-31 — review catches on the F1 hardening (same session)

The INV-4 code-review pass on the remediation diff found two real holes:

- **BLOCKER — `POST /api/jobs` was a third god door**: `web.create_job`
  passed `req.kind` through unvalidated, so any unisolated skill able to
  read `WEB_AUTH_TOKEN` could post `kind=god`. Now 403s with a pointer to
  Telegram /god (`tests/test_web_god_gate.py`).
- **MAJOR — corrupt SUBAGENT frontmatter killed the parent**:
  `agents.build_subagents` didn't catch the new `SkillFrontmatterError`, so
  one broken subagent skill (e.g. the exact unquoted-`:` class just fixed)
  would fail every parent that lists it (19 skills list subagents). Now
  skipped with a warning, matching the function's contract.

## 2026-08-31 — F2 queue honesty: slot-before-BLPOP, stranded-queued healing, honest /health, launchd-aware run.sh, status constraint (EVALUATION_2026-08-30)

**Files changed**: `src/runner/main.py`, `src/runner/reconcile.py`,
`src/gateway/web.py`, `scripts/run.sh`,
`alembic/versions/006_job_status_constraint.py`, tests.

- **Job loop acquires a semaphore slot BEFORE `BLPOP`** (new
  `_run_with_held_slot`). Previously ids were popped eagerly and parked on
  in-process semaphore waiters — a runner death lost every waiting id from
  Redis while rows stayed `queued` in Postgres forever (observed live:
  Redis LLEN 0 vs 15 PG-queued).
- **`reconcile.requeue_stranded_queued()`** (startup, after orphan
  reconciliation): re-RPUSHes every `queued` row absent from Redis; audit
  event `queued_requeued`. Pure helper `stranded_queued_ids`.
- **`/health`**: `queue_depth` is now the Postgres queued count (was Redis
  LLEN alone — reported 0 with 15 queued). New fields `redis_llen`,
  `pg_queued`, `pg_running`, `pg_deferred`. Health verdict logic unchanged.
- **`run.sh`**: when `com.assistant.*` launchd units are loaded, `status`
  reports launchd truth (was: PID files → "not running" while everything
  ran) and `start` refuses (was: would bind :8080 against live uvicorn).
- **Migration 006**: maps the illegal `status='succeeded'` row (wrote by a
  session via SQL; its 3 deferred children stranded 8 days because
  promotion only recognises `completed`) to `completed`, fails any other
  unknown status, and adds CHECK `ck_jobs_status_valid`.

## 2026-08-31 — F1 hardening: fail-closed skill contracts, tighten-only isolation, dispatch guards (EVALUATION_2026-08-30)

**Agent task**: interactive remediation of `docs/EVALUATION_2026-08-30.md` F1.

**Files changed**: `src/registry/skills.py`, `src/runner/session.py`,
`src/runner/workspaces.py`, `src/runner/mcp_dispatch.py`,
`src/runner/main.py`, `src/gateway/telegram_bot.py`,
`tests/test_registry_failclosed.py` (new), `tests/test_workspaces.py`.

- **Registry fails closed**: corrupt SKILL.md frontmatter now raises
  `SkillFrontmatterError` instead of silently running the skill on registry
  defaults (full toolset, acceptEdits, isolation none). `list_all()` skips
  corrupt skills with an ERROR log. Three atlas skills (atlas-chat,
  atlas-k401-review, atlas-portfolio) had unparseable descriptions (unquoted
  `"name: arg"` trigger text) and ran defaulted for weeks — descriptions now
  block-scalar quoted.
- **`session._resolve_skill` raises `SkillResolutionError`** (terminal, not
  escalated — new handler in `main._process_job`, error_category
  `skill_contract`) when an explicit kind's skill is missing or corrupt, and
  when a router match resolves to a corrupt skill.
- **`workspaces.resolve_isolation`**: payload may only TIGHTEN isolation
  (anything → workspace). Payload `host`/`none` relaxation is ignored with a
  warning; unknown tiers fail closed to `workspace` (was `none`).
- **Generic unmatched task** (`kind=task`, no skill contract) is forced onto
  the guarded `workspace` tier (audit event `isolation_forced`). Owner host
  work goes through /god.
- **Dispatch MCP**: `enqueue_job` rejects `kind='god'` (owner-invoked only,
  via Telegram /god) and strips `isolation`/`permission_mode`/`permission`
  from dispatched payloads (logged). Telegram `/task --kind=god` is rejected
  with a pointer to /god.
- **Gateway**: httpx logger raised to WARNING (one INFO line per 10s
  getUpdates long-poll had grown bot.err.log to ~46MB, F7.3).

## 2026-08-23 — Second variant of session_id collision bug documented (`_learning_apply` preflight rejection)

**Agent task**: self-diagnose — escalation `b8767cb3` for failed `_learning_apply` job `46acc317` (parent 18257848). Root cause is the known `Session ID … is already in use` bug (TROUBLESHOOTING.md §468), but this instance widens the diagnosis: the first attempt was **preflight-rejected** by quota (`rate_limit_status: rejected` → `job_requeued_for_quota`) BEFORE any Claude work ran, and yet the SDK subprocess still created the session file on disk. When the retry fired ~1h37m later, it collided. Unlike the atlas-report variant (48ad692d), no deliverable existed to salvage. Remediation: manually appended the intended PATTERN entry to `.context/modules/runner/skills/PATTERNS.md`, updated TROUBLESHOOTING.md to note the preflight-rejection variant + `_learning_apply` failure mode. Fix still requires server-patch (Phase 5): rotate `session_id` on any requeue (quota preflight OR post-work `QuotaExhausted`), or short-circuit-on-`already-in-use` in `session._run_in_process`. Total `Session ID … is already in use` hits in `runner.err.log` still 22 (this incident is entry #22).

## 2026-08-21 — API-terminal sessions reclassified as failed (was silently completed)

**Agent task**: server-patch — job 143c8cfb (atlas-evaluate, 2026-08-17 13:48Z)
ran ~200s, produced zero output, and recorded status=`completed` with a summary
that was literally "API Error: 529 Overloaded. This is a server-side issue,
usually temporary — try again in a moment. If it persists, check
status.claude.com." Because the job did not fail, `escalation.on_failure`
never fired, no self-diagnose was enqueued, the schedule's `last_run_at`
looked healthy, and the Telegram completion card looked normal. The atlas
governor was silently dark for 10 days as a result.

**Files changed**:
- `src/runner/session.py` — three pure classifiers (`is_api_terminal_summary`,
  `usage_is_empty`, `is_api_terminal_session`) + a raise in `_run_in_process`
  when the completed-shape session matches BOTH signals (banner AND empty
  usage). The RuntimeError falls into the existing `_process_job` exception
  path, which fails the job and calls `_maybe_escalate` — engaging the
  skill's on_failure retry (opus/xhigh) and, if that also fails, the L1→L2
  self-diagnose escalation.
- `tests/test_api_terminal.py` — 37-case regression suite that pins the
  verbatim (summary, usage) pair from job 143c8cfb, exercises 5xx / timeout
  / overloaded / overloaded_error / internal_server_error / api_error
  banner shapes, and confirms conservative behaviour (4xx does NOT match,
  long summaries that lead with the phrase do NOT match, banner-with-real-
  usage does NOT match).

**Why the SDK let this through**: the bundled Claude CLI, on an Anthropic
5xx or timeout, emits the failure as a plain `TextBlock` inside an
`AssistantMessage` and returns a `ResultMessage` whose `usage` dict is
all-zero and whose `is_error` is not usefully set. The existing
"is_error AND no text" fallback (session.py) therefore never triggered —
there WAS text (the banner). Now we look at the two-signal shape
independent of `is_error`, and raise before the caller records
`job_completed`.

**Why "conservative" matters**: the classifier requires BOTH the banner
shape AND all-zero usage. A skill that legitimately produces a summary
mentioning "API error" (e.g. a self-diagnose report on this very
incident) does NOT trigger — the banner regex is anchored at start-of-
string with a 800-char cap, and any tokens consumed disqualifies the
call. A skill that hit a genuine API 5xx on its FIRST turn (empty usage)
DOES trigger, which is exactly the escalation-eligible shape.

**Side effects**: none for the happy path. Sessions that used to be
recorded as `completed` while dying on Anthropic 5xx / overloaded /
request-timed-out now record as `failed` with `error_category="quota"`
(the classifier in `audit_index.categorize_error` maps "overloaded"
to quota — semantically adjacent, and does NOT trip queue-pause because
pause is only triggered by `QuotaExhausted`, not by category labels).
Escalation and self-diagnose paths engage automatically.

**Gotchas discovered**: the SDK's `ResultMessage.is_error` is not a
reliable "did this session actually succeed?" flag for Anthropic-side
5xx — it can be False (or unset) even when the CLI has already printed
its own error banner as text. Any future "did the session succeed?"
logic has to look at the SHAPE of the final text + usage, not just at
`is_error`. Added to `.context/modules/runner/skills/GOTCHAS.md`.

**Verify**: `POSTGRES_DSN=<dummy> pipenv run pytest tests/` — 1182 passed,
1 skipped, 2 warnings. `tests/test_api_terminal.py` — 37 passed.

## 2026-08-21 — event-trigger dedup: filter by Job.kind not Job.resolved_skill

**Agent task**: fix duplicate self-diagnose spawning during the 20-min window
between an event-triggered enqueue and the runner picking that job up.

**Files changed**:
- `src/runner/events.py` — `_check_skill_failures` + `_check_project_health`
  dedup queries now filter existing self-diagnose jobs by `Job.kind ==
  "self-diagnose"` (set at INSERT by `enqueue_job`) instead of
  `Job.resolved_skill == "self-diagnose"` (NULL until the runner starts the
  job).
- `tests/test_events.py` — two new regression tests
  (`TestSkillDiagnose::test_queued_diagnose_with_null_resolved_skill_still_dedups`,
  `TestProjectDiagnose::test_queued_diagnose_with_null_resolved_skill_still_dedups`)
  that construct queued-shape dicts with `resolved_skill=None` and confirm
  the pure functions still dedupe.

**Why**: on 2026-08-21 06:34–06:36Z a single cadence-slip false-positive on
`healthcheck-all` spawned SIX duplicate self-diagnose jobs (three per project)
for baseball-bingo + atlas. Root cause: the DB dedup query keyed off
`Job.resolved_skill`, which the runner only populates when it *starts* running
a job. While a self-diagnose sat queued, the next 60-s event cycle couldn't
see it and re-enqueued. Filtering by `Job.kind` — set at INSERT and never
NULL — closes the window. This is recurrence #92 of the well-known "project
'X' unhealthy 20+ min but actually up" false positive (docs/TROUBLESHOOTING.md
line 1175); the live-probe gate proposed there is a separate (still
un-landed) prevention. This patch only fixes the duplication amplifier.

**Side effects**: none — the query is strictly widened to include the same
jobs it always meant to include (queued + running + terminal self-diagnose
jobs in the dedup window). No caller changed.

**Gotchas discovered**: `enqueue_job(kind=...)` writes the raw string into
`Job.kind`; the `JobKind` enum has `self_diagnose = "self_diagnose"`
(underscore), but every event/escalation callsite passes `"self-diagnose"`
(hyphen). The stored value is the hyphenated string — the enum is not the
source of truth for dedup filters. Anyone adding a new event-trigger dedup
query must match the hyphenated literal.

**Verify**: `POSTGRES_DSN=<dummy> pipenv run pytest tests/` — 1145 passed, 1
skipped, 2 warnings. `tests/test_events.py` — 46 passed (2 new).

## 2026-08-11 — per-job session-timeout override (payload.session_timeout_seconds)

**Files changed**: `src/runner/main.py`, `src/gateway/web.py`,
`scripts/seed-schedules.sh`, `tests/test_pure_functions.py`.

**Why**: the 30-minute global ceiling killed three consecutive
atlas-momo-research cycle-2 attempts (jobs 1ff5ec9a stream-timeout,
bd9d04a1 + escalation 4ccd3a01 both `session_timeout` with real work
unpushed). Heavy governed lab cycles legitimately need more; the ceiling
itself must survive.

**Fix**: `resolve_session_timeout(payload, default, cap=5400)` — payload
override clamped to [60, 5400], garbage falls back to the default. Web API
gains the optional `session_timeout_seconds` field (validated ge=60 le=5400);
the momo schedule row now carries 3600 so Thursday's run benefits.

**Verify**: `pipenv run pytest` — 1104 passed (6 new).

## 2026-08-10 — workspace env-file provisioning (delivery.env_files)

**Files changed**: `src/runner/workspaces.py`, `src/runner/session.py`,
`tests/test_workspaces.py`, (registry: `src/registry/manifest.py`,
`tests/test_manifest.py`).

**Why**: `git clone` doesn't carry gitignored files, so a workspace-tier
session never saw owner-provisioned credentials — atlas cycle #1 reported
"No `.env`/credentials exist in this workspace" even after the owner put the
Alpaca keys in `~/Documents/repos/atlas/.env` exactly as instructed. The
Thursday `atlas-momo-research` run would have hit the same wall.

**Fix**: projects opt in via manifest `delivery.env_files: [".env"]`;
`workspaces.provision_env_files` copies each declared file from the canonical
into the clone right after `create_workspace` (wired in `run_session`, where
the delivery contract is already resolved). Copied entries are audited on
`workspace_created.env_files`. Containment: relative in-repo paths only —
absolute/`~`/`..` rejected at manifest validation AND by the runner-side
`env_file_violation` belt; symlink sources refused (a repo symlink could
otherwise smuggle a host file into the session-readable clone). Never raises;
missing sources are skipped so the consumer fails with its own message.
Code-review hardening (same day): resolve-containment on BOTH ends — the
reviewer reproduced a symlinked-parent bypass (`sub/.env`, `sub` → host dir)
that passed the final-component check; src must resolve inside the canonical
and dst inside the workspace (dst-side symlinks also refused, else copy2
writes through a committed symlink to a host path).

**Verify**: `pipenv run pytest` — 1098 passed (13 new).

## 2026-08-07 — session timeouts now escalate (timeout branch was a silent dead end)

**Files changed**: `src/runner/main.py`, `tests/test_timeout_escalation.py` (new).

**Why**: `_process_job`'s `asyncio.TimeoutError` handler failed the job and
returned without `_refetch_job` + `_maybe_escalate` — every session timeout,
for every skill, produced no escalation retry and no level-1 self-diagnose.
Found live by the first `atlas-momo-research` smoke run (job `d21b5498`,
timed out at the 30-min ceiling; its declared opus-5/xhigh escalation never
spawned). Same missing-post-step class as the 0/516 post_review bug.

**Fix**: timeout branch now mirrors the generic failure branch (refetch →
escalate, exception-guarded). New hermetic AST contract test pins all three
awaits (`_finish_job`, `_refetch_job`, `_maybe_escalate`) in the handler.

**Verify**: `pytest tests/test_timeout_escalation.py` (3 passed) + full suite.

## 2026-08-05 — post-review resurrected (0/516 → live) + escalation refetch

**Files changed**: `src/runner/main.py`, `src/runner/review.py`,
`tests/test_review.py`, `scripts/seed-schedules.sh`.

Found by the closed-loop arc's own code review (three rounds — the first two
rounds' more ambitious "review gates the deferred deploy child" design was
scoped OUT after review kept finding holes in the deep promotion-ordering
surgery it required; the deploy is already gated by the builder's in-session
`code-review` subagent + `atlas_redeploy`'s pytest gates, so post_review
stays a SECOND belt that flags, exactly like app-patch/server-patch).

1. **post_review had NEVER fired — 0 of 516 jobs** (INV-13's second belt was
   dead since inception): `_maybe_review` read `job.resolved_skill` off the
   ORM instance loaded BEFORE `run_session`, but the session stamps
   `resolved_skill` via a separate DB session — the detached instance never
   sees it, so `skill_name` was always `None` and the review returned early.
   Fix: `_process_job` refetches the Job row right after `_finish_job(
   completed)`; every resolved_skill-keyed post-step (review, writeback
   gate, learning gate) now sees the stamped value. Same refetch on the
   FAILURE path so level-0 `escalation.on_failure` reads the real skill
   (it was silently jumping to self-diagnose for task-kind jobs).
2. **Wrong-diff guard**: reviewing `HEAD~1` is wrong when the workspace's
   `sync_canonical` ff failed (routine on a dirty/diverged dev clone) or the
   session committed nothing — the review would grade someone else's commit.
   `review.head_commit_epoch` + `is_stale_head` (pure, tested): HEAD older
   than `job.started_at - 120s` → skip with audit event
   `post_review_skipped` (reason=stale_head or no_diff).
3. **`post_review.reviewer_model`/`reviewer_effort` were dead keys**
   (reviewer hardcoded opus-4-7 for everyone): `run_code_review` takes
   optional `model`/`effort`, wired from the skill's post_review dict;
   defaults unchanged.
4. **post_review FLAGS, it does not park** (the design the review rounds
   converged on): activating post_review surfaced that the old
   blocker→`awaiting_user` park was buggy dead code — it published a SECOND
   `jobs:done` after the completion DM already fired (owner told "completed"
   on a blocker), stranded task state, and let writeback/learning run on a
   parked diff. And it bought nothing: the review runs AFTER the code is
   committed/pushed, so parking can't un-merge — the real merge gate is each
   skill's IN-SESSION `code-review` subagent before the push. So
   `_maybe_review` now stamps `review_outcome` (job stays `completed`), and
   on blocker/error emits a `post_review_flagged` audit event + a
   `review_flagged` task DM (new additive branch in telegram_bot's
   tasks:notify consumer). Surfaced by `review_outcome` in /status, the
   retrospective, and the weekly manager sweep. No `awaiting_user`, no
   task-advance skip, no double-publish.
5. **Reviewer is FIXED (opus-4-7/high), not skill-chosen**: `run_code_review`
   dropped the `reviewer_model`/`reviewer_effort` passthrough — a skill must
   not be able to downgrade the reviewer that grades its own diffs.
   atlas-build's frontmatter reviewer keys were removed (they were the only
   caller trying to set them).
6. **`_refetch_job` helper** dedupes the identical post-session refetch used
   by both the success and failure paths (one place to change the refresh
   semantics).
7. **seed-schedules.sh**: every upsert value is a psql bound variable
   (`-v n/c/k/d/p/nx`) inside a quoted heredoc (nothing bash-expands — a
   payload with a quote or `$()` can no longer break seeding); empty
   next-slot → NOW() via `COALESCE(NULLIF(:'nx','')::timestamptz, NOW())`;
   new `job_payload` column carried via `COALESCE(EXCLUDED.job_payload,
   schedules.job_payload)` so out-of-band scoping survives re-seeds.

Deliberately NOT changed (reviewed across four rounds and scoped out):
promotion ordering is untouched — `promote_deferred_for` runs
unconditionally on completion as before; the deploy child is dispatched
immediately by atlas-build (no `depends_on`-on-review); `session.py`,
`plans.py`, `workspaces.py` are unchanged from HEAD (an earlier round's
"review gates the deferred deploy child" machinery — ReviewGate,
blocks_dependents, retained-workspace review, promotion reorder,
fail_taskless_dependents — was fully reverted: it required deep
promotion-ordering surgery that kept generating bugs, and the deploy is
already gated by the in-session review + the executor's test gates).
post_review runs under `_POST_REVIEW_TIMEOUT_SECONDS` (600s) — now that it
actually fires, a hung reviewer sub-agent can't pin a concurrency slot while
/health stays green; a timeout is an audited skip, not a verdict. The
reviewed diff is the canonical checkout's `HEAD~1` (unchanged, pre-existing):
the `is_stale_head` guard rejects an OLDER foreign HEAD but not a NEWER one,
so on the multi-writer atlas canonical a foreign commit landing between the
build's push and the ff-sync can be mis-graded — low harm now that
post_review only FLAGS (a rare mis-stamp the evaluator/owner dismisses),
never gates. Failure-path escalation now reads the real `resolved_skill`, so
a failed atlas-build escalates into a stronger-model REBUILD (its own resume
check completes-transitions-only on already-pushed work, so no duplication)
instead of a read-only self-diagnose — an improvement.

Follow-up backlog: task-less deferred dependents of a terminally-failed job
aren't cascade-failed (pre-existing, unrelated); a task-less job flagged by
post_review has no chat_id so its `review_flagged` DM is dropped — the audit
event + review_outcome still record it, and the weekly atlas-evaluate now
reads `review_outcome` for each build to surface a flag as a backlog item.

**Verify**: `pipenv run pytest tests/test_review.py -q` (25 passed;
TestStaleHeadGuard covers the wrong-diff guard); full suite green; after the
next deploy, `psql assistant -c "SELECT review_outcome, count(*) FROM jobs
WHERE resolved_skill IN ('app-patch','server-patch','atlas-build') GROUP BY
1;"` should start showing non-NULL outcomes (the 0/516 symptom clears).
## 2026-08-03 — P4/P5 phase continuation: max_turns root-cause confirmed, two server-patch jobs dispatched (job `2e92aaae`)

**Files changed**: `.context/modules/runner/skills/GOTCHAS.md` (root-cause diagnosis appended),
`docs/superpowers/plans/2026-07-28-management-hierarchy.md` (P4/P5 status updated).
**Why**: Investigation of the "Continue to the next phase of the plan" task. Confirmed root cause
of the server-patch workspace-push meta-bug: `max_turns: 60` is exhausted by context-reading +
coding + test-running before the session reaches the commit/push phase. Job `5dfebb42` hit exactly
60 tool_use events during tests (no commit). Job `2bfb6d20` committed on turn ~59 and used its
last turn to invoke code-review — 0 turns left to execute step 8A merge/push. Dispatched two
follow-up server-patch jobs: `388681d6` (max_turns fix, PR mode — protected path) and `98e3eb75`
(P5 management surfaces: /proposals command + dashboard rollup, autonomous merge lane).
**Side effects**: P4 (guards.py privilege guardrails) remains blocked until `388681d6` PR is
merged and deployed; then a new server-patch for P4 can complete within the increased turn budget.

## 2026-08-03 — Second server-patch attempt also failed to land; baseball-bingo diagnose #44 (job `a629fb94`, ~18:23Z)

**Files changed**: `.context/modules/runner/CHANGELOG.md` (this entry) +
`.context/modules/runner/skills/GOTCHAS.md` (occurrence tick). No code
touched. Baseball-bingo `/healthz` returned 200 in ~1ms, uvicorn PID 71682
up 3d14h, `projects.last_healthy_at` = 54s stale (fresh) at diagnosis
time — same cadence-slip false positive as the previous 43 baseball-bingo
recurrences (88 total across atlas+bingo). **Critical**: the second
server-patch attempt `2bfb6d20-dedf-43a1-96dd-ce36e3a35956` (completed
2026-08-03 12:55Z) ALSO failed to land on origin/main — `git log
origin/main -- src/runner/events.py` still shows `197f239` as the latest
touch. Audit summary shows the session wrote the patch, added 13 passing
tests, updated CHANGELOG, and was about to trigger code-review, but no
commit ever reached origin. Two consecutive server-patch attempts have
now produced no on-disk change; the fix is being re-lost each time. Not
re-dispatching from this diagnose — pattern indicates a defect in the
server-patch skill's commit/push handoff (workspace GC before push, or
code-review sub-agent returning without merging back). Recommend human
review of the server-patch skill flow before spending a third Opus
session on the same fix. Concurrent atlas twin `fa287ee8` running in
same dispatch window (queued-but-unresolved dedup race still open).

## 2026-08-03 — Fiftieth false-positive self-diagnose + prior server-patch never committed (baseball-bingo, ~12:41Z, job `61e9de7d`)

**Files changed**: `docs/TROUBLESHOOTING.md` only. Baseball-bingo answered
`/healthz` 200 in 17ms and `/` 200 in 6ms on port 8790, uvicorn PID 71686
healthy. DB `last_healthy_at` was 20m38s stale at diagnosis due to another
`healthcheck-all` cadence slip (12:21:07Z → 12:41:41Z, four missed ticks);
natural launchd tick refreshed it 3s after this diagnose picked up.
Concurrent atlas twin `7a19aaf7` running in the same dispatch window —
queued-but-unresolved dedup race still active. **Critical finding**:
prior server-patch `5dfebb42` (dispatched at the 49th recurrence) DID
edit `src/runner/events.py` and DID add 6 passing tests to
`tests/test_pure_functions.py`, but the session ended without committing
or pushing — `workspace_synced` recorded only `canonical fast-forwarded
from origin`, no local commits existed, and `git log origin/main --
src/runner/events.py` still shows `197f239` as the latest touch (pre-patch).
The workspace was GC'd and the fix is lost. Re-dispatched fresh
`server-patch` job `2bfb6d20-dedf-43a1-96dd-ce36e3a35956` at ~12:44Z with
explicit COMMIT-AND-PUSH-BEFORE-EXIT + INV-13 code-review instructions.
Secondary bug observed but not fixed here: the workspace guard hook
mis-fired on a benign `find` command containing the protected-path
substring — worth tightening the destructive-command classifier.

## 2026-08-03 — Forty-seventh false-positive self-diagnose (baseball-bingo, ~11:53Z, job `db9c2625`)

**Files changed**: `docs/TROUBLESHOOTING.md` only — appended forty-seventh
recurrence of the `events.py:_check_project_health` false positive.
baseball-bingo answered `/healthz` 200 in 4.0ms and `/` 200 in 4.5ms on
port 8790, project PID 71682 healthy. Two back-to-back `healthcheck-all`
cadence slips this window (11:08:32Z → 11:29:06Z, then 11:29:06Z →
11:50:48Z, each ~20-min / four missed 5-min ticks), the second fired the
trigger; natural launchd 11:50:48Z tick had already refreshed
`last_healthy_at` to 2m54s old before this diagnose loaded, so no inline
kickstart needed. Runner behavior unchanged. The `events.py` live-probe
gate + the `healthcheck-all.sh` psql-exit-status surfacing remain the
correct prevention (server-patch, Phase 5) — un-landed after 47
recurrences.

## 2026-08-03 — Forty-second false-positive self-diagnose (atlas, ~09:42Z, job `3e813db1`)

**Files changed**: `docs/TROUBLESHOOTING.md` only — appended forty-second
recurrence of the `_check_project_health` false positive as the atlas twin
of the concurrent baseball-bingo diagnose `daa80e8a` (both fired by the
same event tick, same 08:49:17Z → 09:25:51Z 36-min `healthcheck-all.sh`
slip + a silent psql UPDATE loss on the 09:25:51Z tick that left
`projects.last_healthy_at` at 09:09:21Z despite a `checked=2 healthy=2`
summary). Atlas answered `/` 200 in 43ms on port 8791; all three atlas
launchd processes stayed running (PIDs 24233/81428/81432). No inline
kickstart needed — the natural launchd 09:43 tick self-caught-up.
Runner behavior unchanged. Also noted in TROUBLESHOOTING for follow-up:
a real, unrelated app bug is visible in the atlas project log
(`invalid input syntax for type uuid: "AAPL"` in the Next.js
`/api/atlas/{assets,candles}` routes) — separate from healthcheck and
should be triaged in an atlas deploy, not here. The `events.py`
live-probe gate + a companion fix to stop `psql ... > /dev/null 2>&1`
in `scripts/healthcheck-all.sh` remain the correct prevention
(server-patch, Phase 5).

## 2026-08-02 — Recurring false-positive self-diagnose (bingo, ~17:58Z, job `67d9a2bc`)

**Files changed**: `docs/TROUBLESHOOTING.md` only — appended sixteenth
recurrence of the `_check_project_health` false-positive symptom. Same
`healthcheck-all.sh` cadence-slip signature as the prior fifteen: last
successful tick 17:35:54Z, then a 21-min gap that pushed
`projects.last_healthy_at` past the 20-min unhealthy threshold in
`src/runner/events.py:_check_project_health`. Direct probes returned 200 on
`/healthz`, `/`, and `/static/app.js`; project PID 71682 was healthy;
healthcheck-all had already self-resumed at 17:57:09Z before the diagnose
ran, so no inline kickstart was needed. No server code changed — the
prevention patch (gate the trigger on a fresh direct probe, or trust a
`healthcheck:last_run` freshness key) still requires `server-patch` (Phase
5). Runner behavior unchanged.

## 2026-08-02 — Applied stranded learning + refined `_learning_apply` root cause

**Files changed**: `.context/modules/runner/skills/GOTCHAS.md` — inserted the
"Aged healthcheck timestamp triggers false-positive unhealthy alert" gotcha
(from evidence job `a480b1ee`) that `_learning_apply` job `30d66555`
tried but failed to write when it hit `max_turns:6`. Also updated
`docs/TROUBLESHOOTING.md` with the deeper root cause: `session.py` passes
only `job.description` as the user prompt, so the skill's "Payload you will
receive" section is aspirational — the model never sees `payload.module` and
has to infer it, burning turns before it can Edit. Three fixes proposed
(inline payload into description, append payload block in session.py for
internal skill kinds, or bump max_turns to 10) — all server-code, medium
risk, deferred to server-patch. Diagnosed by self-diagnose job `6c281518`.

## 2026-08-01 — Restored missing APPEND_ENTRIES_BELOW marker in runner/skills/PATTERNS.md

**Files changed**: `.context/modules/runner/skills/PATTERNS.md` — inserted the
standard `<!-- APPEND_ENTRIES_BELOW -->` marker that every other module's
skills/*.md file has. This file pre-dated the seed convention and had never
been re-seeded, which caused `_learning_apply` job `912237f7` to hit
max_turns while the model wandered checking other modules' files instead of
following its own Step 3 fallback ("if the marker is missing, just append at
end"). Also applied the learning that failed job was trying to write (about
`context_files` frontmatter injection, evidence job `64644863`). See
Troubleshooting entry for the failure mode. Diagnosed by self-diagnose job
`f13d03a6`.

## 2026-07-31 — MCP tools joined allowed_tools (the second dispatch blocker)

**Files changed**: `src/runner/session.py` — the MCP injection block now
appends the injected servers' tool names (`mcp__dispatch__enqueue_job`,
`mcp__projects__{list_projects,get_project,read_project_logs,restart_project}`)
to `allowed_tools`, mirroring the Task-tool auto-add. Without it, acceptEdits
sessions had MCP servers but no permission to call them — acceptEdits
auto-accepts EDITS only, and a headless session can answer no permission
prompt. Proven live 2026-07-31: the deploy-director's first autonomous
dispatch attempt ran a clean preflight, prepared the executor description,
and was then denied `enqueue_job` twice. This was the SECOND layer of the
dispatch blocker (the first: plan mode blocks MCP outright) — dispatch had
only ever worked under bypassPermissions, which is also why
review-and-improve's dispatch stayed dead even after its plan→acceptEdits
fix. The readonly guard profile (INV-20) still hook-denies restart_project
for read-only skills; hooks fire before permission evaluation.

## 2026-07-31 — Workspace directive aligned to the execution lane

**Files changed**: `src/runner/session.py` — the injected workspace directive
told every server-scoped session "server code lands via PR + deploy ... never
push to main from here", which contradicted the new autonomous execution lane
(WS-C). It now defers to the skill's declared merge flow: lane-authorized
skills (server-patch/new-skill, post-LGTM + owner notification) may push main;
everything else branches + PRs; protected paths always stop at a PR. No
behavior change outside the directive text.

## 2026-07-31 — Read-only guard profile: oversight skills get structural read-only + dispatch

**Why**: `permission_mode: plan` blocks MCP tools (proven live 2026-07-30 —
deploy-director's enqueue_job unreachable; review-and-improve's dispatch
silently dead for weeks), so dispatch-capable oversight skills must run
acceptEdits — which until now left their read-only-ness prose-only.

**guards.py**: new READ-ONLY profile alongside the workspace profile. Pure
predicates `readonly_file_violation` (Write/Edit/MultiEdit/NotebookEdit denied
outright — no path exceptions, temp dirs included) and
`readonly_bash_violation` (mutation denylist: output redirection except
/dev/null + fd-dups, quote-masked so quoted SQL `>` comparisons pass; file
mutators; git mutators with `git fetch` as the sanctioned refs-only exception;
launchctl mutating subcommands, list/print allowed; alembic
upgrade/downgrade/revision/stamp; dbmate; createdb/dropdb; pip/pipenv
install/uninstall/sync/lock; npm/npx/brew; redis-cli
set/del/push/pop/flush/expire; psql write verbs — statement-start anchored, so
identifiers like `project-update-poll`/`created_at` never false-positive;
sudo/kill/crontab/keychain/API-key hard denials).
`make_readonly_guard_hooks(job_id)` → 3 PreToolUse matchers: file tools, Bash,
and `.*restart_project` (suffix re-checked in-hook); `enqueue_job`
deliberately unmatched. Denials audited `guard_denied` with
`profile: "read-only"`. The guarantee, honestly: file tools structurally
denied; Bash is a best-effort denylist, not a sandbox (SDK Seatbelt stays the
SYSTEM.md-tracked OS-level closure).

**session.py**: `_build_options` attaches the readonly profile whenever
`skill_cfg.privilege_class == "read-only"` — every isolation tier and
permission mode (belt under plan, load-bearing under acceptEdits); read-only
wins over workspace hooks if both somehow apply. Workspace wiring untouched.

**lint**: oversight roles ⇒ read-only + mode ∈ {plan, acceptEdits}; new
role-independent rule: needs-dispatch-mcp + read-only ⇒ acceptEdits.

**Skills**: system-manager + 4 division managers plan→acceptEdits +
needs-dispatch-mcp + dispatch-authority paragraphs; review-and-improve
plan→acceptEdits + privilege_class read-only (matches its charter row) +
gotcha recording the silent-dispatch weeks; deploy-director gotcha updated —
its read-only contract is now hook-enforced, not prose-only.

Tests: tests/test_guards.py +127 (69-entry deny matrix, 37-entry allow matrix
of real oversight command vocabulary, 8 hook-contract); tests/test_doc_lint.py
+6 (rule logic on synthetic trees).


## 2026-07-31 — Event-loop circuit breaker + global (task-less) deferred promotion

**1. Circuit breaker in `src/runner/events.py`** (2026-07-30 incident: ~17
self-diagnose jobs event-spawned into a substrate where self-diagnose itself
was broken — `'Server' object has no attribute 'list_tools'` — each failure
feeding the 2-in-10-min window; only per-target dedup bounded it):
- Pure `should_trip_breaker(recent_failures, threshold=5)`: groups failed
  jobs by normalized error signature (`_error_signature`: whitespace-collapsed
  first 80 chars; None/blank -> "unknown"); any cluster >= threshold returns
  that signature (largest cluster wins, ties lexicographic).
- `_check_circuit_breaker()` runs FIRST each cycle: if `KEY_EVENTS_BREAKER`
  exists -> skip all event-trigger spawning (skill-failure, project-health,
  correlated) but NOT the idle-queue review; one info line per cycle at most.
  On trip: `SET NX EX TTL_EVENTS_BREAKER` (30 min), one error-level log, and
  EXACTLY ONE `self-diagnose` job ("CIRCUIT BREAKER tripped: N failed jobs ...
  share the error signature '<sig>'", `target_kind: circuit-breaker`,
  `created_by: event-trigger:circuit-breaker`) — its completion summary DMs
  the owner via the normal path. The check crashes fail OPEN in the loop's
  non-fatal try/except style; new constants `BREAKER_WINDOW_MINUTES = 10`,
  `BREAKER_FAILURE_THRESHOLD = 5`, `BREAKER_SIGNATURE_LEN = 80`.

**2. Global deferred promotion in `src/runner/plans.py`**: `promote_deferred_for`
early-returned for task-less completing jobs, stranding any task-less
`depends_on` child forever (the limitation deploy-director's SKILL.md works
around). Task-scoped sibling promotion is behaviorally unchanged; the function
now ALSO scans `status='deferred' AND task_id IS NULL` rows (bounded:
`TASKLESS_PROMOTION_SCAN_LIMIT = 200`, oldest first), Python-filters for
`payload.depends_on` naming the completed job (pure `names_dependency`), and
applies the identical flow: `deps_satisfied` over a completed-set covering all
of each candidate's deps, INV-9-guarded deferred->queued UPDATE, RPUSH,
`job_promoted` audit, per-item isolation, never raises. escalation_map is
passed EMPTY on this path — escalation lineage is derived from a task's own
job set and has no task-less equivalent — so a dep satisfied only via a
completed escalation retry does not promote a task-less child (conservative:
under-promotes, never wrongly promotes). NOTE: `main.py` gated the call on
`job.task_id` — that gate was lifted in the integration commit immediately
after this merge, so promotion now fires for every completing job.

Tests: `tests/test_events.py` +23 (signature normalization, breaker boundary/
mixed/empty/None cases, loop gating incl. fail-open), `tests/test_plans.py`
+10 (`names_dependency`, task-less `deps_satisfied` semantics). Full suite
898 passed; lint_docs all-PASS.


## 2026-07-30 — Enqueue visibility race fix (stranded queued jobs) + epoch heartbeat with TTL

**BUG 1 — `_process_job` dropped popped ids whose row wasn't visible yet.**
BLPOP can return a job id before the INSERTing transaction's commit is visible
to the runner's SELECT: `_tick_schedules` RPUSHes *inside* an open transaction
(add → flush → rpush → … commit on scope exit), and even commit-then-RPUSH
producers race the BLPOP by sub-ms. The old code logged "job not found" and
returned — the Redis entry was consumed, the row stayed `status='queued'`
forever. Bit tonight: job e38d0028 ("job not found" at its exact created_at
second; re-pushed by hand).

**Fix (consumer-side, covers every producer)** in `src/runner/main.py`:
- `_process_job` retries the SELECT over ~2s (`_JOB_FETCH_DELAYS` =
  (0.0, 0.2, 0.3, 0.5, 1.0); fresh session per attempt — only a new
  transaction sees a commit that landed after the previous attempt began).
- Still missing → `note_missing_job(id, _requeued_missing_ids)` (deterministic,
  no-I/O helper + module-level set): first miss → RPUSH the id back to the
  queue **TAIL** exactly once; a repeat miss → error-log and drop for good, so
  a truly-deleted row can't ping-pong. The set stays bounded (cleared on found
  and on drop). The requeue RPUSH is guarded per the loop's 2026-07-28 Redis
  try/except hygiene — a Redis blip logs the id instead of raising.
- Found-but-not-queued rows return silently as before (cancel race etc.).

Tests: `tests/test_job_visibility.py` (8 — decision sequences + retry-schedule
contract).

**BUG 2a — heartbeat hardened for off-runner consumers**: `_job_loop` now
writes `KEY_RUNNER_HEARTBEAT` as **epoch seconds** with a **15-min TTL**
(`TTL_RUNNER_HEARTBEAT`, new constant in `src/db.py` beside the key name —
db.py comment updated in the same commit). Epoch so
`scripts/healthcheck-all.sh` can age-check it from bash; TTL so a dead
runner's key disappears instead of sitting stale-but-parsable. Companions:
gateway `/health` parses epoch with ISO fallback (see gateway CHANGELOG);
`scripts/healthcheck-all.sh` gained an independent runner-down Telegram DM
(heartbeat missing/>600s AND no launchd PID for com.assistant.runner; creds
READ from the checkout's .env; one DM per 30 min via a volumes/ state file;
fully guarded so project probes can never be blocked). Closes the liveness
blind spot from the 2026-07-30 incident (runner down ~a day —
docs/TROUBLESHOOTING.md "runner down, launchctl shows no PID with last
exit 0").

## 2026-07-30 — mcp 2.0.0 regression: pin `mcp<2` (dispatch/projects MCP injection broken)

**Incident** (same evening as the runner-down fix, surfaced by the hierarchy's
first pass): every `needs-dispatch-mcp` / `needs-projects-mcp` session failed
with `'Server' object has no attribute 'list_tools'` (review-and-improve + the
two event-triggered self-diagnose jobs — the event triggers' first-ever real
firings, ironically). Cause: claude-agent-sdk 0.1.x pins `mcp>=1.19.0`
with no upper bound; a routine `pipenv lock` on 2026-07-30 pulled mcp 2.0.0,
which removed the 1.x lowlevel `Server.list_tools` API the SDK's
`create_sdk_mcp_server` bridge calls. Last working dispatch-MCP job: 2026-07-28 22:46 (pre-re-lock).

**Fix**: explicit `"mcp<2"` in pyproject dependencies (drop only with the
deliberate SDK 0.2.x migration); both venvs repaired in place with
`pip install "mcp<2"` (mcp 1.28.1) pending the next deploy's re-lock.
Bonus finding: mcp 2.0 in the venv silently suppressed 40 MCP-dependent tests
from collection — the suite is back to full strength (842).

## 2026-07-30 — Runner-down incident: stdlib/structlog logging mismatch + supervisor exit code

**Incident**: prod runner found down (launchctl: no PID, last exit 0) with the
queue stranded. Root-cause chain: `events.py` logs with structlog-style kwargs
on a stdlib `logging.getLogger` logger → `TypeError: Logger._log() got an
unexpected keyword argument 'poll_interval'` the moment `event_loop` starts →
the 2026-07-28 subsystem supervisor correctly shuts the process down — but
`main()` exits **0**, and launchd's `KeepAlive {SuccessfulExit: false}` never
restarts successful exits, so the runner stayed down. Latent since Phase 4
(42ef735): before supervision, the event_loop task died silently at startup,
which also means event triggers had never actually run in production.

**Changes**:
- `events.py` (×4), `retention.py` (×1), `review.py` (×1): structlog-style
  kwargs → %-style stdlib logging. The last two instances (a multiline call in
  events.py and review.py's `code review complete` — INV-13's own machinery)
  were found by the new lint check, not by grep: AST beats regex here.
- `main.main` now returns an exit code (`sys.exit(asyncio.run(main()))`):
  crash path exits 1 so launchd actually restarts a crashed runner — the
  supervision fix's stated intent, previously unreachable.
- Regression test `tests/test_events.py::TestEventLoopStartup` (a pre-set
  shutdown event exercises exactly the startup log line, no DB).
- Lint check 13 `check_logger_style` (scripts/lint_docs.py, AST-based): bans
  structlog-style kwargs on stdlib loggers across src/ — the whole bug class,
  which pure-function tests can't catch because the crash is at log time in
  paths tests never execute.

**Why**: a repo mixing structlog (main, quota) and stdlib logging (everything
else) will keep regrowing this bug unless it's linted structurally.

Closed a cluster of silent-failure paths the 2026-07-28 audit found where a
documented invariant wasn't actually enforced:

- **`main._cancel_listener`** (INV-8): per-iteration try/except + UUID
  validation. A malformed cancel payload (`uuid.UUID("garbage")`) or a
  transient Redis error previously killed the listener permanently while
  `/health` stayed green (only `_job_loop` heartbeats).
- **`main._finish_job`** (INV-9): guards `WHERE status != 'cancelled'` +
  rowcount check, so the cancel-race (cancel lands, then a trailing
  `_finish_job(completed)` resurrects the job) can't overwrite a user cancel.
  `completed→awaiting_user` (review blocker) is still allowed.
- **`main._job_loop`** (M5): `is_paused` + `blpop` are now inside the Redis
  try/except — a Redis blip no longer kills the loop and strands the runner.
- **`main.main`** (M5): supervises the 4 async tasks — if any exits on its own
  (dead scheduler/cancel-listener), it shuts the process down so launchd
  restarts a clean one instead of limping invisibly. (Code-review fix: cancel
  survivors ONLY on the crash path — on graceful SIGTERM `_job_loop` is draining
  in-flight jobs, so cancelling it there would abort running sessions.)
- **`review.run_code_review` + `main._maybe_review`** (INV-13): the review gate
  fails CLOSED. A review that can't run now returns `ReviewOutcome.error` →
  `awaiting_user`, instead of `changes_requested` (which doesn't gate) letting
  an unreviewed diff ship.
- **`plans.promote_deferred_for` / `fail_dependents_of`** (T4): per-item
  isolation — one failed subtask promotion/cascade no longer aborts the loop
  and strands ready siblings.
- **`workspaces._run_git`** (M3): catches `TimeoutExpired` → returncode 124, so
  a hung `git pull --ff-only` in `sync_canonical`'s finally can't turn an
  already-pushed, successful job into a failure that re-runs done work.
- **`config.server_root`** default corrected (`assistant` → `ai-server`) — the
  wrong default silently repointed every volume path when SERVER_ROOT was unset.
- **`audit_log.py`** docstring: `job_completed` writes `usage`+`duration_seconds`,
  not the previously-documented `cost_usd` (none — subscription auth).

Behavioral tests for these land with the fakeredis/DB harness (Batch 4).

## 2026-07-28 — Segregation code-review fixes (Phases A–E)

Addressed the code-review sub-agent's should-fixes (all were latent — they bite
the first dev-repo project, not today's legacy ones):
- **main.py `_maybe_review` / `_verify_writeback`** now resolve the diff cwd via
  `session._resolve_cwd(job, resolved_skill)` (delivery-aware) instead of always
  the runtime clone — otherwise a dev-repo project (which commits to the dev
  repo) would show an empty diff and SILENTLY SKIP the code-review gate.
- **main.py `DeployNeedsApproval`** now fails terminally with an actionable nudge
  instead of parking in `awaiting_user` — there is no deploy-resume path (the
  telegram Approve button completes a task, it does not re-enqueue a deploy), so
  parking would hang forever.
- **`skills/project-redeploy`** fails CLOSED when a project has no
  `delivery.deploy` block or (service/api) empty `services` — a bare pull with no
  restart ships stale code. Fixed the slug example (slug is the projects/ dir
  name, may differ from subdomain — `baseball-bingo` not `bingo`).
- **router.py** `\bredeploy\b.*\batlas\b` → atlas-redeploy so "redeploy the atlas
  dashboard" keeps atlas's bespoke pipeline instead of the generic engine.
- Doc nits: corrected the `_resolve_delivery` docstring (described a runtime
  special-case that never existed) and noted the INV-2 pre-execution-rejection
  exception in SYSTEM.md.

## 2026-07-27 — Generic project-redeploy router rule (segregation Phase C)

**Files changed**: `src/runner/router.py` — added `\bredeploy\b` → `project-redeploy`
AFTER the atlas + server-deploy rules (first-match-wins, so "redeploy atlas" →
atlas-redeploy and "deploy the server" → server-deploy still win; "redeploy
bingo" → the generic engine). "deploy X" phrasings the regex misses fall to the
LLM router via the new skill's description.

**Why**: `skills/project-redeploy/SKILL.md` (new) is the contract-driven deploy
engine that reads a project's `delivery.deploy` block; it needs a routing entry.
`atlas-redeploy` is kept (hard rule: never delete a skill) and remains atlas's
path until atlas's manifest carries an explicit delivery block (Phase E).

## 2026-07-27 — Project delivery enforcement (segregation Phase B)

**Files created**: `src/runner/delivery.py` (contract enforcement: dev-repo
cwd scoping + deploy-authority gate; pure decision fns + fail-open manifest
loader), `tests/test_delivery.py` (24).

**Files changed**:
- `src/runner/session.py` — `_resolve_project(job, skill_name)` resolves the
  session cwd from the project's delivery contract: `topology: dev-repo` scopes
  a NON-deploy session to the canonical dev repo (the separate git thread),
  audited as `project_cwd_resolved`. run_session runs the deploy-authority gate
  BEFORE any work (raises `DeployRefused`/`DeployNeedsApproval`).
- `src/runner/main.py` — `_process_job` catches `DeployRefused` (terminal fail,
  NO escalation — a policy refusal must not retry) and `DeployNeedsApproval`
  (→ awaiting_user + notify).
- `src/runner/guards.py` — git write subcommands (commit/add/rebase/merge added
  to reset/checkout/clean/restore) now count as mutators, so a workspace-tier
  session that reaches into a runtime clone via absolute path
  (`cd <runtime-clone> && git add -A && git commit`) is guard-denied. The
  runtime clone lives under server_root (already a protected root), so no new
  plumbing. Guards bind workspace-tier only → content projects (isolation:none)
  that legitimately commit are unaffected.

**Why**: make the single-writer / deployability rules structural instead of
prose. Combined with dev-repo cwd scoping, the EXISTING workspace guard (denies
writes outside the per-job clone) already prevents a dev-repo patch session from
touching the runtime clone — the git-mutator addition is belt-and-suspenders for
explicit-absolute-path reaches. See
`docs/superpowers/plans/2026-07-27-project-delivery-segregation.md`.

**Side effects**: NONE until a project opts in with a `delivery` block —
legacy/derived manifests resolve to the runtime clone exactly as before. A
deploy job whose project is `deployable:false`/`manual-only` (autonomous) now
fails with a clear contract reason instead of running.

**Gotchas discovered**: the deploy gate raises before `job_started` is logged
(like preflight failures already do) — the `deploy_authority` audit event is the
record. Adding `git add`/`commit` to the mutator set is safe ONLY because it is
gated on a protected-root reference AND guards bind workspace-tier sessions only.

## 2026-07-27 — SDK-native overhaul: container lane removed, guard hooks + subagents + structured outputs

**Files created**: `src/runner/guards.py` (PreToolUse guard hooks — the
container lane's containment duty, now enforced in-process and binding even
under bypassPermissions), `src/runner/agents.py` (SKILL.md → SDK
AgentDefinition compilation; frontmatter `subagents:` → in-session Task-tool
delegation), `tests/test_guards.py`, `tests/test_agents.py`.

**Files removed**: `src/runner/executors.py`, `tests/test_executors.py`,
`Dockerfile.agent` — the `claude -p`-in-docker lane and its image.

**Files changed**:
- `src/runner/session.py` — single execution path (in-process SDK only);
  wires guard hooks for workspace-tier sessions + `agents=` subagents +
  effort validation (`xhigh` is a native SDK value on 0.1.81 — passed
  through, NOT remapped); typed
  rate-limit handling (`RateLimitEvent` → QuotaExhausted, audited as
  `rate_limit_status`); ResultMessage.is_error now fails the job when no
  usable text was produced (parity with the removed container lane).
- `src/runner/workspaces.py` — `resolve_isolation(skill, payload)` (2-arg);
  tiers are `none | workspace | host`; retired `container` maps to workspace.
- `src/runner/quota.py` — `detect_from_rate_limit(info)`: typed detection
  from RateLimitInfo (status/resets_at); string heuristic kept as fallback.
  Retires the "quota detection is heuristic" debt item.
- `src/runner/review.py` — **bug fix**: the reviewer called the nonexistent
  `ClaudeSDKClient.process_message()`; the blanket except turned EVERY review
  into `changes_requested` silently (no LGTM/blocker verdict was ever real).
  Rewritten on `query()` + `output_format` json_schema (verdict enum enforced
  by the SDK; `outcome_from_structured` pure, text parse kept as fallback).
- `src/runner/llm_router.py` / `src/runner/learning.py` — structured outputs
  via `output_format` (+ `route_from_structured` / `proposal_from_obj` pure
  validators); text parsers kept as fallback; router catalog now reads
  `SkillConfig.description` instead of re-parsing YAML per skill.
- `src/runner/main.py` — startup check no longer shells out to
  `claude --version`; verifies no ANTHROPIC_API_KEY + SDK import + bundled
  (or system) CLI presence.
- `src/config.py` — container settings removed (CONTAINER_RUNTIME,
  AGENT_IMAGE, CONTAINER_MEMORY, CONTAINER_CPUS, CLAUDE_CODE_OAUTH_TOKEN);
  stale env vars are ignored (`extra="ignore"`).
- `evals/run.py` — judge ported from `claude -p` subprocess to an SDK
  `query()` call (last CLI shell-out in the codebase).
- `pyproject.toml` — `claude-agent-sdk>=0.1.63,<0.2` (0.2.x exists; upgrade
  is a deliberate follow-up with its own test pass).

**Why**: the mission is Agent-SDK-native on subscription auth. The docker
lane was our only self-managed CLI execution path, was disabled by default
(empty CONTAINER_RUNTIME), and duplicated the SDK lane's audit plumbing.
The SDK's own surface (hooks, agents, output_format, RateLimitEvent,
bundled CLI) now covers everything the lane did, with enforcement instead
of convention. Full rationale: `docs/SDK_MIGRATION_2026-07-27.md`.

**Side effects**: INV-17 redefined (guard hooks instead of containers);
`isolation: container` frontmatter is lint-flagged (runtime still maps it);
sessions that error with no output now FAIL instead of completing empty.

**Gotchas discovered**: `ClaudeAgentOptions.effort` accepts only
low|medium|high|max — the repo's `xhigh` was passing through unvalidated;
hook input keys are snake_case (`tool_name`, `tool_input`); workspace clones
live UNDER server_root, so guard path scans must mask the workspace path
before matching protected roots.

## 2026-07-12 — Push gates injected into workspace directives

**Files changed**: `src/runner/session.py` — both workspace directive
variants (project + server) now carry the push-gate procedure inline:
verify-before-commit, fetch+rebase-before-push, retry-once-then-report,
never force-push. Needed because isolated project sessions load the
PROJECT's CLAUDE.md (not the server's), so the gates must arrive via the
injected directive. Companion doc changes: CLAUDE.md § Git push gates
(server sessions) and PROJECT_PROTOCOL.md Phase 4 (project sessions).

**Why**: today's incidents were both push-procedure failures (unpushed prod
commit; dev push without pull). Convention → enforced procedure in every
surface a session reads.

## 2026-07-12 — P4: hygiene — silent excepts now log

**Files changed**: `src/runner/session.py` (`_publish_stream` debug-logs,
`publish_done` warn-logs), `src/runner/main.py` (audit-index append failures
debug-logged). No behavior change beyond observability — these paths
previously swallowed every exception with `pass`.

**Why**: a lost done-notification or stream drop was undiagnosable.

## 2026-07-12 — P2/P3: plan DAG orchestration, LLM router fallback, text-marker events, acceptance evaluator

**Files changed**:
- `src/runner/plans.py` (new) — plan validation (`validate_plan`, `topo_order`,
  `deps_satisfied` — all pure), DAG spawn (`spawn_plan_jobs`: roots queued,
  dependents deferred), promotion (`promote_deferred_for` — a completed
  escalation retry satisfies its failed original), failure cascade
  (`fail_dependents_of`), drain check (`plan_jobs_remaining`).
- `src/runner/llm_router.py` (new) — the LLM routing fallback the router
  docstring promised since Phase 4: one-turn Haiku pick from the skill catalog
  (may return `plan`); `parse_route_response` is pure + fail-open to generic.
- `src/runner/session.py` — `_resolve_skill` is async and audits every
  `routing_decision` (method=rule|llm|fallback + confidence);
  `extract_text_events` (pure): TASK_COMPLETE / TASK_QUESTION / EVAL_PASS /
  EVAL_FAIL line markers + `<<<TASK_PLAN` JSON block in a session's final text
  are synthesized into audit events runner-side — executor-agnostic (works in
  containers where the host audit log isn't mounted) and race-free (job id is
  also now injected into every non-chat directive).
- `src/runner/main.py` — task lifecycle rework: `task_plan` → validate → store
  on Task → auto-approve (default) spawns the DAG (`plan`/`plan_approval`
  notifies); plan subtasks never auto-continue (DAG drain detection instead);
  `task_complete` → `_evaluate` acceptance job (auto_evaluate default) instead
  of pending_approval; `_evaluate` outcomes: EVAL_PASS auto-closes with
  evidence (`completed` notify + Reopen), EVAL_FAIL spawns a fix round
  (max_eval_rounds=2) then hands to the user; deferred promotion after each
  completion; terminal escalation cascades failure to dependents; review/
  writeback/learning skip all `_`-prefixed internal kinds.
- `src/runner/mcp_dispatch.py` — `create_server(job)`: dispatched children
  inherit task_id/parent_job_id; `depends_on` arg creates deferred jobs.
- `src/config.py` — `llm_router_enabled`, `plan_auto_approve` (true),
  `auto_evaluate` (true), `max_eval_rounds` (2).
- `skills/plan/SKILL.md` (new), `skills/_evaluate/SKILL.md` (new).
- `tests/test_plans.py` (new, 30 tests: plan validation/topo/deps, marker
  extraction, route parsing, triage).

**Why**: "single Telegram ask → decompose → execute → evaluate" was the
mission's core promise; before this, /task mapped to exactly one skill job
and "done" was self-reported.

**Side effects**: tasks now auto-close on evaluator pass (user overrules via
Reopen button); pending_approval remains for auto_evaluate=false and for
evaluator no-verdict edge cases. New audit events: routing_decision,
plan_stored, evaluator_spawned, eval_fix_spawned, job_promoted.

**Gotchas discovered**: dispatch MCP tools must be built per-session (closure)
— a module-level job context would be shared mutable state across concurrent
sessions.

## 2026-07-12 — P1: per-job workspace isolation + container executor + concurrency 4

**Files changed**:
- `src/runner/workspaces.py` (new) — isolation tiers (`none|workspace|container|host`),
  per-job git clones under `volumes/workspaces/`, canonical ff-sync after push,
  cleanup (failed jobs keep theirs), prune helper for server-upkeep.
- `src/runner/executors.py` (new) — container lane: `claude -p --output-format
  stream-json` via docker CLI, mapped to the SAME audit events as the SDK lane;
  runtime/token availability probe; `docker kill` cancel path; OAuth-token-only
  env (ANTHROPIC_API_KEY actively stripped).
- `src/runner/session.py` — run_session resolves isolation, creates workspaces,
  picks the executor, syncs + cleans up after; `_build_server_directive` gained
  workspace/container variants (`canonical_cwd`, `context_root` params);
  `_build_task_context` event-loop hack REPLACED by async prefetch +
  pure `build_task_context(turns, task_id)` — context-load failures now audit
  as `task_context_load_failed` instead of silently losing the conversation;
  `interrupt()` also kills containers.
- `src/registry/skills.py` — `isolation` frontmatter field (default `none`).
- `src/config.py` — `max_concurrent_jobs` 2→4; container settings
  (`container_runtime`, `agent_image`, `container_memory`, `container_cpus`,
  `claude_code_oauth_token`); `workspaces_dir` property.
- Frontmatter: app-patch + project-evaluate → `isolation: workspace`;
  server-patch → `isolation: container` (dead `needs-projects-mcp` tag removed —
  body never used it); god → `isolation: host` (explicit break-glass lane).
- `Dockerfile.agent` (new), `docs/CONTAINERS.md` (new), `.env.example` —
  container lane setup.
- `tests/test_workspaces.py` (new, 17 tests incl. real-git clone/push/sync/
  collision cases), `tests/test_executors.py` (new, 15 tests for command
  construction + stream-json parity parsing).

**Why**: two concurrent jobs shared checkouts (single-writer incidents
2026-07-09) and every session ran bare on the host. Now: code-writing skills
get throwaway clones (collision-proof, blast-radius-contained), the riskiest
automated skill (server-patch) additionally runs containerized when a runtime
is configured, god remains host-native by explicit decision (phone break-glass),
and concurrency rises to 4.

**Side effects**: audit logs gain `workspace_created` / `workspace_synced` /
`workspace_fallback` / `container_started` / `task_context_load_failed` events.
Failed jobs leave their workspace on disk for debugging (pruned after 7 days).
Container lane passes `--model` but not effort (no stable CLI flag) — documented
in docs/CONTAINERS.md.

**Gotchas discovered**: git refuses pushes to a checked-out branch, so
workspaces re-point origin at the canonical's real remote and the canonical is
ff-synced afterward; when a canonical has no remote, sync fetches from the
workspace instead.

## 2026-07-12 — P0: server-deploy routing rules

**Files changed**:
- `src/runner/router.py` — Added `server-deploy` rules (`deploy the server`,
  `server-deploy`, etc.) ABOVE the server-patch rules so a deploy request is a
  pull+gate+restart, never a code-change session. Part of the P0 dev→prod
  pipeline (new skill `skills/server-deploy/`, new `scripts/sync-learnings.sh`,
  hourly `com.assistant.sync-learnings` launchd timer).

**Why**: Production checkout drift was being hand-"rescued" (commits cbbdd02,
8cfbfc6, 60e1e5c). Deploys and learning sync are now first-class, single-writer
topology documented in CLAUDE.md.

**Side effects**: "update the server to..." still routes to server-patch;
"deploy the server" now routes to server-deploy.

**Gotchas discovered**: The runner cannot restart itself synchronously —
server-deploy uses a detached delayed `launchctl kickstart` (see SKILL.md).
## 2026-07-11 — L2 self-diagnose false positive for cancelled sentinel (5ef4d36d)

**Files changed**:
- `docs/TROUBLESHOOTING.md` — New symptom section
  "self-diagnose fires for a god sentinel job that died with exit code 143
  (SIGTERM)" with diagnostic queries and prevention notes.

**Why**: L2 escalation `5f7d8f62` fired for job `5ef4d36d` with
`Error: unknown`. Root cause traced to two-race compound:
(a) Cancel race — the parallel god session `184b480f` (see entry below)
executed `UPDATE jobs SET status='cancelled'` then killed the sentinel PID.
The sentinel's SIGTERM handler in the runner then wrote `job_failed` and
`UPDATE jobs SET status='failed'`, overwriting the cancel. So the DB row
shows `failed` and the escalation logic couldn't tell it was intentional.
(b) Escalation blindness — the L2 spawn path in `main.py` around
L494-L500 doesn't check whether the failure was a user/system cancellation
(exit 143 from `created_by LIKE 'auto-continue:%'` is a strong signal it was).

**Diagnosis only** (medium-server risk, needs server-patch):
1. In the SIGTERM handler, use `UPDATE ... WHERE status != 'cancelled'` so a
   prior cancel is preserved.
2. In the escalation spawn, suppress self-diagnose when the failed job was
   an auto-continue sentinel and died with exit 143.

**Side effects**: None — this session only appended docs.

_Evidence: jobs `5ef4d36d` (sentinel), `184b480f` (killer god), `5f7d8f62`
(this self-diagnose)._

## 2026-07-11 — Live cleanup: killed rogue auto-continue caught in the act

**Files changed**: None (runtime state only).

**Why**: While investigating "check on my last task" (job `184b480f`), I discovered the exact defect documented in the previous entry firing in real time. Job `0651defb` (the diagnostic session) ended with an A/B/C question to the user but emitted no `task_question` event. The runner's `_update_task_after_job` fell through to auto-continue and enqueued job `5ef4d36d` with description `"Continue to the next phase of the plan."` on task `20daab34` ("why are these changes for these last tasks not deploying"). By the time I looked at its audit log, `5ef4d36d` had already `ls`'d `docs/superpowers/plans/`, read `2026-07-10-eval-remediation.md`, checked PR #3, and was preparing to work on Wave 2 of the eval remediation — **on a task that literally asks "why aren't my changes deploying"**. Perfect reproduction of the hijack in the wild.

**Action taken**: `UPDATE jobs SET status='cancelled'` on `5ef4d36d`; killed PID `94785`; `UPDATE tasks SET status='failed'` on `20daab34`. Documenting this reproduction as additional evidence for the fix work (patch `superpowers:brainstorming` to emit `task_question`; patch `_update_task_after_job` sentinel to carry task context).

**Side effects**: One rogue god session cancelled mid-flight before it could commit unrelated code.

## 2026-07-11 — Diagnosis: task-hijack defect (brainstorming + auto-continue)

**Files changed**:
- `.context/modules/runner/skills/GOTCHAS.md` — Added detailed entry
  "Brainstorming clarifying questions get 'Continue to next phase' hijacked"
  documenting a two-part defect discovered while debugging the 2026-07-11
  baseball-bingo redeploy tasks.

**Why**: Investigation of user question "why are these changes for these last
tasks not deploying" traced back to two combined failures:
(1) `superpowers:brainstorming` asks clarifying questions but never emits a
`task_question` audit event, so the runner never enters `awaiting_user`;
(2) the auto-continue sentinel `"Continue to the next phase of the plan."`
carries no task context, so the next job reads `MEMORY.md` and continues
whatever plan it finds there — silently swapping the user's actual task for
an unrelated one. Evidence: tasks `b59375a8`, `3bfb65aa`; jobs `137c27eb`,
`1681307a`, `2867bcd7`. No code changes made in this session — this is a
diagnosis-only writeup documenting the defect for a follow-up fix.

**Side effects**: None (documentation only).

## 2026-07-11 — T12 cleanup: remove stale "route skill fallback" claim from router.py docstring

**Files changed**:
- `src/runner/router.py` — Removed never-implemented "LLM fallback via route skill" claim from module docstring. Routing has always been rule-based; unmatched descriptions run as generic tasks. Docstring now matches reality.

**Why**: Documentation inconsistency found in T12 audit pass (EVALUATION_2026-07-10).

## 2026-07-09 — Narrow sentinel-only loop guard (code-review fix)

**Files changed**:
- `src/runner/main.py` — Removed `_is_auto_continued` from the loop guard condition.
  The guard now fires only when the job description IS the sentinel string exactly.
  The previous check (`created_by.startswith("auto-continue:")`) was too broad: any
  auto-continued job that did genuine work and emitted no signal would be stopped at
  `pending_approval`, preventing tasks with 3+ phases from ever reaching phase 3.
  Sentinel-only detection is sufficient because the sentinel job never emits task signals.
- `tests/test_pure_functions.py` — Added `TestAutoContineGuard` (7 cases) and 6
  atlas-redeploy router test parametrize entries.

**Why**: Code review of PR #2 identified the over-broad guard as a BLOCKER.
528 tests pass.

**Side effects**: Multi-phase tasks with 3+ phases now work correctly. Any job whose
description matches the sentinel exactly is still stopped. Any job auto-continued from
the sentinel but doing real work is no longer stopped.

**Gotchas discovered**: None new.

## 2026-07-09 — Auto-continue loop guard in _update_task_after_job

**Files changed**:
- `src/runner/main.py` — `_update_task_after_job` now checks before spawning a
  continuation job: if the finishing job's description IS the auto-continue sentinel
  (`"Continue to the next phase of the plan."`) OR the job was itself created by
  `auto-continue:*`, it stops and moves the task to `pending_approval` instead of
  spawning another continuation. This breaks the infinite loop that occurred when
  single-shot skills (e.g. `atlas-redeploy`) completed without emitting `task_complete`.
- `src/runner/router.py` — Added `atlas-redeploy` routing rules: patterns
  `\bredeploy atlas\b` and `\batlas[- ](redeploy|deploy|restart|update)\b` now resolve
  to the `atlas-redeploy` skill so its system prompt (including `task_complete`
  instructions) is loaded.

**Why**: `/task redeploy atlas` had no router rule → `atlas-redeploy` skill never loaded
→ no `task_complete` signal → auto-continue loop spawned jobs forever. Eight stuck
`active` tasks and three looping sentinel jobs observed in production on 2026-07-09.
See `docs/TROUBLESHOOTING.md` §"web dashboard active task list shows completed jobs"
for the full diagnosis and fix procedure.

**How to verify**: `python3.12 -m pytest tests/ -q` — 515 pass.

## 2026-07-06 — Runner liveness heartbeat

**Files changed**:
- `src/runner/main.py` — `_job_loop` writes `KEY_RUNNER_HEARTBEAT` (Redis) with the
  current ISO timestamp on every iteration. The loop ticks ≤2s normally (BLPOP timeout)
  and keeps ticking while jobs run in the background, so a fresh value means the runner
  is alive. Non-fatal on Redis error.

**Why**: Feeds the meaningful `GET /health` (gateway) and the external heartbeat Worker
(`ops/heartbeat-worker/`) so a dead runner is detectable from off-box. See gateway +
db CHANGELOGs for the same day.

**How to verify**: `redis-cli get heartbeat:runner` returns a recent timestamp while the
runner is up.

## 2026-07-06 — Startup reconciliation of orphaned 'running' jobs

**Files changed**:
- `src/runner/reconcile.py` (new) — `reconcile_orphaned_jobs()` + pure helper
  `orphaned_job_ids()`. On startup, any job still `status='running'` is a leftover
  from a process that died mid-job; each is marked `failed` with a terminal
  `job_failed` audit event (`error_category='orphaned'`).
- `src/runner/main.py` — call `reconcile_orphaned_jobs()` in `main()` after the auth
  check, before starting the loops. Non-fatal on error.
- `src/runner/audit_index.py` — `categorize_error()` now recognises `orphaned` (matches
  "startup reconciliation"/"orphaned") and documents it in the taxonomy.
- `tests/test_orphaned_jobs.py` (new) — 6 pure-function tests.

**Why**: The per-job timeout (`session_timeout_seconds`) only guards jobs the *current*
process runs. A runner killed mid-job (crash, SIGKILL, `launchctl stop`, power loss)
left its Job row in `running` forever — violating INV-2 (missing terminal event) and
making the job look perpetually in-flight to self-diagnose/upkeep. Reconciliation writes
the missing terminal event on next boot.

**Design**: Fail-only, no auto-requeue — a job may have had side effects before the
crash; blindly re-running could double them. **Idempotent**: reconcile checks the job's
audit log for an existing terminal event first — if none, it synthesises `job_failed`
and fails the row; if one already exists (the rare crash *between* writing the event and
committing the DB update), it reconciles the row to that recorded outcome without writing
a second event. This keeps INV-2 at exactly one terminal event across repeated restarts.
Each reconciled job also updates the incremental audit index (mirrors `_finish_job`).

**New invariant**: INV-15 — runner reconciles orphaned `running` jobs on startup before
consuming the queue. Added to `.context/SYSTEM.md`.

**How to verify**: insert a row with `status='running'`, restart the runner, confirm it
flips to `failed` with a `job_failed` audit event categorised `orphaned`;
`pipenv run pytest tests/test_orphaned_jobs.py`.

**Side effects**: None on normal operation (no `running` rows at a clean startup → no-op).

**Files changed**:
- `src/runner/main.py` — Added `_preflight_check()`: validates skill
  resolution (inherits from task if router doesn't match), CWD existence.
  Rewrote `_maybe_escalate()` as a 3-level chain: L1 = higher model/effort,
  L2 = self-diagnose with full audit context, L3 = max-effort last resort.
  Level 3 failure notifies user via tasks:notify.
- `src/runner/session.py` — `format_task_turns()` now expands the last
  assistant turn to 8000 chars (the plan). `_build_task_context()` adds
  explicit "Your instructions for this turn" section with user's last reply.
- `.context/SYSTEM.md` — Added `runner.router` to main.py deps.

**Why**: Continuation jobs were losing context (routed wrong, wrong model,
plan truncated). Failures had no recovery path beyond a single retry.
Now: pre-flight catches misconfigs instantly, continuations inherit their
parent skill, and failures escalate through 3 levels before giving up.

## 2026-04-20 — Router fix: app-patch pattern for project-level requests

**Files changed**: `src/runner/router.py` — Added pattern matching
`fix/update/patch/add/modify/change/upgrade` + `app/project/site/dashboard/page`
so requests like "update the bingo app to add login" route to app-patch.

**Why**: "Update the baseball bingo app..." was falling through to generic
task (no skill resolved) because the existing patterns required technical
nouns like `function`, `endpoint`, etc.

## 2026-04-20 — Multi-turn task interaction with approval flow

**Files changed**:
- `src/runner/session.py` — Added `format_task_turns()` pure helper and
  `_build_task_context()` which loads prior turns from DB and injects a
  "Task conversation" section into the system prompt for continuation jobs.
  Added `_fetch_task_turns()` async helper.
- `src/runner/main.py` — Added `_update_task_after_job()` which runs after
  task-linked jobs complete. Records assistant turns, detects `task_question`
  and `task_complete` audit events, updates task status, and publishes
  notifications via `tasks:notify` Redis channel.

**Why**: Jobs were one-shot with no way to respond to output or approve
completion. Tasks now wrap jobs into multi-turn conversations where the
user can reply and the system continues with full context.

**Side effects**: Every task-linked job now triggers `_update_task_after_job`
after completion (non-fatal). Jobs without `task_id` are unaffected.

## 2026-04-20 — Skill consistency: sections lint, post_review standardization, template

**Files changed**:
- `scripts/lint_docs.py` — New `check_skill_sections()` (8th lint check).
  Non-internal skills must have `## Gotchas` section and body >= 10 lines.
- `skills/TEMPLATE.md` (NEW) — Reference template for skill authors.
  Documents required frontmatter fields, required body sections (Inputs,
  Procedure, Quality gate, Gotchas), optional sections, and conventions.
- `skills/new-skill/SKILL.md` — References TEMPLATE.md as first step.
- `skills/app-patch/SKILL.md`, `skills/new-project/SKILL.md`,
  `skills/new-skill/SKILL.md`, `skills/project-evaluate/SKILL.md` —
  Added explicit `reviewer_model` + `reviewer_effort` to post_review config.
- `skills/code-review/SKILL.md` — Added `## Gotchas` section (was missing).

**Why**: Skill bodies were structurally inconsistent. No template for new
skill authors. Post-review config was implicit except for server-patch.
New lint check catches structural gaps early.

**Side effects**: New lint check (8th) runs on every invocation. Skills
missing Gotchas will be flagged — code-review was the only one.

## 2026-04-20 — Debugging: error categorization, incremental index, failure correlation

**Files changed**:
- `src/runner/audit_index.py` — Added `categorize_error()` pure function
  that classifies error messages into categories (quota, auth, timeout,
  tool_error, network, import_error, schema, unknown). Added
  `error_category` field to `IndexEntry`. Added `append_to_index()` for
  incremental index updates without full rebuild.
- `src/runner/main.py` — `job_failed` audit events now include
  `error_category`. `_finish_job()` calls `append_to_index()` after every
  job completion/failure for real-time index freshness.
- `src/runner/events.py` — Multi-skill failure correlation: if 3+ different
  skills fail within 5 minutes, enqueues a single combined self-diagnose
  with `target_kind: multi-skill` instead of N separate diagnoses.
- `.context/SYSTEM.md` — Added `runner.audit_index` to runner.main deps.

**Why**: Error messages were unstructured text — no aggregation possible.
Audit index was stale between nightly rebuilds. Multi-skill failures
triggered redundant diagnoses instead of surfacing shared root cause.

**Side effects**: Every finished job now appends to INDEX.jsonl (~1ms).
New `error_category` field in audit events and index entries.

## 2026-04-20 — Feedback loops: unified MCP tags, escalation, parent tracking

**Files changed**:
- `src/runner/session.py` — Removed `_NEEDS_PROJECTS_MCP` and
  `_NEEDS_DISPATCH_MCP` hardcoded sets. MCP injection now uses frontmatter
  tags as sole source of truth. Added `parent_job_id` field to `job_started`
  audit log events for child jobs (enables cross-job tracing without DB).
- `skills/review-and-improve/SKILL.md` — Added `needs-projects-mcp` tag
  (was hardcoded only).
- `skills/server-upkeep/SKILL.md` — Added `needs-projects-mcp` tag.
- `skills/server-patch/SKILL.md` — Added `needs-projects-mcp` tag.
- `skills/app-patch/SKILL.md` — Added `escalation.on_failure` (Opus 4.7 / xhigh).
- `skills/new-skill/SKILL.md` — Added `escalation.on_failure` (Opus 4.7 / max).

**Why**: MCP opt-in had a dual source of truth (hardcoded sets + tags).
Now tags-only — single source, auditable in each SKILL.md. app-patch and
new-skill previously hard-failed with no retry; now escalate on failure.
Parent_job_id in audit events enables log-only causality tracing.

**Side effects**: Skills that relied on the hardcoded sets but lacked tags
would break — all 4 have been updated with the correct tags.

## 2026-04-20 — Knowledge surfacing: seed module skills + auto-inject + context_files validation

**Files changed**:
- `.context/modules/runner/skills/GOTCHAS.md` — Seeded with 5 entries from
  Troubleshooting.md and CHANGELOG gotchas (audit_log.append collision,
  _writeback false positives, stuck jobs, SDK version mismatch, import lint).
- `.context/modules/runner/skills/DEBUG.md` — Seeded with 2 entries (8-step
  failure triage order, quota false positive detection).
- `.context/modules/gateway/skills/GOTCHAS.md` — Seeded with 2 entries
  (Telegram done-listener mapping, dashboard 404).
- `.context/modules/hosting/skills/GOTCHAS.md` — Seeded with 5 entries
  (cloudflared TLS, config location, plist args, Python modules, TCC).
- `.context/modules/hosting/skills/DEBUG.md` — Seeded with 2 entries
  (runner restart checklist, cloudflared no connections).
- `.context/modules/db/skills/GOTCHAS.md` — Seeded with 2 entries
  (sqlalchemy.update collision, never edit migrations).
- `src/runner/session.py` — Added `parse_skill_file_entries()` pure helper
  and `_module_knowledge_context()` function. Server-scoped sessions now
  get a "Known issues" section with GOTCHAS/DEBUG entry titles for
  detected modules.
- `src/registry/skills.py` — Added context_files validation at load time.
  Logs warning for missing files.
- `scripts/lint_docs.py` — New `check_context_files_exist()` (7th check).
  Validates all skills' context_files reference real files.
- `skills/idea-generation/SKILL.md` — Removed nonexistent
  `projects/ideas/README.md` from context_files (caught by new lint check).

**Why**: Module skill files were empty stubs — zero institutional knowledge
visible to sessions. Now seeded from Troubleshooting.md + CHANGELOG
gotchas, auto-injected into directives, and context_files are validated.

**Side effects**: Server-scoped sessions mentioning specific modules now
get a slightly larger directive (entry titles only — compact). New lint
check (7th) runs on every lint invocation.

## 2026-04-19 — Tool-use audit in code review (Rec 15)

**Files changed**:
- `src/runner/review.py` — Added `_summarize_tool_usage()` helper that
  reads the parent job's audit log and produces a compact tool-count
  summary (Read: N files, Edit: N, etc.). `run_code_review()` now appends
  this summary to the review prompt. Updated `REVIEW_SYSTEM_PROMPT` to
  include an "Approach" section in the output format.
- `skills/code-review/SKILL.md` — Added Approach section to output format
  description.

**Why**: Per § 7 Rec 15. Code review previously only evaluated the diff.
Now the reviewer also sees how the session arrived at the diff (tool usage
patterns), enabling process quality feedback.

**Side effects**: Every code review that has a parent job ID now reads
the parent's audit log (~1ms overhead). The review prompt is slightly
longer.

## 2026-04-19 — Audit log index (Rec 9)

**Files changed**:
- `src/runner/audit_index.py` (NEW) — `rebuild_index()` builds
  `volumes/audit_log/INDEX.jsonl` from all JSONL audit logs. One line
  per job: `{job_id, skill, model, effort, status, error_first_line,
  keywords}`. `search_index()` queries the index by skill, status, or
  keyword. `build_index_entry()` and `_extract_keywords()` are pure
  and unit-tested.
- `skills/self-diagnose/SKILL.md` — Added audit log index search step
  before drilling into individual logs.
- `skills/server-upkeep/SKILL.md` — Added step 2b to rebuild the index
  during daily upkeep.

**Why**: Per § 7 Rec 9. Self-diagnose previously had to scan individual
audit logs to find similar past failures. The index provides O(1) lookup
by skill/status/keyword.

**Side effects**: `volumes/audit_log/INDEX.jsonl` is created/overwritten
on each rebuild. Not append-only — safe to delete and rebuild.

## 2026-04-19 — Context budget accounting (Rec 8)

**Files changed**:
- `src/runner/session.py` — Added `estimate_context_tokens()`,
  `context_budget_fraction()` pure helpers and `_MODEL_BUDGETS` map.
  `run_session()` now emits `context_budget_used` audit log event with
  estimated tokens, model budget, and fraction before starting the session.
- `src/runner/retrospective.py` — Added `ContextBudget` dataclass,
  `parse_budget_events()` and `aggregate_context_budgets()` pure helpers,
  and `context_budget_report()` function. Walks audit logs for
  `context_budget_used` events and aggregates by skill.
- `src/audit_log.py` — Documented `context_budget_used` event kind.

**Why**: Per § 7 Rec 8. Skills with oversized static context waste tokens
on every run. Now measurable: review-and-improve flags skills using >30%
of the model's context window.

**Side effects**: Every job now emits one extra audit log event
(`context_budget_used`) before the session starts. ~1ms overhead.

## 2026-04-19 — Stale-context warnings in retrospective (Rec 7)

**Files changed**:
- `src/runner/retrospective.py` — Added `StaleContextWarning` dataclass,
  `_newest_mtime()`, `_days_since()` pure helpers, and
  `stale_context_warnings()` function. Checks for CONTEXT.md files >30d
  older than newest source, and CHANGELOG.md files with no updates in 60d
  despite git commits. Synchronous (filesystem + git only).

**Why**: Per § 7 Rec 7. Documentation decay was invisible — now it's a
measurable finding that review-and-improve can propose to fix.

**Side effects**: None on runner execution. Called by review-and-improve
skill during retrospective analysis.

## 2026-04-19 — Project-level protocol reference in directive (Rec 6)

**Files changed**:
- `src/runner/session.py` — `_build_server_directive()` now references
  `.context/PROJECT_PROTOCOL.md` for project-scoped sessions and directs
  to project's `skills/GOTCHAS.md` for non-obvious learnings.

**Why**: Per § 7 Rec 6. Project-scoped sessions lacked a protocol document
analogous to PROTOCOL.md. The new PROJECT_PROTOCOL.md gives them write-back
rules, and the directive now points there.

**Side effects**: None on runner execution — just adds a line to the
project-scoped directive string.

## 2026-04-19 — Graph-walked context injection + import lint (Rec 4)

**Files changed**:
- `src/context/module_graph.py` (NEW) — Pure functions: `parse_module_graph()`
  parses the SYSTEM.md markdown table into a forward dependency map,
  `reverse_graph()` builds the reverse map, `extract_imports()` AST-parses
  Python source for `from src.*` imports, `detect_modules_in_text()` finds
  module references in free-form text, `module_path_to_shorthand()` converts
  file paths to graph shorthands.
- `src/runner/session.py` — `_build_server_directive()` now accepts
  `job_description` and calls `_module_dependency_context()` for server-scoped
  sessions. When the description mentions known modules, the directive includes
  "Module dependencies" section listing dependents and advising to read their
  CONTEXT.md before API changes.
- `scripts/lint_docs.py` — New `check_module_graph_imports()` lint check.
  AST-parses every Python file under `src/`, compares actual imports against
  declared dependencies in SYSTEM.md module graph. Warns on undeclared deps.
- `.context/SYSTEM.md` — Fixed undeclared deps for runner.main, runner.session,
  gateway.web, gateway.telegram_bot, runner.retrospective. Added
  context.module_graph row.
- `tests/test_module_graph.py` (NEW, 23 tests) — Pure-function coverage for
  graph parser, import extractor, module detector, path shorthand conversion.
- `tests/test_doc_lint.py` — Added `test_module_graph_imports` test.

**Why**: Per § 7 Rec 4. Sessions modifying server modules now get automatic
dependency context, and the lint check catches undeclared cross-module imports
before they accumulate.

**Side effects**: The new lint check (6th) runs on every `python3 scripts/lint_docs.py`
invocation. It caught 12 real undeclared deps from prior phases, now fixed.

## 2026-04-19 — Added context consumption rollup (Rec 2)

**Files changed**:
- `src/runner/retrospective.py` — Added `ContextUsage` dataclass,
  `parse_read_events()` pure helper, `_normalize_path()` pure helper,
  and `context_consumption()` async rollup function. Walks audit log
  JSONL files for Read tool_use events, joins against jobs table for
  skill/status/rating, returns per-(skill, file_path) usage metrics.

**Why**: Teaches `review-and-improve` what files are actually useful to
skills by measuring actual Read tool usage from audit logs. Files read in
>50% of a skill's runs should be in `context_files`; files read <10% can
be removed. Per § 7 Rec 2.

**Side effects**: None on runner execution — this module is imported by
the gateway web route and by the review-and-improve skill.

## 2026-04-18 — Added proposals.py helper module (Rec 10)

**Files changed**:
- `src/runner/proposals.py` (NEW, ~230 lines) — pure helpers + async DB
  ops for proposal tracking table. Public interface: `extract_proposal_id`,
  `is_valid_change_type`, `is_valid_outcome`, `format_proposal_line`,
  `find_recent_duplicate`, `insert_proposal`, `mark_proposal_merged`,
  `list_pending_proposals`, `list_recent_proposals`, `get_proposal_by_id_prefix`.

**Why**: Supports the `/proposals` Telegram command + dedup/merge-stamping
in the review-and-improve and server-patch skills per § 7 Rec 10.

**Side effects**: None on runner execution — this module is imported lazily
by the Telegram handler and by skills that need it.

## 2026-04-18 — Added learning extractor post-session hook (Rec 1)

**Files changed**:
- `src/runner/learning.py` (NEW, ~280 lines) — Haiku classifier that runs after each successful non-chat, non-internal job. Pure helpers (`should_extract`, `parse_learning_response`, `format_audit_excerpt`, `list_installed_modules`) + async `extract_learning` (one-turn Haiku call, returns `LearningProposal`) + `maybe_extract_and_enqueue` (full pipeline entry point).
- `src/runner/main.py` — Added import of `maybe_extract_and_enqueue`. Added hook call in `_process_job` after writeback verification. Conditions: skip chat kind, skip any kind starting with `_`, skip internal skills (resolved_skill starts with `_`), skip escalation retries (`escalated_from` flag in payload).
- `skills/_learning_apply/SKILL.md` (NEW, internal skill) — Sonnet 4.6 / low, leading-underscore kind, takes payload from the classifier and appends to `.context/modules/<module>/skills/<CATEGORY>.md` using the `APPEND_ENTRIES_BELOW` marker. Dedup check by title grep before append. Commits locally; does not push.
- `.context/SKILLS_REGISTRY.md` — registered `_learning_apply` as internal skill.
- `.context/SYSTEM.md` — added `src/runner/learning.py` row to module graph.
- `.context/modules/runner/CONTEXT.md` — added `learning.py` to Paths, documented `maybe_extract_and_enqueue` in public interface.
- `tests/test_learning.py` (NEW) — 4 test classes / 27 pure-function tests covering should_extract, parse_learning_response, format_audit_excerpt, list_installed_modules.

**Why**: Closes the F1 feedback loop per `docs/EVALUATION_2026-04-18.md` § 7 Rec 1. Before this, institutional learnings were supposed to be written back by the primary session per PROTOCOL.md, but in practice only 1 PATTERNS.md existed across 5 modules. The classifier runs on every code-touching job and proposes a learning when appropriate; the internal skill applies it. Token-efficient: the `should_extract` gate avoids Haiku calls on read-only/chat jobs.

**Side effects**: Every successful non-chat, non-internal, non-escalation job now runs a ~5s Haiku classification after the existing writeback + review hooks. Classifier failures are logged and swallowed (non-fatal for the primary job). New audit log event kinds: `learning_extraction_done`, `learning_apply_enqueued`. New `_learning_apply` child job kind can appear in the queue.

**Gotchas discovered**: None yet; will accumulate as the loop runs in production. Likely candidates: classifier over-proposing (too lax) or under-proposing (too strict), `_learning_apply` concurrent-write conflicts on the same file.

## 2026-04-18 — Seeded skills/ subdirectory per Rec 3 (§ 7 Seed module skills/ dirs)

**Change**: This module now has `.context/modules/runner/skills/` containing stub `GOTCHAS.md`, `PATTERNS.md`, and `DEBUG.md` files. Stubs were created via `scripts/seed-module-skills.sh`; no source code modified.

**Why**: PROTOCOL.md directs sessions to append learnings to these files, but four of five modules had no skills/ directory at all, discouraging write-backs. Creating the directories with format-header stubs removes the friction and gives future sessions a template to append to. See `docs/EVALUATION_2026-04-18.md` § 7 Rec 3.

**Side effects**: None on module behavior. New lint check `check_module_skills_dirs` in `scripts/lint_docs.py` verifies these files continue to exist.


<!-- Newest entries at top. Every session that modifies src/runner/ appends here. -->

## 2026-04-18 — Context-aware SERVER_DIRECTIVE + context_files frontmatter

**Files changed**:
- `src/runner/session.py` — Replaced static `SERVER_DIRECTIVE` string with `_build_server_directive(skill_cfg, cwd)` function. Three code paths: chat (minimal), project-scoped (targeted), server-scoped (full). Appends `context_files` reading list when declared in skill frontmatter.
- `src/registry/skills.py` — Added `context_files: list[str]` field to `SkillConfig` dataclass. Parsed from SKILL.md frontmatter in `load()`.

**Why**: Reduces wasted tokens. Chat sessions no longer get instructions to read SYSTEM.md. Project-scoped sessions get targeted instructions about the project's CLAUDE.md. Skills can declare which docs their sessions should read first.

## 2026-04-17 — Phase 6: research-deep, idea-generation, project-update-poll, restore skills

**Files created**:
- `skills/research-deep/SKILL.md` — Deep-dive research skill. Opus 4.7 / high, 80 max turns, escalation to xhigh on failure. 10-20 sources, 2000-5000 words, mandatory "Where sources disagree" and "How I researched this" sections. Output to `projects/research-deep/`.
- `skills/idea-generation/SKILL.md` — Idea generation skill. Sonnet 4.6 / medium, 20 max turns. Generates 3-5 novel ideas, deduped against `projects/ideas/history.jsonl`. Supports actionable/speculative/technical-only/product-only styles.
- `skills/project-update-poll/SKILL.md` — Project update polling skill. Haiku 4.5 / low, 4 max turns. Runs a project's `on_update` command from manifest.yml. One retry on failure, no diagnosis.
- `skills/restore/SKILL.md` — Restore from backup skill. Sonnet 4.6 / medium, 30 max turns. Destructive: requires "RESTORE <date>" confirmation, second confirmation for >30 day old backups. Stops services, restores pg_dump + audit logs, restarts.

**Files changed**:
- `src/runner/router.py` — Added routing rule for `restore` skill (pattern: `\brestore\b`). Verified `research-deep` and `idea-generation` rules already exist; no duplicates added.
- `.context/SKILLS_REGISTRY.md` — Moved `research-deep`, `idea-generation`, `project-update-poll`, `restore` from Planned to Installed.

**Scaffolded**:
- `projects/ideas/` — Private ideas storage with CLAUDE.md, .context/CONTEXT.md, .context/CHANGELOG.md, empty history.jsonl. Not git-initialized (skill bootstraps on first run).

**Why**: Phase 6 adds four utility skills. `research-deep` is the heavyweight research path (vs `research-report`'s standard path). `idea-generation` provides creative brainstorming with dedup. `project-update-poll` enables cheap scheduled polling of project update commands. `restore` is the disaster recovery path paired with the `backup` script (Phase 5 planned).

**Side effects**: The `restore` router rule is broad (`\brestore\b`) — any message containing "restore" will route there. This is intentional since restore is a rare, deliberate action. `project-update-poll` has no router rule (triggered only via schedules/payload).

## 2026-04-17 — Phase 5: server-upkeep, server-patch, review-and-improve skills

**Files created**:
- `skills/server-upkeep/SKILL.md` — Daily health audit skill. Sonnet 4.6 / low, 20 max turns. Rotates logs, VACUUMs DB, checks tunnel/project/process health, reports anomalies only (outputs SILENT when all quiet, always reports on Sundays). Tags: scheduled, operations.
- `skills/server-patch/SKILL.md` — Server code modification skill. Opus 4.7 / xhigh, 60 max turns. Always PR-gated via `gh pr create`, never auto-merged. Post-review trigger always (Opus 4.7 / high reviewer). Commit metadata includes Requires-migration, Requires-env-change, Rollback. Tags: server, maintenance, manual-merge-required.
- `skills/review-and-improve/SKILL.md` — Retrospective auditor skill. Opus 4.7 / max, plan mode, 30 max turns. Queries job success rates, ratings, escalation/writeback frequency, code-review outcomes. Proposes structured changes for skills with >25% failure, <3 avg rating, frequent escalation, or 0 runs in 30 days. Dispatches server-patch via enqueue_job MCP. Tags: retrospective, needs-dispatch-mcp.

**Files changed**:
- `.context/SKILLS_REGISTRY.md` — Moved `server-upkeep`, `server-patch`, `review-and-improve` from Planned to Installed.

**Why**: Phase 5 completes the operational autonomy layer. `server-upkeep` handles daily housekeeping without human attention (SILENT output suppresses DMs). `server-patch` is the only path for modifying server code, enforcing branch + PR + human-merge. `review-and-improve` closes the feedback loop by analyzing job data and dispatching improvement patches.

**Side effects**: No `src/` files modified. These are skill definitions only — the runner already supports all required features (post_review, escalation, MCP dispatch, SILENT output).

## 2026-04-17 — Phase 4F: self-diagnose skill + event trigger loop

**Files created**:
- `skills/self-diagnose/SKILL.md` — Diagnose failures with risk classification. Auto-applies very-low/low risk fixes, delegates medium to app-patch (direct push) or server-patch (Phase 5, manual only for now), outputs diagnosis only for high risk. Tags: needs-projects-mcp, needs-dispatch-mcp.
- `src/runner/events.py` — Fourth async task. Polls every 60s. Rule 1: skill failed >= 2x in 10 min → enqueue self-diagnose. Rule 2: project unhealthy > 20 min → enqueue self-diagnose. Deduplication via recent job query.
- `tests/test_events.py` — 14 pure-function tests for `_should_trigger_skill_diagnose` and `_should_trigger_project_diagnose`.

**Files changed**:
- `src/runner/main.py` — Added `event_loop` as fourth async task in `main()`.

**Why**: Automated failure recovery. The event loop detects repeated failures and unhealthy projects, then enqueues self-diagnose jobs without user intervention. Per user decision: app-patch pushes freely, server code changes require Telegram Y/N (delegated to server-patch when it ships in Phase 5).

## 2026-04-17 — Phase 4G: project-evaluate skill + router rule

**Agent task**: Build Module G of Phase 4 -- the `project-evaluate` skill that automates producing manifest.yml + .context/CONTEXT.md for existing projects.

**Files created**:
- `skills/project-evaluate/SKILL.md` -- Skill definition with full procedure for analyzing a project codebase, generating manifest.yml, .context/CONTEXT.md, CLAUDE.md, and .context/CHANGELOG.md. Includes non-destructive overwrite checks via AskUserQuestion.

**Files changed**:
- `src/runner/router.py` -- Added routing rule for `project-evaluate` skill. Pattern matches "evaluate/assess/document/onboard project/app". Placed before the "new project" rules so "evaluate project X" does not fall through.
- `.context/SKILLS_REGISTRY.md` -- Added `project-evaluate` to the Installed table.

**Why**: Projects in `projects/` need standardized documentation (manifest.yml, .context/CONTEXT.md) to be registerable for hosting via `register-project.sh`. This skill automates producing that documentation by analyzing the project's codebase.

**Side effects**: The new router rule introduces four new trigger words (evaluate, assess, document, onboard) followed by "project" or "app". These are distinct from existing triggers and placed before the "new project" rules to avoid conflicts.

## 2026-04-17 — Phase 4E: new-skill meta-skill

**Agent task**: Create Module E of Phase 4 -- the `new-skill` meta-skill that authors new skills from natural-language descriptions.

**Files created**:
- `skills/new-skill/SKILL.md` -- Meta-skill system prompt. Opus 4.7 / high, acceptEdits mode, 30 max turns, post_review always. 10-step procedure covering analysis, overlap check, structural reference, drafting, support files, router rules, registry updates, scheduling, commit, and summary.

**Files changed**:
- `.context/SKILLS_REGISTRY.md` -- Moved `new-skill` from Planned to Installed table.

**Why**: `new-skill` is the self-expansion mechanism: once installed, the server can author additional skills from plain-language descriptions without manual SKILL.md authoring. This completes the meta-skill layer of Phase 4.

**Side effects**: None. No `src/` files were modified -- the router already had `new-skill` rules from a prior session (lines 42-43 in router.py). The skill is purely additive.

## 2026-04-17 — Phase 4D: app-patch skill

**Files created**: `skills/app-patch/SKILL.md`
**Why**: Lets the system patch existing projects via `/task fix <project>: <issue>`. Direct commit + push to main per user decision (no PR gate for project repos). Code review sub-agent runs after every patch via `post_review: { trigger: always }`.

## 2026-04-17 — Phase 4B: in-process MCP servers for projects + dispatch

**Agent task**: Build Module B of Phase 4 — two in-process MCP servers that give skills structured access to the projects registry and job dispatch.

**Files created**:
- `src/runner/mcp_projects.py` — MCP server with four tools: `list_projects`, `get_project`, `read_project_logs`, `restart_project`. Uses `create_sdk_mcp_server()` from the Claude Agent SDK. Pure helpers `_format_project()` and `_read_log_tail()` are separated for testability.
- `src/runner/mcp_dispatch.py` — MCP server with one tool: `enqueue_job`. Wraps `src.gateway.jobs.enqueue_job()` with `created_by="dispatch-mcp"`. Pure helper `_validate_enqueue_args()` separated for testability.
- `tests/test_mcp_tools.py` — 21 pure-function tests covering `_format_project`, `_read_log_tail`, and `_validate_enqueue_args`. No DB, no Redis, no SDK.

**Files changed**:
- `src/runner/session.py` — added MCP server injection in `_build_options()`. Skills opt in via `_NEEDS_PROJECTS_MCP` / `_NEEDS_DISPATCH_MCP` name sets (module-level) or `"needs-projects-mcp"` / `"needs-dispatch-mcp"` tags in SKILL.md frontmatter. MCP servers are passed as a dict to `ClaudeAgentOptions(mcp_servers=...)`.

**Why**: Skills like `self-diagnose` and `review-and-improve` need structured project introspection and the ability to spawn child jobs. MCP servers provide this via typed tool calls rather than ad-hoc Bash/file reads, making skill prompts simpler and more reliable.

**Side effects**:
- Skills in the opt-in sets now receive extra MCP tools in their sessions. These tools are additive and do not affect existing tool access.
- The `enqueue_job` MCP tool creates jobs with `created_by="dispatch-mcp"` for audit trail visibility.

**Gotchas discovered**:
- `ClaudeAgentOptions.mcp_servers` is a `dict[str, McpSdkServerConfig]`, not a list. The server name key must match the name passed to `create_sdk_mcp_server()`.
- The `@tool` decorator's function receives a single `args: dict` parameter with all input fields, not keyword arguments.

## 2026-04-17 — Phase 4 Module A: Code review sub-agent infrastructure

**Agent task**: Add synchronous code-review sub-agent that evaluates diffs after code-touching sessions.

**Files created**:
- `src/runner/review.py` — `run_code_review()` spins up an Opus 4.7 / plan-mode session to review a diff. `_parse_outcome()` extracts LGTM/CHANGES/BLOCKER from the reviewer's first line. `get_git_diff()` helper for extracting diffs. Diff truncated at 50K chars.
- `skills/code-review/SKILL.md` — User-triggerable code review. Plan mode, read-only tools, max 5 turns.
- `tests/test_review.py` — 16 pure-function tests for `_parse_outcome` and `get_git_diff`.

**Files changed**:
- `src/runner/main.py` — Added `_maybe_review()` post-session hook. Runs after successful sessions for skills with `post_review.trigger` set in frontmatter. Gets git diff, runs review, stamps `review_outcome` on the job. If BLOCKER, changes job status to `awaiting_user`.
- `src/runner/router.py` — Added routing rule for `code-review` skill.

**Why**: The code-review sub-agent is the quality gate for all Phase 4 coding skills (`new-project`, `app-patch`, `new-skill`). Skills opt in via `post_review: { trigger: always }` in their frontmatter.

**Side effects**: No existing skills have `post_review` set, so this hook is inert until Phase 4 skills are added. Zero impact on existing behavior.

**Design decisions**:
- Synchronous (blocks parent job), not async child job — because the parent's final status depends on the review outcome.
- Skills must opt in via `post_review.trigger: always` (default is `never`). Keeps the review surface explicit.
- Escalated jobs skip review (prevents reviewing the same diff twice after a failure retry).

## 2026-04-17 — Fix: audit_log.append `kind` argument collision

**Agent task**: Diagnose why all jobs fail immediately with `TypeError: append() got multiple values for argument 'kind'`.

**Files changed**:
- `src/runner/session.py` — renamed `kind=job.kind` keyword argument to `job_kind=job.kind` in the `audit_log.append(job_id, "job_started", ...)` call at line 182. The positional `"job_started"` already fills the `kind` parameter in `audit_log.append(job_id, kind, **fields)`, so passing `kind=` as a keyword collided.

**Why**: This bug broke INV-2 (every job must write `job_started` + terminal event). The crash happened before the audit log file was created, so `volumes/audit_log/` was empty — no jobs could run at all.

**Side effects**: The audit log field name for the job's kind changes from `kind` to `job_kind` in `job_started` events. No downstream code reads this field yet, so no migration needed.

**Gotchas discovered**:
- `audit_log.append(job_id, kind, **fields)` uses `kind` as a positional param name. Never pass `kind=` as a keyword in `**fields` — it collides. Use `job_kind` instead.

## 2026-04-17 — Phase 2: write-back verification + failure escalation + tests

**Agent task**: Complete Phase 2 — ship the `research-report` skill end-to-end with write-back enforcement and model escalation on failure.

**Files changed**:
- `src/runner/writeback.py` (new) — pure-function classifier: given a cwd, returns (needs_writeback, list_of_modified_files). Uses `git status --porcelain --untracked-files=all` so individual files are visible, not just parent directories.
- `src/runner/main.py` — added `_verify_writeback()` called after every successful job (except `chat` and `_writeback` itself); if the session left non-doc changes without touching a CHANGELOG, enqueues a child `_writeback` job linked via `parent_job_id`. Added `_maybe_escalate()` called after job failure: if the skill's frontmatter declares `escalation.on_failure`, enqueues a retry with the escalated model/effort (guarded by `escalated_from` payload to prevent loops).
- `src/runner/session.py` — fixed skill-name resolution: leading underscores preserved (`_writeback` stays `_writeback`), other underscores still become dashes (`research_report` → `research-report`).
- `src/runner/router.py` — reordered rules: `new-skill` pattern now matches before `research-report` so "new skill: daily BTC summary" doesn't route to research via the "summary" keyword.
- `tests/test_pure_functions.py` (new) — 52 tests covering router keyword matching, telegram flag parsing (model aliases, effort/permission validation, unknown flags), and writeback classification (doc vs non-doc paths, git status with and without changelog updates).

**Why**: The write-back protocol is the core mechanism that makes "pick up a project 3 months later" work — but only if it's enforced. Primary sessions may skip it under Opus 4.7's stricter instruction following or because a skill author forgot to include it. The `_verify_writeback` hook spawns a cheap Sonnet-low follow-up exclusively for the CHANGELOG update. Similarly, `on_failure` escalation catches the "Sonnet tried and couldn't; Opus 4.7 / high should" case without over-provisioning on every job.

**Side effects**:
- Every successful non-`chat`, non-`_writeback` job now incurs a ~1-second git-status check. Negligible.
- Failed jobs with a skill that declares `on_failure` will retry automatically — doubling cost for persistent failures. This is the intended trade: one extra escalated attempt is cheaper than the user re-running with flags manually.

**Gotchas discovered**:
- `git status --porcelain` without `--untracked-files=all` collapses new directories to their parent name (`src/` instead of `src/thing.py`). Writeback classification needs file-level visibility.
- Router rule order matters: earlier rules win. When adding a new rule, place it above anything it might conflict with.
- `kind.replace("_", "-")` converts `_writeback` to `-writeback` (bad). Internal skills (leading underscore) need to be preserved as-is.
- Top-level markdown files (README.md, MISSION.md, SERVER.md, CLAUDE.md) must be classified as docs — otherwise editing them would trigger false writeback spawns.

## 2026-04-16 — Initial bootstrap (Phase 1)

**Agent task**: Create the runner module from scratch.

**Files created**:
- `src/runner/main.py` — entry point with 3 async loops (job, scheduler, cancel)
- `src/runner/session.py` — one ClaudeSDKClient session per job; streams to audit log
- `src/runner/router.py` — rule-based keyword → skill matcher (no LLM)
- `src/runner/quota.py` — subscription-quota detection and pause/resume

**Why**: Replace the old `worker.py` (94KB, 9 loops, monolithic) with a thin,
skill-driven runner that delegates all agent logic to the Claude Agent SDK.

**Side effects**: None — this is a new module.

**Gotchas discovered**:
- `update` from SQLAlchemy collides with Telegram's `Update` type. Import as
  `sql_update` in files that handle telegram updates.
- The SDK's Python hooks are partially shell-only in the current version; we
  capture audit events via message-iteration instead, which is robust across versions.
- `ANTHROPIC_API_KEY` silently flips the SDK to API billing — the runner's startup
  check aborts if it's set.
