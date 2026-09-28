# Design: Kernel overhaul — provider-agnostic execution kernel (executors, policy, unified run model)

Architect lens: kernel overhaul. Date: 2026-09-24. Inputs: `current-state-map.md` (state map; `file:line` cites below are its verified numbers), `docs/research/llm-landscape-2026-09/*` (cited as `<doc> §n`), `docs/superpowers/plans/2026-08-10-model-router.md` (the APPROVED plan; cited as `plan §n`). Hard constraints honoured throughout: INV-3 (no `ANTHROPIC_API_KEY`), INV-22/MISSION §M (no order path), INV-4 protected paths, INV-21 (Anthropic trust anchor; non-Anthropic only workspace-isolated), 16 GB M4 / prod concurrency 2, subscription-and-free-tier-only spend (owner decisions 2026-08-17, plan §10).

---

## 0) Thesis

The server does not need a new architecture; it needs its one vendor-shaped organ replaced and its vendor-neutral skeleton promoted to first-class. Everything that makes the system trustworthy is already executor-agnostic and load-bearing — the Job row + `jobs:queue` + slot-before-BLPOP loop (`main.py:113-185`), the per-job JSONL audit log and `<job>.summary.md`, the text-marker lifecycle protocol (`session.py:405-460`), the fail-closed skill resolution, the workspace clone + ff-sync containment (`workspaces.py:127-170, 247-270`), the pure guard predicates (`guards.py`, 254 real denials), and the in-session `code-review` gate (state map §6). Everything that blocks a second provider is accidental and small: one 166-line `ClaudeAgentOptions` builder (`session.py:650-816`), one 85-line SDK loop (`session.py:1048-1132`), an isinstance-dispatch event handler (`session.py:1138-1170`), four copy-pasted `query()` loops (`llm_router.py:145-159`, `learning.py:255-269`, `review.py:247-261`, `evals/run.py:48,74-100`), a UI alias table doubling as the CI model allowlist (`telegram_bot.py:122-134` → `tests/test_skill_contracts.py:24`), and one global quota key (`quota.py:21`). The overhaul therefore is: (1) extract an `Executor` protocol with a vendor-neutral `ExecSpec` in and a normalized `ExecEvent` stream out, making today's path the byte-identical `ClaudeSdkExecutor`; (2) add three executors — `CodexCliExecutor` (agentic second lane, OS-sandboxed), `CompletionsExecutor` (one-turn HTTP: Gemini key, local Ollama, Haiku terminal fallback), `ScriptExecutor` (the dead `no_llm` flag, implemented); (3) replace the global pause with a per-lane policy/quota/breaker engine that admits a job only when a lane in its class has headroom; (4) land a unified Run model — provider, lane, tokens, cost, turns, terminal reason, priority, origin, deliverables — as columns, plus an `agent_events` ledger that is the single visibility sink for every surface; (5) keep Anthropic pinned on `code-server`, `review-gate` and `_evaluate` (INV-21, C4) and add non-Anthropic work only as workspace-tier, env-scrubbed, sandboxed, Anthropic-reviewed lanes. The system keeps running throughout because the executor call site is a single line (`main.py:376-380`) behind a kill switch, and every migration adds columns and event kinds without renaming any contract a consumer reads.

---

## 1) Architecture

### 1.1 Text diagram

```
 Surfaces            Telegram bot ── web app (CF Access) ── owner CLI ── REST/SSE ── out-of-band alerters
                          │ enqueue_job() (jobs.py:16, unchanged shape; + origin_channel/ref, priority)
                          ▼
 Queue               Postgres jobs row  +  Redis jobs:queue:p0 | jobs:queue   (slot-before-BLPOP kept, INV-15)
                          │
 Runner main loop    _job_loop ── admission: policy.select(task_class, caps, sensitivity) ∩ lane headroom
                          │           (held → job_held audit + visible in queue view; never silently stuck)
                          ▼
 Kernel              run_session(job)  →  ExecSpec (prompt, cwd, caps, guard profile, model/lane, limits)
 (src/kernel/)             │
                    ┌──────┴────────────┬──────────────────────┬─────────────────────┬────────────────┐
 Executors          ClaudeSdkExecutor   CodexCliExecutor       CompletionsExecutor    ScriptExecutor
                    (today's path,      (codex exec --json,    (HTTP one-turn: gemini  (no_llm skills:
                     hooks+MCP+agents)   Seatbelt, env-scrub)   key, ollama-local,      SQL rollups,
                          │                    │                haiku via SDK query)    adherence, seeds)
 Containment        SdkHookAdapter      OsSandboxAdapter+      no tools (rank-1        declared cmd,
                    (guards.py preds)   EnvScrubber+clone      injection posture)      workspace, scrub
                          └──────────────┴──────────────────────┴─────────────────────┘
                                                   │  ExecEvent (normalized)
                                                   ▼
 Ledger              audit JSONL (kinds unchanged +5 new)  ·  Redis jobs:stream:<id> (richer)  ·  agent_events table
                     jobs columns (provider, lane, tokens, cost_usd_est, turns, terminal_reason, deliverables)
                                                   │
 Policy plane        providers.yml · models.yml · routing-policy.yml · schedules.yml (tracked data)
                     lane_quota_snapshots (vendor-read or inferred) · breakers · provider_qualifications
                                                   │
 Post-steps          DAG promote → Anthropic post-review (pinned) → optional 2nd-belt (Codex/Gemini) →
                     writeback → learning (utility lane) → DoD check → task lifecycle → notify.py (all channels)
```

### 1.2 Components (new package `src/kernel/`, consumed by `src/runner/`)

