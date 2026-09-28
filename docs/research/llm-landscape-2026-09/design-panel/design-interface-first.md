# Design: Interface-first — one command grammar, one control plane (2026-09-24)

Lens: start from the owner's hands. Every surface (Telegram on the phone, PWA/web and the `ai` CLI on the laptop, Claude Desktop / Codex as MCP clients) is a *view* of one typed state and speaks one grammar. Multi-vendor routing is a feature behind that plane, not the plane itself. Citations: `file:line` are from the current-state map (`scratchpad/current-state-map.md`, read 2026-09-24); research cites are `docs/research/llm-landscape-2026-09/<doc> §n`; the plan is `docs/superpowers/plans/2026-08-10-model-router.md`.

## 0) Thesis

The server already has a vendor-neutral spine — `jobs` row + `jobs:queue` + per-job JSONL + text-marker lifecycle + workspace clone/ff-sync (state map §6, "load-bearing") — wrapped in a vendor-specific executor (`session.py:650-816`, `1048-1132`) and fronted by surfaces that are thin, text-shaped and divergent: 12 registered Telegram commands plus four ghost ones (`telegram_bot.py:1296-1308`, `709-713`, `1042`), a 200-line inline htmx page with a raw-JSON job view (`web.py:646-847`), an SSE route nothing renders (`web.py:600-640`), completion DMs that reach ~3 % of jobs because the job→chat binding lives in process memory (`telegram_bot.py:38, 1028`), zero cost/provider/queue-wait visibility anywhere (`audit_log.py:12`; §5 items 1-9), and three copies of every policy the surfaces share (model aliases `telegram_bot.py:122-134` vs `web.py:689-691` vs 72 frontmatters; god/privilege strip in `mcp_dispatch.py:32-59`, `web.py:383-386`, `telegram_bot.py:292-298`). The owner's ask — schedule, interface, deliver, automate research, watch progress, across interfaces — is therefore mostly a **control-plane** problem and only secondarily a routing problem. This design adds one `src/control/` layer (grammar → typed intents → view models), one persisted notification outbox, typed tables for approvals/deliverables/quota/events, lane-aware queueing, and per-surface renderers; then lands the approved router (R0-R5) *behind* that plane so that provider, cost, window and qualification state are first-class things the owner can see and steer from a phone. It keeps the Claude Agent SDK as the trust anchor and the only executor with hooks (INV-21; plan §8), adds Codex/Gemini/local as contained, measured lanes, and never creates an order path (INV-22).

## 1) Architecture

### 1.1 Components (text diagram)

```
                                OWNER'S HANDS
  phone: Telegram ──┐   laptop/phone: PWA (/app) ──┐   terminal: `ai` ──┐   Claude Desktop / Codex: `ai-mcp` ──┐
   cards + buttons  │   views + SSE + Web Push     │   stream + tail     │   MCP tools (same intents)          │
  ──────────────────┴───────────────────────────────┴─────────────────────┴──────────────────────────────────────
                                  │  ONE GRAMMAR  src/control/grammar.py  (verbs, flags, aliases)
                                  ▼
            CONTROL PLANE  src/control/   intents.py · views.py · policy.py (god/privilege strip, once)
            ┌──────────────────────────────────────────────────────────────────────────────┐
            │ intents: run watch jobs job cancel approve reject reply schedule providers     │
            │          quota cost deliverables atlas proposals project                       │
            │ views:   JobCard TaskCard ApprovalCard DeliverableCard ScheduleBoard           │
            │          ProviderPanel QuotaStrip CostReport AtlasHealth AlertHistory          │
            └────────────┬─────────────────────────────────────────┬───────────────────────┘
                         │ enqueue_job (jobs.py:16-47, unchanged)  │ read-only queries
                         ▼                                         ▼
  STATE  Postgres: jobs(+provider,model_served,lane,priority,origin_*,tokens,cost_usd_list,num_turns,
                        duration_api_ms,terminal_reason,done_verdict)  tasks(+origin_*)  task_turns
                   schedules(+lane,misfire_policy,owner_edited,last_run_job_id)  approvals  deliverables
                   notifications(outbox)  quota_snapshots  agent_events  review_verdicts  provider_qualifications
  BUS    Redis:    jobs:queue:<lane>  jobs:stream:<id> (rich)  jobs:done:<id>  jobs:cancel  events:control
                   quota:<provider>:paused_until  quota:<provider>:counters:<day>  heartbeat:runner
                         │
                         ▼
  RUNNER main.py  job loop: lane-ordered BLPOP, per-lane caps, provider-window gate (still slot-before-BLPOP)
     ├─ registry/models.py + providers.yml + routing-policy.yml + provider_qualifications → policy.select()
     ├─ ExecSpec (vendor-neutral) → Executor
     │     ├ ClaudeSdkExecutor   = today's _build_options + _run_in_process, moved byte-for-byte (anchor)
     │     ├ CodexCliExecutor    = codex exec --json --output-schema; Seatbelt; workspace-only; scrubbed env
     │     ├ HttpCompletionsExec = gemini-free / ollama-local; no tools (utility_call seam)
     │     └ ScriptExecutor      = no_llm skills (skills.py:55, dead today)
     ├─ normalized ExecEvent → same audit kinds (C14) + jobs:stream + agent_events + heartbeat
     └─ post-steps: deliverables registration · done-verdict · review belts (Anthropic gate + optional critic)
                   · notify outbox · learning · task lifecycle (main.py:1056-1161, unchanged markers)
                         │
                         ▼
  NOTIFY src/notify/  outbox → renderers: Telegram · Web Push · SSE · CLI · `python -m src.notify send`
                      (healthcheck-all.sh, schedule-monitor.sh, heartbeat Worker keep working when runner is dead)
```

### 1.2 Control plane (`src/control/`, new)

- `grammar.py`: one parser for every surface. `<verb> [target] [text] [--flag[=value]]…`. Replaces three divergent parsers (`telegram_bot.py:140-172` leading-flags-only; `web.py` `CreateJobRequest`; `mcp_dispatch.py:35-40` which strips isolation/permission but not model/effort). Flags: `--as=<skill>` (today `--kind`), `--on=<provider/model|alias>` (today `--model`), `--effort`, `--project`, `--lane`, `--timeout`, `--watch`, `--quiet`. Unknown model strings are rejected here, not at session time (today `telegram_bot.py:157` passes them through; `session.py:699-700` applies `payload['model']` unchecked).
- `intents.py`: `run, watch, cancel, approve, reject, reply, schedule_*, provider_*, quota, cost, deliverables, atlas, proposals, project_*`. Each intent is a pure function `(actor, args) → Result | Error` over the models; the only mutation path into the runner remains `enqueue_job` (`jobs.py:16`), and `cancel` gains a durable path for queued jobs (LREM + status flip; today `main.py:1389-1398` reaches running jobs only).
- `policy.py`: the god/privilege strip and `kind=god` rejection written once (INV-18, C10), imported by Telegram, web, CLI, `ai-mcp` and `mcp_dispatch`.
- `views.py`: JSON view models rendered by each surface. Same object → Telegram card, PWA panel, CLI table, MCP tool result.
- `renderers/`: `telegram.py` (MarkdownV2 escaping in one place — the legacy escaping crashes in `TROUBLESHOOTING.md:699-707` go away), `sse.py`, `cli.py`, `mcp.py`. Renderers are the only code that knows Telegram's 4096-char / 64-byte callback / 8-button limits (C23).

What moves out of the gateway: `telegram_bot.py` shrinks to transport (updates in, renderer output out); `web.py` keeps routes and delegates to intents; the gateway stops importing runner internals (`quota`, `router`, `plans.spawn_plan_jobs`, `retrospective`, `delivery.load_project_manifest` — state map §2.3 coupling) because `control` owns those reads. `Task` creation happens in `intents.run` for every human-initiated launch, not only Telegram (`telegram_bot.py:231-256` vs `web.py:399-405`).

### 1.3 Data model changes (migration 007-010, all additive)

