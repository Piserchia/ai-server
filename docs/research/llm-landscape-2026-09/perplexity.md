# Perplexity — research (as of 2026-09-24)

Scope: Perplexity AI as a candidate research backend / auxiliary model provider for a
single-tenant assistant server (Mac Mini M4, Python 3.12, Claude Agent SDK on Claude Max,
Postgres/Redis, Telegram + web dashboard, launchd). Owner preference: subscriptions over
metered billing, free tiers welcome, headless/CLI automation.

Bracketed numbers cite Section 9. "(unverified)" marks numbers seen only in secondary
sources or where primary pages returned 403.

## 1. Snapshot

**Company.** Perplexity AI, San Francisco; "answer engine" founded 2022. Positioning in
2026: a *front-end and orchestration layer over other vendors' models* (search-grounded
chat, Deep Research, the Comet browser, and the "Computer" multi-model agent), plus a
developer platform (Agent API, Search API, Router API, Embeddings). Its own models are the
Sonar family; everything frontier-grade is resold OpenAI/Anthropic/Google/xAI/Moonshot/
Z.AI/NVIDIA capacity [2][27]. It is in active copyright/scraping litigation with Dow Jones, Yomiuri/Asahi/Nikkei
(Aug 2025), Reddit (Oct 2025), NYT, Chicago Tribune and CNN, and Cloudflare publicly accused
it of "stealth crawling" in 2025 [66][67][75].

**Current developer model lineup (exact IDs, Agent API `POST /v1/agent`)** [2][27]:

| Model ID | Provider | $/1M in | $/1M out | Cache read | Notes |
|---|---|---|---|---|---|
| `perplexity/sonar` | Perplexity | $0.25 | $2.50 | $0.0625 | Search-native; the only Sonar that survives the Sonar sunset |
| `anthropic/claude-opus-5-5` | Anthropic | $4 | $20 | $0.20 | Newest Opus (added Sep 2026) |
| `anthropic/claude-opus-5` / `-opus-4-8` / `-4-7` / `-4-6` / `-4-5` | Anthropic | $5 | $25 | $0.50 | |
| `anthropic/claude-sonnet-5` | Anthropic | $2 | $10 | $0.20 | |
| `anthropic/claude-sonnet-4-6` / `-4-5` | Anthropic | $3 | $15 | $0.30 | previous-gen Sonnet, still listed |
| `anthropic/claude-haiku-4-5` | Anthropic | $1 | $5 | $0.10 | |
| `anthropic/claude-fable-5-1` / `-fable-5` | Anthropic | $10 | $50 | $0.25 / $1.00 | "experimental" |
| `openai/gpt-6-sol` | OpenAI | $2–4 | $10–15 | $0.20 | tiered above 272k input |
| `openai/gpt-6-luna` | OpenAI | $0.10–0.20 | $0.50–0.75 | $0.01 | powers the `fast` preset (2x "priority" price) |
| `openai/gpt-5.6-sol` | OpenAI | $5–10 | $30–45 | $0.50 | powers `high`/`xhigh`/`wide-research` |
| `openai/gpt-5.6-luna` | OpenAI | $0.20–0.40 | $1.20–1.80 | $0.02 | powers `low`/`medium` |
| `openai/gpt-5.6-terra`, `gpt-5.5`, `gpt-5.4`, `gpt-5.4-mini`, `gpt-5.4-nano`, `gpt-5.2`, `gpt-5.1`, `gpt-5`, `gpt-5-mini` | OpenAI | $0.20–10 | $1.25–45 | | see [2] |
| `google/gemini-3.1-pro-preview` | Google | $2–4 | $12–18 | 90% off | tiered above 200k |
| `google/gemini-3.8-flash` / `3.7-flash` | Google | $0.75 | $3.75 | $0.075 | 3.8 promo price through 2026-12-31 |
| `google/gemini-3.5-flash`, `3.5-flash-lite`, `3.6-flash`, `3.1-flash-lite`, `3-flash-preview` | Google | $0.25–1.50 | $1.50–9 | | |
| `xai/grok-4.7` / `4.6` / `4.5` | xAI | $2–4 | $6–12 | $0.30–1.00 | tiered at 199,999 |
| `xai/grok-4.3`, `grok-4.20-reasoning`, `-non-reasoning`, `-multi-agent` | xAI | $1.25–2.50 | $2.50–5 | $0.20 | |
| `perplexity/kimi-k3` | Moonshot | $3 | $15 | $0.30 | |
| `perplexity/kimi-k2.7-code` | Moonshot | $0.95 | $4 | $0.19 | code-specialised |
| `perplexity/glm-5.3` / `glm-5.3-flash` | Z.AI | $1.40 / $0.15 | $4.40 / $0.50 | $0.26 / $0.03 | |
| `perplexity/nemotron-3-ultra-550b-a55b` | NVIDIA | $0.25 | $2.50 | $0.25 | added Aug 2026 |
| `nvidia/nemotron-3-super-120b-a12b` | NVIDIA | see [2] | see [2] | | added Jun 2026 (Agent + Router API) [27]; price not captured this session |

**Legacy Sonar chat-completions models** (`sonar` 128K ctx, `sonar-pro` 200K, `sonar-reasoning-pro`
128K, `sonar-deep-research` 128K) are "supported until September 27, 2026" — i.e. three days
after this document [6][23][24][25][26]. The non-pro `sonar-reasoning` was already deprecated
and removed on 2025-12-15 [27]. Perplexity's official migration mapping is `sonar` → preset
`fast`, `sonar-pro` → `low`, `sonar-reasoning-pro` → `medium`, `sonar-deep-research` → `high`
(with `xhigh` recommended for "state-of-the-art deep research") [6]. Third-party gateways
report `sonar-pro` and `sonar-reasoning-pro` become non-routable at the sunset, with no
same-named IDs on the Agent API; only `perplexity/sonar` carries over unchanged on
`/v1/chat/completions` [70]. **Cutover date resolved (2026-09-24):** Perplexity's migration page,
re-fetched today, says "Sonar will be supported until September 27, 2026" [6]; llmgateway.io's
"September 25" is *its own* gateway routing schedule for moving `perplexity/sonar` onto the Agent
API two days early — the post cites no Perplexity source and itself states Perplexity retires
Sonar on the 27th [70]. Plan for **2026-09-27** direct, **2026-09-25** if you route through
that gateway.

**Context windows / modalities / cutoffs.** Perplexity does not publish context windows for
third-party models on the Agent API; the tiered-pricing thresholds (272k for OpenAI, 200k for
Gemini 3.1 Pro, 199,999 for Grok) imply windows at least that large [2]. Presets cap output
at 8,192 tokens (`fast`) to 128,000 (`medium` and above) [5]. Image attachments are supported
on the Agent API [3] (unverified as of 2026-09-24 — not confirmed on the cited overview page);
text-only for Sonar reasoning with structured outputs [25]. **Knowledge
cutoffs: Not found — searched:** "Perplexity Sonar knowledge cutoff", "Sonar 2 base model";
Perplexity's position is that search grounding makes cutoffs moot [72]. Sonar (Jan 2025) was
Llama-3.3-70B-based; the base of the consumer-side "Sonar 2" is not disclosed (unverified) [72].

**Consumer model picker (Sept 2026, unverified, secondary).** Pro and Max: Sonar 2, GPT-5.6
Terra, Gemini 3.7 Flash, Claude Sonnet 5, Kimi K3, GLM 5.3, Grok 4.6, Nemotron 3 Ultra; Max
adds GPT-5.6 Sol and Claude Opus 5 [48][72]; Perplexity's 2026-09-21 changelog adds GPT-6
Astra for Computer tasks (plan tier not stated) plus an Effort-level selector and Skills
marketplace [74]. Deep Research for Max and Pro was moved to Claude Opus 4.5 (Feb 6, 2026
changelog: "runs on Opus 4.5 for Max and Pro users") [54][36][38].

