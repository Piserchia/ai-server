# Dynamic multi-provider model router — plan (2026-08-10)

> Owner ask: "What models could we use on this repo other than just Claude?
> I want to route different types/sources of models into this server so that
> if Anthropic raised prices I wouldn't be stuck paying or risking the
> project dying. Think Codex free/cheap tiers, GPT, etc."
>
> Status: **APPROVED 2026-08-17** — all four open decisions answered by the
> owner (§10). MISSION.md §Non-goals amended the same day. R0 may start.
> Provider keys remain owner-added by hand; sessions never write them.

## 1. Goal

Make the server **provider-plural**: every LLM call goes through a routing
layer that can select Anthropic, OpenAI (Codex), Google (Gemini), OpenRouter,
or a local model — chosen per task class by capability, trust tier, health,
and cost — with automatic failover. Anthropic stops being a single point of
failure (price, quota, or outage) while remaining the trust anchor for the
safety-critical gates.

## 2. Done =

- A skill or utility call can resolve to a non-Anthropic provider and the job
  completes end-to-end with the same audit-log/stream/summary contract.
- Anthropic quota exhaustion no longer pauses the whole queue — jobs whose
  task class has a healthy alternative provider keep flowing; only
  Anthropic-pinned classes pause.
- The one-turn utility calls (LLM router, learning classifier) run on a
  free/local tier by default, spending zero premium subscription quota.
- `jobs.resolved_provider` is populated and the retrospective can answer
  "success rate and review outcome per provider per skill" from data.
- A kill switch: `ROUTER_PROVIDERS_ENABLED=anthropic` reverts the entire
  system to today's behavior with one env var.

## 3. Why now (mission fit)

MISSION §K optimizes subscription economics; §F/§G demand self-healing. Both
are today coupled to one vendor:

- **Price risk**: a Max-plan price hike or quota reshaping has no counter.
- **Availability risk**: `quota.py` pausing the queue is a *global* stop —
  the "self-healing server" stops healing when one vendor's window is spent.
- **Waste**: Haiku utility calls (routing fallback, learning classifier) burn
  the same subscription window the real coding sessions need.

