# Alibaba Qwen — research (as of 2026-09-24)

Scope note: the brief's focus list (Qwen3 / Qwen3.5 / Qwen3-Max / Qwen3-Coder / Qwen3-Next) is two generations stale. The
current family is **Qwen3.8** (Aug–Sep 2026), with Qwen3.7 / 3.6 / 3.5 still served. The **Qwen OAuth free tier of Qwen
Code was discontinued on 2026-04-15** [2], which changes the "free CLI" thesis. Everything below is from primary sources
fetched 2026-09-24 unless marked (unverified). Web search quota was exhausted in this session, so all facts come from
direct fetches of vendor docs, model cards, OpenRouter/Ollama/HF APIs, Artificial Analysis, arena.ai, and HN's Algolia API;
Reddit and X could not be fetched.

## 1. Snapshot

**Company.** Qwen is the model lab of Alibaba Cloud (Tongyi). Two commercial front doors: **Alibaba Cloud Model Studio**
(a.k.a. Bailian / DashScope; regions Singapore-international and Beijing, plus limited US-Virginia/Frankfurt/Tokyo/HK
availability for some models) [11][16], and the newer **QwenCloud** brand (qwencloud.com, `maas.qwencloudapi.com`)
which fronts the same catalogue [21]. Consumer product is **Qwen Studio** (chat.qwen.ai, formerly "Qwen Chat"), stated
as "free to use, open to all" [34]. Open weights are published on Hugging Face/ModelScope under `Qwen/*` [24][30].

**Current lineup (API IDs, exact where verified).**

| Model | Type / params | Context | Modalities | Released | Weights / license |
|---|---|---|---|---|---|
| `qwen3.8-max` (= `qwen3.8-max-0902`, alias `qwen3.8-max-2026-09-02`) | MoE 2.4T total / 95B active, thinking-only | 1M (API) [21]; 262K native, ext. 1.01M (weights) [26] | text (+image/video on API per QwenCloud [21]; weights are text-only [26]) | announced 2026-08-03 [32], weights 2026-08-12 [31] | `Qwen/Qwen3.8-2.4T-A95B` under the "Qwen3.8-Max License" (custom, not Apache) [26][27] |
| `qwen3.8-27b` | dense 27B, hybrid Gated-DeltaNet attention, thinking w/ effort levels | 262K native, ext. 1M [24]; 1M on API [22] | text+image+video in, text out | 2026-08-14 [31] | `Qwen/Qwen3.8-27B`, **Apache-2.0** [24] |
| `Qwen3.8-Flash-Next` | MoE 125B / 6B active (+51B n-gram embedding +4B MTP; ~180B on disk) — "experimental preview architecture intended for Qwen4" | 262K native, ext. 1M | text+image+video | 2026-08-26 (HN) [64] | `qwen-community-1.0` license [25] |
| `qwen3.8-flash` | proprietary API model | 1M [42] | multimodal reasoning | 2026 | API only |
| `qwen3.8-omni-flash`, `qwen3.8-omni-flash-realtime` | omnimodal, audio in/out, WebSocket/WebRTC realtime | up to 1 h audio-visual input | audio/video/text | 2026-09-14 per blog post [33]; qwen.ai homepage lists it under 2026/09/18 (same day as LiveTranslate) [34] — exact date unverified as of 2026-09-24 | proprietary |
| `qwen3.7-plus` (snapshot `qwen3.7-plus-20260602`), `qwen3.7-max` | proprietary | 1M [43] | text/vision | mid-2026 | API only |
| `Qwen3.6-27B`, `Qwen3.6-35B-A3B` | dense 27B; MoE 35B/3B active | 262K native | text+image+video | 2026-04-22 / 2026-04-16 [31] | Apache-2.0 [28] |
| Qwen3.5 series: 397B-A17B, 122B-A10B, 35B-A3B, 27B, 9B, 4B, 2B, 0.8B | mixed | 262K native | text+image+video | from 2026-02-24 [31] | Apache-2.0 (9B verified) [29] |
| Qwen3-Coder-480B-A35B (`qwen/qwen3-coder`) | older coder MoE | 262K | text | 2025 | open; still served [45] |
| Embedding/rerank: `text-embedding-v4`, `qwen3.7-text-embedding`, `qwen3-rerank`; `Qwen3-Embedding-0.6B/4B/8B` open | | | | | [11][30] |

Also in the catalogue: `decision-model-preview`, image/video/TTS/ASR models [11] — out of scope. NEW (2026-09-23):
`qwen3.8-max-prime`, a higher-throughput SKU of Qwen3.8-Max served by Alibaba at $4.00 / $12.00 per 1M (cache read $0.50),
1M context, text+image+video in — listed on OpenRouter [75]; the qwencloud.com model page for it 404s as of 2026-09-24 and
the Model Studio pricing/models pages [10][11] do not list it — attested only by OpenRouter, treat the $4/$12 price as
provisional (unverified as of 2026-09-24).

Newer open release, out of scope but confirming cadence: `Qwen/Qwen-Drive-1.0-4B` (2026-09-02, arXiv 2609.00111) — an
Apache-2.0 autonomous-driving VLM built on Qwen3.5-4B (~5B params with BEV perception head and planning expert) [76].

**Knowledge cutoff:** Not found — searched: HF model cards for Qwen3.8-27B / 2.4T / Flash-Next, qwencloud.com model
pages for qwen3.8-max-0902 and qwen3.8-27b, Model Studio model list, launch blog. None state a cutoff [21][22][24][26][32].

**Release cadence.** Roughly one point release every 6–8 weeks in 2026: Qwen3.5 (Feb 24), 3.6 (Apr 16/22), 3.7 (~Jun 2
snapshot), 3.8-Max (Aug 3 API / Aug 12 weights), 3.8-27B (Aug 14), Flash-Next (Aug 26), Omni-Flash + LiveTranslate
(Sep 14–18), Qwen-Image-2.1 (Sep 20) [31][32][33][34][43]. Older generations are deprecated quickly (Anthropic-compat
endpoint returns HTTP 403 for models "marked for upcoming deprecation") [17].

**Positioning (one paragraph).** Qwen is the leading open-weight family by download volume and community mindshare
(Qwen3.8-27B: 6.8M HF downloads / 16K likes within six weeks [30]; four of the top-10 HN Qwen stories of 2026 are 27B
local-run reports [66]). Alibaba positions Qwen3.8-Max as a frontier "coding and cowork" model that can take "a real,
multi-day project from an empty folder all the way to a finished result" [32], while the 27B dense model is the
family's "runs on a laptop, competes with mid-2025 frontier" workhorse. Independent scoring puts 3.8-Max at #22 on
arena.ai text (1481) [53] and #24/210 on the Artificial Analysis Intelligence Index (45) [49] — top-tier open, a step
below Anthropic/OpenAI/Google/Meta flagships — and 3.8-27B at #1 of 142 open-weight models in its class (AA index 34)
[50]. Pricing is the strategic weapon: `qwen3.8-max` is $2/$6 per 1M [10], `qwen3.8-flash` $0.15/$0.47 [10], the 27B is
free to self-host.

## 2. Interfaces & surfaces

- **Consumer app.** Qwen Studio at chat.qwen.ai plus iOS/Android/desktop apps ("on your phone or desktop") [34]. Features
  advertised: Deep Research agent, Web Dev (site generation), Thinking, Search, image generation/editing (Qwen-Image),
  multimodal understanding, voice + video chat (since 2025) [34][74]. No paid consumer tier found — the site says
  "free to use, open to all" [34]; HN Algolia search for Qwen Chat subscription/pricing returned 0 hits [74].
- **Browser / OS.** Qwen Code v0.24.4 ships a Chrome extension packaging workflow and a macOS desktop app with native
  title bar [9]; a Web Shell UI is built into `qwen serve` [4]. Not verified beyond release notes.
- **Voice.** `qwen3.8-omni-flash-realtime` — WebSocket/WebRTC, TTFT 591–981 ms, 74 ASR languages, 29 TTS languages [33];
  `Qwen3.8-LiveTranslate` (2026-09-18) [34]; open `Qwen3-TTS` / `Qwen3-ASR` weights [30].
- **CLI / agentic coding: Qwen Code** (`npm i -g @qwen-code/qwen-code@latest`, Node 22+; standalone installer also
  offered) [1]. Fork-lineage of Gemini CLI. Features: Auto-Memory, Auto-Skills, SubAgents, Agent Teams, MCP, hooks,
  runtime provider switching (OpenAI / Anthropic / Gemini / Qwen / Ollama / vLLM) [1][8]. Latest v0.24.4 (2026-09-22) [9].
- **API + SDKs.** OpenAI-compatible Chat Completions and Responses API; DashScope native API; Python SDK `dashscope`
  1.27.7 (2026-09-24, Python ≥3.9) [70]; Java SDK `com.alibaba:dashscope-sdk-java` 2.23.1 (Maven Central, published
  ~2026-09-18, Apache-2.0) [78]. Model Studio's install page lists only Python and Java as official DashScope SDKs — there
  is **no official Node.js or Go DashScope SDK**; those languages are directed to the OpenAI SDK against the
  compatible-mode endpoint [79]. Base URLs (three families, all live):
  - QwenCloud: `https://maas.qwencloudapi.com/compatible-mode/v1` [21]
  - Model Studio new: `https://{WorkspaceId}.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1` [15]
  - Model Studio legacy: `https://dashscope-intl.aliyuncs.com/compatible-mode/v1` (Singapore), `https://dashscope.aliyuncs.com/compatible-mode/v1` (Beijing) [14]
- **Anthropic-compatible endpoint.** `/v1/messages` only (no model list) at `https://token-plan.ap-southeast-1.maas.aliyuncs.com/apps/anthropic`
  (Token Plan) [17] and `https://coding-intl.dashscope.aliyuncs.com/apps/anthropic` (Coding Plan) [18]. Anthropic-compatible
  endpoint for pay-as-you-go keys is documented (page updated 2026-09-22): `https://{WorkspaceId}.ap-southeast-1.maas.aliyuncs.com/apps/anthropic`
  with a normal Model Studio `sk-` key (Beijing and US-Virginia variants also listed). `/v1/models` returns 404 on all three
  base URLs; only `/v1/messages` is served [17].
- **MCP.** Qwen Code: `qwen mcp add --transport stdio|http|sse`, `mcpServers` in `~/.qwen/settings.json`, OAuth for
  remote servers, `includeTools/excludeTools`, `trust` [8]. OAuth for remote MCP servers needs a reachable callback: the
  default redirect is `http://localhost:7777/oauth/callback` (listener on 127.0.0.1:7777), which "will NOT work" on remote
  servers/cloud IDEs; pass `--oauth-redirect-uri https://<host>/oauth/callback` and reverse-proxy that path to
  `127.0.0.1:7777` (Qwen Code does not terminate TLS; the proxy must) [8]. The flow is browser-interactive, so on a
  headless daemon complete it once from an interactive session before scheduled runs. Model Studio also hosts cloud MCP
  services (FAQ) [2b].
  Qwen-Agent Python framework: `pip install -U "qwen-agent[gui,rag,code_interpreter,mcp]"` [71].
