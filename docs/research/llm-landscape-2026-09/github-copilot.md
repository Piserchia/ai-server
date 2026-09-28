# GitHub Copilot (Pro/Pro+ plans, Copilot CLI, coding agent / cloud agent) — research (as of 2026-09-24)

Method note: this session's web-search budget was exhausted before this task started, so every fact below comes from direct fetches of primary pages (docs.github.com, github.blog, githubstatus.com API, the copilot-cli/copilot-sdk repos, GitHub Community discussions, HN Algolia API) plus `gh api`, `npm view` and `pip index`. Reddit blocks this host; community sentiment is drawn from GitHub Community discussions and HN instead. Numbers not found are marked as such. Newer-than-doc sweep (unverified as of 2026-09-24 beyond direct fetches): the github.blog Copilot changelog shows nothing after 2026-09-23 ("More ways to request and configure Copilot code reviews", "Local sandboxing in the GitHub Copilot app"); no new models or price changes found between 09-22 and 09-24.

## 1. Snapshot

- **Company**: GitHub (Microsoft subsidiary). Copilot is a model *aggregator + agent harness*, not a model vendor: it fronts OpenAI, Anthropic, Google, xAI, Moonshot and Microsoft models behind one login and one billing meter [5][6].
- **Billing regime (important, changed 2026-06-01)**: "premium requests" were retired; all plans now consume **GitHub AI Credits**, `1 AI credit = $0.01 USD`, metered on input, output, cached-input and (for Anthropic and GPT-5.6/GPT-6 models) cache-write tokens at each model's published list rate [1][3][7][8]. Several older docs pages still describe 300/1,500 premium requests at $0.04 overage [9] — that is the legacy regime (annual plans only, until they expire and drop to Free [7]).
- **Current model lineup** (Copilot model picker, 32 models, exact names as listed) [5]:
  - OpenAI: GPT-5 mini, GPT-5.3-Codex, GPT-5.4, GPT-5.4 mini, GPT-5.4 nano, GPT-5.5, GPT-5.6 Luna, GPT-5.6 Sol, GPT-5.6 Terra, GPT-6 Astra, GPT-6 Luna, GPT-6 Sol.
  - Anthropic: Claude Haiku 4.5, Claude Sonnet 4.6 (retired 2026-09-01; remains only for individual subscribers on legacy annual Pro/Pro+ plans, not available on monthly plans), Claude Sonnet 5, Claude Opus 4.7, Claude Opus 4.8, Claude Opus 4.8 (fast mode, preview), Claude Opus 5, Claude Opus 5.5, Claude Fable 5, Claude Fable 5.1.
  - Google: Gemini 3.5 / 3.6 / 3.7 / 3.8 Flash. Microsoft: MAI-Code-1.1-Flash. Moonshot: Kimi K2.7 Code, Kimi K3. xAI: Grok 4.5, 4.6, 4.7.
  - Model IDs as passed on the CLI/SDK are lower-cased slugs (`gpt-5`, `claude-sonnet-4.5`, `kimi-k3` appear in SDK docs and the CLI changelog) [18][20]; GitHub does not publish a canonical ID table (unverified beyond those examples; the slugs used in §7 — `claude-sonnet-5`, `gpt-6-sol` — are inferred and unverified as of 2026-09-24).
- **Context windows**: most frontier models are listed with a "1 million token context window" and "configurable reasoning levels" [5]. Pricing is tiered: a `default` tier (≤272K tokens for GPT-5.4/5.5/5.6/6, ≤200K for Grok and GPT-5.6 Luna) and a `long_context` tier at 2× the input/cached-input rate but only 1.5× the output rate for the GPT models (e.g. GPT-5.4 $15.00 → $22.50 out, GPT-6 Sol $10.00 → $15.00 out), and 2× across input, cached and output for Grok [4]; selected per session via `--context default|long_context` [10]. **Surface gating**: the 1M-token context window is available *only* in VS Code and Copilot CLI; configurable reasoning levels only in VS Code, CLI and the cloud agent [5] — the SDK rides on the CLI runtime, so both reach it, but GitHub.com chat, the Copilot app and cloud-agent long-context runs do not. **Knowledge cutoffs: Not found** — Copilot docs do not state them; searched supported-models, model-comparison, model-hosting pages.
- **Modalities**: text + images (JPEG/PNG/GIF/WEBP/HEIC/HEIF) + PDF attachments in CLI [16]; vision requires the selected model and org policy to allow it [10].
- **Release cadence**: extremely fast. CLI ships ~1–3 releases/week (1.0.68 on 2026-07-01 → 1.0.88 on 2026-09-22; 1.0.89 pre-releases on npm 2026-09-23) [18][63]. New models land within days of vendor release (Claude Opus 5.5 and GPT-6 Sol/Luna 2026-09-22, Grok 4.7 2026-09-21, GPT-6 Astra GA 2026-09-04) [43]. Deprecations are equally fast: Gemini 3.5/3.6 Flash, **Kimi K2.7 Code** and Claude Opus 4.7 are removed 2026-10-02 (replacements: Gemini 3.8 Flash, Kimi K3, Claude Opus 5) [37]. (The 2026-10-02 date comes from the changelog body table and the supported-models retirement table; the changelog page header reads "Retired September 3, 2026", its URL slug says September 18 and its title says "mid-October" — a GitHub-side inconsistency, unverified which is authoritative as of 2026-09-24.) Retirement history as churn evidence: Claude Opus 4.5, Opus 4.6, Sonnet 4.5 and Sonnet 4.6 (monthly plans), Gemini 3.1 Pro and Raptor mini all retired 2026-09-01; MAI-Code-1-Flash retired 2026-09-10; GPT-5.2/5.2-Codex 2026-06-05; GPT-4.1 2026-06-01 — nine retirements in the last four months [5].
- **Positioning**: the cheapest legitimate way to get one OAuth login that reaches Claude, GPT, Gemini, Grok and Kimi inside a first-party agent harness (CLI + SDK + cloud agent) with GitHub-native tooling (repo, PR, issues, Actions, MCP). Since June 2026 it is no longer a "flat-rate unlimited" product: it is usage-based billing with a modest included allowance (1.5–2× the subscription price in credits) and undisclosed hourly/weekly rate limits [3][32][53].

## 2. Interfaces & surfaces