| Module | Responsibility | Replaces / extracts from |
|---|---|---|
| `kernel/spec.py` | `ExecSpec{cwd, system_prompt, user_prompt, capabilities:set[Capability], guard_profile, lane, model_id, effort_tier, max_turns, timeout_s, mcp_servers, subagent_skills, output_schema, sensitivity}`; `Capability ∈ {read, write, edit, shell, search, fetch, ask, delegate, mcp, structured_output, session_resume}` | the five fused seams in `_build_options` (prompt 664-692, resolution 694-724, subagents 730-736, guards 752-755, MCP 757-796) |
| `kernel/events.py` | `ExecEvent{kind ∈ text\|thinking\|tool_use\|tool_result\|guard_denied\|rate_limit\|api_retry\|system\|heartbeat\|result, tool_name, tool_category, payload}`; `ExecResult{final_text, usage(normalized), cost_usd_est, num_turns, duration_api_ms, model_served, terminal_reason ∈ ok\|api_error{status}\|rate_limited\|max_turns\|interrupted\|timeout\|auth_expired\|unrecognized_model, permission_denials}` | isinstance dispatch at `session.py:1141-1169`; banner regex `session.py:495-534`; dropped fields at `session.py:1095` |
| `kernel/executors/base.py` | `Executor` protocol: `describe()→ExecutorInfo{caps, guard_adapters, cli_version}`, `start(spec)→AsyncIterator[ExecEvent]`, `interrupt()`, `kill(grace_s)`; conformance test with a fake executor | the single call site `main.py:376-380` |
| `kernel/executors/claude_sdk.py` | today's `_build_options` + `_run_in_process` moved **behaviour-identically**; reads the whole `ResultMessage` (`total_cost_usd`, `num_turns`, `duration_api_ms`, `model_usage`, `stop_reason`, `api_error_status`, `permission_denials` — SDK 0.1.81 `types.py:1144-1158`); asserts `model_usage` contains the requested model and `duration_api_ms>0` (the silent `unrecognized_model` success, `claude-anthropic.md §7`) | `session.py:650-816, 1048-1132` |
| `kernel/executors/codex_cli.py` | `codex exec --json --ephemeral --sandbox {read-only\|workspace-write} -m <model> --cd <clone> [--output-schema]`; maps `item.*`/`turn.completed`/`turn.failed` to `ExecEvent`; config forced per job: `features.goals=false`, `otel.metrics_exporter="none"` (default is `statsig`), `analytics.enabled=false`, `web_search` per skill (`chatgpt-openai.md §3, §7`); SIGTERM→SIGKILL on cancel/timeout | new |
| `kernel/executors/completions.py` | one-turn (or bounded few-turn) HTTP: `gemini` (`google-genai`, `GEMINI_API_KEY`, `response_schema`), `ollama-local` (native `/api/chat` with `format=<schema>`, `think=false`, memory guard), `anthropic-utility` (Haiku/Sonnet-low via SDK `query()` — the included-cost terminal link, plan §6c); schema-validate-and-retry once | the four copy-pasted loops |
| `kernel/executors/script.py` | `no_llm: true` skills run `command:` from frontmatter in the workspace under the same Job/audit/stream contract, zero tokens | dead `no_llm` (`skills.py:55`), bash sprawl in `healthcheck-all.sh:191-240` |
| `kernel/providers/registry.py` | loads `providers.yml` + `models.yml` → `Provider{id, kind, auth, cost_class, data_class, trust}`, `Lane{provider, auth_mode, concurrency, windows}`, `Model{id, provider, context_window, list_price, effort_map}`; single source for aliases, `VALID_MODELS`, web dropdown, budgets | `_MODEL_ALIASES` (`telegram_bot.py:122-134`), `_MODEL_BUDGETS` (`session.py:466-471`), `web.py:689-691`, 5 hardcoded ids |
| `kernel/providers/policy.py` | `select(task_class, required_caps, sensitivity) → [Lane]`: capability filter → data-class filter → trust floor (qualification state) → health/headroom → ranked; emits `provider_selected{lane, reason∈pin\|policy\|fallback\|canary}`; **unknown provider/model fails the job** (C12) | routing gaps; plan §6d |
| `kernel/providers/quota.py` | per-lane `lane:{id}:paused_until`, window counters (5h/7d/day), breaker (closed/open/half-open), pollers: Claude status-line probe (`rate_limits.five_hour/seven_day`, `claude-anthropic.md §3`), Codex `account/rateLimits/read` (`chatgpt-openai.md §3`), Gemini RPD counter vs 250, local RAM; writes `lane_quota_snapshots{source=vendor\|inferred}` | `quota.py:21-92` global key; INV-12 semantics preserved per lane |
| `kernel/providers/credentials.py` | preflight per lane at runner start and daily (`claude -p ping`, `codex login status` + no-op exec to force refresh, Gemini key 200), mint-date alarms (setup-token T−30 d; Codex T−7 d) — `crosscut-subscription-automation-tos.md §3.10c` | `_check_subscription_auth` (`main.py:70-104`) |
| `kernel/containment/adapters.py` | `SdkHookAdapter` (today's PreToolUse binding, `guards.py:381-490`), `ToolServerAdapter` (projects/dispatch tools exposed over stdio MCP with the predicates *inside* the tool — moves the `restart_project` deny from the hook regex `guards.py:488` into `mcp_projects.restart_project_tool`), `OsSandboxAdapter` (maps `protected_roots()` + workspace path into Codex `--sandbox` / Claude `sandbox.failIfUnavailable+strictAllowlist`), `EnvScrubber` (allowlist env for non-Anthropic lanes; no `env_files` unless the skill declares and the lane's data class permits) | hook-only containment (C9) |
| `kernel/ledger/` | `agent_events` writer + JSONL mirror; `costing.py` list-price estimator per `models.yml` (subscription lanes: `cost_usd_est` shown as "API-equivalent", marginal $0) | `audit_log.py:12` "no cost" |
| `src/notify.py` | one outbound client (Telegram now; channel-agnostic renderers) used by bot, runner, scripts, Worker fallback | three independent senders (state map §2.3) |
| `src/cli.py` | `ai job run\|watch\|list\|cancel`, `ai lanes`, `ai schedule …`, `ai cost` — canonical owner launcher (`created_by=owner-cli`) | ad-hoc `created_by` strings |

`guards.py` predicates are **not** modified by the kernel (protected path); only their transport changes. The three protected edits the design needs are bundled into one owner PR (§11 D2).

### 1.3 Data model changes (alembic 007–010; additive, no renames)

| Migration | Change |
|---|---|
| 007 `jobs` run columns | `resolved_provider` (String 32), `resolved_lane` (String 48), `executor` (String 24), `input_tokens`, `cache_read_tokens`, `cache_write_tokens`, `output_tokens` (BigInteger), `cost_usd_est` (Numeric 10,4), `num_turns`, `duration_api_ms`, `queue_wait_ms`, `terminal_reason` (String 32), `model_served` (String 64), `cli_version` (String 24); backfill from `result.usage` for the 642 rows that have it |
| 008 control plane | `jobs.priority` (0 owner/1 system/2 atlas-batch), `jobs.task_class`, `jobs.sensitivity`, `jobs.origin_channel` + `origin_ref` (replaces `Task.chat_id`/`thread_message_id` binding, `models.py:284-286`; old columns kept one release), `jobs.deliverables` JSONB, `jobs.dod_status` (met/unmet/n-a), `jobs.merge_gate_verdict`; new `job_attempts(job_id, attempt, lane, model, effort, reason, parent_job_id)` replacing `payload.escalation_level` (fixes the auto-continue inheritance bug, `main.py:1231-1237`); `kind` validated at enqueue against `list_all()` (retire `JobKind`, `models.py:60-79`) |
| 009 ledger | `agent_events(ts, job_id, lane, executor, model, kind, tool_name, tool_category, tokens_in, tokens_out, cache_read, cache_write, cost_usd_est, latency_ms, http_status, rate_limit_hit)`; `lane_quota_snapshots(lane, window, used_pct, resets_at, source, ts)`; `provider_qualifications(provider, task_class, state, evidence JSONB, updated_at)`; `eval_results(case, lane, model, score, verdict, baseline, ts)` |
| 010 schedules | `schedules.task_class`, `providers_allow` JSONB, `priority`, `misfire_policy` (skip\|catch_up_one), `lane_concurrency`; seeded from tracked `schedules.yml` by a Python seeder that validates cron collisions and DST pairs (replaces hand-commented `seed-schedules.sh:22-47`) |

Redis: `jobs:queue` kept; `jobs:queue:p0` added (owner/interactive); `lane:{id}:*` keys replace `quota:paused_until`; `jobs:stream:<id>` gains kinds (`tool_result` preview, `guard_denied`, `rate_limit`, `heartbeat{elapsed_s, tools, tokens_so_far}`, `progress`) — additive, the SSE consumer at `web.py:611-640` keeps working. `jobs:done:<id>` semantics unchanged (INV-2 / consumers); a new `jobs:reviewed:<id>` fires after post-steps so completion cards can wait for `review_outcome` when the skill opts in.

### 1.4 Skill frontmatter (backward-compatible)

