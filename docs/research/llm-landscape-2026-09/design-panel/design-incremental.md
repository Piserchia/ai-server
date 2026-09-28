# Design: Incremental — execute R0–R5 and bolt on the missing surfaces (2026-09-24)

Lens: least change that satisfies the ask. Reuse `docs/superpowers/plans/2026-08-10-model-router.md` (APPROVED 2026-08-17) where it still holds, amend where `docs/research/llm-landscape-2026-09/` shows it is stale, and add only the visibility/effectiveness/surface pieces it lacks. Every `file:line` below is from the 2026-09-24 state map (`scratchpad/current-state-map.md`, relative to the repo root); research citations are `<doc>.md §N` in `docs/research/llm-landscape-2026-09/`.

## 0) Thesis

The server already has a vendor-neutral lifecycle (job row + `jobs:queue` + JSONL audit + `<job>.summary.md` + text markers + workspace clone/ff-sync; state map §6 "load-bearing") wrapped around exactly one Anthropic-shaped executor (`session.py:650-816`, `:1048-1132`) and zero visibility (no provider/cost/token columns, SSE nobody renders, DMs reaching ~3 % of jobs; state map §5). The approved router plan already names the right seams (registry, policy, executor protocol, `utility_call`, per-provider quota, `resolved_provider`, qualification ladder) and the owner already fixed the money rules (Codex Free, OpenRouter free-only, Gemini unpaid key, Anthropic pinned for review/evaluate/server-code). So the incremental path is: land R0–R5 as written with six research-driven amendments (models, the dead Gemini login lane, Codex quota introspection, Claude `--bare`/setup-token hardening, `rate_limit_status` aggregation, Codex as an *additive* second reviewer), then bolt on the missing surfaces — a migration that stores what the SDK already hands us, a `/providers` + `/usage` card, a rendered live-progress pane, persisted job→origin so every launch gets its DM, schedule controls from the phone, stored review verdicts and a provider scoreboard — without touching protected paths except in two owner-approved PRs. Under the standing free-tier policy the owner gets resilience, visibility and a measured second opinion at $0 incremental; what he does **not** get (§9, §11) is a real second *executor* carrying load (Codex Free is probe-only), any metered sentiment/finance data lane, a rewritten dashboard, priority queues, or OS-sandboxed Claude jobs.

### 0a. Amendments to the 2026-08-10 plan (what the research made stale)

| Plan claim (§) | Research finding (2026-09-24) | Amendment in this design |
|---|---|---|
| §5 Codex "works on every plan incl. Free" as a load-carrying lane | Codex is included on Free/Go, but published 5-hour message bands start at Plus (Astra 5–45 / Sol 15–150 / Luna 350–3,000); Free is "explore" (chatgpt-openai §3; matrix §2) | Free = probe + second belt when quota allows; carrying load is owner decision 1 |
| §5 "Codex non-interactive MCP is broken → Codex lane gets no MCP" | `default_tools_approval_mode` and per-tool `approval_mode` now exist in `config.toml` (chatgpt-openai §7); MCP works headless | Keep "no MCP on Codex" anyway — dispatch/projects MCP are in-process SDK servers (`mcp_dispatch.py:20,145`) and containment is simpler without them; the reason changed, the rule did not |
| §5 Gemini "personal-account tier ~1000/day" | Gemini CLI Google-login lane ended 2026-06-18 for unpaid/Google One; AI Plus unlocks nothing; unpaid key = 250 RPD Flash-only and **trains + human review** (gemini-google §3, §3a; runtimes §1) | `gemini-free` is HTTP-only, `sensitivity: public` only; no Gemini executor |
| §5 OpenRouter "~14 :free models, 20 req/min" | 22 `:free` variants, 20 RPM, 50 RPD (<$10 lifetime) / 1,000 RPD; account toggle "allow training providers" per free/paid (runtimes §3) | toggle off; RPD counter in Redis; middle link only |
| §5 local "qwen3:4b" | Qwen3.5-4B (3.4 GB) is the current fit; live Ollama holds 14 GB of stale weights and has zero callers (local-models §7; state map §2.8) | pull `qwen3.5:4b` + `embeddinggemma`, delete stale weights, memory guard |
| §6a model ids (`gpt-5.6-codex`, `claude-sonnet-4-6`) | Opus 5.5 ($4/$20, 2026-09-22), Sonnet 5, Haiku 4.5 retires ≥2026-10-15; GPT-6 Sol/Luna/Astra; bundled CLI 2.1.139 may reject new ids silently (claude-anthropic §7) | ids live in `providers.yml`; router/learning stop hardcoding `claude-haiku-4-5-20251001` (`llm_router.py:148`, `learning.py:258`); `model_usage` assertion guards silent-success |
| §6f "no lane exposes remaining budget" (implicit) | Codex app-server `account/rateLimits/read` + `updated` push; Claude SDK already emits typed `RateLimitEvent` with utilization/resets_at (635 prod events, never aggregated; `session.py:1065-1082`); status-line JSON is interactive-only (crosscut-tos §3.10) | `provider_quota_snapshots` fed by SDK events (Claude) and a 15-min RPC poll (Codex); no scraping |
| §7 "GPT reviewing anything is not in-plan" (R6+) | Codex/Gemini rank **high** independence for reviewing Claude output; Kimi/MiniMax/DeepSeek named in distillation disclosures (crosscut-tos §5.2a); state map §2.6 names a second-vendor critic the highest-value insertion | Codex second belt brought into R3 as *additive* and informational; Anthropic verdict of record unchanged (INV-21 pin intact) |
| §8 INV-21(b) "Codex Seatbelt workspace-write" | confirmed A− rating; network off by default; goal mode on by default burns the window; `otel.metrics_exporter` defaults to `statsig` (chatgpt-openai §3; crosscut-tos §3.8a) | add `--ephemeral`, `features.goals=false`, `metrics_exporter="none"`, `web_search="cached"` to the lane contract |
| — (not in plan) | `--bare` "will become the default for `-p`" and never reads OAuth; `claude setup-token` one-year token; `-p` runs get no auto-continue at the limit (claude-anthropic §3; crosscut-tos §3.1) | SDK pin gate + smoke test; setup-token in launchd env; scheduler owns back-off from the reset time in the limit error |
| — (not in plan) | Consumer training toggles default on for Claude and ChatGPT; theses are 30-day retained at best (crosscut-tos §3.8) | `sensitivity` frontmatter + audit assertion; owner decision 5 |

## 1) Architecture

### 1a. Components (kept / extracted / new)

