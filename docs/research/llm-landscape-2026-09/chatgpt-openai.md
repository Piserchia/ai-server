# OpenAI ChatGPT / Codex — research (as of 2026-09-24)

Scope note: openai.com and help.openai.com return HTTP 403 to direct fetches
from this session, so OpenAI's announcement posts could not be read directly.
Primary facts below come from developers.openai.com (API docs),
learn.chatgpt.com (Codex docs), github.com/openai/codex (source and releases),
pypi.org and status.openai.com; secondary sources fill gaps and are marked as
such. Gap-fill pass (2026-09-24, second session): the Terms of Use, the
consumer Data Controls FAQ, the Privacy Policy, the Enterprise Privacy page,
the Codex-with-ChatGPT-plan help article and the tbench.ai / swebench.com
leaderboard rows were obtained through a read-only text mirror (r.jina.ai) of
the same URLs and are cited as [72]-[79]; they are primary text, fetched
indirectly. The web-search budget was exhausted in both sessions, so anything
still marked "Not found — searched: ..." was not re-searched. Anything not
directly read from a primary source is marked (unverified). Third pass
(2026-09-24, gap-fill): the web-search budget was already exhausted, so
every new fact below came from direct fetches of developers.openai.com,
learn.chatgpt.com, artificialanalysis.ai, raw.githubusercontent.com and
r.jina.ai mirrors of openai.com / help.openai.com / platform.openai.com,
cited as [91]-[107].

## 1. Snapshot

**Company.** OpenAI (OpenAI Group PBC under the OpenAI Foundation). April 2026:
$122B round at $852B post-money; filed for IPO June 2026, delayed to 2027;
ChatGPT reached ~900M weekly actives (Feb 2026); ads in the Free/Go tiers hit
$1B annualized by Aug 2026 [34][35].

**Current model lineup (API IDs, from the model cards):**

| Model ID | Context / max in / max out | Cutoff | Modalities | $/1M in / cached / out | Notes |
|---|---|---|---|---|---|
| `gpt-6-astra` | 1,050,000 / 922,000 / 128,000 | 2026-04-30 | text+image in, text out | $10 / $1 / $50 | Flagship, released 2026-09-03/04 [4][31] |
| `gpt-6-sol` | 1,050,000 / 922,000 / 128,000 | 2026-04-20 | text+image in, text out | $2 / $0.20 / $10 | Workhorse, released 2026-09-22; reasoning effort none/low/medium/high/xhigh/max [2][18] |
| `gpt-6-luna` | 1,050,000 / 922,000 / 128,000 | 2026-05-18 | text+image in, text out | $0.10 / $0.01 / $0.50 | Budget/high-volume, 2026-09-22 [3][18] |
| `gpt-5.6-sol` | 1.05M (same family) | — | text+image | $4 / $0.40 / $20 (promo through 2026-11-21) | Limited preview 2026-06-26, public release 2026-07-09 (Wikipedia's GPT-5.6 article, citing Axios and TechCrunch, both dated Jul 9 [100]; the "June 2026" in the ChatGPT article [34] is the preview, so the two dates are reconciled). The model card itself carries no release date and a single undated snapshot `gpt-5.6-sol` (card re-read: cutoff 2026-02-16, $4/$0.40/$20) [107]. TechCrunch's launch prices (Sol $5/$30, Terra $2.50/$15, Luna $1/$6) are all above today's sheet — Terra and Luna were cut too, not only Sol's promo [1][29] |
| `gpt-5.6-terra` | 1,050,000 / 922,000 / 128,000 | 2026-02-16 | text+image | $2 / $0.20 / $12 | [5] |
| `gpt-5.6-luna` | 1,050,000 / — / 128,000 | 2026-02-16 | text+image | $0.20 / $0.02 / $1.20 | [6] |
| `gpt-5.5` | — | — | — | $5 / $0.50 / $30 | Released 2026-04-23; retires from Codex 2026-10-14 [1][12][32] |
| `gpt-5.3-codex` | 400,000 / 272,000 / 128,000 | — | — | $1.75 / $0.175 / $14 | Still listed as active, "optimized for agentic coding"; `gpt-5.2-codex` also listed [7] |
| `gpt-5.4` / `-mini` / `-nano` | — | — | — | $2.50/$15; $0.75/$4.50; $0.20/$1.25 | Prior generation, still on price sheet [1] |
| `gpt-5.1`, `gpt-5-mini`, `gpt-5-nano` | — | — | — | $1.25/$10; $0.25/$2; $0.05/$0.40 | Legacy; `gpt-5-2025-08-07` family shuts down 2026-12-11 [1][9] |
| `gpt-realtime-2.1`, `-mini` | — | — | audio+text in/out | audio in $32 / text in $4 / audio out $64; mini $10/$0.60/$20 | Realtime API GA; beta removed 2026-05-12 [1][26] |
| `gpt-5.6-cyber`, `gpt-daybreak-red/blue-latest`, `gpt-rosalind-research` | — | — | — | cyber $12.50 / $1.25 / $75; rosalind $5 / $0.50 / $25 (billing starts 2026-10-05); daybreak-blue = alias of `gpt-5.6-sol`, daybreak-red = alias of `gpt-5.6-cyber` | Gated specialty models (trusted-access programs) [1][8] |
| `o3-deep-research` | 200,000 | 2024-06-01 | text | $10 / $2.50 / $40 | Still listed active, Responses API only, tools `web_search`/`code_interpreter`/`mcp`; no successor ID found [56] |
| `gpt-live-1` | — | — | full-duplex voice | $0.05/min billed per second + backend model/tool usage | GA 2026-09-10 [68] |
| `gpt-image-2.5-sunburst` / `-flare` | — | — | image | GPT Image 2 token rates; new `xhigh`/`max` quality | Released 2026-09-08 (Sunburst = editing precision, Flare = fast generation) [68] |

Long-context surcharge: requests over 272K input tokens bill 2x input / 1.5x
output on GPT-6 and GPT-5.6 tiers [2][4][5]. Cache writes cost 1.25x input; cache
reads are 10% of input [2][3]. Prompt Cache Diagnostics went GA in the
Responses API for GPT-5.6+ on 2026-09-08 — it reports cache reuse and the
reason for each miss, so the caching assumptions in Section 4 can be measured
rather than guessed [68].

**Agents API (public beta 2026-09-10).** "Build agents with a managed Codex
harness while OpenAI handles session orchestration, context compaction, and
recovery": durable sessions, tool connections, MCP servers, and either
OpenAI-hosted or customer-provided sandboxes [68]. This is the hosted
alternative to running `codex exec` ourselves — same harness, but OpenAI owns
the session state and the sandbox. It is API-billed (no plan auth), it is the
surface that had the 2026-09-14 degraded-performance incident (Section 5),
and it is beta, so this doc treats it as a Phase-2 option rather than the
integration path (Section 7). Session retention (third pass, read from the
guide pages [95][96][98]): "OpenAI maintains the session for later work";
"A session keeps an agent's configuration, conversation, and saved work over
time"; "Delete a session when your application no longer needs it. Deletion
removes the session from the API" — i.e. sessions persist **until deleted**,
and no TTL, idle timeout, sandbox lifetime or per-account session cap is
published anywhere in the guide (overview, sessions, manage, architecture,
observability). "The Agents API currently supports data residency only in
the United States and does not support Zero Data Retention (ZDR)" [95].
Billing: "Model usage is billed at the selected model's API rates ... and
OpenAI-hosted sandboxes use standard container rates"; usage on
session/turn resources is "best-effort", "can be `null` when unknown", and
"Missing usage does not mean zero usage. These counts are not a final bill"
[95][97] — so the Agents API cannot be the server's cost ledger of record.

**o-series status.** `o3`/`o3-pro` API shutdown 2026-12-11 (replacement
`gpt-5.6-sol`); `o1-2024-12-17`, `o3-mini`, `o4-mini` and GPT-3.5/GPT-4 legacy variants (incl.
`gpt-4.1-nano`; `gpt-3.5-turbo-instruct` earlier on 2026-09-28) shut down
2026-10-23; `o4-mini` was pulled from ChatGPT 2026-02-13 and `o3` from ChatGPT
2026-08-26 (unverified as of 2026-09-24 — [9] is the API deprecations page and
lists no ChatGPT-app removals; neither date could be confirmed) [9]. Platform
products are gone or going: the Assistants API shut down 2026-08-26 (announced
2025-08-26; replacement = Responses + Conversations APIs); Evals (read-only
2026-10-31), Agent Builder and reusable prompts (`v1/prompts`) were announced
deprecated 2026-06-03 and shut down 2026-11-30; Sora 2 / Videos API removed
2026-09-24 [9][35]. Further model deprecations on the same page: `gpt-5.4-cyber`
shuts down 2026-10-01 (announced 2026-09-11, replacement `gpt-5.6-cyber`);
`gpt-image-1-mini` / `gpt-image-1.5` / `chatgpt-image-latest` 2026-12-01
(→ `gpt-image-2`); legacy `gpt-realtime` / `gpt-audio` / `gpt-4o-audio|realtime`
families 2027-01-20 (→ versioned replacements); `whisper-1` and the
`gpt-4o-transcribe` family 2027-02-26 (→ `gpt-live-transcribe` /
`gpt-transcribe`); and the fine-tuning platform is being wound down — closed to
orgs without prior usage since 2026-05-07, full restrictions by 2027-01-06 [9].

**Release cadence.** Roughly one major family every 2-3 months in 2026: GPT-5.4
(Mar 5), GPT-5.5 (Apr 23), GPT-5.6 Sol/Terra/Luna (preview Jun 26, public Jul
9 [100]), GPT-6 Astra (Sep
3-4), GPT-6 Sol/Luna (Sep 22; Plus/Pro/Business/Enterprise/Edu in Codex + ChatGPT
Work, Free/Go get Luna in the desktop app only, Enterprise admins must enable)
[18][29][31][32][33]. Codex CLI ships weekly-ish
(0.156.1 on 2026-09-23; 0.158.0 alphas on 09-24) [20].

**Positioning.** OpenAI now sells three things that matter here: (a) ChatGPT
as a consumer/prosumer "superapp" (chat, Work mode for docs/sheets/decks,
scheduled tasks, connectors, apps/plugins), (b) Codex as the agentic coding
product on CLI/IDE/desktop/cloud/GitHub, billed through the same ChatGPT plan,
and (c) the API (Responses API first, Chat Completions still supported, Agents
SDK on top). GPT-6 Astra is marketed as a "generational leap" and near-AGI
[31]; GPT-6 Sol is widely read as a 50% price cut at flat capability [39]. The
flagship leads OpenAI-published agentic/cyber/math benchmarks but sits behind
Anthropic's Claude on the independent Arena text leaderboard and the
Artificial Analysis index [30][41].

## 2. Interfaces & surfaces

- **Consumer app**: web (chatgpt.com), iOS/Android, macOS and Windows desktop.
  The March 2026 "superapp" consolidated ChatGPT, Codex and (formerly) Atlas
  into one desktop app; the Codex desktop app merged into the ChatGPT desktop
  app on 2026-07-09 [36]. **ChatGPT Work** (July 2026) is an agent that produces
  presentations, spreadsheets and documents from connected apps/files [34];
  Work and Codex share one usage pool [12][40].
- **Browser / OS**: **ChatGPT Atlas** (macOS browser, Oct 2025) was
  **discontinued 2026-08-09**; OpenAI says browser-agent capabilities move into
  ChatGPT (desktop app, Chrome extension/sidebar, Work) and Codex [45]. Sources
  conflict on the standalone "ChatGPT agent": Wikipedia's Operator article
  says it "was itself removed from ChatGPT in early August 2026 without an
  advance deprecation notice" (unverified as of 2026-09-24 — Wikipedia only;
  no OpenAI source readable, help.openai.com 403) [37], while therundown.ai says agent mode now
  lives inside ChatGPT Agent/Work [45]. Treat "agent mode" as in flux.
- **Voice**: Advanced Voice in the app; Realtime API (`gpt-realtime-2.1`) and
  Agents SDK voice/realtime agents for developers; GPT-Live 1 went GA
  2026-09-10 (full-duplex voice with reasoning and tool handling, $0.05/min
  billed per second, backend model/tool usage extra) [68]; Codex CLI 0.156
  turned on voice conversations by default (F8) [18][26].
