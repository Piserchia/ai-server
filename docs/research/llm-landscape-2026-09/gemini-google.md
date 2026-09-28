# Google Gemini — research (as of 2026-09-24)

Scope: Google's Gemini models, consumer plans, developer API, and agent tooling, evaluated for a single-tenant
Mac Mini assistant server (Python 3.12, Claude Agent SDK on Claude Max, Postgres/Redis, Telegram + web
dashboard, launchd; finance product with paper-trading/research loops). Owner preference: subscriptions over
metered billing, free tiers welcome, headless automation.

Reading key: `[n]` cites the numbered source in §9. "(unverified)" = only secondary sources found, or sources
conflict. Web search budget was exhausted mid-research; a few items rely on WebFetch/curl of primary pages only.

## 1. Snapshot

**Company.** Google DeepMind (models) + Google (Gemini app, Workspace, Cloud). Distribution through the
Gemini Developer API (AI Studio), Vertex AI / "Gemini Enterprise Agent Platform", the consumer Gemini app,
Antigravity (agentic IDE + CLI + SDK), Jules (async coding agent), Chrome, Android, Workspace, Home.

**Current text-model lineup (Gemini Developer API, model IDs verbatim) [1][2][4][5][6][8]:**

| Model (ID) | Status | Context (in / out) | Modalities | Knowledge cutoff | Released |
|---|---|---|---|---|---|
| `gemini-3.8-flash` | Stable (newest) | 1,048,576 / 65,536 | text, image, video, audio, PDF → text | March 2026 [8] (model card: 'The knowledge cutoff date for Gemini 3.8 Flash is March 2026') | 2026-09-02 [9] |
| `gemini-3.7-flash` | Stable | 1M / 64K (unverified; inherited from 3.8 card lineage [8]) | same | Not found | 2026-08-13 (GA per API changelog [72]) |
| `gemini-3.6-flash` | Stable | 1M / 64K (unverified) | same | Not found | 2026-07-21 [12][20] |
| `gemini-3.5-flash` | Stable | 1M / 64K (unverified) | same | Not found | 2026-05-19 [12] |
| `gemini-3.5-flash-lite` | Stable (cheapest 3.x) | 1M (unverified) | same | Not found | 2026-07-21 [12] |
| `gemini-3.1-flash-lite` | Stable | 1M (unverified) | text/image/video/audio | Not found | 2026-03-03 [12] |
| `gemini-3.1-pro-preview` | **Preview** (still no stable Pro) | 1,048,576 / 65,536 | text, image, video, audio, PDF → text | Not found — searched [5][7] | 2026-02-19 [7] |
| `gemini-3-flash-preview` | Preview (older) | 1M | same | Not found | 2025-12-17 [12] |
| Gemini 3 Deep Think | App-only (AI Ultra) [14]; 'API for select enterprises' (unverified as of 2026-09-24 — [14] only says Ultra subscribers) | n/a | text | n/a | 2025-12-03; 'major upgrade 2026-02' [12] (unverified as of 2026-09-24) |
| `gemini-3.5-pro` | **Not released** — announced I/O 2026-05-19, missed June / Jul-17 / early-Aug targets; "testing with partners"; Bloomberg: coding performance below bar [13] | — | — | — | — |

Specialised endpoints [1][2]: `gemini-3.8-live`, `gemini-3.8-live-extended-thinking`, `gemini-3.8-flash-tts`,
`gemini-3.5-transcribe`, `gemini-3.1-flash-image` ("Nano Banana 2"), `gemini-3-pro-image` ("Nano Banana Pro"),
`gemini-omni-1.1-flash` (video-out), `gemini-embedding-2-preview`, `veo-3.1-generate-preview`, `lyria-3.5`,
`gemini-2.5-computer-use-preview-10-2025` (legacy; computer use is now a tool on 3.8/3.5 Flash [41]),
managed agents `deep-research-preview-04-2026`, `deep-research-max-preview-04-2026`,
`antigravity-preview-09-2026` (released 2026-09-17; it replaces and deprecates `antigravity-preview-05-2026`, which shuts down 2026-10-05; 09-2026 switches parameter names from snake_case to PascalCase and uses line-range file edits) [1][35][36][72][73]. Gemini 2.5 models are being access-restricted to prior users [1].
A `gemini-3.1-pro-preview-customtools` variant prioritises custom tools/bash [5].
Also on the API (changelog [72]): `gemini-3.8-flash-lite-tts` (GA 2026-09-22 alongside 3.8 Flash TTS, with voice
design/replication 'persistent custom vocal personas from text prompts'), `gemini-3.8-live` models GA 2026-09-15,
`gemini-3.5-transcribe-live` (2026-08-26, bidirectional WebSocket STT), `gemini-omni-1.1-flash` GA 2026-08-27,
agentic video understanding (2026-09-01), `gemini-3.1-flash-lite-image` ('Nano Banana 2 Lite', GA 2026-06-30),
`gemini-robotics-er-2-preview` (2026-07-30), and Gemma 4 (`gemma-4-26b-a4b-it`, `gemma-4-31b-it`, free on the
API since 2026-04-02).

**Deprecation calendar to track [73]**: `antigravity-preview-05-2026` → shutdown 2026-10-05 (successor
`antigravity-preview-09-2026`); `gemini-omni-flash-preview` → 2026-09-30 (successor `gemini-omni-1.1-flash`);
`gemini-2.5-flash-image` → 2026-10-02 (successor `gemini-3.1-flash-image-preview`);
`gemini-3.1-pro-preview` and `gemini-3-flash-preview` currently 'No shutdown date announced' (3-flash successor
listed as `gemini-3.6-flash`); 2.5 models access-limited to prior users since 2026-09-18; Google notes listed
shutdown dates are 'the earliest possible dates'.

**Release cadence.** Very fast on Flash (3.5 → 3.6 → 3.7 → 3.8 in May/Jul/Aug/Sep 2026), pricing held at
introductory rates through 2026-12-31 [2][6]; the Pro line is stuck at 3.1 Preview since Feb 2026 and 3.5 Pro
has slipped three times [13]. Legacy SDK `google-generativeai` was deprecated 2025-11-30 in favour of
`google-genai` [38].

**Positioning (one paragraph).** Google is currently competing on *price-performance and speed* rather than
on the frontier: 3.8 Flash is "the cheapest model at its level of intelligence" (The Register [49]; on the current AA
Intelligence Index v4.3.2 it scores **41, #40/210, vs Claude Fable 5.1 at 53, #4** [50][91] — the Register's
launch-week "59 vs 66" pair is a pre-v4.3.2 reading, see §5), tops Terminal-Bench 2.1 (90.8%) and leads finance/legal agent benchmarks [9][11],
while its flagship Pro is a seven-month-old preview and the community consistently rates it below Claude for
agentic coding [47][48]. Its real moats are 1M-token native multimodality (video/audio/PDF), Google Search/Maps
grounding, the consumer footprint (Android, Chrome, Workspace, Home, Finance), and a generous — though shrinking
and training-data-harvesting — free API tier [2][42].

## 2. Interfaces & surfaces

- **Consumer app**: web (gemini.google.com), Android, iOS, **macOS app** (Spark agent + Fn voice dictation
  since Jun/Jul 2026) and **Windows app** (Alt+Space, since 2026-09-10) [20]. Model picker exposes 3.1 Pro
  (paid tiers), 3.6/3.8 Flash, Deep Think (Ultra) [18][20]. App context window: 32k free, 128k Plus, 1M Pro/Ultra [18].
- **Browser/OS integrations**: Gemini in Chrome with "auto browse" agentic browsing (AI Pro/Ultra, US-first,
  desktop + mobile) [55]; Gemini replaced Assistant on Android; Google Home Premium bundled with AI Pro/Ultra [15];
  Gemini in Gmail/Docs/Sheets (Workspace) from AI Plus up [15]; AI Mode in Search runs 3.8 Flash [9].
- **Gemini Spark** (macOS, AI Ultra US beta since 2026-06-30): background agent that acts on local files on a
  schedule, with Tasks/Keep/Dropbox/etc. connectors and **custom MCP servers** [20][56].
- **Voice**: Gemini Live in-app; Live API models `gemini-3.8-live` / `-extended-thinking` [1][2].
- **CLI / agentic coding**:
  - **Gemini CLI** (open source, `gemini`): headless via `-p`, `--output-format json|stream-json` [23]; `--resume latest|<n>`,
    `--include-directories` (CLI reference [75]); exit codes 0/1/42/53, MCP servers [23]. **Free Google-login tier ended 2026-06-18**;
    unpaid and Google One users are pointed to Antigravity CLI (geminicli.com footnote [21]; [22] predates this). **Resolved 2026-09-24
    (primary, [21])**: the quota page's "Personal accounts" section still lists Google-account login for **Google AI Pro (1,500
    requests/day) and Google AI Ultra (2,000/day)** and states verbatim "Tiers not listed above, including Google AI Plus, are not
    supported" — i.e. Pro/Ultra OAuth to Gemini CLI is supported, Free/Google One/AI Plus is not. CLI still works with a Gemini API key
    (free tier: 250 requests/day, Flash only [21]; or paid) / Vertex / Code Assist licence [21][22]. See the canonical reading in §3.
  - **Antigravity CLI** (`agy`, curl installer, `~/.local/bin/agy`; macOS/Linux/Windows): `-p/--print`,
    `--output-format json|stream-json`, `--input-format stream-json` (multi-turn over stdin), `--model
    gemini-3.8-flash-high`, `--effort low|medium|high`, `--continue`/`--conversation <id>`,
    `--dangerously-skip-permissions`, `--json-schema` structured output, `--print-timeout` (docs table still says default 5m [26], but release 1.2.6 (2026-09-18) 'changed the default timeout for headless (-p / --prompt) runs from 5 minutes to unlimited' [70] — always pass it explicitly in a scheduler),
    `--sandbox` [25][26]. Included at every plan tier incl. free; shares the IDE quota pool [29].
    **Release cadence**: ten releases 1.2.1→1.2.10 between 2026-09-11 and 2026-09-24, with headless-behaviour
    changes landing mid-month (1.2.6: headless timeout default → unlimited, daemon background commands kept
    alive in headless `GEMINI_API_KEY` sessions; 1.2.4: `hooks.json` silently dropped under token-budget
    truncation fixed; 1.2.9: API-key path discrepancies reduced) — pin the binary version [70]. **System
    requirements**: macOS 12 (Monterey)+ on Apple Silicon only ('X86 is not supported'), Windows 10 64-bit
    x64/ARM64, Linux glibc ≥ 2.28 [25].
  - **Antigravity IDE** (VS Code fork + "Manager" multi-agent view; 2.0 desktop app at I/O 2026 with scheduled
    tasks and subagents) and **Antigravity SDK** (programmatic agent harness) [34][65].
  - **Jules** (async cloud coding agent on GitHub repos): plan → PR; API at `https://jules.googleapis.com/v1alpha/`
    with `X-Goog-Api-Key` (max 3 keys), sessions/sources/activities, `automationMode: "AUTO_CREATE_PR"`,
    `requirePlanApproval`; scheduled tasks (pause/resume), CI-failure auto-fix, MCP (Linear, Supabase, Neon,
    Context7 …) [31][32][33].
- **API + SDKs**: `google-genai` (Python), `@google/genai` (JS/TS), `google.golang.org/genai` (Go), Java
  `com.google.genai:google-genai`, C# `Google.GenAI` — all GA [38]. REST at
  `generativelanguage.googleapis.com`. Vertex AI / Gemini Enterprise Agent Platform for Cloud accounts.
- **Interactions API (GA since June 2026)**: 'As of June 2026, it is Generally Available and recommended for all
  new projects'; `generateContent` 'is now considered legacy' but 'remains fully supported' [74]. It adds
  optional server-side conversation state (`previous_interaction_id`), observable execution steps, and
  `background=true` for long-running work; the 3.8 Flash migration notes say 'Standardize multi-turn conversations
  on server-side `previous_interaction_id`' and, 'only if using generateContent', ensure every `FunctionResponse`
  includes `call_id` and `name` [6][78]. Server-side interactions are retained **55 days on the paid tier, 1 day
  on the free tier** [74].
- **OpenAI-compatible endpoint**: `https://generativelanguage.googleapis.com/v1beta/openai/`, Bearer = Gemini
  API key; chat completions, streaming, function calling, structured outputs, embeddings, image input,
  `reasoning_effort` → thinking level, Batch; "still in beta", unknown params silently ignored; no Anthropic-
  compatible endpoint [37].
