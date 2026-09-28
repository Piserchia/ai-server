# Design: "The Council" — multi-bot chat as the owner's front door (2026-09-24)

Lens: every vendor is a named persona in one Telegram workspace; the server orchestrates conversations between them, records everything as jobs, and a moderator turns talk into ledger entries. All `file:line` cites are from `scratchpad/current-state-map.md` (state map) unless prefixed; research cites are `docs/research/llm-landscape-2026-09/<doc> §n`.

Two research facts correct the lens premise before anything else:
- **Grok is not "natively in Telegram."** xAI's Telegram deal "never materialized"; `@GrokAI` is an unofficial bot; "for our Telegram front door Grok is therefore only ever a routed backend" (`grok-xai.md §2`). xAI has **no free API credits** (`§3`), the SuperGrok seat's headless use is Grey (AUP "using bots to access", opaque non-machine-readable weekly pool, `§3`, `§8`). A Grok persona therefore needs an owner decision (§11 D2).
- **Telegram bots cannot receive messages from other bots.** So a "many bots talking" room only works if one process holds every bot token and originates every persona message. That is exactly what this design does: the server is the only speaker; persona bots are send-only puppets. This turns a Telegram limitation into the audit property we want (every utterance is a server-originated, ledgered event).

---

## 0) Thesis

Replace "one bot that DMs job summaries" with a **council room**: a Telegram supergroup (forum topics on) where Claude, Codex, Gemini, Grok, and Local appear as named participants, every utterance is a job or a utility call in the existing ledger, and a deterministic **moderator** (with Claude as the only extraction model) turns debates into `decisions`, `deliverables`, and scheduled work. The executor seam the approved router plan already calls for (`docs/superpowers/plans/2026-08-10-model-router.md §6b`) is what makes personas possible; the council is the *user-facing shape* of INV-21, not a second system. Safety is by construction: non-Anthropic personas get **no tools by default** (text-in, text-out, so C-rated sandboxes are irrelevant — `crosscut-subscription-automation-tos.md §3.8a` rule), Codex gets a Seatbelt read-only sandbox only for review, Anthropic keeps `review-gate`/`_evaluate`/`code-server` (INV-21, plan §6d), and INV-22 stays "no order path" with a new server-side deny. The owner gets ease of use (talk in one room from a phone; same room from web/CLI), visibility (pinned boards: queue, quota per persona, schedule adherence, deliverables), and effectiveness (definition-of-done per deliverable, cross-vendor adversarial review recorded structurally, a per-persona scoreboard that gates routing).

---

## 1) Architecture

### 1.1 Components (new vs rewritten vs kept)

```
                    ┌──────────────────────── Telegram supergroup "AI Council" ──────────────────────────┐
  owner phone ────► │  #general  #atlas-research  #project:pickem  #ops  #schedule  (forum topics)       │
                    │  personas: 🟠Claude  🟢Codex  🔵Gemini  ⚫Grok  🟤Local  🧭Moderator (pinned boards)│
                    └──────────▲──────────────────────────────────────────────────┬───────────────────────┘
                               │ owner msgs (one RECEIVER bot, privacy off,        │ persona msgs
                               │ chat id in TELEGRAM_ALLOWED_CHAT_IDS — owner-added)│ (send-only puppet bots)
                    ┌──────────┴──────────────────────────────────────────────────▼───────────────────────┐
                    │ src/gateway/telegram/   receiver.py · puppets.py · cards.py · boards.py              │
                    │ src/notify.py           one outbound client (bot, scripts, Worker all use it)        │
                    └──────────▲──────────────────────────────────────────────────┬───────────────────────┘
        web (/council, SSE)    │            typed notification bus (tasks:notify v2, schema'd)             │  CLI `ai` (REST)
                    ┌──────────┴──────────────────────────────────────────────────▼───────────────────────┐
                    │ src/council/                                                                         │
                    │   threads.py   council_threads/council_turns tables ⇄ Telegram topic/thread ids      │
                    │   engine.py    turn scheduler; protocols: ask · debate · review · verify · standup    │
                    │   moderator.py deterministic state machine + Claude extraction → decisions/deliverables│
                    │   personas.yml persona → provider lane, capability set, voice, default task classes  │
                    └──────────▲──────────────────────────────────────────────────┬───────────────────────┘
                               │ every persona turn = Job (kind=council-turn) or utility_call             │
                    ┌──────────┴──────────────────────────────────────────────────▼───────────────────────┐
                    │ src/providers/   registry.py(providers.yml) · policy.py(routing-policy.yml)          │
                    │                  quota.py(per-provider keys+pollers) · utility.py(one-turn seam)     │
                    │ src/runner/executors/  base.py · claude_sdk.py (extracted) · codex_cli.py ·          │
                    │                        http_completions.py (gemini/xai/ollama) · script.py (no_llm)  │
                    │ src/runner/ (kept) main.py job loop · workspaces.py · guards.py predicates · plans.py │
                    └──────────────────────────────────────────────────────────────────────────────────────┘
                     Postgres: jobs(+provider,tokens,cost,origin) · council_* · decisions · deliverables ·
                               provider_quota_snapshots · provider_scores       Redis: jobs:queue/stream/done,
                               quota:{provider}:*, council:{thread}:lock        JSONL audit (kept, kinds added)
```

**Kept as-is (load-bearing, state map §6):** `enqueue_job` + `jobs:queue` + Job row as truth + slot-before-BLPOP (`jobs.py:16-47`, `main.py:143-151`); per-job JSONL audit + `<job>.summary.md`; the text-marker lifecycle contract (`session.py:405-460`, `main.py:1056-1161`); workspace clone + ff-sync (`workspaces.py:127-170, 247-270`); guard predicates (`guards.py`, 56 tests, 254 fleet denials); fail-closed skill resolution and tighten-only isolation (`session.py:587-647, 914-918`; `workspaces.py:79-101`); in-session `code-review` subagent as the INV-13 gate; out-of-band launchd alerters + edge Worker; atlas "kernel disposes" order path.

**Rewritten:** `_build_options` (`session.py:650-816`) and `_run_in_process` (`session.py:1048-1132`) → `executors/claude_sdk.py` behind an `Executor` protocol (plan §6b; state map §2.1 Opportunities). `telegram_bot.py` (1300 lines, one bot, 12 commands, `_job_to_chat` in-process dict at `:38`) → `src/gateway/telegram/` package. The four copy-pasted `query()` loops (`llm_router.py:156-168`, `learning.py:266-278`, `review.py:258-278`, `evals/run.py:74-100`) → one `providers/utility.py` seam. Global quota (`quota.py:21`) → per-provider keys. `_MODEL_ALIASES` (`telegram_bot.py:122-134`) → `providers.yml`.

### 1.2 Persona ≙ lane (personas.yml)

