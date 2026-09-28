# Design synthesis: interface-first spine, outcome-first core (2026-09-24)

Synthesizing architect. Inputs: six designs, three judges, `scratchpad/current-state-map.md` (cited as "state map §n"; `file:line` are repo-relative and were re-verified against the working tree on 2026-09-24), `docs/research/llm-landscape-2026-09/*` (cited `<doc> §n`), and the approved plan `docs/superpowers/plans/2026-08-10-model-router.md` (cited `plan §n`).

**Judging outcome.** Mean scores tie `design-interface-first` and `design-outcome-first` at 7.71; judge 1 named interface-first, judges 2 and 3 named outcome-first, and all three said "ship one, graft the other". The two are complementary, not rivals: interface-first is the only design that phases in the order the owner *feels* (persisted origin + DMs + ghost fixes in week 0-1, phone control plane by week 3, hot-path refactor last behind a replay gate); outcome-first is the only design whose core is a runner-verified definition of done and a grader that is never the writer's vendor. Outcome-first's own fatal flaws were about phasing (a two-week big-bang P0, contracts in observe mode until week 7, INV-13 blocking fleet-wide); interface-first's were about mechanisms (transcript-parse done checks, `ai-mcp` mutating tools, `owner_edited` on atlas rows, Gemini-free classifying owner text). So: **interface-first's control plane, phasing and lanes are the spine; outcome-first's Deliverable Contract, verdict ledger, provider ledger and redacted projection are the effectiveness core**, with the grafts from the other four listed in §0 and marked `[graft: <design>]` where they land.

## 0) Decision summary

What we are building (ten bullets):

1. **One control plane, one grammar, every surface a view** — `src/control/` (grammar → typed intents → view models → per-channel renderers) fronting Telegram, a static PWA, an `ai` CLI and a *read-only* `ai-mcp`; `/task` and its `--kind/--model/--effort/--project` flags stay the canonical launch (no `--as/--on` relearning; judge 1), bare text = `/task`. *[spine: interface-first §1.2, §2.1]*
2. **Every job DMs, every job is watchable, from week 1** — persisted `origin_*` on jobs and tasks replaces the in-process `_job_to_chat` dict (`telegram_bot.py:38, 1028`), a `notifications` outbox gives alert history, scheduled failures DM within 60 s, and a single self-editing JobCard walks `queued → starting → working → blocked → reviewing → done/failed` with a live DoD tick-list. *[interface-first §1.3, §2.2; graft: outcome-first §2.1 DoD ticks; multi-bot §2.1 edit coalescing + `/mute`]*
3. **Definition of done is a runner-executed contract, not a transcript vibe** — frontmatter `done:` blocks with deterministic checks (`file_exists`, `git_pushed`, `url_200`, `db_row`, `tests_green`, `budget_within`, …), a default contract for every job, and an honest `done_verdict=unverified` on cards; graders receive an evidence bundle, never the writer's self-report. *[core: outcome-first §3.1-3.2]*
4. **Cross-vendor review is additive dissent, recorded structurally; Anthropic stays the only LGTM** — belts: evidence checks → in-session `code-review` gate (verdict finally stored) → Anthropic post-review (timeout now stamps a verdict) → cross-vendor grader/critic on a *redacted projection* with `grader.provider != writer.provider` enforced in code and fallback `skipped`, never Anthropic. INV-13 pre-push is mandatory for non-Anthropic lanes and flag-only on Anthropic lanes unless the owner decides otherwise. *[outcome-first §3.3, §6.3; kernel §3.2 `REVIEW_PRE_PUSH`; plan §7 "GPT reviews nothing on `code-server`" stands]*
5. **Provider registry + policy + per-provider quota land behind the plane** — `providers.yml`/`routing-policy.yml` replace the accidental allowlist (`telegram_bot.py:122-134` → `tests/test_skill_contracts.py:24`), quota keys go per provider, fan-out starts 2/2/1/1, and the Claude window is read from the typed `RateLimitEvent` the SDK already emits (`session.py:1065`; 636 prod events) — no interactive probe session. *[plan §6a-f; interface-first §2.6; incremental §0a row 6]*
6. **Executor seam extracted last, behind a golden-file + audit-replay gate** — `ClaudeSdkExecutor` is `_build_options` + `_run_in_process` (`session.py:650-816, 1048-1132`) moved byte-for-byte; `ExecSpec.to_claude_options()` must equal today's `ClaudeAgentOptions` on 10 recorded skills before the seam goes live; typed `terminal_reason` (incl. `auth_expired`, `unrecognized_model` with the `model_usage` assertion) replaces the banner regex. *[incremental §8 R2 gates; kernel §1.2 events]*
7. **Non-Anthropic lanes are text-only by default and env-scrubbed always** — Codex runs `exec --json --ephemeral --sandbox read-only` in a per-job clone with `EnvScrubber` default-deny (PATH/HOME/CODEX_HOME/LANG), `features.goals=false`, `otel.metrics_exporter="none"`, no MCP, no `env_files`; utility HTTP lanes get no tools; the only non-Anthropic *writer* (a `code-project` canary) is deferred to P6 with pre-push review. *[kernel §1.6; incremental §1e; multi-bot §1.6]*
8. **Lanes with an owner reservation and visible holds** — `BLPOP jobs:queue:owner jobs:queue:kernel jobs:queue:atlas jobs:queue:utility jobs:queue` with legacy `jobs:queue` kept as `background` (six producers untouched), no pop-then-push-back, `job_held{reason}` + `/queue` so a stalled job is never silently stuck. *[interface-first §4; kernel §1.7/§2.1]*
9. **Scheduling stays on one scheduler of record, made honest** — commit-before-RPUSH, slot-based `next_run_at`, `misfire_policy`, `notify ∈ {never,failures,always}`, `expects.within` late/missing alarms, phone edits on non-governed rows only (atlas loop rows keep LOOP.md §7), `/schedule add "<phrase>"` → cron via the local model with a confirm button. Vendor-native schedulers are not producers. *[interface-first §4; hub §3-4 `expects`; multi-bot §2.1 phrase→cron]*
10. **Trading = research, critic, evaluation, paper loops; never an order path** — `atlas-critic` (Codex read-only, no atlas env, redacted memo) after the Anthropic validator; local Qwen for mechanical checks; server-side broker-host deny in `guards.py` (owner PR); per-vertical `env_files`; a trading-health "is any of this working" page; the cheap blockers (tokens, `weekly.py:316`, Alpaca fallback) fixed first. *[interface-first §6; outcome-first §6; kernel §2.2 health page]*

What we are explicitly **NOT** building: a council/persona room, puppet bots or a supergroup in `TELEGRAM_ALLOWED_CHAT_IDS` (multi-bot D1); an IMAP mailbox collector, vendor-side crons as producers, ChatGPT Plus or SuperGrok by default (hub §11); metered xAI/Perplexity/OpenRouter spend (declined 2026-08-17, plan §10.3); an interactive Claude statusLine probe session; `--as/--on`, `--lane/--priority`, `--class/--done` launch flags or `ai job run` verb nesting; mandatory `<<<EVIDENCE>>>` blocks; a sorted-set queue; a `src/kernel/` rename, a `job_attempts` table or dropping `Task.chat_id` this cycle; four migrations in one phase; INV-13 blocking on Anthropic lanes by default; Codex grading `code-server` diffs; Web Push/CF Access/SSE-cookie changes outside one owner-approved auth PR; a LiteLLM or Langfuse daemon (`runtimes-aggregators.md §3(c)`: 4 GiB / 16 GiB floors); an SDK pin bump outside the replay gate; any order tool.

### 0a) Amendments to the approved 2026-08-10 plan (what the research made stale) *[graft: incremental §0a]*

| Plan claim | Research finding | Amendment |
|---|---|---|
| §5 Codex "works on every plan incl. Free" as a load-carrying lane | Free = "explore"; published 5-h bands start at Plus (`chatgpt-openai.md §3`; matrix §2) | Free = grader/critic + canary probes; load-carrying is owner decision D5 |
| §5 "Codex non-interactive MCP is broken" | `default_tools_approval_mode`/per-tool `approval_mode` now exist (`chatgpt-openai.md §7`) | Keep "no MCP on Codex" anyway — dispatch/projects MCP are in-process SDK servers (`mcp_dispatch.py:20,145`) and containment is simpler; reason changed, rule did not |
| §5 Gemini "personal-account tier ~1000/day" | Gemini CLI Google-login lane ended for unpaid/Google One (`gemini-google.md §3`; `runtimes-aggregators.md §1`); unpaid key = 250 RPD Flash, **trains + human review** (`gemini-google.md §3a`) | `gemini-free` is HTTP-only, `sensitivity: public` only, never Telegram text or transcripts; no Gemini executor |
| §5 OpenRouter `:free` in the utility chain | 20 RPM, 50 RPD without a purchase, provider-dependent training (`runtimes-aggregators.md §3`) | Registered in `providers.yml` as `trust: probation`; in **no** default chain (judges 1/3) |
| §5 local "qwen3:4b" | `qwen3.5:4b` (3.4 GB) is the fit; live Ollama holds 14 GB stale weights, zero callers (`local-models-m4-16gb.md §1, §7`; state map §2.8) | pull `qwen3.5:4b` + `embeddinggemma`, delete stale weights, RAM guard <3 GB free |
| §6a model ids (`gpt-5.6-codex`, `claude-sonnet-4-6`) | Opus 5.5/Sonnet 5 exist but the pinned bundled CLI 2.1.139 may return a **silent empty success** for unknown ids (`claude-anthropic.md §7`); Haiku 4.5 retires ≥2026-10-15 (`§1`) | ids live in `providers.yml`; no new Anthropic id enters until the SDK bump passes the replay gate (D13); router/learning swap `claude-haiku-4-5-20251001` (`llm_router.py:148`, `learning.py:258`) → `claude-sonnet-4-6` `effort=low` in P0 |
| §6f "no lane exposes remaining budget" (implicit) | SDK emits typed `RateLimitEvent{utilization, resets_at}` (`session.py:1065-1082`); Codex app-server `account/rateLimits/read` + `updated` push (`chatgpt-openai.md §3`); status-line JSON is interactive-only (`claude-anthropic.md §3` [68]) | `quota_snapshots(source=vendor)` from SDK events + a 15-min Codex RPC poll; no probe, no scraping |
| §7 "GPT reviewing anything is not in-plan" | Codex/Gemini rank **high** independence for reviewing Claude output; Kimi/MiniMax/DeepSeek/Qwen named in distillation disclosures (`crosscut-subscription-automation-tos.md §5.2a`) | Codex/Gemini graders are *additive dissent* on `research-read`, `trading-research`, `code-project`; `code-server`/`review-gate`/`_evaluate` stay Anthropic-only with **no** advisory grade (judge 2 condition 1) |
| §8 INV-21(b) Codex Seatbelt | confirmed A− rating; network off by default; goal mode + `statsig` metrics on by default (`chatgpt-openai.md §3, §7`; `crosscut-tos §3.8a`) | lane contract: `--ephemeral`, `features.goals=false`, `otel.metrics_exporter="none"`, `analytics.enabled=false`, `web_search="cached"`, `stale_head → flagged` |
| — | `--bare` "will become the default for `-p`" and never reads OAuth; `claude setup-token` is a one-year token (`claude-anthropic.md §3`) | SDK/CLI pin gate + `claude -p ping` smoke; setup-token in launchd env; never pass `--bare` |
| — | Consumer training toggles default on; theses 30-day retained at best; Fable always 30 d (`crosscut-tos §3.8`) | `sensitivity` on every skill (default `owner-private` for human-originated or transcript-derived text); quarterly training-toggle checklist card gates thesis-class routing (hub §10) |

## 1) Goals and non-goals mapped to the owner's ask