- **Batch API.** OpenAI-style JSONL upload → poll → download; **50 % of real-time price**; ≤500 MB, ≤50,000 requests/file,
  completion window 24 h–336 h; Beijing supports qwen3.8-max, qwen3.7-max, qwen3-max, qwen3.7/3.6/3.5-plus,
  qwen3.8/3.7/3.6/3.5-flash and legacy qwen-max/plus/flash (page updated 2026-09-10), **Singapore supports only
  qwen-max/plus/flash/turbo** [14].
- **Structured outputs.** `response_format: json_object` (most models) and strict `json_schema` (only Qwen3.7-Plus/Flash/Max
  and Qwen3.8-Max/Flash series; not with multimodal inputs) [15]. OpenRouter lists `structured_outputs`, `tools`,
  `tool_choice`, `reasoning`, `reasoning_effort`, `logprobs` for qwen3.8-max [41].
- **Tool use / built-ins.** Function calling; server-side tools: code interpreter, web search, PDF parsing, web fetch,
  image search [21][22]. Web search: `enable_search: true` (Chat) or `{"type":"web_search"}` (Responses, agentic multi-search) [16].
- **Computer-use / browser agent.** Qwen3.8-27B reports OSWorld-Verified 84.3, WebArena-Verified 64.8, AndroidWorld
  81.9 [24]; Qwen-Agent ships a browser assistant [71]. No hosted "computer use" product found.
- **Scheduled/automated tasks.** None in the consumer app that I could verify. Qwen Code offers a GitHub Action
  integration and daemon mode [5][7b].
- **Memory / projects.** Qwen Code Auto-Memory [1]; Qwen Studio memory: Not found — searched: qwen.ai, chat.qwen.ai (SPA login page only).
- **Messaging integrations (Qwen Code "channels").** Telegram, WeChat (weixin), DingTalk, WeCom, Feishu/Lark, QQ Bot,
  GitHub, GitLab, DWS, plugin channels [7b][5]. Telegram: BotFather token, `senderPolicy: allowlist`, `allowedUsers`,
  `sessionScope: user`, `cwd`, `qwen channel start <name>`; photos analyzed with a vision model, docs ≤20 MB; 4096-char
  message limit [6]. No Slack/Discord/WhatsApp channel listed [7b].
- **IDE plugins.** VS Code, JetBrains, Zed integrations [7b]; Coding Plan lists Claude Code, Cursor, Codex, Cline,
  OpenCode, Kilo CLI, Qoder, Lingma, Cherry Studio, Chatbox, OpenClaw, Hermes Agent, QwenPaw as supported clients [18].

## 3. Headless / server automation fit

- **Non-interactive CLI.** `qwen -p "..."` (stdin piping works: `cat file.py | qwen -p "Review"`), `--output-format
  text|json|stream-json`, `--include-partial-messages`, `--approval-mode plan|default|auto-edit|auto|yolo` (`--yolo` =
  auto-approve, **no sandbox by default**), `--safe-mode`, `--system-prompt` / `--append-system-prompt`, `--model`,
  `--include-directories`, `--continue`, `--resume <id>` [3].
- **Budgets and exit codes (orchestration-friendly).** `--max-session-turns` (exit 53), `--max-wall-time 5m|1h`, and
  `--max-tool-calls` (exit 55); 0 success, 130 SIGINT. JSON output is an array of `{type: system|assistant|result,
  subtype, session_id, result, usage, stats:{models:{tokens}, tools:{totalCalls, byName}}}`; extract with
  `jq -r '.[-1].result'`. `QWEN_CODE_UNATTENDED_RETRY=1` retries 429/529 indefinitely with capped backoff (opt-in) [3].
- **Daemon.** `qwen serve --port 4170 --hostname 127.0.0.1 --token ... --workspace <dir> --no-web --max-sessions 32
  --channel <name>`; REST + SSE (25-op OpenAPI 3.1 contract: `POST /session`, `POST /session/:id/prompt` → 202,
  `GET /session/:id/events` SSE with `Last-Event-ID` replay, `/transcript`, `/file`, `/glob`); bearer auth (token-free
  on loopback unless `--require-auth`); sessions persist on disk; documented for launchd/systemd [4][5].
- **Sandboxing.** macOS Seatbelt via `sandbox-exec` with six built-in profiles selected via `SEATBELT_PROFILE`:
  `permissive-open` (default; write-restricted, network allowed), `permissive-closed`, `permissive-proxied`,
  `restrictive-open`, `restrictive-closed`, `restrictive-proxied`, plus custom `.qwen/sandbox-macos-<name>.sb`; or
  Docker/Podman; enable with `QWEN_SANDBOX=`, `--sandbox`, or `tools.sandbox` in settings [7].
- **Auth modes.**
  1. **Qwen OAuth free tier — DISCONTINUED 2026-04-15** [2] (the "2,000 req/day" figure in the brief is dead).
  2. **Model Studio / QwenCloud API key (pay-as-you-go)** — `OPENAI_API_KEY` + `OPENAI_BASE_URL` + `OPENAI_MODEL` (or
     `DASHSCOPE_API_KEY`) — the only mode with no automation restriction. New accounts get 1M free tokens per model for
     90 days, Singapore/international scope only, real-time inference only [12]. A per-model **"Free Quota Only"**
     (worry-free) switch — off by default, toggled on the Free Quota tab or model detail page — makes the service return
     `AllocationQuota.FreeTierOnly` instead of billing once the quota is gone; it cannot be enabled for exhausted/expired
     quotas [12]. Dated snapshot IDs and the undated alias (e.g. `qwen3.8-max-0902` vs `qwen3.8-max`) are "treated as two
     independent models, each with its own free quota" [12] — so the trial for the same weights is effectively 2M tokens.
  3. **Coding Plan** (`BAILIAN_CODING_PLAN_API_KEY`, `sk-sp-…`) and **Token Plan** (`BAILIAN_TOKEN_PLAN_API_KEY`) —
     subscriptions, but **terms explicitly forbid non-interactive use**: "Do not use the plan's API key for automated
     scripts, application backends, or other non-interactive scenarios" [18]; Token Plan: "must not be used for
     automation scripts, custom application backends, or any non-interactive batch call scenarios… may result in
     subscription suspension or API Key banning" [20]. Account/key sharing is also prohibited [18][20].
  4. Third-party keys in Qwen Code (OpenRouter, Anthropic, Gemini, Vertex) [2].
- **Consumer subscription programmatic use.** There is no paid consumer plan to speak of; Qwen Studio ToS could not be
  fetched (SPA) — Not found — searched: chat.qwen.ai/legal/terms(-of-service), qwen.ai/terms, r.jina.ai render. Second
  attempt 2026-09-24: `chat.qwen.ai/terms`, `/privacy`, `/legal/terms-of-service`, `/legal/privacy-policy` all render the
  login shell whose own "Terms of Service" and "Privacy Policy" links point back at the same shell URL (`/terms` →
  `/terms`, `/privacy` → `/privacy`); `qwen.ai/terms` and `qwen.ai/legal-agreement` return the marketing homepage
  [89][90]. The documents evidently exist only behind login. **Decision: treat Qwen Studio as a lane with *no readable
  contract* — excluded from every automation, third-party-serving and data-handling matrix in this research set, not
  merely "unknown".** It also has no API, so nothing is lost operationally.
- **Rate limits (PAYG).** Account-level, independent of spend (topping up does not raise limits) [13]. `qwen3.8-max`:
  TPM 1M / RPM 15K [21]; `qwen3.8-27b`: TPM 5M / RPM 5K [22]; `qwen3.7-plus`: 15,000 RPM / 5M TPM [13]; `qwen3-max`
  600 RPM / 1M TPM; `qwen3-coder-plus` 5,000 RPM / 5M TPM [13]. Batch is exempt from RPM/TPM [13] (unverified as of
  2026-09-24 for qwen3.8-* models: the rate-limit page states the exemption only for qwen-max/qwen-plus/qwen-flash; the
  batch doc does not restate it for Qwen3.8).
  **Reconciliation of Model Studio "Dynamic" vs QwenCloud headline limits (resolved 2026-09-24).** Model Studio's
  rate-limit page (updated 2026-09-24) marks qwen3.8-max / -flash / -27b "Dynamic" in both regions and defers to the
  quota-management page, which publishes the actual spend-tiered **TPM baselines** [13][81]; QwenCloud's model pages
  print a single number per model with no tier note [21][22]. Read side by side:

  | Model | Model Studio Singapore TPM by monthly-spend tier (≤100K / 100K–1M / >1M, platform currency) | Model Studio Beijing TPM | QwenCloud headline | Reading |
  |---|---|---|---|---|
  | qwen3.8-max | 2M / 5M / 10M | 5M / 10M / 20M | 1M TPM, 15K RPM | QwenCloud's 1M is *below* Model Studio's bottom tier — a conservative marketing floor, not a different regime |
  | qwen3.8-flash | 2.5M / 5M / 10M | 5M / 10M / 20M | (no page) | — |
  | qwen3.8-27b | 5M (all tiers) | 5M (all tiers) | 5M TPM, 5K RPM | identical — the 27B is not spend-tiered |
  | qwen3.7-plus (static, for scale) | 5M TPM / 15K RPM | 5M TPM / 30K RPM | — | non-dynamic models publish fixed numbers [13] |

  RPM under dynamic limiting is deliberately unpublished: "A model has a relatively large RPM limit… RPM rate limiting
  is not triggered during normal use" [81]; when a limit trips it "usually recovers within one minute" [13]. Tiers are
  computed on the calendar-month bill, announced on the 10th, effective on the 15th, aggregated by primary account across
  RAM users/workspaces/keys [13][81]; the default tier for a brand-new account is not stated, so assume the bottom row.
  **Planning number for this server: 2M TPM on `qwen3.8-max` and 2.5M TPM on `qwen3.8-flash` (Singapore, bottom tier),
  soft, not an SLA.** At 165K tokens/job that is ~12 concurrent max-jobs or ~15 flash-jobs per minute before the soft
  ceiling — far above anything the scheduler will fan out. The QwenCloud numbers should no longer be cited as the
  Model Studio limits; they are only correct for the `maas.qwencloudapi.com` front door, and even there are unexplained.
- **Streaming.** SSE on all OpenAI-compatible endpoints; `stream-json` in the CLI [3][42].
- **Session resume.** `--continue`, `--resume <sessionId>`, daemon `POST /session/:id/resume|load` (with branching) [3][5].
- **Reliability (normalized: StatusGator, trailing 90 days to 2026-09-24).** StatusGator tracks "Alibaba Cloud Model
  Studio" as a component: **0 incidents in the last 30 days, 1 in the last 90** (2026-07-28, "Minor incident", warning
  severity, 3 h 55 min) [80]. DashScope/Bailian are not separately tracked, and status.alibabacloud.com renders empty
  (JS-only), status.qwencloud.com does not resolve [80]; HN Algolia for dashscope/"qwen api" outage: 0 hits [73]. **No
  priority/SLA tier is sold** — the only throughput lever is the spend-tiered "dynamic rate limit" (below), which is a
  soft baseline, not an SLA [81]. Use the StatusGator figure (1 incident / 90 d) as this doc's entry in the cross-vendor
  reliability row; it is a single-source count and should be read as a floor.
