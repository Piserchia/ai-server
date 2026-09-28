# Cloudflare AI Gateway (plus Helicone/Portkey-class observability gateways) — research (as of 2026-09-24)

Scope note: this is a *gateway/observability layer*, not a model vendor. Sections that the template
frames around "models" (Snapshot, benchmarks) are answered for what a gateway actually offers: which
upstream models it can front, what it adds per request, and what reviewers say about the proxy
itself. The comparison set is Cloudflare AI Gateway (primary), Helicone, Portkey, with LiteLLM and
OpenRouter as the incumbents the `runtimes-aggregators` doc already evaluates.

Research method: web search budget was exhausted before this task started, so every claim below
comes from direct fetches of primary pages (vendor docs, changelogs, GitHub issues, HN Algolia API).
Reddit was not reachable from this environment (fetch blocked); community sentiment is HN-only.

---

## 1. Snapshot

**Company / product.** Cloudflare, Inc. (NYSE: NET). AI Gateway launched Sept 2023, GA May 2024 (unverified as of 2026-09-24), and
had proxied 2 billion requests by its first anniversary [32]. It is a Workers-based reverse proxy in
front of AI providers that adds analytics, logging, caching, rate limiting, retries/fallbacks [1],
and, since 2025-2026, BYOK key storage, Unified Billing (Cloudflare bills you for third-party
models), dynamic routing, spend limits, Guardrails, DLP and identity-aware analytics [5][29][30].

**"Model lineup" (models it can front).** AI Gateway has no models of its own beyond Workers AI. It
proxies 24 providers in their native formats: Workers AI, Amazon Bedrock, Anthropic, Azure OpenAI,
Baseten, Cartesia, Cerebras, Cohere, Deepgram, DeepSeek, ElevenLabs, Fal AI, Google AI Studio,
Google Vertex AI, Groq, HuggingFace, Ideogram, Mistral AI, OpenAI, OpenRouter, Parallel, Perplexity,
Replicate, xAI [4]. The unified model catalogue at `developers.cloudflare.com/ai/models` lists 229
models across Workers AI and third parties [28]. Third-party IDs seen in the catalogue include
`anthropic/claude-sonnet-4.6`, `anthropic/claude-opus-4.5` … `4.8`, `anthropic/claude-fable-5`/`5.1`,
`anthropic/claude-haiku-4.5`, `openai/gpt-5.6-sol`/`-luna`/`-terra`, `openai/gpt-5.5`, `openai/gpt-6-sol`/`-luna`/`-astra`,
`google/gemini-3.x`, `xai/grok-4.3` … `4.7` plus `xai/grok-4.20-0309-*` [28]. Context windows, modalities and knowledge cutoffs are
those of the upstream provider (see the per-vendor docs in this folder); the gateway does not change
them. Note an **ID-format conflict** across Cloudflare's own docs: the catalogue uses dotted versions
(`claude-sonnet-4.6`) [28], the compat page shows `anthropic/claude-4-5-sonnet` [6], the REST API page
shows `anthropic/claude-sonnet-4` [11], and the compat page uses the provider slug `grok/grok-4` where the
catalogue uses `xai/` [6][28]; the 2026-09-01 changelog says invoice model names are now standardized to
`provider/model` [5]; verify against the catalogue page before hard-coding.

**Release cadence.** Very active in 2026: changelog entries on 2026-02-19 (unverified as of 2026-09-24), 03-02, 03-17, 04-02,
05-21 (new REST API incl. Anthropic-compatible `/ai/v1/messages`), 06-05 (spend limits), 06-12,
08-05 (x2), 08-07 (Workers AI + AI Gateway unification), 08-19, 09-01, 09-09, 09-14 (`byok_only`) [5].
One HN commenter's arc matches this: the product "had tons of limitations ... with very few updates
months+. And then recently they basically added all the features" (shados, 2026-08-05 (unverified as of 2026-09-24)) [53].

**Positioning.** A zero-markup, mostly-free control plane at the edge: per-request logs with prompt,
response, tokens, cost and latency; provider keys held server-side; optional single-bill credits for
OpenAI/Anthropic/Google/xAI/Groq with a 5% load fee [2][9]. Competes with OpenRouter (aggregation +
5.5% fee [56]), Helicone (observability-first, OSS Rust gateway, hosted free tier 10k req/mo [41][42]),
Portkey (OSS TypeScript gateway, hosted free tier 10k logs/mo [45][46]) and LiteLLM (self-hosted
Python proxy; compromised on PyPI in March 2026 [50][51][52]).

---

## 2. Interfaces & surfaces