| Owner ask | Goal (measurable) | Non-goal |
|---|---|---|
| Ease of use across interfaces | Same verbs on Telegram, PWA, `ai` CLI, `ai-mcp` (read-only); launch in one line; ack card ≤2 s; deploy approvals are a button, not a retype; `/schedule add` works from a phone | Vendor apps as systems of record; email/Slack channels; a chat room of personas |
| Visibility | Live JobCard (turn/tool/tokens/window %); `/queue` with hold reasons; `/quota` per provider from vendor signals; `/cost` weekly; schedule adherence on the phone; deliverables with deep links; alert history; trading-health page | Per-tool latency decomposition beyond `queue_wait_ms`/`first_event_at`; host RSS series (later) |
| Deliverable effectiveness | `done_verdict` on 100 % of jobs; DoD pass-rate and grade per provider × task class; independence measured; scoreboard drives the ladder; retro replaces the opus/max idle auditor | Human ratings as a signal (2/1633); any grader as the merge gate |
| Scheduling across vendors | One scheduler of record with lanes, misfire policy, `expects.within`, per-row `provider_policy`; class-aware pause so an Anthropic red window pauses only pinned lanes | Vendor-native crons as producers; minute-cadence anything on vendor lanes |
| Project delivery | Clone → work → evidence checks → gate → push → parked approval → gated deploy → DoneCard with URL + healthcheck; Codex `code-project` canary only after P6 with pre-push review | Non-owner-facing generation on subscription lanes (`crosscut-tos §3.9`) |
| Trading research (INV-22) | Critic stage, mechanical checks, constitution DoD, per-vertical env scoping, server-side broker deny, health page; blockers fixed first | Any order path, broker MCP with order tools, sentiment as a signal, metered feeds by default |

## 2) Architecture

### 2.1 Components

```
                                   OWNER'S HANDS
  phone: Telegram ───┐   laptop/phone: PWA /app ───┐   terminal: `ai` ───┐   Claude Desktop/Codex: `ai-mcp` (read-only)
   cards + buttons   │   views + streamed fetch    │   stream + tail     │   ai_jobs ai_job ai_watch ai_queue ai_quota ai_cost …
  ───────────────────┴──────────────────────────────┴─────────────────────┴───────────────────────────────────────────────
                                    │  ONE GRAMMAR  src/control/grammar.py   (/task flags unchanged; verbs added)
                                    ▼
             CONTROL PLANE  src/control/  intents.py · views.py · policy.py (god/privilege strip written once, C10)
             ┌───────────────────────────────────────────────────────────────────────────────────────┐
             │ intents: task watch jobs job queue cancel approve reject reply schedule_* providers    │
             │          quota cost deliverables atlas proposals project_* clear(confirm)              │
             │ views:   JobCard DoneCard FailedCard ApprovalCard DeliverableCard ScheduleCard          │
             │          QuotaStrip ProviderPanel CostReport AtlasHealth AlertHistory Scoreboard       │
             └──────────────┬──────────────────────────────────────────────┬──────────────────────────┘
                            │ enqueue_job (jobs.py:16-47, shape unchanged) │ read-only queries
                            ▼                                              ▼
  STATE  Postgres  jobs(+run/origin/contract columns)  tasks(+origin, awaiting_since)  schedules(+lane, misfire, notify, expects…)
                   notifications(outbox) approvals deliverables verdicts provider_ledger quota_snapshots provider_qualifications
  BUS    Redis     jobs:queue:<lane> (+legacy jobs:queue)  jobs:stream:<id> (rich)  jobs:done:<id>  jobs:reviewed:<id>  jobs:cancel
                   quota:<provider>:paused_until  quota:<provider>:counters:<day>  heartbeat:runner  events:control
                            │
                            ▼
  RUNNER src/runner/main.py   lane-ordered BLPOP · owner reservation · provider-window gate · job_held (slot-before-BLPOP kept)
     ├─ registry/models.py + providers.yml + routing-policy.yml + provider_qualifications → policy.select()
     ├─ ExecSpec (vendor-neutral) → executors/
     │     ├ claude_sdk.py   = _build_options + _run_in_process moved byte-for-byte (trust anchor; hooks, MCP, subagents)
     │     ├ codex_cli.py    = codex exec --json --ephemeral --sandbox read-only|workspace-write; EnvScrubber; clone only
     │     ├ completions.py  = utility_call(): ollama-local / gemini-free(public) / anthropic-utility; in-process, no tools
     │     └ script.py       = no_llm skills (skills.py:55, dead today): checks, SQL pre-pass, canaries, deploy autopilot
     ├─ normalized ExecEvent → same audit kinds (C14) + jobs:stream + provider_ledger + heartbeat
     └─ post-steps: DAG promote → contracts.check → deliverables → gate verdict capture → post-review (pre-push for non-Anthropic)
                    → grader/critic (vendor ≠ writer) → writeback → learning → task lifecycle (markers unchanged) → notify outbox → jobs:reviewed
                            │
                            ▼
  NOTIFY src/notify/   outbox → renderers: Telegram · SSE · CLI · `python -m src.notify send` (launchd alerters, edge Worker keep working)
```

### 2.2 Control plane (`src/control/`, new) *[interface-first §1.2]*

- `grammar.py`: one parser. `/task <text> [--kind=<skill>] [--model=<provider/model|alias>] [--effort=] [--project=] [--timeout=] [--watch] [--quiet]` — the existing flags (`telegram_bot.py:140-172`) with unknown models rejected here against the registry (today `:157` passes them through unchecked). Replaces the three divergent parsers (Telegram leading-flags-only, `web.py` `CreateJobRequest`, `mcp_dispatch.py:35-40`).
- `intents.py`: pure functions `(actor, args) → Result | Error` over the models. The only mutation path into the runner stays `enqueue_job` (`jobs.py:16`). `cancel` gains a durable path for queued jobs (`LREM` + status flip; today `main.py:1368-1404` reaches running jobs only). `task` creates a `Task` + origin for every human launch, not only Telegram (`telegram_bot.py:231-256` vs `web.py:399-405`).
- `policy.py`: god/privilege strip and `kind=god` rejection written once (INV-18, C10); imported by Telegram, web, CLI, `ai-mcp`, `mcp_dispatch`.
- `views.py` + `renderers/{telegram,sse,cli,mcp}.py`: one view object per card, rendered per channel; renderers are the only code that knows Telegram's 4096 chars / 64-byte callback / ≤8 buttons (C23) and MarkdownV2 escaping (fixes `TROUBLESHOOTING.md:699-707`).
- **SPOF rule (judge 1/2 must-fix):** `telegram_bot.py` is not rewritten in P1. New handlers are registered *beside* the 12 legacy ones (`telegram_bot.py:1296-1313`); `CONTROL_PLANE_V2=0` restores legacy behaviour and `tests/test_grammar.py` asserts the legacy handler list is still registered with the flag off. Transport extraction happens in P5 after two releases of soak.

### 2.3 Data model (all additive, nullable; one migration per phase)

| Migration (phase) | Table | Columns / shape | Why (gap) |
|---|---|---|---|
| **007** (P0) | `jobs` | `resolved_provider` s32, `model_served` s64, `executor` s24, `cli_version` s24, `lane` s16, `priority` smallint, `origin_channel` s16, `origin_ref` s64, `origin_thread` s64, `queue_wait_ms` int, `first_event_at` ts, `input_tokens`/`output_tokens`/`cache_read_tokens`/`cache_write_tokens` bigint, `num_turns` int, `duration_api_ms` int, `cost_usd_list` numeric(10,4), `terminal_reason` s32, `task_class` s32, `sensitivity` s16 | `session.py:1095` drops `num_turns/total_cost_usd/duration_api_ms/model_usage/stop_reason/api_error_status`; `models.py:14` promises a tokens column that does not exist; `Task.chat_id` (`models.py:284-286`) is the only channel binding; backfill tokens from `result.usage` (642 rows) |
| 007 (P0) | `tasks` | `origin_channel`, `origin_ref`, `origin_thread`, `awaiting_since` | web launches get no Task; stuck-state ages invisible (state map §5.24) |
| 007 (P0) | `notifications` (new outbox) | `id, notice_kind, subject_type, subject_id, severity, body, actions jsonb, channel, external_ref, status, attempts, sent_at, created_at` | `_job_to_chat` dict; `tasks:notify` string vocabulary (`main.py:733,886,1112,1129,1216,1260` ↔ `telegram_bot.py:1087-1271`); no alert history |
| **008** (P1) | `approvals` (new) | `id, kind ∈ {deploy, plan, protected_path, provider_promote, question, choice}, subject_type, subject_id, requested_by_job, payload jsonb, status, decided_via, decided_at, note` | `DeployNeedsApproval` fails the job (`main.py:492-511`; `session.py:872-881`) |
| 008 (P1) | `deliverables` (new) | `id, job_id, task_id, kind ∈ {file, commit, pr, url, report, artifact}, title, path, url, sha, bytes, preview, created_at` | deliverables are truncated text with no path/URL (state map §5.10); local `<job>.summary.md` and skill-written files become rows too *[graft: hub §1.3]* |
| 008 (P1) | `jobs` | `contract` jsonb, `dod_pass_count`/`dod_total` smallint, `done_verdict` s16 ∈ {verified, unverified, failed_checks, n/a}, `merge_gate_verdict` s16 | `jobs.status` CHECK (migration 006) untouched — done-ness is a column, not a status *[outcome-first §1.2]* |
| 008 (P1) | `schedules` | `lane` s16, `misfire_policy` s16 ∈ {skip, catch_up_once}, `notify` s16 ∈ {never, failures, always}, `owner_edited` bool, `governed` bool, `last_run_job_id`, `provider_policy` s16, `expects` jsonb, `adherence` s16 | misfires dropped silently (`main.py:1314-1362`); seeder overwrites cron (`seed-schedules.sh:22-47`); atlas rows stay LOOP.md §7-governed |
| **009** (P2) | `quota_snapshots` (new) | `provider, window ∈ {five_hour, seven_day, day, month}, used_pct, resets_at, source ∈ {vendor, inferred}, ts` | 636 `rate_limit_status` events never aggregated |
| 009 (P2) | `provider_ledger` (new) | `ts, job_id, provider, model, task_class, purpose ∈ {main, subagent, router, learning, review, grade, judge, utility, script}, tokens_in, tokens_out, cache_read, cache_write, cost_usd_list, latency_ms, ttft_ms, terminal_reason, rate_limited bool, window_id` | the three hidden Claude sessions per job (router, review, learning) are invisible today *[outcome-first §1.2]* |
| 009 (P2) | `verdicts` (new) | `id, job_id, stage ∈ {evidence, merge_gate, post_review, grade, critic, eval, retro}, grader_provider, grader_model, grader_job_id, verdict ∈ {pass, fail, lgtm, changes_requested, blocker, concur, dissent, error, skipped, timeout}, score numeric, findings jsonb, dod jsonb, cost_usd_list, latency_ms, created_at` | INV-13 gate verdict never stored; `evals/results/` empty |
| **010** (P4) | `provider_qualifications` (new) | `provider, task_class, state ∈ {shadow, canary, qualified, demoted}, canary_share, since, evidence jsonb, changed_by` | plan §6g artefacts absent |

Redis: `jobs:queue:<lane>` keys added, `jobs:queue` kept; `quota:<provider>:*` replaces `quota:paused_until` (`quota.py:21`) in P3; `jobs:stream:<id>` gains `tool_result` previews, `guard_denied`, `rate_limit_status`, `heartbeat`, `dod_tick`; `jobs:reviewed:<id>` fires after post-steps *[graft: multi-bot §1.7]*; `events:control` carries fleet events for the Now panel.

### 2.4 Executors (`src/runner/executors/`, P3) *[plan §6b; kernel §1.8 adapter contract]*

