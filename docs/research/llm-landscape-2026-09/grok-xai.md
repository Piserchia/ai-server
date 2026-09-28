# xAI Grok — research (as of 2026-09-24)

Scope note: xAI was acquired by SpaceX (2026-02-02) and rebranded to **SpaceXAI** on
2026-07-06; the products keep the **Grok** name and the API/docs still live at
`x.ai` / `docs.x.ai` / `api.x.ai` [45][40]. "xAI" below means SpaceXAI. A
verification pass on 2026-09-24 re-checked first-party docs (see the log at the
end); claims that could not be re-confirmed are marked "unverified as of
2026-09-24" in place. `x.ai/*` pages return HTTP 403 to non-browser fetchers, so
several first-party announcements are cited through secondary coverage. A
2026-09-24 follow-up pass reached `x.ai/news/grok-4-7` directly and the legal
pages (consumer ToS, AUP, enterprise ToS, privacy policy) through Wayback captures
dated 2026-09-21, which closed the ToS-quote and benchmark-discrepancy gaps [79]–[83].
A third pass the same day (WebSearch budget exhausted; direct fetches only) reached
`x.ai/news/grok-bot-more-plans`, `docs.x.ai/developers/faq/security` (self-serve ZDR),
`cursor.com/help/grok-bot/plans`, the OpenClaw and Hermes provider docs and the
OpenRouter endpoints API, closing the Grok Bot plan-inclusion, ZDR-eligibility and
third-party-OAuth gaps [94]–[100], and added the cross-doc dimension rows (§3
"Cross-cut dimensions") the router plan asked for.

## 1. Snapshot

**Company.** SpaceXAI (formerly xAI), wholly owned SpaceX subsidiary since 2026-02-02
(all-stock, xAI valued ~$250B) [45]. Compute: Colossus / Colossus 2 [47]. Products:
Grok chat (grok.com, iOS/Android, inside X), Grok Build (coding-agent CLI), Grok Bot
(cloud "AI teammates"), Grok Imagine (image/video), Grok Voice, Grokipedia, the
developer API at `api.x.ai` [40][4][16][42].

**Current API model lineup** (docs.x.ai pricing + models pages, 2026-09-24) [1][2]:

| Model ID | Context | Modalities | Cutoff | Notes |
|---|---|---|---|---|
| `grok-4.7` | 500k | text in, text out (image input unverified as of 2026-09-24: docs.x.ai/developers/models lists grok-4.7 as Text and gives image-input specs without naming which text models accept images) | May 2026 | flagship, launched 2026-09-21; reasoning effort low/medium/high (default)/xhigh; encrypted reasoning returned via Responses API [1][2][15][22] |
| `grok-4.7` "Fast" tier | 500k | same | May 2026 | same weights on faster infra at **2x** token price; listed on the pricing page as "Grok 4.7 Fast pricing (Cursor and Grok Build only)" — no API model ID, not selectable via api.x.ai; $4.00/$1.00/$12.00 (<200k) and $6.00/$1.50/$18.00 (≥200k, i.e. 1.5x not 2x at long context) [1] |
| `grok-4.6` | 500k | text | not stated | previous flagship, 2026-08-12 [15][40] |
| `grok-4.5` | 500k | text | not stated | 2026-07-08, co-developed with Cursor [40] |
| `grok-4.3` | 1M | text | not stated | cheap tier, batch-eligible [1] |
| `grok-4.20-0309-reasoning` / `-non-reasoning` / `grok-4.20-multi-agent-0309` | 1M | text | not stated | Feb 2026 family; logprobs unsupported on 4.20+ [1][2] |
| `grok-build-0.1` | 256k | text | not stated | coding model behind Grok Build; AA Intelligence Index 27, 43 tok/s; AA marks it deprecated in favour of 4.5+ [1][20] |
| `grok-imagine-image-2.0` / `-image` / `-image-quality` (retires 2026-11-02) | — | text→image | — | $0.04 / $0.02 / $0.05 per image [1][15] |
| `grok-imagine-video` / `grok-imagine-video-1.5` | — | text/image/ref→video | — | $0.05 / $0.08 per second [1] |
| `grok-voice-think-fast-2.0` + STT/TTS | — | audio | — | $0.08/min speech-to-speech [1] |

`grok-code-fast-1` (Aug 2025, $0.20/$1.50, 256k) [63] no longer appears on the
pricing/models pages; treat as superseded by `grok-build-0.1` (whether it still
serves is unverified as of 2026-09-24). Grok 4 / 4.1 Fast / Grok 3 are absent from the current price list [1].

**Release cadence.** Roughly one frontier point-release every 4–8 weeks in 2026:
4.20 (Feb — date unverified as of 2026-09-24) → 4.3 (Apr — date unverified as of
2026-09-24; neither appears with a date in the Wikipedia Grok/xAI articles) → 4.5
(Jul 8) → 4.6 (Aug 12) → 4.7 (Sep 21) [40][15]. Musk's public roadmap (May 2026) had
seven models training on Colossus 2 including 6T and 10T-parameter "Grok 5"
variants; as of Sep 2026 Grok 5 is unreleased with no date, and Musk now slots
4.8/4.9 before it [47][48].

**Imminent churn (plan for model-ID changes within weeks).** On 2026-09-14 Musk
said "Grok 4.8, which is a 2.5T model trained with our new C++ software stack, will
finish training this week and start RL" (CGTN headline 2026-09-14; Analytics India
Mag 2026-09-15 on the human-written C++ pre-training stack); on 2026-09-22 he
called 4.8 training "fully completed" (36kr) [74]. The claim that Grok 4.9 will be
"Astra/Fable class" before Grok 5 was not found in the sources reachable this
session (unverified as of 2026-09-24). Practical consequence: expect `grok-4.8` to
appear on the price list in Q4 2026, likely with the same $2/$6 tag; treat any
model-ID string in our config as a bump-deliberately setting (§7 gotcha 8).

**Positioning.** Aggressive price (Grok 4.7 at $2/$6 per 1M is a third of Western
frontier list prices) plus real-time X data and web search as first-class API tools,
fast shipping, weak reliability and safety track record. Independent evals place
Grok 4.7 mid-pack on general intelligence and well behind Claude/GPT-6 on agentic
terminal work, but competitive on "knowledge-work" agent evals and on cost per task
[18][21][22].

## 2. Interfaces & surfaces

- **Consumer app:** grok.com (web), iOS + Android standalone apps, and Grok embedded
  in the X app/website [32][40]. No official macOS/Windows *chat* desktop app found;
  the Grok **Bot** app ships for macOS/Windows/Linux/iOS/iPadOS/Android [16].
  Free tier exists (~10 prompts / 2 h reported by [26], but that page is "Last
  updated 2026-06-25" and still lists Grok 4 / 4.3 as the paid models — stale;
  unverified as of 2026-09-24; xAI publishes no numbers) [26][32].
- **Voice:** in-app voice mode on all paid tiers ("longer voice conversations" on
  SuperGrok+) [25]; Voice API (speech-to-speech, STT, TTS) [1].
- **Browser/OS integrations:** X platform integration (mention @grok on posts) [40].
  Tesla: in-car Grok chatbot since software 2025.26 (2025-07-12), originally no
  vehicle control [40]; 2026 (headline-level only, via Google News index —
  unverified as of 2026-09-24, article bodies not fetched): Spring 2026 update added
  "Hey Grok" wake word (Not a Tesla App, 2026-04-13); Summer 2026 update added Grok
  phone calls and wider rollout to Europe/India/Thailand (Electrek 2026-07-21,
  teslahubs 2026-07-22); Tesla said Grok will take FSD driving commands (BASENOR
  2026-07-07); "Grok can now control more than 100 vehicle functions hands-free"
  (driveteslacanada 2026-08-31, site 403s fetchers); "Tesla launches Grok Bot in
  cars for voice-run errands and email" (Dataconomy 2026-09-23) [75]. Not a server
  surface for us; listed for vendor-footprint context only.
- **Messaging integrations:** *Telegram* — the May-2025 $300M deal **never
  materialized**; Telegram built its own "Cocoon" AI instead (summaries Jan 2026,
  text editor Mar 2026) [43]. A verified `@GrokAI` Telegram bot is described by a
  how-to site (Apr 2026) [44]; Wikipedia's Telegram article contradicts the
  "official partnership" framing, so treat `@GrokAI` as unofficial (unverified as
  of 2026-09-24). Slack/WhatsApp/Discord: a 2026 Google News scan for "Grok Slack /
  WhatsApp / Discord integration" returned no first-party or press coverage of an
  official Grok app on any of the three (the index surfaced X, Tesla, Microsoft
  Copilot, GitHub Copilot, OpenClaw, Hermes Agent and CarPlay instead) — treat as
  **no official messaging integrations beyond X** as of 2026-09-24 [76]. For our
  Telegram front door Grok is therefore only ever a routed backend.
- **CLI / agentic coding — Grok Build** (`grok`): terminal TUI + headless mode
  (`grok -p "<prompt>"`), `--output-format streaming-json`, `-m <model>`, MCP
  servers (`grok inspect`), Agent Client Protocol for editors (unverified as of
  2026-09-24), parallel (official subagents guide states no maximum; the "8" figure
  comes from a 2026-05-26 review of the grok-build-0.1 era; worktree isolation is
  opt-in per subagent via `isolation: worktree`, or `--worktree [NAME]` for the
  whole session) sub-agents, plan-first mode [73]; installed via
  `curl -fsSL https://x.ai/cli/install.sh | bash`; Apache-2.0 source on GitHub —
  the README says only that it is "synced periodically from the SpaceXAI monorepo";
  the 2026-07-15 publish date and "issues/PRs disabled — public snapshot" status
  are unverified as of 2026-09-24 (x.ai/build/changelog 403) [4][5][36][60]. Grok
  Build runs on Grok 4.7 as of 2026-09-21 [18][61]. Also "Build Mode" inside chat
  (no-install app builder; "SuperGrok Heavy only, 2026-07-28" is unverified as of
  2026-09-24 — x.ai/news 403) [35].