- **Progress-visibility / usage introspection.** *No programmatic quota endpoint.* Model Studio's rate-limit page names
  no `x-ratelimit-*` headers or quota API; the only view is the console (`O&M Management > Monitoring`, "minute(s)-level
  and for reference only") [13]. Qwen3.8 models are on **dynamic rate limiting**: the TPM baseline is "determined by tier
  based on your monthly consumption amount on Bailian… adjusted every month" (notification on the 10th, new tier on the
  15th), aggregated "by account + model" across all workspaces and API keys, and *soft* ("if the platform still has spare
  resources, rate limiting is not triggered"); the current tier/TPM is visible only on the console's **Quota management**
  page [81]. Billing/usage OpenAPI and observability doc pages (`billing-overview`, `bills`, `monitoring`,
  `observability`, BSS `QueryAccountBill`) all returned 404 on 2026-09-24 — unverified whether the generic Alibaba Cloud
  BSS bill API covers Model Studio. **Qwen Code side is better:** `/stats` (alias `/usage`) opens a Session/Activity/
  Efficiency dashboard; `/stats model|tools|skills|daily|monthly`; and **`/stats export`** writes CSV/JSON for a date
  range [82] — that plus headless JSON `stats` [3] is the machine-readable path. OpenTelemetry is **opt-in**
  (`telemetry.enabled` default false; `QWEN_TELEMETRY_ENABLED`, `QWEN_TELEMETRY_OTLP_ENDPOINT` default
  `http://localhost:4317`, `QWEN_TELEMETRY_OUTFILE`); it logs prompts/responses, tool calls, tokens by type
  (input/output/thought/cache), API latency and retries; `logPrompts` defaults **true** (`QWEN_TELEMETRY_LOG_PROMPTS`),
  so set it false before pointing at any shared collector; nothing is sent to Alibaba unless an ARMS endpoint is
  configured [83]. Net: **per-job token telemetry = yes (CLI stats/OTEL); remaining-budget introspection = no** (PAYG
  has no budget to introspect; Token/Coding Plan quotas are irrelevant because those plans are not usable here).
- **Data handling per lane (training use / retention / residency / ZDR).** Model Studio's "Security certifications and
  privacy" page (updated 2026-09-20) states Alibaba Cloud "will never use your data for model training", transit
  encryption AES-256, and SOC 2 (unqualified opinion; Security, Availability, Confidentiality) [84][85]. It also says
  "Model Studio stores data generated from model and application calls" **with no retention window stated**, no
  deletion procedure, no content-moderation-review statement and no zero-data-retention option [84]. Residency follows
  the endpoint: Singapore (`dashscope-intl`, `ap-southeast-1`), Beijing, or US-Virginia/Frankfurt/Tokyo/HK for a subset
  [11][16][17]. The Alibaba Cloud International privacy policy (updated 2026-09-04) says personal data is retained "as
  long as you have an account… or as required or permitted by applicable laws" and may be transferred cross-border [86];
  the Product Terms of Service (updated 2026-08-28) contain no Model Studio / generative-AI clause at all [87], and the
  Model Studio service-terms and data-privacy-and-security pages 404 [84]. QwenCloud's privacy policy (updated
  2026-04-01) collects "prompts, and other input content… and Output Data", stores in Singapore, retains "where we have
  an ongoing legitimate need", and is **silent on training use** [88]; its terms page 404s.

  | Lane | Training on inputs | Retention window | Residency | ZDR / enterprise opt-out |
  |---|---|---|---|---|
  | Model Studio PAYG API key (`sk-`) | **No** — "will never use your data for model training" [84] | **Not stated** (call data is stored) [84] | SG / Beijing / US-VA / FRA / Tokyo / HK by endpoint [11][16] | Not offered |
  | QwenCloud PAYG (`maas.qwencloudapi.com`) | Not stated [88] | "ongoing legitimate need" [88] | Singapore [88] | Not offered |
  | Coding Plan / Token Plan (`sk-sp-`) | Same platform as Model Studio; plan pages silent | Not stated | ap-southeast-1 only [18][19] | n/a — non-interactive use forbidden anyway [18][20] |
  | Qwen Studio consumer (chat.qwen.ai) | Not found (ToS/privacy are login-gated SPAs) | Not found | Not found | n/a |
  | Open weights via OpenRouter / Cerebras / DeepInfra / local | Governed by the host, not Alibaba (OpenRouter's per-provider data-policy table did not render) [40][47][67] | per host | per host | local = ZDR by construction |

  Verdict for the paper-trading lab: **proprietary theses may go to the Model Studio PAYG lane on the no-training
  statement alone, but only with the "retained for an unstated period, reviewable" assumption** — i.e. no credentials,
  no PII, no un-hashed position sizes — until a retention window is published. Third-party hosts and the consumer app
  stay off-limits for theses.

  **Retention window — what could and could not be pinned down (2026-09-24).** Re-fetched the international
  privacy-notice page [84] (updated 2026-09-20) and the China-site Bailian equivalent [91]: both say only that Model
  Studio "stores data generated from model and application calls" ("according to relevant laws and regulations" on the
  China page) and defer to a "Service Agreement" that 404s on both sites. Neither states a days figure, a deletion
  procedure or a moderation-review clause. What *is* stated: (i) **uploaded files "do not expire" and are "permanently
  stored in your account unless deleted"** (Files API, 10,000 files / 100 GB, deletable via API; updated 2026-09-11)
  [92] — so any batch-input JSONL or PDF pushed through the Files API is retained indefinitely by default and the job
  must delete it; (ii) **API keys "do not expire"** (updated 2026-09-11) [93]; (iii) account-level personal data is
  retained "as long as you have an account" [86]. Working assumption for the matrix: **inference logs = indefinite until
  proven otherwise; files = indefinite by contract, delete-after-use is the job's responsibility.** This is worse than
  the OpenAI/Anthropic 30-day-default posture and should be scored as such in `crosscut-tos`.

  **Beijing region — data-residency trade-off scored (2026-09-24).** The Beijing endpoint is the only place Qwen3.8
  batch (50 % off) exists [14]; Singapore batch is legacy-only. Against that: the regions page (updated 2026-09-24)
  lists six regions (`cn-beijing`, `ap-southeast-1`, `eu-central-1`, `ap-northeast-1`, `cn-hongkong`, `us-east-1`),
  each with its own key and model list, "cannot be used across regions", and "your static data always remains in the
  selected region" [94] — i.e. choosing Beijing places stored call data and files under PRC jurisdiction. The
  international privacy policy adds that using "servers located in the PRC" triggers photo-ID collection for legal
  verification, that data may be disclosed "in response to lawful requests by public authorities, including to meet
  national security or law enforcement requirements", and it does **not** say whether PRC-stored data falls under PIPL
  [86]. Web search is also 17× cheaper there ($0.573 vs $10 per 1k calls) [16]. Neither the get-api-key page nor the
  regions page says whether an international-site account can even mint a Beijing key [93][94] (unverified as of
  2026-09-24). Score: for a trading-research lab whose prompts contain proprietary theses, **the 50 % batch saving on a
  $39/100-job line item (~$20/month at 100 jobs) does not buy PRC-jurisdiction storage of the corpus plus a second
  key/region to manage** — Beijing is **rejected**; Singapore PAYG real-time is the only Qwen region for this server.
  Revisit only if a non-sensitive, public-data bulk job (e.g. classifying public filings) reaches ≥1,000 jobs/month,
  where the saving becomes ~$200/month.
- **Third-party-serving permission per lane** (may non-owner users consume outputs — pickem dashboard, shared project
  sites?). PAYG API key: **yes** — no clause found restricting serving outputs to your own end users; this is a
  standard cloud product, and the Product Terms carry no AI-specific restriction [87] (service-specific Model Studio
  terms 404, so this is absence-of-prohibition, not affirmative permission). Coding Plan / Token Plan: **no** — "Do not
  use the plan's API key for… application backends" and key/account sharing is prohibited [18][20], which rules out any
  second-person surface. Qwen Studio consumer: unknown (ToS unreadable) — treat as personal-use-only like every other
  consumer chat product. OpenRouter/Cerebras-hosted open weights: yes under those hosts' commercial terms [48][68];
  Apache-2.0 weights (27B/3.6/3.5) carry no serving restriction [24][28]; Qwen3.8-Max weights add license terms only above
  100M MAU / $20M monthly revenue [27].
- **Tool-churn cost of ownership.** Qwen Code shipped **v0.24.3 (2026-09-21), v0.24.4 (2026-09-22), v0.24.5-preview.0
  (2026-09-22)** plus nightlies and a separate `sdk-typescript` v0.1.14 (2026-09-21) — roughly one stable release per day
  in the sampled week; v0.24.4 notes "No known breaking changes" and no default flips or deprecations were flagged in the
  window [9]. The churn that *does* bite is on the model side: ~6-weekly point releases with fast deprecation (403 on
  the Anthropic-compatible endpoint once a model is "marked for upcoming deprecation") [17][31], and the mid-cycle Lite
  plan / OAuth-tier shutdowns [2][18]. Pin the CLI (`@qwen-code/qwen-code@0.24.4`) and dated model snapshots
  (`qwen3.8-max-0902`, `qwen3.7-plus-20260602`); budget a monthly model-ID review. Comparable burden to Codex-weekly;
  lighter than Antigravity's 10-releases/13-days; heavier than a pinned Python SDK.
- **Cross-doc dimension answers for this lane (added 2026-09-24; feed the cross-cut matrices).**
  - *Concurrency per lane.* PAYG: **no concurrency cap** — the only limits are account-level TPM (tiered, table above)
    and an unpublished "relatively large" RPM [13][81]; parallel headless `qwen -p` processes are bounded by TPM
    (~12 max-jobs or ~15 flash-jobs in flight per minute at the bottom tier). `qwen serve` caps fresh sessions at
    `--max-sessions 32` (503 + `Retry-After: 5` when hit; attaches not counted) [95]. Subscription lanes publish
    concurrency (Token Plan 1–2 / 2–3 / 3–4 / 6–8 "concurrent agents" [19][20]) but are interactive-only, so they do not
    enter the scheduler's fan-out design. This is the *only* lane in the set whose automation-legal mode has no
    session-count ceiling at all.
  - *Credential lifecycle on a headless box.* Model Studio keys **never expire** ("valid until you manually delete
    them") [93]; no refresh, no browser, so nothing fails first on renewal — the failure modes are key deletion and the
    free-quota hard stop (`AllocationQuota.FreeTierOnly` [12]). Storage: Qwen Code reads `OPENAI_API_KEY` /
    `DASHSCOPE_API_KEY` from the shell, then `.qwen/.env` (walking up from cwd), `.env`, `~/.env`, then the `env` field
    of `~/.qwen/settings.json` — all **plaintext files**, no Keychain option for API keys [96]. MCP OAuth tokens land in
    `~/.qwen/mcp-oauth-tokens.json` (plaintext, mode 0600) unless `QWEN_CODE_FORCE_ENCRYPTED_FILE_STORAGE=true`
    (Keychain or AES-256-GCM); they are refreshed automatically "if refresh tokens are available" and validated before
    each connection [97]. Daemon bearer token: `--token` / `QWEN_SERVER_TOKEN`; ephemeral tokens rotate on restart and
    are not persisted; loopback without a token exposes "the full operator API" to any local process [95]. Matrix row:
    **TTL = none; silent refresh = n/a (API key) / automatic (MCP OAuth); storage = plaintext env/.env by default;
    alarm needed = free-quota exhaustion only.**
  - *Progress-visibility sink.* Emitters are covered above (`stats` JSON, `/stats export`, opt-in OTEL) [3][82][83].
    On the collector side Qwen Code's OTLP default is `http://localhost:4317` (gRPC) or a JSONL `QWEN_TELEMETRY_OUTFILE`
    [83]; the file exporter is the zero-daemon path — a launchd job can tail one JSONL per run into the existing audit
    log without running an OTEL collector at all. Whatever cross-lane event schema the plan adopts, the Qwen lane can
    populate `tokens{input,output,thought,cache}`, `api_latency`, `retries`, `tool_calls.byName` and `exit_code`
    (0/53/55) per job today; **remaining-budget cannot be inferred** because PAYG has no budget and the console's tier
    page is not an API [81]. Recommendation for the dashboard: show Qwen as spend-to-date (computed from the JSONL
    tokens × list price), not as a quota bar.
  - *Empirical calibration against this server.* Not done in this doc (the brief forbade reading other repo files, and
    `volumes/audit_log` is out of scope here). The cost tables use the synthetic 150k-in/15k-out job with a 70 %
    *implicit*-cache case; at Qwen's prices the verdict is insensitive to the real numbers — even a 3× token overrun
    with 0 % cache leaves `qwen3.8-flash` under $0.10/job. The calibration owed by the cross-cut doc matters for the
    Claude/OpenAI subscription-vs-metered flip, not for this lane.
  - *Prompt-injection / sandbox posture.* Ingest paths: Telegram channel (allowlist/pairing on *who*, nothing on
    *what* — the channel doc has no injection guidance and does not say whether channel sessions auto-run tools) [6][98];
    MCP tool results (no untrusted-result handling documented; `trust: true` skips tool-call confirmations in a trusted
    workspace, `excludeTools` wins over `includeTools`) [97]; `--yolo` runs with **no sandbox by default** [3]. Mitigation
    available: six Seatbelt profiles, all of which "restrict writes outside the project directory"; `*-closed` blocks
    network, `*-proxied` routes through a `QWEN_SANDBOX_PROXY_COMMAND` listening on `:::8877` with an allowlist [7].
    Ranking within this research set: **middle** — better than opencode-style bypasses and Perplexity's approval-free MCP
    (there is a real OS sandbox and a network-proxy allowlist), worse than Claude's verbatim-prompt handling and Hermes'
    injection scan (no content-level defence at all). Server rule: run Qwen Code under `restrictive-proxied` for any job
    that reads fetched web pages or Telegram text, with the proxy allowlist limited to the Model Studio endpoint.
  - *Host resource budget.* Qwen Code is a Node 22 CLI [1]; per-process RSS is not documented. `qwen serve` derives a
    default `--memory-budget-mb` of "50 % of the cgroup limit or host memory" (8 GB on the 16 GB M4) and journals up to
    5 % of that (≤1 GB) [95] — set it explicitly (e.g. 2048) beside Postgres/Redis. The proposed local models are
    `qwen3.5:9b` (6.6 GB) / `:4b` [37], which cannot coexist with a Q2 27B (10.7 GB) [55]. No always-on Qwen daemon is
    required for the PAYG path (`qwen -p` per job), which is the recommended shape.
  - *Reviewer independence.* The prefill experiment [61] found Qwen3.8's answers move toward GPT-5.5 Pro's when seeded
    with 1 % of its reasoning (+18.2 pp overlap), with no Claude condition run; so the only evidence points at an
    *OpenAI* lineage signal, none at Anthropic. For a Claude-primary server that makes Qwen a **better** second-opinion
    lane than a GPT one on the correlated-error argument, not worse — but the honest statement is that independence
    from Claude is *unmeasured*. Cheap test the plan should include: re-run the gist's protocol with a Claude Opus 5.5
    prefill on 50 STEM items; if overlap moves by >10 pp, downgrade Qwen's adversarial-review weight.
  - *Chat-surface latency.* Qwen's numbers are already measured (§5: TTFT 2.9–4.0 s, ~9–10 s for 500 tokens on
    Flash-Next) [49][50][51]; the missing Claude Sonnet 5 / Opus 5.5 TTFT belongs to the claude doc, not this one.

## 4. Cost

**Consumer plans.** Qwen Studio: free, no verified paid tier [34][74] (unverified as of 2026-09-24 — could not confirm or
refute; qwen.ai still says "free to use, open to all" with no plan tiers shown). (No ChatGPT-Plus-style product found.)

**Developer subscriptions (interactive-tool use only — see §3).**

| Plan | Price | Includes | Cite |
|---|---|---|---|
| Coding Plan Pro | $50/mo | 6,000 req / 5 h; 45,000 / week; 90,000 / month; models qwen3.7-plus, qwen3.6-plus, kimi-k2.5, glm-5, MiniMax-M2.5, qwen3.5-plus, qwen3-max-2026-01-23, qwen3-coder-next/plus, glm-4.7; ap-southeast-1 only. Lite tier: no new subscriptions from 2026-03-20 00:00 (UTC+8); renewals and upgrades ceased 2026-04-13 18:00 (UTC+8); existing subscribers run to expiry then must move to Pro. | [18] |
| Token Plan Lite / Essential / Standard / Pro | $6 / $10 / $18 / $68 per month (limited-time; list $8/$16/$25/$80) | 11,500 / 25,500 / 45,000 / 180,000 credits/mo; 1–2 / 2–3 / 3–4 / 6–8 concurrent agents; extra bundle $15 = 20,000 credits (max 5); models incl. qwen3.8-max, 3.8-flash, 3.7-max, 3.7-plus, 3.6-flash, DeepSeek v4.x, GLM-5.x; Singapore only; "around 40% off" PAYG per marketing. Credit burn per token is **undisclosed** ("dynamically determined by model type, token usage, thinking mode, and tool calls"). | [19][20][23] |
| Token Plan Team | Standard seat $20/mo (list $30), Pro seat $75/mo (list $100), Max seat $200/mo (no discount shown); 25K / 100K / 250K credits per seat; shared quota pack $700/mo = 625,000 credits | limited-time discount on Standard/Pro seats, no stated end date | [19] |

**API list prices, Singapore/international region, USD per 1M tokens** (page last updated 2026-09-24) [10]:

| Model | Input | Output | Cached input | Notes |
|---|---|---|---|---|
| qwen3.8-max | 2.00 | 6.00 | implicit cache hit 0.25 (12.5 % of input), explicit cache read 0.17, explicit cache create 2.50 per QwenCloud [21]; Model Studio's context-cache page says qwen3.8-max/-0902/-flash/2.4t-a95b are exceptions to its usual 10 % explicit-hit / 20 % implicit-hit rule (explicit cache TTL 5 min, reset on hit) [77] | Beijing 1.65 / 4.951; batch 50 % (Beijing only) [10][14] |
| qwen3.8-max-prime | 4.00 | 12.00 | 0.50 cache read (write not listed) | higher-throughput SKU; OpenRouter-only attestation, created 2026-09-23 [75]; provisional (unverified as of 2026-09-24) |
| qwen3.8-flash | 0.15 | 0.47 | 0.016 | cached price: Model Studio pricing page shows a cached price only for qwen3.8-omni-flash in the fetched table; OpenRouter's Alibaba endpoint confirms $0.016 cache read / $0.20 cache write for qwen3.8-flash [42] (Model Studio figure unverified as of 2026-09-24) |
| qwen3.8-omni-flash | 0.15 | 0.47 | 0.016 | audio priced separately (unverified) |
| qwen3.8-27b (hosted by Alibaba) | 0.50 | 3.00 | 0.10 implicit / 0.05 explicit read | [22]; AA lists same [50] |
| qwen3.7-plus | 0.40–1.20 | 1.60–4.80 | 10 % | tiered by prompt length (32K/128K/256K/1M); Model Studio marks qwen3.7-plus "Limited-time 20% off"; OpenRouter's Alibaba endpoint shows 0.32 / 1.28 (<256K) and 0.96 / 3.84 (≥256K) for `qwen3.7-plus-20260602` [43], i.e. exactly the 20 %-off promo price — not a conflict, but the promo has no stated end date [10] |
| qwen3-max (legacy) | 1.20–3.00 | 6.00–15.00 | 10 % | tiered |
| qwen3-coder-plus | 1.00–6.00 | 5.00–60.00 | — | tiered; expensive at long context |
| qwen3-coder-flash | 0.30–1.60 | 1.50–9.60 | — | tiered |
| qwen-plus / qwen-flash (legacy) | 0.40–1.20 / 0.05–0.25 | 1.20–3.60 / 0.40–2.00 | — | only these + qwen-max/turbo are batch-eligible in Singapore [14] |
| Web search tool | — | — | — | $10.00 per 1,000 calls in Singapore; $0.573 per 1,000 in China/US/HK/Tokyo/Frankfurt [16] |

**Third-party hosting of open weights (OpenRouter, USD/1M in/out)** [40][44][45]: qwen3.8-27b from $0.094/$4.40 (Reka)
to $0.45/$3.20 (Cloudflare), DeepInfra bf16 $0.15/$1.875, Alibaba $0.425/$2.55; qwen3.5-397b-a17b Alibaba $0.39/$2.34;
qwen3-coder-480b DeepInfra $0.30/$1.00, Google $0.22/$1.80. **Free endpoints:** `qwen/qwen3.8-27b:free` (ModelRun,
262K ctx, $0) [47] and `qwen/qwen3-coder:free` [46]; OpenRouter free-model caps are 20 RPM and 50 req/day, or 1,000
req/day once the account has bought ≥$10 credits lifetime [48]. Cerebras serves `qwen-3.8-27b` at ~1,850 tok/s for
$0.99/$1.49, free trial 5 RPM / 30K uncached TPM / 1M tokens/day (64K context on free tier, 128K paid); the $5 starter
credit is granted only after adding a verified payment method and expires in 30 days [67][68][69].

**Free API quota (PAYG account):** 1,000,000 tokens per model, 90 days (from the later of account activation / model
release / request approval; unused quota is voided, not extended), Singapore/international only, real-time only [12].
At 165K tokens/job that is ~6 jobs per model — a trial, not a tier. Dated snapshot and undated alias each carry their own
1M (e.g. `qwen3.8-max` + `qwen3.8-max-0902` = 2M for the same weights), and the "Free Quota Only" switch hard-stops
billing at zero [12] — useful for a no-surprise evaluation window.

**Context-cache economics (material to the cache scenario below)** [77]: explicit cache TTL is 5 minutes, reset to 5 on
each hit; cache creation is billed at **125 %** of the input rate and explicit hits at 10 % (implicit hits 20 %), except
for qwen3.8-max/-0902/-flash/2.4t-a95b, which have their own rates (qwen3.8-max: create 2.50 / explicit read 0.17 /
implicit hit 0.25 per QwenCloud [21]). Consequence: explicit caching only pays when a prefix is re-read within 5 minutes
at least ~1.25/(1−0.085) ≈ 1.4× — i.e. two or more hits per creation; a scheduled job that runs once per hour and
re-reads its context cold gets **no** explicit-cache benefit and pays the 25 % surcharge on top. Implicit caching is free
to attempt and needs no TTL management, so it is the realistic path for our job shapes.

**Monthly cost estimate — 10 / 100 / 1000 agent jobs.** Assumptions: 150K input + 15K output per job; no prompt
caching (the "70 % cache hits" case below assumes *implicit* hits at qwen3.8-max's 0.25 rate, i.e. ~61 % off input;
explicit caching's 125 % creation surcharge and 5-minute TTL [77] make it a net loss for once-per-hour jobs); single-region list
prices [10][22][40]; thinking tokens billed as output and *not* included (Qwen3.8 is "very verbose" per AA [49][50], so
real output could be 2–5× higher — treat these as floors).

| Path | Per job | 10 jobs | 100 jobs | 1,000 jobs | Notes |
|---|---|---|---|---|---|
| (a) Subscription — Token Plan / Coding Plan | n/a | n/a | n/a | n/a | **Not permitted** for non-interactive/backend use [18][20]; credit-per-token undisclosed, so cannot be priced anyway |
| (a′) Qwen Studio consumer | $0 | $0 | $0 | $0 | no API; manual only |
| (b) API `qwen3.8-max` PAYG | $0.39 | $3.90 | $39 | $390 | $195 with Beijing batch; ~$0.21/job with 70 % implicit cache hits (150K × (0.3 × 2.00 + 0.7 × 0.25) + 15K × 6.00) |
| (b) API `qwen3.8-max-prime` (provisional) | $0.78 | $7.80 | $78 | $780 | 2× Max for throughput; no batch/cache-write data; price unverified as of 2026-09-24 [75] |
| (b) API `qwen3.7-plus` | $0.067 (OpenRouter-listed Alibaba rate) / ~$0.084 (Model Studio floor tier) | $0.67–0.84 | $6.7–8.4 | $67–84 | tier boundary at 128K/256K may raise this |
| (b) API `qwen3.8-flash` | $0.030 | $0.30 | $3.0 | $30 | cheapest hosted reasoning model |
| (b) API `qwen3.8-27b` hosted | $0.12 (Alibaba) / $0.05 (DeepInfra) / $0.17 (Cerebras) | $0.5–1.7 | $5–17 | $50–170 | |
| (c) OpenRouter `:free` 27B | $0 (+$10 once) | $0 | $0 | $0 if ≤1,000 req/day | ~30 tool turns/job ⇒ ~33 jobs/day ceiling; ModelRun reliability unverified [47][48] |
| (d) Local 27B on the M4 16 GB | $0 marginal | feasible | marginal | infeasible | only Q2 fits (10.7 GB) [55][57]; ~14 tok/s gen at Q4 on M3 Ultra [57], slower on M4 ⇒ ≥1 h/job ⇒ ~1,000 h for 1,000 jobs |

## 5. Strengths & weaknesses per reviews

**Benchmarks (vendor-reported unless noted).**
- Qwen3.8-Max (2.4T-A95B) model card: SWE-bench Pro 67.7 (Claude Opus 4.8 69.2, GPT-5.6 Sol 64.6), GPQA Diamond 92.6
  (92.0 / 94.1), PaperBench 93.0 (80.3 / 90.5) [26]; launch post adds FrontierSWE 73.5 vs Opus 70.0, Parametric CAD 91.5 [32].
- Qwen3.8-27B card: Terminal-Bench 2.1 73.0 (Opus 4.6 Max 78.2), SWE-bench Pro 61.7 (Opus 53.4), GPQA 89.2, HLE 30.8
  (Opus 40.0), LiveCodeBench v6 90.3, IFBench 79.5, OSWorld-Verified 84.3, MathVision-CI 94.6, CoWorkBench 70.7 [24].
- Qwen3.8-Flash-Next card: GPQA 91.7, SWE-bench Pro 62.5, CoWorkBench 73.9 [25].
- Qwen3.6-35B-A3B card: SWE-bench Verified 73.4, AIME 2026 92.7 [28]. Alex Ellis cites Qwen3.6-27B at 77.2 % SWE-bench
  Verified vs Opus 88.6 % [58].
- **Independent:** arena.ai text (2026-09-13): qwen3.8-max #22 (1481±6); qwen3.7-max-preview #34; qwen3.7-plus #62;
  qwen3.5-397b-a17b #82; qwen3.8-27b #90 (1437±6). Top slots are Anthropic/Meta/Google/OpenAI; best Chinese model is
  kimi-k3-max #17 (1485) and glm-5.3-max #19 [53]. Artificial Analysis: qwen3.8-max Intelligence Index 45, #24/210,
  39.2 tok/s (median 70.1), TTFT 3.03 s, 190M eval output tokens ("very verbose"), $5.41 per AA task [49]; qwen3.8-27b
  index 34, **#1/142 open-weight peers**, 42.7 tok/s, $1.01/task [50]; Flash-Next index 40, #6/113, 53.2 tok/s,
  $0.37/task [51]. AA's overall index top is Claude Opus 5.5 at 58 [52]. HN reported (2026-08-06) that AA's *agentic*
  index briefly ranked Qwen3.8-Max best overall [66] — unverified as of 2026-09-24: no such story found; Algolia shows
  instead "Qwen3.8 27B scores 52 on Artificial Analysis" (2026-08-17, 381 pts). That 52 vs today's 34 for the same model
  suggests AA rescaled its Intelligence Index between mid-August and now; the absolute AA numbers above (45 / 34 / 40) are
  on today's scale only and are not comparable to August-era citations.
- Terminal-Bench 4.0 and SWE-bench Verified public leaderboards could not be parsed (tables load client-side).
- **Interactive-surface latency (Telegram round trip).** Artificial Analysis (Alibaba first-party API): qwen3.8-max
  TTFT 3.03 s, 39.1 tok/s [49]; qwen3.8-27b (xhigh) TTFT 4.04 s, 41.2 tok/s [50]; Flash-Next TTFT 2.86 s, 54.1 tok/s,
  **~9–10 s end-to-end for 500 output tokens** [51]; qwen3.8-flash has no AA latency figure (page 404) — assume the
  Flash-Next envelope. Omni-Flash-realtime TTFT 591–981 ms is voice-path only [33]. Rating for the chat surface:
  **acceptable with streaming and thinking off** (2–4 s to first token, a 300-token reply in ~10–12 s), **poor with
  thinking on** (verbosity is at the high end of AA's peer set: 190M/200M/240M eval output tokens vs 88–140M medians
  [49][50][51]). Telegram's 4096-char limit [6] plus edit-in-place streaming makes flash-class models the only
  sensible chat routing; never route the front door to `qwen3.8-max` with thinking.

**What reviewers say it is BEST at.**
- *Local coding agent per dollar.* Simon Willison: the 17 GB Q4_K_M 27B "can do all of this stuff on my home
  machines… a miracle"; drives coding-agent loops, builds and tests Python tools, "absolutely beautiful" SVG and precise
  bounding boxes [54]. XDA: a local 27B "took half an hour to tear apart a commercial application's authentication
  system and build a working bypass" via static ARM64 analysis, self-correcting a wrong key [59] (note: the test ran at
  Q8 on a 128 GB Lenovo ThinkStation PGX at 15–50 tok/s — workstation-class hardware, not a consumer laptop). HN
  (NorwegianDude, not Balinares): "If the benchmarks are a real indication, we now have a local model that is runnable on
  a high-end personal PC that trades blows with the leading model Claude Opus 4.6 Max from half a year ago" — a hedged,
  benchmark-conditional remark; (hadlock) "99 % agent completion rate… on Qwen 3.8 27B @ NVFP4" [62].
- *Vision + GUI agents* — OSWorld/AndroidWorld/WebArena leadership at 27B [24]; consistent praise for document/vision [54].
- *Quantization robustness.* Quesma: Q4_K_M (17 GB) ≈ BF16 on GPQA/IFBench/Terminal-Bench 2.1 (~94/80/77 % vs BF16 ~95/80/77 %); Q2_K_XL
  (10.7 GB) drops Terminal-Bench to ~72 %; IQ1 (6.2 GB) "around random chance" [55]. HN: Q6 is the practical sweet spot,
  and turning reasoning off at Q6 often "solves the task in record time" (anyfoo) [65].
- *Economics.* Emerging Trajectories (published 2026-07-19, i.e. before Qwen3.8-Max or its weights shipped, so this is
  pre-release speculation): Qwen 3.8 and Kimi K3 are "allegedly close to Anthropic's Fable 5", Fable 5 is
  "nearly 3× as expensive per completed task", and this is "much larger than the DeepSeek moment of 2025" [60]. HN on
  Flash-Next (monster_truck): "90M cached in/400k out for $0.45 is wild" [64] (unverified as of 2026-09-24 — this comment
  could not be found in HN item 49448210 via the Algolia items API; the thread discusses the $0.16/$0.47 pricing but not
  that quote).

**Weaknesses.**
- *Overthinking / verbosity.* Willison: default `xhigh` effort spent 21 minutes and 22,276 reasoning tokens on a pelican
  SVG — "Was that worth waiting 21 minutes for? Absolutely not… Run Qwen 3.8 27B on low or even no reasoning levels at
  first" [54]. AA flags both 3.8-Max and 27B as "notably slow and very verbose" [49][50]. Terminalbytes: 3.8-27B
  generates at half the speed of 3.6-27B but uses ~50 % fewer tokens, so wall-clock is similar [57].
- *Long-horizon reliability of local models.* Alex Ellis (Qwen3.6-27B on a $12K RTX 6000 Pro): infinite repetition
  "burning 600W of electricity for half an hour", miscounting 27.3K as 273,000, "I'd never leave Qwen 3.6 27B working on
  a long horizon task"; good for bounded, well-documented jobs and reading/explaining code [58].
- *Hosted 27B is pricey for its size* — AA: "particularly expensive when comparing to other open weight models of similar
  size" at Alibaba's $0.50/$3.00 [50]; third-party hosts are 3–5× cheaper [40].
- *Speed on Apple silicon.* 15–30 tok/s on an M5 Max 128 GB [54]; ~14 tok/s Q4 on M3 Ultra [57]; ~8 tok/s for a
  quantized Qwen3.6-35B on an M3 Air 16 GB (HN) [62]. Cerebras/DGX-class hardware is where it shines.
- *Benchmark-gaming suspicion.* HN (dofm): "Qwen is fine-tuned on youtuber test cases; it's too certain right off the bat
  in low reasoning mode" [62] (unverified as of 2026-09-24 — no such comment surfaced in HN item 49299605 via the Algolia
  items API); skeptics on the Max launch thread about structural-engineering demo claims [63].