- `base.py`: `ExecSpec{job_id, provider, model, effort, cwd, system_prompt, user_prompt, capabilities:set, guard_profile, mcp_servers, subagents, max_turns, timeout_s, output_schema, sensitivity}`; `Executor.start(spec) → AsyncIterator[ExecEvent]`, `interrupt()` (≤2 s, INV-8), `kill(grace_s)` (the timeout path finally calls it; today `main.py:376-380` never interrupts), `result() → ExecResult{final_text, usage, cost_usd_list, num_turns, duration_api_ms, model_served, terminal_reason ∈ ok|max_turns|interrupted|timeout|api_error{status}|rate_limited|auth_expired|unrecognized_model, permission_denials}`; conformance test with a fake executor.
- `claude_sdk.py`: `_build_options` (`session.py:650-816`) split at its five seams (prompt 664-692, resolution 694-724, subagents 730-736, guards 752-755, MCP 757-796) into `ExecSpec` + `to_claude_options()`; `_run_in_process` (`:1048-1132`) + `_handle_message` (`:1138-1170`) moved verbatim. Two fixes ride along: read typed `api_error_status`/`stop_reason` (banner regex `:495-534` kept one release as a belt), and assert `model_usage ∋ requested model ∧ duration_api_ms > 0` (silent-empty-success trap, `claude-anthropic.md §7`).
- `codex_cli.py` (P4): `codex exec --json --ephemeral --sandbox read-only -m <pinned> --cd <clone> [--output-schema s.json -o out.json]`; per-job config forces `features.goals=false`, `otel.metrics_exporter="none"`, `analytics.enabled=false`, `web_search="cached"`, `approval_policy=never`; `CODEX_HOME=volumes/codex/<job8>` seeded with one `auth.json` per serialized stream (`runtimes-aggregators.md §3(a)`); SIGTERM→SIGKILL on cancel/timeout. JSONL mapping *[graft: incremental §1h]*: `thread.started→job_started`, `agent_message→text`, `reasoning→thinking`, `command_execution→tool_use{tool_name:"Bash"}+tool_result`, `file_change→tool_use{tool_name:"Edit"}+tool_result`, `web_search→tool_use{WebSearch}`, `turn.completed.usage→job_completed.usage`, `turn.failed/error→job_failed` (`429 slow_down→rate_limited`, `503→api_error`). Contract-tested on pinned-CLI fixtures.
- `completions.py`: `utility_call(task_class, system, user, schema, sensitivity) → dict|None` replacing the four copy-pasted `query()` loops (`llm_router.py:156-168`, `learning.py:266-278`, `review.py:258-278`, `evals/run.py:74-100`; the reviewer keeps its 6-turn agent form, pinned). Runs **in-process over HTTP** (Ollama native `/api/chat` with `format`, Gemini `generateContent`, Anthropic utility via SDK `query()` as the terminal link) so routing/learning stop spawning two ~148 MB `claude` subprocesses per job *[graft: kernel §4]*. Schema-validate-and-retry once; fail-open only where the caller is fail-open today.
- `script.py`: implements `no_llm: true` + `command:`; used for evidence checks, credential canaries, adherence, retro SQL pre-pass, and the deploy autopilot (moves `healthcheck-all.sh:204-252` raw SQL onto `enqueue_job`) *[graft: kernel §1.2/§5.4]*.

### 2.5 Registry and routing policy (P3) *[plan §6a/§6d]*

`providers.yml` (anthropic `sdk-anthropic` trust anchor; codex `cli-agent` probation; gemini-free `openai-compat` `data:{trains:true, max_sensitivity:public}` `caps:{rpd:250}`; ollama-local `guard:{min_free_gb:3}`; openrouter-free `trust: probation`, no chain) feeds `grammar.py`, the PWA picker, `VALID_MODELS` (`tests/test_skill_contracts.py:24`), `_MODEL_BUDGETS` (`session.py:466-471`) and escalation targets (`main.py:759-760`). Bare ids default to `anthropic/` (C17; 72 skills unchanged).

```yaml
# routing-policy.yml (initial; pins are data, un-pinning is protected)
classes:
  utility-classify: {chain: [ollama-local, anthropic-utility], fail_open: true}      # human-originated/transcript text: never gemini-free/openrouter
  utility-public:   {chain: [ollama-local, gemini-free, anthropic-utility], fail_open: true, max_sensitivity: public}  # pre-fetched public docs only
  chat:             {chain: [anthropic/claude-sonnet-4-6@low], pinned: true}          # Sonnet 5 low after D13 (matrix §1 item 8)
  research-read:    {chain: [anthropic], grader: [codex#redacted, gemini-free#public, ollama-local#mechanical]}
  code-project:     {chain: [anthropic, codex#ladder(P6)], grader: [codex], gate: anthropic}
  code-server:      {chain: [anthropic], pinned: true, grader: none}                  # plan §7: GPT reviews nothing here
  review-gate:      {chain: [anthropic], pinned: true}
  _evaluate:        {chain: [anthropic], pinned: true}
  trading-research: {chain: [anthropic], pinned: true, critic: [codex#redacted, ollama-local#mechanical], default_sensitivity: proprietary}
pairing_rule: grader.provider != writer.provider        # enforced in grading.py, not in a prompt
grader_fallback: skipped                                # never anthropic (quota asymmetry)
infer:
  - {when: {subagents: nonempty}, require_caps: [subagents]}
  - {when: {tags: [needs-dispatch-mcp, needs-projects-mcp]}, require_caps: [mcp]}
  - {when: {isolation: none}, require_caps: [guard-hooks]}   # 48 unisolated skills stay on Anthropic
sensitivity_default: {telegram: owner-private, transcript: owner-private, scheduled: skill.sensitivity, atlas: proprietary}
```

Skill frontmatter extension (backward-compatible; `SkillConfig.model` stays a raw string with derived `provider`/`model_id` so `test_agents.py:33-56` and `test_registry_failclosed.py:58-61` keep passing; 72 skills need no edit):

```yaml
# additive fields on skills/<name>/SKILL.md (all optional)
model: anthropic/claude-opus-5          # bare id → anthropic/; unknown provider fails the job (C12)
task_class: research-read               # inferred from isolation + tags when absent (plan §6e)
providers: {allow: [anthropic], critic: [codex, ollama-local]}   # writer chain and grader/critic lanes; deny: [...] also accepted
sensitivity: proprietary                # public | owner-private | proprietary; atlas/alpha default proprietary
done:                                   # §5.1; absent → default contract, done_verdict=unverified
  deliverables: [{file: "projects/research/*-{{date}}.md"}, {commit: true}]
  checks: [{name: citations_min, min: 3}, {name: sections_present, sections: [Thesis, Evidence, Risks]}, {name: git_pushed}]
  on_fail: flag                         # flag (default) | fail (deploy-verify only) | fix-round
no_llm: true                            # with command: → ScriptExecutor
command: "python -m evals.run --provider {{provider}}"
escalation:
  on_failure: [{provider: anthropic, model: claude-opus-4-7, effort: high}]   # list form; the bare-map form of 31 skills still accepted
```

Lint rules (P4 owner PR, `lint_docs.py`): non-Anthropic provider ⇒ `isolation: workspace`; pinned classes ⇒ `anthropic/`; provider and every check name must exist in the registries; `sensitivity: proprietary` ⇒ critic lanes with `data.trains=false` only; a `governed` schedule row's kind must be an atlas-charter skill. Capability matching keeps the 20 subagent skills and 16 dispatch-MCP skills on Anthropic with no special-case code. Unknown provider/model fails the job at spec build (C12), never falls back. `routing_decision` confidence is thresholded (<0.6 → generic workspace task; today discarded at `session.py:616`); `--kind` corrections are recorded as ground truth. Escalation becomes a chain of `{provider, model, effort}` with error-class gating: `rate_limited`/`auth_expired`/`api_error` never spawn `self-diagnose` (21 % of all jobs today, `main.py:704-853`).

### 2.6 Containment equivalents (INV-17/20/21/22) *[kernel §1.6 matrix; multi-bot §1.6 text-only]*

| Executor | Tier | Filesystem | Network | Secrets | Tool veto | Review of diffs |
|---|---|---|---|---|---|---|
| Claude SDK | none (allowlist), workspace, host (god) | clone or shared | via SDK | inherits launchd env; `env_files` per manifest, scoped per vertical (P5) | PreToolUse hooks unchanged (`guards.py:381-490`, attached `session.py:753/755`) | in-session `code-review` + post-review |
| Codex CLI | **workspace only**; `read-only` sandbox for grader/critic; `workspace-write` only for the P6 canary | per-job clone; `protected_roots()` never inside | off (`workspace-write` default is network-disabled; `crosscut-tos §3.8a`) | `EnvScrubber` default-deny: PATH/HOME/CODEX_HOME/LANG only; no `env_files`, no git credentials (the runner ff-syncs) | OS sandbox; no MCP; capability matching refuses `delegate/mcp/ask` | Anthropic post-review **pre-push, mandatory** (`REVIEW_PRE_PUSH` forced on); `stale_head → flagged` |
| Completions (HTTP) | n/a (in-process) | none | one vendor HTTPS | one key | **no tools by construction** ("nothing to sandbox") | n/a |
| Script | workspace | clone | as declared | scrubbed | declared command only | n/a |

`ExecSpec` → executor adapter contract *[graft: kernel §1.8]*:

| `ExecSpec` field | `claude_sdk.py` | `codex_cli.py` | `completions.py` | `script.py` |
|---|---|---|---|---|
| `cwd` | `cwd=` (delivery-resolved, `session.py:819-858`) | `--cd <clone>` (workspace only) | n/a | subprocess cwd = clone |
| `system_prompt` (directive + job id + markers + transcript + skill body + context_files) | `system_prompt=` as today (`session.py:664-692`) | written to `AGENTS.md` in the clone (32 KiB cap, `chatgpt-openai.md §2`) + prepended to the prompt | `system` message | ignored |
| `capabilities` | `allowed_tools` via a `Capability → tool name` table; the 9-tool default (`session.py:706-709`) minus `AskUserQuestion` becomes the default set | `--sandbox read-only` unless `write/edit/shell` requested (P6 only); refuse `delegate/mcp/ask` | refuse anything but `structured_output` | refuse anything but `shell` |
| `guard_profile` | `hooks=` via today's `make_guard_hooks`/`make_readonly_guard_hooks` (`guards.py:381, 419`) | OS sandbox + `EnvScrubber` | n/a | `EnvScrubber` |
| `provider`, `model`, `effort` | `model=`, `effort=` passthrough (`agents.py:38-54`) | `-m <id>` pinned (never the picker default; the rate-limit prompt silently retargets Luna), `model_reasoning_effort` | Ollama tag by digest / Gemini `thinking_level` via `effort_map` | n/a |
| `max_turns`, `timeout_s` | `max_turns=`; `wait_for` → `interrupt()` then `kill()` | wall clock from the `--json` stream; SIGTERM→SIGKILL | HTTP timeout | wall clock |
| `mcp_servers`, `subagents` | in-process (`session.py:773`, `:733`) | none | none | none |
| `output_schema` | `output_format={"type":"json_schema",…}` | `--output-schema s.json -o out.json` | `format=` / `response_schema` | n/a |
| `sensitivity` | any | `proprietary` only after D4 (toggle off) and only on the redacted projection | `proprietary` ⇒ local only | any |

`EnvScrubber` contract: child env = `{PATH, HOME, LANG, TMPDIR}` + the executor's own auth dir (`CODEX_HOME`) + nothing else; `delivery.env_files` (`workspaces.py:192-244`) is skipped for every non-Anthropic executor; `executor_started.env_keys` lists what was passed and a test asserts none of `ALPACA_*|TRADIER_*|ANTHROPIC_*|CLAUDE_CODE_OAUTH_TOKEN|GEMINI_*|TELEGRAM_*|DATABASE_URL` appears.

Two `guards.py` edits (protected; one owner PR in P4, D2): (i) add `GEMINI_API_KEY|OPENROUTER_API_KEY|OPENAI_API_KEY|CODEX_API_KEY|XAI_API_KEY|CLAUDE_CODE_OAUTH_TOKEN` to the assignment/export deny beside `ANTHROPIC_API_KEY` (`guards.py:148-149, 261-262` guard the literal name only); (ii) INV-22 server-side deny for `api.tradier.com`, `sandbox.tradier.com/v1/accounts/*/orders`, `*.alpaca.markets/v2/orders` in the hard-deny list (`guards.py:137-149`; `SYSTEM.md:130` open follow-up). The read-only `restart_project` deny moves from the hook regex (`guards.py:485-488`) into `mcp_projects.restart_project_tool` (not protected). Untrusted input (Telegram text, fetched pages, MCP results) reaches only A-rated lanes: Claude `-p` with hooks (Seatbelt opt-in later) and Codex `exec` (`crosscut-tos §3.8a`); HTTP lanes get owner-authored prompts and pre-fetched public documents only.