| Surface | Cloudflare AI Gateway | Helicone | Portkey |
|---|---|---|---|
| Consumer app (web/mobile/desktop) | None. Dashboard only (Cloudflare dash, "AI" top-level nav since 2026-02 (unverified as of 2026-09-24)) [5] | Web dashboard | Web dashboard |
| Browser / OS integration | None | None | None |
| Voice | Realtime WebSockets API proxies OpenAI, Google AI Studio, Cartesia, ElevenLabs, Fal AI and Deepgram (Workers AI) [61] | Not found | Multimodal incl. audio [47] |
| CLI / agentic coding tools | Official integration pages for Claude Code, OpenAI Codex, OpenCode [25][26]; `wrangler` for Workers | Claude Code page (marked "maintained but no longer actively developed") [44] | Claude Code integration page [48] |
| API + SDKs | REST at `api.cloudflare.com/client/v4/accounts/{id}/ai/*` [11]; provider-native paths at `gateway.ai.cloudflare.com/v1/{acct}/{gw}/{provider}` [8][27]; Workers binding (JS) [30]; Vercel AI SDK [6]. No Python SDK of its own; use the OpenAI/Anthropic SDKs with `base_url` [6][8] | OpenAI-compatible `ai-gateway.helicone.ai` + Anthropic passthrough `anthropic.helicone.ai` [43][44] | `api.portkey.ai` REST, Python/JS SDKs, `/v1/messages` passthrough [49] |
| OpenAI-compatible endpoint | Yes: `/compat/chat/completions` (since 2025-06-03) and REST `/ai/v1/chat/completions`, `/ai/v1/responses` [5][6][11] | Yes [43] | Yes [46] |
| Anthropic-compatible endpoint | Yes: REST `/ai/v1/messages` (2026-05-21) and native `/anthropic/v1/messages` [5][8][11] | Yes (passthrough) [44] | Yes `/v1/messages` [49] |
| MCP support | Client-side caveat: Claude Code disables MCP tool search by default when `ANTHROPIC_BASE_URL` is a non-first-party host (`ENABLE_TOOL_SEARCH=true` re-enables it if the gateway forwards `tool_reference` blocks) [60]. Gateway-side: not found on AI Gateway pages — searched: llms.txt index [6-index], integrations index. (MCP lives in Cloudflare Agents SDK / Cloudflare One, not the gateway) | Not found | "MCP server integration" listed as a gateway feature [47] |
| Batch API | Provider batch endpoints not documented as proxied. REST `/ai/run` supports `"background": true` + `webhookUrl` for async jobs [11] | Not found | Not found |
| Structured outputs / tool use | Passthrough of provider request bodies; DLP scans tool arguments/results [22]. Claude Code protocol requires bodies forwarded unchanged [37] | Passthrough | Passthrough |
| Computer-use / browser agent | None (proxy only) | None | None |
| Scheduled / automated tasks | None in gateway; `/ai/run` background+webhook [11]. Scheduling belongs to Workers Cron/Agents SDK | None | None |
| Memory / projects / workspaces | "Gateways" are the workspace unit: 10 per account Free, 20 Paid [3]. Metadata: 5 entries/request for attribution [3] | Sessions, prompts | Prompt templates, virtual keys |
| Messaging integrations | None | None | None |
| IDE plugins | None; Claude Code/Codex/OpenCode via env vars [25][26] | Same | Same |
| First-party alternative | **Claude apps gateway** (Anthropic, self-hosted, inside the `claude` binary v2.1.195+: `claude gateway --config gateway.yaml`): OIDC SSO sign-in, per-IdP-group model allowlists + managed settings, OTLP/HTTP telemetry fan-out (tokens, model, user, latency), per-user/per-group spend limits, upstreams Bedrock / Claude Platform on AWS / Google Cloud / Foundry / Anthropic API with failover; needs Postgres 14+. Developers "don't need a claude.ai account, an API key, or a subscription" because the org's upstream credential is used — so it is **not** a subscription-preserving path [64] | — | — |

Feature detail (Cloudflare):
- **Logging**: prompt, response, provider, timestamp, status, tokens, cost, duration, user agent; DLP
  actions when triggered [12]. `cf-aig-collect-log: false` skips logging; `cf-aig-collect-log-payload: false`
  keeps metadata but drops prompt/response bodies (2026-03-17) [5][12].
- **Caching**: exact-match hash of provider, endpoint, model, auth headers and full body; TTL 60 s to
  1 month; headers `cf-aig-cache-ttl`, `cf-aig-skip-cache`, `cf-aig-cache-key`; text and image
  responses only; cache is "volatile" (concurrent identical requests may both miss) [17].
- **Rate limiting**: per-gateway, fixed or sliding window, returns 429 [19].
- **Retries/timeouts**: `cf-aig-request-timeout`, `cf-aig-max-attempts`, `cf-aig-retry-delay`,
  `cf-aig-backoff` (2025-02-06); auto-retry on upstream failure up to 5 attempts, 100 ms-5 s delay,
  constant/linear/exponential (2026-04-02) [5].
- **Dynamic routing**: visual/JSON flow with Conditional, Percentage, Model, Rate Limit, Budget
  Limit nodes; versioned drafts with rollback; requires authenticated gateway + BYOK; only via the
  compat endpoint as `model: "dynamic/<route>"`, *not* the new REST API [18][6].
- **Spend limits** (2026-06-05): cost budgets scoped by provider, model, custom metadata and `cf.user_id`, rules configured per gateway ('gateway' as a separate scope dimension is an interpretation (unverified as of 2026-09-24)), rolling or
  fixed windows, block (429) or fall back via dynamic route; max 20 rules/gateway; eventually
  consistent [10].
- **Guardrails**: prompt/response moderation using Llama Guard 3 8B on Workers AI (adds ~500 ms per
  request; does not support streaming — on gateway endpoints the full response is buffered and returned
  non-streamed; if block mode is on and Workers AI is unavailable, requests are blocked) [62], flag or
  block, billed through Workers AI (Llama Guard 3
  at $0.484/M input, $0.030/M output) [2][15][23].
- **DLP**: scans prompts, responses, tool args/results; two predefined profiles free; flagged
  findings in `cf-aig-dlp` header; **streaming responses are fully buffered when response DLP is on** [22].
- **Custom costs**: `cf-aig-custom-cost` header with `per_token_in`, `per_token_out`,
  `per_cache_read_token`, `per_cache_write_token` [20]. Cost figures are estimates only [24].
- **Evaluations**: deprecated for new accounts [21].
- **Identity**: Cloudflare Access integration adds `cf.user_id` to logs/spend rules; User Insights
  flags anomalous sessions (2026-08-05) [5][10].

---

## 3. Headless / server automation fit

**Non-interactive use.** Entirely API-driven; nothing requires a browser after one-time dashboard
setup (create gateway, create token, optionally store BYOK keys). Since 2026-03-02 a gateway named
`default` is auto-created on first request, so even that step is optional [5].

**Auth modes.**
- Cloudflare API token with **AI Gateway: Run** permission in `cf-aig-authorization: Bearer …`
  (provider-native paths) or standard `Authorization: Bearer …` (REST API, which needs *Workers AI: Read*)
  [7][11]. Tokens are account-scoped: "The AI Gateway Read, Run, and Edit permissions cannot be
  restricted to a single gateway", so a Run token can spend any gateway's BYOK keys or credits [7].
- Provider API key passed through (`x-api-key` / `Authorization`) with the gateway token alongside [6][8].
- BYOK: keys stored in Cloudflare Secrets Store; substituted "only when the provider authorization
  header is absent"; alias via `cf-aig-byok-alias`, `default` otherwise; `byok_only: true` blocks
  fallback to Unified Billing (2026-09-14) [5][14].
- Cloudflare Access short-lived tokens via `cloudflared access login` + `apiKeyHelper` [25][26].