MISSION currently lists "Not cross-provider — Anthropic only" as a non-goal.
This plan proposes amending that line (owner approval required — MISSION.md
is protected path #6) to: *"Cross-provider by policy, not by default:
Anthropic remains the trust anchor for review/evaluate/server-code lanes;
other providers serve routable lanes under INV-21 containment."*

## 4. Current state (what is Anthropic-coupled)

Two call shapes exist, with very different portability:

| Shape | Sites | Coupling |
|---|---|---|
| **Agentic sessions** | `runner/session.py:run_session` (every job); in-session subagents (`runner/agents.py`); `review.run_code_review`; `_evaluate` | Deep: `ClaudeSDKClient`, PreToolUse **guard hooks (INV-17/INV-20)**, MCP servers (`dispatch`, `projects`), `AgentDefinition` subagents, text-marker protocol, typed `RateLimitEvent` quota detection |
| **One-turn utility calls** | `runner/llm_router.py` (Haiku), `runner/learning.py` (Haiku classifier) | Shallow: prompt → JSON out. Uses SDK `query()` for convenience only |

Model selection today: skill frontmatter `model:` → payload override →
`settings.default_model`; escalation frontmatter promotes one level on
failure. All of it assumes Anthropic model ids.

**The safety machinery is the real constraint, not the API shape.** Guard
hooks fire in-process inside the SDK; no other runtime honors them. Any plan
that routes *agentic* work elsewhere must replace that containment, not wish
it away (§8).

## 5. Provider landscape (researched 2026-08-10)

| Provider / runtime | Auth & cost | Agentic? | Fit |
|---|---|---|---|
| **Claude Agent SDK** (today) | Max subscription | Yes (the benchmark) | Trust anchor; keeps review/evaluate/server-code lanes |
| **OpenAI Codex CLI** | ChatGPT plan sign-in — works on **every** plan incl. Free and $8 Go; credit-based since 2026; or metered API key | Yes — `codex exec --json --output-schema`, own macOS Seatbelt sandbox (`workspace-write`), AGENTS.md | Best agentic second source. Caveat: MCP tool approvals are broken in non-interactive mode without a bypass flag → Codex lane gets **no MCP** |
| **Gemini API** | Free key: 250 req/day Flash-only; personal-account tier ~1000/day; paid Flash very cheap. CLI OAuth free tier effectively ended June 2026 | API only (CLI free lane dead) | Utility-call tier + research summarization. Treat quotas as volatile |
| **OpenRouter** | Free: ~14 `:free` models, 20 req/min, high churn (`openrouter/free` meta-router); paid credits for GPT-OSS-120B / DeepSeek etc. at commodity prices | Via API (or opencode) | Utility fallback + burst capacity under an explicit monthly cap. Never load-bearing on `:free` |
| **Local Ollama** (this M4 Mac Mini, 16 GB) | Free, private | No — 4–8B class only (qwen3:4b/8b); GPT-OSS-20B needs ~13 GB, too tight beside Postgres/Redis/runner | Utility-call tier: routing/classification. Zero marginal cost, survives *every* vendor event |
| **opencode CLI** | 75+ providers; ChatGPT sub natively; **Anthropic sub login banned** (Jan 2026 dispute); Ollama/OpenRouter fine | Yes, headless | Deferred option (R6+) for a provider-neutral agentic lane; adds a big new dependency |
| **GitHub Copilot** | $10/mo, usable as opencode backend | Via opencode | Note only; not in scope |

Sources: [Codex pricing](https://uibakery.io/blog/openai-codex-pricing) /
[rate card](https://help.openai.com/en/articles/20001106-codex-rate-card) /
[plan usage](https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan),
[codex exec non-interactive](https://developers.openai.com/codex/noninteractive),
[MCP-in-exec issue #24135](https://github.com/openai/codex/issues/24135),
[Gemini free-tier changes](https://www.tembo.io/blog/gemini-cli-pricing) /
[API limits](https://aipromptshub.co/blog/gemini-api-free-tier-rate-limits),
[OpenRouter free list](https://www.teamday.ai/blog/best-free-ai-models-openrouter-2026),
[opencode providers](https://open-code.ai/en/docs/providers).

## 6. Target architecture

```
                       ┌─ providers.yml (registry: caps, auth, cost class)
                       ├─ routing-policy.yml (task-class → ranked providers)
Job / utility call ──► src/providers/policy.py
                       │   capability filter → trust floor → health/budget
                       │   filter → ranked pick (audited provider_selected)
                       ▼
        ┌──────────────┴───────────────┬──────────────────────┐
        │ executors/claude_sdk.py      │ executors/codex_cli.py│  providers/completions.py
        │ (today's path, extracted)    │ (codex exec --json)   │  (one-turn: ollama →
        │ guard hooks, MCP, subagents  │ Seatbelt sandbox,     │   gemini-free → openrouter
        │                              │ workspace-only        │   → haiku)
        └──────────────┬───────────────┴──────────┬───────────┘
                       ▼                          ▼
              same audit-log events    normalized event mapping
              + Redis stream           (JSONL → text/tool_use/usage)
```

### 6a. Provider registry — `src/providers/registry.py` + `providers.yml`

Declarative catalog; one entry per provider:

```yaml
- id: anthropic
  kind: sdk-anthropic          # sdk-anthropic | cli-agent | openai-compat
  auth: subscription           # subscription | oauth | api-key | local
  capabilities: [agentic, tools, mcp, subagents, guard-hooks, structured-output]
  cost_class: included         # included | free-tier | metered
  trust: anchor                # anchor | qualified | probation
- id: codex
  kind: cli-agent
  auth: subscription           # ChatGPT plan sign-in
  capabilities: [agentic, tools, structured-output, os-sandbox]
  cost_class: included
  trust: probation
- id: ollama-local
  kind: openai-compat
  base_url: http://localhost:11434/v1
  capabilities: [structured-output]
  cost_class: free-tier
  trust: qualified             # utility only — no agentic capability at all
# gemini-free, openrouter … same shape
```

### 6b. Executor abstraction — `src/runner/executors/`

- `base.py` — `Executor` protocol: `run(prompt, options_ctx) → (final_text,
  usage, events)` streaming normalized events (`text`, `tool_use`,
  `tool_result`, `thinking`, `usage`, `error`) into the existing
  `audit_log.append` + Redis publish path. Cancel via `interrupt(job_id)`.
- `claude_sdk.py` — today's `_run_in_process` + `_build_options` extracted
  **behavior-identically**. The refactor gate: full pytest green + a replayed
  job produces the same audit event sequence.
- `codex_cli.py` — subprocess `codex exec --json --output-schema …` in the
  workspace clone; maps Codex JSONL items (`agent_message`, `command_execution`,
  `file_change`, `turn.completed` usage) onto the normalized events; enforces
  `--sandbox workspace-write`, network per skill flag, scrubbed env (no
  keychain, no unrelated tokens); kills the process on cancel/timeout.
- Text-marker protocol (`TASK_COMPLETE:` etc.) already lives in final text —
  executor-agnostic by design (P2 decision pays off here).

### 6c. Utility completions client — `src/providers/completions.py`

One function the shallow call sites migrate to:
`complete(prompt, system, schema, task="utility-classify") → dict | None`.
Walks the policy chain (default: `ollama-local → gemini-free →
openrouter-free → anthropic-haiku`), honoring per-provider daily counters in
Redis; every hop audited (`provider_fallback`). Never raises — same
fail-open contract `llm_route` has today. Call sites: `llm_router.py`,
`learning.py` (both keep their pure parsers; only the transport swaps).

### 6d. Routing policy — `src/providers/policy.py` + `routing-policy.yml`

`select(task_class, required_caps, sensitivity) → ranked [provider]`.

Task classes and their initial pins:

| Task class | Examples | Initial policy |
|---|---|---|
| `utility-classify` | llm_router, learning classifier | local → free tiers → haiku |
| `chat` | chat skill | anthropic (cheap model) → gemini-flash |
| `research-read` | research-report, momo-research reads | anthropic ↔ codex ↔ gemini (freely routable) |
| `code-project` | app-patch, atlas-build (non-server repos) | anthropic primary; codex canary → qualified |
| `code-server` | server-patch, new-skill, deploys | **anthropic pinned** (trust anchor) |
| `review-gate` | code-review subagent, post_review, `_evaluate` | **anthropic pinned** (the gate must not be gameable by the writer's own vendor) |

Capability matching does the load-bearing work automatically: a skill that
declares `subagents:` or `needs-dispatch-mcp`/`needs-projects-mcp` tags
requires `subagents`/`mcp` capabilities → only the Claude executor qualifies.
No special-case code; the constraint lives in data.

### 6e. Skill frontmatter (backward-compatible extension)

- `model:` accepts provider-qualified ids — `anthropic/claude-sonnet-4-6`,
  `codex/gpt-5.6-codex`. Bare ids (all current skills) default to
  `anthropic/` — zero migration.
- New optional `task_class:` (defaults inferred from isolation + tags) and
  `providers: {allow: [...], deny: [...]}` override list.
- `escalation.on_failure` generalizes to a chain that may cross providers
  (e.g. codex failure → anthropic retry), same single-level loop guard.

### 6f. Per-provider quota & health — generalize `runner/quota.py`

- Redis keys move from one global pause to `provider:{id}:paused` +
  `provider:{id}:counters:{day}` (req/day for free tiers, credit burn for
  Codex).
- Circuit breaker per provider (closed / open / half-open with probe).
- `_job_loop` consults the policy: a job only waits when **no** provider in
  its class chain is healthy. Anthropic quota exhaustion then pauses the
  pinned lanes exactly as today, while routable lanes keep running — this is
  the headline resilience win.
- Telegram `/providers` command: status card (health, today's counters,
  breaker state) + `pause <id>` / `resume <id>`.

### 6g. Ledger & qualification (evidence, not vibes)

- Migration: `jobs.resolved_provider` column (beside `resolved_model`);
  audit events `provider_selected` (with reason: policy/pin/fallback) and
  `provider_fallback`.
- `retrospective.py` rollup: per provider × skill — success rate, review
  outcomes, avg duration, est. cost class. Consumed by review-and-improve.
- Qualification ladder per (provider, skill): `shadow` (run `evals/` cases
  offline, compare vs `baseline_score`) → `canary` (route a capped share of
  low-stakes live jobs; post_review + evaluator watch) → `qualified`
  (enters the policy chain) → auto-`demoted` on regression (breaker trips on
  failure-rate delta). State lives in `provider_qualifications.yml`; changes
  are review-and-improve proposals — owner-approved while the lane is young.

## 7. Rollout phases

| Phase | Scope | Risk | Gate to pass |
|---|---|---|---|
| **R0 — foundations** | MISSION §non-goals amendment (owner), `providers.yml` + registry + policy skeleton (anthropic-only entries), `resolved_provider` migration, `ROUTER_PROVIDERS_ENABLED` kill switch, docs | None (no behavior change) | pytest + lint_docs green; owner signs MISSION diff |
| **R1 — utility lane** | `completions.py`; migrate `llm_router` + `learning` transports; install Ollama + qwen3:4b; Gemini free key + OpenRouter free as middle links; Haiku stays terminal fallback | Low (fail-open, non-agentic, parsers unchanged) | routing-precision eval ≥ Haiku baseline on `evals/` router cases; a week of `provider_fallback` audits reviewed |
| **R2 — executor extraction** | `executors/base.py` + `claude_sdk.py`; `session.py` delegates; no new providers yet | Medium (refactor of the hot path) | full pytest; replay job → identical audit event sequence; one live canary job per skill class |
| **R3 — Codex agentic lane** | `codex_cli.py`; ChatGPT account (owner picks plan — Free tier suffices for probing); qualify on `research-read`, then `code-project` canary on a non-critical project; INV-21 containment (below) | High — treat like onboarding an untrusted contractor | shadow evals pass; canary diffs get Anthropic review LGTMs at ≥ the skill's baseline rate; zero guard-equivalent violations in audit |
| **R4 — dynamic failover** | Per-provider breakers live; `_job_loop` class-aware pause; `/providers` command; `provider_selected` everywhere | Medium | simulated Anthropic quota-pause drill: routable lanes keep draining, pinned lanes pause, DM notifies |
| **R5 — continuous tuning** | Retrospective provider rollups; qualification autopilot proposals; monthly cost report to Telegram | Low | first monthly report delivered with real numbers |

Deferred (R6+, separate decision): opencode as a provider-neutral agentic
executor; paid OpenRouter burst lane; review-gate diversity experiments
(Claude reviewing GPT code is in-plan; GPT reviewing anything is not).

## 8. Safety: INV-21 (new) and friends

Non-SDK executors get **no guard hooks** — the INV-17/INV-20 enforcement
point doesn't exist for them. Proposed invariant:

> **INV-21**: A non-Anthropic executor runs ONLY (a) at `isolation:
> workspace` in a per-job clone — never `none`, never `host`, never the
> server repo; (b) under its runtime's OS sandbox (Codex Seatbelt
> `workspace-write`) with a scrubbed environment (no keychain access, no
> tokens beyond its own auth); (c) with its diffs merging exclusively
> through the Anthropic review gate (in-session for pinned lanes, INV-13
> post-review for all). `code-server`, `review-gate`, and `_evaluate` task
> classes are Anthropic-pinned; un-pinning any of them is a protected-path
> change requiring owner approval.

Also: INV-1 extends to "resolved provider"; INV-3 is **unchanged** for
Anthropic (`ANTHROPIC_API_KEY` stays banned — Anthropic work is
subscription-only; the guard-hook denylist that blocks API-key injection
stays). New keys (`GEMINI_API_KEY`, `OPENROUTER_API_KEY`, Codex's ChatGPT
login) are auth-config additions → owner adds them to `.env` by hand;
sessions never write them. The cross-provider review asymmetry is
deliberate: the writer's vendor never reviews its own lane's diffs.

## 9. Risks

- **Free-tier churn** (OpenRouter delistings, Gemini quota rugs): free tiers
  are opportunistic middle links only; every chain terminates in an
  included-cost provider (Haiku subscription or local). Breakers make churn
  a logged degradation, not an outage.
- **Codex non-interactive MCP is broken**: accepted — capability matching
  keeps MCP-needing skills on Claude. Don't work around with bypass flags.
- **Event-mapping drift** (Codex JSONL schema changes): pin the CLI version
  in bootstrap; contract test on recorded fixtures.
- **Refactor risk in R2**: mitigated by the identical-event-replay gate and
  the kill switch.
- **Quality regression from cheaper models**: the qualification ladder +
  post_review/evaluator telemetry catch it; demotion is automatic.
- **16 GB local ceiling**: qwen3:4b-class only; if utility-eval parity
  fails, the chain simply starts at gemini-free — the design doesn't depend
  on local.

## 10. Owner decisions — ANSWERED 2026-08-17

1. **MISSION amendment** — **APPROVED.** The non-goal "Not cross-provider —
   Anthropic only" is replaced by "Cross-provider by policy, not by default:
   Anthropic remains the trust anchor for review/evaluate/server-code lanes;
   other providers serve routable lanes under INV-21 containment." Applied to
   `MISSION.md` on 2026-08-17. INV-3 unchanged.
2. **ChatGPT tier for Codex** — **Start Free.** $0, probing only. Revisit after
   R3 canaries show whether Codex actually carries load. Rationale: the router
   exists to remove single-vendor cost exposure, so paying a second vendor
   before there is evidence would be the wrong shape.
3. **Metered OpenRouter budget** — **DECLINED. Free tiers only ($0).** No
   metered spend is authorised. This is a deliberate acceptance of risk #1
   (free-tier churn: delistings, quota rugs): a free-only chain can lose a link
   exactly when failover is needed.
   **Consequence to design around, not to re-litigate:** every chain must still
   terminate in an included-cost provider (Haiku subscription, or local), and
   breakers must turn a churned free tier into a *logged degradation* rather
   than a silent gap. R1's provider-health telemetry is therefore load-bearing
   rather than nice-to-have — if a free tier disappears, the ledger of record
   must say so out loud. Revisit only if telemetry shows chains terminating in
   degradation often enough to matter.
4. **Gemini key tier** — **Unpaid API key (250/day Flash).** A standalone
   revocable key, not personal-account OAuth: the utility lanes (LLM routing,
   learning classifier) fit inside 250/day, and a key keeps the credential
   surface narrower than an account.

## 11. NOT in this plan

- No fine-tuning; no self-hosted big models (hardware won't carry them).
- No provider marketplace/arbitrage beyond the fixed registry.
- No un-pinning of review/evaluate/server-code lanes.
- No opencode dependency yet (R6+ decision).
- No change to Telegram/web auth, isolation tiers, or the delivery contract.