### 2.7 Event / audit model

All 33 existing kinds and shapes are kept (C14). Added, all appended to the per-job JSONL and mirrored to `jobs:stream:<id>`: `provider_selected{provider, model, reason ∈ pin|policy|fallback|canary, chain}`, `provider_fallback{from, to, cause}`, `executor_started{executor, cli_version, lane, queue_wait_ms}`, `quota_snapshot{provider, window, used_pct, resets_at, source}`, `heartbeat{turn, last_tool, tokens_so_far, elapsed_s}` every 15 s, `job_held{reason, next_check}`, `contract_resolved{checks, on_fail}`, `evidence_check{check, pass, detail}`, `dod_tick{pass_count, total}`, `deliverable_registered{kind, title, ref}`, `done_verdict{verdict, missing[]}`, `merge_gate_verdict{belt, reviewer, verdict, findings_n}`, `grade_done{provider, verdict, score, findings_n}`, `approval_requested/decided`, `notice_queued/sent/failed`, `shadow_decision{provider, agrees, latency_ms}`. `terminal_reason` is stamped on `job_completed`/`job_failed`. JSONL stays the durable trace and the task state-machine input (`main.py:1053-1266`); rows are derived from it, never the reverse, so `reconcile.py` ("last terminal wins") is unchanged. `ScriptExecutor` synthesises `TASK_COMPLETE:` from exit 0 so the marker contract (`session.py:405-460`) covers every executor.

### 2.8 Cost / quota ledger

| Lane | Window source | Per-call ledger | Evidence |
|---|---|---|---|
| Claude Max | typed `RateLimitEvent` → `quota_snapshots(source=vendor)`; `system/api_retry rate_limit` reset time; **optional** owner-run status-line dump for calibration only | full `ResultMessage` (`usage`, `model_usage`, `total_cost_usd` as list-equivalent, `num_turns`, `duration_api_ms`) → `jobs` + `provider_ledger(purpose=main)`; nested calls ledgered by purpose | `claude-anthropic.md §3` [68]; matrix §1 item 7 |
| Codex | `account/rateLimits/read` every 15 min + after each Codex job via a short app-server session | `turn.completed` usage | `chatgpt-openai.md §3, §7` |
| Gemini free | own Redis counter vs 250 RPD (`source=inferred`) | `usage_metadata` | `gemini-google.md §3b` |
| Local | free RAM (`psutil`), `GET /api/ps`; skip when <3 GB free | `eval_count/eval_duration` | `local-models-m4-16gb.md §7` |

`cost_usd_list` is list-price-equivalent computed from tokens per `providers.yml`; cards say "$0 marginal · $0.14 list-equiv". Calibration anchor: the measured job (~100k in at 82 % cache, ~2k out) prices Sonnet-class at ~$0.08 and the whole scheduled load at ~$8-14/month equivalent (`crosscut-finance-trading-ai.md §3`).

## 3) Vendor plan

| Vendor | Surface on this server | Auth | Cost path | ToS status (research) | Task classes | Qualification status |
|---|---|---|---|---|---|---|
| **Anthropic** (trust anchor) | Claude Agent SDK, bundled CLI pinned `>=0.1.81,<0.2` (2.1.139); never `--bare`; `ANTHROPIC_API_KEY` banned (INV-3) | Max `/login` (Keychain) + `CLAUDE_CODE_OAUTH_TOKEN` from `claude setup-token` in launchd env (owner); training toggle off | included; $0 marginal; tier (5x/20x) owner-confirmed | **Allowed\*** — own account, unmodified binary, "ordinary, individual usage"; policy volatile; `--bare` may become `-p` default (`claude-anthropic.md §3, §7`; `crosscut-tos §3.1, §3.7`) | everything agentic; pinned `code-server`, `review-gate`, `_evaluate`, `chat`; trading analyst/validator/governor; utility terminal link | qualified (anchor) |
| **OpenAI Codex** | `codex exec --json --output-schema` (brew-pinned CLI); app-server `account/rateLimits/read`; `ai-mcp` registered in Codex for owner's interactive views | `codex login --device-auth` on ChatGPT **Free** (decision 2026-08-17); one `auth.json` per stream, 0600; "Improve the model" off before any thesis text | $0 (Plus $20 only on measured skip rate, D5) | **Gray/Yes\*** — owner-only, owner-read outputs; API key "recommended" for CI; goals off; `statsig` off (`chatgpt-openai.md §3, §7, §8`) | grader/critic (first adversarial vote) on `research-read`, `trading-research`(redacted), `code-project`; `code-project` writer canary P6 | shadow (P4) → canary (P6) |
| **Google Gemini** | HTTP `generateContent` / OpenAI-compat endpoint on `gemini-3.8-flash` | unpaid AI Studio key, owner-added (decision 2026-08-17) | $0; 250 RPD Flash | **Allowed** for the key; unpaid tier **trains + human review** (`gemini-google.md §3a`); Antigravity/Gemini-CLI OAuth via orchestrator **banned** — not used | `utility-public` (pre-fetched public docs), grader on public-content bundles only | qualified-utility (public only) |
| **Local Ollama** | native `/api/chat` with `format`; `qwen3.5:4b` (routing), `qwen3.5:9b` (extraction), `embeddinggemma`; `OLLAMA_MAX_LOADED_MODELS=1`, `KEEP_ALIVE 10m` | none | $0 | n/a (MIT runtime, Apache-2.0 weights) | `utility-classify` first hop, mechanical checks, embeddings, sentiment labels; never research/coding/review (`local-models §5`) | shadow (P3) → qualified-utility |
| **OpenRouter `:free`** | registered only | key, owner-added | $0; 20 RPM / 50 RPD | Allowed (API); churn; training provider-dependent (`runtimes-aggregators.md §3`) | none in any default chain | probation (registered, unused) |
| **xAI Grok** *(deferred)* | `x_search` sentiment side-car | prepaid key | metered ~$1-5/mo | API Allowed; seat headless Grey (`grok-xai.md §3, §8`) | `sentiment-feed` (feature column, never a signal) | D6, default no |
| **Perplexity** *(deferred)* | Agent API `finance_search` | key | metered | API Allowed; consumer **Banned** | transcripts/estimates beyond EDGAR | D6, default no |
| **Claude Routines** *(deferred)* | `/fire` cold standby for repo-scoped jobs when the Mini is down, mirrored as Jobs | subscription login | draws Max window; daily cap | Allowed (first-party; research preview) | `code-project`/`research-read` only | D14, default off |
| Excluded | Antigravity/Gemini OAuth via orchestrator, Alibaba/Xiaomi token plans, Perplexity consumer, DeepSeek, Kimi/MiniMax as graders of Claude (distillation exposure), LiteLLM/Langfuse daemons, Cursor/Copilot/Kiro seats, any second consumer seat per vendor | — | — | written bans, API-key-only, PRC storage, or RAM floors (`crosscut-tos §3.7, §3.8, §5.2a`; `runtimes-aggregators.md §3(c)`) | — | — |

Onboarding rule for any future lane *[graft: hub §1.8]*: fill the headless capability matrix (create / trigger / collect / status / quota / data terms) before a `providers.yml` entry; a lane that cannot be triggered *and* observed headlessly is not a lane.

## 4) Interfaces and visibility

### 4.1 Grammar (identical strings on Telegram `/verb`, `ai verb`, and `ai_verb` tools)

```
task <text> [--kind=<skill>] [--model=<provider/model|alias>] [--effort=low|medium|high|xhigh|max] [--project=<slug>] [--timeout=<s>] [--watch] [--quiet]
watch <job|task>     jobs [--running|--queued|--held|--failed|--lane=owner]     job <id> [--log|--files|--cost]     queue
cancel <id>          approve <approval-id> [note]     reject <approval-id> [note]     reply <task|job> <text>
schedule list|show <name>|run <name>|pause <name>|resume <name>|edit <name> --cron="<preset|cron>" [--notify=…]|add "<phrase or cron>" --kind=<skill> [--project=…]
providers [status|pause <id>|resume <id>|ladder]     quota     cost [--week|--month] [--by=provider|skill|vertical|lane]
deliverables [<task|job>]     open <deliverable-id>     atlas [status|<vertical>]     proposals [list|show|approve <id>]     project <slug> status|deploy|logs
```

Telegram: bare text = `task`; `/status`, `/tasks`, `/chat`, `/god`, `/resume`, `/projects` unchanged; `/clear` requires a confirm button; the four ghost commands (`/cancel <prefix>`, `/status <prefix>`, `/proposals`) become real and `/rate` leaves the help text (endpoint kept; 👍/👎 only on DeliverableCards). `ai-mcp` (stdio, `mcp<2`) exposes **read-only** tools only: `ai_jobs, ai_job, ai_watch, ai_queue, ai_quota, ai_cost, ai_deliverables, ai_schedule_list, ai_atlas`. No `ai_run/ai_approve/ai_cancel` inside a model context (judge 3 fatal flaw); mutating verbs require Telegram or the PWA.

### 4.2 Cards (Telegram; every card is a `views.py` object)

- **JobCard** (one message per job, edited on phase change and otherwise coalesced to ≤1 edit / 10 s *[graft: multi-bot §2.1]*; `[Mute]` stops edits): phases `queued (lane owner · pos 1 · est 0-2 min)` → `starting (anthropic/claude-opus-5 · workspace clone 3 s)` → `working (turn 12 · 3m40s / 30m · last: Bash pytest -q · files 3 · 41k tok · DoD 2/5)` → `blocked` → `reviewing (gate · post-review · critic: codex)` → Done/Failed. Buttons `[Cancel] [Details] [Open]`; callback `j:<8-char>:c|d|o` (≤64 bytes). Message id persisted in `notifications.external_ref` so a bot restart loses nothing.
- **DoneCard**: verdict lines (gate, post-review, critic CONCUR|DISSENT), `done_verdict` with DoD ticks, deliverables with deep links, cost strip *[graft: multi-bot §2.4]*, `[Reopen] [👍] [👎] [Open]`; flips "done → reviewed" on `jobs:reviewed`.
- **FailedCard**: error class, `terminal_reason`, escalation hop, `[Retry] [Details] [Mute today]`; fires for scheduled jobs too (silent today, state map §5.7).
- **ApprovalCard**: from an `approvals` row (deploy parks here instead of failing), `[Approve] [Reject] [Ask]`.
- **DeliverableCard**: title, kind, 500-char preview, `[Open]` → PWA `/app/d/<id>`, `[Send file]` (Telegram document ≤50 MB).
- **ScheduleCard**: next fire, last outcome, adherence flag (DARK/NEVER_RAN/STUCK/FAILURE_STREAK/LATE/MISSING), `[Run now] [Pause] [Edit]`.
- **QuotaStrip / ProviderPanel**: `anthropic 5h 34 % (resets 14:10) · 7d 61 % · codex 5h 12 % · gemini 88/250 · local ok 5.1 GB free`, breaker state, pause/resume.
- **CostCard** (Monday 08:00 + `/cost`); **AtlasCard** (per vertical runs ok/stale/blocked, last decision, gate status, provisioning gaps); **DailyDigest 07:15** replaces the bash `schedule-monitor.sh` DM via `python -m src.notify digest` on the same launchd timer.

```
▶ RUNNING  c6cfbf6b · atlas-critic · lane owner
   anthropic/claude-opus-5 · high · workspace 7f2a…
   turn 12 · 3m40s / 30m · last: Bash pytest -q · files 3 · 41k tok
   DoD 2/4  ✅ marker  ✅ files_exist  ⬜ git_pushed  ⬜ citations_min
   window 5h 34 % (resets 14:10) · 7d 61 %
   [Cancel] [Details] [Open]

✅ DONE  c6cfbf6b · atlas-critic · 6m12s · $0 marginal ($0.14 list-equiv · 92k tok)
   gate: LGTM · post-review: LGTM · critic (codex): DISSENT (2 findings, 1 high)
   done: verified (4/4 checks · 2 deliverables)
   📄 research/swing-critic-2026-09-24.md   🔗 commit 9d3ebcf
   [Reopen] [👍] [👎] [Open]

⚠️ FAILED  1a9e42c0 · atlas-daily-brief · scheduler · 2m03s
   terminal: api_error 529 · escalation L1 → opus-4-7 queued (job 88c1…)
   [Retry] [Details] [Mute today]

🛂 APPROVAL  ap-3f9c · deploy · server · 3 commits · +212 −40 · pytest green · lint green
   what's deploying: control-plane P1 (grammar, approvals, deliverables)
   [Approve] [Reject] [Ask]

⏸ HELD  4d0e… · atlas-value-monitor · lane atlas
   held: no headroom on anthropic (5h 100 %, resets 14:10) · next check 30 s   [Cancel] [Details]
```