| Persona | Provider lane | Auth / cost path | Default capability set | Task classes it may take | Trust |
|---|---|---|---|---|---|
| **Claude** | `anthropic` via Claude Agent SDK (kept executor) | Max subscription; `CLAUDE_CODE_OAUTH_TOKEN` from `claude setup-token` in launchd env; never `--bare` (`claude-anthropic.md §3, §7`) | full (Read/Write/Edit/Bash/Web/MCP/subagents, guard hooks) | everything; **pinned** for `code-server`, `review-gate`, `_evaluate` (plan §6d) | anchor |
| **Codex** | `codex` via `codex exec --json --output-schema` subprocess | ChatGPT **Free** (owner decision 2026-08-17, plan §10.2), `codex login --device-auth`, one `auth.json` per serialized stream (`runtimes-aggregators.md §3(a)`); `features.goals=false`, `otel.metrics_exporter="none"` (`chatgpt-openai.md §3, §7`) | text-only in council; **read-only Seatbelt** (`--sandbox read-only --ephemeral`) inside a workspace clone for review; no MCP (plan §5) | `review-second-opinion`, `research-read`, `debate`; `code-project` canary later (plan R3) | probation → qualified |
| **Gemini** | `gemini` via `google-genai` (or OpenAI-compat endpoint) HTTP | unpaid API key, 250 RPD Flash-only, **trains on content + human review** (`gemini-google.md §3a`; plan §10.4) | text-only; optional Google Search grounding (results may not be stored programmatically, `§3c`) | `utility-classify`, `summarize-public`, `review-public-memo`, `debate` on **non-sensitive content only** | qualified (utility) |
| **Grok** | `xai` via OpenAI-compatible Responses API | **needs owner decision** (§11 D2): prepaid xAI credits (no free tier; ~$0.05–0.40/turn on `grok-4.3`/`4.7`, `grok-xai.md §4`) or no automated Grok persona | text-only; `x_search` server tool with handle allowlist + date window, `store:false` | `sentiment-feed`, `debate` (dissent), `research-read` | probation |
| **Local** | `ollama-local` `/v1/messages` or native REST, `qwen3.5:4b` (routing) / `qwen3.5:9b` (extraction) / `embeddinggemma` (`local-models-m4-16gb.md §7`) | $0; memory guard: skip if <3 GB free; `OLLAMA_MAX_LOADED_MODELS=1`, `KEEP_ALIVE 10m` | schema-constrained JSON only; no tools | `utility-classify`, `extract`, `embed`, `dedupe`, `standup-digest ≤8k tokens` | qualified (utility) |
| **Moderator** | not a model — deterministic code; extraction step uses **Claude** (`claude-sonnet-5`, effort low) | subscription | — | `extract-decisions`, `extract-deliverables`, `board-render` | anchor |

Capability matching does the safety work (plan §6d): a skill/protocol step that needs `mcp`, `subagents`, `write` or `deploy` resolves only to Claude. `providers: {allow, deny}` in frontmatter and `sensitivity: proprietary|owner|public` on every council thread gate Gemini (free key) out of anything with positions/theses (`crosscut-finance-trading-ai.md §3` data-handling rule) and Codex out of anything a second person reads (`chatgpt-openai.md §3` Gray/Yes* operating rule).

### 1.3 Data model changes (migration 007 + 008)

- `jobs`: `resolved_provider` (String 32), `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`, `cost_usd_est` (numeric, null on subscription lanes), `num_turns`, `duration_api_ms`, `terminal_reason`, `model_served`, `lane_version` (CLI/SDK version string). Captures the fields `session.py:1095` drops today (`num_turns/total_cost_usd/duration_api_ms/model_usage/stop_reason` on SDK 0.1.81 `types.py:1144-1158`).
- `job_origins`: `(job_id, channel ∈ telegram|web|cli|scheduler|council, external_chat_id, external_thread_id, external_message_id, council_thread_id)` — replaces `Task.chat_id`/`thread_message_id` as the only channel binding (`models.py:284-286`) and the in-process `_job_to_chat` dict (`telegram_bot.py:38,1028`) that drops ~97 % of completion DMs (state map §5.6).
- `council_threads`: `id, topic, telegram_topic_id, sensitivity, protocol, state ∈ open|deciding|decided|archived, project_slug, created_by`.
- `council_turns`: `id, thread_id, seq, persona, job_id (nullable for utility calls), role ∈ owner|persona|moderator, content_ref (summary.md path or inline ≤4 KB), tokens, cost_usd_est, latency_ms, telegram_message_id`.
- `decisions`: `id, thread_id, text, kind ∈ decision|assumption|open_question|owner_decision_required, evidence_refs[], status, decided_by ∈ owner|moderator`.
- `deliverables`: `id, thread_id, task_id, job_id, kind ∈ file|url|pr|report|ledger_row|schedule, path_or_url, definition_of_done (jsonb), evidence (jsonb), status ∈ draft|review|accepted|rejected, reviewers (jsonb: persona→verdict)`.
- `provider_quota_snapshots`: `(provider, window ∈ five_hour|seven_day|day|balance, used_pct, remaining_units, resets_at, source ∈ vendor|inferred, ts)`.
- `provider_scores`: `(provider, model, task_class, n, judge_mean, review_lgtm_rate, agreement_rate, p50_latency_ms, tokens_p50, escalations, demoted_at)`.
- `schedules`: add `persona/provider` pin (already honoured via `payload.model`, `main.py:1327-1362`) and `misfire_policy`; a Python seeder replaces `seed-schedules.sh` (§4).

### 1.4 Executors and providers

- `executors/base.py`: `Executor.start(spec) → AsyncIterator[ExecEvent]`, `interrupt()`, `kill()`, `result()` with a normalized `ExecEvent` enum `{text, thinking, tool_use, tool_result, rate_limit, system, permission_denied, result}` (state map §4 row 1). `ExecSpec` is the vendor-neutral intermediate the state map says is missing (`session.py:650-816` has five fused seams: prompt 664-692, resolution 694-724, subagents 730-736, guards 752-755, MCP 757-796).
- `claude_sdk.py`: `_run_in_process` + `_build_options` moved **behavior-identically**; gate = full pytest + replayed job yields the identical audit event sequence (plan R2). Adds: read `api_error_status`/`stop_reason` typed fields instead of the banner regex (`session.py:495-534`); assert `model_usage` contains the requested model and `duration_api_ms>0` before accepting success (the silent `unrecognized_model` failure, `claude-anthropic.md §7` gotcha); `verbatim_prompts=True` for any owner/Telegram-built prompt when the SDK pin is raised to ≥0.2.158 (`claude-anthropic.md §3`) — SDK pin bump is its own gated step.
- `codex_cli.py`: `codex exec --json --ephemeral --sandbox read-only -m <pinned> --output-schema <schema> -o <file> --cd <workspace clone>`; maps `item.*`/`turn.completed` to `ExecEvent`; kills the process on cancel/timeout; enforces the runner's own wall-clock and token ceilings from the stream (`chatgpt-openai.md §3` goal-mode rule); one `auth.json` per stream → a per-lane serialization lock (`runtimes-aggregators.md §3(a)`).
- `http_completions.py`: one client for Gemini (`generativelanguage…/openai/`), xAI (`api.x.ai/v1`, `store:false`), Ollama local (`localhost:11434/v1`); schema-validate-and-retry loop; per-call `usage` → tokens columns; `usage.server_side_tool_usage_details.x_posts_fetched` logged for Grok.
- `script.py`: implements the dead `no_llm` flag (`skills.py:55`; never checked by the runner) so deterministic steps (board rendering, ledger diffs, adherence) are jobs with audit trails instead of bash timers.
- `providers/utility.py`: `utility_call(task_class, system, user, schema, sensitivity) → dict|None`, fail-open like `llm_route` today (`llm_router.py:145-154`). Chain default: `ollama-local → gemini-free (public only) → anthropic-haiku/sonnet-5-low`. Emits `provider_selected{reason}` / `provider_fallback` / `shadow_decision{provider, agrees, latency_ms}`.

