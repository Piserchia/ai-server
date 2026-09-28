# Z.ai GLM (Zhipu) — research (as of 2026-09-24)

Method note: this session's web-search budget was exhausted before this task started, so
everything below comes from direct fetches of primary pages (docs.z.ai, Hugging Face, Z.ai
legal pages), the Hacker News Algolia API, Artificial Analysis, Arena, Simon Willison's GLM
tag, Wikipedia and the Claude Code gateway docs. Reddit and X were unreachable from this
environment (fetch blocked); community sentiment is therefore HN-weighted. Several Z.ai
marketing pages (z.ai/subscribe, z.ai/pricing, z.ai/blog/*) are JS-rendered and returned
only navigation, so tier prices come from the docs "transition" page, not the live checkout.
A verification pass on 2026-09-24 (see the log at the end) re-fetched docs.z.ai, OpenRouter's
models API, The Register, GitHub, HN Algolia and the Claude Code gateway docs; corrections and
additions from that pass are folded into the sections below. A second gap-fill pass later on
2026-09-24 (web search budget again exhausted; fetch-only) re-probed z.ai/subscribe, z.ai/pricing,
r.jina.ai and the Wayback API for live checkout prices (all still JS-only / not archived), the Z.ai
OpenAPI spec, error-code table, DPA/privacy pages, The Register, the OpenRouter endpoints API, npm,
PyPI, GitHub and HN Algolia; its results are marked "(gap-fill 2026-09-24)" and tabulated in §3
under the five cross-doc dimensions (data handling, progress visibility, third-party serving,
reliability, latency, tool churn) plus the calibrated scorecard in §8. A third pass on 2026-09-24
(search budget exhausted again; fetch-only, ~30 fetches) targeted the six residual gaps (checkout
prices, JSON on 5.3, rate limits, 2×-vs-3× off-peak, DPA scope of Coding Plan traffic, status
page) and the eight cross-doc dimensions; its results are marked "(pass 3)" and collected in §3
under "Cross-doc dimensions (pass 3)" and in the log at the end.

## 1. Snapshot

**Company.** Z.ai is the international brand of Zhipu AI (Beijing, founded 2019 as a
Tsinghua spin-out by Jie Tang and Li Juanzi). Listed on the Hong Kong Stock Exchange on
2026-01-08 (ticker 2513), "China's first major LLM company" to IPO; market cap reported at
~$62B in Aug 2026 [39]. Added to the U.S. Commerce Department Entity List in January 2025
[39]. The international service entity is JINGSHENG HENGXING TECHNOLOGY PTE. LTD, Singapore;
data is "generally processed in Singapore" [31]. Terms are governed by Singapore law with
SIAC arbitration [30].

**Current lineup (API model IDs, per docs.z.ai pricing page and model pages):**

| Model ID | Params (total/active) | Context / max out | Modalities | Notes |
|---|---|---|---|---|
| `glm-5.3` | 753B MoE [34] | 1M ctx / 128K out [18] (HF card evals cap at 300K [34]; OpenRouter lists 1.3M [53]) | text→text | Flagship; reasoning always on, `reasoning_effort` low/high/max [18]; open weights under custom "GLM-5.3 License" [35] |
| `glm-5.3-prime` | same as 5.3 (inference-accelerated) [63] | 1M ctx [63] | text→text | "high-speed variant of GLM-5.3 … 1.5–2× the output throughput"; listed on OpenRouter 2026-09-23 at $2.80/$8.80 [63]; not on docs.z.ai pricing/model pages as of 2026-09-24 — native api.z.ai availability unverified as of 2026-09-24 |
| `glm-5.3-flash` | 320B / 18B [36] | 1M / 128K [19] (HF card: 300K ctx / 163,840 max generation, eval settings, tagged image-text-to-text [36]; which applies on the hosted API is unverified as of 2026-09-24) | video, image, text, file → text [19] | "first natively multimodal model in the GLM-5 series"; MIT [36]; thinking cannot be disabled [19] |
| `glm-5.3-flashx` | same weights, faster serving | 1M / 128K [19] | same | "200 tokens/second" serving tier [19]; not yet on Coding Plan [19] |
| `glm-5.2` | 753B / ~40B [33][49] | 1M / 128K [20] | text | June 2026 flagship; open weights MIT [49] |
| `glm-5.1` | 754B [49] | 200K [49] | text | April 2026; MIT [49] |
| `glm-5` | 744B / 40B [21] | 200K / 128K [21] | text | Feb 2026 |
| `glm-4.7`, `glm-4.7-flashx` | 368B (4.7) [49]; Flash 30B-A3B [37] | 200K / 128K [22] | text | `glm-4.7-flash` is FREE on API [1] and MIT [37] |
| `glm-4.6v`, `glm-4.6v-flash`, `glm-ocr` | — | — | vision | 4.6V-Flash free [1] |
| `glm-4.5-air` (106B/12B), `glm-4.5-flash` (free) | [49][1] | 128K [49] | text | legacy but still priced |

**Knowledge cutoffs:** Not found — searched: docs.z.ai model pages for glm-5.3 / glm-5.3-flash /
glm-5.2 / glm-5 / glm-4.7, Hugging Face cards for GLM-5.3, GLM-5.3-Flash(-BF16), GLM-4.7-Flash,
docs.z.ai pricing page. Z.ai does not publish cutoffs on any of those pages.

**Release cadence** (roughly every 6–8 weeks for a flagship point release): GLM-4.5 2025-07-28
[49]; GLM-4.6 2025-10-01 [49]; GLM-4.7 2025-12-22 [44]; GLM-5 2026-02-11 [44] (Wikipedia says 2026-02-12 — one-day discrepancy, likely timezone; unverified as of 2026-09-24); GLM-5.1
2026-04-07 (API prices +10% same day) [39][44]; GLM-5.2 2026-06-16 (1M context) [44]; GLM-5.3
2026-08-14, weights 2026-08-28 [44]; GLM-5.3-Flash 2026-08-26 [44] (pre-tested as the stealth model **"Ox Alpha"** on OpenRouter and
OpenCode from 2026-08-20, unmasked by the community and confirmed by Z.ai on 2026-08-26 — HN 435
points [64][65]; this stealth-then-confirm pattern is how Z.ai now trials models); GLM-5.3-FlashX
2026-09-18 [44]; GLM-5.3-Prime 2026-09-23 (OpenRouter listing only) [63]. Older Coding Plan model names (5.2, 5.1, 4.7) are "automatically routed" to newer
versions [2].

**Positioning.** Z.ai sells itself as the open-weight frontier coding/agent lab: every flagship
since GLM-4.5 ships weights (MIT until 5.2; a custom licence with a $10B-revenue
security-review clause for 5.3 [35]), and its commercial product is a flat-rate "GLM Coding
Plan" that plugs into Claude Code, Codex, OpenCode and a dozen other harnesses via
Anthropic- and OpenAI-compatible endpoints [10]. Benchmarks and Arena place GLM-5.3 just
behind the Anthropic/OpenAI/Google frontier (Arena text #19 at 1483 vs Claude Fable 5 at 1506
[42]; Artificial Analysis Intelligence Index 45, "#2 of 113" in its class [40]), at roughly
one-third to one-fifth of frontier API prices [1]. Reliability under load and Chinese-entity
data-governance concerns are the recurring caveats [48][46] — sharpened on 2026-09-18 by the
**ZCode repository-upload incident** (ZCode silently uploaded users' whole repos to Alibaba Cloud;
feature disabled, apology, ZCode open-sourced Apache-2.0 on 2026-09-21/22 — details in §3
Reliability and §5 Governance [60][61][62]).

## 2. Interfaces & surfaces

- **Consumer app:** chat.z.ai — "Advanced AI Chatbot & Agent powered by GLM-5.3-Flash",
  with a "Deep Think Max" mode and template builders (landing pages, mini games, 3D, blogs)
  [54]. Consumer plan prices: Not found — searched: chat.z.ai, z.ai (redirects to chat),
  docs.z.ai/help/faq (unverified as of 2026-09-24). Mobile/desktop consumer chat apps: Not found
  (same searches; unverified as of 2026-09-24) — the consumer surface remains the thinnest part of
  this doc; the only Z.ai-built end-user apps confirmed are AutoClaw (desktop/mobile agent, below)
  and ZCode. Wikipedia lists
  AutoGLM (voice-driven phone agent) and ZCode (coding IDE, launched 2026-07-02) [39]; an
  "AutoClaw" agent product is referenced in the Flash promo page [12] — correction: it does have a
  docs page (docs.z.ai/devpack/tool/autoclaw, "1.5× usage quota throughout the day" for Coding
  Plan users [58]), a product site (autoclaw.z.ai: desktop agent with browser automation, office
  automation and WhatsApp/Telegram/Discord/Lark integration; 200M free tokens "valued at $24" on
  signup [59]) and HN stories (autoclaw.z.ai 2026-07-29; autoglm.z.ai/autoclaw 2026-03-30).
- **Browser/OS integrations, voice:** Not found — searched: docs.z.ai/llms.txt (no
  browser-extension, desktop or voice-mode pages); only `glm-asr-2512` speech-to-text API
  ($0.03/MTok) exists [1].
- **CLI / agentic coding tools:** own tool **ZCode** (Coding Plan; 1.5× quota; open-sourced under Apache-2.0 at
  github.com/zai-org/ZCode on 2026-09-21 after the repo-upload incident — see §5 Governance [62])
  plus 16 officially
  supported third-party harnesses: ZCode, Claude Code, Claude for IDE, Codex, OpenCode, Pi,
  Cursor, Cline, TRAE, Qoder, Droid, Kilo Code, Roo Code, Crush, Goose, Eigent [10]; plus four
  "general-purpose agent tools" that are also officially supported (served best-effort, may be
  rate-limited under load): AutoClaw (1.5× usage), OpenClaw, Hermes Agent, SillyTavern [10] — 20
  supported tools in total. ZCode and AutoClaw are labelled "1.5× Usage" (same work consumes ~67%
  of standard quota) [10][58]. OpenClaw (open-source, multi-platform local assistant) is the one
  most relevant to a Telegram-bot server, since it is an officially supported client rather than
  a coding harness.
  `npx @z_ai/coding-helper` interactive wizard configures Claude Code, Codex, OpenCode,
  Crush and Droid [14].
- **API + SDKs:** native/OpenAI-compatible base `https://api.z.ai/api/paas/v4/`; official
  Python `zai-sdk` and Java `ai.z.openapi:zai-sdk`; OpenAI Python/Node/Java SDKs work by
  pointing base_url at Z.ai [23][24]. LangChain integration page exists [32].
- **Compatible endpoints (Coding Plan):** Anthropic Messages `https://api.z.ai/api/anthropic`;
  OpenAI Chat Completions `https://api.z.ai/api/coding/paas/v4`; OpenAI Responses (Codex)
  `https://api.z.ai/api/v1` [10][8].
- **MCP:** Z.ai hosts remote MCP servers for Coding Plan users: Web Search Prime
  (`https://api.z.ai/api/mcp/web_search_prime/mcp`) [15], Web Reader, Zread (GitHub repo
  docs/structure/file reading, `https://api.z.ai/api/mcp/zread/mcp`) [17], and a Vision MCP
  with 8 tools (`ui_to_artifact`, `extract_text_from_screenshot`, `diagnose_error_screenshot`,
  `analyze_data_visualization`, `video_analysis` up to 8 MB, etc.) [16]. GLM-5.3 itself is
  benchmarked on MCP-Atlas [21].
- **Batch API:** Not found — searched: docs.z.ai/llms.txt for "batch" (no page); pricing page
  has no batch column [1]. Treat as unavailable on Z.ai's own API. OpenRouter does list
  third-party batch variants `z-ai/glm-5.3:batch` ($0.45 in / $2.00 out per 1M) and
  `z-ai/glm-5.3-flash:batch` ($0.06 / $0.20) as of 2026-09-24, plus 60–70% promo pricing on the
  non-batch routes ($0.5614/$1.764 for 5.3; $0.045/$0.14 for Flash) [63] (the raw models API
  returns list $1.40/$4.40 and $0.15/$0.50; the discounted figures appear on the model pages).
- **Structured outputs:** `response_format={"type":"json_object"}` with the schema described
  in the system prompt (no `json_schema` mode documented); listed for glm-5/4.7/4.6/4.5 and
  stated as supported on 5.3 and 5.3-Flash on the model pages [18][19] — the struct-output page
  itself lists only glm-5 / 4.7 / 4.6 / 4.5, so JSON-mode support on the 5.3 models is unverified
  as of 2026-09-24 [25]. (Gap-fill 2026-09-24, still unverified on api.z.ai:) the model pages say
  only "Supports structured output formats such as JSON" with no parameter reference [18][19];
  OpenRouter's per-endpoint capability listing shows `response_format`/`structured_outputs`
  advertised by most third-party hosts of the open weights (DeepInfra, Fireworks, Together,
  Cloudflare, …) but **not by the Z.AI first-party endpoint** for glm-5.3-flash [66][67]. Working
  rule: for anything that must parse, either pin the JSON lane to the documented models
  (`glm-4.7-flash` free / `glm-5`) [25], or route 5.3 through an OpenRouter provider that lists
  `structured_outputs`, and validate output with a schema check regardless. **(Pass 3, partial
  reversal:)** re-fetched on 2026-09-24 the OpenRouter endpoints API now lists `response_format`
  in `supported_parameters` for the **Z.AI first-party endpoint of both `glm-5.3` and
  `glm-5.3-flash`** (`reasoning, include_reasoning, max_tokens, temperature, top_p, tools,
  tool_choice, top_k, response_format, reasoning_effort`), but still **not** `structured_outputs`
  [66][67] — i.e. `json_object` mode is advertised through Z.ai's own serving, `json_schema`
  strict mode is not. The struct-output page itself still names only glm-5 / 4.7 / 4.6 / 4.5 and
  only `{"type":"json_object"}` [25], and the glm-5.3 model page still says only "Supports
  structured output formats such as JSON" [18]. Status: **json_object on 5.3 = likely (vendor
  endpoint advertises it, docs silent); json_schema on any GLM = not offered.** Keep the schema
  validator; the "pin to documented models" rule can relax once one live `response_format` call
  on api.z.ai succeeds — a 30-second probe the owner can run with the cheap-lane sketch in §7.
- **Tool use:** OpenAI-style `tools`/`tool_calls`; `tool_choice` "only supports `auto`" [26].
  Streaming and context caching supported on 5.x [18][19].
- **Computer-use / browser agent:** no hosted CUA product found; the Vision MCP covers
  screenshot understanding only [16]. AutoGLM (phone agent) is China-market [39].
- **Scheduled/automated tasks, memory, projects/workspaces:** Not found on docs.z.ai — searched
  llms.txt index; the only "memory" page is a Coding-Plan best-practices note on session
  memory [32]. No cron/"tasks" feature in the consumer app was reachable.
- **Hosted agents API:** `POST https://api.z.ai/api/v1/agents` with `general_translation`,
  `slides_glm_agent`, `vidu_template_agent` (async) [29].
- **Messaging integrations (Telegram/Slack/WhatsApp/Discord):** Not found — searched llms.txt;
  none listed for the API itself. However Z.ai's own AutoClaw ("An AI agent for Work",
  autoclaw.z.ai; desktop app for Windows 10+/macOS, iOS/Android listed) advertises IM integration
  with "WhatsApp, Telegram, Discord, Lark, and other IM platforms", browser/office automation and
  50+ built-in skills, and is an officially supported Coding Plan tool with 1.5× quota; OpenClaw
  (open-source, multi-platform local assistant) is also officially supported [10][58][59]. For a
  bring-your-own-bot server these are optional; the API has no first-party Telegram/Slack bot.
- **IDE plugins:** via the supported-tool list (Claude for IDE, Cline, Kilo, Roo, Cursor, TRAE,
  Qoder) rather than a first-party plugin [10].

## 3. Headless / server automation fit

- **Auth modes.** API key only. Pay-as-you-go keys and Coding Plan keys are both bearer
  tokens created in the console (`z.ai/manage-apikey/apikey-list`); the Team Plan key "is not
  interchangeable with other Z.AI's API Keys" [23]. No OAuth device login, no subscription
  sign-in flow — the Coding Plan is *itself* a key-based product, which is the whole reason it
  slots into headless harnesses.
- **May a subscription be used programmatically?** Partly, and this is the key policy risk:
  - "The GLM Coding Plan is strictly limited to use within officially supported tools and
    products" and "API calls outside the plan are not available" [4].
  - Subscription terms: "If the system detects usage through unauthorized or unsupported tools
    (such as SDK-based access or other third-party integrations), some subscription benefits
    may be restricted" [6]. Enforcement is escalating: "rate limiting, account freezing, or
    other restrictions. Accounts with more than three violations may be banned" [5].
  - Licensed "only to the individual natural person associated with such account"; sharing,
    proxying, resale and "bulk or automated usage on behalf of others" are prohibited [6].
  - Nothing in the FAQ, usage policy or subscription terms prohibits *headless* or
    non-interactive use of a supported tool (e.g. `claude -p` or the Agent SDK, which spawns
    the Claude Code binary [52]). But the SDK path is exactly the ambiguous "SDK-based access"
    phrase, and the doc set never defines how "supported tool" is detected (user-agent?
    endpoint?). Treat single-tenant, single-person automation through Claude Code as
    grey-but-defensible; treat anything that looks like multi-user or resale as banned.
  - Z.ai's general Terms prohibit "social bots, spiders, or other automated means to access
    this service" — that clause targets the consumer site, not the API, but note it [30].
- **Rate limits / caps.** API pay-as-you-go limits live behind a login-gated console page
  (`z.ai/manage-apikey/rate-limits`, the docs link redirects there); numbers: Not found —
  searched docs.z.ai/api-reference/rate-limit (307 redirect), guides/overview/*, help/faq
  (unverified as of 2026-09-24; free-model limits likewise). Gap-fill 2026-09-24: the docs'
  "concepts" page only says concurrency "is set by the platform" and "different users or
  subscription plans may have varying concurrency quotas" [68]; the OpenAPI spec exposes no
  limits endpoint [69]; the usage policy's only sizing guidance is Lite "single project at a
  time", Pro "1–2 projects simultaneously", Max "2 or more" [5] — read that as a de-facto
  concurrency of ~1 Lite session. The **error-code table** is the one programmatic contract:
  HTTP 429 with body codes 1302 (request rate), 1305 (overloaded), 1308 (usage threshold, reset
  time given), 1313 (Fair Usage Policy throttle), 1316 (5-hour limit reached), 1317 (7-day limit
  reached), 1318–1321 (window exhausted + monthly spend cap), 1113 (insufficient balance) [70] —
  the router should key its backoff/breaker on these codes, not on the 429 alone.
  Coding Plan caps are credit-based (table in §4): Lite 2,000 credits per rolling 5 h and
  10,000 per 7 days; Pro 12,000 / 60,000; Max 28,000 / 140,000 [2]. Credits =
  (input×mult + cached×mult + output×mult)/10,000 with GLM-5.3 multipliers 6.9 / 1.7 / 24 and
  GLM-5.3-Flash 2.3 / 0.56 / 8 [2]. Off-peak = 50% of the standard rate; **peak is only
  Mon–Fri 14:00–18:00 Singapore time (06:00–10:00 UTC, 02:00–06:00 ET)** [2] — almost every
  US-daytime and overnight job is off-peak. **(Conflict resolved, pass 3:)** the usage-revision
  notice's "1× during off-peak hours and 3× during peak hours" (GLM-5.3) and "0.4× off-peak /
  1.2× peak" (Flash) are explicitly the multipliers for **legacy (prompt-based) plans** migrated
  on 2026-07-30 [11]; the current credit plans use the overview's "50% of the standard credit
  rate" off-peak, i.e. a 2× peak:off-peak ratio [2]. The two pages describe two different plan
  generations, not one plan twice; a new buyer is on the 2× ratio. The same notice adds that
  "existing active subscriptions" get weekends "deducted at off-peak rates all day" [11] — treat
  as legacy-only until seen on the dashboard. Concurrency is the other quota axis: the usage
  policy states plan users receive "higher concurrency limits during off-peak hours (dynamically
  increased)" and that the platform "dynamically adjusts these limits based on resource
  availability" (Max > Pro > Lite) [5]; the Team Plan page repeats "rate limits and concurrency
  limits are related to your plan tier, and the platform dynamically adjusts them" [13]. No
  number is published anywhere (pass 3 re-checked the FAQ, pricing page, API introduction,
  concept page and llms.txt index [4][1][24][68][32]; `z.ai/manage-apikey/rate-limits` is a login
  wall [82]). **Promo:** 2026-09-25 → 2026-10-07 "all-day
  usage will be charged at the off-peak rate" — every hour at 50% of the standard credit rate [2].
- **Sandboxing.** None provided by Z.ai; the harness (Claude Code, Codex, OpenCode) supplies
  it. Z.ai's GLM-5.3 launch emphasises "emergent cyber capabilities" (2,436 vulns found in
  269 OSS projects) [43] — treat outputs from adversarial/security prompts with the same
  guards as any model.
- **Structured event output for orchestration.** Not a Z.ai feature; comes from the harness.
  Claude Code `-p --output-format stream-json` works unchanged because the Anthropic-compat
  endpoint speaks the Messages protocol [7][52]. Native API: OpenAI-style SSE streaming
  (`stream: true`) [24].
- **Session resume.** Harness-level (Claude Code / SDK sessions). Z.ai's API is stateless;
  context caching is automatic ("identifying content that is identical or highly similar to
  previous requests"), cached tokens billed at "usually 50% of standard price" (cache page,
  re-read pass 3; TTL unstated — "will recalculate after expiration") / $0.26 vs $1.40
  for 5.3 on the price list (18.6%) / 81% discount per AA [27][1][40] — three figures that do not
  agree; trust the price list.
- **Streaming.** Yes on all chat models [18][19][24].
- **Reliability.** No public status page exists: status.z.ai re-probed 2026-09-24 → DNS
  `ENOTFOUND`; StatusGator has no Z.ai service page (404) [71][72]; pass 3 also tried z.ai/status
  (404), statusgator.com/services/zhipu-ai (404), isdown.app/status/z-ai (403) and the llms.txt
  index (no status/incident/uptime entry) [83][32] — **closed: there is no status page; the only
  live health signal is OpenRouter's first-party endpoint uptime** (2026-09-24 30-min window:
  Z.AI glm-5.3 99.92%, Z.AI glm-5.3-flash 99.07%) [66][67], which the breaker can poll for free
  as a pre-dispatch check. No priority or SLA tier is
  sold on the API or Coding Plan (pricing page, overview, team plan: none) [1][2][13]. The only
  normalized external signal is OpenRouter's per-provider uptime for the open weights: on
  2026-09-24 the Z.ai-hosted glm-5.3 endpoints were not separately broken out in the sampled
  window, while the third-party hosts ranged 99.0–100% (Alibaba, Novita, Io Net, Sail) down to
  64–81% (Venice, Decart, AtlasCloud) over the last 30 min / 1 day [66][67] — i.e. the open
  weights let you fail over to another host at will, which is the practical reliability story
  for this lane. Common-window incident count (2026-06-25 → 09-24, 90 days, source = HN
  Algolia comments): 0 outage/overload comments matched, vs the April-2026 "Discord is filled …
  with people experiencing capacity issues" wave [73][74]; treat as "no counted incidents, no
  counting instrument" rather than as clean. **ZCode incident:** on 2026-09-18 ZCode's
  Repository Index/Repo Wiki feature was found uploading whole user workspaces to Alibaba Cloud;
  Reuters 2026-09-21 reported Z.ai disabled the feature; 2026-09-22 apology, data deletion
  audited by CAICT/NSFOCUS, ZCode open-sourced (Apache-2.0, v3.14.3 2026-09-23) [60][61][62].
  Operationally: a first-party client shipped an undisclosed exfiltration path and the fix history
  was wiped — pin client versions and audit outbound traffic of any Z.ai tool. Known
  incidents: a late-Feb-2026 compute shortage severe enough that shares fell 23% and new
  registrations were restricted [39]; HN users in Aug 2026: "APIs are hammered now, so service
  is bumpy" (Frannky) [48]; the Ox Alpha stealth test (2026-08-20 → 08-26) was also Z.ai's
  load/feedback rehearsal for the Flash launch [64][65]; Artificial Analysis measured GLM-5.3 at 58.8 tok/s with 3.37 s
  TTFT, and Flash at 42.8 tok/s / 3.49 s — slower than median [40][41].
- **Data-handling matrix (gap-fill 2026-09-24)** — per lane and auth mode, from the privacy
  policy / DPA [31], terms [30], subscription terms [6] and, for the comparison row, Claude
  Code's data-usage page [75]:

  | Lane / auth | Training use | Retention | Residency | ZDR / opt-out |
  |---|---|---|---|---|
  | Z.ai API, pay-as-you-go key | "We will not use End User Content to develop or improve Services, unless you explicitly agree" [30] | DPA: content "is processed in real-time … and is not saved on our servers"; other data deleted after termination [31] | "generally processed in Singapore"; may be transferred cross-border "with appropriate safeguards" [31] | No ZDR product — the DPA's no-storage claim is the whole offer; no enterprise retention knob found |
  | Z.ai Coding Plan key (Claude Code / Agent SDK) | Same API rule (the plan is an API product) — but no plan-specific DPA text; still unverified as of 2026-09-24 (pass 3) whether Coding Plan traffic is "API Services" under the DPA: the privacy-policy page *is* the "Data Processing Addendum for API Services" and never defines the term or names Coding Plan / Developer Pack; docs.z.ai/legal/dpa is 404; the subscription terms and FAQ say nothing about storage or training [31][6][4]. Nearest plan-family statement: the Team Plan page says "Code, prompts, conversations, and related content are excluded from model training by default" [13] — a training exclusion, not a no-storage claim, and for Team seats | Same as API (assumed) | Singapore | None; ZCode client uploads (not the API) showed the client side can bypass this [60] |
  | chat.z.ai consumer | Content "may be used to develop and improve our machine learning" [30] | "as long as needed to provide our Services" [31] | Singapore | Delete conversations/account only |
  | Claude Max lane (Claude Code / Agent SDK on subscription OAuth) — *comparison row* | Consumer plan: trained on **only if the account's "improve models" setting is on**, "including when you use Claude Code from these accounts" [75] | 5 years if opted in, 30 days if opted out; local transcripts 30 days (`cleanupPeriodDays`) [75] | Anthropic API infrastructure (US), AES-256 at rest [75] | ZDR is Enterprise-only, not Max; opt-out via claude.ai/settings/data-privacy-controls [75] |

  Consequence for the paper-trading lab: proprietary theses can go down the Z.ai *API* lane
  under the "not saved / not trained" DPA wording (Entity-List vendor caveat stands), and down
  the Claude Max lane only with the training toggle verified off; neither lane has ZDR.
- **Progress-visibility plumbing (gap-fill 2026-09-24).** No programmatic quota/usage
  introspection: the OpenAPI spec has no usage, balance, quota or limits path [69]; remaining
  5-hour/weekly credits are visible only on the login-gated dashboards
  `z.ai/manage-apikey/subscription` (quota progress) and `z.ai/manage-apikey/billing` (tokens per
  charge type, tool calls) [4][2]. What is programmatic: per-response `usage` fields
  (`prompt_tokens`/`completion_tokens`, cached tokens) [69], and the 429 body codes 1316/1317
  (5-h / 7-day exhausted) which carry a reset time [70]. No telemetry export, no OTEL, no webhooks.
  Compare Claude Code on the Max lane: `/usage` (TUI only) plus OTEL metrics export [75] — so on
  the GLM lane the server must **compute credits itself** from the published multipliers [2] and
  the response usage fields, and treat 1316/1317 as the ground truth.
- **Third-party-serving permission (gap-fill 2026-09-24).** Coding Plan: outputs may be
  consumed only by the subscriber — "directly invoking model APIs from your own applications,
  bots, websites, SaaS products or other systems" is prohibited without a separate written
  agreement, as is letting "customers or any organization" use the quota [6]. Pay-as-you-go
  API: explicitly permitted "to integrate the Services into your applications or to develop
  downstream systems, applications or functions to your end users", on condition that you
  "truthfully and accurately disclose the use of models from the Z.ai" and take responsibility
  for end-user terms [30]. Consumer chat: no bots/automated access [30]. Matrix row: **pickem
  dashboard / shared project sites → API key only, with a "powered by GLM" disclosure; Coding
  Plan → owner-only jobs.**
- **Interactive-surface latency (gap-fill 2026-09-24).** Artificial Analysis 2026-09-24:
  GLM-5.3 (max) TTFT 3.45 s, 60.0 tok/s (open-weight medians 2.39 s / 67.1 tok/s); GLM-5.3-Flash
  TTFT 3.67 s, 42.8 tok/s [40][41]; FlashX is sold at "200 tokens/s" (vendor claim, no
  independent TTFT) [19]. Telegram round-trip rating: a 300-token reply ≈ 3.5 s + 5 s ≈ 8–9 s on
  5.3, ≈ 3.7 s + 7 s ≈ 11 s on Flash, ≈ 5 s on FlashX if the claim holds — **acceptable for an
  async bot with a typing indicator, not for "instant" replies**; thinking cannot be disabled on
  either model, so `reasoning_effort: low` is the only lever [18][19].
- **Cost-of-ownership from tool churn (gap-fill 2026-09-24).** `@z_ai/coding-helper` (npm): 5
  releases 2026-08-10 → 08-27, now 0.1.1, none since [76]; `zai-sdk` (PyPI): 0.2.3 on
  2026-06-16, 0 releases in the last 90 days [77]; ZCode on GitHub: history wiped, 3 commits and
  a single release v3.14.3 (2026-09-24) since open-sourcing [62][78]. The lane itself has no
  SDK of ours to break — the churn burden is Claude Code's (the gateway path is unsupported by
  Anthropic [50]; every Claude Code upgrade is a regression test for the GLM env) plus Z.ai's
  model-ID/pricing churn (four Max-plan variants in a year [47], prompt→credit migration 07-30
  [11], +10% API 04-07 [39]). Burden rating: **medium** — lower than Antigravity/Codex weekly
  release trains, higher than a plain OpenAI-compatible API key because of the harness coupling.

### Cross-doc dimensions (pass 3, 2026-09-24)

These are the eight cross-document gaps the matrix flagged, answered for the Z.ai lane only.

1. **Concurrency per lane on subscription auth.** Published guidance is qualitative: Lite "single
   project at a time", Pro "1–2 projects simultaneously", Max "2 or more", plus "higher
   concurrency limits during off-peak hours (dynamically increased)" [5]; Team seats Standard
   "1–2 concurrent development projects", Premium "2+" [13]; numeric API concurrency is "set by
   the platform … different users or subscription plans may have different concurrency quotas"
   and over-limit requests "may fail or need to wait in queue" [68]. **Design value for the
   scheduler: Lite = 1 headless session, Pro = 2, Max = 3 (conservative), with the fan-out
   allowed to rise off-peak; the over-limit signal is a 429 body code 1302/1305 (retry) rather
   than a documented queue** [70]. Measure the real ceiling on day 1 by launching N parallel
   `claude -p` probes and recording the first 1302.
2. **Credential lifecycle on a headless box.** The lane is a static bearer key, not OAuth: no
   TTL, no refresh, no browser step, no device flow; the API introduction says only that keys are
   created/managed at `z.ai/manage-apikey/apikey-list` and documents no expiry, rotation or
   scoping [24][23]. Consequence: nothing expires on its own — the failure modes are (a) balance
   exhaustion (429 code 1113), (b) plan quota windows (1316/1317), (c) subscription lapse at the
   monthly renewal (cancel ≥3 days before; charged bonus → cash → card) [5][70], and (d) manual
   revocation after a leak. Storage: plaintext in the runner's env file (`ZAI_CODING_KEY`,
   `ZAI_API_KEY`, §7) or macOS Keychain via the existing secret loader — same posture as any
   OpenAI-compatible key; the three key types (pay-as-you-go, Coding Plan, Team) are not
   interchangeable and must be stored as three secrets [23]. Alarm to add: a renewal-date
   reminder 4 days before the billing date (the 3-day cancel rule) and a 1113/1316/1317 counter.
3. **Progress-visibility sink.** Emitter side: per-response `usage` (prompt/completion/cached
   tokens) and 429 bodies with reset times; no usage endpoint, no OTEL, no webhooks [69][70].
   Collector side for this lane needs nothing new: the Claude Code harness already emits
   `stream-json` envelopes the runner parses, so the GLM lane's events land in the same
   audit_log JSONL as the Anthropic lane. What is missing is one derived series —
   `credits_used = (in×6.9 + cached×1.7 + out×24)/10,000` (5.3) or `(in×2.3 + cached×0.56 +
   out×8)/10,000` (Flash), halved off-peak [2] — accumulated per rolling 5 h and 7 d, and
   `credits_remaining = tier_cap − used`, which is the number the web dashboard should show.
   Ground truth is only the login-gated dashboard [4]; reconcile by hand weekly. A common
   cross-lane event schema needs at minimum `{lane, model, in, cached, out, cost_native_units,
   cost_usd_equiv, window_reset_at}`; for Z.ai `cost_native_units` = credits and `window_reset_at`
   comes from the 1316/1317 body when present. No Prometheus/Grafana/Langfuse daemon is required
   for this lane.
4. **Empirical calibration against this server.** This pass could not read
   `volumes/audit_log` (out of scope for the task), so the 150k-in / 15k-out synthetic job stands
   here with **0% cache** as the worst case; the cache page says hits are "usually 50%" off, the
   price list 81% off [27][1], so at 70% cache-hit share a 5.3 API job is $0.276 → ≈$0.15
   (price-list rate) and a Coding-Plan job 139.5 → ≈76 credits (multiplier 1.7 vs 6.9 on the
   cached share). The verdict is insensitive to the cache assumption at ≤100 jobs/month (Lite
   $18 wins vs $28 API on 5.3 either way; API Flash at $3 wins on cost alone but not on quality)
   and flips only above ~600 Flash-equivalent jobs/month. Owner inputs still needed: real
   jobs/month, tokens/job and cache share from the audit log, and the current Claude Max tier —
   none of which changes the Z.ai lane's recommendation, only the share of work routed to it.
5. **Prompt-injection / sandbox posture.** Z.ai provides no sandbox, no injection filter and no
   content-safety layer for tool results; the harness (Claude Code / Agent SDK permission modes,
   `allowed_tools`, `verbatim` prompt handling) is the entire defence, identical to the Anthropic
   lane [50][52]. Two lane-specific exposures: (a) the Web Search Prime / Web Reader / Zread MCP
   servers return untrusted web and repo text straight into context [15][17] — same class as any
   fetch tool, so keep them off Telegram-facing jobs; (b) Z.ai's own clients (ZCode, AutoClaw) are
   a supply-chain risk after the 2026-09-18 upload incident and stay off the server (§7 gotcha
   11) [60]. Model-side, GLM-5.3 is marketed on offensive cyber capability [43], so treat
   security-flavoured outputs with the same guards as any model. Ranking for the cross-cut: **same
   posture as Claude (harness-supplied), one notch worse on tool-result trust because the
   vendor MCP servers auto-return fetched content with no allow-list.**
6. **Host resource budget.** Zero always-on daemon: the lane is env vars on the existing Claude
   Code binary plus HTTPS calls, so RAM/CPU on the 16 GB M4 is the same Node process the
   Anthropic lane already runs (no LiteLLM proxy, no local weights — §7 gotcha 8 rules out local
   GLM). If OpenRouter is used as the fallback route it is also proxy-less. Budget line: **0 MB
   incremental.**
7. **Reviewer independence.** The "different lineage → uncorrelated errors" premise is *weaker*
   for GLM than the matrix assumes but not refuted: HN carries speculation both ways
   ("the fact that Z.ai isn't distilling makes me wonder", Imustaskforhelp 2026-02-23; "perhaps
   they quickly distilled Fable or Mythos", tom2026hn 2026-07-17) and zero comments reporting
   GLM identifying as Claude or an Anthropic distillation allegation specific to Zhipu [84][85]
   — unlike the kimi/minimax/deepseek/qwen docs' recorded allegations. Zhipu publishes its own
   inference-infrastructure story [57] and open weights with training details [34][36], and its
   Claude-Code-compatible plan gives it every incentive to match Claude's style, which is a
   behavioural (prompt-format) correlation even without weight-level lineage. Working rule: GLM
   is an acceptable *second* adversarial reviewer (cheap, non-Anthropic training lineage as far
   as public evidence goes), never the INV-13 LGTM reviewer, and its verdicts should be sampled
   against a Claude review to measure actual agreement rate rather than assumed independent.
8. **Measured chat-surface latency.** Already measured for this lane (Artificial Analysis
   2026-09-24: GLM-5.3 TTFT 3.45 s / 60 tok/s; Flash 3.67 s / 42.8 tok/s [40][41]); the missing
   number is FlashX (vendor "200 tokens/s", no independent TTFT [19]). The Claude Sonnet 5 /
   Opus 5.5 TTFT gap belongs to the Claude doc; for the comparison here, GLM's ~3.5 s TTFT is
   the *floor* a Telegram reply pays before the first token, versus a sub-2 s figure claimed but
   unsourced for Claude — measure both with the same `-p` probe on the same day.

## 4. Cost

**Consumer/prosumer plans (GLM Coding Plan, individual).** Prices below are from the docs
"transition" page, labelled "(example based on current pricing)" and "for reference only" [3]; that page is the
Legacy Plan Migration Notice, and its 50%-off column applies only to legacy subscribers who had
auto-renew on as of 2026-04-30 (until 3 months after their legacy term ends), not to new buyers; the live z.ai/subscribe checkout was
not renderable (live checkout prices unverified as of 2026-09-24; HN Sept-2026 comments show no
new price changes). HN reports of "$80 two weeks ago, and now it's $160" for Max and "$65 Pro"
indicate prices moved in 2026 [47] (comment dates not re-verified — unverified as of 2026-09-24;
may describe mid-2026 plan churn already superseded by the 2026-07-30 credits migration [11]);
verify at checkout. **Gap-fill 2026-09-24:** z.ai/subscribe and z.ai/pricing still render only
navigation (direct, r.jina.ai) and the Wayback Machine has no capture of z.ai/subscribe [79], so
the live checkout remains unverified; corroboration that the $18/$72/$160 ladder is current:
the Coding Plan overview (not the legacy notice) says "Starting at just 18 USD per month, with Pro
and Max plans" [2]; HN 2026-08-26 "'Pro' plan (the middle one) is $56/mo if you prepay for a
year" (BeetleB — annual $691.20/12 = $57.60, matches); HN 2026-09-17 "The max plan will provide
~1,100 USD of GLM-5.3 … per month for 168 USD" (_aavaa_ — $168 vs the docs' $160, possibly
tax/PayPal or a rounding; 5% discrepancy noted); HN 2026-09-07 "the z.AI pro plan for $30 / month"
(ma2kx — likely a first-month/referral promo, unverified); HN 2026-07-22 "$17/mo" Lite
(ignoramous) [80]. Net: Lite $18 monthly is corroborated by two current sources; Pro/Max
monthly are consistent with annual-rate reports but carry a ±5% error bar until the owner sees
checkout. **Pass 3:** archive.org is unreachable from this environment (fetch blocked, not just
"no snapshot"), z.ai/status and the checkout remain JS-only, and HN comments since 2026-09-01 add
only "$30 / month" Pro (ma2kx, 09-07, unexplained) [86]; the transition page still shows the same
$18/$48.60/$172.80 · $72/$194.40/$691.20 · $160/$432/$1,536 ladder [3]. Verdict unchanged:
**Lite $18 corroborated; Pro/Max ±5%; the only closer is a human loading z.ai/subscribe.**

| Tier | Monthly | Quarterly | Annual | 5-h credits | Weekly credits | Models / extras |
|---|---|---|---|---|---|---|
| Lite | $18 | $48.60 | $172.80 | 2,000 | 10,000 | GLM-5.3, GLM-5.3-Flash; Vision, Web Search, Web Reader, Zread MCP [2][3] |
| Pro | $72 | $194.40 | $691.20 | 12,000 | 60,000 | same [2][3] |
| Max | $160 | $432 | $1,536 | 28,000 | 140,000 | same [2][3] |
| Team (Standard seat) | not published | — | — | 15,000 | 66,000 | min 2 seats [13] |
| Team (Premium seat) | not published | — | — | 35,000 | 155,000 | [13] |

Rules: non-refundable [4]; 7-day quota window from purchase date [4]; 10% first-order
referral discount [55]; legacy (pre-credits) plans were prompt-based (Lite ≈80 prompts/5 h,
Pro ≈400, Max ≈1,600) and were migrated 2026-07-30 [11]. Promo through 2026-10-07:
GLM-5.3-Flash is "zero quota consumption" in ZCode/AutoClaw and 2× quota in other tools,
nightly 23:00–09:00 SGT [12]. MCP tool calls cost output-multiplier 1.2 per call [2]. **All-day off-peak promo 2026-09-25 →
2026-10-07:** every hour billed at the 50% off-peak credit rate [2] — for the next two weeks the
off-peak columns of the estimate below apply to every job, peak-window or not.

**Billing mechanics (usage policy [5]):** auto-renewal is charged from bonus balance → cash
balance → linked card/PayPal; cancel "at least 3 days before the next billing date"; "Use in
unsupported tools may result in restricted benefits". **Legacy-plan migration terms [3]:** legacy
subscribers with auto-renew on as of 2026-04-30 received 2 complimentary months of the equivalent
tier and may renew at 50% off until 3 months after their legacy term ends — only relevant if the
owner already held a legacy plan (we do not).

**API (pay-as-you-go, $ per 1M tokens, docs pricing page 2026-09-24) [1]:**

| Model | Input | Cached input | Output | Batch |
|---|---|---|---|---|
| glm-5.3 | $1.40 | $0.26 | $4.40 | n/a (OpenRouter `:batch` $0.45 / $2.00 [63]) |
| glm-5.3-prime | $2.80 (OpenRouter only [63]) | — | $8.80 | — |
| glm-5.3-flash | $0.15 | $0.03 | $0.50 | n/a (OpenRouter `:batch` $0.06 / $0.20 [63]) |
| glm-5.3-flashx | $0.37 | $0.075 | $1.25 | n/a |
| glm-5.2 / glm-5.1 | $1.40 | $0.26 | $4.40 | n/a |
| glm-5 | $1.00 | $0.20 | $3.20 | n/a |
| glm-4.7 / glm-4.6 / glm-4.5 | $0.60 | $0.11 | $2.20 | n/a |
| glm-4.7-flashx | $0.07 | $0.01 | $0.40 | n/a |
| glm-4.7-flash, glm-4.5-flash, glm-4.6v-flash | free | free | free | — |
| glm-4.5-air | $0.20 | $0.03 | $1.10 | n/a |
| glm-4.6v (vision) | $0.30 | $0.05 | $0.90 | n/a |
| glm-ocr | $0.03 | — | $0.03 | — |
| Web Search tool | $0.01 / call | | | |

Artificial Analysis independently lists GLM-5.3 at $1.40/$4.40 and Flash at $0.15/$0.50 with
cache discounts of 81% (GLM-5.3) and 83% (GLM-5.3-Flash) [40][41]. GLM-5.3-Prime (1.5–2× throughput, text-only, 1M ctx) is $2.80 / $8.80 on OpenRouter
(2026-09-23) and absent from the docs.z.ai price list — 2× the GLM-5.3 rate for speed [63].
**OpenRouter as an alternative route [53][63]:** promo pricing of 60% off glm-5.3 ($0.5614 /
$1.764) and 70% off glm-5.3-flash ($0.045 / $0.14), batch endpoints (`:batch` above), a 1.31M-ctx
listing for 5.3/Flash, and `z-ai/glm-5.2:free` (32K ctx, $0). While the promo lasts this is
cheaper than Z.ai list for the API column below (5.3 job ≈ $0.11 instead of $0.276; Flash job ≈
$0.009) and avoids the Coding Plan "supported tools" ambiguity entirely, at the cost of a second
vendor in the data path. Off-peak API discount: the Coding Plan
docs mention it for credits; an API-side off-peak rate was not found.

**Free tiers:** `glm-4.7-flash`, `glm-4.5-flash`, `glm-4.6v-flash` are $0 on the API [1];
rate limits for free models: Not found (login-gated; unverified as of 2026-09-24). OpenRouter
adds `z-ai/glm-5.2:free` (32K ctx) [63]. Zero-quota GLM-5.3-Flash nightly promo on
the Coding Plan until 2026-10-07 [12].

**Monthly cost estimate — 10 / 100 / 1,000 agent jobs at ~150k input + 15k output tokens each.**
Assumptions: no cache hits (worst case), all jobs at "standard" credit rate (during the
2026-09-25 → 10-07 promo every job is at the off-peak half-rate, so read the off-peak figures);
4.33 weeks/month;
Coding Plan credits/job from the published formula [2]: GLM-5.3 = (150,000×6.9 + 15,000×24)/10,000
= **139.5 credits** (69.75 off-peak); GLM-5.3-Flash = (150,000×2.3 + 15,000×8)/10,000 =
**46.5 credits** (23.25 off-peak). Lite ≈ 43,300 credits/month (≈310 GLM-5.3 jobs or ≈930
Flash jobs; ≈620 GLM-5.3 jobs if scheduled off-peak); Pro ≈ 259,800/month (≈1,860 GLM-5.3
jobs); Max ≈ 606,000/month (≈4,340). 5-hour ceiling: Lite 14 GLM-5.3 jobs per window.

| Jobs/mo | (a) Subscription — cheapest tier that fits | (b) API glm-5.3 | (b) API glm-5.3-flash | (b) API glm-4.7-flash |
|---|---|---|---|---|
| 10 | Lite $18 (1,395 credits, 3% of month) | $2.76 | $0.30 | $0 |
| 100 | Lite $18 (13,950 credits, 32%) | $27.60 | $3.00 | $0 |
| 1,000 | Pro $72 (139,500 credits, 54%); or Lite $18 if all jobs are off-peak GLM-5.3 (69,750 — over Lite's 43,300, so no) / Lite if Flash off-peak (23,250 — fits) | $276 | $30 | $0 (rate-limited, unverified) |

Per-job API math: GLM-5.3 = 150k×$1.40/M + 15k×$4.40/M = $0.21 + $0.066 = $0.276; Flash =
$0.0225 + $0.0075 = $0.030. With Z.ai's automatic caching on repeated system prompts, real API
cost falls (cached input is 18.6% of list for 5.3) [1]. Break-even: Coding Plan Lite beats
GLM-5.3 API at >65 jobs/month; beats Flash API only above ~600 jobs/month.

## 5. Strengths & weaknesses per reviews

**Benchmarks (vendor-reported unless noted):**
- GLM-5.3 [18][43]: Terminal Bench 3.0 28.3 (GLM-5.2 4.6, Claude Opus 4.8 21.1, Claude Fable 5
  33.7, GPT-5.6 Sol 34.6); DeepSWE v1.1 66.9 (Opus 4.8 58.0, Fable 5 69.7, GPT-5.6 Sol 72.7);
  CyberGym 84.5 (comparison column 83.8, GPT-5.6 Sol 83.6); ExploitBench 54.4 (comparison column
  78.0, GPT-5.6 Sol 76.5); Agents' Last Exam 28.5; HLE-with-tools 62.5 (Fable 5 63.9, GPT-5.6 Sol
  64.5) [34][43]. Label of the 83.8/78.0 comparison column: docs.z.ai/guides/llm/glm-5.3 calls it
  "Mythos 5" (and adds ExploitGym Mythos 5 181/247) while z.ai/blog/glm-5.3 calls it "Fable 5" —
  Z.ai's own pages disagree (unverified as of 2026-09-24 which is correct). Net: on the launch
  table GLM-5.3 trails GPT-5.6 Sol on every row except CyberGym. Z.ai Code Bench 34.5% at
  max effort (~75K output tokens/task) vs Fable 5 39.5%.
- GLM-5.2 [20]: SWE-bench Pro 62.1; Terminal-Bench 2.1 81.0 vs Opus 4.8 85.0.
- GLM-5 [21]: SWE-bench Verified 77.8; Terminal Bench 2.0 56.2. GLM-4.7 [22]: SWE-bench
  Verified 73.8, LiveCodeBench v6 84.9, HLE 42.8, τ²-Bench 84.7.
- GLM-5.3-Flash [19][36]: DeepSWE 63.4; AutomationBench 48.8; Z.ai Code Bench 29.0 vs Opus 4.8
  29.5 ("approaching Claude Opus 4.8 on coding and agentic benchmarks").
- Independent: Artificial Analysis Intelligence Index — GLM-5.3 (max) 45, "#2 / 113", $2.01
  per index task, "very verbose" (210M output tokens vs 140M median) [40]; GLM-5.3-Flash 42,
  "#4 / 113" open-weights, $0.25/task [41] (the Z.ai VLM page claims 57 on index v4.1.1 at
  $0.045/task [19] — different index version; conflict noted). Arena text: glm-5.3-max #19
  (1483±6; Arena tags it "MIT" but the HF LICENSE is the custom "GLM-5.3 License" — Arena's
  metadata appears stale [35][42]), glm-5.3-flash #29 (1475±7), glm-5.2-max #38, glm-5.1 #47, glm-5 #56, glm-4.7 #83;
  leaders claude-fable-5-high 1506, claude-opus-4-6-high 1505 [42]. Terminal-Bench and
  SWE-bench leaderboard pages were JS-only and not readable here.

**What it is best at (attributed):**
- Cheap near-frontier agentic coding. HN: "GLM 5.3 feels like Opus 4.8 ... replaced all other
  models for me" (bel8) [45]; "it really is opus 4.8 level" (zackify) [45]; "I've noticed no
  real difference between the Claude model and GLM ... for coding" (crossroadsguy) [45]; "If
  you told me I could only use this and never use Fable or Sol again, I'd shrug"
  (InsideOutSanta, on GLM-5.2) [48]; "get 80% of Claude Code for like $3/month" and "a no
  brainer" for budget users [47].
- Price/volume: "I ran 30M tokens through for 50c" (zackify) [45]; "900m tokens (95% cached)
  on Z.ai's $18/mo coding plan" [47]; bkd9: Flash is "the cheapest way to reach Artificial
  Analysis Intelligence Index 52.3 to 57.5, at 8.7¢ per task" [45].
- Open weights + permissive licences (MIT through 5.2, custom for 5.3) — Simon Willison calls
  GLM-5.2 "probably the most powerful text-only open weights LLM" [49]; Hugging Face used
  GLM-5.2 to defend against an attacker when a commercial frontier model refused [44].
- Long context that is "practically usable" for coding agents (1M on 5.2/5.3) [20].
- Security research: GLM-5.3's cyber results and the public disclosure ledger at cvd.z.ai [43].

**Weaknesses (attributed):**
- Staying on task: "it constantly builds things I didn't ask it to" (kaeluka) [46]; "I often
  find myself asking Sonnet to clean up GLM's code"; one user "switched to Claude subscription"
  after rewriting ~90% of GLM output [47].
- Speed/verbosity: below-median tokens/s and high TTFT; very verbose reasoning [40][41].
- Language drift: "It starts replying in Chinese after a while" (Swingboy) [45].
- Quota friction: "if I use it during peak hours I will hit the 5hr limit super fast" (ryan-a)
  [46]; "5-hour limits felt too restrictive"; "weekly limits somewhat fast with their 65 USD Pro"
  [47]; "4 different flavours of the Max plan floating around" — plan churn [47].
- Reliability: Feb-2026 compute shortage and registration freeze [39]; "service is bumpy"
  during launches [48]; no public status page found.
- Governance: U.S. Entity List [39]; "I suspect any model connected or built by China will
  serve their interest despite their terms" (pizzafeelsright) [45]; Chinese-user privacy
  complaints [48]. **ZCode repo-upload incident (2026-09-18 → 09-22):** researcher Ferstar showed
  ZCode's Repository Index / Repo Wiki feature packaged and git-encrypted entire user workspaces
  (full project history) and uploaded them to Alibaba Cloud with the decryption key held only by
  Z.ai; Reuters (2026-09-21) reported Z.ai disabled the feature, and on 2026-09-22 Z.ai
  apologised, said all uploaded data was deleted and never used for training, had CAICT/NSFOCUS
  audit the fix, and open-sourced ZCode (github.com/zai-org/ZCode, Apache-2.0; v3.14.3
  2026-09-23) — though Ferstar notes pre-patch upload code and commit history were wiped
  [60][61][62]. Reports describe it as a ZCode client feature, not the API or other harnesses.
  Gap-fill 2026-09-24: The Register names the mechanism as ZCode's "Repository Index
  functionality" triggered by "Repo Wiki generated pages in the cloud" — a client-side feature
  Claude Code, Codex and OpenCode do not have — and mentions no other tool, no API path and no
  Coding-Plan-wide exposure; Z.ai's statement scopes deletion to "the previously uploaded data"
  without naming affected products [60]. HN coverage was thin (the 09-18 X-post story got 2
  points, The Register story 5) and no comment claims other-harness exposure [81]; Reuters' body
  is paywalled (403). So: **no source implicates Coding Plan users on other harnesses, but Z.ai
  has not affirmatively cleared them either** — downgrade from "unverified" to "no evidence of
  exposure; no vendor attestation". Treat client-side telemetry of any Z.ai
  tool as a governance risk. Privacy policy says API content is "not saved on our servers" and consumer
  content may train models; API/enterprise content is not used unless you agree [31][30].
- Licence drift: GLM-5.3 moved from MIT to a custom licence with a $10B-revenue security-review
  trigger [35] (irrelevant at our scale, but a trend).
- Controversy: the "emergent cyber capabilities" framing of GLM-5.3 drew an HN debate on open
  release of offensive capability [46]; API prices rose 10% on 2026-04-07 [39] and Coding Plan
  tiers repriced in 2026 [47].

## 6. Finance / trading relevance

- **Real-time data:** Web Search API (`search-prime` engine, 1–50 results, domain and recency
  filters, $0.01/call) returning titles/URLs/summaries/dates; the docs' own example is
  economic-events/CPI news [28]. Same capability as an MCP server for Coding Plan users [15].
  Web Reader MCP fetches pages [2].
- **Market-data connectors / finance products:** Not found — searched: docs.z.ai/llms.txt
  (no finance, market, quote or ticker pages), Agents API (translation, slides, video only)
  [29], HN Algolia "GLM trading OR finance OR stock" (0 relevant hits). Zhipu has no public
  finance vertical outside China that this research could locate.
- **Sentiment sources:** none first-party; you would pipe your own (RSS, X/Reddit APIs) into
  the model. No X/Twitter firehose access (contrast Grok).
- **Restrictions:** Terms prohibit using the service "as a substitute for professional services"
  in "investment and financial management" and for "high-risk automated decision-making" [30].
  For Atlas (research + paper trading, no live order path on the server) that is compatible;
  a live order path driven directly by GLM output would sit against that clause.
- **Practical fit:** GLM-5.3's strengths (long-horizon agentic coding, 1M context, tool use,
  cheap tokens) map well to research-loop work — backtest code, data-pipeline maintenance,
  adversarial review of theses, summarising filings pulled via Web Reader. It has no edge in
  data access, so treat it as a cheap compute tier, not a data source.

## 7. Integration recipe for our server

**Recommended path:** GLM Coding Plan **Lite ($18/mo)** used through the existing Claude Agent
SDK / Claude Code runner via the Anthropic-compatible endpoint, as a *second lane* selected
per job by the model router. Rationale: (1) the server already speaks the Messages protocol
and `stream-json`; (2) Lite covers ~300 GLM-5.3 jobs or ~900 Flash jobs a month at our job
profile, and nearly all of our schedule falls in Z.ai off-peak hours (peak is 02:00–06:00
ET Mon–Fri) [2]; (3) keys, not OAuth — nothing about Anthropic subscription auth changes. Gap-fill 2026-09-24:
the Lite $18 recommendation **stands, conditionally** — Lite $18 is corroborated by the current
overview page and HN [2][80], and the §3 dimension review changes the *shape* of the lane rather
than the tier: (a) owner-only jobs on the Coding Plan key (third-party-serving is prohibited
[6]); (b) proprietary theses only on the pay-as-you-go API key under the DPA "not saved / not
trained" wording [30][31]; (c) JSON-parsing jobs pinned to `glm-4.7-flash` / `glm-5` or an
OpenRouter provider advertising `structured_outputs` until 5.3 JSON mode is confirmed [25][66];
(d) credit accounting computed server-side from response `usage` fields, with 429 codes
1316/1317 as the stop signal [69][70]; (e) buy one month, not a quarter, until checkout prices
are seen. If any of (a)–(d) is unacceptable, drop the Coding Plan and run the whole lane on the
API key (100 jobs/month on 5.3 ≈ $28, Flash ≈ $3).
Fallback path for classification/routing/cheap bulk work: pay-as-you-go API key with
`glm-4.7-flash` (free) or `glm-5.3-flash` ($0.03/job) via the OpenAI-compatible endpoint,
which is fully inside the Terms (no "supported tool" clause).

**Anthropic's position:** the Claude Code gateway docs state Anthropic "doesn't endorse,
maintain, or audit third-party gateway products, and doesn't support routing Claude Code to
non-Claude models through any gateway" [50] — the recommended path is an unsupported
configuration on the Anthropic side as well; expect breakage on Claude Code upgrades and no
support recourse. Alternative that avoids both vendors' grey zones: OpenRouter `z-ai/glm-5.3` /
`glm-5.3-flash` via the OpenAI-compatible cheap lane (promo-priced, batch available) [63].

**Policy caveat, decide before enabling:** the Coding Plan is licensed for one natural person
inside "officially supported tools"; Z.ai names "SDK-based access" as a restrictable pattern
[6]. The Agent SDK spawns the real Claude Code binary and just sets env vars [51][52], so the
wire traffic is Claude Code's, but Z.ai never publishes its detection rule. Keep it
single-tenant, keep job volume within quota, and prefer the API key for anything that is not
a coding-harness session.

**Auth/env (per Z.ai's Claude Code page [7] and Claude Code gateway docs [50][51]):**

```bash
# ~/.env for the GLM lane (never mix with Anthropic vars in the same process env)
ZAI_CODING_KEY=...           # Coding Plan key from z.ai/manage-apikey/apikey-list
ZAI_API_KEY=...              # optional pay-as-you-go key for the OpenAI-compatible lane
```

```python
# src/runner: launch a job on the GLM lane with the Claude Agent SDK (Python merges env
# on top of the parent env, so scrub Anthropic creds first) [51]
import os
from claude_agent_sdk import query, ClaudeAgentOptions

def glm_env(model="glm-5.3", small="glm-5.3-flash"):
    return {
        "ANTHROPIC_BASE_URL": "https://api.z.ai/api/anthropic",
        "ANTHROPIC_AUTH_TOKEN": os.environ["ZAI_CODING_KEY"],
        "ANTHROPIC_DEFAULT_OPUS_MODEL": model,
        "ANTHROPIC_DEFAULT_SONNET_MODEL": model,
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": small,   # also moves background tasks to Flash
        "API_TIMEOUT_MS": "3000000",
    }

async def run_glm_job(prompt, cwd, allowed_tools):
    opts = ClaudeAgentOptions(cwd=cwd, allowed_tools=allowed_tools,
                              permission_mode="acceptEdits", env=glm_env())
    async for msg in query(prompt=prompt, options=opts):
        yield msg   # same stream-json events the Anthropic lane already parses
```

CLI equivalent for a launchd/cron probe:

```bash
ANTHROPIC_BASE_URL=https://api.z.ai/api/anthropic ANTHROPIC_AUTH_TOKEN=$ZAI_CODING_KEY \
ANTHROPIC_DEFAULT_SONNET_MODEL=glm-5.3 ANTHROPIC_DEFAULT_HAIKU_MODEL=glm-5.3-flash \
claude -p "summarise CHANGELOG.md" --output-format stream-json --max-turns 3
```

Cheap-lane sketch (OpenAI-compatible, API key, inside Terms):

```python
from openai import OpenAI
c = OpenAI(api_key=os.environ["ZAI_API_KEY"], base_url="https://api.z.ai/api/paas/v4/")
r = c.chat.completions.create(model="glm-4.7-flash",   # free tier [1]
    messages=[{"role":"system","content":"Return JSON: {label, confidence}"},
              {"role":"user","content":text}],
    response_format={"type":"json_object"})               # [25]
```

Optional MCP for research jobs: `claude mcp add -s user -t http web-search-prime
https://api.z.ai/api/mcp/web_search_prime/mcp --header "Authorization: Bearer $ZAI_CODING_KEY"`
[15] (costs 1.2 output-multiplier credits per call [2]).

**Task-class fit here:**
- Research (long-doc synthesis, 1M ctx): good — GLM-5.3 or Flash; add Web Search MCP.
- Coding / build loops: good; expect more "did more than asked" drift than Claude [46] —
  keep the existing post_review gate.
- Code review: fair; use as a *second* reviewer, not the INV-13 LGTM reviewer.
- Chat (Telegram): TTFT 3.45–3.67 s and 43–60 tok/s [40][41] ⇒ ≈ 8–11 s for a 300-token reply;
  fine for an async bot with a typing indicator, wrong for instant replies — rate **5/10** for the
  chat surface, FlashX (200 tok/s claim [19]) untested.
- Classification / routing: `glm-4.7-flash` free (documented JSON mode [25]); `glm-5.3-flash`
  only once its JSON mode is confirmed on api.z.ai (unverified; Z.AI's OpenRouter endpoint does
  not advertise `response_format` [67]).
- Adversarial review (fable-5-style grading): usable and cheap; independent model family
  is a plus for diversity, minus for calibration — run it alongside, not instead.
- Trading research: good for code and summarisation; no data edge; not for order decisions
  (Terms [30] + our own live-money gate).

**Gotchas:**
1. Peak/off-peak: current credit plans are 2× (off-peak = 50%) [2]; the 3× (and Flash
   0.4×/1.2×) figures are legacy-plan multipliers only [11] — still measure actual credit burn on
   first jobs, since concurrency is also "dynamically" raised off-peak [5].
2. GLM-5.3 reasoning cannot be turned off and defaults verbose; set `reasoning_effort`
   (`low` for routing) and cap `max_tokens` — output multiplier is 24 vs input 6.9 [2][18].
3. `tool_choice` only `auto` on the native API [26]; `json_schema` strict mode not documented.
4. Chinese-language drift in long sessions [45] — add a language guard in the post-processor.
5. Gateway vars disable Remote Control/voice in Claude Code (Remote Control is also blocked
   whenever ANTHROPIC_BASE_URL points at a non-Anthropic host, since v2.1.196; `claude doctor`
   names the blocker) and replace the subscription for
   that process [50][51] — isolate the GLM lane's env so the Anthropic lane keeps its Max login.
6. Coding-Plan key ≠ API key; Team key ≠ either [23]. Store separately.
7. Non-refundable; 7-day quota anchored to purchase time [4]. Buy monthly first.
8. Local running on the 16 GB M4 Mini is not practical: GLM-4.7-Flash (30B-A3B) Q4_K_M is
   18.3 GB, Q3_K_S 13.3 GB [38] — only a ~3-bit quant fits, leaving no headroom for Postgres
   + Redis + runner. GLM-5.3-Flash is 320B [36]. Use the hosted free tier instead.
9. Entity-List vendor; API content "not saved" per policy [31], but keep proprietary Atlas
   strategy code off this lane until the owner signs off.
10. No batch API on api.z.ai (OpenRouter has `:batch`), no status page (status.z.ai
    `ENOTFOUND` 2026-09-24 [71]), no published API rate limits — build client-side retries and a
    breaker exactly like the existing 529 handling, keyed on body codes 1302/1305/1313 (retry)
    vs 1316/1317/1318–1321 (stop until reset) [70].
13. No usage endpoint [69]: meter credits locally from response `usage` × the §3 multipliers,
    and surface them on the ops dashboard — otherwise "watch their progress" is blind on this lane.
14. Coding-Plan outputs must not reach non-owner users (pickem dashboard, shared project
    sites) [6]; anything served to a second person goes through the API key with a Z.ai model
    disclosure [30].
11. Do not install ZCode or AutoClaw on the server: ZCode shipped a silent whole-repo upload
    feature (2026-09-18) [60][61]; the API/harness path used here was not implicated, but any
    Z.ai client binary gets egress auditing first.
12. Promo window 2026-09-25 → 10-07 (all-day off-peak) halves credit burn [2] — do not calibrate
    long-run quota assumptions on jobs run in that window.

## 8. Verdict

1. GLM-5.3 is the best cheap near-frontier coding/agent model that plugs into Claude Code
   unchanged; GLM-5.3-Flash is the best price/intelligence point on the market right now.
2. The Coding Plan Lite tier ($18/mo) covers a few hundred of our jobs a month, almost all at
   off-peak rates given US scheduling; API Flash is ~$0.03/job for overflow.
3. Terms are the real risk: single-person, "supported tools only", "SDK-based access" named
   as restrictable — single-tenant Agent SDK use is grey; API-key use is clean. Scheduler
   sizing: plan Lite = 1 parallel headless session, Pro = 2, Max = 3, more off-peak [5].
4. Quality is a step below Claude Fable/Opus (and GPT-5.6 Sol on the launch table) for
   staying on task and review calibration; speed and verbosity are below median; reliability
   has cracked under launch load. GLM-5.3-Prime buys 1.5–2× speed at 2× price (OpenRouter
   only so far).
5. No finance data edge; fits as a compute tier for research/coding, not a data source.
6. Governance is now a demonstrated, not theoretical, risk: ZCode uploaded whole user repos
   without consent (2026-09-18); the API/harness lane was not implicated, but keep Z.ai client
   apps off the server and proprietary code off this lane pending owner sign-off. Anthropic
   also does not support Claude Code against non-Claude models [50].

Fit scores (1–10): research **7** · coding/agentic **8** · cost efficiency **9** ·
automation friendliness **6** (key-based and harness-compatible, but ToS ambiguity on both
sides, no native batch, no status page) · governance/trust **4** (Entity List + ZCode incident)
· trading research **5**.

**Calibrated scorecard (gap-fill 2026-09-24, common anchors for the cross-provider matrix):**
anchor 10 = Claude Max lane on Claude Code/Agent SDK as this server runs it today; 5 = usable
with real workarounds; 1 = unusable. Dimensions and evidence: research **6** (1M ctx + Web
Search MCP, no data edge; Arena #19 [42]) · coding **7** (Terminal-Bench 3.0 28.3 vs Fable 5
33.7 [43]; "did more than asked" drift [46]) · cost **9** ($0.03–0.28/job API, $18 plan [1][2])
· automation **5** (harness-compatible; but no usage API [69], no status page [71], ToS grey
zone on SDK use [6], Anthropic-unsupported gateway [50]) · trading **4** (no data; Terms bar
"investment … as a substitute for professional services" [30]; DPA allows theses on the API
lane [31]) · chat/Telegram latency **5** (8–11 s round trip [40][41]) · data governance **3**
(Entity List, ZCode upload, no ZDR [39][60][31]) · third-party serving **3 (plan) / 7 (API)**
[6][30] · tool-churn burden **6** (medium; harness coupling) · reliability **4** (no status
page, no SLA tier, failover via open weights on OpenRouter [66][67]).

## 9. Sources

All accessed 2026-09-24.

1. https://docs.z.ai/guides/overview/pricing — API price list
2. https://docs.z.ai/devpack/overview — Coding Plan quotas, credit formula/multipliers, off-peak, MCP
3. https://docs.z.ai/devpack/transition — tier prices (monthly/quarterly/annual)
4. https://docs.z.ai/devpack/faq — supported-tools-only, non-refund, weekly window
5. https://docs.z.ai/devpack/usage-policy — enforcement ladder
6. https://docs.z.ai/legal-agreement/subscription-terms — single person, SDK-access clause
7. https://docs.z.ai/devpack/tool/claude — Claude Code env config
8. https://docs.z.ai/devpack/tool/codex — Codex config (Responses endpoint)
9. https://docs.z.ai/devpack/tool/opencode — OpenCode config
10. https://docs.z.ai/devpack/tool/others — 16 supported tools, 3 endpoints
11. https://docs.z.ai/devpack/notice/usage-revision — legacy prompt quotas, 1×/3× rates, 2026-07-30
12. https://docs.z.ai/devpack/notice/event-glm-5.3-flash — Flash promo to 2026-10-07
13. https://docs.z.ai/devpack/teamplan — Team seats
14. https://docs.z.ai/devpack/extension/coding-tool-helper — `npx @z_ai/coding-helper`
15. https://docs.z.ai/devpack/mcp/search-mcp-server — Web Search Prime MCP
16. https://docs.z.ai/devpack/mcp/vision-mcp-server — Vision MCP tools
17. https://docs.z.ai/devpack/mcp/zread-mcp-server — Zread MCP
18. https://docs.z.ai/guides/llm/glm-5.3 — GLM-5.3 specs/benchmarks
19. https://docs.z.ai/guides/vlm/glm-5.3-flash — GLM-5.3-Flash/FlashX specs
20. https://docs.z.ai/guides/llm/glm-5.2 — GLM-5.2 specs
21. https://docs.z.ai/guides/llm/glm-5 — GLM-5 specs
22. https://docs.z.ai/guides/llm/glm-4.7 — GLM-4.7 specs
23. https://docs.z.ai/guides/overview/quick-start — base URLs, SDKs
24. https://docs.z.ai/api-reference/introduction — auth, SDKs, bundles
25. https://docs.z.ai/guides/capabilities/struct-output — JSON mode
26. https://docs.z.ai/guides/capabilities/function-calling — tools, `tool_choice` auto only
27. https://docs.z.ai/guides/capabilities/cache — automatic context caching
28. https://docs.z.ai/guides/tools/web-search — Web Search API
29. https://docs.z.ai/api-reference/agents/agent — Agents API
30. https://docs.z.ai/legal-agreement/terms-of-use — Singapore law, training use, finance clause
31. https://docs.z.ai/legal-agreement/privacy-policy — Singapore processing, API content not stored
32. https://docs.z.ai/llms.txt — docs index (used to establish absence of batch/finance/messaging pages)
33. https://huggingface.co/zai-org — model repo list
34. https://huggingface.co/zai-org/GLM-5.3 — card, 753B, 300K eval ctx, licence name
35. https://huggingface.co/zai-org/GLM-5.3/raw/main/LICENSE — custom licence text
36. https://huggingface.co/zai-org/GLM-5.3-Flash — MIT, 320B/18B, multimodal
37. https://huggingface.co/zai-org/GLM-4.7-Flash — MIT, 30B-A3B, benchmarks
38. https://huggingface.co/unsloth/GLM-4.7-Flash-GGUF — quant sizes
39. https://en.wikipedia.org/wiki/Zhipu_AI — company, IPO, Entity List, timeline, Feb-2026 shortage
40. https://artificialanalysis.ai/models/glm-5-3 — index 45, speed, price, verbosity
41. https://artificialanalysis.ai/models/glm-5-3-flash — index 42, speed, price
42. https://arena.ai/leaderboard/text — Arena ranks
43. https://z.ai/blog/glm-5.3 (fetched via r.jina.ai) — launch benchmarks, cyber, weights in two weeks
44. https://hn.algolia.com/api/v1/search?query=z.ai%20GLM&tags=story — HN story list/dates
45. https://news.ycombinator.com/item?id=49449507 — HN GLM-5.3-Flash thread (via Algolia comments)
46. https://news.ycombinator.com/item?id=49294997 — HN GLM-5.3 thread (via Algolia comments)
47. https://hn.algolia.com/api/v1/search?query=%22coding%20plan%22%20GLM&tags=comment — HN Coding Plan comments
48. https://hn.algolia.com/api/v1/search?query=Zhipu&tags=comment — HN Zhipu comments
49. https://simonwillison.net/tags/glm/ — release notes, sizes, licences, local runs
50. https://code.claude.com/docs/en/llm-gateway — subscription vs gateway credential semantics
51. https://code.claude.com/docs/en/llm-gateway-connect — env vars, Agent SDK `env` behaviour
52. https://code.claude.com/docs/en/agent-sdk/overview — SDK runs the Claude Code binary; headless `-p`
53. https://openrouter.ai/z-ai/glm-5.3/uptime — OpenRouter listing (1.3M ctx, promo price)
54. https://chat.z.ai/ — consumer app tagline/features
55. https://docs.z.ai/devpack/credit-campaign-rules — referral discount
56. https://docs.z.ai/devpack/latest-model — 5.3 + Flash on all tiers
57. https://news.ycombinator.com/item?id=49737922 — HN "How GLM built its own inference infrastructure"
58. https://docs.z.ai/devpack/tool/autoclaw — AutoClaw docs, 1.5× quota ("consumes only 67% of the standard quota")
59. https://autoclaw.z.ai/ — AutoClaw product page (Windows/macOS, iOS/Android, WhatsApp/Telegram/Discord/Lark, 50+ skills, 200M free tokens)
60. https://www.theregister.com/security/2026/09/22/zai-says-sorry-for-slurping-up-your-code-open-sources-zcode/5298300 — ZCode incident, apology, CAICT/NSFOCUS audit, Ferstar's wiped-history caveat
61. https://www.reuters.com/legal/litigation/chinas-zai-disables-ai-coding-assistant-features-after-security-issue-2026-09-21/ — Reuters 2026-09-21, feature disabled (title via HN Algolia; body not fetched)
62. https://github.com/zai-org/ZCode — Apache-2.0, v3.14.3 2026-09-23
63. https://openrouter.ai/api/v1/models — z-ai/* listings: glm-5.3-prime ($2.80/$8.80, 1M, created 2026-09-23), glm-5.3:batch, glm-5.3-flash:batch, glm-5.2:free (32K), 1,310,720 ctx for 5.3/Flash
64. https://hn.algolia.com/api/v1/search?query=%22Ox%20Alpha%22&tags=story — Ox Alpha stories (OpenRouter 2026-08-20 264 pts; Bloomberg confirm 2026-08-26 435 pts)
65. https://hn.algolia.com/api/v1/search?query=Ox%20Alpha%20GLM-5.3-Flash&tags=comment — comments quoting Z.ai: "we tested GLM-5.3-Flash anonymously as ox-alpha on OpenCode and OpenRouter"
66. https://openrouter.ai/api/v1/models/z-ai/glm-5.3/endpoints — per-provider uptime (30m/5m/1d), pricing, supported_parameters for glm-5.3 (gap-fill 2026-09-24)
67. https://openrouter.ai/api/v1/models/z-ai/glm-5.3-flash/endpoints — per-provider uptime and supported_parameters; Z.AI endpoint not listing response_format/structured_outputs (gap-fill 2026-09-24)
68. https://docs.z.ai/guides/overview/concept-param.md — concurrency "set by the platform", varies by plan; no numbers
69. https://docs.z.ai/openapi.json — full path list (14 paths); no usage/quota/balance/limits endpoint; per-response usage fields
70. https://docs.z.ai/api-reference/api-code.md — 429 body codes 1113, 1302, 1305, 1308, 1313, 1316, 1317, 1318–1321
71. https://status.z.ai/ — re-probed 2026-09-24: DNS ENOTFOUND (no status page)
72. https://statusgator.com/services/z-ai — 404 (no StatusGator service page)
73. https://hn.algolia.com/api/v1/search_by_date?query=GLM%20outage%20OR%20down%20OR%20502%20OR%20overloaded&tags=comment&numericFilters=created_at_i%3E1751328000 — 0 hits since 2026-07-01
74. https://hn.algolia.com/api/v1/search_by_date?query=%22z.ai%22%20plan%20month&tags=comment&numericFilters=created_at_i%3E1756000000 — April-2026 capacity-issue comments (greenavocado, jauntywundrkind) surfaced alongside price comments
75. https://code.claude.com/docs/en/data-usage — Claude Code data policy: consumer (Pro/Max) training toggle, 5-year/30-day retention, ZDR Enterprise-only, telemetry/OTEL, local transcript retention
76. https://registry.npmjs.org/@z_ai/coding-helper — 0.1.1 latest; 5 releases 2026-08-10 → 08-27
77. https://pypi.org/pypi/zai-sdk/json — 0.2.3 on 2026-06-16; 0 releases in prior 90 days
78. https://api.github.com/repos/zai-org/ZCode/releases?per_page=50 — single release v3.14.3, published 2026-09-24T10:54Z
79. https://archive.org/wayback/available?url=z.ai/subscribe&timestamp=20260920 — no archived snapshot of z.ai/subscribe
80. https://hn.algolia.com/api/v1/search_by_date?query=%22coding%20plan%22%20z.ai&tags=comment — price datapoints: BeetleB 2026-08-26 "$56/mo if you prepay for a year"; _aavaa_ 2026-09-17 "for 168 USD" (Max); ma2kx 2026-09-07 "$30 / month" (Pro); ignoramous 2026-07-22 "$17/mo"; KronisLV 2026-07-06 "Pro (50 USD)"
81. https://hn.algolia.com/api/v1/search_by_date?query=ZCode%20Z.ai&tags=story — incident stories 2026-09-18 (2 pts, X post) and 2026-09-22 (5 pts, The Register); no other-harness exposure claims
82. https://z.ai/manage-apikey/rate-limits — target of the docs rate-limit redirect; login wall, navigation only (pass 3, 2026-09-24)
83. https://z.ai/status (404), https://statusgator.com/services/zhipu-ai (404), https://isdown.app/status/z-ai (403) — no status page or third-party tracker found (pass 3, 2026-09-24)
84. https://hn.algolia.com/api/v1/search?query=Zhipu%20OR%20%22z.ai%22%20distill&tags=comment — two speculative comments (Imustaskforhelp 2026-02-23; tom2026hn 2026-07-17), no allegation with evidence
85. https://hn.algolia.com/api/v1/search_by_date?query=GLM%20%22identifies%20as%22%20OR%20%22I%20am%20Claude%22%20OR%20%22trained%20on%20Claude%22&tags=comment — 0 hits
86. https://hn.algolia.com/api/v1/search_by_date?query=%22coding%20plan%22%20GLM%20max&tags=comment&numericFilters=created_at_i%3E1756684800 — post-2026-09-01 comments: ma2kx "$30 / month" Pro; Havoc "4 different flavours of the Max plan"; no new prices
87. https://docs.z.ai/legal/dpa — 404; the DPA text lives inside the privacy-policy page [31]
88. https://web.archive.org/web/2026/https://z.ai/subscribe — fetch blocked from this environment (archive.org unreachable), so "no capture" in [79] could not be re-tested

## Verification log (2026-09-24)

**Corrections applied: 9** — major 4 (supported-tool list + general-purpose agent tools /
1.5× quota; messaging integrations via AutoClaw/OpenClaw; AutoClaw "no docs/HN" claim reversed;
ZCode repo-upload incident added to Governance), minor 5 (ZCode open-sourced note; 81%/83% cache
discounts; OpenRouter batch variants; transition-page label and legacy-only 50% column; Remote
Control blocked on non-Anthropic base URL since v2.1.196).

**Missing topics added:** ZCode incident (Snapshot, §3 Reliability, §5 Governance, §7 gotcha 11,
§8 item 6); GLM-5.3-Prime (lineup table, API price table, §4 text, §8); all-day off-peak promo
2026-09-25 → 10-07 (§3, §4 rules + estimate assumptions, §7 gotcha 12); four general-purpose agent
tools + 1.5× multiplier (§2); AutoClaw messaging agent (§2); Ox Alpha stealth history (§1 cadence,
§3); OpenRouter alternative route with promo/batch/free listings (§2, §4, §7); Anthropic's
"doesn't support routing Claude Code to non-Claude models" statement (§7, §8); GPT-5.6 Sol columns
(§5); billing mechanics and legacy-migration terms (§4); consumer-surface gap noted explicitly (§2).

**Claims re-verified this pass (source):** 20 supported tools, four best-effort agent tools,
"1.5× Usage" labels (docs.z.ai/devpack/tool/others); AutoClaw 67%-quota wording
(docs.z.ai/devpack/tool/autoclaw); AutoClaw platforms/IM list/200M tokens (autoclaw.z.ai);
incident timeline, CAICT/NSFOCUS audit, wiped-history caveat (The Register 2026-09-22); Reuters
2026-09-21 headline (HN Algolia); ZCode Apache-2.0 + v3.14.3 2026-09-23 (github.com/zai-org/ZCode);
promo dates and 50% off-peak wording, peak window Mon–Fri 14:00–18:00 SGT, credit multipliers
(docs.z.ai/devpack/overview); billing order / 3-day cancel / unsupported-tools sentence
(docs.z.ai/devpack/usage-policy); transition-page labels and 2026-04-30 / 2-month / 3-month terms
(docs.z.ai/devpack/transition); GLM-5.3-Prime $2.80/$8.80, 1M ctx, created 2026-09-23, text-only,
"1.5–2× the output throughput"; glm-5.3:batch $0.45/$2.00; glm-5.3-flash:batch $0.06/$0.20;
glm-5.2:free 32,768 ctx; 1,310,720 ctx on 5.3/Flash (openrouter.ai/api/v1/models, live curl);
GPT-5.6 Sol 34.6 / 72.7 / 83.6 / 76.5 / 64.5 and "Fable 5" label (z.ai/blog/glm-5.3 via
r.jina.ai); Anthropic non-Claude-routing sentence (code.claude.com/docs/en/llm-gateway) and
Remote Control / v2.1.196 / `claude doctor` text (code.claude.com/docs/en/llm-gateway-connect);
Ox Alpha HN stories 2026-08-20 (264 pts) and 2026-08-26 confirm (435 pts) plus comments quoting
Z.ai's "tested GLM-5.3-Flash anonymously as ox-alpha" (HN Algolia).

**Stale / unverified flags left in place (marked "unverified as of 2026-09-24"):** live Coding
Plan checkout prices ($18/$72/$160 are a docs example); GLM-5.3-Flash hosted context/output (HF
300K/163,840 vs docs 1M/128K); "Mythos 5" vs "Fable 5" comparison-column label; structured-output
support on 5.3 models; context-cache billing (50% vs 18.6% vs 81%); GLM-5.3-Prime native
api.z.ai availability; whether ZCode upload touched other-harness Coding Plan users; API
pay-as-you-go and free-model rate limits (login-gated); status page absence (not re-probed); HN
"$80 → $160 / $65 Pro" comment dates; Arena "MIT" tag for glm-5.3-max (doc's custom-licence
reading stands); Wikipedia 2026-02-12 vs 2026-02-11 for GLM-5; OpenRouter promo prices
($0.5614/$1.764, $0.045/$0.14) seen on model pages, not in the raw models API (which returns
list); Reuters body not fetched (headline only). Consumer chat.z.ai plan pricing and consumer
mobile/desktop apps remain "Not found".

**Fact-checker overall quality rating:** acceptable.

## Gap-fill log (2026-09-24, second pass)

**Gaps targeted:** live checkout prices; ZCode scope vs other-harness Coding Plan users; API and
free-model rate limits; JSON mode on 5.3; plus the seven cross-doc dimensions.

**Resolved / narrowed:** Lite $18 corroborated by the current overview page and HN (not just
the legacy "example") [2][80]; Pro/Max consistent with annual-rate HN reports, ±5% (Max $160 vs
"$168") — checkout itself still unrenderable and not archived [79]. ZCode: mechanism identified
as a ZCode-only client feature, no source implicates other harnesses, no vendor attestation
either [60][81]. Rate limits: still login-gated numerically, but the 429 body-code contract
(1302/1305/1308/1313/1316/1317/1318–1321) and the plan-tier "projects simultaneously" guidance
are now documented [70][5][68]. JSON on 5.3: still unverified on api.z.ai; model pages claim it
generically, the struct-output page omits it, and Z.AI's own OpenRouter endpoint does not
advertise `response_format` [18][25][67] — lane pinned to documented models.

**Dimensions added (§3 bullets + §8 calibrated scorecard):** data-handling matrix (API / Coding
Plan / consumer / Claude Max comparison row) [30][31][75]; progress-visibility plumbing (no usage
API; dashboards only; 1316/1317 as signals) [69][70]; third-party-serving permission (plan =
owner-only; API = end-user apps with disclosure) [6][30]; normalized reliability (no status
page, no SLA tier, OpenRouter per-host uptime, 0 HN incident comments in the 90-day window)
[66][67][71][72][73]; Telegram latency rating (8–11 s round trip, 5/10) [40][41]; tool churn
(coding-helper 5 releases/Aug, zai-sdk idle 90 d, ZCode history wiped; burden medium)
[76][77][78].

**Still unverified as of 2026-09-24:** live checkout prices (JS-only, no archive); whether
Coding Plan traffic falls under the DPA's "API Services" no-storage clause; JSON mode on
glm-5.3/5.3-flash on api.z.ai; numeric API/free-model rate limits; FlashX 200 tok/s and TTFT;
Reuters body (403); z.ai/blog (404 via r.jina.ai — no vendor statement page located).

## Gap-fill log (2026-09-24, third pass)

**Gaps targeted:** live checkout prices; JSON mode on 5.3; API/free-model rate limits; 2× vs 3×
off-peak; DPA scope of Coding Plan traffic; status page; plus the eight cross-doc dimensions.

**Closed:** 2×-vs-3× — the 3× (and 0.4×/1.2× Flash) multipliers are the legacy prompt-plan
values in the migration notice; current credit plans are 50% off-peak, so a new buyer is on 2×
[11][2]. Status page — z.ai/status, statusgator, isdown and the docs index all negative; treat
OpenRouter first-party uptime (99.92% / 99.07% at 30 min) as the only health signal [83][66][67].
Concurrency — qualitative ladder (Lite 1 / Pro 1–2 / Max 2+, higher off-peak, platform-dynamic)
documented in three places [5][13][68]; numbers remain login-gated [82].

**Narrowed:** JSON on 5.3 — Z.AI's own OpenRouter endpoints now advertise `response_format`
for glm-5.3 and glm-5.3-flash (contradicting the pass-2 reading of [67]); `structured_outputs`
(json_schema) is not offered by Z.AI; the struct-output page is unchanged [66][67][25] →
"json_object likely, one live probe to confirm". DPA scope — the privacy page *is* the "Data
Processing Addendum for API Services" with no definition of the term; nothing names Coding Plan;
Team Plan page adds a "excluded from model training by default" statement [31][13][87]. Cache
billing — cache page says "usually 50%", still ≠ price-list 18.6% [27][1].

**Still unverified as of 2026-09-24:** live Coding Plan checkout prices (Pro/Max ±5%; archive.org
unreachable from here [88]); numeric API and free-model rate limits / concurrency [82]; whether
individual Coding Plan traffic is "API Services" under the DPA [31]; `json_object` on 5.3 on
api.z.ai itself (endpoint advertises, docs silent); FlashX TTFT; Reuters body.

**Cross-doc dimensions answered for this lane (§3 "Cross-doc dimensions (pass 3)"):**
concurrency (1/2/3 sessions by tier, more off-peak); credential lifecycle (static key, no TTL,
three non-interchangeable key types, renewal + 1113/1316/1317 alarms); progress sink (derive
credits locally, no new daemon); empirical calibration (audit log out of scope; verdict
insensitive to cache share ≤100 jobs/month); prompt-injection posture (harness-supplied, vendor
MCP fetches untrusted content, Z.ai clients banned); host budget (0 MB incremental); reviewer
independence (no distillation allegation on record for Zhipu, behavioural correlation via
Claude-Code targeting; second reviewer only); chat latency (already measured; FlashX missing).