`model:` accepts `[provider/]model_id` (bare → `anthropic/`, C17); new optional `task_class`, `providers: {allow, deny}`, `sensitivity: public|internal|proprietary`, `done: {deliverables: [globs], evidence: [tests|diff|url|ledger_row], acceptance: "…"}`, `command:` (with `no_llm: true`), `escalation.on_failure` generalised to a list of `{provider, model, effort}` hops. Lint (new rules in `lint_docs.py`, protected): non-Anthropic provider ⇒ `isolation: workspace`; pinned classes ⇒ `anthropic/`; provider must exist in `providers.yml`; `proprietary` sensitivity ⇒ lanes with `data_class: no_training`. `SkillConfig.model` stays a raw string with derived `provider`/`model_id` so `test_agents.py:33-56` and `test_registry_failclosed.py:58-61` keep passing.

### 1.5 Routing policy (`routing-policy.yml`, initial)

| task_class | Lanes (ranked) | Pin / note |
|---|---|---|
| `code-server` (server-patch, new-skill, deploys) | anthropic only | **pinned** (C4) |
| `review-gate` (code-review subagent, post_review, `_evaluate`) | anthropic only | **pinned**; second belt is *additive* (§3) |
| `utility-classify` (llm_router, learning, summary compaction) | ollama-local → gemini-free (public prompts only) → anthropic-utility | never spends Max weekly capacity first (`00-comparison-matrix.md §3`) |
| `chat` | anthropic Sonnet-class `effort=low` | Telegram TTFT ≈2 s measured (`claude-anthropic.md §5`); flagships never interactive |
| `research-read` (research-report, atlas reads on public data) | anthropic → codex (owner-only output) → gemini-free (public only) | freely routable |
| `code-project` (app-patch, non-server repos) | anthropic → codex canary (capped share) | Claude review LGTM required for every Codex diff (INV-21c) |
| `review-second-belt` | codex read-only → gemini (paid key if approved, else public-only) | independence ranking `crosscut-subscription-automation-tos.md §5.2a` |
| `trading-research` / `trading-critic` | anthropic (training toggle off) / codex-or-gemini second vote on non-proprietary memos | §6 |
| `summarize-bulk` | gemini-free (public) → ollama-local (≤8k) → anthropic Sonnet | |
| `no-llm` | script | |

### 1.6 Containment matrix (INV-17/20/21 equivalents per executor)

| Executor | Tier allowed | Filesystem | Network | Secrets | Tool veto | Review of diffs |
|---|---|---|---|---|---|---|
| Claude SDK | none (allowlist), workspace, host(god) | clone or shared | via SDK; Seatbelt opt-in at workspace tier with `sandbox.failIfUnavailable`+`strictAllowlist` (`crosscut-tos §3.8a`, rating A) | inherits launchd env; `env_files` per manifest | PreToolUse hooks (`guards.py:381-490`) | in-session code-review + post-review |
| Codex CLI | **workspace only** | per-job clone only; `protected_roots()` never inside | `--sandbox workspace-write` = network off by default (`chatgpt-openai.md §3`); `read-only` for reviews | `EnvScrubber`: PATH/HOME/CODEX_HOME/LANG only; no atlas `.env`; no git push credentials — the runner ff-syncs (`workspaces.py:247-270`) | OS sandbox + no MCP initially (capability matching keeps MCP skills on Claude; Codex `default_tools_approval_mode=writes` makes stdio MCP possible later via `ToolServerAdapter`) | Anthropic post-review **mandatory and pre-push** for this lane |
| Completions | n/a (in-process HTTP) | none | HTTPS to one vendor | one key | no tools by construction (rank 1 for untrusted input) | n/a |
| Script | workspace | clone | as declared | scrubbed | declared command only | n/a |

Three protected-path edits are required (one owner PR, §11 D2): add `GEMINI_API_KEY|CODEX_API_KEY|XAI_API_KEY|OPENROUTER_API_KEY` to the guard deny list beside `ANTHROPIC_API_KEY` (`guards.py:148-149, 261-262`); add broker-host deny patterns (`api.tradier.com`, `sandbox.tradier.com/v1/accounts/*/orders`, `paper-api.alpaca.markets/v2/orders`, `api.alpaca.markets`) to `guards.py:137-149` — the INV-22 server-side deny that `SYSTEM.md:130` lists as open; register new lint rules in `lint_docs.py`.

### 1.7 Event / audit model

Audit kinds are the parsing contract for reconcile, learning, retrospective, INDEX and the task state machine (C14) — none are renamed. Five kinds are added: `provider_selected`, `provider_fallback`, `executor_started{executor, cli_version, lane}`, `lane_quota_snapshot`, `job_held{reason}`. Every executor adapter emits the same shapes (`text`, `tool_use{tool_name,tool_use_id,input}`, `tool_result`, `thinking`, `guard_denied`, `rate_limit_status`, `job_completed{duration_seconds,usage}`) plus a canonical `tool_category` so `review._summarize_tool_usage`, learning's Write/Edit gate and `retrospective.parse_read_events` keep working across vendors. The final-text markers (`TASK_COMPLETE:` etc.) remain the lifecycle seam for all executors; `ScriptExecutor` synthesises `TASK_COMPLETE:` from exit 0.

### 1.8 `ExecSpec` → executor mapping (the adapter contract)

| `ExecSpec` field | ClaudeSdkExecutor (`to_claude_options`) | CodexCliExecutor (`to_codex_args`) | CompletionsExecutor | ScriptExecutor |
|---|---|---|---|---|
| `cwd` | `cwd=` (delivery-resolved, `session.py:819-858`) | `--cd <clone>` (workspace only) | n/a | subprocess cwd = clone |
| `system_prompt` (directive + job id + markers + transcript + skill body + context_files) | `system_prompt=` as today (`session.py:664-692`) | `--append`-style: written to `AGENTS.md` in the clone (32 KiB cap, `chatgpt-openai.md §2`) + prepended to the prompt | `system` message | ignored |
| `capabilities` | `allowed_tools` from a `Capability→tool name` table (Read/Write/Edit/Bash/Glob/Grep/WebSearch/WebFetch/Task/mcp__*) — the 9-tool default at `session.py:706-709` becomes the default capability set | `--sandbox read-only` when no `write/edit/shell`, else `workspace-write`; `web_search` cached/live iff `search`; refuse if `delegate`/`mcp`/`ask` requested | refuse anything but `structured_output` | refuse anything but `shell` |
| `guard_profile` (`read-only` / `workspace` / none) | `hooks=` via `SdkHookAdapter` (`session.py:753/755`) | `OsSandboxAdapter` + `EnvScrubber`; `read-only` ⇒ `--sandbox read-only` | n/a | `EnvScrubber` |
| `lane`, `model_id` | `model=` (bare id) | `-m <id>` pinned (never the picker default) | SDK model / Ollama tag by digest | n/a |
| `effort_tier` (low/medium/high/xhigh/max) | `effort=` passthrough (`agents.py:38-54`) | `model_reasoning_effort` none/low/medium/high/xhigh/max (`chatgpt-openai.md §7`) | `thinking_level` (Gemini low/medium/high) / `think=false` (Ollama) via `models.yml effort_map` | n/a |
| `max_turns`, `timeout_s` | `max_turns=`; `asyncio.wait_for` (`main.py:376-380`) → `interrupt()` then `kill()` (today timeout never interrupts) | runner-enforced wall clock from the `--json` stream; SIGTERM→SIGKILL | HTTP timeout | wall clock |
| `mcp_servers`, `subagent_skills` | `mcp_servers=` in-process (`session.py:773`), `agents=` (`:733`) | none in P4; `ToolServerAdapter` stdio later | none | none |
| `output_schema` | `output_format={"type":"json_schema",…}` | `--output-schema schema.json -o out.json` | `response_schema` / `format=` | n/a |
| `sensitivity` | any | `proprietary` only if the ChatGPT training toggle is verified off (D4) | `proprietary` ⇒ local or paid Gemini only | any |