- *Distillation controversy.* A widely-shared experiment (HN 237 pts) found that prefixing Qwen 3.8's reasoning channel
  with the first 1 % of GPT-5.5 Pro's reasoning raised answer overlap with GPT-5.5 Pro from 16.8 % to 35.0 % (+27 pp on
  STEM) (+18.2 pp overall); the gist tested DeepSeek V4 Flash, Inkling, Kimi K3 and Qwen3.8-A95B against GPT-5.5 Pro
  prefills only — no Claude prefill condition was run, so the contrast cannot be drawn from this source [61]. Unproven;
  reputational, not technical.
- *License creep.* 27B and 3.5/3.6 are Apache-2.0 [24][28][29], but 3.8-Max weights carry a custom license (attribution
  above 100M MAU or $20M monthly revenue; MaaS / "AI work assistant" businesses over $50M/yr need a separate license)
  [27], and Flash-Next uses `qwen-community-1.0` [25]. Irrelevant at our scale but worth tracking.
- *Privacy / geopolitics.* No CCP/censorship complaints surfaced in the three HN threads sampled [62][63][64]. Model
  Studio's own data-use statement could not be retrieved (see §7 gotchas). The ToS/privacy pages 404 or are JS-only.

## 6. Finance / trading relevance

- **Real-time data.** Built-in web search on Chat Completions (`enable_search`), Responses API (`web_search` tool with
  autonomous multi-search), DashScope (`enable_source` returns `search_info` citations) and the Anthropic-compatible
  endpoint; **OpenAI-compatible mode does not return sources** [16]. Priced $10 per 1,000 calls in Singapore vs $0.57
  elsewhere [16] — non-trivial for a research loop that searches 20× per job ($0.20/job).
