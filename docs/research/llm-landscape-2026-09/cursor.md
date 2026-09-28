# Cursor (cloud/background agents API, headless `agent` CLI, multi-model plan; SpaceX-owned since 2026-08-14) — research (as of 2026-09-24)

Method note: this session's web-search budget was exhausted before this task started, so every fact below comes from direct fetches of vendor docs, vendor blog/changelog/status pages, the Cursor forum (Discourse JSON), HN (Algolia API), Wikipedia, and a handful of secondary news/analysis pages. Reddit, Reuters, Bloomberg, BBC, CNBC and openai.com blocked fetches; where a claim rests on one of those, it is routed through a page that quotes it and marked accordingly. "(unverified)" means no primary source was reachable.

## 1. Snapshot

**Company.** Anysphere, Inc. (trade name Cursor), founded 2022 by four MIT students (Truell, Asif, Lunnemark, Sanger); CEO Michael Truell [35]. Revenue ramp: $100M ARR Jan 2025 → $500M Jun 2025 → ~$3B May 2026 [35]; ~$4B ARR cited at acquisition [36][40] (unverified as of 2026-09-24 — [36] gives no ARR figure, only ~80% B2B and NVIDIA 30k WAU; Wikipedia stops at ~$3B, May 2026). Ownership: SpaceX announced a $60B purchase option 2026-04-21, exercised it 2026-06-16 (all-stock), and the deal **closed 2026-08-14**, making Cursor a wholly owned subsidiary of "SpaceXAI" (SpaceX having absorbed xAI earlier in 2026) [35][36][25]. The option carried a $1.5B cash breakup fee plus $8.5B in compute credits [36]. Cursor now co-develops the Grok 4.5/4.6/4.7 line with xAI and trains on Colossus compute [36][28].

**Model lineup available inside Cursor (CLI, cloud agents, SDK, IDE)** — Cursor's models page lists display names and per-token prices; SDK/CLI docs show the wire IDs where they exist [5][17][18][16]:

| Family | Display name (models page) | Wire ID seen in docs | Context in Cursor | Cursor price in/out ($/M) | Notes |
|---|---|---|---|---|---|
| Cursor/xAI | Grok 4.7, Grok 4.7 Fast | `grok-4.7` on xAI API [29]; forum shows `cursor-grok-4.6-high-fast` style internal IDs [46] | 256k (500k at 2x price) [5] | 2 / 6; Fast 4 / 12 [5][28] | Released 2026-09-21 [28]; knowledge cutoff **May 2026**, text+image input [29] |
| Cursor/xAI | Grok 4.6, Grok 4.6 Fast | `grok-4.6` [29] | "Standard" [5] | 2 / 6; Fast 4 / 12 [5] | Released 2026-08-12 [25] |
| Cursor/xAI | Grok 4.5, Grok 4.5 Fast | `grok-4.5` [29] | "Standard" [5] | 2 / 6; Fast 4 / 18 [5] | |
| Cursor | Composer 2.5, Composer 2.5 Fast | `composer-2.5` [17][18]; `composer-2`, aliases `composer-latest`, `composer` [16] | Not stated ("Standard") [5] — Not found — searched: models page, Composer 2.5 blog, AA page (404) | 0.5 / 2.5; Fast 3 / 15 [5][26] | Released 2026-05-18; RL on Moonshot Kimi K2.5 open checkpoint [26][35] |
| Router | Auto | `auto`, `auto-smart` (+ `optimize_for` = `cost` / `balanced` / `intelligence`) [18][47] — **`auto-smart` (Cursor Router) is Teams/Enterprise-only**: the SDK docs say Router "is available on Teams and Enterprise" and that `auto-smart` "is missing or an optimization mode is rejected" when "Router is not available for this API key"; the help pricing page says individual plans (Hobby/Pro/Pro+/Ultra) "will receive this update a few months after launch" (Router launched 2026-07-22) [17][3][59] | per routed model | per routed model | Classifier trained on 600k+ live requests [31] |
| Anthropic | Claude Opus 5.5, Sonnet 5, Opus 4.8, 4.7 Opus, 4.6 Sonnet | `claude-4.6-sonnet-thinking` [16]; forum shows `claude-opus-5-thinking-low` [46] | 1M [5] | Opus 5.5 4 / 20; Sonnet 5 2 / 10; Opus 4.8 5 / 25; 4.6 Sonnet 3 / 15 [5] | Claude Fable 5 and Fable 5.1 are on the models page at **$10 / $50** ("Standard" context, "about 2x the cost of Claude Opus 5"); the page also lists Claude Opus 5 at 5 / 25 (1M), Claude Opus 4.5/4.6/4.7 at 5 / 25, and Claude Opus 4.7 fast mode at 30 / 150 ("limited research preview") [5] |
| OpenAI | GPT-5.6 Sol / Terra / Luna (Luna is on the models page at 0.2 / 1.2, 1M, "smallest GPT-5.6 variant"), GPT-5.5, GPT-5.4, GPT-5.4 Mini, GPT-5-Codex | `gpt-5` in CI docs [11] | 1M [5] | Sol 4 / 20 "promotional through Nov 21, 2026"; Terra 2 / 12; 5.5 5 / 30; 5.4 2.5 / 15 [5] | **Being withdrawn: OpenAI terminates Cursor's access by 2026-11-12** [37] (see §5) |
| Google | Gemini 3.8 Flash, 3.7 Flash, 3.6 Flash (1.5 / 7.5), 3.5 Flash (1.5 / 9), 3.1 Pro, 3 Pro (2 / 12), 3 Flash (0.5 / 3), 2.5 Flash | — | "Standard" [5] | 3.8 Flash 0.75 / 3.5; 3.1 Pro 2 / 12; 2.5 Flash 0.3 / 2.5 [5] | |
| Meta | Muse Spark 1.3 | — | 1M, Max Mode required [5] | 1.25 / 4.25 [5] | |
| Moonshot / Z.ai | Kimi K3, Kimi K2.7 Code; GLM 5.2 | — | 1M, Standard; Standard [5] | 3 / 15, 0.95 / 4; 1.4 / 4.4 [5] | |

Knowledge cutoffs for everything except Grok 4.7: Not found — searched: cursor.com/docs/models, Composer 2.5 blog, docs.x.ai models table (blank for 4.5/4.6).