### 1.5 Routing / policy

`routing-policy.yml` per plan §6d with council-specific classes added:

| Task class | Ranked lanes | Notes |
|---|---|---|
| `utility-classify` (job routing, Telegram intent, learning classifier) | local → gemini-free → anthropic (Sonnet 5 low) | Haiku 4.5 retires ≥2026-10-15 (`claude-anthropic.md §1`); router fallback moves to Sonnet 5 low |
| `chat` (council quick reply) | anthropic Sonnet 5 low/medium (≈2 s wall measured on this box, `§5`) | Opus 5.5/Fable never first responder (`crosscut-tos §5.2`) |
| `debate` | Claude ↔ Codex ↔ Gemini(public) ↔ Grok(if enabled) | protocol picks roles; each turn text-only |
| `review-second-opinion` | codex → gemini-paid(n/a) → gemini-free (public) | **additive**; INV-13 gate stays Claude in-session `code-review` |
| `review-gate`, `_evaluate`, `code-server` | anthropic **pinned** | protected to un-pin |
| `research-read` | anthropic ↔ codex ↔ gemini(public) | free routing |
| `sentiment-feed` | xai only | data feed, never a signal (`crosscut-finance §6`) |
| `extract`, `embed`, `standup-digest` | local → anthropic | ≤8k tokens, schema-constrained |

Fail-closed: unknown provider in `model:` fails the job (state map C12); every chain terminates in an included-cost lane (plan §10.3).

### 1.6 Containment

- **Text-only by default.** Council turns for Codex/Gemini/Grok/Local run with an empty tool set, so untrusted text (owner messages, fetched pages relayed by Claude) reaches C-rated lanes only "with no tool access" — the exact rule in `crosscut-tos §3.8a`. There is nothing to sandbox.
- **Codex review runs** get `--sandbox read-only --ephemeral` in a per-job workspace clone (INV-16 path, `workspaces.py:127-170`), `CODEX_HOME` pointed at a per-lane dir with 0600 `auth.json`, scrubbed env (no atlas `.env` copied — `env_files` is skipped for non-Anthropic executors), network off (Seatbelt `workspace-write` default; A− rating `§3.8a`).
- **Claude** keeps PreToolUse hooks (`guards.py:381-490` attached at `session.py:753/755`); the Seatbelt sandbox (`sandbox.failIfUnavailable`, `strictAllowlist`) is a per-executor adapter, not an SDK option (`SYSTEM.md:163` planned it as `ClaudeAgentOptions.sandbox`).
- **INV-22 server-side deny (owner-gated PR, protected `guards.py`):** add broker-host patterns (`api.tradier.com`, `sandbox.tradier.com/v1/accounts/*/orders`, `alpaca…/v2/orders`) to `guards.py:137-149`; council personas never receive brokerage credentials because non-Anthropic executors never get `env_files`, and atlas `env_files` becomes per-vertical (today the whole atlas `.env` lands in every workspace, `workspaces.py:192`).
- **Vendor keys are auth config** (plan `:252-256`): `GEMINI_API_KEY`, `XAI_API_KEY`, Codex `auth.json`, puppet bot tokens — owner-added; guard deny-list extended from the single `ANTHROPIC_API_KEY` literal (`guards.py:148-149, 261-262`) to `GEMINI_API_KEY|XAI_API_KEY|CODEX_API_KEY|TELEGRAM_*_TOKEN` (same protected PR).
- **Data classes:** `sensitivity=proprietary` (theses, positions, shadow ledger) → Claude (training toggle verified **off**, 30-day retention; Fable always 30-day, `claude-anthropic.md §3`) or Codex only after the ChatGPT "Improve the model" toggle is verified off (`chatgpt-openai.md §3`); never Gemini free (`gemini-google.md §3a`).

### 1.7 Event / audit model

Audit kinds added (never renamed): `council_turn{thread,persona,seq,job_id}`, `council_decision`, `deliverable_registered`, `deliverable_reviewed{persona,verdict}`, `provider_selected`, `provider_fallback`, `quota_snapshot`, `shadow_decision`, `merge_gate_verdict` (records the in-session `code-review` verdict that is never stored today, state map §5.20). `jobs:stream:<id>` payloads grow to include `tool_result` previews, `guard_denied`, `rate_limit`, `heartbeat` (today text+tool_use only, `session.py:1146,1154-1157`). `jobs:done` keeps firing before post-steps (C14) but a new `jobs:reviewed:<id>` fires after post-review so cards can flip from "done" to "reviewed".

---

## 2) Interfaces & visibility

### 2.1 Telegram (phone) — the council room

Prerequisite (owner, auth config): create the "AI Council" supergroup with Topics on, add its chat id to `TELEGRAM_ALLOWED_CHAT_IDS` by hand (INV-6, never by a session), create 5 puppet bots in BotFather, put tokens in `.env`. Phase 1 works with **one bot and persona prefixes** (`🟢 Codex:`) and no auth change; puppets are Phase 3.

Commands (all registered; ghost commands `/rate /status <prefix> /cancel <prefix> /proposals` either implemented or removed from help text — state map §5.13):

| Command / gesture | What happens |
|---|---|
| plain text in `#general` | Local classifies intent (schema) → `chat` reply by Claude Sonnet 5 low in ≤5 s, or a job with an immediate ack card |
| `@Codex …`, `@Gemini …`, `@Grok …`, `@Local …`, `@Claude …` | direct turn to that persona (text-only unless Claude); logged as `council_turn` |
| `/council <topic> [--sensitivity proprietary\|owner\|public] [--project slug]` | creates a forum topic + `council_threads` row; Moderator posts the pinned **thread board** |
| `/debate <thesis>` (or `--protocol red-team\|verify\|vote`) | runs a protocol (§2.3); default: Claude proposes → Codex red-teams → Gemini checks sources (public only) → Grok dissents (if enabled) → Claude synthesizes → Moderator extracts |
| `/decide` | Moderator extraction pass; posts decisions with buttons **Accept / Reject / Needs owner**; accepted decisions become `decisions` rows; deliverables become `deliverables` rows with a DoD |
| `/do <ask>` inside a thread | turns the thread's accepted decision into a Task+Job (existing `plans.py` DAG) with `job_origins` bound to the topic |
| `/watch <job8>` | subscribes the topic to live progress for that job (edited-in-place progress card) |
| `/board` | re-posts the pinned boards (queue, quota, schedule, deliverables) |
| `/quota` | per-persona window bars (§2.4) |
| `/schedule list\|run <name>\|pause <name>\|resume <name>\|add "<cron or phrase>" <kind> [--persona X]` | phrase → cron via Local (schema) with confirmation; `run` = enqueue now |
| `/deliverables [thread]` | list with status + URL/path + reviewers' verdicts |
| `/cancel <job8>` | durable cancel (LREM + status flip for queued; interrupt for running — fixes state map §2.2 "cancel cannot reach queued") |
| `/clear` | requires a confirmation button (state map §5.14) |
| `/providers pause <persona>\|resume <persona>` | per-lane kill switch |
| buttons | Approve, Reject, Reopen, Escalate-to-Claude, Ask-again, Details, rate 1–5 (kept but only on `completed` cards) |