Phase model (single source in `views.py`; same strings on every surface) *[interface-first §2.5]*:

| Phase | Trigger | What the owner sees | Source |
|---|---|---|---|
| `queued` | `enqueue_job` | lane, position, estimated wait from p50 of running jobs | `LLEN jobs:queue:<lane>`, `jobs.started_at` |
| `held` | provider-window gate | reason + next check | `job_held` |
| `starting` | `job_started` | provider/model resolved, clone status, queue wait | `provider_selected`, `executor_started`, `workspace_created` |
| `working` | first executor event, then `heartbeat` | turn, last tool, files, tokens, elapsed/timeout, DoD ticks, window % | `heartbeat`, `tool_use`, `dod_tick`, `quota_snapshot` |
| `blocked` | `approval_requested` / `task_question` | what is asked + buttons; `awaiting_since` age | `approvals` row |
| `reviewing` | post-steps after `jobs:done` | which belts are running (the card never claims "completed" before verdicts) | `merge_gate_verdict`, `grade_done` |
| `done` / `failed` / `reviewed` | `done_verdict` / `job_failed` / `jobs:reviewed` | verdicts, deliverables, cost strip, `terminal_reason`, escalation hop | columns |

Surface coverage (which view renders which object):

| View object | Telegram | PWA | `ai` CLI | `ai-mcp` (read-only) |
|---|---|---|---|---|
| JobCard / DoneCard / FailedCard | edited message | Jobs list + detail | `--watch` lines | `ai_watch` |
| ApprovalCard | buttons | Approvals inbox | `ai approve` | — (deliberately absent) |
| DeliverableCard | preview + Open/Send file | Deliverables browser | `ai open` prints path/URL | `ai_deliverables` |
| ScheduleCard / board | list + per-row buttons | week board | table | `ai_schedule_list` |
| QuotaStrip / ProviderPanel / held queue | one-line strip; `/queue` | Now + Providers | `ai quota`, `ai queue` | `ai_quota`, `ai_queue` |
| CostReport / Scoreboard | weekly card; `/scoreboard` | Cost + Scoreboard | `ai cost` | `ai_cost` |
| AtlasHealth | card | Atlas view | `ai atlas` | `ai_atlas` |
| AlertHistory | — | Alerts view | `ai alerts` | — |

### 4.3 PWA `/app` (static SPA under `static/app/`, no build step, installable)