| Surface | Status / notes | Source |
|---|---|---|
| **IDE plugins** | VS Code, Visual Studio, JetBrains, Xcode, Eclipse (Kimi/Grok changelogs list all of them as clients) | [36][38] |
| **Copilot app (desktop)** | Standalone agent-session desktop app, macOS/Windows/Linux, GA for every plan 2026-07-07; local sandboxing (public preview 2026-09-23); OpenTelemetry export (2026-09-22) | [44][61][43] |
| **Web** | Copilot Chat on github.com + "Agents" panel; merging with cloud agent and Mobile into one experience no earlier than 2026-09-28, chat history then persists for account lifetime instead of 28 days | [40] |
| **Mobile** | GitHub Mobile iOS/Android: chat, start cloud-agent tasks, and **remote-control a local CLI session** (approve tool calls, answer questions, send prompts) | [30][36] |
| **CLI** | `copilot` (Node, `npm i -g @github/copilot`, `brew install copilot-cli`, or `curl -fsSL https://gh.io/copilot-install \| bash`), GA 2026-02-25 (date unverified as of 2026-09-24 — not re-fetched this pass; changelog slug matches), current 1.0.88 | [17][42][63] |
| **SDK** | `@github/copilot-sdk` (Node), `github-copilot-sdk` (Python, 1.0.14, Python 3.11+), Go, .NET, Java, Rust; GA 2026-06-02; embeds the CLI runtime as a JSON-RPC subprocess. The CLI is auto-bundled/staged only for **Node, Python and .NET** (Python: `python -m copilot download-runtime`, else staged on first use); **Go, Java and Rust need a separately installed `copilot` on PATH**. Auth accepts a `github_token_provider` callable that returns rotating session-scoped tokens (`accessToken` + positive `expiresIn`; production tokens ~8 h; refreshed only before the next credential-consuming operation; mutually exclusive with `github_token`) | [19][20][22][63] |
| **ACP server** | `copilot --acp --stdio` or `--acp --port N`; NDJSON; streaming chunks + `requestPermission` callbacks; for editors/scripts | [14] |
| **Cloud agent (ex "coding agent")** | Runs in an ephemeral GitHub Actions environment; triggers: issue assignment, `@copilot` PR comments, Agents panel, VS Code, Mobile, Slack/Teams @mention, **Automations** (schedule/hourly/daily/weekly or issue/PR events); hard 59-minute cap; one repo/branch/PR per task | [23][24] |
| **GitHub Agentic Workflows** | Markdown-defined Actions workflows (`on: daily` etc.) with `engine: copilot \| claude \| codex \| gemini`; default cap 1,000 credits/run; public preview | [25] |
| **Third-party agents** | Delegate GitHub tasks to "Anthropic Claude" (Claude Agent SDK, Opus 4.7/Sonnet 4.6/Auto as of 2026-09-24 per [28] — likely to change imminently: Opus 4.7 is deprecated 2026-10-02 and Sonnet 4.6 was retired 09-01 for monthly plans) or "OpenAI Codex" **billed from Copilot credits**, Pro/Pro+/Max/Business/Enterprise, public preview | [27][28] |
| **MCP** | GitHub MCP server pre-configured; Playwright MCP default in cloud agent; user/project `mcp-config.json`; `copilot mcp add --transport http NAME URL`; MCP spec 2026-07-28 supported; OAuth device-code + `client_credentials` for headless MCP auth | [15][16][18][23] |
| **Scheduled / automated** | CLI `/every TIME` and `/after DELAY` in-session schedulers; cloud Automations; Agentic Workflows; `/delegate` or `&` prefix hands a local task to the cloud agent | [16][24][25][42] |
| **Memory** | CLI `--enable-memory` (off by default in `-p` mode); SDK `memory={}`; "repository memory" | [10][20][42] |
| **Projects/workspaces** | Copilot Spaces (all plans); `--worktree` isolated git worktrees; sessions stored under `~/.copilot/session-state/` | [1][10][13] |
| **Messaging** | Slack and Microsoft Teams (@mention to start cloud-agent tasks). **Telegram / WhatsApp / Discord: Not found** (searched cloud-agent, plans, changelog pages) | [23] |
| **Voice** | Not found (searched plans, app, CLI docs) | — |
| **API / OpenAI-compatible endpoint** | **None official.** GitHub Models (the free OpenAI-compatible inference API) was fully retired 2026-07-30 [57]. The sanctioned programmatic paths are the CLI `-p` mode, the SDK, and ACP. Community bridges exist (e.g. an "OpenAI API compatible server that uses GitHub Copilot SDK", Show HN 2026-01-27) — grey area, see §3 | [57][64] |
| **Batch API / structured outputs** | None. CLI `--output-format=json` emits JSONL; SDK emits typed events. No JSON-schema-constrained outputs | [10][20] |
| **Tool use** | Built-in shell/file/web tools + custom tools (`@define_tool` with Pydantic schema in Python) + MCP + skills + hooks (pre/post tool use, session start, permission) | [20][22] |
| **Computer-use / browser** | Playwright MCP in cloud agent; no first-party OS computer-use | [23] |
| **BYOK** | `COPILOT_PROVIDER_TYPE=openai\|azure\|anthropic`, `COPILOT_PROVIDER_BASE_URL`, `COPILOT_PROVIDER_API_KEY`, `COPILOT_MODEL`; Ollama/vLLM/Foundry Local; GitHub login optional in BYOK mode; `COPILOT_OFFLINE=true` stops the CLI contacting GitHub at all (telemetry off, talks only to the configured provider — BYOK-only/air-gapped operation); `copilot help environment` (also `help billing|config|commands|logging|monitoring|permissions|providers|sandbox`) is the canonical env-var reference — the docs pages list only `COPILOT_GITHUB_TOKEN`/`GH_TOKEN`/`GITHUB_TOKEN`, `COPILOT_HOME`, `COPILOT_ENABLE_INTERRUPTED_SESSION_RESTORE` and defer the rest to it | [10][15][41] |

## 3. Headless / server automation fit

**Non-interactive mode** is first-class: `copilot -p "PROMPT"` (or piped stdin) runs one task and exits; the exit summary prints a `copilot --resume=SESSION-ID` hint [10][12]. Relevant flags [10]:

- `--output-format=json` → JSONL, one JSON object per line (event schema **not documented**; use the SDK for typed events).
- `-s/--silent` → response only, no usage stats. `--no-ask-user` → never asks clarifying questions. `--autopilot` / `--mode autopilot` and `--plan --mode autopilot` (plan-then-run without human approval); `--max-autopilot-continues=N`.
- Permissions: `--allow-all` (= `--allow-all-tools --allow-all-paths --allow-all-urls`, alias `--yolo`), `--allow-tool='shell(git)'`, `--deny-tool='write(PATH)'`, `--allow-url`, `--deny-url`, `--available-tools`, `--excluded-tools`, `--disable-builtin-mcps`, `--add-dir=PATH`, `--disallow-temp-dir`, `--secret-env-vars=VAR`.
- Cost/context control: `--model=MODEL|auto`, `--effort=low|medium|high|xhigh|max`, `--context default|long_context`, `--max-ai-credits=N` (soft per-*session* cap, minimum 30; a response already in progress completes before the session stops, so actual spend can slightly exceed N; in `-p` mode the run ends when the limit is reached; interactive equivalent `/limits set max-ai-credits N`) [31].
- Session: `--resume=ID`, `--session-id UUID`, `--continue`, `--worktree[=NAME]`, `--share=PATH` (Markdown transcript), `--share-gist`, `--log-dir`, `--log-level`.
- Misc: `--stream on|off` (default on), `--attachment PATH`, `--fleet` (parallel sub-agents on a low-cost model by default) [29], `--remote` (steer from Mobile) [30], `--no-auto-update`.
- Env: `COPILOT_TASK_WAIT_TIMEOUT_SECONDS` bounds how long `-p` waits for background tasks; non-zero exit when a prompt is blocked or a `--share` export fails [18].