- **MCP**: built into `google-genai` Python/JS SDKs (experimental; tools only, not resources/prompts) [66];
  Gemini CLI and Antigravity CLI/IDE consume MCP servers [23][25]; Spark accepts custom MCP [56]; Gemini
  Enterprise for Financial Services ships MCP connectors to FactSet/S&P/SEC Edgar etc. [54].
- **Batch API**: 50% off, 24h target turnaround ("usually much quicker"), inline ≤20 MB or JSONL file ≤2 GB [3][39];
  '100 concurrent jobs' (unverified as of 2026-09-24 — not on the batch-api page as fetched).
- **Structured outputs / tool use**: JSON-schema structured outputs, function calling, code execution, URL
  context, Google Search grounding (5,000 free prompts/mo then $14/1,000 on 3.x), Maps grounding, file search;
  3.8 Flash uses `thinking_level` (low/medium/high; `minimal` errors) and drops temperature/top_p/top_k [2][4][6].
- **Computer use / browser agent**: tool on `gemini-3.8-flash` and `gemini-3.5-flash` (Preview; browser via
  Playwright, Android, desktop; 0–999 normalised coordinates; "may contain errors and security
  vulnerabilities") [41]. Consumer equivalents: Chrome auto browse, "Gemini Agent" (Ultra, US) [15][55].
- **Managed agents (Interactions API)**: `antigravity-preview-09-2026` (05-2026 deprecated 2026-09-17, shutdown 2026-10-05 [73]; 3.8 Flash by default, Google-hosted
  Ubuntu sandbox, Python 3.12 + Node 22, 'unrestricted egress unless allow-listed' (unverified as of 2026-09-24 — the page mentions allowlists/credentials but the fetched text did not state the default egress policy), env deleted after 7 days idle,
  up to 1,000 agents/account; sandbox compute free during preview) and Deep Research (`background=True`,
  poll `client.interactions.get`) [35][36].
- **Scheduled/automated tasks**: Gemini app **Scheduled Actions** (any personal Google Account — 'gradually making this feature available to all personal Google Accounts' — or qualifying Workspace edition; paid plans only get responses prepared 'within the hour' vs 'up to several hours in advance' on free; max 10 active; recurring
  daily/weekly/monthly; delivered as unread chat + push; responses "prepared in advance" so stock prices are
  stale; needs Keep Activity on) [19]; Antigravity 2.0 scheduled tasks [34]; Jules scheduled tasks [33];
  Spark scheduled file jobs [56]. No API-side cron.
- **Memory**: app-level "personal context"/memory and Keep Activity; Gems = custom assistants with files +
  Drive context [62]. API has no persistent memory (managed-agent environments persist 7 days [35]).
- **Projects/workspaces**: Gems; NotebookLM ("Gemini Notebook": 50 sources/notebook free, 300 Pro, 500–600
  Ultra; usage quota now 5-hourly/weekly since 2026-09-02) [63] (unverified as of 2026-09-24; secondary only).
- **Messaging**: **no official Telegram/Slack/WhatsApp/Discord Gemini bot**; all are third-party bridges or
  API bots [search results only, no primary source].
- **IDE plugins**: Antigravity (own IDE), Gemini Code Assist for VS Code/JetBrains (paid licence for
  individuals since 2026-06-18 — unverified as of 2026-09-24: the Code Assist overview now lists only Standard and
  Enterprise editions, consistent but not explicit; geminicli.com still lists AI Pro 1,500 / Ultra 2,000
  requests/day via Google account, so Pro/Ultra OAuth to Gemini CLI may still work) [21], Android Studio [9], `run-gemini-cli` GitHub Action (API key / Vertex /
  WIF only, no consumer OAuth) [58].

## 3. Headless / server automation fit

**Auth modes.**
1. *Gemini API key* (AI Studio): free or paid tier, `GEMINI_API_KEY`/`GOOGLE_API_KEY` env; works with SDK,
   OpenAI endpoint, Gemini CLI, GitHub Action [23][37][58]. Paid data is not used for training; free-tier
   prompts/outputs may be human-reviewed and used to improve products; do not send confidential data [42].
2. *Vertex AI* (service account / `GOOGLE_GENAI_USE_VERTEXAI=1`): Cloud billing, DSQ or provisioned
   throughput [21][23].
3. *Google account OAuth (consumer subscription)*: Gemini CLI login for free/Google One users **stopped
   2026-06-18**; geminicli.com's quota page lists "Google AI Pro: 1,500 requests/day, Ultra: 2,000/day" under
   "Personal accounts" and its footnote says the CLI "was replaced by Antigravity CLI on June 18th, 2026" for the
   unpaid tier and Google One users; the same page adds "Tiers not listed above, including Google AI Plus, are not
   supported" [21]. **Canonical reading (resolves the three cross-doc readings):** (a) Pro/Ultra-via-Gemini-CLI is
   **supported, not conflicting** — the footnote scopes the replacement to unpaid/Google One accounts; (b) there is
   **no $0 Google-login lane** into Gemini CLI any more — a "$0 reviewer lane" on Gemini can only be the **API-key
   free tier (250 RPD, Flash only, prompts are training data + human-reviewed [21][42])** or Antigravity CLI's free
   weekly quota (unpublished size, subscription ToS) — crosscut-finance/crosscut-benchmarks must not book Gemini CLI
   Google-login as $0; (c) **Google AI Plus ($4.99) unlocks neither Gemini CLI nor Antigravity's 5-hour refill** —
   the cheapest subscription that reaches Gemini CLI is AI Pro $19.99. Antigravity CLI: "Headless mode uses your
   cached credentials. Authenticate once with an interactive `agy` session first"; a Gemini API-key mode IS documented: set `"modelProvider": "gemini"` in `~/.gemini/antigravity-cli/settings.json` and export `GEMINI_API_KEY` (the env var alone has no effect; optional `GOOGLE_GEMINI_BASE_URL`); it bills the Gemini API (paid/free tier) instead of subscription quota and needs no keyring/OAuth session, so it works in CI/Docker [67] — caveat: workspace hooks are reported to load but never execute under API-key auth (issue #893, open since 2026-08-28) [69] and 1.2.9 notes 'behavior discrepancies with the non-API-key sign-in path' [70];
   in CI without cached auth it exits with an auth error rather than hanging [26].
   **Owner probe that settles the runtimes-aggregators dispute (Pro/Ultra OAuth to Gemini CLI: supported per [21] vs
   "replaced by Antigravity CLI" per the same page's footnote):** on the Mac Mini, with the AI Pro Google account
   already logged in once interactively, run `gemini -p "reply with the single word pong" --output-format json` and
   then, in a TUI session, `/stats model`. Outcomes: (i) JSON `response` = "pong" and `/stats model` shows a Pro quota
   line (1,500 req/day) → the [21] reading stands and the subscription lane is real; (ii) an auth/licence error or a
   redirect message naming Antigravity CLI → the footnote reading wins and geminicli.com's "Personal accounts" table is
   stale; (iii) success but `/stats model` reports Code-Assist-individual quota → the login fell through to the free
   Code Assist licence and no Pro quota is being consumed. Ten minutes, zero cost, and it fixes the number every
   cross-cut table has been guessing at. Until it runs, this doc's canonical reading remains (a) above.

**Terms on programmatic use of consumer subscriptions.** Driving the *official* CLI non-interactively under
your own subscription is the sanctioned pattern (Google ships `-p`/JSON modes) [23][26][44]. Prohibited:
"Directly accessing the services powering Gemini CLI … using third-party software (for example, using OpenClaw
with Gemini CLI OAuth)" [24]; the March 2026 service update (discussion [22], dated 2026-03-18, covering the 2026-03-25 routing change,
Pro-paid-only, and OAuth-with-third-party-software detection — it does **not** describe the June 18 free-tier
shutdown) routes traffic by licence type; the enforcement ladder (email → rate/model adjustment → pause → account
closure) is in the usage policies [43] (updated 2026-06-09) [44]. Gemini API additional terms: users of agentic services must not "automatically bypass any
requests for human confirmation"; no programmatic collection of grounding links; 18+; "don't rely on the
Services for … financial … advice" [42].

**Rate limits / caps.** API: tiers by spend — Free; Tier 1 (billing linked, $250 cap); Tier 2 ($100 spent + 3
days; $2,000 cap); Tier 3 ($1,000 + 30 days; $20,000–100,000+ cap); per-model RPM/TPM/RPD only visible in the AI Studio dashboard; 10-min
spend windows $10/$50/$200 [3]. Free tier, secondary sources (unverified, Sep 2026): Flash ≈10 RPM / 250k TPM /
RPD unconfirmed — Google's own geminicli.com quota page lists the free (unpaid) Gemini API key at 250 requests/day, Flash model only [21]; Flash-Lite 15 RPM / 1,000 RPD; **Pro models removed from free tier (Apr–May 2026)** [45][46].
Re-checked 2026-09-24: the rate-limits page publishes **no per-model RPM/TPM/RPD numbers at all** — "Rate limits …
can be viewed in Google AI Studio" at aistudio.google.com/rate-limit and "will automatically update" with tier [3]; the
pricing page says only "Free of charge" for 3.8 Flash input/output [2]. So the **only Google-published free-tier
number is 250 RPD (Flash)** [21]; every RPM/TPM figure in circulation is a dashboard screenshot. Treat free-tier RPM as
**unverifiable from public docs by design** — read it from the AI Studio dashboard on the actual key before sizing a lane.
Antigravity: no published absolute numbers; free = weekly reset; Pro/Ultra = refill every 5 h to a weekly
ceiling, metered "by work performed", capacity-dependent; AI-credit overages at Gemini Enterprise rates [27][28][29].
Jules: 15/100/300 tasks per rolling 24 h, 3/15/60 concurrent (Free/Pro/Ultra) [31].

