# Cross-cut: current leaderboards and review consensus — research (as of 2026-09-24)

Scope note: this is the cross-vendor document. Per-vendor docs cover interfaces and pricing in depth; here each section is a cross-cut comparison with the numbers needed to rank models by task class. Web-search quota was exhausted for this session, so every fact was pulled by direct fetch of the primary page listed in §9; pages that could not be retrieved are marked "Not found — searched: …". Vendor-published numbers are labelled **self-reported**; leaderboard numbers run by a third party are labelled **independent**.

## 1. Snapshot

The frontier as of 2026-09-24 is a five-lab race with a very fresh top tier: Claude Opus 5.5 (2026-09-22), GPT-6 Astra (2026-09-03), Grok 4.7 (2026-09-21), Gemini 3.8 Flash (2026-09-02), Muse Spark 1.3 (2026-09-02), Claude Fable 5.1 (2026-09-01). Anthropic holds the independent composite (AA Intelligence Index #1, Arena text #1, Arena vision #1, Arena WebDev #1), OpenAI holds the hardest single-task evals (HLE on Scale, GPQA on AA, ARC-AGI-3, Vending-Bench 2), Google owns the speed/price corner, xAI is a distant-but-cheap 4th, and Meta's Muse Spark is the surprise SWE-bench Pro leader. Below the five labs sits a second tier that the sibling docs score on the same AA v4.3.2 index and that this cross-cut previously omitted: GLM-5.3 (45), Qwen3.8 Max (45), Kimi K3 (44), GLM-5.3-Flash (42), DeepSeek V4.1 Flash (39), MiniMax M3 (29), and Mistral's current line far below (Medium 3.5 14, Small 4 11, Large 3 9). Two of them matter for the router: GLM-5.3-Flash is within one index point of Gemini 3.8 Flash at one-fifth the price, and DeepSeek V4.1 Flash is the fastest sub-$1 model (232 tok/s, 0.9 s TTFT) [103][104][105][106][107][108][109].

| Vendor | Flagship (API ID) | Context / max out | Modalities (in→out) | Knowledge cutoff | Released | Cadence | Src |
|---|---|---|---|---|---|---|---|
| Anthropic | Claude Fable 5.1 (`claude-fable-5-1`) | 1M / 128K | text+image → text | Jun 2026 | 2026-09-01 | ~monthly (Opus 4.8 May, Sonnet 5 Jun, Opus 5 Jul, Fable 5.1 Sep, Opus 5.5 Sep) | [30][47] |
| Anthropic | Claude Opus 5.5 (`claude-opus-5-5`) | 1M / 128K | text+image → text | Jun 2026 | 2026-09-22 | " | [30][29] |
| Anthropic | Claude Sonnet 5 (`claude-sonnet-5`) / Haiku 4.5 (`claude-haiku-4-5-20251001`) | 1M / 128K; 200K / 64K | text+image → text | Jan 2026; Feb 2025 | 2026-06-30; 2025-10-15 | " | [30][47] |
| Anthropic | Claude Mythos 5.1 (restricted via Project Glasswing; "~150 orgs" unverified as of 2026-09-24) | (unverified) | — | — | 2026-09-01 | — | [47] |
| OpenAI | GPT-6 Astra (`gpt-6-astra`) | 1.05M / 128K | text+image → text | 2026-04-30 | 2026-09-03 | 2–3 months (GPT-5.4 Mar confirmed; 5.5 and 5.6 Jun dates unverified as of 2026-09-24; GPT-6 limited preview Sep 3, GA Sep 4 per Wikipedia) | [34][46] |
| OpenAI | GPT-6 Sol (`gpt-6-sol`) / Luna (`gpt-6-luna`) | 1.05M / 128K | text+image → text | 2026-04-20 / 2026-05-18 | 2026-09 | " | [34] |
| Google | Gemini 3.8 Flash (`gemini-3.8-flash`) | 1M / 64K | text+image+audio+video → text | not disclosed | 2026-09-02 | Flash every ~4–6 weeks (3.5, 3.7, 3.8); Pro stuck on 3.1 preview since 2026-02-19 | [38][50][49] |
| Google | Gemini 3.1 Pro (`gemini-3.1-pro-preview`) | 1M (unverified for 3.1) | multimodal → text | — | 2026-02-19 | " | [38][49] |
| xAI (SpaceXAI) | Grok 4.7 (`grok-4.7`) | 500K / — | text+image → text | not disclosed | 2026-09-21 | monthly (4.5 Jul, 4.6 Aug, 4.7 Sep); `grok-4.3` 1M ctx; `grok-build-0.1` coding | [42][43][18] |
| Meta | Muse Spark 1.3 (`meta/muse-spark-1.3` on OpenRouter) | 1M (self-reported) | multimodal → text | — | 2026-09-02 (1.1 Jul 9, 1.2 Aug 5) | monthly; Muse Glimmer 30B open-weight Apache-2 | [48] |

Positioning in one paragraph: Anthropic sells "long-horizon agentic work" (Opus 5.5 for most workloads, Fable 5.1 when Opus at high effort falls short) with adaptive thinking always-on and 1M context on every current model; OpenAI sells Astra as the reasoning/computer-use flagship with a three-tier Astra/Sol/Luna price ladder ($10/$50, $2/$10, $0.10/$0.50) that Simon Willison calls "a new price war"; Google sells Gemini 3.8 Flash as the fastest frontier-class model (AA #1 output speed, 297 tok/s) at $0.75/$3.75 promo pricing with a $0-per-token (rate-limited) free tier; xAI sells Grok 4.7 at $2/$6 with native Grok Build harness training; Meta's Muse Spark is proprietary-API-only but tops SWE-bench Pro and the Vals Finance Agent v2 podium. [30][33][37][19][43][48][52]

## 2. Interfaces & surfaces

Cross-cut of what matters for a headless server; per-vendor docs have the full matrices.

| Surface | Anthropic | OpenAI | Google | xAI | Meta |
|---|---|---|---|---|---|
| Consumer app | claude.ai web/desktop/mobile; Cowork, Design, Slides, Docs, Science, Security surfaces [31][29] | ChatGPT web/desktop/mobile; "Work Mode"; Images 2.5 [71][55] | Gemini app; Gemini Spark 24/7 agent on AI Pro; Deep Research/Deep Think [39] | grok.com + X app (X Premium/Premium+); SuperGrok [44] | Meta AI in FB/IG/WhatsApp (powered by Muse Spark) [48] |
| Agentic CLI | Claude Code (`claude -p`, Agent SDK Python/TS) [64][65] | Codex CLI (`codex exec --json`), Codex GitHub Action [36] | Gemini CLI (`-p`, `--output-format json/stream-json`) [40] | Grok Build (terminal agent, `grok -p "..." --output-format streaming-json`, browser sign-in or API key; open-sourced Apache-2 on 2026-07-16; see the access reconciliation below) [92][44][43] | none found |
| API + SDKs | Claude API, Bedrock, Vertex, Foundry IDs; Models API returns `max_input_tokens`/`capabilities` [30] | OpenAI API; long-context and fast-mode tiers [33] | Gemini API + Vertex; batch/flex/priority tiers [37] | xAI API, OpenAI-compatible; also via OpenRouter/Cursor [42][43] | "Meta Model API" + OpenRouter only [48] |
| Structured output / JSON events | `--output-format json --json-schema`; `stream-json` with `system/init`, `api_retry`, `permission_denied` events [64] | `--output-schema`, JSON Lines via `--json` [36] | `--output-format json` / `stream-json` [40] | API `response_format` (via OpenRouter params) (unverified for CLI) | OpenRouter lists `response_format`, `tools`, `reasoning_effort` [48] |
| Batch API | 50% off, up to 300K output with beta header [30][31] | ~50% off [33] | 50% off (Flash), batch=flex tier for 3.1 Pro [37] | none found on models page [42] | none found |
| Prompt caching | reads 10% of input (2.5% Fable 5.1, 5% Opus 5.5); 1h TTL on subscription, 5m on credits/API [30][66] | cached input 10% of input (Astra $1.00) [33] | $0.075/1M cache (3.8 Flash promo) [37] | 75% cache discount (Grok 4.7 cached $0.50) [42][18] | — |
| MCP | Claude Code `--mcp-config`, `mcp_servers` in SDK [64][65] | Codex supports MCP (per-vendor doc) (unverified here) | Gemini CLI MCP (per-vendor doc) (unverified here) | — | — |
| Computer use / browser | OSWorld 2.0 81.8% self-reported Opus 5.5 [29] | Astra "standout capability is computer use" (Raschka) [56] | — | — | — |
| Session resume | `--resume <id>` / `--continue`; SDK `resume=`, `fork_session` [64][65] | `codex exec resume [SESSION_ID]` [36] | (per-vendor) | — | — |
| Scheduled tasks | Claude Code `/loop`, scheduled tasks, cloud routines (usage counts against plan) [66] | Codex cloud tasks share plan allowance [35] | Gemini Spark agent (consumer) [39] | — | — |
| Messaging integrations | Slack (Claude), none native Telegram | Codex Slack integration (cloud) [35] | Gmail/Docs (Workspace) [39] | X itself | WhatsApp/Messenger (Meta AI) [48] |

Grok Build access — resolved: Grok Build is available on every xAI plan (including free) since 2026-08-19, which is the position the sibling docs (`grok-xai.md`, `crosscut-tos`) record and which the two primary sources fetched this pass are consistent with — xAI's Grok 4.7 announcement (2026-09-21) says "Get started today at x.ai/build" with no plan requirement, and the Grok Build docs describe sign-in "via browser or API key" with no tier gate [43][92]. Wikipedia's "requires SuperGrok ($30/mo)" sentence predates the August change and is stale [44]; x.ai/grok and x.ai/news returned 403 on 2026-09-24, so the 2026-08-19 date itself is carried from the sibling docs rather than re-fetched here. Two facts that do not change with the plan question: the July 14 2026 incident in which Grok Build uploaded whole repositories (secrets included, "27,800 times more data than needed") to SpaceXAI storage, disabled the same day, and the July 16 Apache-2 open-sourcing of the CLI in response [44]. §4 and §7 refer back here rather than restating.

Independent adoption signal: OpenRouter weekly token rankings (week ending 2026-09-23): 1 Claude Opus 5.5, 2 Claude Fable 5.1, 3 Qwen3.8 Max, 4 GPT-6 Astra, 5 Claude Opus 5, 6 Claude Fable 5, 7 GPT-6 Sol, 8 GPT-5.6 Sol, 9 Grok 4.7, 10 MiMo-V2.6-Pro. [51]

## 3. Headless / server automation fit

| Concern | Anthropic (Claude Code / Agent SDK) | OpenAI (Codex CLI) | Google (Gemini CLI) | xAI (Grok Build / API) |
|---|---|---|---|---|
| Non-interactive entry point | `claude -p "..." --output-format json --allowedTools ... --permission-mode auto --permission-prompts none`; `--bare` skips hooks/MCP/CLAUDE.md but **requires `ANTHROPIC_API_KEY`** ("bare mode doesn't use your subscription login") [64] | `codex exec "task" --json --output-schema s.json --sandbox workspace-write`; `--ephemeral`, `-o last.txt` [36] | `gemini -p "..." --output-format stream-json` [40]; Antigravity CLI (binary is `agy`, not `antigravity`) `agy -p "..." --output-format json` or `stream-json`, `--json-schema …`, `--effort low/medium/high`, `--dangerously-skip-permissions` (JSON envelope carries `usage`, `structured_output`, `num_turns`) [91] | Grok Build `grok -p "..." --output-format streaming-json` ("ideal for scripts, automations"); `grok inspect` for config discovery [92] |
| Auth modes | subscription OAuth via `/login` (default for Claude Code; **non-bare `-p` runs use it**), or `ANTHROPIC_API_KEY`, or Bedrock/Vertex/Foundry creds; env var API key **overrides** subscription silently [64][68] | ChatGPT sign-in (browser; headless fallbacks: device-code auth (beta), copying cached credentials from an authenticated machine, or SSH-forwarding the localhost callback) or `CODEX_API_KEY`; OpenAI's guidance: "Use API key authentication for programmatic Codex CLI workflows, such as CI/CD jobs" [89][36] | Google OAuth (browser flow) — **free personal Google login was retired from Gemini CLI on 2026-06-18** (unpaid-tier and Google One users are routed to Antigravity CLI); Gemini CLI login now needs AI Pro (1,500 req/day) or AI Ultra (2,000/day) or Code Assist Standard/Enterprise; `GEMINI_API_KEY` (free tier 250 req/day, Flash only) or Vertex (`GOOGLE_GENAI_USE_VERTEXAI=true`) [102][40] | Browser sign-in (any plan) or API key [92][42] |
| Subscription-for-automation terms | Consumer Terms bar automated access "except when you are accessing our Services via an Anthropic API Key or where we otherwise explicitly permit it"; Claude Code `-p`/Agent SDK on a Pro/Max login is first-party documented, so this is the explicitly-permitted path; third-party harnesses on consumer OAuth are not. The operative policy text is the support article "Using Agents According to Our Usage Policy" (linked from the Pro/Max Claude Code article): it lists prohibited agentic uses (surveillance without consent, phishing/mimic sites, spamming services, malware/backdoors, accessing another person's account with stored credentials), calls itself "non-exhaustive", and does not itself address third-party harnesses or account sharing [67][64][68][77] | Codex docs steer automation to API keys ("great for automation in shared environments like CI"); ChatGPT-account automation is "advanced/enterprise" [35][36] | Gemini CLI README documents "Headless Mode (Scripting)"; since 2026-06-18 the Google-login path is a paid-plan path (AI Pro/Ultra) and the no-cost path is Antigravity CLI on a Google account or the API-key free tier (250 RPD, Flash only) [40][102][90] | Grok Build docs document headless use on either browser sign-in or API key; no automation clause in the fetched docs [92] |
| Caps on subscription | Pro/Max: rolling 5-hour window + weekly cap shared across claude.ai, Cowork, IDE and Claude Code; Opus 5.5 launch raised 5-hour limits on Pro/Max/Team and added a **saveable rate-limit reset** ("a rate limit reset, which you can now save and use whenever you choose") for Pro/Max/Team/seat-based Enterprise; exact message counts not published ("depends on length and complexity") [29][32][68] | Codex per-5h message ranges: Astra 5–45 (Plus/Business), 25–225 (Pro 5x), 100–900 (Pro 20x); Sol 15–150 / 70–700 / 300–3,000; Luna 350–3,000 / 1,750–14,000 / 7,000–56,000 (table lists Astra 5–45 only for Plus and Business; no Free/Go rows); "Cloud chats on ChatGPT plans use GPT-5.6 Sol and may use more of your allowance than local messages"; weekly limits "may also apply" [35] | Gemini CLI on Google login: Code Assist Individual 1,000 req/day (the row the quota page still prints, but the free-login route was replaced by Antigravity CLI on 2026-06-18), AI Pro 1,500/day, AI Ultra 2,000/day, Code Assist Standard 1,500 / Enterprise 2,000, aggregated across models; "one prompt might result in multiple model requests". API-key free tier: 250 req/day, Flash only; per-model RPM/TPM are visible only in AI Studio [102][40][41][37] | HN user report: "SuperGrok allowance is drained extremely fast. About 20-30 simple coding prompts…and it's over for the week" (jmaker) [60] |
| Overage path | Usage credits at standard API rates once plan is exhausted; monthly spend cap; `/usage-credits` (subscription login only) [69][66] | API pricing [35] | API key billing [40] | API |
| Sandboxing | permission modes `auto`/`dontAsk`/`acceptEdits`; `--allowedTools` prefix rules; `-p` shows no trust dialog and **runs project hooks/MCP unless `--bare`** [64] | `--sandbox read-only|workspace-write|danger-full-access`; requires a git repo unless `--skip-git-repo-check` [36] | (per-vendor) | — |
| Streaming / events | `stream-json` NDJSON with `system/init` (plugins, MCP status, capabilities), `api_retry` (error categories incl. `rate_limit`, `overloaded`), subagent messages via `parent_tool_use_id`; final `result` carries `total_cost_usd`, `session_id`, `permission_denials` [64] | JSON Lines event stream on stdout; progress on stderr [36] | NDJSON `stream-json` [40] | SSE via API |
| Exit semantics | exit 0 on success, non-zero on failure; SIGTERM → 143, turn left unfinished but resumable; stdin capped at 10MB; background subagents keep `-p` open up to 10 min idle (`CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS`) [64] | final message to stdout [36] | — | — |
| Cost/telemetry | `--max-budget-usd`, `max_budget_usd` in SDK; OpenTelemetry export (`claude_code.cost.usage`, `claude_code.token.usage`, …); `/usage` attribution by skill/subagent/MCP/loop — TUI only, no quota API [65][66][88] | `/status` shows remaining limits in a TUI session; no quota API; **OpenTelemetry export is documented** (`[otel]` in config.toml: exporters `otlp-http`, `otlp-grpc`, `statsig`, `none`; events `codex.conversation_starts`, `codex.api_request`, `codex.tool_decision`, tool results; `log_user_prompt` defaults to `false`) [35][89][120] | Antigravity CLI `/usage` ("Model Quotas", TUI) and a `usage` token object in the headless JSON envelope; Gemini CLI has neither [90][91] | `grok inspect` (config only); no quota or telemetry docs on the fetched page [92] |

The full progress-visibility table across all lanes (including the Chinese coding plans and Mistral) is in §7.

### Reliability, normalized (window 2026-08-01 → 2026-09-24, one source per vendor)

| Lane | Source | Incidents in window | Longest | Priority / SLA tier sold? | Src |
|---|---|---|---|---|---|
| OpenAI | status.openai.com/history | ~22 listed (8 Aug / 14 Sep; totals unverified) | ~23 h API elevated errors (Sep 17) | "Fast mode" 2x API price, 2.5x plan credit rate — speed, no uptime SLA | [71][33][35] |
| Anthropic | status.claude.com | 5 in Sep (Aug not rendered) | 1 h 41 m API latency (Sep 10); ~6-day Cowork-on-Windows degradation | fast mode 2x (Opus 5.5 $8/$40); no SLA | [70][29] |
| Google (Gemini API / Vertex) | status.cloud.google.com | 0 listed | — (last: 1 h 58 m, 2026-02-27) | priority tier 3.1 Pro $3.60/$21.60 (1.8x) — no numeric SLA | [78][37] |
| xAI | StatusGator (status.x.ai 403) | 10 across Aug–Sep | 3 h 27 m outage (Sep 3); 1 h 30 m (Aug 17) | "fast" variants 2x price for 2x speed; no SLA | [115][42] |
| DeepSeek | status.deepseek.com | 0 listed | — ; published uptime Jun–Sep: V4 Pro API 99.89%, V4.1 Flash API 99.66% | none | [112] |
| MiniMax | status.minimax.io | 13 in Sep (Aug not shown), all LLM service, 1–9 min each | ~9 min | none documented in fetched docs | [113] |
| Mistral | StatusGator (status.mistral.ai 404) | 26 (16 Aug / 10 Sep), ~178 h StatusGator-counted "downtime" incl. multi-day Aug 12–16 and Sep 5–9 | multi-day | "Priority inference" tier listed on pricing page; sibling docs report a Priority Tier preview with an uptime SLA — SLA number not on any page fetched this pass | [114][109] |
| Kimi / Z.ai / Meta / Qwen | none — status.kimi.ai and status.z.ai do not resolve; Kimi docs index lists only a changelog; no Meta or Alibaba status page found | n/a | n/a | none | [117] |

Caveats: StatusGator counts component-level warnings as incidents, so the xAI and Mistral rows are not comparable to vendor-run pages; MiniMax's 13 short blips would probably not appear on a vendor-curated history at all; "0 listed" for Google and DeepSeek means nothing was posted, not that nothing happened. No vendor in the table publishes a numeric SLA on a self-serve tier. Narrative per vendor follows.

OpenAI status shows a ~23h "elevated error rates across API models" (Sep 17), ~20h GPT-5.6 errors (Sep 15), ~12h login outage (Aug 20) — the three incidents are listed on the history page but the durations and the incident totals (22: 8 Aug / 14 Sep; a re-count gave 11 Aug / 23 Sep) are unverified as of 2026-09-24 [71]. Claude status shows 5 incidents in Sep 2026, the longest being ~1h41m of elevated Claude API latency (Sep 10) and 1h22m of Fable/Mythos error spikes (Sep 15) and 1h20m multi-model errors on Opus 5.5 launch day (Sep 22); one ~6-day Cowork-on-Windows degradation (Sep 8–14, caused by a Windows update, fixed by Microsoft) [70]. Google: the Google Cloud status summary lists **no Vertex AI / Gemini API incidents in Aug–Sep 2026** (last listed Gemini API incident 2026-02-27, 1h58m elevated errors on the global endpoint); the AI Studio status page rendered no incident data, so the consumer Gemini API surface is unassessed [78]. xAI: status.x.ai returned 403 on 2026-09-24; StatusGator's Grok feed supplies the 10-incident count above [115].

## 4. Cost

### Consumer plans (monthly, USD)

| Vendor | Tier | Price | Includes / caps | Src |
|---|---|---|---|---|
| Anthropic | Free | $0 | chat, web search, artifacts | [31] |
| Anthropic | Pro | $20 ($17 annual) | Claude Code, Design/Slides/Docs/Science, Projects; 5h + weekly caps | [31] |
| Anthropic | Max 5x | $100 | 5x Pro usage per 5-hour session, higher output limits, priority; Claude Code included | [31][32] |
| Anthropic | Max 20x | "From $100" on page (commonly $200 — unverified as of 2026-09-24) | 20x Pro usage per 5h | [31][32] |
| Anthropic | Team / Enterprise | Standard $20/seat annual ($25 monthly), Premium $100/seat annual ($125 monthly); Enterprise $20/seat + usage | SSO, admin, seat allowances on 5h + weekly windows | [31][66] |
| OpenAI | Free / Go / Plus | $0 / $8 / $20 | Codex on all; Astra 5–45 msgs per 5h on Plus | [35] |
| OpenAI | Pro | "$100/month" starting (5x or 20x rate-limit variants) | Astra 25–225 (5x) or 100–900 (20x) msgs/5h | [35] |
| OpenAI | Business | $25 monthly / $20 annual per user | teams 2+ | [35] |
| Google | AI Plus / AI Pro / AI Ultra | $4.99 / $19.99 / $99.99–$199.99 | 2x / 4x / up-to-20x usage; Pro adds Gemini 3.1 Pro 1M ctx, Deep Research, Gemini Spark agent; Ultra adds $40/mo Cloud credits (unverified as of 2026-09-24; not shown on gemini.google/subscriptions) | [39] |
| Google | Gemini CLI on Google login | $0 tier **retired 2026-06-18** (replaced by Antigravity CLI for unpaid/Google One users); AI Pro 1,500 RPD, AI Ultra 2,000 RPD | the old "60 RPM / 1,000 RPD free" figure is dead; the no-cost paths are Antigravity CLI (quota via its `/usage`, numbers not published) and the API-key free tier (250 RPD, Flash only; unpaid terms = data used to improve products) | [102][90][82] |
| xAI | SuperGrok | $30 (Wikipedia; Wikipedia says Grok Build requires it, but x.ai/news/grok-4-7 says Grok Build is free at x.ai/build) | weekly allowance reported to drain after "20-30 simple coding prompts" | [44][60] |
| xAI | Grok Heavy | $300 at launch (Wikipedia) | high-performance variant | [45] |
| xAI | X Premium / Premium+ | Premium+ $40/mo (raised from $22 in Feb 2025, per Wikipedia); Premium price not retrieved | — | [44] |
| Meta | Meta AI | $0 (consumer apps) | no consumer subscription found | [48] |
| Mistral | Le Chat Free / Pro / Student / Team | $0 / $14.99 / $5.99 / $24.99 per user | Free includes $10/mo API credits, Pro $15/mo API credits + full Vibe access | [110] |
| Z.ai | GLM Coding Plan Lite / Pro / Max | from $18 | 5-hour credits 2,000 / 12,000 / 28,000; weekly 10,000 / 60,000 / 140,000; GLM-5.3 costs 3x the credits of GLM-5.3-Flash per token; 50% off-peak outside Mon–Fri 14:00–18:00 SGT; "strictly limited to use within officially supported tools" | [87][86] |
| MiniMax | Token Plan Plus / Max / Ultra | $22 / $55 / $132 | 5-hour rolling + weekly windows, 3–4 / 4–5 / 6–7 concurrent agents; usage shown as a console bar | [93] |

### API prices ($ per 1M tokens)

| Model | Input | Output | Cache read | Cache write (5m / 1h) | Batch | Src |
|---|---|---|---|---|---|---|
| Claude Fable 5.1 | 10.00 | 50.00 | 0.25 | 12.50 / 20.00 | 50% off | [31][30][76] |
| Claude Opus 5.5 | 4.00 | 20.00 | 0.20 | 5.00 / 8.00 | 50% off; fast mode 8/40 | [31][29][76] |
| Claude Sonnet 5 | 2.00 | 10.00 | 0.20 | 2.50 / 4.00 | 50% off; $2/$10 introductory price made permanent (scheduled 2026-09-01 rise to $3/$15 cancelled) | [31][76] |
| Claude Haiku 4.5 | 1.00 | 5.00 | 0.10 | 1.25 / 2.00 | 50% off | [31][76] |
| GPT-6 Astra | 10.00 | 50.00 | 1.00 | 12.50 | 50% off (batch/flex); fast mode 2x; long-context (>272K input tokens) 2x input & cache, 1.5x output ($20/$2/$75) | [33][34] |
| GPT-6 Sol | 2.00 | 10.00 | 0.20 | 2.50 (1.25x input) | " | [33] |
| GPT-6 Luna | 0.10 | 0.50 | 0.01 | 0.125 (1.25x input) | " | [33] |
| GPT-5.6 Sol / Terra / Luna | 4.00 / 2.00 / 0.20 | 20.00 / 12.00 / 1.20 | 0.40 / 0.20 / 0.02 | — | " | [33] |
| Gemini 3.8 Flash | 0.75 (→1.50 from 2027-01-01) | 3.75 (→7.50) | 0.075 (→0.15) | storage $0.50/1M/h (→$1.00) | 50% off; **free tier: $0 per token** ("Free of charge"; RPM/RPD/TPM-limited via AI Studio tiers; data used to improve products) | [37] |
| Gemini 3.5 Flash-Lite | 0.30 | 2.50 | — | — | 50% off; free tier | [37] |
| Gemini 3.1 Pro (preview) | 2.00 (4.00 >200K) | 12.00 (18.00 >200K) | 0.20 (0.40 >200K) | storage $4.50/1M/h | batch=flex 1.00/6.00; priority 3.60/21.60; **no free tier**; Search grounding 5,000 free/mo then $14/1K | [37] |
| Grok 4.7 / 4.6 | 2.00 (4.00 ≥200K) | 6.00 (12.00 ≥200K) | 0.50 | — | fast variant 2x price for 2x speed | [42][43] |
| Grok 4.3 / 4.20 | 1.25 (2.50 ≥200K) | 2.50 (5.00) | 0.20 | — | 1M ctx | [42] |
| grok-build-0.1 | 1.00 | 2.00 | 0.20 | — | 256K ctx | [42] |
| Muse Spark 1.3 | 1.25 | 4.25 | — | — | 1,048,576 ctx; matches the dev.meta.ai figure in `llama-meta.md` (dev.meta.ai/pricing is SSO-gated, so the number here is from OpenRouter's endpoints API); contributor vs standard (no-retention) tiers on 1.2 | [111][48] |
| GLM-5.3 | 1.40 | 4.40 | — | — | 1M ctx; AA cost per index task $2.01 (verbose: 210M output tokens) | [104] |
| GLM-5.3-Flash | 0.15 | 0.50 | 83% cache discount | — | 1M ctx; AA cost per index task $0.25 | [105] |
| Qwen3.8 Max (0902) | 2.00 | 6.00 | — | — | 984K ctx; AA cost per task $5.41 (very verbose) | [106] |
| Kimi K3 | 3.00 | 15.00 | — | — | 1M ctx; AA cost per task $2.00; "particularly expensive" for an open-weight model | [103] |
| DeepSeek V4.1 Flash | 0.30 | 1.20 | 98% cache discount | — | 1M ctx; AA cost per task $0.27 | [107] |
| MiniMax M3 | 0.30 | 1.20 | — | — | 1M ctx; AA cost per task $0.51 | [108] |
| Mistral Medium 3.5 / Large 3 / Small 4 / Codestral | 1.50 / 0.50 / 0.15 / 0.30 | 7.50 / 1.50 / 0.60 / 0.90 | −90% cached input | — | batch 50% off; EU regional inference +10%; Ministral 3 (3B/8B/14B) $0.10/$0.15/$0.20 flat | [109] |

Pricing modifiers that the table does not show:

- **Cache-write TTL**: Anthropic bills 5-minute writes at 1.25x input and 1-hour writes at 2x input ($20 Fable 5.1, $8 Opus 5.5, $4 Sonnet 5, $2 Haiku 4.5 per MTok). This matters here because the subscription lane uses the 1h TTL — a 1h write pays back after two cache reads, a 5m write after one [76][66].
- **OpenAI cache writes** are 1.25x the uncached input rate on every GPT-6 tier (Astra $12.50, Sol $2.50, Luna $0.125); above the **272K-input-token** threshold the whole request bills at 2x input/cache (Astra cache writes $25) and 1.5x output [33][34].
- **Data residency**: Anthropic `inference_geo: "us"` (Claude 4.6+) applies a 1.1x multiplier to every token category, stacking with cache and fast-mode modifiers; Bedrock/Vertex regional endpoints carry a 10% premium; OpenAI charges a 10% uplift on regional-processing endpoints for models released on/after 2026-03-05. Pinning US inference therefore costs ~10% on either vendor; the default global routing is standard price [76][33].
- **Server-side web search**: Anthropic $10 per 1,000 searches plus token costs, web fetch free; OpenAI web search $10 per 1,000 calls plus content tokens at model rates ($25/1K for the preview on non-reasoning models); Gemini Search grounding 5,000 free requests/month then $14 per 1,000 [76][33][37].
- **Gemini cache storage**: 3.1 Pro $4.50 per 1M tokens per hour, 3.8 Flash $0.50 (→$1.00 in 2027). The cost model below ignores storage; a 150K-token cache held for one hour adds ~$0.68/job on 3.1 Pro (more than its $0.48 token cost) and ~$0.08 on 3.8 Flash — do not use explicit caching on 3.1 Pro for short jobs [37].

### Monthly cost estimate for 10 / 100 / 1,000 agent jobs

Assumptions: 150K input + 15K output per job, list price, no caching (and therefore no cache-write or cache-storage charges), no batch, no reasoning overrun, global (non-US-pinned) inference. Two caveats change this materially: (a) thinking tokens bill as output and AA measured Grok 4.7 (xhigh) at ~81K output tokens per index task, roughly 3x Astra's [20][17] — so on max-effort reasoning models multiply the output line by 3–5x; (b) with prompt caching a 70%-cached prefix cuts Opus 5.5 input from $0.60 to ~$0.20/job [30].

| Path | Per job | 10 jobs | 100 jobs | 1,000 jobs | Notes |
|---|---|---|---|---|---|
| (b) API — Claude Fable 5.1 | $2.25 | $22.50 | $225 | $2,250 | $1.50 in + $0.75 out [31] |
| (b) API — Claude Opus 5.5 | $0.90 | $9 | $90 | $900 | batch → $450/1K [31] |
| (b) API — Claude Sonnet 5 | $0.45 | $4.50 | $45 | $450 | [31] |
| (b) API — Claude Haiku 4.5 | $0.23 | $2.25 | $22.50 | $225 | [31] |
| (b) API — GPT-6 Astra | $2.25 | $22.50 | $225 | $2,250 | [33] |
| (b) API — GPT-6 Sol | $0.45 | $4.50 | $45 | $450 | [33] |
| (b) API — GPT-6 Luna | $0.02 | $0.23 | $2.25 | $22.50 | [33] |
| (b) API — Grok 4.7 | $0.39 | $3.90 | $39 | $390 | reasoning overrun risk high [42][20] |
| (b) API — Gemini 3.8 Flash (paid) | $0.17 | $1.69 | $16.90 | $169 | promo pricing through 2026-12-31 [37] |
| (b) API — Gemini 3.8 Flash (free tier) | $0 | $0 | $0 | $0 | RPM/RPD/TPM-limited (limits visible only in AI Studio), data used to improve products [37][40] |
| (b) API — Gemini 3.1 Pro | $0.48 | $4.80 | $48 | $480 | [37] |
| (b) API — GLM-5.3-Flash | $0.03 | $0.30 | $3.00 | $30 | AA 42 vs Gemini 3.8 Flash 41 — see §5 head-to-head [105] |
| (b) API — Mistral Small 4 | $0.03 | $0.32 | $3.15 | $32 | AA 11 — cheap but not frontier [109] |
| (b) API — DeepSeek V4.1 Flash / MiniMax M3 | $0.06 | $0.63 | $6.30 | $63 | AA 39 / 29 [107][108] |
| (b) API — GLM-5.3 | $0.28 | $2.76 | $27.60 | $276 | AA 45; verbose (3x Flash credits on the coding plan) [104] |
| (b) API — Muse Spark 1.3 | $0.25 | $2.51 | $25.10 | $251 | AA 48 — cheapest model in the AA top 20 [111] |
| (b) API — Mistral Medium 3.5 | $0.34 | $3.38 | $33.75 | $338 | AA 14 [109] |
| (b) API — Qwen3.8 Max | $0.39 | $3.90 | $39 | $390 | AA 45; reasoning-overrun risk (190M output tokens on the index) [106] |
| (b) API — Kimi K3 | $0.68 | $6.75 | $67.50 | $675 | AA 44; slow (35 tok/s) [103] |
| (a) Sub — GLM Coding Plan Lite | $18 | $18 | $18 | capacity-bound | 10,000 weekly credits; a 150K/15K GLM-5.3-Flash job ≈ 46 credits, GLM-5.3 ≈ 140 → Lite covers ~200 Flash or ~70 GLM-5.3 jobs/week [87] |
| (a) Sub — MiniMax Token Plan Plus | $22 | $22 | $22 | capacity-bound | 5h + weekly windows; quota numbers not published, console bar only [93] |
| (a) Sub — Claude Max 5x / 20x | flat | $100 / ~$200 | $100 / ~$200 | capacity-bound | 1,000 jobs ≈ 33/day ≈ 5M tokens/day; almost certainly exceeds Max 20x weekly cap → spills to usage credits at API rates [32][69] |
| (a) Sub — ChatGPT Pro 20x | flat | $100+ (20x tier price unverified) | $100+ | capacity-bound | Astra 100–900 msgs/5h; a job is many "messages", so budget Sol/Luna for bulk [35] |
| (a) Sub — Google AI Pro + Gemini CLI / Antigravity | $19.99 | $19.99 | $19.99 | capacity-bound | **1,500 req/day** on AI Pro (2,000 on AI Ultra) — the old "1,000 RPD free" login tier was retired 2026-06-18 and only survives as the Code Assist Individual row the quota page still prints; agent prompts = multiple requests; Antigravity on the same plan refreshes its quota every 5 h until the weekly limit (§3, §7 concurrency table) [102][41][148] |
| (a) Sub — SuperGrok | $30 | $30 | ? | not viable | weekly allowance reported exhausted after ~20–30 prompts [44][60] |

Calibration caveat (added 2026-09-24): the 150K/15K job and the 0% cache assumption are synthetic, and the sibling docs use 60–90% cache assumptions that are not reconciled with this table. The subscription-vs-metered verdict flips on three numbers this research set never measured — real jobs/month, tokens/job and cache-hit share from `volumes/audit_log/*.jsonl`, plus the owner's current Max tier (5x vs 20x) and existing seats. §7 "Empirical calibration" gives the one-command recipe; until it is run, treat every row here as an ordering, not a budget.

Reading: at 10–100 jobs/month a single Claude Max plan already covers the Anthropic path at flat cost; at 1,000 jobs/month the honest comparison is API metering, where Opus 5.5 ($900) sits between GPT-6 Sol ($450) and Astra ($2,250). At the cheap end the ordering is GLM-5.3-Flash ($30) < DeepSeek V4.1 Flash / MiniMax M3 ($63) < Gemini 3.8 Flash ($169) < Muse Spark 1.3 ($251) — Gemini 3.8 Flash is no longer the cheapest frontier-class option once the second-tier models are on the table, and its free tier is now 250 requests/day, Flash only [102].

## 5. Strengths & weaknesses per reviews

### Leaderboard tables (top entries, with who ran them)

**Composite / preference**

| Leaderboard (date) | #1 | #2 | #3 | Notes | Src |
|---|---|---|---|---|---|
| AA Intelligence Index v4.3.2 (2026-09-24, independent) | Claude Opus 5.5 max 58 | Opus 5.5 xhigh 56 | Opus 5.5 high 54; then Fable 5.1 max/xhigh 53, GPT-6 Astra max 53, Astra xhigh 52 | Muse Spark 1.3 max 48, GPT-6 Sol max 48, Grok 4.7 xhigh 46 (#21), then the second tier: GLM-5.3 max 45, Qwen3.8 Max 45 (#24/210), Kimi K3 max 44, GLM-5.3-Flash 42, Gemini 3.8 Flash high 41 (rank #40 unverified as of 2026-09-24 — leaderboard fetch placed it ~#33), DeepSeek V4.1 Flash max 39, GPT-6 Luna max 37, MiniMax M3 29, Mistral Medium 3.5 14 / Small 4 11 / Large 3 9; Anthropic holds 9 of top 15 | [1][16][17][18][19][103][104][105][106][107][108] |
| Arena text (2026-09-13, 8.1M votes, independent) | claude-fable-5-high 1506±5 | claude-opus-4-6-high 1505±4 | claude-opus-4-7-high 1502±4 | muse-spark-1.2 xhigh 1500±11 (#4), fable-5.1-max 1498±8, gemini-3.8-flash-high 1493±9, gemini-3.1-pro-preview 1487±3 (#15, 107K votes); GPT-6 and Grok 4.7 absent from top 15 | [2] |
| Arena WebDev (independent) | Claude Opus 5.5 max 1818 | GPT-6 Astra max 1792 | Claude Fable 5.1 max 1755 | Opus 5 max 1692, GPT-6 Sol max 1686 | [3] |
| Arena Vision (2026-09-13) | claude-fable-5-high 1310±8 | qwen3.8-max 1302±8 | claude-opus-4-7-high 1301±7 | muse-spark-1.3-max 1294±15 | [4] |
| Arena text coding category | Not found — searched: arena.ai/leaderboard/text?category=coding (category view not rendered server-side) | | | | |

**Coding / terminal / agentic**

| Benchmark (date) | Top results | Run by | Src |
|---|---|---|---|
| SWE-bench Verified (Vals, 2026-09-01) | Claude Opus 5 97.0%, DeepSeek V4 Pro 0813 96.4%, Kimi K3 93.4%; 7 of 86 models ≥95% — **saturated**; Opus 4.8 88.6%, Grok 4.5 86.6% | independent | [12] |
| SWE-bench Pro public (Scale) | Muse Spark 1.1 61.5±3.1, gpt-5.4 xhigh 59.1±3.6, Muse Spark 55.0, claude-opus-4-6 thinking 51.9, gemini-3.1-pro 46.1 — Sept-2026 models not yet listed | independent (mixed harnesses, some mini-swe-agent) | [6] |
| Terminal-Bench 4.0 (self-reported by Anthropic, 2026-09-22) | Opus 5.5 66.4%, GPT-6 Astra 57.9%, Fable 5.1 55.8%, Opus 5 52.3%, GPT-5.6 Sol 37.3%; xAI self-reports Grok 4.7 37.6% | self-reported | [29][43] |
| Terminal-Bench 2.0 leaderboard | Not found — searched: tbench.ai/leaderboard (now shows 4.0 only, table client-rendered), tbench.ai/leaderboard/terminal-bench/2.0, hub.harborframework.com, vals.ai/benchmarks/terminal_bench | | |
| AA Coding Agent Index v1.5 | ranking text not retrievable; AA article: Grok 4.7 + Grok Build = 56, "4th among native implementations behind Claude Fable 5.1, GPT-6 Astra, Claude Opus 5" | independent | [20] |
| Aider polyglot (stale, last entry 2025-10) | gpt-5 high 88.0% — not updated for 2026 models | independent | [73] |
| FrontierCode v1.1 / CursorBench 4.0 (self-reported) | Opus 5.5 54.4% / 57.8%; Astra 53.3% / —; Fable 5.1 50.3% / 51.8%; Grok 4.7 CursorBench 46.3% | self-reported | [29][43] |
| Vals Excel Modeling (2026-09-22) | Fable 5.1, Opus 5.5, Fable 5 (top 3) | independent | [10] |

**Reasoning / knowledge**

| Benchmark (date) | Top results | Run by | Src |
|---|---|---|---|
| HLE (Scale, statistical ranks) | GPT-6 Astra 54.80±1.94; Fable 5.1 xhigh 46.50, gemini-3.1-pro thinking-high 46.44, Gemini 3.8 Flash 44.52, gpt-5.4-pro 44.32; Muse Spark 40.56; claude-opus-4-7 36.20 | independent | [5] |
| HLE (AA, 2,158 text-only Qs) | Opus 5.5 max 61.4%, Fable 5.1 max 59.1%, Fable 5.1 xhigh 58.7% | independent | [14] |
| HLE (Anthropic self-report) | Opus 5.5 67.7%, Fable 5.1 65.6%, Opus 5 63.6%, Astra 57.2% | self-reported | [29] |
| GPQA Diamond (AA) | GPT-6 Astra xhigh 96.3%, Astra max 96.1%, Gemini 3.8 Flash high 95.3% | independent | [15] |
| GPQA Diamond (Vals, 2026-09-01) | Gemini 3.1 Pro Preview 95.45%; 24 of 136 models ≥90% — **saturated** | independent | [13] |
| ARC-AGI-3 (ARC Prize, 2026-09-03) | GPT-6 Astra 62.7% semi-private on standard harness ($26,098); 99.9% with OpenAI's Provider Adapter harness ($18,817); baseline May 2026: GPT-5.5 0.43%, Opus 4.7 0.18% | independent (harness supplied by vendor for the 99.9%) | [23][24] |
| ARC-AGI-2 (current) | Not found — searched: arcprize.org/leaderboard, arcprize.org/arc-agi/2/, arcprize.org/blog (tables client-rendered) | | |
| FrontierMath Erdős (Epoch, 2026-09-03) | GPT-6 Astra 3% | independent | [75] |
| METR 50% time horizon | numeric values not retrievable (interactive chart); page last updated 2026-05-08 with Claude Mythos Preview and Gemini 3.1 Pro added; "measurements above 16 hrs are unreliable"; Opus 4.7, Grok 4.3, GPT-5.5 listed without horizons; METR's Opus 5.5 pre-deployment note: "not a huge leap in AI R&D capability above Fable 5.1, but likely a modest improvement" | independent | [26][27] |

**Agents / tool use / long-horizon**

| Benchmark (date) | Top results | Run by | Src |
|---|---|---|---|
| Vending-Bench 2 (Andon Labs) | GPT-6 Astra $15,515±1,074; Claude Opus 5 $11,182±2,094; Opus 4.7 $10,937; GPT-5.6 Sol $9,619; Grok 4.6 $9,047; GLM-5.2 $8,314 | independent | [7] |
| τ²-bench (site leaderboard, stale) | Qwen 3.5-397B-A17B 87.9%, Gemini 3.0 Pro 85.4%, Claude Opus 4.5 85.3% — no 2026-09 models | independent | [9] |
| AA-Briefcase v1.1 (agentic knowledge work) | Opus 5 and Fable 5.1 lead; Grok 4.7 1,657 Elo just behind | independent | [20] |
| GDPval-AA v2.1 / AutomationBench (self-reported) | Opus 5.5 1846 / 40.0%; Fable 5.1 1735 / 31.4%; Astra 1542 / 41.4% | self-reported | [29] |
| OSWorld 2.0 (self-reported) | Opus 5.5 81.8%, Fable 5.1 80.7%, Opus 5 74.0% | self-reported | [29] |
| BrowseComp | Not found — searched: openai.com (403), vals.ai/benchmarks/web_search_index (404), anthropic.com/claude-opus-5-5 (not listed), deepmind.google (not listed) | | |

**Speed / price (AA, independent)** [22][19][17][18]: fastest output Celeris-1 1,513 tok/s, Mercury 2.5 781, Gemini 3.5 Flash-Lite 351; among frontier reasoning models Gemini 3.8 Flash 297 tok/s (#1), Opus 5.5 ~90 (high/xhigh), Fable 5.1 56–66, Astra 52 (#133 of 210, with a 352 s TTFT at max), Grok 4.7 40 (#160) — note AA's own benchmarking article states "approximately 188 tokens/second for long prompts", so the two AA measurements differ (leaderboard 40.1 tok/s vs article 188 tok/s; unverified which is current as of 2026-09-24) [20]. Second tier (AA model pages, v4.3.2): DeepSeek V4.1 Flash 232 tok/s / 0.92 s TTFT, MiniMax M3 145 / 1.28 s, GLM-5.3 60 / 3.45 s, GLM-5.3-Flash 43 / 3.67 s, Qwen3.8 Max 39 / 3.03 s, Kimi K3 35 / 3.79 s ("notably slow"); Mistral Small 4 170 / 0.77 s, Medium 3.5 149 / 2.31 s, Large 3 77 / 1.10 s; Gemini 3.8 Flash (high) 292 / **14.7 s**; GPT-6 Luna (max) 141 / 108 s [103][104][105][106][107][108][109]. Cheapest per AA task: GPT-6 Luna low $0.0045. Cost to run the whole Intelligence Index: Opus 5.5 max $5.98 vs Astra max $3.26 vs Grok 4.7 $3.74 vs Gemini 3.8 Flash $1.24 vs GLM-5.3 $2.01 vs Kimi K3 $2.00 vs Qwen3.8 Max $5.41 vs MiniMax M3 $0.51 vs DeepSeek V4.1 Flash $0.27 vs GLM-5.3-Flash $0.25.

### Cheap-frontier head-to-head (the test verdict 3 previously skipped)

| Model | AA v4.3.2 | $ in / out per 1M | AA cost per index task | tok/s | TTFT | Free tier / plan | Verdict | Src |
|---|---|---|---|---|---|---|---|---|
| GLM-5.3-Flash | 42 | 0.15 / 0.50 (83% cache discount) | $0.25 | 43 | 3.7 s | GLM Coding Plan from $18 (2.3x/8x credit multipliers) | **best $/intelligence**; slow output, 3.7 s TTFT | [105][87] |
| Gemini 3.8 Flash (high) | 41 | 0.75 / 3.75 (→1.50/7.50 in 2027) | $1.24 | 292 | 14.7 s | API key: 250 RPD, Flash only, unpaid terms | 5x the price of GLM-5.3-Flash for +0 points; wins only on throughput and multimodal input | [19][37][102] |
| DeepSeek V4.1 Flash (max) | 39 | 0.30 / 1.20 (98% cache) | $0.27 | 232 | 0.9 s | none | best latency in the tier; 3 points below GLM-5.3-Flash | [107] |
| GPT-6 Luna | 37 (max) | 0.10 / 0.50 | $0.0045 (low) | 141 | 108 s at max | ChatGPT plan: 350–3,000 msgs/5h on Plus | cheapest per task at low effort; unusable at max for chat | [33][35] |
| MiniMax M3 | 29 | 0.30 / 1.20 | $0.51 | 145 | 1.3 s | Token Plan from $22 | fast, cheap, 10+ points behind | [108][93] |
| Mistral Small 4 | 11 | 0.15 / 0.60 | — | 170 | 0.8 s | Le Chat Free $10/mo API credits | not frontier-class; EU-hosted option | [109][110] |

Reading: on the AA index the cheap frontier is GLM-5.3-Flash, not Gemini 3.8 Flash — same intelligence band, $0.25 vs $1.24 to run the index, $30 vs $169 per 1,000 jobs. Gemini 3.8 Flash keeps two things GLM-5.3-Flash lacks: 7x the output speed (292 vs 43 tok/s, though with a 14.7 s TTFT at high effort) and audio/video input. DeepSeek V4.1 Flash is the latency pick. The data-handling matrix in §7 is the other half of this decision (GLM's retention terms are unpublished; Gemini paid tier has processor terms).

### Interactive-surface latency (Telegram round trip)

Rating anchors: a Telegram reply that starts within ~2 s and streams at ≥60 tok/s reads as live; 2–5 s TTFT is tolerable with a typing indicator; >10 s TTFT needs a "working…" placeholder message; >60 s is batch-only. TTFT figures are AA's for the effort level named; lower effort shortens them.

| Model (effort) | TTFT | tok/s | Telegram rating | Src |
|---|---|---|---|---|
| Mistral Small 4 | 0.77 s | 170 | live | [109] |
| DeepSeek V4.1 Flash (max) | 0.92 s | 232 | live | [107] |
| Mistral Large 3 | 1.10 s | 77 | live | [109] |
| MiniMax M3 | 1.28 s | 145 | live | [108] |
| Mistral Medium 3.5 | 2.31 s | 149 | live (borderline) | [109] |
| Qwen3.8 Max | 3.03 s | 39 | typing-indicator; slow stream | [106] |
| GLM-5.3 (max) | 3.45 s | 60 | typing-indicator | [104] |
| GLM-5.3-Flash | 3.67 s | 43 | typing-indicator; slow stream | [105] |
| Kimi K3 (max) | 3.79 s | 35 | typing-indicator; slow stream | [103] |
| Claude Sonnet 5 (low / medium) | 1.80 s / 2.36 s | 64 / 67 | **live** at low, live-borderline at medium — the primary Telegram setting; high 8.5 s, xhigh 17.4 s, max 150 s | [22][153] |
| Claude Opus 5.5 (low / medium) | 5.18 s / 21.4 s | 83 / 79 | typing-indicator at low; placeholder at medium and above (high 34.9 s, xhigh/max 142 s) | [22] |
| Claude Haiku 4.5 (standard / reasoning) | 0.63 s / 22.1 s | 87 / 104 | live without thinking; placeholder with | [22] |
| Claude Fable 5.1 (low / medium) | 6.29 s / 11.9 s | 56 / 57 | typing-indicator at low; placeholder above (high 20.9 s, xhigh 110 s, max 265 s) | [22] |
| Gemini 3.8 Flash (high) | 14.7 s | 292 | placeholder at high; use low/medium effort for chat | [19] |
| Grok 4.7 (xhigh) | — | 40 | placeholder (token-hungry) | [18] |
| GPT-6 Luna (max) | 108 s | 141 | batch-only at max; low effort is the chat setting | [33] |
| GPT-6 Astra (max) | 352 s | 52 | batch-only | [17] |

Chat-surface conclusion: no frontier model at high effort is a live Telegram model. The Claude numbers are now measured (AA speed view, 2026-09-24): Sonnet 5 at low effort is the only Anthropic configuration under 2 s TTFT (1.80 s, 64 tok/s), medium is 2.36 s, and Opus 5.5 is 5.2 s even at low — so the primary Telegram lane is **Sonnet 5 low/medium**, with Haiku 4.5 non-thinking (0.63 s) as the cheap fallback, never Opus 5.5 above low. Gemini 3.8 Flash low, Luna low, DeepSeek V4.1 Flash and MiniMax M3 remain the cross-vendor chat picks; long reasoning is deferred to a job with a progress message. (This replaces the earlier "typing-indicator (assumed)" cell and the sibling docs' unsourced "sub-2 s typical" for Claude.) [22][153]

### Tool churn (operational cost of ownership per lane)

| Lane / tool | Releases, Aug 25 → Sep 24 2026 | Breaking or default-changing items in window | Burden | Src |
|---|---|---|---|---|
| Claude Code | 10 stable releases Sep 14–23 (v2.1.271→2.1.281), ~every 1–2 days | Opus 5.5 became default Opus (2.1.280); auto-mode moved to a server-side classifier by default (2.1.278, `CLAUDE_CODE_DISABLE_AUTO_MODE_SERVER=0` to opt out); AGENTS.md read when no CLAUDE.md (2.1.277); `--bare` semantics (requires API key) already noted in §3 | high cadence, additive; pin a version and read notes weekly | [97][64] |
| Codex CLI | stable 0.156.1 (Sep 23) after 0.155; multiple alpha builds per day (0.157/0.158 alphas Sep 23–24) | rate-limit switch prompt now recommends GPT-6 Luna (changes which model a plan-auth job silently falls to) | weekly stable; pin, and set the model explicitly | [98] |
| Gemini CLI | v0.61.0 (Sep 23), previews and nightlies daily | free Google login removed 2026-06-18 (policy, not a CLI release); OAuth handling refinements; 3.8 Flash / 3.5 Flash-Lite added | monthly minor; the auth-policy change was the breaking event | [99][102] |
| Antigravity CLI | current 2.5.0; sibling docs count 10 releases in 13 days; changelog page 404 on 2026-09-24 | headless flags (`-p`, `--output-format`, `--json-schema`) are Claude-Code-shaped | very high cadence, unversioned docs | [90][91] |
| Grok Build | open-sourced 2026-07-16; `grok-build-0.1` model; cadence not retrievable | July repo-upload behaviour disabled Jul 14 | unknown cadence; young | [44][92] |
| DeepSeek Harness | "developer preview" | no compatibility promise in the fetched docs (sibling doc records a "WILL BREAK" warning) | preview: expect breakage | [100] |
| Perplexity Sonar API | **Sonar Chat Completions sunset confirmed: "Sonar will be supported until September 27, 2026"** (migration page; all Sonar / Sonar Pro / Sonar Reasoning Pro / Sonar Deep Research variants) — the September changelog does not list it, which is why the earlier pass flagged it; the changelog is not the authoritative page. Successor is the Agent API (OpenAI/Anthropic/xAI model catalogue) | Sonar endpoint dies in 3 days; any Sonar-shaped integration must move to the Agent API now | [118][101] |
| GLM / MiniMax / Kimi coding plans | consumed through Claude Code, Kimi Code CLI or Anthropic-compatible endpoints | churn is upstream (Claude Code's) plus each vendor's credit multipliers | inherits Claude Code cadence | [87][93][95] |
| Mistral | Devstral and Magistral moved to the deprecated list with named successors | model deprecations, not tooling | low | [109] |

### Review consensus and "best for X"

- **Coding/agentic**: consensus favours Claude (Opus 5.5 for long multi-step work; Anthropic's own guidance: "Opus 5.5 keeps going on long, multi-part work better than Opus 5 did" [74]); HN: "I have the impression that Anthropic's models are better at this than OpenAI's" (gjm11) [58]. Willison now defaults to "GPT-6 Sol and Opus 5.5 for general development tools" [52]. Astra's edge is cost-per-capability: "Astra equals Fable 5.1 in the Intelligence Index at ~40% of the cost, and in the Coding Agent Index at ~60% of the cost" (forgot-my-pw, HN) [58] — consistent with AA's 53 vs 53 [1].
- **Code review specifically**: CodeRabbit measured Opus 5.5 catching 63.8% of 80 OSS patterns vs 61.3% baseline, 8/13 vs 5/13 on hard cases, but precision slightly lower (38.6% vs 39.3%; 35.7% at max), and ~40–49% more tokens consumed, offsetting the 20% price cut; "switching reviewers changes which bugs slip through" [57].
- **Research/reasoning**: Astra leads Scale HLE, AA GPQA, ARC-AGI-3, FrontierMath, Vending-Bench 2 [5][15][23][75][7]; Raschka attributes gains to "improved training recipes and training data" rather than the looped-transformer architecture, and flags "reduced monitorability of reasoning traces" [56]. Anthropic counters on its own HLE numbers (67.7% vs Astra 57.2%) — self-reported and inconsistent with Scale's 54.8 for Astra vs 46.5 for Fable 5.1 (likely tool/config differences) [29][5].
- **Writing/preference**: Arena text top 10 is Anthropic + Muse Spark + Gemini Flash; GPT-6 absent [2]. Willison: Opus 5.5 has "improved communication style and token efficiency" [52].
- **Speed/cheap**: Gemini 3.8 Flash — "fast, cheap, and competent at things like HTML and JavaScript", interactive components "in approximately 13 seconds for under 2 cents" (Willison) [55]; GPT-6 Luna "fast and competent" for SQL/web [52].
- **Weaknesses**: Opus 5.5 at max effort "exhausted its 128,000-token output limit on a simple pelican-drawing task… max reasoning is effectively useless for practical work" (Willison) [52]; HN Opus 5.5 thread is dominated by refusal/safeguard and trust complaints ("became much more sycophant and eager to change stuff as it guessed I want" — aytigra) [59]; Opus 4.7 had 35 unwarranted-refusal reports in April 2026 [47]. Astra: 352 s TTFT at max, hidden reasoning, "spit out falsehoods and errors regularly in the handful of fields I have expertise in" (NateEag) [17][58]. Grok 4.7: slow on the AA leaderboard (40 tok/s; AA's article says ~188 tok/s for long prompts — see §5 speed note), token-hungry (~81K out/task), regressions on AA-LCR and AutomationBench, 29% hallucination rate on AA-Omniscience; HN thread is mostly political and quota complaints [18][20][60].
- **Controversies**: Grok Build uploaded whole repos including secrets to SpaceXAI storage ("27,800 times more data than needed", Jul 2026; see the §2 access reconciliation); CSAM litigation; DoD integration [44]. Anthropic: 200+ shared chats indexed by Google (Jul 2026), DoD blacklisting dispute, export-control episode Jun 2026 [47]. Google: Nano Banana/Google Earth withdrawn within 24h (Jul 2026) [49]. OpenAI: a 23h API degradation (Sep 17) plus a ~20h GPT-5.6 incident; September incident totals unverified as of 2026-09-24 [71].
- **Cost pressure sentiment**: HN "Best AI coding plan alternative to Claude and ChatGPT" (May 2026) — users defecting to GLM/Kimi/MiniMax coding plans over "reduced usage limits" [61]; weekly limits introduced 2025-08-28 (609-point HN thread) [62]; "Claude has the worst pricing – but people want it" (Jul 2026) [62].

### Benchmark-gaming caveats

1. **Arena is gameable**: "The Leaderboard Illusion" documented 27 private Meta variants pre-Llama-4, ~20% of battles each for Google/OpenAI vs 29.7% for 83 open models, and "up to 112%" relative gains from arena-distribution data [63]. Arena also excludes GPT-6/Grok 4.7 from its 2026-09-13 top 15, which may reflect submission timing rather than quality [2].
2. **Saturation**: SWE-bench Verified (7 models ≥95%) and GPQA Diamond (24 models ≥90%) no longer discriminate at the frontier; prefer SWE-bench Pro, Terminal-Bench 4.0, AA-Briefcase, Vending-Bench 2 [12][13].
3. **Harness effects**: ARC-AGI-3 for Astra is 62.7% or 99.9% depending on whether OpenAI's own adapter is used [23]; SWE-bench Pro mixes mini-swe-agent with other harnesses [6].
4. **Self-report vs independent**: Anthropic's launch table (Terminal-Bench 4.0, HLE, OSWorld, GDPval) and xAI's (Terminal-Bench 4.0, CursorBench) are self-reported; AA, Scale, Vals, Andon, ARC Prize, METR, Epoch are independent. Where both exist they disagree (HLE: 67.7 self vs 61.4 AA vs Scale not-yet-listed for Opus 5.5) [29][14][5].
5. **Index versioning**: AA's index numbers shift with version; Willison quoted Astra 61 vs Fable 5.1 66 on 2026-09-03, while v4.3.2 on 2026-09-24 shows 53 vs 53 — compare only within one version [53][1].
6. **HLE curation bias**: AA notes HLE's authors selected questions adversarially against specific models [21].
7. **Effort/verbosity confounds**: max-effort variants top the tables but cost 3–10x in output tokens (Fable 5.1 max 65,927 tokens for one SVG) [54].

## 6. Finance / trading relevance

- **Finance-specific evals (independent, Vals)**: Finance Agent v2 (2026-09-23, 68 models): top 3 Gemini 3.8 Flash, Muse Spark 1.2, Muse Spark 1.3 Max; Google self-reports 61.4% for 3.8 Flash [10][50]. Finance Agent v1.1 (2026-06-04): Claude Opus 4.7 64.37%, Sonnet 4.6 63.33%, Muse Spark 60.59%, DeepSeek V4 60.39% — entry-level-analyst tasks, 537 questions across retrieval, market research, projections [11]. Excel Modeling (2026-09-22): Fable 5.1, Opus 5.5, Fable 5. Tax Agent (2026-09-23): Fable 5.1, Opus 5, GLM 5.3. CorpFin v2 exists but its page was not retrievable [10].
- **FinanceBench** (Patronus): 10,231 questions over 10-K/10-Q/8-K/earnings calls, 150 open; original finding "GPT-4-Turbo… incorrectly answered or refused to answer 81% of questions"; **no public leaderboard** — contact Patronus for full-set evals [72].
- **Long-horizon economic agency**: Vending-Bench 2 — Astra $15.5K vs Opus 5 $11.2K vs Grok 4.6 $9.0K [7]; AA-Briefcase (agentic knowledge work Elo) — Opus 5 / Fable 5.1 lead, Grok 4.7 close [20]. These are the closest public proxies for "run a research desk unattended"; no public benchmark measures live-trading P&L credibly (nof1 Alpha Arena page returned 403).
- **Real-time data**: Gemini API has Google Search grounding (5,000 free requests/mo, then $14/1K) [37]; Grok is "trained to natively understand the Grok Bot harness" and is the only vendor with native X firehose sentiment, but the announcement gives no API detail [43]; Claude has web search in the app and via Claude Code tooling, and on the API as a server-side tool at $10 per 1,000 searches (web fetch free); OpenAI's API web search is also $10 per 1,000 calls plus content tokens; none of the vendors ships a market-data connector — bring Alpaca/Tradier/Finnhub via MCP or CLI.
- **Restrictions**: Anthropic's Opus 5.5 launch added cyber/life-science safeguards with verification programs; "most flagged messages move to an older model" [29][74]; Astra shipped with cyber-prompt refusals [46]. No vendor restricts paper-trading research; live order placement is a server-policy matter here, not a vendor one.
- **Hallucination**: AA-Omniscience hallucination rate is the number to watch for research desks — Grok 4.7 29% (vs 34% for 4.6) [20]; Anthropic's HN critics stress reliability over benchmark gains [59].

## 7. Integration recipe for our server

Recommended shape given the owner's constraints (Claude Max, no Anthropic API key, subscriptions-first, free tiers welcome):

1. **Primary lane stays Claude Agent SDK on the Max login** (already in place). Route by effort, not model: Opus 5.5 `medium` (default) for coding/build jobs, `high` for adversarial review, Fable 5.1 only when Opus at `xhigh` fails evals; never `max` for unattended jobs (Willison's 128K-output exhaustion) [30][52]. Keep `--bare` OFF (it forces an API key) but pass `--permission-prompts none --permission-mode auto --output-format stream-json --max-budget-usd` and parse `api_retry` events with `error: rate_limit` to back off to the 5-hour reset; the Opus 5.5 launch added a saveable rate-limit reset on Pro/Max/Team, so the backoff strategy can hold one reset in reserve for a stuck deploy or review rather than spending it on a scheduled batch [64][29]. The operative policy text for this lane is the "Using Agents According to Our Usage Policy" support article, not just the Consumer Terms clause [77].
2. **Second opinion lane — OpenAI via Codex CLI, plan auth by default, API key when a second person is served**: this reconciles the earlier CODEX_API_KEY-only recipe with `chatgpt-openai.md`'s plan-auth recommendation. Default: `codex login` on the server once (device-code auth is in beta; the documented fallback is copying `~/.codex/auth.json` from an authenticated machine), then `codex exec "$PROMPT" --json --output-schema review.json --sandbox read-only --ephemeral` on the ChatGPT Pro allowance — flat cost, consistent with the subscriptions-first constraint [89][36][35]. Switch to `CODEX_API_KEY` for (a) any job whose output is consumed by someone other than the owner (OpenAI's "great for automation in shared environments" guidance and the serves-a-second-person rule), (b) anything that must not fall to Luna — Codex 0.156.1's rate-limit switch prompt now recommends GPT-6 Luna, so set `--model` explicitly on plan auth [98]. Sol at $2/$10 is the budget reviewer, Astra for the hard cases [33]. Remaining allowance: `/status` in a TUI session only; no quota API [35].
3. **Bulk/cheap lane — GLM-5.3-Flash first, Gemini 3.8 Flash for multimodal, Antigravity CLI for the no-cost Google path**: the §5 head-to-head puts GLM-5.3-Flash (AA 42, $0.15/$0.50, $0.03/job) ahead of Gemini 3.8 Flash (AA 41, $0.75/$3.75, $0.17/job) for classification, routing, summarising and first-pass triage; use the GLM Coding Plan Lite ($18, ~200 Flash jobs/week) or metered Z.ai [105][87]. Keep Gemini 3.8 Flash for audio/video input and for throughput-bound jobs, on a paid API key (processor terms) [37][82]. The Gemini CLI free-Google-login lane recommended earlier **does not exist any more** (retired 2026-06-18): the free Google path is Antigravity CLI (`agy -p … --output-format json`, quotas unpublished, `/usage` TUI) or the API-key free tier (250 RPD, Flash only, data used to improve products — never proprietary Atlas research) [102][90][91]. DeepSeek V4.1 Flash ($0.30/$1.20, 0.9 s TTFT) is the latency pick when the chat lane needs a cheap fast model [107]. Avoid explicit context caching on Gemini 3.1 Pro — $4.50/1M/h storage exceeds its token cost for short jobs [37].
4. **Optional — Grok 4.7 API for X-sentiment probes only**; not for coding (slow, verbose) [18][20]. Grok Build is on every plan (§2) and has a headless mode, but its July repo-upload history keeps it off private repos [92][44].
5. **Second-tier reasoning alternates** for cross-vendor review when OpenAI is rate-limited: GLM-5.3 (AA 45, $1.40/$4.40) or Muse Spark 1.3 (AA 48, $1.25/$4.25 via OpenRouter) — both cheaper than Sol per job and from different training lineages, which is the point of a second reviewer; Kimi K3 (AA 44) is not worth $3/$15 and 35 tok/s; Qwen3.8 Max (AA 45) is Arena Vision #2 and the pick for image-heavy review [104][111][103][106][4].

Minimal Python sketch (Claude lane, structured output + budget guard) [65]:

```python
from claude_agent_sdk import query, ClaudeAgentOptions
opts = ClaudeAgentOptions(
    model="claude-opus-5-5", permission_mode="acceptEdits",
    allowed_tools=["Read","Edit","Bash(pytest *)"], max_turns=40,
    max_budget_usd=3.0, cwd="/path/to/project",
    output_format={"type":"json_schema","schema":{"type":"object",
        "properties":{"verdict":{"type":"string"},"findings":{"type":"array"}},
        "required":["verdict"]}})
async for m in query(prompt="Review the diff for correctness bugs", options=opts):
    ...  # final ResultMessage expected to carry structured_output + total_cost_usd (unverified as of 2026-09-24 — fetched SDK page truncated; the option fields above are confirmed)
```

Codex lane one-liner (plan auth, model pinned): `git diff main | codex exec --model gpt-6-sol --json --output-schema schema.json --sandbox read-only "review this diff"`; prefix `CODEX_API_KEY=$K` only on the serves-others path [36][89]. Cheap lane: GLM-5.3-Flash through the Anthropic-compatible coding-plan endpoint inside Claude Code, or Antigravity: `agy -p "classify: $TEXT" --output-format json --effort low` — the installed binary is `agy` (every example on the headless page uses it; `antigravity` is the product name, not a command) [87][91].

### Data-handling matrix per lane and auth mode

| Lane (auth) | Training use | Retention | Residency | ZDR | Fit for proprietary theses (paper-trading lab) | Src |
|---|---|---|---|---|---|---|
| **Claude Max — Claude Code / Agent SDK on subscription OAuth** (primary lane) | Consumer terms; "Model Improvement" is a user toggle, **opt-in**, and it covers Claude Code sessions from Pro/Max accounts when on | 30 days with the toggle off; **5 years** with it on | global (no `inference_geo` on the subscription path) | not available (Enterprise-only) | OK with the toggle off (verify at claude.ai/settings/data-privacy-controls); Claude Code also caches transcripts locally in plaintext under `~/.claude/projects/` for 30 days | [79][80] |
| Claude API / Team / Enterprise | no training | 30 days | `inference_geo: "us"` at 1.1x | qualified Enterprise orgs only | OK | [80][76] |
| ChatGPT plan — Codex on plan auth | consumer data controls; not re-fetched this pass (openai.com terms 403) — see `chatgpt-openai.md` | — | — | no | treat as unknown until the sibling doc's terms are confirmed; use the API key for theses | [89] |
| OpenAI API (`CODEX_API_KEY`) | no training unless opted in | 30-day abuse logs; `/v1/conversations` stores until deleted | US/EU/UK/JP/… regional processing at +10% | eligible endpoints incl. chat/completions, responses, embeddings | OK | [81][33] |
| Gemini API — paid key | not used to improve products; processor DPA | "limited period" abuse logs; grounding data 30 days | Google Cloud regions (Vertex) | via Vertex terms (unverified) | OK on paid key only | [82] |
| Gemini API — unpaid key / Antigravity CLI on a Google account | **used "to provide, improve, and develop Google products"**; Google may "generate the same or similar content for others" | not stated | — | no | **never** | [82][102] |
| xAI API / Grok Build | **"xAI never trains on your API inputs or outputs without your explicit permission"** (developer security FAQ, fetched 2026-09-24) | **30 days** by default (security auditing); ZDR available, team-wide via the Console, disables Stateful Responses / Files / Collections / Batch | global by default; `https://us.api.x.ai/v1` pins US inference at **+10%** (grok-4.7 / 4.6 only) | yes (team-wide toggle) | **OK on the API key** (30-day, no training, ZDR); Grok Build still off private repos because of the July 2026 repo-upload incident, and the consumer SuperGrok terms are still unfetched (x.ai 403) | [121][44][92] |
| Meta Muse Spark (Model API / OpenRouter) | contributor tier (data used) vs standard no-retention tier on 1.2; 1.3 terms behind dev.meta.ai SSO | tier-dependent | — | standard tier is effectively no-retention | standard tier only | [48][111] |
| Mistral La Plateforme | commercial terms + DPA listed on the legal center; opt-out/ZDR text not fetched; EU regional inference +10% | — | EU option | — | plausible (EU processor terms) but unconfirmed here | [116][109] |
| Kimi API (Moonshot) | "By default, the Kimi Open Platform does not use enterprise customer data to train models"; consumer/individual keys: policy says content helps "optimize our models" | "as long as necessary" | **Singapore** servers | on request, enterprise only | not for theses on an individual key | [83][84] |
| Z.ai GLM API (metered) | Additional Terms for API: **"We will not use End User Content to develop or improve Services, unless you explicitly agree"**; DPA: API inputs "not saved on our servers" | API data deleted after termination of the Terms; consumer accounts retained "as long as you have an account" | **Singapore** ("We generally provide the Services from Singapore") | not offered | **OK on the metered API** (processor-style terms, no training, Singapore) | [122][123] |
| Z.ai GLM Coding Plan (subscription) | the Coding Plan is bought as an individual subscription; the individual-user Terms say Z.ai "reserve[s] the right to process any User Content to improve our existing Services and/or to develop new products", and the usage policy adds "Account sharing or multi-user access is prohibited" and tool-lock — which of the two clauses governs Coding Plan traffic is not stated | as individual accounts | Singapore | no | **not for theses** (individual-terms training reservation); public-input triage only | [123][124][86] |
| MiniMax Token Plan / API | still not found: platform.minimax.io/protocol/privacy-policy, minimax.io/privacy-policy and the docs index all render without clause text on 2026-09-24 (the sibling `minimax.md` cites terms this pass could not reproduce — treat its cell as the only source) | not found | — | — | not for theses until the sibling doc's clause is re-fetched | [93][94] |
| Qwen / Alibaba Model Studio | **"Alibaba Cloud protects data privacy and will never use your data for model training"** (Model Studio overview, fetched 2026-09-24; the dedicated data-security help page still 404s) | not stated on the fetched page | **six regions: China (Beijing), US (Virginia), Singapore, Japan (Tokyo), Germany (Frankfurt), China (Hong Kong)** — separate endpoints, keys, model lists and prices per region | not stated | **conditional OK** on a non-China region key (Singapore/Virginia/Frankfurt) once the retention clause is read; do not use a Beijing-region key for theses | [125] |
| DeepSeek API | privacy policy: data used **"to train and improve our technology, such as our machine learning models"** with an opt-out on request; ToS assigns output rights to the user and permits "training other models" on outputs | "as long as necessary"; no fixed period | **"we directly collect, process and store your Personal Data in People's Republic of China"** | no | **never** for theses (training by default + PRC storage); public-input triage only | [126][127] |
| Perplexity API (Sonar → Agent API) | "we do not use customer data to train our models or for any purpose beyond processing the immediate request" | **"We do not retain data sent through the Chat Completions API"** (billing metadata only: token counts, model, timestamp, key) | not stated | yes, by default | OK for search-grounded research on the API key (consumer Perplexity remains personal/non-commercial) | [128] |
| Local (LM Studio / Ollama) | none leaves the box | local | local | n/a | best; LM Studio licence is personal/internal-business only | [96] |

Router rule that falls out of the table (re-cut 2026-09-24 after the vendor pages were fetched): proprietary theses and any Atlas research artefact route only to lanes marked OK — **Claude Max with Model Improvement off, Claude API, OpenAI API key, Gemini paid key, xAI API key (30-day, no training, ZDR), Z.ai metered API (Singapore, no training), Perplexity API (ZDR), Meta standard tier, Qwen on a non-China region key (conditional), or local** — ten lanes, not the five the previous pass counted. **Never** lanes: DeepSeek (trains by default, PRC storage), Gemini unpaid / Antigravity on a Google account, Z.ai Coding Plan and Kimi individual keys (individual-terms training reservations). Still "not found": MiniMax only.

### Progress-visibility plumbing per lane

| Lane | Remaining-quota introspection | Per-job usage/cost in output | Telemetry export | Src |
|---|---|---|---|---|
| Claude Code / Agent SDK | `/usage` TUI only; no API; `api_retry` events with `error: rate_limit` are the programmatic signal, plus the saveable reset | `result.total_cost_usd`, tokens, `session_id`, `permission_denials` in stream-json; `max_budget_usd` | OpenTelemetry metrics (`session.count`, `cost.usage`, `token.usage`, `active_time.total`, …) and events (`user_prompt`, `assistant_response`, `tool_result`); `CLAUDE_CODE_ENABLE_TELEMETRY=1` + OTLP env | [64][88] |
| Codex CLI | `/status` TUI only | JSON Lines events; final message | **OpenTelemetry**: `[otel]` exporter = `otlp-http` / `otlp-grpc` / `statsig` / `none`, endpoint + headers with `${ENV}` interpolation, `log_user_prompt=false` by default; structured events for conversation start, API requests, stream events, tool decisions and tool results | [35][89][36][120] |
| Gemini CLI | none (AI Studio console only) | stream-json | none documented | [40][41] |
| Antigravity CLI | `/usage` TUI ("Model Quotas", AI Credits) | JSON envelope `usage` {input, output, thinking, cache_read, total tokens}, `num_turns`, `duration_seconds` | none documented | [90][91] |
| Grok Build | none (`grok inspect` = config) | streaming-json | OTEL not in the fetched docs (sibling doc reports a double-opt-in) | [92] |
| MiniMax Token Plan | console usage bar **and** `GET https://www.minimax.io/v1/token_plan/remains` (bearer = Subscription Key; documented in the Token Plan FAQ, which the docs index does not list — the earlier "not in docs index" flag is withdrawn); peak-hour dynamic limiting weekdays 15:00–17:30 | API usage fields | none | [119][93] |
| Kimi API / Kimi Code CLI | `GET /v1/users/me/balance` → `available_balance`, `voucher_balance`, `cash_balance` (USD; metered platform only — "the Kimi Code API is independent from the API service on this platform"); the sibling `kimi.md` documents `kimi web` + `/api/v1/oauth/usage` for the Kimi Code subscription quota — not reproducible from the Kimi Code CLI pages fetched this pass (install/feature pages only), so carried as sibling-sourced rather than "no usage endpoint documented" | API usage fields | none | [85][95][146] |
| Z.ai GLM Coding Plan | subscription page in the console only | API usage fields | none | [86] |
| Alibaba (Qwen) | "Dynamic" quota per sibling doc; not retrieved here | — | — | — |
| Mistral | console only (not verified) | API usage fields | none found | [109] |
| OpenAI API / Anthropic API | admin usage APIs exist but were not fetched this pass — unverified as of 2026-09-24 | usage fields on every response | — | [33][76] |

What this means for "watch their progress": of the subscription lanes only MiniMax (`token_plan/remains`) and, per its sibling doc, Kimi Code (`oauth/usage`) expose remaining budget programmatically; Claude Max, ChatGPT/Codex, Gemini/Antigravity and Copilot do not. The server has to infer it — count jobs and tokens per window from the stream-json/JSON envelopes it already receives, treat `rate_limit` retries as the hard signal, and surface that inferred budget on the dashboard. Claude Code and Codex CLI are the two lanes with a real OTLP exporter (Grok Build's is a sibling-reported double-opt-in); Antigravity is the only other one whose headless envelope reports thinking and cache-read tokens.

### Concurrency per lane on subscription auth (scheduler fan-out)

| Lane | Documented parallel-session cap | What actually limits fan-out | Src |
|---|---|---|---|
| Claude Max (Claude Code / Agent SDK) | **none published** — no concurrency figure on pricing, costs, errors or agent-teams pages; agent teams say "no hard limit on the number of teammates" and the errors page lists only session/weekly/Opus/Sonnet limits and generic 429s | the shared 5-hour + weekly token window (all sessions draw from it), server-side 429 `rate_limit` retries surfaced as `api_retry` events, and the 1h→5m cache-TTL drop for subagents (`subagentPromptCacheTtl`); `-p` sessions cannot spawn teammates, only subagents | [66][151][134] |
| ChatGPT / Codex (plan auth) | **none published** — pricing page gives per-5h message bands and "weekly limits may also apply", nothing on parallel `codex exec` processes | the message band (Astra 5–45 / 25–225 / 100–900 per 5h) is consumed per message across all processes; cloud tasks bill on GPT-5.6 Sol at a higher rate | [35] |
| Gemini / Antigravity (Google login) | **none published** — Antigravity plans page: quota "refreshed every five hours until weekly limit reached" (Pro/Ultra), weekly refresh on Base; Gemini CLI: 1,500 / 2,000 RPD | request-per-day ceilings; "one prompt might result in multiple model requests" | [148][102][41] |
| GitHub Copilot CLI | **none published**; billing is per AI credit / premium request (Pro $10: 1,500 credits/mo; Pro+ $39: 7,000; Max $100: 20,000; overage $0.04 per premium request on legacy plans); each CLI prompt = one premium request at the model's rate | the monthly credit pool; no session cap found on any Copilot CLI page fetched | [149][150] |
| Ollama Cloud | **1 / 3 / 10** concurrent requests (Free / Pro $20 / Max $100 and Team $500); excess "queued and processed as soon as a slot is available" | hard, documented | [145] |
| Kimi | metered API: **concurrency 1 / 15 / 40 / 50 / 60 / 100** at recharge tiers $1 / $10 / $20 / $100 / $1,000 / $3,000 (RPM 3–300, TPM 0.5–5M); Kimi Code subscription: 1–4 parallel tasks per sibling doc (not re-fetched) | hard, documented (metered) | [146] |
| MiniMax Token Plan | **~3–4 / 4–5 / 6–7 agents** (Plus / Max / Ultra), "dynamically adjusted based on cluster load" during weekday 15:00–17:30 peak | soft, documented | [119] |
| Z.ai GLM Coding Plan | Lite "a single project at a time", Pro "1–2 projects simultaneously", Max "2 or more"; concurrency ordering "Max > Pro > Lite", numbers unpublished (rate-limit page requires login) | soft, documented as recommendations | [124] |

Design consequence: only the second-tier lanes give the scheduler a number. For the four primary subscription lanes the fan-out control has to be empirical — start at 2 parallel `-p` / `codex exec` processes per lane, watch `api_retry`/429 rate and the 5-hour bar, and back off; never size fan-out on a documented figure that does not exist.

### Credential lifecycle on a headless box

| Lane | Store on macOS | TTL / renewal | Headless-safe path | What fails first | Src |
|---|---|---|---|---|---|
| Claude Code / Agent SDK (Max OAuth) | **Keychain**; falls back to `~/.claude/.credentials.json` (0600) when the Keychain is locked, e.g. an SSH session | refreshes silently while the login is valid; startup warning "Your login expires in 3 days · run /login to renew" (v2.1.203+); after expiry every request fails `Login expired · Please run /login` / `OAuth session expired and could not be refreshed`; `/status` shows `Login: Expired` | `claude setup-token` → **1-year** `CLAUDE_CODE_OAUTH_TOKEN` (Pro/Max/Team/Enterprise; model requests only, no Remote Control / claude.ai connectors; **not read in `--bare`**) | a launchd job whose Keychain is locked writes plaintext instead; an env `ANTHROPIC_API_KEY` silently outranks the login; a background session "stops making progress once the credential expires and can't recover" | [131] |
| Codex CLI (ChatGPT auth) | `cli_auth_credentials_store = file | keyring | auto | ephemeral`; default file is **plaintext `~/.codex/auth.json`** ("treat like a password") | "refreshes tokens automatically during use before they expire" — refresh is triggered by use, so an idle box can lapse; no expiry alarm documented | `codex login --device-auth` (beta), or copy `auth.json` from an authenticated machine, or SSH-forward the localhost callback; `CODEX_API_KEY` for CI | idle-lapse with no warning; plaintext file on disk unless `keyring` is set | [89][120] |
| Antigravity CLI (Google) | **OS keyring** (Apple Keychain); `/logout` clears keyring + cache | refresh/expiry undocumented | SSH flow prints a paste-in authorization URL; `modelProvider = gemini` + `GEMINI_API_KEY` env for "headless and CI runs" | undocumented expiry; keyring locked under launchd | [147] |
| Gemini CLI | Google OAuth cache (per-vendor doc); `GEMINI_API_KEY` env | OAuth path is now paid-plan only | API key | free login gone (2026-06-18) | [102][40] |
| Grok Build | `~/.grok/` (sandbox `workspace` profile whitelists it for writes); auth page 403 this pass | undocumented | API key | undocumented | [136][92] |
| GitHub Copilot CLI | token from `COPILOT_GITHUB_TOKEN` → `GH_TOKEN` → `GITHUB_TOKEN` (that precedence), or `copilot login` (fine-grained v2 PAT with Copilot Requests permission, or Copilot-CLI / gh OAuth tokens; classic PATs rejected); config dir `~/.copilot` (contents page 404 this pass) | PAT-controlled; no refresh needed for a PAT | fine-grained PAT in env | PAT expiry date set at creation | [150] |
| Hermes agent | **plaintext `~/.hermes/.env`** (0600) for secrets, `config.yaml` for the rest; `~/.ssh`, `~/.aws`, `.env` write-blocked | n/a (static keys) | static keys | key rotation is manual | [139][138] |
| OpenClaw gateway | `~/.openclaw/openclaw.json` (plaintext JSON) | n/a | static keys | same | [140] |
| Kimi Code / MiniMax / Z.ai | API/Subscription keys in env (Anthropic-compatible endpoints) | static | static keys | key leak = full quota drain; MiniMax Subscription Key doubles as the `remains` bearer | [119][87][95] |

Rule for this server: prefer the long-lived token or keyring path on every lane (`setup-token`, Codex `keyring`, Antigravity keyring, PAT for Copilot), add a daily probe that runs `/status`-equivalents (`claude -p` with a 1-token prompt, `codex exec --ephemeral "ok"`) and alerts on `Login expired` / 401 **before** the scheduler's first job of the day, and keep every plaintext auth file (`~/.codex/auth.json`, `~/.hermes/.env`, `~/.openclaw/openclaw.json`, `~/.claude/.credentials.json` fallback) in the sandbox `denyRead` / Codex protected-path list so a prompt-injected job cannot read it [131][135][139].

### Progress-visibility sink (collector side)

Emitters are covered in the table above; this is the collector/dashboard side, sized for the 16 GB M4 that already runs Postgres and Redis.

| Option | Footprint (vendor guidance) | Verdict for this box | Src |
|---|---|---|---|
| Langfuse self-hosted | Postgres + ClickHouse + Redis/Valkey + S3/MinIO + web + worker; docker-compose guidance **"at least 4 cores and 16 GiB of memory"** plus ~100 GB disk | **no** — its recommended machine is the whole box | [142] |
| LiteLLM proxy (as a metering gateway) | **"1 vCPU and 4Gi of memory" per worker**, Prisma engine's RSS is a high-water mark that never shrinks; under 4Gi "a single large write could trigger OOM" | **no as an always-on daemon**; acceptable only as an on-demand process for a metered lane | [141] |
| Prometheus + Grafana | Grafana minimum 512 MB / 1 core (2–4 GB for small production); Prometheus stores 1–2 bytes/sample, memory scales with active series — a few hundred series from this server is trivial | **yes, ~1 GB total**, but it is a second dashboard beside the existing web dashboard | [143][154] |
| OpenTelemetry Collector (OTLP receiver → file/Postgres exporter) | benchmark page renders client-side, no fetchable numbers; the collector's own scaling guide only mandates `memory_limiter`. Practical envelope for tens of events/s is well under 200 MB | **yes** as the single ingress for Claude Code OTEL and Codex `[otel]`, with `memory_limiter` set (e.g. 256 MiB limit) | [88][120] |
| Direct-to-Postgres (no collector) | the server already parses stream-json / JSON Lines envelopes into `volumes/audit_log`; a Postgres table is 0 extra daemons | **preferred**: write one normalised event row per envelope, and point the Claude/Codex OTLP exporters at a tiny OTLP-HTTP receiver only if OTEL-only metrics (active time, tool decisions) are wanted | — |

Common cross-lane event schema (the minimum that both OTLP streams and the JSON envelopes can be mapped onto): `ts, lane, auth_mode (sub|api), model, effort, job_id, session_id, event (start|api_request|tool|retry|result), tokens_in, tokens_out, tokens_thinking, tokens_cache_read, tokens_cache_write, cost_usd_list, rate_limited (bool), reset_at, exit_code`. Inferred remaining budget = for each lane, the window's known ceiling (Codex message band; Gemini RPD; MiniMax `remains`; Ollama slots) or, where no ceiling is published (Claude Max, Copilot credits), an EWMA of tokens-per-window until the first `rate_limit` retry — surfaced on the existing dashboard as "budget used / est. reset". This is the piece no vendor supplies.

### Empirical calibration against this server (recipe, not run here)

Every cost table in this research set uses a synthetic 150K-in / 15K-out job with cache assumptions ranging from 0% to 90%. No doc reads the audit log, and none states the owner's current Max tier or existing paid seats. Because the task scope for this pass excluded reading other repo files, the numbers are left as a recipe:

```bash
# jobs/month, tokens/job, cache share — from the server's own audit log
jq -s '
  map(select(.event=="result")) |
  {jobs: length,
   in_per_job: (map(.usage.input_tokens // 0) | add / length),
   out_per_job: (map(.usage.output_tokens // 0) | add / length),
   cache_share: ((map(.usage.cache_read_input_tokens // 0) | add) /
                 ((map(.usage.input_tokens // 0) | add) + (map(.usage.cache_read_input_tokens // 0) | add)))}
' volumes/audit_log/*.jsonl
```

Fill in: (1) jobs/month and tokens/job from the query above; (2) cache-hit share (Claude Code's `/usage` "Prompt cache (main)" line reports the same ratio per session: e.g. "91% of input tokens from cache" on a warm 1h TTL); (3) the Max tier actually billed (pricing page shows both 5x and 20x as "From $100", so the tier is only visible on claude.ai/settings/usage); (4) any ChatGPT / Copilot / Google seat already paid for. Then re-price §4 with the measured cache share — at 90% cache reads Opus 5.5 input drops from $0.60 to ~$0.10/job and the API break-even against Max 20x moves from ~100 jobs/month to several hundred [66][31].

### Prompt-injection and sandbox posture per lane (untrusted Telegram text, fetched pages, MCP results)

Ranked by what the lane enforces by default in headless mode, best first.

| Rank | Lane | Enforced by default (headless) | Opt-in hardening | Known holes | Src |
|---|---|---|---|---|---|
| 1 | Codex CLI `exec` | Seatbelt on macOS; **"By default, the agent runs with network access turned off"**; `.git` protected read-only; web search defaults to cached results; MCP/app tools that advertise side effects trigger approval (read-only annotations take priority) | domain allow/deny lists with DNS-rebinding and private-network blocking | with `approval_policy = "never"` the auto-review reviewer is not invoked — "the sandbox boundary remains the sole gatekeeper"; `danger-full-access` removes it | [132][133][36] |
| 2 | Claude Code `-p` | isolated context window for WebFetch; `curl`/`wget` not auto-approved; Bash sandbox (Seatbelt / bubblewrap) **pre-allows no domains** and prompts per new host — in auto mode a server-side classifier reviews the command plus the hosts it names; messages from other agents are marked untrusted and approval claims relayed by agents are rejected | `strictAllowlist`, `allowManagedDomainsOnly`, `sandbox.credentials` deny/mask, `denyRead`; `failIfUnavailable` | trust verification is **disabled under `-p`**; sandbox default read scope is "the entire computer" incl. `~/.ssh` and `~/.aws` unless `denyRead`/credentials rules are set; project hooks/MCP in the cwd run without a prompt unless `--bare` | [134][135][64] |
| 3 | Hermes agent | context files scanned for injection patterns before entering the system prompt (flagged project files blocked; `SOUL.md` warns); dangerous-command blocklist always on; Docker backend `cap-drop ALL`, `no-new-privileges`, `pids-limit 256` | `smart` approval uses an auxiliary LLM | scan covers context files, not tool results at runtime (not documented); plaintext `.env` | [138] |
| 4 | Gemini CLI | sandbox is opt-in (`-s`); default Seatbelt profile `permissive-open` = write restrictions, **network allowed** | `restrictive-proxied` / `strict-proxied` profiles, Docker/Podman image | network open in the default profile; no injection-specific controls documented | [137] |
| 5 | Grok Build | **sandbox off by default**; Landlock (Linux) / Seatbelt (macOS); child-process network restriction "no-op on macOS for `read-only` / `strict`" | `strict` profile + restricted permissions "in headless environments" | network isolation does not exist on this Mac; July 2026 repo-upload history | [136][44] |
| 6 | Perplexity MCP / Computer MCP | Computer MCP pauses on `confirm_action` for "sensitive" actions (email, deploy) and `ask_user_question`; the plain search MCP has no side effects to approve — client-side permission mode decides (Antigravity "Ask" by default) | client permission mode | in a `-p` / `exec` client with all tools allowed, `confirm_action` events have nobody to answer them | [129] |
| 7 | opencode / OpenClaw / direct API lanes (GLM, Kimi, MiniMax, DeepSeek, Qwen via Anthropic-compatible endpoints) | none of their own — they inherit whatever harness runs them (Claude Code's when used as a coding-plan backend) | — | OpenClaw's "trusted gateway, untrusted execution" is architecture, not an enforced sandbox; opencode bypasses per sibling docs | [140] |

Server rule: Telegram text and fetched pages enter only lanes ranked 1–2, with the Claude sandbox `denyRead` covering every auth file listed in the credential table and Codex kept at `--sandbox read-only` for review jobs; lanes 4–7 receive only owner-authored prompts and public, pre-fetched inputs.

### Host resource budget (always-on daemons on the 16 GB M4)

| Daemon | RAM (documented or bounded) | Keep always-on? | Src |
|---|---|---|---|
| Postgres + Redis (existing) | already resident | yes | — |
| Claude Code / Agent SDK `-p` job | Node process per job; not documented; budget ~0.4–0.8 GB per concurrent session from the cost page's warning that "running multiple instances" drives cost — treat 2–3 as the ceiling alongside Postgres | per-job, not daemon | [66] |
| Codex CLI `exec` | Rust binary; not documented; small | per-job | [36] |
| Node CLIs (Gemini CLI v0.61, Antigravity `agy`, Copilot CLI, OpenClaw gateway on Node 24/26) | undocumented; each a Node runtime (~0.2–0.5 GB resident when active) | Gemini/Antigravity/Copilot per-job; **OpenClaw gateway is the only one that wants to be a daemon and publishes no RAM figure** | [99][147][140] |
| Hermes gateway | undocumented RAM; Docker backend adds the Docker VM (multi-GB on macOS) | no — run on demand or not at all | [138][139] |
| LiteLLM proxy | **4 GiB per worker** guidance; RSS high-water mark | no | [141] |
| Langfuse | 16 GiB machine guidance | no | [142] |
| OTEL Collector | small; set `memory_limiter` (256 MiB) | optional, one instance | [88] |
| Prometheus + Grafana | ~1 GB combined at this scale | optional | [143][154] |
| Ollama / LM Studio | model-sized (see `local-models.md`); a 7B Q4 model is ~5 GB resident | no — on demand, and never concurrently with Langfuse/LiteLLM | [96] |

Budget: Postgres/Redis + 2–3 Claude/Codex jobs + an OTEL collector + Grafana fits in ~6–8 GB, leaving headroom for one local model or a Node gateway, not both. Anything that recommends a 4 GiB or 16 GiB machine of its own (LiteLLM, Langfuse) is off the always-on list. OpenClaw/Hermes RAM remains explicitly undocumented on their pages.

### Reviewer independence (is the second-opinion lane actually independent?)

The cross-vendor adversarial-review rationale assumes uncorrelated errors from different training lineages. Two facts cut against it for the cheap Chinese lanes: Anthropic's 2026-02-23 disclosure names **DeepSeek (150,000+ exchanges), Moonshot/Kimi (3.4 million+) and MiniMax (13 million+)** as having run distillation operations against Claude — "over 16 million exchanges … through approximately 24,000 fraudulent accounts", with Moonshot targeting "coding and agent development" and MiniMax "agentic coding and tool orchestration" — exactly the review task classes this server would assign them [144]; and the sibling docs record a GPT-5.5 prefill-overlap experiment suggesting output-distribution overlap between Claude and OpenAI models (sibling-sourced, not re-verified here). Qwen and Z.ai are **not** named in the Anthropic disclosure. Consequences for the router: (a) Kimi K3, MiniMax M3 and DeepSeek V4.1 Flash are **not** independent second reviewers for Claude-authored code — their coding/agentic behaviour was shaped on Claude outputs; (b) the independent pairings that survive are Opus 5.5 ↔ GPT-6 Sol/Astra (different lineage, the prefill-overlap caveat noted), Opus 5.5 ↔ Gemini 3.8 Flash, and Opus 5.5 ↔ GLM-5.3 / Qwen3.8 Max / Muse Spark 1.3; (c) CodeRabbit's "switching reviewers changes which bugs slip through" result [57] is the only empirical independence signal in the set and it covered Anthropic models only — an independence eval (same PR set, per-reviewer miss sets, overlap coefficient) belongs in the plan before any lane is trusted as a second opinion.

### Third-party-serving permission per lane

Question: may outputs from this lane be consumed by someone other than the account owner (pickem league dashboard, shared project sites, a Telegram group)?

| Lane | Position | Basis | Src |
|---|---|---|---|
| Claude Max (subscription OAuth) | not explicitly addressed; the agents policy governs *what* the agent does, not *who* consumes the output; the Consumer Terms bar automated access except via API key or "where we otherwise explicitly permit" (Claude Code is the permitted path) | conservative reading: owner-facing automation yes; a page other people hit that calls the subscription live, no — route that through a metered lane | [67][77][68] |
| Claude API | yes (commercial terms) | — | [80] |
| ChatGPT plan / Codex plan auth | **no** — "serves a second person → API key" (`chatgpt-openai.md`); OpenAI steers shared environments to API keys | consumer terms not re-fetched (403) | [89][35] |
| OpenAI API | yes | — | [81] |
| Gemini API paid | yes (processor terms) | — | [82] |
| Gemini API unpaid / Antigravity on a Google account | personal; Google keeps the right to "generate the same or similar content for others"; Code Assist Individual is per-person | no for shared surfaces | [82][102] |
| Grok Build / SuperGrok | not retrievable (x.ai 403); API key = yes | — | [42] |
| Perplexity (consumer) | "personal, non-commercial" per sibling docs; ToS 403 this pass | no for shared surfaces | — |
| LM Studio | "solely for Your personal and / or internal business purposes"; no "service bureau … application service provider, or a software-as-a-service" | no SaaS; internal-only | [96] |
| Mistral La Plateforme | commercial terms ("business customers" per sibling doc); Le Chat consumer plans are personal | API yes, Le Chat no | [116][110] |
| Z.ai GLM Coding Plan | "strictly limited to use within officially supported tools and products"; sibling `crosscut-tos` records an "on behalf of others" bar | no for shared surfaces; metered Z.ai API for those | [86] |
| MiniMax Token Plan / Kimi Code | not stated in the fetched docs | treat as personal | [93][95] |
| OpenRouter / any metered API | yes | pass-through billing | — |

Rule: anything that renders for a non-owner viewer is served from a metered API lane or from cached output produced by an owner-initiated job; no live subscription call sits behind a public page.

### Reconciled fit scorecard (calibrated across providers)

Anchors, so the numbers mean the same thing on every row: **Research** = independent reasoning evals (AA index, Scale HLE, AA GPQA) plus a web/grounding path; **Coding/agentic** = Terminal-Bench 4.0, Arena WebDev, SWE-bench Pro, AA Coding Agent Index; **Cost** = $/job at 150K/15K from §4 and whether a flat plan covers 100 jobs/month; **Automation** = headless JSON mode, resume, budget cap, quota visibility, and clear ToS for unattended use; **Trading research** = Vals finance evals, data connectors, and a data-handling row marked OK above. 10 = best available lane on that axis today.

| Lane | Research | Coding/agentic | Cost | Automation | Trading research | One-line reason |
|---|---|---|---|---|---|---|
| Claude Max (Opus 5.5 / Fable 5.1) | 9 | 10 | 7 | 9 | 7 | AA #1, WebDev #1, Terminal-Bench 66%; flat plan; OTEL; only Excel/Tax finance wins; caps bite at 1,000 jobs |
| OpenAI (Codex plan auth / API) | 10 | 9 | 7 | 8 | 6 | HLE/GPQA/ARC/Vending leader; JSON + schema + resume; no telemetry; Luna fallback surprise |
| Gemini (paid key / Antigravity) | 7 | 6 | 8 | 6 | 7 | 3.8 Flash AA 41 at 292 tok/s, Finance Agent v2 #1; free-login lane gone; no quota API |
| xAI (Grok 4.7 / Build) | 6 | 5 | 8 | 5 | 5 | cheap, slow, verbose, 29% hallucination; X sentiment unique; data terms unfetched; repo-upload history |
| Meta Muse Spark 1.3 | 7 | 7 | 8 | 4 | 6 | AA 48 at $1.25/$4.25, SWE-bench Pro #1, Finance Agent v2 podium; API-only, no CLI, SSO-gated docs |
| Z.ai GLM-5.3 / 5.3-Flash | 6 | 7 | 10 | 6 | 3 | AA 45/42 at the lowest $/point; coding plan; no data terms found; tool-lock clause |
| DeepSeek V4.1 Flash | 5 | 6 | 9 | 5 | 3 | AA 39, 232 tok/s, 0.9 s TTFT, 98% cache discount; Harness in preview; terms not fetched |
| Kimi K3 | 6 | 6 | 4 | 6 | 3 | AA 44 but $3/$15 and 35 tok/s; balance API; Singapore residency; enterprise-only ZDR |
| Qwen3.8 Max | 6 | 6 | 5 | 4 | 3 | AA 45, Arena Vision #2; very verbose ($5.41/index task); no docs reachable |
| MiniMax M3 | 3 | 4 | 9 | 5 | 2 | AA 29; fast; 13 blips in Sep; quota API unverified |
| Mistral (Medium 3.5 / Small 4) | 2 | 3 | 8 | 5 | 3 | AA 14/11; EU residency and processor terms are the only reasons to route here |
| Perplexity | 6 | 1 | 5 | 3 | 4 | search-grounded research only; consumer terms personal/non-commercial |
| Local (LM Studio / Ollama) | 3 | 3 | 9 | 7 | 5 | zero data egress; no SaaS; capability-bound by the box |

**Authority.** This table is the designated final scorecard for the research set; `runtimes.md` §8 and `crosscut-tos.md` §8 each carry a lane table with narrower anchors and different numbers for the same lanes, and neither was previously marked as subordinate. The rule from here on: router design reads only this table; the two sibling tables are inputs (runtimes scores headless mechanics alone, crosscut-tos scores terms clarity alone) and should be reduced to a one-line pointer here rather than maintained as competing totals. The known disagreements and how this table resolves them: **Claude Max automation** 9 here / 9 runtimes / 7 crosscut-tos — the tos score docks the Consumer-Terms automation clause, which this table folds in at 9 because `claude -p` and the Agent SDK on a Pro/Max login are first-party documented and the "Using Agents" policy article governs conduct, not surface (§3) [64][68][77]; **Claude Max cost** 7 here / 9 runtimes / 5 crosscut-tos — runtimes scores flat-plan coverage at ≤100 jobs/month, crosscut-tos scores the API break-even at 1,000 jobs, and 7 is the blend the §4 cost table supports (flat to ~100–200 jobs, usage credits at API rates beyond); **Gemini automation** 6 here / 4 runtimes / 5 crosscut-tos — runtimes penalises the retired free-login lane and the missing quota API, this table credits Antigravity's headless JSON envelope (`usage`, `structured_output`, `num_turns`) and `/usage` quotas, which no other secondary lane matches [91][90]. Where a future edit changes a number in this table, the sibling pointers inherit it; a number changed only in a sibling table is a doc bug.

The per-doc self-scores (Grok automation 7, Claude 8, Perplexity 7/1, local 8, and so on) are likewise superseded by this table; where a sibling doc disagrees, the anchors above are the tie-break.

Task-class fit: research → Astra (HLE/GPQA/Vending) or Opus 5.5 (AA index), with Muse Spark 1.3 (AA 48, $1.25/$4.25) as the cheap third opinion [5][1][111]; coding → Opus 5.5 (Terminal-Bench 4.0 66.4% self, WebDev #1), GLM-5.3 (AA 45, open-weight lineage) as the budget agentic alternate [29][3][104]; code review → Opus 5.5 high with a Sol/Astra second reviewer (different miss sets), GLM-5.3 or Muse Spark when OpenAI is rate-limited [57]; chat/Telegram → Sonnet 5 at low effort (1.80 s TTFT measured) or medium (2.36 s), or DeepSeek V4.1 Flash / MiniMax M3 for sub-1.5 s TTFT — never a high-effort Gemini 3.8 Flash (14.7 s TTFT) or Luna at max (108 s) [107][108][19]; classification/routing → GLM-5.3-Flash ($0.03/job, AA 42) first, GPT-6 Luna low or Gemini 3.8 Flash paid second [105][33][37]; multimodal (audio/video) → Gemini 3.8 Flash; image-heavy review → Qwen3.8 Max (Arena Vision #2) or Fable 5.1 [4]; adversarial review → cross-vendor pair (Astra vs Opus) to avoid correlated blind spots; trading research → Opus 5.5/Fable 5.1 for spreadsheet/Excel-style modelling, Gemini 3.8 Flash (paid key) for finance-agent retrieval, Grok only for X sentiment — and only lanes marked OK in the data-handling matrix carry proprietary theses [10][11]; EU-residency-required jobs → Mistral Medium 3.5 (+10% regional) despite AA 14 [109].

Gotchas: `ANTHROPIC_API_KEY` in env silently switches billing off the subscription [68]; `claude setup-token` is the only Claude credential that survives a year unattended, and `--bare` ignores it [131]; Codex refreshes its token only "during use", so an idle box lapses without warning [89]; Perplexity Sonar Chat Completions dies 2026-09-27 — move to the Agent API [118]; the Claude Max "Model Improvement" toggle turns a 30-day retention into 5 years and covers Claude Code sessions — check it before routing theses [79][80]; Codex on plan auth can silently fall to Luna at the rate-limit prompt unless `--model` is pinned [98]; the Gemini CLI free-Google-login quota (60 RPM / 1,000 RPD) no longer exists — anything sized on it is wrong [102]; `-p` without `--bare` executes any `.mcp.json`/hooks in the working dir with no trust prompt [64]; subscription cache TTL drops from 1h to 5m once usage credits kick in [66]; Codex `exec` refuses to run outside a git repo [36]; Gemini free tier trains on your data [37]; Grok Build's July repo-exfiltration incident argues against pointing it at private repos, whether or not it is free (see §2 reconciliation) [44][43]; pinning US inference (`inference_geo: "us"`) costs 1.1x on Anthropic and OpenAI regional endpoints 10% more — leave global routing unless a policy demands otherwise [76][33].

## 8. Verdict

1. Independent composites (AA, Arena) say Claude Opus 5.5 is the best general agent today; OpenAI's Astra wins the hardest reasoning evals and long-horizon economic sims at the same list price as Fable 5.1 but 60% cheaper per AA task.
2. Coding leaderboards are saturated (SWE-bench Verified, GPQA); rely on Terminal-Bench 4.0, SWE-bench Pro, Arena WebDev and AA-Briefcase — and discount vendor self-reports by roughly one tier.
3. The cheap frontier, tested head-to-head on AA v4.3.2, is GLM-5.3-Flash (AA 42, $0.15/$0.50, $0.03/job, $0.25 to run the index) ahead of Gemini 3.8 Flash (AA 41, $0.75/$3.75, $0.17/job, $1.24), with GPT-6 Luna ($0.02/job at low effort) and DeepSeek V4.1 Flash (AA 39, 0.9 s TTFT) as the effort-limited and latency picks; Gemini 3.8 Flash keeps only throughput and audio/video input. Muse Spark 1.3 at $1.25/$4.25 is the cheapest AA top-20 model. Grok 4.7 is competitively priced but slow and token-hungry; Kimi K3 is over-priced for its score; Mistral is an EU-residency choice, not a capability one.
4. For this server, keep Claude Max as the primary lane with Model Improvement off (30-day retention); add a Codex lane on ChatGPT Pro plan auth with `--model` pinned, switching to `CODEX_API_KEY` for anything that serves a second person; add a GLM-5.3-Flash coding-plan lane for bulk classification and a paid Gemini key for multimodal; the Gemini free-Google-login lane is retired (2026-06-18) and its replacement, Antigravity CLI, sits on unpaid terms — public inputs only. Subscriptions only beat API below ~100 jobs/month on the synthetic 0%-cache job — the real break-even needs the audit-log calibration in §7. Only MiniMax and Kimi Code expose remaining quota programmatically; for Claude Max / Codex / Gemini / Copilot, progress visibility is inferred from the JSON envelopes and the two OTLP streams (Claude Code, Codex) the server can collect (§7). The Telegram lane is Sonnet 5 low/medium (1.8–2.4 s TTFT measured), not Opus 5.5 (5.2 s at low). Second-opinion review must avoid Kimi/MiniMax/DeepSeek (distilled on Claude) and pair Opus with Sol/Astra, Gemini, GLM, Qwen or Muse Spark instead. Sonnet 5's $2/$10 price is now permanent, so the Sonnet chat/Telegram lane in §7 does not face the previously scheduled 50% rise.
5. Finance-specific independent evals are thin: Vals Finance Agent v2 favours Gemini 3.8 Flash and Muse Spark, Excel/Tax favour Claude; nothing public measures live trading — treat all "trading" claims as unverified.

Fit scores (cross-cut, 1–10, same anchors as the §7 scorecard): research 9 (Astra/Opus 5.5 both strong, independent coverage good); coding/agentic 9 (Opus 5.5, with Astra/Sol and now GLM-5.3 as alternates); cost efficiency 8 (price war plus a real sub-$0.10/job tier; reasoning-token overruns and subscription caps still bite); automation friendliness 7 (JSON streams, schemas, resume, budgets and OTLP telemetry exist on the two primary CLIs; only MiniMax and Kimi Code expose remaining quota programmatically, no primary subscription lane publishes a concurrency cap, and MiniMax's data terms are still unpublished); trading research 6 (few independent finance evals, no live-data connectors, no trading benchmark — but ten lanes now clear the data-handling bar for proprietary theses once the xAI, Z.ai-API, Perplexity, Qwen-region and DeepSeek cells were read from vendor pages, up from the five the stale cells implied). The per-lane scorecard in §7 replaces the per-doc self-scores.

## 9. Sources

Accessed 2026-09-24 unless noted.

1. https://artificialanalysis.ai/leaderboards/models — AA Intelligence Index v4.3.2 leaderboard
2. https://arena.ai/leaderboard/text — Arena text leaderboard (updated 2026-09-13)
3. https://arena.ai/leaderboard — Arena overview incl. WebDev top 5
4. https://arena.ai/leaderboard/vision — Arena vision (updated 2026-09-13)
5. https://labs.scale.com/leaderboard/humanitys_last_exam — Scale HLE leaderboard
6. https://labs.scale.com/leaderboard/swe_bench_pro_public — SWE-bench Pro public
7. https://andonlabs.com/evals/vending-bench-2 — Vending-Bench 2
8. https://andonlabs.com/evals/vending-bench — Vending-Bench (deprecated 2025-11-18)
9. http://taubench.com/ — τ²-bench leaderboard
10. https://www.vals.ai/benchmarks — Vals benchmark list with Finance Agent v2 / Excel Modeling / Tax Agent top 3 (updated 2026-09-22/23)
11. https://www.vals.ai/benchmarks/finance_agent — Vals Finance Agent v1.1 (updated 2026-06-04)
12. https://www.vals.ai/benchmarks/swebench — Vals SWE-bench Verified (updated 2026-09-01)
13. https://www.vals.ai/benchmarks/gpqa — Vals GPQA Diamond (updated 2026-09-01)
14. https://artificialanalysis.ai/evaluations/humanitys-last-exam — AA HLE
15. https://artificialanalysis.ai/evaluations/gpqa-diamond — AA GPQA Diamond
16. https://artificialanalysis.ai/models/claude-opus-5-5 — AA model page, Opus 5.5
17. https://artificialanalysis.ai/models/gpt-6-astra — AA model page, GPT-6 Astra
18. https://artificialanalysis.ai/models/grok-4-7 — AA model page, Grok 4.7
19. https://artificialanalysis.ai/models/gemini-3-8-flash — AA model page, Gemini 3.8 Flash
20. https://artificialanalysis.ai/articles/benchmarking-grok-4-7 — AA article (2026-09-21)
21. https://artificialanalysis.ai/methodology/intelligence-benchmarking — AA methodology
22. https://artificialanalysis.ai/leaderboards/models?speed=true — AA speed/price view
23. https://arcprize.org/blog/astra — ARC Prize on GPT-6 Astra (2026-09-03)
24. https://arcprize.org/blog/arc-agi-3-gpt-5-5-opus-4-7-analysis — ARC Prize (2026-05-01)
25. https://arcprize.org/leaderboard — ARC Prize leaderboard (table not rendered)
26. https://metr.org/time-horizons/ — METR time horizons (last updated 2026-05-08)
27. https://metr.org/blog/2026-09-22-claude-opus-5-5/ — METR Opus 5.5 pre-deployment summary
28. https://metr.org/research/ — METR research index
29. https://www.anthropic.com/claude-opus-5-5 — Anthropic Opus 5.5 announcement (2026-09-22)
30. https://platform.claude.com/docs/en/models/overview — Claude models overview
31. https://claude.com/pricing — Claude plans and API pricing
32. https://claude.com/pricing/max — Claude Max plan page
33. https://developers.openai.com/api/docs/pricing — OpenAI API pricing
34. https://developers.openai.com/api/docs/models — OpenAI models; GPT-6 Astra model page https://developers.openai.com/api/docs/models/gpt-6-astra (cache writes $12.50, 272K long-context threshold)
35. https://learn.chatgpt.com/docs/pricing — ChatGPT plans and Codex usage limits
36. https://learn.chatgpt.com/docs/non-interactive-mode — Codex CLI non-interactive mode
37. https://ai.google.dev/gemini-api/docs/pricing — Gemini API pricing
38. https://ai.google.dev/gemini-api/docs/models — Gemini models
39. https://gemini.google/subscriptions/ — Google AI plan prices
40. https://github.com/google-gemini/gemini-cli — Gemini CLI README
41. https://docs.cloud.google.com/gemini/docs/quotas — Gemini Code Assist / CLI quotas
42. https://docs.x.ai/docs/models — xAI models and pricing
43. https://x.ai/news/grok-4-7 — Grok 4.7 announcement (2026-09-21)
44. https://en.wikipedia.org/wiki/Grok_(chatbot) — Grok lineup, SuperGrok, controversies
45. https://en.wikipedia.org/wiki/SpaceXAI — Grok Heavy pricing
46. https://en.wikipedia.org/wiki/GPT-6 — GPT-6 release and safety notes
47. https://en.wikipedia.org/wiki/Claude_(language_model) — Claude lineup and 2026 incidents
48. https://en.wikipedia.org/wiki/Muse_Spark — Meta Muse Spark
49. https://en.wikipedia.org/wiki/Gemini_(language_model) — Gemini lineup and incidents
50. https://deepmind.google/models/gemini/flash/ — Gemini 3.8 Flash page
51. https://openrouter.ai/rankings — OpenRouter weekly usage (through 2026-09-23)
52. https://simonwillison.net/2026/Sep/22/opus-and-sol-and-luna/ — Willison on Opus 5.5 / Sol / Luna
53. https://simonwillison.net/2026/Sep/3/gpt6-astra/ — Willison on GPT-6 Astra
54. https://simonwillison.net/2026/Sep/1/claude-fable-5-1/ — Willison on Fable 5.1
55. https://simonwillison.net/2026/Sep/ — Willison September 2026 archive
56. https://magazine.sebastianraschka.com/p/gpt-6-astra-looped-transformers-and — Raschka on Astra (2026-09-09)
57. https://www.coderabbit.ai/blog/opus-5-5-model-review — CodeRabbit Opus 5.5 code-review eval (2026-09-22)
58. https://news.ycombinator.com/item?id=49554643 — HN: GPT-6 Astra (Sep 3; 2,279 pts, 2,081 comments — counts unverified as of 2026-09-24, algolia item API returns no score; comments via hn.algolia.com API)
59. https://news.ycombinator.com/item?id=49803892 — HN: Claude Opus 5.5 (Sep 22; 1,782 pts, 1,107 comments — counts unverified as of 2026-09-24)
60. https://news.ycombinator.com/item?id=49788838 — HN: Grok 4.7 (Sep 21; 606 pts, 529 comments — counts unverified as of 2026-09-24)
61. https://news.ycombinator.com/item?id=48081266 — Ask HN: Best AI coding plan alternative (2026-05-10)
62. https://hn.algolia.com/api/v1/search?query=Claude%20usage%20limits%20weekly&tags=story — HN stories on Claude usage limits
63. https://arxiv.org/abs/2504.20879 — "The Leaderboard Illusion"
64. https://code.claude.com/docs/en/headless — Claude Code headless / `-p` reference
65. https://code.claude.com/docs/en/agent-sdk/python — Claude Agent SDK Python
66. https://code.claude.com/docs/en/costs — Claude Code cost management, plan limits
67. https://www.anthropic.com/legal/consumer-terms — Anthropic Consumer Terms
68. https://support.claude.com/en/articles/11145838-using-claude-code-with-your-pro-or-max-plan — Claude Code on Pro/Max
69. https://support.claude.com/en/articles/12429409-extra-usage-for-paid-claude-plans — usage credits
70. https://status.claude.com/ — Claude status (September 2026 incidents)
71. https://status.openai.com/history — OpenAI status history (Aug–Sep 2026)
72. https://github.com/patronus-ai/financebench — FinanceBench
73. https://aider.chat/docs/leaderboards/ — Aider polyglot (stale)
74. https://claude.dev/blog/getting-the-most-out-of-opus-5-5/ — Anthropic Opus 5.5 usage guide
75. https://epoch.ai/benchmarks — Epoch Benchmarking Hub (FrontierMath Erdős)
76. https://platform.claude.com/docs/en/about-claude/pricing — Claude API pricing reference (5m/1h cache writes, Sonnet 5 permanent-price footnote, data residency 1.1x, web search $10/1K, web fetch free)
77. https://support.claude.com/en/articles/12005017-using-agents-according-to-our-usage-policy — "Using Agents According to Our Usage Policy"
78. https://status.cloud.google.com/summary — Google Cloud status summary (no Vertex AI / Gemini API incidents Aug–Sep 2026)
79. https://privacy.claude.com/en/articles/10023580-is-my-data-used-for-model-training — consumer Model Improvement toggle (opt-in), covers Claude Code on Pro/Max
80. https://code.claude.com/docs/en/data-usage — Claude Code data usage: consumer 30-day / 5-year retention, commercial 30-day, ZDR Enterprise-only, local plaintext transcripts, telemetry defaults
81. https://developers.openai.com/api/docs/guides/your-data — OpenAI API data controls: no training by default, 30-day abuse logs, ZDR-eligible endpoints, regional processing +10%
82. https://ai.google.dev/gemini-api/terms — Gemini API terms: unpaid services used to improve products, paid services under processor DPA, grounding 30-day
83. https://platform.kimi.ai/docs/guide/zero-data-retention.md — Kimi ZDR (enterprise, on request); enterprise data not used for training by default
84. https://platform.kimi.ai/docs/agreement/userprivacy.md — Kimi Open Platform privacy policy (Singapore servers; content used to "optimize our models")
85. https://platform.kimi.ai/docs/api/balance.md — Kimi `GET /v1/users/me/balance`
86. https://docs.z.ai/devpack/faq — GLM Coding Plan FAQ ("strictly limited to use within officially supported tools"; quota visible in subscription page; retention/training absent)
87. https://docs.z.ai/devpack/overview — GLM Coding Plan tiers, 5-hour/weekly credits, credit multipliers, off-peak discount
88. https://code.claude.com/docs/en/monitoring-usage — Claude Code OpenTelemetry metrics/events; no quota API
89. https://learn.chatgpt.com/docs/auth — Codex auth: ChatGPT sign-in vs API key; "Use API key authentication for programmatic Codex CLI workflows, such as CI/CD jobs"; device-code beta and cached-credential fallbacks
90. https://antigravity.google/docs/getting-started?tab=cli — Antigravity CLI 2.5.0, `/usage` Model Quotas, AI Credits
91. https://antigravity.google/docs/cli/headless/ — Antigravity CLI headless flags and JSON envelope (`usage`, `structured_output`, `num_turns`)
92. https://docs.x.ai/build/overview — Grok Build overview: browser or API-key sign-in, `-p` / `--output-format streaming-json`, `grok inspect`
93. https://platform.minimax.io/docs/token-plan/intro.md — MiniMax Token Plan Plus/Max/Ultra $22/$55/$132, 5-hour + weekly windows, console usage bar
94. https://platform.minimax.io/docs/llms.txt — MiniMax docs index (no `token_plan/remains`, priority tier, or status page listed)
95. https://platform.kimi.ai/docs/guide/kimi-code-cli.md — Kimi Code CLI (`/login`, `/status`; no usage endpoint documented)
96. https://lmstudio.ai/terms — LM Studio terms: personal / internal business use; no service-bureau, ASP or SaaS use
97. https://github.com/anthropics/claude-code/releases — Claude Code releases v2.1.271–2.1.281 (Sep 14–23, 2026)
98. https://github.com/openai/codex/releases — Codex CLI 0.156.1 (Sep 23, 2026) and alphas; rate-limit prompt recommends GPT-6 Luna
99. https://github.com/google-gemini/gemini-cli/releases — Gemini CLI v0.61.0 (Sep 23, 2026), previews/nightlies
100. https://api-docs.deepseek.com/guides/deepseek_harness — DeepSeek Harness "developer preview"
101. https://docs.perplexity.ai/changelog/changelog — Perplexity changelog (September 2026: Agent API model additions, no Sonar deprecation listed)
102. https://geminicli.com/docs/resources/quota-and-pricing/ — Gemini CLI quotas by auth mode; "As of June 18, 2026, Gemini CLI was replaced by Antigravity CLI" for unpaid-tier and Google One users; API-key free tier 250 RPD Flash only
103. https://artificialanalysis.ai/models/kimi-k3 — AA model page, Kimi K3 (index 44, $3/$15, 35 tok/s, 3.79 s TTFT, $2.00/task)
104. https://artificialanalysis.ai/models/glm-5-3 — AA model page, GLM-5.3 (45, $1.40/$4.40, 60 tok/s, 3.45 s, $2.01/task)
105. https://artificialanalysis.ai/models/glm-5-3-flash — AA model page, GLM-5.3-Flash (42, $0.15/$0.50, 43 tok/s, 3.67 s, $0.25/task, 83% cache discount)
106. https://artificialanalysis.ai/models/qwen3-8-max — AA model page, Qwen3.8 Max 0902 (45, #24/210, $2/$6, 39 tok/s, 3.03 s, $5.41/task)
107. https://artificialanalysis.ai/models/deepseek-v4-1-flash — AA model page, DeepSeek V4.1 Flash (39, $0.30/$1.20, 232 tok/s, 0.92 s, $0.27/task, 98% cache discount)
108. https://artificialanalysis.ai/models/minimax-m3 — AA model page, MiniMax M3 (29, $0.30/$1.20, 145 tok/s, 1.28 s, $0.51/task)
109. https://mistral.ai/pricing/api — Mistral API pricing (Large 3 $0.5/$1.5, Medium 3.5 $1.5/$7.5, Small 4 $0.15/$0.6, Codestral $0.3/$0.9, Ministral 3, −90% cache, +10% regional, "Priority inference" tier); Mistral AA scores (Large 3 9, Medium 3.5 14, Small 4 11) from source 1
110. https://mistral.ai/pricing — Le Chat plans (Free $0 + $10/mo API credits, Pro $14.99 + $15/mo credits, Student $5.99, Team $24.99/user)
111. https://openrouter.ai/api/v1/models/meta/muse-spark-1.3/endpoints — Muse Spark 1.3 $1.25/$4.25 per 1M, 1,048,576 ctx, provider Meta
112. https://status.deepseek.com/ — DeepSeek status (no incidents listed; Jun–Sep uptime V4 Pro API 99.89%, V4.1 Flash API 99.66%)
113. https://status.minimax.io/ — MiniMax status (13 LLM incidents in Sep 2026, 1–9 min each)
114. https://statusgator.com/services/mistral-ai — StatusGator Mistral (26 incidents Aug–Sep 2026, ~178 h counted)
115. https://statusgator.com/services/grok — StatusGator Grok/xAI (10 incidents Aug–Sep 2026; 3 h 27 m on Sep 3)
116. https://legal.mistral.ai/terms — Mistral legal center (Commercial Terms, Additional Product Terms, DPA listed; clause text not fetched)
117. https://platform.kimi.ai/docs/llms.txt — Kimi docs index (balance, limits, ZDR, privacy pages; no status page)
118. https://docs.perplexity.ai/docs/agent-api/migrate-from-sonar/overview.md — "Sonar will be supported until September 27, 2026"; Agent API is the successor (all Sonar variants)
119. https://platform.minimax.io/docs/token-plan/faq.md — MiniMax Token Plan FAQ: `GET https://www.minimax.io/v1/token_plan/remains`; ~3–4 / 4–5 / 6–7 agents; weekday 15:00–17:30 dynamic limiting
120. https://learn.chatgpt.com/docs/config-file/config-advanced — Codex `[otel]`: exporters otlp-http / otlp-grpc / statsig / none, `log_user_prompt=false`, event types; credential store options
121. https://docs.x.ai/developers/faq/security — xAI: no training on API data without permission; 30-day retention; team-wide ZDR; `us.api.x.ai` +10% (grok-4.7/4.6)
122. https://docs.z.ai/legal-agreement/privacy-policy.md — Z.ai privacy: Singapore; API inputs "not saved on our servers"; API data deleted after termination
123. https://docs.z.ai/legal-agreement/terms-of-use.md — Z.ai terms: API "will not use End User Content to develop or improve Services, unless you explicitly agree"; individual users "reserve the right to process any User Content to improve"
124. https://docs.z.ai/devpack/usage-policy.md — GLM Coding Plan: Lite single project / Pro 1–2 / Max 2+; account sharing prohibited; tool lock
125. https://www.alibabacloud.com/help/en/model-studio/what-is-model-studio — Model Studio: six regions; "will never use your data for model training"
126. https://cdn.deepseek.com/policies/en-US/deepseek-privacy-policy.html — DeepSeek: trains on data (opt-out on request); stored in the PRC; retention "as long as necessary"
127. https://cdn.deepseek.com/policies/en-US/deepseek-open-platform-terms-of-service.html — DeepSeek ToS: output rights assigned to user; training other models on outputs permitted
128. https://docs.perplexity.ai/docs/resources/privacy-security.md — Perplexity API: no retention of Chat Completions data; no training on customer data
129. https://docs.perplexity.ai/docs/getting-started/integrations/computer-mcp-server.md — Perplexity Computer MCP: `confirm_action` / `ask_user_question` / `auth_required` events
131. https://code.claude.com/docs/en/authentication — Claude Code credentials: Keychain / `~/.claude/.credentials.json` 0600 fallback; 3-day expiry warning; `claude setup-token` one-year `CLAUDE_CODE_OAUTH_TOKEN` (not read in `--bare`); precedence list
132. https://learn.chatgpt.com/docs/agent-approvals-security.md — Codex: network off by default; domain allow/deny; MCP side-effect approvals; `.git` protected
133. https://learn.chatgpt.com/docs/sandboxing/auto-review.md — Codex auto-review applies only with interactive approvals; with `approval_policy = "never"` the sandbox is the sole gatekeeper
134. https://code.claude.com/docs/en/security — Claude Code prompt-injection protections; trust verification disabled under `-p`; isolated WebFetch context
135. https://code.claude.com/docs/en/sandboxing — Claude Code sandbox: Seatbelt/bubblewrap; no domains pre-allowed; `strictAllowlist`; default read scope is the whole machine; credential deny/mask
136. https://docs.x.ai/build/features/sandbox — Grok Build sandbox: off by default; Landlock/Seatbelt; child network enforcement "no-op on macOS"; `~/.grok/` writable in `workspace` profile
137. https://geminicli.com/docs/cli/sandbox/ — Gemini CLI sandbox: opt-in; default Seatbelt profile `permissive-open` (network allowed)
138. https://hermes-agent.nousresearch.com/docs/user-guide/security — Hermes: injection scan of context files; approval modes; Docker hardening
139. https://hermes-agent.nousresearch.com/docs/user-guide/configuration — Hermes: secrets in plaintext `~/.hermes/.env` (0600)
140. https://docs.openclaw.ai/ — OpenClaw: Node 24.16+/26; `~/.openclaw/openclaw.json`; gateway model; no RAM figure
141. https://docs.litellm.ai/docs/proxy/prod — LiteLLM: 1 vCPU + 4Gi per worker; Prisma RSS high-water mark
142. https://langfuse.com/self-hosting/deployment/docker-compose — Langfuse: "at least 4 cores and 16 GiB of memory", ~100 GB disk
143. https://grafana.com/docs/grafana/latest/setup-grafana/installation/ — Grafana minimum 512 MB / 1 core
144. https://www.anthropic.com/news/detecting-and-preventing-distillation-attacks — Anthropic (2026-02-23): DeepSeek 150K+, Moonshot 3.4M+, MiniMax 13M+ exchanges; ~24,000 fraudulent accounts
145. https://ollama.com/cloud — Ollama plans: 1 / 3 / 10 concurrent requests; $20 / $100 / $500
146. https://platform.kimi.ai/docs/pricing/limits.md — Kimi metered tiers: concurrency 1–100, RPM 3–300, TPM 0.5–5M by cumulative recharge; product-plans page: Kimi Code API independent of the platform
147. https://antigravity.google/docs/cli/install/ — Antigravity CLI auth: OS keyring (Apple Keychain); SSH paste-URL flow; `GEMINI_API_KEY` for headless/CI
148. https://antigravity.google/docs/plans/ — Antigravity plans: 5-hour refresh until weekly limit (Pro/Ultra); AI-credit overage modes; no BYOK
149. https://docs.github.com/en/copilot/concepts/billing/individual-plans — Copilot Pro $10 (1,500 credits) / Pro+ $39 (7,000) / Max $100 (20,000); legacy premium-request overage $0.04
150. https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference — Copilot CLI: `COPILOT_GITHUB_TOKEN` → `GH_TOKEN` → `GITHUB_TOKEN`; `copilot login`; fine-grained PATs only; `-p`, `--allow-all-tools`, `--yolo`
151. https://code.claude.com/docs/en/agent-teams — "no hard limit on the number of teammates"; teammates not spawned under `-p`; 5-minute subagent cache TTL
153. https://artificialanalysis.ai/models/claude-sonnet-5 — AA Sonnet 5 model page (max effort 150 s TTFT, 79 tok/s, index 38); per-effort TTFT from source 22
154. https://prometheus.io/docs/prometheus/latest/storage/ — Prometheus 1–2 bytes/sample
155. https://opentelemetry.io/docs/collector/configuration/ — OTEL Collector `memory_limiter` processor (example `limit_mib: 4000`, `spike_limit_mib: 500`; no footprint figures published)
156. https://geminicli.com/docs/get-started/authentication/ — Gemini CLI auth: "Your credentials will be cached locally"; headless uses the cached credential or `GEMINI_API_KEY` / Vertex env; no TTL, path or concurrency stated

Not retrievable on 2026-09-24 second pass (403/404/empty render): platform.minimax.io privacy/ToS pages (render without clause text), alibabacloud.com Model Studio data-security page, z.ai rate-limits page (login), docs.x.ai grok-bot approvals page (Cursor content served), Kimi Code CLI usage/OAuth reference pages, Copilot CLI configuration-directory page, support.claude.com Max-usage article, OTEL Collector benchmark data (client-rendered). Earlier pass, left as flagged: dev.meta.ai/pricing (SSO wall), x.ai/grok, x.ai/news, docs.x.ai/build/authentication and /pricing, x.ai privacy and enterprise terms, docs.mistral.ai priority-tier pages, openai.com terms-of-use and usage-policies, perplexity.ai terms, alibabacloud.com Model Studio data-security pages, docs.z.ai terms-of-service, platform.minimax.io terms clause text, status.kimi.ai and status.z.ai (no DNS), antigravity.google CLI changelog.

## Verification log (2026-09-24)

**Corrections applied from the fact-check**: 10 total — 2 major (GPT-6 Astra API price row: cache writes $12.50, 50% batch/flex, fast mode 2x, 272K long-context threshold with 2x/1.5x multipliers; Grok Build access conflict flagged in §2), 8 minor (SuperGrok/Grok Build note, AA top-15 count 8→9, Team seat pricing annual vs monthly, X Premium+ $40, Claude status longest incident 1h41m Sep 10, Cowork-on-Windows ~6 days, Gemini free tier "$0 per token" not "unlimited tokens", AA Grok 4.7 article date 2026-09-21).

**Claims re-verified this pass, with sources**: Astra cache-write $12.50 / 1.25x input, 272K threshold, batch/flex 50%, fast mode 2x (developers.openai.com/api/docs/models/gpt-6-astra); OpenAI regional-processing 10% uplift for models released on/after 2026-03-05 and web search $10/1K (developers.openai.com/api/docs/pricing); Claude 1h cache writes $20/$8/$4/$2, Sonnet 5 $2/$10 made permanent with the 2026-09-01 rise cancelled, `inference_geo: "us"` 1.1x, web search $10/1K, web fetch free (platform.claude.com/docs/en/about-claude/pricing); Team Standard $20 annual/$25 monthly and Premium $100/$125, Max "From $100" (claude.com/pricing); saveable rate-limit reset for Pro/Max/Team/seat-based Enterprise (anthropic.com/claude-opus-5-5); "Using Agents According to Our Usage Policy" article exists and is linked from the Pro/Max Claude Code article (support.claude.com 12005017); Grok Build "Get started today at x.ai/build", announcement 2026-09-21 (x.ai/news/grok-4-7); AA article date 2026-09-21 and "approximately 188 tokens/second for long prompts" (artificialanalysis.ai/articles/benchmarking-grok-4-7); Gemini 3.8 Flash cache read $0.075→$0.15 and storage $0.50→$1.00/1M/h, 3.1 Pro storage $4.50/1M/h, free tier "Free of charge", grounding 5,000 free then $14/1K (ai.google.dev/gemini-api/docs/pricing); Gemini rate-limits page publishes no per-model free-tier numbers ("can be viewed in Google AI Studio"); Codex Astra 5–45 / Sol 15–150 / Luna 350–3,000 on Plus and the "Cloud chats … use GPT-5.6 Sol" note, ChatGPT Pro from $100 (learn.chatgpt.com/docs/pricing); Google Cloud status lists no Vertex AI / Gemini API incidents in Aug–Sep 2026 (status.cloud.google.com/summary).

**Stale or unverifiable flags left in place** (each marked "unverified as of 2026-09-24" in the text): Claude Max 20x = $200; Gemini 3.8 Flash AA rank #40 (fetch suggested ~#33); which Grok 4.7 speed figure (40 vs 188 tok/s) is current; OpenAI Aug/Sep incident totals and durations; HN point/comment counts for threads 58–60; Mythos 5.1 "~150 orgs"; Google AI Ultra $40/mo Cloud credits; Agent SDK ResultMessage fields; GPT-5.5/5.6 release dates; Muse Spark 1.3 API pricing; ChatGPT Pro 20x tier price. Not re-fetchable this pass: status.claude.com/history (rendered no incident data — Sep 10/15/22 durations taken from the fact-checker's source), status.x.ai (403), aistudio.google.com/status (empty). Newer-model scan: no model newer than Opus 5.5 / GPT-6 Astra-Sol-Luna / Gemini 3.8 Flash / Grok 4.7 / Muse Spark 1.3 was seen on vendor pages, but this is unconfirmed rather than confirmed-absent.

**Fact-checker's overall quality rating**: good.

**Gap-fix pass (2026-09-24, web-search budget exhausted; direct fetches only)**: (1) added the second tier — Kimi K3, GLM-5.3, GLM-5.3-Flash, Qwen3.8 Max, DeepSeek V4.1 Flash, MiniMax M3, Mistral Large 3 / Medium 3.5 / Small 4 — to §1, the §4 price and cost tables, the §5 composite row and speed note, and §7 task-class fit, all on AA v4.3.2 from the AA model pages; (2) replaced verdict 3 with a GLM-5.3-Flash vs Gemini 3.8 Flash head-to-head (42 vs 41; $0.25 vs $1.24 per index task); (3) retired the Gemini CLI free-Google-login lane everywhere (replaced by Antigravity CLI on 2026-06-18 per geminicli.com; API-key free tier 250 RPD Flash-only); (4) filled Muse Spark 1.3 at $1.25/$4.25 from OpenRouter's endpoints API, matching `llama-meta.md`; (5) resolved Grok Build access to every-plan-since-2026-08-19 (sibling docs; consistent with x.ai/news/grok-4-7 and docs.x.ai/build/overview; Wikipedia stale); (6) reconciled the Codex lane to plan auth by default with `CODEX_API_KEY` on the serves-others path, per learn.chatgpt.com/docs/auth; (7) added five cross-doc tables — data-handling matrix per lane and auth mode (Claude Max lane now stated: opt-in Model Improvement, 30-day vs 5-year retention, no ZDR), progress-visibility plumbing, third-party-serving permission, normalized reliability (one source per vendor, Aug 1–Sep 24), tool churn — plus a Telegram latency rating and a calibrated fit scorecard. New unverified flags: the 2026-08-19 Grok Build date (x.ai 403), MiniMax `/v1/token_plan/remains` (absent from the docs index), Perplexity Sonar sunset (September changelog lists none), Mistral Priority Tier SLA number, and every "not found" cell in the data-handling matrix.

**Gap-fix pass 3 (2026-09-24, web-search budget exhausted; direct fetches only)**: (1) §4 subscription row corrected — Google AI Pro + Gemini CLI is 1,500 RPD (AI Ultra 2,000), not "1,000 req/day free"; the 1,000 figure is the retired Code Assist Individual login tier, now consistent with §3 and `gemini-google.md` [102][41][148]; (2) Antigravity binary normalised to `agy` in §3, §7 item 3 and the cheap-lane one-liner — the headless page's examples all use `agy -p`, matching `gemini-google.md` and `runtimes.md` [91]; (3) the §7 scorecard is now designated the single authoritative lane table, with the three known divergences against `runtimes.md` §8 and `crosscut-tos.md` §8 (Claude Max automation 9/9/7, Claude Max cost 7/9/5, Gemini automation 6/4/5) explained and resolved in place; sibling tables are to be reduced to pointers. Re-verified this pass from primary pages: Claude Code credential storage (Keychain, `.credentials.json` 0600 fallback, 3-day expiry warning, `setup-token` one-year token, precedence list) [131]; Claude Code OTEL metric/event/span names and the `prometheus` exporter on :9464 [88]; Claude sandbox Seatbelt/bubblewrap and proxy allowlist [135]; Codex `auth.json` and use-triggered refresh [89]; Codex plan allowance shared between local and cloud [35]; AA speed view per-effort TTFT for Sonnet 5 (low 1.80 s, medium 2.36 s, high 8.49 s, xhigh 17.4 s, max 150 s), Opus 5.5 (low 5.18 s, medium 21.4 s, high 34.9 s, xhigh 142 s) and Fable 5.1 (low 6.29 s, medium 11.9 s, high 20.9 s, xhigh 110 s, max 265 s) [22]; Anthropic distillation disclosure figures [144]; LiteLLM 4Gi/worker and Langfuse 16 GiB guidance [141][142]; OTEL collector `memory_limiter` example [155]. Not retrievable this pass: learn.chatgpt.com/docs/sandbox (404), docs.x.ai/build/sandbox (404; the features/sandbox page cited as [136] stands), docs.github.com Copilot CLI how-to (auth storage not on page), geminicli.com authentication page (no credential path or TTL stated — "Your credentials will be cached locally for future sessions" only) [156].

**Gap-fix pass 2 (2026-09-24, web-search budget exhausted; direct fetches only)**: (1) corrected four sibling conflicts from vendor pages — Perplexity Sonar sunset 2026-09-27 confirmed on the migration page [118]; MiniMax `token_plan/remains` confirmed in the Token Plan FAQ [119]; Codex OTEL export confirmed in config-advanced [120]; Kimi Code `oauth/usage` left as sibling-sourced (pages not reachable) with the metered balance endpoint kept; (2) re-filled the data-handling matrix for xAI (30-day, no training, ZDR, US +10%), Z.ai API vs Coding Plan (Singapore; API no-training; individual-terms reservation), Qwen (six regions; never trains), DeepSeek (trains by default; PRC storage), Perplexity API (ZDR) — MiniMax remains the only "not found"; router rule and §8 re-cut from five OK lanes to ten; (3) added seven cross-cut subsections in §7: concurrency per lane (primary subscription lanes publish none; Ollama 1/3/10, Kimi 1–100 by tier, MiniMax 3–7 agents, Z.ai 1/1–2/2+), credential lifecycle matrix (Keychain vs plaintext files, 1-year `setup-token`, Codex use-triggered refresh, Copilot PAT precedence), collector-side visibility sink (Langfuse 16 GiB and LiteLLM 4 GiB ruled out; direct-to-Postgres + optional OTEL collector; common event schema), empirical-calibration recipe (audit-log `jq`; Max tier and seats to be supplied by the owner — no repo files read this pass), prompt-injection/sandbox ranking (Codex > Claude Code > Hermes > Gemini CLI > Grok Build > Perplexity MCP > pass-through lanes), host RAM budget, reviewer independence (Anthropic 2026-02-23 distillation disclosure names DeepSeek/Moonshot/MiniMax; Qwen and Z.ai not named); (4) measured Claude chat latency from AA's speed view — Sonnet 5 low 1.80 s / medium 2.36 s, Opus 5.5 low 5.18 s / medium 21.4 s, Haiku 4.5 0.63 s — replacing the "not captured" cell and the sibling docs' unsourced "sub-2 s"; (5) sources 118–154 added.