**Auth modes** [10][11][17][18]:
1. `copilot login` — browser flow on a desktop terminal; **OAuth device-code flow (RFC 8628) is the default on remote/headless terminals** and can be forced with `--device-code`; `--with-token` reads a token from stdin. Credentials persist in `~/.copilot` (`COPILOT_HOME` to relocate).
2. Fine-grained PAT with the **"Copilot Requests"** permission, supplied via `COPILOT_GITHUB_TOKEN` > `GH_TOKEN` > `GITHUB_TOKEN` (that precedence order). Both token values are redacted from output by default.
3. SDK: reuses the CLI's stored OAuth login (`use_logged_in_user=True`), or `CopilotClient(github_token=...)`, or an OAuth GitHub App user token, or BYOK (no GitHub auth needed) [19][20].
4. In GitHub Actions, the workflow `GITHUB_TOKEN` is recommended (installation identity; personal-repo runs bill the repo owner's seat) [26].

**May a consumer subscription be used programmatically?** Yes, explicitly. The SDK is "available to all existing GitHub Copilot subscribers, including Copilot Free for personal use" and "billing … is based on the same model as the Copilot CLI, with each prompt being counted towards your usage allowance" [19] (the quote is from the copilot-sdk README, not the GA changelog post [22] — citation corrected 2026-09-24). The Generative AI Services Terms (effective 2026-03-05, replacing the Copilot Product-Specific Terms) say you are "solely responsible for any application or agent you create using (or for use with) Generative AI Services" (§5.B) and defer acceptable use to the AUP and Microsoft AI Code of Conduct (§5.A) [34]. Nothing found prohibits headless use of an individual plan. What *is* discouraged: GitHub ToS §H — "Abuse or excessively frequent requests to GitHub via the API may result in temporary or permanent suspension"; ToS §B.3 bans bot-registered accounts (machine accounts owned by a human are fine) [33]; the rate-limits page tells you to reduce "frequent or automated requests (for example, rapid-fire completions or large-scale usage)" [32]. **Unofficial clients** (opencode/goose logging in with Copilot's device flow [56]): not addressed in any GitHub term I could find — a grey area; the SDK is the sanctioned equivalent and is what I recommend.

**Rate limits and caps**: no numeric limits are published [32]. Since 2026-04-17 individual plans carry "hourly + weekly" rate limits in addition to the monthly credit allowance; users report multi-hour lockouts with quota remaining ("You've hit your session rate limit") and GitHub closed the 484-comment thread by redirecting to the FAQ [53][54]. Pro+ is stated to have "more than 5X the limits of Pro" and "priority access" to premium models [2][53]. When credits run out you either upgrade, set a paid budget ($0.01/credit), or wait for the 1st-of-month UTC reset; unused credits are forfeited [3].

**Sandboxing**: OS-level local sandbox (`--sandbox`, experimental; `/sandbox enable`) restricting filesystem, network and credentials; on macOS/Linux **sandboxed commands cannot reach localhost** unless "Allow local network" is enabled — this matters for a box running Postgres/Redis on 127.0.0.1 [16][18]. Cloud isolation via `copilot --cloud`. No official Docker image (issue #55 open since 2025-09) [59]. Known permission-bypass class: PromptArmor showed `env curl … | sh` slipping past the approval allow-list via indirect prompt injection (2026-02-27 — date unverified as of 2026-09-24; the writeup shows a report-submitted date of 2026-02-25 and no explicit publication date); GitHub called it "a known issue that does not present a significant security risk" [47].

**Structured events for orchestration**: SDK events `assistant.message`, `assistant.message_delta`, `assistant.reasoning(_delta)`, `tool.call`, `permission.requested`, `session.idle`, `session.compaction_start/complete`, `assistant.usage` (input/output tokens, multiplier), `session.usage_info`; RPC `session.usage.getMetrics` returns session-wide credit cost (reported in "nano-AI units", `totalNanoAiu`) [20][21]. **Session resume**: `client.resume_session(id)`; state under `~/.copilot/session-state/{id}/` [13][20]. **Streaming**: `streaming=True` in SDK; `--stream` in CLI [10][20].

## 4. Cost

**Individual plans (monthly; whether NEW annual purchases are closed since June 2026 is unverified as of 2026-09-24 — the usage-based-billing post only says existing annual subscribers keep request-based pricing until expiry, and the supported-models page still references legacy annual Pro/Pro+ plans)** [1][2][3][7]:

| Plan | $/mo | Base credits | Flex credits | Total ($ value) | Notes |
|---|---|---|---|---|---|
| Free | $0 | "an allowance" (number **not found**; searched plans, usage-limits, FAQ) | — | — | 2,000 completions/mo; Auto model only; limited chat/agent; CLI + app included [2] |
| Student | $0 | 200 | — | 200 ($2) | Auto model only; unlimited completions [55] |
| Pro | $10 | 1,000 | 500 | 1,500 ($15) | "A selection of models" — the supported-models per-plan matrix marks as NOT included on Pro: Claude Opus 4.7, 4.8, 4.8 (fast mode), 5, 5.5; Claude Fable 5 and 5.1; GPT-5.5; GPT-5.6 Sol; GPT-6 Sol; GPT-6 Astra; GPT-5.4 nano. Included on Pro: Claude Haiku 4.5, Claude Sonnet 5 (and legacy-annual-only Sonnet 4.6), Gemini 3.5–3.8 Flash, GPT-5 mini, GPT-5.3-Codex, GPT-5.4, GPT-5.4 mini, GPT-5.6 Luna, GPT-5.6 Terra, GPT-6 Luna, Grok 4.5–4.7, Kimi K2.7 Code, Kimi K3, MAI-Code-1.1-Flash [5]; cloud agent, automations, CLI, SDK, code review |
| Pro+ | $39 | 3,900 | 3,100 | 7,000 ($70) | "Access to premium models" (the plans page reserves "Priority access to premium models" for Max and Enterprise), third-party agent delegation, >5× Pro's rate limits per GitHub staff (April 2026) [53] |
| Max | $100 | 10,000 | 10,000 | 20,000 ($200) | "sustained agent-driven workflows" |
| Business | $19/seat | 1,900 per user per month ("pooled" org-level sharing unverified as of 2026-09-24; the plans page says "Total per user per month: 1,900") | — | $19 | Upfront per-seat charge from 2026-10-01; signups re-opened 2026-09-01 [40] |
| Enterprise | $39/seat | 3,900 per user per month (pooling unverified as of 2026-09-24) | — | $39 | Kimi models ship **off by default** for Business/Enterprise; an admin must enable the model policy (Kimi K2.7 changelog [36]); Grok 4.7 follows the normal default-enablement rule [38] |

- Flex credits cost nothing extra but "may change over time" / "designed to adapt as the economics of AI evolve" [1][3][52] — treat them as a soft promise.
- Additional usage: set a dollar budget; billed at **$0.01 per credit** = the same list rate as the included credits [3]. Copilot's overage *is* API-list pricing ("Copilot now bills usage at listed API rates") [45].
- **Auto model selection** gives a 10% discount on paid plans and is configurable to `efficiency | balance | intelligence` [39]. Cached input ≈ 10% of input price; cache *writes* are billed separately at 1.25× the input rate for every Anthropic model and for GPT-5.6/GPT-6 (e.g. Claude Sonnet 5 $2.50, Claude Opus 5.5 $5.00, Claude Fable 5.1 $12.50, GPT-6 Sol $2.50, GPT-6 Luna $0.125 per 1M cache-write tokens); earlier OpenAI models, Gemini, Grok, Kimi and MAI have no cache-write charge [4][60]. Code completions/NES never consume credits [7].
**Per-plan model availability (supported-models "Available models" table, 32 rows; Free/Student get auto-selection only)** [5]:

| Model group | Pro | Pro+ | Max | Business | Enterprise |
|---|---|---|---|---|---|
| Claude Opus 4.7 / 4.8 / 4.8 fast (preview) / 5 / 5.5 | Not included | ✓ | ✓ | ✓ | ✓ |
| Claude Fable 5 / 5.1 | Not included | ✓ | ✓ | ✓ | ✓ |
| GPT-5.5, GPT-5.6 Sol, GPT-6 Sol, GPT-6 Astra | Not included | ✓ | ✓ | ✓ | ✓ |
| GPT-5.4 nano (Codex VS Code extension only) | Not included | ✓ | ✓ | Not included | Not included |
| Claude Sonnet 4.6 (legacy annual only) | ✓ (annual) | ✓ (annual) | Not included | Not included | Not included |
| Claude Haiku 4.5, Claude Sonnet 5, Gemini 3.5–3.8 Flash, GPT-5 mini, GPT-5.3-Codex, GPT-5.4, GPT-5.4 mini, GPT-5.6 Luna, GPT-5.6 Terra, GPT-6 Luna, Grok 4.5–4.7, Kimi K2.7 Code, Kimi K3, MAI-Code-1.1-Flash | ✓ | ✓ | ✓ | ✓ | ✓ |

Org plans additionally gate by policy: Kimi models are off by default for Business/Enterprise until an admin enables the model policy [36]; new models otherwise default-enable unless the admin disabled the global default [38]. This matrix, not credit volume, is what decides Pro vs Pro+ for us (§7).

- Legacy conflict: the still-published "copilot-requests" page says Pro = 300 and Pro+ = 1,500 premium requests with $0.04 overage and "13 premium requests per code review from June 1, 2026" [9]. That regime applies only to grandfathered annual subscribers [7][8].

**Per-model rates (USD per 1M tokens; divide by 0.01 for credits) — selection** [4]:

| Model | Input | Cached in | Output | Tier note |
|---|---|---|---|---|
| GPT-6 Luna | 0.10 | 0.01 | 0.50 | ≤272K; 2× above |
| GPT-5.4 nano | 0.20 | 0.02 | 1.25 | |
| MAI-Code-1.1-Flash | 0.20 | 0.02 | 1.20 | |
| GPT-5 mini | 0.25 | 0.025 | 2.00 | |
| GPT-5.4 mini | 0.75 | 0.075 | 4.50 | |
| Gemini 3.8 Flash | 0.75 | 0.075 | 3.75 | promo through 2026-12-31 |
| Kimi K2.7 Code | 0.95 | 0.19 | 4.00 | deprecated 2026-10-02 [37] |
| Claude Haiku 4.5 | 1.00 | 0.10 | 5.00 | |
| Grok 4.7 | 2.00 | 0.50 | 6.00 | ≤200K; 2× above |
| Claude Sonnet 5 | 2.00 | 0.20 | 10.00 | |
| GPT-6 Sol | 2.00 | 0.20 | 10.00 | ≤272K; 2× above |
| GPT-5.4 | 2.50 | 0.25 | 15.00 | ≤272K; 2× above |
| Claude Sonnet 4.6 | 3.00 | 0.30 | 15.00 | |
| Kimi K3 | 3.00 | 0.30 | 15.00 | |
| Claude Opus 5.5 | 4.00 | 0.20 | 20.00 | |
| Claude Opus 5 / 4.8 / 4.7 | 5.00 | 0.50 | 25.00 | |
| GPT-5.5 | 5.00 | 0.50 | 30.00 | ≤272K; 2× above |
| GPT-6 Astra | 10.00 | 1.00 | 50.00 | ≤272K; 2× above |
| Claude Fable 5.1 | 10.00 | 0.25 | 50.00 | Anthropic retains data by default [5][6] |
| Claude Opus 4.8 fast (preview) | 10.00 | 1.00 | 50.00 | |

(The pricing page also lists "Claude Sonnet 4" at 3.00/15.00 although it is absent from the supported-models list — stale row [4][5].)

**Batch API price: none exists.**

**Monthly cost estimate for the assistant server.** Assumptions: 150k input + 15k output tokens per job; **no cache hits** (worst case; a stable system prompt + repo context typically caches 40–70% of input and would cut the input line to ~10% for those tokens on *hits* — but on Anthropic and GPT-5.6/GPT-6 models the first turn that *writes* the cache is billed at 1.25× input, so a one-shot job that never re-reads its context pays ~25% more for the cached span than plain uncached input; caching only nets out positive from the second read onward); default context tier; no auto discount; 1 credit = $0.01 [3][4].

Per-job cost: GPT-6 Luna $0.02 (2 cr) · Kimi K2.7 Code $0.20 (20 cr) · Gemini 3.8 Flash $0.17 (17 cr) · Grok 4.7 $0.39 (39 cr) · Claude Sonnet 5 / GPT-6 Sol $0.45 (45 cr) · Kimi K3 $0.68 (68 cr) · Claude Opus 5.5 $0.90 (90 cr) · Claude Fable 5.1 / GPT-6 Astra $2.25 (225 cr).

| Jobs/mo | Model | Credits needed | (a) Cheapest subscription path | (b) "API" path = Copilot pay-as-you-go at list rates |
|---|---|---|---|---|
| 10 | Sonnet 5 | 450 | Pro $10 (1,500 incl.) | $4.50 |
| 10 | Opus 5.5 | 900 | Pro+ $39 (Opus models are "Not included" on Pro; Opus 5.5 is Pro+/Max/Business/Enterprise only) | $9.00 |
| 100 | GPT-6 Luna | 225 | Pro $10 | $2.25 |
| 100 | Kimi K2.7 Code | 2,025 | Pro+ $39 (7,000 incl.) — Pro would need $5.25 overage ($15.25) | $20.25 |
| 100 | Sonnet 5 | 4,500 | Pro+ $39 | $45.00 |
| 100 | Opus 5.5 | 9,000 | Pro+ $39 + $20 overage = $59, or Max $100 | $90.00 |
| 1,000 | GPT-6 Luna | 2,250 | Pro+ $39 | $22.50 |
| 1,000 | Kimi K2.7 Code | 20,250 | Max $100 + $2.50 = $102.50 | $202.50 |
| 1,000 | Sonnet 5 | 45,000 | Max $100 + $250 overage = $350 | $450.00 |
| 1,000 | Opus 5.5 | 90,000 | Max $100 + $700 = $800 | $900.00 |

Reading: the subscription's only pricing edge is the included multiplier (Pro 1.5×, Pro+ 1.8×, Max 2.0× of face value) [2]; beyond the allowance you pay exactly list price. There is **no** Claude-Max-style "unlimited-ish" tier. Real-world burn reports are far above these idealised numbers (see §5) because agent sessions re-read context every turn.

## 5. Strengths & weaknesses per reviews

**Benchmarks.** Copilot is a harness, so model benchmarks (LMArena, SWE-bench Verified, GPQA, HLE, Artificial Analysis) apply to the underlying models — see the per-vendor docs in this set. Harness-level numbers: **Terminal-Bench 2.0 — Not found** (leaderboard is client-rendered; fetched HTML contained no Copilot entry; searched tbench.ai/leaderboard and /terminal-bench/2.0) [62]. GitHub's own claim is a "benchmarked, production tested harness" without published scores [45]. The one rigorous external datapoint: an arXiv study of Microsoft's early-2026 internal rollout of Claude Code *and* Copilot CLI across "tens of thousands of engineers" found adopters "merged roughly 24% more pull requests" over four months, sustained, with adoption spreading through social networks; it does not separate the two tools [48]. HN's reaction was that PR count is an effort metric, citing METR's finding that developers self-rated +20% while measuring −19% [49].

**Best at (with attribution):**
- *Multi-vendor access under one login for $10–$39*: HN user aurareturn — "$10 for so much usage and access to Opus 4.6 and GPT 5.4" (April 2026, pre-credits) [50]; fabev found Copilot's tools "better optimized" than Cursor's [50].
- *GitHub-native automation*: cloud agent + Automations + Agentic Workflows are unique — scheduled, event-driven agents that open PRs with CodeQL/secret scanning on output [23][24][25][27].
- *Model breadth and speed of onboarding new models*: 32 models, new frontier releases within 24–72 h [5][43]; first open-weight model (Kimi K2.7 Code) in a mainstream picker, Azure-hosted with zero-retention [36][6].
- *Headless ergonomics*: `-p`, JSONL, PAT auth, `--max-ai-credits`, device-code login, plugins/agents usable headlessly [10][18][31].

**Weak at / controversies:**
- *Credit burn and predictability* — the dominant 2026 complaint. Community thread "GitHub Copilot AI Credits Are Unfair, Expensive…" (415 upvotes, 182 comments, closed by staff after one day with a redirect that drew 52 downvotes): "I used 100% of copilot pro+ in just 2 days of normal work" (KarimWajihKMW); other reports: 500 credits on three tasks, Pro+ at 85% "within one afternoon" (chalkplum), "2–4 prompts" costing 210.5 credits (EuSouVoce, 317 upvotes on the official FAQ) [51][52]. An enterprise writeup reports teams exhausting 1,900-credit Business allowances by mid-month [58].
- *Rate limits on paid plans* — "Copilot rate limit but i have PRO licence" (235 upvotes, 484 comments) — hourly/weekly limits with undisclosed numbers, closed unresolved [54][53].
- *Model access downgrades* — April 2026 removal of Opus from Pro and premium models from Student/Free drew 1,270 downvotes vs 12 upvotes; "This bait-and-switch is completely unacceptable" [53][55]. Recurring pattern: HN "Ask HN: Why does it look like everyone is abandoning GitHub Copilot?" cites smaller context and "inline completion tool rather than a full agent" as reasons for moving to Cursor/Codex/Claude Code [50]; re-thc notes different harnesses wrap the same model with different system prompts and tooling, so "Opus in Copilot" ≠ "Opus in Claude Code" [50].
- *Security* — the `env`-wrapper approval bypass; GitHub declined to treat it as a vulnerability [47]. Sandbox is still "experimental" on the CLI [10].
- *Reliability* — in the last 50 GitHub status incidents (2026-07-23 → 2026-09-23), **24 mention Copilot**, including two Copilot-specific *critical* ones — "Intermittent failures creating agent tasks" (08-20) and "Incident with Copilot AI Model Providers" (08-27) — plus two critical platform-wide incidents that also reference Copilot ("Incident with GitHub.com" 08-17, "Incident with Actions" 08-06), plus major degradations of Gemini 3.8 Flash (09-16), Copilot Code Review (09-04), Fable 5 upstream (08-24) and "Several GPT models degraded" (07-25) [46]. Expect roughly two Copilot-tagged incidents per week; most are single-model-provider degradations, which argues for model-fallback logic in any orchestrator.
- *Open-issue backlog*: copilot-cli 11.2k stars / 2,266 open issues; long-standing asks include a Docker image (#55), org-owned "Copilot Requests" tokens (#223), and transient-API-error retries (#2101) [59].

## 6. Finance / trading relevance

- **No finance product, no market-data connectors, no sentiment feeds** ship with Copilot (searched plans, cloud-agent, MCP docs). Real-time data arrives only through what you attach: web fetch tool, GitHub/Playwright MCP, or your own MCP servers (an Alpaca/Finnhub/Tradier MCP would work in CLI, SDK and cloud agent) [15][23].
- The underlying models with native web access elsewhere (Grok's X/live search, Gemini grounding, GPT browsing) are served **without** those vendor-side tools inside Copilot — you get the weights, not the vendor's search stack (no Copilot doc mentions provider-side search; unverified whether any is passed through).
- **Restrictions**: the Microsoft AI Code of Conduct (which Copilot's terms incorporate) forbids using the service "to make decisions or take actions without appropriate human oversight as part of an application that may have a consequential impact on any individual's … financial position", and its "Autonomous AI Systems" section requires human controls, anomaly detection and intervention for irreversible actions [34][35]. Paper trading, research and shadow ledgers are fine; an unattended live order path driven by Copilot output would sit on the wrong side of that clause.
- **Data**: GitHub ToS §J.3 grants GitHub a licence to use individual users' Inputs/Outputs to train models unless you opt out in settings [33]; the Generative AI Services Terms §3 conversely says GitHub "will not use Inputs or Outputs to train generative AI models, unless you have given us documented instructions" [34] — the two documents conflict; opt out in account settings regardless. Claude Fable 5/5.1 via Copilot are *not* zero-retention (Anthropic keeps prompts/outputs for safety monitoring; ZDR only on request through end-2026 under a time-bound exemption via "your GitHub account team" — effectively enterprise, but "enterprise-only" is unverified as of 2026-09-24 since the page does not literally say so) [5][6]; Grok, Kimi, OpenAI, Gemini paths are ZDR [6].

## 7. Integration recipe for our server

**Recommended shape**: Copilot **Pro+ ($39)** as the "cheap second lane" behind the Claude Max primary. Pro+ rather than Pro is forced by model access, not credits: Pro's picker excludes every Opus model, Fable 5/5.1, GPT-5.5, GPT-5.6 Sol, GPT-6 Sol and GPT-6 Astra [5], leaving Sonnet 5 / GPT-5.4 / GPT-6 Luna / Grok 4.7 / Kimi K3 as its frontier ceiling — fine for cheap routing, not for cross-family adversarial review against Opus-class output — used through the **Python SDK** (typed events, session resume, credit metrics) with the CLI's `-p` mode as the fallback for one-shot jobs. Auth once via device-code OAuth on the Mac Mini (no API key touches the repo, consistent with the subscription-only policy), or a fine-grained PAT with "Copilot Requests" in the job env. Do **not** route through unofficial OpenAI-compatible bridges or opencode's Copilot login for server jobs — same models, weaker ToS footing [56][64].

Setup (macOS, headless):

```bash
brew install copilot-cli            # or: npm i -g @github/copilot@1.0.88
copilot login --device-code         # one-time; stores OAuth under ~/.copilot (COPILOT_HOME to relocate per service user)
copilot --version
pip install "github-copilot-sdk==1.0.14"   # Python 3.11+; bundles/downloads the CLI runtime
```

One-shot job (CLI):

```bash
COPILOT_HOME=/srv/ai-server/volumes/copilot \
copilot -p "Review PR #123 for correctness; output findings as JSON array" \
  --model claude-sonnet-5 --effort medium --context default \
  --output-format json --silent --no-ask-user \
  --allow-tool 'shell(git)' --allow-tool 'shell(gh)' --deny-tool 'write' \
  --disable-builtin-mcps --add-dir /srv/projects/atlas \
  --max-ai-credits 120 --no-auto-update --share /tmp/copilot-$JOB_ID.md
# resume later: copilot -p "continue" --resume=$SESSION_ID
```

Embedded (Python SDK) — sketch for a runner adapter:

```python
import asyncio
from copilot import CopilotClient
from copilot.session import PermissionHandler
from copilot.session_events import AssistantMessageData, SessionIdleData

async def run_job(prompt: str, model: str = "gpt-6-sol") -> str:
    out: list[str] = []
    async with CopilotClient() as client:                       # uses stored device-code login
        async with await client.create_session(
            model=model, streaming=False,
            on_permission_request=PermissionHandler.approve_all,  # tighten: custom handler
            system_message={"content": "You are the ai-server research worker."},
        ) as s:
            done = asyncio.Event()
            def on_event(ev):
                if isinstance(ev.data, AssistantMessageData): out.append(ev.data.content)
                elif isinstance(ev.data, SessionIdleData): done.set()
            s.on(on_event)
            await s.send(prompt)
            await done.wait()
            usage = await s.rpc("session.usage.getMetrics")   # credits per model (nano-AI units) [21]
    return "\n".join(out)
```

(Model slugs, `rpc` call shape and `system_message` keys should be confirmed against the SDK 1.0.14 docs at install time — the README shows `model="gpt-5"` / `"claude-sonnet-4.5"` examples and `session.usage.getMetrics` as an RPC method, but not a full slug table [20][21].)

**Task-class fit here:**
- *Research* — good: Grok 4.7 / GPT-6 Sol / Gemini 3.8 Flash for cross-vendor second opinions at $0.17–0.45/job; no vendor search tools, so pair with our own fetch/MCP.
- *Coding & deploys* — good for project builds: `--worktree`, GitHub MCP, `/delegate` to cloud agent for PR-shaped work; cloud agent needs a GitHub-hosted repo and caps at 59 min [23].
- *Code review / adversarial review* — strong use: run the same diff through a different model family than the Claude author (the CLI's own "rubber-duck" agent does cross-family second opinions [18]); Kimi K3 or GPT-6 Sol at ~45–70 credits per review.
- *Chat (Telegram)* — workable via SDK sessions with `resume_session`; latency and rate limits make it a secondary lane, not the primary.
- *Classification / routing* — excellent value: GPT-6 Luna at ~2 credits per 165k-token job; 1,000 jobs ≈ $22 [4].
- *Trading research* — fine for paper/research loops (Atlas); keep it out of any order path (§6).

**Gotchas:**
1. Credits burn on *every* turn's re-sent context; 150k-token jobs on Opus-class models blow through Pro in ~15 jobs. Always set `--max-ai-credits` (floor 30) and prefer `--model auto` (10% off) for non-critical runs [31][39].
2. Hourly/weekly rate limits are undocumented and bite Pro hardest; design retries with backoff and a Claude-lane fallback [53][54].
3. Flex credits (500 of Pro's 1,500; 3,100 of Pro+'s 7,000) are explicitly variable month-to-month [3][52].
4. Model churn: Kimi K2.7 Code dies 2026-10-02 → Kimi K3 is ~3× the price [37][4]; pin models by slug in config and watch the deprecation changelog. The retirement table shows the tempo: Opus 4.5, Opus 4.6, Sonnet 4.5, Sonnet 4.6 (monthly plans) retired 2026-09-01, MAI-Code-1-Flash 2026-09-10, four more on 2026-10-02 — a pinned slug should be expected to die within ~3–6 months of its release [5].
5. Local sandbox blocks 127.0.0.1 (Postgres/Redis) unless "Allow local network" is set; `--sandbox` is experimental [16][18].
6. The CLI auto-updates by default — pin with `--no-auto-update` for reproducible jobs; `settings.json` `permissions.disableBypassPermissionsMode` can neuter `--yolo` if an org policy is ever applied [10][13].
7. Fable 5/5.1 through Copilot retain data at Anthropic; use our Claude Max lane for anything sensitive [5][6].
8. Opt out of training in GitHub settings (ToS §J.3) before sending Atlas data [33].
9. Cloud agent + Automations consume GitHub Actions minutes too; personal-repo runs bill the repo owner's seat [23][26].
10. Node CLI + Python SDK subprocess per job is RAM-cheap, but each session persists state under `~/.copilot/session-state/`; prune it.
11. Copilot code review's default effort switches from **Lite to Balanced on 2026-09-28** [40] — anyone triggering Copilot code review from automation (PR events, Automations) will see per-review credit burn rise unless they pin Lite explicitly before then.
12. Pro vs Pro+ is a model-access decision, not just a credit-volume one: Pro cannot select any Opus model, Fable 5/5.1, GPT-5.5, GPT-5.6 Sol, GPT-6 Sol or GPT-6 Astra [5]; every Opus/Fable/GPT-6-Sol line in §4's estimate table therefore presumes Pro+ or above.

## 8. Verdict

1. Copilot is now a usage-metered multi-vendor agent harness: $39 (Pro+; the $10 Pro tier locks out Opus, Fable, GPT-5.5 and GPT-6 Sol/Astra) buys $70 of list-price tokens across Claude/GPT/Gemini/Grok/Kimi plus a headless CLI, a real SDK and GitHub-native cloud agents — nothing else legitimate gives that breadth for the money.
2. It is *not* a flat-rate lane: included credits are ~1.5–2× face value, overage is pure list price, flex allotments can shrink, and undisclosed hourly/weekly limits hit paid users.
3. Automation friendliness is genuinely good (device-code OAuth, PAT, `-p` + JSONL, SDK events, session resume, credit caps), but reliability is mediocre (≈2 Copilot-tagged incidents/week) and the sandbox is experimental with a known approval-bypass class.
4. Versus the GLM/Kimi/MiniMax coding plans it competes with, Copilot wins on model breadth, GitHub integration and legitimacy, loses on raw tokens-per-dollar for heavy agentic loops.
5. Recommended role here: Pro+ as the cross-vendor second-opinion / cheap-routing / GitHub-automation lane behind Claude Max; never the primary reasoning lane, never in an order path.

Fit scores (1–10): **research 6 · coding/agentic 7 · cost efficiency 5 · automation friendliness 7 · trading research 4.**

## 9. Sources

All accessed 2026-09-24.

1. https://github.com/features/copilot/plans
2. https://docs.github.com/en/copilot/get-started/plans
3. https://docs.github.com/copilot/concepts/billing/usage-based-billing-for-individuals
4. https://docs.github.com/copilot/reference/copilot-billing/models-and-pricing
5. https://docs.github.com/en/copilot/reference/ai-models/supported-models
6. https://docs.github.com/en/copilot/reference/ai-models/model-hosting
7. https://github.blog/news-insights/company-news/github-copilot-is-moving-to-usage-based-billing/
8. https://docs.github.com/en/copilot/reference/copilot-billing/request-based-billing-legacy/what-changed-with-billing
9. https://docs.github.com/en/copilot/concepts/billing/copilot-requests
10. https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference
11. https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-programmatic-reference
12. https://docs.github.com/en/copilot/how-tos/copilot-cli/automate-copilot-cli/run-cli-programmatically
13. https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-config-dir-reference
14. https://docs.github.com/en/copilot/reference/copilot-cli-reference/acp-server
15. https://docs.github.com/en/copilot/concepts/agents/about-copilot-cli
16. https://docs.github.com/en/copilot/how-tos/use-copilot-agents/use-copilot-cli
17. https://github.com/github/copilot-cli
18. https://raw.githubusercontent.com/github/copilot-cli/main/changelog.md
19. https://github.com/github/copilot-sdk
20. https://github.com/github/copilot-sdk/blob/main/python/README.md
21. https://docs.github.com/en/copilot/how-tos/copilot-sdk/features/usage-and-billing
22. https://github.blog/changelog/2026-06-02-copilot-sdk-is-now-generally-available/
23. https://docs.github.com/en/copilot/concepts/agents/cloud-agent/about-cloud-agent
24. https://docs.github.com/en/copilot/concepts/agents/cloud-agent/about-automations
25. https://docs.github.com/en/copilot/concepts/agents/about-github-agentic-workflows
26. https://docs.github.com/en/copilot/concepts/agents/copilot-cli/copilot-cli-in-github-actions
27. https://docs.github.com/en/copilot/concepts/agents/about-third-party-coding-agents
28. https://docs.github.com/en/copilot/concepts/agents/anthropic-claude
29. https://docs.github.com/en/copilot/concepts/agents/copilot-cli/fleet
30. https://docs.github.com/en/copilot/concepts/agents/copilot-cli/about-remote-control
31. https://docs.github.com/en/copilot/how-tos/copilot-cli/use-copilot-cli/set-session-limit
32. https://docs.github.com/en/copilot/concepts/rate-limits
33. https://docs.github.com/en/site-policy/github-terms/github-terms-of-service
34. https://github.com/customer-terms/github-generative-ai-services-terms
35. https://learn.microsoft.com/en-us/legal/ai-code-of-conduct
36. https://github.blog/changelog/2026-07-01-kimi-k2-7-is-now-available-in-github-copilot
37. https://github.blog/changelog/2026-09-18-upcoming-deprecation-of-selected-github-copilot-models/
38. https://github.blog/changelog/2026-09-21-grok-4-7-is-now-available-in-github-copilot
39. https://github.blog/changelog/2026-09-14-configure-cost-and-quality-in-copilot-auto-model-selection
40. https://github.blog/changelog/2026-08-28-upcoming-changes-to-github-copilot-policies-and-billing
41. https://github.blog/changelog/2026-04-07-copilot-cli-now-supports-byok-and-local-models/
42. https://github.blog/changelog/2026-02-25-github-copilot-cli-is-now-generally-available/
43. https://github.blog/changelog/label/copilot/
44. https://github.blog/?s=%22Copilot+app%22 (GA entry 2026-07-07)
45. https://github.blog/ai-and-ml/github-copilot/copilot-vs-raw-api-access-what-are-you-actually-paying-for/
46. https://www.githubstatus.com/api/v2/incidents.json
47. https://www.promptarmor.com/resources/github-copilot-cli-downloads-and-executes-malware
48. https://arxiv.org/abs/2607.01418
49. https://news.ycombinator.com/item?id=48899321
50. https://news.ycombinator.com/item?id=47678650
51. https://github.com/orgs/community/discussions/198015
52. https://github.com/orgs/community/discussions/197089
53. https://github.com/orgs/community/discussions/192963
54. https://github.com/orgs/community/discussions/180092
55. https://github.com/orgs/community/discussions/189268
56. https://opencode.ai/docs/providers/
57. https://docs.github.com/en/github-models/use-github-models/prototyping-with-ai-models
58. https://nstech.substack.com/p/are-your-teams-running-out-of-github
59. https://api.github.com/repos/github/copilot-cli/issues?sort=reactions (via `gh api`; issues #55, #223, #2101)
60. https://docs.github.com/en/copilot/tutorials/optimize-ai-usage
61. https://github.blog/changelog/2026-09-23-local-sandboxing-in-the-github-copilot-app/
62. https://www.tbench.ai/leaderboard/terminal-bench/2.0 (no Copilot entry retrievable)
63. npm registry `npm view @github/copilot` (1.0.88, 2026-09-22) and PyPI `pip index versions github-copilot-sdk` (1.0.14)
64. https://hn.algolia.com/api/v1/search?query=%22copilot%20sdk%22 (Show HN "OpenAI API compatible server that uses GitHub Copilot SDK", 2026-01-27)

## Verification log (2026-09-24)

**Corrections applied (10 from the fact-checker's list):** 1 critical (Opus 5.5 estimate row said Pro $10; Opus is Pro+/Max/Business/Enterprise only), 2 major (Pro-row model access; Sonnet 4.6 retired 2026-09-01 / legacy-annual-only), 7 minor (model count 31→32; long_context output multiplier 1.5× for GPT models; cache-write pricing 1.25× input; billing-regime token classes; `--max-ai-credits` is per-session not per-response; Pro+ "Access to premium models" wording; status-incident critical count split into 2 Copilot-specific + 2 platform-wide). Plus 3 follow-on consistency edits (§5 "31 models"; §7 recommended-shape rationale; §8 verdict 1).

**Claims re-verified this pass (primary sources, direct fetch / curl):**
- Per-plan "Available models" matrix, 32 rows, `aria-label="Not included"` cells parsed from the HTML — https://docs.github.com/en/copilot/reference/ai-models/supported-models
- Retirement history table (Opus 4.5/4.6, Sonnet 4.5/4.6, Gemini 3.1 Pro, Raptor mini 2026-09-01; MAI-Code-1-Flash 2026-09-10; Opus 4.7, Gemini 3.5/3.6 Flash, Kimi K2.7 Code 2026-10-02) — same page
- Sonnet 4.6 footnote ("retired on September 1, 2026, but remains available to individual Copilot subscribers on annual Copilot Pro and Copilot Pro+ plans. It is not available to subscribers on monthly plans.") — same page
- Surface gating: "The 1 million token context window is available in Visual Studio Code and Copilot CLI only. Configurable reasoning levels are available in Visual Studio Code, Copilot CLI, and Copilot cloud agent." — same page
- Fable 5/5.1 ZDR footnote wording (request via account team, through end-2026, EFS afterwards) — same page
- Cache-write pricing (Anthropic + GPT-5.6/GPT-6 only; Sonnet 5 $2.50, Opus 5.5 $5.00, Fable 5.1 $12.50, GPT-6 Sol $2.50, GPT-6 Luna $0.125) and long_context rates (GPT-5.4 5.00/0.50/22.50; GPT-6 Sol 4.00/0.40/15.00; Grok 4.7 4.00/1.00/12.00) — https://docs.github.com/copilot/reference/copilot-billing/models-and-pricing
- Opus 5.5 plan availability ("available to Copilot Pro+, Max, Business, and Enterprise users") — https://github.blog/changelog/2026-09-22-claude-opus-5-5-is-now-available-in-github-copilot
- Code review default effort Lite→Balanced on 2026-09-28; Business/Enterprise signups 09-01, upfront per-seat billing 10-01; unified chat experience ≥09-28 — https://github.blog/changelog/2026-08-28-upcoming-changes-to-github-copilot-policies-and-billing
- `--max-ai-credits` semantics (session-scoped, min 30, in-progress response completes, `/limits set`) — https://docs.github.com/en/copilot/how-tos/copilot-cli/use-copilot-cli/set-session-limit
- SDK bundling (Node/Python/.NET bundled; Go/Java/Rust need `copilot` on PATH) and billing sentence — https://github.com/github/copilot-sdk/blob/main/README.md; `github_token_provider` contract (rotating session-scoped tokens, positive `expiresIn`, ~8 h, exclusive with `github_token`) — https://github.com/github/copilot-sdk/blob/main/python/README.md
- `COPILOT_OFFLINE=true` ("prevent Copilot CLI from contacting GitHub's servers … only communicates with your configured provider") — https://github.blog/changelog/2026-04-07-copilot-cli-now-supports-byok-and-local-models/; `copilot help environment` listed as a help topic — https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference
- Kimi K2.7 Code "off by default for Copilot Business and Copilot Enterprise" — https://github.blog/changelog/2026-07-01-kimi-k2-7-is-now-available-in-github-copilot; Grok 4.7 has no such off-by-default statement (normal default enablement) — https://github.blog/changelog/2026-09-21-grok-4-7-is-now-available-in-github-copilot

**Stale / unverified flags left in place (marked "(unverified as of 2026-09-24)" inline):** PromptArmor disclosure date 02-27 (§3); "no annual option since June 2026" (§4 header); Business/Enterprise "pooled" credits (§4 table); CLI GA date 2026-02-25 (§2); Fable ZDR "enterprise-only" (§6); deprecation-changelog header/slug/title date inconsistency (§1); third-party Claude agent model list Opus 4.7/Sonnet 4.6 (§2); CLI/SDK model slugs (§1, §7); SDK billing quote citation moved from [22] to [19] (§3); newer-than-doc sweep limited to direct fetches (method note). Not found and still not found: Free-plan credit allowance, knowledge cutoffs, Terminal-Bench harness score, numeric rate limits.

**Fact-checker overall quality rating:** acceptable.