- **CLI / agentic coding**: Codex CLI (`@openai/codex`, Rust, Apache-2.0;
  npm, `brew install --cask codex`, or curl installer; macOS arm64/x86_64,
  Linux x86_64/arm64, Windows) [19]. Codex IDE extension (VS Code, JetBrains,
  Xcode), Codex cloud (chatgpt.com/codex, `codex cloud exec`, `@codex` in
  GitHub PRs, GitLab/Linear/Slack delegation, automated PR code review) [16][36].
- **API + SDKs**: Responses API (primary), Chat Completions (still supported),
  Batch, Realtime, Images, Audio. Official SDKs: Python (`openai` 3.19.2,
  2026-09-24, Python >=3.10) [27], plus Node/TS, .NET, Java, Go (not
  re-verified this session). Agents SDK (`openai-agents`, Python; also JS):
  agents, handoffs, guardrails, sessions, tracing, MCP tool calling, sandbox
  agents, realtime/voice agents, human-in-the-loop; works with non-OpenAI
  providers via LiteLLM / Any-LLM adapters [26].
- **Codex SDKs**: `@openai/codex-sdk` (TS, Node 18+, spawns the CLI and
  exchanges JSONL) [21]; `openai-codex` (Python 0.156.1, 2026-09-23, Python
  >=3.10) with `Codex()`, `thread_start()`, `thread.run()`, streaming, and
  `login_chatgpt()` / `login_chatgpt_device_code()` / `login_api_key()` [22][23].
  Codex app-server exposes JSON-RPC (`thread/start`, `thread/resume`,
  `thread/fork`, `turn/start`, `model/list`, approvals) for embedding [24].