### 1.9 Invariant-preservation checklist (asserted by tests in P1)

INV-2 exactly one terminal audit event per job (executor result → single `job_completed`/`job_failed`); INV-8 cancel within 2 s (`interrupt()` then `kill(grace_s=1.5)` on every executor); INV-9 `_finish_job` never overwrites `cancelled`; INV-12 quota exhaustion requeues at the front — now per lane; INV-13 reviewer fixed by registry class, fail-closed on error and on timeout; INV-15 startup order and slot-before-BLPOP unchanged; INV-16 clone fail-closed, ff-sync only on success; INV-17/20 hook binding under `bypassPermissions` unchanged for Claude, OS-sandbox equivalent for Codex; INV-18 `god` host-only, rejected at every launcher including the CLI; INV-21 non-Anthropic ⇒ workspace + sandbox + scrub + Anthropic review; INV-22 no executor may reach a broker endpoint (deny patterns + env scoping); INV-3 the literal `ANTHROPIC_API_KEY` is still exited-on at start (`main.py:77-84`) and denied in sessions; C12 unknown provider/model fails the job at spec build, never falls back to a default.

---

## 2) Interfaces & visibility

### 2.1 Telegram (phone) — registered commands after the overhaul

| Command | Behaviour |
|---|---|
| `/task <text> [--model=provider/id --lane= --effort= --project= --kind= --priority=]` | as today (`telegram_bot.py:150-180`); `--model` validated against the registry; creates Task + Job with `origin_channel=telegram`, `priority=0` |
| `/run <skill> [flags]` | direct skill launch (kind validated at enqueue) |
| `/status [prefix]`, `/cancel <prefix>`, `/rate <prefix> 1-5`, `/proposals` | the four ghost commands (state map §5.13) implemented or removed from help; `/cancel` reaches queued jobs (LREM + flip) |
| `/watch <prefix>` | edits one message every 10 s from `jobs:stream`: `⏱ 4m12s · lane anthropic/sonnet · 23 tools · last: Bash(pytest) · ~180k cache-read/9k out · est $0.08` until terminal; stops on done |
| `/lanes` | card per lane: `anthropic  5h 42% ↻14:00 · 7d 61% ↻Mon · breaker closed · 2/2 slots`; `codex  5h 12% (vendor) · 1/1`; `gemini-free  RPD 37/250`; `local  RAM ok`; buttons `pause/resume <lane>` |
| `/cost [7d\|30d]` | tokens + API-equivalent $ by lane × skill; "subscription marginal $0" line |
| `/schedule list\|run <name>\|pause\|resume\|edit <name> cron=…` | schedules as data; `run` = run-now with same payload |
| `/queue` | queued/held/running with reason (`held: no headroom on anthropic; next reset 14:00`) |
| `/deliverables <prefix>` | file paths / commit / project URL recorded in `jobs.deliverables` |
| `/clear` | requires `/clear confirm` |