- **Computer-use / browser agent — Grok Bot** (beta 2026-08-11 — date unverified as
  of 2026-09-24, confirmed only via aibuilderclub [33]; docs.x.ai gives no date and
  no public plans/billing page was reachable): persistent named agents on a
  per-account cloud computer in **Cursor's cloud** (browser + filesystem + terminal;
  "all of your Bots use the same cloud computer"), access via any paid Cursor plan or
  a linked SuperGrok / Plus / Heavy subscription — **resolved 2026-09-24**: xAI's own
  announcement (2026-08-26) says "Grok Bot is now included with all SuperGrok, Cursor
  Pro, and Cursor Teams plans" and that it "comes with its own usage, separate from
  your Grok and Cursor plans" [94]; Cursor's plans page lists SuperGrok, SuperGrok
  Plus, SuperGrok Heavy and X Premium+ as linkable and **SuperGrok Lite, SuperGrok
  Team and SuperGrok Enterprise as not supported** [95]; Engadget's Plus/Heavy-only
  list [34] predates or omits the 08-26 widening. Usage resets weekly [16]; with both
  a Cursor and a SuperGrok plan "Grok Bot uses whichever has more usage" [96].
  Concurrency: "Each Bot gets its own screen on the shared computer" and "One Bot can
  run one computer-use task on its screen at a time"; no cap on the number of Bots is
  published, and "Do not use separate Bots as a security boundary" [96][97]. Connectors
  "where available and computer use for everything else", drafts-before-send
  approvals, learned routines re-runnable on a schedule. Controlled only via the
  desktop/mobile apps; **no CLI, API, or webhook trigger documented** [16][34].
- **Scheduled tasks — Grok Automations** (`grok.com/tasks`, formerly "Tasks"):
  scheduled prompts (daily/weekdays/weekly/custom) and email-triggered runs; results
  delivered by email, in-app notification, and run history; paid tiers only; no
  third-party tool integrations and **no API** [46].
- **Memory / projects:** memory on all tiers (basic on Free); Projects & Tasks on
  SuperGrok and up; "Companions" on SuperGrok+; "Heavy" multi-agent mode on Heavy
  only (per aggregator table, unverified against x.ai) [31].
- **API + SDKs:** REST base `https://api.x.ai/v1`; native Python `xai-sdk` (gRPC,
  Python ≥3.10); JS via Vercel AI SDK `@ai-sdk/xai`; OpenAI Python/JS SDKs work with
  `base_url="https://api.x.ai/v1"` [7][8][9]. **Responses API** (`/v1/responses`,
  stateful via `previous_response_id`, 30-day storage, `store:false` to disable,
  encrypted reasoning passthrough) is the primary surface; Chat Completions still
  referenced [9]. **Anthropic-compatible `/v1/messages`: not offered natively**
  (Cloudflare AI Gateway provides that shim) [62]. Release-notes items May–Sep 2026
  worth knowing [15]: Context Compaction API and WebSocket Responses API (May);
  `service_tier: "priority"` per-request priority processing at 2x, and Files API
  **public URLs** (permanent, unauthenticated, revocable) (Jun); `vad_threshold` for
  STT, `grok-voice-think-fast-2.0`, and Grok 4.5 available in the EU console (Jul);
  Grok 4.6 (Aug); Grok 4.7 and `grok-voice-transcribe-2.0` (default remains
  `grok-voice-transcribe-1.0`) (Sep). Reasoning effort: Grok 4.5 accepts
  low/medium/high only — `xhigh` is a 4.6/4.7 addition (per the fact-check pass
  against [15]; not re-confirmed in this pass).
- **Tool use:** custom function calling (parallel by default, whole-chunk streaming
  of calls) [14]; server-side tools `web_search` (allowed/excluded domains ≤5, image
  understanding), `x_search` (allowed/excluded handles ≤20, ISO date range, image and
  video understanding of posts; returns citations), `code_interpreter` (code
  execution), `image_generation`, `collections_search`; file attachments are billed
  as a tool call on the pricing page although the tools overview lists only the
  five types above [77][12][13][1].
- **Structured outputs:** `response_format: {type: "json_schema"}` with Pydantic
  support; JSON-Schema subset (no circular refs; guaranteed ranges: string
  min/maxLength ≤2048, minItems/maxItems ≤256, min/maxProperties ≤64 — beyond
  those, conformance is best-effort, as are `not`, `if/then/else`, multi-schema
  `allOf` and non-standard `format`; **400 errors** for empty `enum`/`anyOf`,
  properties given as boolean `true`/`false` schemas, `minContains`/`maxContains`,
  and array-form `items` (use `prefixItems`); `additionalProperties` defaults to
  false) [10].
- **Batch API:** `/v1/batches`, JSONL, ≤200 MB / 50k requests per file, best-effort
  24 h; 20% discount only on `grok-4.3` and the 4.20 family (none on 4.5/4.6/4.7)
  [11][1].
- **MCP:** supported in the Grok Build CLI [4]. Remote-MCP-as-API-tool: **not
  documented** on the function-calling or tools pages [14].