**Consumer subscriptions through the gateway — the decisive question for this server.**
- Claude Code's own docs describe two modes behind `ANTHROPIC_BASE_URL`: (a) with a gateway credential
  (`ANTHROPIC_AUTH_TOKEN`/`ANTHROPIC_API_KEY`/`apiKeyHelper`) "a developer's claude.ai subscription
  isn't used ... That traffic is billed per token to whoever owns the credential the gateway forwards";
  (b) with **only** `ANTHROPIC_BASE_URL` set, "a saved claude.ai login remains the active credential,
  so its usage limits and billing apply. Gateways that pass this traffic on to Anthropic must forward
  the OAuth capability in `anthropic-beta`" [35][37]. So Anthropic documents subscription-OAuth-through-
  a-gateway as a supported first-party-client pattern.
- Cloudflare's Claude Code page documents only mode (a): `ANTHROPIC_API_KEY` set to the same `<CF_AIG_TOKEN>` (Cloudflare states the value is ignored when BYOK
  or Unified Billing hold the Anthropic key) plus
  `ANTHROPIC_CUSTOM_HEADERS="cf-aig-authorization: Bearer <CF_AIG_TOKEN>"`, with BYOK or Unified
  Billing supplying the real key [25]. Whether the Anthropic provider path forwards a client
  `Authorization: Bearer <oauth>` header and the `anthropic-beta` OAuth value untouched is **not
  documented** (unverified). BYOK substitution keys off the *absence* of the provider auth header [14],
  which suggests a present OAuth bearer would be forwarded, but this must be tested.
- Terms: Anthropic in Jan-Mar 2026 forced OpenCode (a third-party harness) to remove Claude Pro/Max
  OAuth login ("per legal requests", PR 2026-03-19 confirmed; HN 625 pts, 2026-01-09 (unverified as of 2026-09-24)) [57][58]. That action targeted non-Claude-
  Code clients; the Claude Agent SDK spawns the real Claude Code binary, and Anthropic's gateway docs
  explicitly contemplate OAuth traffic via gateways [35]. Still, no Anthropic page fetched here states
  in terms that *subscription* traffic through a *third-party* gateway is permitted; treat as
  "documented behaviour, unconfirmed policy" and see `crosscut-subscription-automation-tos.md`.
- Portkey's Claude Code page claims "Includes Max plan and OAuth support" [48] but its Anthropic
  provider page mentions only API keys [49]; Helicone's Claude Code page is API-key-only [44].

**Agent SDK plumbing.** The Python Agent SDK "has no gateway-specific options; it passes environment
variables to the Claude Code process it spawns" via the `env` option [36]. So integration is purely
`ANTHROPIC_BASE_URL` (+ optional `ANTHROPIC_CUSTOM_HEADERS`) in the SDK `env` dict. Semantics differ by
SDK: Python `ClaudeAgentOptions(env=...)` merges on top of the inherited environment, while the TypeScript
SDK's `options.env` replaces it entirely (spread `process.env` to keep gateway variables) [36].

**What the gateway must not break** (Claude Code protocol) [37]:
- Endpoints: `POST /v1/messages?beta=true`, optional `/v1/messages/count_tokens`, optional
  `GET /v1/models?limit=1000` (3 s timeout, no redirects), best-effort `HEAD /api/hello`.
- Forward `anthropic-version` and `anthropic-beta` verbatim (open list; stripping the OAuth value
  gives 401; stripping `extended-cache-ttl` etc. silently disables features).
- Stall watchdog: Claude Code counts every relayed byte and aborts a stream silent for 300 s by default,
  so the gateway must forward upstream SSE `ping` events and comment lines untouched [37].
- Forward the `extended-cache-ttl` value in `anthropic-beta`: the 1-hour prompt-cache TTL is requested
  via `cache_control.ttl` plus that beta value, and stripping it silently drops to the 5-minute TTL [37].
- Forward `system` array, `cache_control` markers and unknown body fields unchanged; don't rewrite
  error bodies; stream SSE without buffering (DLP response-scanning buffers — do not enable it on the
  Claude path [22]); return `retry-after` in integer seconds and `anthropic-ratelimit-unified-*` unchanged.
- Cloudflare's Anthropic provider page does not describe the path as a byte-level passthrough; it
  documents only `x-api-key`/`anthropic-version`/`cf-aig-authorization` and warns that sending your own
  `x-api-key` alongside BYOK/Unified Billing fails the request [8]. The only documented forwarding rule
  is the BYOK page's "If you send a provider authorization header, AI Gateway forwards its value to the
  provider" [14]; whether `/v1/models` and
  `count_tokens` are proxied is not documented (unverified as of 2026-09-24) — Claude Code degrades gracefully if not.

**Rate limits / caps.** Unified Billing: 200 requests per 60 s per gateway [3]. Caching request
size 25 MB; metadata 5 entries; log 10 MB (legacy) / 256 KB (Workers Logs) [3][13]. Log storage for
accounts created after **2026-09-24** (i.e. a new account today) follows Workers Logs: 200,000 events
per day and 3-day retention on Free; 20 M/month, $0.60 per extra million, 7-day retention on Paid
[2][12][13]. Legacy accounts: 100,000 logs total Free / 10 M per gateway Paid [2][3].

**Sandboxing.** Not applicable (proxy). **JSON event output.** Logs queryable via dashboard and API;
Logpush (Paid only, 10 M/month included, +$0.05/M, 4 jobs/account, 1 MB/log) to external sinks [2][3].
**Session resume.** Stateless; resume is the client's (Claude Code) concern. **Streaming.** SSE
passthrough on native and compat paths; `stream: true` on REST [11]; caching does not apply to streams [17] (unverified as of 2026-09-24) — the caching page says only text and image responses are cached and is silent on streaming.

---

## 4. Cost

**Gateway-layer plans (Cloudflare).**
| Tier | $/mo | Includes | Caps |
|---|---|---|---|
| Workers Free | $0 | Analytics, caching, rate limiting, retries, BYOK, DLP (2 profiles), spend limits, dynamic routing [2] | 10 gateways; Workers Logs 200k events/day, 3-day retention [3][13] |
| Workers Paid | $5 min | Same + Logpush (10 M/mo, +$0.05/M) [2] | 20 gateways; Workers Logs 20 M/mo, +$0.60/M, 7-day retention [3][13][16] |
| Unified Billing | prepaid credits | Third-party models billed by Cloudflare at provider list price, "no markup" | **5% fee on credits loaded** ($100 → $105) [2][9]; 200 req/60 s/gateway [3]. Runs time-boxed promos (e.g. GPT-5.6 Sol 50% off for Unified Billing only, 2026-08-19 to 2026-09-18, now expired) [5] |
| Guardrails | usage | Llama Guard 3 via Workers AI: $0.484/M in, $0.030/M out [23] | 10,000 neurons/day free [23] |