Views: **Now** (running/queued/held by lane, QuotaStrip, next 6 fires, open approvals), **Jobs** (filterable; detail = live transcript, tool timeline, guard denials, tokens/cost, provider served vs requested, cancel/approve/reply), **Tasks** (turns, plan DAG from `payload.depends_on`, evaluator rounds, `awaiting_since` age), **Schedules** (week board, presets like `weekdays 17:30 America/New_York`, run-now/pause/edit, adherence), **Providers** (windows, breakers, ladder), **Cost**, **Deliverables**, **Approvals**, **Atlas** ("is any of this working"), **Alerts** (outbox history), **Proposals**, **Scoreboard**. Auth: the existing shared token stays; the live stream uses `fetch()` + `ReadableStream` with the bearer header so the SSE token-in-URL (`web.py:600-640`) is retired **without** touching `web.py:49-63` (protected path #2). CF Access, an SSE cookie and Web Push VAPID keys are one owner-approved auth PR (D10), not a P2 dependency. The old inline dashboard (`web.py:646-847`) stays until P5.

### 4.4 `ai` CLI

`src/cli/__main__.py` (stdlib `argparse`): REST client, token from Keychain; `ai task "…" --watch` prints the JobCard phase lines and tails the stream; `ai job <id> --log` tails `volumes/audit_log/<id>.jsonl`; `ai jobs|queue|quota|cost|providers|deliverables|schedule|atlas` render `views.py` tables. Owner terminal work stops appearing as ad-hoc `created_by` strings (`owner-terminal`, `owner-dispatch`, …): `origin_channel=cli`.

### 4.5 Notifications and approvals

`src/notify/` outbox with renderers; retries with backoff; `notice_sent/failed` recorded; per-schedule `notify ∈ {never, failures, always}` keeps machines quiet (default `failures`); `_error_safe`'s self-diagnose auto-dispatch is capped by the breaker (C26). `DeployNeedsApproval` (`main.py:492`) creates `approvals(kind=deploy)` + ApprovalCard with deploy-director's what's-deploying summary; `approve` enqueues the deploy with `approval_id` in payload and `delivery.deploy_permitted` (`delivery.py:75-101`) accepts it. `TASK_QUESTION`/choices become `approvals(kind=question|choice)` so `awaiting_since` is set and stale asks age visibly. `AskUserQuestion` leaves the default tool list (`session.py:706-709`; documented to hang jobs).

## 5) Effectiveness

### 5.1 Definition of done — the Deliverable Contract *[core: outcome-first §3.1]*

Declared in frontmatter `done:`, overridable per job via `payload.contract`, resolved once at session start (`contract_resolved`), and checked by the runner (`ScriptExecutor`) — never by the model.

| Check | Args | Runs | Typical class |
|---|---|---|---|
| `marker_present`, `no_marker` | `TASK_COMPLETE:` present / `TASK_QUESTION:` absent | summary parse | all (default) |
| `claimed_files_exist` | paths named in final text or Write/Edit `tool_use` targets exist post ff-sync | fs | all (default) |
| `budget_within` | tokens / turns / seconds ceilings | columns | all (default) |
| `file_exists`, `glob_matched`, `sections_present`, `word_range`, `citations_min` | path/glob, sections[], min | fs + regex over the file | research-read, memos |
| `git_pushed`, `changelog_touched` | — | ff-sync SHA (`workspaces.py:247-270`), diff names | code-* |
| `tests_ran` | pattern | transcript: a `Bash` `tool_use` matching `pytest|npm test` with a non-failing `tool_result` (weaker; honest) | code-* default |
| `tests_green`, `lint_green` | cmd | runner executes cmd in the clone before ff-sync (opt-in; needs `command:` and the project venv) | code-server, delivery |
| `url_200`, `healthcheck_green` | url | HTTP | project delivery |
| `db_row` | read-only SQL via a read-only atlas role (P5) | atlas DB | trading (`swing.runs` status, `trials.jsonl` line, `value.theses` count) |
| `schema_valid` | JSON schema over structured output | — | utility, grading |

Default contract for every job without a `done:` block: `marker_present ∧ no_marker ∧ claimed_files_exist ∧ budget_within`. Outcome: `done_verdict ∈ {verified, unverified, failed_checks}`; `jobs.status` is untouched. `on_fail` default is `flag` fleet-wide (card + scoreboard); `fail` only for deploy-verify skills (`deploy-director: verify`) where the check *is* the deliverable; trading-ledger checks flag, never fail, so loops cannot go dark on a flaky probe (judge 1 flaw on outcome-first). `fix_round` reuses the evaluator fix loop (`main.py:949-985`, max 2) when a skill opts in. A `done:` block lands on the 10 highest-volume skills in P1 and on every routable class before its lane leaves shadow.

Example (research-report; the optional deliverables block is the only thing the model writes, everything else is runner-observed):

```
<<<DELIVERABLES
- file: projects/research/spy-liquidity-2026-09-24.md
- url: https://atlas.chrispiserchia.com/reports/spy-liquidity
DELIVERABLES>>>
TASK_COMPLETE: liquidity memo committed (9d3ebcf) with 7 cited sources.
```

```json
// <job>.evidence.json (runner-written)
{"contract": "research-report@done", "checks": [
  {"name": "marker_present", "pass": true}, {"name": "claimed_files_exist", "pass": true, "detail": "1/1"},
  {"name": "citations_min", "pass": true, "detail": "7 >= 3"}, {"name": "git_pushed", "pass": true, "detail": "9d3ebcf"},
  {"name": "budget_within", "pass": true, "detail": "92k tok / 200k; 6m12s / 30m"}],
 "deliverables": [{"kind": "file", "path": "projects/research/spy-liquidity-2026-09-24.md", "sha": "…"}, {"kind": "commit", "sha": "9d3ebcf"}, {"kind": "url", "url": "https://…"}],
 "diff": {"files": 1, "insertions": 214, "deletions": 0}, "done_verdict": "verified"}
```

### 5.2 Evidence

`<job>.evidence.json` from (a) check results, (b) auto-detected deliverables (Write/Edit targets under `projects/**`, `docs/**`, `research/**`; ff-sync SHA; PR URLs in final text; `<job>.summary.md`), (c) an *optional* `<<<DELIVERABLES … DELIVERABLES>>>` block (same mechanism as `<<<TASK_PLAN>>>`, `session.py:405-460`; no mandatory `<<<EVIDENCE>>>` ceremony), (d) the workspace diff summary. `deliverables` rows are what cards link; the bundle is what graders read — never the writer's transcript alone.

### 5.3 Review belts — vendor ≠ writer, Anthropic the only LGTM

1. **Evidence checks** (no LLM).
2. **In-session gate**: the `code-review` subagent stays the INV-13 merge gate; its final `VERDICT:` line (the format `skills/code-review/SKILL.md:129-131` already documents) is parsed from the `Task` tool_result into `verdicts(stage=merge_gate)` + `jobs.merge_gate_verdict`. Test: a deploy of a workspace-produced commit without a recorded `lgtm` is refused for non-Anthropic-written commits and warns (card) for Anthropic ones *[graft: hub §8 H2, narrowed]*.
3. **Post-review** (`review.py:247-256`, Anthropic-pinned, reviewer chosen by registry class not by the skill, C5): the 600 s timeout stamps `review_outcome=timeout` + `post_review_flagged` (closes `main.py:616-626`); runs **pre-push on the workspace diff before `sync_canonical` (`session.py:1040`)** when `REVIEW_PRE_PUSH` is on — forced on for non-Anthropic lanes (INV-21(c)), flag-only default on Anthropic lanes (D8) so atlas research pushes never park on review latency (15 `stale_head` skips today).
4. **Grader / critic** (`src/runner/grading.py`, new post-step): picks `grader.provider != writer.provider` from the class policy; runs read-only on the evidence bundle + class rubric (reusing `evals/cases/<skill>.yml`) with structured output `{verdict ∈ CONCUR|DISSENT, score 0-10, confidence, findings[{severity, text, location, kind}], dod_items[]}` *[graft: multi-bot §2.3 vote schema]*; Codex `exec --sandbox read-only --output-schema grade.json`; Gemini-free / local only on the **redacted projection** (§8.3) of public-class bundles; bounded 600 s; error → `verdict=error` ("ungraded" on the card); quota → `skipped`, **never Anthropic**. Kimi/MiniMax/DeepSeek/Qwen never grade Claude output (`crosscut-tos §5.2a`). A `DISSENT` with `severity=high` on a memo that feeds a governor opens `approvals(kind=question)` → owner card.
5. **Independence is measured**: monthly pairwise Jaccard on normalised findings per (grader, anchor) pair; a pair >0.7 is "not a second opinion" and is rotated (`runtimes-aggregators.md §3(g)`).

### 5.4 Scoreboard and qualification ladder

`scoreboard` view keyed `(provider, model, task_class)` over `verdicts ⋈ provider_ledger ⋈ jobs`: `n, dod_pass_rate, unverified_rate, grade_mean, grade_p10, dissent_rate, lgtm_rate, escalation_rate, fail_rate_by_terminal_reason, cost_usd_list_p50, latency_p50/p90, ttft_p50, rate_limited_incidence, quota_share_pct, independence_jaccard, ladder_state`. Served at `/api/scoreboard`, `/scoreboard` (Telegram, PWA, CLI); replaces the never-called `retrospective.skill_performance` (`retrospective.py:39-96`). Ladder per `(provider, task_class)` in `provider_qualifications`: `shadow` (evals with `--provider` persisted to `verdicts(stage=eval)`; `shadow_decision` at the fail-open utility sites) → `canary` (≤10 % of low-stakes live jobs, anchor-graded) → `qualified` → `demoted` (breaker on `dod_pass_rate`/`grade_mean` delta over a rolling 20 jobs, or DISSENT spike). Promotions are `proposals` of the never-used `default-model` kind, owner-approved while a lane is young; demotion automatic. Initial thresholds (tunable by proposal) *[graft: hub §3.1]*: `shadow → canary` needs ≥30 shadow grades with `grade_mean` within 1.0 of the anchor's self-grade and grader error <5 %; `canary → qualified` needs ≥20 canary jobs, `dod_pass_rate ≥ 0.9`, `lgtm_rate ≥` the skill's baseline (49/60 post-reviews today), `unverified_rate` no worse than the anchor's; `qualified → demoted` on any rolling-20 window with `dod_pass_rate < 0.7`, `grade_mean` −1.5 vs anchor, `rate_limited` on ≥3 consecutive runs, or two `auth_expired` in a week (breaker). Judge stays Anthropic (`evals/run.py:48`, INV-21); eval coverage target: one case file per routable skill (7/72 today).

### 5.5 Retrospective

`retro` skill (weekly Sunday; Anthropic read-only, opus-4-7/medium) replaces the idle-triggered `review-and-improve` at opus-4-7/max (28 runs/30 d, ~1.3 M cache-read tokens each, for 11 pending proposals): a `ScriptExecutor` SQL pre-pass produces the tables (per task class: which vendor delivered, DoD, grade, dissent, cost, latency, quota incidents, ladder moves), the LLM writes the narrative to `docs/retro/<week>.md` and files proposals; the idle trigger (`events.py:404-419`) is removed; a monthly CostCard DM rides the first Sunday.

## 6) Scheduling

- **One scheduler of record** (`main.py:1314-1362`); vendor-native schedulers (Routines, ChatGPT/Codex tasks, Gemini Scheduled Actions, Grok) are not producers — none enqueues into `jobs:queue`, most are UI-only, all draw the same windows (matrix §2; `crosscut-tos §3.1`).
- **Lanes (P2)**: `jobs.lane` derived from `created_by` at enqueue (`telegram/web/cli → owner`; `deploy-autopilot/event-trigger/self-diagnose → kernel`; atlas kinds → `atlas`; utility/learning children → `utility`; legacy producers → `background` = the untouched `jobs:queue`). Job loop:

```
# main.py:113-185, same task, slot-before-BLPOP kept (INV-15)
await sem.acquire()
non_owner_running = count(running where lane != owner)
if non_owner_running >= MAX_CONCURRENT_JOBS - OWNER_RESERVED_SLOTS and llen(jobs:queue:owner) > 0:
    keys = [jobs:queue:owner]                                   # strict reservation only when an owner job is waiting
else:
    keys = [jobs:queue:owner, jobs:queue:kernel, jobs:queue:atlas, jobs:queue:utility, jobs:queue]
popped = await redis.blpop(keys, timeout=2)                     # no pop-then-push-back (judge 1 must-fix vs INV-12)
… resolve skill/provider chain …
if not any(window_ok(p) for p in chain):
    audit job_held{reason="no headroom on <p>", next_check=30}; LPUSH jobs:queue:<lane> job.id   # INV-12 front-requeue, per lane
    sleep 30; continue
```

`OWNER_RESERVED_SLOTS=1`; at prod `MAX_CONCURRENT_JOBS=2` the reservation is soft (owner job is *next*, never behind a second atlas job) and becomes strict once in-process utility calls (P3) free the RAM to raise prod to 3 (D1). `tests/test_lanes.py`: owner-next ordering; legacy `jobs:queue` still drained; quota requeue lands at the lane head; breaker not bypassable by lane (C26).
- **Provider-window gate**: a job waits only when every provider in its class chain is red (plan §6f); pinned lanes pause on an Anthropic red window exactly as today; routable/utility lanes keep draining. Fan-out per lane is a token-window budget, not a slot count: start 2 / 2 / 1 / 1 (`crosscut-tos §3.10b`), Codex serialized per `auth.json`, local RAM-guarded.
- **Scheduler tick** (every 30 s): due unpaused rows → if `last_run_job_id` running and `misfire_policy=skip` → `schedule_skipped`; chain = `policy.chain(kind, provider_policy)` (`[anthropic]` for the default `pinned`); no healthy provider → `schedule_deferred{reason=window}` + failures-notify; else `Job(kind, description, payload, lane, schedule_id, provider_hint)`, **commit before RPUSH** (closes the race the retry ladder absorbs, `main.py:196-230`), `next_run_at = croniter.next(slot)` (slot-based), `last_run_job_id` stamped; `kind` validated at enqueue against `list_all()` (retires `JobKind`).
- **Adherence**: `schedule_adherence.py` runs in-process every 30 min in addition to the 07:15 launchd belt; `expects: {artifact, within}` per row flips `LATE`/`MISSING` and DMs *[graft: hub §3-4]*; findings appear on ScheduleCards and the Schedules view.
- **Ownership**: `scripts/seed-schedules.sh` stays the sole payload writer through P4; `owner_edited=true` rows keep cron/payload across deploys (name/desc still overwritten) **only when `governed=false`** — atlas loop rows (`division: atlas` skills) are `governed=true`, and a phone edit on them files a proposal for the LOOP.md §7 front door instead of writing the row (judge 1 must-fix). P5 replaces the 41× `pipenv run python | psql` loop with `schedules.yml` + a Python seeder that validates cron collisions, DST-anchored ET pairs and provider capability.
```yaml
# schedules.yml row shape (P5; seeder validates and is the sole writer for governed rows)
- name: atlas-daily-brief
  cron: "0 7 * * 1-5"            # tz America/New_York; DST pairs generated by the seeder, not hand-commented
  kind: atlas-daily-brief
  payload: {project_slug: atlas, session_timeout_seconds: 3600}
  lane: atlas
  provider_policy: pinned        # pinned (default) | routable | <named chain>
  misfire_policy: skip
  notify: failures
  governed: true                 # LOOP.md §7 front door; phone edits → proposal
  expects: {artifact: file, within: 90m}
```

- **Phone add**: `/schedule add "every weekday 17:30 ET" --kind=atlas-daily-brief --project=atlas` → the local model (schema `{cron, tz, confidence}`) → a confirm button showing the cron and the next three fires → row with payload derived from the kind's project *[graft: multi-bot §2.1]*.
- **Credential canaries as schedules** *[graft: incremental §4]*: daily `claude -p ping` with the `model_usage` assertion, daily `codex exec --ephemeral "ok"` (refresh fires only during use; an idle lane lapses after ~8 days, `runtimes-aggregators.md §3`), Gemini key 200, Ollama `/api/ps`; `setup-token` T−30 d alarm from a recorded mint date; an auth failure parks the lane (`auth_expired`) before the first job of the day.

## 7) Project delivery

1. **Contract**: `projects/<slug>/.context/CONTEXT.md` gains `deliverables:` (build green, healthcheck 200, URL 200, tests, CHANGELOG) → the job's DoD; the delivery contract (`delivery.py:130-147` cwd, `:75-101` authority) and workspace clone + ff-sync (INV-16) are unchanged.
2. **Plan** (Anthropic `plan` → DAG via `plans.py`) with per-subtask checks.
3. **Build**: Anthropic by default; Codex `code-project` canary on non-server repos (pickem, bingo, content-forge; never ai-server, never atlas kernels) only in P6 once `qualified` — `workspace-write`, network off, no MCP, pre-push review mandatory (closes the ff-sync-before-review hole judge 2 found in interface-first/incremental).
4. **Evidence checks** in the clone before anything leaves it.
5. **Gate**: `merge_gate_verdict` recorded; `changes_requested` on a non-Anthropic lane parks the clone (kept, as failures are today) and opens a fix round instead of pushing.
6. **Grader** (cross-vendor, advisory) → `verdicts`.
7. **Push → parked approval → gated deploy**: `deploy_permitted` "needs approval" → `approvals(kind=deploy)` + ApprovalCard; `approve` → deploy job (`server-deploy`/`atlas-redeploy`, unchanged executor skills; `deploy-director: verify` writes `done_verdict`) → `deliverable_registered{url, commit, healthcheck}`; a red gate keeps old code serving and produces a FailedCard with `[Retry] [Open logs]`.
8. **Deliverable card** to the origin channel; Deliverables feed on the PWA. `project <slug> status|deploy|logs` wraps `mcp_projects`; the deploy autopilot moves from `healthcheck-all.sh:204-252` raw SQL to `ScriptExecutor` + `enqueue_job`.

Atlas two-repo copies (15/26 drifted, state map §2.6) get a lint diffing `atlas/integrations/ai-server/skills/` against `skills/` (in the P4 lint PR).

## 8) Trading research within INV-22

### 8.1 What runs where

| Stage (existing atlas loop) | Executor | Change |
|---|---|---|
| Research cycles, theses, quant sweeps, alpha scout, CIO memo | Anthropic (Max; "Help improve Claude" **off** → 30-day retention, `claude-anthropic.md §3`) + Alpaca-paper/EDGAR/Massive/Finnhub MCP | constitution DoD checks: card pre-registered, `trials.jsonl` line before verdict, walk-forward folds, DSR computed, memo sections, no web tools in evaluation runs (`db_row`/`file_exists`/`sections_present`) |
| Adversarial validator | Anthropic clean-context subagent (C22 separated duties) | verdict → `verdicts(stage=grade, provider=anthropic)` |
| **Cross-vendor critic** (new skill `atlas-critic`, staged in `atlas/integrations/ai-server/skills/`) | Codex `exec --sandbox read-only --output-schema critic.json` on the **redacted projection**; local `qwen3.5:9b` for mechanical checks (numbers vs tool outputs, dates ≤ cutoff, link liveness) | writes `DISSENT/CONCUR` + findings to `<vertical>/evaluation/critic.jsonl` and `verdicts(stage=critic)`; additive after the validator, never replaces it; `DISSENT` severity=high on a governor-feeding memo → owner card |
| Governors (grade from DB rows only) | Anthropic read-only | consume `critic.jsonl` and must cite a DISSENT in their grade (LOOP.md §7 amendment, evidence-gated) |
| Paper supervision / sandbox swing decisions (inside the kernel's bounded candidates) | Anthropic sonnet | `db_row` checks make "completed ≠ productive" visible (37/37 `provisioning_gap` runs report success today) |
| Sentiment feature (optional) | xAI `x_search` → append-only snapshot table, overlay tag only, forward-paper only (`grok-xai.md §6`) | **D6, metered, default off** |

Critic contract: `isolation: workspace`, `task_class: trading-research`, `providers: {critic: [codex, ollama-local]}`, `required_tools: [Read, Glob, Grep]`, `sensitivity: proprietary`; input = memo path in a fresh clone + the validator verdict; env = `CODEX_HOME=volumes/codex/<job8>`, **no atlas `.env`** (`env_files` skipped for non-Anthropic executors), network off; cost ≈ one Codex message per memo on Free; Gemini-free only when `memo.sensitivity == public`.

### 8.2 Never

No lane gets an order tool; the only order path stays `atlas/swing/swing/executor.py --submit` behind `risk.validate` (`:535, :599, :621, :640`); Tradier/IBKR remote MCPs (live order tools in the same server, `crosscut-finance-trading-ai.md §3`) stay off the box; the server-side broker-host deny (§2.6) turns INV-22 from docs into a guard. **Tripwire** (scheduled weekly): run the critic against a fixture memo containing `tradier.com/v1/accounts/x/orders` and a fake `TRADIER_SANDBOX_TOKEN=` line; assert no outbound request, no token value in the transcript, and `guard_denied` fires on the Anthropic lane.

### 8.3 Data and credential boundaries

- **Redacted projection** *[core: outcome-first §6.3]*: a deterministic, tested redactor strips positions, sizes, ledger rows, account values and owner identifiers before any non-Anthropic critic sees a memo; Anthropic keeps full context. Codex on plan auth receives thesis text only after the ChatGPT "Improve the model" toggle is verified off (D4) — otherwise public-class memos only.
- **Credential scoping**: `env_files` today copies the whole atlas `.env` into every atlas workspace (`workspaces.py:192-244`); it becomes per vertical in the atlas manifest (atlas PR via LOOP.md §7): Tradier sandbox token only in swing workspaces, vendor keys never in any atlas workspace, non-Anthropic executors never receive atlas env at all (audit assertion on `executor_started.env_keys`).
- **AUP posture**: owner-only research memos, human on the order path, nothing served to a second person — inside every vendor's advice/reliance clause (`crosscut-finance-trading-ai.md §6`); population-scale 2026 evidence says no vendor has directional edge (`§5, §8`), so no vendor is ever a decision-maker.
- **Blockers first (cheap, no vendor work)**: provision `TRADIER_SANDBOX_TOKEN` + `FINNHUB_TOKEN` (owner, D3); patch `weekly.py:316` `KeyError('screen')`; Alpaca→yfinance/Tradier data fallback for the paper trader (9/21 `stale_data`); a `provisioning_gap` pre-check (`ScriptExecutor`) that skips the LLM session when the credential is missing (~45 sessions/month today).
- **Visibility**: the Atlas view/card reads `resolved_provider/model`, `schedule_rollup` (`web.py:175-260`), adherence and per-vertical `*.runs` (read-only atlas role) — the "is any of this working" page (state map §5.25) *[graft: kernel §2.2]*.

## 9) Migration and rollout

Kill switches (env, one line each): `CONTROL_PLANE_V2=0` (legacy Telegram handlers), `NOTIFY_OUTBOX=0`, `LANES_ENABLED=0` (single `jobs:queue`), `CONTRACTS_MODE=observe|enforce`, `GRADING_ENABLED=0`, `REVIEW_PRE_PUSH=anthropic:off,codex:on`, `EXECUTOR_LEGACY_PATH=1` (verbatim `_run_in_process`), `ROUTER_PROVIDERS_ENABLED=anthropic` (plan §2), `providers pause <id>`. Every phase is one migration at most, ships as small server-patch PRs on the INV-4 lane, and is deployed through `server-deploy` gates. What keeps running throughout: all 41 schedules, all 72 skills, the INV-13 gate, the launchd alerters and edge Worker (they gain `notify send`), prod concurrency 2 until D1.

| Phase | Weeks | Scope | Entry | Exit criteria | Kill switch |
|---|---|---|---|---|---|
| **P0 foundations + hygiene** | 0-1 | migration 007; capture the full `ResultMessage` (`session.py:1094-1128`); typed `terminal_reason` (regex kept as belt); `src/notify/` outbox + persisted origin (done/failed DMs for every launch, scheduled included); ghost commands fixed; `/clear` confirm; `AskUserQuestion` off the default list; **Haiku → `claude-sonnet-4-6@low` at `llm_router.py:148`, `learning.py:258`** (retirement ≥2026-10-15); credential canary schedules; ops debt: rclone→R2 off-site backup, `pg_dump atlas`, sealed `.env`/cloudflared copies, `pmset autorestart 1`, stale Ollama weights removed + `qwen3.5:4b`/`embeddinggemma` pulled (D12) | design sign-off; R2 creds | every completed job has tokens/cost/provider in Postgres; a scheduled failure DMs within 60 s; bot restart loses no DM; restore drill passes | `NOTIFY_OUTBOX=0` |
| **P1 control plane + contracts (observe)** | 1-3 | `src/control/` grammar/intents/views/policy; new Telegram handlers beside legacy; live JobCard; migration 008; `approvals` + deploy parking; `deliverables` + auto-detection; durable cancel; schedule run/pause/resume/edit (non-governed) + phrase→cron; `ai` CLI; `src/contracts/` with the default contract and `done:` on the 10 busiest skills, `CONTRACTS_MODE=observe` (verdict shown, nothing blocked); gate verdict captured | P0 | owner launches from the phone, watches, approves a deploy from a card, opens the deliverable; `test_grammar` is the only parser; 100 % of new jobs carry `contract_resolved` + `done_verdict`; legacy handlers still registered with the flag off | `CONTROL_PLANE_V2=0` |
| **P2 visibility + lanes** | 3-5 | migration 009 (`quota_snapshots`, `provider_ledger`, `verdicts`); lanes + owner reservation + `job_held` + `/queue`; `RateLimitEvent` → snapshots; heartbeat + `first_event_at`/`queue_wait_ms`; PWA `/app` (Now/Jobs/Tasks/Schedules/Deliverables/Approvals/Alerts/Cost); post-review timeout stamps; `jobs:reviewed`; DailyDigest; scheduler fixes (commit-before-RPUSH, slot-based, misfire, `expects.within`, `notify`) | P1 | owner-lane job never waits behind two atlas jobs; QuotaStrip shows Claude 5h/7d from live events; Cost view reconciles with JSONL sums for 30 d; `provider_ledger` shows the nested router/review/learning calls | `LANES_ENABLED=0`; PWA opt-in |
| **P3 registry + executor seam + utility lane** (plan R0+R2+R1) | 5-7 | `providers.yml` + `registry/models.py` (anthropic-only entries first) + `routing-policy.yml`; `executors/base.py` + `claude_sdk.py` byte-for-byte; `utility_call` in-process (ollama-local → anthropic-utility; `utility-public` chain with gemini-free on pre-fetched public docs, owner adds key); `script.py`; per-provider quota keys; error-class-gated escalation; prod concurrency → 3 (D1) | P2; owner: Gemini key, Ollama bench | **golden-file gate**: `ExecSpec.to_claude_options()` equals `_build_options` output on 10 recorded skills; audit-replay of 20 recorded jobs identical; fake-executor conformance; router precision on `evals/` router cases ≥ Haiku/Sonnet baseline for 7 d of `shadow_decision`; zero `claude` subprocesses spawned for utility calls; zero owner-private prompts on free lanes (audit assertion) | `EXECUTOR_LEGACY_PATH=1`; `ROUTER_PROVIDERS_ENABLED=anthropic` |
| **P4 Codex read-only lane + grading (shadow) + owner PR #1** | 7-10 | `codex_cli.py` + `EnvScrubber`; device-code login (owner); `grading.py` in shadow on `research-read`; redacted projection; scoreboard v1; evals `--provider` persisted; migration 010 ladder; `retro` replaces review-and-improve; Codex JSONL fixture tests; env-scrub tripwire; **owner PR #1**: `guards.py` vendor-key + broker-host deny, lint rules (policy file, two-repo drift, sensitivity), wire the four unwired checks (allowlist untouched) | P3; owner: Codex login, training toggles off (D4), PR #1 (D2) | ≥100 graded jobs; grader error <5 %; skip-rate on Free measured (feeds D5); Jaccard(codex, anchor) reported; zero guard-equivalent violations; first retro with real numbers | `GRADING_ENABLED=0`; `providers pause codex` |
| **P5 failover + trading critic + polish** | 10-12 | class-aware pause + drill; `atlas-critic` stage + per-vertical `env_files` + constitution DoD + governor amendment (LOOP.md §7, D11); `db_row` via read-only atlas role; `CONTRACTS_MODE=enforce`; `ai-mcp` (read-only); `schedules.yml` + seeder; Atlas view; INV-22 tripwire schedule; Telegram transport extraction; old dashboard removed; monthly cost report | P4; D9, D11 | simulated Anthropic pause drill: pinned lanes pause, routable/utility lanes drain, owner DM'd; critic dissent rate per vertical; no non-Anthropic executor ever launched with atlas env (audit assertion); INV-22 deny test green | per-provider pause; legacy dashboard restorable from git |
| **P6 owner-gated / deferred** | — | Codex `code-project` writer canary (pre-push review); SDK pin bump behind the replay gate (D13); auth PR (CF Access, SSE cookie, Web Push VAPID) (D10); isolation default flip per vertical + allowlist shrink (D16); Routines cold standby (D14); xAI/Perplexity side-cars (D6); ChatGPT Plus (D5) | each its own decision | — | — |

What the owner feels after each phase: P0 — every job DMs, failures DM, `/cancel` works, backups exist; P1 — one-line launch from the phone with a live card, approvals as buttons, deliverables as links, schedules editable; P2 — never waits behind atlas, sees windows and cost, has the PWA; P3 — routing/learning stop spending the Max window, the kill switch to today is one env var; P4 — a second opinion on research memos with measured independence, weekly retro; P5 — an Anthropic red window no longer freezes the fleet, the trading critic runs, the "is any of this working" page exists.

Rollback rule per phase: flip the phase's switch, `git revert` its merge(s); migrations are additive/nullable so a rollback never loses data; reconcile, INV-2, `jobs:done` and the marker protocol are never altered, so a half-migrated runner restarts cleanly. Each phase's PR carries a rollback note naming the switch and the merge SHA.

Test gates per phase (pure/fixture style the repo uses; live stack only for replay and drills) *[graft: incremental §8]*: P0 `test_result_capture` (fake `ResultMessage` → columns), `test_notify_outbox` (renderer limits, retry, delivery status), every `tasks:notify` kind has an outbox equivalent, registry-less Haiku swap smoke; P1 `test_grammar` (every verb/flag/alias; unknown model rejected; legacy handlers with flag off), `test_intents` (approve resumes a parked deploy; cancel of a queued job LREMs; governed-row edit files a proposal), `test_views` (4096 chars, ≤64-byte callback, ≤8 buttons), `test_contracts` (each check kind on fixtures; default contract); P2 `test_lanes` (owner-next, legacy queue drained, INV-12 lane-head requeue, breaker not bypassable), `test_quota_snapshots` (RateLimitEvent → snapshot → `window_ok`), scheduler commit-before-RPUSH; P3 golden files, `tests/replay/` over 20 recorded JSONL jobs, `test_registry` (72 frontmatters + 31 escalation targets resolve; `VALID_MODELS` equals today's set), `utility_call` chain walk on 429/timeout and sensitivity refusal; P4 `test_codex_events` on pinned fixtures, env-scrub assertion (no `ALPACA_*`/`TRADIER_*`/`ANTHROPIC_*`/`CLAUDE_CODE_OAUTH_TOKEN` in the child env), `test_grading` (pairing rule, fallback=skipped), redactor golden files, `test_done_verdict`; P5 `scripts/drill-quota-pause.sh`, INV-22 tripwire, invariant-preservation checklist as tests (INV-2/8/9/12/13/15/16/17/18/20/21/22 and C12) *[graft: kernel §1.9]*.

## 10) Deleted / rewritten / kept

| Element | Verdict | Action |
|---|---|---|
| JSONL audit + `summary.md`; text-marker lifecycle; workspace clone/ff-sync; guard predicates; fail-closed resolution / tighten-only / deploy gate; `enqueue_job` + `jobs:queue` + Job row as truth + slot-before-BLPOP; out-of-band alerters + edge Worker; in-session `code-review` gate; atlas order path + tripwires; SDK `<0.2` + `mcp<2` pins | **Keep** (load-bearing, state map §6) | extend only: kinds, columns, lane keys, verdict recording; the executor seam isolates the fragile SDK edge rather than removing the pin |
| `_build_options` monolith (`session.py:650-816`); `_run_in_process`; `_handle_message` | **Rewrite** (behaviour-identical move) | `ExecSpec` + `claude_sdk.py` behind golden-file + replay gates; first tests for this code ever |
| Four `query()` loops (router, learning, review, judge) | **Rewrite** into `utility_call` (reviewer keeps its agent form, pinned) | in-process; shadow-mode hook |
| `_MODEL_ALIASES` as CI allowlist; web 3-id dropdown; `_MODEL_BUDGETS` (all 200 k) | **Delete** | `registry/models.py`; `test_skill_contracts.py:24` imports the registry |
| Global `quota:paused_until`; banner regex; dropped `ResultMessage` fields | **Replace** | per-provider keys; typed `terminal_reason`; columns |
| `tasks:notify` string vocabulary; `_job_to_chat`; three Telegram senders; `_error_safe` self-diagnose dispatch | **Delete** (outbox + renderers; capped auto-dispatch) | `notify.py` shared by bot, scripts, Worker |
| `Task.chat_id`/`thread_message_id` as the only binding | **Keep columns, stop depending on them** | `origin_*` on jobs and tasks |
| Ghost commands; `/rate` in help; rating buttons on every card; `avg_rating` in rollups | **Delete** | 👍/👎 on deliverables only; endpoint kept |
| `DeployNeedsApproval` failing the job; `AskUserQuestion` in defaults | **Replace** | `approvals` rows; removed from the default list |
| Inline htmx dashboard; SSE token-in-URL | **Rewrite** as static PWA + streamed fetch with bearer header | old route removed in P5; auth checks untouched until D10 |
| `seed-schedules.sh` as sole payload writer; hand cron de-confliction | **Rewrite** (P5) as `schedules.yml` + validating seeder honouring `owner_edited` on non-governed rows | C19 amended narrowly |
| `JobKind` enum, dual kind spellings, `notify` ghost; payload-as-control-plane keys | **Delete enum; keep payload keys, mirror into columns** | `kind` validated at enqueue |
| `self-diagnose` on every L2/L3 regardless of error class | **Rewrite** (error-class gate; provider-down substitution) | 21 % of jobs today |
| `healthcheck-all.sh` (probes + liveness + swing watchdog + autopilot + raw SQL enqueue) | **Split** (doctrine kept) | `ops_probe` + `notify send`; autopilot via `ScriptExecutor` + `enqueue_job` |
| `review-and-improve` at opus/max on idle with raw psql by `kind` | **Replace** with `retro` (SQL pre-pass + weekly narrative) | skill file kept; idle trigger removed |
| `no_llm` dead flag | **Implement** as `ScriptExecutor` | |
| `isolation: none` default + 44-name allowlist (`lint_docs.py:612-635`) | **Keep frozen this cycle** (protected; D16 later) | non-Anthropic lanes are workspace-only regardless |
| Idle Ollama with 14 GB stale weights; no off-site backup; atlas DB outside dump; `autorestart 0` | **Fix in P0** (cheaper than anything above) | |

## 11) Risks and mitigations

| Risk | Mitigation |
|---|---|
| **Anthropic policy/CLI flips** (`--bare` becomes the `-p` default; subscription re-gated) (`claude-anthropic.md §3, §7`) | pin SDK/CLI; never pass `--bare`; `claude -p ping` smoke + `model_usage` assertion on every bump; setup-token and Keychain both present; T−30 d alarm; Codex read-only lane and Routines (D14) as fallbacks for routable classes; kill switch restores today |
| **Hot-path refactor regression (P3)** | behaviour-identical move; golden-file `to_claude_options` equality on 10 skills; audit-replay on 20 jobs; fake-executor conformance; `EXECUTOR_LEGACY_PATH=1`; one live canary per skill class |
| **Telegram is the SPOF and P1 touches it** | new handlers beside legacy; `CONTROL_PLANE_V2=0` tested; transport extraction deferred to P5; launchd alerters and the Worker unchanged |
| **Codex Free capacity unknown; plan auth Gray/Yes\*; `auth.json` lapses when idle** (`chatgpt-openai.md §3, §7`) | grader fallback `skipped`, never Anthropic; owner-only outputs; goals/statsig off; daily canary; one `auth.json` per stream; skip rate measured before any Plus decision (D5) |
| **Thesis text leaks to a training lane** (Gemini unpaid trains + human review; consumer toggles default on) | `sensitivity` on every skill with owner-private defaults for human/transcript text; `utility-classify` chain excludes Gemini; redacted projection tested; env scrub; lint rule `proprietary ⇒ no_training lanes`; quarterly training-toggle checklist card blocks thesis-class routing until stamped |
| **Weekly Max window is the binding constraint** (re-based 2026-09-14; `crosscut-tos §8`) and new belts could burn it | graders on Codex/local, never Anthropic; utility calls leave the window in P3; `retro` replaces the opus/max auditor; chat stays Sonnet-low; `provider_ledger` makes every nested call visible; window forecast on the Schedules view |
| **16 GB RAM** (3.8 GB swap in use; SDK subprocess ~148 MB; local model 3-7 GB) | utility in-process (removes two spawns per job); RAM guard skips local <3 GB free; `OLLAMA_MAX_LOADED_MODELS=1`, short keep-alive; no OTEL collector/LiteLLM/Langfuse; concurrency raised to 3 only after the P3 measurement |
| **Haiku 4.5 retirement ≥2026-10-15 hits router/learning before P3** | one-line swap to `claude-sonnet-4-6@low` in P0 (the pinned CLI knows that id); registry alias later |
| **Reviewer non-independence** (harness effects, distillation) | Codex/Gemini first; monthly Jaccard; distilled lanes never grade Claude; DISSENT is advisory |
| **INV-13 pre-push parks atlas research** (08-17 governor-dark pattern) | pre-push forced only on non-Anthropic lanes; Anthropic lanes flag-only unless D8; timeout stamps a verdict but never blocks on Anthropic lanes |
| **Protected-path bottleneck** | exactly two owner PRs (P4 guards/lint; P6 auth), everything else on the INV-4 lane |
| **Free-tier churn** (accepted 2026-08-17) | every chain terminates in Anthropic utility or local; breakers → `provider_fallback` cards; `:free` links in no chain |
| **Card noise / Telegram edit limits** | coalesced edits, phase-change-only edits, `notify=failures` default for machines, `/mute`, outbox retry with delivery history |
| **INV-22 via atlas `.env` once `TRADIER_SANDBOX_TOKEN` lands** | per-vertical `env_files`; broker-host deny; non-Anthropic executors never receive `env_files`; weekly tripwire |

## 12) Owner decisions required (recommended answer in bold)

1. **D1 Scope and phase gates** as in §9, including prod `MAX_CONCURRENT_JOBS` 2 → 3 after P3's RAM measurement and the strict owner reservation. **Approve.**
2. **D2 Protected-path PR #1 (P4)**: `guards.py` vendor-key deny names + INV-22 broker-host deny; `lint_docs.py` policy/sensitivity/two-repo rules + wiring the four unwired checks; `UNISOLATED_WRITER_ALLOWLIST` untouched. **Approve when P3 exits.**
3. **D3 Auth config by hand (one session)**: `CLAUDE_CODE_OAUTH_TOKEN` (setup-token) in launchd env; `GEMINI_API_KEY` (unpaid); `codex login --device-auth` on Free; `TRADIER_SANDBOX_TOKEN` + `FINNHUB_TOKEN` in atlas `.env`; R2 credentials for backup; confirm Max tier (5x/20x). **Do it before P0 exit.**
4. **D4 Training toggles**: Claude "Help improve Claude" off; ChatGPT "Improve the model for everyone" off; quarterly checklist card. **Yes — precondition for any thesis text to Codex.**
5. **D5 ChatGPT tier**: stay Free; consider Plus $20 only if P4 measures grader skip-rate >30 %. **Free.**
6. **D6 Metered side-cars** (xAI `x_search`, Perplexity `finance_search`, Ollama Cloud Pro): remain declined. **Defer; revisit on critic data.**
7. **D7 Gemini unpaid key scope**: pre-fetched public documents and public-class memo grading only; never Telegram text, transcripts, theses. **Yes.**
8. **D8 INV-13 pre-push on Anthropic workspace lanes** (`REVIEW_PRE_PUSH=anthropic:on`): **Defer** until the scoreboard shows review latency and `stale_head` rates; non-Anthropic lanes are pre-push regardless.
9. **D9 Schedule ownership**: phone edits persist on non-governed rows; atlas loop rows file proposals (LOOP.md §7). **Yes.**
10. **D10 Auth PR (P6)**: CF Access on the dashboard vhost, SSE cookie, Web Push VAPID keys — one protected-path #2 PR. **Approve before the PWA carries approvals as the primary surface (after P2).**
11. **D11 Atlas front door**: `atlas-critic` stage, per-vertical `env_files`, constitution DoD checks, governor "cite the DISSENT" amendment as evidence-gated proposals. **Yes.**
12. **D12 Ops debt in P0**: R2 off-site backup, `pg_dump atlas`, sealed `.env`/cloudflared copies, `pmset autorestart 1`, delete 14 GB stale Ollama weights, pull `qwen3.5:4b` + `embeddinggemma`. **Yes.**
13. **D13 SDK/CLI pin bump** (0.1.81 → 0.2.x bundling a CLI that knows Opus 5.5/Sonnet 5) behind the replay gate + `model_usage` assertion; until then no new Anthropic id enters `providers.yml`. **Schedule after P3.**
14. **D14 Claude Routines `/fire` cold standby** for repo-scoped jobs when the Mini is down. **Defer.**
15. **D15 Codex `code-project` canary targets (P6)**: pickem, bingo, content-forge; never ai-server or atlas kernels. **Defer to P6; approve the list now.**
16. **D16 Isolation default flip per vertical + allowlist shrink** (INV-21(a) precondition; three psql-writing governors affected). **Separate PR after P5, not bundled.**
17. **D17 Definition-of-done default**: skills without a `done:` block show `unverified` (honest) rather than silently `verified`. **Honest.**

## 13) Effort and monthly cost

- **Effort**: P0 1 + P1 2 + P2 2 + P3 2 + P4 3 + P5 2 = **~12 agent-weeks** of session time on the INV-4 lane (one gated deploy per phase; P4 shadow soak is calendar, not effort). Owner time ≈ **15-20 hours**: one credential/login session (~1 h), two protected-path PR reviews (~1 h each), five phase sign-offs (~1 h each), ~1 h/week reading DoneCards, DISSENTs and the first retros.
- **Monthly cost, default plan: $0 incremental.** Claude Max as today ($100 or $200 by tier); ChatGPT Free $0; Gemini unpaid $0; local $0; OpenRouter $0 (unused); Cloudflare free. List-equivalent spend on the scheduled load stays ~$8-14/month-equivalent inside the subscription (`crosscut-finance-trading-ai.md §3`); grading adds ~30-120 short read-only Codex runs and ~100-200 local/Gemini utility calls per month.
- **Optional, each an owner decision**: ChatGPT Plus $20 (D5); xAI prepaid ~$5-10 (D6); Perplexity ~$5 (D6); Ollama Cloud Pro $20 (D6). Worst case with every option ≈ $50-55/month on top of Max. No new always-on daemon; ~150 MB per subprocess executor as today; one ≤3.4 GB local model resident only during its own calls.

## 14) Open questions

1. Owner's Max tier (5x vs 20x) — needed to label the weekly window forecast; not derivable from vendor pages.
2. Does the pinned CLI 2.1.139 honour `sandbox.failIfUnavailable`/`strictAllowlist` for the Claude lane? If yes, Seatbelt for Telegram-originated jobs is a P5 add; if not, it waits for D13.
3. Can the `code-review` subagent return structured output under SDK 0.1.81 `AgentDefinition`? If not, the `VERDICT:` line parse (documented at `skills/code-review/SKILL.md:129-131`) is the P1 mechanism and structured capture waits for D13.
4. Codex Free grader capacity in practice (bands unpublished): the P4 skip-rate measurement decides D5.
5. Will a read-only atlas DB role be acceptable under LOOP.md §6 (dependency/`[system]` ceilings) for `db_row` checks and the Atlas view? Proposal through the §7 front door.
6. Whether the runner should execute `tests_green` in atlas clones (needs the per-run venv the state map calls a recurring failure class) or keep `tests_ran` transcript evidence for atlas until the venv is cached via `env_files`.
7. Telegram edit-rate ceilings for a busy day (several concurrent JobCards): the 10 s coalescing is an assumption to measure in P1.
8. Whether `queue_wait_ms` should count time held for a red window separately (`held_ms`) so lane starvation and quota holds are distinguishable on the scoreboard.