| Table | Change | Why (gap) |
|---|---|---|
| `jobs` | `provider`, `model_served`, `lane`, `priority`, `origin_channel`, `origin_ref`, `origin_thread`, `first_event_at`, `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`, `num_turns`, `duration_api_ms`, `cost_usd_list`, `terminal_reason`, `done_verdict` | `session.py:1095` drops `num_turns/total_cost_usd/duration_api_ms/model_usage/stop_reason/api_error_status`; `models.py:14` promises a tokens column that does not exist; `Task.chat_id` (`models.py:284-286`) is the only channel binding; `jobs.status` CHECK (migration 006) stays untouched — done-ness is a column, not a new status |
| `tasks` | `origin_channel`, `origin_ref`, `origin_thread`, `awaiting_since` | web launches never get a Task (`web.py:399-405`, `main.py:441`); stuck-state ages invisible (§5 item 24) |
| `schedules` | `lane`, `misfire_policy` (skip / catch_up_once), `owner_edited`, `last_run_job_id`, `provider_policy` | misfires dropped silently (`main.py:1327-1362`); seeder overwrites cron on deploy (`seed-schedules.sh:22-47`) so phone edits cannot survive today |
| `approvals` (new) | `id, kind ∈ {deploy, plan, protected_path, provider_promote, question, choice, spend}, subject_type, subject_id, requested_by_job, payload, status, decided_via, decided_at, note` | `DeployNeedsApproval` fails the job and asks the owner to re-type (`main.py:460-511`; §5 item 11); `awaiting_user` never set |
| `deliverables` (new) | `id, job_id, task_id, kind ∈ {file, commit, pr, url, report, artifact}, title, path, url, sha, bytes, preview` | deliverables are truncated summary text with caps 3500/3200/600/500 (§5 item 10) |
| `notifications` (new outbox) | `id, notice_kind, subject, severity, body, actions, channel, external_ref, status, attempts, sent_at` | `_job_to_chat` dict (`telegram_bot.py:38`), `tasks:notify` string vocabulary (`main.py:733,886,1112,1129,1216,1260` ↔ `telegram_bot.py:1087-1271`), no alert history (§5 item 26) |
| `quota_snapshots` (new) | `provider, window ∈ {five_hour, seven_day, day, month}, used_pct, resets_at, source ∈ {vendor, inferred}, ts` | 636 `rate_limit_status` events with utilization never aggregated (§5 item 3); `/api/quota` shows only paused/reset |
| `agent_events` (new) | one row per model call: `ts, job_id, lane, provider, model, kind, tokens{…}, cost_usd_list, latency_ms, ttft_ms, http_status, error_type` | the collector/dashboard side no vendor supplies (`crosscut-subscription-automation-tos.md §3.10a`; `crosscut-finance-trading-ai.md §3` "Progress-visibility sink": Postgres-as-sink is first choice on 16 GB) |
| `review_verdicts` (new) | `job_id, belt ∈ {in_session_gate, post_review, critic}, reviewer_provider, reviewer_model, verdict, findings` | INV-13 gate verdict never stored (§5 item 20); post-review covers 75/1633 |
| `provider_qualifications` (new) | `provider, task_class, state ∈ {shadow, canary, qualified, demoted}, evidence, changed_by` | plan §6g artefacts absent (state map §2.7 pain point) |

### 1.4 Executors / providers (plan §6a-c, landed behind the plane)

- `src/runner/executors/base.py`: `Executor.start(spec) → AsyncIterator[ExecEvent]`, `interrupt()`, `kill()`; `ExecResult{final_text, usage, terminal_reason, cost_usd_list, num_turns, model_served}`. `ExecSpec{cwd, system_prompt, capabilities, effort_tier, max_turns, guard_profile, mcp_servers, subagent_skills, provider, model}` built from the five seams already visible in `_build_options` (prompt 664-692, resolution 694-724, subagents 730-736, guards 752-755, MCP 757-796).
- `claude_sdk.py`: `_run_in_process` + `_build_options` moved behavior-identically (plan R2 gate: audit-replay yields identical event sequence). Two fixes ride along: read typed `api_error_status`/`stop_reason` instead of the banner regex (`session.py:495-534`), and assert `model_usage` names the requested model and `duration_api_ms > 0` (the `unrecognized_model` silent-empty-result trap, `claude-anthropic.md §7` gotchas).
- `codex_cli.py`: `codex exec --json --ephemeral --sandbox read-only|workspace-write -m <pinned> --output-schema`; `features.goals=false`, `otel.metrics_exporter="none"` or local OTLP (default is `statsig`, phones home: `chatgpt-openai.md §2, §7`); one `auth.json` per serialized stream (`runtimes-aggregators.md §3 (a)`); JSONL `item.*`/`turn.completed` mapped onto `tool_use/tool_result/text/job_completed`. Never receives MCP (plan §5 caveat) or the atlas `.env`.
- `http_completions.py`: the `utility_call(provider, model, system, user, schema)` seam replacing the four copy-pasted `query()` loops (`llm_router.py:156-168`, `learning.py:266-278`, `review.py:258-278`, `evals/run.py:74-100`). Chain per plan §6c: `ollama-local → gemini-free → anthropic-haiku` (OpenRouter free omitted by default; see §7). Schema-validate-and-retry; fail-open exactly as `llm_route` today.
- `registry/models.py` + `providers.yml`: the single "which models exist" list, consumed by `grammar.py`, the PWA model picker, `tests/test_skill_contracts.py:24` (`VALID_MODELS`), `_MODEL_BUDGETS` (`session.py:466-471`) and escalation chains (`main.py:759-760`). Bare ids default to `anthropic/` (plan §6e; C17 backward-compat).

### 1.5 Routing / policy

`routing-policy.yml` (plan §6d) with task classes `utility-classify`, `chat`, `research-read`, `code-project`, `code-server` (pinned), `review-gate` (pinned), `_evaluate` (pinned), plus two this design adds: `critic` (cross-vendor adversarial second opinion; Anthropic never the *first* critic of its own memo, Codex/Gemini first per `crosscut-subscription-automation-tos.md §5.2a`) and `sentiment-feed` (data ingestion, no reasoning). Capability matching does the pinning work automatically: `subagents:` or `needs-*-mcp` tags require the Claude executor (plan §6d). Selection is audited as `provider_selected{reason}` / `provider_fallback`. Escalation becomes a chain of `{provider, model, effort}` with provider-down substitution and error-class gating so quota/auth/network failures never spawn `self-diagnose` (21 % of all jobs today, `main.py:704-853`).

### 1.6 Containment (INV-17/20/21/22; guards.py is a protected path)

- Claude lane: unchanged PreToolUse hooks (`guards.py:381-490`, attached `session.py:753/755`).
- Codex lane: workspace tier only (`workspaces.py:127-170`, clone fail-closed), Seatbelt `read-only` for critic/review, `workspace-write` for `code-project` canaries, network off unless the skill declares it, scrubbed env (no Keychain, no atlas `.env`, own `CODEX_HOME`), diffs merge only through the Anthropic review gate (plan §8 INV-21 (c)).
- HTTP lanes: no tools at all; untrusted text (Telegram, fetched pages) enters only Claude `-p` with `verbatim_prompts` or Codex `exec` (`crosscut-subscription-automation-tos.md §3.8a`; `runtimes-aggregators.md §3 (e)`).
- Two owner-approved `guards.py` edits batched into one PR: (i) add `GEMINI_API_KEY|OPENROUTER_API_KEY|CODEX_API_KEY|XAI_API_KEY` to the assignment/export deny alongside `ANTHROPIC_API_KEY` (`guards.py:148-149, 261-262` guard the literal name only); (ii) the INV-22 server-side deny for broker order hosts/paths (`SYSTEM.md:130` open follow-up; `guards.py:137-149` has no broker pattern).

### 1.7 Event / audit model

Keep every existing kind and shape (C14: `job_started`, `tool_use`, `tool_result`, `text`, `thinking`, `guard_denied`, `rate_limit_status`, `context_budget_used`, `job_completed`, `job_failed`, the marker-derived `task_*`/`eval_*` kinds). New kinds, all appended to the same per-job JSONL and mirrored to `jobs:stream:<id>`:

- `provider_selected {provider, model, reason ∈ pin|policy|fallback|canary, chain}` at resolution; `provider_fallback {from, to, cause}` on substitution.
- `quota_snapshot {provider, window, used_pct, resets_at, source}` whenever a `RateLimitEvent` arrives or a poller runs.
- `heartbeat {turn, last_tool, tokens_so_far, elapsed_s}` every 15 s from the executor loop — the phone card and the Now panel read this instead of polling Postgres every 2 s (`web.py:611-640` today).
- `lane_wait {lane, seconds, position}` when a job leaves the queue; `first_event_at` is stamped on the first executor event.
- `deliverable_registered {kind, title, path|url|sha}`; `done_verdict {verdict, missing[]}`.
- `approval_requested {approval_id, kind, subject}` / `approval_decided {approval_id, decision, via}`.
- `merge_gate_verdict {belt, reviewer, verdict, findings_n}` for the in-session gate, post-review and critic belts.
- `notice_queued/sent/failed {notice_kind, channel, external_ref}` — the alert history.
- `terminal_reason` is stamped on `job_completed`/`job_failed`: `ok | max_turns | interrupted | timeout | api_error{status} | rate_limited | auth_expired | unrecognized_model`.

`jobs:stream:<id>` additionally carries `tool_result` previews and `guard_denied` (today text + tool_use only, `session.py:1146-1157`). A second Redis stream `events:control` carries fleet-level events (queue depth by lane, provider window changes, schedule fires, breaker trips) for the PWA "Now" panel and the CLI `ai watch --fleet`. Audit JSONL remains the durable trace and the task state-machine input (`main.py:1071`); structured rows are derived from it, never the reverse, so reconcile (`reconcile.py:131`, "last terminal wins") is unchanged.

## 2) Interfaces & visibility

### 2.1 One grammar, every surface

```
run <text> [--as=<skill>] [--on=<provider/model>] [--effort=low|medium|high|xhigh|max] [--project=<slug>] [--watch]
watch <job|task>          jobs [--running|--queued|--blocked|--failed|--lane=owner]        job <id> [--log|--files|--cost]
cancel <id>               approve <approval-id> [note]      reject <approval-id> [note]     reply <task|job> <text>
schedule list|show <name>|run <name>|pause <name>|resume <name>|edit <name> --cron="<preset|cron>"|add <name> --as=<skill> --cron=… [--payload=…]
providers [status|pause <id>|resume <id>|ladder]     quota      cost [--week|--month] [--by=provider|skill|vertical|lane]
deliverables [<task|job>]   open <deliverable-id>    atlas [status|<vertical>]    proposals [list|show|approve]    project <slug> status|deploy|logs
```
Telegram: same verbs as `/run`, `/watch`, `/jobs`, `/job`, `/cancel`, `/approve`, `/reply`, `/schedule`, `/providers`, `/quota`, `/cost`, `/deliverables`, `/atlas`, `/proposals`, `/project`; bare text = `run`; `/task` kept as an alias of `/run`; `/god`, `/resume`, `/chat`, `/projects` unchanged; `/clear` gains a confirmation button (§5 item 14). The four ghost commands become real (`/cancel <prefix>`, `/job <prefix>`, `/proposals`) or are removed from help text (`/rate`, replaced by 👍/👎 on DeliverableCards only). CLI `ai <verb> …` and MCP tools `ai_<verb>` are the same strings.

### 2.2 Cards (Telegram) — every card is a `views.py` object rendered once per channel

- **JobCard (live)**: one message per job, edited on phase change and at most every 15 s (Telegram edit budget; `crosscut-benchmarks` latency table not needed here). Phases: `queued (lane owner · pos 1 · est 0-2 min)` → `starting (anthropic/claude-opus-5-5 · workspace clone 3 s)` → `working (turn 12 · 3m40s / 30m · last: Bash pytest -q · files 3 · 41k tok · window 5h 34 %)` → `reviewing (gate: code-review · critic: codex)` → done/failed. Buttons: `[Cancel] [Details] [Open in app]`. Callback data `j:<8-char id>:c|d|o` (≤ 64 bytes, C23). Message id persisted in `notifications.external_ref`, so a bot restart no longer loses the binding (§5 item 6).
- **DoneCard**: replaces the JobCard: verdicts (gate LGTM / post-review / critic CONCUR|DISSENT), `done_verdict`, deliverables list with deep links, cost line (`$0 marginal · $0.14 API-equiv · 92 k tok`), `[Reopen] [👍] [👎] [Open]`. Failed: error class, `terminal_reason`, escalation hop taken, `[Retry on <alt provider>]` when the class is routable.
- **ApprovalCard**: kind, subject (diff stats / plan / schedule change / provider promotion), evidence links, `[Approve] [Reject] [Ask]`; fires from `approvals` rows, not from a failed job. Deploys park on this card instead of `DeployNeedsApproval` failing the job (`session.py:872-881`, `delivery.py:75-101`).
- **DeliverableCard**: title, kind, first 500 chars, `[Open]` → PWA `/app/d/<id>` (auth), `[Send file]` (Telegram document ≤ 50 MB) for reports.
- **ScheduleCard**: next fire, last outcome, adherence flag (DARK/NEVER_RAN/STUCK/FAILURE_STREAK from `schedule_adherence.py`), `[Run now] [Pause] [Edit]`; an immediate FailedCard on any scheduled failure (today silent until 07:15, §5 item 7).
- **ProviderCard / QuotaStrip**: per lane `anthropic 5h 34 % (resets 14:10) · 7d 61 % · codex 5h 12 % · gemini 88/250 · local ok 5.1 GB free`, breaker state, pause/resume buttons.
- **CostCard** (weekly Monday 08:00 + `/cost`): tokens and API-equivalent cost by provider × vertical × skill; "subscription lanes: $0 marginal, $X list-equivalent"; metered lanes: actual.
- **AtlasCard**: per vertical `runs ok/stale/blocked`, last decision, gate status, provisioning gaps (today: swing 37/37 `provisioning_gap`, value 0 theses — §2.6).

Exact renderings (Telegram, MarkdownV2 escaped by the renderer; one line per phase so a phone shows the whole card without scrolling):

```
▶ RUNNING  c6cfbf6b · atlas-critic · lane owner
   anthropic/claude-opus-5-5 · high · workspace 7f2a…
   turn 12 · 3m40s / 30m · last: Bash pytest -q · files 3 · 41k tok
   window 5h 34 % (resets 14:10) · 7d 61 %
   [Cancel] [Details] [Open in app]

✅ DONE  c6cfbf6b · atlas-critic · 6m12s · $0 marginal ($0.14 list-equiv · 92k tok)
   gate: LGTM · post-review: LGTM · critic (codex): DISSENT (2 findings)
   done: verified (2/2 deliverables, 1/1 checks)
   📄 research/swing-critic-2026-09-24.md   🔗 commit 9d3ebcf
   [Reopen] [👍] [👎] [Open]

⚠️ FAILED  1a9e42c0 · atlas-daily-brief · scheduler · 2m03s
   terminal: api_error 529 · escalation L1 → opus-4-7 queued (job 88c1…)
   [Retry on codex] [Details] [Mute today]

🛂 APPROVAL  ap-3f9c · deploy · server · 3 commits · +212 −40 · pytest green · lint green
   what's deploying: control-plane P1 (grammar, approvals, deliverables)
   [Approve] [Reject] [Ask]
```
- **DailyDigest 07:15**: yesterday's jobs by lane, failures with one-line causes, today's board, window forecast; replaces the bash `schedule-monitor.sh` DM with the same launchd timer calling `python -m src.notify digest`.

### 2.3 PWA / web (`/app`, static SPA under `static/app/`, served by `web.py`; installable on the phone)