**Comparable gateways.**
| Product | Free tier | Paid |
|---|---|---|
| Helicone hosted | Hobby: 10,000 requests, 1 GB, 7-day retention, 10 logs/min [41] | Pro $79/mo (1-month retention, 1,000 logs/min, usage overage); Team $799/mo [41]. Pass-through credits "0% markup" [43] |
| Helicone OSS gateway | Free (Rust; licence Apache-2.0 per repo body but GPL-3.0 per GitHub header (unverified as of 2026-09-24); ~631 stars; public beta) [42] | — |
| Portkey hosted | Developer: 10k logs/mo, 3-day log retention, "not suitable for production" [45] | Production $49/mo, 100k logs, +$9 per 100k [45] |
| Portkey OSS gateway | Free (TypeScript, MIT, 13.1k stars); semantic cache and advanced logging/observability hosted-only; PII redaction hosted-only (unverified as of 2026-09-24); README lists Guardrails and an MCP Gateway as open-source features [46] | — |
| OpenRouter (for reference) | 50 free-model req/day (1,000 with $10 credits) [56] | 5.5% ($0.80 min) on Stripe credit loads; 5% BYOK fee above $25k/mo [56] |
| LiteLLM proxy | Free OSS | Enterprise (not fetched) |

**Upstream API prices (list, $/1M tokens), which the gateway passes through unchanged [2][9].**
| Model | Input | Cached read | Output | Batch (in/out) | Src |
|---|---|---|---|---|---|
| claude-sonnet-5 | 2.00 | 0.20 | 10.00 | 1.00 / 5.00 | [38] |
| claude-sonnet-4.6 / 4.5 | 3.00 | 0.30 | 15.00 | 1.50 / 7.50 | [38] |
| claude-opus-4.8 / 5 | 5.00 | 0.50 | 25.00 | 2.50 / 12.50 | [38] |
| claude-opus-5.5 | 4.00 | 0.20 | 20.00 | 2.00 / 10.00 | [38] |
| claude-fable-5.1 | 10.00 | 0.25 | 50.00 | 5.00 / 25.00 | [38] |
| claude-haiku-4.5 | 1.00 | 0.10 | 5.00 | 0.50 / 2.50 | [38] |
| gpt-5.6-sol | 4.00 | 0.40 | 20.00 | 50% off | [39] |
| gpt-5.5 | 5.00 | 0.50 | 30.00 | 50% off | [39] |
| gpt-6-sol | 2.00 | 0.20 | 10.00 | 50% off | [39] |
| gpt-6-luna | 0.10 | 0.01 | 0.50 | 50% off | [39] |
| gpt-6-astra | 10.00 | 1.00 | 50.00 | 50% off | [39] |
| gpt-5.4-mini | 0.75 | 0.075 | 4.50 | 50% off | [39] |
| grok-4.7 (<200k ctx) | 2.00 | 0.50 | 6.00 | n/a | [40] |
| grok-4.3 (<200k ctx) | 1.25 | 0.20 | 2.50 | n/a | [40] |
| @cf/meta/llama-3.3-70b (Workers AI) | 0.293 | — | 2.253 | n/a | [23] |
| @cf/openai/gpt-oss-120b (Workers AI) | 0.350 | — | 0.750 | n/a | [23] |
| @cf/openai/gpt-oss-20b (Workers AI) | 0.200 | — | 0.300 | n/a | [23] |
| @cf/moonshotai/kimi-k2.6 (Workers AI) | 0.950 | — | 4.000 | n/a | [23] |
| @cf/deepseek-ai/deepseek-v4-pro-0813 (Workers AI) | 1.320 | — | 3.960 | n/a | [23] |
| @cf/zai-org/glm-5.3 (Workers AI) | 1.400 | — | 4.400 | n/a | [23] |
Workers AI bills in neurons: $0.011 per 1,000 neurons on Paid, 10,000 neurons/day free [23].
Batch endpoints are not documented as proxied by AI Gateway, so batch rates apply only if you call the
provider directly (unverified for `/ai/run background:true`, which is async but not provider-batch).
Claude 4.7+ use a tokenizer producing ~30% more tokens for the same text [38]; the job assumption
below ignores that.

**Monthly cost estimate — 10 / 100 / 1000 agent jobs, ~150k input + 15k output tokens per job.**
Assumptions: no prompt-cache hits (worst case); one job = one logical task, ~20 HTTP requests (so
1000 jobs ≈ 20k log events/month, well inside the free 200k/day [13]); gateway on Workers Free unless
noted; Unified Billing adds 5% [2]; BYOK adds 0%.

| Path | 10 jobs | 100 jobs | 1000 jobs | Notes |
|---|---|---|---|---|
| (a) Claude Max subscription, Claude Code OAuth via gateway (mode b) | $0 extra | $0 extra | $0 extra | Gateway $0; model cost stays inside the Max plan's caps (plan prices not fetched here — see `claude-anthropic.md`; unverified). Max weekly limits will bind long before 1000 jobs/month of 165k tokens (unverified as of 2026-09-24). Plan: Max from $100/mo, 5x or 20x Pro usage, weekly caps on top of 5-hour session windows; Anthropic publishes no token figures for the caps [63]. |
| (b) API BYOK, claude-sonnet-4.6 | $6.75 | $67.50 | $675 | 0.45 + 0.225 = $0.675/job [38]; gateway $0 |
| (b) API BYOK, claude-sonnet-5 | $4.50 | $45 | $450 | $0.45/job [38] |
| (b) API BYOK, claude-opus-4.8 | $11.25 | $112.50 | $1,125 | $1.125/job [38] |
| (b) Unified Billing, claude-sonnet-4.6 | $7.09 | $70.88 | $708.75 | +5% credit fee [2] |
| (b) API BYOK, gpt-5.6-sol | $9.00 | $90 | $900 | $0.90/job [39]; now 2x the price of gpt-6-sol |
| (b) API BYOK, gpt-6-sol | $4.50 | $45 | $450 | 0.30 + 0.15 = $0.45/job [39] |
| (b) API BYOK, gpt-6-luna | $0.225 | $2.25 | $22.50 | $0.0225/job [39] |
| (b) API BYOK, gpt-5.4-mini | $1.80 | $18 | $180 | $0.18/job [39] |
| (b) API BYOK, grok-4.7 | $3.90 | $39 | $390 | $0.39/job [40] |
| (b) API BYOK, grok-4.3 | $2.25 | $22.50 | $225 | $0.225/job [40] |
| Gateway overhead if Workers Paid (7-day logs, Logpush) | +$5 | +$5 | +$5 | [16] |
| Helicone hosted overhead | $0 (≤10k req) | $0 | $79 (Pro; 20k req > 10k free) | [41] |
| Portkey hosted overhead | $0 | $0 | $49 (Production; 20k logs > 10k) | [45] |