Cards are Telegram-native and obey the limits (4096 chars, 64-byte callback data, ≤8 buttons — state map C23). Progress cards are **edited in place** with coalescing (≤1 edit / 4 s per card; Telegram group rate limits ~20 msg/min) so a 40-turn job is one moving card, not 40 messages.

### 2.2 What "watch progress" looks like

Progress card for a job (edited in place from `jobs:stream`):

```
🟠 Claude · atlas-momo-research · running 04:12 · 🔧 17 tools · ⚠ 1 guard deny
now: Bash(pytest -q trader/tests) …
queue-wait 0:38 · slot 1/2 · window 5h 41% (resets 18:05) · est. tokens 212k
[Cancel] [Details] [Watch off]
```
Sources: `tool_use` stream events (`session.py:1154-1157`), the new `heartbeat`/`guard_denied` stream kinds, `provider_quota_snapshots` (§2.4), queue-wait computed from `created_at→started_at` (missing today, state map §2.2 metrics). Terminal card flips to `completed → reviewed (LGTM/changes_requested)` on `jobs:reviewed`, and lists **deliverables with paths/URLs** (today deliverables are truncated text with no path, state map §5.10). Scheduled-job failures post a card to `#ops` immediately (today silent until the 07:15 DM, §5.7).

### 2.3 Debate protocols (engine.py)

Each protocol is a small state machine over `council_turns`; each step is one Job (`kind=council-turn`, persona pinned via `payload.provider`) so it inherits timeout, audit, escalation, quota gating:

- **ask**: one persona, one turn.
- **red-team**: Proposer (Claude) → Critic (Codex; Gemini for public content) → Rebuttal (Claude) → Moderator extraction. Critic prompt requires enumerated, testable objections with severity; rebuttal must address each by id.
- **verify**: claims list (Claude) → Gemini/Grok cite sources (public claims only; Grok `x_search` if enabled) → Local dedupes/normalizes → Moderator marks each claim `supported|contested|unverifiable`.
- **vote**: N personas answer a structured question (schema `{position, confidence, reasons[]}`); Moderator tallies; disagreement above a threshold auto-opens an `owner_decision_required`.
- **standup** (scheduled): Local digests overnight jobs (≤8k tokens) → Gemini/Claude summarize → Moderator posts `#general` morning board.

Turn limits (default 6), a per-thread token budget, and a `council:{thread}:lock` in Redis prevent two protocols racing one topic. Every persona turn is subject to the breaker (`events.py:41-60`) so a cheap persona cannot bypass it (C26).

### 2.4 Cost / quota / schedule visibility (pinned boards)

**Quota board** (`#ops`, edited every 5 min by a `script.py` job):

| Persona | Window | Used | Resets | Source |
|---|---|---|---|---|
| Claude | 5 h / 7 d | 41 % / 63 % | 18:05 / Sun | status-line `rate_limits.five_hour/seven_day` harvested by a short interactive **probe session** every 30 min (only machine-readable Max gauge; not in `-p` output — `claude-anthropic.md §3`, `crosscut-tos §3.10`) + `system/api_retry rate_limit` reset time from `-p` jobs |
| Codex | 5 h / weekly | 12 % / 30 % | … | `account/rateLimits/read` via app-server stdio once per scheduler tick (`chatgpt-openai.md §3`) — the only frontier subscription lane with a vendor quota read |
| Gemini | day | 112/250 req | 00:00 PT | self-metered counter (no Google quota endpoint, `gemini-google.md §3b`) |
| Grok | balance | $3.40 left | — | prepaid balance minus summed `usage`-priced calls (`grok-xai.md §3` cross-cut) |
| Local | RAM | 5.1 GB free | — | `vm_stat`; model resident? `GET /api/ps` |

Per-job **cost strip** on every terminal card: tokens in/out/cache, `cost_usd_est` (list-price estimate; null-marked "subscription" for Claude/Codex), persona, model served. Monthly roll-up posted first of month (plan R5): tokens and estimated-API-equivalent per persona × task class, with the "subscription is justified by chat, not jobs" calibration from `crosscut-finance-trading-ai.md §3` (measured job ≈ 98.5k in at 82 % cache, 1.9k out; ≈$8–14/month metered-equivalent for the scheduled load).

**Schedule board** (`#schedule`): every schedule row with next run, last outcome, adherence flag (DARK/NEVER_RAN/STUCK/FAILURE_STREAK from `schedule_adherence.py`), persona, and buttons Run-now/Pause. **Queue board** (`#ops`): queued (with lane + reason if held: `quota`, `breaker`, `deferred-on`), running, blocked-on-owner (ages shown — fixes state map §5.24).

### 2.5 Laptop: web and CLI

- Web `/council`: the same threads/turns/boards read from Postgres, SSE for live cards (the existing `GET /api/jobs/{id}/stream` finally gets a consumer; token moves from URL to cookie), deliverable links, provider panel, cancel/approve/reopen buttons (routes exist, buttons do not — state map §5.16). Behind CF Access like atlas (dashboard is single-token today, `web.py:49-63`).
- CLI `ai` (thin Python over REST): `ai council new|say|debate|decide`, `ai jobs watch <id>`, `ai quota`, `ai schedule run <name>`, `ai deliverables`. Gives the owner's terminal a canonical `created_by` (today ad-hoc strings, §5.17). Owner terminal sessions can also post *as owner* into the room via the receiver bot, so laptop and phone see one transcript.
- Vendor apps: the owner keeps using claude.ai / ChatGPT / Gemini apps interactively; the council does not proxy them (consumer web apps driven by scripts are Banned everywhere, `00-comparison-matrix.md §1.5`). Optional first-party complements that draw on the same subscriptions: Claude Code cloud **Routines** for repo-scoped jobs when the Mini is down (`claude-anthropic.md §7`), Gemini app Scheduled Actions for the owner's personal digest — both outside the server, linked from the schedule board as "external".

---

## 3) Effectiveness

### 3.1 Definition of done (DoD) on every deliverable

`deliverables.definition_of_done` is a JSON checklist the Moderator writes from the accepted decision and the skill's contract, e.g. for a PR: `{tests: "pytest green", review: "code-review LGTM (Claude)", second_opinion: "Codex verdict recorded", changelog: true, deployed: "server-deploy green", url: "required"}`; for a research memo: `{numbers_from_tools: true, citations: "≥1 per claim", critic_pass: "Codex red-team round with all objections addressed", no_positions_leaked_to_free_lanes: true}`. Nothing flips to `accepted` until every DoD item has an `evidence` pointer (job id, audit event, URL, test output path). Owner acceptance is a button; auto-acceptance is allowed only on the execution lane where MISSION §M already permits it (gate-green + agent LGTM + owner notification).