| Component | Status | What changes |
|---|---|---|
| `src/gateway/jobs.enqueue_job` + `jobs:queue` + Job row | **kept** | adds `origin_channel/origin_ref`, `provider`, `priority` fields on the payload→columns path (§1b) |
| `src/runner/main._job_loop` (`main.py:113-185`) | kept, 20-line change | pause check becomes `quota.is_paused(provider_for(job))`; QuotaExhausted carries provider (`main.py:446-458`) |
| `src/runner/session.run_session` (`session.py:864`) | kept | resolution stays; `_run_in_process` moves verbatim into `executors/claude_sdk.py`; call site `main.py:376-380` becomes `executors.get(spec.provider).run(spec)` |
| `_build_options` (`session.py:650-816`) | **extracted**, behavior-identical | split at its five existing seams (prompt 664-692, resolution 694-724, subagents 730-736, guards 752-755, MCP 757-796) into an `ExecSpec` + `to_claude_options()`; no vocabulary rename |
| `src/providers/registry.py` + `providers.yml` | **new** (plan §6a) | one catalog feeding `_MODEL_ALIASES` (`telegram_bot.py:122-134`), `VALID_MODELS` (`tests/test_skill_contracts.py:24`), web dropdown (`web.py:689-691`), `_MODEL_BUDGETS` (`session.py:466-471`), `config.default_model` (`config.py:25`) |
| `src/providers/policy.py` + `routing-policy.yml` | **new** (plan §6d) | `select(task_class, required_caps, sensitivity) → [provider]`; audited `provider_selected{reason}` |
| `src/providers/completions.py` `utility_call()` | **new** (plan §6c) | replaces the four copy-pasted `query()` loops (`llm_router.py:156-168`, `learning.py:266-278`, `review.py:258-278`, `evals/run.py:74-100`); schema-validate-and-retry; fail-open only where the caller is fail-open today |
| `src/runner/executors/{base,claude_sdk,codex_cli}.py` | **new** (plan §6b) | `Executor.run(spec) → AsyncIterator[ExecEvent]`, `interrupt()`, `kill()`; Codex maps `codex exec --json` items onto today's audit kinds |
| `src/runner/quota.py` | generalized | `quota:{provider}:paused_until`; `rate_limit_status` events (635 in prod, never aggregated; state map §2.2) written to `provider_quota_snapshots` |
| `alembic/versions/007_provider_and_usage.py` | **new** | §1b |
| `src/gateway/notify.py` | **new, small** | one Telegram sender used by bot + `_finish_job` DMs; scripts/Worker untouched this round |
| `src/gateway/web.py` dashboard | extended, not rewritten | providers strip, cost tile, live-job pane (htmx `sse` ext on the existing `GET /api/jobs/{id}/stream`), schedule buttons |
| `scripts/seed-schedules.sh` | kept | payload gains optional `provider`/`model` per row; `/schedule run|pause|resume` added on the bot |
| `guards.py`, `lint_docs.py` | **protected** | two owner PRs only: (a) add vendor key names to the deny list + broker-host INV-22 deny (`guards.py:137-149`); (b) lint rules over `routing-policy.yml` + wire the four unwired checks (`lint_docs.py:729-746`) |

### 1b. Data model (migration 007, additive only)

`jobs` gains: `resolved_provider VARCHAR(32)`, `input_tokens/output_tokens/cache_read_tokens/cache_write_tokens BIGINT`, `cost_usd_est NUMERIC`, `num_turns INT`, `duration_api_ms INT`, `terminal_reason VARCHAR(32)`, `model_served VARCHAR(64)`, `merge_gate_verdict VARCHAR(20)`, `origin_channel VARCHAR(16)`, `origin_ref VARCHAR(64)`, `deliverables JSONB`. All are already on the SDK `ResultMessage` and dropped at `session.py:1095` (`num_turns, total_cost_usd, duration_api_ms, model_usage, stop_reason, api_error_status`; state map §2.1). `origin_*` replaces the in-process `_job_to_chat` dict (`telegram_bot.py:38, 1028`) so done-DMs survive bot restarts and web launches get them too.

New tables: `provider_quota_snapshots(provider, window, used_pct, resets_at, source ∈ {sdk_event, codex_rpc, inferred}, ts)`; `eval_results(skill, case, provider, model, score, verdict, baseline, ts)` (today `evals/results/` holds only `.gitkeep`; state map §2.4); `provider_qualifications` is a tracked YAML (plan §6g), not a table.

Frontmatter (backward-compatible, plan §6e): `model:` accepts `[provider/]id`, bare ids default `anthropic/`; optional `task_class:`, `providers: {allow, deny}`, `sensitivity: public|owner|theses`; `escalation.on_failure` becomes a list of `{provider, model, effort}` with the bare-map form still accepted (31 skills untouched). `post_review.reviewer_model/effort` — documented but ignored today (`review.py:247-256`) — becomes honoured only within the Anthropic pin.

### 1c. Executors / providers (what actually runs where)