**Release cadence.** Product ships roughly weekly (changelog: Aug 19 cloud-agent harness, Aug 27 repo-less agents, Sep 2 self-hosted machines, Sep 10 Projects + CursorBench 4.0, Sep 23 Rollouts/Security Review bots) [24]; **Sep 23 blog "Improved token efficiency for longer agent runs"**: system prompt trimmed ~66%, 60% of built-in tool-description tokens moved to lazy/dynamic loading, GPT-5.6 explicit cache breakpoints (cold cache misses −20%), line-number compression (−1.6% cache-read tokens), "reduced token costs for users by 7% without reducing agent quality"; the same learnings are being applied to Grok Bot's harness [60]; first-party models every ~5–6 weeks (Composer 2 Mar 2026 → Composer 2.5 May 18 → Grok 4.6 Aug 12 → Grok 4.7 Sep 21) [25][26][35]. Forum is already asking for Composer 2.6/3.0 [44].

**Positioning.** Cursor is no longer "an IDE": it is a multi-model agent platform (IDE + `agent` CLI + Python/TS SDK + Cloud Agents REST API + Automations + Grok Bot computer-use agents + Origin code hosting + Projects) whose economic engine is a subscription pool that is deliberately cheaper to spend on its own Grok/Composer models than on third-party ones [2][4]. Post-acquisition it is simultaneously the most model-diverse cheap agent plan on the market and the one with the sharpest single-owner concentration risk (SpaceX/xAI), which OpenAI has already acted on [37].

## 2. Interfaces & surfaces

- **Desktop IDE** (macOS/Windows/Linux, VS Code fork) — Cursor 3 shipped 2026-04-02 [58] (unverified as of 2026-09-24 — date taken from the HN story listing for cursor.com/blog/cursor-3, 544 points; the blog post itself was not fetched); **web** (cursor.com/agents) and **iOS** app for cloud agents [6][14]. Grok Bot has desktop (macOS/Windows/Linux) + iPhone apps [21].
- **Browser/OS integration.** Grok Bot runs on a cloud VM with browser, filesystem and terminal, can sign into websites, learns workflows by demonstration and saves them as skills, keeps memory/files/browser sessions across sessions, and runs scheduled routines while your device is offline [21]. VM specs (Debian, 128 GB disk / 16 GB RAM) come only from runtimewire's 2026-08-11 launch coverage [42] (unverified as of 2026-09-24 — cursor.com/docs/grok-bot gives no specs; the numbers may have changed). Self-hosted "Machines" (Sep 2) let cloud agents execute inside your own network with computer-use on Linux and Mac [24]. Built-in agent tools include **Web search**, **Browser** (screenshots/navigation), shell, file read/edit, image generation [23].
- **Voice.** Not found — searched: Grok Bot docs, changelog, agent tools page.
- **CLI.** `agent` binary; install `curl https://cursor.com/install -fsS | bash` (macOS/Linux/WSL), lands in `~/.cursor/bin` [6][11]. Windows native install via PowerShell: `irm 'https://cursor.com/install?win32=true' | iex` [62]. Modes agent/plan/ask; `&`-prefixed message hands a task to a Cloud Agent [6]. Subcommands on the parameters page: `ls`, `resume`, `create-chat`, `models`, `mcp`, `sandbox enable|disable|reset|run`, `worker`, `login`/`logout`, `status`/`whoami`, `about`, `generate-rule`, `update`, `help` [8]. Full flag list in §3.
- **API + SDKs.** Cloud Agents REST API at `https://api.cursor.com/v1/` (public beta) [15]. Official SDKs: **`cursor-sdk` on PyPI (v1.0.32, 2026-09-22, Python ≥3.10)** and **`@cursor/sdk` on npm (Node ≥22.13)**, version-paired since 1.0.24 [19][17][18]. Both run agents **locally** (bundled `cursor-sdk-bridge` binary + ripgrep/sandbox binaries; no IDE/CLI install needed) or in the **cloud** [17][18]. Full REST surface [16][15]: `POST /v1/agents` (create + first run, idempotent), `GET /v1/agents`, `GET /v1/agents/{id}`, `POST /v1/agents/{id}/runs` (follow-up), `GET .../runs`, `GET .../runs/{runId}`, `GET .../runs/{runId}/stream` (SSE), `POST .../runs/{runId}/cancel`, `GET /v1/agents/{id}/usage`, `GET /v1/agents/{id}/artifacts` + `GET .../artifacts/download` ("a temporary 15-minute presigned S3 URL"), `POST .../archive` / `.../unarchive`, `DELETE /v1/agents/{id}`, `GET /v1/me` (key info), `GET /v1/models`, `GET /v1/repositories`; auth is "both Basic and Bearer" with user API keys or service-account keys.
- **OpenAI/Anthropic-compatible endpoints.** None — Cursor exposes agents, not a raw chat-completions proxy. Not found — searched: API overview, SDK docs, models page.
- **MCP.** Supported everywhere: IDE config precedence project→global→nested reused by CLI; CLI has `mcp list/enable/disable/login/list-tools` and `--approve-mcps`; API/SDK accept inline `mcpServers` (http/sse/stdio) per agent [13][15][17].
- **Batch API.** None. Not found — searched: API overview, endpoints. (Cloud agents are idempotent per `agentId` and can be created in bulk, which is the closest analogue [15].)
- **Structured outputs / tool use.** No JSON-schema output mode; structured *event* streams instead (`stream-json` NDJSON in CLI, SSE `status/assistant/tool_call/thinking/result` in API, typed `SDKMessage` in SDK) [9][15][17]. Tool allow/deny lists: CLI permissions JSON, SDK `tools=[...]`/`disallowed_tools=[...]` (local only) [12][17].
- **Computer-use / browser agent.** Grok Bot (cloud VM) and Machines `worker start --computer-use` [21][8][24].
- **Scheduled/automated tasks.** **Automations**: cron or preset schedules, webhooks (private POST endpoint), GitHub/GitLab/Bitbucket events, Slack, Linear, Sentry, PagerDuty; each run is a cloud agent billed as cloud-agent usage [20]. **Projects** (beta, 2026-09-10): a coordinator that keeps months of context, watches Slack/PRs/schedules and delegates to "thousands of subagents" [32][24]. Grok Bot scheduled routines [21].
- **Memory.** Grok Bot persistent memory per named bot [21]; cloud agents are "durable" (workspace + conversation persist across runs; `POST /v1/agents/{id}/runs` for follow-ups) [15]; CLI `--resume`/`--continue`, SDK `Agent.resume("bc-…")` [8][17].
- **Projects/workspaces.** Origin code hosting (early beta, all paid plans; GitHub optional; Vercel/Depot/Buildkite integrations) [33]; cloud agents can start from scratch with no repo [24].
- **Messaging integrations.** Slack (`@cursor …` starts an agent; `@Cursor list my agents`) [22]; GitHub/Bitbucket PR comments and Linear `@cursor` [14]. Telegram / WhatsApp / Discord: Not found — searched: cloud-agent surfaces page, Grok Bot docs, Slack integration page.
- **IDE plugins.** Cursor *is* the IDE; there is no plugin for other editors. Not found — searched: docs index, changelog.