**Sandboxing.** Managed agents run in Google-hosted Linux sandboxes [35]. Antigravity CLI has `--sandbox`
(terminal restrictions) [26] and a documented permission policy in `~/.gemini/antigravity-cli/settings.json`
(`toolPermission`: `request-review` (default, prompts for write/bash/web tools), `proceed-in-sandbox` (auto-runs
sandboxed terminal commands, else prompts), `strict` (prompts for all non-read tools), `always-proceed` (runs all
tools without prompting — 'highest risk'); plus `allowNonWorkspaceAccess` (off by default),
`enableTerminalSandbox`, `artifactReviewPolicy`) — this is the documented way to pre-authorise tools for
automation instead of `--dangerously-skip-permissions` [71]; Gemini CLI supports Docker/Seatbelt sandbox (documented elsewhere on
geminicli.com, not re-verified). **Known limitation**: in headless mode a tool call without an exact permission grant is auto-denied ('a tool required the "command" permission that headless mode cannot prompt for, so it was auto-denied') — the headless docs themselves describe this as policy: un-approvable tools are 'soft-denied: the run continues, exits `0`, and prints a notice to `stderr`' [26]; `autoExecutionPolicy: AUTO` is ignored (#1054, CLI 1.2.7, Sep 2026, which also notes the error text points at a non-existent `permissions.allow` path — the real key is `userSettings.globalPermissionGrants.allow`) [68] and a denied call can end the turn with status SUCCESS/exit 0 and an empty response (#1062, closed as duplicate) [76]; settings.json `"toolPermission": "always-proceed"` or `--dangerously-skip-permissions` bypass this
unless `--dangerously-skip-permissions` (issue #548, open since 2026-07-06, was filed on Windows 11 and is labelled `subtype:windows`; the reporter also says `--dangerously-skip-permissions` 'has its own long-standing silent tool-call failure'; the current tickets are #1054 (also filed on Windows 11, CLI 1.2.7, but the soft-deny behaviour it describes is the documented headless policy [26]) and #1080 (macOS arm64, CLI 1.2.7, asking which controls a bounded subscription-authenticated headless worker can rely on) — both open and 'awaiting response') [30][68][77].

**Structured events / orchestration.** Antigravity CLI JSON envelope: `conversation_id, status, response,
duration_seconds, num_turns, usage{input_tokens, output_tokens, thinking_tokens, cache_read_tokens,
total_tokens}, error, structured_output`; stream-json events `init | step_update | result`; exit 0 on success, non-zero on failure (docs do not enumerate codes; reason goes to stderr and `status`/`error`) [26]; status
`SUCCESS|ERROR|CANCELED|INTERRUPTED|INVALID|WAITING|RUNNING` [26]. Gemini CLI: `response, stats, error`;
stream events `init, message, tool_use, tool_result, error, result` [23]. Jules API: session/activities polling,
PR URL in outputs [32].

**Session resume.** `agy --continue` / `--conversation <id>` [26]; `gemini --resume` / `--include-directories`
(CLI reference [75]); Interactions API `previous_interaction_id` (state kept 55 days paid / 1 day free [74]);
managed-agent environments persist 7 days [35]; Jules sessions are addressable via API [32].

**Streaming.** SDK streaming, OpenAI `stream=True`, CLI `stream-json`, Interactions API streaming [26][35][37].

**macOS/Linux fit.** Everything above runs on macOS arm64; the Mac Mini has a logged-in GUI session, so the
one-time interactive `agy` login is feasible, but the credential is a personal OAuth token in the keyring and
must be refreshed manually if revoked.

### 3a. Data-handling matrix per lane and auth mode (for the cross-doc table)

| Lane / auth | Training use | Human review | Retention | Residency | ZDR eligible | Source |
|---|---|---|---|---|---|---|
| Developer API **free** key | **Yes** — "Google uses the content you submit … and any generated responses to provide, improve, and develop Google products" | Yes — "human reviewers may read, annotate, and process your API input and output" | Indefinite for improvement; 55-day abuse log | "any country in which Google or its agents maintain facilities" | No | [42][43] |
| Developer API **paid** key (Tier 1+) | **No** — "Google doesn't use your prompts … or responses to improve our products" | Not for improvement (abuse investigation only) | **55 days** abuse-monitoring log, "solely for detecting and preventing violations"; Interactions server state 55 days | same as above | **No ZDR offer on the Developer API** (no such language in the terms) | [42][43][74] |
| Gemini app / Scheduled Actions (Free, Plus, Pro, Ultra — no paid-tier difference stated) | **Yes when Keep Activity is on** (default) — extends "to the generative AI models"; **No when off** (unless you submit feedback) | Yes — subset reviewed by employees + service providers, "disconnected from your account" | Keep Activity on: auto-delete 18 months (3/36/never selectable); reviewed chats up to 3 years. Off: 72 hours | not stated | No | [82] |
| Gemini CLI via Google AI Pro/Ultra OAuth | Not stated in the CLI privacy page; governed by "Google One Additional Terms and Google Privacy Policy" — assume the Gemini-app row above (Keep Activity semantics) until Google says otherwise (unverified) | as above | as above | not stated | No | [24] |
| Gemini CLI via Code Assist individual (free Google account, still listed) | Governed by the Code Assist for individuals Privacy Notice (opt-out of usage statistics via config); training use not restated on the CLI page (unverified) | — | not disclosed | not stated | No | [24] |
| Antigravity CLI/IDE (any plan, OAuth) — **resolved 2026-09-24 via antigravity.google/terms** | **Yes by default.** Terms define "Interactions" as "user data, interaction data pertaining to your usage of the Service, related metadata … and any feedback" and state "We use Interactions to evaluate, develop, and improve Google and Alphabet research, products, services and machine learning technologies"; opt-out: "If you don't want your Interactions used in this way, navigate to settings to change your preference" — the IDE's **Enable Telemetry** toggle ("collects interactions for use in evaluating, developing, and improving Antigravity and models that support Antigravity") [95][71] | Yes — "Google employees and contractors may access, view, review and use Interactions" [95] | Not stated; deletion on request (antigravity-support@google.com) [95] | not stated | No | [95][71][28] |
| Antigravity CLI with `GEMINI_API_KEY` | Follows the API-key row (free or paid) — the CLI bills the API, not the subscription | as API row | as API row | as API row | No | [67][42] |
| Vertex AI / Agent Platform (service account) — **verified 2026-09-24** | **No** — "Google won't use your data to train or fine-tune any AI/ML models without your prior permission or instruction. This applies to all managed models … including GA and pre-GA models" [93] | Abuse-monitoring only; standard Google models: prompts logged for AUP review, "stored securely for up to 90 days"; models designated "Advanced AI": prompts + responses "up to 30 days" (Claude on Vertex also 30 days, shared with Anthropic) [94] | In-memory cache of inputs/outputs/derived data, project-isolated, **24-hour TTL**, not at rest; Live-API session resumption caches up to 24 h (off by default) [93] | Abuse logs "stored in the same region or multi-region selected by the customer"; global vs non-global endpoints priced separately [94][96] | **Yes** — "customers may request for an exception by filling out this form. If approved, Google won't store any prompts"; customers on a Google Cloud Master Agreement are exempt by default; "Zero data retention may not be possible when using some Advanced AI features" [93][94] | [93][94][96] |
| Jules API | Not found (docs not re-fetched for privacy) | — | — | — | — | [31][32] |

Rule for the paper-trading lab: **proprietary theses go only through a paid Developer-API key (row 2)**; the
consumer/OAuth rows train by default unless Keep Activity is off, and the free key trains unconditionally.

### 3b. Progress-visibility plumbing (quota/usage introspection and telemetry export)

| Lane | Remaining-budget introspection | Per-call usage | Telemetry export | Verdict for "watch their progress" |
|---|---|---|---|---|
| Developer API (any key) | **None programmatic.** Limits and usage only in AI Studio "Dashboard > Usage" and the rate-limit dashboard (UI); Cloud Billing export lags "typically within a day, … sometimes more than 24 hours" [3][83] | `usage_metadata` on every `generateContent`/Interactions response (input/output/thinking/cached tokens) [2][74] | None built in; you log `usage_metadata` yourself | Sum `usage_metadata` locally against the tier cap; RPM/RPD headroom is invisible until a 429 |
| Gemini CLI (OAuth or key) | `/stats model` shows "token counts and quota information" — **TUI only**, not in `-p` JSON [84] | headless JSON `stats` block [23] | **Yes — OpenTelemetry**: `telemetry.enabled`, `target: local|gcp`, `otlpEndpoint` (default `localhost:4317`, grpc/http), `outfile`; metrics = token usage (input/output/thought/cache per model), tool-call count/latency/success, API request count/latency, agent run duration/turns; `logPrompts` default true — set false [85] | Best Google lane for OTEL; still no remaining-quota metric |
| Antigravity CLI (subscription) | `/usage` ("Model Quotas") and "Baseline quota usage … in the settings page" — **TUI/IDE only**; no headless equivalent documented; absolute quota never published [28][29] | headless JSON `usage{input, output, thinking, cache_read, total}` per run [26] | **None documented** (no telemetry page found) | Blind budget: you learn the ceiling when a run degrades or refuses |
| Antigravity CLI (`GEMINI_API_KEY`) | as Developer API row | as above | none | as Developer API |
| Jules | tasks/day and concurrency are published per plan [31]; session/activity polling via API [32] | n/a | none | Countable: track your own task count against 15/100/300 |
| Vertex / Agent Platform | Cloud Monitoring "Monitor models" + cost labels (metric names not fetched, unverified) [80] | `usage_metadata` | Cloud Monitoring/Logging | Only lane with a real metrics backend, at Cloud-account cost |

Net: **no Google lane exposes remaining 5-hour/weekly budget programmatically**; the server must meter itself from
`usage_metadata`/CLI JSON and treat 429/quota-exhausted responses as the signal.

### 3c. Third-party-serving permission per lane (outputs consumed by non-owner users)

| Lane | May outputs be shown to other people (pickem dashboard, shared project sites)? | Basis |
|---|---|---|
| Developer API paid key | **Yes** — the API exists to build applications; "Google won't claim ownership over that content". Constraint: **grounded (Search/Maps) results may be displayed only "to the end user who submitted the prompt"** and may not be stored/collected programmatically; 18+ end users; no financial-advice reliance | [42] |
| Developer API free key | Same permission, but content is training data + human-reviewed, and free tier is unavailable in EEA/UK/CH — fine for public, non-confidential pages only | [42] |
| Gemini app / Scheduled Actions / Gemini CLI on Pro/Ultra OAuth | **Not prohibited, but not licensed for it either.** Google ToS: you keep IP in your content, Google claims none of the generated content; no clause bans sharing outputs; the only hard bans are automated access "in violation of … robots.txt", third-party software on the Gemini CLI OAuth ("using OpenClaw with Gemini CLI OAuth") and selling/transferring AI credits. Consumer quota is per-person ("Personal accounts"), so a subscription that feeds a multi-user surface is outside the product's design even if not enumerated | [24][86][87] |
| Antigravity (subscription) | Same as above; plans page says nothing on redistribution | [28] |
| Jules | PRs land in your repos; downstream users of the code are unaffected — no restriction found | [31][32] |

House rule (matches chatgpt-openai.md's "serves a second person → API key"): **anything a non-owner reads is generated
on a paid API key**; subscription/OAuth lanes serve only the owner's own briefs, reviews and interactive sessions.

### 3d. Cost of ownership from tool churn (release cadence / breaking-change burden)

| Surface | Cadence observed | Breaking or behaviour-changing events in the last 60 days | Burden |
|---|---|---|---|
| Antigravity CLI `agy` | **10 releases in 13 days** (1.2.1 09-11 → 1.2.10 09-24) | headless timeout default 5 m → unlimited (1.2.6); hooks.json truncation fix (1.2.4); API-key path discrepancies (1.2.9); open headless auto-deny tickets #1054/#1080 | **High** — pin the binary; re-run a smoke test per release |
| Gemini CLI | nightly builds daily + stable 0.61.0 on 09-23 (10 tags 09-18 → 09-24); no breaking changes flagged in those notes [88] | free Google-login tier removed 06-18 (auth change, not a code change) | **Medium** — track stable tags only |
| Developer API / SDK | `google-generativeai` deprecated 2025-11-30 → `google-genai`; `generateContent` declared legacy at Interactions GA (June 2026); 3.8 Flash dropped `temperature/top_p/top_k` and `thinking_budget` | `antigravity-preview-05-2026` → 09-2026 renamed parameters to PascalCase and changed edit semantics (shutdown 10-05); 2.5 access-restricted 09-18; intro price doubles 2027-01-01 | **Medium** — two migrations a year, each announced with a shutdown date [72][73] |
| Consumer plans | quota model rewritten at I/O 05-19 (daily counts → 5-h compute refresh); Ultra 20× price cut; Gemini CLI login tiers cut 06-18 | Antigravity third-party-model tiering contradicts itself across two Google pages | **Medium-high** — plan terms move quarterly |
| Jules | changelog-driven; API still `v1alpha` | none observed | Low-medium (alpha API) |

Comparable line for the crosscut table: Gemini = "agy: 10 rel/13 d, 3 headless-behaviour changes; SDK: 1 rename + 1
legacy-flag + 1 managed-agent break per half-year; plans: 3 term changes in 4 months".

### 3e. Cross-doc dimensions (added 2026-09-24, third pass)

**3e.1 Concurrency per lane on subscription auth (parallel headless sessions).** **CONFIRMED-ABSENT for the two
subscription CLIs**: the Antigravity plans page [28], headless page [26], install page [67], settings page [71] and
getting-started page [25] contain no occurrence of "parallel", "concurrent", "simultaneous" or "sessions"; the only
concurrency statement on any Antigravity page is that quota is "correlated with the amount of work done by the agent"
and "primarily determined to the degree we have capacity" [28] — i.e. N parallel `agy -p` runs drain the same 5-hour
pool N× faster and there is no published session cap to hit first. Gemini CLI publishes requests/day (1,500 Pro /
2,000 Ultra) and no RPM/session bound [21]. The **only Google-published concurrency numbers** are Jules' **3 / 15 / 60
concurrent tasks** (Free / Pro / Ultra) [31] and, on the metered lane, the per-tier RPM in the AI Studio dashboard [3].
Fan-out design consequence: cap the Gemini subscription lane at **1 concurrent `agy` session** in the scheduler until an
owner probe (two simultaneous `agy -p` runs, watch for a 429/quota status in the JSON `status`/`error` fields [26])
shows otherwise; fan out on the API key instead, where RPM is the bound and is readable in the dashboard.

**3e.2 Credential lifecycle on a headless box (facts for the cross-cut matrix).**

| Credential | Storage | TTL / refresh | Fails how | Source |
|---|---|---|---|---|
| Gemini CLI Google-account OAuth | **Plaintext JSON at `~/.gemini/oauth_creds.json`**, written with mode `0o600` (`OAUTH_FILE = 'oauth_creds.json'` under `Storage.getGlobalGeminiDir()`); Google account cached separately in `~/.gemini/` | Standard Google OAuth: short-lived access token + `refresh_token` in the file; `google-auth-library` refreshes silently; on every start the CLI calls `getAccessToken()` locally and then `getTokenInfo()` **against the server "to see if it hasn't been revoked"** | Revoked/expired refresh token → cached-credential load fails → interactive login is attempted; headless with no browser prints "Please try running again with NO_BROWSER=true set" (manual copy-paste flow) — i.e. a headless job **stops, it does not hang**; `GOOGLE_CLOUD_ACCESS_TOKEN` env is honoured as an override (not cached) for a pre-minted token | [99][23] |
| Gemini CLI MCP-server OAuth tokens | macOS Keychain via `KeychainTokenStorage`, with **encrypted-file fallback** (`isUsingFileFallback`, forced by an env flag) | per-server | keyring locked in a non-GUI launchd session → falls back to file | [99] |
| Antigravity CLI OAuth | **Apple Keychain** ("the CLI attempts to access your operating system's native secure keyring"); `/logout` "clears active credentials and local cache directories" and purges keyring profiles | **Undocumented** — no TTL, refresh or expiry text on any fetched page | Headless without cached auth: "fail with an authentication error rather than hanging" [26]; a Keychain that is locked (no GUI login session) is the realistic failure on a Mac Mini — keep the box auto-logged-in | [67][26] |
| Antigravity CLI `GEMINI_API_KEY` | env var + `modelProvider: gemini` in `~/.gemini/antigravity-cli/settings.json`; "no stored session to clear" | No expiry; revoke in AI Studio | 4xx on the API | [67] |
| Developer API key | env / `~/.gemini/.env` / server `.env`; Gemini CLI auto-loads `.env` upward from cwd then `~/.gemini/.env` | No expiry | 400/403 on revoke; **no expiry alarm needed** | [23][3] |
| Jules API key | header `X-Goog-Api-Key`, max 3 keys per account | No expiry | 401 | [32] |
| Vertex service account | ADC JSON / workload identity | Google-managed 1-h access tokens, auto-refreshed | IAM revoke | [93] |

What fails first on renewal: the **Antigravity Keychain credential** (undocumented TTL, needs an unlocked Keychain),
then the Gemini CLI refresh token (revocable at myaccount.google.com; the CLI detects revocation at start-up). API keys
never expire — the metered lane is the only one with no credential clock, which is another point for §7's lane-1 choice.
Gap that stays: neither Google CLI documents its refresh-token lifetime; treat both as "revocable at any time, no alarm".

**3e.3 Progress-visibility sink (collector side).** Emitters on the Google side: Gemini CLI **OTLP** — default
`http://localhost:4317`, `otlpProtocol: grpc|http`, or `outfile` for JSONL; metrics `gemini_cli.token.usage`
(input/output/thought/cache/tool), `gemini_cli.api.request.latency`, `gemini_cli.tool.call.count`,
`gen_ai.client.operation.duration`; log events `gemini_cli.user_prompt`, `gemini_cli.tool_call`,
`gemini_cli.api_response`, `approval_mode_switch`; `logPrompts` defaults **true** — set false [85]. Antigravity CLI has no
OTEL; its only emitter is the per-run JSON `usage{}` block [26]. The API lane emits `usage_metadata` per response [2][74].
Sink recommendation for a 16 GB Mac beside Postgres/Redis: **no Prometheus/Grafana/Langfuse daemon for one lane** — point
Gemini CLI at `outfile` (JSONL, zero daemons) and have the server's existing job runner parse `agy` JSON and SDK
`usage_metadata` into **one cross-lane event row** `{ts, lane, model, job_id, input, output, thinking, cache_read, cost_usd,
status}` in Postgres, which the existing web dashboard already reads. Remaining-budget inference per lane: API key → tier cap
minus Σ cost (exact); Antigravity → **unknowable** (no published ceiling; only the degrade/refuse signal, §3b); Gemini CLI
OAuth → Σ requests vs 1,500/2,000 per day (exact if you count). An OTLP collector is worth its ~100–200 MB only when a
second OTEL-emitting lane (Claude Code also emits OTEL) is wired up — then run one `otel-collector` with a file exporter,
not a Prometheus stack.

**3e.4 Empirical calibration against this server.** This pass was instructed not to read repo files, so the
150k-in/15k-out synthetic job in §4c stays; what changes is the **cache assumption**, stated explicitly: the §4c
table assumes **0 % cache**. Gemini's implicit caching (min 4,096-token prefix on 3.x, cached input at 10 % of list
[2][40]) makes the realistic per-job figure at 70 % cache hit **$0.19 → $0.12** for 3.8 Flash (150k × 0.3 × $0.75 + 150k ×
0.7 × $0.075 + 21k × $3.75 = $0.034 + $0.008 + $0.079). At 100 jobs/mo that is ~$12 vs ~$19; the subscription-vs-metered
verdict in §8 does not flip in either case because Antigravity's ceiling is unpublished (no number to compare against).
The numbers the owner must supply before the crosscut re-bases: real jobs/month, median tokens/job and cache-hit share from
`volumes/audit_log`, and the Claude Max tier — none of which changes the Gemini recommendation, which is API-key-first
regardless of Max tier because the Google subscription lane cannot be metered from outside.

**3e.5 Prompt-injection / sandbox posture per lane (server ingests Telegram text, fetched pages, MCP results).**

| Lane | Sandbox | Network from tools | Secrets exposure | Auto-run risk | Rank (1 = safest for untrusted input) |
|---|---|---|---|---|---|
| Developer API / SDK (§7 lane 1) | None — the model only returns JSON/function calls; **the server executes nothing the model says** unless it chooses to | n/a | n/a | Zero by construction; terms also forbid agents that "automatically bypass any requests for human confirmation" [42] | **1** |
| Managed agents (`antigravity-preview-09-2026`) | Google-hosted Ubuntu sandbox, env deleted after 7 idle days [35] | egress policy unverified (§2) | credentials you inject | Runs shell autonomously inside Google's box, not yours | 2 |
| Antigravity CLI `--sandbox` / `enableTerminalSandbox` | macOS **Seatbelt (SBPL)**: "restrict filesystem access and socket connections"; "Sensitive files like `~/.ssh` and `.env` are blocked, anything not explicitly mounted is invisible"; writes limited to project folders, temp and build caches [98] | **"Sandboxed commands run without network access by default"**; only domains granted via `read_url` permissions are added to the outbound allowlist [98] | `.env`/`~/.ssh` blocked | Pair with `toolPermission: proceed-in-sandbox` (auto-runs only sandboxed commands) [71]; `--dangerously-skip-permissions` removes the last check | 3 (best of the CLIs) |
| Gemini CLI `--sandbox` | Seatbelt via `sandbox-exec`; default profile **`permissive-open`**: writes confined to project dir, "broad file reads **and network access**"; stricter profiles selectable; Docker/Podman container option; "Sandboxing reduces but doesn't eliminate all risks" | **Allowed by default** (permissive-open) | broad reads allowed → `.env`/keys readable unless a restrictive profile is chosen | YOLO/auto-edit approval modes exist; event `approval_mode_switch` is logged [85] | 4 |
| Computer-use tool (3.8/3.5 Flash) | Your Playwright/desktop | full | full | Google's own page: "may contain errors and security vulnerabilities" [41] | 5 |
| Gemini app / Chrome auto browse / Spark | Google-controlled | full browser | your logged-in Google session | consumer surfaces, owner-only | n/a |

For the server's two ingest paths: Telegram text and fetched web pages should reach Gemini **only through lane 1**
(the model classifies/reviews; the server decides), and any `agy` job that touches untrusted content runs with
`enableTerminalSandbox: true` + `proceed-in-sandbox`, never `always-proceed`.

**3e.6 Host resource budget.** Lane 1 (SDK) adds **no daemon** — it is an HTTP client inside the existing Python
process. Gemini CLI and Antigravity CLI are per-job processes (Gemini CLI is Node; `agy` ships as a binary under
`~/.local/bin`), so their RAM is transient and **undocumented** on every fetched page; no always-on Google daemon is
proposed. The only optional resident is an OTLP collector (§3e.3), which this doc recommends against for a single lane.
Net Google contribution to the always-on budget: **0 MB**; transient per headless run: one Node/agy process (unmeasured —
record RSS on the first probe).

**3e.7 Reviewer independence.** Gemini is the one second-opinion lane in this research with **no distillation
allegation** attached to it in the sources read here (contrast the kimi/minimax/deepseek/qwen docs); its errors are
plausibly the least correlated with Claude's. Two caveats keep the independence claim honest: (i) Google's own 3.8 Flash
eval PDF admits mis-reporting Opus 5's DeepSWE score and blames Sonnet 5's content filters for HLE-Verified gaps [10], so
Google's *comparative* claims are not neutral evidence; (ii) on AA v4.3.2 the two models sit 12 points apart (41 vs 53)
[50][91], so "independent" also means "weaker" — use Gemini as a **detector of Claude's blind spots** (multimodal, geo,
long-context recall, finance-doc benchmarks where it leads [9][51]) rather than as a tie-breaker on hard reasoning.

**3e.8 Measured chat-surface latency (this lane's numbers; Claude's belong in claude.md).** Gemini: 3.8 Flash (high)
TTFT 14.71 s / 292 tok/s [50]; 3.5 Flash-Lite (reasoning) 8.21 s / 351 tok/s [90]; 3.8 Flash (low) **TTFT N/A** [92];
Flash-Lite non-reasoning **unmeasured**. For the crosscut row that still reads "not captured": AA's Claude Fable 5.1
number (264.69 s TTFT at max effort, 66.9 tok/s [91]) is a max-effort figure and **must not** be quoted as chat-surface
latency. **Owner probe (five minutes, free tier):** `for m in gemini-3.8-flash gemini-3.5-flash-lite; do for t in low
medium; do curl -sN -w '\nTTFB=%{time_starttransfer}\n' -H "x-goog-api-key: $GEMINI_API_KEY" \
"https://generativelanguage.googleapis.com/v1beta/models/$m:streamGenerateContent?alt=sse" -d '{"contents":[{"parts":[{"text":"In one sentence, what is a covered call?"}]}],"generationConfig":{"thinkingConfig":{"thinkingLevel":"'$t'"}}}' | head -c 300; done; done` — record `time_starttransfer` as TTFT and paste the four numbers into the
Telegram row of §8 and the crosscut table; the same loop against the Anthropic SDK at low/medium effort fills the Claude gap.

## 4. Cost

### 4a. Consumer plans (USD/month, monthly billing) [15][16][17][18]

| Plan | Price | Usage vs free | App context | Notable inclusions / caps |
|---|---|---|---|---|
| Free | $0 | standard daily limits | 32k | Gemini app (Flash; limited 3.1 Pro), NotebookLM 50 sources, Antigravity free tier (weekly quota), Jules 15 tasks/day (2.5 Pro), AI Studio + API free tier |
| Google AI Plus | **$4.99 — resolved 2026-09-24 (primary: gemini.google/subscriptions lists "Google AI Plus $4.99/month" [79]; one.google.com renders the Plus card with a blank "/mo" price [15], which is where the $9.99 confusion came from — $9.99 is not attributed to Plus on any Google page fetched). crosscut-tos's $9.99 should be corrected to $4.99.** | 2× | 128k | 400 GB storage, Gemini in Gmail/Docs, 3.1 Pro "2x access", limited Omni Flash, family sharing; **does not unlock Gemini CLI login ("Tiers not listed above, including Google AI Plus, are not supported" [21]) nor Antigravity's 5-h refill (Pro/Ultra only [28])** |
| Google AI Pro | $19.99 | 4× | 1M | 5 TB, Deep Research, Scheduled Actions prepared within the hour (the feature itself, 10 active, is available on free personal accounts) [19], Chrome auto browse (US), Jules 100 tasks/day, Antigravity 5-h refill quota, NotebookLM 300 sources, YouTube Premium Lite, Home Premium, Gemini CLI 1,500 req/day (conflicting, see §3) |
| Google AI Ultra (5×) | $99.99 | 5× Pro | 1M | 20 TB, Deep Think, Gemini Agent (US), Spark beta, Flow 25,000 credits, Jules 300 tasks/day, Antigravity highest limits + third-party models (Claude/gpt-oss) (unverified as of 2026-09-24: antigravity.google/pricing lists 'Claude Sonnet & Opus 4.6, gpt-oss-120b' under the Free tier while docs/plans says Ultra-only — live contradiction, CloudZero flags the same [27][28][29]), $40/mo Cloud credits, YouTube Premium |
| Google AI Ultra (20×) | $199.99 (cut from $249.99 on 2026-05-19) | 20× Pro | 1M | 30 TB, Project Genie, everything above |

I/O 2026 moved plans from daily prompt counts to a "compute-used" model refreshing every 5 h, with model
downgrade at cap and optional pay-as-you-go credits [16].

### 4b. API prices, Gemini Developer API paid tier ($/1M tokens) [2]

| Model | Input | Output | Cached input | Cache storage /h | Batch in/out | Notes |
|---|---|---|---|---|---|---|
| `gemini-3.8-flash` | 0.75 | 3.75 | 0.075 | 0.50 | 0.375 / 1.875 | intro through 2026-12-31; **1.50 / 7.50 from 2027-01-01** [6] |
| `gemini-3.7-flash`, `gemini-3.6-flash` | 0.75 | 3.75 | 0.075 | 0.50 | 0.375 / 1.875 | same intro schedule |
| `gemini-3.5-flash` | 1.50 | 9.00 | 0.15 | 1.00 | 0.75 / 4.50 | no scheduled change |
| `gemini-3.5-flash-lite` | 0.30 | 2.50 | 0.03 | 1.00 | 0.15 / 1.25 | caching not available for batch |
| `gemini-3.1-flash-lite` | 0.25 (0.50 audio) | 1.50 | 0.025 (0.05 audio) | 1.00 | 0.125 / 0.75 | |
| `gemini-3.1-pro-preview` | 2.00 (≤200k) / 4.00 (>200k) | 12.00 / 18.00 | 0.20 / 0.40 | 4.50 | 50% off | |
| `gemini-2.5-pro` | 1.25 / 2.50 | 10.00 / 15.00 | | | 50% off | access-restricted [1] |
| `gemini-2.5-flash` | 0.30 (1.00 audio) | 2.50 | | | 0.15 / 1.25 | |
| `gemini-embedding-2-preview` | 0.20 text; 0.45 image; 6.50 audio; 12.00 video | — | | | | |
| `deep-research-preview-04-2026` | billed at underlying model rates + tool fees; ≈$1–3/task; search grounding ≈80 queries/task at $14/1k ≈ $1.12 [61] (unverified as of 2026-09-24; secondary only — the deep-research doc [36] has no pricing) | | | | | |
| Search grounding (3.x) | 5,000 prompts/mo free, then $14 / 1,000 | | | | | [2] |
| Antigravity managed agent | model tokens + tool fees; sandbox compute free in preview [35] | | | | | |

Implicit caching is on by default for 2.5+; min cacheable prefix 4,096 tokens on 3.x [40].
**Vertex AI / Gemini Enterprise Agent Platform list prices — verified 2026-09-24 (page read by curl, not by a human)
[96]:** the *Global* endpoint is at **parity with the Developer API** — 3.8 Flash $0.75 / $3.75 (cached $0.075) through
2026-12-31 then $1.50 / $7.50; 3.5 Flash $1.50 / $9.00; 3.5 Flash-Lite $0.30 / $2.50 (cached $0.03); 3.1 Pro Preview
$2.00 / $4.00 in (≤200k / >200k), $12.00 / $18.00 out; 3.8 Flash Cyber $1.50 / $7.50. Extras the Developer API lacks:
**Non-global (regional) endpoints = +10 %** (3.8 Flash $0.825 / $4.125); a **Priority tier = 1.8×** (3.8 Flash $1.35 /
$6.75 intro, $2.70 / $13.50 from 2027; Flash-Lite $0.54 / $4.50); **Flex/Batch = 50 %** (3.1 Pro $1.00 / $6.00). The
Agent Platform model list carries the same IDs [80]. So Vertex buys three things the Developer API does not sell:
regional residency (+10 %), a priority-processing SKU (1.8×), and the ZDR/abuse-log exception in §3a — at the cost of a
Cloud project, IAM and billing export. Still not needed for this server's lanes; use it only if a residency or
priority requirement appears. **SLA [97]:** the Vertex AI SLA covers "Training, Deployment, and Batch Prediction ≥ 99.9 %",
AutoML online prediction ≥ 99.9 %, custom-model online prediction (≥ 2 nodes) ≥ 99.5 %, Pipelines ≥ 99.5 %, with financial
credits of 10 % / 25 % / 50 % (99–99.9 % / 95–99 % / < 95 %); **no line names Gemini, generative AI or Provisioned
Throughput** in the fetched text, so treat Gemini-on-Vertex as **no uptime SLA** unless a Provisioned Throughput contract
adds one (that document was not found).

**Free tier**: "free input & output tokens" on Flash/Flash-Lite/embeddings, "limited access", content used to
improve products; upgrade required for context caching / Batch (as presented on the pricing page) [2]. Free
tier not available in EEA/UK/CH [42].

### 4c. Monthly cost estimate — 150k input + 15k output per job

Assumptions: single call per job (real agent loops re-send context; multiply input by turns), no caching,
intro prices, 3.8 Flash `thinking_level=medium` (thinking tokens bill as output and 3.8 Flash is verbose —
Register/AA report ~40% more tokens per task than 3.7 [49][50]; add ~+40% output as a realistic overhead).

| Jobs/mo | (b) API `gemini-3.8-flash` (intro) | 3.8 Flash Batch | 3.8 Flash from 2027-01-01 | API `gemini-3.1-pro-preview` | API `gemini-3.5-flash-lite` | (a) Subscription route |
|---|---|---|---|---|---|---|
| 10 | $1.69 | $0.84 | $3.38 | $4.80 | $0.83 | $0 on API free tier (1.65M tok/mo; fits the ~250 RPD free API-key quota that geminicli.com lists [21] (per-model numbers only in AI Studio), data trained on) or $0 Antigravity free (weekly quota, unpublished) |
| 100 | $16.88 | $8.44 | $33.75 | $48.00 | $8.25 | API free tier still fits (≈16.5M tok/mo) if ≤10 RPM; else AI Pro $19.99 via `agy` (quota unpublished, unverified fit) |
| 1,000 | $168.75 | $84.38 | $337.50 | $480.00 | $82.50 | AI Pro $19.99 will almost certainly cap (165M tok/mo); AI Ultra 5× $99.99 or 20× $199.99 — fit unverified; API paid tier is deterministic |

Per-job arithmetic: 3.8 Flash = 150k×$0.75/M + 15k×$3.75/M = $0.1125 + $0.0563 = **$0.169**; 3.1 Pro = $0.30 +
$0.18 = **$0.48**; 3.5 Flash-Lite = $0.045 + $0.0375 = **$0.0825**. With the +40% verbosity overhead, 3.8 Flash
≈ $0.19/job. Deep Research jobs are a different animal: ≈$2 each ⇒ $20 / $200 / $2,000 [61] (unverified).

## 5. Strengths & weaknesses per reviews

**Benchmarks (official unless noted).**
- Gemini 3.1 Pro model card [7]: HLE 44.4% (no tools; vs Opus 4.6 40.0, GPT-5.2 34.5), ARC-AGI-2 77.1%
  (Opus 4.6 68.8), GPQA Diamond 94.3%, SWE-bench Verified 80.6% (Opus 4.6 80.8, Sonnet 4.6 79.6), LiveCodeBench
  Pro Elo 2887, MMMLU 92.6%. Note these compare against Feb-2026 competitors; Claude Fable 5/5.1 and GPT-5.5/5.6
  have since shipped.
- Gemini 3.8 Flash: Terminal-Bench 2.1 **90.8%** (3.7 Flash 81.6; "first model over 90" per
  secondary), SWE-Bench Pro 61.6% (60.4), SWE-Atlas 51.9%, τ³-bench Banking 38.1%, CharXiv 86.2%, HLE 45.4%
  (flat vs 45.7) — these figures come from DataCamp [11] (and presumably the eval PDF [10]); the Google launch
  post [9] as fetched states only HLE-Verified 54.9% and the finance/legal/DeepSWE claims; Google claims it "outperforms larger frontier models" on DeepSWE v1.1,
  Vals Finance Agent v2 and Harvey Legal. Google's own eval PDF notes it originally mis-reported Opus 5's
  DeepSWE score and that "a significant proportion" of HLE-Verified questions were blocked by Sonnet 5's
  content filters — i.e., the comparison columns are contestable [10].
- Artificial Analysis: **adopt 41 (#40 of 210) on Intelligence Index v4.3.2** [50]. The Register's launch-week
  figure of 59 (Claude Fable 5.1 = 66) [49] predates the v4.3.2 rescale: v4.3.2 is a 10-evaluation composite
  (AA-Briefcase v1.1, GDPval-AA v2.1, AutomationBench-AA, Terminal-Bench 4.0, SciCode, AA-LCR v1.1, AA-Omniscience,
  HLE, GDP.pdf, CritPt) whose Elo-based components were re-anchored ("We anchor the Elo scale by pinning DeepSeek V4.1
  Flash (max) at 1600"; "Whilst Elo scores shift, rank ordering is largely preserved") [89], so absolute numbers from
  before and after the version boundary are not comparable — only same-version pairs are. Same-version pairs on
  2026-09-24: 3.8 Flash (high) 41 / #40; 3.8 Flash (low) 33 / #71 [92]; 3.5 Flash-Lite 22 [90]; Claude Fable 5.1
  (adaptive, max effort) 53 / #4 [91]. The gap to Claude is therefore 12 index points, not 7 — Gemini's
  "cheapest at its level" claim survives, "ties the frontier" does not. (Resolved 2026-09-24; matches the
  llama-meta / crosscut-benchmarks reading of the rescale.)
  Output speed 296.8 tok/s (#1 of 210), TTFT 14.3 s, blended $0.58/M, "very verbose" (170M output tokens in
  eval vs 88M median) [50]. AA-Omniscience: 3.1 Pro leads the knowledge index and cut hallucination rate from
  88% (3 Pro) to 50% [51]. Re-fetched 2026-09-24: 3.8 Flash (high) TTFT **14.71 s**, 292.4 tok/s, "latency somewhat
  higher than average … in a similar price tier" [50].
- **Interactive-surface (Telegram round-trip) rating.** With `thinking_level=high` a 14.7 s TTFT [50] plus a
  ~500-token answer (≈1.7 s at 292 tok/s) gives ≈16–17 s before the first Telegram edit lands — **unsuitable** for
  a chat front-door (Telegram's own typing indicator expires at ~5 s). **Measured (AA, re-fetched 2026-09-24):** `gemini-3.8-flash` (low) — AA lists index 33 but **TTFT "N/A"**, speed
  unknown [92]; `gemini-3.5-flash-lite` (reasoning variant, the only one AA measures) — **TTFT 8.21 s**, 351.1 tok/s,
  "at the higher end compared to other reasoning models in a similar price tier"; "a non-reasoning variant may also
  exist" but is unmeasured [90]. So the earlier "sub-2 s class" assumption for Flash-Lite was **wrong for its
  default (reasoning-on) configuration**; only a thinking-off / `thinking_level=low` request can plausibly reach a
  Telegram-grade TTFT, and no third party has measured it. Rating for the chat surface, revised: **Flash-low /
  Flash-Lite-thinking-off = provisionally suitable (stream via `stream=True`; 297–351 tok/s is the fastest streaming
  rate in the market) but UNMEASURED — the owner probe in §3e.8 must run before this lane is routed; Flash-Lite with
  reasoning on (8.2 s), Flash-high (14.7 s), 3.1 Pro and Deep Research = background-only, deliver by message edit or
  follow-up.**
- LMArena text (secondary, Aug–Sep 2026): Claude Fable 5 #1 (~1525), Opus 4.8 / GPT-5.5 Pro ~1510, Gemini 3.1
  Pro Preview in the chasing cluster; Gemini strongest in Vision and Multi-turn categories [60] (unverified as of 2026-09-24; secondary only).

**Best at (consensus).** Speed + cost at a given intelligence level [49][50]; multimodal and video/PDF/chart
understanding (CharXiv, LVBench, "can tell whether a photo is of the thing or of the view from it" — jampa,
HN) [48][10]; real-world/geo knowledge via Search/Maps grounding [48]; terminal/long-horizon tool loops
(Terminal-Bench) [9]; finance/legal agent benchmarks [9]; HTML/JS generation ("really good at HTML JavaScript" —
simonw, HN) [48]; 1M context; breadth of factual knowledge (AA-Omniscience accuracy leader) [51].

**Weak at (consensus).** Agentic coding discipline: HN 3.1 Pro thread (963 pts / 914 comments as of 2026-09-24) — "consistently
the most frustrating model I've used for development"; thinking loops that "burn 10s of 1000s of tokens
repeating itself" (jbellis); "randomly fail reading PDFs … and just makes shit up" (ant6n); ex-Googler spankalee's
"plan-in-Gemini, execute-in-Claude" workflow [47]. 3.8 Flash thread: hard-coded fake values ("sixty FPS" —
badlucklottery), over-engineering, 11k+ extra tokens per task, search grounding is exclude-list only [48].
Register/DataCamp: exam-style reasoning flat, +40% tokens per task, intro price doubles in 2027 [11][49].
Hallucination: 3 Pro fabricated 88% of the time when it didn't know; 3.1 Pro improved to 50% — still a
"confident guesser" profile [51]. Hidden/summarised chain-of-thought is opaque vs Claude [47]. Fragmented access
(Google One / AI Studio / Cloud / Antigravity) confuses even HN [48].

**Reliability / outage record.** StatusGator logged 173+ incidents on AI Studio/Gemini API since Jun 2025, 5 in
the last 30 days (mostly billing/batch), notable 1.5–2.5 h disruptions on Aug 27, Sep 11, Sep 15 2026; rates
Google's official status page "D — never acknowledged most detected incidents" [52].
**Normalized window for the cross-provider comparison (2026-08-25 → 2026-09-24, one third-party source + one vendor
source):** StatusGator = 5 detected incidents in 30 days, the last three being Sep 16 (batch requests not finishing in
24 h, 15 min; combined billing+batch, 6 h) and Sep 17 (billing/payment settings, 5 min); official grade D, "avg. delay
2–4 hrs" [52]. Vendor source = Google Cloud status summary: **zero** Gemini/Vertex incidents in Aug–Sep 2026; the last
Gemini API entry is 2026-02-27 (global-endpoint error rates, 1 h 58 m) [81]; AI Studio's own status page returns no
incident history at all. Read the pair as "5 detected / 0 acknowledged". **Priority/SLA tiers:** none on the Developer
API (no priority processing SKU, no uptime commitment in the terms [42]); Provisioned Throughput and a **Priority tier (1.8× list price)** exist only on Vertex/
Agent Platform [80][96]; the Vertex SLA names training/deployment/batch/online-prediction services but not Gemini or
generative AI [97]. For the crosscut table: Gemini = 5 / 0 / no SLA on the Developer API (none named for Gemini on
Vertex either) / priority tier only on Vertex at 1.8×. Model-availability
churn is a second reliability axis: Pro removed from free API tier (Apr 2026), Gemini CLI free tier killed
(Jun 18 2026), 2.5 models access-restricted, Antigravity quotas "primarily determined … by capacity" [1][21][29].

**Controversies.** Gemini CLI abuse/priority update (1,039 downvotes vs 137 up on GitHub) [22]; Nano Banana
integration into Google Earth pulled within 24 h after users generated disaster/9-11 imagery (2026-07-30) [12];
Gemini "hacked 3 companies" during independent cybersecurity testing (2026-09-18) [57]; 3.5 Pro missed three
announced dates [13]; free-tier prompts are human-reviewed training data [42].

## 6. Finance / trading relevance

- **Google Finance (consumer, free)**: Gemini "Deep Search" for multi-step cited market research, live earnings
  audio + transcripts, AI earnings "at a glance", advanced charting, watchlists, **prediction-market data from
  Kalshi and Polymarket** (all announced 2025-11-06 [53]); Deep Search 'with higher limits for Google AI Pro and AI
  Ultra subscribers' (Pro/Ultra-gated higher limits, per that post); US (all features) + India; no API/export [53]. A
  standalone Android app and "out of beta" status on 2026-06-25 is reported only by a low-quality secondary
  source (unverified) [64].
- **Gemini app**: Scheduled Actions can produce "daily market reports tracking your stock portfolio, crypto …"
  but Google warns responses are pre-computed so "rapidly changing data, like stock prices, won't be the
  latest" [19]. Deep Research (Pro/Ultra) for fundamental write-ups.
- **API-level market data**: none native. Google Search grounding (real-time web, $14/1k after 5,000/mo) and
  URL context are the only built-in "live" tools [2][4]; you bring your own market feed (Alpaca/Tradier/Finnhub)
  via function calling or MCP. Managed agents can reportedly reach your own data APIs (default egress policy unverified as of 2026-09-24) [35].
- **Deep Research API** (`deep-research-preview-04-2026` / `-max-`): async, cited reports, optional
  visualisations; ≈$1–3/task (unverified as of 2026-09-24; secondary only [61]); suited to weekly thesis reviews, not intraday [36].
- **Gemini Enterprise for Financial Services** (2026-08-25, preview): Financial Research agent with 50+ skills,
  confidence scores, MCP connectors to FactSet, S&P Global, LSEG, Finnhub, Fiscal.ai, Daloopa, Moody's, MSCI,
  PitchBook, SEC Edgar, D&B, CoinDesk; design partners Deutsche Bank, CME; **enterprise-only, no individual
  access, pricing unpublished** [54].
- **Benchmarks**: 3.8 Flash claims top marks on Vals Finance Agent v2 and τ³-bench Banking 38.1% [9][11] —
  relevant to document/earnings analysis, not to alpha.
- **Restrictions**: API terms disclaim financial advice; agentic services may not auto-bypass human
  confirmation [42]. Nothing prohibits paper-trading research. No Google-provided order routing.

## 7. Integration recipe for our server

**Recommendation.** Two lanes, both API-key-free of Anthropic policy conflicts (Google key only):

1. **Primary (deterministic, headless): Gemini Developer API, paid Tier 1, `google-genai` Python SDK,
   model `gemini-3.8-flash` with `thinking_level` per task, Batch for anything not latency-sensitive.**
   Rationale: subscription-driven `agy` headless mode auto-denies tool calls unless pre-granted or run with
   `--dangerously-skip-permissions` [26][68], its quota is unpublished [29], its OAuth is a personal token, and
   the binary changes almost daily [70]. (An `agy` API-key lane exists [67] but it is metered the same as the SDK
   and hooks reportedly do not fire there (#893) [69], so the SDK is the cleaner metered path.) A
   paid API key costs ~$17/mo at 100 jobs and keeps prompts out of training [2][42]. Start on the **free tier**
   for classification/routing/adversarial-review tasks that carry no private data (Flash only, 250 RPD per geminicli.com's quota page [21]; RPM is
   published nowhere — read it from the AI Studio rate-limit dashboard [3]; the ≈10 RPM figure is secondary [45]).
   Data/serving/visibility rules for both lanes are in §3a–3c: proprietary theses and anything a non-owner reads go
   through the paid key; the server meters itself from `usage_metadata` because no lane exposes remaining quota.
2. **Secondary (subscription value, human-adjacent): Google AI Pro ($19.99)** for the owner's own Gemini app
   Scheduled Actions (daily brief / portfolio digest), Chrome auto browse, Jules (100 tasks/day via API with
   `AUTO_CREATE_PR` — a genuine free-ish async code-review/patch worker for hosted projects) and Antigravity
   IDE/CLI for interactive work. `agy -p` can run unattended today with `--dangerously-skip-permissions` (or settings `"toolPermission": "always-proceed"`) — otherwise un-granted tool calls are auto-denied (#1054) [26][68]; the real open risks are unpublished subscription quota [29], hooks not firing under API-key auth (#893) [69], and a CLI that ships a release almost daily (1.2.1→1.2.10 in Sep 2026) [70] — pin the version.

**Minimal sketches.**

```python
# pip install google-genai   (Python 3.12 OK)   export GEMINI_API_KEY=...
from google import genai
from google.genai import types

client = genai.Client()  # reads GEMINI_API_KEY
resp = client.models.generate_content(
    model="gemini-3.8-flash",
    contents=[types.Part.from_text(text=prompt)],
    config=types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_level="medium"),
        response_mime_type="application/json",
        response_schema=ReviewVerdict,          # pydantic model -> structured output
        tools=[types.Tool(google_search=types.GoogleSearch())],  # optional live web
    ),
)
print(resp.parsed, resp.usage_metadata)
# NOTE: generateContent is 'legacy' since the Interactions API went GA (June 2026) [74]. For multi-turn/tool
# loops prefer server-side state (retained 55 days paid / 1 day free):
#   it = client.interactions.create(model="gemini-3.8-flash", input=prompt, tools=[...])
#   it2 = client.interactions.create(model="gemini-3.8-flash", previous_interaction_id=it.id,
#             input=[{"type": "function_result", "name": step.name, "call_id": step.id, "result": [...]}])
# If you stay on generate_content, every FunctionResponse must carry call_id AND name [6][78].

# Batch (50% off): client.batches.create(model="gemini-3.8-flash", src="jobs.jsonl")
# Deep Research (async): client.interactions.create(input=q, agent="deep-research-preview-04-2026", background=True)
```

```bash
# OpenAI-compatible drop-in (reuse any existing OpenAI client/router in the server):
OPENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/ OPENAI_API_KEY=$GEMINI_API_KEY \
  python -c 'from openai import OpenAI; print(OpenAI().chat.completions.create(model="gemini-3.8-flash", \
  reasoning_effort="low", messages=[{"role":"user","content":"ping"}]).choices[0].message.content)'

# Subscription lane (after one interactive `agy` login on the Mac Mini GUI session):
agy -p "Review the diff in $PWD for correctness; output JSON" --model gemini-3.8-flash-high \
    --output-format json --json-schema review.schema.json --print-timeout 10m \
    --dangerously-skip-permissions | jq '.structured_output, .usage'

# Jules async PR worker:
curl -s -X POST https://jules.googleapis.com/v1alpha/sessions -H "X-Goog-Api-Key: $JULES_KEY" \
  -d '{"prompt":"Fix flaky test X","sourceContext":{"source":"sources/github/<owner>/<repo>","githubRepoContext":{"startingBranch":"main"}},"automationMode":"AUTO_CREATE_PR"}'
```

**Task-class fit here.**
- *Research* (Atlas weekly theses, sector scans): good — 1M context, Search grounding, Deep Research API; watch
  the confident-guessing profile [51]; require citations and cross-check numbers.
- *Coding / build loops*: use as a **second opinion or cheap first pass**; community strongly prefers Claude for
  execution [47][48]. Jules is the exception worth trialling for scoped, test-covered PRs.
- *Code review*: fits — Terminal-Bench/SWE-Pro strength, JSON verdicts, $0.17/job [2][9].
- *Chat (Telegram front-door)*: via API only, **and only after the §3e.8 TTFT probe** — every AA-measured Gemini
  configuration is 8–15 s to first token [50][90]; no native Telegram integration.
- *Classification / routing*: `gemini-3.5-flash-lite` or 3.8 Flash `thinking_level=low` on free tier — best
  cost/latency in the market for this [2][50].
- *Adversarial review (governor/evaluate)*: strong — different training lineage from Claude, cheap, fast;
  set `thinking_level=high` and structured output.
- *Trading research*: good for earnings/filing digestion and Vals-Finance-style tasks [9]; no market data of its
  own; not for intraday signals (no real-time feed, Scheduled Actions are stale) [19].

**Gotchas.**
- 3.8 Flash rejects `thinking_level=minimal` and deprecated sampling params; migrate `thinking_budget` →
  `thinking_level` [6]. Thinking tokens bill as output; budget +40% [49][50].
- `generateContent` is legacy since the Interactions API GA (June 2026); on `generateContent` every
  `FunctionResponse` needs `call_id` + `name`; Interactions state lives 55 days paid / 1 day free [6][74][78].
- `antigravity-preview-05-2026` shuts down 2026-10-05 and 09-2026 changed parameter casing to PascalCase and
  edits to line-range — a managed-agent integration written before Sep 17 breaks [72][73].
- Intro pricing doubles 2027-01-01 [6]; Pro line is preview-only, no stable SKU to pin [1].
- Free tier = training data + human review; not for Atlas ledgers or owner data [42]. Tier 1 has a $250 spend
  cap and $10 / 10-minute window [3].
- Gemini CLI OAuth via third-party clients = ToS violation [22][24]; only official CLIs.
- `agy -p` auto-denies un-granted tools (documented soft-deny [26]; #1054 [68]) — pre-grant via settings.json `toolPermission` [71] or use `--dangerously-skip-permissions`; a denied call can still exit 0 with an empty response (#1062) [76]; `agy` supports Gemini API-key auth (`modelProvider: gemini` + `GEMINI_API_KEY`, per the install docs [67]) but hooks reportedly do not fire in that mode (#893) [69]; OAuth is only required for the subscription-quota lane.
- Search-grounding results may not be programmatically collected/stored [42].
- Deep Research costs ≈$2/task before you notice [61]; always `background=True` and poll [36].
- Status page under-reports outages; add your own probe [52].
- Batch/caching shown as paid-tier-only on the pricing page [2]; explicit caching not supported in the
  Interactions API [40].

## 8. Verdict

1. Gemini is the best **price/speed** option in the market today: `gemini-3.8-flash` at $0.75/$3.75 with a 1M
   window, top Terminal-Bench, and a still-usable free tier — but that intro price doubles in 2027 and the free
   tier feeds training.
2. It is **not** a Claude replacement for agentic coding; reviewers and HN converge on "plan/research in
   Gemini, execute in Claude", and Google's own flagship Pro line is stalled at a February preview.
3. The **subscription-driven headless path is immature**: Gemini CLI's free login is gone, Antigravity CLI's
   headless tool calls are auto-denied unless pre-granted or run with `--dangerously-skip-permissions` (#1054; #548 is a Windows report; the soft-deny is documented policy [26][68]), and it does have an API-key auth mode [67] and its quotas are unpublished, so metered API is the reliable
   automation lane despite the owner's preference — cost is small ($17–170/mo at 100–1,000 jobs).
4. Unique assets worth wiring in: Jules (async PR worker inside AI Pro), Deep Research API, Search/Maps
   grounding, video/PDF multimodality, and Google Finance/Scheduled Actions for the owner's personal briefs.
5. For Atlas: excellent document/earnings analysis and adversarial second-opinion reviewer; brings no market
   data and must not be trusted for uncited numbers.

Anchors used (so the crosscut scorecard can re-base every provider on one scale): **10** = best-in-market
today with no caveat; **8** = top-3 with one material caveat; **6** = usable with a workaround the server must own;
**4** = works but you would not choose it; **2** = unfit. Automation is scored on the *headless subscription lane*
(the owner's preferred mode), not on the metered API, which would score 8.

| Dimension | Score /10 | Why |
|---|---|---|
| Research | 8 | 1M context, grounding, Deep Research API, AA-Omniscience accuracy leader; hallucination-when-unsure profile costs points |
| Coding / agentic | 6 | Terminal-Bench leader on paper; community reliability complaints, token bloat, Pro stalled; Jules is a real plus |
| Cost efficiency | 8 | Cheapest at its intelligence level, Batch 50%, free tier; verbosity + 2027 price doubling |
| Automation friendliness | 6 | Excellent SDK/OpenAI-compat/JSON/batch/Interactions (metered lane alone = 8); subscription headless lane workable only with pre-granted or skipped permissions and unpublished quota, no programmatic quota introspection on any lane (§3b), daily CLI releases (§3d), `agy` OAuth for subscription quota or `GEMINI_API_KEY` for metered use, ToS churn |
| Chat-surface latency (Telegram) | 5 | Flash-low/Flash-Lite stream at the market's fastest tok/s (292–351 tok/s), but every *measured* configuration is reasoning-on with 8.2 s (Flash-Lite) to 14.7 s (Flash-high) TTFT [50][90]; Flash-low / Flash-Lite-thinking-off are unmeasured (AA: "N/A" [92]) — the §3e.8 probe is required before this lane is routed |
| Trading research | 6 | Strong finance-doc benchmarks and Google Finance surface; no data feed, stale scheduled outputs, enterprise finance stack out of reach |

## 9. Sources

All accessed 2026-09-24.

1. https://ai.google.dev/gemini-api/docs/models
2. https://ai.google.dev/gemini-api/docs/pricing
3. https://ai.google.dev/gemini-api/docs/rate-limits
4. https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash
5. https://ai.google.dev/gemini-api/docs/models/gemini-3.1-pro-preview
6. https://ai.google.dev/gemini-api/docs/latest-model
7. https://deepmind.google/models/model-cards/gemini-3-1-pro/
8. https://storage.googleapis.com/deepmind-media/Model-Cards/Gemini-3-8-Flash-Model-Card.pdf
9. https://blog.google/innovation-and-ai/models-and-research/gemini-models/3-8-flash-and-3-8-flash-cyber/
10. https://storage.googleapis.com/deepmind-media/gemini/gemini_3-8_flash_model_evaluation.pdf
11. https://www.datacamp.com/blog/gemini-3-8-flash-cyber
12. https://en.wikipedia.org/wiki/Gemini_(language_model)
13. https://9to5google.com/2026/07/16/gemini-3-5-pro-delays/
14. https://blog.google/products-and-platforms/products/gemini/gemini-3-deep-think/
15. https://one.google.com/about/google-ai-plans/
16. https://blog.google/products-and-platforms/products/google-one/google-ai-subscriptions/
17. https://9to5google.com/2026/05/25/google-one-ai-ultra-clarification/
18. https://support.google.com/gemini/answer/16275805?hl=en
19. https://support.google.com/gemini/answer/16316416?hl=en&co=GENIE.Platform%3DDesktop
20. https://gemini.google/release-notes/
21. https://geminicli.com/docs/resources/quota-and-pricing/
22. https://github.com/google-gemini/gemini-cli/discussions/22970
23. https://geminicli.com/docs/cli/headless/
24. https://geminicli.com/docs/resources/tos-privacy/
25. https://antigravity.google/docs/getting-started?tab=cli
26. https://antigravity.google/docs/cli/headless/
27. https://antigravity.google/pricing
28. https://antigravity.google/docs/plans
29. https://www.cloudzero.com/blog/google-antigravity-pricing/ (updated 2026-09-18)
30. https://github.com/google-antigravity/antigravity-cli/issues/548
31. https://jules.google/docs/usage-limits/
32. https://developers.google.com/jules/api
33. https://jules.google/docs/changelog/
34. https://blog.google/innovation-and-ai/technology/developers-tools/google-io-2026-developer-highlights/
35. https://ai.google.dev/gemini-api/docs/agents
36. https://ai.google.dev/gemini-api/docs/interactions/deep-research
37. https://ai.google.dev/gemini-api/docs/openai (updated 2026-09-02)
38. https://ai.google.dev/gemini-api/docs/libraries
39. https://ai.google.dev/gemini-api/docs/batch-api
40. https://ai.google.dev/gemini-api/docs/caching
41. https://ai.google.dev/gemini-api/docs/computer-use
42. https://ai.google.dev/gemini-api/terms
43. https://ai.google.dev/gemini-api/docs/usage-policies
44. https://zylos.ai/research/2026-07-13-subscription-auth-boundaries-official-cli-agent-automation/
45. https://pecollective.com/tools/gemini-free-tier-guide/ (secondary, Sep 2026)
46. https://tinkerllm.com/blog/gemini-api-free-tier-limits-rate-quotas/ (secondary, 2026-05-07)
47. https://news.ycombinator.com/item?id=47074735 (Gemini 3.1 Pro thread)
48. https://news.ycombinator.com/item?id=49537553 (Gemini 3.8 Flash thread, 1,160 pts / 669 comments)
49. https://www.theregister.com/ai-and-ml/2026/09/02/with-gemini-38-flash-google-reminds-everyone-its-still-in-the-race/5294049
50. https://artificialanalysis.ai/models/gemini-3-8-flash
51. https://x.com/ArtificialAnlys/status/2024518556659179685
52. https://statusgator.com/services/google-ai-studio-and-gemini-api
53. https://blog.google/products/search/new-google-finance-ai-deep-search/
54. https://cloud.google.com/blog/products/ai-machine-learning/introducing-gemini-enterprise-for-financial-services
55. https://gemini.google/overview/gemini-in-chrome/
56. https://techcrunch.com/2026/07/01/gemini-spark-googles-agentic-assistant-is-now-available-on-mac/
57. https://en.wikipedia.org/wiki/Google_Gemini
58. https://github.com/google-github-actions/run-gemini-cli
59. https://www.androidauthority.com/gemini-scheduled-actions-3654445/
60. https://localaimaster.com/blog/lmarena-chatbot-arena-leaderboard (secondary LMArena snapshot)
61. https://tokencost.app/blog/gemini-deep-research-agent-cost (secondary)
62. https://support.google.com/gemini/answer/15235603?hl=en
63. https://elephas.app/blog/notebooklm-source-limits (secondary)
64. https://www.lycamobile.pl/blog/en/google-finance-app-ai-analysis/ (low-quality secondary; unverified)
65. https://developers.googleblog.com/build-with-google-antigravity-our-new-agentic-development-platform/
66. https://gofastmcp.com/integrations/gemini (MCP support in google-genai SDK; secondary)
67. https://antigravity.google/docs/cli/install (API-key mode: `modelProvider: gemini` + `GEMINI_API_KEY`)
68. https://github.com/google-antigravity/antigravity-cli/issues/1054 (headless auto-deny; opened 2026-09-19, CLI 1.2.7, Windows 11)
69. https://github.com/google-antigravity/antigravity-cli/issues/893 (hooks not executed under GEMINI_API_KEY; opened 2026-08-28)
70. https://github.com/google-antigravity/antigravity-cli/releases (1.2.1 2026-09-11 → 1.2.10 2026-09-24)
71. https://antigravity.google/docs/settings?tab=cli (`toolPermission` modes, `allowNonWorkspaceAccess`)
72. https://ai.google.dev/gemini-api/docs/changelog
73. https://ai.google.dev/gemini-api/docs/deprecations
74. https://ai.google.dev/gemini-api/docs/interactions (GA June 2026; retention 55 d paid / 1 d free)
75. https://geminicli.com/docs/cli/cli-reference/ (`--resume`, `--include-directories`)
76. https://github.com/google-antigravity/antigravity-cli/issues/1062 (denied tool call → SUCCESS/exit 0; closed as duplicate)
77. https://github.com/google-antigravity/antigravity-cli/issues/1080 (macOS arm64 headless worker controls; opened 2026-09-21)
78. https://ai.google.dev/gemini-api/docs/interactions/function-calling (`function_result` requires `name` + `call_id`)
79. https://gemini.google/subscriptions/ (Google AI Plus $4.99/month, Pro $19.99, Ultra from $99.99 / $199.99; fetched 2026-09-24)
80. https://docs.cloud.google.com/vertex-ai/generative-ai/docs/learn/models (Agent Platform model list; pricing/quota/data-governance/SLA pages under docs.cloud.google.com rendered navigation-only on 2026-09-24 — Vertex parity still unverified)
81. https://status.cloud.google.com/summary (Google Cloud status: no Gemini/Vertex incident Aug–Sep 2026; last Gemini API entry 2026-02-27, 1 h 58 m)
82. https://support.google.com/gemini/answer/13594961?hl=en (Gemini Apps Privacy Hub: Keep Activity on → training + human review, 18-month default retention, 3 years if reviewed; off → 72 hours, no training)
83. https://ai.google.dev/gemini-api/docs/billing (usage only in AI Studio Dashboard > Usage; Cloud Billing lag "typically within a day … sometimes more than 24 hours"; no usage API)
84. https://geminicli.com/docs/reference/commands/ (`/stats session|model|tools`; `model` shows "token counts and quota information")
85. https://geminicli.com/docs/cli/telemetry/ (OpenTelemetry: `telemetry.enabled/target/otlpEndpoint/otlpProtocol/outfile/logPrompts`; token, tool-call, API-request, agent-run metrics)
86. https://policies.google.com/terms (Google ToS: "Google won't claim ownership over that content"; automated-access ban limited to robots.txt violations)
87. https://one.google.com/terms-of-service (Google One terms: "You may not sell or transfer AI credits"; family-sharing rules; no automation or third-party-serving clause)
88. https://github.com/google-gemini/gemini-cli/releases (v0.61.0 stable 2026-09-23; nightly tags daily 09-18 → 09-24; no breaking changes flagged)
89. https://artificialanalysis.ai/methodology/intelligence-benchmarking (Intelligence Index v4.3.2 = 10 evaluations; AA-Briefcase v1.1 / GDPval-AA v2.1 Elo re-anchoring — "Whilst Elo scores shift, rank ordering is largely preserved"; normalisation `clamp((Elo - 500) / 2000)`)
90. https://artificialanalysis.ai/models/gemini-3-5-flash-lite (index 22 on v4.3.2; reasoning variant TTFT 8.21 s, 351.1 tok/s, $0.30 / $2.50; "a non-reasoning variant may also exist", unmeasured)
91. https://artificialanalysis.ai/models/claude-fable-5-1 (index 53, #4 of 210 on v4.3.2; adaptive reasoning / max effort TTFT 264.69 s, 66.9 tok/s — not a chat-surface figure)
92. https://artificialanalysis.ai/models/gemini-3-8-flash-low (index 33, #71 of 210 on v4.3.2; TTFT "N/A", speed unknown; $0.75 / $3.75, 90 % cache discount)
93. https://docs.cloud.google.com/vertex-ai/generative-ai/docs/data-governance ("Gemini Enterprise Agent Platform and zero data retention": training restriction for all managed models; in-memory 24-h cache; Live session-resumption 24 h; ZDR steps)
94. https://docs.cloud.google.com/vertex-ai/generative-ai/docs/learn/abuse-monitoring (standard models: prompt logs "up to 90 days"; "Advanced AI" models: prompts + responses "up to 30 days"; Master Agreement customers exempt; exception form; region-pinned storage; Claude on Vertex 30 days shared with Anthropic)
95. https://antigravity.google/terms ("Interactions" used "to evaluate, develop, and improve … machine learning technologies"; employees/contractors may review; settings opt-out; deletion via antigravity-support@google.com; "using OpenClaw with Antigravity OAuth" prohibited; Anthropic commercial terms apply to third-party models)
96. https://cloud.google.com/vertex-ai/generative-ai/pricing (read by curl 2026-09-24: Global = Developer-API parity; Non-global +10 %; Priority 1.8×; Flex/Batch 50 %; 3.8 Flash intro $0.75 / $3.75 → $1.50 / $7.50 from 2027-01-01)
97. https://cloud.google.com/vertex-ai/sla (Training/Deployment/Batch ≥ 99.9 %, AutoML online ≥ 99.9 %, custom online ≥ 99.5 %, Pipelines ≥ 99.5 %; credits 10 / 25 / 50 %; no Gemini / generative-AI / Provisioned-Throughput line)
98. https://antigravity.google/docs/sandbox?tab=cli (Seatbelt SBPL; "Sandboxed commands run without network access by default"; `~/.ssh` and `.env` blocked; `enableTerminalSandbox` / `--sandbox`; `read_url` domains join the outbound allowlist)
99. https://github.com/google-gemini/gemini-cli/blob/main/packages/core/src/code_assist/oauth2.ts (+ `config/storage.ts`: `OAUTH_FILE = 'oauth_creds.json'` under `~/.gemini/`, written mode 0o600; `getTokenInfo()` revocation check at start-up; `NO_BROWSER=true` manual flow; `GOOGLE_CLOUD_ACCESS_TOKEN` override; `mcp/token-storage/hybrid-token-storage.ts`: Keychain with encrypted-file fallback)

## Verification log (2026-09-24)

**Corrections applied: 21** — critical 4 (agy API-key auth ×2, `antigravity-preview-09-2026` ×2), major 10
(Scheduled Actions availability ×2, headless permission behaviour ×2, lane-2 recommendation, verdict §8.3,
`--print-timeout` default, free-tier RPD ×3), minor 7 (Gemini CLI API-key note, 3.8 Flash knowledge cutoff,
exit-code wording, Flash-Lite price rows ×2, HN thread counts, scorecard wording).

**Claims re-verified today (primary fetches):**
- Antigravity CLI API-key mode (`modelProvider: gemini` + `GEMINI_API_KEY`; "Only setting a `GEMINI_API_KEY`
  environment variable on its own has no effect") — antigravity.google/docs/cli/install [67].
- Headless soft-deny policy ("soft-denied: the run continues, exits `0`, and prints a notice to `stderr`"),
  `--print-timeout` still documented as 5m, exit 0 = success / non-zero = failure — antigravity.google/docs/cli/headless [26].
- #1054 (opened 2026-09-19, CLI 1.2.7, Windows 11, open/awaiting response; error text; `userSettings.globalPermissionGrants.allow`)
  [68]; #1062 (closed as duplicate) [76]; #548 (Windows 11, `subtype:windows`, open) [30]; #1080 (macOS arm64,
  CLI 1.2.7, open) [77]; #893 (opened 2026-08-28, open, hooks loaded but not executed under `GEMINI_API_KEY`) [69].
- Releases 1.2.1 (09-11) … 1.2.10 (09-24); 1.2.6 headless timeout → unlimited + daemon commands in API-key
  sessions; 1.2.4 hooks.json truncation fix; 1.2.9 API-key discrepancy note — GitHub releases [70].
- settings.json `toolPermission` modes (`request-review` default, `proceed-in-sandbox`, `strict`,
  `always-proceed`), `allowNonWorkspaceAccess` off by default — antigravity.google/docs/settings?tab=cli [71].
- System requirements: macOS 12+ Apple Silicon only, Windows 10 64-bit, Linux glibc ≥ 2.28 — getting-started [25].
- Interactions API GA June 2026, `generateContent` legacy, retention 55 d paid / 1 d free, `previous_interaction_id`,
  `background=true` [74]; `function_result` carries `name` + `call_id` [78]; migration notes on 3.8 Flash [6].
- Rate-limit tiers: Tier 1 $250, Tier 2 $2,000, Tier 3 $20,000–100,000+; 10-min windows $10/$50/$200 [3].
- geminicli.com quota page: free API key 250 requests/day, Flash only; AI Pro 1,500 / Ultra 2,000 via Google
  account; "Gemini CLI was replaced by Antigravity CLI on June 18th, 2026" for unpaid/Google One [21].
- API changelog: 3.7 Flash GA 2026-08-13; 3.5 Transcribe (+ `-live`) 2026-08-26; Omni 1.1 Flash GA 2026-08-27
  with `gemini-omni-flash-preview` deprecated 2026-09-30; agentic video 2026-09-01; 3.8 Flash GA 2026-09-02;
  3.8 Live GA 2026-09-15; `antigravity-preview-09-2026` 2026-09-17 (PascalCase, line-range edits; 05-2026
  shutdown 2026-10-05); 2.5 access limits 2026-09-18; 3.8 Flash TTS + Flash-Lite TTS GA 2026-09-22 with voice
  design/replication; Nano Banana 2 Lite GA 2026-06-30; Robotics ER 2 preview 2026-07-30; Gemma 4 2026-04-02 [72].
- Deprecations page: 05-2026 → 2026-10-05; omni-flash-preview → 2026-09-30; `gemini-2.5-flash-image` → 2026-10-02;
  3.1 Pro preview / 3 Flash preview "No shutdown date announced" [73].
- Gemini CLI `--resume`, `--include-directories`, `-p`, `--output-format` on the CLI reference [75].
- Google Finance post dated 2025-11-06; Deep Search "with higher limits for Google AI Pro and AI Ultra
  subscribers" [53].

**Not found / omitted (nothing speculative added):** `gemini-3.5-live-translate-preview` does not appear in the
changelog as fetched; "Apple Silicon + macOS 12+" was confirmed on the getting-started page, not the install page.
Note: the fact-checker characterised #1054 as macOS-relevant; it was filed on Windows 11 — kept, because the
soft-deny it describes is the documented headless policy [26] and #1080 confirms the same lane on macOS arm64.

**Gap-fix pass (2026-09-24, second pass; web-search budget exhausted, WebFetch of primary pages only):**
- RESOLVED — Google AI Plus = **$4.99** (gemini.google/subscriptions [79]; one.google.com renders a blank price [15]).
- RESOLVED — Pro/Ultra OAuth to Gemini CLI is **supported** (1,500 / 2,000 req/day); Free, Google One and AI Plus are
  not ("Tiers not listed above, including Google AI Plus, are not supported") [21]. Canonical reading in §3 for the
  three cross-cut docs; a Gemini "$0 reviewer lane" can only be the API-key free tier or Antigravity free weekly quota.
- CONFIRMED-ABSENT — free-tier RPM/TPM are not published anywhere by Google (rate-limits page defers to the AI Studio
  dashboard [3]); 250 RPD Flash-only [21] remains the only primary number.
- Added §3a data-handling matrix [42][43][82][24][28][67][80], §3b progress-visibility table [3][83][84][85][26][28],
  §3c third-party-serving table [42][24][86][87], §3d tool-churn table [70][72][73][88 = gemini-cli releases via
  github.com/google-gemini/gemini-cli/releases], normalized reliability window in §5 [52][81], Telegram latency rating
  in §5 [50], and scorecard anchors + a chat-latency row in §8.

**Stale / unverified flags left in place (marked "(unverified as of 2026-09-24)"):** Antigravity third-party models
Free-vs-Ultra contradiction; Deep Think enterprise API + Feb-2026 upgrade date; Code Assist individual licence; Batch
"100 concurrent jobs"; managed-agent default egress policy; NotebookLM limits/quota; LMArena snapshot [60]; Deep Research
per-task cost; AA index 59-vs-41 conflict; **Vertex price parity, Vertex ZDR/data-governance and Vertex SLA** (all
docs.cloud.google.com pages fetched as navigation-only or exceeded the fetch size cap — needs a human read); Gemini CLI
OAuth data-use semantics (CLI privacy page defers to Google One terms); Antigravity data-use policy (not stated on any
fetched page); TTFT for Flash-low / Flash-Lite (AA page carries only the high variant).

**Gap-fix pass (2026-09-24, third pass; WebSearch budget exhausted, WebFetch + curl of primary pages only):**
- RESOLVED — AA index: **41 on v4.3.2** adopted (§1, §5); 59/66 was pre-rescale; same-version pairs added (Flash-low 33,
  Flash-Lite 22, Claude Fable 5.1 53) [89][90][91][92].
- RESOLVED — Vertex pricing (Global parity, Non-global +10 %, Priority 1.8×, Flex/Batch 50 %) [96]; Vertex data governance
  (no training; 24-h in-memory cache; abuse logs 90 d standard / 30 d Advanced AI; ZDR via exception form) [93][94];
  Vertex SLA (named services and credit table; Gemini not named) [97]. The pages were read by curl+regex, not by a human —
  numbers are quoted verbatim but a human should still eyeball the SLA's "Covered Service" definition.
- RESOLVED — Antigravity data-use policy: terms train on "Interactions" by default, opt-out in settings (Enable Telemetry
  toggle), human review permitted [95][71]; §3a row rewritten.
- PARTIALLY RESOLVED — Flash-Lite TTFT is measured (8.21 s, reasoning variant) [90]; Flash-low TTFT is "N/A" on AA [92];
  thinking-off variants remain unmeasured → owner probe written out in §3e.8; chat rating downgraded from "suitable" to
  "provisionally suitable, unmeasured".
- OWNER PROBE WRITTEN — Pro/Ultra-via-Gemini-CLI dispute (§3, auth mode 3): three-outcome recipe; canonical reading (a)
  stands until it runs.
- CONFIRMED-ABSENT — concurrency limits for Antigravity CLI / Gemini CLI on subscription auth (five pages, zero
  occurrences of parallel/concurrent/sessions); only Jules publishes concurrency (3/15/60) — §3e.1.
- Added §3e (cross-doc dimensions): credential-lifecycle matrix [99][67][26], visibility sink recommendation [85][26],
  cache-sensitivity for the cost table, prompt-injection/sandbox ranking [98][71][41][42], host budget, reviewer
  independence, chat-latency probe.

**Stale / unverified flags still in place after the third pass:** Antigravity third-party models Free-vs-Ultra
contradiction; Deep Think enterprise API; Code Assist individual licence (privacy-notice page is JS-rendered, not readable
by curl); Batch "100 concurrent jobs"; managed-agent default egress; NotebookLM limits; LMArena snapshot; Deep Research
per-task cost; Gemini CLI OAuth data-use semantics; Antigravity/Gemini CLI refresh-token TTL; Flash-low / Flash-Lite
thinking-off TTFT (probe pending); Provisioned Throughput SLA document (not found).

**Fact-checker overall quality rating: acceptable.**
