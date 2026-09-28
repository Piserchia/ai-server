# Aggregators & agent harnesses (OpenRouter, LiteLLM, Ollama, opencode, aider, goose, Cline, vendor CLIs) — research (as of 2026-09-24)

Scope: the "one interface, many models" layer for a headless macOS server that must audit-log every tool call. Benchmark harness = Claude Agent SDK (already in production here). Web search budget was exhausted for this session, so every fact below comes from direct fetches of primary docs, GitHub, and the HN Algolia API; nothing is from memory unless marked "(unverified)".

## 1. Snapshot

Two layers are conflated under "aggregator": **model gateways** (one API key → many models: OpenRouter, LiteLLM, Ollama Cloud, OpenCode Zen, LM Studio, and the two CDN-hosted gateways Cloudflare AI Gateway and Vercel AI Gateway added in the third pass) and **agent harnesses** (the tool loop that reads/edits/runs: opencode, aider, goose, Cline, Codex CLI, Antigravity CLI, Qwen Code, Kimi Code CLI, Claude Agent SDK). Only harnesses produce audit-able tool-call events; gateways only see chat completions.

| Product | Maker / license | Current version (date) | What it is |
|---|---|---|---|
| OpenRouter | OpenRouter Inc., acquired by Stripe (announced 2026-08-19, closing "in the coming weeks" — no closing confirmation found as of 2026-09-24 (unverified as of 2026-09-24; HN carries only the 08-16…08-19 announcement stories [92]); "same name, same product, same roadmap") [16] | SaaS; $113M Series B 2026-05-30 [92] | OpenAI-compatible gateway to hundreds of models, provider-routed, no markup, 5.5% credit fee [1] |
| LiteLLM | BerriAI, MIT + commercial enterprise tier, 59.5k stars [20] | v1.102.1 (2026-09-23; v1.104.0-dev.1 pre-release the same day) [19] | Python SDK + self-hosted proxy: virtual keys, spend tracking, fallbacks, MCP gateway, Anthropic `/v1/messages` passthrough [18][23] |
| Ollama | Ollama Inc., MIT (server) | v0.34.4 (2026-09-23) [30] | Local runner (MLX on Apple Silicon) + Ollama Cloud hosted open-weight models with `-cloud` tags, OpenAI and Anthropic compatible endpoints [25][28][29]; the Anthropic `/v1/messages` endpoint is real and documented for Claude Code (`ollama launch claude`) [29][115] — see §3 "Local lane" |
| LM Studio | Element Labs, proprietary EULA (2026-08-23) [34] | 0.4.x; `llmster` daemon | Local runner with GUI or headless `lms daemon up`; OpenAI + Anthropic compatible endpoints; "Bionic" agent (2026-07-16) [32][36] |
| opencode | anomalyco (ex-sst), MIT, 209.8k stars [43] | v1.18.32 (2026-09-21) [44] | Terminal coding agent with `run` (headless), `serve` (HTTP+SSE), `acp`; Zen gateway; Anthropic subscription plugin removed 2026-03-19 [45] |
| aider | Aider-AI, Apache-2.0, 49.1k stars [51] | leaderboard last updated 2025-11-20 [50] | Git-native pair programmer; `--message` scripting; Python API "not officially supported" [49] |
| goose | Block → Agentic AI Foundation (Linux Foundation), Apache-2.0, Rust [52] | rolling; repo now `aaif-goose/goose` | Desktop + CLI agent; recipes, `goose schedule` cron, ACP providers that reuse Claude Code / Codex subscriptions [53][54] |
| Cline | Cline Bot Inc., Apache-2.0, 69.2k stars [57] | CLI 2.0 (2026-02; release date unverified as of 2026-09-24) [93] | VS Code agent + `cline` CLI with headless NDJSON mode; free for individuals, pay inference only [55][56] |
| Codex CLI | OpenAI, Apache-2.0, 126.3k stars, Rust (`codex-rs`) [62] | rolling; docs moved to learn.chatgpt.com | `codex exec --json`, Seatbelt sandbox, `codex app-server` JSONL/WebSocket, MCP [58][61] |
| Gemini CLI → Antigravity CLI (`agy`) | Google, Gemini CLI Apache-2.0 (107.1k stars) [67]; Antigravity CLI governed by the Google Antigravity Terms (antigravity.google/terms), which ban third-party-tool access [104] | Gemini CLI stopped serving **sign-in** users (free, Google AI Pro and AI Ultra) on 2026-06-18; it "will remain accessible via paid Gemini and Gemini Enterprise Agent Platform API keys" [63]. Cross-doc reconciliation (re-fetched 2026-09-24, third pass): geminicli.com's quota page **still prints** the Google-login rows — 1,000 RPD personal, 1,500 RPD Google AI Pro, 2,000 RPD AI Ultra — but now carries the banner "Gemini CLI was replaced by Antigravity CLI on June 18th, 2026" for the unpaid tier and Google One users [64], and the Google blog is explicit that Gemini CLI "will stop serving requests for Google AI Pro and Ultra, as well as those using it free of charge", with only Gemini Code Assist Standard/Enterprise licences and paid API keys continuing [63]. So gemini-google.md's 'canonical reading' (AI Pro 1,500 / Ultra 2,000 RPD via Gemini CLI Google login) quotes a legacy table that the same page says is no longer served; the reconciliation is by product **and** by page: the numbers are historical Gemini-CLI quotas, the live consumer path is Antigravity CLI (`agy`) with only qualitative quotas [105]. gemini-google.md should carry the banner text, not the table alone | Go rewrite; `agy -p --output-format json`, `--json-schema`, stream-json stdin/stdout sessions [69] |
| Qwen Code | Alibaba/QwenLM, Apache-2.0, 28.1k stars [73] | 0.22.0 evaluated in README [73] | Gemini-CLI fork; Qwen OAuth free tier **discontinued 2026-04-15**; now Alibaba Coding Plan / Token Plan / any OpenAI-compatible key [71] |
| Kimi Code CLI | Moonshot AI, MIT [75] | `kimi-cli` archived → `kimi-code` (single binary) [74][75] | Kimi Code OAuth or Moonshot API key; `kimi acp`; subagents coder/explore/plan [75] |
| Claude Agent SDK | Anthropic, Commercial ToS [78] | Python/TypeScript; CLI `claude -p` | Runs the Claude Code binary as a library: hooks, subagents, MCP, sessions, permissions, structured output [78][79] |
| Cloudflare AI Gateway | Cloudflare, SaaS, "available on all plans" [132] | rolling; new-customer logging moved to Workers Logs pricing on 2026-09-24 [131] | Proxy in front of Workers AI, Anthropic, Gemini, OpenAI, Replicate "and more": caching, rate limiting, request/token/cost analytics, retry + model-fallback dynamic routing; core features free; Unified Billing credits carry a 5% fee, inference "passed through with no markup"; legacy logs 100k total (Free) / 10M per gateway (Paid); Logpush Paid-only [131][132] |
| Vercel AI Gateway | Vercel, SaaS (GA) [134] | docs updated 2026-09-08/14 [133][134] | `ai-gateway.vercel.sh/v1` — OpenAI Chat Completions, Responses **and Anthropic Messages** endpoints; "no markup and no platform fee on tokens", BYOK at zero fee (paid tier only, with system-credential fallback that bills your credits); budgets per team/project/key/member (soft-cap); provider ordering + model fallbacks with the serving provider returned in metadata; per-request ZDR free on Pro/Enterprise, team-wide ZDR $0.10 per 1k requests; trace drains $0.05 per 1k traces (OTLP to your collector); free tier = subset of models, per-model 429s [133][134] |

Model lineup exposed (representative, exact IDs): OpenRouter top-by-usage 2026-09-23: `anthropic/claude-opus-5.5`, `anthropic/claude-fable-5.1`, `qwen/qwen3.8-max`, `openai/gpt-6-astra`, `anthropic/claude-opus-5`, `openai/gpt-6-sol`, `x-ai/grok-4.7`, `xiaomi/mimo-v2.6-pro` [8]. Ollama Cloud catalog: `glm-5.3`, `glm-5.3-flash`, `deepseek-v4-flash`, `deepseek-v4.1-flash`, `deepseek-v4-pro`, `minimax-m3`, `kimi-k2.6`, `kimi-k2.7-code`, `kimi-k3`, `nemotron-3-ultra`, `gemma4:12b/26b/31b`, `qwen3.5:0.8b…122b`, `mistral-large-3`, `gpt-oss:20b/120b` [31]. OpenCode Zen: 60+ models incl. GPT-6 Luna $0.10/$0.50, Claude Haiku 4.5 $1/$5, DeepSeek V4 Flash $0.14/$0.28 per 1M, plus rotating free "stealth" models [40]. Context windows for the frontier set are 1M (Claude Sonnet 5 `anthropic/claude-sonnet-5-20260630` 1,000,000 ctx / 128k out; GPT-6 Astra 1,050,000 / 128k; Gemini 3.8 Flash 1,048,576 / 65,536; Kimi K3 1,048,576; DeepSeek V4 Flash 1,048,576) [9][12][13][11][10]. Knowledge cutoffs: not published by the gateways; see the per-vendor docs in this folder.

Release cadence: LiteLLM weekly minor releases [19]; Ollama roughly weekly patch releases [30]; opencode several patch releases per week [44]; Antigravity CLI replaced Gemini CLI wholesale in June 2026 [63]; Terminal-Bench itself is on 4.0 (2026-08-28) [94].

Positioning in one paragraph: OpenRouter is the default "any model, one key" gateway and is now Stripe-owned; LiteLLM is the self-hosted equivalent with the richest control plane but a serious 2026 supply-chain incident; Ollama Cloud is the cheapest legitimate subscription path to strong open-weight models with a local fallback on the M4; opencode is the most complete open harness (headless, HTTP server, ACP) but is legally cut off from Claude subscriptions; goose is the only third-party harness with a built-in cron scheduler (Claude Code itself now ships cloud Routines, Desktop scheduled tasks and in-session `/loop` [96][97][98]) and can front Claude Code and Codex via ACP; Codex CLI and Antigravity CLI are the vendor headless executors with the best JSON event streams after Claude Code; aider is the low-overhead git-diff specialist; Cline is a fine BYOK CLI with weaker orchestration story; Qwen Code and Kimi Code are worth having only for their own models.

## 2. Interfaces & surfaces