**Release cadence.** Very fast: the developer changelog shows new third-party models roughly
monthly (Jun: Claude Sonnet 5, Kimi K2.7 Code, Nemotron 3 Super; Jul: Router API, remote MCP;
Aug: GLM 5.3, Grok 4.6, Nemotron 3 Ultra, preset prompt-caching (Agent API GA was announced in
Perplexity's Feb 2026 changelog; the Jul 2026 entry reads "Sonar Chat Completions is now Agent
API" — the 2026-08-13 'launch' date comes only from a third-party blog [71]); Sep: GPT-6
Sol/Luna, Claude Opus 5.5, Grok 4.7, custom MCP connectors, MCP OAuth) [27][71]. Consumer side
(dates from the consumer changelog [74] unless noted): Computer (Feb 2026; the 2026-02-25
day-level date is unverified as of 2026-09-24 — Wikipedia confirms only "February 2026" [75]),
Personal Computer for Mac (announcement date 2026-03-11 unverified as of 2026-09-24; shipping
2026-04-16 [43]), Comet free for everyone (Oct 2025; 2026-03-18 is the iOS release date [76]),
Computer in Microsoft 365 apps (2026-05-28), Brain memory (2026-06-18 preview) and custom
Computer credit limits for Enterprise (2026-06-18), Personal Computer for Windows (2026-08-04),
Computer from email + subagent automations (2026-08-24), Portable Computer on DGX Spark
(2026-08-25), and Hybrid compute on Mac, GPT-6 Astra, Effort-level selector, Skills marketplace
and Side Chat (2026-09-21) [43][45][46][53][74].

## 2. Interfaces & surfaces

| Surface | Status (2026-09) | Source |
|---|---|---|
| Web app (perplexity.ai), iOS, Android, macOS, Windows apps | Yes; Free/Pro/Max tiers | [34][40] |
| **Comet** browser (Chromium; macOS, Windows, iOS, Android) | Free since Oct 2025 (iOS app since 2026-03-18) [76]; sidebar assistant, cross-tab, autonomous "Browser Agent" actions need Pro/Max | [69] |
| **Computer** (cloud multi-model agent, "19 models", sub-agents, connectors) | Pro (bonus credits only) and Max (10,000 credits/mo); Enterprise. Also reachable inside Microsoft 365 apps (Word/Excel/PowerPoint/Outlook/Teams, since 2026-05-28) and by emailing `computer@perplexity.com` (since 2026-08-24, which also added subagents + automations on GPT-5.6 Terra/Luna). 2026-09-21 added an Effort-level selector, a Skills marketplace of reusable skills, Side Chat and GPT-6 Astra [48][74] | [34][35][47][48][74] |
| **Personal Computer for Mac / Windows** (Mac shipped 2026-04-16; Personal Computer for Windows shipped 2026-08-04 per Perplexity's changelog; agent on your own machine, file/app access, Comet integration, iPhone remote trigger, kill switch; 2026-09-21 added Hybrid compute on Mac mixing local and cloud models) | **Pro and Max** (secondary sources, consistent): Max-only at the 2026-04-16 Mac launch [43]; "every Mac user on May 10" [48] (AppleInsider lists Pro/Max/Enterprise on 2026-05-02 [44]); Windows "for Pro and Max on August 4" [48]. AppleInsider (2026-05-02) states outright: "Personal Computer functionality is available to all Perplexity Pro, Max, and Enterprise subscribers using a Mac" and MacRumors (2026-04-16) confirms the launch was Max-only ("not available to $20/month Pro plan subscribers"; macOS 14 Sonoma+) [43][44]. Perplexity's own pricing/help/computer pages still 403 (re-tried 2026-09-24 direct, via text proxy; web.archive.org unreachable from this box), so the tier line is triangulated from three consistent secondary sources, not primary | [43][44][48][74] |
| **Hybrid compute on Mac** (Computer delegates lighter subtasks to models downloaded to the Mac; cloud handles orchestration/heavy reasoning; local work does not consume credits) | Shipped 2026-09-21 per changelog [74]. TestingCatalog's 2026-08-31 pre-release look describes three local options (a ~19 GB Perplexity model and Qwen 32B needing 32 GB RAM, a ~5.6 GB Gemma-based model for 16 GB Macs) and a "Privacy Gate" local model that screens data for PII before anything goes to the cloud [73]; which of those pieces shipped, and the tier gating, are unverified as of 2026-09-24 | [73][74] |
| **Portable Computer** (fully local runtime, Qwen 3.8 27B / PPLX 27B) | Linux + NVIDIA DGX Spark / RTX ≥24 GB at launch; **macOS unsupported**; "Linux only" is unverified as of 2026-09-24 — Vellum (Aug 2026) says Windows was targeted for September 2026 and may have shipped [46] | [45][46] |
| Voice | Voice mode in apps and Comet; Personal Computer accepts voice | [43][69] |
| CLI / agentic coding tool | **None official** (unverified as of 2026-09-24 — the Agent API docs mention none, but no negative search was possible). No `perplexity` CLI; the Agent API `sandbox` tool runs Python/bash server-side in Perplexity's container | [11] |
| API + official SDKs | Python `pip install perplexityai` (3.8+, sync+async), TypeScript `npm install @perplexity-ai/perplexity_ai` | [31] |
| OpenAI-compatible endpoint | Yes: `base_url="https://api.perplexity.ai/v1"`, `client.responses.create()` → `/v1/responses` alias of `/v1/agent`. Chat Completions shape survives only for `perplexity/sonar` through gateways | [19][70] |
| Anthropic-compatible endpoint | Router API (private preview) exposes "Chat Completions and Messages" endpoints for kimi-k3, glm-5.3, glm-5.3-flash, nemotron-3-ultra | [22] |
| MCP | (a) Official MCP *server* `@perplexity-ai/mcp-server`, remote `https://api.perplexity.ai/mcp` (Streamable HTTP; OAuth 2.1 since Sep 2026 — the sign-in is against an **API organization**, not the consumer account: you must be an admin of "an API organization that can pay for usage", pick which org to bill, and calls are "billed at standard API pricing … to the organization you chose when signing in"; the connection "cannot create API keys, view balances, or manage the organization" [78]), tools `perplexity_search` (Search API), `perplexity_ask` (`fast`), `perplexity_reason` (`medium`), `perplexity_research` (`high`); (b) Agent API can *call* remote MCP servers (`type:"mcp"`, `server_url`, `authorization`, `allowed_tools`, `defer_loading`), free per call; **`require_approval` is ignored — "every MCP tool call auto-runs"** [12] | [12][27][33] |
| Batch API | No discounted batch. `background=true` runs async server-side; poll `GET /v1/agent/{id}` (`queued`/`in_progress`/`completed`/`failed`/`cancelled`/`incomplete`). No webhooks documented | [17] |
| Structured outputs | `response_format={"type":"json_schema","json_schema":{"name","schema"}}`; all Agent API models; first call with a new schema adds 10–30 s; reasoning models leave `<think>` blocks you must strip | [15][25] |
| Tool use | Built-ins: `web_search` ($2.50/1K), `fetch_url` ($0.50/1K), `finance_search` ($5/1K), `people_search` ($5/1K), `sandbox` ($0.03/session ≤20 min); custom function tools; managed connectors (GitHub, Slack, Google Drive, Datadog, Linear, Notion); Skills (built-in office/pdf etc., inline, or uploaded ZIP with `SKILL.md`, ≤16 per request) | [1][10][11][13][14] |
| Computer-use / browser agent | Comet Browser Agent (consumer), Computer/Personal Computer (consumer). **Not exposed via API** — the only Computer API is read-only analytics | [32] |
| Scheduled / automated tasks | Consumer: "Scheduled Tasks in Computer" replaced the 2025 Tasks feature (Pro/Max; older Tasks launched Jun 2025 for Pro/Enterprise with no disclosed per-user limit per [49]; a 10-task cap circulated on X [52] (unverified)); since 2026-08-24 Computer also runs "subagents and automations" and can be triggered by email [74]; WhatsApp bot supports natural-language scheduling; Telegram bot @askplexbot exists (18.8k monthly users) but no scheduling documented | [48][49][50][51][52] |
| Memory | Brain (self-improving work memory for Computer) — Max/Enterprise Max research preview since 2026-06-18; legacy per-account memory in Search | [53] |
| Projects / workspaces | Consumer "Spaces"; API "Projects" (billing + keys + connectors per project) | [29][48] |
| Messaging | WhatsApp bot (scheduling since mid-2025; Meta's Jan-2026 ban on general assistants over the Business API makes its status uncertain — unverified), Telegram @askplexbot, Slack via Computer for Enterprise; **no Discord** found | [50][51][52] |
| IDE plugins | None first-party; reached via MCP in Claude Code / Cursor / VS Code / Codex | [33] |

## 3. Headless / server automation fit

- **Auth modes.** API: Bearer API key (`PERPLEXITY_API_KEY`) from the API Portal
  (`console.perplexity.ai`), prepaid credits with optional auto top-up; keys are *blocked*
  when the balance hits zero [29][30]. There is no OAuth device login, and the consumer
  subscription does **not** grant API access ("API access: separate billing" on every plan)
  [34]. A widely-cited "$5/month API credit for Pro" is reported *removed* without announcement
  [39]; the API FAQ no longer mentions it [30] — treat as gone (conflicting secondary sources).
  **Remote-MCP OAuth does not open a subscription path either** (checked 2026-09-24): the OAuth
  sign-in on `https://api.perplexity.ai/mcp` authenticates an *API organization* from the API
  Portal, requires you to be an admin of an org "that can pay for usage", and bills tool calls
  "at standard API pricing" to that org; an account with no API org is told to create one in the
  console first [78]. So a Pro/Max subscription cannot feed the server through MCP OAuth — the
  only difference from a Bearer key is that the token is user-scoped and cannot view balances
  or mint keys [78]. For a headless launchd job the Bearer key remains the right mode.
- **Consumer subscription used programmatically: prohibited.** Perplexity's consumer Terms
  ban "any robot, spider, crawlers, scraper, or other automatic device, process, software or
  queries that … accesses the Services" (§5.2(i)), and limit all consumer users (ToS §5.1, last
  updated 2026-01-23, not only Free and Pro) to "personal, non-commercial use" [41][42]. No
  sanctioned CLI, no headless Comet, no Computer-trigger API. Driving the web
  app with Playwright to harvest Pro/Max quota would be a ToS violation and a ban risk. The only
  compliant "subscription" automation paths are Perplexity's own: Scheduled Tasks in Computer
  (results land in the app/notifications, not in your DB), the email trigger
  (`computer@perplexity.com`, 2026-08-24 [74]) and Personal Computer for Mac/Windows (agent
  runs on your machine; still no API to enqueue work from your scheduler) [43][48][74].
- **Rate limits (API).** Usage tiers by cumulative spend: Tier 0 ($0) → 1 QPS on Agent API,
  50 RPM Sonar, 5 RPM `sonar-deep-research`; Tier 1 ($50+) 3 QPS; Tier 2 ($250+) 8 QPS; Tier 3
  ($500+) 17 QPS; Tier 4/5 ($1k/$5k+) 33 QPS. Search API: 50 query-units/s at all tiers [8].
  For this server (single tenant, tens of jobs/day) Tier 0 is sufficient.
- **Sandboxing.** Agent API `sandbox` is Perplexity-hosted (isolated Linux, Python + bash,
  full outbound internet, $0.03 per 20-minute billing window (docs: "this is the billing window,
  not a runtime cap"), in-session `web_search`/`fetch_url`/`people_search` calls billed at their
  standard per-invocation rates on top, ~1 MiB stdout cap, files retrievable via the files
  API) [1][11]. Nothing runs on your machine. Personal Computer is the opposite: it *is* an agent
  with Accessibility + Full Disk Access on your Mac (unverified as of 2026-09-24 — not stated
  in the cited MacRumors article), sandboxed file creation, auditable/reversible actions and a
  kill switch [43] — a security decision, not a convenience one, on a box that also runs your
  trading research. The 2026-09-21 Hybrid compute option keeps *some* subtasks local, and the
  pre-release "Privacy Gate" PII screen [73] is the first Perplexity feature aimed at exactly
  this concern — but orchestration and heavy reasoning still go to the cloud [73][74].
- **Structured event output.** Streaming via `stream=true` with SSE events
  `response.output_text.delta` and `response.completed`; final `usage` carries
  `input_cost`/`output_cost`/`total_cost` in USD; `search_results` output items carry
  `id,url,title,snippet,date,last_updated,source` [4][10][15]. Good for audit-log ingestion.
- **Session resume.** `previous_response_id` continues server-side stored state (`store`
  defaults true); retention window undocumented; ZDR accounts told to "check with your account
  team" [16]. Fallback chains: `models: [...]` up to 5, billed only for the model that served
  [18].
- **Data handling.** Zero-data-retention for the (legacy) Chat Completions API, no training on
  customer data, SOC 2 Type II; third-party-model data handling on the Agent API not addressed
  in the privacy page [28]. Per-lane matrix (2026-09-24):

  | Lane / auth mode | Training use | Retention window | Residency | ZDR eligibility | Source |
  |---|---|---|---|---|---|
  | Agent/Search API, Bearer key | No — API ToS: Perplexity "shall not use (or authorize third parties to use) Customer Content to train, retrain, fine-tune or otherwise improve any generative artificial intelligence models" [79] | FAQ: "zero day retention of user prompt data"; billing metadata only (tokens, model, timestamp, key) [28][30]. Exception: `store=true`/`previous_response_id` server-side state — window undocumented [16] | **Not found** (DPA page 404; trust.perplexity.ai renders no text) | Default for prompts; conversation-state ZDR "check with your account team" [16] | [16][28][30][79] |
  | Remote MCP, OAuth | Same as API (bills an API org) [78] | Same as API | Same | Same | [78] |
  | Third-party models via Agent API / Router (`anthropic/*`, `openai/*`, `xai/*`, Router deployments) | Perplexity's no-training covenant binds Perplexity [79]; upstream: Perplexity's help center states "Perplexity's agreements with third party model providers like OpenAI and Anthropic prohibit using Perplexity data for training their models" [87] (article 403 direct; wording from search snippet + DeleteMe's 2026-09-15 quotation [89]) — a **general, not lane-specific** statement. Anthropic, OpenAI, Google Cloud, xAI, Amazon Bedrock and Microsoft Azure are listed as sub-processors ("AI models like Claude / Gemini / Grok"), all US [91] | Upstream **ZDR is asserted only for Enterprise**: "Strict Zero Data Retention and Zero Data Training agreements with AI providers (OpenAI, Anthropic, and more) prevent training on Enterprise data" [88]; not stated for the API-key lane | US sub-processors [91]; deployment identity hidden ("regardless of which deployment served the request") [84] | Not stated for API; Enterprise only [88] | [79][84][87][88][91] |
  | Consumer Pro/Max (web, Computer, Personal Computer, Comet) | Privacy notice: content used to "improve or create services and products, including our AI models" [86]. **Opt-out exists but is off-by-default-on:** the "AI data retention" toggle (profile → All settings → Preferences) is *enabled* on Free/Pro/Max and must be switched off to stop training; Enterprise has it off automatically [89][90][92]. Upstream labs are contractually barred from training on Perplexity data either way [87] | Notice: "as long as necessary" [86]; Strac (2026-08-10): ~30 days consumer, ~7 days Enterprise, uploaded files 7 days on Enterprise [88][92] | US sub-processors [91] | None (Enterprise only) | [86][87][88][89][90][91][92] |

  Consequence for the paper-trading lab (revised 2026-09-24): proprietary theses may go through
  the **API-key lane to `perplexity/sonar`** (Perplexity-hosted, ZDR, no training). For
  `anthropic/*`/`openai/*`/`xai/*` via Perplexity the *training* half is now covered (upstream
  labs contractually barred [87]) but the *retention* half is only asserted for Enterprise
  [88] — so treat those routes as "no-training, unknown-retention": acceptable for a
  second-opinion read of a thesis you would also send to the lab directly, not for anything
  you would only send under a ZDR lane. The labs' own API/ZDR lanes remain the default for
  thesis routing; the blocker is downgraded from "unstated" to "retention unconfirmed".

- **Progress visibility / quota introspection.** API: **no programmatic balance or budget
  endpoint** — usage tier and spend are visible only on the console Billing/Pricing pages
  (7/30-day and custom filters, per-model breakdown) [8][29][30]; rate-limit docs list no
  spend headers [8]; the OAuth MCP connection explicitly "cannot … view balances" [78]. What
  you *can* collect: per-response `usage.input_cost/output_cost/total_cost` in USD [4] and
  `GET /v1/agent/{id}` status for background jobs [17]; webhooks are on the roadmap only
  ("Async API Webhook Support", "Developer Analytics Dashboard — query, latency, and cost
  visibility") [83]. Consumer: Computer credits/searches/Deep Research counters are in-app
  only; the Computer Analytics API (`/v1|v2/analytics/computer/usage`, hourly/daily buckets,
  free) is **Enterprise-only** [32]. Lane rating for "watch their progress": API = per-call
  cost + job status (adequate, self-tabulated); subscription = none.
- **Third-party serving.** API ToS lets the customer "display such Output … solely within the
  Customer Applications" [79] → API outputs may be served to non-owner users (pickem league
  dashboard, shared project sites) under your key, subject to the AUP. Consumer ToS §5.1
  "personal, non-commercial use" + §5.2(i) robot ban [42] → nothing from Pro/Max/Computer/
  Personal Computer may back a page a second person reads. Rule: **serves a second person →
  API key**, same as chatgpt-openai.md.
- **Interactive-surface latency (Telegram round trip).** Vendor publishes no TTFT/tok-s on the
  presets, models, output-control or SDK-performance pages [5][2][15][85]; Artificial Analysis
  lists `sonar` and `sonar-reasoning-pro` speed as N/A [62][95]. Third-party numbers found
  2026-09-24: **OpenRouter's live panel for `perplexity/sonar` — P50 latency 1.45 s, 75 tok/s,
  3-day uptime 100% / availability 99.98%** [93] (its JSON endpoint reports `latency`/`throughput`
  null, context 127,072, max completion 114,364 [94] — the panel figure is a rolling P50, so
  re-check before relying on it). Historical vendor claim: Sonar on Cerebras, "1,200 tokens per
  second", Llama 3.3 70B, 2025-02-11 — that was the *consumer Pro* Sonar, and the current
  `perplexity/sonar` base/host is undisclosed, so do not assume it [96]. For the presets, the
  only measured figures are for the underlying OpenAI models at *max* reasoning effort on
  OpenAI's own API: `gpt-5.6-luna` TTFT 132 s / 122.6 tok/s, `gpt-6-luna` TTFT 108 s /
  141.4 tok/s [97][98] — upper bounds, since Perplexity does not state which effort its
  `fast`/`low`/`medium` run at. Also documented: `fast` is the preset for when "latency matters
  most" [5]; structured outputs add 10–30 s on the first call per schema [15]; the docs advise
  *non-streaming* when search results must be shown immediately and `background=true` for
  anything taking minutes [15]. Rating for the chat surface (now number-backed for `sonar`):
  `sonar` streaming ≈ 1.5 s to first token + ~4 s for a 300-token answer, acceptable for
  Telegram with a typing indicator; `fast`/`low` = unmeasured, assume 5–30 s; `medium`+ = tens
  of seconds; `high`/`xhigh`/`wide-research` = background-only.
- **Concurrency / scheduler fan-out.** No concurrent-request limit is documented anywhere; the
  only limiter is org-wide QPS in "a rolling one-second window" across all keys and models
  (Tier 0 = 1 QPS) [8]; background jobs have no documented cap, and their reconnect window
  duration is undefined [17]; the SDK guide's own pattern is an `asyncio.Semaphore` plus
  exponential backoff with jitter on 429 [99]. Practical fan-out for this server: at Tier 0
  *launch* ≤1 job/s (a `time.sleep(1)` between `background=True` submits), then poll — dozens of
  jobs can be in flight; long streams are not counted against QPS once started.
- **Credential lifecycle (headless box).** Bearer API key only: no TTL, no refresh, no device
  flow; it lives wherever you put `PERPLEXITY_API_KEY` (docs: env var / `.env`, never in VCS
  [99]) — on this box that means the launchd `.env` or Keychain via `security find-generic-
  password`, your choice. What fails first is *balance*, not the token: keys hard-stop at $0
  and return 401/402-class errors until topped up [29]. Remote-MCP OAuth tokens (Sep 2026) have
  no published TTL and are user-scoped [78] — do not use them for unattended jobs. Expiry alarm:
  none from the vendor; build one from `usage.total_cost` accumulation vs. the last known
  console balance.
- **Prompt-injection / sandbox posture (untrusted inputs).** API lane: the model sees fetched
  pages and `web_search` snippets as tool results, and attached remote MCP tools **auto-run with
  no approval hook** [12] — so the Perplexity-side agent must only ever hold read-only tools;
  the server-side `sandbox` is Perplexity-hosted with full outbound internet [11], i.e. nothing
  can reach this Mac. Consumer/agentic lane: the worst injection record in this research set
  (Comet OTP exfiltration, CometJacking, PerplexedComet, Guardio phishing in <4 min) [65].
  Cross-cut rank for this server's Telegram/web-page ingestion: API-key lane = **safe-by-
  isolation** (remote execution, read-only tools) — comparable to Codex Seatbelt for
  containment, weaker than Claude's `verbatim_prompts` for *awareness*; consumer/Comet/Personal
  Computer = **worst in class**, keep off the trading host.
- **Progress-visibility sink.** Emitters: per-response `usage.{input,output,total}_cost` [4],
  SSE `response.output_text.delta`/`response.completed` [15], `GET /v1/agent/{id}` status [17].
  No OTEL exporter, no webhooks (roadmap [83]). To feed the existing web dashboard, the runner
  should write one JSONL envelope per call — `{lane:"perplexity", model, preset, job_id,
  cost_usd, in_tok, out_tok, tool_calls, ttfb_ms, status}` — into `volumes/audit_log/<job>.jsonl`
  (the same file the other lanes append to) and a Postgres rollup of `Σcost_usd` per day; the
  "remaining budget" figure is *inferred* (last console top-up − Σcost) because no balance API
  exists [29][30]. Host footprint: **zero always-on daemons** — the remote MCP is HTTP, the
  Python SDK is in-process; only the optional `npx @perplexity-ai/mcp-server` local shim costs
  a Node process (~100 MB class, unmeasured) [33].
- **Empirical calibration caveat.** The §4 cost table uses the shared synthetic 150k-in/15k-out
  job with 0% cache; this pass did not read `volumes/audit_log` (out of scope for the doc
  fix), so real jobs/month, tokens/job and cache-hit share are still the cross-doc open item.
  For Perplexity the verdict is insensitive to it: every path is metered and the sub-$0.10
  `sonar`/`low` job beats any subscription below ~200 jobs/month regardless of the Max tier the
  owner holds.
- **Reviewer independence.** Routing `anthropic/*`/`openai/*`/`xai/*` through Perplexity buys
  *no* extra lineage diversity over calling those labs directly — they are the same upstream
  models via sub-processors [91]; the only genuinely different lineage on this key is
  `perplexity/sonar` (Llama-3.3-derived as of 2025 [96], current base undisclosed) plus the
  Moonshot/Z.AI/NVIDIA routes, and the Nov-2025 routing scandal (cheaper models served under
  Claude labels [37]) means the *served* model is not verifiable from the response. For a
  second-opinion lane, prefer the labs' direct APIs and use Perplexity for the *search-grounded*
  opinion, which is the one dimension where its errors are actually uncorrelated with a
  non-grounded reviewer.
- **Tool churn (cost of ownership).** Python SDK `perplexityai` went 0.39.0 → 0.43.5 in ten
  releases between 2026-07-02 and 2026-08-31 (MCP tool support, `skills` parameter, Bazel
  migration, Python ≥3.10 requirement), none flagged breaking, but the package states
  "certain backwards-incompatible changes may be released as minor versions" [81][82]. Platform
  churn is the larger burden: Sonar sunset 2026-09-27 [6], presets are dynamic [5], monthly
  model additions [27], webhooks/analytics still roadmap [83]. Burden rating: **medium** — pin
  the SDK minor, freeze preset configs, re-read the changelog monthly.
- **Reliability (normalized: last 90 days / last 12 months, one source).** StatusGator: **1**
  API incident in the last 90 days (2026-08-13, 25 min, bad deploy rolled back) and **5** in
  the last 12 months (2026-08-13; 2026-05-08 2 h 5 m + 1 h 35 m; 2026-02-16 Sonar 50 min;
  2025-12-05 35 min major) [64] (the ">44 since May 2025" figure counts every status notice,
  not outages). Vendor page status.perplexity.com shows Jun–Sep 2026 uptime API 100%, App
  99.95%, Computer 99.65%, and lists no incidents for the window [80] — it under-reports
  relative to StatusGator. **No SLA and no priority/paid tier**: FAQ on uptime guarantees —
  "We do not guarantee this at the moment" [30]; API ToS is as-is with no uptime commitment
  [79]; rate-limit tiers change QPS only, not priority [8]; the Router does weighted failover
  across deployments and returns 429 + `Retry-After` when all fail [84]. Expect to wrap calls
  with retries and a fallback provider.

## 4. Cost

**Consumer plans (monthly; annual in parentheses)** [34][35][36][37][40] — Perplexity's own pricing
page is still unreachable (403 direct and via text proxy, 2026-09-24), but the headline prices are
now **verified from a first-party source**: the App Store listing's In-App Purchases (app v26.37.0)
show "Perplexity Pro — $20.00", "Perplexity Pro — $200.00" (annual), "Perplexity Max — $200.00",
and Computer credit packs "500 Credits — $5.00, 1,000 — $10.00, 2,500 — $25.00, 5,000 — $50.00"
[77], matching CloudZero (2026-09-21) [34], Finout [40] and SecondTalent [48]. Max annual
($2,000) and Enterprise ($40 / $325 per seat, $400 / $3,250 annual) remain secondary [34][48]:

| Plan | Price | Includes | Caps (as reported) |
|---|---|---|---|
| Free | $0 | Basic model, ~3 Pro searches/day, Comet browser, Finance hub browsing, Deep Research limited | [36] |
| Pro | $20 ($200/yr ≈ $16.67) | Pro searches, model picker (GPT/Claude/Gemini/Grok/Kimi/GLM), Deep Research, Labs, file uploads, Computer access, Scheduled Tasks, Finance Portfolio (Plaid) | Pro searches 100/week (halved May 2026 — scope unverified as of 2026-09-24: ailimit.watch [36] attributes the cut to promo-code accounts only, Okane Land [37] to prepaid annual plans generally); Deep Research ~20/month (was ~500/day until Feb 2026); Labs 25/month; uploads 50/week; Computer: one-time 4,000-credit bonus, no monthly credits [35][36][37][38] |
| Education Pro | $10 | Pro for verified students | [40] |
| Max | $200 ($2,000/yr ≈ $167) | Everything in Pro + frontier models (GPT-5.6 Sol, Claude Opus 5), Model Council, Brain, 10× upload limits, 5× video; Personal Computer for Mac/Windows is **no longer a Max exclusive** (Pro since 2026-05-10 Mac / 2026-08-04 Windows, secondary [48]) | 10,000 Computer credits/month + 35,000 one-time bonus (CloudZero [34], Zieminski [35] and SecondTalent [48] all say 35,000; Finout [40] lists only the 10,000/month allowance and gives no bonus figure — no 20,000 source located); credits ≈ $0.01 each (500 = $5, "100 credits to the dollar" [34]); no rollover; typical task 31–100+ credits, 5–8× more in long threads [35][47]. Overage is governed by a **monthly Computer spending cap, $200 by default and adjustable up to $5,000** per [34][48] (the fact-checker saw a $2,000 ceiling elsewhere — not located this session); running tasks pause at the cap [34] |
| Enterprise Pro / Max | $40 / $325 per seat | Admin controls; 500 / 15,000 Computer credits per month; custom Computer credit limits per org since 2026-06-18 [74] | [34][74] |

**API prices** [1][2][10][11][23][24][25][26]: see the model table in §1 for per-token
rates. Tool fees: web search $0.0025, fetch URL $0.0005, finance search $0.005, people search
$0.005, sandbox $0.03 per 20-minute billing window plus $0.0025 per in-session web search,
MCP calls free. Search API $5/1K requests (no token fees). Embeddings `pplx-embed-v1-0.6b`
$0.004/1M, `-4b` $0.03/1M; context variants `pplx-embed-context-v1-0.6b` $0.008/1M, `-4b`
$0.05/1M [1]. Legacy Sonar (to 2026-09-27):
`sonar` $1/$1 + $5–12/1K requests by `search_context_size`; `sonar-pro` $3/$15 + $6–14/1K;
`sonar-reasoning-pro` $2/$8 + $6/$10/$14 per 1K; `sonar-deep-research` $2 in / $8 out / $2
citation / $3 reasoning per 1M + $5/1K searches — doc sample report cost $0.816 for 11,395
completion tokens and 21 searches [26]. No cached-input discount on legacy Sonar; Agent API
lists cache-read rates per model. **No batch discount exists** [17]. Free tier: **Not found —
searched:** "Perplexity API free credits new account"; docs FAQ lists none [30].

**Monthly cost to run N agent jobs (assume 150k input + 15k output tokens/job, ~10 tool calls/job)**

| Path | Per job | 10 jobs | 100 jobs | 1,000 jobs | Notes |
|---|---|---|---|---|---|
| (a) Pro subscription, driven manually / Scheduled Tasks | n/a | $20 | quota-bound | not feasible | Programmatic use violates ToS; Deep Research ~20/mo, Pro searches 100/wk [36][41] |
| (a) Max subscription via Computer credits | ~100 credits ≈ $1 | $200 | $200 (10k credits ≈ 100 tasks) | $200 + ~$900 overage under the Computer spending cap (default $200/mo, raisable to $5,000 [34][48]) | No API to enqueue/collect results; credits "burn" 5–8× in long threads [35][47] |
| (b) Agent API `perplexity/sonar` | $0.0375 + $0.0375 + $0.025 tools ≈ **$0.10** | $1 | $10 | $100 | Cheapest grounded path [2][10] |
| (b) Agent API preset `low` (gpt-5.6-luna) | ≈ $0.03 + $0.02 + $0.02 ≈ **$0.07** | $0.70 | $7 | $70 | Vendor's own "~$0.05/query" for short prompts [71] |
| (b) Agent API `anthropic/claude-sonnet-5` | $0.30 + $0.15 + $0.03 ≈ **$0.48** | $4.80 | $48 | $480 | |
| (b) Agent API preset `high` (gpt-5.6-sol) | $0.75 + $0.45 + $0.04 ≈ **$1.25** | $12.50 | $125 | $1,250 | Above-272k inputs hit the tiered rate [2] |
| (b) Agent API `anthropic/claude-opus-5-5` | $0.60 + $0.30 + $0.03 ≈ **$0.93** | $9.30 | $93 | $930 | Cheaper than Anthropic direct for Opus (unverified as of 2026-09-24 — not checked against Anthropic list price) but metered |
| (b) Legacy `sonar-deep-research` report | ≈ $0.82/report (doc sample) | $8 | $82 | $820 | Dies 2026-09-27 [26] |

Assumptions: no cache hits (since Aug 2026 presets carry stable cache keys so independent
requests with the same preset share the prompt prefix — Perplexity estimates ~5% savings for
preset-heavy apps [27]; explicit-model calls get the per-model cache-read rate in §1 on repeated
prefixes); tool calls = 8 web searches + 2 fetches; presets' "dynamic"
model may change underneath you [5]; the `fast` preset bills gpt-6-luna at 2× standard token
price [27]. All API paths are metered — the owner's "subscriptions over metered" preference is
satisfied by none of them, but at $0.07–0.10/job the Sonar/`low` path is cheaper than any
subscription for < ~200 jobs/month.

## 5. Strengths & weaknesses per reviews

**Benchmarks (vendor-reported, Agent API vs Sonar)** [7]: BrowseComp accuracy — `sonar` 7.0%,
`sonar-pro` 7.3%, `sonar-reasoning-pro` 16.3%, `sonar-deep-research` 29.1%, Agent API `fast`
28.0%, `low` 54.2%, `medium` 69.3%, `high` 85.7%. DeepSearchQA F1 — Sonar 27–49%, Agent API
61–90%. WideSearch F1 — Sonar 8–19%, Agent API 33–57%. Perplexity's Deep Research launch claim
(2025-02-15): 21.1% on Humanity's Last Exam [61] and 93.9% on SimpleQA (unverified as of
2026-09-24 — TechCrunch carries only the HLE figure; 93.9% comes from Perplexity's own blog
[60], which returned 403), most reports <3 minutes [61]. Perplexity says its "wide-research" preset leads its own WANDR benchmark [20].
Independent: Artificial Analysis rates legacy `sonar` Intelligence Index 8 (#129/298
non-reasoning), flags it deprecated in favour of Sonar Reasoning Pro [62]; Parallel's Sept-2026
Search-API benchmark (SimpleQA-Verified, BrowseComp, WideSearch) ranks Perplexity below
Parallel and compares it only with Exa and Tavily — a competitor-run benchmark, weigh
accordingly [63]. **Not found — searched:** LMArena, SWE-bench Verified, Terminal-Bench, GPQA
entries for any Sonar model (Perplexity does not compete on coding/agentic-coding leaderboards).

**Citation accuracy (the thing it sells).**
- CJR/Tow Center (2025-03-06, 1,600 queries, 8 engines): Perplexity was the *best* of the
  eight but still wrong 37% of the time on retrieving the source of a quoted passage [57].
- Haus Research (2026-09-02, `sonar` + `sonar-pro`, 310 questions, 1,826 numeric citations):
  34.7% of citations pointed at a page that would not open or did not contain the cited figure;
  per-claim, 14.4% of claims had no supporting source; `sonar` and `sonar-pro` were
  indistinguishable (65.9% vs 64.7% pass); 16.1% of cited pages sat behind paywalls [58].
- Indian Journal of Orthopaedics 2026 (3,150 references, rotator-cuff literature): Perplexity
  had the *highest* reference-hallucination rate of ChatGPT/Gemini/Perplexity in that academic
  setting [59].
- Community audits (Sept 2026, HN-circulated): 59.8% of Sonar citations in a software-category
  sample pointed at domains ranked worse than #100,000 on Tranco; content farms are being cited
  as sources (attributed to Beri.net / Trellner Research; not part of the Haus report [58] —
  primary source not located, treat as unverified).
Net: best-in-class at *attaching* sources, unreliable at guaranteeing the source *supports*
the claim. Treat citations as leads to verify, not evidence.

**Strengths (professional reviews).** Fastest end-to-end deep research (2–4 min) with
transparent citations, "most citation-verifiable" of the deep-research modes [72][61];
Finance answers on well-covered large caps rated ~94% accurate vs ChatGPT 81% in one
2026 comparison [56]; Comet reviewed as a solid free Chromium browser on Mac/Windows/iOS/Android whose autonomous
Browser Agent needs Pro/Max [69];
Agent API praised for one-endpoint search+fetch+code+MCP+finance ("Search as Code") and
transparent per-request cost fields [71].

**Weaknesses / controversies.**
- *Quota bait-and-switch.* Pro Deep Research cut ~500/day → ~20/month (Feb 2026), Labs 50 →
  25/month, uploads unlimited → 50/week, Pro searches 200 → 100/week (May 2026; scope disputed
  between [36] and [37], see §4), applied
  mid-term to annual subscribers; ailimit.watch counts 75% of tightenings as unannounced
  [36][37][38]. Okane Land's 1,024-post study ranks complaints: price/value (121), limits (113),
  Computer credit burn (63), billing/refunds (47) [37].
- *Model-routing scandal (Nov 2025):* users found cheaper models served under Claude labels;
  CEO called it "an engineering bug" found only because of the Reddit thread [37].
- *Security of the agentic surfaces:* Brave (2025) prompt-injection exfiltrating Gmail OTP;
  CometJacking (Oct 2025); Zenity "PerplexedComet" zero-clicks (1Password hijack); Trail of Bits
  four injection techniques; Guardio (2026-03-11) tricked Comet into entering credentials on a
  GAN-optimised phishing page in under four minutes [65]. A malicious Chrome extension
  impersonating Perplexity logged searches (Microsoft, Jun 2026) (unverified as of 2026-09-24 —
  not in the cited Hacker News article [65]).
- *Legal:* Dow Jones/NY Post (Oct 2024), Yomiuri Shimbun (2025-08-08, "free-riding" on
  ~120,000 articles), Asahi Shimbun and Nikkei (late Aug 2025), Reddit (Oct 2025, federal
  scraping suit, S.D.N.Y.) [75]; NYT (2025-12-05), Chicago Tribune (Dec 2025), CNN (2026-05-28,
  17,000+ items) copyright suits (these three dates unverified as of 2026-09-24 —
  lawsuitsjournal.com [67] returned 404 and Wikipedia [75] does not list them); Amazon suit over
  Comet shopping agent; Cloudflare de-listed Perplexity as a verified bot for UA-spoofing crawls
  [66][67][75].
- *Business durability:* HN thread "Is Perplexity the first AI unicorn to fail?" — consensus
  "wrapper, no moat"; counterpoint the $400M Snapchat deal [68]. Relevant to lock-in risk.
- *Computer credits are opaque in consumption, not in price:* top-up packs are $5/500 to
  $50/5,000 (linear, 100 credits per dollar) on the App Store [77]; what is opaque is burn —
  reviewers logged a 40-min task at 15,000 credits and a 280k-line codebase scan at ~21,000
  credits [47].

## 6. Finance / trading relevance

- **Consumer Perplexity Finance** (perplexity.ai/finance): market dashboard, index charts,
  gainers/losers, sector heatmap, Earnings Hub (calendar, transcripts, near-real-time call
  transcription with revenue/EPS pulled as spoken), natural-language screener, watchlists,
  price alerts (push/email), Portfolio via Plaid (US/Canada, read-only brokerage aggregation,
  ~Mar 2026), Scheduled Tasks. Data partners named: SEC/EDGAR, FactSet, S&P Global, Morningstar,
  LSEG, Financial Modeling Prep, Crunchbase, Quartr, Coinbase (crypto), Polymarket (prediction
  markets). Coverage: US equities primary, Indian equities, ETFs, mutual funds, crypto; options
  not mentioned [55]. Quotes are "fetched when you ask, not streamed"; free users throttled at
  peak [56]. Weak on small caps; one review documents a 1,000× revenue misread from a 10-K; no
  thesis memory or position re-evaluation [56].
- **API: `finance_search` tool** (Agent API, $5/1K invocations + model tokens, `max_steps` ≥
  3): quotes, profiles, peers; income/balance/cash-flow (quarterly/annual) and ratios; OHLCV from
  1-minute to 1-month bars including pre/after-hours; earnings transcripts, SEC filings,
  beat/miss history, guidance; segment KPIs (ARPU, subscribers, GMV); analyst estimates; top
  gainers/losers/most active; insider activity, splits; ETF/index constituents and weights.
  Coverage: public companies and ETFs; "market data may be delayed, incomplete, or unavailable
  for some symbols"; "informational purposes only — not investment advice" [9]. Presets `xhigh`
  and `wide-research` include `finance_search` by default [5].
- **Sentiment sources.** Web search with domain allow/deny lists (≤20), recency filters, and
  `fetch_url` cover news/blogs; no first-party X/Reddit firehose; Polymarket data appears only in
  the consumer product [10][55].
- **Restrictions.** No order routing, no brokerage write access anywhere (Plaid link is
  read-only) [55]. The consumer ToS "personal, non-commercial" clause is irrelevant to the API,
  which is commercial by design [41]; the API ToS page returned 403 — **unverified** whether it
  carries finance-specific restrictions beyond the not-advice disclaimer in the tool docs [9].
- **Fit for Atlas.** As a *research* backend (earnings-transcript summaries, peer/ratio pulls,
  "why did X move today" with sources) it is genuinely useful and cheap. As a *market-data*
  backend it is inferior to a direct provider (delayed, coverage caveats, no streaming) and
  should never be the price source for paper fills.

## 7. Integration recipe for our server

**Recommended path:** Agent API with a prepaid API key (no subscription). Start on
`perplexity/sonar` or preset `low` for grounded lookups, `high`/`wide-research` in
`background=true` mode for reports, `finance_search` for Atlas research. Keep Claude (via the
existing Claude Max SDK session) as the reasoning/coding brain; use Perplexity strictly as a
*tool*: (1) an MCP server the Claude Agent SDK session can call, and (2) a Python client inside
scheduled jobs.

**Auth/cost path.** Create a Project in the API Portal, buy a small credit block (e.g. $20 —
minimum not documented [29]), enable auto top-up with a low ceiling, set a per-job budget guard
in the runner using `usage.total_cost` from each response [4]. Tier 0 (1 QPS) is fine.

**Wire-up A — MCP tool for the Claude Agent SDK** (remote, no npx process to babysit) [33]:

```
# ~/.claude/mcp.json (or SDK mcp_servers config)
{ "mcpServers": { "perplexity": {
    "type": "http", "url": "https://api.perplexity.ai/mcp",
    "headers": { "Authorization": "Bearer ${PERPLEXITY_API_KEY}" } } } }
```
Tools exposed: `perplexity_search` (raw ranked results, $0.005/req), `perplexity_ask`
(`fast`), `perplexity_reason` (`medium`), `perplexity_research` (`high`). Allowlist only
`perplexity_search` + `perplexity_ask` for cheap workers; enable `perplexity_research` only for
research-lane skills.

**Wire-up B — Python in a scheduled job** [4][9][15][17]:

```python
from perplexity import Perplexity            # pip install perplexityai
px = Perplexity()                            # reads PERPLEXITY_API_KEY

# 1) cheap grounded lookup with structured output
r = px.responses.create(
    model="perplexity/sonar",
    input="Summarise today's SEC 8-K filings for NVDA with dates. Cite sources.",
    tools=[{"type": "web_search",
            "filters": {"allowed_domains": ["sec.gov", "reuters.com"]},
            "search_context_size": "medium"}],
    response_format={"type": "json_schema", "json_schema": {
        "name": "filings", "schema": {"type": "object", "properties": {
            "items": {"type": "array", "items": {"type": "object", "properties": {
                "date": {"type": "string"}, "summary": {"type": "string"},
                "source_id": {"type": "integer"}}, "required": ["date", "summary"]}}},
            "required": ["items"]}}})
print(r.output_text, r.usage.total_cost)     # USD, log into audit_log

# 2) finance research, async so the launchd job can exit and a poller collects
r = px.responses.create(
    model="anthropic/claude-sonnet-5", max_output_tokens=8000,   # required for anthropic/*
    input="Compare AAPL vs MSFT last 4 quarters: revenue, FCF margin, guidance changes.",
    tools=[{"type": "finance_search"}, {"type": "web_search"}],
    max_steps=8, background=True)
# later: px.responses.retrieve(r.id) until status in {"completed","failed","cancelled","incomplete"}
```

Streaming for the Telegram bridge: `stream=True`, forward `response.output_text.delta`
events; finish on `response.completed` and post the `search_results` URLs as the citation
footer [15].

**Task classes here.**

| Task class | Fit | Why |
|---|---|---|
| Research (web-grounded briefs, "what changed since X") | Strong | This is the product; `low`/`high` presets, `wide-research` for enumerations [5][20] |
| Trading research (earnings, filings, peers, KPIs) | Good | `finance_search` structured pulls + citations; not a price feed [9] |
| Adversarial review / second opinion | Useful | Cheap cross-vendor read (Grok, GPT-6, Kimi K3, GLM) through one key with `models` fallback [18] — a poor-man's Model Council |
| Classification / routing | OK | `perplexity/sonar` or `gpt-6-luna` at $0.10–0.75/1M in [2]; no search needed → disable tools |
| Coding / agentic coding | Weak | No repo access, no local execution, sandbox is remote and 20-min; Claude Code stays the coder [11] |
| Code review | Weak–OK | Could pass diffs to `kimi-k2.7-code` or Opus for an alternative opinion, but no tooling advantage |
| Chat (Telegram front door) | OK (`sonar`/`fast` only) | Streaming works; citations need post-processing; no vendor TTFT figures (§3) — `fast` is the documented low-latency preset, `low`+ are tens of seconds, `high`+ must run `background=true` [5][15] |

**Gotchas.**
1. Sonar chat-completions models die **2026-09-27** per Perplexity [6] (llmgateway.io's 25th is
   that gateway's own early re-route, not Perplexity's date [70]) — do not build on `sonar-pro`,
   `sonar-reasoning-pro`, `sonar-deep-research`; only `perplexity/sonar` survives. Official
   replacement mapping: `sonar`→`fast`, `sonar-pro`→`low`, `sonar-reasoning-pro`→`medium`,
   `sonar-deep-research`→`high` [6][70].
2. `anthropic/*` models require `max_output_tokens` or you get HTTP 400 [2][18].
3. Presets are *dynamic* — the underlying model changes as Perplexity's evals move; freeze by
   copying the preset's explicit config if reproducibility matters [5].
4. `fast` preset bills gpt-6-luna at 2× the listed token price ("priority processing") [27].
5. Structured outputs: first call per schema is 10–30 s slower; outputs can exceed
   `max_tokens` and break the schema; never put URLs in the JSON — read `search_results` [15].
6. Citations are not verification: budget a fetch-and-check step (Haus: 34.7% of numeric
   citations fail) [58].
7. API keys hard-stop at zero balance; auto top-up or a balance monitor is mandatory for
   unattended jobs [29].
8. `finance_search` needs `max_steps ≥ 3`; data can be delayed; not a fill-price source [9].
9. `previous_response_id` state retention window is undocumented; persist your own
   transcripts [16].
10. Do not script the consumer app or Comet; ToS forbids automated access and the surfaces have
    a poor prompt-injection record [41][65].
11. Personal Computer for Mac (now Pro-tier, so cheaply reachable) would want Accessibility +
    Full Disk Access (unverified as of 2026-09-24) on the same Mac Mini that hosts Postgres and
    the trading loops — keep it off this box, or on a separate user. Hybrid compute (2026-09-21) reduces what leaves the box
    but does not change the local-permission footprint [73][74].
12. Third-party model data handling on the Agent API: upstream labs are contractually barred
    from *training* on Perplexity data [87], but upstream *ZDR* is asserted only for Enterprise
    [88] — don't send secrets or brokerage exports through `anthropic/*`/`openai/*` here [28].
13. Remote MCP tools attached to an Agent API request run **without approval** —
    `require_approval` is ignored ("Agent API does not support MCP approvals yet") — so never
    expose write-capable MCP tools (brokerage, git push, DB) to a Perplexity-side agent [12].
14. Preset prompt caching is automatic (stable cache keys since Aug 2026, ~5% saving); for
    explicit models, keep a stable system-prompt prefix to earn the cache-read rate [27].
15. MCP OAuth is convenience, not a billing path: it signs into an API org and bills it at API
    rates; it cannot draw on Pro/Max [78]. Use a Bearer key server-side.
16. No balance/usage endpoint exists — build the budget guard from `usage.total_cost` per
    response and a console check; auto top-up is the only hard-stop protection [4][29][30].
17. Outputs served to other people (pickem, shared sites) must come from the API lane; consumer
    outputs are personal/non-commercial [42][79].

## 8. Verdict

1. Perplexity is a search-and-orchestration vendor, not a frontier lab; its value to this
   server is *grounded retrieval with cost transparency*, reachable through one API key.
2. Subscriptions (Pro/Max) are the wrong tool: no API rights, ToS bans automation, quotas were
   cut ~95% in 2026, and Computer overage runs against a $200-default spending cap that
   burns unpredictably; Personal Computer (Mac since Apr 2026, Windows since Aug 2026, Hybrid
   local compute on Mac since Sep 2026) is intriguing but un-scriptable and security-heavy for
   a trading host, even now that it is on Pro (secondary sources) rather than Max-only. The
   Sep-2026 MCP OAuth does not change this: it authenticates an API org and bills API credits.
3. The Agent API (`/v1/agent`, Python SDK, OpenAI-compatible, MCP server, `background=true`,
   JSON schema, `finance_search`) is a clean fit as a *tool* inside Claude Agent SDK jobs at
   ~$0.07–0.10 per grounded job on `sonar`/`low`, ~$1.25 on `high` (before the ~5% preset
   cache saving); its MCP tool calls auto-run with no approval hook, so give it read-only tools.
4. Treat citations as leads (a third of numeric citations fail independent audit) and the
   vendor as a churn risk (litigation, 44+ API incidents/yr, Sonar sunset in 3 days).
5. Adopt for research and finance-research lanes with a hard per-job budget; do not adopt for
   coding, chat primary, or any subscription-based automation.

Fit scores (1–10), **calibrated anchors** so they can sit in the cross-provider router matrix:
10 = best available lane for this server's need with no workaround; 7 = production-usable with
a documented workaround; 4 = usable only for a narrow slice; 1 = prohibited or non-functional.
Two lanes scored separately because they differ in kind:

| Dimension | API-key lane | Consumer Pro/Max lane | Why |
|---|---|---|---|
| Research | **8** | 5 | Best grounded-retrieval API with cost fields; consumer Deep Research capped ~20/mo and un-scriptable |
| Coding / agentic | **3** | 2 | No repo/local execution; remote 20-min sandbox only |
| Cost efficiency | **7** | 2 | $0.07–0.10/grounded job, metered; Max $200 + credit burn, no API rights |
| Automation friendliness | **7** | 1 | Python SDK, background mode, MCP, JSON schema, no concurrency cap (1 QPS launch rate at Tier 0 [8]); consumer ToS bans automation; no usage endpoint keeps it off 9 |
| Trading research | **7** | 3 | `finance_search` + citations; not a price feed; consumer Finance is read-only, manual |
| Progress visibility | **5** | 1 | Per-call cost + job status only; no balance/budget API; Enterprise-only analytics |
| Chat-surface latency | **6** | n/a | `sonar` P50 1.45 s TTFT / 75 tok/s on OpenRouter [93]; presets unmeasured (underlying OpenAI models 108–132 s TTFT at max effort [97][98], upper bound) |
| Reliability | **6** | 5 | 1 incident/90 d, no SLA, no priority tier |
| Data handling | **7** | 3 | ZDR + no-training on API; upstream labs barred from training [87], upstream retention confirmed only for Enterprise [88]; consumer content trains unless the "AI data retention" toggle is switched off [89] |
| Third-party serving | **8** | 1 | API ToS allows display in Customer Applications; consumer personal/non-commercial |

## 9. Sources

All accessed 2026-09-24 unless noted. Pages marked (403) refused fetch; facts from them are
taken from search-engine snippets and secondary sources and are flagged unverified in the text.

1. https://docs.perplexity.ai/getting-started/pricing
2. https://docs.perplexity.ai/docs/agent-api/models
3. https://docs.perplexity.ai/docs/agent-api
4. https://docs.perplexity.ai/docs/agent-api/quickstart
5. https://docs.perplexity.ai/docs/agent-api/presets
6. https://docs.perplexity.ai/docs/agent-api/migrate-from-sonar
7. https://docs.perplexity.ai/docs/agent-api/migrate-from-sonar/benchmarks
8. https://docs.perplexity.ai/guides/rate-limits-usage-tiers
9. https://docs.perplexity.ai/docs/agent-api/tools/finance-search
10. https://docs.perplexity.ai/docs/agent-api/tools/web-search.md
11. https://docs.perplexity.ai/docs/agent-api/tools/sandbox
12. https://docs.perplexity.ai/docs/agent-api/tools/mcp
13. https://docs.perplexity.ai/docs/agent-api/tools/connectors.md
14. https://docs.perplexity.ai/docs/agent-api/skills.md
15. https://docs.perplexity.ai/docs/agent-api/output-control.md
16. https://docs.perplexity.ai/docs/agent-api/conversation-state.md
17. https://docs.perplexity.ai/docs/agent-api/background-mode.md
18. https://docs.perplexity.ai/docs/agent-api/model-fallback.md
19. https://docs.perplexity.ai/docs/agent-api/openai-compatibility.md
20. https://docs.perplexity.ai/docs/agent-api/wide-research.md
21. https://docs.perplexity.ai/docs/search/quickstart
22. https://docs.perplexity.ai/docs/router/models.md
23. https://docs.perplexity.ai/docs/sonar/models/sonar.md
24. https://docs.perplexity.ai/docs/sonar/models/sonar-pro
25. https://docs.perplexity.ai/docs/sonar/models/sonar-reasoning-pro.md
26. https://docs.perplexity.ai/docs/sonar/models/sonar-deep-research.md
27. https://docs.perplexity.ai/docs/resources/changelog
28. https://docs.perplexity.ai/docs/resources/privacy-security.md
29. https://docs.perplexity.ai/docs/getting-started/projects.md
30. https://docs.perplexity.ai/docs/resources/faq.md
31. https://docs.perplexity.ai/docs/sdk/overview.md
32. https://docs.perplexity.ai/docs/admin/computer-analytics-api.md
33. https://github.com/perplexityai/modelcontextprotocol
34. https://www.cloudzero.com/blog/perplexity-pricing/ (dated 2026-09-21)
35. https://karozieminski.substack.com/p/perplexity-computer-pricing-credits-2026 (Jun 2026)
36. https://ailimit.watch/tools/perplexity/ (last verified 2026-06-06)
37. https://okaneland.com/study/perplexity-pro-limits/ (Jul 2026)
38. https://www.makeuseof.com/bought-annual-perplexity-subscription-lied/ (2026-02-21)
39. https://goosed.ie/news/perplexity-pro-quietly-removes-free-api-credits/
40. https://www.finout.io/blog/perplexity-pricing-in-2026
41. https://www.geeky-gadgets.com/perplexity-bot-scraper-ban/ (2026-02-20)
42. https://www.perplexity.ai/hub/legal/terms-of-service (403 direct; §5.1/§5.2(i) verified 2026-09-24 via a text-proxy fetch; last updated 2026-01-23)
43. https://www.macrumors.com/2026/04/16/perplexity-personal-computer-for-mac/
44. https://appleinsider.com/articles/26/05/02/mac-mini-is-the-best-platform-for-perplexitys-personal-computer
45. https://siliconangle.com/2026/08/25/perplexity-ai-launches-portable-computer-on-device-ai-agent/
46. https://www.vellum.ai/blog/official-perplexity-computer-breakdown
47. https://www.customcodelabs.com/blog/perplexity-computer-19-model-ai-agent-review-2026
48. https://www.secondtalent.com/resources/perplexity-ai-features-capabilities-2026/
49. https://www.testingcatalog.com/perplexity-adds-scheduled-tasks-feature-for-pro-and-enterprise-users/ (2025-06)
50. https://www.business-standard.com/technology/tech-news/perplexity-ai-whatsapp-chatbot-adds-schedule-task-feature-how-it-works-125062500758_1.html
51. https://t.me/askplexbot
52. https://x.com/testingcatalog/status/1910346590537032180
53. https://aiweekly.co/alerts/perplexity-brain-adds-self-improving-work-memory-to-its-agent
54. https://www.perplexity.ai/en-GB/changelog/what-we-shipped---february-6th-2026 (Model Council; Deep Research on Opus 4.5 for Max and Pro; 403, via snippet)
55. https://sidsaladi.substack.com/p/perplexity-finance-101-2026-the-complete
56. https://helmterminal.dev/blog/perplexity-stock-research (2026-07-08, updated 2026-09-15)
57. https://www.cjr.org/tow_center/we-compared-eight-ai-search-engines-theyre-all-bad-at-citing-news.php (2025-03-06)
58. https://hausresearch.com/reports/perplexity-citation-audit/ (2026-09-02)
59. https://link.springer.com/article/10.1007/s43465-026-01807-0
60. https://www.perplexity.ai/hub/blog/introducing-perplexity-deep-research (403)
61. https://techcrunch.com/2025/02/15/perplexity-launches-its-own-freemium-deep-research-product/
62. https://artificialanalysis.ai/models/sonar
63. https://parallel.ai/benchmarks (Sept 2026)
64. https://statusgator.com/services/perplexity/api
65. https://thehackernews.com/2026/03/researchers-trick-perplexitys-comet-ai.html
66. https://www.marketingaiinstitute.com/blog/cloudflare-perplexity
67. https://lawsuitsjournal.com/perplexity-ai-lawsuit/ (404 on 2026-09-24 re-check)
68. https://news.ycombinator.com/item?id=45944428
69. https://www.itechguides.com/perplexity-comet-browser-review-2026-is-it-worth-trying/ (2026-08-10)
70. https://llmgateway.io/blog/perplexity-sonar-api-retirement
71. https://ai-watch-blog.vercel.app/en/posts/2026-08-13-perplexity-agent-api-launch/
72. https://www.datastudios.org/post/perplexity-ai-all-available-models-modes-and-how-they-differ-in-late-2025
73. https://www.testingcatalog.com/perplexity-prepares-hybrid-mode-for-computer-on-mac/ (2026-08-31; pre-release, Hybrid mode + Privacy Gate)
74. https://www.perplexity.ai/changelog (consumer changelog; 403 direct, read 2026-09-24 via a text-proxy fetch — entries 05/28/26, 06/18/26, 08/04/26, 08/24/26, 09/21/26)
75. https://en.wikipedia.org/wiki/Perplexity_AI (lawsuit list; launch months)
76. https://en.wikipedia.org/wiki/Comet_(web_browser) (free Oct 2025; iOS 2026-03-18)
77. https://apps.apple.com/us/app/perplexity-ask-anything/id1668000334 (In-App Purchases: Pro $20 / $200, Max $200, credit packs $5–$50; app v26.37.0, read 2026-09-24)
78. https://docs.perplexity.ai/docs/getting-started/integrations/mcp-server (remote MCP: OAuth 2.1 vs Bearer key; bills an API organization at standard API pricing; cannot view balances)
79. https://www.perplexity.ai/hub/legal/perplexity-api-terms-of-service (403 direct; read 2026-09-24 via text proxy — Output display "solely within the Customer Applications"; no training on Customer Content; no SLA)
80. https://status.perplexity.com (Jun–Sep 2026 uptime: API 100%, App 99.95%, Computer 99.65%; no incidents listed)
81. https://pypi.org/project/perplexityai/ (0.43.5, 2026-08-31; Python ≥3.10)
82. https://github.com/perplexityai/perplexity-py/releases (0.39.0 2026-07-02 → 0.43.5 2026-08-31)
83. https://docs.perplexity.ai/docs/resources/feature-roadmap.md (webhooks, developer analytics dashboard still roadmap)
84. https://docs.perplexity.ai/docs/router/routing-and-reliability.md (weighted failover; 429 + Retry-After; no SLA; deployment identity not exposed)
85. https://docs.perplexity.ai/docs/sdk/performance.md (no TTFT figures; batch 5 / 1 s guidance; keepalive defaults)
86. https://www.perplexity.ai/hub/legal/privacy-notice (403 direct; read 2026-09-24 via text proxy — content used to "improve or create services and products, including our AI models"; retention "as long as necessary")
87. https://www.perplexity.ai/help-center/en/articles/10354963-are-third-party-model-providers-training-on-my-data (403 direct and via proxy; snippet via Brave Search 2026-09-24: "No, Perplexity's agreements with third party model providers like OpenAI and Anthropic prohibit using Perplexity data for training their models")
88. https://www.perplexity.ai/help-center/en/articles/11564572-data-collection-at-perplexity (403 direct; snippet: "Strict Zero Data Retention and Zero Data Training agreements with AI providers (OpenAI, Anthropic, and more) prevent training on Enterprise data"; uploaded files retained 7 days on Enterprise)
89. https://joindeleteme.com/ai-privacy-settings/perplexity-ai-opt-out-data-training-guide/ (updated 2026-09-15; opt-out path Account → All settings → Preferences → "AI data retention" off; quotes the third-party no-training clause)
90. https://www.guideflow.com/tutorial/how-to-turn-off-ai-data-retention-in-perplexity (profile → Preferences → "AI data retention" toggle)
91. https://trust.perplexity.ai/subprocessors (read 2026-09-24 via text proxy — Anthropic, OpenAI, Google Cloud, xAI, Amazon Bedrock, AWS, Microsoft Azure, Cloudflare, Datadog, Snowflake, ClickHouse et al.; all US); https://trust.perplexity.ai/faq ("Enterprise customer data is never used to train")
92. https://www.strac.io/blog/perplexity-data-privacy (2026-08-10; "AI data retention" enabled by default on Free/Pro/Max; ~30 d consumer / ~7 d Enterprise retention; Sonar API "deleted after processing")
93. https://openrouter.ai/perplexity/sonar (rendered 2026-09-24 via text proxy — P50 latency 1.45 s, 75 tok/s "best across providers", 3-day uptime 100%, availability 99.98%)
94. https://openrouter.ai/api/v1/models/perplexity/sonar/endpoints (latency/throughput fields null; context 127,072; max completion 114,364; 24 h uptime 99.997%)
95. https://artificialanalysis.ai/models/sonar-reasoning-pro (TTFT and speed N/A; Intelligence Index 12)
96. https://www.cerebras.ai/press-release/cerebras-powers-perplexity-sonar-with-industrys-fastest-ai-inference (2025-02-11; "1,200 tokens per second", Llama 3.3 70B, "available to Perplexity Pro users")
97. https://artificialanalysis.ai/models/gpt-5-6-luna (max effort: TTFT 132.23 s, 122.6 tok/s, $0.20/$1.20)
98. https://artificialanalysis.ai/models/gpt-6-luna (max effort: TTFT 108.47 s, 141.4 tok/s, $0.10/$0.50)
99. https://docs.perplexity.ai/docs/sdk/best-practices.md (semaphore-bounded async concurrency, exponential backoff with jitter on 429, httpx timeouts, API keys in env vars only)

## Verification log (2026-09-24)

**Corrections applied: 12** — 2 major (Agent API GA date attribution; Personal Computer
Mac-only → Mac/Windows + Hybrid compute), 10 minor (Comet free date ×2, GPT-6 Astra/Effort/
Skills in the consumer picker, Deep Research → Opus 4.5 for Max *and* Pro, ToS §5.1 scope,
sandbox 20-min billing-window wording, Max bonus-credit source reconciliation, legacy Tasks
limit, Beri.net/Trellner attribution, Comet review characterisation).

**Missing topics added (16):** Personal Computer for Windows (2026-08-04); Hybrid compute on
Mac (2026-09-21) + Privacy Gate (pre-release, 2026-08-31); GPT-6 Astra, Effort-level selector,
Skills marketplace, Side Chat (2026-09-21); Computer from email + subagent automations
(2026-08-24); Computer in Microsoft 365 (2026-05-28); custom Computer credit limits
(2026-06-18); official Sonar→preset mapping (§1, §7 gotcha 1); `claude-sonnet-4-6`/`-4-5` and
`nvidia/nemotron-3-super-120b-a12b` in the model table; MCP `require_approval` ignored (§2, §7
gotcha 13, §8); preset prompt caching (§4 assumptions, §7 gotcha 14); sandbox in-session search
$0.0025; embeddings context variants; `sonar-reasoning` deprecated 2025-12-15; Reddit + Japanese
newspaper suits (§1, §5); Max Computer spending cap ($200 default → $5,000) replacing the
"unverified top-up" wording in §4.

**Claims re-verified this session (with source):**
- Agent API GA in Feb 2026 changelog; "Sonar Chat Completions is now Agent API" Jul 2026; preset
  caching Aug 2026 (~5%); nemotron-3-super Jun 2026; `sonar-reasoning` removed 2025-12-15 — [27].
- Sonar→preset mapping and "supported until September 27, 2026" — [6].
- `anthropic/claude-sonnet-4-6`/`-4-5` $3/$15, cache $0.30; Opus 5.5 $4/$20 — [2].
- `require_approval` "Ignored. Every MCP tool call auto-runs."; MCP calls free — [12].
- Sandbox $0.03/session, 20-min billing window, ~1 MiB truncation, in-session tools billed at
  standard rates — [11]; $0.0025 per in-session search and all four embeddings prices — [1].
- ToS last updated 2026-01-23; §5.1 personal/non-commercial applies to all users; §5.2(i)
  robot/scraper ban — [42] (via text proxy).
- Consumer changelog dates 05/28, 06/18, 08/04, 08/24, 09/21 — [74] (via text proxy).
- Comet free Oct 2025, iOS 2026-03-18 — [76]; Computer Feb 2026, Personal Computer Apr 2026,
  Yomiuri 2025-08-08, Asahi/Nikkei Aug 2025, Reddit Oct 2025 — [75].
- Max spending cap $200 default, adjustable to $5,000; 35,000 bonus; Pro $20 / Max $200 /
  Enterprise $40 / $325 — [34]; Windows Personal Computer "for Pro and Max on August 4",
  M365 2026-05-28, email trigger 2026-08-24 — [48].
- Hybrid mode local model sizes and Privacy Gate description — [73] (pre-release article).

**Stale / unverified flags left in place (13):** Personal Computer Accessibility + Full Disk
Access; Personal Computer tier as of Sept 2026; Computer 2026-02-25 and Personal Computer
2026-03-11 day-level dates; Portable Computer "Linux only"; scope of the May 2026 Pro-search cut;
Agent API image attachments; SimpleQA 93.9%; malicious Chrome extension (Microsoft, Jun 2026);
CNN / NYT / Chicago Tribune suit dates; Max annual / Enterprise prices vs Perplexity's own page (headline Pro/Max now verified [77]);
"no official CLI"; Opus 5.5 via Perplexity vs Anthropic list price (Sept 25 vs 27 cutover:
resolved, see gap-fill pass).
Also still open: price of `nvidia/nemotron-3-super-120b-a12b` (not captured), the $2,000
spending-cap figure the fact-checker saw (not located), and whether every Hybrid-mode piece from
the 2026-08-31 preview shipped on 2026-09-21.

**Gap-fill pass (2026-09-24, second session):** consumer headline prices verified first-party via
App Store IAP [77]; Personal Computer tier triangulated to Pro+Max (Mac 05-10, Windows 08-04; still
secondary [44][48]); Sonar cutover resolved to 2026-09-27 (Perplexity [6]) with 09-25 attributed
to llmgateway's own routing [70]; MCP OAuth confirmed to bill an API org, not the consumer plan
[78]; added per-lane data-handling matrix, progress-visibility, third-party-serving, normalized
reliability, chat-latency, tool-churn bullets (§3) and a calibrated two-lane fit scorecard (§8).
Still unverified: Personal Computer tier from a Perplexity page (all first-party pages 403/404);
DPA / sub-processor list (404); consumer training opt-out toggle (not in the privacy notice text);
any numeric TTFT. WebSearch budget was exhausted this session; all new facts come from direct fetches.

**Gap-fill pass 3 (2026-09-24, third session; WebSearch budget exhausted — Brave/Bing result
pages and direct fetches only):** chat latency now number-backed for `sonar` (OpenRouter P50
1.45 s / 75 tok/s [93]; Cerebras 1,200 tok/s historical [96]; preset upper bounds from the
underlying OpenAI models [97][98]); Personal Computer tier upgraded to a direct AppleInsider
quote ("all Perplexity Pro, Max, and Enterprise subscribers using a Mac" [44]) though still
secondary — perplexity.ai/pricing, /computer, help center and web.archive.org all unreachable;
consumer training opt-out located ("AI data retention" toggle, on by default for Free/Pro/Max
[89][90][92]); upstream pass-through partly resolved — sub-processor list names Anthropic/
OpenAI/Google/xAI/Bedrock/Azure [91], help center says upstream labs may not train [87], but
upstream ZDR is stated only for Enterprise [88], so thesis routing through `anthropic/*`/
`openai/*` stays "no-training, retention-unconfirmed". Cross-doc dimensions added to §3:
concurrency (no cap; org-wide QPS window [8][99]), credential lifecycle, prompt-injection
posture, progress-visibility sink + host footprint (zero daemons), calibration caveat, reviewer
independence. Still open: numeric TTFT for `fast`/`low`/`medium` presets; Perplexity-first-party
tier statement; upstream retention terms for the API-key lane; help-center article bodies
(403) beyond their search snippets.

**Fact-checker overall quality rating:** good.