- **Market-data connectors.** None first-party. Hosted MCP services exist in Model Studio [2b]; Qwen Code/Qwen-Agent
  consume arbitrary MCP servers, so Alpaca/Tradier/Finnhub MCP servers would be the path. Nothing Qwen-specific.
- **Sentiment sources.** None built in beyond web search.
- **Finance-specific products.** Not found — searched: HF `Qwen-Fin`, `Finix`, Qwen org listing. Only community
  FinGPT LoRA on Qwen-7B [72]. Model Studio lists a `decision-model-preview` [11]: "a structured decision model for
  high-frequency business decisions" that performs "classification, yes-or-no decisions, and scoring in a single forward
  pass, returning probability distributions and confidence"; ap-southeast-1; no pricing, context size or benchmark is
  published on the catalogue page [11]. It is not a finance model, but calibrated probabilities from one forward pass are
  exactly the shape of a signal-gating / triage step (e.g. "is this filing worth a full read?"); untested here. A community
  "Kev" family of decision models built on Qwen3.5 (HN, 2026-09-21) [66] — unexplored.
- **Numeric / table extraction quality.** Still not tested here — no filing or transcript was run through any Qwen
  model. The closest published proxies are on the Qwen3.8-27B card: **OmniDocBench 1.5 = 91.1** (Qwen3.6-27B 89.4,
  Qwen3.7-Plus 91.4, Opus 4.6 Max 86.6) and **CharXiv-RQ 90.2 with code interpreter / 83.7 without** (3.6-27B 85.8 /
  78.4) [24] — document-layout and scientific-chart reasoning, not financial tables; the card publishes no DocVQA,
  ChartQA, TableVQA, OCRBench or MMLongBench-Doc numbers, and the 2.4T-A95B (Max) weights are text-only so have no
  document benchmark at all [24][26]. Two implications for the §7 recommendation: (i) the vision-capable models
  (27B, Flash, Flash-Next) are the ones with any documented document-understanding strength, and their numbers put
  layout/OCR extraction at frontier parity; (ii) the 17-point CharXiv gap between "with CI" and "without" [24] says
  the model is materially better when it can *compute* rather than read — consistent with Ellis's 27.3K → 273,000
  miscount on Qwen3.6-27B [58]. So: extract with strict `json_schema` + tool-computed arithmetic, never model
  arithmetic, and keep the **20-document XBRL-vs-model extraction probe** as the production gate. The
  `qwen3.8-flash` recommendation remains provisional until that probe runs.
  **Probe status and what published evidence exists instead (2026-09-24).** The probe is still deferred: it needs a
  funded Model Studio key (the 1M free quota per model [12] covers ~6 such documents at 165K tokens, so a 20-document
  run on `qwen3.8-flash` costs ≈$0.60 PAYG, on `qwen3.8-max` ≈$8) and the XBRL ground truth from the trading
  project, which is out of this doc's scope. No substitute exists in the literature: an arXiv search for Qwen3.8 with
  XBRL / FinanceBench / financial table extraction returns **0 papers** [99], and the Vals AI Finance Agent
  leaderboard (entry-level-analyst tasks over SEC filings; updated 2026-06-04) lists **no Qwen model** — its top rows
  are Claude Opus 4.7 64.37 %, Claude Sonnet 4.6 63.33 %, Muse Spark 60.59 % [100]. So the recommendation is
  *provisional on purpose*, and the plan should treat it as: **route bulk extraction to `qwen3.8-flash` only behind a
  shadow-mode gate** — run Claude and Qwen on the same document, compare against XBRL facts, promote Qwen per field
  class once its exact-match rate is within 2 pp of Claude's over the 20-document set. Pre-registered acceptance
  numbers so the gate cannot drift: ≥97 % exact match on tagged numeric facts with strict `json_schema`, 0 sign/scale
  errors (the 27.3K → 273,000 class [58]) after tool-computed normalisation, per-document cost ≤$0.05. Until then
  Qwen's trading-research role is summarisation and second-opinion critique, not the numbers of record.