- **Observability (Codex CLI 0.156.0, 2026-09-22)**: `/usage` analytics
  dashboard with account summaries, plan usage history, token totals, top
  chats, and plugin/skill activity ("Record active plugin inventory in turn
  analytics"); `/daemon` manages the local background server and `--no-daemon`
  bypasses it, `/status` identifies it; an agent command center filters tasks
  by status and creates worktree sessions, with worktrees "now enabled by
  default" in the desktop app [20][69]. Relevant to the owner's "watch their
  progress" requirement: the dashboard is per-machine TUI state, so a server
  that wants the same numbers should count tokens from the `--json` stream
  (`turn.completed` carries usage) rather than scrape `/usage` — or, better, turn on the CLI's
  built-in **OpenTelemetry export**, which is a documented config surface
  [76]: `otel.exporter = none|otlp-http|otlp-grpc` (logs),
  `otel.trace_exporter = none|otlp-http|otlp-grpc`, `otel.metrics_exporter =
  none|statsig|otlp-http|otlp-grpc` (**default `statsig`, i.e. metrics go to
  OpenAI unless changed**), per-exporter `endpoint`, `headers`, `protocol =
  binary|json` and TLS keys, `otel.environment` (default `dev`),
  `otel.log_user_prompt` (opt-in; prompts are not exported by default), and a
  separate `analytics.enabled` switch for OpenAI's own product analytics.
  The metric names the crate emits include `codex.turn.token_usage`,
  `codex.turn.cost_microusd`, `codex.turn.e2e_duration_ms`,
  `codex.turn.ttft.duration_ms`, `codex.api_request` /
  `.duration_ms`, `codex.tool.call` / `.duration_ms`, and the goal counters
  `codex.goal.created|resumed|completed|budget_limited|usage_limited` [80].
  Pointing `otel.*` at the server's own collector gives per-turn tokens,
  cost, TTFT and tool calls without parsing JSONL, and setting
  `metrics_exporter = "none"` (or our collector) plus `analytics.enabled =
  false` stops the default phone-home. Comparable surfaces elsewhere in the
  set: Claude Code OTEL + `/usage` (TUI), Grok Build OTEL (double opt-in),
  MiniMax `/v1/token_plan/remains`, Kimi `/usage` — Codex is the only lane
  besides Claude Code with both an OTEL pipe *and* a programmatic
  rate-limit read (`account/rateLimits/read`, Section 3).
- **OpenAI/Anthropic-compatible endpoints**: OpenAI is the de-facto standard;
  Codex CLI can point at custom `model_provider`s (OpenAI-compatible) via
  config.toml (from prior knowledge; config doc 404'd this session —
  unverified).
- **MCP**: Codex is an MCP *client* (stdio + HTTP servers, OAuth or bearer
  auth, `codex mcp add|list|login`, `required = true` fails the run if a server
  cannot start, `enabled_tools`/`disabled_tools`, per-server approval modes)
  [15]. Approval modes: `default_tools_approval_mode = "auto" | "prompt" |
  "writes" | "approve"` per server (`auto` runs tools without prompts,
  `prompt`/`approve` require confirmation, `writes` prompts only for tools not
  marked read-only), with per-tool overrides via
  `[mcp_servers.<name>.tools.<tool>] approval_mode = ...`; first-party servers
  can use `auth = "chatgpt"` to reuse the current ChatGPT session (OAuth
  fallback) instead of a separate login [15]. For unattended runs the server
  must set `auto` or `writes` (with read-only tools annotated) — otherwise the
  run blocks on a prompt nobody answers. Responses API has a hosted MCP tool,
  and GPT-6 model cards list "MCP" and "tool search" among tools [2][3].
  ChatGPT connectors: custom MCP connectors historically needed
  Business/Enterprise ("developer mode") (unverified as of 2026-09-24 — not
  confirmed by any source read); an Aug 2026 vendor guide describes adding a
  third-party MCP server through ChatGPT connectors without stating plan
  gating [55]. Plan gating for individual Plus/Pro users: Not found —
  searched: "ChatGPT custom MCP connector Plus Pro developer mode 2026".
- **Batch API**: 50% off, separate queue limits (up to 15B queued tokens at
  Tier 5 for GPT-6 Sol) [1][2][10]. **Flex** = batch pricing on sync calls;
  **Fast mode** (renamed from Priority 2026-07-30) = 2x [1][3].
- **Structured outputs / tool use**: JSON-schema structured outputs and
  function calling on all GPT-6/5.6 models [2][3][5]. Codex: `--output-schema`.
- **Computer use / browser agent**: `computer use` tool on Responses API for
  GPT-6 models [2][3]; Astra scores 72.6% OSWorld 2.0 [30]. Consumer browser
  agent is mid-migration (see above).
- **Scheduled tasks**: ChatGPT Scheduled tasks on every plan — 3 active
  (Free/Go), 5 (Plus), 10 (Business/Edu), 15 (Pro/Enterprise); max once per
  hour on paid tiers per a secondary guide [52] — but OpenAI's own automations
  doc says schedules support minute-based intervals ("active loops"),
  daily/weekly, or custom RFC 5545 RRULEs, and states no cap on task count
  [17]; once/day flexible windows on Free; event-triggered tasks
  (Gmail/Slack/GitHub) capped at 30 runs/hour and 720/day; push/email
  notifications; Pulse was sunset 2026-06-17 in favor of scheduled briefings
  (unverified as of 2026-09-24 — only the ai-toolbox guide [52] says so;
  Wikipedia has no Pulse page and its ChatGPT article does not mention it)
  [17][51][52]. Codex also has scheduled tasks that run with your sandbox
  settings and can use skills [17].
- **Memory / projects**: memory and Projects in ChatGPT (Plus 20 files/project,
  Pro+ 40) [51]. Codex uses `AGENTS.md` hierarchy (32 KiB cap) [53].
- **Messaging**: WhatsApp integration ended 2026-01-15 (Meta banned third-party
  general assistants) [61]; Slack app + connector exist, Slack *actions*
  Enterprise/Edu only [60]; **no official Telegram bot** [59]; Discord: Not
  found — searched: "ChatGPT Discord official 2026".
- **Apps in ChatGPT / Apps SDK**: now framed as "plugins" = MCP server +
  optional UI + skills, with submission/review and a checkout API for
  monetization [28].

## 3. Headless / server automation fit

- **Non-interactive CLI**: `codex exec "<prompt>"` runs without the TUI;
  `--json` emits JSONL events (`thread.started`, `turn.started`,
  `turn.completed`, `turn.failed`, `item.started`, `item.completed`, `error`;
  item types: agent message, reasoning, command execution, file change, MCP
  tool call, web search, plan update); `--output-schema schema.json` +
  `-o/--output-last-message out.json` for structured final answers; `--sandbox
  read-only|workspace-write|danger-full-access`; `--ephemeral` (no session
  files); `--ignore-user-config`; `--skip-git-repo-check`; `codex exec resume
  --last|<SESSION_ID> "<next prompt>"`; stdin piping (`cmd | codex exec
  "..."`). `--full-auto` is a deprecated alias for `--sandbox workspace-write`
  [13].
- **Auth modes**: (1) ChatGPT sign-in via browser OAuth; (2) headless: `codex
  login --device-auth` (preferred), or copy `~/.codex/auth.json` (plaintext;
  "treat as password"), or SSH-forward localhost:1455; (3) API key via
  `CODEX_API_KEY` env (preferred over saved auth in `codex exec`) or `codex
  login --with-api-key`. Credential store configurable (`file`, `keyring`,
  `auto`, `ephemeral`); `forced_login_method = "chatgpt"|"api"` [13][14].
- **May a subscription be used programmatically? (position aligned with the
  ToS cross-cut: Gray / Yes*)** Three sources, read in this order of
  authority. (1) The **Terms of Use** (last updated 2026-01-01, read via
  mirror [72]) never mention Codex, agents or automation. They prohibit
  sharing "your account credentials or make your account available to anyone
  else", and — in "What you cannot do" — "Automatically or programmatically
  extract data or Output" and "Use Output to develop models that compete with
  OpenAI". They do not prohibit an owner running an OpenAI-supplied client
  (Codex CLI) unattended on their own account. (2) The **Codex docs** are the
  operative product guidance: "Use API key authentication for programmatic
  Codex CLI workflows, such as CI/CD jobs"; the pricing page repeats "API Key
  — Great for automation in shared environments like CI", and the same docs
  also document ("Advanced") reusing ChatGPT-managed `auth.json` in CI/CD
  [12][13][14]. The plan help article says only that "usage depends on the
  model, where the task runs, task complexity, context, reasoning, speed, and
  tools. A long-running task can use substantially more than a short request"
  and does not address automation at all [73]. (3) The **Manifest write-up**
  [50] is a practitioner reading, not an OpenAI statement: one subscription,
  one user; "no unattended production system should run on a ChatGPT
  subscription"; but "you can point an autonomous agent ... at your ChatGPT
  subscription, as long as it only talks to you. The moment that agent starts
  chatting with other people, or serving them in any way, it turns into a
  team use case, and that inference should be paid per usage."
  **Set-wide position (this doc now uses the same wording as crosscut-tos and
  the aggregators):** *Gray / Yes\** — plan-auth `codex exec` is not
  prohibited by the Terms and is documented by OpenAI itself for CI via
  `auth.json`, but OpenAI's *recommended* path for anything unattended is an
  API key, and the plan is a single-person licence. Operating rule for this
  server: (a) **owner-only, owner-triggered or owner-read output** (Telegram
  to the owner's own chat, reports only the owner reads, adversarial reviews
  of the owner's own theses) → plan auth is acceptable, with the risk
  accepted that OpenAI may throttle or ban without notice; (b) **anything
  scheduled at volume, anything unattended for hours (goal mode, below), and
  anything a second person consumes** (pickem league dashboard, shared project
  sites, anything under a project's public URL) → `CODEX_API_KEY` /
  Responses API on a dedicated project key — the "CI/CD service-account"
  pattern the aggregators recommend. This is one notch more conservative than
  the earlier draft of this doc, which read Manifest as blanket permission;
  the earlier reading is withdrawn. Note Codex cloud features and some
  OAuth-dependent plugins are unavailable with API-key auth [14].
- **Third-party-serving permission (one row of the cross-provider matrix)**:
  ChatGPT Free/Go/Plus/Pro outputs → owner only (Terms: no credential
  sharing, no programmatic extraction of Output; Manifest: serving others =
  team use case) [50][72]. ChatGPT Business/Enterprise seats → the seat
  holder only; a second human needs their own seat. The usage-based
  "Codex-only seat" that uibakery describes [48] could not be found on any
  OpenAI page (Section 4), so the sanctioned bot identity on the plan side is
  a paid Standard/Premium seat, not a metered one [102]. API key (any usage tier) → outputs may be served to anyone,
  subject to the Usage Policies, which prohibit "automation of high-stakes
  decisions in sensitive areas without human review" including finance —
  relevant to the trading lab, which already keeps a human on the order path
  [74]. Practical mapping: pickem dashboard, project sites, anything a
  league member or client reads = API key; the owner's Telegram assistant =
  plan auth tolerated.
- **Goal mode: the token-burn finding (crosscut-tos [39] reported it; this
  doc now carries the primary evidence).** Codex has a persisted-goals
  feature — `features.goals`, "Enable persisted goals and automatic
  continuation (stable; on by default)" [76] — that keeps a thread working
  after each turn ends until the objective is verified complete. The
  continuation prompt Codex injects on every automatic turn tells the model
  to keep polling: "A verified wait polls a specific process, session, job,
  or tool handle confirmed live now ... An observation timeout or transient
  polling failure is not terminal: re-poll the same handle", and to "leave
  the goal active" while a blocker persists, only reporting `blocked` once
  "the same blocking condition has repeated for at least three consecutive
  goal turns" [77]. Each such turn is a fresh model call billed against the
  5-hour/weekly allowance, so an unattended goal on a plan will run until one
  of two stops trips: the per-goal `token_budget` (status `budget_limited`)
  or the plan cap (status `usage_limited`) — both are literal states in the
  goals store (`thread_goals.status IN ('active','paused','blocked',
  'usage_limited','budget_limited','complete')`, with `token_budget`,
  `tokens_used`, `time_used_seconds` columns; observed in this machine's
  `~/.codex/goals_1.sqlite`, which the ChatGPT desktop app created) and are
  emitted as OTEL metrics `codex.goal.created|resumed|completed|
  budget_limited|usage_limited` [78][79][80]. The pricing page's "If you
  reach your usage limits during an active turn, the agent will be able to
  continue working on that turn, subject to fair use limits" [12] means a
  goal can overrun the cap by one turn. **Rule for the server**: every
  `codex exec` job sets `features.goals = false` (or a small
  `max_goal_token_budget` via the goal API [80]) unless the job is
  explicitly a long-running goal, and the runner enforces its own wall-clock
  and token ceilings from the `--json` stream rather than trusting the
  CLI's; on the API path, `background=true` responses do not loop, so goal
  mode is a CLI/desktop concern only. A goal-mode doc page could not be
  found (learn.chatgpt.com/docs/goals and /goal-mode both 404) — the
  feature is documented only in the config reference and source [76]-[80].
- **Concurrency on plan auth (parallel headless sessions).** No OpenAI page
  states a cap on the number of simultaneous `codex exec` processes or
  cloud tasks per plan: the pricing page defines the allowance only as
  local messages per 5-hour window plus "Weekly limits may also apply", and
  "Local messages and cloud chats share your plan's usage allowance" [12];
  the plan help article says nothing about parallelism [73]. The only
  documented concurrency knobs are *inside* a session:
  `agents.max_concurrent_threads_per_session` ("Maximum number of
  spawned-agent threads that can be open concurrently, excluding the primary
  thread. When unset, Codex chooses the default"; legacy alias
  `agents.max_threads`; the subagents doc's examples set 6 or 8 and warn that
  "subagent workflows consume more tokens than comparable single-agent
  runs") [76][103], and on the Agents API a `max_concurrent_subagents: 4`
  example [95]. The rate-limit headers are per account, not per process
  [78], so N parallel `codex exec` jobs simply drain the same 5-hour/weekly
  window N times faster. Cross-lane row: **ChatGPT/Codex = no published
  process cap; budget-bound, not slot-bound** (contrast Ollama Cloud 1/3/10,
  Kimi 1-4, MiniMax "3-4 agents", Z.ai "1-2 projects"). Scheduler rule:
  fan-out is limited by `usedPercent` from `account/rateLimits/read`, not by
  a slot count; whether OpenAI applies a hidden concurrent-request limit on
  plan auth is unverified (search budget exhausted) — measure by launching
  2/4/8 `codex exec --json` jobs and watching for `429`.
- **Credential lifecycle on a headless box (OpenAI row of the cross-cut
  matrix).** Storage: `cli_auth_credentials_store = file | keyring | auto |
  ephemeral` — `file` is plaintext `auth.json` under `CODEX_HOME`
  (`~/.codex`), `keyring` is the OS credential store (macOS Keychain) and
  fails if unavailable, `auto` tries the keyring then falls back to the file,
  `ephemeral` is process-memory only; the reference does not state the
  default, and the auth doc's warning that `auth.json` "contains access
  tokens" implies `file` in practice [14][76]. Token shape: `auth.json` holds
  `id_token` (JWT), `access_token` (JWT with an `exp` claim, parsed by
  `parse_jwt_expiration`) and `refresh_token`, plus `last_refresh` [104].
  Refresh: the CLI refreshes proactively when the access token is within
  `CHATGPT_ACCESS_TOKEN_REFRESH_WINDOW_MINUTES = 5` of expiry, by a
  refresh-token grant to `https://auth.openai.com/oauth/token` (client
  `app_EMoamEEZ73f0CkXaXp7hrann`), then rewrites the stored tokens and sets
  `last_refresh` [104]; the auth doc adds "Codex refreshes tokens
  automatically during use before they expire" [14] — *during use*, so an
  idle box does not refresh and the refresh token is the thing that ages.
  Failure ladder: permanent errors `refresh_token_expired` ("log out and
  sign in again"), `refresh_token_reused`, `refresh_token_invalidated` →
  re-login required and the failure is recorded so the CLI stops retrying
  that credential snapshot; transient errors → retry; policy denials → cache
  the current auth [104]. Refresh-token and access-token lifetimes are not
  published (unverified). What fails first on renewal: the next `codex exec`
  after refresh-token expiry fails at auth before any model call (and
  `account/rateLimits/read` fails the same way), so the expiry alarm is
  simply "auth error on first turn" plus a daily `codex login status` probe;
  recovery is `codex login --device-auth` from any shell — no browser on the
  box [14]. API-key lane: `CODEX_API_KEY` has no refresh but can now be
  forced to expire by org policy [68], so it needs a rotation job. Caveat
  for `keyring` on macOS: a launchd session may not have the login keychain
  unlocked, which would make `auto` silently fall back to the plaintext
  file (unverified; test on the Mac Mini before choosing `keyring`).
- **Data handling by auth mode**: the auth doc says ChatGPT sign-in makes Codex
  usage follow "your ChatGPT workspace permissions, role-based access control
  (RBAC), and ChatGPT Enterprise retention and residency settings", while with
  an API key "usage follows your API organization's retention and data-sharing
  settings instead" [14]. API-side defaults: "data sent to the OpenAI API is
  not used to train or improve OpenAI models (unless you explicitly opt in)";
  abuse-monitoring logs are kept up to 30 days; Zero Data Retention is
  available for `/v1/responses`, `/v1/chat/completions`, `/v1/embeddings`,
  audio and realtime endpoints but *not* `/v1/conversations`; on background
  responses with `store=false` "the response is deleted after the temporary
  polling period" (~10 minutes) and server-side compaction retains nothing
  [11][67]. Consumer side (Data Controls FAQ, read via mirror [75]): the opt-out is
  Settings → Data controls → "Improve the model for everyone"; "When Improve
  the model for everyone is off, your new conversations won't be used to
  train OpenAI models", and — the sentence that matters for this server —
  "If you use Codex on a personal ChatGPT plan, Improve the model for
  everyone also applies to your Codex tasks." **Default state of that
  toggle (third pass):** none of the three consumer-facing texts states it
  outright — the Data Controls FAQ [75] and the "How your data is used to
  improve model performance" article [99] describe only how to turn it *off*
  ("You can choose whether your conversations help improve our models"),
  the Privacy Policy says "we may use Content you provide us to improve our
  Services, for example to train the models that power ChatGPT" and "You can
  easily choose whether your Content can be used to improve and train our
  models" [81], and the only explicit "By default" sentence is the exclusion
  list ("By default, we don't use inputs or outputs from ChatGPT Business,
  ChatGPT Enterprise, ChatGPT Edu, or our API to improve our models" [99]).
  Reading: Free/Go/Plus/Pro are an **opt-out** regime, i.e. training use is
  effectively on until the owner turns it off — inferred from the structure
  of the texts, not a quoted sentence; the crosscut-finance "default on"
  wording is therefore the right operating assumption, and the owner should
  confirm on the account (Settings → Data controls) before any thesis
  material goes through plan-auth Codex. Temporary chats are kept up to
  30 days and not used for training; deleted content is removed "within 30
  days" unless retained for safety/legal reasons; consumer data is processed
  "in the United States, or in countries or territories where our
  affiliates ... are located" — no consumer residency choice [75][81].
  Business/Enterprise/Edu workspaces are not trained on by default and admins
  control retention [75][82]. API-side residency: US/EU endpoints
  (`us.`/`eu.api.openai.com`) with storage-only options in Australia, Canada,
  Japan, India, Singapore, South Korea and the UK, at a 10% price uplift for
  models released after 2026-03-05 [67].

  **Data-handling matrix per lane (OpenAI row of the cross-provider table):**

  | Lane / auth | Training use | Retention | Residency | ZDR |
  |---|---|---|---|---|
  | Codex CLI on personal Plus/Pro (plan OAuth) | Yes unless "Improve the model for everyone" is off; toggle covers Codex tasks [75] | Chats kept until deleted; deleted/temporary ≤30 d [75][81] | US / "various jurisdictions", no choice [81] | No |
  | Codex CLI on Business/Enterprise seat | No by default [75][82] | Admin-controlled; deletions ≤30 d [82] | Enterprise residency settings apply to Codex [14] | No (ZDR is API-only) |
  | API key, default (`store` default) | No unless opted in [67] | Abuse-monitoring logs ≤30 d; stored responses until deleted [67] | US/EU processing; storage-only regions +10% [67] | Eligible on `/v1/responses`, chat, embeddings, images, audio, realtime, moderations — not `/v1/conversations` [67] |
  | API key, `background=true` + `store=false` | No [67] | Response deleted after the ~10-min polling window [11] | as above | as above |
  | Agents API beta (hosted Codex harness) | Follows API org settings [68] | Sessions persist until the app deletes them ("Deletion removes the session from the API"); no TTL/idle timeout published [96][98] | US only [95] | No — "does not support Zero Data Retention" [95] |

  Net for the paper-trading lab: proprietary theses can go through plan-auth
  Codex *only after* the owner has turned "Improve the model for everyone"
  off and accepts 30-day safety retention without residency choice; the
  provable no-training, bounded-retention route remains the API key with
  `store=false` (ZDR needs an approved use case).
- **API key operations (Sep 2026)**: org/project admins can enforce maximum
  API-key lifetimes (new keys must expire within the configured limit, 09-10)
  and restrict key creation to service-account keys only, user-owned project
  keys only, or none (09-15; org restrictions override project settings,
  existing keys unaffected) [68]. For `CODEX_API_KEY` that means a rotation
  job and an expiry alarm, not a set-and-forget secret. mTLS and X.509
  workload-identity federation went GA 2026-08-29 (configured in the Platform
  console, role-gated) — an option for keyless server auth later [68].
- **Error codes for retry design**: since 2026-09-02, "traffic that increases
  too quickly can return a `429` error with the `slow_down` code" and
  "temporary model overload returns a `503` error with the
  `server_is_overloaded` code" — back off on `slow_down`, fail over to another
  model/provider on `server_is_overloaded` [68].
- **Rate limits / caps (plan auth)**: local messages per rolling 5-hour window
  with "weekly limits may also apply"; Plus: GPT-6 Astra 5-45, GPT-6 Sol
  15-150, GPT-6 Luna 350-3,000; Pro 5x: 25-225 / 70-700 / 1,750-14,000; Pro
  20x: 100-900 / 300-3,000 / 7,000-56,000; Business seats = Plus ranges [12].
  Local messages and cloud chats share the allowance; cloud chats on ChatGPT
  plans use GPT-5.6 Sol and "may consume usage faster"; image generation burns
  3-5x a typical turn [12]. When the limit is hit the CLI prompts to switch
  model (now recommends GPT-6 Luna) [20]. **Programmatic quota introspection
  exists even though `/usage` is TUI-only**: every plan-auth response carries
  a rate-limit header family that the CLI parses —
  `x-codex-primary-used-percent`, `x-codex-primary-window-minutes`,
  `x-codex-primary-reset-at`, the `-secondary-*` triplet for the weekly
  window, `x-codex-limit-name`, plus a credits snapshot (prefixes
  `x-codex-<limit_id>-*` for additional limits) [78] — and the app-server
  exposes it as `account/rateLimits/read` (request) and
  `account/rateLimits/updated` (push notification), returning
  `RateLimitSnapshot { primary, secondary: RateLimitWindow { usedPercent,
  windowDurationMins, resetsAt }, credits, planType, spendControlReached,
  rateLimitReachedType }` [79]; the Python SDK registers the same
  notification (`openai_codex/generated/notification_registry.py`). So a
  server can read "remaining 5-hour / weekly budget" as two percentages and
  two reset timestamps from a long-lived app-server session, no scraping
  needed. On the API path the equivalents are the `x-ratelimit-
  remaining-requests|tokens` / `x-ratelimit-reset-*` and project-scoped
  `x-ratelimit-*-project-tokens` response headers [10], and the org-level
  Usage/Costs endpoints (`/v1/organization/usage/completions`,
  `/v1/organization/costs`) — endpoint existence confirmed by an
  unauthenticated probe returning 401 on 2026-09-24 [83], and the details are
  now verified from OpenAI's cookbook and reference [93][94]: both require an
  **Admin API key** (`Authorization: Bearer $OPENAI_ADMIN_KEY`, created in
  org settings, distinct from project keys); `start_time` (unix seconds) is
  required; `end_time`, `bucket_width` = `1m` | `1h` | `1d` (default `1d`),
  `group_by` (array; `model`, `project_id`, `user_id`, `api_key_id`, `batch`),
  `limit` (buckets per page), `page` (cursor), and filters `project_ids`,
  `user_ids`, `api_key_ids`, `models`, `batch` are optional; each completions
  bucket returns `input_tokens`, `output_tokens`, `input_cached_tokens`,
  `input_audio_tokens`, `output_audio_tokens`, `num_model_requests` and the
  grouping keys — which "return as `null`" unless named in `group_by`; the
  costs endpoint returns `amount {value, currency}`, `line_item`,
  `project_id`, `organization_id`. Sibling endpoints exist for embeddings,
  images, moderations, audio, code-interpreter sessions, vector stores, file
  search and web search calls [94]. These cover **API-org usage only** —
  plan-auth Codex consumption never appears there; for that the only feed is
  the rate-limit RPC/headers above.
- **Rate limits (API)**: usage tiers Free/1-5; Tier 1 ($5 paid): 500 RPM /
  500K TPM on GPT-6 Sol/Luna; Tier 5 ($1,000 paid): 15,000 RPM / 40M TPM (Sol),
  30K RPM / 180M TPM (Luna) — RPM/TPM/batch figures are from the model cards
  [2][3]; the rate-limits guide [10] only defines tier qualification and the
  monthly spend caps, $100 (Free/Tier 1) up to $200,000 (Tier 5) [10].
- **Sandboxing**: Codex uses macOS Seatbelt and Linux sandboxes; modes
  `read-only` (default in exec), `workspace-write`, `danger-full-access`;
  approval policies `untrusted` / `on-request` / `never`. Seatbelt can restrict
  directory access unpredictably on some Macs (unverified as of 2026-09-24 —
  the shipyard cheat sheet [53] does not contain this caveat; treat as prior
  knowledge) [13]. Codex cloud runs in
  isolated containers with per-environment internet toggles [16].
  **Prompt-injection / untrusted-input posture (OpenAI row of the cross-cut
  ranking, from the security and sandboxing docs [105][106]):** mechanisms
  are OS-level — macOS Seatbelt via `sandbox-exec` with per-mode profiles,
  Linux `bwrap` + `seccomp` (needs unprivileged user namespaces; AppArmor
  profile on Ubuntu), Windows native sandbox or WSL2 — and "Defaults include
  no network access and write permissions limited to the active workspace";
  the sandboxed-network proxy (`features.network_proxy.domains`) is "Unset
  by default, which means no external destinations are allowed until you add
  `allow` rules" [76]. OpenAI's own warning: "Use caution when enabling
  network access or web search in Codex. Prompt injection can cause the
  agent to fetch and follow untrusted instructions"; the default cached
  web-search mode "returns pre-indexed results instead of fetching live
  pages", which is why Section 3's `web_search = "live"` recommendation
  widens the injection surface [105]. Nothing in the docs treats MCP tool
  results or piped stdin (our Telegram text) as untrusted — the model sees
  them as ordinary context. Ranking against the set: Codex sits in the top
  tier for *blast-radius containment* (OS sandbox + deny-by-default network
  + domain allowlist + per-tool MCP approval), alongside Claude Code's
  sandbox and above Grok Build (network sandbox is a no-op on macOS),
  Perplexity MCP (auto-runs with no approval) and opencode; but like every
  lane it has no *input-side* injection filter, so the server's own
  quoting/verbatim-prompt wrapper stays mandatory for Telegram text and
  fetched pages.
- **JSON / structured events**: `--json` JSONL stream; `--output-schema`;
  Python/TS SDKs expose typed events (`item.completed`, `turn.completed`) and
  `TurnResult` [13][21][22]. Responses API supports `background=true` with
  polling, resumable streaming via `sequence_number`/`starting_after`, and
  cancel [11].
- **Session resume**: `codex exec resume --last`; SDK `resumeThread(id)`
  reads `~/.codex/sessions`; app-server `thread/resume` and `thread/fork` [13][21][24].
- **Streaming**: JSONL on stdout; SDK `runStreamed()`; Responses API SSE [11][21].
- **Orchestration extras**: `codex exec-server --remote` exists per the
  non-interactive doc summary (unverified as of 2026-09-24 — page 404'd and
  the app-server README [24] does not mention it); `openai/codex-action`
  for GitHub Actions requires an API key and offers `safety-strategy`
  `drop-sudo|unprivileged-user|read-only|unsafe` [25].
- **Web search from the CLI**: config `web_search = "cached"|"live"`; default
  cached, so switch to `live` for market/news freshness [53].

## 4. Cost

**Consumer plans (2026-09):**

| Plan | Price | Includes / caps |
|---|---|---|
| Free | $0 | GPT-5.6 Luna chat "unlimited everyday" with ads (US, since Jan-Mar 2026); ~10 msgs/5h on heavier models (secondary); Deep Research 5 light/mo; 3 scheduled tasks (once/day); Codex "explore quick coding tasks" [12][34][46][52][58] |
| Go | $8/mo | Ad-supported, 98 countries since Jan 2026; ~10x Free messages; 3 scheduled tasks; Codex "lightweight tasks", no cloud task delegation [46][49][58] |
| Plus | $20/mo | GPT-6 Sol/Astra access; Codex Plus limits (above); Deep Research 25/mo (Jun-2025 figure, no longer published — Section 6); 5 scheduled tasks; agent/Work "available"; Projects 20 files; 32K standard context (secondary) [12][46][51][52] |
| Pro 5x ("Pro Codex") | $100/mo | 5x Plus Codex limits; split introduced 2026-04-09 [12][48] |
| Pro 20x ("Pro Max") | $200/mo | 20x Plus Codex limits; top Deep Research / GPT Pro quotas; 15 scheduled tasks; 128K context (secondary) [12][46][52] |
| Business | $20/user/mo annual, $25 monthly, min 2 users | Plus-level Codex per seat, pooled credits option, larger cloud VMs, admin controls, custom MCP connectors (entitlement unverified as of 2026-09-24) [12][48] |
| Business "Codex-only seat" | **not found on any OpenAI page** | uibakery's claim that "Codex-only seats provide access to Codex only and are usage-based with no fixed monthly seat price" [48] is contradicted by OpenAI's own Business pricing page (read via mirror, third pass), which lists exactly two seat types — "Standard seat $20/month" ($25 monthly) and "Premium seat $100/month" ($125 monthly), both including "All ChatGPT, ChatGPT Work, and Codex features", with "Enterprise and Business can purchase credits for more access" and token-based pricing only for Enterprise [102]; learn.chatgpt.com/docs/pricing lists only the $20/$25 seat [12] and openai.com/codex/pricing 404s. Treat the Codex-only seat as unconfirmed or retired; the plan-side path to a non-personal identity is a Standard seat + credits |
| Enterprise / Edu | quote | Credit-based flexible pricing, SCIM/EKM/audit/data residency [12] |

**Codex credits (overage on any plan)**: rate card in credits per 1M tokens —
GPT-6 Sol 50 in / 5 cached / 250 out; GPT-6 Luna 2.5 / 0.25 / 12.5; GPT-5.6
Luna 5 / 0.5 / 30 [12]; GPT-5.5 125 / 12.5 / 750; GPT-5.4 62.5 / 6.25 / 375;
GPT-5.3-Codex 43.75 / 4.375 / 350 [48]. Fast mode 2.5x on GPT-6 [12]. USD per
credit: "roughly four cents" (unverified as of 2026-09-24 — cloudzero derived
it by cross-referencing the GPT-5.3-Codex credit rate against its API price;
OpenAI publishes no USD-per-credit figure on learn.chatgpt.com/docs/pricing)
[12][49] — which would make credit prices equal to API list prices (50
credits x $0.04 = $2/M = Sol API input).

**API prices**: see Section 1 table [1]-[7]. Batch and Flex = 50%; Fast = 2x;
data-residency endpoints +10% [1]. Tools: web search $10 per 1k calls + tokens;
file search $2.50/1k calls + $0.10/GB-day (1 GB free); Code Interpreter
$0.03-$1.92 per 20-min session [1]. Realtime: see table. Free API tier: usage
tier "Free" exists for allowed geographies with a $100/mo cap and low RPM
[10]; complimentary daily tokens for data sharing: Not found — searched:
"OpenAI API free tokens per day complimentary data sharing program 2026".

**Monthly cost estimate, 10 / 100 / 1000 agent jobs.** Assumptions: 150k
input + 15k output tokens per job; no prompt caching (caching at 70% hit would
cut GPT-6 Sol to ~$0.26/job — measurable now via Prompt Cache Diagnostics on
GPT-5.6+ [68]); standard (non-batch) unless stated; 1 job ≈
8-12 Codex "local messages" (a guess — OpenAI publishes message ranges, not
token allowances, so subscription coverage is an estimate); credit = $0.04
(unverified).

| Path | Per job | 10 jobs | 100 jobs | 1,000 jobs |
|---|---|---|---|---|
| API `gpt-6-luna` | $0.0225 | $0.23 | $2.25 | $22.50 (batch $11.25) |
| API `gpt-6-sol` | $0.45 | $4.50 | $45 | $450 (batch $225) |
| API `gpt-5.6-terra` | $0.48 | $4.80 | $48 | $480 |
| API `gpt-5.3-codex` | $0.47 | $4.73 | $47 | $473 |
| API `gpt-6-astra` | $2.25 | $22.50 | $225 | $2,250 |
| Subscription: Plus $20 (Sol) | included up to cap | $20 (fits) | $20 (~3 jobs/day fits the 15-150 msgs/5h range if spread; weekly cap unknown) | $20 + overage ≈ 11.25 credits x $0.04 x ~700 jobs over cap ≈ $315 → or move to Pro |
| Subscription: Pro 5x $100 (Sol) | included | $100 | $100 | ~$100-250 (33 jobs/day likely exceeds 70-700/5h on Sol at the low end; Luna would fit) |
| Subscription: Pro 20x $200 (Sol) | included | $200 | $200 | $200 (300-3,000 Sol msgs/5h should cover ~33 jobs/day) |
| Subscription: Plus $20 (Luna) | included | $20 | $20 | $20 (350-3,000 Luna msgs/5h) |

Reading: for <100 Sol-class jobs/month the API is cheaper than any plan
(~$45) but violates the owner's subscription-over-metered preference and
needs a paid API org; Plus at $20 covers light use; at 1,000 Sol jobs/month
Pro 20x ($200) is the only plan that plausibly covers it without overage, and
it beats API list price ($450). Luna-class jobs are nearly free either way.
If goal mode is left enabled (Section 3) none of the plan rows hold: a single
unattended goal can consume the whole 5-hour window.

**Calibration against this server (cross-doc gap).** Every number above is
synthetic (150k in / 15k out, 0% cache), and the subscription-vs-metered
verdict flips on three facts this doc does not hold: real jobs/month,
tokens/job and cache-hit share from `volumes/audit_log`, and the owner's
current Max tier and existing seats (this pass was instructed not to read
repo files). The break-evens to check against those numbers: Plus $20 =
44 Sol-class API jobs/month at 0% cache (77 at a 70% hit rate, $0.26/job);
Pro 5x $100 = 222 / 385; Pro 20x $200 = 444 / 770; Luna-class jobs never
justify a plan on cost alone ($0.0225/job → 889 jobs per $20). Recipe: sum
`usage.input_tokens`, `usage.cached_input_tokens`, `usage.output_tokens`
from each job's `turn.completed` event (or the OTEL `codex.turn.token_usage`
series) over the last 30 days, compute cache share = cached / input, and
read the plan-side headroom as `usedPercent` from `account/rateLimits/read`
at the end of each 5-hour window; if median monthly Sol-class volume is
below the Plus break-even, the API key is cheaper *and* cleaner (no
Gray/Yes* exposure) — which is the crosscut-finance verdict this row should
feed, not the reverse.

**Cost of ownership from tool churn (OpenAI row of the cross-lane
comparison).** Stable Codex CLI tags between 2026-08-07 (0.147.0) and
2026-09-23 (0.156.1): 20 in 47 days, i.e. ~3 stable releases/week, with
0.158.0 alphas landing several times a day [20][84]. Breaking/behavioural
changes seen in one month: `thread/rollback` app-server API removed and the
`friendly`/`pragmatic` personalities retired in 0.156.0 (2026-09-22) [18];
`--full-auto` deprecated to an alias [13]; the rate-limit switch prompt now
retargets GPT-6 Luna [20]; the model picker gained GPT-6 Sol/Luna the same
week [18]; plus the platform-side deprecations in Section 1 (Assistants API
gone, GPT-5.5 leaving Codex 2026-10-14, o-series 2026-12-11). Operational
burden rating for the router: **high-cadence / medium-breakage** — comparable
to Claude Code (weekly, occasional default flips such as `--bare`) and below
Antigravity (10 releases in 13 days) or DeepSeek Harness ("WILL BREAK"); the
mitigation is the same as for Claude Code: pin the CLI version in the
runner's install script, pin `-m`, read the app-server protocol through the
Python SDK's generated types rather than hand-parsed JSON, and run the
adapter's smoke test on every CLI bump.

## 5. Strengths & weaknesses per reviews

**Benchmarks (OpenAI-published, GPT-6 Astra, Sep 2026)** [30]: Terminal-Bench
4.0 57.7 (Claude Fable 5.1 55.8, Opus 5 52.3, GPT-5.6 Sol 37.3); DeepSWE v1.1
74.1% (Sol 72.7%); FrontierCode 1.1 Extended 64.5% (trails Fable 5 at 64.9%);
OSWorld 2.0 72.6%; ScreenSpot-Pro 92.7%; AutomationBench 41.4% (Fable 5.1
31.4%); GPQA Diamond 96.0%; HLE with tools 57.2% (Fable 5.1 65.0%, Opus 5
63.6%); FrontierMath Tier 4 97.6% (Fable 5.1 87.8%); ARC-AGI-3 99.9%;
ExploitBench 100%; SRE-Bench 88.0%; MRCR v2 100% at 256-512K and 96.3% at
512K-1M. GPT-5.5 (Apr 2026): Terminal-Bench 2.0 82.7%, FrontierMath T1-3
51.7% [32]. GPT-5.4: OSWorld-Verified 75% [33]. **Terminal-Bench leaderboard (tbench.ai, rows obtained via text mirror
2026-09-24; runs dated late Aug-Sep 2026)** [85]:

| # | Model | Agent | Resolved | Run cost |
|---|---|---|---|---|
| 1 | GPT-6 Astra | Codex | 58.2% ± 2.8 | $3.3k |
| 2 | Claude Fable 5.1 | Claude Code | 57.9% ± 3.8 | $6.2k |
| 3 | Claude Opus 5 | Claude Code | 53.9% ± 3.2 | $6.1k |
| 4 | Claude Fable 5 | Claude Code | 44.5% ± 3.8 | $7.3k |
| 5 | GLM-5.3 | Claude Code | 41.8% ± 3.2 | $2.7k |
| 6 | Grok 4.7 | Grok Build | 37.6% ± 3.5 | $3.7k |
| 7 | GPT-5.6 Sol | Codex | 37.3% ± 3.8 | $2.5k |
| 8 | Claude Opus 4.8 | Claude Code | 23.6% ± 3.6 | $6.5k |
| 9 | GPT-5.6 Terra | Codex | 21.5% ± 3.3 | $1.7k |
| 12 | GPT-5.6 Luna | Codex | 17.3% ± 2.8 | $0.3k |

Reading: OpenAI's published 57.7 vs 55.8 is within the leaderboard's error
bars (58.2 ± 2.8 vs 57.9 ± 3.8) — a statistical tie at the top, with Astra's
run costing roughly half of Fable 5.1's. The mirror did not expose the
benchmark version label; the earlier fetch confirmed the page is
Terminal-Bench 4.0 [71]. **SWE-bench Verified (swebench.com via mirror)**:
the public table is stale — its newest entries are dated 2026-02-26 and no
GPT-6 or GPT-5.6 row exists; top rows are Claude 4.5 Opus (high) 76.8%,
Gemini 3 Flash 75.8%, MiniMax M2.5 75.8%, Claude 4.6 Opus 75.6%, with GPT-5.2
(high) and GPT-5.2-Codex at 72.8% [86]. Treat SWE-bench Verified as
saturated/abandoned for current-generation comparisons; use DeepSWE and
Terminal-Bench instead [30][85].

**Independent aggregates**: Artificial Analysis Intelligence Index v4.1.1 put
Astra at 61.2 below Claude Fable 5.1 (65.7), Opus 5 (63.1) and Fable 5 (62.1)
[30]; on the current v4.3.2 index GPT-6 Sol (max) scores 48, rank #18 of 210,
115.9 tok/s output, blended $1.54/M, and Claude Opus 5.5 took #1 on 2026-09-22
[42][43]. Arena text leaderboard (2026-09-13 snapshot): top 15 are all
Anthropic, Meta Muse Spark and Gemini; GPT-6 Astra (max) is #24 at 1480±12 and
GPT-5.6 variants sit #18-#45 [41]. GPT-5.6 Sol scored 80 on AA's Coding Agent
Index, 2.8 above Fable 5, with half the output tokens/time — an OpenAI launch
claim relayed by TechCrunch [29]. That does not reconcile with Vellum's
reading of the *current* AA Coding Agent Index, "where Fable 5 leads at 68.1
with Astra at 67.0 and Fable 5.1 at 67.2, effectively a three-way tie" [30]:
the scales differ (80 vs. 68 for the same Fable 5 baseline), which means
either the index was re-versioned between July and September or OpenAI quoted
a different sub-score. Treat the 80/2.8-point claim as unreconciled and use
Vellum's current numbers, which show no OpenAI lead on that index.

**Interactive-surface latency (Telegram round trip) — now measured.**
Artificial Analysis publishes both ends of the `reasoning_effort` ladder for
the GPT-6 family. Reasoning `max`: GPT-6 Sol (max) TTFT 165.07 s (re-read
2026-09-24; the earlier snapshot said 136.1 s), 109.6 tok/s; GPT-6 Luna
(max) TTFT 108.5 s, 141.4 tok/s, blended $0.08/M; GPT-6 Astra (max) TTFT
336.7 s, 51.3 tok/s, blended $7.70/M [42][87][88]. **Non-reasoning
(= `reasoning_effort: none`)**: GPT-6 Sol 1.00 s TTFT, 93.4 tok/s, "very
competitive compared to other non-reasoning models"; GPT-6 Luna 0.86 s
TTFT, 128.2 tok/s, against a same-price-tier median of 1.87 s / 98.5 tok/s
[91][92]. `low`/`medium` sit between the two ends and are not published;
the Codex OTEL metric `codex.turn.ttft.duration_ms` [80] measures them on
our own traffic. Chat-surface rating for the set's comparison: **Luna/Sol
at `none` = sub-2 s TTFT with streaming, the fastest measured points in the
set** (Kimi K3 3.84 s, GLM-5.3 3.4 s, Gemini 3.8 Flash 14 s; Claude Sonnet
5 / Opus 5.5 at low effort still unmeasured in the claude doc); `low` =
plausible, measure; Sol `high` and above, Astra at any effort = unsuitable
for chat, batch/report only. Note the AA figure is the Responses API; the
`codex exec` path adds process start, sandbox setup and the AGENTS.md read
before the first model call, so a Telegram lane should hit the Responses
API (or a long-lived app-server session) rather than spawn a CLI per
message.

**Best at (per sources)**: long-context recall at 1M (MRCR) [30]; agentic
computer/browser use (OSWorld, AutomationBench) [30]; cybersecurity and SRE
tasks [30][32]; math (FrontierMath, ARC-AGI-3) [30]; token efficiency in coding
("54% more token efficient", Altman via TechCrunch) [29]; price/performance —
GPT-6 Luna at $0.10/$0.50 and Sol at $2/$10 with 1M context [2][3]; the Codex
toolchain (CLI+IDE+cloud+GitHub review+SDKs) is the most complete headless
coding stack next to Claude Code [13][16][21][22].

**Weak at / criticisms**: hallucination — eesel (a vendor blog, no stated
methodology) quotes "hallucination" figures of 60% for GPT-6 Sol (down from
92% for GPT-5.6 Sol) and 77% for Luna (from 93%) [39] (unverified as of
2026-09-24: eesel dates GPT-6 Sol's release Sep 23 against the primary's Sep
22, and a 60% hallucination *rate* is implausible — these are more likely
scores on a hallucination benchmark, misread; treat as unverified secondary,
not independent testing); METR flagged GPT-5.6 Sol's reward-hacking rate as
"the highest of any public model" [40]; Astra's "recurrent depth" reasoning
hides chain-of-thought and OpenAI's own system card says it is "harder to
monitor than Sol's" [30][31]; Vellum, citing The New Stack, says "OpenAI's
chart uses a 67.4% Fable 5.1 result, which makes the lead look bigger than the
broader set of results does" on DeepSWE, and that "OpenAI removed the usual
six-hour time limit for both models" on ExploitGym (re-verified 2026-09-24
against [30]); HN's top comment on GPT-6 Sol:
"~equal performance for 0.5x the price" — a price cut, not a capability jump
[39]; r/ChatGPT and r/OpenAI complain that "the software is running ahead of
the distribution" (model sprawl across Classic/Work/Codex apps, shared usage
pools draining unexpectedly) [40]; r/claude skeptics call Sol "incremental"
[40]; a 1Password researcher said Codex-era patches were "better at exploiting
vulnerabilities than patching them" [36]; GPT-5.4 mini/nano launched at 4x the
GPT-5 mini/nano price (The Decoder) [33]; ChatGPT agent was removed in early
Aug 2026 with no deprecation notice (Wikipedia; unverified as of 2026-09-24)
[37] and Atlas was killed 10
months after launch [45] — product churn is a real integration risk.

**Reliability / outages (normalized: one source, one window).** Source:
status.openai.com/history, re-read 2026-09-24; the page is a single scroll,
not paginated, so this count supersedes the earlier "38" and "≈45" figures
[44]. Window 2026-07-01 → 2026-09-23: **33 incidents** — July 10, August 9,
September 14 (to the 23rd) — none classified major. Codex-specific: 2 (Jul 20,
Jul 24). Agents API: 2 ("Degraded Performance affecting Agents API" Sep 14;
"Overbilling for OpenAI-hosted containers in the Agent API" Sep 19 — a
billing bug on the very surface Section 1 calls the Phase-2 option). API
models: "elevated error rates across API models" Sep 17. ChatGPT/Work-mode
paid-plan errors: Sep 15, 16, 17, 22, 23 (five in nine days, including
"Elevated errors from GPT-5.6 and GPT-5.6 Instant on paid plans"). Sep 3 GPT-6
launch-day disruption is third-party reported (~4 h) and not visible under
that title on the history page [62][63]. The previously cited "Jul 18" and
"Aug 11" incident titles were not found on re-read and are withdrawn. For the
cross-vendor comparison, use the same rule for every lane: vendor status
history, Jul 1-Sep 23 2026, all severities. **Priority / SLA tiers**: Fast
mode (`service_tier: "fast"` or the legacy `"priority"`, renamed 2026-07-30)
is 2x API list and 2.5x credits, and OpenAI's pricing, latency-optimization
and Flex guides contain **no latency target, uptime number or SLA** for it
[1][12][89][90]; Flex is explicitly "slower response times and occasional
resource unavailability" with an uncharged `429 resource_unavailable` [90];
the Enterprise Privacy page carries no SLA either [82]. So OpenAI sells a
priority tier without a numeric SLA — the same situation as xAI priority and
MiniMax priority, and unlike Mistral's Priority Tier preview which states an
uptime SLA. Plan for retries and a fallback model, keyed on the new `429
slow_down` / `503 server_is_overloaded` codes (Section 3).

**Controversies (2026)**: ads in Free/Go [34]; OpenAI agents gaining
unintended internet access and hacking Hugging Face and Australia's Medicare
during testing (May-Jul 2026) [35]; Navier-Stokes proof priority dispute [35];
wrongful-death lawsuits over ChatGPT safety [35]; consent-setting data-loss
bug (Jan 2026) [34]; GPT-5.5 "goblins and gremlins" personality quirk [32].

## 6. Finance / trading relevance

- **Native market data in ChatGPT**: two 2026 vendor guides (Mar, Aug) state
  ChatGPT has no live quotes/option chains natively and relies on web search
  or connectors [54][55]. Any built-in stock widgets/charts: Not found —
  searched: "ChatGPT stock prices finance widgets finance connectors brokerage
  Plaid Robinhood 2026 OpenAI".
- **Data access paths**: (a) Responses API `web_search` tool ($10/1k calls)
  and Codex `web_search = "live"` for news/sentiment [1][53]; (b) MCP servers
  for market data — Intrinio (real-time prices, options with Greeks,
  fundamentals for 9,000+ companies), MarketXLS (1,100+ functions), Shibui
  Finance (free, ~10,000 NYSE/NASDAQ tickers, 64 years, 56 indicators) — all
  attachable to Codex via config.toml, and to ChatGPT where the plan allows
  custom connectors [15][54][55]; (c) Deep Research supports MCP connectors and
  site-scoping since Feb 2026 [38]; (d) `o3-deep-research` in the API at
  $10/$40 [56].
- **Deep Research quotas and models (reconciled, third pass)**: OpenAI no
  longer publishes per-plan numbers. The current Deep Research FAQ says only
  "Deep research usage varies by plan. Your in-product usage counter shows
  your remaining tasks. For plans with a fixed monthly allowance, it resets
  every 30 days from the date of your first use", that it "is powered by the
  latest models" with a legacy-model option, and that availability "depends
  on your plan and your country or territory" [101]; neither
  learn.chatgpt.com/docs/pricing [12] nor the free-tier limits article [58]
  carries a figure. Wikipedia's figures (dated June 2025 — Pro 250/month,
  half "lightweight"; Plus/Team/Enterprise 25/month, 15 lightweight; Free 5
  lightweight; ChatGPT-side model moved from o3 to a GPT-5.2-based model in
  Feb 2026 with o4-mini for the lightweight tier) [38] are therefore the
  last public numbers, not current ones: treat them as historic and read
  the in-product counter on the owner's account for the live allowance. In the API the only deep-research model
  is still `o3-deep-research`: 200K context, knowledge cutoff 2024-06-01,
  $10/$2.50/$40, tools `web_search` + `code_interpreter` + `mcp`, Responses
  API only [56]. For trading research that cutoff is a problem — it knows
  nothing of the 2025-26 market — so a web-search-equipped GPT-6 Sol
  ($2/$10, 1M context, cutoff 2026-04-20, `web_search` at $10/1k calls) is
  the better API research engine: 5x cheaper per token, two years fresher,
  and it can hold whole filings in context; what it lacks is the
  multi-step planning loop Deep Research runs for you, which the server can
  supply itself (or via the Agents API beta, Section 1). Plan-side Deep
  Research (25/month on Plus) is UI-only — no `codex exec` path — so it is a
  manual owner tool, not an automation surface.
- **Data handling for proprietary research**: on the API, research prompts
  are not used for training by default, ZDR is available on `/v1/responses`,
  and `store=false` bounds retention to the polling window for background
  jobs [11][67]; plan-auth Codex inherits the consumer account's data-controls
  setting, which is an opt-out regime — effectively on until switched off
  (Section 3). Feed Atlas
  theses through the API-key path if training opt-out must be provable.
- **Reviewer independence (cross-doc gap).** The "different training lineage
  → uncorrelated errors" rationale for using GPT-6 as the second opinion on
  Atlas theses is stronger for OpenAI than for the Chinese lanes: none of
  this doc's sources allege Anthropic distillation for GPT-6 (contrast the
  kimi/minimax/deepseek/qwen docs), and OpenAI's post-training is its own.
  What is *not* independent: the pre-training web corpus (both vendors saw
  the same filings, transcripts and sell-side commentary), the public
  benchmark set both tune toward, and the shared web-search index if both
  reviewers are given live search — so errors on *facts* will correlate,
  while errors of *judgment* (thesis logic, risk framing) are where the
  second opinion has value. Practical rule: give the OpenAI reviewer the
  same documents but **not** the Claude review, and score disagreement rate
  over time; if the two lanes agree >90% on rejected theses the second
  opinion is decorative. This is reasoning, not a sourced finding.
- **Sentiment sources**: Slack/Gmail/GitHub event triggers and connectors in
  ChatGPT; X/Reddit are only reachable via web search [17][60].
- **Restrictions**: consumer agent requires approval before purchases or
  permission changes, which blocks unattended overnight runs [51]; purchases
  via ChatGPT limited to Stripe/Etsy pilots [34]; no brokerage connectors
  found. There is no OpenAI order-execution path, which matches the server's
  no-live-orders policy anyway.
- **Fit**: strong for research synthesis over long filings (1M context), for
  adversarial review of Atlas theses (different training lineage from Claude),
  and for cheap classification/screening with Luna; weak as a data source.

## 7. Integration recipe for our server

**Recommended path**: Codex CLI in `exec` mode, driven from Python via
subprocess (or the `openai-codex` SDK). Auth follows the set-wide Gray/Yes*
rule (Section 3): `codex login --device-auth` on the owner's ChatGPT plan
**only** for owner-triggered, owner-read jobs (accepting the ban/throttle
risk), and `CODEX_API_KEY` on a dedicated project key — the CI/CD
service-account pattern OpenAI's own docs recommend for "programmatic Codex
CLI workflows" — for scheduled volume, multi-hour unattended runs, anything a
second person consumes, and anything that must be provably no-training
[13][14][50][72]. Every job config sets `features.goals = false` and
`otel.metrics_exporter = "none"` / `analytics.enabled = false` unless the
server's own OTLP collector is configured (Section 2, 3). Rotate that key on a schedule — org
admins can now force key expiry [68]. The Agents API beta (hosted Codex
harness, durable sessions) is the Phase-2 candidate if we want OpenAI to own
session state; not yet, it is beta and API-billed [68].
Start on Plus ($20); move to Pro 5x/20x only if the 5-hour/weekly caps bite.
Keep Claude as primary; use Codex for second-opinion review, cheap
classification (Luna), and long-context research.

```bash
# one-time, on the Mac Mini (headless-friendly)
brew install --cask codex            # or: npm i -g @openai/codex
codex login --device-auth             # ChatGPT plan sign-in without a browser on the box
# ~/.codex/config.toml
#   model = "gpt-6-sol"
#   model_reasoning_effort = "high"
#   approval_policy = "never"
#   sandbox_mode = "workspace-write"
#   web_search = "live"
#   [features]  goals = false            # no automatic continuation loop on unattended jobs (Section 3)
#   analytics.enabled = false
#   [otel]  exporter = "otlp-http"  metrics_exporter = "otlp-http"  trace_exporter = "none"
#   [otel.exporter.otlp-http]  endpoint = "http://127.0.0.1:4318"   # server's collector; tokens/cost/TTFT per turn
#   [mcp_servers.market]  command = "npx" args = ["-y","shibui-finance-mcp"]  required = true
#   default_tools_approval_mode = "writes"   # unattended: never block on a prompt; read-only tools run free
#   [mcp_servers.market.tools.place_order]  approval_mode = "prompt"   # belt-and-braces: any order tool always blocks

# a job: structured, non-interactive, resumable
codex exec --json --ephemeral --sandbox read-only -m gpt-6-luna \
  --output-schema schemas/review.json -o /tmp/out.json \
  --cd projects/atlas "Adversarially review docs/theses/latest.md; list flaws as JSON" \
  | tee volumes/audit_log/$JOB_ID.codex.jsonl
```

```python
# runner/providers/codex.py (sketch)
import json, os, subprocess
def run_codex(prompt, cwd, model="gpt-6-sol", schema=None, sandbox="read-only", api_key=None):
    cmd = ["codex", "exec", "--json", "--ephemeral", "--sandbox", sandbox, "-m", model, "--cd", cwd]
    if schema: cmd += ["--output-schema", schema, "-o", f"/tmp/{model}.out.json"]
    env = {**os.environ, **({"CODEX_API_KEY": api_key} if api_key else {})}
    p = subprocess.Popen(cmd + [prompt], stdout=subprocess.PIPE, text=True, env=env)
    for line in p.stdout:                       # JSONL: thread.started, item.*, turn.completed/failed
        ev = json.loads(line); yield ev         # turn.completed carries usage -> write to the job's audit row
        if ev["type"] in ("turn.completed", "turn.failed", "error"): break
# Retry policy for the API path: back off on 429 `slow_down`; on 503
# `server_is_overloaded` fail over to the next provider (Claude) immediately [68].
```

Alternative when a real API budget exists: `openai` Python SDK → Responses API
with `background=True` for long jobs, `store=False` (response deleted after the
~10-minute polling window; ZDR-eligible endpoint) [11][67], structured outputs,
Prompt Cache Diagnostics to verify the cache-hit assumption [68], Batch for
nightly bulk screens at 50% [1]; Agents SDK if we want handoffs + tracing, and
it can route to Claude via LiteLLM [26]; Agents API (beta) if we want hosted
durable sessions [68].

**Visibility**: per-job token counts come from the `--json` stream's
`turn.completed` event and go into the audit row; the CLI's OTEL export
(`codex.turn.token_usage`, `codex.turn.cost_microusd`,
`codex.turn.ttft.duration_ms`, `codex.goal.*`) gives the same numbers plus
latency to the server's collector [76][80]; remaining plan budget comes from
`account/rateLimits/read` / `account/rateLimits/updated` on an app-server
session (`usedPercent`, `windowDurationMins`, `resetsAt` for the 5-hour and
weekly windows, plus credits) or from the `x-codex-*-used-percent` headers
[78][79]; API-side budget comes from `x-ratelimit-remaining-*` headers and
the org Usage/Costs endpoints [10][83]. The CLI's own `/usage` dashboard
(0.156.0) is TUI-only, per machine, and useful for the owner's manual check,
not for the server [20][69]. **Collector side (cross-doc gap):** Codex
speaks OTLP over HTTP or gRPC with `protocol = binary|json` [76], so the
lightest sink on the 16 GB Mac is a single `otelcol-contrib` process with a
Prometheus exporter (no Grafana/Langfuse needed for a first cut: the
existing web dashboard can scrape the Prometheus endpoint or read the
collector's file exporter). A common cross-lane event schema that Codex
fills without adapter code: `lane=codex`, `model` (from the turn), `job_id`
(pass through `otel.environment` or a resource attribute set in
`[otel.exporter.otlp-http] headers`), `tokens_in/cached/out` from
`codex.turn.token_usage`, `cost_microusd`, `ttft_ms`, `e2e_ms`,
`tool_calls`; remaining budget is *not* an OTEL metric — it comes from
`account/rateLimits/read` and should be written into the same series by the
runner as `budget_used_pct{window=5h|weekly}` after each job. Host cost of
the collector is unmeasured here; the Codex CLI itself is a Rust binary with
remote models, and its `/daemon` background server's RSS is undocumented
(measure with `ps` before leaving it resident).

**Task-class fit here**: research (Sol; Deep Research only via UI/API model),
coding (Sol via Codex exec, workspace-write, on a worktree), code review (Luna
first pass, Sol on diff; or `@codex` on GitHub PRs with plan auth) [16],
chat via Telegram (route to Luna through our own bot — there is no official
Telegram surface) [59], classification/routing (Luna, $0.0225/job),
adversarial review (Sol/Astra as a non-Anthropic second opinion), trading
research (Sol + live web search + a market-data MCP; not a data source).

**Gotchas**: no first-party Telegram/WhatsApp; Work and Codex share one usage
pool, so UI use drains automation headroom [12]; caps are per 5h with unstated
weekly limits [12]; `auth.json` is plaintext and refresh tokens must be
re-minted if the login lapses [14]; Seatbelt sandbox quirks on macOS [53];
cloud tasks and some plugins need ChatGPT auth, not API key [14]; `--full-auto`
is deprecated [13]; web search defaults to cached [53]; MCP servers default to
prompting — set `default_tools_approval_mode` or the run hangs [15]; 16 GB RAM
is fine (CLI is a Rust binary; models are remote); model churn — pin `-m`
explicitly and watch the deprecations page (GPT-5.5 leaves Codex 2026-10-14;
`gpt-5.4-cyber` 2026-10-01; o3 API 2026-12-11; image-1 family 2026-12-01;
Assistants API already gone 2026-08-26) [9][12]; API keys can now be forced to
expire by org policy — add rotation [68]; plan-authenticated automation is
tolerated (Gray/Yes*) only while it serves the owner alone, and OpenAI's own
recommendation for programmatic use is an API key [13][50][72]; goal mode is
on by default and will re-poll until `usage_limited` — disable it per job
[76][77]; `otel.metrics_exporter` defaults to `statsig` (phones home) [76];
the Agents API had an overbilling incident on 2026-09-19 [44].

## 8. Verdict

1. OpenAI's stack is the most complete alternative to Claude Code for headless
   agentic coding: `codex exec --json`, Python/TS SDKs, device-auth, MCP client,
   cloud/GitHub review — and it runs on a $20 plan.
2. GPT-6 Sol ($2/$10, 1M context) and Luna ($0.10/$0.50) are the price
   leaders; Astra is a premium research/cyber/math model whose independent
   scores trail Claude Fable 5.1 / Opus 5.5.
3. METR's reward-hacking finding on GPT-5.6 Sol and Astra's hidden reasoning
   (the eesel hallucination figures are unverified) mean it should review, not
   decide, in the Atlas loops.
4. Product churn (Atlas killed, agent removal and Pulse sunset both reported
   but unverified, Assistants API shut down, o-series going, fine-tuning
   winding down, monthly model families) plus roughly 40-45 status incidents
   in one quarter argue for a thin adapter with model pinning and fallback
   keyed on `slow_down` / `server_is_overloaded`.
5. Subscription automation is Gray/Yes* (the set-wide position): the Terms
   do not prohibit it, OpenAI documents `auth.json` reuse in CI, but its
   recommended programmatic path is an API key and the plan is single-user.
   Owner-only jobs may use plan auth; scheduled volume, multi-hour goals,
   anything user-facing or needing provable no-training runs on
   `CODEX_API_KEY` (with expiry rotation, `store=false`). Goal mode must be
   disabled on unattended jobs.
7. Terminal-Bench 4.0 is a statistical tie at the top (Astra 58.2 ± 2.8 vs
   Fable 5.1 57.9 ± 3.8) at about half the run cost; SWE-bench Verified is
   stale (Feb 2026) and should be dropped from the comparison.
8. Visibility is better than the earlier draft said: OTEL export of tokens,
   cost, TTFT and goal counters, plus `account/rateLimits/read` for remaining
   5-hour/weekly budget, make Codex one of two lanes (with Claude Code) that
   can feed a progress dashboard without scraping.
6. For API-side trading research, GPT-6 Sol + `web_search` beats the only
   deep-research model (`o3-deep-research`, Jun-2024 cutoff) on freshness,
   context and price; plan-side Deep Research is UI-only and its per-plan
   quota is no longer published.
9. Chat lane: GPT-6 Luna/Sol at `reasoning_effort: none` are the fastest
   measured chat models in the set (0.86 s / 1.00 s TTFT); hit the Responses
   API or a resident app-server session for Telegram, not a CLI spawn per
   message. Parallel fan-out on plan auth is budget-bound (shared 5-hour /
   weekly window), not slot-bound; the credential to watch is the refresh
   token, which only refreshes during use and dies with
   `refresh_token_expired`.

Fit scores (1-10), re-anchored for the cross-provider scorecard. Anchors used
by this doc, so the synthesis can calibrate every provider to the same scale:
10 = best lane in the set on that axis for *this server's* workload; 5 = usable
with workarounds; 1 = unusable. **Research 7** (1M context + live web search
+ MCP; API deep-research model has a 2024 cutoff; plan Deep Research is
UI-only). **Coding/agentic 8** (Terminal-Bench tie for #1 at half the cost;
headless CLI + SDKs + app-server; minus one for churn and goal-mode
foot-guns). **Cost efficiency 8** (Luna $0.10/$0.50, Sol $2/$10; Plus $20
covers light use; Fast mode has no SLA to justify its 2x). **Automation
friendliness 7** (down from 8: Gray/Yes* plan-auth, goal mode on by default,
statsig metrics default, but JSONL/OTEL/rate-limit RPC are the best
visibility plumbing in the set after Claude Code). **Trading research 5**
(good second opinion and long-filing synthesis; no data source; Usage
Policies forbid unreviewed high-stakes financial automation, which the lab's
human-on-order-path design already satisfies). **Chat-surface latency 8**
(up from 4: measured 0.86-1.00 s TTFT at `none` for Luna/Sol via the
Responses API [91][92], the fastest measured points in the set; unusable at
`max`; `low`/`medium` still unmeasured).

## 9. Sources

All accessed 2026-09-24.

1. https://developers.openai.com/api/docs/pricing
2. https://developers.openai.com/api/docs/models/gpt-6-sol
3. https://developers.openai.com/api/docs/models/gpt-6-luna
4. https://developers.openai.com/api/docs/models/gpt-6-astra
5. https://developers.openai.com/api/docs/models/gpt-5.6-terra
6. https://developers.openai.com/api/docs/models/gpt-5.6-luna
7. https://developers.openai.com/api/docs/models/gpt-5.3-codex
8. https://developers.openai.com/api/docs/models
9. https://developers.openai.com/api/docs/deprecations
10. https://developers.openai.com/api/docs/guides/rate-limits
11. https://developers.openai.com/api/docs/guides/background
12. https://learn.chatgpt.com/docs/pricing
13. https://learn.chatgpt.com/docs/non-interactive-mode
14. https://learn.chatgpt.com/docs/auth
15. https://learn.chatgpt.com/docs/extend/mcp?surface=cli
16. https://learn.chatgpt.com/docs/cloud
17. https://learn.chatgpt.com/docs/automations
18. https://learn.chatgpt.com/docs/changelog
19. https://github.com/openai/codex
20. https://github.com/openai/codex/releases
21. https://github.com/openai/codex/blob/main/sdk/typescript/README.md
22. https://github.com/openai/codex/blob/main/sdk/python/README.md
23. https://pypi.org/project/openai-codex/
24. https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md
25. https://github.com/openai/codex-action
26. https://openai.github.io/openai-agents-python/
27. https://pypi.org/project/openai/
28. https://developers.openai.com/apps-sdk
29. https://techcrunch.com/2026/07/09/openai-launches-its-new-family-of-models-with-gpt-5-6/
30. https://www.vellum.ai/blog/gpt-6-astra-benchmarks-explained
31. https://en.wikipedia.org/wiki/GPT-6
32. https://en.wikipedia.org/wiki/GPT-5.5
33. https://en.wikipedia.org/wiki/GPT-5.4
34. https://en.wikipedia.org/wiki/ChatGPT
35. https://en.wikipedia.org/wiki/OpenAI
36. https://en.wikipedia.org/wiki/OpenAI_Codex_(AI_agent)
37. https://en.wikipedia.org/wiki/OpenAI_Operator
38. https://en.wikipedia.org/wiki/ChatGPT_Deep_Research
39. https://www.eesel.ai/blog/gpt-6-sol
40. https://hwbusters.com/news/gpt-5-6-is-finally-public-and-reddit-cant-decide-if-its-a-breakthrough-or-a-mess/
41. https://arena.ai/leaderboard/text
42. https://artificialanalysis.ai/models/gpt-6-sol
43. https://artificialanalysis.ai/
44. https://status.openai.com/history
45. https://www.therundown.ai/tools/atlas
46. https://www.gradually.ai/en/chatgpt-pricing/
47. https://simplemetrics.xyz/chatgpt-codex-limits-2026/
48. https://uibakery.io/blog/openai-codex-pricing
49. https://www.cloudzero.com/blog/openai-codex-pricing/
50. https://manifest.build/blog/banned-from-chatgpt-subscriptions/
51. https://www.notis.ai/blog/chatgpt-limitations-2026-workarounds/
52. https://www.ai-toolbox.co/chatgpt-management-and-productivity/how-to-use-chatgpt-tasks-schedule-2026
53. https://shipyard.build/blog/codex-cli-cheat-sheet/
54. https://marketxls.com/blog/chatgpt-stock-data-real-time-prices-financials-ai
55. https://intrinio.com/blog/how-to-connect-financial-data-to-chatgpt-for-better-stock-analysis
56. https://developers.openai.com/api/docs/models/o3-deep-research
57. https://www.morphllm.com/openai-api-pricing (search snippet only)
58. https://intuitionlabs.ai/articles/chatgpt-plans-comparison
59. https://www.chatbase.co/blog/chatgpt-on-telegram (search snippet only)
60. https://www.usecarly.com/blog/chatgpt-slack-integration/ (search snippet only)
61. https://chatarmin.com/en/blog/chatgpt-whats-app (search snippet only)
62. https://tech-insider.org/chatgpt-claude-gemini-down-outage-2026/ (search snippet only)
63. https://shattered.io/chatgpt-codex-outage-74000-reports-2026/ (search snippet only)
64. https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan (HTTP 403 this session; not read)
65. https://openai.com/policies/row-terms-of-use/ (HTTP 403 this session; not read)
66. https://help.openai.com/en/articles/20001371-evolving-atlas-into-chatgpt-for-browser-based-agentic-work (HTTP 403; summarized via [45])
67. https://developers.openai.com/api/docs/guides/your-data
68. https://developers.openai.com/api/docs/changelog
69. https://github.com/openai/codex/releases/tag/rust-v0.156.0
70. https://www.swebench.com/ (leaderboard rows did not render; navigation shell only)
71. https://www.tbench.ai/leaderboard (Terminal-Bench 4.0; rows did not render on direct fetch — see [85])
72. https://openai.com/policies/terms-of-use/ (last updated 2026-01-01; read via r.jina.ai text mirror — direct fetch 403)
73. https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan (read via r.jina.ai mirror)
74. https://openai.com/policies/usage-policies/ (changelog to 2025-10-29; read via r.jina.ai mirror)
75. https://help.openai.com/en/articles/7730893-data-controls-faq (read via r.jina.ai mirror)
76. https://learn.chatgpt.com/docs/config-file/config-reference (otel.*, analytics.enabled, features.goals, web_search, model_provider)
77. https://github.com/openai/codex/blob/main/codex-rs/ext/goal/templates/goals/continuation.md (goal-continuation prompt template)
78. https://github.com/openai/codex/blob/main/codex-rs/codex-api/src/rate_limits.rs (x-codex-*-used-percent / -window-minutes / -reset-at header parser)
79. https://github.com/openai/codex/blob/main/codex-rs/app-server-protocol/schema/typescript/v2/RateLimitSnapshot.ts and RateLimitWindow.ts; `account/rateLimits/read` and `account/rateLimits/updated` in codex-rs/app-server-protocol/src/protocol/common.rs
80. https://github.com/openai/codex/blob/main/codex-rs/otel/src/metrics/names.rs (codex.turn.*, codex.goal.* metric names); codex-rs/state/goals_migrations/0001_thread_goals.sql and codex-rs/ext/goal/src/api.rs (`max_goal_token_budget`); local evidence: `~/.codex/goals_1.sqlite` schema on the Mac Mini (created by the ChatGPT desktop app), statuses active/paused/blocked/usage_limited/budget_limited/complete
81. https://openai.com/policies/privacy-policy/ (US; previous version 2026-05-18; read via r.jina.ai mirror)
82. https://openai.com/enterprise-privacy/ (read via r.jina.ai mirror)
83. https://api.openai.com/v1/organization/usage/completions and /v1/organization/costs (unauthenticated probe 2026-09-24 → HTTP 401 "Missing bearer or basic authentication", confirming the endpoints exist; reference page 404'd)
84. https://api.github.com/repos/openai/codex/releases (stable tags 0.147.0 2026-08-07 → 0.156.1 2026-09-23, 20 stable releases)
85. https://www.tbench.ai/leaderboard (rows read via r.jina.ai text mirror, 2026-09-24)
86. https://www.swebench.com/ (rows read via r.jina.ai text mirror; newest entries 2026-02-26)
87. https://artificialanalysis.ai/models/gpt-6-luna
88. https://artificialanalysis.ai/models/gpt-6-astra
89. https://developers.openai.com/api/docs/guides/latency-optimization
90. https://developers.openai.com/api/docs/guides/flex-processing
91. https://artificialanalysis.ai/models/gpt-6-sol-non-reasoning (TTFT 1.00 s, 93.4 tok/s; read 2026-09-24 third pass)
92. https://artificialanalysis.ai/models/gpt-6-luna-non-reasoning (TTFT 0.86 s, 128.2 tok/s; tier median 1.87 s / 98.5 tok/s)
93. https://developers.openai.com/cookbook/examples/completions_usage_api (Admin API key, `bucket_width` 1m|1h|1d, `group_by`, response fields; redirected from cookbook.openai.com)
94. https://platform.openai.com/docs/api-reference/usage/completions (endpoint list incl. `/organization/costs`; read via r.jina.ai mirror)
95. https://developers.openai.com/api/docs/guides/agents-api/overview (billing at API rates + container rates; US-only residency, no ZDR; `max_concurrent_subagents: 4` example)
96. https://developers.openai.com/api/docs/guides/agents-api/sessions and /sessions/manage (sessions persist until deleted; `requires_action`; no TTL stated)
97. https://developers.openai.com/api/docs/guides/agents-api/observability (best-effort `usage`, "not a final bill")
98. https://developers.openai.com/api/docs/guides/agents-api/architecture ("OpenAI maintains the session for later work")
99. https://help.openai.com/en/articles/5722486-how-your-data-is-used-to-improve-model-performance (read via r.jina.ai mirror; "By default" exclusion list covers Business/Enterprise/Edu/API only)
100. https://en.wikipedia.org/wiki/GPT-5.6 (limited preview 2026-06-26, public release 2026-07-09; cites Axios and TechCrunch, Jul 9)
101. https://help.openai.com/en/articles/10500283-deep-research-faq (read via r.jina.ai mirror; no per-plan numbers, 30-day reset from first use)
102. https://openai.com/business/pricing/ (read via r.jina.ai mirror; Standard $20 / Premium $100 seats annual, $25 / $125 monthly; no Codex-only seat; openai.com/codex/pricing and openai.com/chatgpt/pricing carry nothing on it)
103. https://learn.chatgpt.com/docs/agent-configuration/subagents (`agents.max_concurrent_threads_per_session`, "Codex chooses the default", examples 6/8, token-cost warning)
104. https://github.com/openai/codex/blob/main/codex-rs/login/src/auth/manager.rs (`CHATGPT_ACCESS_TOKEN_REFRESH_WINDOW_MINUTES = 5`; refresh grant to auth.openai.com/oauth/token; `refresh_token_expired|reused|invalidated` permanent failures; `persist_tokens` + `last_refresh`) and codex-rs/login/src/token_data.rs (`id_token`/`access_token`/`refresh_token`, `parse_jwt_expiration`)
105. https://learn.chatgpt.com/docs/agent-approvals-security (prompt-injection warning; Seatbelt via sandbox-exec, bwrap+seccomp, Windows sandbox/WSL2; network off by default; cached web search = pre-indexed results)
106. https://learn.chatgpt.com/docs/sandboxing (per-OS mechanisms, ChatGPT Work "Allow public internet access" managed allowlist)
107. https://developers.openai.com/api/docs/models/gpt-5.6-sol (no release date on the card; single snapshot `gpt-5.6-sol`; cutoff 2026-02-16)

## Verification log (2026-09-24)

**Corrections applied: 6** — 3 major (o-series/platform deprecations
paragraph rewritten with Assistants API shutdown 2026-08-26 and Evals/Agent
Builder/prompts 2026-11-30 shutdowns; subscription-automation stance corrected
to "permitted while it serves only you", with the manifest.build wording
quoted; scheduled-task frequency corrected against OpenAI's automations doc —
minute intervals, RRULEs, no stated task cap) and 3 minor (specialty-model
pricing and aliases in the model table; o1/o3-mini/o4-mini/gpt-4.1-nano/
gpt-3.5-turbo-instruct shutdown list; GPT-6 Sol/Luna plan availability on
the Sep 22 changelog entry).

**Missing topics added (all from primary sources unless noted)**: Agents API
public beta (Section 1, 7) [68]; GPT-Live 1 GA $0.05/min, GPT Image 2.5
(Section 1, 2) [68]; Prompt Cache Diagnostics GA (Section 1, 4, 7) [68];
project API-key expiration + org key governance, mTLS/workload identity GA,
`429 slow_down` / `503 server_is_overloaded` (Section 3, 5, 7) [68]; extra
deprecations — gpt-5.4-cyber, image-1 family, legacy realtime/audio,
whisper-1/gpt-4o-transcribe, fine-tuning wind-down (Section 1) [9]; Codex CLI
0.156.0 observability — /usage, plugin/skill analytics, /daemon,
worktrees-by-default (Section 2, 7) [69]; Business Codex-only usage-based
seats (Section 4; uibakery secondary, absent from OpenAI's pricing page)
[48]; MCP approval modes and per-tool overrides, `auth = "chatgpt"` (Section
2, 7) [15]; data handling by auth mode, API no-training default, ZDR
eligibility, `store=false` on background responses (Section 3, 6, 7)
[14][67]; Deep Research quotas per plan (Wikipedia, Jun-2025 figures) and
`o3-deep-research` (200K, cutoff 2024-06-01) vs GPT-6 Sol + web_search
(Section 6) [38][56]; AA Coding Agent Index reconciliation — OpenAI's "80,
+2.8" vs Vellum's 68.1/67.2/67.0 three-way tie (Section 5) [29][30];
manifest.build clarification quoted as best available reading of the Terms
(Section 3) [50].

**Claims re-verified with sources**: API changelog entries Aug 20-Sep 22
[68]; full deprecations table [9]; MCP approval config [15]; 0.156.0 release
notes [69]; automations doc frequency wording [17]; auth-mode data handling
[14]; API data controls [67]; manifest.build wording [50]; o3-deep-research
card [56]; Deep Research quotas [38]; Vellum's DeepSWE 67.4% / ExploitGym
time-limit statements — the cherry-pick claim previously flagged is now
confirmed verbatim in [30]; Codex-only seats wording [48]; pricing page has
no USD-per-credit figure and no Codex-only seat [12].

**Stale flags left in place (marked "unverified as of 2026-09-24")**:
o4-mini pulled from ChatGPT 2026-02-13 and o3 2026-08-26; Pulse sunset
2026-06-17; "38 incidents Jul-Sep" (recount ≈ 45, page paginated); `codex
exec-server --remote`; ~$0.04 per credit; ChatGPT agent removed early Aug
2026; GPT-5.6 launch date Jul 9 vs June (and launch prices); Seatbelt
directory-access caveat; eesel hallucination figures; Plus/Pro custom MCP
connector gating and the Business connector entitlement; rate-limit citation
moved from [10] to the model cards [2][3]. Still unobtainable: SWE-bench
Verified and Terminal-Bench 4.0 leaderboard rows (JS-rendered; search budget
exhausted), the Terms of Use text (403), consumer data-controls page (403).

**Fact-checker overall quality rating: good.**

## Gap-fill log (2026-09-24, second pass)

**Position reconciled**: subscription-automation stance moved from "permitted
while serving only the owner" (Manifest reading adopted wholesale) to the
set-wide *Gray / Yes\** with API key recommended for unattended/scheduled/
multi-user work (Section 3, 7, 8), now grounded in the Terms of Use text
[72] and the Codex/pricing docs [12][13][14] rather than a practitioner blog.
**Previously unobtained, now read via text mirror**: Terms of Use [72],
consumer Data Controls FAQ [75] (opt-out explicitly covers Codex on personal
plans), Privacy Policy retention [81], Enterprise Privacy [82], Codex plan
help article [73], Usage Policies [74], Terminal-Bench rows [85], SWE-bench
rows [86] (stale). **Added**: goal-mode token-burn mechanism with primary
evidence (config reference, continuation template, goals store schema, OTEL
goal counters, local `goals_1.sqlite`) [76]-[80]; Codex OTEL export surface
and its `statsig` default [76][80]; programmatic quota introspection
(`account/rateLimits/read`, `x-codex-*` headers, API `x-ratelimit-*`,
org Usage/Costs endpoints) [10][78][79][83]; data-handling matrix per lane
(Section 3); third-party-serving row (Section 3); normalized incident count
33 for Jul 1-Sep 23 from a single unpaginated source, superseding "38"/"≈45",
plus the no-SLA finding for Fast mode [44][89][90]; AA latency for Luna/
Astra and a chat-surface rating (Section 5); CLI release-cadence/breakage
row (Section 4); re-anchored fit scores with stated anchors (Section 8).
**Withdrawn**: the "Jul 18" and "Aug 11" incident titles (not on the history
page on re-read); the claim that the status page is paginated. **Still
unverified**: TTFT at `none`/`low` reasoning effort; Usage/Costs API admin-key
and bucket details; goal-mode user documentation (no doc page found, source
only); Agents API session retention.

## Gap-fill log (2026-09-24, third pass)

Web-search budget was exhausted before this pass began; all facts came from
direct fetches and text mirrors [91]-[107]. **Resolved**: TTFT at
`reasoning_effort: none` — Sol 1.00 s, Luna 0.86 s (AA non-reasoning pages;
chat rating moved from "measure first" to measured, fit score 4 → 8);
Usage/Costs API — Admin API key, `bucket_width` 1m|1h|1d, `group_by`,
filters and response fields verified from OpenAI's cookbook; Agents API
retention — sessions persist until deleted, no TTL/idle timeout published,
US-only, no ZDR, best-effort usage; GPT-5.6 date — preview Jun 26 / public
Jul 9, both correct; Deep Research quotas — OpenAI no longer publishes
per-plan numbers, Jun-2025 figures marked historic; "Codex-only seat" —
absent from OpenAI's Business pricing page (Standard $20 / Premium $100
seats only), downgraded to unconfirmed. **Partially resolved**: consumer
data-controls default — no OpenAI text states it; opt-out structure implies
on-by-default, recorded as an inference with an owner check. **Cross-doc
rows added**: concurrency on plan auth (no published process cap;
budget-bound; `agents.max_concurrent_threads_per_session`); credential
lifecycle (storage modes, 5-minute pre-expiry refresh during use, permanent
failure codes, what fails first); prompt-injection/sandbox posture with a
ranking against the set; visibility sink (OTLP → single collector →
Prometheus, common schema, budget series from `account/rateLimits/read`);
calibration break-evens for the subscription-vs-API verdict; reviewer
independence caveat. **Still unverified**: refresh-token lifetime; hidden
concurrent-request caps on plan auth; TTFT at `low`/`medium`; Codex daemon
RSS; whether `keyring` works under launchd; the Codex-only seat's fate.