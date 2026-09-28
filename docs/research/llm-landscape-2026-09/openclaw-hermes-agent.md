# OpenClaw / Hermes Agent (open multi-channel personal-assistant runtimes) — research (as of 2026-09-24)

Scope note: neither project is a model vendor. Both are MIT-licensed, self-hosted agent
runtimes that sit *between* a model provider and your chat apps, and both already do what
this decision targets (Telegram/WhatsApp/Discord/Slack channels, memory, cron, per-provider
routing). Sections that ask for "model lineup", "API price per model" or "LMArena/SWE-bench"
are therefore answered for the runtime (defaults, what it routes to, what it costs to run) and
marked "not applicable" where the question does not apply. Web search budget was exhausted in
this session; every claim below comes from a fetched primary page or HN thread listed in §9.
Fact-checked and corrected 2026-09-24 — see the verification log at the end.

## 1. Snapshot

**OpenClaw**
- Origin: Peter Steinberger's weekend "WhatsApp relay" (Nov 2025) → *Clawd* (renamed after
  Anthropic legal contact) → *Moltbot* → *OpenClaw* (announced Jan 29 2026; HN rename thread Jan 30) [27]. Passed 100k GitHub
  stars in two months [27]; 390k stars / 82.1k forks / ~99.5k commits on 2026-09-24 [2].
- Governance: OpenClaw Foundation, an independent 501(c)(3) formed Jul 8 2026, employs the
  core team; "no paid tier, hosted service, or token requirements" [1][2][28].
- Stack: TypeScript/Node (Node 24.16+ or 26.1+, Node 26 recommended) [22]. Single always-on
  "Gateway" daemon on `127.0.0.1:18789` [9][10].