- **Restrictions.** No finance-specific prohibitions found in the docs fetched; the subscription plans' interactive-only
  clause is the binding constraint [18][20]. Qwen3.8-Max weights are text-only and thinking-only [26].
- **Practical fit for Atlas.** Long-context (1M) cheap models (`qwen3.8-flash` at $0.15/$0.47) suit bulk filing/transcript
  digestion and adversarial second opinions; the 27B's IFBench 79.5 [24] and strict `json_schema` on 3.8-Flash/Max [15]
  suit structured extraction. Numeric reliability caveat from Ellis (27.3K → 273,000) [58] argues for tool-computed
  arithmetic, never model arithmetic.

## 7. Integration recipe for our server

**Recommendation.** Integrate Qwen as a *second-opinion and bulk-token tier*, not a replacement for the Claude Max lane.
Two concrete paths, both API-key (the only automation-legal mode):

1. **Hosted PAYG via OpenAI-compatible endpoint** — `qwen3.8-flash` as the default cheap reasoning/classification model,
   `qwen3.8-max` for adversarial review where a non-Anthropic frontier opinion is wanted, `qwen3.8-27b` via OpenRouter
   `:free` (with a one-time $10 top-up for 1,000 req/day) for zero-cost experimentation [47][48]. Metered, but at
   $30/1,000 jobs on flash the owner's "subscriptions over metered" preference is a rounding error.
2. **Qwen Code headless as a sandboxed coding worker** — only if a PAYG key is used (`OPENAI_API_KEY`+`OPENAI_BASE_URL`);
   do **not** buy the Coding/Token Plan for scheduled jobs (ToS) [18][20].

Skip local inference on the M4 16 GB for agent jobs: only Q2 27B (10.7 GB) or Qwen3.5-9B (6.6 GB on Ollama) fit
[37][55]; Q2 loses ~5 pts on Terminal-Bench [55] and throughput would be ≥1 h/job. Keep `qwen3.5:9b` or `qwen3.5:4b`
[37] for offline classification/routing only.

**Minimal sketch — Python (OpenAI SDK, structured output, web search, no new dependency):**

```python
# src/providers/qwen.py  (illustrative)
import os, json
from openai import OpenAI

client = OpenAI(
    api_key=os.environ["DASHSCOPE_API_KEY"],          # PAYG key from Model Studio / QwenCloud (Singapore scope)
    base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
)

def qwen_json(prompt: str, schema: dict, model="qwen3.8-flash", search=False):
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": "Return JSON only."},
                  {"role": "user", "content": prompt}],
        response_format={"type": "json_schema",
                         "json_schema": {"name": "out", "schema": schema, "strict": True}},
        extra_body={"enable_search": search,            # $10/1k calls in SG region
                    "enable_thinking": False},           # opt in per task; thinking is billed as output
        # no max_tokens: Model Studio warns it can truncate JSON mid-output
    )
    return json.loads(resp.choices[0].message.content)
```

**Minimal sketch — Qwen Code headless (coding / code-review worker):**

```bash
export OPENAI_API_KEY="$DASHSCOPE_API_KEY"
export OPENAI_BASE_URL="https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
export OPENAI_MODEL="qwen3.8-flash"           # or qwen3.8-max for review
export QWEN_SANDBOX=sandbox-exec               # macOS Seatbelt; default profile permissive-open
export QWEN_CODE_UNATTENDED_RETRY=1
cd "$WORKSPACE" && qwen -p "$(cat task.md)" \
  --approval-mode auto-edit --output-format json \
  --max-session-turns 60 --max-tool-calls 120 --max-wall-time 30m \
  > out.json; rc=$?     # 0 ok, 53 turn cap, 55 budget cap
jq -r '.[-1].result' out.json; jq '.[-1].stats' out.json   # tokens by model, tool calls by name
```