With cache hits (Claude Code's system prompt and repo context are cache-eligible; cache reads are
0.1x input [38]) real API costs are typically far lower than the no-cache rows.

---

## 5. Strengths & weaknesses per reviews

Standard LLM benchmarks (LMArena, SWE-bench, Terminal-Bench, GPQA, HLE, Artificial Analysis) do not
apply to a proxy; the relevant metrics are added latency, reliability, log fidelity and price.

**Vendor claims.** Log insertion happens "in the background, ensuring that the user experience
remains seamless"; Gateway Worker runs near the user; storage is Durable Objects (SQLite) + R2 for
bodies, sharded per account+gateway, 10 M logs per gateway [32]. No published p50/p95 overhead
figure was found for Cloudflare — searched: unification blog [30], scaling blog [32]. Helicone OSS
claims P95 <5 ms, ~64 MB RAM, ~3,000 rps [42]; Portkey claims "<1 ms latency", 122 KB footprint [46].

**Community sentiment (HN, attributed).**
- Pricing honesty: "Free? They take the same 5% fee as OpenRouter does." (yencabulator, 2026-05-31)
  [53] — accurate only for Unified Billing; BYOK routing has no fee [2].
- Cost-report accuracy: "reporting inaccurate/wrong price for flagship models such as Nano Banana 2"
  (sf_tristanb, 2026-04-17 (unverified as of 2026-09-24)) [53]; Cloudflare itself calls cost data "an estimation" [24].
- Geographic routing: "they hilariously put a node in HK so you never know when your Anthropic request
  is randomly going to fail" (maeil, 2025-01-29 (unverified as of 2026-09-24)) and "Cloudflare AI gateway has no means of choosing
  placement" (realsarm, 2025-10-02 (unverified as of 2026-09-24)) [53]. Relevance to a US-based Mac Mini is low but non-zero.
- Cache utility: "cache hit rate was near zero despite the product being mature" (idrisitanzil,
  2026-03-08 (unverified as of 2026-09-24)) [53] — expected for exact-match caching of agent traffic [17].
- Maturation: "recently they basically added all the features" (shados, 2026-08-05 (unverified as of 2026-09-24)) [53].
- LiteLLM (the incumbent recommendation): "poor code quality...slow, doesn't scale well and adds a lot
  of latency" and "worst codebase and performing Python code I've used" (smcleod, 2025-11-19 and
  2026-04-21); "OpenRouter performs much, much better than LiteLLM proxy" (blazarquasar, 2026-04-10);
  positive: "Usage and Logs feature greatly helps ... Caching functionality greatly helps" (dlojudice,
  2025-07-22) [54] (all four LiteLLM attributions (unverified as of 2026-09-24)).
- Helicone/Portkey: no substantive HN opinion threads found — searched: Algolia `helicone OR portkey`
  comments [query returned one off-topic hit].

**First-party comparison (Claude apps gateway).** Anthropic's own gateway gives per-user OTLP telemetry,
SSO and spend limits with no third-party vendor, but it is a different product class: it needs an OIDC
IdP plus Postgres, only fronts Claude upstreams billed on an org credential (Bedrock / Claude Platform on
AWS / Google Cloud / Foundry / Anthropic API), disables server-side WebSearch and the 1-hour cache TTL on
gateway sessions, and explicitly does not use a claude.ai subscription [64]. For a single-operator,
subscription-only server it solves observability only by abandoning subscription billing.

**Reliability / outage record.** The 2025-11-18 Cloudflare core outage (11:20-14:30 UTC core impact,
full resolution 17:06; Bot Management feature-file bug) took down CDN, Turnstile, Workers KV, Access
and the dashboard; the post-mortem does not list AI Gateway, but anything fronted by the core proxy
was affected [33]. The public status history (last 25 events, fetched 2026-09-24) shows no 2026
incident naming AI Gateway or Workers AI [34]. Structural point: the server *already* depends on
Cloudflare (tunnel), so adding AI Gateway adds no new vendor SPOF — but it does put model traffic on the
same failure domain as the tunnel, so a Cloudflare outage would take out both inbound and outbound.

**Notable controversies.**
- LiteLLM supply-chain compromise: on 2026-03-24 versions 1.82.7 and 1.82.8 were pushed straight to
  PyPI (never through GitHub CI) using a maintainer PyPI credential stolen via an unpinned Trivy
  install poisoned in CI; 1.82.8 shipped a `litellm_init.pth` credential stealer that ran at
  interpreter start, dumped AWS Secrets Manager/SSM, created privileged K8s pods and installed a
  systemd C2 beacon; the package was suspended on PyPI, Mandiant engaged, and releases paused pending a
  supply-chain review (unverified as of 2026-09-24) (HN 739 pts) [50][51][52][55]. This is the strongest argument for a hosted
  gateway with no Python dependency in the server's trust boundary.
- Cloudflare AI Gateway token scoping: Run tokens cannot be restricted to one gateway [7] — a leaked
  token can drain BYOK keys/credits across the account.
- Anthropic vs third-party harnesses (OpenCode forced to drop Pro/Max OAuth, 2026-01 to 03) [57][58].

**Best at:** zero-cost per-request visibility (tokens, cost, latency, user-agent, user identity) across
every provider the server might use; edge-hosted so nothing to run or patch on the Mac Mini; BYOK
secret storage; spend limits and 429-on-budget as a hard cost brake; Anthropic-format passthrough that
Claude Code officially supports [25][35].
**Weak at:** exact-match cache is near-useless for agent traffic [53][17]; cost numbers are estimates
[24]; dynamic routing is compat-endpoint-only and not on the REST API [18]; evaluations deprecated
[21]; token scoping [7]; no MCP, batch or scheduling primitives; new-account log retention is 3-7 days
[13] so long-term audit must go to Logpush (Paid) or your own Postgres.