## 3. Headless / server automation fit

**Non-interactive use on macOS/Linux.** Explicitly supported and documented for CI. `agent -p "<prompt>" --output-format json` prints a single result object; `--output-format stream-json` (+ `--stream-partial-output`) emits NDJSON events; `--force`/`--yolo` is required for the agent to actually apply edits/run commands in print mode ("changes are only proposed, not applied" otherwise); `--trust` skips the workspace-trust prompt (headless only); `--approve-mcps` auto-approves MCP servers; `--model <id>`, `--list-models`, `--mode plan|ask`, `--workspace <path>`, `-w/--worktree [name]` (isolated worktree under `~/.cursor/worktrees/<repo>/<name>`), `--sandbox enabled|disabled` [8][9][10]. Exit code is non-zero on failure and no JSON is emitted in that case [9].

**Auth modes.** (a) `agent login` browser OAuth (`NO_OPEN_BROWSER=1` prints the URL for SSH boxes); (b) **`CURSOR_API_KEY` env var or `--api-key`**, keys minted at cursor.com/dashboard/api, documented as "recommended for automation, scripts, or CI environments" [7][11]. The SDK and REST API take the same user API keys or team service-account keys (team Admin keys not accepted by the SDK) [17][15].

**Can a consumer subscription be used programmatically?** Yes, and it is the sanctioned path, not a grey area: the SDK docs state **"SDK runs follow the same pricing, request pools, and Privacy Mode rules as runs from the IDE and Cloud Agents"** [17]; cloud agents "are charged at API pricing for the selected model" with a user-set spend limit [14]; the ToS (last updated 2026-09-03) prohibits scraping, model extraction, probing and unreplicable benchmark publication but contains **no clause restricting scripted/CI/automation use of individual plans** [54]. Contrast: this is the opposite of Anthropic's stance on driving Claude Max through third-party harnesses, which is why Cursor belongs in the cheap-agentic-plan comparison.

**Rate limits and caps.** Plan pool is dollar-denominated at each model's API price (docs: "your model selection affects how quickly your included usage is consumed") but the per-plan amount is **not published** [2][4] — Not found — searched: /pricing, /docs/account/pricing, /help/account-and-billing/pricing, /docs/models-and-pricing. Documented hard limits: `GET /v1/repositories` 1/min and 30/h per user [15]; API `envVars` ≤50, `customSubagents` ≤20, repositories per agent ≤20, `mcpServers` ≤50, images ≤5×15 MB (PNG/JPEG/GIF/WebP) [15]; Grok Bot has a *separate* weekly allowance that "resets weekly" [21]; an individual SuperGrok / SuperGrok Plus / SuperGrok Heavy subscription can be *linked* to enable Grok Bot [21] — whether the two allowances stack is not stated (the earlier "does not stack" claim is unverified as of 2026-09-24). Staff spillover order (2026-08-31): "Grok Bot has its own weekly usage pool on Pro+, but once that's used up it keeps going and spills onto your regular Cursor balance: credits (referral/promo) first, then on-demand if enabled"; Grok Bot picks models server-side (`claude-opus-5-thinking-low`, `cursor-grok-4.6-high-fast` appear in usage even though the user never selected them) [46]. Teams/Enterprise pay a "Cursor Token Rate" of $0.25/M on third-party models on top of API price [2][4]; individual plans do not (per docs wording; unverified as of 2026-09-24 whether it also hits individual on-demand — the docs scope the rate to "Teams and Enterprise plans" [4], but the help page's Auto-mode section says "Third-party models also incur the Cursor Token Rate" with no plan qualifier [3][59]). **Team Admin API** (Team API key, Basic auth — i.e. a Teams/Enterprise team, not an individual key): `GET /teams/filtered-usage-events` returns per-event `tokenUsage` (input/output/cacheWrite/cacheRead) and `chargedCents` with a `conversationId` ("for SDK runs that value is exactly the `agentId`"; "Subagent requests are recorded against their parent's `conversationId`, so filtering on that one id gives you everything, tasks included" — staff 2026-07-28), plus `/teams/daily-usage-data` and `/teams/spend` [63][48]. This is the only complete token accounting; `run.usage` is not.

**Sandboxing.** CLI sandbox (`sandbox enable|disable|reset|run`, `--allow-paths`, `--readonly-paths`, `--blocked-patterns`, `--network` "Enable network access in the sandbox (default: `false`)" — re-verified on the parameters page 2026-09-24) and a permissions file (`~/.cursor/cli-config.json` global, `<project>/.cursor/cli.json` project) with `Shell(cmd)`, `Read(glob)`, `Write(glob)`, `WebFetch(domain)`, `Mcp(server:tool)` allow/deny; deny wins [8][12]. Cloud agents run in isolated VMs; "Machines" pools run in your network [14][24].

**Structured events for orchestration.** CLI `stream-json` events: `system/init` (session_id, model, permissionMode), `user`, `assistant`, `tool_call` (started/completed with args/result), terminal `result` (`duration_ms`, `duration_api_ms`, `session_id`, `request_id`) [9]. SDK: typed `SDKMessage` stream (`system|user|assistant|thinking|tool_call|status|task|usage`) and `Run` with `status ∈ running|finished|error|cancelled|expired`, `duration_ms`, `usage` (input/output/cache_read/cache_write/reasoning tokens) [17]. API: SSE stream + `GET /v1/agents/{id}/usage` with per-run token accounting [15]. Caveat: `run.usage`/`result.usage` **exclude subagent tokens**; only the team Admin API sees them (staff, 2026-07-28) [48].

**Session resume.** CLI `agent ls`, `--resume <chatId>`, `--continue`; SDK `Agent.resume(agent_id)` (local state kept by the bridge, cloud state server-side; MCP/tool restrictions must be re-passed) [8][17]. **Streaming.** Yes on all three surfaces [9][15][17]. Known SDK gotcha: Python SDK has no HTTP/1.1 fallback, so TLS-inspecting proxies produce `"[unknown] [internal] Protocol error"` after 15–20 s; TS SDK has `local.useHttp1ForAgent: true` [47][18].