**Task-class fit here.**
- Research (bulk reading, summarising filings/transcripts, 1M context): **good** on `qwen3.8-flash` / `qwen3.7-plus`.
- Coding (bounded, well-specified changes with tests): **good** via Qwen Code + `qwen3.8-max`; long-horizon autonomous
  builds: keep on Claude (reviewers' consistent warning [58]).
- Code review / adversarial review: **good** — a different training lineage than Claude; use `qwen3.8-max` with thinking.
- Chat (Telegram front door): possible via Qwen Code channels [6], but redundant with the existing bot.
- Classification / routing: **excellent** on `qwen3.8-flash` ($0.03/job) or local `qwen3.5:9b`.
- Trading research: **good for text**; web search costs $10/1k calls in SG [16]; never trust model arithmetic [58].

**Gotchas.**
- Free OAuth tier is gone (2026-04-15) [2]; Coding/Token Plans forbid backends [18][20]; the only clean automation path
  is PAYG (or third-party hosts of the open weights).
- Three base-URL families and six regions with different prices, batch eligibility and web-search prices [10][14][16][94];
  Singapore batch supports only legacy `qwen-*` models [14] — Qwen3.8 batch discount is Beijing-only, and Beijing is
  rejected for this server on data-residency grounds (§3 scoring); do not architect around the 50 % batch price.
- Files API objects and inference logs have **no stated expiry** (files are explicitly permanent until deleted) [92][84];
  any job that uploads must delete on completion. API keys also never expire [93] — rotate by hand.
- Rate-limit planning numbers are Model Studio's bottom-tier TPM (2M max / 2.5M flash, Singapore) [81], not QwenCloud's
  page headlines [21][22].
- Thinking is on by default for many models and is billed as output; Qwen3.8 is unusually verbose [49][54]. Set effort
  low or disable thinking for routing/classification.
- Strict `json_schema` only on 3.7-Plus/Flash/Max and 3.8-Max/Flash; not with image input; do not set `max_tokens` [15].
- Rate limits are per Alibaba account, not per key, and do not scale with spend [13]; Model Studio lists Qwen3.8 limits
  as "Dynamic", so budget for throttling rather than the QwenCloud headline numbers.
- Explicit context cache: 125 % creation surcharge, 5-minute TTL [77] — only worth it for burst re-reads; rely on
  implicit caching for scheduled jobs.
- Remote MCP servers with OAuth need the `127.0.0.1:7777/oauth/callback` listener reachable (or `--oauth-redirect-uri`
  behind a TLS proxy) and a one-time interactive authorisation before the daemon can use them [8].
- Older models 403 on the Anthropic-compatible endpoint once flagged for deprecation; releases are ~6-weekly [17][31].
- Data-use / retention: Model Studio states it "will never use your data for model training" (SOC 2, AES-256 in
  transit; page updated 2026-09-20) but **stores call data for an unstated period** with no deletion/ZDR terms [84];
  the service-terms, data-privacy-and-security and generative-AI-terms pages all 404 [84][87]. Keep Atlas PII and
  credentials out of prompts; see the §3 data-handling matrix.
- **Cross-doc propagation (owed by this doc).** The finding that Coding Plan / Token Plan keys are contractually
  interactive-only [18][20] belongs in `runtimes-aggregators` (Qwen Code rows: only the PAYG/OpenAI-compatible key mode
  is automation-legal; Coding Plan's "supported clients" list of Claude Code/Codex/Cursor [18] is *interactive* support,
  not a backend licence) and in `crosscut-tos` (third-party-serving matrix row: PAYG = permitted, plans = forbidden,
  consumer = unknown). Until those docs are amended, any router table that shows a Qwen "subscription" lane is wrong.
- `--yolo` runs without a sandbox by default [3]; always pair with `QWEN_SANDBOX` on the Mac Mini.

## 8. Verdict

1. Qwen3.8 is the strongest open-weight family today (27B = #1 open in its AA class [50]; Max ≈ top-25 overall [49][53]),
   priced 3–10× below Anthropic/OpenAI list [10][60].
2. The "free CLI tier" is dead and every subscription forbids automation [2][18][20]; for this server Qwen is a
   **metered-API** option, not a subscription one.
3. Cheapest credible hosted reasoning: `qwen3.8-flash` ≈ $0.03 per 165K-token job [10]; frontier-ish second opinion:
   `qwen3.8-max` ≈ $0.39 [10] (the new `qwen3.8-max-prime` SKU doubles that for throughput we do not need [75]).
4. Local on a 16 GB M4 is a toy (Q2 27B or 9B) [55][57]; not an agent-job path.
5. Best uses here: bulk research digestion, classification/routing, adversarial code/thesis review, bounded coding tasks
   under Qwen Code with hard budgets; avoid unsupervised long-horizon builds and model-side arithmetic [58].

Fit scores (1–10): research **7**; coding/agentic **7** (bounded) / 5 (long-horizon); cost efficiency **9**;
automation friendliness **6** (excellent CLI/daemon with JSON stats/OTEL; no concurrency cap and non-expiring keys;
no subscription path; no quota API; retention window unstated and files permanent by default); trading research **6**
(provisional pending the XBRL probe, which has no published proxy — no Qwen row on Vals Finance Agent [100]).

Calibration anchors for the cross-provider scorecard (so this row can be reconciled with the others rather than
re-anchored per doc): *research* 7 = frontier-minus-one quality at 1M context, web search metered at $10/1k calls in
SG; *coding* 7 = SWE-bench Pro 61.7–67.7 vendor-reported, independent arena #22, reviewers warn off long-horizon;
*cost* 9 = $0.03–0.39/165K-token job vs ~$1–3 on Anthropic/OpenAI list; *automation* 6 = headless CLI + daemon +
sandbox + exit codes (would be 8) minus no subscription lane, no programmatic quota, dynamic account-level limits and
unstated retention; *trading* 6 = text research good, no market-data connectors, arithmetic untrusted, extraction
untested. A 10 on any axis means "the best lane in this research set on that axis with no operational caveat".

## 9. Sources

All accessed 2026-09-24.

1. https://github.com/QwenLM/qwen-code — README (install, providers, `-p`, MCP/subagents)
2. https://qwenlm.github.io/qwen-code-docs/en/users/configuration/auth/ — OAuth discontinued 2026-04-15; Coding/Token Plan env vars and endpoints
2b. https://help.aliyun.com/en/document_detail/2880606.html — Model Studio MCP FAQ (hosted MCP, RAM access)
3. https://qwenlm.github.io/qwen-code-docs/en/users/features/headless/ — flags, JSON schema, exit codes, retry env
4. https://qwenlm.github.io/qwen-code-docs/en/users/qwen-serve/ — daemon flags, auth, persistence
5. https://qwenlm.github.io/qwen-code-docs/en/developers/daemon-rest-api-reference/ — REST/SSE contract, channels list
6. https://qwenlm.github.io/qwen-code-docs/en/users/features/channels/telegram/ — Telegram channel setup
7. https://qwenlm.github.io/qwen-code-docs/en/users/features/sandbox/ — Seatbelt/Docker sandboxing
7b. https://qwenlm.github.io/qwen-code-docs/en/ — docs navigation (channels, IDE integrations, GitHub Action)
8. https://qwenlm.github.io/qwen-code-docs/en/users/features/mcp/ — MCP configuration
9. https://github.com/QwenLM/qwen-code/releases — v0.24.4 (2026-09-22), desktop/Chrome extension
10. https://www.alibabacloud.com/help/en/model-studio/model-pricing — per-model prices, batch 50 %, free quota (updated 2026-09-24)
11. https://www.alibabacloud.com/help/en/model-studio/models — current model catalogue (updated 2026-09-24)
12. https://www.alibabacloud.com/help/en/model-studio/new-free-quota — 1M tokens/model, 90 days, Singapore only
13. https://www.alibabacloud.com/help/en/model-studio/rate-limit — RPM/TPM per model, account-level
14. https://www.alibabacloud.com/help/en/model-studio/batch-interfaces-compatible-with-openai — batch limits, regions
15. https://www.alibabacloud.com/help/en/model-studio/json-mode — structured output modes and model support
16. https://www.alibabacloud.com/help/en/model-studio/web-search — web search tool, pricing per 1k calls
17. https://www.alibabacloud.com/help/en/model-studio/claude-code — Anthropic-compatible endpoint (PAYG, Token Plan; updated 2026-09-22)
18. https://www.alibabacloud.com/help/en/model-studio/coding-plan — Pro $50, request caps, interactive-only clause
19. https://www.alibabacloud.com/help/en/model-studio/token-plan-overview — Token Plan tiers and prices
20. https://www.alibabacloud.com/help/en/model-studio/token-plan-personal-overview — credits, dynamic burn, usage policy
21. https://www.qwencloud.com/models/qwen3.8-max-0902 — specs, prices, rate limits, base URL
22. https://www.qwencloud.com/models/qwen3.8-27b — specs, prices, rate limits
23. https://www.qwencloud.com/pricing/token-plan — plan tiers, supported tools, "around 40 % off"
24. https://huggingface.co/Qwen/Qwen3.8-27B — model card, benchmarks, Apache-2.0
25. https://huggingface.co/Qwen/Qwen3.8-Flash-Next — model card, qwen-community-1.0
26. https://huggingface.co/Qwen/Qwen3.8-2.4T-A95B — model card, benchmarks, text-only
27. https://huggingface.co/Qwen/Qwen3.8-2.4T-A95B/blob/main/LICENSE — Qwen3.8-Max License terms
28. https://huggingface.co/Qwen/Qwen3.6-35B-A3B — model card
29. https://huggingface.co/Qwen/Qwen3.5-9B — model card
30. https://huggingface.co/api/models?author=Qwen&sort=downloads&direction=-1&limit=60 — download counts, family list
31. https://github.com/QwenLM/Qwen3.8 — release dates, deployment frameworks
32. https://qwen.ai/blog?id=qwen3.8 (rendered via r.jina.ai) — Qwen3.8-Max launch post, 2026-08-03
33. https://qwen.ai/blog?id=qwen3.8-omni-flash (rendered via r.jina.ai) — Omni-Flash, 2026-09-14
34. https://qwen.ai/ (rendered via r.jina.ai) — "free to use", product features, latest models
35. https://ollama.com/library/qwen3.8 — 27B tags (18 GB)
36. https://ollama.com/library/qwen3.6 — 27B/35B tags
37. https://ollama.com/library/qwen3.5 — 0.8B–397B tags and sizes
38. https://ollama.com/library/qwen3 — legacy Qwen3 tags
39. https://openrouter.ai/qwen — model slug list
40. https://openrouter.ai/api/v1/models/qwen/qwen3.8-27b/endpoints — per-provider prices
41. https://openrouter.ai/api/v1/models/qwen/qwen3.8-max/endpoints — price, params, 1M ctx
42. https://openrouter.ai/api/v1/models/qwen/qwen3.8-flash/endpoints
43. https://openrouter.ai/api/v1/models/qwen/qwen3.7-plus/endpoints — tiered price, snapshot id
44. https://openrouter.ai/api/v1/models/qwen/qwen3.5-397b-a17b/endpoints
45. https://openrouter.ai/api/v1/models/qwen/qwen3-coder/endpoints
46. https://openrouter.ai/api/v1/models/qwen/qwen3-coder:free/endpoints
47. https://openrouter.ai/api/v1/models/qwen/qwen3.8-27b:free/endpoints — ModelRun free endpoint
48. https://openrouter.ai/docs/api-reference/limits — free-model caps
49. https://artificialanalysis.ai/models/qwen3-8-max — index 45, speed, price, verbosity
50. https://artificialanalysis.ai/models/qwen3-8-27b — index 34, #1/142 open
51. https://artificialanalysis.ai/models/qwen3-8-flash-next — index 40
52. https://artificialanalysis.ai/models — overall index leaders
53. https://arena.ai/leaderboard/text — 2026-09-13 leaderboard, Qwen ranks
54. https://simonwillison.net/2026/Aug/16/qwen-38-27b/ — review
55. https://quesma.com/blog/qwen38-27b-quantizations-benchmarked/ — quantization benchmark
56. https://quesma.com/blog/qwen-36-is-awesome/ — Qwen3.6-27B local review
57. https://terminalbytes.com/run-qwen-3-8-27b-locally/ — Mac Studio numbers, RAM guidance
58. https://blog.alexellis.io/local-ai-is-not-opus/ — long-horizon failure modes
59. https://www.xda-developers.com/qwen-3-8-27b-reverse-engineering-job-frontier-model/ — reverse-engineering test
60. https://www.emergingtrajectories.com/lh/frontier-lab-economics/ — economics commentary
61. https://gist.github.com/wsxiaoys/e0286dc6bb624ff5fdf49e7f4c528ba3 — GPT-5.5 Pro prefill experiment
62. https://news.ycombinator.com/item?id=49299605 — HN: Qwen3.8-27B (comments via hn.algolia.com API)
63. https://news.ycombinator.com/item?id=49150470 — HN: Qwen3.8-Max launch
64. https://news.ycombinator.com/item?id=49448210 — HN: Qwen3.8-Flash-Next
65. https://news.ycombinator.com/item?id=49611128 — HN: quantization benchmark thread
66. https://hn.algolia.com/api/v1/search?query=Qwen&tags=story&numericFilters=created_at_i%3E1780000000&hitsPerPage=30 — 2026 story list
67. https://inference-docs.cerebras.ai/models/overview — qwen-3.8-27b ~1850 tok/s
68. https://inference-docs.cerebras.ai/support/rate-limits — free/developer limits
69. https://www.cerebras.ai/pricing (rendered via r.jina.ai) — $0.99/$1.49
70. https://pypi.org/project/dashscope/ — SDK 1.27.7
71. https://github.com/QwenLM/Qwen-Agent — framework, MCP, install
72. https://huggingface.co/api/models?search=Qwen-Fin&limit=30 — no official finance model
73. https://hn.algolia.com/api/v1/search?query=dashscope%20OR%20%22qwen%20api%22%20outage%20OR%20down%20OR%20degraded&tags=comment — 0 hits
74. https://hn.algolia.com/api/v1/search?query=%22Qwen%20Chat%22&tags=story — no pricing stories
75. https://openrouter.ai/api/v1/models/qwen/qwen3.8-max-prime/endpoints — qwen3.8-max-prime $4/$12, cache read $0.50, created 2026-09-23
76. https://huggingface.co/Qwen/Qwen-Drive-1.0-4B — Apache-2.0 driving VLM on Qwen3.5-4B, arXiv 2609.00111
77. https://www.alibabacloud.com/help/en/model-studio/context-cache — explicit cache TTL 5 min, 125 % creation, exception models
78. https://central.sonatype.com/artifact/com.alibaba/dashscope-sdk-java — Java SDK 2.23.1
79. https://www.alibabacloud.com/help/en/model-studio/install-sdk — official SDKs are Python and Java only
80. https://statusgator.com/services/alibaba-cloud — "Alibaba Cloud Model Studio" component; 0 incidents/30 d, 1/90 d (2026-07-28, 3 h 55 min)
81. https://www.alibabacloud.com/help/en/model-studio/quota-management — dynamic rate limiting: spend-tiered TPM, monthly (10th/15th), account+model aggregation, soft limit, console-only Quota management page
82. https://qwenlm.github.io/qwen-code-docs/en/users/features/commands/ — `/stats` (`/usage`), `/stats model|tools|skills|daily|monthly|export` (CSV/JSON)
83. https://qwenlm.github.io/qwen-code-docs/en/developers/development/telemetry/ — OpenTelemetry opt-in, OTLP/file exporters, `logPrompts` default true, env vars
84. https://www.alibabacloud.com/help/en/model-studio/privacy-notice — "Security certifications and privacy" (updated 2026-09-20): never used for training, AES-256, SOC 2, call data stored (no window)
85. https://www.alibabacloud.com/help/en/model-studio/what-is-model-studio — "will never use your data for model training"
86. https://www.alibabacloud.com/help/en/legal/latest/alibaba-cloud-international-website-privacy-policy — updated 2026-09-04; retention "as long as you have an account"; cross-border transfer
87. https://www.alibabacloud.com/help/en/legal/latest/alibaba-cloud-international-website-product-terms-of-service — updated 2026-08-28; no Model Studio / generative-AI clause (model-studio-service-terms and generative-ai-service-terms URLs 404)
88. https://r.jina.ai/https://www.qwencloud.com/legal/privacy — QwenCloud privacy (updated 2026-04-01): collects prompts and Output Data, Singapore storage, silent on training; qwencloud.com/legal/terms 404
89. https://r.jina.ai/https://chat.qwen.ai/terms and https://r.jina.ai/https://chat.qwen.ai/privacy — login shell; in-page ToS/Privacy links resolve to the same shell URL (also tried /legal/terms-of-service, /legal/privacy-policy)
90. https://r.jina.ai/https://qwen.ai/terms and https://r.jina.ai/https://qwen.ai/legal-agreement — marketing homepage, no legal text
91. https://help.aliyun.com/zh/model-studio/privacy-notice — China-site Bailian privacy page: no training, AES-256, "will store data generated during model and application calls", no retention window; Service Agreement link 404
92. https://www.alibabacloud.com/help/en/model-studio/openai-file-interface — Files API (updated 2026-09-11): "Files do not expire", permanent until deleted, 10,000 files / 100 GB, delete endpoint, Singapore + Beijing
93. https://www.alibabacloud.com/help/en/model-studio/get-api-key — (updated 2026-09-11) "API keys do not expire. They remain valid until you manually delete them"; regions Beijing/Singapore/US-Virginia; account-eligibility per region not stated
94. https://www.alibabacloud.com/help/en/model-studio/regions — (updated 2026-09-24) six regions with workspace domains; "cannot be used across regions"; "Your static data always remains in the selected region"
95. https://qwenlm.github.io/qwen-code-docs/en/users/qwen-serve/ — `--max-sessions 32` (503 + Retry-After 5), `--memory-budget-mb` default 50 % of host memory, journal cap 5 %/1024 MB, token handling and loopback exposure
96. https://qwenlm.github.io/qwen-code-docs/en/users/configuration/auth/ — credential search order (`.qwen/.env` → `.env` → `~/.env` → settings.json `env`), plaintext; CI guidance; OAuth cached tokens after 2026-04-15
97. https://qwenlm.github.io/qwen-code-docs/en/users/features/mcp/ — `trust` bypasses confirmations in trusted workspaces; `~/.qwen/mcp-oauth-tokens.json` plaintext 0600, `QWEN_CODE_FORCE_ENCRYPTED_FILE_STORAGE`; auto-refresh; excludeTools precedence
98. https://github.com/QwenLM/qwen-code/blob/main/docs/users/features/channels/telegram.md — privatePolicy allowlist / pairing; `TELEGRAM_BOT_TOKEN` env; no injection or auto-tool guidance
99. http://export.arxiv.org/api/query?search_query=all:%22Qwen3.8%22+AND+%28all:XBRL+OR+all:financial+OR+all:FinanceBench+OR+all:%22table+extraction%22%29 — 0 results (2026-09-24)
100. https://www.vals.ai/benchmarks/finance_agent — Finance Agent leaderboard (updated 2026-06-04): no Qwen row; Opus 4.7 64.37 %, Sonnet 4.6 63.33 %, Muse Spark 60.59 %

## Verification log (2026-09-24)

**Corrections applied: 13** — 3 major (PAYG Anthropic-compatible endpoint documented, not 404; distillation-gist scope —
no Claude prefill condition; `qwen3.8-max-prime` added to lineup) and 10 minor (qwen3-coder-plus rate limits; qwen3.8-max
cache rates and exception status; qwen3.7-plus OpenRouter price = 20 %-off promo, not a conflict; HN quote re-attributed
to NorwegianDude and quoted in full; Quesma Q4_K_M vs BF16 numbers; six Seatbelt profiles via `SEATBELT_PROFILE`; Coding
Plan client list + OpenClaw/Hermes Agent/QwenPaw; Emerging Trajectories dated 2026-07-19 as pre-release; Cerebras free
trial and $5-credit conditions; Beijing batch model list).

**Claims re-verified in this pass (source → finding).**
- context-cache page [77] → explicit TTL 5 min reset on hit; creation 125 %, explicit hit 10 %, implicit hit 20 %;
  qwen3.8-max/-0902/-flash/2.4t-a95b listed as exceptions.
- new-free-quota page [12] → "Free Quota Only" switch (off by default, `AllocationQuota.FreeTierOnly`); dated snapshot and
  undated alias are independent models with separate 1M quotas; 90 days from the later of activation/release/approval.
- coding-plan page [18] → Lite: no new subs 2026-03-20 00:00 UTC+8, no renewals/upgrades from 2026-04-13 18:00 UTC+8;
  client list includes OpenClaw, Hermes Agent, QwenPaw.
- token-plan-overview [19] → Team seats: Standard $20 (list $30), Pro $75 (list $100), Max $200; shared pack $700 =
  625,000 credits; personal tiers unchanged.
- OpenRouter prime endpoint [75] → Alibaba, $4/$12, cache read $0.50, 1M ctx, text+image+video, created 2026-09-23.
- Model Studio models page [11] → `decision-model-preview` description confirmed; no `qwen3.8-max-prime` listed.
- Qwen Code MCP doc [8] → default OAuth redirect `http://localhost:7777/oauth/callback`; `--oauth-redirect-uri` + TLS
  proxy to 127.0.0.1:7777 required off-box.
- HF Qwen-Drive-1.0-4B [76] → Apache-2.0, Qwen3.5-4B base, ~5B params, arXiv 2609.00111 (2026-09).
- Sonatype [78] + install-sdk [79] → Java SDK 2.23.1 official; no official Node/Go DashScope SDK (npm `dashscope-node`
  page returned 403 and is not referenced by Alibaba docs).

**Stale / unverifiable flags left in place (marked "unverified as of 2026-09-24").** §5 monster_truck Flash-Next quote;
§5 dofm "youtuber test cases" quote; §5 HN 2026-08-06 AA-agentic-index story (with the AA rescale caveat: Aug-era 52 vs
today's 34 for 27B); §3 Qwen3.8 RPM/TPM figures (Model Studio says "Dynamic"; numbers are QwenCloud's); §3 batch RPM/TPM
exemption for qwen3.8-*; §1/§4 `qwen3.8-max-prime` price (OpenRouter-only); §4 qwen3.8-flash cached-input 0.016 on Model
Studio (OpenRouter confirms); §1 Omni-Flash date 09-14 vs 09-18; §4 Qwen Studio has no paid tier; §5 XDA hardware noted
as workstation-class (ThinkStation PGX, Q8). Web-search budget was exhausted in the original pass and this pass used
direct fetches only.

**Fact-checker overall quality rating: good.** Not tested in either pass: numeric/table extraction accuracy (flagged in
§6 as a gate before production use).

**Gap-fill pass (2026-09-24, direct fetches only; web-search budget exhausted).** Added: data-use statement located
on the Model Studio privacy-notice page [84][85] (no-training confirmed; retention window still unstated); per-lane
data-handling, third-party-serving, progress-visibility, normalized-reliability and tool-churn subsections in §3;
Telegram-latency rating in §5; OmniDocBench/CharXiv proxies for extraction in §6; calibrated scorecard anchors in §8;
cross-doc propagation note for the interactive-only plan clause in §7. Still 404: model-studio-service-terms,
data-privacy-and-security, billing-overview, bills, monitoring, observability, BSS QueryAccountBill, AA qwen3-8-flash
page, qwencloud.com/legal/terms, chat.qwen.ai legal pages (login-gated).

**Gap-fill pass 2 (2026-09-24, direct fetches only; web-search budget still exhausted).** Resolved: Model Studio
"Dynamic" limits reconciled against QwenCloud headlines with the published spend-tier TPM table (planning number 2M /
2.5M TPM Singapore bottom tier) [13][81]; retention window pinned as far as the vendor allows (inference logs unstated
on both international and China-site pages [84][91]; Files API objects explicitly permanent until deleted [92]; API keys
never expire [93]); Beijing batch scored and rejected on residency (six-region table, in-region static data, PRC
photo-ID / lawful-request clauses) [86][94]; Qwen Studio ToS confirmed unreachable via four more URLs and the lane
excluded rather than left "unknown" [89][90]; XBRL probe kept deferred with a costed spec, pre-registered acceptance
numbers and a shadow-mode gate, after confirming no published proxy exists (arXiv 0 hits, no Qwen row on Vals Finance
Agent) [99][100]. Cross-doc dimensions answered in the new §3 bullet: concurrency (no cap on PAYG; daemon 32 sessions),
credential lifecycle (plaintext env, no TTL, MCP OAuth auto-refresh), progress sink (JSONL file exporter, spend-to-date
not quota), calibration (not applicable to this lane's verdict), injection posture (middle of set; restrictive-proxied
rule), host budget (`--memory-budget-mb` default 8 GB — set explicitly), reviewer independence (evidence points at OpenAI
lineage, Claude-independence unmeasured; test proposed), latency (already measured here; Claude TTFT owed by the claude
doc). Still unverified: whether an international-site account can create a Beijing key; default dynamic tier for new
accounts; Qwen Code per-process RSS.