---

## 6. Finance / trading relevance

None directly. AI Gateway has no market-data connectors, sentiment feeds or finance products; it is
transport. Indirectly relevant:
- **Auditability**: full prompt/response logs with metadata (5 keys/request, e.g. `job_id`,
  `book`, `strategy`) give Atlas's research and paper-trading loops a provider-independent audit trail,
  but only 3-7 days on Workers Logs for accounts created after 2026-09-24 [12][13]; Logpush to R2/S3
  (Paid, $5/mo) or mirroring into the server's Postgres is required for anything durable [2].
- **Budget brakes**: spend limits per model/provider/metadata with 429 or fallback [10] map directly
  onto per-loop research budgets (e.g. cap `strategy=momo` at $X/week).
- **DLP**: could flag account numbers or broker keys leaking into prompts; response-scanning buffers
  streams, so enable request-side only [22].
- **Restrictions**: none specific to finance in the fetched docs. The gateway does not change any
  provider's financial-advice policies.

---

## 7. Integration recipe for our server

**Recommendation.** Use Cloudflare AI Gateway as the *observability and key-custody plane* for all
non-Claude and API-billed traffic, and route Claude Code/Agent SDK traffic through it in "subscription
passthrough" mode **only after** an explicit test confirms OAuth headers survive. Do not adopt LiteLLM
as a control plane on the Mac Mini (Python dependency in the trust boundary; March 2026 incident
[50][51][52]; HN performance complaints [54]). Keep Helicone/Portkey as fallbacks: same env-var
pattern, but they add a second vendor and paid tiers at ~20k req/mo [41][45].

**Setup (once, dashboard or API).**
1. Create gateway `ai-server` (or rely on auto-created `default` [5]); enable Authenticated Gateway;
   create a token with *AI Gateway: Run* [7]. Create a second token with *Workers AI: Read* for the REST
   API [11]. Store both in the server's secrets, never in repo.
2. BYOK: add xAI / OpenAI / Google keys in AI Gateway → Provider Keys (Secrets Store) with alias
   `default`; set `byok_only: true` so a missing key never silently falls through to Unified Billing [5][14].
   Do **not** store an Anthropic API key (policy: subscription only).
3. Spend limits: one rule per provider (e.g. xAI $20/30d rolling, block) [10]. Rate limit: sliding
   window sized to the busiest loop [19].
4. Logging: leave payload logging on for research loops; send `cf-aig-collect-log-payload: false` from
   any job that handles broker credentials [12]. Add metadata `job_id`, `skill`, `loop` (≤5 keys) [3].

**Claude Code / Agent SDK path (subscription passthrough, mode b).**
```python
# src/runner/... — Agent SDK spawns Claude Code; pass env only, no credential var.
from claude_agent_sdk import ClaudeAgentOptions, query
opts = ClaudeAgentOptions(env={
    "ANTHROPIC_BASE_URL": f"https://gateway.ai.cloudflare.com/v1/{CF_ACCOUNT_ID}/ai-server/anthropic",
    "ANTHROPIC_CUSTOM_HEADERS": f"cf-aig-authorization: Bearer {CF_AIG_RUN_TOKEN}\ncf-aig-metadata: {{\"job_id\":\"{job_id}\"}}",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
})
```
`ANTHROPIC_CUSTOM_HEADERS` requires Claude Code v2.1.227+ and rejects any name/value containing a
character an HTTP header cannot carry (curly quotes, zero-width spaces) — the JSON in `cf-aig-metadata`
above is header-safe, but check it stays so [60]. Add `ENABLE_TOOL_SEARCH=true` only after confirming
the gateway forwards `tool_reference` blocks [60]. Python's `env` merges with the parent environment;
the TypeScript SDK's replaces it [36].
Do **not** set `ANTHROPIC_AUTH_TOKEN` or `ANTHROPIC_API_KEY`: either one replaces the claude.ai login
and bills per token to the forwarded credential [35][36]. Preflight check before rollout:
`curl -X POST "$ANTHROPIC_BASE_URL/v1/messages" -H "Authorization: Bearer <oauth-from-keychain>" -H "anthropic-beta: <value Claude Code sends>" ...` must return 200, and `claude` Status tab must show
`Login method: claude.ai` plus the gateway base URL [36]. If Cloudflare strips `Authorization` or
`anthropic-beta`, expect 401 [37] — then the honest answer is "AI Gateway cannot carry subscription
traffic" and the Claude path stays direct.

**Non-Claude models (BYOK, OpenAI-compatible) — e.g. Grok for adversarial review.**
```python
from openai import OpenAI
client = OpenAI(
    api_key=CF_AIG_RUN_TOKEN,   # stored xAI key is substituted server-side [6][14]
    base_url=f"https://gateway.ai.cloudflare.com/v1/{CF_ACCOUNT_ID}/ai-server/compat",
)
r = client.chat.completions.create(
    model="xai/grok-4.7",       # verify exact ID against developers.cloudflare.com/ai/models [28]
    messages=[{"role": "user", "content": prompt}],
    extra_headers={"cf-aig-metadata": '{"job_id":"%s"}' % job_id, "cf-aig-cache-ttl": "0"},
)
```
Or the newer REST form (streaming, `Authorization: Bearer <workers-ai-read token>`):
```bash
curl -X POST "https://api.cloudflare.com/client/v4/accounts/$CF_ACCOUNT_ID/ai/v1/chat/completions" \
  -H "Authorization: Bearer $CF_API_TOKEN" -H "cf-aig-gateway-id: ai-server" \
  -d '{"model":"xai/grok-4.7","stream":true,"messages":[{"role":"user","content":"..."}]}'   # [11]
```
Grok-through-Anthropic-shim (the `grok-xai` doc's idea): REST `/ai/v1/messages` accepts Anthropic
Messages format for any provider [11], so a Claude-Code-shaped client could target `xai/grok-*` —
but Anthropic "doesn't support routing Claude Code to non-Claude models through any gateway" [35];
use it only for our own Python callers.

**Visibility feed into the dashboard.** Poll the AI Gateway logs API per `job_id` (or Logpush → R2 on
Paid) and mirror `tokens`, `cost`, `duration`, `status` into Postgres next to the audit_log; the
dashboard then shows cross-provider spend per job without any vendor-specific parsing [2][12].

**Task-class fit.** Research (Grok/GPT/Gemini via BYOK + logs): good. Coding/agentic (Claude Code):
good *if* passthrough test passes, otherwise neutral. Code review / adversarial review (second-opinion
model through compat endpoint with spend limit): good. Chat/Telegram: neutral (adds ~one hop).
Classification/routing (Workers AI llama/gpt-oss at cents, 10k neurons/day free [23]): good. Trading
research: good for audit + budget, nothing else.

**Gotchas.**
- Account-scoped Run tokens [7]: one token per purpose, rotate on any leak, keep `byok_only` on.
- New-account logs are 3-day (Free) / 7-day (Paid) [13]; the "100k logs total" legacy figure no longer
  applies to accounts created today [2].
- Exact-match cache is useless for agent loops; set `cf-aig-skip-cache` or TTL 0 to avoid stale
  research answers [17][53].
- Response-side DLP or Guardrails buffer streams and break Claude Code's stall detection (300 s byte
  watchdog; SSE pings must pass through) [22][37][62].