Views: **Now** (running/queued/blocked by lane, QuotaStrip, provider health, next 6 schedule fires, open approvals), **Jobs** (filterable list; detail = live transcript via the existing SSE route made rich, tool timeline, guard denials, tokens/cost, provider/model served vs requested, cancel/approve/reply), **Tasks** (turns, plan DAG from `payload.depends_on`, evaluator rounds, age of `awaiting_user`), **Schedules** (week board, run-now/pause/edit with presets like `weekdays 17:30 America/New_York`, adherence, last run link), **Providers** (windows, breakers, qualification ladder, per-lane fan-out), **Cost** (week/month, by provider × skill × vertical × lane; `retrospective.skill_performance` finally has a caller, `retrospective.py:39-96`), **Deliverables** (browser; files, commits, PRs, report pages), **Approvals** (inbox), **Atlas** ("is any of this working": `resolved_provider/model`, `schedule_rollup` `web.py:175-260`, adherence, per-vertical `*.runs` read-only from the atlas DB), **Alerts** (outbox history + delivery status), **Proposals**. Push: Web Push (VAPID keys are an owner-added `.env` entry; protected path #2) for ApprovalCard/FailedCard/DoneCard-of-owner-jobs; SSE for open tabs. Auth: shared token stays for P1-P2; CF Access on the dashboard vhost (`Caddyfile:36-38`; atlas/content-forge already use it) is an owner decision because `web.py:49-63` is in protected path #2. The SSE token-in-URL (`web.py:600-640`) moves to a short-lived cookie.

### 2.4 `ai` CLI and `ai-mcp` (laptop; vendor-native apps as views)

- `src/cli/__main__.py` (stdlib `argparse`, no new deps): REST client to the gateway with the token from Keychain; `ai run "…" --watch` prints the same phase lines as the JobCard and tails the SSE stream; `ai job <id> --log` tails `volumes/audit_log/<id>.jsonl` locally; `ai jobs`, `ai cost`, `ai quota` render `views.py` tables; shell completions. Owner terminal work stops appearing as ad-hoc `created_by` strings (`owner-terminal`, `owner-dispatch`, …; §2.3) — `origin_channel=cli`.
- `ai-mcp` (stdio, `mcp<2` already pinned): tools `ai_run, ai_watch, ai_jobs, ai_job, ai_cancel, ai_approve, ai_schedule, ai_providers, ai_quota, ai_cost, ai_deliverables`. Registered once in the owner's interactive Claude Code (`claude mcp add`), Claude Desktop, and Codex (`codex mcp add`, `default_tools_approval_mode="writes"` — `chatgpt-openai.md §2`). This is how the vendor apps become views of the same state without any vendor-native scheduler or channel becoming a second system of record. Claude Code channels (Telegram plugin) stay out: research preview, flags may change, needs a running session (`claude-anthropic.md §2`).

### 2.5 What "watch progress" looks like

Phone: send `/run review the swing research memo --as=atlas-critic`; within 2 s an ack JobCard (`queued · lane owner · slot reserved`); it edits itself through `starting → working` with turn/tool/token/elapsed; on completion it becomes a DoneCard with verdict lines and an `[Open]` deep link to the report. Laptop: `ai run … --watch` prints the same lines; the PWA Jobs detail shows the transcript streaming. Machines: scheduled jobs get no chat card unless they fail or produce a deliverable the owner subscribed to (`schedule.notify ∈ {never, failures, always}`), which keeps the phone quiet while the digest and the Now panel carry the fleet.

Phase model (single source in `views.py`, same strings on every surface):

| Phase | Trigger | What the owner sees | Source |
|---|---|---|---|
| `queued` | `enqueue_job` | lane, position, estimated wait from p50 duration of running jobs | `jobs:queue:<lane>` LLEN + `jobs.started_at` |
| `starting` | `job_started` | provider/model resolved, workspace clone status, `lane_wait` | `provider_selected`, `workspace_created` |
| `working` | first executor event, then `heartbeat` | turn, last tool, files touched, tokens, elapsed/timeout, window % | `heartbeat`, `tool_use`, `quota_snapshot` |
| `blocked` | `approval_requested` or `task_question` | what is being asked, buttons | `approvals` row |
| `reviewing` | post-steps after `jobs:done` | which belts are running (`jobs:done` fires before post-steps today, `main.py:381-444` — the card says so instead of claiming "completed") | `merge_gate_verdict` |
| `done` / `failed` | `done_verdict` / `job_failed` | verdicts, deliverables, cost, `terminal_reason`, escalation hop | columns |

Surface coverage matrix (which view renders which object):

| View object | Telegram | PWA | `ai` CLI | `ai-mcp` |
|---|---|---|---|---|
| JobCard / DoneCard / FailedCard | edited message | Jobs list + detail | `--watch` lines | `ai_watch` result |
| ApprovalCard | buttons | Approvals inbox + push | `ai approve` | `ai_approve` |
| DeliverableCard | preview + Open/Send file | Deliverables browser, file view | `ai open` prints path/URL | `ai_deliverables` |
| ScheduleBoard | list + per-row buttons | week board | table | `ai_schedule` |
| QuotaStrip / ProviderPanel | one-line strip | Now + Providers | `ai quota` | `ai_quota` |
| CostReport | weekly card | Cost view | `ai cost` | `ai_cost` |
| AtlasHealth | card | Atlas view | `ai atlas` | — |
| AlertHistory | — | Alerts view | `ai alerts` | — |

### 2.6 Cost / quota / schedule visibility — data sources per lane

| Lane | Window source | Per-job tokens/cost | Evidence |
|---|---|---|---|
| Claude Max | primary: the typed `RateLimitEvent` the SDK already delivers (`session.py:1065-1082`; 636 events in prod, 0 `rejected`) → `quota_snapshots(source=vendor)`; optional calibration: a scheduled 2-minute interactive probe whose status-line command dumps `rate_limits.five_hour/seven_day.{used_percentage,resets_at}` (`claude-anthropic.md §3` [68]; `crosscut-subscription-automation-tos.md §3.10`); OTEL (`CLAUDE_CODE_ENABLE_TELEMETRY=1`, OTLP http/json to a gateway route) for TTFT/api_error per request | full `ResultMessage` (`usage`, `model_usage`, `total_cost_usd` as list-equivalent, `num_turns`, `duration_api_ms`) | `00-comparison-matrix.md §1` item 7; `claude-anthropic.md §3` visibility table |
| Codex | `account/rateLimits/read` + `account/rateLimits/updated` via a short app-server session at scheduler tick and after each Codex job (the only subscription lane exposing *remaining* budget) | `turn.completed` usage; optional OTEL `codex.turn.*` | `chatgpt-openai.md §3, §7` |
| Gemini free key | inferred: daily counter vs 250 RPD (Flash only) | `usage_metadata` | `gemini-google.md §3, §3b` |
| Local Ollama | free RAM (`psutil`), `GET /api/ps`; skip local when < 3 GB free | `eval_count/eval_duration` | `local-models-m4-16gb.md §7, §8` |

Schedule adherence: `schedule_adherence.py` runs in-process every 30 min in addition to the 07:15 launchd run, writes `schedules.adherence` and fires cards on transition; `misfire_policy` is honoured by the scheduler (commit-before-RPUSH; slot-based `next_run_at`).

## 3) Effectiveness

- **Definition of done** lives in the skill contract: optional frontmatter `done:` block. The runner sets `jobs.done_verdict ∈ {verified, unverified, failed}` after post-steps: verified = every declared deliverable registered and every check evidenced in the transcript (tool_result parse) or in a structured `<<<DONE …>>>` block; skills without a `done:` block are `unverified` (honest default), which the Now panel and DoneCard show. This is executor-agnostic like `<<<TASK_PLAN>>>` (`session.py:405-460`), so a Codex or HTTP lane satisfies it the same way.

```yaml
# skills/research-report/SKILL.md frontmatter (additive; lint_docs gains one check: every glob/check name is known)
done:
  deliverables:
    - file: projects/research/*-{{date}}.md      # glob resolved against the canonical after ff-sync
    - commit                                     # the workspace push SHA
  checks:
    - name: sources_cited     # transcript must show ≥1 WebFetch/EDGAR tool_result per numeric claim section
    - name: no_lookahead      # the `<<<DONE>>>` block must assert data_cutoff ≤ job start
  evidence: required
```

```
<<<DONE
deliverables:
  - file: projects/research/spy-liquidity-2026-09-24.md
checks:
  sources_cited: 7 tool_results
  no_lookahead: data_cutoff=2026-09-23T20:00Z
DONE>>>
```
- **Evidence**: `deliverables` rows from (i) the `<<<DELIVERABLES>>>` block, (ii) automatic detection — Write/Edit `tool_use` targets, the workspace ff-sync commit SHA (`workspaces.py:247-270`), PR URLs in final text, `<job>.summary.md`; (iii) the gate/post-review/critic verdicts in `review_verdicts`. INV-16 means workspace-tier files are reachable only via the pushed commit, so the deliverable is `commit + path`, rendered from the canonical clone.
- **Review / grading**: (a) the in-session `code-review` subagent stays the INV-13 merge gate and its verdict is parsed from the parent transcript into `review_verdicts(belt=in_session_gate)` (today never stored, `review.py:220-223`); (b) post-review stays pinned Anthropic (`review.py:247-256`) but the 600 s timeout now stamps `review_outcome=error` (fail-closed gap `main.py:620-626`); (c) an additive **critic belt** on `critic`-class skills (atlas research memos, plans, research reports): Codex `exec --sandbox read-only --output-schema` or Gemini free key (public-content memos only) writes `CONCUR|DISSENT + findings`; DISSENT pages the owner via ApprovalCard when the memo feeds a governor. Reviewer independence is measured on the box: pairwise Jaccard on normalised findings per reviewer pair, monthly; a pair > 0.7 is not a second opinion (`runtimes-aggregators.md §3 (g)`).
- **Provider scoreboard** (Providers view + monthly card): per provider × skill/task_class — success rate, `done_verdict` rate, gate/post-review/critic outcomes, judge score from `evals/`, escalation-needed rate, turn efficiency (`num_turns`, tokens/turn), API-equivalent cost, p50/p90 duration, `rate_limited` incidence. Human ratings retire from job cards (2/1633 ever) and survive only as 👍/👎 on deliverables.
- **Qualification ladder** (plan §6g): `provider_qualifications` per (provider, task_class): `shadow` (run `evals/cases` + shadow decisions at the three fail-open utility sites emitting `shadow_decision{agrees, latency, cost}`) → `canary` (≤ 20 % of low-stakes live jobs; post-review + critic watch) → `qualified` (enters the chain) → `demoted` (breaker on failure-rate delta or DISSENT spike). Promotions are `proposals` rows of the never-used `default-model` kind, shown on the Proposals view, owner-approved while the lane is young. `evals/run.py` gains `--provider/--model` and persists results (today `evals/results/` is empty; judge pinned at `run.py:48` stays Anthropic per INV-21).
- **Measured routing**: `routing_decision` confidence is thresholded (today discarded, `session.py:616`); `--as=` corrections are captured as ground truth; the Haiku classifier moves to the utility chain with Haiku as terminal fallback (plan R1).

## 4) Scheduling across vendors

- **One board, one system of record**: the server's `schedules` table is the only scheduler. Vendor-native schedulers (Claude Routines ≥ 1 h cron, ChatGPT/Codex scheduled tasks, Gemini Scheduled Actions, Grok Build tasks — `00-comparison-matrix.md §2` "Scheduled tasks" column) are not adopted as producers: none can enqueue into `jobs:queue`, most are UI-only, and each draws the same subscription window invisibly. The single exception is deferred (§8): Claude Routines with the `/fire` API as a dead-man fallback for repo-only jobs when the Mini is down (`claude-anthropic.md §7`; `crosscut-subscription-automation-tos.md §3.1` "Routines").
- **Lanes and slots**: `jobs:queue:<lane>` with BLPOP key order `owner, kernel, atlas, utility, background` (legacy `jobs:queue` stays in the list as `background` during migration so every existing producer keeps working — `jobs.py:46`, `main.py:449/1350`, `plans.py:181/233/311`, `mcp_dispatch.py:119`, `reconcile.py:101`, `healthcheck-all.sh:239-244`). Per-lane cap: non-owner lanes may hold at most `MAX_CONCURRENT_JOBS-1` slots, so an owner `/run` never waits behind two daily atlas jobs (§2.2 pain point "FIFO with no priority"). Slot-before-BLPOP and the single semaphore stay (INV-15).
- **Provider-window gate**: before dispatch the loop reads the latest `quota_snapshots` for the job's provider chain; a job waits only when *no* provider in its class chain is healthy (plan §6f). Fan-out per lane is a token-budget-per-window, not a slot count, for Claude/Codex/Gemini (`crosscut-subscription-automation-tos.md §3.10b`: start 2 / 2 / 1 / 1, raise on a clean week); a per-seed serialization lock for Codex `auth.json` (`runtimes-aggregators.md §3 (a)`); a RAM guard for local. Prod stays at 2 concurrent SDK subprocesses (~148 MB RSS each, host budget §2.8).
- **Schedule rows carry `provider_policy`**: `pinned` (default for every existing row — no behavior change), `routable` (may use a qualified alternative when the primary window is red), or a named chain. Atlas cadence/model changes still go through LOOP.md §7 and the seeder; owner edits from the phone set `owner_edited=true`, which the seeder respects (C19 amended: name/desc still overwritten, cron/payload only when not owner-edited).
- **Weekly bars are the binding constraint** (`crosscut-subscription-automation-tos.md §8` item 3; re-based 2026-09-14). The Schedules view shows a window forecast (sum of p90 tokens of the next 7 days' fires vs the inferred weekly allowance) and flags collisions; `schedules.yml` (tracked, data not shell) plus a Python seeder that validates slot collisions replaces the hand-commented cron de-confliction in `seed-schedules.sh`.
- **Scheduler tick (every 30 s, replaces `main.py:1327-1362` body; same task under the same supervisor)**:

```
for row in due_unpaused_schedules():
    if row.last_run_job_id is running and row.misfire_policy == skip:  emit schedule_skipped; advance next_run_at(slot); continue
    chain = policy.chain(row.job_kind, row.provider_policy)            # [anthropic] for pinned rows
    if not any(window_ok(p) for p in chain):                           # every provider red for this class
        emit schedule_deferred{reason=window}; notify(failures-only); advance by misfire_policy; continue
    job = Job(kind, description, payload=row.payload, lane=row.lane, schedule_id=row.id, provider_hint=chain)
    commit()                                                           # commit BEFORE RPUSH (closes the enqueue race, main.py:320-360 retry ladder)
    RPUSH jobs:queue:<row.lane> job.id
    row.last_run_job_id = job.id; row.next_run_at = croniter.next(slot)  # slot-based, not now-based
```

- **Job loop change (`main.py:113-185`)**: acquire the semaphore, then `BLPOP jobs:queue:owner jobs:queue:kernel jobs:queue:atlas jobs:queue:utility jobs:queue:background jobs:queue 2`; if the popped job's lane is non-owner and `running_non_owner >= MAX-1` and `LLEN jobs:queue:owner > 0`, LPUSH it back to its own lane head and pop owner. Provider-window gate runs after resolution: red on every provider in the chain → `LPUSH` to lane head, sleep 30 s (INV-12 semantics per provider instead of one global pause, `main.py:446-458`, `quota.py:21`).

## 5) Project delivery path

- Keep the delivery contract (`delivery.py:130-147` cwd; `75-101` authority gate), workspace clone + ff-sync (INV-16), and the two-repo atlas convention — but add a lint that diffs `atlas/integrations/ai-server/skills/` against `skills/` (15/26 already drifted, §2.6).
- `project <slug> status|deploy|logs` intents wrap `mcp_projects` tools; `restart_project` read-only deny moves into the tool implementation (today a hook regex, `guards.py:488`).
- Deploy approvals: `deploy_permitted` returning "needs approval" creates an `approvals(kind=deploy)` row + ApprovalCard with the what's-deploying summary (deploy-director already derives it); on `approve`, a deploy job is enqueued with `approval_id` in payload and the authority gate accepts it. No re-typing, no failed job.
- Deliverables for projects: PR URL, commit SHA, deployed URL, healthcheck result, `npm run build` output excerpt — registered and shown on the DoneCard; `deploy-director: verify` writes `done_verdict`.
- **Delivery sequence as the owner experiences it** (atlas example, all from the phone):

```
/run add a retirement-sector drawdown chart to /retirement --project=atlas --as=atlas-build
  → JobCard queued(lane owner) → starting(anthropic/opus-4-8, workspace clone of atlas dev)
  → working(turns…) → reviewing(gate: code-review LGTM; post-review LGTM)
  → DoneCard: 🔗 commit 4c1e… on Piserchia/atlas master · 📄 CHANGELOG entry · done: verified
  → ApprovalCard(kind=deploy, target=atlas): "3 files · +140 −12 · npm build green · what's deploying: …"  [Approve]
  → deploy job (gated-auto path unchanged: ff-only pull, dbmate, pytest gates, npm build, healthcheck)
  → DoneCard: 🔗 https://atlas.chrispiserchia.com/retirement · healthcheck 200 · verify: PASS
```

- **Rollback / red gate**: a red deploy gate keeps the old code serving (today's behavior) and produces a FailedCard with the failing gate's excerpt and `[Retry] [Open logs]`; `project <slug> logs` tails the project's launchd log through the gateway.
- Cross-vendor: `code-project` (atlas, pickem, bingo, content-forge — never `src/`) is the Codex canary class (plan §7 R3) under INV-21 containment with the Anthropic gate; `code-server` stays pinned. Non-owner-facing project pages keep being static or API-generated (`crosscut-finance-trading-ai.md §6` third-party-serving table; subscription lanes produce owner-facing artefacts only).

## 6) Trading research automation within INV-22

- **What runs where**: all atlas worker/governor skills stay on the Claude executor (they need MCP dispatch, subagents, `env_files`). Additions are contained stages, not new paths: (1) **critic belt** after the Anthropic validator on research memos, theses and quant reports — Codex `exec --sandbox read-only --output-schema critic.json` in a fresh workspace clone with *no* atlas `.env`, writing a DISSENT/CONCUR ledger line (the "highest-value non-Anthropic insertion", §2.6 opportunities); Gemini free key is allowed as a critic only for memos containing no positions or proprietary theses (it trains on content: `gemini-google.md §3a`); (2) **local utility lane** for advisor RSS/transcript sentiment labels, dedup embeddings (`embeddinggemma`), and alpha-intake triage pre-filter (`local-models-m4-16gb.md §7` task classes); (3) **sentiment feed** via xAI `x_search` as an append-only snapshot table with overlay tags only — *deferred*, metered, no free credits (`grok-xai.md §6-8`; owner decision §11).
- **Never**: no lane gets an order tool; the only order path remains `atlas/swing/swing/executor.py --submit` behind `risk.validate` (`:535, :599, :621, :640`); the server-side broker-host deny (§1.6) turns INV-22 from docs into a guard; Tradier/IBKR remote MCPs (both ship live order tools) stay off the server (`crosscut-finance-trading-ai.md §3, §6`).
- **Critic stage contract** (the one new atlas skill, `atlas-critic`, staged in `atlas/integrations/ai-server/skills/` per the two-repo rule; `isolation: workspace`, `task_class: critic`, `providers: {allow: [codex, gemini-free], deny: [anthropic-as-first]}`, `required_tools: [Read, Glob, Grep]` only):

```
input : the memo/thesis/report path in the fresh clone + the Anthropic validator's verdict (read-only)
output: --output-schema critic.json → {"verdict": "CONCUR|DISSENT", "findings": [{"claim", "why", "severity", "evidence_path"}],
                                        "lookahead_risk": bool, "numbers_unverified": [...]}
ledger: append one line to <vertical>/evaluation/critic.jsonl {job_id, provider, model, verdict, findings_n, memo_sha}
gate  : DISSENT with severity=high on a memo that feeds a governor → approvals(kind=question) → owner card; governor
        skills read critic.jsonl and must cite the DISSENT in their grade (LOOP.md §7 amendment, evidence-gated)
env   : CODEX_HOME=volumes/codex/<job8>; no atlas .env (env_files skipped for non-Anthropic executors); network off
cost  : Codex Free plan (owner-only output); ≈ 1 message per memo; Gemini free key only when memo.sensitivity == public
```

The tripwire for INV-22 on this lane is a scheduled job that runs the critic against a fixture memo containing a `tradier.com/v1/accounts/*/orders` URL and a fake `TRADIER_SANDBOX_TOKEN=` line and asserts the transcript contains neither an outbound request nor the token value.
- **Data / credential boundaries**: brokerage and data keys live only in atlas `.env` (`tradingcore/env.py`); `env_files` gets scoped per vertical in the atlas manifest (today the whole `.env` enters every atlas workspace, §2.6) — an atlas-repo PR; non-Anthropic executors run with a scrubbed environment and never see it. Theses go only to lanes with training verified off: Claude Max "Help improve Claude" off (30-day retention; `claude-anthropic.md §3`), Codex "Improve the model for everyone" off (`chatgpt-openai.md §3`); Fable-class models are 30-day-retained regardless. Owner-only outputs on subscription lanes; nothing served to a second person (`crosscut-finance-trading-ai.md §6` AUP clauses: Anthropic consumer terms securities/not-a-broker-dealer; xAI "unlawfully buy or sell").
- **Which vendor adds what**: Codex — independent adversarial critic (highest lineage independence, `crosscut-subscription-automation-tos.md §5.2a`) and long-filing synthesis on `research-read`; Gemini — cheap public-content review and earnings/filing digestion (Vals Finance Agent v2 #1) once a paid key is ever approved; local — labels/embeddings/pre-filters; Grok — the only programmatic X feed (deferred); Perplexity `finance_search` — transcripts/estimates complement to EDGAR (deferred, metered).
- **Visibility for trading**: the Atlas view/card (§2.2/2.3) answers "is any of this working" from `resolved_provider/model`, rollups, adherence and per-vertical `*.runs` — the page the state map says does not exist (§5 item 25).
- **Blockers to fix first (cheap, no vendor work)**: provision `TRADIER_SANDBOX_TOKEN` and `FINNHUB_TOKEN` (owner; auth config), patch `weekly.py:316` `KeyError('screen')`, add an Alpaca→yfinance/Tradier data fallback for the paper trader's `stale_data` (9/21 runs), stop the ~45 sessions/month that only report the missing credential (a `provisioning_gap` pre-check that skips the LLM session).

## 7) Vendor plan

| Vendor | Surface on this server | Auth | Cost path | ToS status (research) | Task classes | Not used |
|---|---|---|---|---|---|---|
| **Anthropic** | Claude Agent SDK (bundled CLI, pinned `>=0.1.81,<0.2` today; bump deliberately with a `claude -p ping` smoke test) | Max subscription `/login` + a one-year `claude setup-token` in the launchd env (owner action); never `--bare`; `ANTHROPIC_API_KEY` stays banned (INV-3) | included (owner's Max tier, 5x or 20x — not recorded anywhere; owner input) | **Allowed\*** — own account, unmodified binary, "ordinary, individual usage"; policy volatile; `--bare` may become the `-p` default (`claude-anthropic.md §3, §7`; `crosscut-subscription-automation-tos.md §3.1, §3.7`) | everything agentic; pinned: `code-server`, `review-gate`, `_evaluate`; chat on Sonnet 5 low/medium (~2 s measured on this box); Haiku 4.5 utility terminal fallback until its ≥2026-10-15 retirement | Routines as primary scheduler; channels plugin; Managed Agents (API key) |
| **OpenAI / Codex** | `codex exec --json --output-schema` (pinned CLI via brew) + a throwaway app-server session for `account/rateLimits/read`; `ai-mcp` registered in Codex for the owner's interactive use | ChatGPT **Free** plan via `codex login --device-auth` (owner decision 2026-08-17 §10.2), one `auth.json` per stream, 0600, `keyring` mode tested first | $0 (Plus $20 only if canaries show it carries load — owner decision) | **Gray/Yes\*** — owner-only, owner-read outputs; OpenAI steers CI to API keys; `features.goals=false`; `otel.metrics_exporter="none"`; training toggle off (`chatgpt-openai.md §3, §7, §8`) | `critic` (first adversarial vote), `research-read`, `code-project` canary, `utility-classify` on Luna when the plan allows | anything a second person consumes; goal mode; Agents API |
| **Google Gemini** | `google-genai` via `http_completions.py` (OpenAI-compatible endpoint acceptable) | unpaid AI Studio key, owner-added (decision §10.4) | $0; 250 RPD Flash-only | **Allowed** (API key); the free tier trains on content and may be human-reviewed → public-content tasks only; Antigravity/Gemini CLI OAuth from our orchestrator is a written breach — not used (`gemini-google.md §3, §3a, §7`; `crosscut-subscription-automation-tos.md §3.3`) | `utility-classify` middle link; `critic` on memos with no positions/theses | theses, owner data, anything sensitive; `agy` headless |
| **Local (Ollama)** | `qwen3.5:4b` (default), `qwen3.5:9b` (extraction), `embeddinggemma`; `OLLAMA_MAX_LOADED_MODELS=1`, `KEEP_ALIVE 10m`, RAM guard; remove the 14 GB of stale weights (`phi3`, `deepseek-coder-v2:16b`, `mistral`) | none | $0 | n/a (MIT runtime, Apache-2.0 weights; LM Studio's no-SaaS EULA irrelevant) | `utility-classify` first link, sentiment labels, embeddings, pre-filters; chat fallback only when Claude is paused | research, coding, review (fabricates repo facts, `local-models-m4-16gb.md §8`) |
| **OpenRouter `:free`** | optional middle link in the utility chain only | key owner-added | $0; 20 RPM, 50 req/day without credits | Allowed (API); high churn; metered spend **declined** | `utility-classify` fallback | anything load-bearing |
| **xAI Grok** | *deferred* — `x_search` sentiment side-car via OpenAI-compatible client | API key, prepaid | metered, no free credits ($5/1k posts + tokens) | Allowed (API); Grok Build seat lanes not sanctioned for automation (`grok-xai.md §3, §7`) | `sentiment-feed` | coding, review |
| **Perplexity** | *deferred* — Agent API `finance_search` | API key | metered | consumer plan **Banned** for automation; API Allowed (`crosscut-subscription-automation-tos.md §3.7`) | transcripts/estimates | consumer surfaces |
| **Ollama Cloud Pro / Mistral Pro** | *deferred* — the only policy-clean credit-bundled subscriptions; would be the lane behind any non-owner-facing page | key from the plan | $20 / $14.99 | Allowed (credit-bundled metered use) (`crosscut-subscription-automation-tos.md §7` item 7) | bulk / non-owner-facing generation | default plan |
| Cursor, Kiro, Copilot, Z.ai/Kimi/MiniMax/Alibaba plans, opencode, OpenClaw/Hermes, LiteLLM | not adopted | — | — | either banned for our shape, interactive-only, distillation-correlated as reviewers, 4 GiB daemon floor, or supply-chain history (`runtimes-aggregators.md §7-8`) | — | — |

## 8) Migration & rollout

Everything is additive and flag-gated; the Telegram bot keeps legacy handlers behind `CONTROL_PLANE_V2=0`, the runner keeps today's path behind `ROUTER_PROVIDERS_ENABLED=anthropic` (plan §2), and the outbox can be bypassed with `NOTIFY_OUTBOX=0`. Each phase ships as small server-patch PRs through the INV-4 lane; the protected-path edits (guards.py, lint_docs.py allowlist, `.env` keys) are batched into two owner-approved PRs (P1 and P3).

| Phase | Weeks | Scope | Entry | Exit criteria | Kill switch |
|---|---|---|---|---|---|
| **P0 foundations** | 0-1 | migration 007 (jobs columns incl. origin, tokens, cost, `terminal_reason`); capture the full `ResultMessage` (`session.py:1094-1128`); typed `api_error_status` replaces the banner regex; `src/notify/` outbox + `notifications` table; persisted job→origin (done DMs for every launch); immediate FailedCard for scheduled jobs; ghost commands fixed; `/clear` confirmation; `AskUserQuestion` removed from the default tool list (`session.py:706-709`) | pytest green | every completed job has tokens/cost/provider in Postgres; a scheduled failure DMs within 60 s; bot restart loses no completion DM | none needed (additive) |
| **P1 control plane** | 1-3 | `src/control/` grammar/intents/views/policy; Telegram command rewrite with aliases; live JobCard; `approvals` + ApprovalCard + deploy parking; `deliverables` + DeliverableCard + `<<<DELIVERABLES>>>`; `ai` CLI; durable cancel for queued jobs; schedule run-now/pause/edit commands with `owner_edited`; owner PR #1: guards.py vendor-key deny + INV-22 broker deny + lint allowlist untouched | P0 | owner runs a job from the phone, watches it, approves a deploy from a card, opens the deliverable; grammar test suite is the only parser | `CONTROL_PLANE_V2=0` |
| **P2 visibility** | 3-5 | PWA `/app` (Now, Jobs, Tasks, Schedules, Deliverables, Approvals, Alerts) + Web Push; `quota_snapshots` from `RateLimitEvent`; `agent_events` + OTLP http/json gateway route; lanes (`jobs:queue:<lane>`, per-lane caps); heartbeat + `first_event_at`; Cost view; DailyDigest replaces the bash DM; in-session gate verdict stored; post-review timeout fail-closed | P1 | owner-lane job never waits behind atlas; QuotaStrip shows Claude 5h/7d from live events; Cost view reconciles with JSONL sums for 30 days | PWA is opt-in; old dashboard route stays until P5 |
| **P3 executor + utility lane (plan R0-R2 + R1)** | 5-7 | `registry/models.py` + `providers.yml` + `routing-policy.yml` (anthropic-only entries first); `executors/base.py` + `claude_sdk.py` byte-for-byte; `utility_call` + `http_completions.py`; Ollama pull `qwen3.5:4b`/`embeddinggemma`, stale weights removed; Gemini free key (owner adds); per-provider quota keys; `kill switch ROUTER_PROVIDERS_ENABLED`; owner PR #2 if any `.env`/lint edits | P2; owner probes: `ollama run --verbose` bench, Gemini key | audit-replay of 20 recorded jobs yields identical event sequences; router precision on `evals/` router cases ≥ Haiku baseline; a week of `provider_fallback` audits reviewed; Haiku spend on utility calls → ~0 | `ROUTER_PROVIDERS_ENABLED=anthropic` |
| **P4 Codex lane + effectiveness (R3)** | 7-10 | `codex_cli.py`; ChatGPT Free device-code login (owner); critic belt on atlas memos (read-only, no env); `research-read` canary on non-critical skills; `review_verdicts`; `provider_qualifications` + ladder + Providers view; `done_verdict` + `done:` blocks on the 10 highest-volume skills; evals `--provider` + persisted results; reviewer-overlap metric | P3; owner: Codex login, training toggle off | 4 weeks shadow with agreement/latency logged; canary LGTM rate ≥ skill baseline; zero guard-equivalent violations (env scrub verified by a tripwire job); first DISSENT reviewed by owner | `providers pause codex` |
| **P5 failover + polish (R4-R5)** | 10-12 | class-aware pause (pinned lanes pause, routable drain); `ai-mcp` for Claude Desktop/Claude Code/Codex; `schedules.yml` + validating seeder; Atlas view; monthly cost report; old inline dashboard removed; `healthcheck-all.sh` responsibilities split into `python -m src.runner.ops_probe` + `notify send` | P4 | simulated Anthropic pause drill: routable lanes keep draining, pinned lanes pause, owner DM'd; first monthly report with real numbers | per-provider pause; legacy dashboard restorable from git |
| **Deferred / owner-gated** | — | Claude Routines `/fire` fallback; xAI sentiment feed; Perplexity `finance_search`; Ollama Cloud Pro for non-owner pages; CF Access on dashboard; OS sandbox per executor; ChatGPT Plus upgrade | — | — | — |

What keeps running throughout: all 41 schedules, all 72 skills, the INV-13 gate, launchd alerters and the edge Worker (they only gain `notify send`). Ops debt that is cheaper than any of this and should ride P0: off-site backup (rclone R2 is skipped nightly), `pg_dump` of the atlas DB, `.env`/cloudflared copies, `autorestart` on power loss (§2.8).

Test gates per phase (pure-function style the repo already uses; the live stack only for the replay and drill gates):

- P0: `tests/test_result_capture.py` (fake `ResultMessage` → columns); `tests/test_notify_outbox.py` (renderer limits, retry, delivery status); contract test that every `tasks:notify` kind has an outbox equivalent.
- P1: `tests/test_grammar.py` (every verb/flag/alias, rejection of unknown models via the registry); `tests/test_intents.py` (approve resumes a parked deploy; cancel of a queued job LREMs); `tests/test_views.py` (card fits 4096 chars, callback ≤ 64 bytes, ≤ 8 buttons).
- P2: `tests/test_lanes.py` (owner reservation, legacy `jobs:queue` still drained); `tests/test_quota_snapshots.py` (RateLimitEvent → snapshot → window_ok); OTLP route accepts a recorded Claude Code http/json payload.
- P3: audit-replay harness (`tests/replay/`) over 20 recorded JSONL jobs asserting identical kind sequences; `tests/test_registry.py`; `evals/run.py` router cases vs Haiku baseline.
- P4: `tests/test_codex_events.py` on recorded `codex exec --json` fixtures (schema pinned to the CLI version); env-scrub tripwire; `tests/test_done_verdict.py`.
- P5: quota-pause drill script (`scripts/drill-quota-pause.sh`) that fakes a red Anthropic window and asserts routable lanes drain.

## 9) What gets deleted / rewritten vs kept

| Element | Verdict | Action |
|---|---|---|
| JSONL audit log + `summary.md`; text-marker lifecycle; workspace clone/ff-sync; fail-closed resolution/tighten-only/deploy gate; `enqueue_job` + Job row as truth; slot-before-BLPOP; out-of-band alerters; in-session `code-review` gate; atlas kernel order path | **Keep** (load-bearing, state map §6) | extend only: new kinds, new columns, lane keys, verdict recording |
| `_build_options` monolith (`session.py:650-816`) | **Rewrite** into `ExecSpec` + `claude_sdk.py` | behavior-identical move with the audit-replay gate; first tests for this code ever |
| Four `query()` loops (router, learning, review, judge) | **Rewrite** into `utility_call` (reviewer keeps its 6-turn agent form, pinned) | shadow-mode hook |
| `_MODEL_ALIASES` as CI allowlist; web 3-id dropdown; `_MODEL_BUDGETS` | **Delete** (replaced by `registry/models.py`) | `test_skill_contracts.py:24` imports the registry |
| Global `quota:paused_until` (`quota.py:21`); banner regex; dropped `ResultMessage` fields | **Delete/replace** | per-provider keys; typed terminal reason; columns |
| `tasks:notify` string vocabulary; `_job_to_chat`; three Telegram senders; `_error_safe` self-diagnose dispatch | **Delete** (outbox + renderers; cap the auto-dispatch) | `notify.py` shared by bot, scripts, Worker |
| `Task.chat_id`/`thread_message_id` as the only binding | **Keep columns, stop depending on them** | `origin_*` on jobs and tasks |
| Ghost commands; `/rate`; rating buttons on every card; `avg_rating` in rollups | **Delete** | 👍/👎 on deliverables only |
| Inline htmx dashboard (`web.py:646-847`); SSE token-in-URL | **Rewrite** as static PWA under `static/app/` + cookie auth | old route removed in P5 |
| `seed-schedules.sh` as sole payload writer; hand cron de-confliction | **Rewrite** as `schedules.yml` + Python seeder honouring `owner_edited` | C19 amended |
| `JobKind` enum, dual kind spellings, `notify` ghost; payload-as-control-plane keys (`escalation_level`, `depends_on`, `eval_round`) | **Delete enum; keep payload keys, mirror into columns** | `kind` validated at enqueue against `list_all()` |
| `self-diagnose` on every L2/L3 regardless of error class | **Rewrite** (error-class gate; provider-down substitution) | 21 % of jobs today |
| `healthcheck-all.sh` (probes + liveness + swing watchdog + deploy autopilot + raw SQL enqueue) | **Split** (doctrine kept) | `ops_probe` + `notify send`; autopilot enqueues through the API |
| review-and-improve at opus/max on idle with raw psql by `kind` | **Keep, cheapen** | SQL pre-pass via `ScriptExecutor`; group by `resolved_skill`; weekly |
| `isolation: none` default + 44-name allowlist (`lint_docs.py:612-635`) | **Keep frozen this cycle** (protected) | flip per vertical later; INV-21(a) precondition |
| Idle Ollama with 14 GB stale weights | **Delete weights, wire the daemon** | P3 |
| SDK `<0.2` + `mcp<2` pins | **Keep** | executor seam isolates the fragile edge |

## 10) Risks & mitigations

- **Anthropic policy or CLI flips** (`--bare` default, credit split resumed): pin the SDK/CLI, smoke-test `claude -p ping` on every bump, keep the setup-token and `/login` both valid, alarm at T-30 d; the executor seam plus Codex lane make a forced migration a config change (`claude-anthropic.md §7` gotchas).
- **Hot-path refactor (P3)**: audit-replay gate on 20 recorded jobs, kill switch, one live canary per skill class before default; no behavior change in R0.
- **Telegram edit-rate limits and card noise**: 15 s edit cadence, phase-change edits only, `schedule.notify=failures` default for machines; outbox retries with backoff; alert history makes drops visible.
- **Free-tier churn / Gemini rugs** (owner accepted 2026-08-17): every chain terminates in Haiku/Sonnet-low or local; breakers log loudly; Haiku retirement ≥ 2026-10-15 handled by the registry (swap to Sonnet 5 `effort=low`).
- **Codex ban/throttle risk (Gray/Yes\*)**: owner-only outputs, goal mode off, volume tiny (critic + canaries), device-code auth, one `auth.json`; auto-pause on 401/`refresh_token_expired`; nothing user-facing ever on the plan.
- **Reviewer non-independence**: Codex/Gemini first; overlap metric; distilled lanes never the sole critic (`crosscut-subscription-automation-tos.md §5.2a`).
- **Data leakage of theses**: training toggles verified off (owner), Gemini free key fenced to public-content classes by `routing-policy.yml` sensitivity flags, scrubbed env for non-Anthropic executors, atlas `.env` scoped per vertical.
- **RAM on the 16 GB box**: Ollama unloads at 10 min, one model resident, RAM guard skips local under 3 GB free; no OTEL collector daemon (gateway route is the sink), no Langfuse/LiteLLM (`crosscut-finance-trading-ai.md §3` host budget).
- **Scope creep in the PWA**: static SPA, no build step, views are renderings of `views.py` objects also used by Telegram/CLI, so every view has a test through the view model.
- **Protected-path bottleneck**: only two owner PRs (guards/lint/.env), everything else on the INV-4 lane.
- **INV-22**: server-side deny + env scrub + tripwire job that asserts a non-Anthropic session cannot reach broker hosts or read `TRADIER_*`.

## 11) Owner decisions required

1. Approve the **control-plane command grammar** (§2.1) and the alias policy (`/task` kept; `/rate` removed; `/clear` confirm).
2. **Protected-path PR #1**: `guards.py` vendor-key deny + INV-22 broker-host deny (MISSION §M-adjacent, guards.py, `SYSTEM.md` INV-22 row).
3. **Auth-config additions by hand**: `CLAUDE_CODE_OAUTH_TOKEN` (one-year setup-token), `GEMINI_API_KEY` (unpaid), Web Push VAPID keys, `TRADIER_SANDBOX_TOKEN`, `FINNHUB_TOKEN`; ChatGPT Free device-code login on the Mini; confirm Max tier (5x/20x) so window inference has a base.
4. **Training toggles**: Claude "Help improve Claude" off; ChatGPT "Improve the model for everyone" off — precondition for routing any thesis text through either lane.
5. **Dashboard behind Cloudflare Access** (changes `web.py` auth checks, protected path #2) — recommended before the PWA carries approvals.
6. **Codex plan**: stay Free (probing) vs Plus $20 once canaries show load; **metered add-ons** (xAI `x_search`, Perplexity `finance_search`, Ollama Cloud Pro) stay declined by default — confirm or open one.
7. **Schedule ownership**: allow phone edits (`owner_edited`) to override seeded cron/payload; atlas rows stay LOOP.md §7-governed.
8. **Definition-of-done default**: skills without a `done:` block show `unverified` on cards (honest) vs silently `verified` — recommend honest.
9. **Critic belt on atlas**: Codex as first adversarial reviewer of atlas memos (read-only, no env) and DISSENT-pages-owner semantics; whether Gemini free key may review public-content memos.
10. **Ops debt ride-along in P0**: R2 off-site backup, atlas DB dump, sealed `.env`/cloudflared copies, `autorestart`.

## 12) Effort & monthly cost

- **Effort**: ~12 weeks of agent time on the INV-4 lane (P0 1 wk, P1 2, P2 2, P3 2, P4 3, P5 2) plus ~1-2 h/week of owner time for decisions, key provisioning, the two protected PRs, three on-box probes (Ollama bench, Gemini key, Codex login) and reviewing the first DISSENTs. Rough total: **12 agent-weeks, ~20 owner-hours**.
- **Monthly cost, default plan**: $0 incremental. Claude Max as today ($100 or $200 depending on tier); ChatGPT Free $0; Gemini unpaid $0; local $0; Cloudflare free; Web Push $0. Subscription-side load stays inside "ordinary, individual usage": the measured job shape (~100 k input at 82 % cache-read, 2 k output, 30-60 scheduled jobs/month) is ≈ $8-14/month API-equivalent (`00-comparison-matrix.md §4` calibration; `crosscut-finance-trading-ai.md §3`), and utility calls leave the Max window in P3.
- **Optional, each an owner decision**: ChatGPT Plus $20; xAI prepaid ≈ $5-10 (sentiment side-car at cents/job); Perplexity Agent API ≈ $5; Ollama Cloud Pro $20 (only if a non-owner-facing generated page is wanted); Massive Starter $29 only if EOD data blocks a use case. Worst case with every option: ≈ $80-90/month on top of Max.