| Provider id | Kind | Auth (owner-provisioned, INV-3 unchanged) | Capabilities | Cost class | Trust |
|---|---|---|---|---|---|
| `anthropic` | `sdk-anthropic` (today's path) | Max `/login` + `CLAUDE_CODE_OAUTH_TOKEN` from `claude setup-token` in launchd env | agentic, tools, mcp, subagents, guard-hooks, structured-output | included | anchor |
| `codex` | `cli-agent` | `codex login --device-auth` on the ChatGPT account (Free per decision 2) | agentic, tools, structured-output, os-sandbox | included | probation → canary → qualified |
| `gemini-free` | `openai-compat` (`generativelanguage…/openai/`) | `GEMINI_API_KEY` unpaid | structured-output | free-tier | utility only, **public data only** |
| `openrouter-free` | `openai-compat` | `OPENROUTER_API_KEY`, `:free` models only, "allow training providers" toggle **off** | structured-output | free-tier | utility only |
| `ollama-local` | `openai-compat` `127.0.0.1:11434` | none | structured-output | free-tier | utility only, memory-guarded |

No Gemini or Grok *executor*: the Gemini subscription CLI lane is dead for unpaid/AI-Plus users (gemini-google §3; runtimes §1) and Grok is metered-only (grok-xai §7) — both out of scope under the free-tier policy.

### 1d. Routing / policy (plan §6d, amended)

| Task class | Skills (inferred from isolation + tags unless `task_class:` set) | Chain |
|---|---|---|
| `utility-classify` | `llm_router`, `learning` classifier | ollama-local → gemini-free (public prompts only) → openrouter-free → anthropic/sonnet-low |
| `chat` | `chat` | anthropic only (Sonnet low; matrix §3 "knob is effort, not model") |
| `research-read` | research-report, atlas-*-research reads that are `isolation: workspace` and declare no subagents/MCP | anthropic → codex (canary) |
| `code-project` | app-patch, atlas-build (non-server repos) | anthropic → codex (canary, R3) |
| `code-server` | server-patch, new-skill, server-deploy, deploy-director | **anthropic pinned** |
| `review-gate` | code-review subagent, `review.py` post-review, `_evaluate` | **anthropic pinned** (INV-21); Codex added as *second belt*, never the verdict of record |
| `trading-research` | atlas-*/alpha-* research, theses, validators, governors | anthropic; Codex critic stage additive (§6) |

Capability matching keeps the 20 subagent-declaring skills and the 16 `needs-dispatch-mcp` skills on Anthropic automatically (state map §2.4). Unknown provider → job fails (`SkillResolutionError` family, C12), never silent fallback.

### 1e. Containment (INV-21 as code)

- Anthropic lane: unchanged (workspace clone `workspaces.py:127-170`, PreToolUse hooks `guards.py:381-490` at `session.py:753/755`). Hardening from research: never pass `--bare` (claude-anthropic §3, §7); assert `model_usage` contains the requested model and `duration_api_ms > 0` before accepting a result (claude-anthropic §7 "unrecognised model IDs fail silently"); replace the banner regex (`session.py:495-534`) with typed `api_error_status`/`stop_reason`; remove `AskUserQuestion` from the default tool list (`session.py:706-709`; documented to hang jobs, state map §2.3).
- Codex lane (INV-21 a–c): only `isolation: workspace` skills; `codex exec --json --ephemeral --sandbox workspace-write` (network off by default; crosscut-tos §3.8a rating A−), `approval_policy=never`, `features.goals=false`, `otel.metrics_exporter="none"` (chatgpt-openai §3, §7), `web_search="cached"`, scrubbed env (no `delivery.env_files` copy — `workspaces.py:192-244` skipped for non-anthropic executors, so atlas brokerage keys never reach Codex), no MCP, no subagents, `CODEX_HOME` pointed at a server-owned dir. Diffs merge only through the Anthropic review gate; for Codex jobs `post_review.trigger` is forced to `always` and the `stale_head` skip (`review.py:199-208`) is reclassified as `flagged`, not `skipped`.
- Utility lanes: no tools, JSON out only; `sensitivity: theses` prompts may not go to `gemini-free` (trains, human-reviewed; gemini-google §3a) or `openrouter-free` (provider-dependent; runtimes §3).

### 1f. Event / audit model

Executors emit the existing kinds unchanged (`text, tool_use, tool_result, thinking, rate_limit_status, job_started, job_completed, job_failed`; C14) plus new ones: `provider_selected{provider, model, reason}`, `provider_fallback`, `quota_snapshot`, `merge_gate_verdict`, `second_belt_review{provider, verdict}`, `deliverable{path|url}`. Codex JSONL mapping: `agent_message→text`, `command_execution→tool_use{tool_name:"Bash"}`+`tool_result`, `file_change→tool_use{tool_name:"Edit"}`, `reasoning→thinking`, `turn.completed.usage→job_completed.usage`. `jobs:stream:<id>` additionally carries `tool_result`, `guard_denied`, `rate_limit_status` and a 30 s heartbeat so the live pane can render.

```
Telegram /task,/schedule ─┐                                 ┌ anthropic (Claude SDK on Max) ← pinned: code-server, review-gate, _evaluate, chat
web POST /api/jobs, CLI ──┼► enqueue_job ► jobs:queue ► _job_loop (slot, per-provider pause) ► run_session
scheduler (41 rows) ──────┤                                             │
event loop / dispatch MCP ┘                                  resolve skill → cwd → isolation → policy.select()
                                                                        │ provider_selected{reason}
                                    ┌───────────────────────────────────┼─────────────────────────────────┐
                                    ▼                                   ▼                                 ▼
                       executors/claude_sdk.py               executors/codex_cli.py             providers/completions.py
                       (_run_in_process verbatim;            (codex exec --json --ephemeral      (utility_call: ollama → gemini-free
                        hooks, MCP, subagents)                --sandbox workspace-write)          → openrouter-free → anthropic)
                                    └───────────────────────────────────┼─────────────────────────────────┘
                                                                        ▼
                                  normalized ExecEvent → audit JSONL + jobs:stream + jobs.* columns (migration 007)
                                                                        ▼
                                  final text → summary.md → markers → Task lifecycle (unchanged, main.py:1053-1266)
                                                                        ▼
                     post-steps: promote DAG → Anthropic post-review → [Codex second belt] → writeback → learning → notify(origin)
```

### 1g. Config sketches (tracked files; runtime state stays in Redis/Postgres per C20)

```yaml
# providers.yml — the one catalog (replaces telegram_bot._MODEL_ALIASES as allowlist)
- id: anthropic
  kind: sdk-anthropic
  auth: subscription
  capabilities: [agentic, tools, mcp, subagents, guard-hooks, structured-output]
  cost_class: included
  trust: anchor
  models:
    claude-opus-5-5:   {aliases: [opus, opus-5-5], context: 1000000, tier: frontier}
    claude-sonnet-5:   {aliases: [sonnet, sonnet-5], context: 1000000, tier: volume}
    claude-haiku-4-5-20251001: {aliases: [haiku], context: 200000, tier: utility, retires: 2026-10-15}
    claude-opus-4-7:   {aliases: [opus-4-7], context: 200000, tier: legacy}   # 21 skills still pin it
    claude-sonnet-4-6: {aliases: [sonnet-4-6], context: 200000, tier: legacy} # 27 skills + default_model
  concurrency: 2            # crosscut-tos §3.10b: start 2, raise on clean telemetry
- id: codex
  kind: cli-agent
  auth: oauth-device
  capabilities: [agentic, tools, structured-output, os-sandbox]
  cost_class: included
  trust: probation
  models: {gpt-6-sol: {aliases: [sol]}, gpt-6-luna: {aliases: [luna]}}
  concurrency: 1
  exec: {sandbox: workspace-write, ephemeral: true, goals: false, otel_metrics: none, web_search: cached}
- id: gemini-free
  kind: openai-compat
  base_url: https://generativelanguage.googleapis.com/v1beta/openai/
  auth: api-key            # GEMINI_API_KEY, unpaid tier
  capabilities: [structured-output]
  cost_class: free-tier
  trust: qualified-utility
  data: {trains: true, max_sensitivity: public}
  caps: {rpd: 250}
- id: openrouter-free
  kind: openai-compat
  base_url: https://openrouter.ai/api/v1
  auth: api-key
  capabilities: [structured-output]
  cost_class: free-tier
  trust: qualified-utility
  data: {trains: provider-dependent, max_sensitivity: public}
  caps: {rpm: 20, rpd: 50}
- id: ollama-local
  kind: openai-compat
  base_url: http://127.0.0.1:11434/v1
  auth: none
  capabilities: [structured-output]
  cost_class: free-tier
  trust: qualified-utility
  data: {trains: false, max_sensitivity: theses}
  guard: {min_free_gb: 3}
```

```yaml
# routing-policy.yml — task class → ranked chain; pins are data, un-pinning is a protected change
classes:
  utility-classify: {chain: [ollama-local, gemini-free, openrouter-free, anthropic/claude-sonnet-5@low], fail_open: true}
  chat:             {chain: [anthropic/claude-sonnet-5@low], pinned: true}
  research-read:    {chain: [anthropic, codex], canary_share: 0.2}
  code-project:     {chain: [anthropic, codex], canary_share: 0.1}
  code-server:      {chain: [anthropic], pinned: true}
  review-gate:      {chain: [anthropic], pinned: true, second_belt: [codex]}
  trading-research: {chain: [anthropic], pinned: true, second_belt: [codex], default_sensitivity: theses}
infer:
  - {when: {subagents: nonempty}, require_caps: [subagents]}
  - {when: {tags: [needs-dispatch-mcp, needs-projects-mcp]}, require_caps: [mcp]}
  - {when: {isolation: none}, require_caps: [guard-hooks]}     # 48 unisolated skills stay on Anthropic
```

```yaml
# provider_qualifications.yml — state of the shadow → canary → qualified ladder (proposals move rows)
- {provider: codex, skill: research-report, state: canary, since: 2026-10-20, evidence: eval_results#…}
- {provider: codex, skill: atlas-critic,    state: qualified, since: …}
```

### 1h. Executor protocol (plan §6b, made concrete)

```python
# src/runner/executors/base.py
@dataclass
class ExecSpec:            # vendor-neutral; built where _build_options is built today
    job_id: str; provider: str; model: str; effort: str | None
    cwd: Path; system_prompt: str; user_prompt: str
    capabilities: set[str]            # read/write/edit/shell/search/fetch/delegate
    guard_profile: str | None         # "workspace" | "read-only" | None
    mcp_servers: dict; subagents: dict; max_turns: int | None
    timeout_s: int; sensitivity: str

@dataclass
class ExecEvent:          # normalized; adapters map onto today's audit kinds unchanged
    kind: Literal["text","thinking","tool_use","tool_result","rate_limit","system","result"]
    payload: dict

class Executor(Protocol):
    provider_id: str
    def run(self, spec: ExecSpec) -> AsyncIterator[ExecEvent]: ...
    async def interrupt(self, job_id: str) -> bool: ...      # ≤2 s (INV-8)
    async def kill(self, job_id: str) -> None: ...            # timeout path calls this; today it does not
    def result(self) -> ExecResult                            # {final_text, usage, cost_usd_est, num_turns,
                                                              #  duration_api_ms, model_served, terminal_reason}
```

`claude_sdk.py` is `_run_in_process` + `_handle_message` moved verbatim behind this shape; the return dict `{summary, duration_seconds, usage, skill, isolation}` stored at `main.py:1284-1294` is preserved and extended, never renamed.

Codex JSONL → audit mapping (`codex exec --json`, chatgpt-openai §3):

| Codex item | Audit kind | Notes |
|---|---|---|
| `thread.started` | `job_started` (existing shape) + `session_id` | |
| `item.completed{agent_message}` | `text` | streamed to `jobs:stream` |
| `item.completed{reasoning}` | `thinking` | audit only |
| `item.started{command_execution}` / `item.completed` | `tool_use{tool_name:"Bash", input}` / `tool_result` | canonical category so `review._summarize_tool_usage` and learning's Write/Edit gate keep working |
| `item.completed{file_change}` | `tool_use{tool_name:"Edit", input:{file_path}}` + `tool_result` | triggers learning + writeback checks as today |
| `item.completed{web_search}` | `tool_use{tool_name:"WebSearch"}` | cached mode only |
| `turn.completed{usage}` | `job_completed{usage}` normalized to `{input_tokens, output_tokens, cache_read_input_tokens}` | |
| `turn.failed` / `error` | `job_failed{error, error_category}`; `429 slow_down` → `rate_limit`; `503 server_is_overloaded` → `terminal_reason=api_error` (fail over, do not retry) | |
| exit code / `-o out.json` schema | `result{structured_output}` | `--output-schema` for the second belt and `_evaluate`-style verdicts |

## 2) Interfaces & visibility

**Telegram (phone).** Existing 12 commands stay. Ghost commands become real: `/status <prefix>`, `/cancel <prefix>` (also removes queued ids via LREM + status flip — cancel cannot reach queued jobs today, state map §2.2), `/rate <id> n`. New:
- `/providers` — one card: per lane `health ● / ○ / ⏸`, `5h used % · weekly used % · resets in`, breaker state, today's utility counters vs caps (Gemini 250 RPD, OpenRouter 50/1000 RPD), last `provider_fallback`. Buttons: `pause <id>` / `resume <id>`.
- `/usage [7d|30d]` — tokens and list-price-equivalent cost by provider × skill (from the 007 columns; `total_cost_usd` is a client-side estimate, claude-anthropic §7), top-5 skills by cache_read, escalation count, second-belt disagreement rate.
- `/jobs` rows gain provider + cost; `/schedule list` gains last outcome, `run <name>`, `pause`, `resume`, `delete` (confirm), and `set-model <name> <provider/model>` writing `payload.model` (per-schedule pins already work, state map §2.4).
- Completion/failure DMs for **every** job via `origin_channel/origin_ref` (scheduled failures are silent today; state map §5 item 7). Card = summary[:3200] + deliverable links (`deliverables` column) + `review_outcome` + second-belt verdict + provider/cost line.
- Live progress on the phone: a `progress` card every N tool calls or 5 min for jobs > 10 min, editable in place (Telegram `editMessageText`), showing last tool + turn count + elapsed.
- `/clear` asks for confirmation.

Card mockups (Telegram, ≤4096 chars, ≤8 buttons):

```
/providers
● anthropic   5h 41% (resets 14:05)  · week 63% (resets Sun 09:00)  · 2 running · breaker closed
● codex       5h  8% · week 12%      · plan: free · 0 running · last used 07:12 (second belt)
○ gemini-free 137/250 today          · public-only · 3 fallbacks today
○ openrouter  12/50 today            · last error 429 @06:40 (fallback → anthropic)
● ollama      qwen3.5:4b idle · 5.1 GB free · 88 calls today · p50 1.9 s
[pause codex] [resume gemini-free] [details]

/usage 7d
tokens  anthropic 412M cache-read / 5.9M out · codex 0.4M in / 0.1M out · utility 1,204 calls ($0)
est. list-price equivalent: anthropic $186 · codex $0.31 · gemini $0.00 · total $186 (subscription: $0 marginal)
by skill (top 5): review-and-improve $41 · atlas-alpha-research $33 · atlas-build $29 · self-diagnose $18 · atlas-daily-brief $12
second belt: 23 reviews · agree 19 · dissent 4 (2 flagged) · skipped(quota) 6
escalations 3 · self-diagnose 9 (quota/auth-class skipped: 4)

✅ completed  atlas-alpha-research  (opus-5 · anthropic · 11m42s · 2 turns · ~$0.14)
Summary: … (first 3,200 chars)
Deliverables: projects/atlas/alpha-lab/ideas/A-0009/memo.md · /alpha (atlas web)
Review: LGTM (anthropic) · second belt: DISSENT (codex) — 2 flaws listed → flagged
[Reopen] [Details] [Rate] [Open DISSENT]
```

**Web (laptop).** Same inline htmx page, extended: (1) Providers strip (same data as `/providers`); (2) Cost/usage tile with 7d/30d toggles; (3) Job detail page renders the SSE stream (tool timeline, thinking count, guard denials, rate-limit events, cost so far) instead of raw JSON, with Cancel/Rate/Reopen buttons; (4) Schedules table with run-now/pause/resume and last-3 outcomes from `schedule_rollup` (`web.py:175-260`); (5) Tasks view (routes exist, no UI). New routes: `GET /api/telemetry/providers`, `GET /api/telemetry/usage`, `GET /api/jobs/{id}/events`, `POST /api/schedules/{id}/run|pause|resume`. Auth unchanged (single token; CF Access is an owner hosting decision, §11).

**CLI (laptop).** `python -m src.cli task "…" [--provider codex --model …] [--watch]`, `jobs`, `providers`, `usage` — a thin client over the REST API, giving owner terminal work a canonical `created_by="cli"` (today ad-hoc strings; state map §2.3) and `--watch` tailing `/api/jobs/{id}/stream`.

**Vendor apps.** Not integrated (§9). The only first-party complement recommended is Claude Routines for repo-scoped jobs that must run when the Mini is down (crosscut-tos §3.1); optional, R5+.

**Schedule adherence.** `schedule_adherence.py` findings (DARK/NEVER_RAN/STUCK/FAILURE_STREAK) surface in `/schedule list` and the dashboard, not only the 07:15 DM.

## 3) Effectiveness

- **Definition of done** is the existing marker contract (`TASK_COMPLETE:`/`EVAL_PASS:`; C15) plus, per skill, an optional `done_when:` list rendered into the system prompt and checked by `_evaluate` (which today is never load-bearing: 11 runs ever, 0 stored plans; state map §2.5). Incremental: keep `_evaluate` Anthropic-pinned, give it structured output via `utility_call` so the verdict is a column, not a regex.
- **Evidence**: every completion card links the deliverable (`deliverables` column filled from Write/Edit tool_use paths under `projects/**` or `docs/**`, plus the summary file); tokens/cost/turns/provider stamped on the row; `merge_gate_verdict` recorded by parsing the in-session `code-review` subagent's Task tool_result (the INV-13 gate verdict is never stored today; state map §2.5).
- **Review / grading**: reviewer of record stays `review.py` Anthropic (C5, C7). Add the *second belt*: for skills with `post_review.trigger != never` and `sensitivity != theses`-to-untrusted-lane, run `codex exec --sandbox read-only --output-schema review.json` on the same diff, store `second_belt_review{verdict}`; disagreement with Anthropic → `review_flagged` DM. This is the plan's deferred "review-gate diversity" (§7 R6+) brought forward as *additive* because the research reverses the lineage assumption (Codex/Gemini high independence, Kimi/MiniMax/DeepSeek low; crosscut-tos §5.2a) and the state map names it the highest-value non-Anthropic insertion (§2.6). Pairwise agreement is logged so independence is measured, not assumed (runtimes §3(g)).
- **Provider scoreboard**: wire `retrospective.skill_performance` (zero callers today, `retrospective.py:39-96`) with a `resolved_provider` group_by; expose as `GET /api/retrospective/performance` and a `/usage` section: success rate, review_outcome, second-belt agreement, avg duration, tokens, escalation rate per provider × skill.
- **Qualification ladder** (plan §6g): `provider_qualifications.yml` per (provider, skill): `shadow` (evals run with `--provider`, results persisted to `eval_results`) → `canary` (≤20 % of that skill's jobs, non-scheduled first) → `qualified` → auto-`demoted` when failure-rate or `changes_requested` delta exceeds threshold; promotions are `review-and-improve` proposals of the never-used `default-model` kind (0 filed; state map §2.5), owner-approved while young.
- **Ratings**: keep the button, stop rendering it on every card; replace `avg_rating` in rollups with collectible signals (eval score, review_outcome, second-belt agreement, escalation-needed).

## 4) Scheduling across vendors

- Schedules stay DB rows owned by `seed-schedules.sh` (C19); the seeder gains `payload.provider` / `payload.model` per row and a Python validator that checks slot collisions and that the row's skill can run on the requested provider (capability match) — a failed check is a lint error, not a runtime surprise.
- Scheduler (`main.py:1327-1362`): commit before RPUSH (the enqueue race the retry ladder absorbs), log `schedule_misfired` when a slot was skipped, keep "advance from now".
- Class-aware pause: a due job whose class chain has no healthy provider is requeued at the front (INV-12 semantics preserved) and the schedule row is annotated `last_blocked_reason`; pinned lanes pause on Anthropic quota exactly as today, routable lanes keep draining (plan §2 headline win).
- Quota pollers in the event loop (`events.py:463-512`, 60 s tick): Codex `account/rateLimits/read` once per 15 min via a short-lived app-server (chatgpt-openai §3); Claude from the SDK's own `rate_limit_status` events (already emitted per job); Gemini/OpenRouter from our own Redis counters vs caps. Fan-out starts at 2 Anthropic / 1 Codex (crosscut-tos §3.10b) inside the existing `MAX_CONCURRENT_JOBS=2`.
- Credential canaries as schedules: daily `codex exec "ok"` (refresh only fires during use; chatgpt-openai §3), daily `claude -p ping` with the `model_usage` assertion, `setup-token` T−30 d alarm from a recorded mint date (crosscut-tos §3.10c).
- Telegram `/schedule` gets run/pause/resume/delete/set-model (§2); adding a schedule from the phone still writes no payload — the seeder remains the source of truth for payloads.

## 5) Project delivery path

Unchanged mechanics: workspace clone → work → push → canonical ff-sync (`workspaces.py:247-270`, `session.py:1038-1043`) → gated redeploy (`atlas-redeploy`, `server-deploy`). Increments:
- Codex canary on `code-project` for non-server repos (app-patch, atlas-build) only after `research-read` canaries pass (plan §7 R3); Anthropic post-review mandatory, second belt informational.
- Deliverable capture: the `deliverables` column + project page URL derived from `projects/<slug>/.context/CONTEXT.md` web-serving section, so the completion card says *where* the thing is.
- Deploy approval: `DeployNeedsApproval` currently fails the job and asks the owner to retype (state map §5 item 11); incremental fix = park the job as `awaiting_approval` with an Approve button that re-enqueues with `payload.approved_by`.
- Two-repo atlas skill drift (15/26 staged skills differ; state map §2.6): add a lint that diffs `atlas/integrations/ai-server/skills/` against `skills/` for the atlas roster — in the owner-approved lint PR.

## 6) Trading research automation within INV-22

What "automate trading" means here: research, theses, adversarial review, evaluation, paper/shadow loops. No new order path; `atlas/swing/swing/executor.py --submit` behind `risk.validate` stays the only one (C11).

| Stage | Runs on | Vendor adds | Data / credential boundary |
|---|---|---|---|
| Research cycles, thesis composition, governor grading, quant sweeps, alpha triage | anthropic (today's 17 opus-5/sonnet skills) | — | atlas `.env` copied into workspace via `env_files` (as today) |
| **Adversarial critic** (new `atlas-critic` stage after the Anthropic validator) | codex, `isolation: workspace`, `--sandbox read-only`, no `env_files`, no MCP | independent lineage (crosscut-tos §5.2a); writes `DISSENT/CONCUR` + numbered flaws to the ledger via a file the next Anthropic stage commits | reads committed memo files only; brokerage keys never enter the Codex workspace; ChatGPT "Improve the model" **off** before any thesis passes through (chatgpt-openai §3) |
| Public-content memo review (no positions/theses) | gemini-free (utility HTTP) | cheap third vote, multimodal/filing digestion | `sensitivity: public` only; unpaid key trains (gemini-google §3a) |
| Sentiment feature (Grok `x_search`) | **not in this design** | — | metered `XAI_API_KEY` ≈ $0.25–0.75/job (grok-xai §7) → owner decision 4 |
| Data plane | Alpaca paper / EDGAR / Massive Basic / Finnhub free MCPs mounted under the Anthropic lane | — | Tradier remote MCP only with paper token and read-only `allowed_tools` (crosscut-finance §3) |

Server-side INV-22 enforcement (broker-host deny patterns in `guards.py:137-149`, open follow-up per `SYSTEM.md:130`) ships in the owner-approved guards PR. Blocking plumbing that no vendor fixes — `TRADIER_SANDBOX_TOKEN`, `FINNHUB_TOKEN`, `weekly.py:316` KeyError, Alpaca stale-data fallback (state map §2.6) — is listed as owner/atlas work, not router work. AUP posture: every vendor's finance clause is an advice-to-others/reliance clause; owner-only paper research with a human on the order path is inside the lines at all of them (crosscut-finance §6).

## 7) Vendor plan

| Vendor | Surface | Auth | Cost path | ToS status (research) | Task classes here |
|---|---|---|---|---|---|
| **Anthropic** | Claude Agent SDK (pinned `>=0.1.81,<0.2`, bundled CLI 2.1.139) | Max `/login` + `CLAUDE_CODE_OAUTH_TOKEN` (setup-token, 1 yr); `ANTHROPIC_API_KEY` banned (INV-3) | subscription; usage credits **not** enabled (no metered) | **Yes\*** — own unmodified binary/SDK on own plan ("ordinary, individual usage"); June-15 pause means `-p`/SDK still draw plan limits; `--bare` cliff and revocable policy (crosscut-tos §3.1, §3.7) | everything pinned + primary for all classes; models per registry: opus-5-5 / sonnet-5 / haiku-4-5 (retires ≥2026-10-15 → registry alias flips to sonnet-5 low) — **only after** the SDK bump proves the bundled CLI recognises them (claude-anthropic §7) |
| **OpenAI Codex** | `codex exec --json --output-schema`, app-server for `account/rateLimits/read` | `codex login --device-auth` on ChatGPT **Free** (decision 2) | included; Free = "explore" tier, message bands unpublished (matrix §2) | **Gray/Yes\*** — owner-only, owner-read output; API key is OpenAI's "recommended" path; goals off, statsig off (chatgpt-openai §3, §8) | second-belt review, research-read canary, code-project canary; classification via Luna only if a tier with published bands is bought |
| **Google Gemini** | OpenAI-compat HTTP on `gemini-3.8-flash` / `3.5-flash-lite` | unpaid `GEMINI_API_KEY` (decision 4) | free: 250 RPD Flash-only | **Yes** for the key; **trains + human review** on unpaid tier; Gemini CLI Google-login lane dead for unpaid; Antigravity OAuth from orchestrator **banned** (gemini-google §3, §3a; runtimes §3) | utility-classify (public prompts), public-memo review, bulk summarization of public text |
| **OpenRouter** | OpenAI-compat HTTP, `:free` models only | `OPENROUTER_API_KEY`, $0 balance (decision 3) | free: 20 RPM, 50 RPD (<$10 lifetime) | Allowed (API); training toggle per free/paid must be off; high churn (runtimes §3) | utility fallback middle link only; never load-bearing |
| **Ollama local** | `127.0.0.1:11434` `/v1`, `qwen3.5:4b` (3.4 GB) + `embeddinggemma` | none | $0 | Allowed (MIT) | first hop of utility-classify; memory guard (<3 GB free → skip; local-models §7); `OLLAMA_KEEP_ALIVE` short, the 14 GB of stale weights removed |
| xAI, Perplexity, Mistral, Ollama Cloud, Z.ai/Kimi/MiniMax/Qwen, Copilot, Cursor, Kiro | — | — | metered or seat | out of scope by owner policy or ToS (Alibaba/Perplexity consumer banned; Kimi/MiniMax train; Z.ai plan supported-tools-only) | none; §11 lists the two worth a decision |

Data-handling rule applied everywhere: theses/positions only to anthropic (training toggle **off**, 30-day retention) and to codex after the ChatGPT toggle is off; `gemini-free`/`openrouter-free` get `sensitivity: public` prompts only (crosscut-tos §3.8).

## 8) Migration & rollout

Kill switches (all env, all one-line): `ROUTER_PROVIDERS_ENABLED=anthropic` (whole system back to today), `quota pause <provider>` (per lane), `LLM_ROUTER_ENABLED=false` (existing), `SECOND_BELT_ENABLED=false`, `LIVE_PROGRESS_CARDS=false`.

| Phase | Scope | Entry | Exit | Keeps running |
|---|---|---|---|---|
| **R0 foundations** (1 wk) | `providers.yml` + registry + policy skeleton (anthropic-only entries); migration 007; capture the dropped `ResultMessage` fields; `origin_*` persisted; `notify.py`; ghost commands fixed; docs | none | pytest + lint green; replayed job produces identical audit sequence; `/jobs` shows provider=anthropic and cost on new rows | everything |
| **R1 utility lane** (1.5 wk) | `utility_call`; migrate `llm_router` + `learning` transports; Ollama cleanup + `qwen3.5:4b`; Gemini/OpenRouter keys added by owner; `/providers` v1 (counters) | R0 exit; owner adds two keys | routing-precision eval on `evals/` router cases ≥ Haiku baseline; a week of `provider_fallback` audits reviewed; zero `theses`-sensitivity prompts on free lanes (audit assert) | all jobs on Anthropic executor |
| **R2 executor extraction** (2 wk) | `executors/base.py`, `claude_sdk.py` (verbatim), `ExecSpec`; typed terminal reasons; `AskUserQuestion` removed from defaults; SSE payload widened; live-job pane + progress cards | R1 exit | full pytest; audit-replay identical on 5 recorded jobs; one live canary per skill class; conformance test with a fake executor | all |
| **R3 Codex lane** (2 wk) | `codex_cli.py`; device-auth; `atlas-critic` second belt (research skills) → `research-read` canary → `code-project` canary; quota poller; INV-21 containment as code; owner guards PR (vendor key deny + broker-host deny) | R2 exit; owner logs in Codex, turns training toggles off, approves guards PR | shadow evals pass; canary diffs get Anthropic LGTM at ≥ skill baseline; zero guard-equivalent violations; second-belt agreement measured on ≥30 reviews | Anthropic primary throughout |
| **R4 failover + visibility** (1.5 wk) | per-provider breakers; class-aware job loop; `/usage`; dashboard tiles; schedule controls; scheduled-failure DMs; CLI | R3 exit | simulated Anthropic pause drill: routable lanes drain, pinned lanes pause, DM fires; queued-job cancel works | all |
| **R5 tuning** (1 wk) | provider rollups in `review-and-improve`; qualification autopilot proposals; monthly cost report DM; owner lint PR (policy lint + drift lint + wire unwired checks) | R4 exit | first monthly report with real numbers; first `default-model` proposal filed | all |

Deploy path unchanged (dev → `origin/main` → `server-deploy`); every phase is a separate gated deploy; R2 and R3 each get a rollback note (kill switch + `git revert` of one merge).

Test gates added per phase (all pure/fixture-based so they run in the existing `pytest` deploy gate; live-stack checks are named as such):

| Phase | New tests |
|---|---|
| R0 | registry parses + every one of the 72 frontmatters and 31 escalation targets resolves; `VALID_MODELS` derived from registry equals today's set; migration 007 up/down; `origin_*` round-trip; `notify.py` renders each `tasks:notify` type; ghost commands registered (`telegram_bot.py:1296-1308` list assertion) |
| R1 | `utility_call` schema-validate-and-retry with a fake transport; chain walk on 429/timeout; sensitivity gate refuses `theses` on `gemini-free`/`openrouter-free`; Redis RPD counters; router precision harness (`evals/cases/*` router cases) — live |
| R2 | `ExecSpec.to_claude_options()` equals the `ClaudeAgentOptions` `_build_options` produced for 10 recorded skills (golden files); fake executor conformance (event order, terminal reason, interrupt ≤2 s, kill on timeout); audit-replay identical on 5 recorded jobs — live |
| R3 | Codex JSONL fixtures → audit kinds; env scrub asserts no `ALPACA_*`/`TRADIER_*`/`ANTHROPIC_*` in the Codex subprocess env; `env_files` skipped for non-anthropic; forced `post_review.always` + `stale_head→flagged`; second-belt schema; quota poller parses `RateLimitSnapshot` fixture |
| R4 | per-provider pause/resume; class-aware requeue keeps INV-12 front-of-queue; breaker not bypassable by a cheaper provider (C26 regression from 2026-07-30); queued-job cancel via LREM; scheduled-failure DM path without `task_id` |
| R5 | `skill_performance` grouped by provider; `default-model` proposal builder; qualification transitions; monthly report renders from fixtures |

## 9) What gets deleted / rewritten vs kept

**Kept as-is (load-bearing, state map §6):** JSONL audit + summary files; text-marker lifecycle; workspace clone/ff-sync; guard predicates; fail-closed skill resolution, tighten-only isolation, deploy gate before session; SKILL.md frontmatter contract; `enqueue_job`/`jobs:queue`/slot-before-BLPOP; out-of-band alerters and edge Worker; in-session code-review as merge gate; atlas kernel-disposes path; SDK `<0.2` + `mcp<2` pins.

**Rewritten in place (accidental complexity the plan already targets):** `_build_options` monolith → `ExecSpec` + adapter (same knobs, same vocabulary); `_MODEL_ALIASES`-as-allowlist → registry; four `query()` loops → `utility_call`; global `quota:paused_until` → per-provider; banner regex → typed terminal reason; dropped usage fields → columns; `_job_to_chat` → persisted origin; `self-diagnose` on every L2/L3 → error-class gated (quota/auth/network classes skip it; 21 % of all jobs today).

**Deleted:** nothing user-visible. Ghost command *advertisements* go (replaced by real handlers); rating buttons leave every card; `JobKind` enum retired (kind validated at enqueue against `list_all()`); the 14 GB of stale Ollama weights.

**Deliberately NOT touched (honest list of what this path leaves):** `isolation: none` default + 44-name allowlist (48/72 skills stay host-equivalent and therefore unroutable — INV-21(a) precondition deferred); no OS sandbox on the Claude lane (the untrusted Codex lane ends up better sandboxed than the trusted one; state map §2.7); no priority lanes or multi-runner (owner `/task` still queues behind daily atlas jobs); dashboard remains inline htmx behind one shared token; `healthcheck-all.sh` sprawl and the two bash-side enqueues stay; three Telegram senders collapse to two (bot + `notify.py`), scripts/Worker keep theirs; no `Task` for web launches beyond origin binding (no plan/evaluator lifecycle for web jobs); atlas two-repo copies still `cp -R` (now linted, not unified); no email/Slack/vendor-app surfaces; no metered lanes of any kind.

## 10) Risks & mitigations

| Risk | Mitigation |
|---|---|
| `--bare` becomes the `-p` default and ignores OAuth (claude-anthropic §3) | SDK pin unchanged this round; any SDK/CLI bump gated on `claude -p ping` smoke + `model_usage` assertion; setup-token stored so a locked Keychain is not a second failure |
| Anthropic re-prices or re-gates `-p`/SDK without notice (crosscut-tos §3.1 timeline) | keep monthly subscription-side consumption inside "ordinary, individual usage"; Codex lane + Routines noted as fallbacks; kill switch restores today |
| Codex Free quota is tiny/unpublished → second belt rarely runs | poller gates on `usedPercent`; skipped reviews logged `second_belt_skipped{quota}` and counted in `/usage`; owner decision 1 |
| Codex refresh token only refreshes during use; idle lane lapses (chatgpt-openai §3) | daily no-op canary schedule; auth error parks the lane, never fails a job silently |
| Free-tier churn (OpenRouter delist, Gemini quota changes) — owner accepted risk | chains terminate in Anthropic Sonnet-low (included cost); breakers turn churn into `provider_fallback` events surfaced in `/providers` |
| Gemini unpaid trains on content | `sensitivity` field + audit assertion; default sensitivity for atlas/alpha skills is `theses` |
| R2 refactor of the hot path | behavior-identical extraction, audit-replay gate on recorded jobs, fake-executor conformance test, kill switch |
| Event-mapping drift (Codex JSONL schema) | pinned CLI under brew; contract test on recorded fixtures; smoke test per bump (chatgpt-openai §7 churn) |
| Memory: Ollama + 2 SDK jobs + Codex on 16 GB (3.8 GB swap today) | memory guard before local calls; `OLLAMA_MAX_LOADED_MODELS=1`, short keep-alive; Codex fan-out 1 |
| Reviewer "independence" overstated (harness effects; runtimes §3(g)) | pairwise agreement logged; second belt informational until measured |
| Haiku 4.5 retirement ≥2026-10-15 while router/learning hardcode it | registry alias, not code; R1 moves both call sites through the registry first |
| Untrusted Telegram text into a Codex job | Telegram-originated jobs stay on the Anthropic lane (rating A with hooks); Codex only for scheduled/dispatched work on committed files |

## 11) Owner decisions required

1. **Codex tier** — stay on Free (probe-only; second belt mostly skipped) or move to Plus $20 so the second belt and canaries actually run (chatgpt-openai §7 recommends Plus). Default in this design: Free.
2. **Protected-path PR (guards.py)** — add `GEMINI_API_KEY`/`OPENROUTER_API_KEY`/`CODEX_*` to the deny list and broker-host patterns for INV-22 server-side enforcement.
3. **Protected-path PR (lint_docs.py)** — policy-file lint, atlas drift lint, wire the four unwired checks.
4. **Metered sentiment lane** — prepaid `XAI_API_KEY` for `x_search` (~$5–10/mo) as a feature column; declined by default under free-tier policy.
5. **Account hygiene (auth config)** — turn "Help improve Claude" off on the Max account; turn ChatGPT "Improve the model for everyone" off; mint `claude setup-token` into the launchd env; `codex login --device-auth`; create the Gemini/OpenRouter keys.
6. **Ollama disk/RAM** — delete `deepseek-coder-v2:16b`, `mistral`, `phi3:mini` (14 GB) and pull `qwen3.5:4b` + `embeddinggemma`.
7. **Atlas front door (LOOP.md §7)** — accept the `atlas-critic` Codex stage as an additive worker in the research loops.
8. **Dashboard behind Cloudflare Access** — hosting config change; recommended but not required by this design.
9. **Priority lane** — a one-line "owner jobs LPUSH to front" change alters INV-12 requeue ordering semantics; approve or defer.

## 11a) What the owner gets vs does not get (one table, both columns honest)

| Ask | Gets (this path, $0 incremental) | Does not get |
|---|---|---|
| Ease of use — phone | `/providers`, `/usage`, real `/status`/`/cancel`/`/rate`, schedule run/pause/resume/set-model, DMs for every job, in-place progress cards, deliverable links | Vendor apps (ChatGPT/Gemini/Grok) are not wired in; Telegram stays the single human input channel; no email/Slack |
| Ease of use — laptop | Live job pane, providers/cost tiles, schedule buttons, tasks view, `python -m src.cli` with `--watch` | No dashboard rewrite, no CF Access unless decided, no per-vendor "chat with model X" surface (chat stays Sonnet-low) |
| Visibility | provider/model/tokens/cost/turns per job in Postgres; 5h/weekly budget per lane (Claude from SDK events, Codex from RPC); utility counters vs caps; breaker state; second-belt agreement; schedule adherence on the phone | Remaining budget for Gemini/OpenRouter is inferred from our own counters; no host memory/RSS series; no per-tool latency decomposition |
| Deliverable effectiveness | Stored merge-gate verdict, second-belt review, provider scoreboard, persisted evals, qualification ladder, error-class-gated escalation, `done_when` checked by `_evaluate` | `_evaluate` stays a text-marker session; no cross-vendor *verdict of record*; ratings remain owner-driven |
| Scheduling across vendors | Per-schedule provider/model pins, class-aware pause, misfire logging, quota pollers, credential canaries | No priority lanes (owner `/task` still queues behind atlas), no catch-up of missed slots, schedules still seeded from a script |
| Project delivery | Same clone/push/ff-sync path with Codex canaries on non-server repos, deliverable capture, approval parking | 48/72 skills stay unisolated and unroutable; Claude lane still without OS sandbox; atlas two-repo copies linted, not unified |
| Trading research (INV-22) | Independent Codex critic stage, Gemini third vote on public memos, server-side broker-host deny (owner PR) | No X sentiment feed, no Perplexity `finance_search`, no paid data; the swing/value verticals stay blocked on owner-side tokens |
| Vendor resilience | Anthropic quota pause no longer freezes routable classes; kill switch to today in one env var | No lane can *replace* Anthropic for agentic work under Codex Free; a Max policy change still hurts |

## 12) Effort & cost

- **Agent time:** R0 1 + R1 1.5 + R2 2 + R3 2 + R4 1.5 + R5 1 = **9 weeks**, plus ~3 weeks absorbed across phases for the bolt-ons (live pane, cards, CLI, schedule controls, scoreboard, eval persistence) → **≈12 weeks** of session time at today's cadence (one gated deploy per phase). Owner time ≈ 1.5 days total: decisions, two protected PR reviews, four logins/keys, two probes (Codex parallelism, Ollama bench).
- **Monthly cost, this design as written:** **$0 incremental** — Max seat unchanged (already paid), Codex Free, Gemini unpaid, OpenRouter $0, Ollama local. Optional: ChatGPT Plus +$20 (decision 1); xAI prepaid +$5–10 (decision 4). Reference only: the measured scheduled load (≈100k in / 82 % cache / 2k out, 30–60 jobs/mo) would cost ≈$8–14/mo metered on Sonnet 5/Opus 5.5 (crosscut-finance §3) — excluded by INV-3, cited so the owner knows the shape of the alternative he declined.