### 3.2 Evidence

Evidence is structured, not prose: `merge_gate_verdict` (in-session `code-review` verdict captured from the subagent's structured output instead of text in the parent transcript, state map §2.5), `post_review_flagged/skipped` (fix the 600 s timeout gap that stamps no verdict, `main.py:620-626`), `deliverable_reviewed{persona,verdict,findings[]}`, eval scores persisted (`evals/results/` has only `.gitkeep` today). Summaries stay executor-agnostic (`TASK_COMPLETE:` markers) but every council-produced artifact also gets a `deliverables` row with path/URL.

### 3.3 Review / grading

- **Anthropic remains the gate** (INV-13/INV-21c): in-session `code-review` LGTM for merges; `_evaluate` for tasks; post-review fixed reviewer (`review.py:247-256`).
- **Cross-vendor review is additive**: Codex (highest independence from Claude, `crosscut-tos §5.2a`) writes `DISSENT/CONCUR` findings on Claude-authored diffs and theses; Gemini-free reviews public memos; Kimi/MiniMax/DeepSeek/Qwen are excluded as reviewers of Claude work (named in distillation disclosures, `§5.2a`). Independence is **measured**: pairwise Jaccard overlap of normalized findings per reviewer pair per month; a pair >0.7 is flagged "not a second opinion" (`runtimes-aggregators.md §3(g)`).
- Writer's vendor never reviews its own lane (C5); reviewer selection is policy, never the writing skill.

### 3.4 Provider scoreboard and qualification

`provider_scores` rolls up per (persona, model, task_class): judge score (evals judge via registry, `evals/run.py:48` un-pinned only for non-gate classes), `review_outcome` LGTM rate, agreement rate with the anchor on `vote` protocols, p50 latency, tokens, escalations. Ladder per plan §6g: **shadow** (utility seam emits `shadow_decision` while Claude still decides) → **canary** (capped share of low-stakes live jobs, `payload.provider`) → **qualified** (enters chain) → **demoted** on failure-rate delta (breaker). State in `provider_qualifications.yml`; promotions are `default-model` proposals (never used today: 0 of 39) approved by the owner while lanes are young. Surfaced on the web provider panel and a monthly `#ops` card. Human ratings stay (2/1633 used) but are removed from rollups in favor of collectible signals (state map §2.5 Opportunities).

### 3.5 Routing measured

`routing_decision` confidence is thresholded (today discarded, `session.py:616`); `--kind` corrections and `/decide` rejections are captured as ground truth; Local-first routing is compared to the Haiku router in shadow for two weeks before it goes live (plan R1 gate: routing-precision eval ≥ baseline on `evals/` router cases).

---

## 4) Scheduling across vendors

- **Schedules become data**: `schedules.yml` (tracked) with `name, cron, kind, payload{project_slug, session_timeout_seconds, provider, model, effort}, misfire_policy ∈ skip|catch_up_once, sensitivity, owner`; a Python seeder validates cron slot collisions, DST-anchored ET rows, and provider capability (a `provider: gemini` schedule may not name a write-tool skill) and replaces the 41-line `seed-schedules.sh` (sole payload writer, `22-47`). Scheduler commits before RPUSH (the race the retry ladder absorbs, `main.py:1327-1362`) and advances `next_run_at` from the slot.
- **Lane-aware job loop**: `jobs.lane` derived from `(provider, created_by)`; per-provider pause keys (`quota:{provider}:paused_until`) replace the global key (`quota.py:21`, never fired in prod: 0 `rejected`/0 `job_requeued_for_quota` in 620+ logs); a job waits only when **no** lane in its class chain is healthy (plan §6f). Owner-interactive jobs get a reserved slot (FIFO starvation behind daily atlas rows, state map §2.2).
- **Fan-out per lane** from the quota pollers, not slot counts: start Claude 2, Codex 1 (one `auth.json` stream), Gemini 1, Grok 1, Local 1 (`crosscut-tos §3.10b`); raise only after a week of clean `rate_limit` telemetry. Host RAM guard: no local model resident during Claude job windows (`crosscut-finance §3` host budget).
- **Council rituals as schedules**: `standup` 07:30 (Local+Claude), `atlas-research-council` Wed 13:00 (red-team protocol over the week's research memo; Codex critic), `weekly-scoreboard` Sun, `quota-board` every 5 min (`no_llm`), `credential-canary` daily (Claude `-p ping` + `codex login status` + Gemini 1-req + Ollama `/api/ps`; alarms at T−30 d for `setup-token`, T−7 d for OAuth lanes — `crosscut-tos §3.10c`).
- **Adherence**: `schedule_adherence.py` output feeds the `#schedule` board and a same-tick DM on failure; the daily 07:15 launchd job stays as the out-of-band belt.
- **External schedulers as first-class links**: Claude Routines (`/fire` API with per-routine bearer, ≥1 h interval, daily run cap) and Codex scheduled tasks appear on the board as `external` rows with last-run status pulled by a poller; never as a replacement for the server scheduler (they cannot see local files).

---

## 5) Project delivery path

1. **Intake in the room**: `/council "pickem week-3 fixes" --project pickem` → thread + board. Owner and personas discuss; `/decide` extracts decisions and deliverables with DoD (PR, deploy, URL).
2. **Plan**: Claude produces `<<<TASK_PLAN>>>` (existing DAG, `plans.py:62-110`); Codex red-teams the plan (text-only); Moderator records objections and the owner's Accept.
3. **Build**: Claude workspace-tier job (`workspaces.py`), guard hooks on, project delivery contract (`delivery.py:130-147`), commits pushed to the project's canonical remote.
4. **Review**: in-session `code-review` LGTM (Anthropic gate) recorded as `merge_gate_verdict`; Codex `--sandbox read-only` second opinion on the diff in a throwaway clone (no atlas/project `.env` copied); both verdicts on the deliverable card. INV-13 post-review becomes **pre-push** for workspace diffs where feasible (state map §2.7 Opportunities) and fail-closed on timeout.
5. **Deploy**: existing `deploy-director`/`server-deploy`/`atlas-redeploy` dispatch (gate-green); the deliverable card flips to `deployed` with the healthcheck evidence and the public URL; `#project:<slug>` topic gets the card.
6. **Close**: Moderator checks DoD; owner taps Accept (or auto-accept on the execution lane with owner notification per MISSION §M); learning extractor runs (gated on Write/Edit events as today, `learning.py`).

Server-code work (`code-server` class) never leaves Claude and always needs the INV-4 gate; protected paths still need explicit owner approval, and the Moderator refuses to auto-accept a deliverable whose diff touches a protected path (list from MISSION §M, checked by path — today no code checks the 8 paths, state map §2.7 INV-4).

---

## 6) Trading research automation within INV-22

**Boundary restated:** no order path on this server, ever; the only order path is `atlas/swing/swing/executor.py --submit` behind `risk.validate` (`:535, :599`), sandbox-pinned and owner-gated. Council personas produce research, theses, adversarial review, sentiment features, evaluation — and each persona's AUP is satisfied by exactly this owner-only, human-on-the-order-path posture (`crosscut-finance §6`: Anthropic consumer securities clause; xAI "unlawfully… securities"; OpenAI "tailored advice without review"; Google/Mistral/Z.ai advice clauses).

| Step | Runs where | Persona adds | Data / credential boundary |
|---|---|---|---|
| Data pull (bars, filings, calendar) | Claude workspace job with **stdio MCP**: Alpaca paper, `sec-edgar-mcp`, Massive Basic, Finnhub (`crosscut-finance §7`) | deterministic; `disallowed_tools=[WebSearch, WebFetch]` in evaluation runs (no look-ahead) | keys in atlas env only; per-vertical `env_files` (not the whole atlas `.env`); Tradier remote MCP only with paper token + read-only tool names, or off the box |
| Headline/news triage | Local `qwen3.5:4b` classify + `embeddinggemma` dedupe → clusters to Claude (`local-models §6`) | $0, private | nothing leaves the box |
| Sentiment feature | **Grok** `grok-4.3` + `x_search` (handle allowlist ≤20, date window, `store:false`), once per research job, into an append-only `sentiment_snapshots` table, overlay tag only, forward-paper only (state map §2.6 Opportunities) | only programmatic first-party social feed (`crosscut-finance §6`) | metered (owner decision D2); no positions in the prompt; outputs labelled "research", never "advice" |
| Thesis / memo | Claude (Opus 5.5 medium; Fable for hardest) with tool-grounded numbers | analyst | `sensitivity=proprietary`; Claude training toggle verified off; Fable = 30-day retention accepted (D9) |
| Adversarial validator | Claude clean-context subagent (constitution-bound, kill-standing) — **kept** | gate | unchanged |
| Second-vendor critic (additive) | **Codex** text-only red-team of the memo; Gemini-free only for memos with **no positions/theses** (public-data) | independence (`crosscut-tos §5.2a`) | ChatGPT "Improve the model" off before any thesis (D5); Gemini free never sees proprietary content |
| Governor grading | Claude frozen evaluator from DB rows — kept; moved to `isolation: workspace` with read-only DB role where possible (today `none` with psql write, state map §2.6) | gate | protected allowlist edit (D6) |
| Council ritual | `atlas-research-council` Wed: verify + red-team protocol over the week's memo; `owner_decision_required` items (e.g. D-0001 DSR ratchet) posted to `#atlas-research` with buttons | visibility | decisions land in atlas ledgers via the existing LOOP.md §7 front door, not by the Moderator writing atlas files |

Plumbing fixes that precede any vendor (state map §2.6): provision `TRADIER_SANDBOX_TOKEN` + `FINNHUB_TOKEN` (owner), patch `weekly.py:316`, Alpaca→yfinance/Tradier data fallback; a lint diffing ai-server atlas skills against atlas staging (15/26 drifted). Market-hours change 2026-12-06 (23/5 SIP) → every job spec pins `session` explicitly (`crosscut-finance §6`).

---

## 7) Vendor plan

| Vendor / persona | Surface used | Auth | Cost path | ToS status (research) | Task classes here | Not used |
|---|---|---|---|---|---|---|
| **Anthropic / Claude** | Claude Agent SDK (bundled CLI, pinned), `stream-json`; interactive probe session for `rate_limits`; OTEL (`CLAUDE_CODE_ENABLE_TELEMETRY=1`, OTLP http/json to a gateway route, no collector daemon) | Max subscription; `setup-token` one-year token in launchd env + Keychain login; **never `ANTHROPIC_API_KEY`**, never `--bare`; training toggle off; `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` | included (INV-3) | **Allowed\*** — own Max, unmodified binary, "ordinary, individual usage"; revocable (`claude-anthropic.md §3`; `crosscut-tos §3.7`) | all; pinned gates; chat via Sonnet 5 low/medium | third-party harnesses (Banned); Managed Agents/`--bare` (API key); serving non-owners |
| **OpenAI / Codex** | `codex exec --json --output-schema` (Rust binary, brew cask, pinned); app-server `account/rateLimits/read` for quota | `codex login --device-auth` on ChatGPT **Free** (D3 may raise to Plus $20); `auth.json` 0600 per stream; `features.goals=false`; `otel.metrics_exporter="none"`; "Improve the model" off | included ($0 Free; Plus $20 if D3) | **Gray/Yes\*** for owner-only, owner-read output; API key recommended for anything scheduled at volume or seen by others (`chatgpt-openai.md §3, §7`) | second-opinion review, debate critic, research-read; `code-project` canary later | serving non-owners; goal mode; cloud tasks (need ChatGPT auth features Free lacks) |
| **Google / Gemini** | Gemini Developer API (OpenAI-compat endpoint or `google-genai`), `gemini-3.8-flash` `thinking_level=low` | unpaid AI Studio key (250 RPD, Flash only) — **trains + human review** (`gemini-google.md §3a`) | free ($0) | **Allowed** on own key; Antigravity/Gemini-CLI OAuth via third-party tools **Banned** (account termination) | `utility-classify`, public summarization, public-memo review, `verify` source checks | anything proprietary/owner-sensitive; Antigravity headless (auto-denies tools, 10 releases/13 days); Gemini CLI login lane (disputed) |
| **xAI / Grok** | Responses API `api.x.ai/v1` (OpenAI-compat), `x_search`, `store:false`; ZDR self-serve if enabled | `XAI_API_KEY` prepaid credits (min $5, expire 1 yr) — **owner decision D2** | metered, small (est. $1–5/mo at one call per research job + debate turns on `grok-4.3`) | API: **Allowed** (enterprise ToS, no training, 30-day delete); seat headless: **Grey** — not used (`grok-xai.md §3, §8`) | sentiment feed; dissent turns; bulk 1M-ctx summarization | Grok Build subscription headless; Grok Bot (cloud, not scriptable); seat output to others |
| **Local / Ollama** | `localhost:11434` native REST (`format` schema) or `/v1/messages`; `qwen3.5:4b`, `qwen3.5:9b`, `embeddinggemma`; remove the 14 GB of stale weights (phi3, deepseek-coder-v2, mistral — zero requests ever, state map §2.8) | none | $0 | n/a (MIT runtime, Apache-2.0 weights); LM Studio not used (no-SaaS EULA) | classify, route, extract, embed, dedupe, ≤8k digests; chat fallback when Claude is rate-limited | research, coding, review, theses (30–50 % fabricated repo facts, `local-models §5`) |
| **Moderator** | code + Claude Sonnet 5 low for extraction | subscription | included | — | extraction, boards | — |
| Considered, **not adopted** (need separate owner decisions): Perplexity Agent API `finance_search` (metered; only vendor-native finance tool), Ollama Cloud Pro $20 (credit-bundled, policy-clean bulk lane), Mistral Pro credits, GLM-5.3-Flash on Z.ai API (cheapest reviewer for public memos), OpenRouter metered (DECLINED 2026-08-17), Kimi/MiniMax/DeepSeek (data terms + distillation exposure), Cursor/Copilot/Kiro seats, OpenClaw/Hermes runtimes (borrow designs; do not run — `runtimes-aggregators.md §8`). |

Vendor churn is an operating cost: pin every binary/SDK, nightly `--version` + one-prompt smoke test, smoke-test `claude -p ping` on every SDK bump because `--bare` may become the `-p` default and break subscription auth (`claude-anthropic.md §7`). Claude Code shipped 10 releases in 10 days; Codex weekly; Antigravity 10 in 13 (`00-comparison-matrix.md §1.10`).

---

## 8) Migration & rollout

Everything runs on the existing runner throughout; each phase ships behind a switch and can be reverted by env var.

| Phase | Scope | Entry | Exit criteria | Kill switch / what keeps running |
|---|---|---|---|---|
| **P0 Foundations** (plan R0+R2, ~3 wk) | `providers.yml` + registry + policy skeleton (anthropic-only); migration 007 (provider/tokens/cost/origin columns); `executors/base.py` + `claude_sdk.py` extracted behavior-identically; `utility.py` seam replacing 4 loops; per-provider quota keys (anthropic only); `notify.py`; `job_origins` populated by every launcher; ghost commands fixed; `no_llm` → `script.py` | owner signs nothing new (MISSION already amended) | full pytest + `lint_docs.py` green; replayed job → identical audit sequence; `resolved_provider='anthropic'` on 100 % of new jobs; completion DMs reach 100 % of Telegram-launched jobs across bot restarts | `ROUTER_PROVIDERS_ENABLED=anthropic` (plan §2); no behavior change otherwise |
| **P1 Council v0 + utility lanes** (plan R1, ~2 wk) | `src/council/` threads/turns/moderator; single bot with persona prefixes; `/council /debate /decide /watch /board /quota`; Local (pull qwen3.5, drop stale weights) and Gemini-free on `utility-classify` in **shadow**; Claude-only debates (Claude vs Claude clean-context critic) so the protocol machinery is proven before a second vendor | owner: Gemini key in `.env`; confirm Claude training toggle off | routing-precision shadow ≥ Haiku baseline for 2 weeks; `provider_fallback` audits reviewed; ≥10 council threads with extracted decisions; progress cards edited in place | `COUNCIL_ENABLED=false`; `ROUTER_PROVIDERS_ENABLED=anthropic` |
| **P2 Codex persona** (plan R3 narrowed, ~2 wk) | `codex_cli.py`; device-auth on ChatGPT Free; text-only debate critic + `--sandbox read-only` diff review in throwaway clone; `merge_gate_verdict` recorded; `provider_scores` + independence overlap job | owner: `codex login --device-auth`; ChatGPT "Improve the model" off | 30 Codex reviews with zero guard-equivalent violations; Anthropic LGTM rate on Claude diffs unchanged; overlap Jaccard reported | `/providers pause codex`; policy deny list |
| **P3 Puppet bots + topics + web/CLI** (~2 wk) | 5 send-only persona bots; forum topics; `job_origins`→topic routing; web `/council` + SSE; `ai` CLI; quota/queue/schedule boards | owner: supergroup id in `TELEGRAM_ALLOWED_CHAT_IDS` (INV-6, by hand), bot tokens in `.env` | boards refresh <5 min; owner runs a full project delivery (§5) from the phone end-to-end | fall back to single-bot prefixes (`COUNCIL_PUPPETS=false`) |
| **P4 Failover + scheduling-as-data** (plan R4, ~2 wk) | class-aware pause; schedules.yml + Python seeder + misfire policy; lane-aware loop with owner reserved slot; credential canaries; council rituals scheduled | — | simulated Anthropic pause drill: routable lanes keep draining, pinned lanes pause, `#ops` card posted; 41 schedules migrated byte-for-byte | old `seed-schedules.sh` kept one release as fallback |
| **P5 Grok + trading council + qualification autopilot** (plan R5, ~2 wk) | Grok sentiment feed (if D2 yes); `atlas-research-council` ritual; INV-22 server-side deny + per-vertical `env_files` + guard key names (one owner-approved protected PR); qualification ladder proposals; monthly cost card | owner: D2, D6, D7 approvals | first monthly scoreboard with real numbers; first `owner_decision_required` resolved from the room; 0 broker-host guard denies triggered by design (tripwire test) | `/providers pause grok`; guard PR revert |

Rollback rule per phase: the phase's switch off + `git revert` of its commits; DB migrations are additive only (no column drops) so a rollback never loses data.

---

## 9) What gets deleted / rewritten vs kept (honest register)

| Element | Verdict | Action |
|---|---|---|
| `_build_options` monolith (`session.py:650-816`), `_run_in_process` | accidental (state map §6) | rewritten into `ExecSpec` + `claude_sdk.py`; zero-diff audit replay gate |
| `_MODEL_ALIASES` as CI allowlist (`telegram_bot.py:122-134`; `tests/test_skill_contracts.py:24`); web 3-id dropdown (`web.py:689-691`) | accidental | deleted; `providers.yml` feeds aliases, `VALID_MODELS`, dropdown, budgets |
| Four `query()` loops (router/learning/review/judge) | accidental | one `utility.py`; review stays a 6-turn agent call but through the registry with the Anthropic pin |
| Global `quota:paused_until` (`quota.py:21`) | accidental (now blocking) | per-provider keys; INV-12 semantics kept per lane (`tests/test_quota.py` extended) |
| Banner regex `_API_TERMINAL_BANNER` (`session.py:495-534`) | accidental | replaced by typed `api_error_status`/`stop_reason`; regex kept one release as a belt |
| Dropped `ResultMessage` fields (`session.py:1095`) | accidental | captured to columns |
| `Task.chat_id`/`thread_message_id` binding; `_job_to_chat` dict | accidental | `job_origins` table |
| `telegram_bot.py` monolith; three Telegram senders; `_error_safe` self-diagnose dispatch (42 lifetime) | accidental | package + `notify.py`; auto-dispatch capped by breaker |
| `JobKind` enum + dual `deploy_director`/`deploy-director` spellings | accidental | enum retired; `kind` validated at enqueue against `skills/` + `council-turn` |
| Payload JSON as control plane (`escalation_level`, `depends_on`, `eval_round`) | accidental | typed columns/`job_attempts`; auto-continue stops inheriting `escalation_level` |
| `seed-schedules.sh` + hand-commented cron de-confliction | accidental | `schedules.yml` + validating seeder |
| Inline-HTML htmx dashboard | accidental | templates/static app behind CF Access with SSE consumer |
| `review-and-improve` at opus-4-7/max on idle (28 runs/30 d, ~1.3 M cache-read each, 11 pending proposals) | accidental cost | `no_llm` SQL pre-pass + weekly cadence + `skill_performance` (0 callers today) wired with provider group-by |
| `self-diagnose` on every L2/L3 (21 % of all jobs) | accidental | error-class gating; quota/auth/network classes never spawn a diagnose session |
| `isolation: none` default + 44-name allowlist (`lint_docs.py:612-635`) | accidental debt, protected | flip default to `workspace` per vertical in **one owner-approved PR** (D6); INV-21(a) precondition |
| Idle Ollama with 14 GB stale weights; no off-site backup; atlas DB outside dump; `autorestart 0` | ops debt | fix in P1 (Ollama) and alongside P0 (rclone R2 + `pg_dump atlas` + sealed `.env` copy) — cheaper than anything above |
| JSONL audit, text markers, workspace clone, guard predicates, `enqueue_job`/queue contracts, in-session `code-review` gate, atlas order path + tripwires, out-of-band alerters, SDK `<0.2` + `mcp<2` pins | **load-bearing** | kept; kinds/columns added, never renamed; the executor seam isolates the fragile SDK edge rather than removing the pin |

Not built: a general agent framework, OpenClaw/Hermes as runtime, LiteLLM daemon (4 GiB floor + March 2026 supply-chain compromise), Langfuse (needs the whole machine), a second Telegram receiver bot, any order tool.

---

## 10) Risks & mitigations

| Risk | Mitigation |
|---|---|
| Anthropic re-gates `-p`/SDK on subscriptions or flips `--bare` default (`claude-anthropic.md §3, §7`) | pin CLI/SDK; smoke test on bump; `setup-token` + Keychain both present; Routines as the repo-only fallback lane; design portable to usage credits (owner call) |
| Council turns burn the Max weekly window (post-2026-09-14 re-basing, `crosscut-tos §8.3`) | chat = Sonnet 5 low; debate turns capped (6) and token-budgeted; utility on Local/Gemini; quota board + pre-dispatch gating on `rate_limits` probe; owner reserved slot |
| Codex on Free tier has too little quota for real review load | shadow first; `account/rateLimits/read` gating; D3 raise to Plus if evidence says so |
| Gemini free key trains on content / human review | `sensitivity` gate hard-coded in policy; lint rule: no `proprietary` thread may resolve to `gemini-free`; unpaid tier unavailable in EEA/UK — n/a here |
| Free-tier churn (Gemini quota rugs, model IDs retired) — accepted risk per plan §10.3 | breakers turn churn into a logged degradation; every chain ends in an included-cost lane |
| Telegram as SPOF; edit rate limits; 4096-char cards | boards coalesce edits; out-of-band alerters unchanged; web/CLI mirror the room |
| Persona sprawl → owner confusion / noise | topics per project; Moderator posts only decisions/boards; personas speak only when addressed or in a protocol step; `/mute <persona>` |
| Reviewer independence overstated | measured overlap; Chinese lanes excluded as reviewers of Claude work; Codex/Gemini first (`crosscut-tos §5.2a`) |
| Prompt injection through relayed web content | non-Anthropic personas text-only; Claude web fetch isolated context; `verbatim_prompts` once SDK ≥0.2.158; guard hooks unchanged |
| Executor extraction regresses containment | zero-diff audit replay; 56 guard predicate tests + new end-to-end hook wiring test (untested today, state map §2.1) |
| INV-22 leak via atlas `.env` in every workspace once `TRADIER_SANDBOX_TOKEN` lands | per-vertical `env_files`; broker-host deny in `guards.py`; non-Anthropic executors never receive `env_files`; tripwire test in ai-server |
| 16 GB RAM: Ollama + 2 Claude subprocesses + Codex | memory guard before local calls; `OLLAMA_MAX_LOADED_MODELS=1`; no local model resident in job windows; `MAX_CONCURRENT_JOBS` stays 2 |
| Vendor churn (10 releases/10 days) | pinned binaries, nightly smoke tests, weekly bump budget |
| Grok (if enabled): repo-upload incident history, outages, single corporate group | API-only, never Grok Build headless; `store:false`; swappable behind the registry; non-critical lane |

---

## 11) Owner decisions required

1. **D1 — Council supergroup + puppet bots (auth config, INV-6):** create the group with Topics, add its chat id to `TELEGRAM_ALLOWED_CHAT_IDS` by hand, create up to 5 BotFather tokens. Phase 1 works without it (single bot, prefixes).
2. **D2 — Grok persona:** (a) prepaid xAI credits (~$5 once, est. $1–5/month) for `x_search` sentiment + dissent turns — a small, explicit metered exception; or (b) no automated Grok persona (owner uses SuperGrok interactively only). Recommendation: (a) if the sentiment feature column is wanted; otherwise (b). Grok is never "native in Telegram" either way.
3. **D3 — Codex tier:** stay on ChatGPT Free (approved 2026-08-17) for P2 shadow; raise to Plus ($20) only if `account/rateLimits/read` shows the review load does not fit.
4. **D4 — Gemini unpaid key confirmed** with scope = public/non-sensitive only (approved 2026-08-17; this design adds the `sensitivity` gate).
5. **D5 — Training toggles:** verify "Help improve Claude" **off** and ChatGPT "Improve the model for everyone" **off** before any thesis or diff reaches those lanes.
6. **D6 — Protected-path PR #1 (`lint_docs.py`, `guards.py`):** flip `isolation` default to `workspace` per vertical, shrink the 44-name allowlist, move trading governors to workspace + read-only DB role, add vendor key names to the guard deny list.
7. **D7 — Protected-path PR #2 (`guards.py`, MISSION §M unchanged):** INV-22 server-side broker-host deny + per-vertical `env_files`.
8. **D8 — SDK pin bump** from 0.1.81 to ≥0.2.158 (for `verbatim_prompts`, typed fields) as a gated release with the `--bare` smoke test.
9. **D9 — Data retention acceptance:** theses on Claude = 30-day retention (Fable always); Codex plan-auth = consumer retention with training off; no ZDR anywhere under current policy.
10. **D10 — Ops debt now:** remove 14 GB stale Ollama weights and pull `qwen3.5:4b/9b` + `embeddinggemma`; configure rclone R2 off-site backup + `pg_dump atlas`; `pmset autorestart 1`.
11. **D11 — Not adopting (confirm):** Perplexity API, Ollama Cloud Pro, Mistral Pro, Z.ai API, OpenRouter metered, extra seats. Each can be re-opened by evidence from the scoreboard.
12. **D12 — Atlas blockers:** provision `TRADIER_SANDBOX_TOKEN` and `FINNHUB_TOKEN` (owner-side per LOOP.md §7).

---

## 12) Effort and cost

**Agent time (sequential, with the review gates above):** P0 3 wk · P1 2 wk · P2 2 wk · P3 2 wk · P4 2 wk · P5 2 wk ≈ **13 weeks** of agent time (≈10 with P3/P4 overlapping), plus ~2 weeks of shadow/canary soak that is calendar, not effort. **Owner time:** ~1 day total across D1–D12 (group + bots 30 min; three logins 30 min; two protected-path PR reviews 2–3 h; key provisioning 30 min; monthly scoreboard glance).

**Monthly cost:** Claude Max (existing, unchanged) + Codex $0 (Free) or $20 (Plus, D3) + Gemini $0 + Local $0 (≈$0.05–1 electricity, `local-models §4`) + Grok $1–5 if D2(a) → **≈$0–5/month incremental on top of the Max seat** ($20–25 with Plus). No new daemons beyond Ollama (already installed): OTEL lands on a FastAPI route, not a collector (`crosscut-tos §3.10a`, `crosscut-finance §3` sink choice). Reference point from the research: the whole scheduled load would be ≈$8–14/month metered (`crosscut-finance §3` calibration) — the subscription is justified by the interactive room, which is exactly what this design makes central.