- `extended-cache-ttl` must survive in `anthropic-beta` or 1-hour caching silently drops to 5 min [37].
- Dynamic routes only on `/compat`, not REST [18]; spend-limit enforcement is eventually consistent [10].
- `/compat` model IDs vs catalogue IDs disagree in docs [6][11][28]; test each ID.
- Remote Control is disabled behind a non-Anthropic base URL (v2.1.196+). Fast mode's availability check
  goes directly to `api.anthropic.com` regardless of `ANTHROPIC_BASE_URL`, but
  `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` (set in the recipe above) suppresses that check, so `/fast`
  reports unavailable. MCP tool search is disabled by default when `ANTHROPIC_BASE_URL` is a
  non-first-party host; set `ENABLE_TOOL_SEARCH=true` if the gateway forwards `tool_reference` blocks [36][60].
- Adding the gateway puts outbound model traffic on the same Cloudflare failure domain as the inbound
  tunnel [33].

---

## 8. Verdict

1. Cloudflare AI Gateway is the cheapest way to get the "visibility" requirement: per-request tokens,
   cost, latency, identity and metadata across every provider for $0 (Free) or $5/mo (Paid) [2][16].
2. It replaces LiteLLM's *observability and key-custody* role with no Python in the trust boundary,
   which matters after the March 2026 LiteLLM PyPI compromise [50][51][52].
3. It does not replace an orchestrator: no MCP, batch, scheduling or memory; dynamic routing is
   compat-only [18]; caching is ineffective for agents [17][53].
4. Subscription-preserving Claude Code passthrough is documented by Anthropic [35][37] but not by
   Cloudflare [25]; it is a one-curl test away from being either the whole win or a hard no.
5. Anthropic's Claude apps gateway is the first-party observability alternative (SSO, OTLP, per-user
   spend limits) but runs on an org upstream credential, not a subscription, so it fails this server's
   subscription-only constraint [64].
6. Helicone/Portkey are viable substitutes with identical env-var wiring but cost $49-$79/mo past
   ~10-20k requests [41][45]; OpenRouter overlaps only for aggregation and charges 5.5% [56].

Fit scores (1-10): research **7** · coding/agentic **6** (8 if OAuth passthrough verified, 3 if not) ·
cost efficiency **9** · automation friendliness **8** · trading research **5**.

---

## 9. Sources

All accessed 2026-09-24.

1. https://developers.cloudflare.com/ai-gateway/
2. https://developers.cloudflare.com/ai-gateway/reference/pricing/
3. https://developers.cloudflare.com/ai-gateway/reference/limits/
4. https://developers.cloudflare.com/ai-gateway/usage/providers/
5. https://developers.cloudflare.com/ai-gateway/changelog/
6. https://developers.cloudflare.com/ai-gateway/usage/chat-completion/ (and index https://developers.cloudflare.com/ai-gateway/llms.txt)
7. https://developers.cloudflare.com/ai-gateway/configuration/authentication/
8. https://developers.cloudflare.com/ai-gateway/usage/providers/anthropic/
9. https://developers.cloudflare.com/ai-gateway/features/unified-billing/
10. https://developers.cloudflare.com/ai-gateway/features/spend-limits/
11. https://developers.cloudflare.com/ai-gateway/usage/rest-api/
12. https://developers.cloudflare.com/ai-gateway/observability/logging/
13. https://developers.cloudflare.com/workers/observability/logs/workers-logs/
14. https://developers.cloudflare.com/ai-gateway/configuration/bring-your-own-keys/
15. https://developers.cloudflare.com/ai-gateway/features/guardrails/
16. https://developers.cloudflare.com/workers/platform/pricing/
17. https://developers.cloudflare.com/ai-gateway/features/caching/
18. https://developers.cloudflare.com/ai-gateway/features/dynamic-routing/
19. https://developers.cloudflare.com/ai-gateway/features/rate-limiting/
20. https://developers.cloudflare.com/ai-gateway/configuration/custom-costs/
21. https://developers.cloudflare.com/ai-gateway/evaluations/
22. https://developers.cloudflare.com/ai-gateway/features/dlp/
23. https://developers.cloudflare.com/workers-ai/platform/pricing/
24. https://developers.cloudflare.com/ai-gateway/observability/costs/
25. https://developers.cloudflare.com/ai-gateway/integrations/coding-agents/claude-code/
26. https://developers.cloudflare.com/ai-gateway/integrations/coding-agents/opencode/
27. https://developers.cloudflare.com/ai-gateway/usage/providers/openai/
28. https://developers.cloudflare.com/ai/models/
29. https://blog.cloudflare.com/ai-gateway-aug-2025-refresh/
30. https://blog.cloudflare.com/workers-ai-gateway-unification/
31. https://blog.cloudflare.com/ai-platform/
32. https://blog.cloudflare.com/billions-and-billions-of-logs-scaling-ai-gateway-with-the-cloudflare/
33. https://blog.cloudflare.com/18-november-2025-outage/
34. https://www.cloudflarestatus.com/history
35. https://code.claude.com/docs/en/llm-gateway
36. https://code.claude.com/docs/en/llm-gateway-connect
37. https://code.claude.com/docs/en/llm-gateway-protocol
38. https://platform.claude.com/docs/en/about-claude/pricing
39. https://developers.openai.com/api/docs/pricing
40. https://docs.x.ai/docs/models
41. https://www.helicone.ai/pricing
42. https://github.com/Helicone/ai-gateway
43. https://docs.helicone.ai/gateway/overview
44. https://docs.helicone.ai/integrations/anthropic/claude-code
45. https://portkey.ai/pricing
46. https://github.com/Portkey-AI/gateway
47. https://portkey.ai/docs/product/ai-gateway
48. https://portkey.ai/docs/integrations/libraries/claude-code
49. https://portkey.ai/docs/integrations/llms/anthropic
50. https://github.com/BerriAI/litellm/issues/24512
51. https://github.com/BerriAI/litellm/issues/24518
52. https://safedep.io/malicious-litellm-1-82-8-analysis/
53. https://hn.algolia.com/api/v1/search?query=%22ai%20gateway%22%20cloudflare&tags=comment (comment ids 48346648, 47806253, 42862073, 45448347, 49184749, 47301851)
54. https://hn.algolia.com/api/v1/search?query=litellm%20proxy&tags=comment (comment ids 45986731, 45984097, 47714710, 47854697, 44745596, 44651209)
55. https://hn.algolia.com/api/v1/search?query=litellm%20malicious&tags=story (story 47501729, 739 points, 2026-03-24)
56. https://openrouter.ai/docs/faq
57. https://github.com/anomalyco/opencode/pull/18186
58. https://hn.algolia.com/api/v1/search?query=anthropic%20opencode%20subscription&tags=story (story 46549823, 625 points, 2026-01-09)
59. https://hn.algolia.com/api/v1/search?query=cloudflare%20ai%20gateway&tags=story
60. https://code.claude.com/docs/en/env-vars
61. https://developers.cloudflare.com/ai-gateway/websockets-api/realtime-api/
62. https://developers.cloudflare.com/ai-gateway/features/guardrails/usage-considerations/
63. https://claude.com/pricing
64. https://code.claude.com/docs/en/claude-apps-gateway

