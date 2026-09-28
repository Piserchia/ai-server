# DeepSeek — research (as of 2026-09-24)

Scope: DeepSeek as a candidate model provider for the assistant server (Mac Mini M4 16 GB, Claude Agent SDK on a Claude Max subscription, Python 3.12, Telegram + web dashboard, Atlas paper-trading loops). All prices USD per 1M tokens unless stated. Bracketed numbers cite section 9.

## 1. Snapshot

**Company.** Hangzhou DeepSeek Artificial Intelligence Co., Ltd., founded 2023-07-17 in Hangzhou by Liang Wenfeng as a spin-out of the quant hedge fund High-Flyer; ~160 employees (2025); PRC governing law on every policy document [17][19][22]. Series A of ~US$7B at a US$52B post-money valuation (May 2026); IPO prep for a possible 2027 listing; Aug 2026 reporting says the lab is now "too large and capital-intensive to remain simply a side project of the quant fund" (unverified as of 2026-09-24; CNBC returns 403) [22][45].

**Current lineup (official API, 2026-09-24)** [1][2][3][5][6]:

| Model ID | Family | Params (total / active) | Context | Max output | Modalities | Thinking | Notes |
|---|---|---|---|---|---|---|---|
| `deepseek-flash` | DeepSeek-V4.1-Flash (2026-09-10 per DeepSeek's release note; Wikipedia dates it 2026-09-09 US time) | 552B backbone (HF lists 763B total = 552B backbone + 196B Engram conditional-memory parameters + DeepSeek-ViT vision encoder) / 8B prefill, 16B decode | 1M | 384K (393,216) | text + image in, text out | yes (`none/low/high/max`, default high) | Current recommended model; Responses API + Anthropic API |
| `deepseek-v4-pro` | DeepSeek-V4-Pro-0813 (preview 2026-04-24, GA 2026-08-13) | 1.6T / 49B | 1M | 384K | text only | yes (`low/high/max`) | DeepSeek said it was "phasing out V4-Pro" on 09-10, then the changelog the same day reversed: service continues after 09-14 "with the billing method remaining unchanged" [2][3]. `V4.1-Pro` announced as forthcoming, no date. |
| `deepseek-v4-flash`, `deepseek-v4-flash-vision-exp` | legacy V4-Flash (284B/13B) | — | — | — | — | Retired 2026-09-10; names temporarily route to V4.1-Flash at Flash prices [1][2] |
| `deepseek-chat`, `deepseek-reasoner` | V3.x aliases | — | — | — | — | Fully retired after 2026-07-24 15:59 UTC [4] |

Open weights (MIT for DeepSeek's own models: DeepSeek-V4-Pro, DeepSeek-V4.1-Flash, V4-Flash, V3.2, R1; the R1 distills (1.5B–70B) are MIT-released but inherit their base-model licenses — Apache 2.0 for Qwen-based, Llama license for Llama-based) [5][6][33]. Older specialist models still on Hugging Face/Ollama: DeepSeek-OCR (3B), Prover-V2, Coder-V2 [34].

**Knowledge cutoffs.** Not published by DeepSeek for any model. Third-party resellers advertise "April 2026" for V4-Pro; that figure appears nowhere in DeepSeek's docs and looks inferred from the release date (unverified) [5][6].

**R1 / R2.** R1 (Jan 2025, updated R1-0528) is superseded; R2 was never released — the reasoning-capable 2026 line is V4 with a thinking toggle (Reuters/The Information reported a failed Huawei-Ascend training run and CEO dissatisfaction as causes of the delay — unverified as of 2026-09-24; the Wikipedia article does not mention R2) [22][search: "DeepSeek R2 release"].

**Release cadence 2025-26.** V3.2-Exp 2025-09-29 → V3.2 2025-12-01 (both dates unverified as of 2026-09-24) → V4 preview 2026-04-24 → V4-Flash-0731 → V4-Pro-0813 → V4-Flash-Vision-Exp 2026-08-21 → V4.1-Flash 2026-09-10. Roughly one meaningful model event every 4–8 weeks, with model IDs retired on short notice (weeks) [2][4].

**Positioning.** The cheapest near-frontier open-weight lab. V4.1-Flash is a 1M-context multimodal MoE that DeepSeek and third parties (Fireworks, Artificial Analysis) place at or above V4-Pro on agentic coding at 1/5–1/15 the cost of Western frontier models, priced $0.15–0.30 in / $0.60–1.20 out [1][25][31]. The trade-offs are structural, not technical: PRC data residency and law, a thin consumer surface (free chat only, no subscription), a first-party agent harness that is still a developer preview (DeepSeek Harness / `dsh`, MIT, released 2026-08-13 — `npx @deepseek-ai/dsh`, Python SDK `deepseek-harness-sdk`, JSONL session logs with resume/fork/replay, plugin-based sandboxes/scheduling; breaking changes expected), and a status-page history of capacity incidents [17][18][21].

## 2. Interfaces & surfaces

| Surface | Status (2026-09-24) | Detail / source |
|---|---|---|
| Consumer web/mobile chat | Free, no paid tier | chat.deepseek.com, iOS/Android; web capped at 500 msgs/hour; file/image upload; a search service and file-upload service are separate status-page components (so web search exists) [20][23]. No DeepSeek Plus/Pro/Team plan of any kind [51]. |
| Desktop app | Not first-party | Only community Electron wrappers (e.g. doxdk/deepseek-desktop) — Not found: an official macOS client (searched: "DeepSeek app desktop macOS Windows client"). |
| Browser / OS integrations | Not found | searched: "DeepSeek app desktop macOS Windows client release features MCP memory". |
| Voice | Not found as a feature; the privacy policy lists "voice" among collected inputs, which suggests voice input in the mobile app (unverified) [18]. |
| CLI / agentic coding tool | **DeepSeek Harness (`dsh`)** — first-party, open-source (MIT), developer preview since 2026-08-13: CLI + local web UI (`npx @deepseek-ai/dsh web`, http://127.0.0.1:3080), Standard/Code/Minimal/Creator modes, append-only JSONL session log (resumable/forkable/replayable), Python SDK `deepseek-harness-sdk` (`DeepSeekHarness(provider="deepseek-official", model=...).run(task, session_id=...)`), everything-is-a-plugin (models, tools, skills, sessions, sandboxes, scheduling, UI). Rapid iteration / breaking changes expected; DeepSeek endpoints only. Official guides also cover **Claude Code**, **Codex**, OpenCode, OpenClaw, Hermes, Reasonix, WorkBuddy/CodeBuddy, Qoder and GitHub Copilot [9][10][53][54]. |
| API + SDKs | REST at `https://api.deepseek.com` (also `/v1`). No DeepSeek-branded API SDK — docs use the OpenAI Python/Node SDKs and the Anthropic SDK [8][15]; the only first-party Python package is `deepseek-harness-sdk`, which drives the `dsh` harness rather than the raw API [55]. |
| OpenAI-compatible | Chat Completions (full), **Responses API** (`deepseek-flash` only; stateless — `previous_response_id`, `store`, `conversation` silently ignored) [13][15]. |
| Anthropic-compatible | `https://api.deepseek.com/anthropic` (Messages API). Opus names → `deepseek-v4-pro`; Sonnet/Haiku/unknown → `deepseek-flash`. Supported: system, tools, tool_choice (`auto`/`any`/`tool` supported, `disable_parallel_tool_use` ignored), streaming, images, thinking (budget_tokens ignored; effort via `output_config`), `metadata.user_id` (maps to DeepSeek's per-user concurrency/KV-cache isolation — useful for per-job isolation in the runner). Ignored: `service_tier`, `anthropic-beta` headers (except `files-api-2025-04-14` for the Files API), `container`, `mcp_servers`, `top_k`, documents, code-execution results [8]. |
| MCP | Server-side MCP connector not supported (ignored); client-side MCP works through whatever harness you run (Claude Code / Codex) [8]. No MCP in the consumer app (Not found). |
| Web search (API) | **None executed server-side.** The `/anthropic` compatibility table lists `server_tool_use` and `web_search_tool_result` only as *accepted message content blocks* (so a transcript that already contains Anthropic search results can be replayed), not as a tool DeepSeek runs; and Claude Code itself withholds its WebSearch tool from any session whose `ANTHROPIC_BASE_URL` is a third-party host or gateway, so the DeepSeek Claude Code guide's "Web Search tool" cost caveat is moot in practice [8][9][61][62]. Bring your own search (Finnhub/Tavily/Brave as a function tool or MCP server). |
| Batch API | Not found in official docs (searched pricing page, changelog, API reference). Third-party hosts offer batch (Together lists batch tables at the same rates; SiliconFlow advertises batch discounts) [32]. |
| Structured outputs | `response_format: {"type":"json_object"}` only; you must say "json" in the prompt (and give an example of the desired shape) or the model "may generate an unending stream of whitespace" (unverified as of 2026-09-24 — the current json_mode page only warns of occasional empty content and of `max_tokens` truncation; the whitespace wording was not found). No `json_schema` / strict mode documented [14][15]. |
| Tool use | Function tools, `tool_choice` none/auto/required/named — but `required` and named are **not** supported in thinking mode. Tool calls work inside thinking; with `tools` present you must echo `reasoning_content` back every turn [11][15]. Parallel tool calls: not documented. |
| Vision | `deepseek-flash`: JPEG/PNG/GIF/WebP, ≤32 MiB per image, ≤600 images/request, ≤1024 tokens per image, user messages only [16]. |
| Computer-use / browser agent | Not found (searched: "DeepSeek computer use browser agent"). |
| Scheduled / automated tasks | Not found in the consumer product; DeepSeek Harness lists "scheduling" and "loops" among its swappable plugins (developer preview, not evaluated) [53]. |
| Memory / projects / workspaces | Not found in the consumer product [23]. |
| Messaging integrations (Telegram/Slack/WhatsApp/Discord) | Not found first-party. The official OpenClaw guide (supports `deepseek-v4-pro` / `deepseek-v4-flash`) ships Feishu and WeChat channels only — no Telegram/Slack/Discord [59]; otherwise community bots via API key. |
| IDE plugins | None first-party; any OpenAI/Anthropic-compatible extension (Cline, Continue, Codex VS Code extension). The Codex `~/.codex/config.toml` provider block (`base_url = "https://api.deepseek.com/"`, `wire_api = "responses"`, `experimental_bearer_token = <key>`) is shared by Codex CLI, the ChatGPT desktop app and the VS Code extension, so one config covers all three [10]. |
| Files API | Exists (`file_id` inputs for images in Responses API; 64 MiB per image via Files API) [13][16]. |
| Logprobs | `logprobs` + `top_logprobs` (0–20) supported [15]. |

## 3. Headless / server automation fit

- **Auth modes.** API key only (`sk-...` from platform.deepseek.com, prepaid balance). There is no OAuth device login and no subscription sign-in because there is no subscription. The consumer chat account cannot be used programmatically: the Terms of Use forbid "using any robots, spiders, or other automatic setups, setting mirrors" and account lending [17]. So the owner's "subscription over metered API" preference has no DeepSeek-native path; the only subscription-shaped route is a reseller (Ollama Cloud Pro, $20/mo with $60 credits) [36].
- **Credential lifecycle on a headless box (cross-doc matrix row).** The DeepSeek key is a static `sk-` string: no TTL, no refresh, no device flow; it dies only when revoked on platform.deepseek.com or when the prepaid balance hits zero (HTTP **402** "run out of balance" — the first thing that fails, and it fails per request, not at login) [71]. On the Claude Code lane it is delivered as `ANTHROPIC_AUTH_TOKEN`, which ranks **second** in Claude Code's credential precedence (cloud-provider vars > `ANTHROPIC_AUTH_TOKEN` > `ANTHROPIC_API_KEY` > `apiKeyHelper` > `CLAUDE_CODE_OAUTH_TOKEN` > profiles > `/login` OAuth), so it silently out-ranks the Max login in that subprocess — and, per Anthropic's gateway page, setting `ANTHROPIC_BASE_URL` *alone* does **not** replace the subscription: a saved claude.ai login would remain the active credential and its usage limits would apply, so the recipe must always pair base URL + token [72][73]. Storage: nothing touches the macOS Keychain or `~/.claude/.credentials.json` (those hold the OAuth login); the key lives wherever the runner keeps the lane's env (`.env` → subprocess env; never in `~/.claude/settings.json`, which every Max session also reads). Expiry alarms: Claude Code's "login expires in 3 days" warning is *not* shown when `ANTHROPIC_AUTH_TOKEN` supplies the credential [72], so the only alarm is ours — poll `GET /user/balance` daily and alert on `is_available=false` or `total_balance` below a floor [63]. `--bare` mode (announced future default for `-p`) reads `ANTHROPIC_AUTH_TOKEN` but not `CLAUDE_CODE_OAUTH_TOKEN`, so this lane survives the flip while the Max lane needs care [69][72]. Side effects of the token being active: Remote Control, voice dictation, claude.ai connectors and `/schedule` are unavailable in that subprocess, and `/fast` reports fast mode disabled unless `CLAUDE_CODE_SKIP_FAST_MODE_ORG_CHECK=1` (irrelevant: DeepSeek has no fast tier) [73].
- **Concurrency / fan-out on this lane (cross-doc row).** Unlike every subscription lane, there is no per-seat or per-session cap: the scheduler may run as many parallel `claude -p` subprocesses as the **account** concurrency allows — 2,500 in-flight requests on `deepseek-flash`, 500 on `deepseek-v4-pro`, raised on request at no charge [7]. The binding limits are therefore local (RAM per subprocess, below) and the prepaid balance, not the vendor. Set `metadata.user_id=<job_id>` per job so each job gets its own concurrency/KV-cache bucket [7][8]. For comparison, the Claude Max lane's parallel-session ceiling is still undocumented — Anthropic's Pro/Max and usage-limit help articles state only that limits are shared across Claude and Claude Code, with no number of simultaneous instances [74][75]; that gap belongs to claude.md, not here.
- **Host resource budget (measured on this Mac Mini, 2026-09-24).** The DeepSeek lane adds **no daemon**: no Ollama, no proxy, no collector — only one Claude Code subprocess per parallel job. `ps` on the 16 GB host today shows four `claude` processes at 91 / 184 / 237 / 488 MB RSS (the 488 MB one is a long-running interactive session; the SDK-spawned `--output-format stream-json` worker is 130 MB), so budget ~150–250 MB RSS per headless DeepSeek job and ~500 MB for a long one; ten parallel jobs ≈ 2–3 GB, which fits beside Postgres/Redis. If the lane is instead run through the OpenAI SDK for classification calls, the footprint is the Python process itself.
- **Non-interactive use on macOS/Linux.** Trivial: plain HTTPS. The official Claude Code and Codex recipes are env-var/config-file driven and work in `claude -p` / `codex exec` headless modes [9][10]. The Codex provider block is one file shared by Codex CLI, the ChatGPT desktop app and the VS Code extension, which matters if a Codex lane is ever added [10]. No sandboxing is provided by DeepSeek's API; sandboxing is whatever the harness does.
- **DeepSeek Harness (`dsh`) as a headless runner — candidate, not recommended yet.** First-party, MIT, developer preview since 2026-08-13 (747-point HN launch). What fits our runner: a Python SDK (`deepseek-harness-sdk`, 0.1.5rc1 on 2026-09-10, Python ≥3.10, bundles the runtime binary, drives `dsh` over newline-delimited JSON-RPC on stdio, `DeepSeekHarness(dsh_home=..., cwd=..., provider="deepseek-official", model=..., reasoning_effort="max").run(task, session_id=...)` returning `result.final_response`); an append-only JSONL session log that records system prompts, reasoning, tool calls/results, subagent scheduling and every context injection, and can be resumed, forked and replayed; a Minimal mode (bash + file edit only) that is what DeepSeek benchmarks with; sandbox, scheduling and loop plugins; a local web UI (`npx @deepseek-ai/dsh web`, 127.0.0.1:3080) with a Trajectory view. What does not fit: the README states in capitals that "THERE WILL BE COMPATIBILITY-BREAKING CHANGES", the SDK is a release candidate, it targets DeepSeek endpoints only (no provider fallback), and it has no equivalent of our hook/guard/MCP configuration. Verdict: track it (it is the harness DeepSeek tunes V4.1-Flash against, cf. the Terminal-Bench 2.1 spread in section 5), but do not build a lane on it until it leaves preview [53][54][55].
- **Rate limits / caps.** Account-level concurrency: 2,500 in-flight requests for `deepseek-flash`, 500 for `deepseek-v4-pro`; no documented TPM/RPM caps; over-limit → HTTP 429; more concurrency on request at no charge. Optional `user_id` (≤512 chars, `[a-zA-Z0-9-_]+`) gives per-user concurrency, KV-cache and safety isolation [7]. Server keeps connections alive with blank lines / `: keep-alive` SSE comments; if inference has not *started* within 10 minutes the server closes the connection — under load you can wait minutes, which matters for job timeouts [7]. Overload returns 503 "server busy".
- **Streaming and orchestration output.** SSE on Chat Completions and Responses (`response.output_text.delta`, `response.reasoning_text.delta`, `response.completed`, `response.failed`, with sequence numbers); `stream_options.include_usage` puts usage on the final chunk; `usage.prompt_tokens_details.{cached_tokens,prompt_cache_hit_tokens,prompt_cache_miss_tokens}` and `completion_tokens_details.reasoning_tokens` are returned for cost accounting [13][15]. Thinking is exposed as `reasoning_content` [11].
- **Session resume.** None server-side (Responses API is stateless). Resume is the harness's job (Claude Code `--resume`, Codex sessions), and Claude Code's transcript state is local, so it works unchanged with the DeepSeek backend [9][13].
- **Caching.** Automatic disk KV-cache for all users, no code changes, best-effort, evicted "within a few hours to a few days"; cache-hit input is billed at $0.003 (Flash) / $0.022 (Pro) off-peak [1][12].
- **Quota / balance introspection.** `GET https://api.deepseek.com/user/balance` (Bearer key) returns `is_available` and `balance_infos[{currency: CNY|USD, total_balance, granted_balance, topped_up_balance}]` — a prepaid balance, not a 5-hour/weekly window, so the dashboard can show "dollars left" and alert on `is_available=false` but there is no rate-window to display [63]. Per-request accounting comes from `usage.prompt_tokens_details.{prompt_cache_hit_tokens,prompt_cache_miss_tokens}` + `completion_tokens_details.reasoning_tokens` (Chat/Responses) or the Anthropic-shaped `usage` block on `/anthropic` [13][15]. No usage dashboard API, no OTEL export, no `/usage`-style CLI; DeepSeek Harness has no telemetry endpoint documented [53].
- **Interactive latency (Telegram fit).** Artificial Analysis (2026-09-24): V4.1-Flash TTFT 0.92 s, 232 tok/s, 11.7 s end-to-end for a 500-token answer at `max` effort; V4-Pro TTFT 1.61 s, 78 tok/s, 64 s end-to-end [25]. With thinking off, Flash is comfortably inside a Telegram round trip (sub-second first token, ~2–3 s for a 500-token reply); Pro at max effort is not chat-grade. Under load the 10-minute "inference not started" window means TTFT can balloon to minutes — stream and show typing indicators, never block a chat handler on DeepSeek without a timeout [7].
- **Model churn risk.** IDs are retired on 2–8 week notice (`deepseek-chat` gone 07-24, `deepseek-v4-flash` gone 09-10, V4-Pro nearly routed away 09-14) — pin nothing without an alias layer and watch the changelog [2][3][4].
- **Payments (re-checked 2026-09-24, still only partially verified).** Prepaid top-up; the ToS defers the method list to "the information displayed on our product pages and the platform website", and `platform.deepseek.com/top_up` returns 403 unauthenticated, so the authoritative list needs a logged-in look [19]. Best available evidence, in date order: GitHub issue deepseek-ai/DeepSeek-V3#347 (Feb 2025, closed) — "PayPal only", user's card declined inside PayPal although it works at Anthropic/OpenAI; issue #1399 (2026-06-06, open) — reporter states the platform accepts "credit cards, PayPal, Alipay, WeChat Pay" and asks for crypto; issue #1617 (2026-09-01, open) — a Southeast-Asia user still asking for the best way to get access [76][77][78]. Net: the "PayPal-only for overseas cards" line in [47] describes the 2025 state; by mid-2026 a direct card option appears to exist but has not been confirmed on the top-up page itself. HN comment search for "deepseek api paypal top up" returns zero hits, so PayPal friction is not a live HN complaint. Refunds are lump-sum minus handling fees, partial refunds unsupported [19]. Low-friction alternatives with card billing remain OpenRouter (passthrough price) and Ollama Cloud [26][36].

## 4. Cost

**Consumer plans.** Exactly one: **Free** — web + iOS/Android, all models, 500 messages/hour on web, no quota tiers, no Plus/Pro/Team/coding plan [23][51]. There is nothing to subscribe to.

**Official API prices (per 1M tokens, USD)** [1]:

| Model | Input cache hit | Input cache miss | Output | Context / max out |
|---|---|---|---|---|
| `deepseek-flash` off-peak | $0.003 | $0.15 | $0.60 | 1M / 384K |
| `deepseek-flash` peak | $0.006 | $0.30 | $1.20 | 1M / 384K |
| `deepseek-v4-pro` off-peak | $0.022 | $0.66 | $1.98 | 1M / 384K |
| `deepseek-v4-pro` peak | $0.044 | $1.32 | $3.96 | 1M / 384K |

Peak = 01:00–04:00 and 06:00–10:00 UTC, Mon–Fri excluding Chinese public holidays; every other hour and all weekends are off-peak (50% of peak). In US Pacific terms peak is 18:00–21:00 and 23:00–03:00 Sun–Thu night during PDT (17:00–20:00 and 22:00–02:00 once PST resumes in November; DeepSeek defines the window in UTC) [1]. Images bill as ≤1,024 tokens each [16]. Batch: none first-party.

**Free tier / credits.** No standing free API tier. Third-party guides report a one-time ~5M-token sign-up grant valid 30 days, no card required (unverified as of 2026-09-24; not on DeepSeek's docs) [46]. OpenRouter `:free` variants: none observed for V4.x on 2026-09-24 in the endpoints listing [26]; OpenRouter free models are capped at 20 req/min and 50 req/day (1,000/day after $10 lifetime credit purchase) [28].

**Third-party hosting (V4.1-Flash, $/1M in / out / cache-read)** [26][29][30][32][36]:

| Host | Input | Output | Cache read | Note |
|---|---|---|---|---|
| DeepSeek via OpenRouter | $0.15 | $0.60 | $0.003 | 99.998% 30-min uptime; 393K max out |
| DeepInfra (Standard) | $0.14 | $0.42 | $0.004 | FP8, 131K max out; Priority tier 1.5× ($0.21 / $0.63 / $0.0063), Flex tier 0.8× ($0.112 / $0.336 / $0.0034) — Flex is the cheapest reputable FP8 route for non-urgent batch work [58] |
| Fireworks | $0.22 | $0.66 | $0.007 | rising to $0.30 / $1.20 / $0.006 on 2026-10-01 |
| Together | $0.30 | $1.20 | $0.006 | Together's own page shows V4.1 Flash at $0.30/$1.20 (an older V4-Flash-0731 tag is $0.14/$0.28) |
| Ollama Cloud | $0.30 peak / $0.15 off-peak in | — | — | `deepseek-v4.1-flash:cloud`; Free tier = 1 concurrent request, starter credits, pay-as-you-go credits unlock all cloud models, no service fee; Pro plan $20/mo incl. $60 credits (3 concurrent), Max $100/mo incl. $300 (10 concurrent); unused credits do not roll over [36] |
| OpenRouter cheapest (Morph / DekaLLM) | $0.047 / $0.04 | $0.19 / $1.00 | — | unknown quantization; treat as unverified quality |

V4-Pro-0813 on OpenRouter: DeepSeek itself $0.66 / $1.98 / $0.022; most Western hosts (Together, Fireworks, DigitalOcean, CoreWeave) $1.32 / $3.96; Baidu $0.389 / $1.168 [27]. Note: a Sept search snippet claiming "V4.1 Flash costs $0.30–1.20 sits *between* old Flash and Pro" is consistent with these tables — V4.1-Flash is 2× V4-Flash-0731's price and ~1/4–1/2 of Pro's.

**Monthly cost estimate.** Assumptions: 150k input + 15k output tokens per job; single-shot, 0% cache hits (worst case); prices as of 2026-09-24 [1].

| Jobs / month | (a) Subscription | (b) `deepseek-flash` off-peak | (b) `deepseek-flash` peak | (b) `deepseek-v4-pro` off-peak | (b) `deepseek-v4-pro` peak |
|---|---|---|---|---|---|
| 10 | none exists; Ollama Cloud Pro $20 (credits cover ~950–1,900 flash-jobs) | $0.32 | $0.63 | $1.29 | $2.57 |
| 100 | $20 | $3.15 | $6.30 | $12.87 | $25.74 |
| 1,000 | $20 (Pro credits ≈ $60; enough at off-peak, marginal at peak) | $31.50 | $63.00 | $128.70 | $257.40 |

Per-job: flash $0.0315 off-peak / $0.063 peak; pro $0.129 / $0.257. **Cache-hit sensitivity (to make this table comparable with the other landscape docs, which assume 0 %, 60–90 %, 70 % or 80 % hits):** at 70 % of the 150k input served from cache, a flash job is $0.0158 off-peak / $0.0316 peak (pro $0.0674 / $0.135); at 90 %, $0.0113 / $0.0226 (pro $0.0497 / $0.0994) — i.e. the 1,000-job row becomes $11–16/month on flash, not $31.50. The real calibration numbers (jobs/month, tokens/job and cache-hit share from `volumes/audit_log/`, plus the owner's Max tier and seats) were deliberately not read in this pass and are still owed by the cross-doc calibration pass; nothing in the DeepSeek verdict flips on them because there is no subscription to compare against, only the per-job metered figure above. **Caveat for agentic jobs:** a multi-turn agent re-sends its context every turn; Fireworks measured 36.9M input tokens per DeepSWE task (174:1 in/out) at $0.43/task on V4.1-Flash [31]. With DeepSeek's automatic cache, repeated prefixes bill at $0.003, so a 30-turn job with 150k live context costs roughly $0.05–0.10 (flash, off-peak) rather than $1+; without cache hits (e.g. a host with no prefix caching) multiply the table by 10–20×. Real-world confirmation: Enclave.ai's V4.1-Flash pentest run (2,349 Bash commands over ~2h38m inside Grafana/Jenkins/Nextcloud copies) consumed 268.3M input tokens, of which 266.2M were cached, plus ~2M output, for $5.14 total ($4.65 for accepted runs) — at uncached rates the same input would have cost ~$40–80 [56]. Also assume 1.5–3× output-token inflation from thinking tokens at `high`/`max` effort — `reasoning_tokens` are billed as output [15].

## 5. Strengths & weaknesses per reviews

**Benchmarks (DeepSeek's own card, max effort; Terminal-Bench numbers are DeepSeek-run)** [5][6]:

| Benchmark | V4.1-Flash | V4-Pro | Opus-5.0 | GPT-5.6 Sol | Kimi K3 | GLM-5.3 |
|---|---|---|---|---|---|---|
| GPQA Diamond | 90.9 | 92.4 | 93.4 | 94.1 | 92.9 | 88.1 |
| HLE (no tools) | 36.8 | 42.7† | 56.3 | 44.5 | 43.5 | 42.0† |
| HLE w/ tools | 63.9 | 60.0 | 63.6 | — | 59.8 | 62.5 |
| Terminal-Bench 2.1 | 90.6 | 87.9 | 89.1 | 88.8 | 88.3 | 88.2 |
| Terminal-Bench 4.0 | 31.2 | 12.4 | 51.8 | 39.9 | 12.6 | 37.9 |
| DeepSWE v1.1 (resolved) | 74.2 | 62.7 | 74.0 | 73.0 | 67.5 | 66.9 |
| ProgramBench | 20.3 | 15.5 | 37.0 | 23.0 | 17.5 | 19.0 |
| NL2Repo-Bench | 64.0 | 61.5 | 75.3 | 56.8 | 58.0 | 58.0 |
| CyberGym | 88.1 | 83.3 | — | 84.5 | 80.0 | 84.5 |
| Codeforces rating | 3471 | 3348 | — | — | — | — |
| MMLU-Pro (base, 5-shot) | 74.1 | 73.5 | — | — | — | — |

V4-Pro's older card: SWE-bench Verified 80.6, LiveCodeBench 93.5, Terminal-Bench 2.0 67.9, MMLU-Pro 87.5 (instruct, max) [5]. Harness sensitivity is large and DeepSeek publishes it: V4.1-Flash on DeepSWE scores 74.2 under mini-SWE-agent but 69.8 under Claude Code and 65.6 under Codex; Terminal-Bench 2.1 ranges 84.1 (Codex) to 90.6 (DSH Minimal — DSH is DeepSeek's own Harness; the card's table also lists OpenCode, Pi, mini-SWE, DSH Standard and DSH PTC) [6].

**Independent measurements.**
- Artificial Analysis: V4.1-Flash (max) Intelligence Index 39 — highest in the DeepSeek family — at 232 tok/s; V4-Pro-0813 (max) 36, 66 tok/s, TTFT 1.69 s, rank 8 of 113 comparable open-weight models, but flagged as verbose (160M output tokens across the suite vs 140M median) [24][25]. (The April V4-Pro preview scored 45/44 on the then-current index version — unverified as of 2026-09-24; index versions are not comparable across months.)
- Fireworks (2026-09-14): V4.1-Flash 74.34% DeepSWE at $0.43/task vs GPT-6-Astra 74.12% at $6.52; Terminal-Bench 2.1 86.5% vs 87.5% (12× cheaper); HLE 34.5% vs 50.4% [31].
- ARC Prize (verified): V4-Flash-0731 61.4% ARC-AGI-2 at $0.04/task (max effort), 89.0% ARC-AGI-1 at $0.02/task [41].
- Simon Willison on V4 (Apr 2026): "almost on the frontier" — DeepSeek's own report says it trails frontier by ~3–6 months; the story is price (V4-Flash at $0.14 undercut GPT-5.4 Nano at $0.20; "V4-Pro was half of Claude Sonnet 4.6" and "incremental rather than breakthrough" — both unverified as of 2026-09-24, the re-fetch confirmed only the "almost on the frontier", Nano-price and 3–6-month-lag statements) [40].
- LMArena: Not found — a specific V4.1-Flash text-arena Elo (searched: "lmarena leaderboard DeepSeek V4.1 Flash text arena score September 2026"); a third-party mirror puts V4-Flash-0731 first on the coding arena sub-board (unverified).

**Community sentiment.**
- HN on V4.1-Flash (Enclave.ai "best hacking model", 2026-09-16) [38]: *pimeys* runs Rust/design/evals agents at "$0.15–0.30 per task" versus "$3–15" for competitors and says "DeepSeek absolutely wins" against Gemini 3.8, Kimi K3 and Opus 5 for his loads; *TuxSH* found GLM-5.3 better for hard reverse-engineering ($22 for more findings vs $2 for fewer); *habosa* says DeepSeek "gets stuck in loops or tell[s] me nonsense"; several note the harness matters more than the model (unverified as of 2026-09-24 — the only oh-my-pi comment found, *tired_star_nrg*, compares DS 4.1 Flash favourably to GLM-5.3 *inside* oh-my-pi; a separate commenter says Claude Code's TUI harness "does not work well with Deepseek, but Opencode is surprisingly good").
- HN on V4-Pro-0813 [39]: consensus that it is a cheap **execution engine, not a planner** — *coredog64*: "I can't trust it to write its own plans from a spec, but if I give it a detailed execution plan written by Opus, it's fast and cheap"; *freakynit*: "What benchmarks say, vs what I've been observing are different. They are good till the project is simple" (exact wording unverified as of 2026-09-24; the thread fetch returned a paraphrase); *simjnd* stays on Flash because it "has been crushing everything I ever needed it to do." A telling anecdote: "Deepseek 4 pro: cost $0.12 — has bug. Grok 4.6: cost $1.41 — no bug" (*jklmnopqrstuvw*).
- Reddit: not fetchable from this environment (r/LocalLLaMA, r/DeepSeek search blocked); search snippets describe active enthusiasm and API-credit stockpiling around V4 (weak evidence).

**Best at:** price/performance for agentic coding and terminal work; long context (1M default); throughput (Flash ~232 tok/s); open weights with MIT license and unusually detailed tech reports (praised on HN vs "70% safety" Western system cards) [6][25][38].
**Weak at:** hard planning/novel-repo work (ProgramBench 20 vs Opus 37, NL2Repo 64 vs 75, Terminal-Bench 4.0 31 vs 52); HLE-style deep knowledge without tools; occasional loops/empty JSON output; verbosity at max effort [6][14][24].

**Reliability record.** Official status page (Jun–Sep 2026): V4 Pro API 99.89%, V4.1 Flash API 99.66%, Chat 99.64–99.82%, Search 99.90%, File Upload 100% [20]. **Normalized 30-day window (2026-08-24 → 2026-09-24, StatusGator as the one cross-vendor source):** 7 events — Sep 2 (29 min warning + 5 min down), Sep 15 (15 min), Sep 20 (15 min), Sep 23 (50 + 20 + 5 min) — ≈2 h 19 min of degraded time, 1 hard outage; the official page shows *zero* incidents for the same 30 days, which is the acknowledgement gap StatusGator grades "C" (avg 30–120 min delay, most events "never acknowledged") [20][21]. Priority/SLA tiers: none from DeepSeek (`service_tier` is ignored on `/anthropic`); the only paid-priority route is DeepInfra Priority (1.5×, no numeric SLA) [8][58]. StatusGator: >165 outages since Jan 2025 (~2.4/month per IsDown), a 3h49m warning on 2026-08-04, a cluster of 5–49 min warnings through Aug/Sep, and a "C" fairness grade — DeepSeek acknowledges incidents 30–120 min late [21]. Major incidents: 2025-01-27 "large-scale malicious attack" + registration freeze; 2025-01-29 exposed ClickHouse DB with >1M chat logs/API keys; 2026-02-28 degraded API+web; 2026-05-08 web/API unavailable [21][23].

**Controversies.** PRC-aligned content moderation (Tiananmen, Taiwan) in hosted models; OpenAI distillation allegations (unproven); South Korea found user data sent to ByteDance (Feb 2025); CrowdStrike (Sep 2025) reported less-secure code generated for groups disfavored by Beijing; Italy, Australia, Taiwan, South Korea (temporarily), Czech Republic, Netherlands and ≥17 US states (count unverified as of 2026-09-24 — the introl list names Texas, New York, Virginia and Tennessee explicitly) plus US Navy/NASA/Commerce banned the app on government devices; the No DeepSeek on Government Devices Act (H.R.1121) and the bipartisan No Adversarial AI Act are pending; no US ban on open-weight models as of mid-2026 (unverified as of 2026-09-24) [22][23][42][43][44].

## 6. Finance / trading relevance

- **Pedigree, not product.** DeepSeek was incubated by High-Flyer, an AI quant fund, but DeepSeek states it is not used for the fund's trading and sells no finance product [22][45]. There are no DeepSeek finance models, connectors, or datasets.
- **Real-time data.** The API has no built-in web search or market-data tool. **Resolved 2026-09-24:** the DeepSeek Claude Code guide's line that "if the model determines that your question requires a web search, it will invoke the Web Search tool … additional model token costs will be incurred" [9] cannot apply to our lane, because Claude Code's own tools reference states WebSearch is *not available* in "sessions using a third-party base URL or LLM gateway" (only Anthropic API, Claude Platform on AWS, Agent Platform ≥ Claude 4, Foundry-on-Anthropic) [61][62]; and the `/anthropic` compatibility table marks `server_tool_use` / `web_search_tool_result` "Supported" only in the *message fields* section, i.e. as content blocks DeepSeek accepts on input, with no tool of type `web_search_*` in its tools section [8]. The two earlier "Supported" reads and the fact-checker's "ignored" were both looking at the wrong thing: block acceptance ≠ server-side execution. Residual uncertainty: **the probe was attempted on 2026-09-24 but could not be run authenticated** — no `DEEPSEEK_API_KEY` exists in this session's environment; the unauthenticated call (`x-api-key: sk-invalid`) returned HTTP 401 `authentication_error` in 0.36 s (request_id 237bb0f6-…), which shows the `/anthropic/v1/messages` route is live and that authentication is checked *before* tool-schema validation, so the question is not answerable without a funded key. It stays the lane's first-run gate. The one-line probe is `curl https://api.deepseek.com/anthropic/v1/messages -H "x-api-key: $DEEPSEEK_API_KEY" -d '{"model":"deepseek-flash","max_tokens":256,"tools":[{"type":"web_search_20250305","name":"web_search"}],"messages":[{"role":"user","content":"What is today'"'"'s SPY close?"}]}'` — a `server_tool_use` block in the reply would overturn this; a 400 or a plain text answer confirms it. The consumer app has a search service [20]. For Atlas, all market data must come from our own tools (Alpaca/Tradier/Finnhub) passed as function tools — which DeepSeek handles well (tool use in thinking mode) [11].
- **Sentiment sources.** None first-party. Vision input on `deepseek-flash` can read chart screenshots and PDFs-as-images (≤1,024 tokens per image, 600 per request) cheaply [16].
- **Fit for Atlas loops.** Strong for bulk research drafting, adversarial review of theses, classification of filings/news, and backtest-code generation at ~$0.03–0.10 per job; weak as a sole planner for multi-step research (HN consensus) [39]. Cheap enough to run N-of-M ensemble critiques.
- **Restrictions.** Open Platform ToS: outputs in medical/legal/financial domains are not professional advice; PRC law governs; inputs may be stored in China — do not send broker credentials, account numbers, or position-level PII [18][19]. The server's "no live order path" rule is unaffected since DeepSeek never gets execution tools.
- **Regulatory optics.** If Atlas ever serves anyone in a government-restricted context, DeepSeek-derived research may be disallowed; irrelevant for a single-tenant personal system today [42].

## 7. Integration recipe for our server

**Recommended path: Anthropic-compatible endpoint driven by the Claude Code CLI / Agent SDK, with a DeepSeek API key in prepaid mode; Flash by default, Pro only for adversarial second opinions.** Rationale: zero new SDK, reuse of every existing hook/guard/MCP config, $0.03–0.10 per job, and the same JSON event stream the runner already parses. Second path: OpenAI SDK against Chat Completions for classification/routing calls where you want raw usage data and no harness. Considered and deferred: **DeepSeek Harness (`dsh`)** via its Python SDK — it is the harness DeepSeek benchmarks with and its JSONL session log would slot into our audit-log model, but it is a developer preview with announced breaking changes, an RC-grade SDK and no provider fallback (see section 3); re-evaluate when it ships a stable release [53][55]. A Codex lane, if ever added, needs only the shared `config.toml` provider block [10].

Auth/policy note: the Claude Code recipe sets `ANTHROPIC_BASE_URL` and `ANTHROPIC_AUTH_TOKEN` in the *subprocess* environment only. The token is a DeepSeek key, not an Anthropic key, so the "never set ANTHROPIC_API_KEY" rule is honored literally; whether it is honored in spirit (an Anthropic-style env var pointing at a Chinese endpoint) is an owner decision. Never export it in the launchd plist that runs the Claude Max sessions — keep it scoped to a `provider=deepseek` runner lane.

Minimal CLI sketch (headless, JSON events, off-peak aware) [9][11]:

```bash
# one-off headless job on DeepSeek V4.1-Flash via Claude Code
env -i PATH="$PATH" HOME="$HOME" \
  ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic \
  ANTHROPIC_AUTH_TOKEN="$DEEPSEEK_API_KEY" \
  ANTHROPIC_MODEL='deepseek-flash[1m]' \
  ANTHROPIC_DEFAULT_OPUS_MODEL='deepseek-v4-pro' \
  ANTHROPIC_DEFAULT_SONNET_MODEL='deepseek-flash[1m]' \
  ANTHROPIC_DEFAULT_HAIKU_MODEL='deepseek-flash' \
  CLAUDE_CODE_SUBAGENT_MODEL='deepseek-flash' \
  CLAUDE_CODE_EFFORT_LEVEL=high \   # official recipe uses max and maps ANTHROPIC_DEFAULT_OPUS_MODEL=deepseek-flash[1m]; v4-pro-for-opus and effort=high are our deviations
  CLAUDE_CODE_AUTO_COMPACT_WINDOW=786432 \
  claude -p "$PROMPT" --output-format stream-json --max-turns 40 \
        --allowedTools "Read,Grep,Glob,Bash(git *)" --permission-mode acceptEdits
```

Python sketch for routing/classification (OpenAI SDK, no harness) [12][15]:

```python
from openai import OpenAI
client = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com")
r = client.chat.completions.create(
    model="deepseek-flash",
    messages=[{"role":"system","content":"Classify the job. Reply as json: {\"lane\": ...}"},
              {"role":"user","content":job_text}],
    response_format={"type":"json_object"},
    extra_body={"thinking": {"type": "disabled"}},   # non-thinking: 8K default max_tokens, temperature allowed
    max_tokens=512,
)
u = r.usage.prompt_tokens_details  # cached_tokens / prompt_cache_hit_tokens / prompt_cache_miss_tokens -> audit log
```

Agent-SDK path: the Python `claude_agent_sdk` spawns the same CLI, so pass the env dict above via `ClaudeAgentOptions(env=...)` and keep `model="deepseek-flash"`. **Usage plumbing (resolved structurally 2026-09-24, not yet exercised live):** the SDK's message parser builds `ResultMessage(usage=data.get("usage"), total_cost_usd=data.get("total_cost_usd"), model_usage=data.get("modelUsage"))` — a verbatim pass-through of the CLI's `result` JSON, which in turn accumulates the Anthropic-format `usage` block of each Messages response [64][65]. So `ResultMessage.usage` will carry exactly what DeepSeek's `/anthropic` endpoint returns in that block (DeepSeek documents no Anthropic-format usage schema, so expect `input_tokens`/`output_tokens` and treat `cache_read_input_tokens`/`cache_creation_input_tokens` as present-if-mapped; the DeepSeek-native `prompt_cache_hit_tokens` names will *not* appear — those live only on Chat/Responses) [8][13][15]. Two consequences: (1) `total_cost_usd` is a **client-side estimate from Anthropic's bundled price table** and prices `deepseek-flash` as an unknown model (`costBasis: "unknown"`) — wrong by construction; supply a `modelPricing` table — but note Anthropic's costs page says Claude Code honours `modelPricing` only from *managed* settings and ignores it in user/project/local settings and in `--settings` [80], so in practice compute cost in the runner from `model_usage` token counts [65]; (2) `usage` excludes subagent tokens while `model_usage` includes them — bill from `model_usage` [65]. First run of the lane must assert `model_usage["deepseek-flash"].inputTokens > 0` and log the raw `usage` dict to the audit log before any cost figure is trusted. (Still not exercised as of 2026-09-24: no funded key in this environment; see §6.) **Progress-visibility sink for this lane:** the same subprocess can export OpenTelemetry regardless of provider — `CLAUDE_CODE_ENABLE_TELEMETRY=1`, `OTEL_METRICS_EXPORTER=otlp`, `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317` — emitting `claude_code.token.usage{type=input|output|cacheRead|cacheCreation, model, session.id}`, `claude_code.api_request/api_error{model,status_code}` and `claude_code.tool_result{tool_name,success,duration_ms}` events [79]; Anthropic states the prompt-cache statistics "work on every provider and gateway" because they come from the response's cache token fields [80]. Use the **token** metric, not `claude_code.cost.usage` (priced from Anthropic's table → unknown model). So a common cross-lane event schema for the dashboard can be `{lane, job_id, model, input, output, cache_read, tool_name, status}` fed from OTEL on the Claude Code lanes and from the OpenAI-SDK `usage` object on the raw-API lane; DeepSeek contributes nothing server-side beyond `/user/balance` for "dollars left" [63]. The collector itself (OTLP → Prometheus/Grafana or a small Python OTLP receiver writing to Postgres) is a cross-doc decision; on this 16 GB host the cheapest option is a single Python OTLP/HTTP receiver in the existing FastAPI process rather than a separate collector daemon.

**Data-handling matrix (DeepSeek lanes vs the Claude Max baseline).**

| Lane / auth mode | Training use | Retention | Residency | ZDR | Source |
|---|---|---|---|---|---|
| DeepSeek API key (any endpoint, incl. `/anthropic`) | **Not settled by contract.** Open Platform ToS §4.2 gives *you* rights to inputs/outputs (incl. distillation) but contains no clause on DeepSeek's own use of API inputs for training; the Privacy Policy grants an opt-out for *personal data* only and explicitly excludes data of developers' downstream end users from its scope. Assume "may be used" until a written answer says otherwise. | "As long as necessary … and legal obligations"; no numeric window | Stored in the PRC ("we directly collect, process and store your Personal Data in People's Republic of China"); may be stored "outside the country where you live" | None offered | [18][19] |
| DeepSeek consumer app (not usable by us) | Opt-out toggle for training | same | PRC | None | [17][18] |
| Third-party hosts (DeepInfra/Fireworks/Together/OpenRouter) | Per host; OpenRouter's endpoints JSON exposes no data-policy fields for the DeepSeek providers | per host | US/EU per host | per host | [26][58] |
| **Claude Max — Claude Code / Agent SDK on subscription OAuth (primary lane)** | Consumer terms: trained on **only if** the account's "improve Claude" setting is on (claude.ai → Settings → Data privacy controls); Claude Code sessions are included | 5 years with the toggle on, **30 days with it off**; local transcripts in `~/.claude/projects/` 30 days (`cleanupPeriodDays`) | Anthropic US infrastructure, AES-256 at rest | Not available on Pro/Max (Enterprise-only, separately enabled) | [66] |
| Claude Console API key (fallback lane) | Commercial terms: **not** trained on unless opted into the Development Partner Program | 30 days standard | US; `inference_geo` data-residency pricing ×1.1 when pinned | Qualified accounts only | [66] |

**The unrequested written answer.** The Trading-research score (5) rests on "no commitment until DeepSeek answers in writing", yet nobody has asked. The ToS names the channel: `api-service@deepseek.com` or the logged-in "Contact us" button [19]. Draft to send (owner action, ~5 min): *"For API traffic under the Open Platform Terms (eff. 2026-04-29): (1) Are API inputs/outputs used to train or fine-tune DeepSeek models, and can an account opt out? (2) What is the retention period for API request/response content and where is it stored? (3) Is a zero-data-retention or no-training addendum available for paid accounts?"* Until a reply exists, note that a fetch-summary of the ToS on 2026-09-24 asserted "DeepSeek does not use inputs or outputs for training" — that is the summarizer's inference from §4.2's rights-assignment language, not a clause; the document contains no such sentence, and the doc's "no commitment" reading stands [19]. Score moves to 6–7 only on a written no-training + bounded-retention answer; the PRC-residency discount remains regardless.

Practical rule for the paper-trading lab: proprietary theses, broker identifiers and position-level data go only to lanes with a contractual no-training + ≤30-day retention posture (Claude Max with the training toggle **off**, or Console API key). DeepSeek gets scrubbed, non-attributable subtasks (classification, public-filing summaries, code execution on public repos).

**Prompt-injection / sandbox posture (cross-doc ranking input).** Two layers. *Harness layer* — identical to the Claude Max lane because it is the same Claude Code binary: Seatbelt-based Bash sandbox on macOS with filesystem `denyRead`/`denyWrite` and a network domain allowlist enforced on child processes, `allowUnsandboxedCommands:false` to close the `dangerouslyDisableSandbox` escape hatch, `sandbox.credentials` deny/mask (on macOS a masked credential *file* is blocked rather than substituted), WebFetch results read in an isolated context window, `curl`/`wget` not auto-approved, and hooks/`permissions.deny` all apply unchanged [81][82]. Two caveats: trust verification is disabled under `-p`, and Anthropic "doesn't support routing Claude Code to non-Claude models through any gateway", so any injection-classifier behaviour that depends on the model (auto-mode classifier, context-aware analysis) is on a model Anthropic never tuned it for [73][81]. *Model layer* — no published injection-robustness or agentic-safety evaluation for V4.1-Flash (the card reports capability benchmarks only), and CrowdStrike's 2025 finding of politically-conditioned code quality is the only third-party safety signal [6][23]. Ranking for the server's untrusted inputs (Telegram text, fetched pages, MCP results): DeepSeek-on-Claude-Code sits with the Claude lanes on *containment* (OS sandbox + network allowlist, best in the landscape) and below them on *model-side refusal*; it should therefore run with the sandbox in strict mode, `WebFetch`/MCP tool results treated as data, and no secrets in env (`sandbox.credentials` deny list) — the same posture Codex Seatbelt gets, and strictly better than Perplexity-MCP-auto-run or opencode-bypass lanes.

**Reviewer independence (is a DeepSeek second opinion actually uncorrelated?).** The task table below assumes "different training lineage → uncorrelated errors". Evidence for: the V4.1-Flash card describes post-training as SFT → RL → on-policy distillation from *its own* rollouts over "large-scale automated synthesis of agent tasks and environments", names no external teacher, and the pretraining corpus, architecture (Engram conditional memory, DSA attention) and harness are all DeepSeek's [6]. Evidence against: the 2025 OpenAI distillation allegation (unproven) and the general practice of SFT on frontier-model outputs mean some stylistic and some error correlation with GPT/Claude is likely; kimi/minimax/qwen docs record parallel Anthropic-distillation allegations for their labs [22][23]. Practical reading: DeepSeek is the *most* lineage-independent of the cheap second-opinion lanes (own pretraining run, own RL environments, PRC data mix), so it is the right choice for adversarial review if any of them is — but independence is an empirical property: the server should measure it (disagreement rate and unique-catch rate versus the Claude reviewer over the first ~50 review jobs, logged in the audit log) before weighting its verdicts.

**Third-party-serving permission.** The Open Platform ToS explicitly contemplates serving others: §3.2 makes the developer responsible for "systems, applications, or functions" built on the API and requires "agreements with your end users"; §3.3 requires disclosing personal-information processing rules and obtaining end-user consent before offering a public service; §3.4 requires security, monitoring and incident-handling measures [19]. So the pickem dashboard or a shared project site *may* be served from a DeepSeek API key, subject to those obligations and to PRC law as governing law — the consumer app may not be (no robots/mirrors, no account lending) [17]. Contrast: the Claude Max subscription lane is single-user consumer terms; anything that serves a second person should run on a Console API key (the same rule chatgpt-openai.md states for OpenAI).

**Tool-churn / cost of ownership.** Three independent churn clocks: (1) **model IDs** — four retirements/reroutes in 2026 (`deepseek-chat`/`reasoner` 07-24, `deepseek-v4-flash` 09-10, V4-Pro nearly 09-14), i.e. ~one breaking ID event per 6–8 weeks [2][3][4]; (2) **pricing** — one regime change (peak/off-peak, 08-16) that moved list prices up to 10× intraday [57][60]; (3) **DeepSeek Harness** — 8 GitHub releases between 2026-09-10 and 09-24 (0.1.5-rc.1 → 0.1.7-rc.2), **3 of them flagged breaking** in their notes (0.1.5-rc.1, 0.1.6-alpha.1: adapter moved to Messages protocol, E2B backend removed, sync→async agent init; 0.1.7-rc.1: Messages-API-only adapter, PTC packages renamed, session-history APIs deprecated), plus 7 PyPI SDK releases 08-11 → 09-10 — roughly one breaking change per week [67][68]. The recommended lane (Claude Code CLI on `/anthropic`) inherits **Claude Code's** churn instead (the `--bare` default flip is announced for `-p`; WebSearch gating by base URL) but adds none of DeepSeek Harness's [62][69]. Operational burden per lane: Claude Code-on-DeepSeek = low (env vars + alias map + changelog watch); OpenAI-SDK-on-Chat-Completions = low; `dsh` = high (weekly breaking, RC-grade SDK).

**Calibrated fit (anchors shared across the landscape docs: 10 = best-in-class today, 5 = usable with caveats, 1 = unusable).** Research 7 (long context + cheap sweeps; no native search, HLE-w/o-tools 37); Coding-execution 8 / Coding-planning 5 (DeepSWE 74 ≈ Opus vs ProgramBench 20); Cost 10 (cheapest credible frontier-adjacent, cache hits $0.003); Automation 7 (plain HTTPS, Claude Code env recipe, balance endpoint; minus: no OAuth/subscription, 10-min stalls, no SLA, model-ID churn); Trading research 5 (PRC residency + unsettled training use bar proprietary theses; fine for public-data subtasks); Chat surface 7 (Flash TTFT 0.92 s / 232 tok/s, Pro not chat-grade); Visibility 4 (balance-only introspection, no OTEL/usage API, `total_cost_usd` unusable without `modelPricing`).

**Task classes and fit.**

| Task class | Fit | Model / mode | Why |
|---|---|---|---|
| Research drafts, literature sweeps | good | `deepseek-flash`, effort high, 1M ctx | cheap long-context; HLE-with-tools 63.9 ≈ Opus [6] |
| Coding (execute a written plan) | good | `deepseek-flash` in Claude Code, `--max-turns` capped | DeepSWE 74 at 1/15 cost; HN: "execution engine" [31][39] |
| Coding (plan from spec, novel repo) | weak | keep on Claude | ProgramBench 20 vs 37, NL2Repo 64 vs 75 [6] |
| Code review / adversarial review | good as *second* reviewer | `deepseek-v4-pro` max effort | different training lineage = uncorrelated errors; cheap [1] |
| Chat (Telegram) | fair | `deepseek-flash`, thinking off | fast (232 tok/s) but PRC moderation + data residency [18][25] |
| Classification / routing | very good | `deepseek-flash`, thinking off, json_object | ~$0.0002 per call; cache hits $0.003 [1][14] |
| Trading research (Atlas) | good with our tools; never sole planner | `deepseek-flash` + function tools | no built-in market data; PII must be scrubbed [19] |
| Vision (charts, screenshots) | good | `deepseek-flash` | ≤1,024 tokens/image [16] |

**Gotchas.**
1. `tool_choice: required`/named is rejected in thinking mode — disable thinking for forced-tool routing calls [15].
2. With `tools`, you must return `reasoning_content` on every subsequent turn or the request fails — the OpenAI SDK does not do this for you; Claude Code and Codex recipes handle it [11].
3. `json_object` needs the word "json" in the prompt; empty-content responses happen — validate and retry [14].
4. Peak windows hit US evenings (18:00–21:00 and 23:00–03:00 PT Sun–Thu); schedule bulk jobs outside them for 50% off [1].
5. Model IDs churn: alias `deepseek-flash` in config, watch `api-docs.deepseek.com/updates/`, and expect `deepseek-v4-pro` to disappear when V4.1-Pro ships [2][3].
6. 10-minute "inference not started" disconnects and 503s under load — set job timeouts ≥15 min and retry with backoff; consider OpenRouter with provider fallback (DeepSeek → Fireworks → DeepInfra) for availability [7][26].
7. Anthropic-compat ignores `budget_tokens`, `top_k`, `mcp_servers`, documents; `top_p` ≥0.95 in thinking mode; temperature ignored in thinking mode [8][11].
8. Local fallback on the 16 GB M4: V4/V4.1-Flash is unusable (Q2 GGUF ≈ 97 GB, IQ1_M 87 GB; a community stunt ran V4.1-Flash on a 16 GB M1 Mac mini via SSD streaming at ~23 s/token; a 57 GB MoEspresso-pruned V4-Flash exists but still exceeds 16 GB; 128 GB Macs are the practical floor) [37][50]. Only the year-old R1 distills fit — `deepseek-r1:8b` (5.2 GB, Qwen3 base) or `:14b` (9.0 GB) — plus `deepseek-ocr` (3B); treat them as offline-only toys, not routing targets [33][34].
9. Payment: PayPal-only for non-Chinese cards on the official platform (unverified as of 2026-09-24); OpenRouter (cards/USDC) or Ollama Cloud are the low-friction billing paths — both add margin but OpenRouter's DeepSeek endpoint is passthrough-priced [26][47].
10. Data: assume every prompt is stored in the PRC and may be used for training. Re-read 2026-09-24: Open Platform ToS §4.2(1)–(3) (eff. 2026-04-29) only assigns *you* rights over inputs/outputs; the ToS has no clause on DeepSeek's use of API inputs for training or on retention; the Privacy Policy (eff. 2026-02-10) offers a training opt-out for personal data but states downstream end-user data "are not covered by this privacy policy". Net: **no contractual no-training or retention commitment exists for the API** — treat as "may train, indefinite retention, PRC" until DeepSeek answers in writing; keep secrets, keys, account identifiers and proprietary theses out of prompts [18][19].
11. Cost/usage plumbing on the Claude Code lane: `total_cost_usd` is computed from Anthropic's price table and does not know `deepseek-flash` — `modelPricing` is only honoured from managed settings [80], so price from `model_usage` tokens in the runner; the DeepSeek-native cache-hit/miss counters exist only on Chat/Responses, not on `/anthropic` [15][65].
12. WebSearch is silently absent under a third-party `ANTHROPIC_BASE_URL` — any skill that assumes it must inject its own search tool on this lane [61].

## 8. Verdict

1. DeepSeek is the cheapest credible frontier-adjacent option: V4.1-Flash at $0.15/$0.60 off-peak (cache hits $0.003) does agentic coding at roughly GPT-6-Astra/Opus-5 level on DeepSWE and Terminal-Bench 2.1, but visibly trails on planning-heavy benchmarks and in practitioner reports [1][6][31][39].
2. There is no subscription and no way to use the free app programmatically; the only "flat-fee" route is a reseller such as Ollama Cloud Pro ($20/mo, $60 credits), which is still metered credits under the hood [17][36].
3. Integration is nearly free of engineering: the Anthropic-compatible endpoint plus the official Claude Code env recipe means the existing Agent-SDK runner can add a DeepSeek lane with an env dict and a model alias [8][9] — with three now-settled caveats: no WebSearch on that lane (bring your own tool) [61], `ResultMessage.usage` passes through but `total_cost_usd` needs a `modelPricing` override [65], and there is no contractual no-training/retention commitment for API inputs [18][19].
4. The real costs are non-technical — PRC data residency and law, government-device bans, a "C"-grade status page with recurring capacity warnings, model IDs retired on weeks of notice, and price volatility: the 2026-08-13 pricing update (peak/off-peak, effective 08-16 16:00 UTC) was received on HN as "DeepSeek up to 1000% price hike is live" and a 238-point "peak/off-peak pricing update" thread, so today's $0.15/$0.60 is a snapshot, not a floor [2][18][21][42][57][60].
5. Use it as a high-volume execution and second-opinion engine (classification, research drafts, code execution, adversarial review), keep Claude as planner and for anything touching secrets or account data, and never as the sole trading-research authority.

| Dimension | Score (1–10) |
|---|---|
| Research | 7 |
| Coding / agentic | 7 (execution) / 5 (planning) |
| Cost efficiency | 10 |
| Automation friendliness | 7 |
| Trading research | 5 (down from 6: unsettled API training use + PRC residency bar proprietary theses) |
| Chat surface (Telegram) | 7 |
| Visibility / progress plumbing | 4 |

## 9. Sources

All accessed 2026-09-24.

1. https://api-docs.deepseek.com/quick_start/pricing — official price table, peak/off-peak windows, legacy-name routing
2. https://api-docs.deepseek.com/updates/ — changelog (V4.1-Flash 09-10, V4-Pro continuation, Responses API 08-13, effort levels)
3. https://api-docs.deepseek.com/news/news260910/ — V4.1-Flash release note ("phasing out V4-Pro", 552B/8B/16B, KV-cache claims)
4. https://api-docs.deepseek.com/news/news260424/ — V4 preview (1.6T/49B, 284B/13B, 1M default, deepseek-chat/reasoner retirement 07-24)
5. https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro — MIT, FP4/FP8 weights, SWE-bench Verified 80.6, GPQA 90.1, TB2.0 67.9
6. https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash — MIT, 552B/763B, 45T tokens, full frontier and harness benchmark tables
7. https://api-docs.deepseek.com/quick_start/rate_limit — 2,500/500 concurrency, user_id isolation, 10-min timeout
8. https://api-docs.deepseek.com/guides/anthropic_api — /anthropic endpoint, model mapping, supported/ignored fields
9. https://api-docs.deepseek.com/quick_start/agent_integrations/claude_code — env-var recipe, web-search cost caveat
10. https://api-docs.deepseek.com/quick_start/agent_integrations/codex — config.toml provider block
11. https://api-docs.deepseek.com/guides/thinking_mode — reasoning_effort, reasoning_content echo rule, param restrictions
12. https://api-docs.deepseek.com/guides/kv_cache — automatic caching, eviction, usage fields
13. https://api-docs.deepseek.com/guides/responses_api — stateless Responses API, SSE events, unsupported params
14. https://api-docs.deepseek.com/guides/json_mode — json_object requirements and empty-content warning
15. https://api-docs.deepseek.com/api/create-chat-completion — tool_choice rules, max_tokens 1–384K and defaults, usage fields, logprobs
16. https://api-docs.deepseek.com/guides/vision — image limits and token cap
17. https://cdn.deepseek.com/policies/en-US/deepseek-terms-of-use.html — consumer ToU (2026-03-27): no robots/mirrors, no account lending, PRC law
18. https://cdn.deepseek.com/policies/en-US/deepseek-privacy-policy.html — privacy policy (2026-02-10): storage in PRC, training opt-out
19. https://cdn.deepseek.com/policies/en-US/deepseek-open-platform-terms-of-service.html — API ToS (eff. 2026-04-29): output rights, prepaid billing, refunds
20. https://status.deepseek.com/ — component uptimes Jun–Sep 2026
21. https://statusgator.com/services/deepseek — incident log, >165 outages, "C" fairness grade
22. https://en.wikipedia.org/wiki/DeepSeek — company facts, funding, 2026 release dates
23. https://en.wikipedia.org/wiki/DeepSeek_(chatbot) — app details, 500 msg/hr cap, bans, breaches, controversies
24. https://artificialanalysis.ai/models/deepseek-v4-pro — V4-Pro-0813 index 36, 66 tok/s, verbosity note
25. https://artificialanalysis.ai/providers/deepseek — V4.1-Flash index 39, 232 tok/s
26. https://openrouter.ai/api/v1/models/deepseek/deepseek-v4.1-flash/endpoints — per-provider prices, uptime, quantization
27. https://openrouter.ai/api/v1/models/deepseek/deepseek-v4-pro-0813/endpoints — per-provider prices for V4-Pro
28. https://openrouter.ai/docs/api-reference/limits — free-model caps (20 rpm, 50/1,000 per day)
29. https://fireworks.ai/models/deepseek-ai/deepseek-v4p1-flash — $0.22/$0.66/$0.007
30. https://github.com/iinm/plain-agent/issues/265 — Fireworks price rise to $0.30/$1.20 effective 2026-10-01
31. https://fireworks.ai/blog/DeepSeek-V4.1-Flash-Astra — DeepSWE 74.34% at $0.43/task vs GPT-6-Astra; 36.9M input tokens/task
32. https://www.together.ai/pricing — Together DeepSeek rates incl. batch tables
33. https://ollama.com/library/deepseek-r1 — distill sizes (8b 5.2 GB, 14b 9.0 GB), licenses, age
34. https://ollama.com/search?q=deepseek — which DeepSeek models are cloud-only vs local
35. https://ollama.com/library/deepseek-v4.1-flash — cloud-only tag, $0.30/$0.15 input
36. https://ollama.com/pricing — Ollama Cloud Free/Pro $20/Max $100/Team $500 tiers and credits
37. https://terminalbytes.com/run-deepseek-v4-flash-at-home/ — GGUF sizes (87–155 GB), Mac memory floors
38. https://news.ycombinator.com/item?id=49725800 — HN thread on V4.1-Flash (Enclave.ai)
39. https://news.ycombinator.com/item?id=49274600 — HN thread on V4-Pro-0813
40. https://simonwillison.net/2026/Apr/24/deepseek-v4/ — "almost on the frontier" review
41. https://arcprize.org/results/deepseek-v4-flash-0731 — ARC-AGI-1/2 verified scores and cost/task
42. https://introl.com/blog/deepseek-government-bans-spreading-worldwide-2026 — ban list with dates (2026-01-14)
43. https://www.congress.gov/bill/119th-congress/house-bill/1121 — No DeepSeek on Government Devices Act
44. https://therecord.media/bipartisan-bill-ban-deepseek-federal — No Adversarial AI Act
45. https://www.cnbc.com/2026/08/28/deepseek-founder-liang-wenfeng-high-flyer-china-tech-ipos-funding.html — funding/High-Flyer context (403 on fetch; from search snippet, unverified)
46. https://yangmao.ai/en/deals/deepseek-api-free-tokens-2026/ — 5M-token sign-up grant claim (third party, unverified)
47. https://aicreditsapi.com/blog/deepseek-api-credit-card — PayPal-only overseas card path (third party, unverified)
48. https://deepinfra.com/blog/deepseek-v4-pro-pricing-guide-2026-providers-cost-analysis — April 2026 provider comparison for V4-Pro
49. https://llm-stats.com/models/deepseek-v4.1-flash — release date, 763.2B params, providers
50. https://hn.algolia.com/api/v1/search?query=DeepSeek%20V4&tags=story — HN story list and scores
51. https://www.layer3labs.io/guides/deepseek-pricing — "no subscription of any kind" (third party, consistent with [1][23])
52. https://api-docs.deepseek.com/news/news251201/ — V3.2 release (2025-12-01), SWE-bench 73.1, Speciale endpoint (from search snippet)
53. https://deepseek.com/harness/en/ — DeepSeek Harness developer preview: MIT, `npx @deepseek-ai/dsh web`, Standard/Code/Minimal/Creator modes, append-only session log, plugins incl. sandboxes/scheduling/loops (HN 2026-08-13, 747 points, item 49285244)
54. https://api-docs.deepseek.com/quick_start/agent_integrations/ — integration index (Claude Code, Codex, OpenCode, OpenClaw, Hermes, Reasonix, WorkBuddy/CodeBuddy, Qoder, DeepSeek Harness, GitHub Copilot)
55. https://pypi.org/project/deepseek-harness-sdk/ — 0.1.5rc1 (2026-09-10), MIT, Python ≥3.10, JSON-RPC-over-stdio SDK example
56. https://enclave.ai/blog/deepseek-v41-flash-is-now-our-best-hacking-model — 268.3M input (266.2M cached) / ~2M output tokens, $5.14 total
57. https://hn.algolia.com/api/v1/search?query=DeepSeek%20pricing%20update&tags=story — "DeepSeek up to 1000% price hike is live" (item 49287881, 25 pts), "DeepSeek peak/off-peak pricing update" (49296627, 238 pts), "DeepSeek API Pricing Update" (49285160, 130 pts / 185 comments)
58. https://deepinfra.com/deepseek-ai/DeepSeek-V4.1-Flash — Standard / Priority 1.5× / Flex 0.8× tiers, FP8
59. https://api-docs.deepseek.com/quick_start/agent_integrations/openclaw — OpenClaw guide: deepseek-v4-pro / deepseek-v4-flash, Feishu + WeChat channels
60. https://api-docs.deepseek.com/news/news260813/ — 2026-08-13 pricing update, peak/off-peak effective 2026-08-16 16:00 UTC
61. https://code.claude.com/docs/en/tools-reference — WebSearch "not available" on Bedrock, Agent Platform, Foundry, and "sessions using a third-party base URL or LLM gateway"
62. https://code.claude.com/docs/en/feature-availability — web search column by provider (Anthropic API ✓, Bedrock ✗, Agent Platform Claude 4+, Foundry-on-Anthropic); ZDR Enterprise-only; gateway note
63. https://api-docs.deepseek.com/api/get-user-balance — `GET /user/balance`: `is_available`, `balance_infos[{currency,total_balance,granted_balance,topped_up_balance}]`
64. https://github.com/anthropics/claude-agent-sdk-python/blob/main/src/claude_agent_sdk/_internal/message_parser.py — `ResultMessage(usage=data.get("usage"), total_cost_usd=data.get("total_cost_usd"), model_usage=data.get("modelUsage"))` verbatim pass-through
65. https://code.claude.com/docs/en/agent-sdk/cost-tracking — `total_cost_usd` is a client-side estimate from a bundled price table; `modelPricing` override; `costBasis: unknown` for unrecognized model IDs; `usage` excludes subagents, `model_usage` includes them
66. https://code.claude.com/docs/en/data-usage — consumer (Free/Pro/Max) training toggle + 5-year/30-day retention; commercial no-training, 30 days; ZDR qualified Enterprise; local transcripts 30 days; error reporting on for Pro/Max sign-ins
67. https://github.com/deepseek-ai/deepseek-harness/releases — 8 releases 2026-09-10 → 09-24, breaking notes on 0.1.5-rc.1, 0.1.6-alpha.1, 0.1.7-rc.1
68. https://pypi.org/pypi/deepseek-harness-sdk/json — 7 releases 2026-08-11 → 09-10 (0.0.0.dev0 … 0.1.5rc1)
69. https://code.claude.com/docs/en/headless — `--bare` "will become the default for `-p` in a future release"; `--output-format json` cost fields are client-side estimates
70. https://code.claude.com/docs/en/llm-gateway-protocol — feature pass-through table; `service_tier`/beta pairing behavior; `anthropic-ratelimit-unified-*` headers drive plan-usage display (DeepSeek returns none)
71. https://api-docs.deepseek.com/quick_start/error_codes — 401 wrong key, 402 out of balance, 429 too fast, 503 overloaded
72. https://code.claude.com/docs/en/authentication — credential precedence (`ANTHROPIC_AUTH_TOKEN` rank 2, above OAuth), Keychain / `~/.claude/.credentials.json` storage, "login expires in 3 days" warning not shown for env-var credentials, `--bare` ignores `CLAUDE_CODE_OAUTH_TOKEN`
73. https://code.claude.com/docs/en/llm-gateway — `ANTHROPIC_BASE_URL` alone does not replace the subscription; Anthropic "doesn't support routing Claude Code to non-Claude models"; fast-mode / Remote Control / connectors unavailable with a gateway credential (with llm-gateway-connect)
74. https://support.claude.com/en/articles/11145838-using-claude-code-with-your-pro-or-max-plan — limits shared across Claude and Claude Code; no concurrent-session figure
75. https://support.claude.com/en/articles/11647753-how-do-usage-and-length-limits-work — conceptual only; no per-tier numbers, no parallel-session statement
76. https://github.com/deepseek-ai/DeepSeek-V3/issues/347 — "Add other payment providers other than Paypal" (Feb 2025, closed): PayPal-only, card declined inside PayPal
77. https://github.com/deepseek-ai/DeepSeek-V3/issues/1399 — crypto-payment request (2026-06-06): reporter lists cards, PayPal, Alipay, WeChat Pay as current methods
78. https://github.com/deepseek-ai/DeepSeek-V3/issues?q=is%3Aissue+paypal — issue list incl. #1617 (2026-09-01, SE-Asia access question)
79. https://code.claude.com/docs/en/monitoring-usage — OTEL env vars, `claude_code.token.usage` / `api_request` / `tool_result` metric and event schema, cost metric priced from published table
80. https://code.claude.com/docs/en/costs — prompt-cache statistics "work on every provider and gateway"; `modelPricing` is honoured only from managed settings (not `--settings`), so DeepSeek pricing must be computed runner-side
81. https://code.claude.com/docs/en/security — prompt-injection protections (isolated WebFetch context, network command approval, trust verification off under `-p`, Keychain credential storage)
82. https://code.claude.com/docs/en/sandboxing — Seatbelt on macOS, filesystem/network isolation, `allowUnsandboxedCommands`, `sandbox.credentials` deny/mask (macOS blocks masked files instead of substituting)

## Verification log (2026-09-24)

**Corrections applied: 10** — 2 major (Positioning no longer asserts "no first-party agent harness"; the CLI/agentic-tool row now describes DeepSeek Harness and the full official integration list), 8 minor (763B parameter breakdown; R1-distill licensing; DSH label in the Terminal-Bench harness spread; Claude Code recipe deviations from the official env mapping; local-fallback wording incl. the 16 GB SSD-streaming stunt and the 57 GB pruned V4-Flash; Artificial Analysis rank scoped to open-weight models; peak window restated for PDT vs PST; scheduling row cites the Harness plugin).

**Additions (fact-checker's missing topics), all re-fetched 2026-09-24:**
- DeepSeek Harness assessed as a headless-runner candidate in sections 1, 2, 3 and 7 — deepseek.com/harness/en/ (MIT, developer preview, four modes, append-only session log, Cordis plugin kernel incl. sandboxes/scheduling/loops); GitHub README ("THERE WILL BE COMPATIBILITY-BREAKING CHANGES", web UI 127.0.0.1:3080); PyPI `deepseek-harness-sdk` 0.1.5rc1 released 2026-09-10 (Python ≥3.10, JSON-RPC over stdio, `DeepSeekHarness(...).run(task, session_id=...)`); HN launch item 49285244, 747 points / 314 comments, 2026-08-13.
- Anthropic-compat table re-read (api-docs.deepseek.com/guides/anthropic_api): `metadata.user_id` supported, `service_tier` ignored, `tool_choice` auto/any/tool supported with `disable_parallel_tool_use` ignored, `budget_tokens` ignored, `anthropic-beta` ignored except `files-api-2025-04-14`.
- Codex guide: one `~/.codex/config.toml` provider block (`wire_api = "responses"`, `experimental_bearer_token`) shared by Codex CLI, ChatGPT desktop and the VS Code extension.
- Enclave.ai blog: 268.3M input / 266.2M cached / ~2M output tokens, $5.14 total ($4.65 accepted runs), 2,349 Bash commands — added to section 4 cache economics.
- OpenClaw guide: `deepseek-v4-pro` / `deepseek-v4-flash`, Feishu + WeChat channels — cited in the messaging row.
- DeepInfra V4.1-Flash: Standard $0.14/$0.42/$0.004, Priority 1.5×, Flex 0.8× ($0.112/$0.336/$0.0034), FP8.
- Ollama pricing page: Free tier (1 concurrent request, starter credits, pay-as-you-go), Pro $20/$60 credits (3 concurrent), Max $100/$300 (10 concurrent), no rollover.
- HN Algolia: "DeepSeek up to 1000% price hike is live" (49287881, 25 pts), "DeepSeek peak/off-peak pricing update" (49296627, 238 pts), "DeepSeek API Pricing Update" (49285160, 130 pts / 185 comments); news260813 confirms peak/off-peak effective 2026-08-16 16:00 UTC — folded into Verdict 4 as price-volatility risk.
- json_mode page re-read: warns of empty content and `max_tokens` truncation only; the "unending whitespace" phrasing is not present (flagged in place).

**Claims re-verified with sources:** DeepSeek Harness facts [53][54][55]; Anthropic-compat field statuses [8]; Codex shared config [10]; Enclave token/cost figures [56]; OpenClaw models/channels [59]; DeepInfra tiers [58]; Ollama tiers [36]; HN pricing threads and the 08-13 pricing note [57][60]; json_mode warnings [14]; integration index [54]. New sources added: [53]–[60].

**Stale / unverified flags left in place (marked "unverified as of 2026-09-24"):** json_mode whitespace quote (§2); R2 delay attributed to a failed Huawei-Ascend run (§1); Simon Willison's "half of Sonnet 4.6" and "incremental" wording (§5); April V4-Pro preview index 45/44 (§5); "oh-my-pi > Claude Code" harness claim, reworded to what was actually found (§5); freakynit quote wording (§5); CNBC "too large and capital-intensive" quote (§1); PayPal-only overseas card path (§3, Gotcha 9); ~5M-token sign-up grant (§4); "≥17 US states" count and "no US ban on open-weight models" (§5); V3.2-Exp/V3.2 dates (§1); V4.1-Flash launch date 09-09 (Wikipedia, US time) vs 09-10 (DeepSeek note) — primary-source date kept. Newer-than-doc check: no V4.1-Pro release, price change or consumer plan found before 2026-09-24 (coverage limited to the DeepSeek changelog, status page, Ollama, OpenRouter and HN feeds; the web-search budget was exhausted, so WebFetch of known URLs was the only tool available for this pass).

**Gap-fill pass (2026-09-24, second pass; web-search budget exhausted, WebFetch only):**
- **Web search on `/anthropic` — resolved (no):** Claude Code's tools reference withholds WebSearch under any third-party base URL [61][62]; the DeepSeek compat table lists `server_tool_use`/`web_search_tool_result` only as accepted input content blocks [8]. Live curl probe recorded in §6 for final confirmation.
- **Agent SDK usage — resolved structurally:** `message_parser.py` passes `usage`/`total_cost_usd`/`modelUsage` through verbatim [64]; `total_cost_usd` is a client-side Anthropic price-table estimate and needs `modelPricing` for DeepSeek [65]. Live assertion added to §7 as the lane's first-run gate.
- **ToS §4.2(3) training use — resolved as "no commitment":** ToS has no training/retention clause for API inputs; Privacy Policy opt-out covers personal data only and excludes downstream end-user data [18][19]. Gotcha 10 rewritten.
- Cross-doc dimensions added: data-handling matrix incl. the Claude Max OAuth lane [66], `GET /user/balance` introspection [63], normalized 30-day incident window [20][21], TTFT/chat-surface rating [25], third-party-serving permissions (ToS §3.2–3.4) [19], tool-churn clock (8 harness releases / 3 breaking in 14 days) [67][68], calibrated scorecard with shared anchors (§7, §8).
- Not fetchable: GitHub API star/commit counts for deepseek-harness (summary returned implausible numbers, discarded); npm `time` field for `@deepseek-ai/dsh` (dist-tags only: latest 0.1.5-rc.3, next 0.1.7-rc.2, alpha 0.1.7-alpha.2).

**Fact-checker's overall quality rating:** acceptable.

**Gap-fill pass 3 (2026-09-24; web-search budget exhausted at 200/200, WebFetch + local probes only):**
- Curl probe on `/anthropic/v1/messages` with `web_search_20250305`: run unauthenticated (no `DEEPSEEK_API_KEY` in this environment) → 401 in 0.36 s; auth precedes schema validation, so the authenticated probe remains the lane's first-run gate (§6).
- `ResultMessage.usage` pass-through: still not exercised (same reason); added the OTEL route (`claude_code.token.usage` with `model` attribute, provider-agnostic cache stats) as the visibility sink and corrected the `modelPricing` advice — honoured only from managed settings, so price runner-side [79][80].
- Payments: GitHub issues #347 (2025, PayPal-only) vs #1399 (2026-06, cards + PayPal + Alipay + WeChat) — PayPal-only appears stale; top-up page still 403 unauthenticated, so "partially verified" [76][77][78].
- Training/retention: drafted the three-question request to `api-service@deepseek.com` (ToS contact) and flagged that a fetch-summary's "does not train" claim is inference, not a clause [19].
- Cross-doc rows added: credential lifecycle (static key, 402 fail-first, `ANTHROPIC_AUTH_TOKEN` rank 2, base-URL-alone does not detach the subscription, no expiry warning for env credentials) [71][72][73]; concurrency/fan-out (account-level 2,500/500, Max ceiling undocumented per [74][75]); host resource budget (measured 91–488 MB RSS per `claude` process, no daemon); prompt-injection posture (Seatbelt + allowlist identical to Max lane; no model-side safety eval; Anthropic disclaims non-Claude models) [81][82]; reviewer independence (own-rollout OPD, no named teacher; measure disagreement rate before trusting) [6]; cost-table cache-hit sensitivity at 70 %/90 % (audit-log calibration deliberately not read, owed to the cross-doc pass). Chat-surface latency for the Claude primary lane is out of scope here (DeepSeek's own TTFT numbers are in §3).