| Surface | OpenRouter | LiteLLM proxy | Ollama (local + cloud) | LM Studio | opencode | goose | Codex CLI | Antigravity CLI | Claude Agent SDK |
|---|---|---|---|---|---|---|---|---|---|
| Consumer app | web chatroom (local storage) [1] | admin UI only [18] | macOS app + `ollama://apps` protocol (0.34.2) [30] | desktop app, Bionic agent [36] | TUI, `opencode web` [37] | desktop + CLI [52] | TUI + ChatGPT desktop/IDE [60] | TUI (`agy`), Antigravity 2.0 desktop [70] | Claude Code TUI / desktop |
| API style | OpenAI-compatible `/api/v1/chat/completions` + Responses [12] | OpenAI, Anthropic `/v1/messages`, Responses, A2A, MCP gateway [18][19] | `/api/chat`, `/v1/chat/completions`, `/v1/responses`, `/v1/embeddings`, Anthropic `/v1/messages` [28][29] | `/v1/models,chat/completions,completions,embeddings,responses` port 1234 [33] | OpenAPI 3.1 at `:4096/doc`, SSE `/global/event` [39] | `goose acp` stdio; no HTTP server doc found [53] | `codex app-server` JSONL stdio / WebSocket / Unix socket, bearer or capability token [58] | `--input-format stream-json` stdin sessions [69] | Python/TS packages; CLI `--output-format stream-json` [79] |
| Official SDKs | OpenAI SDKs work | Python SDK + proxy | Python/JS libs; OpenAI/Anthropic SDKs work [25] | `lms` CLI, JS/Python SDKs | `@opencode-ai/sdk` (TS, generated from OpenAPI) [39] | Rust binary, ACP | Rust binary; TS app-server client | Go binary | Python, TypeScript [78] |
| MCP | via clients | MCP gateway w/ OAuth 2.0, access groups, semantic tool search [19] | n/a (client side) | MCP in app since 0.3.17 [95] | `opencode mcp` [37] | 70+ MCP extensions [52] | `codex mcp` stdio/HTTP + OAuth [58] | yes ("Extend") [70] | yes [78] |
| Tool use / structured out | `tools`, `tool_choice`, `structured_outputs` per endpoint [9][12] | passthrough | tools, JSON mode, `/v1/responses`; **no `tool_choice`**, no logprobs, base64 images only [28][29] | tools + structured output pages exist [33] | permissions per tool [42] | recipes with params [53] | `--output-schema` JSON Schema [58] | `--json-schema` → `structured_output` [69] | `--json-schema` → `structured_output` [79] |
| Batch API | GPT-6 batch prices listed (50% off) [15]; BYOK batch for Vertex [4] | "batch billing end-to-end" v1.99 [19] | no | no | no | no | n/a | n/a | Anthropic Batch API 50% off (Client SDK, not Agent SDK) [80] |
| Computer/browser use | model-dependent | passthrough | no | no | webfetch tool [42] | extensions | sandboxed shell | shell | Claude browser/computer toolsets exist on API [80]; SDK has WebFetch/WebSearch [78] |
| Scheduled tasks | no | no | no | no | no (external cron) | **`goose schedule add/list/remove/run-now`** cron + `sessions` [53] | no (external) | no | **yes**: cloud Routines (`/schedule`; cron ≥1h, API `/fire` and GitHub triggers; Pro/Max/Team/Enterprise, research preview, daily run cap drawn from subscription usage) [96], Desktop scheduled tasks (local, 1-min granularity) [97], in-session `/loop`/`CronCreate` (7-day expiry) [98]; Managed Agents scheduled deployments (API key, beta) [101] |
| Memory / sessions | session stickiness for Auto Router [5] | "memory management for persistent user preferences" [18] | stateless (`/v1/responses` non-stateful) [28] | stateful chats via REST [33] | sessions, `export` JSON, `--continue/--session` [37] | `--resume`, `--name`, `--no-session` [53] | `codex exec resume --last` [58] | `--continue`, `--conversation ID`, `/fork` [69] | resume/fork sessions [78][79] |
| Messaging (Telegram/Slack/etc.) | none native | none | none | none | `opencode github` bot only [37] | none (desktop) | none (ChatGPT app surfaces) | none | none (this server's Telegram bot) |
| IDE / ACP | n/a | n/a | n/a | Zed/JetBrains via OpenAI compat | `opencode acp` → Zed, JetBrains, Neovim [41] | `goose acp` [53] | ACP via adapter [87] | Antigravity IDE; ACP not confirmed | "Claude Agent" via Zed adapter [87] |

ACP (Agent Client Protocol, JSON-RPC over stdio) is the emerging common wire format for harnesses: native implementers include Gemini CLI, OpenCode, Goose, Kimi CLI, Qwen Code, Cline, Cursor, Factory Droid, GitHub Copilot, OpenHands, Mistral Vibe; Claude Agent (Zed adapter), Codex CLI (ACP adapter) and Pi are adapter-based [86][87]. This matters for section 7: goose exposes `claude-acp` and `codex-acp` *providers*, i.e. it can orchestrate Claude Code and Codex through their own subscriptions [54].

Claude Code's own scheduling and remote-steering surfaces (new since the last pass, all on the subscription login):

- **Cloud Routines** (research preview): a saved prompt + repositories + connectors that runs as a full cloud session on Anthropic-managed (or self-hosted) infrastructure. Triggers: schedule (presets, or a custom cron via `/schedule update`; "The minimum interval is one hour; expressions that run more frequently are rejected"), API (`POST …/v1/claude_code/routines/<id>/fire` with a per-routine bearer token, beta header `experimental-cc-routine-2026-04-01`, optional untrusted `text` payload wrapped in `<routine-fire-payload>`), and GitHub events (pull_request, release, with filters). Pro, Max, Team and Enterprise; "Routines draw down subscription usage the same way interactive sessions do" plus a per-account daily run cap; one-off runs are exempt from the cap; a green run status "does not mean the task in your prompt succeeded". Created at claude.ai/code/routines, from Desktop, or with `/schedule` in the CLI (`/schedule list|update|run`); `/schedule` requires a claude.ai login and is hidden under an API key [96].
- **Desktop scheduled tasks**: local, 1-minute granularity, run only while the Desktop app is open and the machine awake (one catch-up run on wake for up to seven missed days), per-task permission mode and worktree isolation, prompt stored at `~/.claude/scheduled-tasks/<name>/SKILL.md` [97].
- **In-session `/loop` / `CronCreate`**: 1-minute granularity, up to 50 tasks per session, recurring tasks expire after seven days, fire only while the session is idle; restored on `--resume` except expired/self-paced loops [98].
- **Steering cloud sessions from a script**: `claude -p "your message" --cloud <session-id>` queues one message into a running cloud session and exits (`--output-format json` returns `{ok, session_id, url}`); requires `claude auth login` on an Anthropic account and the org's `allow_remote_sessions` policy; an `ANTHROPIC_BASE_URL` gateway does not disqualify it, Bedrock/Vertex/Foundry do [99].
- **Hosted harnesses (API-key only)**: Claude Managed Agents (beta header `managed-agents-2026-04-01`) is Anthropic's managed harness — agent/environment/session/events model, cloud or self-hosted sandboxes (`ant beta:worker` polls an environment), **scheduled deployments** (POSIX cron + IANA timezone, minute granularity, jitter up to 15% of the interval, per-run `budget` copied onto each session, webhook events for every run, `deployment_runs` history, `ant apply deployment.md`, max 1,000 deployments per org), $0.08 per session-hour on top of tokens [100][101][102][80]. OpenAI's **Agents API** (HN 2026-09-10, 350 points) is the counterpart: "access to the Codex harness through an OpenAI-managed API" with OpenAI-hosted or self-hosted sandboxes, `OpenAI-Beta: agents=v1`, billed at model API rates plus hosted-sandbox charges [103][114]. Both require an API key, which collides with this server's no-`ANTHROPIC_API_KEY` policy (see §3).

## 3. Headless / server automation fit

Auth modes and the terms that govern them:

- **Claude (benchmark).** `claude -p` and the SDK use the Claude Code login by default; `--bare` mode "never reads OAuth credentials" and requires `ANTHROPIC_API_KEY` [79]. The Agent SDK docs state: "Unless previously approved, Anthropic does not allow third party developers to offer claude.ai login or rate limits for their products, including agents built on the Claude Agent SDK" [78]. Consumer ToS (effective 2025-10-08) prohibits access "through automated or non-human means" except via an API key "or where we otherwise explicitly permit it" [83]; the Pro/Max support article lists no restriction on headless/scheduled use and explicitly covers Claude Code in the plan [82]. Reading: first-party Claude Code/SDK under the owner's own Max login is the explicitly permitted path; third-party harnesses on Max OAuth are not (and opencode was made to remove that plugin "per legal requests" on 2026-03-19 [45]; the earlier "You are OpenCode" system-prompt block was observed Jan 2026 and reported lifted by 2026-03-23 per a gist, not re-verified as of 2026-09-24 [46]).
- **OpenAI Codex.** `codex login --device-auth` (beta) works on a browserless box; `~/.codex/auth.json` can be copied over SSH; tokens auto-refresh. Docs: "Use API key authentication for programmatic Codex CLI workflows, such as CI/CD jobs"; the auth page does not say ChatGPT sign-in is prohibited for automation; it says "API keys are still the recommended default for automation", documents an advanced "Maintain Codex account auth in CI/CD" workflow for trusted private runners (serialized jobs, `~/.codex/auth.json` treated like a password, never for public repos) [106], and ChatGPT Enterprise admins can mint Codex access tokens "intended for trusted scripts, schedulers, and private CI runners" [60]. Plus/Pro/Business/Edu/Enterprise (and Free/Go) all include Codex [59].
- **Google.** Antigravity CLI headless "uses your cached credentials. Authenticate once with an interactive `agy` session first"; without cached auth it exits with an auth error rather than hanging [69]. Gemini API key path (`GEMINI_API_KEY`) remains for Vertex/API billing [64]. Antigravity's Terms state "Using third party software, tools, or services to access the Service (e.g. using OpenClaw with Antigravity OAuth) is a breach of this Agreement" and that such use "may be grounds for suspension or termination of your Antigravity and/or Gemini CLI accounts" (§6 of the Antigravity Additional Terms; HN 2026-09-03, 338 points) [104] — so Antigravity OAuth may only be driven by `agy` itself, never from goose/opencode/LiteLLM, and the blast radius is the whole Google account.
- **OpenRouter / LiteLLM / Ollama Cloud / Zen / Kimi API / DeepSeek API.** plain API keys; OpenRouter also supports BYOK for OpenAI, Bedrock, Vertex, Azure at a 5% fee after a $25k/month list-price allowance [4]. Ollama: `OLLAMA_API_KEY` bearer against `https://ollama.com` [25].
- **Local lane (Ollama → Claude Code / Agent SDK).** Resolved 2026-09-24 against Ollama's own docs, overriding local-models-m4-16gb.md §2 ("no Anthropic endpoint; SDK cannot target a local model"): Ollama **does** serve an Anthropic-compatible `/v1/messages` ("Connect Anthropic clients and tools such as Claude Code to Ollama") supporting messages, streaming, system prompts, multi-turn, vision, tool calling and thinking; **unsupported**: `tool_choice`, prompt-cache `cache_control`, `/v1/messages/count_tokens`, Batches, Citations; token counts are approximations and `budget_tokens` is accepted but not enforced [29]. The documented Claude Code recipe is `ollama launch claude` or `ANTHROPIC_AUTH_TOKEN=ollama ANTHROPIC_API_KEY="" ANTHROPIC_BASE_URL=http://localhost:11434 claude --model <model>`, with the caveats "choose a model with enough context for your repository" (64k+ recommended) and, on cloud models, "Hosted WebSearch and advanced tool controls are not fully supported" [115]. Because the Agent SDK spawns the same Claude Code binary and inherits the process environment, the same three variables should redirect SDK jobs too (inferred from [78][115]; not exercised on this server as of 2026-09-24). Consequences for the runner: (i) `ANTHROPIC_API_KEY=""` must be set *empty*, which is compatible with the no-API-key policy; (ii) Claude Code disables server-side tool search off first-party, so MCP schemas eat context [23]; (iii) the 16 GB M4 limits usable local models to ≤9B-class at 64k context (§4), so the local lane fits the runner **only for classification/summarisation-grade jobs**, not as a coding executor. The local-models doc's §2 claim should be corrected.
- **Coding-plan keys are interactive-only.** Alibaba Coding Plan: "This plan is for interactive use in programming tools such as Claude Code, Qoder, Qoder CN, and OpenClaw. Do not use the plan's API key for automated scripts, application backends, or other non-interactive scenarios" — violations "may result in subscription suspension or API key revocation"; caps 6,000 req / 5 h, 45,000 / week, 90,000 / month, whichever hits first; usage only on the console dashboard [113]. That prohibition (already recorded in qwen-alibaba.md) means the Coding Plan is **not** a lane for this server's scheduler, only for the owner's interactive Qwen Code sessions. Kimi Code plan: the docs say third-party tools (Claude Code, OpenCode, Codex) are wired "by manually configuring an API Key"; the Kimi Code membership ("membership subscription" billing) is a separate product from the Kimi Platform key ("pay-as-you-go, top up and use"), and no OAuth flow for Claude Code and no usage endpoint are documented [76]. Whether the key issued to a Code member draws on the subscription or on metered platform credit is not stated on fetchable pages (unverified as of 2026-09-24) — kimi.md's reading (plan OAuth undocumented; API key = metered) is the conservative one and §4 below now follows it.
- **Subscription logins inside open harnesses.** opencode: ChatGPT Plus/Pro via `/connect` (Codex OAuth), GitHub Copilot device flow; "There are plugins that allow you to use your Claude Pro/Max models with OpenCode. Anthropic explicitly prohibits this" and they were unbundled in 1.3.0 [38]. goose: `claude-acp` requires "an active Claude Code subscription", `codex-acp` "ChatGPT Plus/Pro subscription or OpenAI API credits", GitHub Copilot via device flow [54]. Kimi Code: third-party harnesses take a manually configured API key; whether that key is subscription-backed or metered is undocumented (see "Coding-plan keys" above) [76]. Alibaba Coding Plan is a fixed-monthly key (`BAILIAN_CODING_PLAN_API_KEY`) usable from Qwen Code [71] but contractually interactive-only [113].
- **Hosted harnesses.** Claude Managed Agents needs "A Claude API key" on every request (`x-api-key: $ANTHROPIC_API_KEY`) — there is no subscription path — so it conflicts with this server's rule that `ANTHROPIC_API_KEY` is never set; adopting it is an owner-level policy change, not an integration detail [100][101]. The OpenAI Agents API is likewise API-key-only [103]. Zero-retention caveats: Managed Agents "is not currently eligible for Zero Data Retention (ZDR) or HIPAA Business Associate Agreement (BAA) coverage" because sessions are stateful [100]; Claude Code cloud sessions (and therefore Routines and `--cloud`) are unavailable to ZDR organisations ("Organizations with Zero Data Retention enabled can't use `/web-setup` or other cloud session features") [99]; the OpenAI Agents API "does not support Zero Data Retention (ZDR)" and is US-data-residency only [103].

Rate limits / caps: OpenRouter free models (22 `:free` variants on 2026-09-24 [111]) 20 req/min, 50 req/day (<$10 lifetime purchases) or 1,000 req/day (≥$10) [2]; paid models have no platform cap beyond upstream and an in-flight credit hold [2]. Ollama Cloud: 1 / 3 / 10 concurrent requests on Free / Pro / Max, queue with fixed cap [26]. Codex: GPT-6 Luna 350–3,000 messages per 5h on Plus, 1,750–14,000 on Pro 5x, 7,000–56,000 on Pro 20x [59]. Gemini CLI legacy quotas (now Antigravity): 1,000 req/day Google login, 250/day unpaid API key (Flash only), 1,500/day AI Pro, 2,000/day AI Ultra [64]. Antigravity quotas are documented qualitatively at antigravity.google/docs/plans: Free = "meaningful quota, refreshed weekly"; Google AI Pro ($19.99/mo) = "high, generous quota, refreshed every five hours until weekly limit reached"; AI Ultra (from $99.99/mo) = highest five-hour quota, highest weekly limit, third-party models; Pro/Ultra can buy AI-credit overages at Gemini Enterprise pricing; no BYOK or org contracts for extra limits [105][112]. Exact request counts are not published.

Sandboxing: Codex uses macOS Seatbelt (`sandbox-exec`) with `read-only | workspace-write | danger-full-access`; `workspace-write` blocks network by default (unverified as of 2026-09-24: the config reference exposes `sandbox_workspace_write.network_access` as a boolean but the fetched pages do not state its default); approval `on-request | never`; "full access" = `danger-full-access` + `approval_policy = "never"` [61]. Claude Code: `-p` permission baselines `auto | dontAsk | acceptEdits` (the documented `-p` baselines; `plan` and `bypassPermissions` also exist as modes — completeness of the list is unverified as of 2026-09-24) [79][99], `--permission-prompts none` for unattended runs (denials appear as `permission_denied` events), `--allowedTools "Bash(git diff *)"` prefix rules, `--bare` skips hooks/MCP/CLAUDE.md discovery and will become the default for `-p` [79]. Antigravity: scoped allow rules `{"permissions":{"allow":["command(git)","write_file(src/)"]}}`, tools needing approval are "soft-denied" in headless [69]. Qwen Code: `--yolo` (no sandbox), `--approval-mode plan|default|auto-edit|auto|yolo`, run budgets `--max-session-turns`, `--max-wall-time`, `--max-tool-calls` with exit codes 53/55 [72]. opencode: `allow|ask|deny` per tool with bash glob patterns, `--auto` approves everything not denied; **documented bypasses**: `echo 'git clean -fdx .' | bash`, `python3 -c ...`, base64, redirections not checked in the AST; CVE-2026-22812 default HTTP server with permissive CORS enabled RCE from websites [48]. Gemini CLI: `-s/--sandbox` (macOS profile details not on the page fetched) [65]. goose, aider, Cline: no OS sandbox; Cline has `CLINE_COMMAND_PERMISSIONS` env allowlist [55]; aider only edits files and commits.

JSON event output for orchestration (what the audit log can ingest):

| Harness | Invocation | Stream | Notable fields |
|---|---|---|---|
| Claude Code / SDK | `claude -p ... --output-format stream-json --verbose --include-partial-messages` | NDJSON: `system/init` (tools, mcp_servers, plugin_errors, capabilities), `assistant`/`user` with `parent_tool_use_id` for subagents, `system/api_retry`, `permission_denied`, final `result` with `total_cost_usd`, `session_id`, `permission_denials`, `structured_output` [79] |
| Codex CLI | `codex exec --json -o last.md --sandbox workspace-write -a never` | NDJSON events + last-message file; `--output-schema` [58] |
| Antigravity CLI | `agy -p ... --output-format stream-json` | `init`, `step_update`, `result`; JSON envelope has `conversation_id`, `status`, `usage`, `structured_output`; exit 0/1/2 [69] — confirmed, but soft-denied tools exit 0 with a stderr notice, so the exit code alone does not signal a denied action |
| Qwen Code | `qwen -p ... --output-format stream-json` | `system/session_start`, `assistant` (usage), `result` (`duration_ms`, `stats`); tool results capped at 65,536 bytes; `QWEN_CODE_UNATTENDED_RETRY=1` [72] |
| Gemini CLI (legacy) | `gemini -p ... --output-format stream-json` | `init, message, tool_use, tool_result, error, result`; exit 42 validation, 53 turn limit [66] |
| opencode | `opencode run --format json --auto --model provider/model` or `POST /session/:id/message` + SSE `/global/event` | bus events over SSE; `opencode export` session JSON [37][39] |
| goose | `goose run -t "..." --output-format stream-json --no-session --max-turns N -q` | text/json/stream-json [53] |
| Cline | `cline --json --auto-approve true "..."` (headless auto when stdout is redirected) | NDJSON messages [55] |
| aider | `aider --message "..." --yes --no-auto-commits` | text only; git diff is the artifact [49] |

Data-handling matrix (per lane and auth mode; "—" = not published on fetched pages as of 2026-09-24):

| Lane / auth | Training on your I/O | Retention | Residency | ZDR eligible | Source |
|---|---|---|---|---|---|
| **Claude Code / Agent SDK on Max OAuth (primary lane)** | Only if "Help improve Claude" is on; default not stated on the fetched page; safety-flagged and `/feedback` transcripts are always usable; Incognito never | 5 years if improvement is on, **30 days if off**; `/feedback` 5 years; local transcripts 30 days (`cleanupPeriodDays`) | US processing (Anthropic first-party); no residency option on consumer plans | **No** (ZDR is Enterprise-only, per-org) | [117][118][119] |
| Claude API key (Sonnet/Opus via Client SDK) | No (commercial terms) unless Developer Partner Program | 30 days standard | — | Yes for qualified orgs | [117] |
| Claude Managed Agents / Claude Code cloud sessions (Routines, `--cloud`) | as above by account type | as above | Anthropic-managed VMs | **No** | [99][100] |
| Codex CLI on ChatGPT login | follows ChatGPT workspace/account settings ("Codex usage follows your ChatGPT workspace permissions … retention and residency settings") | — | — | Enterprise only | [60] |
| OpenAI Agents API | — | — | US only | No | [103] |
| Ollama Cloud | "never train on it" | "not stored beyond the time required to fulfill the request" (transient) | "may be transferred to and processed in the United States" | effectively ZDR by policy, no contract | [116] |
| Ollama local | none leaves the machine | local | local | n/a | [25] |
| OpenRouter | provider-dependent; account toggle "allow routing to providers that may train" (separate for free/paid); OpenRouter's own prompt policy not stated on that page (1% discount if you opt into logging [1]) | provider-dependent; per-endpoint data policy shown in metadata | EU/US in-region routing for Enterprise only | per-request `provider.zdr: true` or account-wide [6] | [3][6] |
| LiteLLM proxy (self-hosted) | none itself; upstream policy applies | whatever the configured log sink keeps | your host | passthrough | [18] |
| OpenCode Zen | zero-retention "for most providers"; "Contributor Free" stealth models may be trained on | — | — | partial | [40] |
| LM Studio (local) | none | local | local | n/a; Bionic advertises ZDR | [36] |
| Antigravity CLI on Google sign-in | governed by Antigravity Terms; not stated on fetched pages | — | — | — | [104][105] |
| Alibaba Coding Plan / Kimi Code / Qwen Code | not found on fetched pages | — | CN-operated endpoints (Alibaba `coding.dashscope`), Moonshot | — | [71][76][113] |

Reading for the paper-trading lab: proprietary theses on the primary lane are retained 30 days (improvement toggle off) with no ZDR; the only ZDR-by-contract options are Claude API key (policy-blocked) or OpenRouter `zdr: true`; Ollama Cloud is transient by policy. Confirm the Max account's improvement toggle is **off** before routing theses.

Progress-visibility plumbing (what the runner can read programmatically):

| Lane | Remaining quota (5 h / weekly) | Per-job cost & tokens | Telemetry export |
|---|---|---|---|
| Claude Code / SDK (Max) | **TUI only** (`/usage`); OTEL exports usage, not remaining quota | `result.total_cost_usd`, per-message `usage` in stream-json [79] | OTEL metrics (`claude_code.cost.usage`, `claude_code.token.usage`, tool decisions) + events via `CLAUDE_CODE_ENABLE_TELEMETRY=1`, OTLP/Prometheus [120]; Routines run history on claude.ai/code/routines [96] |
| Codex CLI (ChatGPT login) | TUI only (`/status`) or chatgpt.com/codex/settings/usage; Analytics/Compliance APIs Business/Enterprise only [59] | `codex exec --json` events | none first-party beyond app-server events [58] |
| Antigravity CLI | none (qualitative plans page) [105] | `usage` in JSON envelope [69] | none |
| OpenRouter | `GET /api/v1/auth/key` (usage, limit, remaining) [2] | `usage` per response incl. cost | activity export in dashboard |
| Ollama Cloud | settings/usage web page only [25] | credits shown in dashboard | none |
| LiteLLM proxy | virtual-key budgets, `/spend/*` DB endpoints | per-request cost via `completion_cost` | OTEL, Langfuse, Prometheus, Datadog, S3/GCS … [121] |
| MiniMax coding plan | documented `/v1/token_plan/remains` per minimax doc (not re-fetched; 404 on the guessed docs URL) | — | — |
| Kimi Code | none documented [76] | — | — |
| Alibaba Coding Plan | console dashboard only [113] | — | — |
| Grok Build | OTEL is double opt-in per grok-xai.md (page 404 here) | — | OTEL |

Implication: no subscription lane exposes remaining 5-hour/weekly budget to a script; the runner must infer headroom from its own token ledger (OTEL for Claude, `usage` fields elsewhere) and treat 429/"limit reached" as the signal.

### Cross-cut matrices (third pass, 2026-09-24) — the dimensions the other docs left scattered

**(a) Concurrency per lane on subscription auth** — what bounds the scheduler's fan-out:

| Lane | Documented concurrency cap | What actually bounds parallel headless sessions | Source |
|---|---|---|---|
| Claude Code / SDK on Max | **none published.** No page states a session or connection cap; limits are a *usage pool* ("all activity in both tools counts against the same usage limits"; 5-hour + weekly windows; "running multiple instances or automation" is named only as a cost driver) | N parallel `claude -p` runs burn the 5-hour window N× faster; the only numeric concurrency guidance Anthropic publishes is on the API side (200k–300k TPM and 5–7 RPM per user for 1–5-user orgs) and agent teams "use approximately 7x more tokens" — so plan fan-out by tokens per window, not by session count | [82][136][137] |
| Codex CLI on ChatGPT login | none published for sessions; message caps per 5 h (Plus 350–3,000 Luna msgs) | the CI/CD auth doc mandates **one `auth.json` per runner or per serialized workflow stream** because concurrent refreshes rotate tokens against each other — so effective headless concurrency = number of independently seeded `auth.json` copies (each a device-auth login), then the 5-hour message cap | [59][106] |
| Antigravity CLI on Google AI Pro/Ultra | none published; quotas qualitative ("five-hour quota … weekly limit") | unknown; the headless page says nothing about parallel runs, and every run shares one cached credential | [69][105] |
| GitHub Copilot Pro/Pro+ | none numeric on fetched pages; the CLI concept index advertises `/fleet` for "parallel task execution" | premium-request credits (1,500 / 7,000 per month) are the binding constraint, not connections | [122][138] |
| Ollama Cloud Free/Pro/Max | **1 / 3 / 10** concurrent requests, queue with fixed cap | hard, documented | [26] |
| Kimi Code / MiniMax plan / Z.ai plan | 1–4 tasks / "3–4 agents" / "1–2 projects" (per kimi.md, minimax.md, z-ai.md) | vendor-stated, soft | those docs |
| OpenRouter / LiteLLM / Cloudflare / Vercel | no platform cap beyond upstream; per-model 429s on free tiers | credit balance and upstream RPM | [2][131][133] |

Design consequence: the runner's fan-out limit must be a **per-lane token budget per rolling window** (Claude, Codex, Antigravity), a **semaphore** only where a hard number exists (Ollama 1/3/10, Kimi 1–4), and a **per-seed serialization lock** for Codex account auth.

**(b) Credential lifecycle on a headless box:**

| Lane | Storage | TTL / refresh | Fails how | Alarm the runner can implement |
|---|---|---|---|---|
| Claude Code / SDK (Max OAuth) | macOS **Keychain**; falls back to `~/.claude/.credentials.json` (mode 0600) when the Keychain rejects the write, e.g. locked in an SSH session; `CLAUDE_CONFIG_DIR` keys a separate entry/file | refreshed automatically; `/login` warns 3 days before expiry (v2.1.203+); `claude setup-token` mints a **one-year** OAuth token for `CLAUDE_CODE_OAUTH_TOKEN` (model requests only; no Remote Control / claude.ai connectors; not read in `--bare`) | every request fails with `Login expired · Please run /login` (v2.1.206+); `/status` shows `Login: Expired — log in again` (v2.1.210+); "a background session … that outlives the login stops making progress" | grep stream-json for the `Login expired` error → page owner; prefer the one-year `setup-token` on the server and calendar its renewal | [139] |
| Codex CLI (ChatGPT login) | **plaintext** `~/.codex/auth.json` or OS credential store; "treat like a password" | auto-refresh during use; in CI the bundle is refreshed when `last_refresh` is older than **~8 days**; built-in refresh-and-retry on 401 | 401 after a failed refresh; sharing one file across concurrent jobs corrupts rotation | stat `last_refresh` in `auth.json`; if > 7 days, run a throwaway `codex exec "ok"` to force refresh; never re-seed an existing file | [60][106] |
| Antigravity CLI | "cached credentials" — path and format undocumented | undocumented | headless "exits with an auth error rather than hanging" | non-zero exit + stderr auth string → alarm; re-auth needs an interactive `agy` (browser) | [69] |
| GitHub Copilot CLI | `~/.copilot` (per crosscut docs; not fetched here) | `gh` token semantics | 401 | `gh auth status` in cron | [138] |
| Grok Build / Mistral Vibe / Hermes / OpenClaw | `~/.grok/auth.json`, `~/.vibe/.env`, `~/.hermes/` (HERMES_HOME; API keys via `hermes config set`), `~/.openclaw/openclaw.json` (holds channel and provider tokens) — all plaintext files | API keys: no TTL; OAuth (Grok): per grok-xai.md | 401 | file-permission audit (0600) + 401 counter | [140][141] |
| Ollama Cloud / OpenRouter / DeepSeek / Cloudflare / Vercel | API keys in `.env` | none | 401 / 402 (negative balance) | balance poll (`GET /api/v1/auth/key` on OpenRouter) | [2][25] |

What fails first on a fresh server: the Keychain path (Claude writes to the file fallback when the Keychain is locked over SSH — expect `.credentials.json`, and treat it like `auth.json`); then Codex's 8-day refresh if the lane sits idle; then Antigravity, which has no non-interactive re-auth at all.

**(c) Progress-visibility sink** — the collector side, which no doc evaluated:

| Option | RAM on the 16 GB M4 | Fit |
|---|---|---|
| Langfuse v3 self-hosted (web, worker, Postgres, ClickHouse, Redis, MinIO) | vendor minimum **4 cores / 16 GiB** for the compose stack [142] | **excluded** — it alone is the whole machine |
| LiteLLM proxy as the sink (`/spend/*`, virtual keys) | vendor floor **4 GiB per worker** ("treat 4Gi as the absolute floor" when storing prompts in spend logs) [143]; a 1-worker dev config runs lower but has no published number | tolerable at 1 worker with `--max_requests_before_restart 10000`; covers gateway calls only, not harness events |
| OTEL Collector (contrib) + Prometheus + Grafana | no vendor sizing; the collector doc only offers `memory_limiter` [149]; three long-running daemons (estimate, unsourced: 0.3–0.8 GB combined) | possible, but it is three more launchd services to babysit for one viewer |
| **Existing web dashboard + Postgres** (recommended) | 0 new daemons | Claude Code exports `OTEL_METRICS_EXPORTER=prometheus` on `:9464` and `OTEL_LOGS_EXPORTER=otlp` with `http/json`, which a 40-line FastAPI route in the existing gateway can receive; Vercel trace drains and LiteLLM callbacks also speak OTLP/HTTP [120][133][121] |

Common cross-lane event schema (one Postgres table, one JSONL mirror in `volumes/audit_log/`): `ts, job_id, lane, harness, model, provider_returned, session_id, event_type ∈ {session_start, tool_use, tool_result, permission_denied, api_retry, rate_limited, result, auth_expired}, tokens_in, tokens_out, cache_read, cache_write, cost_usd, effort, exit_code`. Emitter mapping: Claude stream-json `result.usage`/`total_cost_usd` and OTEL `claude_code.token.usage{model,effort,query_source}` [79][120]; Codex `exec --json` events [58]; Antigravity envelope `usage` [69]; Qwen `result.stats` [72]; gateway responses' `usage` (+ OpenRouter `usage.cost`) [12]. Remaining-budget feed for the dashboard: no lane exposes it (table above), so compute **burn rate per lane per rolling 5-hour and 7-day window** from this table, mark the window red on the first `rate_limited` / "You've hit your session limit" event, and show the reset time the error message carries [137]. Claude's `/usage` breakdown (attribution by skill/subagent/MCP, loops rows) exists only in the TUI and is computed from local session history [137].

**(d) Empirical calibration against this server** — what the cost tables are missing:

Every cost table in this folder uses a synthetic 150k-in / 15k-out job and a different cache assumption (0% here, 60–90% elsewhere). This pass did not read `volumes/audit_log` (out of scope for the doc fix), so the calibration is left as a procedure with the owner-side inputs named: (1) `jq -r 'select(.type=="result") | [.usage.input_tokens, .usage.output_tokens, .usage.cache_read_input_tokens, .usage.cache_creation_input_tokens, .total_cost_usd] | @csv' volumes/audit_log/*.jsonl` over the last 30 days gives real jobs/month, tokens/job and cache-hit share = cache_read ÷ (input + cache_read + cache_creation); (2) the owner's Max tier (5x at $100 or 20x at $200) and any existing ChatGPT/Google/Copilot seats. The verdict flips on these numbers: at metered Sonnet 5 ($0.45/job uncached, $0.26 at 70% cache) the Max 20x subscription breaks even at ≈440 uncached or ≈770 cached jobs/month, Max 5x at ≈220 / ≈385 — below that, metered would be cheaper *if* the policy allowed an API key (it does not), so the practical reading is that the subscription is a fixed cost and the calibration decides only whether to add a second lane. One structural point favours the subscription for chained jobs: the prompt-cache lifetime is **one hour on a subscription and five minutes on an API key or once usage credits kick in** [137], so the 70–90% cache assumptions elsewhere are only reachable on the subscription lane.

**(e) Prompt-injection / sandbox posture for untrusted inputs** (Telegram text, fetched pages, MCP tool results — the server ingests all three), ranked best → worst for *unattended* runs:

| Rank | Lane | Posture | Caveat for `-p`/headless |
|---|---|---|---|
| 1 | Claude Code / SDK | isolated context window for web fetch; `curl`/`wget` not auto-approved; sandboxed bash with filesystem + network isolation; command-injection detection; fail-closed matching; auto-mode classifier | **trust verification is disabled under `-p`**, and `-p` without `--bare` runs project hooks/`.mcp.json` from the folder — so untrusted repos need `--bare` or a fixed workspace [144][79] |
| 2 | Codex CLI | Seatbelt `workspace-write`, approval `never` only inside the sandbox; `danger-full-access` is explicit | network default in `workspace-write` unverified [61] |
| 3 | Antigravity CLI | scoped allow rules; tools needing approval are soft-denied | soft-deny exits 0 — the runner must read stderr [69] |
| 4 | Qwen Code | run budgets (`--max-wall-time`, `--max-tool-calls`) but `--yolo` removes the sandbox | budgets bound damage, not injection [72] |
| 5 | Hermes agent | injection scan on inputs (per hermes doc) | no OS sandbox |
| 6 | goose / Cline / aider | no OS sandbox; Cline env allowlist | aider only edits + commits |
| 7 | opencode | AST permission filter with **documented bypasses** (`echo … \| bash`, `python3 -c`, base64) and a CORS-RCE history | never on untrusted input with `--auto` [48] |
| 8 | Perplexity MCP (auto-runs tools, no approval) / Grok Build (sandbox network isolation is a no-op on macOS, per grok-xai.md) | no gate between fetched text and tool execution | chat/summarise only |

Rule for the router: untrusted text reaches only ranks 1–3, wrapped in verbatim delimiters (the `verbatim_prompts` pattern claude.md records), with network-fetching tools denied for that job; tool results from rank ≥5 lanes are treated as untrusted when handed to another lane.

**(f) Host resource budget** (16 GB M4 beside Postgres/Redis; vendor numbers where they exist, otherwise marked estimate):

| Always-on daemon | RAM | Source / basis |
|---|---|---|
| Postgres + Redis (existing) | ~1 GB | existing deployment (estimate) |
| LiteLLM proxy, 1 worker | vendor floor **4 GiB**; ~1 GB observed-class at low traffic without prompt logging (estimate) | [143] |
| Ollama local model (≤9B Q4, 64k ctx) | ~6 GB while loaded; 0 when unloaded (`OLLAMA_KEEP_ALIVE` short) | [35] scaled; estimate |
| One `claude -p` / `codex exec` / `agy -p` session | 0.2–0.5 GB each, Node/Rust/Go processes (estimate) | — |
| OTEL collector (if adopted) | 0.1–0.3 GB (estimate; no vendor sizing) | [149] |
| OpenClaw gateway | "one always-on process for routing, control plane, and channel connections", Node 26; **RAM undocumented** | [141] |
| Hermes gateway | Python 3.11 + Node 26 service; **RAM undocumented** | [140] |
| Langfuse stack | 16 GiB minimum | [142] — excluded |
| Copilot CLI session state | undocumented | [138] |

Sum for the recommended shape (Postgres/Redis 1 + LiteLLM 1–4 + two concurrent CLI sessions 1 + collector 0.3) = 3.3–6.3 GB, leaving room for **one** loaded ≤9B local model or a third/fourth concurrent harness, not both; OpenClaw/Hermes go on only after measuring their RSS for a day (`ps -o rss=`), since neither vendor publishes it.

**(g) Reviewer independence** — is a cross-vendor second opinion actually uncorrelated? Two pieces of evidence say "less than assumed": Terminal-Bench 4.0 shows the *harness* carrying a large share of the result (GLM-5.3 reaches 41.8% inside Claude Code) [135], so a "different model, same harness" review shares the harness's blind spots; and the kimi/minimax/deepseek/qwen docs record Anthropic-distillation allegations plus a GPT-5.5 prefill-overlap experiment, so Chinese open-weight lanes may be **Claude-correlated on style and failure modes**. Working position: (1) for Claude-produced code, the second opinion is GPT-6 (Codex or gateway) or Grok — a different lab *and* a different harness; (2) treat Kimi/GLM/DeepSeek/Qwen as cheap *third* readers, not independence guarantees; (3) independence is measurable on this server — log findings per reviewer lane and compute pairwise overlap (Jaccard on normalised findings) over a month; a pair above ~0.7 is not a second opinion and should be replaced.

Third-party-serving permission (may the lane's output reach a non-owner viewer, e.g. the pickem league page or a shared project site?):

| Lane | Consumer/subscription wording | Verdict for shared surfaces |
|---|---|---|
| Claude Max OAuth | Consumer ToS: no automated access "except … via an Anthropic API Key or where we otherwise explicitly permit it"; no sharing the account or making it "available to anyone else"; no reselling; evaluation use "personal, non-commercial" [83] | Owner-driven jobs whose artifacts are published are not addressed; a surface where **other users submit prompts** is account-sharing/automation → API key (policy-blocked) |
| ChatGPT Plus / Codex login | auth docs: API keys "recommended default for automation"; usage bound to workspace permissions [60][106] | same rule (chatgpt-openai.md: "serves a second person → API key") |
| Antigravity sign-in | third-party tools banned outright [104] | never behind a shared surface |
| Alibaba Coding Plan | interactive-only, no backends [113] | never |
| Kimi Code | not stated [76] | assume personal |
| GitHub Copilot Pro/Pro+ | individual plans; terms live in GitHub ToS §J (not fetched) [122] | assume personal |
| Ollama Cloud / OpenRouter / Zen / LiteLLM / DeepSeek API | API-key products, no end-user restriction found | **usable** behind shared pages |
| LM Studio | EULA: no "service bureau … application service provider, or software-as-a-service" [34] | never as a backend for other users |
| Perplexity consumer / Mistral consumer / Z.ai plan | per their docs: "personal, non-commercial" / "business customers" / "on behalf of others" clauses (not re-fetched here) | never |

Tool churn (operational burden of the harness/CLI itself, September 2026):

| Lane | Cadence observed | Breaking-change signal | Burden |
|---|---|---|---|
| Codex CLI | 7 tags on 2026-09-23 alone across 0.155/0.157/0.158 alpha tracks; stable 0.156.1 [123] | none flagged in notes; model-picker/rate-limit defaults shift | high (pin a stable tag) |
| Claude Code | multiple patch releases/week; 2.1.280 default-model flip, `--bare` to become default for `-p` [79][107] | explicit changelog | medium (pin version + model) |
| Antigravity CLI | 10 releases / 13 days per gemini doc; changelog page 404 here | forced product migration June 2026 [63] | high |
| LiteLLM | weekly minor [19] | supply-chain incident [21][22] | high (hash-pin) |
| Ollama | ~weekly patch [30] | first-run sign-in prompt 0.34.2 | low |
| opencode | several/week [44] | Anthropic plugin removal [45] | medium |
| DeepSeek API | model IDs retired with silent redirect (2026-09-10/14) [124] | Harness "WILL BREAK" per deepseek.md | medium |
| goose / Cline / aider | rolling / rolling / slow | none observed | low |

Session resume: Claude `--continue/--resume <id or transcript path>` [79]; Codex `exec resume --last` [58]; Antigravity `--continue`, `--conversation ID` [69]; Qwen `--continue`, `--resume <id>` [72]; opencode `-c`, `-s <id>` [37]; goose `-r` [53]; Cline task id (page 404, unverified). Streaming: all of the above stream; OpenRouter/LiteLLM/Ollama/LM Studio stream SSE at the API level.

## 4. Cost

Consumer/subscription tiers (USD/month):

| Plan | Price | Includes / caps |
|---|---|---|
| Claude Pro / Max 5x / Max 20x | $20 ($17 annual) / $100 / $200 — the $200 for Max 20x is **confirmed in claude.md** (cross-doc); claude.com/pricing/max itself shows only "From $100" with "5x" and "20x more usage than Pro per 5-hour session" tiers [81][130] | Claude Code included; 5x / 20x Pro usage per 5-hour session; limits shared across surfaces; optional API-rate extra usage with explicit consent [81][82] |
| ChatGPT Free / Go / Plus / Pro / Business | $0 / $8 / $20 / from $100 (5x, 20x tiers) / $20–25 per user | Codex on every plan; Plus 350–3,000 GPT-6 Luna msgs per 5h; credits e.g. GPT-6 Sol 50 credits per 1M in, 250 per 1M out [59] |
| Ollama Free / Pro / Max / Team | $0 / $20 ($200/yr) / $100 / $500 | starter credits (amount not found — page says only "Starter usage credits included"; unverified as of 2026-09-24), 1 concurrent; $60 credits + 3 concurrent; $300 credits + 10 concurrent + early access; $1,000 shared. Credits don't roll over; off-peak discounts (50% on DeepSeek models, model-specific for others) outside 12:00–18:00 UTC on weekdays and all day on weekends [26][27] |
| Google AI Pro / Ultra (Antigravity) | $19.99 / from $99.99 [112] | legacy Gemini CLI quota-page rows: 1,500 / 2,000 req/day — still printed on the page but banner says the sign-in path was replaced 2026-06-18 [63][64]; Antigravity quotas qualitative only — Pro: five-hour refresh until weekly limit; Ultra: highest five-hour + weekly limits, third-party models; overage via purchased AI credits (see §3) [105] |
| GitHub Copilot Free / Pro / Pro+ (via opencode/goose) | $0 / $10 / $39 [122] | Pro 1,500 AI credits/mo (1,000 base + 500 flex), Pro+ 7,000 (3,900 + 3,100), "curated" vs "premium" models; individual-plan terms sit in GitHub ToS §J (not fetched); device-flow login accepted by opencode and goose [38][54] |
| Kimi Code (Andante/Moderato/Allegretto/Plus/Pro) | Still not on any fetchable page after a third attempt on 2026-09-24 (kimi.com/code/docs/en/membership-benefits → 404, /code/pricing → 404, /code/docs/en/faq → 404, kimi.com/membership/pricing renders only a feature grid — "Upgrade to Kimi Membership to unlock faster models, higher concurrency" — with no price column even through a text mirror [148]); **defer to kimi.md for the tier prices it recorded** — this doc no longer asserts "Not found" as a finding, only that Moonshot does not publish them on a crawlable page | tiers gate K3 (1M ctx, low/high/max effort) vs K2.8 Preview vs K2.7 Code HighSpeed (260 tok/s); third-party tools take a manually configured API key; subscription-vs-metered status of that key undocumented (see §3) [76] |
| Alibaba Coding Plan | Pro $50/month (Lite tier closed to new subscriptions March 2026) [113] | qwen3.5/3.6/3.7-plus, qwen3-coder, GLM, Kimi, MiniMax via `coding.dashscope.aliyuncs.com/v1` [71]; **interactive-only** — automated scripts/backends prohibited, 6,000 req/5 h, 45,000/week, 90,000/month [113] |
| OpenRouter | no plan; 5.5% Stripe fee ($0.80 min), 5% crypto; credits may expire after 1 year; optional 1% discount for opting into prompt logging [1] | free models: 50 req/day, or 1,000/day after $10 lifetime purchase [2] |
| OpenCode Zen | pay-as-you-go, auto-reload $20 when < $5, card fee 4.4% + $0.30 passed through [40] | rotating free models (Big Pickle, Space Bunny Free, MiMo, Ling 3.0, Nemotron, Muse Spark 1.3 "Contributor Free" = Meta may train on prompts — unverified as of 2026-09-24) [40] |
| LiteLLM / opencode / goose / Cline / aider / Codex CLI / Qwen Code / Kimi CLI software | $0 (OSS) | LiteLLM enterprise (SSO, SLAs) is paid [20]; Cline Enterprise custom [56] |
| LM Studio | $0; EULA permits "personal and/or internal business purposes", forbids "service bureau… application service provider, or software-as-a-service" use [34] | a single-tenant personal server is internal use; do not resell |

API prices, $/1M tokens (input / output / cache read unless noted):

| Model (ID) | Direct | Via OpenRouter (cheapest provider → first-party) |
|---|---|---|
| Claude Fable 5.1 | 10 / 50 / 0.25; batch 5 / 25 [80] | not fetched |
| Claude Opus 5.5 | 4 / 20 / 0.20; batch 2 / 10 [80] | — |
| Claude Opus 5 | 5 / 25 / 0.50; batch 2.5 / 12.5 [80] | — |
| Claude Sonnet 5 (`anthropic/claude-sonnet-5-20260630`) | 2 / 10 / 0.20 (introductory price made permanent) [80] | 2 / 10 / 0.20, cache write 2.5 (Anthropic, AWS, Azure, Vertex; Bedrock regional 2.2 / 11) [9] |
| Claude Haiku 4.5 | 1 / 5 / 0.10; batch 0.5 / 2.5 [80] | Zen: 1 / 5 [40] |
| GPT-6 Astra (`openai/gpt-6-astra`) | — | Flex 5 / 25 / 0.50; Standard 10 / 50 / 1; Fast 20 / 100 / 2 [12] |
| GPT-6 Sol / GPT-6 Luna (dated snapshots `openai/gpt-6-sol-20260922`, `openai/gpt-6-luna-20260922`; 1,050,000 ctx) | — | 2 / 10 (batch 1 / 5); 0.10 / 0.50 (batch 0.05 / 0.25) per the models page [15]; the endpoints API lists the Luna OpenAI standard tier at 0.05 / 0.25 with a 272k+ high-volume tier at 0.10 / 0.375 [109][110] — treat Luna as ≤0.10 / 0.50 |
| Grok 4.7 (`x-ai/grok-4.7`) | 2.00 / 6.00 / 0.50 (<200k prompt); 4.00 / 12.00 / 1.00 (≥200k) at docs.x.ai [125] | 1.60 / 4.80 / 0.40 on both `xai` and `xai/zdr` endpoints, doubling ≥200k prompt tokens; `xai/priority` and `xai/zdr/priority` 3.20 / 9.60 / 0.80; 500,000 ctx; web search $0.005/request [108]. The 20% gap is explained, not mysterious: OpenRouter's FAQ states it "passes through the pricing of the underlying providers … there is no markup on inference pricing" [1], so 1.60 / 4.80 is the price **xAI sets for the OpenRouter channel** (grok.md reaches the same conclusion: an xAI-set channel price, not an OpenRouter discount). Treat it as xAI's to change at will and still log `usage.cost` per call |
| Claude Managed Agents runtime | $0.08 per session-hour while `running` (idle time free) on top of model tokens; no Batch discount; not on partner clouds [80] | n/a |
| Gemini 3.8 Flash (`google/gemini-3.8-flash`) | 0.75 / 3.75 through 2026-12-31 (then 1.50 / 7.50); batch 0.375 / 1.875; cache 0.075 [84] | Flex 0.375 / 1.875 / 0.0375; Standard 0.75 / 3.75; Priority 1.35 / 6.75 [13] |
| Gemini 3.5 Flash-Lite / 3.1 Pro Preview | 0.30 / 2.50; 2.00 / 12.00 (≤200k) [84] | — |
| DeepSeek V4.1 Flash (`deepseek-flash`; legacy `deepseek-v4-flash` retired 2026-09-10 and silently redirected to V4.1-Flash, `deepseek-v4-pro` redirected from 2026-09-14 [124]) | 0.30 / 1.20 peak, half off-peak; cache hit 0.006 [85] | OpenRouter's `deepseek/deepseek-v4-flash` still resolves — but as **"DeepSeek V4 Flash 0423"**, the older weights on 15 third-party hosts (StreamLake 0.0855 / 0.171, Baidu 0.087 / 0.174 … Azure 0.21 / 0.56) [10]; it is not the V4.1 model DeepSeek now serves under that name, so first-party and OpenRouter answers will diverge |
| DeepSeek V4 Pro (`deepseek-v4-pro`) | 1.32 / 3.96 peak; 0.66 / 1.98 off-peak [85] | Ollama Cloud 1.32 / 3.96 / 0.044 [27] |
| Kimi K3 (`kimi-k3`) | 3 / 15 / 0.30 (Moonshot; 1,048,576 ctx) [77] | 1.40 / 10.75 (InferenceNet fp4) … 3 / 15 (Moonshot mxfp4, Fireworks, Together) … 6 / 22.5 (Morph Fast) [11]; Ollama Cloud 3 / 15 / 0.30 [27] |
| Kimi K2.7 Code / K2.6 | 0.95 / 4.00, cache 0.19; 0.95 / 4.00, cache 0.16 [77] | — |
| Qwen3.8 Max (`qwen/qwen3.8-max-0902`) | — | 2 / 6 / 0.25 (Alibaba, 1M ctx) [14] |
| GLM 5.3 | — | Ollama Cloud 1.40 / 4.40 / 0.26 [27]; Zen GLM 5.3 1.40 / 4.40 / 0.26 and GLM 5.3 Flash 0.15 / 0.50 [40]; OpenRouter `z-ai/glm-5.3-prime` 2.80 / 8.80 [15] |
| gpt-oss:120b / gemma4 | — | Ollama Cloud 0.15 / 0.60 / 0.014; 0.14 / 0.40 / 0.05 [27] |
| Local (Ollama/LM Studio on M4 16 GB) | $0 marginal; Gemma 4 26B-A4B needs ~21 GB at 48k ctx on a 48 GB M4 Pro at 51 tok/s [35] — **does not fit 16 GB**; realistic local set is ≤9B-class (`qwen3.5:9b`, `gemma4:12b` quantized) | — |

Monthly cost to run 10 / 100 / 1,000 agent jobs (150k input + 15k output tokens per job; no caching unless stated; prices above; "sub" = subscription):

| Path | $/job | 10 jobs | 100 jobs | 1,000 jobs | Notes |
|---|---|---|---|---|---|
| (a) Claude Max 20x sub (current) | 0 marginal | $200 (confirmed in claude.md) | $200 | $200 + overflow | 1,000 jobs ≈ 165M tokens/mo ≈ 5.5M/day; Anthropic publishes no token figure for Max, so whether this fits is **unverified**; overflow bills at API rates with consent [81][82] |
| (a) Ollama Pro $20 sub, `gpt-oss:120b` | 0.0315 | $20 | $20 | $20 + $11.5 overage | $60 credits cover ~1,900 jobs at this model [26][27] |
| (a) Ollama Pro $20 sub, `deepseek-v4-pro` | 0.257 | $20 | $20 (≈$26 credits used) | $20 + ~$197 overage or Max $100 covers 1,167 jobs | off-peak halves it [27] |
| (a) Ollama Max $100 sub, `kimi-k3` | 0.675 | $100 | $100 | $100 + ~$375 overage | 10 concurrent [26] |
| (a) ChatGPT Plus $20 via Codex login | 0 marginal | $20 | $20 | not the documented default for automation (API key recommended; an account-auth CI/CD pattern is documented for trusted private runners) [60][106] | Plus caps 350–3,000 Luna msgs / 5h [59] |
| (b) API Claude Sonnet 5 | 0.45 (0.26 with 70% cache hits) | $4.50 | $45 | $450 | batch 50% off for non-interactive research [80] |
| (b) API Claude Opus 5.5 / Fable 5.1 | 0.90 / 2.25 | $9 / $22.50 | $90 / $225 | $900 / $2,250 | [80] |
| (b) API Claude Haiku 4.5 | 0.225 | $2.25 | $22.50 | $225 | classification/routing tier [80] |
| (b) OpenRouter GPT-6 Astra Flex / Standard | 1.125 / 2.25 | $11 / $22.50 | $113 / $225 | $1,125 / $2,250 | +5.5% credit fee [1][12] |
| (b) OpenRouter GPT-6 Sol / Luna | 0.45 / 0.0225 | $4.50 / $0.23 | $45 / $2.25 | $450 / $22.50 | [15] |
| (b) OpenRouter/Google Gemini 3.8 Flash Flex | 0.084 | $0.84 | $8.40 | $84 | Standard 0.169 [13] |
| (b) OpenRouter DeepSeek V4 Flash (Baidu) | 0.0157 | $0.16 | $1.57 | $15.70 | quality varies ±20 pts by host [17]; direct DeepSeek peak 0.063 [85] |
| (b) OpenRouter Kimi K3 (first-party) | 0.675 | $6.75 | $67.50 | $675 | cheapest fp4 host 0.37 [11] |
| (b) OpenRouter Qwen3.8 Max | 0.39 | $3.90 | $39 | $390 | [14] |
| (b) OpenRouter Grok 4.7 (xAI) | 0.312 | $3.12 | $31.20 | $312 | 500k ctx; only one host, no provider variance [108] |
| (b) Claude Managed Agents, Sonnet 5, 1 h running/job | 0.53 | $5.30 | $53 | $530 | 0.45 tokens + $0.08 runtime; API key required (policy conflict) [80][100] |

Assumptions: prices as fetched 2026-09-24; OpenRouter fee applied at purchase time, not per request; Ollama "job" cost uses on-peak rates; no tool-overhead tokens added (Claude tool-use system prompt adds 286–675 tokens/request [80]; Claude Code harness adds ~33k tokens before the prompt vs ~7k for opencode per the July 2026 systima study [47], so real Claude-Code jobs cost more than the raw per-job number).

## 5. Strengths & weaknesses per reviews

Benchmarks: Terminal-Bench 4.0 (2026-08-28) is the reference for harness+model pairs. The rows are client-rendered on tbench.ai, but a text mirror of the 4.0 leaderboard (the same route chatgpt-openai.md used) returned them on 2026-09-24 [135]:

| Rank | Model | Agent (harness) | Resolution rate | Date | Run cost |
|---|---|---|---|---|---|
| 1 | GPT-6 Astra | Codex | 58.2% ± 2.8 | 2026-09-03 | $3.3k |
| 2 | Claude Fable 5.1 | Claude Code | 57.9% ± 3.8 | 2026-09-01 | $6.2k |
| 3 | Claude Opus 5 | Claude Code | 53.9% ± 3.2 | 2026-07-24 | $6.1k |
| 4 | Claude Fable 5 | Claude Code | 44.5% ± 3.8 | 2026-06-09 | $7.3k |
| 5 | GLM-5.3 | Claude Code | 41.8% ± 3.2 | 2026-08-14 | $2.7k |
| 6 | Grok 4.7 | Grok Build | 37.6% ± 3.5 | 2026-09-21 | $3.7k |
| 7 | GPT-5.6 Sol | Codex | 37.3% ± 3.8 | 2026-06-26 | $2.5k |
| 8 | Claude Opus 4.8 | Claude Code | 23.6% ± 3.6 | 2026-05-28 | $6.5k |
| 9 | GPT-5.6 Terra | Codex | 21.5% ± 3.3 | 2026-06-26 | $1.7k |
| 10 | Grok 4.6 | Grok Build | 20.3% ± 3.1 | 2026-08-12 | $3.6k |
| 11 | Gemini 3.8 Flash | mini-SWE-agent | 19.1% ± 3.4 | 2026-09-02 | $1.8k |
| 12 | GPT-5.6 Luna | Codex | 17.3% ± 2.8 | 2026-06-26 | $0.3k |
| 13 | Grok 4.5 | Grok Build | 12.4% ± 2.6 | 2026-07-16 | $2.1k |
| 13 | Claude Sonnet 5 | Claude Code | 12.4% ± 3.1 | 2026-06-30 | $9.6k |
| 15 | Gemini 3.7 Flash | mini-SWE-agent | 11.2% ± 2.4 | 2026-08-13 | $1.3k |

Readings: (i) top-2 are within each other's CI (Codex+Astra vs Claude Code+Fable 5.1), so harness choice for coding is a coin-flip on capability and a 2x difference on run cost; (ii) Opus 5.5 (2026-09-22) is not yet listed; (iii) Sonnet 5 at 12.4% with the highest run cost is an anomaly worth treating as a submission artefact (effort/config) rather than a model verdict — do not route coding jobs on it; (iv) GLM-5.3 inside the Claude Code harness scores 41.8%, i.e. the harness carries a large share of the result, which matters for the reviewer-independence question in §3; (v) no Antigravity/Gemini-CLI, Kimi, DeepSeek or Qwen harness row appears in the top 15 [135]. Earlier attempts (tbench.ai/leaderboard, /2.0, /4.0 direct, /benchmarks, the leaderboard GitHub repo) returned only headers [94]. Aider's polyglot leaderboard (225 Exercism tasks) is stale (2025-11-20): gpt-5 (high) 88.0% at $29.08, gpt-5 (medium) 86.7% at $17.69, o3-pro 84.9% at $146.32 [50]. OpenRouter's usage rankings (through 2026-09-23) are the best live proxy for revealed preference: Claude Opus 5.5 57.6, Claude Fable 5.1 53.4, Qwen3.8 Max 53.4, GPT-6 Astra 52.7, Claude Opus 5 50.8, Claude Fable 5 49.6, GPT-6 Sol 47.5, GPT-5.6 Sol 47.0, Grok 4.7 46.4, MiMo-V2.6-Pro 46.3 [8]. LMArena, SWE-bench Verified, Artificial Analysis, GPQA, HLE scores belong to models not harnesses; see the per-vendor docs in this folder.

Harness-level evidence and sentiment (attributed):

- **Claude Code vs opencode token overhead** (systima.ai, July 2026, n=3–5, Sonnet 4.5 + Fable 5): Claude Code sends ~33k tokens before the user prompt vs ~7k for opencode (4.7x; 3.3x on Fable); Claude Code rewrote cache prefixes mid-session (54x more cache writes); both completed all tasks; a 72 KB instruction file adds ~20k tokens/request, five MCP servers add 5–7k, subagent fan-out 4.2x [47]. HN: 706 points / 395 comments [88].
- **opencode**: 1,274-point HN launch thread (2026-03-20) [88]; "Annoying and alarming things about OpenCode" (420 points, 2026-07-20) documents remote-by-default model fetch from models.dev, CVE-2026-22812 RCE via default HTTP server, bash-permission bypasses, persisted prefix approvals, security issues closed by stale bot [48]; unauthenticated RCE write-up 432 points (2026-01-11) [88]; Anthropic legal removal PR had 548 downvotes vs 19 upvotes and a maintainer asking "what's the border between normal enforcement of product boundaries and a hostile move against third-party harnesses" [45].
- **OpenRouter**: "So you want to use OpenRouter?" (766 points, 2026-09-07/09): same weights score 90% at first-party vs 75% at DigitalOcean for DeepSeek V4 Flash; some hosts ignore `reasoning.effort`; quantization labels don't predict quality; raw `<use_skills>` markup leaks; HTTP 200 with null content (StreamLake 92% of empty completions in July); IP-based 429s from production infra (Venice, Novita); pinning three "reliable" providers failed within two weeks — "the contract isn't per model, it's per provider" [17]. Stripe acquisition (964 points) and Series B (460 points) dominate the rest of HN coverage [92]. Free-model churn: the `/api/v1/models` list on 2026-09-24 carries 24 zero-price entries, 22 of them `:free` variants (e.g. `qwen/qwen3.8-27b:free`, `z-ai/glm-5.2:free`, `google/gemma-4-26b-a4b-it:free`, `google/gemma-4-31b-it:free`, `nvidia/nemotron-3-ultra-550b-a55b:free`, `nvidia/nemotron-3-super-120b-a12b:free`, `openrouter/free`) plus the stealth Space Bunny Alpha [111]; the client-rendered models page under-reports this [7]. Free variants stay capped at 20 req/min and 50 or 1,000 req/day [2].
- **LiteLLM**: PyPI versions 1.82.7 and 1.82.8 were uploaded directly by an attacker who controlled maintainer account `krrishdholakia`; 1.82.8 shipped a `litellm_init.pth` credential stealer (SSH keys, cloud creds, env vars, wallets) exfiltrating to `models.litellm.cloud`; BerriAI deleted packages, rotated accounts, paused releases, engaged Mandiant (2026-03-24) [21][22]; HN 938 points; Mercor breach attributed to it (TechCrunch 2026-03-31) [89]. "Litelm: LiteLLM without the bloat" (177 points, 2026-09-11) reflects a persistent code-size complaint [24]. Strength: unmatched feature surface (virtual keys, budgets, MCP gateway with OAuth, A2A, auto-router, batch billing) shipping weekly [19].
- **Ollama**: cloud pricing and MLX progress are uncontroversial; one HN report of "crosstalk" (prompts paired with wrong answers) on cloud DeepSeek (2026-03-11, 3 points) [91]; the Anthropic-compatible endpoint lets Claude Code drive Ollama models with `ANTHROPIC_BASE_URL=http://localhost:11434` but lacks `tool_choice`, prompt caching, batches, PDFs [29]. Release notes newer than the narrative above: 0.34.0 (2026-09-05) "Ollama models can now be used directly in ChatGPT Desktop"; 0.34.2 (2026-09-15) "Added first-run setup when running `ollama`, with options to sign in or continue locally" — a headless install should expect that first-run prompt [30].
- **LM Studio**: "Running Gemma 4 locally with LM Studio's new headless CLI and Claude Code" (407 points, 2026-04-05) [90][35]; Bionic agent launch 331 points [90]. Weakness for this server: EULA no-SaaS clause and 16 GB RAM.
- **Codex CLI**: strongest sandbox story on macOS (Seatbelt) and a real app-server protocol [58][61]; HN: skills adoption (587 points, 2025-12-12), running Gemma 4 locally in Codex (285 points, 2026-04-12); an "access temporarily limited for potentially suspicious activity related to cybersecurity" auto-block was reported 2026-03-03 (HN report; unverified as of 2026-09-24) [88] — relevant for a security-flavoured research loop.
- **Gemini CLI → Antigravity**: the forced June 2026 migration (406 points, 209 comments) [63][88]; earlier "hallucinate and delete my files" incident (304 points, 2025-07) [88]; Antigravity's headless mode is well specified but proprietary; its quotas are documented only qualitatively (five-hour + weekly windows, no request counts) [105] and its Terms ban third-party tools on Antigravity OAuth [104].
- **goose**: moved to the Linux Foundation's Agentic AI Foundation (README confirms AAIF membership; the 2026-05 date is unverified as of 2026-09-24) [52]; HN launch 249 points (2025-01) [88]; built-in cron scheduler (no longer unique: Claude Code has Routines/Desktop scheduled tasks [96][97]) and ACP providers [53][54]; light HN discussion since.
- **Cline**: free-for-individuals BYOK, NDJSON headless; HN notes a compromised postinstall incident (2026-02-18, 3 points) and a "founder stole my code" dispute (22 points, 2025-02) [93].
- **aider**: still active (13k commits) but no 2026 HN thread; Python API explicitly unsupported [49][51].
- **Qwen Code / Kimi Code**: zero HN story hits; Qwen's free OAuth ended 2026-04-15 [71]; Kimi CLI was archived in favour of `kimi-code` [74].

Reliability, one window and one source (StatusGator, 2026-08-25 → 2026-09-24, plus vendor pages where StatusGator lacked a page):

| Lane | Incidents in window | Source | Priority / SLA tier sold |
|---|---|---|---|
| Anthropic (Claude Code, API) | 5 listed: Sep 22 elevated errors multiple models; Sep 16 Google Play subs; Sep 15 Mythos 5.1 / Fable 5.1 spikes; Sep 11–14 Mythos 5.1 / Fable 5.1 elevated errors (3+ days) | [126] | none numeric (Priority Tier is API-key only) |
| OpenAI (Codex, API) | ≥3 Codex/API incidents on status.openai.com: Sep 13 Codex GitHub review failures, Sep 14 Codex + ChatGPT Work errors, Sep 17 API elevated errors; StatusGator shows 5 in the last week and "78 user-submitted reports" in 24 h | [127][128] | "Fast" processing tier (pricing only, no SLA) |
| OpenRouter | 1 (Sep 23 sign-in/sign-up, 25 min); 3 in 90 days (Aug 28 20 h 15 m minor, Jul 23 15 min major) | [129] | none; per-provider variance is the real risk [17] |
| Ollama Cloud | no status page found (`status.ollama.com` does not resolve) | — | none |
| Google (Antigravity) | StatusGator page not found here | — | none |
| xAI | not fetched here; grok-xai.md: priority tier, no SLA | — | priority (no SLA) |
| MiniMax / Mistral | per their docs: priority tiers (Mistral Priority preview quotes uptime SLA) | — | priority |
| Kimi / Z.ai / Meta / Qwen | no status page found | — | none |

Caveat: StatusGator counts are heterogeneous (user reports plus vendor feeds) and the Anthropic 90-day view is a chart, not a count; the comparison is indicative only. Nobody in this table sells a numeric SLA on a consumer or prepaid lane.

Interactive-surface latency (Telegram round trip; target ≤5 s to first token, streaming edits thereafter). Primary-lane numbers, previously "unmeasured" in every doc, now have a source: OpenRouter's provider telemetry for Claude Sonnet 5 shows best-provider TTFT **1.48 s** at up to 75 tok/s (trailing-window measurement, default effort) [145]; Claude Opus 5.5's fastest provider (Azure) is **≈3.16 s** TTFT [146]; the same model at *max* effort measures 150 s TTFT on Artificial Analysis (thinking time counted) [147], so the Telegram lane must pin `effort=low|medium` and the API-level figure applies only when the request goes straight to `/v1/messages` — through `claude -p` the ~33k-token harness prefix adds a cache-miss re-read on the first turn [47]. These are API-endpoint measurements; Max OAuth hits the same endpoint, so treat them as the lane's floor, and replace crosscut-finance's unsourced "sub-2 s typical" with "1.5 s (Sonnet 5, OpenRouter-measured) / 3.2 s (Opus 5.5)". The other lanes' figures are the per-vendor docs' TTFT numbers plus the harness overhead in §5: Kimi K3 3.84 s, GLM-5.3 3.4 s, Gemini 3.8 Flash 14 s at 297 tok/s, GPT-6 Astra up to 352 s at max effort — the last two are unusable as chat replies. Ratings: **chat-suitable** — Haiku 4.5, GPT-6 Luna, `gpt-oss:120b-cloud`, local ≤9B (sub-second TTFT locally, but quality-limited), DeepSeek V4.1 Flash; **chat-suitable at low/medium effort via the API endpoint** — Sonnet 5 (1.48 s) and, marginally, Opus 5.5 (3.16 s) [145][146]; **borderline** — Kimi K3, GLM-5.3, Sonnet/Opus through Claude Code `-p` (≈33k harness prefix per request [47] adds seconds before the first token); **not chat-suitable** — Astra/max-effort reasoning, Gemini 3.8 Flash at 14 s TTFT, any Routines/cloud-session path (≥1-h cron, minutes to start) [96]. Rule: the Telegram surface should call the gateway (chat completions, streaming) and hand off to a harness job asynchronously, never block the reply on a harness.

## 6. Finance / trading relevance

None of these layers provides market data. What they do provide:

- **Real-time data access**: only through tools. Claude SDK ships WebSearch/WebFetch (Anthropic web search $10 per 1,000 searches, web fetch free beyond tokens) [80]; Gemini API includes "5,000 free search requests per month (shared across all Gemini 3.x models), then $14 per 1,000 requests" [84] — this is the only "free search" lever the §7 recipe relies on, and above 5,000/month it costs more than Anthropic's $10 per 1,000 [80]; opencode/goose/Codex/Antigravity/Qwen expose a `webfetch`/shell tool and rely on MCP for data connectors [42][53][58].
- **Connectors**: MCP is the only portable mechanism; LiteLLM's MCP gateway can front Alpaca/Tradier/Finnhub MCP servers with OAuth and per-key access groups so every harness sees the same toolset [19]. Ollama Cloud and OpenRouter have no finance products.
- **Sentiment sources**: nothing built in; the HN Algolia API and Reddit JSON are fetchable by any harness with webfetch.
- **Finance-specific products / restrictions**: none of the aggregators publish finance restrictions; OpenAI's Codex ToS-level "not for automation" note applies to ChatGPT login only [60]; Anthropic consumer terms' automation clause applies to non-API access [83]. Data-policy relevance: OpenRouter ZDR can be enforced per request `"provider": {"zdr": true}` or per model group in account settings, and only tightens [6]; Ollama Cloud "never logged or trained on" [27]; Zen zero-retention for most providers [40]; LM Studio Bionic ZDR [36]. For paper-trading research (no order path on the server) the practical constraint is reproducibility: OpenRouter's provider variance [17] argues for pinning `provider.order` and logging the returned `model`/provider on every call.

## 7. Integration recipe for our server

Recommendation: keep the Claude Agent SDK as the primary executor and add a **two-layer sidecar**: (1) a self-hosted gateway for chat-style calls (routing, classification, adversarial second opinions) and (2) a thin "harness adapter" that launches vendor CLIs headlessly and normalises their NDJSON into the existing audit log. Do not adopt opencode as the core executor (Claude-subscription cut-off [38][45], sandbox bypasses [48]); do not adopt LiteLLM without pinning + hash-verifying wheels [22].

Layer 1 — gateway (chat completions). Hosted alternatives to a self-run LiteLLM now exist with zero markup: **Vercel AI Gateway** (OpenAI + Anthropic Messages endpoints, BYOK at no fee, per-key budgets, provider ordering, OTLP trace drains) and **Cloudflare AI Gateway** (caching, rate limiting, fallback routing, free core tier; 5% only on Unified Billing credits) [131]–[134] — either removes the LiteLLM daemon and its supply-chain exposure from the box at the cost of a third party seeing every prompt (Vercel ZDR is per-request free on Pro; Cloudflare's data policy was not evaluated here). Keep LiteLLM only if the MCP gateway or local-network-only routing is needed. Prefer **Ollama Cloud Pro ($20, $60 credits)** for open-weight models over OpenRouter free tiers (22 `:free` variants exist [111], but they are capped at 50/1,000 req/day and 20 req/min with no SLA [2]); use **OpenRouter** with ≥$10 credits only for models Ollama doesn't host (GPT-6, Gemini, Grok) and pin providers. Route everything through a local LiteLLM proxy (pinned, e.g. `litellm==1.102.1`, installed with `--require-hashes`) so the server has one `OPENAI_BASE_URL` and one Anthropic `/v1/messages` URL, virtual keys per job class, spend caps, and a single log sink:

```yaml
# volumes/litellm/config.yaml (sketch)
model_list:
  - model_name: cheap-router      # classification/routing — Ollama Cloud has NO structured outputs [116]; use tool-calling for JSON, or fall back to Haiku 4.5 / an OpenRouter host with `structured_outputs`
    litellm_params: {model: ollama_chat/gpt-oss:120b-cloud, api_base: https://ollama.com, api_key: os.environ/OLLAMA_API_KEY}
  - model_name: cheap-router-json # same job when a JSON Schema must be enforced
    litellm_params: {model: openrouter/openai/gpt-6-luna, api_key: os.environ/OPENROUTER_API_KEY,
                     extra_body: {provider: {order: ["OpenAI"], require_parameters: true}}}
  - model_name: second-opinion    # adversarial review
    litellm_params: {model: openrouter/openai/gpt-6-astra, api_key: os.environ/OPENROUTER_API_KEY,
                     extra_body: {provider: {order: ["OpenAI"], zdr: true}}}
  - model_name: bulk-research     # deepseek-v4-flash was retired 2026-09-10 [124]; go first-party V4.1 and keep OpenRouter's old-weights ID as an explicit, separately named fallback
    litellm_params: {model: deepseek/deepseek-flash, api_key: os.environ/DEEPSEEK_API_KEY}
  - model_name: bulk-research-legacy-v4   # "DeepSeek V4 Flash 0423" weights on third-party hosts — different model, log `model`+provider
    litellm_params: {model: openrouter/deepseek/deepseek-v4-flash, api_key: os.environ/OPENROUTER_API_KEY,
                     extra_body: {provider: {order: ["Baidu", "StreamLake"], allow_fallbacks: true}}}
litellm_settings: {success_callback: ["langfuse"], max_budget: 60, budget_duration: "30d"}
```

Auth: API keys in `.env` (never `ANTHROPIC_API_KEY`, per policy). Cost path: Ollama Pro sub + OpenRouter prepaid credits (5.5% fee) [1][26].

Layer 2 — harness adapter (tool-using jobs). One Python wrapper per CLI, all producing the same event schema (`job_id, harness, model, event_type, tool_name, args_hash, cost_usd, session_id`). Commands that are documented today:

```bash
# Claude (benchmark; owner's Max login, first-party — permitted path)
claude -p "$PROMPT" --output-format stream-json --verbose --include-partial-messages \
  --permission-mode acceptEdits --permission-prompts none --allowedTools "Bash(git *),Read,Edit" --json-schema "$SCHEMA"   # [79]
# OpenAI Codex — auth per the set-wide Gray/Yes* position (chatgpt-openai §3, crosscut-benchmarks §7): ChatGPT-login account auth IS a documented path for trusted private runners (one ~/.codex/auth.json per serialized job stream, auto-refresh, seed only if missing), while OpenAI still calls API keys the "recommended default for automation" [60][106]
codex exec "$PROMPT" --json -o /tmp/last.md --sandbox workspace-write --ask-for-approval never -m gpt-6-sol -C "$WORKDIR"   # [58][60][61]
# Google Antigravity (cached login from a one-time interactive `agy`; headless is documented)
agy -p "$PROMPT" --output-format stream-json --model gemini-3.8-flash-high --effort high --print-timeout 20m            # [69]
# Qwen Code with any OpenAI-compatible key (e.g. LiteLLM proxy) — NOT the Coding Plan key, which is interactive-only [113]; tightest run budgets of the group
OPENAI_BASE_URL=http://127.0.0.1:4000/v1 OPENAI_API_KEY=$LITELLM_KEY QWEN_CODE_UNATTENDED_RETRY=1 \
  qwen -p "$PROMPT" --output-format stream-json --approval-mode auto-edit --max-wall-time 15m --max-tool-calls 200   # [71][72]
# goose as recipe/cron orchestrator that can front Claude Code / Codex via ACP (Claude Code Routines cover the cloud-cron case natively [96])
goose run --recipe recipes/atlas-research.yaml --params symbol=SPY --output-format stream-json --no-session --max-turns 60 -q   # [53][54]
# opencode only with non-Anthropic providers (ChatGPT/Copilot OAuth or API keys), attached to a long-lived server
opencode serve --port 4096 & ; opencode run --attach http://127.0.0.1:4096 --format json --auto -m openai/gpt-6-sol "$PROMPT"   # [37][38][39]
```

Minimal Python sketch for the adapter (stdlib only):

```python
import json, subprocess
def run_harness(cmd: list[str], job_id: str, sink):
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True)
    for line in p.stdout:                       # NDJSON from claude/codex/agy/qwen/goose/cline
        try: ev = json.loads(line)
        except ValueError: continue
        sink.append({"job_id": job_id, "harness": cmd[0], **ev})   # volumes/audit_log/<job>.jsonl
    return p.wait()                             # 0 ok; claude 143 on SIGTERM; agy 1/2; qwen 53/55
```

Task-class fit: research → Claude SDK (WebSearch) or Antigravity/Gemini (free grounding) with DeepSeek V4 Flash for bulk summarisation; coding → Claude SDK first, Codex CLI (`gpt-6-sol`) second; code review → Codex or GPT-6 Astra via gateway for a non-Claude second opinion; chat (Telegram) → cheap-router on Ollama Cloud; classification/routing → `gpt-oss:120b-cloud` via tool-calling (no JSON-schema mode on Ollama Cloud [116]) or Haiku 4.5 / GPT-6 Luna when a schema must be enforced; local Ollama (≤9B) via the Anthropic endpoint is acceptable for the same class [29][115]; adversarial review → deliberately different family (GPT-6 Astra or Kimi K3); trading research (paper) → Claude SDK + MCP data servers, DeepSeek/Kimi for cross-checks with provider pinned and `model` field logged.

Version notes (Claude Code, September 2026, from the changelog [107]): 2.1.280 (2026-09-22) added Claude Opus 5.5 (`claude-opus-5-5`, 1M context) as the default Opus model and changed the default on Pro and Team Standard plans from Sonnet to Opus — pin the model explicitly in every job so a default flip cannot change cost; 2.1.278 made auto mode default to the server-side classifier for Claude API and Enterprise users (no billed overhead; the local fallback warns on billing); 2.1.277 reads `AGENTS.md` when a project has no `CLAUDE.md`; 2.1.276 fixed every request failing with `400 … Input tag 'advisor_20260301'` when `ANTHROPIC_BASE_URL` points at a proxy or gateway (a 2.1.275 regression) — directly relevant to the LiteLLM-fronted path above.

Gotchas: Claude `-p` without `--bare` runs project hooks and `.mcp.json` from untrusted folders and shows no trust dialog [79]; `--bare` cannot use the subscription login [79]; Claude Code disables tool search when `ANTHROPIC_BASE_URL` is not first-party, so MCP schemas eat context [23]; Ollama's Anthropic endpoint lacks `tool_choice`/caching [29]; OpenRouter returns 402 on negative balance even for free models [2]; opencode's default server has had CORS RCE and bash-filter bypasses — bind to 127.0.0.1 and set `OPENCODE_SERVER_PASSWORD` [39][48]; LM Studio's EULA forbids SaaS-style use and Gemma 4 26B does not fit 16 GB [34][35]; Codex may auto-limit accounts for "cybersecurity"-looking activity (single HN report, unverified as of 2026-09-24) [88]; Qwen OAuth free tier is gone [71]; Antigravity quotas are only qualitative (five-hour/weekly windows, no numbers) [105], Antigravity OAuth must never be driven by a third-party tool (ToS breach, account-level suspension) [104], and the Gemini CLI free tier is dead [63][64]; Claude Code 2.1.276 fixed a 2.1.275 regression where every request failed with `400 … Input tag 'advisor_20260301'` when `ANTHROPIC_BASE_URL` pointed at a proxy/gateway — pin ≥2.1.276 on the LiteLLM-fronted path [107]; Claude Managed Agents and the OpenAI Agents API are API-key-only hosted harnesses, so under the no-`ANTHROPIC_API_KEY` policy neither is usable here without an explicit owner decision [100][103].

## 8. Verdict

1. The best "one interface, many models" for this server is **Claude Agent SDK as executor + a pinned LiteLLM proxy as the single gateway + ACP/NDJSON adapters for Codex CLI, Antigravity CLI and Qwen Code**, with goose as the optional recipe/cron layer that can front Claude Code and Codex via their own logins. For scheduling and progress visibility, Claude Code's own cloud Routines (`/schedule`, `/fire`, GitHub triggers, run history on claude.ai/code/routines) and `claude -p … --cloud <session-id>` are the subscription-native complement to this server's scheduler [96][99]; Claude Managed Agents' scheduled deployments are the richer product (per-run budgets, webhooks, run records) but are API-key-only and therefore blocked by policy until the owner decides otherwise [100][101].
2. Cheapest legitimate subscription capacity for non-Claude models is Ollama Cloud Pro ($20 → $60 credits → ~1,900 `gpt-oss:120b` jobs or ~230 `deepseek-v4-pro` jobs at the 165k-token job size).
3. OpenRouter is for reach (GPT-6, Gemini, Grok, 15 DeepSeek hosts), not for free tokens; pin providers, enforce ZDR, log the returned provider.
4. opencode and LM Studio are excluded from the core by legal/ToS reasons (Anthropic subscription ban; no-SaaS EULA) and by security findings, though both remain useful as optional non-Claude workers.
5. Biggest open risks: LiteLLM's supply chain (pin + hash), Max-plan headroom at 1,000 jobs/month (unverified; Routines also draw from the same subscription usage and add a daily run cap [96]), Antigravity's only-qualitatively-documented quotas and its ToS ban on third-party tools using Antigravity OAuth [104][105].
6. Hosted harnesses are not zero-retention: Managed Agents is explicitly not ZDR/BAA-eligible, Claude Code cloud sessions are unavailable to ZDR orgs, and the OpenAI Agents API has no ZDR — if a workload ever needs ZDR it stays on the local Agent SDK / OpenRouter `zdr: true` path [100][99][103][6].

Fit scores (1–10): research 7 · coding/agentic 8 · cost efficiency 8 · automation friendliness 9 · trading research 6.

Calibrated cross-lane scorecard (one anchor set, replacing the per-doc self-scores that used different anchors): research = grounded web access + long context; coding = harness quality + sandbox; cost = $/job at the §4 165k-token job on the cheapest legitimate path; automation = headless/JSON/permitted-for-scripts (ToS counts); trading = data-policy fitness for proprietary theses + reproducibility. 10 = best available in this folder, 1 = unusable. Lanes scored as the *lane* (model + auth + harness), which is what the router chooses.

| Lane | Research | Coding | Cost | Automation | Trading | Chat TTFT | Notes |
|---|---|---|---|---|---|---|---|
| Claude Code / SDK on Max OAuth | 8 | 10 | 9 (sub) | 9 (explicitly permitted first-party; no quota API) | 6 (30-day retention, no ZDR) | 7 via API endpoint at low/medium effort (Sonnet 5 1.48 s, Opus 5.5 3.16 s [145][146]); 5 through `-p` | benchmark; Terminal-Bench 4.0 #2 (Fable 5.1, 57.9%) [135] |
| Codex CLI on ChatGPT Plus | 6 | 8 | 8 (sub) | 6 (Gray/Yes*: account auth documented for trusted private runners, one `auth.json` per stream; API key "recommended default") | 5 | 5 | second coding opinion; Terminal-Bench 4.0 #1 (Astra, 58.2%) [135] |
| Antigravity CLI on Google Pro | 8 (grounding) | 7 | 7 | 4 (no third-party tools; qualitative quotas) | 4 | 4 | research fan-out only |
| Ollama Cloud Pro (gpt-oss/DeepSeek/Kimi) | 4 | 5 (via opencode/Qwen Code) | 10 | 8 (API key; no structured outputs) | 8 (transient, no training) | 8 | cheap-router, bulk |
| Ollama local ≤9B | 2 | 2 | 10 | 8 (Anthropic endpoint, Claude Code-drivable) | 9 (never leaves box) | 7 | classification only |
| OpenRouter (GPT-6/Gemini/Grok/DeepSeek hosts) | 7 | 6 | 7 | 8 (API key; provider variance) | 7 (`zdr: true`) | 6–8 | reach + second family |
| LiteLLM proxy (control plane) | — | — | 9 | 9 (budgets, OTEL) | 8 | — | supply-chain pin required |
| Alibaba Coding Plan | 4 | 6 | 8 | **1** (interactive-only) | 3 | — | owner-interactive only |
| Kimi Code plan | 5 | 7 | ? (key status unverified) | 3 | 3 | 6 | own models only |
| Claude Managed Agents / OpenAI Agents API | 8 | 9 | 5 | 2 (API key policy block) | 3 (no ZDR) | — | owner decision required |
| Grok 4.7 via OpenRouter / xAI | 7 | 6 | 7 | 8 | 7 (ZDR endpoint) | 6 | 20% cheaper on OpenRouter = xAI-set channel price (pass-through, no markup [1]; grok.md agrees) |

## 9. Sources

All accessed 2026-09-24.

1. https://openrouter.ai/docs/faq
2. https://openrouter.ai/docs/api-reference/limits
3. https://openrouter.ai/docs/features/privacy-and-logging
4. https://openrouter.ai/docs/use-cases/byok
5. https://openrouter.ai/docs/features/model-routing
6. https://openrouter.ai/docs/features/zdr
7. https://openrouter.ai/models?q=free
8. https://openrouter.ai/rankings
9. https://openrouter.ai/api/v1/models/anthropic/claude-sonnet-5/endpoints
10. https://openrouter.ai/api/v1/models/deepseek/deepseek-v4-flash/endpoints
11. https://openrouter.ai/api/v1/models/moonshotai/kimi-k3/endpoints
12. https://openrouter.ai/api/v1/models/openai/gpt-6-astra/endpoints
13. https://openrouter.ai/api/v1/models/google/gemini-3.8-flash/endpoints
14. https://openrouter.ai/api/v1/models/qwen/qwen3.8-max/endpoints
15. https://openrouter.ai/models
16. https://openrouter.ai/blog/announcements/openrouter-is-joining-stripe/
17. https://mmoustafa.com/blog/so-you-want-to-use-openrouter/
18. https://docs.litellm.ai/docs/simple_proxy
19. https://docs.litellm.ai/release_notes
20. https://github.com/BerriAI/litellm
21. https://github.com/BerriAI/litellm/issues/24512
22. https://github.com/BerriAI/litellm/issues/24518
23. https://docs.litellm.ai/docs/tutorials/claude_responses_api
24. https://github.com/kennethwolters/litelm
25. https://docs.ollama.com/cloud
26. https://ollama.com/pricing
27. https://ollama.com/cloud
28. https://docs.ollama.com/api/openai-compatibility
29. https://docs.ollama.com/api/anthropic-compatibility
30. https://github.com/ollama/ollama/releases
31. https://ollama.com/search?c=cloud
32. https://lmstudio.ai/docs/developer/core/headless
33. https://lmstudio.ai/docs/developer/openai-compat
34. https://lmstudio.ai/terms
35. https://ai.georgeliu.com/p/running-google-gemma-4-locally-with
36. https://lmstudio.ai/blog/introducing-lm-studio-bionic
37. https://opencode.ai/docs/cli/
38. https://opencode.ai/docs/providers/
39. https://opencode.ai/docs/server/
40. https://opencode.ai/docs/zen/
41. https://opencode.ai/docs/acp/
42. https://opencode.ai/docs/permissions/
43. https://github.com/anomalyco/opencode
44. https://github.com/anomalyco/opencode/releases
45. https://github.com/anomalyco/opencode/pull/18186
46. https://gist.github.com/R44VC0RP/bd391f6a23185c0fed6c6b5fb2bac50e
47. https://systima.ai/blog/claude-code-vs-opencode-token-overhead
48. https://wren.wtf/shower-thoughts/stop-using-opencode/
49. https://aider.chat/docs/scripting.html
50. https://aider.chat/docs/leaderboards/
51. https://github.com/Aider-AI/aider
52. https://raw.githubusercontent.com/block/goose/main/README.md (redirects to aaif-goose/goose)
53. https://raw.githubusercontent.com/aaif-goose/goose/main/documentation/docs/guides/goose-cli-commands.md
54. https://raw.githubusercontent.com/aaif-goose/goose/main/documentation/docs/getting-started/providers.md
55. https://docs.cline.bot/cline-cli/overview
56. https://cline.bot/pricing
57. https://github.com/cline/cline
58. https://learn.chatgpt.com/docs/developer-commands?surface=cli (redirect target of developers.openai.com/codex/cli/reference)
59. https://learn.chatgpt.com/docs/pricing
60. https://learn.chatgpt.com/docs/auth
61. https://learn.chatgpt.com/docs/sandboxing?surface=cli
62. https://github.com/openai/codex
63. https://developers.googleblog.com/an-important-update-transitioning-gemini-cli-to-antigravity-cli/
64. https://geminicli.com/docs/resources/quota-and-pricing
65. https://geminicli.com/docs/cli/cli-reference/
66. https://geminicli.com/docs/cli/headless/
67. https://github.com/google-gemini/gemini-cli
68. https://antigravity.google/docs/getting-started?tab=cli
69. https://antigravity.google/docs/cli/headless/
70. https://antigravity.google/docs/cli/overview/
71. https://qwenlm.github.io/qwen-code-docs/en/users/configuration/auth/
72. https://qwenlm.github.io/qwen-code-docs/en/users/features/headless/
73. https://github.com/QwenLM/qwen-code
74. https://github.com/MoonshotAI/kimi-cli
75. https://github.com/MoonshotAI/kimi-code
76. https://www.kimi.com/code/docs/en/
77. https://platform.kimi.ai/docs/pricing/chat
78. https://code.claude.com/docs/en/agent-sdk/overview
79. https://code.claude.com/docs/en/headless
80. https://platform.claude.com/docs/en/about-claude/pricing
81. https://claude.com/pricing
82. https://support.claude.com/en/articles/11145838-using-claude-code-with-your-pro-or-max-plan
83. https://www.anthropic.com/legal/consumer-terms
84. https://ai.google.dev/gemini-api/docs/pricing
85. https://api-docs.deepseek.com/quick_start/pricing
86. https://agentclientprotocol.com/overview/introduction
87. https://agentclientprotocol.com/overview/agents
88. https://hn.algolia.com/api/v1/search?tags=story&query=opencode (and queries "Codex CLI", "Gemini CLI", "goose block agent", "Antigravity CLI")
89. https://hn.algolia.com/api/v1/search?tags=story&query=LiteLLM
90. https://hn.algolia.com/api/v1/search?tags=story&query=%22LM%20Studio%22
91. https://hn.algolia.com/api/v1/search?tags=story&query=%22Ollama%22%20cloud
92. https://hn.algolia.com/api/v1/search?tags=story&query=OpenRouter
93. https://hn.algolia.com/api/v1/search?tags=story&query=Cline%20CLI
94. https://www.tbench.ai/benchmarks
95. https://lmstudio.ai/blog/lmstudio-v0.3.17 (via [90])
96. https://code.claude.com/docs/en/routines
97. https://code.claude.com/docs/en/desktop-scheduled-tasks
98. https://code.claude.com/docs/en/scheduled-tasks
99. https://code.claude.com/docs/en/claude-code-on-the-web
100. https://platform.claude.com/docs/en/managed-agents/overview
101. https://platform.claude.com/docs/en/managed-agents/scheduled-deployments
102. https://platform.claude.com/docs/en/managed-agents/reference
103. https://developers.openai.com/api/docs/guides/agents-api/overview
104. https://antigravity.google/terms
105. https://antigravity.google/docs/plans/
106. https://learn.chatgpt.com/docs/auth/ci-cd-auth
107. https://raw.githubusercontent.com/anthropics/claude-code/main/CHANGELOG.md
108. https://openrouter.ai/api/v1/models/x-ai/grok-4.7/endpoints
109. https://openrouter.ai/api/v1/models/openai/gpt-6-sol/endpoints
110. https://openrouter.ai/api/v1/models/openai/gpt-6-luna/endpoints
111. https://openrouter.ai/api/v1/models (zero-price entries; cited by the fact-checker, not re-fetched in this pass)
112. https://one.google.com/about/google-ai-plans/ (cited by the fact-checker for $19.99 / $99.99; not re-fetched in this pass)
113. https://www.alibabacloud.com/help/en/model-studio/coding-plan (cited by the fact-checker for Pro $50/month; not re-fetched in this pass)
114. https://hn.algolia.com/api/v1/search?tags=story&query=%22Agents%20API%22%20OpenAI
115. https://docs.ollama.com/integrations/claude-code (`ollama launch claude`; `ANTHROPIC_BASE_URL`/`ANTHROPIC_AUTH_TOKEN=ollama`/`ANTHROPIC_API_KEY=""`; cloud caveats)
116. https://docs.ollama.com/capabilities/structured-outputs ("Ollama's Cloud currently does not support structured outputs") and https://ollama.com/privacy (transient processing, no training, US processing)
117. https://code.claude.com/docs/en/data-usage (consumer 5-year / 30-day retention, ZDR Enterprise-only, telemetry defaults)
118. https://privacy.claude.com/en/articles/10023580-is-my-data-used-for-model-training
119. https://www.anthropic.com/legal/privacy (effective 2026-09-10)
120. https://code.claude.com/docs/en/monitoring-usage (OTEL metrics/events; no remaining-quota metric)
121. https://docs.litellm.ai/docs/proxy/logging
122. https://docs.github.com/en/copilot/concepts/billing/individual-plans (Free / Pro $10 / Pro+ $39; credit allowances) and https://github.com/customer-terms/github-generative-ai-services-terms (volume-licensing only; individuals → GitHub ToS §J, not fetched)
123. https://github.com/openai/codex/releases (0.156.1 stable; 0.157/0.158 alpha tags, 2026-09-23/24)
124. https://api-docs.deepseek.com/news/news260910 (V4.1-Flash 2026-09-10; `deepseek-v4-flash` retired and redirected; `deepseek-v4-pro` redirected from 2026-09-14) and https://api-docs.deepseek.com/news/
125. https://docs.x.ai/docs/models (grok-4.7 $2 / $6 / $0.50 cached; $4 / $12 / $1 at ≥200k)
126. https://statusgator.com/services/anthropic
127. https://status.openai.com/history
128. https://statusgator.com/services/openai
129. https://statusgator.com/services/openrouter
130. https://claude.com/pricing/max ("From $100"; "5x" / "20x more usage than Pro per 5-hour session"; no $200 figure printed)
131. https://developers.cloudflare.com/ai-gateway/reference/pricing/ (core features free; Unified Billing 5% fee; no inference markup; legacy log caps; Logpush; new-customer logging on Workers Logs from 2026-09-24)
132. https://developers.cloudflare.com/ai-gateway/ (providers, caching, rate limiting, dynamic routing, "available on all plans")
133. https://vercel.com/docs/ai-gateway/pricing (last updated 2026-09-08: no markup/platform fee, BYOK zero fee with credit fallback, ZDR $0.10/1k team-wide, provider allowlist $0.10/1k, trace drains $0.05/1k + $0.50/GB, free tier subset + per-model 429)
134. https://vercel.com/docs/ai-gateway (last updated 2026-09-14: `ai-gateway.vercel.sh/v1`, OpenAI Chat/Responses + Anthropic Messages, budgets, provider ordering/fallbacks, coding-agent integration)
135. https://r.jina.ai/https://www.tbench.ai/leaderboard/terminal-bench/4.0 (text mirror of the client-rendered Terminal-Bench 4.0 leaderboard; top-15 rows as of 2026-09-24)
136. https://support.claude.com/en/articles/11647753-understanding-claude-s-usage-limits ("all different Claude product surfaces … count towards the same usage limit"; no concurrency cap stated)
137. https://code.claude.com/docs/en/costs ("running multiple instances or automation" as a cost driver; API-side TPM/RPM per-user table; agent teams ≈7x tokens; prompt-cache lifetime 1 h on subscription vs 5 min on API key / usage credits; `/usage` attribution + loops rows; session/weekly limit messages carry the reset time)
138. https://docs.github.com/en/copilot/concepts/agents/copilot-cli (concept index: autopilot mode, `/fleet` parallel task execution, remote control; auth/credential details on linked pages not fetched)
139. https://code.claude.com/docs/en/authentication (Keychain vs `~/.claude/.credentials.json` 0600 fallback when the Keychain is locked over SSH; `CLAUDE_CONFIG_DIR`; 3-day expiry warning; `Login expired` error; `claude setup-token` one-year `CLAUDE_CODE_OAUTH_TOKEN`, not read in `--bare`; credential precedence list)
140. https://hermes-agent.nousresearch.com/docs/getting-started/installation (Python 3.11 + Node 26; `HERMES_HOME` = `~/.hermes/`; gateway as user-level service needing linger; no RAM figure)
141. https://docs.openclaw.ai/gateway and https://docs.openclaw.ai/ (one always-on process, port 18789, auth required by default, `~/.openclaw/openclaw.json` holds tokens; Node 26; no RAM figure)
142. https://langfuse.com/self-hosting/deployment/docker-compose (web, worker, Postgres, ClickHouse, Redis, MinIO; "at least 4 cores and 16 GiB of memory")
143. https://docs.litellm.ai/docs/proxy/prod (1 vCPU / 4Gi per worker; 4Gi "absolute floor" when storing prompts; `--max_requests_before_restart`)
144. https://code.claude.com/docs/en/security (prompt-injection protections; isolated context for web fetch; network commands not auto-approved; trust verification disabled under `-p`)
145. https://r.jina.ai/https://openrouter.ai/anthropic/claude-sonnet-5 (provider telemetry: best TTFT 1.48 s, up to 75 tok/s, $2/$10; text mirror of the model page)
146. https://r.jina.ai/https://openrouter.ai/anthropic/claude-opus-5.5 (five providers; fastest TTFT ≈3.16 s on Azure; $4/$20; released 2026-09-22)
147. https://artificialanalysis.ai/models/claude-sonnet-5 (Sonnet 5 adaptive reasoning at max effort: 150.02 s TTFT, 79.3 tok/s; the Opus 5.5 page lists speed N/A)
148. https://r.jina.ai/https://www.kimi.com/membership/pricing (renders a feature grid, "Upgrade to Kimi Membership to unlock faster models, higher concurrency", no price column); kimi.com/code/docs/en/membership-benefits, /code/pricing, /code/docs/en/faq → 404 on 2026-09-24
149. https://opentelemetry.io/docs/collector/scaling/ (no baseline sizing; only `memory_limiter` guidance)
Fetched but empty/404 in this pass (recorded so the gap is visible): https://status.claude.com/history (template only), status.ollama.com (does not resolve), statusgator.com/services/google-ai-studio, antigravity.google/docs/cli/changelog, platform.minimax.io coding-plan docs (guessed URLs), docs.x.ai Grok Build telemetry, perplexity.ai ToS (403), docs.z.ai/devpack/terms, openrouter.ai get-current-api-key doc page (endpoint itself is described in [2]).

## Verification log (2026-09-24)

Corrections applied from the fact-check pass: **19** (7 major, 12 minor), plus 6 consistency follow-ups so §1/§3/§4/§7/§8 agree with the corrected facts (Antigravity quota wording in three places, DeepSeek host count 18→15 in §8, OpenRouter free-model count in §3, Max 20x price flagged in the §4 monthly table).

Major: §2 Scheduled-tasks row (Claude Code Routines / Desktop tasks / `/loop`; Managed Agents deployments); §3 Codex auth wording (API key recommended, account-auth CI/CD pattern documented, Enterprise access tokens); §4 ChatGPT Plus automation note; §5 OpenRouter free-model churn (22 `:free` variants, not two); §7 Layer-1 free-tier wording; §3 Antigravity ToS clause on third-party tools; §3 Antigravity quotas (qualitative plans page instead of "Not found"). Minor: Google AI Pro/Ultra prices; §8 open-risk wording; goose "scheduler-native" → "only third-party harness with built-in cron" (§1 and §5); Zen GLM 5.3 vs OpenRouter GLM 5.3 Prime pricing; LiteLLM v1.102.1 (§1 and §7 pin); Cline `--auto-approve true`; DeepSeek V4.1 Flash cheapest hosts and endpoint count; Alibaba Coding Plan Pro $50; Ollama off-peak wording; Antigravity CLI licence → Antigravity Terms.

Claims re-verified in this pass (source fetched directly on 2026-09-24): Routines triggers, ≥1-hour cron minimum, `/fire` beta header, plan eligibility, daily run cap and subscription draw-down (code.claude.com/docs/en/routines); Desktop scheduled tasks 1-minute granularity and app-open requirement (…/desktop-scheduled-tasks); `/loop`/`CronCreate` 7-day expiry and 50-task cap (…/scheduled-tasks); `claude -p "msg" --cloud <session-id>` and the ZDR exclusion for cloud sessions (…/claude-code-on-the-web); `-p` permission baselines auto/dontAsk/acceptEdits (…/headless); Managed Agents beta header, API-key requirement, not ZDR/BAA-eligible (platform.claude.com/docs/en/managed-agents/overview); scheduled deployments cron/timezone/budget/webhooks/run history/`ant apply`, 1,000-deployment cap (…/scheduled-deployments); `ant beta:worker` self-hosted flags and 300/1,200 rpm limits (…/reference); $0.08 per session-hour, Sonnet 5 $2/$10 made permanent, web search $10/1k, Opus 5.5 $4/$20 (platform.claude.com/docs/en/about-claude/pricing); Antigravity Terms §6 third-party-tool clause (antigravity.google/terms); Antigravity plan quotas, overage credits, no BYOK/org contracts (antigravity.google/docs/plans); Codex "API keys are still the recommended default for automation", device auth, Enterprise access tokens (learn.chatgpt.com/docs/auth) and the CI/CD account-auth pattern (…/auth/ci-cd-auth); Claude Code changelog 2.1.280 / 2.1.278 / 2.1.277 / 2.1.276 (github anthropics/claude-code CHANGELOG.md); Grok 4.7 1.60/4.80/0.40, 500k ctx, xAI-only (openrouter.ai …/x-ai/grok-4.7/endpoints); GPT-6 Sol and Luna `-20260922` snapshots at 1,050,000 ctx (…/openai/gpt-6-sol and gpt-6-luna endpoints); Gemini grounding 5,000 free then $14 per 1,000 (ai.google.dev pricing); Ollama 0.34.0 ChatGPT Desktop, 0.34.2 first-run sign-in, 0.34.4 latest (github ollama releases); OpenAI Agents API beta, hosted vs self-hosted sandboxes, no ZDR (developers.openai.com Agents API overview; HN 2026-09-10, 350 points via Algolia); OpenRouter–Stripe: HN carries only the announcement stories, no closing story (Algolia).

Not re-fetched in this pass (taken from the fact-checker's cited sources and marked as such in §9): OpenRouter `/api/v1/models` zero-price count [111], Google One AI plan prices [112], Alibaba Coding Plan Pro price [113]. One new discrepancy recorded rather than resolved: the OpenRouter endpoints API reports GPT-6 Luna's OpenAI standard tier at 0.05 / 0.25 while the models page shows 0.10 / 0.50; the §4 tables keep the models-page figure as an upper bound.

Stale flags left in place, each now marked "(unverified as of 2026-09-24)": Claude Max 20x = $200/month; goose AAIF move dated 2026-05; Codex `workspace-write` blocking network by default; Kimi Code plan prices; Cline CLI 2.0 released 2026-02; opencode "You are OpenCode" block lifted by 2026-03-23; Codex "cybersecurity" auto-block report; Ollama Cloud Free starter-credit amount; Muse Spark 1.3 "Contributor Free" training clause; Terminal-Bench 4.0 leaderboard rows; OpenRouter/Stripe deal closing; Antigravity exit codes (confirmed, with the soft-deny-exits-0 caveat added); `-p` permission-mode list completeness (`plan` and `bypassPermissions` noted). Web search budget was exhausted for this session; everything above came from direct fetches.

Fact-checker's overall quality rating: **acceptable**.

## Gap-fix pass (2026-09-24, second pass; web search budget exhausted, direct fetches only)

Resolved: Ollama Anthropic `/v1/messages` **exists** (docs.ollama.com [29][115]) — local-models-m4-16gb.md §2 is the wrong side; SDK reach via env inherited from the Claude Code binary is inferred, not exercised. `deepseek/deepseek-v4-flash` on OpenRouter = old "V4 Flash 0423" weights; DeepSeek retired the ID 2026-09-10 [124] — LiteLLM sketch rerouted to first-party `deepseek-flash` with the OpenRouter ID demoted to a named legacy fallback. Ollama Cloud has no structured outputs [116] — cheap-router now tool-calling or Luna/Haiku for schema jobs. Alibaba Coding Plan interactive-only prohibition and 6k/45k/90k caps added [113]. Kimi Code third-party access = manual API key; subscription-vs-metered undocumented [76]. Gemini CLI: sign-in (free/Pro/Ultra) dead 2026-06-18, API keys still work; Pro/Ultra sign-in lives on in Antigravity CLI [63][105]. Grok 4.7: OpenRouter 1.60/4.80 vs xAI 2.00/6.00 both confirmed; gap unexplained by either vendor [108][125]. Copilot Free/Pro $10/Pro+ $39 with credit allowances [122]. Added cross-doc tables: data-handling matrix (primary Max lane now stated: 30-day retention with improvement off, 5-year on, no ZDR [117]), progress-visibility plumbing (no subscription lane exposes remaining quota programmatically; Claude OTEL exports usage only [120]), third-party-serving permission, tool churn, reliability window (StatusGator/vendor, 08-25→09-24), Telegram-latency rating, and a calibrated cross-lane scorecard in §8.

## Gap-fix pass (2026-09-24, third pass; web search budget still exhausted, direct fetches + text mirrors only)

Cross-doc contradictions closed: Gemini CLI sign-in — geminicli.com's quota page still prints 1,000/1,500/2,000 RPD for Google-login tiers but banners the 2026-06-18 replacement, and the Google blog says Pro/Ultra/free are no longer served, so gemini-google.md's "canonical reading" quotes a retired table [63][64] (§1, §4). §7 Codex comment aligned with the set-wide Gray/Yes* plan-auth position (account auth documented for trusted private runners; API key "recommended default") [60][106]; §8 automation score 5→6. Max 20x $200 taken as confirmed from claude.md (claude.com/pricing/max prints only "From $100") [130]. Grok 4.7's 20% OpenRouter gap is the xAI-set channel price under OpenRouter's no-markup pass-through [1] (agrees with grok.md). Gateway layer gains Cloudflare AI Gateway and Vercel AI Gateway rows (§1) and a Layer-1 alternative in §7 [131]–[134]. Terminal-Bench 4.0 top-15 retrieved through a text mirror (§5) [135]. New §3 cross-cut matrices: (a) concurrency per lane — none published for Claude Max, Codex, Antigravity or Copilot; Claude is bounded by the shared usage pool, Codex by one `auth.json` per serialized stream; (b) credential lifecycle — Keychain vs `.credentials.json` fallback, 3-day warning, one-year `setup-token`; Codex ~8-day CI refresh; Antigravity undocumented; (c) collector side — Langfuse needs 16 GiB (excluded), LiteLLM floor 4 GiB/worker, recommend OTLP/HTTP into the existing gateway + Postgres with a common event schema and window burn-rate as the remaining-budget proxy; (d) calibration procedure and break-even (Max 20x ≈440 uncached / 770 cached Sonnet-jobs per month; cache TTL 1 h on subscription vs 5 min metered); (e) prompt-injection ranking; (f) host RAM budget (OpenClaw/Hermes still undocumented); (g) reviewer independence weakened by harness effect + distillation allegations, with a measurable Jaccard test. Primary-lane Telegram TTFT now sourced: Sonnet 5 1.48 s, Opus 5.5 3.16 s at default effort, 150 s at max effort [145]–[147]. Still open: Kimi Code tier prices (every kimi.com pricing page 404 or JS-only — defer to kimi.md) [148]; Antigravity credential path/TTL; OpenClaw/Hermes RSS; Copilot CLI auth page not fetched [138].