---

## Verification log (2026-09-24)

**Corrections applied: 9** — 3 major (Anthropic path is not documented as byte-level passthrough;
gpt-6 family added to the price table; fast-mode/Remote-Control/tool-search gotcha rewritten) and
6 minor (`ANTHROPIC_API_KEY` = gateway token, not placeholder; catalogue count 226 → 229; xAI IDs
through grok-4.7 + grok-4.20-0309-*; ID-format note extended with `grok/` slug and 2026-09-01 invoice
standardization; Realtime WebSockets provider list; Guardrails model/latency/streaming/fail-closed detail).

**Claims re-verified today (source):**
- Claude apps gateway: v2.1.195+, `claude gateway --config gateway.yaml`, OIDC-only, Postgres 14+, OTLP/HTTP
  telemetry, per-user/per-group spend limits, upstreams Bedrock / Claude Platform on AWS / Google Cloud /
  Foundry / Anthropic API, "don't need a claude.ai account, an API key, or a subscription" — code.claude.com/docs/en/claude-apps-gateway [64].
- `ANTHROPIC_CUSTOM_HEADERS` v2.1.227+ and header-safe-character rule; `ENABLE_TOOL_SEARCH` default-off behind
  non-first-party `ANTHROPIC_BASE_URL`; Remote Control disabled as of v2.1.196 — code.claude.com/docs/en/env-vars [60].
- 300 s byte watchdog, SSE `ping` forwarding, `extended-cache-ttl` beta forwarding, `anthropic-beta` OAuth
  value → 401 if stripped — code.claude.com/docs/en/llm-gateway-protocol [37].
- Python `env` merges / TypeScript `env` replaces; fast-mode check goes to `api.anthropic.com` and is
  suppressed by `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` — code.claude.com/docs/en/llm-gateway-connect [36].
- gpt-6-sol $2/$0.20/$10, gpt-6-luna $0.10/$0.01/$0.50, gpt-6-astra $10/$1/$50, gpt-5.6-sol $4/$20, batch 50% —
  developers.openai.com/api/docs/pricing [39].
- Catalogue 229 models; `openai/gpt-6-{sol,luna,astra}`; `xai/grok-4.3…4.7`, `grok-4.20-0309-*` —
  developers.cloudflare.com/ai/models [28].
- Workers AI $0.011 / 1,000 neurons Paid, 10,000/day free; kimi-k2.6 $0.95/$4.00, deepseek-v4-pro-0813
  $1.32/$3.96, glm-5.3 $1.40/$4.40, gpt-oss-20b $0.20/$0.30, gpt-oss-120b $0.35/$0.75, llama-guard-3-8b
  $0.484/$0.030 — developers.cloudflare.com/workers-ai/platform/pricing [23].
- Realtime WebSockets providers: OpenAI, Google AI Studio, Cartesia, ElevenLabs, Fal AI, Deepgram [61].
- Guardrails: Llama Guard 3 8B (+ prompt-guard-2-86m), ~500 ms, no streaming on gateway endpoints, block
  mode fails closed when Workers AI is unreachable [62].
- Anthropic provider page: only `x-api-key`/`anthropic-version`/`cf-aig-authorization`; own `x-api-key`
  with BYOK/Unified Billing fails the request [8].
- Changelog: 2026-08-19 GPT-5.6 Sol 50% off (Unified Billing only, ended 2026-09-18); 2026-09-01 invoice
  model names standardized to `provider/model`; 09-09, 09-14 present; nothing newer than 2026-09-14 [5].
- Claude Max: "From $100 / month", "5x or 20x more usage than Pro", "paid plans add weekly limits on top";
  no token figures for weekly caps published — claude.com/pricing [63].

**Stale / unverified flags left in place (marked inline):** 2026-02-19 changelog entry and "AI nav since
2026-02"; "GA May 2024"; "caching does not apply to streams"; Helicone OSS licence (Apache-2.0 vs GPL-3.0);
LiteLLM "releases paused pending a supply-chain review"; Portkey PII redaction hosted-only; spend-limit
'gateway' scope dimension; HN attributions other than yencabulator (2026-05-31) and the litellm story
(739 pts); OpenCode HN story 625 pts / 2026-01-09; whether `/v1/models` and `count_tokens` are proxied on
the Anthropic path; Max 20x plan price and weekly-limit figures.

**Fact-checker overall quality rating: good.**