- Release cadence: calendar-versioned, several releases per month; latest `v2026.9.6`
  (v2026.9.4 → 9.5 (Sep 19; 4,179 PRs from 503 contributors) → 9.6 (Sep 23, macOS rebuild Sep
  24 for a launch crash) all in September 2026; the extended-stable/LTS line is v2026.7.x,
  latest v2026.7.35 on Sep 21 2026 — "OpenClaw from late July 2026 plus security updates and
  performance fixes"; "OpenClaw 2.0" (v2026.8.1) shipped Aug 30 2026 after "nearly seven weeks
  without shipping", rolling up 16,000+ PRs — "roughly 50% of all pull requests ever merged"
  — from 933 contributors (569 first-time), with the browser app rebuilt "as a first-class
  experience" and "shared cloud sessions" making it "a multiplayer experience") [2][72][73];
  an LTS/extended-stable channel was announced Jul 30 2026 [24][28]. Newest architectural
  post: "Decision models in OpenClaw" (Josh Lehman, Sep 22 2026) — small decision models for
  tool relevance, message compaction and agent responsiveness, plus a plugin-first strategy for
  contributors [28]; the fact-checker's "steer-vs-queue" framing was not found in the fetched
  post text (unverified as of 2026-09-24).
- Model lineup: none of its own. Ships provider plugins for 60+ providers [3]. Documented
  defaults on 2026-09-24: `anthropic/claude-opus-5-5` (default per the Anthropic page — the
  providers index still shows `anthropic/claude-opus-4-6` as its example default, doc drift;
  the "documented default" claim rests on one page) (1M input / 128k output;
  also lists `claude-opus-5`, `claude-sonnet-5`, `claude-fable-5-1`, `claude-fable-5`,
  `claude-mythos-5`) [4]; `openai/gpt-6-astra` (1,050,000-token context, 128k output,
  272k default active input budget; also `gpt-6-sol`, `gpt-6-luna`, `gpt-5.6-*`, `gpt-5.5`)
  [6]; `xai/grok-4.7` after OAuth login [7]; `google/gemini-3.1-pro-preview` [8];
  `zai/glm-5.2` / GLM-5.3 [29]. Knowledge cutoffs: not applicable (provider property).
- Positioning (their words): "Your AI assistant, on your own hardware, in every chat app you
  already use" — a local control plane that owns sessions, tools, channel connections and
  memory, and delegates model calls to whatever provider you authenticate [1][9].

**Hermes Agent (Nous Research)**
- Origin: Nous Research (the Hermes fine-tune lab). Repo at 248.6k stars on 2026-09-24,
  MIT, Python 3.11 [38]. Nous's own weights: Hermes-4-14B, Hermes-4-70B (71B),
  Hermes-4-405B-FP8, Hermes-4.3-36B (Dec 2025), NousCoder-14B, nomos-1 (31B) on Hugging
  Face; context windows and licenses not shown on the org page [67].
- Release cadence: patch every 3–10 days; `v0.21.0` "Pantheon" on Aug 31 2026, then
  v0.21.1 (Sep 7), 0.21.2 (Sep 11, "state.db patch"), 0.21.3 (Sep 14), 0.21.4 (Sep 21,
  ~1,800 PRs rolled up), 0.21.5 (Sep 24, ~460 PRs) [39].
- Model lineup: none of its own inside the agent; the model catalog manifest marks
  `z-ai/glm-5.2` as default and `moonshotai/kimi-k3` as recommended, with `openai/gpt-5.4`
  and `anthropic/claude-opus-4.7` as examples; "pricing and context length are NOT in the
  manifest" — they are fetched live from provider `/v1/models` and models.dev [60].
  Provider defaults: `MiniMax-M2.7` (MiniMax) [40], `grok-4.6` (xAI OAuth) [55].
- Positioning: an agent that "creates skills from experience", with persistent memory,
  34 messaging platforms/adapters behind one gateway (per the messaging overview page; the
  README front page names only Telegram, Discord, Slack, WhatsApp, Signal, Email, CLI; a
  recount of the same page on 2026-09-24 gave 31 rows, so treat the exact figure as 30+) [47], built-in cron, subagent delegation, seven
  terminal sandboxes (local, Docker, SSH, Singularity, Modal, Daytona, Vercel Sandbox) and a
  commercial companion subscription, **Nous Portal** (300+ models + hosted tools; Nous's own
  material is inconsistent — Portal "What's included" says 300+, the Hermes homepage and Portal
  tier cards say 200+; unverified as of 2026-09-24 which is current) [37][38][57].

## 2. Interfaces & surfaces

| Surface | OpenClaw | Hermes Agent |
|---|---|---|
| Consumer app | macOS menu-bar app (macOS 15+; voice needs macOS 26; new installer Sep 3 2026), Windows Hub app (WinUI, Windows 10 20H2+/11), browser app rebuilt as first-class in 2.0 with shared cloud sessions, Control UI web dashboard, WebChat, TUI (TUI unverified as of 2026-09-24) [1][23][73] | Desktop app (macOS 12+, Win 10/11), TUI, "Bot Mode" desktop integration (v0.21.0) [37][39] |
| Messaging channels | WhatsApp (Baileys), Telegram (grammY), Slack, Discord, Signal, iMessage, Google Chat, Teams, Matrix, Zalo, Nostr, Twitch, "20+ more" via plugins [1][2][9] | Telegram, Discord, Slack, WhatsApp, WhatsApp Cloud API, Signal, Email, SMS, Matrix, Mattermost, Teams (+meetings), Home Assistant, IRC, Webhooks, A2A, DingTalk/Feishu/WeCom/QQ [37][64] |
| CLI / headless | `openclaw agent --message … --json` one-shot; `openclaw cron`; `openclaw message send` [12][13] | `hermes chat -q … --oneshot`, `hermes -z "…"`, `--format stream-json`, `hermes send --to telegram` [41][42] |
| OpenAI-compatible endpoint | Gateway serves `POST /v1/chat/completions`, `/v1/responses`, `/v1/embeddings`, `GET /v1/models` (off by default; `gateway.http.endpoints.chatCompletions.enabled`; `/v1/responses` is enabled separately via `gateway.http.endpoints.responses.enabled`) [10][11] | API server on `127.0.0.1:8642`: `/v1/chat/completions`, `/v1/responses` (with `previous_response_id`), `/v1/runs` (durable async), `/api/jobs`, `/api/sessions/*` [49] |
| Native RPC | WebSocket JSON frames `{type:"req"|"res"|"event"}` on 18789, idempotency keys on `agent`/`send` [9] | ACP (JSON-RPC over stdio, `hermes acp`), TUI-gateway JSON-RPC (stdio/WebSocket), in-process `run_agent.AIAgent` [50] |
| Official SDKs | none beyond the WS protocol and CLI (unverified beyond docs) | Python in-process import only [50] |
| MCP | not documented as a client feature on docs.openclaw.ai/tools (fetched 2026-09-24: tools/skills/plugins only, no MCP page); the `openclaw agent` reference does mention "bundled MCP loopback resources" retired after `--local` runs and kept under the Gateway process, so some MCP plumbing exists internally [13] | MCP client with config reference and setup guide [64] |
| Batch API | not applicable (runtime) | not applicable |
| Structured output / tool use | passthrough of provider `tools`/`tool_choice`; `finish_reason:"tool_calls"` [11] | 40+ built-in tools; tool schemas per "toolset" [38][43] |
| Computer-use / browser | browser tool (sandboxable), macOS node tools (`screen.record`, `camera.*`, `canvas.*`) [9][20] | Browser Use cloud browser, local browser plugins; "vision" [38] |
| Scheduled tasks | `openclaw automations` (alias `cron`): ISO one-shots, cron rules, stream sources, condition watchers; payloads = agent turn / command / script / system event; delivery to chat, webhook or silent [14] | `hermes cron`: `in 30m`, `every 2h`, natural schedules, cron expr, ISO; fresh isolated session per run; `deliver:` to any platform; script-only (no-LLM) jobs [43][44] |
| Memory | Markdown files `USER.md`, `MEMORY.md`, `memory/YYYY-MM-DD.md`, `DREAMS.md`; hybrid vector+keyword `memory_search` (needs an embedding provider, OpenAI default); "Dreaming" consolidation; Honcho/LanceDB engines [15] | `MEMORY.md` (~2,200 chars) + `USER.md` (~1,375 chars) hard-capped, no auto-compaction; FTS5 `session_search` over all sessions; 7 external providers (Honcho, Mem0, Supermemory…) [45] |
| Projects / workspaces | per-agent workspace + `agentDir` + SQLite session store; `agents.entries.*`; bindings route channel/peer → agent; team preset (coordinator/researcher/writer/reviewer) [16] | Profiles (`--profile`), per-channel model/prompt overrides, subagents via `delegate_task` (10 concurrent, 250 iterations, depth 1 by default) [42][53] |
| IDE plugins | drives external harnesses via ACP: Claude Code, Cursor, Copilot, Droid, OpenCode, Gemini CLI [18] | exposes itself as an ACP server for IDEs [50] |
| Voice | macOS 26 voice, companion "Voice"/"Canvas" nodes [1][23] | STT/TTS voice notes in Telegram, "voice mode" [48][64] |

## 3. Headless / server automation fit

**OpenClaw**
- Runs unattended under launchd (`ai.openclaw.gateway`) via `openclaw gateway install`; on
  Linux, a systemd user unit with `loginctl enable-linger`; exit code 78 = bad config and
  systemd is told not to restart-loop on it [10].
- One-shot: `openclaw agent --agent ops --message-file ./task.md --json` returns a stable
  JSON envelope (`ok`, `status`, `final`, `payloads[]`, `usage`, `costUsd`, `model`,
  `provider`, `sessionId`, `toolSummary`); default timeout 600 s (`agents.defaults.timeoutSeconds`, 0 disables); exit 0 success / 1
  error / 2 timeout (`agent exec`; Gateway-backed `openclaw agent` folds timeout into 1); diagnostics go
  to stderr so stdout is a single JSON document; `--local` runs without the Gateway but takes
  an exclusive state-dir lock [13].
- Session resume: `--session-id` / `--session-key` on `agent`; HTTP API derives a stable
  session from the OpenAI `user` field or `x-openclaw-session-key` [11][13].
- Streaming: WS `agent` requests stream events with a `runId`; HTTP `stream:true` → SSE with
  `data: [DONE]` and optional `stream_options.include_usage` [9][11].
- Auth modes per provider: Anthropic = API key **or** "Claude CLI" (reuses an existing Claude
  Code login on the host; setup tokens `sk-ant-oat01-…`; OpenClaw "communicates directly with
  the installed Claude Code executable" and never persists the OAuth token) [4]; OpenAI = API
  key or ChatGPT/Codex subscription OAuth ("OpenAI explicitly supports subscription OAuth
  usage in external tools" — OpenClaw's wording, not verified against OpenAI's own terms)
  [5]; xAI = device-code OAuth with SuperGrok / X Premium, or `XAI_API_KEY` [7]; Google =
  AI Studio API key only — Gemini-CLI OAuth "ended June 18 2026", Antigravity OAuth "no
  longer supported" [8].
- **Terms history (the reason this matters):** Google permanently suspended AI Pro/Ultra
  accounts that used OAuth through OpenClaw in Feb 2026 ("use of Antigravity servers to power
  a non-Antigravity product") [33]. Anthropic emailed flagged Pro/Max users on ~Apr 3 2026
  that subscription limits could "no longer be used for third-party harnesses including
  OpenClaw", offering a one-time credit and pointing to extra-usage/API billing [31]. On
  Apr 21 2026 OpenClaw reported Anthropic staff confirmed the in-harness `claude -p` path is
  allowed; direct OAuth-token extraction stays prohibited — but in the same Apr 21 post OpenClaw
  said "Anthropic still blocks parts of our system prompt, so the actual behavior today does
  not match what was communicated publicly" [32]. OpenClaw's Anthropic page now
  states that "Subscription-plan Claude Agent SDK, `claude -p`, and third-party app usage still
  draw from the signed-in subscription's usage limits" — mirroring Anthropic's June 15 text [4]. Anthropic's own support article exists and is linked from OpenClaw's Anthropic page:
  support.claude.com article 15036540 "Use the Claude Agent SDK with your Claude plan" states
  that as of June 15 2026 the announced change is paused and "Claude Agent SDK, `claude -p`, and
  third-party app usage still draw from your subscription's usage limits" (the planned per-plan
  monthly Agent SDK credits — Pro $20, Max 5x $100, Max 20x $200, Team Standard $20, Enterprise
  usage-based $20 / Premium seats $200 — are not in effect) [69]. The companion Pro/Max Claude
  Code article (updated Aug 19 2026) says API credits used through Claude Code after the plan
  allocation is exhausted are "billed at standard API rates (distinct from Pro/Max Plan
  pricing)" [70]. No Anthropic statement newer than June 15 2026 on the Agent SDK policy was
  found (a 5-point HN post of 2026-09-18 still cites the June 15 text) (unverified as of
  2026-09-24 whether the pause has since lifted).
- Sandboxing: off by default; `agents.defaults.sandbox` / per-agent; backends Docker,
  Podman, SSH, OpenShell, Crabbox; Gateway itself always stays on host; `tools.elevated`
  escape hatch [20]. `openclaw security audit` checks drift from secure defaults [19].
- Rate limits / caps: none of its own; inherits provider limits. Z.ai documents that
  OpenClaw traffic on GLM Coding Plan is "secondary scheduling and best-effort" behind their
  own coding agent under load [29].

**Hermes Agent**
- Service install: `hermes gateway install` (launchd plist on macOS, systemd user/system unit
  on Linux, Task Scheduler on Windows); `hermes gateway run` for foreground; a durable
  delivery ledger redelivers after crashes with a recovery notice; adapter circuit breakers
  [47]. Cron ticks every 60 s inside the gateway [43].
- One-shot: `hermes chat -q "…" --oneshot` or `hermes -z "…"` (final text on stdout, no
  banners); `--query-file -` for stdin; `--format stream-json` emits one JSON object per line
  with `timestamp`, event `type` and fields; `--yolo` auto-approves; `--toolsets
  web,terminal,skills`; `--profile` [41][42]. Exit codes are enumerated in the CLI reference:
  `--oneshot` → 0 completed, 1 failed/partial/budget (or never ran), 130 interrupted, 75
  (`EX_TEMPFAIL`) for Kanban-dispatched workers on provider rate-limit/5xx/quota; `-z` → 0
  completed, 2 failed/partial/budget (also usage errors), 1 answered nothing, 130 interrupted;
  `--usage-file <path>` writes a JSON usage report (`estimated_cost_usd`, input/output/cache/
  reasoning token counts, `api_calls`, `model`, `provider`, `session_id`, completed/failed/
  partial/interrupted flags, `turn_exit_reason`, auxiliary-task breakdown) even on failure [41].
- Session resume: `hermes -c` (last session, terminal-aware), `hermes -r <id|title>`; IDs
  `YYYYMMDD_HHMMSS_<hex>`; everything in `~/.hermes/state.db` (SQLite WAL + FTS5) [54].
- HTTP: enable with `API_SERVER_ENABLED=true` + `API_SERVER_KEY` in `~/.hermes/.env`;
  `POST /v1/runs` returns `run_id`, `GET /v1/runs/{id}/events` streams `tool.started` /
  `tool.completed`, `POST /v1/runs/{id}/stop`; `POST /api/jobs` creates scheduled jobs and
  `POST /api/jobs/{id}/run` triggers them; 100 stored responses (LRU) [49].
- Auth modes: Nous Portal browser OAuth (`hermes setup --portal`, short-lived JWTs minted
  from a refresh token) [56]; OpenAI API key or **Codex/ChatGPT subscription OAuth**
  (device-code default) [40]; Anthropic API key, OAuth, or (since ~Sep 21 2026,
  Hermes ≥ 0.21.4) the separately installed `claude-subscription-directsdk` plugin (`hermes
  plugins install claude-subscription-directsdk`) which supports Claude Pro and Max via the
  installed Claude Code CLI and bills the subscription's Agent SDK allowance (Pro: Fable 5.1
  requires usage credits; Max includes it up to 50% of weekly limits; metered at the `claude -p`
  rate, ~1.7× the interactive TUI rate; native tools/skills/setting sources disabled;
  single-request admission — one client per independently cancellable Hermes owner; no
  prefill, forced tool choice or arbitrary headers; "Experimental", plugin v0.3.0 added Sep 20
  / updated Sep 23 2026) [71] — docs say the OAuth path
  "requires Claude Max + extra credits" and "Claude Pro subscribers cannot use OAuth path"
  [40]; xAI OAuth (`hermes auth add xai-oauth`, SuperGrok/X Premium+; some SuperGrok tiers get
  403 and must fall back to `XAI_API_KEY`) [55]; MiniMax OAuth, Qwen OAuth, GitHub Copilot
  device login, OpenRouter PKCE; API keys for DeepSeek (`DEEPSEEK_API_KEY`), Kimi
  (`KIMI_API_KEY`), Z.ai (`GLM_API_KEY`), Ollama/vLLM/LM Studio/llama.cpp local [40].
- Credential pools rotate multiple keys/OAuth logins per provider (OpenRouter, Anthropic
  Claude-Max OAuth, OpenAI Codex multi-account, Nous Portal); 429 twice → rotate with 1 h
  cooldown, 402 → immediate rotate, 401 → refresh then rotate; exhaustion falls through to
  `hermes fallback` providers [52].
- Sandboxing: `terminal.backend: docker` runs every command in one persistent container
  (skills dir and declared credential files bind-mounted read-only); Docker hardening =
  dropped caps, no-new-privileges, 256-process limit, tmpfs `/tmp` (unverified as of
  2026-09-24 — not present on the security, docker or network-isolation pages re-fetched)
  [46][63]. Network egress isolation guide: two Docker networks — an `internal: true` network
  with no default route for the agent and an egress network used only by a Squid proxy
  (`HTTP_PROXY`/`HTTPS_PROXY=http://egress-proxy:3128`, `NO_PROXY=hermes,hermes-dashboard,
  localhost`) whose `squid-allowlist.conf` names the permitted API hosts; caveats: DNS still
  resolves unless a local resolver blocks it, it isolates only the network layer, and every
  new platform adapter's endpoint must be added to the allowlist [76]. This maps directly onto
  our "no live order path" / no-exfiltration rule. "Smart"
  approval mode uses an auxiliary LLM risk check; hard blocklist survives `--yolo` [46].
- Subscription Proxy: `hermes proxy start` exposes `http://127.0.0.1:8645/v1` so *other*
  apps can use your **Nous Portal or xAI** subscription; currently only `nous` and `xai` providers are shipped
  (`--provider nous|xai`; more via the `UpstreamAdapter` interface); non-OpenAI-compatible
  protocols such as the Anthropic Messages API "would need a transformation layer, which is
  out of scope", and there is no ChatGPT/Codex proxy — it does not proxy Claude or ChatGPT [51].

**Conflict to note:** OpenClaw says a Claude Max login used through the installed Claude Code
binary draws from the subscription allowance [4]; Hermes says its Anthropic OAuth path bills
"extra credits, not base allowance" [40]. Both are consistent with Anthropic's Apr-2026 line
(in-harness `claude -p` = subscription; raw OAuth = extra usage) [31][32], but neither is an
Anthropic primary source. The Anthropic primary source (support.claude.com/en/articles/15036540,
status as of June 15 2026) says Agent SDK, `claude -p` and third-party app usage draw from the
subscription's usage limits; the planned Agent SDK credit scheme is paused [69]. Note also that
Hermes' providers page [40] still says Claude Pro subscribers cannot use the OAuth path — verbatim
true, but that page has not been updated to mention the newer `claude-subscription-directsdk`
plugin [71], so the two Hermes pages disagree (unverified as of 2026-09-24 which will be
reconciled).

## 4. Cost

**Runtime licence cost:** $0 for both (MIT; no paid tier) [1][2][38][62].

**Consumer plan tiers relevant to these runtimes**
| Plan | $/mo | Includes | Caps / notes | Src |
|---|---|---|---|---|
| Nous Portal Free | $0 | "free models only" | standard rate limits, no credits | [57] |
| Nous Portal Plus | $20 | $22 credits/mo, 200+ models, hosted tools (Firecrawl search, FAL/Krea image, Browser Use, OpenAI TTS) | $10 rollover cap, "high" rate limits | [57] |
| Nous Portal Super | $100 | $110 credits/mo | $50 rollover cap | [57] |
| Nous Portal Ultra | $200 | $220 credits/mo | $100 rollover cap | [57] |
| Nous Portal top-ups | $10/20/50/100/200 | Stripe | — | [57] |
| Claude Max (via OpenClaw Claude-CLI runtime / Hermes `claude-subscription-directsdk` / Hermes OAuth) | see claude-anthropic.md in this set | subscription Agent SDK allowance (OpenClaw Claude CLI, Hermes directsdk) or extra-usage credits (Hermes OAuth) | 5-hour/weekly windows apply; Max 20x multiplier reportedly 5-h window only [77] | [4][40][71] |
| ChatGPT Plus/Pro (Codex OAuth in both runtimes) | see chatgpt-openai.md in this set | Codex quota | model list differs from API key ("account catalog is authoritative") | [5][6][40] |
| SuperGrok / X Premium+ (xAI OAuth in both) | see grok-xai.md in this set | Grok 4.x chat, image, video, TTS via OAuth | xAI tools (`x_search`, `code_execution`) bill **$5 per 1,000 tool calls** on top of tokens; some tiers 403 | [7][55] |
| GLM Coding Plan (OpenClaw guide) | see glm-zai.md in this set | GLM-5.3 / 5.3-Flash | OpenClaw traffic is best-effort behind Z.ai's own agent | [29] |

**API price per model:** not applicable to the runtime; Nous Portal publishes per-model
rates that "vary widely" — budget $0.02–0.10/M input, mid-range $0.50–3.00/M input, and a
a mid/premium example of $2.50 in / $10.00 out per 1M (GPT-4o, a 2024 model, as listed) — current
frontier models on the same page are ~4× higher (Claude Fable 5.1 listed at $10.00 in / $50.00
out per 1M), so the "premium" cost rows below understate frontier-model cost by roughly 4× (a
frontier row is added for comparison) [57]. Per-model rates
for Claude and OpenAI on Portal's front page (as listed there): Claude Fable 5.1 $10.00 in /
$50.00 out per 1M, Claude Opus 4.1 $15.00 / $75.00, Claude Opus 4.5 (batch) $2.50 / $12.50,
Claude 3 Haiku $0.25 / $1.25, GPT-4o $2.50 / $10.00, DeepSeek V4 Flash $0.03 / $0.32, Llama 3.1
8B $0.02 / $0.04 [57]; Gemini rates and the full DeepSeek list could not be captured (portal
pricing/models pages returned HTTP 429; searched: portal.nousresearch.com/pricing, /models).

**Estimated monthly cost to run N agent jobs** — assumptions: 150k input + 15k output
tokens/job, no prompt caching, no tool-call surcharges, no subagent fan-out (Hermes'
`delegate_task` and OpenClaw's team preset multiply this), runtime overhead of system
prompt + tool schemas already inside the 150k. Runtime cost itself is $0 for both.

| Path | Unit price used | 10 jobs | 100 jobs | 1,000 jobs |
|---|---|---|---|---|
| (a) Claude Max via OpenClaw Claude-CLI runtime, Hermes `claude-subscription-directsdk` [71], or our existing Claude Agent SDK | flat subscription (price in claude-anthropic.md); extra usage bills at standard API rates [70] | $0 marginal | $0 marginal **if** inside the 5-h/weekly window; 16.5M tokens/mo is plausible | 165M tokens/mo — will not fit a consumer window; spills to extra usage at API rates [70] (cap unverified) |

Caution on the "$0 marginal inside the window" row: HN reports of Aug 31 / Sep 3 2026 (15 / 7 /
4 pts) cover a false-advertising suit over Claude Max limits — the Max 20x multiplier reportedly
applies only to the 5-hour window, not the weekly limit [77]; cross-reference claude-anthropic.md.
| (a) Nous Portal Plus, mid-range model ($0.50 in / $2.00 out) [57] | $0.105/job | $1.05 (inside $22 credits) | $10.50 (inside $22) | $105 → needs Super ($110 credits) or top-ups |
| (a) Nous Portal Plus, budget model ($0.10 in / $0.40 out; output assumed 4× input) [57] | $0.021/job | $0.21 | $2.10 | $21 (fits Plus) |
| (a) ChatGPT / SuperGrok / MiniMax / Qwen OAuth in Hermes or OpenClaw | flat subscription | $0 marginal | $0 marginal within quota | quota-bound; credential pools rotate multiple accounts [52] |
| (b) API key, premium tier ($2.50 in / $10 out; GPT-4o-class 2024 pricing) [57] | $0.525/job | $5.25 | $52.50 | $525 |
| (b) API key, current frontier (Claude Fable 5.1 on Portal, $10 in / $50 out) [57] | $2.25/job | $22.50 | $225 | $2,250 |
| (b) API key, mid-range ($0.50 / $2.00) [57] | $0.105/job | $1.05 | $10.50 | $105 |
| (b) API key, budget ($0.10 / $0.40) [57] | $0.021/job | $0.21 | $2.10 | $21 |
| Hermes script-only cron (no LLM) [44] | $0 | $0 | $0 | $0 |

Free-tier limits: Nous Portal Free = free models only with standard rate limits [57]; which
models are "free" is partly visible on the Portal front page (e.g. inclusionAI Ling 3.0 Flash
variants, Meituan LongCat 2.0, Poolside Laguna, Step 3.7 Flash, Upstage Solar Pro 4, Reka Edge
listed at $0.00/1M); the full list was not captured (pricing page 429) [57]. OpenRouter free tiers work through
both runtimes via `OPENROUTER_API_KEY` [40][3] — limits are in runtimes-aggregators.md.

## 5. Strengths & weaknesses per reviews

Benchmarks: LMArena / SWE-bench Verified / Terminal-Bench / Artificial Analysis / GPQA / HLE
are model benchmarks and do not score these runtimes. Not found — searched: HN Algolia
"openclaw" and "hermes agent" story indexes, both projects' docs and release pages. Neither
project publishes a harness score on Terminal-Bench (unverified).

**OpenClaw — best at:** breadth of channels and providers (60+ providers, 20+ channels)
[1][3]; local-first control plane with a real RPC protocol, idempotent side effects and
event subscriptions [9]; cost/usage surfaced per run (`costUsd`, `usage` in `--json`) [13] (Hermes matches this with
`--usage-file`, see §3);
running Claude Code as an in-harness runtime while keeping the model reference canonical
[17]; team/subagent presets with deterministic routing [16]. Jake Quist (Feb 2026, 518 HN
points) argues it "has become the killer app for Mac hardware" (exact phrase unverified as of
2026-09-24; the Mac-Mini-buying discussion is confirmed) and that people are "buying
Mac Minis specifically to run AI agents" [36].

**OpenClaw — weak at / controversies:**
- Security surface. HN "OpenClaw is a security nightmare dressed up as a daydream" (397 pts,
  Mar 22 2026): simonw frames it as the unsolved "lethal trifecta" (private data + tool
  execution + exfiltration path); _pdp_ and lemming stress that network access makes
  prompt-injection consequential regardless of containers; defenders (vessenes, phil21)
  say the utility is "too useful" to abandon [35] (thread points/date verified; these username
  attributions unverified as of 2026-09-24). Critical CVE-2026-33579 (Mar 31 2026,
  `/pair approve` scope-subsetting flaw enabling escalation via reopened device pairing;
  credited to AntAISecurityLab) [30]. The docs themselves list "exposed gateways and
  malicious skills" as the primary known incident classes [19]. Mitigation program: NVIDIA
  collaboration on ClawHub "security cards" (Jun 1 2026), Trail of Bits audit via OpenAI's
  "Patch the Planet" (Sep 21 2026), atomic updates, LTS channel [28].
- Provider-policy whiplash. Feb 2026 Google bans (permanent, no warning) [33]; Apr 3 2026
  Anthropic cutoff [31]; Apr 21 partial reversal — throwup238 called Anthropic's strategy
  "confused and shambolic", jarym: "the damage is already done… users now expect potential
  rug-pulls" [32]; Apr 30 thread (1,349 pts) alleging Claude Code refused/charged extra when
  commits mentioned "OpenClaw" — stingraycharles: implemented "incredibly poorly" with
  "simple regex"; defenders (applfanboysbgon, selectively) attribute it to anti-abuse of
  24/7 automated use; no Anthropic statement in-thread [34] (username attributions in [31][32][34]
  unverified as of 2026-09-24; thread points/dates verified). The Apr 30 "commits mention
  OpenClaw" heuristic incident has no confirmed resolution (unverified as of 2026-09-24).
- Token burn: HN commenters across threads (mmusc: "very good at spending all your tokens…
  way too expensive to run") [65]; imtringued/charcircuit explain why flat-rate plans break
  under unattended agents [31].
- Footprint: RAM/CPU not documented [22][23]; Node 24/26 required [22] (TUI surface and
  Node 24/26 RAM figures still undocumented; unverified as of 2026-09-24).
- Momentum: the Aug 31 2026 HN thread on "OpenClaw 2.0, Accidentally" (148 pts, 175
  comments) is dominated by commenters saying interest "fell off a cliff after March"
  (minimaxir, citing Google Trends) and that users migrated to Hermes (radcod3: "Most people
  I know use hermes now"), Claude Code, Pi or custom stacks; criticisms centre on security,
  an "unmaintainable" codebase and breaking updates [74]. Single-thread signal, not a usage
  measurement.

**Hermes Agent — best at:** learning loop (auto-generated, self-improving skills; `/learn`)
[38]; operational hardening useful for a server — durable delivery ledger, circuit breakers,
credential pools with typed 429/402/401 handling, script-only cron, secret redaction on
every cron delivery, prompt-injection scan at cron-creation time [43][47][52][46]; the
richest headless surface of the two (`stream-json`, `/v1/runs` with SSE lifecycle,
`/api/jobs`) [42][49]; seven sandbox backends including serverless (Modal, Daytona) [38].
apexalpha (HN, Jun 2026) calls it "magical" as a homelab sysadmin with k8s monitoring, SSH
and Telegram [65].

**Hermes Agent — weak at / controversies:**
- Platform: the macOS installer is "Apple Silicon only"; Intel macOS is not a supported
  platform [58] (fine for the M-series Mac Mini, but rules out Intel hosts).
- Small community signal: top HN thread is 52 points / 42 comments (Jun 5 2026) versus
  OpenClaw's six 500–1,349-point threads (1,349 / 1,099 / 802 / 667 / 518 / 511) plus the
  148-point / 175-comment "OpenClaw 2.0, Accidentally" thread of Aug 31 2026 [65][68][74].
  Nous's vendor viability, by contrast, looks funded: TechCrunch (Jul 13 2026) reported Nous
  Research in talks to raise at least $75M at a ~$1.5B valuation (prior funding ~$70M from
  Paradigm, Robot Ventures, USV and others), which is the only Portal-durability signal found
  [75].
- Quality complaints: sshine finds it "sluggish, very slow to start" and over-engineered,
  ranking Claude best overall and OpenCode best UI among Claude/OpenCode/Pi/Hermes/OpenClaw;
  jdiff: "janky, flickery CLI" and forced builds from master; dislike of MEMORY.md summaries
  vs full logs [65]. Release notes confirm a run of state.db corruption/handle-leak patches
  in Sep 2026 [39]. Memory files are hard-capped and error rather than compact [45].
- Trust: May 2026 plagiarism claim (Hermes derivative of EvoMap's "Evolver"); Nous blanked
  the issue to ".", deleted four users' comments and blocked them, no statement [66]; jdiff
  repeats the claim in the Jun thread [65]. Commenters flag the third-party hermes-agent.org
  site and eve.new as obscuring non-Nous affiliation, and a broken account-deletion flow for
  Google OIDC users [65].
- Subagents cannot pick models individually (one global `delegation.model`) [53].
- Reliability/outage record for Nous Portal: Not found — searched: portal.nousresearch.com,
  Hermes FAQ, HN.

## 6. Finance / trading relevance

- Neither runtime ships market-data connectors. Hermes' bundled catalog (82 skills, 12
  categories) has no finance/trading/crypto skill; nearest are `research/arxiv` and
  `research/competitor-news-monitor` [61]. ClawHub lists ~30 community "trading" skills
  and 12 plugins: technical-analysis "Trading" (@ivangdavila, 10.9k installs), "Trading
  Coach" (11.5k), "vibe-trading" backtesting toolkit (5.2k), Polymarket BTC 5/15-min
  fast-market bot (1.8k), Hyperliquid perps placement (712), Solana/Base DEX swaps via Nansen
  (1.7k) [26]. These are unvetted third-party skills; ClawHub scanning holds/blocks releases
  and the docs list malicious skills as a known incident class [25][19].
- Real-time data: both can call web search — OpenClaw via provider tools (e.g. xAI
  `x_search`, $5/1k calls [7]) or skills; Hermes via Firecrawl/Nous Tool Gateway on a
  Portal plan or your own keys [56][40]. Sentiment: X/Twitter search only through xAI's
  server-side tool [7].
- Restrictions: ClawHub skills that place real orders (Hyperliquid, DEX swaps) exist; our
  server's "no live order path" rule means any adopted runtime must have `exec`/order tools
  denied per agent (`agents.entries.*.tools.deny` in OpenClaw [16]; `hermes tools` per
  platform / toolsets in Hermes [43]).
- Fit for Atlas: as a *delivery and scheduling* layer (paper-trading digests to Telegram,
  weekly adversarial-review reminders) both are adequate; as a research engine neither adds
  anything over calling the model provider directly.

## 7. Integration recipe for our server

**Recommendation: do not adopt either as the server's core; run Hermes as an optional
sidecar for non-Anthropic subscription providers, and borrow designs (not code) from both.**
Rationale: our engine is already the Claude Agent SDK on a Max subscription, which OpenClaw's
own docs place on the allowed, subscription-drawing side of Anthropic's policy [4][32] — while
the same OpenClaw page adds "For shared production automation, use an Anthropic API key instead
of Claude CLI" (API-key auth = separate pay-as-you-go billing) [4];
neither runtime adds a compliant Claude path we lack — Hermes' new `claude-subscription-directsdk`
plugin [71] is the same Agent SDK path with Claude's native tools disabled, i.e. a duplicate. What we lack is (1) subscription-OAuth
access to Codex, Grok, MiniMax and Qwen without API keys, (2) credential rotation and
fallback across those, and (3) a second, cheaper opinion for adversarial review — all of
which Hermes provides headlessly [40][52][49].

Option A — Hermes sidecar (preferred)
```bash
# one-time, on the Mac Mini (installs uv-managed Python 3.11, Node 26, ripgrep, ffmpeg) [58]
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
hermes model                       # pick "Codex Subscription" (device code) / xAI OAuth / MiniMax OAuth [40]
hermes auth add openrouter         # free-tier models as fallback; then: hermes fallback add … [40][62]
# headless, JSON-lines, no gateway needed
hermes chat -q "$(cat task.md)" --oneshot --format stream-json --yolo \
  --toolsets web --profile review --model openai/gpt-5.5  > run.jsonl     # [41][42]
# or the durable HTTP path (gateway must run; keep API_SERVER_HOST=127.0.0.1)
printf 'API_SERVER_ENABLED=true\nAPI_SERVER_KEY=%s\n' "$KEY" >> ~/.hermes/.env
hermes gateway install && hermes gateway start                               # launchd [47]
curl -s -H "Authorization: Bearer $KEY" -H 'content-type: application/json' \
  -d '{"input":"review PR #123 for correctness","model":"openai/gpt-5.5"}' \
  http://127.0.0.1:8642/v1/runs     # -> run_id; stream /v1/runs/{id}/events [49]
```
Python side: a `runner/providers/hermes.py` adapter that shells out with
`--format stream-json --usage-file run.usage.json`, maps `tool.started/tool.completed` into
our audit log, reads `estimated_cost_usd` from the usage file into the job's cost envelope
[41], and treats Hermes' stdout as untrusted data. Do not install `claude-subscription-
directsdk` in the sidecar: it would run a second Agent SDK consumer against the same Max
allowance with Claude's native tools disabled [71]. Keep Telegram on our bot; do **not** enable Hermes'
Telegram adapter with the same bot token (two long-pollers on one token is undefined;
Hermes' Telegram doc does not cover sharing) [48].

Option B — OpenClaw as a channel/provider layer (only if we want WhatsApp/Signal/iMessage)
```bash
curl -fsSL https://openclaw.ai/install.sh | bash            # Node 26 [22]
openclaw setup --baseline && openclaw onboard               # choose "Claude CLI" for Anthropic [4]
openclaw config set gateway.http.endpoints.chatCompletions.enabled true   # [11]
openclaw agent --agent research --message-file ./task.md --json --timeout 1800   # [13]
openclaw automations create "0 13 * * 3" --name atlas-research --session isolated \
  --message "run the Wednesday research loop" --deliver --channel telegram      # [14]
```
Gotchas: the HTTP token is *full operator access* — loopback only [11]; sandbox is off by
default and the Gateway never sandboxes itself [20]; pairing-flow CVE class means pin to
≥ the patched release — the maintained extended-stable line (v2026.7.35, Sep 21 2026) is the
natural pin for a server [72] — and run `openclaw security audit` on every deploy [19][30]; Google
OAuth is dead, use API keys [8]; commits or prompts that mention "OpenClaw" have been
reported to trip Claude-side heuristics [34].

Task-class fit (H = Hermes sidecar, O = OpenClaw):
research — H via Codex/Grok OAuth + Firecrawl, good; coding — O's ACP (Claude Code/Codex
harness) or H `-z` worktree mode, fine but no better than our SDK; code review — H as a
second-model reviewer, good; chat — neither needed (our Telegram bot + SDK); routing/
classification — H fallback chains + credential pools, good; adversarial review — H with a
different vendor's model, good; trading research — either only as scheduler/delivery,
data must come from our own connectors.

Cross-cutting gotchas: both persist secrets in dotfiles (`~/.openclaw/openclaw.json`,
`~/.hermes/.env`) [4][40] — keep them out of the repo and the sync-learnings path; both
run a 24/7 Node/Python daemon on a 16 GB machine alongside Postgres/Redis/launchd jobs and
neither documents RAM (unverified; budget ~0.5–1 GB each); Hermes' memory files are
hard-capped and error on overflow [45]; OpenClaw's `--local` locks the state dir and cannot
coexist with a running Gateway [13].

## 8. Verdict

1. Both are mature, free, MIT runtimes that already ship the channel/memory/cron/provider
   layer this decision targets; OpenClaw is the larger, riskier, TypeScript control plane,
   Hermes the smaller Python one with better headless and credential ergonomics.
2. Hermes now ships an experimental `claude-subscription-directsdk` plugin (Hermes ≥ 0.21.4,
   published ~Sep 21 2026) that runs turns on a Claude Pro or Max subscription through the
   installed, logged-in Claude Code CLI (Agent SDK path, billed to the subscription's Agent
   SDK allowance, credential files never read); it duplicates rather than adds to our existing
   Claude Agent SDK path, and native Claude tools/skills are disabled in it [71]. Their value
   to us therefore remains OAuth access to Codex/Grok/MiniMax/Qwen and rotation/fallback
   across them — not a new Claude path.
3. OpenClaw's 2026 record (Google bans, Anthropic cutoff/reversal, critical pairing CVE,
   "security nightmare" discourse) argues against making it our trust boundary.
4. Hermes' trust signals are weaker (plagiarism handling, thin community, state.db patches)
   but its blast radius as a loopback sidecar is small and its `stream-json` / `/v1/runs`
   surfaces map cleanly onto our job runner and audit log.
5. Borrow: delivery ledger, per-run cost envelope (OpenClaw `costUsd`, Hermes `--usage-file`
   `estimated_cost_usd`) [13][41], cron-time injection scanning, secret redaction on delivery,
   credential pools, Docker `internal: true` + proxy-allowlist egress pattern [76] — implement
   natively in `src/runner`.

Fit scores (1–10): research 6 (H) / 6 (O); coding/agentic 6 (H) / 7 (O, via ACP harnesses);
cost efficiency 8 (both free; Portal Plus $22 credits stretches) ; automation friendliness
8 (H) / 7 (O); trading research 3 (both — scheduler only).

## 9. Sources (all accessed 2026-09-24)

1. https://docs.openclaw.ai/
2. https://github.com/openclaw/openclaw
3. https://docs.openclaw.ai/providers
4. https://docs.openclaw.ai/providers/anthropic
5. https://docs.openclaw.ai/providers/openai
6. https://docs.openclaw.ai/providers/openai/models
7. https://docs.openclaw.ai/providers/xai
8. https://docs.openclaw.ai/providers/google
9. https://docs.openclaw.ai/concepts/architecture
10. https://docs.openclaw.ai/gateway
11. https://docs.openclaw.ai/gateway/openai-http-api
12. https://docs.openclaw.ai/cli
13. https://docs.openclaw.ai/cli/agent
14. https://docs.openclaw.ai/automation/cron-jobs
15. https://docs.openclaw.ai/concepts/memory
16. https://docs.openclaw.ai/concepts/multi-agent
17. https://docs.openclaw.ai/concepts/agent-runtimes
18. https://docs.openclaw.ai/tools/acp-agents
19. https://docs.openclaw.ai/gateway/security
20. https://docs.openclaw.ai/gateway/sandboxing
21. https://docs.openclaw.ai/channels/telegram
22. https://docs.openclaw.ai/install
23. https://docs.openclaw.ai/platforms/macos
24. https://docs.openclaw.ai/releases
25. https://docs.openclaw.ai/clawhub
26. https://clawhub.ai/search?q=trading
27. https://openclaw.ai/blog/introducing-openclaw
28. https://openclaw.ai/blog (index: Foundation Jul 8 2026; NVIDIA Jun 1; Trail of Bits audit Sep 21; LTS Jul 30)
29. https://docs.z.ai/devpack/tool/openclaw
30. https://github.com/advisories?query=CVE-2026-33579
31. https://news.ycombinator.com/item?id=47633396 (Anthropic no longer allowing Claude Code subscriptions to use OpenClaw, 2026-04-03)
32. https://news.ycombinator.com/item?id=47844269 (Anthropic says OpenClaw-style Claude CLI usage is allowed again, 2026-04-21)
33. https://news.ycombinator.com/item?id=47115805 (Google restricting AI Pro/Ultra subscribers for using OpenClaw, 2026-02-22)
34. https://news.ycombinator.com/item?id=47963204 (Claude Code refuses requests or charges extra if commits mention "OpenClaw", 2026-04-30)
35. https://news.ycombinator.com/item?id=47479962 (OpenClaw is a security nightmare dressed up as a daydream, 2026-03-22)
36. https://www.jakequist.com/thoughts/openclaw-is-what-apple-intelligence-should-have-been (HN 46893970)
37. https://hermes-agent.nousresearch.com/
38. https://github.com/NousResearch/hermes-agent
39. https://github.com/NousResearch/hermes-agent/releases
40. https://hermes-agent.nousresearch.com/docs/integrations/providers
41. https://hermes-agent.nousresearch.com/docs/reference/cli-commands
42. https://hermes-agent.nousresearch.com/docs/user-guide/cli
43. https://hermes-agent.nousresearch.com/docs/user-guide/features/cron
44. https://hermes-agent.nousresearch.com/docs/guides/cron-script-only
45. https://hermes-agent.nousresearch.com/docs/user-guide/features/memory
46. https://hermes-agent.nousresearch.com/docs/user-guide/security
47. https://hermes-agent.nousresearch.com/docs/user-guide/messaging
48. https://hermes-agent.nousresearch.com/docs/user-guide/messaging/telegram
49. https://hermes-agent.nousresearch.com/docs/user-guide/features/api-server
50. https://hermes-agent.nousresearch.com/docs/developer-guide/programmatic-integration
51. https://hermes-agent.nousresearch.com/docs/user-guide/features/subscription-proxy
52. https://hermes-agent.nousresearch.com/docs/user-guide/features/credential-pools
53. https://hermes-agent.nousresearch.com/docs/user-guide/features/delegation
54. https://hermes-agent.nousresearch.com/docs/user-guide/sessions
55. https://hermes-agent.nousresearch.com/docs/guides/xai-grok-oauth
56. https://hermes-agent.nousresearch.com/docs/integrations/nous-portal
57. https://portal.nousresearch.com/ (tier table; /pricing and /models returned HTTP 429)
58. https://hermes-agent.nousresearch.com/docs/getting-started/installation
59. https://hermes-agent.nousresearch.com/docs/getting-started/platform-support
60. https://hermes-agent.nousresearch.com/docs/reference/model-catalog
61. https://hermes-agent.nousresearch.com/docs/reference/skills-catalog
62. https://hermes-agent.nousresearch.com/docs/reference/faq
63. https://hermes-agent.nousresearch.com/docs/user-guide/docker
64. https://hermes-agent.nousresearch.com/docs/llms.txt
65. https://news.ycombinator.com/item?id=48419000 (Hermes Agent – open-source AI agent with persistent memory, 2026-06-05)
66. https://news.ycombinator.com/item?id=48187581 (Nous Research edits GitHub issue to remove plagiarism claims, 2026-05-19)
67. https://huggingface.co/NousResearch
68. https://hn.algolia.com/api/v1/search?query=openclaw&tags=story (story index used for points/dates)
69. https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan (paused as of June 15 2026)
70. https://support.claude.com/en/articles/11145838-using-claude-code-with-your-pro-or-max-plan (updated Aug 19 2026)
71. https://hermes-agent.nousresearch.com/docs/plugins/claude-subscription-directsdk (Experimental, v0.3.0, added Sep 20 / updated Sep 23 2026)
72. https://github.com/openclaw/openclaw/releases (v2026.9.6 Sep 23; v2026.7.35 extended-stable Sep 21; v2026.9.5 Sep 19)
73. https://openclaw.ai/blog/openclaw-2-accidentally (Aug 30 2026)
74. https://news.ycombinator.com/item?id=49505310 (OpenClaw 2.0, Accidentally — 148 pts, 2026-08-31)
75. https://techcrunch.com/2026/07/13/hermes-agent-maker-nous-research-in-talks-for-new-funding-at-1-5b-valuation/ (HN 48903272)
76. https://hermes-agent.nousresearch.com/docs/user-guide/egress/network-isolation
77. https://news.ycombinator.com/item?id=49509882 (Claude 20x usage is only for the 5-hour window, 15 pts, 2026-08-31); https://news.ycombinator.com/item?id=49510223 and ?id=49547952 (Anthropic sued over Claude Max limits, CNET, 7 / 4 pts)

Not found — searched: OpenClaw MCP-client page (docs.openclaw.ai/tools fetched 2026-09-24: no
MCP section); Composio
security article body (composio.dev, 404; HN thread used instead); NVD/CVE.org record body
(returned shells; GitHub advisory used); Nous Portal per-model prices (HTTP 429).

## Verification log (2026-09-24)

**Corrections applied from the fact-check list: 17** — 9 major, 8 minor.
- Major (9): Anthropic support article 15036540 located and cited (§3 OpenClaw terms history);
  Anthropic primary-source note added to the §3 conflict paragraph; Verdict #2 rewritten for the
  Hermes `claude-subscription-directsdk` plugin; Hermes auth modes extended with the plugin (§3);
  OpenClaw "use an API key for shared production automation" caveat added to the §7 rationale;
  OpenClaw's Apr 21 "Anthropic still blocks parts of our system prompt" qualifier added (§3);
  Portal per-model prices for Claude/OpenAI captured (§4); "premium" example re-labelled as
  GPT-4o-class 2024 pricing with a ~4× frontier row added (§4); Hermes exit codes and
  `--usage-file` enumerated (§3).
- Minor (8): OpenClaw one-shot timeout key and exit 0/1/2 (§3); Subscription Proxy provider
  scope `nous|xai` and out-of-scope Anthropic transformation (§3); Portal free-model examples
  (§4); `/v1/responses` enable key (§2); OpenClaw release cadence incl. extended-stable
  v2026.7.35 and 2.0 (§1); six 500+-point HN threads plus the 2.0 thread (§5); Hermes
  messaging-platform count (§1); OpenClaw announcement date Jan 29 vs HN Jan 30 (§1).

**Missing topics added (12):** Anthropic Agent SDK policy status + planned credit table [69] and
Pro/Max API-rate billing [70] (§3); Hermes directsdk plugin [71] (§3, §4, §7, §8); OpenClaw 2.0
release facts [73] and HN sentiment thread [74] (§1, §2, §5); extended-stable line as the pin
target [72] (§1, §7); Hermes `--usage-file` cost envelope [41] (§3, §5, §7, §8); Hermes macOS
Apple-Silicon-only [58] (§5); OpenClaw MCP status from docs.openclaw.ai/tools + `agent`
reference [13] (§2); Hermes network egress isolation guide [76] (§3, §8); "Decision models in
OpenClaw" Sep 22 post [28] (§1); Nous Research $1.5B funding talks [75] (§5); Claude Max
usage-limit suit HN reports [77] (§4, cross-ref claude-anthropic.md).

**Claims re-verified with sources:** Anthropic pause statement and credit amounts
(support.claude.com 15036540); Pro/Max article "billed at standard API rates", updated Aug 19
2026 (support.claude.com 11145838); directsdk install command, ≥ 0.21.4, Pro/Max, Agent SDK
allowance, native tools disabled, single-request admission, Experimental v0.3.0
(hermes-agent.nousresearch.com/docs/plugins/claude-subscription-directsdk); Hermes exit codes
0/1/130/75 and -z 0/2/1/130, `--usage-file` fields (docs/reference/cli-commands); Apple Silicon
only (docs/getting-started/installation); Squid allowlist + `internal: true`
(docs/user-guide/egress/network-isolation); proxy `--provider nous|xai` and Anthropic
out-of-scope quote (docs/user-guide/features/subscription-proxy); OpenClaw `responses.enabled`
(docs.openclaw.ai/gateway/openai-http-api); `agents.defaults.timeoutSeconds`, exit 0/1/2, "bundled
MCP loopback resources" (docs.openclaw.ai/cli/agent); Anthropic page default Opus 5.5, "shared
production automation" sentence, link to article 15036540 (docs.openclaw.ai/providers/anthropic);
releases v2026.9.6 Sep 23 / v2026.7.35 Sep 21 / v2026.9.5 Sep 19 (github.com/openclaw/openclaw/
releases); 2.0 post: ~7-week pause, 16,000+ PRs, 933 contributors, browser app, shared cloud
sessions (openclaw.ai/blog/openclaw-2-accidentally); HN 49505310 148 pts / 175 comments and
migration comments; six 500+-point OpenClaw threads (hn.algolia.com); Portal prices Fable 5.1
$10/$50, Opus 4.1 $15/$75, 3 Haiku $0.25/$1.25, GPT-4o $2.50/$10, Llama 3.1 8B $0.02/$0.04,
$0.00 models (portal.nousresearch.com); Nous funding (TechCrunch Jul 13 2026, HN 48903272);
Claude Max suit threads HN 49509882 / 49510223 / 49547952.

**Stale / unverified flags left in place (marked "(unverified as of 2026-09-24)"):** Hermes
Docker hardening specifics (dropped caps, no-new-privileges, 256-process limit, tmpfs /tmp);
HN username attributions in §5 (35, 31/32/34 threads); Jake Quist "killer app for Mac hardware"
phrase; Nous Portal 200+ vs 300+ model count; OpenClaw TUI surface and Node 24/26 RAM figures;
Hermes providers page vs directsdk page disagreement on Claude Pro; OpenClaw providers index
`claude-opus-4-6` vs Anthropic page Opus 5.5 default (doc drift); no Anthropic statement newer
than June 15 2026 on the Agent SDK policy; Apr 30 "commits mention OpenClaw" incident with no
confirmed resolution; "steer-vs-queue" wording of the Sep 22 decision-models post; Hermes
messaging-platform exact count (34 per fact-checker vs 31 on recount). Web-search budget was
exhausted (200/200) during this pass; all re-verification used direct page fetches.

**Fact-checker's overall quality rating: acceptable.**