## 4. Cost

**Consumer/individual plans** (vendor pages disagree on naming — the marketing page shows one "$20 Individual" card while the help/docs pages list Pro/Pro+/Ultra; the docs are the more specific source) [1][2][3][4]:

| Plan | $/mo | Included | Notes |
|---|---|---|---|
| Hobby | $0 | "Limited Agent requests", Composer access, Agent/Chat/Tab on Auto [1][3] | No request number published — Not found — searched: /pricing FAQ, help pricing |
| Start (India only) | ₹649 | Cursor Models pool only; no Other Models pool, no on-demand, no Bugbot, **no Auto, no Automations, no Cursor SDK**; effort level and Fast mode cannot be changed [4] | |
| Pro ("Individual" on /pricing) | $20 | Both pools; "Generous limits for Grok"; frontier models; **Grok Bot access**; MCPs/skills/hooks; **Cloud agents**; Bugbot on usage billing [1][3] | Pool size not published |
| Pro+ | $60 | Same, larger pool [3] | Forum: heavy user "hit my limit with the $60 plan in like 3 days" [49] (unverified as of 2026-09-24 — not found in thread 170673 itself; may sit in the other search-hit threads) |
| Ultra | $200 | Same, largest pool [3][42] | Forum: exhausted "within 20–30 days for heavy users"; Grok Bot allowance "too low even on Ultra" [49][45] (both unverified as of 2026-09-24 — thread 170673, created 2026-09-05, instead contains "blew a third of my API budget in an Ultra account using Fable 5.1 in 2 hours", consistent with Fable 5.1's $10/$50 price [5]) |
| Teams Standard / Premium | $40 / $120 per user | Premium = "5x the Standard limits on Agent"; service-account keys; +$0.25/M Cursor Token Rate on third-party models [3][4][42] | |
| Enterprise | custom | pooled usage, SCIM, PO billing [1] | |

Mechanics: two monthly-resetting pools — **Cursor Models pool** (Grok 4.7/4.6/4.5, Composer 2.5, "significantly more included usage") and **Other Models pool** (charged at the model's API price) [2][4]. After the pool: on-demand "at the same API rates", billed in arrears, with a user-set spend limit [1][2][14]. Legacy Max Mode = API rate +20% [4]. Cursor's own guidance: daily Agent users "typically $60–$100/mo total usage", power users "$200+/mo" [2]. Since 2026-07-31 the self-serve usage page shows tokens, not dollars (see §5) [43].

**Harness overhead is moving.** The 2026-09-23 token-efficiency post claims a ~7% overall token-cost reduction (66% shorter system prompt, 60% of tool-definition tokens loaded lazily, GPT-5.6 cache breakpoints) [60]; the per-job estimates below use raw model prices and do not model harness overhead in either direction, so treat them as ±10%.

**Per-model price** = the Cursor table in §1 (Cursor charges provider list price; GPT-5.4 gets "90% discount on cached input"; xAI API cached input for Grok 4.7 is $0.50–1.00/M) [5][29]. No batch tier exists. Free API tier: none; xAI advertises free Grok 4.7 access via x.ai/build, but that is xAI's surface, not Cursor's [28].

**Monthly cost to run N agent jobs (150k in + 15k out per job, no cache hits, no subagents, no retries):**

| Model | $/job | (b) API/on-demand: 10 jobs | 100 jobs | 1000 jobs | (a) Subscription path (est.) |
|---|---|---|---|---|---|
| Composer 2.5 | $0.1125 | $1.13 | $11.25 | $112.50 | 10 & 100: **$20 Pro** (fits any plausible Cursor-Models pool); 1000: Pro or Pro+ **$20–60** if the pool is ≥$112 at API rate (unverified) |
| Grok 4.7 | $0.39 | $3.90 | $39 | $390 | 10: $20; 100: **$20–60**; 1000: **Ultra $200 + ~$0–190 on-demand** (depends on unpublished pool) |
| Gemini 3.8 Flash | $0.165 | $1.65 | $16.50 | $165 | 10: $20; 100: $20–60; 1000: $60–200 |
| Muse Spark 1.3 | $0.251 | $2.51 | $25.10 | $251 | 10: $20; 100: $60; 1000: ~$250 (Ultra + on-demand) |
| Claude Sonnet 5 | $0.45 | $4.50 | $45 | $450 | 10: $20; 100: $60; 1000: ~$450 |
| Claude Opus 5.5 | $0.90 | $9 | $90 | $900 | 10: $20; 100: ~$90; 1000: ~$900 |

Assumptions: pool ≈ plan price at API rates for third-party models (Cursor's 2025 rule; the current docs no longer state it — (unverified)), more for Cursor Models; individual plans exempt from the $0.25/M Token Rate (unverified as of 2026-09-24, see §3); **no Router/`auto-smart` on individual plans** — the Router A/B savings below are Teams/Enterprise numbers [59]; Teams would add 150k×0.25/M ≈ $0.04/job. At 150k input per job, the 1M-context Anthropic/OpenAI models are overkill; the pool math strongly favours Composer 2.5 / Grok 4.7 for volume, which is exactly the incentive Cursor designed [2][31]. Router's own A/B numbers: Auto Intelligence ≈ premium quality at ~60% lower cost; cost per commit $6.76 (Intelligence) / $4.63 (Balance) vs $12.69 Fable 5 / $7.34 Opus 4.8 (Router blog, 2026-07-22) [31].

## 5. Strengths & weaknesses per reviews

**Benchmarks.**
- CursorBench 4.0 (Cursor's own, 2026-09-10; "ambiguous, multi-file tasks from real Cursor sessions"): Opus 5.5 Max 57.8% ($13.43/task) > Opus 5.5 High 56.0% ($3.97) > Fable 5.1 Max 51.8% ($17.28) > **Grok 4.7 xHigh 46.3% ($6.01)** > Grok 4.7 High 43.9% > Muse Spark 1.3 Max 41.6% ($2.64) > Grok 4.6 xHigh 41.4% > Gemini 3.8 Flash High 39.6% > Sonnet 5 Max 34.1% > **Composer 2.5 27.7% ($0.68)**; GPT-5.6 variants 16.0–41.7% [30]. Cursor's framing of Grok 4.7 as "at the frontier in price-performance" [28] (unverified as of 2026-09-24 — phrase not surfaced by the x.ai announcement fetch; cursor.com/blog/grok-4-7 [27] only says "our most capable model for long-running coding and knowledge work") — plausible on its own benchmark, but it trails Anthropic's top models by ~10 points.
- xAI's Grok 4.7 card: DeepSWE v1.1 71.0%, Terminal-Bench 4.0 **37.6%**, EEBench 64.0%, HealthBench Pro 56.7%, GDPval 1695 Elo [28]. SWE-bench Verified for Grok 4.7 / Composer 2.5: Not found — searched: x.ai announcement, swebench.com (leaderboard not fetchable), Composer 2.5 blog (charts only).
- Artificial Analysis: Grok 4.7 (xhigh) Intelligence Index **46, rank #21/210**, 40.1 tok/s (slow "at the lower end" of reasoning models), 0.92 s TTFT, 500k ctx, very verbose (240M output tokens in eval vs 88M median) [50]. Composer 2.5 page: Not found (404).
- LMArena text (arena.ai): top spots are Claude Fable 5 / Opus 4.6 / Opus 4.7 (1502–1506); Muse Spark 1.3 max #8 (1493); Gemini 3.8 Flash #9; **no Grok 4.7 or Composer entry in the top 15** [51].

**What it is best at (attributed).**
- Cheapest *sanctioned* programmatic access to a multi-vendor model menu: one $20 key drives Claude Opus 5.5 / Sonnet 5, Gemini, Muse Spark, Kimi K3, GLM 5.2, Grok, Composer from CLI/SDK/API [1][5][17]. A single-comment HN thread (3 points, 2026-02-26) cites model choice, speed and "no provider lock-in" as the CLI's edge over Claude Code (melecas) [57] — weak signal.
- Agent-ops plumbing: durable agents, follow-up runs, SSE streams, artifacts via presigned S3, idempotent create, inline MCP, custom subagents, cron/webhook Automations, self-hosted pools — more orchestration surface than any lab-native CLI [15][20][24].
- Router quality/cost: Cursor's production A/B claims ~60% cost cut at near-premium quality [31].
- Enterprise credibility: SOC 2 Type II, ISO 27001/42001, AIUC-1 [55]; ~80% of revenue B2B; NVIDIA 30k WAU [36].

**Weak at / controversies (attributed).**
- **OpenAI cut-off.** On 2026-08-28 OpenAI told SpaceX it will terminate Cursor's model access by **2026-11-12** and withhold new releases (incl. "Astra") meanwhile, saying "We cannot be confident that SpaceX will use our technology within our terms of service"; Truell says OpenAI models are ~5% of traffic (devops.com notes the figure "was widely dismissed as implausible on social media") [37][39]. HN's pragmatic read (ralusek, chr15m): little practical impact, but "circling of the wagons" and open speculation that Anthropic could follow [39]. **Anthropic's position:** no primary statement found either way — nothing on anthropic.com/news between Aug 14 and Sep 24 mentions Cursor, SpaceX or xAI [64], and the Cursor blog is silent; one HN commenter (ChannelFence) asserts "Anthropic already said they're definitely still in", linking an X post by Tom Brown [39][66] that could not be fetched, and CNBC's 2026-08-29 piece ("Will it be Anthropic or X AI...") was 403 on fetch — so the continuity claim is (unverified as of 2026-09-24) in both directions. Cursor's data-use page does still list Anthropic (with SpaceXAI, OpenAI, Meta) as a ZDR provider [61]. The superml.dev analysis argues Cursor's multi-model routing "has an expiration date" and cites Ramp AI Index spend data showing Cursor's share of AI-coding-tool users falling 41% (Jun 2025) → 26% (May 2026); the piece is dated 2026-06-18, i.e. pre-closing and pre-OpenAI-cutoff [41].
- **Owner risk.** HN's SpaceX-deal thread (1,703 comments) is dominated by Musk-aversion, data-custody worries and valuation mockery; heavy users (senordevnyc) said they would leave [40]. Reuters reported Russian-speaking criminals used "SpaceX's Cursor AI tool" to hack seven companies (2026-08-27) [53] (unverified as of 2026-09-24 — confirmed only as an HN-listed headline, 10 points / 0 comments; article body not verified).
- **Grok quality and reliability.** Forum on Grok 4.7: "sidegrade", "burns almost twice as many tokens as Grok 4.6", inappropriate guideline refusals on doc questions; positive: adequate daily driver [45]. Status page (incidents API): **~31 incidents in the last 30 days (Aug 25–Sep 24); the feed returns 50 going back to Aug 5**, roughly half Grok-model/Grok Bot degradations (Grok Bot 6.5 h on Sep 16; 5.75 h + 3 h on Sep 18; Grok 4.7 on Sep 23) but also Anthropic and OpenAI model error spikes (Sep 3), Composer 2.5 errors and "Fable 5 unavailable" (Aug 19), and a 4.75 h Cloud Agents/Automations/Review Agents degradation on Sep 17 [34][65]. Forum's most-replied thread this month: "Some of the bots became unresponsive" (186 replies) [44].
- **Pricing transparency.** Jul 2025 Pro-plan metering backlash and rollback [35] (unverified as of 2026-09-24 — not re-verified against Wikipedia in this pass); 2026-07-31 removal of dollar amounts from the usage page/CSV for self-serve plans ("You've become too greedy") [43]; Grok Bot silently spilling into paid on-demand and draining the Cursor pool [46]; "$60 plan in 3 days" [49] (unverified as of 2026-09-24, see §4).
- **Provenance.** Composer 2 was revealed by users, not Cursor, to be Kimi K2.5 + RL (Mar 2026) [35][58]; Composer 2.5 openly says so [26].
- **Security posture.** Mindgard's Windows `git.exe` auto-execution 0-day was reported 2025-12-15, unpatched and un-responded-to through full disclosure 2026-07-14 [52]; Dec 2025 supply-chain pwn of X/Vercel/Cursor/Discord; Jan 2026 "browser experiment implied success without evidence" post (724 HN points) [58].
- **Churn narrative.** "Top 0.01% Cursor user → Claude Code 2.0" (Jan 2026, 230 comments, mixed reception) [56]; forum: "Claude Code offers better value for episodic use; Cursor better for continuous development" [49].

## 6. Finance / trading relevance

- **No finance product, data feed or market connector.** Not found — searched: docs index, agent tools, Automations, Grok Bot docs, blog May–Sep 2026.
- **Real-time access exists only as generic tools:** the agent's Web search tool and Browser tool [23], Grok Bot's cloud browser with persistent logins [21], and whatever MCP servers you attach (`mcpServers` on API/SDK, http/sse/stdio) [15][17] — e.g. an Alpaca/Tradier/FRED MCP is the practical route. Grok-in-Cursor does **not** expose xAI's X/Live-Search tooling (unverified as of 2026-09-24; not mentioned on the models page, agent-tools page, Grok Bot docs, or the Grok 4.7 blog [5][23][21][27] — requests are built by Cursor's backend, which does "final prompt building" even with API keys [61], so xAI-side tools would have to be wired by Cursor).
- **Market-event ingress:** Automations' webhook trigger ("Webhook triggers create a private HTTP endpoint for your automation. POST to the endpoint to start a run", with a generated URL + API key) is a usable ingress for price/news alerts from our own monitors → agent run [20]; the docs do not say whether the POST body is exposed to the agent prompt (unverified as of 2026-09-24), so pass context via the prompt/repo instead.
- **Egress for broker/data APIs:** cloud-agent VMs have outbound internet (admins can "restrict outbound domains"; secrets are injected at agent start; private networks reachable via Tailscale), and self-hosted Machines run inside your own network [14][24] — so a read-only broker/FRED call from a cloud agent is technically possible but puts API keys on a SpaceX-operated VM; local SDK/CLI mode keeps egress on our Mac Mini.
- **Sentiment sources:** none native; X access would be via Grok Bot's browser, which is subject to "sites can still block automation, expire a session, or require a human step" [21].
- **Restrictions:** ToS bars scraping/harvesting data from *the Service* (not from third-party sites via the agent) [54]; Privacy Mode "we will not train on your data" is available on free and Pro [55] the data-use page (linked from /security) says that with Privacy Mode on, "Cursor maintains zero data retention (ZDR) agreements with all providers" and lists **SpaceXAI, OpenAI, Anthropic, Meta** as the referenced providers, with the caveats that providers "run risk classifiers" and may store abuse-flagged prompts, that "Non-ZDR models will be designated as such or require an admin to opt-in", and that all requests pass through Cursor's backend for "final prompt building" even with API keys [61]; there is no xAI-specific post-acquisition data-flow term beyond xAI being one ZDR provider among four. The Admin API also lists an Enterprise-only Grok Bot "local egress routing" setting [63].
- Fit: usable for *research/coding on the finance codebase* (Atlas) and for cheap adversarial reviewers; not for market data, and Grok Bot's browser logins into a brokerage would violate the server's no-live-order-path rule.

## 7. Integration recipe for our server

**Recommended path:** one **Pro ($20) key**, the **`cursor-sdk` Python package** as an in-process runtime (local mode, cwd = a workspace clone), falling back to the `agent` CLI subprocess for worktree isolation, and **Cloud Agents only for GitHub-hosted project builds** where a VM + PR is wanted. Reasons: subscription pool is explicitly consumable by SDK/CLI [17]; Python SDK matches our Python 3.12 runner; local mode needs no IDE and ships its own bridge binary [17]; typed usage per run for cost ledgers [17].

```bash
# one-time, on the Mac Mini
curl https://cursor.com/install -fsS | bash            # -> ~/.cursor/bin/agent   [6][11]
pip install cursor-sdk                                # v1.0.32, Py>=3.10        [19]
export CURSOR_API_KEY=crsr_...                        # dashboard/api key        [7]
agent --list-models                                   # confirm IDs for the routing table [8]
```

```python
# runner/backends/cursor_backend.py (sketch)
import os
from cursor_sdk import Agent, LocalAgentOptions, ModelSelection, ModelParameterValue

def run_cursor_job(prompt: str, cwd: str, model: str = "composer-2.5", readonly=False):
    sel = (ModelSelection(id="auto-smart",   # WARNING: Router/auto-smart is Teams/Enterprise-only today; on a Pro key this fails with "Router is not available for this API key" — use plain "auto" or a fixed model id (discover via Cursor.models.list()) until individual-plan rollout
                          params=[ModelParameterValue(id="optimize_for", value="cost")])
           if model == "auto" else model)
    opts = dict(model=sel, api_key=os.environ["CURSOR_API_KEY"],
                local=LocalAgentOptions(cwd=cwd), mode="agent")
    if readonly:                       # review / research jobs: no shell, no writes
        opts["tools"] = ["read", "grep", "glob"]        # local-only allowlist [17][18]
    with Agent.create(**opts) as agent:
        run = agent.send(prompt)
        for ev in run.messages():      # stream to audit_log jsonl
            if ev.type == "tool_call":
                yield {"tool": ev.name, "status": ev.status}
        res = run.wait()
        yield {"status": res.status, "result": res.result,
               "usage": vars(res.usage) if res.usage else None,
               "cost": agent.get_usage().cost}          # billed cents [17]
```

```bash
# CLI equivalent for worktree-isolated coding jobs (launchd/runner subprocess)
agent -p --force --trust --approve-mcps \
  --model grok-4.7 -w job-$JOB_ID --workspace /path/to/repo \
  --output-format stream-json --stream-partial-output \
  "Implement the change described in TASK.md; run pytest; do not push." \
  | tee volumes/audit_log/$JOB_ID.cursor.jsonl            # [8][9][10]
# review-only variant: add --mode ask (read-only), drop --force
```

**Task-class fit here.**
- Coding / project delivery: **good** — worktrees, permissions JSON, PR creation via cloud agents; Composer 2.5 for bulk, Grok 4.7 or Opus 5.5 (pool-expensive) for hard tasks [30][31].
- Code review / adversarial review: **good and cheap** — `--mode ask` or SDK read-only tool allowlist; a second-vendor reviewer (Grok/Composer) diversifies against Claude-grading-Claude; Automations can also run review on PR events for hosted projects [12][20].
- Research (web): **fair** — Web tool exists [23] but is a coding-agent web tool, not Perplexity-grade; use Grok Bot only if a persistent browser session is genuinely required.
- Chat / Telegram front-end: **poor** — no Telegram surface, no chat-completions endpoint; wrap the SDK behind our own bot.
- Classification / routing: **poor** — no cheap structured-output API; a whole agent run per classification is wasteful even at Composer prices.
- Trading research: **fair** — only via MCP connectors we supply; no market data, no sentiment feed [23][15].

**Gotchas.** (1) Third-party models drain the pool at API price; keep Claude/Opus usage on our Claude Max path and use Cursor for Grok/Composer/Gemini/Muse. (2) OpenAI IDs vanish by 2026-11-12 — never hard-code `gpt-*` [37]. (3) `run.usage` omits subagent tokens [48]. (4) Grok Bot shares/adjacent-drains the pool with poor warnings — leave it off for server automation [46]. (5) ~31 incidents/30 days, about half Grok-related but with Anthropic/OpenAI/Composer/Fable outages too — add per-model breaker + fallback to Composer 2.5 or Auto [34][65]. (6) Python SDK needs clean HTTP/2 egress (`*.cursor.sh`) [47]. (7) Usage dashboard no longer shows dollars for self-serve (staff: on-demand spend beyond included usage still appears in CSV exports; Enterprise keeps the dollar view); reconcile from `agent.get_usage().cost.charged_cents` (vs `raw_cost_cents`, which is 0 for request-priced usage) [43][17]. (8) Cloud agents need GitHub App access to repos or Origin; repo listing is 1/min [15][33]. (9) Concentration: Cursor + Grok lane are now the *same* owner; do not treat "Grok via Cursor" and "Grok via xAI" as two vendors in the diversity analysis [36]. (10) Router (`auto-smart` + `optimize_for`) is Teams/Enterprise-only and Enterprise admins must enable it; on an individual key use `auto` or fixed IDs from `Cursor.models.list()` [17][59]. (11) Cloud-agent artifact download URLs expire in 15 minutes — fetch immediately after `GET .../artifacts` [16].

## 8. Verdict

1. Cursor is the cheapest legitimately scriptable multi-model agent plan available: $20/mo, official Python/TS SDKs and a `-p --output-format stream-json` CLI that explicitly draw from the subscription pool [1][17][9] — minus Router, which individual plans do not get yet [59].
2. Its own models are mid-tier (Grok 4.7 ≈ AA #21, CursorBench 46% vs Opus 5.5 58%; Composer 2.5 28%), so the value is orchestration + cheap volume, not frontier quality [50][30].
3. Vendor concentration is now severe: SpaceX/xAI owns it, OpenAI exits 2026-11-12, Anthropic continuity has no primary statement either way (HN claims Anthropic confirmed it is staying via an unfetched X post; Anthropic's newsroom is silent — unverified as of 2026-09-24), and roughly half of the status page's ~31 incidents in 30 days are Grok-related, with Anthropic/OpenAI/Composer outages making up the rest [37][39][34][64][65].
4. Pool sizes are unpublished and the dollar view was removed, so cost control must be done from SDK usage objects, not the dashboard [2][43].
5. For this server: adopt as a **second-vendor coding/review lane and cheap bulk-agent lane**, never as the primary or the Telegram/chat lane, and keep every Cursor call behind a model-agnostic backend interface.

Fit scores (1–10): research **5** · coding/agentic **7** · cost efficiency **7** (Cursor Models) / **4** (third-party models) · automation friendliness **8** · trading research **3**.

## 9. Sources

All accessed 2026-09-24.

1. https://cursor.com/pricing
2. https://cursor.com/docs/account/pricing
3. https://cursor.com/help/account-and-billing/pricing
4. https://cursor.com/docs/models-and-pricing
5. https://cursor.com/docs/models
6. https://cursor.com/docs/cli/overview
7. https://cursor.com/docs/cli/reference/authentication
8. https://cursor.com/docs/cli/reference/parameters
9. https://cursor.com/docs/cli/reference/output-format
10. https://cursor.com/docs/cli/headless
11. https://cursor.com/docs/cli/github-actions
12. https://cursor.com/docs/cli/reference/permissions
13. https://cursor.com/docs/cli/mcp
14. https://cursor.com/docs/cloud-agent
15. https://cursor.com/docs/cloud-agent/api/overview
16. https://cursor.com/docs/cloud-agent/api/endpoints
17. https://cursor.com/docs/sdk/python
18. https://cursor.com/docs/sdk/typescript
19. https://pypi.org/project/cursor-sdk/
20. https://cursor.com/docs/automations
21. https://cursor.com/docs/grok-bot
22. https://cursor.com/docs/integrations/slack
23. https://cursor.com/docs/agent/tools
24. https://cursor.com/changelog
25. https://cursor.com/blog
26. https://cursor.com/blog/composer-2-5
27. https://cursor.com/blog/grok-4-7
28. https://x.ai/news/grok-4-7
29. https://docs.x.ai/docs/models
30. https://cursor.com/evals (CursorBench 4.0)
31. https://cursor.com/blog/router
32. https://cursor.com/blog/projects
33. https://cursor.com/changelog/origin-code-hosting
34. https://status.cursor.com/
35. https://en.wikipedia.org/wiki/Cursor_(code_editor)
36. https://www.a16z.news/p/cursor-spacexai-fastest-iterating-team
37. https://devops.com/openai-cuts-off-cursors-model-access-after-spacex-acquisition/
38. https://openai.com/index/our-decision-on-cursor-following-its-acquisition-by-spacex/ (403 on fetch; content relayed via [37] and [39])
39. https://news.ycombinator.com/item?id=49486172 (HN thread on OpenAI's decision; via hn.algolia.com API)
40. https://news.ycombinator.com/item?id=48553224 (HN thread on SpaceX buying Cursor; via hn.algolia.com API)
41. https://superml.dev/spacex-cursor-enterprise-agentic-coding-lock-in-risk-2026
42. https://runtimewire.com/article/cursor-spacexai-launch-grok-bot-general-purpose-agents
43. https://forum.cursor.com/t/usage-page-to-token-amount-what/167153
44. https://forum.cursor.com/top?period=monthly
45. https://forum.cursor.com/t/share-your-thoughts-on-grok-4-7/172527 (and forum search.json "grok 4.7 thoughts": threads 172567, 172584, 172595)
46. https://forum.cursor.com/t/grok-bot-draining-cursor-credit-pool/169982 (and forum search.json "grok bot credit pool": threads 171010, 170951, 169679, 169658)
47. https://forum.cursor.com/t/172083 (Cursor SDK "[internal] Protocol error", staff reply 2026-09-18)
48. https://forum.cursor.com/t/166895 (SDK subagent token accounting, staff reply 2026-07-28)
49. https://forum.cursor.com/t/is-cursor-ultra-still-worth-it-compared-to-claude-code/170673 (and forum search.json "ultra worth claude code": threads 148298, 156673, 129414)
50. https://artificialanalysis.ai/models/grok-4-7
51. https://arena.ai/leaderboard/text
52. https://mindgard.ai/blog/cursor-0day-when-full-disclosure-becomes-the-only-protection-left
53. https://www.reuters.com/world/russian-speaking-cybercriminals-used-spacexs-cursor-ai-tool-hack-seven-companies-2026-08-27/ (headline only, via HN listing; article not fetchable)
54. https://cursor.com/terms-of-service (last updated 2026-09-03)
55. https://cursor.com/security
56. https://news.ycombinator.com/item?id=46676554 (HN thread on https://blog.silennai.com/claude-code)
57. https://news.ycombinator.com/item?id=47160338 (HN "Cursor has an agent CLI, and it's better than Claude Code")
58. https://hn.algolia.com/api/v1/search?query=cursor&tags=story (story listing used for Cursor 3, Composer 2 = Kimi K2.5 disclosure, supply-chain attack, browser-experiment post)
59. https://cursor.com/docs/cursor-router ("currently only available on Teams and Enterprise plans"; Enterprise default off)
60. https://cursor.com/blog/improved-token-efficiency (2026-09-23)
61. https://cursor.com/data-use (ZDR providers: SpaceXAI, OpenAI, Anthropic, Meta)
62. https://cursor.com/docs/cli/installation (Windows PowerShell installer)
63. https://cursor.com/docs/account/teams/admin-api (filtered-usage-events, conversationId, tokenUsage, chargedCents)
64. https://www.anthropic.com/news (Aug 14–Sep 24 2026 listing; no Cursor/SpaceX/xAI item)
65. https://status.cursor.com/api/v2/incidents.json (50 incidents back to Aug 5; ~31 in Aug 25–Sep 24)
66. https://x.com/NotTomBrown/status/2093541294027280657 (cited on HN as Anthropic's "still in" statement; not fetchable, unverified)

## Verification log (2026-09-24)

**Corrections applied: 16** — critical 2 (Router/`auto-smart` plan gating in the §1 table and the §7 SDK recipe), major 2 (status-page incident count/composition; Claude Fable 5 / 5.1 / Opus 5 prices on the models page), minor 12 (SDK pricing-parity quote, GPT-5.6 Luna, Gemini 3.x Flash/Pro rows, Kimi K2.7 Code, Start-plan exclusions, Truell 5% caveat, Router blog model names, API limits, Ramp AI Index attribution + date, HN thread weakness, usage-dashboard/`raw_cost_cents` nuance, gotcha (5) wording).

**Claims re-verified against primary sources in this pass:**
- Router availability "on Teams and Enterprise", Enterprise admin enable, `auto-smart` troubleshooting via `Cursor.models.list()`, "same pricing, request pools, and Privacy Mode rules as runs from the IDE and Cloud Agents", `UsageCost.raw_cost_cents` / `charged_cents` — cursor.com/docs/sdk/python [17]; "currently only available on Teams and Enterprise plans" — cursor.com/docs/cursor-router [59]; "Individual plans (Hobby, Pro, Pro+, Ultra) will receive this update a few months after launch" and "Third-party models also incur the Cursor Token Rate" — help pricing page [3].
- Sep 23 token-efficiency post: ~66% system-prompt trim, 60% of tool-description tokens moved to dynamic context, GPT-5.6 cache breakpoints (−20% cold misses), 7% user token-cost reduction, applied to Grok Bot — cursor.com/blog/improved-token-efficiency [60].
- Cloud Agents API surface incl. cancel/archive/unarchive/delete/`GET /v1/me`/artifacts + "temporary 15-minute presigned S3 URL", Basic + Bearer auth — cursor.com/docs/cloud-agent/api/endpoints [16]; limits (envVars 50, subagents 20, repositories 20, MCP servers 50, 5 images × 15 MB PNG/JPEG/GIF/WebP; repositories 1/min, 30/h) — api/overview [15].
- Team Admin API `filtered-usage-events` (`conversationId`, `tokenUsage`, `chargedCents`, Team API key/Basic auth) — cursor.com/docs/account/teams/admin-api [63]; staff confirmation that subagent requests are recorded against the parent `conversationId` (Kevin Neilson, 2026-07-28) — forum 166895 [48].
- Grok Bot spillover order (weekly pool → referral/promo credits → on-demand if enabled) and server-side model picks (`claude-opus-5-thinking-low`, `cursor-grok-4.6-high-fast`) — staff (Mohit, 2026-08-31), forum 169982 [46]; SuperGrok linking, "Usage resets weekly", no VM specs — cursor.com/docs/grok-bot [21].
- Data use: ZDR with all providers under Privacy Mode; providers listed SpaceXAI, OpenAI, Anthropic, Meta; risk-classifier caveat; backend prompt building — cursor.com/data-use [61].
- CLI: Windows PowerShell installer `irm 'https://cursor.com/install?win32=true' | iex` [62]; subcommand list and `--network` "(default: `false`)" — parameters page [8].
- Cloud-agent egress: outbound-domain restriction, secrets injected at start, Tailscale for private networks — cursor.com/docs/cloud-agent [14]; Automations webhook = private POST endpoint with generated URL + API key [20].
- Anthropic newsroom Aug 14–Sep 24: no Cursor/SpaceX/xAI item [64]; HN 49486172 comment (ChannelFence) citing an X post by Tom Brown [39][66].

**Stale / unverifiable flags left in place (marked "(unverified as of 2026-09-24)"):** ~$4B ARR at acquisition; Anthropic continuity (no primary statement in either direction; X post unfetched; CNBC 403); forum quotes "$60 plan in 3 days", "within 20–30 days", "too low even on Ultra" (not in thread 170673 itself); Grok Bot / SuperGrok allowance stacking; Grok Bot VM specs (runtimewire only); Grok 4.7 "at the frontier in price-performance" phrasing; Reuters 2026-08-27 hack story (headline only); Jul 2025 metering backlash (not re-checked); individual-plan exemption from the $0.25/M Cursor Token Rate; Cursor 3 ship date (HN listing only); Grok X/Live Search not exposed via Cursor; webhook payload exposure to the agent. Still Not found: per-plan pool sizes, Hobby request count, Composer 2.5 context/cutoff, SWE-bench Verified for Grok 4.7/Composer 2.5.

**Fact-checker overall quality rating: acceptable.** Corrections change the §7 recipe (no `auto-smart` on a Pro key), widen the reliability picture in §5/§8 (not only Grok), and add Fable 5/5.1 pricing to the model table; no verdict-level conclusion reversed, but verdict 3 now records both sides of the Anthropic question rather than a bare "question mark".