Cards (via `notify.py`, rendered per channel): **progress** (lane, tool count, elapsed), **completed** (summary[:3200] + deliverable links + review outcome when available + Reopen), **failed** (now also for scheduled jobs — origin binding is persisted, so the 97 % of jobs that never DM'd today do), **held/blocked** (lane exhausted, reset time), **lane events** (breaker open, credential expiring in 7 d, free-tier churn), **question/choices/plan/approval** unchanged.

### 2.2 Laptop — web app and CLI

Web (static app served from `static/`, behind Cloudflare Access like atlas; the single shared token remains for the API): **Jobs** (live SSE render of `jobs:stream`, cancel button, attempt chain, deliverables), **Tasks** (turns, approve/reopen/reply), **Lanes** (per-window used %, source vendor/inferred, resets_at, breaker, concurrency, credential age), **Queue** (p0/p1, held reasons), **Schedules** (run-now/pause/edit, adherence findings inline), **Cost & usage** (tokens/cost by lane×skill×day; chart from `agent_events`), **Trading health** (per-vertical `*.runs` status, last governor grade, adherence, model/lane used — the "is any of this working" page), **Providers** (qualification ladder state, provider scoreboard §3.4), **Proposals**. New routes: `/api/lanes`, `/api/telemetry/providers`, `/api/telemetry/cost`, `/api/jobs/{id}/deliverables`, `POST /api/schedules/{id}/run`.

CLI: `ai job run research-report "…" --lane codex --watch` streams the same events to the terminal; `ai lanes`; `ai cost 30d`; `ai schedule run atlas-daily-brief`. This is the canonical owner launcher (state map §2.3 "no canonical CLI").

### 2.3 Vendor apps

The kernel is the system of record; vendor apps are optional read views. Claude Code `--cloud`/Remote Control and Routines (`claude-anthropic.md §2-3`) can run repo-scoped jobs when the Mini is down (fired from a `ScriptExecutor` step via `/fire`), and the owner sees them in the Claude app — the run is mirrored as a Job with `executor=claude_routine` and polled status. Codex cloud tasks and ChatGPT scheduled tasks are **not** used as a scheduler (no API cron, shares the plan window; `chatgpt-openai.md §2`). Gemini Scheduled Actions are owner-personal only. Claude Code "channels" Telegram plugin is research-preview and needs a resident interactive session — not adopted; the existing bot stays the phone surface.

### 2.4 Cost / quota / schedule visibility — sources of truth

| Signal | Source | Freshness |
|---|---|---|
| Anthropic 5h/7d used % + reset | short interactive probe session with a statusLine command writing `rate_limits.*` to a file every 30 min (`claude-anthropic.md §3`); `-p` jobs feed the `system/api_retry` error + reset time | 30 min / real-time on limit |
| Codex 5h/weekly | `account/rateLimits/read` at scheduler start and after each Codex job (`chatgpt-openai.md §3`) | per job |
| Gemini free | own counter vs 250 RPD (`gemini-google.md §3`) | exact |
| Local | `vm_stat` free RAM; skip local if < 3 GB (`local-models-m4-16gb.md §7`) | per call |
| Per-job tokens/cost | `ExecResult` → `jobs` columns + `agent_events`; OTEL from Claude Code/Codex optional (Prometheus `:9464` scrape) — no collector daemon in phase 1 (`runtimes-aggregators.md §3(c)`) | per job |
| Schedule adherence | existing `schedule_adherence.py` + lane dimension; immediate failure DMs | real-time |

---

## 3) Effectiveness

### 3.1 Definition of done
Frontmatter `done:` block (§1.4). After `job_completed`, the runner checks `deliverables` globs in the workspace/canonical, required evidence kinds (tests ran = `tool_use Bash(pytest)` + non-zero output, diff = git diff non-empty, url = healthcheck 200, ledger_row = atlas DB row), and that the final text carries `TASK_COMPLETE:` with an `EVIDENCE:` list. Result → `jobs.dod_status`; `unmet` triggers the same escalation path as failure only if the skill sets `done.strict: true` (default: flag + card). `deliverables` paths/commits/URLs are stored and linked from every completion card (state map §5.10).

### 3.2 Evidence and review
- INV-13 post-review stays Anthropic-pinned and fixed by the registry (`review.py:250` → `review-gate` class). Two gaps closed: the 600 s timeout stamps `review_outcome=timeout` and flags (today it emits `post_review_skipped` with no verdict, `main.py:620-626`); for workspace jobs the review runs **before** `sync_canonical` (`session.py:1038-1043`) so a `changes_requested` parks the clone instead of landing it — behind `REVIEW_PRE_PUSH=1`, default on for non-Anthropic lanes, owner decision for Anthropic lanes (§11 D9).
- The in-session `code-review` subagent's verdict is recorded structurally: the subagent ends with a `mcp__dispatch__record_verdict` call (ToolServerAdapter) or a parseable `VERDICT:` line → `jobs.merge_gate_verdict`.
- **Second belt (additive, never the gate):** `review-second-belt` runs Codex `codex exec --sandbox read-only --output-schema review.json` or Gemini one-shot on the same diff/memo, mapped to the existing `ReviewOutcome`, fail-closed on error, stored as `second_belt_outcome`. Pairwise finding overlap (Jaccard on normalised findings) is computed monthly; a pair above ~0.7 is not independent and is swapped (`runtimes-aggregators.md §3(g)`).

### 3.3 Grading and evals
`evals/run.py` gains `--lane`, judge selected via registry but Anthropic-pinned (`review-gate`), results persisted to `eval_results`; cases added for every routable class (research-read, code-project, review-second-belt, utility-classify, trading-critic) before any lane graduates. Human ratings (2/1633) are demoted to optional; the scoreboard uses collectible signals: judge score, `review_outcome`, `second_belt_outcome`, `dod_status`, escalation-needed, `merge_gate_verdict`, turn efficiency, cost.

### 3.4 Provider scoreboard and qualification ladder
`retrospective.skill_performance` (zero callers today, `retrospective.py:39-96`) is wired with `group_by lane` and surfaced at `/api/telemetry/providers` and `/lanes`. Ladder per (provider, task_class) in `provider_qualifications`: `shadow` (evals + shadow decisions on the fail-open utility sites emitting `shadow_decision{lane, agrees, latency_ms}`) → `canary` (policy `canary_share` ≤ 20 % of low-stakes jobs; post-review + evaluator watch) → `qualified` → `demoted` (breaker on failure-rate delta ≥ 15 pts over 20 jobs). Promotion/demotion are review-and-improve proposals of the never-used `default-model` kind, owner-approved while a lane is young (plan §6g).

### 3.5 Measured routing
`routing_decision` confidence is thresholded (below 0.6 → generic workspace task, never a guess); owner `--kind` corrections are captured as ground truth; the LLM router (77/93 decisions today) moves to the utility lane with a local first stage and Haiku/Sonnet-low terminal link. **Time-sensitive:** the router and learning classifier are pinned to `claude-haiku-4-5-20251001` (`llm_router.py:148`, `learning.py:258`), which Anthropic retires "not sooner than 2026-10-15" (`claude-anthropic.md §1`) — Phase 3 must land or the fallback must swap to Sonnet `effort=low` before then.

---

## 4) Scheduling across vendors

- **Schedules are data.** `schedules.yml` (tracked; per row: name, cron, kind, payload, task_class, providers_allow, priority, misfire_policy, timeout) → Python seeder (validates collisions, DST-anchored ET pairs, kind exists, lane exists) → DB rows; the seeder is the sole writer (C19 preserved; `seed-schedules.sh` becomes a wrapper). `/schedule edit` and the web form write the YAML through a `server-patch`-style PR for atlas rows (LOOP.md §7 front door) and directly for non-atlas rows.
- **Admission is lane-aware.** `_scheduler_loop` (`main.py:1327-1362`) commits before RPUSH; `_job_loop` asks `policy.select` for a lane with headroom before taking the job: headroom = vendor-read used % (Codex) or inferred (Anthropic probe / own ledger) below the class threshold, breaker closed, lane concurrency free, RAM guard ok. No lane → `job_held` (visible in `/queue`), re-checked every 30 s; pinned classes wait for Anthropic exactly as today (INV-12 requeue-at-front semantics kept per lane).
- **Fan-out per lane** starts at the researched defaults — anthropic 2, codex 1 (one `auth.json` per serialized stream, `runtimes-aggregators.md §3(a)`), gemini 1, local 1 in its own window (no resident model during job windows) — and rises only after a week of clean `rate_limit`-free telemetry (`crosscut-tos §3.10b`). The global `MAX_CONCURRENT_JOBS=2` stays as the host RAM ceiling for subprocess executors; completions calls are in-process and do not take a slot (today's nested router/learning/review calls each spawn a `claude` subprocess — moving them to HTTP removes two ~148 MB spawns per job).
- **Priority.** `jobs:queue:p0` (owner/interactive) is popped first; when p0 is non-empty the next freed slot goes to p0 (no preemption). Atlas batch rows carry `priority=2`; MISSION "kernel ops win" is now code.
- **Misfire policy** per schedule (`skip` default; `catch_up_one` for daily briefs); `next_run_at` advanced from the slot, not `now`.
- **Cross-vendor failover** is a chain that terminates in an included-cost provider (Anthropic Haiku/Sonnet or local) — owner decision 2026-08-17 #3; a churned free tier becomes `provider_fallback` + a lane card, never a silent gap.
- **Vendor-native schedulers** (Claude Routines ≥1 h cron; Codex/ChatGPT scheduled tasks; Gemini Scheduled Actions) are not the scheduler: none exposes a run-status API the server can join on, all draw the same plan windows (`runtimes-aggregators.md §2`). Routines are the sanctioned "Mini-down" fallback for repo-only jobs, mirrored as Jobs.

---

## 5) Project delivery path

Kept: the delivery contract (`delivery.py:75-147`, topology, `env_files`, deploy-authority gate before session), per-job clone + ff-sync (INV-16), deploy-director/server-deploy executors, atlas gated redeploy. Added:
1. **DoD + deliverables** on every delivery skill (app-patch, atlas-build, project-redeploy): globs, tests evidence, healthcheck URL; completion cards link commit + project URL.
2. **Codex canary on `code-project` only** — non-server repos (pickem, bingo, content-forge, atlas dashboard UI) at ≤20 % share once shadow evals pass; never `code-server`, never atlas trading kernels (`swing/`, `trader/`, `risk`), never anything under `projects/<slug>/.env`. Every Codex diff gets Anthropic post-review **pre-push** (INV-21c); the writer's vendor never reviews its own lane (C5).
3. **Two-repo atlas skill lint**: a lint rule diffs `atlas/integrations/ai-server/skills/` against `skills/` (15/26 already drifted, state map §2.6) — additive lint, not protected.
4. **Deploy autopilot** moves from `healthcheck-all.sh:204-252` raw SQL into `python -m src.runner.ops_probe` using `enqueue_job` (removes the second bash-side enqueue).
5. Web launches create a Task (today `POST /api/jobs` never does, `web.py:399-405`) so plan/evaluator/approval cards exist for laptop work.

---

## 6) Trading research automation within INV-22

**Boundary restated in code terms:** no ai-server executor may reach a broker order endpoint; the only order path stays `atlas/swing/swing/executor.py --submit` behind `risk.validate` (C11). The kernel adds two mechanical enforcements (owner PR, §11 D2): broker-host deny patterns in `guards.py` and per-vertical `env_files` scoping so `TRADIER_*` reaches only the swing workspace and **never** a non-Anthropic lane (`EnvScrubber` default-deny). Tradier's remote MCP ships live order tools (`crosscut-finance-trading-ai.md §3`) — it stays off the server; Alpaca MCP runs paper-only by absence of live keys.

| Work | Lane | Why this vendor | Data boundary |
|---|---|---|---|
| Theses, research memos, validator, governor grading, CIO memo, alpha scout | anthropic (Max; "Help improve Claude" **off** → 30-day retention, `claude-anthropic.md §3`) | only lane with MCP + subagents + hooks; Vals finance podium | `sensitivity: proprietary` |
| Second-vendor adversarial critic (DISSENT/CONCUR ledger line) **after** the Anthropic validator | codex `--sandbox read-only` (ChatGPT plan; owner-only output) — or gemini paid key if D5 approves | highest independence from Claude (`crosscut-tos §5.2a`); Anthropic validator stays the gate (C22 separated duties) | plan-auth Codex only after the ChatGPT "Improve the model" toggle is off (`chatgpt-openai.md §3`); otherwise public-content memos only |
| Filing/earnings digestion (10-K sections, transcripts), decoy rounds, headline classification | gemini-free (250 RPD, Flash) | Vals Finance Agent v2 #1; trains on content → **public data only** (`gemini-google.md §3a`) | `sensitivity: public` enforced by policy |
| News/headline sentiment labels, embeddings dedup, alpha-idea triage | ollama-local `qwen3.5:4b` + `embeddinggemma` (after the 14 GB of stale weights are removed) | $0, nothing leaves the box; the documented fit (`local-models-m4-16gb.md §6-7`) | any |
| X sentiment as a **feature column** (deterministic ingestion → append-only snapshot table → overlay tag, forward-paper only) | xAI API `grok-4.3` + `x_search` with ≤20 allowed handles and a date window | only programmatic social feed (`grok-xai.md §6`) | **metered prepaid — owner decision D6**; never a signal, never a decision-maker |
| Transcripts/estimates beyond EDGAR | Perplexity Agent API `finance_search` | only vendor-native finance tool (`crosscut-finance §1`) | metered — D7, optional |
| Data plane | Alpaca paper MCP (IEX real-time ws), `sec-edgar-mcp`, `mcp_massive` Basic (5/min, cache), Finnhub free | all free (`crosscut-finance §1`) | owner provisions `FINNHUB_TOKEN`, `TRADIER_SANDBOX_TOKEN` (P0) |

What "automate trading" delivers: every research/critic/governor loop runs on schedule across vendors with a visible lane, cost, DoD (ledger row written, memo committed) and the trading-health page; paper/shadow loops keep their frozen evaluators; no new decision path. The 2026 evidence says LLMs have no directional edge and mis-size (`crosscut-finance §5`), which is exactly why the value is in grounded memos, proposer-behind-frozen-referee, monitoring and cross-vendor dissent. Before adding vendors, the blocking plumbing is fixed (state map §2.6): provision the two tokens, patch `weekly.py:316`, add an Alpaca→yfinance/Massive data fallback, cache the per-run venv.

---

## 7) Vendor plan

| Vendor / lane | Surface | Auth | Cost path | ToS status (research) | Task classes | Containment / data |
|---|---|---|---|---|---|---|
| **Anthropic — Claude Max → Agent SDK / `claude -p`** (primary, trust anchor) | ClaudeSdkExecutor (SDK-bundled CLI; no `--bare`, ever) | `/login` Keychain + `CLAUDE_CODE_OAUTH_TOKEN` from `claude setup-token` (1-year; T−30 d alarm) | subscription; API-equivalent shown for information; `ANTHROPIC_API_KEY` banned (INV-3) | **Yes\*** — unmodified binary, own account, "ordinary individual usage"; policy reversed 4× in 2026; `--bare` may become `-p` default (`claude-anthropic.md §3`, `crosscut-tos §3.1/§3.7`) | all pinned classes, chat, research, code, trading-research | hooks + optional Seatbelt; training toggle off; owner-only outputs (non-owner pages stay static) |
| **OpenAI — ChatGPT plan → Codex CLI** (second agentic lane) | CodexCliExecutor `codex exec --json` | `codex login --device-auth`; `~/.codex/auth.json` 0600, one copy, serialized; daily no-op exec to refresh | ChatGPT **Free** (owner decision 2026-08-17 #2; Luna-class, "explore" capacity) → Plus $20 only on canary evidence (D4) | **Gray/Yes\*** — owner-only, owner-read outputs; API key is OpenAI's recommended path; goals off; `statsig` metrics off (`chatgpt-openai.md §3/§8`) | review-second-belt, research-read, code-project canary, trading-critic (non-proprietary unless training toggle off) | workspace only, Seatbelt, network off, env-scrubbed, no MCP initially, Anthropic pre-push review |
| **Google — Gemini Developer API (unpaid key)** | CompletionsExecutor (`google-genai`) | `GEMINI_API_KEY` (no expiry) | $0, 250 RPD Flash (owner decision #4) | **Yes** — but **trains on content + human review** (`gemini-google.md §3a`); Antigravity/Gemini-CLI OAuth via orchestrator is a written breach — not used | utility-classify, summarize-bulk, filing digestion, decoy rounds, public-memo second belt | no tools; `sensitivity: public` only; paid Tier 1 (~$3–17/mo) unlocks proprietary second belt — D5 |
| **Local — Ollama GGUF + (optional) Apple Foundation Models** | CompletionsExecutor native REST | none | $0 | n/a; LM Studio excluded (no-SaaS EULA) | utility-classify, extraction, embeddings, ≤8k summaries | RAM guard; `OLLAMA_MAX_LOADED_MODELS=1`, `KEEP_ALIVE 10m`, KV q8; not used for coding/research (30–50 % fabricated repo facts, `local-models §5`); the Claude-Code-on-Ollama env recipe (`ANTHROPIC_API_KEY=""`) is **not** used, to keep INV-3 mechanically clean |
| **xAI API** (optional) | HTTP via OpenAI-compatible client | `XAI_API_KEY` | prepaid credits, ~$5–10/mo at cents/job (`grok-xai.md §4/§7`) | **Yes** for the API; SuperGrok headless not recommended (opaque pool, AUP "bots") | X-sentiment feature feed only | metered → **D6**; no-training + 30-day delete on the API lane |
| **OpenRouter free tiers** (approved 2026-08-17 #3) | CompletionsExecutor | key | $0 | Allowed | last-resort utility link only | 20 req/min, 50/day, provider variance and empty-completion incidents (`runtimes-aggregators.md §5`) — kept in `providers.yml` as `trust: probation`, not in any default chain |
| **Credit-bundled subs** — Ollama Cloud Pro $20 / Mistral Pro $15 (optional) | CompletionsExecutor | key | subscription credits | Allowed (`crosscut-tos §3.7`) | bulk summarize; non-owner-facing pages | **D7**; Ollama Cloud has no structured outputs |
| Hosted harnesses (Claude Managed Agents, OpenAI Agents API), Alibaba Coding Plan, Antigravity via orchestrator, Perplexity consumer, Kimi/MiniMax/DeepSeek for theses | — | — | — | API-key-only or written prohibition or trains/PRC (`crosscut-tos §3.7/§3.8`) | **excluded** | — |

---

## 8) Migration & rollout

Every phase ships behind a flag, keeps the old path callable, and is gated by `pytest` + `lint_docs.py` + the replay test. Prod concurrency stays 2. Nothing in atlas schedules changes until Phase 6.

| Phase | Weeks | Scope | Entry | Exit criteria | Keeps running / kill switch |
|---|---|---|---|---|---|
| **P0 Ops hygiene** | 0–1 | rclone→R2 off-site backup + `pg_dump atlas` + sealed `.env`/cloudflared copies + `scripts/restore.sh`; `pmset autorestart 1`; remove 14 GB stale Ollama weights, pull `qwen3.5:4b` + `embeddinggemma`; mint `setup-token`; verify Claude training toggle off; `codex login --device-auth` on Free; Gemini key; pin CLIs under brew | owner provides R2 creds, keys | restore drill passes; `claude -p ping` + `codex exec "ok"` + Gemini 200 green from launchd env | no code-path change |
| **P1 Kernel seam** | 1–3 | `src/kernel/{spec,events,executors/base,executors/claude_sdk}`; `run_session` builds `ExecSpec` and calls the executor; full `ResultMessage` capture; migration 007; `registry/models.py` feeding aliases/`VALID_MODELS`/dropdown/budgets; `utility_call` seam for the four loops (still Anthropic); conformance test with a fake executor | P0 | **replay gate**: recorded SDK message fixtures for 5 skill classes → byte-identical audit event sequence; 1434 tests green; one live canary per skill class; `jobs.cost_usd_est` populated | `KERNEL_EXECUTORS_ENABLED=claude_sdk` and `KERNEL_LEGACY_PATH=1` restores `_run_in_process` verbatim |
| **P2 Visibility** | 3–5 | `agent_events` + JSONL mirror; lane quota pollers; origin binding (migration 008 part); `notify.py`; Telegram ghost-command fixes, `/watch`, `/lanes`, `/cost`, `/queue`, failed-DMs for scheduled jobs; web static app behind CF Access; `src/cli.py` | P1 | 100 % of jobs have origin + completion/failure notification; `/lanes` shows Anthropic + Codex vendor-read numbers; SSE rendered | old dashboard route kept at `/legacy` for one release; CF Access is an auth-config change → owner approval (D11) |
| **P3 Policy + utility lane** | 4–6 | `providers.yml`, `routing-policy.yml`, `policy.py`, per-lane quota/breakers, class-aware admission, p0 queue, `job_attempts`; `CompletionsExecutor` (local, gemini-free, anthropic-utility); router + learning on the utility chain with `shadow_decision`; `ScriptExecutor` for adherence, retrospective SQL pre-pass, seeder; **Haiku retirement swap** | P1 | shadow agreement ≥ Haiku baseline on router eval cases for 7 days; quota-pause drill: pinned lanes park, routable lanes drain; zero Max quota spent on routing | `ROUTER_PROVIDERS_ENABLED=anthropic` reverts to today's behaviour (plan §2) |
| **P4 Codex lane** | 6–9 | `CodexCliExecutor`; `OsSandboxAdapter`, `EnvScrubber`; owner PR for guards.py deny list + lint rules; shadow evals on `research-read`/`review-second-belt`; canary on second belt then `code-project` on one non-critical repo | P3 + D2 merged | shadow evals pass; canary diffs reach Anthropic LGTM at ≥ skill baseline; zero guard-equivalent violations; concurrency 1 with clean `rate_limit` telemetry; credential canary green 14 days | `codex` lane `paused` in `/lanes`; capability matching keeps MCP/subagent skills on Claude regardless |
| **P5 Effectiveness** | 8–11 | DoD + deliverables; `merge_gate_verdict`; second-belt review + overlap metric; pre-push review flag; eval persistence + `--lane`; provider scoreboard; qualification ladder; `schedules.yml` + seeder; review-and-improve on SQL pre-pass + cheaper model | P2, P3 | `dod_status` on 100 % of delivery jobs; first provider scoreboard with ≥ 50 jobs per lane; first monthly cost report DM | per-feature flags; ratings UI removal is cosmetic |
| **P6 Trading** | 10–12 | P0 plumbing (tokens, `weekly.py:316`, data fallback, venv cache); per-vertical `env_files` + INV-22 deny (in the same owner PR as P4 or a second one); critic stage; local sentiment/embeddings; sentiment feed if D6; trading-health page; atlas two-repo lint | P4, D13 | swing runs `ok` not `provisioning_gap`; critic ledger lines present; no non-Anthropic lane ever holds `TRADIER_*`/`ALPACA_*` (env audit event) | atlas schedules untouched until this phase; each new stage is a separate schedule row that can be paused |

Rollback at any phase = flip the flag, `git revert` the migration's data use (columns stay, nullable). Reconcile, INV-2, `jobs:done` and the marker protocol are never altered, so a half-migrated runner restarts cleanly.

---

## 9) Deleted / rewritten / kept

**Deleted (accidental complexity, state map §6):** `_API_TERMINAL_BANNER` regex (`session.py:495-534`) → typed `terminal_reason`; `_MODEL_BUDGETS` (all 200 k, cosmetic) → `models.yml` context windows; `_MODEL_ALIASES` as allowlist (`telegram_bot.py:122-134`) → registry-fed alias map, `VALID_MODELS` from registry; `JobKind` enum + `notify` ghost + dual kind spellings; `_job_to_chat` in-process dict and `Task.chat_id`/`thread_message_id` as the only binding (after one release); the four copy-pasted `query()` loops; the raw-SQL deploy-autopilot enqueue in `healthcheck-all.sh:239-244`; the inline-HTML dashboard string (`web.py:646-847`); ghost commands and the dead `on_quality_gate_miss` key; rating buttons on every card (endpoint kept); `payload.escalation_level`/`depends_on` as control plane → `job_attempts` + columns (payload still accepted for one release); per-run venv bootstrap in trading skills → cached via `env_files`; `no_llm` as a dead flag → implemented.

**Rewritten (behaviour-preserving first, then extended):** `_build_options` → `ExecSpec` + `to_claude_options`; `_run_in_process` → `ClaudeSdkExecutor`; `_handle_message` → event adapter; `quota.py` → per-lane; escalation `main.py:704-853` → attempt chain with error-class gating (quota/auth/network never spawn `self-diagnose` — 21 % of all jobs today); `_scheduler_loop` (commit-before-RPUSH, slot-based `next_run_at`, misfire policy); `_update_task_after_job` reads structured events alongside the JSONL (JSONL kept as input); Telegram notify paths → `notify.py`; web → static app; `review-and-improve` → ScriptExecutor SQL pre-pass + LLM only on the delta; `seed-schedules.sh` → YAML + Python seeder.

**Kept (load-bearing):** audit JSONL + summary files and all 33 kinds; text-marker protocol; `workspaces.py` clone/ff-sync; `guards.py` predicates and profiles; fail-closed skill resolution, tighten-only isolation, deploy-authority gate, API-terminal reclassification (now typed); SKILL.md frontmatter as runtime contract; `enqueue_job` + `jobs:queue` + Job-row-as-truth + slot-before-BLPOP; `reconcile.py`; `events.py` breaker/idle triggers (bypass-proof by cheaper providers, C26); `review.py` Anthropic pin + in-session `code-review` gate; `delivery.py`; the atlas order path and tripwires; out-of-band launchd alerters and the edge dead-man Worker (now calling `notify.py` but still runner-independent); the SDK `<0.2` + `mcp<2` pins for as long as the replay gate is the only safety net — the executor boundary isolates that edge so a later bump (D8) is one adapter change.

---

## 10) Risks & mitigations

| Risk | Mitigation |
|---|---|
| Anthropic re-gates `-p`/SDK billing or makes `--bare` the `-p` default (auth break) (`claude-anthropic.md §3/§7`) | pin SDK/CLI; never pass `--bare`; smoke test asserts "Login method: Claude account" on every bump; setup-token + Keychain both present; Codex lane and Routines as fallback for routable classes; `provider_fallback` cards |
| Pinned SDK 0.1.81 bundles CLI 2.1.139; newer models (Opus 5.5, Sonnet 5, Fable 5.1) return a **silent empty success** on old CLIs | `ClaudeSdkExecutor` asserts `model_usage` ∋ requested model and `duration_api_ms>0`; bump only behind the replay gate (D8) |
| Haiku 4.5 retirement ≥ 2026-10-15 breaks router/learning | P3 utility chain or a one-line swap to Sonnet `effort=low` before the date |
| Codex plan-auth is Gray; Free-tier capacity unknown; goal mode burns windows; `auth.json` corruption under concurrency; ban risk | owner-only outputs; goals off per job; concurrency 1 with one credential; daily probe; lane breaker; `/lanes` shows vendor-read headroom; evidence gate before paying for Plus |
| Gemini unpaid key trains on content and is human-reviewed | policy `data_class` gate: `proprietary` never routes there; lint rule; `sensitivity` on every atlas skill |
| 16 GB host: three subprocess executors + a resident 6.6 GB model swap the box (3.8 GB swap in use today) | utility calls in-process; local lane RAM guard (<3 GB free → skip); `OLLAMA_KEEP_ALIVE 10m`, no resident model during job windows; per-executor-class semaphores under the global 2 |
| Hot-path refactor regression | behaviour-identical extraction first; replay gate on recorded fixtures; one live canary per skill class; legacy path flag for one release |
| Reviewer independence lower than assumed (distillation disclosures; harness carries results) | second belt from Codex/Gemini only; overlap metric monthly; distilled lanes only as third vote or mechanical checks (`crosscut-tos §5.2a`) |
| Free-tier churn (250 RPD, OpenRouter delistings) exactly when failover is needed (owner accepted risk #3) | every chain terminates in Anthropic utility or local; breaker + card; chains never load-bearing on `:free` |
| Protected-path edits stall the plan | one bundled owner PR (guards deny lists, lint rules, allowlist flip) reviewed once; everything else unprotected |
| Codex MCP unavailable → dispatch-chained atlas stages can't move lanes | accepted; capability matching keeps them on Claude; `ToolServerAdapter` later with `default_tools_approval_mode=writes` |
| Vendor CLI churn (Codex ~3 stable/week, Claude Code 10 releases/10 days) | brew-pinned versions; nightly `--version` + one-prompt smoke test; `cli_version` stamped on `executor_started`; a lane that breaks twice a quarter is demoted to manual |
| Visibility sink grows into a second DB stack | Postgres `agent_events` + JSONL only; no Langfuse (16 GiB), no LiteLLM daemon (4 GiB floor, March 2026 compromise) (`runtimes-aggregators.md §3(c)`) |

---

## 11) Owner decisions required

1. **D1 — Scope and phase gates** as in §8 (kernel extraction, four executors, per-lane policy, unified Run model).
2. **D2 — One protected-path PR**: `guards.py` deny list gains vendor key names and broker-host patterns (INV-22 server-side deny); `lint_docs.py` gains the provider/sensitivity/two-repo rules and shrinks `UNISOLATED_WRITER_ALLOWLIST` per vertical (flip default to `workspace` for atlas workers); executor skill docs updated. MISSION §M and PROTOCOL.md untouched.
3. **D3 — Anthropic account facts**: confirm Max tier (5x/$100 vs 20x/$200), confirm "Help improve Claude" is **off**, mint `claude setup-token` (owner-side, one browser step).
4. **D4 — ChatGPT tier**: stay Free for P4 probing (current decision) and pre-approve Plus $20 **only if** P4 canary shows the second belt carries load; also turn "Improve the model for everyone" off on the account before any thesis text reaches Codex.
5. **D5 — Gemini**: keep the unpaid key (public-data only, current decision) **or** add paid Tier 1 (~$3–17/mo, no training, `gemini-google.md §4`) to unlock a proprietary-safe second belt. Default assumed: unpaid.
6. **D6 — xAI prepaid credits (~$5–10/mo)** for the X-sentiment feature feed. This is new metered spend; default assumed: **no**.
7. **D7 — Credit-bundled bulk lane** (Ollama Cloud Pro $20 or Mistral Pro $15) and Perplexity `finance_search` (metered). Default: **no**; not required by any phase.
8. **D8 — SDK pin bump** from 0.1.81 to a 0.2.x that bundles a CLI recognising Opus 5.5/Sonnet 5/Fable 5.1, behind the replay gate. Without it the fleet stays on Opus 5/4.8/4.7 + Sonnet 4.6 (fine until Feb 2027 retirements).
9. **D9 — INV-13 pre-push review** on Anthropic workspace lanes (fail-closed) vs flag-only today. Non-Anthropic lanes are pre-push regardless.
10. **D10 — Priority lane**: owner/interactive jobs pop first (no preemption); confirm "kernel ops win over Atlas" as code.
11. **D11 — Dashboard behind Cloudflare Access** (auth config = protected) and removal of ghost commands/rating buttons.
12. **D12 — DR**: R2 destination/credentials for the off-site backup and `pmset autorestart 1`.
13. **D13 — Provision** `TRADIER_SANDBOX_TOKEN` and `FINNHUB_TOKEN` in the atlas dev `.env` (auth config).
14. **D14 — Codex canary targets** for `code-project`: which non-server repos (proposed: pickem, bingo, content-forge; never atlas trading kernels).
15. **D15 — Hosted harnesses** (Managed Agents, OpenAI Agents API) remain declined (API-key-only); confirm.

---

## 12) Effort and cost

**Effort.** ~12 calendar weeks of agent time with P2/P3 and P5/P6 overlapping (roughly: P0 0.5 w, P1 2 w, P2 2 w, P3 2 w, P4 3 w, P5 3 w, P6 2 w; ~14.5 agent-weeks serialised). Owner time ≈ 1.5–2 days total: the 15 decisions, three credential/browser steps (setup-token, `codex login --device-auth`, Gemini key), R2 credentials, two tokens, review of one protected-path PR, and two ten-minute probes (parallel `claude -p` fan-out; Gemini TTFT) the research docs ask for.

**Monthly cost.** Under the current owner decisions the incremental spend is **$0/month**: Claude Max (already paid), ChatGPT Free, Gemini unpaid key, local Ollama, OpenRouter free (unused by default). Optional lines if approved: ChatGPT Plus $20 (D4), Gemini Tier 1 ≈ $3–17 (D5), xAI ≈ $5–10 (D6), Ollama Cloud Pro $20 or Mistral Pro $15 (D7) — worst case ≈ $70/month, and the research's own calibration says the whole scheduled load would cost ≈ $8–14/month metered (`crosscut-finance-trading-ai.md §3`), so every optional lane is a policy choice, not a capacity need. Host resources: no new always-on daemon; ~150 MB per subprocess executor as today; one ≤3.4 GB local model loaded only in its own window; no OTEL collector until a second OTEL lane earns it.