- **IDE plugins:** Cursor (a wholly owned SpaceX subsidiary since 2026-08-14 — $60B
  deal announced 2026-04-21; co-develops Grok 4.5+; Grok Bot originated at Cursor as
  "Sand", runs in Cursor's cloud and is bundled with paid Cursor plans) [72][16],
  GitHub Copilot, Amazon Bedrock listed by Wikipedia [40]; docs.x.ai community page
  lists only LiteLLM and Vercel AI SDK [17].

## 3. Headless / server automation fit

- **API key (recommended):** `XAI_API_KEY` from console.x.ai; prepaid credits
  ("no minimum" is unverified as of 2026-09-24 — the quickstart only says "load it
  with credits"); **no free credits** (the $150/mo free tier ended May 2025) [8][55].
  Rate-limit tiers are by cumulative spend since 2026-01-01: Tier 0 $0 → Tier 1 $50
  → Tier 2 $250 → Tier 3 $1,000 → Tier 4 $5,000 → Enterprise; never downgrade.
  `grok-4.7/4.6/4.5`: 150–500 RPS, 50–100M TPM; `grok-4.3`, 4.20, `grok-build-0.1`:
  37–208 RPS, 10–85M TPM; 429 on excess [3]. Even Tier 0 is far above a single-tenant
  server's needs.
- **Grok Build under a subscription:** `grok login --device-auth` prints a URL + code
  (works on a headless Mac Mini); tokens cached in `~/.grok/auth.json` (0600),
  auto-refreshed ~5 min before expiry, 30-day default lifetime; precedence is
  per-model config keys → session token → `XAI_API_KEY` [6]. So subscription-metered
  headless runs are *technically* supported by the tool. Paid Build usage draws from
  one **undisclosed weekly pool** shared with Chat/Imagine/Voice, resets on a
  per-account schedule, pauses when empty unless you buy Extra Usage Credits (from
  $5, expire after 1 year) or enable Auto Top Up [25][29][30].
- **Terms (verified 2026-09-24 via Wayback captures of 2026-09-21):** the
  **Consumer ToS (Last Updated 2026-09-11)** [80] contains **no** "more request
  messages than a human can reasonably produce" clause — that quote, carried in
  earlier drafts from a search-index snippet, does not appear in the current text and
  is withdrawn. What the consumer ToS does say: "You may not share your account
  credentials or make your account available to anyone else"; "At our sole
  discretion, we may implement rate limitations to accommodate system resources or
  usage needs"; use must comply with the AUP, which is incorporated by reference;
  and "Agentic Actions" (web browsing, code execution, sending communications,
  modifying files, tool invocation, "interactions with third-party services,
  including financial institutions") are the user's responsibility. The **AUP
  (Effective 2026-08-14)** [81] prohibits, verbatim: "Modifying, copying,
  translating, leasing, selling, reselling, distributing, distilling, manipulating,
  **using bots to access**, reverse engineer, decompile, disassemble or otherwise
  seek to obtain the source code of our Service"; "**Scraping, harvesting or
  reselling any Input or Output**, or distilling model data or Outputs"; and
  "Making high-stakes automated decisions that affect a person's safety, legal or
  material rights, or well-being (such as making financial credit ... decisions
  about or for them)" — note the last one targets decisions *about people*, not
  market trades. The Grok Build auth guide explicitly documents device-code login
  "for headless environments" and API keys for CI [6]. Reading: the surviving
  policy risk for subscription-headless use is the AUP's "using bots to access"
  phrase (listed among reverse-engineering acts, so arguably aimed at scraping the
  service rather than at driving the vendor's own CLI) plus the opaque weekly pool;
  CLI-driven, human-paced batches on your own seat are within the documented
  product; a 24/7 job farm on a $30 seat is not. Nothing bans programmatic use of
  the *API* for any purpose (AUP is content-focused) [81].
- **Third-party serving (who may consume the output).** Consumer ToS/AUP: the seat
  is single-person (no credential sharing, no "make your account available to
  anyone else") and the AUP bars "reselling any Input or Output"; nothing grants a
  right to expose consumer-tier output to other users, so a pickem-league page or a
  shared project site fed by a SuperGrok seat is outside the documented use. The
  **Enterprise ToS (Last Updated 2026-08-14)** [82], which governs the API, does the
  opposite: Customer may "develop integrations between the Services and Customer's
  own products or services (each, a 'Bundled Service')" and "distribute or otherwise
  make the Bundled Service available to Customer's end users", provided Customer
  keeps its own ToS/AUP with End Users and stays liable for them; Customer "owns all
  right, title, and interest in the Output in perpetuity"; the only output
  restriction is no training of other models and no misrepresenting Output as
  human-generated. **Rule for us:** anything a second person can see (dashboards,
  shared sites, Telegram groups) goes through the API key, never a seat.
- **Data-handling matrix (Grok lanes)** [82][83][9][25][69][71]:

  | Lane / auth | Training on inputs | Retention | Residency | ZDR |
  |---|---|---|---|---|
  | API key (`api.x.ai`), enterprise ToS | "SpaceXAI will not use any User Content to train any foundation models ... subject to disclosures to Customer and Customer-controlled user settings" | "automatically and permanently deleted no later than 30 days after the end of the interaction or session"; Responses API objects 30 days, `store:false` opts out | global endpoint routes across regions; `us.api.x.ai` (+10%) guarantees US inference/moderation/storage for 4.7/4.6 only, excluding files, collections and server-side tools [84] | "ZDR-Enabled API": content "will exist in SpaceXAI systems only transiently"; **self-serve**: "Team admins can enable or disable ZDR from the Console" (Team Settings → Enable, after deleting existing Files/Collections); disables per-key request logging, stateful Responses API, Files, Collections, **Batch API**, deferred completions, stored image/video outputs, voice history; "If you do not see the ZDR option ... self-serve ZDR may not be enabled for your environment yet" or the team is on a negotiated enterprise agreement [98] |
  | Grok Build on API key | as API | as API; local sessions under `~/.grok/sessions/`; SpaceXAI-side trace upload unless `[telemetry] trace_upload=false` | as API | team-level `features.zdr_access_enabled` |
  | Grok Build / chat on consumer seat (SuperGrok*) | opt-in/out toggle "when logged into our Service, you can select whether or not you want us to use your User Content to improve our products and services and train our models"; `/privacy` in Grok Build controls coding-data sharing; unauthenticated use grants "full rights" for training | deletion requests and Private Chat purged "up to 30 days"; otherwise retained "where we have an ongoing legitimate business need" | not stated (privacy policy silent on location) | none (single seat) |
  | SuperGrok Business seat | "excluded from model training by default" [25] | as consumer | not stated | not stated |
  | Grok Bot (Cursor cloud) | governed by consumer ToS + Cursor's cloud; not separately stated | not stated | Cursor's cloud, region not stated | none |

  The consumer privacy policy (Effective 2026-08-24) states it "does not apply to
  data that we process on behalf of customers of our business offerings, such as
  the SpaceXAI API" [83], so API traffic is governed solely by the enterprise ToS
  row. **Paper-trading lab consequence:** proprietary theses may go to the API-key
  lane (no-training + 30-day delete, `store:false`), never to a consumer seat.
- **Progress visibility / quota introspection.** API: no usage or credits
  endpoint is documented; rate-limit tiers are visible only in the console, 429 is
  the signal [3]; per-request `usage` (incl. `server_side_tool_usage_details`) is
  the only programmatic meter [13]. Subscription pool: consumer FAQ says "Go to
  Settings → Usage ... A progress bar showing your current usage percentage. A
  percentage breakdown by product (API, Build, Chat, Imagine, Voice)" — web/mobile
  UI only [85]. Grok Build: `/usage` (alias `/cost`) opens a modal with "the
  account allowance plus that session's context and token totals" — TUI only, no
  JSON, no CLI flag [86]; the **status line** `command` hook pipes a JSON payload
  (`context_window.*`, `cost.total_cost_usd`, `cost.total_duration_ms`,
  session token totals) to a script on every refresh — per-session cost yes,
  remaining pool **no** [87]; `grok dashboard` is TUI-only with no HTTP/JSON
  surface [88]; headless `--output-format json` returns `usage`, `modelUsage`,
  `total_cost_usd` [70]; OTEL export (below) carries token/latency metrics but not
  the account allowance [71]. Net: **remaining weekly pool is not machine-readable
  on any Grok surface** — one more reason the metered API (where "remaining" is
  just prepaid balance in the console) is the automation lane.
- **Sandboxing:** Grok Build ships an OS-level sandbox (Landlock on Linux 5.13+,
  Seatbelt on macOS) that is OFF by default; enable with `--sandbox <profile>`,
  `GROK_SANDBOX`, or `[sandbox] profile` — built-in profiles
  `off`/`workspace`/`devbox`/`read-only`/`strict`, custom profiles in
  `~/.grok/sandbox.toml` with `restrict_network`, `read_only`, `read_write`, `deny`
  globs (e.g. `**/.env`, `**/*.pem`) [68]. Caveats from the same guide: the sandbox
  is irreversible once applied in a session; network blocking is enforced on Linux
  only (seccomp) and is a **no-op on macOS**, so on the Mac Mini the sandbox limits
  filesystem reach but not egress; Linux deny-globs expand at launch, so files created
  later are not covered [68]. Independently of the sandbox, Grok Build (July 2026)
  uploaded whole repos to a GCS bucket — see §5. Mitigate with `~/.grok/config.toml`
  `[telemetry] trace_upload = false` and env `GROK_TELEMETRY_ENABLED=false`,
  `GROK_TELEMETRY_TRACE_UPLOAD=0` (the gist uses 0/1; the official config reference
  documents `[telemetry] trace_upload` and both `GROK_TELEMETRY_*` env vars, but
  `[harness] disable_codebase_upload` is NOT in the official config reference — it
  was a server-side kill-switch reported by The Register/gist, so do not rely on it
  locally) [37][69]. Grok Bot runs on a per-account cloud computer in Cursor's cloud
  (docs.x.ai/grok-bot/overview: bots "run in Cursor's cloud"), not yours [16].
- **Headless automation surface (Grok Build, beyond `-p`)** [70]: `--yolo` or
  `--permission-mode bypassPermissions` (auto-approve tools); `--allow <RULE>` /
  `--deny <RULE>` glob permission rules (repeatable); `--tools <list>` allowlist and
  `--disallowed-tools <list>` denylist of built-in tools (headless only; MCP
  meta-tools stay available unless denied); `--disable-web-search`; `--max-turns
  <N>` (headless only); `--effort none|minimal|low|medium|high|xhigh|max`;
  `--worktree [NAME]` + `--ref <REF>` to run in a fresh git worktree; `--agents
  <JSON>` inline sub-agent definitions, `--agent <name|file>`, `--no-subagents`,
  `--no-plan`; `--rules <TEXT>` system-prompt rules; `--cwd`; `-s <uuid>` to pin a
  session id; `-r`/`-c`/`--fork-session` (above). Headless does **not** read piped
  stdin — pass content by command substitution or `--prompt-file <path>` (also
  `--prompt-json` for content blocks). The `json` output carries `text`,
  `stopReason`, `sessionId`, `requestId`, `num_turns`, `usage` (input / cache read
  / cache creation / output / reasoning), `modelUsage` and `total_cost_usd` — the
  natural payload for our audit log.
- **Observability (OTEL export):** Grok Build has a customer-side OpenTelemetry
  stream that is **double opt-in** (master switch `GROK_EXTERNAL_OTEL=1` *and* an
  exporter selection such as `OTEL_METRICS_EXPORTER=otlp` / `OTEL_LOGS_EXPORTER=otlp`
  with `OTEL_EXPORTER_OTLP_ENDPOINT`/`_HEADERS`; config-file equivalents under
  `[telemetry] otel_enabled`, `otel_endpoint`, `otel_log_*`). It is **content-free by
  default** (no prompts, prose, code, tool args or bash commands; file paths reduced
  to extensions; MCP/skill names collapsed to categories) with explicit gates
  `OTEL_LOG_USER_PROMPTS`, `OTEL_LOG_ASSISTANT_RESPONSES`, `OTEL_LOG_TOOL_DETAILS`,
  `OTEL_LOG_TOOL_CONTENT`. Metrics (meter `ai.xai.grok_code`): sessions, tokens by
  type/model, turns, TTFT/TTFM latency, tool decisions, errors; events: session
  lifecycle, turn completion, API requests/errors, tool results, permission changes.
  It is structurally separate from SpaceXAI-side `trace_upload`, and an org-level
  **zero-data-retention (ZDR)** setting turns off SpaceXAI-side retention without
  muting the customer OTEL stream [71]. This is the piece that satisfies the owner's
  "watch their progress" requirement if Grok Build is ever used headless: point it at
  the server's collector and never enable the content gates.
- **Structured events:** Grok Build `--output-format
  plain|json|streaming-json|streaming-messages-json` (`json` returns `text`,
  `stopReason`, `sessionId`, `requestId`, `num_turns`, `usage`, `modelUsage`,
  `total_cost_usd` — ideal for audit-log capture); headless does NOT read piped
  stdin, use `--prompt-file` [4][6][70]; API
  streaming via Responses API / OpenAI SDK; structured outputs via json_schema [9][10].
- **Session resume:** API — `previous_response_id` (30-day retention) [9]; Grok
  Build — supported: `grok --resume <session-id-or-title>` (or bare `grok --resume`
  for the most recent session in the cwd); in headless mode `grok -p "..." -r
  <id-or-title>` resumes, `-c`/`--continue` continues the latest session,
  `--fork-session` forks; sessions persist under `~/.grok/sessions/` (override with
  `GROK_HOME`); capture the id via `grok -p "..." --output-format json | jq -r
  '.sessionId'` [67].
- **Privacy:** Responses API stores conversations 30 days unless `store:false` [9];
  SuperGrok Business is "excluded from model training by default" (implying consumer
  tiers are not) [25]. An explicit **zero-data-retention (ZDR)** team/org option is
  referenced in the Grok Build monitoring and config docs (`features.zdr_access_enabled`,
  `tools.disable_zdr_incompatible_tools`, `tools.zdr_video_output_s3`; "ZDR turns
  off SpaceXAI-side retention") — it disables some tools and is a team-level
  setting, so it is not available on a single consumer seat [69][71]. **Resolved
  2026-09-24:** the developers security FAQ documents ZDR as a self-serve console
  toggle for team admins (every console account is a "team", so a single-owner
  self-serve org qualifies unless the option is not yet enabled "for your
  environment"), with the disabled-feature list above; enterprise ZDR for Grok
  Build "is enforced at the team level" and needs user-supplied S3 storage for
  video tools [98][99]. Trade-off for us: ZDR removes the Batch API (the only
  discount on 4.3/4.20) and `previous_response_id` resume, so it is an
  either/or with cheap batch classification.

### Cross-cut dimensions (added 2026-09-24 for the router plan)

- **Subscription OAuth via third-party agents (OpenClaw / Hermes) — confirmed
  as shipped, unsanctioned by xAI.** OpenClaw ships a bundled `xai` provider
  plugin whose "recommended path is Grok OAuth with an eligible SuperGrok or X
  Premium subscription" (`openclaw models auth login --provider xai --method
  oauth`, device-code flow, no localhost callback, "Prefer OAuth login for
  automatic token refresh", default model `xai/grok-4.7`); it states plainly that
  "xAI decides which accounts can receive OAuth API tokens" and documents neither
  eligible tiers, storage path, TTL nor rate limits [100]. Hermes Agent offers
  "xAI Grok OAuth (SuperGrok / Premium+)" from `hermes model`, "uses your
  subscription quota instead of API spend", persists credentials in
  `~/.hermes/auth.json` (API key alternative: `XAI_API_KEY` in `~/.hermes/.env`),
  and warns that "HTTP 403 after a successful login ... is a tier/entitlement
  restriction on xAI's side, not a stale token — the workaround is switching to
  an `XAI_API_KEY`"; its model list is stale (`grok-4-fast-reasoning`) [101]. No
  xAI page acknowledges either client; the consumer ToS/AUP analysis above
  applies unchanged (single seat, "using bots to access", no serving to third
  parties). Status: **confirmed to exist, unsupported by the vendor, entitlement
  gated per account, no published concurrency** — not a lane for the scheduler.
- **Concurrency per lane (parallel headless sessions).** API key: governed only
  by RPS/TPM per spend tier (Tier 0 already 150+ RPS on 4.7), plus explicit
  *concurrent-session* caps only for voice (T0 10 → T4 200) [3]; no per-key
  session cap for text, so fan-out is effectively unlimited for our scale.
  Grok Build on API key: no documented cap on parallel `grok -p` processes;
  sub-agents "no maximum" [73]; scheduler "Maximum 50 scheduled tasks can be
  active at once" [102]. Grok Build / OpenClaw / Hermes on a SuperGrok seat:
  **no published concurrency figure at all** (unverified as of 2026-09-24) —
  only the shared weekly pool and the per-account 403 entitlement gate. Grok
  Bot: one computer-use task per Bot, Bots parallel, count uncapped in docs
  [96]. For the fan-out design treat Grok as: API lane = unbounded (budget-
  bounded), seat lanes = assume 1 until measured.
- **Credential lifecycle on a headless box (Grok lanes).**

  | Lane | Store | TTL | Silent refresh w/o browser | What fails first |
  |---|---|---|---|---|
  | API key | env `XAI_API_KEY` (our secret store) | none (revoke in console) | n/a | 401 on revoke; 429 on tier; prepaid balance → hard stop unless Auto Top Up (min $5, monthly cap) [103] |
  | Grok Build session (`grok login` / `--device-auth`) | `~/.grok/auth.json`, 0600, plaintext (no Keychain) | server `expires_in`, else **30-day** fallback; `GROK_AUTH_TOKEN_TTL` override | yes: re-auth ~5 min before expiry (`GROK_AUTH_EARLY_INVALIDATION_SECS`=300) and on 401; OIDC `refresh_token` refreshes "without re-opening the browser" | if refresh fails headless "Grok stops treating the stored credential as usable and starts the sign-in flow" → the job hangs on an interactive prompt, not a clean error; MCP tokens separately in `~/.grok/mcp_credentials.json`; "Do not copy auth.json ... into shared directories" [6] |
  | OpenClaw OAuth | path undocumented | undocumented | "automatic token refresh" claimed | entitlement 403 (per Hermes note) [100][101] |
  | Hermes OAuth | `~/.hermes/auth.json` (plaintext) | undocumented | undocumented | 403 entitlement → fall back to API key [101] |

  Expiry alarm for us: none is emitted by any Grok surface; wrap headless runs
  in a timeout and treat a stalled process with no JSON output as "re-login
  required".
- **Prompt-injection / sandbox posture for untrusted inputs.** Grok Build:
  no prompt-injection guidance in the permissions guide; defence is layered
  permission modes (`default` auto-runs read-only tools **including web
  search**; `dontAsk` + narrow `allow` rules is the only default-deny; `--yolo`
  keeps `deny` rules and hooks) plus the OS sandbox that is off by default and
  does not block network on macOS [68][104]. Grok Bot: explicitly marks
  "content a Bot reads from the outside world, like web pages, plugin results,
  and command output" as untrusted, adds Auto Review, per-action approvals for
  sends/purchases/deletes/permission changes, user isolation, and (Enterprise
  only) egress allowlists — but all Bots share one computer and credentials
  [97][105]. API: no injection controls beyond the $0.05 violation fee [1].
  **Ranking within Grok lanes:** Grok Bot (strongest, but cloud-hosted and not
  scriptable) > Grok Build with `dontAsk` + `--sandbox strict` + deny-globs
  (medium; network still open on macOS) > Grok Build `--yolo` default (weak) ≈
  raw API tool loop (whatever our runner enforces). For Telegram text and fetched
  pages the API lane is therefore only as safe as our own guard layer.
- **Host resource budget.** Grok Build is a single Rust binary (no Node
  runtime) [5]; RAM/CPU are **undocumented** on docs.x.ai/build/overview and in
  the README (unverified as of 2026-09-24) — expect a few hundred MB per live
  session from the TUI/session store, measure before scheduling parallel runs.
  OpenClaw requires Node 24.16+/26.1+ and publishes no RAM figure [106]; Hermes
  publishes none. The API lane costs nothing beyond the Python client.
- **Progress-visibility sink.** The only machine-readable Grok progress feed is
  Grok Build's OTLP export (metrics + content-free events) [71] and per-request
  `usage` on the API [13]. It needs an OTLP receiver on the Mac (an OTEL
  Collector or a Prometheus-compatible OTLP endpoint) and yields **no**
  remaining-pool number; "remaining budget" for the API lane must be inferred
  server-side as prepaid balance minus summed `total_cost_usd` /
  `usage`-priced calls from our audit log. Proposed common event fields Grok can
  populate: `lane=grok-api|grok-build`, `model`, `session_id`, `request_id`,
  `tokens{in,cached,out,reasoning}`, `cost_usd`, `stop_reason`, `latency_ms` —
  all present in the headless JSON envelope [70].
- **Empirical calibration.** The §4 table uses the synthetic 150k-in/15k-out
  job at 0% cache. Grok's cached-input rate is 25% of list ($0.50 vs $2.00 on
  4.7), so at 70% prefix cache-hit the per-job 4.7 cost falls from $0.39 to
  ~$0.245 (input $0.30 → $0.09 + $0.0525 cached; output unchanged $0.09), i.e.
  the subscription-vs-metered crossover moves from ~75 to ~120 jobs/month. This
  doc did not read `volumes/audit_log` (out of scope for this pass); the verdict
  should be re-run against measured jobs/month, tokens/job and cache-hit share.
  The owner's Max tier and existing seats do not affect the Grok row (no seat is
  recommended).
- **Reviewer independence.** Grok is *not* a fully independent lineage for
  cross-vendor adversarial review of Claude or GPT output: press reported in
  2026 that xAI trained its coding models on Claude outputs "for months before
  getting cut off" (The Decoder / WinBuzzer / opentools, 2026-06-06/07, incl. a
  post-January-cutoff workaround) and that Musk "seemingly admits xAI has used
  OpenAI's models to train its own" (WIRED 2026-04-30) — headline-level via the
  Google News index, bodies not fetched (unverified as of 2026-09-24) [107].
  Weight a Grok second opinion on *coding* as partially correlated with Claude;
  its X-data grounding and different RL stack still make it useful for
  factual/sentiment disagreement.
- **Measured chat-surface latency.** Artificial Analysis: Grok 4.7 (xhigh)
  TTFT 0.92 s, 40.4 tok/s [91]; **Grok 4.3 (high) TTFT 21.24 s**, 123.2 tok/s
  [108] — i.e. the cheap tier at high effort is unusable for a single-message
  Telegram reply; use `reasoning_effort: low` (TTFT not independently published,
  unverified as of 2026-09-24) or stream.

## 4. Cost

**Consumer plans** (x.ai pricing page via [25], 2026-09-15; cross-checked [26][27]).
Price-verification status as of 2026-09-24: Lite $10 confirmed by launch press
(Economic Times/Moneycontrol 2026-03-25/26) [109]; SuperGrok $30 and Heavy $300
confirmed by three independent aggregators [25][26][27]; **Plus $100 rests on
[25] alone** (which states it checked grok.com/plans and x.ai/pricing on
2026-09-15) — no press or first-party confirmation reachable (x.ai 403,
grok.com/plans JS-rendered); annual figures likewise [25]-only.

| Plan | $/mo (annual) | Includes | Caps |
|---|---|---|---|
| Free | $0 | Grok 4.6 chat (unverified as of 2026-09-24 — [25] is dated 2026-09-15, six days before 4.7 launched; x.ai 403), image gen, Grok Build, voice, connectors, limited search | ~10 prompts/2 h (community-reported via a stale 2026-06-25 page; unverified as of 2026-09-24) [26] |
| SuperGrok Lite | $10 ($100/yr) | Expert mode, 2x longer chats, image/video trials; **no Grok Bot** [95] | weekly pool, undisclosed |
| SuperGrok | $30 ($300/yr) | + 5x longer chats, **Grok Bot (resolved: included since 2026-08-26 per x.ai [94]; Cursor's plans page confirms SuperGrok/Plus/Heavy/X Premium+ link, Lite does not [95]; Engadget's Plus/Heavy-only list [34] is superseded)**, 720p video ≤30 s, Automations, Projects | weekly pool; Grok Bot has its own separate pool [94] |
| SuperGrok Plus | $100 ($1,000/yr) | + 1080p video, "significantly higher usage" across Chat/Imagine/Voice/Build, priority | larger weekly pool |
| SuperGrok Heavy | $300 ($3,000/yr) | highest usage, larger agent teams, Heavy multi-agent, Build Mode, X Premium+ included, dedicated support | largest pool; "$99 intro promo" comes from a 2026-05-26 review that priced Heavy at $299 — unverified as of 2026-09-24 [28][36] |
| SuperGrok Business | $30/seat | SuperGrok + shared billing, analytics, no-training default | — |
| X Premium | $8 | higher Grok limits inside X only | — |
| X Premium+ | $40 ($395/yr) | SuperGrok-equivalent + Grok Bot | — |

Extra Usage Credits from $5 (expire 1 year); Auto Top Up with monthly cap [25]. Grok
Bot on-demand overage billed "at model and token cost" with **no Bot-specific spend
cap yet** [33].

**API prices** ($ per 1M tokens; <200k-token prompts / ≥200k) [1]:

| Model | Input | Cached | Output | Batch |
|---|---|---|---|---|
| grok-4.7 | 2.00 / 4.00 | 0.50 / 1.00 | 6.00 / 12.00 | none |
| grok-4.6 | 2.00 / 4.00 | 0.50 / 1.00 | 6.00 / 12.00 | none |
| grok-4.5 | 2.00 / 4.00 | 0.30 / 0.60 | 6.00 / 12.00 | none |
| grok-4.3 | 1.25 / 2.50 | 0.20 / 0.40 | 2.50 / 5.00 | −20% |
| grok-4.20 (3 variants) | 1.25 / 2.50 | 0.20 / 0.40 | 2.50 / 5.00 | −20% |
| grok-build-0.1 | 1.00 / 2.00 | 0.20 / 0.40 | 2.00 / 4.00 | none |

Surcharges: Priority Processing 2x; US-regional endpoint 1.1x; "Grok 4.7 Fast" 2x
below 200k and 1.5x above (Cursor/Grok Build only, no API ID) [1][23]. Tools: web search $5/1k calls; X search $5/1k posts + $10/1k profiles; code
execution $5/1k; file attachments $10/1k; collections search $2.50/1k [1]. Some
aggregators list 4.7 at $2.00/$0.55/$6.60 [65] — that is the 1.1x regional rate, not
the global list price [1]. **OpenRouter lists `x-ai/grok-4.7` at $1.60 / $0.40
cached / $4.80 (≥200k: $3.20 / $0.80 / $9.60), with `xai/zdr` and `xai/priority`
endpoint variants (priority exactly 2x: $3.20/$9.60), while `grok-4.6` and
`grok-4.5` on the same router sit at the direct list $2/$6 and `grok-4.3`,
`grok-4.20`, `grok-build-0.1` match docs.x.ai exactly [89][90].** The 4.7-only
20% gap is therefore a router-channel price set by xAI (the OpenRouter endpoints
are all provider "xAI", not a reseller), not a data-entry error and not the
regional rate; docs.x.ai/pricing shows no promo and Artificial Analysis still
lists a single provider at $2/$6 [1][91]. Neither side labels it a launch
discount or gives an expiry: on 2026-09-24 the OpenRouter endpoints API still
returns $1.60/$4.80/$0.40 on both the `xai` and `xai/zdr` endpoints (priority
variants exactly 2x) with no promotional field, and OpenRouter's announcements
page has no Grok 4.7 pricing post [110][111] — so it is a standing
channel price with unknown duration (unverified as of 2026-09-24 whether it
persists past the 4.7 launch window).
Practical rule: if we route 4.7 through OpenRouter anyway, budget at $1.60/$4.80
and reconcile against the bill monthly; the direct-key estimates below stay at
$2/$6 as the conservative figure. Free API tier: none [55]. Non-token fees on the pricing
page [1]: Responses API **usage-guideline-violation fee $0.05/request** (charged
when a request is rejected before generation — budget for it in adversarial or
scraped-input jobs); file storage $0.025/GiB/day; collection storage $0.10/GiB/day;
file and collection downloads $0.20/GiB. "Grok 4.7 Fast" is Cursor/Grok Build only
(no API ID) at $4.00/$1.00/$12.00 (<200k) and $6.00/$1.50/$18.00 (≥200k) [1].

**Monthly cost estimate** (assumptions: 150k input + 15k output tokens/job, prompts
<200k so base tier applies, no tool calls, no cache; cache would cut input by up to
75% on repeated prefixes):

| Jobs/mo | grok-4.7 API | grok-4.3 API | grok-4.3 batch | grok-build-0.1 API | Subscription route |
|---|---|---|---|---|---|
| 10 (~1.65M tok) | $3.90 | $2.25 | $1.80 | $1.80 | SuperGrok $30 — almost certainly fits |
| 100 (~16.5M tok) | $39 | $22.50 | $18 | $18 | ~4M tok/week of Build; pool undisclosed — likely Plus $100 or Heavy $300 (unverified) |
| 1,000 (~165M tok) | $390 | $225 | $180 | $180 | ~41M tok/week; no evidence any pool covers it; API cheaper anyway |

Per-job: 4.7 = $0.30 in + $0.09 out = $0.39; 4.3 = $0.1875 + $0.0375 = $0.225.
Add ~$1.00 per job if it pulls 200 X posts via `x_search` [1]. Verdict: the API is
the cost path here; a subscription only wins below ~75 jobs/month and carries ToS
and pool-opacity risk.

## 5. Strengths & weaknesses per reviews

**Independent benchmarks.**
- Artificial Analysis (2026-09-21): Grok 4.7 Intelligence Index **46** on index
  v4.3.2 (+2 over 4.6 on the same index version); Claude Fable 5.1 and GPT-6 at 53
  (the "v4.3.2" label and the 53s are confirmed only via The Decoder [21]; the AA
  article itself states neither — unverified as of 2026-09-24).
  Coding Agent Index 56 with Grok Build (DeepSWE v1.1 73%, Terminal-Bench 4.0 33%,
  SWE-Atlas-QnA 63%). AA-Briefcase 1657 Elo, GDPval-AA 1695 Elo (both +90–110 over
  4.6). Hallucination rate 29% (down from 34%), accuracy 47%. Token hunger: ~81k
  output tokens per index task vs 36k for 4.6 (+125%), ~188 tok/s, 7.1 min/task.
  Regressions on AA-LCR (−3.7 pts) and AutomationBench (−1.1) [18][61]. Note: AA's
  August write-up scored Grok 4.6 at **61** on the *older* index version and called it
  Pareto-frontier on cost ($0.84/task) [19]; the 46 vs 61 gap is an index re-version,
  not a regression.
- Vendor-reported (x.ai/news/grok-4-7, 2026-09-21, fetched directly this pass)
  [79]: CursorBench 4.0 46.3% (GPT-5.6 Sol 41.7%, Fable 5.1 51.8%), DeepSWE v1.1
  71.0% (footnoted "high effort"), EEBench 64.0%, AA Briefcase v1.1 1,657,
  **Terminal-Bench 4.0 37.6%** (GPT-5.6 Sol 37.3%, Fable 5.1 57.9%), Harvey Legal
  Agent 19.6%, HealthBench Professional 56.7%. **Discrepancy resolved:** the
  "38.0%" carried earlier in this doc came from kingy's secondary table [22], which
  rounds and labels the row "Grok 4.7 xhigh"; the first-party figure is 37.6% and
  the cross-cut docs are right. The Decoder's independent read: Terminal-Bench 4.0
  26% vs GPT-6 Astra 60% / Fable 5.1 55%, "wide gap" in agentic coding [21]. The
  26/33/37.6 spread is harness/effort dependent; xAI's page footnotes effort only
  for DeepSWE, while the OpenRouter model card states xAI "uses xhigh reasoning
  effort for benchmark reporting" [89].
- Grok 4.6: Vals SWE-bench 95.6%, LiveCodeBench 88.2%, Terminal-Bench v3.0 26% vs
  v2.1 88.4% ("same model, incomparable versions") [24].
- LMArena: no Grok 4.x model in the Sep-2026 text top-10 (Claude Fable 5 / Mythos 5
  / Opus 5 lead at ~1525–1531; Grok 4.5 is #14 at 1499 and Grok 4.3 #15 at 1496 per
  swfte 2026-09-24; Claude Opus 4.8, Gemini 3.1 Pro, GPT-5.5 Pro lead); Grok 4.5 appears on Agent/Vision/Document boards [66];
  llm-stats still shows only Grok 4.1 Thinking (1483) [64]. GPQA/HLE for 4.7: not
  reported by AA, kingy or The Decoder [18][21][22] (unverified as of 2026-09-24).

**Best at (per sources):** price/performance on knowledge-work agent evals
(GDPval, Briefcase, legal/EE benches) [18][22]; real-time X + web data as native
tools [13][57]; parallel sub-agent coding at low token price [36]; cheap 1M-context
tier (`grok-4.3`) [1]. Cursor ships it as a first-class model [40].

**Weak at:** long-horizon terminal/agentic coding vs Claude/GPT-6 [21][18];
instruction adherence and consistency (reviewers: Claude "more obedient and
reliable"; Grok Build "not yet worth replacing Claude Code as your default if
reliability and depth matter" — both quotes from buildfastwithai dated 2026-05-26,
i.e. the grok-build-0.1 era, pre-4.5/4.6/4.7; not a Grok 4.7-era verdict,
unverified as of 2026-09-24 for the current model) [36]; token efficiency at xhigh
[18]; hallucination rate still 29% [18].

**Vendor-concentration risk (new since Aug 2026):** model (SpaceXAI), IDE (Cursor,
wholly owned since 2026-08-14), cloud agent (Grok Bot in Cursor's cloud), social
data (X) and the consumer payment rail (X Money, invite-only since 2026-07-29) are
now one corporate group [72][76][78]. For us that means a single ToS/pricing/outage
decision can hit the model, the coding tool and the data feed at once — one more
reason to keep Grok swappable behind the router rather than wired into a lane.

**Reliability / outages 2026:** mid-Jan (shared X infra, API affected), Jan 23
(maintenance), March (auth failures, API affected), early April [49]; an "Apr 21
multi-day outage coinciding with 4.3 beta + Cursor compute commitments" is
unverified as of 2026-09-24 (ibtimes [49] is dated 2026-04-23 and lists only the
four incidents above); Sep 3 broad "model unavailable" outage (same day ChatGPT and
Claude also had incidents — Axios [50] returns 403; rests on [51]) [49][50][51].
`status.x.ai` exists but blocks fetchers. "High demand" throttling is the most
common user complaint [49]. **Normalized window (StatusGator "Grok" feed, one
source, checked 2026-09-24)** [92]: August 2026 3 incidents; September 2026 5+
incidents through 09-24, latest 09-22 01:05 UTC major (18 min) and 01:23 minor
(10 min), 09-10 minor (10 min); 2 user-submitted reports in the prior 24 h.
OpenRouter's per-endpoint uptime for `grok-4.7` on the same day: 98.4–99.4%
(30 min / 1 day windows) on the default endpoint, 99.3% (29 d) on the priority
endpoint [90]. **Priority/SLA tier:** `service_tier: "priority"` at 2x is a
best-effort queue-jump — the pricing page carries "no service level agreements or
uptime guarantees", and the enterprise ToS offers only a 30-day non-conformity
remedy (fix or pro-rata refund), no numeric SLA [1][82]. Use this row when the
cross-cut reliability table is rebuilt: source = StatusGator Grok, window = Aug
1–Sep 24 2026, count = 8+, SLA tier = none.
**Interactive-surface latency (Telegram round trip):** Artificial Analysis
measures Grok 4.7 (xhigh) at **0.92 s TTFT, 40.4 tok/s** end-to-end on the xAI
endpoint (the 188 tok/s in the AA article is answer-token speed on long prompts
after reasoning) [91][18]; at `reasoning_effort: low` on `grok-4.3` TTFT is
sub-second in practice but not independently published (unverified as of
2026-09-24). Rating for the chat surface: **suitable** as a streamed backend
(first token well under Telegram's edit-throttle), **unsuitable at xhigh** for a
single-message reply (7.1 min/task median on the index [18]) — stream or use
low/medium effort for chat.

**Controversies (attributed):** "MechaHitler" antisemitic outputs (Jul 2025);
"white genocide" prompt injection (May 2025); Musk-sycophancy episode (Nov 2025);
sexual-deepfake scandal Dec 2025–2026 with Ofcom investigation, French raid on X's
Paris office, Indonesia/Malaysia blocks, 35 US AGs, Imagine paywalled Mar 19 2026
[40][41]; Grok Build silently uploading **entire git repos incl. secrets** to a GCS
bucket (~27,800x more data than the task needed; the `/privacy` toggle did nothing;
fixed by a server-side flag; Musk promised deletion; source published as a
no-PRs snapshot — snapshot status unverified as of 2026-09-24) [37][38][39]. Note
the upload happened *outside* any sandbox: the Landlock/Seatbelt sandbox (§3) now
lets you deny-glob secrets at the kernel level, but it is off by default and blocks
network only on Linux, so on macOS it would not have stopped this class of leak —
the telemetry env kill-switches remain the primary control [68][69]; Grok chats
indexed by Google (Aug 2025) [40]; Grokipedia bias, and "frozen since ~Apr 2026"
(unverified as of 2026-09-24) [42]. HN sentiment on Grok Build:
trust dominates ("the reason they open sourced this is because grok-build uploaded
entire directories" — the_duke) [60].

## 6. Finance / trading relevance

- **Real-time X data:** `x_search` is the only first-party LLM tool with live X posts,
  threads, profiles and post media; filter to ≤20 handles and a date window; billed
  $5/1k posts + $10/1k profiles plus tokens; usage reported in
  `usage.server_side_tool_usage_details.x_posts_fetched` [13][1]. Compare raw X API
  at $0.005/post read, 3M reads/mo cap, with up to 20% back in xAI credits [56].
- **Web search** tool ($5/1k) for news/filings [1]; **code execution** ($5/1k) for
  ad-hoc quant work [1]. **First-party finance products:** none from xAI itself —
  no market-data or broker connector in the API docs [1][77]. Adjacent: **Kalshi**
  integrated Grok 4 into its real-money prediction-market app (The Block / Yellow,
  2025-07-24/25 — a Kalshi-side API integration, not an xAI product; no 2026 update
  found); a Polymarket tie-up was not found; **X Money** launched invite-only on
  2026-07-29 (Visa debit card, 6% yield, real-time transfers) and drew
  account-takeover reports by 2026-09-02 — a payment rail, not a trading or data
  surface, and nothing links it to the Grok API [78]. All three are headline-level
  from the Google News index (article bodies not fetched; unverified as of
  2026-09-24).
- **Community evidence:** Grok 4 led a public AI stock-picking contest early 2026
  (+8.2% by mid-Jan) [59]; practitioner write-ups value it for sentiment-shift and
  event detection with a claimed 15–30 min lead over newswires, but stress it "cannot
  analyze live price charts", ~55–65% accuracy on unconfirmed rumors, "a detection
  tool, not a signal generator" [57]; a hands-on test had it produce TSLA
  entry/target/stop and working Pine Script but no comparative benchmark [58].
- **Restrictions:** AUP is content-focused; no financial-advice prohibition found
  [54]; X-data redistribution/storage limits not stated on the x_search page [13].
  Output "must not be relied on as sole truth" [52]. Fits Atlas's advisor/shadow-ledger
  posture (no order path) as a *sentiment feed and adversarial second opinion*, not
  as a decision engine.

## 7. Integration recipe for our server

**Recommended path:** metered **API key** (prepaid credits, no subscription), called
from the existing Python 3.12 runner through the OpenAI-compatible client (already
the lingua franca for the router plan) — reserve `xai-sdk` for `x_search`/Collections
if the gRPC client is needed. Do **not** wire Grok Build's subscription login into
launchd jobs: the pool is opaque and not machine-readable, the AUP's "using bots
to access" clause is a policy risk, and a seat carries no right to serve output to
other people (§3); if the owner wants a subscription seat for interactive use,
keep it interactive.

```python
# pip install openai   (or: pip install xai-sdk)
import os, json
from openai import OpenAI
client = OpenAI(api_key=os.environ["XAI_API_KEY"], base_url="https://api.x.ai/v1")

# 1) cheap classification / routing with structured output
r = client.chat.completions.create(
    model="grok-4.3",
    messages=[{"role": "user", "content": "Classify this job request: ..."}],
    response_format={"type": "json_schema", "json_schema": {"name": "route",
        "schema": {"type": "object", "properties": {"lane": {"type": "string"},
                   "confidence": {"type": "number"}}, "required": ["lane"]}}})
print(json.loads(r.choices[0].message.content))

# 2) X sentiment pull (server-side tool, Responses API)
r = client.responses.create(
    model="grok-4.7",
    input="Summarize sentiment on $SPY in the last 24h; cite posts.",
    tools=[{"type": "x_search", "allowed_x_handles": ["unusual_whales", "zerohedge"],
            "from_date": "2026-09-23", "to_date": "2026-09-24"}],
    store=False)
print(r.output_text, r.usage)   # usage.server_side_tool_usage_details.x_posts_fetched
```

Headless coding (only if evaluated worth it; keep it in a throwaway workspace):

```bash
export XAI_API_KEY=xai-...   # never subscription auth in cron
export GROK_TELEMETRY_ENABLED=false GROK_TELEMETRY_TRACE_UPLOAD=0
# optional progress feed (content-free by default): double opt-in
export GROK_EXTERNAL_OTEL=1 OTEL_METRICS_EXPORTER=otlp OTEL_LOGS_EXPORTER=otlp \
       OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4318
grok -m grok-4.7 --sandbox strict --max-turns 30 --permission-mode bypassPermissions \
     -p "Run the failing pytest and propose a patch" \
     --output-format streaming-json > "$AUDIT/grok-$JOB.jsonl"
# or, for one JSON summary incl. total_cost_usd + sessionId (resume with -r):
# grok -m grok-4.7 --sandbox strict --max-turns 30 --yolo --prompt-file task.md \
#      --output-format json > "$AUDIT/grok-$JOB.json"
```

**Task-class fit:** research (good — web+X tools, cheap 1M-context `grok-4.3` for
bulk summarization) [1][12][13]; coding (usable for parallel migrations, behind
Claude for depth) [36][21]; code review (second-opinion tier only; instruction
adherence weaker) [36]; chat via Telegram bot (fine as a routed backend; no native
Telegram surface) [43]; classification/routing (good — `grok-4.3` batch at
~$0.18/job) [1][11]; adversarial review (good value — differently-trained critic
at $0.39/job) [18]; trading research (best-in-class X sentiment feed; not a signal
engine) [57].

**Gotchas:** (1) `x.ai` 403s scripted fetches — pin `docs.x.ai` for docs. (2) Grok
Build's repo-upload incident: always set the telemetry env kill-switches AND run
with `--sandbox strict` (or a custom profile with `deny = ["**/.env", "**/*.pem"]`);
remember the sandbox is off by default and its network block is a no-op on macOS,
so still treat the binary as untrusted with secrets [37][68]. (2b) Headless Grok
Build ignores piped stdin — use `--prompt-file`; and `--tools`/`--max-turns` are
headless-only flags [70]. (3) Weekly pools reset unpredictably, and
Grok Bot has no spend cap [30][33]. (4) Responses stored 30 days unless
`store:false` [9]. (5) Reasoning models return encrypted reasoning; budget ~2x the
output tokens you expect at xhigh [18]. (6) Batch discount only on 4.3/4.20 [1]. (7)
Long-context (≥200k) doubles the rate for the *whole* request [1]. (8) Model IDs
churn every ~6 weeks; no `-latest` aliases exist for the text models on
docs.x.ai/developers/models (only `grok-voice-latest` for voice); pin explicit IDs
(`grok-4.7`, `grok-4.3`) in config and bump deliberately [2]. (9) Outage
history argues for Grok as a fallback/second-opinion lane, never sole provider [49].
(10) **Tool churn / cost of ownership:** the `xai-org/grok-build` mirror receives
"Synced from monorepo" commits from `grokkybara[bot]` every 1–3 days (Sep 8, 9,
15, 17, 19, 22, 23 in the last fortnight), has **no tags, no GitHub releases and
no CHANGELOG in-repo**; the only release notes are `x.ai/build/changelog` (403 to
fetchers, JS-rendered in the Wayback copy), and "External contributions are not
accepted" [93][5]. There is no documented semver, deprecation window or
breaking-change policy, and the flags table in user-guide 14 already differs from
the 2026-05 reviews (e.g. `--yolo` vs `--permission-mode`). Operational burden
rating: **high** — pin the installed binary, re-run a smoke test of the exact
flags used (`-p`, `--output-format json`, `--sandbox`, `--max-turns`) after every
upgrade, and keep the API-key lane as the fallback that does not depend on the
CLI at all. Compare: the Responses API itself has had additive-only release notes
May–Sep 2026 [15].

## 8. Verdict

1. Grok 4.7 is a cheap, fast-moving mid-pack frontier model with the only native
   real-time X data tool; it is not a Claude/GPT-6 replacement for agentic coding.
2. Integrate via metered API key + OpenAI-compatible client; skip subscription-based
   headless use (opaque, non-machine-readable weekly pool; AUP "using bots to
   access" and no-credential-sharing clauses, now verified verbatim [80][81]; no
   third-party-serving right on a seat; no free credits). Consider routing 4.7
   through OpenRouter's xAI endpoints at $1.60/$4.80 (20% under direct list, ZDR
   variant available, no promo label — re-check monthly) if the router is already
   in the stack [90][110]. Direct-key ZDR is self-serve (console → Team Settings)
   but drops Batch and stateful Responses [98].
3. Cost per 165k-token job ≈ $0.39 (4.7) / $0.22 (4.3) / $0.18 (batch or build-0.1).
4. Best server roles: X-sentiment feed for Atlas research, cheap classifier/router,
   adversarial second reviewer, bulk 1M-context summarization.
5. Risk profile is the worst of the majors: repeated outages, repo-upload incident,
   content scandals, vendor/rebrand churn, and since 2026-08-14 a single corporate
   group owning model + IDE (Cursor) + cloud agent + X data — keep it non-critical
   and swappable. Expect `grok-4.8` within weeks (training completed 2026-09-22 per
   Musk); pin explicit IDs, there are no `-latest` aliases for text models.
6. If Grok Build is ever run headless, the tooling is better than first assessed:
   session resume (`-r`/`-c`), JSON output with `total_cost_usd` + `sessionId`,
   `--max-turns`, `--sandbox strict` with secret deny-globs, and a content-free
   double-opt-in OTEL stream for progress watching. The constraints that remain are
   policy (AUP "using bots to access", single-seat only, no output resale —
   verified 2026-09-24), progress visibility (remaining pool is TUI-only on every
   surface) and platform (macOS sandbox does not block network), not tooling.

Fit scores (1–10): research **7**; coding/agentic **5**; cost efficiency **8**;
automation friendliness **7** (raised from 6 after verifying resume, sandbox and
OTEL export); trading research **7**.

**Calibration anchors for the cross-provider scorecard** (so the router design
can compare this row with the other docs): research 7 = has native web + social
search tools and 1M-context cheap tier, but 29% hallucination rate and no
citations-quality eval; coding 5 = Terminal-Bench 4.0 37.6% self-reported / 26%
independent vs 55–60% for the leaders, CursorBench 46.3% vs 51.8%; cost 8 =
$2/$6 list ($1.60/$4.80 via router), $0.39 per 165k-token job, batch only on
4.3/4.20; automation 7 = full headless CLI + JSON/OTEL + sandbox + resume on the
API-key lane, minus 2 for no quota introspection and tool churn, minus 1 for
subscription-lane policy; trading 7 = only first-party live-X tool, no
market-data or broker surface, community evidence only. Scale used: 10 = best
available in any doc on that dimension, 5 = usable with caveats, 1 = unusable.

## 9. Sources

All accessed 2026-09-24.

1. https://docs.x.ai/developers/pricing
2. https://docs.x.ai/developers/models
3. https://docs.x.ai/developers/rate-limits
4. https://docs.x.ai/build/overview
5. https://github.com/xai-org/grok-build
6. https://github.com/xai-org/grok-build/blob/main/crates/codegen/xai-grok-pager/docs/user-guide/02-authentication.md
7. https://github.com/xai-org/xai-sdk-python
8. https://docs.x.ai/developers/quickstart
9. https://docs.x.ai/developers/model-capabilities/text/generate-text
10. https://docs.x.ai/developers/model-capabilities/text/structured-outputs
11. https://docs.x.ai/developers/advanced-api-usage/batch-api
12. https://docs.x.ai/developers/tools/web-search
13. https://docs.x.ai/developers/tools/x-search
14. https://docs.x.ai/developers/tools/function-calling
15. https://docs.x.ai/developers/release-notes
16. https://docs.x.ai/grok-bot/overview
17. https://docs.x.ai/developers/community
18. https://artificialanalysis.ai/articles/benchmarking-grok-4-7
19. https://artificialanalysis.ai/articles/grok-4-6-benchmarks-and-analysis
20. https://artificialanalysis.ai/models/grok-build-0-1-06-16
21. https://the-decoder.com/xai-launches-grok-4-7-at-bargain-prices-but-benchmarks-reveal-a-wide-gap-to-claude-and-gpt-6/
22. https://kingy.ai/blog/grok-4-7-benchmarks-specs-frontier-comparison/
23. https://tbreak.com/xai-grok-4-7-launch-price-benchmarks/
24. https://codersera.com/blog/grok-4-6-benchmarks-explained-2026/
25. https://www.ai-toolbox.co/grok-models/grok-pricing-plans-api-2026
26. https://pricepertoken.com/subscriptions/grok
27. https://www.cloudzero.com/blog/grok-pricing/
28. https://felloai.com/grok-pricing/
29. https://tracecheck.dev/grok-build/usage-limits/
30. https://christopheralarcon.com/blog/grok-usage-limits-explained
31. https://suprmind.ai/hub/grok/pricing/
32. https://geotoolbox.ai/blog/grok-pricing
33. https://www.aibuilderclub.com/blog/grok-bot-pricing
34. https://www.engadget.com/2259931/spacexai-grok-bot-early-beta-how-to-try/
35. https://x.ai/news/grok-build-mode
36. https://blog.buildfastwithai.com/grok-build-xai-cli-ai-agents-2026
37. https://gist.github.com/cereblab/dc9a40bc26120f4540e4e09b75ffb547
38. https://www.theregister.com/ai-and-ml/2026/07/14/musk-promises-purge-after-grok-build-caught-sending-entire-repos-to-the-cloud/5271123
39. https://thehackernews.com/2026/07/grok-build-uploads-entire-git.html
40. https://en.wikipedia.org/wiki/Grok_(chatbot)
41. https://en.wikipedia.org/wiki/Grok_sexual_deepfake_scandal
42. https://en.wikipedia.org/wiki/Grokipedia
43. https://en.wikipedia.org/wiki/Telegram_(software)
44. https://theplanetsoft.com/how-to-use-grok-ai-in-telegram/
45. https://finance.yahoo.com/technology/ai/articles/xai-makes-rebrand-spacexai-complete-215010760.html
46. https://www.mindstudio.ai/blog/grok-automations-scheduled-tasks-email-triggers
47. https://www.mindstudio.ai/blog/xai-grok-roadmap-7-models-training-grok-5-10-trillion
48. https://geotoolbox.ai/blog/grok-5
49. https://www.ibtimes.com/grok-service-outages-spark-frustration-2026-xai-struggles-explosive-demand-3801803
50. https://www.axios.com/2026/09/03/chatgpt-claude-grok-outages
51. https://www.roic.ai/news/grok-down-xais-ai-assistant-suffers-widespread-outage-09-03-2026
52. https://conductatlas.com/platform/xai/xai-terms-of-service/
53. https://x.ai/legal/terms-of-service (403 to fetcher; the search-index clause formerly cited here is NOT in the 2026-09-11 text — superseded by [80])
54. https://grokipedia.com/page/xAI_Acceptable_Use_Policy
55. https://www.eesel.ai/blog/xai-pricing
56. https://docs.x.com/x-api/getting-started/pricing
57. https://beginnersinai.org/grok-for-traders-investors/
58. https://blog.pickmytrade.trade/ai-trading-bot-grok-test/
59. https://paretoinvestor.substack.com/p/grok-is-crushing-the-s-and-p-500
60. https://hn.algolia.com/api/v1/search?query=grok%20build&tags=story (HN threads: "Grok Build is open source", 590 pts; "What xAI's Grok build CLI sends to xAI", 539 pts)
61. https://x.com/ArtificialAnlys/status/2102074909623271513
62. https://developers.cloudflare.com/ai-gateway/usage/providers/grok/
63. https://x.ai/news/grok-code-fast-1
64. https://llm-stats.com/benchmarks/lmarena-text
65. https://mem0.ai/blog/xai-grok-api-pricing
66. https://www.swfte.com/lmarena
67. https://github.com/xai-org/grok-build/blob/main/crates/codegen/xai-grok-pager/docs/user-guide/17-sessions.md
68. https://github.com/xai-org/grok-build/blob/main/crates/codegen/xai-grok-pager/docs/user-guide/18-sandbox.md
69. https://github.com/xai-org/grok-build/blob/main/crates/codegen/xai-grok-pager/docs/user-guide/26-config-reference.md
70. https://github.com/xai-org/grok-build/blob/main/crates/codegen/xai-grok-pager/docs/user-guide/14-headless-mode.md
71. https://github.com/xai-org/grok-build/blob/main/crates/codegen/xai-grok-pager/docs/user-guide/24-monitoring-usage.md
72. https://en.wikipedia.org/wiki/Cursor_(code_editor)
73. https://github.com/xai-org/grok-build/blob/main/crates/codegen/xai-grok-pager/docs/user-guide/16-subagents.md
74. Google News index (news.google.com/rss/search?q="Grok 4.8" training), headlines: CGTN 2026-09-14 "Musk: Grok 4.8, which is a 2.5T model trained with our new C++ software stack, will finish training this week and start RL"; Analytics India Mag 2026-09-15 "Musk reveals Grok 4.8's pre-training stack is written in C++ by 'humans', not AI"; 36kr 2026-09-22 "Grok 4.7 officially launched ... Musk confirms Grok 4.8 training is fully completed" (headline-level; bodies not fetched)
75. Google News index (news.google.com/rss/search?q=Tesla Grok in-car 2026), headlines dated 2026-04-13 (Not a Tesla App), 2026-07-07 (BASENOR), 2026-07-21 (Electrek, driveteslacanada), 2026-07-22 (teslahubs), 2026-08-31 (driveteslacanada), 2026-09-23 (Dataconomy) (headline-level; bodies not fetched)
76. Google News index (news.google.com/rss/search?q=Grok Slack OR WhatsApp OR Discord integration xAI 2026) — no matching first-party or press coverage returned
77. https://docs.x.ai/developers/tools/overview
78. Google News index (news.google.com/rss/search?q=Grok Polymarket OR Kalshi OR "X Money" 2026), headlines: The Block 2025-07-24 "Elon Musk's Grok AI integrates with Kalshi"; Yellow 2025-07-25; WBAL-TV 2026-07-29 "Elon Musk launches invite-only X Money with a Visa debit card, 6% yield and real-time transfers"; The American Bazaar 2026-09-02 "X Money faces security concerns" (headline-level; bodies not fetched)
79. https://x.ai/news/grok-4-7 (fetched directly 2026-09-24; benchmark table incl. Terminal-Bench 4.0 37.6%)
80. https://x.ai/legal/terms-of-service — Consumer ToS, Last Updated 2026-09-11; read via Wayback capture https://web.archive.org/web/20260921155400/https://x.ai/legal/terms-of-service
81. https://x.ai/legal/acceptable-use-policy — AUP, Effective 2026-08-14; read via Wayback capture https://web.archive.org/web/20260921183014/https://x.ai/legal/acceptable-use-policy
82. https://x.ai/legal/terms-of-service-enterprise — Enterprise ToS, Last Updated 2026-08-14; read via Wayback capture https://web.archive.org/web/20260921155357/https://x.ai/legal/terms-of-service-enterprise
83. https://x.ai/legal/privacy-policy — Effective 2026-08-24; read via Wayback capture https://web.archive.org/web/20260921183027/https://x.ai/legal/privacy-policy
84. https://docs.x.ai/developers/advanced-api-usage/regions
85. https://docs.x.ai/grok/faq (weekly pool; Settings → Usage progress bar)
86. https://github.com/xai-org/grok-build/blob/main/crates/codegen/xai-grok-pager/docs/user-guide/04-slash-commands.md
87. https://github.com/xai-org/grok-build/blob/main/crates/codegen/xai-grok-pager/docs/user-guide/25-status-line.md
88. https://github.com/xai-org/grok-build/blob/main/crates/codegen/xai-grok-pager/docs/user-guide/23-dashboard.md
89. https://openrouter.ai/x-ai/grok-4.7 (model card; "$1.60/$4.80"; "xhigh reasoning effort for benchmark reporting")
90. https://openrouter.ai/api/v1/endpoints/x-ai/grok-4.7 and https://openrouter.ai/api/v1/models (endpoint list: xai, xai/zdr, xai/priority, xai/zdr/priority; per-endpoint uptime; 4.6/4.5 at $2/$6)
91. https://artificialanalysis.ai/models/grok-4-7 and /providers (TTFT 0.92 s, 40.4 tok/s, single provider at $2/$6)
92. https://statusgator.com/services/grok (incident history Aug–Sep 2026)
93. https://github.com/xai-org/grok-build/commits/main (bot sync cadence) and https://github.com/xai-org/grok-build/releases (empty)
94. https://x.ai/news/grok-bot-more-plans (2026-08-26, fetched directly 2026-09-24: "included with all SuperGrok, Cursor Pro, and Cursor Teams plans"; separate usage)
95. https://cursor.com/help/grok-bot/plans (linkable: SuperGrok, Plus, Heavy, X Premium+; not supported: Lite, Team, Enterprise; Pro/Pro+/Ultra relative weekly usage; on-demand monthly limit)
96. https://docs.x.ai/grok-bot/faq (weekly usage, "whichever has more usage", one computer-use task per Bot)
97. https://docs.x.ai/grok-bot/approvals-security-and-privacy (approval classes; "Do not use separate Bots as a security boundary")
98. https://docs.x.ai/developers/faq/security (self-serve ZDR: "Team admins can enable or disable ZDR from the Console"; disabled-feature list; 30-day retention; no training)
99. https://docs.x.ai/build/enterprise (ZDR "enforced at the team level"; `/etc/grok/requirements.toml`; `disable_api_key_auth`) and https://docs.x.ai/build/settings/zdr-video-storage
100. https://docs.openclaw.ai/providers/xai (bundled `xai` plugin; OAuth device-code; "xAI decides which accounts can receive OAuth API tokens")
101. https://hermes-agent.nousresearch.com/docs/integrations/providers ("xAI Grok OAuth (SuperGrok / Premium+)"; `~/.hermes/auth.json`; 403 = entitlement)
102. https://github.com/xai-org/grok-build/blob/main/crates/codegen/xai-grok-pager/docs/user-guide/20-background-tasks.md (50 active scheduled tasks; `/loop`, `monitor`)
103. https://docs.x.ai/console/billing (prepaid credits, Auto Top Up min $5 with monthly cap, invoiced limit default $0, 80% alert)
104. https://github.com/xai-org/grok-build/blob/main/crates/codegen/xai-grok-pager/docs/user-guide/22-permissions-and-safety.md (permission modes; read-only incl. web search auto-run; no injection guidance)
105. https://docs.x.ai/grok-bot/security (outside content "marked as untrusted data"; Auto Review; Enterprise-only egress allowlists; shared static egress IPs)
106. https://docs.openclaw.ai/install (Node 24.16+/26.1+; no RAM figure)
107. Google News index (news.google.com/rss/search?q=xAI Grok Claude outputs training Anthropic cut off), headlines: WIRED 2026-04-30 "Elon Musk Seemingly Admits xAI Has Used OpenAI's Models to Train Its Own"; The Decoder / opentools.ai 2026-06-06 "xAI trained its coding models on Claude outputs for months before getting cut off"; WinBuzzer 2026-06-07 "xAI Reportedly Used Workaround to Train Grok With Claude Output After January Cutoff" (headline-level; bodies not fetched)
108. https://artificialanalysis.ai/models/grok-4-3 (Grok 4.3 (high): TTFT 21.24 s, 123.2 tok/s)
109. Google News index (news.google.com/rss/search?q="SuperGrok Plus" OR "SuperGrok Lite" price), headlines: The Economic Times 2026-03-26 "xAI unveils affordable SuperGrok Lite subscription priced at $10 per month"; Moneycontrol 2026-03-25/26; no headline prices SuperGrok Plus (headline-level)
110. https://openrouter.ai/api/v1/models/x-ai/grok-4.7/endpoints (2026-09-24: xai and xai/zdr at $1.60/$4.80/$0.40, priority variants $3.20/$9.60/$0.80; created 1790007541; no promo field)
111. https://openrouter.ai/announcements (no Grok 4.7 pricing post as of 2026-09-24)

## Verification log (2026-09-24)

**Corrections applied: 12** — 4 major (Grok Build session resume; Grok Build OS
sandbox exists and is off by default; no `-latest` aliases for text models; Grok Bot
inclusion in SuperGrok $30 is conflicting between sources) and 8 minor (Grok 4.7
Fast is Cursor/Build-only with 1.5x long-context uplift; LMArena leaders and Grok
4.5/4.3 ranks; `GROK_TELEMETRY_TRACE_UPLOAD=0` and `[harness]
disable_codebase_upload` not in the official config reference; Cursor is a SpaceX
subsidiary since 2026-08-14; Grok Bot runs in Cursor's cloud; full
`--output-format` list, JSON fields, no-stdin note; sub-agent "up to 8" replaced by
"no documented maximum" with worktree opt-in; headless snippet now uses `--sandbox
strict --max-turns 30 --permission-mode bypassPermissions`). The same edits also
propagated to the §7 bash snippet (`=0`, sandbox flags) and §4 fee text.

**Claims re-verified in this pass (source fetched 2026-09-24):**
- Headless flags, JSON output fields, no-stdin — grok-build user-guide 14 [70].
- Sandbox platforms/profiles/deny globs, off by default, macOS network no-op,
  irreversible per session — user-guide 18 [68].
- Session resume flags and `~/.grok/sessions/` / `GROK_HOME` — user-guide 17 [67].
- OTEL double opt-in, content-free default, content gates, ZDR independence —
  user-guide 24 [71]; `[telemetry]` keys, `GROK_TELEMETRY_*`, ZDR config keys, and
  absence of `[harness] disable_codebase_upload` — user-guide 26 [69].
- Sub-agents: no stated maximum, `isolation: worktree` — user-guide 16 [73].
- Pricing page: Grok 4.7 Fast label and tiers, $0.05 violation fee, storage and
  download fees, 2x priority, text-model price table — docs.x.ai/developers/pricing [1].
- Release notes May–Sep 2026 (service_tier priority, Files public URLs,
  vad_threshold, voice-transcribe-2.0, 4.5 EU) — docs.x.ai/developers/release-notes [15].
- Server-side tool identifiers (`web_search`, `x_search`, `code_interpreter`,
  `image_generation`, `collections_search`) — docs.x.ai/developers/tools/overview [77].
- Structured-output limits and 400 cases — docs.x.ai structured-outputs [10].
- Cursor acquisition (announced 2026-04-21, closed 2026-08-14, $60B, wholly owned)
  — Wikipedia Cursor + SpaceXAI articles [72]. (Grok Bot "Sand" origin and 4.5
  co-development are NOT in the Wikipedia Cursor article; they stand on [16][40]
  and the fact-checker's note.)
- Grok Bot in Cursor's cloud, plan requirements, weekly reset — docs.x.ai/grok-bot/overview [16].
- Grok 4.8 training statements — headline-level only [74].

**Stale / unverified flags left in place (marked "unverified as of 2026-09-24"):**
free-tier model "Grok 4.6"; "~10 prompts / 2 h" (pricepertoken page dated
2026-06-25); (ToS/AUP quotes — RESOLVED in the gap-fix pass below);
API "no minimum" credit purchase; grok-4.7 image input; Grok Build source
publish date and issues/PRs status; Heavy "$99 intro promo" and the two
buildfastwithai reviewer quotes (2026-05-26, grok-build-0.1 era); Apr 21 multi-day
outage; Build Mode "Heavy only, 2026-07-28"; Grok 4.3 (Apr) and 4.20 (Feb) dates;
Tesla 2026 in-car status (headline-level), Grokipedia frozen, @GrokAI Telegram
bot, Agent Client Protocol, grok-code-fast-1 still serving; Grok Bot beta date
2026-08-11; AA index "v4.3.2" and the Fable 5.1/GPT-6 = 53 figures; Grok 4.9
"Astra/Fable class" (not found). Also still unresolved: no first-party page for
Grok Bot plans/billing; Slack/WhatsApp/Discord — no official integration found;
Kalshi/X Money — headline-level only. WebSearch budget was exhausted at the start
of this pass (200/200), so all new evidence came from direct WebFetch of
docs.x.ai, GitHub, Wikipedia and Google News RSS.

**Gap-fix pass (2026-09-24, later the same day):** (a) Terminal-Bench 4.0
self-report corrected 38.0% → **37.6%** from the first-party announcement [79];
kingy's 38.0% [22] was a secondary rounding. (b) OpenRouter $1.60/$4.80 vs direct
$2/$6 explained as a 4.7-only xAI router-channel price (4.6/4.5 on OpenRouter are
$2/$6; all endpoints are provider xAI; AA lists one provider at $2/$6) [89][90][91].
(c) ToS quotes: the "more request messages than a human can reasonably produce"
clause is **absent** from the current consumer ToS (2026-09-11) and withdrawn; the
AUP (2026-08-14) "using bots to access" and "Scraping, harvesting or reselling any
Input or Output" clauses are now quoted verbatim from Wayback captures [80][81];
enterprise ToS (no-training, 30-day delete, ZDR transient, Bundled Service right)
and privacy policy (API excluded, training toggle, 30-day deletion) likewise
[82][83]. (d) Added the cross-doc rows: data-handling matrix per lane,
progress-visibility/quota-introspection inventory, third-party-serving rule,
normalized reliability window with SLA-tier note, interactive-latency rating,
tool-churn burden, and scorecard calibration anchors. Still unverified: whether
the OpenRouter 4.7 price is a time-limited promo; ZDR availability on a
self-serve console account; `x.ai/build/changelog` contents (JS-rendered, 403).
`x.ai/legal/terms-of-service-consumer` (the URL cited as [53]) is 404 on Wayback —
the consumer ToS lives at `/legal/terms-of-service` [80]; [53] is superseded.

**Gap-fix pass 2 (2026-09-24, WebSearch budget 200/200 exhausted; direct fetches
only):** (a) Grok Bot plan inclusion RESOLVED — all SuperGrok tiers since
2026-08-26 with a separate pool [94]; Lite/Team/Enterprise not linkable [95].
(b) Consumer prices: Lite $10 press-confirmed [109]; $30/$300 triple-sourced;
**Plus $100 and all annual prices remain [25]-only** (x.ai 403, grok.com/plans
JS) — still unverified first-party. (c) SuperGrok OAuth in OpenClaw and Hermes
CONFIRMED as shipped features, entitlement-gated by xAI, unacknowledged by xAI
[100][101]. (d) ZDR RESOLVED as a self-serve console toggle for team admins,
with the disabled-feature list (Batch, Files, Collections, stateful Responses)
[98]. (e) OpenRouter 4.7 price: still no promo label or expiry on the endpoints
API or announcements [110][111] — duration remains unverified. (f) Added the
cross-cut dimension block in §3: third-party OAuth, concurrency per lane,
credential-lifecycle matrix, injection/sandbox ranking, host resources, progress
sink, empirical-calibration sensitivity (70% cache moves the crossover ~75 →
~120 jobs/mo), reviewer independence (xAI-on-Claude/OpenAI training reports,
headline-level [107]), and Grok 4.3 (high) TTFT 21.24 s [108]. Not done: no
read of `volumes/audit_log` (out of scope); Grok Build RAM, OpenClaw/Hermes
RAM and seat-lane concurrency remain undocumented by the vendors.

**Fact-checker overall quality rating: acceptable.** After this pass the
cost figures in §1/§4/§7/§8 agree ($2/$6 per 1M for 4.7; $0.39 per 165k-token job;
Fast tier Cursor/Build-only), and the verdict reflects the corrected facts (sandbox
and resume exist; automation friendliness raised 6 → 7; vendor concentration and
4.8 churn added).
